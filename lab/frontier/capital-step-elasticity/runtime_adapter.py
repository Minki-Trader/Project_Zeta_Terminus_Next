#!/usr/bin/env python3
"""Summarize causal real-tick adjacent-tier exposure experiments."""

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
FRONTIER = ROOT / "lab" / "frontier" / "capital-step-elasticity"
ARTIFACTS = ROOT / "lab" / "artifacts" / "backtests" / "capital-step-elasticity"
PRIOR_ARTIFACTS = ROOT / "lab" / "artifacts" / "backtests" / "slot-shadow-price"
PORTFOLIO = "ZT-NEXT-FRONTIER-CAPITAL-ELASTICITY-V1"
COMPONENTS = {
    "ZT-M30-US30-RANGE-COMP-61f61deaba": "RC16",
    "ZT-M30-US30-RANGE-COMP-64efb16616": "RC4",
    "ZT-H1-US100-CROSS-IN-14b72317b7": "CROSS",
    "ZT-M30-US30-INTRADAY-R-2eb111fc46": "PRESSURE",
    "ZT-H1-US30-RETURN-I-c870a788ec": "RETURN",
    "ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8": "PASSIVE",
}
ECONOMIC_EVENTS = {
    "SIZE_DAY",
    "OPEN",
    "PASSIVE_FILL",
    "CLOSE",
    "EXTERNAL_CLOSE",
    "RISK_ADMISSION_SKIP",
    "SLOT_EXCHANGE_RELEASE",
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


def final_metrics(path: Path) -> dict[str, Any]:
    matches = [line for line in read_log(path) if f"final portfolio={PORTFOLIO}" in line]
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


def elasticity_summary(path: Path) -> dict[str, Any]:
    row = tagged_summary(path, "ZETA_FRONTIER_CAPITAL_ELASTICITY_SUMMARY|")
    return {
        "mode": row["mode"],
        "sizing_days": int(row["sizing_days"]),
        "downcross_resets": int(row["downcross_resets"]),
        "high_tier_opportunities": int(row["high_tier_opportunities"]),
        "lower_tier_allocations": int(row["lower_tier_allocations"]),
        "upper_tier_allocations": int(row["upper_tier_allocations"]),
        "exchange_quarantines": int(row.get("exchange_quarantines", "0")),
    }


def exchange_summary(path: Path) -> dict[str, Any]:
    row = tagged_summary(path, "ZETA_FRONTIER_SLOT_EXCHANGE_SUMMARY|")
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


def detail_number(detail: str, key: str) -> float | None:
    match = re.search(rf"(?:^|\s){re.escape(key)}=(-?\d+(?:\.\d+)?)", detail)
    return float(match.group(1)) if match else None


def allocation_lifecycles(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    plans = [row for row in rows if row["event"] == "CAPITAL_ELASTICITY_PLAN"]
    output: list[dict[str, Any]] = []
    for plan in plans:
        opened = next(
            (
                row
                for row in rows
                if row["sequence"] > plan["sequence"]
                and row["component_id"] == plan["component_id"]
                and row["event"] == "OPEN"
            ),
            None,
        )
        closed = (
            next(
                (
                    row
                    for row in rows
                    if opened is not None
                    and row["sequence"] > opened["sequence"]
                    and row["component_id"] == plan["component_id"]
                    and row["event"] in {"CLOSE", "EXTERNAL_CLOSE"}
                ),
                None,
            )
            if opened is not None
            else None
        )
        output.append(
            {
                "server_time": plan["server_time"],
                "component": COMPONENTS.get(plan["component_id"], plan["component_id"]),
                "mode": re.search(r"mode=([^\s]+)", plan["detail"]).group(1),
                "raw_tier": int(detail_number(plan["detail"], "raw") or 0),
                "selected_tier": int(round(plan["value_b_number"])),
                "boundary_progress": rounded(plan["value_a_number"]),
                "balance": rounded(detail_number(plan["detail"], "balance") or 0.0),
                "delivered_volume": rounded(opened["value_b_number"]) if opened else None,
                "actual_net": rounded(closed["value_a_number"]) if closed else None,
                "stressed_net": rounded(closed["value_b_number"]) if closed else None,
            }
        )
    return output


def economic_digest(rows: list[dict[str, Any]], end: datetime) -> dict[str, Any]:
    normalized = [
        {
            "time": row["server_time"],
            "event": row["event"],
            "component": row["component_id"],
            "a": rounded(row["value_a_number"]),
            "b": rounded(row["value_b_number"]),
        }
        for row in rows
        if row["time"] < end and row["event"] in ECONOMIC_EVENTS
    ]
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    return {
        "events": len(normalized),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def run_summary(report: Path, log: Path, event_paths: list[Path]) -> dict[str, Any]:
    rows = load_events(event_paths)
    allocations = allocation_lifecycles(rows)
    return {
        "report": report_metrics(report),
        "final": final_metrics(log),
        "events": {
            "total": event_period(rows, None, None),
            "2025": event_period(rows, datetime(2025, 1, 1), datetime(2026, 1, 1)),
            "2026_h1": event_period(rows, datetime(2026, 1, 1), datetime(2026, 7, 1)),
            "2026_h2_to_aug21": event_period(rows, datetime(2026, 7, 1), None),
            "sizing": sizing_transitions(rows),
        },
        "elasticity_summary": elasticity_summary(log),
        "exchange_summary": exchange_summary(log),
        "allocation_lifecycles": allocations,
        "sources": {
            "report": source(report),
            "agent_log": source(log),
            "events": [source(path) for path in event_paths],
        },
        "_rows": rows,
    }


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


def proxy_policy(proxy: dict[str, Any], policy_id: str) -> dict[str, Any]:
    candidates = [
        proxy["search"]["anchor"],
        proxy["search"]["diagnostic_cap_at_2x"],
        *proxy["search"]["top_survivors"],
    ]
    return next(item for item in candidates if item["policy"]["policy_id"] == policy_id)


def main() -> None:
    phase_runtime_path = ROOT / "lab" / "frontier" / "capital-step-phase" / "runtime.json"
    phase_runtime = json.loads(phase_runtime_path.read_text(encoding="utf-8"))
    retained = phase_runtime["references"]["retained_primary"]
    broad = phase_runtime["references"]["broad_slot_exchange"]
    definitions = {
        "component_clock_band_30": (
            "component30-loser-2025-2026q3.htm",
            "component30-loser-agent.log",
            ["component30-loser-events-a.csv", "component30-loser-events-b.csv"],
        ),
        "hard_third_tier_reserve_20": (
            "hard20-loser-2025-2026q3.htm",
            "hard20-loser-agent.log",
            ["hard20-loser-events-a.csv", "hard20-loser-events-b.csv"],
        ),
        "hard_reserve_20_with_exchange_quarantine": (
            "hard20-loser-quarantine-2025-2026q3.htm",
            "hard20-loser-quarantine-agent.log",
            [
                "hard20-loser-quarantine-events-a.csv",
                "hard20-loser-quarantine-events-b.csv",
            ],
        ),
    }
    runs: dict[str, dict[str, Any]] = {}
    for name, (report_name, log_name, event_names) in definitions.items():
        runs[name] = run_summary(
            ARTIFACTS / report_name,
            ARTIFACTS / log_name,
            [ARTIFACTS / event_name for event_name in event_names],
        )

    prior_rows = load_events(
        [
            PRIOR_ARTIFACTS / "extended-market-only-loser-residual-slot-shadow-exchange-v1-events-a.csv",
            PRIOR_ARTIFACTS / "extended-market-only-loser-residual-slot-shadow-exchange-v1-events-b.csv",
        ]
    )
    first_plan = min(
        row["time"]
        for row in runs["hard_third_tier_reserve_20"]["_rows"]
        if row["event"] == "CAPITAL_ELASTICITY_PLAN"
    )
    pre_plan = {"prior_broad_slot_exchange": economic_digest(prior_rows, first_plan)}
    for name, run in runs.items():
        pre_plan[name] = economic_digest(run["_rows"], first_plan)
    pre_plan["interpretation"] = (
        "The two pure exposure allocators are economically identical to the broad slot path "
        "before the first tier plan. The quarantine branch intentionally diverges at the "
        "February 2026 1x-to-2x upstep by refusing one later slot exchange."
    )

    proxy = json.loads((FRONTIER / "proxy.json").read_text(encoding="utf-8"))
    component_proxy = proxy_policy(proxy, "elastic-049")["paths"]["prior_broad_slot_exchange"]
    hard_proxy = proxy_policy(proxy, "elastic-006")["paths"]["prior_broad_slot_exchange"]
    deltas_broad = {name: delta(run, broad) for name, run in runs.items()}
    deltas_retained = {name: delta(run, retained) for name, run in runs.items()}
    deltas_between = {
        "hard_vs_component_clock": delta(
            runs["hard_third_tier_reserve_20"], runs["component_clock_band_30"]
        ),
        "quarantine_vs_hard": delta(
            runs["hard_reserve_20_with_exchange_quarantine"],
            runs["hard_third_tier_reserve_20"],
        ),
    }
    for run in runs.values():
        del run["_rows"]

    payload = {
        "unit": "capital-step-elasticity-008",
        "question": "Can adjacent integer volume tiers be allocated causally without reducing opportunity count or inheriting one-day high-tier cliffs?",
        "architecture": {
            "measurement": "reuse_current_next_lab_capital_transition_lifecycles",
            "proxy": "57_third_tier_hard_reserve_and_sigma_delta_hypotheses",
            "runtime": "tester_only_adapter_plus_six_strategy_ea_with_two_allocators_and_one_exchange_quarantine_branch",
        },
        "references": {
            "retained_primary": retained,
            "broad_slot_exchange": broad,
        },
        "runtime_runs": runs,
        "deltas_vs_broad_slot_exchange": deltas_broad,
        "deltas_vs_retained_primary": deltas_retained,
        "direct_deltas": deltas_between,
        "causal_identity_before_first_tier_plan": pre_plan,
        "proxy_runtime_gap": {
            "component_clock_band_30": {
                "proxy_first_order_net_delta": component_proxy["first_order_net_delta"],
                "runtime_stressed_net_delta": deltas_broad["component_clock_band_30"]["stressed_net"],
                "proxy_drawdown_delta": component_proxy["first_order_drawdown_delta"],
                "runtime_drawdown_delta": deltas_broad["component_clock_band_30"]["stressed_closed_drawdown"],
            },
            "hard_third_tier_reserve_20": {
                "proxy_first_order_net_delta": hard_proxy["first_order_net_delta"],
                "runtime_stressed_net_delta": deltas_broad["hard_third_tier_reserve_20"]["stressed_net"],
                "proxy_drawdown_delta": hard_proxy["first_order_drawdown_delta"],
                "runtime_drawdown_delta": deltas_broad["hard_third_tier_reserve_20"]["stressed_closed_drawdown"],
            },
            "interpretation": "The sigma-delta clock accumulated exposure debt and assigned its sole 3x opportunity to a losing CROSS lifecycle. The hard reserve kept all nine high-tier opportunities at 2x; real stop geometry then improved both net and drawdown more than first-order rescaling predicted.",
        },
        "judgement": {
            "entry_constraint": {
                name: {
                    "entries": run["report"]["entries"],
                    "passed_vs_retained_913": run["report"]["entries"] >= 913,
                    "preserved_vs_broad_923": run["report"]["entries"] >= 923,
                }
                for name, run in runs.items()
            },
            "runtime_integrity": {name: no_faults(run) for name, run in runs.items()},
            "discovery": "A fractional exposure clock is not automatically smoother risk: unused credit becomes an order-dependent claim on a future trade. A hard marginal-capital reserve avoided that debt and improved broad-path profit and drawdown with all 923 entries retained.",
            "selection": "retain_hard_third_tier_20usd_transition_reserve_as_frontier_candidate",
            "rejected_combination": "The post-upstep exchange quarantine gained only by dropping the February 5 CROSS opportunity, still worsened drawdown versus hard reserve alone, and violates full broad-path entry preservation.",
            "retained_primary": "receiver_time_field_cross_profit_gate_6",
            "promotion": "none",
            "reason_not_promoted": "The reserve advantage is concentrated in nine same-window high-tier opportunities and has no independent later transition evidence.",
            "next": "transition_reserve_geometry_across_starting_capital_and_later_tiers",
        },
        "compile": {
            "capital_elasticity": "MetaEditor build 6140: 0 errors, 0 warnings",
        },
        "sources": {
            "proxy": source(FRONTIER / "proxy.json"),
            "capital_phase_runtime": source(phase_runtime_path),
            "ea": source(ROOT / "lab" / "mt5" / "src" / "Experts" / "ZetaNextCapitalElasticityV1.mq5"),
            "binary": source(ROOT / "lab" / "mt5" / "src" / "Experts" / "ZetaNextCapitalElasticityV1.ex5"),
            "adapter": source(ROOT / "lab" / "mt5" / "src" / "Include" / "ZetaTerminusNext" / "Frontier" / "CapitalElasticityAdapter.mqh"),
            "field_adapter": source(ROOT / "lab" / "mt5" / "src" / "Include" / "ZetaTerminusNext" / "Frontier" / "CapitalElasticityFieldAdapter.mqh"),
        },
    }
    output = FRONTIER / "runtime.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
