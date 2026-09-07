"""Acquire the declared native-price input windows through this own Portable.

Only terminal metadata and historical quote APIs are called. No account, order,
position or deal query is used. This is the campaign's production input path.
"""
from pathlib import Path
import csv
import datetime as dt
import hashlib
import json
import shutil

import MetaTrader5 as mt5
import numpy as np

FAMILY = Path(__file__).resolve().parent
ROOT = FAMILY.parents[2]
RUNTIME = ROOT / "optimization/runtime/v7-onnx-online-market-wait-v1-portable"
RAW = ROOT / "optimization/artifacts/raw/v7-onnx-online-market-wait-v1"
PACKED = np.dtype([("time", "<i8"), ("bid", "<f8"), ("ask", "<f8"),
                   ("last", "<f8"), ("volume", "<u8"), ("time_msc", "<i8"),
                   ("flags", "<u4"), ("volume_real", "<f8")])


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def binding():
    paths = [RUNTIME / p for p in ("terminal64.exe", "MetaEditor64.exe", "metatester64.exe")]
    base = RUNTIME / "Bases/FPMarketsSC-Live"
    paths += list((base / "symbols").glob("symbols-*.dat"))
    for symbol in ("US30", "US100", "US500"):
        paths += [p for p in (base / "ticks" / symbol).glob("*.tkc") if p.stem.isdigit() and int(p.stem) <= 202512]
    return [{"path": p.relative_to(RUNTIME).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)}
            for p in sorted(paths)]


def main():
    evidence = FAMILY / "evidence/TICK_INPUT_V1.json"
    if evidence.exists():
        raise RuntimeError("Completed input export is immutable")
    derivation = json.loads((FAMILY / "evidence/RUNTIME_AND_LEDGER_DERIVATION_V1.json").read_text(encoding="utf-8"))
    ledger = ROOT / derivation["ledger"]["path"]
    if sha(ledger) != derivation["ledger"]["sha256"]:
        raise RuntimeError("Own original ledger binding changed")
    out = RAW / "ticks"
    out.mkdir(exist_ok=False)
    before = binding()
    save(FAMILY / "evidence/TICK_INPUT_BEFORE_V1.json", {"utc": dt.datetime.now(dt.timezone.utc).isoformat(), "binding": before})
    windows = []
    total_bytes = 0
    if not mt5.initialize(str(RUNTIME / "terminal64.exe"), portable=True, timeout=30000):
        raise RuntimeError(f"Own terminal initialization correction required: {mt5.last_error()}")
    try:
        info = mt5.terminal_info()
        if info is None or Path(info.path).resolve() != RUNTIME.resolve() or Path(info.data_path).resolve() != RUNTIME.resolve():
            raise RuntimeError("Own Portable path binding did not match; no quotes requested")
        terminal = {"path": str(Path(info.path).resolve()), "data_path": str(Path(info.data_path).resolve()),
                    "build": info.build, "trade_allowed": bool(info.trade_allowed), "sdk_version": mt5.__version__}
        if any((RUNTIME / "MQL5/Experts").rglob("*.ex5")):
            raise RuntimeError("Input terminal must have no Expert executable")
        with ledger.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for index, row in enumerate(rows):
            if row["symbol"] not in ("US30", "US100") or not "2024.01.01" <= row["entry_time_server"] < "2026.01.01":
                raise RuntimeError("Declared input population mismatch")
            t = int(dt.datetime.strptime(row["entry_time_server"], "%Y.%m.%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp())
            lower, upper = t - 61, t + 34
            if shutil.disk_usage(ROOT).free < 30 * 2**30 + 64 * 2**20:
                raise RuntimeError("Storage reserve requires correction")
            ticks = mt5.copy_ticks_range(row["symbol"], lower, upper, mt5.COPY_TICKS_ALL)
            if ticks is None:
                raise RuntimeError(f"Historical tick input correction at index {index}: {mt5.last_error()}")
            packed = np.empty(len(ticks), dtype=PACKED)
            for name in PACKED.names:
                packed[name] = ticks[name]
            if len(packed) and (np.any(np.diff(packed["time_msc"]) < 0)
                    or int(packed["time_msc"][0]) < lower * 1000
                    or int(packed["time_msc"][-1]) >= (upper + 1) * 1000):
                raise RuntimeError("Returned raw clock/order requires correction")
            path = out / f"window-{index:04d}.npy"
            if total_bytes + packed.nbytes + 512 > 384 * 2**20:
                raise RuntimeError("Declared tick export storage cap requires correction")
            np.save(path, packed)
            total_bytes += path.stat().st_size
            windows.append({"index": index, "position_id": row["position_identifier"],
                            "component_id": row["component_id"], "symbol": row["symbol"],
                            "source_entry": row["entry_time_server"], "source_entry_epoch": t,
                            "requested_seconds": [lower, upper], "rows": len(packed),
                            "path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)})
            if (index + 1) % 50 == 0:
                print(json.dumps({"exported_windows": index + 1, "of": len(rows), "bytes": total_bytes}), flush=True)
        after = binding()
        changed = before != after
        result = {"utc": dt.datetime.now(dt.timezone.utc).isoformat(), "status": "COMPLETE_INPUT_EXPORT" if not changed else "INPUT_BINDING_CORRECTION_REQUIRED",
                  "terminal": terminal, "windows": windows, "total_bytes": total_bytes,
                  "packed_fields": PACKED.descr, "before": before, "after": after,
                  "binding_changed": changed, "source_ledger_sha256": sha(ledger),
                  "candidate_2026_values_opened": False, "broker_state_queries": False,
                  "order_calls": False, "live_changes": False, "free_bytes": shutil.disk_usage(ROOT).free}
        save(evidence, result)
        print(json.dumps({"status": result["status"], "windows": len(windows), "tick_rows": sum(w["rows"] for w in windows),
                          "bytes": total_bytes, "free_gib": result["free_bytes"] / 2**30}), flush=True)
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
