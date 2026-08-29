#!/usr/bin/env python3
"""One frozen source-free aggregation for Frontier Unit 104.

This is a research aggregation, not a validator, test harness, trading program,
or reusable CLI product.
"""

from __future__ import annotations

import bisect
import csv
import hashlib
import json
import math
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[4]
FAMILY = REPO / "lab/research/prior-broad-dollar-portfolio-state-v1"
EVIDENCE = FAMILY / "evidence"
DECLARATION_PATH = EVIDENCE / "PRIOR_BROAD_DOLLAR_PORTFOLIO_STATE_DECLARATION_V1.json"
TRACKED_RESULT_PATH = EVIDENCE / "PRIOR_BROAD_DOLLAR_PORTFOLIO_STATE_RESULT_V1.json"
RAW_ROOT = REPO / "lab/artifacts/raw/prior-broad-dollar-portfolio-state-v1"
INPUT_ROOT = RAW_ROOT / "input"
RAW_RESULT_PATH = RAW_ROOT / "output/proxy-result.json"

DOLLAR_CSV = "FED_H10_NOMINAL_BROAD_DOLLAR_20220601_20260821.csv"
DOLLAR_HTML = "FED_H10_NOMINAL_BROAD_DOLLAR_DAILY_20260824.html"
SCHEDULE_HTML = "FED_H10_RELEASE_SCHEDULE_20260824.html"
SELECTION_CSV = "PAIRED_MONTH_SELECTION_RESEARCH_LIFECYCLES.csv"
FORWARD_CSV = "PAIRED_MONTH_FORWARD_RESEARCH_LIFECYCLES.csv"
ANCHOR_JSON = "PAIRED_MONTH_STABILITY_MT5_RESULT_V1.json"

STRENGTHENING = "STRENGTHENING"
NONSTRENGTHENING = "NONSTRENGTHENING"
STATES = (NONSTRENGTHENING, STRENGTHENING)

COMPONENTS = {
    "ZT-H1-US100-CROSS-IN-14b72317b7": "Cross",
    "ZT-H1-US30-RETURN-I-c870a788ec": "Return",
    "ZT-M30-US30-INTRADAY-R-2eb111fc46": "Pressure",
    "ZT-M30-US30-RANGE-COMP-61f61deaba": "Range61",
    "ZT-M30-US30-RANGE-COMP-64efb16616": "Range64",
}

LIFECYCLE_COLUMNS = [
    "schema", "record_id", "utc", "server_time", "macro_join_utc_minute",
    "release_id", "execution_version", "portfolio_id", "event",
    "component_id", "symbol", "position_identifier", "entry_time_server",
    "segment_started_server", "direction", "volume", "entry_price",
    "entry_feature", "stop_loss", "planned_risk_usd", "entry_spread_price",
    "entry_transaction_cost", "entry_adverse_slippage", "entry_cost_known",
    "last_mark_profit_usd", "last_mark_r", "peak_mark_profit_usd",
    "peak_mark_r", "peak_time_server", "trough_mark_profit_usd",
    "trough_mark_r", "trough_time_server", "maximum_giveback_usd",
    "maximum_giveback_r", "mark_samples", "entry_active_mask",
    "entry_reserved_mask", "entry_active_slots", "entry_aggregate_risk_usd",
    "entry_us30_risk_usd", "entry_us100_risk_usd",
    "entry_aggregate_headroom_usd", "prior_signal_direction",
    "signal_relation", "rc4_sell_warning", "first_peer_component",
    "first_peer_exit_server", "exit_reason", "exit_class", "exit_price",
    "actual_net_usd", "stressed_net_usd", "current_active_mask",
    "current_reserved_mask", "current_us30_risk_usd",
    "current_us100_risk_usd", "partial_observation",
    "research_state_sequence", "research_dropped_records", "detail",
]


@dataclass(frozen=True)
class WeeklyState:
    reference_date: date
    value: float
    prior_value: float
    state: str


@dataclass(frozen=True)
class Lifecycle:
    source: str
    position_identifier: str
    birth_date: date
    period: str
    p1_split: str | None
    state: str
    state_reference_date: date
    state_age_days: int
    component: str
    symbol: str
    planned_risk: float
    actual_net: float
    stressed_net: float
    stressed_r: float
    stop: int


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def byte_count(path: Path) -> int:
    return path.stat().st_size


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    path.write_text(serialized, encoding="utf-8", newline="\n")


def canonical_manifest(paths: Iterable[Path]) -> str:
    lines = [
        f"{path.name}|{byte_count(path)}|{sha256_file(path)}"
        for path in sorted(paths, key=lambda item: item.name)
    ]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest().upper()


def parse_date(text: str) -> date:
    return date.fromisoformat(text)


def parse_server_date(text: str) -> date:
    return datetime.strptime(text[:10], "%Y.%m.%d").date()


def finite_float(value: str, context: str) -> float:
    parsed = float(value)
    require(math.isfinite(parsed), f"nonfinite number: {context}")
    return parsed


def close_enough(left: float, right: float, tolerance: float = 1e-9) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=tolerance)


def period_for(day: date) -> tuple[str, str | None]:
    if date(2022, 8, 1) <= day <= date(2023, 12, 31):
        split = "P1_2022H2" if day.year == 2022 else "P1_2023"
        return "P1", split
    if date(2024, 1, 1) <= day <= date(2024, 12, 31):
        return "P2", None
    if date(2025, 1, 1) <= day <= date(2025, 12, 31):
        return "P3", None
    if date(2026, 1, 1) <= day <= date(2026, 5, 31):
        return "P4", None
    if date(2026, 6, 1) <= day <= date(2026, 7, 31):
        return "P5", None
    raise RuntimeError(f"birth outside fixed periods: {day.isoformat()}")


def load_daily_dollar(path: Path) -> list[tuple[date, float]]:
    rows: list[tuple[date, float]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        require(
            reader.fieldnames == ["date", "nominal_broad_dollar_index"],
            f"unexpected dollar columns: {reader.fieldnames}",
        )
        previous: date | None = None
        for row_number, row in enumerate(reader, start=2):
            day = parse_date(row["date"])
            value = finite_float(row["nominal_broad_dollar_index"], f"dollar:{row_number}")
            require(value > 0.0, f"nonpositive dollar value:{row_number}")
            require(previous is None or day > previous, f"non-increasing dollar date:{row_number}")
            previous = day
            rows.append((day, value))
    require(len(rows) == 1057, f"unexpected dollar row count: {len(rows)}")
    require(rows[0] == (date(2022, 6, 1), 118.6954), "unexpected first dollar row")
    require(rows[-1] == (date(2026, 8, 21), 118.0628), "unexpected last dollar row")
    return rows


def build_weekly_states(daily: list[tuple[date, float]]) -> tuple[list[WeeklyState], dict[str, Any]]:
    week_last: dict[tuple[int, int], tuple[date, float]] = {}
    for day, value in daily:
        iso = day.isocalendar()
        week_last[(iso.year, iso.week)] = (day, value)
    weekly = sorted(week_last.values())
    require(len(weekly) == 221, f"unexpected weekly count: {len(weekly)}")
    require(weekly[0] == (date(2022, 6, 3), 118.2153), "unexpected first weekly row")
    require(weekly[-1] == (date(2026, 8, 21), 118.0628), "unexpected last weekly row")
    states: list[WeeklyState] = []
    flat = 0
    for index in range(1, len(weekly)):
        current_day, current_value = weekly[index]
        prior_value = weekly[index - 1][1]
        difference = current_value - prior_value
        if difference > 0.0:
            state = STRENGTHENING
        elif difference < 0.0:
            state = NONSTRENGTHENING
        else:
            flat += 1
            continue
        states.append(WeeklyState(current_day, current_value, prior_value, state))
    counts = Counter(item.state for item in states)
    require(len(states) == 220, f"unexpected weekly state count: {len(states)}")
    require(counts[STRENGTHENING] == 111, "unexpected strengthening weeks")
    require(counts[NONSTRENGTHENING] == 109, "unexpected nonstrengthening weeks")
    require(flat == 0, "unexpected flat weekly state")
    return states, {
        "daily_rows": len(daily),
        "weekly_records": len(weekly),
        "weekly_states": len(states),
        "strengthening_weeks": counts[STRENGTHENING],
        "nonstrengthening_weeks": counts[NONSTRENGTHENING],
        "flat_weeks": flat,
        "first_weekly_reference": weekly[0][0].isoformat(),
        "last_weekly_reference": weekly[-1][0].isoformat(),
    }


def state_for_birth(birth_day: date, states: list[WeeklyState]) -> WeeklyState:
    cutoff = birth_day - timedelta(days=7)
    references = [item.reference_date for item in states]
    index = bisect.bisect_right(references, cutoff) - 1
    require(index >= 0, f"no causal weekly state for birth {birth_day.isoformat()}")
    return states[index]


def load_event_rows(path: Path) -> tuple[list[dict[str, str]], Counter[str]]:
    rows: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames == LIFECYCLE_COLUMNS, f"unexpected lifecycle columns: {path.name}")
        for row in reader:
            counts[row["event"]] += 1
            rows.append(row)
    return rows, counts


def reconstruct_lifecycles(
    path: Path,
    states: list[WeeklyState],
) -> tuple[list[Lifecycle], Counter[str]]:
    rows, event_counts = load_event_rows(path)
    births: dict[str, dict[str, str]] = {}
    closes: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row["position_identifier"]
        if row["event"] == "BIRTH":
            require(key not in births, f"duplicate birth {path.name}:{key}")
            births[key] = row
        elif row["event"] == "CLOSE":
            require(key not in closes, f"duplicate close {path.name}:{key}")
            closes[key] = row
        elif row["event"] != "FIRST_PEER_NATURAL_EXIT":
            raise RuntimeError(f"unexpected event {path.name}:{row['event']}")
    require(set(births) == set(closes), f"unmatched lifecycle keys: {path.name}")
    lifecycles: list[Lifecycle] = []
    for key, birth in births.items():
        close = closes[key]
        for field in ("component_id", "symbol", "entry_time_server"):
            require(birth[field] == close[field], f"birth/close mismatch {path.name}:{key}:{field}")
        require(birth["component_id"] in COMPONENTS, f"unknown component {birth['component_id']}")
        birth_day = parse_server_date(birth["server_time"])
        period, p1_split = period_for(birth_day)
        weekly_state = state_for_birth(birth_day, states)
        age = (birth_day - weekly_state.reference_date).days
        require(7 <= age <= 14, f"causal state age outside 7..14: {path.name}:{key}:{age}")
        planned_risk = finite_float(birth["planned_risk_usd"], f"risk:{path.name}:{key}")
        require(planned_risk > 0.0, f"nonpositive planned risk:{path.name}:{key}")
        require(
            close_enough(
                planned_risk,
                finite_float(close["planned_risk_usd"], f"close-risk:{path.name}:{key}"),
            ),
            f"birth/close planned risk mismatch:{path.name}:{key}",
        )
        actual = finite_float(close["actual_net_usd"], f"actual:{path.name}:{key}")
        stressed = finite_float(close["stressed_net_usd"], f"stressed:{path.name}:{key}")
        stop = int(close["exit_reason"] == "DEAL_REASON_SL")
        require(
            close["exit_reason"] in {"DEAL_REASON_SL", "DEAL_REASON_EXPERT"},
            f"unexpected close reason:{path.name}:{key}:{close['exit_reason']}",
        )
        require(
            (stop == 1 and close["exit_class"] == "STOP")
            or (stop == 0 and close["exit_class"] == "NATIVE"),
            f"unexpected close class:{path.name}:{key}:{close['exit_class']}",
        )
        lifecycles.append(
            Lifecycle(
                source=path.name,
                position_identifier=key,
                birth_date=birth_day,
                period=period,
                p1_split=p1_split,
                state=weekly_state.state,
                state_reference_date=weekly_state.reference_date,
                state_age_days=age,
                component=COMPONENTS[birth["component_id"]],
                symbol=birth["symbol"],
                planned_risk=planned_risk,
                actual_net=actual,
                stressed_net=stressed,
                stressed_r=stressed / planned_risk,
                stop=stop,
            )
        )
    lifecycles.sort(key=lambda item: (item.birth_date, item.source, int(item.position_identifier)))
    return lifecycles, event_counts


def structural_cell(rows: list[Lifecycle]) -> dict[str, Any]:
    state_counts = Counter(item.state for item in rows)
    return {
        "births": len(rows),
        "birth_dates": len({item.birth_date for item in rows}),
        "state_counts": {
            NONSTRENGTHENING: state_counts[NONSTRENGTHENING],
            STRENGTHENING: state_counts[STRENGTHENING],
        },
        "reference_weeks": len({item.state_reference_date for item in rows}),
        "symbols": {
            symbol: {
                state: sum(1 for item in rows if item.symbol == symbol and item.state == state)
                for state in STATES
            }
            for symbol in ("US100", "US30")
        },
        "components": {
            component: {
                state: sum(1 for item in rows if item.component == component and item.state == state)
                for state in STATES
            }
            for component in ("Cross", "Return", "Pressure", "Range61", "Range64")
        },
    }


def verify_structural_anchors(rows: list[Lifecycle]) -> dict[str, Any]:
    anchors = {period: structural_cell([item for item in rows if item.period == period]) for period in ("P1", "P2", "P3", "P4", "P5")}
    anchors["P1_2022H2"] = structural_cell([item for item in rows if item.p1_split == "P1_2022H2"])
    anchors["P1_2023"] = structural_cell([item for item in rows if item.p1_split == "P1_2023"])
    expected = {
        "P1": (516, 336, 237, 279, 74),
        "P2": (357, 235, 153, 204, 53),
        "P3": (388, 235, 211, 177, 53),
        "P4": (167, 102, 98, 69, 22),
        "P5": (54, 40, 23, 31, 10),
        "P1_2022H2": (149, 99, 74, 75, None),
        "P1_2023": (367, 237, 163, 204, None),
    }
    for key, values in expected.items():
        cell = anchors[key]
        require(cell["births"] == values[0], f"unexpected {key} births")
        require(cell["birth_dates"] == values[1], f"unexpected {key} dates")
        require(cell["state_counts"][NONSTRENGTHENING] == values[2], f"unexpected {key} nonstrengthening")
        require(cell["state_counts"][STRENGTHENING] == values[3], f"unexpected {key} strengthening")
        if values[4] is not None:
            require(cell["reference_weeks"] == values[4], f"unexpected {key} reference weeks")
    expected_books = {
        "P1": {"US100": (120, 135), "US30": (117, 144)},
        "P2": {"US100": (69, 91), "US30": (84, 113)},
        "P3": {"US100": (98, 70), "US30": (113, 107)},
        "P4": {"US100": (48, 29), "US30": (50, 40)},
        "P5": {"US100": (14, 14), "US30": (9, 17)},
        "P1_2022H2": {"US100": (40, 34), "US30": (34, 41)},
        "P1_2023": {"US100": (80, 101), "US30": (83, 103)},
    }
    expected_components = {
        "P1": {"Cross": (120, 135), "Return": (46, 52), "Pressure": (13, 20), "Range61": (38, 39), "Range64": (20, 33)},
        "P2": {"Cross": (69, 91), "Return": (22, 31), "Pressure": (6, 13), "Range61": (32, 40), "Range64": (24, 29)},
        "P3": {"Cross": (98, 70), "Return": (26, 25), "Pressure": (9, 13), "Range61": (45, 34), "Range64": (33, 35)},
        "P4": {"Cross": (48, 29), "Return": (11, 13), "Pressure": (8, 6), "Range61": (20, 10), "Range64": (11, 11)},
        "P5": {"Cross": (14, 14), "Return": (0, 5), "Pressure": (1, 4), "Range61": (3, 6), "Range64": (5, 2)},
    }
    for key, books in expected_books.items():
        for book, counts in books.items():
            actual = anchors[key]["symbols"][book]
            require((actual[NONSTRENGTHENING], actual[STRENGTHENING]) == counts, f"unexpected {key} {book} counts")
    for key, components in expected_components.items():
        for component, counts in components.items():
            actual = anchors[key]["components"][component]
            require((actual[NONSTRENGTHENING], actual[STRENGTHENING]) == counts, f"unexpected {key} {component} counts")
    return anchors


def verify_anchor_result(
    anchor: dict[str, Any],
    selection: list[Lifecycle],
    forward: list[Lifecycle],
) -> dict[str, Any]:
    expected = {
        "selection": (1428, 5786.63, 5477.524, 130),
        "forward": (54, 32.74, 30.626, 17),
    }
    observed: dict[str, Any] = {}
    for name, rows in (("selection", selection), ("forward", forward)):
        source = anchor[name]
        count, actual, stressed, stops = expected[name]
        require(len(rows) == count == source["closed_lifecycles"], f"{name} lifecycle count mismatch")
        require(close_enough(sum(item.actual_net for item in rows), actual, 1e-8), f"{name} actual sum mismatch")
        require(close_enough(sum(item.stressed_net for item in rows), stressed, 1e-8), f"{name} stressed sum mismatch")
        require(sum(item.stop for item in rows) == stops == source["stop_loss_exits"], f"{name} stop count mismatch")
        require(close_enough(source["actual_net_usd"], actual), f"{name} source actual mismatch")
        require(close_enough(source["stressed_2x_cost_net_usd"], stressed), f"{name} source stressed mismatch")
        observed[name] = {
            "closed_lifecycles": len(rows),
            "actual_net_usd": sum(item.actual_net for item in rows),
            "stressed_net_usd": sum(item.stressed_net for item in rows),
            "stop_loss_exits": sum(item.stop for item in rows),
        }
    return observed


def state_metrics(rows: list[Lifecycle]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for state in STATES:
        subset = [item for item in rows if item.state == state]
        require(subset, f"empty state cell: {state}")
        stressed_rs = [item.stressed_r for item in subset]
        result[state] = {
            "count": len(subset),
            "planned_risk_usd": sum(item.planned_risk for item in subset),
            "actual_net_usd": sum(item.actual_net for item in subset),
            "stressed_net_usd": sum(item.stressed_net for item in subset),
            "mean_stressed_r": statistics.fmean(stressed_rs),
            "median_stressed_r": statistics.median(stressed_rs),
            "stop_count": sum(item.stop for item in subset),
            "stop_rate": statistics.fmean(item.stop for item in subset),
        }
    result["strengthening_minus_nonstrengthening"] = {
        "mean_stressed_r": result[STRENGTHENING]["mean_stressed_r"] - result[NONSTRENGTHENING]["mean_stressed_r"],
        "stop_rate": result[STRENGTHENING]["stop_rate"] - result[NONSTRENGTHENING]["stop_rate"],
    }
    return result


def concentration_share(values: dict[str, float]) -> float:
    losses = {key: max(0.0, -value) for key, value in values.items()}
    total = sum(losses.values())
    return max(losses.values()) / total if total > 0.0 else 1.0


def p1_economics(rows: list[Lifecycle], declaration: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    p1 = [item for item in rows if item.period == "P1"]
    pooled = state_metrics(p1)
    splits = {
        split: state_metrics([item for item in p1 if item.p1_split == split])
        for split in ("P1_2022H2", "P1_2023")
    }
    books = {
        symbol: state_metrics([item for item in p1 if item.symbol == symbol])
        for symbol in ("US30", "US100")
    }
    components = {
        component: state_metrics([item for item in p1 if item.component == component])
        for component in ("Cross", "Return", "Pressure", "Range61", "Range64")
    }
    thresholds = declaration["fixed_p1_discovery_gate"]
    negative_components = sum(
        metrics[STRENGTHENING]["stressed_net_usd"] < 0.0
        for metrics in components.values()
    )
    checks = [
        ("strengthening_actual_net_negative", pooled[STRENGTHENING]["actual_net_usd"] < 0.0),
        ("strengthening_stressed_net_negative", pooled[STRENGTHENING]["stressed_net_usd"] < 0.0),
        ("mean_stressed_r_effect_at_most_minus_0_10", pooled["strengthening_minus_nonstrengthening"]["mean_stressed_r"] <= thresholds["maximum_mean_stressed_r_effect"]),
        ("stop_rate_effect_at_least_plus_0_05", pooled["strengthening_minus_nonstrengthening"]["stop_rate"] >= thresholds["minimum_stop_rate_effect"]),
        ("p1_2022h2_strengthening_stressed_net_negative", splits["P1_2022H2"][STRENGTHENING]["stressed_net_usd"] < 0.0),
        ("p1_2023_strengthening_stressed_net_negative", splits["P1_2023"][STRENGTHENING]["stressed_net_usd"] < 0.0),
        ("us30_strengthening_stressed_net_negative", books["US30"][STRENGTHENING]["stressed_net_usd"] < 0.0),
        ("us100_strengthening_stressed_net_negative", books["US100"][STRENGTHENING]["stressed_net_usd"] < 0.0),
        ("at_least_four_components_strengthening_stressed_net_negative", negative_components >= thresholds["minimum_negative_components"]),
    ]
    gates = [{"name": name, "passed": passed} for name, passed in checks]
    return {
        "pooled": pooled,
        "calendar_splits": splits,
        "books": books,
        "components": components,
        "negative_component_count": negative_components,
        "passed_gate_count": sum(item[1] for item in checks),
        "total_gate_count": len(checks),
        "all_gates_passed": all(item[1] for item in checks),
    }, gates, all(item[1] for item in checks)


def later_economics(rows: list[Lifecycle], declaration: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    periods = {
        period: state_metrics([item for item in rows if item.period == period])
        for period in ("P2", "P3", "P4", "P5")
    }
    pooled_confirmation = state_metrics([item for item in rows if item.period in {"P2", "P3", "P4"}])
    full = state_metrics(rows)
    books = {
        symbol: state_metrics([item for item in rows if item.symbol == symbol])
        for symbol in ("US30", "US100")
    }
    components = {
        component: state_metrics([item for item in rows if item.component == component])
        for component in ("Cross", "Return", "Pressure", "Range61", "Range64")
    }
    thresholds = declaration["fixed_confirmation_latest_and_full_gate"]
    negative_components = sum(
        metrics[STRENGTHENING]["stressed_net_usd"] < 0.0
        for metrics in components.values()
    )
    period_losses = {
        period: state_metrics([item for item in rows if item.period == period])[STRENGTHENING]["stressed_net_usd"]
        for period in ("P1", "P2", "P3", "P4", "P5")
    }
    component_losses = {
        component: metrics[STRENGTHENING]["stressed_net_usd"]
        for component, metrics in components.items()
    }
    period_concentration = concentration_share(period_losses)
    component_concentration = concentration_share(component_losses)
    checks: list[tuple[str, bool]] = []
    for period in ("P2", "P3", "P4"):
        checks.extend([
            (f"{period.lower()}_strengthening_actual_net_negative", periods[period][STRENGTHENING]["actual_net_usd"] < 0.0),
            (f"{period.lower()}_strengthening_stressed_net_negative", periods[period][STRENGTHENING]["stressed_net_usd"] < 0.0),
        ])
    checks.extend([
        ("pooled_p2_p4_strengthening_actual_net_negative", pooled_confirmation[STRENGTHENING]["actual_net_usd"] < 0.0),
        ("pooled_p2_p4_strengthening_stressed_net_negative", pooled_confirmation[STRENGTHENING]["stressed_net_usd"] < 0.0),
        ("pooled_p2_p4_mean_stressed_r_effect_at_most_minus_0_05", pooled_confirmation["strengthening_minus_nonstrengthening"]["mean_stressed_r"] <= thresholds["maximum_confirmation_mean_stressed_r_effect"]),
        ("pooled_p2_p4_stop_rate_effect_at_least_plus_0_025", pooled_confirmation["strengthening_minus_nonstrengthening"]["stop_rate"] >= thresholds["minimum_confirmation_stop_rate_effect"]),
        ("p5_strengthening_actual_net_nonpositive", periods["P5"][STRENGTHENING]["actual_net_usd"] <= 0.0),
        ("p5_strengthening_stressed_net_nonpositive", periods["P5"][STRENGTHENING]["stressed_net_usd"] <= 0.0),
        ("p5_mean_stressed_r_effect_nonpositive", periods["P5"]["strengthening_minus_nonstrengthening"]["mean_stressed_r"] <= 0.0),
        ("p5_stop_rate_effect_nonnegative", periods["P5"]["strengthening_minus_nonstrengthening"]["stop_rate"] >= 0.0),
        ("full_strengthening_actual_net_negative", full[STRENGTHENING]["actual_net_usd"] < 0.0),
        ("full_strengthening_stressed_net_negative", full[STRENGTHENING]["stressed_net_usd"] < 0.0),
        ("full_us30_strengthening_stressed_net_negative", books["US30"][STRENGTHENING]["stressed_net_usd"] < 0.0),
        ("full_us100_strengthening_stressed_net_negative", books["US100"][STRENGTHENING]["stressed_net_usd"] < 0.0),
        ("full_at_least_four_components_strengthening_stressed_net_negative", negative_components >= thresholds["minimum_negative_components"]),
        ("maximum_avoided_loss_period_share", period_concentration <= thresholds["maximum_period_loss_concentration"]),
        ("maximum_avoided_loss_component_share", component_concentration <= thresholds["maximum_component_loss_concentration"]),
    ])
    gates = [{"name": name, "passed": passed} for name, passed in checks]
    return {
        "periods": periods,
        "pooled_P2_P4": pooled_confirmation,
        "full": full,
        "full_books": books,
        "full_components": components,
        "negative_component_count": negative_components,
        "strengthening_stressed_net_by_period": period_losses,
        "strengthening_stressed_net_by_component": component_losses,
        "maximum_avoided_loss_period_share": period_concentration,
        "maximum_avoided_loss_component_share": component_concentration,
        "passed_gate_count": sum(item[1] for item in checks),
        "total_gate_count": len(checks),
        "all_gates_passed": all(item[1] for item in checks),
    }, gates, all(item[1] for item in checks)


def main() -> None:
    started = time.perf_counter()
    declaration = load_json(DECLARATION_PATH)
    require(declaration["status"] == "UNIT_104_DECLARATION_FROZEN_OUTCOMES_UNOPENED", "unexpected declaration status")
    require(declaration["outcomes_consumed"] is False, "declaration already consumed outcomes")

    input_paths = [INPUT_ROOT / item["name"] for item in declaration["immutable_inputs"]["files"]]
    require(all(path.is_file() for path in input_paths), "missing immutable input")
    for item, path in zip(declaration["immutable_inputs"]["files"], input_paths):
        require(path.name == item["name"], f"input order mismatch: {path.name}")
        require(byte_count(path) == item["bytes"], f"byte mismatch: {path.name}")
        require(sha256_file(path) == item["sha256"], f"hash mismatch: {path.name}")
    require(canonical_manifest(input_paths) == declaration["immutable_inputs"]["manifest_sha256"], "input manifest mismatch")
    require(byte_count(Path(__file__)) == declaration["implementation"]["script_bytes"], "script byte mismatch")
    require(sha256_file(Path(__file__)) == declaration["implementation"]["script_sha256"], "script hash mismatch")

    dollar_html = (INPUT_ROOT / DOLLAR_HTML).read_text(encoding="utf-8", errors="replace")
    schedule_html = (INPUT_ROOT / SCHEDULE_HTML).read_text(encoding="utf-8", errors="replace")
    require("Release Date: Monday, August 24, 2026" in dollar_html, "official release date semantic mismatch")
    require("Nominal Broad Dollar Index - Daily Index" in dollar_html, "official data title semantic mismatch")
    require("On Mondays at 4:15 p.m." in schedule_html, "official schedule time semantic mismatch")
    require("for the previous business week" in schedule_html, "official schedule vintage semantic mismatch")
    require("following business day" in schedule_html, "official holiday schedule semantic mismatch")

    daily = load_daily_dollar(INPUT_ROOT / DOLLAR_CSV)
    weekly_states, dollar_structure = build_weekly_states(daily)
    selection, selection_events = reconstruct_lifecycles(INPUT_ROOT / SELECTION_CSV, weekly_states)
    forward, forward_events = reconstruct_lifecycles(INPUT_ROOT / FORWARD_CSV, weekly_states)
    require(selection_events == Counter({"BIRTH": 1428, "CLOSE": 1428, "FIRST_PEER_NATURAL_EXIT": 431}), "selection event-count mismatch")
    require(forward_events == Counter({"BIRTH": 54, "CLOSE": 54, "FIRST_PEER_NATURAL_EXIT": 7}), "forward event-count mismatch")
    all_rows = selection + forward
    require(len(all_rows) == 1482, "unexpected total lifecycle count")
    require(min(item.state_age_days for item in all_rows) == 7, "unexpected minimum state age")
    require(max(item.state_age_days for item in all_rows) == 14, "unexpected maximum state age")
    structural = verify_structural_anchors(all_rows)
    anchor_reproduction = verify_anchor_result(load_json(INPUT_ROOT / ANCHOR_JSON), selection, forward)

    p1_result, p1_gates, p1_pass = p1_economics(all_rows, declaration)
    later_result: dict[str, Any] | None = None
    later_gates: list[dict[str, Any]] | None = None
    later_pass = False
    if p1_pass:
        later_result, later_gates, later_pass = later_economics(all_rows, declaration)

    if not p1_pass:
        verdict = "FAIL_PRIOR_BROAD_DOLLAR_NO_P1_PORTFOLIO_RISK_STATE_NO_SEED"
        retained_seed = None
    elif not later_pass:
        verdict = "FAIL_PRIOR_BROAD_DOLLAR_CONFIRMATION_OR_LATEST_NO_SEED"
        retained_seed = None
    else:
        verdict = "PASS_PRIOR_BROAD_DOLLAR_RETAIN_ONE_PORTFOLIO_RISK_SUPPRESSION_INFORMATION_SEED"
        retained_seed = "SUPPRESS_PAIRED_ANCHOR_BIRTHS_DURING_CAUSAL_PRIOR_BROAD_DOLLAR_STRENGTHENING"

    result = {
        "schema": "zeta-next-prior-broad-dollar-portfolio-state-result-v1",
        "created_at_local": "2026-08-29",
        "status": "VALID_COMPLETE_FIXED_SOURCE_FREE_AGGREGATION",
        "unit": declaration["unit"],
        "family": declaration["family"],
        "macro_program": declaration["macro_program"],
        "integrity": {
            "passed": True,
            "input_files": len(input_paths),
            "input_manifest_sha256": declaration["immutable_inputs"]["manifest_sha256"],
            "script_sha256": declaration["implementation"]["script_sha256"],
            "official_html_semantics_passed": True,
            "dollar_structure": dollar_structure,
            "event_counts": {
                "selection": dict(selection_events),
                "forward": dict(forward_events),
            },
            "anchor_reproduction": anchor_reproduction,
            "lifecycle_count": len(all_rows),
            "causal_state_age_days": {
                "minimum": min(item.state_age_days for item in all_rows),
                "maximum": max(item.state_age_days for item in all_rows),
            },
            "premetric_structural_anchors": structural,
            "faults": 0,
        },
        "P1_economics": p1_result,
        "P1_gates": p1_gates,
        "P2_P5_economics_opened": p1_pass,
        "later_economics": later_result,
        "later_gates": later_gates,
        "decision": {
            "verdict": verdict,
            "retained_information_seed": retained_seed,
            "fixed_path_interpretation": "Suppression value is the negative of observed strengthening-state lifecycle net on the unchanged close paths. It does not claim replacement admissions, freed capacity, compounding, native fills or native drawdown.",
            "mt5_shortlist": None,
            "optimization_candidate": None,
            "live_authority": False,
        },
        "execution": {
            "successful_fixed_source_free_aggregations": 1,
            "economic_metric_reruns": 0,
            "internal_elapsed_seconds": time.perf_counter() - started,
            "new_data_acquisitions_during_formal_process": 0,
            "runtime_copies": 0,
            "mql_changes": 0,
            "compile_paths": 0,
            "tester_paths": 0,
            "orders": 0,
            "broker_or_account_queries": 0,
        },
        "program_6_opened": False,
        "live_surface": "UNTOUCHED",
    }
    write_json(TRACKED_RESULT_PATH, result)
    write_json(RAW_RESULT_PATH, result)
    print(json.dumps({
        "status": result["status"],
        "verdict": verdict,
        "P1_passed_gates": p1_result["passed_gate_count"],
        "P1_total_gates": p1_result["total_gate_count"],
        "P2_P5_economics_opened": p1_pass,
        "elapsed_seconds": result["execution"]["internal_elapsed_seconds"],
    }, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
