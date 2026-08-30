from __future__ import annotations

import csv
import hashlib
import json
import shutil
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[4]
FAMILY = "us30-house-recess-cash-long-v1"
INPUT_ROOT = REPO_ROOT / "lab" / "artifacts" / "raw" / FAMILY / "input"
SOURCE_ROOT = INPUT_ROOT / "source"
MARKET_ROOT = INPUT_ROOT / "market"

SOURCE_MARKET = (
    REPO_ROOT
    / "lab"
    / "artifacts"
    / "raw"
    / "dual-portfolio-formula-interaction-spillover-causality-v1"
    / "input"
    / "market"
    / "US30_M1.parquet"
)
SOURCE_MARKET_SHA256 = "8CD68BC54A736BF49CC020ED7CF41C62BBA5305FA7C1453603EF65173F83B063"

DOWNLOADS = [
    {
        "name": "lamb_ma_pace_kennedy_1997_congressional_calendar.pdf",
        "url": "https://openjournals.libs.uga.edu/fsr/article/download/3805/3252/10829",
        "expected_sha256": None,
        "role": "primary paper defining House recess versus in-session DJIA daily-return state",
    },
    {
        "name": "HDoc-117-2-FloorProceedings.xml",
        "url": "https://clerk.house.gov/floor/HDoc-117-2-FloorProceedings.xml",
        "expected_sha256": "29ADD2BE6B97A8739DF0C395E52239FEEF645F1CF3A437F396A8CC3ABA6607E8",
        "role": "official House floor proceedings for 2022",
    },
    {
        "name": "HDoc-118-1-FloorProceedings.xml",
        "url": "https://clerk.house.gov/floor/HDoc-118-1-FloorProceedings.xml",
        "expected_sha256": "7422AB9507674F182F9C562E00E8150E5D94ECF0CF7A5E9180357CDB03C8055B",
        "role": "official House floor proceedings for 2023",
    },
    {
        "name": "HDoc-118-2-FloorProceedings.xml",
        "url": "https://clerk.house.gov/floor/HDoc-118-2-FloorProceedings.xml",
        "expected_sha256": "B3F1EC9F4238C78756D7E313EBA06FCC9296B98F84F86DE3AFDAE70ABEA53EF6",
        "role": "official House floor proceedings for 2024",
    },
    {
        "name": "HDoc-119-1-FloorProceedings.xml",
        "url": "https://clerk.house.gov/floor/HDoc-119-1-FloorProceedings.xml",
        "expected_sha256": "FE4FDBD980C4318D5C3FA24706DB8268043A3FB78B576928BB3D535B5933935B",
        "role": "official House floor proceedings for 2025",
    },
    {
        "name": "HDoc-119-2-FloorProceedings.xml",
        "url": "https://clerk.house.gov/floor/HDoc-119-2-FloorProceedings.xml",
        "expected_sha256": "92CC9725B1AF560A2098436597D17AF0D9F92C2698C3340E099F44B7BB55DA30",
        "role": "official House floor proceedings frozen through 2026-08-27",
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_receipt(path: Path) -> dict[str, Any]:
    return {
        "name": path.relative_to(INPUT_ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def write_text_once(path: Path, text: str) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite frozen acquisition output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def download_once(item: dict[str, Any]) -> Path:
    destination = SOURCE_ROOT / item["name"]
    if destination.exists():
        raise RuntimeError(f"refusing to overwrite frozen download: {destination}")
    request = urllib.request.Request(
        item["url"],
        headers={"User-Agent": "Project-Zeta-Terminus-Next/Unit115 source acquisition"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = response.read()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    actual = sha256(destination)
    expected = item.get("expected_sha256")
    if expected and actual != expected:
        raise RuntimeError(
            f"official source changed before freeze: {item['name']} {actual} != {expected}"
        )
    return destination


def normalize_house_schedule(paths: list[Path]) -> tuple[Path, dict[str, Any]]:
    records: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}
    for path in paths:
        root = ET.parse(path).getroot()
        congress = (root.findtext("congress") or "").strip()
        session = (root.findtext("session") or "").strip()
        count = 0
        for activity in root.findall("legislative_activity"):
            day = activity.find("legislative_day")
            if day is None or "date" not in day.attrib:
                raise RuntimeError(f"missing legislative day in {path.name}")
            date = day.attrib["date"]
            next_values = sorted(
                {
                    node.attrib["next-legislative-day-convenes"]
                    for node in activity.findall(".//legislative_day_finished")
                    if node.attrib.get("next-legislative-day-convenes")
                }
            )
            if not next_values:
                raise RuntimeError(f"missing announced next House meeting after {date}")
            records.append(
                {
                    "date": date,
                    "announced_next_session_values": ";".join(next_values),
                    "congress": congress,
                    "session": session,
                    "source_file": path.name,
                }
            )
            count += 1
        source_counts[path.name] = count

    records.sort(key=lambda row: row["date"])
    dates = [row["date"] for row in records]
    if len(dates) != len(set(dates)):
        raise RuntimeError("duplicate House legislative dates across bulk files")
    if dates != sorted(dates):
        raise RuntimeError("House legislative dates are not monotonic")

    chain_faults: list[dict[str, Any]] = []
    for current, following in zip(records, records[1:]):
        announced_dates = {
            value[:8]
            for value in current["announced_next_session_values"].split(";")
        }
        if following["date"] not in announced_dates:
            chain_faults.append(
                {
                    "date": current["date"],
                    "announced": sorted(announced_dates),
                    "actual_next": following["date"],
                }
            )
    if chain_faults:
        raise RuntimeError(f"House announced-next chain mismatch: {chain_faults[:3]}")

    normalized = SOURCE_ROOT / "house_floor_schedule_frozen_20260830.csv"
    lines: list[str] = []
    header = [
        "date",
        "announced_next_session_values",
        "congress",
        "session",
        "source_file",
    ]
    lines.append(",".join(header))
    for row in records:
        encoded: list[str] = []
        for name in header:
            value = str(row[name])
            if any(character in value for character in ',"\n'):
                value = '"' + value.replace('"', '""') + '"'
            encoded.append(value)
        lines.append(",".join(encoded))
    write_text_once(normalized, "\n".join(lines) + "\n")

    return normalized, {
        "rows": len(records),
        "first_date": records[0]["date"],
        "last_date": records[-1]["date"],
        "duplicate_dates": len(dates) - len(set(dates)),
        "announced_next_chain_faults": len(chain_faults),
        "source_counts": source_counts,
    }


def main() -> None:
    if INPUT_ROOT.exists() and any(INPUT_ROOT.rglob("*")):
        raise RuntimeError(f"input root is not empty: {INPUT_ROOT}")
    SOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    MARKET_ROOT.mkdir(parents=True, exist_ok=True)

    downloaded: list[Path] = []
    for item in DOWNLOADS:
        downloaded.append(download_once(item))

    if not SOURCE_MARKET.exists():
        raise RuntimeError(f"one-time US30 source is missing: {SOURCE_MARKET}")
    if sha256(SOURCE_MARKET) != SOURCE_MARKET_SHA256:
        raise RuntimeError("one-time US30 source hash mismatch")
    market_destination = MARKET_ROOT / "US30_M1_20220103_20260731.parquet"
    if market_destination.exists():
        raise RuntimeError(f"refusing to overwrite market input: {market_destination}")
    shutil.copyfile(SOURCE_MARKET, market_destination)
    if sha256(market_destination) != SOURCE_MARKET_SHA256:
        raise RuntimeError("copied US30 M1 hash mismatch")

    xml_paths = [path for path in downloaded if path.suffix.lower() == ".xml"]
    normalized_path, schedule_summary = normalize_house_schedule(xml_paths)

    market = pd.read_parquet(market_destination, columns=["time"])
    if list(market.columns) != ["time"]:
        raise RuntimeError("US30 M1 time-only schema probe failed")
    if market["time"].isna().any() or market["time"].duplicated().any():
        raise RuntimeError("US30 M1 time surface is null or duplicated")
    if not market["time"].is_monotonic_increasing:
        raise RuntimeError("US30 M1 time surface is not monotonic")

    input_paths = sorted(
        downloaded + [normalized_path, market_destination],
        key=lambda path: path.relative_to(INPUT_ROOT).as_posix(),
    )
    files = [file_receipt(path) for path in input_paths]
    manifest_lines = [
        f"{item['name']}|{item['bytes']}|{item['sha256']}" for item in files
    ]
    manifest_sha256 = hashlib.sha256("\n".join(manifest_lines).encode("utf-8")).hexdigest().upper()

    source_roles = {
        item["name"]: {"url": item["url"], "role": item["role"]}
        for item in DOWNLOADS
    }
    summary = {
        "schema": "zeta-next-us30-house-recess-input-acquisition-v1",
        "family": FAMILY,
        "status": "COMPLETE_OUTCOME_FREE_INPUT_FREEZE",
        "acquisition_date": "2026-08-30",
        "source_roles": source_roles,
        "house_schedule": schedule_summary,
        "market_copy": {
            "source_path": SOURCE_MARKET.relative_to(REPO_ROOT).as_posix(),
            "destination": market_destination.relative_to(REPO_ROOT).as_posix(),
            "rows": int(len(market)),
            "first_epoch": int(market["time"].iloc[0]),
            "last_epoch": int(market["time"].iloc[-1]),
            "duplicate_epochs": int(market["time"].duplicated().sum()),
            "columns_loaded": ["time"],
            "price_or_spread_fields_loaded": False,
        },
        "predeclaration_schema_probe_disclosure": {
            "occurred_before_family_open": True,
            "rows_displayed": 4,
            "scope": "first two and last two raw rows only",
            "target_cash_boundary_rows_displayed": 0,
            "house_state_joined": False,
            "return_or_economic_metric_calculated": False,
            "purpose": "confirm the inherited Parquet schema and physical date range",
        },
        "immutable_inputs": {
            "manifest_rule": "Sort relative-name|bytes|uppercase-SHA256 by relative name, join with LF, hash UTF-8 without trailing LF.",
            "files": files,
            "manifest_sha256": manifest_sha256,
        },
        "outcome_firewall": {
            "target_cash_entry_or_exit_price_loaded": False,
            "target_cash_spread_loaded": False,
            "house_state_joined_to_target_economics": False,
            "return_or_pnl_calculated": False,
            "profit_factor_drawdown_control_gate_or_verdict_calculated": False,
        },
        "live_master_broker_account_touched": False,
    }
    write_text_once(
        INPUT_ROOT / "acquisition-summary.json",
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
