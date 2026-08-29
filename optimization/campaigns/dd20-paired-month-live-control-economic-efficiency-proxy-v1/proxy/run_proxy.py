#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any


CONFIG_SHA256 = "B7F8F3729EB7E9376E0BBD5F627E4A37B3BA9DBE0A92590BCF99D7902EF7B8C1"
SCRIPT_PATH = Path(__file__).resolve()
FAMILY_ROOT = SCRIPT_PATH.parents[1]
REPOSITORY_ROOT = SCRIPT_PATH.parents[4]
CONFIG_PATH = FAMILY_ROOT / "config" / "contract.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def finite(value: Any, label: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise RuntimeError(f"non-finite {label}")
    return parsed


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root is not an object: {path}")
    return value


def load_contract() -> dict[str, Any]:
    if CONFIG_PATH.stat().st_size != 4999 or sha256(CONFIG_PATH) != CONFIG_SHA256:
        raise RuntimeError("frozen config pin mismatch")
    return load_json(CONFIG_PATH)


def load_inputs(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    manifest_lines: list[str] = []
    total_bytes = 0
    for pin in contract["inputs"]:
        name = str(pin["name"])
        path = REPOSITORY_ROOT / str(pin["path"])
        actual_bytes = path.stat().st_size
        actual_sha = sha256(path)
        if actual_bytes != int(pin["bytes"]) or actual_sha != str(pin["sha256"]):
            raise RuntimeError(f"input pin mismatch: {name}")
        loaded[name] = load_json(path)
        total_bytes += actual_bytes
        manifest_lines.append(f"{name}|{actual_bytes}|{actual_sha}\n")
    manifest = hashlib.sha256("".join(manifest_lines).encode("utf-8")).hexdigest().upper()
    if len(loaded) != int(contract["input_files"]):
        raise RuntimeError("input file count mismatch")
    if total_bytes != int(contract["input_bytes"]):
        raise RuntimeError("input byte total mismatch")
    if manifest != str(contract["input_manifest_sha256"]):
        raise RuntimeError("input manifest mismatch")
    loaded["_manifest"] = {"sha256": manifest, "bytes": total_bytes}
    return loaded


def ratio(numerator: float, denominator: float, label: str) -> float:
    if denominator <= 0.0:
        raise RuntimeError(f"nonpositive ratio denominator: {label}")
    return numerator / denominator


def rate(numerator: float, denominator: float, label: str) -> float:
    if denominator <= 0.0:
        raise RuntimeError(f"nonpositive rate denominator: {label}")
    return numerator / denominator


def control_row(rows: list[dict[str, Any]], pass_id: int) -> dict[str, Any]:
    matches = [row for row in rows if int(row["pass"]) == pass_id]
    if len(matches) != 1:
        raise RuntimeError(f"control pass {pass_id} is not unique")
    return matches[0]


def component_totals(rows: list[dict[str, Any]], candidate: bool) -> dict[str, Any]:
    close_key = "closed" if candidate else "closed_lifecycles"
    if not rows:
        raise RuntimeError("empty component rows")
    ids = [str(row["component"]) for row in rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate component identity")
    return {
        "components": len(rows),
        "closes": sum(int(row[close_key]) for row in rows),
        "actual_net_usd": sum(finite(row["actual_net_usd"], "component actual") for row in rows),
        "stressed_net_usd": sum(finite(row["stressed_net_usd"], "component stressed") for row in rows),
        "positive_actual_components": sum(finite(row["actual_net_usd"], "component actual") > 0.0 for row in rows),
        "positive_stressed_components": sum(finite(row["stressed_net_usd"], "component stressed") > 0.0 for row in rows),
    }


def policy_metrics(
    actual: float,
    stressed: float,
    closes: int,
    dd_pct: float,
    skips: int,
    stops: int,
) -> dict[str, Any]:
    if closes <= 0 or dd_pct <= 0.0 or skips < 0 or stops < 0:
        raise RuntimeError("invalid policy metric denominator or count")
    return {
        "actual_net_usd": actual,
        "stressed_net_usd": stressed,
        "closed_lifecycles": closes,
        "native_relative_equity_dd_pct": dd_pct,
        "risk_admission_skips": skips,
        "stop_loss_exits": stops,
        "actual_net_per_close_usd": actual / closes,
        "stressed_net_per_close_usd": stressed / closes,
        "actual_net_per_native_dd_point_usd": actual / dd_pct,
        "stressed_net_per_native_dd_point_usd": stressed / dd_pct,
        "risk_skip_rate": skips / (closes + skips),
        "stop_exit_rate": stops / closes,
    }


def main() -> None:
    started = time.perf_counter()
    contract = load_contract()
    inputs = load_inputs(contract)
    candidate = inputs["candidate-result.json"]
    control = inputs["live-control-result.json"]
    cost = inputs["cost-resilience-result.json"]

    fixed = contract["fixed_candidate"]
    candidate_identity = candidate["candidate"]
    if [finite(value, "candidate weight") for value in candidate_identity["component_exposure_multipliers"]] != [finite(value, "contract weight") for value in fixed["weights"]]:
        raise RuntimeError("candidate weight identity mismatch")
    if finite(candidate_identity["position_risk_fraction"], "candidate position risk") != finite(fixed["position_risk_fraction"], "contract position risk"):
        raise RuntimeError("candidate position risk mismatch")
    if finite(candidate_identity["aggregate_risk_fraction"], "candidate aggregate risk") != finite(fixed["aggregate_risk_fraction"], "contract aggregate risk"):
        raise RuntimeError("candidate aggregate risk mismatch")

    live = contract["active_live_control"]
    if finite(control["parent"]["position_risk_fraction"], "control position risk") != finite(live["position_risk_fraction"], "contract control position risk"):
        raise RuntimeError("control position risk mismatch")
    if finite(control["parent"]["aggregate_risk_fraction"], "control aggregate risk") != finite(live["aggregate_risk_fraction"], "contract control aggregate risk"):
        raise RuntimeError("control aggregate risk mismatch")

    selection_control = control_row(control["selection_matrix"], int(live["selection_pass"]))
    forward_control = control_row(control["forward_matrix"], int(live["selection_pass"]))
    selection_candidate = candidate["selection"]
    forward_candidate = candidate["forward"]
    if str(selection_candidate["interval"]) != str(contract["intervals"]["selection"]):
        raise RuntimeError("candidate selection interval mismatch")
    if str(forward_candidate["interval"]) != str(contract["intervals"]["forward"]):
        raise RuntimeError("candidate forward interval mismatch")
    if not bool(selection_candidate["valid_economic_output"]) or not bool(forward_candidate["valid_economic_output"]):
        raise RuntimeError("candidate economic output is not valid")

    candidate_selection_components = component_totals(selection_candidate["components"], True)
    active_candidate_rows = [row for row in selection_candidate["components"] if int(row["closed"]) > 0]
    active_candidate_components = component_totals(active_candidate_rows, True)
    control_component_rows = control["component_economics"]["selection_parent_0.04_0.12"]
    control_components = component_totals(control_component_rows, False)
    passive_id = str(fixed["disabled_component"])
    control_active_five_rows = [row for row in control_component_rows if str(row["component"]) != passive_id]
    control_active_five = component_totals(control_active_five_rows, False)

    candidate_money_tolerance = 0.005 * len(selection_candidate["components"]) + 1.0e-7
    control_money_tolerance = 0.005 * len(control_component_rows) + 1.0e-7
    for label, value, anchor, tolerance in (
        ("candidate selection closes", candidate_selection_components["closes"], int(selection_candidate["closed_lifecycles"]), 0),
        ("candidate selection actual", candidate_selection_components["actual_net_usd"], finite(selection_candidate["actual_net_usd"], "candidate selection actual"), candidate_money_tolerance),
        ("candidate selection stressed", candidate_selection_components["stressed_net_usd"], finite(selection_candidate["stressed_2x_cost_net_usd"], "candidate selection stressed"), candidate_money_tolerance),
        ("control selection closes", control_components["closes"], int(selection_control["closed_lifecycles"]), 0),
        ("control selection actual", control_components["actual_net_usd"], finite(selection_control["actual_net_usd"], "control selection actual"), control_money_tolerance),
        ("control selection stressed", control_components["stressed_net_usd"], finite(selection_control["stressed_net_usd"], "control selection stressed"), control_money_tolerance),
    ):
        if abs(value - anchor) > tolerance:
            raise RuntimeError(f"component anchor mismatch: {label}")

    selection_candidate_metrics = policy_metrics(
        finite(selection_candidate["actual_net_usd"], "candidate selection actual"),
        finite(selection_candidate["stressed_2x_cost_net_usd"], "candidate selection stressed"),
        int(selection_candidate["closed_lifecycles"]),
        finite(selection_candidate["mt5_equity_drawdown_relative_pct"], "candidate selection dd"),
        int(selection_candidate["risk_admission_skips"]),
        int(selection_candidate["stop_loss_exits"]),
    )
    selection_control_metrics = policy_metrics(
        finite(selection_control["actual_net_usd"], "control selection actual"),
        finite(selection_control["stressed_net_usd"], "control selection stressed"),
        int(selection_control["closed_lifecycles"]),
        finite(selection_control["equity_drawdown_pct"], "control selection dd"),
        int(selection_control["risk_admission_skips"]),
        int(selection_control["stop_exits"]),
    )
    forward_candidate_metrics = policy_metrics(
        finite(forward_candidate["actual_net_usd"], "candidate forward actual"),
        finite(forward_candidate["stressed_2x_cost_net_usd"], "candidate forward stressed"),
        int(forward_candidate["closed_lifecycles"]),
        finite(forward_candidate["mt5_equity_drawdown_maximal_and_relative_pct"], "candidate forward dd"),
        int(forward_candidate["risk_admission_skips"]),
        int(forward_candidate["stop_loss_exits"]),
    )
    forward_control_metrics = policy_metrics(
        finite(forward_control["actual_net_usd"], "control forward actual"),
        finite(forward_control["stressed_net_usd"], "control forward stressed"),
        int(forward_control["closed_lifecycles"]),
        finite(forward_control["equity_drawdown_pct"], "control forward dd"),
        int(forward_control["risk_admission_skips"]),
        int(forward_control["stop_exits"]),
    )

    selection_comparison = {
        "candidate_minus_control_actual_usd": selection_candidate_metrics["actual_net_usd"] - selection_control_metrics["actual_net_usd"],
        "candidate_minus_control_stressed_usd": selection_candidate_metrics["stressed_net_usd"] - selection_control_metrics["stressed_net_usd"],
        "candidate_to_control_actual_net_ratio": ratio(selection_candidate_metrics["actual_net_usd"], selection_control_metrics["actual_net_usd"], "selection actual"),
        "candidate_to_control_stressed_net_ratio": ratio(selection_candidate_metrics["stressed_net_usd"], selection_control_metrics["stressed_net_usd"], "selection stressed"),
        "turnover_retention": selection_candidate_metrics["closed_lifecycles"] / selection_control_metrics["closed_lifecycles"],
        "active_five_turnover_retention": selection_candidate_metrics["closed_lifecycles"] / control_active_five["closes"],
        "candidate_to_control_actual_per_close_ratio": ratio(selection_candidate_metrics["actual_net_per_close_usd"], selection_control_metrics["actual_net_per_close_usd"], "selection actual per close"),
        "candidate_to_control_stressed_per_close_ratio": ratio(selection_candidate_metrics["stressed_net_per_close_usd"], selection_control_metrics["stressed_net_per_close_usd"], "selection stressed per close"),
        "candidate_to_control_actual_per_dd_point_ratio": ratio(selection_candidate_metrics["actual_net_per_native_dd_point_usd"], selection_control_metrics["actual_net_per_native_dd_point_usd"], "selection actual per dd"),
        "candidate_to_control_stressed_per_dd_point_ratio": ratio(selection_candidate_metrics["stressed_net_per_native_dd_point_usd"], selection_control_metrics["stressed_net_per_native_dd_point_usd"], "selection stressed per dd"),
        "native_dd_percentage_point_increase": selection_candidate_metrics["native_relative_equity_dd_pct"] - selection_control_metrics["native_relative_equity_dd_pct"],
        "native_dd_ratio": ratio(selection_candidate_metrics["native_relative_equity_dd_pct"], selection_control_metrics["native_relative_equity_dd_pct"], "selection dd"),
        "risk_skip_rate_percentage_point_delta": (selection_candidate_metrics["risk_skip_rate"] - selection_control_metrics["risk_skip_rate"]) * 100.0,
        "stop_exit_rate_percentage_point_delta": (selection_candidate_metrics["stop_exit_rate"] - selection_control_metrics["stop_exit_rate"]) * 100.0,
    }
    forward_comparison = {
        "candidate_minus_control_actual_usd": forward_candidate_metrics["actual_net_usd"] - forward_control_metrics["actual_net_usd"],
        "candidate_minus_control_stressed_usd": forward_candidate_metrics["stressed_net_usd"] - forward_control_metrics["stressed_net_usd"],
        "turnover_retention": forward_candidate_metrics["closed_lifecycles"] / forward_control_metrics["closed_lifecycles"],
        "candidate_minus_control_actual_per_close_usd": forward_candidate_metrics["actual_net_per_close_usd"] - forward_control_metrics["actual_net_per_close_usd"],
        "candidate_minus_control_stressed_per_close_usd": forward_candidate_metrics["stressed_net_per_close_usd"] - forward_control_metrics["stressed_net_per_close_usd"],
        "native_dd_percentage_point_increase": forward_candidate_metrics["native_relative_equity_dd_pct"] - forward_control_metrics["native_relative_equity_dd_pct"],
        "risk_skip_rate_percentage_point_delta": (forward_candidate_metrics["risk_skip_rate"] - forward_control_metrics["risk_skip_rate"]) * 100.0,
        "stop_exit_rate_percentage_point_delta": (forward_candidate_metrics["stop_exit_rate"] - forward_control_metrics["stop_exit_rate"]) * 100.0,
        "control_net_ratios_reported": False,
        "reason": "The exact control forward actual and stressed nets are nonpositive, so ratios would be economically misleading.",
    }

    cost_verdict = str(cost["verdict"])
    cost_context = {
        "verdict": cost_verdict,
        "selection_candidate_to_control_4x_net_ratio": finite(cost["four_x_comparison"]["selection_candidate_to_active_live_control_net_ratio"], "4x ratio"),
        "forward_candidate_minus_control_4x_usd": finite(cost["four_x_comparison"]["forward_candidate_minus_active_live_control_usd"], "4x forward delta"),
    }

    gates = {
        "selection_actual_net_strictly_higher": selection_candidate_metrics["actual_net_usd"] > selection_control_metrics["actual_net_usd"],
        "selection_stressed_net_strictly_higher": selection_candidate_metrics["stressed_net_usd"] > selection_control_metrics["stressed_net_usd"],
        "selection_actual_per_close_strictly_higher": selection_candidate_metrics["actual_net_per_close_usd"] > selection_control_metrics["actual_net_per_close_usd"],
        "selection_stressed_per_close_strictly_higher": selection_candidate_metrics["stressed_net_per_close_usd"] > selection_control_metrics["stressed_net_per_close_usd"],
        "selection_actual_per_dd_point_strictly_higher": selection_candidate_metrics["actual_net_per_native_dd_point_usd"] > selection_control_metrics["actual_net_per_native_dd_point_usd"],
        "selection_stressed_per_dd_point_strictly_higher": selection_candidate_metrics["stressed_net_per_native_dd_point_usd"] > selection_control_metrics["stressed_net_per_native_dd_point_usd"],
        "candidate_five_active_components_positive_actual_and_stressed": active_candidate_components["components"] == int(fixed["active_components"]) and active_candidate_components["positive_actual_components"] == int(fixed["active_components"]) and active_candidate_components["positive_stressed_components"] == int(fixed["active_components"]),
        "control_six_components_positive_actual_and_stressed": control_components["components"] == int(live["active_components"]) and control_components["positive_actual_components"] == int(live["active_components"]) and control_components["positive_stressed_components"] == int(live["active_components"]),
        "candidate_forward_actual_positive_and_strictly_higher": forward_candidate_metrics["actual_net_usd"] > 0.0 and forward_candidate_metrics["actual_net_usd"] > forward_control_metrics["actual_net_usd"],
        "candidate_forward_stressed_positive_and_strictly_higher": forward_candidate_metrics["stressed_net_usd"] > 0.0 and forward_candidate_metrics["stressed_net_usd"] > forward_control_metrics["stressed_net_usd"],
        "candidate_forward_actual_per_close_strictly_higher": forward_candidate_metrics["actual_net_per_close_usd"] > forward_control_metrics["actual_net_per_close_usd"],
        "candidate_forward_stressed_per_close_strictly_higher": forward_candidate_metrics["stressed_net_per_close_usd"] > forward_control_metrics["stressed_net_per_close_usd"],
        "candidate_forward_native_dd_below_20_percent": forward_candidate_metrics["native_relative_equity_dd_pct"] < 20.0,
        "candidate_selection_exact_pragmatic_context_retained": abs(selection_candidate_metrics["native_relative_equity_dd_pct"] - 20.256887565152653) <= 1.0e-9,
        "prior_4x_cost_pass_retained": cost_verdict == "PASS_FIXED_DEVELOPMENT_CANDIDATE_COST_RESILIENCE_VS_ACTIVE_LIVE_CONTROL" and cost_context["selection_candidate_to_control_4x_net_ratio"] > 1.0 and cost_context["forward_candidate_minus_control_4x_usd"] > 0.0,
    }
    all_passed = all(gates.values())
    verdict = contract["verdicts"]["pass"] if all_passed else contract["verdicts"]["nonconfirmation"]

    output = {
        "schema": "zeta-dd20-paired-month-live-control-economic-efficiency-formal-result-v1",
        "recorded_at_local": "2026-08-30",
        "status": "VALID_COMPLETE",
        "campaign": str(contract["campaign"]),
        "integrity": {
            "passed": True,
            "config_bytes": CONFIG_PATH.stat().st_size,
            "config_sha256": sha256(CONFIG_PATH),
            "input_files": int(contract["input_files"]),
            "input_bytes": int(inputs["_manifest"]["bytes"]),
            "input_manifest_sha256": str(inputs["_manifest"]["sha256"]),
            "candidate_component_totals_match": True,
            "control_component_totals_match": True,
        },
        "selection": {
            "candidate": selection_candidate_metrics,
            "active_live_control": selection_control_metrics,
            "comparison": selection_comparison,
            "candidate_active_component_breadth": active_candidate_components,
            "control_component_breadth": control_components,
            "control_active_five_excluding_passive": control_active_five,
        },
        "forward": {
            "candidate": forward_candidate_metrics,
            "active_live_control": forward_control_metrics,
            "comparison": forward_comparison,
        },
        "cost_resilience_context": cost_context,
        "gate_application": {**gates, "all_gates_passed": all_passed},
        "verdict": verdict,
        "economic_boundary": {
            "candidate_selection_nominal_20_percent_gate_passed": False,
            "candidate_selection_nominal_miss_percentage_points": selection_candidate_metrics["native_relative_equity_dd_pct"] - 20.0,
            "candidate_selection_pragmatic_qualification_rejudged_here": False,
            "candidate_has_lower_turnover_than_control": selection_comparison["turnover_retention"] < 1.0 and forward_comparison["turnover_retention"] < 1.0,
            "candidate_has_higher_native_dd_than_control": selection_comparison["native_dd_percentage_point_increase"] > 0.0 and forward_comparison["native_dd_percentage_point_increase"] > 0.0,
            "fixed_candidate_changed_or_retuned": False,
            "new_mt5_shortlist": False,
            "live_authority": False,
        },
        "execution": {
            "formal_source_free_processes": 1,
            "complete_fixed_policy_comparisons": 1,
            "economic_metric_reruns": 0,
            "mql_or_settings_changes": 0,
            "compile_or_tester_paths": 0,
            "orders": 0,
            "elapsed_seconds": time.perf_counter() - started,
        },
    }
    output_path = REPOSITORY_ROOT / str(contract["output"]["path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(output, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(json.dumps({"output": str(output_path), "verdict": verdict}))


if __name__ == "__main__":
    main()
