from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


SCRIPT_PATH = Path(__file__).resolve()
CAMPAIGN_ROOT = SCRIPT_PATH.parents[1]
REPOSITORY_ROOT = SCRIPT_PATH.parents[4]
CONFIG_PATH = CAMPAIGN_ROOT / "config" / "proxy-contract.json"
TIME_FORMAT = "%Y.%m.%d %H:%M:%S"


@dataclass(frozen=True)
class Lifecycle:
    identifier: str
    component_index: int
    birth_time: datetime
    close_time: datetime
    birth_order: int
    close_order: int
    source_volume_lots: float
    source_planned_risk_usd: float
    actual_net_usd: float
    stressed_net_usd: float


@dataclass(frozen=True)
class ReplayEvent:
    order: int
    event: str
    lifecycle: Lifecycle


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, TIME_FORMAT)


def iso_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def verify_and_load_lifecycles(
    config: dict[str, Any],
) -> tuple[Path, list[Lifecycle]]:
    declared = config["input"]
    path = REPOSITORY_ROOT / str(declared["path"])
    if path.stat().st_size != int(declared["bytes"]):
        raise RuntimeError("staged lifecycle byte count mismatch")
    if sha256(path) != str(declared["sha256"]):
        raise RuntimeError("staged lifecycle hash mismatch")

    components = [str(item["id"]) for item in config["components"]]
    component_index = {value: index for index, value in enumerate(components)}
    births: dict[str, dict[str, Any]] = {}
    closes: dict[str, dict[str, Any]] = {}
    row_count = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for order, row in enumerate(csv.DictReader(handle)):
            row_count += 1
            event = row["event"]
            if event not in {"BIRTH", "CLOSE"}:
                continue
            identifier = row["position_identifier"]
            if row["component_id"] not in component_index:
                raise RuntimeError("undeclared component in lifecycle input")
            target = births if event == "BIRTH" else closes
            if identifier in target:
                raise RuntimeError(f"duplicate {event} identifier")
            target[identifier] = {
                "order": order,
                "time": parse_time(row["server_time"]),
                "component": component_index[row["component_id"]],
                "volume": float(row["volume"]),
                "planned_risk": float(row["planned_risk_usd"]),
                "actual": float(row["actual_net_usd"]),
                "stressed": float(row["stressed_net_usd"]),
            }

    if row_count != int(declared["rows"]):
        raise RuntimeError("staged lifecycle row count mismatch")
    if set(births) != set(closes):
        raise RuntimeError("birth/close identity mismatch")
    if len(births) != int(declared["matched_lifecycles"]):
        raise RuntimeError("matched lifecycle count mismatch")

    lifecycles: list[Lifecycle] = []
    counts = np.zeros(len(components), dtype=np.int32)
    for identifier, birth in births.items():
        close = closes[identifier]
        if birth["component"] != close["component"]:
            raise RuntimeError("component changed within lifecycle")
        if birth["volume"] <= 0.0 or birth["planned_risk"] <= 0.0:
            raise RuntimeError("source birth has nonpositive volume or planned risk")
        counts[birth["component"]] += 1
        lifecycles.append(
            Lifecycle(
                identifier=identifier,
                component_index=int(birth["component"]),
                birth_time=birth["time"],
                close_time=close["time"],
                birth_order=int(birth["order"]),
                close_order=int(close["order"]),
                source_volume_lots=float(birth["volume"]),
                source_planned_risk_usd=float(birth["planned_risk"]),
                actual_net_usd=float(close["actual"]),
                stressed_net_usd=float(close["stressed"]),
            )
        )

    expected_counts = np.asarray(
        [int(item["source_births"]) for item in config["components"]],
        dtype=np.int32,
    )
    if not np.array_equal(counts, expected_counts):
        raise RuntimeError("component birth count mismatch")
    actual = sum(item.actual_net_usd for item in lifecycles)
    stressed = sum(item.stressed_net_usd for item in lifecycles)
    if abs(actual - float(declared["actual_net_usd"])) > 1.0e-7:
        raise RuntimeError("source actual net mismatch")
    if abs(stressed - float(declared["stressed_net_usd"])) > 1.0e-7:
        raise RuntimeError("source stressed net mismatch")
    lifecycles.sort(key=lambda item: item.birth_order)
    return path, lifecycles


def build_lattice(config: dict[str, Any]) -> dict[str, np.ndarray]:
    grids = [list(map(float, item["grid"])) for item in config["components"]]
    grids.append(list(map(float, config["base_position_risk_grid"])))
    grids.append(list(map(float, config["aggregate_risk_grid"])))
    index_ranges = [range(len(grid)) for grid in grids]
    coordinates = np.asarray(
        list(itertools.product(*index_ranges)), dtype=np.int16
    )
    values = np.asarray(
        [[grids[axis][int(index)] for axis, index in enumerate(row)] for row in coordinates],
        dtype=np.float64,
    )
    if len(values) != int(config["expected_parameterizations"]):
        raise RuntimeError("declared lattice size mismatch")
    component_count = len(config["components"])
    weights = values[:, :component_count]
    position_risk = values[:, component_count]
    aggregate_risk = values[:, component_count + 1]
    source_weights = np.asarray(
        [float(item["source_weight"]) for item in config["components"]],
        dtype=np.float64,
    )
    source_position_risk = float(config["source_base_position_risk_fraction"])
    effective = weights * position_risk[:, None]
    source_effective = source_weights * source_position_risk
    if np.any(effective > source_effective[None, :] + 1.0e-12):
        raise RuntimeError("lattice violates monotone effective-risk rule")
    return {
        "coordinates": coordinates,
        "values": values,
        "weights": weights,
        "position_risk": position_risk,
        "aggregate_risk": aggregate_risk,
    }


def events_for_period(
    lifecycles: list[Lifecycle], start: datetime | None, end: datetime | None
) -> list[ReplayEvent]:
    selected = [
        item
        for item in lifecycles
        if (start is None or item.close_time >= start)
        and (end is None or item.close_time < end)
    ]
    events: list[ReplayEvent] = []
    for item in selected:
        events.append(ReplayEvent(item.birth_order, "BIRTH", item))
        events.append(ReplayEvent(item.close_order, "CLOSE", item))
    events.sort(key=lambda item: item.order)
    return events


def simulate(
    lifecycles: list[Lifecycle],
    parameter_values: np.ndarray,
    config: dict[str, Any],
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, np.ndarray]:
    component_count = len(config["components"])
    candidate_count = parameter_values.shape[0]
    weights = parameter_values[:, :component_count]
    position_risk = parameter_values[:, component_count]
    aggregate_risk = parameter_values[:, component_count + 1]
    source_weights = np.asarray(
        [float(item["source_weight"]) for item in config["components"]],
        dtype=np.float64,
    )
    source_position_risk = float(config["source_base_position_risk_fraction"])
    volume_step = float(config["volume_step_lots"])
    reference = float(config["reference_capital_usd"])
    tolerance = float(config["aggregate_tolerance_usd"])

    actual_balance = np.full(candidate_count, reference, dtype=np.float64)
    stressed_balance = np.full(candidate_count, reference, dtype=np.float64)
    actual_peak = actual_balance.copy()
    stressed_peak = stressed_balance.copy()
    actual_dd = np.zeros(candidate_count, dtype=np.float64)
    stressed_dd = np.zeros(candidate_count, dtype=np.float64)
    minimum_balance = np.full(candidate_count, reference, dtype=np.float64)
    open_risk = np.zeros(candidate_count, dtype=np.float64)
    accepted = np.zeros(candidate_count, dtype=np.int32)
    aggregate_skips = np.zeros(candidate_count, dtype=np.int32)
    disabled = np.zeros(candidate_count, dtype=np.int32)
    component_actual = np.zeros((candidate_count, component_count), dtype=np.float64)
    component_stressed = np.zeros_like(component_actual)
    component_closed = np.zeros((candidate_count, component_count), dtype=np.int32)
    open_positions: dict[str, tuple[np.ndarray, np.ndarray, int]] = {}

    for event in events_for_period(lifecycles, start, end):
        item = event.lifecycle
        component = item.component_index
        if event.event == "BIRTH":
            if item.identifier in open_positions:
                raise RuntimeError("duplicate replay birth")
            source_steps = int(math.floor(item.source_volume_lots / volume_step + 0.5))
            if source_steps < 1:
                raise RuntimeError("invalid source volume lattice")
            ratio = (
                weights[:, component] * position_risk
                / (source_weights[component] * source_position_risk)
            )
            target_steps = np.floor(source_steps * ratio + 0.5).astype(np.int32)
            target_steps = np.clip(target_steps, 0, source_steps)
            scale = target_steps.astype(np.float64) / float(source_steps)
            planned_risk = item.source_planned_risk_usd * scale
            conservative_balance = np.minimum(actual_balance, stressed_balance)
            aggregate_budget = conservative_balance * aggregate_risk
            enabled = target_steps > 0
            admitted = (
                enabled
                & (conservative_balance > 0.0)
                & (open_risk + planned_risk <= aggregate_budget + tolerance)
            )
            admitted_steps = np.where(admitted, target_steps, 0).astype(np.int32)
            admitted_risk = np.where(admitted, planned_risk, 0.0)
            accepted += admitted.astype(np.int32)
            disabled += (~enabled).astype(np.int32)
            aggregate_skips += (enabled & ~admitted).astype(np.int32)
            open_risk += admitted_risk
            open_positions[item.identifier] = (
                admitted_steps,
                admitted_risk,
                source_steps,
            )
            continue

        if item.identifier not in open_positions:
            raise RuntimeError("replay close has no birth")
        admitted_steps, admitted_risk, source_steps = open_positions.pop(item.identifier)
        scale = admitted_steps.astype(np.float64) / float(source_steps)
        actual_increment = item.actual_net_usd * scale
        stressed_increment = item.stressed_net_usd * scale
        actual_balance += actual_increment
        stressed_balance += stressed_increment
        open_risk = np.maximum(0.0, open_risk - admitted_risk)
        component_actual[:, component] += actual_increment
        component_stressed[:, component] += stressed_increment
        component_closed[:, component] += (admitted_steps > 0).astype(np.int32)
        actual_peak = np.maximum(actual_peak, actual_balance)
        stressed_peak = np.maximum(stressed_peak, stressed_balance)
        actual_dd = np.maximum(
            actual_dd,
            np.where(actual_peak > 0.0, (actual_peak - actual_balance) / actual_peak, np.inf),
        )
        stressed_dd = np.maximum(
            stressed_dd,
            np.where(
                stressed_peak > 0.0,
                (stressed_peak - stressed_balance) / stressed_peak,
                np.inf,
            ),
        )
        minimum_balance = np.minimum(
            minimum_balance, np.minimum(actual_balance, stressed_balance)
        )

    if open_positions:
        raise RuntimeError("period replay ended with unmatched open positions")
    return {
        "actual_net": actual_balance - reference,
        "stressed_net": stressed_balance - reference,
        "drawdown_pct": np.maximum(actual_dd, stressed_dd) * 100.0,
        "minimum_balance": minimum_balance,
        "accepted": accepted,
        "aggregate_skips": aggregate_skips,
        "disabled": disabled,
        "component_actual": component_actual,
        "component_stressed": component_stressed,
        "component_closed": component_closed,
    }


def period_bounds(config: dict[str, Any], name: str) -> tuple[datetime, datetime]:
    values = config["periods"][name]
    return iso_time(values[0]), iso_time(values[1])


def find_anchor_index(lattice: dict[str, np.ndarray], config: dict[str, Any]) -> int:
    anchor = config["anchor_reproduction"]
    target = np.asarray(
        list(map(float, anchor["weights"]))
        + [float(anchor["base_position_risk_fraction"])]
        + [float(anchor["aggregate_risk_fraction"])],
        dtype=np.float64,
    )
    matches = np.flatnonzero(np.all(np.isclose(lattice["values"], target), axis=1))
    if len(matches) != 1:
        raise RuntimeError("exact anchor absent or duplicated")
    return int(matches[0])


def record(
    index: int,
    parameter_values: np.ndarray,
    metrics: dict[str, np.ndarray],
    config: dict[str, Any],
    coordinate: np.ndarray | None = None,
) -> dict[str, Any]:
    component_count = len(config["components"])
    result: dict[str, Any] = {
        "weights": [float(value) for value in parameter_values[index, :component_count]],
        "base_position_risk_fraction": float(parameter_values[index, component_count]),
        "aggregate_risk_fraction": float(parameter_values[index, component_count + 1]),
        "actual_net_usd": float(metrics["actual_net"][index]),
        "stressed_net_usd": float(metrics["stressed_net"][index]),
        "raw_closed_balance_drawdown_pct": float(metrics["drawdown_pct"][index]),
        "minimum_balance_usd": float(metrics["minimum_balance"][index]),
        "accepted_source_lifecycles": int(metrics["accepted"][index]),
        "aggregate_skips_within_source_path": int(metrics["aggregate_skips"][index]),
        "disabled_by_zero_executable_volume": int(metrics["disabled"][index]),
    }
    if coordinate is not None:
        result["lattice_coordinate"] = [int(value) for value in coordinate]
    components: list[dict[str, Any]] = []
    for component_index, component in enumerate(config["components"]):
        components.append(
            {
                "short": str(component["short"]),
                "closed": int(metrics["component_closed"][index, component_index]),
                "actual_net_usd": float(metrics["component_actual"][index, component_index]),
                "stressed_net_usd": float(metrics["component_stressed"][index, component_index]),
            }
        )
    result["components"] = components
    return result


def positive(metrics: dict[str, np.ndarray]) -> np.ndarray:
    return (
        (metrics["actual_net"] > 0.0)
        & (metrics["stressed_net"] > 0.0)
        & (metrics["minimum_balance"] > 0.0)
    )


def choose_plateau_centers(
    eligible: np.ndarray,
    lattice: dict[str, np.ndarray],
    development: dict[str, np.ndarray],
    config: dict[str, Any],
    anchor_coordinate: np.ndarray,
) -> tuple[list[int], list[dict[str, Any]]]:
    coordinates = lattice["coordinates"]
    coordinate_to_index = {
        tuple(int(value) for value in row): index for index, row in enumerate(coordinates)
    }
    eligible_set = set(int(value) for value in np.flatnonzero(eligible))
    minimum_neighbors = int(config["gates"]["minimum_eligible_neighbors"])
    minimum_axes = int(config["gates"]["minimum_neighbor_axes"])
    plateau: list[dict[str, Any]] = []
    for index in eligible_set:
        coordinate = coordinates[index]
        neighbor_indices: list[int] = []
        neighbor_axes: set[int] = set()
        for axis in range(coordinates.shape[1]):
            for delta in (-1, 1):
                probe = coordinate.copy()
                probe[axis] += delta
                neighbor = coordinate_to_index.get(tuple(int(value) for value in probe))
                if neighbor is not None and neighbor in eligible_set:
                    neighbor_indices.append(neighbor)
                    neighbor_axes.add(axis)
        if len(neighbor_indices) < minimum_neighbors or len(neighbor_axes) < minimum_axes:
            continue
        local = [index] + neighbor_indices
        local_efficiency = [
            float(development["stressed_net"][value])
            / max(float(development["drawdown_pct"][value]), 1.0e-12)
            for value in local
        ]
        plateau.append(
            {
                "index": index,
                "eligible_neighbor_count": len(neighbor_indices),
                "neighbor_axis_count": len(neighbor_axes),
                "worst_local_stressed_net_to_drawdown": min(local_efficiency),
                "distance_from_anchor": int(np.abs(coordinate - anchor_coordinate).sum()),
            }
        )
    plateau.sort(
        key=lambda item: (
            -item["worst_local_stressed_net_to_drawdown"],
            -float(development["stressed_net"][item["index"]]),
            float(development["drawdown_pct"][item["index"]]),
            item["distance_from_anchor"],
            tuple(int(value) for value in coordinates[item["index"]]),
        )
    )
    maximum = int(config["gates"]["maximum_validation_centers"])
    separation = int(config["gates"]["minimum_center_manhattan_separation"])
    selected: list[int] = []
    selected_meta: list[dict[str, Any]] = []
    for item in plateau:
        coordinate = coordinates[item["index"]]
        if any(
            int(np.abs(coordinate - coordinates[prior]).sum()) < separation
            for prior in selected
        ):
            continue
        selected.append(int(item["index"]))
        selected_meta.append(item)
        if len(selected) == maximum:
            break
    return selected, selected_meta


def rounded(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [rounded(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 9)
    return value


def main() -> None:
    started = time.perf_counter()
    config = load_config()
    input_path, lifecycles = verify_and_load_lifecycles(config)
    lattice = build_lattice(config)
    anchor_index = find_anchor_index(lattice, config)
    anchor_coordinate = lattice["coordinates"][anchor_index]

    whole_anchor_metrics = simulate(
        lifecycles, lattice["values"][[anchor_index]], config
    )
    anchor = config["anchor_reproduction"]
    observed_anchor = record(0, lattice["values"][[anchor_index]], whole_anchor_metrics, config)
    if observed_anchor["accepted_source_lifecycles"] != int(anchor["accepted_lifecycles"]):
        raise RuntimeError("exact anchor accepted lifecycle reproduction failed")
    if abs(observed_anchor["actual_net_usd"] - float(anchor["actual_net_usd"])) > float(anchor["net_tolerance_usd"]):
        raise RuntimeError("exact anchor actual reproduction failed")
    if abs(observed_anchor["stressed_net_usd"] - float(anchor["stressed_net_usd"])) > float(anchor["net_tolerance_usd"]):
        raise RuntimeError("exact anchor stressed reproduction failed")
    if abs(observed_anchor["raw_closed_balance_drawdown_pct"] - float(anchor["closed_balance_drawdown_pct"])) > float(anchor["drawdown_tolerance_points"]):
        raise RuntimeError("exact anchor drawdown reproduction failed")

    development_start, development_end = period_bounds(config, "development")
    year_2024_start, year_2024_end = period_bounds(config, "development_2024")
    year_2025_start, year_2025_end = period_bounds(config, "development_2025")
    development = simulate(
        lifecycles, lattice["values"], config, development_start, development_end
    )
    year_2024 = simulate(
        lifecycles, lattice["values"], config, year_2024_start, year_2024_end
    )
    year_2025 = simulate(
        lifecycles, lattice["values"], config, year_2025_start, year_2025_end
    )
    development_anchor_stressed = float(development["stressed_net"][anchor_index])
    development_anchor_dd = float(development["drawdown_pct"][anchor_index])
    common = positive(development) & positive(year_2024) & positive(year_2025)
    primary = (
        common
        & (
            development["stressed_net"]
            >= development_anchor_stressed * float(config["gates"]["primary_stressed_retention"])
        )
        & (development["drawdown_pct"] <= float(config["gates"]["primary_max_drawdown_pct"]))
    )
    fallback = (
        common
        & (
            development["stressed_net"]
            >= development_anchor_stressed * float(config["gates"]["fallback_stressed_retention"])
        )
        & (
            development["drawdown_pct"]
            <= development_anchor_dd
            - float(config["gates"]["fallback_min_drawdown_improvement_points"])
        )
    )
    active_tier = "PRIMARY" if int(primary.sum()) > 0 else "FALLBACK_REHABILITATION"
    eligible = primary if active_tier == "PRIMARY" else fallback
    centers, center_meta = choose_plateau_centers(
        eligible, lattice, development, config, anchor_coordinate
    )

    result: dict[str, Any] = {
        "schema": "zeta-next-dd20-v8-clean-monotone-microfrontier-proxy-result-v1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "campaign": "dd20-v8-clean-monotone-microfrontier-proxy-v1",
        "optimization_unit_id": str(config["optimization_unit_id"]),
        "unit_stage": str(config["unit_stage"]),
        "unit_closure_authority": False,
        "input": {
            "path": str(config["input"]["path"]),
            "bytes": input_path.stat().st_size,
            "sha256": sha256(input_path),
            "matched_lifecycles": len(lifecycles),
        },
        "lattice": {
            "declared_parameterizations": int(len(lattice["values"])),
            "primary_eligible": int(primary.sum()),
            "fallback_eligible": int(fallback.sum()),
            "active_tier": active_tier,
            "active_tier_eligible": int(eligible.sum()),
        },
        "exact_anchor_whole_path": observed_anchor,
        "exact_anchor_development": record(
            anchor_index,
            lattice["values"],
            development,
            config,
            lattice["coordinates"][anchor_index],
        ),
        "development_plateau_population": 0,
        "development_centers": [],
        "validation": [],
        "winner": None,
        "locked_holdout": None,
        "winner_whole_path": None,
        "mt5": {
            "shortlist_count": 0,
            "valid_economic_paths_run": 0,
            "maximum_valid_economic_paths_authorized": int(
                config["mt5_budget"]["maximum_valid_economic_paths"]
            ),
        },
        "limitations": [
            "Accepted-source-path monotone replay only; freed-capacity opportunities are absent and receive zero credit.",
            "Closed-balance replay is not native MT5 open-equity drawdown or final economics.",
        ],
    }

    # The helper returns only separated centers; count every robust point directly.
    coordinates = lattice["coordinates"]
    coordinate_to_index = {
        tuple(int(value) for value in row): index for index, row in enumerate(coordinates)
    }
    eligible_set = set(int(value) for value in np.flatnonzero(eligible))
    plateau_count = 0
    for index in eligible_set:
        axes: set[int] = set()
        neighbors = 0
        for axis in range(coordinates.shape[1]):
            for delta in (-1, 1):
                probe = coordinates[index].copy()
                probe[axis] += delta
                neighbor = coordinate_to_index.get(tuple(int(value) for value in probe))
                if neighbor is not None and neighbor in eligible_set:
                    neighbors += 1
                    axes.add(axis)
        if neighbors >= int(config["gates"]["minimum_eligible_neighbors"]) and len(axes) >= int(config["gates"]["minimum_neighbor_axes"]):
            plateau_count += 1
    result["development_plateau_population"] = plateau_count

    for rank, (index, meta) in enumerate(zip(centers, center_meta), start=1):
        item = record(
            index,
            lattice["values"],
            development,
            config,
            lattice["coordinates"][index],
        )
        item.update(
            {
                "development_rank": rank,
                "eligible_neighbor_count": int(meta["eligible_neighbor_count"]),
                "neighbor_axis_count": int(meta["neighbor_axis_count"]),
                "worst_local_stressed_net_to_drawdown": float(
                    meta["worst_local_stressed_net_to_drawdown"]
                ),
                "distance_from_anchor": int(meta["distance_from_anchor"]),
                "development_2024": record(
                    index, lattice["values"], year_2024, config
                ),
                "development_2025": record(
                    index, lattice["values"], year_2025, config
                ),
            }
        )
        result["development_centers"].append(item)

    if not centers:
        result["status"] = (
            "VALID_PROXY_COMPLETE_NO_DEVELOPMENT_ELIGIBLE_NO_MT5"
            if int(eligible.sum()) == 0
            else "VALID_PROXY_COMPLETE_NO_ROBUST_PLATEAU_NO_MT5"
        )
    else:
        validation_start, validation_end = period_bounds(config, "validation")
        validation_values = lattice["values"][centers]
        validation = simulate(
            lifecycles, validation_values, config, validation_start, validation_end
        )
        validation_pass = positive(validation) & (
            validation["drawdown_pct"]
            <= float(config["gates"]["validation_max_drawdown_pct"])
        )
        passing_roles: list[int] = []
        for local_index, global_index in enumerate(centers):
            item = record(
                local_index,
                validation_values,
                validation,
                config,
                lattice["coordinates"][global_index],
            )
            item["development_rank"] = local_index + 1
            item["passed"] = bool(validation_pass[local_index])
            result["validation"].append(item)
            if validation_pass[local_index]:
                passing_roles.append(local_index)
        if not passing_roles:
            result["status"] = "VALID_PROXY_COMPLETE_VALIDATION_NONCONFIRMATION_NO_MT5"
        else:
            passing_roles.sort(
                key=lambda local_index: (
                    -float(validation["stressed_net"][local_index])
                    / max(float(validation["drawdown_pct"][local_index]), 1.0e-12),
                    -float(validation["stressed_net"][local_index]),
                    float(validation["drawdown_pct"][local_index]),
                    local_index,
                )
            )
            winner_local = passing_roles[0]
            winner_global = centers[winner_local]
            result["winner"] = {
                "development_rank": winner_local + 1,
                "lattice_index": int(winner_global),
                "parameters": record(
                    winner_local,
                    validation_values,
                    validation,
                    config,
                    lattice["coordinates"][winner_global],
                ),
            }
            holdout_start, holdout_end = period_bounds(config, "locked_holdout")
            winner_values = lattice["values"][[winner_global]]
            holdout = simulate(
                lifecycles, winner_values, config, holdout_start, holdout_end
            )
            holdout_pass = bool(
                positive(holdout)[0]
                and holdout["drawdown_pct"][0]
                <= float(config["gates"]["holdout_max_drawdown_pct"])
            )
            result["locked_holdout"] = record(
                0,
                winner_values,
                holdout,
                config,
                lattice["coordinates"][winner_global],
            )
            result["locked_holdout"]["passed"] = holdout_pass
            whole = simulate(lifecycles, winner_values, config)
            result["winner_whole_path"] = record(
                0,
                winner_values,
                whole,
                config,
                lattice["coordinates"][winner_global],
            )
            final_pass = bool(
                holdout_pass
                and positive(whole)[0]
                and whole["stressed_net"][0]
                >= float(observed_anchor["stressed_net_usd"])
                * float(config["gates"]["final_minimum_stressed_retention"])
                and whole["drawdown_pct"][0]
                <= float(observed_anchor["raw_closed_balance_drawdown_pct"])
                - float(config["gates"]["final_minimum_drawdown_improvement_points"])
            )
            if final_pass:
                result["status"] = "VALID_PROXY_COMPLETE_ONE_MT5_SHORTLIST"
                result["mt5"]["shortlist_count"] = 1
            elif not holdout_pass:
                result["status"] = "VALID_PROXY_COMPLETE_LOCKED_HOLDOUT_NONCONFIRMATION_NO_MT5"
            else:
                result["status"] = "VALID_PROXY_COMPLETE_WHOLE_PATH_GATE_NONCONFIRMATION_NO_MT5"

    result["implementation"] = {
        "script_path": str(SCRIPT_PATH.relative_to(REPOSITORY_ROOT)).replace("\\", "/"),
        "script_sha256": sha256(SCRIPT_PATH),
        "config_path": str(CONFIG_PATH.relative_to(REPOSITORY_ROOT)).replace("\\", "/"),
        "config_sha256": sha256(CONFIG_PATH),
        "wall_time_seconds": time.perf_counter() - started,
        "mt5_runs": 0,
        "external_data": False,
    }
    output_path = REPOSITORY_ROOT / str(config["output"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(rounded(result), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(output_path),
                "wall_time_seconds": result["implementation"]["wall_time_seconds"],
                "mt5_shortlist_count": result["mt5"]["shortlist_count"],
            }
        )
    )


if __name__ == "__main__":
    main()
