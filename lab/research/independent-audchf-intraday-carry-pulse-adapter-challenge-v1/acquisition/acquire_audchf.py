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


FAMILY = "independent-audchf-intraday-carry-pulse-adapter-challenge-v1"
SYMBOL = "AUDCHF"
DEVELOPMENT_START = datetime(2023, 7, 1, tzinfo=UTC)
DEVELOPMENT_END = datetime(2026, 1, 1, tzinfo=UTC)
LOCKED_START = DEVELOPMENT_END
LOCKED_END = datetime(2026, 8, 1, tzinfo=UTC)
COLUMNS = [
    "time",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
]
HISTORY_SYNC_TIMEOUT_SECONDS = 300


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


def next_month(value: datetime) -> datetime:
    if value.month == 12:
        return datetime(value.year + 1, 1, 1, tzinfo=UTC)
    return datetime(value.year, value.month + 1, 1, tzinfo=UTC)


def finite_float(value: object, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise RuntimeError(f"nonfinite symbol field: {name}")
    return number


def symbol_spec(symbol_fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "zeta-next-audchf-symbol-spec-v1",
        "symbol": SYMBOL,
        "name": str(symbol_fields.get("name")),
        "path": str(symbol_fields.get("path")),
        "description": str(symbol_fields.get("description")),
        "currency_base": str(symbol_fields.get("currency_base")),
        "currency_profit": str(symbol_fields.get("currency_profit")),
        "currency_margin": str(symbol_fields.get("currency_margin")),
        "digits": int(symbol_fields.get("digits")),
        "point": finite_float(symbol_fields.get("point"), "point"),
        "trade_tick_size": finite_float(
            symbol_fields.get("trade_tick_size"), "trade_tick_size"
        ),
        "trade_tick_value": finite_float(
            symbol_fields.get("trade_tick_value"), "trade_tick_value"
        ),
        "trade_contract_size": finite_float(
            symbol_fields.get("trade_contract_size"), "trade_contract_size"
        ),
        "volume_min": finite_float(symbol_fields.get("volume_min"), "volume_min"),
        "volume_step": finite_float(
            symbol_fields.get("volume_step"), "volume_step"
        ),
        "volume_max": finite_float(symbol_fields.get("volume_max"), "volume_max"),
        "trade_mode": int(symbol_fields.get("trade_mode")),
        "trade_calc_mode": int(symbol_fields.get("trade_calc_mode")),
        "signal_uses_external_spread": False,
    }


def acquire_batches(
    start: datetime,
    end_exclusive: datetime,
) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    batches: list[pd.DataFrame] = []
    receipts: list[dict[str, object]] = []
    cursor = start
    while cursor < end_exclusive:
        batch_end = min(next_month(cursor), end_exclusive)
        batch_start_epoch = int(cursor.timestamp())
        batch_end_epoch = int(batch_end.timestamp())
        deadline = time.monotonic() + HISTORY_SYNC_TIMEOUT_SECONDS
        last_observation = "no response"
        next_progress = time.monotonic() + 15
        while True:
            rates = mt5.copy_rates_range(
                SYMBOL,
                mt5.TIMEFRAME_M1,
                cursor,
                datetime.fromtimestamp(batch_end.timestamp() - 1, tz=UTC),
            )
            if rates is None:
                last_observation = f"last_error={mt5.last_error()}"
                frame = pd.DataFrame()
            else:
                frame = pd.DataFrame(rates)
                missing = [name for name in COLUMNS if name not in frame.columns]
                if missing:
                    raise RuntimeError(f"missing MT5 rate columns: {missing}")
                frame = frame[
                    (frame["time"] >= batch_start_epoch)
                    & (frame["time"] < batch_end_epoch)
                ].copy()
                if frame.empty:
                    last_observation = "zero in-range rows"
                else:
                    first_epoch = int(frame["time"].iloc[0])
                    last_epoch = int(frame["time"].iloc[-1])
                    last_observation = (
                        f"rows={len(frame)} first={first_epoch} last={last_epoch}"
                    )
                    boundary_slack = 4 * 24 * 60 * 60
                    if (
                        len(frame) >= 1_000
                        and first_epoch - batch_start_epoch <= boundary_slack
                        and batch_end_epoch - last_epoch <= boundary_slack
                    ):
                        frame = frame[COLUMNS].copy()
                        break
            now = time.monotonic()
            if now >= deadline:
                raise RuntimeError(
                    f"history synchronization timed out for {cursor.isoformat()} / "
                    f"{batch_end.isoformat()}: {last_observation}"
                )
            if now >= next_progress:
                print(
                    f"waiting for history sync {cursor:%Y-%m}: {last_observation}",
                    flush=True,
                )
                next_progress = now + 15
            time.sleep(1)
        batches.append(frame)
        receipts.append(
            {
                "start_inclusive": cursor.isoformat().replace("+00:00", "Z"),
                "end_exclusive": batch_end.isoformat().replace("+00:00", "Z"),
                "rows": int(len(frame)),
                "first_epoch": int(frame["time"].iloc[0]),
                "last_epoch": int(frame["time"].iloc[-1]),
            }
        )
        print(f"acquired {cursor:%Y-%m}: {len(frame)} rows", flush=True)
        cursor = batch_end

    data = pd.concat(batches, ignore_index=True)
    start_epoch = int(start.timestamp())
    end_epoch = int(end_exclusive.timestamp())
    data = data[(data["time"] >= start_epoch) & (data["time"] < end_epoch)].copy()
    data.sort_values("time", kind="mergesort", inplace=True)
    data.reset_index(drop=True, inplace=True)
    minimum_rows = 500_000 if end_exclusive == DEVELOPMENT_END else 100_000
    if len(data) < minimum_rows:
        raise RuntimeError(f"insufficient AUDCHF M1 rows: {len(data)}")
    if data["time"].duplicated().any():
        raise RuntimeError("duplicate AUDCHF M1 timestamps")
    if not data["time"].is_monotonic_increasing:
        raise RuntimeError("AUDCHF M1 timestamps are not strictly increasing")
    if int(data["time"].iloc[0]) - start_epoch > 3 * 24 * 60 * 60:
        raise RuntimeError("first AUDCHF M1 row is more than three days after request")
    if end_epoch - int(data["time"].iloc[-1]) > 3 * 24 * 60 * 60:
        raise RuntimeError("last AUDCHF M1 row is more than three days before request end")
    for name in ["open", "high", "low", "close"]:
        if not pd.to_numeric(data[name], errors="coerce").notna().all():
            raise RuntimeError(f"nonfinite rate column: {name}")
    if not (data["high"] >= data[["open", "close", "low"]].max(axis=1)).all():
        raise RuntimeError("OHLC high invariant failed")
    if not (data["low"] <= data[["open", "close", "high"]].min(axis=1)).all():
        raise RuntimeError("OHLC low invariant failed")
    if (data["spread"] < 0).any():
        raise RuntimeError("negative recorded spread")
    data.insert(
        1,
        "time_utc",
        pd.to_datetime(data["time"], unit="s", utc=True).dt.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
    )
    return data, receipts


def common_source_receipt(
    terminal: Path,
    terminal_fields: dict[str, Any],
) -> dict[str, Any]:
    return {
        "symbol": SYMBOL,
        "timeframe": "M1",
        "terminal_executable": str(terminal),
        "terminal_executable_bytes": terminal.stat().st_size,
        "terminal_executable_sha256": sha256(terminal),
        "terminal_version": list(mt5.version() or ()),
        "python_package_version": mt5.__version__,
        "terminal_company": str(terminal_fields.get("company")),
        "terminal_name": str(terminal_fields.get("name")),
        "terminal_path": str(terminal_fields.get("path")),
        "terminal_data_path": str(terminal_fields.get("data_path")),
        "connected": bool(terminal_fields.get("connected")),
        "server_authority": "project-local original broker session copied once as non-price account/server support from a stopped non-Master Lab Portable; account identifier and account state intentionally not queried or persisted",
        "broker_account_position_order_or_deal_queries": 0,
        "existing_runtime_price_or_history_cache_reads": 0,
        "other_family_runtime_execution": False,
    }


def csv_output_receipt(
    physical_path: Path,
    logical_path: Path,
    workspace: Path,
    data: pd.DataFrame,
) -> dict[str, Any]:
    return {
        "path": str(logical_path.relative_to(workspace)).replace("\\", "/"),
        "columns": list(data.columns),
        "rows": int(len(data)),
        "first_epoch": int(data["time"].iloc[0]),
        "last_epoch": int(data["time"].iloc[-1]),
        "first_utc": str(data["time_utc"].iloc[0]),
        "last_utc": str(data["time_utc"].iloc[-1]),
        "bytes": physical_path.stat().st_size,
        "sha256": sha256(physical_path),
        "strictly_increasing_unique_timestamps": True,
        "ohlc_and_spread_integrity": True,
    }


def combine_csv_without_duplicate_header(
    development_path: Path,
    locked_path: Path,
    combined_path: Path,
) -> None:
    with development_path.open("rb") as development, combined_path.open("wb") as output:
        development_header = development.readline()
        if not development_header:
            raise RuntimeError("development CSV has no header")
        output.write(development_header)
        shutil.copyfileobj(development, output)
        with locked_path.open("rb") as locked:
            locked_header = locked.readline()
            if locked_header != development_header:
                raise RuntimeError("development and locked CSV headers differ")
            shutil.copyfileobj(locked, output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=["development", "locked"])
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    family_root = script_path.parents[1]
    workspace = script_path.parents[4]
    runtime = workspace / "lab" / "runtime" / f"{FAMILY}-portable"
    terminal = runtime / "terminal64.exe"
    output_root = (
        workspace / "lab" / "artifacts" / "raw" / FAMILY / "input" / "external"
    )
    development_csv = output_root / "AUDCHF_M1_DEVELOPMENT.csv"
    development_receipt = output_root / "AUDCHF_DEVELOPMENT_ACQUISITION_RECEIPT.json"
    locked_csv = output_root / "AUDCHF_M1_LOCKED.csv"
    locked_receipt = output_root / "AUDCHF_LOCKED_ACQUISITION_RECEIPT.json"
    combined_csv = output_root / "AUDCHF_M1.csv"
    final_receipt = output_root / "AUDCHF_ACQUISITION_RECEIPT.json"
    spec_path = output_root / "AUDCHF_SYMBOL_SPEC.json"

    if family_root != workspace / "lab" / "research" / FAMILY:
        raise RuntimeError(f"unexpected family root: {family_root}")
    if not terminal.is_file():
        raise RuntimeError(f"dedicated terminal missing: {terminal}")

    if args.stage == "development":
        final_paths = [development_csv, development_receipt, spec_path]
        start, end_exclusive = DEVELOPMENT_START, DEVELOPMENT_END
    else:
        final_paths = [locked_csv, locked_receipt, combined_csv, final_receipt]
        start, end_exclusive = LOCKED_START, LOCKED_END
        required = [development_csv, development_receipt, spec_path]
        if any(not path.is_file() for path in required):
            raise RuntimeError("locked acquisition requires complete development authority")
        durable_result = (
            family_root
            / "evidence"
            / "INDEPENDENT_AUDCHF_INTRADAY_CARRY_PULSE_ADAPTER_CHALLENGE_V1_DEVELOPMENT_RESULT.json"
        )
        raw_result = (
            workspace
            / "lab"
            / "artifacts"
            / "raw"
            / FAMILY
            / "output"
            / "development-result.json"
        )
        if not durable_result.is_file() or not raw_result.is_file():
            raise RuntimeError("locked acquisition requires raw and durable development results")
        if sha256(raw_result) != sha256(durable_result):
            raise RuntimeError("raw and durable development results are not byte-identical")
        result = read_json(durable_result)
        if result.get("status") != "VALID_DEVELOPMENT_COMPLETE_ONE_SELECTED_PASSER":
            raise RuntimeError("locked acquisition requires a valid one-passer status")
        candidates = result.get("candidate_results")
        selected_role = result.get("selected_role")
        if not isinstance(candidates, list) or len(candidates) != 2:
            raise RuntimeError("locked acquisition requires the complete two-role bundle")
        passing_rows = [
            row
            for row in candidates
            if isinstance(row, dict)
            and isinstance(row.get("gates"), dict)
            and row["gates"].get("passed") is True
        ]
        passing_rows.sort(
            key=lambda row: (
                -float(row["stressed_net_usd"]),
                float(row["actual_closed_balance_drawdown_pct"]),
                -min(
                    float(row["epoch_metrics"][str(year)]["stressed_net_usd"])
                    for year in [2024, 2025]
                ),
                ["AUDCHF_PULSE_FOLLOW", "AUDCHF_PULSE_FADE"].index(row["role"]),
            )
        )
        if (
            int(result.get("complete_passer_count", 0)) != len(passing_rows)
            or not passing_rows
            or selected_role not in {"AUDCHF_PULSE_FOLLOW", "AUDCHF_PULSE_FADE"}
            or passing_rows[0]["role"] != selected_role
        ):
            raise RuntimeError("locked acquisition requires one correctly ranked selected passer")

    if any(path.exists() for path in final_paths):
        raise RuntimeError("refusing to overwrite an existing acquisition artifact")

    output_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="zeta-f007-audchf-"))
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
            raise RuntimeError("dedicated Portable is not connected to a price server")
        if not mt5.symbol_select(SYMBOL, True):
            raise RuntimeError(f"symbol_select({SYMBOL}) failed: {mt5.last_error()}")
        info = mt5.symbol_info(SYMBOL)
        if info is None:
            raise RuntimeError(f"symbol_info({SYMBOL}) failed: {mt5.last_error()}")
        info_fields = info._asdict()
        if str(info_fields.get("name")) != SYMBOL:
            raise RuntimeError(f"unexpected selected symbol: {info_fields.get('name')}")
        current_spec = symbol_spec(info_fields)

        data, batches = acquire_batches(start, end_exclusive)
        stage_csv = staging / (development_csv.name if args.stage == "development" else locked_csv.name)
        data.to_csv(
            stage_csv,
            index=False,
            encoding="utf-8",
            lineterminator="\n",
            float_format="%.10f",
        )
        source = common_source_receipt(terminal, terminal_fields)

        if args.stage == "development":
            stage_spec = staging / spec_path.name
            stage_receipt = staging / development_receipt.name
            write_json(stage_spec, current_spec)
            receipt = {
                "schema": "zeta-next-audchf-development-m1-acquisition-receipt-v1",
                "recorded_at_utc": datetime.now(tz=UTC).isoformat().replace(
                    "+00:00", "Z"
                ),
                "status": "COMPLETE_FRESH_DEDICATED_PORTABLE_DEVELOPMENT_ACQUISITION",
                "family": FAMILY,
                "stage": "development",
                "requested_start_inclusive": start.isoformat().replace("+00:00", "Z"),
                "requested_end_exclusive": end_exclusive.isoformat().replace(
                    "+00:00", "Z"
                ),
                "source": source,
                "batches": batches,
                "output": csv_output_receipt(
                    stage_csv, development_csv, workspace, data
                ),
                "symbol_spec": {
                    "path": str(spec_path.relative_to(workspace)).replace("\\", "/"),
                    "bytes": stage_spec.stat().st_size,
                    "sha256": sha256(stage_spec),
                },
                "locked_external_values_acquired": False,
                "candidate_target_future_paths_opened": False,
                "candidate_lifecycles_or_economics": 0,
            }
            write_json(stage_receipt, receipt)
            moves = [
                (stage_csv, development_csv),
                (stage_spec, spec_path),
                (stage_receipt, development_receipt),
            ]
        else:
            if current_spec != read_json(spec_path):
                raise RuntimeError("AUDCHF symbol specification changed before locked acquisition")
            stage_locked_receipt = staging / locked_receipt.name
            locked_stage_receipt = {
                "schema": "zeta-next-audchf-locked-m1-acquisition-receipt-v1",
                "recorded_at_utc": datetime.now(tz=UTC).isoformat().replace(
                    "+00:00", "Z"
                ),
                "status": "COMPLETE_FRESH_DEDICATED_PORTABLE_LOCKED_ACQUISITION",
                "family": FAMILY,
                "stage": "locked",
                "requested_start_inclusive": start.isoformat().replace("+00:00", "Z"),
                "requested_end_exclusive": end_exclusive.isoformat().replace(
                    "+00:00", "Z"
                ),
                "source": source,
                "batches": batches,
                "output": csv_output_receipt(stage_csv, locked_csv, workspace, data),
                "development_authority": {
                    "path": str(development_csv.relative_to(workspace)).replace("\\", "/"),
                    "bytes": development_csv.stat().st_size,
                    "sha256": sha256(development_csv),
                },
                "locked_open_authority": "exactly one durable complete development passer",
                "candidate_lifecycles_or_economics_in_acquisition": 0,
            }
            write_json(stage_locked_receipt, locked_stage_receipt)
            stage_combined = staging / combined_csv.name
            combine_csv_without_duplicate_header(development_csv, stage_csv, stage_combined)
            development_info = read_json(development_receipt)["output"]
            final = {
                "schema": "zeta-next-audchf-m1-acquisition-receipt-v1",
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
                    "path": str(locked_receipt.relative_to(workspace)).replace(
                        "\\", "/"
                    ),
                    "bytes": stage_locked_receipt.stat().st_size,
                    "sha256": sha256(stage_locked_receipt),
                },
                "output": {
                    "path": str(combined_csv.relative_to(workspace)).replace("\\", "/"),
                    "rows": int(development_info["rows"]) + int(len(data)),
                    "first_utc": str(development_info["first_utc"]),
                    "last_utc": str(data["time_utc"].iloc[-1]),
                    "bytes": stage_combined.stat().st_size,
                    "sha256": sha256(stage_combined),
                },
                "broker_account_position_order_or_deal_queries": 0,
                "candidate_lifecycles_or_economics_in_acquisition": 0,
            }
            stage_final_receipt = staging / final_receipt.name
            write_json(stage_final_receipt, final)
            moves = [
                (stage_csv, locked_csv),
                (stage_locked_receipt, locked_receipt),
                (stage_combined, combined_csv),
                (stage_final_receipt, final_receipt),
            ]
            receipt = locked_stage_receipt

        for stage_path, final_path in moves:
            os.replace(stage_path, final_path)
        print(
            json.dumps(
                {
                    "status": receipt["status"],
                    "stage": args.stage,
                    "rows": receipt["output"]["rows"],
                    "first_utc": receipt["output"]["first_utc"],
                    "last_utc": receipt["output"]["last_utc"],
                    "csv_bytes": receipt["output"]["bytes"],
                    "csv_sha256": receipt["output"]["sha256"],
                    "account_position_order_deal_queries": 0,
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
            except OSError as cleanup_error:
                print(
                    f"STAGING_CLEANUP_WARNING: {cleanup_error}",
                    file=sys.stderr,
                    flush=True,
                )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ACQUISITION_ERROR: {exc}", file=sys.stderr, flush=True)
        raise
