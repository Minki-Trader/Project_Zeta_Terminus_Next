#!/usr/bin/env python3
"""Freeze the official GSCPI vintage matrix for Frontier Unit 116.

This is a finite source acquisition, not a validator, test harness, reusable
CLI product, trading program, or broker/account query.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


REPO = Path(__file__).resolve().parents[4]
FAMILY = REPO / "lab/research/initial-release-gscpi-above-normal-portfolio-state-v1"
EVIDENCE = FAMILY / "evidence"
SOURCE = EVIDENCE / "source"

VINTAGE_URL = (
    "https://www.newyorkfed.org/medialibrary/research/interactives/data/"
    "gscpi/gscpi_interactive_data.csv"
)
CONFIG_URL = (
    "https://www.newyorkfed.org/medialibrary/research/interactives/data/"
    "gscpi/gscpi.json"
)
PRODUCT_URL = "https://www.newyorkfed.org/research/policy/gscpi"
PRESS_RELEASE_URL = (
    "https://www.newyorkfed.org/newsevents/news/research/2022/20220518"
)

VINTAGE_PATH = SOURCE / "NYFED_GSCPI_VINTAGES_THROUGH_2026_08.csv"
CONFIG_PATH = SOURCE / "NYFED_GSCPI_CONFIG_2026_08.json"
SCHEDULE_PATH = EVIDENCE / "GSCPI_INITIAL_RELEASE_SCHEDULE_V1.csv"
RECEIPT_PATH = EVIDENCE / "GSCPI_SOURCE_ACQUISITION_RECEIPT_V1.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def download(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Project-Zeta-Terminus-Next research acquisition"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        require(response.status == 200, f"HTTP {response.status}: {url}")
        return response.read()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def first_monday(year: int, month: int) -> date:
    day = date(year, month, 1)
    while day.weekday() != 0:
        day += timedelta(days=1)
    return day


def early_federal_reserve_holidays(year: int, month: int) -> set[date]:
    """Return closures that can affect the fourth business day.

    Federal Reserve Banks do not substitute the preceding Friday when a
    holiday falls on Saturday. A Sunday holiday is observed Monday.
    """

    closures: set[date] = set()
    if month == 1:
        new_year = date(year, 1, 1)
        if new_year.weekday() < 5:
            closures.add(new_year)
        elif new_year.weekday() == 6:
            closures.add(new_year + timedelta(days=1))
    if month == 7:
        independence = date(year, 7, 4)
        if independence.weekday() < 5:
            closures.add(independence)
        elif independence.weekday() == 6:
            closures.add(independence + timedelta(days=1))
    if month == 9:
        closures.add(first_monday(year, month))
    return closures


def fourth_federal_reserve_business_day(year: int, month: int) -> date:
    closures = early_federal_reserve_holidays(year, month)
    business_days: list[date] = []
    cursor = date(year, month, 1)
    while len(business_days) < 4:
        if cursor.weekday() < 5 and cursor not in closures:
            business_days.append(cursor)
        cursor += timedelta(days=1)
    return business_days[-1]


def parse_initial_releases(vintage_bytes: bytes) -> list[dict[str, Any]]:
    matrix = list(
        csv.reader(io.StringIO(vintage_bytes.decode("utf-8-sig"), newline=""))
    )
    require(len(matrix) == 349, f"unexpected matrix rows: {len(matrix)}")
    require(len(matrix[0]) == 57, f"unexpected matrix columns: {len(matrix[0])}")
    require(matrix[0][0] == "Date", "unexpected first matrix header")
    require(matrix[0][1] == "Jan-22", "unexpected first vintage")
    require(matrix[0][-1] == "Aug-26", "unexpected last vintage")

    releases: list[dict[str, Any]] = []
    for column_index, vintage in enumerate(matrix[0][1:], start=1):
        vintage_month = datetime.strptime(vintage, "%b-%y")
        if vintage_month < datetime(2022, 8, 1):
            continue
        observations: list[tuple[date, float]] = []
        for row in matrix[1:]:
            if not row or not row[0] or column_index >= len(row):
                continue
            try:
                observed = datetime.strptime(row[0], "%d-%b-%Y").date()
                value = float(row[column_index])
            except (ValueError, IndexError):
                continue
            observations.append((observed, value))
        require(observations, f"no observations in vintage {vintage}")
        observation_date, initial_value = observations[-1]
        expected_year = (
            vintage_month.year - 1
            if vintage_month.month == 1
            else vintage_month.year
        )
        expected_month = 12 if vintage_month.month == 1 else vintage_month.month - 1
        require(
            observation_date.year == expected_year
            and observation_date.month == expected_month,
            f"unexpected latest observation for {vintage}: {observation_date}",
        )
        release_date = fourth_federal_reserve_business_day(
            vintage_month.year, vintage_month.month
        )
        releases.append(
            {
                "vintage": vintage,
                "release_date": release_date.isoformat(),
                "release_time_et": "10:00",
                "observation_date": observation_date.isoformat(),
                "initial_value": initial_value,
                "state": "ABOVE_NORMAL"
                if initial_value > 0.0
                else "AT_OR_BELOW_NORMAL",
                "release_rule_source": PRODUCT_URL,
            }
        )
    require(len(releases) == 49, f"unexpected retained releases: {len(releases)}")
    require(
        releases[0]["vintage"] == "Aug-22"
        and releases[0]["initial_value"] == 1.75,
        "unexpected first retained release",
    )
    require(
        releases[-1]["vintage"] == "Aug-26"
        and releases[-1]["initial_value"] == 0.79,
        "unexpected last retained release",
    )
    return releases


def crosscheck_recent_calendar(releases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for release in releases:
        vintage_month = datetime.strptime(release["vintage"], "%b-%y")
        if vintage_month < datetime(2025, 9, 1):
            continue
        slug = vintage_month.strftime("%b").lower() + vintage_month.strftime("%y")
        url = f"https://www.newyorkfed.org/research/calendars/i-{slug}.html"
        payload = download(url)
        soup = BeautifulSoup(payload, "html.parser")
        matches = [
            anchor
            for anchor in soup.find_all("a")
            if "Global Supply Chain Pressure Index (GSCPI)"
            in anchor.get_text(" ", strip=True)
            and anchor.find_parent("td") is not None
        ]
        require(len(matches) == 1, f"calendar match count {len(matches)}: {url}")
        cell_text = matches[0].find_parent("td").get_text(" ", strip=True)
        calendar_date = date(
            vintage_month.year, vintage_month.month, int(cell_text[:2])
        )
        require(
            calendar_date.isoformat() == release["release_date"],
            f"calendar mismatch {release['vintage']}: {calendar_date}",
        )
        checks.append(
            {
                "vintage": release["vintage"],
                "calendar_url": url,
                "calendar_sha256": sha256_bytes(payload),
                "calendar_release_date": calendar_date.isoformat(),
                "rule_date_match": True,
            }
        )
    require(len(checks) == 12, f"unexpected recent calendar checks: {len(checks)}")
    return checks


def write_schedule(releases: list[dict[str, Any]]) -> None:
    SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SCHEDULE_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(releases[0]))
        writer.writeheader()
        writer.writerows(releases)


def main() -> None:
    vintage_bytes = download(VINTAGE_URL)
    config_bytes = download(CONFIG_URL)
    config = json.loads(config_bytes.decode("utf-8-sig"))
    summary = config["interactive"]
    notes = summary["notes"]
    require(summary["summaryTitle"] == "Estimates for July 2026", "unexpected summary")
    require("revised" in summary["summaryList"][0].lower(), "revision absent")
    require("up to a year back" in notes, "revision horizon absent")
    require("fourth business day" in json.dumps(config).lower(), "release rule absent")

    releases = parse_initial_releases(vintage_bytes)
    recent_checks = crosscheck_recent_calendar(releases)
    write_bytes(VINTAGE_PATH, vintage_bytes)
    write_bytes(CONFIG_PATH, config_bytes)
    write_schedule(releases)

    receipt = {
        "schema": "zeta-next-gscpi-source-acquisition-receipt-v1",
        "created_at_local": "2026-08-30",
        "status": "SOURCE_FROZEN_BEFORE_STATE_CONDITIONED_ECONOMIC_AGGREGATION",
        "publisher": "Federal Reserve Bank of New York",
        "product": "Global Supply Chain Pressure Index",
        "product_url": PRODUCT_URL,
        "press_release_url": PRESS_RELEASE_URL,
        "publication_rule": "At or shortly after 10:00 ET on the fourth business day of each month.",
        "causal_use": "Use the initial value in each preserved vintage column only after its release date; exclude every birth on the release server date.",
        "revision_warning": notes,
        "sources": [
            {
                "path": VINTAGE_PATH.relative_to(REPO).as_posix(),
                "url": VINTAGE_URL,
                "bytes": VINTAGE_PATH.stat().st_size,
                "sha256": sha256_file(VINTAGE_PATH),
                "rows": 349,
                "columns": 57,
            },
            {
                "path": CONFIG_PATH.relative_to(REPO).as_posix(),
                "url": CONFIG_URL,
                "bytes": CONFIG_PATH.stat().st_size,
                "sha256": sha256_file(CONFIG_PATH),
            },
            {
                "path": SCHEDULE_PATH.relative_to(REPO).as_posix(),
                "bytes": SCHEDULE_PATH.stat().st_size,
                "sha256": sha256_file(SCHEDULE_PATH),
                "initial_release_rows": len(releases),
                "first_vintage": releases[0]["vintage"],
                "last_vintage": releases[-1]["vintage"],
            },
        ],
        "recent_official_calendar_crosschecks": recent_checks,
        "network_calls": 14,
        "lifecycle_or_economic_outcomes_accessed": False,
        "broker_or_account_state_queried": False,
        "live_surface": "UNTOUCHED",
    }
    write_json(RECEIPT_PATH, receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
