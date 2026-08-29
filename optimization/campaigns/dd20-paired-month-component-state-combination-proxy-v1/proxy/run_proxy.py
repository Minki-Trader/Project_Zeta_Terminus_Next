from __future__ import annotations

import csv
import hashlib
import json
import math
import time
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
CAMPAIGN_ROOT = SCRIPT_PATH.parents[1]
REPOSITORY_ROOT = SCRIPT_PATH.parents[4]
CONFIG_PATH = CAMPAIGN_ROOT / "config" / "proxy-contract.json"
TIME_FORMAT = "%Y.%m.%d %H:%M:%S"
EPSILON = 1.0e-9


@dataclass(frozen=True)
class LifecycleEvent:
    server_time: datetime
    event: str
    component_index: int
    position_identifier: str
    source_volume_lots: float
    planned_risk_usd: float
    actual_net_usd: float
    stressed_net_usd: float


@dataclass(frozen=True)
class CandidatePosition:
    component_index: int
    source_steps: int
    target_steps: int
    admitted_risk_usd: float
    admitted: bool


class PeriodTracker:
    def __init__(self, identifier: str, start: datetime, end: datetime) -> None:
        self.identifier = identifier
        self.start = start
        self.end = end
        self.initialized = False
        self.start_actual = 0.0
        self.start_stressed = 0.0
        self.end_actual = 0.0
        self.end_stressed = 0.0
        self.actual_net = 0.0
        self.stressed_net = 0.0
        self.actual_peak = 0.0
        self.stressed_peak = 0.0
        self.actual_dd = 0.0
        self.stressed_dd = 0.0
        self.minimum_actual = math.inf
        self.minimum_stressed = math.inf
        self.source_closes = 0
        self.admitted_closes = 0

    def contains(self, moment: datetime) -> bool:
        return self.start <= moment < self.end

    def observe(
        self,
        before_actual: float,
        before_stressed: float,
        after_actual: float,
        after_stressed: float,
        actual_increment: float,
        stressed_increment: float,
        admitted: bool,
    ) -> None:
        if not self.initialized:
            self.initialized = True
            self.start_actual = before_actual
            self.start_stressed = before_stressed
            self.actual_peak = before_actual
            self.stressed_peak = before_stressed
            self.minimum_actual = before_actual
            self.minimum_stressed = before_stressed
        self.actual_net += actual_increment
        self.stressed_net += stressed_increment
        self.actual_peak = max(self.actual_peak, after_actual)
        self.stressed_peak = max(self.stressed_peak, after_stressed)
        self.actual_dd = max(
            self.actual_dd,
            (self.actual_peak - after_actual) / self.actual_peak
            if self.actual_peak > 0.0
            else math.inf,
        )
        self.stressed_dd = max(
            self.stressed_dd,
            (self.stressed_peak - after_stressed) / self.stressed_peak
            if self.stressed_peak > 0.0
            else math.inf,
        )
        self.minimum_actual = min(self.minimum_actual, after_actual)
        self.minimum_stressed = min(self.minimum_stressed, after_stressed)
        self.end_actual = after_actual
        self.end_stressed = after_stressed
        self.source_closes += 1
        self.admitted_closes += int(admitted)

    def record(self) -> dict[str, Any]:
        if not self.initialized:
            raise RuntimeError(f"period has no source close: {self.identifier}")
        return {
            "id": self.identifier,
            "start": self.start.strftime(TIME_FORMAT),
            "end": self.end.strftime(TIME_FORMAT),
            "source_closes": self.source_closes,
            "admitted_closes": self.admitted_closes,
            "starting_actual_balance_usd": self.start_actual,
            "starting_stressed_balance_usd": self.start_stressed,
            "ending_actual_balance_usd": self.end_actual,
            "ending_stressed_balance_usd": self.end_stressed,
            "actual_net_usd": self.actual_net,
            "stressed_net_usd": self.stressed_net,
            "actual_closed_balance_drawdown_pct": self.actual_dd * 100.0,
            "stressed_closed_balance_drawdown_pct": self.stressed_dd * 100.0,
            "raw_worse_closed_balance_drawdown_pct": max(self.actual_dd, self.stressed_dd) * 100.0,
            "minimum_actual_balance_usd": self.minimum_actual,
            "minimum_stressed_balance_usd": self.minimum_stressed,
        }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def receipt(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(REPOSITORY_ROOT)).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def round_steps(value: float) -> int:
    return math.floor(value + 0.5 + 1.0e-12)


def periods_from(configured: list[dict[str, Any]]) -> list[PeriodTracker]:
    return [
        PeriodTracker(
            str(item["id"]),
            datetime.strptime(str(item["start"]), TIME_FORMAT),
            datetime.strptime(str(item["end"]), TIME_FORMAT),
        )
        for item in configured
    ]


def verify_inputs(config: dict[str, Any]) -> tuple[Path, dict[str, dict[str, Any]]]:
    input_root = REPOSITORY_ROOT / str(config["input"]["root"])
    declarations = {str(item["name"]): item for item in config["input"]["files"]}
    if len(declarations) != len(config["input"]["files"]):
        raise RuntimeError("duplicate input declaration")
    total = 0
    for name, declared in declarations.items():
        path = input_root / name
        if not path.is_file():
            raise RuntimeError(f"missing campaign input: {name}")
        if path.stat().st_size != int(declared["bytes"]):
            raise RuntimeError(f"input byte mismatch: {name}")
        if sha256(path) != str(declared["sha256"]):
            raise RuntimeError(f"input hash mismatch: {name}")
        total += path.stat().st_size
    if total != int(config["input"]["bytes_total"]):
        raise RuntimeError("input byte total mismatch")
    return input_root, declarations


def load_events(
    path: Path,
    expected_births: int,
    expected_closes: int,
    expected_actual: float,
    expected_stressed: float,
    components: list[str],
) -> tuple[list[LifecycleEvent], dict[str, int]]:
    indices = {component: index for index, component in enumerate(components)}
    events: list[LifecycleEvent] = []
    last_time: datetime | None = None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for source in csv.DictReader(handle):
            if source["event"] not in {"BIRTH", "CLOSE"}:
                continue
            if source["event"] == "CLOSE" and source.get("partial_observation", "0") != "0":
                continue
            moment = datetime.strptime(source["server_time"], TIME_FORMAT)
            if last_time is not None and moment < last_time:
                raise RuntimeError("lifecycle source is not chronological")
            last_time = moment
            component = source["component_id"]
            if component not in indices:
                raise RuntimeError(f"unknown component in lifecycle source: {component}")
            events.append(
                LifecycleEvent(
                    server_time=moment,
                    event=source["event"],
                    component_index=indices[component],
                    position_identifier=source["position_identifier"],
                    source_volume_lots=float(source["volume"]),
                    planned_risk_usd=float(source["planned_risk_usd"]),
                    actual_net_usd=float(source["actual_net_usd"]),
                    stressed_net_usd=float(source["stressed_net_usd"]),
                )
            )

    births = [event for event in events if event.event == "BIRTH"]
    closes = [event for event in events if event.event == "CLOSE"]
    if len(births) != expected_births or len(closes) != expected_closes:
        raise RuntimeError("lifecycle source count mismatch")
    birth_ids = [event.position_identifier for event in births]
    close_ids = [event.position_identifier for event in closes]
    if len(set(birth_ids)) != len(birth_ids) or set(birth_ids) != set(close_ids):
        raise RuntimeError("lifecycle birth/close identity mismatch")
    if any(event.source_volume_lots <= 0.0 or event.planned_risk_usd <= 0.0 for event in births):
        raise RuntimeError("source birth volume/risk must be positive")
    actual = sum(event.actual_net_usd for event in closes)
    stressed = sum(event.stressed_net_usd for event in closes)
    if abs(actual - expected_actual) > 1.0e-6 or abs(stressed - expected_stressed) > 1.0e-6:
        raise RuntimeError("lifecycle source economic total mismatch")
    counts = Counter(components[event.component_index] for event in closes)
    return events, dict(counts)


def add_close_to_trackers(
    trackers: list[PeriodTracker],
    event: LifecycleEvent,
    before_actual: float,
    before_stressed: float,
    after_actual: float,
    after_stressed: float,
    actual_increment: float,
    stressed_increment: float,
    admitted: bool,
) -> None:
    for tracker in trackers:
        if tracker.contains(event.server_time):
            tracker.observe(
                before_actual,
                before_stressed,
                after_actual,
                after_stressed,
                actual_increment,
                stressed_increment,
                admitted,
            )


def simulate_control(
    events: list[LifecycleEvent],
    periods: list[dict[str, Any]],
    components: list[str],
    reference: float,
) -> dict[str, Any]:
    trackers = periods_from(periods)
    actual_balance = reference
    stressed_balance = reference
    actual_peak = reference
    stressed_peak = reference
    actual_dd = 0.0
    stressed_dd = 0.0
    minimum_actual = reference
    minimum_stressed = reference
    component_actual = [0.0] * len(components)
    component_stressed = [0.0] * len(components)
    component_closes = [0] * len(components)

    for event in events:
        if event.event != "CLOSE":
            continue
        before_actual = actual_balance
        before_stressed = stressed_balance
        actual_balance += event.actual_net_usd
        stressed_balance += event.stressed_net_usd
        actual_peak = max(actual_peak, actual_balance)
        stressed_peak = max(stressed_peak, stressed_balance)
        actual_dd = max(actual_dd, (actual_peak - actual_balance) / actual_peak)
        stressed_dd = max(stressed_dd, (stressed_peak - stressed_balance) / stressed_peak)
        minimum_actual = min(minimum_actual, actual_balance)
        minimum_stressed = min(minimum_stressed, stressed_balance)
        component_actual[event.component_index] += event.actual_net_usd
        component_stressed[event.component_index] += event.stressed_net_usd
        component_closes[event.component_index] += 1
        add_close_to_trackers(
            trackers,
            event,
            before_actual,
            before_stressed,
            actual_balance,
            stressed_balance,
            event.actual_net_usd,
            event.stressed_net_usd,
            True,
        )

    return {
        "actual_net_usd": actual_balance - reference,
        "stressed_net_usd": stressed_balance - reference,
        "ending_actual_balance_usd": actual_balance,
        "ending_stressed_balance_usd": stressed_balance,
        "minimum_actual_balance_usd": minimum_actual,
        "minimum_stressed_balance_usd": minimum_stressed,
        "actual_closed_balance_drawdown_pct": actual_dd * 100.0,
        "stressed_closed_balance_drawdown_pct": stressed_dd * 100.0,
        "raw_worse_closed_balance_drawdown_pct": max(actual_dd, stressed_dd) * 100.0,
        "periods": [tracker.record() for tracker in trackers],
        "components": [
            {
                "component": component,
                "closes": component_closes[index],
                "actual_net_usd": component_actual[index],
                "stressed_net_usd": component_stressed[index],
            }
            for index, component in enumerate(components)
        ],
    }


def simulate_candidate(
    events: list[LifecycleEvent],
    periods: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    components = [str(value) for value in config["components"]]
    anchor = config["paired_month_anchor"]
    state = config["component_state"]
    weights = [float(value) for value in anchor["weights"]]
    reference = float(anchor["reference_capital_usd"])
    addition_step = float(anchor["addition_step_usd"])
    volume_step = float(anchor["volume_step_lots"])
    aggregate_fraction = float(anchor["aggregate_risk_fraction"])
    aggregate_tolerance = float(anchor["aggregate_tolerance_usd"])
    lookback = int(state["lookback_admitted_closes"])
    band = float(state["symmetric_mean_band_r"])
    loss_overlay = float(state["loss_overlay"])
    neutral_overlay = float(state["neutral_overlay"])
    gain_overlay = float(state["gain_overlay"])

    trackers = periods_from(periods)
    histories = [deque(maxlen=lookback) for _ in components]
    actual_balance = reference
    stressed_balance = reference
    actual_peak = reference
    stressed_peak = reference
    actual_dd = 0.0
    stressed_dd = 0.0
    minimum_actual = reference
    minimum_stressed = reference
    open_risk = 0.0
    open_positions: dict[str, CandidatePosition] = {}
    current_day = None
    day_multiplier = 1
    path_diverged = False
    admitted = 0
    risk_skips = 0
    disabled_skips = 0
    non_neutral_executable = 0
    non_neutral_by_component = [0] * len(components)
    overlay_evaluations = {"warmup": 0, "loss": 0, "neutral": 0, "gain": 0}
    component_actual = [0.0] * len(components)
    component_stressed = [0.0] * len(components)
    component_closes = [0] * len(components)

    for event in events:
        event_day = event.server_time.date()
        if event_day != current_day:
            day_multiplier = max(
                1,
                1 + math.floor(max(0.0, stressed_balance - reference) / addition_step + 1.0e-9),
            )
            current_day = event_day

        if event.event == "BIRTH":
            if event.position_identifier in open_positions:
                raise RuntimeError("duplicate source position birth")
            component = event.component_index
            source_steps = round_steps(event.source_volume_lots / volume_step)
            if source_steps <= 0:
                raise RuntimeError("invalid source volume steps")

            overlay = neutral_overlay
            if len(histories[component]) < lookback:
                overlay_evaluations["warmup"] += 1
            else:
                mean_r = sum(histories[component]) / lookback
                if mean_r < -band:
                    overlay = loss_overlay
                    overlay_evaluations["loss"] += 1
                elif mean_r > band:
                    overlay = gain_overlay
                    overlay_evaluations["gain"] += 1
                else:
                    overlay_evaluations["neutral"] += 1

            neutral_steps = round_steps(day_multiplier * weights[component])
            target_steps = round_steps(day_multiplier * weights[component] * overlay)
            if not path_diverged and neutral_steps != source_steps:
                raise RuntimeError(
                    f"pre-divergence source volume mismatch for {components[component]} at {event.server_time.strftime(TIME_FORMAT)}"
                )

            candidate_risk = event.planned_risk_usd * target_steps / source_steps if target_steps > 0 else 0.0
            conservative_capital = min(actual_balance, stressed_balance)
            aggregate_cap = conservative_capital * aggregate_fraction
            is_admitted = (
                target_steps > 0
                and conservative_capital > 0.0
                and open_risk + candidate_risk <= aggregate_cap + aggregate_tolerance + EPSILON
            )
            if target_steps <= 0:
                disabled_skips += 1
            elif not is_admitted:
                risk_skips += 1
            else:
                admitted += 1
                open_risk += candidate_risk
                if abs(overlay - neutral_overlay) > EPSILON and target_steps != neutral_steps:
                    non_neutral_executable += 1
                    non_neutral_by_component[component] += 1

            if target_steps != source_steps or not is_admitted:
                path_diverged = True
            open_positions[event.position_identifier] = CandidatePosition(
                component_index=component,
                source_steps=source_steps,
                target_steps=target_steps if is_admitted else 0,
                admitted_risk_usd=candidate_risk if is_admitted else 0.0,
                admitted=is_admitted,
            )
            continue

        if event.position_identifier not in open_positions:
            raise RuntimeError("source close has no candidate birth")
        position = open_positions.pop(event.position_identifier)
        if position.component_index != event.component_index:
            raise RuntimeError("source birth/close component mismatch")
        scale = position.target_steps / position.source_steps if position.admitted else 0.0
        actual_increment = event.actual_net_usd * scale
        stressed_increment = event.stressed_net_usd * scale
        before_actual = actual_balance
        before_stressed = stressed_balance
        actual_balance += actual_increment
        stressed_balance += stressed_increment
        if position.admitted:
            open_risk = max(0.0, open_risk - position.admitted_risk_usd)
            histories[position.component_index].append(stressed_increment / position.admitted_risk_usd)
            component_closes[position.component_index] += 1

        component_actual[position.component_index] += actual_increment
        component_stressed[position.component_index] += stressed_increment
        actual_peak = max(actual_peak, actual_balance)
        stressed_peak = max(stressed_peak, stressed_balance)
        actual_dd = max(actual_dd, (actual_peak - actual_balance) / actual_peak)
        stressed_dd = max(stressed_dd, (stressed_peak - stressed_balance) / stressed_peak)
        minimum_actual = min(minimum_actual, actual_balance)
        minimum_stressed = min(minimum_stressed, stressed_balance)
        add_close_to_trackers(
            trackers,
            event,
            before_actual,
            before_stressed,
            actual_balance,
            stressed_balance,
            actual_increment,
            stressed_increment,
            position.admitted,
        )

    if open_positions or abs(open_risk) > 1.0e-6:
        raise RuntimeError("candidate open position/risk did not reconcile")

    return {
        "actual_net_usd": actual_balance - reference,
        "stressed_net_usd": stressed_balance - reference,
        "ending_actual_balance_usd": actual_balance,
        "ending_stressed_balance_usd": stressed_balance,
        "minimum_actual_balance_usd": minimum_actual,
        "minimum_stressed_balance_usd": minimum_stressed,
        "actual_closed_balance_drawdown_pct": actual_dd * 100.0,
        "stressed_closed_balance_drawdown_pct": stressed_dd * 100.0,
        "raw_worse_closed_balance_drawdown_pct": max(actual_dd, stressed_dd) * 100.0,
        "admitted_lifecycles": admitted,
        "aggregate_risk_skips": risk_skips,
        "disabled_overlay_skips": disabled_skips,
        "path_diverged": path_diverged,
        "non_neutral_executable_birth_decisions": non_neutral_executable,
        "components_with_non_neutral_executable_decisions": sum(count > 0 for count in non_neutral_by_component),
        "overlay_evaluations": overlay_evaluations,
        "periods": [tracker.record() for tracker in trackers],
        "components": [
            {
                "component": component,
                "weight": weights[index],
                "admitted_closes": component_closes[index],
                "actual_net_usd": component_actual[index],
                "stressed_net_usd": component_stressed[index],
                "non_neutral_executable_birth_decisions": non_neutral_by_component[index],
                "final_state_count": len(histories[index]),
                "final_state_mean_stressed_r": sum(histories[index]) / len(histories[index]) if histories[index] else None,
            }
            for index, component in enumerate(components)
        ],
    }


def live_boundary(input_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    boundary = config["live_boundary"]
    candidate_path = input_root / str(boundary["candidate_file"])
    lifecycle_path = input_root / str(boundary["lifecycle_file"])
    with candidate_path.open("r", encoding="utf-8-sig", newline="") as handle:
        candidates = list(csv.DictReader(handle))
    with lifecycle_path.open("r", encoding="utf-8-sig", newline="") as handle:
        lifecycles = list(csv.DictReader(handle))
    births = [row for row in lifecycles if row["event"] == "BIRTH"]
    closes = [row for row in lifecycles if row["event"] == "CLOSE" and row["partial_observation"] == "0"]
    peers = [row for row in lifecycles if row["event"] == "FIRST_PEER_NATURAL_EXIT"]
    if (
        len(candidates) != int(boundary["candidate_rows"])
        or len(lifecycles) != int(boundary["lifecycle_rows"])
        or len(births) != int(boundary["births"])
        or len(closes) != int(boundary["closes"])
        or len(peers) != int(boundary["first_peer_rows"])
    ):
        raise RuntimeError("Live snapshot row boundary mismatch")
    actual = sum(float(row["actual_net_usd"]) for row in closes)
    stressed = sum(float(row["stressed_net_usd"]) for row in closes)
    if abs(actual - float(boundary["actual_net_usd"])) > 1.0e-9 or abs(stressed - float(boundary["stressed_net_usd"])) > 1.0e-9:
        raise RuntimeError("Live snapshot economic boundary mismatch")
    component_counts = Counter(row["component_id"] for row in closes)
    lookback = int(config["component_state"]["lookback_admitted_closes"])
    max_closes = max(component_counts.values(), default=0)
    dropped = sum(int(row["research_dropped_records"]) for row in candidates + lifecycles)
    if dropped != 0:
        raise RuntimeError("Live snapshot has research drops")
    return {
        "candidate_rows": len(candidates),
        "lifecycle_rows": len(lifecycles),
        "births": len(births),
        "closes": len(closes),
        "first_peer_rows": len(peers),
        "actual_net_usd": actual,
        "stressed_net_usd": stressed,
        "component_close_counts": dict(component_counts),
        "maximum_component_closes": max_closes,
        "component_state_lookback": lookback,
        "all_current_live_components_in_warmup": max_closes < lookback,
        "research_dropped_records": dropped,
        "used_for_parameter_selection": False,
    }


def period_gate(periods: list[dict[str, Any]]) -> bool:
    return all(
        period["actual_net_usd"] > 0.0
        and period["stressed_net_usd"] > 0.0
        and period["minimum_actual_balance_usd"] > 0.0
        and period["minimum_stressed_balance_usd"] > 0.0
        for period in periods
    )


def main() -> None:
    started = time.perf_counter()
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    input_root, declarations = verify_inputs(config)
    components = [str(value) for value in config["components"]]
    anchor = config["paired_month_anchor"]
    reference = float(anchor["reference_capital_usd"])

    selection_expected = anchor["selection"]
    selection_events, selection_counts = load_events(
        input_root / str(selection_expected["lifecycle_file"]),
        int(selection_expected["births"]),
        int(selection_expected["closes"]),
        float(selection_expected["actual_net_usd"]),
        float(selection_expected["stressed_net_usd"]),
        components,
    )
    forward_expected = anchor["forward"]
    forward_events, forward_counts = load_events(
        input_root / str(forward_expected["lifecycle_file"]),
        int(forward_expected["births"]),
        int(forward_expected["closes"]),
        float(forward_expected["actual_net_usd"]),
        float(forward_expected["stressed_net_usd"]),
        components,
    )

    selection_control = simulate_control(selection_events, config["selection_periods"], components, reference)
    selection_candidate = simulate_candidate(selection_events, config["selection_periods"], config)
    forward_control = simulate_control(forward_events, config["forward_periods"], components, reference)
    forward_candidate = simulate_candidate(forward_events, config["forward_periods"], config)
    current_live = live_boundary(input_root, config)

    for metrics, expected, phase in (
        (selection_control, selection_expected, "selection"),
        (forward_control, forward_expected, "forward"),
    ):
        if (
            abs(metrics["actual_net_usd"] - float(expected["actual_net_usd"])) > 1.0e-6
            or abs(metrics["stressed_net_usd"] - float(expected["stressed_net_usd"])) > 1.0e-6
        ):
            raise RuntimeError(f"{phase} control reconstruction mismatch")

    gates = config["selection_gates"]
    conservative_actual = (
        selection_candidate["actual_net_usd"]
        - float(gates["prior_incremental_proxy_to_native_error_actual_usd"])
        - float(gates["new_combination_uncertainty_reserve_usd"])
    )
    conservative_stressed = (
        selection_candidate["stressed_net_usd"]
        - float(gates["prior_incremental_proxy_to_native_error_stressed_usd"])
        - float(gates["new_combination_uncertainty_reserve_usd"])
    )
    native_anchor_dd = float(selection_expected["native_relative_equity_drawdown_pct"])
    raw_calibration = max(0.0, native_anchor_dd - selection_control["raw_worse_closed_balance_drawdown_pct"])
    budgeted_dd = (
        max(
            native_anchor_dd,
            selection_candidate["raw_worse_closed_balance_drawdown_pct"] + raw_calibration,
        )
        + float(gates["prior_native_component_state_dd_increment_percentage_points"])
        + float(gates["new_combination_dd_reserve_percentage_points"])
    )
    nominal_line = float(gates["nominal_dd_line_pct"])
    screening_ceiling = nominal_line * (1.0 + float(gates["maximum_proxy_screening_proportional_overshoot"]))

    selection_gate_values = {
        "non_neutral_density": selection_candidate["non_neutral_executable_birth_decisions"] >= int(gates["minimum_non_neutral_executable_decisions"]),
        "component_breadth": selection_candidate["components_with_non_neutral_executable_decisions"] >= int(gates["minimum_components_with_non_neutral_executable_decisions"]),
        "full_capital_positive": selection_candidate["minimum_actual_balance_usd"] > 0.0 and selection_candidate["minimum_stressed_balance_usd"] > 0.0,
        "all_four_epochs_positive": period_gate(selection_candidate["periods"]),
        "conservative_actual_strictly_above_anchor": conservative_actual > float(selection_expected["actual_net_usd"]),
        "conservative_stressed_strictly_above_anchor": conservative_stressed > float(selection_expected["stressed_net_usd"]),
        "proxy_screening_dd_within_6pct_proportional_ceiling": budgeted_dd <= screening_ceiling + EPSILON,
    }
    selection_eligible = all(selection_gate_values.values())

    forward_exact = (
        abs(forward_candidate["actual_net_usd"] - forward_control["actual_net_usd"]) <= 1.0e-9
        and abs(forward_candidate["stressed_net_usd"] - forward_control["stressed_net_usd"]) <= 1.0e-9
        and forward_candidate["non_neutral_executable_birth_decisions"] == 0
        and forward_candidate["aggregate_risk_skips"] == 0
        and forward_candidate["disabled_overlay_skips"] == 0
        and not forward_candidate["path_diverged"]
        and forward_candidate["minimum_actual_balance_usd"] > 0.0
        and forward_candidate["minimum_stressed_balance_usd"] > 0.0
        and all(
            candidate_period["id"] == control_period["id"]
            and abs(candidate_period["actual_net_usd"] - control_period["actual_net_usd"]) <= 1.0e-9
            and abs(candidate_period["stressed_net_usd"] - control_period["stressed_net_usd"]) <= 1.0e-9
            for candidate_period, control_period in zip(
                forward_candidate["periods"], forward_control["periods"]
            )
        )
    )
    live_exact_neutral = current_live["all_current_live_components_in_warmup"]
    shortlist = 1 if selection_eligible and forward_exact and live_exact_neutral else 0
    classification = (
        "VALID_PROXY_COMPLETE_ONE_EXACT_COMBINATION_MT5_SHORTLIST"
        if shortlist == 1
        else "VALID_PROXY_COMPLETE_NO_MT5_SHORTLIST_COMPONENT_STATE_COMBINATION_NONCONFIRMATION"
    )

    output_path = REPOSITORY_ROOT / str(config["output"]["path"])
    result = {
        "schema": "zeta-dd20-paired-month-component-state-combination-proxy-result-v1",
        "recorded_date_local": "2026-08-29",
        "status": classification,
        "campaign": str(config["campaign"]),
        "formal_process": {
            "invocations": 1,
            "elapsed_seconds": time.perf_counter() - started,
            "candidate_count": 1,
            "parameters_tuned": 0,
            "mt5_shortlist_size": shortlist,
        },
        "frozen_files": {
            "config": receipt(CONFIG_PATH),
            "analysis_script": receipt(SCRIPT_PATH),
            "inputs": [
                {
                    "name": name,
                    "bytes": int(declared["bytes"]),
                    "sha256": str(declared["sha256"]),
                }
                for name, declared in sorted(declarations.items())
            ],
        },
        "integrity": {
            "valid_for_economic_judgment": True,
            "selection_source_component_closes": selection_counts,
            "forward_source_component_closes": forward_counts,
            "selection_control_reproduced": True,
            "forward_control_reproduced": True,
            "input_hashes_and_bytes_match": True,
        },
        "fixed_candidate": {
            "weights": anchor["weights"],
            "component_state": config["component_state"],
            "position_risk_fraction": anchor["position_risk_fraction"],
            "aggregate_risk_fraction": anchor["aggregate_risk_fraction"],
            "addition_step_usd": anchor["addition_step_usd"],
        },
        "selection": {
            "control": selection_control,
            "candidate": selection_candidate,
            "candidate_delta_actual_usd": selection_candidate["actual_net_usd"] - selection_control["actual_net_usd"],
            "candidate_delta_stressed_usd": selection_candidate["stressed_net_usd"] - selection_control["stressed_net_usd"],
            "conservative_candidate_actual_net_usd": conservative_actual,
            "conservative_candidate_stressed_net_usd": conservative_stressed,
            "conservative_delta_actual_usd": conservative_actual - float(selection_expected["actual_net_usd"]),
            "conservative_delta_stressed_usd": conservative_stressed - float(selection_expected["stressed_net_usd"]),
            "native_anchor_dd_pct": native_anchor_dd,
            "control_raw_to_native_calibration_points": raw_calibration,
            "budgeted_candidate_dd_pct": budgeted_dd,
            "nominal_dd_line_pct": nominal_line,
            "nominal_dd_gate": budgeted_dd <= nominal_line + EPSILON,
            "proxy_screening_ceiling_pct": screening_ceiling,
            "proxy_screening_proportional_overshoot": max(0.0, budgeted_dd / nominal_line - 1.0),
            "gates": selection_gate_values,
            "eligible": selection_eligible,
        },
        "forward": {
            "control": forward_control,
            "candidate": forward_candidate,
            "exact_neutral_gate": forward_exact,
            "native_relative_equity_drawdown_pct": forward_expected["native_relative_equity_drawdown_pct"],
        },
        "current_live_boundary": current_live,
        "current_live_neutral_gate": live_exact_neutral,
        "mt5_shortlist": (
            [
                {
                    "id": "EXACT_PAIRED_MONTH_PLUS_COMPONENT_STATE_40_BAND_0.10_LOSS_0_GAIN_1.125",
                    "maximum_size": 1,
                    "requires_separate_non_master_campaign": True,
                }
            ]
            if shortlist == 1
            else []
        ),
        "verdict": {
            "classification": classification,
            "complete_valid_numbers": True,
            "engineering_or_environment_failure": False,
            "adjacent_rescue_allowed": False,
            "automatic_live_or_lab_authority": False,
        },
        "boundary": {
            "mql_or_settings_changes": 0,
            "compile_or_tester_invocations": 0,
            "tests_or_validators": 0,
            "live_files_modified": False,
            "lab_paths_used": False,
            "broker_positions_orders_deals_or_account_queried": False,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"status": classification, "mt5_shortlist_size": shortlist, "output": str(output_path)}))


if __name__ == "__main__":
    main()
