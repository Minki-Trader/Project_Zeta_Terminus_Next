from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import MetaTrader5 as mt5
import numpy as np
import pandas as pd


FAMILY = "dd20-dual-portfolio-internal-formula-lattice-proxy-v1"
SCRIPT_PATH = Path(__file__).resolve()
CAMPAIGN_ROOT = SCRIPT_PATH.parents[1]
REPOSITORY_ROOT = SCRIPT_PATH.parents[4]
CONTRACT_PATH = CAMPAIGN_ROOT / "config" / "campaign-contract.json"
RUNTIME_ROOT = (
    REPOSITORY_ROOT
    / "optimization"
    / "runtime"
    / f"{FAMILY}-portable"
)
TERMINAL_PATH = RUNTIME_ROOT / "terminal64.exe"
OUTPUT_ROOT = (
    REPOSITORY_ROOT
    / "optimization"
    / "artifacts"
    / "raw"
    / FAMILY
    / "market"
)
RECEIPT_PATH = OUTPUT_ROOT / "acquisition-receipt.json"

START_UTC = datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
END_UTC = datetime(2026, 7, 31, 23, 59, 59, tzinfo=timezone.utc)
SERIES = (
    ("US30", "M1", mt5.TIMEFRAME_M1),
    ("US30", "M30", mt5.TIMEFRAME_M30),
    ("US30", "H1", mt5.TIMEFRAME_H1),
    ("US30", "D1", mt5.TIMEFRAME_D1),
    ("US100", "M1", mt5.TIMEFRAME_M1),
    ("US100", "M15", mt5.TIMEFRAME_M15),
    ("US100", "H1", mt5.TIMEFRAME_H1),
    ("US500", "H1", mt5.TIMEFRAME_H1),
)
RATE_COLUMNS = (
    "time",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def relative(path: Path) -> str:
    return str(path.relative_to(REPOSITORY_ROOT)).replace("\\", "/")


def runtime_inventory() -> dict[str, Any]:
    files = sorted(path for path in RUNTIME_ROOT.rglob("*") if path.is_file())
    links = [path for path in RUNTIME_ROOT.rglob("*") if path.is_symlink()]
    manifest_lines: list[str] = []
    total_bytes = 0
    for path in files:
        size = path.stat().st_size
        total_bytes += size
        manifest_lines.append(
            f"{path.relative_to(RUNTIME_ROOT).as_posix()}|{size}|{sha256(path)}"
        )
    payload = ("\n".join(manifest_lines) + "\n").encode("utf-8")
    return {
        "files": len(files),
        "bytes": total_bytes,
        "links": len(links),
        "manifest_sha256": hashlib.sha256(payload).hexdigest().upper(),
        "terminal_bytes": TERMINAL_PATH.stat().st_size,
        "terminal_sha256": sha256(TERMINAL_PATH),
    }


def symbol_spec(info: Any) -> dict[str, Any]:
    return {
        "name": str(info.name),
        "description": str(info.description),
        "digits": int(info.digits),
        "point": float(info.point),
        "trade_tick_size": float(info.trade_tick_size),
        "trade_tick_value": float(info.trade_tick_value),
        "trade_tick_value_profit": float(info.trade_tick_value_profit),
        "trade_tick_value_loss": float(info.trade_tick_value_loss),
        "trade_contract_size": float(info.trade_contract_size),
        "volume_min": float(info.volume_min),
        "volume_max": float(info.volume_max),
        "volume_step": float(info.volume_step),
        "trade_stops_level": int(info.trade_stops_level),
        "trade_freeze_level": int(info.trade_freeze_level),
        "spread": int(info.spread),
        "spread_float": bool(info.spread_float),
        "currency_base": str(info.currency_base),
        "currency_profit": str(info.currency_profit),
        "currency_margin": str(info.currency_margin),
        "trade_calc_mode": int(info.trade_calc_mode),
    }


def write_series(symbol: str, label: str, rates: Any) -> dict[str, Any]:
    frame = pd.DataFrame(rates)
    missing = sorted(set(RATE_COLUMNS) - set(frame.columns))
    if missing:
        raise RuntimeError(f"{symbol}_{label} missing fields: {missing}")
    frame = frame.loc[:, RATE_COLUMNS].copy()
    frame["time"] = frame["time"].astype("int64")
    if frame.empty:
        raise RuntimeError(f"{symbol}_{label} returned zero rows")
    raw_rows = len(frame)
    duplicate_rows = int(frame["time"].duplicated(keep=False).sum())
    if duplicate_rows:
        duplicated = frame.loc[frame["time"].duplicated(keep=False)]
        conflicting = duplicated.groupby("time", sort=False).nunique(dropna=False)
        if (conflicting > 1).any(axis=None):
            raise RuntimeError(f"{symbol}_{label} has conflicting duplicate bars")
    frame.sort_values("time", kind="stable", inplace=True)
    frame.drop_duplicates(subset="time", keep="first", inplace=True)
    frame.reset_index(drop=True, inplace=True)
    if not frame["time"].is_monotonic_increasing or frame["time"].duplicated().any():
        raise RuntimeError(f"{symbol}_{label} timestamps remain non-unique")
    prices = frame.loc[:, ["open", "high", "low", "close"]].to_numpy(dtype=float)
    if not np.isfinite(prices).all() or not (prices > 0.0).all():
        raise RuntimeError(f"{symbol}_{label} contains invalid OHLC")
    if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
        raise RuntimeError(f"{symbol}_{label} contains invalid high")
    if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
        raise RuntimeError(f"{symbol}_{label} contains invalid low")
    if (frame[["tick_volume", "spread", "real_volume"]] < 0).any(axis=None):
        raise RuntimeError(f"{symbol}_{label} contains a negative volume or spread")
    path = OUTPUT_ROOT / f"{symbol}_{label}.parquet"
    temp = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temp, engine="pyarrow", compression="zstd", index=False)
    os.replace(temp, path)
    first_epoch = int(frame["time"].iloc[0])
    last_epoch = int(frame["time"].iloc[-1])
    return {
        "id": f"{symbol}_{label}",
        "path": relative(path),
        "raw_chunk_rows": int(raw_rows),
        "exact_duplicate_chunk_rows_removed": int(raw_rows - len(frame)),
        "rows": int(len(frame)),
        "first_utc": datetime.fromtimestamp(first_epoch, timezone.utc).isoformat(),
        "last_utc": datetime.fromtimestamp(last_epoch, timezone.utc).isoformat(),
        "positive_spread_rows": int((frame["spread"] > 0).sum()),
        "median_spread_points": float(frame["spread"].median()),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def copy_rates_chunked(symbol: str, timeframe: int) -> Any:
    chunks: list[Any] = []
    cursor = START_UTC
    while cursor <= END_UTC:
        chunk_end = min(cursor + timedelta(days=60) - timedelta(seconds=1), END_UTC)
        rates = mt5.copy_rates_range(symbol, timeframe, cursor, chunk_end)
        if rates is None:
            raise RuntimeError(
                f"copy_rates_range failed for {symbol} at "
                f"{cursor.isoformat()}..{chunk_end.isoformat()}: {mt5.last_error()}"
            )
        if len(rates) > 0:
            chunks.append(rates)
        cursor = chunk_end + timedelta(seconds=1)
    if not chunks:
        raise RuntimeError(f"copy_rates_range returned zero rows for {symbol}")
    return np.concatenate(chunks)


def main() -> int:
    if not TERMINAL_PATH.is_file():
        raise RuntimeError(f"dedicated terminal missing: {TERMINAL_PATH}")
    if RECEIPT_PATH.exists():
        raise RuntimeError("frozen market snapshot already exists; do not overwrite it")
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if contract["campaign"] != FAMILY:
        raise RuntimeError("campaign contract identity mismatch")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    pre_runtime = runtime_inventory()
    initialized = False
    series_payload: list[dict[str, Any]] = []
    specs: dict[str, Any] = {}
    try:
        initialized = bool(
            mt5.initialize(str(TERMINAL_PATH), timeout=120_000, portable=True)
        )
        if not initialized:
            raise RuntimeError(f"MetaTrader5 initialize failed: {mt5.last_error()}")
        for symbol in ("US30", "US100", "US500"):
            if not mt5.symbol_select(symbol, True):
                raise RuntimeError(f"symbol_select failed for {symbol}: {mt5.last_error()}")
            info = mt5.symbol_info(symbol)
            if info is None:
                raise RuntimeError(f"symbol_info failed for {symbol}: {mt5.last_error()}")
            specs[symbol] = symbol_spec(info)
        for symbol, label, timeframe in SERIES:
            rates = copy_rates_chunked(symbol, timeframe)
            series_payload.append(write_series(symbol, label, rates))
    finally:
        if initialized:
            mt5.shutdown()

    receipt = {
        "schema": "zeta-dd20-dual-portfolio-market-acquisition-receipt-v1",
        "campaign": FAMILY,
        "contract_path": relative(CONTRACT_PATH),
        "contract_bytes": CONTRACT_PATH.stat().st_size,
        "contract_sha256": sha256(CONTRACT_PATH),
        "runtime": relative(RUNTIME_ROOT) + "/",
        "runtime_pre_initialization": pre_runtime,
        "python": sys.version.split()[0],
        "metatrader5_package": mt5.__version__,
        "request_from_utc": START_UTC.isoformat(),
        "request_through_utc": END_UTC.isoformat(),
        "symbols": specs,
        "series": series_payload,
        "series_files": len(series_payload),
        "series_rows": sum(int(item["rows"]) for item in series_payload),
        "series_bytes": sum(int(item["bytes"]) for item in series_payload),
        "api_calls": [
            "initialize",
            "symbol_select",
            "symbol_info",
            "copy_rates_range",
            "shutdown",
        ],
        "account_position_order_deal_queries": 0,
    }
    temp_receipt = RECEIPT_PATH.with_suffix(RECEIPT_PATH.suffix + ".tmp")
    temp_receipt.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temp_receipt, RECEIPT_PATH)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
