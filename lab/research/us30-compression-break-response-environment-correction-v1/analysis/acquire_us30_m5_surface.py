from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import MetaTrader5 as mt5


FAMILY = "us30-compression-break-response-environment-correction-v1"
ROOT = Path(__file__).resolve().parents[4]
RUNTIME_ROOT = ROOT / "lab" / "runtime" / "cbrec122-portable"
TERMINAL = RUNTIME_ROOT / "terminal64.exe"
OUTPUT_ROOT = ROOT / "lab" / "artifacts" / "raw" / FAMILY / "input"
BAR_PATH = OUTPUT_ROOT / "US30_M5_BARS_20220725_20260731.csv"
SPEC_PATH = OUTPUT_ROOT / "US30_SYMBOL_SPEC_V1.json"
ANCHOR_PATH = OUTPUT_ROOT / "UNIT029_P1_SIGNAL_STRUCTURE.csv"
PARENT_OPPORTUNITIES = (
    ROOT
    / "lab"
    / "artifacts"
    / "backtests"
    / "us30-compression-break-response-v1"
    / "p1-integrity-invalid"
    / "opportunities.csv"
)
PARENT_OPPORTUNITIES_SHA256 = "B9709DEFA2E8CC56015036DA06AB8EE7FEB38EAFD0858D3A93C997A5775BC68E"

SYMBOL = "US30"
START_UTC = datetime(2022, 7, 25, 0, 0, 0, tzinfo=timezone.utc)
END_UTC = datetime(2026, 7, 31, 23, 59, 59, tzinfo=timezone.utc)
BAR_COLUMNS = (
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
ANCHOR_COLUMNS = (
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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def finite_positive(value: float) -> bool:
    return math.isfinite(value) and value > 0.0


def read_parent_structure() -> list[tuple[str, ...]]:
    require(PARENT_OPPORTUNITIES.is_file(), f"parent P1 opportunities missing: {PARENT_OPPORTUNITIES}")
    require(
        sha256(PARENT_OPPORTUNITIES) == PARENT_OPPORTUNITIES_SHA256,
        "parent P1 opportunities differ from the frozen Unit 029 result",
    )
    selected: list[tuple[str, ...]] = []
    with PARENT_OPPORTUNITIES.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = tuple(reader.fieldnames or ())
        require(all(name in fields for name in ANCHOR_COLUMNS), "parent structural columns are incomplete")
        for row_number, row in enumerate(reader, start=2):
            values = tuple(row[name] for name in ANCHOR_COLUMNS)
            require(all(value is not None for value in values), f"missing parent structural field at row {row_number}")
            selected.append(values)
    require(len(selected) == 291, f"parent structural row count differs: {len(selected)}")
    return selected


def write_anchor(selected: list[tuple[str, ...]]) -> dict[str, object]:
    temp_path = ANCHOR_PATH.with_suffix(ANCHOR_PATH.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(ANCHOR_COLUMNS)
        writer.writerows(selected)
    os.replace(temp_path, ANCHOR_PATH)
    return {
        "anchor_rows": len(selected),
        "anchor_columns": len(ANCHOR_COLUMNS),
        "anchor_path": str(ANCHOR_PATH.relative_to(ROOT)).replace("\\", "/"),
        "anchor_bytes": ANCHOR_PATH.stat().st_size,
        "anchor_sha256": sha256(ANCHOR_PATH),
        "economic_columns_present": False,
    }


def write_bars(rates: object) -> dict[str, object]:
    epochs: list[int] = []
    positive_tick_volume_rows = 0
    temp_path = BAR_PATH.with_suffix(BAR_PATH.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(BAR_COLUMNS)
        for rate in rates:
            epoch = int(rate["time"])
            ohlc = tuple(float(rate[name]) for name in ("open", "high", "low", "close"))
            require(all(finite_positive(value) for value in ohlc), f"nonpositive or nonfinite OHLC at epoch {epoch}")
            require(not epochs or epoch > epochs[-1], f"non-increasing epoch at {epoch}")
            tick_volume = int(rate["tick_volume"])
            spread = int(rate["spread"])
            real_volume = int(rate["real_volume"])
            require(tick_volume >= 0 and spread >= 0 and real_volume >= 0, f"negative volume or spread at epoch {epoch}")
            if tick_volume > 0:
                positive_tick_volume_rows += 1
            epochs.append(epoch)
            writer.writerow(
                (
                    epoch,
                    datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y.%m.%d %H:%M:%S"),
                    *(repr(value) for value in ohlc),
                    tick_volume,
                    spread,
                    real_volume,
                )
            )
    os.replace(temp_path, BAR_PATH)
    require(bool(epochs), "bar export is empty")
    return {
        "rows": len(epochs),
        "first_time": datetime.fromtimestamp(epochs[0], timezone.utc).strftime("%Y.%m.%d %H:%M:%S"),
        "last_time": datetime.fromtimestamp(epochs[-1], timezone.utc).strftime("%Y.%m.%d %H:%M:%S"),
        "positive_tick_volume_rows": positive_tick_volume_rows,
        "unique_strictly_increasing_epoch": True,
        "finite_positive_ohlc": True,
        "nonnegative_volume_and_spread": True,
    }


def write_spec(info: object) -> None:
    payload = {
        "schema": "zeta-next-us30-compression-break-environment-correction-symbol-spec-v1",
        "symbol": SYMBOL,
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
    temp_path = SPEC_PATH.with_suffix(SPEC_PATH.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp_path, SPEC_PATH)


def acquire_rates() -> tuple[list[object], list[dict[str, object]]]:
    rows_by_epoch: dict[int, object] = {}
    chunks: list[dict[str, object]] = []
    cursor = START_UTC
    while cursor <= END_UTC:
        chunk_end = min(cursor + timedelta(days=90) - timedelta(seconds=1), END_UTC)
        part = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M5, cursor, chunk_end)
        require(part is not None, f"copy_rates_range failed for {cursor.isoformat()}..{chunk_end.isoformat()}: {mt5.last_error()}")
        require(len(part) > 0, f"copy_rates_range returned zero rows for {cursor.isoformat()}..{chunk_end.isoformat()}")
        duplicate_rows = 0
        for rate in part:
            epoch = int(rate["time"])
            if epoch in rows_by_epoch:
                duplicate_rows += 1
                previous = rows_by_epoch[epoch]
                require(all(previous[name] == rate[name] for name in rate.dtype.names), f"conflicting duplicate bar at epoch {epoch}")
            else:
                rows_by_epoch[epoch] = rate
        chunks.append(
            {
                "from_utc": cursor.isoformat(),
                "to_utc": chunk_end.isoformat(),
                "returned_rows": len(part),
                "duplicate_rows": duplicate_rows,
            }
        )
        cursor = chunk_end + timedelta(seconds=1)
    require(bool(rows_by_epoch), "chunked acquisition produced zero unique rows")
    return [rows_by_epoch[epoch] for epoch in sorted(rows_by_epoch)], chunks


def main() -> int:
    require(TERMINAL.is_file(), f"dedicated terminal missing: {TERMINAL}")
    require(not any(path.exists() for path in (BAR_PATH, SPEC_PATH, ANCHOR_PATH)), "frozen acquisition output already exists")
    selected = read_parent_structure()

    initialized = False
    try:
        initialized = bool(mt5.initialize(str(TERMINAL), timeout=120_000, portable=True))
        require(initialized, f"MetaTrader5 initialize failed: {mt5.last_error()}")
        require(mt5.symbol_select(SYMBOL, True), f"symbol_select failed for {SYMBOL}: {mt5.last_error()}")
        info = mt5.symbol_info(SYMBOL)
        require(info is not None, f"symbol_info failed for {SYMBOL}: {mt5.last_error()}")
        rates, chunks = acquire_rates()
    finally:
        if initialized:
            mt5.shutdown()

    require(len(rates) > 0, "copy_rates_range returned zero rows")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    anchor_summary = write_anchor(selected)
    bar_summary = write_bars(rates)
    write_spec(info)
    summary = {
        "python": sys.version.split()[0],
        "metatrader5_package": mt5.__version__,
        "runtime": str(RUNTIME_ROOT.relative_to(ROOT)).replace("\\", "/") + "/",
        "terminal_sha256": sha256(TERMINAL),
        "symbol": SYMBOL,
        "timeframe": "M5",
        "request_from_utc": START_UTC.isoformat(),
        "request_to_utc": END_UTC.isoformat(),
        "bar_path": str(BAR_PATH.relative_to(ROOT)).replace("\\", "/"),
        "bar_bytes": BAR_PATH.stat().st_size,
        "bar_sha256": sha256(BAR_PATH),
        "spec_path": str(SPEC_PATH.relative_to(ROOT)).replace("\\", "/"),
        "spec_bytes": SPEC_PATH.stat().st_size,
        "spec_sha256": sha256(SPEC_PATH),
        "parent_opportunities_sha256": sha256(PARENT_OPPORTUNITIES),
        **anchor_summary,
        **bar_summary,
        "copy_rates_range_calls": len(chunks),
        "copy_rates_range_chunks": chunks,
        "api_calls": ["initialize", "symbol_select", "symbol_info", f"copy_rates_range x {len(chunks)}", "shutdown"],
        "economic_columns_selected_or_emitted": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
