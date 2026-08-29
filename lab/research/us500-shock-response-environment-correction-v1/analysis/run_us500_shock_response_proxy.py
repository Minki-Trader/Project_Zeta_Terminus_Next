from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


FAMILY = "us500-shock-response-environment-correction-v1"
ROOT = Path(__file__).resolve().parents[4]
FAMILY_ROOT = ROOT / "lab" / "research" / FAMILY
DECLARATION_PATH = FAMILY_ROOT / "evidence" / "US500_SHOCK_RESPONSE_ENVIRONMENT_CORRECTION_DECLARATION_V1.json"
ACQUISITION_RECEIPT_PATH = FAMILY_ROOT / "evidence" / "US500_SHOCK_RESPONSE_ENVIRONMENT_CORRECTION_ACQUISITION_RECEIPT_V1.json"
RESULT_PATH = FAMILY_ROOT / "evidence" / "US500_SHOCK_RESPONSE_ENVIRONMENT_CORRECTION_RESULT_V1.json"
INPUT_ROOT = ROOT / "lab" / "artifacts" / "raw" / FAMILY / "input"
OUTPUT_ROOT = ROOT / "lab" / "artifacts" / "raw" / FAMILY / "output"
BAR_PATH = INPUT_ROOT / "US500_M15_BARS_20220701_20260821.csv"
SPEC_PATH = INPUT_ROOT / "US500_SYMBOL_SPEC_V1.json"
STRUCTURAL_ANCHOR_PATH = INPUT_ROOT / "UNIT027_P1_SIGNAL_STRUCTURE.csv"
OPPORTUNITY_PATH = OUTPUT_ROOT / "US500_SHOCK_RESPONSE_PROXY_OPPORTUNITIES_V1.csv"

IMPULSE_BARS = 4
BASELINE_RETURNS = 32
HORIZON_BARS = 4
TRIGGER_Z = 2.0
REARM_Z = 1.0
VOLUME = 0.01
EXPECTED_COLUMNS = (
    "time_epoch",
    "time_server",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
)
PERIODS = (
    ("P1_2022H2_2023", datetime(2022, 8, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, tzinfo=timezone.utc)),
    ("P2_2024", datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2025, 1, 1, tzinfo=timezone.utc)),
    ("P3_2025", datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, tzinfo=timezone.utc)),
    ("P4_2026_YTD", datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 8, 22, tzinfo=timezone.utc)),
)


@dataclass(frozen=True)
class Bar:
    epoch: int
    time_server: str
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    spread_points: int
    real_volume: int


@dataclass(frozen=True)
class SignalObservation:
    trigger_time: str
    resolve_time: str
    market_bars_held: int
    shock_score: float
    signed_impulse: float
    impulse_sign: int


@dataclass(frozen=True)
class Opportunity:
    period: str
    opportunity_id: int
    trigger_time: str
    resolve_time: str
    elapsed_seconds: int
    market_bars_held: int
    shock_score: float
    signed_impulse: float
    impulse_sign: int
    entry_bid: float
    entry_ask: float
    entry_spread: float
    exit_bid: float
    exit_ask: float
    exit_spread: float
    continuation_direction: int
    reversion_direction: int
    continuation_observed_usd: float
    continuation_double_spread_usd: float
    reversion_observed_usd: float
    reversion_double_spread_usd: float


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    require(isinstance(value, dict), f"JSON root must be an object: {relative(path)}")
    return value


def load_bars() -> tuple[list[Bar], dict[str, Any]]:
    bars: list[Bar] = []
    with BAR_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        require(tuple(reader.fieldnames or ()) == EXPECTED_COLUMNS, "bar columns differ from the frozen schema")
        previous_epoch = -1
        for row_number, row in enumerate(reader, start=2):
            epoch = int(row["time_epoch"])
            require(epoch > previous_epoch, f"bar epochs not strictly increasing at CSV row {row_number}")
            previous_epoch = epoch
            ohlc = tuple(float(row[name]) for name in ("open", "high", "low", "close"))
            require(all(math.isfinite(value) and value > 0.0 for value in ohlc), f"invalid OHLC at CSV row {row_number}")
            tick_volume = int(row["tick_volume"])
            spread = int(row["spread"])
            real_volume = int(row["real_volume"])
            require(tick_volume >= 0 and spread >= 0 and real_volume >= 0, f"negative volume/spread at CSV row {row_number}")
            expected_time = datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y.%m.%d %H:%M:%S")
            require(row["time_server"] == expected_time, f"epoch/time mismatch at CSV row {row_number}")
            bars.append(
                Bar(
                    epoch=epoch,
                    time_server=row["time_server"],
                    open=ohlc[0],
                    high=ohlc[1],
                    low=ohlc[2],
                    close=ohlc[3],
                    tick_volume=tick_volume,
                    spread_points=spread,
                    real_volume=real_volume,
                )
            )
    require(len(bars) > 37, "insufficient M15 history")
    return bars, {
        "rows": len(bars),
        "first_time": bars[0].time_server,
        "last_time": bars[-1].time_server,
        "strictly_increasing": True,
        "positive_ohlc": True,
        "nonnegative_volume_and_spread": True,
    }


def read_shock_state(bars: list[Bar], current_index: int) -> tuple[float, float]:
    require(current_index >= IMPULSE_BARS + BASELINE_RETURNS + 1, "insufficient warmup")
    newest_close = bars[current_index - 1].close
    impulse_origin_close = bars[current_index - 1 - IMPULSE_BARS].close
    signed_impulse = math.log(newest_close / impulse_origin_close)
    returns = []
    for offset in range(BASELINE_RETURNS):
        newer_index = current_index - 1 - IMPULSE_BARS - offset
        older_index = newer_index - 1
        returns.append(math.log(bars[newer_index].close / bars[older_index].close))
    mean = sum(returns) / BASELINE_RETURNS
    variance = sum((value - mean) ** 2 for value in returns) / (BASELINE_RETURNS - 1)
    require(variance > 0.0, "nonpositive baseline variance")
    four_bar_volatility = math.sqrt(variance) * math.sqrt(IMPULSE_BARS)
    shock_score = abs(signed_impulse) / four_bar_volatility
    require(math.isfinite(shock_score), "nonfinite shock score")
    return signed_impulse, shock_score


def direction_profit(direction: int, open_price: float, close_price: float, spec: dict[str, Any]) -> float:
    tick_size = float(spec["trade_tick_size"])
    tick_value = float(spec["trade_tick_value"])
    require(tick_size > 0.0 and tick_value > 0.0, "invalid tick economics")
    signed_distance = close_price - open_price if direction > 0 else open_price - close_price
    return signed_distance / tick_size * tick_value * VOLUME


def run_period_structure(
    bars: list[Bar], period: str, start: datetime, end: datetime, spec: dict[str, Any]
) -> tuple[list[SignalObservation], dict[str, Any]]:
    point = float(spec["point"])
    indices = [index for index, bar in enumerate(bars) if int(start.timestamp()) <= bar.epoch < int(end.timestamp())]
    require(indices, f"no bars in {period}")
    armed = True
    active: dict[str, Any] | None = None
    evaluations = 0
    normal_dates: set[str] = set()
    triggers = 0
    observations: list[SignalObservation] = []
    rate_faults = 0
    tick_faults = 0

    for index in indices:
        bar = bars[index]
        bid = bar.open
        ask = bid + bar.spread_points * point
        if bid <= 0.0 or ask < bid:
            tick_faults += 1
            continue

        resolved_this_bar = False
        if active is not None:
            active["market_bars_held"] += 1
            if active["market_bars_held"] >= HORIZON_BARS:
                observations.append(
                    SignalObservation(
                        trigger_time=str(active["trigger_time"]),
                        resolve_time=bar.time_server,
                        market_bars_held=int(active["market_bars_held"]),
                        shock_score=float(active["shock_score"]),
                        signed_impulse=float(active["signed_impulse"]),
                        impulse_sign=int(active["impulse_sign"]),
                    )
                )
                active = None
                resolved_this_bar = True

        try:
            signed_impulse, shock_score = read_shock_state(bars, index)
        except (RuntimeError, ValueError, ZeroDivisionError):
            rate_faults += 1
            continue
        evaluations += 1
        normal_dates.add(bar.time_server[:10])

        if not armed and shock_score <= REARM_Z:
            armed = True
        if active is None and not resolved_this_bar and armed and shock_score >= TRIGGER_Z and signed_impulse != 0.0:
            triggers += 1
            active = {
                "trigger_epoch": bar.epoch,
                "trigger_time": bar.time_server,
                "shock_score": shock_score,
                "signed_impulse": signed_impulse,
                "impulse_sign": 1 if signed_impulse > 0.0 else -1,
                "market_bars_held": 0,
            }
            armed = False

    return observations, {
        "period": period,
        "first_processed_bar": bars[indices[0]].time_server,
        "last_processed_bar": bars[indices[-1]].time_server,
        "normal_days": len(normal_dates),
        "evaluations": evaluations,
        "triggers": triggers,
        "resolved": len(observations),
        "unresolved": 1 if active is not None else 0,
        "rate_faults": rate_faults,
        "tick_faults": tick_faults,
        "profit_calc_faults": 0,
    }


def run_period(bars: list[Bar], period: str, start: datetime, end: datetime, spec: dict[str, Any]) -> tuple[list[Opportunity], dict[str, Any]]:
    point = float(spec["point"])
    indices = [index for index, bar in enumerate(bars) if int(start.timestamp()) <= bar.epoch < int(end.timestamp())]
    require(indices, f"no bars in {period}")
    armed = True
    active: dict[str, Any] | None = None
    evaluations = 0
    normal_dates: set[str] = set()
    triggers = 0
    opportunities: list[Opportunity] = []
    rate_faults = 0
    tick_faults = 0
    profit_calc_faults = 0

    for index in indices:
        bar = bars[index]
        entry_or_exit_bid = bar.open
        spread = bar.spread_points * point
        entry_or_exit_ask = entry_or_exit_bid + spread
        if entry_or_exit_bid <= 0.0 or entry_or_exit_ask < entry_or_exit_bid:
            tick_faults += 1
            continue

        resolved_this_bar = False
        if active is not None:
            active["market_bars_held"] += 1
            if active["market_bars_held"] >= HORIZON_BARS:
                continuation_direction = int(active["impulse_sign"])
                reversion_direction = -continuation_direction
                entry_bid = float(active["entry_bid"])
                entry_ask = float(active["entry_ask"])
                entry_spread = float(active["entry_spread"])
                exit_bid = entry_or_exit_bid
                exit_ask = entry_or_exit_ask
                exit_spread = spread

                def four_profits(direction: int) -> tuple[float, float]:
                    if direction > 0:
                        observed = direction_profit(direction, entry_ask, exit_bid, spec)
                        doubled = direction_profit(direction, entry_ask + entry_spread, exit_bid - exit_spread, spec)
                    else:
                        observed = direction_profit(direction, entry_bid, exit_ask, spec)
                        doubled = direction_profit(direction, entry_bid - entry_spread, exit_ask + exit_spread, spec)
                    return observed, doubled

                continuation_observed, continuation_double = four_profits(continuation_direction)
                reversion_observed, reversion_double = four_profits(reversion_direction)
                opportunities.append(
                    Opportunity(
                        period=period,
                        opportunity_id=len(opportunities) + 1,
                        trigger_time=str(active["trigger_time"]),
                        resolve_time=bar.time_server,
                        elapsed_seconds=bar.epoch - int(active["trigger_epoch"]),
                        market_bars_held=int(active["market_bars_held"]),
                        shock_score=float(active["shock_score"]),
                        signed_impulse=float(active["signed_impulse"]),
                        impulse_sign=continuation_direction,
                        entry_bid=entry_bid,
                        entry_ask=entry_ask,
                        entry_spread=entry_spread,
                        exit_bid=exit_bid,
                        exit_ask=exit_ask,
                        exit_spread=exit_spread,
                        continuation_direction=continuation_direction,
                        reversion_direction=reversion_direction,
                        continuation_observed_usd=continuation_observed,
                        continuation_double_spread_usd=continuation_double,
                        reversion_observed_usd=reversion_observed,
                        reversion_double_spread_usd=reversion_double,
                    )
                )
                active = None
                resolved_this_bar = True

        try:
            signed_impulse, shock_score = read_shock_state(bars, index)
        except (RuntimeError, ValueError, ZeroDivisionError):
            rate_faults += 1
            continue
        evaluations += 1
        normal_dates.add(bar.time_server[:10])

        if not armed and shock_score <= REARM_Z:
            armed = True
        if active is None and not resolved_this_bar and armed and shock_score >= TRIGGER_Z and signed_impulse != 0.0:
            triggers += 1
            active = {
                "trigger_epoch": bar.epoch,
                "trigger_time": bar.time_server,
                "shock_score": shock_score,
                "signed_impulse": signed_impulse,
                "impulse_sign": 1 if signed_impulse > 0.0 else -1,
                "entry_bid": entry_or_exit_bid,
                "entry_ask": entry_or_exit_ask,
                "entry_spread": spread,
                "market_bars_held": 0,
            }
            armed = False

    return opportunities, {
        "period": period,
        "first_processed_bar": bars[indices[0]].time_server,
        "last_processed_bar": bars[indices[-1]].time_server,
        "normal_days": len(normal_dates),
        "evaluations": evaluations,
        "triggers": triggers,
        "resolved": len(opportunities),
        "unresolved": 1 if active is not None else 0,
        "rate_faults": rate_faults,
        "tick_faults": tick_faults,
        "profit_calc_faults": profit_calc_faults,
    }


def load_structural_anchor() -> list[dict[str, str]]:
    expected = ("trigger_time", "resolve_time", "market_bars_held", "shock_score", "signed_impulse", "impulse_sign")
    with STRUCTURAL_ANCHOR_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        require(tuple(reader.fieldnames or ()) == expected, "Unit027 structural-anchor columns differ")
        return list(reader)


def compare_p1_structure(opportunities: list[SignalObservation], anchor: list[dict[str, str]]) -> dict[str, Any]:
    exact_tick_timestamp_identity_matches = 0
    bar_coordinate_identity_matches = 0
    max_score_abs_difference = 0.0
    max_impulse_abs_difference = 0.0
    first_bar_coordinate_mismatch: dict[str, Any] | None = None
    for index, (observed, expected) in enumerate(zip(opportunities, anchor), start=1):
        exact_tick_timestamp_identity = (
            observed.trigger_time == expected["trigger_time"]
            and observed.resolve_time == expected["resolve_time"]
            and observed.market_bars_held == int(expected["market_bars_held"])
            and observed.impulse_sign == int(expected["impulse_sign"])
        )
        if exact_tick_timestamp_identity:
            exact_tick_timestamp_identity_matches += 1
        bar_coordinate_identity = (
            observed.trigger_time[:16] == expected["trigger_time"][:16]
            and observed.resolve_time[:16] == expected["resolve_time"][:16]
            and observed.market_bars_held == int(expected["market_bars_held"])
            and observed.impulse_sign == int(expected["impulse_sign"])
        )
        if bar_coordinate_identity:
            bar_coordinate_identity_matches += 1
        elif first_bar_coordinate_mismatch is None:
            first_bar_coordinate_mismatch = {
                "row": index,
                "observed_trigger": observed.trigger_time,
                "expected_trigger": expected["trigger_time"],
                "observed_resolve": observed.resolve_time,
                "expected_resolve": expected["resolve_time"],
            }
        max_score_abs_difference = max(max_score_abs_difference, abs(observed.shock_score - float(expected["shock_score"])))
        max_impulse_abs_difference = max(max_impulse_abs_difference, abs(observed.signed_impulse - float(expected["signed_impulse"])))
    count_equal = len(opportunities) == len(anchor)
    return {
        "anchor_rows": len(anchor),
        "proxy_rows": len(opportunities),
        "count_equal": count_equal,
        "exact_tick_timestamp_horizon_sign_identity_rows_descriptive": exact_tick_timestamp_identity_matches,
        "m15_bar_coordinate_horizon_sign_identity_rows": bar_coordinate_identity_matches,
        "all_m15_bar_coordinate_horizon_sign_identities_equal": count_equal and bar_coordinate_identity_matches == len(anchor),
        "max_score_abs_difference": max_score_abs_difference,
        "score_tolerance": 5e-10,
        "score_within_tolerance": count_equal and max_score_abs_difference <= 5e-10,
        "max_signed_impulse_abs_difference": max_impulse_abs_difference,
        "signed_impulse_tolerance": 5e-12,
        "signed_impulse_within_tolerance": count_equal and max_impulse_abs_difference <= 5e-12,
        "first_bar_coordinate_mismatch": first_bar_coordinate_mismatch,
    }


def metrics(values: Iterable[float]) -> dict[str, Any]:
    sequence = list(values)
    wins = [value for value in sequence if value > 0.0]
    losses = [value for value in sequence if value < 0.0]
    zeros = len(sequence) - len(wins) - len(losses)
    gross_profit = sum(wins)
    gross_loss = sum(losses)
    profit_factor = gross_profit / abs(gross_loss) if gross_loss < 0.0 else None
    running = 0.0
    peak = 0.0
    maximum_closed_drawdown = 0.0
    for value in sequence:
        running += value
        peak = max(peak, running)
        maximum_closed_drawdown = max(maximum_closed_drawdown, peak - running)
    return {
        "opportunities": len(sequence),
        "net_usd": sum(sequence),
        "wins": len(wins),
        "losses": len(losses),
        "zeros": zeros,
        "gross_profit_usd": gross_profit,
        "gross_loss_usd": gross_loss,
        "profit_factor": profit_factor,
        "maximum_closed_drawdown_usd": maximum_closed_drawdown,
        "net_over_maximum_closed_drawdown": (sum(sequence) / maximum_closed_drawdown if maximum_closed_drawdown > 0.0 else None),
    }


def direction_values(opportunities: list[Opportunity], direction: str, cost_book: str) -> list[float]:
    field = f"{direction.lower()}_{cost_book}_usd"
    return [float(getattr(row, field)) for row in opportunities]


def aggregate_economics(period_opportunities: dict[str, list[Opportunity]], period_summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    direction_books: dict[str, Any] = {}
    for direction in ("CONTINUATION", "REVERSION"):
        per_period: dict[str, Any] = {}
        pooled_observed: list[float] = []
        pooled_double: list[float] = []
        positive_path_double_nets: list[float] = []
        for period, _, _ in PERIODS:
            rows = period_opportunities[period]
            observed = direction_values(rows, direction, "observed")
            doubled = direction_values(rows, direction, "double_spread")
            observed_metrics = metrics(observed)
            double_metrics = metrics(doubled)
            per_period[period] = {
                "normal_days": period_summaries[period]["normal_days"],
                "opportunities_per_normal_day": len(rows) / period_summaries[period]["normal_days"],
                "observed": observed_metrics,
                "double_spread": double_metrics,
            }
            pooled_observed.extend(observed)
            pooled_double.extend(doubled)
            if double_metrics["net_usd"] > 0.0:
                positive_path_double_nets.append(double_metrics["net_usd"])
        total_positive = sum(positive_path_double_nets)
        concentration = max(positive_path_double_nets) / total_positive if total_positive > 0.0 else 1.0
        pooled_double_metrics = metrics(pooled_double)
        direction_books[direction] = {
            "periods": per_period,
            "pooled": {
                "normal_days": sum(period_summaries[name]["normal_days"] for name, _, _ in PERIODS),
                "opportunities_per_normal_day": len(pooled_double) / sum(period_summaries[name]["normal_days"] for name, _, _ in PERIODS),
                "observed": metrics(pooled_observed),
                "double_spread": pooled_double_metrics,
                "positive_periods_double_spread": sum(1 for name, _, _ in PERIODS if per_period[name]["double_spread"]["net_usd"] > 0.0),
                "maximum_positive_path_contribution_share": concentration,
            },
        }
    return direction_books


def evaluate_gates(direction_books: dict[str, Any], period_summaries: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    pooled_resolved = sum(summary["resolved"] for summary in period_summaries.values())
    pooled_days = sum(summary["normal_days"] for summary in period_summaries.values())
    period_frequency_passes = sum(1 for summary in period_summaries.values() if summary["resolved"] / summary["normal_days"] >= 0.25)
    frequency = {
        "pooled_opportunities_per_normal_day": pooled_resolved / pooled_days,
        "pooled_at_least_0_50": pooled_resolved / pooled_days >= 0.50,
        "periods_at_least_0_25": period_frequency_passes,
        "at_least_three_periods_at_0_25": period_frequency_passes >= 3,
        "pooled_opportunities": pooled_resolved,
        "pooled_at_least_100": pooled_resolved >= 100,
    }
    frequency["all_pass"] = bool(frequency["pooled_at_least_0_50"] and frequency["at_least_three_periods_at_0_25"] and frequency["pooled_at_least_100"])
    passing: list[str] = []
    economic: dict[str, Any] = {}
    for direction in ("CONTINUATION", "REVERSION"):
        pooled = direction_books[direction]["pooled"]
        doubled = pooled["double_spread"]
        pf = doubled["profit_factor"]
        ratio = doubled["net_over_maximum_closed_drawdown"]
        gates = {
            "positive_pooled_double_spread_net": doubled["net_usd"] > 0.0,
            "pooled_double_spread_profit_factor_at_least_1_10": pf is not None and pf >= 1.10,
            "positive_double_spread_periods_at_least_three": pooled["positive_periods_double_spread"] >= 3,
            "pooled_net_over_maximum_closed_drawdown_at_least_1_50": ratio is not None and ratio >= 1.50,
            "maximum_positive_path_contribution_share_at_most_0_70": pooled["maximum_positive_path_contribution_share"] <= 0.70,
        }
        gates["all_pass"] = bool(frequency["all_pass"] and all(gates.values()))
        economic[direction] = gates
        if gates["all_pass"]:
            passing.append(direction)
    passing.sort(
        key=lambda direction: (
            -direction_books[direction]["pooled"]["double_spread"]["net_usd"],
            -(direction_books[direction]["pooled"]["double_spread"]["profit_factor"] or -math.inf),
            -direction_books[direction]["pooled"]["positive_periods_double_spread"],
            direction,
        )
    )
    return {"frequency": frequency, "economic": economic}, passing


def write_opportunities(rows: list[Opportunity]) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    temp_path = OPPORTUNITY_PATH.with_suffix(OPPORTUNITY_PATH.suffix + ".tmp")
    fieldnames = list(Opportunity.__dataclass_fields__)
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)
    os.replace(temp_path, OPPORTUNITY_PATH)


def main() -> int:
    started = time.perf_counter()
    declaration = load_json(DECLARATION_PATH)
    receipt = load_json(ACQUISITION_RECEIPT_PATH)
    spec = load_json(SPEC_PATH)
    script_path = Path(__file__).resolve()
    require(sha256(script_path) == declaration["implementation"]["proxy_script_sha256"], "proxy script hash differs from declaration")
    for pin in declaration["unit027_provenance"]:
        path = ROOT / pin["path"]
        require(path.stat().st_size == pin["bytes"], f"Unit027 provenance bytes differ: {pin['path']}")
        require(sha256(path) == pin["sha256"], f"Unit027 provenance hash differs: {pin['path']}")
    for path, pin in ((BAR_PATH, receipt["bar_export"]), (SPEC_PATH, receipt["symbol_spec"])):
        require(relative(path) == pin["path"], f"receipt path mismatch: {relative(path)}")
        require(path.stat().st_size == pin["bytes"], f"receipt bytes mismatch: {relative(path)}")
        require(sha256(path) == pin["sha256"], f"receipt hash mismatch: {relative(path)}")
    anchor_pin = declaration["structural_anchor"]
    require(STRUCTURAL_ANCHOR_PATH.stat().st_size == anchor_pin["bytes"], "structural anchor bytes differ")
    require(sha256(STRUCTURAL_ANCHOR_PATH) == anchor_pin["sha256"], "structural anchor hash differs")

    require(spec["symbol"] == "US500", "symbol spec is not US500")
    require(int(spec["digits"]) == 2, "US500 digits differ")
    require(float(spec["point"]) == 0.01, "US500 point differs")
    require(float(spec["trade_tick_size"]) == 0.01, "US500 tick size differs")
    require(float(spec["trade_tick_value"]) == 0.01, "US500 tick value differs")
    require(float(spec["trade_contract_size"]) == 1.0, "US500 contract size differs")
    require(float(spec["volume_min"]) == 0.01 and float(spec["volume_step"]) == 0.01, "US500 volume contract differs")

    bars, bar_integrity = load_bars()
    structural_period_rows: dict[str, list[SignalObservation]] = {}
    structural_period_summaries: dict[str, dict[str, Any]] = {}
    for period, start, end in PERIODS:
        rows, summary = run_period_structure(bars, period, start, end, spec)
        structural_period_rows[period] = rows
        structural_period_summaries[period] = summary

    structural_anchor = load_structural_anchor()
    p1_structure = compare_p1_structure(structural_period_rows["P1_2022H2_2023"], structural_anchor)
    p1_summary = structural_period_summaries["P1_2022H2_2023"]
    structural_integrity = {
        "expected_p1_normal_days": 366,
        "expected_p1_evaluations": 33453,
        "expected_p1_triggers": 1264,
        "expected_p1_resolved": 1264,
        "p1_summary_anchor_equal": (
            p1_summary["normal_days"] == 366
            and p1_summary["evaluations"] == 33453
            and p1_summary["triggers"] == 1264
            and p1_summary["resolved"] == 1264
            and p1_summary["unresolved"] == 0
            and p1_summary["rate_faults"] == 0
            and p1_summary["tick_faults"] == 0
            and p1_summary["profit_calc_faults"] == 0
        ),
        "p1_signal_structure": p1_structure,
    }
    structural_integrity["all_pass"] = bool(
        structural_integrity["p1_summary_anchor_equal"]
        and p1_structure["all_m15_bar_coordinate_horizon_sign_identities_equal"]
        and p1_structure["score_within_tolerance"]
        and p1_structure["signed_impulse_within_tolerance"]
    )
    require(structural_integrity["all_pass"], "Unit027 structural parity failed; correct engineering without economic verdict")
    require(all(summary["rate_faults"] == 0 and summary["tick_faults"] == 0 for summary in structural_period_summaries.values()), "period structural integrity fault")
    require(all(summary["resolved"] == summary["triggers"] - summary["unresolved"] for summary in structural_period_summaries.values()), "structural resolved/unresolved accounting mismatch")

    period_opportunities: dict[str, list[Opportunity]] = {}
    period_summaries: dict[str, dict[str, Any]] = {}
    all_opportunities: list[Opportunity] = []
    for period, start, end in PERIODS:
        rows, summary = run_period(bars, period, start, end, spec)
        require(summary == structural_period_summaries[period], f"structural/economic observer summary mismatch in {period}")
        period_opportunities[period] = rows
        period_summaries[period] = summary
        all_opportunities.extend(rows)

    direction_books = aggregate_economics(period_opportunities, period_summaries)
    gates, passing = evaluate_gates(direction_books, period_summaries)
    selected_direction = passing[0] if passing else None
    verdict = (
        f"PASS_US500_SHOCK_RESPONSE_{selected_direction}_RETAIN_ONE_PROTOTYPE_INFORMATION_SEED"
        if selected_direction
        else "FAIL_US500_SHOCK_RESPONSE_NO_DIRECTION_NO_SEED"
    )
    write_opportunities(all_opportunities)
    result = {
        "schema": "zeta-next-us500-shock-response-environment-correction-result-v1",
        "created_at_local": datetime.now().astimezone().date().isoformat(),
        "status": "ONE_VALID_FIXED_PROXY_AGGREGATION_COMPLETE",
        "unit": "us500-shock-response-environment-correction-105",
        "family": FAMILY,
        "frozen_inputs": {
            "declaration_path": relative(DECLARATION_PATH),
            "declaration_bytes": DECLARATION_PATH.stat().st_size,
            "declaration_sha256": sha256(DECLARATION_PATH),
            "acquisition_receipt_path": relative(ACQUISITION_RECEIPT_PATH),
            "acquisition_receipt_bytes": ACQUISITION_RECEIPT_PATH.stat().st_size,
            "acquisition_receipt_sha256": sha256(ACQUISITION_RECEIPT_PATH),
            "proxy_script_path": relative(script_path),
            "proxy_script_bytes": script_path.stat().st_size,
            "proxy_script_sha256": sha256(script_path),
            "bar_path": relative(BAR_PATH),
            "bar_bytes": BAR_PATH.stat().st_size,
            "bar_sha256": sha256(BAR_PATH),
            "symbol_spec_path": relative(SPEC_PATH),
            "symbol_spec_bytes": SPEC_PATH.stat().st_size,
            "symbol_spec_sha256": sha256(SPEC_PATH),
            "structural_anchor_path": relative(STRUCTURAL_ANCHOR_PATH),
            "structural_anchor_bytes": STRUCTURAL_ANCHOR_PATH.stat().st_size,
            "structural_anchor_sha256": sha256(STRUCTURAL_ANCHOR_PATH),
        },
        "bar_integrity": bar_integrity,
        "symbol_spec": spec,
        "structural_integrity": structural_integrity,
        "premetric_period_observer_summaries": structural_period_summaries,
        "period_observer_summaries": period_summaries,
        "direction_books": direction_books,
        "selection_gates": gates,
        "passing_directions_in_selection_order": passing,
        "selected_direction": selected_direction,
        "verdict": verdict,
        "interpretation": (
            "Retain exactly one information seed for a later separately declared standalone additive prototype; this proxy does not itself open Optimization or MT5."
            if selected_direction
            else "Neither fixed continuation nor reversion book passed the complete frequency and double-spread economic gate; retain no shock-response seed and do not rescue adjacent variants."
        ),
        "raw_opportunity_artifact": {
            "path": relative(OPPORTUNITY_PATH),
            "bytes": OPPORTUNITY_PATH.stat().st_size,
            "sha256": sha256(OPPORTUNITY_PATH),
            "rows": len(all_opportunities),
        },
        "execution": {
            "successful_fixed_proxy_aggregations": 1,
            "metric_reruns": 0,
            "elapsed_seconds": time.perf_counter() - started,
            "mql_copies": 0,
            "compiles": 0,
            "tester_paths": 0,
            "orders": 0,
            "positions": 0,
        },
        "broker_or_account_state_queried": False,
        "program_6_opened": False,
        "optimization_surface": "UNTOUCHED_BY_UNIT_105",
        "live_surface": "UNTOUCHED",
    }
    temp_path = RESULT_PATH.with_suffix(RESULT_PATH.suffix + ".tmp")
    temp_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp_path, RESULT_PATH)
    print(json.dumps({"verdict": verdict, "selected_direction": selected_direction, "elapsed_seconds": result["execution"]["elapsed_seconds"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
