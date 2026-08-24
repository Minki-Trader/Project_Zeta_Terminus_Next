#!/usr/bin/env python3
"""Analyze the Lab-only strategy independence and risk allocation ledgers."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


COMPONENTS = {
    0: "RC16",
    1: "RC4",
    2: "CROSS",
    3: "PRESSURE",
    4: "RETURN",
    5: "PASSIVE",
}

STANDALONE_RUNS = {
    0: "rc16",
    1: "rc4",
    2: "cross",
    3: "pressure",
    4: "return",
    5: "passive",
}

FIT_START = int(datetime(2022, 8, 1, tzinfo=timezone.utc).timestamp())
FIT_END = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp())
R_CLAMP_LOWER = -3.0
R_CLAMP_UPPER = 3.0
CONSERVATIVE_Z = 1.28155
OVERLAP_PSEUDO_OBSERVATIONS = 20
SELECTION_START = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp())
SELECTION_MID = int(datetime(2024, 7, 1, tzinfo=timezone.utc).timestamp())
SELECTION_END = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp())

SELECTION_PERIODS = {
    "2024_H1": (SELECTION_START, SELECTION_MID),
    "2024_H2": (SELECTION_MID, SELECTION_END),
    "2024_FULL": (SELECTION_START, SELECTION_END),
}

PORTFOLIO_RUNS = {
    "FIRST_COME": "control",
    "WIN_PROB_RESERVE_ONE": "policy-win",
    "CONSERVATIVE_R_RESERVE_ONE": "policy-r",
    "OVERLAP_AWARE_RESERVE_ONE": "policy-overlap",
}

COMPONENT_IDS = {
    0: "ZT-M30-US30-RANGE-COMP-61f61deaba",
    1: "ZT-M30-US30-RANGE-COMP-64efb16616",
    2: "ZT-H1-US100-CROSS-IN-14b72317b7",
    3: "ZT-M30-US30-INTRADAY-R-2eb111fc46",
    4: "ZT-H1-US30-RETURN-I-c870a788ec",
    5: "ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8",
}

COMPONENT_BY_ID = {value: key for key, value in COMPONENT_IDS.items()}


@dataclass(frozen=True)
class Opportunity:
    line_number: int
    opportunity_id: int
    server: int
    bar: int
    deadline: int
    selected: int
    component: int
    direction: int
    signal: float
    outcome: str
    active_mask: int
    aggregate_risk: float
    risk_capital: float
    equity: float
    margin: float
    rc4_shadow: int
    order_price: float
    volume: float
    stop_loss: float
    planned_risk: float


@dataclass(frozen=True)
class Event:
    line_number: int
    server: int
    opportunity_id: int
    component: int
    name: str
    value_a: float
    value_b: float
    detail: str


@dataclass
class Trade:
    component: int
    opportunity_id: int
    decision_bar: int
    entry_server: int
    exit_server: int
    direction: int
    signal: float
    volume: float
    planned_risk: float
    actual_net: float
    stressed_net: float
    entry_event: str
    exit_event: str

    @property
    def stressed_r(self) -> float:
        if self.planned_risk <= 0.0:
            raise ValueError("trade has non-positive planned risk")
        return self.stressed_net / self.planned_risk

    @property
    def clamped_stressed_r(self) -> float:
        return min(R_CLAMP_UPPER, max(R_CLAMP_LOWER, self.stressed_r))


@dataclass
class FlowEdge:
    to_node: int
    reverse_index: int
    capacity: int
    cost: float
    trade_index: int | None


def parse_args() -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    repository_root = script_path.parents[3]
    default_logs = (
        repository_root
        / "lab"
        / "artifacts"
        / "backtests"
        / "strategy-independence-risk-allocation"
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("fit", "selection"))
    parser.add_argument("--logs-root", type=Path, default=default_logs)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ledger-output", type=Path)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_fields(payload: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for item in payload.strip().split("|"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        fields[key] = value
    return fields


def int_field(fields: dict[str, str], key: str) -> int:
    return int(fields[key])


def float_field(fields: dict[str, str], key: str) -> float:
    return float(fields[key])


def read_records(path: Path) -> tuple[list[Opportunity], list[Event], list[tuple[int, str, object]]]:
    opportunities: list[Opportunity] = []
    events: list[Event] = []
    ordered: list[tuple[int, str, object]] = []
    with path.open("r", encoding="utf-16-le", errors="strict") as handle:
        for line_number, line in enumerate(handle, start=1):
            if "SIRA_OPPORTUNITY|" in line:
                fields = parse_fields(line.split("SIRA_OPPORTUNITY|", 1)[1])
                record = Opportunity(
                    line_number=line_number,
                    opportunity_id=int_field(fields, "id"),
                    server=int_field(fields, "server"),
                    bar=int_field(fields, "bar"),
                    deadline=int_field(fields, "deadline"),
                    selected=int_field(fields, "selected"),
                    component=int_field(fields, "component"),
                    direction=int_field(fields, "direction"),
                    signal=float_field(fields, "signal"),
                    outcome=fields["outcome"],
                    active_mask=int_field(fields, "active_mask"),
                    aggregate_risk=float_field(fields, "aggregate_risk"),
                    risk_capital=float_field(fields, "risk_capital"),
                    equity=float_field(fields, "equity"),
                    margin=float_field(fields, "margin"),
                    rc4_shadow=int_field(fields, "rc4_shadow"),
                    order_price=float_field(fields, "order_price"),
                    volume=float_field(fields, "volume"),
                    stop_loss=float_field(fields, "stop_loss"),
                    planned_risk=float_field(fields, "planned_risk"),
                )
                opportunities.append(record)
                ordered.append((line_number, "opportunity", record))
            elif "SIRA_EVENT|" in line:
                fields = parse_fields(line.split("SIRA_EVENT|", 1)[1])
                record = Event(
                    line_number=line_number,
                    server=int_field(fields, "server"),
                    opportunity_id=int_field(fields, "opportunity"),
                    component=int_field(fields, "component"),
                    name=fields["name"],
                    value_a=float_field(fields, "value_a"),
                    value_b=float_field(fields, "value_b"),
                    detail=fields.get("detail", ""),
                )
                events.append(record)
                ordered.append((line_number, "event", record))
    ordered.sort(key=lambda row: row[0])
    return opportunities, events, ordered


def detail_number(detail: str, key: str) -> float | None:
    match = re.search(rf"(?:^|\s){re.escape(key)}=(-?\d+(?:\.\d+)?)", detail)
    return None if match is None else float(match.group(1))


def build_trades(path: Path, expected_component: int | None = None) -> tuple[list[Opportunity], list[Event], list[Trade]]:
    opportunities, events, ordered = read_records(path)
    opportunity_by_id = {row.opportunity_id: row for row in opportunities}
    if len(opportunity_by_id) != len(opportunities):
        raise ValueError(f"duplicate opportunity id in {path}")
    if expected_component is not None:
        wrong = [row for row in opportunities if row.component != expected_component]
        if wrong:
            raise ValueError(f"unexpected component in {path}: {wrong[0].component}")

    active: dict[int, Trade] = {}
    completed: list[Trade] = []
    pending_passive: Opportunity | None = None

    for _, kind, raw_record in ordered:
        if kind == "opportunity":
            opportunity = raw_record
            assert isinstance(opportunity, Opportunity)
            if opportunity.component == 5 and opportunity.outcome == "PENDING_ORDER":
                if pending_passive is not None:
                    raise ValueError(f"overlapping passive pending opportunities in {path}")
                pending_passive = opportunity
            continue

        event = raw_record
        assert isinstance(event, Event)
        if event.name == "OPEN":
            opportunity = opportunity_by_id.get(event.opportunity_id)
            if opportunity is None:
                raise ValueError(f"OPEN lacks opportunity {event.opportunity_id} in {path}")
            if event.component in active:
                raise ValueError(f"overlapping component lifecycle in {path}")
            risk = detail_number(event.detail, "planned_risk")
            if risk is None or risk <= 0.0:
                risk = opportunity.planned_risk
            active[event.component] = Trade(
                component=event.component,
                opportunity_id=opportunity.opportunity_id,
                decision_bar=opportunity.bar,
                entry_server=event.server,
                exit_server=0,
                direction=opportunity.direction,
                signal=opportunity.signal,
                volume=event.value_b,
                planned_risk=risk,
                actual_net=0.0,
                stressed_net=0.0,
                entry_event=event.name,
                exit_event="",
            )
        elif event.name == "PASSIVE_FILL":
            if pending_passive is None:
                raise ValueError(f"PASSIVE_FILL lacks pending opportunity in {path}")
            if event.component in active:
                raise ValueError(f"overlapping passive lifecycle in {path}")
            active[event.component] = Trade(
                component=event.component,
                opportunity_id=pending_passive.opportunity_id,
                decision_bar=pending_passive.bar,
                entry_server=event.server,
                exit_server=0,
                direction=pending_passive.direction,
                signal=pending_passive.signal,
                volume=event.value_b,
                planned_risk=pending_passive.planned_risk,
                actual_net=0.0,
                stressed_net=0.0,
                entry_event=event.name,
                exit_event="",
            )
            pending_passive = None
        elif event.name in {"PASSIVE_EXPIRE", "PASSIVE_CANCEL"}:
            if pending_passive is None:
                raise ValueError(f"{event.name} lacks pending opportunity in {path}")
            pending_passive = None
        elif event.name.endswith("_PARTIAL") and "CLOSE" in event.name:
            trade = active.get(event.component)
            if trade is None:
                raise ValueError(f"partial close lacks active lifecycle in {path}")
            trade.actual_net += event.value_a
            trade.stressed_net += event.value_b
        elif event.name in {"CLOSE", "EXTERNAL_CLOSE"}:
            trade = active.get(event.component)
            if trade is None:
                raise ValueError(f"final close lacks active lifecycle in {path}")
            trade.actual_net += event.value_a
            trade.stressed_net += event.value_b
            trade.exit_server = event.server
            trade.exit_event = event.name
            if trade.planned_risk <= 0.0 or trade.exit_server < trade.entry_server:
                raise ValueError(f"invalid completed lifecycle in {path}")
            completed.append(trade)
            del active[event.component]

    if active:
        raise ValueError(f"unclosed lifecycle(s) in {path}: {sorted(active)}")
    if pending_passive is not None:
        raise ValueError(f"unresolved passive pending opportunity in {path}")
    return opportunities, events, completed


def closed_drawdown(trades: Iterable[Trade], value: str) -> float:
    balance = 0.0
    peak = 0.0
    maximum = 0.0
    for trade in sorted(trades, key=lambda row: (row.exit_server, row.component, row.opportunity_id)):
        balance += getattr(trade, value)
        peak = max(peak, balance)
        maximum = max(maximum, peak - balance)
    return maximum


def mean_and_sample_sd(values: list[float]) -> tuple[float, float]:
    if not values:
        raise ValueError("cannot summarize an empty sample")
    return statistics.fmean(values), statistics.stdev(values) if len(values) > 1 else 0.0


def format_server_time(value: int) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def overlap_adjustments(trades_by_component: dict[int, list[Trade]]) -> dict[str, dict[str, dict[str, float | int]]]:
    output: dict[str, dict[str, dict[str, float | int]]] = {}
    base_means = {
        component: statistics.fmean([trade.clamped_stressed_r for trade in trades])
        for component, trades in trades_by_component.items()
    }
    for component, trades in trades_by_component.items():
        component_rows: dict[str, dict[str, float | int]] = {}
        for incumbent, incumbent_trades in trades_by_component.items():
            if incumbent == component:
                continue
            conditional = [
                trade.clamped_stressed_r
                for trade in trades
                if any(
                    other.entry_server <= trade.entry_server < other.exit_server
                    for other in incumbent_trades
                )
            ]
            conditional_mean = (
                statistics.fmean(conditional) if conditional else base_means[component]
            )
            shrunk_mean = (
                len(conditional) * conditional_mean
                + OVERLAP_PSEUDO_OBSERVATIONS * base_means[component]
            ) / (len(conditional) + OVERLAP_PSEUDO_OBSERVATIONS)
            component_rows[COMPONENTS[incumbent]] = {
                "overlap_trade_count": len(conditional),
                "conditional_mean_clamped_stressed_r": conditional_mean,
                "shrunk_mean_clamped_stressed_r": shrunk_mean,
                "adjustment_vs_component_mean": shrunk_mean - base_means[component],
            }
        output[COMPONENTS[component]] = component_rows
    return output


def period_trade_summary(trades: list[Trade], start: int, end: int) -> dict[str, float | int]:
    selected = [trade for trade in trades if start <= trade.decision_bar < end]
    planned_risk = sum(trade.planned_risk for trade in selected)
    stressed_net = sum(trade.stressed_net for trade in selected)
    return {
        "trade_count": len(selected),
        "win_count": sum(trade.stressed_net > 0.0 for trade in selected),
        "actual_net_usd": sum(trade.actual_net for trade in selected),
        "stressed_net_usd": stressed_net,
        "stressed_max_closed_drawdown_usd": closed_drawdown(selected, "stressed_net"),
        "planned_risk_usd": planned_risk,
        "stressed_net_per_planned_risk": (
            stressed_net / planned_risk if planned_risk > 0.0 else 0.0
        ),
    }


def summaries_by_period(trades: list[Trade]) -> dict[str, dict[str, float | int]]:
    return {
        period: period_trade_summary(trades, start, end)
        for period, (start, end) in SELECTION_PERIODS.items()
    }


def component_summaries(trades: list[Trade]) -> dict[str, dict[str, float | int]]:
    return {
        COMPONENTS[component]: period_trade_summary(
            [trade for trade in trades if trade.component == component],
            SELECTION_START,
            SELECTION_END,
        )
        for component in COMPONENTS
    }


def event_counts(events: list[Event]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        counts[event.name] = counts.get(event.name, 0) + 1
    return counts


def policy_intervention_summary(
    opportunities: list[Opportunity], events: list[Event]
) -> dict[str, object]:
    opportunity_by_id = {row.opportunity_id: row for row in opportunities}
    interventions = [
        event for event in events if event.name == "SIRA_POLICY_RESERVE_SKIP"
    ]
    current_components: set[int] = set()
    later_components: set[int] = set()
    incumbent_candidate_pairs: set[str] = set()
    active_masks: dict[str, int] = {}
    rows: list[dict[str, object]] = []
    for event in interventions:
        opportunity = opportunity_by_id[event.opportunity_id]
        current_components.add(event.component)
        active_names = [
            COMPONENTS[component]
            for component in COMPONENTS
            if opportunity.active_mask & (1 << component)
        ]
        for incumbent in active_names:
            incumbent_candidate_pairs.add(
                f"{incumbent}->{COMPONENTS[event.component]}"
            )
        mask_key = "+".join(active_names) if active_names else "NONE"
        active_masks[mask_key] = active_masks.get(mask_key, 0) + 1
        later_match = re.search(r"(?:^|\s)later_component=([^\s]+)", event.detail)
        later_component = (
            COMPONENT_BY_ID.get(later_match.group(1)) if later_match else None
        )
        if later_component is not None:
            later_components.add(later_component)
        rows.append(
            {
                "server": event.server,
                "server_time": format_server_time(event.server),
                "opportunity_id": event.opportunity_id,
                "current_component": COMPONENTS[event.component],
                "active_mask": opportunity.active_mask,
                "active_components": active_names,
                "later_component": (
                    COMPONENTS[later_component]
                    if later_component is not None
                    else None
                ),
                "detail": event.detail,
            }
        )
    return {
        "reservation_count": len(interventions),
        "current_component_count": len(current_components),
        "current_components": [COMPONENTS[value] for value in sorted(current_components)],
        "later_components": [COMPONENTS[value] for value in sorted(later_components)],
        "distinct_incumbent_candidate_pair_count": len(incumbent_candidate_pairs),
        "incumbent_candidate_pairs": sorted(incumbent_candidate_pairs),
        "active_mask_counts": active_masks,
        "rows": rows,
    }


def maximum_concurrent_positions(trades: list[Trade]) -> int:
    points: list[tuple[int, int]] = []
    for trade in trades:
        points.append((trade.entry_server, 1))
        points.append((trade.exit_server, -1))
    active = 0
    maximum = 0
    for _, delta in sorted(points, key=lambda row: (row[0], row[1])):
        active += delta
        maximum = max(maximum, active)
    return maximum


def overlap_pair_summary(trades: list[Trade]) -> dict[str, object]:
    pair_counts: dict[str, int] = {}
    overlap_pairs = 0
    for index, left in enumerate(trades):
        for right in trades[index + 1 :]:
            if left.component == right.component:
                continue
            overlap_seconds = min(left.exit_server, right.exit_server) - max(
                left.entry_server, right.entry_server
            )
            if overlap_seconds <= 0:
                continue
            overlap_pairs += 1
            names = sorted((COMPONENTS[left.component], COMPONENTS[right.component]))
            key = f"{names[0]}+{names[1]}"
            pair_counts[key] = pair_counts.get(key, 0) + 1
    entries_with_incumbent = sum(
        any(
            other.component != trade.component
            and other.entry_server < trade.entry_server < other.exit_server
            for other in trades
        )
        for trade in trades
    )
    return {
        "position_overlap_pair_count": overlap_pairs,
        "pair_counts": dict(sorted(pair_counts.items())),
        "entries_with_earlier_incumbent_count": entries_with_incumbent,
        "maximum_concurrent_positions": maximum_concurrent_positions(trades),
    }


def pending_passive_at(
    opportunities: list[Opportunity], trades_by_opportunity: dict[int, Trade], server: int
) -> tuple[Opportunity | None, Trade | None]:
    candidates = [
        row
        for row in opportunities
        if row.component == 5
        and row.outcome == "PENDING_ORDER"
        and row.server <= server <= row.deadline
    ]
    if not candidates:
        return None, None
    opportunity = max(candidates, key=lambda row: row.server)
    trade = trades_by_opportunity.get(opportunity.opportunity_id)
    if trade is not None and trade.entry_server <= server:
        return None, None
    return opportunity, trade


def build_control_conflict_ledger(
    control_opportunities: list[Opportunity],
    control_events: list[Event],
    control_trades: list[Trade],
    standalone_opportunities: dict[int, list[Opportunity]],
    standalone_trades: dict[int, list[Trade]],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    control_opportunity_by_id = {
        row.opportunity_id: row for row in control_opportunities
    }
    control_trade_by_opportunity = {
        row.opportunity_id: row for row in control_trades
    }
    standalone_opportunity_by_key: dict[tuple[int, int, int], Opportunity] = {}
    standalone_trade_by_opportunity: dict[int, dict[int, Trade]] = {}
    for component, opportunities in standalone_opportunities.items():
        for opportunity in opportunities:
            standalone_opportunity_by_key[
                (component, opportunity.bar, opportunity.direction)
            ] = opportunity
        standalone_trade_by_opportunity[component] = {
            trade.opportunity_id: trade for trade in standalone_trades[component]
        }

    hard_skips = [
        event for event in control_events if event.name == "RISK_ADMISSION_SKIP"
    ]
    ledger: list[dict[str, object]] = []
    matched = 0
    matched_filled = 0
    matched_winners = 0
    winner_with_nonpositive_incumbent = 0
    winner_with_negative_incumbent_sum = 0
    candidate_counts: dict[str, int] = {}
    mask_counts: dict[str, int] = {}

    for event in hard_skips:
        opportunity = control_opportunity_by_id[event.opportunity_id]
        candidate_name = COMPONENTS[event.component]
        candidate_counts[candidate_name] = candidate_counts.get(candidate_name, 0) + 1
        active_components = [
            component
            for component in COMPONENTS
            if opportunity.active_mask & (1 << component)
        ]
        mask_name = "+".join(COMPONENTS[value] for value in active_components)
        mask_counts[mask_name] = mask_counts.get(mask_name, 0) + 1

        standalone_opportunity = standalone_opportunity_by_key.get(
            (event.component, opportunity.bar, opportunity.direction)
        )
        candidate_trade: Trade | None = None
        if standalone_opportunity is not None:
            matched += 1
            candidate_trade = standalone_trade_by_opportunity[event.component].get(
                standalone_opportunity.opportunity_id
            )
            if candidate_trade is not None:
                matched_filled += 1
                if candidate_trade.stressed_net > 0.0:
                    matched_winners += 1

        incumbents: list[dict[str, object]] = []
        known_incumbent_outcomes: list[float] = []
        for component in active_components:
            active_trade = next(
                (
                    trade
                    for trade in control_trades
                    if trade.component == component
                    and trade.entry_server <= event.server < trade.exit_server
                ),
                None,
            )
            if active_trade is not None:
                known_incumbent_outcomes.append(active_trade.stressed_net)
                incumbents.append(
                    {
                        "component": COMPONENTS[component],
                        "state": "POSITION",
                        "entry_server": active_trade.entry_server,
                        "exit_server": active_trade.exit_server,
                        "stressed_net_usd": active_trade.stressed_net,
                        "actual_net_usd": active_trade.actual_net,
                    }
                )
                continue
            if component == 5:
                pending_opportunity, pending_trade = pending_passive_at(
                    control_opportunities,
                    control_trade_by_opportunity,
                    event.server,
                )
                if pending_opportunity is not None:
                    pending_outcome = (
                        pending_trade.stressed_net if pending_trade is not None else 0.0
                    )
                    known_incumbent_outcomes.append(pending_outcome)
                    incumbents.append(
                        {
                            "component": "PASSIVE",
                            "state": "PENDING_ORDER",
                            "entry_server": (
                                pending_trade.entry_server
                                if pending_trade is not None
                                else None
                            ),
                            "exit_server": (
                                pending_trade.exit_server
                                if pending_trade is not None
                                else pending_opportunity.deadline
                            ),
                            "stressed_net_usd": pending_outcome,
                            "actual_net_usd": (
                                pending_trade.actual_net
                                if pending_trade is not None
                                else 0.0
                            ),
                        }
                    )
                    continue
            incumbents.append(
                {
                    "component": COMPONENTS[component],
                    "state": "UNRESOLVED_MASK_STATE",
                    "entry_server": None,
                    "exit_server": None,
                    "stressed_net_usd": None,
                    "actual_net_usd": None,
                }
            )

        candidate_stressed = (
            candidate_trade.stressed_net if candidate_trade is not None else None
        )
        any_nonpositive_incumbent = any(
            value <= 0.0 for value in known_incumbent_outcomes
        )
        incumbent_sum = sum(known_incumbent_outcomes)
        if candidate_stressed is not None and candidate_stressed > 0.0:
            if any_nonpositive_incumbent:
                winner_with_nonpositive_incumbent += 1
            if incumbent_sum < 0.0:
                winner_with_negative_incumbent_sum += 1

        ledger.append(
            {
                "server": event.server,
                "server_time": format_server_time(event.server),
                "control_opportunity_id": event.opportunity_id,
                "candidate_component": candidate_name,
                "candidate_bar": opportunity.bar,
                "candidate_direction": opportunity.direction,
                "candidate_signal": opportunity.signal,
                "active_mask": opportunity.active_mask,
                "active_components": [COMPONENTS[value] for value in active_components],
                "candidate_planned_risk_usd": event.value_a,
                "aggregate_after_usd": event.value_b,
                "standalone_opportunity_matched": standalone_opportunity is not None,
                "standalone_filled": candidate_trade is not None,
                "standalone_stressed_net_usd": candidate_stressed,
                "standalone_actual_net_usd": (
                    candidate_trade.actual_net if candidate_trade is not None else None
                ),
                "incumbents": incumbents,
                "known_incumbent_stressed_net_sum_usd": incumbent_sum,
                "blocked_winner_with_nonpositive_incumbent": (
                    candidate_stressed is not None
                    and candidate_stressed > 0.0
                    and any_nonpositive_incumbent
                ),
                "blocked_winner_with_negative_incumbent_sum": (
                    candidate_stressed is not None
                    and candidate_stressed > 0.0
                    and incumbent_sum < 0.0
                ),
            }
        )

    summary = {
        "hard_risk_skip_count": len(hard_skips),
        "standalone_opportunity_match_count": matched,
        "standalone_filled_match_count": matched_filled,
        "standalone_winner_count": matched_winners,
        "blocked_winner_with_nonpositive_incumbent_count": winner_with_nonpositive_incumbent,
        "blocked_winner_with_negative_incumbent_sum_count": winner_with_negative_incumbent_sum,
        "candidate_component_counts": dict(sorted(candidate_counts.items())),
        "active_mask_counts": dict(sorted(mask_counts.items())),
    }
    return ledger, summary


def add_flow_edge(
    graph: list[list[FlowEdge]],
    source: int,
    target: int,
    capacity: int,
    cost: float,
    trade_index: int | None = None,
) -> FlowEdge:
    forward = FlowEdge(target, len(graph[target]), capacity, cost, trade_index)
    reverse = FlowEdge(source, len(graph[source]), 0, -cost, None)
    graph[source].append(forward)
    graph[target].append(reverse)
    return forward


def oracle_capacity_three(staged_trades: list[Trade]) -> dict[str, object]:
    trades = [
        trade
        for trade in staged_trades
        if SELECTION_START <= trade.decision_bar < SELECTION_END
        and trade.volume > 0.0
    ]
    normalized_values = [
        trade.stressed_net * (0.01 / trade.volume) for trade in trades
    ]
    times = sorted(
        {value for trade in trades for value in (trade.entry_server, trade.exit_server)}
    )
    time_index = {value: index for index, value in enumerate(times)}
    graph: list[list[FlowEdge]] = [[] for _ in times]
    for index in range(len(times) - 1):
        add_flow_edge(graph, index, index + 1, 3, 0.0)
    trade_edges: list[FlowEdge | None] = [None] * len(trades)
    for index, (trade, value) in enumerate(zip(trades, normalized_values)):
        if value <= 0.0:
            continue
        trade_edges[index] = add_flow_edge(
            graph,
            time_index[trade.entry_server],
            time_index[trade.exit_server],
            1,
            -value,
            index,
        )

    source = 0
    sink = len(times) - 1
    for _ in range(3):
        distance = [math.inf] * len(times)
        predecessor: list[tuple[int, int] | None] = [None] * len(times)
        distance[source] = 0.0
        for _iteration in range(len(times) - 1):
            changed = False
            for node, edges in enumerate(graph):
                if not math.isfinite(distance[node]):
                    continue
                for edge_index, edge in enumerate(edges):
                    if edge.capacity <= 0:
                        continue
                    candidate = distance[node] + edge.cost
                    if candidate < distance[edge.to_node] - 1.0e-12:
                        distance[edge.to_node] = candidate
                        predecessor[edge.to_node] = (node, edge_index)
                        changed = True
            if not changed:
                break
        if predecessor[sink] is None:
            raise ValueError("oracle flow could not reach sink")
        node = sink
        while node != source:
            prior_node, edge_index = predecessor[node]
            edge = graph[prior_node][edge_index]
            edge.capacity -= 1
            graph[node][edge.reverse_index].capacity += 1
            node = prior_node

    selected_indices = [
        index
        for index, edge in enumerate(trade_edges)
        if edge is not None and edge.capacity == 0
    ]
    selected_trades = [trades[index] for index in selected_indices]
    selected_net = sum(normalized_values[index] for index in selected_indices)
    return {
        "diagnostic_only": True,
        "causal": False,
        "input_trade_count": len(trades),
        "selected_trade_count": len(selected_trades),
        "normalized_0_01_stressed_net_usd": selected_net,
        "maximum_concurrent_positions": maximum_concurrent_positions(selected_trades),
        "limitations": [
            "uses realized future standalone lifecycle outcomes",
            "uses only opportunities observed under each always-accept standalone path",
            "normalizes each lifecycle to 0.01 volume",
            "does not reproduce shared-account equity, margin, pending-order or path feedback",
        ],
    }


def selection_pass_result(
    portfolio_metrics: dict[str, dict[str, dict[str, float | int]]],
    interventions: dict[str, dict[str, object]],
) -> dict[str, object]:
    control = portfolio_metrics["FIRST_COME"]
    candidates: dict[str, dict[str, object]] = {}
    passing: list[str] = []
    for policy in (
        "WIN_PROB_RESERVE_ONE",
        "CONSERVATIVE_R_RESERVE_ONE",
        "OVERLAP_AWARE_RESERVE_ONE",
    ):
        metrics = portfolio_metrics[policy]
        net_pass = all(
            float(metrics[period]["stressed_net_usd"])
            > float(control[period]["stressed_net_usd"]) + 1.0e-9
            for period in SELECTION_PERIODS
        )
        drawdown_pass = all(
            float(metrics[period]["stressed_max_closed_drawdown_usd"])
            <= float(control[period]["stressed_max_closed_drawdown_usd"]) + 0.01
            for period in SELECTION_PERIODS
        )
        breadth_pass = (
            int(interventions[policy]["current_component_count"]) >= 2
            and int(
                interventions[policy]["distinct_incumbent_candidate_pair_count"]
            )
            >= 2
        )
        passed = net_pass and drawdown_pass and breadth_pass
        if passed:
            passing.append(policy)
        candidates[policy] = {
            "stressed_net_pass_all_three_periods": net_pass,
            "drawdown_pass_all_three_periods": drawdown_pass,
            "breadth_pass": breadth_pass,
            "passed": passed,
            "stressed_net_delta_usd": {
                period: float(metrics[period]["stressed_net_usd"])
                - float(control[period]["stressed_net_usd"])
                for period in SELECTION_PERIODS
            },
            "drawdown_delta_usd": {
                period: float(
                    metrics[period]["stressed_max_closed_drawdown_usd"]
                )
                - float(
                    control[period]["stressed_max_closed_drawdown_usd"]
                )
                for period in SELECTION_PERIODS
            },
        }
    selected_policy = None
    if passing:
        selected_policy = sorted(
            passing,
            key=lambda policy: (
                -float(portfolio_metrics[policy]["2024_FULL"]["stressed_net_usd"]),
                float(
                    portfolio_metrics[policy]["2024_FULL"][
                        "stressed_max_closed_drawdown_usd"
                    ]
                ),
                int(interventions[policy]["reservation_count"]),
            ),
        )[0]
    return {
        "candidates": candidates,
        "passing_policies": passing,
        "selected_policy": selected_policy,
        "verdict": (
            "SELECTION_POLICY_FIXED_FOR_2025_FORWARD"
            if selected_policy is not None
            else "NO_POLICY_PASSED_RETAIN_FIRST_COME"
        ),
    }


def run_fit(logs_root: Path, output: Path) -> None:
    analysis_path = Path(__file__).resolve()
    repository_root = analysis_path.parents[3]
    trades_by_component: dict[int, list[Trade]] = {}
    source_logs: dict[str, dict[str, str | int]] = {}
    scores: dict[str, dict[str, float | int | str]] = {}

    for component, run_name in STANDALONE_RUNS.items():
        path = logs_root / f"selection-2022-2024-{run_name}-agent.log"
        if not path.is_file():
            raise FileNotFoundError(path)
        _, _, all_trades = build_trades(path, expected_component=component)
        fit_trades = [
            trade
            for trade in all_trades
            if FIT_START <= trade.decision_bar < FIT_END
        ]
        if not fit_trades:
            raise ValueError(f"no fit trades for {COMPONENTS[component]}")
        if any(trade.decision_bar >= FIT_END for trade in fit_trades):
            raise AssertionError("selection-period trade entered fit sample")
        trades_by_component[component] = fit_trades
        source_logs[COMPONENTS[component]] = {
            "path": path.resolve().relative_to(repository_root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }

        clamped_r = [trade.clamped_stressed_r for trade in fit_trades]
        mean_r, sample_sd_r = mean_and_sample_sd(clamped_r)
        standard_error = sample_sd_r / math.sqrt(len(clamped_r))
        wins = sum(trade.stressed_net > 0.0 for trade in fit_trades)
        scores[COMPONENTS[component]] = {
            "component": component,
            "fit_trade_count": len(fit_trades),
            "fit_win_count": wins,
            "fit_loss_or_flat_count": len(fit_trades) - wins,
            "predicted_win_probability_beta_1_1": (wins + 1.0) / (len(fit_trades) + 2.0),
            "mean_clamped_stressed_r": mean_r,
            "sample_sd_clamped_stressed_r": sample_sd_r,
            "standard_error_clamped_stressed_r": standard_error,
            "conservative_stressed_r_score": mean_r - CONSERVATIVE_Z * standard_error,
            "actual_net_usd": sum(trade.actual_net for trade in fit_trades),
            "stressed_net_usd": sum(trade.stressed_net for trade in fit_trades),
            "stressed_max_closed_drawdown_usd": closed_drawdown(fit_trades, "stressed_net"),
            "first_decision_bar": format_server_time(min(trade.decision_bar for trade in fit_trades)),
            "last_decision_bar": format_server_time(max(trade.decision_bar for trade in fit_trades)),
        }

    overlap = overlap_adjustments(trades_by_component)
    fit_payload = {
        "schema_version": 1,
        "record_type": "fit_scores",
        "family_id": "strategy-independence-risk-allocation",
        "source_commit_required": "a5a3e01b05bcc7a890a4404a128142db1c3d3aae",
        "analysis_source": {
            "path": analysis_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(analysis_path),
        },
        "selection_rows_consumed": False,
        "fit_period": ["2022-08-01", "2024-01-01"],
        "score_contract": {
            "win_probability": "(wins+1)/(trades+2)",
            "stressed_r": "stressed_2x_cost_net/planned_risk",
            "stressed_r_clamp": [R_CLAMP_LOWER, R_CLAMP_UPPER],
            "conservative_z": CONSERVATIVE_Z,
            "overlap_pseudo_observations": OVERLAP_PSEUDO_OBSERVATIONS,
            "overlap_runtime_combination": "base conservative score plus the minimum active-incumbent adjustment; no active incumbent means zero adjustment",
        },
        "source_logs": source_logs,
        "component_scores": scores,
        "overlap_adjustments": overlap,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(fit_payload, handle, ensure_ascii=False, indent=2, sort_keys=False)
        handle.write("\n")
    print(
        json.dumps(
            {
                "output": str(output),
                "bytes": output.stat().st_size,
                "sha256": sha256(output),
                "fit_trade_counts": {
                    name: scores[name]["fit_trade_count"] for name in scores
                },
                "maximum_included_decision_bar": max(
                    scores[name]["last_decision_bar"] for name in scores
                ),
                "selection_rows_consumed": False,
            },
            ensure_ascii=False,
        )
    )


def run_selection(logs_root: Path, output: Path, ledger_output: Path) -> None:
    analysis_path = Path(__file__).resolve()
    repository_root = analysis_path.parents[3]
    source_logs: dict[str, dict[str, str | int]] = {}
    standalone_opportunities: dict[int, list[Opportunity]] = {}
    standalone_events: dict[int, list[Event]] = {}
    standalone_trades: dict[int, list[Trade]] = {}
    standalone_performance: dict[str, dict[str, dict[str, float | int]]] = {}

    for component, run_name in STANDALONE_RUNS.items():
        path = logs_root / f"selection-2024-{run_name}-agent.log"
        opportunities, events, trades = build_trades(
            path, expected_component=component
        )
        if any(
            not (SELECTION_START <= trade.decision_bar < SELECTION_END)
            for trade in trades
        ):
            raise ValueError(f"out-of-selection trade in {path}")
        standalone_opportunities[component] = opportunities
        standalone_events[component] = events
        standalone_trades[component] = trades
        standalone_performance[COMPONENTS[component]] = summaries_by_period(trades)
        source_logs[f"standalone_{run_name}"] = {
            "path": path.resolve().relative_to(repository_root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }

    portfolio_opportunities: dict[str, list[Opportunity]] = {}
    portfolio_events: dict[str, list[Event]] = {}
    portfolio_trades: dict[str, list[Trade]] = {}
    portfolio_performance: dict[str, dict[str, dict[str, float | int]]] = {}
    portfolio_component_performance: dict[
        str, dict[str, dict[str, float | int]]
    ] = {}
    interventions: dict[str, dict[str, object]] = {}

    for policy, run_name in PORTFOLIO_RUNS.items():
        path = logs_root / f"selection-2024-{run_name}-agent.log"
        opportunities, events, trades = build_trades(path)
        if any(
            not (SELECTION_START <= trade.decision_bar < SELECTION_END)
            for trade in trades
        ):
            raise ValueError(f"out-of-selection trade in {path}")
        portfolio_opportunities[policy] = opportunities
        portfolio_events[policy] = events
        portfolio_trades[policy] = trades
        portfolio_performance[policy] = summaries_by_period(trades)
        portfolio_component_performance[policy] = component_summaries(trades)
        interventions[policy] = policy_intervention_summary(opportunities, events)
        source_logs[f"portfolio_{run_name}"] = {
            "path": path.resolve().relative_to(repository_root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }

    control_opportunities = portfolio_opportunities["FIRST_COME"]
    control_events = portfolio_events["FIRST_COME"]
    control_trades = portfolio_trades["FIRST_COME"]
    conflict_ledger, conflict_summary = build_control_conflict_ledger(
        control_opportunities,
        control_events,
        control_trades,
        standalone_opportunities,
        standalone_trades,
    )
    ledger_output.parent.mkdir(parents=True, exist_ok=True)
    with ledger_output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in conflict_ledger:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=False))
            handle.write("\n")

    all_standalone_trades = [
        trade
        for component in COMPONENTS
        for trade in standalone_trades[component]
    ]
    selection_result = selection_pass_result(
        portfolio_performance, interventions
    )
    control_counts = event_counts(control_events)
    standalone_vs_control = {
        COMPONENTS[component]: {
            "standalone_trade_count": len(standalone_trades[component]),
            "control_trade_count": sum(
                trade.component == component for trade in control_trades
            ),
            "trade_count_delta_control_minus_standalone": sum(
                trade.component == component for trade in control_trades
            )
            - len(standalone_trades[component]),
        }
        for component in COMPONENTS
    }

    payload = {
        "schema_version": 1,
        "record_type": "selection_result",
        "family_id": "strategy-independence-risk-allocation",
        "source_commit_required": "9af70bf27b119a1aa9e28232a5890631cf806846",
        "selection_rows_consumed": True,
        "forward_2025_consumed": False,
        "selection_period": ["2024-01-01", "2025-01-01"],
        "account_initialization": "every run fresh 100 USD on 2024-01-01",
        "analysis_source": {
            "path": analysis_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(analysis_path),
        },
        "source_logs": source_logs,
        "standalone_performance": standalone_performance,
        "portfolio_performance": portfolio_performance,
        "portfolio_component_performance_2024_full": portfolio_component_performance,
        "policy_interventions": interventions,
        "first_come_overlap": overlap_pair_summary(control_trades),
        "standalone_vs_first_come_trade_counts": standalone_vs_control,
        "first_come_risk_events": {
            "hard_aggregate_risk_skips": control_counts.get(
                "RISK_ADMISSION_SKIP", 0
            ),
            "minimum_lot_risk_skips": control_counts.get("RISK_MIN_LOT_SKIP", 0),
        },
        "risk_conflict_summary": conflict_summary,
        "risk_conflict_ledger": {
            "path": ledger_output.resolve().relative_to(repository_root).as_posix(),
            "records": len(conflict_ledger),
            "bytes": ledger_output.stat().st_size,
            "sha256": sha256(ledger_output),
        },
        "future_oracle_capacity_three": oracle_capacity_three(
            all_standalone_trades
        ),
        "selection_gate": selection_result,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=False)
        handle.write("\n")
    print(
        json.dumps(
            {
                "output": str(output),
                "bytes": output.stat().st_size,
                "sha256": sha256(output),
                "ledger": str(ledger_output),
                "ledger_sha256": sha256(ledger_output),
                "verdict": selection_result["verdict"],
                "selected_policy": selection_result["selected_policy"],
                "forward_2025_consumed": False,
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    arguments = parse_args()
    repository_root = Path(__file__).resolve().parents[3]
    if arguments.mode == "fit":
        output = arguments.output or (
            repository_root
            / "lab"
            / "evidence"
            / "STRATEGY_INDEPENDENCE_RISK_ALLOCATION_FIT_V1.json"
        )
        run_fit(arguments.logs_root.resolve(), output.resolve())
    elif arguments.mode == "selection":
        output = arguments.output or (
            repository_root
            / "lab"
            / "evidence"
            / "STRATEGY_INDEPENDENCE_RISK_ALLOCATION_SELECTION_V1.json"
        )
        ledger_output = arguments.ledger_output or (
            repository_root
            / "lab"
            / "evidence"
            / "STRATEGY_INDEPENDENCE_RISK_ALLOCATION_CONFLICTS_2024_V1.jsonl"
        )
        run_selection(
            arguments.logs_root.resolve(),
            output.resolve(),
            ledger_output.resolve(),
        )


if __name__ == "__main__":
    main()
