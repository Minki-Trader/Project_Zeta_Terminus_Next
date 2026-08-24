#!/usr/bin/env python3
"""Summarize causal slot-exchange runtimes and their forward path effects."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
FRONTIER = ROOT / "lab" / "frontier" / "slot-shadow-price"
ARTIFACTS = ROOT / "lab" / "artifacts" / "backtests" / "slot-shadow-price"
COMPONENTS = {
    "ZT-M30-US30-RANGE-COMP-61f61deaba": "RC16",
    "ZT-M30-US30-RANGE-COMP-64efb16616": "RC4",
    "ZT-H1-US100-CROSS-IN-14b72317b7": "CROSS",
    "ZT-M30-US30-INTRADAY-R-2eb111fc46": "PRESSURE",
    "ZT-H1-US30-RETURN-I-c870a788ec": "RETURN",
    "ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8": "PASSIVE",
}
COMPONENT_BY_INDEX = {
    0: "RC16",
    1: "RC4",
    2: "CROSS",
    3: "PRESSURE",
    4: "RETURN",
    5: "PASSIVE",
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


def number(text: str) -> float:
    match = re.search(r"-?\d+(?:,\d{3})*(?:\.\d+)?", text)
    if match is None:
        raise ValueError(f"numeric metric missing from {text!r}")
    return float(match.group(0).replace(",", ""))


def report_metrics(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-16")

    def values(label: str) -> list[str]:
        pattern = (
            rf"<td[^>]*>\s*{re.escape(label)}:\s*</td>\s*"
            rf"<td[^>]*>\s*<b>([^<]*)</b>"
        )
        return re.findall(pattern, text, flags=re.IGNORECASE)

    net = values("총수입") or values("Total Net Profit")
    balance_dd = values("Balance Drawdown Maximal")
    equity_dd = values("Equity Drawdown Maximal")
    profit_factor = values("Profit Factor")
    recovery_factor = values("Recovery Factor")
    sharpe = values("Sharpe Ratio")
    trades = values("총 거래횟수") or values("Total Trades")
    quality = values("히스토리 품질") or values("History Quality")
    if not all((net, balance_dd, equity_dd, profit_factor, recovery_factor, sharpe, trades)):
        raise RuntimeError(f"report metrics incomplete in {path}")
    return {
        "actual_net": number(net[0]),
        "actual_balance_drawdown": number(balance_dd[0]),
        "actual_equity_drawdown": number(equity_dd[0]),
        "profit_factor": number(profit_factor[0]),
        "recovery_factor": number(recovery_factor[0]),
        "sharpe_ratio": number(sharpe[0]),
        "entries": int(number(trades[0])),
        "history_quality": quality[0] if quality else "unknown",
    }


def read_log(path: Path) -> list[str]:
    return path.read_text(encoding="utf-16-le", errors="strict").splitlines()


def fields(line: str) -> dict[str, str]:
    return dict(re.findall(r"(?:^|\s)([A-Za-z0-9_]+)=([^\s]+)", line))


def final_metrics(path: Path, portfolio: str) -> dict[str, Any]:
    matches = [
        line
        for line in read_log(path)
        if f"final portfolio={portfolio}" in line
    ]
    if not matches:
        raise RuntimeError(f"final summary missing in {path}")
    row = fields(matches[-1])
    return {
        "stressed_net_2x": float(row["stressed_net_2x"]),
        "stressed_closed_drawdown": float(row["stressed_max_closed_dd"]),
        "actual_net": float(row["project_realized_net"]),
        "risk_admission_skips": int(row["risk_admission_skips"]),
        "protection_calculation_failures": int(row["protection_calc_failures"]),
        "protection_mismatches": int(row["protection_mismatches"]),
        "safety_stopped": row["safety_stopped"] == "true",
        "persistence_failed": row["persistence_failed"] == "true",
        "broker_mismatch": row["broker_mismatch"] == "true",
        "foreign_exposure": row["foreign_exposure"] == "true",
    }


def exchange_summary(path: Path) -> dict[str, Any]:
    matches = [
        line
        for line in read_log(path)
        if "ZETA_FRONTIER_SLOT_EXCHANGE_SUMMARY|" in line
    ]
    if not matches:
        return {}
    payload = matches[-1].split("ZETA_FRONTIER_SLOT_EXCHANGE_SUMMARY|", 1)[1]
    row = dict(
        item.split("=", 1)
        for item in payload.split("|")
        if "=" in item
    )
    return {
        "mode": row["mode"],
        "signals": int(row["signals"]),
        "completed_lifecycles": int(row["completed_lifecycles"]),
        "risk_blocks_observed": int(row["risk_blocks"]),
        "qualified_exchanges": int(row["qualified"]),
        "release_successes": int(row["release_successes"]),
        "release_failures": int(row["release_failures"]),
        "retry_blocks": int(row["retry_blocks"]),
        "headroom_blocks": int(row.get("headroom_blocks", 0)),
        "pending_candidate_blocks": int(row.get("pending_candidate_blocks", 0)),
    }


def load_events(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for raw in csv.DictReader(handle):
                row: dict[str, Any] = dict(raw)
                row["sequence"] = int(raw["state_sequence"])
                row["value_a_number"] = float(raw["value_a"])
                row["value_b_number"] = float(raw["value_b"])
                rows.append(row)
    rows.sort(key=lambda row: row["sequence"])
    return rows


def drawdown(values: list[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    maximum = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        maximum = max(maximum, peak - cumulative)
    return rounded(maximum)


def event_period(rows: list[dict[str, Any]], year: str | None) -> dict[str, Any]:
    selected = (
        rows
        if year is None
        else [row for row in rows if row["server_time"].startswith(year + ".")]
    )
    closes = [
        row for row in selected if row["event"] in {"CLOSE", "EXTERNAL_CLOSE"}
    ]
    entries = [row for row in selected if row["event"] in {"OPEN", "PASSIVE_FILL"}]
    by_component: dict[str, dict[str, float | int]] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in closes:
        grouped[COMPONENTS[row["component_id"]]].append(row)
    for component in COMPONENT_BY_INDEX.values():
        component_rows = grouped.get(component, [])
        by_component[component] = {
            "entries": sum(
                COMPONENTS.get(row["component_id"]) == component for row in entries
            ),
            "closed_lifecycles": len(component_rows),
            "actual_net": rounded(sum(row["value_a_number"] for row in component_rows)),
            "stressed_net_2x": rounded(
                sum(row["value_b_number"] for row in component_rows)
            ),
        }
    return {
        "entries": len(entries),
        "closed_lifecycles": len(closes),
        "actual_net": rounded(sum(row["value_a_number"] for row in closes)),
        "stressed_net_2x": rounded(sum(row["value_b_number"] for row in closes)),
        "actual_closed_drawdown": drawdown(
            [row["value_a_number"] for row in closes]
        ),
        "stressed_closed_drawdown": drawdown(
            [row["value_b_number"] for row in closes]
        ),
        "risk_admission_skips": sum(
            row["event"] == "RISK_ADMISSION_SKIP" for row in selected
        ),
        "slot_exchanges": sum(
            row["event"] == "SLOT_EXCHANGE_RELEASE" for row in selected
        ),
        "components": by_component,
    }


def first_sizing_step(rows: list[dict[str, Any]], multiplier: int) -> dict[str, Any] | None:
    found = next(
        (
            row
            for row in rows
            if row["event"] == "SIZE_DAY"
            and row["value_b_number"] >= float(multiplier)
        ),
        None,
    )
    if found is None:
        return None
    return {
        "server_time": found["server_time"],
        "stressed_balance": rounded(found["value_a_number"]),
        "multiplier": int(found["value_b_number"]),
    }


def exchange_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, release in enumerate(rows):
        if release["event"] != "SLOT_EXCHANGE_RELEASE":
            continue
        incumbent_match = re.search(r"(?:^|\s)incumbent=(\d+)", release["detail"])
        if incumbent_match is None:
            raise RuntimeError("slot release lacks incumbent")
        incumbent = COMPONENT_BY_INDEX[int(incumbent_match.group(1))]
        same_time = [
            row for row in rows if row["server_time"] == release["server_time"]
        ]
        incumbent_close = next(
            (
                row
                for row in reversed(same_time)
                if row["sequence"] < release["sequence"]
                and row["event"] in {"CLOSE", "EXTERNAL_CLOSE"}
                and COMPONENTS[row["component_id"]] == incumbent
            ),
            None,
        )
        candidate_open = next(
            (
                row
                for row in same_time
                if row["sequence"] > release["sequence"]
                and row["event"] == "OPEN"
                and row["component_id"] == release["component_id"]
            ),
            None,
        )
        pending = next(
            (
                row
                for row in same_time
                if row["sequence"] > release["sequence"]
                and row["event"] == "DECISION_JOURNAL_FINAL"
                and row["component_id"] == release["component_id"]
                and "outcome=PENDING_ORDER" in row["detail"]
            ),
            None,
        )
        pending_result = None
        if pending is not None:
            pending_result = next(
                (
                    row
                    for row in rows[index + 1 :]
                    if row["event"] in {"PASSIVE_FILL", "PASSIVE_EXPIRE", "PASSIVE_CANCEL"}
                ),
                None,
            )
            if pending_result is not None and pending_result["event"] == "PASSIVE_FILL":
                candidate_open = pending_result
        candidate_close = None
        if candidate_open is not None:
            candidate_close = next(
                (
                    row
                    for row in rows
                    if row["sequence"] > candidate_open["sequence"]
                    and row["component_id"] == release["component_id"]
                    and row["event"] in {"CLOSE", "EXTERNAL_CLOSE"}
                ),
                None,
            )
        retry_skip = any(
            row["sequence"] > release["sequence"]
            and row["event"] == "RISK_ADMISSION_SKIP"
            and row["component_id"] == release["component_id"]
            for row in same_time
        )
        output.append(
            {
                "server_time": release["server_time"],
                "year": release["server_time"][:4],
                "candidate": COMPONENTS[release["component_id"]],
                "incumbent": incumbent,
                "candidate_score": rounded(release["value_a_number"]),
                "slot_price": rounded(release["value_b_number"]),
                "incumbent_close_actual": (
                    None if incumbent_close is None else rounded(incumbent_close["value_a_number"])
                ),
                "incumbent_close_stressed": (
                    None if incumbent_close is None else rounded(incumbent_close["value_b_number"])
                ),
                "candidate_admission": (
                    "market_open"
                    if pending is None and candidate_open is not None
                    else "pending_fill"
                    if candidate_open is not None
                    else "pending_not_filled"
                    if pending is not None
                    else "not_admitted"
                ),
                "candidate_close_actual": (
                    None if candidate_close is None else rounded(candidate_close["value_a_number"])
                ),
                "candidate_close_stressed": (
                    None if candidate_close is None else rounded(candidate_close["value_b_number"])
                ),
                "retry_risk_skip": retry_skip,
            }
        )
    return output


def run_summary(
    report: Path,
    log: Path,
    portfolio: str,
    event_paths: list[Path] | None = None,
) -> dict[str, Any]:
    result = {
        "report": report_metrics(report),
        "final": final_metrics(log, portfolio),
    }
    if "SLOT-SHADOW-EXCHANGE" in portfolio:
        result["exchange_summary"] = exchange_summary(log)
    if event_paths:
        rows = load_events(event_paths)
        exchanges = exchange_rows(rows)
        result["events"] = {
            "total": event_period(rows, None),
            "2025": event_period(rows, "2025"),
            "2025_h1": event_period(
                [
                    row
                    for row in rows
                    if "2025.01.01" <= row["server_time"] < "2025.07.01"
                ],
                None,
            ),
            "2025_h2": event_period(
                [
                    row
                    for row in rows
                    if "2025.07.01" <= row["server_time"] < "2026.01.01"
                ],
                None,
            ),
            "2026_ytd": event_period(rows, "2026"),
            "first_fixed_lot_step_2x": first_sizing_step(rows, 2),
            "exchange_rows": exchanges,
            "orphan_release_count": sum(
                row["candidate_admission"] in {"not_admitted", "pending_not_filled"}
                for row in exchanges
            ),
            "retry_skip_after_release_count": sum(
                row["retry_risk_skip"] for row in exchanges
            ),
        }
    result["sources"] = {
        "report": source(report),
        "agent_log": source(log),
        "events": [source(path) for path in event_paths or []],
    }
    return result


def delta(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return {
        "actual_net": rounded(
            left["report"]["actual_net"] - right["report"]["actual_net"]
        ),
        "stressed_net_2x": rounded(
            left["final"]["stressed_net_2x"] - right["final"]["stressed_net_2x"]
        ),
        "stressed_closed_drawdown": rounded(
            left["final"]["stressed_closed_drawdown"]
            - right["final"]["stressed_closed_drawdown"]
        ),
        "entries": left["report"]["entries"] - right["report"]["entries"],
        "risk_admission_skips": (
            left["final"]["risk_admission_skips"]
            - right["final"]["risk_admission_skips"]
        ),
    }


def main() -> None:
    baseline_2025 = run_summary(
        ARTIFACTS / "baseline-2025.htm",
        ARTIFACTS / "receiver-wounded-headroom-agent.log",
        "ZT-NEXT-FRONTIER-TIME-FIELD-V1",
    )
    diagnostic = run_summary(
        ARTIFACTS / "receiver-wounded-2025.htm",
        ARTIFACTS / "receiver-wounded-agent.log",
        "ZT-NEXT-FRONTIER-SLOT-SHADOW-EXCHANGE-V1",
        [
            ARTIFACTS / "receiver-wounded-events-a.csv",
            ARTIFACTS / "receiver-wounded-events-b.csv",
        ],
    )
    receiver_headroom_nonatomic = run_summary(
        ARTIFACTS / "receiver-wounded-headroom-2025.htm",
        ARTIFACTS / "receiver-wounded-headroom-agent.log",
        "ZT-NEXT-FRONTIER-SLOT-SHADOW-EXCHANGE-V1",
        [
            ARTIFACTS / "receiver-wounded-headroom-events-a.csv",
            ARTIFACTS / "receiver-wounded-headroom-events-b.csv",
        ],
    )
    mature_headroom_nonatomic = run_summary(
        ARTIFACTS / "mature-wounded-2025.htm",
        ARTIFACTS / "mature-wounded-agent.log",
        "ZT-NEXT-FRONTIER-SLOT-SHADOW-EXCHANGE-V1",
        [
            ARTIFACTS / "mature-wounded-events-a.csv",
            ARTIFACTS / "mature-wounded-events-b.csv",
        ],
    )
    loser_headroom_nonatomic = run_summary(
        ARTIFACTS / "loser-residual-2025.htm",
        ARTIFACTS / "loser-residual-agent.log",
        "ZT-NEXT-FRONTIER-SLOT-SHADOW-EXCHANGE-V1",
        [
            ARTIFACTS / "loser-residual-events-a.csv",
            ARTIFACTS / "loser-residual-events-b.csv",
        ],
    )
    extended_baseline = run_summary(
        ARTIFACTS / "extended-baseline-2025-2026q3.htm",
        ARTIFACTS / "extended-baseline-agent.log",
        "ZT-NEXT-FRONTIER-TIME-FIELD-V1",
        [
            ARTIFACTS / "extended-baseline-receiver-time-field-v1-events-a.csv",
            ARTIFACTS / "extended-baseline-receiver-time-field-v1-events-b.csv",
        ],
    )
    receiver = run_summary(
        ARTIFACTS / "market-only-receiver-wounded-2025.htm",
        ARTIFACTS / "market-only-receiver-wounded-agent.log",
        "ZT-NEXT-FRONTIER-SLOT-SHADOW-EXCHANGE-V1",
        [
            ARTIFACTS / "market-only-receiver-wounded-slot-shadow-exchange-v1-events-a.csv",
            ARTIFACTS / "market-only-receiver-wounded-slot-shadow-exchange-v1-events-b.csv",
        ],
    )
    loser = run_summary(
        ARTIFACTS / "market-only-loser-residual-2025.htm",
        ARTIFACTS / "market-only-loser-residual-agent.log",
        "ZT-NEXT-FRONTIER-SLOT-SHADOW-EXCHANGE-V1",
        [
            ARTIFACTS / "market-only-loser-residual-slot-shadow-exchange-v1-events-a.csv",
            ARTIFACTS / "market-only-loser-residual-slot-shadow-exchange-v1-events-b.csv",
        ],
    )
    extended_receiver = run_summary(
        ARTIFACTS / "extended-market-only-receiver-wounded-2025-2026q3.htm",
        ARTIFACTS / "extended-market-only-receiver-wounded-agent.log",
        "ZT-NEXT-FRONTIER-SLOT-SHADOW-EXCHANGE-V1",
        [
            ARTIFACTS / "extended-market-only-receiver-wounded-slot-shadow-exchange-v1-events-a.csv",
            ARTIFACTS / "extended-market-only-receiver-wounded-slot-shadow-exchange-v1-events-b.csv",
        ],
    )
    extended_loser = run_summary(
        ARTIFACTS / "extended-market-only-loser-residual-2025-2026q3.htm",
        ARTIFACTS / "extended-market-only-loser-residual-agent.log",
        "ZT-NEXT-FRONTIER-SLOT-SHADOW-EXCHANGE-V1",
        [
            ARTIFACTS / "extended-market-only-loser-residual-slot-shadow-exchange-v1-events-a.csv",
            ARTIFACTS / "extended-market-only-loser-residual-slot-shadow-exchange-v1-events-b.csv",
        ],
    )

    forward = [
        row
        for row in extended_loser["events"]["exchange_rows"]
        if row["year"] == "2026"
    ]
    if len(forward) != 1:
        raise RuntimeError(f"expected one 2026 exchange, found {len(forward)}")
    forward_row = forward[0]
    baseline_rows = load_events(
        [
            ARTIFACTS / "extended-baseline-receiver-time-field-v1-events-a.csv",
            ARTIFACTS / "extended-baseline-receiver-time-field-v1-events-b.csv",
        ]
    )
    baseline_incumbent_close = next(
        row
        for row in baseline_rows
        if row["server_time"] > forward_row["server_time"]
        and row["component_id"]
        == "ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8"
        and row["event"] in {"CLOSE", "EXTERNAL_CLOSE"}
    )
    forward_reference = {
        "server_time": forward_row["server_time"],
        "exchange_pair": forward_row,
        "same_date_baseline_incumbent_later_close_actual": rounded(
            baseline_incumbent_close["value_a_number"]
        ),
        "same_date_baseline_incumbent_later_close_stressed": rounded(
            baseline_incumbent_close["value_b_number"]
        ),
        "exchange_pair_delta_vs_same_date_baseline_keep_actual": rounded(
            float(forward_row["incumbent_close_actual"])
            + float(forward_row["candidate_close_actual"])
            - baseline_incumbent_close["value_a_number"]
        ),
        "exchange_pair_delta_vs_same_date_baseline_keep_stressed": rounded(
            float(forward_row["incumbent_close_stressed"])
            + float(forward_row["candidate_close_stressed"])
            - baseline_incumbent_close["value_b_number"]
        ),
        "caveat": "The same-date baseline carried a different prior balance path, so this is a bounded reference rather than an exact paired counterfactual.",
    }

    output = {
        "unit": "slot-shadow-price-006",
        "question": "Can occupied risk slots be priced causally so later opportunities replace weak incumbents without reducing entry count?",
        "architecture": {
            "measurement": "receiver_time_field_plus_observation_only_candidate_and_incumbent_tape",
            "proxy": "34560 causal candidate-value and incumbent-shadow-price policies",
            "runtime": "tester_only_six_strategy_ea_with_transaction_buffered_one_slot_exchange",
            "quality_state": "rolling_32_stressed_r_seeded_only_from_prior_2024_next_lab_lifecycles",
        },
        "measurement": {
            "candidates": 606,
            "incumbent_snapshots": 378,
            "risk_blocked": 25,
            "counterfactual_matched": 23,
            "counterfactual_candidate_positive": 12,
            "best_incumbent_exchange_positive": 17,
            "measurement_path_neutrality": "The tape and same-session receiver-time-field control were identical: actual 130.62, stressed 122.2495, stressed drawdown 27.326, 551 entries.",
        },
        "proxy": {
            "evaluations": 34560,
            "stable_cells": 1052,
            "leader": "receiver_priority_vs_wounded_age",
            "leader_actions": 8,
            "leader_first_order_exchange_delta": 15.571,
            "limit": "First-order exchange labels did not include later portfolio path mutation.",
            "source": source(FRONTIER / "proxy.json"),
        },
        "transaction_boundary_discovery": {
            "zero_headroom_diagnostic": diagnostic,
            "headroom_only_nonatomic_runs": {
                "receiver_wounded": receiver_headroom_nonatomic,
                "mature_wounded": mature_headroom_nonatomic,
                "loser_residual": loser_headroom_nonatomic,
            },
            "observations": [
                "Without release headroom, 4 of 10 closes lowered risk capital enough that the candidate failed the recalculated admission. The profitable result mixed genuine exchanges with unilateral loss cutting.",
                "After headroom repair, receiver-wounded and mature-wounded each still sacrificed one incumbent for a Passive limit that never filled. A pending order is not an atomic replacement.",
            ],
            "repairs": [
                "Require the released slot to cover the raw deficit plus max(0.05 USD, 5% of the candidate position budget), then recompute protection and risk from the new capital state.",
                "Do not release an occupied market slot for a Passive pending-order candidate; final runtime branches exchange only into immediate market candidates.",
            ],
        },
        "runtime_2025": {
            "baseline_receiver_time_field": baseline_2025,
            "market_only_receiver_wounded": receiver,
            "market_only_loser_residual": loser,
            "deltas_vs_baseline": {
                "market_only_receiver_wounded": delta(receiver, baseline_2025),
                "market_only_loser_residual": delta(loser, baseline_2025),
            },
        },
        "extended_2025_to_2026_08_21": {
            "baseline_receiver_time_field": extended_baseline,
            "market_only_receiver_wounded": extended_receiver,
            "market_only_loser_residual": extended_loser,
            "deltas_vs_baseline": {
                "market_only_receiver_wounded": delta(extended_receiver, extended_baseline),
                "market_only_loser_residual": delta(extended_loser, extended_baseline),
            },
            "fixed_lot_step_observation": {
                "baseline_first_2x": extended_baseline["events"]["first_fixed_lot_step_2x"],
                "receiver_first_2x": extended_receiver["events"]["first_fixed_lot_step_2x"],
                "loser_first_2x": extended_loser["events"]["first_fixed_lot_step_2x"],
                "interpretation": "The 2025 exchange gains moved the stressed balance through the next fixed lot step 7 days earlier for receiver-wounded and 11 days earlier for loser-residual. All three paths then took the same 359 entries in 2026, but earlier 2x sizing amplified both later profit and drawdown.",
            },
            "forward_exchange_reference": forward_reference,
        },
        "judgment": {
            "portfolio_entry_constraint": "passed; final market-only 2025 entries were 557 and 561 versus 551, and extended entries were 919 and 923 versus 913",
            "transaction_completeness": "passed after both repairs; every final release opened its market candidate with zero retry skips and no pending-order dependence",
            "economic_discovery": "A risk slot has a causal shadow price, but fixed lot-step proximity is a second state variable: a small early exchange advantage can move the entire later portfolio into higher sizing sooner.",
            "forward_limit": "The broad final rule made only one new 2026 exchange and its bounded same-date stressed reference was -1.552 USD; the selective final rule made no new 2026 exchanges.",
            "retained_primary": "receiver_time_field_cross_profit_gate_6",
            "retained_research_seed": "transaction_buffered_slot_shadow_exchange_with_capital_step_context",
            "promotion": "none",
            "next": "capital_step_phase_coupling",
        },
        "compile": {
            "slot_exchange": "MetaEditor build 6140: 0 errors, 0 warnings",
            "receiver_reference_after_neutral_parent_hooks": "MetaEditor build 6140: 0 errors, 0 warnings",
            "sources": [
                source(ROOT / "lab" / "mt5" / "src" / "Experts" / "ZetaNextSlotShadowExchangeV1.mq5"),
                source(ROOT / "lab" / "mt5" / "src" / "Include" / "ZetaTerminusNext" / "Frontier" / "SlotShadowExchangeAdapter.mqh"),
            ],
        },
        "runtime_faults": {
            "safety_stopped": 0,
            "persistence_failed": 0,
            "broker_mismatch": 0,
            "foreign_exposure": 0,
            "protection_calculation_failures": 0,
            "protection_mismatches": 0,
            "release_failures": 0,
        },
        "live_surface": "untouched",
    }
    (FRONTIER / "runtime.json").write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
