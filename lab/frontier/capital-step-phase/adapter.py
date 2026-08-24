#!/usr/bin/env python3
"""Map discrete sizing-step phases from current Next Lab event paths."""

from __future__ import annotations

import bisect
import csv
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
FRONTIER = ROOT / "lab" / "frontier" / "capital-step-phase"
ARTIFACTS = ROOT / "lab" / "artifacts" / "backtests" / "slot-shadow-price"
REFERENCE_CAPITAL = 100.0
ADDITION_STEP = 150.0
BASE_VOLUME = 0.01
PASSIVE = "PASSIVE"
COMPONENTS = {
    "ZT-M30-US30-RANGE-COMP-61f61deaba": "RC16",
    "ZT-M30-US30-RANGE-COMP-64efb16616": "RC4",
    "ZT-H1-US100-CROSS-IN-14b72317b7": "CROSS",
    "ZT-M30-US30-INTRADAY-R-2eb111fc46": "PRESSURE",
    "ZT-H1-US30-RETURN-I-c870a788ec": "RETURN",
    "ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8": PASSIVE,
}
COMPONENT_BY_INDEX = {
    0: "RC16",
    1: "RC4",
    2: "CROSS",
    3: "PRESSURE",
    4: "RETURN",
    5: PASSIVE,
}
RUN_PATHS = {
    "baseline_receiver_time_field": [
        "extended-baseline-receiver-time-field-v1-events-a.csv",
        "extended-baseline-receiver-time-field-v1-events-b.csv",
    ],
    "market_only_receiver_wounded": [
        "extended-market-only-receiver-wounded-slot-shadow-exchange-v1-events-a.csv",
        "extended-market-only-receiver-wounded-slot-shadow-exchange-v1-events-b.csv",
    ],
    "market_only_loser_residual": [
        "extended-market-only-loser-residual-slot-shadow-exchange-v1-events-a.csv",
        "extended-market-only-loser-residual-slot-shadow-exchange-v1-events-b.csv",
    ],
}


def rounded(value: float, digits: int = 6) -> float:
    return round(value, digits)


def source(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "sha256": digest.hexdigest(),
        "bytes": path.stat().st_size,
    }


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y.%m.%d %H:%M:%S")


def drawdown(values: list[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    maximum = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        maximum = max(maximum, peak - cumulative)
    return rounded(maximum)


def raw_multiplier(balance: float) -> int:
    growth = max(0.0, balance - REFERENCE_CAPITAL)
    return max(1, 1 + int((growth + 1.0e-9) // ADDITION_STEP))


def load_events(names: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in names:
        with (ARTIFACTS / name).open("r", encoding="utf-8", newline="") as handle:
            for raw in csv.DictReader(handle):
                row: dict[str, Any] = dict(raw)
                row["sequence"] = int(raw["state_sequence"])
                row["time"] = parse_time(raw["server_time"])
                row["value_a_number"] = float(raw["value_a"])
                row["value_b_number"] = float(raw["value_b"])
                row["stressed_balance_number"] = float(raw["stressed_balance"])
                rows.append(row)
    rows.sort(key=lambda row: row["sequence"])
    return rows


@dataclass
class Lifecycle:
    component: str
    open_time: datetime
    open_sequence: int
    open_volume: float
    open_price: float
    close_time: datetime
    close_sequence: int
    actual_net: float
    stressed_net: float


def build_lifecycles(rows: list[dict[str, Any]]) -> list[Lifecycle]:
    active: dict[str, dict[str, Any]] = {}
    output: list[Lifecycle] = []
    for row in rows:
        component = COMPONENTS.get(row["component_id"])
        if component is None:
            continue
        if row["event"] in {"OPEN", "PASSIVE_FILL"}:
            active[component] = {
                "time": row["time"],
                "sequence": row["sequence"],
                "volume": row["value_b_number"],
                "price": row["value_a_number"],
            }
        elif row["event"] in {"CLOSE", "EXTERNAL_CLOSE"} and component in active:
            opened = active.pop(component)
            output.append(
                Lifecycle(
                    component=component,
                    open_time=opened["time"],
                    open_sequence=opened["sequence"],
                    open_volume=opened["volume"],
                    open_price=opened["price"],
                    close_time=row["time"],
                    close_sequence=row["sequence"],
                    actual_net=row["value_a_number"],
                    stressed_net=row["value_b_number"],
                )
            )
    output.sort(key=lambda item: item.close_sequence)
    return output


def recent_drawdown(values: list[float]) -> float:
    return drawdown(values[-20:]) if values else 0.0


def phase_name(multiplier: int, buffer: float, distance: float, since_up: int | None) -> str:
    if multiplier > 1 and since_up is not None and since_up <= 10 and buffer <= 30.0:
        return "fresh_step_shallow"
    if buffer < 0.0:
        return "below_active_floor"
    if multiplier > 1 and buffer <= 15.0:
        return "upper_step_shallow"
    if distance <= 5.0:
        return "next_step_edge"
    if distance <= 15.0:
        return "next_step_approach"
    if distance <= 30.0:
        return "next_step_near"
    return "step_interior"


def daily_states(rows: list[dict[str, Any]], lifecycles: list[Lifecycle]) -> list[dict[str, Any]]:
    closes = sorted(lifecycles, key=lambda item: item.close_time)
    close_index = 0
    past_values: list[float] = []
    states: list[dict[str, Any]] = []
    last_multiplier: int | None = None
    since_up: int | None = None
    peak = 0.0
    for row in (item for item in rows if item["event"] == "SIZE_DAY"):
        while close_index < len(closes) and closes[close_index].close_time < row["time"]:
            past_values.append(closes[close_index].stressed_net)
            close_index += 1
        balance = row["value_a_number"]
        multiplier = int(round(row["value_b_number"]))
        if last_multiplier is None:
            since_up = None
        elif multiplier > last_multiplier:
            since_up = 0
        elif since_up is not None:
            since_up += 1
        floor = REFERENCE_CAPITAL + (multiplier - 1) * ADDITION_STEP
        next_threshold = REFERENCE_CAPITAL + multiplier * ADDITION_STEP
        peak = max(peak, balance)
        state = {
            "time": row["time"],
            "server_time": row["server_time"],
            "balance": balance,
            "multiplier": multiplier,
            "raw_multiplier": raw_multiplier(balance),
            "floor": floor,
            "floor_buffer": balance - floor,
            "next_threshold": next_threshold,
            "distance_to_next": next_threshold - balance,
            "drawdown_from_daily_peak": peak - balance,
            "recent_20_close_drawdown": recent_drawdown(past_values),
            "days_since_upstep": since_up,
        }
        for lookback in (3, 5, 10):
            state[f"velocity_{lookback}"] = (
                None if len(states) < lookback else balance - states[-lookback]["balance"]
            )
        state["phase"] = phase_name(
            multiplier,
            state["floor_buffer"],
            state["distance_to_next"],
            since_up,
        )
        states.append(state)
        last_multiplier = multiplier
    return states


def state_at(states: list[dict[str, Any]], moment: datetime) -> dict[str, Any]:
    times = [state["time"] for state in states]
    index = bisect.bisect_right(times, moment) - 1
    if index < 0:
        raise RuntimeError(f"sizing state missing before {moment}")
    return states[index]


def lifecycle_slice(
    lifecycles: list[Lifecycle], start: datetime, end: datetime
) -> dict[str, Any]:
    selected = [item for item in lifecycles if start <= item.open_time < end]
    values = [item.stressed_net for item in selected]
    return {
        "entries": len(selected),
        "market_entries": sum(item.component != PASSIVE for item in selected),
        "passive_entries": sum(item.component == PASSIVE for item in selected),
        "actual_net": rounded(sum(item.actual_net for item in selected)),
        "stressed_net": rounded(sum(values)),
        "stressed_drawdown": drawdown(values),
        "by_component": {
            component: {
                "entries": sum(item.component == component for item in selected),
                "stressed_net": rounded(
                    sum(item.stressed_net for item in selected if item.component == component)
                ),
            }
            for component in sorted(set(COMPONENTS.values()))
        },
    }


def transition_map(
    states: list[dict[str, Any]], lifecycles: list[Lifecycle]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, state in enumerate(states):
        if index == 0 or state["multiplier"] == states[index - 1]["multiplier"]:
            continue
        end_index = min(len(states) - 1, index + 5)
        end = states[end_index]["time"]
        if end_index == index:
            end += timedelta(days=1)
        window = lifecycle_slice(lifecycles, state["time"], end)
        output.append(
            {
                "server_time": state["server_time"],
                "direction": "up" if state["multiplier"] > states[index - 1]["multiplier"] else "down",
                "from_multiplier": states[index - 1]["multiplier"],
                "to_multiplier": state["multiplier"],
                "balance": rounded(state["balance"]),
                "floor_buffer": rounded(state["floor_buffer"]),
                "velocity_5": (
                    None if state["velocity_5"] is None else rounded(state["velocity_5"])
                ),
                "recent_20_close_drawdown": rounded(state["recent_20_close_drawdown"]),
                "next_five_sizing_days": window,
            }
        )
    return output


def path_map(
    states: list[dict[str, Any]], lifecycles: list[Lifecycle]
) -> dict[str, Any]:
    transitions = transition_map(states, lifecycles)
    phase_counts: dict[str, int] = defaultdict(int)
    for state in states:
        phase_counts[state["phase"]] += 1
    return {
        "sizing_days": len(states),
        "entries": len(lifecycles),
        "observed_stressed_net": rounded(sum(item.stressed_net for item in lifecycles)),
        "observed_stressed_drawdown": drawdown([item.stressed_net for item in lifecycles]),
        "multiplier_days": {
            str(multiplier): sum(state["multiplier"] == multiplier for state in states)
            for multiplier in sorted({state["multiplier"] for state in states})
        },
        "phase_days": dict(sorted(phase_counts.items())),
        "transitions": transitions,
        "upsteps": sum(item["direction"] == "up" for item in transitions),
        "downsteps": sum(item["direction"] == "down" for item in transitions),
    }


def first_multiplier_state(
    states: list[dict[str, Any]], multiplier: int
) -> dict[str, Any] | None:
    return next((state for state in states if state["multiplier"] >= multiplier), None)


def asynchronous_window(
    baseline_states: list[dict[str, Any]],
    baseline_lifecycles: list[Lifecycle],
    candidate_states: list[dict[str, Any]],
    candidate_lifecycles: list[Lifecycle],
) -> dict[str, Any] | None:
    baseline_step = first_multiplier_state(baseline_states, 2)
    candidate_step = first_multiplier_state(candidate_states, 2)
    if baseline_step is None or candidate_step is None or candidate_step["time"] >= baseline_step["time"]:
        return None
    start = candidate_step["time"]
    end = baseline_step["time"]
    baseline_start = state_at(baseline_states, start)
    candidate_end = state_at(candidate_states, end - timedelta(seconds=1))
    baseline_end = state_at(baseline_states, end - timedelta(seconds=1))
    return {
        "start": candidate_step["server_time"],
        "end_exclusive": baseline_step["server_time"],
        "calendar_days": (end.date() - start.date()).days,
        "candidate_sizing_days_at_2x_while_baseline_1x": sum(
            start <= state["time"] < end and state["multiplier"] >= 2
            for state in candidate_states
        ),
        "candidate": lifecycle_slice(candidate_lifecycles, start, end),
        "baseline": lifecycle_slice(baseline_lifecycles, start, end),
        "balance_delta_at_start": rounded(candidate_step["balance"] - baseline_start["balance"]),
        "balance_delta_before_baseline_step": rounded(
            candidate_end["balance"] - baseline_end["balance"]
        ),
        "limit": "The paths already carry different prior balances and stops; this window is descriptive, not a paired counterfactual.",
    }


def policy_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = [
        {
            "family": "observed_anchor",
            "confirm_days": 1,
            "base_buffer": 0.0,
            "velocity_lookback": 0,
            "minimum_velocity": 0.0,
            "downside_multiple": 0.0,
        }
    ]
    for confirm in (2, 3, 5, 8):
        specs.append(
            {
                "family": "persistence_confirmation",
                "confirm_days": confirm,
                "base_buffer": 0.0,
                "velocity_lookback": 0,
                "minimum_velocity": 0.0,
                "downside_multiple": 0.0,
            }
        )
    for confirm in (1, 2):
        for buffer in (2.5, 5.0, 7.5, 10.0, 15.0):
            specs.append(
                {
                    "family": "static_profit_escrow",
                    "confirm_days": confirm,
                    "base_buffer": buffer,
                    "velocity_lookback": 0,
                    "minimum_velocity": 0.0,
                    "downside_multiple": 0.0,
                }
            )
    for confirm in (1, 2):
        for buffer in (0.0, 5.0):
            for lookback in (3, 5, 10):
                for velocity in (0.0, 2.5):
                    specs.append(
                        {
                            "family": "positive_approach_velocity",
                            "confirm_days": confirm,
                            "base_buffer": buffer,
                            "velocity_lookback": lookback,
                            "minimum_velocity": velocity,
                            "downside_multiple": 0.0,
                        }
                    )
    for confirm in (1, 2):
        for buffer in (0.0, 5.0):
            for multiple in (0.25, 0.5, 0.75, 1.0):
                specs.append(
                    {
                        "family": "recent_downside_escrow",
                        "confirm_days": confirm,
                        "base_buffer": buffer,
                        "velocity_lookback": 0,
                        "minimum_velocity": 0.0,
                        "downside_multiple": multiple,
                    }
                )
    for confirm in (2, 3):
        for buffer in (2.5, 5.0):
            for multiple in (0.25, 0.5):
                specs.append(
                    {
                        "family": "compound_phase_filter",
                        "confirm_days": confirm,
                        "base_buffer": buffer,
                        "velocity_lookback": 5,
                        "minimum_velocity": 0.0,
                        "downside_multiple": multiple,
                    }
                )
    for index, spec in enumerate(specs):
        spec["policy_id"] = f"phase-{index:03d}"
    return specs


def simulate_policy(states: list[dict[str, Any]], spec: dict[str, Any]) -> list[int]:
    proposed: list[int] = []
    active = 1
    eligible_streak = 0
    for state in states:
        target = state["raw_multiplier"]
        if target < active:
            active = target
            eligible_streak = 0
        elif target > active:
            threshold = REFERENCE_CAPITAL + active * ADDITION_STEP
            required = (
                threshold
                + spec["base_buffer"]
                + spec["downside_multiple"] * state["recent_20_close_drawdown"]
            )
            velocity_ok = True
            if spec["velocity_lookback"]:
                velocity = state[f"velocity_{spec['velocity_lookback']}"]
                velocity_ok = velocity is not None and velocity >= spec["minimum_velocity"]
            if state["balance"] >= required and velocity_ok:
                eligible_streak += 1
            else:
                eligible_streak = 0
            if eligible_streak >= spec["confirm_days"]:
                active += 1
                eligible_streak = 0
        else:
            eligible_streak = 0
        proposed.append(active)
    return proposed


def policy_path_result(
    states: list[dict[str, Any]],
    lifecycles: list[Lifecycle],
    proposed: list[int],
) -> dict[str, Any]:
    times = [state["time"] for state in states]
    observed_values: list[float] = []
    adjusted_values: list[float] = []
    slices: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"entries": 0, "observed": 0.0, "adjusted": 0.0}
    )
    suppressed = 0
    for item in lifecycles:
        index = bisect.bisect_right(times, item.open_time) - 1
        if index < 0:
            raise RuntimeError(f"lifecycle before sizing state: {item.open_time}")
        observed_multiplier = states[index]["multiplier"]
        proposed_multiplier = proposed[index]
        ratio = 1.0 if item.component == PASSIVE else proposed_multiplier / observed_multiplier
        adjusted = item.stressed_net * ratio
        observed_values.append(item.stressed_net)
        adjusted_values.append(adjusted)
        if ratio < 1.0:
            suppressed += 1
        key = (
            "2025"
            if item.close_time.year == 2025
            else "2026_h1"
            if item.close_time < datetime(2026, 7, 1)
            else "2026_h2"
        )
        slices[key]["entries"] += 1
        slices[key]["observed"] += item.stressed_net
        slices[key]["adjusted"] += adjusted
    transitions = sum(
        proposed[index] != proposed[index - 1] for index in range(1, len(proposed))
    )
    observed_net = sum(observed_values)
    adjusted_net = sum(adjusted_values)
    observed_dd = drawdown(observed_values)
    adjusted_dd = drawdown(adjusted_values)
    return {
        "entries": len(lifecycles),
        "suppressed_market_entries": suppressed,
        "observed_stressed_net": rounded(observed_net),
        "first_order_adjusted_stressed_net": rounded(adjusted_net),
        "first_order_net_delta": rounded(adjusted_net - observed_net),
        "observed_stressed_drawdown": observed_dd,
        "first_order_adjusted_drawdown": adjusted_dd,
        "first_order_drawdown_delta": rounded(adjusted_dd - observed_dd),
        "proposed_transition_count": transitions,
        "proposed_2x_days": sum(value >= 2 for value in proposed),
        "proposed_3x_days": sum(value >= 3 for value in proposed),
        "first_proposed_2x": next(
            (states[i]["server_time"] for i, value in enumerate(proposed) if value >= 2),
            None,
        ),
        "first_proposed_3x": next(
            (states[i]["server_time"] for i, value in enumerate(proposed) if value >= 3),
            None,
        ),
        "temporal_slices": {
            key: {
                "entries": int(value["entries"]),
                "observed_stressed_net": rounded(float(value["observed"])),
                "first_order_adjusted_stressed_net": rounded(float(value["adjusted"])),
                "first_order_delta": rounded(float(value["adjusted"]) - float(value["observed"])),
            }
            for key, value in sorted(slices.items())
        },
    }


def policy_search(
    run_data: dict[str, dict[str, Any]], specs: list[dict[str, Any]]
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for spec in specs:
        paths: dict[str, dict[str, Any]] = {}
        for name, data in run_data.items():
            proposed = simulate_policy(data["states"], spec)
            paths[name] = policy_path_result(data["states"], data["lifecycles"], proposed)
        net_delta = sum(path["first_order_net_delta"] for path in paths.values())
        dd_reduction = sum(-path["first_order_drawdown_delta"] for path in paths.values())
        worst_dd_increase = max(path["first_order_drawdown_delta"] for path in paths.values())
        slice_deltas = [
            item["first_order_delta"]
            for path in paths.values()
            for item in path["temporal_slices"].values()
        ]
        transition_reduction = sum(
            run_data[name]["map"]["upsteps"]
            + run_data[name]["map"]["downsteps"]
            - path["proposed_transition_count"]
            for name, path in paths.items()
        )
        score = net_delta + 0.35 * dd_reduction + 0.5 * transition_reduction
        results.append(
            {
                "policy": spec,
                "aggregate": {
                    "first_order_net_delta": rounded(net_delta),
                    "drawdown_reduction": rounded(dd_reduction),
                    "worst_path_drawdown_increase": rounded(worst_dd_increase),
                    "worst_temporal_slice_delta": rounded(min(slice_deltas)),
                    "transition_reduction": transition_reduction,
                    "score": rounded(score),
                },
                "paths": paths,
            }
        )
    anchor = next(item for item in results if item["policy"]["family"] == "observed_anchor")
    survivors = [
        item
        for item in results
        if item["policy"]["family"] != "observed_anchor"
        and item["aggregate"]["first_order_net_delta"] >= -3.0
        and item["aggregate"]["worst_path_drawdown_increase"] <= 0.5
        and item["aggregate"]["worst_temporal_slice_delta"] >= -3.0
        and (
            item["aggregate"]["drawdown_reduction"] > 0.5
            or item["aggregate"]["transition_reduction"] > 0
        )
    ]
    survivors.sort(key=lambda item: item["aggregate"]["score"], reverse=True)
    all_ranked = sorted(results, key=lambda item: item["aggregate"]["score"], reverse=True)
    return {
        "hypotheses": len(results),
        "anchor": anchor,
        "survivors": len(survivors),
        "top_survivors": survivors[:16],
        "top_unconstrained": all_ranked[:8],
        "proxy_limit": "Adjusted PnL scales observed stressed outcomes by the proposed market-volume ratio. Real stops, admissions, and exits mutate with sizing, so only a real-tick EA run can judge a candidate.",
    }


def exchange_phase_references(
    run_name: str,
    rows: list[dict[str, Any]],
    states: list[dict[str, Any]],
    lifecycles: list[Lifecycle],
    baseline_lifecycles: list[Lifecycle],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for release in (row for row in rows if row["event"] == "SLOT_EXCHANGE_RELEASE"):
        match = re.search(r"(?:^|\s)incumbent=(\d+)", release["detail"])
        if match is None:
            continue
        incumbent = COMPONENT_BY_INDEX[int(match.group(1))]
        candidate = COMPONENTS[release["component_id"]]
        forced = next(
            (
                item
                for item in reversed(lifecycles)
                if item.component == incumbent
                and item.close_time == release["time"]
                and item.close_sequence < release["sequence"]
            ),
            None,
        )
        admitted = next(
            (
                item
                for item in lifecycles
                if item.component == candidate
                and item.open_time == release["time"]
                and item.open_sequence > release["sequence"]
            ),
            None,
        )
        baseline_active = next(
            (
                item
                for item in baseline_lifecycles
                if item.component == incumbent
                and item.open_time <= release["time"] < item.close_time
            ),
            None,
        )
        state = state_at(states, release["time"])
        matched_identity = (
            forced is not None
            and baseline_active is not None
            and forced.open_time == baseline_active.open_time
            and abs(forced.open_volume - baseline_active.open_volume) < 1.0e-9
            and abs(forced.open_price - baseline_active.open_price) < 1.0e-6
        )
        bounded = None
        if forced is not None and admitted is not None and matched_identity:
            bounded = forced.stressed_net + admitted.stressed_net - baseline_active.stressed_net
        output.append(
            {
                "run": run_name,
                "server_time": release["server_time"],
                "candidate": candidate,
                "incumbent": incumbent,
                "multiplier": state["multiplier"],
                "phase": state["phase"],
                "days_since_upstep": state["days_since_upstep"],
                "floor_buffer": rounded(state["floor_buffer"]),
                "distance_to_next": rounded(state["distance_to_next"]),
                "velocity_5": None if state["velocity_5"] is None else rounded(state["velocity_5"]),
                "recent_20_close_drawdown": rounded(state["recent_20_close_drawdown"]),
                "matched_incumbent_identity": matched_identity,
                "forced_incumbent_stressed": None if forced is None else rounded(forced.stressed_net),
                "candidate_stressed": None if admitted is None else rounded(admitted.stressed_net),
                "baseline_keep_stressed": (
                    None if baseline_active is None else rounded(baseline_active.stressed_net)
                ),
                "bounded_exchange_delta": None if bounded is None else rounded(bounded),
            }
        )
    return output


def gate_map(references: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matched = [item for item in references if item["bounded_exchange_delta"] is not None]
    gates: list[tuple[str, Any]] = [
        ("all_matched", lambda item: True),
        (
            "quarantine_first_5_step_days",
            lambda item: not (
                item["multiplier"] > 1
                and item["days_since_upstep"] is not None
                and item["days_since_upstep"] <= 5
            ),
        ),
        (
            "quarantine_first_10_step_days",
            lambda item: not (
                item["multiplier"] > 1
                and item["days_since_upstep"] is not None
                and item["days_since_upstep"] <= 10
            ),
        ),
        (
            "upper_step_requires_10_buffer",
            lambda item: item["multiplier"] == 1 or item["floor_buffer"] >= 10.0,
        ),
        (
            "upper_step_requires_recent_drawdown_cover",
            lambda item: (
                item["multiplier"] == 1
                or item["floor_buffer"] >= item["recent_20_close_drawdown"]
            ),
        ),
    ]
    output: list[dict[str, Any]] = []
    for name, predicate in gates:
        admitted = [item for item in matched if predicate(item)]
        blocked = [item for item in matched if not predicate(item)]
        output.append(
            {
                "gate": name,
                "matched_observations": len(matched),
                "admitted": len(admitted),
                "blocked": len(blocked),
                "admitted_bounded_delta": rounded(
                    sum(item["bounded_exchange_delta"] for item in admitted)
                ),
                "blocked_bounded_delta": rounded(
                    sum(item["bounded_exchange_delta"] for item in blocked)
                ),
            }
        )
    return output


def json_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        key: (
            value.isoformat(sep=" ") if isinstance(value, datetime)
            else rounded(value) if isinstance(value, float)
            else value
        )
        for key, value in state.items()
        if key != "time"
    }


def main() -> None:
    run_data: dict[str, dict[str, Any]] = {}
    for name, paths in RUN_PATHS.items():
        rows = load_events(paths)
        lifecycles = build_lifecycles(rows)
        states = daily_states(rows, lifecycles)
        run_data[name] = {
            "rows": rows,
            "lifecycles": lifecycles,
            "states": states,
            "map": path_map(states, lifecycles),
        }

    baseline = run_data["baseline_receiver_time_field"]
    exchange_references: list[dict[str, Any]] = []
    for name in ("market_only_receiver_wounded", "market_only_loser_residual"):
        data = run_data[name]
        exchange_references.extend(
            exchange_phase_references(
                name,
                data["rows"],
                data["states"],
                data["lifecycles"],
                baseline["lifecycles"],
            )
        )

    payload = {
        "unit": "capital-step-phase-007",
        "question": "Can distance to a discrete lot step become a causal portfolio phase state without reducing entry count?",
        "architecture": {
            "measurement": "reuse_current_next_lab_real_tick_event_paths",
            "proxy": "daily_phase_reconstruction_plus_hypothesis_family_policy_probe",
            "runtime": "deferred_until_a_small_rule_survives_temporal_slices",
        },
        "constants": {
            "reference_capital_usd": REFERENCE_CAPITAL,
            "addition_step_usd": ADDITION_STEP,
            "base_market_volume": BASE_VOLUME,
        },
        "paths": {name: data["map"] for name, data in run_data.items()},
        "asynchronous_2x_windows": {
            name: asynchronous_window(
                baseline["states"],
                baseline["lifecycles"],
                run_data[name]["states"],
                run_data[name]["lifecycles"],
            )
            for name in ("market_only_receiver_wounded", "market_only_loser_residual")
        },
        "exchange_phase_references": exchange_references,
        "exchange_phase_gates": gate_map(exchange_references),
        "policy_search": policy_search(run_data, policy_specs()),
        "observations": {
            "causal_state": "At each sizing day, floor buffer, next-step distance, trailing balance velocity, and recent closed-trade drawdown are all knowable before new entries.",
            "discontinuity": "The lot rule is a state transition, not a smooth scale: volume changes alter stop distance and can alter exit identity, so the proxy deliberately does not claim counterfactual parity.",
            "entry_constraint": "Every policy probe changes only the proposed daily market-volume multiplier; the observed opportunity count is held constant in the proxy.",
        },
        "sources": {
            "prior_runtime": source(ROOT / "lab" / "frontier" / "slot-shadow-price" / "runtime.json"),
            "event_paths": {
                name: [source(ARTIFACTS / path) for path in paths]
                for name, paths in RUN_PATHS.items()
            },
        },
    }
    output = FRONTIER / "proxy.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
