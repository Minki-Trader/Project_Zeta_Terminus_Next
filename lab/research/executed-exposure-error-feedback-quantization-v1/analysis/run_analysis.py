from __future__ import annotations

import csv
import hashlib
import json
import math
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
FAMILY_ROOT = SCRIPT_PATH.parents[1]
REPOSITORY_ROOT = SCRIPT_PATH.parents[4]
DECLARATION_PATH = (
    FAMILY_ROOT
    / "evidence"
    / "EXECUTED_EXPOSURE_ERROR_FEEDBACK_QUANTIZATION_DECLARATION_V1.json"
)
OUTPUT_PATH = (
    REPOSITORY_ROOT
    / "lab"
    / "artifacts"
    / "raw"
    / "executed-exposure-error-feedback-quantization-v1"
    / "output"
    / "formal-result.json"
)
TIME_FORMAT = "%Y.%m.%d %H:%M:%S"
EPSILON = 1.0e-9


@dataclass(frozen=True)
class LifecycleEvent:
    server_time: datetime
    event: str
    component_id: str
    position_identifier: str
    source_volume_lots: float
    actual_net_usd: float
    stressed_net_usd: float


@dataclass(frozen=True)
class OpenPosition:
    component_id: str
    admitted_risk_usd: float
    admitted_steps: int
    source_volume_lots: float


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_contract() -> dict[str, Any]:
    contract = json.loads(DECLARATION_PATH.read_text(encoding="utf-8"))
    pin = contract["immutable_inputs"]["lab_owned_lifecycle_copy"]
    input_path = REPOSITORY_ROOT / str(pin["path"])
    if input_path.stat().st_size != int(pin["bytes"]):
        raise RuntimeError("Lab-owned input byte count mismatch")
    if sha256(input_path) != str(pin["sha256"]):
        raise RuntimeError("Lab-owned input hash mismatch")
    return contract


def extract_segment(
    path: Path,
    target_segment: int,
    expected_births: int,
    expected_closes: int,
    component_ids: set[str],
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[LifecycleEvent]:
    events: list[LifecycleEvent] = []
    segment = 0
    previous_sequence: int | None = None
    previous_time: datetime | None = None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for source in csv.DictReader(handle):
            sequence = int(source["research_state_sequence"])
            if previous_sequence is not None and sequence < previous_sequence:
                segment += 1
                previous_time = None
            previous_sequence = sequence
            if segment > target_segment:
                break
            if segment != target_segment or source["event"] not in {"BIRTH", "CLOSE"}:
                continue
            server_time = datetime.strptime(source["server_time"], TIME_FORMAT)
            if end is not None and server_time >= end:
                break
            if start is not None and server_time < start:
                continue
            if previous_time is not None and server_time < previous_time:
                raise RuntimeError("selected lifecycle events are not time ordered")
            previous_time = server_time
            component_id = source["component_id"]
            if component_id not in component_ids:
                raise RuntimeError("undeclared component in lifecycle input")
            events.append(
                LifecycleEvent(
                    server_time=server_time,
                    event=source["event"],
                    component_id=component_id,
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
    if len(births) != expected_births or len(closes) != expected_closes:
        raise RuntimeError("segment lifecycle density mismatch")
    if len(set(birth_ids)) != len(birth_ids) or set(birth_ids) != set(close_ids):
        raise RuntimeError("segment BIRTH/CLOSE identity mismatch")
    if any(event.source_volume_lots <= 0.0 for event in births):
        raise RuntimeError("source birth volume must be positive")
    return events


def round_positive_steps(requested_steps: float) -> int:
    if requested_steps < -EPSILON or not math.isfinite(requested_steps):
        raise RuntimeError("invalid positive step request")
    return int(math.floor(max(0.0, requested_steps) + 0.5 + 1.0e-12))


def drawdown(increments: list[float], reference: float) -> tuple[float, float]:
    balance = reference
    peak = reference
    maximum = 0.0
    minimum = reference
    for increment in increments:
        balance += increment
        peak = max(peak, balance)
        minimum = min(minimum, balance)
        maximum = max(maximum, (peak - balance) / peak if peak > 0.0 else math.inf)
    return maximum * 100.0, minimum


def profit_factor(increments: list[float]) -> float | None:
    gross_profit = sum(value for value in increments if value > 0.0)
    gross_loss = -sum(value for value in increments if value < 0.0)
    if gross_loss <= EPSILON:
        return None
    return gross_profit / gross_loss


def epoch_for_time(server_time: datetime, epochs: list[dict[str, Any]]) -> str | None:
    for epoch in epochs:
        start = datetime.strptime(str(epoch["start"]), TIME_FORMAT)
        end = datetime.strptime(str(epoch["end"]), TIME_FORMAT)
        if start <= server_time < end:
            return str(epoch["id"])
    return None


def simulate(
    events: list[LifecycleEvent],
    contract: dict[str, Any],
    policy: str,
    weights_override: dict[str, float] | None = None,
    epochs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    fixed = contract["fixed_execution_contract"]
    reference = float(fixed["reference_capital_usd"])
    volume_step = float(fixed["volume_step_lots"])
    addition_step = float(fixed["addition_step_usd"])
    position_fraction = float(fixed["position_risk_fraction"])
    aggregate_fraction = float(fixed["aggregate_risk_fraction"])
    aggregate_tolerance = float(fixed["aggregate_tolerance_usd"])
    components = contract["components"]
    component_ids = [str(component["id"]) for component in components]
    weights = {
        str(component["id"]): float(component["weight"]) for component in components
    }
    if weights_override is not None:
        weights = dict(weights_override)
    passive_id = "ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8"
    epochs = epochs or []

    actual_balance = reference
    stressed_balance = reference
    open_risk = 0.0
    current_day = None
    day_multiplier = 1
    maximum_day_multiplier = 1
    residual = {component_id: 0.0 for component_id in component_ids}
    maximum_absolute_residual = {component_id: 0.0 for component_id in component_ids}
    committed_ideal_steps = {component_id: 0.0 for component_id in component_ids}
    committed_executed_steps = {component_id: 0 for component_id in component_ids}
    birth_decisions: dict[str, dict[str, Any]] = {}
    open_positions: dict[str, OpenPosition] = {}
    actual_increments: list[float] = []
    stressed_increments: list[float] = []
    accepted = 0
    aggregate_skips = 0
    disabled_skips = 0
    capital_skips = 0

    component_metrics = {
        component_id: {
            "name": str(components[index]["name"]),
            "births": 0,
            "accepted": 0,
            "aggregate_skips": 0,
            "executed_steps": 0,
            "actual": 0.0,
            "stressed": 0.0,
            "actual_increments": [],
            "stressed_increments": [],
        }
        for index, component_id in enumerate(component_ids)
    }
    epoch_metrics = {
        str(epoch["id"]): {"actual": 0.0, "stressed": 0.0, "closes": 0}
        for epoch in epochs
    }

    for event in events:
        event_day = event.server_time.date()
        if event_day != current_day:
            growth = max(0.0, stressed_balance - reference)
            day_multiplier = 1 + math.floor(growth / addition_step + 1.0e-9)
            day_multiplier = max(1, day_multiplier)
            maximum_day_multiplier = max(maximum_day_multiplier, day_multiplier)
            current_day = event_day

        if event.event == "BIRTH":
            if event.position_identifier in open_positions:
                raise RuntimeError("duplicate open source position")
            metric = component_metrics[event.component_id]
            metric["births"] += 1
            weight = weights[event.component_id]
            if event.component_id == passive_id:
                raw_source_steps = event.source_volume_lots / volume_step
                base_steps = round_positive_steps(raw_source_steps)
                if base_steps < 1 or abs(raw_source_steps - base_steps) > EPSILON:
                    raise RuntimeError("passive source volume is not an exact lot step")
            else:
                base_steps = day_multiplier
            desired_steps = base_steps * weight
            prior_residual = residual[event.component_id]
            adjusted_steps = desired_steps
            if policy == "ADMITTED_COMPONENT_ERROR_FEEDBACK":
                adjusted_steps += prior_residual
            elif policy != "INDEPENDENT_POSITIVE_MATHROUND":
                raise RuntimeError("unknown quantization policy")
            target_steps = round_positive_steps(adjusted_steps)
            tentative_residual = adjusted_steps - target_steps
            executable_multiplier = target_steps / base_steps if base_steps > 0 else 0.0
            conservative_capital = min(actual_balance, stressed_balance)
            position_budget = (
                conservative_capital * position_fraction * executable_multiplier
            )
            aggregate_budget = conservative_capital * aggregate_fraction
            enabled = target_steps > 0
            capital_valid = conservative_capital > 0.0
            admitted = bool(
                enabled
                and capital_valid
                and open_risk + position_budget
                <= aggregate_budget + aggregate_tolerance + EPSILON
            )
            if not enabled:
                disabled_skips += 1
            elif not capital_valid:
                capital_skips += 1
            elif not admitted:
                aggregate_skips += 1
                metric["aggregate_skips"] += 1
            if admitted:
                accepted += 1
                metric["accepted"] += 1
                metric["executed_steps"] += target_steps
                committed_ideal_steps[event.component_id] += desired_steps
                committed_executed_steps[event.component_id] += target_steps
                open_risk += position_budget
                if policy == "ADMITTED_COMPONENT_ERROR_FEEDBACK":
                    residual[event.component_id] = tentative_residual
                    maximum_absolute_residual[event.component_id] = max(
                        maximum_absolute_residual[event.component_id],
                        abs(tentative_residual),
                    )
            admitted_risk = position_budget if admitted else 0.0
            admitted_steps = target_steps if admitted else 0
            birth_decisions[event.position_identifier] = {
                "component_id": event.component_id,
                "base_steps": base_steps,
                "desired_steps": desired_steps,
                "target_steps": target_steps,
                "admitted": admitted,
                "prior_residual_steps": prior_residual,
                "committed_residual_steps": residual[event.component_id],
            }
            open_positions[event.position_identifier] = OpenPosition(
                component_id=event.component_id,
                admitted_risk_usd=admitted_risk,
                admitted_steps=admitted_steps,
                source_volume_lots=event.source_volume_lots,
            )
            continue

        if event.position_identifier not in open_positions:
            raise RuntimeError("source close has no matching birth")
        opened = open_positions.pop(event.position_identifier)
        if opened.component_id != event.component_id:
            raise RuntimeError("source lifecycle component mismatch")
        scale = opened.admitted_steps * volume_step / opened.source_volume_lots
        actual_increment = event.actual_net_usd * scale
        stressed_increment = event.stressed_net_usd * scale
        actual_balance += actual_increment
        stressed_balance += stressed_increment
        open_risk = max(0.0, open_risk - opened.admitted_risk_usd)
        actual_increments.append(actual_increment)
        stressed_increments.append(stressed_increment)
        metric = component_metrics[event.component_id]
        metric["actual"] += actual_increment
        metric["stressed"] += stressed_increment
        metric["actual_increments"].append(actual_increment)
        metric["stressed_increments"].append(stressed_increment)
        epoch_id = epoch_for_time(event.server_time, epochs)
        if epoch_id is not None:
            epoch_metrics[epoch_id]["actual"] += actual_increment
            epoch_metrics[epoch_id]["stressed"] += stressed_increment
            epoch_metrics[epoch_id]["closes"] += int(opened.admitted_steps > 0)

    if open_positions:
        raise RuntimeError("segment ended with open source positions")
    actual_dd, minimum_actual = drawdown(actual_increments, reference)
    stressed_dd, minimum_stressed = drawdown(stressed_increments, reference)
    raw_dd = max(actual_dd, stressed_dd)
    component_rows = []
    for component_id in component_ids:
        metric = component_metrics[component_id]
        component_rows.append(
            {
                "component_id": component_id,
                "name": metric["name"],
                "births": metric["births"],
                "accepted": metric["accepted"],
                "aggregate_skips": metric["aggregate_skips"],
                "executed_steps": metric["executed_steps"],
                "actual_net_usd": metric["actual"],
                "stressed_net_usd": metric["stressed"],
                "actual_profit_factor": profit_factor(metric["actual_increments"]),
                "stressed_profit_factor": profit_factor(metric["stressed_increments"]),
                "final_residual_steps": residual[component_id],
                "maximum_absolute_residual_steps": maximum_absolute_residual[
                    component_id
                ],
                "committed_ideal_steps": committed_ideal_steps[component_id],
                "committed_executed_steps": committed_executed_steps[component_id],
                "cumulative_executed_minus_ideal_steps": committed_executed_steps[
                    component_id
                ]
                - committed_ideal_steps[component_id],
            }
        )
    return {
        "policy": policy,
        "actual_net_usd": actual_balance - reference,
        "stressed_net_usd": stressed_balance - reference,
        "actual_profit_factor": profit_factor(actual_increments),
        "stressed_profit_factor": profit_factor(stressed_increments),
        "actual_raw_closed_drawdown_pct": actual_dd,
        "stressed_raw_closed_drawdown_pct": stressed_dd,
        "raw_closed_drawdown_pct": raw_dd,
        "minimum_actual_balance_usd": minimum_actual,
        "minimum_stressed_balance_usd": minimum_stressed,
        "stressed_net_per_drawdown_point": (
            (stressed_balance - reference) / raw_dd if raw_dd > EPSILON else None
        ),
        "accepted_lifecycles": accepted,
        "aggregate_risk_skips": aggregate_skips,
        "disabled_component_skips": disabled_skips,
        "capital_skips": capital_skips,
        "maximum_day_multiplier": maximum_day_multiplier,
        "components": component_rows,
        "epochs": [
            {"id": epoch_id, **values} for epoch_id, values in epoch_metrics.items()
        ],
        "birth_decisions": birth_decisions,
    }


def verify_source_reproduction(
    events: list[LifecycleEvent],
    contract: dict[str, Any],
    segment: dict[str, Any],
) -> dict[str, Any]:
    all_one = {str(component["id"]): 1.0 for component in contract["components"]}
    result = simulate(
        events,
        contract,
        "INDEPENDENT_POSITIVE_MATHROUND",
        weights_override=all_one,
        epochs=segment.get("epochs", []),
    )
    close_actual = sum(
        event.actual_net_usd for event in events if event.event == "CLOSE"
    )
    close_stressed = sum(
        event.stressed_net_usd for event in events if event.event == "CLOSE"
    )
    if abs(result["actual_net_usd"] - close_actual) > 1.0e-7:
        raise RuntimeError("all-ones actual source reproduction failed")
    if abs(result["stressed_net_usd"] - close_stressed) > 1.0e-7:
        raise RuntimeError("all-ones stressed source reproduction failed")
    if result["accepted_lifecycles"] != int(segment["expected_closes"]):
        raise RuntimeError("all-ones source close count reproduction failed")
    if "source_actual_net_usd" in segment and abs(
        close_actual - float(segment["source_actual_net_usd"])
    ) > 1.0e-7:
        raise RuntimeError("declared source actual anchor mismatch")
    if "source_stressed_net_usd" in segment and abs(
        close_stressed - float(segment["source_stressed_net_usd"])
    ) > 1.0e-7:
        raise RuntimeError("declared source stressed anchor mismatch")
    result.pop("birth_decisions")
    return result


def verify_control_anchor(result: dict[str, Any], anchor: dict[str, Any]) -> None:
    numeric_keys = [
        "actual_net_usd",
        "stressed_net_usd",
        "raw_closed_drawdown_pct",
    ]
    integer_keys = [
        "accepted_lifecycles",
        "aggregate_risk_skips",
        "disabled_component_skips",
    ]
    for key in numeric_keys:
        if abs(float(result[key]) - float(anchor[key])) > 1.0e-7:
            raise RuntimeError(f"fixed control numeric anchor mismatch: {key}")
    for key in integer_keys:
        if int(result[key]) != int(anchor[key]):
            raise RuntimeError(f"fixed control count anchor mismatch: {key}")


def policy_comparison(control: dict[str, Any], treatment: dict[str, Any]) -> dict[str, Any]:
    control_decisions = control["birth_decisions"]
    treatment_decisions = treatment["birth_decisions"]
    if control_decisions.keys() != treatment_decisions.keys():
        raise RuntimeError("policy decision universes differ")
    joint = 0
    changed_joint_volume = 0
    control_only = 0
    treatment_only = 0
    component_changed: dict[str, int] = {}
    for position_identifier, control_decision in control_decisions.items():
        treatment_decision = treatment_decisions[position_identifier]
        component_id = str(control_decision["component_id"])
        component_changed.setdefault(component_id, 0)
        if control_decision["admitted"] and treatment_decision["admitted"]:
            joint += 1
            if int(control_decision["target_steps"]) != int(
                treatment_decision["target_steps"]
            ):
                changed_joint_volume += 1
                component_changed[component_id] += 1
        elif control_decision["admitted"]:
            control_only += 1
        elif treatment_decision["admitted"]:
            treatment_only += 1
    return {
        "joint_admitted_lifecycles": joint,
        "changed_joint_volume_lifecycles": changed_joint_volume,
        "changed_joint_admission_fraction": (
            changed_joint_volume / joint if joint else 0.0
        ),
        "control_only_admitted_lifecycles": control_only,
        "treatment_only_admitted_lifecycles": treatment_only,
        "components_with_changed_joint_volume": sum(
            count > 0 for count in component_changed.values()
        ),
        "changed_joint_volume_by_component": component_changed,
        "treatment_minus_control_actual_usd": treatment["actual_net_usd"]
        - control["actual_net_usd"],
        "treatment_minus_control_stressed_usd": treatment["stressed_net_usd"]
        - control["stressed_net_usd"],
        "treatment_stressed_net_retention": (
            treatment["stressed_net_usd"] / control["stressed_net_usd"]
            if control["stressed_net_usd"] > EPSILON
            else None
        ),
        "raw_drawdown_improvement_percentage_points": control[
            "raw_closed_drawdown_pct"
        ]
        - treatment["raw_closed_drawdown_pct"],
        "treatment_to_control_stressed_net_per_drawdown_ratio": (
            treatment["stressed_net_per_drawdown_point"]
            / control["stressed_net_per_drawdown_point"]
            if treatment["stressed_net_per_drawdown_point"] is not None
            and control["stressed_net_per_drawdown_point"] is not None
            and control["stressed_net_per_drawdown_point"] > EPSILON
            else None
        ),
        "accepted_lifecycle_delta": treatment["accepted_lifecycles"]
        - control["accepted_lifecycles"],
        "aggregate_skip_delta": treatment["aggregate_risk_skips"]
        - control["aggregate_risk_skips"],
    }


def strip_decisions(result: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(result)
    cleaned.pop("birth_decisions", None)
    return cleaned


def rounded(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 10)
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [rounded(item) for item in value]
    return value


def main() -> None:
    started = time.perf_counter()
    contract = load_contract()
    input_pin = contract["immutable_inputs"]["lab_owned_lifecycle_copy"]
    input_path = REPOSITORY_ROOT / str(input_pin["path"])
    component_ids = {str(component["id"]) for component in contract["components"]}
    segment_results: dict[str, Any] = {}

    for segment_id, segment in contract["segments"].items():
        start = (
            datetime.strptime(str(segment["start"]), TIME_FORMAT)
            if "start" in segment
            else None
        )
        end = (
            datetime.strptime(str(segment["end"]), TIME_FORMAT)
            if "end" in segment
            else None
        )
        events = extract_segment(
            input_path,
            int(segment["source_segment_index"]),
            int(segment["expected_births"]),
            int(segment["expected_closes"]),
            component_ids,
            start,
            end,
        )
        source_reproduction = verify_source_reproduction(events, contract, segment)
        control = simulate(
            events,
            contract,
            "INDEPENDENT_POSITIVE_MATHROUND",
            epochs=segment.get("epochs", []),
        )
        if "control_proxy_anchor" in segment:
            verify_control_anchor(control, segment["control_proxy_anchor"])
        treatment = simulate(
            events,
            contract,
            "ADMITTED_COMPONENT_ERROR_FEEDBACK",
            epochs=segment.get("epochs", []),
        )
        comparison = policy_comparison(control, treatment)
        segment_results[segment_id] = {
            "source_all_ones_reproduction": source_reproduction,
            "control": strip_decisions(control),
            "treatment": strip_decisions(treatment),
            "comparison": comparison,
        }

    selection = segment_results["selection"]
    june = segment_results["june"]
    july = segment_results["july"]
    continuous = segment_results["june_july_continuous"]
    gates_contract = contract["fixed_gates"]
    binding = gates_contract["material_binding"]
    practical = gates_contract["practical_seed"]
    strong_null_contract = gates_contract["strong_null"]
    adverse_contract = gates_contract["economic_adverse"]

    selection_control = selection["control"]
    selection_treatment = selection["treatment"]
    selection_comparison = selection["comparison"]
    fractional_ids = {
        str(component["id"])
        for component in contract["components"]
        if abs(float(component["weight"]) % 1.0) > EPSILON
    }
    changed_by_component = selection_comparison["changed_joint_volume_by_component"]
    changed_fractional_components = sum(
        int(changed_by_component.get(component_id, 0)) > 0
        for component_id in fractional_ids
    )
    maximum_final_residual = max(
        abs(float(component["final_residual_steps"]))
        for component in selection_treatment["components"]
    )
    treatment_epochs = selection_treatment["epochs"]
    treatment_active_components = [
        component
        for component in selection_treatment["components"]
        if component["name"] != "Passive"
    ]

    material_gates = {
        "minimum_selection_changed_joint_admission_fraction": selection_comparison[
            "changed_joint_admission_fraction"
        ]
        + EPSILON
        >= float(binding["minimum_selection_changed_joint_admission_fraction"]),
        "minimum_fractional_components_with_changed_joint_volume": changed_fractional_components
        >= int(binding["minimum_fractional_components_with_changed_joint_volume"]),
        "maximum_absolute_final_treatment_residual_steps": maximum_final_residual
        <= float(binding["maximum_absolute_final_treatment_residual_steps"]),
    }
    practical_gates = {
        "minimum_selection_stressed_net_retention": selection_comparison[
            "treatment_stressed_net_retention"
        ]
        + EPSILON
        >= float(practical["minimum_selection_stressed_net_retention"]),
        "minimum_selection_raw_drawdown_improvement_percentage_points": selection_comparison[
            "raw_drawdown_improvement_percentage_points"
        ]
        + EPSILON
        >= float(
            practical[
                "minimum_selection_raw_drawdown_improvement_percentage_points"
            ]
        ),
        "minimum_selection_stressed_net_per_drawdown_ratio_to_control": selection_comparison[
            "treatment_to_control_stressed_net_per_drawdown_ratio"
        ]
        + EPSILON
        >= float(
            practical[
                "minimum_selection_stressed_net_per_drawdown_ratio_to_control"
            ]
        ),
        "treatment_accepted_lifecycles_not_below_control": selection_treatment[
            "accepted_lifecycles"
        ]
        >= selection_control["accepted_lifecycles"],
        "treatment_aggregate_skips_not_above_control": selection_treatment[
            "aggregate_risk_skips"
        ]
        <= selection_control["aggregate_risk_skips"],
        "all_four_selection_epochs_actual_and_stressed_positive": all(
            float(epoch["actual"]) > 0.0 and float(epoch["stressed"]) > 0.0
            for epoch in treatment_epochs
        ),
        "all_five_active_selection_components_actual_and_stressed_positive": all(
            float(component["actual_net_usd"]) > 0.0
            and float(component["stressed_net_usd"]) > 0.0
            for component in treatment_active_components
        ),
        "june_july_independent_actual_and_stressed_positive": all(
            float(segment["treatment"]["actual_net_usd"]) > 0.0
            and float(segment["treatment"]["stressed_net_usd"]) > 0.0
            for segment in [june, july]
        ),
        "june_july_continuous_actual_and_stressed_positive": float(
            continuous["treatment"]["actual_net_usd"]
        )
        > 0.0
        and float(continuous["treatment"]["stressed_net_usd"]) > 0.0,
        "june_and_july_raw_closed_drawdown_at_or_below_pct": all(
            float(segment["treatment"]["raw_closed_drawdown_pct"])
            <= float(practical["june_and_july_raw_closed_drawdown_at_or_below_pct"])
            + EPSILON
            for segment in [june, july]
        ),
    }
    nominal_gates = {
        "selection_stressed_net_not_below_control": selection_treatment[
            "stressed_net_usd"
        ]
        + EPSILON
        >= selection_control["stressed_net_usd"],
        "selection_raw_closed_drawdown_strictly_below_control": selection_treatment[
            "raw_closed_drawdown_pct"
        ]
        < selection_control["raw_closed_drawdown_pct"] - EPSILON,
        "all_other_practical_seed_gates": all(practical_gates.values()),
    }
    strong_null_gates = {
        "maximum_absolute_selection_stressed_net_change_fraction": abs(
            selection_comparison["treatment_minus_control_stressed_usd"]
            / selection_control["stressed_net_usd"]
        )
        <= float(
            strong_null_contract[
                "maximum_absolute_selection_stressed_net_change_fraction"
            ]
        )
        + EPSILON,
        "maximum_absolute_selection_raw_drawdown_change_percentage_points": abs(
            selection_comparison["raw_drawdown_improvement_percentage_points"]
        )
        <= float(
            strong_null_contract[
                "maximum_absolute_selection_raw_drawdown_change_percentage_points"
            ]
        )
        + EPSILON,
        "maximum_absolute_selection_accepted_lifecycle_change": abs(
            selection_comparison["accepted_lifecycle_delta"]
        )
        <= int(
            strong_null_contract[
                "maximum_absolute_selection_accepted_lifecycle_change"
            ]
        ),
    }
    adverse_gates = {
        "selection_stressed_net_retention_below": selection_comparison[
            "treatment_stressed_net_retention"
        ]
        < float(adverse_contract["selection_stressed_net_retention_below"])
        - EPSILON,
        "selection_raw_drawdown_worse": selection_treatment[
            "raw_closed_drawdown_pct"
        ]
        > selection_control["raw_closed_drawdown_pct"] + EPSILON,
        "any_selection_epoch_actual_or_stressed_nonpositive": any(
            float(epoch["actual"]) <= 0.0 or float(epoch["stressed"]) <= 0.0
            for epoch in treatment_epochs
        ),
        "june_or_july_actual_or_stressed_nonpositive": any(
            float(segment["treatment"]["actual_net_usd"]) <= 0.0
            or float(segment["treatment"]["stressed_net_usd"]) <= 0.0
            for segment in [june, july]
        ),
    }

    material_pass = all(material_gates.values())
    nominal_pass = material_pass and all(nominal_gates.values())
    practical_pass = material_pass and all(practical_gates.values())
    strong_null = material_pass and all(strong_null_gates.values())
    economic_adverse = material_pass and any(adverse_gates.values())
    if nominal_pass:
        classification = "PASS_NOMINAL_ERROR_FEEDBACK_QUANTIZATION_OPTIMIZATION_SEED"
    elif practical_pass:
        classification = "PASS_PRACTICAL_ERROR_FEEDBACK_QUANTIZATION_OPTIMIZATION_SEED"
    elif strong_null:
        classification = "VALID_ERROR_FEEDBACK_QUANTIZATION_STRONG_NULL_NO_SEED"
    elif economic_adverse:
        classification = "VALID_ERROR_FEEDBACK_QUANTIZATION_ECONOMIC_ADVERSE_NO_SEED"
    else:
        classification = "VALID_ERROR_FEEDBACK_QUANTIZATION_AMBIGUOUS_NO_SEED"

    payload = {
        "schema": "zeta-next-executed-exposure-error-feedback-quantization-formal-result-v1",
        "created_at_local": "2026-08-30",
        "unit": contract["unit"],
        "family": contract["family"],
        "primary_macro_program": contract["primary_macro_program"],
        "integrity": {
            "passed": True,
            "declaration_path": str(DECLARATION_PATH.relative_to(REPOSITORY_ROOT)).replace(
                "\\", "/"
            ),
            "declaration_bytes": DECLARATION_PATH.stat().st_size,
            "declaration_sha256": sha256(DECLARATION_PATH),
            "script_bytes": SCRIPT_PATH.stat().st_size,
            "script_sha256": sha256(SCRIPT_PATH),
            "input_bytes": int(input_pin["bytes"]),
            "input_sha256": str(input_pin["sha256"]),
            "source_all_ones_reproductions": len(segment_results),
            "fixed_control_anchor_reproductions": 3,
        },
        "execution": {
            "formal_processes": 1,
            "economic_metric_reruns": 0,
            "fixed_policy_paths_per_segment": 2,
            "grid_points": 0,
            "mql_set_compile_tester_mt5_runtime_or_broker_paths": 0,
            "elapsed_seconds": time.perf_counter() - started,
        },
        "segments": segment_results,
        "gates": {
            "material_binding": material_gates,
            "nominal_seed": nominal_gates,
            "practical_seed": practical_gates,
            "strong_null": strong_null_gates,
            "economic_adverse": adverse_gates,
            "material_binding_passed": material_pass,
            "nominal_seed_passed": nominal_pass,
            "practical_seed_passed": practical_pass,
            "strong_null_passed": strong_null,
            "economic_adverse_triggered": economic_adverse,
        },
        "classification": classification,
        "retained_optimization_seed": (
            "ADMITTED_COMPONENT_ERROR_FEEDBACK"
            if nominal_pass or practical_pass
            else None
        ),
        "source_free_limit": contract["source_free_limit"],
        "fixed_candidate_changed": False,
        "optimization_or_mt5_opened": False,
        "live_surface": "UNTOUCHED",
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(rounded(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "classification": classification,
                "output": str(OUTPUT_PATH),
                "elapsed_seconds": payload["execution"]["elapsed_seconds"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
