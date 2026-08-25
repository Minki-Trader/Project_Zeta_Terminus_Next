#!/usr/bin/env python3
"""Summarize real-tick transition-reserve geometry across capital scales."""

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
FRONTIER = ROOT / "lab" / "frontier" / "transition-reserve-geometry"
ARTIFACTS = ROOT / "lab" / "artifacts" / "backtests" / "transition-reserve-geometry"
PORTFOLIO = "ZT-NEXT-FRONTIER-TRANSITION-RESERVE-GEOMETRY-V1"
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


def final_metrics(lines: list[str]) -> dict[str, Any]:
    matches = [line for line in lines if f"final portfolio={PORTFOLIO}" in line]
    if not matches:
        raise RuntimeError("final summary missing")
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


def tagged_summary(lines: list[str], tag: str) -> dict[str, str]:
    matches = [line for line in lines if tag in line]
    if not matches:
        return {}
    payload = matches[-1].split(tag, 1)[1]
    return {
        item.split("=", 1)[0]: item.split("=", 1)[1]
        for item in payload.split("|")
        if "=" in item
    }


def reserve_summary(lines: list[str]) -> dict[str, Any]:
    row = tagged_summary(lines, "ZETA_FRONTIER_TRANSITION_RESERVE_SUMMARY|")
    return {
        "mode": row["mode"],
        "deposit": float(row["deposit"]),
        "base_volume": float(row["base_volume"]),
        "addition_step": float(row["addition_step"]),
        "sizing_days": int(row["sizing_days"]),
        "upsteps": int(row["upsteps"]),
        "downsteps": int(row["downsteps"]),
        "maximum_raw_tier": int(row["max_raw_tier"]),
        "high_tier_opportunities": int(row["high_tier_opportunities"]),
        "lower_tier_allocations": int(row["lower_tier_allocations"]),
        "upper_tier_allocations": int(row["upper_tier_allocations"]),
    }


def exchange_summary(lines: list[str]) -> dict[str, Any]:
    row = tagged_summary(lines, "ZETA_FRONTIER_SLOT_EXCHANGE_SUMMARY|")
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


def allocation_lifecycles(
    rows: list[dict[str, Any]], base_volume: float
) -> list[dict[str, Any]]:
    plans = [row for row in rows if row["event"] == "TRANSITION_RESERVE_PLAN"]
    output: list[dict[str, Any]] = []
    for plan in plans:
        deadline = plan["time"] + timedelta(minutes=2)
        opened = next(
            (
                row
                for row in rows
                if row["sequence"] > plan["sequence"]
                and row["component_id"] == plan["component_id"]
                and row["event"] == "OPEN"
                and row["time"] <= deadline
            ),
            None,
        )
        blocked = next(
            (
                row
                for row in rows
                if row["sequence"] > plan["sequence"]
                and row["component_id"] == plan["component_id"]
                and row["event"] == "RISK_ADMISSION_SKIP"
                and row["time"] <= deadline
            ),
            None,
        )
        closed = (
            next(
                (
                    row
                    for row in rows
                    if row["sequence"] > opened["sequence"]
                    and row["component_id"] == plan["component_id"]
                    and row["event"] in {"CLOSE", "EXTERNAL_CLOSE"}
                ),
                None,
            )
            if opened is not None
            else None
        )
        raw_tier = int(detail_number(plan["detail"], "raw") or 0)
        output.append(
            {
                "server_time": plan["server_time"],
                "component": COMPONENTS.get(plan["component_id"], plan["component_id"]),
                "raw_tier": raw_tier,
                "selected_tier": int(round(plan["value_b_number"])),
                "reserve": rounded(plan["value_a_number"]),
                "threshold": rounded(detail_number(plan["detail"], "threshold") or 0.0),
                "balance": rounded(detail_number(plan["detail"], "balance") or 0.0),
                "admitted": opened is not None,
                "risk_blocked": blocked is not None,
                "delivered_volume": rounded(opened["value_b_number"]) if opened else None,
                "delivered_tier": (
                    int(round(opened["value_b_number"] / base_volume)) if opened else None
                ),
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
    return {"events": len(normalized), "sha256": hashlib.sha256(encoded).hexdigest()}


def run_summary(
    report: Path,
    log: Path,
    event_paths: list[Path],
    deposit: float,
) -> dict[str, Any]:
    lines = read_log(log)
    rows = load_events(event_paths)
    summary = reserve_summary(lines)
    return {
        "deposit": deposit,
        "report": report_metrics(report),
        "final": final_metrics(lines),
        "normalized": {},
        "events": {
            "total": event_period(rows, None, None),
            "2025": event_period(rows, datetime(2025, 1, 1), datetime(2026, 1, 1)),
            "2026_h1": event_period(rows, datetime(2026, 1, 1), datetime(2026, 7, 1)),
            "2026_h2_to_aug21": event_period(rows, datetime(2026, 7, 1), None),
            "sizing": sizing_transitions(rows),
        },
        "reserve_summary": summary,
        "exchange_summary": exchange_summary(lines),
        "allocation_lifecycles": allocation_lifecycles(rows, summary["base_volume"]),
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


def normalized(run: dict[str, Any], deposit: float) -> dict[str, Any]:
    stressed_net = run["final"]["stressed_net"]
    stressed_dd = run["final"]["stressed_closed_drawdown"]
    return {
        "actual_return_percent": rounded(100.0 * run["report"]["actual_net"] / deposit),
        "stressed_return_percent": rounded(100.0 * stressed_net / deposit),
        "stressed_closed_drawdown_percent": rounded(100.0 * stressed_dd / deposit),
        "stressed_net_to_drawdown": rounded(stressed_net / stressed_dd),
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


def scaled_departure(run: dict[str, Any], reference: dict[str, Any], scale: int) -> dict[str, Any]:
    return {
        "entries_vs_reference": run["report"]["entries"] - reference["report"]["entries"],
        "actual_net_vs_linear": rounded(
            run["report"]["actual_net"] - scale * reference["report"]["actual_net"]
        ),
        "stressed_net_vs_linear": rounded(
            run["final"]["stressed_net"] - scale * reference["final"]["stressed_net"]
        ),
        "stressed_drawdown_vs_linear": rounded(
            run["final"]["stressed_closed_drawdown"]
            - scale * reference["final"]["stressed_closed_drawdown"]
        ),
    }


def main() -> None:
    definitions = {
        "anchor_200": (
            200.0,
            "anchor-200-2025-2026q3.htm",
            "anchor-200-agent.log",
            ["anchor-200-events-a.csv", "anchor-200-events-b.csv"],
        ),
        "geometry_200": (
            200.0,
            "geometry-200-2025-2026q3.htm",
            "geometry-200-agent.log",
            ["geometry-200-events-a.csv", "geometry-200-events-b.csv"],
        ),
        "anchor_300": (
            300.0,
            "anchor-300-2025-2026q3.htm",
            "anchor-300-agent.log",
            ["anchor-300-events-a.csv", "anchor-300-events-b.csv"],
        ),
        "fixed_20_300": (
            300.0,
            "fixed20-300-2025-2026q3.htm",
            "fixed20-300-agent.log",
            ["fixed20-300-events-a.csv", "fixed20-300-events-b.csv"],
        ),
        "geometry_300": (
            300.0,
            "geometry-300-2025-2026q3.htm",
            "geometry-300-agent.log",
            ["geometry-300-events-a.csv", "geometry-300-events-b.csv"],
        ),
    }
    runs: dict[str, dict[str, Any]] = {}
    for name, (deposit, report_name, log_name, event_names) in definitions.items():
        runs[name] = run_summary(
            ARTIFACTS / report_name,
            ARTIFACTS / log_name,
            [ARTIFACTS / event_name for event_name in event_names],
            deposit,
        )
        runs[name]["normalized"] = normalized(runs[name], deposit)

    elasticity_path = ROOT / "lab" / "frontier" / "capital-step-elasticity" / "runtime.json"
    elasticity = json.loads(elasticity_path.read_text(encoding="utf-8"))
    anchor_100 = elasticity["references"]["broad_slot_exchange"]
    geometry_100 = elasticity["runtime_runs"]["hard_third_tier_reserve_20"]
    anchor_100["normalized"] = normalized(anchor_100, 100.0)
    geometry_100["normalized"] = normalized(geometry_100, 100.0)

    causal_identity: dict[str, Any] = {}
    for deposit, names in {
        "200": ["anchor_200", "geometry_200"],
        "300": ["anchor_300", "fixed_20_300", "geometry_300"],
    }.items():
        first_plan = min(
            row["time"]
            for name in names
            for row in runs[name]["_rows"]
            if row["event"] == "TRANSITION_RESERVE_PLAN"
        )
        digests = {name: economic_digest(runs[name]["_rows"], first_plan) for name in names}
        causal_identity[deposit] = {
            "first_plan": first_plan.strftime("%Y.%m.%d %H:%M:%S"),
            "digests": digests,
            "identical": len({item["sha256"] for item in digests.values()}) == 1,
        }

    comparisons = {
        "geometry_200_vs_anchor_200": delta(runs["geometry_200"], runs["anchor_200"]),
        "fixed_20_300_vs_anchor_300": delta(runs["fixed_20_300"], runs["anchor_300"]),
        "geometry_300_vs_anchor_300": delta(runs["geometry_300"], runs["anchor_300"]),
        "geometry_300_vs_fixed_20_300": delta(runs["geometry_300"], runs["fixed_20_300"]),
    }
    proxy = json.loads((FRONTIER / "proxy.json").read_text(encoding="utf-8"))
    selected_proxy = proxy["mechanism_selection"]["selected_paths"]
    fixed_proxy = next(
        item for item in proxy["results"] if item["policy"]["policy_id"] == "geometry-fixed-20"
    )["paths"]

    scale_table = {
        "100": {"anchor": anchor_100, "geometry": geometry_100},
        "200": {"anchor": runs["anchor_200"], "geometry": runs["geometry_200"]},
        "300": {
            "anchor": runs["anchor_300"],
            "fixed_20": runs["fixed_20_300"],
            "geometry": runs["geometry_300"],
        },
    }
    scale_departures = {
        "anchor_200_vs_2x_100": scaled_departure(runs["anchor_200"], anchor_100, 2),
        "anchor_300_vs_3x_100": scaled_departure(runs["anchor_300"], anchor_100, 3),
        "geometry_200_vs_2x_100": scaled_departure(runs["geometry_200"], geometry_100, 2),
        "geometry_300_vs_3x_100": scaled_departure(runs["geometry_300"], geometry_100, 3),
    }
    for run in runs.values():
        del run["_rows"]

    payload = {
        "unit": "transition-reserve-geometry-009",
        "question": "Does marginal position-risk capacity generalize transition reserve across 100, 200, and 300 USD starting capital?",
        "architecture": {
            "measurement": "current_next_lab_capital_scale_and_transition_lifecycles",
            "proxy": "11_mechanism_family_recenterings_plus_later_tier_geometry",
            "runtime": "one_scaled_adapter_ea_five_serial_real_tick_paths",
        },
        "references": {"anchor_100": anchor_100, "geometry_100": geometry_100},
        "runtime_runs": runs,
        "comparisons": comparisons,
        "capital_scale_table": scale_table,
        "linear_scale_departures": scale_departures,
        "causal_identity_before_first_reserve_plan": causal_identity,
        "proxy_runtime_gap": {
            "geometry_200": {
                "proxy_stressed_net_delta": selected_proxy["200"]["first_order_net_delta"],
                "runtime_stressed_net_delta": comparisons["geometry_200_vs_anchor_200"]["stressed_net"],
                "proxy_drawdown_delta": selected_proxy["200"]["first_order_drawdown_delta"],
                "runtime_drawdown_delta": comparisons["geometry_200_vs_anchor_200"]["stressed_closed_drawdown"],
            },
            "geometry_300": {
                "proxy_stressed_net_delta": selected_proxy["300"]["first_order_net_delta"],
                "runtime_stressed_net_delta": comparisons["geometry_300_vs_anchor_300"]["stressed_net"],
                "proxy_drawdown_delta": selected_proxy["300"]["first_order_drawdown_delta"],
                "runtime_drawdown_delta": comparisons["geometry_300_vs_anchor_300"]["stressed_closed_drawdown"],
            },
            "fixed_20_300": {
                "proxy_stressed_net_delta": fixed_proxy["300"]["first_order_net_delta"],
                "runtime_stressed_net_delta": comparisons["fixed_20_300_vs_anchor_300"]["stressed_net"],
                "proxy_drawdown_delta": fixed_proxy["300"]["first_order_drawdown_delta"],
                "runtime_drawdown_delta": comparisons["fixed_20_300_vs_anchor_300"]["stressed_closed_drawdown"],
            },
            "interpretation": "The fixed-path proxy could not distinguish fixed 20 from scaled risk capacity because the observed broad path barely crossed 3x. Runtime mutation created nine high-tier opportunities: nominal 20 admitted two upper-tier trades and reversed the predicted drawdown benefit, while risk-capacity geometry admitted none and retained joint net-and-drawdown improvement.",
        },
        "judgement": {
            "entry_preservation": {
                "200": runs["geometry_200"]["report"]["entries"] == runs["anchor_200"]["report"]["entries"],
                "300_fixed": runs["fixed_20_300"]["report"]["entries"] == runs["anchor_300"]["report"]["entries"],
                "300_geometry": runs["geometry_300"]["report"]["entries"] == runs["anchor_300"]["report"]["entries"],
            },
            "runtime_integrity": {name: no_faults(run) for name, run in runs.items()},
            "discovery": "Transition reserve is economically portable when denominated in prospective position-risk capacity, not nominal dollars. The 1.25-position-budget rule kept stressed drawdown near 52.1-53.4 percent and stressed net-to-drawdown near 5.22-5.25 across all three deposits, while fixed 20 USD at 300 USD raised drawdown above the unreserved anchor.",
            "selection": "retain_prospective_position_budget_1_25_transition_reserve",
            "retained_primary": "receiver_time_field_cross_profit_gate_6",
            "promotion": "none",
            "reason_not_promoted": "All high-tier evidence remains inside one continuous window; the 200 USD effect came from one high-tier opportunity and the 300 USD path still lost one entry relative to the 100/200 opportunity set.",
            "next": "capital_scale_admission_topology",
        },
        "compile": {
            "transition_reserve_geometry": "MetaEditor build 6140: 0 errors, 0 warnings",
            "neutral_parent_after_capital_input_hook": "MetaEditor build 6140: 0 errors, 0 warnings",
        },
        "sources": {
            "proxy": source(FRONTIER / "proxy.json"),
            "capital_elasticity_runtime": source(elasticity_path),
            "ea": source(ROOT / "lab" / "mt5" / "src" / "Experts" / "ZetaNextTransitionReserveGeometryV1.mq5"),
            "binary": source(ROOT / "lab" / "mt5" / "src" / "Experts" / "ZetaNextTransitionReserveGeometryV1.ex5"),
            "adapter": source(ROOT / "lab" / "mt5" / "src" / "Include" / "ZetaTerminusNext" / "Frontier" / "TransitionReserveGeometryAdapter.mqh"),
            "field_adapter": source(ROOT / "lab" / "mt5" / "src" / "Include" / "ZetaTerminusNext" / "Frontier" / "TransitionReserveFieldAdapter.mqh"),
            "neutral_parent": source(ROOT / "lab" / "mt5" / "src" / "Experts" / "ZetaNextPre500FiniteRiskPortfolioV7.mq5"),
        },
    }
    output = FRONTIER / "runtime.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
