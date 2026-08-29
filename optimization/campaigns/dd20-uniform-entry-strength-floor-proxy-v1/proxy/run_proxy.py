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
    / "dd20-uniform-entry-strength-floor-proxy-v1"
    / "output"
    / "proxy-result.json"
)
TIME_FORMAT = "%Y.%m.%d %H:%M:%S"


@dataclass(frozen=True)
class CloseRow:
    ordinal: int
    server_time: datetime
    component_id: str
    position_identifier: str
    normalized_strength: float
    actual_net_usd: float
    stressed_net_usd: float


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def normalized_strength(feature: float, component: dict[str, Any]) -> float:
    threshold = float(component["native_threshold"])
    rule = str(component["rule"])
    if rule == "positive":
        value = feature
    elif rule == "negative":
        value = -feature
    elif rule == "absolute":
        value = abs(feature)
    else:
        raise RuntimeError(f"unknown threshold rule: {rule}")
    return value / threshold


def load_lifecycles(
    path: Path,
    declared: dict[str, Any],
    component_map: dict[str, dict[str, Any]],
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
            if source["component_id"] not in component_map:
                raise RuntimeError("close row contains a disabled or undeclared component")
            if int(source["partial_observation"]) != 0:
                raise RuntimeError("partial close row is not eligible")
            dropped_max = max(dropped_max, int(source["research_dropped_records"]))
            feature = float(source["entry_feature"])
            strength = normalized_strength(feature, component_map[source["component_id"]])
            if not math.isfinite(strength) or strength < 1.0 - 1.0e-10:
                raise RuntimeError("native close does not reproduce its declared threshold")
            close_rows.append(
                CloseRow(
                    ordinal=rows,
                    server_time=datetime.strptime(source["server_time"], TIME_FORMAT),
                    component_id=source["component_id"],
                    position_identifier=source["position_identifier"],
                    normalized_strength=strength,
                    actual_net_usd=float(source["actual_net_usd"]),
                    stressed_net_usd=float(source["stressed_net_usd"]),
                )
            )

    if rows != int(declared["rows"]):
        raise RuntimeError("input row count mismatch")
    if births != int(declared["births"]):
        raise RuntimeError("input birth count mismatch")
    if len(close_rows) != int(declared["closes"]):
        raise RuntimeError("input close count mismatch")
    actual = math.fsum(row.actual_net_usd for row in close_rows)
    stressed = math.fsum(row.stressed_net_usd for row in close_rows)
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


def simulate(
    rows: list[CloseRow],
    multiplier: float,
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
    retained = 0
    removed = 0

    for row in rows:
        if not (period_start <= row.server_time < period_end):
            continue
        if row.normalized_strength + 1.0e-12 < multiplier:
            removed += 1
            continue
        retained += 1
        component_counts[row.component_id] += 1
        actual_balance += row.actual_net_usd
        stressed_balance += row.stressed_net_usd
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
        "retained_closes": retained,
        "removed_closes": removed,
        "component_retained_closes": component_counts,
    }


def main() -> None:
    started = time.perf_counter()
    if OUTPUT_PATH.exists():
        raise RuntimeError("formal proxy output already exists")
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    input_root = REPOSITORY_ROOT / str(config["input"]["root"])
    component_map = {str(item["id"]): item for item in config["components"]}
    component_ids = list(component_map)
    declared_files = {str(item["name"]): item for item in config["input"]["files"]}

    selection_rows, selection_receipt = load_lifecycles(
        input_root / "anchor-selection-lifecycles.csv",
        declared_files["anchor-selection-lifecycles.csv"],
        component_map,
    )
    forward_rows, forward_receipt = load_lifecycles(
        input_root / "anchor-forward-lifecycles.csv",
        declared_files["anchor-forward-lifecycles.csv"],
        component_map,
    )

    reference = float(config["reference_capital_usd"])
    selection_start, selection_end = parse_period(config["selection_period"])
    multipliers = [float(value) for value in config["global_threshold_multipliers"]]
    if multipliers[0] != 1.0 or multipliers != sorted(set(multipliers)):
        raise RuntimeError("threshold grid must be unique, ordered and start at control")

    control = simulate(
        selection_rows, 1.0, selection_start, selection_end, reference, component_ids
    )
    expected_selection = declared_files["anchor-selection-lifecycles.csv"]
    if abs(control["actual_net_usd"] - float(expected_selection["actual_net_usd"])) > 1.0e-7:
        raise RuntimeError("control actual reproduction failed")
    if abs(control["stressed_net_usd"] - float(expected_selection["stressed_net_usd"])) > 1.0e-7:
        raise RuntimeError("control stressed reproduction failed")
    if control["retained_closes"] != int(expected_selection["closes"]):
        raise RuntimeError("control close reproduction failed")

    native_anchor_dd = float(
        config["qualified_anchor"]["selection_native_relative_equity_dd_pct"]
    )
    if control["raw_closed_balance_drawdown_pct"] <= 0.0:
        raise RuntimeError("control raw drawdown is not calibratable")
    dd_factor = native_anchor_dd / control["raw_closed_balance_drawdown_pct"]
    effective_dd_limit = float(
        config["qualified_anchor"]["effective_pragmatic_dd_limit_pct"]
    )

    records: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for multiplier in multipliers:
        metrics = simulate(
            selection_rows,
            multiplier,
            selection_start,
            selection_end,
            reference,
            component_ids,
        )
        epoch_metrics: list[dict[str, Any]] = []
        for epoch in config["selection_epochs"]:
            epoch_start, epoch_end = parse_period(epoch)
            epoch_result = simulate(
                selection_rows,
                multiplier,
                epoch_start,
                epoch_end,
                reference,
                component_ids,
            )
            epoch_metrics.append({"id": str(epoch["id"]), **epoch_result})
        calibrated_dd = max(
            metrics["raw_closed_balance_drawdown_pct"],
            metrics["raw_closed_balance_drawdown_pct"] * dd_factor,
        )
        gates = {
            "above_control_multiplier": multiplier > 1.0,
            "actual_profit_improves": metrics["actual_net_usd"] > control["actual_net_usd"] + 1.0e-9,
            "stressed_profit_improves": metrics["stressed_net_usd"] > control["stressed_net_usd"] + 1.0e-9,
            "all_epochs_positive": all(
                item["actual_net_usd"] > 0.0 and item["stressed_net_usd"] > 0.0
                for item in epoch_metrics
            ),
            "five_component_breadth": all(
                int(metrics["component_retained_closes"][component]) > 0
                for component in component_ids
            ),
            "balance_positive": metrics["minimum_balance_usd"] > 0.0,
            "calibrated_dd_no_worse_than_anchor": calibrated_dd <= native_anchor_dd + 1.0e-12,
            "calibrated_dd_within_effective_limit": calibrated_dd <= effective_dd_limit + 1.0e-12,
        }
        record = {
            "multiplier": multiplier,
            **metrics,
            "calibrated_selection_dd_pct": calibrated_dd,
            "nominal_20pct_dd_passed": calibrated_dd <= 20.0 + 1.0e-12,
            "epochs": epoch_metrics,
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
                item["stressed_net_usd"],
                item["actual_net_usd"],
                -item["calibrated_selection_dd_pct"],
                -item["multiplier"],
            ),
        )
        holdout_periods: list[dict[str, Any]] = []
        for period in config["holdout_periods"]:
            period_start, period_end = parse_period(period)
            metrics = simulate(
                forward_rows,
                float(winner["multiplier"]),
                period_start,
                period_end,
                reference,
                component_ids,
            )
            gates = {
                "actual_positive": metrics["actual_net_usd"] > 0.0,
                "stressed_positive": metrics["stressed_net_usd"] > 0.0,
                "balance_positive": metrics["minimum_balance_usd"] > 0.0,
                "raw_dd_within_effective_limit": metrics["raw_closed_balance_drawdown_pct"] <= effective_dd_limit + 1.0e-12,
            }
            holdout_periods.append(
                {"id": str(period["id"]), **metrics, "gates": gates, "passed": all(gates.values())}
            )
        holdout_passed = all(period["passed"] for period in holdout_periods)
        holdout = {
            "opened_for_multiplier": winner["multiplier"],
            "periods": holdout_periods,
            "all_gates_passed": holdout_passed,
        }

    shortlist = []
    if winner is not None and holdout_passed:
        shortlist.append(
            {
                "global_threshold_multiplier": winner["multiplier"],
                "position_risk_fraction": config["qualified_anchor"]["position_risk_fraction"],
                "aggregate_risk_fraction": config["qualified_anchor"]["aggregate_risk_fraction"],
                "component_exposure_multipliers": config["qualified_anchor"]["component_exposure_multipliers"],
                "maximum_shortlist_size": 1,
            }
        )

    output = {
        "schema": "zeta-dd20-uniform-entry-strength-floor-proxy-raw-output-v1",
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
            "native_profit_claim": False,
            "native_drawdown_claim": False,
            "freed_admissions_or_sizing_feedback_synthesized": False,
            "component_specific_tuning": False,
            "live_lab_or_master_action": False,
        },
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
