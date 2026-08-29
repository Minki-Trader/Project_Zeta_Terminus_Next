from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import MetaTrader5 as mt5


FAMILY = "us500-earnings-extrapolation-monthly-signal-v1"
ROOT = Path(__file__).resolve().parents[4]
RUNTIME_ROOT = ROOT / "lab" / "runtime" / "ussr105-portable"
TERMINAL = RUNTIME_ROOT / "terminal64.exe"
INPUT_ROOT = ROOT / "lab" / "artifacts" / "raw" / FAMILY / "input"
SOURCE_ROOT = INPUT_ROOT / "source"
MARKET_ROOT = INPUT_ROOT / "market"

AUTHOR_DATA = SOURCE_ROOT / "vwretd_clean_202106.tab"
AUTHOR_CODE = SOURCE_ROOT / "TSMomentumImplementation_final.do"
AUTHOR_METADATA = SOURCE_ROOT / "dataverse_metadata_v1.json"
US500_D1 = MARKET_ROOT / "US500_D1_BARS_20210601_20260821.csv"
US500_M15 = MARKET_ROOT / "US500_M15_BARS_20220701_20260821.csv"
US500_SPEC = MARKET_ROOT / "US500_SYMBOL_SPEC_V1.json"
SUMMARY_PATH = INPUT_ROOT / "acquisition-summary.json"

AUTHOR_DATA_URL = "https://dataverse.harvard.edu/api/access/datafile/10802963"
AUTHOR_CODE_URL = "https://dataverse.harvard.edu/api/access/datafile/10802971"
AUTHOR_METADATA_URL = (
    "https://dataverse.harvard.edu/api/datasets/:persistentId/"
    "?persistentId=doi:10.7910/DVN/AFOM9J"
)
AUTHOR_DATA_SHA256 = "4BFB7621521976FB51B59D6F14B706E55A287A3DB5F15A896CA8128098D5CA65"
AUTHOR_CODE_SHA256 = "050D4B37CF2B0E3B0579C755DA11BC6912FCDEC335A30AC60AFD8A60446A9528"

M15_SOURCE = (
    ROOT
    / "lab"
    / "artifacts"
    / "raw"
    / "us500-turn-of-month-cash-session-rebalancing-v1"
    / "input"
    / "US500_M15_BARS_20220701_20260821.csv"
)
SPEC_SOURCE = M15_SOURCE.with_name("US500_SYMBOL_SPEC_V1.json")
M15_SHA256 = "A3A5BDEBCE22327B37A38B3D443898356856FCA5F1B4BBED7CA63C148189073A"
SPEC_SHA256 = "9DF9AAE5DEB54547283DE612FF00081248759E8F7A04A3158D7A607AFABE5918"

SYMBOL = "US500"
START_UTC = datetime(2021, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
END_UTC = datetime(2026, 8, 21, 23, 59, 59, tzinfo=timezone.utc)
COLUMNS = (
    "time_epoch",
    "time_utc",
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


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def download_once(url: str, path: Path) -> None:
    if path.exists():
        return
    request = urllib.request.Request(url, headers={"User-Agent": "Zeta-Research/1.0"})
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with urllib.request.urlopen(request, timeout=120) as response, temp_path.open("wb") as out:
        shutil.copyfileobj(response, out)
    os.replace(temp_path, path)


def require_hash(path: Path, expected: str) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"required input missing: {path}")
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError(f"unexpected bytes for {path.name}: {actual}")
    return {"path": relative(path), "bytes": path.stat().st_size, "sha256": actual}


def copy_once(source: Path, target: Path, expected: str) -> dict[str, Any]:
    require_hash(source, expected)
    if not target.exists():
        shutil.copyfile(source, target)
    return require_hash(target, expected)


def validate_author_metadata() -> dict[str, Any]:
    with AUTHOR_METADATA.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("status") != "OK":
        raise RuntimeError("Harvard Dataverse metadata status is not OK")
    version = payload["data"]["latestVersion"]
    if version.get("versionNumber") != 1 or version.get("versionMinorNumber") != 0:
        raise RuntimeError("unexpected Dataverse version")
    if version.get("license", {}).get("name") != "CC0 1.0":
        raise RuntimeError("unexpected Dataverse license")
    files = {item["dataFile"]["id"]: item for item in version["files"]}
    if 10802963 not in files or 10802971 not in files:
        raise RuntimeError("fixed author data or code file id is absent")
    return {
        "path": relative(AUTHOR_METADATA),
        "bytes": AUTHOR_METADATA.stat().st_size,
        "sha256": sha256(AUTHOR_METADATA),
        "dataset_doi": "10.7910/DVN/AFOM9J",
        "version": "1.0",
        "license": "CC0 1.0",
        "file_count": len(version["files"]),
        "fixed_file_ids_present": True,
    }


def finite_positive(value: float) -> bool:
    return math.isfinite(value) and value > 0.0


def write_d1(rates: object) -> dict[str, Any]:
    epochs: list[int] = []
    temp_path = US500_D1.with_suffix(US500_D1.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(COLUMNS)
        for rate in rates:
            epoch = int(rate["time"])
            ohlc = tuple(float(rate[name]) for name in ("open", "high", "low", "close"))
            if not all(finite_positive(value) for value in ohlc):
                raise RuntimeError(f"nonpositive or nonfinite D1 OHLC at epoch {epoch}")
            if epochs and epoch <= epochs[-1]:
                raise RuntimeError(f"non-increasing D1 epoch at {epoch}")
            tick_volume = int(rate["tick_volume"])
            spread = int(rate["spread"])
            real_volume = int(rate["real_volume"])
            if tick_volume < 0 or spread < 0 or real_volume < 0:
                raise RuntimeError(f"negative D1 volume or spread at epoch {epoch}")
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
    if not epochs:
        raise RuntimeError("copy_rates_range returned zero D1 rows")
    os.replace(temp_path, US500_D1)
    return {
        "path": relative(US500_D1),
        "bytes": US500_D1.stat().st_size,
        "sha256": sha256(US500_D1),
        "rows": len(epochs),
        "first_time_utc": datetime.fromtimestamp(epochs[0], timezone.utc).isoformat(),
        "last_time_utc": datetime.fromtimestamp(epochs[-1], timezone.utc).isoformat(),
        "unique_strictly_increasing_epoch": True,
        "finite_positive_ohlc": True,
        "nonnegative_volume_and_spread": True,
    }


def combined_manifest(files: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda item: relative(item)):
        digest.update(relative(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256(path)))
        digest.update(b"\0")
    return digest.hexdigest().upper()


def main() -> int:
    if not TERMINAL.is_file():
        raise RuntimeError(f"dedicated terminal missing: {TERMINAL}")
    if US500_D1.exists() or SUMMARY_PATH.exists():
        raise RuntimeError("frozen D1 acquisition output already exists; do not overwrite it")

    SOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    MARKET_ROOT.mkdir(parents=True, exist_ok=True)
    download_once(AUTHOR_DATA_URL, AUTHOR_DATA)
    download_once(AUTHOR_CODE_URL, AUTHOR_CODE)
    download_once(AUTHOR_METADATA_URL, AUTHOR_METADATA)
    author_data = require_hash(AUTHOR_DATA, AUTHOR_DATA_SHA256)
    author_code = require_hash(AUTHOR_CODE, AUTHOR_CODE_SHA256)
    author_metadata = validate_author_metadata()
    m15 = copy_once(M15_SOURCE, US500_M15, M15_SHA256)
    spec = copy_once(SPEC_SOURCE, US500_SPEC, SPEC_SHA256)

    initialized = False
    try:
        initialized = bool(mt5.initialize(str(TERMINAL), timeout=120_000, portable=True))
        if not initialized:
            raise RuntimeError(f"MetaTrader5 initialize failed: {mt5.last_error()}")
        if not mt5.symbol_select(SYMBOL, True):
            raise RuntimeError(f"symbol_select failed for {SYMBOL}: {mt5.last_error()}")
        rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_D1, START_UTC, END_UTC)
        if rates is None:
            raise RuntimeError(f"copy_rates_range failed for {SYMBOL}: {mt5.last_error()}")
    finally:
        if initialized:
            mt5.shutdown()

    d1 = write_d1(rates)
    frozen_files = [AUTHOR_DATA, AUTHOR_CODE, AUTHOR_METADATA, US500_D1, US500_M15, US500_SPEC]
    summary = {
        "schema": "zeta-next-us500-earnings-extrapolation-monthly-signal-acquisition-summary-v1",
        "created_at_local": "2026-08-30",
        "family": FAMILY,
        "python": sys.version.split()[0],
        "metatrader5_package": mt5.__version__,
        "runtime": relative(RUNTIME_ROOT) + "/",
        "terminal_sha256": sha256(TERMINAL),
        "source": {
            "publisher_dataset": author_metadata,
            "monthly_return_data": author_data,
            "implementation_code": author_code,
        },
        "market": {
            "d1": d1,
            "m15": m15,
            "symbol_spec": spec,
        },
        "request": {
            "symbol": SYMBOL,
            "timeframe": "D1",
            "from_utc": START_UTC.isoformat(),
            "to_utc": END_UTC.isoformat(),
            "api_calls": ["initialize", "symbol_select", "copy_rates_range", "shutdown"],
            "forbidden_account_position_order_deal_trade_calls": 0,
        },
        "input_files": len(frozen_files),
        "input_bytes": sum(path.stat().st_size for path in frozen_files),
        "manifest_sha256": combined_manifest(frozen_files),
    }
    temp_summary = SUMMARY_PATH.with_suffix(SUMMARY_PATH.suffix + ".tmp")
    temp_summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp_summary, SUMMARY_PATH)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
