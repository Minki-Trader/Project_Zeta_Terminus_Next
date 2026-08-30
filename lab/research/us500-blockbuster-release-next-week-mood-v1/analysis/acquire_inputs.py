from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import date, datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup


REPO_ROOT = Path(__file__).resolve().parents[4]
FAMILY = "us500-blockbuster-release-next-week-mood-v1"
INPUT_ROOT = REPO_ROOT / "lab" / "artifacts" / "raw" / FAMILY / "input"
SOURCE_ROOT = INPUT_ROOT / "source"
MARKET_ROOT = INPUT_ROOT / "market"
ARTICLE_URL = "https://academic.oup.com/rof/article/29/2/603/7990917"
ARTICLE_DOWNLOAD_URL = "https://oup.silverchair-cdn.com/article-minimal/7990917"
YEAR_URL = (
    "https://www.boxofficemojo.com/year/{year}/"
    "?grossesOption=totalGrosses&releaseScale=wide&sort=openingNumTheaters"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
        "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}
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
    payload = path.read_bytes()
    return {
        "name": path.relative_to(INPUT_ROOT).as_posix(),
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
    }


def write_once(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise RuntimeError(f"refusing to replace frozen acquisition byte: {path}")
        return
    path.write_bytes(payload)


def period_name(target_monday: date) -> str:
    for name, start, end in PERIODS:
        if start <= target_monday < end:
            return name
    return "OUTSIDE_TARGET"


def parse_year(year: int, payload: bytes) -> tuple[list[dict[str, Any]], int]:
    soup = BeautifulSoup(payload, "html.parser")
    table_rows = soup.select("table tr")
    if not table_rows:
        raise RuntimeError(f"Box Office Mojo {year} response has no table")
    headers = [cell.get_text(" ", strip=True) for cell in table_rows[0].select("th,td")]
    required = {"Release", "Open Th", "Open"}
    if not required.issubset(headers):
        raise RuntimeError(f"Box Office Mojo {year} schema mismatch: {headers}")

    normalized: list[dict[str, Any]] = []
    parsed_rows = 0
    for table_row in table_rows[1:]:
        values = [cell.get_text(" ", strip=True) for cell in table_row.select("th,td")]
        if len(values) != len(headers):
            continue
        parsed_rows += 1
        row = dict(zip(headers, values))
        raw_theaters = row["Open Th"].replace(",", "")
        if not raw_theaters.isdigit():
            continue
        opening_theaters = int(raw_theaters)
        if opening_theaters <= 4000:
            continue
        release_date = datetime.strptime(f"{year} {row['Open']}", "%Y %b %d").date()
        release_monday = release_date - timedelta(days=release_date.weekday())
        target_monday = release_monday + timedelta(days=7)
        normalized.append(
            {
                "year": year,
                "release": row["Release"],
                "release_date": release_date.isoformat(),
                "opening_theaters": opening_theaters,
                "release_week_monday": release_monday.isoformat(),
                "target_week_monday": target_monday.isoformat(),
                "target_period": period_name(target_monday),
                "source_file": f"box_office_mojo_{year}.html",
            }
        )
    if parsed_rows < 50:
        raise RuntimeError(f"Box Office Mojo {year} unexpectedly sparse: {parsed_rows}")
    return normalized, parsed_rows


def normalized_csv(rows: list[dict[str, Any]]) -> bytes:
    fields = [
        "year",
        "release",
        "release_date",
        "opening_theaters",
        "release_week_monday",
        "target_week_monday",
        "target_period",
        "source_file",
    ]
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
    events: list[dict[str, Any]] = []
    yearly_rows: dict[str, int] = {}
    for year in range(2022, 2027):
        url = YEAR_URL.format(year=year)
        response = session.get(url, timeout=45)
        response.raise_for_status()
        payload = response.content
        parsed, row_count = parse_year(year, payload)
        events.extend(parsed)
        yearly_rows[str(year)] = row_count
        filename = f"box_office_mojo_{year}.html"
        fetched[filename] = payload
        source_receipts.append(
            {
                "name": f"source/{filename}",
                "url": url,
                "http_status": response.status_code,
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
                "table_rows": row_count,
            }
        )

    article = session.get(ARTICLE_DOWNLOAD_URL, timeout=45)
    article.raise_for_status()
    article_text = BeautifulSoup(article.content, "html.parser").get_text(" ", strip=True)
    required_article_phrases = (
        "over 4,000 theaters",
        "from Monday to Sunday",
        "subsequent week",
    )
    missing_phrases = [phrase for phrase in required_article_phrases if phrase not in article_text]
    if missing_phrases:
        raise RuntimeError(f"publisher article contract phrases missing: {missing_phrases}")
    fetched["hong_wei_2025_review_of_finance.html"] = article.content
    source_receipts.append(
        {
            "name": "source/hong_wei_2025_review_of_finance.html",
            "url": ARTICLE_URL,
            "download_url": ARTICLE_DOWNLOAD_URL,
            "http_status": article.status_code,
            "bytes": len(article.content),
            "sha256": sha256_bytes(article.content),
        }
    )

    events.sort(key=lambda row: (row["release_date"], row["release"], row["opening_theaters"]))
    event_payload = normalized_csv(events)
    fetched["blockbuster_events_over_4000.csv"] = event_payload
    source_receipts.append(
        {
            "name": "source/blockbuster_events_over_4000.csv",
            "derived_from": [f"source/box_office_mojo_{year}.html" for year in range(2022, 2027)],
            "bytes": len(event_payload),
            "sha256": sha256_bytes(event_payload),
            "rows": len(events),
            "strict_threshold": "opening_theaters > 4000",
        }
    )

    for filename, payload in fetched.items():
        write_once(SOURCE_ROOT / filename, payload)

    source_market = (
        REPO_ROOT
        / "lab"
        / "artifacts"
        / "raw"
        / "us500-earnings-extrapolation-monthly-signal-v1"
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

    period_title_counts: dict[str, int] = {}
    period_week_counts: dict[str, int] = {}
    for name, _, _ in PERIODS:
        in_period = [row for row in events if row["target_period"] == name]
        period_title_counts[name] = len(in_period)
        period_week_counts[name] = len({row["target_week_monday"] for row in in_period})

    input_files = sorted(
        [file_receipt(path) for path in SOURCE_ROOT.iterdir() if path.is_file()]
        + [file_receipt(path) for path in MARKET_ROOT.iterdir() if path.is_file()],
        key=lambda item: item["name"],
    )
    manifest_lines = [f"{item['name']}|{item['bytes']}|{item['sha256']}" for item in input_files]
    manifest_sha256 = sha256_bytes("\n".join(manifest_lines).encode("utf-8"))
    summary = {
        "schema": "zeta-next-us500-blockbuster-release-input-acquisition-v1",
        "family": FAMILY,
        "acquired_at_local_date": date.today().isoformat(),
        "source": {
            "paper": "Hong and Wei (2025), Blockbuster or bust? Silver screen effect and stock returns",
            "doi": "10.1093/rof/rfaf004",
            "receipts": source_receipts,
            "yearly_table_rows": yearly_rows,
        },
        "normalized_events": {
            "all_over_4000_titles": len(events),
            "target_period_title_counts": period_title_counts,
            "target_period_week_counts": period_week_counts,
            "same_week_multiplicity": {
                "2023-06-19": 2,
            },
        },
        "market": {
            "receipts": copied_market,
            "mt5_acquisition_calls": 0,
            "tester_calls": 0,
            "account_position_order_deal_trade_calls": 0,
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
