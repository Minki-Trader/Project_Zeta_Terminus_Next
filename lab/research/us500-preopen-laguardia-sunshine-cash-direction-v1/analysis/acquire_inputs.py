from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests


REPO_ROOT = Path(__file__).resolve().parents[4]
FAMILY = "us500-preopen-laguardia-sunshine-cash-direction-v1"
INPUT_ROOT = REPO_ROOT / "lab" / "artifacts" / "raw" / FAMILY / "input"
SOURCE_ROOT = INPUT_ROOT / "source"
MARKET_ROOT = INPUT_ROOT / "market"
STATION_ID = "USW00014732"
STATION_NAME = "LA GUARDIA AIRPORT, NY US"
TARGET_START = date(2022, 7, 1)
TARGET_END = date(2026, 7, 31)
TARGET_HOURS = (5, 6, 7, 8)
NEW_YORK = ZoneInfo("America/New_York")
LOCAL_STANDARD = timezone(timedelta(hours=-5), name="EST")
LCD_URL = (
    "https://www.ncei.noaa.gov/oa/local-climatological-data/v2/access/"
    "{year}/LCD_{station}_{year}.csv"
)
LCD_DOCUMENTATION_URL = (
    "https://www.ncei.noaa.gov/oa/local-climatological-data/v2/doc/"
    "lcdv2_DOCUMENTATION.pdf"
)
PAPER_URL = "https://www.tylergshumway.org/Hirshleifer-GoodDaySunshine-2003.pdf"
HEADERS = {
    "User-Agent": "Project-Zeta-Terminus-Next research acquisition/1.0",
    "Accept": "*/*",
}
SKY_VALUE = {
    "CLR": 0,
    "SKC": 0,
    "NSC": 0,
    "NCD": 0,
    "FEW": 2,
    "SCT": 4,
    "BKN": 7,
    "OVC": 8,
    "VV": 8,
    "X": 8,
}
SKY_TOKEN = re.compile(r"\b(CLR|SKC|NSC|NCD|FEW|SCT|BKN|OVC|VV|X):(\d{2})\b")
PERIODS = (
    ("P1_2022H2_2023", date(2022, 7, 1), date(2024, 1, 1)),
    ("P2_2024", date(2024, 1, 1), date(2025, 1, 1)),
    ("P3_2025", date(2025, 1, 1), date(2026, 1, 1)),
    ("P4_2026_JAN_MAY", date(2026, 1, 1), date(2026, 6, 1)),
    ("P5_LATEST_2026_JUN_JUL", date(2026, 6, 1), date(2026, 8, 1)),
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def file_receipt(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return {
        "name": path.relative_to(INPUT_ROOT).as_posix(),
        "bytes": size,
        "sha256": digest.hexdigest().upper(),
    }


def write_once(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise RuntimeError(f"refusing to replace frozen acquisition byte: {path}")
        return
    path.write_bytes(payload)


def fetch(
    session: requests.Session, url: str, minimum_bytes: int
) -> tuple[bytes, dict[str, Any]]:
    response = session.get(url, timeout=180)
    response.raise_for_status()
    payload = response.content
    if len(payload) < minimum_bytes:
        raise RuntimeError(f"unexpectedly short source response: {url} ({len(payload)} bytes)")
    return payload, {
        "url": url,
        "http_status": response.status_code,
        "last_modified": response.headers.get("Last-Modified"),
        "etag": response.headers.get("ETag"),
    }


def period_name(value: date) -> str:
    for name, start, end in PERIODS:
        if start <= value < end:
            return name
    return "OUTSIDE_TARGET"


def parse_lcd_year(
    year: int, payload: bytes
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reader = csv.DictReader(StringIO(payload.decode("utf-8-sig")))
    required = {"STATION", "DATE", "NAME", "REPORT_TYPE", "HourlySkyConditions", "REM"}
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise RuntimeError(f"LCDv2 {year} schema mismatch")

    candidates: list[dict[str, Any]] = []
    total_rows = 0
    station_rows = 0
    routine_rows = 0
    target_hour_rows = 0
    target_hour_rows_without_sky = 0
    encoded_values_by_code: dict[str, set[int]] = defaultdict(set)
    for row_number, row in enumerate(reader, start=2):
        total_rows += 1
        if row.get("STATION") != STATION_ID:
            continue
        station_rows += 1
        if (row.get("REPORT_TYPE") or "").strip() != "FM-15":
            continue
        routine_rows += 1

        standard_local = datetime.fromisoformat(row["DATE"])
        observed_utc = standard_local.replace(tzinfo=LOCAL_STANDARD).astimezone(timezone.utc)
        observed_et = observed_utc.astimezone(NEW_YORK)
        if not (TARGET_START <= observed_et.date() <= TARGET_END):
            continue
        if observed_et.hour not in TARGET_HOURS:
            continue
        target_hour_rows += 1

        raw_sky = (row.get("HourlySkyConditions") or "").strip()
        decoded: list[tuple[str, int]] = []
        for code, encoded_amount in SKY_TOKEN.findall(raw_sky.upper()):
            encoded_values_by_code[code].add(int(encoded_amount))
            decoded.append((code, SKY_VALUE[code]))
        if not decoded and "CAVOK" in (row.get("REM") or "").upper():
            decoded = [("CAVOK", 0)]
        if not decoded:
            target_hour_rows_without_sky += 1
            continue

        maximum = max(value for _, value in decoded)
        maximum_codes = sorted({code for code, value in decoded if value == maximum})
        candidates.append(
            {
                "local_date": observed_et.date(),
                "local_hour": observed_et.hour,
                "local_minute": observed_et.minute,
                "utc_timestamp": observed_utc.isoformat().replace("+00:00", "Z"),
                "local_timestamp": observed_et.isoformat(),
                "lcd_standard_timestamp": standard_local.isoformat(),
                "report_type": "FM-15",
                "sky_cover_oktas": maximum,
                "maximum_sky_codes": "+".join(maximum_codes),
                "raw_hourly_sky_conditions": raw_sky if raw_sky else "CAVOK",
                "source_file": f"LCD_{STATION_ID}_{year}.csv",
                "source_row": row_number,
            }
        )
    if total_rows < 5000 or station_rows != total_rows:
        raise RuntimeError(
            f"LCDv2 {year} station/row geometry is unexpected: {station_rows}/{total_rows}"
        )
    if target_hour_rows == 0 or not candidates:
        raise RuntimeError(f"LCDv2 {year} has no usable target-hour routine METAR rows")
    return candidates, {
        "year": year,
        "total_rows": total_rows,
        "station_rows": station_rows,
        "routine_fm15_rows": routine_rows,
        "target_hour_fm15_rows": target_hour_rows,
        "target_hour_rows_with_decoded_sky": len(candidates),
        "target_hour_rows_without_decoded_sky": target_hour_rows_without_sky,
        "encoded_amounts_by_code": {
            code: sorted(values) for code, values in sorted(encoded_values_by_code.items())
        },
    }


def choose_hourly_rows(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    grouped: dict[tuple[date, int], list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        grouped[(row["local_date"], int(row["local_hour"]))].append(row)
    selected: list[dict[str, Any]] = []
    duplicate_groups = 0
    for key in sorted(grouped):
        rows = grouped[key]
        if len(rows) > 1:
            duplicate_groups += 1
        rows.sort(
            key=lambda row: (
                abs(int(row["local_minute"]) - 51),
                -int(row["local_minute"]),
                row["utc_timestamp"],
                int(row["source_row"]),
            )
        )
        selected.append(rows[0])
    return selected, duplicate_groups


def hourly_csv(rows: list[dict[str, Any]]) -> bytes:
    fields = (
        "local_date",
        "local_hour",
        "local_minute",
        "utc_timestamp",
        "local_timestamp",
        "lcd_standard_timestamp",
        "report_type",
        "sky_cover_oktas",
        "maximum_sky_codes",
        "raw_hourly_sky_conditions",
        "source_file",
        "source_row",
    )
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({**row, "local_date": row["local_date"].isoformat()})
    return buffer.getvalue().encode("utf-8")


def daily_rows(hourly: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[date, dict[int, dict[str, Any]]] = defaultdict(dict)
    for row in hourly:
        key = row["local_date"]
        hour = int(row["local_hour"])
        if hour in grouped[key]:
            raise RuntimeError(f"duplicate selected local hour: {key} {hour}")
        grouped[key][hour] = row

    rows: list[dict[str, Any]] = []
    value = TARGET_START
    while value <= TARGET_END:
        observations = grouped.get(value, {})
        complete = all(hour in observations for hour in TARGET_HOURS)
        sky_values = [
            int(observations[hour]["sky_cover_oktas"])
            for hour in TARGET_HOURS
            if hour in observations
        ]
        mean = sum(sky_values) / len(sky_values) if sky_values else None
        direction = ""
        classification = "INCOMPLETE"
        if complete:
            direction = "LONG" if mean <= 4.0 else "SHORT"
            classification = "SUNNY_OR_MIXED_0_TO_4" if mean <= 4.0 else "CLOUDY_ABOVE_4"
        row: dict[str, Any] = {
            "date": value.isoformat(),
            "period": period_name(value),
            "observation_count": len(sky_values),
            "complete_four_hours": int(complete),
            "sky_cover_mean_oktas": "" if mean is None else f"{mean:.6f}",
            "direction": direction,
            "classification": classification,
        }
        for hour in TARGET_HOURS:
            observation = observations.get(hour)
            row[f"sky_{hour:02d}_oktas"] = "" if observation is None else observation["sky_cover_oktas"]
            row[f"obs_{hour:02d}_utc"] = "" if observation is None else observation["utc_timestamp"]
        rows.append(row)
        value += timedelta(days=1)
    return rows


def daily_csv(rows: list[dict[str, Any]]) -> bytes:
    fields = (
        "date",
        "period",
        "observation_count",
        "complete_four_hours",
        "sky_cover_mean_oktas",
        "direction",
        "classification",
        "sky_05_oktas",
        "obs_05_utc",
        "sky_06_oktas",
        "obs_06_utc",
        "sky_07_oktas",
        "obs_07_utc",
        "sky_08_oktas",
        "obs_08_utc",
    )
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def main() -> None:
    SOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    MARKET_ROOT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)

    fetched: dict[str, bytes] = {}
    source_receipts: list[dict[str, Any]] = []
    all_candidates: list[dict[str, Any]] = []
    yearly_parse: list[dict[str, Any]] = []
    for year in range(2022, 2027):
        url = LCD_URL.format(year=year, station=STATION_ID)
        payload, network = fetch(session, url, 4_000_000)
        parsed, parse_receipt = parse_lcd_year(year, payload)
        all_candidates.extend(parsed)
        yearly_parse.append(parse_receipt)
        filename = f"LCD_{STATION_ID}_{year}.csv"
        fetched[filename] = payload
        source_receipts.append(
            {
                "name": f"source/{filename}",
                **network,
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
                **parse_receipt,
            }
        )

    documentation, documentation_network = fetch(session, LCD_DOCUMENTATION_URL, 100_000)
    if not documentation.startswith(b"%PDF"):
        raise RuntimeError("LCDv2 documentation response is not a PDF")
    fetched["lcdv2_DOCUMENTATION.pdf"] = documentation
    source_receipts.append(
        {
            "name": "source/lcdv2_DOCUMENTATION.pdf",
            **documentation_network,
            "bytes": len(documentation),
            "sha256": sha256_bytes(documentation),
        }
    )

    paper, paper_network = fetch(session, PAPER_URL, 100_000)
    if not paper.startswith(b"%PDF"):
        raise RuntimeError("Good Day Sunshine response is not a PDF")
    fetched["hirshleifer_shumway_2003_good_day_sunshine.pdf"] = paper
    source_receipts.append(
        {
            "name": "source/hirshleifer_shumway_2003_good_day_sunshine.pdf",
            **paper_network,
            "bytes": len(paper),
            "sha256": sha256_bytes(paper),
        }
    )

    selected_hourly, duplicate_groups = choose_hourly_rows(all_candidates)
    normalized_hourly = hourly_csv(selected_hourly)
    normalized_daily_rows = daily_rows(selected_hourly)
    normalized_daily = daily_csv(normalized_daily_rows)
    fetched["laguardia_morning_sky_hourly_20220701_20260731.csv"] = normalized_hourly
    fetched["laguardia_morning_sky_daily_20220701_20260731.csv"] = normalized_daily
    source_receipts.extend(
        [
            {
                "name": "source/laguardia_morning_sky_hourly_20220701_20260731.csv",
                "derived_from": [f"source/LCD_{STATION_ID}_{year}.csv" for year in range(2022, 2027)],
                "bytes": len(normalized_hourly),
                "sha256": sha256_bytes(normalized_hourly),
                "rows": len(selected_hourly),
                "selection": "one FM-15 row per actual 05/06/07/08 America/New_York hour, nearest minute 51",
            },
            {
                "name": "source/laguardia_morning_sky_daily_20220701_20260731.csv",
                "derived_from": ["source/laguardia_morning_sky_hourly_20220701_20260731.csv"],
                "bytes": len(normalized_daily),
                "sha256": sha256_bytes(normalized_daily),
                "rows": len(normalized_daily_rows),
                "complete_rows": sum(int(row["complete_four_hours"]) for row in normalized_daily_rows),
            },
        ]
    )

    for filename, payload in fetched.items():
        write_once(SOURCE_ROOT / filename, payload)

    source_market = (
        REPO_ROOT
        / "lab"
        / "artifacts"
        / "raw"
        / "us500-blockbuster-release-next-week-mood-v1"
        / "input"
        / "market"
    )
    copied_market: list[dict[str, Any]] = []
    for filename in (
        "US500_M15_BARS_20220701_20260821.csv",
        "US500_SYMBOL_SPEC_V1.json",
    ):
        source = source_market / filename
        target = MARKET_ROOT / filename
        if not source.is_file():
            raise RuntimeError(f"one-time source market input is missing: {source}")
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise RuntimeError(f"refusing to replace frozen market byte: {target}")
        if not target.exists():
            shutil.copyfile(source, target)
        copied_market.append(
            {
                **file_receipt(target),
                "one_time_copy_from": source.relative_to(REPO_ROOT).as_posix(),
            }
        )

    complete_by_period = {
        name: sum(
            int(row["complete_four_hours"])
            for row in normalized_daily_rows
            if row["period"] == name
        )
        for name, _, _ in PERIODS
    }
    direction_by_period = {
        name: {
            direction: sum(
                1
                for row in normalized_daily_rows
                if row["period"] == name and row["direction"] == direction
            )
            for direction in ("LONG", "SHORT")
        }
        for name, _, _ in PERIODS
    }
    input_files = sorted(
        [file_receipt(path) for path in SOURCE_ROOT.iterdir() if path.is_file()]
        + [file_receipt(path) for path in MARKET_ROOT.iterdir() if path.is_file()],
        key=lambda item: item["name"],
    )
    manifest_lines = [f"{item['name']}|{item['bytes']}|{item['sha256']}" for item in input_files]
    manifest_sha256 = sha256_bytes("\n".join(manifest_lines).encode("utf-8"))
    summary = {
        "schema": "zeta-next-us500-laguardia-sunshine-input-acquisition-v1",
        "family": FAMILY,
        "acquired_at_local_date": date.today().isoformat(),
        "source": {
            "paper": "Hirshleifer and Shumway (2003), Good Day Sunshine: Stock Returns and the Weather",
            "paper_doi": "10.1111/1540-6261.00556",
            "weather_dataset": "NOAA NCEI Local Climatological Data Version 2",
            "weather_lineage": "LCDv2 hourly observations are derived from GHCNh; the station/year files expose current FM-15 METAR sky conditions",
            "station": STATION_ID,
            "station_name": STATION_NAME,
            "receipts": source_receipts,
            "yearly_parse": yearly_parse,
        },
        "normalization": {
            "target_dates": [TARGET_START.isoformat(), TARGET_END.isoformat()],
            "source_date_clock": "LCDv2 DATE is local standard time; interpret as UTC-05:00 before converting to America/New_York",
            "decision_timezone": "America/New_York",
            "target_actual_local_hours": list(TARGET_HOURS),
            "routine_report_type": "FM-15",
            "hourly_tie_break": "nearest actual local minute to 51, then later minute, UTC timestamp, source row",
            "sky_mapping_oktas": SKY_VALUE,
            "sky_aggregation": "maximum decoded HourlySkyConditions amount",
            "daily_aggregation": "arithmetic mean of exactly four selected hourly amounts",
            "primary_direction": "LONG if mean <= 4.0; SHORT if mean > 4.0",
            "candidate_rows_before_hour_deduplication": len(all_candidates),
            "selected_hourly_rows": len(selected_hourly),
            "duplicate_date_hour_groups_resolved": duplicate_groups,
            "daily_rows": len(normalized_daily_rows),
            "complete_daily_rows": sum(int(row["complete_four_hours"]) for row in normalized_daily_rows),
            "complete_daily_rows_by_period": complete_by_period,
            "complete_daily_directions_by_period": direction_by_period,
        },
        "market": {
            "receipts": copied_market,
            "market_file_parsed": False,
            "mt5_acquisition_calls": 0,
            "tester_calls": 0,
            "account_position_order_deal_trade_calls": 0,
        },
        "engineering_correction": {
            "initial_source": "GHCNh direct yearly PSV",
            "observed_fault": "LaGuardia FM15 rows stopped at 2026-04-13, leaving latest P5 with zero complete days",
            "research_judgment": "none; price and spread columns remained unopened",
            "correction": "replace the whole weather surface with one uniform current NOAA LCDv2 station/year series for every period",
        },
        "immutable_inputs": {
            "files": input_files,
            "manifest_sha256": manifest_sha256,
        },
    }
    summary_payload = (json.dumps(summary, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    write_once(INPUT_ROOT / "acquisition-summary.json", summary_payload)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
