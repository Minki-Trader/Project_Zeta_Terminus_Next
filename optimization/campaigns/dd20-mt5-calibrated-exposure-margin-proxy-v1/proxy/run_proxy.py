from __future__ import annotations

import csv
import hashlib
import itertools
import json
import struct
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
OUTPUT_PATH = (
    REPOSITORY_ROOT
    / "optimization"
    / "artifacts"
    / "raw"
    / "dd20-mt5-calibrated-exposure-margin-proxy-v1"
    / "output"
    / "proxy-result.json"
)
TIME_FORMAT = "%Y.%m.%d %H:%M:%S"


@dataclass(frozen=True)
class LifecycleEvent:
    server_time: datetime
    event: str
    component_index: int
    position_identifier: str
    source_volume_lots: float
    actual_net_usd: float
    stressed_net_usd: float


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def verify_inputs(config: dict[str, Any]) -> Path:
    input_root = REPOSITORY_ROOT / str(config["input"]["root"])
    files = sorted(config["input"]["files"], key=lambda item: str(item["name"]))
    manifest_lines: list[str] = []
    total_bytes = 0
    for declared in files:
        path = input_root / str(declared["name"])
        size = path.stat().st_size
        digest = sha256(path)
        if size != int(declared["bytes"]) or digest != str(declared["sha256"]):
            raise RuntimeError(f"copied input mismatch: {declared['name']}")
        total_bytes += size
        manifest_lines.append(f"{declared['name']}|{size}|{digest}")
    manifest = ("\n".join(manifest_lines) + "\n").encode("utf-8")
    manifest_hash = hashlib.sha256(manifest).hexdigest().upper()
    if len(files) != int(config["input"]["files_total"]):
        raise RuntimeError("copied input file count mismatch")
    if total_bytes != int(config["input"]["bytes_total"]):
        raise RuntimeError("copied input byte total mismatch")
    if manifest_hash != str(config["input"]["canonical_manifest_sha256"]):
        raise RuntimeError("copied input manifest mismatch")
    return input_root


def extract_segment(
    path: Path,
    target_segment: int,
    expected: dict[str, Any],
    components: list[str],
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> list[LifecycleEvent]:
    component_index = {component: index for index, component in enumerate(components)}
    events: list[LifecycleEvent] = []
    segment = 0
    previous_sequence: int | None = None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for source in csv.DictReader(handle):
            sequence = int(source["research_state_sequence"])
            if previous_sequence is not None and sequence < previous_sequence:
                segment += 1
            previous_sequence = sequence
            if segment > target_segment:
                break
            if segment != target_segment or source["event"] not in {"BIRTH", "CLOSE"}:
                continue
            server_time = datetime.strptime(source["server_time"], TIME_FORMAT)
            if period_end is not None and server_time >= period_end:
                break
            if period_start is not None and server_time < period_start:
                continue
            component = source["component_id"]
            if component not in component_index:
                raise RuntimeError("segment contains an undeclared component")
            events.append(
                LifecycleEvent(
                    server_time=server_time,
                    event=source["event"],
                    component_index=component_index[component],
                    position_identifier=source["position_identifier"],
                    source_volume_lots=float(source["volume"]),
                    actual_net_usd=float(source["actual_net_usd"]),
                    stressed_net_usd=float(source["stressed_net_usd"]),
                )
            )

    births = [event for event in events if event.event == "BIRTH"]
    closes = [event for event in events if event.event == "CLOSE"]
    birth_ids = [event.position_identifier for event in births]
    close_ids = [event.position_identifier for event in closes]
    if len(births) != int(expected["births"]):
        raise RuntimeError("declared birth count does not match copied input")
    if len(closes) != int(expected["closed_lifecycles"]):
        raise RuntimeError("declared close count does not match copied input")
    if len(set(birth_ids)) != len(birth_ids) or set(birth_ids) != set(close_ids):
        raise RuntimeError("birth/close position identity mismatch")
    if any(event.source_volume_lots <= 0.0 for event in births):
        raise RuntimeError("source birth volume must be positive")
    if "component_birth_counts" in expected:
        observed_counts = {component: 0 for component in components}
        for event in births:
            observed_counts[components[event.component_index]] += 1
        if observed_counts != {
            str(key): int(value)
            for key, value in expected["component_birth_counts"].items()
        }:
            raise RuntimeError("declared component birth density does not match input")
    if "actual_net_usd" in expected and "stressed_net_usd" in expected:
        actual = sum(event.actual_net_usd for event in closes)
        stressed = sum(event.stressed_net_usd for event in closes)
        if abs(actual - float(expected["actual_net_usd"])) > 1.0e-7:
            raise RuntimeError("declared actual net does not match copied input")
        if abs(stressed - float(expected["stressed_net_usd"])) > 1.0e-7:
            raise RuntimeError("declared stressed net does not match copied input")
    return events


def candidate_weights(config: dict[str, Any]) -> np.ndarray:
    grids = [
        [float(value) for value in values]
        for values in config["component_weight_grids"]
    ]
    if len(grids) != len(config["components"]):
        raise RuntimeError("component grid count does not match component count")
    rows = list(itertools.product(*grids))
    weights = np.asarray(rows, dtype=np.float64)
    if len(weights) != int(config["expected_compositions"]):
        raise RuntimeError("candidate lattice count does not match the contract")
    if len(np.unique(weights, axis=0)) != len(weights):
        raise RuntimeError("candidate lattice contains duplicate weight rows")
    return weights


def add_anchor_weights(
    weights: np.ndarray, anchors: list[dict[str, Any]]
) -> tuple[np.ndarray, dict[str, int]]:
    rows = [row.copy() for row in weights]
    anchor_indices: dict[str, int] = {}
    for anchor in anchors:
        target = np.asarray(anchor["weights"], dtype=np.float64)
        matches = [
            index for index, row in enumerate(rows) if np.all(np.isclose(row, target))
        ]
        if len(matches) > 1:
            raise RuntimeError("anchor weight appears more than once")
        if matches:
            index = matches[0]
        else:
            rows.append(target)
            index = len(rows) - 1
        anchor_indices[str(anchor["id"])] = index
    return np.asarray(rows, dtype=np.float64), anchor_indices


def cache_double(path: Path, offset_hex: str) -> float:
    payload = path.read_bytes()
    offset = int(offset_hex, 16)
    if offset < 0 or offset + 8 > len(payload):
        raise RuntimeError("native cache statistic offset is outside the file")
    return float(struct.unpack_from("<d", payload, offset)[0])


def piecewise_calibration(
    raw_values: np.ndarray,
    raw_anchors: list[float],
    observed_anchors: list[float],
) -> tuple[np.ndarray, list[float]]:
    order = np.argsort(np.asarray(raw_anchors, dtype=np.float64))
    raw_points = np.asarray(raw_anchors, dtype=np.float64)[order]
    observed_points = np.asarray(observed_anchors, dtype=np.float64)[order]
    if np.any(np.diff(raw_points) <= 1.0e-12):
        raise RuntimeError("selection DD anchors do not have distinct raw values")
    if np.any(np.diff(observed_points) <= 0.0):
        raise RuntimeError("selection MT5 DD anchors are not increasing")
    slopes = np.diff(observed_points) / np.diff(raw_points)
    projected = np.interp(raw_values, raw_points, observed_points)
    below = raw_values < raw_points[0]
    above = raw_values > raw_points[-1]
    projected[below] = observed_points[0] + slopes[0] * (
        raw_values[below] - raw_points[0]
    )
    projected[above] = observed_points[-1] + slopes[-1] * (
        raw_values[above] - raw_points[-1]
    )
    return np.maximum(raw_values, projected), [float(value) for value in slopes]


def affine_calibration(
    raw_values: np.ndarray,
    raw_low: float,
    observed_low: float,
    raw_high: float,
    observed_high: float,
) -> tuple[np.ndarray, float, float]:
    if raw_high <= raw_low + 1.0e-12 or observed_high <= observed_low:
        raise RuntimeError("paired-forward DD anchors do not define an increasing line")
    slope = (observed_high - observed_low) / (raw_high - raw_low)
    intercept = observed_low - slope * raw_low
    projected = slope * raw_values + intercept
    return np.maximum(raw_values, projected), float(slope), float(intercept)


def epoch_index(server_time: datetime, epochs: list[dict[str, Any]]) -> int | None:
    for index, epoch in enumerate(epochs):
        if epoch["start_time"] <= server_time < epoch["end_time"]:
            return index
    return None


def simulate(
    events: list[LifecycleEvent],
    weights: np.ndarray,
    config: dict[str, Any],
    declared_epochs: list[dict[str, Any]],
) -> dict[str, np.ndarray]:
    candidate_count, component_count = weights.shape
    epoch_count = len(declared_epochs)
    reference = float(config["reference_capital_usd"])
    model = config["economic_execution_model"]
    base_volume = float(model["base_volume_lots"])
    volume_step = float(model["volume_step_lots"])
    addition_step = float(model["addition_step_usd"])
    position_fraction = float(model["position_risk_fraction"])
    aggregate_fraction = float(model["aggregate_risk_fraction"])
    aggregate_tolerance = float(model["aggregate_tolerance_usd"])
    component_names = [str(value) for value in config["components"]]
    passive_component_index = component_names.index(
        str(model["passive_pending_component"])
    )

    actual_balance = np.full(candidate_count, reference, dtype=np.float64)
    stressed_balance = np.full(candidate_count, reference, dtype=np.float64)
    actual_peak = actual_balance.copy()
    stressed_peak = stressed_balance.copy()
    actual_max_dd = np.zeros(candidate_count, dtype=np.float64)
    stressed_max_dd = np.zeros(candidate_count, dtype=np.float64)
    actual_minimum = actual_balance.copy()
    stressed_minimum = stressed_balance.copy()
    open_risk = np.zeros(candidate_count, dtype=np.float64)
    day_multiplier = np.ones(candidate_count, dtype=np.int32)
    accepted_count = np.zeros(candidate_count, dtype=np.int32)
    aggregate_skip_count = np.zeros(candidate_count, dtype=np.int32)
    disabled_skip_count = np.zeros(candidate_count, dtype=np.int32)
    capital_skip_count = np.zeros(candidate_count, dtype=np.int32)

    component_actual = np.zeros((candidate_count, component_count), dtype=np.float64)
    component_stressed = np.zeros_like(component_actual)
    component_closed = np.zeros((candidate_count, component_count), dtype=np.int32)

    epoch_actual_net = np.zeros((candidate_count, epoch_count), dtype=np.float64)
    epoch_stressed_net = np.zeros_like(epoch_actual_net)
    epoch_actual_peak = np.zeros_like(epoch_actual_net)
    epoch_stressed_peak = np.zeros_like(epoch_actual_net)
    epoch_actual_dd = np.zeros_like(epoch_actual_net)
    epoch_stressed_dd = np.zeros_like(epoch_actual_net)
    epoch_actual_minimum = np.full_like(epoch_actual_net, np.inf)
    epoch_stressed_minimum = np.full_like(epoch_actual_net, np.inf)
    epoch_initialized = [False] * epoch_count

    open_positions: dict[str, tuple[np.ndarray, np.ndarray, float, int]] = {}
    current_day = None
    for event in events:
        event_day = event.server_time.date()
        if event_day != current_day:
            growth = np.maximum(0.0, stressed_balance - reference)
            day_multiplier = (
                1 + np.floor(growth / addition_step + 1.0e-9).astype(np.int32)
            )
            day_multiplier = np.maximum(1, day_multiplier)
            current_day = event_day

        if event.event == "BIRTH":
            if event.position_identifier in open_positions:
                raise RuntimeError("duplicate open source position")
            component_weight = weights[:, event.component_index]
            if event.component_index == passive_component_index:
                source_base_steps = int(np.floor(event.source_volume_lots / volume_step + 0.5))
                if source_base_steps < 1:
                    raise RuntimeError("passive source reservation volume is invalid")
                base_steps = np.full(candidate_count, source_base_steps, dtype=np.int32)
            else:
                base_steps = day_multiplier
            requested_steps = base_steps.astype(np.float64) * component_weight
            target_steps = np.floor(requested_steps + 0.5).astype(np.int32)
            executable_multiplier = target_steps / base_steps.astype(np.float64)
            conservative_capital = np.minimum(actual_balance, stressed_balance)
            position_budget = (
                conservative_capital * position_fraction * executable_multiplier
            )
            aggregate_budget = conservative_capital * aggregate_fraction
            enabled = target_steps > 0
            capital_valid = conservative_capital > 0.0
            admitted = (
                enabled
                & capital_valid
                & (open_risk + position_budget <= aggregate_budget + aggregate_tolerance)
            )
            disabled_skip_count += (~enabled).astype(np.int32)
            capital_skip_count += (enabled & ~capital_valid).astype(np.int32)
            aggregate_skip_count += (
                enabled
                & capital_valid
                & ~admitted
            ).astype(np.int32)
            accepted_count += admitted.astype(np.int32)
            admitted_risk = np.where(admitted, position_budget, 0.0)
            admitted_steps = np.where(admitted, target_steps, 0).astype(np.int32)
            open_risk += admitted_risk
            open_positions[event.position_identifier] = (
                admitted_risk,
                admitted_steps,
                event.source_volume_lots,
                event.component_index,
            )
            continue

        if event.position_identifier not in open_positions:
            raise RuntimeError("source close has no matching birth")
        admitted_risk, admitted_steps, source_volume, component = open_positions.pop(
            event.position_identifier
        )
        e_index = epoch_index(event.server_time, declared_epochs)
        if e_index is not None and not epoch_initialized[e_index]:
            epoch_actual_peak[:, e_index] = actual_balance
            epoch_stressed_peak[:, e_index] = stressed_balance
            epoch_actual_minimum[:, e_index] = actual_balance
            epoch_stressed_minimum[:, e_index] = stressed_balance
            epoch_initialized[e_index] = True

        scale = admitted_steps.astype(np.float64) * volume_step / source_volume
        actual_increment = event.actual_net_usd * scale
        stressed_increment = event.stressed_net_usd * scale
        actual_balance += actual_increment
        stressed_balance += stressed_increment
        open_risk = np.maximum(0.0, open_risk - admitted_risk)

        component_actual[:, component] += actual_increment
        component_stressed[:, component] += stressed_increment
        component_closed[:, component] += (admitted_steps > 0).astype(np.int32)

        actual_peak = np.maximum(actual_peak, actual_balance)
        stressed_peak = np.maximum(stressed_peak, stressed_balance)
        actual_max_dd = np.maximum(
            actual_max_dd,
            np.where(actual_peak > 0.0, (actual_peak - actual_balance) / actual_peak, np.inf),
        )
        stressed_max_dd = np.maximum(
            stressed_max_dd,
            np.where(
                stressed_peak > 0.0,
                (stressed_peak - stressed_balance) / stressed_peak,
                np.inf,
            ),
        )
        actual_minimum = np.minimum(actual_minimum, actual_balance)
        stressed_minimum = np.minimum(stressed_minimum, stressed_balance)

        if e_index is not None:
            epoch_actual_net[:, e_index] += actual_increment
            epoch_stressed_net[:, e_index] += stressed_increment
            epoch_actual_peak[:, e_index] = np.maximum(
                epoch_actual_peak[:, e_index], actual_balance
            )
            epoch_stressed_peak[:, e_index] = np.maximum(
                epoch_stressed_peak[:, e_index], stressed_balance
            )
            epoch_actual_dd[:, e_index] = np.maximum(
                epoch_actual_dd[:, e_index],
                np.where(
                    epoch_actual_peak[:, e_index] > 0.0,
                    (epoch_actual_peak[:, e_index] - actual_balance)
                    / epoch_actual_peak[:, e_index],
                    np.inf,
                ),
            )
            epoch_stressed_dd[:, e_index] = np.maximum(
                epoch_stressed_dd[:, e_index],
                np.where(
                    epoch_stressed_peak[:, e_index] > 0.0,
                    (epoch_stressed_peak[:, e_index] - stressed_balance)
                    / epoch_stressed_peak[:, e_index],
                    np.inf,
                ),
            )
            epoch_actual_minimum[:, e_index] = np.minimum(
                epoch_actual_minimum[:, e_index], actual_balance
            )
            epoch_stressed_minimum[:, e_index] = np.minimum(
                epoch_stressed_minimum[:, e_index], stressed_balance
            )

    if open_positions:
        raise RuntimeError("segment ended with open source positions")
    if epoch_count and not all(epoch_initialized):
        raise RuntimeError("one or more declared epochs contain no close")
    if base_volume != volume_step:
        raise RuntimeError("this frozen model requires equal base and step volume")

    return {
        "actual_net": actual_balance - reference,
        "stressed_net": stressed_balance - reference,
        "raw_drawdown_pct": np.maximum(actual_max_dd, stressed_max_dd) * 100.0,
        "minimum_balance": np.minimum(actual_minimum, stressed_minimum),
        "accepted_count": accepted_count,
        "aggregate_skip_count": aggregate_skip_count,
        "disabled_skip_count": disabled_skip_count,
        "capital_skip_count": capital_skip_count,
        "component_actual": component_actual,
        "component_stressed": component_stressed,
        "component_closed": component_closed,
        "epoch_actual_net": epoch_actual_net,
        "epoch_stressed_net": epoch_stressed_net,
        "epoch_raw_drawdown_pct": np.maximum(epoch_actual_dd, epoch_stressed_dd)
        * 100.0,
        "epoch_minimum_balance": np.minimum(
            epoch_actual_minimum, epoch_stressed_minimum
        ),
    }


def find_weight_index(weights: np.ndarray, target: list[float]) -> int:
    matches = np.flatnonzero(
        np.all(np.isclose(weights, np.asarray(target, dtype=np.float64)), axis=1)
    )
    if len(matches) != 1:
        raise RuntimeError("declared anchor is absent or duplicated in the lattice")
    return int(matches[0])


def record_for_index(
    index: int,
    weights: np.ndarray,
    metrics: dict[str, np.ndarray],
    calibrated_dd: np.ndarray | None,
    epochs: list[dict[str, Any]],
    components: list[str],
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "weights": [float(value) for value in weights[index]],
        "active_components": int(np.count_nonzero(weights[index] > 0.0)),
        "actual_net_usd": float(metrics["actual_net"][index]),
        "stressed_net_usd": float(metrics["stressed_net"][index]),
        "raw_closed_balance_drawdown_pct": float(
            metrics["raw_drawdown_pct"][index]
        ),
        "minimum_balance_usd": float(metrics["minimum_balance"][index]),
        "accepted_lifecycles": int(metrics["accepted_count"][index]),
        "aggregate_risk_skips": int(metrics["aggregate_skip_count"][index]),
        "disabled_component_skips": int(metrics["disabled_skip_count"][index]),
        "capital_skips": int(metrics["capital_skip_count"][index]),
        "components": [],
    }
    if calibrated_dd is not None:
        record["calibrated_selection_mt5_drawdown_pct"] = float(
            calibrated_dd[index]
        )
    component_records: list[dict[str, Any]] = []
    for component_index, component in enumerate(components):
        component_records.append(
            {
                "component": component,
                "closed": int(metrics["component_closed"][index, component_index]),
                "actual_net_usd": float(
                    metrics["component_actual"][index, component_index]
                ),
                "stressed_net_usd": float(
                    metrics["component_stressed"][index, component_index]
                ),
            }
        )
    record["components"] = component_records
    if epochs:
        epoch_records: list[dict[str, Any]] = []
        for epoch_index_value, epoch in enumerate(epochs):
            epoch_records.append(
                {
                    "id": epoch["id"],
                    "actual_net_usd": float(
                        metrics["epoch_actual_net"][index, epoch_index_value]
                    ),
                    "stressed_net_usd": float(
                        metrics["epoch_stressed_net"][index, epoch_index_value]
                    ),
                    "raw_closed_balance_drawdown_pct": float(
                        metrics["epoch_raw_drawdown_pct"][index, epoch_index_value]
                    ),
                    "minimum_balance_usd": float(
                        metrics["epoch_minimum_balance"][index, epoch_index_value]
                    ),
                }
            )
        record["epochs"] = epoch_records
    return record


def rounded(value: Any) -> Any:
    if isinstance(value, np.generic):
        return rounded(value.item())
    if isinstance(value, float):
        return round(value, 10)
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [rounded(item) for item in value]
    return value


def main() -> None:
    started = time.perf_counter()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    components = [str(value) for value in config["components"]]
    input_root = verify_inputs(config)
    lifecycle_path = input_root / "parent-selection-forward-lifecycles.csv"

    calibration = config["selection_mt5_drawdown_calibration"]
    near_anchor = next(
        anchor for anchor in calibration["anchors"] if anchor["id"] == "near_miss"
    )
    extract_segment(
        input_root / str(near_anchor["lifecycle_file"]),
        0,
        near_anchor["lifecycle_expected"],
        components,
    )
    near_cache = input_root / str(near_anchor["native_cache_file"])
    cache_offsets = config["native_cache_offsets"]
    if (
        abs(
            cache_double(near_cache, cache_offsets["total_net_profit"])
            - float(near_anchor["observed_actual_net_usd"])
        )
        > 1.0e-9
        or abs(
            cache_double(near_cache, cache_offsets["equity_drawdown_relative_pct"])
            - float(near_anchor["observed_mt5_equity_drawdown_relative_pct"])
        )
        > 1.0e-9
    ):
        raise RuntimeError("near-miss selection native cache anchor mismatch")

    paired_calibration = config["paired_forward_mt5_drawdown_calibration"]
    near_forward_anchor = paired_calibration["near_miss_anchor"]
    extract_segment(
        input_root / str(near_forward_anchor["lifecycle_file"]),
        0,
        near_forward_anchor["lifecycle_expected"],
        components,
    )
    near_forward_cache = input_root / str(near_forward_anchor["native_cache_file"])
    if (
        abs(
            cache_double(near_forward_cache, cache_offsets["total_net_profit"])
            - float(near_forward_anchor["observed_actual_net_usd"])
        )
        > 1.0e-9
        or abs(
            cache_double(
                near_forward_cache,
                cache_offsets["equity_drawdown_relative_pct"],
            )
            - float(
                near_forward_anchor[
                    "observed_mt5_equity_drawdown_relative_pct"
                ]
            )
        )
        > 1.0e-9
    ):
        raise RuntimeError("near-miss forward native cache anchor mismatch")

    epochs: list[dict[str, Any]] = []
    for declared in config["selection_epochs"]:
        epochs.append(
            {
                "id": str(declared["id"]),
                "start": str(declared["start"]),
                "end": str(declared["end"]),
                "start_time": datetime.strptime(declared["start"], TIME_FORMAT),
                "end_time": datetime.strptime(declared["end"], TIME_FORMAT),
            }
        )

    selection_events = extract_segment(
        lifecycle_path,
        int(config["input"]["selection_segment_index"]),
        config["input"]["selection_expected"],
        components,
    )
    weights = candidate_weights(config)
    candidate_count = len(weights)
    evaluation_weights, anchor_indices = add_anchor_weights(
        weights, calibration["anchors"]
    )
    selection = simulate(selection_events, evaluation_weights, config, epochs)

    base_index = anchor_indices["base"]
    high_index = anchor_indices["high_exposure"]
    near_index = anchor_indices["near_miss"]
    selection_expected = config["input"]["selection_expected"]
    if (
        abs(float(selection["actual_net"][base_index]) - float(selection_expected["actual_net_usd"]))
        > 1.0e-7
        or abs(
            float(selection["stressed_net"][base_index])
            - float(selection_expected["stressed_net_usd"])
        )
        > 1.0e-7
        or int(selection["accepted_count"][base_index])
        != int(selection_expected["closed_lifecycles"])
        or int(selection["aggregate_skip_count"][base_index]) != 0
        or int(selection["disabled_skip_count"][base_index]) != 0
    ):
        raise RuntimeError("unweighted base does not reproduce source lifecycle economics")
    expected_near_proxy = near_anchor["expected_proxy_selection"]
    if (
        abs(
            float(selection["actual_net"][near_index])
            - float(expected_near_proxy["actual_net_usd"])
        )
        > 1.0e-7
        or abs(
            float(selection["stressed_net"][near_index])
            - float(expected_near_proxy["stressed_net_usd"])
        )
        > 1.0e-7
        or abs(
            float(selection["raw_drawdown_pct"][near_index])
            - float(expected_near_proxy["raw_drawdown_pct"])
        )
        > 1.0e-7
    ):
        raise RuntimeError("near-miss weight does not reproduce its frozen proxy anchor")

    raw_selection_anchors = [
        float(selection["raw_drawdown_pct"][anchor_indices[str(anchor["id"])]])
        for anchor in calibration["anchors"]
    ]
    observed_selection_anchors = [
        float(anchor["observed_mt5_equity_drawdown_relative_pct"])
        for anchor in calibration["anchors"]
    ]
    calibrated_dd, calibration_slopes = piecewise_calibration(
        selection["raw_drawdown_pct"],
        raw_selection_anchors,
        observed_selection_anchors,
    )
    selection_reserve = float(calibration["uncertainty_reserve_percentage_points"])
    budgeted_selection_dd = calibrated_dd + selection_reserve
    hard_dd = float(config["hard_mt5_equity_drawdown_pct"])
    selection_eligible = (
        (selection["actual_net"] > 0.0)
        & (selection["stressed_net"] > 0.0)
        & (selection["minimum_balance"] > 0.0)
        & (budgeted_selection_dd <= hard_dd + 1.0e-12)
        & np.all(selection["epoch_actual_net"] > 0.0, axis=1)
        & np.all(selection["epoch_stressed_net"] > 0.0, axis=1)
        & np.all(selection["epoch_minimum_balance"] > 0.0, axis=1)
        & np.all(selection["epoch_raw_drawdown_pct"] <= hard_dd + 1.0e-12, axis=1)
    )
    selection_eligible[candidate_count:] = False

    paired_config = config["paired_forward_period"]
    paired_events = extract_segment(
        lifecycle_path,
        int(config["input"]["later_segment_index"]),
        paired_config["expected"],
        components,
        datetime.strptime(paired_config["start"], TIME_FORMAT),
        datetime.strptime(paired_config["end"], TIME_FORMAT),
    )
    paired = simulate(paired_events, evaluation_weights, config, [])
    paired_base_index = anchor_indices["base"]
    paired_near_index = anchor_indices["near_miss"]
    calibrated_paired_dd, paired_slope, paired_intercept = affine_calibration(
        paired["raw_drawdown_pct"],
        float(paired["raw_drawdown_pct"][paired_base_index]),
        float(
            paired_calibration["base_anchor"][
                "observed_mt5_equity_drawdown_relative_pct"
            ]
        ),
        float(paired["raw_drawdown_pct"][paired_near_index]),
        float(
            paired_calibration["near_miss_anchor"][
                "observed_mt5_equity_drawdown_relative_pct"
            ]
        ),
    )
    paired_reserve = float(
        paired_calibration["uncertainty_reserve_percentage_points"]
    )
    budgeted_paired_dd = calibrated_paired_dd + paired_reserve
    paired_eligible = (
        selection_eligible
        & (paired["actual_net"] > 0.0)
        & (paired["stressed_net"] > 0.0)
        & (paired["minimum_balance"] > 0.0)
        & (budgeted_paired_dd <= hard_dd + 1.0e-12)
    )

    development_config = config["development_period"]
    development_events = extract_segment(
        lifecycle_path,
        int(config["input"]["later_segment_index"]),
        development_config["expected"],
        components,
        datetime.strptime(development_config["start"], TIME_FORMAT),
        datetime.strptime(development_config["end"], TIME_FORMAT),
    )
    development = simulate(development_events, evaluation_weights, config, [])
    development_eligible = (
        paired_eligible
        & (development["actual_net"] > 0.0)
        & (development["stressed_net"] > 0.0)
        & (development["minimum_balance"] > 0.0)
        & (development["raw_drawdown_pct"] <= hard_dd + 1.0e-12)
    )

    july_config = config["july_development_period"]
    july_events = extract_segment(
        lifecycle_path,
        int(config["input"]["later_segment_index"]),
        july_config["expected"],
        components,
        datetime.strptime(july_config["start"], TIME_FORMAT),
        datetime.strptime(july_config["end"], TIME_FORMAT),
    )
    july = simulate(july_events, evaluation_weights, config, [])
    final_eligible = (
        development_eligible
        & (july["actual_net"] > 0.0)
        & (july["stressed_net"] > 0.0)
        & (july["minimum_balance"] > 0.0)
        & (july["raw_drawdown_pct"] <= hard_dd + 1.0e-12)
    )
    final_eligible[candidate_count:] = False
    final_indices = [int(value) for value in np.flatnonzero(final_eligible)]

    def rank_key(index: int) -> tuple[Any, ...]:
        weaker_month = min(
            float(development["stressed_net"][index]),
            float(july["stressed_net"][index]),
        )
        return (
            -float(selection["stressed_net"][index]),
            -float(paired["stressed_net"][index]),
            -weaker_month,
            -float(selection["actual_net"][index]),
            -float(selection["epoch_stressed_net"][index, -1]),
            float(budgeted_selection_dd[index]),
            float(budgeted_paired_dd[index]),
            tuple(float(value) for value in evaluation_weights[index]),
        )

    ranked = sorted(final_indices, key=rank_key)
    winner_index = ranked[0] if ranked else None

    def complete_record(index: int) -> dict[str, Any]:
        record = record_for_index(
            index,
            evaluation_weights,
            selection,
            calibrated_dd,
            epochs,
            components,
        )
        record["selection_drawdown_uncertainty_reserve_percentage_points"] = (
            selection_reserve
        )
        record["budgeted_selection_mt5_drawdown_pct"] = float(
            budgeted_selection_dd[index]
        )
        record["paired_full_forward"] = record_for_index(
            index,
            evaluation_weights,
            paired,
            None,
            [],
            components,
        )
        record["paired_full_forward"]["calibrated_mt5_drawdown_pct"] = float(
            calibrated_paired_dd[index]
        )
        record["paired_full_forward"][
            "drawdown_uncertainty_reserve_percentage_points"
        ] = paired_reserve
        record["paired_full_forward"]["budgeted_mt5_drawdown_pct"] = float(
            budgeted_paired_dd[index]
        )
        record["development_june"] = record_for_index(
            index,
            evaluation_weights,
            development,
            None,
            [],
            components,
        )
        record["development_july"] = record_for_index(
            index,
            evaluation_weights,
            july,
            None,
            [],
            components,
        )
        return record

    top_count = int(config["output_top_selection_records"])
    top_qualified = [complete_record(index) for index in ranked[:top_count]]
    selection_winner = complete_record(winner_index) if winner_index is not None else None

    anchor_records: list[dict[str, Any]] = []
    for anchor in calibration["anchors"]:
        index = anchor_indices[str(anchor["id"])]
        record = complete_record(index)
        record["id"] = str(anchor["id"])
        record["observed_selection_mt5"] = {
            "actual_net_usd": float(anchor["observed_actual_net_usd"]),
            "stressed_net_usd": float(anchor["observed_stressed_net_usd"]),
            "equity_drawdown_relative_pct": float(
                anchor["observed_mt5_equity_drawdown_relative_pct"]
            ),
            "closed_lifecycles": int(anchor["observed_closed_lifecycles"]),
        }
        anchor_records.append(record)

    candidate_selection_count = int(np.count_nonzero(selection_eligible[:candidate_count]))
    candidate_paired_count = int(np.count_nonzero(paired_eligible[:candidate_count]))
    candidate_june_count = int(np.count_nonzero(development_eligible[:candidate_count]))
    if candidate_selection_count == 0:
        status = "VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE"
    elif candidate_paired_count == 0:
        status = "VALID_PROXY_COMPLETE_NO_FULL_PAIRED_FORWARD_ELIGIBLE"
    elif candidate_june_count == 0:
        status = "VALID_PROXY_COMPLETE_NO_JUNE_STABLE_CANDIDATE"
    elif winner_index is None:
        status = "VALID_PROXY_COMPLETE_NO_JULY_STABLE_CANDIDATE"
    else:
        status = "VALID_PROXY_COMPLETE_ONE_MT5_SHORTLIST"

    result = {
        "schema": "zeta-dd20-mt5-calibrated-exposure-margin-proxy-raw-result-v1",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "campaign": config["campaign"],
        "implementation": {
            "contract_sha256": sha256(CONFIG_PATH),
            "script_sha256": sha256(SCRIPT_PATH),
            "input_manifest_sha256": config["input"]["canonical_manifest_sha256"],
            "wall_time_seconds": time.perf_counter() - started,
            "unweighted_base_reproduction_gate": "PASS",
            "near_miss_proxy_reproduction_gate": "PASS",
            "near_miss_native_selection_cache_gate": "PASS",
            "near_miss_native_forward_cache_gate": "PASS",
        },
        "selection_search": {
            "compositions": int(candidate_count),
            "evaluation_rows_including_external_anchors": int(len(evaluation_weights)),
            "eligible_compositions": candidate_selection_count,
            "eligible_fraction": float(candidate_selection_count / candidate_count),
            "selection_role": config["selection_role"],
            "selection_lifecycle_births": int(
                config["input"]["selection_expected"]["births"]
            ),
            "selection_lifecycle_closes": int(
                config["input"]["selection_expected"]["closed_lifecycles"]
            ),
            "hard_mt5_equity_drawdown_pct": hard_dd,
            "uncertainty_reserve_percentage_points": selection_reserve,
        },
        "paired_full_forward": {
            "interval": {
                "start": paired_config["start"],
                "end": paired_config["end"],
            },
            "selection_eligible_candidates_evaluated": candidate_selection_count,
            "qualified_candidates": candidate_paired_count,
            "uncertainty_reserve_percentage_points": paired_reserve,
            "used_in_frozen_gate_and_ranking": True,
        },
        "development_june": {
            "interval": {
                "start": development_config["start"],
                "end": development_config["end"],
            },
            "full_pair_qualified_candidates_evaluated": candidate_paired_count,
            "development_qualified_candidates": candidate_june_count,
            "development_qualified_fraction_of_full_pair_eligible": float(
                candidate_june_count / max(1, candidate_paired_count)
            ),
            "used_in_frozen_ranking": True,
        },
        "development_july": {
            "interval": {
                "start": july_config["start"],
                "end": july_config["end"],
            },
            "june_qualified_candidates_evaluated": candidate_june_count,
            "final_qualified_candidates": int(len(final_indices)),
            "final_qualified_fraction_of_june_qualified": float(
                len(final_indices) / max(1, candidate_june_count)
            ),
            "used_in_frozen_gate_and_ranking": True,
        },
        "component_order": components,
        "calibration": {
            "rule": calibration["rule"],
            "piecewise_slopes": calibration_slopes,
            "selection_anchors": anchor_records,
            "paired_forward_rule": paired_calibration["rule"],
            "paired_forward_affine_slope": paired_slope,
            "paired_forward_affine_intercept": paired_intercept,
        },
        "selection_winner": selection_winner,
        "top_qualified": top_qualified,
        "proxy_holdout_remaining": False,
        "mt5_shortlist": (
            [
                {
                    "role": config["selection_role"]["id"],
                    "weights": selection_winner["weights"],
                    "selection_stressed_net_usd": selection_winner[
                        "stressed_net_usd"
                    ],
                    "selection_calibrated_drawdown_pct": selection_winner[
                        "calibrated_selection_mt5_drawdown_pct"
                    ],
                    "selection_budgeted_drawdown_pct": selection_winner[
                        "budgeted_selection_mt5_drawdown_pct"
                    ],
                    "paired_full_forward_stressed_net_usd": selection_winner[
                        "paired_full_forward"
                    ]["stressed_net_usd"],
                    "paired_full_forward_budgeted_drawdown_pct": selection_winner[
                        "paired_full_forward"
                    ]["budgeted_mt5_drawdown_pct"],
                    "development_june_stressed_net_usd": selection_winner[
                        "development_june"
                    ]["stressed_net_usd"],
                    "development_july_stressed_net_usd": selection_winner[
                        "development_july"
                    ]["stressed_net_usd"],
                    "development_july_raw_drawdown_pct": selection_winner[
                        "development_july"
                    ]["raw_closed_balance_drawdown_pct"],
                }
            ]
            if winner_index is not None
            else []
        ),
        "boundary": {
            "proxy_completed": True,
            "full_pair_june_and_july_used_as_predeclared_gates": True,
            "near_miss_anchor_rerun": False,
            "failed_candidate_rescue_or_retune": False,
            "mt5_launched": False,
            "maximum_mt5_shortlist_size": 1,
            "prior_15_combination_restart": False,
            "prior_mt5_candidate_restart": False,
            "live_runtime_modified": False,
            "lab_source_or_runtime_modified": False,
            "broker_positions_orders_deals_or_account_queried": False,
        },
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(rounded(result), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "output": str(OUTPUT_PATH), "wall_time_seconds": result["implementation"]["wall_time_seconds"]}))


if __name__ == "__main__":
    main()
