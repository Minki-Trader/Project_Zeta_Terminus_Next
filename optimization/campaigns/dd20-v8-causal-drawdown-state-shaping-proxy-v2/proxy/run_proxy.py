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


def verify_and_load_lifecycles(
    config: dict[str, Any],
) -> tuple[dict[str, Path], list[Lifecycle], dict[str, Any], dict[str, Any]]:
    declared_inputs = config["inputs"]
    input_root = REPOSITORY_ROOT / str(declared_inputs["root"])
    paths: dict[str, Path] = {}
    for role in ("lifecycle", "candidate", "stage_b", "v1"):
        declared = declared_inputs[role]
        path = input_root / str(declared["name"])
        if path.stat().st_size != int(declared["bytes"]):
            raise RuntimeError(f"staged {role} byte count mismatch")
        if sha256(path) != str(declared["sha256"]):
            raise RuntimeError(f"staged {role} hash mismatch")
        paths[role] = path

    lifecycle_declared = declared_inputs["lifecycle"]
    candidate_declared = declared_inputs["candidate"]
    stage_b_declared = declared_inputs["stage_b"]
    stage_b_result = json.loads(paths["stage_b"].read_text(encoding="utf-8"))
    if stage_b_result.get("schema") != str(stage_b_declared["schema"]):
        raise RuntimeError("staged Stage-B schema mismatch")
    if stage_b_result.get("status") != str(stage_b_declared["status"]):
        raise RuntimeError("staged Stage-B status mismatch")
    v1_declared = declared_inputs["v1"]
    v1_result = json.loads(paths["v1"].read_text(encoding="utf-8"))
    if v1_result.get("schema") != str(v1_declared["schema"]):
        raise RuntimeError("staged V1 schema mismatch")
    if v1_result.get("status") != str(v1_declared["status"]):
        raise RuntimeError("staged V1 status mismatch")
    observed_centers = stage_b_result.get("stage_c_seed_centers", [])
    declared_centers = config["static_seeds"]
    if len(observed_centers) != int(stage_b_declared["stage_c_seed_count"]):
        raise RuntimeError("staged Stage-B center count mismatch")
    if len(observed_centers) != len(declared_centers):
        raise RuntimeError("declared static seed count mismatch")
    for observed, declared in zip(observed_centers, declared_centers):
        observed_parameters = observed["parameters"]
        observed_values = list(map(float, observed_parameters["weights"]))
        declared_values = list(map(float, declared["weights"]))
        if len(observed_values) != len(declared_values):
            raise RuntimeError("staged Stage-B center width mismatch")
        if not np.allclose(observed_values, declared_values, atol=1.0e-12, rtol=0.0):
            raise RuntimeError("staged Stage-B center weight mismatch")
        if not math.isclose(
            float(observed_parameters["aggregate_risk_fraction"]),
            float(declared["aggregate_risk_fraction"]),
            abs_tol=1.0e-12,
            rel_tol=0.0,
        ):
            raise RuntimeError("staged Stage-B center aggregate-risk mismatch")

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
    return paths, lifecycles, stage_b_result, v1_result


def build_lattice(config: dict[str, Any]) -> dict[str, np.ndarray]:
    state = config["state_lattice"]
    trigger_values = list(map(float, state["trigger_drawdown_fractions"]))
    multiplier_values = list(map(float, state["future_birth_multipliers"]))
    hysteresis_values = list(map(float, state["release_hysteresis_fractions"]))
    hold_values = list(map(int, state["minimum_subsequent_accepted_closes"]))
    coordinates: list[tuple[int, int, int, int, int]] = []
    seed_indices: list[int] = []
    weights: list[list[float]] = []
    aggregate_risk: list[float] = []
    triggers: list[float] = []
    multipliers: list[float] = []
    hysteresis: list[float] = []
    minimum_holds: list[int] = []
    for seed_index, seed in enumerate(config["static_seeds"]):
        seed_weights = list(map(float, seed["weights"]))
        if len(seed_weights) != len(config["components"]):
            raise RuntimeError("static seed component count mismatch")
        before = len(coordinates)
        for trigger_index, multiplier_index, hysteresis_index, hold_index in itertools.product(
            range(len(trigger_values)),
            range(len(multiplier_values)),
            range(len(hysteresis_values)),
            range(len(hold_values)),
        ):
            coordinates.append(
                (
                    seed_index,
                    trigger_index,
                    multiplier_index,
                    hysteresis_index,
                    hold_index,
                )
            )
            seed_indices.append(seed_index)
            weights.append(seed_weights)
            aggregate_risk.append(float(seed["aggregate_risk_fraction"]))
            triggers.append(trigger_values[trigger_index])
            multipliers.append(multiplier_values[multiplier_index])
            hysteresis.append(hysteresis_values[hysteresis_index])
            minimum_holds.append(hold_values[hold_index])
        if len(coordinates) - before != int(state["variants_per_static_seed"]):
            raise RuntimeError("declared per-seed state variant count mismatch")
    if len(coordinates) != int(state["expected_parameterizations"]):
        raise RuntimeError("declared state lattice size mismatch")
    if len(set(coordinates)) != len(coordinates):
        raise RuntimeError("state lattice coordinate collision")
    weight_array = np.asarray(weights, dtype=np.float64)
    source_weights = np.asarray(
        [float(item["source_weight"]) for item in config["components"]],
        dtype=np.float64,
    )
    if np.any(weight_array > source_weights[None, :] + 1.0e-12):
        raise RuntimeError("state lattice violates monotone effective-risk rule")
    return {
        "coordinates": np.asarray(coordinates, dtype=np.int16),
        "seed_index": np.asarray(seed_indices, dtype=np.int16),
        "weights": weight_array,
        "aggregate_risk": np.asarray(aggregate_risk, dtype=np.float64),
        "state_enabled": np.ones(len(coordinates), dtype=np.bool_),
        "trigger_drawdown": np.asarray(triggers, dtype=np.float64),
        "state_multiplier": np.asarray(multipliers, dtype=np.float64),
        "release_hysteresis": np.asarray(hysteresis, dtype=np.float64),
        "minimum_hold_closes": np.asarray(minimum_holds, dtype=np.int32),
    }


def static_candidates(
    weights: list[list[float]], aggregate_risk: list[float]
) -> dict[str, np.ndarray]:
    count = len(weights)
    if count != len(aggregate_risk):
        raise RuntimeError("static candidate width mismatch")
    return {
        "coordinates": np.zeros((count, 5), dtype=np.int16),
        "seed_index": np.arange(count, dtype=np.int16),
        "weights": np.asarray(weights, dtype=np.float64),
        "aggregate_risk": np.asarray(aggregate_risk, dtype=np.float64),
        "state_enabled": np.zeros(count, dtype=np.bool_),
        "trigger_drawdown": np.ones(count, dtype=np.float64),
        "state_multiplier": np.ones(count, dtype=np.float64),
        "release_hysteresis": np.zeros(count, dtype=np.float64),
        "minimum_hold_closes": np.zeros(count, dtype=np.int32),
    }


def subset_candidates(
    candidates: dict[str, np.ndarray], indices: list[int]
) -> dict[str, np.ndarray]:
    selected = np.asarray(indices, dtype=np.int64)
    return {key: values[selected] for key, values in candidates.items()}


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
    candidates: dict[str, np.ndarray],
    config: dict[str, Any],
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, np.ndarray]:
    component_count = len(config["components"])
    weights = candidates["weights"]
    aggregate_risk = candidates["aggregate_risk"]
    candidate_count = weights.shape[0]
    if weights.shape != (candidate_count, component_count):
        raise RuntimeError("candidate weight matrix mismatch")
    state_enabled = candidates["state_enabled"].astype(np.bool_, copy=False)
    trigger_drawdown = candidates["trigger_drawdown"]
    state_multiplier = candidates["state_multiplier"]
    release_drawdown = np.maximum(
        0.0, trigger_drawdown - candidates["release_hysteresis"]
    )
    minimum_hold_closes = candidates["minimum_hold_closes"]
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
    state_active = np.zeros(candidate_count, dtype=np.bool_)
    state_hold_count = np.zeros(candidate_count, dtype=np.int32)
    state_maximum_hold_count = np.zeros(candidate_count, dtype=np.int32)
    state_trigger_count = np.zeros(candidate_count, dtype=np.int32)
    state_release_count = np.zeros(candidate_count, dtype=np.int32)
    state_active_births = np.zeros(candidate_count, dtype=np.int32)
    state_changed_births = np.zeros(candidate_count, dtype=np.int32)
    state_admitted_births = np.zeros(candidate_count, dtype=np.int32)
    state_hold_closes = np.zeros(candidate_count, dtype=np.int32)
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
            active_birth = state_enabled & state_active
            effective_state_multiplier = np.where(
                active_birth, state_multiplier, 1.0
            )
            target_steps = np.floor(
                base_steps.astype(np.float64)
                * weights[:, component]
                * effective_state_multiplier
                + 0.5
            ).astype(np.int32)
            changed_birth = active_birth & (target_steps != unscaled_target_steps)
            state_active_births += active_birth.astype(np.int32)
            state_changed_births += changed_birth.astype(np.int32)
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
            state_admitted_births += (active_birth & admitted).astype(np.int32)
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
        current_actual_drawdown = np.where(
            actual_peak > 0.0,
            np.maximum(0.0, (actual_peak - actual_balance) / actual_peak),
            np.inf,
        )
        was_active = state_active.copy()
        counted_close = state_enabled & was_active & accepted_close
        state_hold_count += counted_close.astype(np.int32)
        state_hold_closes += counted_close.astype(np.int32)
        state_maximum_hold_count = np.maximum(
            state_maximum_hold_count, state_hold_count
        )
        release = (
            counted_close
            & (state_hold_count >= minimum_hold_closes)
            & (current_actual_drawdown <= release_drawdown + 1.0e-12)
        )
        state_active[release] = False
        state_hold_count[release] = 0
        state_release_count += release.astype(np.int32)
        trigger = (
            state_enabled
            & ~state_active
            & accepted_close
            & (current_actual_drawdown + 1.0e-12 >= trigger_drawdown)
        )
        state_active[trigger] = True
        state_hold_count[trigger] = 0
        state_trigger_count += trigger.astype(np.int32)

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
        "state_trigger_count": state_trigger_count,
        "state_release_count": state_release_count,
        "state_active_births": state_active_births,
        "state_changed_births": state_changed_births,
        "state_admitted_births": state_admitted_births,
        "state_hold_closes": state_hold_closes,
        "state_maximum_hold_count": state_maximum_hold_count,
        "state_active_at_period_end": state_active.astype(np.int32),
    }


def period_bounds(config: dict[str, Any], name: str) -> tuple[datetime, datetime]:
    values = config["periods"][name]
    return iso_time(values[0]), iso_time(values[1])


def record(
    index: int,
    candidates: dict[str, np.ndarray],
    metrics: dict[str, np.ndarray],
    config: dict[str, Any],
    coordinate: np.ndarray | None = None,
) -> dict[str, Any]:
    state_enabled = bool(candidates["state_enabled"][index])
    result: dict[str, Any] = {
        "weights": [float(value) for value in candidates["weights"][index]],
        "base_position_risk_fraction": float(config["base_position_risk_fraction"]),
        "aggregate_risk_fraction": float(candidates["aggregate_risk"][index]),
        "static_seed_index": int(candidates["seed_index"][index]),
        "state": {
            "enabled": state_enabled,
            "trigger_drawdown_fraction": float(candidates["trigger_drawdown"][index])
            if state_enabled
            else None,
            "future_birth_multiplier": float(candidates["state_multiplier"][index])
            if state_enabled
            else None,
            "release_hysteresis_fraction": float(
                candidates["release_hysteresis"][index]
            )
            if state_enabled
            else None,
            "minimum_subsequent_accepted_closes": int(
                candidates["minimum_hold_closes"][index]
            )
            if state_enabled
            else None,
            "trigger_count": int(metrics["state_trigger_count"][index]),
            "release_count": int(metrics["state_release_count"][index]),
            "births_observed_while_active": int(
                metrics["state_active_births"][index]
            ),
            "births_whose_target_steps_changed": int(
                metrics["state_changed_births"][index]
            ),
            "admitted_births_while_active": int(
                metrics["state_admitted_births"][index]
            ),
            "accepted_closes_counted_toward_hold": int(
                metrics["state_hold_closes"][index]
            ),
            "maximum_hold_count": int(metrics["state_maximum_hold_count"][index]),
            "active_at_period_end": bool(
                metrics["state_active_at_period_end"][index]
            ),
        },
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


def choose_plateau_centers(
    eligible: np.ndarray,
    lattice: dict[str, np.ndarray],
    development: dict[str, np.ndarray],
    config: dict[str, Any],
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
        for axis in range(1, coordinates.shape[1]):
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
                "static_seed_index": int(lattice["seed_index"][index]),
            }
        )
    plateau.sort(
        key=lambda item: (
            -item["worst_local_stressed_net_to_drawdown"],
            -float(development["stressed_net"][item["index"]])
            / max(float(development["drawdown_pct"][item["index"]]), 1.0e-12),
            -float(development["stressed_net"][item["index"]]),
            float(development["drawdown_pct"][item["index"]]),
            -float(lattice["trigger_drawdown"][item["index"]]),
            -float(lattice["state_multiplier"][item["index"]]),
            float(lattice["release_hysteresis"][item["index"]]),
            int(lattice["minimum_hold_closes"][item["index"]]),
            tuple(int(value) for value in coordinates[item["index"]]),
        )
    )
    maximum = int(config["gates"]["maximum_total_centers"])
    maximum_per_seed = int(config["gates"]["maximum_centers_per_static_seed"])
    selected: list[int] = []
    selected_meta: list[dict[str, Any]] = []
    selected_per_seed: dict[int, int] = {}
    for item in plateau:
        seed_index = int(item["static_seed_index"])
        if selected_per_seed.get(seed_index, 0) >= maximum_per_seed:
            continue
        selected.append(int(item["index"]))
        selected_meta.append(item)
        selected_per_seed[seed_index] = selected_per_seed.get(seed_index, 0) + 1
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
    input_paths, lifecycles, stage_b_result, v1_result = verify_and_load_lifecycles(config)
    lattice = build_lattice(config)

    anchor = config["anchor_reproduction"]
    anchor_candidates = static_candidates(
        [list(map(float, anchor["weights"]))],
        [float(anchor["aggregate_risk_fraction"])],
    )
    seed_candidates = static_candidates(
        [list(map(float, item["weights"])) for item in config["static_seeds"]],
        [float(item["aggregate_risk_fraction"]) for item in config["static_seeds"]],
    )

    whole_anchor_metrics = simulate(lifecycles, anchor_candidates, config)
    observed_anchor = record(0, anchor_candidates, whole_anchor_metrics, config)
    if observed_anchor["accepted_source_lifecycles"] != int(anchor["accepted_lifecycles"]):
        raise RuntimeError("exact anchor accepted lifecycle reproduction failed")
    if observed_anchor["source_volume_matches"] != int(anchor["source_volume_matches"]):
        raise RuntimeError("exact anchor source volume reproduction failed")
    if observed_anchor["source_risk_capital_matches"] != int(anchor["joined_birth_open_rows"]):
        raise RuntimeError("exact anchor source risk-capital reproduction failed")
    if observed_anchor["source_position_cap_matches"] != int(anchor["joined_birth_open_rows"]):
        raise RuntimeError("exact anchor source position-cap reproduction failed")
    if abs(observed_anchor["actual_net_usd"] - float(anchor["actual_net_usd"])) > float(
        anchor["net_tolerance_usd"]
    ):
        raise RuntimeError("exact anchor actual reproduction failed")
    if abs(observed_anchor["stressed_net_usd"] - float(anchor["stressed_net_usd"])) > float(
        anchor["net_tolerance_usd"]
    ):
        raise RuntimeError("exact anchor stressed reproduction failed")
    if abs(
        observed_anchor["raw_closed_balance_drawdown_pct"]
        - float(anchor["closed_balance_drawdown_pct"])
    ) > float(anchor["drawdown_tolerance_points"]):
        raise RuntimeError("exact anchor drawdown reproduction failed")

    development_start, development_end = period_bounds(config, "development")
    year_2024_start, year_2024_end = period_bounds(config, "development_2024")
    year_2025_start, year_2025_end = period_bounds(config, "development_2025")
    development_anchor_metrics = simulate(
        lifecycles, anchor_candidates, config, development_start, development_end
    )
    static_seed_development = simulate(
        lifecycles, seed_candidates, config, development_start, development_end
    )
    seed_reproduction = config["static_seed_development_reproduction"]
    observed_stage_b_centers = stage_b_result["development_centers"]
    for seed_index in range(len(config["static_seeds"])):
        if abs(
            float(static_seed_development["actual_net"][seed_index])
            - float(seed_reproduction["actual_net_usd"])
        ) > float(seed_reproduction["net_tolerance_usd"]):
            raise RuntimeError("static seed development actual reproduction failed")
        if abs(
            float(static_seed_development["stressed_net"][seed_index])
            - float(seed_reproduction["stressed_net_usd"])
        ) > float(seed_reproduction["net_tolerance_usd"]):
            raise RuntimeError("static seed development stressed reproduction failed")
        if abs(
            float(static_seed_development["drawdown_pct"][seed_index])
            - float(seed_reproduction["closed_balance_drawdown_pct"])
        ) > float(seed_reproduction["drawdown_tolerance_points"]):
            raise RuntimeError("static seed development drawdown reproduction failed")
        stage_b_center = observed_stage_b_centers[seed_index]
        if abs(
            float(static_seed_development["actual_net"][seed_index])
            - float(stage_b_center["actual_net_usd"])
        ) > float(seed_reproduction["net_tolerance_usd"]):
            raise RuntimeError("static seed differs from staged Stage-B actual")
        if abs(
            float(static_seed_development["stressed_net"][seed_index])
            - float(stage_b_center["stressed_net_usd"])
        ) > float(seed_reproduction["net_tolerance_usd"]):
            raise RuntimeError("static seed differs from staged Stage-B stressed")

    development = simulate(
        lifecycles, lattice, config, development_start, development_end
    )
    year_2024 = simulate(
        lifecycles, lattice, config, year_2024_start, year_2024_end
    )
    year_2025 = simulate(
        lifecycles, lattice, config, year_2025_start, year_2025_end
    )
    development_anchor_stressed = float(development_anchor_metrics["stressed_net"][0])
    own_seed_drawdown = static_seed_development["drawdown_pct"][
        lattice["seed_index"].astype(np.int64)
    ]
    common = (
        positive(development)
        & positive(year_2024)
        & positive(year_2025)
        & (development["state_trigger_count"] > 0)
        & (development["state_changed_births"] > 0)
    )
    primary = (
        common
        & (
            development["stressed_net"]
            >= development_anchor_stressed
            * float(
                config["gates"][
                    "primary_stressed_retention_vs_exact_v8_development"
                ]
            )
        )
        & (
            development["drawdown_pct"]
            <= float(config["gates"]["primary_max_drawdown_pct"])
        )
        & (
            development["drawdown_pct"]
            <= own_seed_drawdown
            - float(
                config["gates"][
                    "primary_minimum_seed_drawdown_improvement_points"
                ]
            )
        )
    )
    fallback = (
        common
        & (
            development["stressed_net"]
            >= development_anchor_stressed
            * float(
                config["gates"][
                    "fallback_stressed_retention_vs_exact_v8_development"
                ]
            )
        )
        & (
            development["drawdown_pct"]
            <= own_seed_drawdown
            - float(
                config["gates"][
                    "fallback_minimum_seed_drawdown_improvement_points"
                ]
            )
        )
    )
    active_tier = "PRIMARY" if int(primary.sum()) > 0 else "FALLBACK_REHABILITATION"
    eligible = primary if active_tier == "PRIMARY" else fallback
    centers, center_meta = choose_plateau_centers(
        eligible, lattice, development, config
    )

    result: dict[str, Any] = {
        "schema": "zeta-next-dd20-v8-causal-drawdown-state-shaping-proxy-result-v2",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "campaign": "dd20-v8-causal-drawdown-state-shaping-proxy-v2",
        "optimization_unit_id": str(config["optimization_unit_id"]),
        "unit_stage": str(config["unit_stage"]),
        "unit_closure_authority": False,
        "inputs": {
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
            "stage_b": {
                "path": str(config["inputs"]["root"])
                + "/"
                + str(config["inputs"]["stage_b"]["name"]),
                "bytes": input_paths["stage_b"].stat().st_size,
                "sha256": sha256(input_paths["stage_b"]),
                "status": str(stage_b_result["status"]),
            },
            "v1_correction_parity": {
                "path": str(config["inputs"]["root"])
                + "/"
                + str(config["inputs"]["v1"]["name"]),
                "bytes": input_paths["v1"].stat().st_size,
                "sha256": sha256(input_paths["v1"]),
                "status": str(v1_result["status"]),
            },
            "matched_lifecycles": len(lifecycles),
        },
        "lattice": {
            "declared_parameterizations": int(len(lattice["seed_index"])),
            "variants_per_static_seed": int(
                config["state_lattice"]["variants_per_static_seed"]
            ),
            "static_seed_count": len(config["static_seeds"]),
            "primary_eligible": int(primary.sum()),
            "fallback_eligible": int(fallback.sum()),
            "active_tier": active_tier,
            "active_tier_eligible": int(eligible.sum()),
        },
        "exact_anchor_whole_path": observed_anchor,
        "exact_anchor_development": record(
            0, anchor_candidates, development_anchor_metrics, config
        ),
        "static_seed_development": [
            record(index, seed_candidates, static_seed_development, config)
            for index in range(len(config["static_seeds"]))
        ],
        "development_plateau_population": 0,
        "development_centers": [],
        "validation": [],
        "winner": None,
        "locked_holdout": None,
        "winner_whole_path": None,
        "stage_d_roles": [],
        "mt5": {
            "shortlist_count": 0,
            "valid_economic_paths_run": 0,
            "stage_c_authorized_paths": int(
                config["mt5_budget"]["stage_c_authorized_paths"]
            ),
            "maximum_valid_economic_paths_after_stage_d": int(
                config["mt5_budget"][
                    "maximum_valid_economic_paths_after_stage_d"
                ]
            ),
        },
        "limitations": [
            "Accepted-source-path causal state replay only; freed-capacity opportunities are absent and receive zero credit.",
            "Actual closed-balance state is causal and deployable, but source context cannot reconstruct candidate-specific open equity.",
            "A changed capital ladder can alter native stop quantization; proxy drawdown is not native MT5 equity drawdown.",
            "Stage C supplies unchanged state roles to mandatory temporal/cost Stage D and never opens MT5 directly.",
        ],
    }

    coordinates = lattice["coordinates"]
    coordinate_to_index = {
        tuple(int(value) for value in row): index
        for index, row in enumerate(coordinates)
    }
    eligible_set = set(int(value) for value in np.flatnonzero(eligible))
    plateau_count = 0
    for index in eligible_set:
        axes: set[int] = set()
        neighbors = 0
        for axis in range(1, coordinates.shape[1]):
            for delta in (-1, 1):
                probe = coordinates[index].copy()
                probe[axis] += delta
                neighbor = coordinate_to_index.get(
                    tuple(int(value) for value in probe)
                )
                if neighbor is not None and neighbor in eligible_set:
                    neighbors += 1
                    axes.add(axis)
        if (
            neighbors >= int(config["gates"]["minimum_eligible_neighbors"])
            and len(axes) >= int(config["gates"]["minimum_neighbor_axes"])
        ):
            plateau_count += 1
    result["development_plateau_population"] = plateau_count

    for rank, (index, meta) in enumerate(zip(centers, center_meta), start=1):
        item = record(
            index,
            lattice,
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
                "seed_drawdown_improvement_points": float(
                    own_seed_drawdown[index] - development["drawdown_pct"][index]
                ),
                "development_2024": record(index, lattice, year_2024, config),
                "development_2025": record(index, lattice, year_2025, config),
            }
        )
        result["development_centers"].append(item)

    if not centers:
        result["status"] = (
            "VALID_PROXY_COMPLETE_STAGE_C_NO_DEVELOPMENT_ELIGIBLE_STAGE_D_EMPTY_CLOSURE_REQUIRED_NO_MT5"
            if int(eligible.sum()) == 0
            else "VALID_PROXY_COMPLETE_STAGE_C_NO_ROBUST_STATE_PLATEAU_STAGE_D_EMPTY_CLOSURE_REQUIRED_NO_MT5"
        )
    else:
        validation_start, validation_end = period_bounds(config, "validation")
        validation_candidates = subset_candidates(lattice, centers)
        validation = simulate(
            lifecycles,
            validation_candidates,
            config,
            validation_start,
            validation_end,
        )
        validation_pass = positive(validation) & (
            validation["drawdown_pct"]
            <= float(config["gates"]["validation_max_drawdown_pct"])
        )
        passing_roles: list[int] = []
        for local_index, global_index in enumerate(centers):
            item = record(
                local_index,
                validation_candidates,
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
            result["status"] = (
                "VALID_PROXY_COMPLETE_STAGE_C_VALIDATION_NONCONFIRMATION_"
                "STAGE_D_EMPTY_CLOSURE_REQUIRED_NO_MT5"
            )
        else:
            winner_local = passing_roles[0]
            winner_global = centers[winner_local]
            result["winner"] = {
                "development_rank": winner_local + 1,
                "lattice_index": int(winner_global),
                "parameters": record(
                    winner_local,
                    validation_candidates,
                    validation,
                    config,
                    lattice["coordinates"][winner_global],
                ),
            }
            holdout_start, holdout_end = period_bounds(config, "locked_holdout")
            winner_candidates = subset_candidates(lattice, [winner_global])
            holdout = simulate(
                lifecycles,
                winner_candidates,
                config,
                holdout_start,
                holdout_end,
            )
            holdout_pass = bool(
                positive(holdout)[0]
                and holdout["drawdown_pct"][0]
                <= float(config["gates"]["holdout_max_drawdown_pct"])
            )
            result["locked_holdout"] = record(
                0,
                winner_candidates,
                holdout,
                config,
                lattice["coordinates"][winner_global],
            )
            result["locked_holdout"]["passed"] = holdout_pass
            whole = simulate(lifecycles, winner_candidates, config)
            result["winner_whole_path"] = record(
                0,
                winner_candidates,
                whole,
                config,
                lattice["coordinates"][winner_global],
            )
            final_pass = bool(
                holdout_pass
                and positive(whole)[0]
                and whole["stressed_net"][0]
                >= float(observed_anchor["stressed_net_usd"])
                * float(
                    config["gates"][
                        "final_minimum_stressed_retention_vs_exact_v8"
                    ]
                )
                and whole["drawdown_pct"][0]
                <= float(observed_anchor["raw_closed_balance_drawdown_pct"])
                - float(
                    config["gates"][
                        "final_minimum_drawdown_improvement_vs_exact_v8_points"
                    ]
                )
            )
            if final_pass:
                result["stage_d_roles"].append(
                    {
                        "development_rank": winner_local + 1,
                        "lattice_index": int(winner_global),
                        "parameters": {
                            "weights": [
                                float(value)
                                for value in lattice["weights"][winner_global]
                            ],
                            "base_position_risk_fraction": float(
                                config["base_position_risk_fraction"]
                            ),
                            "aggregate_risk_fraction": float(
                                lattice["aggregate_risk"][winner_global]
                            ),
                            "static_seed_index": int(
                                lattice["seed_index"][winner_global]
                            ),
                            "trigger_drawdown_fraction": float(
                                lattice["trigger_drawdown"][winner_global]
                            ),
                            "future_birth_multiplier": float(
                                lattice["state_multiplier"][winner_global]
                            ),
                            "release_hysteresis_fraction": float(
                                lattice["release_hysteresis"][winner_global]
                            ),
                            "minimum_subsequent_accepted_closes": int(
                                lattice["minimum_hold_closes"][winner_global]
                            ),
                        },
                    }
                )
                result["status"] = (
                    "VALID_PROXY_COMPLETE_STAGE_C_SURVIVOR_STAGE_D_REQUIRED_NO_MT5"
                )
            elif not holdout_pass:
                result["status"] = (
                    "VALID_PROXY_COMPLETE_STAGE_C_LOCKED_HOLDOUT_NONCONFIRMATION_"
                    "NO_STAGE_D_ROLE_STAGE_D_EMPTY_CLOSURE_REQUIRED_NO_MT5"
                )
            else:
                result["status"] = (
                    "VALID_PROXY_COMPLETE_STAGE_C_WHOLE_PATH_GATE_NONCONFIRMATION_"
                    "NO_STAGE_D_ROLE_STAGE_D_EMPTY_CLOSURE_REQUIRED_NO_MT5"
                )

    parity = config["correction_parity"]
    tolerance = float(parity["numeric_tolerance"])

    def require_triplet(
        label: str, observed: dict[str, Any], expected: list[float]
    ) -> None:
        values = [
            float(observed["actual_net_usd"]),
            float(observed["stressed_net_usd"]),
            float(observed["raw_closed_balance_drawdown_pct"]),
        ]
        if any(abs(value - float(target)) > tolerance for value, target in zip(values, expected)):
            raise RuntimeError(f"V1 correction parity failed for {label}")

    for label, payload in (("staged V1", v1_result), ("V2 replay", result)):
        if int(payload["lattice"]["primary_eligible"]) != int(
            parity["primary_eligible"]
        ):
            raise RuntimeError(f"{label} primary count parity failed")
        if int(payload["lattice"]["fallback_eligible"]) != int(
            parity["fallback_eligible"]
        ):
            raise RuntimeError(f"{label} fallback count parity failed")
        if int(payload["development_plateau_population"]) != int(
            parity["development_plateau_population"]
        ):
            raise RuntimeError(f"{label} plateau parity failed")
        if int(payload["winner"]["lattice_index"]) != int(
            parity["selected_lattice_index"]
        ):
            raise RuntimeError(f"{label} selected index parity failed")
        require_triplet(
            f"{label} development",
            payload["development_centers"][0],
            parity["development_actual_stressed_dd"],
        )
        require_triplet(
            f"{label} validation",
            payload["validation"][0],
            parity["validation_actual_stressed_dd"],
        )
        require_triplet(
            f"{label} holdout",
            payload["locked_holdout"],
            parity["holdout_actual_stressed_dd"],
        )
        require_triplet(
            f"{label} whole",
            payload["winner_whole_path"],
            parity["whole_actual_stressed_dd"],
        )
    if result["status"] != str(parity["expected_status"]):
        raise RuntimeError("V2 corrected final status mismatch")
    if len(result["stage_d_roles"]) != int(parity["expected_stage_d_role_count"]):
        raise RuntimeError("V2 corrected Stage-D role count mismatch")

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
                "mt5_shortlist_count": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
