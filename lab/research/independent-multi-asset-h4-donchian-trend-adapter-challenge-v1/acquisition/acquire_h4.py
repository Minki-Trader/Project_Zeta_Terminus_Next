from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import MetaTrader5 as mt5
import pandas as pd


FAMILY = "independent-multi-asset-h4-donchian-trend-adapter-challenge-v1"
SYMBOLS = ("AUDUSD", "EURUSD", "GBPUSD", "NZDUSD", "US100", "US30", "US500")
DEVELOPMENT_START = datetime(2022, 1, 1, tzinfo=UTC)
DEVELOPMENT_END = datetime(2026, 1, 1, tzinfo=UTC)
LOCKED_START = DEVELOPMENT_END
LOCKED_END = datetime(2026, 8, 1, tzinfo=UTC)
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
HISTORY_SYNC_TIMEOUT_SECONDS = 300
SUPPORTED_SWAP_MODES = {
    0: "DISABLED",
    1: "POINTS",
    4: "CURRENCY_DEPOSIT",
    5: "INTEREST_CURRENT",
    6: "INTEREST_OPEN",
}
ALL_SWAP_MODES = {
    0: "DISABLED",
    1: "POINTS",
    2: "CURRENCY_SYMBOL",
    3: "CURRENCY_MARGIN",
    4: "CURRENCY_DEPOSIT",
    5: "INTEREST_CURRENT",
    6: "INTEREST_OPEN",
    7: "REOPEN_CURRENT",
    8: "REOPEN_BID",
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
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def finite_float(value: object, field: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise RuntimeError(f"nonfinite symbol field: {field}")
    return number


def next_quarter(value: datetime) -> datetime:
    month = value.month + 3
    year = value.year
    if month > 12:
        month -= 12
        year += 1
    return datetime(year, month, 1, tzinfo=UTC)


def symbol_spec(symbol: str, fields: dict[str, Any]) -> dict[str, Any]:
    swap_code = int(fields.get("swap_mode"))
    return {
        "schema": "zeta-next-multi-asset-h4-symbol-spec-v1",
        "symbol": symbol,
        "name": str(fields.get("name")),
        "path": str(fields.get("path")),
        "description": str(fields.get("description")),
        "currency_base": str(fields.get("currency_base")),
        "currency_profit": str(fields.get("currency_profit")),
        "currency_margin": str(fields.get("currency_margin")),
        "digits": int(fields.get("digits")),
        "point": finite_float(fields.get("point"), "point"),
        "trade_tick_size": finite_float(
            fields.get("trade_tick_size"), "trade_tick_size"
        ),
        "trade_tick_value": finite_float(
            fields.get("trade_tick_value"), "trade_tick_value"
        ),
        "trade_tick_value_profit": finite_float(
            fields.get("trade_tick_value_profit"), "trade_tick_value_profit"
        ),
        "trade_tick_value_loss": finite_float(
            fields.get("trade_tick_value_loss"), "trade_tick_value_loss"
        ),
        "trade_contract_size": finite_float(
            fields.get("trade_contract_size"), "trade_contract_size"
        ),
        "volume_min": finite_float(fields.get("volume_min"), "volume_min"),
        "volume_step": finite_float(fields.get("volume_step"), "volume_step"),
        "volume_max": finite_float(fields.get("volume_max"), "volume_max"),
        "trade_mode": int(fields.get("trade_mode")),
        "trade_calc_mode": int(fields.get("trade_calc_mode")),
        "swap_mode": swap_code,
        "swap_mode_name": ALL_SWAP_MODES.get(swap_code, f"UNKNOWN_{swap_code}"),
        "swap_long": finite_float(fields.get("swap_long"), "swap_long"),
        "swap_short": finite_float(fields.get("swap_short"), "swap_short"),
        "swap_rollover3days": int(fields.get("swap_rollover3days")),
        "swap_mode_supported_by_declared_economics": swap_code
        in SUPPORTED_SWAP_MODES,
    }


def acquire_symbol(
    symbol: str,
    start: datetime,
    end_exclusive: datetime,
) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    frames: list[pd.DataFrame] = []
    receipts: list[dict[str, object]] = []
    cursor = start
    while cursor < end_exclusive:
        batch_end = min(next_quarter(cursor), end_exclusive)
        start_epoch = int(cursor.timestamp())
        end_epoch = int(batch_end.timestamp())
        deadline = time.monotonic() + HISTORY_SYNC_TIMEOUT_SECONDS
        last_observation = "no response"
        next_progress = time.monotonic() + 15
        while True:
            rates = mt5.copy_rates_range(
                symbol,
                mt5.TIMEFRAME_H4,
                cursor,
                datetime.fromtimestamp(batch_end.timestamp() - 1, tz=UTC),
            )
            if rates is None:
                frame = pd.DataFrame()
                last_observation = f"last_error={mt5.last_error()}"
            else:
                frame = pd.DataFrame(rates)
                missing = [name for name in RATE_COLUMNS if name not in frame.columns]
                if missing:
                    raise RuntimeError(f"missing {symbol} H4 columns: {missing}")
                frame = frame[
                    (frame["time"] >= start_epoch) & (frame["time"] < end_epoch)
                ].copy()
                if frame.empty:
                    last_observation = "zero in-range rows"
                else:
                    first_epoch = int(frame["time"].iloc[0])
                    last_epoch = int(frame["time"].iloc[-1])
                    last_observation = (
                        f"rows={len(frame)} first={first_epoch} last={last_epoch}"
                    )
                    boundary_slack = 10 * 24 * 60 * 60
                    if (
                        len(frame) >= 100
                        and first_epoch - start_epoch <= boundary_slack
                        and end_epoch - last_epoch <= boundary_slack
                    ):
                        frame = frame[list(RATE_COLUMNS)].copy()
                        break
            now = time.monotonic()
            if now >= deadline:
                raise RuntimeError(
                    f"history synchronization timed out for {symbol} "
                    f"{cursor.isoformat()} / {batch_end.isoformat()}: "
                    f"{last_observation}"
                )
            if now >= next_progress:
                print(
                    f"waiting for {symbol} H4 {cursor:%Y-%m}: "
                    f"{last_observation}",
                    flush=True,
                )
                next_progress = now + 15
            time.sleep(1)
        frames.append(frame)
        receipts.append(
            {
                "start_inclusive": cursor.isoformat().replace("+00:00", "Z"),
                "end_exclusive": batch_end.isoformat().replace("+00:00", "Z"),
                "rows": int(len(frame)),
                "first_raw_epoch": int(frame["time"].iloc[0]),
                "last_raw_epoch": int(frame["time"].iloc[-1]),
            }
        )
        print(
            f"acquired {symbol} H4 {cursor:%Y-%m}/{batch_end:%Y-%m}: "
            f"{len(frame)} rows",
            flush=True,
        )
        cursor = batch_end

    data = pd.concat(frames, ignore_index=True)
    start_epoch = int(start.timestamp())
    end_epoch = int(end_exclusive.timestamp())
    data = data[(data["time"] >= start_epoch) & (data["time"] < end_epoch)].copy()
    data.sort_values("time", kind="mergesort", inplace=True)
    data.reset_index(drop=True, inplace=True)
    minimum_rows = 3_000 if end_exclusive == DEVELOPMENT_END else 500
    if len(data) < minimum_rows:
        raise RuntimeError(f"insufficient {symbol} H4 rows: {len(data)}")
    if data["time"].duplicated().any() or not data["time"].is_monotonic_increasing:
        raise RuntimeError(f"duplicate or nonincreasing {symbol} H4 timestamps")
    if int(data["time"].iloc[0]) - start_epoch > 10 * 24 * 60 * 60:
        raise RuntimeError(f"first {symbol} H4 row is too far after request")
    if end_epoch - int(data["time"].iloc[-1]) > 10 * 24 * 60 * 60:
        raise RuntimeError(f"last {symbol} H4 row is too far before request end")
    for name in ("open", "high", "low", "close"):
        values = pd.to_numeric(data[name], errors="coerce")
        if not values.notna().all() or not values.map(math.isfinite).all():
            raise RuntimeError(f"nonfinite {symbol} H4 column: {name}")
        if not (values > 0).all():
            raise RuntimeError(f"nonpositive {symbol} H4 column: {name}")
    if not (data["high"] >= data[["open", "close", "low"]].max(axis=1)).all():
        raise RuntimeError(f"{symbol} H4 high invariant failed")
    if not (data["low"] <= data[["open", "close", "high"]].min(axis=1)).all():
        raise RuntimeError(f"{symbol} H4 low invariant failed")
    if (data["spread"] < 0).any() or (data["tick_volume"] < 0).any():
        raise RuntimeError(f"negative {symbol} H4 spread or volume")
    return data, receipts


def source_receipt(terminal: Path, fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "terminal_executable": str(terminal),
        "terminal_executable_bytes": terminal.stat().st_size,
        "terminal_executable_sha256": sha256(terminal),
        "terminal_version": list(mt5.version() or ()),
        "python_package_version": mt5.__version__,
        "terminal_company": str(fields.get("company")),
        "terminal_name": str(fields.get("name")),
        "terminal_path": str(fields.get("path")),
        "terminal_data_path": str(fields.get("data_path")),
        "connected": bool(fields.get("connected")),
        "server_authority": (
            "project-local original-broker session support copied from a stopped "
            "non-Master Lab Portable; account identifier and account state are not "
            "queried or persisted"
        ),
        "broker_account_position_order_or_deal_queries": 0,
        "existing_runtime_price_or_history_cache_reads": 0,
        "other_family_runtime_execution": False,
    }


def csv_receipt(
    staged_path: Path,
    logical_path: Path,
    workspace: Path,
    data: pd.DataFrame,
) -> dict[str, Any]:
    first_epoch = int(data["time"].iloc[0])
    last_epoch = int(data["time"].iloc[-1])
    return {
        "path": str(logical_path.relative_to(workspace)).replace("\\", "/"),
        "columns": list(data.columns),
        "rows": int(len(data)),
        "first_raw_epoch": first_epoch,
        "last_raw_epoch": last_epoch,
        "first_raw_server_wall_clock_rendered_utc_like": datetime.fromtimestamp(
            first_epoch, tz=UTC
        ).isoformat().replace("+00:00", "Z"),
        "last_raw_server_wall_clock_rendered_utc_like": datetime.fromtimestamp(
            last_epoch, tz=UTC
        ).isoformat().replace("+00:00", "Z"),
        "raw_renderings_are_not_semantic_utc": True,
        "bytes": staged_path.stat().st_size,
        "sha256": sha256(staged_path),
        "strictly_increasing_unique_raw_timestamps": True,
        "ohlc_spread_and_volume_integrity": True,
    }


def validate_locked_authority(family_root: Path, workspace: Path) -> dict[str, Any]:
    durable = (
        family_root
        / "evidence"
        / "INDEPENDENT_MULTI_ASSET_H4_DONCHIAN_TREND_ADAPTER_CHALLENGE_V1_DEVELOPMENT_RESULT.json"
    )
    raw = (
        workspace
        / "lab"
        / "artifacts"
        / "raw"
        / FAMILY
        / "output"
        / "development-result.json"
    )
    if not durable.is_file() or not raw.is_file() or sha256(durable) != sha256(raw):
        raise RuntimeError("locked acquisition requires byte-equal raw and durable result")
    result = read_json(durable)
    if result.get("status") != "VALID_DEVELOPMENT_COMPLETE_ONE_SELECTED_PASSER":
        raise RuntimeError("locked acquisition requires one selected development passer")
    selected = result.get("selected_variant")
    if selected not in ("MULTI_ASSET_DONCHIAN_120_60", "MULTI_ASSET_DONCHIAN_240_120"):
        raise RuntimeError("invalid selected development variant")
    if int(result.get("complete_passer_count", 0)) < 1:
        raise RuntimeError("locked acquisition requires at least one complete passer")
    return {
        "path": str(durable.relative_to(workspace)).replace("\\", "/"),
        "bytes": durable.stat().st_size,
        "sha256": sha256(durable),
        "selected_variant": selected,
    }


def combine_csv(development: Path, locked: Path, destination: Path) -> None:
    with development.open("rb") as first, destination.open("wb") as output:
        header = first.readline()
        if not header:
            raise RuntimeError("development CSV has no header")
        output.write(header)
        shutil.copyfileobj(first, output)
        with locked.open("rb") as second:
            if second.readline() != header:
                raise RuntimeError("development and locked CSV headers differ")
            shutil.copyfileobj(second, output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=("development", "locked"))
    args = parser.parse_args()

    script_path = Path(__file__).absolute()
    family_root = script_path.parents[1]
    workspace = script_path.parents[4]
    expected_family = workspace / "lab" / "research" / FAMILY
    if family_root != expected_family:
        raise RuntimeError(f"unexpected family root: {family_root}")
    runtime = workspace / "lab" / "runtime" / f"{FAMILY}-portable"
    terminal = runtime / "terminal64.exe"
    output_root = workspace / "lab" / "artifacts" / "raw" / FAMILY / "input"
    market_root = output_root / "market"
    spec_root = output_root / "spec"
    if not terminal.is_file():
        raise RuntimeError(f"dedicated terminal missing: {terminal}")

    development_paths = {
        symbol: market_root / f"{symbol}_H4_DEVELOPMENT.csv" for symbol in SYMBOLS
    }
    locked_paths = {
        symbol: market_root / f"{symbol}_H4_LOCKED.csv" for symbol in SYMBOLS
    }
    combined_paths = {symbol: market_root / f"{symbol}_H4.csv" for symbol in SYMBOLS}
    spec_paths = {symbol: spec_root / f"{symbol}_SYMBOL_SPEC.json" for symbol in SYMBOLS}
    development_receipt = output_root / "DEVELOPMENT_ACQUISITION_RECEIPT.json"
    locked_receipt = output_root / "LOCKED_ACQUISITION_RECEIPT.json"
    combined_receipt = output_root / "COMPLETE_ACQUISITION_RECEIPT.json"

    if args.stage == "development":
        start, end_exclusive = DEVELOPMENT_START, DEVELOPMENT_END
        final_paths = [
            *development_paths.values(),
            *spec_paths.values(),
            development_receipt,
        ]
        locked_authority = None
    else:
        start, end_exclusive = LOCKED_START, LOCKED_END
        required = [
            *development_paths.values(),
            *spec_paths.values(),
            development_receipt,
        ]
        if any(not path.is_file() for path in required):
            raise RuntimeError("locked acquisition requires complete development source")
        locked_authority = validate_locked_authority(family_root, workspace)
        final_paths = [
            *locked_paths.values(),
            *combined_paths.values(),
            locked_receipt,
            combined_receipt,
        ]
    if any(path.exists() for path in final_paths):
        raise RuntimeError("refusing to overwrite an acquisition artifact")

    market_root.mkdir(parents=True, exist_ok=True)
    spec_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="zeta-f009-h4-"))
    initialized = False
    try:
        initialized = bool(mt5.initialize(str(terminal), portable=True, timeout=120_000))
        if not initialized:
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
        terminal_info = mt5.terminal_info()
        if terminal_info is None:
            raise RuntimeError(f"terminal_info failed: {mt5.last_error()}")
        terminal_fields = terminal_info._asdict()
        if not bool(terminal_fields.get("connected", False)):
            raise RuntimeError("dedicated Portable is not connected")
        if Path(str(terminal_fields.get("path"))).absolute() != runtime:
            raise RuntimeError("terminal path is not the family runtime")
        if Path(str(terminal_fields.get("data_path"))).absolute() != runtime:
            raise RuntimeError("terminal data path is not the family runtime")

        data_by_symbol: dict[str, pd.DataFrame] = {}
        batches_by_symbol: dict[str, list[dict[str, object]]] = {}
        specs: dict[str, dict[str, Any]] = {}
        staged_csvs: dict[str, Path] = {}
        for symbol in SYMBOLS:
            if not mt5.symbol_select(symbol, True):
                raise RuntimeError(f"symbol_select({symbol}) failed: {mt5.last_error()}")
            info = mt5.symbol_info(symbol)
            if info is None:
                raise RuntimeError(f"symbol_info({symbol}) failed: {mt5.last_error()}")
            fields = info._asdict()
            if str(fields.get("name")) != symbol:
                raise RuntimeError(f"unexpected selected symbol: {fields.get('name')}")
            spec = symbol_spec(symbol, fields)
            if spec["currency_profit"] != "USD":
                raise RuntimeError(f"{symbol} profit currency is not USD")
            if min(
                float(spec["point"]),
                float(spec["trade_tick_size"]),
                float(spec["trade_tick_value_profit"]),
                float(spec["trade_tick_value_loss"]),
                float(spec["volume_min"]),
                float(spec["volume_step"]),
            ) <= 0:
                raise RuntimeError(f"{symbol} has a nonpositive contract field")
            data, batches = acquire_symbol(symbol, start, end_exclusive)
            data_by_symbol[symbol] = data
            batches_by_symbol[symbol] = batches
            specs[symbol] = spec
            logical = (
                development_paths[symbol]
                if args.stage == "development"
                else locked_paths[symbol]
            )
            staged = staging / logical.name
            data.to_csv(
                staged,
                index=False,
                encoding="utf-8",
                lineterminator="\n",
                float_format="%.10f",
            )
            staged_csvs[symbol] = staged

        source = source_receipt(terminal, terminal_fields)
        output_receipts = {
            symbol: csv_receipt(
                staged_csvs[symbol],
                development_paths[symbol]
                if args.stage == "development"
                else locked_paths[symbol],
                workspace,
                data_by_symbol[symbol],
            )
            for symbol in SYMBOLS
        }
        if args.stage == "development":
            staged_specs: dict[str, Path] = {}
            for symbol in SYMBOLS:
                path = staging / spec_paths[symbol].name
                write_json(path, specs[symbol])
                staged_specs[symbol] = path
            receipt = {
                "schema": "zeta-next-multi-asset-h4-development-acquisition-receipt-v1",
                "recorded_at_utc": datetime.now(tz=UTC).isoformat().replace(
                    "+00:00", "Z"
                ),
                "status": "COMPLETE_FRESH_DEDICATED_PORTABLE_DEVELOPMENT_ACQUISITION",
                "family": FAMILY,
                "timeframe": "H4",
                "requested_start_inclusive": start.isoformat().replace("+00:00", "Z"),
                "requested_end_exclusive": end_exclusive.isoformat().replace(
                    "+00:00", "Z"
                ),
                "source": source,
                "batches": batches_by_symbol,
                "outputs": output_receipts,
                "symbol_specs": {
                    symbol: {
                        "path": str(spec_paths[symbol].relative_to(workspace)).replace(
                            "\\", "/"
                        ),
                        "bytes": staged_specs[symbol].stat().st_size,
                        "sha256": sha256(staged_specs[symbol]),
                        "swap_mode_name": specs[symbol]["swap_mode_name"],
                        "swap_mode_supported_by_declared_economics": specs[symbol][
                            "swap_mode_supported_by_declared_economics"
                        ],
                    }
                    for symbol in SYMBOLS
                },
                "all_declared_swap_modes_supported": all(
                    bool(specs[symbol]["swap_mode_supported_by_declared_economics"])
                    for symbol in SYMBOLS
                ),
                "locked_values_acquired": False,
                "channels_ATR_signals_lifecycles_or_economics": 0,
            }
            staged_receipt = staging / development_receipt.name
            write_json(staged_receipt, receipt)
            moves = [
                *[
                    (staged_csvs[symbol], development_paths[symbol])
                    for symbol in SYMBOLS
                ],
                *[(staged_specs[symbol], spec_paths[symbol]) for symbol in SYMBOLS],
                (staged_receipt, development_receipt),
            ]
        else:
            for symbol in SYMBOLS:
                if specs[symbol] != read_json(spec_paths[symbol]):
                    raise RuntimeError(f"{symbol} specification changed before locked stage")
            receipt = {
                "schema": "zeta-next-multi-asset-h4-locked-acquisition-receipt-v1",
                "recorded_at_utc": datetime.now(tz=UTC).isoformat().replace(
                    "+00:00", "Z"
                ),
                "status": "COMPLETE_FRESH_DEDICATED_PORTABLE_LOCKED_ACQUISITION",
                "family": FAMILY,
                "timeframe": "H4",
                "requested_start_inclusive": start.isoformat().replace("+00:00", "Z"),
                "requested_end_exclusive": end_exclusive.isoformat().replace(
                    "+00:00", "Z"
                ),
                "source": source,
                "batches": batches_by_symbol,
                "outputs": output_receipts,
                "development_result_authority": locked_authority,
                "channels_ATR_signals_lifecycles_or_economics_in_acquisition": 0,
            }
            staged_locked_receipt = staging / locked_receipt.name
            write_json(staged_locked_receipt, receipt)
            staged_combined: dict[str, Path] = {}
            development_info = read_json(development_receipt)["outputs"]
            for symbol in SYMBOLS:
                path = staging / combined_paths[symbol].name
                combine_csv(development_paths[symbol], staged_csvs[symbol], path)
                staged_combined[symbol] = path
            complete = {
                "schema": "zeta-next-multi-asset-h4-complete-acquisition-receipt-v1",
                "recorded_at_utc": datetime.now(tz=UTC).isoformat().replace(
                    "+00:00", "Z"
                ),
                "status": "COMPLETE_STAGED_FRESH_DEDICATED_PORTABLE_ACQUISITION",
                "family": FAMILY,
                "development_receipt": {
                    "path": str(development_receipt.relative_to(workspace)).replace(
                        "\\", "/"
                    ),
                    "bytes": development_receipt.stat().st_size,
                    "sha256": sha256(development_receipt),
                },
                "locked_receipt": {
                    "path": str(locked_receipt.relative_to(workspace)).replace("\\", "/"),
                    "bytes": staged_locked_receipt.stat().st_size,
                    "sha256": sha256(staged_locked_receipt),
                },
                "outputs": {
                    symbol: {
                        "path": str(combined_paths[symbol].relative_to(workspace)).replace(
                            "\\", "/"
                        ),
                        "rows": int(development_info[symbol]["rows"])
                        + int(len(data_by_symbol[symbol])),
                        "bytes": staged_combined[symbol].stat().st_size,
                        "sha256": sha256(staged_combined[symbol]),
                    }
                    for symbol in SYMBOLS
                },
                "broker_account_position_order_or_deal_queries": 0,
                "candidate_lifecycles_or_economics_in_acquisition": 0,
            }
            staged_complete_receipt = staging / combined_receipt.name
            write_json(staged_complete_receipt, complete)
            moves = [
                *[(staged_csvs[symbol], locked_paths[symbol]) for symbol in SYMBOLS],
                (staged_locked_receipt, locked_receipt),
                *[(staged_combined[symbol], combined_paths[symbol]) for symbol in SYMBOLS],
                (staged_complete_receipt, combined_receipt),
            ]

        for staged, final in moves:
            os.replace(staged, final)
        print(
            json.dumps(
                {
                    "status": receipt["status"],
                    "stage": args.stage,
                    "outputs": receipt["outputs"],
                    "broker_account_position_order_deal_queries": 0,
                },
                indent=2,
            ),
            flush=True,
        )
        return 0
    finally:
        if initialized:
            mt5.shutdown()
        if staging.exists():
            try:
                shutil.rmtree(staging)
            except OSError as error:
                print(f"STAGING_CLEANUP_WARNING: {error}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ACQUISITION_ERROR: {exc}", file=sys.stderr, flush=True)
        raise
