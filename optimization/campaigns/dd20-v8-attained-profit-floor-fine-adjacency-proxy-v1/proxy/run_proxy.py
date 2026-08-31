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
    volume_lots: float
    planned_risk_usd: float
    entry_feature: float
    last_mark_profit_usd: float
    last_mark_r: float
    peak_mark_r: float
    peak_time: datetime
    trough_mark_r: float
    trough_time: datetime
    mark_samples: int
    actual_net_usd: float
    stressed_net_usd: float
    exit_class: str


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


def verify_authority_and_inputs(config: dict[str, Any]) -> dict[str, Path]:
    authority = config["declaration_authority"]
    declaration = REPOSITORY_ROOT / str(authority["path"])
    if declaration.stat().st_size != int(authority["bytes"]):
        raise RuntimeError("declaration authority byte count mismatch")
    if sha256(declaration) != str(authority["sha256"]):
        raise RuntimeError("declaration authority hash mismatch")

    input_root = REPOSITORY_ROOT / str(config["inputs"]["root"])
    paths: dict[str, Path] = {"declaration": declaration}
    for role in ("lifecycle", "candidate", "stage_a_raw", "stage_a_durable"):
        declared = config["inputs"][role]
        path = input_root / str(declared["name"])
        if path.stat().st_size != int(declared["bytes"]):
            raise RuntimeError(f"staged {role} byte count mismatch")
        if sha256(path) != str(declared["sha256"]):
            raise RuntimeError(f"staged {role} hash mismatch")
        paths[role] = path
    for index, declared in enumerate(config["inputs"]["source_files"]):
        path = input_root / str(declared["name"])
        if path.stat().st_size != int(declared["bytes"]):
            raise RuntimeError("staged source byte count mismatch")
        if sha256(path) != str(declared["sha256"]):
            raise RuntimeError("staged source hash mismatch")
        paths[f"source_{index}"] = path
    return paths


def verify_stage_a_authority(
    config: dict[str, Any], paths: dict[str, Path]
) -> dict[str, Any]:
    raw = json.loads(paths["stage_a_raw"].read_text(encoding="utf-8"))
    durable = json.loads(paths["stage_a_durable"].read_text(encoding="utf-8"))
    raw_declared = config["inputs"]["stage_a_raw"]
    durable_declared = config["inputs"]["stage_a_durable"]
    if raw.get("schema") != raw_declared["schema"]:
        raise RuntimeError("Stage-A raw schema mismatch")
    if raw.get("status") != raw_declared["status"]:
        raise RuntimeError("Stage-A raw status mismatch")
    if durable.get("schema") != durable_declared["schema"]:
        raise RuntimeError("Stage-A durable schema mismatch")
    if durable.get("status") != durable_declared["status"]:
        raise RuntimeError("Stage-A durable status mismatch")
    coarse = raw.get("coarse_map", {})
    if int(coarse.get("common_positive_four_half_year_roles", -1)) != 0:
        raise RuntimeError("Stage-A common-positive count changed")
    if int(coarse.get("primary_eligible", -1)) != 0:
        raise RuntimeError("Stage-A primary count changed")
    if int(coarse.get("fallback_eligible", -1)) != 0:
        raise RuntimeError("Stage-A fallback count changed")
    if coarse.get("selection_kind") != "DECLARED_NEAR_MISS":
        raise RuntimeError("Stage-A selection kind changed")

    raw_centers = raw.get("stage_b_centers", [])
    durable_centers = durable.get("stage_b_near_miss_centers", [])
    expected = config["stage_a_centers"]
    if len(raw_centers) != len(expected) or len(durable_centers) != len(expected):
        raise RuntimeError("Stage-A center count mismatch")
    tolerance = 1.0e-9
    for index, frozen in enumerate(expected):
        raw_center = raw_centers[index]
        durable_center = durable_centers[index]
        integer_fields = ("rank", "stage_a_role_index")
        if int(frozen[integer_fields[0]]) != int(raw_center["development_rank"]):
            raise RuntimeError("Stage-A raw center rank mismatch")
        if int(frozen[integer_fields[1]]) != int(raw_center["role_index"]):
            raise RuntimeError("Stage-A raw center role mismatch")
        comparisons = (
            ("activation_r", "activation_r"),
            ("floor_r", "floor_r"),
            ("normalized_gate_deficit", "normalized_gate_deficit"),
            ("development_lower_actual_net_usd", "lower_actual_net_usd"),
            ("development_lower_stressed_net_usd", "lower_stressed_net_usd"),
            (
                "development_actual_drawdown_pct",
                "adverse_timing_actual_closed_balance_drawdown_pct",
            ),
        )
        for frozen_key, raw_key in comparisons:
            if abs(float(frozen[frozen_key]) - float(raw_center[raw_key])) > tolerance:
                raise RuntimeError(f"Stage-A raw center {frozen_key} mismatch")
        if int(durable_center["development_rank"]) != int(frozen["rank"]):
            raise RuntimeError("Stage-A durable center rank mismatch")
        if int(durable_center["role_index"]) != int(frozen["stage_a_role_index"]):
            raise RuntimeError("Stage-A durable center role mismatch")
        for key in ("activation_r", "floor_r", "normalized_gate_deficit"):
            if abs(float(durable_center[key]) - float(frozen[key])) > tolerance:
                raise RuntimeError(f"Stage-A durable center {key} mismatch")
    return {
        "raw_schema": raw["schema"],
        "raw_status": raw["status"],
        "durable_schema": durable["schema"],
        "durable_status": durable["status"],
        "center_count": len(expected),
        "center_role_indices": [int(item["stage_a_role_index"]) for item in expected],
        "raw_and_durable_centers_agree": True,
    }


def verify_and_load_data(
    config: dict[str, Any], paths: dict[str, Path]
) -> tuple[list[Lifecycle], dict[str, Any]]:
    components = config["components"]
    component_ids = [str(item["id"]) for item in components]
    component_index = {value: index for index, value in enumerate(component_ids)}
    lifecycle_declared = config["inputs"]["lifecycle"]
    candidate_declared = config["inputs"]["candidate"]

    births: dict[str, dict[str, Any]] = {}
    closes: dict[str, dict[str, Any]] = {}
    lifecycle_rows = 0
    with paths["lifecycle"].open("r", encoding="utf-8-sig", newline="") as handle:
        for order, row in enumerate(csv.DictReader(handle)):
            lifecycle_rows += 1
            event = row["event"]
            if event not in {"BIRTH", "CLOSE"}:
                continue
            component_id = row["component_id"]
            if component_id not in component_index:
                raise RuntimeError("undeclared component in lifecycle input")
            identifier = row["position_identifier"]
            target = births if event == "BIRTH" else closes
            if identifier in target:
                raise RuntimeError(f"duplicate {event} identifier")
            target[identifier] = {
                "order": order,
                "component": component_index[component_id],
                "time": parse_time(row["server_time"]),
                "volume": float(row["volume"]),
                "planned_risk": float(row["planned_risk_usd"]),
                "entry_feature": float(row["entry_feature"]),
                "last_mark_profit": float(row["last_mark_profit_usd"]),
                "last_mark_r": float(row["last_mark_r"]),
                "peak_mark_r": float(row["peak_mark_r"]),
                "peak_time": parse_time(row["peak_time_server"]),
                "trough_mark_r": float(row["trough_mark_r"]),
                "trough_time": parse_time(row["trough_time_server"]),
                "mark_samples": int(row["mark_samples"]),
                "actual": float(row["actual_net_usd"]),
                "stressed": float(row["stressed_net_usd"]),
                "exit_class": row["exit_class"],
                "partial": int(row["partial_observation"]),
            }
    if lifecycle_rows != int(lifecycle_declared["rows"]):
        raise RuntimeError("staged lifecycle row count mismatch")
    if set(births) != set(closes):
        raise RuntimeError("birth/close identity mismatch")
    if len(births) != int(lifecycle_declared["matched_lifecycles"]):
        raise RuntimeError("matched lifecycle count mismatch")

    open_contexts: dict[str, dict[str, float]] = {}
    candidate_rows = 0
    signal_passed_rows = 0
    with paths["candidate"].open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            candidate_rows += 1
            component_id = row["component_id"]
            if component_id not in component_index:
                raise RuntimeError("undeclared component in candidate input")
            signal_passed = row["signal_known"] == "1" and row["signal_passed"] == "1"
            if signal_passed:
                signal_passed_rows += 1
            if row["result"] != "POSITION_OPEN":
                continue
            if not signal_passed:
                raise RuntimeError("POSITION_OPEN row is not signal passed")
            key = f"{component_id}|{row['server_time']}"
            if key in open_contexts:
                raise RuntimeError("duplicate component/time POSITION_OPEN key")
            open_contexts[key] = {
                "volume": float(row["volume"]),
                "planned_risk": float(row["planned_risk_usd"]),
                "feature": float(row["feature"]),
            }
    if candidate_rows != int(candidate_declared["rows"]):
        raise RuntimeError("candidate row count mismatch")
    if signal_passed_rows != int(candidate_declared["signal_passed_rows"]):
        raise RuntimeError("signal-passed row count mismatch")
    if len(open_contexts) != int(candidate_declared["position_open_rows"]):
        raise RuntimeError("POSITION_OPEN row count mismatch")
    if len(open_contexts) != int(candidate_declared["unique_component_time_open_keys"]):
        raise RuntimeError("POSITION_OPEN key count mismatch")

    tolerance = float(config["numeric_tolerance"])
    lifecycles: list[Lifecycle] = []
    matched_open_keys: set[str] = set()
    birth_counts = np.zeros(len(components), dtype=np.int32)
    exit_classes: dict[str, int] = {}
    mark_samples_total = 0
    for identifier, birth in births.items():
        close = closes[identifier]
        if birth["component"] != close["component"]:
            raise RuntimeError("component changed within lifecycle")
        if birth["partial"] != 0 or close["partial"] != 0:
            raise RuntimeError("partial lifecycle in exact input")
        if int(close["order"]) <= int(birth["order"]):
            raise RuntimeError("lifecycle close row does not follow birth row")
        if birth["volume"] <= 0.0 or birth["planned_risk"] <= 0.0:
            raise RuntimeError("nonpositive source volume or planned risk")
        component = int(birth["component"])
        key = (
            f"{component_ids[component]}|"
            f"{birth['time'].strftime(TIME_FORMAT)}"
        )
        if key not in open_contexts:
            raise RuntimeError("lifecycle birth has no POSITION_OPEN context")
        if key in matched_open_keys:
            raise RuntimeError("multiple lifecycle births share one POSITION_OPEN context")
        matched_open_keys.add(key)
        context = open_contexts[key]
        if abs(birth["volume"] - context["volume"]) > 1.0e-9:
            raise RuntimeError("lifecycle/candidate volume mismatch")
        if abs(birth["planned_risk"] - context["planned_risk"]) > 0.011:
            raise RuntimeError("lifecycle/candidate planned risk mismatch")
        if abs(birth["entry_feature"] - context["feature"]) > 1.0e-10:
            raise RuntimeError("lifecycle/candidate feature mismatch")
        if close["time"] < birth["time"]:
            raise RuntimeError("close precedes birth")
        if close["peak_time"] < birth["time"] or close["peak_time"] > close["time"]:
            raise RuntimeError("peak timestamp outside lifecycle")
        if close["trough_time"] < birth["time"] or close["trough_time"] > close["time"]:
            raise RuntimeError("trough timestamp outside lifecycle")
        if close["mark_samples"] <= 0:
            raise RuntimeError("nonpositive mark sample count")
        expected_last_r = close["last_mark_profit"] / birth["planned_risk"]
        if abs(expected_last_r - close["last_mark_r"]) > max(tolerance, 1.0e-10):
            raise RuntimeError("last mark R does not match planned risk")
        if close["peak_mark_r"] + tolerance < close["last_mark_r"]:
            raise RuntimeError("peak mark below last mark")
        if close["trough_mark_r"] - tolerance > close["last_mark_r"]:
            raise RuntimeError("trough mark above last mark")
        if close["exit_class"] not in {"NATIVE", "STOP"}:
            raise RuntimeError("unexpected source exit class")
        birth_counts[component] += 1
        mark_samples_total += close["mark_samples"]
        exit_classes[close["exit_class"]] = exit_classes.get(close["exit_class"], 0) + 1
        lifecycles.append(
            Lifecycle(
                identifier=identifier,
                component_index=component,
                birth_time=birth["time"],
                close_time=close["time"],
                birth_order=int(birth["order"]),
                close_order=int(close["order"]),
                volume_lots=float(birth["volume"]),
                planned_risk_usd=float(birth["planned_risk"]),
                entry_feature=float(birth["entry_feature"]),
                last_mark_profit_usd=float(close["last_mark_profit"]),
                last_mark_r=float(close["last_mark_r"]),
                peak_mark_r=float(close["peak_mark_r"]),
                peak_time=close["peak_time"],
                trough_mark_r=float(close["trough_mark_r"]),
                trough_time=close["trough_time"],
                mark_samples=int(close["mark_samples"]),
                actual_net_usd=float(close["actual"]),
                stressed_net_usd=float(close["stressed"]),
                exit_class=str(close["exit_class"]),
            )
        )
    if matched_open_keys != set(open_contexts):
        raise RuntimeError("lifecycle/POSITION_OPEN context set mismatch")
    expected_birth_counts = np.asarray(
        [int(item["source_births"]) for item in components], dtype=np.int32
    )
    if not np.array_equal(birth_counts, expected_birth_counts):
        raise RuntimeError("component birth count mismatch")
    if mark_samples_total != int(lifecycle_declared["mark_samples"]):
        raise RuntimeError("mark sample total mismatch")
    actual = sum(item.actual_net_usd for item in lifecycles)
    stressed = sum(item.stressed_net_usd for item in lifecycles)
    if abs(actual - float(lifecycle_declared["actual_net_usd"])) > 1.0e-7:
        raise RuntimeError("source actual net mismatch")
    if abs(stressed - float(lifecycle_declared["stressed_net_usd"])) > 1.0e-7:
        raise RuntimeError("source stressed net mismatch")
    lifecycles.sort(key=lambda item: item.birth_order)
    diagnostics = {
        "candidate_rows": candidate_rows,
        "signal_passed_rows": signal_passed_rows,
        "position_open_rows": len(open_contexts),
        "component_birth_counts": birth_counts.tolist(),
        "exit_classes": exit_classes,
        "mark_samples_total": mark_samples_total,
        "minimum_mark_samples": min(item.mark_samples for item in lifecycles),
        "median_mark_samples": int(
            np.median(np.asarray([item.mark_samples for item in lifecycles]))
        ),
    }
    return lifecycles, diagnostics


def build_role_map(config: dict[str, Any]) -> dict[str, Any]:
    fine = config["fine_map"]
    separation = float(fine["minimum_activation_floor_separation_r"])
    tolerance = float(config["numeric_tolerance"])
    roles: list[dict[str, Any]] = [
        {"index": 0, "kind": "EXACT_V8_NEUTRAL", "activation_r": None, "floor_r": None}
    ]
    pair_to_index: dict[tuple[float, float], int] = {}
    provenance_to_index: dict[tuple[int, int, int], int] = {}
    center_counts: list[int] = []
    for center in fine["centers"]:
        center_rank = int(center["rank"])
        activations = [float(value) for value in center["activations_r"]]
        floors = [float(value) for value in center["floors_r"]]
        count = 0
        for activation_index, activation in enumerate(activations):
            for floor_index, floor in enumerate(floors):
                if floor >= activation - tolerance:
                    continue
                if activation - floor < separation - tolerance:
                    continue
                pair = (activation, floor)
                if pair in pair_to_index:
                    raise RuntimeError("unexpected cross-center fine role duplicate")
                index = len(roles)
                roles.append(
                    {
                        "index": index,
                        "kind": "ALL_FIVE_ATTAINED_PROFIT_FLOOR",
                        "activation_r": activation,
                        "floor_r": floor,
                        "center_ranks": [center_rank],
                        "coordinate_provenance": [
                            {
                                "center_rank": center_rank,
                                "activation_coordinate_index": activation_index,
                                "floor_coordinate_index": floor_index,
                            }
                        ],
                    }
                )
                pair_to_index[pair] = index
                provenance_to_index[
                    (center_rank, activation_index, floor_index)
                ] = index
                count += 1
        center_counts.append(count)
    if center_counts != [int(value) for value in fine["expected_center_role_counts"]]:
        raise RuntimeError("fine center role counts mismatch")
    if len(roles) - 1 != int(fine["expected_unique_nonneutral_roles"]):
        raise RuntimeError("fine nonneutral role count mismatch")
    if len(roles) != int(fine["expected_internal_roles_with_neutral_control"]):
        raise RuntimeError("fine internal role count mismatch")

    adjacency: list[set[int]] = [set() for _ in roles]
    edge_axes: list[dict[int, set[str]]] = [dict() for _ in roles]
    center_edge_counts: list[int] = []
    for center in fine["centers"]:
        center_rank = int(center["rank"])
        center_edges: set[tuple[int, int]] = set()
        for (rank, activation_index, floor_index), index in provenance_to_index.items():
            if rank != center_rank:
                continue
            for delta_a, delta_f, axis in (
                (-1, 0, "activation_r"),
                (1, 0, "activation_r"),
                (0, -1, "floor_r"),
                (0, 1, "floor_r"),
            ):
                neighbor = provenance_to_index.get(
                    (center_rank, activation_index + delta_a, floor_index + delta_f)
                )
                if neighbor is None:
                    continue
                adjacency[index].add(neighbor)
                edge_axes[index].setdefault(neighbor, set()).add(axis)
                center_edges.add(tuple(sorted((index, neighbor))))
        center_edge_counts.append(len(center_edges))
    if center_edge_counts != [
        int(value) for value in fine["expected_center_local_adjacency_edges"]
    ]:
        raise RuntimeError("fine center-local adjacency edge counts mismatch")
    edge_count = sum(len(values) for values in adjacency) // 2
    if edge_count != int(fine["expected_total_adjacency_edges"]):
        raise RuntimeError("fine total adjacency edge count mismatch")
    center_role_indices: list[int] = []
    for frozen in config["stage_a_centers"]:
        pair = (float(frozen["activation_r"]), float(frozen["floor_r"]))
        if pair not in pair_to_index:
            raise RuntimeError("immutable Stage-A center missing from fine role map")
        center_role_indices.append(pair_to_index[pair])
    return {
        "roles": roles,
        "adjacency": adjacency,
        "edge_axes": edge_axes,
        "edge_count": edge_count,
        "center_edge_counts": center_edge_counts,
        "center_role_indices": center_role_indices,
    }


def period_bounds(config: dict[str, Any], name: str) -> tuple[datetime, datetime]:
    values = config["periods"][name]
    return iso_time(values[0]), iso_time(values[1])


def selected_lifecycles(
    lifecycles: list[Lifecycle], start: datetime | None, end: datetime | None
) -> list[Lifecycle]:
    return [
        item
        for item in lifecycles
        if (start is None or item.close_time >= start)
        and (end is None or item.close_time < end)
    ]


def classify(
    item: Lifecycle, role: dict[str, Any], tolerance: float
) -> str:
    if role["kind"] == "EXACT_V8_NEUTRAL":
        return "NEUTRAL"
    activation = float(role["activation_r"])
    floor = float(role["floor_r"])
    reached = item.peak_mark_r + tolerance >= activation
    post_peak_close_cross = (
        item.peak_time < item.close_time
        and item.last_mark_r <= floor + tolerance
    )
    post_peak_trough_cross = (
        item.peak_time < item.trough_time <= item.close_time
        and item.trough_mark_r <= floor + tolerance
    )
    certain_trigger = reached and (post_peak_close_cross or post_peak_trough_cross)
    certain_never = (not reached) or item.trough_mark_r > floor + tolerance
    if certain_trigger and certain_never:
        raise RuntimeError("contradictory partial-identification classification")
    if certain_trigger:
        return "CERTAIN_TRIGGER"
    if certain_never:
        return "CERTAIN_NEVER"
    return "AMBIGUOUS"


def floor_books(item: Lifecycle, floor_r: float) -> tuple[float, float]:
    actual_friction = max(0.0, item.last_mark_profit_usd - item.actual_net_usd)
    stressed_friction = max(0.0, item.last_mark_profit_usd - item.stressed_net_usd)
    gross = floor_r * item.planned_risk_usd
    return gross - actual_friction, gross - stressed_friction


def lifecycle_books(
    item: Lifecycle, role: dict[str, Any], tolerance: float
) -> dict[str, Any]:
    classification = classify(item, role, tolerance)
    if classification == "NEUTRAL" or classification == "CERTAIN_NEVER":
        return {
            "classification": classification,
            "lower_actual": item.actual_net_usd,
            "lower_stressed": item.stressed_net_usd,
            "upper_actual": item.actual_net_usd,
            "upper_stressed": item.stressed_net_usd,
            "lower_actual_replaced": False,
            "lower_stressed_replaced": False,
        }
    floor_actual, floor_stressed = floor_books(item, float(role["floor_r"]))
    if classification == "CERTAIN_TRIGGER":
        return {
            "classification": classification,
            "lower_actual": floor_actual,
            "lower_stressed": floor_stressed,
            "upper_actual": floor_actual,
            "upper_stressed": floor_stressed,
            "lower_actual_replaced": True,
            "lower_stressed_replaced": True,
        }
    lower_actual = min(item.actual_net_usd, floor_actual)
    lower_stressed = min(item.stressed_net_usd, floor_stressed)
    return {
        "classification": classification,
        "lower_actual": lower_actual,
        "lower_stressed": lower_stressed,
        "upper_actual": max(item.actual_net_usd, floor_actual),
        "upper_stressed": max(item.stressed_net_usd, floor_stressed),
        "lower_actual_replaced": floor_actual < item.actual_net_usd - tolerance,
        "lower_stressed_replaced": floor_stressed < item.stressed_net_usd - tolerance,
    }


def density_only(
    lifecycles: list[Lifecycle],
    role_map: dict[str, Any],
    config: dict[str, Any],
    start: datetime | None,
    end: datetime | None,
) -> dict[str, np.ndarray]:
    selected = selected_lifecycles(lifecycles, start, end)
    role_count = len(role_map["roles"])
    component_count = len(config["components"])
    tolerance = float(config["numeric_tolerance"])
    activated = np.zeros(role_count, dtype=np.int32)
    certain = np.zeros(role_count, dtype=np.int32)
    never = np.zeros(role_count, dtype=np.int32)
    ambiguous = np.zeros(role_count, dtype=np.int32)
    certain_components = np.zeros((role_count, component_count), dtype=np.int32)
    for role_index, role in enumerate(role_map["roles"]):
        if role["kind"] == "EXACT_V8_NEUTRAL":
            continue
        activation = float(role["activation_r"])
        for item in selected:
            if item.peak_mark_r + tolerance >= activation:
                activated[role_index] += 1
            classification = classify(item, role, tolerance)
            if classification == "CERTAIN_TRIGGER":
                certain[role_index] += 1
                certain_components[role_index, item.component_index] += 1
            elif classification == "CERTAIN_NEVER":
                never[role_index] += 1
            elif classification == "AMBIGUOUS":
                ambiguous[role_index] += 1
            else:
                raise RuntimeError("unexpected nonneutral density classification")
    if role_count > 1 and np.any(
        certain[1:] + never[1:] + ambiguous[1:] != len(selected)
    ):
        raise RuntimeError("partial-identification density does not partition lifecycles")
    return {
        "lifecycles": np.full(role_count, len(selected), dtype=np.int32),
        "activated": activated,
        "certain": certain,
        "never": never,
        "ambiguous": ambiguous,
        "certain_components": certain_components,
    }


def simulate(
    lifecycles: list[Lifecycle],
    role_map: dict[str, Any],
    config: dict[str, Any],
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, np.ndarray]:
    selected = selected_lifecycles(lifecycles, start, end)
    roles = role_map["roles"]
    role_count = len(roles)
    component_count = len(config["components"])
    tolerance = float(config["numeric_tolerance"])
    reference = float(config["reference_capital_usd"])

    lower_actual_balance = np.full(role_count, reference, dtype=np.float64)
    lower_stressed_balance = np.full(role_count, reference, dtype=np.float64)
    actual_peak = lower_actual_balance.copy()
    stressed_peak = lower_stressed_balance.copy()
    actual_dd = np.zeros(role_count, dtype=np.float64)
    stressed_dd = np.zeros(role_count, dtype=np.float64)
    minimum_balance = np.full(role_count, reference, dtype=np.float64)
    upper_actual_net = np.zeros(role_count, dtype=np.float64)
    upper_stressed_net = np.zeros(role_count, dtype=np.float64)
    activated = np.zeros(role_count, dtype=np.int32)
    certain = np.zeros(role_count, dtype=np.int32)
    never = np.zeros(role_count, dtype=np.int32)
    ambiguous = np.zeros(role_count, dtype=np.int32)
    certain_components = np.zeros((role_count, component_count), dtype=np.int32)
    lower_actual_replacements = np.zeros(role_count, dtype=np.int32)
    lower_stressed_replacements = np.zeros(role_count, dtype=np.int32)
    lower_component_actual = np.zeros((role_count, component_count), dtype=np.float64)
    lower_component_stressed = np.zeros_like(lower_component_actual)

    prepared: dict[str, list[dict[str, Any]]] = {}
    for item in selected:
        books_by_role: list[dict[str, Any]] = []
        for role_index, role in enumerate(roles):
            books = lifecycle_books(item, role, tolerance)
            books_by_role.append(books)
            upper_actual_net[role_index] += float(books["upper_actual"])
            upper_stressed_net[role_index] += float(books["upper_stressed"])
            classification = str(books["classification"])
            if role["kind"] != "EXACT_V8_NEUTRAL" and (
                item.peak_mark_r + tolerance >= float(role["activation_r"])
            ):
                activated[role_index] += 1
            if classification == "CERTAIN_TRIGGER":
                certain[role_index] += 1
                certain_components[role_index, item.component_index] += 1
            elif classification == "CERTAIN_NEVER":
                never[role_index] += 1
            elif classification == "AMBIGUOUS":
                ambiguous[role_index] += 1
            elif classification != "NEUTRAL":
                raise RuntimeError("unexpected classification")
            lower_actual_replacements[role_index] += int(
                bool(books["lower_actual_replaced"])
            )
            lower_stressed_replacements[role_index] += int(
                bool(books["lower_stressed_replaced"])
            )
        prepared[item.identifier] = books_by_role

    if role_count > 1 and np.any(
        certain[1:] + never[1:] + ambiguous[1:] != len(selected)
    ):
        raise RuntimeError("partial-identification simulation does not partition lifecycles")

    events: list[tuple[int, str, Lifecycle]] = []
    for item in selected:
        events.append((item.birth_order, "BIRTH", item))
        events.append((item.close_order, "CLOSE", item))
    events.sort(key=lambda value: value[0])
    for _, event, item in events:
        actual_increment = np.zeros(role_count, dtype=np.float64)
        stressed_increment = np.zeros(role_count, dtype=np.float64)
        for role_index, books in enumerate(prepared[item.identifier]):
            actual_value = float(books["lower_actual"])
            stressed_value = float(books["lower_stressed"])
            actual_at_birth = bool(books["lower_actual_replaced"]) and actual_value < 0.0
            stressed_at_birth = bool(books["lower_stressed_replaced"]) and stressed_value < 0.0
            if event == "BIRTH":
                if actual_at_birth:
                    actual_increment[role_index] = actual_value
                if stressed_at_birth:
                    stressed_increment[role_index] = stressed_value
            else:
                if not actual_at_birth:
                    actual_increment[role_index] = actual_value
                if not stressed_at_birth:
                    stressed_increment[role_index] = stressed_value
                lower_component_actual[role_index, item.component_index] += actual_value
                lower_component_stressed[role_index, item.component_index] += stressed_value
        lower_actual_balance += actual_increment
        lower_stressed_balance += stressed_increment
        actual_peak = np.maximum(actual_peak, lower_actual_balance)
        stressed_peak = np.maximum(stressed_peak, lower_stressed_balance)
        actual_dd = np.maximum(
            actual_dd,
            np.where(
                actual_peak > 0.0,
                (actual_peak - lower_actual_balance) / actual_peak,
                np.inf,
            ),
        )
        stressed_dd = np.maximum(
            stressed_dd,
            np.where(
                stressed_peak > 0.0,
                (stressed_peak - lower_stressed_balance) / stressed_peak,
                np.inf,
            ),
        )
        minimum_balance = np.minimum(
            minimum_balance,
            np.minimum(lower_actual_balance, lower_stressed_balance),
        )
    lower_actual_net = lower_actual_balance - reference
    lower_stressed_net = lower_stressed_balance - reference
    if np.any(upper_actual_net + tolerance < lower_actual_net):
        raise RuntimeError("actual upper identification book fell below lower book")
    if np.any(upper_stressed_net + tolerance < lower_stressed_net):
        raise RuntimeError("stressed upper identification book fell below lower book")
    return {
        "lifecycles": np.full(role_count, len(selected), dtype=np.int32),
        "lower_actual_net": lower_actual_net,
        "lower_stressed_net": lower_stressed_net,
        "upper_actual_net": upper_actual_net,
        "upper_stressed_net": upper_stressed_net,
        "actual_dd_pct": actual_dd * 100.0,
        "stressed_dd_pct": stressed_dd * 100.0,
        "minimum_balance": minimum_balance,
        "activated": activated,
        "certain": certain,
        "never": never,
        "ambiguous": ambiguous,
        "certain_components": certain_components,
        "lower_actual_replacements": lower_actual_replacements,
        "lower_stressed_replacements": lower_stressed_replacements,
        "lower_component_actual": lower_component_actual,
        "lower_component_stressed": lower_component_stressed,
    }


def assert_close(observed: float, expected: float, tolerance: float, label: str) -> None:
    if abs(observed - expected) > tolerance:
        raise RuntimeError(
            f"{label} mismatch: observed={observed!r}, expected={expected!r}"
        )


def verify_anchor(
    metrics: dict[str, np.ndarray], anchor: dict[str, Any], config: dict[str, Any], label: str
) -> None:
    if int(metrics["lifecycles"][0]) != int(anchor["lifecycles"]):
        raise RuntimeError(f"{label} lifecycle anchor mismatch")
    tolerances = config["anchors"]
    assert_close(
        float(metrics["lower_actual_net"][0]),
        float(anchor["actual_net_usd"]),
        float(tolerances["net_tolerance_usd"]),
        f"{label} actual net",
    )
    assert_close(
        float(metrics["lower_stressed_net"][0]),
        float(anchor["stressed_net_usd"]),
        float(tolerances["net_tolerance_usd"]),
        f"{label} stressed net",
    )
    assert_close(
        float(metrics["actual_dd_pct"][0]),
        float(anchor["actual_closed_balance_drawdown_pct"]),
        float(tolerances["drawdown_tolerance_points"]),
        f"{label} drawdown",
    )
    assert_close(
        float(metrics["minimum_balance"][0]),
        float(anchor["minimum_balance_usd"]),
        float(tolerances["minimum_balance_tolerance_usd"]),
        f"{label} minimum balance",
    )


def verify_stage_a_center_reproduction(
    role_map: dict[str, Any],
    development: dict[str, np.ndarray],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    tolerance = 1.0e-7
    reproduced: list[dict[str, Any]] = []
    for frozen, role_index in zip(
        config["stage_a_centers"], role_map["center_role_indices"]
    ):
        role = role_map["roles"][role_index]
        comparisons = (
            (float(role["activation_r"]), float(frozen["activation_r"]), "activation"),
            (float(role["floor_r"]), float(frozen["floor_r"]), "floor"),
            (
                float(development["lower_actual_net"][role_index]),
                float(frozen["development_lower_actual_net_usd"]),
                "lower actual",
            ),
            (
                float(development["lower_stressed_net"][role_index]),
                float(frozen["development_lower_stressed_net_usd"]),
                "lower stressed",
            ),
            (
                float(development["actual_dd_pct"][role_index]),
                float(frozen["development_actual_drawdown_pct"]),
                "actual drawdown",
            ),
        )
        for observed, expected, label in comparisons:
            if abs(observed - expected) > tolerance:
                raise RuntimeError(f"Stage-A center {label} reproduction mismatch")
        reproduced.append(
            {
                "stage_a_rank": int(frozen["rank"]),
                "fine_role_index": int(role_index),
                "activation_r": float(role["activation_r"]),
                "floor_r": float(role["floor_r"]),
                "lower_actual_net_usd": float(
                    development["lower_actual_net"][role_index]
                ),
                "lower_stressed_net_usd": float(
                    development["lower_stressed_net"][role_index]
                ),
                "actual_drawdown_pct": float(
                    development["actual_dd_pct"][role_index]
                ),
            }
        )
    return reproduced


def metric_record(
    index: int,
    role_map: dict[str, Any],
    metrics: dict[str, np.ndarray],
    config: dict[str, Any],
) -> dict[str, Any]:
    role = role_map["roles"][index]
    components = config["components"]
    return {
        "role_index": index,
        "kind": str(role["kind"]),
        "activation_r": role["activation_r"],
        "floor_r": role["floor_r"],
        "center_ranks": list(role.get("center_ranks", [])),
        "coordinate_provenance": list(role.get("coordinate_provenance", [])),
        "source_lifecycles": int(metrics["lifecycles"][index]),
        "lower_actual_net_usd": float(metrics["lower_actual_net"][index]),
        "lower_stressed_net_usd": float(metrics["lower_stressed_net"][index]),
        "upper_actual_net_usd": float(metrics["upper_actual_net"][index]),
        "upper_stressed_net_usd": float(metrics["upper_stressed_net"][index]),
        "stressed_identification_width_usd": float(
            metrics["upper_stressed_net"][index]
            - metrics["lower_stressed_net"][index]
        ),
        "adverse_timing_actual_closed_balance_drawdown_pct": float(
            metrics["actual_dd_pct"][index]
        ),
        "adverse_timing_stressed_closed_balance_drawdown_pct": float(
            metrics["stressed_dd_pct"][index]
        ),
        "minimum_balance_usd": float(metrics["minimum_balance"][index]),
        "activation_reached": int(metrics["activated"][index]),
        "certain_triggers": int(metrics["certain"][index]),
        "certain_never": int(metrics["never"][index]),
        "ambiguous": int(metrics["ambiguous"][index]),
        "lower_actual_replacements": int(metrics["lower_actual_replacements"][index]),
        "lower_stressed_replacements": int(
            metrics["lower_stressed_replacements"][index]
        ),
        "components": [
            {
                "short": str(component["short"]),
                "certain_triggers": int(
                    metrics["certain_components"][index, component_index]
                ),
                "lower_actual_net_usd": float(
                    metrics["lower_component_actual"][index, component_index]
                ),
                "lower_stressed_net_usd": float(
                    metrics["lower_component_stressed"][index, component_index]
                ),
            }
            for component_index, component in enumerate(components)
        ],
    }


def identification_summary(
    role_index: int,
    density_blocks: dict[str, dict[str, np.ndarray]],
    config: dict[str, Any],
) -> dict[str, Any]:
    component_count = len(config["components"])
    certain_total = sum(
        int(metrics["certain"][role_index]) for metrics in density_blocks.values()
    )
    component_counts = np.zeros(component_count, dtype=np.int32)
    blocks_with_certain = 0
    by_block: dict[str, int] = {}
    for name, metrics in density_blocks.items():
        count = int(metrics["certain"][role_index])
        by_block[name] = count
        component_counts += metrics["certain_components"][role_index]
        if count > 0:
            blocks_with_certain += 1
    components_with_certain = int(np.count_nonzero(component_counts > 0))
    gates = config["gates"]
    passed = (
        certain_total >= int(gates["minimum_certain_triggers"])
        and components_with_certain
        >= int(gates["minimum_certain_trigger_components"])
        and blocks_with_certain
        >= int(gates["minimum_certain_trigger_presholdout_blocks"])
    )
    return {
        "certain_triggers_presholdout": certain_total,
        "components_with_certain_triggers": components_with_certain,
        "blocks_with_certain_triggers": blocks_with_certain,
        "certain_triggers_by_block": by_block,
        "certain_triggers_by_component": [int(value) for value in component_counts],
        "passed": passed,
    }


def robust_points(
    eligible: np.ndarray,
    role_map: dict[str, Any],
    development: dict[str, np.ndarray],
    blocks: list[dict[str, np.ndarray]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    eligible_set = set(int(value) for value in np.flatnonzero(eligible))
    minimum_neighbors = int(config["fine_map"]["minimum_eligible_neighbors"])
    minimum_axes = int(config["fine_map"]["minimum_neighbor_axes"])
    robust: list[dict[str, Any]] = []
    for index in sorted(eligible_set):
        if index == 0:
            continue
        neighbors = sorted(
            neighbor
            for neighbor in role_map["adjacency"][index]
            if neighbor in eligible_set
        )
        axes: set[str] = set()
        for neighbor in neighbors:
            axes.update(role_map["edge_axes"][index].get(neighbor, set()))
        if len(neighbors) < minimum_neighbors or len(axes) < minimum_axes:
            continue
        robust.append(
            {
                "index": index,
                "eligible_neighbor_count": len(neighbors),
                "eligible_neighbor_indices": neighbors,
                "eligible_neighbor_axes": sorted(axes),
                "weakest_block_lower_stressed_net_usd": min(
                    float(metrics["lower_stressed_net"][index]) for metrics in blocks
                ),
            }
        )
    robust.sort(
        key=lambda item: (
            -float(item["weakest_block_lower_stressed_net_usd"]),
            -float(development["lower_stressed_net"][item["index"]])
            / max(float(development["actual_dd_pct"][item["index"]]), 1.0e-12),
            -float(development["lower_stressed_net"][item["index"]]),
            float(development["actual_dd_pct"][item["index"]]),
            float(
                development["upper_stressed_net"][item["index"]]
                - development["lower_stressed_net"][item["index"]]
            ),
            int(item["index"]),
        )
    )
    return robust


def near_miss_points(
    role_map: dict[str, Any],
    development: dict[str, np.ndarray],
    blocks: list[dict[str, np.ndarray]],
    identifications: list[dict[str, Any]],
    config: dict[str, Any],
    active_tier: str,
) -> list[dict[str, Any]]:
    anchor = config["anchors"]["development"]
    gates = config["gates"]
    floor = float(gates["near_miss_normalization_floor"])
    if not bool(config["fine_map"]["near_miss_targets_follow_active_tier"]):
        raise RuntimeError("near-miss active-tier targeting must remain frozen")
    if active_tier == "PRIMARY":
        target_stressed = float(anchor["stressed_net_usd"]) * float(
            gates["primary_stressed_retention"]
        )
        target_dd = float(gates["primary_max_drawdown_pct"])
    elif active_tier == "FALLBACK_REHABILITATION":
        target_stressed = float(anchor["stressed_net_usd"]) * float(
            gates["fallback_stressed_retention"]
        )
        target_dd = float(anchor["actual_closed_balance_drawdown_pct"]) - float(
            gates["fallback_min_drawdown_improvement_points"]
        )
    else:
        raise RuntimeError("unexpected active tier for near-miss ranking")
    ranked: list[dict[str, Any]] = []
    block_anchor_names = [
        "development_2024_h1",
        "development_2024_h2",
        "development_2025_h1",
        "development_2025_h2",
    ]
    if len(blocks) != len(block_anchor_names):
        raise RuntimeError("near-miss block count does not match frozen anchors")
    for index in range(1, len(role_map["roles"])):
        score = 0.0
        for name, metrics in zip(block_anchor_names, blocks):
            block_anchor = config["anchors"][name]
            score += max(
                0.0, floor - float(metrics["lower_actual_net"][index])
            ) / max(abs(float(block_anchor["actual_net_usd"])), floor)
            score += max(
                0.0, floor - float(metrics["lower_stressed_net"][index])
            ) / max(abs(float(block_anchor["stressed_net_usd"])), floor)
            score += max(
                0.0, floor - float(metrics["minimum_balance"][index])
            ) / max(float(config["reference_capital_usd"]), floor)
        score += max(
            0.0, target_stressed - float(development["lower_stressed_net"][index])
        ) / max(abs(target_stressed), floor)
        score += max(
            0.0, float(development["actual_dd_pct"][index]) - target_dd
        ) / max(abs(float(anchor["actual_closed_balance_drawdown_pct"])), floor)
        identification = identifications[index]
        score += max(
            0,
            int(gates["minimum_certain_triggers"])
            - int(identification["certain_triggers_presholdout"]),
        ) / max(int(gates["minimum_certain_triggers"]), 1)
        score += max(
            0,
            int(gates["minimum_certain_trigger_components"])
            - int(identification["components_with_certain_triggers"]),
        ) / max(int(gates["minimum_certain_trigger_components"]), 1)
        score += max(
            0,
            int(gates["minimum_certain_trigger_presholdout_blocks"])
            - int(identification["blocks_with_certain_triggers"]),
        ) / max(int(gates["minimum_certain_trigger_presholdout_blocks"]), 1)
        ranked.append(
            {
                "index": index,
                "normalized_gate_deficit": score,
                "eligible_neighbor_count": 0,
                "eligible_neighbor_indices": [],
                "eligible_neighbor_axes": [],
                "weakest_block_lower_stressed_net_usd": min(
                    float(metrics["lower_stressed_net"][index]) for metrics in blocks
                ),
            }
        )
    ranked.sort(
        key=lambda item: (
            float(item["normalized_gate_deficit"]),
            -float(item["weakest_block_lower_stressed_net_usd"]),
            -float(development["lower_stressed_net"][item["index"]])
            / max(float(development["actual_dd_pct"][item["index"]]), 1.0e-12),
            int(item["index"]),
        )
    )
    return ranked


def select_centers(
    ranked: list[dict[str, Any]], role_map: dict[str, Any], config: dict[str, Any]
) -> list[dict[str, Any]]:
    maximum = int(config["fine_map"]["maximum_stage_c_centers"])
    if not bool(config["fine_map"]["center_selection_requires_distinct_pair"]):
        raise RuntimeError("fine center selection must require distinct pairs")
    selected: list[dict[str, Any]] = []
    selected_coordinates: set[tuple[float, float]] = set()
    for item in ranked:
        role = role_map["roles"][int(item["index"])]
        coordinate = (
            float(role["activation_r"]),
            float(role["floor_r"]),
        )
        if coordinate in selected_coordinates:
            continue
        selected.append(item)
        selected_coordinates.add(coordinate)
        if len(selected) == maximum:
            break
    return selected


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


def structural_precheck() -> dict[str, Any]:
    config = load_config()
    paths = verify_authority_and_inputs(config)
    stage_a_diagnostics = verify_stage_a_authority(config, paths)
    lifecycles, diagnostics = verify_and_load_data(config, paths)
    role_map = build_role_map(config)
    neutral_map = {
        "roles": role_map["roles"][:1],
        "adjacency": role_map["adjacency"][:1],
        "edge_axes": role_map["edge_axes"][:1],
        "edge_count": 0,
    }
    whole = simulate(lifecycles, neutral_map, config)
    verify_anchor(whole, config["anchors"]["whole"], config, "whole")
    development_start, development_end = period_bounds(config, "development")
    development = simulate(
        lifecycles, neutral_map, config, development_start, development_end
    )
    verify_anchor(
        development, config["anchors"]["development"], config, "development"
    )
    density_periods = [
        "development_2024_h1",
        "development_2024_h2",
        "development_2025_h1",
        "development_2025_h2",
        "validation_density_only",
    ]
    densities: dict[str, dict[str, np.ndarray]] = {}
    for name in density_periods:
        start, end = period_bounds(config, name)
        densities[name] = density_only(lifecycles, role_map, config, start, end)
    if int(densities["validation_density_only"]["lifecycles"][0]) != int(
        config["anchors"]["validation_density_only_lifecycles"]
    ):
        raise RuntimeError("validation density-only lifecycle count mismatch")
    return {
        "matched_lifecycles": len(lifecycles),
        "input_diagnostics": diagnostics,
        "stage_a_authority": stage_a_diagnostics,
        "internal_roles_with_neutral_control": len(role_map["roles"]),
        "nonneutral_roles": len(role_map["roles"]) - 1,
        "adjacency_edges": int(role_map["edge_count"]),
        "center_edge_counts": list(role_map["center_edge_counts"]),
        "stage_a_center_role_indices": list(role_map["center_role_indices"]),
        "role_coordinates": [
            [role["activation_r"], role["floor_r"], role.get("center_ranks", [])]
            for role in role_map["roles"]
        ],
        "whole_exact_v8": metric_record(0, neutral_map, whole, config),
        "development_exact_v8": metric_record(
            0, neutral_map, development, config
        ),
        "density_only": {
            name: {
                "lifecycles": int(metrics["lifecycles"][0]),
                "certain_by_role": [int(value) for value in metrics["certain"]],
            }
            for name, metrics in densities.items()
        },
        "candidate_economics_executed": False,
        "validation_economics_opened": False,
        "locked_holdout_economics_opened": False,
    }


def main() -> None:
    started = time.perf_counter()
    config = load_config()
    paths = verify_authority_and_inputs(config)
    stage_a_diagnostics = verify_stage_a_authority(config, paths)
    lifecycles, input_diagnostics = verify_and_load_data(config, paths)
    role_map = build_role_map(config)

    neutral_map = {
        "roles": role_map["roles"][:1],
        "adjacency": role_map["adjacency"][:1],
        "edge_axes": role_map["edge_axes"][:1],
        "edge_count": 0,
    }
    whole_anchor_metrics = simulate(lifecycles, neutral_map, config)
    verify_anchor(
        whole_anchor_metrics, config["anchors"]["whole"], config, "whole"
    )

    development_start, development_end = period_bounds(config, "development")
    development = simulate(
        lifecycles, role_map, config, development_start, development_end
    )
    verify_anchor(
        development, config["anchors"]["development"], config, "development"
    )
    stage_a_center_reproduction = verify_stage_a_center_reproduction(
        role_map, development, config
    )
    block_names = [
        "development_2024_h1",
        "development_2024_h2",
        "development_2025_h1",
        "development_2025_h2",
    ]
    block_metrics: list[dict[str, np.ndarray]] = []
    for name in block_names:
        start, end = period_bounds(config, name)
        metrics = simulate(lifecycles, role_map, config, start, end)
        verify_anchor(metrics, config["anchors"][name], config, name)
        block_metrics.append(metrics)

    density_names = block_names + ["validation_density_only"]
    density_blocks: dict[str, dict[str, np.ndarray]] = {}
    for name in density_names:
        start, end = period_bounds(config, name)
        density_blocks[name] = density_only(
            lifecycles, role_map, config, start, end
        )
    identifications = [
        identification_summary(index, density_blocks, config)
        for index in range(len(role_map["roles"]))
    ]
    common = np.ones(len(role_map["roles"]), dtype=bool)
    for metrics in block_metrics:
        common &= (
            (metrics["lower_actual_net"] > 0.0)
            & (metrics["lower_stressed_net"] > 0.0)
            & (metrics["minimum_balance"] > 0.0)
        )
    identification_passed = np.asarray(
        [bool(item["passed"]) for item in identifications], dtype=bool
    )
    anchor = config["anchors"]["development"]
    gates = config["gates"]
    primary = (
        common
        & identification_passed
        & (
            development["lower_stressed_net"]
            >= float(anchor["stressed_net_usd"])
            * float(gates["primary_stressed_retention"])
        )
        & (development["actual_dd_pct"] <= float(gates["primary_max_drawdown_pct"]))
    )
    fallback = (
        common
        & identification_passed
        & (
            development["lower_stressed_net"]
            >= float(anchor["stressed_net_usd"])
            * float(gates["fallback_stressed_retention"])
        )
        & (
            development["actual_dd_pct"]
            <= float(anchor["actual_closed_balance_drawdown_pct"])
            - float(gates["fallback_min_drawdown_improvement_points"])
        )
    )
    active_tier = "PRIMARY" if int(primary.sum()) > 0 else "FALLBACK_REHABILITATION"
    eligible = primary if active_tier == "PRIMARY" else fallback
    robust = robust_points(
        eligible, role_map, development, block_metrics, config
    )
    selection_kind = "ROBUST_ELIGIBLE"
    ranked = robust
    if not robust:
        ranked = near_miss_points(
            role_map,
            development,
            block_metrics,
            identifications,
            config,
            active_tier,
        )
        selection_kind = "DECLARED_NEAR_MISS"
    selected = select_centers(ranked, role_map, config)
    if not selected:
        raise RuntimeError("Stage B failed to select mandatory Stage-C centers")

    result: dict[str, Any] = {
        "schema": "zeta-next-dd20-v8-attained-profit-floor-fine-adjacency-proxy-result-v1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "campaign": "dd20-v8-attained-profit-floor-fine-adjacency-proxy-v1",
        "optimization_unit_id": str(config["optimization_unit_id"]),
        "unit_stage": str(config["unit_stage"]),
        "unit_closure_authority": False,
        "authority": {
            "declaration_commit_on_origin_main": str(
                config["declaration_authority"]["commit_on_origin_main"]
            ),
            "exact_v8_is_sole_economic_parent": True,
            "all_five_existing_entry_strategies_active": True,
            "entry_formula_direction_timestamp_initial_stop_native_hold_unchanged": True,
            "position_management_only": True,
            "new_entry_strategy": False,
            "lab_opened": False,
            "external_input": False,
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
            },
            "stage_a_durable": {
                "path": str(config["inputs"]["root"]) + "/" + str(config["inputs"]["stage_a_durable"]["name"]),
                "bytes": paths["stage_a_durable"].stat().st_size,
                "sha256": sha256(paths["stage_a_durable"]),
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
            "diagnostics": input_diagnostics,
            "stage_a_authority": stage_a_diagnostics,
            "stage_a_center_reproduction": stage_a_center_reproduction,
        },
        "partial_identification": {
            "activation_reached_rule": str(
                config["partial_identification"]["activation_reached"]
            ),
            "certain_trigger_rule": str(
                config["partial_identification"]["certain_trigger"]
            ),
            "certain_never_rule": str(
                config["partial_identification"]["certain_never"]
            ),
            "ambiguous_lower": str(config["partial_identification"]["ambiguous_lower"]),
            "ambiguous_upper": str(config["partial_identification"]["ambiguous_upper"]),
            "negative_replacement_timing": str(
                config["partial_identification"]["negative_replacement_timing"]
            ),
            "nonnegative_replacement_timing": str(
                config["partial_identification"]["nonnegative_replacement_timing"]
            ),
            "native_close_time_risk_occupancy_retained": True,
            "source_volume_and_accepted_path_fixed": True,
            "freed_capacity_profit_credit_usd": 0.0,
            "upper_book_can_select": False,
        },
        "fine_map": {
            "internal_roles_with_neutral_control": len(role_map["roles"]),
            "nonneutral_roles": len(role_map["roles"]) - 1,
            "adjacency_edges": int(role_map["edge_count"]),
            "center_edge_counts": list(role_map["center_edge_counts"]),
            "stage_a_center_role_indices": list(role_map["center_role_indices"]),
            "common_positive_four_half_year_roles": int(common.sum()),
            "identification_passing_roles": int(identification_passed.sum()),
            "primary_eligible": int(primary.sum()),
            "fallback_eligible": int(fallback.sum()),
            "active_tier": active_tier,
            "active_tier_eligible": int(eligible.sum()),
            "robust_active_tier_points": len(robust),
            "selection_kind": selection_kind,
        },
        "exact_anchor_whole_path": metric_record(
            0, neutral_map, whole_anchor_metrics, config
        ),
        "exact_anchor_development": metric_record(0, role_map, development, config),
        "exact_anchor_development_blocks": {
            name: metric_record(0, role_map, metrics, config)
            for name, metrics in zip(block_names, block_metrics)
        },
        "development_roles": [],
        "stage_c_centers": [],
        "validation_density_only": True,
        "validation_economics_opened": False,
        "locked_holdout_economics_opened": False,
        "mt5": {
            "shortlist_count": 0,
            "valid_economic_paths_run": 0,
            "maximum_valid_economic_paths_authorized_after_all_proxy_stages": int(
                config["mt5_budget"]["maximum_valid_economic_paths_after_all_proxy_stages"]
            ),
        },
        "limitations": [
            "The aggregate lifecycle ledger does not identify every first crossing; ambiguous paths are adverse in lower books and upper books have no selection authority.",
            "Proxy roles retain source accepted lifecycles, volume, native close-time risk occupancy and give zero credit to early capacity release or later existing-V8 admissions.",
            "Floor books use frozen observed close friction and cannot establish candidate-time gaps, stop quantization, slippage or exact broker execution.",
            "Adverse closed-balance timing charges negative replacements at birth and delays nonnegative replacements until native close; it is not native open-equity DD.",
            "January-May candidate economics and locked June-July remain unopened. A proxy survivor still requires the conditional exact control/finalist native pair.",
        ],
    }

    for index in range(len(role_map["roles"])):
        item = metric_record(index, role_map, development, config)
        item.update(
            {
                "identification": identifications[index],
                "common_gate_passed": bool(common[index]),
                "primary_gate_passed": bool(primary[index]),
                "fallback_gate_passed": bool(fallback[index]),
                "development_blocks": {
                    name: metric_record(index, role_map, metrics, config)
                    for name, metrics in zip(block_names, block_metrics)
                },
            }
        )
        result["development_roles"].append(item)

    for rank, meta in enumerate(selected, start=1):
        index = int(meta["index"])
        role = role_map["roles"][index]
        result["stage_c_centers"].append(
            {
                "development_rank": rank,
                "selection_kind": selection_kind,
                "role_index": index,
                "activation_r": float(role["activation_r"]),
                "floor_r": float(role["floor_r"]),
                "center_ranks": list(role["center_ranks"]),
                "coordinate_provenance": list(role["coordinate_provenance"]),
                "lower_actual_net_usd": float(development["lower_actual_net"][index]),
                "lower_stressed_net_usd": float(development["lower_stressed_net"][index]),
                "upper_stressed_net_usd": float(development["upper_stressed_net"][index]),
                "adverse_timing_actual_closed_balance_drawdown_pct": float(
                    development["actual_dd_pct"][index]
                ),
                "minimum_balance_usd": float(development["minimum_balance"][index]),
                "identification": identifications[index],
                "eligible_neighbor_count": int(meta["eligible_neighbor_count"]),
                "eligible_neighbor_indices": [
                    int(value) for value in meta["eligible_neighbor_indices"]
                ],
                "eligible_neighbor_axes": list(meta["eligible_neighbor_axes"]),
                "weakest_block_lower_stressed_net_usd": float(
                    meta["weakest_block_lower_stressed_net_usd"]
                ),
                "normalized_gate_deficit": meta.get("normalized_gate_deficit"),
            }
        )

    result["status"] = (
        "VALID_PROXY_COMPLETE_STAGE_B_ROBUST_FINE_PROFIT_FLOOR_CENTERS_STAGE_C_REQUIRED_NO_MT5"
        if selection_kind == "ROBUST_ELIGIBLE"
        else "VALID_PROXY_COMPLETE_STAGE_B_NEAR_MISS_FINE_PROFIT_FLOOR_CENTERS_STAGE_C_REQUIRED_NO_MT5"
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
                "stage_c_center_count": len(result["stage_c_centers"]),
                "mt5_paths": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
