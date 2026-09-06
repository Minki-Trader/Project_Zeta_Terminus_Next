"""Acquire only declared Treasury-note static metadata and historical M1 timestamps."""
from pathlib import Path
import argparse
import calendar
import datetime as dt
import hashlib
import json
import shutil
import subprocess

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
SYMBOL = "US10YR"
FIELDS = (
    "name", "description", "path", "custom", "exchange", "isin", "category",
    "digits", "point", "trade_tick_size", "trade_contract_size", "trade_calc_mode",
    "currency_base", "currency_profit", "currency_margin",
    "volume_min", "volume_step", "volume_max", "trade_mode", "trade_exemode",
    "order_mode", "filling_mode", "expiration_mode", "order_gtc_mode",
    "trade_stops_level", "trade_freeze_level", "start_time", "expiration_time",
    "swap_mode", "swap_long", "swap_short", "swap_rollover3days",
    "margin_initial", "margin_maintenance", "margin_hedged")


def fingerprint(path):
    path = path.absolute()
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest().upper()
    return {"path": path.relative_to(REPO).as_posix(), "bytes": path.stat().st_size, "sha256": digest}


def json_scalar(value):
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError("Unsupported source-report scalar: " + type(value).__name__)


def write(path, value, overwrite=False):
    if path.exists() and not overwrite:
        raise RuntimeError("Preserve existing source evidence")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False,
                         default=json_scalar, allow_nan=False) + "\n",
                         encoding="utf-8", newline="\n")
    temporary.replace(path)


def context():
    declaration = json.loads((ROOT / "evidence/DECLARATION_V1.json").read_text(encoding="utf-8-sig"))
    runtime = REPO / declaration["ownership"]["runtime"]
    raw = REPO / declaration["ownership"]["raw"]
    return declaration, runtime, raw


def owned_size(runtime, raw):
    return sum(p.stat().st_size for root in (runtime, raw)
               for p in root.rglob("*") if p.is_file()) if runtime.exists() or raw.exists() else 0


def reserve(declaration, runtime, raw):
    owned = owned_size(runtime, raw)
    allowance = declaration["storage"]["maximum_source_growth_bytes"]
    if owned > allowance:
        raise RuntimeError("Source growth exceeded its declaration")
    if shutil.disk_usage(REPO).free - (allowance-owned) < declaration["storage"]["minimum_free_bytes"]:
        raise RuntimeError("Source acquisition would threaten the 30 GiB reserve")


def prepare():
    declaration, runtime, raw = context()
    reserve(declaration, runtime, raw)
    if runtime.exists():
        raise RuntimeError("Existing source preparation requires attributable continuation")
    ignored = subprocess.run(["git", "check-ignore", "--quiet", str(runtime/"config/accounts.dat")], cwd=REPO)
    if ignored.returncode != 0:
        raise RuntimeError("Private source reader must be ignored before any copy")
    expected = declaration["generic_platform"]
    platform = REPO / expected["path"]
    if fingerprint(platform) != expected:
        raise RuntimeError("Declared generic platform content changed")
    (runtime/"config").mkdir(parents=True)
    shutil.copyfile(platform, runtime/"terminal64.exe")
    copied = fingerprint(runtime/"terminal64.exe")
    if copied["bytes"] != expected["bytes"] or copied["sha256"] != expected["sha256"]:
        raise RuntimeError("Owned platform copy mismatch")
    private = []
    for name in ("accounts.dat", "common.ini", "servers.dat", "terminal.lic"):
        source = REPO/"lab/runtime/tester-portable/config"/name
        target = runtime/"config"/name
        shutil.copyfile(source, target)
        left, right = fingerprint(source), fingerprint(target)
        if left["bytes"] != right["bytes"] or left["sha256"] != right["sha256"]:
            raise RuntimeError("Private connection copy mismatch")
        private.append({"name": name, "bytes": right["bytes"], "sha256": right["sha256"]})
    write(runtime/"private-connection-copy.json", {"files": private})
    ini = ("[Common]\nServer=FPMarketsSC-Live\nKeepPrivate=1\nNewsEnable=0\n"
           "[Charts]\nMaxBars=2000000\n[Experts]\nEnabled=0\nAllowLiveTrading=0\nAllowDllImport=0\n"
           "[StartUp]\nExpert=\nScript=\n")
    (runtime/"config/source-readonly.ini").write_text(ini, encoding="utf-16", newline="\n")
    write(ROOT/"evidence/SOURCE_PREPARATION_V1.json", {
        "schema": "zeta-treasury-source-preparation-v1",
        "recorded_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "platform_source": expected, "owned_platform": copied,
        "private_material": "Exact copies retained only in the ignored own reader; no private contents published.",
        "strategy_EA_Include_chart_profiles_copied": 0,
        "history_copied": 0, "reader_launched": False,
        "free_bytes_after": shutil.disk_usage(REPO).free})
    print(json.dumps({"status": "OWN_NO_EA_READER_PREPARED_NOT_LAUNCHED",
                      "free_gib": shutil.disk_usage(REPO).free/1024**3}), flush=True)


def static(item):
    return {field: getattr(item, field, None) for field in FIELDS}


def capture():
    import MetaTrader5 as mt5
    declaration, runtime, raw = context()
    reserve(declaration, runtime, raw)
    freeze = json.loads((ROOT/"evidence/SOURCE_IMPLEMENTATION_FREEZE_V1.json").read_text(encoding="utf-8-sig"))
    for item in freeze["files"]:
        if fingerprint(REPO/item["path"]) != item:
            raise RuntimeError("Frozen source scope or implementation drift")
    progress_path = raw/"source-progress.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8-sig")) if progress_path.exists() else {
        "schema": "zeta-treasury-source-progress-v1", "api_version": mt5.__version__,
        "symbol": SYMBOL, "completed": [], "price_volume_spread_columns_accessed": False,
        "strategy_economic_queries": 0, "account_positions_orders_deals_or_execution_calls": 0}
    completed = {item["month"]: item for item in progress["completed"]}
    try:
        if not mt5.initialize(str(runtime/"terminal64.exe"), server="FPMarketsSC-Live",
                              portable=True, timeout=15000):
            raise RuntimeError("Own reader initialization: "+str(mt5.last_error()))
        terminal = mt5.terminal_info()
        if (terminal is None or Path(terminal.data_path).resolve() != runtime.resolve() or
                not terminal.connected or terminal.trade_allowed or terminal.maxbars < 2000000):
            raise RuntimeError("Own connected no-EA path or history-capacity guard failed")
        progress["terminal"] = {key: getattr(terminal, key) for key in
                               ("path", "data_path", "build", "connected", "trade_allowed", "maxbars")}
        # The exact symbol is the sole history target. Matching names are identity metadata only.
        exact = mt5.symbol_info(SYMBOL)
        progress["exact_symbol_lookup_error"] = list(mt5.last_error())
        matches = mt5.symbols_get(group="*US10YR*")
        progress["matching_inventory_error"] = list(mt5.last_error())
        if matches is None:
            raise RuntimeError("Matching static inventory failed")
        if len(matches) > 25:
            raise RuntimeError("Unexpectedly broad exact-underlying inventory needs a source correction")
        progress["matching_static_contracts"] = [static(item) for item in matches]
        if exact is None:
            if (progress["exact_symbol_lookup_error"][0] not in (1, -4) or
                    any(item.name == SYMBOL for item in matches)):
                raise RuntimeError("Exact lookup is inconsistent or has an operational error")
            progress["status"] = "EXACT_US10YR_NOT_RESOLVED_IN_THIS_NATIVE_OBSERVATION_NO_ALTERNATIVE_HISTORY_REQUEST"
            progress["exact_static_contract"] = None
            write(progress_path, progress, overwrite=True)
            write(ROOT/"evidence/NATIVE_SOURCE_OBSERVATION_V1.json", progress)
            print(json.dumps({"status": progress["status"], "matching_names": [x.name for x in matches]}), flush=True)
            return
        progress["exact_static_contract"] = static(exact)
        if not mt5.symbol_select(SYMBOL, True):
            raise RuntimeError("Exact symbol cannot be selected: "+str(mt5.last_error()))
        progress["status"] = "EXACT_CONTRACT_CAPTURED_TIMESTAMP_ACQUISITION_PENDING"
        write(progress_path, progress, overwrite=True)
        for year in (2023, 2024, 2025):
            for month in range(1, 13):
                label = f"{year}{month:02d}"
                if label in completed:
                    item = completed[label]
                    if item["timestamps"] is not None and fingerprint(REPO/item["timestamps"]["path"]) != item["timestamps"]:
                        raise RuntimeError("Completed own timestamp chunk changed")
                    continue
                if (raw/"STOP_AFTER_CURRENT_MONTH").exists():
                    progress["status"] = "SOURCE_PAUSED_AT_COMPLETED_MONTH"
                    write(progress_path, progress, overwrite=True)
                    print(json.dumps({"status": progress["status"], "completed_months": len(completed)}), flush=True)
                    return
                reserve(declaration, runtime, raw)
                start = dt.datetime(year, month, 1, tzinfo=dt.timezone.utc)
                end = start + dt.timedelta(days=calendar.monthrange(year, month)[1])
                rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start, end)
                api_error = list(mt5.last_error())
                if rates is None and api_error[0] not in (-4,):
                    raise RuntimeError("Native timestamp request failed: "+str(api_error))
                if rates is not None and api_error[0] != 1:
                    raise RuntimeError("Native timestamp payload has an unresolved API error: "+str(api_error))
                if rates is None:
                    times, returned, excluded = np.empty(0, dtype="<i8"), 0, 0
                else:
                    # Only the time field is read, including before exact half-open slicing.
                    observed_times = rates["time"]
                    returned = len(observed_times)
                    keep = (observed_times >= int(start.timestamp())) & (observed_times < int(end.timestamp()))
                    times = np.array(observed_times[keep], dtype="<i8")
                    excluded = returned-len(times)
                    del observed_times, rates, keep
                if len(times) and (np.any(np.diff(times) <= 0) or np.any(times % 60 != 0)):
                    raise RuntimeError("Unexpected M1 time chronology or minute grid")
                timestamp_record = None
                if len(times):
                    target = raw/"timestamps"/(label+".npy")
                    if target.exists():
                        raise RuntimeError("Unsealed existing timestamp chunk must not be overwritten")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temporary = target.with_suffix(".npy.partial")
                    with temporary.open("wb") as handle:
                        np.save(handle, times, allow_pickle=False)
                    temporary.replace(target)
                    timestamp_record = fingerprint(target)
                item = {"month": label, "requested_UTC_dates": [start.isoformat(), end.isoformat()],
                        "api_error": api_error, "returned_rows": returned, "retained_rows": len(times),
                        "outside_half_open_time_rows_excluded": excluded, "timestamps": timestamp_record,
                        "first_raw_epoch": int(times[0]) if len(times) else None,
                        "last_raw_epoch": int(times[-1]) if len(times) else None,
                        "source_raw_dates": np.unique(times//86400).tolist(),
                        "nonconsecutive_minute_gaps": int(np.count_nonzero(np.diff(times) > 60)),
                        "largest_gap_seconds": int(np.max(np.diff(times))) if len(times)>1 else None,
                        "price_volume_spread_columns_read": False,
                        "captured_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
                progress["completed"].append(item)
                completed[label] = item
                progress["status"] = "TIMESTAMP_SOURCE_ACQUISITION_IN_PROGRESS"
                write(progress_path, progress, overwrite=True)
                print(json.dumps({"status": "SOURCE_MONTH_COMPLETE", "month": label,
                                  "timestamp_rows": len(times), "complete_months": len(completed)}), flush=True)
        progress["status"] = "COMPLETE_DECLARED_STATIC_AND_TIMESTAMP_OBSERVATION_NO_READINESS_VERDICT"
        progress["total_timestamp_rows"] = sum(q["retained_rows"] for q in progress["completed"])
        progress["empty_months"] = [q["month"] for q in progress["completed"] if q["retained_rows"] == 0]
        progress["free_bytes_after"] = shutil.disk_usage(REPO).free
        progress["recorded_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        write(progress_path, progress, overwrite=True)
        write(ROOT/"evidence/NATIVE_SOURCE_OBSERVATION_V1.json", progress)
        print(json.dumps({"status": progress["status"], "rows": progress["total_timestamp_rows"],
                          "empty_months": progress["empty_months"]}), flush=True)
    except BaseException as error:
        progress["status"] = "SOURCE_OR_INVOCATION_CORRECTION_REQUIRED"
        progress["error"] = type(error).__name__ + ": " + str(error)
        write(progress_path, progress, overwrite=True)
        raise
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "capture"))
    args = parser.parse_args()
    prepare() if args.operation == "prepare" else capture()
