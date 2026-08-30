from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FAMILY = "us30-compression-break-response-environment-correction-v1"
ROOT = Path(__file__).resolve().parents[4]
FAMILY_ROOT = ROOT / "lab" / "research" / FAMILY
DECLARATION_PATH = FAMILY_ROOT / "evidence" / "US30_CBR_ENVIRONMENT_CORRECTION_DECLARATION_V1.json"
RECEIPT_PATH = FAMILY_ROOT / "evidence" / "US30_CBR_ENVIRONMENT_CORRECTION_ACQUISITION_RECEIPT_V1.json"
BAR_PATH = ROOT / "lab" / "artifacts" / "raw" / FAMILY / "input" / "US30_M5_BARS_20220725_20260731.csv"
FIRST_TICK_PATH = ROOT / "lab" / "artifacts" / "raw" / FAMILY / "input" / "US30_M5_FIRST_TICKS_20220725_20260731.csv"
SPEC_PATH = ROOT / "lab" / "artifacts" / "raw" / FAMILY / "input" / "US30_SYMBOL_SPEC_V1.json"
ANCHOR_PATH = ROOT / "lab" / "artifacts" / "raw" / FAMILY / "input" / "UNIT029_P1_SIGNAL_STRUCTURE.csv"
OUTPUT_ROOT = ROOT / "lab" / "artifacts" / "raw" / FAMILY / "output"
RAW_RESULT_PATH = OUTPUT_ROOT / "US30_CBR_ENVIRONMENT_CORRECTION_RAW_RESULT_V1.json"
OPPORTUNITY_PATH = OUTPUT_ROOT / "US30_CBR_ENVIRONMENT_CORRECTION_OPPORTUNITIES_V1.csv"

RECENT_RETURNS = 12
REFERENCE_RETURNS = 36
REQUIRED_BARS = RECENT_RETURNS + REFERENCE_RETURNS + 1
RANGE_BARS = 12
HORIZON_BARS = 12
BAR_SECONDS = 300
COMPRESSION_THRESHOLD = 0.65
VOLUME = 0.01
STRUCTURAL_FLOAT_TOLERANCE = 5.1e-10
BAR_OPEN_TOLERANCE = 0.0051
MAX_RATE_CONSISTENT_FIRST_TICK_SPREAD = 321.8

PERIODS = (
    {"id": "P1_2022H2_2023", "from": "2022-08-01T00:00:00Z", "to_exclusive": "2024-01-01T00:00:00Z"},
    {"id": "P2_2024", "from": "2024-01-01T00:00:00Z", "to_exclusive": "2025-01-01T00:00:00Z"},
    {"id": "P3_2025", "from": "2025-01-01T00:00:00Z", "to_exclusive": "2026-01-01T00:00:00Z"},
    {"id": "P4_2026_COMPLETE_MONTHS", "from": "2026-01-01T00:00:00Z", "to_exclusive": "2026-08-01T00:00:00Z"},
)


@dataclass(frozen=True)
class Bar:
    epoch: int
    server_time: str
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    spread_points: int
    real_volume: int


@dataclass(frozen=True)
class FirstTick:
    bar_epoch: int
    bar_time: str
    tick_epoch: int
    tick_time: str
    time_msc: int
    bid: float
    ask: float
    spread: float
    flags: int


@dataclass(frozen=True)
class Signal:
    period: str
    entry_index: int
    exit_index: int
    market_bars_held: int
    recent_volatility: float
    reference_volatility: float
    compression_ratio: float
    range_high: float
    range_low: float
    break_mid: float
    break_direction: int


@dataclass(frozen=True)
class Opportunity:
    period: str
    opportunity_id: int
    trigger_bar_time: str
    resolve_bar_time: str
    elapsed_seconds: int
    market_bars_held: int
    recent_volatility: float
    reference_volatility: float
    compression_ratio: float
    range_high: float
    range_low: float
    break_mid: float
    break_direction: int
    entry_bid: float
    entry_ask: float
    entry_spread: float
    entry_price_source: str
    exit_bid: float
    exit_ask: float
    exit_spread: float
    exit_price_source: str
    continuation_direction: int
    reversion_direction: int
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


def parse_epoch(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def parse_server_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y.%m.%d %H:%M:%S")


def floor_m5_text(value: str) -> str:
    parsed = parse_server_time(value)
    floored = parsed.replace(minute=(parsed.minute // 5) * 5, second=0)
    return floored.strftime("%Y.%m.%d %H:%M:%S")


def read_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def read_and_verify_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    declaration = read_json(DECLARATION_PATH)
    receipt = read_json(RECEIPT_PATH)
    require(declaration.get("unit") == "us30-compression-break-response-environment-correction-122", "declaration unit differs")
    require(declaration.get("outcomes_consumed") is False, "declaration says outcomes were already consumed")
    expected_proxy = declaration["implementation"]["proxy_script"]
    require(expected_proxy["sha256"] == sha256(Path(__file__).resolve()), "proxy script differs from declaration")
    require(receipt.get("status") == "VALID_TWO_OUTPUT_BATCH_NON_ECONOMIC_ACQUISITION", "acquisition receipt is not valid")
    require(receipt.get("declaration_sha256") == sha256(DECLARATION_PATH), "receipt declaration pin differs")
    outputs = receipt["outputs"]
    expected_paths = {
        "bars": BAR_PATH,
        "first_ticks": FIRST_TICK_PATH,
        "symbol_spec": SPEC_PATH,
        "structural_anchor": ANCHOR_PATH,
    }
    for key, path in expected_paths.items():
        item = outputs[key]
        require(item["path"] == str(path.relative_to(ROOT)).replace("\\", "/"), f"receipt path differs for {key}")
        require(path.is_file(), f"acquisition output missing for {key}")
        require(path.stat().st_size == int(item["bytes"]), f"acquisition bytes differ for {key}")
        require(sha256(path) == item["sha256"], f"acquisition hash differs for {key}")
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
    with BAR_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        require(tuple(reader.fieldnames or ()) == expected, "bar columns differ")
        previous_epoch: int | None = None
        for row_number, row in enumerate(reader, start=2):
            epoch = int(row["time_epoch"])
            require(previous_epoch is None or epoch > previous_epoch, f"bar epochs not increasing at row {row_number}")
            expected_time = datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y.%m.%d %H:%M:%S")
            require(row["time_server"] == expected_time, f"epoch/time mismatch at row {row_number}")
            ohlc = tuple(float(row[name]) for name in ("open", "high", "low", "close"))
            require(all(math.isfinite(value) and value > 0.0 for value in ohlc), f"invalid OHLC at row {row_number}")
            require(ohlc[1] >= max(ohlc[0], ohlc[2], ohlc[3]) and ohlc[2] <= min(ohlc[0], ohlc[1], ohlc[3]), f"invalid bar geometry at row {row_number}")
            bars.append(
                Bar(
                    epoch=epoch,
                    server_time=row["time_server"],
                    open=ohlc[0],
                    high=ohlc[1],
                    low=ohlc[2],
                    close=ohlc[3],
                    tick_volume=int(row["tick_volume"]),
                    spread_points=int(row["spread"]),
                    real_volume=int(row["real_volume"]),
                )
            )
            require(bars[-1].tick_volume >= 0 and bars[-1].spread_points >= 0 and bars[-1].real_volume >= 0, f"negative bar field at row {row_number}")
            previous_epoch = epoch
    require(len(bars) > REQUIRED_BARS, "insufficient M5 bars")
    return bars, {
        "rows": len(bars),
        "first_time": bars[0].server_time,
        "last_time": bars[-1].server_time,
        "strictly_increasing": True,
        "finite_positive_ohlc_and_valid_geometry": True,
        "nonnegative_volume_and_spread": True,
    }


def read_first_ticks(bars: list[Bar]) -> tuple[dict[int, FirstTick], dict[str, Any]]:
    expected = (
        "bar_epoch",
        "bar_time",
        "tick_epoch",
        "tick_time",
        "time_msc",
        "bid",
        "ask",
        "spread",
        "flags",
    )
    ticks: dict[int, FirstTick] = {}
    with FIRST_TICK_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        require(tuple(reader.fieldnames or ()) == expected, "first-tick columns differ")
        for row_number, row in enumerate(reader, start=2):
            bar_epoch = int(row["bar_epoch"])
            tick_epoch = int(row["tick_epoch"])
            time_msc = int(row["time_msc"])
            bid = float(row["bid"])
            ask = float(row["ask"])
            spread = float(row["spread"])
            require(bar_epoch not in ticks, f"duplicate first-tick bar epoch at row {row_number}")
            require(tick_epoch - tick_epoch % BAR_SECONDS == bar_epoch, f"first tick outside M5 bar at row {row_number}")
            require(time_msc // 1000 == tick_epoch, f"first-tick epoch/millisecond mismatch at row {row_number}")
            expected_bar_time = datetime.fromtimestamp(bar_epoch, timezone.utc).strftime("%Y.%m.%d %H:%M:%S")
            expected_tick_time = datetime.fromtimestamp(tick_epoch, timezone.utc).strftime("%Y.%m.%d %H:%M:%S")
            require(row["bar_time"] == expected_bar_time, f"first-tick bar time differs at row {row_number}")
            require(row["tick_time"] == expected_tick_time, f"first-tick time differs at row {row_number}")
            require(math.isfinite(bid) and math.isfinite(ask) and bid > 0.0 and ask >= bid, f"invalid first-tick bid/ask at row {row_number}")
            require(math.isfinite(spread) and abs(spread - (ask - bid)) <= 1e-10, f"first-tick spread differs at row {row_number}")
            ticks[bar_epoch] = FirstTick(
                bar_epoch=bar_epoch,
                bar_time=row["bar_time"],
                tick_epoch=tick_epoch,
                tick_time=row["tick_time"],
                time_msc=time_msc,
                bid=bid,
                ask=ask,
                spread=spread,
                flags=int(row["flags"]),
            )
    expected_epoch_set = {bar.epoch for bar in bars}
    require(set(ticks).issubset(expected_epoch_set), "first-tick carrier contains an epoch outside the acquired bar surface")
    expected_available_epochs = [bar.epoch for bar in bars if bar.epoch in ticks]
    require(list(ticks) == expected_available_epochs, "first-tick carrier order differs from the acquired bar surface")
    bar_by_epoch = {bar.epoch: bar for bar in bars}
    rate_consistent = {
        epoch: tick for epoch, tick in ticks.items() if abs(tick.bid - bar_by_epoch[epoch].open) <= BAR_OPEN_TOLERANCE
    }
    raw_missing_epochs = [bar.epoch for bar in bars if bar.epoch not in ticks]
    usable_missing_epochs = [bar.epoch for bar in bars if bar.epoch not in rate_consistent]
    rejected_epochs = [epoch for epoch in ticks if epoch not in rate_consistent]
    maximum_spread = max(tick.spread for tick in rate_consistent.values())
    require(abs(maximum_spread - MAX_RATE_CONSISTENT_FIRST_TICK_SPREAD) <= 1e-10, "maximum rate-consistent first-tick spread differs")
    return rate_consistent, {
        "raw_rows": len(ticks),
        "rate_consistent_rows": len(rate_consistent),
        "rate_inconsistent_rows_rejected": len(rejected_epochs),
        "first_bar_time": ticks[expected_available_epochs[0]].bar_time,
        "last_bar_time": ticks[expected_available_epochs[-1]].bar_time,
        "bar_surface_rows_without_raw_first_tick": len(raw_missing_epochs),
        "bar_surface_rows_without_rate_consistent_first_tick": len(usable_missing_epochs),
        "bar_open_tolerance": BAR_OPEN_TOLERANCE,
        "maximum_rate_consistent_first_tick_spread": maximum_spread,
        "coverage_sufficiency_checked_by_fixed_economic_envelope": True,
        "finite_positive_bid_ask_and_exact_spread": True,
    }


def build_hybrid_ticks(
    bars: list[Bar],
    exact_ticks: dict[int, FirstTick],
    point: float,
    fallback_spread_override: float | None = None,
) -> tuple[dict[int, FirstTick], set[int]]:
    hybrid = dict(exact_ticks)
    fallback_epochs: set[int] = set()
    for bar in bars:
        if bar.epoch in exact_ticks:
            continue
        fallback_epochs.add(bar.epoch)
        spread = bar.spread_points * point if fallback_spread_override is None else fallback_spread_override
        hybrid[bar.epoch] = FirstTick(
            bar_epoch=bar.epoch,
            bar_time=bar.server_time,
            tick_epoch=bar.epoch,
            tick_time=bar.server_time,
            time_msc=bar.epoch * 1000,
            bid=bar.open,
            ask=bar.open + spread,
            spread=spread,
            flags=0,
        )
    return hybrid, fallback_epochs


def read_anchor() -> list[dict[str, str]]:
    expected = (
        "observer_id",
        "run_code",
        "opportunity_id",
        "trigger_bar_time",
        "trigger_tick_time",
        "resolve_time",
        "elapsed_seconds",
        "market_bars_held",
        "recent_volatility",
        "reference_volatility",
        "compression_ratio",
        "range_high",
        "range_low",
        "break_mid",
        "break_direction",
        "continuation_direction",
        "reversion_direction",
    )
    with ANCHOR_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        require(tuple(reader.fieldnames or ()) == expected, "anchor columns differ")
        rows = list(reader)
    require(len(rows) == 291, f"anchor row count differs: {len(rows)}")
    return rows


def sample_standard_deviation(values: list[float]) -> float:
    require(len(values) >= 2, "standard deviation needs at least two values")
    mean = 0.0
    for value in values:
        require(math.isfinite(value), "nonfinite return")
        mean += value
    mean /= float(len(values))
    squared_sum = 0.0
    for value in values:
        difference = value - mean
        squared_sum += difference * difference
    result = math.sqrt(squared_sum / float(len(values) - 1))
    require(math.isfinite(result), "nonfinite standard deviation")
    return result


def build_signals(bars: list[Bar], first_ticks: dict[int, FirstTick], period: dict[str, str]) -> tuple[list[Signal], dict[str, Any]]:
    start_epoch = parse_epoch(period["from"])
    end_epoch = parse_epoch(period["to_exclusive"])
    indices = [index for index, bar in enumerate(bars) if start_epoch <= bar.epoch < end_epoch]
    require(bool(indices), f"no bars for {period['id']}")
    signals: list[Signal] = []
    active: dict[str, Any] | None = None
    eligible_dates: set[str] = set()
    eligible_compression_evaluations = 0
    rate_faults = 0
    triggers = 0

    for index in indices:
        if active is not None:
            active["market_bars_held"] += 1
            if active["market_bars_held"] >= HORIZON_BARS:
                signals.append(
                    Signal(
                        period=period["id"],
                        entry_index=int(active["entry_index"]),
                        exit_index=index,
                        market_bars_held=int(active["market_bars_held"]),
                        recent_volatility=float(active["recent_volatility"]),
                        reference_volatility=float(active["reference_volatility"]),
                        compression_ratio=float(active["compression_ratio"]),
                        range_high=float(active["range_high"]),
                        range_low=float(active["range_low"]),
                        break_mid=float(active["break_mid"]),
                        break_direction=int(active["break_direction"]),
                    )
                )
                active = None
            else:
                continue

        if index < REQUIRED_BARS:
            continue
        window = bars[index - REQUIRED_BARS : index + 1]
        if len(window) != REQUIRED_BARS + 1 or any(window[offset + 1].epoch - window[offset].epoch != BAR_SECONDS for offset in range(REQUIRED_BARS)):
            continue
        completed = [bars[index - 1 - offset] for offset in range(REQUIRED_BARS)]
        try:
            recent_values = [math.log(completed[offset].close / completed[offset + 1].close) for offset in range(RECENT_RETURNS)]
            reference_values = [
                math.log(completed[RECENT_RETURNS + offset].close / completed[RECENT_RETURNS + offset + 1].close)
                for offset in range(REFERENCE_RETURNS)
            ]
            recent_volatility = sample_standard_deviation(recent_values)
            reference_volatility = sample_standard_deviation(reference_values)
        except (RuntimeError, ValueError, ZeroDivisionError):
            rate_faults += 1
            continue
        if reference_volatility <= 0.0:
            continue
        compression_ratio = recent_volatility / reference_volatility
        if not math.isfinite(compression_ratio):
            rate_faults += 1
            continue
        eligible_dates.add(bars[index].server_time[:10])
        if compression_ratio > COMPRESSION_THRESHOLD:
            continue
        eligible_compression_evaluations += 1
        recent_range = completed[:RANGE_BARS]
        range_high = max(bar.high for bar in recent_range)
        range_low = min(bar.low for bar in recent_range)
        require(bars[index].epoch in first_ticks, f"first tick unavailable at required signal-mid evaluation {period['id']} {bars[index].server_time}")
        current_tick = first_ticks[bars[index].epoch]
        current_mid = 0.5 * (current_tick.bid + current_tick.ask)
        break_direction = 1 if current_mid > range_high else (-1 if current_mid < range_low else 0)
        if break_direction == 0:
            continue
        triggers += 1
        active = {
            "entry_index": index,
            "market_bars_held": 0,
            "recent_volatility": recent_volatility,
            "reference_volatility": reference_volatility,
            "compression_ratio": compression_ratio,
            "range_high": range_high,
            "range_low": range_low,
            "break_mid": current_mid,
            "break_direction": break_direction,
        }

    return signals, {
        "period": period["id"],
        "evaluations": len(indices),
        "eligible_continuous_days": len(eligible_dates),
        "eligible_compression_evaluations": eligible_compression_evaluations,
        "triggers": triggers,
        "resolved": len(signals),
        "unresolved": int(active is not None),
        "rate_faults": rate_faults,
        "first_processed_bar": bars[indices[0]].server_time,
        "last_processed_bar": bars[indices[-1]].server_time,
    }


def compare_p1(signals: list[Signal], bars: list[Bar], first_ticks: dict[int, FirstTick], anchor: list[dict[str, str]], summary: dict[str, Any]) -> dict[str, Any]:
    require(len(signals) == len(anchor) == 291, f"P1 structural row count differs: proxy={len(signals)} parent={len(anchor)}")
    expected_summary = {
        "evaluations": 100263,
        "eligible_continuous_days": 366,
        "eligible_compression_evaluations": 12444,
        "triggers": 291,
        "resolved": 291,
        "unresolved": 0,
        "rate_faults": 0,
    }
    for key, expected in expected_summary.items():
        require(summary[key] == expected, f"P1 summary differs for {key}: {summary[key]} != {expected}")

    exact_first_tick_timestamp_matches = 0
    exact_coordinates_directions_horizons = 0
    maximum_recent_difference = 0.0
    maximum_reference_difference = 0.0
    maximum_ratio_difference = 0.0
    maximum_range_high_difference = 0.0
    maximum_range_low_difference = 0.0
    maximum_break_mid_difference = 0.0

    for row_number, (signal, expected) in enumerate(zip(signals, anchor), start=1):
        entry = bars[signal.entry_index]
        exit_bar = bars[signal.exit_index]
        require(entry.epoch in first_ticks, f"P1 entry first tick unavailable at {entry.server_time}")
        require(exit_bar.epoch in first_ticks, f"P1 exit first tick unavailable at {exit_bar.server_time}")
        entry_tick = first_ticks[entry.epoch]
        exit_tick = first_ticks[exit_bar.epoch]
        require(expected["observer_id"] == "ZETA-NEXT-US30-COMPRESSION-BREAK-RESPONSE-V1", f"parent observer differs at row {row_number}")
        require(int(expected["run_code"]) == 1 and int(expected["opportunity_id"]) == row_number, f"parent identity differs at row {row_number}")
        exact_timestamp = entry_tick.tick_time == expected["trigger_tick_time"] and exit_tick.tick_time == expected["resolve_time"]
        if exact_timestamp:
            exact_first_tick_timestamp_matches += 1
        coordinate_match = (
            entry.server_time == expected["trigger_bar_time"]
            and entry.server_time == floor_m5_text(expected["trigger_tick_time"])
            and exit_bar.server_time == floor_m5_text(expected["resolve_time"])
            and signal.market_bars_held == int(expected["market_bars_held"])
            and signal.break_direction == int(expected["break_direction"])
            and signal.break_direction == int(expected["continuation_direction"])
            and -signal.break_direction == int(expected["reversion_direction"])
        )
        if coordinate_match:
            exact_coordinates_directions_horizons += 1
        maximum_recent_difference = max(maximum_recent_difference, abs(signal.recent_volatility - float(expected["recent_volatility"])))
        maximum_reference_difference = max(maximum_reference_difference, abs(signal.reference_volatility - float(expected["reference_volatility"])))
        maximum_ratio_difference = max(maximum_ratio_difference, abs(signal.compression_ratio - float(expected["compression_ratio"])))
        maximum_range_high_difference = max(maximum_range_high_difference, abs(signal.range_high - float(expected["range_high"])))
        maximum_range_low_difference = max(maximum_range_low_difference, abs(signal.range_low - float(expected["range_low"])))
        maximum_break_mid_difference = max(maximum_break_mid_difference, abs(signal.break_mid - float(expected["break_mid"])))
        require(coordinate_match, f"P1 coordinate/direction/horizon differs at row {row_number}")

    require(exact_coordinates_directions_horizons == 291, "P1 coordinate parity is incomplete")
    require(maximum_recent_difference <= STRUCTURAL_FLOAT_TOLERANCE, "P1 recent-volatility parity failed")
    require(maximum_reference_difference <= STRUCTURAL_FLOAT_TOLERANCE, "P1 reference-volatility parity failed")
    require(maximum_ratio_difference <= STRUCTURAL_FLOAT_TOLERANCE, "P1 compression-ratio parity failed")
    require(maximum_range_high_difference <= STRUCTURAL_FLOAT_TOLERANCE, "P1 range-high parity failed")
    require(maximum_range_low_difference <= STRUCTURAL_FLOAT_TOLERANCE, "P1 range-low parity failed")
    require(maximum_break_mid_difference <= 0.0051, "P1 break-mid parity failed")
    return {
        "parent_rows": len(anchor),
        "proxy_rows": len(signals),
        "exact_coordinates_directions_horizons": exact_coordinates_directions_horizons,
        "exact_first_tick_entry_exit_timestamp_matches_descriptive": exact_first_tick_timestamp_matches,
        "maximum_recent_volatility_abs_difference": maximum_recent_difference,
        "maximum_reference_volatility_abs_difference": maximum_reference_difference,
        "maximum_compression_ratio_abs_difference": maximum_ratio_difference,
        "maximum_range_high_abs_difference": maximum_range_high_difference,
        "maximum_range_low_abs_difference": maximum_range_low_difference,
        "maximum_break_mid_abs_difference": maximum_break_mid_difference,
        "break_mid_tolerance": 0.0051,
        "structural_gate_passed": True,
    }


def direction_profit(direction: int, entry_bid: float, entry_ask: float, exit_bid: float, exit_ask: float, entry_spread: float, exit_spread: float, tick_size: float, tick_value: float, doubled: bool) -> float:
    if direction > 0:
        open_price = entry_ask + (entry_spread if doubled else 0.0)
        close_price = exit_bid - (exit_spread if doubled else 0.0)
        signed_distance = close_price - open_price
    else:
        open_price = entry_bid - (entry_spread if doubled else 0.0)
        close_price = exit_ask + (exit_spread if doubled else 0.0)
        signed_distance = open_price - close_price
    return signed_distance / tick_size * tick_value * VOLUME


def price_signals(
    signals: list[Signal],
    bars: list[Bar],
    first_ticks: dict[int, FirstTick],
    exact_epochs: set[int],
    spec: dict[str, Any],
) -> list[Opportunity]:
    tick_size = float(spec["trade_tick_size"])
    tick_value = float(spec["trade_tick_value"])
    require(tick_size > 0.0 and tick_value > 0.0, "symbol pricing fields are invalid")
    output: list[Opportunity] = []
    for opportunity_id, signal in enumerate(signals, start=1):
        entry = bars[signal.entry_index]
        exit_bar = bars[signal.exit_index]
        require(entry.epoch in first_ticks, f"entry first tick unavailable for {signal.period} at {entry.server_time}")
        require(exit_bar.epoch in first_ticks, f"exit first tick unavailable for {signal.period} at {exit_bar.server_time}")
        entry_tick = first_ticks[entry.epoch]
        exit_tick = first_ticks[exit_bar.epoch]
        entry_spread = entry_tick.spread
        exit_spread = exit_tick.spread
        entry_bid = entry_tick.bid
        entry_ask = entry_tick.ask
        exit_bid = exit_tick.bid
        exit_ask = exit_tick.ask
        continuation_direction = signal.break_direction
        reversion_direction = -signal.break_direction
        output.append(
            Opportunity(
                period=signal.period,
                opportunity_id=opportunity_id,
                trigger_bar_time=entry.server_time,
                resolve_bar_time=exit_bar.server_time,
                elapsed_seconds=exit_bar.epoch - entry.epoch,
                market_bars_held=signal.market_bars_held,
                recent_volatility=signal.recent_volatility,
                reference_volatility=signal.reference_volatility,
                compression_ratio=signal.compression_ratio,
                range_high=signal.range_high,
                range_low=signal.range_low,
                break_mid=signal.break_mid,
                break_direction=signal.break_direction,
                entry_bid=entry_bid,
                entry_ask=entry_ask,
                entry_spread=entry_spread,
                entry_price_source="EXACT_RATE_CONSISTENT_FIRST_TICK" if entry.epoch in exact_epochs else "M5_BAR_OPEN_SPREAD_FALLBACK",
                exit_bid=exit_bid,
                exit_ask=exit_ask,
                exit_spread=exit_spread,
                exit_price_source="EXACT_RATE_CONSISTENT_FIRST_TICK" if exit_bar.epoch in exact_epochs else "M5_BAR_OPEN_SPREAD_FALLBACK",
                continuation_direction=continuation_direction,
                reversion_direction=reversion_direction,
                continuation_observed_usd=direction_profit(continuation_direction, entry_bid, entry_ask, exit_bid, exit_ask, entry_spread, exit_spread, tick_size, tick_value, False),
                continuation_double_spread_usd=direction_profit(continuation_direction, entry_bid, entry_ask, exit_bid, exit_ask, entry_spread, exit_spread, tick_size, tick_value, True),
                reversion_observed_usd=direction_profit(reversion_direction, entry_bid, entry_ask, exit_bid, exit_ask, entry_spread, exit_spread, tick_size, tick_value, False),
                reversion_double_spread_usd=direction_profit(reversion_direction, entry_bid, entry_ask, exit_bid, exit_ask, entry_spread, exit_spread, tick_size, tick_value, True),
            )
        )
    return output


def aggregate(values: list[float]) -> dict[str, Any]:
    wins = [value for value in values if value > 0.0]
    losses = [value for value in values if value < 0.0]
    cumulative = 0.0
    peak = 0.0
    maximum_drawdown = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        maximum_drawdown = max(maximum_drawdown, peak - cumulative)
    gross_profit = sum(wins)
    gross_loss = -sum(losses)
    net = sum(values)
    profit_factor = gross_profit / gross_loss if gross_loss > 0.0 else None
    net_to_drawdown = net / maximum_drawdown if maximum_drawdown > 0.0 else None
    return {
        "opportunities": len(values),
        "net_usd": net,
        "wins": len(wins),
        "losses": len(losses),
        "zeros": len(values) - len(wins) - len(losses),
        "gross_profit_usd": gross_profit,
        "gross_loss_usd": gross_loss,
        "profit_factor": profit_factor,
        "maximum_closed_drawdown_usd": maximum_drawdown,
        "net_to_drawdown": net_to_drawdown,
    }


def evaluate_book(period_opportunities: dict[str, list[Opportunity]], prefix: str) -> dict[str, Any]:
    observed_field = f"{prefix}_observed_usd"
    stressed_field = f"{prefix}_double_spread_usd"
    period_metrics: dict[str, Any] = {}
    pooled: list[Opportunity] = []
    for period in PERIODS:
        opportunities = period_opportunities[period["id"]]
        pooled.extend(opportunities)
        period_metrics[period["id"]] = {
            "observed": aggregate([float(getattr(item, observed_field)) for item in opportunities]),
            "double_spread": aggregate([float(getattr(item, stressed_field)) for item in opportunities]),
        }
    observed = aggregate([float(getattr(item, observed_field)) for item in pooled])
    stressed = aggregate([float(getattr(item, stressed_field)) for item in pooled])
    stressed_period_nets = [period_metrics[period["id"]]["double_spread"]["net_usd"] for period in PERIODS]
    positive_period_nets = [value for value in stressed_period_nets if value > 0.0]
    concentration = max(positive_period_nets) / sum(positive_period_nets) if positive_period_nets else None
    gates = {
        "positive_pooled_double_spread_net": stressed["net_usd"] > 0.0,
        "pooled_double_spread_profit_factor_at_least_1_10": stressed["profit_factor"] is not None and stressed["profit_factor"] >= 1.10,
        "at_least_three_positive_double_spread_paths": len(positive_period_nets) >= 3,
        "pooled_double_spread_net_to_drawdown_at_least_1_50": stressed["net_to_drawdown"] is not None and stressed["net_to_drawdown"] >= 1.50,
        "maximum_positive_path_contribution_at_most_0_70": concentration is not None and concentration <= 0.70,
    }
    return {
        "observed": observed,
        "double_spread": stressed,
        "periods": period_metrics,
        "double_spread_period_nets_usd": stressed_period_nets,
        "positive_double_spread_periods": len(positive_period_nets),
        "maximum_positive_path_contribution": concentration,
        "gates": gates,
        "gates_passed": sum(gates.values()),
        "gates_total": len(gates),
        "passed": all(gates.values()),
    }


def evaluate_scenario(
    period_opportunities: dict[str, list[Opportunity]],
    period_summaries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    pooled_eligible_days = sum(period_summaries[period["id"]]["eligible_continuous_days"] for period in PERIODS)
    pooled_resolved = sum(len(period_opportunities[period["id"]]) for period in PERIODS)
    period_rates = {
        period["id"]: (
            len(period_opportunities[period["id"]]) / period_summaries[period["id"]]["eligible_continuous_days"]
            if period_summaries[period["id"]]["eligible_continuous_days"] > 0
            else 0.0
        )
        for period in PERIODS
    }
    pooled_rate = pooled_resolved / pooled_eligible_days if pooled_eligible_days > 0 else 0.0
    frequency_gates = {
        "pooled_at_least_0_25_per_eligible_day": pooled_rate >= 0.25,
        "at_least_three_paths_at_least_0_15_per_eligible_day": sum(rate >= 0.15 for rate in period_rates.values()) >= 3,
        "pooled_at_least_200": pooled_resolved >= 200,
    }
    frequency_passed = all(frequency_gates.values())
    continuation = evaluate_book(period_opportunities, "continuation")
    reversion = evaluate_book(period_opportunities, "reversion")
    passing = [("CONTINUATION", continuation), ("REVERSION", reversion)] if frequency_passed else []
    passing = [item for item in passing if item[1]["passed"]]
    passing.sort(
        key=lambda item: (
            -item[1]["double_spread"]["net_usd"],
            -(item[1]["double_spread"]["profit_factor"] or -math.inf),
            -item[1]["positive_double_spread_periods"],
            item[0],
        )
    )
    selected_direction = passing[0][0] if passing else None
    return {
        "frequency": {
            "pooled_resolved": pooled_resolved,
            "pooled_eligible_continuous_days": pooled_eligible_days,
            "pooled_opportunities_per_eligible_day": pooled_rate,
            "period_opportunities_per_eligible_day": period_rates,
            "gates": frequency_gates,
            "passed": frequency_passed,
        },
        "books": {"CONTINUATION": continuation, "REVERSION": reversion},
        "selected_direction": selected_direction,
    }


def write_opportunities(rows: list[Opportunity]) -> None:
    temp_path = OPPORTUNITY_PATH.with_suffix(OPPORTUNITY_PATH.suffix + ".tmp")
    fieldnames = list(asdict(rows[0]).keys()) if rows else list(Opportunity.__dataclass_fields__.keys())
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
    os.replace(temp_path, OPPORTUNITY_PATH)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


def main() -> int:
    require(not RAW_RESULT_PATH.exists() and not OPPORTUNITY_PATH.exists(), "formal economic output already exists")
    started = time.perf_counter()
    declaration, receipt = read_and_verify_contract()
    bars, bar_integrity = read_bars()
    exact_ticks, first_tick_integrity = read_first_ticks(bars)
    anchor = read_anchor()
    spec = read_json(SPEC_PATH)
    point = float(spec["point"])
    require(point > 0.0, "symbol point is invalid")
    recorded_ticks, fallback_epochs = build_hybrid_ticks(bars, exact_ticks, point)
    zero_spread_ticks, zero_fallback_epochs = build_hybrid_ticks(bars, exact_ticks, point, 0.0)
    maximum_spread_ticks, maximum_fallback_epochs = build_hybrid_ticks(
        bars, exact_ticks, point, MAX_RATE_CONSISTENT_FIRST_TICK_SPREAD
    )
    require(fallback_epochs == zero_fallback_epochs == maximum_fallback_epochs, "fallback epoch sets differ")
    require(len(exact_ticks) == 282761 and len(fallback_epochs) == 1642, "rate-consistent carrier counts differ")

    p1_signals, p1_summary = build_signals(bars, recorded_ticks, PERIODS[0])
    structural = compare_p1(p1_signals, bars, recorded_ticks, anchor, p1_summary)
    period_signals: dict[str, list[Signal]] = {PERIODS[0]["id"]: p1_signals}
    period_summaries: dict[str, dict[str, Any]] = {PERIODS[0]["id"]: p1_summary}
    for period in PERIODS[1:]:
        signals, summary = build_signals(bars, recorded_ticks, period)
        period_signals[period["id"]] = signals
        period_summaries[period["id"]] = summary
    require(all(summary["rate_faults"] == 0 for summary in period_summaries.values()), "one or more periods has a rate fault")

    exact_epochs = set(exact_ticks)
    recorded_period_opportunities = {
        period["id"]: price_signals(period_signals[period["id"]], bars, recorded_ticks, exact_epochs, spec)
        for period in PERIODS
    }
    zero_period_opportunities = {
        period["id"]: price_signals(period_signals[period["id"]], bars, zero_spread_ticks, exact_epochs, spec)
        for period in PERIODS
    }
    maximum_period_opportunities = {
        period["id"]: price_signals(period_signals[period["id"]], bars, maximum_spread_ticks, exact_epochs, spec)
        for period in PERIODS
    }
    omitted_period_opportunities = {
        period["id"]: [
            item
            for item in recorded_period_opportunities[period["id"]]
            if item.entry_price_source == "EXACT_RATE_CONSISTENT_FIRST_TICK"
            and item.exit_price_source == "EXACT_RATE_CONSISTENT_FIRST_TICK"
        ]
        for period in PERIODS
    }
    all_opportunities = [item for period in PERIODS for item in recorded_period_opportunities[period["id"]]]
    fallback_priced_opportunities = [
        item
        for item in all_opportunities
        if item.entry_price_source != "EXACT_RATE_CONSISTENT_FIRST_TICK"
        or item.exit_price_source != "EXACT_RATE_CONSISTENT_FIRST_TICK"
    ]
    require(len(fallback_priced_opportunities) == 1, "fallback-priced opportunity count differs")
    fallback_item = fallback_priced_opportunities[0]
    require(
        fallback_item.period == "P1_2022H2_2023"
        and fallback_item.trigger_bar_time == "2022.09.29 06:40:00"
        and fallback_item.resolve_bar_time == "2022.09.29 07:40:00",
        "fallback-priced opportunity identity differs",
    )

    scenario_period_opportunities = {
        "RECORDED_SPREAD_FALLBACK": recorded_period_opportunities,
        "OMIT_UNAVAILABLE_FALLBACK_OPPORTUNITY": omitted_period_opportunities,
        "ZERO_SPREAD_FALLBACK_OPTIMISTIC": zero_period_opportunities,
        "MAX_OBSERVED_SPREAD_FALLBACK_ADVERSE": maximum_period_opportunities,
    }
    scenario_definitions = {
        "RECORDED_SPREAD_FALLBACK": "Price the one unavailable entry and exit with their M5 bar-open bid and recorded 2.10 USD spread.",
        "OMIT_UNAVAILABLE_FALLBACK_OPPORTUNITY": "Remove the one structurally anchored but unpriceable opportunity from frequency and economics.",
        "ZERO_SPREAD_FALLBACK_OPTIMISTIC": "Keep the opportunity but set both unavailable spreads to zero, an economic upper endpoint.",
        "MAX_OBSERVED_SPREAD_FALLBACK_ADVERSE": "Keep the opportunity and set both unavailable spreads to the fixed 321.80 USD maximum among all rate-consistent exact first ticks, an adverse endpoint.",
    }
    scenarios = {
        scenario_id: {
            "definition": scenario_definitions[scenario_id],
            **evaluate_scenario(opportunities, period_summaries),
        }
        for scenario_id, opportunities in scenario_period_opportunities.items()
    }
    scenario_directions = {scenario_id: item["selected_direction"] for scenario_id, item in scenarios.items()}
    selected_values = list(scenario_directions.values())
    if selected_values[0] is not None and all(value == selected_values[0] for value in selected_values):
        selected_direction = selected_values[0]
        classification = f"PASS_US30_COMPRESSION_BREAK_{selected_direction}_ROBUST_TO_COVERAGE_ENVELOPE_RETAIN_ONE_PROTOTYPE_QUESTION"
        research_verdict = "PASS"
    elif all(value is None for value in selected_values):
        selected_direction = None
        classification = "FAIL_US30_COMPRESSION_BREAK_NO_DIRECTION_IN_ANY_COVERAGE_SCENARIO_NO_SEED"
        research_verdict = "FAIL"
    else:
        selected_direction = None
        classification = "CORRECTION_REQUIRED_US30_COMPRESSION_BREAK_COVERAGE_SCENARIOS_DISAGREE_NO_RESEARCH_VERDICT"
        research_verdict = "CORRECTION_REQUIRED"
    canonical = scenarios["RECORDED_SPREAD_FALLBACK"]

    elapsed = time.perf_counter() - started
    result = {
        "schema": "zeta-next-us30-compression-break-environment-correction-raw-result-v1",
        "created_at_local": "2026-08-30",
        "status": "VALID_COMPLETE_FIXED_PROXY_ECONOMIC_COVERAGE_ENVELOPE",
        "unit": declaration["unit"],
        "family": FAMILY,
        "pins": {
            "declaration": {"bytes": DECLARATION_PATH.stat().st_size, "sha256": sha256(DECLARATION_PATH)},
            "acquisition_receipt": {"bytes": RECEIPT_PATH.stat().st_size, "sha256": sha256(RECEIPT_PATH)},
            "proxy_script": {"bytes": Path(__file__).stat().st_size, "sha256": sha256(Path(__file__).resolve())},
            "bars": receipt["outputs"]["bars"],
            "first_ticks": receipt["outputs"]["first_ticks"],
            "symbol_spec": receipt["outputs"]["symbol_spec"],
            "structural_anchor": receipt["outputs"]["structural_anchor"],
        },
        "bar_integrity": bar_integrity,
        "first_tick_integrity": first_tick_integrity,
        "p1_structural_parity": structural,
        "period_summaries": period_summaries,
        "pricing_coverage": {
            "exact_rate_consistent_bar_epochs": len(exact_epochs),
            "bar_proxy_fallback_epochs": len(fallback_epochs),
            "fallback_priced_opportunities": len(fallback_priced_opportunities),
            "fallback_opportunity": {
                "period": fallback_item.period,
                "trigger_bar_time": fallback_item.trigger_bar_time,
                "resolve_bar_time": fallback_item.resolve_bar_time,
                "entry_recorded_spread": fallback_item.entry_spread,
                "exit_recorded_spread": fallback_item.exit_spread,
            },
            "maximum_rate_consistent_first_tick_spread": MAX_RATE_CONSISTENT_FIRST_TICK_SPREAD,
        },
        "frequency": canonical["frequency"],
        "books": canonical["books"],
        "coverage_scenarios": scenarios,
        "decision": {
            "classification": classification,
            "research_verdict": research_verdict,
            "selected_direction": selected_direction,
            "scenario_selected_directions": scenario_directions,
            "retained_prototype_question": selected_direction if research_verdict == "PASS" else None,
            "optimization_candidate": None,
            "mt5_shortlist": None,
            "fixed_development_candidate": "unchanged",
        },
        "execution": {
            "formal_processes": 1,
            "complete_economic_aggregations": 1,
            "fixed_coverage_scenarios_inside_aggregation": len(scenarios),
            "economic_metric_reruns": 0,
            "grid_or_retune_points": 0,
            "elapsed_seconds": elapsed,
            "mql_set_compile_tester_or_mt5_paths": 0,
            "tests_or_validators": 0,
        },
        "surface": {
            "broker_account_position_order_or_deal_queries": 0,
            "master_terminal_touched": False,
            "live_surface": "UNTOUCHED",
            "optimization_surface": "UNTOUCHED",
        },
    }
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    write_opportunities(all_opportunities)
    result["raw_opportunities"] = {
        "path": str(OPPORTUNITY_PATH.relative_to(ROOT)).replace("\\", "/"),
        "rows": len(all_opportunities),
        "bytes": OPPORTUNITY_PATH.stat().st_size,
        "sha256": sha256(OPPORTUNITY_PATH),
    }
    write_json_atomic(RAW_RESULT_PATH, result)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
