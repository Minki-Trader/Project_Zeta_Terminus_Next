#!/usr/bin/env python3
"""Summarize real-tick capital-step phase mutations and proxy error."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
FRONTIER = ROOT / "lab" / "frontier" / "capital-step-phase"
ARTIFACTS = ROOT / "lab" / "artifacts" / "backtests" / "capital-step-phase"
PRIOR_ARTIFACTS = ROOT / "lab" / "artifacts" / "backtests" / "slot-shadow-price"
PORTFOLIO = "ZT-NEXT-FRONTIER-CAPITAL-STEP-PHASE-V1"
PRIOR_BASELINE_PORTFOLIO = "ZT-NEXT-FRONTIER-TIME-FIELD-V1"
PRIOR_EXCHANGE_PORTFOLIO = "ZT-NEXT-FRONTIER-SLOT-SHADOW-EXCHANGE-V1"
COMPONENTS = {
    "ZT-M30-US30-RANGE-COMP-61f61deaba": "RC16",
    "ZT-M30-US30-RANGE-COMP-64efb16616": "RC4",
    "ZT-H1-US100-CROSS-IN-14b72317b7": "CROSS",
    "ZT-M30-US30-INTRADAY-R-2eb111fc46": "PRESSURE",
    "ZT-H1-US30-RETURN-I-c870a788ec": "RETURN",
    "ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8": "PASSIVE",
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
    matches = [line for line in read_log(path) if f"final portfolio={portfolio}" in line]
    if not matches:
        raise RuntimeError(f"final summary missing in {path}")
    row = fields(matches[-1])
    return {
        "stressed_net": float(row["stressed_net_2x"]),
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


def tagged_summary(path: Path, tag: str) -> dict[str, str]:
    matches = [line for line in read_log(path) if tag in line]
    if not matches:
        return {}
    payload = matches[-1].split(tag, 1)[1]
    return {
        item.split("=", 1)[0]: item.split("=", 1)[1]
        for item in payload.split("|")
        if "=" in item
    }


def phase_summary(path: Path) -> dict[str, Any]:
    row = tagged_summary(path, "ZETA_FRONTIER_CAPITAL_STEP_PHASE_SUMMARY|")
    if not row:
        return {}
    return {
        "mode": row["mode"],
        "sizing_days": int(row["sizing_days"]),
        "upsteps": int(row["upsteps"]),
        "downsteps": int(row["downsteps"]),
        "blocked_upsteps": int(row["blocked_upsteps"]),
        "exchange_quarantines": int(row["exchange_quarantines"]),
        "recent_drawdown_at_end": float(row["recent_dd"]),
        "rolling_outcomes": int(row["outcomes"]),
    }


def exchange_summary(path: Path) -> dict[str, Any]:
    row = tagged_summary(path, "ZETA_FRONTIER_SLOT_EXCHANGE_SUMMARY|")
    if not row:
        return {}
    return {
        "mode": row["mode"],
        "signals": int(row["signals"]),
        "completed_lifecycles": int(row["completed_lifecycles"]),
        "risk_blocks": int(row["risk_blocks"]),
        "qualified": int(row["qualified"]),
        "release_successes": int(row["release_successes"]),
        "release_failures": int(row["release_failures"]),
        "retry_blocks": int(row["retry_blocks"]),
        "headroom_blocks": int(row["headroom_blocks"]),
        "pending_candidate_blocks": int(row["pending_candidate_blocks"]),
    }


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y.%m.%d %H:%M:%S")


def load_events(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for raw in csv.DictReader(handle):
                row: dict[str, Any] = dict(raw)
                row["sequence"] = int(raw["state_sequence"])
                row["time"] = parse_time(raw["server_time"])
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


def event_period(
    rows: list[dict[str, Any]], start: datetime | None, end: datetime | None
) -> dict[str, Any]:
    selected = [
        row
        for row in rows
        if (start is None or row["time"] >= start)
        and (end is None or row["time"] < end)
    ]
    closes = [row for row in selected if row["event"] in {"CLOSE", "EXTERNAL_CLOSE"}]
    entries = [row for row in selected if row["event"] in {"OPEN", "PASSIVE_FILL"}]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in closes:
        component = COMPONENTS.get(row["component_id"])
        if component is not None:
            grouped[component].append(row)
    return {
        "entries": len(entries),
        "closed_lifecycles": len(closes),
        "actual_net": rounded(sum(row["value_a_number"] for row in closes)),
        "stressed_net": rounded(sum(row["value_b_number"] for row in closes)),
        "actual_closed_drawdown": drawdown([row["value_a_number"] for row in closes]),
        "stressed_closed_drawdown": drawdown([row["value_b_number"] for row in closes]),
        "risk_admission_skips": sum(row["event"] == "RISK_ADMISSION_SKIP" for row in selected),
        "slot_exchanges": sum(row["event"] == "SLOT_EXCHANGE_RELEASE" for row in selected),
        "components": {
            component: {
                "closed_lifecycles": len(component_rows),
                "actual_net": rounded(sum(row["value_a_number"] for row in component_rows)),
                "stressed_net": rounded(sum(row["value_b_number"] for row in component_rows)),
            }
            for component, component_rows in sorted(grouped.items())
        },
    }


def sizing_transitions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sizing = [row for row in rows if row["event"] == "SIZE_DAY"]
    transitions: list[dict[str, Any]] = []
    prior: int | None = None
    for index, row in enumerate(sizing):
        multiplier = int(round(row["value_b_number"]))
        if prior is not None and multiplier != prior:
            end = next(
                (
                    later["time"]
                    for later in sizing[index + 1 :]
                    if int(round(later["value_b_number"])) != multiplier
                ),
                rows[-1]["time"] + timedelta(seconds=1),
            )
            transitions.append(
                {
                    "server_time": row["server_time"],
                    "from_multiplier": prior,
                    "to_multiplier": multiplier,
                    "balance": rounded(row["value_a_number"]),
                    "until_next_transition": end.strftime("%Y.%m.%d %H:%M:%S"),
                    "calendar_days": (end.date() - row["time"].date()).days,
                    "path": event_period(rows, row["time"], end),
                }
            )
        prior = multiplier
    return {
        "sizing_days": len(sizing),
        "multiplier_days": {
            str(multiplier): sum(
                int(round(row["value_b_number"])) == multiplier for row in sizing
            )
            for multiplier in sorted({int(round(row["value_b_number"])) for row in sizing})
        },
        "maximum_multiplier": max(int(round(row["value_b_number"])) for row in sizing),
        "transitions": transitions,
    }


def run_summary(
    report: Path,
    log: Path,
    portfolio: str,
    event_paths: list[Path],
    phase: bool,
    exchange: bool,
) -> dict[str, Any]:
    rows = load_events(event_paths)
    result = {
        "report": report_metrics(report),
        "final": final_metrics(log, portfolio),
        "events": {
            "total": event_period(rows, None, None),
            "2025": event_period(rows, datetime(2025, 1, 1), datetime(2026, 1, 1)),
            "2026_h1": event_period(rows, datetime(2026, 1, 1), datetime(2026, 7, 1)),
            "2026_h2_to_aug21": event_period(rows, datetime(2026, 7, 1), None),
            "sizing": sizing_transitions(rows),
        },
        "sources": {
            "report": source(report),
            "agent_log": source(log),
            "events": [source(path) for path in event_paths],
        },
    }
    if phase:
        result["phase_summary"] = phase_summary(log)
    if exchange:
        result["exchange_summary"] = exchange_summary(log)
    return result


def delta(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return {
        "entries": left["report"]["entries"] - right["report"]["entries"],
        "actual_net": rounded(left["report"]["actual_net"] - right["report"]["actual_net"]),
        "actual_balance_drawdown": rounded(
            left["report"]["actual_balance_drawdown"]
            - right["report"]["actual_balance_drawdown"]
        ),
        "stressed_net": rounded(left["final"]["stressed_net"] - right["final"]["stressed_net"]),
        "stressed_closed_drawdown": rounded(
            left["final"]["stressed_closed_drawdown"]
            - right["final"]["stressed_closed_drawdown"]
        ),
        "risk_admission_skips": (
            left["final"]["risk_admission_skips"]
            - right["final"]["risk_admission_skips"]
        ),
    }


def no_faults(run: dict[str, Any]) -> bool:
    final = run["final"]
    return (
        not final["safety_stopped"]
        and not final["persistence_failed"]
        and not final["broker_mismatch"]
        and not final["foreign_exposure"]
        and final["protection_calculation_failures"] == 0
        and final["protection_mismatches"] == 0
    )


def main() -> None:
    prior_baseline = run_summary(
        PRIOR_ARTIFACTS / "extended-baseline-2025-2026q3.htm",
        PRIOR_ARTIFACTS / "extended-baseline-agent.log",
        PRIOR_BASELINE_PORTFOLIO,
        [
            PRIOR_ARTIFACTS / "extended-baseline-receiver-time-field-v1-events-a.csv",
            PRIOR_ARTIFACTS / "extended-baseline-receiver-time-field-v1-events-b.csv",
        ],
        phase=False,
        exchange=False,
    )
    prior_loser = run_summary(
        PRIOR_ARTIFACTS / "extended-market-only-loser-residual-2025-2026q3.htm",
        PRIOR_ARTIFACTS / "extended-market-only-loser-residual-agent.log",
        PRIOR_EXCHANGE_PORTFOLIO,
        [
            PRIOR_ARTIFACTS / "extended-market-only-loser-residual-slot-shadow-exchange-v1-events-a.csv",
            PRIOR_ARTIFACTS / "extended-market-only-loser-residual-slot-shadow-exchange-v1-events-b.csv",
        ],
        phase=False,
        exchange=True,
    )

    definitions = {
        "downside_baseline": (
            "downside-baseline-2025-2026q3.htm",
            "downside-baseline-agent.log",
            ["downside-baseline-events-a.csv", "downside-baseline-events-b.csv"],
            False,
        ),
        "downside_loser": (
            "downside-loser-2025-2026q3.htm",
            "downside-loser-agent.log",
            ["downside-loser-events-a.csv", "downside-loser-events-b.csv"],
            True,
        ),
        "downside_loser_quarantine": (
            "downside-loser-quarantine-2025-2026q3.htm",
            "downside-loser-quarantine-agent.log",
            [
                "downside-loser-quarantine-events-a.csv",
                "downside-loser-quarantine-events-b.csv",
            ],
            True,
        ),
        "confirm2_loser": (
            "confirm2-loser-2025-2026q3.htm",
            "confirm2-loser-agent.log",
            ["confirm2-loser-events-a.csv", "confirm2-loser-events-b.csv"],
            True,
        ),
    }
    runs: dict[str, dict[str, Any]] = {}
    for name, (report_name, log_name, event_names, uses_exchange) in definitions.items():
        runs[name] = run_summary(
            ARTIFACTS / report_name,
            ARTIFACTS / log_name,
            PORTFOLIO,
            [ARTIFACTS / event_name for event_name in event_names],
            phase=True,
            exchange=uses_exchange,
        )

    with (FRONTIER / "proxy.json").open("r", encoding="utf-8") as handle:
        proxy = json.load(handle)
    proxy_downside = next(
        item
        for item in proxy["policy_search"]["top_survivors"]
        if item["policy"]["policy_id"] == "phase-039"
    )["paths"]["market_only_loser_residual"]
    proxy_confirm = next(
        item
        for item in proxy["policy_search"]["top_survivors"]
        if item["policy"]["policy_id"] == "phase-001"
    )["paths"]["market_only_loser_residual"]

    payload = {
        "unit": "capital-step-phase-007",
        "question": "Can discrete lot-step distance become a causal portfolio phase state without reducing entry count?",
        "architecture": {
            "measurement": "reused_current_next_lab_slot_paths",
            "proxy": "63_hypothesis_family_first_order_phase_probe",
            "runtime": "tester_only_adapter_plus_six_strategy_ea_with_two_sizing_rules_and_one_exchange_quarantine_branch",
        },
        "references": {
            "retained_primary": prior_baseline,
            "broad_slot_exchange": prior_loser,
        },
        "runtime_runs": runs,
        "deltas_vs_broad_slot_exchange": {
            name: delta(run, prior_loser)
            for name, run in runs.items()
            if name != "downside_baseline"
        },
        "baseline_neutrality": {
            "delta": delta(runs["downside_baseline"], prior_baseline),
            "identical_event_economics": (
                runs["downside_baseline"]["events"]["total"]
                == prior_baseline["events"]["total"]
            ),
        },
        "proxy_runtime_gap": {
            "recent_downside_escrow_25": {
                "proxy_first_order_net_delta": proxy_downside["first_order_net_delta"],
                "runtime_net_delta": delta(runs["downside_loser"], prior_loser)["stressed_net"],
                "proxy_drawdown_delta": proxy_downside["first_order_drawdown_delta"],
                "runtime_drawdown_delta": delta(runs["downside_loser"], prior_loser)["stressed_closed_drawdown"],
                "proxy_proposed_3x_days": proxy_downside["proposed_3x_days"],
                "runtime_3x_days": runs["downside_loser"]["events"]["sizing"]["multiplier_days"].get("3", 0),
            },
            "two_sizing_day_confirmation": {
                "proxy_first_order_net_delta": proxy_confirm["first_order_net_delta"],
                "runtime_net_delta": delta(runs["confirm2_loser"], prior_loser)["stressed_net"],
                "proxy_drawdown_delta": proxy_confirm["first_order_drawdown_delta"],
                "runtime_drawdown_delta": delta(runs["confirm2_loser"], prior_loser)["stressed_closed_drawdown"],
                "proxy_proposed_3x_days": proxy_confirm["proposed_3x_days"],
                "runtime_3x_days": runs["confirm2_loser"]["events"]["sizing"]["multiplier_days"].get("3", 0),
            },
            "interpretation": "The first-order proxy held the observed balance path fixed. Real delayed sizing changed stop distances and realized outcomes, rebuilt enough capital to cross 3x later, and reversed the predicted drawdown benefit.",
        },
        "judgement": {
            "entry_constraint": {
                name: {
                    "entries": run["report"]["entries"],
                    "passed_vs_retained_913": run["report"]["entries"] >= 913,
                }
                for name, run in runs.items()
            },
            "runtime_integrity": {
                name: no_faults(run) for name, run in runs.items()
            },
            "discovery": "A capital step is an endogenous phase boundary. A small profit escrow or one-day confirmation can postpone a crossing, but the altered stops and outcomes can rebuild the crossing and lengthen later high-multiplier exposure. Removing a bad exchange can raise capital soon enough to worsen later drawdown.",
            "selection": "none",
            "retained_primary": "receiver_time_field_cross_profit_gate_6",
            "retained_research_seed": "tier_specific_transition_budget_or_continuous_exposure_ramp",
            "promotion": "none",
            "next": "capital_step_elasticity",
        },
        "compile": {
            "capital_step_phase": "MetaEditor build 6140: 0 errors, 0 warnings",
            "neutral_parent": "MetaEditor build 6140: 0 errors, 0 warnings",
            "neutral_receiver": "MetaEditor build 6140: 0 errors, 0 warnings",
            "neutral_slot_exchange": "MetaEditor build 6140: 0 errors, 0 warnings",
        },
        "sources": {
            "proxy": source(FRONTIER / "proxy.json"),
            "ea": source(ROOT / "lab" / "mt5" / "src" / "Experts" / "ZetaNextCapitalStepPhaseV1.mq5"),
            "adapter": source(ROOT / "lab" / "mt5" / "src" / "Include" / "ZetaTerminusNext" / "Frontier" / "CapitalStepPhaseAdapter.mqh"),
            "field_adapter": source(ROOT / "lab" / "mt5" / "src" / "Include" / "ZetaTerminusNext" / "Frontier" / "CapitalStepExchangeFieldAdapter.mqh"),
        },
    }
    output = FRONTIER / "runtime.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
