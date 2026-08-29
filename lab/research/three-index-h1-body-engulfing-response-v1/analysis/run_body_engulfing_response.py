#!/usr/bin/env python3
"""Run the frozen three-index H1 body-engulfing response experiment.

This is a research aggregation, not a validator or a trading executable.  It
reads only the family-owned immutable snapshots, reconstructs the declared
signals, selects a direction on P1, and opens later-period economics only when
that P1 selection passes every frozen gate.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


HEADER = [
    "time_epoch",
    "time_server",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
]


@dataclass(frozen=True)
class Bar:
    epoch: int
    server_time: datetime
    server_text: str
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    spread: int
    real_volume: int


@dataclass(frozen=True)
class Observation:
    symbol: str
    period: str
    signal_epoch: int
    signal_time: datetime
    entry_epoch: int
    entry_time: datetime
    exit_epoch: int
    exit_time: datetime
    signal_direction: int
    prior_open: float
    prior_close: float
    signal_open: float
    signal_close: float
    entry_bid: float
    entry_spread_points: int
    exit_bid: float
    exit_spread_points: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--declaration", required=True)
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--raw-output", required=True)
    parser.add_argument("--durable-output", required=True)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def finite_number(text: str, label: str) -> float:
    value = float(text)
    require(math.isfinite(value), f"nonfinite {label}")
    return value


def exact_int(text: str, label: str) -> int:
    value = int(text)
    require(str(value) == text.strip(), f"noncanonical integer {label}: {text!r}")
    return value


def load_bars(path: Path, expected: dict[str, Any]) -> list[Bar]:
    require(path.stat().st_size == expected["bytes"], f"byte mismatch {path}")
    require(sha256_file(path) == expected["sha256"], f"hash mismatch {path}")
    bars: list[Bar] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames == HEADER, f"header mismatch {path}: {reader.fieldnames}")
        prior_epoch: int | None = None
        for line_number, row in enumerate(reader, start=2):
            epoch = exact_int(row["time_epoch"], f"{path.name}:{line_number}:epoch")
            server_text = row["time_server"].strip()
            server_time = datetime.strptime(server_text, "%Y.%m.%d %H:%M:%S")
            open_price = finite_number(row["open"], f"{path.name}:{line_number}:open")
            high = finite_number(row["high"], f"{path.name}:{line_number}:high")
            low = finite_number(row["low"], f"{path.name}:{line_number}:low")
            close = finite_number(row["close"], f"{path.name}:{line_number}:close")
            tick_volume = exact_int(row["tick_volume"], f"{path.name}:{line_number}:tick_volume")
            spread = exact_int(row["spread"], f"{path.name}:{line_number}:spread")
            real_volume = exact_int(row["real_volume"], f"{path.name}:{line_number}:real_volume")
            require(open_price > 0 and high > 0 and low > 0 and close > 0, f"nonpositive OHLC {path.name}:{line_number}")
            require(high >= max(open_price, close) and low <= min(open_price, close) and high >= low, f"invalid OHLC geometry {path.name}:{line_number}")
            require(tick_volume > 0 and spread >= 0 and real_volume >= 0, f"invalid volume/spread {path.name}:{line_number}")
            if prior_epoch is not None:
                require(epoch > prior_epoch, f"nonincreasing epoch {path.name}:{line_number}")
            prior_epoch = epoch
            bars.append(
                Bar(
                    epoch=epoch,
                    server_time=server_time,
                    server_text=server_text,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    tick_volume=tick_volume,
                    spread=spread,
                    real_volume=real_volume,
                )
            )
    require(len(bars) == expected["rows"], f"row count mismatch {path}: {len(bars)}")
    require(bars[0].server_text == expected["first_time"], f"first time mismatch {path}")
    require(bars[-1].server_text == expected["last_time"], f"last time mismatch {path}")
    return bars


def period_of(moment: datetime, periods: dict[str, dict[str, str]]) -> str | None:
    for period, boundary in periods.items():
        start = datetime.strptime(boundary["from_inclusive"], "%Y-%m-%d")
        end = datetime.strptime(boundary["to_exclusive"], "%Y-%m-%d")
        if start <= moment < end:
            return period
    return None


def is_body_engulf(prior: Bar, signal: Bar) -> tuple[bool, int]:
    prior_delta = prior.close - prior.open
    signal_delta = signal.close - signal.open
    if prior_delta == 0 or signal_delta == 0:
        return False, 0
    prior_direction = 1 if prior_delta > 0 else -1
    signal_direction = 1 if signal_delta > 0 else -1
    if prior_direction != -signal_direction:
        return False, 0
    prior_low = min(prior.open, prior.close)
    prior_high = max(prior.open, prior.close)
    signal_low = min(signal.open, signal.close)
    signal_high = max(signal.open, signal.close)
    contains = signal_low <= prior_low and signal_high >= prior_high
    strict = signal_low < prior_low or signal_high > prior_high
    return contains and strict, signal_direction


def reconstruct(
    symbol: str,
    bars: list[Bar],
    periods: dict[str, dict[str, str]],
) -> tuple[list[Observation], dict[str, Any]]:
    observations: list[Observation] = []
    normal_dates: dict[str, set[str]] = {period: set() for period in periods}
    boundary_excluded = {period: 0 for period in periods}
    busy_through_index = -1
    for index in range(1, len(bars) - 5):
        continuous = all(
            bars[j + 1].epoch - bars[j].epoch == 3600
            for j in range(index - 1, index + 5)
        )
        if not continuous:
            continue
        signal = bars[index]
        period = period_of(signal.server_time, periods)
        if period is None:
            continue
        normal_dates[period].add(signal.server_time.strftime("%Y-%m-%d"))
        exit_bar = bars[index + 5]
        if period_of(exit_bar.server_time, periods) != period:
            boundary_excluded[period] += 1
            continue
        triggered, signal_direction = is_body_engulf(bars[index - 1], signal)
        if not triggered or index <= busy_through_index:
            continue
        entry_bar = bars[index + 1]
        observations.append(
            Observation(
                symbol=symbol,
                period=period,
                signal_epoch=signal.epoch,
                signal_time=signal.server_time,
                entry_epoch=entry_bar.epoch,
                entry_time=entry_bar.server_time,
                exit_epoch=exit_bar.epoch,
                exit_time=exit_bar.server_time,
                signal_direction=signal_direction,
                prior_open=bars[index - 1].open,
                prior_close=bars[index - 1].close,
                signal_open=signal.open,
                signal_close=signal.close,
                entry_bid=entry_bar.open,
                entry_spread_points=entry_bar.spread,
                exit_bid=exit_bar.open,
                exit_spread_points=exit_bar.spread,
            )
        )
        busy_through_index = index + 5
    per_period: dict[str, Any] = {}
    for period in periods:
        selected = [item for item in observations if item.period == period]
        up = sum(item.signal_direction > 0 for item in selected)
        down = sum(item.signal_direction < 0 for item in selected)
        days = len(normal_dates[period])
        per_period[period] = {
            "signals": len(selected),
            "up": up,
            "down": down,
            "normal_days": days,
            "signals_per_day": len(selected) / days if days else None,
            "boundary_excluded": boundary_excluded[period],
        }
    return observations, per_period


def pnl(item: Observation, book: str, point: float, contract: float, volume: float) -> dict[str, float]:
    direction = item.signal_direction if book == "CONTINUATION" else -item.signal_direction
    entry_spread_price = item.entry_spread_points * point
    exit_spread_price = item.exit_spread_points * point
    entry_mid = item.entry_bid + 0.5 * entry_spread_price
    exit_mid = item.exit_bid + 0.5 * exit_spread_price
    gross = direction * (exit_mid - entry_mid) * contract * volume
    spread_pair = (entry_spread_price + exit_spread_price) * contract * volume
    return {
        "gross_usd": gross,
        "observed_usd": gross - 0.5 * spread_pair,
        "double_spread_usd": gross - spread_pair,
    }


def max_closed_drawdown(values: Iterable[float], initial: float = 100.0) -> tuple[float, float, float]:
    balance = initial
    peak = initial
    maximum_usd = 0.0
    maximum_pct = 0.0
    minimum_balance = initial
    for value in values:
        balance += value
        minimum_balance = min(minimum_balance, balance)
        peak = max(peak, balance)
        drawdown = peak - balance
        maximum_usd = max(maximum_usd, drawdown)
        if peak > 0:
            maximum_pct = max(maximum_pct, 100.0 * drawdown / peak)
    return maximum_usd, maximum_pct, minimum_balance


def metrics(
    observations: list[Observation],
    book: str,
    point: float,
    contract: float,
    volume: float,
) -> dict[str, Any]:
    ordered = sorted(observations, key=lambda item: (item.exit_epoch, item.symbol, item.signal_epoch))
    rows = [pnl(item, book, point, contract, volume) for item in ordered]
    stressed = [row["double_spread_usd"] for row in rows]
    gross_profit = sum(value for value in stressed if value > 1e-12)
    gross_loss = -sum(value for value in stressed if value < -1e-12)
    maximum_dd_usd, maximum_dd_pct, minimum_balance = max_closed_drawdown(stressed)
    net = sum(stressed)
    profit_factor = None if gross_loss == 0 else gross_profit / gross_loss
    net_to_dd = None if maximum_dd_usd == 0 else net / maximum_dd_usd
    return {
        "count": len(rows),
        "gross_net_usd": sum(row["gross_usd"] for row in rows),
        "observed_net_usd": sum(row["observed_usd"] for row in rows),
        "double_spread_net_usd": net,
        "double_spread_gross_profit_usd": gross_profit,
        "double_spread_gross_loss_usd": gross_loss,
        "double_spread_profit_factor": profit_factor,
        "double_spread_max_closed_drawdown_usd": maximum_dd_usd,
        "double_spread_max_closed_drawdown_pct": maximum_dd_pct,
        "double_spread_net_to_drawdown": net_to_dd,
        "minimum_closed_balance_usd": minimum_balance,
        "wins": sum(value > 1e-12 for value in stressed),
        "losses": sum(value < -1e-12 for value in stressed),
        "zeros": sum(abs(value) <= 1e-12 for value in stressed),
        "win_rate": sum(value > 1e-12 for value in stressed) / len(stressed) if stressed else None,
        "mean_double_spread_usd": statistics.fmean(stressed) if stressed else None,
        "median_double_spread_usd": statistics.median(stressed) if stressed else None,
    }


def passes_floor(value: float | None, floor: float) -> bool:
    return value is not None and value >= floor


def positive_share(nets: dict[str, float]) -> float | None:
    positives = [value for value in nets.values() if value > 0]
    if not positives:
        return None
    return max(positives) / sum(positives)


def main() -> int:
    args = parse_args()
    started = time.perf_counter()
    declaration_path = Path(args.declaration).resolve()
    input_root = Path(args.input_root).resolve()
    raw_output = Path(args.raw_output).resolve()
    durable_output = Path(args.durable_output).resolve()
    declaration = json.loads(declaration_path.read_text(encoding="utf-8"))
    require(declaration["outcomes_consumed"] is False, "declaration already marks outcomes consumed")
    require(declaration["status"] == "UNIT_102_DECLARATION_FROZEN_OUTCOMES_UNOPENED", "unexpected declaration status")
    own_path = Path(__file__).resolve()
    require(sha256_file(own_path) == declaration["implementation"]["script_sha256"], "script hash mismatch")

    pins = declaration["immutable_inputs"]["files"]
    pin_by_name = {item["name"]: item for item in pins}
    require(set(pin_by_name) == {path.name for path in input_root.iterdir() if path.is_file()}, "input filename set mismatch")
    for name, pin in pin_by_name.items():
        path = input_root / name
        require(path.stat().st_size == pin["bytes"], f"byte mismatch {name}")
        require(sha256_file(path) == pin["sha256"], f"hash mismatch {name}")

    point_specs = json.loads((input_root / "SYMBOL_POINT_SPECS_V1.json").read_text(encoding="utf-8"))
    trade_specs = json.loads((input_root / "SYMBOL_TRADE_SPECS_V1.json").read_text(encoding="utf-8"))
    for symbol in declaration["symbols"]:
        require(point_specs["symbols"][symbol]["point"] == 0.01, f"point mismatch {symbol}")
        require(point_specs["symbols"][symbol]["trade_tick_size"] == 0.01, f"tick size mismatch {symbol}")
        spec = trade_specs["symbols"][symbol]
        require(spec["trade_contract_size"] == 1.0, f"contract mismatch {symbol}")
        require(spec["trade_tick_value"] == 0.01, f"tick value mismatch {symbol}")
        require(spec["volume_min"] == 0.01 and spec["volume_step"] == 0.01, f"volume spec mismatch {symbol}")

    periods = declaration["fixed_periods"]
    all_observations: list[Observation] = []
    per_symbol: dict[str, Any] = {}
    for symbol in declaration["symbols"]:
        pin = pin_by_name[declaration["bar_files"][symbol]]
        bars = load_bars(input_root / pin["name"], pin)
        observations, structural = reconstruct(symbol, bars, periods)
        all_observations.extend(observations)
        per_symbol[symbol] = structural

    pooled: dict[str, Any] = {}
    for period in periods:
        selected = [item for item in all_observations if item.period == period]
        hours: dict[int, int] = {}
        dates: set[str] = set()
        for item in selected:
            hours[item.signal_epoch] = hours.get(item.signal_epoch, 0) + 1
            dates.add(item.signal_time.strftime("%Y-%m-%d"))
        # Normal-day counts are common across all three inputs by declaration.
        normal_days = max(per_symbol[symbol][period]["normal_days"] for symbol in declaration["symbols"])
        pooled[period] = {
            "normal_days": normal_days,
            "signals": len(selected),
            "signals_per_day": len(selected) / normal_days,
            "unique_signal_hours": len(hours),
            "unique_hours_per_day": len(hours) / normal_days,
            "single_symbol_hours": sum(value == 1 for value in hours.values()),
            "two_symbol_hours": sum(value == 2 for value in hours.values()),
            "three_symbol_hours": sum(value == 3 for value in hours.values()),
            "up": sum(item.signal_direction > 0 for item in selected),
            "down": sum(item.signal_direction < 0 for item in selected),
        }

    p1 = [item for item in all_observations if item.period == "P1_2022H2_2023"]
    p1_splits = {
        "P1_2022H2": {
            "signals": sum(item.signal_time < datetime(2023, 1, 1) for item in p1),
            "normal_days": declaration["premetric_structural_feasibility"]["p1_splits"]["P1_2022H2"]["normal_days"],
        },
        "P1_2023": {
            "signals": sum(item.signal_time >= datetime(2023, 1, 1) for item in p1),
            "normal_days": declaration["premetric_structural_feasibility"]["p1_splits"]["P1_2023"]["normal_days"],
        },
    }
    for value in p1_splits.values():
        value["signals_per_day"] = value["signals"] / value["normal_days"]

    expected = declaration["premetric_structural_feasibility"]
    require(per_symbol == expected["per_symbol"], "per-symbol structural reconstruction mismatch")
    require(pooled == expected["pooled"], "pooled structural reconstruction mismatch")
    require(p1_splits == expected["p1_splits"], "P1 split structural reconstruction mismatch")

    density_gate = declaration["fixed_integrity_and_density_gate"]
    density_checks = {
        "minimum_signals_per_day_each_period": all(
            pooled[period]["signals_per_day"] >= density_gate["minimum_signals_per_day_each_period"]
            for period in periods
        ),
        "minimum_unique_hours_per_day_each_period": all(
            pooled[period]["unique_hours_per_day"] >= density_gate["minimum_unique_hours_per_day_each_period"]
            for period in periods
        ),
        "minimum_per_symbol_signals_per_day_each_period": all(
            per_symbol[symbol][period]["signals_per_day"] >= density_gate["minimum_per_symbol_signals_per_day_each_period"]
            for symbol in declaration["symbols"]
            for period in periods
        ),
        "minimum_each_side_each_period": all(
            min(pooled[period]["up"], pooled[period]["down"]) >= density_gate["minimum_each_side_each_period"]
            for period in periods
        ),
        "zero_boundary_exclusions": all(
            per_symbol[symbol][period]["boundary_excluded"] == 0
            for symbol in declaration["symbols"]
            for period in periods
        ),
    }
    require(all(density_checks.values()), f"density gate failed: {density_checks}")

    point = declaration["fixed_cost_proxy"]["point"]
    contract = declaration["fixed_cost_proxy"]["trade_contract_size"]
    volume = declaration["fixed_cost_proxy"]["volume"]
    discovery: dict[str, Any] = {}
    p1_passes: list[str] = []
    for book in declaration["direction_books"]:
        pooled_metrics = metrics(p1, book, point, contract, volume)
        splits = {
            "P1_2022H2": metrics([item for item in p1 if item.signal_time < datetime(2023, 1, 1)], book, point, contract, volume),
            "P1_2023": metrics([item for item in p1 if item.signal_time >= datetime(2023, 1, 1)], book, point, contract, volume),
        }
        symbols = {
            symbol: metrics([item for item in p1 if item.symbol == symbol], book, point, contract, volume)
            for symbol in declaration["symbols"]
        }
        sides = {
            "UP": metrics([item for item in p1 if item.signal_direction > 0], book, point, contract, volume),
            "DOWN": metrics([item for item in p1 if item.signal_direction < 0], book, point, contract, volume),
        }
        symbol_nets = {symbol: value["double_spread_net_usd"] for symbol, value in symbols.items()}
        gate = declaration["fixed_p1_direction_selection_gate"]
        checks = {
            "positive_net": pooled_metrics["double_spread_net_usd"] > 0,
            "profit_factor": passes_floor(pooled_metrics["double_spread_profit_factor"], gate["minimum_profit_factor"]),
            "net_to_drawdown": passes_floor(pooled_metrics["double_spread_net_to_drawdown"], gate["minimum_net_to_drawdown"]),
            "both_calendar_splits_positive": all(value["double_spread_net_usd"] > 0 for value in splits.values()),
            "all_symbols_positive": all(value > 0 for value in symbol_nets.values()),
            "both_signal_sides_positive": all(value["double_spread_net_usd"] > 0 for value in sides.values()),
            "symbol_concentration": (positive_share(symbol_nets) or 1.0) <= gate["maximum_symbol_share_of_positive_net"],
        }
        passed = all(checks.values())
        if passed:
            p1_passes.append(book)
        discovery[book] = {
            "pooled": pooled_metrics,
            "calendar_splits": splits,
            "symbols": symbols,
            "signal_sides": sides,
            "maximum_symbol_share_of_positive_net": positive_share(symbol_nets),
            "gate_checks": checks,
            "passed": passed,
        }

    selected_book: str | None = None
    if p1_passes:
        selected_book = sorted(
            p1_passes,
            key=lambda book: (
                discovery[book]["pooled"]["double_spread_net_to_drawdown"],
                discovery[book]["pooled"]["double_spread_profit_factor"],
                discovery[book]["pooled"]["double_spread_net_usd"],
                1 if book == "REVERSION" else 0,
            ),
            reverse=True,
        )[0]

    later_economics_opened = selected_book is not None
    confirmation: dict[str, Any] | None = None
    full_metrics: dict[str, Any] | None = None
    confirmation_passed = False
    full_candidate_passed = False
    if selected_book is not None:
        period_metrics = {
            period: metrics([item for item in all_observations if item.period == period], selected_book, point, contract, volume)
            for period in periods
        }
        confirmation_items = [item for item in all_observations if item.period in {"P2_2024", "P3_2025", "P4_2026_JAN_MAY"}]
        confirmation_pooled = metrics(confirmation_items, selected_book, point, contract, volume)
        confirmation_symbols = {
            symbol: metrics([item for item in confirmation_items if item.symbol == symbol], selected_book, point, contract, volume)
            for symbol in declaration["symbols"]
        }
        confirmation_sides = {
            "UP": metrics([item for item in confirmation_items if item.signal_direction > 0], selected_book, point, contract, volume),
            "DOWN": metrics([item for item in confirmation_items if item.signal_direction < 0], selected_book, point, contract, volume),
        }
        gate = declaration["fixed_confirmation_and_latest_gate"]
        confirmation_checks = {
            "each_confirmation_period_positive": all(period_metrics[p]["double_spread_net_usd"] > 0 for p in ["P2_2024", "P3_2025", "P4_2026_JAN_MAY"]),
            "each_confirmation_period_pf": all(passes_floor(period_metrics[p]["double_spread_profit_factor"], gate["minimum_each_confirmation_profit_factor"]) for p in ["P2_2024", "P3_2025", "P4_2026_JAN_MAY"]),
            "pooled_confirmation_pf": passes_floor(confirmation_pooled["double_spread_profit_factor"], gate["minimum_pooled_confirmation_profit_factor"]),
            "pooled_confirmation_net_to_dd": passes_floor(confirmation_pooled["double_spread_net_to_drawdown"], gate["minimum_pooled_confirmation_net_to_drawdown"]),
            "all_confirmation_symbols_positive": all(value["double_spread_net_usd"] > 0 for value in confirmation_symbols.values()),
            "both_confirmation_sides_positive": all(value["double_spread_net_usd"] > 0 for value in confirmation_sides.values()),
            "latest_nonnegative": period_metrics["P5_LATEST_2026_JUN_JUL"]["double_spread_net_usd"] >= 0,
            "latest_pf": passes_floor(period_metrics["P5_LATEST_2026_JUN_JUL"]["double_spread_profit_factor"], gate["minimum_latest_profit_factor"]),
        }
        confirmation_passed = all(confirmation_checks.values())
        full_metrics = metrics(all_observations, selected_book, point, contract, volume)
        full_symbols = {
            symbol: metrics([item for item in all_observations if item.symbol == symbol], selected_book, point, contract, volume)
            for symbol in declaration["symbols"]
        }
        full_sides = {
            "UP": metrics([item for item in all_observations if item.signal_direction > 0], selected_book, point, contract, volume),
            "DOWN": metrics([item for item in all_observations if item.signal_direction < 0], selected_book, point, contract, volume),
        }
        period_nets = {period: value["double_spread_net_usd"] for period, value in period_metrics.items()}
        symbol_nets = {symbol: value["double_spread_net_usd"] for symbol, value in full_symbols.items()}
        full_gate = declaration["fixed_full_candidate_gate"]
        full_checks = {
            "confirmation_passed": confirmation_passed,
            "full_positive": full_metrics["double_spread_net_usd"] > 0,
            "full_pf": passes_floor(full_metrics["double_spread_profit_factor"], full_gate["minimum_profit_factor"]),
            "full_net_to_dd": passes_floor(full_metrics["double_spread_net_to_drawdown"], full_gate["minimum_net_to_drawdown"]),
            "all_periods_nonnegative": all(value >= 0 for value in period_nets.values()),
            "all_symbols_positive": all(value > 0 for value in symbol_nets.values()),
            "both_signal_sides_positive": all(value["double_spread_net_usd"] > 0 for value in full_sides.values()),
            "period_concentration": (positive_share(period_nets) or 1.0) <= full_gate["maximum_period_share_of_positive_net"],
            "symbol_concentration": (positive_share(symbol_nets) or 1.0) <= full_gate["maximum_symbol_share_of_positive_net"],
        }
        full_candidate_passed = all(full_checks.values())
        confirmation = {
            "periods": period_metrics,
            "pooled_P2_P4": confirmation_pooled,
            "P2_P4_symbols": confirmation_symbols,
            "P2_P4_signal_sides": confirmation_sides,
            "confirmation_gate_checks": confirmation_checks,
            "confirmation_passed": confirmation_passed,
            "full": full_metrics,
            "full_symbols": full_symbols,
            "full_signal_sides": full_sides,
            "maximum_period_share_of_positive_net": positive_share(period_nets),
            "maximum_symbol_share_of_positive_net": positive_share(symbol_nets),
            "full_gate_checks": full_checks,
            "full_candidate_passed": full_candidate_passed,
        }

    if selected_book is None:
        verdict = "FAIL_H1_BODY_ENGULFING_NO_P1_DIRECTION_NO_SEED"
        retained_seed = None
    elif not full_candidate_passed:
        verdict = "FAIL_H1_BODY_ENGULFING_CONFIRMATION_OR_LATEST_NO_SEED"
        retained_seed = None
    else:
        verdict = "PASS_H1_BODY_ENGULFING_RETAIN_ONE_OPTIMIZATION_INFORMATION_SEED"
        retained_seed = f"THREE_INDEX_H1_BODY_ENGULFING_{selected_book}_FIXED_001_4H"

    elapsed = time.perf_counter() - started
    result = {
        "schema": "zeta-next-three-index-h1-body-engulfing-response-result-v1",
        "created_at_local": datetime.now().astimezone().isoformat(),
        "status": "UNIT_102_VALID_COMPLETE",
        "unit": declaration["unit"],
        "family": declaration["family"],
        "evidence": {
            "declaration_path": declaration_path.as_posix(),
            "declaration_bytes": declaration_path.stat().st_size,
            "declaration_sha256": sha256_file(declaration_path),
            "script_path": own_path.as_posix(),
            "script_bytes": own_path.stat().st_size,
            "script_sha256": sha256_file(own_path),
            "input_manifest_sha256": declaration["immutable_inputs"]["manifest_sha256"],
        },
        "execution": {
            "successful_formal_processes": 1,
            "economic_metric_reruns": 0,
            "engineering_or_design_corrections": 0,
            "internal_elapsed_seconds": elapsed,
            "mql_changes": 0,
            "runtime_copies": 0,
            "compile_paths": 0,
            "tester_paths": 0,
            "orders": 0,
            "broker_account_queries": 0,
        },
        "integrity": {
            "passed": True,
            "input_files": len(pins),
            "bar_rows": sum(pin.get("rows", 0) for pin in pins),
            "signals": len(all_observations),
            "density_checks": density_checks,
            "faults": 0,
        },
        "structural": {
            "per_symbol": per_symbol,
            "pooled": pooled,
            "p1_splits": p1_splits,
        },
        "P1_direction_discovery": discovery,
        "P1_passing_directions": p1_passes,
        "selected_direction": selected_book,
        "later_economics_opened": later_economics_opened,
        "confirmation_and_latest": confirmation,
        "verdict": verdict,
        "retained_seed": retained_seed,
        "economic_interpretation": (
            "The fixed threshold-free body-control-transfer response passed discovery, confirmation, latest and full economic gates. It remains proxy information only."
            if retained_seed
            else "The structurally dense fixed response did not produce the complete required double-spread economic breadth; no additive-alpha seed survives."
        ),
        "live_surface": "UNTOUCHED",
        "program_6_opened": False,
    }
    raw_output.parent.mkdir(parents=True, exist_ok=True)
    durable_output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    raw_output.write_text(rendered, encoding="utf-8")
    durable_output.write_text(rendered, encoding="utf-8")
    print(json.dumps({"verdict": verdict, "selected_direction": selected_book, "signals": len(all_observations), "elapsed_seconds": elapsed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
