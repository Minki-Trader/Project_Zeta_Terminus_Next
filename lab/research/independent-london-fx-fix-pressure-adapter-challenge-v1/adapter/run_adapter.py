from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


FAMILY = "independent-london-fx-fix-pressure-adapter-challenge-v1"
SYMBOLS = ("AUDUSD", "EURUSD", "GBPUSD", "NZDUSD")
SYMBOL_ORDER = {symbol: index for index, symbol in enumerate(SYMBOLS)}
VARIANTS: dict[str, dict[str, Any]] = {
    "LONDON_FIX_PRE_FLOW_CONTINUATION": {
        "signal_open_minute": 15 * 60 + 45,
        "decision_minute": 15 * 60 + 54,
        "atr_first_minute": 15 * 60 + 35,
        "atr_prior_minute": 15 * 60 + 34,
        "entry_minute": 15 * 60 + 55,
        "held_bars": 10,
        "exit_minute": 16 * 60 + 5,
        "reverse": False,
    },
    "LONDON_FIX_POST_PRESSURE_REVERSAL": {
        "signal_open_minute": 15 * 60 + 55,
        "decision_minute": 16 * 60 + 4,
        "atr_first_minute": 15 * 60 + 45,
        "atr_prior_minute": 15 * 60 + 44,
        "entry_minute": 16 * 60 + 5,
        "held_bars": 25,
        "exit_minute": 16 * 60 + 30,
        "reverse": True,
    },
}
VARIANT_ORDER = tuple(VARIANTS)
HORIZONS = (1, 5, 10, 20, 25, 30)
BROAD_HORIZONS = (5, 10, 20, 25, 30)
EVENT_FIRST_MINUTE = 15 * 60 + 34
EVENT_LAST_MINUTE = 16 * 60 + 35
EVENT_MINUTES = tuple(range(EVENT_FIRST_MINUTE, EVENT_LAST_MINUTE + 1))
DEVELOPMENT_START = pd.Timestamp("2024-01-01T00:00:00Z")
DEVELOPMENT_END = pd.Timestamp("2026-01-01T00:00:00Z")
LOCKED_START = DEVELOPMENT_END
LOCKED_END = pd.Timestamp("2026-08-01T00:00:00Z")
INITIAL_DEPOSIT = 100.0
POSITION_RISK_FRACTION = 0.015
MINIMUM_LOT_CAP_FRACTION = 0.03
AGGREGATE_RISK_CAP_FRACTION = 0.08
DEVELOPMENT_ACTUAL_GATE = 149.97
DEVELOPMENT_STRESS_GATE = 127.786
WHOLE_ACTUAL_GATE = 409.81
WHOLE_STRESS_GATE = 367.818
DRAWDOWN_GATE_PCT = 37.39
ROBUST_RECOVERY_GATE = 3.295860215
TURNOVER_GATE = 3.0
YEAR_START_GATE = 150
LOCKED_START_GATE = 75
SYMBOL_BREADTH_GATE = 3
BROAD_SLICE_MIN = 8
CSV_COLUMNS = (
    "time",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
)

EXPECTED = {
    "selection": {
        "path": "lab/evidence/INDEPENDENT_V8_CHALLENGE_POST_FAMILY_009_AUTONOMOUS_METHOD_SELECTION_V1.json",
        "bytes": 8784,
        "sha256": "5830CBF6257C656BBF235622FD91E50F8725D9C046E21E5049380F070ECAD2E6",
    },
    "contract": {
        "path": f"lab/research/{FAMILY}/config/challenge-contract.json",
        "bytes": 18309,
        "sha256": "F1F2CBCCEA4FE5E870FF0863BF58BEAE98F685AFAE3B8646FEB336C0EF297708",
    },
    "declaration": {
        "path": f"lab/research/{FAMILY}/evidence/INDEPENDENT_LONDON_FX_FIX_PRESSURE_ADAPTER_CHALLENGE_V1_DECLARATION.json",
        "bytes": 11207,
        "sha256": "8FDB21D7855B0C98D15A3B6979A3ECF63CF84A1BA876B33BF425455871633401",
    },
    "runtime_source": {
        "path": f"lab/research/{FAMILY}/evidence/INDEPENDENT_LONDON_FX_FIX_PRESSURE_ADAPTER_CHALLENGE_V1_RUNTIME_SOURCE_ENGINEERING_RECEIPT.json",
        "bytes": 9539,
        "sha256": "8C0E2F2E5FB46A9CBAB692841CFAEC21734C79888C7AEE2AEBD742C38D6F0EA2",
    },
    "history_correction": {
        "path": f"lab/research/{FAMILY}/evidence/INDEPENDENT_LONDON_FX_FIX_PRESSURE_ADAPTER_CHALLENGE_V1_M1_HISTORY_SYNCHRONIZATION_CORRECTION.json",
        "bytes": 5570,
        "sha256": "EC13141EE2821BBEAF4501A5693E9785492C34BD88286128F03A2022C2296CE6",
    },
    "development_source": {
        "path": f"lab/research/{FAMILY}/evidence/INDEPENDENT_LONDON_FX_FIX_PRESSURE_ADAPTER_CHALLENGE_V1_DEVELOPMENT_SOURCE_RECEIPT.json",
        "bytes": 8422,
        "sha256": "72B8FDD1EEF16D2400FDE226A394CBEB98FE029D2E1D0DEF327DBF0F1BF5FD8E",
    },
    "requirements": {
        "path": f"lab/research/{FAMILY}/adapter/requirements-adapter.txt",
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


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root is not an object: {path}")
    return value


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
    return 0.0 if rounded == 0.0 else rounded


def iso_utc(value: object) -> str:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    else:
        stamp = stamp.tz_convert("UTC")
    return stamp.isoformat().replace("+00:00", "Z")


def iso_server(value: object) -> str:
    return pd.Timestamp(value).isoformat()


def minute_label(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


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
    statuses = {
        "selection": "READY_AUTONOMOUS_LONDON_FX_FIX_PRESSURE_ADAPTER_BUNDLE_SUCCESSOR_NOT_OPENED",
        "declaration": "DECLARED_PRERUNTIME_PREACQUISITION_PREFEATURE_PREDECISION_PREIMPLEMENTATION_PREOUTCOME",
        "runtime_source": "DEDICATED_ORIGINAL_BROKER_RUNTIME_AND_M1_ACQUISITION_READY_PREACQUISITION_PREIMPLEMENTATION_PREOUTCOME",
        "history_correction": "SOURCE_SYNCHRONIZATION_SECTION_CORRECTED_PREACQUISITION_NO_PERSISTENT_SOURCE_PREIMPLEMENTATION_PREOUTCOME",
        "development_source": "COMPLETE_FRESH_ORIGINAL_BROKER_DEVELOPMENT_SOURCE_TIME_GEOMETRY_VALID_PREIMPLEMENTATION_PREOUTCOME",
    }
    for name, status in statuses.items():
        if read_json(workspace / EXPECTED[name]["path"]).get("status") != status:
            raise RuntimeError(f"authority has the wrong status: {name}")
    return verified


def verify_freeze(
    freeze_path: Path, script_path: Path, workspace: Path
) -> dict[str, Any]:
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


def load_spec(path: Path, expected: dict[str, Any], symbol: str) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing specification: {symbol}")
    if path.stat().st_size != int(expected["bytes"]) or sha256(path) != str(
        expected["sha256"]
    ):
        raise RuntimeError(f"symbol specification authority mismatch: {symbol}")
    spec = read_json(path)
    if spec.get("symbol") != symbol or spec.get("currency_profit") != "USD":
        raise RuntimeError(f"invalid USD specification: {symbol}")
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
        if finite(spec.get(field), f"{symbol}.{field}") <= 0.0:
            raise RuntimeError(f"nonpositive contract field: {symbol}.{field}")
    if int(spec.get("digits", -1)) != 5:
        raise RuntimeError(f"unexpected digits: {symbol}")
    if int(spec.get("swap_mode", -1)) not in (0, 1, 2, 4, 5, 6):
        raise RuntimeError(f"unsupported swap mode: {symbol}")
    if float(spec["volume_min"]) > float(spec["volume_max"]):
        raise RuntimeError(f"invalid volume bounds: {symbol}")
    return spec


def normalize_raw_time(raw: pd.Series, symbol: str) -> tuple[pd.Series, pd.Series]:
    server = pd.to_datetime(raw, unit="s", errors="raise")
    try:
        utc = server.dt.tz_localize(
            "Europe/Helsinki", ambiguous="raise", nonexistent="raise"
        ).dt.tz_convert("UTC")
    except Exception as exc:
        raise RuntimeError(f"{symbol} raw time localization failed: {exc}") from exc
    return server, utc


def load_event_rate_file(
    path: Path,
    expected: dict[str, Any],
    symbol: str,
    period_end: pd.Timestamp,
    require_no_locked_rows: bool,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not path.is_file():
        raise RuntimeError(f"missing market source: {symbol}")
    if path.stat().st_size != int(expected["bytes"]) or sha256(path) != str(
        expected["sha256"]
    ):
        raise RuntimeError(f"market source authority mismatch: {symbol}")
    compact: list[pd.DataFrame] = []
    total_rows = 0
    previous_raw: int | None = None
    previous_utc: pd.Timestamp | None = None
    locked_rows = 0
    after_period_rows = 0
    for chunk in pd.read_csv(path, chunksize=200_000):
        if tuple(chunk.columns) != CSV_COLUMNS:
            raise RuntimeError(f"unexpected source columns: {symbol}")
        if chunk.empty:
            continue
        total_rows += len(chunk)
        chunk["time"] = pd.to_numeric(chunk["time"], errors="raise").astype("int64")
        raw_values = chunk["time"].to_numpy(dtype="int64")
        if np.any(np.diff(raw_values) <= 0):
            raise RuntimeError(f"duplicate or nonincreasing raw time: {symbol}")
        if previous_raw is not None and int(raw_values[0]) <= previous_raw:
            raise RuntimeError(f"cross-chunk raw time failure: {symbol}")
        previous_raw = int(raw_values[-1])
        for column in ("open", "high", "low", "close", "spread"):
            chunk[column] = pd.to_numeric(chunk[column], errors="raise")
            if not np.isfinite(chunk[column].to_numpy(dtype="float64")).all():
                raise RuntimeError(f"nonfinite source column: {symbol}.{column}")
        for column in ("tick_volume", "real_volume"):
            chunk[column] = pd.to_numeric(chunk[column], errors="raise")
            if (
                not np.isfinite(chunk[column].to_numpy(dtype="float64")).all()
                or (chunk[column] < 0).any()
            ):
                raise RuntimeError(f"invalid volume column: {symbol}.{column}")
        if not (chunk[["open", "high", "low", "close"]] > 0.0).all().all():
            raise RuntimeError(f"nonpositive OHLC: {symbol}")
        if not (chunk["high"] >= chunk[["open", "close", "low"]].max(axis=1)).all():
            raise RuntimeError(f"high invariant failed: {symbol}")
        if not (chunk["low"] <= chunk[["open", "close", "high"]].min(axis=1)).all():
            raise RuntimeError(f"low invariant failed: {symbol}")
        if (chunk["spread"] < 0.0).any():
            raise RuntimeError(f"negative spread: {symbol}")
        server, utc = normalize_raw_time(chunk["time"], symbol)
        if utc.duplicated().any() or not utc.is_monotonic_increasing:
            raise RuntimeError(f"normalized timestamp invariant failed: {symbol}")
        if previous_utc is not None and pd.Timestamp(utc.iloc[0]) <= previous_utc:
            raise RuntimeError(f"cross-chunk normalized time failure: {symbol}")
        previous_utc = pd.Timestamp(utc.iloc[-1])
        locked_rows += int(((utc >= LOCKED_START) & (utc < LOCKED_END)).sum())
        after_period_rows += int((utc >= period_end).sum())
        london = utc.dt.tz_convert("Europe/London")
        minute = london.dt.hour * 60 + london.dt.minute
        mask = (
            (utc < period_end)
            & (london.dt.weekday < 5)
            & (minute >= EVENT_FIRST_MINUTE)
            & (minute <= EVENT_LAST_MINUTE)
        )
        if mask.any():
            selected = chunk.loc[mask, list(CSV_COLUMNS)].copy()
            selected["server_time"] = server.loc[mask].to_numpy()
            selected["time_utc"] = utc.loc[mask].array
            selected["time_london"] = london.loc[mask].array
            selected["local_date"] = london.loc[mask].dt.date.to_numpy()
            selected["minute"] = minute.loc[mask].to_numpy(dtype="int16")
            compact.append(selected)
    if total_rows != int(expected["rows"]):
        raise RuntimeError(f"unexpected source row count: {symbol}")
    if require_no_locked_rows and locked_rows != 0:
        raise RuntimeError(f"development source unexpectedly contains locked rows: {symbol}")
    if after_period_rows != 0:
        raise RuntimeError(f"source contains rows at or after its judged end: {symbol}")
    if not compact:
        raise RuntimeError(f"no event-window rows: {symbol}")
    frame = pd.concat(compact, ignore_index=True)
    if frame.duplicated(["local_date", "minute"]).any():
        raise RuntimeError(f"duplicate London event minute: {symbol}")
    if not frame["time_utc"].is_monotonic_increasing:
        raise RuntimeError(f"compact source is nonincreasing: {symbol}")
    return frame, {
        "source_rows": total_rows,
        "event_window_rows": len(frame),
        "locked_rows": locked_rows,
        "first_event_time_utc": iso_utc(frame["time_utc"].iloc[0]),
        "last_event_time_utc": iso_utc(frame["time_utc"].iloc[-1]),
    }


def source_maps_from_development_receipt(
    workspace: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    receipt = read_json(workspace / EXPECTED["development_source"]["path"])
    if receipt.get("status") != (
        "COMPLETE_FRESH_ORIGINAL_BROKER_DEVELOPMENT_SOURCE_TIME_GEOMETRY_VALID_PREIMPLEMENTATION_PREOUTCOME"
    ):
        raise RuntimeError("development source receipt has the wrong status")
    market = receipt.get("market_outputs")
    specifications = receipt.get("symbol_specifications")
    if not isinstance(market, dict) or not isinstance(specifications, dict):
        raise RuntimeError("development source receipt is incomplete")
    if tuple(market) != SYMBOLS:
        raise RuntimeError("development market symbol order mismatch")
    spec_map = {symbol: specifications.get(symbol) for symbol in SYMBOLS}
    if any(not isinstance(spec_map[symbol], dict) for symbol in SYMBOLS):
        raise RuntimeError("development specification map is incomplete")
    raw = receipt.get("raw_acquisition", {}).get("receipt", {})
    raw_path = workspace / str(raw.get("path", ""))
    if (
        not raw_path.is_file()
        or raw_path.stat().st_size != int(raw.get("bytes", -1))
        or sha256(raw_path) != str(raw.get("sha256"))
    ):
        raise RuntimeError("raw acquisition receipt authority mismatch")
    if read_json(raw_path).get("status") != (
        "COMPLETE_FRESH_DEDICATED_PORTABLE_DEVELOPMENT_ACQUISITION"
    ):
        raise RuntimeError("raw acquisition receipt has the wrong status")
    return market, spec_map, receipt


def load_development_sources(
    workspace: Path,
) -> tuple[
    dict[str, pd.DataFrame],
    dict[str, dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
]:
    market, spec_map, receipt = source_maps_from_development_receipt(workspace)
    frames: dict[str, pd.DataFrame] = {}
    specs: dict[str, dict[str, Any]] = {}
    loading: dict[str, Any] = {}
    for symbol in SYMBOLS:
        frames[symbol], loading[symbol] = load_event_rate_file(
            workspace / str(market[symbol]["path"]),
            market[symbol],
            symbol,
            DEVELOPMENT_END,
            True,
        )
        specs[symbol] = load_spec(
            workspace / str(spec_map[symbol]["path"]), spec_map[symbol], symbol
        )
    return frames, specs, receipt, loading


def load_complete_sources(
    workspace: Path,
) -> tuple[
    dict[str, pd.DataFrame],
    dict[str, dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
]:
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
    _, spec_map, _ = source_maps_from_development_receipt(workspace)
    frames: dict[str, pd.DataFrame] = {}
    specs: dict[str, dict[str, Any]] = {}
    loading: dict[str, Any] = {}
    for symbol in SYMBOLS:
        frames[symbol], loading[symbol] = load_event_rate_file(
            workspace / str(outputs[symbol]["path"]),
            outputs[symbol],
            symbol,
            LOCKED_END,
            False,
        )
        specs[symbol] = load_spec(
            workspace / str(spec_map[symbol]["path"]), spec_map[symbol], symbol
        )
    if any(int(loading[symbol]["locked_rows"]) <= 0 for symbol in SYMBOLS):
        raise RuntimeError("complete source lacks locked rows")
    return frames, specs, receipt, loading


def build_event_surface(
    frames: dict[str, pd.DataFrame], require_development_counts: bool = True
) -> tuple[
    dict[str, dict[date, pd.DataFrame]],
    list[date],
    dict[str, Any],
]:
    by_symbol: dict[str, dict[date, pd.DataFrame]] = {}
    complete_sets: list[set[date]] = []
    incomplete_counts: dict[str, int] = {}
    for symbol in SYMBOLS:
        date_map: dict[date, pd.DataFrame] = {}
        incomplete = 0
        for local_date, group in frames[symbol].groupby("local_date", sort=True):
            if local_date.weekday() >= 5:
                continue
            minutes = tuple(int(value) for value in group["minute"])
            if minutes == EVENT_MINUTES:
                indexed = group.set_index("minute", drop=False)
                if len(indexed) != 62:
                    raise RuntimeError("complete event row count changed")
                date_map[local_date] = indexed
            else:
                incomplete += 1
        by_symbol[symbol] = date_map
        complete_sets.append(set(date_map))
        incomplete_counts[symbol] = incomplete
    common_dates = sorted(set.intersection(*complete_sets))
    counts = Counter(day.year for day in common_dates)
    if require_development_counts:
        expected = {2023: 258, 2024: 256, 2025: 258}
        for year, count in expected.items():
            if counts.get(year, 0) != count:
                raise RuntimeError(
                    f"common complete-event count mismatch for {year}: {counts.get(year, 0)}"
                )
    development_dates = [day for day in common_dates if day.year in (2024, 2025)]
    if len(development_dates) != 514:
        raise RuntimeError("development common-event count mismatch")
    for day in common_dates:
        for symbol in SYMBOLS:
            frame = by_symbol[symbol][day]
            if tuple(int(value) for value in frame.index) != EVENT_MINUTES:
                raise RuntimeError("common event lost exact minute geometry")
    month_end_dates: set[date] = set()
    grouped: dict[tuple[int, int], list[date]] = defaultdict(list)
    for day in common_dates:
        if day.year >= 2024:
            grouped[(day.year, day.month)].append(day)
    for values in grouped.values():
        month_end_dates.add(max(values))
    quarter_end_dates = {
        day for day in month_end_dates if day.month in (3, 6, 9, 12)
    }
    geometry = {
        "timezone": "Europe/London",
        "exact_minute_interval": (
            f"{minute_label(EVENT_FIRST_MINUTE)}..{minute_label(EVENT_LAST_MINUTE)}"
        ),
        "rows_per_symbol_per_event": 62,
        "complete_dates_by_london_year": {
            str(year): int(counts[year]) for year in sorted(counts)
        },
        "common_complete_dates_total": len(common_dates),
        "development_complete_dates": len(development_dates),
        "development_month_end_dates": sum(
            day.year in (2024, 2025) for day in month_end_dates
        ),
        "development_quarter_end_dates": sum(
            day.year in (2024, 2025) for day in quarter_end_dates
        ),
        "symbol_local_window_incomplete_date_counts": incomplete_counts,
        "month_end_dates": month_end_dates,
        "quarter_end_dates": quarter_end_dates,
    }
    return by_symbol, common_dates, geometry


def true_range(high: float, low: float, prior_close: float) -> float:
    return max(high - low, abs(high - prior_close), abs(low - prior_close))


def build_opportunities(
    events: dict[str, dict[date, pd.DataFrame]],
    active_dates: Iterable[date],
    specs: dict[str, dict[str, Any]],
    month_end_dates: set[date],
    quarter_end_dates: set[date],
) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {
        variant: [] for variant in VARIANT_ORDER
    }
    for variant in VARIANT_ORDER:
        config = VARIANTS[variant]
        for day in sorted(active_dates):
            for symbol in SYMBOLS:
                event = events[symbol][day]
                prior = event.loc[int(config["atr_prior_minute"])]
                prior_close = float(prior["close"])
                tr_values: list[float] = []
                for minute in range(
                    int(config["atr_first_minute"]),
                    int(config["decision_minute"]) + 1,
                ):
                    row = event.loc[minute]
                    tr_values.append(
                        true_range(float(row["high"]), float(row["low"]), prior_close)
                    )
                    prior_close = float(row["close"])
                if len(tr_values) != 20:
                    raise RuntimeError("ATR20 window cardinality changed")
                atr = float(np.mean(tr_values))
                if not math.isfinite(atr) or atr <= 0.0:
                    raise RuntimeError(f"nonpositive ATR20: {variant}/{day}/{symbol}")
                signal_open = event.loc[int(config["signal_open_minute"])]
                decision = event.loc[int(config["decision_minute"])]
                entry = event.loc[int(config["entry_minute"])]
                move = float(decision["close"]) - float(signal_open["open"])
                direction = ""
                if move > 0.0:
                    direction = "SHORT" if bool(config["reverse"]) else "LONG"
                elif move < 0.0:
                    direction = "LONG" if bool(config["reverse"]) else "SHORT"
                spec = specs[symbol]
                spread_price = float(entry["spread"]) * float(spec["point"])
                risk_distance = max(5.0 * atr, 4.0 * spread_price)
                risk_per_lot = (
                    risk_distance
                    / float(spec["trade_tick_size"])
                    * float(spec["trade_tick_value_loss"])
                )
                if (
                    not math.isfinite(risk_distance)
                    or risk_distance <= 0.0
                    or not math.isfinite(risk_per_lot)
                    or risk_per_lot <= 0.0
                ):
                    raise RuntimeError("nonpositive risk geometry")
                expected_held = tuple(
                    range(
                        int(config["entry_minute"]),
                        int(config["entry_minute"]) + int(config["held_bars"]),
                    )
                )
                if expected_held[-1] + 1 != int(config["exit_minute"]):
                    raise RuntimeError("declared held-bar and exit geometry disagree")
                if any(minute not in event.index for minute in expected_held):
                    raise RuntimeError("held lifecycle minute is missing")
                if int(config["exit_minute"]) not in event.index:
                    raise RuntimeError("time-exit minute is missing")
                if any(
                    minute not in event.index
                    for minute in range(
                        int(config["entry_minute"]),
                        int(config["entry_minute"]) + max(HORIZONS),
                    )
                ):
                    raise RuntimeError("audit horizon geometry is incomplete")
                entry_bid = float(entry["open"])
                opportunity = {
                    "variant": variant,
                    "signal_id": f"{variant}:{day.isoformat()}:{symbol}",
                    "event_date": day,
                    "symbol": symbol,
                    "direction": direction,
                    "signal_move": move,
                    "signal_open_minute": int(config["signal_open_minute"]),
                    "decision_minute": int(config["decision_minute"]),
                    "decision_raw_time": int(decision["time"]),
                    "decision_time_utc": pd.Timestamp(decision["time_utc"]),
                    "entry_minute": int(config["entry_minute"]),
                    "entry_raw_time": int(entry["time"]),
                    "entry_server_time": pd.Timestamp(entry["server_time"]),
                    "entry_time_utc": pd.Timestamp(entry["time_utc"]),
                    "entry_time_london": pd.Timestamp(entry["time_london"]),
                    "entry_bid": entry_bid,
                    "entry_spread_points": float(entry["spread"]),
                    "entry_spread_price": spread_price,
                    "entry_ask": entry_bid + spread_price,
                    "atr20": atr,
                    "risk_distance": risk_distance,
                    "risk_per_lot": risk_per_lot,
                    "held_bars": int(config["held_bars"]),
                    "exit_minute": int(config["exit_minute"]),
                    "month_end": day in month_end_dates,
                    "quarter_end": day in quarter_end_dates,
                }
                output[variant].append(opportunity)
    return output


def volume_for_opportunity(
    opportunity: dict[str, Any], spec: dict[str, Any], balance_snapshot: float
) -> tuple[float, float, str | None]:
    if not math.isfinite(balance_snapshot) or balance_snapshot <= 0.0:
        return 0.0, 0.0, "CAPITAL_DEPLETED"
    risk_per_lot = float(opportunity["risk_per_lot"])
    step = float(spec["volume_step"])
    minimum = float(spec["volume_min"])
    maximum = float(spec["volume_max"])
    target_risk = balance_snapshot * POSITION_RISK_FRACTION
    target_volume = target_risk / risk_per_lot
    steps = math.floor((target_volume + 1e-12) / step)
    volume = min(maximum, steps * step)
    if volume + 1e-12 < minimum:
        minimum_loss = minimum * risk_per_lot
        if minimum_loss > balance_snapshot * MINIMUM_LOT_CAP_FRACTION + 1e-9:
            return 0.0, minimum_loss, "MINIMUM_LOT_POSITION_RISK"
        volume = minimum
    volume = math.floor((volume + 1e-12) / step) * step
    volume = round(volume, 10)
    if volume < minimum - 1e-12 or volume > maximum + 1e-12:
        raise RuntimeError("rounded volume left contract bounds")
    planned_loss = volume * risk_per_lot
    if planned_loss > balance_snapshot * MINIMUM_LOT_CAP_FRACTION + 1e-9:
        raise RuntimeError("accepted volume exceeded hard position-risk cap")
    return volume, planned_loss, None


def precheck_summary(
    authorities: dict[str, dict[str, Any]],
    loading: dict[str, Any],
    geometry: dict[str, Any],
    opportunities: dict[str, list[dict[str, Any]]],
    specs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    variants: dict[str, Any] = {}
    maximum_minimum_loss = 0.0
    for variant in VARIANT_ORDER:
        rows = opportunities[variant]
        signals = [row for row in rows if row["direction"]]
        feasible = 0
        by_year = Counter(row["event_date"].year for row in signals)
        by_direction = Counter(str(row["direction"]) for row in signals)
        by_symbol = Counter(str(row["symbol"]) for row in signals)
        for row in signals:
            minimum_loss = float(row["risk_per_lot"]) * float(
                specs[str(row["symbol"])]["volume_min"]
            )
            maximum_minimum_loss = max(maximum_minimum_loss, minimum_loss)
            if minimum_loss <= INITIAL_DEPOSIT * MINIMUM_LOT_CAP_FRACTION + 1e-9:
                feasible += 1
        active_dates = int(geometry["development_complete_dates"])
        variants[variant] = {
            "complete_opportunity_states": len(rows),
            "nonzero_signals": len(signals),
            "equality_no_direction": len(rows) - len(signals),
            "signals_per_portfolio_active_date": clean_float(
                len(signals) / active_dates if active_dates else 0.0
            ),
            "signals_by_london_year": {
                str(year): int(by_year[year]) for year in (2024, 2025)
            },
            "signals_by_direction": {
                direction: int(by_direction[direction])
                for direction in ("LONG", "SHORT")
            },
            "signals_by_symbol": {
                symbol: int(by_symbol[symbol]) for symbol in SYMBOLS
            },
            "minimum_lot_feasible_at_initial_100_usd": feasible,
            "minimum_lot_infeasible_at_initial_100_usd": len(signals) - feasible,
            "declared_held_m1_bars": int(VARIANTS[variant]["held_bars"]),
            "declared_time_exit_local": minute_label(
                int(VARIANTS[variant]["exit_minute"])
            ),
            "maximum_audit_horizon_geometry_present": True,
        }
    return {
        "schema": "zeta-next-independent-london-fx-fix-pressure-adapter-challenge-v1-outcome-free-precheck",
        "status": "VALID_OUTCOME_FREE_PRECHECK",
        "family": FAMILY,
        "authorities": authorities,
        "source_loading": loading,
        "event_geometry": {
            key: value
            for key, value in geometry.items()
            if key not in ("month_end_dates", "quarter_end_dates")
        },
        "variants": variants,
        "maximum_minimum_lot_planned_loss_usd": clean_float(
            maximum_minimum_loss
        ),
        "future_exit_path_rows_evaluated": 0,
        "candidate_lifecycles_or_economic_metrics": 0,
        "improvement_audit_values": 0,
        "locked_2026_rows_loaded": 0,
        "persistent_outputs_written": 0,
    }


def money_from_directional_price(
    directional_price: float, spec: dict[str, Any], volume: float
) -> float:
    tick_value = float(
        spec[
            "trade_tick_value_profit"
            if directional_price >= 0.0
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


def base_state_row(opportunity: dict[str, Any], signal_sequence: int) -> dict[str, Any]:
    return {
        "variant": opportunity["variant"],
        "signal_sequence": signal_sequence if opportunity["direction"] else 0,
        "signal_id": opportunity["signal_id"],
        "event_date_london": opportunity["event_date"].isoformat(),
        "symbol": opportunity["symbol"],
        "direction": opportunity["direction"],
        "signal_move": clean_float(opportunity["signal_move"]),
        "decision_raw_time": opportunity["decision_raw_time"],
        "decision_time_utc": iso_utc(opportunity["decision_time_utc"]),
        "entry_raw_time": opportunity["entry_raw_time"],
        "entry_time_utc": iso_utc(opportunity["entry_time_utc"]),
        "entry_time_london": opportunity["entry_time_london"].isoformat(),
        "entry_server_time": iso_server(opportunity["entry_server_time"]),
        "atr20": clean_float(opportunity["atr20"]),
        "risk_distance": clean_float(opportunity["risk_distance"]),
        "risk_per_lot_usd": clean_float(opportunity["risk_per_lot"]),
        "entry_bid": clean_float(opportunity["entry_bid"]),
        "entry_ask": clean_float(opportunity["entry_ask"]),
        "entry_spread_points": clean_float(opportunity["entry_spread_points"]),
        "month_end": bool(opportunity["month_end"]),
        "quarter_end": bool(opportunity["quarter_end"]),
        "admission_status": "NO_DIRECTION" if not opportunity["direction"] else "UNSET",
        "block_reason": "EQUALITY_NO_DIRECTION" if not opportunity["direction"] else "",
        "actual_balance_snapshot_usd": 0.0,
        "reservation_before_usd": 0.0,
        "aggregate_cap_usd": 0.0,
        "volume": 0.0,
        "planned_stop_loss_usd": 0.0,
        "trade_sequence": 0,
        "exit_reason": "",
        "exit_time_utc": "",
        "actual_pnl_usd": "",
        "stressed_pnl_usd": "",
        "realized_actual_r": "",
        "realized_stressed_r": "",
    }


def settle_opportunity(
    opportunity: dict[str, Any],
    event: pd.DataFrame,
    spec: dict[str, Any],
    volume: float,
    planned_loss: float,
    signal_sequence: int,
    trade_sequence: int,
) -> dict[str, Any]:
    direction = str(opportunity["direction"])
    entry_price = (
        float(opportunity["entry_ask"])
        if direction == "LONG"
        else float(opportunity["entry_bid"])
    )
    stop_price = (
        entry_price - float(opportunity["risk_distance"])
        if direction == "LONG"
        else entry_price + float(opportunity["risk_distance"])
    )
    exit_reason = "TIME_EXIT"
    exit_row: pd.Series | None = None
    held_bars = int(opportunity["held_bars"])
    for held_index, minute in enumerate(
        range(
            int(opportunity["entry_minute"]),
            int(opportunity["entry_minute"]) + held_bars,
        ),
        start=1,
    ):
        row = event.loc[minute]
        spread_price = float(row["spread"]) * float(spec["point"])
        if direction == "LONG":
            stop_hit = float(row["low"]) <= stop_price
        else:
            stop_hit = float(row["high"]) + spread_price >= stop_price
        if stop_hit:
            exit_reason = "HARD_STOP"
            exit_row = row
            held_bars = held_index
            break
    if exit_row is None:
        exit_row = event.loc[int(opportunity["exit_minute"])]
    exit_spread_price = float(exit_row["spread"]) * float(spec["point"])
    if exit_reason == "HARD_STOP":
        execution_price = stop_price
        exit_bid = stop_price if direction == "LONG" else stop_price - exit_spread_price
        exit_time_utc = pd.Timestamp(exit_row["time_utc"])
        exit_server_time = pd.Timestamp(exit_row["server_time"])
    else:
        exit_bid = float(exit_row["open"])
        execution_price = exit_bid if direction == "LONG" else exit_bid + exit_spread_price
        exit_time_utc = pd.Timestamp(exit_row["time_utc"])
        exit_server_time = pd.Timestamp(exit_row["server_time"])
    entry_server_time = pd.Timestamp(opportunity["entry_server_time"])
    if entry_server_time.normalize() != exit_server_time.normalize():
        raise RuntimeError("unexpected rollover boundary in intraday lifecycle")
    if direction == "LONG":
        gross_directional_price = exit_bid - float(opportunity["entry_bid"])
        actual_directional_price = execution_price - entry_price
        observed_spread_price = float(opportunity["entry_spread_price"])
    else:
        gross_directional_price = float(opportunity["entry_bid"]) - exit_bid
        actual_directional_price = entry_price - execution_price
        observed_spread_price = exit_spread_price
    gross_movement = money_from_directional_price(
        gross_directional_price, spec, volume
    )
    price_pnl = money_from_directional_price(actual_directional_price, spec, volume)
    observed_spread_burden = spread_burden_money(
        observed_spread_price, spec, volume
    )
    actual_pnl = price_pnl
    stressed_pnl = actual_pnl - observed_spread_burden
    if abs((gross_movement - observed_spread_burden) - actual_pnl) > 1e-7:
        raise RuntimeError("direction-specific actual spread identity failed")
    if exit_reason == "HARD_STOP" and abs(actual_pnl + planned_loss) > 1e-6:
        raise RuntimeError("hard-stop planned-loss identity failed")
    return {
        "variant": opportunity["variant"],
        "trade_sequence": trade_sequence,
        "signal_sequence": signal_sequence,
        "signal_id": opportunity["signal_id"],
        "event_date_london": opportunity["event_date"].isoformat(),
        "symbol": opportunity["symbol"],
        "direction": direction,
        "entry_raw_time": opportunity["entry_raw_time"],
        "entry_time_utc": iso_utc(opportunity["entry_time_utc"]),
        "entry_time_london": opportunity["entry_time_london"].isoformat(),
        "entry_server_time": iso_server(entry_server_time),
        "exit_bar_raw_time": int(exit_row["time"]),
        "exit_time_utc": iso_utc(exit_time_utc),
        "exit_server_time": iso_server(exit_server_time),
        "exit_reason": exit_reason,
        "held_m1_bars": held_bars,
        "volume": clean_float(volume),
        "planned_stop_loss_usd": clean_float(planned_loss),
        "risk_distance": clean_float(opportunity["risk_distance"]),
        "entry_bid": clean_float(opportunity["entry_bid"]),
        "entry_price": clean_float(entry_price),
        "stop_price": clean_float(stop_price),
        "exit_bid": clean_float(exit_bid),
        "exit_price": clean_float(execution_price),
        "entry_spread_points": clean_float(opportunity["entry_spread_points"]),
        "exit_spread_points": clean_float(exit_row["spread"]),
        "gross_movement_usd": clean_float(gross_movement),
        "observed_spread_burden_usd": clean_float(observed_spread_burden),
        "price_pnl_usd": clean_float(price_pnl),
        "swap_usd": 0.0,
        "rollover_boundaries": 0,
        "actual_pnl_usd": clean_float(actual_pnl),
        "stressed_pnl_usd": clean_float(stressed_pnl),
        "actual_r": clean_float(actual_pnl / planned_loss),
        "stressed_r": clean_float(stressed_pnl / planned_loss),
    }


def summarize_simulation(
    variant: str,
    states: list[dict[str, Any]],
    trades: list[dict[str, Any]],
    active_dates: list[date],
    initial_actual_balance: float,
    initial_stressed_balance: float,
    ending_actual_balance: float,
    ending_stressed_balance: float,
    actual_peak: float,
    maximum_drawdown_usd: float,
    maximum_drawdown_pct: float,
    years: tuple[int, ...],
) -> dict[str, Any]:
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
    for values in epochs.values():
        values["actual_net_usd"] = clean_float(values["actual_net_usd"])
        values["stressed_net_usd"] = clean_float(values["stressed_net_usd"])
    accepted = len(trades)
    stressed_net = ending_stressed_balance - initial_stressed_balance
    recovery = (
        clean_float(stressed_net / maximum_drawdown_usd)
        if maximum_drawdown_usd > 0.0
        else None
    )
    signals = [row for row in states if row["direction"]]
    blocked = [row for row in signals if row["admission_status"] == "BLOCKED"]
    block_counts = Counter(str(row["block_reason"]) for row in blocked)
    exit_counts = Counter(str(row["exit_reason"]) for row in trades)
    accepted_symbols = sorted(
        {str(row["symbol"]) for row in trades}, key=SYMBOL_ORDER.get
    )
    directions = sorted({str(row["direction"]) for row in trades})
    return {
        "variant": variant,
        "opportunity_states": len(states),
        "signal_count": len(signals),
        "equality_no_direction": len(states) - len(signals),
        "accepted_starts": accepted,
        "blocked_signals": len(blocked),
        "block_counts": dict(sorted(block_counts.items())),
        "exit_counts": dict(sorted(exit_counts.items())),
        "portfolio_active_dates": len(active_dates),
        "accepted_starts_per_portfolio_active_date": clean_float(
            accepted / len(active_dates) if active_dates else 0.0
        ),
        "initial_actual_balance_usd": clean_float(initial_actual_balance),
        "initial_stressed_balance_usd": clean_float(initial_stressed_balance),
        "actual_net_usd": clean_float(ending_actual_balance - initial_actual_balance),
        "stressed_net_usd": clean_float(
            ending_stressed_balance - initial_stressed_balance
        ),
        "ending_actual_balance_usd": clean_float(ending_actual_balance),
        "ending_stressed_balance_usd": clean_float(ending_stressed_balance),
        "actual_closed_balance_peak_usd": clean_float(actual_peak),
        "actual_closed_balance_drawdown_usd": clean_float(maximum_drawdown_usd),
        "actual_closed_balance_drawdown_pct": clean_float(maximum_drawdown_pct),
        "robust_recovery": recovery,
        "robust_recovery_unbounded_positive": (
            maximum_drawdown_usd == 0.0 and stressed_net > 0.0
        ),
        "epoch_metrics": epochs,
        "symbol_breadth": len(accepted_symbols),
        "accepted_symbols": accepted_symbols,
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
        "median_held_m1_bars": clean_float(
            float(np.median([int(row["held_m1_bars"]) for row in trades]))
            if trades
            else 0.0
        ),
    }


def simulate_variant(
    variant: str,
    events: dict[str, dict[date, pd.DataFrame]],
    specs: dict[str, dict[str, Any]],
    opportunities: list[dict[str, Any]],
    active_dates: list[date],
    years: tuple[int, ...],
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
    by_date: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for row in opportunities:
        by_date[row["event_date"]].append(row)
    states: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    signal_sequence = 0
    trade_sequence = 0
    for day in active_dates:
        day_rows = sorted(by_date[day], key=lambda row: SYMBOL_ORDER[str(row["symbol"])])
        if len(day_rows) != len(SYMBOLS):
            raise RuntimeError("portfolio date lacks four opportunity states")
        balance_snapshot = actual_balance
        aggregate_cap = max(0.0, balance_snapshot * AGGREGATE_RISK_CAP_FRACTION)
        reservation = 0.0
        accepted: list[tuple[dict[str, Any], dict[str, Any], int, int]] = []
        for opportunity in day_rows:
            if opportunity["direction"]:
                signal_sequence += 1
            state = base_state_row(opportunity, signal_sequence)
            state["actual_balance_snapshot_usd"] = clean_float(balance_snapshot)
            state["reservation_before_usd"] = clean_float(reservation)
            state["aggregate_cap_usd"] = clean_float(aggregate_cap)
            states.append(state)
            state_index = len(states) - 1
            if not opportunity["direction"]:
                continue
            symbol = str(opportunity["symbol"])
            volume, planned_loss, block_reason = volume_for_opportunity(
                opportunity, specs[symbol], balance_snapshot
            )
            state["volume"] = clean_float(volume)
            state["planned_stop_loss_usd"] = clean_float(planned_loss)
            if block_reason is not None:
                state["admission_status"] = "BLOCKED"
                state["block_reason"] = block_reason
                continue
            if reservation + planned_loss > aggregate_cap + 1e-9:
                state["admission_status"] = "BLOCKED"
                state["block_reason"] = "AGGREGATE_INITIAL_STOP_RISK"
                continue
            reservation += planned_loss
            trade_sequence += 1
            state["admission_status"] = "ACCEPTED"
            state["trade_sequence"] = trade_sequence
            accepted.append((opportunity, state, signal_sequence, trade_sequence))
        for opportunity, state, this_signal, this_trade in accepted:
            symbol = str(opportunity["symbol"])
            trade = settle_opportunity(
                opportunity,
                events[symbol][day],
                specs[symbol],
                float(state["volume"]),
                float(state["planned_stop_loss_usd"]),
                this_signal,
                this_trade,
            )
            trade["actual_balance_before_usd"] = clean_float(actual_balance)
            trade["stressed_balance_before_usd"] = clean_float(stressed_balance)
            actual_balance += float(trade["actual_pnl_usd"])
            stressed_balance += float(trade["stressed_pnl_usd"])
            if not math.isfinite(actual_balance) or not math.isfinite(stressed_balance):
                raise RuntimeError("nonfinite portfolio balance")
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
            state["exit_reason"] = trade["exit_reason"]
            state["exit_time_utc"] = trade["exit_time_utc"]
            state["actual_pnl_usd"] = trade["actual_pnl_usd"]
            state["stressed_pnl_usd"] = trade["stressed_pnl_usd"]
            state["realized_actual_r"] = trade["actual_r"]
            state["realized_stressed_r"] = trade["stressed_r"]
            trades.append(trade)
    if len(states) != len(active_dates) * len(SYMBOLS):
        raise RuntimeError("state cardinality mismatch")
    if len(trades) != trade_sequence:
        raise RuntimeError("trade cardinality mismatch")
    if abs(
        sum(float(row["actual_pnl_usd"]) for row in trades)
        - (actual_balance - initial_actual_balance)
    ) > 1e-7:
        raise RuntimeError("actual balance identity failed")
    if abs(
        sum(float(row["stressed_pnl_usd"]) for row in trades)
        - (stressed_balance - initial_stressed_balance)
    ) > 1e-7:
        raise RuntimeError("stressed balance identity failed")
    metrics = summarize_simulation(
        variant,
        states,
        trades,
        active_dates,
        initial_actual_balance,
        initial_stressed_balance,
        actual_balance,
        stressed_balance,
        actual_peak,
        maximum_drawdown_usd,
        maximum_drawdown_pct,
        years,
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
        "development_actual_strictly_above_149_97": float(metrics["actual_net_usd"])
        > DEVELOPMENT_ACTUAL_GATE,
        "development_stressed_strictly_above_127_786": float(
            metrics["stressed_net_usd"]
        )
        > DEVELOPMENT_STRESS_GATE,
        "actual_closed_balance_drawdown_at_most_37_39_pct": float(
            metrics["actual_closed_balance_drawdown_pct"]
        )
        <= DRAWDOWN_GATE_PCT,
        "accepted_starts_per_active_date_at_least_3": float(
            metrics["accepted_starts_per_portfolio_active_date"]
        )
        >= TURNOVER_GATE,
        "at_least_150_starts_in_each_development_year": all(
            int(epochs[str(year)]["starts"]) >= YEAR_START_GATE
            for year in (2024, 2025)
        ),
        "symbol_breadth_at_least_3": int(metrics["symbol_breadth"])
        >= SYMBOL_BREADTH_GATE,
        "both_directions": set(metrics["direction_breadth"]) == {"LONG", "SHORT"},
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
    events: dict[str, dict[date, pd.DataFrame]],
    specs: dict[str, dict[str, Any]],
    opportunities_by_variant: dict[str, list[dict[str, Any]]],
    states_by_variant: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    state_by_id = {
        str(row["signal_id"]): row
        for rows in states_by_variant.values()
        for row in rows
    }
    opportunity_by_key = {
        (str(row["variant"]), row["event_date"], str(row["symbol"])): row
        for rows in opportunities_by_variant.values()
        for row in rows
    }
    output: list[dict[str, Any]] = []
    audit_sequence = 0
    for variant in VARIANT_ORDER:
        sibling = next(value for value in VARIANT_ORDER if value != variant)
        signal_sequence = 0
        for opportunity in opportunities_by_variant[variant]:
            if not opportunity["direction"]:
                continue
            signal_sequence += 1
            symbol = str(opportunity["symbol"])
            day = opportunity["event_date"]
            spec = specs[symbol]
            event = events[symbol][day]
            state = state_by_id[str(opportunity["signal_id"])]
            sibling_row = opportunity_by_key[(sibling, day, symbol)]
            sibling_direction = str(sibling_row["direction"])
            if not sibling_direction:
                relationship = "SIBLING_EQUALITY_NO_DIRECTION"
            elif sibling_direction == opportunity["direction"]:
                relationship = "SAME_DIRECTION"
            else:
                relationship = "OPPOSITE_DIRECTION"
            entry_bid = float(opportunity["entry_bid"])
            entry_price = (
                float(opportunity["entry_ask"])
                if opportunity["direction"] == "LONG"
                else entry_bid
            )
            stop_price = (
                entry_price - float(opportunity["risk_distance"])
                if opportunity["direction"] == "LONG"
                else entry_price + float(opportunity["risk_distance"])
            )
            first_stop_bar: int | None = None
            for held_bar, minute in enumerate(
                range(int(opportunity["entry_minute"]), int(opportunity["entry_minute"]) + 30),
                start=1,
            ):
                row = event.loc[minute]
                spread_price = float(row["spread"]) * float(spec["point"])
                stop_hit = (
                    float(row["low"]) <= stop_price
                    if opportunity["direction"] == "LONG"
                    else float(row["high"]) + spread_price >= stop_price
                )
                if stop_hit:
                    first_stop_bar = held_bar
                    break
            for horizon in HORIZONS:
                audit_sequence += 1
                minutes = range(
                    int(opportunity["entry_minute"]),
                    int(opportunity["entry_minute"]) + horizon,
                )
                path = event.loc[list(minutes)]
                exit_row = path.iloc[-1]
                exit_bid = float(exit_row["close"])
                exit_spread_price = float(exit_row["spread"]) * float(spec["point"])
                if opportunity["direction"] == "LONG":
                    raw_price = exit_bid - entry_bid
                    actual_price = exit_bid - entry_price
                    extra_spread_price = float(opportunity["entry_spread_price"])
                    mfe_price = float(path["high"].max()) - entry_bid
                    mae_price = float(path["low"].min()) - entry_bid
                else:
                    raw_price = entry_bid - exit_bid
                    actual_price = entry_price - (exit_bid + exit_spread_price)
                    extra_spread_price = exit_spread_price
                    mfe_price = entry_bid - float(path["low"].min())
                    mae_price = entry_bid - float(path["high"].max())
                raw_money = money_from_directional_price(raw_price, spec, 1.0)
                actual_money = money_from_directional_price(actual_price, spec, 1.0)
                extra_stress = spread_burden_money(extra_spread_price, spec, 1.0)
                stressed_money = actual_money - extra_stress
                mfe_money = money_from_directional_price(mfe_price, spec, 1.0)
                mae_money = money_from_directional_price(mae_price, spec, 1.0)
                risk_per_lot = float(opportunity["risk_per_lot"])
                if pd.Timestamp(opportunity["entry_server_time"]).normalize() != pd.Timestamp(
                    exit_row["server_time"]
                ).normalize():
                    raise RuntimeError("audit unexpectedly crossed rollover")
                output.append(
                    {
                        "audit_sequence": audit_sequence,
                        "variant": variant,
                        "signal_sequence": signal_sequence,
                        "signal_id": opportunity["signal_id"],
                        "event_date_london": day.isoformat(),
                        "year": day.year,
                        "symbol": symbol,
                        "direction": opportunity["direction"],
                        "sibling_variant": sibling,
                        "sibling_direction": sibling_direction,
                        "cross_variant_direction_relationship": relationship,
                        "date_slice": "MONTH_END" if opportunity["month_end"] else "ORDINARY",
                        "month_end": bool(opportunity["month_end"]),
                        "quarter_end": bool(opportunity["quarter_end"]),
                        "horizon_m1": horizon,
                        "entry_time_utc": iso_utc(opportunity["entry_time_utc"]),
                        "audit_exit_time_utc": iso_utc(
                            pd.Timestamp(exit_row["time_utc"]) + pd.Timedelta(minutes=1)
                        ),
                        "risk_distance": clean_float(opportunity["risk_distance"]),
                        "risk_per_lot_usd": clean_float(risk_per_lot),
                        "entry_spread_points": clean_float(opportunity["entry_spread_points"]),
                        "exit_spread_points": clean_float(exit_row["spread"]),
                        "raw_gross_usd_one_lot": clean_float(raw_money),
                        "actual_usd_one_lot": clean_float(actual_money),
                        "extra_stress_spread_usd_one_lot": clean_float(extra_stress),
                        "stressed_usd_one_lot": clean_float(stressed_money),
                        "raw_gross_r": clean_float(raw_money / risk_per_lot),
                        "actual_r": clean_float(actual_money / risk_per_lot),
                        "stressed_r": clean_float(stressed_money / risk_per_lot),
                        "raw_bid_mfe_r": clean_float(mfe_money / risk_per_lot),
                        "raw_bid_mae_r": clean_float(mae_money / risk_per_lot),
                        "hard_stop_hit_by_horizon": (
                            first_stop_bar is not None and first_stop_bar <= horizon
                        ),
                        "first_hard_stop_held_bar": first_stop_bar or 0,
                        "declared_lifecycle_held_bars": int(opportunity["held_bars"]),
                        "horizon_beyond_declared_lifecycle": horizon
                        > int(opportunity["held_bars"]),
                        "proxy_admission_status": state["admission_status"],
                        "proxy_block_reason": state["block_reason"],
                        "proxy_declared_exit_reason": state["exit_reason"],
                    }
                )
    expected = sum(
        sum(bool(row["direction"]) for row in rows)
        for rows in opportunities_by_variant.values()
    ) * len(HORIZONS)
    if len(output) != expected:
        raise RuntimeError("improvement path cardinality mismatch")
    return output


def path_group_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "count": 0,
            "mean_raw_gross_r": 0.0,
            "mean_actual_r": 0.0,
            "mean_stressed_r": 0.0,
            "mean_raw_bid_mfe_r": 0.0,
            "mean_raw_bid_mae_r": 0.0,
            "hard_stop_hit_fraction": 0.0,
        }
    return {
        "count": len(rows),
        "mean_raw_gross_r": clean_float(
            np.mean([float(row["raw_gross_r"]) for row in rows])
        ),
        "mean_actual_r": clean_float(
            np.mean([float(row["actual_r"]) for row in rows])
        ),
        "mean_stressed_r": clean_float(
            np.mean([float(row["stressed_r"]) for row in rows])
        ),
        "mean_raw_bid_mfe_r": clean_float(
            np.mean([float(row["raw_bid_mfe_r"]) for row in rows])
        ),
        "mean_raw_bid_mae_r": clean_float(
            np.mean([float(row["raw_bid_mae_r"]) for row in rows])
        ),
        "hard_stop_hit_fraction": clean_float(
            np.mean([bool(row["hard_stop_hit_by_horizon"]) for row in rows])
        ),
    }


def grouped_path_summaries(
    rows: list[dict[str, Any]], fields: tuple[str, ...]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row[field] for field in fields)].append(row)
    output: list[dict[str, Any]] = []
    for key in sorted(grouped, key=lambda value: tuple(str(item) for item in value)):
        labels = {field: value for field, value in zip(fields, key)}
        output.append({**labels, **path_group_summary(grouped[key])})
    return output


def broad_headroom(rows: list[dict[str, Any]]) -> dict[str, Any]:
    evaluations: list[dict[str, Any]] = []
    qualifying: list[dict[str, Any]] = []
    for variant in VARIANT_ORDER:
        for horizon in BROAD_HORIZONS:
            subset = [
                row
                for row in rows
                if row["variant"] == variant and int(row["horizon_m1"]) == horizon
            ]
            year_slices = {
                str(year): path_group_summary(
                    [row for row in subset if int(row["year"]) == year]
                )
                for year in (2024, 2025)
            }
            symbol_slices = {
                symbol: path_group_summary(
                    [row for row in subset if row["symbol"] == symbol]
                )
                for symbol in SYMBOLS
            }
            direction_slices = {
                direction: path_group_summary(
                    [row for row in subset if row["direction"] == direction]
                )
                for direction in ("LONG", "SHORT")
            }
            date_slices = {
                label: path_group_summary(
                    [row for row in subset if row["date_slice"] == label]
                )
                for label in ("ORDINARY", "MONTH_END")
            }

            def positive(summary: dict[str, Any]) -> bool:
                return (
                    int(summary["count"]) >= BROAD_SLICE_MIN
                    and float(summary["mean_raw_gross_r"]) > 0.0
                    and float(summary["mean_stressed_r"]) > 0.0
                )

            qualifying_symbols = [
                symbol for symbol, summary in symbol_slices.items() if positive(summary)
            ]
            gates = {
                "both_years_positive_raw_and_stressed_with_min_8": all(
                    positive(summary) for summary in year_slices.values()
                ),
                "at_least_three_positive_symbols_with_min_8": len(qualifying_symbols)
                >= 3,
                "both_directions_positive_raw_and_stressed_with_min_8": all(
                    positive(summary) for summary in direction_slices.values()
                ),
                "ordinary_and_month_end_positive_raw_and_stressed_with_min_8": all(
                    positive(summary) for summary in date_slices.values()
                ),
            }
            gates["passed"] = all(gates.values())
            evaluation = {
                "variant": variant,
                "horizon_m1": horizon,
                "overall": path_group_summary(subset),
                "year_slices": year_slices,
                "symbol_slices": symbol_slices,
                "qualifying_positive_symbols": qualifying_symbols,
                "direction_slices": direction_slices,
                "ordinary_month_end_slices": date_slices,
                "gates": gates,
            }
            evaluations.append(evaluation)
            if gates["passed"]:
                qualifying.append(evaluation)
    qualifying.sort(
        key=lambda row: (
            -float(row["overall"]["mean_stressed_r"]),
            VARIANT_ORDER.index(str(row["variant"])),
            BROAD_HORIZONS.index(int(row["horizon_m1"])),
        )
    )
    return {
        "definition": "one frozen 5/10/20/25/30 M1 horizon with positive raw and stressed mean R in both years, at least three pairs, both directions, ordinary and month-end slices, minimum eight each",
        "evaluation_count": len(evaluations),
        "evaluations": evaluations,
        "broad_headroom": bool(qualifying),
        "selected_bounded_seed": (
            {
                "variant": qualifying[0]["variant"],
                "horizon_m1": qualifying[0]["horizon_m1"],
                "authority": "RETAIN_ONLY_RECOMPARE_BEFORE_ANY_SUCCESSOR",
            }
            if qualifying
            else None
        ),
    }


def build_improvement_audit(
    path_rows: list[dict[str, Any]], states_by_variant: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    headroom = broad_headroom(path_rows)
    blocks = Counter(
        str(row["block_reason"])
        for rows in states_by_variant.values()
        for row in rows
        if row["direction"] and row["admission_status"] == "BLOCKED"
    )
    exits = Counter(
        str(row["exit_reason"])
        for rows in states_by_variant.values()
        for row in rows
        if row["admission_status"] == "ACCEPTED"
    )
    return {
        "schema": "zeta-next-independent-london-fx-fix-pressure-adapter-challenge-v1-development-improvement-audit",
        "status": "VALID_MANDATORY_IMPROVEMENT_POTENTIAL_AUDIT_COMPLETE",
        "family": FAMILY,
        "population": "every complete nonzero development signal in both frozen variants whether admitted or blocked",
        "horizons_m1": list(HORIZONS),
        "path_rows": len(path_rows),
        "signal_population": len(path_rows) // len(HORIZONS),
        "proxy_block_counts": dict(sorted(blocks.items())),
        "proxy_exit_counts": dict(sorted(exits.items())),
        "by_variant_horizon": grouped_path_summaries(
            path_rows, ("variant", "horizon_m1")
        ),
        "by_variant_horizon_year": grouped_path_summaries(
            path_rows, ("variant", "horizon_m1", "year")
        ),
        "by_variant_horizon_symbol": grouped_path_summaries(
            path_rows, ("variant", "horizon_m1", "symbol")
        ),
        "by_variant_horizon_direction": grouped_path_summaries(
            path_rows, ("variant", "horizon_m1", "direction")
        ),
        "by_variant_horizon_date_slice": grouped_path_summaries(
            path_rows, ("variant", "horizon_m1", "date_slice")
        ),
        "quarter_end_descriptive": grouped_path_summaries(
            [row for row in path_rows if row["quarter_end"]],
            ("variant", "horizon_m1"),
        ),
        "broad_headroom_evaluation": headroom,
        "audit_authority_limit": "cannot execute or authorize an adjacent clock, window, threshold, pair, direction, ATR, stop, hold, risk or sizing rescue inside V1",
    }


def json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")


def csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        return b"\n"
    fieldnames = list(rows[0])
    if any(list(row) != fieldnames for row in rows):
        raise RuntimeError("CSV row schema changed within one tape")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def output_paths(workspace: Path) -> dict[str, Path]:
    root = workspace / "lab" / "artifacts" / "raw" / FAMILY / "output"
    return {
        "result": root / "development-result.json",
        "audit": root / "development-audit.json",
        "states": root / "signal-states.csv",
        "trades": root / "trades.csv",
        "paths": root / "improvement-paths.csv",
    }


def byte_record(path: Path, data: bytes, workspace: Path) -> dict[str, Any]:
    return {
        "path": rel(path, workspace),
        "bytes": len(data),
        "sha256": sha256_bytes(data),
    }


def atomic_write_outputs(outputs: list[tuple[Path, bytes]], result_path: Path) -> None:
    destinations = [path for path, _ in outputs]
    if len(destinations) != len(set(destinations)):
        raise RuntimeError("duplicate output destination")
    if any(path.exists() for path in destinations):
        raise RuntimeError("refusing to overwrite a development artifact")
    parent = result_path.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="zeta-f010-output-", dir=parent))
    try:
        staged: dict[Path, Path] = {}
        for destination, data in outputs:
            path = staging / destination.name
            path.write_bytes(data)
            if path.stat().st_size != len(data) or sha256(path) != sha256_bytes(data):
                raise RuntimeError("staged output verification failed")
            staged[destination] = path
        for destination, _ in outputs:
            if destination == result_path:
                continue
            os.replace(staged[destination], destination)
        os.replace(staged[result_path], result_path)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def compare_precheck_to_freeze(
    precheck: dict[str, Any], freeze: dict[str, Any]
) -> None:
    frozen = freeze.get("outcome_free_precheck")
    if not isinstance(frozen, dict):
        raise RuntimeError("freeze lacks outcome-free precheck")
    if frozen.get("status") != "VALID_OUTCOME_FREE_PRECHECK":
        raise RuntimeError("frozen precheck status mismatch")
    for key in (
        "maximum_minimum_lot_planned_loss_usd",
        "future_exit_path_rows_evaluated",
        "candidate_lifecycles_or_economic_metrics",
        "improvement_audit_values",
        "locked_2026_rows_loaded",
        "persistent_outputs_written",
    ):
        if frozen.get(key) != precheck.get(key):
            raise RuntimeError(f"frozen precheck field mismatch: {key}")
    frozen_variants = frozen.get("variants")
    if not isinstance(frozen_variants, dict):
        raise RuntimeError("frozen precheck variant map missing")
    for variant in VARIANT_ORDER:
        for key in (
            "complete_opportunity_states",
            "nonzero_signals",
            "equality_no_direction",
            "signals_by_london_year",
            "signals_by_direction",
            "signals_by_symbol",
            "minimum_lot_feasible_at_initial_100_usd",
            "minimum_lot_infeasible_at_initial_100_usd",
        ):
            if frozen_variants.get(variant, {}).get(key) != precheck["variants"][
                variant
            ].get(key):
                raise RuntimeError(f"frozen precheck variant mismatch: {variant}.{key}")


def run_precheck(workspace: Path, script_path: Path) -> dict[str, Any]:
    authorities = verify_authorities(workspace)
    frames, specs, _, loading = load_development_sources(workspace)
    events, common_dates, geometry = build_event_surface(frames)
    development_dates = [day for day in common_dates if day.year in (2024, 2025)]
    opportunities = build_opportunities(
        events,
        development_dates,
        specs,
        set(geometry["month_end_dates"]),
        set(geometry["quarter_end_dates"]),
    )
    result = precheck_summary(authorities, loading, geometry, opportunities, specs)
    result["adapter"] = {
        "path": rel(script_path, workspace),
        "bytes": script_path.stat().st_size,
        "lines": len(script_path.read_text(encoding="utf-8").splitlines()),
        "sha256": sha256(script_path),
    }
    return result


def run_development(workspace: Path, script_path: Path) -> dict[str, Any]:
    authorities = verify_authorities(workspace)
    freeze_path = (
        workspace
        / "lab"
        / "research"
        / FAMILY
        / "evidence"
        / "INDEPENDENT_LONDON_FX_FIX_PRESSURE_ADAPTER_CHALLENGE_V1_IMPLEMENTATION_FREEZE.json"
    )
    freeze = verify_freeze(freeze_path, script_path, workspace)
    frames, specs, _, loading = load_development_sources(workspace)
    events, common_dates, geometry = build_event_surface(frames)
    development_dates = [day for day in common_dates if day.year in (2024, 2025)]
    opportunities = build_opportunities(
        events,
        development_dates,
        specs,
        set(geometry["month_end_dates"]),
        set(geometry["quarter_end_dates"]),
    )
    precheck = precheck_summary(authorities, loading, geometry, opportunities, specs)
    compare_precheck_to_freeze(precheck, freeze)
    results: list[dict[str, Any]] = []
    states_by_variant: dict[str, list[dict[str, Any]]] = {}
    trades_by_variant: dict[str, list[dict[str, Any]]] = {}
    for variant in VARIANT_ORDER:
        metrics, states, trades = simulate_variant(
            variant,
            events,
            specs,
            opportunities[variant],
            development_dates,
            (2024, 2025),
        )
        metrics["gates"] = development_gates(metrics)
        results.append(metrics)
        states_by_variant[variant] = states
        trades_by_variant[variant] = trades
    path_rows = improvement_path_rows(
        events, specs, opportunities, states_by_variant
    )
    audit = build_improvement_audit(path_rows, states_by_variant)
    passers = ranked_development_passers(results)
    selected_variant = str(passers[0]["variant"]) if passers else None
    broad = bool(audit["broad_headroom_evaluation"]["broad_headroom"])
    status = (
        "VALID_DEVELOPMENT_COMPLETE_ONE_SELECTED_PASSER"
        if passers
        else (
            "VALID_DEVELOPMENT_COMPLETE_NO_PASSER_BROAD_HEADROOM"
            if broad
            else "VALID_DEVELOPMENT_COMPLETE_NO_PASSER_NO_BROAD_HEADROOM"
        )
    )
    all_states = [
        row for variant in VARIANT_ORDER for row in states_by_variant[variant]
    ]
    all_trades = [
        row for variant in VARIANT_ORDER for row in trades_by_variant[variant]
    ]
    paths = output_paths(workspace)
    audit_data = json_bytes(audit)
    states_data = csv_bytes(all_states)
    trades_data = csv_bytes(all_trades)
    path_data = csv_bytes(path_rows)
    result: dict[str, Any] = {
        "schema": "zeta-next-independent-london-fx-fix-pressure-adapter-challenge-v1-development-result",
        "status": status,
        "family": FAMILY,
        "architecture": "Python adapter + EA",
        "period": "2024-01-01T00:00:00Z/2026-01-01T00:00:00Z",
        "authorities": authorities,
        "implementation_freeze": authority_record(freeze_path, workspace),
        "source_loading": loading,
        "event_geometry": {
            key: value
            for key, value in geometry.items()
            if key not in ("month_end_dates", "quarter_end_dates")
        },
        "variant_results": results,
        "complete_passer_count": len(passers),
        "complete_passers_ranked": [str(row["variant"]) for row in passers],
        "selected_variant": selected_variant,
        "mandatory_improvement_audit_status": audit["status"],
        "broad_headroom": broad,
        "bounded_successor_seed": audit["broad_headroom_evaluation"][
            "selected_bounded_seed"
        ],
        "raw_outputs": {
            "audit": byte_record(paths["audit"], audit_data, workspace),
            "states": byte_record(paths["states"], states_data, workspace),
            "trades": byte_record(paths["trades"], trades_data, workspace),
            "improvement_paths": byte_record(paths["paths"], path_data, workspace),
        },
        "integrity": {
            "both_frozen_variants_complete": True,
            "state_rows": len(all_states),
            "trade_rows": len(all_trades),
            "improvement_path_rows": len(path_rows),
            "expected_improvement_path_rows": sum(
                int(precheck["variants"][variant]["nonzero_signals"])
                for variant in VARIANT_ORDER
            )
            * len(HORIZONS),
            "actual_balance_pnl_stress_and_spread_identities_passed": True,
            "rollover_boundaries": sum(
                int(row["rollover_boundaries"]) for row in all_trades
            ),
            "locked_2026_rows_loaded": 0,
            "broker_account_position_order_or_deal_queries": 0,
            "orders_or_trades": 0,
            "live_changed": False,
            "optimization_changed": False,
        },
        "next_authorized_action": (
            "persist byte-equal durable development result, acquire locked 2026 once, and confirm only the unchanged selected variant"
            if passers
            else (
                "close V1, retain only the bounded audit seed, recompare the complete autonomous method map, and do not execute the seed inside V1"
                if broad
                else "close V1 before locked 2026, EA and MT5, then recompare the complete autonomous method map"
            )
        ),
    }
    result_data = json_bytes(result)
    atomic_write_outputs(
        [
            (paths["audit"], audit_data),
            (paths["states"], states_data),
            (paths["trades"], trades_data),
            (paths["paths"], path_data),
            (paths["result"], result_data),
        ],
        paths["result"],
    )
    return result


def verify_recorded_development_result(
    workspace: Path,
) -> tuple[dict[str, Any], Path]:
    durable = (
        workspace
        / "lab"
        / "research"
        / FAMILY
        / "evidence"
        / "INDEPENDENT_LONDON_FX_FIX_PRESSURE_ADAPTER_CHALLENGE_V1_DEVELOPMENT_RESULT.json"
    )
    raw = output_paths(workspace)["result"]
    if not durable.is_file() or not raw.is_file() or sha256(durable) != sha256(raw):
        raise RuntimeError("confirmation requires byte-equal raw and durable result")
    result = read_json(durable)
    if result.get("status") != "VALID_DEVELOPMENT_COMPLETE_ONE_SELECTED_PASSER":
        raise RuntimeError("confirmation requires one selected development passer")
    if result.get("selected_variant") not in VARIANT_ORDER:
        raise RuntimeError("development selected variant is invalid")
    for record in result.get("raw_outputs", {}).values():
        path = workspace / str(record["path"])
        if (
            not path.is_file()
            or path.stat().st_size != int(record["bytes"])
            or sha256(path) != str(record["sha256"])
        ):
            raise RuntimeError("recorded development output authority mismatch")
    return result, durable


def whole_gates(metrics: dict[str, Any]) -> dict[str, bool]:
    epochs = metrics["epoch_metrics"]
    recovery = metrics["robust_recovery"]
    gates = {
        "locked_2026_actual_positive": float(epochs["2026"]["actual_net_usd"]) > 0.0,
        "locked_2026_stressed_positive": float(epochs["2026"]["stressed_net_usd"])
        > 0.0,
        "every_epoch_actual_and_stressed_positive": all(
            float(epochs[str(year)]["actual_net_usd"]) > 0.0
            and float(epochs[str(year)]["stressed_net_usd"]) > 0.0
            for year in (2024, 2025, 2026)
        ),
        "whole_actual_strictly_above_409_81": float(metrics["actual_net_usd"])
        > WHOLE_ACTUAL_GATE,
        "whole_stressed_strictly_above_367_818": float(metrics["stressed_net_usd"])
        > WHOLE_STRESS_GATE,
        "whole_drawdown_at_most_37_39_pct": float(
            metrics["actual_closed_balance_drawdown_pct"]
        )
        <= DRAWDOWN_GATE_PCT,
        "whole_robust_recovery_strictly_above_3_295860215": (
            bool(metrics["robust_recovery_unbounded_positive"])
            or (recovery is not None and float(recovery) > ROBUST_RECOVERY_GATE)
        ),
        "accepted_starts_per_active_date_at_least_3": float(
            metrics["accepted_starts_per_portfolio_active_date"]
        )
        >= TURNOVER_GATE,
        "locked_2026_starts_at_least_75": int(epochs["2026"]["starts"])
        >= LOCKED_START_GATE,
        "symbol_breadth_at_least_3": int(metrics["symbol_breadth"])
        >= SYMBOL_BREADTH_GATE,
        "both_directions": set(metrics["direction_breadth"]) == {"LONG", "SHORT"},
    }
    gates["passed"] = all(gates.values())
    return gates


def native_decision_rows(
    opportunities: list[dict[str, Any]], whole_states: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    state_by_id = {str(row["signal_id"]): row for row in whole_states}
    output: list[dict[str, Any]] = []
    sequence = 0
    for opportunity in opportunities:
        if not opportunity["direction"]:
            continue
        sequence += 1
        state = state_by_id[str(opportunity["signal_id"])]
        output.append(
            {
                "schema_version": 1,
                "decision_sequence": sequence,
                "family": FAMILY,
                "variant": opportunity["variant"],
                "signal_id": opportunity["signal_id"],
                "symbol": opportunity["symbol"],
                "direction": opportunity["direction"],
                "decision_time_utc": iso_utc(opportunity["decision_time_utc"]),
                "entry_time_utc": iso_utc(opportunity["entry_time_utc"]),
                "entry_raw_time": opportunity["entry_raw_time"],
                "atr20": clean_float(opportunity["atr20"]),
                "risk_distance": clean_float(opportunity["risk_distance"]),
                "entry_spread_points_observed": clean_float(
                    opportunity["entry_spread_points"]
                ),
                "held_m1_bars": opportunity["held_bars"],
                "time_exit_local": minute_label(int(opportunity["exit_minute"])),
                "proxy_admission_status_nonbinding_native": state["admission_status"],
            }
        )
    return output


def run_confirmation(workspace: Path, script_path: Path) -> dict[str, Any]:
    authorities = verify_authorities(workspace)
    freeze_path = (
        workspace
        / "lab"
        / "research"
        / FAMILY
        / "evidence"
        / "INDEPENDENT_LONDON_FX_FIX_PRESSURE_ADAPTER_CHALLENGE_V1_IMPLEMENTATION_FREEZE.json"
    )
    freeze = verify_freeze(freeze_path, script_path, workspace)
    development, durable_path = verify_recorded_development_result(workspace)
    selected = str(development["selected_variant"])
    frames, specs, complete_receipt, loading = load_complete_sources(workspace)
    events, common_dates, geometry = build_event_surface(frames)
    whole_dates = [
        day
        for day in common_dates
        if day >= date(2024, 1, 1) and day < date(2026, 8, 1)
    ]
    locked_dates = [day for day in whole_dates if day.year == 2026]
    if not locked_dates:
        raise RuntimeError("confirmation has no locked complete dates")
    opportunities = build_opportunities(
        events,
        whole_dates,
        specs,
        set(geometry["month_end_dates"]),
        set(geometry["quarter_end_dates"]),
    )
    development_dates = [day for day in whole_dates if day.year in (2024, 2025)]
    replay_metrics, _, _ = simulate_variant(
        selected,
        events,
        specs,
        [
            row
            for row in opportunities[selected]
            if row["event_date"].year in (2024, 2025)
        ],
        development_dates,
        (2024, 2025),
    )
    replay_metrics["gates"] = development_gates(replay_metrics)
    recorded_metrics = next(
        (
            row
            for row in development.get("variant_results", [])
            if row.get("variant") == selected
        ),
        None,
    )
    if replay_metrics != recorded_metrics:
        raise RuntimeError("combined source does not exactly replay selected development result")
    metrics, states, trades = simulate_variant(
        selected,
        events,
        specs,
        opportunities[selected],
        whole_dates,
        (2024, 2025, 2026),
    )
    gates = whole_gates(metrics)
    metrics["gates"] = gates
    output_root = workspace / "lab" / "artifacts" / "raw" / FAMILY / "confirmation"
    paths = {
        "result": output_root / "confirmation-result.json",
        "states": output_root / "confirmation-states.csv",
        "trades": output_root / "confirmation-trades.csv",
        "native": output_root / "native-decision-tape.csv",
    }
    states_data = csv_bytes(states)
    trades_data = csv_bytes(trades)
    native_rows = native_decision_rows(opportunities[selected], states) if gates["passed"] else []
    native_data = csv_bytes(native_rows) if gates["passed"] else b""
    result = {
        "schema": "zeta-next-independent-london-fx-fix-pressure-adapter-challenge-v1-confirmation-result",
        "status": (
            "VALID_WHOLE_PROXY_SURVIVOR_NATIVE_AUTHORIZED"
            if gates["passed"]
            else "VALID_LOCKED_OR_WHOLE_PROXY_NONCONFIRMATION_NO_NATIVE"
        ),
        "family": FAMILY,
        "selected_variant": selected,
        "authorities": authorities,
        "implementation_freeze": authority_record(freeze_path, workspace),
        "development_result": authority_record(durable_path, workspace),
        "complete_source_receipt": authority_record(
            workspace
            / "lab"
            / "artifacts"
            / "raw"
            / FAMILY
            / "input"
            / "COMPLETE_ACQUISITION_RECEIPT.json",
            workspace,
        ),
        "source_loading": loading,
        "complete_event_dates": len(whole_dates),
        "locked_complete_event_dates": len(locked_dates),
        "whole_metrics": metrics,
        "outputs": {
            "states": byte_record(paths["states"], states_data, workspace),
            "trades": byte_record(paths["trades"], trades_data, workspace),
            "native_decision_tape": (
                byte_record(paths["native"], native_data, workspace)
                if gates["passed"]
                else None
            ),
        },
        "native_authorized": bool(gates["passed"]),
        "proxy_has_victory_or_live_authority": False,
        "next_authorized_action": (
            "freeze the byte-pinned decision tape, implement the self-contained EA, compile and run one dedicated-Portable native real-tick candidate path"
            if gates["passed"]
            else "close V1 before EA and MT5"
        ),
    }
    result_data = json_bytes(result)
    outputs = [
        (paths["states"], states_data),
        (paths["trades"], trades_data),
    ]
    if gates["passed"]:
        outputs.append((paths["native"], native_data))
    outputs.append((paths["result"], result_data))
    atomic_write_outputs(outputs, paths["result"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", required=True, choices=("precheck", "development", "confirmation")
    )
    parser.add_argument("--workspace", type=Path)
    args = parser.parse_args()
    script_path = Path(__file__).absolute()
    workspace = (
        args.workspace.absolute() if args.workspace is not None else script_path.parents[4]
    )
    expected_script = workspace / "lab" / "research" / FAMILY / "adapter" / "run_adapter.py"
    if script_path != expected_script:
        raise RuntimeError(f"unexpected adapter path: {script_path}")
    if args.mode == "precheck":
        result = run_precheck(workspace, script_path)
    elif args.mode == "development":
        result = run_development(workspace, script_path)
    else:
        result = run_confirmation(workspace, script_path)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
