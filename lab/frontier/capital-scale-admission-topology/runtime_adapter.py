#!/usr/bin/env python3
"""Close the capital-scale admission-topology unit from serial real-tick evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
FRONTIER = ROOT / "lab" / "frontier" / "capital-scale-admission-topology"
ARTIFACTS = (
    ROOT / "lab" / "artifacts" / "backtests" / "capital-scale-admission-topology"
)
TRANSITION_ARTIFACTS = (
    ROOT / "lab" / "artifacts" / "backtests" / "transition-reserve-geometry"
)
ELASTICITY_ARTIFACTS = (
    ROOT / "lab" / "artifacts" / "backtests" / "capital-step-elasticity"
)
PORTFOLIO = "ZT-NEXT-FRONTIER-CAPITAL-SCALE-ADMISSION-TOPOLOGY-V1"
MODELED_RISK_FRACTION = 0.75
POSITION_RISK_FRACTION = 0.04
AGGREGATE_RISK_FRACTION = 0.12
TOLERANCE = 0.01
TARGET_TIME = "2026.03.06 17:00:00"
TARGET_COMPONENT = "ZT-H1-US100-CROSS-IN-14b72317b7"
RETURN_COMPONENT = "ZT-H1-US30-RETURN-I-c870a788ec"
PRESSURE_COMPONENT = "ZT-M30-US30-INTRADAY-R-2eb111fc46"
RC16_COMPONENT = "ZT-M30-US30-RANGE-COMP-61f61deaba"
PASSIVE_COMPONENT = "ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8"
COMPONENTS = {
    RC16_COMPONENT: "RC16",
    "ZT-M30-US30-RANGE-COMP-64efb16616": "RC4",
    TARGET_COMPONENT: "CROSS",
    PRESSURE_COMPONENT: "PRESSURE",
    RETURN_COMPONENT: "RETURN",
    PASSIVE_COMPONENT: "PASSIVE",
}
NEW_RUNS = {
    "100": {
        "deposit": 100.0,
        "report": "topology-100-2025-2026q3.htm",
        "log": "topology-100-agent.log",
        "events": ["topology-100-events-a.csv", "topology-100-events-b.csv"],
    },
    "200": {
        "deposit": 200.0,
        "report": "topology-200-2025-2026q3.htm",
        "log": "topology-200-agent.log",
        "events": ["topology-200-events-a.csv", "topology-200-events-b.csv"],
    },
    "300": {
        "deposit": 300.0,
        "report": "topology-300-2025-2026q3.htm",
        "log": "topology-300-agent.log",
        "events": ["topology-300-events-a.csv", "topology-300-events-b.csv"],
    },
}
OLD_EVENTS = {
    "100": [
        ELASTICITY_ARTIFACTS / "hard20-loser-events-a.csv",
        ELASTICITY_ARTIFACTS / "hard20-loser-events-b.csv",
    ],
    "200": [
        TRANSITION_ARTIFACTS / "geometry-200-events-a.csv",
        TRANSITION_ARTIFACTS / "geometry-200-events-b.csv",
    ],
    "300": [
        TRANSITION_ARTIFACTS / "geometry-300-events-a.csv",
        TRANSITION_ARTIFACTS / "geometry-300-events-b.csv",
    ],
}


def rounded(value: float, digits: int = 6) -> float:
    return round(value, digits)


def source(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "sha256": digest.hexdigest(),
        "bytes": path.stat().st_size,
    }


def number(text: str) -> float:
    match = re.search(r"-?\d+(?:,\d{3})*(?:\.\d+)?", text)
    if match is None:
        raise RuntimeError(f"numeric metric missing from {text!r}")
    return float(match.group(0).replace(",", ""))


def report_metrics(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-16")

    def values(label: str) -> list[str]:
        pattern = (
            rf"<td[^>]*>\s*{re.escape(label)}:\s*</td>\s*"
            rf"<td[^>]*>\s*<b>([^<]*)</b>"
        )
        return re.findall(pattern, text, flags=re.IGNORECASE)

    net = values("총수입") or values("Total Net Profit")
    balance_dd = values("Balance Drawdown Maximal")
    equity_dd = values("Equity Drawdown Maximal")
    profit_factor = values("Profit Factor")
    recovery_factor = values("Recovery Factor")
    sharpe = values("Sharpe Ratio")
    trades = values("총 거래횟수") or values("Total Trades")
    quality = values("히스토리 품질") or values("History Quality")
    if not all(
        (net, balance_dd, equity_dd, profit_factor, recovery_factor, sharpe, trades)
    ):
        raise RuntimeError(f"report metrics incomplete in {path}")
    return {
        "actual_net": number(net[0]),
        "actual_balance_drawdown": number(balance_dd[0]),
        "actual_equity_drawdown": number(equity_dd[0]),
        "profit_factor": number(profit_factor[0]),
        "recovery_factor": number(recovery_factor[0]),
        "sharpe_ratio": number(sharpe[0]),
        "entries": int(number(trades[0])),
        "history_quality": quality[0] if quality else "unknown",
    }


def fields(line: str) -> dict[str, str]:
    return dict(re.findall(r"(?:^|\s)([A-Za-z0-9_]+)=([^\s]+)", line))


def tagged_fields(line: str, tag: str) -> dict[str, str]:
    payload = line.split(tag, 1)[1]
    return {
        item.split("=", 1)[0]: item.split("=", 1)[1]
        for item in payload.split("|")
        if "=" in item
    }


def log_summaries(path: Path) -> dict[str, Any]:
    finals: list[dict[str, str]] = []
    topology: list[dict[str, str]] = []
    reserve: list[dict[str, str]] = []
    with path.open("r", encoding="utf-16-le", errors="strict") as handle:
        for line in handle:
            if f"final portfolio={PORTFOLIO}" in line:
                finals.append(fields(line))
            if "ZETA_FRONTIER_ADMISSION_TOPOLOGY_SUMMARY|" in line:
                topology.append(
                    tagged_fields(line, "ZETA_FRONTIER_ADMISSION_TOPOLOGY_SUMMARY|")
                )
            if "ZETA_FRONTIER_TRANSITION_RESERVE_SUMMARY|" in line:
                reserve.append(
                    tagged_fields(line, "ZETA_FRONTIER_TRANSITION_RESERVE_SUMMARY|")
                )
    if not finals or not topology or not reserve:
        raise RuntimeError(f"runtime summaries missing in {path}")

    final = finals[-1]
    topo = topology[-1]
    reserve_row = reserve[-1]
    return {
        "final": {
            "stressed_net": float(final["stressed_net_2x"]),
            "stressed_closed_drawdown": float(final["stressed_max_closed_dd"]),
            "actual_net": float(final["project_realized_net"]),
            "stage_balance": float(final["project_stage_balance"]),
            "risk_admission_skips": int(final["risk_admission_skips"]),
            "protection_calculation_failures": int(
                final["protection_calc_failures"]
            ),
            "protection_mismatches": int(final["protection_mismatches"]),
            "safety_stopped": final["safety_stopped"] == "true",
            "persistence_failed": final["persistence_failed"] == "true",
            "broker_mismatch": final["broker_mismatch"] == "true",
            "foreign_exposure": final["foreign_exposure"] == "true",
        },
        "topology": {
            "checks": int(topo["checks"]),
            "overrides": int(topo["overrides"]),
            "unit_blocks": int(topo["unit_blocks"]),
            "stop_risk_blocks": int(topo["stop_risk_blocks"]),
            "read_failures": int(topo["read_failures"]),
            "post_placement_checks": int(topo.get("post_placement_checks", "0")),
            "post_placement_confirmations": int(
                topo.get("post_placement_confirmations", "0")
            ),
            "post_placement_blocks": int(topo.get("post_placement_blocks", "0")),
            "maximum_evaluated_units_after": int(topo["max_units_after"]),
            "maximum_evaluated_actual_stop_risk": float(
                topo["max_actual_stop_risk_after"]
            ),
        },
        "reserve": {
            "mode": reserve_row["mode"],
            "deposit": float(reserve_row["deposit"]),
            "base_volume": float(reserve_row["base_volume"]),
            "addition_step": float(reserve_row["addition_step"]),
            "maximum_raw_tier": int(reserve_row["max_raw_tier"]),
        },
        "attempt_history": [
            {
                "actual_net": float(row["project_realized_net"]),
                "safety_stopped": row["safety_stopped"] == "true",
                "broker_mismatch": row["broker_mismatch"] == "true",
                "protection_mismatches": int(row["protection_mismatches"]),
            }
            for row in finals
        ],
    }


def detail_number(detail: str, key: str) -> float | None:
    match = re.search(rf"(?:^|\s){re.escape(key)}=(-?\d+(?:\.\d+)?)", detail)
    return float(match.group(1)) if match else None


def load_events(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for raw in csv.DictReader(handle):
                row: dict[str, Any] = dict(raw)
                row["sequence"] = int(raw["state_sequence"])
                row["value_a_number"] = float(raw["value_a"])
                row["value_b_number"] = float(raw["value_b"])
                row["stressed_balance_number"] = float(raw["stressed_balance"])
                row["stage_balance_number"] = float(raw["project_stage_balance"])
                row["equity_number"] = float(raw["account_equity"])
                rows.append(row)
    rows.sort(key=lambda row: row["sequence"])
    return rows


def event_key(row: dict[str, Any]) -> str:
    return f"{row['server_time']}|{row['component_id']}"


def stop_bound_risk(entry: float, stop: float, volume: float) -> float:
    return abs(entry - stop) * volume / MODELED_RISK_FRACTION


def drawdown(values: list[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    maximum = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        maximum = max(maximum, peak - cumulative)
    return rounded(maximum)


def event_metrics(rows: list[dict[str, Any]], base_volume: float) -> dict[str, Any]:
    entries = [row for row in rows if row["event"] in {"OPEN", "PASSIVE_FILL"}]
    closes = [row for row in rows if row["event"] in {"CLOSE", "EXTERNAL_CLOSE"}]
    active: dict[str, dict[str, float]] = {}
    pending: dict[str, float] | None = None
    maximum_occupied = 0
    maximum_initial_stop_risk = 0.0
    component_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        event = row["event"]
        component = row["component_id"]
        if event == "PASSIVE_PLACE":
            pending = {
                "entry": row["value_a_number"],
                "stop": detail_number(row["detail"], "stop") or 0.0,
                "volume": base_volume,
            }
        elif event == "PASSIVE_FILL":
            if pending is None:
                raise RuntimeError(f"passive fill without pending at {row['server_time']}")
            active[component] = {
                "entry": row["value_a_number"],
                "stop": pending["stop"],
                "volume": row["value_b_number"],
            }
            pending = None
        elif event == "PASSIVE_EXPIRE":
            pending = None
        elif event == "OPEN":
            active[component] = {
                "entry": detail_number(row["detail"], "position_open")
                or row["value_a_number"],
                "stop": detail_number(row["detail"], "stop") or 0.0,
                "volume": row["value_b_number"],
            }
        elif event in {"CLOSE", "EXTERNAL_CLOSE"}:
            active.pop(component, None)

        exposures = list(active.values()) + ([pending] if pending else [])
        maximum_occupied = max(maximum_occupied, len(exposures))
        maximum_initial_stop_risk = max(
            maximum_initial_stop_risk,
            sum(
                stop_bound_risk(item["entry"], item["stop"], item["volume"])
                for item in exposures
            ),
        )

    for row in closes:
        component_rows[COMPONENTS.get(row["component_id"], row["component_id"])].append(
            row
        )

    overrides = [row for row in rows if row["event"] == "RISK_UNIT_ADMISSION_OVERRIDE"]
    confirmations = [
        row for row in rows if row["event"] == "RISK_UNIT_POST_PLACEMENT_CONFIRM"
    ]
    override_contract = [
        {
            "key": event_key(row),
            "actual_stop_risk_after": rounded(row["value_a_number"]),
            "units_after": int(round(row["value_b_number"])),
            "actual_stop_risk_cap": rounded(
                detail_number(row["detail"], "actual_cap") or 0.0
            ),
            "within_contract": (
                row["value_b_number"] <= 3.0
                and row["value_a_number"]
                <= (detail_number(row["detail"], "actual_cap") or 0.0) + TOLERANCE
            ),
        }
        for row in overrides
    ]
    confirmation_contract = [
        {
            "key": event_key(row),
            "actual_stop_risk": rounded(row["value_a_number"]),
            "occupied_units": int(round(row["value_b_number"])),
            "actual_stop_risk_cap": rounded(
                detail_number(row["detail"], "actual_cap") or 0.0
            ),
            "within_contract": (
                row["value_b_number"] <= 3.0
                and row["value_a_number"]
                <= (detail_number(row["detail"], "actual_cap") or 0.0) + TOLERANCE
            ),
        }
        for row in confirmations
    ]
    return {
        "entries": len(entries),
        "closed_lifecycles": len(closes),
        "actual_net": rounded(sum(row["value_a_number"] for row in closes)),
        "stressed_net": rounded(sum(row["value_b_number"] for row in closes)),
        "actual_closed_drawdown": drawdown(
            [row["value_a_number"] for row in closes]
        ),
        "stressed_closed_drawdown": drawdown(
            [row["value_b_number"] for row in closes]
        ),
        "risk_admission_skips": sum(
            row["event"] == "RISK_ADMISSION_SKIP" for row in rows
        ),
        "normal_stops": sum(
            row["event"] == "STOP" and row["detail"] == "normal" for row in rows
        ),
        "maximum_occupied_units": maximum_occupied,
        "maximum_reconstructed_initial_stop_risk": rounded(
            maximum_initial_stop_risk
        ),
        "override_contract": override_contract,
        "post_placement_contract": confirmation_contract,
        "all_override_events_within_contract": all(
            item["within_contract"] for item in override_contract
        ),
        "all_post_placement_events_within_contract": all(
            item["within_contract"] for item in confirmation_contract
        ),
        "components": {
            component: {
                "closed_lifecycles": len(component_closes),
                "actual_net": rounded(
                    sum(row["value_a_number"] for row in component_closes)
                ),
                "stressed_net": rounded(
                    sum(row["value_b_number"] for row in component_closes)
                ),
            }
            for component, component_closes in sorted(component_rows.items())
        },
        "entry_keys": sorted(event_key(row) for row in entries),
    }


def no_faults(final: dict[str, Any], topology: dict[str, Any]) -> bool:
    return (
        not final["safety_stopped"]
        and not final["persistence_failed"]
        and not final["broker_mismatch"]
        and not final["foreign_exposure"]
        and final["protection_calculation_failures"] == 0
        and final["protection_mismatches"] == 0
        and topology["read_failures"] == 0
        and topology["post_placement_blocks"] == 0
    )


def run_summary(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    report_path = ARTIFACTS / spec["report"]
    log_path = ARTIFACTS / spec["log"]
    event_paths = [ARTIFACTS / item for item in spec["events"]]
    rows = load_events(event_paths)
    report = report_metrics(report_path)
    log = log_summaries(log_path)
    events = event_metrics(rows, log["reserve"]["base_volume"])
    deposit = float(spec["deposit"])
    parity = {
        "report_equals_final_actual_net": abs(
            report["actual_net"] - log["final"]["actual_net"]
        )
        <= 0.011,
        "events_equal_final_actual_net": abs(
            events["actual_net"] - log["final"]["actual_net"]
        )
        <= 0.011,
        "events_equal_final_stressed_net": abs(
            events["stressed_net"] - log["final"]["stressed_net"]
        )
        <= 0.011,
        "events_equal_final_stressed_drawdown": abs(
            events["stressed_closed_drawdown"]
            - log["final"]["stressed_closed_drawdown"]
        )
        <= 0.011,
        "report_equals_event_entries": report["entries"] == events["entries"],
        "entries_equal_closes": events["entries"] == events["closed_lifecycles"],
        "one_normal_stop": events["normal_stops"] == 1,
        "summary_equals_event_overrides": log["topology"]["overrides"]
        == len(events["override_contract"]),
        "summary_equals_event_skips": log["final"]["risk_admission_skips"]
        == events["risk_admission_skips"],
    }
    if not all(parity.values()):
        raise RuntimeError(f"runtime parity failed for {name}: {parity}")
    if abs(log["reserve"]["deposit"] - deposit) > 1.0e-9:
        raise RuntimeError(f"deposit mismatch for {name}")

    return {
        "deposit": deposit,
        "report": report,
        "final": log["final"],
        "topology_summary": log["topology"],
        "reserve_summary": log["reserve"],
        "events": {key: value for key, value in events.items() if key != "entry_keys"},
        "normalized": {
            "actual_return_percent": rounded(100.0 * report["actual_net"] / deposit),
            "stressed_return_percent": rounded(
                100.0 * log["final"]["stressed_net"] / deposit
            ),
            "stressed_closed_drawdown_percent": rounded(
                100.0 * log["final"]["stressed_closed_drawdown"] / deposit
            ),
        },
        "no_faults": no_faults(log["final"], log["topology"]),
        "parity": parity,
        "sources": {
            "report": source(report_path),
            "agent_log": source(log_path),
            "events": [source(path) for path in event_paths],
        },
        "_rows": rows,
        "_entry_keys": events["entry_keys"],
        "_attempt_history": log["attempt_history"],
    }


def old_metrics(capital: str, prior: dict[str, Any]) -> dict[str, Any]:
    if capital == "100":
        row = prior["references"]["geometry_100"]
    else:
        row = prior["runtime_runs"][f"geometry_{capital}"]
    return {
        "entries": row["report"]["entries"],
        "actual_net": row["report"]["actual_net"],
        "stressed_net": row["final"]["stressed_net"],
        "stressed_closed_drawdown": row["final"]["stressed_closed_drawdown"],
        "risk_admission_skips": row["final"]["risk_admission_skips"],
    }


def find_row(
    rows: list[dict[str, Any]],
    *,
    event: str,
    server_time: str,
    component: str,
) -> dict[str, Any]:
    matches = [
        row
        for row in rows
        if row["event"] == event
        and row["server_time"] == server_time
        and row["component_id"] == component
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one {event} {server_time} {component}, found {len(matches)}"
        )
    return matches[0]


def next_close(rows: list[dict[str, Any]], opened: dict[str, Any]) -> dict[str, Any]:
    for row in rows:
        if (
            row["sequence"] > opened["sequence"]
            and row["component_id"] == opened["component_id"]
            and row["event"] in {"CLOSE", "EXTERNAL_CLOSE"}
        ):
            return row
    raise RuntimeError(f"close missing after {event_key(opened)}")


def open_brief(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "server_time": row["server_time"],
        "component": COMPONENTS.get(row["component_id"], row["component_id"]),
        "entry": rounded(row["value_a_number"]),
        "volume": rounded(row["value_b_number"]),
        "stop": rounded(detail_number(row["detail"], "stop") or 0.0),
        "planned_risk": rounded(
            detail_number(row["detail"], "planned_risk") or 0.0
        ),
    }


def close_brief(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "server_time": row["server_time"],
        "event": row["event"],
        "actual_net": rounded(row["value_a_number"]),
        "stressed_net": rounded(row["value_b_number"]),
    }


def compile_result(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-16-le", errors="strict")
    matches = re.findall(r"Result:\s*(\d+) errors,\s*(\d+) warnings", text)
    if not matches:
        raise RuntimeError(f"compile result missing in {path}")
    errors, warnings = (int(item) for item in matches[-1])
    return {
        "errors": errors,
        "warnings": warnings,
        "passed": errors == 0 and warnings == 0,
        "source": source(path),
    }


def main() -> None:
    runs = {name: run_summary(name, spec) for name, spec in NEW_RUNS.items()}
    if not all(run["no_faults"] for run in runs.values()):
        raise RuntimeError("one or more valid runtime paths contain a fault")

    prior_path = ROOT / "lab" / "frontier" / "transition-reserve-geometry" / "runtime.json"
    prior = json.loads(prior_path.read_text(encoding="utf-8"))
    proxy_path = FRONTIER / "proxy.json"
    proxy = json.loads(proxy_path.read_text(encoding="utf-8"))

    old_rows = {capital: load_events(paths) for capital, paths in OLD_EVENTS.items()}
    entry_comparisons: dict[str, Any] = {}
    economics: dict[str, Any] = {}
    for capital, run in runs.items():
        old_keys = sorted(
            event_key(row)
            for row in old_rows[capital]
            if row["event"] in {"OPEN", "PASSIVE_FILL"}
        )
        new_keys = run["_entry_keys"]
        missing = sorted(set(old_keys) - set(new_keys))
        added = sorted(set(new_keys) - set(old_keys))
        entry_comparisons[capital] = {
            "old_entries": len(old_keys),
            "new_entries": len(new_keys),
            "preserved_entries": len(old_keys) - len(missing),
            "missing_old_entries": missing,
            "added_new_entries": added,
            "exact_old_entry_superset": not missing,
        }
        old = old_metrics(capital, prior)
        economics[capital] = {
            "retained_geometry": old,
            "topology": {
                "entries": run["report"]["entries"],
                "actual_net": run["report"]["actual_net"],
                "stressed_net": run["final"]["stressed_net"],
                "stressed_closed_drawdown": run["final"][
                    "stressed_closed_drawdown"
                ],
                "risk_admission_skips": run["final"]["risk_admission_skips"],
            },
            "topology_minus_retained": {
                "entries": run["report"]["entries"] - old["entries"],
                "actual_net": rounded(
                    run["report"]["actual_net"] - old["actual_net"]
                ),
                "stressed_net": rounded(
                    run["final"]["stressed_net"] - old["stressed_net"]
                ),
                "stressed_closed_drawdown": rounded(
                    run["final"]["stressed_closed_drawdown"]
                    - old["stressed_closed_drawdown"]
                ),
                "risk_admission_skips": run["final"]["risk_admission_skips"]
                - old["risk_admission_skips"],
            },
        }

    new_sets = {capital: set(run["_entry_keys"]) for capital, run in runs.items()}
    scale_entry_sets_equal = len({frozenset(values) for values in new_sets.values()}) == 1

    old_300 = old_rows["300"]
    new_300 = runs["300"]["_rows"]
    original_skip = find_row(
        old_300,
        event="RISK_ADMISSION_SKIP",
        server_time=TARGET_TIME,
        component=TARGET_COMPONENT,
    )
    recovered_open = find_row(
        new_300,
        event="OPEN",
        server_time=TARGET_TIME,
        component=TARGET_COMPONENT,
    )
    old_return_open = find_row(
        old_300,
        event="OPEN",
        server_time="2026.03.06 16:00:00",
        component=RETURN_COMPONENT,
    )
    new_return_open = find_row(
        new_300,
        event="OPEN",
        server_time="2026.03.06 16:00:00",
        component=RETURN_COMPONENT,
    )
    old_return_close = next_close(old_300, old_return_open)
    new_return_close = next_close(new_300, new_return_open)
    new_pressure_open = find_row(
        new_300,
        event="OPEN",
        server_time="2026.03.06 15:00:00",
        component=PRESSURE_COMPONENT,
    )
    target_overrides = [
        row
        for row in new_300
        if row["event"] == "RISK_UNIT_ADMISSION_OVERRIDE"
        and row["server_time"] == TARGET_TIME
        and row["component_id"] == TARGET_COMPONENT
    ]
    target_planned_risk = detail_number(recovered_open["detail"], "planned_risk") or 0.0
    target_stop = detail_number(recovered_open["detail"], "stop") or 0.0
    target_actual_stop_risk = stop_bound_risk(
        recovered_open["value_a_number"],
        target_stop,
        recovered_open["value_b_number"],
    )
    pressure_stop = detail_number(new_pressure_open["detail"], "stop") or 0.0
    pressure_planned_risk = (
        detail_number(new_pressure_open["detail"], "planned_risk") or 0.0
    )
    pressure_actual_stop_risk = stop_bound_risk(
        new_pressure_open["value_a_number"],
        pressure_stop,
        new_pressure_open["value_b_number"],
    )

    jan2_new_cross = find_row(
        new_300,
        event="OPEN",
        server_time="2025.01.02 17:00:00",
        component=TARGET_COMPONENT,
    )
    jan2_new_cross_close = next_close(new_300, jan2_new_cross)
    jan8_old_rc16 = find_row(
        old_300,
        event="OPEN",
        server_time="2025.01.08 13:30:00",
        component=RC16_COMPONENT,
    )
    jan8_new_rc16 = find_row(
        new_300,
        event="OPEN",
        server_time="2025.01.08 13:30:00",
        component=RC16_COMPONENT,
    )
    jan8_old_return = find_row(
        old_300,
        event="OPEN",
        server_time="2025.01.08 16:00:00",
        component=RETURN_COMPONENT,
    )
    jan8_new_return_skip = find_row(
        new_300,
        event="RISK_ADMISSION_SKIP",
        server_time="2025.01.08 16:00:00",
        component=RETURN_COMPONENT,
    )
    jan8_old_exchange = find_row(
        old_300,
        event="SLOT_EXCHANGE_RELEASE",
        server_time="2025.01.08 16:00:00",
        component=RETURN_COMPONENT,
    )
    may13_old_passive = find_row(
        old_300,
        event="PASSIVE_FILL",
        server_time="2025.05.13 15:18:49",
        component=PASSIVE_COMPONENT,
    )
    may13_new_passive = find_row(
        new_300,
        event="PASSIVE_FILL",
        server_time="2025.05.13 15:00:29",
        component=PASSIVE_COMPONENT,
    )

    contract_checks = {
        "all_three_paths_fault_free": all(run["no_faults"] for run in runs.values()),
        "maximum_occupied_units_no_more_than_three": all(
            run["events"]["maximum_occupied_units"] <= 3 for run in runs.values()
        ),
        "all_override_events_within_three_units_and_stop_backstop": all(
            run["events"]["all_override_events_within_contract"]
            for run in runs.values()
        ),
        "all_post_placement_confirmations_within_contract": all(
            run["events"]["all_post_placement_events_within_contract"]
            for run in runs.values()
        ),
        "scale_entry_sets_equal": scale_entry_sets_equal,
        "target_300_entry_recovered": event_key(recovered_open)
        in new_sets["300"],
        "target_recovered_by_same_decision_override": bool(target_overrides),
        "every_old_entry_preserved": all(
            item["exact_old_entry_superset"] for item in entry_comparisons.values()
        ),
    }
    selected_for_retention = all(
        (
            contract_checks["all_three_paths_fault_free"],
            contract_checks["maximum_occupied_units_no_more_than_three"],
            contract_checks[
                "all_override_events_within_three_units_and_stop_backstop"
            ],
            contract_checks["all_post_placement_confirmations_within_contract"],
            contract_checks["scale_entry_sets_equal"],
            contract_checks["target_300_entry_recovered"],
            contract_checks["target_recovered_by_same_decision_override"],
            contract_checks["every_old_entry_preserved"],
        )
    )

    compile_paths = {
        "topology_ea": ROOT
        / "lab"
        / "artifacts"
        / "logs"
        / "ZetaNextCapitalScaleAdmissionTopologyV1-post-placement.log",
        "neutral_parent": ROOT
        / "lab"
        / "artifacts"
        / "logs"
        / "ZetaNextPre500FiniteRiskPortfolioV7-post-placement-neutral.log",
        "neutral_transition_reserve": ROOT
        / "lab"
        / "artifacts"
        / "logs"
        / "ZetaNextTransitionReserveGeometryV1-post-placement-neutral.log",
    }
    compile_evidence = {
        name: compile_result(path) for name, path in compile_paths.items()
    }

    invalid_attempt = next(
        (
            item
            for item in runs["100"]["_attempt_history"][:-1]
            if item["safety_stopped"] and item["protection_mismatches"] > 0
        ),
        None,
    )

    payload = {
        "unit": "capital-scale-admission-topology-010",
        "question": "Can shared 12 percent admission use scale-consistent risk units so the 300 USD path recovers its single missing opportunity without increasing maximum exposure or weakening transition reserve?",
        "boundary": {
            "new_hypothesis_opened": False,
            "mechanism_run": "current_cap_three_units_with_actual_stop_backstop",
            "transition_reserve": "prospective_position_budget_1_25 retained unchanged",
            "entry_priority": "unchanged first-come physical order",
            "independent_account_and_priority_experiments": "not opened",
            "live_surface": "untouched",
        },
        "compile": compile_evidence,
        "implementation_correction": {
            "excluded_first_attempt": invalid_attempt,
            "cause": "The selected admission contract allowed a third Passive risk unit, but the legacy post-placement confirmation reapplied the old nominal dollar aggregate and engaged a safety stop.",
            "correction": "A frontier-only post-placement hook now confirms the same three-unit plus actual-stop backstop contract. Neutral parent and retained transition-reserve binaries compile without the hook.",
            "economic_evidence_use": False,
        },
        "runtime_runs": {
            capital: {
                key: value
                for key, value in run.items()
                if not key.startswith("_")
            }
            for capital, run in runs.items()
        },
        "scale_consistency": {
            "entry_sets_equal": scale_entry_sets_equal,
            "entries": {
                capital: run["report"]["entries"] for capital, run in runs.items()
            },
            "actual_return_percent_range": rounded(
                max(run["normalized"]["actual_return_percent"] for run in runs.values())
                - min(
                    run["normalized"]["actual_return_percent"]
                    for run in runs.values()
                )
            ),
            "stressed_return_percent_range": rounded(
                max(
                    run["normalized"]["stressed_return_percent"]
                    for run in runs.values()
                )
                - min(
                    run["normalized"]["stressed_return_percent"]
                    for run in runs.values()
                )
            ),
            "stressed_drawdown_percent_range": rounded(
                max(
                    run["normalized"]["stressed_closed_drawdown_percent"]
                    for run in runs.values()
                )
                - min(
                    run["normalized"]["stressed_closed_drawdown_percent"]
                    for run in runs.values()
                )
            ),
        },
        "entry_preservation": entry_comparisons,
        "economic_comparison": economics,
        "original_missing_incident": proxy["incident"],
        "runtime_target_incident": {
            "original_skip": {
                "planned_candidate_risk": rounded(original_skip["value_a_number"]),
                "nominal_aggregate_after": rounded(original_skip["value_b_number"]),
                "detail": original_skip["detail"],
            },
            "recovered_open": open_brief(recovered_open),
            "recovered_close": close_brief(next_close(new_300, recovered_open)),
            "same_decision_override_count": len(target_overrides),
            "candidate_actual_stop_risk": rounded(target_actual_stop_risk),
            "candidate_position_budget": rounded(target_planned_risk),
            "candidate_current_aggregate_cap": rounded(
                target_planned_risk
                / POSITION_RISK_FRACTION
                * AGGREGATE_RISK_FRACTION
            ),
            "incumbent_at_decision": {
                "open": open_brief(new_pressure_open),
                "actual_stop_risk": rounded(pressure_actual_stop_risk),
            },
            "occupied_units_after": 2,
            "nominal_aggregate_after": rounded(
                pressure_planned_risk + target_planned_risk
            ),
            "actual_stop_risk_after": rounded(
                pressure_actual_stop_risk + target_actual_stop_risk
            ),
            "actual_stop_headroom": rounded(
                target_planned_risk
                / POSITION_RISK_FRACTION
                * AGGREGATE_RISK_FRACTION
                - pressure_actual_stop_risk
                - target_actual_stop_risk
            ),
            "old_return": {
                "open": open_brief(old_return_open),
                "close": close_brief(old_return_close),
            },
            "new_return": {
                "open": open_brief(new_return_open),
                "close": close_brief(new_return_close),
            },
            "causal_interpretation": "The target was recovered indirectly. Earlier topology admissions changed cumulative P/L and current capital, moving the 300 USD Return stop from 47012.24 to 47033.36. Return then stopped at 16:46:41, so Cross arrived with one incumbent unit fewer and passed the ordinary nominal admission path; no topology override fired at 17:00.",
        },
        "adjacent_path_substitutions": {
            "first_added_lifecycle": {
                "open": open_brief(jan2_new_cross),
                "close": close_brief(jan2_new_cross_close),
                "effect": "This formerly blocked Cross added 10.214 stressed dollars before the first common lost lifecycle.",
            },
            "first_common_lost_lifecycle": {
                "key": "2025.01.08 16:00:00|" + RETURN_COMPONENT,
                "old_rc16": {
                    "open": open_brief(jan8_old_rc16),
                    "close": close_brief(next_close(old_300, jan8_old_rc16)),
                },
                "new_rc16": {
                    "open": open_brief(jan8_new_rc16),
                    "close": close_brief(next_close(new_300, jan8_new_rc16)),
                },
                "old_exchange": {
                    "actual_net_at_release": rounded(
                        jan8_old_exchange["value_a_number"]
                    ),
                    "stressed_r_at_release": rounded(
                        jan8_old_exchange["value_b_number"]
                    ),
                    "detail": jan8_old_exchange["detail"],
                },
                "old_return_open": open_brief(jan8_old_return),
                "new_return_skip": {
                    "candidate_actual_stop_risk": rounded(
                        jan8_new_return_skip["value_a_number"]
                    ),
                    "nominal_aggregate_after": rounded(
                        jan8_new_return_skip["value_b_number"]
                    ),
                    "detail": jan8_new_return_skip["detail"],
                },
                "interpretation": "The January 2 gain increased January 8 risk capital and widened RC16's stop from 42310.48 to 42303.71. RC16 therefore survived from 14:31:43 to 16:43:37. Return arrived as the fourth occupied unit and was blocked instead of receiving the old Pressure slot exchange.",
            },
            "passive_timing_substitution": {
                "old_fill": {
                    "server_time": may13_old_passive["server_time"],
                    "entry": rounded(may13_old_passive["value_a_number"]),
                },
                "new_fill": {
                    "server_time": may13_new_passive["server_time"],
                    "entry": rounded(may13_new_passive["value_a_number"]),
                },
                "interpretation": "An earlier 15:00 Passive opportunity replaced the retained 15:15 opportunity, so higher total entries still do not imply strict opportunity preservation.",
            },
        },
        "gate": {
            **contract_checks,
            "selected_for_retention": selected_for_retention,
            "decision": "reject_runtime_transform",
            "reason": "The transform made the three capital paths numerically scale-consistent and recovered the named 300 USD entry, but it failed the predeclared exact-entry-preservation gate and recovered the target only through endogenous earlier path mutation rather than a same-decision admission correction.",
        },
        "judgement": {
            "retained_primary": "prospective_position_budget_1_25_transition_reserve_with_existing_nominal_12_percent_admission",
            "promotion": "none",
            "next_research_opened": False,
            "closed_observation": "Current-cap three-unit admission is a coherent safety representation but not a behavior-preserving repair. It aligned the paths at 930 entries each and bounded occupied exposure at three units, yet replaced existing opportunities and reduced stressed net at every capital scale. The original 300 USD miss remains explained by incumbent survival plus nominal budget occupancy, while no tested non-oracle admission transform satisfied the preservation gate.",
        },
        "limits": [
            "Only the mechanism selected by the already-open proxy was run; no new admission, priority, independent-account or portfolio-ranking hypothesis was introduced.",
            "Outcome differences are diagnostic. Rejection is controlled first by exact entry preservation and direct causal recovery, not hindsight profitability.",
            "The maximum_evaluated_units_after summary includes blocked fourth candidates; reconstructed actually occupied exposure never exceeded three units.",
        ],
        "sources": {
            "runtime_adapter": source(Path(__file__)),
            "proxy": source(proxy_path),
            "prior_transition_runtime": source(prior_path),
            "old_entry_events": {
                capital: [source(path) for path in paths]
                for capital, paths in OLD_EVENTS.items()
            },
            "ea": source(
                ROOT
                / "lab"
                / "mt5"
                / "src"
                / "Experts"
                / "ZetaNextCapitalScaleAdmissionTopologyV1.mq5"
            ),
            "binary": source(
                ROOT
                / "lab"
                / "mt5"
                / "src"
                / "Experts"
                / "ZetaNextCapitalScaleAdmissionTopologyV1.ex5"
            ),
            "admission_adapter": source(
                ROOT
                / "lab"
                / "mt5"
                / "src"
                / "Include"
                / "ZetaTerminusNext"
                / "Frontier"
                / "CapitalScaleAdmissionTopologyAdapter.mqh"
            ),
            "field_adapter": source(
                ROOT
                / "lab"
                / "mt5"
                / "src"
                / "Include"
                / "ZetaTerminusNext"
                / "Frontier"
                / "CapitalScaleAdmissionTopologyFieldAdapter.mqh"
            ),
        },
    }

    output = FRONTIER / "runtime.json"
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {output}")
    print(
        "gate:",
        payload["gate"]["decision"],
        "preserved=",
        payload["gate"]["every_old_entry_preserved"],
        "direct=",
        payload["gate"]["target_recovered_by_same_decision_override"],
    )


if __name__ == "__main__":
    main()
