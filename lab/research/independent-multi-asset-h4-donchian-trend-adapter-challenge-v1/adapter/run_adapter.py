from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time as datetime_time, timedelta
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


FAMILY = "independent-multi-asset-h4-donchian-trend-adapter-challenge-v1"
SYMBOLS = ("AUDUSD", "EURUSD", "GBPUSD", "NZDUSD", "US100", "US30", "US500")
SYMBOL_ORDER = {symbol: index for index, symbol in enumerate(SYMBOLS)}
ASSET_CLASS = {
    "AUDUSD": "currency",
    "EURUSD": "currency",
    "GBPUSD": "currency",
    "NZDUSD": "currency",
    "US100": "equity_index",
    "US30": "equity_index",
    "US500": "equity_index",
}
VARIANTS = {
    "MULTI_ASSET_DONCHIAN_120_60": {"entry_window": 120, "exit_window": 60},
    "MULTI_ASSET_DONCHIAN_240_120": {"entry_window": 240, "exit_window": 120},
}
VARIANT_ORDER = tuple(VARIANTS)
DEVELOPMENT_START = pd.Timestamp("2024-01-01T00:00:00Z")
DEVELOPMENT_END = pd.Timestamp("2026-01-01T00:00:00Z")
LOCKED_START = DEVELOPMENT_END
LOCKED_END = pd.Timestamp("2026-08-01T00:00:00Z")
MAX_HOLD_BARS = 480
ATR_WINDOW = 20
INITIAL_DEPOSIT = 100.0
POSITION_RISK_FRACTION = 0.04
MINIMUM_LOT_CAP_FRACTION = 0.06
AGGREGATE_RISK_CAP_FRACTION = 0.18
DEVELOPMENT_ACTUAL_GATE = 149.97
DEVELOPMENT_STRESS_GATE = 127.786
WHOLE_ACTUAL_GATE = 409.81
WHOLE_STRESS_GATE = 367.818
DRAWDOWN_GATE_PCT = 37.39
ROBUST_RECOVERY_GATE = 3.295860215
TURNOVER_GATE = 0.10
YEAR_START_GATE = 20
BREADTH_SYMBOL_GATE = 4
BROAD_SLICE_MIN = 10

EXPECTED = {
    "contract": {
        "path": "lab/research/independent-multi-asset-h4-donchian-trend-adapter-challenge-v1/config/challenge-contract.json",
        "bytes": 23734,
        "sha256": "B2B481A47D82476C2096F45E8FB48D24EE73C864037862327E2B8F223BB673A1",
    },
    "declaration": {
        "path": "lab/research/independent-multi-asset-h4-donchian-trend-adapter-challenge-v1/evidence/INDEPENDENT_MULTI_ASSET_H4_DONCHIAN_TREND_ADAPTER_CHALLENGE_V1_DECLARATION.json",
        "bytes": 11870,
        "sha256": "0D307B8DF16070474490287E27A3F7BFA380FE752A78C3C4905D33768B70C2DB",
    },
    "runtime_source_correction": {
        "path": "lab/research/independent-multi-asset-h4-donchian-trend-adapter-challenge-v1/evidence/INDEPENDENT_MULTI_ASSET_H4_DONCHIAN_TREND_ADAPTER_CHALLENGE_V1_RUNTIME_SOURCE_ENGINEERING_CORRECTION.json",
        "bytes": 8969,
        "sha256": "8DFD07F8DDBBE31133FEC4602ED56ED52840B2DACFF53AE70307F0A7A471EEA4",
    },
    "development_source": {
        "path": "lab/research/independent-multi-asset-h4-donchian-trend-adapter-challenge-v1/evidence/INDEPENDENT_MULTI_ASSET_H4_DONCHIAN_TREND_ADAPTER_CHALLENGE_V1_DEVELOPMENT_SOURCE_RECEIPT.json",
        "bytes": 11292,
        "sha256": "001EB67EF1E15651A32F47446D7AA88BA7AB969984E2D95071EF9467E57BD815",
    },
    "maturation": {
        "path": "lab/research/independent-multi-asset-h4-donchian-trend-adapter-challenge-v1/evidence/INDEPENDENT_MULTI_ASSET_H4_DONCHIAN_TREND_ADAPTER_CHALLENGE_V1_MATURATION_GEOMETRY_CORRECTION.json",
        "bytes": 5467,
        "sha256": "F4326D228F52205E427A8C15CB9C8179DC0EEC381A5D2AB5DBCD977027078ECD",
    },
    "requirements": {
        "path": "lab/research/independent-multi-asset-h4-donchian-trend-adapter-challenge-v1/adapter/requirements-adapter.txt",
        "bytes": 58,
        "sha256": "A8312E14ACD23C9B07977AE03A4A6CC747A6B6CC07B2C6D5ABCD3B824C4F3F33",
    },
    "v8": {
        "path": "optimization/campaigns/dd20-paired-clean-requal-mt5-v2/evidence/DD20_PAIRED_CLEAN_REQUAL_MT5_V2_VALID_NONCONFIRMATION_V1.json",
        "bytes": 8423,
        "sha256": "693969C5C7988B5C504DD5A29D533770DBB15F7D80C430484C1861DB2CC5EA46",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root is not an object: {path}")
    return value


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def rel(path: Path, workspace: Path) -> str:
    return str(path.relative_to(workspace)).replace("\\", "/")


def finite(value: object, label: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise RuntimeError(f"nonfinite {label}")
    return number


def clean_float(value: float, digits: int = 12) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise RuntimeError("attempted to serialize a nonfinite number")
    rounded = round(number, digits)
    return 0.0 if rounded == 0 else rounded


def authority_record(path: Path, workspace: Path) -> dict[str, Any]:
    return {
        "path": rel(path, workspace),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def verify_authorities(workspace: Path) -> dict[str, dict[str, Any]]:
    verified: dict[str, dict[str, Any]] = {}
    for name, expected in EXPECTED.items():
        path = workspace / str(expected["path"])
        if not path.is_file():
            raise RuntimeError(f"missing authority {name}: {path}")
        observed = authority_record(path, workspace)
        if (
            observed["bytes"] != int(expected["bytes"])
            or observed["sha256"] != str(expected["sha256"])
        ):
            raise RuntimeError(f"authority mismatch: {name}")
        verified[name] = observed
    if read_json(workspace / EXPECTED["maturation"]["path"]).get("status") != (
        "COMPLETE_MATURATION_GEOMETRY_CORRECTED_PREIMPLEMENTATION_PREOUTCOME"
    ):
        raise RuntimeError("maturation authority has the wrong status")
    return verified


def verify_freeze(freeze_path: Path, script_path: Path, workspace: Path) -> dict[str, Any]:
    if not freeze_path.is_file():
        raise RuntimeError(f"implementation freeze missing: {freeze_path}")
    freeze = read_json(freeze_path)
    if freeze.get("status") != "IMPLEMENTATION_FROZEN_PREDEVELOPMENT_OUTCOME":
        raise RuntimeError("implementation freeze status is not authoritative")
    adapter = freeze.get("adapter")
    if not isinstance(adapter, dict):
        raise RuntimeError("implementation freeze lacks adapter authority")
    if (
        adapter.get("path") != rel(script_path, workspace)
        or int(adapter.get("bytes", -1)) != script_path.stat().st_size
        or adapter.get("sha256") != sha256(script_path)
    ):
        raise RuntimeError("adapter does not match implementation freeze")
    return freeze


def normalize_time(raw: pd.Series, symbol: str) -> pd.Series:
    naive = pd.to_datetime(raw, unit="s", errors="raise")
    try:
        normalized = naive.dt.tz_localize(
            "Europe/Helsinki", ambiguous="raise", nonexistent="raise"
        ).dt.tz_convert("UTC")
    except Exception as exc:
        raise RuntimeError(f"{symbol} raw time localization failed: {exc}") from exc
    if normalized.duplicated().any() or not normalized.is_monotonic_increasing:
        raise RuntimeError(f"{symbol} normalized time is duplicate or nonincreasing")
    return normalized


def load_spec(path: Path, expected: dict[str, Any]) -> dict[str, Any]:
    if path.stat().st_size != int(expected["bytes"]) or sha256(path) != expected["sha256"]:
        raise RuntimeError(f"symbol specification authority mismatch: {path}")
    spec = read_json(path)
    if spec.get("symbol") not in SYMBOLS or spec.get("currency_profit") != "USD":
        raise RuntimeError(f"invalid USD symbol specification: {path}")
    positive = (
        "point",
        "trade_tick_size",
        "trade_tick_value",
        "trade_tick_value_profit",
        "trade_tick_value_loss",
        "trade_contract_size",
        "volume_min",
        "volume_step",
        "volume_max",
    )
    for field in positive:
        if finite(spec.get(field), f"{spec.get('symbol')}.{field}") <= 0:
            raise RuntimeError(f"nonpositive contract field: {spec.get('symbol')}.{field}")
    mode = int(spec.get("swap_mode"))
    if mode not in (0, 1, 2, 4, 5, 6):
        raise RuntimeError(f"unsupported corrected swap mode: {mode}")
    if mode == 2 and spec.get("currency_base") != "USD":
        raise RuntimeError("CURRENCY_SYMBOL requires USD base currency in Family 009")
    return spec


def load_rate_file(path: Path, expected: dict[str, Any], symbol: str) -> pd.DataFrame:
    if path.stat().st_size != int(expected["bytes"]) or sha256(path) != expected["sha256"]:
        raise RuntimeError(f"market source authority mismatch: {symbol}")
    frame = pd.read_csv(path)
    required = [
        "time",
        "open",
        "high",
        "low",
        "close",
        "tick_volume",
        "spread",
        "real_volume",
    ]
    if list(frame.columns) != required or len(frame) != int(expected["rows"]):
        raise RuntimeError(f"unexpected market source shape: {symbol}")
    frame["time"] = pd.to_numeric(frame["time"], errors="raise").astype("int64")
    if frame["time"].duplicated().any() or not frame["time"].is_monotonic_increasing:
        raise RuntimeError(f"raw time invariant failed: {symbol}")
    for column in ("open", "high", "low", "close", "spread"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        if not np.isfinite(frame[column].to_numpy(dtype="float64")).all():
            raise RuntimeError(f"nonfinite source column: {symbol}.{column}")
    if not (frame[["open", "high", "low", "close"]] > 0).all().all():
        raise RuntimeError(f"nonpositive OHLC: {symbol}")
    if not (frame["high"] >= frame[["open", "close", "low"]].max(axis=1)).all():
        raise RuntimeError(f"high invariant failed: {symbol}")
    if not (frame["low"] <= frame[["open", "close", "high"]].min(axis=1)).all():
        raise RuntimeError(f"low invariant failed: {symbol}")
    if (frame["spread"] < 0).any():
        raise RuntimeError(f"negative spread: {symbol}")
    frame["server_time"] = pd.to_datetime(frame["time"], unit="s", errors="raise")
    frame["time_utc"] = normalize_time(frame["time"], symbol)
    return frame


def load_development_sources(
    workspace: Path,
) -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, Any]], dict[str, Any]]:
    source_receipt = read_json(workspace / EXPECTED["development_source"]["path"])
    if source_receipt.get("status") != (
        "COMPLETE_FRESH_ORIGINAL_BROKER_DEVELOPMENT_SOURCE_SWAP_MODE_CORRECTED_PREIMPLEMENTATION_PREOUTCOME"
    ):
        raise RuntimeError("development source receipt has the wrong status")
    market_rows = source_receipt.get("market_outputs")
    spec_rows = source_receipt.get("specification_outputs")
    if not isinstance(market_rows, list) or not isinstance(spec_rows, list):
        raise RuntimeError("development source receipt is incomplete")
    market_by_symbol = {str(row["symbol"]): row for row in market_rows}
    spec_by_symbol = {str(row["symbol"]): row for row in spec_rows}
    if tuple(market_by_symbol) != SYMBOLS or tuple(spec_by_symbol) != SYMBOLS:
        raise RuntimeError("development source symbol order mismatch")
    frames: dict[str, pd.DataFrame] = {}
    specs: dict[str, dict[str, Any]] = {}
    for symbol in SYMBOLS:
        market_authority = market_by_symbol[symbol]
        spec_authority = spec_by_symbol[symbol]
        frames[symbol] = load_rate_file(
            workspace / market_authority["path"], market_authority, symbol
        )
        specs[symbol] = load_spec(
            workspace / spec_authority["path"], spec_authority
        )
    return frames, specs, source_receipt


def load_complete_sources(
    workspace: Path,
) -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, Any]], dict[str, Any]]:
    input_root = workspace / "lab" / "artifacts" / "raw" / FAMILY / "input"
    receipt_path = input_root / "COMPLETE_ACQUISITION_RECEIPT.json"
    if not receipt_path.is_file():
        raise RuntimeError("complete acquisition receipt is absent")
    receipt = read_json(receipt_path)
    if receipt.get("status") != "COMPLETE_STAGED_FRESH_DEDICATED_PORTABLE_ACQUISITION":
        raise RuntimeError("complete acquisition receipt has the wrong status")
    outputs = receipt.get("outputs")
    if not isinstance(outputs, dict) or tuple(outputs) != SYMBOLS:
        raise RuntimeError("complete acquisition outputs are incomplete")
    development_receipt = read_json(workspace / EXPECTED["development_source"]["path"])
    spec_by_symbol = {
        str(row["symbol"]): row for row in development_receipt["specification_outputs"]
    }
    frames: dict[str, pd.DataFrame] = {}
    specs: dict[str, dict[str, Any]] = {}
    for symbol in SYMBOLS:
        authority = dict(outputs[symbol])
        path = workspace / authority["path"]
        frame = pd.read_csv(path)
        authority["rows"] = int(authority["rows"])
        authority["bytes"] = int(authority["bytes"])
        frames[symbol] = load_rate_file(path, authority, symbol)
        spec_authority = spec_by_symbol[symbol]
        specs[symbol] = load_spec(workspace / spec_authority["path"], spec_authority)
    return frames, specs, receipt


def prepare_features(frame: pd.DataFrame, variant: str) -> dict[str, np.ndarray]:
    parameters = VARIANTS[variant]
    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1, skipna=False)
    return {
        "atr": true_range.rolling(ATR_WINDOW, min_periods=ATR_WINDOW).mean().to_numpy(),
        "entry_high": frame["high"]
        .rolling(parameters["entry_window"], min_periods=parameters["entry_window"])
        .max()
        .shift(1)
        .to_numpy(),
        "entry_low": frame["low"]
        .rolling(parameters["entry_window"], min_periods=parameters["entry_window"])
        .min()
        .shift(1)
        .to_numpy(),
        "exit_high": frame["high"]
        .rolling(parameters["exit_window"], min_periods=parameters["exit_window"])
        .max()
        .shift(1)
        .to_numpy(),
        "exit_low": frame["low"]
        .rolling(parameters["exit_window"], min_periods=parameters["exit_window"])
        .min()
        .shift(1)
        .to_numpy(),
    }


def signal_surface(
    frames: dict[str, pd.DataFrame],
    specs: dict[str, dict[str, Any]],
    period_start: pd.Timestamp,
    period_end: pd.Timestamp,
) -> tuple[
    dict[str, dict[str, dict[str, np.ndarray]]],
    dict[str, list[dict[str, Any]]],
    dict[str, set[date]],
    dict[str, dict[str, int]],
]:
    features: dict[str, dict[str, dict[str, np.ndarray]]] = {
        variant: {} for variant in VARIANT_ORDER
    }
    signals: dict[str, list[dict[str, Any]]] = {variant: [] for variant in VARIANT_ORDER}
    active_dates: dict[str, set[date]] = {variant: set() for variant in VARIANT_ORDER}
    opportunity_counts: dict[str, dict[str, int]] = {
        variant: {symbol: 0 for symbol in SYMBOLS} for variant in VARIANT_ORDER
    }
    for variant in VARIANT_ORDER:
        for symbol in SYMBOLS:
            frame = frames[symbol]
            spec = specs[symbol]
            feature = prepare_features(frame, variant)
            features[variant][symbol] = feature
            times = frame["time_utc"]
            closes = frame["close"].to_numpy(dtype="float64")
            for entry_index in range(1, len(frame)):
                decision_index = entry_index - 1
                entry_time = times.iloc[entry_index]
                if entry_time < period_start or entry_time >= period_end:
                    continue
                maturity_index = entry_index + MAX_HOLD_BARS - 1
                if maturity_index >= len(frame) or times.iloc[maturity_index] >= period_end:
                    continue
                required_values = (
                    feature["atr"][decision_index],
                    feature["entry_high"][decision_index],
                    feature["entry_low"][decision_index],
                    feature["exit_high"][decision_index],
                    feature["exit_low"][decision_index],
                )
                if not all(math.isfinite(float(value)) for value in required_values):
                    continue
                atr = float(feature["atr"][decision_index])
                if atr <= 0:
                    raise RuntimeError(f"nonpositive ATR: {variant}/{symbol}/{entry_index}")
                opportunity_counts[variant][symbol] += 1
                active_dates[variant].add(entry_time.date())
                close = float(closes[decision_index])
                high = float(feature["entry_high"][decision_index])
                low = float(feature["entry_low"][decision_index])
                if close > high:
                    direction = "LONG"
                    excess = (close - high) / atr
                elif close < low:
                    direction = "SHORT"
                    excess = (low - close) / atr
                else:
                    continue
                entry_spread_points = float(frame["spread"].iloc[entry_index])
                point = float(spec["point"])
                entry_bid = float(frame["open"].iloc[entry_index])
                entry_ask = entry_bid + entry_spread_points * point
                risk_distance = 2.0 * atr
                risk_per_lot = (
                    risk_distance
                    / float(spec["trade_tick_size"])
                    * float(spec["trade_tick_value_loss"])
                )
                signals[variant].append(
                    {
                        "variant": variant,
                        "symbol": symbol,
                        "asset_class": ASSET_CLASS[symbol],
                        "direction": direction,
                        "decision_index": decision_index,
                        "entry_index": entry_index,
                        "decision_bar_raw_time": int(frame["time"].iloc[decision_index]),
                        "entry_raw_time": int(frame["time"].iloc[entry_index]),
                        "decision_bar_time_utc": frame["time_utc"].iloc[
                            decision_index
                        ],
                        "entry_time_utc": entry_time,
                        "entry_server_time": frame["server_time"].iloc[entry_index],
                        "entry_bid": entry_bid,
                        "entry_ask": entry_ask,
                        "entry_spread_points": entry_spread_points,
                        "atr": atr,
                        "risk_distance": risk_distance,
                        "risk_per_lot": risk_per_lot,
                        "normalized_excess": float(excess),
                        "signal_id": (
                            f"{variant}:{symbol}:{int(frame['time'].iloc[entry_index])}:"
                            f"{direction}"
                        ),
                    }
                )
        signals[variant].sort(
            key=lambda row: (
                row["entry_time_utc"],
                -float(row["normalized_excess"]),
                SYMBOL_ORDER[str(row["symbol"])],
            )
        )
    return features, signals, active_dates, opportunity_counts


def volume_for_signal(
    signal: dict[str, Any], spec: dict[str, Any], balance_snapshot: float
) -> tuple[float, float, str | None]:
    if not math.isfinite(balance_snapshot) or balance_snapshot <= 0:
        return 0.0, 0.0, "CAPITAL_DEPLETED"
    risk_per_lot = float(signal["risk_per_lot"])
    minimum = float(spec["volume_min"])
    step = float(spec["volume_step"])
    maximum = float(spec["volume_max"])
    minimum_loss = risk_per_lot * minimum
    if minimum_loss > MINIMUM_LOT_CAP_FRACTION * balance_snapshot + 1e-12:
        return 0.0, minimum_loss, "MINIMUM_LOT_RISK"
    target_lots = POSITION_RISK_FRACTION * balance_snapshot / risk_per_lot
    capped = min(target_lots, maximum)
    units = math.floor((capped + 1e-12) / step)
    volume = round(units * step, 10)
    if volume < minimum - 1e-12:
        volume = minimum
    planned = risk_per_lot * volume
    return volume, planned, None


def precheck(
    frames: dict[str, pd.DataFrame],
    specs: dict[str, dict[str, Any]],
    authorities: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    _, signals, active_dates, opportunities = signal_surface(
        frames, specs, DEVELOPMENT_START, DEVELOPMENT_END
    )
    variants: dict[str, Any] = {}
    for variant in VARIANT_ORDER:
        rows = signals[variant]
        feasible = 0
        minimum_losses: list[float] = []
        by_symbol = Counter(str(row["symbol"]) for row in rows)
        by_direction = Counter(str(row["direction"]) for row in rows)
        by_year = Counter(int(row["entry_time_utc"].year) for row in rows)
        for row in rows:
            spec = specs[str(row["symbol"])]
            minimum_loss = float(row["risk_per_lot"]) * float(spec["volume_min"])
            minimum_losses.append(minimum_loss)
            if minimum_loss <= MINIMUM_LOT_CAP_FRACTION * INITIAL_DEPOSIT + 1e-12:
                feasible += 1
        variants[variant] = {
            "mature_opportunities_by_symbol": opportunities[variant],
            "mature_opportunities_total": sum(opportunities[variant].values()),
            "portfolio_active_dates": len(active_dates[variant]),
            "signal_count": len(rows),
            "signals_per_active_date": clean_float(
                len(rows) / len(active_dates[variant]) if active_dates[variant] else 0
            ),
            "signals_by_symbol": dict(by_symbol),
            "signals_by_direction": dict(by_direction),
            "signals_by_entry_year": {str(year): by_year[year] for year in (2024, 2025)},
            "minimum_lot_feasible_at_100_usd": feasible,
            "minimum_lot_infeasible_at_100_usd": len(rows) - feasible,
            "maximum_minimum_lot_planned_loss_usd": clean_float(
                max(minimum_losses) if minimum_losses else 0
            ),
        }
    return {
        "status": "VALID_OUTCOME_FREE_PRECHECK",
        "family": FAMILY,
        "authorities": authorities,
        "variants": variants,
        "future_exit_path_rows_evaluated": 0,
        "candidate_lifecycles_or_economic_metrics": 0,
        "improvement_audit_values": 0,
        "locked_2026_rows_loaded": 0,
        "persistent_outputs_written": 0,
    }


def iso_utc(value: object) -> str:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    else:
        stamp = stamp.tz_convert("UTC")
    return stamp.isoformat().replace("+00:00", "Z")


def iso_server(value: object) -> str:
    return pd.Timestamp(value).isoformat()


def money_from_directional_price(
    directional_price: float, spec: dict[str, Any], volume: float
) -> float:
    tick_value = float(
        spec[
            "trade_tick_value_profit"
            if directional_price >= 0
            else "trade_tick_value_loss"
        ]
    )
    return directional_price / float(spec["trade_tick_size"]) * tick_value * volume


def spread_burden_money(
    spread_price: float, spec: dict[str, Any], volume: float
) -> float:
    return (
        spread_price
        / float(spec["trade_tick_size"])
        * float(spec["trade_tick_value_loss"])
        * volume
    )


def rollover_boundaries(
    entry_server_time: pd.Timestamp, exit_server_time: pd.Timestamp
) -> list[pd.Timestamp]:
    entry = pd.Timestamp(entry_server_time)
    exit_stamp = pd.Timestamp(exit_server_time)
    boundary = entry.normalize()
    if boundary <= entry:
        boundary += pd.Timedelta(days=1)
    result: list[pd.Timestamp] = []
    while boundary <= exit_stamp:
        # Broker triple-rollover fields already carry weekend financing. Charging
        # Saturday/Sunday boundaries in addition would count that financing twice.
        if boundary.weekday() < 5:
            result.append(boundary)
        boundary += pd.Timedelta(days=1)
    return result


def rollover_reference_price(
    frame: pd.DataFrame, boundary: pd.Timestamp
) -> float:
    server_values = frame["server_time"].to_numpy(dtype="datetime64[ns]")
    position = int(
        np.searchsorted(server_values, np.datetime64(boundary.to_datetime64()), side="right")
    ) - 1
    if position < 0:
        raise RuntimeError("rollover reference precedes source")
    if pd.Timestamp(frame["server_time"].iloc[position]) == boundary:
        return float(frame["open"].iloc[position])
    return float(frame["close"].iloc[position])


def swap_money(
    spec: dict[str, Any],
    frame: pd.DataFrame,
    direction: str,
    volume: float,
    entry_server_time: pd.Timestamp,
    exit_server_time: pd.Timestamp,
    entry_price: float,
) -> tuple[float, int, int]:
    mode = int(spec["swap_mode"])
    if mode == 0:
        return 0.0, 0, 0
    rate = float(spec["swap_long"] if direction == "LONG" else spec["swap_short"])
    total = 0.0
    charged_boundaries = 0
    multiplier_days = 0
    for boundary in rollover_boundaries(entry_server_time, exit_server_time):
        mql_weekday = (boundary.weekday() + 1) % 7
        multiplier = 3 if mql_weekday == int(spec["swap_rollover3days"]) else 1
        if mode == 1:  # POINTS
            amount = (
                rate
                * float(spec["point"])
                / float(spec["trade_tick_size"])
                * float(spec["trade_tick_value"])
                * volume
                * multiplier
            )
        elif mode == 2:  # CURRENCY_SYMBOL, USD base and USD deposit are frozen.
            amount = rate * volume * multiplier
        elif mode == 4:  # CURRENCY_DEPOSIT
            amount = rate * volume * multiplier
        elif mode == 5:  # INTEREST_CURRENT
            reference = rollover_reference_price(frame, boundary)
            amount = (
                rate
                / 100.0
                * float(spec["trade_contract_size"])
                * reference
                * volume
                / 360.0
                * multiplier
            )
        elif mode == 6:  # INTEREST_OPEN
            amount = (
                rate
                / 100.0
                * float(spec["trade_contract_size"])
                * entry_price
                * volume
                / 360.0
                * multiplier
            )
        else:
            raise RuntimeError(f"unsupported swap mode reached economics: {mode}")
        if not math.isfinite(amount):
            raise RuntimeError("nonfinite swap amount")
        total += amount
        charged_boundaries += 1
        multiplier_days += multiplier
    return total, charged_boundaries, multiplier_days


def base_state_row(signal: dict[str, Any], signal_sequence: int) -> dict[str, Any]:
    return {
        "variant": signal["variant"],
        "signal_sequence": signal_sequence,
        "signal_id": signal["signal_id"],
        "symbol": signal["symbol"],
        "asset_class": signal["asset_class"],
        "direction": signal["direction"],
        "decision_bar_raw_time": signal["decision_bar_raw_time"],
        "decision_bar_time_utc": iso_utc(signal["decision_bar_time_utc"]),
        "entry_raw_time": signal["entry_raw_time"],
        "entry_time_utc": iso_utc(signal["entry_time_utc"]),
        "entry_server_time": iso_server(signal["entry_server_time"]),
        "normalized_breakout_excess": clean_float(signal["normalized_excess"]),
        "atr20": clean_float(signal["atr"]),
        "risk_distance": clean_float(signal["risk_distance"]),
        "risk_per_lot_usd": clean_float(signal["risk_per_lot"]),
        "entry_bid": clean_float(signal["entry_bid"]),
        "entry_ask": clean_float(signal["entry_ask"]),
        "entry_spread_points": clean_float(signal["entry_spread_points"]),
        "admission_status": "UNSET",
        "block_reason": "",
        "actual_balance_snapshot_usd": 0.0,
        "reservation_before_usd": 0.0,
        "aggregate_cap_usd": 0.0,
        "volume": 0.0,
        "planned_stop_loss_usd": 0.0,
        "trade_sequence": 0,
        "exit_reason": "",
        "exit_time_utc": "",
        "realized_actual_r": "",
        "realized_stressed_r": "",
    }


def settle_position(
    position: dict[str, Any],
    frame: pd.DataFrame,
    spec: dict[str, Any],
    exit_index: int,
    exit_reason: str,
) -> dict[str, Any]:
    row = frame.iloc[exit_index]
    direction = str(position["direction"])
    at_close = exit_reason == "MAX_HOLD"
    spread_price = float(row["spread"]) * float(spec["point"])
    bid_reference = float(row["close"] if at_close else row["open"])
    exit_time_utc = pd.Timestamp(row["time_utc"])
    exit_server_time = pd.Timestamp(row["server_time"])
    if at_close:
        exit_time_utc += pd.Timedelta(hours=4)
        exit_server_time += pd.Timedelta(hours=4)
    if exit_reason == "HARD_STOP":
        execution_price = float(position["stop_price"])
        exit_bid = execution_price if direction == "LONG" else execution_price - spread_price
    else:
        exit_bid = bid_reference
        execution_price = exit_bid if direction == "LONG" else exit_bid + spread_price
    if direction == "LONG":
        gross_directional_price = exit_bid - float(position["entry_bid"])
        actual_directional_price = execution_price - float(position["entry_price"])
        stress_spread_price = float(position["entry_spread_price"])
    else:
        gross_directional_price = float(position["entry_bid"]) - exit_bid
        actual_directional_price = float(position["entry_price"]) - execution_price
        stress_spread_price = spread_price
    volume = float(position["volume"])
    gross_movement = money_from_directional_price(
        gross_directional_price, spec, volume
    )
    price_pnl = money_from_directional_price(actual_directional_price, spec, volume)
    swap, rollover_count, rollover_multiplier_days = swap_money(
        spec,
        frame,
        direction,
        volume,
        pd.Timestamp(position["entry_server_time"]),
        exit_server_time,
        float(position["entry_price"]),
    )
    spread_burden = spread_burden_money(stress_spread_price, spec, volume)
    actual_pnl = price_pnl + swap
    stressed_pnl = actual_pnl - spread_burden
    planned = float(position["planned_stop_loss_usd"])
    return {
        "variant": position["variant"],
        "trade_sequence": position["trade_sequence"],
        "signal_sequence": position["signal_sequence"],
        "signal_id": position["signal_id"],
        "symbol": position["symbol"],
        "asset_class": position["asset_class"],
        "direction": direction,
        "entry_raw_time": position["entry_raw_time"],
        "entry_time_utc": iso_utc(position["entry_time_utc"]),
        "entry_server_time": iso_server(position["entry_server_time"]),
        "exit_bar_raw_time": int(row["time"]),
        "exit_time_utc": iso_utc(exit_time_utc),
        "exit_server_time": iso_server(exit_server_time),
        "exit_reason": exit_reason,
        "held_h4_bars": exit_index - int(position["entry_index"]) + 1,
        "volume": clean_float(volume),
        "planned_stop_loss_usd": clean_float(planned),
        "risk_distance": clean_float(position["risk_distance"]),
        "entry_bid": clean_float(position["entry_bid"]),
        "entry_price": clean_float(position["entry_price"]),
        "stop_price": clean_float(position["stop_price"]),
        "exit_bid": clean_float(exit_bid),
        "exit_price": clean_float(execution_price),
        "exit_spread_points": clean_float(row["spread"]),
        "gross_movement_usd": clean_float(gross_movement),
        "observed_spread_burden_usd": clean_float(spread_burden),
        "price_pnl_usd": clean_float(price_pnl),
        "swap_usd": clean_float(swap),
        "rollover_boundaries": rollover_count,
        "rollover_multiplier_days": rollover_multiplier_days,
        "actual_pnl_usd": clean_float(actual_pnl),
        "stressed_pnl_usd": clean_float(stressed_pnl),
        "actual_r": clean_float(actual_pnl / planned),
        "stressed_r": clean_float(stressed_pnl / planned),
    }


def summarize_simulation(
    variant: str,
    states: list[dict[str, Any]],
    trades: list[dict[str, Any]],
    active_dates: set[date],
    opportunities: dict[str, int],
    period_start: pd.Timestamp,
    period_end: pd.Timestamp,
    initial_actual_balance: float,
    initial_stressed_balance: float,
    ending_actual_balance: float,
    ending_stressed_balance: float,
    actual_peak: float,
    maximum_drawdown_usd: float,
    maximum_drawdown_pct: float,
) -> dict[str, Any]:
    years = list(range(int(period_start.year), int(period_end.year)))
    epochs: dict[str, dict[str, Any]] = {
        str(year): {
            "starts": 0,
            "closed_trades": 0,
            "actual_net_usd": 0.0,
            "stressed_net_usd": 0.0,
        }
        for year in years
    }
    for trade in trades:
        entry_year = str(pd.Timestamp(trade["entry_time_utc"]).year)
        exit_year = str(pd.Timestamp(trade["exit_time_utc"]).year)
        if entry_year in epochs:
            epochs[entry_year]["starts"] += 1
        if exit_year in epochs:
            epochs[exit_year]["closed_trades"] += 1
            epochs[exit_year]["actual_net_usd"] += float(trade["actual_pnl_usd"])
            epochs[exit_year]["stressed_net_usd"] += float(
                trade["stressed_pnl_usd"]
            )
    for epoch in epochs.values():
        epoch["actual_net_usd"] = clean_float(epoch["actual_net_usd"])
        epoch["stressed_net_usd"] = clean_float(epoch["stressed_net_usd"])

    accepted = len(trades)
    active_count = len(active_dates)
    stressed_net = ending_stressed_balance - initial_stressed_balance
    recovery_unbounded = maximum_drawdown_usd == 0.0 and stressed_net > 0.0
    recovery = (
        clean_float(stressed_net / maximum_drawdown_usd)
        if maximum_drawdown_usd > 0.0
        else None
    )
    block_counts = Counter(
        str(row["block_reason"])
        for row in states
        if row["admission_status"] == "BLOCKED"
    )
    exit_counts = Counter(str(row["exit_reason"]) for row in trades)
    symbols = sorted({str(row["symbol"]) for row in trades}, key=SYMBOL_ORDER.get)
    asset_classes = sorted({str(row["asset_class"]) for row in trades})
    directions = sorted({str(row["direction"]) for row in trades})
    return {
        "variant": variant,
        "period": f"{iso_utc(period_start)}/{iso_utc(period_end)}",
        "signal_count": len(states),
        "accepted_starts": accepted,
        "blocked_signals": len(states) - accepted,
        "block_counts": dict(sorted(block_counts.items())),
        "exit_counts": dict(sorted(exit_counts.items())),
        "portfolio_active_dates": active_count,
        "accepted_starts_per_portfolio_active_date": clean_float(
            accepted / active_count if active_count else 0.0
        ),
        "mature_decision_opportunities_by_symbol": opportunities,
        "mature_decision_opportunities_total": sum(opportunities.values()),
        "initial_actual_balance_usd": clean_float(initial_actual_balance),
        "initial_stressed_balance_usd": clean_float(initial_stressed_balance),
        "actual_net_usd": clean_float(
            ending_actual_balance - initial_actual_balance
        ),
        "stressed_net_usd": clean_float(
            ending_stressed_balance - initial_stressed_balance
        ),
        "ending_actual_balance_usd": clean_float(ending_actual_balance),
        "ending_stressed_balance_usd": clean_float(ending_stressed_balance),
        "actual_closed_balance_peak_usd": clean_float(actual_peak),
        "actual_closed_balance_drawdown_usd": clean_float(maximum_drawdown_usd),
        "actual_closed_balance_drawdown_pct": clean_float(maximum_drawdown_pct),
        "robust_recovery": recovery,
        "robust_recovery_unbounded_positive": recovery_unbounded,
        "epoch_metrics": epochs,
        "symbol_breadth": len(symbols),
        "accepted_symbols": symbols,
        "asset_class_breadth": asset_classes,
        "direction_breadth": directions,
        "gross_movement_usd": clean_float(
            sum(float(row["gross_movement_usd"]) for row in trades)
        ),
        "observed_spread_burden_usd": clean_float(
            sum(float(row["observed_spread_burden_usd"]) for row in trades)
        ),
        "swap_usd": clean_float(sum(float(row["swap_usd"]) for row in trades)),
        "actual_price_pnl_usd": clean_float(
            sum(float(row["price_pnl_usd"]) for row in trades)
        ),
        "total_rollover_boundaries": sum(
            int(row["rollover_boundaries"]) for row in trades
        ),
        "median_held_h4_bars": clean_float(
            float(np.median([int(row["held_h4_bars"]) for row in trades]))
            if trades
            else 0.0
        ),
    }


def simulate_variant(
    variant: str,
    frames: dict[str, pd.DataFrame],
    specs: dict[str, dict[str, Any]],
    features: dict[str, dict[str, np.ndarray]],
    signals: list[dict[str, Any]],
    active_dates: set[date],
    opportunities: dict[str, int],
    period_start: pd.Timestamp,
    period_end: pd.Timestamp,
    initial_actual_balance: float = INITIAL_DEPOSIT,
    initial_stressed_balance: float = INITIAL_DEPOSIT,
    initial_actual_peak: float | None = None,
    initial_maximum_drawdown_usd: float = 0.0,
    initial_maximum_drawdown_pct: float = 0.0,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    actual_balance = float(initial_actual_balance)
    stressed_balance = float(initial_stressed_balance)
    actual_peak = max(
        actual_balance,
        float(initial_actual_peak)
        if initial_actual_peak is not None
        else actual_balance,
    )
    maximum_drawdown_usd = float(initial_maximum_drawdown_usd)
    maximum_drawdown_pct = float(initial_maximum_drawdown_pct)
    open_positions: dict[str, dict[str, Any]] = {}
    states: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    trade_sequence = 0

    signals_by_time: dict[pd.Timestamp, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for signal_sequence, signal in enumerate(signals, start=1):
        signals_by_time[pd.Timestamp(signal["entry_time_utc"])].append(
            (signal_sequence, signal)
        )

    bars_by_time: dict[pd.Timestamp, dict[str, int]] = defaultdict(dict)
    for symbol in SYMBOLS:
        frame = frames[symbol]
        period_rows = frame.loc[
            (frame["time_utc"] >= period_start) & (frame["time_utc"] < period_end)
        ]
        for index, timestamp in zip(period_rows.index, period_rows["time_utc"]):
            bars_by_time[pd.Timestamp(timestamp)][symbol] = int(index)

    def close_open(symbol: str, exit_index: int, reason: str) -> None:
        nonlocal actual_balance
        nonlocal stressed_balance
        nonlocal actual_peak
        nonlocal maximum_drawdown_usd
        nonlocal maximum_drawdown_pct
        position = open_positions.pop(symbol)
        trade = settle_position(
            position, frames[symbol], specs[symbol], exit_index, reason
        )
        trade["actual_balance_before_usd"] = clean_float(actual_balance)
        trade["stressed_balance_before_usd"] = clean_float(stressed_balance)
        actual_balance += float(trade["actual_pnl_usd"])
        stressed_balance += float(trade["stressed_pnl_usd"])
        trade["actual_balance_after_usd"] = clean_float(actual_balance)
        trade["stressed_balance_after_usd"] = clean_float(stressed_balance)
        actual_peak = max(actual_peak, actual_balance)
        drawdown_usd = actual_peak - actual_balance
        drawdown_pct = (
            drawdown_usd / actual_peak * 100.0 if actual_peak > 0.0 else math.inf
        )
        if not math.isfinite(drawdown_pct):
            raise RuntimeError("nonfinite closed-balance drawdown")
        maximum_drawdown_usd = max(maximum_drawdown_usd, drawdown_usd)
        maximum_drawdown_pct = max(maximum_drawdown_pct, drawdown_pct)
        trade["actual_peak_after_usd"] = clean_float(actual_peak)
        trade["actual_drawdown_after_usd"] = clean_float(drawdown_usd)
        trade["actual_drawdown_after_pct"] = clean_float(drawdown_pct)
        state = states[int(position["state_row_index"])]
        state["exit_reason"] = reason
        state["exit_time_utc"] = trade["exit_time_utc"]
        state["realized_actual_r"] = trade["actual_r"]
        state["realized_stressed_r"] = trade["stressed_r"]
        trades.append(trade)

    for timestamp in sorted(bars_by_time):
        current_bars = bars_by_time[timestamp]

        # 1. Previously scheduled open exits settle first in frozen symbol order.
        for symbol in SYMBOLS:
            index = current_bars.get(symbol)
            position = open_positions.get(symbol)
            if (
                index is not None
                and position is not None
                and position.get("scheduled_exit_index") == index
            ):
                close_open(symbol, index, "CHANNEL_EXIT")

        # 2. One post-open-exit balance and reservation snapshot governs this time.
        balance_snapshot = actual_balance
        aggregate_cap = AGGREGATE_RISK_CAP_FRACTION * balance_snapshot
        reservation = sum(
            float(position["planned_stop_loss_usd"])
            for position in open_positions.values()
        )

        # 3. Entries are already ordered by excess then frozen symbol order.
        for same_time_rank, (signal_sequence, signal) in enumerate(
            signals_by_time.get(timestamp, []), start=1
        ):
            symbol = str(signal["symbol"])
            state = base_state_row(signal, signal_sequence)
            state["same_timestamp_rank"] = same_time_rank
            state["actual_balance_snapshot_usd"] = clean_float(balance_snapshot)
            state["reservation_before_usd"] = clean_float(reservation)
            state["aggregate_cap_usd"] = clean_float(aggregate_cap)
            states.append(state)
            state_index = len(states) - 1
            if symbol in open_positions:
                state["admission_status"] = "BLOCKED"
                state["block_reason"] = "ALREADY_OPEN"
                continue
            volume, planned_loss, block_reason = volume_for_signal(
                signal, specs[symbol], balance_snapshot
            )
            state["volume"] = clean_float(volume)
            state["planned_stop_loss_usd"] = clean_float(planned_loss)
            if block_reason is not None:
                state["admission_status"] = "BLOCKED"
                state["block_reason"] = block_reason
                continue
            if planned_loss > MINIMUM_LOT_CAP_FRACTION * balance_snapshot + 1e-9:
                raise RuntimeError("accepted position exceeded minimum-lot hard cap")
            if reservation + planned_loss > aggregate_cap + 1e-9:
                state["admission_status"] = "BLOCKED"
                state["block_reason"] = "AGGREGATE_INITIAL_STOP_RISK"
                continue
            reservation += planned_loss
            trade_sequence += 1
            state["admission_status"] = "ACCEPTED"
            state["trade_sequence"] = trade_sequence
            entry_spread_price = float(signal["entry_spread_points"]) * float(
                specs[symbol]["point"]
            )
            entry_price = (
                float(signal["entry_ask"])
                if signal["direction"] == "LONG"
                else float(signal["entry_bid"])
            )
            stop_price = (
                entry_price - float(signal["risk_distance"])
                if signal["direction"] == "LONG"
                else entry_price + float(signal["risk_distance"])
            )
            open_positions[symbol] = {
                **signal,
                "signal_sequence": signal_sequence,
                "trade_sequence": trade_sequence,
                "state_row_index": state_index,
                "volume": volume,
                "planned_stop_loss_usd": planned_loss,
                "entry_price": entry_price,
                "entry_spread_price": entry_spread_price,
                "stop_price": stop_price,
                "scheduled_exit_index": None,
            }

        # 4-6. Intrabar stop, maximum hold, then next-open channel scheduling.
        for symbol in SYMBOLS:
            index = current_bars.get(symbol)
            position = open_positions.get(symbol)
            if index is None or position is None:
                continue
            if index < int(position["entry_index"]):
                continue
            row = frames[symbol].iloc[index]
            spec = specs[symbol]
            if position["direction"] == "LONG":
                stop_hit = float(row["low"]) <= float(position["stop_price"])
            else:
                ask_high = float(row["high"]) + float(row["spread"]) * float(
                    spec["point"]
                )
                stop_hit = ask_high >= float(position["stop_price"])
            if stop_hit:
                close_open(symbol, index, "HARD_STOP")
                continue
            held_bars = index - int(position["entry_index"]) + 1
            if held_bars >= MAX_HOLD_BARS:
                close_open(symbol, index, "MAX_HOLD")
                continue
            feature = features[symbol]
            if position["direction"] == "LONG":
                channel_exit = float(row["close"]) < float(feature["exit_low"][index])
            else:
                channel_exit = float(row["close"]) > float(feature["exit_high"][index])
            if channel_exit:
                next_index = index + 1
                if next_index >= len(frames[symbol]):
                    raise RuntimeError("channel exit has no next observed bar")
                next_time = pd.Timestamp(frames[symbol]["time_utc"].iloc[next_index])
                if next_time >= period_end:
                    raise RuntimeError("channel exit would cross judged period")
                position["scheduled_exit_index"] = next_index

    if len(states) != len(signals):
        raise RuntimeError("signal/state cardinality mismatch")
    if open_positions:
        raise RuntimeError(f"unresolved mature positions: {sorted(open_positions)}")
    if len(trades) != trade_sequence:
        raise RuntimeError("accepted/trade cardinality mismatch")
    metrics = summarize_simulation(
        variant,
        states,
        trades,
        active_dates,
        opportunities,
        period_start,
        period_end,
        initial_actual_balance,
        initial_stressed_balance,
        actual_balance,
        stressed_balance,
        actual_peak,
        maximum_drawdown_usd,
        maximum_drawdown_pct,
    )
    return metrics, states, trades


def development_gates(metrics: dict[str, Any]) -> dict[str, bool]:
    epochs = metrics["epoch_metrics"]
    gates = {
        "both_2024_2025_actual_positive": all(
            float(epochs[str(year)]["actual_net_usd"]) > 0.0
            for year in (2024, 2025)
        ),
        "both_2024_2025_stressed_positive": all(
            float(epochs[str(year)]["stressed_net_usd"]) > 0.0
            for year in (2024, 2025)
        ),
        "development_actual_strictly_above_149_97": float(
            metrics["actual_net_usd"]
        )
        > DEVELOPMENT_ACTUAL_GATE,
        "development_stressed_strictly_above_127_786": float(
            metrics["stressed_net_usd"]
        )
        > DEVELOPMENT_STRESS_GATE,
        "actual_closed_balance_drawdown_at_most_37_39_pct": float(
            metrics["actual_closed_balance_drawdown_pct"]
        )
        <= DRAWDOWN_GATE_PCT,
        "accepted_starts_per_active_date_at_least_0_10": float(
            metrics["accepted_starts_per_portfolio_active_date"]
        )
        >= TURNOVER_GATE,
        "at_least_20_starts_in_each_development_year": all(
            int(epochs[str(year)]["starts"]) >= YEAR_START_GATE
            for year in (2024, 2025)
        ),
        "symbol_breadth_at_least_4": int(metrics["symbol_breadth"])
        >= BREADTH_SYMBOL_GATE,
        "both_asset_classes": set(metrics["asset_class_breadth"])
        == {"currency", "equity_index"},
        "both_directions": set(metrics["direction_breadth"])
        == {"LONG", "SHORT"},
    }
    gates["passed"] = all(gates.values())
    return gates


def ranked_development_passers(
    candidate_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    passers = [row for row in candidate_results if row["gates"]["passed"]]
    passers.sort(
        key=lambda row: (
            -float(row["stressed_net_usd"]),
            float(row["actual_closed_balance_drawdown_pct"]),
            -min(
                float(row["epoch_metrics"][str(year)]["stressed_net_usd"])
                for year in (2024, 2025)
            ),
            VARIANT_ORDER.index(str(row["variant"])),
        )
    )
    return passers


def improvement_path_rows(
    frames: dict[str, pd.DataFrame],
    specs: dict[str, dict[str, Any]],
    signals_by_variant: dict[str, list[dict[str, Any]]],
    states_by_variant: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    horizons = (1, 3, 6, 12)
    output: list[dict[str, Any]] = []
    for variant in VARIANT_ORDER:
        state_by_id = {
            str(row["signal_id"]): row for row in states_by_variant[variant]
        }
        for signal_sequence, signal in enumerate(
            signals_by_variant[variant], start=1
        ):
            symbol = str(signal["symbol"])
            direction = str(signal["direction"])
            frame = frames[symbol]
            spec = specs[symbol]
            entry_index = int(signal["entry_index"])
            entry_bid = float(signal["entry_bid"])
            entry_price = (
                float(signal["entry_ask"])
                if direction == "LONG"
                else entry_bid
            )
            risk_distance = float(signal["risk_distance"])
            risk_per_lot = float(signal["risk_per_lot"])
            state = state_by_id[str(signal["signal_id"])]
            for horizon in horizons:
                exit_index = entry_index + horizon - 1
                path = frame.iloc[entry_index : exit_index + 1]
                if len(path) != horizon:
                    raise RuntimeError("incomplete improvement path despite maturation")
                exit_row = frame.iloc[exit_index]
                exit_spread_price = float(exit_row["spread"]) * float(spec["point"])
                exit_bid = float(exit_row["close"])
                exit_price = exit_bid if direction == "LONG" else exit_bid + exit_spread_price
                if direction == "LONG":
                    gross_directional_price = exit_bid - entry_bid
                    actual_directional_price = exit_price - entry_price
                    stress_spread_price = float(signal["entry_spread_points"]) * float(
                        spec["point"]
                    )
                    mfe = (float(path["high"].max()) - entry_bid) / risk_distance
                    mae = (entry_bid - float(path["low"].min())) / risk_distance
                else:
                    gross_directional_price = entry_bid - exit_bid
                    actual_directional_price = entry_price - exit_price
                    stress_spread_price = exit_spread_price
                    mfe = (entry_bid - float(path["low"].min())) / risk_distance
                    mae = (float(path["high"].max()) - entry_bid) / risk_distance
                gross = money_from_directional_price(
                    gross_directional_price, spec, 1.0
                )
                price_pnl = money_from_directional_price(
                    actual_directional_price, spec, 1.0
                )
                exit_server_time = pd.Timestamp(exit_row["server_time"]) + pd.Timedelta(
                    hours=4
                )
                swap, rollover_count, rollover_multiplier_days = swap_money(
                    spec,
                    frame,
                    direction,
                    1.0,
                    pd.Timestamp(signal["entry_server_time"]),
                    exit_server_time,
                    entry_price,
                )
                observed_spread = spread_burden_money(
                    stress_spread_price, spec, 1.0
                )
                actual = price_pnl + swap
                stressed = actual - observed_spread
                output.append(
                    {
                        "variant": variant,
                        "signal_sequence": signal_sequence,
                        "signal_id": signal["signal_id"],
                        "symbol": symbol,
                        "asset_class": signal["asset_class"],
                        "direction": direction,
                        "entry_time_utc": iso_utc(signal["entry_time_utc"]),
                        "entry_year": int(pd.Timestamp(signal["entry_time_utc"]).year),
                        "horizon_h4_bars": horizon,
                        "horizon_exit_time_utc": iso_utc(
                            pd.Timestamp(exit_row["time_utc"]) + pd.Timedelta(hours=4)
                        ),
                        "admission_status": state["admission_status"],
                        "block_reason": state["block_reason"],
                        "realized_exit_reason": state["exit_reason"],
                        "risk_distance": clean_float(risk_distance),
                        "gross_movement_per_lot_usd": clean_float(gross),
                        "observed_spread_burden_per_lot_usd": clean_float(
                            observed_spread
                        ),
                        "swap_per_lot_usd": clean_float(swap),
                        "rollover_boundaries": rollover_count,
                        "rollover_multiplier_days": rollover_multiplier_days,
                        "raw_gross_close_r": clean_float(gross / risk_per_lot),
                        "actual_close_r": clean_float(actual / risk_per_lot),
                        "stressed_close_r": clean_float(stressed / risk_per_lot),
                        "mfe_r": clean_float(max(0.0, mfe)),
                        "mae_r": clean_float(max(0.0, mae)),
                    }
                )
    return output


def path_group_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "count": 0,
            "mean_raw_gross_close_r": 0.0,
            "mean_actual_close_r": 0.0,
            "mean_stressed_close_r": 0.0,
            "mean_mfe_r": 0.0,
            "mean_mae_r": 0.0,
            "stressed_positive_fraction": 0.0,
        }
    return {
        "count": len(rows),
        "mean_raw_gross_close_r": clean_float(
            np.mean([float(row["raw_gross_close_r"]) for row in rows])
        ),
        "mean_actual_close_r": clean_float(
            np.mean([float(row["actual_close_r"]) for row in rows])
        ),
        "mean_stressed_close_r": clean_float(
            np.mean([float(row["stressed_close_r"]) for row in rows])
        ),
        "mean_mfe_r": clean_float(np.mean([float(row["mfe_r"]) for row in rows])),
        "mean_mae_r": clean_float(np.mean([float(row["mae_r"]) for row in rows])),
        "stressed_positive_fraction": clean_float(
            np.mean([float(row["stressed_close_r"]) > 0.0 for row in rows])
        ),
    }


def grouped_path_summaries(
    rows: list[dict[str, Any]], field: str, order: Iterable[object]
) -> dict[str, Any]:
    return {
        str(value): path_group_summary(
            [row for row in rows if row[field] == value]
        )
        for value in order
    }


def broad_headroom(
    rows: list[dict[str, Any]], variant: str
) -> dict[str, Any]:
    selected = [
        row
        for row in rows
        if row["variant"] == variant and int(row["horizon_h4_bars"]) == 12
    ]

    def qualifies(group: list[dict[str, Any]]) -> bool:
        summary = path_group_summary(group)
        return (
            int(summary["count"]) >= BROAD_SLICE_MIN
            and float(summary["mean_raw_gross_close_r"]) > 0.0
            and float(summary["mean_stressed_close_r"]) > 0.0
        )

    year = {
        str(value): qualifies([row for row in selected if row["entry_year"] == value])
        for value in (2024, 2025)
    }
    asset_class = {
        value: qualifies([row for row in selected if row["asset_class"] == value])
        for value in ("currency", "equity_index")
    }
    direction = {
        value: qualifies([row for row in selected if row["direction"] == value])
        for value in ("LONG", "SHORT")
    }
    symbol = {
        value: qualifies([row for row in selected if row["symbol"] == value])
        for value in SYMBOLS
    }
    qualifying_symbols = [value for value in SYMBOLS if symbol[value]]
    passed = (
        all(year.values())
        and all(asset_class.values())
        and all(direction.values())
        and len(qualifying_symbols) >= BREADTH_SYMBOL_GATE
    )
    return {
        "rule": (
            "12-H4 raw-gross and stressed mean R must both be positive with at "
            "least 10 signals in both years, both asset classes, both directions "
            "and at least four individual symbols"
        ),
        "year": year,
        "asset_class": asset_class,
        "direction": direction,
        "symbol": symbol,
        "qualifying_symbols": qualifying_symbols,
        "passed": passed,
    }


def build_improvement_audit(
    path_rows: list[dict[str, Any]],
    signals_by_variant: dict[str, list[dict[str, Any]]],
    states_by_variant: dict[str, list[dict[str, Any]]],
    trades_by_variant: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    variants: dict[str, Any] = {}
    headroom_results: dict[str, dict[str, Any]] = {}
    for variant in VARIANT_ORDER:
        variant_paths = [row for row in path_rows if row["variant"] == variant]
        states = states_by_variant[variant]
        trades = trades_by_variant[variant]
        horizons: dict[str, Any] = {}
        for horizon in (1, 3, 6, 12):
            rows = [
                row
                for row in variant_paths
                if int(row["horizon_h4_bars"]) == horizon
            ]
            horizons[str(horizon)] = {
                "overall": path_group_summary(rows),
                "by_entry_year": grouped_path_summaries(
                    rows, "entry_year", (2024, 2025)
                ),
                "by_symbol": grouped_path_summaries(rows, "symbol", SYMBOLS),
                "by_asset_class": grouped_path_summaries(
                    rows, "asset_class", ("currency", "equity_index")
                ),
                "by_direction": grouped_path_summaries(
                    rows, "direction", ("LONG", "SHORT")
                ),
            }
        headroom_results[variant] = broad_headroom(path_rows, variant)
        variants[variant] = {
            "signals": len(signals_by_variant[variant]),
            "admission_counts": dict(
                sorted(Counter(str(row["admission_status"]) for row in states).items())
            ),
            "block_counts": dict(
                sorted(
                    Counter(
                        str(row["block_reason"])
                        for row in states
                        if row["admission_status"] == "BLOCKED"
                    ).items()
                )
            ),
            "exit_counts": dict(
                sorted(Counter(str(row["exit_reason"]) for row in trades).items())
            ),
            "realized_actual_r_mean": clean_float(
                np.mean([float(row["actual_r"]) for row in trades])
                if trades
                else 0.0
            ),
            "realized_stressed_r_mean": clean_float(
                np.mean([float(row["stressed_r"]) for row in trades])
                if trades
                else 0.0
            ),
            "gross_movement_usd": clean_float(
                sum(float(row["gross_movement_usd"]) for row in trades)
            ),
            "observed_spread_burden_usd": clean_float(
                sum(float(row["observed_spread_burden_usd"]) for row in trades)
            ),
            "swap_usd": clean_float(sum(float(row["swap_usd"]) for row in trades)),
            "horizon_paths": horizons,
            "broad_headroom_12h": headroom_results[variant],
        }

    signal_sets = {
        variant: {
            (str(row["symbol"]), int(row["entry_raw_time"]), str(row["direction"]))
            for row in signals_by_variant[variant]
        }
        for variant in VARIANT_ORDER
    }
    first, second = VARIANT_ORDER
    overlap = signal_sets[first] & signal_sets[second]
    family_headroom = any(row["passed"] for row in headroom_results.values())
    best_variant = max(
        VARIANT_ORDER,
        key=lambda value: float(
            variants[value]["horizon_paths"]["12"]["overall"][
                "mean_stressed_close_r"
            ]
        ),
    )
    return {
        "schema": (
            "zeta-next-independent-multi-asset-h4-donchian-trend-adapter-"
            "challenge-v1-development-improvement-audit"
        ),
        "family": FAMILY,
        "status": "COMPLETE_SAME_PROCESS_IMPROVEMENT_POTENTIAL_AUDIT",
        "path_horizons_h4": [1, 3, 6, 12],
        "path_rows": len(path_rows),
        "variant_signal_overlap": {
            "shared": len(overlap),
            f"unique_{first}": len(signal_sets[first] - overlap),
            f"unique_{second}": len(signal_sets[second] - overlap),
        },
        "variants": variants,
        "family_broad_causal_improvement_headroom": family_headroom,
        "bounded_successor_seed": (
            {
                "status": "RETAINED_ONLY_RECOMPARE_REQUIRED",
                "basis": "strongest frozen 12-H4 mean stressed path",
                "variant": best_variant,
            }
            if family_headroom
            else None
        ),
        "adjacent_rescue_executed": False,
    }


def dataframe_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    frame = pd.DataFrame(rows)
    return frame.to_csv(
        index=False,
        lineterminator="\n",
        float_format="%.12f",
        quoting=csv.QUOTE_MINIMAL,
    ).encode("utf-8")


def json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")


def byte_authority(
    path: Path, content: bytes, rows: int | None = None
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path).replace("\\", "/"),
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest().upper(),
    }
    if rows is not None:
        result["rows"] = rows
    return result


def atomic_write_outputs(outputs: list[tuple[Path, bytes]]) -> None:
    existing = [str(path) for path, _ in outputs if path.exists()]
    if existing:
        raise RuntimeError(f"refusing to overwrite output artifacts: {existing}")
    if not outputs:
        return
    output_parent = outputs[0][0].parent
    output_parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix="zeta-f009-adapter-", dir=output_parent.parent)
    )
    try:
        staged: list[tuple[Path, Path]] = []
        for index, (destination, content) in enumerate(outputs):
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = staging / f"{index:02d}-{destination.name}"
            temporary.write_bytes(content)
            staged.append((temporary, destination))
        for temporary, destination in staged:
            os.replace(temporary, destination)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def output_paths(workspace: Path) -> dict[str, Path]:
    root = workspace / "lab" / "artifacts" / "raw" / FAMILY / "output"
    return {
        "development_result": root / "development-result.json",
        "development_audit": root / "development-audit.json",
        "development_states": root / "development-states.csv",
        "development_trades": root / "development-trades.csv",
        "development_audit_paths": root / "development-audit-paths.csv",
        "confirmation_result": root / "confirmation-result.json",
        "confirmation_states": root / "confirmation-states.csv",
        "confirmation_trades": root / "confirmation-trades.csv",
        "native_decisions": root / "native-decisions.csv",
    }


def output_record(
    workspace: Path, path: Path, content: bytes, rows: int | None = None
) -> dict[str, Any]:
    return byte_authority(
        Path(rel(path, workspace)), content, rows
    )


def run_precheck(
    workspace: Path, script_path: Path, outputs: dict[str, Path]
) -> int:
    authorities = verify_authorities(workspace)
    if any(path.exists() for path in outputs.values()):
        raise RuntimeError("precheck requires an empty family output surface")
    frames, specs, _ = load_development_sources(workspace)
    result = precheck(frames, specs, authorities)
    result["schema"] = (
        "zeta-next-independent-multi-asset-h4-donchian-trend-adapter-"
        "challenge-v1-precheck"
    )
    result["adapter"] = authority_record(script_path, workspace)
    result["broker_account_position_order_or_deal_queries"] = 0
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False), flush=True)
    return 0


def run_development(
    workspace: Path,
    family_root: Path,
    script_path: Path,
    outputs: dict[str, Path],
) -> int:
    authorities = verify_authorities(workspace)
    freeze_path = (
        family_root
        / "evidence"
        / "INDEPENDENT_MULTI_ASSET_H4_DONCHIAN_TREND_ADAPTER_CHALLENGE_V1_IMPLEMENTATION_FREEZE.json"
    )
    freeze = verify_freeze(freeze_path, script_path, workspace)
    authorities["implementation_freeze"] = authority_record(freeze_path, workspace)
    development_outputs = [
        outputs["development_result"],
        outputs["development_audit"],
        outputs["development_states"],
        outputs["development_trades"],
        outputs["development_audit_paths"],
    ]
    if any(path.exists() for path in development_outputs):
        raise RuntimeError("development output surface is not empty")
    frames, specs, source_receipt = load_development_sources(workspace)
    features, signals, active_dates, opportunities = signal_surface(
        frames, specs, DEVELOPMENT_START, DEVELOPMENT_END
    )
    candidate_results: list[dict[str, Any]] = []
    states_by_variant: dict[str, list[dict[str, Any]]] = {}
    trades_by_variant: dict[str, list[dict[str, Any]]] = {}
    for variant in VARIANT_ORDER:
        metrics, states, trades = simulate_variant(
            variant,
            frames,
            specs,
            features[variant],
            signals[variant],
            active_dates[variant],
            opportunities[variant],
            DEVELOPMENT_START,
            DEVELOPMENT_END,
        )
        metrics["gates"] = development_gates(metrics)
        candidate_results.append(metrics)
        states_by_variant[variant] = states
        trades_by_variant[variant] = trades

    path_rows = improvement_path_rows(
        frames, specs, signals, states_by_variant
    )
    audit = build_improvement_audit(
        path_rows, signals, states_by_variant, trades_by_variant
    )
    audit["recorded_at_utc"] = datetime.now(tz=UTC).isoformat().replace(
        "+00:00", "Z"
    )
    audit["adapter"] = authority_record(script_path, workspace)
    audit["implementation_freeze"] = authorities["implementation_freeze"]
    audit["broker_account_position_order_or_deal_queries"] = 0
    audit["locked_2026_rows_loaded"] = 0

    all_states = [
        row for variant in VARIANT_ORDER for row in states_by_variant[variant]
    ]
    all_trades = [
        row for variant in VARIANT_ORDER for row in trades_by_variant[variant]
    ]
    states_content = dataframe_csv_bytes(all_states)
    trades_content = dataframe_csv_bytes(all_trades)
    paths_content = dataframe_csv_bytes(path_rows)
    audit_content = json_bytes(audit)
    passers = ranked_development_passers(candidate_results)
    selected_variant = str(passers[0]["variant"]) if passers else None
    broad = bool(audit["family_broad_causal_improvement_headroom"])
    status = (
        "VALID_DEVELOPMENT_COMPLETE_ONE_SELECTED_PASSER"
        if selected_variant is not None
        else (
            "VALID_DEVELOPMENT_COMPLETE_NO_PASSER_BROAD_HEADROOM"
            if broad
            else "VALID_DEVELOPMENT_COMPLETE_NO_PASSER_NO_BROAD_HEADROOM"
        )
    )
    result = {
        "schema": (
            "zeta-next-independent-multi-asset-h4-donchian-trend-adapter-"
            "challenge-v1-development-result"
        ),
        "recorded_at_utc": datetime.now(tz=UTC).isoformat().replace(
            "+00:00", "Z"
        ),
        "status": status,
        "family": FAMILY,
        "period": "2024-01-01T00:00:00Z/2026-01-01T00:00:00Z",
        "authorities": authorities,
        "source_receipt_status": source_receipt["status"],
        "adapter": authority_record(script_path, workspace),
        "implementation_freeze_status": freeze["status"],
        "candidate_results": candidate_results,
        "complete_passer_count": len(passers),
        "selected_variant": selected_variant,
        "family_broad_causal_improvement_headroom": broad,
        "bounded_successor_seed": audit["bounded_successor_seed"],
        "raw_outputs": {
            "states": output_record(
                workspace,
                outputs["development_states"],
                states_content,
                len(all_states),
            ),
            "trades": output_record(
                workspace,
                outputs["development_trades"],
                trades_content,
                len(all_trades),
            ),
            "audit_paths": output_record(
                workspace,
                outputs["development_audit_paths"],
                paths_content,
                len(path_rows),
            ),
            "audit": output_record(
                workspace, outputs["development_audit"], audit_content
            ),
        },
        "locked_2026_rows_loaded": 0,
        "ea_source_files": 0,
        "mt5_compile_or_tester_paths": 0,
        "broker_account_position_order_or_deal_queries": 0,
        "proxy_victory_claimed": False,
    }
    result_content = json_bytes(result)
    atomic_write_outputs(
        [
            (outputs["development_states"], states_content),
            (outputs["development_trades"], trades_content),
            (outputs["development_audit_paths"], paths_content),
            (outputs["development_audit"], audit_content),
            (outputs["development_result"], result_content),
        ]
    )
    print(
        json.dumps(
            {
                "status": status,
                "complete_passer_count": len(passers),
                "selected_variant": selected_variant,
                "family_broad_causal_improvement_headroom": broad,
                "candidate_results": candidate_results,
                "raw_outputs": result["raw_outputs"],
            },
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        ),
        flush=True,
    )
    return 0


def combine_counts(first: dict[str, Any], second: dict[str, Any]) -> dict[str, int]:
    keys = sorted(set(first) | set(second))
    return {key: int(first.get(key, 0)) + int(second.get(key, 0)) for key in keys}


def combine_whole_metrics(
    development: dict[str, Any], locked: dict[str, Any]
) -> dict[str, Any]:
    epochs = {
        **development["epoch_metrics"],
        **locked["epoch_metrics"],
    }
    accepted = int(development["accepted_starts"]) + int(locked["accepted_starts"])
    active_dates = int(development["portfolio_active_dates"]) + int(
        locked["portfolio_active_dates"]
    )
    ending_actual = float(locked["ending_actual_balance_usd"])
    ending_stressed = float(locked["ending_stressed_balance_usd"])
    stressed_net = ending_stressed - INITIAL_DEPOSIT
    maximum_drawdown = float(locked["actual_closed_balance_drawdown_usd"])
    recovery_unbounded = maximum_drawdown == 0.0 and stressed_net > 0.0
    opportunities = {
        symbol: int(
            development["mature_decision_opportunities_by_symbol"].get(symbol, 0)
        )
        + int(locked["mature_decision_opportunities_by_symbol"].get(symbol, 0))
        for symbol in SYMBOLS
    }
    symbols = sorted(
        set(development["accepted_symbols"]) | set(locked["accepted_symbols"]),
        key=SYMBOL_ORDER.get,
    )
    asset_classes = sorted(
        set(development["asset_class_breadth"])
        | set(locked["asset_class_breadth"])
    )
    directions = sorted(
        set(development["direction_breadth"]) | set(locked["direction_breadth"])
    )
    return {
        "variant": development["variant"],
        "period": "2024-01-01T00:00:00Z/2026-08-01T00:00:00Z",
        "signal_count": int(development["signal_count"])
        + int(locked["signal_count"]),
        "accepted_starts": accepted,
        "blocked_signals": int(development["blocked_signals"])
        + int(locked["blocked_signals"]),
        "block_counts": combine_counts(
            development["block_counts"], locked["block_counts"]
        ),
        "exit_counts": combine_counts(
            development["exit_counts"], locked["exit_counts"]
        ),
        "portfolio_active_dates": active_dates,
        "accepted_starts_per_portfolio_active_date": clean_float(
            accepted / active_dates if active_dates else 0.0
        ),
        "mature_decision_opportunities_by_symbol": opportunities,
        "mature_decision_opportunities_total": sum(opportunities.values()),
        "initial_actual_balance_usd": INITIAL_DEPOSIT,
        "initial_stressed_balance_usd": INITIAL_DEPOSIT,
        "actual_net_usd": clean_float(ending_actual - INITIAL_DEPOSIT),
        "stressed_net_usd": clean_float(ending_stressed - INITIAL_DEPOSIT),
        "ending_actual_balance_usd": clean_float(ending_actual),
        "ending_stressed_balance_usd": clean_float(ending_stressed),
        "actual_closed_balance_peak_usd": locked[
            "actual_closed_balance_peak_usd"
        ],
        "actual_closed_balance_drawdown_usd": clean_float(maximum_drawdown),
        "actual_closed_balance_drawdown_pct": locked[
            "actual_closed_balance_drawdown_pct"
        ],
        "robust_recovery": (
            clean_float(stressed_net / maximum_drawdown)
            if maximum_drawdown > 0.0
            else None
        ),
        "robust_recovery_unbounded_positive": recovery_unbounded,
        "epoch_metrics": epochs,
        "symbol_breadth": len(symbols),
        "accepted_symbols": symbols,
        "asset_class_breadth": asset_classes,
        "direction_breadth": directions,
        "gross_movement_usd": clean_float(
            float(development["gross_movement_usd"])
            + float(locked["gross_movement_usd"])
        ),
        "observed_spread_burden_usd": clean_float(
            float(development["observed_spread_burden_usd"])
            + float(locked["observed_spread_burden_usd"])
        ),
        "swap_usd": clean_float(
            float(development["swap_usd"]) + float(locked["swap_usd"])
        ),
        "actual_price_pnl_usd": clean_float(
            float(development["actual_price_pnl_usd"])
            + float(locked["actual_price_pnl_usd"])
        ),
        "total_rollover_boundaries": int(
            development["total_rollover_boundaries"]
        )
        + int(locked["total_rollover_boundaries"]),
    }


def whole_gates(
    whole: dict[str, Any], locked: dict[str, Any]
) -> dict[str, bool]:
    epochs = whole["epoch_metrics"]
    gates = {
        "locked_2026_actual_positive": float(locked["actual_net_usd"]) > 0.0,
        "locked_2026_stressed_positive": float(locked["stressed_net_usd"]) > 0.0,
        "each_2024_2025_locked_2026_actual_positive": all(
            float(epochs[str(year)]["actual_net_usd"]) > 0.0
            for year in (2024, 2025, 2026)
        ),
        "each_2024_2025_locked_2026_stressed_positive": all(
            float(epochs[str(year)]["stressed_net_usd"]) > 0.0
            for year in (2024, 2025, 2026)
        ),
        "whole_actual_strictly_above_409_81": float(whole["actual_net_usd"])
        > WHOLE_ACTUAL_GATE,
        "whole_stressed_strictly_above_367_818": float(
            whole["stressed_net_usd"]
        )
        > WHOLE_STRESS_GATE,
        "actual_closed_balance_drawdown_at_most_37_39_pct": float(
            whole["actual_closed_balance_drawdown_pct"]
        )
        <= DRAWDOWN_GATE_PCT,
        "robust_recovery_strictly_above_3_295860215": bool(
            whole["robust_recovery_unbounded_positive"]
        )
        or (
            whole["robust_recovery"] is not None
            and float(whole["robust_recovery"]) > ROBUST_RECOVERY_GATE
        ),
        "accepted_starts_per_active_date_at_least_0_10": float(
            whole["accepted_starts_per_portfolio_active_date"]
        )
        >= TURNOVER_GATE,
        "at_least_20_starts_in_each_epoch": all(
            int(epochs[str(year)]["starts"]) >= YEAR_START_GATE
            for year in (2024, 2025, 2026)
        ),
        "symbol_breadth_at_least_4": int(whole["symbol_breadth"])
        >= BREADTH_SYMBOL_GATE,
        "both_asset_classes": set(whole["asset_class_breadth"])
        == {"currency", "equity_index"},
        "both_directions": set(whole["direction_breadth"])
        == {"LONG", "SHORT"},
    }
    gates["passed"] = all(gates.values())
    return gates


def verify_recorded_output(workspace: Path, record: dict[str, Any]) -> Path:
    path = workspace / str(record["path"])
    if not path.is_file():
        raise RuntimeError(f"recorded development output missing: {path}")
    if (
        path.stat().st_size != int(record["bytes"])
        or sha256(path) != str(record["sha256"])
    ):
        raise RuntimeError(f"recorded development output mismatch: {path}")
    return path


def native_decision_rows(
    selected_variant: str,
    development_states_path: Path,
    locked_states: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    development_frame = pd.read_csv(development_states_path, keep_default_na=False)
    development_rows = development_frame.loc[
        development_frame["variant"] == selected_variant
    ].to_dict(orient="records")
    combined = development_rows + locked_states
    combined.sort(
        key=lambda row: (
            int(row["entry_raw_time"]),
            int(row["same_timestamp_rank"]),
            SYMBOL_ORDER[str(row["symbol"])],
        )
    )
    return [
        {
            "sequence": sequence,
            "variant": selected_variant,
            "signal_id": row["signal_id"],
            "decision_bar_raw_time": int(row["decision_bar_raw_time"]),
            "entry_raw_time": int(row["entry_raw_time"]),
            "entry_time_utc": row["entry_time_utc"],
            "same_timestamp_rank": int(row["same_timestamp_rank"]),
            "symbol": row["symbol"],
            "direction": row["direction"],
            "normalized_breakout_excess": float(
                row["normalized_breakout_excess"]
            ),
            "atr20": float(row["atr20"]),
            "risk_distance": float(row["risk_distance"]),
            "adapter_proxy_admission_status": row["admission_status"],
            "adapter_proxy_block_reason": row["block_reason"],
        }
        for sequence, row in enumerate(combined, start=1)
    ]


def run_confirmation(
    workspace: Path,
    family_root: Path,
    script_path: Path,
    outputs: dict[str, Path],
) -> int:
    authorities = verify_authorities(workspace)
    freeze_path = (
        family_root
        / "evidence"
        / "INDEPENDENT_MULTI_ASSET_H4_DONCHIAN_TREND_ADAPTER_CHALLENGE_V1_IMPLEMENTATION_FREEZE.json"
    )
    verify_freeze(freeze_path, script_path, workspace)
    authorities["implementation_freeze"] = authority_record(freeze_path, workspace)
    durable_result_path = (
        family_root
        / "evidence"
        / "INDEPENDENT_MULTI_ASSET_H4_DONCHIAN_TREND_ADAPTER_CHALLENGE_V1_DEVELOPMENT_RESULT.json"
    )
    raw_result_path = outputs["development_result"]
    if not raw_result_path.is_file() or not durable_result_path.is_file():
        raise RuntimeError("confirmation requires raw and durable development result")
    if sha256(raw_result_path) != sha256(durable_result_path):
        raise RuntimeError("raw and durable development results are not byte-identical")
    development_result = read_json(raw_result_path)
    if development_result.get("status") != (
        "VALID_DEVELOPMENT_COMPLETE_ONE_SELECTED_PASSER"
    ):
        raise RuntimeError("confirmation requires a selected development passer")
    selected_variant = str(development_result.get("selected_variant"))
    candidates = development_result.get("candidate_results")
    if (
        selected_variant not in VARIANT_ORDER
        or not isinstance(candidates, list)
        or [row.get("variant") for row in candidates] != list(VARIANT_ORDER)
    ):
        raise RuntimeError("development selection bundle is malformed")
    ranked = ranked_development_passers(candidates)
    if (
        not ranked
        or ranked[0]["variant"] != selected_variant
        or len(ranked) != int(development_result["complete_passer_count"])
    ):
        raise RuntimeError("development selection does not reproduce")
    recorded_adapter = development_result.get("adapter", {})
    observed_adapter = authority_record(script_path, workspace)
    if recorded_adapter != observed_adapter:
        raise RuntimeError("development result adapter identity changed")
    development_output_records = development_result["raw_outputs"]
    development_states_path = verify_recorded_output(
        workspace, development_output_records["states"]
    )
    for name in ("trades", "audit_paths", "audit"):
        verify_recorded_output(workspace, development_output_records[name])

    confirmation_outputs = [
        outputs["confirmation_result"],
        outputs["confirmation_states"],
        outputs["confirmation_trades"],
        outputs["native_decisions"],
    ]
    if any(path.exists() for path in confirmation_outputs):
        raise RuntimeError("confirmation output surface is not empty")
    frames, specs, complete_receipt = load_complete_sources(workspace)
    complete_receipt_path = (
        workspace
        / "lab"
        / "artifacts"
        / "raw"
        / FAMILY
        / "input"
        / "COMPLETE_ACQUISITION_RECEIPT.json"
    )
    authorities["complete_source_receipt"] = authority_record(
        complete_receipt_path, workspace
    )
    features, signals, active_dates, opportunities = signal_surface(
        frames, specs, LOCKED_START, LOCKED_END
    )
    development_metrics = next(
        row for row in candidates if row["variant"] == selected_variant
    )
    locked_metrics, locked_states, locked_trades = simulate_variant(
        selected_variant,
        frames,
        specs,
        features[selected_variant],
        signals[selected_variant],
        active_dates[selected_variant],
        opportunities[selected_variant],
        LOCKED_START,
        LOCKED_END,
        initial_actual_balance=float(
            development_metrics["ending_actual_balance_usd"]
        ),
        initial_stressed_balance=float(
            development_metrics["ending_stressed_balance_usd"]
        ),
        initial_actual_peak=float(
            development_metrics["actual_closed_balance_peak_usd"]
        ),
        initial_maximum_drawdown_usd=float(
            development_metrics["actual_closed_balance_drawdown_usd"]
        ),
        initial_maximum_drawdown_pct=float(
            development_metrics["actual_closed_balance_drawdown_pct"]
        ),
    )
    whole = combine_whole_metrics(development_metrics, locked_metrics)
    whole["gates"] = whole_gates(whole, locked_metrics)
    passed = bool(whole["gates"]["passed"])
    decisions = (
        native_decision_rows(
            selected_variant, development_states_path, locked_states
        )
        if passed
        else []
    )
    states_content = dataframe_csv_bytes(locked_states)
    trades_content = dataframe_csv_bytes(locked_trades)
    decision_content = dataframe_csv_bytes(decisions) if decisions else b""
    status = (
        "VALID_WHOLE_PROXY_PASS_NATIVE_ESCALATION_READY"
        if passed
        else "VALID_WHOLE_PROXY_NONCONFIRMATION"
    )
    result = {
        "schema": (
            "zeta-next-independent-multi-asset-h4-donchian-trend-adapter-"
            "challenge-v1-confirmation-result"
        ),
        "recorded_at_utc": datetime.now(tz=UTC).isoformat().replace(
            "+00:00", "Z"
        ),
        "status": status,
        "family": FAMILY,
        "selected_variant": selected_variant,
        "authorities": authorities,
        "complete_source_receipt_status": complete_receipt["status"],
        "adapter": observed_adapter,
        "locked_metrics": locked_metrics,
        "whole_metrics": whole,
        "native_decision_tape_written": bool(decisions),
        "raw_outputs": {
            "locked_states": output_record(
                workspace,
                outputs["confirmation_states"],
                states_content,
                len(locked_states),
            ),
            "locked_trades": output_record(
                workspace,
                outputs["confirmation_trades"],
                trades_content,
                len(locked_trades),
            ),
            "native_decisions": (
                output_record(
                    workspace,
                    outputs["native_decisions"],
                    decision_content,
                    len(decisions),
                )
                if decisions
                else None
            ),
        },
        "ea_source_files": 0,
        "mt5_compile_or_tester_paths": 0,
        "broker_account_position_order_or_deal_queries": 0,
        "proxy_victory_claimed": False,
    }
    result_content = json_bytes(result)
    writes = [
        (outputs["confirmation_states"], states_content),
        (outputs["confirmation_trades"], trades_content),
    ]
    if decisions:
        writes.append((outputs["native_decisions"], decision_content))
    writes.append((outputs["confirmation_result"], result_content))
    atomic_write_outputs(writes)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False), flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", required=True, choices=("precheck", "development", "confirmation")
    )
    args = parser.parse_args()
    script_path = Path(__file__).resolve()
    family_root = script_path.parent.parent
    workspace = family_root.parents[2]
    outputs = output_paths(workspace)
    if args.mode == "precheck":
        return run_precheck(workspace, script_path, outputs)
    if args.mode == "development":
        return run_development(workspace, family_root, script_path, outputs)
    return run_confirmation(workspace, family_root, script_path, outputs)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ADAPTER_ERROR: {exc}", file=sys.stderr, flush=True)
        raise
