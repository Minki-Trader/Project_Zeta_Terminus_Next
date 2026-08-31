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
    authority_path = REPOSITORY_ROOT / str(authority["path"])
    if authority_path.stat().st_size != int(authority["bytes"]):
        raise RuntimeError("declaration authority byte count mismatch")
    if sha256(authority_path) != str(authority["sha256"]):
        raise RuntimeError("declaration authority hash mismatch")
    authority_paths: dict[str, Path] = {"declaration": authority_path}

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
    raw_centers = payloads["stage_b_raw"].get("stage_c_static_seeds", [])
    durable_centers = payloads["stage_b_durable"].get(
        "stage_c_static_seeds", []
    )
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
        if not np.array_equal(raw_weights, expected_weights):
            raise RuntimeError("raw Stage-B seed weights mismatch")
        if not np.array_equal(durable_weights, expected_weights):
            raise RuntimeError("durable Stage-B seed weights mismatch")
        expected_cap = float(expected["aggregate_risk_fraction"])
        if float(raw_centers[index]["aggregate_risk_fraction"]) != expected_cap:
            raise RuntimeError("raw Stage-B seed aggregate cap mismatch")
        if float(durable_centers[index]["aggregate_risk_fraction"]) != expected_cap:
            raise RuntimeError("durable Stage-B seed aggregate cap mismatch")
        if int(raw_centers[index]["development_rank"]) != index + 1:
            raise RuntimeError("raw Stage-B seed rank mismatch")
        if int(durable_centers[index]["development_rank"]) != index + 1:
            raise RuntimeError("durable Stage-B seed rank mismatch")
        expected_mask = int(expected["membership_mask_integer"])
        if int(raw_centers[index]["membership_mask_integer"]) != expected_mask:
            raise RuntimeError("raw Stage-B seed membership mismatch")
        if int(durable_centers[index]["membership_mask_integer"]) != expected_mask:
            raise RuntimeError("durable Stage-B seed membership mismatch")

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
    component_count = len(config["components"])
    aggregate_risk = float(config["aggregate_risk_fraction"])
    state = config["state_lattice"]
    trigger_values = list(map(int, state["loss_close_triggers"]))
    suppression_values = list(
        map(int, state["suppressed_future_source_birth_counts"])
    )
    source_weights = np.asarray(
        [float(item["source_weight"]) for item in config["components"]],
        dtype=np.float64,
    )
    weights: list[list[float]] = []
    seed_indices: list[int] = []
    masks: list[int] = []
    triggers: list[int] = []
    suppressions: list[int] = []
    state_enabled: list[bool] = []
    coordinates: list[tuple[int, int, int]] = []
    neutral_indices: list[int] = []
    coordinate_to_index: dict[tuple[int, int, int], int] = {}
    for seed_index, seed in enumerate(config["static_seeds"]):
        seed_weights = list(map(float, seed["weights"]))
        if len(seed_weights) != component_count:
            raise RuntimeError("static seed component count mismatch")
        mask = int(seed["membership_mask_integer"])
        if float(seed["aggregate_risk_fraction"]) != aggregate_risk:
            raise RuntimeError("static seed aggregate cap mismatch")
        for axis, value in enumerate(seed_weights):
            if bool(mask & (1 << axis)) != (value > 0.0):
                raise RuntimeError("static seed mask/weight mismatch")
        neutral_index = len(weights)
        neutral_indices.append(neutral_index)
        coordinates.append((seed_index, -1, -1))
        coordinate_to_index[(seed_index, -1, -1)] = neutral_index
        weights.append(seed_weights)
        seed_indices.append(seed_index)
        masks.append(mask)
        triggers.append(0)
        suppressions.append(0)
        state_enabled.append(False)
        before = len(weights)
        for trigger_index, suppression_index in itertools.product(
            range(len(trigger_values)), range(len(suppression_values))
        ):
            coordinate = (seed_index, trigger_index, suppression_index)
            coordinate_to_index[coordinate] = len(weights)
            coordinates.append(coordinate)
            weights.append(seed_weights)
            seed_indices.append(seed_index)
            masks.append(mask)
            triggers.append(trigger_values[trigger_index])
            suppressions.append(suppression_values[suppression_index])
            state_enabled.append(True)
        if len(weights) - before != int(state["nonneutral_variants_per_seed"]):
            raise RuntimeError("declared nonneutral variants-per-seed mismatch")
        if len(weights) - neutral_index != int(state["roles_per_seed"]):
            raise RuntimeError("declared roles-per-seed mismatch")

    if len(weights) != int(state["expected_parameterizations"]):
        raise RuntimeError("declared state lattice size mismatch")
    if len(set(coordinates)) != len(coordinates):
        raise RuntimeError("state lattice coordinate collision")
    weight_array = np.asarray(weights, dtype=np.float64)
    values = np.column_stack(
        [
            weight_array,
            np.full(len(weights), aggregate_risk, dtype=np.float64),
            np.asarray(triggers, dtype=np.float64),
            np.asarray(suppressions, dtype=np.float64),
        ]
    )
    adjacency: list[set[int]] = [set() for _ in weights]
    adjacency_axes: list[dict[int, int]] = [dict() for _ in weights]
    for coordinate, index in coordinate_to_index.items():
        seed_index, trigger_index, suppression_index = coordinate
        if trigger_index < 0:
            continue
        for axis, size in ((0, len(trigger_values)), (1, len(suppression_values))):
            for delta in (-1, 1):
                probe_indices = [trigger_index, suppression_index]
                probe_indices[axis] += delta
                if probe_indices[axis] < 0 or probe_indices[axis] >= size:
                    continue
                neighbor = coordinate_to_index[
                    (seed_index, probe_indices[0], probe_indices[1])
                ]
                adjacency[index].add(neighbor)
                adjacency_axes[index][neighbor] = axis
    if np.any(weight_array > source_weights[None, :] + 1.0e-12):
        raise RuntimeError("state lattice violates exact-V8 weight ceiling")
    if np.any(np.sum(weight_array > 0.0, axis=1) == 0):
        raise RuntimeError("empty membership reached state lattice")
    return {
        "values": values,
        "weights": weight_array,
        "masks": np.asarray(masks, dtype=np.int16),
        "seed_indices": np.asarray(seed_indices, dtype=np.int16),
        "coordinates": np.asarray(coordinates, dtype=np.int16),
        "state_enabled": np.asarray(state_enabled, dtype=np.bool_),
        "triggers": np.asarray(triggers, dtype=np.int16),
        "suppressions": np.asarray(suppressions, dtype=np.int16),
        "neutral_indices": np.asarray(neutral_indices, dtype=np.int32),
        "adjacency": adjacency,
        "adjacency_axes": adjacency_axes,
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
    if parameter_values.shape[1] >= component_count + 3:
        loss_trigger = parameter_values[:, component_count + 1].astype(np.int32)
        suppression_length = parameter_values[:, component_count + 2].astype(np.int32)
    else:
        loss_trigger = np.zeros(candidate_count, dtype=np.int32)
        suppression_length = np.zeros(candidate_count, dtype=np.int32)
    state_enabled = (loss_trigger > 0) & (suppression_length > 0)
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
    consecutive_losses = np.zeros((candidate_count, component_count), dtype=np.int32)
    maximum_consecutive_losses = np.zeros_like(consecutive_losses)
    remaining_suppression = np.zeros_like(consecutive_losses)
    trigger_count = np.zeros(candidate_count, dtype=np.int32)
    component_trigger_count = np.zeros_like(consecutive_losses)
    suppressed_source_births = np.zeros(candidate_count, dtype=np.int32)
    suppressed_executable_births = np.zeros(candidate_count, dtype=np.int32)
    component_suppressed_source_births = np.zeros_like(consecutive_losses)
    component_suppressed_executable_births = np.zeros_like(consecutive_losses)
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
            unscaled_target_steps = np.floor(
                base_steps.astype(np.float64) * weights[:, component] + 0.5
            ).astype(np.int32)
            suppressed = state_enabled & (remaining_suppression[:, component] > 0)
            suppressed_executable = suppressed & (unscaled_target_steps > 0)
            target_steps = np.where(suppressed, 0, unscaled_target_steps).astype(
                np.int32
            )
            remaining_suppression[suppressed, component] -= 1
            suppressed_source_births += suppressed.astype(np.int32)
            suppressed_executable_births += suppressed_executable.astype(np.int32)
            component_suppressed_source_births[:, component] += suppressed.astype(
                np.int32
            )
            component_suppressed_executable_births[:, component] += (
                suppressed_executable.astype(np.int32)
            )
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
        accepted_close = admitted_steps > 0
        scale = admitted_steps.astype(np.float64) / float(source_steps)
        actual_increment = item.actual_net_usd * scale
        stressed_increment = item.stressed_net_usd * scale
        actual_balance += actual_increment
        stressed_balance += stressed_increment
        open_risk = np.maximum(0.0, open_risk - admitted_risk)
        component_actual[:, component] += actual_increment
        component_stressed[:, component] += stressed_increment
        component_closed[:, component] += accepted_close.astype(np.int32)
        loss_close = state_enabled & accepted_close & (actual_increment < 0.0)
        nonloss_close = state_enabled & accepted_close & ~loss_close
        consecutive_losses[nonloss_close, component] = 0
        consecutive_losses[loss_close, component] += 1
        maximum_consecutive_losses[:, component] = np.maximum(
            maximum_consecutive_losses[:, component],
            consecutive_losses[:, component],
        )
        triggered = (
            state_enabled
            & loss_close
            & (consecutive_losses[:, component] >= loss_trigger)
        )
        consecutive_losses[triggered, component] = 0
        remaining_suppression[triggered, component] = suppression_length[triggered]
        trigger_count += triggered.astype(np.int32)
        component_trigger_count[:, component] += triggered.astype(np.int32)
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
        "state_enabled": state_enabled.astype(np.int32),
        "loss_trigger": loss_trigger,
        "suppression_length": suppression_length,
        "trigger_count": trigger_count,
        "component_trigger_count": component_trigger_count,
        "suppressed_source_births": suppressed_source_births,
        "suppressed_executable_births": suppressed_executable_births,
        "component_suppressed_source_births": component_suppressed_source_births,
        "component_suppressed_executable_births": component_suppressed_executable_births,
        "maximum_consecutive_losses": maximum_consecutive_losses,
        "remaining_suppression_at_end": remaining_suppression,
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
        "state": {
            "enabled": bool(metrics["state_enabled"][index]),
            "consecutive_loss_close_trigger": int(metrics["loss_trigger"][index]),
            "future_source_birth_suppression_count": int(
                metrics["suppression_length"][index]
            ),
            "trigger_count": int(metrics["trigger_count"][index]),
            "suppressed_source_births": int(
                metrics["suppressed_source_births"][index]
            ),
            "suppressed_executable_births": int(
                metrics["suppressed_executable_births"][index]
            ),
        },
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
                "state_triggers": int(
                    metrics["component_trigger_count"][index, component_index]
                ),
                "suppressed_source_births": int(
                    metrics["component_suppressed_source_births"][
                        index, component_index
                    ]
                ),
                "suppressed_executable_births": int(
                    metrics["component_suppressed_executable_births"][
                        index, component_index
                    ]
                ),
                "maximum_consecutive_losses": int(
                    metrics["maximum_consecutive_losses"][index, component_index]
                ),
                "remaining_suppression_at_end": int(
                    metrics["remaining_suppression_at_end"][index, component_index]
                ),
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


def robust_membership_points(
    eligible: np.ndarray,
    lattice: dict[str, Any],
    development: dict[str, np.ndarray],
    year_2024: dict[str, np.ndarray],
    year_2025: dict[str, np.ndarray],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    eligible_set = set(int(value) for value in np.flatnonzero(eligible))
    minimum_neighbors = int(config["gates"]["minimum_nonneutral_neighbors"])
    minimum_axes = int(config["gates"]["minimum_nonneutral_axes"])
    robust: list[dict[str, Any]] = []
    for index in sorted(eligible_set):
        neighbors = sorted(
            value for value in lattice["adjacency"][index] if value in eligible_set
        )
        axes = {
            int(lattice["adjacency_axes"][index][neighbor]) for neighbor in neighbors
        }
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
                "eligible_nonneutral_neighbor_count": len(neighbors),
                "eligible_nonneutral_neighbor_indices": neighbors,
                "eligible_state_axis_count": len(axes),
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
    nonneutral_activity = (
        lattice["state_enabled"]
        & (development["trigger_count"] > 0)
        & (development["suppressed_executable_births"] > 0)
    )
    nonneutral_eligible = eligible & nonneutral_activity
    robust = robust_membership_points(
        nonneutral_eligible, lattice, development, year_2024, year_2025, config
    )
    tolerance = float(config["gates"]["neutral_comparison_tolerance"])
    selected_indices: list[int] = []
    selected_meta: list[dict[str, Any]] = []
    for seed_index, neutral_index_value in enumerate(lattice["neutral_indices"]):
        neutral_index = int(neutral_index_value)
        if not bool(eligible[neutral_index]):
            raise RuntimeError("frozen neutral seed lost declared development eligibility")
        candidates = [
            item
            for item in robust
            if int(lattice["seed_indices"][item["index"]]) == seed_index
        ]
        neutral_weakest = min(
            float(year_2024["stressed_net"][neutral_index]),
            float(year_2025["stressed_net"][neutral_index]),
        )
        neutral_efficiency = float(development["stressed_net"][neutral_index]) / max(
            float(development["drawdown_pct"][neutral_index]), 1.0e-12
        )
        selected_index = neutral_index
        meta: dict[str, Any] = {
            "index": neutral_index,
            "selection_kind": "NEUTRAL_RETAINED",
            "reason": "No robust nonneutral role improved frozen neutral precedence.",
            "eligible_nonneutral_neighbor_count": 0,
            "eligible_nonneutral_neighbor_indices": [],
            "eligible_state_axis_count": 0,
            "worst_local_stressed_net_to_drawdown": None,
            "weakest_annual_stressed_net_usd": neutral_weakest,
            "neutral_weakest_annual_stressed_net_usd": neutral_weakest,
            "neutral_development_stressed_net_to_drawdown": neutral_efficiency,
        }
        if candidates:
            best = candidates[0]
            best_index = int(best["index"])
            best_weakest = float(best["weakest_annual_stressed_net_usd"])
            best_efficiency = float(development["stressed_net"][best_index]) / max(
                float(development["drawdown_pct"][best_index]), 1.0e-12
            )
            improves_weakest = best_weakest > neutral_weakest + tolerance
            ties_and_improves_efficiency = (
                abs(best_weakest - neutral_weakest) <= tolerance
                and best_efficiency > neutral_efficiency + tolerance
            )
            if improves_weakest or ties_and_improves_efficiency:
                selected_index = best_index
                meta = dict(best)
                meta.update(
                    {
                        "selection_kind": "ROBUST_CAUSAL_DISPLACED_NEUTRAL",
                        "reason": "Robust causal role passed frozen weakest-year/efficiency precedence.",
                        "neutral_weakest_annual_stressed_net_usd": neutral_weakest,
                        "neutral_development_stressed_net_to_drawdown": neutral_efficiency,
                    }
                )
        selected_indices.append(selected_index)
        selected_meta.append(meta)
    if len(selected_indices) != len(config["static_seeds"]):
        raise RuntimeError("Stage-C per-seed development selection count mismatch")

    validation_start, validation_end = period_bounds(config, "validation")
    validation_values = lattice["values"][selected_indices]
    validation = simulate(
        lifecycles, validation_values, config, validation_start, validation_end
    )
    validation_anchor_metrics = simulate(
        lifecycles, anchor_values, config, validation_start, validation_end
    )
    validation_anchor_stressed = float(validation_anchor_metrics["stressed_net"][0])
    validation_pass = (
        positive(validation)
        & (
            validation["drawdown_pct"]
            <= float(config["gates"]["validation_max_drawdown_pct"])
        )
        & (
            validation["stressed_net"]
            >= validation_anchor_stressed
            * float(config["gates"]["validation_minimum_stressed_retention"])
        )
    )

    result: dict[str, Any] = {
        "schema": "zeta-next-dd20-v8-component-local-loss-suspension-proxy-result-v1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "campaign": "dd20-v8-component-local-loss-suspension-proxy-v1",
        "optimization_unit_id": str(config["optimization_unit_id"]),
        "unit_stage": str(config["unit_stage"]),
        "unit_closure_authority": False,
        "authority": {
            "declaration_commit_on_origin_main": str(
                config["declaration_authority"]["commit_on_origin_main"]
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
        "state_map": {
            "declared_parameterizations": int(len(lattice["values"])),
            "neutral_roles": int((~lattice["state_enabled"]).sum()),
            "nonneutral_roles": int(lattice["state_enabled"].sum()),
            "primary_eligible": int(primary.sum()),
            "fallback_eligible": int(fallback.sum()),
            "active_tier": active_tier,
            "active_tier_eligible": int(eligible.sum()),
            "nonneutral_active_eligible": int(nonneutral_eligible.sum()),
            "robust_nonneutral_active_tier_points": len(robust),
            "development_selected_roles": len(selected_indices),
            "causal_roles_displacing_neutral": sum(
                item["selection_kind"] == "ROBUST_CAUSAL_DISPLACED_NEUTRAL"
                for item in selected_meta
            ),
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
        "exact_anchor_validation": record(
            0, anchor_values, validation_anchor_metrics, config
        ),
        "development_selected_roles": [],
        "validation": [],
        "stage_d_roles": [],
        "validation_opened": True,
        "locked_holdout_opened": False,
        "mt5": {
            "shortlist_count": 0,
            "valid_economic_paths_run": 0,
            "maximum_valid_economic_paths_authorized": int(
                config["mt5_budget"]["maximum_valid_economic_paths_after_stage_d"]
            ),
        },
        "limitations": [
            "Accepted-source-path suppression/resizing replay only; 143 observed capacity-blocked existing-V8 opportunities have unknown outcomes and receive zero profit credit.",
            "Source pre-order risk-capital context can reduce admission capital but cannot reconstruct candidate-specific open-equity paths.",
            "A different capital ladder can alter native stop quantization; closed-balance replay is not native MT5 equity drawdown or final economics.",
            "Component-local state uses candidate-admitted actual closes only and suppresses future accepted-source births; unknown freed-capacity outcomes receive zero credit.",
            "January-May validation is opened only for exactly one frozen development role per seed. Locked June-July remains unopened.",
        ],
    }

    component_names = [str(item["short"]) for item in config["components"]]
    for seed_rank, (index, meta) in enumerate(
        zip(selected_indices, selected_meta), start=1
    ):
        item = record(
            index,
            lattice["values"],
            development,
            config,
        )
        mask = int(lattice["masks"][index])
        item.update(
            {
                "static_seed_rank": seed_rank,
                "selection_kind": meta["selection_kind"],
                "selection_reason": meta["reason"],
                "membership_mask_integer": mask,
                "membership_mask_binary_rc61_to_return": format(mask, "05b")[::-1],
                "active_components": [
                    name for axis, name in enumerate(component_names) if mask & (1 << axis)
                ],
                "state_coordinate": [
                    int(value) for value in lattice["coordinates"][index]
                ],
                "common_gate_passed": bool(common[index]),
                "primary_gate_passed": bool(primary[index]),
                "fallback_gate_passed": bool(fallback[index]),
                "eligible_nonneutral_neighbor_count": int(
                    meta["eligible_nonneutral_neighbor_count"]
                ),
                "eligible_nonneutral_neighbor_indices": [
                    int(value) for value in meta["eligible_nonneutral_neighbor_indices"]
                ],
                "eligible_state_axis_count": int(
                    meta["eligible_state_axis_count"]
                ),
                "worst_local_stressed_net_to_drawdown": meta[
                    "worst_local_stressed_net_to_drawdown"
                ],
                "weakest_annual_stressed_net_usd": float(
                    meta["weakest_annual_stressed_net_usd"]
                ),
                "neutral_weakest_annual_stressed_net_usd": float(
                    meta["neutral_weakest_annual_stressed_net_usd"]
                ),
                "neutral_development_stressed_net_to_drawdown": float(
                    meta["neutral_development_stressed_net_to_drawdown"]
                ),
                "development_2024": record(
                    index, lattice["values"], year_2024, config
                ),
                "development_2025": record(
                    index, lattice["values"], year_2025, config
                ),
            }
        )
        result["development_selected_roles"].append(item)

    for local_index, global_index in enumerate(selected_indices):
        validation_item = record(
            local_index,
            validation_values,
            validation,
            config,
            lattice["coordinates"][global_index],
        )
        validation_item["static_seed_rank"] = local_index + 1
        validation_item["development_selection_kind"] = selected_meta[local_index][
            "selection_kind"
        ]
        validation_item["stressed_retention_vs_exact_v8_validation"] = (
            float(validation["stressed_net"][local_index])
            / max(validation_anchor_stressed, 1.0e-12)
        )
        validation_item["passed"] = bool(validation_pass[local_index])
        result["validation"].append(validation_item)
        if validation_pass[local_index]:
            result["stage_d_roles"].append(
                {
                    "static_seed_rank": local_index + 1,
                    "development_selection_kind": selected_meta[local_index][
                        "selection_kind"
                    ],
                    "membership_mask_integer": int(lattice["masks"][global_index]),
                    "weights": [
                        float(value)
                        for value in lattice["weights"][global_index]
                    ],
                    "base_position_risk_fraction": float(
                        config["base_position_risk_fraction"]
                    ),
                    "aggregate_risk_fraction": float(
                        config["aggregate_risk_fraction"]
                    ),
                    "consecutive_loss_close_trigger": int(
                        lattice["triggers"][global_index]
                    ),
                    "future_source_birth_suppression_count": int(
                        lattice["suppressions"][global_index]
                    ),
                }
            )
    if len(result["stage_d_roles"]) > int(config["gates"]["maximum_stage_d_roles"]):
        raise RuntimeError("Stage-D role limit exceeded")
    result["status"] = (
        "VALID_PROXY_COMPLETE_STAGE_C_VALIDATION_ROLES_STAGE_D_REQUIRED_NO_MT5"
        if result["stage_d_roles"]
        else "VALID_PROXY_COMPLETE_STAGE_C_VALIDATION_NONCONFIRMATION_STAGE_D_EMPTY_REQUIRED_NO_MT5"
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
                "stage_d_role_count": len(result["stage_d_roles"]),
                "mt5_paths": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
