#!/usr/bin/env python3
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


TIME_FORMAT = "%Y.%m.%d %H:%M:%S"
DECLARATION_SHA256 = (
    "25C328630AC28D84FE1C1B958BF2C0C6B412A31DC0D574721F318A6C330420A5"
)

SCRIPT_PATH = Path(__file__).resolve()
FAMILY_ROOT = SCRIPT_PATH.parents[1]
REPOSITORY_ROOT = SCRIPT_PATH.parents[4]
DECLARATION_PATH = (
    FAMILY_ROOT
    / "evidence"
    / "PAIRED_ANCHOR_COMPONENT_CAPITAL_SUBSIDY_DECLARATION_V1.json"
)
OUTPUT_PATH = (
    REPOSITORY_ROOT
    / "lab"
    / "artifacts"
    / "raw"
    / "paired-anchor-component-capital-subsidy-v1"
    / "output"
    / "formal-result.json"
)


@dataclass(frozen=True)
class Component:
    name: str
    component_id: str
    weight: float


@dataclass(frozen=True)
class Event:
    row_number: int
    server_time: datetime
    event: str
    component_id: str
    position_identifier: str
    volume: float
    actual_net: float
    stressed_net: float


@dataclass(frozen=True)
class OpenPosition:
    component_id: str
    source_steps: int
    candidate_steps: int


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def finite(value: str, field: str, row_number: int) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise RuntimeError(f"non-finite {field} at CSV row {row_number}")
    return parsed


def load_contract() -> dict[str, Any]:
    if sha256(DECLARATION_PATH) != DECLARATION_SHA256:
        raise RuntimeError("frozen declaration hash mismatch")
    with DECLARATION_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_events(contract: dict[str, Any]) -> tuple[list[Event], dict[str, int]]:
    pin = contract["immutable_inputs"]["lab_owned_lifecycle_copy"]
    path = REPOSITORY_ROOT / str(pin["path"])
    if path.stat().st_size != int(pin["bytes"]) or sha256(path) != str(pin["sha256"]):
        raise RuntimeError("Lab-owned lifecycle input pin mismatch")

    events: list[Event] = []
    counts: dict[str, int] = {}
    previous_time: datetime | None = None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "server_time",
            "event",
            "component_id",
            "position_identifier",
            "volume",
            "actual_net_usd",
            "stressed_net_usd",
        }
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise RuntimeError("lifecycle CSV header is incomplete")
        for row_number, row in enumerate(reader, start=2):
            event_name = str(row["event"])
            counts[event_name] = counts.get(event_name, 0) + 1
            server_time = datetime.strptime(str(row["server_time"]), TIME_FORMAT)
            if previous_time is not None and server_time < previous_time:
                raise RuntimeError("lifecycle CSV server times are not nondecreasing")
            previous_time = server_time
            if event_name not in {"BIRTH", "CLOSE"}:
                continue
            events.append(
                Event(
                    row_number=row_number,
                    server_time=server_time,
                    event=event_name,
                    component_id=str(row["component_id"]),
                    position_identifier=str(row["position_identifier"]),
                    volume=finite(str(row["volume"]), "volume", row_number),
                    actual_net=finite(
                        str(row["actual_net_usd"]), "actual_net_usd", row_number
                    ),
                    stressed_net=finite(
                        str(row["stressed_net_usd"]),
                        "stressed_net_usd",
                        row_number,
                    ),
                )
            )

    expected = contract["fixed_anchor"]
    if sum(counts.values()) != int(expected["expected_rows"]):
        raise RuntimeError("declared total row count mismatch")
    if counts.get("BIRTH", 0) != int(expected["expected_births"]):
        raise RuntimeError("declared BIRTH count mismatch")
    if counts.get("CLOSE", 0) != int(expected["expected_closes"]):
        raise RuntimeError("declared CLOSE count mismatch")
    if counts.get("FIRST_PEER_NATURAL_EXIT", 0) != int(
        expected["expected_first_peer_rows"]
    ):
        raise RuntimeError("declared first-peer count mismatch")
    if set(counts) != {"BIRTH", "CLOSE", "FIRST_PEER_NATURAL_EXIT"}:
        raise RuntimeError("unexpected lifecycle event type")
    return events, counts


def epoch_id(server_time: datetime, epochs: list[dict[str, Any]]) -> str:
    for epoch in epochs:
        start = datetime.strptime(str(epoch["start"]), TIME_FORMAT)
        end = datetime.strptime(str(epoch["end"]), TIME_FORMAT)
        if start <= server_time < end:
            return str(epoch["id"])
    raise RuntimeError("CLOSE event is outside every frozen epoch")


def max_closed_drawdown_pct(increments: list[float], reference: float) -> tuple[float, float]:
    balance = reference
    peak = reference
    minimum = reference
    maximum_drawdown = 0.0
    for increment in increments:
        balance += increment
        if balance <= 0.0 or not math.isfinite(balance):
            raise RuntimeError("closed balance became nonpositive or non-finite")
        peak = max(peak, balance)
        minimum = min(minimum, balance)
        maximum_drawdown = max(maximum_drawdown, (peak - balance) / peak * 100.0)
    return maximum_drawdown, minimum


def rounded_steps(multiplier: int, weight: float) -> int:
    return int(math.floor(float(multiplier) * weight + 0.5))


def replay(contract: dict[str, Any], events: list[Event]) -> dict[str, Any]:
    components = [Component(**row) for row in contract["components"]]
    component_by_id = {component.component_id: component for component in components}
    if len(component_by_id) != len(components):
        raise RuntimeError("duplicate component identity in declaration")

    fixed = contract["fixed_anchor"]
    reference = float(fixed["reference_capital_usd"])
    addition_step = float(fixed["addition_step_usd"])
    volume_step = float(fixed["base_and_volume_step_lots"])
    epochs = contract["selection_epochs"]
    epoch_names = [str(epoch["id"]) for epoch in epochs]

    source_stressed_profit = 0.0
    candidate_component_stressed_profit = {
        component.component_id: 0.0 for component in components
    }
    source_day_multiplier = 1
    local_day_multiplier = {component.component_id: 1 for component in components}
    current_day = None
    open_positions: dict[str, OpenPosition] = {}
    birth_ids: set[str] = set()
    close_ids: set[str] = set()

    source_actual_increments: list[float] = []
    source_stressed_increments: list[float] = []
    candidate_actual_increments: list[float] = []
    candidate_stressed_increments: list[float] = []

    component_metrics = {
        component.component_id: {
            "name": component.name,
            "births": 0,
            "reduced_lifecycles": 0,
            "source_steps": 0,
            "candidate_steps": 0,
            "source_actual": 0.0,
            "source_stressed": 0.0,
            "candidate_actual": 0.0,
            "candidate_stressed": 0.0,
        }
        for component in components
    }
    epoch_metrics = {
        name: {
            "closes": 0,
            "source_actual": 0.0,
            "source_stressed": 0.0,
            "candidate_actual": 0.0,
            "candidate_stressed": 0.0,
        }
        for name in epoch_names
    }

    source_steps_total = 0
    candidate_steps_total = 0
    reduced_lifecycles = 0
    request_shortfall_births = 0
    maximum_request_shortfall_steps = 0
    maximum_source_multiplier = 1
    maximum_local_multiplier = {component.component_id: 1 for component in components}

    for event in events:
        if event.component_id not in component_by_id:
            raise RuntimeError(f"unmapped component at CSV row {event.row_number}")
        event_day = event.server_time.date()
        if event_day != current_day:
            source_day_multiplier = 1 + math.floor(
                max(0.0, source_stressed_profit) / addition_step + 1.0e-9
            )
            maximum_source_multiplier = max(
                maximum_source_multiplier, source_day_multiplier
            )
            for component in components:
                multiplier = 1 + math.floor(
                    max(
                        0.0,
                        candidate_component_stressed_profit[component.component_id],
                    )
                    / addition_step
                    + 1.0e-9
                )
                local_day_multiplier[component.component_id] = multiplier
                maximum_local_multiplier[component.component_id] = max(
                    maximum_local_multiplier[component.component_id], multiplier
                )
            current_day = event_day

        component = component_by_id[event.component_id]
        if event.event == "BIRTH":
            if event.position_identifier in birth_ids or event.position_identifier in open_positions:
                raise RuntimeError("duplicate BIRTH position identity")
            raw_steps = event.volume / volume_step
            source_steps = int(math.floor(raw_steps + 0.5))
            if source_steps <= 0 or abs(raw_steps - source_steps) > 1.0e-9:
                raise RuntimeError("source volume is not an exact positive lot step")
            predicted_source_steps = rounded_steps(
                source_day_multiplier, component.weight
            )
            if source_steps > predicted_source_steps:
                raise RuntimeError(
                    "source fill exceeds frozen global ladder request at "
                    f"row {event.row_number}: observed={source_steps} "
                    f"requested={predicted_source_steps}"
                )
            if source_steps < predicted_source_steps:
                request_shortfall_births += 1
                maximum_request_shortfall_steps = max(
                    maximum_request_shortfall_steps,
                    predicted_source_steps - source_steps,
                )
            local_steps = rounded_steps(
                local_day_multiplier[event.component_id], component.weight
            )
            candidate_steps = min(source_steps, local_steps)
            if candidate_steps <= 0 or candidate_steps > source_steps:
                raise RuntimeError("candidate no-add step contract failed")
            birth_ids.add(event.position_identifier)
            open_positions[event.position_identifier] = OpenPosition(
                component_id=event.component_id,
                source_steps=source_steps,
                candidate_steps=candidate_steps,
            )
            metric = component_metrics[event.component_id]
            metric["births"] += 1
            metric["source_steps"] += source_steps
            metric["candidate_steps"] += candidate_steps
            source_steps_total += source_steps
            candidate_steps_total += candidate_steps
            if candidate_steps < source_steps:
                metric["reduced_lifecycles"] += 1
                reduced_lifecycles += 1
            continue

        if event.position_identifier not in open_positions:
            raise RuntimeError("CLOSE has no matching open BIRTH")
        if event.position_identifier in close_ids:
            raise RuntimeError("duplicate CLOSE position identity")
        opened = open_positions.pop(event.position_identifier)
        if opened.component_id != event.component_id:
            raise RuntimeError("BIRTH/CLOSE component identity mismatch")
        close_ids.add(event.position_identifier)
        scale = opened.candidate_steps / opened.source_steps
        candidate_actual = event.actual_net * scale
        candidate_stressed = event.stressed_net * scale

        source_actual_increments.append(event.actual_net)
        source_stressed_increments.append(event.stressed_net)
        candidate_actual_increments.append(candidate_actual)
        candidate_stressed_increments.append(candidate_stressed)
        source_stressed_profit += event.stressed_net
        candidate_component_stressed_profit[event.component_id] += candidate_stressed

        metric = component_metrics[event.component_id]
        metric["source_actual"] += event.actual_net
        metric["source_stressed"] += event.stressed_net
        metric["candidate_actual"] += candidate_actual
        metric["candidate_stressed"] += candidate_stressed

        e_id = epoch_id(event.server_time, epochs)
        e_metric = epoch_metrics[e_id]
        e_metric["closes"] += 1
        e_metric["source_actual"] += event.actual_net
        e_metric["source_stressed"] += event.stressed_net
        e_metric["candidate_actual"] += candidate_actual
        e_metric["candidate_stressed"] += candidate_stressed

    if open_positions or birth_ids != close_ids:
        raise RuntimeError("BIRTH/CLOSE lifecycle identity set mismatch")

    source_actual = sum(source_actual_increments)
    source_stressed = sum(source_stressed_increments)
    candidate_actual = sum(candidate_actual_increments)
    candidate_stressed = sum(candidate_stressed_increments)
    if abs(source_actual - float(fixed["expected_actual_net_usd"])) > 1.0e-7:
        raise RuntimeError("source actual net anchor mismatch")
    if abs(source_stressed - float(fixed["expected_stressed_net_usd"])) > 1.0e-7:
        raise RuntimeError("source stressed net anchor mismatch")

    source_actual_dd, source_actual_min = max_closed_drawdown_pct(
        source_actual_increments, reference
    )
    source_stressed_dd, source_stressed_min = max_closed_drawdown_pct(
        source_stressed_increments, reference
    )
    candidate_actual_dd, candidate_actual_min = max_closed_drawdown_pct(
        candidate_actual_increments, reference
    )
    candidate_stressed_dd, candidate_stressed_min = max_closed_drawdown_pct(
        candidate_stressed_increments, reference
    )
    source_raw_dd = max(source_actual_dd, source_stressed_dd)
    candidate_raw_dd = max(candidate_actual_dd, candidate_stressed_dd)

    component_rows: list[dict[str, Any]] = []
    positive_stressed_improvements: list[float] = []
    components_nonnegative_both = 0
    for component in components:
        metric = component_metrics[component.component_id]
        delta_actual = metric["candidate_actual"] - metric["source_actual"]
        delta_stressed = metric["candidate_stressed"] - metric["source_stressed"]
        if delta_actual >= -1.0e-9 and delta_stressed >= -1.0e-9:
            components_nonnegative_both += 1
        positive_stressed_improvements.append(max(0.0, delta_stressed))
        component_rows.append(
            {
                "name": metric["name"],
                "component_id": component.component_id,
                "births": metric["births"],
                "reduced_lifecycles": metric["reduced_lifecycles"],
                "source_steps": metric["source_steps"],
                "candidate_steps": metric["candidate_steps"],
                "removed_step_fraction": (
                    (metric["source_steps"] - metric["candidate_steps"])
                    / metric["source_steps"]
                ),
                "source_actual_usd": metric["source_actual"],
                "source_stressed_usd": metric["source_stressed"],
                "candidate_actual_usd": metric["candidate_actual"],
                "candidate_stressed_usd": metric["candidate_stressed"],
                "candidate_minus_source_actual_usd": delta_actual,
                "candidate_minus_source_stressed_usd": delta_stressed,
                "maximum_component_local_day_multiplier": maximum_local_multiplier[
                    component.component_id
                ],
            }
        )

    positive_improvement_total = sum(positive_stressed_improvements)
    maximum_positive_component_share = (
        max(positive_stressed_improvements) / positive_improvement_total
        if positive_improvement_total > 1.0e-12
        else 1.0
    )

    epoch_rows: list[dict[str, Any]] = []
    candidate_epochs_positive_both = 0
    epochs_nonnegative_delta_both = 0
    for name in epoch_names:
        metric = epoch_metrics[name]
        delta_actual = metric["candidate_actual"] - metric["source_actual"]
        delta_stressed = metric["candidate_stressed"] - metric["source_stressed"]
        if metric["candidate_actual"] > 0.0 and metric["candidate_stressed"] > 0.0:
            candidate_epochs_positive_both += 1
        if delta_actual >= -1.0e-9 and delta_stressed >= -1.0e-9:
            epochs_nonnegative_delta_both += 1
        epoch_rows.append(
            {
                "id": name,
                "closes": metric["closes"],
                "source_actual_usd": metric["source_actual"],
                "source_stressed_usd": metric["source_stressed"],
                "candidate_actual_usd": metric["candidate_actual"],
                "candidate_stressed_usd": metric["candidate_stressed"],
                "candidate_minus_source_actual_usd": delta_actual,
                "candidate_minus_source_stressed_usd": delta_stressed,
            }
        )

    removed_fraction = (source_steps_total - candidate_steps_total) / source_steps_total
    delta_actual = candidate_actual - source_actual
    delta_stressed = candidate_stressed - source_stressed
    binding_gate = contract["fixed_material_binding_gate"]
    economic_gate = contract["fixed_economic_seed_gate"]
    gates = {
        "integrity": True,
        "minimum_reduced_lifecycles": reduced_lifecycles
        >= int(binding_gate["minimum_reduced_lifecycles"]),
        "minimum_removed_source_lot_step_fraction": removed_fraction
        >= float(binding_gate["minimum_removed_source_lot_step_fraction"]),
        "minimum_candidate_minus_control_actual_usd": delta_actual
        >= float(economic_gate["minimum_candidate_minus_control_actual_usd"]),
        "minimum_candidate_minus_control_stressed_usd": delta_stressed
        >= float(economic_gate["minimum_candidate_minus_control_stressed_usd"]),
        "candidate_raw_closed_drawdown_not_worse": candidate_raw_dd
        <= source_raw_dd + 1.0e-9,
        "all_four_candidate_epochs_actual_and_stressed_positive": candidate_epochs_positive_both
        == len(epoch_names),
        "minimum_epochs_with_nonnegative_actual_and_stressed_delta": epochs_nonnegative_delta_both
        >= int(economic_gate["minimum_epochs_with_nonnegative_actual_and_stressed_delta"]),
        "minimum_components_with_nonnegative_actual_and_stressed_delta": components_nonnegative_both
        >= int(
            economic_gate[
                "minimum_components_with_nonnegative_actual_and_stressed_delta"
            ]
        ),
        "maximum_single_component_share_of_positive_stressed_improvement": maximum_positive_component_share
        <= float(
            economic_gate[
                "maximum_single_component_share_of_positive_stressed_improvement"
            ]
        ),
    }
    material_pass = gates["minimum_reduced_lifecycles"] and gates[
        "minimum_removed_source_lot_step_fraction"
    ]
    economic_keys = [
        key
        for key in gates
        if key
        not in {
            "integrity",
            "minimum_reduced_lifecycles",
            "minimum_removed_source_lot_step_fraction",
        }
    ]
    economic_pass = all(gates[key] for key in economic_keys)
    passed = material_pass and economic_pass
    classification = (
        "PASS_COMPONENT_LOCAL_NO_ADD_CAPITAL_SUBSIDY_OPTIMIZATION_SEED"
        if passed
        else "VALID_COMPONENT_CAPITAL_SUBSIDY_NONCONFIRMATION_NO_SEED"
    )

    return {
        "integrity": {
            "passed": True,
            "births": len(birth_ids),
            "closes": len(close_ids),
            "source_global_volume_mismatches": 0,
            "source_fills_above_requested": 0,
            "request_shortfall_births": request_shortfall_births,
            "maximum_request_shortfall_steps": maximum_request_shortfall_steps,
            "unmapped_components": 0,
            "open_positions_at_end": 0,
            "source_actual_anchor_delta_usd": source_actual
            - float(fixed["expected_actual_net_usd"]),
            "source_stressed_anchor_delta_usd": source_stressed
            - float(fixed["expected_stressed_net_usd"]),
        },
        "control": {
            "actual_net_usd": source_actual,
            "stressed_net_usd": source_stressed,
            "raw_closed_drawdown_pct": source_raw_dd,
            "actual_raw_closed_drawdown_pct": source_actual_dd,
            "stressed_raw_closed_drawdown_pct": source_stressed_dd,
            "minimum_actual_balance_usd": source_actual_min,
            "minimum_stressed_balance_usd": source_stressed_min,
            "maximum_global_day_multiplier": maximum_source_multiplier,
            "source_lot_steps": source_steps_total,
        },
        "component_local_no_add": {
            "actual_net_usd": candidate_actual,
            "stressed_net_usd": candidate_stressed,
            "candidate_minus_control_actual_usd": delta_actual,
            "candidate_minus_control_stressed_usd": delta_stressed,
            "raw_closed_drawdown_pct": candidate_raw_dd,
            "actual_raw_closed_drawdown_pct": candidate_actual_dd,
            "stressed_raw_closed_drawdown_pct": candidate_stressed_dd,
            "minimum_actual_balance_usd": candidate_actual_min,
            "minimum_stressed_balance_usd": candidate_stressed_min,
            "candidate_lot_steps": candidate_steps_total,
            "removed_lot_steps": source_steps_total - candidate_steps_total,
            "removed_source_lot_step_fraction": removed_fraction,
            "reduced_lifecycles": reduced_lifecycles,
            "marginal_removed_actual_usd": source_actual - candidate_actual,
            "marginal_removed_stressed_usd": source_stressed - candidate_stressed,
        },
        "breadth": {
            "candidate_epochs_positive_both": candidate_epochs_positive_both,
            "epochs_nonnegative_delta_both": epochs_nonnegative_delta_both,
            "components_nonnegative_delta_both": components_nonnegative_both,
            "positive_stressed_improvement_usd": positive_improvement_total,
            "maximum_single_component_share_of_positive_stressed_improvement": maximum_positive_component_share,
        },
        "components": component_rows,
        "epochs": epoch_rows,
        "gates": gates,
        "material_binding_gate_passed": material_pass,
        "economic_seed_gate_passed": economic_pass,
        "classification": classification,
        "retained_seed": "COMPONENT_LOCAL_NO_ADD" if passed else None,
    }


def main() -> None:
    started = time.perf_counter()
    contract = load_contract()
    events, event_counts = load_events(contract)
    result = replay(contract, events)
    payload = {
        "schema": "zeta-next-paired-anchor-component-capital-subsidy-formal-result-v1",
        "created_at_local": "2026-08-29",
        "status": "VALID_FIXED_SOURCE_FREE_REPLAY_COMPLETE",
        "unit": contract["unit"],
        "family": contract["family"],
        "macro_program": contract["macro_program"],
        "declaration": {
            "path": str(DECLARATION_PATH.relative_to(REPOSITORY_ROOT)).replace(
                "\\", "/"
            ),
            "bytes": DECLARATION_PATH.stat().st_size,
            "sha256": DECLARATION_SHA256,
        },
        "input": {
            **contract["immutable_inputs"]["lab_owned_lifecycle_copy"],
            "event_counts": event_counts,
        },
        "execution": {
            "successful_formal_processes": 1,
            "economic_metric_reruns": 0,
            "engineering_or_design_corrections": 1,
            "runtime_copies": 0,
            "mql_source_copies": 0,
            "compile_paths": 0,
            "tester_paths": 0,
            "orders": 0,
            "broker_or_account_queries": 0,
            "elapsed_seconds": time.perf_counter() - started,
        },
        **result,
        "forward_opened": False,
        "program_6_opened": False,
        "live_surface": "UNTOUCHED",
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
