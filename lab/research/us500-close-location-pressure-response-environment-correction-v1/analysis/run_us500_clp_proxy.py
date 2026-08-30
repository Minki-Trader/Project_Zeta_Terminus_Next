from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


FAMILY = "us500-close-location-pressure-response-environment-correction-v1"
ROOT = Path(__file__).resolve().parents[4]
FAMILY_ROOT = ROOT / "lab" / "research" / FAMILY
RAW_ROOT = ROOT / "lab" / "artifacts" / "raw" / FAMILY
INPUT_ROOT = RAW_ROOT / "input"
OUTPUT_ROOT = RAW_ROOT / "output"

DECLARATION_PATH = FAMILY_ROOT / "evidence" / "US500_CLP_ENVIRONMENT_CORRECTION_DECLARATION_V1.json"
RECEIPT_PATH = FAMILY_ROOT / "evidence" / "US500_CLP_ENVIRONMENT_CORRECTION_ACQUISITION_RECEIPT_V1.json"
BAR_PATH = INPUT_ROOT / "US500_M15_BARS_20241201_20260731.csv"
SPEC_PATH = INPUT_ROOT / "US500_SYMBOL_SPEC_V1.json"
ANCHOR_PATH = INPUT_ROOT / "UNIT036_P1_SIGNAL_STRUCTURE.csv"
RAW_RESULT_PATH = OUTPUT_ROOT / "US500_CLP_ENVIRONMENT_CORRECTION_RAW_RESULT_V1.json"
RAW_OPPORTUNITY_PATH = OUTPUT_ROOT / "US500_CLP_ENVIRONMENT_CORRECTION_OPPORTUNITIES_V1.csv"

M15_SECONDS = 900
HORIZON_BARS = 4
CLOSE_LOCATION_THRESHOLD = 0.75
BODY_FRACTION_THRESHOLD = 0.50
VOLUME = 0.01
PERIODS = (
    {
        "id": "P1_DISCOVERY_2025",
        "start": "2025-01-01T00:00:00Z",
        "end": "2026-01-01T00:00:00Z",
        "last_trigger_epoch": 1767110400,
        "minimum_rate": 3.0,
        "minimum_resolved": 500,
    },
    {
        "id": "P2_CONFIRM_2026_JAN_MAY",
        "start": "2026-01-01T00:00:00Z",
        "end": "2026-06-01T00:00:00Z",
        "last_trigger_epoch": 1779984000,
        "minimum_rate": 3.0,
        "minimum_resolved": 200,
    },
    {
        "id": "P3_LATEST_2026_JUN_JUL",
        "start": "2026-06-01T00:00:00Z",
        "end": "2026-08-01T00:00:00Z",
        "last_trigger_epoch": 1785427200,
        "minimum_rate": 3.0,
        "minimum_resolved": 80,
    },
)
P1_EXPECTED = {
    "eligible_days": 257,
    "eligible_evaluations": 13755,
    "triggers": 3088,
    "resolved": 3088,
    "unresolved": 0,
}


@dataclass(frozen=True)
class Bar:
    epoch: int
    server_time: str
    open: float
    high: float
    low: float
    close: float
    spread_points: int


@dataclass(frozen=True)
class Signal:
    period: str
    opportunity_id: int
    completed_index: int
    entry_index: int
    exit_index: int
    market_bars_held: int
    close_location: float
    body_fraction: float
    continuation_direction: int


@dataclass(frozen=True)
class Opportunity:
    period: str
    opportunity_id: int
    completed_bar_time: str
    entry_time: str
    exit_time: str
    market_bars_held: int
    bar_open: float
    bar_high: float
    bar_low: float
    bar_close: float
    close_location: float
    body_fraction: float
    continuation_direction: str
    reversion_direction: str
    entry_bid: float
    entry_ask: float
    entry_spread: float
    exit_bid: float
    exit_ask: float
    exit_spread: float
    continuation_observed_usd: float
    continuation_double_spread_usd: float
    reversion_observed_usd: float
    reversion_double_spread_usd: float


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_epoch(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def parse_server_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y.%m.%d %H:%M:%S")


def floor_m15_text(value: str) -> str:
    parsed = parse_server_time(value)
    floored = parsed.replace(minute=(parsed.minute // 15) * 15, second=0)
    return floored.strftime("%Y.%m.%d %H:%M:%S")


def direction_text(direction: int) -> str:
    return "BUY" if direction > 0 else "SELL"


def verify_frozen_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    paths = (DECLARATION_PATH, RECEIPT_PATH, BAR_PATH, SPEC_PATH, ANCHOR_PATH, Path(__file__).resolve())
    for path in paths:
        require(path.is_file(), f"required frozen input missing: {path}")
    declaration = load_json(DECLARATION_PATH)
    receipt = load_json(RECEIPT_PATH)
    pins = receipt["frozen_inputs"]
    expected = {
        DECLARATION_PATH: pins["declaration_sha256"],
        Path(__file__).resolve(): pins["proxy_script_sha256"],
        BAR_PATH: pins["bar_sha256"],
        SPEC_PATH: pins["spec_sha256"],
        ANCHOR_PATH: pins["structural_anchor_sha256"],
    }
    faults = []
    for path, expected_hash in expected.items():
        actual_hash = sha256(path)
        if actual_hash != expected_hash:
            faults.append(f"{path}: expected {expected_hash}, got {actual_hash}")
    require(not faults, "frozen input hash fault: " + "; ".join(faults))
    require(
        declaration.get("unit") == "us500-close-location-pressure-response-environment-correction-121",
        "unexpected declaration unit",
    )
    return declaration, receipt


def read_bars() -> tuple[list[Bar], dict[str, Any]]:
    expected = (
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
    bars: list[Bar] = []
    previous_epoch: int | None = None
    with BAR_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        require(tuple(reader.fieldnames or ()) == expected, "bar columns differ")
        for row_number, row in enumerate(reader, start=2):
            epoch = int(row["time_epoch"])
            require(previous_epoch is None or epoch > previous_epoch, f"bar epochs not increasing at row {row_number}")
            previous_epoch = epoch
            ohlc = tuple(float(row[name]) for name in ("open", "high", "low", "close"))
            require(all(math.isfinite(value) and value > 0.0 for value in ohlc), f"invalid OHLC at row {row_number}")
            spread = int(row["spread"])
            require(spread >= 0, f"negative spread at row {row_number}")
            expected_time = datetime.utcfromtimestamp(epoch).strftime("%Y.%m.%d %H:%M:%S")
            require(row["time_server"] == expected_time, f"epoch/time mismatch at row {row_number}")
            bars.append(
                Bar(
                    epoch=epoch,
                    server_time=row["time_server"],
                    open=ohlc[0],
                    high=ohlc[1],
                    low=ohlc[2],
                    close=ohlc[3],
                    spread_points=spread,
                )
            )
    require(len(bars) > 3, "insufficient M15 bars")
    return bars, {
        "rows": len(bars),
        "first_time": bars[0].server_time,
        "last_time": bars[-1].server_time,
        "strictly_increasing": True,
        "finite_positive_ohlc": True,
        "nonnegative_spread": True,
    }


def read_anchor() -> list[dict[str, str]]:
    expected = (
        "observer_id",
        "run_code",
        "opportunity_id",
        "completed_bar_time",
        "entry_time",
        "exit_time",
        "bar_open",
        "bar_high",
        "bar_low",
        "bar_close",
        "close_location",
        "body_fraction",
        "continuation_direction",
        "reversion_direction",
        "market_bars_held",
    )
    with ANCHOR_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        require(tuple(reader.fieldnames or ()) == expected, "Unit 036 structural-anchor columns differ")
        rows = list(reader)
    require(len(rows) == 3088, "Unit 036 structural-anchor row count differs")
    return rows


def build_signals(bars: list[Bar], period: dict[str, Any]) -> tuple[list[Signal], dict[str, Any]]:
    start_epoch = parse_epoch(period["start"])
    end_epoch = parse_epoch(period["end"])
    indices = [index for index, bar in enumerate(bars) if start_epoch <= bar.epoch < end_epoch]
    require(bool(indices), f"no bars for {period['id']}")
    eligible_dates: set[str] = set()
    eligible_evaluations = 0
    triggers = 0
    active: dict[str, Any] | None = None
    signals: list[Signal] = []
    rate_faults = 0

    for index in indices:
        current = bars[index]
        if active is not None:
            active["market_bars_held"] += 1
            if active["market_bars_held"] >= HORIZON_BARS:
                signals.append(
                    Signal(
                        period=period["id"],
                        opportunity_id=len(signals) + 1,
                        completed_index=int(active["completed_index"]),
                        entry_index=int(active["entry_index"]),
                        exit_index=index,
                        market_bars_held=int(active["market_bars_held"]),
                        close_location=float(active["close_location"]),
                        body_fraction=float(active["body_fraction"]),
                        continuation_direction=int(active["continuation_direction"]),
                    )
                )
                active = None

        if active is not None or current.epoch > int(period["last_trigger_epoch"]):
            continue
        if index < 2:
            continue
        completed = bars[index - 1]
        predecessor = bars[index - 2]
        if current.epoch - completed.epoch != M15_SECONDS or completed.epoch - predecessor.epoch != M15_SECONDS:
            continue
        bar_range = completed.high - completed.low
        valid_ohlc = (
            all(math.isfinite(value) for value in (completed.open, completed.high, completed.low, completed.close))
            and completed.open > 0.0
            and completed.close > 0.0
            and bar_range > 0.0
            and completed.low <= completed.open <= completed.high
            and completed.low <= completed.close <= completed.high
        )
        if not valid_ohlc:
            rate_faults += 1
            continue
        eligible_evaluations += 1
        eligible_dates.add(current.server_time[:10])
        close_location = (2.0 * completed.close - completed.high - completed.low) / bar_range
        body_fraction = (completed.close - completed.open) / bar_range
        if not math.isfinite(close_location) or not math.isfinite(body_fraction):
            rate_faults += 1
            continue
        if abs(close_location) < CLOSE_LOCATION_THRESHOLD or abs(body_fraction) < BODY_FRACTION_THRESHOLD:
            continue
        if close_location > 0.0 and body_fraction > 0.0:
            direction = 1
        elif close_location < 0.0 and body_fraction < 0.0:
            direction = -1
        else:
            continue
        triggers += 1
        active = {
            "completed_index": index - 1,
            "entry_index": index,
            "market_bars_held": 0,
            "close_location": close_location,
            "body_fraction": body_fraction,
            "continuation_direction": direction,
        }

    summary = {
        "period": period["id"],
        "first_processed_bar": bars[indices[0]].server_time,
        "last_processed_bar": bars[indices[-1]].server_time,
        "eligible_days": len(eligible_dates),
        "eligible_evaluations": eligible_evaluations,
        "triggers": triggers,
        "resolved": len(signals),
        "unresolved": 1 if active is not None else 0,
        "rate_faults": rate_faults,
    }
    return signals, summary


def compare_p1(signals: list[Signal], bars: list[Bar], anchor: list[dict[str, str]]) -> dict[str, Any]:
    count_equal = len(signals) == len(anchor)
    exact_first_tick_timestamp_matches = 0
    m15_coordinate_matches = 0
    exact_ohlc_direction_horizon_matches = 0
    max_close_location_difference = 0.0
    max_body_fraction_difference = 0.0
    first_mismatch: dict[str, Any] | None = None
    for index, (signal, expected) in enumerate(zip(signals, anchor), start=1):
        completed = bars[signal.completed_index]
        entry = bars[signal.entry_index]
        exit_bar = bars[signal.exit_index]
        expected_continuation = expected["continuation_direction"]
        expected_reversion = expected["reversion_direction"]
        exact_timestamp = entry.server_time == expected["entry_time"] and exit_bar.server_time == expected["exit_time"]
        if exact_timestamp:
            exact_first_tick_timestamp_matches += 1
        coordinate = (
            completed.server_time == expected["completed_bar_time"]
            and entry.server_time == floor_m15_text(expected["entry_time"])
            and exit_bar.server_time == floor_m15_text(expected["exit_time"])
        )
        if coordinate:
            m15_coordinate_matches += 1
        exact_structure = (
            int(expected["opportunity_id"]) == signal.opportunity_id
            and int(expected["run_code"]) == 1
            and signal.market_bars_held == int(expected["market_bars_held"])
            and direction_text(signal.continuation_direction) == expected_continuation
            and direction_text(-signal.continuation_direction) == expected_reversion
            and completed.open == float(expected["bar_open"])
            and completed.high == float(expected["bar_high"])
            and completed.low == float(expected["bar_low"])
            and completed.close == float(expected["bar_close"])
        )
        if exact_structure:
            exact_ohlc_direction_horizon_matches += 1
        close_difference = abs(signal.close_location - float(expected["close_location"]))
        body_difference = abs(signal.body_fraction - float(expected["body_fraction"]))
        max_close_location_difference = max(max_close_location_difference, close_difference)
        max_body_fraction_difference = max(max_body_fraction_difference, body_difference)
        if first_mismatch is None and (not coordinate or not exact_structure):
            first_mismatch = {
                "row": index,
                "coordinate_match": coordinate,
                "structure_match": exact_structure,
                "observed_completed_entry_exit": [completed.server_time, entry.server_time, exit_bar.server_time],
                "expected_completed_entry_exit": [
                    expected["completed_bar_time"],
                    expected["entry_time"],
                    expected["exit_time"],
                ],
            }
    return {
        "anchor_rows": len(anchor),
        "proxy_rows": len(signals),
        "count_equal": count_equal,
        "exact_first_tick_entry_exit_timestamp_matches_descriptive": exact_first_tick_timestamp_matches,
        "m15_coordinate_matches": m15_coordinate_matches,
        "all_m15_coordinates_equal": count_equal and m15_coordinate_matches == len(anchor),
        "exact_ohlc_direction_horizon_matches": exact_ohlc_direction_horizon_matches,
        "all_exact_ohlc_direction_horizon_equal": count_equal and exact_ohlc_direction_horizon_matches == len(anchor),
        "maximum_close_location_abs_difference": max_close_location_difference,
        "maximum_body_fraction_abs_difference": max_body_fraction_difference,
        "first_mismatch": first_mismatch,
    }


def direction_profit(direction: int, open_price: float, close_price: float, spec: dict[str, Any]) -> float:
    tick_size = float(spec["trade_tick_size"])
    tick_value = float(spec["trade_tick_value"])
    require(tick_size > 0.0 and tick_value > 0.0, "invalid tick economics")
    signed_distance = close_price - open_price if direction > 0 else open_price - close_price
    return signed_distance / tick_size * tick_value * VOLUME


def price_signals(signals: list[Signal], bars: list[Bar], spec: dict[str, Any]) -> list[Opportunity]:
    point = float(spec["point"])
    require(point > 0.0, "invalid point")
    opportunities: list[Opportunity] = []
    for signal in signals:
        completed = bars[signal.completed_index]
        entry = bars[signal.entry_index]
        exit_bar = bars[signal.exit_index]
        entry_spread = entry.spread_points * point
        exit_spread = exit_bar.spread_points * point
        entry_bid = entry.open
        entry_ask = entry.open + entry_spread
        exit_bid = exit_bar.open
        exit_ask = exit_bar.open + exit_spread

        def profits(direction: int) -> tuple[float, float]:
            if direction > 0:
                observed = direction_profit(direction, entry_ask, exit_bid, spec)
                doubled = direction_profit(direction, entry_ask + entry_spread, exit_bid - exit_spread, spec)
            else:
                observed = direction_profit(direction, entry_bid, exit_ask, spec)
                doubled = direction_profit(direction, entry_bid - entry_spread, exit_ask + exit_spread, spec)
            return observed, doubled

        continuation_observed, continuation_doubled = profits(signal.continuation_direction)
        reversion_observed, reversion_doubled = profits(-signal.continuation_direction)
        opportunities.append(
            Opportunity(
                period=signal.period,
                opportunity_id=signal.opportunity_id,
                completed_bar_time=completed.server_time,
                entry_time=entry.server_time,
                exit_time=exit_bar.server_time,
                market_bars_held=signal.market_bars_held,
                bar_open=completed.open,
                bar_high=completed.high,
                bar_low=completed.low,
                bar_close=completed.close,
                close_location=signal.close_location,
                body_fraction=signal.body_fraction,
                continuation_direction=direction_text(signal.continuation_direction),
                reversion_direction=direction_text(-signal.continuation_direction),
                entry_bid=entry_bid,
                entry_ask=entry_ask,
                entry_spread=entry_spread,
                exit_bid=exit_bid,
                exit_ask=exit_ask,
                exit_spread=exit_spread,
                continuation_observed_usd=continuation_observed,
                continuation_double_spread_usd=continuation_doubled,
                reversion_observed_usd=reversion_observed,
                reversion_double_spread_usd=reversion_doubled,
            )
        )
    return opportunities


def metrics(values: list[float]) -> dict[str, Any]:
    wins = [value for value in values if value > 0.0]
    losses = [value for value in values if value < 0.0]
    gross_profit = sum(wins)
    gross_loss = -sum(losses)
    running = 0.0
    peak = 0.0
    maximum_closed_drawdown = 0.0
    for value in values:
        running += value
        peak = max(peak, running)
        maximum_closed_drawdown = max(maximum_closed_drawdown, peak - running)
    net = sum(values)
    return {
        "opportunities": len(values),
        "net_usd": net,
        "wins": len(wins),
        "losses": len(losses),
        "zeros": len(values) - len(wins) - len(losses),
        "gross_profit_usd": gross_profit,
        "gross_loss_usd": gross_loss,
        "profit_factor": gross_profit / gross_loss if gross_loss > 0.0 else None,
        "maximum_closed_drawdown_usd": maximum_closed_drawdown,
        "net_over_maximum_closed_drawdown": net / maximum_closed_drawdown if maximum_closed_drawdown > 0.0 else None,
    }


def direction_metrics(opportunities: list[Opportunity], direction: str) -> dict[str, Any]:
    observed_field = f"{direction.lower()}_observed_usd"
    doubled_field = f"{direction.lower()}_double_spread_usd"
    return {
        "observed": metrics([float(getattr(row, observed_field)) for row in opportunities]),
        "double_spread": metrics([float(getattr(row, doubled_field)) for row in opportunities]),
    }


def frequency_gate(summary: dict[str, Any], period: dict[str, Any]) -> dict[str, Any]:
    rate = summary["resolved"] / summary["eligible_days"] if summary["eligible_days"] else 0.0
    checks = {
        f"opportunities_per_eligible_day_at_least_{period['minimum_rate']}": rate >= float(period["minimum_rate"]),
        f"resolved_at_least_{period['minimum_resolved']}": summary["resolved"] >= int(period["minimum_resolved"]),
    }
    return {"opportunities_per_eligible_day": rate, "checks": checks, "passed": all(checks.values())}


def p1_direction_gate(book: dict[str, Any]) -> dict[str, Any]:
    stressed = book["double_spread"]
    checks = {
        "double_spread_net_positive": stressed["net_usd"] > 0.0,
        "double_spread_profit_factor_at_least_1_10": stressed["profit_factor"] is not None and stressed["profit_factor"] >= 1.10,
        "double_spread_net_to_drawdown_at_least_1_50": stressed["net_over_maximum_closed_drawdown"] is not None
        and stressed["net_over_maximum_closed_drawdown"] >= 1.50,
    }
    return {"checks": checks, "passed": all(checks.values())}


def confirmation_gate(book: dict[str, Any], profit_factor: float, net_to_dd: float) -> dict[str, Any]:
    stressed = book["double_spread"]
    checks = {
        "double_spread_net_positive": stressed["net_usd"] > 0.0,
        f"double_spread_profit_factor_at_least_{profit_factor}": stressed["profit_factor"] is not None
        and stressed["profit_factor"] >= profit_factor,
        f"double_spread_net_to_drawdown_at_least_{net_to_dd}": stressed["net_over_maximum_closed_drawdown"] is not None
        and stressed["net_over_maximum_closed_drawdown"] >= net_to_dd,
    }
    return {"checks": checks, "passed": all(checks.values())}


def select_p1_direction(books: dict[str, Any], gates: dict[str, Any]) -> str | None:
    passing = [name for name in ("CONTINUATION", "REVERSION") if gates[name]["passed"]]
    if not passing:
        return None
    passing.sort(
        key=lambda name: (
            -books[name]["double_spread"]["net_usd"],
            -(books[name]["double_spread"]["profit_factor"] or float("-inf")),
            -(books[name]["double_spread"]["net_over_maximum_closed_drawdown"] or float("-inf")),
            0 if name == "CONTINUATION" else 1,
        )
    )
    return passing[0]


def pooled_gate(period_results: dict[str, Any], selected: str) -> dict[str, Any]:
    opened = [item for item in PERIODS if item["id"] in period_results]
    stressed_values: list[float] = []
    path_nets: list[float] = []
    path_drawdowns: list[float] = []
    field = f"{selected.lower()}_double_spread_usd"
    for period in opened:
        result = period_results[period["id"]]
        opportunities = result["_opportunities"]
        values = [float(getattr(row, field)) for row in opportunities]
        stressed_values.extend(values)
        path_nets.append(result["books"][selected]["double_spread"]["net_usd"])
        path_drawdowns.append(result["books"][selected]["double_spread"]["maximum_closed_drawdown_usd"])
    pooled = metrics(stressed_values)
    positive_sum = sum(value for value in path_nets if value > 0.0)
    concentration = max((value / positive_sum for value in path_nets if value > 0.0), default=None)
    summed_path_net_to_summed_path_dd = sum(path_nets) / sum(path_drawdowns) if sum(path_drawdowns) > 0.0 else None
    checks = {
        "double_spread_net_positive": pooled["net_usd"] > 0.0,
        "double_spread_profit_factor_at_least_1_10": pooled["profit_factor"] is not None and pooled["profit_factor"] >= 1.10,
        "summed_path_net_to_summed_path_drawdown_at_least_1_50": summed_path_net_to_summed_path_dd is not None
        and summed_path_net_to_summed_path_dd >= 1.50,
        "maximum_positive_path_contribution_at_most_0_70": concentration is not None and concentration <= 0.70,
    }
    return {
        "metrics": pooled,
        "path_nets_usd": path_nets,
        "path_maximum_closed_drawdowns_usd": path_drawdowns,
        "summed_path_net_to_summed_path_drawdown": summed_path_net_to_summed_path_dd,
        "maximum_positive_path_contribution_share": concentration,
        "checks": checks,
        "passed": len(opened) == 3 and all(checks.values()),
    }


def write_opportunities(rows: list[Opportunity]) -> None:
    require(not RAW_OPPORTUNITY_PATH.exists(), "raw opportunity output already exists")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    temp_path = RAW_OPPORTUNITY_PATH.with_suffix(RAW_OPPORTUNITY_PATH.suffix + ".tmp")
    fieldnames = list(Opportunity.__dataclass_fields__.keys())
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
    os.replace(temp_path, RAW_OPPORTUNITY_PATH)


def main() -> int:
    started = time.perf_counter()
    declaration, receipt = verify_frozen_inputs()
    require(not RAW_RESULT_PATH.exists() and not RAW_OPPORTUNITY_PATH.exists(), "formal raw output already exists")
    bars, bar_integrity = read_bars()
    spec = load_json(SPEC_PATH)
    anchor = read_anchor()

    p1_signals, p1_summary = build_signals(bars, PERIODS[0])
    structural = compare_p1(p1_signals, bars, anchor)
    expected_faults = {key: {"expected": expected, "observed": p1_summary[key]} for key, expected in P1_EXPECTED.items() if p1_summary[key] != expected}
    structural_pass = (
        not expected_faults
        and p1_summary["rate_faults"] == 0
        and structural["all_m15_coordinates_equal"]
        and structural["all_exact_ohlc_direction_horizon_equal"]
        and structural["maximum_close_location_abs_difference"] <= 5.1e-10
        and structural["maximum_body_fraction_abs_difference"] <= 5.1e-10
    )
    require(structural_pass, f"P1 structural integrity failed before economics: {json.dumps({'expected_faults': expected_faults, 'structural': structural}, sort_keys=True)}")

    period_results: dict[str, Any] = {}
    all_opportunities: list[Opportunity] = []
    selected_direction: str | None = None
    stop_stage = "P1"

    p1_opportunities = price_signals(p1_signals, bars, spec)
    p1_books = {name: direction_metrics(p1_opportunities, name) for name in ("CONTINUATION", "REVERSION")}
    p1_frequency = frequency_gate(p1_summary, PERIODS[0])
    p1_gates = {name: p1_direction_gate(p1_books[name]) for name in ("CONTINUATION", "REVERSION")}
    if p1_frequency["passed"]:
        selected_direction = select_p1_direction(p1_books, p1_gates)
    period_results[PERIODS[0]["id"]] = {
        "summary": p1_summary,
        "frequency_gate": p1_frequency,
        "books": p1_books,
        "direction_gates": p1_gates,
        "selected_direction": selected_direction,
        "_opportunities": p1_opportunities,
    }
    all_opportunities.extend(p1_opportunities)

    if selected_direction is not None:
        stop_stage = "P2"
        p2_signals, p2_summary = build_signals(bars, PERIODS[1])
        require(p2_summary["rate_faults"] == 0 and p2_summary["unresolved"] == 0, "P2 structural integrity fault")
        p2_opportunities = price_signals(p2_signals, bars, spec)
        p2_books = {selected_direction: direction_metrics(p2_opportunities, selected_direction)}
        p2_frequency = frequency_gate(p2_summary, PERIODS[1])
        p2_confirmation = confirmation_gate(p2_books[selected_direction], 1.10, 1.50)
        period_results[PERIODS[1]["id"]] = {
            "summary": p2_summary,
            "frequency_gate": p2_frequency,
            "books": p2_books,
            "selected_direction_confirmation": p2_confirmation,
            "_opportunities": p2_opportunities,
        }
        all_opportunities.extend(p2_opportunities)

        if p2_frequency["passed"] and p2_confirmation["passed"]:
            stop_stage = "P3"
            p3_signals, p3_summary = build_signals(bars, PERIODS[2])
            require(p3_summary["rate_faults"] == 0 and p3_summary["unresolved"] == 0, "P3 structural integrity fault")
            p3_opportunities = price_signals(p3_signals, bars, spec)
            p3_books = {selected_direction: direction_metrics(p3_opportunities, selected_direction)}
            p3_frequency = frequency_gate(p3_summary, PERIODS[2])
            p3_confirmation = confirmation_gate(p3_books[selected_direction], 1.05, 1.00)
            period_results[PERIODS[2]["id"]] = {
                "summary": p3_summary,
                "frequency_gate": p3_frequency,
                "books": p3_books,
                "selected_direction_confirmation": p3_confirmation,
                "_opportunities": p3_opportunities,
            }
            all_opportunities.extend(p3_opportunities)

    pooled = pooled_gate(period_results, selected_direction) if selected_direction and len(period_results) == 3 else None
    if selected_direction is None:
        verdict = "FAIL_US500_CLOSE_LOCATION_PRESSURE_P1_NO_DIRECTION_NO_SEED"
        classification = "VALID_P1_ECONOMIC_NONCONFIRMATION"
    elif len(period_results) == 1:
        verdict = "FAIL_US500_CLOSE_LOCATION_PRESSURE_P1_NO_DIRECTION_NO_SEED"
        classification = "VALID_P1_ECONOMIC_NONCONFIRMATION"
    elif len(period_results) == 2:
        verdict = "FAIL_US500_CLOSE_LOCATION_PRESSURE_P2_CONFIRMATION_NO_SEED"
        classification = "VALID_P2_ECONOMIC_NONCONFIRMATION"
    else:
        p3 = period_results[PERIODS[2]["id"]]
        if p3["frequency_gate"]["passed"] and p3["selected_direction_confirmation"]["passed"] and pooled and pooled["passed"]:
            verdict = "PASS_US500_CLOSE_LOCATION_PRESSURE_RETAIN_ONE_ADDITIVE_PROTOTYPE_CLUE"
            classification = "VALID_COMPLETE_ECONOMIC_CONFIRMATION_RETAIN_ONE_SEED"
        else:
            verdict = "FAIL_US500_CLOSE_LOCATION_PRESSURE_LATEST_OR_POOLED_CONFIRMATION_NO_SEED"
            classification = "VALID_COMPLETE_ECONOMIC_NONCONFIRMATION"

    serializable_periods: dict[str, Any] = {}
    for name, result in period_results.items():
        serializable_periods[name] = {key: value for key, value in result.items() if key != "_opportunities"}
    write_opportunities(all_opportunities)
    elapsed = time.perf_counter() - started
    raw_result = {
        "schema": "zeta-next-us500-close-location-pressure-response-environment-correction-raw-result-v1",
        "created_at_local": "2026-08-30",
        "status": "ONE_VALID_STRUCTURAL_FIRST_SEQUENTIAL_PROXY_AGGREGATION_COMPLETE",
        "unit": declaration["unit"],
        "family": FAMILY,
        "frozen_inputs": receipt["frozen_inputs"],
        "bar_integrity": bar_integrity,
        "p1_structural_integrity": {
            "expected_summary_faults": expected_faults,
            "comparison": structural,
            "passed": structural_pass,
        },
        "opened_periods": list(serializable_periods.keys()),
        "unopened_periods": [period["id"] for period in PERIODS if period["id"] not in serializable_periods],
        "serial_stop_stage": stop_stage,
        "periods": serializable_periods,
        "selected_direction": selected_direction,
        "pooled_selected_direction": pooled,
        "verdict": verdict,
        "economic_classification": classification,
        "retained_seed": selected_direction if classification == "VALID_COMPLETE_ECONOMIC_CONFIRMATION_RETAIN_ONE_SEED" else None,
        "mt5_clue": selected_direction if classification == "VALID_COMPLETE_ECONOMIC_CONFIRMATION_RETAIN_ONE_SEED" else None,
        "fixed_development_candidate_changed": False,
        "execution": {
            "successful_fixed_economic_aggregations": 1,
            "economic_metric_reruns": 0,
            "grid_or_retune_points": 0,
            "tester_paths": 0,
            "elapsed_seconds": elapsed,
        },
        "raw_opportunities": {
            "path": str(RAW_OPPORTUNITY_PATH.relative_to(ROOT)).replace("\\", "/"),
            "rows": len(all_opportunities),
            "bytes": RAW_OPPORTUNITY_PATH.stat().st_size,
            "sha256": sha256(RAW_OPPORTUNITY_PATH),
        },
        "broker_or_account_state_queried": False,
        "master_terminal_touched": False,
        "live_surface": "UNTOUCHED",
    }
    temp_path = RAW_RESULT_PATH.with_suffix(RAW_RESULT_PATH.suffix + ".tmp")
    temp_path.write_text(json.dumps(raw_result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp_path, RAW_RESULT_PATH)
    print(
        json.dumps(
            {
                "status": raw_result["status"],
                "opened_periods": raw_result["opened_periods"],
                "unopened_periods": raw_result["unopened_periods"],
                "selected_direction": selected_direction,
                "verdict": verdict,
                "raw_result_path": str(RAW_RESULT_PATH.relative_to(ROOT)).replace("\\", "/"),
                "raw_result_bytes": RAW_RESULT_PATH.stat().st_size,
                "raw_result_sha256": sha256(RAW_RESULT_PATH),
                "opportunities_rows": len(all_opportunities),
                "elapsed_seconds": elapsed,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
