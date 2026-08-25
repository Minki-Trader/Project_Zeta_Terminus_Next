#!/usr/bin/env python3
"""Decompose scale-dependent admission and select one bounded risk-unit form."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
FRONTIER = ROOT / "lab" / "frontier" / "capital-scale-admission-topology"
TRANSITION_ARTIFACTS = (
    ROOT / "lab" / "artifacts" / "backtests" / "transition-reserve-geometry"
)
ELASTICITY_ARTIFACTS = (
    ROOT / "lab" / "artifacts" / "backtests" / "capital-step-elasticity"
)
MODELED_RISK_FRACTION = 0.75
POSITION_RISK_FRACTION = 0.04
AGGREGATE_RISK_FRACTION = 0.12
TOLERANCE = 0.01
PASSIVE_ID = "ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8"
COMPONENTS = {
    "ZT-M30-US30-RANGE-COMP-61f61deaba": "RC16",
    "ZT-M30-US30-RANGE-COMP-64efb16616": "RC4",
    "ZT-H1-US100-CROSS-IN-14b72317b7": "CROSS",
    "ZT-M30-US30-INTRADAY-R-2eb111fc46": "PRESSURE",
    "ZT-H1-US30-RETURN-I-c870a788ec": "RETURN",
    PASSIVE_ID: "PASSIVE",
}
RUNS = {
    "geometry_100": {
        "deposit": 100.0,
        "directory": ELASTICITY_ARTIFACTS,
        "events": ["hard20-loser-events-a.csv", "hard20-loser-events-b.csv"],
    },
    "geometry_200": {
        "deposit": 200.0,
        "directory": TRANSITION_ARTIFACTS,
        "events": ["geometry-200-events-a.csv", "geometry-200-events-b.csv"],
    },
    "geometry_300": {
        "deposit": 300.0,
        "directory": TRANSITION_ARTIFACTS,
        "events": ["geometry-300-events-a.csv", "geometry-300-events-b.csv"],
    },
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


def detail_number(detail: str, key: str) -> float | None:
    match = re.search(rf"(?:^|\s){re.escape(key)}=(-?\d+(?:\.\d+)?)", detail)
    return float(match.group(1)) if match else None


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y.%m.%d %H:%M:%S")


def load_events(directory: Path, names: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in names:
        with (directory / name).open("r", encoding="utf-8", newline="") as handle:
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
class Exposure:
    component_id: str
    opened: str
    entry: float
    stop: float
    volume: float
    reserved_budget: float
    actual_stop_risk: float
    state: str

    def record(self) -> dict[str, Any]:
        return {
            "component": COMPONENTS.get(self.component_id, self.component_id),
            "state": self.state,
            "opened": self.opened,
            "entry": rounded(self.entry),
            "stop": rounded(self.stop),
            "volume": rounded(self.volume),
            "reserved_budget": rounded(self.reserved_budget),
            "actual_stop_risk": rounded(self.actual_stop_risk),
        }


def stop_bound_risk(entry: float, stop: float, volume: float) -> float:
    # The frozen startup contract pins unit contract size and USD profit currency.
    return abs(entry - stop) * volume / MODELED_RISK_FRACTION


def market_exposure(row: dict[str, Any]) -> Exposure:
    detail = row["detail"]
    entry = detail_number(detail, "position_open") or row["value_a_number"]
    stop = detail_number(detail, "stop") or 0.0
    volume = row["value_b_number"]
    reserved = detail_number(detail, "planned_risk") or 0.0
    return Exposure(
        component_id=row["component_id"],
        opened=row["server_time"],
        entry=entry,
        stop=stop,
        volume=volume,
        reserved_budget=reserved,
        actual_stop_risk=stop_bound_risk(entry, stop, volume),
        state="POSITION",
    )


def passive_pending(row: dict[str, Any], base_volume: float) -> Exposure:
    detail = row["detail"]
    entry = row["value_a_number"]
    stop = detail_number(detail, "stop") or 0.0
    reserved = detail_number(detail, "planned_risk") or 0.0
    return Exposure(
        component_id=row["component_id"],
        opened=row["server_time"],
        entry=entry,
        stop=stop,
        volume=base_volume,
        reserved_budget=reserved,
        actual_stop_risk=stop_bound_risk(entry, stop, base_volume),
        state="PENDING",
    )


def passive_filled(row: dict[str, Any], pending: Exposure | None) -> Exposure:
    if pending is None:
        raise RuntimeError(f"passive fill without pending order at {row['server_time']}")
    entry = row["value_a_number"]
    volume = row["value_b_number"]
    return Exposure(
        component_id=row["component_id"],
        opened=row["server_time"],
        entry=entry,
        stop=pending.stop,
        volume=volume,
        reserved_budget=pending.reserved_budget,
        actual_stop_risk=stop_bound_risk(entry, pending.stop, volume),
        state="POSITION",
    )


def lifecycle_close(
    rows: list[dict[str, Any]], open_row: dict[str, Any]
) -> dict[str, Any] | None:
    for row in rows:
        if (
            row["sequence"] > open_row["sequence"]
            and row["component_id"] == open_row["component_id"]
            and row["event"] in {"CLOSE", "EXTERNAL_CLOSE"}
        ):
            return row
    return None


def event_key(row: dict[str, Any]) -> str:
    return f"{row['server_time']}|{row['component_id']}"


def analyze_run(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    deposit = float(spec["deposit"])
    base_volume = 0.01 * deposit / 100.0
    rows = load_events(spec["directory"], spec["events"])
    active: dict[str, Exposure] = {}
    pending: Exposure | None = None
    skips: list[dict[str, Any]] = []
    maximum_positions = 0
    open_rows: dict[str, dict[str, Any]] = {}
    signals_by_time: dict[str, list[str]] = {}

    for row in rows:
        event = row["event"]
        component = row["component_id"]
        if event == "SIGNAL_DECIDED":
            signals_by_time.setdefault(row["server_time"], []).append(
                COMPONENTS.get(component, component)
            )
        elif event == "PASSIVE_PLACE":
            pending = passive_pending(row, base_volume)
        elif event == "PASSIVE_FILL":
            active[component] = passive_filled(row, pending)
            pending = None
            open_rows[event_key(row)] = row
        elif event == "PASSIVE_EXPIRE":
            pending = None
        elif event == "OPEN":
            active[component] = market_exposure(row)
            open_rows[event_key(row)] = row
        elif event in {"CLOSE", "EXTERNAL_CLOSE"}:
            active.pop(component, None)
        elif event == "RISK_ADMISSION_SKIP":
            position_cap = detail_number(row["detail"], "position_cap") or 0.0
            aggregate_cap = detail_number(row["detail"], "aggregate_cap") or 0.0
            exposures = list(active.values()) + ([pending] if pending else [])
            actual_before = sum(item.actual_stop_risk for item in exposures)
            reserved_before = sum(item.reserved_budget for item in exposures)
            candidate_actual = row["value_a_number"]
            actual_after = actual_before + candidate_actual
            occupied_units = len(exposures)
            rebase_allowed = (
                occupied_units + 1 <= 3
                and actual_after <= aggregate_cap + TOLERANCE
            )
            residual_only_allowed = actual_after <= aggregate_cap + TOLERANCE
            unit_only_allowed = occupied_units + 1 <= 3
            skips.append(
                {
                    "key": event_key(row),
                    "server_time": row["server_time"],
                    "candidate": COMPONENTS.get(component, component),
                    "candidate_actual_stop_risk": rounded(candidate_actual),
                    "candidate_position_budget": rounded(position_cap),
                    "occupied_units": occupied_units,
                    "units_after": occupied_units + 1,
                    "incumbents": [item.record() for item in exposures],
                    "reserved_before": rounded(reserved_before),
                    "current_dollar_aggregate_after": rounded(row["value_b_number"]),
                    "actual_stop_risk_before": rounded(actual_before),
                    "actual_stop_risk_after": rounded(actual_after),
                    "aggregate_cap": rounded(aggregate_cap),
                    "current_dollar_excess": rounded(
                        row["value_b_number"] - aggregate_cap
                    ),
                    "actual_stop_headroom": rounded(aggregate_cap - actual_after),
                    "mechanisms": {
                        "current_entry_budget_dollars": False,
                        "current_cap_three_units_with_actual_stop_backstop": rebase_allowed,
                        "actual_stop_residual_only": residual_only_allowed,
                        "three_units_without_stop_backstop": unit_only_allowed,
                        "lot_demotion_under_same_stop_budget": False,
                    },
                    "same_timestamp_signals": signals_by_time.get(row["server_time"], []),
                }
            )
        maximum_positions = max(maximum_positions, len(active) + int(pending is not None))

    entries = [
        row for row in rows if row["event"] in {"OPEN", "PASSIVE_FILL"}
    ]
    return {
        "name": name,
        "deposit": deposit,
        "entries": len(entries),
        "risk_admission_skips": len(skips),
        "maximum_occupied_units": maximum_positions,
        "open_keys": sorted(event_key(row) for row in entries),
        "skip_keys": sorted(item["key"] for item in skips),
        "skips": skips,
        "rows": rows,
        "open_rows": open_rows,
        "sources": [source(spec["directory"] / event) for event in spec["events"]],
    }


def mechanism_summary(runs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    mechanism_names = list(runs["geometry_100"]["skips"][0]["mechanisms"])
    output: dict[str, Any] = {}
    for mechanism in mechanism_names:
        paths: dict[str, Any] = {}
        for name, run in runs.items():
            eligible = [
                row for row in run["skips"] if row["mechanisms"][mechanism]
            ]
            paths[name] = {
                "existing_entries": run["entries"],
                "fixed_path_newly_eligible": len(eligible),
                "fixed_path_entry_projection": run["entries"] + len(eligible),
                "maximum_units_after_newly_eligible": max(
                    (row["units_after"] for row in eligible), default=0
                ),
                "maximum_actual_stop_risk_percent": rounded(
                    max(
                        (
                            100.0
                            * row["actual_stop_risk_after"]
                            / (row["aggregate_cap"] / AGGREGATE_RISK_FRACTION)
                            for row in eligible
                        ),
                        default=0.0,
                    )
                ),
                "eligible_keys": [row["key"] for row in eligible],
            }
        output[mechanism] = paths
    return output


def main() -> None:
    runs = {name: analyze_run(name, spec) for name, spec in RUNS.items()}
    open_sets = {name: set(run["open_keys"]) for name, run in runs.items()}
    missing_300_vs_200 = sorted(open_sets["geometry_200"] - open_sets["geometry_300"])
    extra_300_vs_200 = sorted(open_sets["geometry_300"] - open_sets["geometry_200"])
    if len(missing_300_vs_200) != 1 or extra_300_vs_200:
        raise RuntimeError(
            "expected exactly one 300 USD missing entry and no extra entry versus 200 USD"
        )
    missing_key = missing_300_vs_200[0]
    missing_skip = next(
        row for row in runs["geometry_300"]["skips"] if row["key"] == missing_key
    )
    matched_open = runs["geometry_200"]["open_rows"][missing_key]
    matched_close = lifecycle_close(runs["geometry_200"]["rows"], matched_open)
    if matched_close is None:
        raise RuntimeError("matched 200 USD lifecycle did not close")

    return_key = "2026.03.06 16:00:00|ZT-H1-US30-RETURN-I-c870a788ec"
    return_200 = runs["geometry_200"]["open_rows"][return_key]
    return_300 = runs["geometry_300"]["open_rows"][return_key]
    return_200_close = lifecycle_close(runs["geometry_200"]["rows"], return_200)
    return_300_close = lifecycle_close(runs["geometry_300"]["rows"], return_300)
    if return_200_close is None or return_300_close is None:
        raise RuntimeError("causal Return incumbent did not close")

    mechanisms = mechanism_summary(runs)
    selected_name = "current_cap_three_units_with_actual_stop_backstop"
    selected = mechanisms[selected_name]
    selected_counts = {
        name: item["fixed_path_entry_projection"] for name, item in selected.items()
    }
    selected_topology_aligned = len(set(selected_counts.values())) == 1
    selected_recovers_missing = missing_key in selected["geometry_300"]["eligible_keys"]
    selected_never_exceeds_three = all(
        item["maximum_units_after_newly_eligible"] <= 3
        for item in selected.values()
    )
    selected_never_exceeds_actual_cap = all(
        item["maximum_actual_stop_risk_percent"] <= 12.0 + 1.0e-9
        for item in selected.values()
    )

    incident = {
        "missing_key": missing_key,
        "candidate": missing_skip,
        "physical_sequence": [
            "PRESSURE entered at 15:00",
            "RETURN entered at 16:00",
            "CROSS was evaluated at 17:00",
        ],
        "same_timestamp_competition": len(missing_skip["same_timestamp_signals"]) > 1,
        "return_incumbent": {
            "geometry_200": {
                "entry_time": return_200["server_time"],
                "volume": return_200["value_b_number"],
                "stop": detail_number(return_200["detail"], "stop"),
                "close_time": return_200_close["server_time"],
                "close_event": return_200_close["event"],
                "actual_net": rounded(return_200_close["value_a_number"]),
                "stressed_net": rounded(return_200_close["value_b_number"]),
            },
            "geometry_300": {
                "entry_time": return_300["server_time"],
                "volume": return_300["value_b_number"],
                "stop": detail_number(return_300["detail"], "stop"),
                "close_time": return_300_close["server_time"],
                "close_event": return_300_close["event"],
                "actual_net": rounded(return_300_close["value_a_number"]),
                "stressed_net": rounded(return_300_close["value_b_number"]),
            },
            "interpretation": "The 300 USD Return stop was 4.74 index points farther away. It survived the 16:59:11 tick that stopped the 200 USD path and remained an occupied risk unit when CROSS arrived.",
        },
        "matched_200_cross_outcome_diagnostic_only": {
            "open_time": matched_open["server_time"],
            "volume": matched_open["value_b_number"],
            "stop": detail_number(matched_open["detail"], "stop"),
            "close_time": matched_close["server_time"],
            "actual_net": rounded(matched_close["value_a_number"]),
            "stressed_net": rounded(matched_close["value_b_number"]),
            "selection_use": False,
        },
        "cause_decomposition": {
            "physical_evaluation_order": "not_direct; the three relevant decisions occurred at distinct 15:00, 16:00 and 17:00 times",
            "incumbent_occupancy": "causal; PRESSURE and RETURN were both open at the 300 USD CROSS decision",
            "aggregate_12_percent": "immediate_block; two 37.3038 entry budgets plus the current 37.0007 unit produced 111.6082 against 111.0020",
            "lot_rounding": "not_direct; 0.04 at 200 and 0.06 at 300 are exactly deposit-proportional. Earlier path P/L changed conservative capital and widened the 300 USD Return stop, which changed occupancy.",
            "lower_lot_demotion": "not_independent; the frozen stop search expands distance to spend the same position budget and admission then books a full 4 percent unit, so volume reduction alone does not create aggregate capacity",
        },
    }

    payload = {
        "unit": "capital-scale-admission-topology-010",
        "question": "Can shared 12 percent admission use scale-consistent risk units so the 300 USD path recovers its single missing opportunity without increasing maximum exposure or weakening transition reserve?",
        "boundary": {
            "opened_scope": "decompose the one scale-induced missing lifecycle and compare only fixed current-dollar, residual-risk, risk-unit, same-time handling and lot-demotion representations already named by the open unit",
            "new_hypothesis_opened": False,
            "transition_reserve": "prospective_position_budget_1_25 retained unchanged",
            "entry_priority": "unchanged first-come physical order",
            "live_surface": "untouched",
        },
        "path_topology": {
            name: {
                "deposit": run["deposit"],
                "entries": run["entries"],
                "risk_admission_skips": run["risk_admission_skips"],
                "maximum_occupied_units": run["maximum_occupied_units"],
            }
            for name, run in runs.items()
        },
        "entry_set_comparison": {
            "missing_300_vs_200": missing_300_vs_200,
            "extra_300_vs_200": extra_300_vs_200,
        },
        "incident": incident,
        "mechanisms": mechanisms,
        "mechanism_judgement": {
            "current_entry_budget_dollars": "retains the scale-induced missing lifecycle because old 4 percent dollar reservations do not contract with current conservative capital",
            "actual_stop_residual_only": "rejected before runtime because it can admit a fourth concurrent exposure even when actual stop risk remains below 12 percent",
            "three_units_without_stop_backstop": "rejected before runtime because unit count alone has no catastrophic-stop dollar backstop after a deep capital contraction",
            "lot_demotion_under_same_stop_budget": "rejected before runtime because unchanged stop-budget search and full-unit booking consume the same admission capacity at a lower volume",
            "same_timestamp_batching": "not applicable to the missing event because the incumbent and candidate decisions are one hour apart",
            selected_name: {
                "selected_for_runtime": True,
                "fixed_path_entry_projection": selected_counts,
                "fixed_path_projection_equal": selected_topology_aligned,
                "scale_consistent_contract": True,
                "existing_entries_suppressed": 0,
                "recovers_missing_300_lifecycle": selected_recovers_missing,
                "maximum_three_units": selected_never_exceeds_three,
                "actual_stop_risk_within_12_percent": selected_never_exceeds_actual_cap,
                "contract": "Each live position or pending Passive order occupies one current 4 percent risk unit; no more than three units may exist, and exact initial catastrophic-stop risk including the candidate must also remain within current 12 percent capacity.",
            },
        },
        "runtime_plan": {
            "required": all(
                (
                    selected_recovers_missing,
                    selected_never_exceeds_three,
                    selected_never_exceeds_actual_cap,
                )
            ),
            "paths": [
                "current-cap-three-units-stop-backstop at 100 USD",
                "current-cap-three-units-stop-backstop at 200 USD",
                "current-cap-three-units-stop-backstop at 300 USD",
            ],
            "reason": "The same relax-only rule applies at all deposits, preserves every existing entry, first-come order and transition reserve, recovers the named 300 USD miss, and allows neither a fourth unit nor an exact-stop-risk breach. Fixed-path projections are 933/934/933, so endogenous real-tick mutation rather than projection equality is decisive.",
        },
        "limits": [
            "Fixed-path eligibility does not include endogenous P/L, stop, hold, exchange or later admission mutation; real-tick runtime is decisive.",
            "The matched 200 USD winner is descriptive only and did not select the mechanism.",
            "No strategy priority, preemption, threshold rescue, latest-period extension or independent-account study is opened here.",
        ],
        "skip_diagnostics": {name: run["skips"] for name, run in runs.items()},
        "sources": {
            "transition_runtime": source(
                ROOT / "lab" / "frontier" / "transition-reserve-geometry" / "runtime.json"
            ),
            "runs": {name: run["sources"] for name, run in runs.items()},
        },
    }
    FRONTIER.mkdir(parents=True, exist_ok=True)
    output = FRONTIER / "proxy.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
