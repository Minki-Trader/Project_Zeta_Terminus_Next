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
    / "dd20-equity-high-watermark-terminal-lock-proxy-v1"
    / "output"
    / "proxy-result.json"
)
TIME_FORMAT = "%Y.%m.%d %H:%M:%S"


@dataclass(frozen=True)
class CloseEvent:
    server_time: datetime
    component_index: int
    actual_net_usd: float
    stressed_net_usd: float


@dataclass(frozen=True)
class Snapshot:
    server_time: datetime
    row_index: int
    stage: str
    result: str
    account_balance: float
    account_equity: float
    account_margin: float
    active_slots: int
    reserved_slots: int


@dataclass(frozen=True)
class AlignedSnapshot:
    snapshot: Snapshot
    stressed_balance: float
    stressed_equity: float
    closed_count: int
    balance_alignment_error_usd: float


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


def load_lifecycle(
    path: Path,
    expected_births: int,
    expected_closes: int,
    expected_actual: float,
    expected_stressed: float,
    components: list[str],
) -> list[CloseEvent]:
    component_index = {component: index for index, component in enumerate(components)}
    births: list[str] = []
    closes: list[str] = []
    close_events: list[CloseEvent] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for source in csv.DictReader(handle):
            event = source["event"]
            if event == "BIRTH":
                births.append(source["position_identifier"])
            elif event == "CLOSE":
                component = source["component_id"]
                if component not in component_index:
                    raise RuntimeError("lifecycle contains undeclared component")
                closes.append(source["position_identifier"])
                close_events.append(
                    CloseEvent(
                        server_time=datetime.strptime(
                            source["server_time"], TIME_FORMAT
                        ),
                        component_index=component_index[component],
                        actual_net_usd=float(source["actual_net_usd"]),
                        stressed_net_usd=float(source["stressed_net_usd"]),
                    )
                )
    if len(births) != expected_births or len(closes) != expected_closes:
        raise RuntimeError("lifecycle count mismatch")
    if len(set(births)) != len(births) or set(births) != set(closes):
        raise RuntimeError("lifecycle birth and close identities mismatch")
    if abs(sum(item.actual_net_usd for item in close_events) - expected_actual) > 1.0e-7:
        raise RuntimeError("lifecycle actual net mismatch")
    if (
        abs(sum(item.stressed_net_usd for item in close_events) - expected_stressed)
        > 1.0e-7
    ):
        raise RuntimeError("lifecycle stressed net mismatch")
    return close_events


def load_snapshots(path: Path, expected_rows: int) -> list[Snapshot]:
    snapshots: list[Snapshot] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row_index, source in enumerate(csv.DictReader(handle)):
            snapshots.append(
                Snapshot(
                    server_time=datetime.strptime(source["server_time"], TIME_FORMAT),
                    row_index=row_index,
                    stage=source["stage"],
                    result=source["result"],
                    account_balance=float(source["account_balance"]),
                    account_equity=float(source["account_equity"]),
                    account_margin=float(source["account_margin"]),
                    active_slots=int(source["active_slots"]),
                    reserved_slots=int(source["reserved_slots"]),
                )
            )
    if len(snapshots) != expected_rows:
        raise RuntimeError("candidate snapshot row count mismatch")
    if any(
        not np.isfinite(item.account_balance)
        or not np.isfinite(item.account_equity)
        or item.account_balance <= 0.0
        for item in snapshots
    ):
        raise RuntimeError("candidate snapshot capital is invalid")
    return sorted(snapshots, key=lambda item: (item.server_time, item.row_index))


def align_snapshots(
    snapshots: list[Snapshot],
    closes: list[CloseEvent],
    reference: float,
    maximum_error: float,
) -> tuple[list[AlignedSnapshot], float]:
    ordered_closes = sorted(
        enumerate(closes), key=lambda item: (item[1].server_time, item[0])
    )
    close_index = 0
    actual_balance = reference
    stressed_balance = reference
    closed_count = 0
    aligned: list[AlignedSnapshot] = []
    maximum_observed_error = 0.0

    snapshot_index = 0
    while snapshot_index < len(snapshots):
        current_time = snapshots[snapshot_index].server_time
        group_end = snapshot_index
        while (
            group_end < len(snapshots)
            and snapshots[group_end].server_time == current_time
        ):
            group_end += 1

        while (
            close_index < len(ordered_closes)
            and ordered_closes[close_index][1].server_time < current_time
        ):
            event = ordered_closes[close_index][1]
            actual_balance += event.actual_net_usd
            stressed_balance += event.stressed_net_usd
            closed_count += 1
            close_index += 1

        variants: list[tuple[float, float, int]] = [
            (actual_balance, stressed_balance, closed_count)
        ]
        local_close_index = close_index
        local_actual = actual_balance
        local_stressed = stressed_balance
        local_closed_count = closed_count
        while (
            local_close_index < len(ordered_closes)
            and ordered_closes[local_close_index][1].server_time == current_time
        ):
            event = ordered_closes[local_close_index][1]
            local_actual += event.actual_net_usd
            local_stressed += event.stressed_net_usd
            local_closed_count += 1
            variants.append((local_actual, local_stressed, local_closed_count))
            local_close_index += 1

        for snapshot in snapshots[snapshot_index:group_end]:
            matched = min(
                variants, key=lambda item: abs(item[0] - snapshot.account_balance)
            )
            error = abs(matched[0] - snapshot.account_balance)
            maximum_observed_error = max(maximum_observed_error, error)
            if error > maximum_error + 1.0e-12:
                raise RuntimeError(
                    f"snapshot/lifecycle balance alignment exceeds ${maximum_error:.3f}"
                )
            cost_drag = snapshot.account_balance - matched[1]
            aligned.append(
                AlignedSnapshot(
                    snapshot=snapshot,
                    stressed_balance=matched[1],
                    stressed_equity=snapshot.account_equity - cost_drag,
                    closed_count=matched[2],
                    balance_alignment_error_usd=error,
                )
            )

        actual_balance = local_actual
        stressed_balance = local_stressed
        closed_count = local_closed_count
        close_index = local_close_index
        snapshot_index = group_end

    return aligned, maximum_observed_error


def sampled_drawdown(snapshots: list[AlignedSnapshot], reference: float) -> float:
    peak = reference
    maximum = 0.0
    for item in snapshots:
        peak = max(peak, item.snapshot.account_equity)
        maximum = max(
            maximum,
            100.0 * (peak - item.snapshot.account_equity) / peak,
        )
    return maximum


def activation_from_closes(
    closes: list[CloseEvent], reference: float, growth_threshold: float
) -> tuple[datetime, float, float]:
    actual = reference
    stressed = reference
    for event in closes:
        actual += event.actual_net_usd
        stressed += event.stressed_net_usd
        if stressed >= reference + growth_threshold:
            return event.server_time, actual, stressed
    raise RuntimeError("selection never reaches terminal-lock arming threshold")


def epoch_index(server_time: datetime, epochs: list[dict[str, Any]]) -> int | None:
    for index, epoch in enumerate(epochs):
        if epoch["start_time"] <= server_time < epoch["end_time"]:
            return index
    return None


def epoch_nets_at_lock(
    closes: list[CloseEvent],
    closed_count: int,
    lock: AlignedSnapshot,
    reserve: float,
    epochs: list[dict[str, Any]],
) -> tuple[list[float], list[float]]:
    actual = [0.0 for _ in epochs]
    stressed = [0.0 for _ in epochs]
    for event in closes[:closed_count]:
        index = epoch_index(event.server_time, epochs)
        if index is not None:
            actual[index] += event.actual_net_usd
            stressed[index] += event.stressed_net_usd
    lock_epoch = epoch_index(lock.snapshot.server_time, epochs)
    if lock_epoch is None:
        raise RuntimeError("terminal lock is outside declared selection epochs")
    floating = lock.snapshot.account_equity - lock.snapshot.account_balance
    stressed_floating = lock.stressed_equity - lock.stressed_balance
    actual[lock_epoch] += floating - reserve
    stressed[lock_epoch] += stressed_floating - reserve
    return actual, stressed


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
    reference = float(config["reference_capital_usd"])
    selection_config = config["selection_observation"]
    forward_config = config["forward_observation"]
    components = [
        "ZT-M30-US30-RANGE-COMP-61f61deaba",
        "ZT-M30-US30-RANGE-COMP-64efb16616",
        "ZT-H1-US100-CROSS-IN-14b72317b7",
        "ZT-M30-US30-INTRADAY-R-2eb111fc46",
        "ZT-H1-US30-RETURN-I-c870a788ec",
        "ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8",
    ]

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
    predecessor_result = json.loads(
        (
            input_root / str(config["input"]["closed_predecessor_result_file"])
        ).read_text(encoding="utf-8")
    )
    if (
        accelerated_result.get("campaign")
        != "dd20-deferred-profit-accelerator-mt5-v1"
        or accelerated_result.get("status")
        != "VALID_MT5_COMPLETE_SELECTION_DD20_FAIL_FORWARD_ALL_GATES_PASS"
        or qualified_result.get("campaign")
        != config["qualified_anchor"]["campaign"]
        or qualified_result.get("status")
        != config["qualified_anchor"]["result_status"]
        or predecessor_result.get("campaign")
        != "dd20-profit-protected-risk-ceiling-proxy-v1"
        or predecessor_result.get("status")
        != "VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE"
    ):
        raise RuntimeError("closed predecessor identity mismatch")

    selection_closes = load_lifecycle(
        input_root / str(config["input"]["selection_lifecycle_file"]),
        int(selection_config["births"]),
        int(selection_config["closed_lifecycles"]),
        float(selection_config["actual_net_usd"]),
        float(selection_config["stressed_net_usd"]),
        components,
    )
    forward_closes = load_lifecycle(
        input_root / str(config["input"]["forward_lifecycle_file"]),
        int(forward_config["births"]),
        int(forward_config["closed_lifecycles"]),
        float(forward_config["actual_net_usd"]),
        float(forward_config["stressed_net_usd"]),
        components,
    )
    selection_snapshots = load_snapshots(
        input_root / str(config["input"]["selection_candidate_file"]),
        int(selection_config["candidate_rows"]),
    )
    forward_snapshots = load_snapshots(
        input_root / str(config["input"]["forward_candidate_file"]),
        int(forward_config["candidate_rows"]),
    )
    alignment_error = float(
        config["snapshot_alignment"][
            "maximum_allowed_balance_alignment_error_usd"
        ]
    )
    aligned_selection, selection_alignment_max = align_snapshots(
        selection_snapshots, selection_closes, reference, alignment_error
    )
    aligned_forward, forward_alignment_max = align_snapshots(
        forward_snapshots, forward_closes, reference, alignment_error
    )

    selection_cache = input_root / str(config["input"]["selection_cache_file"])
    forward_cache = input_root / str(config["input"]["forward_cache_file"])
    for cache, declared, phase in (
        (selection_cache, selection_config, "selection"),
        (forward_cache, forward_config, "forward"),
    ):
        offsets = declared["cache_offsets"]
        if (
            abs(
                cache_double(cache, offsets["total_net_profit"])
                - float(declared["actual_net_usd"])
            )
            > 1.0e-9
            or abs(
                cache_double(cache, offsets["equity_drawdown_relative_pct"])
                - float(declared["native_maximum_equity_drawdown_pct"])
            )
            > 1.0e-9
        ):
            raise RuntimeError(f"accelerated {phase} native anchor mismatch")

    full_sampled_dd = sampled_drawdown(aligned_selection, reference)
    if (
        abs(
            full_sampled_dd
            - float(selection_config["sampled_maximum_equity_drawdown_pct"])
        )
        > 1.0e-9
    ):
        raise RuntimeError("selection sampled-equity DD anchor mismatch")
    native_gap = (
        float(selection_config["native_maximum_equity_drawdown_pct"])
        - full_sampled_dd
    )
    if (
        abs(
            native_gap
            - float(
                selection_config[
                    "native_minus_sampled_gap_percentage_points"
                ]
            )
        )
        > 1.0e-9
    ):
        raise RuntimeError("selection sampled-to-native gap mismatch")

    growth_threshold = float(config["fixed_accelerator"]["activation_growth_threshold_usd"])
    activation_time, activation_actual, activation_stressed = activation_from_closes(
        selection_closes, reference, growth_threshold
    )
    if (
        activation_time
        != datetime.strptime(selection_config["activation_time_server"], TIME_FORMAT)
        or abs(
            activation_actual
            - float(selection_config["activation_actual_balance_usd"])
        )
        > 1.0e-7
        or abs(
            activation_stressed
            - float(selection_config["activation_stressed_balance_usd"])
        )
        > 1.0e-7
    ):
        raise RuntimeError("terminal-lock activation anchor mismatch")

    forward_stressed = reference
    forward_maximum_stressed = reference
    for event in forward_closes:
        forward_stressed += event.stressed_net_usd
        forward_maximum_stressed = max(forward_maximum_stressed, forward_stressed)
    if (
        forward_maximum_stressed >= reference + growth_threshold
        or abs(
            forward_maximum_stressed
            - float(forward_config["maximum_stressed_closed_balance_usd"])
        )
        > 1.0e-7
    ):
        raise RuntimeError("forward arming-invariance anchor mismatch")

    trigger_config = config["terminal_lock"]
    triggers = np.asarray(
        trigger_config["candidate_drawdown_triggers_pct"], dtype=np.float64
    )
    if (
        len(triggers) != int(trigger_config["expected_candidates"])
        or len(np.unique(triggers)) != len(triggers)
        or np.any(triggers <= 0.0)
        or np.any(triggers >= 20.0)
    ):
        raise RuntimeError("terminal-lock trigger grid is invalid")
    reserve = float(trigger_config["liquidation_and_proxy_reserve_usd"])
    candidate_count = len(triggers)
    locked = np.zeros(candidate_count, dtype=bool)
    peak_equity = np.full(candidate_count, reference, dtype=np.float64)
    maximum_sampled_dd = np.zeros(candidate_count, dtype=np.float64)
    lock_snapshot_index = np.full(candidate_count, -1, dtype=np.int32)
    lock_current_dd = np.zeros(candidate_count, dtype=np.float64)
    actual_net = np.zeros(candidate_count, dtype=np.float64)
    stressed_net = np.zeros(candidate_count, dtype=np.float64)

    for index, item in enumerate(aligned_selection):
        active = ~locked
        if not np.any(active):
            break
        equity = item.snapshot.account_equity
        peak_equity[active] = np.maximum(peak_equity[active], equity)
        current_dd = np.where(
            peak_equity > 0.0,
            100.0 * (peak_equity - equity) / peak_equity,
            np.inf,
        )
        maximum_sampled_dd[active] = np.maximum(
            maximum_sampled_dd[active], current_dd[active]
        )
        armed = item.stressed_balance >= reference + growth_threshold
        fires = active & armed & (current_dd >= triggers - 1.0e-12)
        if np.any(fires):
            lock_snapshot_index[fires] = index
            lock_current_dd[fires] = current_dd[fires]
            actual_net[fires] = equity - reference - reserve
            stressed_net[fires] = item.stressed_equity - reference - reserve
            locked[fires] = True

    if not np.all(locked):
        raise RuntimeError("one or more terminal-lock candidates never fire")

    epochs = [
        {
            "id": str(item["id"]),
            "start_time": datetime.strptime(item["start"], TIME_FORMAT),
            "end_time": datetime.strptime(item["end"], TIME_FORMAT),
        }
        for item in config["selection_epochs"]
    ]
    epoch_actual = np.zeros((candidate_count, len(epochs)), dtype=np.float64)
    epoch_stressed = np.zeros_like(epoch_actual)
    for candidate_index, snapshot_index in enumerate(lock_snapshot_index):
        lock = aligned_selection[int(snapshot_index)]
        actual_values, stressed_values = epoch_nets_at_lock(
            selection_closes,
            lock.closed_count,
            lock,
            reserve,
            epochs,
        )
        epoch_actual[candidate_index] = np.asarray(actual_values, dtype=np.float64)
        epoch_stressed[candidate_index] = np.asarray(
            stressed_values, dtype=np.float64
        )
        if (
            abs(float(np.sum(epoch_actual[candidate_index])) - actual_net[candidate_index])
            > 1.0e-7
            or abs(
                float(np.sum(epoch_stressed[candidate_index]))
                - stressed_net[candidate_index]
            )
            > 1.0e-7
        ):
            raise RuntimeError("terminal-lock epoch net does not reconcile")

    dd_config = config["selection_drawdown_calibration"]
    qualified_floor = float(
        config["qualified_anchor"]["selection_native_equity_drawdown_pct"]
    ) + float(dd_config["qualified_native_floor_reserve_percentage_points"])
    budgeted_dd = np.maximum(
        qualified_floor,
        maximum_sampled_dd
        + native_gap
        + float(
            dd_config[
                "terminal_detection_and_liquidation_reserve_percentage_points"
            ]
        ),
    )
    qualified_actual = float(
        config["qualified_anchor"]["selection_actual_net_usd"]
    )
    qualified_stressed = float(
        config["qualified_anchor"]["selection_stressed_net_usd"]
    )
    positive_gate = (actual_net > 0.0) & (stressed_net > 0.0)
    profit_gate = (actual_net > qualified_actual) & (
        stressed_net > qualified_stressed
    )
    dd_gate = budgeted_dd <= float(
        dd_config["hard_native_mt5_equity_drawdown_pct"]
    ) + 1.0e-12
    epoch_gate = np.all(epoch_actual > 0.0, axis=1) & np.all(
        epoch_stressed > 0.0, axis=1
    )
    selection_eligible = positive_gate & profit_gate & dd_gate & epoch_gate

    def record(index: int) -> dict[str, Any]:
        lock = aligned_selection[int(lock_snapshot_index[index])]
        return {
            "equity_drawdown_trigger_pct": float(triggers[index]),
            "lock_time_server": lock.snapshot.server_time.strftime(TIME_FORMAT),
            "lock_stage": lock.snapshot.stage,
            "lock_result": lock.snapshot.result,
            "lock_account_balance_usd": lock.snapshot.account_balance,
            "lock_account_equity_usd": lock.snapshot.account_equity,
            "lock_stressed_balance_usd": lock.stressed_balance,
            "lock_stressed_equity_usd": lock.stressed_equity,
            "lock_account_margin_usd": lock.snapshot.account_margin,
            "lock_active_slots": lock.snapshot.active_slots,
            "lock_reserved_slots": lock.snapshot.reserved_slots,
            "liquidation_and_proxy_reserve_usd": reserve,
            "actual_terminal_net_usd": float(actual_net[index]),
            "stressed_terminal_net_usd": float(stressed_net[index]),
            "sampled_current_drawdown_at_lock_pct": float(lock_current_dd[index]),
            "maximum_sampled_drawdown_through_lock_pct": float(
                maximum_sampled_dd[index]
            ),
            "budgeted_native_equity_drawdown_pct": float(budgeted_dd[index]),
            "closed_lifecycles_before_lock": int(lock.closed_count),
            "balance_alignment_error_usd": lock.balance_alignment_error_usd,
            "epochs": [
                {
                    "id": epoch["id"],
                    "actual_net_usd": float(epoch_actual[index, epoch_position]),
                    "stressed_net_usd": float(
                        epoch_stressed[index, epoch_position]
                    ),
                }
                for epoch_position, epoch in enumerate(epochs)
            ],
            "selection_gates": {
                "positive": bool(positive_gate[index]),
                "profit_above_qualified": bool(profit_gate[index]),
                "budgeted_drawdown": bool(dd_gate[index]),
                "all_epochs": bool(epoch_gate[index]),
                "combined": bool(selection_eligible[index]),
            },
            "forward_invariant": {
                "terminal_lock_armed": False,
                "actual_net_usd": float(forward_config["actual_net_usd"]),
                "stressed_net_usd": float(forward_config["stressed_net_usd"]),
                "native_equity_drawdown_pct": float(
                    forward_config["native_maximum_equity_drawdown_pct"]
                ),
                "june_actual_net_usd": float(
                    forward_config["june_actual_net_usd"]
                ),
                "june_stressed_net_usd": float(
                    forward_config["june_stressed_net_usd"]
                ),
                "july_actual_net_usd": float(
                    forward_config["july_actual_net_usd"]
                ),
                "july_stressed_net_usd": float(
                    forward_config["july_stressed_net_usd"]
                ),
            },
        }

    def rank_key(index: int) -> tuple[Any, ...]:
        return (
            -float(stressed_net[index]),
            -float(actual_net[index]),
            -float(epoch_stressed[index, -1]),
            float(budgeted_dd[index]),
            -float(triggers[index]),
        )

    eligible_indices = [int(value) for value in np.flatnonzero(selection_eligible)]
    ranked = sorted(eligible_indices, key=rank_key)
    winner_index = ranked[0] if ranked else None
    diagnostic_indices = sorted(range(candidate_count), key=rank_key)
    dd_indices = sorted(
        [index for index in range(candidate_count) if bool(dd_gate[index])],
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
        "schema": "zeta-dd20-equity-high-watermark-terminal-lock-proxy-raw-result-v1",
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
            "accelerated_selection_lifecycle_native_and_sampled_anchor_gate": "PASS",
            "accelerated_forward_lifecycle_and_native_anchor_gate": "PASS",
            "qualified_result_identity_gate": "PASS",
            "closed_predecessor_identity_gate": "PASS",
            "selection_snapshot_balance_alignment_gate": "PASS",
            "forward_never_arms_gate": "PASS",
        },
        "search": {
            "candidate_triggers": candidate_count,
            "minimum_trigger_pct": float(np.min(triggers)),
            "maximum_trigger_pct": float(np.max(triggers)),
            "trigger_step_percentage_points": 0.5,
            "all_candidates_fired_in_selection": True,
            "forward_terminal_lock_armed": False,
            "selection_individual_gate_counts": {
                "positive": int(np.count_nonzero(positive_gate)),
                "profit_above_qualified": int(np.count_nonzero(profit_gate)),
                "budgeted_drawdown": int(np.count_nonzero(dd_gate)),
                "all_epochs": int(np.count_nonzero(epoch_gate)),
                "combined": int(np.count_nonzero(selection_eligible)),
            },
            "selection_role": config["selection_role"],
        },
        "calibration": {
            "qualified_native_floor_pct": qualified_floor,
            "selection_full_path_sampled_dd_pct": full_sampled_dd,
            "selection_native_minus_sampled_gap_percentage_points": native_gap,
            "terminal_detection_and_liquidation_reserve_percentage_points": float(
                dd_config[
                    "terminal_detection_and_liquidation_reserve_percentage_points"
                ]
            ),
            "liquidation_and_proxy_reserve_usd": reserve,
            "selection_snapshot_maximum_alignment_error_usd": selection_alignment_max,
            "forward_snapshot_maximum_alignment_error_usd": forward_alignment_max,
        },
        "closed_accelerated_anchor": {
            "actual_net_usd": float(selection_config["actual_net_usd"]),
            "stressed_net_usd": float(selection_config["stressed_net_usd"]),
            "sampled_equity_drawdown_pct": full_sampled_dd,
            "native_equity_drawdown_pct": float(
                selection_config["native_maximum_equity_drawdown_pct"]
            ),
            "rerun": False,
        },
        "closed_qualified_anchor": {
            "actual_net_usd": qualified_actual,
            "stressed_net_usd": qualified_stressed,
            "native_equity_drawdown_pct": float(
                config["qualified_anchor"]["selection_native_equity_drawdown_pct"]
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
                    "equity_drawdown_trigger_pct": winner[
                        "equity_drawdown_trigger_pct"
                    ],
                    "lock_time_server": winner["lock_time_server"],
                    "selection_actual_terminal_net_usd": winner[
                        "actual_terminal_net_usd"
                    ],
                    "selection_stressed_terminal_net_usd": winner[
                        "stressed_terminal_net_usd"
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
            "terminal_lock_is_permanent_and_has_no_reset": True,
            "accelerated_candidate_rerun": False,
            "risk_ceiling_grid_rerun": False,
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
