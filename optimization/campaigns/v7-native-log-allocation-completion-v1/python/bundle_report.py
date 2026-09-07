"""Summarize the whole frozen native allocation bundle, without selecting a rescue."""
from pathlib import Path
import json
import math

from native_run import EVIDENCE, ROLES, binding, save, utc


def compare(control, candidate):
    dd = candidate["native_relative_equity_dd_pct"]
    control_dd = control["native_relative_equity_dd_pct"]
    tolerance = min(control_dd + 1.5, control_dd * 1.10)
    growth_gates = {
        "actual_terminal_wealth_strictly_higher": candidate["actual_terminal_wealth"] > control["actual_terminal_wealth"],
        "actual_log_growth_strictly_higher": candidate["actual_log_growth"] is not None and
        candidate["actual_log_growth"] > control["actual_log_growth"],
        "conservative_net_at_least_five_percent_higher": candidate["conservative_stressed_net"] >=
        control["conservative_stressed_net"] * 1.05,
        "conservative_terminal_wealth_strictly_higher": candidate["conservative_terminal_wealth"] >
        control["conservative_terminal_wealth"],
        "robust_recovery_strictly_higher": candidate["robust_recovery"] > control["robust_recovery"],
        "each_actual_and_conservative_closed_and_marked_half_positive":
        all(value > 0 for epoch in candidate["epochs"].values() for value in epoch.values()),
    }
    nominal = dd <= control_dd
    all_other = all(growth_gates.values())
    result = {
        "control": control["tag"], "candidate": candidate["tag"],
        "growth_and_temporal_gates": growth_gates,
        "native_dd_nominal_pass": nominal, "native_dd_effective_ceiling_pct": tolerance,
        "native_dd_within_effective_ceiling": dd <= tolerance,
        "all_other_gates_pass": all_other,
        "eligible_without_dd_tolerance": all_other and nominal,
        "requires_explicit_root_dd_judgment": all_other and not nominal and dd <= tolerance,
        "rejected_by_fixed_mathematical_gates": not all_other or dd > tolerance,
        "actual_net_improvement_pct": 100 * (candidate["actual_net"] / control["actual_net"] - 1),
        "actual_wealth_improvement_pct": 100 * (candidate["actual_terminal_wealth"] / control["actual_terminal_wealth"] - 1),
        "conservative_net_improvement_pct": 100 * (candidate["conservative_stressed_net"] /
                                                     control["conservative_stressed_net"] - 1),
        "conservative_wealth_improvement_pct": 100 * (candidate["conservative_terminal_wealth"] /
                                                        control["conservative_terminal_wealth"] - 1),
        "native_dd_change_percentage_points": dd - control_dd,
        "robust_recovery_improvement_pct": 100 * (candidate["robust_recovery"] / control["robust_recovery"] - 1),
        "actual_reinvestment_births": candidate["actual_reinvestment_births"],
        "root_dd_tolerance_judgment": None,
    }
    return result


def produce():
    target = EVIDENCE / "NATIVE_SELECTION_COMPARISON_V1.json"
    if target.exists():
        raise ValueError("Preserve the existing whole-bundle report")
    sources = [EVIDENCE / (tag + "-economics.json") for tag in ROLES]
    values = [json.loads(p.read_text(encoding="utf-8")) for p in sources]
    if any(v["status"] != "COMPLETE_VALID_FULL2025_NATIVE_ECONOMICS" for v in values):
        raise ValueError("Every ordered native role must be complete and valid before bundle interpretation")
    for candidate in values[1:]:
        if candidate["contract_fingerprints"] != values[0]["contract_fingerprints"]:
            raise ValueError("Mid-matrix contract/financing drift requires a complete new matrix")
        if candidate["tick_coverage"] != values[0]["tick_coverage"]:
            raise ValueError("The complete matrix did not exercise identical all-symbol native tick coverage")
    comparisons = [compare(values[0], values[1]), compare(values[2], values[3])]
    result = {
        "utc": utc(), "status": "COMPLETE_FIXED_NATIVE_BUNDLE_AWAITING_ROOT_JUDGMENT",
        "sources": [binding(p) for p in sources], "producer": binding(Path(__file__).resolve()),
        "order": list(ROLES), "all_four_real_tick_paths_complete": True,
        "all_contracts_swaps_and_native_tick_coverage_equal": True,
        "comparisons": comparisons,
        "finalist_rule": "At most one fully eligible unchanged role, highest conservative stressed net; exact tie online. "
        "Any DD tolerance requires explicit root judgment and every stronger gate. Complete remaining continuous "
        "confirmation storage must be funded before an eligible finalist opens that fresh paired path.",
        "no_mathematical_passers": all(v["rejected_by_fixed_mathematical_gates"] for v in comparisons),
        "whole_bundle_closed": False, "selected_finalist": None, "candidate_2026_values_opened": False,
        "known_selection_limitation": "Prior V7 research has already consumed 2025; it is not a pristine holdout.",
        "actual_compounding_limit": "Allocation weights can increase lots while the original staircase remains1. "
        "Full native quantity/staircase evidence determines reinvestment, never curve shape alone.",
    }
    save(target, result)
    return result


if __name__ == "__main__":
    result = produce()
    print(json.dumps({"status": result["status"], "comparisons": result["comparisons"],
                      "no_mathematical_passers": result["no_mathematical_passers"]}))
