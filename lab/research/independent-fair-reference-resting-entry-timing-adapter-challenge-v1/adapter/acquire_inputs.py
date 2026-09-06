"""Ordinary bounded native-source acquisition for Family 014; no trading calls."""
from pathlib import Path
import argparse
import calendar
import datetime as dt
import hashlib
import json
import shutil
import subprocess

import numpy as np

FAMILY_ROOT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
TICK_DTYPE = np.dtype([
    ("time", "<i8"), ("bid", "<f8"), ("ask", "<f8"), ("last", "<f8"),
    ("volume", "<u8"), ("time_msc", "<i8"), ("flags", "<u4"), ("volume_real", "<f8")])


def fingerprint(path):
    path = path.resolve()
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest().upper()
    return {"path": path.relative_to(REPO).as_posix(),
            "bytes": path.stat().st_size, "sha256": digest}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8", newline="\n")
    temporary.replace(path)


def month_bounds():
    for year in (2023, 2024, 2025):
        for month in (range(12, 13) if year == 2023 else range(1, 13)):
            start = dt.datetime(year, month, 1, tzinfo=dt.timezone.utc)
            end = start + dt.timedelta(days=calendar.monthrange(year, month)[1])
            yield start.strftime("%Y%m"), start, end


def owned_bytes(path):
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file()) if path.exists() else 0


def settings():
    contract = json.loads((FAMILY_ROOT / "config/contract.json").read_text(encoding="utf-8-sig"))
    artifact = REPO / "lab/artifacts/raw" / contract["family"]
    runtime = REPO / contract["identity"]["source_runtime"]
    return contract, artifact, runtime


def reserve(contract, artifact, runtime):
    allowance = contract["storage"]["initial_acquisition_and_results_allowance_bytes"]
    used = owned_bytes(artifact) + owned_bytes(runtime)
    if used > allowance:
        raise RuntimeError("Owned source and results exceed the declared growth allowance")
    remaining = allowance - used
    if shutil.disk_usage(REPO).free - remaining < contract["storage"]["minimum_free_bytes"]:
        raise RuntimeError("Declared acquisition allowance would threaten 30 GiB reserve")


def prepare():
    contract, artifact, runtime = settings()
    reserve(contract, artifact, runtime)
    if runtime.exists():
        raise RuntimeError("Reader already staged; inspect/resume it instead of replacing it")
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", str(runtime / "config/accounts.dat")], cwd=REPO)
    if ignored.returncode != 0:
        raise RuntimeError("Private native reader must be Git-ignored before staging")
    runtime.mkdir(parents=True)
    (runtime / "config").mkdir()
    declaration = json.loads((FAMILY_ROOT / "evidence/DECLARATION_V1.json").read_text(encoding="utf-8-sig"))
    copied = []
    for source_record in declaration["physical_native_cache_and_platform_sources"]:
        source = REPO / source_record["source"]["path"]
        target = runtime / source_record["relative_target"]
        if fingerprint(source) != source_record["source"]:
            raise RuntimeError("Declared native observation/platform source drift")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        observed = fingerprint(target)
        if observed["bytes"] != source_record["source"]["bytes"] or observed["sha256"] != source_record["source"]["sha256"]:
            raise RuntimeError("Owned physical source copy failed")
        copied.append({"source": source_record["source"], "copy": observed})
    private = []
    for name in ("accounts.dat", "common.ini", "servers.dat", "terminal.lic"):
        source = REPO / "lab/runtime/tester-portable/config" / name
        target = runtime / "config" / name
        shutil.copyfile(source, target)
        source_info, target_info = fingerprint(source), fingerprint(target)
        if source_info["sha256"] != target_info["sha256"]:
            raise RuntimeError("Private connection copy mismatch")
        private.append({"name": name, "bytes": target_info["bytes"], "sha256": target_info["sha256"]})
    write_json(runtime / "private-copy-receipt.json", {"files": private})
    ini = ("[Common]\nKeepPrivate=1\nNewsEnable=0\n[Charts]\nMaxBars=2000000\n"
           "[Experts]\nEnabled=0\nAllowLiveTrading=0\nAllowDllImport=0\n[StartUp]\nExpert=\nScript=\n")
    (runtime / "config/source-readonly.ini").write_text(ini, encoding="utf-16", newline="\n")
    capture_source = REPO / declaration["dated_contract_source"]["path"]
    target = artifact / "input/spec/current-contract-source.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(capture_source, target)
    if fingerprint(target)["sha256"] != declaration["dated_contract_source"]["sha256"]:
        raise RuntimeError("Dated contract copy mismatch")
    record = {"schema": "zeta-ch014-source-staging-v1",
              "recorded_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "copies": copied, "dated_contract_copy": fingerprint(target),
              "private_copy_receipt": "Retained only inside ignored reader; no contents in tracked evidence",
              "strategy_profiles_EA_Include_copied": 0,
              "free_bytes_after": shutil.disk_usage(REPO).free}
    write_json(FAMILY_ROOT / "evidence/SOURCE_STAGING_V1.json", record)
    print(json.dumps({"status": "SOURCE_STAGED_NOT_LAUNCHED", "files": len(copied),
                      "bytes": sum(x["copy"]["bytes"] for x in copied),
                      "free_gib": record["free_bytes_after"] / 1024**3}), flush=True)


def capture():
    import MetaTrader5 as mt5
    contract, artifact, runtime = settings()
    reserve(contract, artifact, runtime)
    freeze = json.loads((FAMILY_ROOT / "evidence/SOURCE_IMPLEMENTATION_FREEZE_V1.json").read_text(encoding="utf-8-sig"))
    for item in freeze["files"]:
        if fingerprint(REPO / item["path"]) != item:
            raise RuntimeError("Pre-acquisition source/declaration drift")
    progress_path = artifact / "acquisition-progress.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8-sig")) if progress_path.exists() else {
        "schema": "zeta-ch014-input-acquisition-progress-v1", "completed": [],
        "api_version": mt5.__version__, "account_position_order_deal_calls": 0,
        "order_execution_calls": 0, "candidate_features_or_economics_computed": False}
    finished = {(x["symbol"], x["month"]): x for x in progress["completed"]}
    output = artifact / "input/ticks"
    output.mkdir(parents=True, exist_ok=True)
    static_fields = ["name", "trade_mode", "trade_exemode", "order_mode", "filling_mode",
                     "expiration_mode", "trade_stops_level", "trade_freeze_level",
                     "point", "trade_tick_size", "trade_contract_size", "volume_min",
                     "volume_step", "volume_max", "swap_mode", "swap_long", "swap_short"]
    try:
        if not mt5.initialize(str(runtime / "terminal64.exe"), portable=True, timeout=15000):
            raise RuntimeError("Explicit own reader initialization failed: " + str(mt5.last_error()))
        info = mt5.terminal_info()
        if info is None or Path(info.data_path).resolve() != runtime.resolve():
            raise RuntimeError("Wrong data-path attachment")
        if not info.connected or info.trade_allowed:
            raise RuntimeError("Reader must be connected with algorithmic trading disabled")
        if info.maxbars < 1000000:
            raise RuntimeError("Reader M1 calendar history capacity is too small")
        progress["terminal"] = {key: getattr(info, key) for key in
                                ("path", "data_path", "build", "connected", "trade_allowed", "maxbars")}
        progress["static_contracts"] = {}
        for symbol in contract["symbols"]:
            if not mt5.symbol_select(symbol, True):
                raise RuntimeError("Missing required symbol " + symbol)
            spec = mt5.symbol_info(symbol)
            if spec is None:
                raise RuntimeError("Missing current source contract")
            progress["static_contracts"][symbol] = {key: getattr(spec, key) for key in static_fields}
        write_json(progress_path, progress)
        for month, start, end in month_bounds():
            for symbol in contract["symbols"]:
                key = (symbol, month)
                if key in finished:
                    saved = finished[key]
                    if fingerprint(REPO / saved["ticks"]["path"]) != saved["ticks"]:
                        raise RuntimeError("Completed input chunk changed")
                    continue
                if (artifact / "STOP_AFTER_CURRENT_CHUNK").exists():
                    progress["status"] = "SOURCE_PAUSED_AT_COMPLETE_CHUNK"
                    write_json(progress_path, progress)
                    print(json.dumps({"status": progress["status"], "completed_chunks": len(finished)}), flush=True)
                    return
                if shutil.disk_usage(REPO).free - 2 * 1024**3 < contract["storage"]["minimum_free_bytes"]:
                    raise RuntimeError("Insufficient reserve for next bounded month")
                print(json.dumps({"status": "ACQUIRING", "month": month, "symbol": symbol}), flush=True)
                cache = runtime / "bases/FPMarketsSC-Live/ticks" / symbol / (month + ".tkc")
                before = fingerprint(cache) if cache.exists() else None
                ticks = mt5.copy_ticks_range(symbol, start, end, mt5.COPY_TICKS_ALL)
                tick_error = mt5.last_error()
                if ticks is None or tick_error[0] != 1:
                    raise RuntimeError("Incomplete tick acquisition " + str(tick_error))
                lower, upper = int(start.timestamp() * 1000), int(end.timestamp() * 1000)
                # Inspect time only before touching any price fields outside the half-open request.
                source_ms = ticks["time_msc"]
                response_rows = len(ticks)
                if np.any(np.diff(source_ms) < 0):
                    raise RuntimeError("Nonchronological source response")
                left, right = np.searchsorted(source_ms, [lower, upper], side="left")
                in_range = ticks[left:right]
                packed = np.empty(len(in_range), dtype=TICK_DTYPE)
                for field in TICK_DTYPE.names:
                    packed[field] = in_range[field]
                del in_range, source_ms, ticks
                if len(packed) == 0:
                    raise RuntimeError("No quote observations for a complete declared month")
                if np.any(packed["time"] != packed["time_msc"] // 1000):
                    raise RuntimeError("Inconsistent native second/millisecond timestamps")
                if (not np.all(np.isfinite(packed["bid"])) or not np.all(np.isfinite(packed["ask"])) or
                        np.any(packed["bid"] <= 0) or np.any(packed["ask"] < packed["bid"])):
                    raise RuntimeError("Invalid native quote observations require source correction")
                rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start, end)
                rate_error = mt5.last_error()
                if rates is None or rate_error[0] != 1:
                    raise RuntimeError("Incomplete source M1 calendar")
                rate_times = rates["time"]
                rate_times = rate_times[(rate_times >= lower // 1000) & (rate_times < upper // 1000)]
                source_days = np.unique(rate_times // 86400).astype(np.int64).tolist()
                tick_days = np.unique(packed["time_msc"] // 86400000).astype(np.int64).tolist()
                del rates, rate_times
                if not source_days:
                    raise RuntimeError("Empty source calendar for declared month")
                if (owned_bytes(artifact) + owned_bytes(runtime) + packed.nbytes + 4096 >
                        contract["storage"]["initial_acquisition_and_results_allowance_bytes"]):
                    raise RuntimeError("Next retained month exceeds declared growth allowance")
                target = output / symbol / (month + ".npy")
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    raise RuntimeError("Unsealed existing month requires attributable correction, not overwrite")
                temporary = target.with_suffix(".npy.partial")
                with temporary.open("wb") as handle:
                    np.save(handle, packed, allow_pickle=False)
                temporary.replace(target)
                after = fingerprint(cache) if cache.exists() else None
                chunk = {
                    "symbol": symbol, "month": month,
                    "request_utc_inclusive": [start.isoformat(), end.isoformat()],
                    "retained_raw_ms_half_open": [lower, upper], "rows": len(packed),
                    "first_raw_ms": int(packed["time_msc"][0]), "last_raw_ms": int(packed["time_msc"][-1]),
                    "source_m1_calendar_days_raw_epoch": source_days,
                    "quote_days_raw_epoch": tick_days, "ticks": fingerprint(target),
                    "cache_before_request": before, "cache_after_request": after,
                    "cache_refreshed_during_request": before != after,
                    "tick_api_error": list(tick_error), "calendar_api_error": list(rate_error),
                    "boundary_rows_not_retained": {"before": int(left), "after": response_rows - int(right)},
                    "price_fields_outside_retained_bounds_used": False,
                    "captured_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
                del packed
                finished[key] = chunk
                progress["completed"].append(chunk)
                progress["status"] = "SOURCE_ACQUISITION_IN_PROGRESS"
                progress["free_bytes"] = shutil.disk_usage(REPO).free
                write_json(progress_path, progress)
                print(json.dumps({"status": "CHUNK_COMPLETE", "symbol": symbol, "month": month,
                                  "rows": chunk["rows"], "bytes": chunk["ticks"]["bytes"],
                                  "cache_refreshed": chunk["cache_refreshed_during_request"],
                                  "completed_chunks": len(finished),
                                  "free_gib": progress["free_bytes"] / 1024**3}), flush=True)
        if len(finished) != 75:
            raise RuntimeError("Not all declared monthly source chunks exist")
        progress["status"] = "COMPLETE_SOURCE_INPUTS_FEATURES_UNOPENED"
        progress["total_rows"] = sum(x["rows"] for x in progress["completed"])
        progress["total_tick_bytes"] = sum(x["ticks"]["bytes"] for x in progress["completed"])
        progress["sealed_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        progress["source_reader_shutdown_required"] = True
        write_json(progress_path, progress)
        final = FAMILY_ROOT / "evidence/INPUT_ACQUISITION_V1.json"
        if final.exists():
            raise RuntimeError("Refusing to overwrite sealed acquisition")
        write_json(final, progress)
        print(json.dumps({"status": progress["status"], "rows": progress["total_rows"],
                          "bytes": progress["total_tick_bytes"]}), flush=True)
    except BaseException as exc:
        progress["status"] = "SOURCE_CORRECTION_OR_PAUSE_REQUIRED"
        progress["last_error"] = type(exc).__name__ + ": " + str(exc)
        write_json(progress_path, progress)
        raise
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "capture"))
    args = parser.parse_args()
    prepare() if args.operation == "prepare" else capture()
