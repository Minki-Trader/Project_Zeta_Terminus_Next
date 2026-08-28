from __future__ import annotations

import csv
import hashlib
import itertools
import json
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
    / "dd20-executable-volume-lattice-proxy-v1"
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
            component = source["component_id"]
            if component not in component_index:
                raise RuntimeError("segment contains an undeclared component")
            events.append(
                LifecycleEvent(
                    server_time=datetime.strptime(source["server_time"], TIME_FORMAT),
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
    actual = sum(event.actual_net_usd for event in closes)
    stressed = sum(event.stressed_net_usd for event in closes)
    if abs(actual - float(expected["actual_net_usd"])) > 1.0e-7:
        raise RuntimeError("declared actual net does not match copied input")
    if abs(stressed - float(expected["stressed_net_usd"])) > 1.0e-7:
        raise RuntimeError("declared stressed net does not match copied input")
    return events


def candidate_weights(config: dict[str, Any]) -> np.ndarray:
    grid = [float(value) for value in config["weight_grid"]]
    component_count = len(config["components"])
    minimum_active = int(config["minimum_active_components"])
    rows = [
        values
        for values in itertools.product(grid, repeat=component_count)
        if sum(value > 0.0 for value in values) >= minimum_active
    ]
    weights = np.asarray(rows, dtype=np.float64)
    if len(weights) != int(config["expected_compositions"]):
        raise RuntimeError("candidate lattice count does not match the contract")
    return weights


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
            requested_steps = day_multiplier.astype(np.float64) * component_weight
            target_steps = np.floor(requested_steps + 0.5).astype(np.int32)
            executable_multiplier = target_steps / day_multiplier.astype(np.float64)
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
    selection = simulate(selection_events, weights, config, epochs)

    calibration = config["selection_mt5_drawdown_calibration"]
    base_index = find_weight_index(weights, calibration["base_anchor"]["weights"])
    high_index = find_weight_index(
        weights, calibration["high_exposure_anchor"]["weights"]
    )
    base_raw_dd = float(selection["raw_drawdown_pct"][base_index])
    high_raw_dd = float(selection["raw_drawdown_pct"][high_index])
    base_observed_dd = float(
        calibration["base_anchor"]["observed_mt5_equity_drawdown_relative_pct"]
    )
    high_observed_dd = float(
        calibration["high_exposure_anchor"][
            "observed_mt5_equity_drawdown_relative_pct"
        ]
    )
    if high_raw_dd <= base_raw_dd + 1.0e-12:
        raise RuntimeError("selection DD anchors do not define an increasing line")
    calibration_slope = (high_observed_dd - base_observed_dd) / (
        high_raw_dd - base_raw_dd
    )
    calibration_intercept = base_observed_dd - calibration_slope * base_raw_dd
    affine_dd = calibration_slope * selection["raw_drawdown_pct"] + calibration_intercept
    calibrated_dd = np.maximum(selection["raw_drawdown_pct"], affine_dd)

    hard_dd = float(config["hard_selection_calibrated_drawdown_pct"])
    eligible = (
        (selection["actual_net"] > 0.0)
        & (selection["stressed_net"] > 0.0)
        & (selection["minimum_balance"] > 0.0)
        & (calibrated_dd <= hard_dd + 1.0e-12)
        & np.all(selection["epoch_actual_net"] > 0.0, axis=1)
        & np.all(selection["epoch_stressed_net"] > 0.0, axis=1)
        & np.all(selection["epoch_minimum_balance"] > 0.0, axis=1)
        & np.all(selection["epoch_raw_drawdown_pct"] <= hard_dd + 1.0e-12, axis=1)
    )
    eligible_indices = np.flatnonzero(eligible)

    def rank_key(index: int) -> tuple[Any, ...]:
        return (
            -float(selection["stressed_net"][index]),
            -float(selection["actual_net"][index]),
            -float(selection["epoch_stressed_net"][index, -1]),
            float(calibrated_dd[index]),
            tuple(float(value) for value in weights[index]),
        )

    ranked = sorted((int(index) for index in eligible_indices), key=rank_key)
    winner_index = ranked[0] if ranked else None
    top_count = int(config["output_top_selection_records"])
    top_selection = [
        record_for_index(
            index, weights, selection, calibrated_dd, epochs, components
        )
        for index in ranked[:top_count]
    ]

    later_record = None
    later_confirmation_passed = False
    selection_winner = None
    if winner_index is not None:
        selection_winner = record_for_index(
            winner_index, weights, selection, calibrated_dd, epochs, components
        )
        later_events = extract_segment(
            lifecycle_path,
            int(config["input"]["later_segment_index"]),
            config["input"]["later_expected"],
            components,
        )
        winner_weights = weights[winner_index : winner_index + 1]
        later = simulate(later_events, winner_weights, config, [])
        later_record = record_for_index(
            0, winner_weights, later, None, [], components
        )
        later_confirmation_passed = bool(
            later["actual_net"][0] > 0.0
            and later["stressed_net"][0] > 0.0
            and later["minimum_balance"][0] > 0.0
            and later["raw_drawdown_pct"][0] <= 20.0 + 1.0e-12
        )

    base_record = record_for_index(
        base_index, weights, selection, calibrated_dd, epochs, components
    )
    high_record = record_for_index(
        high_index, weights, selection, calibrated_dd, epochs, components
    )
    high_anchor = calibration["high_exposure_anchor"]
    high_record["observed_mt5"] = {
        "actual_net_usd": float(high_anchor["observed_actual_net_usd"]),
        "stressed_net_usd": float(high_anchor["observed_stressed_net_usd"]),
        "equity_drawdown_relative_pct": high_observed_dd,
        "closed_lifecycles": int(high_anchor["observed_closed_lifecycles"]),
        "risk_admission_skips": int(high_anchor["observed_risk_admission_skips"]),
    }
    base_anchor = calibration["base_anchor"]
    base_record["observed_mt5"] = {
        "actual_net_usd": float(base_anchor["observed_actual_net_usd"]),
        "stressed_net_usd": float(base_anchor["observed_stressed_net_usd"]),
        "equity_drawdown_relative_pct": base_observed_dd,
        "closed_lifecycles": int(base_anchor["observed_closed_lifecycles"]),
    }

    if winner_index is None:
        status = "VALID_PROXY_COMPLETE_NO_SELECTION_CANDIDATE"
    elif later_confirmation_passed:
        status = "VALID_PROXY_COMPLETE_ONE_MT5_SHORTLIST"
    else:
        status = "VALID_PROXY_COMPLETE_SELECTION_WINNER_FAILS_LATER_NO_MT5_SHORTLIST"

    result = {
        "schema": "zeta-dd20-executable-volume-lattice-proxy-raw-result-v1",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "campaign": config["campaign"],
        "implementation": {
            "contract_sha256": sha256(CONFIG_PATH),
            "script_sha256": sha256(SCRIPT_PATH),
            "input_manifest_sha256": config["input"]["canonical_manifest_sha256"],
            "wall_time_seconds": time.perf_counter() - started,
        },
        "selection_search": {
            "compositions": int(len(weights)),
            "eligible_compositions": int(len(eligible_indices)),
            "eligible_fraction": float(len(eligible_indices) / len(weights)),
            "selection_role": config["selection_role"],
            "selection_role_frozen_before_later_opened": True,
            "known_later_used_in_ranking_or_weight_tuning": False,
            "selection_lifecycle_births": int(
                config["input"]["selection_expected"]["births"]
            ),
            "selection_lifecycle_closes": int(
                config["input"]["selection_expected"]["closed_lifecycles"]
            ),
            "hard_calibrated_drawdown_pct": hard_dd,
        },
        "component_order": components,
        "calibration": {
            "rule": calibration["rule"],
            "affine_slope": calibration_slope,
            "affine_intercept": calibration_intercept,
            "base_anchor": base_record,
            "high_exposure_anchor": high_record,
        },
        "selection_winner": selection_winner,
        "top_selection": top_selection,
        "later_confirmation": later_record,
        "later_confirmation_passed": later_confirmation_passed,
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
                    "later_stressed_net_usd": later_record["stressed_net_usd"],
                    "later_raw_drawdown_pct": later_record[
                        "raw_closed_balance_drawdown_pct"
                    ],
                }
            ]
            if later_confirmation_passed
            else []
        ),
        "boundary": {
            "proxy_completed": True,
            "later_failed_candidate_rescue_or_retune": False,
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
    print(json.dumps({"status": status, "output": str(OUTPUT_PATH), "wall_time_seconds": result["implementation"]["wall_time_seconds"]}))


if __name__ == "__main__":
    main()
