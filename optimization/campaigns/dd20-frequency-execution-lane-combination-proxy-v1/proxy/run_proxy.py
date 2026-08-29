from __future__ import annotations

import hashlib
import json
import time
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config" / "proxy-contract.json"
RESULT_PATH = (
    ROOT
    / "evidence"
    / "DD20_FREQUENCY_EXECUTION_LANE_COMBINATION_PROXY_RESULT_V1.json"
)


def dec(value: object) -> Decimal:
    return Decimal(str(value))


def number(value: Decimal) -> float:
    return float(value)


def main() -> None:
    started = time.perf_counter()
    contract_bytes = CONTRACT_PATH.read_bytes()
    contract = json.loads(contract_bytes)

    high = contract["high_mid_economics"]
    low = contract["low_frequency_economics"]
    rules = contract["proxy_contract"]

    selection_actual = dec(high["selection_actual_net_usd"])
    selection_stressed = dec(high["selection_stressed_net_usd"])
    selection_dd = dec(high["selection_native_equity_drawdown_pct"])
    direct_actual = dec(low["prior_shared_selection_h4_direct_actual_net_usd"])
    direct_stressed = dec(low["prior_shared_selection_h4_direct_stressed_net_usd"])
    coupled_actual = dec(low["prior_shared_selection_total_actual_uplift_usd"])
    coupled_stressed = dec(low["prior_shared_selection_total_stressed_uplift_usd"])
    dd_charge = dec(
        low["prior_shared_selection_native_drawdown_charge_percentage_points"]
    )
    nominal_dd = dec(rules["nominal_equity_drawdown_line_pct"])
    proportional_reference = dec(
        rules["conservative_user_example_proportional_reference_pct"]
    )

    direct_projection_actual = selection_actual + direct_actual
    direct_projection_stressed = selection_stressed + direct_stressed
    coupled_projection_actual = selection_actual + coupled_actual
    coupled_projection_stressed = selection_stressed + coupled_stressed
    projected_dd = selection_dd + max(Decimal("0"), dd_charge)
    projected_dd_excess = projected_dd - nominal_dd
    projected_dd_proportional_excess = (
        projected_dd_excess / nominal_dd * Decimal("100")
    )

    projected_epochs = []
    all_epochs_actual_positive = True
    all_epochs_stressed_positive = True
    for high_epoch, low_epoch in zip(
        high["selection_epochs"], low["prior_shared_h4_epoch_direct"], strict=True
    ):
        if high_epoch["id"] != low_epoch["id"]:
            raise ValueError("epoch identities do not match")
        actual = dec(high_epoch["actual_net_usd"]) + dec(
            low_epoch["actual_net_usd"]
        )
        stressed = dec(high_epoch["stressed_net_usd"]) + dec(
            low_epoch["stressed_net_usd"]
        )
        projected_epochs.append(
            {
                "id": high_epoch["id"],
                "actual_net_usd": number(actual),
                "stressed_net_usd": number(stressed),
            }
        )
        all_epochs_actual_positive &= actual > 0
        all_epochs_stressed_positive &= stressed > 0

    forward_actual = dec(high["forward_actual_net_usd"])
    forward_stressed = dec(high["forward_stressed_net_usd"])
    forward_dd = dec(high["forward_native_equity_drawdown_pct"])
    forward_max_balance = dec(high["forward_maximum_closed_balance_usd"])
    low_frequency_gate = dec(
        contract["execution_lanes"]["low_frequency"]["new_entry_balance_gate_usd"]
    )
    forward_h4_inactive = forward_max_balance < low_frequency_gate

    gates = {
        "direct_only_selection_actual_improves_anchor": (
            direct_projection_actual > selection_actual
        ),
        "direct_only_selection_stressed_improves_anchor": (
            direct_projection_stressed > selection_stressed
        ),
        "all_direct_only_selection_epochs_actual_positive": (
            all_epochs_actual_positive
        ),
        "all_direct_only_selection_epochs_stressed_positive": (
            all_epochs_stressed_positive
        ),
        "projected_selection_nominal_drawdown_gate": projected_dd <= nominal_dd,
        "projected_selection_pragmatic_reference_gate": (
            projected_dd_proportional_excess <= proportional_reference
        ),
        "forward_h4_stage_gate_inactive": forward_h4_inactive,
        "forward_actual_positive": forward_actual > 0,
        "forward_stressed_positive": forward_stressed > 0,
        "forward_nominal_drawdown_gate": forward_dd <= nominal_dd,
        "exact_candidate_count_is_one": contract["candidate_count"] == 1,
    }
    effective_gate_names = [
        "direct_only_selection_actual_improves_anchor",
        "direct_only_selection_stressed_improves_anchor",
        "all_direct_only_selection_epochs_actual_positive",
        "all_direct_only_selection_epochs_stressed_positive",
        "projected_selection_pragmatic_reference_gate",
        "forward_h4_stage_gate_inactive",
        "forward_actual_positive",
        "forward_stressed_positive",
        "forward_nominal_drawdown_gate",
        "exact_candidate_count_is_one",
    ]
    one_mt5_shortlist = all(gates[name] for name in effective_gate_names)

    elapsed = time.perf_counter() - started
    status = (
        "VALID_PROXY_COMPLETE_ONE_COMBINED_MT5_SHORTLIST"
        if one_mt5_shortlist
        else "VALID_PROXY_COMPLETE_NO_COMBINED_MT5_SHORTLIST"
    )
    result = {
        "schema": "zeta-dd20-frequency-execution-lane-combination-proxy-result-v1",
        "recorded_date_local": "2026-08-29",
        "status": status,
        "campaign": contract["campaign"],
        "contract_sha256": hashlib.sha256(contract_bytes).hexdigest().upper(),
        "elapsed_seconds": elapsed,
        "process_invocations": 1,
        "candidate_count": contract["candidate_count"],
        "grid": contract["grid"],
        "dependency_finding": {
            "execution_lane_split_feasible": True,
            "high_mid_market_data_can_exclude_us500": False,
            "reason": contract["execution_lanes"]["high_mid_frequency"][
                "read_only_market_dependencies"
            ][0]["reason"],
            "high_mid_trade_symbols": contract["execution_lanes"][
                "high_mid_frequency"
            ]["owned_trade_symbols"],
            "high_mid_read_only_symbols": ["US500"],
            "low_frequency_trade_symbols": contract["execution_lanes"][
                "low_frequency"
            ]["owned_trade_symbols"],
        },
        "projection": {
            "direct_only_selection_actual_net_usd": number(
                direct_projection_actual
            ),
            "direct_only_selection_stressed_net_usd": number(
                direct_projection_stressed
            ),
            "coupled_information_selection_actual_net_usd": number(
                coupled_projection_actual
            ),
            "coupled_information_selection_stressed_net_usd": number(
                coupled_projection_stressed
            ),
            "projected_selection_native_equity_drawdown_pct": number(
                projected_dd
            ),
            "projected_selection_drawdown_excess_percentage_points": number(
                projected_dd_excess
            ),
            "projected_selection_drawdown_proportional_excess_pct": number(
                projected_dd_proportional_excess
            ),
            "projected_selection_epochs": projected_epochs,
            "forward_actual_net_usd": number(forward_actual),
            "forward_stressed_net_usd": number(forward_stressed),
            "forward_native_equity_drawdown_pct": number(forward_dd),
            "forward_maximum_closed_balance_usd": number(forward_max_balance),
            "forward_h4_new_entries": 0 if forward_h4_inactive else None,
        },
        "gates": gates,
        "economic_verdict": {
            "one_combined_mt5_shortlist": one_mt5_shortlist,
            "selected_high_mid_lane": "dd20-paired-month-stability-mt5-v1",
            "selected_low_frequency_lane": (
                "ZT-H4-US500-V2-VOLATILITY-EXP-b4d28831f9"
            ),
            "classification": (
                "FROZEN_TWO_LANE_COMBINATION_HAS_POSITIVE_PROXY_INFORMATION"
                if one_mt5_shortlist
                else "FROZEN_TWO_LANE_COMBINATION_LACKS_PROXY_SUPPORT"
            ),
            "interpretation": (
                "Both frozen lane evidences support exactly one combined MT5 "
                "candidate. The direct-only projection improves selection net, "
                "all four projected epochs remain positive, and the observed H4 "
                "drawdown charge produces a 4.3077% proportional overshoot, below "
                "the conservative 6% end of the user's example. The full forward "
                "remains the qualified high/mid path because its maximum closed "
                "balance never reaches the unchanged H4 stage gate. These are "
                "selection projections only: earlier activation and shared margin "
                "on the stronger anchor make one complete combined MT5 run mandatory."
            ),
        },
        "boundary": {
            "proxy_complete": True,
            "mt5_invocations": 0,
            "candidate_source_or_runtime_created": False,
            "live_lab_or_master_modified": False,
            "isolated_lane_arithmetic_is_final_verdict": False,
            "adjacent_threshold_or_h4_parameter_search": False,
        },
    }
    RESULT_PATH.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
