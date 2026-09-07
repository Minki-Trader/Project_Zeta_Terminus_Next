"""Produce one immutable factual report from an archived native VS episode.

Usage:
    python collect_native_result.py selection-control-static-v1
    python collect_native_result.py selection-static-v2

Input is read only from RAW/native/<tag>.  Output is written once to
RAW/native-results/<tag>.json.  The report describes economic paths, native
summaries, lifecycle totals, trace counts, source hashes, and unresolved input
facts.  It does not rank roles or apply economic selection gates.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Callable, Iterable

from variance_signal import FAMILY, RAW, ROOT, record


SCHEMA = "v7-vs-native-economic-report-v1"
TAG_PATTERN = re.compile(
    r"selection-(?P<role>control-static|static|control-online|online)-v[1-9][0-9]*\Z"
)
KIND_NAMES = {"0": "cross", "1": "return", "2": "passive"}
REQUIRED_FILES = (
    "equity.csv",
    "forecasts.csv",
    "updates.csv",
    "entry-features.csv",
    "research-lifecycles.csv",
)
ACCOUNT_HEADER = (
    "server_time",
    "server_time_epoch",
    "server_minute_epoch",
    "forced",
    "actual_balance",
    "actual_equity",
    "original_stressed_balance",
    "conservative_stressed_mark",
    "conservative_mark_known",
    "conservative_mark_status",
    "positive_closed_swap",
    "conservative_risk_capital",
    "day_volume_multiplier",
    "owned_open_volume",
    "owned_pending_volume",
    "tracked_aggregate_planned_risk",
    "row_maximum_quote_age_seconds",
    "maximum_observed_quote_age_seconds",
    "quote_age_known",
    "owned_position_count",
    "owned_pending_count",
    "mark_skip_total",
    "entry_state_skip_total",
    "position_quote_skip_total",
    "quote_age_unknown_row_total",
    "write_fault_total",
    "evidence_fault_total",
)
FORECAST_HEADER = (
    "kind", "origin", "closed_bar", "observed_server", "v0", "ratio",
    "updates_before", "x0", "x1", "x2", "x3", "x4", "x5", "x6", "x7",
)
UPDATE_HEADER = (
    "kind", "label_origin", "available", "before_origin", "label", "complete",
    "update_count", "w0", "w1", "w2", "w3", "w4", "w5", "w6", "w7",
)
ENTRY_HEADER = (
    "kind", "server", "decision_closed_bar", "forecast_origin_bar",
    "original_feature", "candidate_feature", "status",
)
LIFECYCLE_HEADER = (
    "schema", "record_id", "utc", "server_time", "macro_join_utc_minute",
    "release_id", "execution_version", "portfolio_id", "event", "component_id",
    "symbol", "position_identifier", "entry_time_server", "segment_started_server",
    "direction", "volume", "entry_price", "entry_feature", "stop_loss",
    "planned_risk_usd", "entry_spread_price", "entry_transaction_cost",
    "entry_adverse_slippage", "entry_cost_known", "last_mark_profit_usd",
    "last_mark_r", "peak_mark_profit_usd", "peak_mark_r", "peak_time_server",
    "trough_mark_profit_usd", "trough_mark_r", "trough_time_server",
    "maximum_giveback_usd", "maximum_giveback_r", "mark_samples",
    "entry_active_mask", "entry_reserved_mask", "entry_active_slots",
    "entry_aggregate_risk_usd", "entry_us30_risk_usd", "entry_us100_risk_usd",
    "entry_aggregate_headroom_usd", "prior_signal_direction", "signal_relation",
    "rc4_sell_warning", "first_peer_component", "first_peer_exit_server",
    "exit_reason", "exit_class", "exit_price", "actual_net_usd",
    "stressed_net_usd", "current_active_mask", "current_reserved_mask",
    "current_us30_risk_usd", "current_us100_risk_usd", "partial_observation",
    "research_state_sequence", "research_dropped_records", "detail",
)
NUMBER = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?\Z")
KEY_VALUE = re.compile(r"([A-Za-z][A-Za-z0-9_]*)=(.*?)(?=\s+[A-Za-z][A-Za-z0-9_]*=|$)")
QUALITY_PATTERN = re.compile(r"(?:history\s+quality|real\s+ticks|히스토리\s*품질|실제\s*틱)", re.I)
FALLBACK_PATTERN = re.compile(
    r"(?:\bfallback\b|using\s+generated\s+ticks?|generated\s+ticks?\s+(?:used|substitut)|"
    r"ticks?\s+(?:were\s+)?generated\s+(?:instead|from)|real\s+ticks?.{0,80}(?:unavailable|missing|not\s+found)|"
    r"(?:history|tick\s+history).{0,80}(?:mismatch|missing|absent|unavailable|not\s+found|failed|error)|"
    r"(?:no|missing)\s+(?:real\s+)?tick\s+(?:data|history))",
    re.I,
)
GENERATION_PATTERN = re.compile(r"generat(?:e|ed|ing|ion)|생성", re.I)


def fail(message: str) -> None:
    raise RuntimeError(message)


def parse_tag(argv: list[str]) -> tuple[str, str]:
    if len(argv) != 2 or len(argv[1]) > 64:
        fail("expected one safe selection-{control-static|static|control-online|online}-vN tag")
    match = TAG_PATTERN.fullmatch(argv[1])
    if match is None:
        fail("expected one safe selection-{control-static|static|control-online|online}-vN tag")
    return argv[1], match.group("role")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def decode_text(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    if b"\x00" in data[:4096]:
        try:
            return data.decode("utf-16-le")
        except UnicodeDecodeError:
            return data.decode("utf-16-be")
    for encoding in ("utf-8-sig", "cp949", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace")


def text_encoding(path: Path) -> str:
    with path.open("rb") as stream:
        prefix = stream.read(4096)
    if prefix.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    if b"\x00" in prefix:
        return "utf-16-le"
    try:
        prefix.decode("utf-8-sig")
        return "utf-8-sig"
    except UnicodeDecodeError:
        return "cp949"


def csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]], int]:
    rows: list[dict[str, str]] = []
    malformed = 0
    with path.open("r", encoding=text_encoding(path), errors="replace", newline="") as stream:
        reader = csv.DictReader(stream)
        header = list(reader.fieldnames or [])
        if header:
            header[0] = header[0].lstrip("\ufeff")
            reader.fieldnames = header
        for raw in reader:
            if None in raw:
                malformed += 1
            rows.append({str(key): ("" if value is None else value.strip())
                         for key, value in raw.items() if key is not None})
    return header, rows, malformed


def schema_observation(header: list[str], expected: Iterable[str]) -> dict[str, object]:
    expected_list = list(expected)
    return {
        "header": header,
        "expected_header": expected_list,
        "exact_header_match": header == expected_list,
        "missing_columns": [name for name in expected_list if name not in header],
        "additional_columns": [name for name in header if name not in expected_list],
    }


def finite_number(value: str) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def integer(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        number = finite_number(value)
        if number is None or not number.is_integer():
            return None
        return int(number)


def clean_number(value: float) -> float:
    return float(f"{value:.12g}")


def series_summary(values: list[float]) -> dict[str, object]:
    if not values:
        return {"count": 0}
    peak = values[0]
    maximum_drawdown = 0.0
    maximum_drawdown_percent: float | None = None
    for value in values:
        peak = max(peak, value)
        drawdown = peak - value
        maximum_drawdown = max(maximum_drawdown, drawdown)
        if peak > 0.0:
            percentage = 100.0 * drawdown / peak
            maximum_drawdown_percent = max(maximum_drawdown_percent or 0.0, percentage)
    first = values[0]
    last = values[-1]
    return {
        "count": len(values),
        "first": clean_number(first),
        "last": clean_number(last),
        "change": clean_number(last - first),
        "growth_multiple": (clean_number(last / first) if first != 0.0 else None),
        "minimum": clean_number(min(values)),
        "maximum": clean_number(max(values)),
        "maximum_drawdown": clean_number(maximum_drawdown),
        "maximum_drawdown_percent": (
            clean_number(maximum_drawdown_percent)
            if maximum_drawdown_percent is not None else None
        ),
    }


def value_histogram(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def account_path_report(path: Path, unknowns: list[str]) -> dict[str, object]:
    row_count = 0
    malformed = 0
    missing_numbers: Counter[str] = Counter()
    series: dict[str, list[float]] = {
        "actual_balance": [],
        "actual_equity": [],
        "original_stressed_balance": [],
        "conservative_stressed_mark": [],
    }
    mark_status: Counter[str] = Counter()
    day_multiplier: Counter[str] = Counter()
    observed_minutes: set[int] = set()
    duplicate_minutes = 0
    unreadable_minutes = 0
    nondecreasing = True
    previous_minute: int | None = None
    forced_rows = 0
    mark_known_rows = 0
    mark_unknown_rows = 0
    first_server_time: str | None = None
    last_server_time: str | None = None
    final_row: dict[str, str] | None = None
    maximum_open_volume = 0.0
    maximum_pending_volume = 0.0
    maximum_position_count = 0
    maximum_pending_count = 0
    maximum_quote_age = 0.0

    with path.open("r", encoding=text_encoding(path), errors="replace", newline="") as stream:
        reader = csv.DictReader(stream)
        header = list(reader.fieldnames or [])
        if header:
            header[0] = header[0].lstrip("\ufeff")
            reader.fieldnames = header
        schema = schema_observation(header, ACCOUNT_HEADER)
        if not schema["exact_header_match"]:
            unknowns.append("equity.csv header differs from the authored account-path schema")
        for raw in reader:
            if None in raw:
                malformed += 1
            row = {str(key): ("" if value is None else value.strip())
                   for key, value in raw.items() if key is not None}
            row_count += 1
            final_row = row
            server_time = row.get("server_time", "")
            if first_server_time is None:
                first_server_time = server_time
            last_server_time = server_time
            forced_rows += row.get("forced") == "1"
            mark_status[row.get("conservative_mark_status", "")] += 1
            day_multiplier[row.get("day_volume_multiplier", "")] += 1

            minute = integer(row.get("server_minute_epoch", ""))
            if minute is None:
                unreadable_minutes += 1
            else:
                if minute in observed_minutes:
                    duplicate_minutes += 1
                observed_minutes.add(minute)
                if previous_minute is not None and minute < previous_minute:
                    nondecreasing = False
                previous_minute = minute

            for name in ("actual_balance", "actual_equity", "original_stressed_balance"):
                value = finite_number(row.get(name, ""))
                if value is None:
                    missing_numbers[name] += 1
                else:
                    series[name].append(value)
            if row.get("conservative_mark_known") == "1":
                mark_known_rows += 1
                value = finite_number(row.get("conservative_stressed_mark", ""))
                if value is None:
                    missing_numbers["conservative_stressed_mark"] += 1
                else:
                    series["conservative_stressed_mark"].append(value)
            else:
                mark_unknown_rows += 1

            open_volume = finite_number(row.get("owned_open_volume", ""))
            pending_volume = finite_number(row.get("owned_pending_volume", ""))
            position_count = integer(row.get("owned_position_count", ""))
            pending_count = integer(row.get("owned_pending_count", ""))
            quote_age = finite_number(row.get("maximum_observed_quote_age_seconds", ""))
            for name, value in (
                ("owned_open_volume", open_volume),
                ("owned_pending_volume", pending_volume),
                ("owned_position_count", position_count),
                ("owned_pending_count", pending_count),
                ("maximum_observed_quote_age_seconds", quote_age),
            ):
                if value is None:
                    missing_numbers[name] += 1
            if open_volume is not None:
                maximum_open_volume = max(maximum_open_volume, open_volume)
            if pending_volume is not None:
                maximum_pending_volume = max(maximum_pending_volume, pending_volume)
            if position_count is not None:
                maximum_position_count = max(maximum_position_count, position_count)
            if pending_count is not None:
                maximum_pending_count = max(maximum_pending_count, pending_count)
            if quote_age is not None:
                maximum_quote_age = max(maximum_quote_age, quote_age)

    csv_final_flat: bool | None = None
    csv_final_mark_known: bool | None = None
    if final_row is not None:
        positions = integer(final_row.get("owned_position_count", ""))
        pending = integer(final_row.get("owned_pending_count", ""))
        open_volume = finite_number(final_row.get("owned_open_volume", ""))
        pending_volume = finite_number(final_row.get("owned_pending_volume", ""))
        csv_final_mark_known = final_row.get("conservative_mark_known") == "1"
        if None not in (positions, pending, open_volume, pending_volume):
            csv_final_flat = (
                positions == 0 and pending == 0 and
                open_volume == 0.0 and pending_volume == 0.0
            )
    if row_count == 0:
        unknowns.append("equity.csv contains no observations")
    if malformed:
        unknowns.append(f"equity.csv contains {malformed} malformed CSV rows")
    if unreadable_minutes:
        unknowns.append("equity.csv contains an unreadable server_minute_epoch")
    return {
        "source": record(path),
        "schema": schema,
        "rows": row_count,
        "malformed_rows": malformed,
        "first_server_time": first_server_time,
        "last_server_time": last_server_time,
        "distinct_server_minutes": len(observed_minutes),
        "duplicate_server_minute_rows": duplicate_minutes,
        "server_minutes_nondecreasing": nondecreasing,
        "forced_rows": forced_rows,
        "actual_balance": series_summary(series["actual_balance"]),
        "actual_equity": series_summary(series["actual_equity"]),
        "original_stressed_balance": series_summary(series["original_stressed_balance"]),
        "conservative_stressed_mark": series_summary(series["conservative_stressed_mark"]),
        "conservative_mark_known_rows": mark_known_rows,
        "conservative_mark_unknown_rows": mark_unknown_rows,
        "conservative_mark_status_histogram": dict(sorted(mark_status.items())),
        "day_volume_multiplier_histogram": dict(sorted(day_multiplier.items())),
        "maximum_owned_open_volume": clean_number(maximum_open_volume),
        "maximum_owned_pending_volume": clean_number(maximum_pending_volume),
        "maximum_owned_position_count": maximum_position_count,
        "maximum_owned_pending_count": maximum_pending_count,
        "maximum_observed_quote_age_seconds": clean_number(maximum_quote_age),
        "final_csv_observation": {
            "flat": csv_final_flat,
            "conservative_mark_known": csv_final_mark_known,
            "mark_status": (final_row.get("conservative_mark_status") if final_row else None),
            "write_fault_total": (
                integer(final_row.get("write_fault_total", "")) if final_row else None
            ),
            "evidence_fault_total": (
                integer(final_row.get("evidence_fault_total", "")) if final_row else None
            ),
        },
        "unreadable_numeric_values": dict(sorted(missing_numbers.items())),
    }


def server_half(value: str) -> str | None:
    try:
        timestamp = datetime.strptime(value, "%Y.%m.%d %H:%M:%S")
    except ValueError:
        return None
    return f"{timestamp.year}-H{1 if timestamp.month <= 6 else 2}"


def volume_key(value: str) -> str | None:
    try:
        decimal = Decimal(value)
    except InvalidOperation:
        return None
    if not decimal.is_finite():
        return None
    return format(decimal.normalize(), "f")


def lifecycle_report(path: Path, unknowns: list[str]) -> dict[str, object]:
    header, rows, malformed = csv_rows(path)
    schema = schema_observation(header, LIFECYCLE_HEADER)
    if not schema["exact_header_match"]:
        unknowns.append("research-lifecycles.csv header differs from the authored lifecycle schema")
    births = [row for row in rows if row.get("event") == "BIRTH"]
    closes = [row for row in rows if row.get("event") == "CLOSE"]
    partial_exits = [row for row in rows if row.get("event") == "PARTIAL_EXIT"]
    event_histogram = value_histogram(row.get("event", "") for row in rows)

    birth_ids: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    close_ids: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in births:
        birth_ids[row.get("position_identifier", "")].append(row)
    for row in closes:
        close_ids[row.get("position_identifier", "")].append(row)
    identifiers = set(birth_ids) | set(close_ids)
    exactly_matched = sum(
        len(birth_ids[identifier]) == 1 and len(close_ids[identifier]) == 1
        for identifier in identifiers if identifier not in ("", "0")
    )
    unmatched_births = sum(
        len(group) for identifier, group in birth_ids.items()
        if (identifier in ("", "0") or len(group) != 1 or
            len(close_ids[identifier]) != 1)
    )
    unmatched_closes = sum(
        len(group) for identifier, group in close_ids.items()
        if (identifier in ("", "0") or len(group) != 1 or
            len(birth_ids[identifier]) != 1)
    )
    duplicate_birth_identifiers = sorted(
        identifier for identifier, group in birth_ids.items() if len(group) > 1
    )
    duplicate_close_identifiers = sorted(
        identifier for identifier, group in close_ids.items() if len(group) > 1
    )

    by_half: defaultdict[str, dict[str, object]] = defaultdict(
        lambda: {"birth_count": 0, "close_count": 0,
                 "actual_values": [], "stressed_values": []}
    )
    by_component: defaultdict[str, dict[str, object]] = defaultdict(
        lambda: {"birth_count": 0, "close_count": 0,
                 "actual_values": [], "stressed_values": [], "volumes": Counter()}
    )
    by_component_half: defaultdict[str, dict[str, object]] = defaultdict(
        lambda: {"birth_count": 0, "close_count": 0,
                 "actual_values": [], "stressed_values": []}
    )
    all_birth_volumes: Counter[str] = Counter()
    unreadable_economic_rows = 0
    unreadable_server_times = 0
    unreadable_volumes = 0
    for row in births:
        half = server_half(row.get("server_time", ""))
        if half is None:
            unreadable_server_times += 1
        else:
            by_half[half]["birth_count"] += 1
        component = row.get("component_id", "")
        by_component[component]["birth_count"] += 1
        if half is not None:
            by_component_half[f"{component}|{half}"]["birth_count"] += 1
        volume = volume_key(row.get("volume", ""))
        if volume is None:
            unreadable_volumes += 1
        else:
            by_component[component]["volumes"][volume] += 1
            all_birth_volumes[volume] += 1
    for row in closes:
        actual = finite_number(row.get("actual_net_usd", ""))
        stressed = finite_number(row.get("stressed_net_usd", ""))
        half = server_half(row.get("server_time", ""))
        component = row.get("component_id", "")
        by_component[component]["close_count"] += 1
        if half is None:
            unreadable_server_times += 1
        else:
            by_half[half]["close_count"] += 1
            by_component_half[f"{component}|{half}"]["close_count"] += 1
        if actual is None or stressed is None:
            unreadable_economic_rows += 1
            continue
        by_component[component]["actual_values"].append(actual)
        by_component[component]["stressed_values"].append(stressed)
        if half is not None:
            by_half[half]["actual_values"].append(actual)
            by_half[half]["stressed_values"].append(stressed)
            by_component_half[f"{component}|{half}"]["actual_values"].append(actual)
            by_component_half[f"{component}|{half}"]["stressed_values"].append(stressed)

    def totals(bucket: dict[str, object], include_volumes: bool = False) -> dict[str, object]:
        result = {
            "birth_count": bucket["birth_count"],
            "close_count": bucket["close_count"],
            "actual_net_usd": clean_number(math.fsum(bucket["actual_values"])),
            "stressed_net_usd": clean_number(math.fsum(bucket["stressed_values"])),
        }
        if include_volumes:
            result["birth_volume_histogram"] = dict(sorted(bucket["volumes"].items()))
        return result

    halves = {name: totals(bucket) for name, bucket in sorted(by_half.items())}
    components = {
        name: totals(bucket, include_volumes=True)
        for name, bucket in sorted(by_component.items())
    }
    component_halves = {
        name: totals(bucket) for name, bucket in sorted(by_component_half.items())
    }
    all_actual = [value for bucket in by_component.values() for value in bucket["actual_values"]]
    all_stressed = [value for bucket in by_component.values() for value in bucket["stressed_values"]]
    if malformed:
        unknowns.append(f"research-lifecycles.csv contains {malformed} malformed CSV rows")
    if unreadable_economic_rows:
        unknowns.append(f"{unreadable_economic_rows} CLOSE rows have unreadable economic totals")
    if unreadable_server_times:
        unknowns.append(f"{unreadable_server_times} BIRTH/CLOSE rows have unreadable server_time")
    if unreadable_volumes:
        unknowns.append(f"{unreadable_volumes} BIRTH rows have unreadable volume")
    if unmatched_births or unmatched_closes:
        unknowns.append("some native lifecycle BIRTH/CLOSE rows are not one-to-one")
    return {
        "source": record(path),
        "schema": schema,
        "event_contract": {"birth": "BIRTH", "final": "CLOSE"},
        "rows": len(rows),
        "malformed_rows": malformed,
        "event_histogram": event_histogram,
        "birth_count": len(births),
        "close_count": len(closes),
        "partial_exit_count": len(partial_exits),
        "exactly_one_birth_one_close_identifiers": exactly_matched,
        "unmatched_birth_rows": unmatched_births,
        "unmatched_close_rows": unmatched_closes,
        "duplicate_birth_identifiers": duplicate_birth_identifiers,
        "duplicate_close_identifiers": duplicate_close_identifiers,
        "full_close_totals": {
            "actual_net_usd": clean_number(math.fsum(all_actual)),
            "stressed_net_usd": clean_number(math.fsum(all_stressed)),
        },
        "birth_volume_histogram": dict(sorted(all_birth_volumes.items())),
        "by_server_half": halves,
        "by_component": components,
        "by_component_and_server_half": component_halves,
        "entry_cost_known_histogram": value_histogram(
            row.get("entry_cost_known", "") for row in closes
        ),
        "partial_observation_histogram": value_histogram(
            row.get("partial_observation", "") for row in closes
        ),
        "unreadable_economic_close_rows": unreadable_economic_rows,
        "unreadable_server_time_rows": unreadable_server_times,
        "unreadable_birth_volumes": unreadable_volumes,
    }


def trace_csv_report(path: Path, expected: Iterable[str]) -> tuple[dict[str, object], list[dict[str, str]]]:
    header, rows, malformed = csv_rows(path)
    result = {
        "source": record(path),
        "schema": schema_observation(header, expected),
        "rows": len(rows),
        "malformed_rows": malformed,
        "rows_by_kind": {
            KIND_NAMES.get(kind, f"unknown-{kind}"): count
            for kind, count in sorted(Counter(row.get("kind", "") for row in rows).items())
        },
    }
    return result, rows


def trace_report(paths: dict[str, Path | None], unknowns: list[str]) -> dict[str, object]:
    output: dict[str, object] = {}
    parsed: dict[str, list[dict[str, str]]] = {}
    definitions = {
        "forecasts.csv": FORECAST_HEADER,
        "updates.csv": UPDATE_HEADER,
        "entry-features.csv": ENTRY_HEADER,
    }
    for name, expected in definitions.items():
        path = paths.get(name)
        if path is None:
            output[name] = None
            parsed[name] = []
            continue
        report, rows = trace_csv_report(path, expected)
        output[name] = report
        parsed[name] = rows
        if not report["schema"]["exact_header_match"]:
            unknowns.append(f"{name} header differs from its authored trace schema")
        if report["malformed_rows"]:
            unknowns.append(f"{name} contains malformed CSV rows")

    update_rows = parsed["updates.csv"]
    entry_rows = parsed["entry-features.csv"]
    output["updates"] = {
        "complete_histogram": value_histogram(row.get("complete", "") for row in update_rows),
        "last_update_count_by_kind": {},
    }
    for kind in ("0", "1", "2"):
        values = [integer(row.get("update_count", "")) for row in update_rows if row.get("kind") == kind]
        valid = [value for value in values if value is not None]
        output["updates"]["last_update_count_by_kind"][KIND_NAMES[kind]] = (
            valid[-1] if valid else 0
        )
    output["entry_features"] = {
        "status_histogram": value_histogram(row.get("status", "") for row in entry_rows),
        "status_by_kind": {
            KIND_NAMES[kind]: value_histogram(
                row.get("status", "") for row in entry_rows if row.get("kind") == kind
            ) for kind in ("0", "1", "2")
        },
    }
    return output


def convert_value(value: str) -> object:
    lowered = value.casefold()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.fullmatch(r"[-+]?\d+", value):
        try:
            return int(value)
        except ValueError:
            return value
    if NUMBER.fullmatch(value):
        number = finite_number(value)
        return clean_number(number) if number is not None else value
    return value


def parse_key_values(text: str) -> dict[str, object]:
    return {match.group(1): convert_value(match.group(2).strip()) for match in KEY_VALUE.finditer(text)}


def line_item(path: Path, number: int, line: str, marker: str | None = None) -> dict[str, object]:
    payload = line[line.find(marker):] if marker and marker in line else line
    return {
        "source": rel(path),
        "line_number": number,
        "line": line,
        "fields": parse_key_values(payload),
    }


def log_report(paths: list[Path]) -> dict[str, object]:
    markers: dict[str, tuple[str, Callable[[str], bool]]] = {
        "v7rr1_native": ("V7RR1_NATIVE ", lambda line: "V7RR1_NATIVE " in line),
        "v7rr1_result": ("V7RR1_RESULT ", lambda line: "V7RR1_RESULT " in line),
        "v7rr1_unavailable_summary": (
            "V7RR1_UNAVAILABLE_SUMMARY ", lambda line: "V7RR1_UNAVAILABLE_SUMMARY " in line
        ),
        "vs_account_end": (
            "VS_ACCOUNT_END ", lambda line: "VS_ACCOUNT_END " in line and "VS_ACCOUNT_END_FAULT" not in line
        ),
        "vs_account_end_fault": (
            "VS_ACCOUNT_END_FAULT ", lambda line: "VS_ACCOUNT_END_FAULT " in line
        ),
        "vs_account_file_fault": (
            "VS_ACCOUNT_FILE_FAULT ", lambda line: "VS_ACCOUNT_FILE_FAULT " in line
        ),
        "vs_learning": (
            "VS_LEARNING kind=", lambda line: "VS_LEARNING kind=" in line
        ),
        "vs_learning_faults": (
            "VS_LEARNING_FAULTS ", lambda line: "VS_LEARNING_FAULTS " in line
        ),
        "vs_learning_fault": (
            "VS_LEARNING_FAULT ",
            lambda line: "VS_LEARNING_FAULT " in line and "VS_LEARNING_FAULTS " not in line,
        ),
        "final_portfolio": ("final portfolio=", lambda line: "final portfolio=" in line),
        "tester_scheduler": ("tester_scheduler ", lambda line: "tester_scheduler " in line),
    }
    found: dict[str, list[dict[str, object]]] = {name: [] for name in markers}
    quality_lines: list[dict[str, object]] = []
    fallback_lines: list[dict[str, object]] = []
    generic_generation_lines: list[dict[str, object]] = []
    for path in paths:
        for number, line in enumerate(decode_text(path).splitlines(), start=1):
            exact = line.rstrip("\r\n")
            for name, (marker, predicate) in markers.items():
                if predicate(exact):
                    found[name].append(line_item(path, number, exact, marker))
            if QUALITY_PATTERN.search(exact):
                quality_lines.append(line_item(path, number, exact))
            if FALLBACK_PATTERN.search(exact):
                fallback_lines.append(line_item(path, number, exact))
            elif GENERATION_PATTERN.search(exact):
                generic_generation_lines.append(line_item(path, number, exact))
    summaries = {
        name: {"count": len(items), "latest": (items[-1] if items else None), "occurrences": items}
        for name, items in found.items()
    }
    return {
        "sources": [record(path) for path in paths],
        "summaries": summaries,
        "quality_lines": quality_lines,
        "explicit_history_fallback_lines": fallback_lines,
        "generic_generation_lines": generic_generation_lines,
    }


class TableRows(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.casefold()
        if name == "tr":
            self.row = []
        elif name in ("td", "th") and self.row is not None:
            self.cell = []
        elif name == "br" and self.cell is not None:
            self.cell.append(" ")

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        name = tag.casefold()
        if name in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif name == "tr" and self.row is not None:
            if any(self.row):
                self.rows.append(self.row)
            self.row = None


REPORT_LABELS = {
    "period": ("period", "기간"),
    "initial_deposit": ("initial deposit", "초기 예탁금", "초기예탁금"),
    "history_quality": ("history quality", "히스토리 품질"),
    "total_net_profit": ("total net profit", "총 순이익", "총순이익"),
    "equity_drawdown": (
        "equity drawdown maximal", "equity drawdown maximum",
        "자본금 최대 감소", "자본 최대 감소",
    ),
    "total_trades": ("total trades", "총 거래", "총거래"),
}


def report_html(path: Path, unknowns: list[str]) -> dict[str, object]:
    parser = TableRows()
    parser.feed(decode_text(path))
    fields: dict[str, dict[str, str]] = {}
    for row in parser.rows:
        for index, cell in enumerate(row):
            normalized = cell.rstrip(":").strip().casefold()
            for key, aliases in REPORT_LABELS.items():
                if key in fields:
                    continue
                if normalized in aliases:
                    fields[key] = {
                        "label": cell,
                        "value": (row[index + 1] if index + 1 < len(row) else ""),
                    }
    quality = fields.get("history_quality")
    quality_percent: float | None = None
    real_tick_label: bool | None = None
    if quality is not None:
        match = re.search(r"(\d+(?:\.\d+)?)\s*%", quality["value"])
        if match:
            quality_percent = float(match.group(1))
        else:
            unknowns.append("report.html history-quality percentage was not parsed")
        real_tick_label = bool(re.search(r"real\s+ticks|실제\s*틱", quality["value"], re.I))
    else:
        unknowns.append("report.html history-quality label/value was not located")
    return {
        "source": record(path),
        "summary_fields": fields,
        "history_quality_percent": quality_percent,
        "history_quality_real_tick_label": real_tick_label,
        "table_row_count": len(parser.rows),
    }


def locate_files(files_root: Path, unknowns: list[str]) -> dict[str, Path | None]:
    candidates: defaultdict[str, list[Path]] = defaultdict(list)
    if files_root.is_dir():
        for path in files_root.rglob("*"):
            if path.is_file():
                candidates[path.name.casefold()].append(path)
    located: dict[str, Path | None] = {}
    for name in REQUIRED_FILES:
        matches = candidates[name.casefold()]
        if len(matches) == 1:
            located[name] = matches[0]
        else:
            located[name] = None
            if not matches:
                unknowns.append(f"required Files artifact is missing: {name}")
            else:
                unknowns.append(f"required Files artifact is ambiguous: {name} ({len(matches)} copies)")
    return located


def native_summary_observations(logs: dict[str, object]) -> dict[str, object]:
    summaries = logs["summaries"]
    keys = (
        "v7rr1_native", "v7rr1_result", "v7rr1_unavailable_summary",
        "vs_account_end", "vs_account_end_fault", "vs_account_file_fault",
        "vs_learning_faults", "vs_learning_fault", "final_portfolio", "tester_scheduler",
    )
    return {key: summaries[key]["latest"] for key in keys}


def learner_trace_observations(logs: dict[str, object], trace: dict[str, object]) -> dict[str, object]:
    learning = logs["summaries"]["vs_learning"]["occurrences"]
    reported_by_kind: dict[str, dict[str, object]] = {}
    for item in learning:
        raw_kind = str(item["fields"].get("kind", ""))
        reported_by_kind[KIND_NAMES.get(raw_kind, f"unknown-{raw_kind}")] = item["fields"]
    forecast_rows = (trace.get("forecasts.csv") or {}).get("rows_by_kind", {})
    update_counts = trace.get("updates", {}).get("last_update_count_by_kind", {})
    entry_status = trace.get("entry_features", {}).get("status_by_kind", {})
    comparison: dict[str, object] = {}
    for name in ("cross", "return", "passive"):
        reported = reported_by_kind.get(name, {})
        observed_status = entry_status.get(name, {})
        comparison[name] = {
            "reported": reported or None,
            "forecast_csv_rows": forecast_rows.get(name, 0),
            "last_update_count_in_updates_csv": update_counts.get(name, 0),
            "entry_applied_csv_rows": observed_status.get("APPLIED", 0),
            "entry_non_applied_csv_rows": sum(
                count for status, count in observed_status.items() if status != "APPLIED"
            ),
        }
    return comparison


def collect() -> int:
    tag, role = parse_tag(sys.argv)
    if FAMILY != Path(__file__).resolve().parent:
        fail("variance_signal family binding differs from this report producer")
    episode = RAW / "native" / tag
    output = RAW / "native-results" / f"{tag}.json"
    if not episode.is_dir():
        fail(f"native episode is missing: {rel(episode)}")
    if output.exists():
        fail("native result already exists for this immutable tag")

    unknowns: list[str] = []
    files_root = episode / "Files"
    located = locate_files(files_root, unknowns)
    log_paths = [episode / "agent-episode.log", episode / "terminal-episode.log"]
    present_logs = [path for path in log_paths if path.is_file()]
    for path in log_paths:
        if not path.is_file():
            unknowns.append(f"required native log is missing: {path.name}")
    html_path = episode / "report.html"
    if not html_path.is_file():
        unknowns.append("required native report is missing: report.html")

    source_paths = sorted(
        (path for path in episode.rglob("*") if path.is_file()),
        key=lambda path: rel(path),
    )
    source_records = [record(path) for path in source_paths]
    account = (
        account_path_report(located["equity.csv"], unknowns)
        if located["equity.csv"] is not None else None
    )
    lifecycle = (
        lifecycle_report(located["research-lifecycles.csv"], unknowns)
        if located["research-lifecycles.csv"] is not None else None
    )
    traces = trace_report(located, unknowns)
    logs = log_report(present_logs)
    html = report_html(html_path, unknowns) if html_path.is_file() else None
    summary_observations = native_summary_observations(logs)

    end_observation = summary_observations.get("vs_account_end")
    logged_flat = (
        end_observation["fields"].get("flat") if end_observation is not None else None
    )
    logged_mark_known = (
        end_observation["fields"].get("mark_known") if end_observation is not None else None
    )
    csv_final = account["final_csv_observation"] if account is not None else {}
    end_flat = {
        "equity_csv_flat": csv_final.get("flat"),
        "equity_csv_mark_known": csv_final.get("conservative_mark_known"),
        "vs_account_end_flat": logged_flat,
        "vs_account_end_mark_known": logged_mark_known,
    }

    missing_required = [name for name, path in located.items() if path is None]
    if not present_logs:
        unknowns.append("no native log is available for summary extraction")
    for marker in ("v7rr1_native", "v7rr1_result", "vs_account_end"):
        if logs["summaries"][marker]["count"] == 0:
            unknowns.append(f"native summary line was not observed: {marker}")

    report_data = {
        "schema": SCHEMA,
        "family": "v7-onnx-online-variance-standardization-v1",
        "observation_tag": tag,
        "role": role,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "input_root": rel(episode),
        "report_contract": {
            "lifecycle_birth_event": "BIRTH",
            "lifecycle_final_event": "CLOSE",
            "birth_half_year_attribution": "BIRTH observer server_time",
            "economic_half_year_attribution": "CLOSE observer server_time",
            "partial_exit_rows_in_economic_sum": False,
            "role_ranking_or_economic_gate": None,
            "causal_completeness_assessed": False,
            "native_fault_counts_used_as_causal_completeness": False,
        },
        "input_inventory": {
            "files": source_records,
            "file_count": len(source_records),
            "logical_bytes": sum(item["bytes"] for item in source_records),
        },
        "completeness": {
            "scope": "artifact availability and authored schema observations only",
            "required_files": list(REQUIRED_FILES),
            "missing_or_ambiguous_files": missing_required,
            "agent_log_present": log_paths[0].is_file(),
            "terminal_log_present": log_paths[1].is_file(),
            "report_html_present": html_path.is_file(),
            "unknowns": sorted(set(unknowns)),
        },
        "account_path": account,
        "end_flat_observations": end_flat,
        "lifecycles": lifecycle,
        "learner_traces": traces,
        "learner_summary_vs_trace_observations": learner_trace_observations(logs, traces),
        "native_logs": logs,
        "native_summary_observations": summary_observations,
        "report_html": html,
        "original_valid_and_fault_counters": {
            "v7rr1_result": (
                summary_observations["v7rr1_result"]["fields"]
                if summary_observations["v7rr1_result"] is not None else None
            ),
            "v7rr1_unavailable_summary": (
                summary_observations["v7rr1_unavailable_summary"]["fields"]
                if summary_observations["v7rr1_unavailable_summary"] is not None else None
            ),
            "final_portfolio": (
                summary_observations["final_portfolio"]["fields"]
                if summary_observations["final_portfolio"] is not None else None
            ),
            "vs_account_end": (
                summary_observations["vs_account_end"]["fields"]
                if summary_observations["vs_account_end"] is not None else None
            ),
            "vs_learning_faults": (
                summary_observations["vs_learning_faults"]["fields"]
                if summary_observations["vs_learning_faults"] is not None else None
            ),
            "vs_account_file_fault_lines": logs["summaries"]["vs_account_file_fault"]["count"],
            "vs_account_end_fault_lines": logs["summaries"]["vs_account_end_fault"]["count"],
            "vs_learning_fault_lines": logs["summaries"]["vs_learning_fault"]["count"],
        },
    }
    payload = (json.dumps(report_data, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        fail("native result already exists for this immutable tag")
    print(json.dumps({"native_result": record(output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(collect())
    except Exception as exc:
        print(f"native result collection failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
