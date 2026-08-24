#!/usr/bin/env python3
"""Analyze the frozen 2025 Lab selection runs for deposit/risk capacity V1."""

from __future__ import annotations

import argparse
import collections
import dataclasses
import hashlib
import importlib.util
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


SELECTION_START = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp())
SELECTION_MID = int(datetime(2025, 7, 1, tzinfo=timezone.utc).timestamp())
SELECTION_END = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
PERIODS = {
    "2025_H1": (SELECTION_START, SELECTION_MID),
    "2025_H2": (SELECTION_MID, SELECTION_END),
    "2025_FULL": (SELECTION_START, SELECTION_END),
}
REPORT_SUFFIXES = (
    "-agent.log",
    ".htm",
    ".png",
    "-holding.png",
    "-hst.png",
    "-mfemae.png",
)
RELEVANT_EVENT_NAMES = (
    "RISK_ADMISSION_SKIP",
    "RISK_MIN_LOT_SKIP",
    "PASSIVE_MARGIN_SKIP",
    "PASSIVE_MARGIN_CALC_FAIL",
    "DCRC_MARKET_MARGIN_OR_CALC_BLOCK",
    "PROTECTION_CALC_FAIL",
    "PROTECTION_MISMATCH",
    "STOP",
)


@dataclass(frozen=True)
class RunSpec:
    name: str
    policy: str
    deposit_usd: float
    reference_capital_usd: float
    role: str
    expected_ea: str
    selectable: bool


RUNS = (
    RunSpec(
        "control-100",
        "DEPOSIT_ONLY_RESERVE",
        100.0,
        100.0,
        "identity_control",
        "ZetaSiraCombinedControlV1",
        False,
    ),
    RunSpec(
        "control-200",
        "DEPOSIT_ONLY_RESERVE",
        200.0,
        100.0,
        "matching_deposit_control",
        "ZetaSiraCombinedControlV1",
        False,
    ),
    RunSpec(
        "control-300",
        "DEPOSIT_ONLY_RESERVE",
        300.0,
        100.0,
        "matching_deposit_control",
        "ZetaSiraCombinedControlV1",
        False,
    ),
    RunSpec(
        "linear-100",
        "LINEAR_CAPITAL",
        100.0,
        100.0,
        "structural_anchor",
        "ZetaDcrcLinearCapitalV1",
        False,
    ),
    RunSpec(
        "linear-200",
        "LINEAR_CAPITAL",
        200.0,
        200.0,
        "structural_anchor",
        "ZetaDcrcLinearCapitalV1",
        False,
    ),
    RunSpec(
        "linear-300",
        "LINEAR_CAPITAL",
        300.0,
        300.0,
        "structural_anchor",
        "ZetaDcrcLinearCapitalV1",
        False,
    ),
    RunSpec(
        "breadth-200",
        "BREADTH_DOLLAR_SLOTS",
        200.0,
        200.0,
        "capacity_candidate",
        "ZetaDcrcBreadthDollarSlotsV1",
        True,
    ),
    RunSpec(
        "breadth-300",
        "BREADTH_DOLLAR_SLOTS",
        300.0,
        300.0,
        "capacity_candidate",
        "ZetaDcrcBreadthDollarSlotsV1",
        True,
    ),
    RunSpec(
        "ladder-200",
        "FIXED_LOT_LADDER",
        200.0,
        200.0,
        "sizing_diagnostic_only",
        "ZetaDcrcFixedLotLadderV1",
        False,
    ),
    RunSpec(
        "ladder-300",
        "FIXED_LOT_LADDER",
        300.0,
        300.0,
        "sizing_diagnostic_only",
        "ZetaDcrcFixedLotLadderV1",
        False,
    ),
)


class ReportTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        del attrs
        if tag.lower() == "tr":
            self._row = []
        elif tag.lower() == "td" and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered == "td" and self._row is not None and self._cell is not None:
            value = " ".join("".join(self._cell).split())
            self._row.append(value)
            self._cell = None
        elif lowered == "tr" and self._row is not None:
            if any(self._row):
                self.rows.append(self._row)
            self._row = None
            self._cell = None


def parse_args() -> argparse.Namespace:
    repository_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifacts-root",
        type=Path,
        default=(
            repository_root
            / "lab"
            / "artifacts"
            / "backtests"
            / "deposit-capital-risk-capacity"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            repository_root
            / "lab"
            / "evidence"
            / "DEPOSIT_CAPITAL_RISK_CAPACITY_SELECTION_V1.json"
        ),
    )
    return parser.parse_args()


def load_sira_analysis(repository_root: Path) -> object:
    source = (
        repository_root
        / "lab"
        / "research"
        / "strategy-independence-risk-allocation"
        / "analyze_strategy_independence_risk_allocation_v1.py"
    )
    spec = importlib.util.spec_from_file_location("zeta_sira_analysis_v1", source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load SIRA analysis helpers from {source}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_record(path: Path, repository_root: Path) -> dict[str, object]:
    return {
        "path": path.resolve().relative_to(repository_root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def first_number(value: str) -> float:
    match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
    if match is None:
        raise ValueError(f"numeric value not found in {value!r}")
    return float(match.group(0))


def report_label_values(rows: list[list[str]], label: str) -> list[str]:
    values: list[str] = []
    for row in rows:
        for index, cell in enumerate(row[:-1]):
            if cell == label:
                values.append(row[index + 1])
    return values


def single_report_value(rows: list[list[str]], label: str) -> str:
    values = report_label_values(rows, label)
    if len(values) != 1:
        raise ValueError(f"expected one report value for {label!r}; found {values}")
    return values[0]


def indexed_report_value(rows: list[list[str]], label: str, index: int) -> str:
    values = report_label_values(rows, label)
    if index < 0 or index >= len(values):
        raise ValueError(
            f"report value index {index} missing for {label!r}; found {values}"
        )
    return values[index]


def parse_report(path: Path) -> dict[str, object]:
    parser = ReportTableParser()
    parser.feed(path.read_text(encoding="utf-16"))
    trade_and_deal_counts = report_label_values(parser.rows, "총 거래횟수:")
    if len(trade_and_deal_counts) != 2:
        raise ValueError(f"trade/deal rows missing from {path}")
    deposit = first_number(single_report_value(parser.rows, "입금액:"))
    actual_net = first_number(single_report_value(parser.rows, "총수입:"))
    return {
        "expert": single_report_value(parser.rows, "시스템 트레이딩:"),
        # The Korean report reuses "통화" for symbol, account currency, and
        # tested-currency count. The first settings occurrence is the symbol.
        "symbol": indexed_report_value(parser.rows, "통화:", 0),
        "period": single_report_value(parser.rows, "주기:"),
        "deposit_usd": deposit,
        "history_quality": single_report_value(parser.rows, "히스토리 품질:"),
        "bars": int(first_number(single_report_value(parser.rows, "봉수:"))),
        "ticks": int(first_number(single_report_value(parser.rows, "틱:"))),
        "actual_net_usd": actual_net,
        "actual_ending_balance_usd": deposit + actual_net,
        "actual_balance_max_drawdown_usd": first_number(
            single_report_value(parser.rows, "Balance Drawdown Maximal:")
        ),
        "profit_factor": first_number(
            single_report_value(parser.rows, "Profit Factor:")
        ),
        "recovery_factor": first_number(
            single_report_value(parser.rows, "Recovery Factor:")
        ),
        "sharpe_ratio": first_number(
            single_report_value(parser.rows, "Sharpe Ratio:")
        ),
        "total_trades": int(first_number(trade_and_deal_counts[0])),
        "total_deals": int(first_number(trade_and_deal_counts[1])),
    }


def key_value_fields(payload: str) -> dict[str, str]:
    return dict(re.findall(r"([A-Za-z0-9_]+)=([^\s]+)", payload))


def read_final_lines(path: Path) -> tuple[dict[str, str], dict[str, str] | None]:
    portfolio_rows: list[dict[str, str]] = []
    dcrc_rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-16-le", errors="strict") as handle:
        for line in handle:
            if " final portfolio=" in line:
                portfolio_rows.append(
                    key_value_fields(line.split(" final ", 1)[1])
                )
            if " DCRC_FINAL " in line:
                dcrc_rows.append(
                    key_value_fields(line.split(" DCRC_FINAL ", 1)[1])
                )
    if len(portfolio_rows) != 1:
        raise ValueError(f"expected one final portfolio row in {path}")
    if len(dcrc_rows) > 1:
        raise ValueError(f"multiple DCRC final rows in {path}")
    return portfolio_rows[0], (dcrc_rows[0] if dcrc_rows else None)


def logged_margin_observations(path: Path) -> dict[str, float | int]:
    maximum_usd = 0.0
    maximum_fraction = 0.0
    observations = 0
    pattern = re.compile(
        r"\|equity=(-?\d+(?:\.\d+)?)\|margin=(-?\d+(?:\.\d+)?)"
    )
    with path.open("r", encoding="utf-16-le", errors="strict") as handle:
        for line in handle:
            match = pattern.search(line)
            if match is None:
                continue
            equity = float(match.group(1))
            margin = float(match.group(2))
            observations += 1
            maximum_usd = max(maximum_usd, margin)
            if equity > 0.0:
                maximum_fraction = max(maximum_fraction, margin / equity)
    return {
        "observation_count": observations,
        "maximum_margin_usd": maximum_usd,
        "maximum_margin_equity_fraction": maximum_fraction,
        "maximum_margin_equity_percent": maximum_fraction * 100.0,
    }


def period_summary(
    trades: list[object],
    start: int,
    end: int,
    deposit_usd: float,
    sira: object,
) -> dict[str, float | int]:
    selected = [trade for trade in trades if start <= trade.decision_bar < end]
    actual_net = sum(trade.actual_net for trade in selected)
    stressed_net = sum(trade.stressed_net for trade in selected)
    actual_dd = sira.closed_drawdown(selected, "actual_net")
    stressed_dd = sira.closed_drawdown(selected, "stressed_net")
    planned_risk = sum(trade.planned_risk for trade in selected)
    return {
        "trade_count": len(selected),
        "win_count_actual": sum(trade.actual_net > 0.0 for trade in selected),
        "win_count_stressed": sum(trade.stressed_net > 0.0 for trade in selected),
        "actual_net_usd": actual_net,
        "actual_return_percent": actual_net / deposit_usd * 100.0,
        "actual_max_closed_drawdown_usd": actual_dd,
        "actual_max_closed_drawdown_percent": actual_dd / deposit_usd * 100.0,
        "actual_net_to_drawdown": actual_net / actual_dd if actual_dd > 0.0 else 0.0,
        "stressed_net_usd": stressed_net,
        "stressed_return_percent": stressed_net / deposit_usd * 100.0,
        "stressed_max_closed_drawdown_usd": stressed_dd,
        "stressed_max_closed_drawdown_percent": stressed_dd / deposit_usd * 100.0,
        "stressed_net_to_drawdown": (
            stressed_net / stressed_dd if stressed_dd > 0.0 else 0.0
        ),
        "planned_risk_usd": planned_risk,
        "stressed_net_per_planned_risk": (
            stressed_net / planned_risk if planned_risk > 0.0 else 0.0
        ),
    }


def volume_distribution(trades: Iterable[object]) -> dict[str, int]:
    counts = collections.Counter(f"{trade.volume:.2f}" for trade in trades)
    return dict(sorted(counts.items(), key=lambda row: float(row[0])))


def component_summary(
    trades: list[object], deposit_usd: float, sira: object
) -> dict[str, dict[str, object]]:
    output: dict[str, dict[str, object]] = {}
    for component, name in sira.COMPONENTS.items():
        selected = [trade for trade in trades if trade.component == component]
        row = period_summary(
            selected, SELECTION_START, SELECTION_END, deposit_usd, sira
        )
        row["volume_distribution"] = volume_distribution(selected)
        output[name] = row
    return output


def event_component_counts(events: list[object], event_name: str, sira: object) -> dict[str, int]:
    counts = collections.Counter(
        sira.COMPONENTS.get(event.component, str(event.component))
        for event in events
        if event.name == event_name
    )
    return dict(sorted(counts.items()))


def sizing_summary(events: list[object]) -> dict[str, object]:
    rows = sorted(
        (event for event in events if event.name == "DCRC_SIZE_DAY"),
        key=lambda event: event.server,
    )
    transitions: list[dict[str, object]] = []
    prior_multiplier: int | None = None
    for event in rows:
        multiplier = int(round(event.value_b))
        if prior_multiplier is not None and multiplier != prior_multiplier:
            transitions.append(
                {
                    "server": event.server,
                    "server_time": datetime.fromtimestamp(
                        event.server, tz=timezone.utc
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                    "from_multiplier": prior_multiplier,
                    "to_multiplier": multiplier,
                    "volume": event.value_a,
                    "detail": event.detail,
                }
            )
        prior_multiplier = multiplier
    return {
        "sizing_day_count": len(rows),
        "daily_volume_counts": dict(
            sorted(collections.Counter(f"{row.value_a:.2f}" for row in rows).items())
        ),
        "transition_count": len(transitions),
        "transitions": transitions,
    }


def normalized_dataclasses(rows: Iterable[object]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in rows:
        value = dataclasses.asdict(row)
        value.pop("line_number", None)
        output.append(value)
    return output


def economic_identity_check(
    control: tuple[list[object], list[object], list[object]],
    linear: tuple[list[object], list[object], list[object]],
) -> dict[str, object]:
    control_opportunities, control_events, control_trades = control
    linear_opportunities, linear_events, linear_trades = linear
    diagnostic_names = {"SIZE_DAY", "DCRC_SIZE_DAY"}
    control_economic_events = [
        event for event in control_events if event.name not in diagnostic_names
    ]
    linear_economic_events = [
        event for event in linear_events if event.name not in diagnostic_names
    ]
    checks = {
        "opportunities_exact": normalized_dataclasses(control_opportunities)
        == normalized_dataclasses(linear_opportunities),
        "economic_events_exact": normalized_dataclasses(control_economic_events)
        == normalized_dataclasses(linear_economic_events),
        "completed_lifecycles_exact": normalized_dataclasses(control_trades)
        == normalized_dataclasses(linear_trades),
    }
    return {
        **checks,
        "ignored_identity_only_events": sorted(diagnostic_names),
        "passed": all(checks.values()),
    }


def trade_key(trade: object) -> tuple[int, int, int]:
    return trade.component, trade.decision_bar, trade.direction


def lifecycle_path_delta(
    candidate: list[object], baseline: list[object], sira: object
) -> dict[str, object]:
    candidate_by_key = {trade_key(trade): trade for trade in candidate}
    baseline_by_key = {trade_key(trade): trade for trade in baseline}
    if len(candidate_by_key) != len(candidate) or len(baseline_by_key) != len(baseline):
        raise ValueError("lifecycle key is not unique")
    candidate_keys = set(candidate_by_key)
    baseline_keys = set(baseline_by_key)
    added = candidate_keys - baseline_keys
    removed = baseline_keys - candidate_keys
    shared = candidate_keys & baseline_keys

    def component_counts(
        keys: set[tuple[int, int, int]], rows: dict[tuple[int, int, int], object]
    ) -> dict[str, int]:
        counts = collections.Counter(sira.COMPONENTS[rows[key].component] for key in keys)
        return dict(sorted(counts.items()))

    added_net = sum(candidate_by_key[key].stressed_net for key in added)
    removed_net = sum(baseline_by_key[key].stressed_net for key in removed)
    shared_delta = sum(
        candidate_by_key[key].stressed_net - baseline_by_key[key].stressed_net
        for key in shared
    )
    total_delta = sum(trade.stressed_net for trade in candidate) - sum(
        trade.stressed_net for trade in baseline
    )
    reconstructed = added_net - removed_net + shared_delta
    if not math.isclose(total_delta, reconstructed, abs_tol=1.0e-8):
        raise ValueError("lifecycle delta decomposition failed")
    return {
        "matching_key": "component + decision_bar + direction",
        "shared_lifecycle_count": len(shared),
        "added_lifecycle_count": len(added),
        "added_component_counts": component_counts(added, candidate_by_key),
        "added_stressed_net_usd": added_net,
        "removed_lifecycle_count": len(removed),
        "removed_component_counts": component_counts(removed, baseline_by_key),
        "removed_baseline_stressed_net_usd": removed_net,
        "shared_lifecycle_stressed_net_delta_usd": shared_delta,
        "total_stressed_net_delta_usd": total_delta,
        "decomposition_identity": "added - removed_baseline + shared_delta",
    }


def validate_and_summarize_run(
    spec: RunSpec,
    artifacts_root: Path,
    repository_root: Path,
    sira: object,
) -> tuple[dict[str, object], tuple[list[object], list[object], list[object]]]:
    base = f"selection-2025-{spec.name}"
    paths = [artifacts_root / f"{base}{suffix}" for suffix in REPORT_SUFFIXES]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing run artifacts: {missing}")
    log_path = paths[0]
    report_path = paths[1]
    opportunities, events, trades = sira.build_trades(log_path)
    if [row.opportunity_id for row in opportunities] != list(
        range(1, len(opportunities) + 1)
    ):
        raise ValueError(f"non-contiguous opportunity ids in {log_path}")
    if any(
        not (SELECTION_START <= trade.decision_bar < SELECTION_END)
        for trade in trades
    ):
        raise ValueError(f"out-of-selection trade in {log_path}")

    counts = collections.Counter(event.name for event in events)
    stop_rows = [event for event in events if event.name == "STOP"]
    final, dcrc_final = read_final_lines(log_path)
    report = parse_report(report_path)
    actual_net = sum(trade.actual_net for trade in trades)
    stressed_net = sum(trade.stressed_net for trade in trades)
    actual_dd = sira.closed_drawdown(trades, "actual_net")
    stressed_dd = sira.closed_drawdown(trades, "stressed_net")
    expected_deals = (
        counts["OPEN"]
        + counts["PASSIVE_FILL"]
        + counts["CLOSE"]
        + counts["EXTERNAL_CLOSE"]
        + sum(
            value
            for name, value in counts.items()
            if name.endswith("_PARTIAL") and "CLOSE" in name
        )
    )

    checks = {
        "report_expert_matches": report["expert"] == spec.expected_ea,
        "report_deposit_matches": math.isclose(
            float(report["deposit_usd"]), spec.deposit_usd, abs_tol=1.0e-9
        ),
        "report_period_matches": report["period"]
        == "M30 (2025.01.01 - 2026.01.01)",
        "report_real_ticks": report["history_quality"] == "100% 실제 틱",
        "report_trade_count_matches": int(report["total_trades"]) == len(trades),
        "report_deal_count_matches": int(report["total_deals"]) == expected_deals,
        "report_actual_net_matches_log": math.isclose(
            float(report["actual_net_usd"]), actual_net, abs_tol=0.0051
        ),
        "report_actual_drawdown_matches_log": math.isclose(
            float(report["actual_balance_max_drawdown_usd"]),
            actual_dd,
            abs_tol=0.0051,
        ),
        "normal_stop_once": len(stop_rows) == 1 and stop_rows[0].detail == "normal",
        "normal_deinit_reason": int(final["reason"]) == 1,
        "no_safety_fault": final["safety_stopped"] == "false",
        "no_persistence_fault": final["persistence_failed"] == "false",
        "no_broker_identity_fault": final["broker_mismatch"] == "false",
        "no_foreign_exposure_fault": final["foreign_exposure"] == "false",
        "no_protection_calculation_fault": int(final["protection_calc_failures"])
        == 0,
        "no_protection_mismatch": int(final["protection_mismatches"]) == 0,
        "final_actual_net_matches_lifecycles": math.isclose(
            float(final["project_realized_net"]), actual_net, abs_tol=1.0e-8
        ),
        "final_stressed_net_matches_lifecycles": math.isclose(
            float(final["stressed_net_2x"]), stressed_net, abs_tol=1.0e-8
        ),
        "final_stressed_drawdown_matches_lifecycles": math.isclose(
            float(final["stressed_max_closed_dd"]), stressed_dd, abs_tol=1.0e-8
        ),
        "final_risk_skip_count_matches_events": int(final["risk_admission_skips"])
        == counts["RISK_ADMISSION_SKIP"],
        "dcrc_telemetry_presence_matches_role": (dcrc_final is not None)
        == (spec.policy != "DEPOSIT_ONLY_RESERVE"),
    }
    if dcrc_final is not None:
        checks["dcrc_policy_matches"] = dcrc_final["policy"] == spec.policy
        checks["dcrc_deposit_matches"] = math.isclose(
            float(dcrc_final["deposit"]), spec.deposit_usd, abs_tol=1.0e-9
        )
        checks["dcrc_margin_block_count_matches"] = int(
            dcrc_final["market_margin_or_calc_blocks"]
        ) == counts["DCRC_MARKET_MARGIN_OR_CALC_BLOCK"]
        checks["dcrc_passive_margin_skip_count_matches"] = int(
            dcrc_final["passive_margin_skips"]
        ) == counts["PASSIVE_MARGIN_SKIP"]
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise ValueError(f"integrity check failed for {spec.name}: {failed}")

    periods = {
        period: period_summary(
            trades, start, end, spec.deposit_usd, sira
        )
        for period, (start, end) in PERIODS.items()
    }
    margin_log = logged_margin_observations(log_path)
    exact_margin = (
        {
            "source": "DCRC_FINAL",
            "maximum_margin_usd": float(dcrc_final["maximum_margin_usd"]),
            "maximum_margin_equity_fraction": float(
                dcrc_final["maximum_margin_equity_fraction"]
            ),
            "maximum_margin_equity_percent": float(
                dcrc_final["maximum_margin_equity_fraction"]
            )
            * 100.0,
        }
        if dcrc_final is not None
        else {
            "source": "maximum of persisted log observations; control has no DCRC exact tracker",
            "maximum_margin_usd": margin_log["maximum_margin_usd"],
            "maximum_margin_equity_fraction": margin_log[
                "maximum_margin_equity_fraction"
            ],
            "maximum_margin_equity_percent": margin_log[
                "maximum_margin_equity_percent"
            ],
        }
    )
    relevant_counts = {name: counts[name] for name in RELEVANT_EVENT_NAMES}
    artifact_sources = {
        path.name: source_record(path, repository_root) for path in paths
    }
    config_path = (
        repository_root
        / "lab"
        / "research"
        / "deposit-capital-risk-capacity"
        / "mt5"
        / "config"
        / "tester"
        / f"{base}.ini"
    )
    row: dict[str, object] = {
        "policy": spec.policy,
        "deposit_usd": spec.deposit_usd,
        "reference_capital_usd": spec.reference_capital_usd,
        "role": spec.role,
        "selectable": spec.selectable,
        "integrity": {"passed": True, "checks": checks},
        "report": report,
        "periods": periods,
        "actual_ending_balance_usd": spec.deposit_usd + actual_net,
        "stressed_ending_balance_equivalent_usd": spec.deposit_usd + stressed_net,
        "internal_final_summary": {
            key: final[key]
            for key in (
                "portfolio",
                "reason",
                "stressed_balance_2x",
                "stressed_net_2x",
                "stressed_max_closed_dd",
                "project_realized_net",
                "project_stage_balance",
                "max_aggregate_planned_risk",
            )
        },
        "opportunity_count": len(opportunities),
        "opportunity_outcome_counts": dict(
            sorted(collections.Counter(row.outcome for row in opportunities).items())
        ),
        "event_counts": relevant_counts,
        "risk_admission_skip_component_counts": event_component_counts(
            events, "RISK_ADMISSION_SKIP", sira
        ),
        "volume_distribution": volume_distribution(trades),
        "sizing": sizing_summary(events),
        "overlap": sira.overlap_pair_summary(trades),
        "margin": {"selection_metric": exact_margin, "logged": margin_log},
        "component_performance_2025_full": component_summary(
            trades, spec.deposit_usd, sira
        ),
        "sources": {
            "configuration": source_record(config_path, repository_root),
            "artifacts": artifact_sources,
        },
    }
    if dcrc_final is not None:
        row["dcrc_final"] = {
            "policy": dcrc_final["policy"],
            "deposit_usd": float(dcrc_final["deposit"]),
            "sizing_day_transitions": int(dcrc_final["sizing_interventions"]),
            "market_margin_or_calculation_blocks": int(
                dcrc_final["market_margin_or_calc_blocks"]
            ),
            "passive_margin_skips": int(dcrc_final["passive_margin_skips"]),
            "maximum_margin_usd": float(dcrc_final["maximum_margin_usd"]),
            "maximum_margin_equity_fraction": float(
                dcrc_final["maximum_margin_equity_fraction"]
            ),
            "maximum_entry_volume": float(dcrc_final["maximum_entry_volume"]),
        }
        if row["dcrc_final"]["sizing_day_transitions"] != row["sizing"][
            "transition_count"
        ]:
            raise ValueError(f"sizing transition mismatch for {spec.name}")
    return row, (opportunities, events, trades)


def candidate_gate(
    policy: str,
    run_rows: dict[str, dict[str, object]],
    integrity_by_run: dict[str, bool],
) -> dict[str, object]:
    prefix = "breadth" if policy == "BREADTH_DOLLAR_SLOTS" else "ladder"
    selectable = policy == "BREADTH_DOLLAR_SLOTS"
    deposit_rows: dict[str, dict[str, object]] = {}
    all_positive = True
    risk_pass_both = True
    efficiency_pass_both = True
    return_floor_pass_both = True
    integrity_pass_both = True
    for deposit in (200, 300):
        candidate_name = f"{prefix}-{deposit}"
        linear_name = f"linear-{deposit}"
        candidate_full = run_rows[candidate_name]["periods"]["2025_FULL"]
        linear_full = run_rows[linear_name]["periods"]["2025_FULL"]
        positive = all(
            run_rows[candidate_name]["periods"][period]["stressed_net_usd"] > 0.0
            for period in PERIODS
        )
        risk_pass = (
            candidate_full["stressed_max_closed_drawdown_percent"]
            <= linear_full["stressed_max_closed_drawdown_percent"] + 0.10 + 1.0e-12
        )
        efficiency_pass = (
            candidate_full["stressed_net_to_drawdown"]
            > linear_full["stressed_net_to_drawdown"] + 1.0e-12
        )
        return_floor = 0.90 * linear_full["stressed_return_percent"]
        return_pass = candidate_full["stressed_return_percent"] + 1.0e-12 >= return_floor
        integrity_pass = integrity_by_run[candidate_name]
        all_positive = all_positive and positive
        risk_pass_both = risk_pass_both and risk_pass
        efficiency_pass_both = efficiency_pass_both and efficiency_pass
        return_floor_pass_both = return_floor_pass_both and return_pass
        integrity_pass_both = integrity_pass_both and integrity_pass
        deposit_rows[str(deposit)] = {
            "positive_stressed_net_h1_h2_full": positive,
            "candidate_stressed_return_percent": candidate_full[
                "stressed_return_percent"
            ],
            "linear_stressed_return_percent": linear_full[
                "stressed_return_percent"
            ],
            "required_return_floor_percent": return_floor,
            "return_floor_pass": return_pass,
            "candidate_stressed_drawdown_percent": candidate_full[
                "stressed_max_closed_drawdown_percent"
            ],
            "linear_stressed_drawdown_percent": linear_full[
                "stressed_max_closed_drawdown_percent"
            ],
            "drawdown_delta_percentage_points": candidate_full[
                "stressed_max_closed_drawdown_percent"
            ]
            - linear_full["stressed_max_closed_drawdown_percent"],
            "risk_pass": risk_pass,
            "candidate_stressed_net_to_drawdown": candidate_full[
                "stressed_net_to_drawdown"
            ],
            "linear_stressed_net_to_drawdown": linear_full[
                "stressed_net_to_drawdown"
            ],
            "efficiency_delta": candidate_full["stressed_net_to_drawdown"]
            - linear_full["stressed_net_to_drawdown"],
            "efficiency_pass": efficiency_pass,
            "integrity_pass": integrity_pass,
        }
    economic_gate_passed = (
        all_positive
        and risk_pass_both
        and efficiency_pass_both
        and return_floor_pass_both
        and integrity_pass_both
    )
    return {
        "selectable_under_proxy_freeze": selectable,
        "diagnostic_only": not selectable,
        "by_deposit": deposit_rows,
        "positive_periods_both_deposits": all_positive,
        "risk_pass_both_deposits": risk_pass_both,
        "efficiency_pass_both_deposits": efficiency_pass_both,
        "return_floor_pass_both_deposits": return_floor_pass_both,
        "integrity_pass_both_deposits": integrity_pass_both,
        "economic_gate_passed": economic_gate_passed,
        "passed": selectable and economic_gate_passed,
    }


def run_analysis(artifacts_root: Path, output: Path) -> None:
    script_path = Path(__file__).resolve()
    repository_root = script_path.parents[3]
    sira = load_sira_analysis(repository_root)
    rows: dict[str, dict[str, object]] = {}
    parsed: dict[str, tuple[list[object], list[object], list[object]]] = {}
    for spec in RUNS:
        rows[spec.name], parsed[spec.name] = validate_and_summarize_run(
            spec, artifacts_root, repository_root, sira
        )

    anchor = economic_identity_check(parsed["control-100"], parsed["linear-100"])
    linear_100 = rows["linear-100"]["periods"]["2025_FULL"]
    scale_by_deposit: dict[str, dict[str, object]] = {}
    scale_pass = True
    for deposit in (200, 300):
        metrics = rows[f"linear-{deposit}"]["periods"]["2025_FULL"]
        return_delta = metrics["stressed_return_percent"] - linear_100[
            "stressed_return_percent"
        ]
        drawdown_delta = metrics["stressed_max_closed_drawdown_percent"] - linear_100[
            "stressed_max_closed_drawdown_percent"
        ]
        passed = abs(return_delta) <= 0.50 + 1.0e-12 and abs(drawdown_delta) <= 0.50 + 1.0e-12
        scale_pass = scale_pass and passed
        scale_by_deposit[str(deposit)] = {
            "stressed_return_percent": metrics["stressed_return_percent"],
            "return_delta_vs_linear_100_percentage_points": return_delta,
            "stressed_drawdown_percent": metrics[
                "stressed_max_closed_drawdown_percent"
            ],
            "drawdown_delta_vs_linear_100_percentage_points": drawdown_delta,
            "within_0_50_percentage_point_tolerance": passed,
        }

    integrity_by_run = {
        name: bool(row["integrity"]["passed"]) for name, row in rows.items()
    }
    gates = {
        policy: candidate_gate(policy, rows, integrity_by_run)
        for policy in ("BREADTH_DOLLAR_SLOTS", "FIXED_LOT_LADDER")
    }
    passing = [policy for policy, gate in gates.items() if gate["passed"]]
    if len(passing) > 1:
        raise ValueError("predeclared at-most-one selection rule violated")

    comparisons = {
        "deposit_only_200_vs_100": lifecycle_path_delta(
            parsed["control-200"][2], parsed["control-100"][2], sira
        ),
        "deposit_only_300_vs_100": lifecycle_path_delta(
            parsed["control-300"][2], parsed["control-100"][2], sira
        ),
        "breadth_200_vs_same_lot_deposit_control_200": lifecycle_path_delta(
            parsed["breadth-200"][2], parsed["control-200"][2], sira
        ),
        "breadth_300_vs_same_lot_deposit_control_300": lifecycle_path_delta(
            parsed["breadth-300"][2], parsed["control-300"][2], sira
        ),
        "ladder_200_vs_linear_200": lifecycle_path_delta(
            parsed["ladder-200"][2], parsed["linear-200"][2], sira
        ),
        "ladder_300_vs_linear_300": lifecycle_path_delta(
            parsed["ladder-300"][2], parsed["linear-300"][2], sira
        ),
    }

    declaration = (
        repository_root
        / "lab"
        / "evidence"
        / "DEPOSIT_CAPITAL_RISK_CAPACITY_DECLARATION_V1.json"
    )
    proxy = (
        repository_root
        / "lab"
        / "evidence"
        / "DEPOSIT_CAPITAL_RISK_CAPACITY_PROXY_V1.json"
    )
    compile_receipt = (
        repository_root
        / "lab"
        / "evidence"
        / "DEPOSIT_CAPITAL_RISK_CAPACITY_COMPILE_RECEIPT_V1.json"
    )
    payload = {
        "schema_version": 1,
        "record_type": "ea_selection_result",
        "research_family_ko": "예치자본·위험용량 연구",
        "research_family_slug": "deposit-capital-risk-capacity",
        "version": "V1",
        "source_commit_required": "09e32e15923d0a3037c03d6151a3637c5f0007f1",
        "selection_period": ["2025-01-01", "2026-01-01"],
        "selection_rows_consumed": True,
        "conditional_2026_confirmation_consumed": False,
        "held_out_2026_june_through_partial_august_consumed": False,
        "execution": {
            "platform": "MetaTrader 5 strategy tester build 6140",
            "broker_report": "FPMarketsSC-Live",
            "model": "100% real ticks",
            "serial_runs": True,
            "fresh_account_each_run": True,
            "run_count": len(RUNS),
            "all_integrity_checks_passed": all(integrity_by_run.values()),
        },
        "analysis_source": source_record(script_path, repository_root),
        "frozen_inputs": {
            "declaration": source_record(declaration, repository_root),
            "proxy": source_record(proxy, repository_root),
            "compile_receipt": source_record(compile_receipt, repository_root),
        },
        "runs": rows,
        "linear_anchor_gate": {
            "linear_100_identity": anchor,
            "scale_consistency_by_deposit": scale_by_deposit,
            "linear_100_identity_passed": anchor["passed"],
            "linear_scale_consistency_passed": scale_pass,
            "passed": anchor["passed"] and scale_pass,
        },
        "candidate_gates": gates,
        "lifecycle_path_comparisons": comparisons,
        "selection_gate": {
            "passing_non_control_policies": passing,
            "selected_policy": passing[0] if passing else None,
            "verdict": (
                "POLICY_FIXED_FOR_CONDITIONAL_2026_CONFIRMATION"
                if passing
                else "NO_NON_CONTROL_POLICY_PASSED_CLOSE_RETAIN_FROZEN_V7"
            ),
            "conditional_2026_confirmation_opened": bool(passing),
            "live_change_or_promotion_authorized": False,
        },
        "interpretation_limits": [
            "LINEAR_CAPITAL is the mandatory scaling anchor, not a competing allocation policy.",
            "The breadth EA fixes 0.01 volume and approximately 4 starting risk dollars, but its percentage risk fraction acts on changing conservative capital; shared stop geometry can therefore diverge by deposit and path.",
            "Lifecycle matching by component, decision bar, and direction is a path decomposition, not an oracle counterfactual after rejected signals.",
            "No result grants Live-dev source, settings, process, or promotion authority.",
        ],
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
                "linear_anchor_passed": payload["linear_anchor_gate"]["passed"],
                "passing_non_control_policies": passing,
                "verdict": payload["selection_gate"]["verdict"],
                "conditional_2026_confirmation_consumed": False,
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    arguments = parse_args()
    run_analysis(arguments.artifacts_root.resolve(), arguments.output.resolve())


if __name__ == "__main__":
    main()
