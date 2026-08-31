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


def verify_authority_and_stage_c(
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
    for role in ("stage_c_raw", "stage_c_durable"):
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

    raw_roles = payloads["stage_c_raw"].get("stage_d_roles", [])
    durable_roles = payloads["stage_c_durable"].get("stage_d_roles", [])
    if len(raw_roles) != 1 or len(durable_roles) != 1:
        raise RuntimeError("Stage-C successor role count mismatch")
    expected = config["immutable_role"]
    comparable_fields = (
        "development_selection_kind",
        "membership_mask_integer",
        "weights",
        "base_position_risk_fraction",
        "aggregate_risk_fraction",
        "consecutive_loss_close_trigger",
        "future_source_birth_suppression_count",
    )
    for field in comparable_fields:
        if raw_roles[0][field] != expected[field]:
            raise RuntimeError(f"raw Stage-C role {field} mismatch")
        if durable_roles[0][field] != expected[field]:
            raise RuntimeError(f"durable Stage-C role {field} mismatch")
    if int(raw_roles[0]["static_seed_rank"]) != int(
        expected["stage_c_static_seed_rank"]
    ):
        raise RuntimeError("raw Stage-C role rank mismatch")
    if int(durable_roles[0]["static_seed_rank"]) != int(
        expected["stage_c_static_seed_rank"]
    ):
        raise RuntimeError("durable Stage-C role rank mismatch")
    if bool(payloads["stage_c_raw"].get("locked_holdout_opened")):
        raise RuntimeError("Stage-C raw result opened the locked holdout")
    if int(payloads["stage_c_raw"]["mt5"]["valid_economic_paths_run"]) != 0:
        raise RuntimeError("Stage-C raw result used MT5")

    return {**authority_paths, **input_paths}, payloads["stage_c_raw"], payloads[
        "stage_c_durable"
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
            config["source_anchor_reproduction"]["volume_tolerance_lots"]
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


def build_values(config: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    component_count = len(config["components"])
    role = config["immutable_role"]
    role_weights = np.asarray(role["weights"], dtype=np.float64)
    source_weights = np.asarray(
        [float(item["source_weight"]) for item in config["components"]],
        dtype=np.float64,
    )
    if role_weights.shape != (component_count,):
        raise RuntimeError("immutable role component count mismatch")
    if np.any(role_weights <= 0.0):
        raise RuntimeError("immutable all-five role has an inactive component")
    if np.any(role_weights > source_weights + 1.0e-12):
        raise RuntimeError("immutable role violates exact-V8 weight ceiling")
    if int(role["membership_mask_integer"]) != (1 << component_count) - 1:
        raise RuntimeError("immutable role membership mask mismatch")
    if int(role["consecutive_loss_close_trigger"]) != 0:
        raise RuntimeError("Stage-D role unexpectedly enables loss state")
    if int(role["future_source_birth_suppression_count"]) != 0:
        raise RuntimeError("Stage-D role unexpectedly enables suppression state")
    candidate = np.asarray(
        [
            list(map(float, role["weights"]))
            + [
                float(role["aggregate_risk_fraction"]),
                float(role["consecutive_loss_close_trigger"]),
                float(role["future_source_birth_suppression_count"]),
            ]
        ],
        dtype=np.float64,
    )
    anchor = config["source_anchor_reproduction"]
    anchor_values = np.asarray(
        [
            list(map(float, anchor["weights"]))
            + [float(anchor["aggregate_risk_fraction"])]
        ],
        dtype=np.float64,
    )
    return candidate, anchor_values


def verify_blocks(
    config: dict[str, Any],
) -> list[tuple[str, datetime, datetime, bool]]:
    declared = config["blocks"]
    expected_names = [
        "2024-H1",
        "2024-H2",
        "2025-H1",
        "2025-H2",
        "2026-01-through-05",
        "2026-06-through-07",
    ]
    if [str(item["name"]) for item in declared] != expected_names:
        raise RuntimeError("Stage-D block name/order mismatch")
    blocks = [
        (
            str(item["name"]),
            iso_time(str(item["start"])),
            iso_time(str(item["end"])),
            bool(item["locked_before_stage_d"]),
        )
        for item in declared
    ]
    for index, (_, start, end, locked) in enumerate(blocks):
        if start >= end:
            raise RuntimeError("Stage-D block has nonpositive duration")
        if index and blocks[index - 1][2] != start:
            raise RuntimeError("Stage-D blocks are not contiguous")
        if locked != (index == len(blocks) - 1):
            raise RuntimeError("Stage-D locked-block identity mismatch")
    whole = config["whole_period"]
    if blocks[0][1] != iso_time(str(whole["start"])):
        raise RuntimeError("Stage-D whole start mismatch")
    if blocks[-1][2] != iso_time(str(whole["end"])):
        raise RuntimeError("Stage-D whole end mismatch")
    return blocks


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
                atol=float(
                    config["source_anchor_reproduction"]["volume_tolerance_lots"]
                ),
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
    authority_paths, stage_c_raw, stage_c_durable = verify_authority_and_stage_c(
        config
    )
    input_paths, lifecycles = verify_and_load_lifecycles(config)
    candidate_values, anchor_values = build_values(config)
    blocks = verify_blocks(config)

    source_anchor = config["source_anchor_reproduction"]
    source_anchor_metrics = simulate(lifecycles, anchor_values, config)
    observed_source_anchor = record(
        0, anchor_values, source_anchor_metrics, config
    )
    if observed_source_anchor["accepted_source_lifecycles"] != int(
        source_anchor["accepted_lifecycles"]
    ):
        raise RuntimeError("exact source anchor accepted lifecycle reproduction failed")
    if observed_source_anchor["source_volume_matches"] != int(
        source_anchor["source_volume_matches"]
    ):
        raise RuntimeError("exact source anchor volume reproduction failed")
    if observed_source_anchor["source_risk_capital_matches"] != int(
        source_anchor["joined_birth_open_rows"]
    ):
        raise RuntimeError("exact source anchor risk-capital reproduction failed")
    if observed_source_anchor["source_position_cap_matches"] != int(
        source_anchor["joined_birth_open_rows"]
    ):
        raise RuntimeError("exact source anchor position-cap reproduction failed")
    if abs(
        observed_source_anchor["actual_net_usd"]
        - float(source_anchor["actual_net_usd"])
    ) > float(source_anchor["net_tolerance_usd"]):
        raise RuntimeError("exact source anchor actual reproduction failed")
    if abs(
        observed_source_anchor["stressed_net_usd"]
        - float(source_anchor["stressed_net_usd"])
    ) > float(source_anchor["net_tolerance_usd"]):
        raise RuntimeError("exact source anchor stressed reproduction failed")
    if abs(
        observed_source_anchor["raw_closed_balance_drawdown_pct"]
        - float(source_anchor["closed_balance_drawdown_pct"])
    ) > float(source_anchor["drawdown_tolerance_points"]):
        raise RuntimeError("exact source anchor drawdown reproduction failed")

    block_results: list[dict[str, Any]] = []
    block_passes: list[bool] = []
    block_max_dd = float(config["gates"]["block_max_drawdown_pct"])
    tolerance = float(config["gates"]["numeric_tolerance"])
    for name, start, end, was_locked in blocks:
        candidate_metrics = simulate(
            lifecycles, candidate_values, config, start, end
        )
        anchor_metrics = simulate(lifecycles, anchor_values, config, start, end)
        candidate_record = record(
            0, candidate_values, candidate_metrics, config
        )
        anchor_record = record(0, anchor_values, anchor_metrics, config)
        positive_passed = bool(positive(candidate_metrics)[0])
        drawdown_passed = bool(
            float(candidate_metrics["drawdown_pct"][0])
            <= block_max_dd + tolerance
        )
        passed = positive_passed and drawdown_passed
        block_passes.append(passed)
        block_results.append(
            {
                "name": name,
                "start": start.isoformat(),
                "end_exclusive": end.isoformat(),
                "locked_before_stage_d": was_locked,
                "opened_by_this_stage": True,
                "exact_v8_anchor": anchor_record,
                "candidate": candidate_record,
                "positive_gate_passed": positive_passed,
                "drawdown_gate_passed": drawdown_passed,
                "passed": passed,
            }
        )

    stage_c_role = config["immutable_role"]
    validation_result = block_results[4]["candidate"]
    validation_anchor = block_results[4]["exact_v8_anchor"]
    validation_anchor_stressed = float(validation_anchor["stressed_net_usd"])
    if validation_anchor_stressed <= 0.0:
        raise RuntimeError("Stage-C validation anchor is nonpositive")
    validation_retention = (
        float(validation_result["stressed_net_usd"]) / validation_anchor_stressed
    )
    if abs(
        float(validation_result["actual_net_usd"])
        - float(stage_c_role["expected_stage_c_validation_actual_net_usd"])
    ) > 1.0e-7:
        raise RuntimeError("Stage-C validation actual parity failed")
    if abs(
        float(validation_result["stressed_net_usd"])
        - float(stage_c_role["expected_stage_c_validation_stressed_net_usd"])
    ) > 1.0e-7:
        raise RuntimeError("Stage-C validation stressed parity failed")
    if abs(
        float(validation_result["raw_closed_balance_drawdown_pct"])
        - float(stage_c_role["expected_stage_c_validation_drawdown_pct"])
    ) > 1.0e-9:
        raise RuntimeError("Stage-C validation drawdown parity failed")
    if abs(
        validation_retention
        - float(stage_c_role["expected_stage_c_validation_stressed_retention"])
    ) > 1.0e-9:
        raise RuntimeError("Stage-C validation retention parity failed")

    whole = config["whole_period"]
    whole_start = iso_time(str(whole["start"]))
    whole_end = iso_time(str(whole["end"]))
    candidate_whole_metrics = simulate(
        lifecycles, candidate_values, config, whole_start, whole_end
    )
    anchor_whole_metrics = simulate(
        lifecycles, anchor_values, config, whole_start, whole_end
    )
    candidate_whole = record(
        0, candidate_values, candidate_whole_metrics, config
    )
    anchor_whole = record(0, anchor_values, anchor_whole_metrics, config)
    anchor_whole_stressed = float(anchor_whole["stressed_net_usd"])
    if anchor_whole_stressed <= 0.0:
        raise RuntimeError("Stage-D whole anchor stressed net is nonpositive")
    stressed_retention = (
        float(candidate_whole["stressed_net_usd"]) / anchor_whole_stressed
    )
    drawdown_improvement = (
        float(anchor_whole["raw_closed_balance_drawdown_pct"])
        - float(candidate_whole["raw_closed_balance_drawdown_pct"])
    )
    retention_passed = (
        stressed_retention + tolerance
        >= float(config["gates"]["whole_minimum_stressed_retention"])
    )
    drawdown_passed = (
        drawdown_improvement + tolerance
        >= float(
            config["gates"]["whole_minimum_drawdown_improvement_points"]
        )
    )
    all_blocks_passed = all(block_passes)
    final_pass = all_blocks_passed and retention_passed and drawdown_passed

    role_payload = {
        "stage_c_static_seed_rank": int(
            stage_c_role["stage_c_static_seed_rank"]
        ),
        "development_selection_kind": str(
            stage_c_role["development_selection_kind"]
        ),
        "membership_mask_integer": int(
            stage_c_role["membership_mask_integer"]
        ),
        "weights": [float(value) for value in stage_c_role["weights"]],
        "base_position_risk_fraction": float(
            config["base_position_risk_fraction"]
        ),
        "aggregate_risk_fraction": float(
            stage_c_role["aggregate_risk_fraction"]
        ),
        "consecutive_loss_close_trigger": int(
            stage_c_role["consecutive_loss_close_trigger"]
        ),
        "future_source_birth_suppression_count": int(
            stage_c_role["future_source_birth_suppression_count"]
        ),
    }
    stage_e_roles = [role_payload] if final_pass else []
    if len(stage_e_roles) > int(
        config["succession"]["maximum_stage_e_roles"]
    ):
        raise RuntimeError("Stage-E role limit exceeded")

    result: dict[str, Any] = {
        "schema": "zeta-next-dd20-v8-membership-temporal-cost-stability-proxy-result-v1",
        "recorded_at_utc": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "campaign": "dd20-v8-membership-temporal-cost-stability-proxy-v1",
        "optimization_unit_id": str(config["optimization_unit_id"]),
        "unit_stage": str(config["unit_stage"]),
        "stage_d_has_unit_closure_authority": True,
        "unit_closed": not final_pass,
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
                "path": str(
                    authority_paths["declaration"].relative_to(REPOSITORY_ROOT)
                ).replace("\\", "/"),
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
            "stage_c_raw": {
                "path": str(config["inputs"]["root"])
                + "/"
                + str(config["inputs"]["stage_c_raw"]["name"]),
                "bytes": authority_paths["stage_c_raw"].stat().st_size,
                "sha256": sha256(authority_paths["stage_c_raw"]),
                "status": stage_c_raw["status"],
            },
            "stage_c_durable": {
                "path": str(config["inputs"]["root"])
                + "/"
                + str(config["inputs"]["stage_c_durable"]["name"]),
                "bytes": authority_paths["stage_c_durable"].stat().st_size,
                "sha256": sha256(authority_paths["stage_c_durable"]),
                "status": stage_c_durable["status"],
            },
            "matched_lifecycles": len(lifecycles),
        },
        "immutable_role": role_payload,
        "source_anchor_whole_path": observed_source_anchor,
        "blocks": block_results,
        "block_gate": {
            "required_block_count": len(blocks),
            "passing_block_count": sum(block_passes),
            "all_blocks_passed": all_blocks_passed,
            "all_positive_gates_passed": all(
                item["positive_gate_passed"] for item in block_results
            ),
            "all_drawdown_gates_passed": all(
                item["drawdown_gate_passed"] for item in block_results
            ),
            "maximum_actual_closed_balance_drawdown_pct": block_max_dd,
        },
        "whole": {
            "name": str(whole["name"]),
            "start": whole_start.isoformat(),
            "end_exclusive": whole_end.isoformat(),
            "exact_v8_anchor": anchor_whole,
            "candidate": candidate_whole,
            "stressed_retention_vs_exact_v8": stressed_retention,
            "minimum_stressed_retention": float(
                config["gates"]["whole_minimum_stressed_retention"]
            ),
            "stressed_retention_passed": retention_passed,
            "actual_closed_balance_drawdown_improvement_points": drawdown_improvement,
            "minimum_drawdown_improvement_points": float(
                config["gates"][
                    "whole_minimum_drawdown_improvement_points"
                ]
            ),
            "drawdown_improvement_passed": drawdown_passed,
        },
        "final_passed": final_pass,
        "stage_e_roles": stage_e_roles,
        "locked_holdout_opened": True,
        "stage_c_reopened": False,
        "mt5": {
            "shortlist_count": len(stage_e_roles),
            "valid_economic_paths_run": 0,
            "maximum_valid_economic_paths_authorized": int(
                config["mt5_budget"][
                    "maximum_valid_economic_paths_after_stage_d"
                ]
            ),
        },
        "limitations": [
            "Accepted-source-path replay only; 143 capacity-blocked existing-V8 opportunities have unknown outcomes and receive zero profit credit.",
            "Candidate-specific open-equity paths, native stop quantization and capacity-freed admissions require conditional Stage E and are not claimed here.",
            "The doubled-observed-cost book is reused exactly; no new cost model or post-hoc stress fit is introduced.",
            "The locked June-July block can reject the immutable role but cannot select an alternate or reopen Stage C.",
        ],
    }
    result["status"] = (
        "VALID_PROXY_COMPLETE_STAGE_D_ONE_FINALIST_STAGE_E_REQUIRED_NO_MT5"
        if final_pass
        else "VALID_PROXY_COMPLETE_STAGE_D_NONCONFIRMATION_UNIT_002_CLOSED_EXHAUSTED_NO_MT5"
    )
    result["implementation"] = {
        "script_path": str(SCRIPT_PATH.relative_to(REPOSITORY_ROOT)).replace(
            "\\", "/"
        ),
        "script_sha256": sha256(SCRIPT_PATH),
        "config_path": str(CONFIG_PATH.relative_to(REPOSITORY_ROOT)).replace(
            "\\", "/"
        ),
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
                "wall_time_seconds": result["implementation"][
                    "wall_time_seconds"
                ],
                "stage_e_role_count": len(stage_e_roles),
                "unit_closed": result["unit_closed"],
                "mt5_paths": 0,
            }
        )
    )

if __name__ == "__main__":
    main()
