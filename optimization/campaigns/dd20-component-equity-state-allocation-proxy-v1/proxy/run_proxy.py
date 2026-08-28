from __future__ import annotations

import copy
import csv
import hashlib
import itertools
import json
import math
import struct
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
CAMPAIGN_ROOT = SCRIPT_PATH.parents[1]
REPOSITORY_ROOT = SCRIPT_PATH.parents[4]
CONFIG_PATH = CAMPAIGN_ROOT / "config" / "proxy-contract.json"
OUTPUT_PATH = (
    REPOSITORY_ROOT
    / "optimization"
    / "artifacts"
    / "raw"
    / "dd20-component-equity-state-allocation-proxy-v1"
    / "output"
    / "proxy-result.json"
)
TIME_FORMAT = "%Y.%m.%d %H:%M:%S"
EPSILON = 1.0e-12


@dataclass(frozen=True)
class LifecycleEvent:
    server_time: datetime
    event: str
    component_index: int
    position_identifier: str
    source_volume_lots: float
    planned_risk_usd: float
    actual_net_usd: float
    stressed_net_usd: float


@dataclass(frozen=True)
class Policy:
    lookback: int
    band_r: float
    loss_multiplier: float
    gain_multiplier: float


@dataclass(frozen=True)
class OpenPosition:
    admitted: bool
    admitted_risk_usd: float
    admitted_steps: int
    source_volume_lots: float
    component_index: int


class PeriodTracker:
    def __init__(self, identifier: str, start: datetime, end: datetime) -> None:
        self.identifier = identifier
        self.start = start
        self.end = end
        self.initialized = False
        self.start_actual = 0.0
        self.start_stressed = 0.0
        self.end_actual = 0.0
        self.end_stressed = 0.0
        self.actual_net = 0.0
        self.stressed_net = 0.0
        self.actual_peak = 0.0
        self.stressed_peak = 0.0
        self.actual_dd = 0.0
        self.stressed_dd = 0.0
        self.minimum_actual = math.inf
        self.minimum_stressed = math.inf
        self.closes = 0

    def contains(self, server_time: datetime) -> bool:
        return self.start <= server_time < self.end

    def observe_close(
        self,
        before_actual: float,
        before_stressed: float,
        after_actual: float,
        after_stressed: float,
        actual_increment: float,
        stressed_increment: float,
    ) -> None:
        if not self.initialized:
            self.initialized = True
            self.start_actual = before_actual
            self.start_stressed = before_stressed
            self.actual_peak = before_actual
            self.stressed_peak = before_stressed
            self.minimum_actual = before_actual
            self.minimum_stressed = before_stressed
        self.actual_net += actual_increment
        self.stressed_net += stressed_increment
        self.actual_peak = max(self.actual_peak, after_actual)
        self.stressed_peak = max(self.stressed_peak, after_stressed)
        self.actual_dd = max(
            self.actual_dd,
            (self.actual_peak - after_actual) / self.actual_peak
            if self.actual_peak > 0.0
            else math.inf,
        )
        self.stressed_dd = max(
            self.stressed_dd,
            (self.stressed_peak - after_stressed) / self.stressed_peak
            if self.stressed_peak > 0.0
            else math.inf,
        )
        self.minimum_actual = min(self.minimum_actual, after_actual)
        self.minimum_stressed = min(self.minimum_stressed, after_stressed)
        self.end_actual = after_actual
        self.end_stressed = after_stressed
        self.closes += 1

    def record(self) -> dict[str, Any]:
        if not self.initialized:
            raise RuntimeError(f"period {self.identifier} contains no candidate close")
        return {
            "id": self.identifier,
            "start": self.start.strftime(TIME_FORMAT),
            "end": self.end.strftime(TIME_FORMAT),
            "continuous_state": True,
            "closes": self.closes,
            "starting_actual_balance_usd": self.start_actual,
            "starting_stressed_balance_usd": self.start_stressed,
            "ending_actual_balance_usd": self.end_actual,
            "ending_stressed_balance_usd": self.end_stressed,
            "actual_net_usd": self.actual_net,
            "stressed_net_usd": self.stressed_net,
            "actual_closed_balance_drawdown_pct": self.actual_dd * 100.0,
            "stressed_closed_balance_drawdown_pct": self.stressed_dd * 100.0,
            "raw_worse_closed_balance_drawdown_pct": max(
                self.actual_dd, self.stressed_dd
            )
            * 100.0,
            "minimum_actual_balance_usd": self.minimum_actual,
            "minimum_stressed_balance_usd": self.minimum_stressed,
        }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def declared_input_root(config: dict[str, Any]) -> tuple[Path, dict[str, dict[str, Any]]]:
    input_config = config["input"]
    input_root = REPOSITORY_ROOT / str(input_config["root"])
    declarations = {
        str(item["name"]): item for item in input_config["files"]
    }
    if len(declarations) != int(input_config["files_total"]):
        raise RuntimeError("copied input declaration count mismatch")
    total_bytes = 0
    manifest_lines: list[str] = []
    for name in sorted(declarations):
        declared = declarations[name]
        size = (input_root / name).stat().st_size
        if size != int(declared["bytes"]):
            raise RuntimeError(f"copied input size mismatch: {name}")
        total_bytes += size
        manifest_lines.append(f"{name}|{size}|{declared['sha256']}")
    manifest = ("\n".join(manifest_lines) + "\n").encode("utf-8")
    if total_bytes != int(input_config["bytes_total"]):
        raise RuntimeError("copied input byte total mismatch")
    if (
        hashlib.sha256(manifest).hexdigest().upper()
        != str(input_config["canonical_manifest_sha256"])
    ):
        raise RuntimeError("declared copied input manifest mismatch")
    return input_root, declarations


def verify_pinned_file(
    input_root: Path,
    declarations: dict[str, dict[str, Any]],
    name: str,
    verified: set[str],
) -> Path:
    if name not in declarations:
        raise RuntimeError(f"input file is not pinned: {name}")
    path = input_root / name
    if name not in verified:
        if sha256(path) != str(declarations[name]["sha256"]):
            raise RuntimeError(f"copied input hash mismatch: {name}")
        verified.add(name)
    return path


def cache_double(path: Path, offset_hex: str) -> float:
    payload = path.read_bytes()
    offset = int(offset_hex, 16)
    if offset < 0 or offset + 8 > len(payload):
        raise RuntimeError("native cache statistic offset is outside the file")
    return float(struct.unpack_from("<d", payload, offset)[0])


def extract_segment(
    path: Path,
    target_segment: int,
    expected: dict[str, Any],
    components: list[str],
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> list[LifecycleEvent]:
    component_indices = {name: index for index, name in enumerate(components)}
    events: list[LifecycleEvent] = []
    segment = 0
    previous_sequence: int | None = None
    last_time: datetime | None = None
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
            if last_time is not None and server_time < last_time:
                raise RuntimeError("selected lifecycle events are not chronological")
            last_time = server_time
            component = source["component_id"]
            if component not in component_indices:
                raise RuntimeError("segment contains an undeclared component")
            planned_risk = source.get("planned_risk_usd", "")
            events.append(
                LifecycleEvent(
                    server_time=server_time,
                    event=source["event"],
                    component_index=component_indices[component],
                    position_identifier=source["position_identifier"],
                    source_volume_lots=float(source["volume"]),
                    planned_risk_usd=float(planned_risk) if planned_risk else 0.0,
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
    if any(event.planned_risk_usd <= 0.0 for event in births):
        raise RuntimeError("source birth planned risk must be positive")
    if "component_birth_counts" in expected:
        observed = {component: 0 for component in components}
        for event in births:
            observed[components[event.component_index]] += 1
        declared = {
            str(name): int(count)
            for name, count in expected["component_birth_counts"].items()
        }
        if observed != declared:
            raise RuntimeError("declared component birth density does not match input")
    if "actual_net_usd" in expected:
        actual = sum(event.actual_net_usd for event in closes)
        stressed = sum(event.stressed_net_usd for event in closes)
        if abs(actual - float(expected["actual_net_usd"])) > 1.0e-7:
            raise RuntimeError("declared actual net does not match copied input")
        if abs(stressed - float(expected["stressed_net_usd"])) > 1.0e-7:
            raise RuntimeError("declared stressed net does not match copied input")
    return events


def verify_period_density(
    events: list[LifecycleEvent],
    periods: list[dict[str, Any]],
    components: list[str],
) -> None:
    for period in periods:
        start = datetime.strptime(period["start"], TIME_FORMAT)
        end = datetime.strptime(period["end"], TIME_FORMAT)
        selected = [event for event in events if start <= event.server_time < end]
        births = [event for event in selected if event.event == "BIRTH"]
        closes = [event for event in selected if event.event == "CLOSE"]
        expected = period["expected"]
        if len(births) != int(expected["births"]) or len(closes) != int(
            expected["closed_lifecycles"]
        ):
            raise RuntimeError(f"{period['id']} lifecycle count mismatch")
        observed = {component: 0 for component in components}
        for event in births:
            observed[components[event.component_index]] += 1
        declared = {
            str(name): int(count)
            for name, count in expected["component_birth_counts"].items()
        }
        if observed != declared:
            raise RuntimeError(f"{period['id']} component birth density mismatch")


def parse_periods(declarations: list[dict[str, Any]]) -> list[PeriodTracker]:
    return [
        PeriodTracker(
            str(item["id"]),
            datetime.strptime(item["start"], TIME_FORMAT),
            datetime.strptime(item["end"], TIME_FORMAT),
        )
        for item in declarations
    ]


def simulate(
    events: list[LifecycleEvent],
    config: dict[str, Any],
    policy: Policy | None,
    period_declarations: list[dict[str, Any]],
) -> dict[str, Any]:
    components = [str(value) for value in config["components"]]
    weights = [float(value) for value in config["fixed_anchor_weights"]]
    component_count = len(components)
    model = config["economic_execution_model"]
    reference = float(config["reference_capital_usd"])
    base_volume = float(model["base_volume_lots"])
    volume_step = float(model["volume_step_lots"])
    addition_step = float(model["addition_step_usd"])
    position_fraction = float(model["position_risk_fraction"])
    aggregate_fraction = float(model["aggregate_risk_fraction"])
    aggregate_tolerance = float(model["aggregate_tolerance_usd"])
    passive_index = components.index(str(model["passive_pending_component"]))
    if len(weights) != component_count or base_volume != volume_step:
        raise RuntimeError("fixed weights or volume-step model is invalid")

    histories = [
        deque(maxlen=policy.lookback if policy is not None else 1)
        for _ in components
    ]
    actual_balance = reference
    stressed_balance = reference
    actual_peak = reference
    stressed_peak = reference
    actual_dd = 0.0
    stressed_dd = 0.0
    minimum_actual = reference
    minimum_stressed = reference
    open_risk = 0.0
    open_positions: dict[str, OpenPosition] = {}
    current_day = None
    day_multiplier = 1
    accepted = 0
    aggregate_skips = 0
    disabled_skips = 0
    capital_skips = 0
    non_neutral_executable = 0
    non_neutral_by_component = [0 for _ in components]
    component_actual = [0.0 for _ in components]
    component_stressed = [0.0 for _ in components]
    component_closed = [0 for _ in components]
    period_trackers = parse_periods(period_declarations)

    for event in events:
        event_day = event.server_time.date()
        if event_day != current_day:
            day_multiplier = 1 + math.floor(
                max(0.0, stressed_balance - reference) / addition_step + 1.0e-9
            )
            day_multiplier = max(1, day_multiplier)
            current_day = event_day

        if event.event == "BIRTH":
            if event.position_identifier in open_positions:
                raise RuntimeError("duplicate open source position")
            component = event.component_index
            overlay = 1.0
            if policy is not None and len(histories[component]) == policy.lookback:
                mean_r = sum(histories[component]) / policy.lookback
                if mean_r < -policy.band_r:
                    overlay = policy.loss_multiplier
                elif mean_r > policy.band_r:
                    overlay = policy.gain_multiplier
            effective_weight = weights[component] * overlay
            if component == passive_index:
                base_steps = math.floor(
                    event.source_volume_lots / volume_step + 0.5
                )
                if base_steps < 1:
                    raise RuntimeError("passive source reservation volume is invalid")
            else:
                base_steps = day_multiplier
            neutral_target_steps = math.floor(base_steps * weights[component] + 0.5)
            target_steps = math.floor(base_steps * effective_weight + 0.5)
            executable_multiplier = target_steps / base_steps
            conservative_capital = min(actual_balance, stressed_balance)
            position_budget = (
                conservative_capital * position_fraction * executable_multiplier
            )
            aggregate_budget = conservative_capital * aggregate_fraction
            enabled = target_steps > 0
            capital_valid = conservative_capital > 0.0
            admitted = (
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
            else:
                accepted += 1
                open_risk += position_budget
                if (
                    policy is not None
                    and abs(overlay - 1.0) > EPSILON
                    and target_steps != neutral_target_steps
                ):
                    non_neutral_executable += 1
                    non_neutral_by_component[component] += 1
            open_positions[event.position_identifier] = OpenPosition(
                admitted=admitted,
                admitted_risk_usd=position_budget if admitted else 0.0,
                admitted_steps=target_steps if admitted else 0,
                source_volume_lots=event.source_volume_lots,
                component_index=component,
            )
            continue

        if event.position_identifier not in open_positions:
            raise RuntimeError("source close has no matching birth")
        position = open_positions.pop(event.position_identifier)
        if position.component_index != event.component_index:
            raise RuntimeError("source birth and close component mismatch")
        scale = position.admitted_steps * volume_step / position.source_volume_lots
        actual_increment = event.actual_net_usd * scale
        stressed_increment = event.stressed_net_usd * scale
        before_actual = actual_balance
        before_stressed = stressed_balance
        actual_balance += actual_increment
        stressed_balance += stressed_increment
        open_risk = max(0.0, open_risk - position.admitted_risk_usd)

        component = position.component_index
        component_actual[component] += actual_increment
        component_stressed[component] += stressed_increment
        if position.admitted:
            component_closed[component] += 1
            if policy is not None:
                histories[component].append(
                    stressed_increment / position.admitted_risk_usd
                )

        actual_peak = max(actual_peak, actual_balance)
        stressed_peak = max(stressed_peak, stressed_balance)
        actual_dd = max(
            actual_dd,
            (actual_peak - actual_balance) / actual_peak
            if actual_peak > 0.0
            else math.inf,
        )
        stressed_dd = max(
            stressed_dd,
            (stressed_peak - stressed_balance) / stressed_peak
            if stressed_peak > 0.0
            else math.inf,
        )
        minimum_actual = min(minimum_actual, actual_balance)
        minimum_stressed = min(minimum_stressed, stressed_balance)
        for tracker in period_trackers:
            if tracker.contains(event.server_time):
                tracker.observe_close(
                    before_actual,
                    before_stressed,
                    actual_balance,
                    stressed_balance,
                    actual_increment,
                    stressed_increment,
                )

    if open_positions:
        raise RuntimeError("segment ended with open source positions")
    if abs(open_risk) > 1.0e-7:
        raise RuntimeError("candidate aggregate planned risk did not reconcile")
    periods = [tracker.record() for tracker in period_trackers]
    return {
        "actual_net_usd": actual_balance - reference,
        "stressed_net_usd": stressed_balance - reference,
        "ending_actual_balance_usd": actual_balance,
        "ending_stressed_balance_usd": stressed_balance,
        "actual_closed_balance_drawdown_pct": actual_dd * 100.0,
        "stressed_closed_balance_drawdown_pct": stressed_dd * 100.0,
        "raw_worse_closed_balance_drawdown_pct": max(actual_dd, stressed_dd)
        * 100.0,
        "minimum_actual_balance_usd": minimum_actual,
        "minimum_stressed_balance_usd": minimum_stressed,
        "accepted_lifecycles": accepted,
        "aggregate_risk_skips": aggregate_skips,
        "disabled_component_skips": disabled_skips,
        "capital_skips": capital_skips,
        "non_neutral_executable_birth_decisions": non_neutral_executable,
        "nonzero_anchor_components_with_non_neutral_executable_decisions": sum(
            1
            for index, count in enumerate(non_neutral_by_component)
            if weights[index] > 0.0 and count > 0
        ),
        "periods": periods,
        "components": [
            {
                "component": component,
                "fixed_anchor_weight": weights[index],
                "admitted_closes": component_closed[index],
                "non_neutral_executable_birth_decisions": non_neutral_by_component[
                    index
                ],
                "actual_net_usd": component_actual[index],
                "stressed_net_usd": component_stressed[index],
                "final_state_count": len(histories[index]) if policy is not None else 0,
                "final_state_mean_stressed_r": (
                    sum(histories[index]) / len(histories[index])
                    if policy is not None and histories[index]
                    else None
                ),
            }
            for index, component in enumerate(components)
        ],
    }


def verify_native_control(
    phase: str,
    config: dict[str, Any],
    input_root: Path,
    declarations: dict[str, dict[str, Any]],
    verified: set[str],
) -> None:
    control = config["qualified_control"][phase]
    components = [str(value) for value in config["components"]]
    lifecycle_name = str(control["lifecycle_file"])
    extract_segment(
        verify_pinned_file(input_root, declarations, lifecycle_name, verified),
        0,
        control["expected_lifecycle"],
        components,
    )
    cache_name = str(control["cache_file"])
    cache = verify_pinned_file(input_root, declarations, cache_name, verified)
    offsets = config["qualified_control"]["cache_offsets"]
    if (
        abs(
            cache_double(cache, offsets["total_net_profit"])
            - float(control["native_total_net_profit_usd"])
        )
        > 1.0e-9
        or abs(
            cache_double(cache, offsets["equity_drawdown_relative_pct"])
            - float(control["native_equity_drawdown_relative_pct"])
        )
        > 1.0e-9
    ):
        raise RuntimeError(f"qualified {phase} native cache fact mismatch")


def assert_neutral_control(
    metrics: dict[str, Any], expected: dict[str, Any], phase: str
) -> None:
    if (
        abs(metrics["actual_net_usd"] - float(expected["actual_net_usd"])) > 1.0e-7
        or abs(metrics["stressed_net_usd"] - float(expected["stressed_net_usd"]))
        > 1.0e-7
        or abs(
            metrics["raw_worse_closed_balance_drawdown_pct"]
            - float(expected["raw_drawdown_pct"])
        )
        > 1.0e-7
    ):
        raise RuntimeError(f"qualified neutral {phase} proxy calibration mismatch")


def policy_grid(config: dict[str, Any]) -> list[Policy]:
    state = config["component_equity_state"]
    policies = [
        Policy(int(lookback), float(band), float(loss), float(gain))
        for lookback, band, loss, gain in itertools.product(
            state["lookbacks"],
            state["symmetric_bands_r"],
            state["loss_multipliers"],
            state["gain_multipliers"],
        )
    ]
    if len(policies) != int(state["expected_candidates"]):
        raise RuntimeError("candidate policy count does not match contract")
    if len(set(policies)) != len(policies):
        raise RuntimeError("candidate policy grid contains duplicates")
    return policies


def period_by_id(metrics: dict[str, Any], identifier: str) -> dict[str, Any]:
    matches = [item for item in metrics["periods"] if item["id"] == identifier]
    if len(matches) != 1:
        raise RuntimeError(f"period is absent or duplicated: {identifier}")
    return matches[0]


def selection_record(
    policy: Policy, metrics: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    calibration = config["selection"]["profit_calibration"]
    dd = config["selection"]["drawdown_calibration"]
    state = config["component_equity_state"]
    conservative_actual = (
        metrics["actual_net_usd"]
        - float(calibration["proxy_minus_native_actual_error_usd"])
        - float(calibration["uncertainty_reserve_usd"])
    )
    conservative_stressed = (
        metrics["stressed_net_usd"]
        - float(calibration["proxy_minus_native_stressed_error_usd"])
        - float(calibration["uncertainty_reserve_usd"])
    )
    budgeted_dd = (
        metrics["raw_worse_closed_balance_drawdown_pct"]
        + float(dd["native_minus_raw_gap_percentage_points"])
        + float(dd["state_and_execution_reserve_percentage_points"])
    )
    epochs = metrics["periods"]
    density_gate = (
        metrics["non_neutral_executable_birth_decisions"]
        >= int(state["minimum_non_neutral_executable_birth_decisions"])
        and metrics[
            "nonzero_anchor_components_with_non_neutral_executable_decisions"
        ]
        >= int(
            state[
                "minimum_nonzero_anchor_components_with_non_neutral_executable_decisions"
            ]
        )
    )
    full_positive_gate = (
        metrics["actual_net_usd"] > 0.0 and metrics["stressed_net_usd"] > 0.0
    )
    conservative_profit_gate = (
        conservative_actual
        > float(calibration["qualified_native_actual_net_usd"])
        and conservative_stressed
        > float(calibration["qualified_native_stressed_net_usd"])
    )
    balance_gate = (
        metrics["minimum_actual_balance_usd"] > 0.0
        and metrics["minimum_stressed_balance_usd"] > 0.0
        and all(
            epoch["minimum_actual_balance_usd"] > 0.0
            and epoch["minimum_stressed_balance_usd"] > 0.0
            for epoch in epochs
        )
    )
    epoch_profit_gate = all(
        epoch["actual_net_usd"] > 0.0 and epoch["stressed_net_usd"] > 0.0
        for epoch in epochs
    )
    epoch_dd_gate = all(
        epoch["raw_worse_closed_balance_drawdown_pct"]
        <= float(dd["hard_equity_drawdown_pct"]) + EPSILON
        for epoch in epochs
    )
    full_dd_gate = budgeted_dd <= float(dd["hard_equity_drawdown_pct"]) + EPSILON
    combined = (
        density_gate
        and full_positive_gate
        and conservative_profit_gate
        and balance_gate
        and epoch_profit_gate
        and epoch_dd_gate
        and full_dd_gate
    )
    return {
        "policy": {
            "lookback": policy.lookback,
            "band_r": policy.band_r,
            "loss_multiplier": policy.loss_multiplier,
            "gain_multiplier": policy.gain_multiplier,
        },
        **metrics,
        "conservative_actual_net_usd": conservative_actual,
        "conservative_stressed_net_usd": conservative_stressed,
        "budgeted_selection_equity_drawdown_pct": budgeted_dd,
        "selection_gates": {
            "non_neutral_density": density_gate,
            "full_actual_and_stressed_positive": full_positive_gate,
            "conservative_profit_strictly_above_qualified_native": conservative_profit_gate,
            "full_and_epoch_balances_positive": balance_gate,
            "all_epoch_actual_and_stressed_positive": epoch_profit_gate,
            "all_epoch_raw_drawdown_at_or_below_20_pct": epoch_dd_gate,
            "budgeted_selection_drawdown_at_or_below_20_pct": full_dd_gate,
            "combined": combined,
        },
    }


def rank_key(record: dict[str, Any]) -> tuple[Any, ...]:
    policy = record["policy"]
    e4 = period_by_id(record, "E4")
    return (
        -float(record["conservative_stressed_net_usd"]),
        -float(record["conservative_actual_net_usd"]),
        -float(e4["stressed_net_usd"]),
        float(record["budgeted_selection_equity_drawdown_pct"]),
        int(policy["lookback"]),
        float(policy["band_r"]),
        float(policy["loss_multiplier"]),
        float(policy["gain_multiplier"]),
    )


def forward_record(metrics: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    full = period_by_id(metrics, "FULL_JUNE_JULY_2026")
    june = period_by_id(metrics, "JUNE_2026_CONTINUOUS_SLICE")
    july = period_by_id(metrics, "JULY_2026_CONTINUOUS_SLICE")
    dd = config["forward"]["drawdown_calibration"]
    july_calibration = config["forward"]["july_profit_calibration"]
    budgeted_dd = (
        metrics["raw_worse_closed_balance_drawdown_pct"]
        + float(dd["native_minus_raw_gap_percentage_points"])
        + float(dd["uncertainty_reserve_percentage_points"])
    )
    july_conservative_actual = (
        july["actual_net_usd"]
        - float(july_calibration["proxy_minus_continuous_native_actual_error_usd"])
        - float(july_calibration["uncertainty_reserve_usd"])
    )
    july_conservative_stressed = (
        july["stressed_net_usd"]
        - float(july_calibration["proxy_minus_continuous_native_stressed_error_usd"])
        - float(july_calibration["uncertainty_reserve_usd"])
    )
    profit_gate = all(
        period["actual_net_usd"] > 0.0 and period["stressed_net_usd"] > 0.0
        for period in (full, june, july)
    )
    balance_gate = (
        metrics["minimum_actual_balance_usd"] > 0.0
        and metrics["minimum_stressed_balance_usd"] > 0.0
        and all(
            period["minimum_actual_balance_usd"] > 0.0
            and period["minimum_stressed_balance_usd"] > 0.0
            for period in (full, june, july)
        )
    )
    dd_gate = budgeted_dd <= float(dd["hard_equity_drawdown_pct"]) + EPSILON
    july_gate = july_conservative_actual > 0.0 and july_conservative_stressed > 0.0
    return {
        **metrics,
        "budgeted_forward_equity_drawdown_pct": budgeted_dd,
        "july_conservative_actual_net_usd": july_conservative_actual,
        "july_conservative_stressed_net_usd": july_conservative_stressed,
        "forward_gates": {
            "full_june_july_actual_and_stressed_positive": profit_gate,
            "full_june_july_balances_positive": balance_gate,
            "budgeted_forward_drawdown_at_or_below_20_pct": dd_gate,
            "conservative_july_actual_and_stressed_positive": july_gate,
            "combined": profit_gate and balance_gate and dd_gate and july_gate,
        },
    }


def rounded(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.strftime(TIME_FORMAT)
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
    input_root, declarations = declared_input_root(config)
    verified: set[str] = set()
    components = [str(value) for value in config["components"]]
    parent_name = str(config["input"]["parent_lifecycle_file"])
    parent_path = verify_pinned_file(
        input_root, declarations, parent_name, verified
    )

    selection_events = extract_segment(
        parent_path,
        int(config["input"]["selection_segment_index"]),
        config["selection"]["expected"],
        components,
    )
    verify_native_control(
        "selection", config, input_root, declarations, verified
    )
    neutral_selection = simulate(
        selection_events,
        config,
        None,
        config["selection"]["epochs"],
    )
    assert_neutral_control(
        neutral_selection,
        config["qualified_control"]["selection"]["expected_neutral_proxy"],
        "selection",
    )

    records = [
        selection_record(
            policy,
            simulate(
                selection_events,
                config,
                policy,
                config["selection"]["epochs"],
            ),
            config,
        )
        for policy in policy_grid(config)
    ]
    eligible = sorted(
        [record for record in records if record["selection_gates"]["combined"]],
        key=rank_key,
    )
    all_ranked = sorted(records, key=rank_key)

    # The policy object and its complete selection record are copied and frozen before
    # any forward lifecycle economics are parsed or simulated.
    frozen_selection_winner = copy.deepcopy(eligible[0]) if eligible else None
    frozen_policy = (
        Policy(**frozen_selection_winner["policy"])
        if frozen_selection_winner is not None
        else None
    )
    selection_freeze = {
        "frozen_before_forward_open": True,
        "eligible_candidates": len(eligible),
        "winner_policy": (
            copy.deepcopy(frozen_selection_winner["policy"])
            if frozen_selection_winner is not None
            else None
        ),
    }

    # Complete the copied-input pin gate only after the selection freeze. This may
    # hash forward files, but no forward row or cache statistic was parsed above.
    for name in sorted(declarations):
        verify_pinned_file(input_root, declarations, name, verified)

    forward_native_gate = "NOT_OPENED_NO_SELECTION_WINNER"
    neutral_forward_gate = "NOT_OPENED_NO_SELECTION_WINNER"
    forward_density_gate = "NOT_OPENED_NO_SELECTION_WINNER"
    neutral_forward = None
    winner_forward = None
    if frozen_policy is not None:
        forward_periods = config["forward"]["periods"]
        full_forward = forward_periods[0]
        forward_events = extract_segment(
            parent_path,
            int(config["input"]["later_segment_index"]),
            full_forward["expected"],
            components,
            datetime.strptime(full_forward["start"], TIME_FORMAT),
            datetime.strptime(full_forward["end"], TIME_FORMAT),
        )
        verify_period_density(forward_events, forward_periods, components)
        forward_density_gate = "PASS"
        verify_native_control("forward", config, input_root, declarations, verified)
        forward_native_gate = "PASS"
        neutral_forward = simulate(forward_events, config, None, forward_periods)
        assert_neutral_control(
            neutral_forward,
            config["qualified_control"]["forward"]["expected_neutral_proxy"],
            "forward",
        )
        neutral_forward_gate = "PASS"
        winner_forward = forward_record(
            simulate(forward_events, config, frozen_policy, forward_periods),
            config,
        )
    shortlist = []
    if (
        frozen_selection_winner is not None
        and winner_forward is not None
        and winner_forward["forward_gates"]["combined"]
    ):
        shortlist.append(
            {
                "policy": copy.deepcopy(frozen_selection_winner["policy"]),
                "selection_conservative_actual_net_usd": frozen_selection_winner[
                    "conservative_actual_net_usd"
                ],
                "selection_conservative_stressed_net_usd": frozen_selection_winner[
                    "conservative_stressed_net_usd"
                ],
                "selection_budgeted_equity_drawdown_pct": frozen_selection_winner[
                    "budgeted_selection_equity_drawdown_pct"
                ],
                "forward_actual_net_usd": winner_forward["actual_net_usd"],
                "forward_stressed_net_usd": winner_forward["stressed_net_usd"],
                "forward_budgeted_equity_drawdown_pct": winner_forward[
                    "budgeted_forward_equity_drawdown_pct"
                ],
                "july_conservative_actual_net_usd": winner_forward[
                    "july_conservative_actual_net_usd"
                ],
                "july_conservative_stressed_net_usd": winner_forward[
                    "july_conservative_stressed_net_usd"
                ],
            }
        )

    if frozen_selection_winner is None:
        status = "VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE"
    elif shortlist:
        status = "VALID_PROXY_COMPLETE_ONE_MT5_SHORTLIST"
    else:
        status = "VALID_PROXY_COMPLETE_FORWARD_GATE_FAIL_NO_SHORTLIST"

    gate_names = tuple(records[0]["selection_gates"])
    gate_counts = {
        name: sum(1 for record in records if record["selection_gates"][name])
        for name in gate_names
    }
    classification_counts = {
        "selection_candidates": len(records),
        "selection_eligible": len(eligible),
        "selection_ineligible": len(records) - len(eligible),
        "forward_winner_evaluated": 1 if winner_forward is not None else 0,
        "forward_all_gates_pass": (
            1
            if winner_forward is not None
            and winner_forward["forward_gates"]["combined"]
            else 0
        ),
        "mt5_shortlist_size": len(shortlist),
    }
    top_count = int(config["output_top_selection_records"])
    result = {
        "schema": "zeta-dd20-component-equity-state-allocation-proxy-raw-result-v1",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "campaign": config["campaign"],
        "implementation": {
            "contract_sha256": sha256(CONFIG_PATH),
            "script_sha256": sha256(SCRIPT_PATH),
            "input_manifest_sha256": config["input"][
                "canonical_manifest_sha256"
            ],
            "verified_input_files": len(verified),
            "verified_input_bytes": config["input"]["bytes_total"],
            "wall_time_seconds": time.perf_counter() - started,
            "selection_native_qualified_cache_gate": "PASS",
            "forward_native_qualified_cache_gate": forward_native_gate,
            "neutral_selection_proxy_calibration_gate": "PASS",
            "neutral_forward_proxy_calibration_gate": neutral_forward_gate,
            "continuous_forward_month_density_gate": forward_density_gate,
        },
        "search": {
            "candidate_combinations": len(records),
            "fixed_anchor_weights": config["fixed_anchor_weights"],
            "candidate_policy_grid": config["component_equity_state"],
            "selection_gate_counts": gate_counts,
            "classification_counts": classification_counts,
            "selection_ranking": config["selection_ranking"],
        },
        "calibration": {
            "neutral_fixed_weight_run_is_candidate": False,
            "selection": neutral_selection,
            "forward": neutral_forward,
            "selection_profit": config["selection"]["profit_calibration"],
            "selection_drawdown": config["selection"]["drawdown_calibration"],
            "forward_drawdown": config["forward"]["drawdown_calibration"],
            "july_profit": config["forward"]["july_profit_calibration"],
            "qualified_native_cache_facts": {
                "offsets": config["qualified_control"]["cache_offsets"],
                "selection": config["qualified_control"]["selection"],
                "forward": config["qualified_control"]["forward"],
            },
        },
        "selection_freeze": selection_freeze,
        "top_selection_records": all_ranked[:top_count],
        "top_selection_eligible": eligible[:top_count],
        "selection_winner": frozen_selection_winner,
        "winner_forward_continuous_holdout": winner_forward,
        "mt5_shortlist": shortlist,
        "boundary": {
            "proxy_completed": True,
            "candidate_state_is_local_and_causal": True,
            "forward_economics_opened": frozen_policy is not None,
            "forward_balance_reset_to_100_and_open_positions_component_state_empty": (
                frozen_policy is not None
            ),
            "forward_full_june_july_simulated_once_continuously": (
                frozen_policy is not None
            ),
            "selection_winner_frozen_before_forward_economics_opened": True,
            "signals_clocks_directions_and_exits_changed": False,
            "synthetic_birth_or_capacity_replacement": False,
            "qualified_control_rerun": False,
            "prior_candidate_rerun": False,
            "original_15_combination_rerun": False,
            "mt5_launched": False,
            "maximum_mt5_shortlist_size": 1,
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
