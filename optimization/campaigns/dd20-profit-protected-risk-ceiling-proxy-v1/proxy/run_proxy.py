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
    / "dd20-profit-protected-risk-ceiling-proxy-v1"
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
    planned_risk_usd: float
    entry_aggregate_risk_usd: float
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


def cache_double(path: Path, offset_hex: str) -> float:
    payload = path.read_bytes()
    offset = int(offset_hex, 16)
    if offset < 0 or offset + 8 > len(payload):
        raise RuntimeError("native cache statistic offset is outside the file")
    return float(struct.unpack_from("<d", payload, offset)[0])


def load_events(
    path: Path,
    expected: dict[str, Any],
    components: list[str],
) -> list[LifecycleEvent]:
    component_index = {component: index for index, component in enumerate(components)}
    events: list[LifecycleEvent] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for source in csv.DictReader(handle):
            if source["event"] not in {"BIRTH", "CLOSE"}:
                continue
            component = source["component_id"]
            if component not in component_index:
                raise RuntimeError("lifecycle contains an undeclared component")
            events.append(
                LifecycleEvent(
                    server_time=datetime.strptime(source["server_time"], TIME_FORMAT),
                    event=source["event"],
                    component_index=component_index[component],
                    position_identifier=source["position_identifier"],
                    planned_risk_usd=float(source["planned_risk_usd"]),
                    entry_aggregate_risk_usd=float(
                        source["entry_aggregate_risk_usd"]
                    ),
                    actual_net_usd=float(source["actual_net_usd"]),
                    stressed_net_usd=float(source["stressed_net_usd"]),
                )
            )

    births = [event for event in events if event.event == "BIRTH"]
    closes = [event for event in events if event.event == "CLOSE"]
    birth_ids = [event.position_identifier for event in births]
    close_ids = [event.position_identifier for event in closes]
    if len(births) != int(expected["births"]):
        raise RuntimeError("declared birth count does not match copied lifecycle")
    if len(closes) != int(expected["closed_lifecycles"]):
        raise RuntimeError("declared close count does not match copied lifecycle")
    if len(set(birth_ids)) != len(birth_ids) or set(birth_ids) != set(close_ids):
        raise RuntimeError("birth and close position identities do not match")
    if any(event.planned_risk_usd <= 0.0 for event in births):
        raise RuntimeError("birth planned risk must be positive")
    actual = sum(event.actual_net_usd for event in closes)
    stressed = sum(event.stressed_net_usd for event in closes)
    if abs(actual - float(expected["actual_net_usd"])) > 1.0e-7:
        raise RuntimeError("declared actual net does not match copied lifecycle")
    if abs(stressed - float(expected["stressed_net_usd"])) > 1.0e-7:
        raise RuntimeError("declared stressed net does not match copied lifecycle")
    return events


def epoch_index(server_time: datetime, epochs: list[dict[str, Any]]) -> int | None:
    for index, epoch in enumerate(epochs):
        if epoch["start_time"] <= server_time < epoch["end_time"]:
            return index
    return None


def simulate_retained_path(
    events: list[LifecycleEvent],
    hard_caps: np.ndarray,
    reference: float,
    tolerance: float,
    component_count: int,
    epochs: list[dict[str, Any]],
) -> dict[str, np.ndarray]:
    candidate_count = len(hard_caps)
    epoch_count = len(epochs)
    actual_balance = np.full(candidate_count, reference, dtype=np.float64)
    stressed_balance = np.full(candidate_count, reference, dtype=np.float64)
    actual_peak = actual_balance.copy()
    stressed_peak = stressed_balance.copy()
    actual_max_dd = np.zeros(candidate_count, dtype=np.float64)
    stressed_max_dd = np.zeros(candidate_count, dtype=np.float64)
    minimum_balance = np.full(candidate_count, reference, dtype=np.float64)
    open_risk = np.zeros(candidate_count, dtype=np.float64)
    maximum_open_risk = np.zeros(candidate_count, dtype=np.float64)
    accepted_count = np.zeros(candidate_count, dtype=np.int32)
    hard_cap_skip_count = np.zeros(candidate_count, dtype=np.int32)

    component_actual = np.zeros((candidate_count, component_count), dtype=np.float64)
    component_stressed = np.zeros_like(component_actual)
    component_closed = np.zeros((candidate_count, component_count), dtype=np.int32)

    epoch_actual_net = np.zeros((candidate_count, epoch_count), dtype=np.float64)
    epoch_stressed_net = np.zeros_like(epoch_actual_net)
    epoch_actual_peak = np.zeros_like(epoch_actual_net)
    epoch_stressed_peak = np.zeros_like(epoch_actual_net)
    epoch_actual_dd = np.zeros_like(epoch_actual_net)
    epoch_stressed_dd = np.zeros_like(epoch_actual_net)
    epoch_minimum_balance = np.full_like(epoch_actual_net, np.inf)
    epoch_initialized = [False] * epoch_count

    open_positions: dict[str, tuple[np.ndarray, float, int]] = {}
    for event in events:
        if event.event == "BIRTH":
            if event.position_identifier in open_positions:
                raise RuntimeError("duplicate open position in retained path")
            aggregate_after = open_risk + event.planned_risk_usd
            admitted = aggregate_after <= hard_caps + tolerance
            accepted_count += admitted.astype(np.int32)
            hard_cap_skip_count += (~admitted).astype(np.int32)
            open_risk += np.where(admitted, event.planned_risk_usd, 0.0)
            maximum_open_risk = np.maximum(maximum_open_risk, open_risk)
            open_positions[event.position_identifier] = (
                admitted,
                event.planned_risk_usd,
                event.component_index,
            )
            continue

        if event.position_identifier not in open_positions:
            raise RuntimeError("retained-path close has no matching birth")
        admitted, planned_risk, component = open_positions.pop(
            event.position_identifier
        )
        e_index = epoch_index(event.server_time, epochs)
        if e_index is not None and not epoch_initialized[e_index]:
            epoch_actual_peak[:, e_index] = actual_balance
            epoch_stressed_peak[:, e_index] = stressed_balance
            epoch_minimum_balance[:, e_index] = np.minimum(
                actual_balance, stressed_balance
            )
            epoch_initialized[e_index] = True

        actual_increment = np.where(admitted, event.actual_net_usd, 0.0)
        stressed_increment = np.where(admitted, event.stressed_net_usd, 0.0)
        actual_balance += actual_increment
        stressed_balance += stressed_increment
        open_risk = np.maximum(
            0.0, open_risk - np.where(admitted, planned_risk, 0.0)
        )

        component_actual[:, component] += actual_increment
        component_stressed[:, component] += stressed_increment
        component_closed[:, component] += admitted.astype(np.int32)

        actual_peak = np.maximum(actual_peak, actual_balance)
        stressed_peak = np.maximum(stressed_peak, stressed_balance)
        actual_max_dd = np.maximum(
            actual_max_dd,
            np.where(
                actual_peak > 0.0,
                (actual_peak - actual_balance) / actual_peak,
                np.inf,
            ),
        )
        stressed_max_dd = np.maximum(
            stressed_max_dd,
            np.where(
                stressed_peak > 0.0,
                (stressed_peak - stressed_balance) / stressed_peak,
                np.inf,
            ),
        )
        minimum_balance = np.minimum(
            minimum_balance, np.minimum(actual_balance, stressed_balance)
        )

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
            epoch_minimum_balance[:, e_index] = np.minimum(
                epoch_minimum_balance[:, e_index],
                np.minimum(actual_balance, stressed_balance),
            )

    if open_positions:
        raise RuntimeError("retained path ended with open positions")
    if epoch_count and not all(epoch_initialized):
        raise RuntimeError("one or more declared epochs contain no close")
    if not (
        np.all(np.isfinite(actual_balance))
        and np.all(np.isfinite(stressed_balance))
        and np.all(np.isfinite(actual_max_dd))
        and np.all(np.isfinite(stressed_max_dd))
    ):
        raise RuntimeError("retained-path simulation produced non-finite economics")

    return {
        "actual_net": actual_balance - reference,
        "stressed_net": stressed_balance - reference,
        "raw_drawdown_pct": np.maximum(actual_max_dd, stressed_max_dd) * 100.0,
        "actual_drawdown_pct": actual_max_dd * 100.0,
        "stressed_drawdown_pct": stressed_max_dd * 100.0,
        "minimum_balance": minimum_balance,
        "maximum_open_risk": maximum_open_risk,
        "accepted_count": accepted_count,
        "hard_cap_skip_count": hard_cap_skip_count,
        "component_actual": component_actual,
        "component_stressed": component_stressed,
        "component_closed": component_closed,
        "epoch_actual_net": epoch_actual_net,
        "epoch_stressed_net": epoch_stressed_net,
        "epoch_raw_drawdown_pct": np.maximum(
            epoch_actual_dd, epoch_stressed_dd
        )
        * 100.0,
        "epoch_minimum_balance": epoch_minimum_balance,
    }


def rounded(value: Any) -> Any:
    if isinstance(value, np.generic):
        return rounded(value.item())
    if isinstance(value, float):
        if not np.isfinite(value):
            return None
        return round(value, 10)
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [rounded(item) for item in value]
    return value


def main() -> None:
    started = time.perf_counter()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    input_root = verify_inputs(config)
    components = [str(value) for value in config["components"]]
    reference = float(config["reference_capital_usd"])
    tolerance = float(config["aggregate_tolerance_usd"])

    accelerated = config["accelerated_anchor"]
    qualified = config["qualified_anchor"]
    accelerated_result = json.loads(
        (input_root / str(config["input"]["accelerated_result_file"])).read_text(
            encoding="utf-8"
        )
    )
    qualified_result = json.loads(
        (input_root / str(config["input"]["qualified_result_file"])).read_text(
            encoding="utf-8"
        )
    )
    if (
        accelerated_result.get("campaign") != accelerated["campaign"]
        or accelerated_result.get("status") != accelerated["result_status"]
        or qualified_result.get("campaign") != qualified["campaign"]
        or qualified_result.get("status") != qualified["result_status"]
    ):
        raise RuntimeError("closed MT5 result identity mismatch")

    accelerated_selection_events = load_events(
        input_root / str(config["input"]["accelerated_selection_lifecycle_file"]),
        accelerated["selection"],
        components,
    )
    accelerated_forward_events = load_events(
        input_root / str(config["input"]["accelerated_forward_lifecycle_file"]),
        accelerated["forward"],
        components,
    )
    qualified_selection_events = load_events(
        input_root / str(config["input"]["qualified_selection_lifecycle_file"]),
        qualified["selection"],
        components,
    )
    qualified_forward_events = load_events(
        input_root / str(config["input"]["qualified_forward_lifecycle_file"]),
        qualified["forward"],
        components,
    )

    for anchor, phase, cache_key in (
        (accelerated, "selection", "accelerated_selection_cache_file"),
        (accelerated, "forward", "accelerated_forward_cache_file"),
        (qualified, "selection", "qualified_selection_cache_file"),
        (qualified, "forward", "qualified_forward_cache_file"),
    ):
        declared = anchor[phase]
        cache = input_root / str(config["input"][cache_key])
        offsets = declared["cache_offsets"]
        if (
            abs(
                cache_double(cache, offsets["total_net_profit"])
                - float(declared["actual_net_usd"])
            )
            > 1.0e-9
            or abs(
                cache_double(cache, offsets["equity_drawdown_relative_pct"])
                - float(declared["native_equity_drawdown_pct"])
            )
            > 1.0e-9
        ):
            raise RuntimeError(f"{anchor['campaign']} {phase} native anchor mismatch")

    epochs = [
        {
            "id": str(item["id"]),
            "start_time": datetime.strptime(item["start"], TIME_FORMAT),
            "end_time": datetime.strptime(item["end"], TIME_FORMAT),
        }
        for item in config["selection_epochs"]
    ]
    sentinel_cap = np.asarray([1.0e12], dtype=np.float64)
    accelerated_anchor_metrics = simulate_retained_path(
        accelerated_selection_events,
        sentinel_cap,
        reference,
        tolerance,
        len(components),
        epochs,
    )
    qualified_anchor_metrics = simulate_retained_path(
        qualified_selection_events,
        sentinel_cap,
        reference,
        tolerance,
        len(components),
        epochs,
    )
    for metrics, declared, label in (
        (accelerated_anchor_metrics, accelerated["selection"], "accelerated"),
        (qualified_anchor_metrics, qualified["selection"], "qualified"),
    ):
        if (
            abs(float(metrics["actual_net"][0]) - float(declared["actual_net_usd"]))
            > 1.0e-7
            or abs(
                float(metrics["stressed_net"][0])
                - float(declared["stressed_net_usd"])
            )
            > 1.0e-7
            or abs(
                float(metrics["raw_drawdown_pct"][0])
                - float(declared["raw_retained_path_drawdown_pct"])
            )
            > 1.0e-7
        ):
            raise RuntimeError(f"{label} retained-path anchor mismatch")

    caps = np.asarray(
        config["candidate_hard_aggregate_risk_caps_usd"], dtype=np.float64
    )
    if (
        len(caps) != int(config["expected_candidates"])
        or len(np.unique(caps)) != len(caps)
        or np.any(caps <= 0.0)
    ):
        raise RuntimeError("candidate hard-cap grid is invalid")
    forward_max = float(
        config["forward_invariance"][
            "accelerated_forward_maximum_aggregate_planned_risk_usd"
        ]
    )
    selection_max = float(
        accelerated["selection"]["maximum_aggregate_planned_risk_usd"]
    )
    if np.any(caps <= forward_max + tolerance) or np.any(caps >= selection_max):
        raise RuntimeError("candidate caps violate forward-invariant binding bounds")

    selection = simulate_retained_path(
        accelerated_selection_events,
        caps,
        reference,
        tolerance,
        len(components),
        epochs,
    )
    if np.any(selection["hard_cap_skip_count"] <= 0):
        raise RuntimeError("one or more candidate caps never bind in selection")

    forward = simulate_retained_path(
        accelerated_forward_events,
        caps,
        reference,
        tolerance,
        len(components),
        [],
    )
    forward_config = config["forward_invariance"]
    if not (
        np.all(forward["accepted_count"] == int(accelerated["forward"]["births"]))
        and np.all(forward["hard_cap_skip_count"] == 0)
        and np.allclose(
            forward["actual_net"],
            float(forward_config["full_forward_actual_net_usd"]),
            atol=1.0e-7,
        )
        and np.allclose(
            forward["stressed_net"],
            float(forward_config["full_forward_stressed_net_usd"]),
            atol=1.0e-7,
        )
    ):
        raise RuntimeError("candidate hard cap changed the declared forward path")

    qualified_forward_metrics = simulate_retained_path(
        qualified_forward_events,
        sentinel_cap,
        reference,
        tolerance,
        len(components),
        [],
    )
    if (
        abs(
            float(qualified_forward_metrics["actual_net"][0])
            - float(qualified["forward"]["actual_net_usd"])
        )
        > 1.0e-7
        or abs(
            float(qualified_forward_metrics["stressed_net"][0])
            - float(qualified["forward"]["stressed_net_usd"])
        )
        > 1.0e-7
    ):
        raise RuntimeError("qualified forward lifecycle anchor mismatch")

    june_actual = sum(
        event.actual_net_usd
        for event in accelerated_forward_events
        if event.event == "CLOSE" and event.server_time < datetime(2026, 7, 1)
    )
    june_stressed = sum(
        event.stressed_net_usd
        for event in accelerated_forward_events
        if event.event == "CLOSE" and event.server_time < datetime(2026, 7, 1)
    )
    july_actual = sum(
        event.actual_net_usd
        for event in accelerated_forward_events
        if event.event == "CLOSE" and event.server_time >= datetime(2026, 7, 1)
    )
    july_stressed = sum(
        event.stressed_net_usd
        for event in accelerated_forward_events
        if event.event == "CLOSE" and event.server_time >= datetime(2026, 7, 1)
    )
    for observed, key in (
        (june_actual, "june_actual_net_usd"),
        (june_stressed, "june_stressed_net_usd"),
        (july_actual, "july_actual_net_usd"),
        (july_stressed, "july_stressed_net_usd"),
    ):
        if abs(observed - float(forward_config[key])) > 1.0e-7:
            raise RuntimeError("forward month invariant mismatch")

    dd_config = config["selection_drawdown_calibration"]
    accelerated_gap = (
        float(accelerated["selection"]["native_equity_drawdown_pct"])
        - float(accelerated["selection"]["raw_retained_path_drawdown_pct"])
    )
    if (
        abs(
            accelerated_gap
            - float(dd_config["accelerated_native_minus_raw_gap_percentage_points"])
        )
        > 1.0e-7
    ):
        raise RuntimeError("accelerated native-minus-raw DD gap mismatch")
    baseline_floor = float(qualified["selection"]["native_equity_drawdown_pct"]) + float(
        dd_config["qualified_native_floor_reserve_percentage_points"]
    )
    budgeted_dd = np.maximum(
        baseline_floor,
        selection["raw_drawdown_pct"]
        + accelerated_gap
        + float(dd_config["accelerated_gap_uncertainty_reserve_percentage_points"]),
    )

    profit_config = config["selection_profit_calibration"]
    profit_reserve = float(profit_config["retained_path_uncertainty_reserve_usd"])
    conservative_actual = selection["actual_net"] - profit_reserve
    conservative_stressed = selection["stressed_net"] - profit_reserve
    positive_gate = (
        (selection["actual_net"] > 0.0)
        & (selection["stressed_net"] > 0.0)
        & (selection["minimum_balance"] > 0.0)
    )
    profit_gate = (
        conservative_actual > float(qualified["selection"]["actual_net_usd"])
    ) & (
        conservative_stressed > float(qualified["selection"]["stressed_net_usd"])
    )
    dd_gate = budgeted_dd <= float(
        dd_config["hard_native_mt5_equity_drawdown_pct"]
    ) + 1.0e-12
    epoch_gate = (
        np.all(selection["epoch_actual_net"] > 0.0, axis=1)
        & np.all(selection["epoch_stressed_net"] > 0.0, axis=1)
        & np.all(selection["epoch_minimum_balance"] > 0.0, axis=1)
        & np.all(selection["epoch_raw_drawdown_pct"] <= 20.0 + 1.0e-12, axis=1)
    )
    selection_eligible = positive_gate & profit_gate & dd_gate & epoch_gate

    def record(index: int) -> dict[str, Any]:
        item: dict[str, Any] = {
            "hard_aggregate_risk_cap_usd": float(caps[index]),
            "actual_net_usd": float(selection["actual_net"][index]),
            "stressed_net_usd": float(selection["stressed_net"][index]),
            "conservative_actual_net_usd": float(conservative_actual[index]),
            "conservative_stressed_net_usd": float(conservative_stressed[index]),
            "actual_closed_balance_drawdown_pct": float(
                selection["actual_drawdown_pct"][index]
            ),
            "stressed_closed_balance_drawdown_pct": float(
                selection["stressed_drawdown_pct"][index]
            ),
            "raw_retained_path_drawdown_pct": float(
                selection["raw_drawdown_pct"][index]
            ),
            "budgeted_native_equity_drawdown_pct": float(budgeted_dd[index]),
            "minimum_balance_usd": float(selection["minimum_balance"][index]),
            "accepted_lifecycles": int(selection["accepted_count"][index]),
            "hard_cap_skips": int(selection["hard_cap_skip_count"][index]),
            "maximum_retained_open_risk_usd": float(
                selection["maximum_open_risk"][index]
            ),
            "selection_gates": {
                "positive": bool(positive_gate[index]),
                "conservative_profit_above_qualified": bool(profit_gate[index]),
                "budgeted_drawdown": bool(dd_gate[index]),
                "all_epochs": bool(epoch_gate[index]),
                "combined": bool(selection_eligible[index]),
            },
            "epochs": [],
            "components": [],
            "forward_invariant": {
                "accepted_lifecycles": int(forward["accepted_count"][index]),
                "hard_cap_skips": int(forward["hard_cap_skip_count"][index]),
                "actual_net_usd": float(forward["actual_net"][index]),
                "stressed_net_usd": float(forward["stressed_net"][index]),
                "native_equity_drawdown_pct": float(
                    forward_config["full_forward_native_equity_drawdown_pct"]
                ),
                "june_actual_net_usd": june_actual,
                "june_stressed_net_usd": june_stressed,
                "july_actual_net_usd": july_actual,
                "july_stressed_net_usd": july_stressed,
            },
        }
        for epoch_position, epoch in enumerate(epochs):
            item["epochs"].append(
                {
                    "id": epoch["id"],
                    "actual_net_usd": float(
                        selection["epoch_actual_net"][index, epoch_position]
                    ),
                    "stressed_net_usd": float(
                        selection["epoch_stressed_net"][index, epoch_position]
                    ),
                    "raw_closed_balance_drawdown_pct": float(
                        selection["epoch_raw_drawdown_pct"][index, epoch_position]
                    ),
                    "minimum_balance_usd": float(
                        selection["epoch_minimum_balance"][index, epoch_position]
                    ),
                }
            )
        for component_index, component in enumerate(components):
            item["components"].append(
                {
                    "component": component,
                    "closed": int(
                        selection["component_closed"][index, component_index]
                    ),
                    "actual_net_usd": float(
                        selection["component_actual"][index, component_index]
                    ),
                    "stressed_net_usd": float(
                        selection["component_stressed"][index, component_index]
                    ),
                }
            )
        return item

    def rank_key(index: int) -> tuple[Any, ...]:
        return (
            -float(conservative_stressed[index]),
            -float(conservative_actual[index]),
            -float(selection["stressed_net"][index]),
            -float(selection["epoch_stressed_net"][index, -1]),
            float(budgeted_dd[index]),
            float(caps[index]),
        )

    eligible_indices = [int(value) for value in np.flatnonzero(selection_eligible)]
    ranked = sorted(eligible_indices, key=rank_key)
    winner_index = ranked[0] if ranked else None
    diagnostic_indices = sorted(range(len(caps)), key=rank_key)
    dd_indices = sorted(
        [index for index in range(len(caps)) if bool(dd_gate[index])],
        key=rank_key,
    )
    top_count = int(config["output_top_records"])
    winner = record(winner_index) if winner_index is not None else None
    status = (
        "VALID_PROXY_COMPLETE_ONE_MT5_SHORTLIST"
        if winner is not None
        else "VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE"
    )

    result = {
        "schema": "zeta-dd20-profit-protected-risk-ceiling-proxy-raw-result-v1",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "campaign": config["campaign"],
        "implementation": {
            "contract_sha256": sha256(CONFIG_PATH),
            "script_sha256": sha256(SCRIPT_PATH),
            "input_manifest_sha256": config["input"][
                "canonical_manifest_sha256"
            ],
            "wall_time_seconds": time.perf_counter() - started,
            "accelerated_selection_lifecycle_and_native_anchor_gate": "PASS",
            "accelerated_forward_lifecycle_and_native_anchor_gate": "PASS",
            "qualified_selection_lifecycle_and_native_anchor_gate": "PASS",
            "qualified_forward_lifecycle_and_native_anchor_gate": "PASS",
            "closed_result_identity_gate": "PASS",
            "candidate_binding_and_forward_invariance_gate": "PASS",
        },
        "search": {
            "candidate_hard_caps": len(caps),
            "minimum_hard_cap_usd": float(np.min(caps)),
            "maximum_hard_cap_usd": float(np.max(caps)),
            "hard_cap_step_usd": 10.0,
            "all_candidates_bind_in_selection": True,
            "all_candidates_nonbinding_in_forward": True,
            "selection_individual_gate_counts": {
                "positive": int(np.count_nonzero(positive_gate)),
                "conservative_profit_above_qualified": int(
                    np.count_nonzero(profit_gate)
                ),
                "budgeted_drawdown": int(np.count_nonzero(dd_gate)),
                "all_epochs": int(np.count_nonzero(epoch_gate)),
                "combined": int(np.count_nonzero(selection_eligible)),
            },
            "selection_role": config["selection_role"],
        },
        "calibration": {
            "qualified_native_floor_pct": baseline_floor,
            "accelerated_native_minus_raw_gap_percentage_points": accelerated_gap,
            "accelerated_gap_uncertainty_reserve_percentage_points": float(
                dd_config["accelerated_gap_uncertainty_reserve_percentage_points"]
            ),
            "retained_path_profit_uncertainty_reserve_usd": profit_reserve,
            "hard_native_equity_drawdown_pct": float(
                dd_config["hard_native_mt5_equity_drawdown_pct"]
            ),
        },
        "closed_accelerated_anchor": {
            "hard_aggregate_risk_cap_usd": None,
            "actual_net_usd": float(accelerated_anchor_metrics["actual_net"][0]),
            "stressed_net_usd": float(
                accelerated_anchor_metrics["stressed_net"][0]
            ),
            "raw_retained_path_drawdown_pct": float(
                accelerated_anchor_metrics["raw_drawdown_pct"][0]
            ),
            "native_equity_drawdown_pct": float(
                accelerated["selection"]["native_equity_drawdown_pct"]
            ),
            "accepted_lifecycles": int(
                accelerated_anchor_metrics["accepted_count"][0]
            ),
            "rerun": False,
        },
        "closed_qualified_anchor": {
            "actual_net_usd": float(qualified_anchor_metrics["actual_net"][0]),
            "stressed_net_usd": float(
                qualified_anchor_metrics["stressed_net"][0]
            ),
            "raw_retained_path_drawdown_pct": float(
                qualified_anchor_metrics["raw_drawdown_pct"][0]
            ),
            "native_equity_drawdown_pct": float(
                qualified["selection"]["native_equity_drawdown_pct"]
            ),
            "accepted_lifecycles": int(
                qualified_anchor_metrics["accepted_count"][0]
            ),
            "rerun": False,
        },
        "selection_winner": winner,
        "top_qualified": [record(index) for index in ranked[:top_count]],
        "top_selection_diagnostic": [
            record(index) for index in diagnostic_indices[:top_count]
        ],
        "top_dd_eligible_diagnostic": [
            record(index) for index in dd_indices[:top_count]
        ],
        "mt5_shortlist": (
            [
                {
                    "role": config["selection_role"]["id"],
                    "hard_aggregate_risk_cap_usd": winner[
                        "hard_aggregate_risk_cap_usd"
                    ],
                    "selection_actual_net_usd": winner["actual_net_usd"],
                    "selection_stressed_net_usd": winner["stressed_net_usd"],
                    "conservative_selection_actual_net_usd": winner[
                        "conservative_actual_net_usd"
                    ],
                    "conservative_selection_stressed_net_usd": winner[
                        "conservative_stressed_net_usd"
                    ],
                    "selection_budgeted_drawdown_pct": winner[
                        "budgeted_native_equity_drawdown_pct"
                    ],
                    "forward_actual_net_usd": winner["forward_invariant"][
                        "actual_net_usd"
                    ],
                    "forward_stressed_net_usd": winner["forward_invariant"][
                        "stressed_net_usd"
                    ],
                }
            ]
            if winner is not None
            else []
        ),
        "boundary": {
            "proxy_completed": True,
            "retained_path_does_not_synthesize_freed_opportunities": True,
            "accelerated_candidate_rerun": False,
            "deferred_proxy_grid_rerun": False,
            "qualified_anchor_rerun": False,
            "prior_candidate_rerun": False,
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
                "wall_time_seconds": result["implementation"][
                    "wall_time_seconds"
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
