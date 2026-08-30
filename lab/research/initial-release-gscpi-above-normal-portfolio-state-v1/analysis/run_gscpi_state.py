#!/usr/bin/env python3
"""Run the one frozen Unit 116 GSCPI-state economic aggregation.

This is a finite research aggregation, not a validator, test harness, reusable
CLI product, trading program, promotion checker, or broker/account query.
"""

from __future__ import annotations

import bisect
import csv
import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[4]
FAMILY = REPO / "lab/research/initial-release-gscpi-above-normal-portfolio-state-v1"
EVIDENCE = FAMILY / "evidence"
DECLARATION_PATH = (
    EVIDENCE
    / "INITIAL_RELEASE_GSCPI_ABOVE_NORMAL_PORTFOLIO_STATE_DECLARATION_V1.json"
)
SCHEDULE_PATH = EVIDENCE / "GSCPI_INITIAL_RELEASE_SCHEDULE_V1.csv"
DERIVED_PATH = EVIDENCE / "INITIAL_RELEASE_GSCPI_ABOVE_NORMAL_DERIVED_ROWS_V1.csv"
RESULT_PATH = (
    EVIDENCE / "INITIAL_RELEASE_GSCPI_ABOVE_NORMAL_PORTFOLIO_STATE_RESULT_V1.json"
)
CLOSURE_PATH = (
    EVIDENCE / "INITIAL_RELEASE_GSCPI_ABOVE_NORMAL_PORTFOLIO_STATE_CLOSURE_V1.json"
)

ABOVE = "ABOVE_NORMAL"
BELOW = "AT_OR_BELOW_NORMAL"
UNAVAILABLE = "UNAVAILABLE"
STATES = (ABOVE, BELOW)
CONFIRMATORY_PERIODS = ("P1_2022H2_2023", "P2_2024", "P3_2025")
ALL_PERIODS = CONFIRMATORY_PERIODS + ("P4_2026_YTD",)

PLANNED_RISK = re.compile(r"(?:^|\s)planned_risk=([-+0-9.eE]+)(?:\s|$)")
REASON = re.compile(r"(?:^|\s)reason=([A-Z_]+)(?:\s|$)")


@dataclass(frozen=True)
class Release:
    vintage: str
    release_date: date
    observation_date: date
    value: float
    state: str


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
    state: str
    release_vintage: str | None
    release_date: date | None
    observation_date: date | None
    initial_gscpi: float | None
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def finite_float(text: str, context: str) -> float:
    value = float(text)
    require(math.isfinite(value), f"nonfinite value: {context}")
    return value


def detail_value(pattern: re.Pattern[str], detail: str, context: str) -> str:
    match = pattern.search(detail)
    require(match is not None, f"missing detail field {context}")
    return match.group(1)


def parse_server(text: str) -> datetime:
    return datetime.strptime(text, "%Y.%m.%d %H:%M:%S")


def verify_pins(declaration: dict[str, Any]) -> dict[str, Any]:
    checked: list[dict[str, Any]] = []
    for pin in declaration["immutable_source_pins"] + declaration[
        "immutable_portfolio_inputs"
    ]:
        path = REPO / pin["path"]
        require(path.is_file(), f"missing pinned input: {pin['path']}")
        actual_bytes = path.stat().st_size
        actual_sha = sha256_file(path)
        require(actual_bytes == pin["bytes"], f"byte mismatch: {pin['path']}")
        require(actual_sha == pin["sha256"], f"hash mismatch: {pin['path']}")
        checked.append(
            {
                "path": pin["path"],
                "bytes": actual_bytes,
                "sha256": actual_sha,
            }
        )
    require(len(checked) == 10, f"unexpected pin count: {len(checked)}")
    return {"passed": True, "count": len(checked), "pins": checked}


def load_releases() -> list[Release]:
    releases: list[Release] = []
    with SCHEDULE_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        require(
            reader.fieldnames
            == [
                "vintage",
                "release_date",
                "release_time_et",
                "observation_date",
                "initial_value",
                "state",
                "release_rule_source",
            ],
            f"unexpected schedule columns: {reader.fieldnames}",
        )
        previous: date | None = None
        for row in reader:
            release = Release(
                vintage=row["vintage"],
                release_date=date.fromisoformat(row["release_date"]),
                observation_date=date.fromisoformat(row["observation_date"]),
                value=finite_float(row["initial_value"], row["vintage"]),
                state=row["state"],
            )
            require(release.state in STATES, f"unexpected state: {release.state}")
            require(
                previous is None or release.release_date > previous,
                "non-increasing release schedule",
            )
            require(
                release.observation_date < release.release_date,
                f"noncausal observation date: {release.vintage}",
            )
            previous = release.release_date
            releases.append(release)
    require(len(releases) == 49, f"unexpected release count: {len(releases)}")
    return releases


def map_release(birth_day: date, releases: list[Release]) -> Release | None:
    release_dates = [item.release_date for item in releases]
    index = bisect.bisect_left(release_dates, birth_day) - 1
    return releases[index] if index >= 0 else None


def reconstruct_lifecycles(
    declaration: dict[str, Any], releases: list[Release]
) -> tuple[list[Lifecycle], Counter[str], int]:
    mappings = {
        item["component_id"]: (item["name"], item["book"], item["birth_event"])
        for item in declaration["component_mapping"]
    }
    lifecycles: list[Lifecycle] = []
    event_counts: Counter[str] = Counter()
    event_rows = 0
    record_number = 0

    for source in declaration["immutable_portfolio_inputs"]:
        path = REPO / source["path"]
        open_by_component: dict[str, tuple[int, dict[str, str]]] = {}
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            require(
                reader.fieldnames
                == [
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
                ],
                f"unexpected event columns: {source['path']}",
            )
            for source_row, row in enumerate(reader, start=2):
                event_rows += 1
                event = row["event"]
                event_counts[event] += 1
                component_id = row["component_id"]
                if component_id not in mappings:
                    continue
                component, book, birth_event = mappings[component_id]
                if event == birth_event:
                    require(
                        component_id not in open_by_component,
                        f"overlapping birth: {source['path']}:{source_row}:{component}",
                    )
                    open_by_component[component_id] = (source_row, row)
                elif event in {"CLOSE", "EXTERNAL_CLOSE"}:
                    require(
                        component_id in open_by_component,
                        f"final without birth: {source['path']}:{source_row}:{component}",
                    )
                    birth_row_number, birth = open_by_component.pop(component_id)
                    birth_server = parse_server(birth["server_time"])
                    final_server = parse_server(row["server_time"])
                    require(final_server >= birth_server, "final precedes birth")
                    planned_risk = finite_float(
                        detail_value(
                            PLANNED_RISK,
                            row["detail"],
                            f"planned_risk:{source['path']}:{source_row}",
                        ),
                        f"planned_risk:{source['path']}:{source_row}",
                    )
                    require(planned_risk > 0.0, "nonpositive planned risk")
                    reason = detail_value(
                        REASON,
                        row["detail"],
                        f"reason:{source['path']}:{source_row}",
                    )
                    require(
                        reason in {"DEAL_REASON_SL", "DEAL_REASON_EXPERT"},
                        f"unexpected final reason: {reason}",
                    )
                    actual_net = finite_float(
                        row["value_a"], f"actual:{source['path']}:{source_row}"
                    )
                    stressed_net = finite_float(
                        row["value_b"], f"stressed:{source['path']}:{source_row}"
                    )
                    release = map_release(birth_server.date(), releases)
                    record_number += 1
                    lifecycles.append(
                        Lifecycle(
                            record_id=f"L{record_number:04d}",
                            source_path=source["path"],
                            source_birth_row=birth_row_number,
                            source_final_row=source_row,
                            birth_server=birth_server,
                            final_server=final_server,
                            period=source["period"],
                            component=component,
                            book=book,
                            state=release.state if release else UNAVAILABLE,
                            release_vintage=release.vintage if release else None,
                            release_date=release.release_date if release else None,
                            observation_date=release.observation_date if release else None,
                            initial_gscpi=release.value if release else None,
                            planned_risk=planned_risk,
                            actual_net=actual_net,
                            stressed_net=stressed_net,
                            stressed_r=stressed_net / planned_risk,
                            stop=int(reason == "DEAL_REASON_SL"),
                        )
                    )
        require(
            not open_by_component,
            f"unclosed births at end of {source['path']}: {sorted(open_by_component)}",
        )

    require(event_rows == 16477, f"unexpected event rows: {event_rows}")
    require(len(lifecycles) == 2233, f"unexpected lifecycles: {len(lifecycles)}")
    require(event_counts["OPEN"] == 1639, "unexpected OPEN count")
    require(event_counts["PASSIVE_FILL"] == 594, "unexpected PASSIVE_FILL count")
    require(event_counts["CLOSE"] == 2027, "unexpected CLOSE count")
    require(event_counts["EXTERNAL_CLOSE"] == 206, "unexpected EXTERNAL_CLOSE count")
    require(sum(item.stop for item in lifecycles) == 206, "unexpected stop count")
    require(
        math.isclose(
            sum(item.actual_net for item in lifecycles),
            444.19,
            rel_tol=0.0,
            abs_tol=1e-9,
        ),
        "unexpected actual net anchor",
    )
    require(
        math.isclose(
            sum(item.stressed_net for item in lifecycles),
            407.0477,
            rel_tol=0.0,
            abs_tol=1e-9,
        ),
        "unexpected stressed net anchor",
    )
    return lifecycles, event_counts, event_rows


def center_outcomes(rows: list[Lifecycle]) -> list[Lifecycle]:
    mapped = [row for row in rows if row.state in STATES]
    cells: dict[tuple[str, str], list[Lifecycle]] = defaultdict(list)
    for row in mapped:
        cells[(row.component, row.period)].append(row)
    centered: list[Lifecycle] = []
    for row in rows:
        if row.state not in STATES:
            centered.append(row)
            continue
        cell = cells[(row.component, row.period)]
        mean_r = statistics.fmean(item.stressed_r for item in cell)
        mean_stop = statistics.fmean(item.stop for item in cell)
        centered.append(
            replace(
                row,
                centered_stressed_r=row.stressed_r - mean_r,
                centered_stop=row.stop - mean_stop,
            )
        )
    return centered


def state_metrics(rows: list[Lifecycle], state: str) -> dict[str, Any]:
    selected = [row for row in rows if row.state == state]
    require(selected, f"empty state cell: {state}")
    require(
        all(
            row.centered_stressed_r is not None and row.centered_stop is not None
            for row in selected
        ),
        f"uncentered state cell: {state}",
    )
    return {
        "n": len(selected),
        "actual_net_usd": sum(row.actual_net for row in selected),
        "stressed_net_usd": sum(row.stressed_net for row in selected),
        "planned_risk_usd": sum(row.planned_risk for row in selected),
        "mean_stressed_r": statistics.fmean(row.stressed_r for row in selected),
        "stop_rate": statistics.fmean(row.stop for row in selected),
        "mean_centered_stressed_r": statistics.fmean(
            row.centered_stressed_r for row in selected
        ),
        "mean_centered_stop": statistics.fmean(row.centered_stop for row in selected),
    }


def contrast(rows: list[Lifecycle]) -> dict[str, Any]:
    above = state_metrics(rows, ABOVE)
    below = state_metrics(rows, BELOW)
    return {
        ABOVE: above,
        BELOW: below,
        "above_minus_below": {
            "raw_mean_stressed_r": above["mean_stressed_r"]
            - below["mean_stressed_r"],
            "raw_stop_rate": above["stop_rate"] - below["stop_rate"],
            "centered_stressed_r": above["mean_centered_stressed_r"]
            - below["mean_centered_stressed_r"],
            "centered_stop_rate": above["mean_centered_stop"]
            - below["mean_centered_stop"],
        },
    }


def direction(cell: dict[str, Any]) -> str:
    effect = cell["above_minus_below"]
    if effect["centered_stressed_r"] > 0.0 and effect["centered_stop_rate"] < 0.0:
        return "FAVORABLE_ABOVE_NORMAL"
    if effect["centered_stressed_r"] < 0.0 and effect["centered_stop_rate"] > 0.0:
        return "ADVERSE_ABOVE_NORMAL"
    return "NONCONCORDANT"


def breakout(
    rows: list[Lifecycle], field: str, values: Iterable[str]
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for value in values:
        selected = [row for row in rows if getattr(row, field) == value]
        states = Counter(row.state for row in selected)
        if states[ABOVE] == 0 or states[BELOW] == 0:
            output[value] = {
                "available": False,
                "state_counts": {ABOVE: states[ABOVE], BELOW: states[BELOW]},
            }
            continue
        cell = contrast(selected)
        cell["direction"] = direction(cell)
        output[value] = cell
    return output


def contribution_cap(
    rows: list[Lifecycle], field: str, values: Iterable[str]
) -> dict[str, Any]:
    above_total = sum(row.state == ABOVE for row in rows)
    below_total = sum(row.state == BELOW for row in rows)
    contributions: dict[str, float] = {}
    for value in values:
        selected = [row for row in rows if getattr(row, field) == value]
        above_rows = [row for row in selected if row.state == ABOVE]
        below_rows = [row for row in selected if row.state == BELOW]
        above_part = sum(row.centered_stressed_r for row in above_rows) / above_total
        below_part = sum(row.centered_stressed_r for row in below_rows) / below_total
        contributions[value] = above_part - below_part
    denominator = sum(abs(value) for value in contributions.values())
    shares = {
        key: (abs(value) / denominator if denominator > 0.0 else 0.0)
        for key, value in contributions.items()
    }
    return {
        "signed_contributions": contributions,
        "absolute_shares": shares,
        "maximum_absolute_share": max(shares.values()),
        "sum_matches_pooled": math.isclose(
            sum(contributions.values()),
            contrast(rows)["above_minus_below"]["centered_stressed_r"],
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
    }


def write_derived(rows: list[Lifecycle]) -> None:
    fields = [
        "record_id",
        "period",
        "component",
        "book",
        "birth_server",
        "final_server",
        "state",
        "release_vintage",
        "release_date",
        "observation_date",
        "initial_gscpi",
        "planned_risk_usd",
        "actual_net_usd",
        "stressed_net_usd",
        "stressed_r",
        "stop",
        "centered_stressed_r",
        "centered_stop",
        "source_path",
        "source_birth_row",
        "source_final_row",
    ]
    with DERIVED_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
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
                    "state": row.state,
                    "release_vintage": row.release_vintage or "",
                    "release_date": row.release_date.isoformat()
                    if row.release_date
                    else "",
                    "observation_date": row.observation_date.isoformat()
                    if row.observation_date
                    else "",
                    "initial_gscpi": ""
                    if row.initial_gscpi is None
                    else row.initial_gscpi,
                    "planned_risk_usd": row.planned_risk,
                    "actual_net_usd": row.actual_net,
                    "stressed_net_usd": row.stressed_net,
                    "stressed_r": row.stressed_r,
                    "stop": row.stop,
                    "centered_stressed_r": ""
                    if row.centered_stressed_r is None
                    else row.centered_stressed_r,
                    "centered_stop": ""
                    if row.centered_stop is None
                    else row.centered_stop,
                    "source_path": row.source_path,
                    "source_birth_row": row.source_birth_row,
                    "source_final_row": row.source_final_row,
                }
            )


def main() -> None:
    require(not RESULT_PATH.exists(), "frozen result already exists")
    require(not DERIVED_PATH.exists(), "frozen derived rows already exist")
    require(not CLOSURE_PATH.exists(), "frozen closure already exists")

    declaration = load_json(DECLARATION_PATH)
    require(declaration["outcomes_consumed"] is False, "declaration already consumed")
    declaration_sha = sha256_file(DECLARATION_PATH)
    require(
        declaration_sha
        == "CBD4A49E6EF4F01F59EA907654132F43A795EAEAB62AB29FDA9FDE6EC742BCB5",
        "declaration hash mismatch",
    )
    pins = verify_pins(declaration)
    releases = load_releases()
    lifecycles, event_counts, event_rows = reconstruct_lifecycles(
        declaration, releases
    )
    lifecycles = center_outcomes(lifecycles)

    state_counts = Counter(row.state for row in lifecycles)
    require(
        state_counts == Counter({BELOW: 1252, ABOVE: 972, UNAVAILABLE: 9}),
        f"unexpected state counts: {state_counts}",
    )
    expected_period_states = {
        "P1_2022H2_2023": Counter({BELOW: 407, ABOVE: 353, UNAVAILABLE: 9}),
        "P2_2024": Counter({BELOW: 415, ABOVE: 139}),
        "P3_2025": Counter({BELOW: 422, ABOVE: 132}),
        "P4_2026_YTD": Counter({ABOVE: 348, BELOW: 8}),
    }
    for period, expected in expected_period_states.items():
        actual = Counter(row.state for row in lifecycles if row.period == period)
        require(actual == expected, f"unexpected {period} state counts: {actual}")
    for period in CONFIRMATORY_PERIODS:
        for book in ("US30_BOOK", "US100_BOOK"):
            for state in STATES:
                cell_count = sum(
                    row.period == period and row.book == book and row.state == state
                    for row in lifecycles
                )
                require(
                    cell_count >= 20,
                    f"thin confirmatory period-book-state cell: {period}:{book}:{state}:{cell_count}",
                )
    for component in ("RC16", "RC4", "Cross", "Pressure", "Return", "Passive"):
        for state in STATES:
            cell_count = sum(
                row.component == component and row.state == state for row in lifecycles
            )
            require(
                cell_count >= 15,
                f"thin pooled component-state cell: {component}:{state}:{cell_count}",
            )
    confirmatory = [
        row
        for row in lifecycles
        if row.period in CONFIRMATORY_PERIODS and row.state in STATES
    ]
    full_mapped = [row for row in lifecycles if row.state in STATES]
    primary = contrast(confirmatory)
    full = contrast(full_mapped)

    books = breakout(confirmatory, "book", ("US30_BOOK", "US100_BOOK"))
    periods = breakout(full_mapped, "period", ALL_PERIODS)
    components = breakout(
        confirmatory,
        "component",
        ("RC16", "RC4", "Cross", "Pressure", "Return", "Passive"),
    )
    book_directions = Counter(cell["direction"] for cell in books.values())
    period_directions = Counter(
        periods[period]["direction"] for period in CONFIRMATORY_PERIODS
    )
    component_directions = Counter(
        cell["direction"] for cell in components.values()
    )
    period_contribution = contribution_cap(
        confirmatory, "period", CONFIRMATORY_PERIODS
    )
    component_contribution = contribution_cap(
        confirmatory,
        "component",
        ("RC16", "RC4", "Cross", "Pressure", "Return", "Passive"),
    )
    require(period_contribution["sum_matches_pooled"], "period contribution mismatch")
    require(
        component_contribution["sum_matches_pooled"],
        "component contribution mismatch",
    )

    effect_r = primary["above_minus_below"]["centered_stressed_r"]
    effect_stop = primary["above_minus_below"]["centered_stop_rate"]
    favorable = {
        "centered_stressed_r_at_least_0_10": effect_r >= 0.10,
        "centered_stop_rate_at_most_minus_0_05": effect_stop <= -0.05,
        "both_books": book_directions["FAVORABLE_ABOVE_NORMAL"] == 2,
        "at_least_two_of_three_periods": period_directions[
            "FAVORABLE_ABOVE_NORMAL"
        ]
        >= 2,
        "at_least_four_components": component_directions[
            "FAVORABLE_ABOVE_NORMAL"
        ]
        >= 4,
        "period_contribution_cap_0_60": period_contribution[
            "maximum_absolute_share"
        ]
        <= 0.60,
        "component_contribution_cap_0_45": component_contribution[
            "maximum_absolute_share"
        ]
        <= 0.45,
    }
    favorable["passed"] = all(favorable.values())
    adverse = {
        "centered_stressed_r_at_most_minus_0_10": effect_r <= -0.10,
        "centered_stop_rate_at_least_0_05": effect_stop >= 0.05,
        "both_books": book_directions["ADVERSE_ABOVE_NORMAL"] == 2,
        "at_least_two_of_three_periods": period_directions[
            "ADVERSE_ABOVE_NORMAL"
        ]
        >= 2,
        "at_least_four_components": component_directions[
            "ADVERSE_ABOVE_NORMAL"
        ]
        >= 4,
        "period_contribution_cap_0_60": period_contribution[
            "maximum_absolute_share"
        ]
        <= 0.60,
        "component_contribution_cap_0_45": component_contribution[
            "maximum_absolute_share"
        ]
        <= 0.45,
    }
    adverse["passed"] = all(adverse.values())
    strong_null = {
        "absolute_centered_stressed_r_below_0_05": abs(effect_r) < 0.05,
        "absolute_centered_stop_rate_below_0_025": abs(effect_stop) < 0.025,
        "favorable_period_breadth_at_most_1": period_directions[
            "FAVORABLE_ABOVE_NORMAL"
        ]
        <= 1,
        "adverse_period_breadth_at_most_1": period_directions[
            "ADVERSE_ABOVE_NORMAL"
        ]
        <= 1,
        "favorable_component_breadth_at_most_3": component_directions[
            "FAVORABLE_ABOVE_NORMAL"
        ]
        <= 3,
        "adverse_component_breadth_at_most_3": component_directions[
            "ADVERSE_ABOVE_NORMAL"
        ]
        <= 3,
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

    result = {
        "schema": "zeta-next-initial-release-gscpi-above-normal-portfolio-state-result-v1",
        "created_at_local": "2026-08-30",
        "status": "COMPLETE_VALID_ECONOMIC_AGGREGATION",
        "unit": declaration["unit"],
        "macro_program": declaration["macro_program"],
        "declaration_sha256": declaration_sha,
        "verdict": verdict,
        "integrity": {
            "passed": True,
            "pins": pins,
            "event_rows": event_rows,
            "event_counts": dict(sorted(event_counts.items())),
            "lifecycles": len(lifecycles),
            "mapped_lifecycles": len(full_mapped),
            "unavailable_lifecycles": state_counts[UNAVAILABLE],
            "stops": sum(row.stop for row in lifecycles),
            "actual_net_usd": sum(row.actual_net for row in lifecycles),
            "stressed_net_usd": sum(row.stressed_net for row in lifecycles),
            "initial_release_rows": len(releases),
            "same_release_date_excluded": True,
        },
        "state_counts": {
            ABOVE: state_counts[ABOVE],
            BELOW: state_counts[BELOW],
            UNAVAILABLE: state_counts[UNAVAILABLE],
        },
        "confirmatory_periods": list(CONFIRMATORY_PERIODS),
        "descriptive_period": "P4_2026_YTD",
        "confirmatory_primary": primary,
        "full_horizon_descriptive": full,
        "breakouts": {
            "books_confirmatory": books,
            "periods": periods,
            "components_confirmatory": components,
        },
        "direction_breadth": {
            "books": dict(book_directions),
            "confirmatory_periods": dict(period_directions),
            "components": dict(component_directions),
        },
        "contribution_caps": {
            "periods": period_contribution,
            "components": component_contribution,
        },
        "gates": {
            "favorable": favorable,
            "adverse": adverse,
            "strong_null": strong_null,
        },
        "selected_candidate": None,
        "retained_lab_question": (
            "one_nonautomatic_whole_portfolio_gscpi_state_question"
            if favorable["passed"] or adverse["passed"]
            else None
        ),
        "optimization_candidate": None,
        "mt5_escalation": False,
        "successful_fixed_aggregations": 1,
        "metric_reruns": 0,
        "mql_or_tester_runs": 0,
        "program_6_opened": False,
        "broker_or_account_state_queried": False,
        "live_surface": "UNTOUCHED",
    }
    write_derived(lifecycles)
    result["derived_rows"] = {
        "path": DERIVED_PATH.relative_to(REPO).as_posix(),
        "bytes": DERIVED_PATH.stat().st_size,
        "sha256": sha256_file(DERIVED_PATH),
        "rows": len(lifecycles),
    }
    write_json(RESULT_PATH, result)
    result_sha = sha256_file(RESULT_PATH)

    closure = {
        "schema": "zeta-next-initial-release-gscpi-above-normal-portfolio-state-closure-v1",
        "created_at_local": "2026-08-30",
        "status": "CLOSED_VALID",
        "unit": declaration["unit"],
        "macro_program": declaration["macro_program"],
        "verdict": verdict,
        "confirmatory_primary_effect": primary["above_minus_below"],
        "full_horizon_descriptive_effect": full["above_minus_below"],
        "state_counts": result["state_counts"],
        "direction_breadth": result["direction_breadth"],
        "gates": result["gates"],
        "declaration_sha256": declaration_sha,
        "result_sha256": result_sha,
        "derived_rows_sha256": result["derived_rows"]["sha256"],
        "selected_candidate": None,
        "retained_seed": result["retained_lab_question"],
        "optimization_candidate": None,
        "mt5_escalation": False,
        "same_family_rescue": False,
        "automatic_followup_opened": False,
        "program_6_opened": False,
        "broker_or_account_state_queried": False,
        "promotion": "none",
        "live_surface": "UNTOUCHED",
        "goal_status": "active_not_complete",
        "next": "update_state_close_unit_116_recompare_whole_map_and_return_to_optimization_boundary",
    }
    write_json(CLOSURE_PATH, closure)
    print(json.dumps(closure, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
