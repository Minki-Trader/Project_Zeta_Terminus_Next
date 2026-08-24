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
    default_output = (
        repository_root
        / "lab"
        / "evidence"
        / "STRATEGY_INDEPENDENCE_RISK_ALLOCATION_FIT_V1.json"
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("fit",))
    parser.add_argument("--logs-root", type=Path, default=default_logs)
    parser.add_argument("--output", type=Path, default=default_output)
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


def main() -> None:
    arguments = parse_args()
    if arguments.mode == "fit":
        run_fit(arguments.logs_root.resolve(), arguments.output.resolve())


if __name__ == "__main__":
    main()
