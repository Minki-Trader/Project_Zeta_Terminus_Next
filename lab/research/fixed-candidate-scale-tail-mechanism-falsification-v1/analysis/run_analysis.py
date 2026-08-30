from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
FAMILY_ROOT = SCRIPT_PATH.parents[1]
REPOSITORY_ROOT = SCRIPT_PATH.parents[4]
DECLARATION_PATH = (
    FAMILY_ROOT
    / "evidence"
    / "FIXED_CANDIDATE_SCALE_TAIL_MECHANISM_FALSIFICATION_DECLARATION_V1.json"
)
OUTPUT_PATH = (
    REPOSITORY_ROOT
    / "lab"
    / "artifacts"
    / "raw"
    / "fixed-candidate-scale-tail-mechanism-falsification-v1"
    / "output"
    / "formal-result.json"
)
TIME_FORMAT = "%Y.%m.%d %H:%M:%S"
EPSILON = 1.0e-9


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def finite_float(value: str, field: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise RuntimeError(f"non-finite {field}")
    return parsed


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, TIME_FORMAT)


def rounded(value: float, digits: int = 12) -> float:
    return round(value, digits)


def assert_close(observed: float, expected: float, label: str, tolerance: float = 1.0e-6) -> None:
    if abs(observed - expected) > tolerance:
        raise RuntimeError(f"{label} mismatch: observed={observed} expected={expected}")


def load_contract() -> tuple[dict[str, Any], dict[str, Path]]:
    contract = json.loads(DECLARATION_PATH.read_text(encoding="utf-8"))
    paths: dict[str, Path] = {}
    manifest_lines: list[str] = []
    for pin in contract["immutable_lab_inputs"]:
        path = REPOSITORY_ROOT / str(pin["path"])
        if not path.is_file():
            raise RuntimeError(f"missing Lab input: {path}")
        if path.stat().st_size != int(pin["bytes"]):
            raise RuntimeError(f"byte mismatch: {pin['name']}")
        digest = sha256(path)
        if digest != str(pin["sha256"]):
            raise RuntimeError(f"hash mismatch: {pin['name']}")
        paths[str(pin["name"])] = path
        manifest_lines.append(f"{pin['name']}\t{pin['bytes']}\t{digest}")
    manifest = ("\n".join(sorted(manifest_lines)) + "\n").encode("utf-8")
    if len(manifest) != int(contract["input_manifest"]["bytes"]):
        raise RuntimeError("canonical manifest byte mismatch")
    manifest_hash = hashlib.sha256(manifest).hexdigest().upper()
    if manifest_hash != str(contract["input_manifest"]["sha256"]):
        raise RuntimeError("canonical manifest hash mismatch")
    return contract, paths


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError(f"empty CSV: {path.name}")
    for index, row in enumerate(rows):
        row["_file_index"] = str(index)
        if int(row.get("research_dropped_records", "0") or "0") != 0:
            raise RuntimeError(f"dropped research records in {path.name}")
    return rows


def read_lifecycles(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = read_csv_rows(path)
    births: dict[str, dict[str, str]] = {}
    closes: dict[str, dict[str, str]] = {}
    previous_time: datetime | None = None
    for row in rows:
        server_time = parse_time(row["server_time"])
        if previous_time is not None and server_time < previous_time:
            raise RuntimeError(f"lifecycle time reversal in {path.name}")
        previous_time = server_time
        if int(row.get("partial_observation", "0") or "0") != 0:
            raise RuntimeError(f"partial lifecycle observation in {path.name}")
        position_id = row["position_identifier"]
        if row["event"] == "BIRTH":
            if position_id in births:
                raise RuntimeError(f"duplicate BIRTH {position_id} in {path.name}")
            births[position_id] = row
        elif row["event"] == "CLOSE":
            if position_id in closes:
                raise RuntimeError(f"duplicate CLOSE {position_id} in {path.name}")
            closes[position_id] = row
    if births.keys() != closes.keys():
        raise RuntimeError(f"unpaired lifecycle records in {path.name}")

    lifecycles: list[dict[str, Any]] = []
    match_keys: set[tuple[str, str]] = set()
    for position_id, birth in births.items():
        close = closes[position_id]
        birth_time = parse_time(birth["server_time"])
        close_time = parse_time(close["server_time"])
        if close_time < birth_time:
            raise RuntimeError(f"negative holding time for {position_id}")
        if birth["component_id"] != close["component_id"]:
            raise RuntimeError(f"component mismatch for {position_id}")
        match_key = (birth["component_id"], birth["entry_time_server"])
        if match_key in match_keys:
            raise RuntimeError(f"duplicate component/time match key in {path.name}")
        match_keys.add(match_key)
        lifecycles.append(
            {
                "position_id": position_id,
                "component_id": birth["component_id"],
                "symbol": birth["symbol"],
                "direction": int(birth["direction"]),
                "birth_time": birth_time,
                "close_time": close_time,
                "entry_time_server": birth["entry_time_server"],
                "entry_price": finite_float(birth["entry_price"], "entry_price"),
                "stop_loss": finite_float(birth["stop_loss"], "stop_loss"),
                "volume": finite_float(birth["volume"], "volume"),
                "planned_risk_usd": finite_float(birth["planned_risk_usd"], "planned_risk_usd"),
                "entry_aggregate_risk_usd": finite_float(
                    birth["entry_aggregate_risk_usd"], "entry_aggregate_risk_usd"
                ),
                "entry_aggregate_headroom_usd": finite_float(
                    birth["entry_aggregate_headroom_usd"], "entry_aggregate_headroom_usd"
                ),
                "birth_sequence": int(birth["research_state_sequence"]),
                "birth_file_index": int(birth["_file_index"]),
                "close_sequence": int(close["research_state_sequence"]),
                "close_file_index": int(close["_file_index"]),
                "exit_reason": close["exit_reason"],
                "exit_class": close["exit_class"],
                "exit_price": finite_float(close["exit_price"], "exit_price"),
                "actual_net_usd": finite_float(close["actual_net_usd"], "actual_net_usd"),
                "stressed_net_usd": finite_float(close["stressed_net_usd"], "stressed_net_usd"),
                "match_key": match_key,
            }
        )
    lifecycles.sort(key=lambda item: (item["birth_time"], item["birth_sequence"], item["birth_file_index"]))
    summary = {
        "csv_rows": len(rows),
        "births": len(births),
        "closes": len(closes),
        "actual_net_usd": rounded(sum(item["actual_net_usd"] for item in lifecycles), 6),
        "stressed_net_usd": rounded(sum(item["stressed_net_usd"] for item in lifecycles), 6),
    }
    return lifecycles, summary


def read_decisions(path: Path) -> list[dict[str, str]]:
    rows = read_csv_rows(path)
    previous_time: datetime | None = None
    for row in rows:
        server_time = parse_time(row["server_time"])
        if previous_time is not None and server_time < previous_time:
            raise RuntimeError(f"decision time reversal in {path.name}")
        previous_time = server_time
    return rows


def position_open_index(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    index: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        if row["stage"] != "OUTCOME" or row["result"] != "POSITION_OPEN":
            continue
        key = (row["component_id"], row["server_time"])
        if key in index:
            raise RuntimeError(f"duplicate POSITION_OPEN decision {key}")
        index[key] = row
    return index


def analyze_sampled_drawdown(
    rows: list[dict[str, str]],
    native_drawdown_pct: float,
    native_drawdown_usd: float,
    contract: dict[str, Any],
) -> dict[str, Any]:
    running_peak = -math.inf
    maximum: dict[str, Any] | None = None
    finite_samples = 0
    for row in rows:
        equity = finite_float(row["account_equity"], "account_equity")
        if equity <= 0.0:
            continue
        finite_samples += 1
        running_peak = max(running_peak, equity)
        drawdown_usd = running_peak - equity
        drawdown_pct = drawdown_usd / running_peak * 100.0
        if maximum is None or drawdown_pct > maximum["drawdown_pct"]:
            risk_capital = finite_float(row["risk_capital_usd"], "risk_capital_usd")
            ladder = 1 + math.floor(max(0.0, risk_capital - 100.0) / 150.0 + 1.0e-9)
            maximum = {
                "server_time": row["server_time"],
                "record_id": row["record_id"],
                "stage": row["stage"],
                "result": row["result"],
                "component_id": row["component_id"],
                "equity_usd": equity,
                "running_peak_usd": running_peak,
                "drawdown_usd": drawdown_usd,
                "drawdown_pct": drawdown_pct,
                "account_balance_usd": finite_float(row["account_balance"], "account_balance"),
                "risk_capital_usd": risk_capital,
                "ladder_level": ladder,
            }
    if maximum is None:
        raise RuntimeError("no positive decision equity samples")
    absolute_gap = abs(native_drawdown_pct - maximum["drawdown_pct"])
    lens = contract["formal_lenses"]["selection_decision_sampled_drawdown"]
    if absolute_gap <= float(lens["resolved_absolute_gap_at_or_below_percentage_points"]) + EPSILON:
        localization = "RESOLVED_WITHIN_0_5PP"
    elif absolute_gap <= float(lens["directional_absolute_gap_at_or_below_percentage_points"]) + EPSILON:
        localization = "DIRECTIONAL_WITHIN_2PP"
    else:
        localization = "UNRESOLVED_SAMPLING_GAP"
    implied_native_peak = native_drawdown_usd / (native_drawdown_pct / 100.0)
    return {
        "finite_decision_samples": finite_samples,
        "sampled_maximum": {
            key: rounded(value) if isinstance(value, float) else value
            for key, value in maximum.items()
        },
        "native_anchor": {
            "relative_equity_drawdown_usd": native_drawdown_usd,
            "relative_equity_drawdown_pct": native_drawdown_pct,
            "implied_peak_equity_usd": rounded(implied_native_peak),
        },
        "absolute_gap_percentage_points": rounded(absolute_gap),
        "sampled_is_lower_bound_or_equal": maximum["drawdown_pct"] <= native_drawdown_pct + EPSILON,
        "localization": localization,
        "seed_authority": False,
    }


def weighted_direction(active: list[dict[str, Any]], symbol: str) -> float:
    return sum(
        item["direction"] * item["planned_risk_usd"]
        for item in active
        if item["symbol"] == symbol
    )


def same_side_cross_index(active: list[dict[str, Any]]) -> bool:
    us30 = weighted_direction(active, "US30")
    us100 = weighted_direction(active, "US100")
    return abs(us30) > EPSILON and abs(us100) > EPSILON and us30 * us100 > 0.0


def analyze_occupancy_and_factor_cap(
    lifecycles: list[dict[str, Any]],
    decisions: list[dict[str, str]],
    cap_fraction: float,
    tolerance_usd: float,
    evaluate_factor_cap: bool = True,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    opens = position_open_index(decisions) if evaluate_factor_cap else {}
    event_groups: dict[datetime, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: {"births": [], "closes": []}
    )
    for item in lifecycles:
        event_groups[item["birth_time"]]["births"].append(item)
        event_groups[item["close_time"]]["closes"].append(item)
    active: dict[str, dict[str, Any]] = {}
    duration_by_occupancy: Counter[int] = Counter()
    cross_index_seconds = 0.0
    same_side_cross_index_seconds = 0.0
    simultaneous_seconds = 0.0
    occupied_seconds = 0.0
    same_side_episodes = 0
    prior_same_side = False
    maximum_occupancy = 0
    binding_records: dict[str, dict[str, Any]] = {}
    binding_components: Counter[str] = Counter()
    all_binding_births = 0
    cross_index_binding_births = 0
    times = sorted(event_groups)
    previous_time = times[0]

    for server_time in times:
        seconds = (server_time - previous_time).total_seconds()
        current = list(active.values())
        occupancy = len(current)
        duration_by_occupancy[occupancy] += seconds
        if occupancy > 0:
            occupied_seconds += seconds
        if occupancy >= 2:
            simultaneous_seconds += seconds
        symbols = {item["symbol"] for item in current}
        if "US30" in symbols and "US100" in symbols:
            cross_index_seconds += seconds
        if same_side_cross_index(current):
            same_side_cross_index_seconds += seconds

        group = event_groups[server_time]
        for item in sorted(
            group["closes"],
            key=lambda row: (row["close_sequence"], row["close_file_index"]),
        ):
            if item["position_id"] not in active:
                raise RuntimeError(f"closing inactive position {item['position_id']}")
            del active[item["position_id"]]

        for item in sorted(
            group["births"],
            key=lambda row: (row["birth_sequence"], row["birth_file_index"]),
        ):
            if evaluate_factor_cap:
                key = (item["component_id"], item["birth_time"].strftime(TIME_FORMAT))
                decision = opens.get(key)
                if decision is None:
                    raise RuntimeError(f"missing POSITION_OPEN decision for {key}")
                risk_capital = finite_float(decision["risk_capital_usd"], "risk_capital_usd")
                same_direction_active = [
                    open_item
                    for open_item in active.values()
                    if open_item["symbol"] in {"US30", "US100"}
                    and open_item["direction"] == item["direction"]
                ]
                side_risk_before = sum(
                    open_item["planned_risk_usd"] for open_item in same_direction_active
                )
                side_risk_after = side_risk_before + item["planned_risk_usd"]
                symbols_after = {open_item["symbol"] for open_item in same_direction_active}
                symbols_after.add(item["symbol"])
                cap_usd = risk_capital * cap_fraction
                would_block = side_risk_after > cap_usd + tolerance_usd + EPSILON
                cross_index = "US30" in symbols_after and "US100" in symbols_after
                if would_block:
                    all_binding_births += 1
                    binding_components[item["component_id"]] += 1
                if would_block and cross_index:
                    cross_index_binding_births += 1
                binding_records[item["position_id"]] = {
                    "position_id": item["position_id"],
                    "component_id": item["component_id"],
                    "symbol": item["symbol"],
                    "direction": item["direction"],
                    "birth_time": item["birth_time"].strftime(TIME_FORMAT),
                    "risk_capital_usd": rounded(risk_capital),
                    "cap_usd": rounded(cap_usd),
                    "same_direction_risk_before_usd": rounded(side_risk_before),
                    "proposed_risk_usd": rounded(item["planned_risk_usd"]),
                    "same_direction_risk_after_usd": rounded(side_risk_after),
                    "cross_index_after": cross_index,
                    "would_block": would_block,
                    "would_block_cross_index": would_block and cross_index,
                }
            else:
                binding_records[item["position_id"]] = {
                    "position_id": item["position_id"],
                    "evaluated": False,
                    "reason": "Control Passive entries can fill after pending-order decisions; control cap binding is outside the declared candidate mechanism question.",
                }
            if item["position_id"] in active:
                raise RuntimeError(f"duplicate active position {item['position_id']}")
            active[item["position_id"]] = item

        current = list(active.values())
        new_same_side = same_side_cross_index(current)
        if new_same_side and not prior_same_side:
            same_side_episodes += 1
        prior_same_side = new_same_side
        maximum_occupancy = max(maximum_occupancy, len(active))
        previous_time = server_time

    if active:
        raise RuntimeError("positions remain active after final lifecycle event")
    total_span_seconds = sum(duration_by_occupancy.values())
    occupancy_hours = {
        str(level): rounded(seconds / 3600.0, 6)
        for level, seconds in sorted(duration_by_occupancy.items())
    }
    occupied_share = {
        str(level): rounded(seconds / occupied_seconds, 9)
        for level, seconds in sorted(duration_by_occupancy.items())
        if level > 0 and occupied_seconds > 0.0
    }
    return (
        {
            "lifecycles": len(lifecycles),
            "maximum_simultaneous_positions": maximum_occupancy,
            "calendar_span_hours": rounded(total_span_seconds / 3600.0, 6),
            "occupied_hours": rounded(occupied_seconds / 3600.0, 6),
            "simultaneous_two_or_more_hours": rounded(simultaneous_seconds / 3600.0, 6),
            "cross_index_overlap_hours": rounded(cross_index_seconds / 3600.0, 6),
            "same_side_cross_index_overlap_hours": rounded(
                same_side_cross_index_seconds / 3600.0, 6
            ),
            "same_side_share_of_cross_index_overlap": rounded(
                same_side_cross_index_seconds / cross_index_seconds
                if cross_index_seconds > 0.0
                else 0.0,
                9,
            ),
            "same_side_share_of_simultaneous_time": rounded(
                same_side_cross_index_seconds / simultaneous_seconds
                if simultaneous_seconds > 0.0
                else 0.0,
                9,
            ),
            "same_side_cross_index_episodes": same_side_episodes,
            "hours_by_occupancy": occupancy_hours,
            "occupied_time_share_by_occupancy": occupied_share,
            "factor_cap_counterfactual": {
                "evaluated": evaluate_factor_cap,
                "cap_fraction": cap_fraction,
                "tolerance_usd": tolerance_usd,
                "all_realized_births_that_would_bind": all_binding_births,
                "cross_index_same_direction_births_that_would_bind": cross_index_binding_births,
                "binding_by_proposed_component": dict(sorted(binding_components.items())),
                "economic_effect_not_replayed": True,
            },
        },
        binding_records,
    )


def median(values: list[float]) -> float:
    if not values:
        raise RuntimeError("median of empty sequence")
    return statistics.median(values)


def analyze_common_scale(
    control: list[dict[str, Any]],
    candidate: list[dict[str, Any]],
    contract: dict[str, Any],
) -> dict[str, Any]:
    control_map = {item["match_key"]: item for item in control}
    candidate_map = {item["match_key"]: item for item in candidate}
    common_keys = sorted(control_map.keys() & candidate_map.keys())
    pairs: list[dict[str, Any]] = []
    component_counts: Counter[str] = Counter()
    component_volume_ratios: dict[str, list[float]] = defaultdict(list)
    for key in common_keys:
        left = control_map[key]
        right = candidate_map[key]
        price_denominator = (abs(left["entry_price"]) + abs(right["entry_price"])) / 2.0
        entry_difference_bp = (
            abs(right["entry_price"] - left["entry_price"]) / price_denominator * 10000.0
            if price_denominator > 0.0
            else 0.0
        )
        left_stop_distance = abs(left["entry_price"] - left["stop_loss"])
        right_stop_distance = abs(right["entry_price"] - right["stop_loss"])
        if left_stop_distance <= 0.0:
            raise RuntimeError("zero control stop distance")
        stop_ratio = right_stop_distance / left_stop_distance
        if left["volume"] <= 0.0 or left["planned_risk_usd"] <= 0.0 or right["planned_risk_usd"] <= 0.0:
            raise RuntimeError("nonpositive common-pair scale denominator")
        volume_ratio = right["volume"] / left["volume"]
        planned_risk_ratio = right["planned_risk_usd"] / left["planned_risk_usd"]
        left_r = left["stressed_net_usd"] / left["planned_risk_usd"]
        right_r = right["stressed_net_usd"] / right["planned_risk_usd"]
        pairs.append(
            {
                "component_id": left["component_id"],
                "entry_time_server": left["entry_time_server"],
                "symbol": left["symbol"],
                "equal_direction": left["direction"] == right["direction"],
                "control_direction": left["direction"],
                "candidate_direction": right["direction"],
                "entry_price_difference_bp": entry_difference_bp,
                "stop_distance_ratio": stop_ratio,
                "volume_ratio": volume_ratio,
                "planned_risk_ratio": planned_risk_ratio,
                "control_stressed_r": left_r,
                "candidate_stressed_r": right_r,
                "absolute_stressed_r_difference": abs(right_r - left_r),
                "control_stressed_net_usd": left["stressed_net_usd"],
                "candidate_stressed_net_usd": right["stressed_net_usd"],
            }
        )
        component_counts[left["component_id"]] += 1
        component_volume_ratios[left["component_id"]].append(volume_ratio)

    control_common = sum(item["control_stressed_net_usd"] for item in pairs)
    candidate_common = sum(item["candidate_stressed_net_usd"] for item in pairs)
    control_total = sum(item["stressed_net_usd"] for item in control)
    candidate_total = sum(item["stressed_net_usd"] for item in candidate)
    total_uplift = candidate_total - control_total
    common_uplift = candidate_common - control_common
    common_share = common_uplift / total_uplift if abs(total_uplift) > EPSILON else math.nan
    lens = contract["formal_lenses"]["august_common_scale"]
    low_band, high_band = [float(value) for value in lens["stop_distance_ratio_band"]]
    equal_direction_fraction = (
        sum(1 for item in pairs if item["equal_direction"]) / len(pairs) if pairs else 0.0
    )
    stop_band_fraction = (
        sum(
            1
            for item in pairs
            if low_band - EPSILON <= item["stop_distance_ratio"] <= high_band + EPSILON
        )
        / len(pairs)
        if pairs
        else 0.0
    )
    metrics = {
        "common_closes": len(pairs),
        "control_only_closes": len(control_map.keys() - candidate_map.keys()),
        "candidate_only_closes": len(candidate_map.keys() - control_map.keys()),
        "equal_direction_fraction": equal_direction_fraction,
        "maximum_entry_price_difference_basis_points": max(
            (item["entry_price_difference_bp"] for item in pairs), default=math.inf
        ),
        "fraction_stop_distance_ratio_in_band": stop_band_fraction,
        "median_candidate_to_control_volume_ratio": median(
            [item["volume_ratio"] for item in pairs]
        ),
        "median_candidate_to_control_planned_risk_ratio": median(
            [item["planned_risk_ratio"] for item in pairs]
        ),
        "median_absolute_stressed_r_difference": median(
            [item["absolute_stressed_r_difference"] for item in pairs]
        ),
        "control_common_stressed_net_usd": control_common,
        "candidate_common_stressed_net_usd": candidate_common,
        "common_stressed_uplift_usd": common_uplift,
        "total_candidate_minus_control_stressed_net_usd": total_uplift,
        "common_uplift_share_of_total": common_share,
    }
    gates = {
        "common_count": metrics["common_closes"] == int(lens["required_common_closes"]),
        "equal_direction": equal_direction_fraction
        >= float(lens["required_equal_direction_fraction"]) - EPSILON,
        "entry_geometry": metrics["maximum_entry_price_difference_basis_points"]
        <= float(lens["maximum_entry_price_difference_basis_points"]) + EPSILON,
        "stop_geometry": stop_band_fraction
        >= float(lens["minimum_fraction_in_stop_distance_band"]) - EPSILON,
        "material_volume_scale": metrics["median_candidate_to_control_volume_ratio"]
        >= float(lens["minimum_median_candidate_to_control_volume_ratio"]) - EPSILON,
        "normalized_economy": metrics["median_absolute_stressed_r_difference"]
        <= float(lens["maximum_median_absolute_stressed_r_difference"]) + EPSILON,
        "common_path_dominance": common_share
        >= float(lens["minimum_common_uplift_share_of_total"]) - EPSILON,
    }
    component_summary = []
    for component_id in sorted(component_counts):
        component_pairs = [item for item in pairs if item["component_id"] == component_id]
        component_summary.append(
            {
                "component_id": component_id,
                "common_closes": component_counts[component_id],
                "median_volume_ratio": rounded(median(component_volume_ratios[component_id])),
                "control_stressed_net_usd": rounded(
                    sum(item["control_stressed_net_usd"] for item in component_pairs), 6
                ),
                "candidate_stressed_net_usd": rounded(
                    sum(item["candidate_stressed_net_usd"] for item in component_pairs), 6
                ),
            }
        )
    return {
        "match_key": "component_id plus exact entry_time_server",
        "metrics": {
            key: rounded(value) if isinstance(value, float) else value
            for key, value in metrics.items()
        },
        "gates": gates,
        "scale_mechanism_supported": all(gates.values()),
        "component_summary": component_summary,
        "pair_detail": [
            {
                key: rounded(value) if isinstance(value, float) else value
                for key, value in item.items()
            }
            for item in pairs
        ],
    }


def overlap_seconds(left: dict[str, Any], right: dict[str, Any]) -> float:
    return max(
        0.0,
        (
            min(left["close_time"], right["close_time"])
            - max(left["birth_time"], right["birth_time"])
        ).total_seconds(),
    )


def tail_trade_record(
    item: dict[str, Any],
    binding_records: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    binding = binding_records[item["position_id"]]
    return {
        "position_id": item["position_id"],
        "component_id": item["component_id"],
        "symbol": item["symbol"],
        "direction": item["direction"],
        "birth_time": item["birth_time"].strftime(TIME_FORMAT),
        "close_time": item["close_time"].strftime(TIME_FORMAT),
        "exit_class": item["exit_class"],
        "exit_reason": item["exit_reason"],
        "planned_risk_usd": rounded(item["planned_risk_usd"]),
        "actual_net_usd": rounded(item["actual_net_usd"], 6),
        "stressed_net_usd": rounded(item["stressed_net_usd"], 6),
        "factor_cap_binding_at_birth": binding,
    }


def analyze_august_tail(
    candidate: list[dict[str, Any]],
    binding_records: dict[str, dict[str, Any]],
    contract: dict[str, Any],
) -> dict[str, Any]:
    daily: dict[str, float] = defaultdict(float)
    for item in candidate:
        daily[item["close_time"].date().isoformat()] += item["stressed_net_usd"]
    worst_day, worst_net = min(daily.items(), key=lambda pair: (pair[1], pair[0]))
    tail = [item for item in candidate if item["close_time"].date().isoformat() == worst_day]
    losers = [item for item in tail if item["stressed_net_usd"] < 0.0]
    losing_stops = [item for item in losers if item["exit_class"] == "STOP"]
    gross_negative = -sum(item["stressed_net_usd"] for item in losers)

    eligible_pairs: list[dict[str, Any]] = []
    for left, right in itertools.combinations(losing_stops, 2):
        seconds = overlap_seconds(left, right)
        if (
            left["symbol"] != right["symbol"]
            and {left["symbol"], right["symbol"]} == {"US30", "US100"}
            and left["direction"] == right["direction"]
            and seconds > 0.0
        ):
            pair_loss = -(left["stressed_net_usd"] + right["stressed_net_usd"])
            later = max((left, right), key=lambda item: item["birth_time"])
            eligible_pairs.append(
                {
                    "position_ids": [left["position_id"], right["position_id"]],
                    "symbols": [left["symbol"], right["symbol"]],
                    "direction": left["direction"],
                    "overlap_seconds": seconds,
                    "combined_stressed_loss_usd": pair_loss,
                    "share_of_gross_negative_exit_economics": (
                        pair_loss / gross_negative if gross_negative > 0.0 else 0.0
                    ),
                    "later_birth_position_id": later["position_id"],
                    "later_birth_factor_cap_binding": binding_records[later["position_id"]],
                }
            )
    eligible_pairs.sort(
        key=lambda pair: (
            pair["share_of_gross_negative_exit_economics"],
            pair["combined_stressed_loss_usd"],
        ),
        reverse=True,
    )
    best_pair = eligible_pairs[0] if eligible_pairs else None
    lens = contract["formal_lenses"]["august_tail"]
    gates = {
        "worst_day_anchor": worst_day == str(lens["required_worst_exit_day"]),
        "minimum_losing_stops": len(losing_stops)
        >= int(lens["minimum_losing_stop_positions"]),
        "cross_index_same_direction_overlap_pair": best_pair is not None,
        "pair_gross_loss_concentration": best_pair is not None
        and best_pair["share_of_gross_negative_exit_economics"]
        >= float(lens["minimum_pair_share_of_gross_negative_exit_economics"]) - EPSILON,
        "later_pair_birth_would_bind_012_cap": best_pair is not None
        and bool(best_pair["later_birth_factor_cap_binding"]["would_block_cross_index"]),
    }
    return {
        "daily_stressed_net_usd": {
            day: rounded(value, 6) for day, value in sorted(daily.items())
        },
        "worst_exit_day": worst_day,
        "worst_exit_day_stressed_net_usd": rounded(worst_net, 6),
        "tail_closed_lifecycles": len(tail),
        "tail_losing_lifecycles": len(losers),
        "tail_losing_stop_lifecycles": len(losing_stops),
        "tail_gross_negative_exit_economics_usd": rounded(gross_negative, 6),
        "tail_trades": [
            tail_trade_record(item, binding_records)
            for item in sorted(tail, key=lambda row: (row["close_time"], row["position_id"]))
        ],
        "eligible_cross_index_same_direction_stop_pairs": [
            {
                key: rounded(value) if isinstance(value, float) else value
                for key, value in pair.items()
            }
            for pair in eligible_pairs
        ],
        "best_pair": (
            {
                key: rounded(value) if isinstance(value, float) else value
                for key, value in best_pair.items()
            }
            if best_pair is not None
            else None
        ),
        "gates": gates,
        "cross_index_same_direction_tail_supported": all(gates.values()),
    }


def main() -> None:
    started = time.perf_counter()
    contract, paths = load_contract()
    selection_decisions = read_decisions(paths["selection-candidate-decisions.csv"])
    selection_lifecycles, selection_summary = read_lifecycles(
        paths["selection-candidate-lifecycles.csv"]
    )
    august_candidate_decisions = read_decisions(paths["august-candidate-decisions.csv"])
    august_control_decisions = read_decisions(paths["august-control-decisions.csv"])
    august_candidate, august_candidate_summary = read_lifecycles(
        paths["august-candidate-lifecycles.csv"]
    )
    august_control, august_control_summary = read_lifecycles(
        paths["august-control-lifecycles.csv"]
    )
    selection_parent = json.loads(paths["selection-native-result.json"].read_text(encoding="utf-8"))
    august_parent = json.loads(
        paths["august-relative-native-result.json"].read_text(encoding="utf-8")
    )

    known = contract["known_parent_context"]
    assert_close(selection_summary["actual_net_usd"], float(known["selection"]["actual_net_usd"]), "selection actual")
    assert_close(selection_summary["stressed_net_usd"], float(known["selection"]["stressed_net_usd"]), "selection stressed")
    if selection_summary["closes"] != int(known["selection"]["closed_lifecycles"]):
        raise RuntimeError("selection close-count mismatch")
    assert_close(
        float(selection_parent["selection"]["mt5_equity_drawdown_relative_pct"]),
        float(known["selection"]["native_relative_equity_drawdown_pct"]),
        "selection native relative equity drawdown",
    )
    assert_close(
        august_control_summary["actual_net_usd"],
        float(known["august_control"]["actual_net_usd"]),
        "August control actual",
    )
    assert_close(
        august_control_summary["stressed_net_usd"],
        float(known["august_control"]["stressed_net_usd"]),
        "August control stressed",
    )
    assert_close(
        august_candidate_summary["actual_net_usd"],
        float(known["august_candidate"]["actual_net_usd"]),
        "August candidate actual",
    )
    assert_close(
        august_candidate_summary["stressed_net_usd"],
        float(known["august_candidate"]["stressed_net_usd"]),
        "August candidate stressed",
    )
    if august_control_summary["closes"] != int(known["august_control"]["closed_lifecycles"]):
        raise RuntimeError("August control close-count mismatch")
    if august_candidate_summary["closes"] != int(known["august_candidate"]["closed_lifecycles"]):
        raise RuntimeError("August candidate close-count mismatch")
    if not bool(august_parent["frozen_judgment"]["mandatory_validity"]["both_complete_normal_100pct_real_ticks"]):
        raise RuntimeError("August parent validity anchor false")

    sampled_drawdown = analyze_sampled_drawdown(
        selection_decisions,
        float(known["selection"]["native_relative_equity_drawdown_pct"]),
        float(known["selection"]["native_relative_equity_drawdown_usd"]),
        contract,
    )
    factor_lens = contract["formal_lenses"]["selection_occupancy"]
    selection_occupancy, selection_bindings = analyze_occupancy_and_factor_cap(
        selection_lifecycles,
        selection_decisions,
        float(factor_lens["proposed_factor_side_cap_fraction"]),
        float(factor_lens["cap_tolerance_usd"]),
    )
    august_candidate_occupancy, august_candidate_bindings = analyze_occupancy_and_factor_cap(
        august_candidate,
        august_candidate_decisions,
        float(factor_lens["proposed_factor_side_cap_fraction"]),
        float(factor_lens["cap_tolerance_usd"]),
    )
    august_control_occupancy, _ = analyze_occupancy_and_factor_cap(
        august_control,
        august_control_decisions,
        float(factor_lens["proposed_factor_side_cap_fraction"]),
        float(factor_lens["cap_tolerance_usd"]),
        evaluate_factor_cap=False,
    )
    common_scale = analyze_common_scale(august_control, august_candidate, contract)
    known_decomposition = known["august_known_decomposition"]
    if common_scale["metrics"]["common_closes"] != int(known_decomposition["common_closes"]):
        raise RuntimeError("common-close anchor mismatch")
    if common_scale["metrics"]["control_only_closes"] != int(known_decomposition["control_only_closes"]):
        raise RuntimeError("control-only anchor mismatch")
    if common_scale["metrics"]["candidate_only_closes"] != int(known_decomposition["candidate_only_closes"]):
        raise RuntimeError("candidate-only anchor mismatch")
    assert_close(
        float(common_scale["metrics"]["control_common_stressed_net_usd"]),
        float(known_decomposition["common_control_stressed_net_usd"]),
        "common control stressed",
    )
    assert_close(
        float(common_scale["metrics"]["candidate_common_stressed_net_usd"]),
        float(known_decomposition["common_candidate_stressed_net_usd"]),
        "common candidate stressed",
    )
    august_tail = analyze_august_tail(august_candidate, august_candidate_bindings, contract)
    assert_close(
        float(august_tail["worst_exit_day_stressed_net_usd"]),
        float(known_decomposition["candidate_worst_exit_day_stressed_net_usd"]),
        "August worst-day stressed",
    )

    scale_supported = bool(common_scale["scale_mechanism_supported"])
    tail_supported = bool(august_tail["cross_index_same_direction_tail_supported"])
    if scale_supported and tail_supported:
        classification = contract["classifications"]["both_mechanisms"]
        retained_seed = contract["retained_seed_if_eligible"]["single_point"]
    elif scale_supported:
        classification = contract["classifications"]["scale_only"]
        retained_seed = None
    else:
        classification = contract["classifications"]["scale_not_confirmed"]
        retained_seed = None

    result = {
        "schema": "zeta-next-fixed-candidate-scale-tail-mechanism-falsification-formal-result-v1",
        "recorded_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "VALID_COMPLETE",
        "unit": int(contract["unit"]),
        "family": contract["family"],
        "formal_processes": 1,
        "duration_seconds": rounded(time.perf_counter() - started, 6),
        "input_manifest": contract["input_manifest"],
        "integrity": {
            "all_eight_input_pins_passed": True,
            "selection_lifecycle": selection_summary,
            "august_control_lifecycle": august_control_summary,
            "august_candidate_lifecycle": august_candidate_summary,
            "selection_decision_rows": len(selection_decisions),
            "august_control_decision_rows": len(august_control_decisions),
            "august_candidate_decision_rows": len(august_candidate_decisions),
            "all_parent_anchors_reproduced": True,
            "all_research_dropped_records_zero": True,
            "all_partial_observations_zero": True,
        },
        "selection_decision_sampled_drawdown": sampled_drawdown,
        "selection_occupancy_and_factor_cap": selection_occupancy,
        "august_control_occupancy_and_factor_cap": august_control_occupancy,
        "august_candidate_occupancy_and_factor_cap": august_candidate_occupancy,
        "august_common_scale_mechanism": common_scale,
        "august_candidate_tail_mechanism": august_tail,
        "economic_verdict": {
            "classification": classification,
            "scale_mechanism_supported": scale_supported,
            "cross_index_same_direction_tail_supported": tail_supported,
            "retained_information_seed": retained_seed,
            "fixed_candidate_changed": False,
            "optimization_campaign_opened": False,
            "mt5_escalation_authorized_or_run": False,
            "interpretation": (
                "The exact raw mechanism gates determine whether the single 0.12 factor-side cap information seed survives. "
                "Decision-sampled drawdown localization is supporting-only because decisions do not contain every tick-level equity extremum."
            ),
        },
        "boundaries": {
            "formal_process_read_only_lab_owned_inputs": True,
            "new_market_data": False,
            "counterfactual_pnl_replay": False,
            "mql_set_compile_tester_or_mt5": False,
            "master_terminal_or_broker_account_surface": "UNTOUCHED",
            "automatic_successor_or_live_authority": False,
        },
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["economic_verdict"], indent=2, ensure_ascii=False))
    print(f"formal_result={OUTPUT_PATH}")


if __name__ == "__main__":
    main()
