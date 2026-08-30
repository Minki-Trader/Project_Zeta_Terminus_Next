#!/usr/bin/env python3
"""Run the one frozen Unit 123 standard-expiration-week aggregation.

This is a finite economic research aggregation, not a validator, test harness,
reusable CLI, trading program, promotion checker, or broker/account query.
"""

from __future__ import annotations

import calendar
import csv
import hashlib
import io
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[4]
FAMILY = REPO / "lab/research/standard-options-expiration-week-state-engineering-correction-v1"
EVIDENCE = FAMILY / "evidence"
DECLARATION_PATH = EVIDENCE / "STANDARD_OPTIONS_EXPIRATION_WEEK_STATE_ENGINEERING_CORRECTION_DECLARATION_V1.json"
RECEIPT_PATH = EVIDENCE / "STANDARD_OPTIONS_EXPIRATION_WEEK_STATE_ENGINEERING_CORRECTION_INPUT_RECEIPT_V1.json"
SCHEDULE_PATH = REPO / "lab/research/standard-options-expiration-week-state-v1/evidence/standard_options_expiration_weeks_2022_08_2026_08.csv"
DAILY_PATH = EVIDENCE / "STANDARD_OPTIONS_EXPIRATION_WEEK_DAILY_SUPPLY_ROWS_V1.csv"
LIFECYCLE_PATH = EVIDENCE / "STANDARD_OPTIONS_EXPIRATION_WEEK_LIFECYCLE_ROWS_V1.csv"
RESULT_PATH = EVIDENCE / "STANDARD_OPTIONS_EXPIRATION_WEEK_STATE_ENGINEERING_CORRECTION_RESULT_V1.json"
CLOSURE_PATH = EVIDENCE / "STANDARD_OPTIONS_EXPIRATION_WEEK_STATE_ENGINEERING_CORRECTION_CLOSURE_V1.json"

DECLARATION_SHA256 = "94720EF140624B078D14DC79EC6844AE6A031E1A899F761C4F38AED64B18F319"
RECEIPT_SHA256 = "A90FA7D93BD4FC3AE1E937DFEED7531D68999CF8A57E765BD4E65F67CA8E2329"

TREATMENT = "STANDARD_EXPIRATION_WEEK"
OTHER = "OTHER_WEEK"
STATES = (TREATMENT, OTHER)
PERIODS = ("P1_2022H2_2023", "P2_2024", "P3_2025", "P4_2026_YTD")
BOOKS = ("US30_BOOK", "US100_BOOK")
COMPONENTS = ("RC16", "RC4", "Cross", "Pressure", "Return", "Passive")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")

EVENT_COLUMNS = [
    "utc",
    "server_time",
    "event",
    "execution_version",
    "schema_version",
    "release_id",
    "project_id",
    "portfolio_id",
    "component_id",
    "value_a",
    "value_b",
    "detail",
    "stressed_balance",
    "project_stage_balance",
    "account_equity",
    "account_margin",
    "state_sequence",
]

PLANNED_RISK = re.compile(r"(?:^|\s)planned_risk=([-+0-9.eE]+)(?:\s|$)")
REASON = re.compile(r"(?:^|\s)reason=([A-Z_]+)(?:\s|$)")


@dataclass(frozen=True)
class ExpirationWeek:
    year_month: str
    third_friday: date
    start_monday: date
    end_friday: date


@dataclass(frozen=True)
class DailySupply:
    period: str
    server_date: date
    weekday: str
    state: str
    signal_count: int
    birth_count: int
    sub_three_signal: int
    centered_signal_count: float | None = None
    centered_birth_count: float | None = None
    centered_sub_three_signal: float | None = None


@dataclass(frozen=True)
class Lifecycle:
    record_id: str
    source_path: str
    source_birth_row: int
    source_final_row: int
    birth_server: datetime
    final_server: datetime
    period: str
    component: str
    book: str
    weekday: str
    state: str
    planned_risk: float
    actual_net: float
    stressed_net: float
    stressed_r: float
    stop: int
    centered_stressed_r: float | None = None
    centered_stop: float | None = None


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False))
        handle.write("\n")


def finite_float(text: str, context: str) -> float:
    value = float(text)
    require(math.isfinite(value), f"nonfinite value: {context}")
    return value


def detail_value(pattern: re.Pattern[str], detail: str, context: str) -> str:
    match = pattern.search(detail)
    require(match is not None, f"missing detail field: {context}")
    return match.group(1)


def parse_server(text: str) -> datetime:
    return datetime.strptime(text, "%Y.%m.%d %H:%M:%S")


def verify_pin(pin: dict[str, Any]) -> dict[str, Any]:
    path = REPO / pin["path"]
    require(path.is_file(), f"missing pinned input: {pin['path']}")
    actual_bytes = path.stat().st_size
    actual_sha = sha256_file(path)
    require(actual_bytes == pin["bytes"], f"byte mismatch: {pin['path']}")
    require(actual_sha == pin["sha256"], f"hash mismatch: {pin['path']}")
    return {"path": pin["path"], "bytes": actual_bytes, "sha256": actual_sha}


def verify_preoutcome_boundary(declaration: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    require(sha256_file(DECLARATION_PATH) == DECLARATION_SHA256, "declaration hash mismatch")
    require(sha256_file(RECEIPT_PATH) == RECEIPT_SHA256, "receipt hash mismatch")
    require(declaration["outcomes_consumed"] is False, "declaration already consumed")
    require(receipt["verification"]["cp2_rows_read"] is False, "receipt is not outcome-free")
    require(receipt["verification"]["cp2_value_b_read"] is False, "value_b already read")
    require(receipt["verification"]["planned_risk_read"] is False, "planned risk already read")
    require(receipt["verification"]["stop_reason_read"] is False, "stop reason already read")
    require(receipt["verification"]["conditional_outcomes_calculated"] is False, "outcomes already calculated")

    declared_inputs = (
        declaration["immutable_inputs"]["cp2_event_files"]
        + declaration["immutable_inputs"]["closed_boundaries"]
        + declaration["immutable_inputs"]["official_sources"]
        + [declaration["immutable_inputs"]["schedule"]]
    )
    require(len(declared_inputs) == 17, "unexpected declared input count")
    declared_by_path = {item["path"]: item for item in declared_inputs}
    receipt_by_path = {item["path"]: item for item in receipt["verified_inputs"]}
    require(len(receipt_by_path) == 17, "unexpected receipt input count")
    require(set(declared_by_path) == set(receipt_by_path), "declaration/receipt path mismatch")
    for path, declared in declared_by_path.items():
        received = receipt_by_path[path]
        require(declared["bytes"] == received["bytes"], f"receipt byte declaration mismatch: {path}")
        require(declared["sha256"] == received["sha256"], f"receipt hash declaration mismatch: {path}")

    checked_inputs = [verify_pin(item) for item in declared_inputs]
    checked_parent = [verify_pin(item) for item in declaration["parent_record"]["files"]]
    receipt_declaration = receipt["declaration"]
    require(receipt_declaration["bytes"] == DECLARATION_PATH.stat().st_size, "receipt declaration bytes mismatch")
    require(receipt_declaration["sha256"] == DECLARATION_SHA256, "receipt declaration hash mismatch")
    require(declaration["parent_record"]["valid_parent_economic_verdicts"] == 0, "parent economic verdict exists")
    require(declaration["parent_record"]["economic_outcomes_opened"] is False, "parent outcomes were opened")
    return {
        "passed": True,
        "input_count": len(checked_inputs),
        "parent_record_count": len(checked_parent),
        "inputs": checked_inputs,
        "parent_record": checked_parent,
    }


def third_friday(year: int, month: int) -> date:
    fridays = [week[calendar.FRIDAY] for week in calendar.monthcalendar(year, month) if week[calendar.FRIDAY] != 0]
    require(len(fridays) >= 3, f"no third Friday: {year}-{month:02d}")
    return date(year, month, fridays[2])


def next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def load_schedule() -> tuple[list[ExpirationWeek], set[date]]:
    weeks: list[ExpirationWeek] = []
    treatment_dates: set[date] = set()
    with SCHEDULE_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        require(
            reader.fieldnames == ["year_month", "calendar_third_friday", "treatment_start_monday", "treatment_end_friday"],
            f"unexpected schedule columns: {reader.fieldnames}",
        )
        expected_year, expected_month = 2022, 8
        for row in reader:
            expected_label = f"{expected_year:04d}-{expected_month:02d}"
            require(row["year_month"] == expected_label, f"nonsequential schedule: {row['year_month']}")
            observed_third = date.fromisoformat(row["calendar_third_friday"])
            observed_start = date.fromisoformat(row["treatment_start_monday"])
            observed_end = date.fromisoformat(row["treatment_end_friday"])
            calculated_third = third_friday(expected_year, expected_month)
            require(observed_third == calculated_third, f"third Friday mismatch: {expected_label}")
            require(observed_start == observed_third - timedelta(days=4), f"Monday mismatch: {expected_label}")
            require(observed_end == observed_third, f"Friday mismatch: {expected_label}")
            require(observed_start.weekday() == calendar.MONDAY, f"non-Monday start: {expected_label}")
            require(observed_end.weekday() == calendar.FRIDAY, f"non-Friday end: {expected_label}")
            week = ExpirationWeek(expected_label, observed_third, observed_start, observed_end)
            weeks.append(week)
            treatment_dates.update(observed_start + timedelta(days=offset) for offset in range(5))
            expected_year, expected_month = next_month(expected_year, expected_month)
    require(len(weeks) == 49, f"unexpected schedule rows: {len(weeks)}")
    require(weeks[0].year_month == "2022-08", "unexpected first schedule month")
    require(weeks[-1].year_month == "2026-08", "unexpected last schedule month")
    require(len(treatment_dates) == 245, "overlapping or missing treatment calendar dates")
    return weeks, treatment_dates


def reconstruct(
    declaration: dict[str, Any], treatment_dates: set[date]
) -> tuple[list[DailySupply], list[Lifecycle], Counter[str], int]:
    mappings = {
        component_id: (item["name"], item["book"], item["birth_event"])
        for component_id, item in declaration["strategy_identity"].items()
    }
    normal_days: set[tuple[str, date]] = set()
    signal_counts: Counter[tuple[str, date]] = Counter()
    birth_counts: Counter[tuple[str, date]] = Counter()
    event_counts: Counter[str] = Counter()
    full_rows_seen: set[tuple[str, ...]] = set()
    lifecycles: list[Lifecycle] = []
    record_number = 0

    for source in declaration["immutable_inputs"]["cp2_event_files"]:
        period = source["period"]
        require(period in PERIODS, f"unknown period: {period}")
        path = REPO / source["path"]
        open_by_component: dict[str, tuple[int, dict[str, str]]] = {}
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            require(reader.fieldnames == EVENT_COLUMNS, f"unexpected event columns: {source['path']}")
            for source_row, row in enumerate(reader, start=2):
                full_row = tuple(row[field] for field in EVENT_COLUMNS)
                require(full_row not in full_rows_seen, f"duplicate full row: {source['path']}:{source_row}")
                full_rows_seen.add(full_row)
                event = row["event"]
                event_counts[event] += 1
                server = parse_server(row["server_time"])
                day_key = (period, server.date())
                component_id = row["component_id"]

                if event == "SIZE_DAY":
                    require(day_key not in normal_days, f"duplicate SIZE_DAY: {period}:{server.date()}")
                    normal_days.add(day_key)
                elif event == "SIGNAL_DECIDED":
                    require(component_id in mappings, f"unknown signal component: {component_id}")
                    signal_counts[day_key] += 1

                if component_id not in mappings:
                    continue
                component, book, birth_event = mappings[component_id]
                if event == birth_event:
                    require(component_id not in open_by_component, f"overlapping birth: {source['path']}:{source_row}:{component}")
                    open_by_component[component_id] = (source_row, row)
                    birth_counts[day_key] += 1
                elif event in {"CLOSE", "EXTERNAL_CLOSE"}:
                    require(component_id in open_by_component, f"final without birth: {source['path']}:{source_row}:{component}")
                    birth_row_number, birth = open_by_component.pop(component_id)
                    birth_server = parse_server(birth["server_time"])
                    final_server = server
                    require(final_server >= birth_server, "final precedes birth")
                    planned_risk = finite_float(
                        detail_value(PLANNED_RISK, row["detail"], f"planned_risk:{source['path']}:{source_row}"),
                        f"planned_risk:{source['path']}:{source_row}",
                    )
                    require(planned_risk > 0.0, "nonpositive planned risk")
                    reason = detail_value(REASON, row["detail"], f"reason:{source['path']}:{source_row}")
                    require(reason in {"DEAL_REASON_SL", "DEAL_REASON_EXPERT"}, f"unexpected final reason: {reason}")
                    actual_net = finite_float(row["value_a"], f"actual:{source['path']}:{source_row}")
                    stressed_net = finite_float(row["value_b"], f"stressed:{source['path']}:{source_row}")
                    record_number += 1
                    birth_day = birth_server.date()
                    lifecycles.append(
                        Lifecycle(
                            record_id=f"L{record_number:04d}",
                            source_path=source["path"],
                            source_birth_row=birth_row_number,
                            source_final_row=source_row,
                            birth_server=birth_server,
                            final_server=final_server,
                            period=period,
                            component=component,
                            book=book,
                            weekday=birth_day.strftime("%A"),
                            state=TREATMENT if birth_day in treatment_dates else OTHER,
                            planned_risk=planned_risk,
                            actual_net=actual_net,
                            stressed_net=stressed_net,
                            stressed_r=stressed_net / planned_risk,
                            stop=int(event == "EXTERNAL_CLOSE"),
                        )
                    )
        require(not open_by_component, f"unclosed births at end of {source['path']}: {sorted(open_by_component)}")

    require(len(full_rows_seen) == 16477, f"unexpected distinct event rows: {len(full_rows_seen)}")
    require(event_counts["SIZE_DAY"] == 1051, f"unexpected SIZE_DAY count: {event_counts['SIZE_DAY']}")
    require(len(normal_days) == 1051, f"unexpected unique normal days: {len(normal_days)}")
    require(event_counts["SIGNAL_DECIDED"] == 2429, f"unexpected signal count: {event_counts['SIGNAL_DECIDED']}")
    require(sum(signal_counts.values()) == 2429, "daily signal total mismatch")
    require(event_counts["OPEN"] == 1639, "unexpected OPEN count")
    require(event_counts["PASSIVE_FILL"] == 594, "unexpected PASSIVE_FILL count")
    require(sum(birth_counts.values()) == 2233, "daily birth total mismatch")
    require(len(lifecycles) == 2233, f"unexpected lifecycles: {len(lifecycles)}")
    require(event_counts["CLOSE"] == 2027, "unexpected CLOSE count")
    require(event_counts["EXTERNAL_CLOSE"] == 206, "unexpected EXTERNAL_CLOSE count")
    require(sum(row.stop for row in lifecycles) == 206, "unexpected stop count")
    require(math.isclose(sum(row.actual_net for row in lifecycles), 444.19, rel_tol=0.0, abs_tol=1e-9), "actual net anchor mismatch")
    require(math.isclose(sum(row.stressed_net for row in lifecycles), 407.0477, rel_tol=0.0, abs_tol=1e-9), "stressed net anchor mismatch")
    require(set(signal_counts).issubset(normal_days), "signal exists outside normal days")
    require(set(birth_counts).issubset(normal_days), "birth exists outside normal days")

    daily = [
        DailySupply(
            period=period,
            server_date=server_day,
            weekday=server_day.strftime("%A"),
            state=TREATMENT if server_day in treatment_dates else OTHER,
            signal_count=signal_counts[(period, server_day)],
            birth_count=birth_counts[(period, server_day)],
            sub_three_signal=int(signal_counts[(period, server_day)] < 3),
        )
        for period, server_day in sorted(normal_days, key=lambda item: (PERIODS.index(item[0]), item[1]))
    ]
    require(all(row.weekday in WEEKDAYS for row in daily), "weekend normal day")
    require(all(row.weekday in WEEKDAYS for row in lifecycles), "weekend lifecycle birth")
    return daily, lifecycles, event_counts, len(full_rows_seen)


def center_daily(rows: list[DailySupply]) -> list[DailySupply]:
    cells: dict[tuple[str, str], list[DailySupply]] = defaultdict(list)
    for row in rows:
        cells[(row.period, row.weekday)].append(row)
    require(len(cells) == 20, f"unexpected daily centering cells: {len(cells)}")
    centered: list[DailySupply] = []
    for row in rows:
        cell = cells[(row.period, row.weekday)]
        centered.append(
            replace(
                row,
                centered_signal_count=row.signal_count - statistics.fmean(item.signal_count for item in cell),
                centered_birth_count=row.birth_count - statistics.fmean(item.birth_count for item in cell),
                centered_sub_three_signal=row.sub_three_signal - statistics.fmean(item.sub_three_signal for item in cell),
            )
        )
    return centered


def center_lifecycles(rows: list[Lifecycle]) -> list[Lifecycle]:
    cells: dict[tuple[str, str], list[Lifecycle]] = defaultdict(list)
    for row in rows:
        cells[(row.component, row.period)].append(row)
    require(len(cells) == 24, f"unexpected lifecycle centering cells: {len(cells)}")
    centered: list[Lifecycle] = []
    for row in rows:
        cell = cells[(row.component, row.period)]
        centered.append(
            replace(
                row,
                centered_stressed_r=row.stressed_r - statistics.fmean(item.stressed_r for item in cell),
                centered_stop=row.stop - statistics.fmean(item.stop for item in cell),
            )
        )
    return centered


def daily_state_metrics(rows: list[DailySupply], state: str) -> dict[str, Any]:
    selected = [row for row in rows if row.state == state]
    require(selected, f"empty daily state: {state}")
    require(all(row.centered_signal_count is not None for row in selected), f"uncentered daily state: {state}")
    return {
        "days": len(selected),
        "signals": sum(row.signal_count for row in selected),
        "births": sum(row.birth_count for row in selected),
        "sub_three_signal_days": sum(row.sub_three_signal for row in selected),
        "signal_rate_per_day": statistics.fmean(row.signal_count for row in selected),
        "birth_rate_per_day": statistics.fmean(row.birth_count for row in selected),
        "sub_three_signal_day_rate": statistics.fmean(row.sub_three_signal for row in selected),
        "mean_centered_signal_count": statistics.fmean(row.centered_signal_count for row in selected),
        "mean_centered_birth_count": statistics.fmean(row.centered_birth_count for row in selected),
        "mean_centered_sub_three_signal": statistics.fmean(row.centered_sub_three_signal for row in selected),
    }


def daily_contrast(rows: list[DailySupply]) -> dict[str, Any]:
    treatment = daily_state_metrics(rows, TREATMENT)
    other = daily_state_metrics(rows, OTHER)
    return {
        TREATMENT: treatment,
        OTHER: other,
        "treatment_minus_other": {
            "raw_signal_rate_per_day": treatment["signal_rate_per_day"] - other["signal_rate_per_day"],
            "raw_birth_rate_per_day": treatment["birth_rate_per_day"] - other["birth_rate_per_day"],
            "raw_sub_three_signal_day_rate": treatment["sub_three_signal_day_rate"] - other["sub_three_signal_day_rate"],
            "centered_signal_count": treatment["mean_centered_signal_count"] - other["mean_centered_signal_count"],
            "centered_birth_count": treatment["mean_centered_birth_count"] - other["mean_centered_birth_count"],
            "centered_sub_three_signal": treatment["mean_centered_sub_three_signal"] - other["mean_centered_sub_three_signal"],
        },
    }


def lifecycle_state_metrics(rows: list[Lifecycle], state: str) -> dict[str, Any]:
    selected = [row for row in rows if row.state == state]
    require(selected, f"empty lifecycle state: {state}")
    require(all(row.centered_stressed_r is not None and row.centered_stop is not None for row in selected), f"uncentered lifecycle state: {state}")
    return {
        "n": len(selected),
        "actual_net_usd": sum(row.actual_net for row in selected),
        "stressed_net_usd": sum(row.stressed_net for row in selected),
        "planned_risk_usd": sum(row.planned_risk for row in selected),
        "mean_stressed_r": statistics.fmean(row.stressed_r for row in selected),
        "stop_rate": statistics.fmean(row.stop for row in selected),
        "mean_centered_stressed_r": statistics.fmean(row.centered_stressed_r for row in selected),
        "mean_centered_stop": statistics.fmean(row.centered_stop for row in selected),
    }


def lifecycle_contrast(rows: list[Lifecycle]) -> dict[str, Any]:
    treatment = lifecycle_state_metrics(rows, TREATMENT)
    other = lifecycle_state_metrics(rows, OTHER)
    return {
        TREATMENT: treatment,
        OTHER: other,
        "treatment_minus_other": {
            "raw_mean_stressed_r": treatment["mean_stressed_r"] - other["mean_stressed_r"],
            "raw_stop_rate": treatment["stop_rate"] - other["stop_rate"],
            "centered_stressed_r": treatment["mean_centered_stressed_r"] - other["mean_centered_stressed_r"],
            "centered_stop_rate": treatment["mean_centered_stop"] - other["mean_centered_stop"],
        },
    }


def direction(cell: dict[str, Any]) -> str:
    effect = cell["treatment_minus_other"]
    if effect["centered_stressed_r"] > 0.0 and effect["centered_stop_rate"] < 0.0:
        return "FAVORABLE_STANDARD_EXPIRATION_WEEK"
    if effect["centered_stressed_r"] < 0.0 and effect["centered_stop_rate"] > 0.0:
        return "ADVERSE_STANDARD_EXPIRATION_WEEK"
    return "NONCONCORDANT"


def lifecycle_breakout(rows: list[Lifecycle], field: str, values: Iterable[str]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for value in values:
        selected = [row for row in rows if getattr(row, field) == value]
        states = Counter(row.state for row in selected)
        require(states[TREATMENT] > 0 and states[OTHER] > 0, f"empty breakout state: {field}:{value}")
        cell = lifecycle_contrast(selected)
        cell["direction"] = direction(cell)
        output[value] = cell
    return output


def daily_period_breakout(rows: list[DailySupply]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for period in PERIODS:
        selected = [row for row in rows if row.period == period]
        states = Counter(row.state for row in selected)
        require(states[TREATMENT] > 0 and states[OTHER] > 0, f"empty daily period state: {period}")
        output[period] = daily_contrast(selected)
    return output


def contribution_cap(rows: list[Lifecycle], field: str, values: Iterable[str]) -> dict[str, Any]:
    treatment_total = sum(row.state == TREATMENT for row in rows)
    other_total = sum(row.state == OTHER for row in rows)
    contributions: dict[str, float] = {}
    for value in values:
        selected = [row for row in rows if getattr(row, field) == value]
        treatment_part = sum(row.centered_stressed_r for row in selected if row.state == TREATMENT) / treatment_total
        other_part = sum(row.centered_stressed_r for row in selected if row.state == OTHER) / other_total
        contributions[value] = treatment_part - other_part
    denominator = sum(abs(value) for value in contributions.values())
    shares = {key: (abs(value) / denominator if denominator > 0.0 else 0.0) for key, value in contributions.items()}
    return {
        "signed_contributions": contributions,
        "absolute_shares": shares,
        "maximum_absolute_share": max(shares.values()),
        "sum_matches_pooled": math.isclose(
            sum(contributions.values()),
            lifecycle_contrast(rows)["treatment_minus_other"]["centered_stressed_r"],
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
    }


def write_csv_text(path: Path, text_value: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text_value)


def daily_csv_text(rows: list[DailySupply]) -> str:
    fields = [
        "period", "server_date", "weekday", "state", "signal_count", "birth_count",
        "sub_three_signal", "centered_signal_count", "centered_birth_count", "centered_sub_three_signal",
    ]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "period": row.period,
                "server_date": row.server_date.isoformat(),
                "weekday": row.weekday,
                "state": row.state,
                "signal_count": row.signal_count,
                "birth_count": row.birth_count,
                "sub_three_signal": row.sub_three_signal,
                "centered_signal_count": row.centered_signal_count,
                "centered_birth_count": row.centered_birth_count,
                "centered_sub_three_signal": row.centered_sub_three_signal,
            }
        )
    return buffer.getvalue()


def lifecycle_csv_text(rows: list[Lifecycle]) -> str:
    fields = [
        "record_id", "period", "component", "book", "birth_server", "final_server", "weekday", "state",
        "planned_risk_usd", "actual_net_usd", "stressed_net_usd", "stressed_r", "stop",
        "centered_stressed_r", "centered_stop", "source_path", "source_birth_row", "source_final_row",
    ]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "record_id": row.record_id,
                "period": row.period,
                "component": row.component,
                "book": row.book,
                "birth_server": row.birth_server.isoformat(),
                "final_server": row.final_server.isoformat(),
                "weekday": row.weekday,
                "state": row.state,
                "planned_risk_usd": row.planned_risk,
                "actual_net_usd": row.actual_net,
                "stressed_net_usd": row.stressed_net,
                "stressed_r": row.stressed_r,
                "stop": row.stop,
                "centered_stressed_r": row.centered_stressed_r,
                "centered_stop": row.centered_stop,
                "source_path": row.source_path,
                "source_birth_row": row.source_birth_row,
                "source_final_row": row.source_final_row,
            }
        )
    return buffer.getvalue()


def main() -> None:
    require(not RESULT_PATH.exists(), "frozen result already exists")
    require(not DAILY_PATH.exists(), "frozen daily rows already exist")
    require(not LIFECYCLE_PATH.exists(), "frozen lifecycle rows already exist")
    require(not CLOSURE_PATH.exists(), "frozen closure already exists")

    declaration = load_json(DECLARATION_PATH)
    receipt = load_json(RECEIPT_PATH)
    pins = verify_preoutcome_boundary(declaration, receipt)
    weeks, treatment_dates = load_schedule()
    daily, lifecycles, event_counts, event_rows = reconstruct(declaration, treatment_dates)
    daily = center_daily(daily)
    lifecycles = center_lifecycles(lifecycles)

    daily_states = Counter(row.state for row in daily)
    daily_signals = Counter()
    daily_births = Counter()
    for row in daily:
        daily_signals[row.state] += row.signal_count
        daily_births[row.state] += row.birth_count
    require(daily_states == Counter({OTHER: 808, TREATMENT: 243}), f"unexpected daily states: {daily_states}")
    require(daily_signals == Counter({OTHER: 1849, TREATMENT: 580}), f"unexpected state signals: {daily_signals}")
    require(daily_births == Counter({OTHER: 1708, TREATMENT: 525}), f"unexpected state births: {daily_births}")

    expected_treatment_period = {
        "P1_2022H2_2023": (85, 193, 175),
        "P2_2024": (60, 143, 133),
        "P3_2025": (59, 145, 130),
        "P4_2026_YTD": (39, 99, 87),
    }
    actual_treatment_period: dict[str, tuple[int, int, int]] = {}
    for period in PERIODS:
        selected = [row for row in daily if row.period == period and row.state == TREATMENT]
        actual_treatment_period[period] = (
            len(selected),
            sum(row.signal_count for row in selected),
            sum(row.birth_count for row in selected),
        )
    require(actual_treatment_period == expected_treatment_period, f"unexpected treatment period counts: {actual_treatment_period}")

    lifecycle_states = Counter(row.state for row in lifecycles)
    require(lifecycle_states == Counter({OTHER: 1708, TREATMENT: 525}), f"unexpected lifecycle states: {lifecycle_states}")
    treatment_books = Counter(row.book for row in lifecycles if row.state == TREATMENT)
    require(treatment_books == Counter({"US100_BOOK": 324, "US30_BOOK": 201}), f"unexpected treatment books: {treatment_books}")
    treatment_components = Counter(row.component for row in lifecycles if row.state == TREATMENT)
    require(
        treatment_components == Counter({"Cross": 179, "Passive": 145, "Return": 71, "RC16": 54, "RC4": 46, "Pressure": 30}),
        f"unexpected treatment components: {treatment_components}",
    )
    treatment_weekdays = Counter(row.weekday for row in daily if row.state == TREATMENT)
    require(
        treatment_weekdays == Counter({"Monday": 49, "Tuesday": 49, "Wednesday": 49, "Thursday": 49, "Friday": 47}),
        f"unexpected treatment weekdays: {treatment_weekdays}",
    )

    component_period_density: dict[str, dict[str, int]] = {}
    for component in COMPONENTS:
        for period in PERIODS:
            selected = [row for row in lifecycles if row.component == component and row.period == period]
            counts = Counter(row.state for row in selected)
            require(counts[TREATMENT] >= 3, f"thin treatment component-period: {component}:{period}:{counts[TREATMENT]}")
            require(counts[OTHER] >= 15, f"thin other component-period: {component}:{period}:{counts[OTHER]}")
            component_period_density[f"{component}|{period}"] = {TREATMENT: counts[TREATMENT], OTHER: counts[OTHER]}
    for period in PERIODS:
        for state in STATES:
            require(any(row.period == period and row.state == state for row in daily), f"missing daily state: {period}:{state}")
    for book in BOOKS:
        for state in STATES:
            require(any(row.book == book and row.state == state for row in lifecycles), f"missing book state: {book}:{state}")
    for component in COMPONENTS:
        for state in STATES:
            require(any(row.component == component and row.state == state for row in lifecycles), f"missing component state: {component}:{state}")

    supply_primary = daily_contrast(daily)
    supply_periods = daily_period_breakout(daily)
    lifecycle_primary = lifecycle_contrast(lifecycles)
    books = lifecycle_breakout(lifecycles, "book", BOOKS)
    periods = lifecycle_breakout(lifecycles, "period", PERIODS)
    components = lifecycle_breakout(lifecycles, "component", COMPONENTS)
    weekdays = lifecycle_breakout(lifecycles, "weekday", WEEKDAYS)

    book_directions = Counter(cell["direction"] for cell in books.values())
    period_directions = Counter(cell["direction"] for cell in periods.values())
    component_directions = Counter(cell["direction"] for cell in components.values())
    weekday_directions = Counter(cell["direction"] for cell in weekdays.values())

    period_contribution = contribution_cap(lifecycles, "period", PERIODS)
    component_contribution = contribution_cap(lifecycles, "component", COMPONENTS)
    weekday_contribution = contribution_cap(lifecycles, "weekday", WEEKDAYS)
    require(period_contribution["sum_matches_pooled"], "period contribution mismatch")
    require(component_contribution["sum_matches_pooled"], "component contribution mismatch")
    require(weekday_contribution["sum_matches_pooled"], "weekday contribution mismatch")

    effect_r = lifecycle_primary["treatment_minus_other"]["centered_stressed_r"]
    effect_stop = lifecycle_primary["treatment_minus_other"]["centered_stop_rate"]
    favorable_name = "FAVORABLE_STANDARD_EXPIRATION_WEEK"
    adverse_name = "ADVERSE_STANDARD_EXPIRATION_WEEK"
    favorable = {
        "centered_stressed_r_at_least_0_10": effect_r >= 0.10,
        "centered_stop_rate_at_most_minus_0_05": effect_stop <= -0.05,
        "both_books": book_directions[favorable_name] == 2,
        "at_least_three_of_four_periods": period_directions[favorable_name] >= 3,
        "at_least_four_of_six_components": component_directions[favorable_name] >= 4,
        "at_least_three_of_five_weekdays": weekday_directions[favorable_name] >= 3,
        "period_contribution_cap_0_60": period_contribution["maximum_absolute_share"] <= 0.60,
        "component_contribution_cap_0_45": component_contribution["maximum_absolute_share"] <= 0.45,
        "weekday_contribution_cap_0_45": weekday_contribution["maximum_absolute_share"] <= 0.45,
    }
    favorable["passed"] = all(favorable.values())
    adverse = {
        "centered_stressed_r_at_most_minus_0_10": effect_r <= -0.10,
        "centered_stop_rate_at_least_0_05": effect_stop >= 0.05,
        "both_books": book_directions[adverse_name] == 2,
        "at_least_three_of_four_periods": period_directions[adverse_name] >= 3,
        "at_least_four_of_six_components": component_directions[adverse_name] >= 4,
        "at_least_three_of_five_weekdays": weekday_directions[adverse_name] >= 3,
        "period_contribution_cap_0_60": period_contribution["maximum_absolute_share"] <= 0.60,
        "component_contribution_cap_0_45": component_contribution["maximum_absolute_share"] <= 0.45,
        "weekday_contribution_cap_0_45": weekday_contribution["maximum_absolute_share"] <= 0.45,
    }
    adverse["passed"] = all(adverse.values())
    strong_null = {
        "absolute_centered_stressed_r_below_0_05": abs(effect_r) < 0.05,
        "absolute_centered_stop_rate_below_0_025": abs(effect_stop) < 0.025,
        "favorable_period_breadth_at_most_2": period_directions[favorable_name] <= 2,
        "adverse_period_breadth_at_most_2": period_directions[adverse_name] <= 2,
        "favorable_component_breadth_at_most_3": component_directions[favorable_name] <= 3,
        "adverse_component_breadth_at_most_3": component_directions[adverse_name] <= 3,
        "favorable_weekday_breadth_at_most_2": weekday_directions[favorable_name] <= 2,
        "adverse_weekday_breadth_at_most_2": weekday_directions[adverse_name] <= 2,
        "not_both_books_favorable": book_directions[favorable_name] < 2,
        "not_both_books_adverse": book_directions[adverse_name] < 2,
    }
    strong_null["passed"] = all(strong_null.values())

    if favorable["passed"]:
        verdict = declaration["fixed_verdict_rules"]["favorable"]
    elif adverse["passed"]:
        verdict = declaration["fixed_verdict_rules"]["adverse"]
    elif strong_null["passed"]:
        verdict = declaration["fixed_verdict_rules"]["no_field"]
    else:
        verdict = declaration["fixed_verdict_rules"]["ambiguous"]

    daily_text = daily_csv_text(daily)
    lifecycle_text = lifecycle_csv_text(lifecycles)
    write_csv_text(DAILY_PATH, daily_text)
    write_csv_text(LIFECYCLE_PATH, lifecycle_text)

    result = {
        "schema": "zeta-next-standard-options-expiration-week-state-engineering-correction-result-v1",
        "created_at_local": "2026-08-30",
        "status": "COMPLETE_VALID_SINGLE_ECONOMIC_AGGREGATION",
        "unit": declaration["unit"],
        "family": declaration["family"],
        "macro_program": declaration["macro_program"],
        "research_height": declaration["research_height"],
        "declaration_sha256": DECLARATION_SHA256,
        "input_receipt_sha256": RECEIPT_SHA256,
        "analysis_script_sha256": sha256_file(Path(__file__)),
        "verdict": verdict,
        "integrity": {
            "passed": True,
            "pins": pins,
            "schedule_rows": len(weeks),
            "schedule_first_month": weeks[0].year_month,
            "schedule_last_month": weeks[-1].year_month,
            "calendar_treatment_dates": len(treatment_dates),
            "distinct_event_rows": event_rows,
            "event_counts": dict(sorted(event_counts.items())),
            "normal_days": len(daily),
            "native_signals": sum(row.signal_count for row in daily),
            "lifecycles": len(lifecycles),
            "close_finals": event_counts["CLOSE"],
            "external_close_finals": event_counts["EXTERNAL_CLOSE"],
            "actual_net_usd": sum(row.actual_net for row in lifecycles),
            "stressed_net_usd": sum(row.stressed_net for row in lifecycles),
            "daily_centering_cells": 20,
            "lifecycle_centering_cells": 24,
            "component_period_density": component_period_density,
        },
        "state_counts": {
            TREATMENT: {
                "days": daily_states[TREATMENT],
                "signals": daily_signals[TREATMENT],
                "births": lifecycle_states[TREATMENT],
                "books": dict(sorted(treatment_books.items())),
                "components": dict(sorted(treatment_components.items())),
                "normal_day_weekdays": {weekday: treatment_weekdays[weekday] for weekday in WEEKDAYS},
            },
            OTHER: {
                "days": daily_states[OTHER],
                "signals": daily_signals[OTHER],
                "births": lifecycle_states[OTHER],
            },
            "treatment_period_days_signals_births": {
                key: {"days": value[0], "signals": value[1], "births": value[2]}
                for key, value in actual_treatment_period.items()
            },
        },
        "daily_supply": {"primary": supply_primary, "periods": supply_periods},
        "lifecycle_economics": {
            "primary": lifecycle_primary,
            "breakouts": {"books": books, "periods": periods, "components": components, "weekdays": weekdays},
            "direction_breadth": {
                "books": dict(book_directions),
                "periods": dict(period_directions),
                "components": dict(component_directions),
                "weekdays": dict(weekday_directions),
            },
            "contribution_caps": {
                "periods": period_contribution,
                "components": component_contribution,
                "weekdays": weekday_contribution,
            },
        },
        "gates": {"favorable": favorable, "adverse": adverse, "strong_null": strong_null},
        "decision": {
            "selected_candidate": None,
            "retained_lab_question": "one_nonautomatic_whole_portfolio_standard_expiration_week_risk_or_slot_question" if favorable["passed"] or adverse["passed"] else None,
            "optimization_candidate": None,
            "mt5_escalation": False,
            "fixed_development_candidate_changed_or_rejected": False,
            "live_authority": False,
        },
        "derived_rows": {
            "daily_supply": {
                "path": DAILY_PATH.relative_to(REPO).as_posix(),
                "bytes": DAILY_PATH.stat().st_size,
                "sha256": sha256_file(DAILY_PATH),
                "rows": len(daily),
            },
            "lifecycles": {
                "path": LIFECYCLE_PATH.relative_to(REPO).as_posix(),
                "bytes": LIFECYCLE_PATH.stat().st_size,
                "sha256": sha256_file(LIFECYCLE_PATH),
                "rows": len(lifecycles),
            },
        },
        "execution": {
            "preoutcome_engineering_corrections_inherited": 2,
            "unit_123_additional_engineering_corrections": 0,
            "successful_fixed_aggregations": 1,
            "metric_reruns": 0,
            "mql_copies_or_changes": 0,
            "compile_paths": 0,
            "tester_paths": 0,
            "mt5_runs": 0,
            "broker_or_account_queries": 0,
        },
        "limits": "A schedule association is not direct evidence of options positioning, gamma, volume, open interest, settlement flow or a tradable intraday expiration signal.",
        "program_6_opened": False,
        "optimization_surface": "UNTOUCHED",
        "live_surface": "UNTOUCHED",
        "goal_status": "ACTIVE_NOT_COMPLETE",
    }
    write_json(RESULT_PATH, result)
    print(
        json.dumps(
            {
                "verdict": verdict,
                "centered_stressed_r": effect_r,
                "centered_stop_rate": effect_stop,
                "daily_centered_signal_count": supply_primary["treatment_minus_other"]["centered_signal_count"],
                "daily_centered_birth_count": supply_primary["treatment_minus_other"]["centered_birth_count"],
                "daily_centered_sub_three_signal": supply_primary["treatment_minus_other"]["centered_sub_three_signal"],
                "direction_breadth": result["lifecycle_economics"]["direction_breadth"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
