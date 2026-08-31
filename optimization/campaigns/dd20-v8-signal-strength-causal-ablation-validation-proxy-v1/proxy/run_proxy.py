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
    for role in ("lifecycle", "candidate", "stage_b_raw", "stage_b_durable"):
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


def verify_stage_b_inputs(
    config: dict[str, Any], paths: dict[str, Path]
) -> dict[str, Any]:
    payloads: dict[str, Any] = {}
    for role in ("stage_b_raw", "stage_b_durable"):
        declared = config["inputs"][role]
        payload = json.loads(paths[role].read_text(encoding="utf-8"))
        if payload.get("schema") != str(declared["schema"]):
            raise RuntimeError(f"{role} schema mismatch")
        if payload.get("status") != str(declared["status"]):
            raise RuntimeError(f"{role} status mismatch")
        payloads[role] = payload

    expected = config["strength_lattice"]["centers"]
    raw_centers = payloads["stage_b_raw"].get("stage_c_strength_centers", [])
    durable_centers = payloads["stage_b_durable"].get("stage_c_strength_centers", [])
    if len(raw_centers) != len(expected) or len(durable_centers) != len(expected):
        raise RuntimeError("Stage-B center count mismatch")
    tolerance = 1.0e-9
    for index, center in enumerate(expected):
        expected_quantiles = np.asarray(center["quantiles"], dtype=np.float64)
        expected_thresholds = np.asarray(
            center["thresholds"], dtype=np.float64
        )
        for observed in (raw_centers[index], durable_centers[index]):
            if int(observed["development_rank"]) != int(center["rank"]):
                raise RuntimeError("Stage-B center rank mismatch")
            if not np.allclose(
                np.asarray(observed["quantile_coordinates"], dtype=np.float64),
                expected_quantiles,
                atol=tolerance,
                rtol=0.0,
            ):
                raise RuntimeError("Stage-B center quantile mismatch")
            if not np.allclose(
                np.asarray(observed["normalized_thresholds"], dtype=np.float64),
                expected_thresholds,
                atol=tolerance,
                rtol=0.0,
            ):
                raise RuntimeError("Stage-B center threshold mismatch")
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


def build_role_map(config: dict[str, Any]) -> dict[str, Any]:
    lattice_config = config["strength_lattice"]
    component_count = len(config["components"])
    native = float(lattice_config["native_normalized_threshold"])
    ablation_components = [int(value) for value in lattice_config["ablation_components"]]
    if ablation_components != list(range(component_count)):
        raise RuntimeError("ablation component order mismatch")

    roles: list[dict[str, Any]] = []
    center_role_indices: list[int] = []
    ablation_role_indices: list[list[int]] = []
    seen: set[tuple[float, ...]] = set()
    for center_index, center in enumerate(lattice_config["centers"]):
        thresholds = tuple(float(value) for value in center["thresholds"])
        quantiles = tuple(float(value) for value in center["quantiles"])
        if len(thresholds) != component_count or len(quantiles) != component_count:
            raise RuntimeError("Stage-C center component count mismatch")
        if any(value <= native for value in thresholds):
            raise RuntimeError("Stage-C center must restrict every component")
        center_role_indices.append(len(roles))
        roles.append(
            {
                "center_rank": center_index + 1,
                "role_kind": "CENTER",
                "ablation_component_index": None,
                "quantiles": quantiles,
                "thresholds": thresholds,
            }
        )
        local_ablation_indices: list[int] = []
        for axis in ablation_components:
            ablated_thresholds = list(thresholds)
            ablated_quantiles = list(quantiles)
            ablated_thresholds[axis] = native
            ablated_quantiles[axis] = 0.0
            local_ablation_indices.append(len(roles))
            roles.append(
                {
                    "center_rank": center_index + 1,
                    "role_kind": "NATIVE_GATE_ABLATION",
                    "ablation_component_index": axis,
                    "quantiles": tuple(ablated_quantiles),
                    "thresholds": tuple(ablated_thresholds),
                }
            )
        ablation_role_indices.append(local_ablation_indices)
    if len(roles) != int(lattice_config["total_roles"]):
        raise RuntimeError("Stage-C role count mismatch")
    for role in roles:
        thresholds = tuple(role["thresholds"])
        if thresholds in seen:
            raise RuntimeError("duplicate Stage-C threshold role")
        seen.add(thresholds)
    if len(seen) != int(lattice_config["expected_unique_threshold_roles"]):
        raise RuntimeError("Stage-C unique threshold count mismatch")
    values = np.asarray([role["thresholds"] for role in roles], dtype=np.float64)
    quantiles = np.asarray([role["quantiles"] for role in roles], dtype=np.float64)
    if np.any(values < native - float(lattice_config["strength_tolerance"])):
        raise RuntimeError("Stage-C role loosened below native gate")
    return {
        "roles": roles,
        "values": values,
        "quantiles": quantiles,
        "center_role_indices": center_role_indices,
        "ablation_role_indices": ablation_role_indices,
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


def assert_close(
    observed: float, expected: float, tolerance: float, label: str
) -> None:
    if abs(observed - expected) > tolerance:
        raise RuntimeError(
            f"{label} mismatch: observed={observed!r}, expected={expected!r}"
        )


def reproduce_whole_anchor(
    lifecycles: list[Lifecycle], config: dict[str, Any]
) -> dict[str, Any]:
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
    assert_close(
        observed["actual_net_usd"],
        float(anchor["actual_net_usd"]),
        float(anchor["net_tolerance_usd"]),
        "exact anchor actual net",
    )
    assert_close(
        observed["stressed_net_usd"],
        float(anchor["stressed_net_usd"]),
        float(anchor["net_tolerance_usd"]),
        "exact anchor stressed net",
    )
    assert_close(
        observed["raw_closed_balance_drawdown_pct"],
        float(anchor["closed_balance_drawdown_pct"]),
        float(anchor["drawdown_tolerance_points"]),
        "exact anchor drawdown",
    )
    return observed


def reproduce_stage_b_centers(
    lifecycles: list[Lifecycle], role_map: dict[str, Any], config: dict[str, Any]
) -> list[dict[str, Any]]:
    center_indices = role_map["center_role_indices"]
    thresholds = role_map["values"][center_indices]
    quantiles = role_map["quantiles"][center_indices]
    start, end = period_bounds(config, "development")
    metrics = simulate(lifecycles, thresholds, config, start, end)
    tolerance = 1.0e-6
    reproduced: list[dict[str, Any]] = []
    for local_index, declared in enumerate(config["strength_lattice"]["centers"]):
        item = record(local_index, thresholds, metrics, config, quantiles)
        assert_close(
            item["actual_net_usd"],
            float(declared["development_actual_net_usd"]),
            tolerance,
            f"Stage-B center {local_index + 1} development actual net",
        )
        assert_close(
            item["stressed_net_usd"],
            float(declared["development_stressed_net_usd"]),
            tolerance,
            f"Stage-B center {local_index + 1} development stressed net",
        )
        assert_close(
            item["raw_closed_balance_drawdown_pct"],
            float(declared["development_drawdown_pct"]),
            tolerance,
            f"Stage-B center {local_index + 1} development drawdown",
        )
        assert_close(
            item["minimum_balance_usd"],
            float(declared["development_minimum_balance_usd"]),
            tolerance,
            f"Stage-B center {local_index + 1} development minimum balance",
        )
        item["stage_b_rank"] = int(declared["rank"])
        item["stage_b_lattice_index"] = int(declared["stage_b_lattice_index"])
        reproduced.append(item)
    return reproduced


def reproduce_validation_anchor(
    lifecycles: list[Lifecycle], config: dict[str, Any]
) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, Any]]:
    thresholds = np.asarray(
        [config["anchor_reproduction"]["normalized_thresholds"]], dtype=np.float64
    )
    start, end = period_bounds(config, "validation")
    metrics = simulate(lifecycles, thresholds, config, start, end)
    observed = record(0, thresholds, metrics, config)
    declared = config["validation_anchor"]
    tolerance = float(declared["tolerance"])
    for observed_key, declared_key, label in (
        ("actual_net_usd", "actual_net_usd", "validation anchor actual net"),
        ("stressed_net_usd", "stressed_net_usd", "validation anchor stressed net"),
        (
            "raw_closed_balance_drawdown_pct",
            "closed_balance_drawdown_pct",
            "validation anchor drawdown",
        ),
        ("minimum_balance_usd", "minimum_balance_usd", "validation anchor minimum"),
    ):
        assert_close(
            float(observed[observed_key]),
            float(declared[declared_key]),
            tolerance,
            label,
        )
    return thresholds, metrics, observed


def structural_precheck() -> dict[str, Any]:
    config = load_config()
    paths = verify_authority_and_inputs(config)
    stage_b_payloads = verify_stage_b_inputs(config, paths)
    lifecycles, populations, diagnostics = verify_and_load_data(config, paths)
    role_map = build_role_map(config)
    observed = reproduce_whole_anchor(lifecycles, config)
    reproduced_centers = reproduce_stage_b_centers(lifecycles, role_map, config)
    return {
        "matched_lifecycles": len(lifecycles),
        "input_diagnostics": diagnostics,
        "development_signal_passed_populations": [len(values) for values in populations],
        "center_count": len(role_map["center_role_indices"]),
        "total_roles": len(role_map["roles"]),
        "unique_threshold_roles": len(
            {tuple(float(value) for value in row) for row in role_map["values"]}
        ),
        "center_role_indices": role_map["center_role_indices"],
        "ablation_role_indices": role_map["ablation_role_indices"],
        "all_thresholds_at_or_above_native": bool(np.all(role_map["values"] >= 1.0)),
        "stage_b_raw_status": stage_b_payloads["stage_b_raw"]["status"],
        "stage_b_durable_status": stage_b_payloads["stage_b_durable"]["status"],
        "exact_v8_whole": observed,
        "reproduced_stage_b_development_centers": reproduced_centers,
        "validation_opened": False,
        "locked_holdout_opened": False,
    }


def main() -> None:
    started = time.perf_counter()
    config = load_config()
    paths = verify_authority_and_inputs(config)
    stage_b_payloads = verify_stage_b_inputs(config, paths)
    lifecycles, populations, input_diagnostics = verify_and_load_data(config, paths)
    role_map = build_role_map(config)
    observed_anchor = reproduce_whole_anchor(lifecycles, config)
    reproduced_centers = reproduce_stage_b_centers(lifecycles, role_map, config)
    _, _, observed_validation_anchor = reproduce_validation_anchor(lifecycles, config)

    validation_start, validation_end = period_bounds(config, "validation")
    validation_metrics = simulate(
        lifecycles,
        role_map["values"],
        config,
        validation_start,
        validation_end,
    )
    gates = config["validation_gates"]
    dominance_tolerance = float(gates["dominance_tolerance"])
    validation_anchor_stressed = float(observed_validation_anchor["stressed_net_usd"])
    center_results: list[dict[str, Any]] = []
    stage_d_roles: list[dict[str, Any]] = []
    components = config["components"]

    for center_offset, center_index in enumerate(role_map["center_role_indices"]):
        declared_center = config["strength_lattice"]["centers"][center_offset]
        center_record = record(
            center_index,
            role_map["values"],
            validation_metrics,
            config,
            role_map["quantiles"],
        )
        positive_actual = center_record["actual_net_usd"] > 0.0
        positive_stressed = center_record["stressed_net_usd"] > 0.0
        positive_minimum = center_record["minimum_balance_usd"] > 0.0
        drawdown_passed = (
            center_record["raw_closed_balance_drawdown_pct"]
            <= float(gates["maximum_drawdown_pct"])
        )
        stressed_retention = (
            center_record["stressed_net_usd"] / validation_anchor_stressed
        )
        retention_passed = stressed_retention >= float(
            gates["minimum_stressed_retention"]
        )
        economic_gate_passed = all(
            (
                positive_actual,
                positive_stressed,
                positive_minimum,
                drawdown_passed,
                retention_passed,
            )
        )

        ablation_results: list[dict[str, Any]] = []
        dominating_ablation_components: list[str] = []
        for ablation_index in role_map["ablation_role_indices"][center_offset]:
            role = role_map["roles"][ablation_index]
            component_index = int(role["ablation_component_index"])
            ablation_record = record(
                ablation_index,
                role_map["values"],
                validation_metrics,
                config,
                role_map["quantiles"],
            )
            stressed_not_worse = (
                ablation_record["stressed_net_usd"]
                >= center_record["stressed_net_usd"] - dominance_tolerance
            )
            drawdown_not_worse = (
                ablation_record["raw_closed_balance_drawdown_pct"]
                <= center_record["raw_closed_balance_drawdown_pct"]
                + dominance_tolerance
            )
            strict_improvement = (
                ablation_record["stressed_net_usd"]
                > center_record["stressed_net_usd"] + dominance_tolerance
                or ablation_record["raw_closed_balance_drawdown_pct"]
                < center_record["raw_closed_balance_drawdown_pct"]
                - dominance_tolerance
            )
            dominates_center = (
                stressed_not_worse and drawdown_not_worse and strict_improvement
            )
            component_short = str(components[component_index]["short"])
            if dominates_center:
                dominating_ablation_components.append(component_short)
            ablation_results.append(
                {
                    "role_index": ablation_index,
                    "restored_component_index": component_index,
                    "restored_component_short": component_short,
                    "restored_to_exact_v8_native_gate": True,
                    "stressed_not_worse_than_center": stressed_not_worse,
                    "drawdown_not_worse_than_center": drawdown_not_worse,
                    "strict_improvement_on_at_least_one_axis": strict_improvement,
                    "dominates_center": dominates_center,
                    "stressed_net_delta_vs_center_usd": (
                        ablation_record["stressed_net_usd"]
                        - center_record["stressed_net_usd"]
                    ),
                    "drawdown_delta_vs_center_points": (
                        ablation_record["raw_closed_balance_drawdown_pct"]
                        - center_record["raw_closed_balance_drawdown_pct"]
                    ),
                    "validation": ablation_record,
                }
            )

        causal_nondominance_passed = not dominating_ablation_components
        stage_c_passed = economic_gate_passed and causal_nondominance_passed
        center_result = {
            "stage_b_rank": int(declared_center["rank"]),
            "stage_b_lattice_index": int(declared_center["stage_b_lattice_index"]),
            "center_role_index": center_index,
            "validation": center_record,
            "validation_stressed_retention_vs_exact_v8": stressed_retention,
            "economic_gate": {
                "positive_actual": positive_actual,
                "positive_stressed": positive_stressed,
                "positive_minimum_balance": positive_minimum,
                "drawdown_at_or_below_maximum": drawdown_passed,
                "stressed_retention_at_or_above_minimum": retention_passed,
                "passed": economic_gate_passed,
            },
            "one_component_native_gate_ablations": ablation_results,
            "dominating_ablation_components": dominating_ablation_components,
            "causal_nondominance_passed": causal_nondominance_passed,
            "stage_c_passed": stage_c_passed,
        }
        center_results.append(center_result)
        if stage_c_passed:
            stage_d_roles.append(
                {
                    "stage_b_rank": int(declared_center["rank"]),
                    "stage_b_lattice_index": int(
                        declared_center["stage_b_lattice_index"]
                    ),
                    "normalized_thresholds": center_record["normalized_thresholds"],
                    "raw_feature_thresholds": center_record["raw_feature_thresholds"],
                    "quantile_coordinates": center_record["quantile_coordinates"],
                    "weights": center_record["weights"],
                    "base_position_risk_fraction": center_record[
                        "base_position_risk_fraction"
                    ],
                    "aggregate_risk_fraction": center_record[
                        "aggregate_risk_fraction"
                    ],
                    "validation": center_record,
                }
            )

    maximum_stage_d = int(config["stage_succession"]["maximum_stage_d_centers"])
    if len(stage_d_roles) > maximum_stage_d:
        raise RuntimeError("Stage-C passed more centers than Stage-D authority permits")
    status = (
        "VALID_PROXY_COMPLETE_STAGE_C_VALIDATION_CENTERS_STAGE_D_REQUIRED_NO_MT5"
        if stage_d_roles
        else "VALID_PROXY_COMPLETE_STAGE_C_NO_VALIDATION_CENTER_STAGE_D_EMPTY_REQUIRED_NO_MT5"
    )

    result: dict[str, Any] = {
        "schema": "zeta-next-dd20-v8-signal-strength-causal-ablation-validation-proxy-result-v1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "campaign": "dd20-v8-signal-strength-causal-ablation-validation-proxy-v1",
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
            "thresholds_and_ablations_can_only_suppress_exact_v8_births": True,
            "validation_outcomes_used_for_retuning": False,
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
            "stage_b_raw": {
                "path": str(config["inputs"]["root"]) + "/" + str(config["inputs"]["stage_b_raw"]["name"]),
                "bytes": paths["stage_b_raw"].stat().st_size,
                "sha256": sha256(paths["stage_b_raw"]),
                "status": stage_b_payloads["stage_b_raw"]["status"],
            },
            "stage_b_durable": {
                "path": str(config["inputs"]["root"]) + "/" + str(config["inputs"]["stage_b_durable"]["name"]),
                "bytes": paths["stage_b_durable"].stat().st_size,
                "sha256": sha256(paths["stage_b_durable"]),
                "status": stage_b_payloads["stage_b_durable"]["status"],
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
        "immutable_center_and_role_map": {
            "development_signal_passed_populations": [len(values) for values in populations],
            "center_count": len(role_map["center_role_indices"]),
            "roles_per_center": int(config["strength_lattice"]["roles_per_center"]),
            "total_roles": len(role_map["roles"]),
            "unique_threshold_roles": len(
                {tuple(float(value) for value in row) for row in role_map["values"]}
            ),
            "center_role_indices": role_map["center_role_indices"],
            "ablation_role_indices": role_map["ablation_role_indices"],
            "all_roles_at_or_above_exact_v8_native_gates": bool(
                np.all(role_map["values"] >= 1.0)
            ),
            "validation_threshold_retuning": False,
        },
        "exact_anchor_whole_path": observed_anchor,
        "reproduced_stage_b_development_centers": reproduced_centers,
        "exact_v8_validation_anchor": observed_validation_anchor,
        "validation_period": config["periods"]["validation"],
        "validation_gates": gates,
        "center_results": center_results,
        "stage_d_roles": stage_d_roles,
        "validation_opened": True,
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
            "Stage C judges immutable Stage-B centers on January-May 2026 and does not retune them from validation outcomes.",
            "Locked June-July 2026 remains unopened for the independent Stage-D stability decision.",
        ],
        "status": status,
    }
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
                "stage_d_center_count": len(result["stage_d_roles"]),
                "mt5_paths": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
