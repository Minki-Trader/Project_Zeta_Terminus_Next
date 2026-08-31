from __future__ import annotations

import csv
import hashlib
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
    source_account_balance_usd: float
    source_account_equity_usd: float
    source_risk_capital_usd: float
    source_position_cap_usd: float
    source_aggregate_cap_usd: float
    source_risk_capital_haircut_ratio: float
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


def verify_authority_and_stage_b(
    config: dict[str, Any],
) -> tuple[dict[str, Path], dict[str, Any], dict[str, Any]]:
    authority = config["declaration_authority"]
    authority_paths: dict[str, Path] = {}
    for role in ("declaration", "correction"):
        path = REPOSITORY_ROOT / str(authority[f"{role}_path"])
        if path.stat().st_size != int(authority[f"{role}_bytes"]):
            raise RuntimeError(f"{role} authority byte count mismatch")
        if sha256(path) != str(authority[f"{role}_sha256"]):
            raise RuntimeError(f"{role} authority hash mismatch")
        authority_paths[role] = path

    declared_inputs = config["inputs"]
    input_root = REPOSITORY_ROOT / str(declared_inputs["root"])
    input_paths: dict[str, Path] = {}
    payloads: dict[str, dict[str, Any]] = {}
    for role in ("stage_b_raw", "stage_b_durable"):
        declared = declared_inputs[role]
        path = input_root / str(declared["name"])
        if path.stat().st_size != int(declared["bytes"]):
            raise RuntimeError(f"staged {role} byte count mismatch")
        if sha256(path) != str(declared["sha256"]):
            raise RuntimeError(f"staged {role} hash mismatch")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema") != str(declared["schema"]):
            raise RuntimeError(f"staged {role} schema mismatch")
        if payload.get("status") != str(declared["status"]):
            raise RuntimeError(f"staged {role} status mismatch")
        input_paths[role] = path
        payloads[role] = payload

    expected_seeds = config["static_seeds"]
    raw_centers = payloads["stage_b_raw"].get("development_centers", [])
    durable_centers = payloads["stage_b_durable"].get("development_centers", [])
    if len(raw_centers) != len(expected_seeds) or len(durable_centers) != len(
        expected_seeds
    ):
        raise RuntimeError("Stage-B center count mismatch")
    for index, expected in enumerate(expected_seeds):
        expected_weights = np.asarray(expected["weights"], dtype=np.float64)
        raw_weights = np.asarray(raw_centers[index]["weights"], dtype=np.float64)
        durable_weights = np.asarray(
            durable_centers[index]["weights"][: len(expected_weights)],
            dtype=np.float64,
        )
        passive = durable_centers[index]["weights"][len(expected_weights) :]
        if not np.array_equal(raw_weights, expected_weights):
            raise RuntimeError("raw Stage-B seed weights mismatch")
        if not np.array_equal(durable_weights, expected_weights):
            raise RuntimeError("durable Stage-B seed weights mismatch")
        if passive != [0.0]:
            raise RuntimeError("durable Stage-B Passive seed mismatch")
        expected_cap = float(expected["aggregate_risk_fraction"])
        if float(raw_centers[index]["aggregate_risk_fraction"]) != expected_cap:
            raise RuntimeError("raw Stage-B seed aggregate cap mismatch")
        if float(durable_centers[index]["aggregate_risk_fraction"]) != expected_cap:
            raise RuntimeError("durable Stage-B seed aggregate cap mismatch")
        if int(durable_centers[index]["rank"]) != index + 1:
            raise RuntimeError("durable Stage-B seed rank mismatch")

    return {**authority_paths, **input_paths}, payloads["stage_b_raw"], payloads[
        "stage_b_durable"
    ]


def verify_and_load_lifecycles(
    config: dict[str, Any],
) -> tuple[dict[str, Path], list[Lifecycle]]:
    declared_inputs = config["inputs"]
    input_root = REPOSITORY_ROOT / str(declared_inputs["root"])
    paths: dict[str, Path] = {}
    for role in ("lifecycle", "candidate"):
        declared = declared_inputs[role]
        path = input_root / str(declared["name"])
        if path.stat().st_size != int(declared["bytes"]):
            raise RuntimeError(f"staged {role} byte count mismatch")
        if sha256(path) != str(declared["sha256"]):
            raise RuntimeError(f"staged {role} hash mismatch")
        paths[role] = path

    lifecycle_declared = declared_inputs["lifecycle"]
    candidate_declared = declared_inputs["candidate"]

    components = [str(item["id"]) for item in config["components"]]
    component_index = {value: index for index, value in enumerate(components)}
    births: dict[str, dict[str, Any]] = {}
    closes: dict[str, dict[str, Any]] = {}
    row_count = 0
    with paths["lifecycle"].open("r", encoding="utf-8-sig", newline="") as handle:
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

    if row_count != int(lifecycle_declared["rows"]):
        raise RuntimeError("staged lifecycle row count mismatch")
    if set(births) != set(closes):
        raise RuntimeError("birth/close identity mismatch")
    if len(births) != int(lifecycle_declared["matched_lifecycles"]):
        raise RuntimeError("matched lifecycle count mismatch")

    open_contexts: dict[str, dict[str, float]] = {}
    with paths["candidate"].open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["result"] != "POSITION_OPEN":
                continue
            key = f"{row['component_id']}|{row['server_time']}"
            if key in open_contexts:
                raise RuntimeError("duplicate component/time POSITION_OPEN key")
            account_balance = float(row["account_balance"])
            account_equity = float(row["account_equity"])
            if account_balance <= 0.0 or account_equity <= 0.0:
                raise RuntimeError("nonpositive source account context")
            open_contexts[key] = {
                "volume": float(row["volume"]),
                "planned_risk": float(row["planned_risk_usd"]),
                "account_balance": account_balance,
                "account_equity": account_equity,
                "risk_capital": float(row["risk_capital_usd"]),
                "position_cap": float(row["position_cap_usd"]),
                "aggregate_cap": float(row["aggregate_cap_usd"]),
            }
    if len(open_contexts) != int(candidate_declared["position_open_rows"]):
        raise RuntimeError("POSITION_OPEN row count mismatch")
    if len(open_contexts) != int(candidate_declared["unique_component_time_open_keys"]):
        raise RuntimeError("POSITION_OPEN key count mismatch")

    lifecycles: list[Lifecycle] = []
    counts = np.zeros(len(components), dtype=np.int32)
    for identifier, birth in births.items():
        close = closes[identifier]
        if birth["component"] != close["component"]:
            raise RuntimeError("component changed within lifecycle")
        if birth["volume"] <= 0.0 or birth["planned_risk"] <= 0.0:
            raise RuntimeError("source birth has nonpositive volume or planned risk")
        component_id = components[int(birth["component"])]
        context_key = f"{component_id}|{birth['time'].strftime(TIME_FORMAT)}"
        if context_key not in open_contexts:
            raise RuntimeError("lifecycle birth has no POSITION_OPEN context")
        context = open_contexts[context_key]
        if abs(float(birth["volume"]) - context["volume"]) > float(
            config["anchor_reproduction"]["volume_tolerance_lots"]
        ):
            raise RuntimeError("lifecycle/candidate source volume mismatch")
        if abs(float(birth["planned_risk"]) - context["planned_risk"]) > 0.011:
            raise RuntimeError("lifecycle/candidate planned risk mismatch")
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
                source_account_balance_usd=context["account_balance"],
                source_account_equity_usd=context["account_equity"],
                source_risk_capital_usd=context["risk_capital"],
                source_position_cap_usd=context["position_cap"],
                source_aggregate_cap_usd=context["aggregate_cap"],
                source_risk_capital_haircut_ratio=min(
                    1.0, context["risk_capital"] / context["account_balance"]
                ),
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
    if abs(actual - float(lifecycle_declared["actual_net_usd"])) > 1.0e-7:
        raise RuntimeError("source actual net mismatch")
    if abs(stressed - float(lifecycle_declared["stressed_net_usd"])) > 1.0e-7:
        raise RuntimeError("source stressed net mismatch")
    lifecycles.sort(key=lambda item: item.birth_order)
    return paths, lifecycles


def build_lattice(config: dict[str, Any]) -> dict[str, Any]:
    membership = config["membership"]
    component_count = len(config["components"])
    aggregate_risk = float(config["aggregate_risk_fraction"])
    raw_roles: list[dict[str, Any]] = []
    grouped: dict[tuple[float, ...], list[dict[str, int]]] = {}
    for seed_index, seed in enumerate(config["static_seeds"]):
        seed_weights = list(map(float, seed["weights"]))
        if len(seed_weights) != component_count:
            raise RuntimeError("static seed component count mismatch")
        if float(seed["aggregate_risk_fraction"]) != aggregate_risk:
            raise RuntimeError("static seed aggregate cap mismatch")
        for mask in range(
            int(membership["first_nonempty_mask"]),
            int(membership["last_nonempty_mask"]) + 1,
        ):
            weights = tuple(
                seed_weights[axis] if mask & (1 << axis) else 0.0
                for axis in range(component_count)
            )
            provenance = {"seed_rank": seed_index + 1, "mask": mask}
            raw_roles.append({"weights": weights, **provenance})
            grouped.setdefault(weights, []).append(provenance)
    if len(raw_roles) != int(membership["raw_seed_mask_roles"]):
        raise RuntimeError("declared raw seed-mask role count mismatch")

    unique_weights = sorted(grouped)
    if len(unique_weights) != int(membership["deduplicated_exact_weight_roles"]):
        raise RuntimeError("declared deduplicated membership role count mismatch")
    if len(raw_roles) - len(unique_weights) != int(membership["duplicates_removed"]):
        raise RuntimeError("declared membership duplicate count mismatch")

    weights = np.asarray(unique_weights, dtype=np.float64)
    values = np.column_stack(
        [weights, np.full(len(weights), aggregate_risk, dtype=np.float64)]
    )
    masks = np.asarray(
        [
            sum((1 << axis) for axis, value in enumerate(row) if value > 0.0)
            for row in weights
        ],
        dtype=np.int16,
    )
    provenance = [
        sorted(grouped[key], key=lambda item: (item["seed_rank"], item["mask"]))
        for key in unique_weights
    ]
    weight_to_index = {key: index for index, key in enumerate(unique_weights)}
    adjacency: list[set[int]] = [set() for _ in unique_weights]
    for seed_index, seed in enumerate(config["static_seeds"]):
        seed_weights = list(map(float, seed["weights"]))
        mask_to_index: dict[int, int] = {}
        for mask in range(
            int(membership["first_nonempty_mask"]),
            int(membership["last_nonempty_mask"]) + 1,
        ):
            key = tuple(
                seed_weights[axis] if mask & (1 << axis) else 0.0
                for axis in range(component_count)
            )
            mask_to_index[mask] = weight_to_index[key]
        for mask, index in mask_to_index.items():
            for axis in range(component_count):
                neighbor_mask = mask ^ (1 << axis)
                if neighbor_mask < int(membership["first_nonempty_mask"]):
                    continue
                neighbor = mask_to_index[neighbor_mask]
                if neighbor != index:
                    adjacency[index].add(neighbor)
                    adjacency[neighbor].add(index)

    source_weights = np.asarray(
        [float(item["source_weight"]) for item in config["components"]],
        dtype=np.float64,
    )
    if np.any(weights > source_weights[None, :] + 1.0e-12):
        raise RuntimeError("membership lattice violates exact-V8 weight ceiling")
    if np.any(np.sum(weights > 0.0, axis=1) == 0):
        raise RuntimeError("empty membership reached executable lattice")
    return {
        "values": values,
        "weights": weights,
        "masks": masks,
        "provenance": provenance,
        "adjacency": adjacency,
        "raw_roles": raw_roles,
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
    aggregate_risk = parameter_values[:, component_count]
    position_risk = float(config["base_position_risk_fraction"])
    base_volume = float(config["base_volume_lots"])
    volume_step = float(config["volume_step_lots"])
    addition_step = float(config["addition_step_usd"])
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
    source_volume_matches = np.zeros(candidate_count, dtype=np.int32)
    source_risk_capital_matches = np.zeros(candidate_count, dtype=np.int32)
    source_position_cap_matches = np.zeros(candidate_count, dtype=np.int32)
    component_actual = np.zeros((candidate_count, component_count), dtype=np.float64)
    component_stressed = np.zeros_like(component_actual)
    component_closed = np.zeros((candidate_count, component_count), dtype=np.int32)
    open_positions: dict[str, tuple[np.ndarray, np.ndarray, int]] = {}
    day_multiplier = np.ones(candidate_count, dtype=np.int32)
    current_day = None

    for event in events_for_period(lifecycles, start, end):
        item = event.lifecycle
        component = item.component_index
        event_day = (
            item.birth_time.date() if event.event == "BIRTH" else item.close_time.date()
        )
        if event_day != current_day:
            growth = np.maximum(0.0, stressed_balance - reference)
            day_multiplier = 1 + np.floor(
                growth / addition_step + 1.0e-9
            ).astype(np.int32)
            day_multiplier = np.maximum(1, day_multiplier)
            current_day = event_day
        if event.event == "BIRTH":
            if item.identifier in open_positions:
                raise RuntimeError("duplicate replay birth")
            source_steps = int(math.floor(item.source_volume_lots / volume_step + 0.5))
            if source_steps < 1:
                raise RuntimeError("invalid source volume lattice")
            base_steps = np.floor(
                base_volume * day_multiplier / volume_step + 0.5
            ).astype(np.int32)
            target_steps = np.floor(
                base_steps.astype(np.float64) * weights[:, component] + 0.5
            ).astype(np.int32)
            executable_multiplier = np.divide(
                target_steps.astype(np.float64),
                base_steps.astype(np.float64),
                out=np.zeros(candidate_count, dtype=np.float64),
                where=base_steps > 0,
            )
            source_capital_proxy = (
                actual_balance * item.source_risk_capital_haircut_ratio
            )
            conservative_balance = np.minimum(
                np.minimum(actual_balance, stressed_balance), source_capital_proxy
            )
            position_budget = (
                conservative_balance * position_risk * executable_multiplier
            )
            aggregate_budget = conservative_balance * aggregate_risk
            enabled = target_steps > 0
            admitted = (
                enabled
                & (conservative_balance > 0.0)
                & (open_risk + position_budget <= aggregate_budget + tolerance)
            )
            admitted_steps = np.where(admitted, target_steps, 0).astype(np.int32)
            admitted_risk = np.where(admitted, position_budget, 0.0)
            accepted += admitted.astype(np.int32)
            disabled += (~enabled).astype(np.int32)
            aggregate_skips += (enabled & ~admitted).astype(np.int32)
            source_volume_matches += np.isclose(
                target_steps.astype(np.float64) * volume_step,
                item.source_volume_lots,
                atol=float(config["anchor_reproduction"]["volume_tolerance_lots"]),
                rtol=0.0,
            ).astype(np.int32)
            source_risk_capital_matches += np.isclose(
                conservative_balance,
                item.source_risk_capital_usd,
                atol=0.011,
                rtol=0.0,
            ).astype(np.int32)
            source_position_cap_matches += np.isclose(
                position_budget,
                item.source_position_cap_usd,
                atol=0.011,
                rtol=0.0,
            ).astype(np.int32)
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
        "drawdown_pct": actual_dd * 100.0,
        "stressed_drawdown_pct": stressed_dd * 100.0,
        "minimum_balance": minimum_balance,
        "accepted": accepted,
        "aggregate_skips": aggregate_skips,
        "disabled": disabled,
        "source_volume_matches": source_volume_matches,
        "source_risk_capital_matches": source_risk_capital_matches,
        "source_position_cap_matches": source_position_cap_matches,
        "component_actual": component_actual,
        "component_stressed": component_stressed,
        "component_closed": component_closed,
    }


def period_bounds(config: dict[str, Any], name: str) -> tuple[datetime, datetime]:
    values = config["periods"][name]
    return iso_time(values[0]), iso_time(values[1])


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
        "base_position_risk_fraction": float(config["base_position_risk_fraction"]),
        "aggregate_risk_fraction": float(parameter_values[index, component_count]),
        "actual_net_usd": float(metrics["actual_net"][index]),
        "stressed_net_usd": float(metrics["stressed_net"][index]),
        "raw_closed_balance_drawdown_pct": float(metrics["drawdown_pct"][index]),
        "stressed_counterfactual_closed_balance_drawdown_pct": float(
            metrics["stressed_drawdown_pct"][index]
        ),
        "minimum_balance_usd": float(metrics["minimum_balance"][index]),
        "accepted_source_lifecycles": int(metrics["accepted"][index]),
        "aggregate_skips_within_source_path": int(metrics["aggregate_skips"][index]),
        "disabled_by_zero_executable_volume": int(metrics["disabled"][index]),
        "source_volume_matches": int(metrics["source_volume_matches"][index]),
        "source_risk_capital_matches": int(
            metrics["source_risk_capital_matches"][index]
        ),
        "source_position_cap_matches": int(
            metrics["source_position_cap_matches"][index]
        ),
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


def membership_hamming(left: int, right: int) -> int:
    return int((left ^ right).bit_count())


def robust_membership_points(
    eligible: np.ndarray,
    lattice: dict[str, Any],
    development: dict[str, np.ndarray],
    year_2024: dict[str, np.ndarray],
    year_2025: dict[str, np.ndarray],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    eligible_set = set(int(value) for value in np.flatnonzero(eligible))
    minimum_neighbors = int(
        config["membership"]["minimum_eligible_unique_neighbors"]
    )
    robust: list[dict[str, Any]] = []
    for index in sorted(eligible_set):
        neighbors = sorted(
            value for value in lattice["adjacency"][index] if value in eligible_set
        )
        if len(neighbors) < minimum_neighbors:
            continue
        local = [index] + neighbors
        local_efficiency = min(
            float(development["stressed_net"][value])
            / max(float(development["drawdown_pct"][value]), 1.0e-12)
            for value in local
        )
        robust.append(
            {
                "index": index,
                "eligible_unique_neighbor_count": len(neighbors),
                "eligible_unique_neighbor_indices": neighbors,
                "worst_local_stressed_net_to_drawdown": local_efficiency,
                "weakest_annual_stressed_net_usd": min(
                    float(year_2024["stressed_net"][index]),
                    float(year_2025["stressed_net"][index]),
                ),
            }
        )
    robust.sort(
        key=lambda item: (
            -float(item["weakest_annual_stressed_net_usd"]),
            -float(development["stressed_net"][item["index"]])
            / max(float(development["drawdown_pct"][item["index"]]), 1.0e-12),
            -float(development["stressed_net"][item["index"]]),
            float(development["drawdown_pct"][item["index"]]),
            int(item["index"]),
        )
    )
    return robust


def select_separated_then_fill(
    ranked: list[dict[str, Any]], lattice: dict[str, Any], config: dict[str, Any]
) -> list[dict[str, Any]]:
    maximum = int(config["membership"]["maximum_stage_a_centers"])
    separation = int(config["membership"]["minimum_center_hamming_separation"])
    selected: list[dict[str, Any]] = []
    for item in ranked:
        mask = int(lattice["masks"][item["index"]])
        if any(
            membership_hamming(mask, int(lattice["masks"][prior["index"]]))
            < separation
            for prior in selected
        ):
            continue
        selected.append(item)
        if len(selected) == maximum:
            return selected
    selected_indices = {int(item["index"]) for item in selected}
    for item in ranked:
        if int(item["index"]) in selected_indices:
            continue
        selected.append(item)
        selected_indices.add(int(item["index"]))
        if len(selected) == maximum:
            break
    return selected


def near_miss_points(
    lattice: dict[str, Any],
    development: dict[str, np.ndarray],
    year_2024: dict[str, np.ndarray],
    year_2025: dict[str, np.ndarray],
    development_anchor: dict[str, float],
    year_2024_anchor: dict[str, float],
    year_2025_anchor: dict[str, float],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    floor = float(config["gates"]["near_miss_normalization_floor"])
    target_stressed = (
        float(development_anchor["stressed_net"])
        * float(config["gates"]["fallback_stressed_retention"])
    )
    target_dd = float(development_anchor["drawdown_pct"]) - float(
        config["gates"]["fallback_min_drawdown_improvement_points"]
    )
    ranked: list[dict[str, Any]] = []
    for index in range(len(lattice["values"])):
        score = 0.0
        for metrics, anchor in (
            (development, development_anchor),
            (year_2024, year_2024_anchor),
            (year_2025, year_2025_anchor),
        ):
            for field in ("actual_net", "stressed_net"):
                value = float(metrics[field][index])
                denominator = max(abs(float(anchor[field])), 1.0)
                score += max(0.0, floor - value) / denominator
            score += max(0.0, floor - float(metrics["minimum_balance"][index])) / 100.0
        score += max(
            0.0, target_stressed - float(development["stressed_net"][index])
        ) / max(abs(target_stressed), floor)
        score += max(
            0.0, float(development["drawdown_pct"][index]) - target_dd
        ) / max(abs(float(development_anchor["drawdown_pct"])), floor)
        ranked.append(
            {
                "index": index,
                "normalized_gate_deficit": score,
                "weakest_annual_stressed_net_usd": min(
                    float(year_2024["stressed_net"][index]),
                    float(year_2025["stressed_net"][index]),
                ),
                "eligible_unique_neighbor_count": 0,
                "eligible_unique_neighbor_indices": [],
                "worst_local_stressed_net_to_drawdown": None,
            }
        )
    ranked.sort(
        key=lambda item: (
            float(item["normalized_gate_deficit"]),
            -float(item["weakest_annual_stressed_net_usd"]),
            -float(development["stressed_net"][item["index"]])
            / max(float(development["drawdown_pct"][item["index"]]), 1.0e-12),
            int(item["index"]),
        )
    )
    return ranked


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
    authority_paths, stage_b_raw, stage_b_durable = verify_authority_and_stage_b(
        config
    )
    input_paths, lifecycles = verify_and_load_lifecycles(config)
    lattice = build_lattice(config)
    anchor = config["anchor_reproduction"]
    anchor_values = np.asarray(
        [
            list(map(float, anchor["weights"]))
            + [float(anchor["aggregate_risk_fraction"])]
        ],
        dtype=np.float64,
    )
    whole_anchor_metrics = simulate(lifecycles, anchor_values, config)
    observed_anchor = record(0, anchor_values, whole_anchor_metrics, config)
    if observed_anchor["accepted_source_lifecycles"] != int(anchor["accepted_lifecycles"]):
        raise RuntimeError("exact anchor accepted lifecycle reproduction failed")
    if observed_anchor["source_volume_matches"] != int(anchor["source_volume_matches"]):
        raise RuntimeError("exact anchor source volume reproduction failed")
    if observed_anchor["source_risk_capital_matches"] != int(anchor["joined_birth_open_rows"]):
        raise RuntimeError("exact anchor source risk-capital reproduction failed")
    if observed_anchor["source_position_cap_matches"] != int(anchor["joined_birth_open_rows"]):
        raise RuntimeError("exact anchor source position-cap reproduction failed")
    if abs(observed_anchor["actual_net_usd"] - float(anchor["actual_net_usd"])) > float(anchor["net_tolerance_usd"]):
        raise RuntimeError("exact anchor actual reproduction failed")
    if abs(observed_anchor["stressed_net_usd"] - float(anchor["stressed_net_usd"])) > float(anchor["net_tolerance_usd"]):
        raise RuntimeError("exact anchor stressed reproduction failed")
    if abs(observed_anchor["raw_closed_balance_drawdown_pct"] - float(anchor["closed_balance_drawdown_pct"])) > float(anchor["drawdown_tolerance_points"]):
        raise RuntimeError("exact anchor drawdown reproduction failed")

    development_start, development_end = period_bounds(config, "development")
    year_2024_start, year_2024_end = period_bounds(config, "development_2024")
    year_2025_start, year_2025_end = period_bounds(config, "development_2025")
    development_anchor_metrics = simulate(
        lifecycles, anchor_values, config, development_start, development_end
    )
    year_2024_anchor_metrics = simulate(
        lifecycles, anchor_values, config, year_2024_start, year_2024_end
    )
    year_2025_anchor_metrics = simulate(
        lifecycles, anchor_values, config, year_2025_start, year_2025_end
    )
    development = simulate(
        lifecycles, lattice["values"], config, development_start, development_end
    )
    year_2024 = simulate(
        lifecycles, lattice["values"], config, year_2024_start, year_2024_end
    )
    year_2025 = simulate(
        lifecycles, lattice["values"], config, year_2025_start, year_2025_end
    )
    development_anchor_stressed = float(development_anchor_metrics["stressed_net"][0])
    development_anchor_dd = float(development_anchor_metrics["drawdown_pct"][0])
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
    robust = robust_membership_points(
        eligible, lattice, development, year_2024, year_2025, config
    )
    selection_kind = "ROBUST_ELIGIBLE"
    ranked_for_selection = robust
    if not robust:
        scalar_fields = ("actual_net", "stressed_net", "drawdown_pct", "minimum_balance")
        development_anchor_scalar = {
            field: float(development_anchor_metrics[field][0]) for field in scalar_fields
        }
        year_2024_anchor_scalar = {
            field: float(year_2024_anchor_metrics[field][0]) for field in scalar_fields
        }
        year_2025_anchor_scalar = {
            field: float(year_2025_anchor_metrics[field][0]) for field in scalar_fields
        }
        ranked_for_selection = near_miss_points(
            lattice,
            development,
            year_2024,
            year_2025,
            development_anchor_scalar,
            year_2024_anchor_scalar,
            year_2025_anchor_scalar,
            config,
        )
        selection_kind = "DECLARED_NEAR_MISS"
    selected_meta = select_separated_then_fill(
        ranked_for_selection, lattice, config
    )
    centers = [int(item["index"]) for item in selected_meta]
    if not centers:
        raise RuntimeError("Stage A failed to select mandatory Stage-B seeds")

    result: dict[str, Any] = {
        "schema": "zeta-next-dd20-v8-existing-component-membership-reconstruction-proxy-result-v1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "campaign": "dd20-v8-existing-component-membership-reconstruction-proxy-v1",
        "optimization_unit_id": str(config["optimization_unit_id"]),
        "unit_stage": str(config["unit_stage"]),
        "unit_closure_authority": False,
        "authority": {
            "declaration_commit_on_origin_main": str(
                config["declaration_authority"]["declaration_commit_on_origin_main"]
            ),
            "correction_commit_on_origin_main": str(
                config["declaration_authority"]["correction_commit_on_origin_main"]
            ),
            "exact_v8_is_sole_economic_parent": True,
            "v7_or_historical_lab_economic_input": False,
            "external_input": False,
            "lab_opened": False,
            "new_entry_strategy": False,
            "live_changed": False,
        },
        "inputs": {
            "declaration": {
                "path": str(authority_paths["declaration"].relative_to(REPOSITORY_ROOT)).replace("\\", "/"),
                "bytes": authority_paths["declaration"].stat().st_size,
                "sha256": sha256(authority_paths["declaration"]),
            },
            "declaration_correction": {
                "path": str(authority_paths["correction"].relative_to(REPOSITORY_ROOT)).replace("\\", "/"),
                "bytes": authority_paths["correction"].stat().st_size,
                "sha256": sha256(authority_paths["correction"]),
            },
            "lifecycle": {
                "path": str(config["inputs"]["root"])
                + "/"
                + str(config["inputs"]["lifecycle"]["name"]),
                "bytes": input_paths["lifecycle"].stat().st_size,
                "sha256": sha256(input_paths["lifecycle"]),
            },
            "candidate": {
                "path": str(config["inputs"]["root"])
                + "/"
                + str(config["inputs"]["candidate"]["name"]),
                "bytes": input_paths["candidate"].stat().st_size,
                "sha256": sha256(input_paths["candidate"]),
            },
            "stage_b_raw": {
                "path": str(config["inputs"]["root"])
                + "/"
                + str(config["inputs"]["stage_b_raw"]["name"]),
                "bytes": authority_paths["stage_b_raw"].stat().st_size,
                "sha256": sha256(authority_paths["stage_b_raw"]),
                "status": stage_b_raw["status"],
            },
            "stage_b_durable": {
                "path": str(config["inputs"]["root"])
                + "/"
                + str(config["inputs"]["stage_b_durable"]["name"]),
                "bytes": authority_paths["stage_b_durable"].stat().st_size,
                "sha256": sha256(authority_paths["stage_b_durable"]),
                "status": stage_b_durable["status"],
            },
            "matched_lifecycles": len(lifecycles),
        },
        "membership_map": {
            "raw_seed_mask_roles": len(lattice["raw_roles"]),
            "deduplicated_exact_weight_roles": int(len(lattice["values"])),
            "duplicates_removed": len(lattice["raw_roles"]) - len(lattice["values"]),
            "unique_membership_masks_represented": int(len(set(map(int, lattice["masks"])))),
            "primary_eligible": int(primary.sum()),
            "fallback_eligible": int(fallback.sum()),
            "active_tier": active_tier,
            "active_tier_eligible": int(eligible.sum()),
            "robust_active_tier_points": len(robust),
            "selection_kind": selection_kind,
        },
        "exact_anchor_whole_path": observed_anchor,
        "exact_anchor_development": record(
            0, anchor_values, development_anchor_metrics, config
        ),
        "exact_anchor_development_2024": record(
            0, anchor_values, year_2024_anchor_metrics, config
        ),
        "exact_anchor_development_2025": record(
            0, anchor_values, year_2025_anchor_metrics, config
        ),
        "development_centers": [],
        "stage_b_membership_seeds": [],
        "validation_opened": False,
        "locked_holdout_opened": False,
        "mt5": {
            "shortlist_count": 0,
            "valid_economic_paths_run": 0,
            "maximum_valid_economic_paths_authorized": int(
                config["mt5_budget"]["maximum_valid_economic_paths"]
            ),
        },
        "limitations": [
            "Accepted-source-path suppression/resizing replay only; 143 observed capacity-blocked existing-V8 opportunities have unknown outcomes and receive zero profit credit.",
            "Source pre-order risk-capital context can reduce admission capital but cannot reconstruct candidate-specific open-equity paths.",
            "A different capital ladder can alter native stop quantization; closed-balance replay is not native MT5 equity drawdown or final economics.",
            "Stage A uses development only. January-May validation and locked June-July remain unopened by declaration.",
        ],
    }

    component_names = [str(item["short"]) for item in config["components"]]
    for rank, (index, meta) in enumerate(zip(centers, selected_meta), start=1):
        item = record(
            index,
            lattice["values"],
            development,
            config,
        )
        mask = int(lattice["masks"][index])
        item.update(
            {
                "development_rank": rank,
                "selection_kind": selection_kind,
                "membership_mask_integer": mask,
                "membership_mask_binary_rc61_to_return": format(mask, "05b")[::-1],
                "active_components": [
                    name for axis, name in enumerate(component_names) if mask & (1 << axis)
                ],
                "seed_mask_provenance": lattice["provenance"][index],
                "common_gate_passed": bool(common[index]),
                "primary_gate_passed": bool(primary[index]),
                "fallback_gate_passed": bool(fallback[index]),
                "eligible_unique_neighbor_count": int(
                    meta["eligible_unique_neighbor_count"]
                ),
                "eligible_unique_neighbor_indices": [
                    int(value) for value in meta["eligible_unique_neighbor_indices"]
                ],
                "worst_local_stressed_net_to_drawdown": meta[
                    "worst_local_stressed_net_to_drawdown"
                ],
                "weakest_annual_stressed_net_usd": float(
                    meta["weakest_annual_stressed_net_usd"]
                ),
                "normalized_gate_deficit": meta.get("normalized_gate_deficit"),
                "development_2024": record(
                    index, lattice["values"], year_2024, config
                ),
                "development_2025": record(
                    index, lattice["values"], year_2025, config
                ),
            }
        )
        result["development_centers"].append(item)
        result["stage_b_membership_seeds"].append(
            {
                "development_rank": rank,
                "selection_kind": selection_kind,
                "lattice_index": index,
                "membership_mask_integer": mask,
                "active_components": item["active_components"],
                "weights": item["weights"],
                "base_position_risk_fraction": item["base_position_risk_fraction"],
                "aggregate_risk_fraction": item["aggregate_risk_fraction"],
                "seed_mask_provenance": item["seed_mask_provenance"],
            }
        )

    result["status"] = (
        "VALID_PROXY_COMPLETE_STAGE_A_ROBUST_MEMBERSHIP_SEEDS_STAGE_B_REQUIRED_NO_MT5"
        if selection_kind == "ROBUST_ELIGIBLE"
        else "VALID_PROXY_COMPLETE_STAGE_A_NEAR_MISS_MEMBERSHIP_SEEDS_STAGE_B_REQUIRED_NO_MT5"
    )

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
                "stage_b_seed_count": len(result["stage_b_membership_seeds"]),
                "mt5_paths": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
