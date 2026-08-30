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
INPUT_ROOT = ROOT / "lab" / "artifacts" / "raw" / FAMILY / "input"
BAR_PATH = INPUT_ROOT / "US30_M5_BARS_20220725_20260731.csv"
OUTPUT_PATH = INPUT_ROOT / "US30_M5_FIRST_TICKS_20220725_20260731.csv"
SYMBOL = "US30"
START_UTC = datetime(2022, 7, 25, 0, 0, 0, tzinfo=timezone.utc)
END_EXCLUSIVE_UTC = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
BAR_SECONDS = 300
FIRST_PERIOD_EPOCH = int(datetime(2022, 8, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_bar_epochs() -> list[int]:
    require(BAR_PATH.is_file(), f"bar surface missing: {BAR_PATH}")
    epochs: list[int] = []
    with BAR_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        require("time_epoch" in tuple(reader.fieldnames or ()), "bar epoch column missing")
        for row_number, row in enumerate(reader, start=2):
            epoch = int(row["time_epoch"])
            require(not epochs or epoch > epochs[-1], f"bar epochs not increasing at row {row_number}")
            epochs.append(epoch)
    require(bool(epochs), "bar surface is empty")
    return epochs


def acquire_first_ticks(bar_epochs: set[int]) -> tuple[dict[int, tuple[int, int, float, float, int]], list[dict[str, object]], int, int, int]:
    first_by_bar: dict[int, tuple[int, int, float, float, int]] = {}
    chunks: list[dict[str, object]] = []
    total_valid_ticks = 0
    same_millisecond_followups = 0
    different_same_millisecond_followups = 0
    cursor = START_UTC
    while cursor < END_EXCLUSIVE_UTC:
        chunk_end_exclusive = min(cursor + timedelta(days=30), END_EXCLUSIVE_UTC)
        request_end = chunk_end_exclusive - timedelta(microseconds=1)
        ticks = mt5.copy_ticks_range(SYMBOL, cursor, request_end, mt5.COPY_TICKS_ALL)
        require(ticks is not None, f"copy_ticks_range failed for {cursor.isoformat()}..{request_end.isoformat()}: {mt5.last_error()}")
        require(len(ticks) > 0, f"copy_ticks_range returned zero rows for {cursor.isoformat()}..{request_end.isoformat()}")
        valid_ticks = 0
        eligible_ticks = 0
        updated_first_ticks = 0
        previous_time_msc: int | None = None
        for tick in ticks:
            time_msc = int(tick["time_msc"])
            require(previous_time_msc is None or time_msc >= previous_time_msc, "copy_ticks_range order is not nondecreasing")
            previous_time_msc = time_msc
            bid = float(tick["bid"])
            ask = float(tick["ask"])
            if not (math.isfinite(bid) and math.isfinite(ask) and bid > 0.0 and ask >= bid):
                continue
            valid_ticks += 1
            tick_epoch = int(tick["time"])
            bar_epoch = tick_epoch - tick_epoch % BAR_SECONDS
            if bar_epoch not in bar_epochs:
                continue
            eligible_ticks += 1
            flags = int(tick["flags"])
            candidate = (time_msc, tick_epoch, bid, ask, flags)
            previous = first_by_bar.get(bar_epoch)
            if previous is None or candidate[0] < previous[0]:
                first_by_bar[bar_epoch] = candidate
                updated_first_ticks += 1
            elif candidate[0] == previous[0]:
                same_millisecond_followups += 1
                if candidate[1:] != previous[1:]:
                    different_same_millisecond_followups += 1
        total_valid_ticks += valid_ticks
        chunks.append(
            {
                "from_utc": cursor.isoformat(),
                "to_utc": request_end.isoformat(),
                "returned_ticks": len(ticks),
                "valid_bid_ask_ticks": valid_ticks,
                "ticks_in_acquired_bar_epochs": eligible_ticks,
                "first_tick_updates": updated_first_ticks,
            }
        )
        cursor = chunk_end_exclusive
    return first_by_bar, chunks, total_valid_ticks, same_millisecond_followups, different_same_millisecond_followups


def write_first_ticks(bar_epochs: list[int], first_by_bar: dict[int, tuple[int, int, float, float, int]]) -> dict[str, object]:
    missing = [epoch for epoch in bar_epochs if epoch not in first_by_bar]
    available = [epoch for epoch in bar_epochs if epoch in first_by_bar]
    require(bool(available), "no M5 bar has a valid first bid/ask tick")
    temp_path = OUTPUT_PATH.with_suffix(OUTPUT_PATH.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("bar_epoch", "bar_time", "tick_epoch", "tick_time", "time_msc", "bid", "ask", "spread", "flags"))
        for bar_epoch in available:
            time_msc, tick_epoch, bid, ask, flags = first_by_bar[bar_epoch]
            writer.writerow(
                (
                    bar_epoch,
                    datetime.fromtimestamp(bar_epoch, timezone.utc).strftime("%Y.%m.%d %H:%M:%S"),
                    tick_epoch,
                    datetime.fromtimestamp(tick_epoch, timezone.utc).strftime("%Y.%m.%d %H:%M:%S"),
                    time_msc,
                    repr(bid),
                    repr(ask),
                    repr(ask - bid),
                    flags,
                )
            )
    os.replace(temp_path, OUTPUT_PATH)
    return {
        "rows": len(available),
        "first_bar_time": datetime.fromtimestamp(available[0], timezone.utc).strftime("%Y.%m.%d %H:%M:%S"),
        "last_bar_time": datetime.fromtimestamp(available[-1], timezone.utc).strftime("%Y.%m.%d %H:%M:%S"),
        "bars_without_available_first_valid_bid_ask": len(missing),
        "pre_period_bars_without_available_first_valid_bid_ask": sum(epoch < FIRST_PERIOD_EPOCH for epoch in missing),
        "fixed_period_bars_without_available_first_valid_bid_ask": sum(epoch >= FIRST_PERIOD_EPOCH for epoch in missing),
        "first_missing_bar_times": [datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y.%m.%d %H:%M:%S") for epoch in missing[:10]],
        "last_missing_bar_times": [datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y.%m.%d %H:%M:%S") for epoch in missing[-10:]],
        "coverage_sufficiency_deferred_to_structural_and_pricing_use": True,
    }


def main() -> int:
    require(TERMINAL.is_file(), f"dedicated terminal missing: {TERMINAL}")
    require(not OUTPUT_PATH.exists(), "first-tick output already exists")
    bar_epochs = read_bar_epochs()

    initialized = False
    try:
        initialized = bool(mt5.initialize(str(TERMINAL), timeout=120_000, portable=True))
        require(initialized, f"MetaTrader5 initialize failed: {mt5.last_error()}")
        require(mt5.symbol_select(SYMBOL, True), f"symbol_select failed for {SYMBOL}: {mt5.last_error()}")
        first_by_bar, chunks, total_valid_ticks, same_millisecond_followups, different_same_millisecond_followups = acquire_first_ticks(set(bar_epochs))
    finally:
        if initialized:
            mt5.shutdown()

    summary = write_first_ticks(bar_epochs, first_by_bar)
    payload = {
        "python": sys.version.split()[0],
        "metatrader5_package": mt5.__version__,
        "runtime": str(RUNTIME_ROOT.relative_to(ROOT)).replace("\\", "/") + "/",
        "terminal_sha256": sha256(TERMINAL),
        "symbol": SYMBOL,
        "request_from_utc": START_UTC.isoformat(),
        "request_to_exclusive_utc": END_EXCLUSIVE_UTC.isoformat(),
        "copy_ticks_range_calls": len(chunks),
        "copy_ticks_range_chunks": chunks,
        "total_valid_bid_ask_ticks": total_valid_ticks,
        "same_millisecond_followups_after_preserved_first_returned_tick": same_millisecond_followups,
        "different_same_millisecond_followups_after_preserved_first_returned_tick": different_same_millisecond_followups,
        "same_millisecond_policy": "Preserve the first valid row in the nondecreasing copy_ticks_range return order, matching the first OnTick delivery; later rows sharing that millisecond do not replace it.",
        "bar_surface_sha256": sha256(BAR_PATH),
        "output_path": str(OUTPUT_PATH.relative_to(ROOT)).replace("\\", "/"),
        "output_bytes": OUTPUT_PATH.stat().st_size,
        "output_sha256": sha256(OUTPUT_PATH),
        **summary,
        "api_calls": ["initialize", "symbol_select", f"copy_ticks_range x {len(chunks)}", "shutdown"],
        "account_position_order_deal_history_margin_check_send_or_trade_calls": 0,
        "economic_columns_selected_or_emitted": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
