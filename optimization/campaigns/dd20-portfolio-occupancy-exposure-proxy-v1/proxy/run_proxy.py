from __future__ import annotations

import csv
import hashlib
import json
import math
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
CAMPAIGN_ROOT = SCRIPT_PATH.parents[1]
REPOSITORY_ROOT = SCRIPT_PATH.parents[4]
CONFIG_PATH = CAMPAIGN_ROOT / "config" / "proxy-contract.json"
TIME_FORMAT = "%Y.%m.%d %H:%M:%S"
EPSILON = 1.0e-9


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
    source_post_entry_active_slots: int


@dataclass(frozen=True)
class CandidatePosition:
    component_index: int
    source_steps: int
    target_steps: int
    admitted_risk_usd: float
    admitted: bool
    occupancy_class: str


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
        self.source_closes = 0
        self.admitted_closes = 0

    def contains(self, moment: datetime) -> bool:
        return self.start <= moment < self.end

    def observe(
        self,
        before_actual: float,
        before_stressed: float,
        after_actual: float,
        after_stressed: float,
        actual_increment: float,
        stressed_increment: float,
        admitted: bool,
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
        self.source_closes += 1
        self.admitted_closes += int(admitted)

    def record(self) -> dict[str, Any]:
        if not self.initialized:
            raise RuntimeError(f"period has no source close: {self.identifier}")
        return {
            "id": self.identifier,
            "start": self.start.strftime(TIME_FORMAT),
            "end": self.end.strftime(TIME_FORMAT),
            "source_closes": self.source_closes,
            "admitted_closes": self.admitted_closes,
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


def receipt(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(REPOSITORY_ROOT)).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def round_steps(value: float) -> int:
    return math.floor(value + 0.5 + 1.0e-12)


def periods_from(configured: list[dict[str, Any]]) -> list[PeriodTracker]:
    return [
        PeriodTracker(
            str(item["id"]),
            datetime.strptime(str(item["start"]), TIME_FORMAT),
            datetime.strptime(str(item["end"]), TIME_FORMAT),
        )
        for item in configured
    ]


def verify_inputs(config: dict[str, Any]) -> tuple[Path, dict[str, dict[str, Any]]]:
    input_root = REPOSITORY_ROOT / str(config["input"]["root"])
    declarations = {str(item["name"]): item for item in config["input"]["files"]}
    if len(declarations) != len(config["input"]["files"]):
        raise RuntimeError("duplicate input declaration")
    total = 0
    for name, declared in declarations.items():
        path = input_root / name
        if not path.is_file():
            raise RuntimeError(f"missing campaign input: {name}")
        if path.stat().st_size != int(declared["bytes"]):
            raise RuntimeError(f"input byte mismatch: {name}")
        if sha256(path) != str(declared["sha256"]):
            raise RuntimeError(f"input hash mismatch: {name}")
        total += path.stat().st_size
    if total != int(config["input"]["bytes_total"]):
        raise RuntimeError("input byte total mismatch")
    return input_root, declarations


def load_events(
    path: Path,
    expected: dict[str, Any],
    components: list[str],
) -> tuple[list[LifecycleEvent], dict[str, Any]]:
    indices = {component: index for index, component in enumerate(components)}
    events: list[LifecycleEvent] = []
    last_time: datetime | None = None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for source in csv.DictReader(handle):
            if source["event"] not in {"BIRTH", "CLOSE"}:
                continue
            if source["event"] == "CLOSE" and source.get("partial_observation", "0") != "0":
                continue
            moment = datetime.strptime(source["server_time"], TIME_FORMAT)
            if last_time is not None and moment < last_time:
                raise RuntimeError("lifecycle source is not chronological")
            last_time = moment
            component = source["component_id"]
            if component not in indices:
                raise RuntimeError(f"unknown component in lifecycle source: {component}")
            events.append(
                LifecycleEvent(
                    server_time=moment,
                    event=source["event"],
                    component_index=indices[component],
                    position_identifier=source["position_identifier"],
                    source_volume_lots=float(source["volume"]),
                    planned_risk_usd=float(source["planned_risk_usd"]),
                    actual_net_usd=float(source["actual_net_usd"]),
                    stressed_net_usd=float(source["stressed_net_usd"]),
                    source_post_entry_active_slots=(
                        int(source["entry_active_slots"])
                        if source["event"] == "BIRTH"
                        else 0
                    ),
                )
            )

    births = [event for event in events if event.event == "BIRTH"]
    closes = [event for event in events if event.event == "CLOSE"]
    if len(births) != int(expected["births"]) or len(closes) != int(expected["closes"]):
        raise RuntimeError("lifecycle source count mismatch")
    birth_ids = [event.position_identifier for event in births]
    close_ids = [event.position_identifier for event in closes]
    if len(set(birth_ids)) != len(birth_ids) or set(birth_ids) != set(close_ids):
        raise RuntimeError("lifecycle birth/close identity mismatch")
    if any(
        event.source_volume_lots <= 0.0 or event.planned_risk_usd <= 0.0
        for event in births
    ):
        raise RuntimeError("source birth volume/risk must be positive")
    actual = sum(event.actual_net_usd for event in closes)
    stressed = sum(event.stressed_net_usd for event in closes)
    if (
        abs(actual - float(expected["actual_net_usd"])) > 1.0e-6
        or abs(stressed - float(expected["stressed_net_usd"])) > 1.0e-6
    ):
        raise RuntimeError("lifecycle source economic total mismatch")
    slot_counts = Counter(event.source_post_entry_active_slots for event in births)
    return events, {
        "births": len(births),
        "closes": len(closes),
        "actual_net_usd": actual,
        "stressed_net_usd": stressed,
        "source_post_entry_active_slot_counts": {
            str(key): value for key, value in sorted(slot_counts.items())
        },
    }


def add_close_to_trackers(
    trackers: list[PeriodTracker],
    event: LifecycleEvent,
    before_actual: float,
    before_stressed: float,
    after_actual: float,
    after_stressed: float,
    actual_increment: float,
    stressed_increment: float,
    admitted: bool,
) -> None:
    for tracker in trackers:
        if tracker.contains(event.server_time):
            tracker.observe(
                before_actual,
                before_stressed,
                after_actual,
                after_stressed,
                actual_increment,
                stressed_increment,
                admitted,
            )


def simulate(
    events: list[LifecycleEvent],
    configured_periods: list[dict[str, Any]],
    config: dict[str, Any],
    empty_factor: float,
    occupied_factor: float,
    require_exact_control: bool,
) -> dict[str, Any]:
    components = [str(value) for value in config["components"]]
    anchor = config["paired_month_anchor"]
    weights = [float(value) for value in anchor["weights"]]
    reference = float(anchor["reference_capital_usd"])
    volume_step = float(anchor["volume_step_lots"])
    aggregate_fraction = float(anchor["aggregate_risk_fraction"])
    aggregate_tolerance = float(anchor["aggregate_tolerance_usd"])

    trackers = periods_from(configured_periods)
    actual_balance = reference
    stressed_balance = reference
    actual_peak = reference
    stressed_peak = reference
    actual_dd = 0.0
    stressed_dd = 0.0
    minimum_actual = reference
    minimum_stressed = reference
    open_risk = 0.0
    open_positions: dict[str, CandidatePosition] = {}
    source_open: set[str] = set()
    admitted = 0
    risk_skips = 0
    zero_step_skips = 0
    modified_birth_decisions = 0
    maximum_candidate_open_positions = 0
    component_actual = [0.0] * len(components)
    component_stressed = [0.0] * len(components)
    component_closes = [0] * len(components)
    occupancy = {
        "EMPTY": {"births": 0, "admitted": 0, "closes": 0, "actual": 0.0, "stressed": 0.0},
        "OCCUPIED": {"births": 0, "admitted": 0, "closes": 0, "actual": 0.0, "stressed": 0.0},
    }

    for event in events:
        if event.event == "BIRTH":
            if event.position_identifier in open_positions or event.position_identifier in source_open:
                raise RuntimeError("duplicate source position birth")
            expected_source_slots = len(source_open) + 1
            if event.source_post_entry_active_slots != expected_source_slots:
                raise RuntimeError(
                    "source active-slot chronology mismatch at "
                    f"{event.server_time.strftime(TIME_FORMAT)}: "
                    f"expected {expected_source_slots}, got {event.source_post_entry_active_slots}"
                )
            source_open.add(event.position_identifier)

            candidate_open_count = sum(
                int(position.admitted) for position in open_positions.values()
            )
            occupancy_class = "EMPTY" if candidate_open_count == 0 else "OCCUPIED"
            factor = empty_factor if occupancy_class == "EMPTY" else occupied_factor
            occupancy[occupancy_class]["births"] += 1
            source_steps = round_steps(event.source_volume_lots / volume_step)
            target_steps = round_steps(source_steps * factor)
            if require_exact_control and target_steps != source_steps:
                raise RuntimeError(
                    "control volume mismatch at "
                    f"{event.server_time.strftime(TIME_FORMAT)} for "
                    f"{components[event.component_index]}: {target_steps} != {source_steps}"
                )
            modified_birth_decisions += int(target_steps != source_steps)
            candidate_risk = (
                event.planned_risk_usd * target_steps / source_steps
                if target_steps > 0
                else 0.0
            )
            conservative_capital = min(actual_balance, stressed_balance)
            aggregate_cap = conservative_capital * aggregate_fraction
            is_admitted = (
                target_steps > 0
                and conservative_capital > 0.0
                and open_risk + candidate_risk
                <= aggregate_cap + aggregate_tolerance + EPSILON
            )
            if target_steps <= 0:
                zero_step_skips += 1
            elif not is_admitted:
                risk_skips += 1
            else:
                admitted += 1
                open_risk += candidate_risk
                occupancy[occupancy_class]["admitted"] += 1
            open_positions[event.position_identifier] = CandidatePosition(
                component_index=event.component_index,
                source_steps=source_steps,
                target_steps=target_steps,
                admitted_risk_usd=candidate_risk if is_admitted else 0.0,
                admitted=is_admitted,
                occupancy_class=occupancy_class,
            )
            maximum_candidate_open_positions = max(
                maximum_candidate_open_positions,
                sum(int(position.admitted) for position in open_positions.values()),
            )
            continue

        if event.position_identifier not in open_positions or event.position_identifier not in source_open:
            raise RuntimeError("source close has no matching birth")
        source_open.remove(event.position_identifier)
        position = open_positions.pop(event.position_identifier)
        before_actual = actual_balance
        before_stressed = stressed_balance
        if position.admitted:
            scale = position.target_steps / position.source_steps
            actual_increment = event.actual_net_usd * scale
            stressed_increment = event.stressed_net_usd * scale
            open_risk = max(0.0, open_risk - position.admitted_risk_usd)
            component_actual[position.component_index] += actual_increment
            component_stressed[position.component_index] += stressed_increment
            component_closes[position.component_index] += 1
            occupancy[position.occupancy_class]["closes"] += 1
            occupancy[position.occupancy_class]["actual"] += actual_increment
            occupancy[position.occupancy_class]["stressed"] += stressed_increment
        else:
            actual_increment = 0.0
            stressed_increment = 0.0
        actual_balance += actual_increment
        stressed_balance += stressed_increment
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
        add_close_to_trackers(
            trackers,
            event,
            before_actual,
            before_stressed,
            actual_balance,
            stressed_balance,
            actual_increment,
            stressed_increment,
            position.admitted,
        )

    if source_open or open_positions:
        raise RuntimeError("segment ended with open positions")
    if abs(open_risk) > 1.0e-6:
        raise RuntimeError("segment ended with nonzero candidate open risk")

    return {
        "empty_book_factor": empty_factor,
        "occupied_book_factor": occupied_factor,
        "actual_net_usd": actual_balance - reference,
        "stressed_net_usd": stressed_balance - reference,
        "ending_actual_balance_usd": actual_balance,
        "ending_stressed_balance_usd": stressed_balance,
        "minimum_actual_balance_usd": minimum_actual,
        "minimum_stressed_balance_usd": minimum_stressed,
        "actual_closed_balance_drawdown_pct": actual_dd * 100.0,
        "stressed_closed_balance_drawdown_pct": stressed_dd * 100.0,
        "raw_worse_closed_balance_drawdown_pct": max(actual_dd, stressed_dd) * 100.0,
        "admitted_lifecycles": admitted,
        "risk_skips": risk_skips,
        "zero_step_skips": zero_step_skips,
        "modified_birth_decisions": modified_birth_decisions,
        "maximum_candidate_open_positions": maximum_candidate_open_positions,
        "occupancy": {
            key: {
                "births": int(value["births"]),
                "admitted": int(value["admitted"]),
                "closes": int(value["closes"]),
                "actual_net_usd": float(value["actual"]),
                "stressed_net_usd": float(value["stressed"]),
            }
            for key, value in occupancy.items()
        },
        "components": [
            {
                "component": component,
                "admitted_closes": component_closes[index],
                "actual_net_usd": component_actual[index],
                "stressed_net_usd": component_stressed[index],
            }
            for index, component in enumerate(components)
        ],
        "periods": [tracker.record() for tracker in trackers],
    }


def verify_control(
    record: dict[str, Any], expected: dict[str, Any], label: str
) -> None:
    if (
        abs(record["actual_net_usd"] - float(expected["actual_net_usd"])) > 1.0e-6
        or abs(record["stressed_net_usd"] - float(expected["stressed_net_usd"]))
        > 1.0e-6
        or record["admitted_lifecycles"] != int(expected["closes"])
        or record["risk_skips"] != 0
        or record["zero_step_skips"] != 0
        or record["modified_birth_decisions"] != 0
    ):
        raise RuntimeError(f"{label} control does not reproduce the frozen anchor")


def apply_selection_gates(
    record: dict[str, Any],
    control: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    gates = config["selection_gates"]
    anchor = config["paired_month_anchor"]["selection"]
    reserve_actual = (
        float(gates["maximum_prior_adverse_proxy_overstatement_actual_usd"])
        + float(gates["new_occupancy_uncertainty_reserve_usd"])
    )
    reserve_stressed = (
        float(gates["maximum_prior_adverse_proxy_overstatement_stressed_usd"])
        + float(gates["new_occupancy_uncertainty_reserve_usd"])
    )
    conservative_actual = record["actual_net_usd"] - reserve_actual
    conservative_stressed = record["stressed_net_usd"] - reserve_stressed
    adverse_raw_delta = max(
        0.0,
        record["raw_worse_closed_balance_drawdown_pct"]
        - control["raw_worse_closed_balance_drawdown_pct"],
    )
    budgeted_dd = (
        float(anchor["native_relative_equity_drawdown_pct"])
        + adverse_raw_delta
        + float(gates["new_mechanism_drawdown_reserve_percentage_points"])
    )
    periods_positive = all(
        period["actual_net_usd"] > 0.0 and period["stressed_net_usd"] > 0.0
        for period in record["periods"]
    )
    gate_values = {
        "noncontrol": not (
            abs(record["empty_book_factor"] - 1.0) <= EPSILON
            and abs(record["occupied_book_factor"] - 1.0) <= EPSILON
        ),
        "minimum_modified_birth_decisions": record["modified_birth_decisions"]
        >= int(gates["minimum_modified_birth_decisions"]),
        "minimum_admitted_fraction": record["admitted_lifecycles"]
        >= math.ceil(
            control["admitted_lifecycles"]
            * float(gates["minimum_admitted_fraction_of_control"])
            - EPSILON
        ),
        "positive_capital": record["minimum_actual_balance_usd"] > 0.0
        and record["minimum_stressed_balance_usd"] > 0.0,
        "all_four_epochs_actual_and_stressed_positive": periods_positive,
        "strict_conservative_actual_profit_improvement": conservative_actual
        > float(anchor["actual_net_usd"]),
        "strict_conservative_stressed_profit_improvement": conservative_stressed
        > float(anchor["stressed_net_usd"]),
        "proxy_drawdown_screen": budgeted_dd
        <= float(gates["maximum_proxy_screening_drawdown_pct"]) + EPSILON,
    }
    return {
        **record,
        "conservative_actual_net_usd": conservative_actual,
        "conservative_stressed_net_usd": conservative_stressed,
        "adverse_raw_drawdown_delta_percentage_points": adverse_raw_delta,
        "budgeted_drawdown_pct": budgeted_dd,
        "nominal_20pct_drawdown_passed": budgeted_dd
        <= float(gates["nominal_drawdown_line_pct"]) + EPSILON,
        "selection_gates": gate_values,
        "selection_eligible": all(gate_values.values()),
    }


def selection_rank(record: dict[str, Any]) -> tuple[float, ...]:
    departure = abs(record["empty_book_factor"] - 1.0) + abs(
        record["occupied_book_factor"] - 1.0
    )
    return (
        -record["conservative_stressed_net_usd"],
        -record["conservative_actual_net_usd"],
        record["budgeted_drawdown_pct"],
        departure,
        -record["empty_book_factor"],
        -record["occupied_book_factor"],
    )


def period_by_id(record: dict[str, Any], identifier: str) -> dict[str, Any]:
    matches = [period for period in record["periods"] if period["id"] == identifier]
    if len(matches) != 1:
        raise RuntimeError(f"missing or duplicate period: {identifier}")
    return matches[0]


def apply_forward_gates(
    record: dict[str, Any],
    control: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    gates = config["forward_gates"]
    anchor = config["paired_month_anchor"]["forward"]
    full = period_by_id(record, "FULL")
    june = period_by_id(record, "JUNE")
    july = period_by_id(record, "JULY")
    adverse_raw_delta = max(
        0.0,
        record["raw_worse_closed_balance_drawdown_pct"]
        - control["raw_worse_closed_balance_drawdown_pct"],
    )
    budgeted_dd = (
        float(anchor["native_relative_equity_drawdown_pct"])
        + adverse_raw_delta
        + float(gates["new_mechanism_drawdown_reserve_percentage_points"])
    )
    gate_values = {
        "minimum_admitted_fraction": record["admitted_lifecycles"]
        >= math.ceil(
            control["admitted_lifecycles"]
            * float(gates["minimum_admitted_fraction_of_control"])
            - EPSILON
        ),
        "positive_capital": record["minimum_actual_balance_usd"] > 0.0
        and record["minimum_stressed_balance_usd"] > 0.0,
        "full_actual_floor": full["actual_net_usd"]
        >= float(anchor["actual_net_usd"])
        - float(gates["maximum_actual_net_degradation_vs_anchor_usd"])
        - EPSILON,
        "full_stressed_floor": full["stressed_net_usd"]
        >= float(anchor["stressed_net_usd"])
        - float(gates["maximum_stressed_net_degradation_vs_anchor_usd"])
        - EPSILON,
        "june_actual_and_stressed_positive": june["actual_net_usd"] > 0.0
        and june["stressed_net_usd"] > 0.0,
        "july_actual_floor": july["actual_net_usd"]
        >= float(gates["minimum_july_actual_net_usd"]) - EPSILON,
        "july_stressed_floor": july["stressed_net_usd"]
        >= float(gates["minimum_july_stressed_net_usd"]) - EPSILON,
        "proxy_drawdown_screen": budgeted_dd
        <= float(gates["maximum_proxy_screening_drawdown_pct"]) + EPSILON,
    }
    return {
        **record,
        "adverse_raw_drawdown_delta_percentage_points": adverse_raw_delta,
        "budgeted_drawdown_pct": budgeted_dd,
        "forward_gates": gate_values,
        "forward_eligible": all(gate_values.values()),
    }


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
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    input_root, declarations = verify_inputs(config)
    components = [str(value) for value in config["components"]]
    anchor = config["paired_month_anchor"]

    selection_path = input_root / str(anchor["selection"]["lifecycle_file"])
    selection_events, selection_source = load_events(
        selection_path, anchor["selection"], components
    )
    expected_slots = {
        str(key): int(value)
        for key, value in config["outcome_free_structure"][
            "selection_births_by_source_post_entry_active_slots"
        ].items()
    }
    if selection_source["source_post_entry_active_slot_counts"] != expected_slots:
        raise RuntimeError("selection occupancy structure differs from declaration")

    control = simulate(
        selection_events,
        config["selection_periods"],
        config,
        1.0,
        1.0,
        True,
    )
    verify_control(control, anchor["selection"], "selection")

    selection_records: list[dict[str, Any]] = []
    for empty_factor in config["occupancy_rule"]["empty_book_factors"]:
        for occupied_factor in config["occupancy_rule"]["occupied_book_factors"]:
            record = simulate(
                selection_events,
                config["selection_periods"],
                config,
                float(empty_factor),
                float(occupied_factor),
                False,
            )
            selection_records.append(apply_selection_gates(record, control, config))

    if len(selection_records) != int(
        config["occupancy_rule"]["candidate_count_including_control"]
    ):
        raise RuntimeError("selection candidate count mismatch")
    eligible = [record for record in selection_records if record["selection_eligible"]]
    eligible.sort(key=selection_rank)
    selection_winner = eligible[0] if eligible else None

    forward_opened = selection_winner is not None
    forward_source = None
    forward_control = None
    forward_candidate = None
    mt5_shortlist: list[dict[str, Any]] = []
    if forward_opened:
        forward_path = input_root / str(anchor["forward"]["lifecycle_file"])
        forward_events, forward_source = load_events(
            forward_path, anchor["forward"], components
        )
        expected_forward_slots = {
            str(key): int(value)
            for key, value in config["outcome_free_structure"][
                "forward_births_by_source_post_entry_active_slots"
            ].items()
        }
        if forward_source["source_post_entry_active_slot_counts"] != expected_forward_slots:
            raise RuntimeError("forward occupancy structure differs from declaration")
        forward_control = simulate(
            forward_events,
            config["forward_periods"],
            config,
            1.0,
            1.0,
            True,
        )
        verify_control(forward_control, anchor["forward"], "forward")
        forward_candidate = simulate(
            forward_events,
            config["forward_periods"],
            config,
            selection_winner["empty_book_factor"],
            selection_winner["occupied_book_factor"],
            False,
        )
        forward_candidate = apply_forward_gates(
            forward_candidate, forward_control, config
        )
        if forward_candidate["forward_eligible"]:
            mt5_shortlist.append(
                {
                    "empty_book_factor": selection_winner["empty_book_factor"],
                    "occupied_book_factor": selection_winner[
                        "occupied_book_factor"
                    ],
                    "selection_conservative_actual_net_usd": selection_winner[
                        "conservative_actual_net_usd"
                    ],
                    "selection_conservative_stressed_net_usd": selection_winner[
                        "conservative_stressed_net_usd"
                    ],
                    "selection_budgeted_drawdown_pct": selection_winner[
                        "budgeted_drawdown_pct"
                    ],
                    "forward_actual_net_usd": forward_candidate["actual_net_usd"],
                    "forward_stressed_net_usd": forward_candidate[
                        "stressed_net_usd"
                    ],
                    "forward_budgeted_drawdown_pct": forward_candidate[
                        "budgeted_drawdown_pct"
                    ],
                }
            )

    if not forward_opened:
        status = "VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE_PORTFOLIO_OCCUPANCY_EXPOSURE"
    elif not mt5_shortlist:
        status = "VALID_PROXY_COMPLETE_SELECTION_WINNER_FAILS_FORWARD_NO_MT5_SHORTLIST"
    else:
        status = "VALID_PROXY_COMPLETE_ONE_MT5_SHORTLIST_PORTFOLIO_OCCUPANCY_EXPOSURE"

    output_path = REPOSITORY_ROOT / str(config["output"]["path"])
    result = {
        "schema": "zeta-dd20-portfolio-occupancy-exposure-proxy-raw-result-v1",
        "recorded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": status,
        "campaign": config["campaign"],
        "implementation": {
            "formal_proxy_processes": 1,
            "wall_time_seconds": time.perf_counter() - started,
            "script": receipt(SCRIPT_PATH),
            "config": receipt(CONFIG_PATH),
            "input_hashes_and_bytes_match": True,
        },
        "input": {
            "selection": receipt(selection_path),
            "forward": receipt(input_root / str(anchor["forward"]["lifecycle_file"])),
            "selection_source": selection_source,
            "forward_source_opened_for_candidate": forward_opened,
            "forward_source": forward_source,
        },
        "fixed_grid": {
            "empty_book_factors": config["occupancy_rule"]["empty_book_factors"],
            "occupied_book_factors": config["occupancy_rule"][
                "occupied_book_factors"
            ],
            "selection_paths_including_control": len(selection_records),
        },
        "selection": {
            "control": control,
            "eligible_noncontrol_paths": len(eligible),
            "winner": selection_winner,
            "all_paths": selection_records,
        },
        "forward": {
            "opened": forward_opened,
            "control": forward_control,
            "candidate": forward_candidate,
        },
        "mt5_shortlist": mt5_shortlist,
        "boundary": {
            "mql_or_settings_changes": 0,
            "compile_or_tester_paths": 0,
            "tests_or_validators": 0,
            "live_changes": 0,
            "lab_changes": 0,
            "broker_or_account_queries": 0,
            "automatic_live_promotion": False,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(rounded(result), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": status,
                "selection_eligible": len(eligible),
                "forward_opened": forward_opened,
                "mt5_shortlist": len(mt5_shortlist),
                "output": str(output_path),
                "wall_time_seconds": result["implementation"]["wall_time_seconds"],
            }
        )
    )


if __name__ == "__main__":
    main()
