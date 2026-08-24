#!/usr/bin/env python3
"""Predeclared proxy screen for the Lab-only deposit/capital/risk-capacity family."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


COMPONENTS = {
    0: "RC16",
    1: "RC4",
    2: "CROSS",
    3: "PRESSURE",
    4: "RETURN",
    5: "PASSIVE",
}

SYMBOLS = {
    0: "US30",
    1: "US30",
    2: "US100",
    3: "US30",
    4: "US30",
    5: "US100",
}

# Frozen physical order after ProcessClosures: Passive, RC4, RC16, Pressure,
# Return, Cross. It matters only when independent entries share a timestamp.
PHYSICAL_PRIORITY = {5: 0, 1: 1, 0: 2, 3: 3, 4: 4, 2: 5}

START = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp())
MID = int(datetime(2024, 7, 1, tzinfo=timezone.utc).timestamp())
END = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp())

PERIODS = {
    "2024_H1": (START, MID),
    "2024_H2": (MID, END),
    "2024_FULL": (START, END),
}

DEPOSITS = (200, 300)


@dataclass(frozen=True)
class ProxyTrade:
    component: int
    opportunity_id: int
    decision_bar: int
    entry_server: int
    exit_server: int
    actual_net: float
    stressed_fixed_path: float
    stressed_r_invariant: float
    stressed_conservative: float
    planned_risk: float
    volume_units: float


@dataclass
class Simulation:
    trades: list[ProxyTrade]
    rejected: int = 0
    interventions: int = 0


def parse_args() -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    root = script_path.parents[3]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--logs-root",
        type=Path,
        default=root
        / "lab"
        / "artifacts"
        / "backtests"
        / "strategy-independence-risk-allocation",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "lab" / "evidence" / "DEPOSIT_CAPITAL_RISK_CAPACITY_PROXY_V1.json",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_sira_analysis(root: Path):
    source = (
        root
        / "lab"
        / "research"
        / "strategy-independence-risk-allocation"
        / "analyze_strategy_independence_risk_allocation_v1.py"
    )
    spec = importlib.util.spec_from_file_location("zeta_sira_analysis_v1", source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {source}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, source


def to_proxy(
    trade,
    *,
    actual_factor: float,
    fixed_factor: float,
    planned_risk: float,
    volume_units: float,
) -> ProxyTrade:
    if trade.planned_risk <= 0.0 or planned_risk <= 0.0:
        raise ValueError("non-positive planned risk")
    fixed = trade.stressed_net * fixed_factor
    r_invariant = trade.stressed_net * (planned_risk / trade.planned_risk)
    return ProxyTrade(
        component=trade.component,
        opportunity_id=trade.opportunity_id,
        decision_bar=trade.decision_bar,
        entry_server=trade.entry_server,
        exit_server=trade.exit_server,
        actual_net=trade.actual_net * actual_factor,
        stressed_fixed_path=fixed,
        stressed_r_invariant=r_invariant,
        stressed_conservative=min(fixed, r_invariant),
        planned_risk=planned_risk,
        volume_units=volume_units,
    )


def direct_path(trades, deposit: int, factor: float) -> Simulation:
    return Simulation(
        trades=[
            to_proxy(
                trade,
                actual_factor=factor,
                fixed_factor=factor,
                planned_risk=trade.planned_risk * factor,
                volume_units=factor,
            )
            for trade in trades
        ]
    )


def capacity_path(
    trades,
    *,
    deposit: int,
    maximum_slots: int,
    position_fraction: float | None,
    volume_units: float,
    maximum_symbol_slots: int | None = None,
    fixed_dollar_risk: bool = False,
) -> Simulation:
    active: list[ProxyTrade] = []
    accepted: list[ProxyTrade] = []
    rejected = 0
    for trade in sorted(
        trades,
        key=lambda row: (
            row.entry_server,
            PHYSICAL_PRIORITY[row.component],
            row.opportunity_id,
        ),
    ):
        active = [row for row in active if row.exit_server > trade.entry_server]
        symbol = SYMBOLS[trade.component]
        symbol_count = sum(SYMBOLS[row.component] == symbol for row in active)
        if len(active) >= maximum_slots or (
            maximum_symbol_slots is not None and symbol_count >= maximum_symbol_slots
        ):
            rejected += 1
            continue
        planned = trade.planned_risk if fixed_dollar_risk else deposit * float(position_fraction)
        candidate = to_proxy(
            trade,
            actual_factor=volume_units,
            fixed_factor=volume_units,
            planned_risk=planned,
            volume_units=volume_units,
        )
        accepted.append(candidate)
        active.append(candidate)
    return Simulation(trades=accepted, rejected=rejected)


def replay_variable_units(
    trades,
    *,
    deposit: int,
    policy: str,
) -> Simulation:
    initial_units = deposit // 100
    cumulative_stress = 0.0
    peak = 0.0
    current_day = None
    day_units = initial_units
    active: dict[int, tuple[object, int, float]] = {}
    completed: list[ProxyTrade] = []
    interventions = 0
    brake_active = False
    brake_recovery_level = 0.0

    events: list[tuple[int, int, int, int, object]] = []
    for index, trade in enumerate(trades):
        events.append((trade.exit_server, 0, PHYSICAL_PRIORITY[trade.component], index, trade))
        events.append((trade.entry_server, 1, PHYSICAL_PRIORITY[trade.component], index, trade))
    events.sort()

    for server, kind, _, index, trade in events:
        if kind == 0:
            active_row = active.pop(index)
            _, units, planned = active_row
            fixed = trade.stressed_net * units
            r_invariant = trade.stressed_net * (planned / trade.planned_risk)
            conservative = min(fixed, r_invariant)
            cumulative_stress += conservative
            if policy == "DRAWDOWN_TRANCHE_BRAKE":
                if brake_active:
                    if cumulative_stress >= brake_recovery_level:
                        brake_active = False
                        peak = max(peak, cumulative_stress)
                else:
                    peak = max(peak, cumulative_stress)
                    if peak - cumulative_stress >= 0.06 * deposit:
                        brake_active = True
                        brake_recovery_level = peak
            completed.append(
                ProxyTrade(
                    component=trade.component,
                    opportunity_id=trade.opportunity_id,
                    decision_bar=trade.decision_bar,
                    entry_server=trade.entry_server,
                    exit_server=trade.exit_server,
                    actual_net=trade.actual_net * units,
                    stressed_fixed_path=fixed,
                    stressed_r_invariant=r_invariant,
                    stressed_conservative=conservative,
                    planned_risk=planned,
                    volume_units=float(units),
                )
            )
            continue

        day = server // 86400
        if day != current_day:
            current_day = day
            if policy == "FIXED_LOT_LADDER":
                day_units = initial_units + int(math.floor(max(0.0, cumulative_stress) / 150.0 + 1.0e-12))
            elif policy == "DRAWDOWN_TRANCHE_BRAKE":
                day_units = max(1, initial_units - (1 if brake_active else 0))
            else:
                raise ValueError(policy)
        if day_units != initial_units:
            interventions += 1
        if policy == "FIXED_LOT_LADDER":
            capital = max(1.0, deposit + cumulative_stress)
            planned = 0.04 * capital
        else:
            planned = 4.0 * day_units
        active[index] = (trade, day_units, planned)

    if active:
        raise ValueError(f"unclosed proxy trades: {sorted(active)}")
    return Simulation(trades=completed, interventions=interventions)


def maximum_closed_drawdown(trades: list[ProxyTrade], field: str) -> float:
    balance = 0.0
    peak = 0.0
    maximum = 0.0
    for trade in sorted(
        trades, key=lambda row: (row.exit_server, PHYSICAL_PRIORITY[row.component], row.opportunity_id)
    ):
        balance += getattr(trade, field)
        peak = max(peak, balance)
        maximum = max(maximum, peak - balance)
    return maximum


def period_summary(
    trades: list[ProxyTrade],
    *,
    deposit: int,
    start: int,
    end: int,
) -> dict[str, float | int]:
    selected = [trade for trade in trades if start <= trade.decision_bar < end]
    actual = sum(trade.actual_net for trade in selected)
    fixed = sum(trade.stressed_fixed_path for trade in selected)
    r_invariant = sum(trade.stressed_r_invariant for trade in selected)
    conservative = sum(trade.stressed_conservative for trade in selected)
    fixed_dd = maximum_closed_drawdown(selected, "stressed_fixed_path")
    r_dd = maximum_closed_drawdown(selected, "stressed_r_invariant")
    conservative_dd = maximum_closed_drawdown(selected, "stressed_conservative")
    return {
        "trade_count": len(selected),
        "win_count_conservative": sum(trade.stressed_conservative > 0.0 for trade in selected),
        "actual_net_usd_fixed_path": actual,
        "stressed_net_usd_fixed_path": fixed,
        "stressed_net_usd_r_invariant": r_invariant,
        "stressed_net_usd_conservative": conservative,
        "stressed_return_pct_conservative": 100.0 * conservative / deposit,
        "stressed_max_closed_drawdown_usd_fixed_path": fixed_dd,
        "stressed_max_closed_drawdown_usd_r_invariant": r_dd,
        "stressed_max_closed_drawdown_usd_conservative": conservative_dd,
        "stressed_max_closed_drawdown_pct_conservative": 100.0 * conservative_dd / deposit,
        "stressed_net_to_drawdown_conservative": (
            conservative / conservative_dd if conservative_dd > 0.0 else 0.0
        ),
        "planned_risk_usd": sum(trade.planned_risk for trade in selected),
        "average_volume_units": (
            sum(trade.volume_units for trade in selected) / len(selected) if selected else 0.0
        ),
    }


def summarize(simulation: Simulation, deposit: int) -> dict[str, object]:
    return {
        "deposit_usd": deposit,
        "accepted_trade_count": len(simulation.trades),
        "rejected_trade_count": simulation.rejected,
        "policy_intervention_count": simulation.interventions,
        "periods": {
            name: period_summary(simulation.trades, deposit=deposit, start=start, end=end)
            for name, (start, end) in PERIODS.items()
        },
        "component_trade_counts": {
            COMPONENTS[component]: sum(trade.component == component for trade in simulation.trades)
            for component in COMPONENTS
        },
    }


def trade_keys(simulation: Simulation) -> set[tuple[int, int, int]]:
    return {
        (trade.component, trade.decision_bar, trade.entry_server)
        for trade in simulation.trades
    }


def evaluate_candidate(
    candidate_name: str,
    results: dict[str, dict[str, object]],
    linear: dict[str, dict[str, object]],
    controls: dict[int, Simulation],
    simulations: dict[tuple[str, int], Simulation],
    group: str,
) -> dict[str, object]:
    reasons: list[str] = []
    efficiency_deltas: list[float] = []
    drawdowns: list[float] = []
    intervention_counts: list[int] = []
    for deposit in DEPOSITS:
        candidate_periods = results[str(deposit)]["periods"]
        linear_periods = linear[str(deposit)]["periods"]
        for period in ("2024_H1", "2024_H2", "2024_FULL"):
            if candidate_periods[period]["stressed_net_usd_conservative"] <= 0.0:
                reasons.append(f"{deposit}:{period}:nonpositive_net")
        candidate_full = candidate_periods["2024_FULL"]
        linear_full = linear_periods["2024_FULL"]
        if (
            candidate_full["stressed_max_closed_drawdown_pct_conservative"]
            > linear_full["stressed_max_closed_drawdown_pct_conservative"] + 1.0e-9
        ):
            reasons.append(f"{deposit}:full_drawdown_worse")
        delta = (
            candidate_full["stressed_net_to_drawdown_conservative"]
            - linear_full["stressed_net_to_drawdown_conservative"]
        )
        efficiency_deltas.append(delta)
        if delta <= 0.0:
            reasons.append(f"{deposit}:efficiency_not_better")
        drawdowns.append(candidate_full["stressed_max_closed_drawdown_pct_conservative"])
        simulation = simulations[(candidate_name, deposit)]
        if group == "capacity":
            interventions = len(trade_keys(simulation) ^ trade_keys(controls[deposit]))
        else:
            interventions = simulation.interventions
        intervention_counts.append(interventions)
    minimum_required = 12 if group == "capacity" else 20
    if sum(intervention_counts) < minimum_required:
        reasons.append(f"interventions_below_{minimum_required}")
    return {
        "group": group,
        "economically_eligible": not reasons,
        "failure_reasons": reasons,
        "minimum_efficiency_improvement": min(efficiency_deltas),
        "worst_full_drawdown_pct": max(drawdowns),
        "intervention_counts_by_deposit": {
            str(deposit): intervention_counts[index] for index, deposit in enumerate(DEPOSITS)
        },
        "ranking_tuple": [
            min(efficiency_deltas),
            -max(drawdowns),
            -sum(intervention_counts),
        ],
    }


def choose_group(evaluations: dict[str, dict[str, object]], group: str) -> dict[str, object]:
    rows = [(name, row) for name, row in evaluations.items() if row["group"] == group]
    eligible = [(name, row) for name, row in rows if row["economically_eligible"]]
    pool = eligible if eligible else rows
    name, row = max(pool, key=lambda item: tuple(item[1]["ranking_tuple"]))
    return {
        "hypothesis": name,
        "proxy_status": "ELIGIBLE" if row["economically_eligible"] else "DIAGNOSTIC_ONLY",
        "selection_basis": "eligible_pool" if eligible else "diagnostic_fallback",
        "ranking_tuple": row["ranking_tuple"],
    }


def main() -> None:
    args = parse_args()
    script_path = Path(__file__).resolve()
    root = script_path.parents[3]
    sira, sira_source = load_sira_analysis(root)

    log_paths = {
        "control": args.logs_root / "selection-2024-control-agent.log",
        "rc16": args.logs_root / "selection-2024-rc16-agent.log",
        "rc4": args.logs_root / "selection-2024-rc4-agent.log",
        "cross": args.logs_root / "selection-2024-cross-agent.log",
        "pressure": args.logs_root / "selection-2024-pressure-agent.log",
        "return": args.logs_root / "selection-2024-return-agent.log",
        "passive": args.logs_root / "selection-2024-passive-agent.log",
    }
    for path in log_paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)

    _, _, control_trades = sira.build_trades(log_paths["control"])
    standalone = []
    for component, run in enumerate(("rc16", "rc4", "cross", "pressure", "return", "passive")):
        _, _, trades = sira.build_trades(log_paths[run], expected_component=component)
        standalone.extend(trades)

    if len(control_trades) != 554 or len(standalone) != 571:
        raise ValueError(
            f"unexpected source lifecycle counts control={len(control_trades)} standalone={len(standalone)}"
        )
    if any(abs(trade.volume - 0.01) > 1.0e-8 for trade in control_trades + standalone):
        raise ValueError("proxy requires fresh-2024 0.01 source lifecycles")

    simulations: dict[tuple[str, int], Simulation] = {}
    controls: dict[int, Simulation] = {}
    for deposit in DEPOSITS:
        units = deposit / 100.0
        controls[deposit] = direct_path(control_trades, deposit, 1.0)
        simulations[("DEPOSIT_ONLY_RESERVE", deposit)] = controls[deposit]
        simulations[("LINEAR_CAPITAL", deposit)] = direct_path(control_trades, deposit, units)
        simulations[("FIXED_LOT_LADDER", deposit)] = replay_variable_units(
            control_trades, deposit=deposit, policy="FIXED_LOT_LADDER"
        )
        simulations[("DRAWDOWN_TRANCHE_BRAKE", deposit)] = replay_variable_units(
            control_trades, deposit=deposit, policy="DRAWDOWN_TRANCHE_BRAKE"
        )
        simulations[("FOUR_SLOT_LINEAR", deposit)] = capacity_path(
            standalone,
            deposit=deposit,
            maximum_slots=4,
            position_fraction=0.03,
            volume_units=units,
        )
        simulations[("SIX_SLOT_LINEAR", deposit)] = capacity_path(
            standalone,
            deposit=deposit,
            maximum_slots=6,
            position_fraction=0.02,
            volume_units=units,
        )
        simulations[("BREADTH_DOLLAR_SLOTS", deposit)] = capacity_path(
            standalone,
            deposit=deposit,
            maximum_slots=min(6, int(3 * units)),
            position_fraction=None,
            volume_units=1.0,
            fixed_dollar_risk=True,
        )
        simulations[("SYMBOL_BUCKET_CAP", deposit)] = capacity_path(
            standalone,
            deposit=deposit,
            maximum_slots=3,
            maximum_symbol_slots=2,
            position_fraction=0.04,
            volume_units=units,
        )

    hypotheses = sorted({name for name, _ in simulations})
    results: dict[str, dict[str, dict[str, object]]] = {}
    for name in hypotheses:
        results[name] = {
            str(deposit): summarize(simulations[(name, deposit)], deposit)
            for deposit in DEPOSITS
        }

    candidate_groups = {
        "FOUR_SLOT_LINEAR": "capacity",
        "SIX_SLOT_LINEAR": "capacity",
        "BREADTH_DOLLAR_SLOTS": "capacity",
        "SYMBOL_BUCKET_CAP": "capacity",
        "FIXED_LOT_LADDER": "sizing_governor",
        "DRAWDOWN_TRANCHE_BRAKE": "sizing_governor",
    }
    evaluations = {
        name: evaluate_candidate(
            name,
            results[name],
            results["LINEAR_CAPITAL"],
            controls,
            simulations,
            group,
        )
        for name, group in candidate_groups.items()
    }
    shortlist = [
        {
            "hypothesis": "LINEAR_CAPITAL",
            "proxy_status": "MANDATORY_STRUCTURAL_ANCHOR",
            "selection_basis": "predeclared",
        },
        choose_group(evaluations, "capacity"),
        choose_group(evaluations, "sizing_governor"),
    ]

    record = {
        "schema_version": 1,
        "record_type": "proxy_result",
        "research_family": "deposit-capital-risk-capacity",
        "version": "V1",
        "generated_on_kst": "2026-08-24",
        "declaration": {
            "path": "lab/evidence/DEPOSIT_CAPITAL_RISK_CAPACITY_DECLARATION_V1.json",
            "sha256": sha256(root / "lab" / "evidence" / "DEPOSIT_CAPITAL_RISK_CAPACITY_DECLARATION_V1.json"),
        },
        "analysis_source": {
            "path": str(script_path.relative_to(root)).replace("\\", "/"),
            "sha256": sha256(script_path),
            "sira_parser_path": str(sira_source.relative_to(root)).replace("\\", "/"),
            "sira_parser_sha256": sha256(sira_source),
        },
        "source_logs": {
            name: {
                "path": str(path.relative_to(root)).replace("\\", "/"),
                "sha256": sha256(path),
            }
            for name, path in log_paths.items()
        },
        "integrity": {
            "control_lifecycles": len(control_trades),
            "standalone_lifecycles": len(standalone),
            "all_source_volumes_0_01": true,
            "proxy_period": "2024-01-01/2025-01-01",
            "selection_or_later_candidate_outcomes_consumed": false,
        },
        "results": results,
        "candidate_evaluations": evaluations,
        "ea_shortlist": shortlist,
        "limitations": [
            "standalone merging omits replacement signals after a rejected lifecycle",
            "changed-stop variants use the predeclared fixed-path and R-invariant endpoint envelopes",
            "shared equity, margin, passive pending orders, RC4 feedback, rounding, and execution require MT5",
            "proxy is hypothesis screening rather than profit proof",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"ea_shortlist": shortlist, "candidate_evaluations": evaluations}, indent=2))


if __name__ == "__main__":
    main()
