#!/usr/bin/env python3
"""Probe causal adjacent-tier exposure dithering on current Next Lab paths."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
FRONTIER = ROOT / "lab" / "frontier" / "capital-step-elasticity"
PHASE_ARTIFACTS = ROOT / "lab" / "artifacts" / "backtests" / "capital-step-phase"
SLOT_ARTIFACTS = ROOT / "lab" / "artifacts" / "backtests" / "slot-shadow-price"
REFERENCE_CAPITAL = 100.0
ADDITION_STEP = 150.0
BASE_VOLUME = 0.01
PASSIVE_ID = "ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8"
COMPONENT_IDS = {
    "ZT-M30-US30-RANGE-COMP-61f61deaba",
    "ZT-M30-US30-RANGE-COMP-64efb16616",
    "ZT-H1-US100-CROSS-IN-14b72317b7",
    "ZT-M30-US30-INTRADAY-R-2eb111fc46",
    "ZT-H1-US30-RETURN-I-c870a788ec",
    PASSIVE_ID,
}
RUN_PATHS = {
    "prior_broad_slot_exchange": (
        SLOT_ARTIFACTS,
        [
            "extended-market-only-loser-residual-slot-shadow-exchange-v1-events-a.csv",
            "extended-market-only-loser-residual-slot-shadow-exchange-v1-events-b.csv",
        ],
    ),
    "downside_escrow": (
        PHASE_ARTIFACTS,
        ["downside-loser-events-a.csv", "downside-loser-events-b.csv"],
    ),
    "downside_escrow_quarantine": (
        PHASE_ARTIFACTS,
        [
            "downside-loser-quarantine-events-a.csv",
            "downside-loser-quarantine-events-b.csv",
        ],
    ),
    "two_day_confirmation": (
        PHASE_ARTIFACTS,
        ["confirm2-loser-events-a.csv", "confirm2-loser-events-b.csv"],
    ),
    "retained_baseline": (
        PHASE_ARTIFACTS,
        ["downside-baseline-events-a.csv", "downside-baseline-events-b.csv"],
    ),
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


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y.%m.%d %H:%M:%S")


def load_events(folder: Path, names: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in names:
        with (folder / name).open("r", encoding="utf-8", newline="") as handle:
            for raw in csv.DictReader(handle):
                row: dict[str, Any] = dict(raw)
                row["sequence"] = int(raw["state_sequence"])
                row["time"] = parse_time(raw["server_time"])
                row["value_a_number"] = float(raw["value_a"])
                row["value_b_number"] = float(raw["value_b"])
                row["stressed_balance_number"] = float(raw["stressed_balance"])
                rows.append(row)
    rows.sort(key=lambda row: row["sequence"])
    return rows


def build_lifecycle_map(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    active: dict[str, dict[str, Any]] = {}
    output: dict[int, dict[str, Any]] = {}
    for row in rows:
        component = row["component_id"]
        if component not in COMPONENT_IDS:
            continue
        if row["event"] in {"OPEN", "PASSIVE_FILL"}:
            active[component] = row
        elif row["event"] in {"CLOSE", "EXTERNAL_CLOSE"} and component in active:
            opened = active.pop(component)
            output[opened["sequence"]] = {
                "open_sequence": opened["sequence"],
                "open_time": opened["time"],
                "close_time": row["time"],
                "component": component,
                "passive": component == PASSIVE_ID,
                "volume": opened["value_b_number"],
                "balance": opened["stressed_balance_number"],
                "actual_net": row["value_a_number"],
                "stressed_net": row["value_b_number"],
            }
    return output


def drawdown(values: list[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    maximum = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        maximum = max(maximum, peak - cumulative)
    return rounded(maximum)


def policy_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = [
        {
            "family": "observed_discrete_anchor",
            "band_usd": 0.0,
            "scope": "none",
            "initial_credit": 0.0,
            "reset_on_downcross": True,
        },
        {
            "family": "diagnostic_cap_at_2x",
            "band_usd": 0.0,
            "scope": "cap",
            "initial_credit": 0.0,
            "reset_on_downcross": True,
        },
    ]
    for band in (2.5, 5.0, 10.0, 15.0, 20.0, 30.0, 50.0):
        specs.append(
            {
                "family": "hard_third_tier_escrow",
                "band_usd": band,
                "scope": "hard",
                "initial_credit": 0.0,
                "reset_on_downcross": True,
            }
        )
    for scope in ("portfolio_clock", "component_clock"):
        for band in (5.0, 10.0, 15.0, 20.0, 30.0, 50.0):
            for initial_credit in (0.0, 0.5):
                for reset in (True, False):
                    specs.append(
                        {
                            "family": "third_tier_sigma_delta",
                            "band_usd": band,
                            "scope": scope,
                            "initial_credit": initial_credit,
                            "reset_on_downcross": reset,
                        }
                    )
    for index, spec in enumerate(specs):
        spec["policy_id"] = f"elastic-{index:03d}"
    return specs


def selected_tier(
    spec: dict[str, Any],
    raw_tier: int,
    balance: float,
    component: str,
    credits: dict[str, float],
) -> int:
    if spec["scope"] == "none" or raw_tier < 3:
        return(raw_tier)
    if spec["scope"] == "cap":
        return(min(raw_tier, 2))
    threshold = REFERENCE_CAPITAL + (raw_tier - 1) * ADDITION_STEP
    progress = max(0.0, min(1.0, (balance - threshold) / spec["band_usd"]))
    if spec["scope"] == "hard":
        return(raw_tier if progress >= 1.0 else raw_tier - 1)
    if progress >= 1.0:
        return(raw_tier)
    key = "portfolio" if spec["scope"] == "portfolio_clock" else component
    if key not in credits:
        credits[key] = spec["initial_credit"]
    credits[key] += progress
    if credits[key] + 1.0e-12 >= 1.0:
        credits[key] -= 1.0
        return(raw_tier)
    return(raw_tier - 1)


def slice_name(moment: datetime) -> str:
    if moment.year == 2025:
        return("2025")
    return("2026_h1" if moment < datetime(2026, 7, 1) else "2026_h2")


def simulate(
    rows: list[dict[str, Any]], lifecycles: dict[int, dict[str, Any]], spec: dict[str, Any]
) -> dict[str, Any]:
    raw_tier = 1
    prior_raw_tier = 1
    credits: dict[str, float] = {}
    observed: list[float] = []
    adjusted: list[float] = []
    tier_allocations: dict[str, int] = defaultdict(int)
    high_tier_rows: list[dict[str, Any]] = []
    slices: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"entries": 0, "observed": 0.0, "adjusted": 0.0}
    )
    for row in rows:
        if row["event"] == "SIZE_DAY":
            prior_raw_tier = raw_tier
            raw_tier = int(round(row["value_b_number"]))
            if (
                spec["reset_on_downcross"]
                and raw_tier < prior_raw_tier
                and raw_tier < 3
            ):
                credits.clear()
            continue
        if row["event"] not in {"OPEN", "PASSIVE_FILL"}:
            continue
        lifecycle = lifecycles.get(row["sequence"])
        if lifecycle is None:
            continue
        if lifecycle["passive"]:
            chosen = 1
            actual_tier = 1
        else:
            actual_tier = max(1, int(round(lifecycle["volume"] / BASE_VOLUME)))
            chosen = selected_tier(
                spec,
                raw_tier,
                lifecycle["balance"],
                lifecycle["component"],
                credits,
            )
        ratio = chosen / actual_tier
        adjusted_net = lifecycle["stressed_net"] * ratio
        observed.append(lifecycle["stressed_net"])
        adjusted.append(adjusted_net)
        tier_allocations[str(chosen)] += 1
        key = slice_name(lifecycle["close_time"])
        slices[key]["entries"] += 1
        slices[key]["observed"] += lifecycle["stressed_net"]
        slices[key]["adjusted"] += adjusted_net
        if raw_tier >= 3 and not lifecycle["passive"]:
            high_tier_rows.append(
                {
                    "server_time": row["server_time"],
                    "component_id": lifecycle["component"],
                    "balance": rounded(lifecycle["balance"]),
                    "observed_tier": actual_tier,
                    "selected_tier": chosen,
                    "observed_stressed_net": rounded(lifecycle["stressed_net"]),
                    "first_order_adjusted_stressed_net": rounded(adjusted_net),
                }
            )
    observed_net = sum(observed)
    adjusted_total = sum(adjusted)
    observed_dd = drawdown(observed)
    adjusted_dd = drawdown(adjusted)
    return {
        "entries": len(observed),
        "tier_allocations": dict(sorted(tier_allocations.items())),
        "observed_stressed_net": rounded(observed_net),
        "first_order_adjusted_stressed_net": rounded(adjusted_total),
        "first_order_net_delta": rounded(adjusted_total - observed_net),
        "observed_stressed_drawdown": observed_dd,
        "first_order_adjusted_drawdown": adjusted_dd,
        "first_order_drawdown_delta": rounded(adjusted_dd - observed_dd),
        "observed_high_tier_market_entries": sum(
            item["observed_tier"] >= 3 for item in high_tier_rows
        ),
        "selected_high_tier_market_entries": sum(
            item["selected_tier"] >= 3 for item in high_tier_rows
        ),
        "high_tier_rows": high_tier_rows,
        "temporal_slices": {
            key: {
                "entries": int(value["entries"]),
                "observed_stressed_net": rounded(float(value["observed"])),
                "first_order_adjusted_stressed_net": rounded(float(value["adjusted"])),
                "first_order_delta": rounded(float(value["adjusted"]) - float(value["observed"])),
            }
            for key, value in sorted(slices.items())
        },
    }


def main() -> None:
    runs: dict[str, dict[str, Any]] = {}
    for name, (folder, paths) in RUN_PATHS.items():
        rows = load_events(folder, paths)
        runs[name] = {
            "rows": rows,
            "lifecycles": build_lifecycle_map(rows),
            "sources": [source(folder / path) for path in paths],
        }

    results: list[dict[str, Any]] = []
    for spec in policy_specs():
        paths = {
            name: simulate(data["rows"], data["lifecycles"], spec)
            for name, data in runs.items()
        }
        active_paths = [
            path
            for name, path in paths.items()
            if name != "retained_baseline"
        ]
        net_delta = sum(path["first_order_net_delta"] for path in active_paths)
        dd_reduction = sum(-path["first_order_drawdown_delta"] for path in active_paths)
        worst_net_delta = min(path["first_order_net_delta"] for path in active_paths)
        worst_dd_increase = max(path["first_order_drawdown_delta"] for path in active_paths)
        retained_high_tier = sum(
            path["selected_high_tier_market_entries"] for path in active_paths
        )
        results.append(
            {
                "policy": spec,
                "aggregate": {
                    "first_order_net_delta": rounded(net_delta),
                    "drawdown_reduction": rounded(dd_reduction),
                    "worst_path_net_delta": rounded(worst_net_delta),
                    "worst_path_drawdown_increase": rounded(worst_dd_increase),
                    "selected_high_tier_market_entries": retained_high_tier,
                    "score": rounded(net_delta + 0.5 * dd_reduction),
                },
                "paths": paths,
            }
        )
    anchor = next(
        item for item in results if item["policy"]["family"] == "observed_discrete_anchor"
    )
    survivors = [
        item
        for item in results
        if item["policy"]["family"] not in {
            "observed_discrete_anchor",
            "diagnostic_cap_at_2x",
        }
        and item["aggregate"]["worst_path_net_delta"] >= 0.0
        and item["aggregate"]["worst_path_drawdown_increase"] <= 0.0
        and item["paths"]["retained_baseline"]["first_order_net_delta"] == 0.0
    ]
    survivors.sort(key=lambda item: item["aggregate"]["score"], reverse=True)
    diagnostic_cap = next(
        item for item in results if item["policy"]["family"] == "diagnostic_cap_at_2x"
    )
    payload = {
        "unit": "capital-step-elasticity-008",
        "question": "Can adjacent integer volume tiers be mixed causally across opportunities to smooth high-tier exposure without dropping entries?",
        "architecture": {
            "measurement": "reuse_current_next_lab_transition_lifecycles",
            "proxy": "third_tier_only_hard_escrow_and_sigma_delta_exposure_clocks",
            "runtime": "deferred_until_allocator_scope_and_band_are_selected",
        },
        "mechanism": {
            "target": "Only 2x-to-3x and higher transitions are softened; the economically productive 1x-to-2x transition remains unchanged.",
            "component_clock": "Each strategy accumulates its own fractional upper-tier credit, preventing physical evaluation order from assigning all larger positions to one strategy.",
            "downcross_reset": "Fractional credit can be cleared when the portfolio falls below the high-tier boundary so stale exposure debt does not survive a failed crossing.",
            "entry_constraint": "Every observed opportunity remains an entry; only its adjacent integer volume tier changes.",
        },
        "search": {
            "hypotheses": len(results),
            "anchor": anchor,
            "diagnostic_cap_at_2x": diagnostic_cap,
            "survivors": len(survivors),
            "top_survivors": survivors[:20],
            "limit": "This first-order proxy rescales observed stressed outcomes. Because volume changes stop geometry and later balances, real-tick runtime mutation remains decisive.",
        },
        "observed_high_tier_events": {
            name: anchor["paths"][name]["high_tier_rows"]
            for name in runs
        },
        "sources": {
            "capital_phase_runtime": source(
                ROOT / "lab" / "frontier" / "capital-step-phase" / "runtime.json"
            ),
            "event_paths": {name: data["sources"] for name, data in runs.items()},
        },
    }
    output = FRONTIER / "proxy.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
