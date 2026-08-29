from __future__ import annotations

import csv
import hashlib
import json
import math
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
CAMPAIGN_ROOT = SCRIPT_PATH.parents[1]
REPOSITORY_ROOT = SCRIPT_PATH.parents[4]
CONFIG_PATH = CAMPAIGN_ROOT / "config" / "proxy-contract.json"
OUTPUT_PATH = (
    REPOSITORY_ROOT
    / "optimization"
    / "artifacts"
    / "raw"
    / "dd20-protective-stop-headroom-proxy-v1"
    / "output"
    / "proxy-result.json"
)
TIME_FORMAT = "%Y.%m.%d %H:%M:%S"


@dataclass(frozen=True)
class CloseRow:
    ordinal: int
    native_close_time: datetime
    trough_time: datetime
    component_id: str
    position_identifier: str
    planned_risk_usd: float
    trough_mark_r: float
    native_actual_net_usd: float
    native_stressed_net_usd: float


@dataclass(frozen=True)
class CandidateExit:
    ordinal: int
    event_time: datetime
    component_id: str
    actual_net_usd: float
    stressed_net_usd: float
    stopped: bool


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_lifecycles(
    path: Path,
    declared: dict[str, Any],
    components: set[str],
) -> tuple[list[CloseRow], dict[str, Any]]:
    if path.stat().st_size != int(declared["bytes"]):
        raise RuntimeError(f"input byte mismatch: {path.name}")
    digest = sha256(path)
    if digest != str(declared["sha256"]):
        raise RuntimeError(f"input hash mismatch: {path.name}")

    rows = 0
    births = 0
    close_rows: list[CloseRow] = []
    dropped_max = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for source in csv.DictReader(handle):
            rows += 1
            event = source["event"]
            if event == "BIRTH":
                births += 1
                continue
            if event != "CLOSE":
                continue
            component = source["component_id"]
            if component not in components:
                raise RuntimeError("close row contains a disabled or undeclared component")
            if int(source["partial_observation"]) != 0:
                raise RuntimeError("partial close row is not eligible")
            dropped_max = max(dropped_max, int(source["research_dropped_records"]))
            planned_risk = float(source["planned_risk_usd"])
            trough_r = float(source["trough_mark_r"])
            if planned_risk <= 0.0 or not math.isfinite(trough_r):
                raise RuntimeError("close row lacks valid risk or trough information")
            native_close_time = datetime.strptime(source["server_time"], TIME_FORMAT)
            trough_time = datetime.strptime(source["trough_time_server"], TIME_FORMAT)
            if trough_time < datetime.strptime(source["entry_time_server"], TIME_FORMAT):
                raise RuntimeError("trough precedes entry")
            close_rows.append(
                CloseRow(
                    ordinal=rows,
                    native_close_time=native_close_time,
                    trough_time=trough_time,
                    component_id=component,
                    position_identifier=source["position_identifier"],
                    planned_risk_usd=planned_risk,
                    trough_mark_r=trough_r,
                    native_actual_net_usd=float(source["actual_net_usd"]),
                    native_stressed_net_usd=float(source["stressed_net_usd"]),
                )
            )

    if rows != int(declared["rows"]):
        raise RuntimeError("input row count mismatch")
    if births != int(declared["births"]):
        raise RuntimeError("input birth count mismatch")
    if len(close_rows) != int(declared["closes"]):
        raise RuntimeError("input close count mismatch")
    actual = math.fsum(row.native_actual_net_usd for row in close_rows)
    stressed = math.fsum(row.native_stressed_net_usd for row in close_rows)
    if abs(actual - float(declared["actual_net_usd"])) > 1.0e-7:
        raise RuntimeError("input actual net mismatch")
    if abs(stressed - float(declared["stressed_net_usd"])) > 1.0e-7:
        raise RuntimeError("input stressed net mismatch")
    if dropped_max != 0:
        raise RuntimeError("input reports dropped research records")
    return close_rows, {
        "name": path.name,
        "bytes": path.stat().st_size,
        "sha256": digest,
        "rows": rows,
        "births": births,
        "closes": len(close_rows),
        "actual_net_usd": actual,
        "stressed_net_usd": stressed,
    }


def parse_period(source: dict[str, Any]) -> tuple[datetime, datetime]:
    return (
        datetime.strptime(str(source["start"]), TIME_FORMAT),
        datetime.strptime(str(source["end"]), TIME_FORMAT),
    )


def candidate_exits(
    rows: list[CloseRow],
    headroom: float,
    reserve: float,
    timing_bound: str,
) -> list[CandidateExit]:
    if timing_bound not in {"trough_time", "native_close_time"}:
        raise RuntimeError("unknown timing bound")
    control = abs(headroom - 0.25) <= 1.0e-12
    gross_fraction = 1.0 - reserve - headroom
    if gross_fraction <= 0.0:
        raise RuntimeError("candidate gross stop fraction is nonpositive")
    exits: list[CandidateExit] = []
    for row in rows:
        stopped = False
        actual = row.native_actual_net_usd
        stressed = row.native_stressed_net_usd
        event_time = row.native_close_time
        if not control and row.trough_mark_r <= -gross_fraction + 1.0e-12:
            stopped = True
            actual = -row.planned_risk_usd * gross_fraction
            extra_cost = max(0.0, row.native_actual_net_usd - row.native_stressed_net_usd)
            stressed = actual - extra_cost
            if timing_bound == "trough_time":
                event_time = row.trough_time
        exits.append(
            CandidateExit(
                ordinal=row.ordinal,
                event_time=event_time,
                component_id=row.component_id,
                actual_net_usd=actual,
                stressed_net_usd=stressed,
                stopped=stopped,
            )
        )
    exits.sort(key=lambda item: (item.event_time, item.ordinal))
    return exits


def simulate(
    exits: list[CandidateExit],
    period_start: datetime,
    period_end: datetime,
    reference: float,
    component_ids: list[str],
) -> dict[str, Any]:
    actual_balance = reference
    stressed_balance = reference
    actual_peak = reference
    stressed_peak = reference
    actual_max_dd = 0.0
    stressed_max_dd = 0.0
    actual_minimum = reference
    stressed_minimum = reference
    component_counts = {component: 0 for component in component_ids}
    closes = 0
    hypothetical_stops = 0

    for event in exits:
        if not (period_start <= event.event_time < period_end):
            continue
        closes += 1
        hypothetical_stops += int(event.stopped)
        component_counts[event.component_id] += 1
        actual_balance += event.actual_net_usd
        stressed_balance += event.stressed_net_usd
        actual_peak = max(actual_peak, actual_balance)
        stressed_peak = max(stressed_peak, stressed_balance)
        if actual_peak > 0.0:
            actual_max_dd = max(actual_max_dd, (actual_peak - actual_balance) / actual_peak)
        else:
            actual_max_dd = math.inf
        if stressed_peak > 0.0:
            stressed_max_dd = max(
                stressed_max_dd, (stressed_peak - stressed_balance) / stressed_peak
            )
        else:
            stressed_max_dd = math.inf
        actual_minimum = min(actual_minimum, actual_balance)
        stressed_minimum = min(stressed_minimum, stressed_balance)

    return {
        "actual_net_usd": actual_balance - reference,
        "stressed_net_usd": stressed_balance - reference,
        "raw_closed_balance_drawdown_pct": max(actual_max_dd, stressed_max_dd) * 100.0,
        "minimum_balance_usd": min(actual_minimum, stressed_minimum),
        "closes": closes,
        "hypothetical_stop_closes": hypothetical_stops,
        "component_closes": component_counts,
    }


def main() -> None:
    started = time.perf_counter()
    if OUTPUT_PATH.exists():
        raise RuntimeError("formal proxy output already exists")
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    input_root = REPOSITORY_ROOT / str(config["input"]["root"])
    component_ids = [str(value) for value in config["components"]]
    components = set(component_ids)
    declared_files = {str(item["name"]): item for item in config["input"]["files"]}
    selection_rows, selection_receipt = load_lifecycles(
        input_root / "anchor-selection-lifecycles.csv",
        declared_files["anchor-selection-lifecycles.csv"],
        components,
    )
    forward_rows, forward_receipt = load_lifecycles(
        input_root / "anchor-forward-lifecycles.csv",
        declared_files["anchor-forward-lifecycles.csv"],
        components,
    )

    reference = float(config["reference_capital_usd"])
    reserve = float(config["qualified_anchor"]["unmodelled_risk_reserve_fraction"])
    headrooms = [float(value) for value in config["stop_headroom_grid"]]
    timing_bounds = [str(value) for value in config["timing_bounds"]]
    if headrooms[0] != 0.25 or headrooms != sorted(set(headrooms)):
        raise RuntimeError("headroom grid must be unique, ordered and start at control")
    selection_start, selection_end = parse_period(config["selection_period"])

    control_exits = candidate_exits(selection_rows, 0.25, reserve, "native_close_time")
    control = simulate(
        control_exits, selection_start, selection_end, reference, component_ids
    )
    expected = declared_files["anchor-selection-lifecycles.csv"]
    if abs(control["actual_net_usd"] - float(expected["actual_net_usd"])) > 1.0e-7:
        raise RuntimeError("control actual reproduction failed")
    if abs(control["stressed_net_usd"] - float(expected["stressed_net_usd"])) > 1.0e-7:
        raise RuntimeError("control stressed reproduction failed")
    if control["closes"] != int(expected["closes"]):
        raise RuntimeError("control close reproduction failed")

    native_anchor_dd = float(
        config["qualified_anchor"]["selection_native_relative_equity_dd_pct"]
    )
    effective_dd_limit = float(
        config["qualified_anchor"]["effective_pragmatic_dd_limit_pct"]
    )
    control_raw_dd = float(control["raw_closed_balance_drawdown_pct"])
    if control_raw_dd <= 0.0:
        raise RuntimeError("control raw drawdown is not calibratable")
    dd_factor = native_anchor_dd / control_raw_dd

    records: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for headroom in headrooms:
        bound_records: dict[str, Any] = {}
        for timing in timing_bounds:
            exits = candidate_exits(selection_rows, headroom, reserve, timing)
            metrics = simulate(
                exits, selection_start, selection_end, reference, component_ids
            )
            epoch_metrics: list[dict[str, Any]] = []
            for epoch in config["selection_epochs"]:
                epoch_start, epoch_end = parse_period(epoch)
                epoch_result = simulate(
                    exits, epoch_start, epoch_end, reference, component_ids
                )
                epoch_metrics.append({"id": str(epoch["id"]), **epoch_result})
            calibrated_dd = max(
                metrics["raw_closed_balance_drawdown_pct"],
                metrics["raw_closed_balance_drawdown_pct"] * dd_factor,
            )
            bound_records[timing] = {
                **metrics,
                "calibrated_selection_dd_pct": calibrated_dd,
                "epochs": epoch_metrics,
            }

        minimum_actual = min(
            bound_records[timing]["actual_net_usd"] for timing in timing_bounds
        )
        minimum_stressed = min(
            bound_records[timing]["stressed_net_usd"] for timing in timing_bounds
        )
        worst_dd = max(
            bound_records[timing]["calibrated_selection_dd_pct"]
            for timing in timing_bounds
        )
        gates = {
            "above_control_headroom": headroom > 0.25,
            "both_bounds_actual_profit_improve": all(
                bound_records[timing]["actual_net_usd"] > control["actual_net_usd"] + 1.0e-9
                for timing in timing_bounds
            ),
            "both_bounds_stressed_profit_improve": all(
                bound_records[timing]["stressed_net_usd"] > control["stressed_net_usd"] + 1.0e-9
                for timing in timing_bounds
            ),
            "both_bounds_all_epochs_positive": all(
                epoch["actual_net_usd"] > 0.0 and epoch["stressed_net_usd"] > 0.0
                for timing in timing_bounds
                for epoch in bound_records[timing]["epochs"]
            ),
            "five_component_breadth": all(
                bound_records[timing]["component_closes"][component] > 0
                for timing in timing_bounds
                for component in component_ids
            ),
            "both_bounds_balance_positive": all(
                bound_records[timing]["minimum_balance_usd"] > 0.0
                for timing in timing_bounds
            ),
            "worst_dd_no_worse_than_native_anchor": worst_dd <= native_anchor_dd + 1.0e-12,
            "worst_dd_within_effective_limit": worst_dd <= effective_dd_limit + 1.0e-12,
        }
        record = {
            "headroom_fraction": headroom,
            "gross_stop_risk_fraction": 1.0 - reserve - headroom,
            "timing_bounds": bound_records,
            "minimum_actual_net_usd": minimum_actual,
            "minimum_stressed_net_usd": minimum_stressed,
            "worst_calibrated_selection_dd_pct": worst_dd,
            "gates": gates,
            "selection_eligible": all(gates.values()),
        }
        records.append(record)
        if record["selection_eligible"]:
            eligible.append(record)

    winner = None
    holdout = None
    holdout_passed = False
    if eligible:
        winner = max(
            eligible,
            key=lambda item: (
                item["minimum_stressed_net_usd"],
                item["minimum_actual_net_usd"],
                -item["worst_calibrated_selection_dd_pct"],
                -item["headroom_fraction"],
            ),
        )
        period_records: list[dict[str, Any]] = []
        for period in config["holdout_periods"]:
            period_start, period_end = parse_period(period)
            bounds: dict[str, Any] = {}
            for timing in timing_bounds:
                exits = candidate_exits(
                    forward_rows,
                    float(winner["headroom_fraction"]),
                    reserve,
                    timing,
                )
                metrics = simulate(
                    exits, period_start, period_end, reference, component_ids
                )
                gates = {
                    "actual_positive": metrics["actual_net_usd"] > 0.0,
                    "stressed_positive": metrics["stressed_net_usd"] > 0.0,
                    "balance_positive": metrics["minimum_balance_usd"] > 0.0,
                    "raw_dd_within_effective_limit": metrics["raw_closed_balance_drawdown_pct"] <= effective_dd_limit + 1.0e-12,
                }
                bounds[timing] = {**metrics, "gates": gates, "passed": all(gates.values())}
            period_records.append(
                {
                    "id": str(period["id"]),
                    "timing_bounds": bounds,
                    "all_bounds_passed": all(bounds[timing]["passed"] for timing in timing_bounds),
                }
            )
        holdout_passed = all(period["all_bounds_passed"] for period in period_records)
        holdout = {
            "opened_for_headroom_fraction": winner["headroom_fraction"],
            "periods": period_records,
            "all_gates_passed": holdout_passed,
        }

    shortlist = []
    if winner is not None and holdout_passed:
        shortlist.append(
            {
                "stop_placement_headroom_fraction": winner["headroom_fraction"],
                "unmodelled_risk_reserve_fraction": reserve,
                "position_risk_fraction": config["qualified_anchor"]["position_risk_fraction"],
                "aggregate_risk_fraction": config["qualified_anchor"]["aggregate_risk_fraction"],
                "component_exposure_multipliers": config["qualified_anchor"]["component_exposure_multipliers"],
                "maximum_shortlist_size": 1,
            }
        )

    output = {
        "schema": "zeta-dd20-protective-stop-headroom-proxy-raw-output-v1",
        "campaign": str(config["campaign"]),
        "formal_process_invocations": 1,
        "elapsed_seconds": time.perf_counter() - started,
        "input_receipts": [selection_receipt, forward_receipt],
        "control": control,
        "selection_dd_calibration_factor": dd_factor,
        "selection_records": records,
        "selection_eligible_count": len(eligible),
        "selection_winner": winner,
        "holdout": holdout,
        "mt5_shortlist": shortlist,
        "mt5_shortlist_size": len(shortlist),
        "interpretation_boundary": {
            "native_first_crossing_or_fill_claim": False,
            "native_profit_claim": False,
            "native_drawdown_claim": False,
            "volume_admission_or_later_path_synthesized": False,
            "live_lab_or_master_action": False,
        },
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
