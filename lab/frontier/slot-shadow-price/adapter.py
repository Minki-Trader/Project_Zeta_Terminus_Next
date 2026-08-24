#!/usr/bin/env python3
"""Build the causal slot-shadow proxy from the isolated 2025 Lab tape."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import re
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[3]
FRONTIER_ROOT = ROOT / "lab" / "frontier" / "slot-shadow-price"
AGENT_LOG = (
    ROOT
    / "lab"
    / "runtime"
    / "tester-portable"
    / "Tester"
    / "Agent-127.0.0.1-3000"
    / "logs"
    / "20260825.log"
)
EVENT_ROOT = (
    ROOT
    / "lab"
    / "runtime"
    / "tester-portable"
    / "Tester"
    / "Agent-127.0.0.1-3000"
    / "MQL5"
    / "Files"
    / "ZetaTerminusNext"
    / "frontier"
)
MEASUREMENT_REPORT = (
    ROOT
    / "lab"
    / "runtime"
    / "tester-portable"
    / "reports"
    / "frontier-slot-shadow-tape-2025.htm"
)
SEED_LOG = (
    ROOT
    / "lab"
    / "artifacts"
    / "backtests"
    / "strategy-independence-risk-allocation"
    / "selection-2024-control-agent.log"
)
BREADTH_LOG = (
    ROOT
    / "lab"
    / "artifacts"
    / "backtests"
    / "deposit-capital-risk-capacity"
    / "selection-2025-breadth-300-agent.log"
)
SIRA_SOURCE = (
    ROOT
    / "lab"
    / "research"
    / "strategy-independence-risk-allocation"
    / "analyze_strategy_independence_risk_allocation_v1.py"
)

COMPONENTS = {
    0: "RC16",
    1: "RC4",
    2: "CROSS",
    3: "PRESSURE",
    4: "RETURN",
    5: "PASSIVE",
}
COMPONENT_IDS = {
    "ZT-M30-US30-RANGE-COMP-61f61deaba": 0,
    "ZT-M30-US30-RANGE-COMP-64efb16616": 1,
    "ZT-H1-US100-CROSS-IN-14b72317b7": 2,
    "ZT-M30-US30-INTRADAY-R-2eb111fc46": 3,
    "ZT-H1-US30-RETURN-I-c870a788ec": 4,
    "ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8": 5,
}
MIDPOINT = int(datetime(2025, 7, 1, tzinfo=timezone.utc).timestamp())


@dataclass
class Candidate:
    candidate_id: int
    server: int
    component: int
    direction: int
    signal: float
    receiver_qualified: bool
    active_positions: int
    pending_passive: bool
    aggregate_risk: float
    risk_capital: float
    equity: float
    margin: float
    outcome: str = ""
    risk_skip_planned: float | None = None
    risk_skip_aggregate_after: float | None = None
    risk_skip_aggregate_cap: float | None = None
    trade: "Trade | None" = None
    incumbents: list["Snapshot"] = field(default_factory=list)


@dataclass
class Snapshot:
    candidate_id: int
    server: int
    candidate_component: int
    component: int
    state: str
    identifier: int
    ticket: int
    direction: int
    opened: int
    age_seconds: int
    held_bars: int
    effective_hold_bars: int
    entry: float
    mark: float
    stop: float
    volume: float
    planned_risk: float
    floating_profit: float
    floating_r: float
    expiration: int | None = None
    remaining_seconds: int | None = None


@dataclass
class Trade:
    component: int
    candidate_id: int
    decision_bar: int
    entry_server: int
    exit_server: int
    direction: int
    signal: float
    planned_risk: float
    actual_net: float = 0.0
    stressed_net: float = 0.0

    @property
    def stressed_r(self) -> float:
        return self.stressed_net / self.planned_risk if self.planned_risk > 0 else 0.0


@dataclass
class PendingInterval:
    candidate_id: int
    start_server: int
    end_server: int
    trade: Trade | None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source(path: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def fields(payload: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in payload.strip().split("|"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        result[key] = value
    return result


def rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


def parse_int(value: str | None, default: int = 0) -> int:
    return default if value is None or value == "" else int(float(value))


def parse_float(value: str | None, default: float = 0.0) -> float:
    return default if value is None or value == "" else float(value)


def load_sira() -> object:
    spec = importlib.util.spec_from_file_location("slot_shadow_sira_reader", SIRA_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the existing Next Lab ledger reader")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_latest_tape() -> list[Candidate]:
    candidates: dict[int, Candidate] = {}
    snapshots: dict[int, list[Snapshot]] = defaultdict(list)
    with AGENT_LOG.open("r", encoding="utf-16-le", errors="strict") as handle:
        for line in handle:
            if "ZetaNextSlotShadowTapeV1" not in line:
                continue
            if "ZETA_FRONTIER_SLOT_CANDIDATE|" in line:
                row = fields(line.split("ZETA_FRONTIER_SLOT_CANDIDATE|", 1)[1])
                candidate_id = parse_int(row.get("id"))
                if candidate_id == 1 and candidates:
                    candidates = {}
                    snapshots = defaultdict(list)
                candidates[candidate_id] = Candidate(
                    candidate_id=candidate_id,
                    server=parse_int(row.get("server")),
                    component=parse_int(row.get("component")),
                    direction=parse_int(row.get("direction")),
                    signal=parse_float(row.get("signal")),
                    receiver_qualified=bool(parse_int(row.get("receiver_qualified"))),
                    active_positions=parse_int(row.get("active_positions")),
                    pending_passive=bool(parse_int(row.get("pending_passive"))),
                    aggregate_risk=parse_float(row.get("aggregate_risk")),
                    risk_capital=parse_float(row.get("risk_capital")),
                    equity=parse_float(row.get("equity")),
                    margin=parse_float(row.get("margin")),
                )
            elif "ZETA_FRONTIER_SLOT_INCUMBENT|" in line:
                row = fields(line.split("ZETA_FRONTIER_SLOT_INCUMBENT|", 1)[1])
                candidate_id = parse_int(row.get("candidate_id"))
                snapshots[candidate_id].append(
                    Snapshot(
                        candidate_id=candidate_id,
                        server=parse_int(row.get("server")),
                        candidate_component=parse_int(row.get("candidate_component")),
                        component=parse_int(row.get("component")),
                        state=row["state"],
                        identifier=parse_int(row.get("identifier")),
                        ticket=parse_int(row.get("ticket")),
                        direction=parse_int(row.get("direction")),
                        opened=parse_int(row.get("opened")),
                        age_seconds=parse_int(row.get("age_seconds")),
                        held_bars=parse_int(row.get("held_bars")),
                        effective_hold_bars=parse_int(row.get("effective_hold_bars")),
                        entry=parse_float(row.get("entry")),
                        mark=parse_float(row.get("mark")),
                        stop=parse_float(row.get("stop")),
                        volume=parse_float(row.get("volume")),
                        planned_risk=parse_float(row.get("planned_risk")),
                        floating_profit=parse_float(row.get("floating_profit")),
                        floating_r=parse_float(row.get("floating_r")),
                        expiration=(
                            None if "expiration" not in row else parse_int(row["expiration"])
                        ),
                        remaining_seconds=(
                            None
                            if "remaining_seconds" not in row
                            else parse_int(row["remaining_seconds"])
                        ),
                    )
                )
    ordered = [candidates[index] for index in sorted(candidates)]
    for candidate in ordered:
        candidate.incumbents = snapshots.get(candidate.candidate_id, [])
    if len(ordered) != 606:
        raise RuntimeError(f"latest slot tape has {len(ordered)} candidates, expected 606")
    return ordered


def load_event_rows() -> list[dict[str, str]]:
    paths = sorted(EVENT_ROOT.glob("slot-shadow-tape-v1-events-*.csv"))
    if not paths:
        raise RuntimeError("slot shadow event journal is absent")
    rows: list[dict[str, str]] = []
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def detail_number(detail: str, key: str) -> float | None:
    match = re.search(rf"(?:^|\s){re.escape(key)}=(-?\d+(?:\.\d+)?)", detail)
    return None if match is None else float(match.group(1))


def detail_word(detail: str, key: str) -> str | None:
    match = re.search(rf"(?:^|\s){re.escape(key)}=([^\s]+)", detail)
    return None if match is None else match.group(1)


def bind_events(
    candidates: list[Candidate], rows: list[dict[str, str]]
) -> tuple[list[Trade], list[PendingInterval]]:
    signal_index = 0
    current: dict[int, Candidate] = {}
    active: dict[int, Trade] = {}
    completed: list[Trade] = []
    pending_candidate: Candidate | None = None
    pending_start = 0
    pending_intervals: list[PendingInterval] = []

    for row in rows:
        event = row["event"]
        component = COMPONENT_IDS.get(row["component_id"], -1)
        server = int(datetime.strptime(row["server_time"], "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
        value_a = float(row["value_a"])
        value_b = float(row["value_b"])
        detail = row["detail"]

        if event == "SIGNAL_DECIDED":
            candidate = candidates[signal_index]
            signal_index += 1
            direction = int(round(value_b))
            if (
                candidate.component != component
                or candidate.server != server
                or candidate.direction != direction
                or not math.isclose(candidate.signal, value_a, abs_tol=1.0e-7)
            ):
                raise RuntimeError("slot tape and event signal sequence diverged")
            current[component] = candidate
        elif event == "RISK_ADMISSION_SKIP":
            candidate = current[component]
            candidate.risk_skip_planned = value_a
            candidate.risk_skip_aggregate_after = value_b
            candidate.risk_skip_aggregate_cap = detail_number(detail, "aggregate_cap")
        elif event == "OPEN":
            candidate = current[component]
            planned_risk = detail_number(detail, "planned_risk") or 0.0
            active[component] = Trade(
                component=component,
                candidate_id=candidate.candidate_id,
                decision_bar=candidate.server,
                entry_server=server,
                exit_server=0,
                direction=candidate.direction,
                signal=candidate.signal,
                planned_risk=planned_risk,
            )
            candidate.trade = active[component]
        elif event == "DECISION_JOURNAL_FINAL":
            candidate = current[component]
            candidate.outcome = detail_word(detail, "outcome") or "UNKNOWN"
            if component == 5 and candidate.outcome == "PENDING_ORDER":
                pending_candidate = candidate
                pending_start = server
        elif event == "PASSIVE_FILL":
            if pending_candidate is None:
                raise RuntimeError("passive fill has no pending candidate")
            trade = Trade(
                component=5,
                candidate_id=pending_candidate.candidate_id,
                decision_bar=pending_candidate.server,
                entry_server=server,
                exit_server=0,
                direction=pending_candidate.direction,
                signal=pending_candidate.signal,
                planned_risk=0.0,
            )
            active[5] = trade
            pending_candidate.trade = trade
            pending_intervals.append(
                PendingInterval(
                    candidate_id=pending_candidate.candidate_id,
                    start_server=pending_start,
                    end_server=server,
                    trade=trade,
                )
            )
            pending_candidate = None
            pending_start = 0
        elif event in {"PASSIVE_EXPIRE", "PASSIVE_CANCEL"}:
            if pending_candidate is not None:
                pending_intervals.append(
                    PendingInterval(
                        candidate_id=pending_candidate.candidate_id,
                        start_server=pending_start,
                        end_server=server,
                        trade=None,
                    )
                )
            pending_candidate = None
            pending_start = 0
        elif event.endswith("_PARTIAL") and "CLOSE" in event:
            trade = active[component]
            trade.actual_net += value_a
            trade.stressed_net += value_b
        elif event in {"CLOSE", "EXTERNAL_CLOSE"}:
            trade = active[component]
            trade.actual_net += value_a
            trade.stressed_net += value_b
            trade.exit_server = server
            if trade.planned_risk <= 0.0:
                candidate = candidates[trade.candidate_id - 1]
                trade.planned_risk = max(
                    0.01,
                    next(
                        (
                            snapshot.planned_risk
                            for later in candidates
                            if later.server >= trade.entry_server
                            for snapshot in later.incumbents
                            if snapshot.component == component
                            and snapshot.state == "POSITION"
                            and snapshot.opened == trade.entry_server
                            and snapshot.planned_risk > 0.0
                        ),
                        candidate.risk_capital * 0.04,
                    ),
                )
            completed.append(trade)
            del active[component]

    if signal_index != len(candidates) or active or pending_candidate is not None:
        raise RuntimeError("measurement event journal ended with unresolved state")
    if len(completed) != 551:
        raise RuntimeError(f"measurement produced {len(completed)} trades, expected 551")
    return completed, pending_intervals


def prior_stats(
    component: int,
    server: int,
    seed_trades: list[object],
    measurement_trades: list[Trade],
    window: int,
) -> dict[str, float]:
    values: list[tuple[int, float, float]] = []
    for trade in seed_trades:
        if trade.component == component:
            values.append(
                (
                    trade.exit_server,
                    max(-3.0, min(3.0, trade.stressed_r)),
                    max(0.0, trade.actual_net - trade.stressed_net),
                )
            )
    for trade in measurement_trades:
        if trade.component == component and trade.exit_server < server:
            values.append(
                (
                    trade.exit_server,
                    max(-3.0, min(3.0, trade.stressed_r)),
                    max(0.0, trade.actual_net - trade.stressed_net),
                )
            )
    values.sort(key=lambda row: row[0])
    selected = values[-window:]
    r_values = [row[1] for row in selected]
    friction = [row[2] for row in selected]
    return {
        "count": float(len(selected)),
        "mean_r": statistics.fmean(r_values) if r_values else 0.0,
        "win_rate": (
            sum(value > 0.0 for value in r_values) / len(r_values)
            if r_values
            else 0.5
        ),
        "median_friction": statistics.median(friction) if friction else 0.02,
    }


def signal_percentile(
    candidate: Candidate,
    seed_opportunities: list[object],
    candidates: list[Candidate],
) -> float:
    prior = [
        abs(row.signal)
        for row in seed_opportunities
        if row.component == candidate.component
    ]
    prior.extend(
        abs(row.signal)
        for row in candidates
        if row.component == candidate.component and row.server < candidate.server
    )
    if not prior:
        return 0.5
    value = abs(candidate.signal)
    return sum(item <= value for item in prior) / len(prior)


def active_trade(
    trades: list[Trade], component: int, server: int
) -> Trade | None:
    return next(
        (
            trade
            for trade in trades
            if trade.component == component
            and trade.entry_server <= server < trade.exit_server
        ),
        None,
    )


def pending_at(
    intervals: list[PendingInterval], server: int
) -> PendingInterval | None:
    return next(
        (
            interval
            for interval in intervals
            if interval.start_server <= server < interval.end_server
        ),
        None,
    )


def breadth_trade_map(sira: object) -> dict[tuple[int, int, int], object]:
    _, _, trades = sira.build_trades(BREADTH_LOG)
    return {
        (trade.component, trade.decision_bar, trade.direction): trade
        for trade in trades
    }


def build_conflicts(
    candidates: list[Candidate],
    trades: list[Trade],
    pending_intervals: list[PendingInterval],
    seed_opportunities: list[object],
    seed_trades: list[object],
    breadth: dict[tuple[int, int, int], object],
) -> list[dict[str, object]]:
    conflicts: list[dict[str, object]] = []
    for candidate in candidates:
        if candidate.risk_skip_planned is None:
            continue
        counterfactual = breadth.get(
            (candidate.component, candidate.server, candidate.direction)
        )
        candidate_stats = {
            str(window): prior_stats(
                candidate.component, candidate.server, seed_trades, trades, window
            )
            for window in (8, 16, 32, 64)
        }
        percentile = signal_percentile(candidate, seed_opportunities, candidates)
        required_release = max(
            0.0,
            (candidate.risk_skip_aggregate_after or 0.0)
            - (candidate.risk_skip_aggregate_cap or 0.0),
        )
        options: list[dict[str, object]] = []
        for snapshot in candidate.incumbents:
            if snapshot.planned_risk + 0.01 < required_release:
                continue
            incumbent_stats = {
                str(window): prior_stats(
                    snapshot.component, candidate.server, seed_trades, trades, window
                )
                for window in (8, 16, 32, 64)
            }
            if snapshot.state == "POSITION":
                base_trade = active_trade(trades, snapshot.component, candidate.server)
                if base_trade is None:
                    continue
                base_stressed = base_trade.stressed_net
                base_actual = base_trade.actual_net
                remaining = max(
                    0.0,
                    min(
                        1.0,
                        1.0
                        - snapshot.held_bars
                        / max(1.0, float(snapshot.effective_hold_bars)),
                    ),
                )
                immediate_stressed = (
                    snapshot.floating_profit
                    - incumbent_stats["32"]["median_friction"]
                )
            else:
                interval = pending_at(pending_intervals, candidate.server)
                if interval is None:
                    continue
                base_trade = interval.trade
                base_stressed = 0.0 if base_trade is None else base_trade.stressed_net
                base_actual = 0.0 if base_trade is None else base_trade.actual_net
                remaining = max(
                    0.0,
                    min(
                        1.0,
                        (snapshot.remaining_seconds or 0) / (4.0 * 3600.0),
                    ),
                )
                immediate_stressed = 0.0
            exchange_delta = None
            if counterfactual is not None:
                exchange_delta = (
                    counterfactual.stressed_net
                    + immediate_stressed
                    - base_stressed
                )
            options.append(
                {
                    "component": snapshot.component,
                    "component_name": COMPONENTS[snapshot.component],
                    "state": snapshot.state,
                    "planned_risk": rounded(snapshot.planned_risk),
                    "floating_profit": rounded(snapshot.floating_profit),
                    "floating_r": rounded(snapshot.floating_r),
                    "held_bars": snapshot.held_bars,
                    "effective_hold_bars": snapshot.effective_hold_bars,
                    "remaining_fraction": rounded(remaining),
                    "base_actual_net": rounded(base_actual),
                    "base_stressed_net": rounded(base_stressed),
                    "immediate_stressed_proxy": rounded(immediate_stressed),
                    "exchange_delta_proxy": rounded(exchange_delta),
                    "prior": incumbent_stats,
                }
            )
        conflicts.append(
            {
                "candidate_id": candidate.candidate_id,
                "server": candidate.server,
                "server_time": datetime.fromtimestamp(
                    candidate.server, tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M:%S"),
                "half": "early" if candidate.server < MIDPOINT else "late",
                "component": candidate.component,
                "component_name": COMPONENTS[candidate.component],
                "direction": candidate.direction,
                "signal": rounded(candidate.signal),
                "signal_percentile": rounded(percentile),
                "receiver_qualified": candidate.receiver_qualified,
                "required_risk_release": rounded(required_release),
                "candidate_counterfactual": (
                    None
                    if counterfactual is None
                    else {
                        "actual_net": rounded(counterfactual.actual_net),
                        "stressed_net": rounded(counterfactual.stressed_net),
                        "planned_risk": rounded(counterfactual.planned_risk),
                        "stressed_r": rounded(counterfactual.stressed_r),
                    }
                ),
                "candidate_prior": candidate_stats,
                "options": options,
            }
        )
    return conflicts


def candidate_score(
    conflict: dict[str, object], model: str, signal_weight: float, receiver_weight: float
) -> float:
    prior = conflict["candidate_prior"]
    assert isinstance(prior, dict)
    base = float(prior["32"]["mean_r"])
    percentile = float(conflict["signal_percentile"])
    if model == "component_mean":
        return base
    if model == "signal_rarity":
        return base + signal_weight * (percentile - 0.5)
    if model == "receiver_priority":
        return base + receiver_weight * float(bool(conflict["receiver_qualified"]))
    return (
        base
        + signal_weight * (percentile - 0.5)
        + receiver_weight * float(bool(conflict["receiver_qualified"]))
    )


def slot_price(option: dict[str, object], model: str) -> float:
    prior = option["prior"]
    assert isinstance(prior, dict)
    mean_r = float(prior["32"]["mean_r"])
    floating_r = float(option["floating_r"])
    remaining = float(option["remaining_fraction"])
    if model == "floating_only":
        return floating_r
    if model == "posterior_remaining":
        return mean_r * remaining
    if model == "maturity_residual":
        return floating_r + mean_r * remaining
    if model == "convex_maturity":
        return floating_r + mean_r * remaining * remaining
    return (
        floating_r
        + max(0.0, mean_r) * remaining
        - max(0.0, -floating_r) * (1.0 - remaining)
    )


def drawdown(values: Iterable[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    maximum = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        maximum = max(maximum, peak - cumulative)
    return maximum


def period_metrics(rows: list[dict[str, object]]) -> dict[str, object]:
    values = [float(row["exchange_delta_proxy"]) for row in rows]
    return {
        "actions": len(rows),
        "total_exchange_delta": rounded(sum(values)),
        "mean_exchange_delta": rounded(statistics.fmean(values) if values else 0.0),
        "positive": sum(value > 0.0 for value in values),
        "negative": sum(value < 0.0 for value in values),
        "closed_drawdown": rounded(drawdown(values)),
    }


def evaluate_policy(
    conflicts: list[dict[str, object]],
    candidate_model: str,
    slot_model: str,
    signal_weight: float,
    receiver_weight: float,
    margin: float,
    candidate_floor: float,
    signal_floor: float,
    floating_ceiling: float,
    age_floor: float,
    state_filter: str,
) -> dict[str, object]:
    actions: list[dict[str, object]] = []
    for conflict in conflicts:
        if conflict["candidate_counterfactual"] is None:
            continue
        score = candidate_score(
            conflict, candidate_model, signal_weight, receiver_weight
        )
        if score < candidate_floor or float(conflict["signal_percentile"]) < signal_floor:
            continue
        options = []
        for option in conflict["options"]:
            if option["exchange_delta_proxy"] is None:
                continue
            if state_filter != "ANY" and option["state"] != state_filter:
                continue
            if float(option["floating_r"]) > floating_ceiling:
                continue
            age = 1.0 - float(option["remaining_fraction"])
            if age < age_floor:
                continue
            options.append((slot_price(option, slot_model), option))
        if not options:
            continue
        price, selected = min(options, key=lambda row: row[0])
        if score - price < margin:
            continue
        actions.append(
            {
                "server": conflict["server"],
                "half": conflict["half"],
                "candidate_id": conflict["candidate_id"],
                "candidate_component": conflict["component_name"],
                "incumbent_component": selected["component_name"],
                "incumbent_state": selected["state"],
                "candidate_score": rounded(score),
                "slot_price": rounded(price),
                "exchange_delta_proxy": selected["exchange_delta_proxy"],
            }
        )
    actions.sort(key=lambda row: int(row["server"]))
    early = [row for row in actions if row["half"] == "early"]
    late = [row for row in actions if row["half"] == "late"]
    return {
        "candidate_model": candidate_model,
        "slot_model": slot_model,
        "params": {
            "signal_weight": signal_weight,
            "receiver_weight": receiver_weight,
            "margin": margin,
            "candidate_floor": candidate_floor,
            "signal_floor": signal_floor,
            "floating_ceiling": floating_ceiling,
            "age_floor": age_floor,
            "state_filter": state_filter,
        },
        "full": period_metrics(actions),
        "early": period_metrics(early),
        "late": period_metrics(late),
        "actions": actions,
    }


def policy_search(conflicts: list[dict[str, object]]) -> dict[str, object]:
    evaluations: list[dict[str, object]] = []
    candidate_models = (
        "component_mean",
        "signal_rarity",
        "receiver_priority",
        "signal_receiver",
    )
    slot_models = (
        "floating_only",
        "posterior_remaining",
        "maturity_residual",
        "convex_maturity",
        "wounded_age",
    )
    for candidate_model in candidate_models:
        signal_weights = (0.0,) if "signal" not in candidate_model else (0.25, 0.5, 1.0)
        receiver_weights = (
            (0.0,) if "receiver" not in candidate_model else (0.1, 0.25, 0.5)
        )
        for slot_model in slot_models:
            for signal_weight in signal_weights:
                for receiver_weight in receiver_weights:
                    for margin in (-0.25, 0.0, 0.25, 0.5):
                        for candidate_floor in (-0.25, 0.0, 0.25):
                            for signal_floor in (0.0, 0.5, 0.75):
                                for floating_ceiling in (999.0, 0.25, 0.0, -0.25):
                                    for age_floor in (0.0, 0.25, 0.5):
                                        evaluations.append(
                                            evaluate_policy(
                                                conflicts,
                                                candidate_model,
                                                slot_model,
                                                signal_weight,
                                                receiver_weight,
                                                margin,
                                                candidate_floor,
                                                signal_floor,
                                                floating_ceiling,
                                                age_floor,
                                                "POSITION",
                                            )
                                        )
    stable = [
        row
        for row in evaluations
        if int(row["full"]["actions"]) >= 2
        and int(row["early"]["actions"]) >= 1
        and int(row["late"]["actions"]) >= 1
        and float(row["full"]["total_exchange_delta"]) > 0.0
        and float(row["early"]["total_exchange_delta"]) > 0.0
        and float(row["late"]["total_exchange_delta"]) > 0.0
    ]
    for row in stable:
        row["stable_score"] = rounded(
            min(
                float(row["early"]["total_exchange_delta"]),
                float(row["late"]["total_exchange_delta"]),
            )
            + 0.25 * float(row["full"]["total_exchange_delta"])
            - 0.10 * float(row["full"]["closed_drawdown"])
        )
    stable.sort(
        key=lambda row: (
            float(row["stable_score"]),
            float(row["full"]["total_exchange_delta"]),
        ),
        reverse=True,
    )
    distinct: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for row in stable:
        key = (str(row["candidate_model"]), str(row["slot_model"]))
        if key in seen:
            continue
        seen.add(key)
        distinct.append(row)
        if len(distinct) == 20:
            break
    return {
        "evaluation_count": len(evaluations),
        "stable_count": len(stable),
        "leaders": distinct,
    }


def oracle_summary(conflicts: list[dict[str, object]]) -> dict[str, object]:
    matched = [row for row in conflicts if row["candidate_counterfactual"] is not None]
    candidate_values = [
        float(row["candidate_counterfactual"]["stressed_net"]) for row in matched
    ]
    best_options: list[tuple[int, str, float]] = []
    for row in matched:
        values = [
            float(option["exchange_delta_proxy"])
            for option in row["options"]
            if option["exchange_delta_proxy"] is not None
        ]
        if values:
            best_options.append(
                (int(row["server"]), str(row["half"]), max(values))
            )
    positive = [row for row in best_options if row[2] > 0.0]
    return {
        "blocked": len(conflicts),
        "counterfactual_matched": len(matched),
        "candidate_only_stressed_net": rounded(sum(candidate_values)),
        "candidate_only_positive": sum(value > 0.0 for value in candidate_values),
        "candidate_only_negative": sum(value < 0.0 for value in candidate_values),
        "best_incumbent_exchange_positive_count": len(positive),
        "best_incumbent_exchange_positive_total": rounded(
            sum(row[2] for row in positive)
        ),
        "best_incumbent_exchange_positive_early": rounded(
            sum(row[2] for row in positive if row[1] == "early")
        ),
        "best_incumbent_exchange_positive_late": rounded(
            sum(row[2] for row in positive if row[1] == "late")
        ),
    }


def compact_conflict(row: dict[str, object]) -> dict[str, object]:
    return {
        "candidate_id": row["candidate_id"],
        "server": row["server"],
        "server_time": row["server_time"],
        "half": row["half"],
        "component": row["component_name"],
        "direction": row["direction"],
        "signal": row["signal"],
        "signal_percentile": row["signal_percentile"],
        "receiver_qualified": row["receiver_qualified"],
        "required_risk_release": row["required_risk_release"],
        "candidate_counterfactual": row["candidate_counterfactual"],
        "candidate_prior_32": row["candidate_prior"]["32"],
        "options": [
            {
                key: option[key]
                for key in (
                    "component_name",
                    "state",
                    "planned_risk",
                    "floating_profit",
                    "floating_r",
                    "held_bars",
                    "effective_hold_bars",
                    "remaining_fraction",
                    "base_stressed_net",
                    "immediate_stressed_proxy",
                    "exchange_delta_proxy",
                )
            }
            for option in row["options"]
        ],
    }


def main() -> None:
    sira = load_sira()
    candidates = parse_latest_tape()
    event_rows = load_event_rows()
    trades, pending_intervals = bind_events(candidates, event_rows)
    seed_opportunities, _, seed_trades = sira.build_trades(SEED_LOG)
    breadth = breadth_trade_map(sira)
    conflicts = build_conflicts(
        candidates,
        trades,
        pending_intervals,
        seed_opportunities,
        seed_trades,
        breadth,
    )
    search = policy_search(conflicts)
    output = {
        "unit": "slot-shadow-price-006",
        "question": "Can an occupied risk slot be priced causally against a later arriving opportunity?",
        "causality": {
            "features": "Only prior completed 2024/2025 Lab lifecycles, signal history, receiver qualification, incumbent age, planned risk and marked floating P/L known at the blocked decision are used by policies.",
            "labels": "The candidate label comes from the already-opened Next 2025 broad-capacity path; incumbent keep and immediate-close values are used only after policy selection for proxy economics.",
            "limits": "Exchange deltas are first-order counterfactuals. They do not model later path mutation, so only a few causal shapes may proceed to a real-tick EA runtime.",
        },
        "measurement": {
            "candidates": len(candidates),
            "incumbent_snapshots": sum(len(row.incumbents) for row in candidates),
            "risk_blocked": len(conflicts),
            "completed_lifecycles": len(trades),
            "pending_intervals": len(pending_intervals),
            "position_read_failures": 0,
        },
        "oracle_ceiling": oracle_summary(conflicts),
        "search": search,
        "runtime_seed": {
            COMPONENTS[component]: [
                rounded(trade.stressed_r)
                for trade in seed_trades
                if trade.component == component
            ][-32:]
            for component in range(len(COMPONENTS))
        },
        "conflicts": [compact_conflict(row) for row in conflicts],
        "sources": {
            "adapter": source(Path(__file__).resolve()),
            "measurement_agent_log": source(AGENT_LOG),
            "measurement_events": [
                source(path)
                for path in sorted(EVENT_ROOT.glob("slot-shadow-tape-v1-events-*.csv"))
            ],
            "measurement_report": source(MEASUREMENT_REPORT),
            "seed_2024_control": source(SEED_LOG),
            "candidate_counterfactual_breadth": source(BREADTH_LOG),
        },
    }
    FRONTIER_ROOT.mkdir(parents=True, exist_ok=True)
    (FRONTIER_ROOT / "proxy.json").write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
