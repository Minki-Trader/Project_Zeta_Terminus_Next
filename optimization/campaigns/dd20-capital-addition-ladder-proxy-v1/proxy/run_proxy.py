from __future__ import annotations

import csv
import hashlib
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
    / "dd20-capital-addition-ladder-proxy-v1"
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
    if "actual_net_usd" in expected and "stressed_net_usd" in expected:
        actual = sum(event.actual_net_usd for event in closes)
        stressed = sum(event.stressed_net_usd for event in closes)
        if abs(actual - float(expected["actual_net_usd"])) > 1.0e-7:
            raise RuntimeError("declared actual net does not match copied input")
        if abs(stressed - float(expected["stressed_net_usd"])) > 1.0e-7:
            raise RuntimeError("declared stressed net does not match copied input")
    return events


def cache_double(path: Path, offset_hex: str) -> float:
    payload = path.read_bytes()
    offset = int(offset_hex, 16)
    if offset < 0 or offset + 8 > len(payload):
        raise RuntimeError("native cache statistic offset is outside the file")
    return float(struct.unpack_from("<d", payload, offset)[0])


def candidate_steps(config: dict[str, Any]) -> np.ndarray:
    values = np.asarray(config["capital_addition_step_grid_usd"], dtype=np.float64)
    if len(values) != int(config["expected_candidates"]):
        raise RuntimeError("capital ladder count does not match the contract")
    if len(np.unique(values)) != len(values) or np.any(values <= 0.0):
        raise RuntimeError("capital ladder steps must be unique and positive")
    baseline = float(config["baseline_addition_step_usd"])
    if np.any(np.isclose(values, baseline)):
        raise RuntimeError("baseline addition step appears in the candidate grid")
    return values


def add_anchor_step(steps: np.ndarray, anchor_step: float) -> tuple[np.ndarray, int]:
    matches = np.flatnonzero(np.isclose(steps, anchor_step))
    if len(matches) != 0:
        raise RuntimeError("closed anchor step appears in the candidate grid")
    return np.append(steps, anchor_step), len(steps)


def epoch_index(server_time: datetime, epochs: list[dict[str, Any]]) -> int | None:
    for index, epoch in enumerate(epochs):
        if epoch["start_time"] <= server_time < epoch["end_time"]:
            return index
    return None


def simulate(
    events: list[LifecycleEvent],
    weights: np.ndarray,
    addition_steps: np.ndarray,
    config: dict[str, Any],
    declared_epochs: list[dict[str, Any]],
) -> dict[str, np.ndarray]:
    candidate_count, component_count = weights.shape
    if len(addition_steps) != candidate_count:
        raise RuntimeError("addition-step and weight row counts differ")
    epoch_count = len(declared_epochs)
    reference = float(config["reference_capital_usd"])
    model = config["economic_execution_model"]
    base_volume = float(model["base_volume_lots"])
    volume_step = float(model["volume_step_lots"])
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
    day_multiplier = np.ones(candidate_count, dtype=np.int64)
    accepted_count = np.zeros(candidate_count, dtype=np.int32)
    aggregate_skip_count = np.zeros(candidate_count, dtype=np.int32)
    disabled_skip_count = np.zeros(candidate_count, dtype=np.int32)
    capital_skip_count = np.zeros(candidate_count, dtype=np.int32)
    maximum_day_multiplier = np.ones(candidate_count, dtype=np.int64)

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
                1 + np.floor(growth / addition_steps + 1.0e-9).astype(np.int64)
            )
            day_multiplier = np.maximum(1, day_multiplier)
            maximum_day_multiplier = np.maximum(maximum_day_multiplier, day_multiplier)
            current_day = event_day

        if event.event == "BIRTH":
            if event.position_identifier in open_positions:
                raise RuntimeError("duplicate open source position")
            component_weight = weights[:, event.component_index]
            if event.component_index == passive_component_index:
                source_base_steps = int(
                    np.floor(event.source_volume_lots / volume_step + 0.5)
                )
                if source_base_steps < 1:
                    raise RuntimeError("passive source reservation volume is invalid")
                base_steps = np.full(candidate_count, source_base_steps, dtype=np.int64)
            else:
                base_steps = day_multiplier
            target_steps = np.floor(
                base_steps.astype(np.float64) * component_weight + 0.5
            ).astype(np.int64)
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
            aggregate_skip_count += (enabled & capital_valid & ~admitted).astype(np.int32)
            accepted_count += admitted.astype(np.int32)
            admitted_risk = np.where(admitted, position_budget, 0.0)
            admitted_steps = np.where(admitted, target_steps, 0).astype(np.int64)
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
    if not (
        np.all(np.isfinite(actual_balance))
        and np.all(np.isfinite(stressed_balance))
        and np.all(np.isfinite(actual_max_dd))
        and np.all(np.isfinite(stressed_max_dd))
    ):
        raise RuntimeError("capital ladder produced non-finite economics")

    return {
        "actual_net": actual_balance - reference,
        "stressed_net": stressed_balance - reference,
        "raw_drawdown_pct": np.maximum(actual_max_dd, stressed_max_dd) * 100.0,
        "minimum_balance": np.minimum(actual_minimum, stressed_minimum),
        "accepted_count": accepted_count,
        "aggregate_skip_count": aggregate_skip_count,
        "disabled_skip_count": disabled_skip_count,
        "capital_skip_count": capital_skip_count,
        "maximum_day_multiplier": maximum_day_multiplier,
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


def record_for_index(
    index: int,
    steps: np.ndarray,
    weights: np.ndarray,
    metrics: dict[str, np.ndarray],
    calibrated_dd: np.ndarray | None,
    epochs: list[dict[str, Any]],
    components: list[str],
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "addition_step_usd": float(steps[index]),
        "weights": [float(value) for value in weights[index]],
        "actual_net_usd": float(metrics["actual_net"][index]),
        "stressed_net_usd": float(metrics["stressed_net"][index]),
        "raw_closed_balance_drawdown_pct": float(metrics["raw_drawdown_pct"][index]),
        "minimum_balance_usd": float(metrics["minimum_balance"][index]),
        "accepted_lifecycles": int(metrics["accepted_count"][index]),
        "aggregate_risk_skips": int(metrics["aggregate_skip_count"][index]),
        "disabled_component_skips": int(metrics["disabled_skip_count"][index]),
        "capital_skips": int(metrics["capital_skip_count"][index]),
        "maximum_day_multiplier": int(metrics["maximum_day_multiplier"][index]),
        "components": [],
    }
    if calibrated_dd is not None:
        record["calibrated_mt5_drawdown_pct"] = float(calibrated_dd[index])
    for component_index, component in enumerate(components):
        record["components"].append(
            {
                "component": component,
                "closed": int(metrics["component_closed"][index, component_index]),
                "actual_net_usd": float(metrics["component_actual"][index, component_index]),
                "stressed_net_usd": float(metrics["component_stressed"][index, component_index]),
            }
        )
    if epochs:
        record["epochs"] = []
        for epoch_position, epoch in enumerate(epochs):
            record["epochs"].append(
                {
                    "id": epoch["id"],
                    "actual_net_usd": float(metrics["epoch_actual_net"][index, epoch_position]),
                    "stressed_net_usd": float(metrics["epoch_stressed_net"][index, epoch_position]),
                    "raw_closed_balance_drawdown_pct": float(metrics["epoch_raw_drawdown_pct"][index, epoch_position]),
                    "minimum_balance_usd": float(metrics["epoch_minimum_balance"][index, epoch_position]),
                }
            )
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
    lifecycle_path = input_root / str(config["input"]["parent_lifecycle_file"])
    anchor = config["qualified_success_anchor"]
    cache_offsets = config["native_cache_offsets"]

    observed_selection_events = extract_segment(
        input_root / str(anchor["selection"]["lifecycle_file"]),
        0,
        anchor["selection"]["lifecycle_expected"],
        components,
    )
    selection_cache = input_root / str(anchor["selection"]["native_cache_file"])
    if (
        abs(
            cache_double(selection_cache, cache_offsets["total_net_profit"])
            - float(anchor["selection"]["lifecycle_expected"]["actual_net_usd"])
        )
        > 1.0e-9
        or abs(
            cache_double(selection_cache, cache_offsets["equity_drawdown_relative_pct"])
            - float(anchor["selection"]["observed_native_mt5_equity_drawdown_pct"])
        )
        > 1.0e-9
    ):
        raise RuntimeError("qualified selection native anchor mismatch")

    observed_forward_events = extract_segment(
        input_root / str(anchor["paired_forward"]["lifecycle_file"]),
        0,
        anchor["paired_forward"]["lifecycle_expected"],
        components,
    )
    forward_cache = input_root / str(anchor["paired_forward"]["native_cache_file"])
    if (
        abs(
            cache_double(forward_cache, cache_offsets["total_net_profit"])
            - float(anchor["paired_forward"]["lifecycle_expected"]["actual_net_usd"])
        )
        > 1.0e-9
        or abs(
            cache_double(forward_cache, cache_offsets["equity_drawdown_relative_pct"])
            - float(anchor["paired_forward"]["observed_native_mt5_equity_drawdown_pct"])
        )
        > 1.0e-9
    ):
        raise RuntimeError("qualified forward native anchor mismatch")

    steps = candidate_steps(config)
    candidate_count = len(steps)
    evaluation_steps, anchor_index = add_anchor_step(
        steps, float(config["baseline_addition_step_usd"])
    )
    fixed_weights = np.asarray(config["fixed_component_weights"], dtype=np.float64)
    if len(fixed_weights) != len(components):
        raise RuntimeError("fixed component weights do not match component count")
    evaluation_weights = np.tile(fixed_weights, (len(evaluation_steps), 1))

    epochs = [
        {
            "id": str(item["id"]),
            "start_time": datetime.strptime(item["start"], TIME_FORMAT),
            "end_time": datetime.strptime(item["end"], TIME_FORMAT),
        }
        for item in config["selection_epochs"]
    ]
    selection_events = extract_segment(
        lifecycle_path,
        int(config["input"]["selection_segment_index"]),
        config["input"]["selection_expected"],
        components,
    )
    selection = simulate(
        selection_events, evaluation_weights, evaluation_steps, config, epochs
    )
    for key, expected_key in (
        ("actual_net", "expected_proxy_actual_net_usd"),
        ("stressed_net", "expected_proxy_stressed_net_usd"),
        ("raw_drawdown_pct", "expected_proxy_raw_drawdown_pct"),
    ):
        if abs(float(selection[key][anchor_index]) - float(anchor["selection"][expected_key])) > 1.0e-7:
            raise RuntimeError("qualified selection proxy anchor mismatch")

    dd_calibration = config["selection_drawdown_calibration"]
    selection_gap = (
        float(anchor["selection"]["observed_native_mt5_equity_drawdown_pct"])
        - float(anchor["selection"]["expected_proxy_raw_drawdown_pct"])
    )
    if abs(selection_gap - float(dd_calibration["native_minus_raw_gap_percentage_points"])) > 1.0e-7:
        raise RuntimeError("qualified selection DD gap mismatch")
    calibrated_selection_dd = selection["raw_drawdown_pct"] + selection_gap
    budgeted_selection_dd = calibrated_selection_dd + float(
        dd_calibration["uncertainty_reserve_percentage_points"]
    )

    profit_calibration = config["selection_incremental_profit_calibration"]
    retention = float(profit_calibration["incremental_proxy_profit_retention_fraction"])
    profit_reserve = float(profit_calibration["uncertainty_reserve_usd"])
    anchor_proxy_actual = float(anchor["selection"]["expected_proxy_actual_net_usd"])
    anchor_proxy_stressed = float(anchor["selection"]["expected_proxy_stressed_net_usd"])
    anchor_observed_actual = float(anchor["selection"]["lifecycle_expected"]["actual_net_usd"])
    anchor_observed_stressed = float(anchor["selection"]["lifecycle_expected"]["stressed_net_usd"])
    conservative_selection_actual = (
        anchor_observed_actual
        + retention * (selection["actual_net"] - anchor_proxy_actual)
        - profit_reserve
    )
    conservative_selection_stressed = (
        anchor_observed_stressed
        + retention * (selection["stressed_net"] - anchor_proxy_stressed)
        - profit_reserve
    )
    positive_gate = (
        (selection["actual_net"] > 0.0)
        & (selection["stressed_net"] > 0.0)
        & (selection["minimum_balance"] > 0.0)
    )
    profit_gate = (
        (conservative_selection_actual > anchor_observed_actual)
        & (conservative_selection_stressed > anchor_observed_stressed)
    )
    dd_gate = budgeted_selection_dd <= float(
        dd_calibration["hard_native_mt5_equity_drawdown_pct"]
    ) + 1.0e-12
    epoch_gate = (
        np.all(selection["epoch_actual_net"] > 0.0, axis=1)
        & np.all(selection["epoch_stressed_net"] > 0.0, axis=1)
        & np.all(selection["epoch_minimum_balance"] > 0.0, axis=1)
        & np.all(
            selection["epoch_raw_drawdown_pct"]
            <= float(dd_calibration["hard_native_mt5_equity_drawdown_pct"])
            + 1.0e-12,
            axis=1,
        )
    )
    selection_eligible = positive_gate & profit_gate & dd_gate & epoch_gate
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
    paired = simulate(paired_events, evaluation_weights, evaluation_steps, config, [])
    for key, expected_key in (
        ("actual_net", "expected_proxy_actual_net_usd"),
        ("stressed_net", "expected_proxy_stressed_net_usd"),
        ("raw_drawdown_pct", "expected_proxy_raw_drawdown_pct"),
    ):
        if abs(float(paired[key][anchor_index]) - float(anchor["paired_forward"][expected_key])) > 1.0e-7:
            raise RuntimeError("qualified paired proxy anchor mismatch")
    paired_dd_calibration = config["paired_forward_drawdown_calibration"]
    paired_gap = (
        float(anchor["paired_forward"]["observed_native_mt5_equity_drawdown_pct"])
        - float(anchor["paired_forward"]["expected_proxy_raw_drawdown_pct"])
    )
    if abs(paired_gap - float(paired_dd_calibration["native_minus_raw_gap_percentage_points"])) > 1.0e-7:
        raise RuntimeError("qualified paired DD gap mismatch")
    calibrated_paired_dd = paired["raw_drawdown_pct"] + paired_gap
    budgeted_paired_dd = calibrated_paired_dd + float(
        paired_dd_calibration["uncertainty_reserve_percentage_points"]
    )
    paired_eligible = (
        selection_eligible
        & (paired["actual_net"] > 0.0)
        & (paired["stressed_net"] > 0.0)
        & (paired["minimum_balance"] > 0.0)
        & (
            budgeted_paired_dd
            <= float(paired_dd_calibration["hard_native_mt5_equity_drawdown_pct"])
            + 1.0e-12
        )
    )

    june_config = config["development_period"]
    june_events = extract_segment(
        lifecycle_path,
        int(config["input"]["later_segment_index"]),
        june_config["expected"],
        components,
        datetime.strptime(june_config["start"], TIME_FORMAT),
        datetime.strptime(june_config["end"], TIME_FORMAT),
    )
    june = simulate(june_events, evaluation_weights, evaluation_steps, config, [])
    june_eligible = (
        paired_eligible
        & (june["actual_net"] > 0.0)
        & (june["stressed_net"] > 0.0)
        & (june["minimum_balance"] > 0.0)
        & (june["raw_drawdown_pct"] <= 20.0 + 1.0e-12)
    )

    july_config = config["july_development_period"]
    july_start = datetime.strptime(july_config["start"], TIME_FORMAT)
    july_end = datetime.strptime(july_config["end"], TIME_FORMAT)
    july_events = extract_segment(
        lifecycle_path,
        int(config["input"]["later_segment_index"]),
        july_config["expected"],
        components,
        july_start,
        july_end,
    )
    july = simulate(july_events, evaluation_weights, evaluation_steps, config, [])
    july_anchor = anchor["continuous_july"]
    if (
        abs(float(july["actual_net"][anchor_index]) - float(july_anchor["expected_proxy_actual_net_usd"])) > 1.0e-7
        or abs(float(july["stressed_net"][anchor_index]) - float(july_anchor["expected_proxy_stressed_net_usd"])) > 1.0e-7
    ):
        raise RuntimeError("qualified independent July proxy anchor mismatch")
    observed_july_closes = [
        event
        for event in observed_forward_events
        if event.event == "CLOSE" and july_start <= event.server_time < july_end
    ]
    observed_july_actual = sum(event.actual_net_usd for event in observed_july_closes)
    observed_july_stressed = sum(event.stressed_net_usd for event in observed_july_closes)
    if (
        len(observed_july_closes) != int(july_anchor["observed_closes"])
        or abs(observed_july_actual - float(july_anchor["observed_actual_net_usd"])) > 1.0e-7
        or abs(observed_july_stressed - float(july_anchor["observed_stressed_net_usd"])) > 1.0e-7
    ):
        raise RuntimeError("qualified continuous July MT5 anchor mismatch")
    july_calibration = config["continuous_july_calibration"]
    july_actual_shortfall = float(july_anchor["expected_proxy_actual_net_usd"]) - observed_july_actual
    july_stressed_shortfall = float(july_anchor["expected_proxy_stressed_net_usd"]) - observed_july_stressed
    if (
        abs(july_actual_shortfall - float(july_calibration["proxy_minus_observed_actual_shortfall_usd"])) > 1.0e-7
        or abs(july_stressed_shortfall - float(july_calibration["proxy_minus_observed_stressed_shortfall_usd"])) > 1.0e-7
    ):
        raise RuntimeError("qualified continuous July shortfall mismatch")
    july_reserve = float(july_calibration["uncertainty_reserve_usd"])
    conservative_july_actual = july["actual_net"] - july_actual_shortfall - july_reserve
    conservative_july_stressed = july["stressed_net"] - july_stressed_shortfall - july_reserve
    raw_july_eligible = (
        june_eligible
        & (july["actual_net"] > 0.0)
        & (july["stressed_net"] > 0.0)
        & (july["minimum_balance"] > 0.0)
        & (july["raw_drawdown_pct"] <= 20.0 + 1.0e-12)
    )
    final_eligible = (
        raw_july_eligible
        & (conservative_july_actual > 0.0)
        & (conservative_july_stressed > 0.0)
    )
    final_eligible[candidate_count:] = False

    def complete_record(index: int) -> dict[str, Any]:
        record = record_for_index(
            index,
            evaluation_steps,
            evaluation_weights,
            selection,
            calibrated_selection_dd,
            epochs,
            components,
        )
        record["selection_dd_gap_percentage_points"] = selection_gap
        record["selection_dd_reserve_percentage_points"] = float(
            dd_calibration["uncertainty_reserve_percentage_points"]
        )
        record["budgeted_selection_mt5_drawdown_pct"] = float(
            budgeted_selection_dd[index]
        )
        record["conservative_selection_actual_net_usd"] = float(
            conservative_selection_actual[index]
        )
        record["conservative_selection_stressed_net_usd"] = float(
            conservative_selection_stressed[index]
        )
        record["selection_gates"] = {
            "positive": bool(positive_gate[index]),
            "conservative_profit_above_qualified": bool(profit_gate[index]),
            "budgeted_drawdown": bool(dd_gate[index]),
            "all_epochs": bool(epoch_gate[index]),
            "combined": bool(selection_eligible[index]),
        }
        record["paired_full_forward"] = record_for_index(
            index,
            evaluation_steps,
            evaluation_weights,
            paired,
            calibrated_paired_dd,
            [],
            components,
        )
        record["paired_full_forward"]["drawdown_gap_percentage_points"] = paired_gap
        record["paired_full_forward"]["budgeted_mt5_drawdown_pct"] = float(
            budgeted_paired_dd[index]
        )
        record["development_june"] = record_for_index(
            index, evaluation_steps, evaluation_weights, june, None, [], components
        )
        record["development_july"] = record_for_index(
            index, evaluation_steps, evaluation_weights, july, None, [], components
        )
        record["development_july"]["actual_shortfall_usd"] = july_actual_shortfall
        record["development_july"]["stressed_shortfall_usd"] = july_stressed_shortfall
        record["development_july"]["uncertainty_reserve_usd"] = july_reserve
        record["development_july"]["conservative_actual_net_usd"] = float(
            conservative_july_actual[index]
        )
        record["development_july"]["conservative_stressed_net_usd"] = float(
            conservative_july_stressed[index]
        )
        return record

    def final_rank_key(index: int) -> tuple[Any, ...]:
        weaker_month = min(
            float(june["stressed_net"][index]), float(july["stressed_net"][index])
        )
        return (
            -float(conservative_selection_stressed[index]),
            -float(conservative_selection_actual[index]),
            -float(selection["stressed_net"][index]),
            -float(selection["epoch_stressed_net"][index, -1]),
            -float(conservative_july_stressed[index]),
            -float(paired["stressed_net"][index]),
            -weaker_month,
            float(budgeted_selection_dd[index]),
            -float(evaluation_steps[index]),
        )

    final_indices = [int(value) for value in np.flatnonzero(final_eligible)]
    ranked = sorted(final_indices, key=final_rank_key)
    winner_index = ranked[0] if ranked else None
    diagnostic_indices = sorted(
        range(candidate_count),
        key=lambda index: (
            -float(conservative_selection_stressed[index]),
            -float(conservative_selection_actual[index]),
            float(budgeted_selection_dd[index]),
            -float(evaluation_steps[index]),
        ),
    )
    dd_diagnostic_indices = sorted(
        [index for index in range(candidate_count) if bool(dd_gate[index])],
        key=lambda index: (
            -float(conservative_selection_stressed[index]),
            -float(conservative_selection_actual[index]),
            -float(evaluation_steps[index]),
        ),
    )
    top_count = int(config["output_top_selection_records"])
    winner = complete_record(winner_index) if winner_index is not None else None
    top_qualified = [complete_record(index) for index in ranked[:top_count]]
    top_selection_diagnostic = [
        complete_record(index) for index in diagnostic_indices[:top_count]
    ]
    top_dd_eligible_diagnostic = [
        complete_record(index) for index in dd_diagnostic_indices[:top_count]
    ]

    if int(np.count_nonzero(selection_eligible[:candidate_count])) == 0:
        status = "VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE"
    elif int(np.count_nonzero(paired_eligible[:candidate_count])) == 0:
        status = "VALID_PROXY_COMPLETE_NO_FULL_PAIRED_FORWARD_ELIGIBLE"
    elif int(np.count_nonzero(june_eligible[:candidate_count])) == 0:
        status = "VALID_PROXY_COMPLETE_NO_JUNE_STABLE_CANDIDATE"
    elif int(np.count_nonzero(raw_july_eligible[:candidate_count])) == 0:
        status = "VALID_PROXY_COMPLETE_NO_RAW_JULY_STABLE_CANDIDATE"
    elif winner_index is None:
        status = "VALID_PROXY_COMPLETE_NO_CONSERVATIVE_JULY_STABLE_CANDIDATE"
    else:
        status = "VALID_PROXY_COMPLETE_ONE_MT5_SHORTLIST"

    result = {
        "schema": "zeta-dd20-capital-addition-ladder-proxy-raw-result-v1",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "campaign": config["campaign"],
        "implementation": {
            "contract_sha256": sha256(CONFIG_PATH),
            "script_sha256": sha256(SCRIPT_PATH),
            "input_manifest_sha256": config["input"]["canonical_manifest_sha256"],
            "wall_time_seconds": time.perf_counter() - started,
            "qualified_selection_lifecycle_and_native_anchor_gate": "PASS",
            "qualified_forward_lifecycle_and_native_anchor_gate": "PASS",
            "qualified_selection_proxy_anchor_gate": "PASS",
            "qualified_paired_proxy_anchor_gate": "PASS",
            "qualified_continuous_july_anchor_gate": "PASS",
        },
        "search": {
            "candidate_steps": candidate_count,
            "evaluation_rows_including_closed_anchor": int(len(evaluation_steps)),
            "fixed_component_weights": [float(value) for value in fixed_weights],
            "closed_anchor_addition_step_usd": float(config["baseline_addition_step_usd"]),
            "closed_anchor_in_candidate_grid": False,
            "selection_individual_gate_counts": {
                "positive": int(np.count_nonzero(positive_gate[:candidate_count])),
                "conservative_profit_above_qualified": int(np.count_nonzero(profit_gate[:candidate_count])),
                "budgeted_drawdown": int(np.count_nonzero(dd_gate[:candidate_count])),
                "all_epochs": int(np.count_nonzero(epoch_gate[:candidate_count])),
                "combined": int(np.count_nonzero(selection_eligible[:candidate_count])),
            },
            "paired_qualified": int(np.count_nonzero(paired_eligible[:candidate_count])),
            "june_qualified": int(np.count_nonzero(june_eligible[:candidate_count])),
            "raw_july_qualified": int(np.count_nonzero(raw_july_eligible[:candidate_count])),
            "final_qualified": int(len(final_indices)),
            "selection_role": config["selection_role"],
        },
        "calibration": {
            "selection_native_minus_raw_gap_percentage_points": selection_gap,
            "selection_drawdown_uncertainty_reserve_percentage_points": float(dd_calibration["uncertainty_reserve_percentage_points"]),
            "incremental_profit_retention_fraction": retention,
            "selection_profit_uncertainty_reserve_usd": profit_reserve,
            "paired_native_minus_raw_gap_percentage_points": paired_gap,
            "paired_drawdown_uncertainty_reserve_percentage_points": float(paired_dd_calibration["uncertainty_reserve_percentage_points"]),
            "continuous_july_actual_shortfall_usd": july_actual_shortfall,
            "continuous_july_stressed_shortfall_usd": july_stressed_shortfall,
            "continuous_july_uncertainty_reserve_usd": july_reserve,
        },
        "closed_qualified_anchor": complete_record(anchor_index),
        "selection_winner": winner,
        "top_qualified": top_qualified,
        "top_selection_diagnostic": top_selection_diagnostic,
        "top_dd_eligible_diagnostic": top_dd_eligible_diagnostic,
        "mt5_shortlist": (
            [
                {
                    "role": config["selection_role"]["id"],
                    "addition_step_usd": winner["addition_step_usd"],
                    "weights": winner["weights"],
                    "selection_actual_net_usd": winner["actual_net_usd"],
                    "selection_stressed_net_usd": winner["stressed_net_usd"],
                    "conservative_selection_actual_net_usd": winner["conservative_selection_actual_net_usd"],
                    "conservative_selection_stressed_net_usd": winner["conservative_selection_stressed_net_usd"],
                    "selection_budgeted_drawdown_pct": winner["budgeted_selection_mt5_drawdown_pct"],
                    "paired_stressed_net_usd": winner["paired_full_forward"]["stressed_net_usd"],
                    "june_stressed_net_usd": winner["development_june"]["stressed_net_usd"],
                    "july_conservative_stressed_net_usd": winner["development_july"]["conservative_stressed_net_usd"],
                }
            ]
            if winner is not None
            else []
        ),
        "boundary": {
            "proxy_completed": True,
            "closed_qualified_anchor_rerun": False,
            "closed_static_weight_grid_rerun": False,
            "failed_candidate_rescue_or_retune": False,
            "mt5_launched": False,
            "maximum_mt5_shortlist_size": 1,
            "prior_15_combination_restart": False,
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
    print(
        json.dumps(
            {
                "status": status,
                "output": str(OUTPUT_PATH),
                "wall_time_seconds": result["implementation"]["wall_time_seconds"],
            }
        )
    )


if __name__ == "__main__":
    main()
