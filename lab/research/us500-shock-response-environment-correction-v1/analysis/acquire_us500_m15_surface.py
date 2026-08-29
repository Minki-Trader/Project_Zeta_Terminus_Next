from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import MetaTrader5 as mt5


FAMILY = "us500-shock-response-environment-correction-v1"
ROOT = Path(__file__).resolve().parents[4]
RUNTIME_ROOT = ROOT / "lab" / "runtime" / "ussr105-portable"
TERMINAL = RUNTIME_ROOT / "terminal64.exe"
OUTPUT_ROOT = ROOT / "lab" / "artifacts" / "raw" / FAMILY / "input"
BAR_PATH = OUTPUT_ROOT / "US500_M15_BARS_20220701_20260821.csv"
SPEC_PATH = OUTPUT_ROOT / "US500_SYMBOL_SPEC_V1.json"

SYMBOL = "US500"
START_UTC = datetime(2022, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
END_UTC = datetime(2026, 8, 21, 23, 59, 59, tzinfo=timezone.utc)
COLUMNS = (
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def finite_positive(value: float) -> bool:
    return math.isfinite(value) and value > 0.0


def write_bars(rates: object) -> dict[str, object]:
    epochs: list[int] = []
    positive_tick_volume_rows = 0
    temp_path = BAR_PATH.with_suffix(BAR_PATH.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(COLUMNS)
        for rate in rates:
            epoch = int(rate["time"])
            ohlc = tuple(float(rate[name]) for name in ("open", "high", "low", "close"))
            if not all(finite_positive(value) for value in ohlc):
                raise RuntimeError(f"nonpositive or nonfinite OHLC at epoch {epoch}")
            if epochs and epoch <= epochs[-1]:
                raise RuntimeError(f"non-increasing epoch at {epoch}")
            tick_volume = int(rate["tick_volume"])
            spread = int(rate["spread"])
            real_volume = int(rate["real_volume"])
            if tick_volume < 0 or spread < 0 or real_volume < 0:
                raise RuntimeError(f"negative volume or spread at epoch {epoch}")
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
        "schema": "zeta-next-us500-shock-response-environment-correction-symbol-spec-v1",
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


def main() -> int:
    if not TERMINAL.is_file():
        raise RuntimeError(f"dedicated terminal missing: {TERMINAL}")
    if BAR_PATH.exists() or SPEC_PATH.exists():
        raise RuntimeError("frozen acquisition output already exists; do not overwrite it")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    initialized = False
    try:
        initialized = bool(mt5.initialize(str(TERMINAL), timeout=120_000, portable=True))
        if not initialized:
            raise RuntimeError(f"MetaTrader5 initialize failed: {mt5.last_error()}")
        if not mt5.symbol_select(SYMBOL, True):
            raise RuntimeError(f"symbol_select failed for {SYMBOL}: {mt5.last_error()}")
        info = mt5.symbol_info(SYMBOL)
        if info is None:
            raise RuntimeError(f"symbol_info failed for {SYMBOL}: {mt5.last_error()}")
        rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M15, START_UTC, END_UTC)
        if rates is None:
            raise RuntimeError(f"copy_rates_range failed for {SYMBOL}: {mt5.last_error()}")
    finally:
        if initialized:
            mt5.shutdown()

    if len(rates) == 0:
        raise RuntimeError("copy_rates_range returned zero rows")
    bar_summary = write_bars(rates)
    write_spec(info)
    summary = {
        "python": sys.version.split()[0],
        "metatrader5_package": mt5.__version__,
        "runtime": str(RUNTIME_ROOT.relative_to(ROOT)).replace("\\", "/") + "/",
        "terminal_sha256": sha256(TERMINAL),
        "symbol": SYMBOL,
        "timeframe": "M15",
        "request_from_utc": START_UTC.isoformat(),
        "request_to_utc": END_UTC.isoformat(),
        "bar_path": str(BAR_PATH.relative_to(ROOT)).replace("\\", "/"),
        "bar_bytes": BAR_PATH.stat().st_size,
        "bar_sha256": sha256(BAR_PATH),
        "spec_path": str(SPEC_PATH.relative_to(ROOT)).replace("\\", "/"),
        "spec_bytes": SPEC_PATH.stat().st_size,
        "spec_sha256": sha256(SPEC_PATH),
        **bar_summary,
        "api_calls": ["initialize", "symbol_select", "symbol_info", "copy_rates_range", "shutdown"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
