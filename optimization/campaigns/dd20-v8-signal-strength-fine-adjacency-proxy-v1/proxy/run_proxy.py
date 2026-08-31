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
    normalized_strength: float
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


def normalized_strength(feature: float, component: dict[str, Any]) -> float:
    mode = str(component["strength_mode"])
    gate = float(component["native_feature_gate"])
    if mode == "positive":
        numerator = feature
    elif mode == "negative":
        numerator = -feature
    elif mode == "absolute":
        numerator = abs(feature)
    else:
        raise RuntimeError("unknown component strength mode")
    result = numerator / gate
    if not math.isfinite(result):
        raise RuntimeError("nonfinite normalized feature strength")
    return result


def verify_authority_and_inputs(config: dict[str, Any]) -> dict[str, Path]:
    authority = config["declaration_authority"]
    declaration = REPOSITORY_ROOT / str(authority["path"])
    if declaration.stat().st_size != int(authority["bytes"]):
        raise RuntimeError("declaration authority byte count mismatch")
    if sha256(declaration) != str(authority["sha256"]):
        raise RuntimeError("declaration authority hash mismatch")

    declared_inputs = config["inputs"]
    input_root = REPOSITORY_ROOT / str(declared_inputs["root"])
    paths: dict[str, Path] = {"declaration": declaration}
    for role in ("lifecycle", "candidate", "stage_a_raw", "stage_a_durable"):
        declared = declared_inputs[role]
        path = input_root / str(declared["name"])
        if path.stat().st_size != int(declared["bytes"]):
            raise RuntimeError(f"staged {role} byte count mismatch")
        if sha256(path) != str(declared["sha256"]):
            raise RuntimeError(f"staged {role} hash mismatch")
        paths[role] = path

    for index, declared in enumerate(declared_inputs["source_files"]):
        path = input_root / str(declared["name"])
        if path.stat().st_size != int(declared["bytes"]):
            raise RuntimeError("staged source byte count mismatch")
        if sha256(path) != str(declared["sha256"]):
            raise RuntimeError("staged source hash mismatch")
        paths[f"source_{index}"] = path
    return paths


def verify_stage_a_inputs(
    config: dict[str, Any], paths: dict[str, Path]
) -> dict[str, Any]:
    payloads: dict[str, Any] = {}
    for role in ("stage_a_raw", "stage_a_durable"):
        declared = config["inputs"][role]
        payload = json.loads(paths[role].read_text(encoding="utf-8"))
        if payload.get("schema") != str(declared["schema"]):
            raise RuntimeError(f"{role} schema mismatch")
        if payload.get("status") != str(declared["status"]):
            raise RuntimeError(f"{role} status mismatch")
        payloads[role] = payload

    expected = config["strength_lattice"]["centers"]
    raw_centers = payloads["stage_a_raw"].get("stage_b_strength_seeds", [])
    durable_centers = payloads["stage_a_durable"].get("stage_b_strength_seeds", [])
    if len(raw_centers) != len(expected) or len(durable_centers) != len(expected):
        raise RuntimeError("Stage-A center count mismatch")
    tolerance = 1.0e-9
    for index, center in enumerate(expected):
        expected_quantiles = np.asarray(center["quantiles"], dtype=np.float64)
        expected_thresholds = np.asarray(
            center["stage_a_thresholds"], dtype=np.float64
        )
        for observed in (raw_centers[index], durable_centers[index]):
            if int(observed["development_rank"]) != int(center["rank"]):
                raise RuntimeError("Stage-A center rank mismatch")
            if not np.allclose(
                np.asarray(observed["quantile_coordinates"], dtype=np.float64),
                expected_quantiles,
                atol=tolerance,
                rtol=0.0,
            ):
                raise RuntimeError("Stage-A center quantile mismatch")
            if not np.allclose(
                np.asarray(observed["normalized_thresholds"], dtype=np.float64),
                expected_thresholds,
                atol=tolerance,
                rtol=0.0,
            ):
                raise RuntimeError("Stage-A center threshold mismatch")
    return payloads


def verify_and_load_data(
    config: dict[str, Any], paths: dict[str, Path]
) -> tuple[list[Lifecycle], list[list[float]], dict[str, Any]]:
    lifecycle_declared = config["inputs"]["lifecycle"]
    candidate_declared = config["inputs"]["candidate"]
    components = config["components"]
    component_ids = [str(item["id"]) for item in components]
    component_index = {value: index for index, value in enumerate(component_ids)}
    strength_tolerance = float(config["strength_lattice"]["strength_tolerance"])
    development_start, development_end = (
        iso_time(value)
        for value in config["strength_lattice"]["development_population"]
    )

    births: dict[str, dict[str, Any]] = {}
    closes: dict[str, dict[str, Any]] = {}
    lifecycle_rows = 0
    with paths["lifecycle"].open("r", encoding="utf-8-sig", newline="") as handle:
        for order, row in enumerate(csv.DictReader(handle)):
            lifecycle_rows += 1
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
                "entry_feature": float(row["entry_feature"]),
                "actual": float(row["actual_net_usd"]),
                "stressed": float(row["stressed_net_usd"]),
            }
    if lifecycle_rows != int(lifecycle_declared["rows"]):
        raise RuntimeError("staged lifecycle row count mismatch")
    if set(births) != set(closes):
        raise RuntimeError("birth/close identity mismatch")
    if len(births) != int(lifecycle_declared["matched_lifecycles"]):
        raise RuntimeError("matched lifecycle count mismatch")

    open_contexts: dict[str, dict[str, float]] = {}
    populations: list[list[float]] = [[] for _ in components]
    signal_passed_all = np.zeros(len(components), dtype=np.int32)
    signal_passed_development = np.zeros(len(components), dtype=np.int32)
    candidate_rows = 0
    total_signal_passed = 0
    with paths["candidate"].open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            candidate_rows += 1
            component_id = row["component_id"]
            if component_id not in component_index:
                raise RuntimeError("undeclared component in candidate input")
            index = component_index[component_id]
            feature = float(row["feature"])
            strength = normalized_strength(feature, components[index])
            signal_passed = row["signal_known"] == "1" and row["signal_passed"] == "1"
            if signal_passed:
                if strength < 1.0 - strength_tolerance:
                    raise RuntimeError("signal-passed feature violates native gate")
                total_signal_passed += 1
                signal_passed_all[index] += 1
                when = parse_time(row["server_time"])
                if development_start <= when < development_end:
                    signal_passed_development[index] += 1
                    populations[index].append(strength)
            if row["result"] != "POSITION_OPEN":
                continue
            if not signal_passed:
                raise RuntimeError("POSITION_OPEN row is not signal passed")
            key = f"{component_id}|{row['server_time']}"
            if key in open_contexts:
                raise RuntimeError("duplicate component/time POSITION_OPEN key")
            account_balance = float(row["account_balance"])
            account_equity = float(row["account_equity"])
            if account_balance <= 0.0 or account_equity <= 0.0:
                raise RuntimeError("nonpositive source account context")
            open_contexts[key] = {
                "feature": feature,
                "normalized_strength": strength,
                "volume": float(row["volume"]),
                "planned_risk": float(row["planned_risk_usd"]),
                "account_balance": account_balance,
                "account_equity": account_equity,
                "risk_capital": float(row["risk_capital_usd"]),
                "position_cap": float(row["position_cap_usd"]),
                "aggregate_cap": float(row["aggregate_cap_usd"]),
            }

    if candidate_rows != int(candidate_declared["rows"]):
        raise RuntimeError("candidate row count mismatch")
    if total_signal_passed != int(candidate_declared["signal_passed_rows"]):
        raise RuntimeError("signal-passed row count mismatch")
    if len(open_contexts) != int(candidate_declared["position_open_rows"]):
        raise RuntimeError("POSITION_OPEN row count mismatch")
    if len(open_contexts) != int(candidate_declared["unique_component_time_open_keys"]):
        raise RuntimeError("POSITION_OPEN key count mismatch")

    expected_signal_all = np.asarray(
        [int(item["signal_passed_all"]) for item in components], dtype=np.int32
    )
    expected_signal_development = np.asarray(
        [int(item["signal_passed_development"]) for item in components],
        dtype=np.int32,
    )
    if not np.array_equal(signal_passed_all, expected_signal_all):
        raise RuntimeError("component signal-passed count mismatch")
    if not np.array_equal(signal_passed_development, expected_signal_development):
        raise RuntimeError("component development signal-passed count mismatch")
    if any(not values for values in populations):
        raise RuntimeError("empty component development strength population")
    for values in populations:
        values.sort()

    lifecycles: list[Lifecycle] = []
    birth_counts = np.zeros(len(components), dtype=np.int32)
    feature_tolerance = 1.0e-10
    for identifier, birth in births.items():
        close = closes[identifier]
        if birth["component"] != close["component"]:
            raise RuntimeError("component changed within lifecycle")
        if birth["volume"] <= 0.0 or birth["planned_risk"] <= 0.0:
            raise RuntimeError("source birth has nonpositive volume or planned risk")
        index = int(birth["component"])
        component_id = component_ids[index]
        context_key = f"{component_id}|{birth['time'].strftime(TIME_FORMAT)}"
        if context_key not in open_contexts:
            raise RuntimeError("lifecycle birth has no POSITION_OPEN context")
        context = open_contexts[context_key]
        if abs(float(birth["entry_feature"]) - context["feature"]) > feature_tolerance:
            raise RuntimeError("lifecycle/candidate entry feature mismatch")
        if abs(float(birth["volume"]) - context["volume"]) > float(
            config["anchor_reproduction"]["volume_tolerance_lots"]
        ):
            raise RuntimeError("lifecycle/candidate source volume mismatch")
        if abs(float(birth["planned_risk"]) - context["planned_risk"]) > 0.011:
            raise RuntimeError("lifecycle/candidate planned risk mismatch")
        birth_counts[index] += 1
        lifecycles.append(
            Lifecycle(
                identifier=identifier,
                component_index=index,
                birth_time=birth["time"],
                close_time=close["time"],
                birth_order=int(birth["order"]),
                close_order=int(close["order"]),
                normalized_strength=context["normalized_strength"],
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

    expected_birth_counts = np.asarray(
        [int(item["source_births"]) for item in components], dtype=np.int32
    )
    if not np.array_equal(birth_counts, expected_birth_counts):
        raise RuntimeError("component birth count mismatch")
    actual = sum(item.actual_net_usd for item in lifecycles)
    stressed = sum(item.stressed_net_usd for item in lifecycles)
    if abs(actual - float(lifecycle_declared["actual_net_usd"])) > 1.0e-7:
        raise RuntimeError("source actual net mismatch")
    if abs(stressed - float(lifecycle_declared["stressed_net_usd"])) > 1.0e-7:
        raise RuntimeError("source stressed net mismatch")
    lifecycles.sort(key=lambda item: item.birth_order)
    diagnostics = {
        "candidate_rows": candidate_rows,
        "signal_passed_rows": total_signal_passed,
        "position_open_rows": len(open_contexts),
        "signal_passed_all_by_component": signal_passed_all.tolist(),
        "signal_passed_development_by_component": signal_passed_development.tolist(),
        "accepted_births_by_component": birth_counts.tolist(),
    }
    return lifecycles, populations, diagnostics


def nearest_rank_threshold(values: list[float], quantile: float) -> float:
    if quantile == 0.0:
        return 1.0
    rank = max(1, min(len(values), int(math.ceil(quantile * len(values)))))
    return float(values[rank - 1])


def build_lattice(
    config: dict[str, Any], populations: list[list[float]]
) -> dict[str, Any]:
    lattice_config = config["strength_lattice"]
    component_count = len(config["components"])
    offset = float(lattice_config["fine_offset"])
    minimum = float(lattice_config["minimum_quantile"])
    maximum = float(lattice_config["maximum_quantile"])

    def normalized_quantile(value: float) -> float:
        return round(min(maximum, max(minimum, value)), 12)

    all_quantiles: set[float] = set()
    center_axis_values: list[list[list[float]]] = []
    for center in lattice_config["centers"]:
        quantiles = [float(value) for value in center["quantiles"]]
        if len(quantiles) != component_count:
            raise RuntimeError("fine center component count mismatch")
        axes: list[list[float]] = []
        for value in quantiles:
            choices = sorted(
                {
                    normalized_quantile(value - offset),
                    normalized_quantile(value),
                    normalized_quantile(value + offset),
                }
            )
            axes.append(choices)
            all_quantiles.update(choices)
        center_axis_values.append(axes)
    threshold_lookup = [
        {
            quantile: nearest_rank_threshold(populations[axis], quantile)
            for quantile in sorted(all_quantiles)
        }
        for axis in range(component_count)
    ]
    raw_roles: list[dict[str, Any]] = []
    grouped: dict[tuple[float, ...], list[dict[str, Any]]] = {}
    quantile_vectors_seen: set[tuple[float, ...]] = set()
    center_quantile_to_threshold: list[dict[tuple[float, ...], tuple[float, ...]]] = []
    for center_index, axes in enumerate(center_axis_values):
        local: dict[tuple[float, ...], tuple[float, ...]] = {}
        for quantile_vector in itertools.product(*axes):
            quantile_vector = tuple(float(value) for value in quantile_vector)
            thresholds = tuple(
                threshold_lookup[axis][quantile_vector[axis]]
                for axis in range(component_count)
            )
            role = {
                "center_rank": center_index + 1,
                "quantiles": quantile_vector,
                "thresholds": thresholds,
            }
            raw_roles.append(role)
            grouped.setdefault(thresholds, []).append(role)
            quantile_vectors_seen.add(quantile_vector)
            local[quantile_vector] = thresholds
        if len(local) != int(lattice_config["centers"][center_index]["raw_roles"]):
            raise RuntimeError("fine center raw role count mismatch")
        center_quantile_to_threshold.append(local)
    if len(raw_roles) != int(lattice_config["raw_roles"]):
        raise RuntimeError("fine strength raw role count mismatch")
    if len(quantile_vectors_seen) != int(
        lattice_config["expected_unique_quantile_roles"]
    ):
        raise RuntimeError("fine strength unique quantile role count mismatch")

    unique_thresholds: list[tuple[float, ...]] = []
    threshold_to_index: dict[tuple[float, ...], int] = {}
    for role in raw_roles:
        key = role["thresholds"]
        if key not in threshold_to_index:
            threshold_to_index[key] = len(unique_thresholds)
            unique_thresholds.append(key)
    if len(unique_thresholds) != int(lattice_config["expected_unique_threshold_roles"]):
        raise RuntimeError("fine strength unique threshold role count mismatch")

    adjacency: list[set[int]] = [set() for _ in unique_thresholds]
    edge_axes: list[dict[int, set[int]]] = [dict() for _ in unique_thresholds]
    center_edge_counts: list[int] = []
    for center_index, local in enumerate(center_quantile_to_threshold):
        axes = center_axis_values[center_index]
        local_edges: set[tuple[int, int]] = set()
        for quantile_vector, thresholds in local.items():
            index = threshold_to_index[thresholds]
            for axis in range(component_count):
                axis_values = axes[axis]
                position = axis_values.index(quantile_vector[axis])
                for neighbor_position in (position - 1, position + 1):
                    if neighbor_position < 0 or neighbor_position >= len(axis_values):
                        continue
                    neighbor_quantiles = list(quantile_vector)
                    neighbor_quantiles[axis] = axis_values[neighbor_position]
                    neighbor_thresholds = local[tuple(neighbor_quantiles)]
                    neighbor = threshold_to_index[neighbor_thresholds]
                    if neighbor == index:
                        continue
                    adjacency[index].add(neighbor)
                    edge_axes[index].setdefault(neighbor, set()).add(axis)
                    local_edges.add(tuple(sorted((index, neighbor))))
        expected_edges = int(lattice_config["centers"][center_index]["adjacency_edges"])
        if len(local_edges) != expected_edges:
            raise RuntimeError("fine center adjacency edge count mismatch")
        center_edge_counts.append(len(local_edges))
    if sum(center_edge_counts) != int(lattice_config["expected_adjacency_edges"]):
        raise RuntimeError("fine total adjacency edge count mismatch")

    provenance = [grouped[key] for key in unique_thresholds]
    quantile_vectors = np.asarray(
        [values[0]["quantiles"] for values in provenance], dtype=np.float64
    )
    thresholds = np.asarray(unique_thresholds, dtype=np.float64)
    if np.any(thresholds < 1.0 - float(lattice_config["strength_tolerance"])):
        raise RuntimeError("candidate threshold loosened below native gate")

    for center_index, center in enumerate(lattice_config["centers"]):
        quantiles = tuple(float(value) for value in center["quantiles"])
        expected = np.asarray(center["stage_a_thresholds"], dtype=np.float64)
        observed = np.asarray(
            center_quantile_to_threshold[center_index][quantiles], dtype=np.float64
        )
        if not np.allclose(observed, expected, atol=1.0e-9, rtol=0.0):
            raise RuntimeError("fine center threshold reconstruction mismatch")
    return {
        "values": thresholds,
        "quantiles": quantile_vectors,
        "integer_coordinates": quantile_vectors,
        "provenance": provenance,
        "adjacency": adjacency,
        "edge_axes": edge_axes,
        "raw_roles": raw_roles,
        "threshold_lookup": threshold_lookup,
        "center_role_counts": [len(values) for values in center_quantile_to_threshold],
        "center_adjacency_edges": center_edge_counts,
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
    normalized_thresholds: np.ndarray,
    config: dict[str, Any],
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, np.ndarray]:
    component_count = len(config["components"])
    candidate_count = normalized_thresholds.shape[0]
    weights = np.asarray(
        [float(item["source_weight"]) for item in config["components"]],
        dtype=np.float64,
    )
    aggregate_risk = float(config["aggregate_risk_fraction"])
    position_risk = float(config["base_position_risk_fraction"])
    base_volume = float(config["base_volume_lots"])
    volume_step = float(config["volume_step_lots"])
    addition_step = float(config["addition_step_usd"])
    reference = float(config["reference_capital_usd"])
    tolerance = float(config["aggregate_tolerance_usd"])
    strength_tolerance = float(config["strength_lattice"]["strength_tolerance"])

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
    strength_suppressed = np.zeros(candidate_count, dtype=np.int32)
    source_volume_matches = np.zeros(candidate_count, dtype=np.int32)
    source_risk_capital_matches = np.zeros(candidate_count, dtype=np.int32)
    source_position_cap_matches = np.zeros(candidate_count, dtype=np.int32)
    component_actual = np.zeros((candidate_count, component_count), dtype=np.float64)
    component_stressed = np.zeros_like(component_actual)
    component_closed = np.zeros((candidate_count, component_count), dtype=np.int32)
    component_suppressed = np.zeros((candidate_count, component_count), dtype=np.int32)
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
                base_steps.astype(np.float64) * weights[component] + 0.5
            ).astype(np.int32)
            executable_multiplier = np.divide(
                target_steps.astype(np.float64),
                base_steps.astype(np.float64),
                out=np.zeros(candidate_count, dtype=np.float64),
                where=base_steps > 0,
            )
            source_capital_proxy = actual_balance * item.source_risk_capital_haircut_ratio
            conservative_balance = np.minimum(
                np.minimum(actual_balance, stressed_balance), source_capital_proxy
            )
            position_budget = conservative_balance * position_risk * executable_multiplier
            aggregate_budget = conservative_balance * aggregate_risk
            strength_passed = (
                item.normalized_strength + strength_tolerance
                >= normalized_thresholds[:, component]
            )
            enabled = strength_passed & (target_steps > 0)
            admitted = (
                enabled
                & (conservative_balance > 0.0)
                & (open_risk + position_budget <= aggregate_budget + tolerance)
            )
            admitted_steps = np.where(admitted, target_steps, 0).astype(np.int32)
            admitted_risk = np.where(admitted, position_budget, 0.0)
            accepted += admitted.astype(np.int32)
            strength_suppressed += (~strength_passed).astype(np.int32)
            component_suppressed[:, component] += (~strength_passed).astype(np.int32)
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
            open_positions[item.identifier] = (admitted_steps, admitted_risk, source_steps)
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
            np.where(
                actual_peak > 0.0,
                (actual_peak - actual_balance) / actual_peak,
                np.inf,
            ),
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
        "strength_suppressed": strength_suppressed,
        "source_volume_matches": source_volume_matches,
        "source_risk_capital_matches": source_risk_capital_matches,
        "source_position_cap_matches": source_position_cap_matches,
        "component_actual": component_actual,
        "component_stressed": component_stressed,
        "component_closed": component_closed,
        "component_suppressed": component_suppressed,
    }


def period_bounds(config: dict[str, Any], name: str) -> tuple[datetime, datetime]:
    values = config["periods"][name]
    return iso_time(values[0]), iso_time(values[1])


def raw_feature_threshold(normalized: float, component: dict[str, Any]) -> float:
    value = normalized * float(component["native_feature_gate"])
    return -value if str(component["strength_mode"]) == "negative" else value


def record(
    index: int,
    thresholds: np.ndarray,
    metrics: dict[str, np.ndarray],
    config: dict[str, Any],
    quantiles: np.ndarray | None = None,
) -> dict[str, Any]:
    components = config["components"]
    normalized = [float(value) for value in thresholds[index]]
    result: dict[str, Any] = {
        "normalized_thresholds": normalized,
        "raw_feature_thresholds": [
            raw_feature_threshold(normalized[axis], component)
            for axis, component in enumerate(components)
        ],
        "weights": [float(item["source_weight"]) for item in components],
        "base_position_risk_fraction": float(config["base_position_risk_fraction"]),
        "aggregate_risk_fraction": float(config["aggregate_risk_fraction"]),
        "actual_net_usd": float(metrics["actual_net"][index]),
        "stressed_net_usd": float(metrics["stressed_net"][index]),
        "raw_closed_balance_drawdown_pct": float(metrics["drawdown_pct"][index]),
        "stressed_counterfactual_closed_balance_drawdown_pct": float(
            metrics["stressed_drawdown_pct"][index]
        ),
        "minimum_balance_usd": float(metrics["minimum_balance"][index]),
        "accepted_source_lifecycles": int(metrics["accepted"][index]),
        "suppressed_by_strength": int(metrics["strength_suppressed"][index]),
        "aggregate_skips_within_source_path": int(metrics["aggregate_skips"][index]),
        "source_volume_matches": int(metrics["source_volume_matches"][index]),
        "source_risk_capital_matches": int(
            metrics["source_risk_capital_matches"][index]
        ),
        "source_position_cap_matches": int(
            metrics["source_position_cap_matches"][index]
        ),
    }
    if quantiles is not None:
        result["quantile_coordinates"] = [float(value) for value in quantiles[index]]
    component_results: list[dict[str, Any]] = []
    for component_index, component in enumerate(components):
        component_results.append(
            {
                "short": str(component["short"]),
                "closed": int(metrics["component_closed"][index, component_index]),
                "suppressed": int(
                    metrics["component_suppressed"][index, component_index]
                ),
                "actual_net_usd": float(
                    metrics["component_actual"][index, component_index]
                ),
                "stressed_net_usd": float(
                    metrics["component_stressed"][index, component_index]
                ),
            }
        )
    result["components"] = component_results
    return result


def positive(metrics: dict[str, np.ndarray]) -> np.ndarray:
    return (
        (metrics["actual_net"] > 0.0)
        & (metrics["stressed_net"] > 0.0)
        & (metrics["minimum_balance"] > 0.0)
    )


def robust_points(
    eligible: np.ndarray,
    lattice: dict[str, Any],
    development: dict[str, np.ndarray],
    blocks: list[dict[str, np.ndarray]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    eligible_set = set(int(value) for value in np.flatnonzero(eligible))
    minimum_neighbors = int(config["strength_lattice"]["minimum_eligible_neighbors"])
    minimum_axes = int(config["strength_lattice"]["minimum_neighbor_axes"])
    robust: list[dict[str, Any]] = []
    for index in sorted(eligible_set):
        neighbors = sorted(
            value for value in lattice["adjacency"][index] if value in eligible_set
        )
        axes: set[int] = set()
        for neighbor in neighbors:
            axes.update(lattice["edge_axes"][index].get(neighbor, set()))
        if len(neighbors) < minimum_neighbors or len(axes) < minimum_axes:
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
                "eligible_neighbor_count": len(neighbors),
                "eligible_neighbor_indices": neighbors,
                "eligible_neighbor_axes": sorted(axes),
                "worst_local_stressed_net_to_drawdown": local_efficiency,
                "weakest_half_year_stressed_net_usd": min(
                    float(metrics["stressed_net"][index]) for metrics in blocks
                ),
            }
        )
    robust.sort(
        key=lambda item: (
            -float(item["weakest_half_year_stressed_net_usd"]),
            -float(development["stressed_net"][item["index"]])
            / max(float(development["drawdown_pct"][item["index"]]), 1.0e-12),
            -float(development["stressed_net"][item["index"]]),
            float(development["drawdown_pct"][item["index"]]),
            int(item["index"]),
        )
    )
    return robust


def coordinate_separation(left: np.ndarray, right: np.ndarray) -> int:
    return int(np.count_nonzero(left != right))


def select_separated_then_fill(
    ranked: list[dict[str, Any]], lattice: dict[str, Any], config: dict[str, Any]
) -> list[dict[str, Any]]:
    maximum = int(config["strength_lattice"]["maximum_stage_c_centers"])
    separation = int(
        config["strength_lattice"]["minimum_center_component_separation"]
    )
    selected: list[dict[str, Any]] = []
    for item in ranked:
        coordinate = lattice["integer_coordinates"][item["index"]]
        if any(
            coordinate_separation(
                coordinate, lattice["integer_coordinates"][prior["index"]]
            )
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
    blocks: list[dict[str, np.ndarray]],
    development_anchor: dict[str, float],
    block_anchors: list[dict[str, float]],
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
        for metrics, anchor in zip(blocks, block_anchors):
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
                "weakest_half_year_stressed_net_usd": min(
                    float(metrics["stressed_net"][index]) for metrics in blocks
                ),
                "eligible_neighbor_count": 0,
                "eligible_neighbor_indices": [],
                "eligible_neighbor_axes": [],
                "worst_local_stressed_net_to_drawdown": None,
            }
        )
    ranked.sort(
        key=lambda item: (
            float(item["normalized_gate_deficit"]),
            -float(item["weakest_half_year_stressed_net_usd"]),
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
        return round(value, 12)
    return value


def scalar_record(metrics: dict[str, np.ndarray], index: int = 0) -> dict[str, float]:
    return {
        field: float(metrics[field][index])
        for field in ("actual_net", "stressed_net", "drawdown_pct", "minimum_balance")
    }


def structural_precheck() -> dict[str, Any]:
    config = load_config()
    paths = verify_authority_and_inputs(config)
    stage_a_payloads = verify_stage_a_inputs(config, paths)
    lifecycles, populations, diagnostics = verify_and_load_data(config, paths)
    lattice = build_lattice(config, populations)
    anchor_thresholds = np.asarray(
        [config["anchor_reproduction"]["normalized_thresholds"]], dtype=np.float64
    )
    metrics = simulate(lifecycles, anchor_thresholds, config)
    anchor = config["anchor_reproduction"]
    observed = record(0, anchor_thresholds, metrics, config)
    if observed["accepted_source_lifecycles"] != int(anchor["accepted_lifecycles"]):
        raise RuntimeError("exact anchor accepted lifecycle reproduction failed")
    if observed["source_volume_matches"] != int(anchor["source_volume_matches"]):
        raise RuntimeError("exact anchor source volume reproduction failed")
    if observed["source_risk_capital_matches"] != int(anchor["joined_birth_open_rows"]):
        raise RuntimeError("exact anchor source risk-capital reproduction failed")
    if observed["source_position_cap_matches"] != int(anchor["joined_birth_open_rows"]):
        raise RuntimeError("exact anchor source position-cap reproduction failed")
    if abs(observed["actual_net_usd"] - float(anchor["actual_net_usd"])) > float(
        anchor["net_tolerance_usd"]
    ):
        raise RuntimeError("exact anchor actual reproduction failed")
    if abs(observed["stressed_net_usd"] - float(anchor["stressed_net_usd"])) > float(
        anchor["net_tolerance_usd"]
    ):
        raise RuntimeError("exact anchor stressed reproduction failed")
    if abs(
        observed["raw_closed_balance_drawdown_pct"]
        - float(anchor["closed_balance_drawdown_pct"])
    ) > float(anchor["drawdown_tolerance_points"]):
        raise RuntimeError("exact anchor drawdown reproduction failed")
    threshold_summary = []
    quantiles = [
        float(value)
        for value in config["strength_lattice"]["precheck_quantile_coordinates"]
    ]
    for axis, component in enumerate(config["components"]):
        threshold_summary.append(
            {
                "short": str(component["short"]),
                "population": len(populations[axis]),
                "normalized_thresholds": {
                    str(value): nearest_rank_threshold(populations[axis], value)
                    for value in quantiles
                },
            }
        )
    return {
        "matched_lifecycles": len(lifecycles),
        "input_diagnostics": diagnostics,
        "raw_roles": len(lattice["raw_roles"]),
        "unique_threshold_roles": len(lattice["values"]),
        "duplicates_removed": len(lattice["raw_roles"]) - len(lattice["values"]),
        "adjacency_edges": sum(len(values) for values in lattice["adjacency"]) // 2,
        "center_role_counts": lattice["center_role_counts"],
        "center_adjacency_edges": lattice["center_adjacency_edges"],
        "all_thresholds_at_or_above_native": bool(np.all(lattice["values"] >= 1.0)),
        "stage_a_raw_status": stage_a_payloads["stage_a_raw"]["status"],
        "stage_a_durable_status": stage_a_payloads["stage_a_durable"]["status"],
        "threshold_summary": threshold_summary,
        "exact_v8_whole": observed,
    }


def main() -> None:
    started = time.perf_counter()
    config = load_config()
    paths = verify_authority_and_inputs(config)
    stage_a_payloads = verify_stage_a_inputs(config, paths)
    lifecycles, populations, input_diagnostics = verify_and_load_data(config, paths)
    lattice = build_lattice(config, populations)
    anchor_thresholds = np.asarray(
        [config["anchor_reproduction"]["normalized_thresholds"]], dtype=np.float64
    )

    whole_anchor_metrics = simulate(lifecycles, anchor_thresholds, config)
    observed_anchor = record(0, anchor_thresholds, whole_anchor_metrics, config)
    anchor = config["anchor_reproduction"]
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

    period_names = [
        "development_2024_h1",
        "development_2024_h2",
        "development_2025_h1",
        "development_2025_h2",
    ]
    development_start, development_end = period_bounds(config, "development")
    development_anchor_metrics = simulate(
        lifecycles, anchor_thresholds, config, development_start, development_end
    )
    development = simulate(
        lifecycles, lattice["values"], config, development_start, development_end
    )
    block_anchor_metrics: list[dict[str, np.ndarray]] = []
    block_metrics: list[dict[str, np.ndarray]] = []
    for name in period_names:
        start, end = period_bounds(config, name)
        block_anchor_metrics.append(
            simulate(lifecycles, anchor_thresholds, config, start, end)
        )
        block_metrics.append(simulate(lifecycles, lattice["values"], config, start, end))

    development_anchor_stressed = float(development_anchor_metrics["stressed_net"][0])
    development_anchor_dd = float(development_anchor_metrics["drawdown_pct"][0])
    common = np.ones(len(lattice["values"]), dtype=bool)
    for metrics in block_metrics:
        common &= positive(metrics)
    primary = (
        common
        & (
            development["stressed_net"]
            >= development_anchor_stressed
            * float(config["gates"]["primary_stressed_retention"])
        )
        & (development["drawdown_pct"] <= float(config["gates"]["primary_max_drawdown_pct"]))
    )
    fallback = (
        common
        & (
            development["stressed_net"]
            >= development_anchor_stressed
            * float(config["gates"]["fallback_stressed_retention"])
        )
        & (
            development["drawdown_pct"]
            <= development_anchor_dd
            - float(config["gates"]["fallback_min_drawdown_improvement_points"])
        )
    )
    active_tier = "PRIMARY" if int(primary.sum()) > 0 else "FALLBACK_REHABILITATION"
    eligible = primary if active_tier == "PRIMARY" else fallback
    robust = robust_points(eligible, lattice, development, block_metrics, config)
    selection_kind = "ROBUST_ELIGIBLE"
    ranked_for_selection = robust
    if not robust:
        ranked_for_selection = near_miss_points(
            lattice,
            development,
            block_metrics,
            scalar_record(development_anchor_metrics),
            [scalar_record(metrics) for metrics in block_anchor_metrics],
            config,
        )
        selection_kind = "DECLARED_NEAR_MISS"
    selected_meta = select_separated_then_fill(ranked_for_selection, lattice, config)
    centers = [int(item["index"]) for item in selected_meta]
    if not centers:
        raise RuntimeError("Stage B failed to select mandatory Stage-C centers")

    result: dict[str, Any] = {
        "schema": "zeta-next-dd20-v8-signal-strength-fine-adjacency-proxy-result-v1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "campaign": "dd20-v8-signal-strength-fine-adjacency-proxy-v1",
        "optimization_unit_id": str(config["optimization_unit_id"]),
        "unit_stage": str(config["unit_stage"]),
        "unit_closure_authority": False,
        "authority": {
            "declaration_commit_on_origin_main": str(
                config["declaration_authority"]["commit_on_origin_main"]
            ),
            "exact_v8_is_sole_economic_parent": True,
            "v7_historical_lab_or_prior_optimization_winner_input": False,
            "external_input": False,
            "lab_opened": False,
            "new_entry_strategy": False,
            "all_five_existing_v8_strategies_active": True,
            "thresholds_can_only_suppress_exact_v8_births": True,
            "live_changed": False,
        },
        "inputs": {
            "declaration": {
                "path": str(paths["declaration"].relative_to(REPOSITORY_ROOT)).replace("\\", "/"),
                "bytes": paths["declaration"].stat().st_size,
                "sha256": sha256(paths["declaration"]),
            },
            "lifecycle": {
                "path": str(config["inputs"]["root"]) + "/" + str(config["inputs"]["lifecycle"]["name"]),
                "bytes": paths["lifecycle"].stat().st_size,
                "sha256": sha256(paths["lifecycle"]),
            },
            "candidate": {
                "path": str(config["inputs"]["root"]) + "/" + str(config["inputs"]["candidate"]["name"]),
                "bytes": paths["candidate"].stat().st_size,
                "sha256": sha256(paths["candidate"]),
            },
            "stage_a_raw": {
                "path": str(config["inputs"]["root"]) + "/" + str(config["inputs"]["stage_a_raw"]["name"]),
                "bytes": paths["stage_a_raw"].stat().st_size,
                "sha256": sha256(paths["stage_a_raw"]),
                "status": stage_a_payloads["stage_a_raw"]["status"],
            },
            "stage_a_durable": {
                "path": str(config["inputs"]["root"]) + "/" + str(config["inputs"]["stage_a_durable"]["name"]),
                "bytes": paths["stage_a_durable"].stat().st_size,
                "sha256": sha256(paths["stage_a_durable"]),
                "status": stage_a_payloads["stage_a_durable"]["status"],
            },
            "source_files": [
                {
                    "path": str(path.relative_to(REPOSITORY_ROOT)).replace("\\", "/"),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
                for key, path in sorted(paths.items())
                if key.startswith("source_")
            ],
            "matched_lifecycles": len(lifecycles),
            "diagnostics": input_diagnostics,
        },
        "outcome_free_threshold_construction": {
            "development_signal_passed_populations": [len(values) for values in populations],
            "component_thresholds": [
                {
                    "short": str(config["components"][axis]["short"]),
                    "quantiles": {
                        str(quantile): nearest_rank_threshold(populations[axis], quantile)
                        for quantile in config["strength_lattice"]["precheck_quantile_coordinates"]
                    },
                }
                for axis in range(len(populations))
            ],
            "outcome_columns_used": False,
        },
        "fine_map": {
            "raw_roles": len(lattice["raw_roles"]),
            "unique_threshold_roles": len(lattice["values"]),
            "duplicates_removed": len(lattice["raw_roles"]) - len(lattice["values"]),
            "adjacency_edges": sum(len(values) for values in lattice["adjacency"]) // 2,
            "center_role_counts": lattice["center_role_counts"],
            "center_adjacency_edges": lattice["center_adjacency_edges"],
            "common_positive_four_half_year_roles": int(common.sum()),
            "primary_eligible": int(primary.sum()),
            "fallback_eligible": int(fallback.sum()),
            "active_tier": active_tier,
            "active_tier_eligible": int(eligible.sum()),
            "robust_active_tier_points": len(robust),
            "selection_kind": selection_kind,
        },
        "exact_anchor_whole_path": observed_anchor,
        "exact_anchor_development": record(
            0, anchor_thresholds, development_anchor_metrics, config
        ),
        "exact_anchor_development_blocks": {
            name: record(0, anchor_thresholds, metrics, config)
            for name, metrics in zip(period_names, block_anchor_metrics)
        },
        "development_centers": [],
        "stage_c_strength_centers": [],
        "validation_opened": False,
        "locked_holdout_opened": False,
        "mt5": {
            "shortlist_count": 0,
            "valid_economic_paths_run": 0,
            "maximum_valid_economic_paths_authorized": int(
                config["mt5_budget"]["maximum_valid_economic_paths_after_all_proxy_stages"]
            ),
        },
        "limitations": [
            "Accepted-source-path suppression replay only; 143 observed capacity-blocked exact-V8 opportunities have unknown outcomes and receive zero profit credit.",
            "Source pre-order risk-capital context cannot reconstruct candidate-specific open-equity paths or freed-capacity admissions.",
            "Closed-balance replay is not native MT5 equity drawdown, spread/stop quantization or final economics.",
            "Stage B uses 2024-2025 development only. January-May validation and locked June-July remain unopened.",
        ],
    }

    for rank, (index, meta) in enumerate(zip(centers, selected_meta), start=1):
        item = record(
            index, lattice["values"], development, config, lattice["quantiles"]
        )
        item.update(
            {
                "development_rank": rank,
                "selection_kind": selection_kind,
                "lattice_index": index,
                "center_quantile_provenance": [
                    {
                        "center_rank": int(role["center_rank"]),
                        "quantiles": [float(value) for value in role["quantiles"]],
                    }
                    for role in lattice["provenance"][index]
                ],
                "common_gate_passed": bool(common[index]),
                "primary_gate_passed": bool(primary[index]),
                "fallback_gate_passed": bool(fallback[index]),
                "eligible_neighbor_count": int(meta["eligible_neighbor_count"]),
                "eligible_neighbor_indices": [
                    int(value) for value in meta["eligible_neighbor_indices"]
                ],
                "eligible_neighbor_axes": [
                    str(config["components"][axis]["short"])
                    for axis in meta["eligible_neighbor_axes"]
                ],
                "worst_local_stressed_net_to_drawdown": meta[
                    "worst_local_stressed_net_to_drawdown"
                ],
                "weakest_half_year_stressed_net_usd": float(
                    meta["weakest_half_year_stressed_net_usd"]
                ),
                "normalized_gate_deficit": meta.get("normalized_gate_deficit"),
                "development_blocks": {
                    name: record(
                        index,
                        lattice["values"],
                        metrics,
                        config,
                        lattice["quantiles"],
                    )
                    for name, metrics in zip(period_names, block_metrics)
                },
            }
        )
        result["development_centers"].append(item)
        result["stage_c_strength_centers"].append(
            {
                "development_rank": rank,
                "selection_kind": selection_kind,
                "lattice_index": index,
                "quantile_coordinates": item["quantile_coordinates"],
                "normalized_thresholds": item["normalized_thresholds"],
                "raw_feature_thresholds": item["raw_feature_thresholds"],
                "weights": item["weights"],
                "base_position_risk_fraction": item["base_position_risk_fraction"],
                "aggregate_risk_fraction": item["aggregate_risk_fraction"],
            }
        )

    result["status"] = (
        "VALID_PROXY_COMPLETE_STAGE_B_ROBUST_FINE_STRENGTH_CENTERS_STAGE_C_REQUIRED_NO_MT5"
        if selection_kind == "ROBUST_ELIGIBLE"
        else "VALID_PROXY_COMPLETE_STAGE_B_NEAR_MISS_FINE_STRENGTH_CENTERS_STAGE_C_REQUIRED_NO_MT5"
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
                "stage_c_center_count": len(result["stage_c_strength_centers"]),
                "mt5_paths": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
