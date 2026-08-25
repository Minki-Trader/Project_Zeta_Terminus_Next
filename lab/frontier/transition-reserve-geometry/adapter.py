#!/usr/bin/env python3
"""Recenter transition-reserve mechanisms across capital scales and later tiers."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
FRONTIER = ROOT / "lab" / "frontier" / "transition-reserve-geometry"
ARTIFACTS = ROOT / "lab" / "artifacts" / "backtests" / "slot-shadow-price"
EVENT_NAMES = [
    "extended-market-only-loser-residual-slot-shadow-exchange-v1-events-a.csv",
    "extended-market-only-loser-residual-slot-shadow-exchange-v1-events-b.csv",
]
REFERENCE_DEPOSIT = 100.0
REFERENCE_STEP = 150.0
POSITION_RISK_FRACTION = 0.04
AGGREGATE_RISK_FRACTION = 0.12
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


def load_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in EVENT_NAMES:
        with (ARTIFACTS / name).open("r", encoding="utf-8", newline="") as handle:
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


def lifecycles(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    active: dict[str, tuple[dict[str, Any], int]] = {}
    output: list[dict[str, Any]] = []
    raw_tier = 1
    for row in rows:
        if row["event"] == "SIZE_DAY":
            raw_tier = int(round(row["value_b_number"]))
        elif row["component_id"] not in COMPONENT_IDS:
            continue
        elif row["event"] in {"OPEN", "PASSIVE_FILL"}:
            active[row["component_id"]] = (row, raw_tier)
        elif row["event"] in {"CLOSE", "EXTERNAL_CLOSE"} and row["component_id"] in active:
            opened, entry_tier = active.pop(row["component_id"])
            output.append(
                {
                    "open_time": opened["time"],
                    "close_time": row["time"],
                    "server_time": opened["server_time"],
                    "component_id": row["component_id"],
                    "passive": row["component_id"] == PASSIVE_ID,
                    "raw_tier": entry_tier,
                    "observed_volume": opened["value_b_number"],
                    "balance": opened["stressed_balance_number"],
                    "stressed_net": row["value_b_number"],
                }
            )
    output.sort(key=lambda item: item["close_time"])
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


def policies() -> list[dict[str, Any]]:
    specs = [
        {
            "policy_id": "geometry-observed",
            "family": "observed_discrete",
            "parameter": 0.0,
            "economic_claim": "Immediate raw-tier allocation remains the reference path.",
        },
        {
            "policy_id": "geometry-fixed-20",
            "family": "fixed_dollar",
            "parameter": 20.0,
            "economic_claim": "A nominal 20 USD reserve transfers unchanged across account sizes.",
        },
        {
            "policy_id": "geometry-deposit-share-20",
            "family": "starting_capital_share",
            "parameter": 0.20,
            "economic_claim": "Reserve remains 20 percent of starting project capital.",
        },
        {
            "policy_id": "geometry-step-share-2of15",
            "family": "compounding_step_share",
            "parameter": 2.0 / 15.0,
            "economic_claim": "Reserve remains the observed 20/150 share of each scaled compounding step.",
        },
    ]
    for multiple in (0.75, 1.0, 1.25, 1.5, 2.0):
        specs.append(
            {
                "policy_id": f"geometry-position-budget-{str(multiple).replace('.', '_')}",
                "family": "prospective_position_budget",
                "parameter": multiple,
                "economic_claim": "Reserve scales with the 4 percent position-risk capacity at the prospective tier boundary.",
            }
        )
    specs.extend(
        [
            {
                "policy_id": "geometry-aggregate-slack",
                "family": "aggregate_minus_position_capacity",
                "parameter": 1.0,
                "economic_claim": "Reserve equals the gap between 12 percent aggregate and 4 percent single-position capacity at the boundary.",
            },
            {
                "policy_id": "geometry-stop-continuity",
                "family": "full_risk_bound_stop_continuity",
                "parameter": 1.0,
                "economic_claim": "Capital fully offsets the stop compression caused by one adjacent-tier volume increase when the risk cap binds.",
            },
        ]
    )
    return specs


def reserve_usd(policy: dict[str, Any], deposit: float, raw_tier: int) -> float:
    scale = deposit / REFERENCE_DEPOSIT
    step = REFERENCE_STEP * scale
    threshold = deposit + (raw_tier - 1) * step
    family = policy["family"]
    if family == "observed_discrete":
        return 0.0
    if family == "fixed_dollar":
        return policy["parameter"]
    if family == "starting_capital_share":
        return deposit * policy["parameter"]
    if family == "compounding_step_share":
        return step * policy["parameter"]
    if family == "prospective_position_budget":
        return threshold * POSITION_RISK_FRACTION * policy["parameter"]
    if family == "aggregate_minus_position_capacity":
        return threshold * (AGGREGATE_RISK_FRACTION - POSITION_RISK_FRACTION)
    if family == "full_risk_bound_stop_continuity":
        return threshold / max(1, raw_tier - 1)
    raise ValueError(f"unknown family {family}")


def temporal_slice(moment: datetime) -> str:
    if moment.year == 2025:
        return "2025"
    return "2026_h1" if moment < datetime(2026, 7, 1) else "2026_h2"


def simulate(
    path: list[dict[str, Any]], policy: dict[str, Any], deposit: float
) -> dict[str, Any]:
    scale = deposit / REFERENCE_DEPOSIT
    adjusted: list[float] = []
    observed: list[float] = []
    high_rows: list[dict[str, Any]] = []
    slices: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"entries": 0, "observed": 0.0, "adjusted": 0.0}
    )
    for lifecycle in path:
        raw_tier = lifecycle["raw_tier"]
        selected_tier = raw_tier
        scaled_balance = lifecycle["balance"] * scale
        if raw_tier >= 3 and not lifecycle["passive"]:
            threshold = deposit + (raw_tier - 1) * REFERENCE_STEP * scale
            reserve = reserve_usd(policy, deposit, raw_tier)
            if scaled_balance + 1.0e-9 < threshold + reserve:
                selected_tier = raw_tier - 1
            high_rows.append(
                {
                    "server_time": lifecycle["server_time"],
                    "component_id": lifecycle["component_id"],
                    "raw_tier": raw_tier,
                    "selected_tier": selected_tier,
                    "scaled_balance": rounded(scaled_balance),
                    "threshold": rounded(threshold),
                    "reserve": rounded(reserve),
                    "distance_into_tier": rounded(scaled_balance - threshold),
                }
            )
        ratio = selected_tier / raw_tier if not lifecycle["passive"] else 1.0
        observed_net = lifecycle["stressed_net"] * scale
        adjusted_net = observed_net * ratio
        observed.append(observed_net)
        adjusted.append(adjusted_net)
        key = temporal_slice(lifecycle["close_time"])
        slices[key]["entries"] += 1
        slices[key]["observed"] += observed_net
        slices[key]["adjusted"] += adjusted_net
    return {
        "deposit": deposit,
        "entries": len(path),
        "high_tier_market_opportunities": len(high_rows),
        "lower_tier_allocations": sum(
            row["selected_tier"] < row["raw_tier"] for row in high_rows
        ),
        "upper_tier_allocations": sum(
            row["selected_tier"] == row["raw_tier"] for row in high_rows
        ),
        "observed_stressed_net": rounded(sum(observed)),
        "first_order_adjusted_stressed_net": rounded(sum(adjusted)),
        "first_order_net_delta": rounded(sum(adjusted) - sum(observed)),
        "observed_stressed_drawdown": drawdown(observed),
        "first_order_adjusted_drawdown": drawdown(adjusted),
        "first_order_drawdown_delta": rounded(drawdown(adjusted) - drawdown(observed)),
        "high_tier_rows": high_rows,
        "temporal_slices": {
            key: {
                "entries": int(values["entries"]),
                "observed_stressed_net": rounded(float(values["observed"])),
                "first_order_adjusted_stressed_net": rounded(float(values["adjusted"])),
                "first_order_delta": rounded(float(values["adjusted"]) - float(values["observed"])),
            }
            for key, values in sorted(slices.items())
        },
    }


def geometry_table(policy: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for deposit in (100.0, 200.0, 300.0):
        scale = deposit / REFERENCE_DEPOSIT
        step = REFERENCE_STEP * scale
        for raw_tier in range(3, 9):
            threshold = deposit + (raw_tier - 1) * step
            reserve = reserve_usd(policy, deposit, raw_tier)
            output.append(
                {
                    "deposit": deposit,
                    "raw_tier": raw_tier,
                    "threshold": rounded(threshold),
                    "reserve": rounded(reserve),
                    "reserve_to_deposit": rounded(reserve / deposit),
                    "reserve_to_step": rounded(reserve / step),
                    "reserve_to_threshold": rounded(reserve / threshold),
                }
            )
    return output


def main() -> None:
    rows = load_events()
    path = lifecycles(rows)
    results: list[dict[str, Any]] = []
    for policy in policies():
        paths = {
            str(int(deposit)): simulate(path, policy, deposit)
            for deposit in (100.0, 200.0, 300.0)
        }
        results.append(
            {
                "policy": policy,
                "paths": paths,
                "geometry": geometry_table(policy),
                "aggregate": {
                    "first_order_net_delta": rounded(
                        sum(item["first_order_net_delta"] for item in paths.values())
                    ),
                    "drawdown_reduction": rounded(
                        sum(-item["first_order_drawdown_delta"] for item in paths.values())
                    ),
                    "worst_net_delta": rounded(
                        min(item["first_order_net_delta"] for item in paths.values())
                    ),
                    "worst_drawdown_increase": rounded(
                        max(item["first_order_drawdown_delta"] for item in paths.values())
                    ),
                },
            }
        )
    survivors = [
        item
        for item in results
        if item["policy"]["family"] != "observed_discrete"
        and item["aggregate"]["worst_net_delta"] >= 0.0
        and item["aggregate"]["worst_drawdown_increase"] <= 0.0
    ]
    survivors.sort(
        key=lambda item: (
            item["aggregate"]["first_order_net_delta"]
            + 0.5 * item["aggregate"]["drawdown_reduction"]
        ),
        reverse=True,
    )
    selected_id = "geometry-position-budget-1_25"
    selected = next(item for item in results if item["policy"]["policy_id"] == selected_id)
    payload = {
        "unit": "transition-reserve-geometry-009",
        "question": "Can the 20 USD third-tier reserve become deposit- and tier-aware marginal risk-capacity geometry?",
        "architecture": {
            "measurement": "reuse_current_next_lab_broad_slot_exchange_lifecycles",
            "proxy": "linear_capital_recentering_plus_analytic_later_tier_geometry",
            "runtime": "deferred_to_few_mechanism_distinct_real_tick_paths",
        },
        "scaling_contract": {
            "deposits": [100, 200, 300],
            "base_volume": "0.01 lots per 100 USD starting capital",
            "compounding_step": "150 percent of starting capital",
            "position_risk": POSITION_RISK_FRACTION,
            "aggregate_risk": AGGREGATE_RISK_FRACTION,
            "softened_transitions": "raw multiplier 3 and higher; the productive 1-to-2 transition remains immediate",
        },
        "hypotheses": len(results),
        "results": results,
        "survivors": [item["policy"]["policy_id"] for item in survivors],
        "mechanism_selection": {
            "policy_id": selected_id,
            "reason": "At the observed 100 USD third-tier boundary, 1.25 times the prospective 4 percent position budget equals the successful 20 USD reserve. Unlike nominal dollars or a constant step share, it scales with both starting capital and every later tier threshold while preserving all opportunities.",
            "selected_paths": selected["paths"],
            "runtime_plan": [
                "linear-capital anchors at 200 and 300 USD",
                "prospective-position-budget reserve at 200 and 300 USD",
                "fixed-20-dollar reserve at 300 USD as a scale-breaking falsification",
            ],
        },
        "limit": "The proxy assumes deposit-proportional outcomes and rescales observed closes. It cannot reproduce changed stops, margin, risk admission, slot exchange, or endogenous balance paths; real-tick runtime is decisive.",
        "sources": {
            "capital_elasticity_runtime": source(
                ROOT / "lab" / "frontier" / "capital-step-elasticity" / "runtime.json"
            ),
            "events": [source(ARTIFACTS / name) for name in EVENT_NAMES],
        },
    }
    output = FRONTIER / "proxy.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
