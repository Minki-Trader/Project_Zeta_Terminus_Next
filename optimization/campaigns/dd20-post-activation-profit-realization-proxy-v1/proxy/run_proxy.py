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
    / "dd20-post-activation-profit-realization-proxy-v1"
    / "output"
    / "proxy-result.json"
)
TIME_FORMAT = "%Y.%m.%d %H:%M:%S"


@dataclass(frozen=True)
class Trade:
    position_identifier: str
    component_id: str
    order: int
    entry_time: datetime
    close_time: datetime
    peak_time: datetime
    planned_risk_usd: float
    peak_mark_profit_usd: float
    peak_mark_r: float
    original_actual_net_usd: float
    original_stressed_net_usd: float


@dataclass(frozen=True)
class EconomicEvent:
    server_time: datetime
    order: int
    component_id: str
    actual_net_usd: float
    stressed_net_usd: float
    profit_realized: bool


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


def load_trades(
    path: Path,
    expected_births: int,
    expected_closes: int,
    expected_actual: float,
    expected_stressed: float,
    components: list[str],
) -> list[Trade]:
    component_set = set(components)
    births: list[str] = []
    closes: list[str] = []
    trades: list[Trade] = []
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
            identifier = source["position_identifier"]
            closes.append(identifier)
            entry_time = datetime.strptime(source["entry_time_server"], TIME_FORMAT)
            close_time = datetime.strptime(source["server_time"], TIME_FORMAT)
            peak_time = datetime.strptime(source["peak_time_server"], TIME_FORMAT)
            planned_risk = float(source["planned_risk_usd"])
            actual = float(source["actual_net_usd"])
            stressed = float(source["stressed_net_usd"])
            if (
                planned_risk <= 0.0
                or peak_time < entry_time
                or peak_time > close_time
                or actual - stressed < -1.0e-9
            ):
                raise RuntimeError("lifecycle profit-realization fields are invalid")
            trades.append(
                Trade(
                    position_identifier=identifier,
                    component_id=component,
                    order=row_index,
                    entry_time=entry_time,
                    close_time=close_time,
                    peak_time=peak_time,
                    planned_risk_usd=planned_risk,
                    peak_mark_profit_usd=float(source["peak_mark_profit_usd"]),
                    peak_mark_r=float(source["peak_mark_r"]),
                    original_actual_net_usd=actual,
                    original_stressed_net_usd=stressed,
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
    if abs(sum(item.original_actual_net_usd for item in trades) - expected_actual) > 1.0e-7:
        raise RuntimeError("lifecycle actual net mismatch")
    if abs(sum(item.original_stressed_net_usd for item in trades) - expected_stressed) > 1.0e-7:
        raise RuntimeError("lifecycle stressed net mismatch")
    return trades


def activation_from_trades(
    trades: list[Trade], reference: float, growth_threshold: float
) -> tuple[datetime, float, float]:
    actual = reference
    stressed = reference
    for trade in sorted(trades, key=lambda item: (item.close_time, item.order)):
        actual += trade.original_actual_net_usd
        stressed += trade.original_stressed_net_usd
        if stressed >= reference + growth_threshold:
            return trade.close_time, actual, stressed
    raise RuntimeError("selection never reaches the profit-realization arming threshold")


def maximum_stressed_balance(trades: list[Trade], reference: float) -> float:
    balance = reference
    maximum = reference
    for trade in sorted(trades, key=lambda item: (item.close_time, item.order)):
        balance += trade.original_stressed_net_usd
        maximum = max(maximum, balance)
    return maximum


def closed_balance_metrics(
    events: list[EconomicEvent], reference: float
) -> dict[str, float]:
    actual_balance = reference
    stressed_balance = reference
    actual_peak = reference
    stressed_peak = reference
    actual_dd = 0.0
    stressed_dd = 0.0
    minimum_actual = reference
    minimum_stressed = reference
    ordered = sorted(
        events,
        key=lambda item: (
            item.server_time,
            0 if min(item.actual_net_usd, item.stressed_net_usd) < 0.0 else 1,
            item.order,
        ),
    )
    for event in ordered:
        actual_balance += event.actual_net_usd
        stressed_balance += event.stressed_net_usd
        actual_peak = max(actual_peak, actual_balance)
        stressed_peak = max(stressed_peak, stressed_balance)
        actual_dd = max(actual_dd, 100.0 * (actual_peak - actual_balance) / actual_peak)
        stressed_dd = max(
            stressed_dd,
            100.0 * (stressed_peak - stressed_balance) / stressed_peak,
        )
        minimum_actual = min(minimum_actual, actual_balance)
        minimum_stressed = min(minimum_stressed, stressed_balance)
    return {
        "actual_net_usd": actual_balance - reference,
        "stressed_net_usd": stressed_balance - reference,
        "actual_closed_balance_drawdown_pct": actual_dd,
        "stressed_closed_balance_drawdown_pct": stressed_dd,
        "raw_worse_closed_balance_drawdown_pct": max(actual_dd, stressed_dd),
        "minimum_actual_closed_balance_usd": minimum_actual,
        "minimum_stressed_closed_balance_usd": minimum_stressed,
    }


def epoch_index(server_time: datetime, epochs: list[dict[str, Any]]) -> int | None:
    for index, epoch in enumerate(epochs):
        if epoch["start_time"] <= server_time < epoch["end_time"]:
            return index
    return None


def epoch_nets(
    events: list[EconomicEvent], epochs: list[dict[str, Any]]
) -> tuple[list[float], list[float]]:
    actual = [0.0 for _ in epochs]
    stressed = [0.0 for _ in epochs]
    for event in events:
        index = epoch_index(event.server_time, epochs)
        if index is None:
            raise RuntimeError("profit-realization event is outside selection epochs")
        actual[index] += event.actual_net_usd
        stressed[index] += event.stressed_net_usd
    return actual, stressed


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
    risk_ceiling_result = json.loads(
        (input_root / str(config["input"]["risk_ceiling_result_file"])).read_text(
            encoding="utf-8"
        )
    )
    terminal_lock_result = json.loads(
        (input_root / str(config["input"]["terminal_lock_result_file"])).read_text(
            encoding="utf-8"
        )
    )
    if (
        accelerated_result.get("campaign")
        != "dd20-deferred-profit-accelerator-mt5-v1"
        or accelerated_result.get("status")
        != "VALID_MT5_COMPLETE_SELECTION_DD20_FAIL_FORWARD_ALL_GATES_PASS"
        or qualified_result.get("campaign") != config["qualified_anchor"]["campaign"]
        or qualified_result.get("status")
        != config["qualified_anchor"]["result_status"]
        or risk_ceiling_result.get("campaign")
        != "dd20-profit-protected-risk-ceiling-proxy-v1"
        or risk_ceiling_result.get("status")
        != "VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE"
        or terminal_lock_result.get("campaign")
        != "dd20-equity-high-watermark-terminal-lock-proxy-v1"
        or terminal_lock_result.get("status")
        != "VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE"
    ):
        raise RuntimeError("closed predecessor identity mismatch")

    dd_config = config["selection_drawdown_calibration"]
    observed_gap = float(
        risk_ceiling_result["calibration"][
            "accelerated_native_minus_raw_gap_percentage_points"
        ]
    )
    if (
        abs(
            observed_gap
            - float(
                dd_config[
                    "accelerated_native_minus_raw_closed_balance_gap_percentage_points"
                ]
            )
        )
        > 1.0e-9
    ):
        raise RuntimeError("closed-balance/native DD calibration mismatch")

    selection_trades = load_trades(
        input_root / str(config["input"]["selection_lifecycle_file"]),
        int(selection_config["births"]),
        int(selection_config["closed_lifecycles"]),
        float(selection_config["actual_net_usd"]),
        float(selection_config["stressed_net_usd"]),
        components,
    )
    forward_trades = load_trades(
        input_root / str(config["input"]["forward_lifecycle_file"]),
        int(forward_config["births"]),
        int(forward_config["closed_lifecycles"]),
        float(forward_config["actual_net_usd"]),
        float(forward_config["stressed_net_usd"]),
        components,
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

    growth_threshold = float(config["fixed_accelerator"]["activation_growth_threshold_usd"])
    activation_time, activation_actual, activation_stressed = activation_from_trades(
        selection_trades, reference, growth_threshold
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
        raise RuntimeError("profit-realization activation anchor mismatch")

    post_activation = [
        trade for trade in selection_trades if trade.entry_time >= activation_time
    ]
    cost_drag = sum(
        trade.original_actual_net_usd - trade.original_stressed_net_usd
        for trade in selection_trades
    )
    post_cost_drag = sum(
        trade.original_actual_net_usd - trade.original_stressed_net_usd
        for trade in post_activation
    )
    peak_values = [trade.peak_mark_r for trade in post_activation]
    targets = [float(value) for value in config["profit_realization"]["candidate_profit_targets_r"]]
    if (
        len(post_activation)
        != int(selection_config["post_activation_entry_lifecycles"])
        or abs(
            sum(trade.original_actual_net_usd for trade in post_activation)
            - float(selection_config["post_activation_actual_net_usd"])
        )
        > 1.0e-7
        or abs(
            sum(trade.original_stressed_net_usd for trade in post_activation)
            - float(selection_config["post_activation_stressed_net_usd"])
        )
        > 1.0e-7
        or abs(min(peak_values) - float(selection_config["post_activation_peak_mark_r_minimum"]))
        > 1.0e-9
        or abs(max(peak_values) - float(selection_config["post_activation_peak_mark_r_maximum"]))
        > 1.0e-9
        or sum(1 for value in peak_values if value >= max(targets) - 1.0e-12)
        != int(
            selection_config[
                "post_activation_lifecycles_at_or_above_maximum_candidate"
            ]
        )
        or abs(cost_drag - float(selection_config["actual_minus_stressed_cost_drag_usd"]))
        > 1.0e-7
        or abs(
            post_cost_drag
            - float(selection_config["post_activation_actual_minus_stressed_cost_drag_usd"])
        )
        > 1.0e-7
    ):
        raise RuntimeError("post-activation structural anchor mismatch")

    forward_maximum_stressed = maximum_stressed_balance(forward_trades, reference)
    if (
        forward_maximum_stressed >= reference + growth_threshold
        or abs(
            forward_maximum_stressed
            - float(forward_config["maximum_stressed_closed_balance_usd"])
        )
        > 1.0e-7
    ):
        raise RuntimeError("forward arming-invariance anchor mismatch")

    realization_config = config["profit_realization"]
    expected_count = int(realization_config["expected_candidates"])
    step = float(realization_config["target_step_r"])
    if (
        len(targets) != expected_count
        or len(set(targets)) != len(targets)
        or any(value <= 0.0 for value in targets)
        or any(
            abs((targets[index] - targets[index - 1]) - step) > 1.0e-12
            for index in range(1, len(targets))
        )
        or max(targets) >= max(peak_values)
    ):
        raise RuntimeError("profit-realization target grid is invalid")

    epochs = [
        {
            "id": str(item["id"]),
            "start_time": datetime.strptime(item["start"], TIME_FORMAT),
            "end_time": datetime.strptime(item["end"], TIME_FORMAT),
        }
        for item in config["selection_epochs"]
    ]
    minimum_reserve = float(realization_config["minimum_absolute_realization_reserve_usd"])
    risk_reserve_fraction = float(
        realization_config["planned_risk_realization_reserve_fraction"]
    )
    global_profit_reserve = float(
        realization_config["selection_profit_uncertainty_reserve_usd"]
    )
    qualified_actual = float(config["qualified_anchor"]["selection_actual_net_usd"])
    qualified_stressed = float(config["qualified_anchor"]["selection_stressed_net_usd"])
    qualified_dd_floor = float(
        config["qualified_anchor"]["selection_native_equity_drawdown_pct"]
    ) + float(dd_config["qualified_native_floor_reserve_percentage_points"])
    timing_reserve = float(
        dd_config["profit_realization_timing_and_path_reserve_percentage_points"]
    )
    hard_dd = float(dd_config["hard_native_mt5_equity_drawdown_pct"])

    records: list[dict[str, Any]] = []
    for target in targets:
        events: list[EconomicEvent] = []
        realization_count = 0
        realized_original_actual = 0.0
        realized_counterfactual_actual = 0.0
        component_records = {
            component: {
                "profit_realizations": 0,
                "actual_net_usd": 0.0,
                "stressed_net_usd": 0.0,
            }
            for component in components
        }
        for trade in selection_trades:
            applies = (
                trade.entry_time >= activation_time
                and trade.peak_mark_r >= target - 1.0e-12
            )
            if applies:
                reserve = max(
                    minimum_reserve,
                    trade.planned_risk_usd * risk_reserve_fraction,
                )
                actual = target * trade.planned_risk_usd - reserve
                drag = max(
                    0.0,
                    trade.original_actual_net_usd
                    - trade.original_stressed_net_usd,
                )
                stressed = actual - drag
                event_time = trade.peak_time
                realization_count += 1
                realized_original_actual += trade.original_actual_net_usd
                realized_counterfactual_actual += actual
            else:
                actual = trade.original_actual_net_usd
                stressed = trade.original_stressed_net_usd
                event_time = trade.close_time
            events.append(
                EconomicEvent(
                    server_time=event_time,
                    order=trade.order,
                    component_id=trade.component_id,
                    actual_net_usd=actual,
                    stressed_net_usd=stressed,
                    profit_realized=applies,
                )
            )
            component = component_records[trade.component_id]
            component["actual_net_usd"] += actual
            component["stressed_net_usd"] += stressed
            if applies:
                component["profit_realizations"] += 1

        if realization_count <= 0:
            raise RuntimeError("one or more declared candidates do not bind")
        metrics = closed_balance_metrics(events, reference)
        epoch_actual, epoch_stressed = epoch_nets(events, epochs)
        if (
            abs(sum(epoch_actual) - metrics["actual_net_usd"]) > 1.0e-7
            or abs(sum(epoch_stressed) - metrics["stressed_net_usd"]) > 1.0e-7
        ):
            raise RuntimeError("profit-realization epoch net does not reconcile")
        conservative_actual = metrics["actual_net_usd"] - global_profit_reserve
        conservative_stressed = metrics["stressed_net_usd"] - global_profit_reserve
        budgeted_dd = max(
            qualified_dd_floor,
            metrics["raw_worse_closed_balance_drawdown_pct"]
            + observed_gap
            + timing_reserve,
        )
        positive_gate = (
            metrics["actual_net_usd"] > 0.0
            and metrics["stressed_net_usd"] > 0.0
        )
        profit_gate = (
            conservative_actual > qualified_actual
            and conservative_stressed > qualified_stressed
        )
        capital_gate = (
            metrics["minimum_actual_closed_balance_usd"] > 0.0
            and metrics["minimum_stressed_closed_balance_usd"] > 0.0
        )
        epoch_gate = all(value > 0.0 for value in epoch_actual) and all(
            value > 0.0 for value in epoch_stressed
        )
        dd_gate = budgeted_dd <= hard_dd + 1.0e-12
        combined = positive_gate and profit_gate and capital_gate and epoch_gate and dd_gate
        records.append(
            {
                "profit_target_r": target,
                "profit_realizations": realization_count,
                "realized_original_actual_net_usd": realized_original_actual,
                "realized_counterfactual_actual_net_usd": realized_counterfactual_actual,
                "actual_net_usd": metrics["actual_net_usd"],
                "stressed_net_usd": metrics["stressed_net_usd"],
                "conservative_actual_net_usd": conservative_actual,
                "conservative_stressed_net_usd": conservative_stressed,
                "actual_uplift_over_accelerated_usd": metrics["actual_net_usd"]
                - float(selection_config["actual_net_usd"]),
                "stressed_uplift_over_accelerated_usd": metrics["stressed_net_usd"]
                - float(selection_config["stressed_net_usd"]),
                **{
                    key: value
                    for key, value in metrics.items()
                    if key not in ("actual_net_usd", "stressed_net_usd")
                },
                "budgeted_native_equity_drawdown_pct": budgeted_dd,
                "epochs": [
                    {
                        "id": epoch["id"],
                        "actual_net_usd": epoch_actual[index],
                        "stressed_net_usd": epoch_stressed[index],
                    }
                    for index, epoch in enumerate(epochs)
                ],
                "components": [
                    {
                        "component_id": component,
                        **component_records[component],
                    }
                    for component in components
                ],
                "selection_gates": {
                    "positive": positive_gate,
                    "profit_above_qualified_after_reserve": profit_gate,
                    "positive_capital": capital_gate,
                    "all_epochs": epoch_gate,
                    "budgeted_drawdown": dd_gate,
                    "combined": combined,
                },
                "forward_invariant": {
                    "profit_realization_armed": False,
                    "actual_net_usd": float(forward_config["actual_net_usd"]),
                    "stressed_net_usd": float(forward_config["stressed_net_usd"]),
                    "native_equity_drawdown_pct": float(
                        forward_config["native_maximum_equity_drawdown_pct"]
                    ),
                    "june_actual_net_usd": float(forward_config["june_actual_net_usd"]),
                    "june_stressed_net_usd": float(
                        forward_config["june_stressed_net_usd"]
                    ),
                    "july_actual_net_usd": float(forward_config["july_actual_net_usd"]),
                    "july_stressed_net_usd": float(
                        forward_config["july_stressed_net_usd"]
                    ),
                },
            }
        )

    def rank_key(record: dict[str, Any]) -> tuple[Any, ...]:
        return (
            -float(record["conservative_stressed_net_usd"]),
            -float(record["conservative_actual_net_usd"]),
            -float(record["epochs"][-1]["stressed_net_usd"]),
            float(record["budgeted_native_equity_drawdown_pct"]),
            -float(record["profit_target_r"]),
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
    top_count = int(config["output_top_records"])
    gate_names = (
        "positive",
        "profit_above_qualified_after_reserve",
        "positive_capital",
        "all_epochs",
        "budgeted_drawdown",
        "combined",
    )
    gate_counts = {
        gate: sum(1 for record in records if record["selection_gates"][gate])
        for gate in gate_names
    }

    result = {
        "schema": "zeta-dd20-post-activation-profit-realization-proxy-raw-result-v1",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "campaign": config["campaign"],
        "implementation": {
            "contract_sha256": sha256(CONFIG_PATH),
            "script_sha256": sha256(SCRIPT_PATH),
            "input_manifest_sha256": config["input"]["canonical_manifest_sha256"],
            "wall_time_seconds": time.perf_counter() - started,
            "accelerated_selection_lifecycle_and_native_anchor_gate": "PASS",
            "accelerated_forward_lifecycle_and_native_anchor_gate": "PASS",
            "qualified_result_identity_gate": "PASS",
            "risk_ceiling_result_and_dd_gap_gate": "PASS",
            "terminal_lock_result_identity_gate": "PASS",
            "post_activation_lifecycle_structure_gate": "PASS",
            "forward_never_arms_gate": "PASS",
        },
        "search": {
            "candidate_profit_targets": len(targets),
            "minimum_profit_target_r": min(targets),
            "maximum_profit_target_r": max(targets),
            "target_step_r": step,
            "all_candidates_bind_in_selection": True,
            "forward_profit_realization_armed": False,
            "selection_individual_gate_counts": gate_counts,
            "selection_role": config["selection_role"],
        },
        "calibration": {
            "qualified_native_floor_pct": qualified_dd_floor,
            "accelerated_native_minus_raw_closed_balance_gap_percentage_points": observed_gap,
            "profit_realization_timing_and_path_reserve_percentage_points": timing_reserve,
            "selection_profit_uncertainty_reserve_usd": global_profit_reserve,
            "minimum_absolute_realization_reserve_usd": minimum_reserve,
            "planned_risk_realization_reserve_fraction": risk_reserve_fraction,
        },
        "closed_accelerated_anchor": {
            "actual_net_usd": float(selection_config["actual_net_usd"]),
            "stressed_net_usd": float(selection_config["stressed_net_usd"]),
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
                    "profit_target_r": winner["profit_target_r"],
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
            "nonterminal_profit_realization": True,
            "later_original_births_retained": True,
            "freed_capacity_synthetic_births": False,
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
