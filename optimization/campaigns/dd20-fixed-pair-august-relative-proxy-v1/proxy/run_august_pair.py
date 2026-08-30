from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

import proxy_engine as engine


FAMILY = "dd20-fixed-pair-august-relative-proxy-v1"
SCRIPT_PATH = Path(__file__).resolve()
CAMPAIGN_ROOT = SCRIPT_PATH.parents[1]
REPOSITORY_ROOT = SCRIPT_PATH.parents[4]
CONTRACT_PATH = CAMPAIGN_ROOT / "config" / "campaign-contract.json"
MARKET_ROOT = (
    REPOSITORY_ROOT / "optimization" / "artifacts" / "raw" / FAMILY / "market"
)
OUTPUT_ROOT = MARKET_ROOT.parent / "output"
RESULT_PATH = OUTPUT_ROOT / "august-relative-proxy-result.json"


def relative(path: Path) -> str:
    return str(path.relative_to(REPOSITORY_ROOT)).replace("\\", "/")


def finite_metric_record(record: dict[str, Any]) -> bool:
    scalar_keys = (
        "actual_net_usd",
        "stressed_net_usd",
        "actual_closed_dd_pct",
        "stressed_closed_dd_pct",
        "actual_minimum_balance_usd",
        "stressed_minimum_balance_usd",
        "actual_gross_profit_usd",
        "actual_gross_loss_usd",
        "stressed_gross_profit_usd",
        "stressed_gross_loss_usd",
        "maximum_open_risk_fraction",
    )
    if not all(math.isfinite(float(record[key])) for key in scalar_keys):
        return False
    for component in record["components"]:
        if not math.isfinite(float(component["actual_net_usd"])):
            return False
        if not math.isfinite(float(component["stressed_net_usd"])):
            return False
    return all(
        math.isfinite(float(value))
        for value in record["epoch_actual_net_usd"]
        + record["epoch_stressed_net_usd"]
    )


def anchor_record(
    observed: dict[str, Any], reference: dict[str, Any], gate: dict[str, Any]
) -> dict[str, Any]:
    actual_denominator = max(abs(float(reference["actual_net_usd"])), 5.0)
    stressed_denominator = max(abs(float(reference["stressed_net_usd"])), 5.0)
    close_denominator = max(abs(float(reference["closed_lifecycles"])), 5.0)
    errors = {
        "actual_net_relative_error": abs(
            float(observed["actual_net_usd"]) - float(reference["actual_net_usd"])
        )
        / actual_denominator,
        "stressed_net_relative_error": abs(
            float(observed["stressed_net_usd"])
            - float(reference["stressed_net_usd"])
        )
        / stressed_denominator,
        "closed_lifecycle_relative_error": abs(
            int(observed["closed_lifecycles"])
            - int(reference["closed_lifecycles"])
        )
        / close_denominator,
    }
    checks = {
        "actual_net": errors["actual_net_relative_error"]
        <= float(gate["actual_net_relative_tolerance"]),
        "stressed_net": errors["stressed_net_relative_error"]
        <= float(gate["stressed_net_relative_tolerance"]),
        "closed_lifecycles": errors["closed_lifecycle_relative_error"]
        <= float(gate["closed_lifecycle_relative_tolerance"]),
    }
    return {
        "observed_proxy": observed,
        "native_reference": reference,
        "relative_errors": errors,
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> int:
    started = time.perf_counter()
    if RESULT_PATH.exists():
        raise RuntimeError("frozen August relative proxy result already exists")
    contract = engine.load_contract()
    if contract["campaign"] != FAMILY:
        raise RuntimeError("campaign identity mismatch")
    receipt_path = MARKET_ROOT / "acquisition-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    basis = engine.build_basis(contract)
    baseline_levels = engine.baseline_level_row(contract)
    parameters, point_ids, point_payloads = engine.resolve_points(
        baseline_levels[None, :], contract
    )
    multipliers = np.asarray(
        contract["spread_cost_calibration"]["multipliers"], dtype=np.float64
    )
    epochs = [
        ("2026-08-01T00:00:00", "2026-08-08T00:00:00"),
        ("2026-08-08T00:00:00", "2026-08-15T00:00:00"),
        ("2026-08-15T00:00:00", "2026-08-22T00:00:00"),
        ("2026-08-22T00:00:00", "2026-08-29T00:00:00"),
    ]
    result = engine.run_period(
        contract,
        basis,
        parameters,
        baseline_levels[None, :],
        "2026-08-01T00:00:00",
        "2026-08-29T00:00:00",
        epochs,
        multipliers,
    )
    control = engine.metric_record(result, 0)
    candidate = engine.metric_record(result, 1)
    native_reference = contract["paired_contracts"][1]["august_native_reference"]
    anchor = anchor_record(candidate, native_reference, contract["anchor_gate"])

    candidate_positive_components = [
        item
        for item in candidate["components"][:5]
        if float(item["stressed_net_usd"]) > 0.0
    ]
    largest_positive_component_share = (
        max(float(item["stressed_net_usd"]) for item in candidate_positive_components)
        / float(candidate["stressed_net_usd"])
        if candidate_positive_components and float(candidate["stressed_net_usd"]) > 0.0
        else None
    )
    weeks_not_worse = sum(
        float(candidate_value) >= float(control_value)
        for candidate_value, control_value in zip(
            candidate["epoch_stressed_net_usd"],
            control["epoch_stressed_net_usd"],
            strict=True,
        )
    )
    control_pf = control["stressed_profit_factor"]
    candidate_pf = candidate["stressed_profit_factor"]
    complete = finite_metric_record(control) and finite_metric_record(candidate)
    survival = all(
        float(record[key]) > 0.0
        for record in (control, candidate)
        for key in ("actual_minimum_balance_usd", "stressed_minimum_balance_usd")
    )
    actual_uplift = float(candidate["actual_net_usd"]) - float(
        control["actual_net_usd"]
    )
    stressed_uplift = float(candidate["stressed_net_usd"]) - float(
        control["stressed_net_usd"]
    )
    stressed_dd_excess = float(candidate["stressed_closed_dd_pct"]) - float(
        control["stressed_closed_dd_pct"]
    )
    nominal = contract["relative_judgment"]["nominal_clue_checks"]
    checks = {
        "candidate_stressed_net_positive": float(candidate["stressed_net_usd"]) > 0.0,
        "candidate_stressed_uplift_vs_control": stressed_uplift
        >= float(nominal["candidate_stressed_uplift_vs_control_usd_at_least"]),
        "candidate_stressed_profit_factor_above_control": (
            candidate_pf is not None
            and control_pf is not None
            and float(candidate_pf) > float(control_pf)
        ),
        "candidate_stressed_closed_dd_excess_vs_control": stressed_dd_excess
        <= float(
            nominal[
                "candidate_stressed_closed_dd_excess_vs_control_at_most_percentage_points"
            ]
        ),
        "candidate_positive_active_components": len(candidate_positive_components)
        >= int(nominal["candidate_positive_active_components_at_least"]),
        "candidate_weeks_not_worse_than_control": weeks_not_worse
        >= int(nominal["candidate_weeks_not_worse_than_control_at_least"]),
        "candidate_component_concentration": (
            largest_positive_component_share is not None
            and largest_positive_component_share
            <= float(
                nominal[
                    "largest_positive_component_share_of_candidate_stressed_net_at_most"
                ]
            )
        ),
    }
    mandatory = anchor["passed"] and complete and survival
    core_keys = (
        "candidate_stressed_net_positive",
        "candidate_stressed_uplift_vs_control",
        "candidate_stressed_profit_factor_above_control",
    )
    contextual_keys = (
        "candidate_stressed_closed_dd_excess_vs_control",
        "candidate_positive_active_components",
        "candidate_weeks_not_worse_than_control",
        "candidate_component_concentration",
    )
    contextual_misses = [key for key in contextual_keys if not checks[key]]
    advance = (
        mandatory
        and all(checks[key] for key in core_keys)
        and len(contextual_misses) <= 1
    )

    if not anchor["passed"]:
        status = "CORRECTION_REQUIRED_AUGUST_NATIVE_ANCHOR_NO_OPTIMIZATION_VERDICT"
    elif not complete or not survival:
        status = "CORRECTION_REQUIRED_INCOMPLETE_OR_NONVIABLE_ECONOMICS"
    elif advance:
        status = "MEANINGFUL_FIXED_PAIR_AUGUST_RELATIVE_CLUE_ADVANCE_TO_PAIRED_MT5"
    else:
        status = "VALID_COMPLETE_NO_MEANINGFUL_FIXED_PAIR_AUGUST_RELATIVE_CLUE"

    payload = {
        "schema": "zeta-dd20-fixed-pair-august-relative-proxy-result-v1",
        "campaign": FAMILY,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "contract": {
            "path": relative(CONTRACT_PATH),
            "bytes": CONTRACT_PATH.stat().st_size,
            "sha256": engine.sha256(CONTRACT_PATH),
        },
        "engine": {
            "path": relative(engine.SCRIPT_PATH),
            "bytes": engine.SCRIPT_PATH.stat().st_size,
            "sha256": engine.sha256(engine.SCRIPT_PATH),
            "source_sha256": contract["source_contract"]["isolated_proxy_engine_copy"][
                "source_sha256"
            ],
        },
        "market": {
            "receipt_path": relative(receipt_path),
            "receipt_sha256": engine.sha256(receipt_path),
            "series_files": receipt["series_files"],
            "series_rows": receipt["series_rows"],
            "series_bytes": receipt["series_bytes"],
            "request_from_utc": receipt["request_from_utc"],
            "request_through_utc": receipt["request_through_utc"],
            "account_position_order_deal_queries": receipt[
                "account_position_order_deal_queries"
            ],
        },
        "design": {
            "formula_points": 1,
            "paired_contracts": ["LIVE_CONTROL", "FIXED_REPLACEMENT"],
            "parameter_risk_weight_search": False,
            "baseline_point_id": point_ids[0],
            "baseline_point": json.loads(point_payloads[0]),
            "period": ["2026-08-01T00:00:00", "2026-08-29T00:00:00"],
            "weekly_epochs": epochs,
            "events": int(result["event_count"][0]),
        },
        "candidate_native_anchor": anchor,
        "economics": {
            "LIVE_CONTROL": control,
            "FIXED_REPLACEMENT": candidate,
            "replacement_minus_control": {
                "actual_net_usd": actual_uplift,
                "stressed_net_usd": stressed_uplift,
                "stressed_closed_dd_percentage_points": stressed_dd_excess,
                "closed_lifecycles": int(candidate["closed_lifecycles"])
                - int(control["closed_lifecycles"]),
                "weekly_stressed_net_usd": [
                    float(candidate_value) - float(control_value)
                    for candidate_value, control_value in zip(
                        candidate["epoch_stressed_net_usd"],
                        control["epoch_stressed_net_usd"],
                        strict=True,
                    )
                ],
            },
        },
        "relative_judgment": {
            "complete_finite_economics": complete,
            "positive_balance_survival": survival,
            "mandatory_passed": mandatory,
            "nominal_checks": checks,
            "nominal_checks_passed": sum(checks.values()),
            "nominal_checks_total": len(checks),
            "contextual_misses": contextual_misses,
            "candidate_positive_active_components": len(candidate_positive_components),
            "candidate_weeks_not_worse_than_control": weeks_not_worse,
            "largest_positive_component_share_of_candidate_stressed_net": largest_positive_component_share,
            "practical_rule": contract["relative_judgment"]["practical_rule"],
            "practical_advance_to_paired_mt5": advance,
            "interpretation": (
                "The proxy opens no new formula, weight or risk candidate. It only decides whether the already fixed pair owns enough same-window relative economic separation to justify one binding adjacent MT5 pair."
            ),
        },
        "mt5": {
            "advance": advance,
            "role": contract["mt5_escalation"]["role"] if advance else None,
            "existing_candidate_anchor_is_not_reused_as_binding_pair": True,
        },
        "elapsed_seconds": time.perf_counter() - started,
        "authority": "Optimization proxy evidence only; no Live, Lab, release or broker-account authority",
    }
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    engine.atomic_json(RESULT_PATH, payload)
    print(
        json.dumps(
            {
                "campaign": FAMILY,
                "status": status,
                "anchor_passed": anchor["passed"],
                "stressed_uplift_usd": stressed_uplift,
                "advance_to_paired_mt5": advance,
                "result": relative(RESULT_PATH),
                "elapsed_seconds": payload["elapsed_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if anchor["passed"] and complete and survival else 2


if __name__ == "__main__":
    raise SystemExit(main())
