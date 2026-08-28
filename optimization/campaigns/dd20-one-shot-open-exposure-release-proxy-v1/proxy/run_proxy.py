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


SCRIPT_PATH = Path(__file__).resolve()
CAMPAIGN_ROOT = SCRIPT_PATH.parents[1]
REPOSITORY_ROOT = SCRIPT_PATH.parents[4]
CONFIG_PATH = CAMPAIGN_ROOT / "config" / "proxy-contract.json"
OUTPUT_PATH = (
    REPOSITORY_ROOT
    / "optimization"
    / "artifacts"
    / "raw"
    / "dd20-one-shot-open-exposure-release-proxy-v1"
    / "output"
    / "proxy-result.json"
)
TIME_FORMAT = "%Y.%m.%d %H:%M:%S"


@dataclass(frozen=True)
class CloseTrade:
    position_identifier: str
    component_id: str
    entry_time: datetime
    close_time: datetime
    order: int
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


@dataclass(frozen=True)
class NetEvent:
    server_time: datetime
    order: int
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


def load_lifecycle(
    path: Path,
    expected_births: int,
    expected_closes: int,
    expected_actual: float,
    expected_stressed: float,
    components: list[str],
) -> list[CloseTrade]:
    component_set = set(components)
    births: list[str] = []
    closes: list[str] = []
    trades: list[CloseTrade] = []
    last_close_time: datetime | None = None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row_index, source in enumerate(csv.DictReader(handle)):
            event = source["event"]
            if event == "BIRTH":
                births.append(source["position_identifier"])
                continue
            if event != "CLOSE":
                continue
            component = source["component_id"]
            if component not in component_set:
                raise RuntimeError("lifecycle contains undeclared component")
            close_time = datetime.strptime(source["server_time"], TIME_FORMAT)
            if last_close_time is not None and close_time < last_close_time:
                raise RuntimeError("lifecycle closes are not chronological")
            last_close_time = close_time
            identifier = source["position_identifier"]
            closes.append(identifier)
            trades.append(
                CloseTrade(
                    position_identifier=identifier,
                    component_id=component,
                    entry_time=datetime.strptime(
                        source["entry_time_server"], TIME_FORMAT
                    ),
                    close_time=close_time,
                    order=row_index,
                    actual_net_usd=float(source["actual_net_usd"]),
                    stressed_net_usd=float(source["stressed_net_usd"]),
                )
            )
    if len(births) != expected_births or len(closes) != expected_closes:
        raise RuntimeError("lifecycle count mismatch")
    if (
        len(set(births)) != len(births)
        or len(set(closes)) != len(closes)
        or set(births) != set(closes)
    ):
        raise RuntimeError("lifecycle birth and close identities mismatch")
    if abs(sum(item.actual_net_usd for item in trades) - expected_actual) > 1.0e-7:
        raise RuntimeError("lifecycle actual net mismatch")
    if abs(sum(item.stressed_net_usd for item in trades) - expected_stressed) > 1.0e-7:
        raise RuntimeError("lifecycle stressed net mismatch")
    if any(item.actual_net_usd - item.stressed_net_usd < -1.0e-9 for item in trades):
        raise RuntimeError("lifecycle doubled-cost drag is negative")
    return trades


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
    if any(item.account_balance <= 0.0 or item.account_equity <= 0.0 for item in snapshots):
        raise RuntimeError("candidate snapshot capital is invalid")
    return sorted(snapshots, key=lambda item: (item.server_time, item.row_index))


def align_snapshots(
    snapshots: list[Snapshot],
    closes: list[CloseTrade],
    reference: float,
    maximum_error: float,
) -> tuple[list[AlignedSnapshot], float]:
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
        while group_end < len(snapshots) and snapshots[group_end].server_time == current_time:
            group_end += 1
        while close_index < len(closes) and closes[close_index].close_time < current_time:
            event = closes[close_index]
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
            local_close_index < len(closes)
            and closes[local_close_index].close_time == current_time
        ):
            event = closes[local_close_index]
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
                raise RuntimeError("snapshot/lifecycle balance alignment exceeds tolerance")
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


def sampled_drawdown(values: list[float], reference: float) -> tuple[float, float]:
    peak = reference
    maximum = 0.0
    minimum = reference
    for value in values:
        peak = max(peak, value)
        maximum = max(maximum, 100.0 * (peak - value) / peak)
        minimum = min(minimum, value)
    return maximum, minimum


def activation_from_closes(
    closes: list[CloseTrade], reference: float, growth_threshold: float
) -> tuple[datetime, float, float]:
    actual = reference
    stressed = reference
    for event in closes:
        actual += event.actual_net_usd
        stressed += event.stressed_net_usd
        if stressed >= reference + growth_threshold:
            return event.close_time, actual, stressed
    raise RuntimeError("selection never reaches release arming threshold")


def maximum_stressed_balance(closes: list[CloseTrade], reference: float) -> float:
    balance = reference
    maximum = reference
    for event in closes:
        balance += event.stressed_net_usd
        maximum = max(maximum, balance)
    return maximum


def epoch_index(server_time: datetime, epochs: list[dict[str, Any]]) -> int | None:
    for index, epoch in enumerate(epochs):
        if epoch["start_time"] <= server_time < epoch["end_time"]:
            return index
    return None


def closed_path_metrics(
    closes: list[CloseTrade],
    closed_count_at_release: int,
    affected_ids: set[str],
    retained_fraction: float,
    release_time: datetime,
    release_actual_net: float,
    release_stressed_net: float,
    reference: float,
    epochs: list[dict[str, Any]],
) -> dict[str, Any]:
    events: list[NetEvent] = []
    for index, trade in enumerate(closes):
        scale = retained_fraction if trade.position_identifier in affected_ids else 1.0
        events.append(
            NetEvent(
                server_time=trade.close_time,
                order=trade.order + (1 if index >= closed_count_at_release else 0),
                actual_net_usd=trade.actual_net_usd * scale,
                stressed_net_usd=trade.stressed_net_usd * scale,
            )
        )
    release_order = (
        closes[closed_count_at_release - 1].order + 1
        if closed_count_at_release > 0
        else -1
    )
    events.append(
        NetEvent(
            server_time=release_time,
            order=release_order,
            actual_net_usd=release_actual_net,
            stressed_net_usd=release_stressed_net,
        )
    )
    events.sort(key=lambda item: (item.server_time, item.order))
    actual = reference
    stressed = reference
    actual_peak = reference
    stressed_peak = reference
    actual_dd = 0.0
    stressed_dd = 0.0
    minimum_actual = reference
    minimum_stressed = reference
    epoch_actual = [0.0 for _ in epochs]
    epoch_stressed = [0.0 for _ in epochs]
    for event in events:
        actual += event.actual_net_usd
        stressed += event.stressed_net_usd
        actual_peak = max(actual_peak, actual)
        stressed_peak = max(stressed_peak, stressed)
        actual_dd = max(actual_dd, 100.0 * (actual_peak - actual) / actual_peak)
        stressed_dd = max(
            stressed_dd, 100.0 * (stressed_peak - stressed) / stressed_peak
        )
        minimum_actual = min(minimum_actual, actual)
        minimum_stressed = min(minimum_stressed, stressed)
        index = epoch_index(event.server_time, epochs)
        if index is None:
            raise RuntimeError("release economic event is outside selection epochs")
        epoch_actual[index] += event.actual_net_usd
        epoch_stressed[index] += event.stressed_net_usd
    return {
        "actual_net_usd": actual - reference,
        "stressed_net_usd": stressed - reference,
        "actual_closed_balance_drawdown_pct": actual_dd,
        "stressed_closed_balance_drawdown_pct": stressed_dd,
        "minimum_actual_closed_balance_usd": minimum_actual,
        "minimum_stressed_closed_balance_usd": minimum_stressed,
        "epoch_actual": epoch_actual,
        "epoch_stressed": epoch_stressed,
    }


def find_lock_snapshot(
    aligned: list[AlignedSnapshot], record: dict[str, Any]
) -> int:
    lock_time = datetime.strptime(record["lock_time_server"], TIME_FORMAT)
    matches: list[int] = []
    for index, item in enumerate(aligned):
        snapshot = item.snapshot
        if (
            snapshot.server_time == lock_time
            and snapshot.stage == record["lock_stage"]
            and snapshot.result == record["lock_result"]
            and abs(snapshot.account_balance - float(record["lock_account_balance_usd"]))
            <= 1.0e-9
            and abs(snapshot.account_equity - float(record["lock_account_equity_usd"]))
            <= 1.0e-9
            and item.closed_count == int(record["closed_lifecycles_before_lock"])
        ):
            matches.append(index)
    if not matches:
        raise RuntimeError("recorded terminal-lock snapshot cannot be located")
    return matches[0]


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
    terminal_raw = json.loads(
        (
            input_root / str(config["input"]["terminal_lock_raw_result_file"])
        ).read_text(encoding="utf-8")
    )
    terminal_result = json.loads(
        (input_root / str(config["input"]["terminal_lock_result_file"])).read_text(
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
        or qualified_result.get("campaign") != config["qualified_anchor"]["campaign"]
        or qualified_result.get("status")
        != config["qualified_anchor"]["result_status"]
        or terminal_raw.get("campaign")
        != "dd20-equity-high-watermark-terminal-lock-proxy-v1"
        or terminal_raw.get("status")
        != "VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE"
        or terminal_result.get("campaign")
        != "dd20-equity-high-watermark-terminal-lock-proxy-v1"
        or terminal_result.get("status")
        != "VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE"
        or predecessor_result.get("campaign")
        != "dd20-drawdown-responsive-exposure-proxy-v1"
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
    snapshots = load_snapshots(
        input_root / str(config["input"]["selection_candidate_file"]),
        int(selection_config["candidate_rows"]),
    )
    alignment_tolerance = float(
        config["snapshot_alignment"]["maximum_allowed_balance_alignment_error_usd"]
    )
    aligned, alignment_maximum = align_snapshots(
        snapshots, selection_closes, reference, alignment_tolerance
    )

    for cache_name, declared, phase in (
        (config["input"]["selection_cache_file"], selection_config, "selection"),
        (config["input"]["forward_cache_file"], forward_config, "forward"),
    ):
        cache = input_root / str(cache_name)
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

    baseline_actual_equity = [item.snapshot.account_equity for item in aligned]
    baseline_stressed_equity = [item.stressed_equity for item in aligned]
    baseline_sampled_dd, _ = sampled_drawdown(baseline_actual_equity, reference)
    if (
        abs(
            baseline_sampled_dd
            - float(selection_config["sampled_maximum_equity_drawdown_pct"])
        )
        > 1.0e-9
        or abs(
            float(selection_config["native_maximum_equity_drawdown_pct"])
            - baseline_sampled_dd
            - float(selection_config["native_minus_sampled_gap_percentage_points"])
        )
        > 1.0e-9
    ):
        raise RuntimeError("selection sampled/native DD anchor mismatch")

    growth_threshold = float(config["fixed_accelerator"]["activation_growth_threshold_usd"])
    activation_time, activation_actual, activation_stressed = activation_from_closes(
        selection_closes, reference, growth_threshold
    )
    if (
        activation_time
        != datetime.strptime(selection_config["activation_time_server"], TIME_FORMAT)
        or abs(activation_actual - float(selection_config["activation_actual_balance_usd"]))
        > 1.0e-7
        or abs(
            activation_stressed
            - float(selection_config["activation_stressed_balance_usd"])
        )
        > 1.0e-7
    ):
        raise RuntimeError("release activation anchor mismatch")
    forward_maximum = maximum_stressed_balance(forward_closes, reference)
    if (
        forward_maximum >= reference + growth_threshold
        or abs(
            forward_maximum
            - float(forward_config["maximum_stressed_closed_balance_usd"])
        )
        > 1.0e-7
    ):
        raise RuntimeError("forward arming-invariance anchor mismatch")

    release_config = config["open_exposure_release"]
    triggers = [
        float(value) for value in release_config["candidate_drawdown_triggers_pct"]
    ]
    retained_fractions = [
        float(value)
        for value in release_config["candidate_retained_open_exposure_fractions"]
    ]
    if (
        len(triggers) * len(retained_fractions)
        != int(release_config["expected_candidates"])
        or len(set(triggers)) != len(triggers)
        or len(set(retained_fractions)) != len(retained_fractions)
        or any(value <= 0.0 or value >= 18.0 for value in triggers)
        or any(value < 0.0 or value >= 1.0 for value in retained_fractions)
    ):
        raise RuntimeError("open-exposure release grid is invalid")

    terminal_records = {
        float(record["equity_drawdown_trigger_pct"]): record
        for record in terminal_raw["top_selection_diagnostic"]
    }
    if len(terminal_records) != int(selection_config["terminal_lock_source_triggers"]):
        raise RuntimeError("terminal-lock source trigger count mismatch")
    if any(trigger not in terminal_records for trigger in triggers):
        raise RuntimeError("declared trigger is absent from terminal-lock source")

    nonbinding_counts: list[int] = []
    for trigger in (18.0, 18.5, 19.0):
        record = terminal_records[trigger]
        lock_index = find_lock_snapshot(aligned, record)
        lock = aligned[lock_index]
        lock_time = lock.snapshot.server_time
        affected = [
            (index, trade)
            for index, trade in enumerate(selection_closes)
            if index >= lock.closed_count
            and trade.close_time >= lock_time
            and (
                trade.entry_time < lock_time
                or (
                    trade.entry_time == lock_time
                    and lock.snapshot.result == "POSITION_OPEN"
                )
            )
        ]
        nonbinding_counts.append(len(affected))
    if any(nonbinding_counts):
        raise RuntimeError("excluded 18%-19% trigger range is not nonbinding")

    epochs = [
        {
            "id": str(item["id"]),
            "start_time": datetime.strptime(item["start"], TIME_FORMAT),
            "end_time": datetime.strptime(item["end"], TIME_FORMAT),
        }
        for item in config["selection_epochs"]
    ]
    action_reserve = float(release_config["release_action_and_proxy_reserve_usd"])
    global_profit_reserve = float(
        release_config["selection_profit_uncertainty_reserve_usd"]
    )
    dd_config = config["selection_drawdown_calibration"]
    native_gap = float(dd_config["sampled_to_native_gap_percentage_points"])
    qualified_dd_floor = float(
        config["qualified_anchor"]["selection_native_equity_drawdown_pct"]
    ) + float(dd_config["qualified_native_floor_reserve_percentage_points"])
    release_dd_reserve = float(
        dd_config[
            "release_detection_transition_and_execution_reserve_percentage_points"
        ]
    )
    hard_dd = float(dd_config["hard_native_mt5_equity_drawdown_pct"])
    qualified_actual = float(config["qualified_anchor"]["selection_actual_net_usd"])
    qualified_stressed = float(config["qualified_anchor"]["selection_stressed_net_usd"])

    records: list[dict[str, Any]] = []
    binding_lock_times: set[str] = set()
    for trigger in triggers:
        source_record = terminal_records[trigger]
        lock_index = find_lock_snapshot(aligned, source_record)
        lock = aligned[lock_index]
        lock_time = lock.snapshot.server_time
        affected_pairs = [
            (index, trade)
            for index, trade in enumerate(selection_closes)
            if index >= lock.closed_count
            and trade.close_time >= lock_time
            and (
                trade.entry_time < lock_time
                or (
                    trade.entry_time == lock_time
                    and lock.snapshot.result == "POSITION_OPEN"
                )
            )
        ]
        if not affected_pairs:
            raise RuntimeError("declared release trigger has no open exposure")
        binding_lock_times.add(lock_time.strftime(TIME_FORMAT))
        affected_ids = {trade.position_identifier for _, trade in affected_pairs}
        affected_actual = sum(trade.actual_net_usd for _, trade in affected_pairs)
        affected_stressed = sum(trade.stressed_net_usd for _, trade in affected_pairs)
        affected_drag = affected_actual - affected_stressed
        floating_actual = lock.snapshot.account_equity - lock.snapshot.account_balance
        floating_stressed = lock.stressed_equity - lock.stressed_balance
        if abs(floating_actual - floating_stressed) > 1.0e-9:
            raise RuntimeError("actual/stressed floating P/L mismatch at release")
        last_affected_close = max(trade.close_time for _, trade in affected_pairs)

        for retained in retained_fractions:
            released = 1.0 - retained
            release_actual = released * floating_actual - action_reserve
            release_stressed = (
                released * floating_stressed
                - released * affected_drag
                - action_reserve
            )
            closed_metrics = closed_path_metrics(
                selection_closes,
                lock.closed_count,
                affected_ids,
                retained,
                lock_time,
                release_actual,
                release_stressed,
                reference,
                epochs,
            )
            final_delta_actual = (
                closed_metrics["actual_net_usd"]
                - float(selection_config["actual_net_usd"])
            )
            final_delta_stressed = (
                closed_metrics["stressed_net_usd"]
                - float(selection_config["stressed_net_usd"])
            )
            transition_actual_shift = min(-action_reserve, final_delta_actual)
            transition_stressed_shift = min(-action_reserve, final_delta_stressed)
            candidate_actual_equity: list[float] = []
            candidate_stressed_equity: list[float] = []
            for index, item in enumerate(aligned):
                if index < lock_index:
                    actual_shift = 0.0
                    stressed_shift = 0.0
                elif item.snapshot.server_time <= last_affected_close:
                    actual_shift = transition_actual_shift
                    stressed_shift = transition_stressed_shift
                else:
                    actual_shift = final_delta_actual
                    stressed_shift = final_delta_stressed
                candidate_actual_equity.append(
                    item.snapshot.account_equity + actual_shift
                )
                candidate_stressed_equity.append(item.stressed_equity + stressed_shift)
            actual_sampled_dd, minimum_actual_equity = sampled_drawdown(
                candidate_actual_equity, reference
            )
            stressed_sampled_dd, minimum_stressed_equity = sampled_drawdown(
                candidate_stressed_equity, reference
            )
            worse_sampled_dd = max(actual_sampled_dd, stressed_sampled_dd)
            budgeted_dd = max(
                qualified_dd_floor,
                worse_sampled_dd + native_gap + release_dd_reserve,
            )
            conservative_actual = (
                closed_metrics["actual_net_usd"] - global_profit_reserve
            )
            conservative_stressed = (
                closed_metrics["stressed_net_usd"] - global_profit_reserve
            )
            positive_gate = (
                closed_metrics["actual_net_usd"] > 0.0
                and closed_metrics["stressed_net_usd"] > 0.0
            )
            profit_gate = (
                conservative_actual > qualified_actual
                and conservative_stressed > qualified_stressed
            )
            capital_gate = (
                closed_metrics["minimum_actual_closed_balance_usd"] > 0.0
                and closed_metrics["minimum_stressed_closed_balance_usd"] > 0.0
                and minimum_actual_equity > 0.0
                and minimum_stressed_equity > 0.0
            )
            epoch_gate = all(
                value > 0.0 for value in closed_metrics["epoch_actual"]
            ) and all(value > 0.0 for value in closed_metrics["epoch_stressed"])
            dd_gate = budgeted_dd <= hard_dd + 1.0e-12
            combined = positive_gate and profit_gate and capital_gate and epoch_gate and dd_gate
            records.append(
                {
                    "equity_drawdown_trigger_pct": trigger,
                    "retained_open_exposure_fraction": retained,
                    "released_open_exposure_fraction": released,
                    "release_time_server": lock_time.strftime(TIME_FORMAT),
                    "release_stage": lock.snapshot.stage,
                    "release_result": lock.snapshot.result,
                    "affected_open_positions": len(affected_pairs),
                    "affected_position_identifiers": sorted(affected_ids),
                    "affected_components": sorted(
                        {trade.component_id for _, trade in affected_pairs}
                    ),
                    "last_affected_original_close_time_server": last_affected_close.strftime(
                        TIME_FORMAT
                    ),
                    "closed_lifecycles_before_release": lock.closed_count,
                    "release_account_balance_usd": lock.snapshot.account_balance,
                    "release_account_equity_usd": lock.snapshot.account_equity,
                    "release_stressed_balance_usd": lock.stressed_balance,
                    "release_stressed_equity_usd": lock.stressed_equity,
                    "aggregate_floating_net_at_release_usd": floating_actual,
                    "affected_original_actual_net_usd": affected_actual,
                    "affected_original_stressed_net_usd": affected_stressed,
                    "release_action_and_proxy_reserve_usd": action_reserve,
                    "actual_net_usd": closed_metrics["actual_net_usd"],
                    "stressed_net_usd": closed_metrics["stressed_net_usd"],
                    "conservative_actual_net_usd": conservative_actual,
                    "conservative_stressed_net_usd": conservative_stressed,
                    "actual_uplift_over_accelerated_usd": final_delta_actual,
                    "stressed_uplift_over_accelerated_usd": final_delta_stressed,
                    "actual_closed_balance_drawdown_pct": closed_metrics[
                        "actual_closed_balance_drawdown_pct"
                    ],
                    "stressed_closed_balance_drawdown_pct": closed_metrics[
                        "stressed_closed_balance_drawdown_pct"
                    ],
                    "actual_sampled_equity_drawdown_pct": actual_sampled_dd,
                    "stressed_sampled_equity_drawdown_pct": stressed_sampled_dd,
                    "worse_sampled_equity_drawdown_pct": worse_sampled_dd,
                    "budgeted_native_equity_drawdown_pct": budgeted_dd,
                    "minimum_actual_closed_balance_usd": closed_metrics[
                        "minimum_actual_closed_balance_usd"
                    ],
                    "minimum_stressed_closed_balance_usd": closed_metrics[
                        "minimum_stressed_closed_balance_usd"
                    ],
                    "minimum_actual_sampled_equity_usd": minimum_actual_equity,
                    "minimum_stressed_sampled_equity_usd": minimum_stressed_equity,
                    "transition_actual_equity_shift_usd": transition_actual_shift,
                    "transition_stressed_equity_shift_usd": transition_stressed_shift,
                    "epochs": [
                        {
                            "id": epoch["id"],
                            "actual_net_usd": closed_metrics["epoch_actual"][index],
                            "stressed_net_usd": closed_metrics["epoch_stressed"][index],
                        }
                        for index, epoch in enumerate(epochs)
                    ],
                    "selection_gates": {
                        "positive": positive_gate,
                        "profit_above_qualified_after_reserve": profit_gate,
                        "positive_capital_and_equity": capital_gate,
                        "all_epochs": epoch_gate,
                        "budgeted_drawdown": dd_gate,
                        "combined": combined,
                    },
                    "forward_invariant": {
                        "open_exposure_release_armed": False,
                        "actual_net_usd": float(forward_config["actual_net_usd"]),
                        "stressed_net_usd": float(
                            forward_config["stressed_net_usd"]
                        ),
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
            )

    if len(binding_lock_times) != int(selection_config["unique_binding_lock_times"]):
        raise RuntimeError("binding terminal-lock time count mismatch")

    def rank_key(record: dict[str, Any]) -> tuple[Any, ...]:
        return (
            -float(record["conservative_stressed_net_usd"]),
            -float(record["conservative_actual_net_usd"]),
            -float(record["epochs"][-1]["stressed_net_usd"]),
            float(record["budgeted_native_equity_drawdown_pct"]),
            -float(record["equity_drawdown_trigger_pct"]),
            -float(record["retained_open_exposure_fraction"]),
        )

    eligible = [record for record in records if record["selection_gates"]["combined"]]
    ranked = sorted(eligible, key=rank_key)
    diagnostics = sorted(records, key=rank_key)
    dd_eligible = sorted(
        [record for record in records if record["selection_gates"]["budgeted_drawdown"]],
        key=rank_key,
    )
    winner = ranked[0] if ranked else None
    status = (
        "VALID_PROXY_COMPLETE_ONE_MT5_SHORTLIST"
        if winner is not None
        else "VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE"
    )
    gate_names = (
        "positive",
        "profit_above_qualified_after_reserve",
        "positive_capital_and_equity",
        "all_epochs",
        "budgeted_drawdown",
        "combined",
    )
    gate_counts = {
        gate: sum(1 for record in records if record["selection_gates"][gate])
        for gate in gate_names
    }
    top_count = int(config["output_top_records"])

    result = {
        "schema": "zeta-dd20-one-shot-open-exposure-release-proxy-raw-result-v1",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "campaign": config["campaign"],
        "implementation": {
            "contract_sha256": sha256(CONFIG_PATH),
            "script_sha256": sha256(SCRIPT_PATH),
            "input_manifest_sha256": config["input"]["canonical_manifest_sha256"],
            "wall_time_seconds": time.perf_counter() - started,
            "accelerated_selection_lifecycle_native_and_sampled_anchor_gate": "PASS",
            "accelerated_forward_lifecycle_and_native_anchor_gate": "PASS",
            "qualified_result_identity_gate": "PASS",
            "terminal_lock_raw_and_durable_identity_gate": "PASS",
            "closed_predecessor_identity_gate": "PASS",
            "selection_snapshot_balance_alignment_gate": "PASS",
            "binding_open_exposure_and_nonbinding_exclusion_gate": "PASS",
            "forward_never_arms_gate": "PASS",
        },
        "search": {
            "candidate_combinations": len(records),
            "drawdown_triggers": triggers,
            "retained_open_exposure_fractions": retained_fractions,
            "binding_unique_lock_times": len(binding_lock_times),
            "excluded_nonbinding_triggers": [18.0, 18.5, 19.0],
            "all_candidates_release_open_exposure": True,
            "forward_open_exposure_release_armed": False,
            "selection_individual_gate_counts": gate_counts,
            "selection_role": config["selection_role"],
        },
        "calibration": {
            "qualified_native_floor_pct": qualified_dd_floor,
            "selection_full_path_sampled_dd_pct": baseline_sampled_dd,
            "selection_native_minus_sampled_gap_percentage_points": native_gap,
            "release_detection_transition_and_execution_reserve_percentage_points": release_dd_reserve,
            "release_action_and_proxy_reserve_usd": action_reserve,
            "selection_profit_uncertainty_reserve_usd": global_profit_reserve,
            "selection_snapshot_maximum_alignment_error_usd": alignment_maximum,
        },
        "closed_accelerated_anchor": {
            "actual_net_usd": float(selection_config["actual_net_usd"]),
            "stressed_net_usd": float(selection_config["stressed_net_usd"]),
            "sampled_equity_drawdown_pct": baseline_sampled_dd,
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
        "top_qualified": ranked[:top_count],
        "top_selection_diagnostic": diagnostics[:top_count],
        "top_dd_eligible_diagnostic": dd_eligible[:top_count],
        "mt5_shortlist": (
            [
                {
                    "role": config["selection_role"]["id"],
                    "equity_drawdown_trigger_pct": winner[
                        "equity_drawdown_trigger_pct"
                    ],
                    "retained_open_exposure_fraction": winner[
                        "retained_open_exposure_fraction"
                    ],
                    "selection_conservative_actual_net_usd": winner[
                        "conservative_actual_net_usd"
                    ],
                    "selection_conservative_stressed_net_usd": winner[
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
            "one_shot_nonterminal_open_exposure_release": True,
            "later_original_births_retained_at_full_exposure": True,
            "freed_capacity_synthetic_births": False,
            "drawdown_responsive_grid_rerun": False,
            "profit_realization_grid_rerun": False,
            "terminal_lock_grid_rerun": False,
            "risk_ceiling_grid_rerun": False,
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
                "wall_time_seconds": result["implementation"]["wall_time_seconds"],
            }
        )
    )


if __name__ == "__main__":
    main()
