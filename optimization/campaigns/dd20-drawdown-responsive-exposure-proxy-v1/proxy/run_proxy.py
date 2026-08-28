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
    / "dd20-drawdown-responsive-exposure-proxy-v1"
    / "output"
    / "proxy-result.json"
)
TIME_FORMAT = "%Y.%m.%d %H:%M:%S"


@dataclass(frozen=True)
class LifecycleEvent:
    event: str
    position_identifier: str
    component_id: str
    server_time: datetime
    order: int
    planned_risk_usd: float
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
    expected_births: int,
    expected_closes: int,
    expected_actual: float,
    expected_stressed: float,
    components: list[str],
) -> list[LifecycleEvent]:
    component_set = set(components)
    births: list[str] = []
    closes: list[str] = []
    events: list[LifecycleEvent] = []
    last_time: datetime | None = None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row_index, source in enumerate(csv.DictReader(handle)):
            event = source["event"]
            if event not in ("BIRTH", "CLOSE"):
                continue
            component = source["component_id"]
            if component not in component_set:
                raise RuntimeError("lifecycle contains undeclared component")
            server_time = datetime.strptime(source["server_time"], TIME_FORMAT)
            if last_time is not None and server_time < last_time:
                raise RuntimeError("lifecycle events are not chronological")
            last_time = server_time
            identifier = source["position_identifier"]
            if event == "BIRTH":
                births.append(identifier)
            else:
                closes.append(identifier)
            events.append(
                LifecycleEvent(
                    event=event,
                    position_identifier=identifier,
                    component_id=component,
                    server_time=server_time,
                    order=row_index,
                    planned_risk_usd=float(source["planned_risk_usd"]),
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
    if abs(sum(item.actual_net_usd for item in events) - expected_actual) > 1.0e-7:
        raise RuntimeError("lifecycle actual net mismatch")
    if abs(sum(item.stressed_net_usd for item in events) - expected_stressed) > 1.0e-7:
        raise RuntimeError("lifecycle stressed net mismatch")
    if any(
        item.event == "BIRTH" and item.planned_risk_usd <= 0.0 for item in events
    ):
        raise RuntimeError("lifecycle birth planned risk is invalid")
    return events


def percentile_observation(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(fraction * (len(ordered) - 1)))
    return ordered[index]


def baseline_structure(
    events: list[LifecycleEvent], reference: float, arming_balance: float
) -> dict[str, Any]:
    actual = reference
    stressed = reference
    stressed_peak = reference
    maximum_stressed = reference
    armed = False
    activation_time: datetime | None = None
    activation_actual = 0.0
    activation_stressed = 0.0
    post_arm_birth_dd: list[float] = []
    open_positions: set[str] = set()
    for event in events:
        if event.event == "BIRTH":
            if event.position_identifier in open_positions:
                raise RuntimeError("duplicate open lifecycle identity")
            open_positions.add(event.position_identifier)
            if armed:
                post_arm_birth_dd.append(
                    100.0 * (stressed_peak - stressed) / stressed_peak
                )
            continue
        if event.position_identifier not in open_positions:
            raise RuntimeError("close without open lifecycle identity")
        open_positions.remove(event.position_identifier)
        actual += event.actual_net_usd
        stressed += event.stressed_net_usd
        stressed_peak = max(stressed_peak, stressed)
        maximum_stressed = max(maximum_stressed, stressed)
        if not armed and stressed >= arming_balance:
            armed = True
            activation_time = event.server_time
            activation_actual = actual
            activation_stressed = stressed
    if open_positions:
        raise RuntimeError("lifecycle has positions left open")
    return {
        "armed": armed,
        "activation_time": activation_time,
        "activation_actual_balance_usd": activation_actual,
        "activation_stressed_balance_usd": activation_stressed,
        "maximum_stressed_closed_balance_usd": maximum_stressed,
        "post_arm_birth_drawdowns_pct": post_arm_birth_dd,
    }


def epoch_index(server_time: datetime, epochs: list[dict[str, Any]]) -> int | None:
    for index, epoch in enumerate(epochs):
        if epoch["start_time"] <= server_time < epoch["end_time"]:
            return index
    return None


def simulate_candidate(
    events: list[LifecycleEvent],
    reference: float,
    arming_balance: float,
    drawdown_trigger_pct: float,
    risk_multiplier: float,
    scaled_position_reserve: float,
    epochs: list[dict[str, Any]],
    components: list[str],
) -> dict[str, Any]:
    actual = reference
    stressed = reference
    actual_peak = reference
    stressed_peak = reference
    actual_dd = 0.0
    stressed_dd = 0.0
    minimum_actual = reference
    minimum_stressed = reference
    armed = False
    activation_time: datetime | None = None
    activation_actual = 0.0
    activation_stressed = 0.0
    position_scales: dict[str, float] = {}
    post_arm_births = 0
    scaled_births = 0
    full_exposure_births = 0
    risk_off_episodes = 0
    prior_birth_scaled = False
    first_scaled_time: datetime | None = None
    last_scaled_time: datetime | None = None
    scaled_birth_dd: list[float] = []
    epoch_actual = [0.0 for _ in epochs]
    epoch_stressed = [0.0 for _ in epochs]
    component_records = {
        component: {
            "scaled_births": 0,
            "actual_net_usd": 0.0,
            "stressed_net_usd": 0.0,
        }
        for component in components
    }

    for event in events:
        if event.event == "BIRTH":
            if event.position_identifier in position_scales:
                raise RuntimeError("duplicate candidate position birth")
            scale = 1.0
            scaled = False
            if armed:
                post_arm_births += 1
                current_dd = 100.0 * (stressed_peak - stressed) / stressed_peak
                if current_dd >= drawdown_trigger_pct - 1.0e-12:
                    scale = risk_multiplier
                    scaled = True
                    scaled_births += 1
                    scaled_birth_dd.append(current_dd)
                    component_records[event.component_id]["scaled_births"] += 1
                    if not prior_birth_scaled:
                        risk_off_episodes += 1
                    if first_scaled_time is None:
                        first_scaled_time = event.server_time
                    last_scaled_time = event.server_time
                else:
                    full_exposure_births += 1
                prior_birth_scaled = scaled
            position_scales[event.position_identifier] = scale
            continue

        if event.position_identifier not in position_scales:
            raise RuntimeError("candidate close without birth")
        scale = position_scales.pop(event.position_identifier)
        actual_net = event.actual_net_usd * scale
        stressed_net = event.stressed_net_usd * scale
        if scale < 1.0 - 1.0e-12:
            actual_net -= scaled_position_reserve
            stressed_net -= scaled_position_reserve
        actual += actual_net
        stressed += stressed_net
        actual_peak = max(actual_peak, actual)
        stressed_peak = max(stressed_peak, stressed)
        actual_dd = max(actual_dd, 100.0 * (actual_peak - actual) / actual_peak)
        stressed_dd = max(
            stressed_dd,
            100.0 * (stressed_peak - stressed) / stressed_peak,
        )
        minimum_actual = min(minimum_actual, actual)
        minimum_stressed = min(minimum_stressed, stressed)
        index = epoch_index(event.server_time, epochs)
        if index is None:
            raise RuntimeError("candidate close is outside selection epochs")
        epoch_actual[index] += actual_net
        epoch_stressed[index] += stressed_net
        component = component_records[event.component_id]
        component["actual_net_usd"] += actual_net
        component["stressed_net_usd"] += stressed_net
        if not armed and stressed >= arming_balance:
            armed = True
            activation_time = event.server_time
            activation_actual = actual
            activation_stressed = stressed

    if position_scales:
        raise RuntimeError("candidate has positions left open")
    if not armed or activation_time is None:
        raise RuntimeError("candidate never arms")
    if abs(sum(epoch_actual) - (actual - reference)) > 1.0e-7:
        raise RuntimeError("candidate actual epoch net does not reconcile")
    if abs(sum(epoch_stressed) - (stressed - reference)) > 1.0e-7:
        raise RuntimeError("candidate stressed epoch net does not reconcile")
    return {
        "actual_net_usd": actual - reference,
        "stressed_net_usd": stressed - reference,
        "actual_closed_balance_drawdown_pct": actual_dd,
        "stressed_closed_balance_drawdown_pct": stressed_dd,
        "raw_worse_closed_balance_drawdown_pct": max(actual_dd, stressed_dd),
        "minimum_actual_closed_balance_usd": minimum_actual,
        "minimum_stressed_closed_balance_usd": minimum_stressed,
        "activation_time": activation_time,
        "activation_actual_balance_usd": activation_actual,
        "activation_stressed_balance_usd": activation_stressed,
        "post_arm_births": post_arm_births,
        "scaled_births": scaled_births,
        "full_exposure_births": full_exposure_births,
        "risk_off_episodes": risk_off_episodes,
        "first_scaled_time": first_scaled_time,
        "last_scaled_time": last_scaled_time,
        "minimum_scaled_birth_drawdown_pct": min(scaled_birth_dd)
        if scaled_birth_dd
        else None,
        "maximum_scaled_birth_drawdown_pct": max(scaled_birth_dd)
        if scaled_birth_dd
        else None,
        "epoch_actual": epoch_actual,
        "epoch_stressed": epoch_stressed,
        "components": component_records,
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
    profit_result = json.loads(
        (
            input_root / str(config["input"]["profit_realization_result_file"])
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
        or risk_ceiling_result.get("campaign")
        != "dd20-profit-protected-risk-ceiling-proxy-v1"
        or risk_ceiling_result.get("status")
        != "VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE"
        or profit_result.get("campaign")
        != "dd20-post-activation-profit-realization-proxy-v1"
        or profit_result.get("status")
        != "VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE"
    ):
        raise RuntimeError("closed predecessor identity mismatch")

    selection_events = load_events(
        input_root / str(config["input"]["selection_lifecycle_file"]),
        int(selection_config["births"]),
        int(selection_config["closed_lifecycles"]),
        float(selection_config["actual_net_usd"]),
        float(selection_config["stressed_net_usd"]),
        components,
    )
    forward_events = load_events(
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
    arming_balance = reference + growth_threshold
    selection_structure = baseline_structure(
        selection_events, reference, arming_balance
    )
    forward_structure = baseline_structure(forward_events, reference, arming_balance)
    birth_dd = selection_structure["post_arm_birth_drawdowns_pct"]
    if (
        not selection_structure["armed"]
        or selection_structure["activation_time"]
        != datetime.strptime(selection_config["activation_time_server"], TIME_FORMAT)
        or abs(
            selection_structure["activation_actual_balance_usd"]
            - float(selection_config["activation_actual_balance_usd"])
        )
        > 1.0e-7
        or abs(
            selection_structure["activation_stressed_balance_usd"]
            - float(selection_config["activation_stressed_balance_usd"])
        )
        > 1.0e-7
        or len(birth_dd) != int(selection_config["post_activation_births"])
        or abs(min(birth_dd) - float(selection_config["baseline_post_activation_birth_drawdown_minimum_pct"]))
        > 1.0e-9
        or abs(
            percentile_observation(birth_dd, 0.5)
            - float(selection_config["baseline_post_activation_birth_drawdown_median_pct"])
        )
        > 1.0e-9
        or abs(
            percentile_observation(birth_dd, 0.9)
            - float(
                selection_config[
                    "baseline_post_activation_birth_drawdown_ninetieth_percentile_pct"
                ]
            )
        )
        > 1.0e-9
        or abs(
            max(birth_dd)
            - float(selection_config["baseline_post_activation_birth_drawdown_maximum_pct"])
        )
        > 1.0e-9
        or sum(1 for value in birth_dd if value >= 1.0 - 1.0e-12)
        != int(selection_config["baseline_post_activation_births_at_or_above_one_pct"])
        or sum(1 for value in birth_dd if value >= 18.0 - 1.0e-12)
        != int(
            selection_config["baseline_post_activation_births_at_or_above_eighteen_pct"]
        )
    ):
        raise RuntimeError("selection drawdown-state structural anchor mismatch")
    if (
        forward_structure["armed"]
        or abs(
            forward_structure["maximum_stressed_closed_balance_usd"]
            - float(forward_config["maximum_stressed_closed_balance_usd"])
        )
        > 1.0e-7
    ):
        raise RuntimeError("forward arming-invariance anchor mismatch")

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

    exposure_config = config["drawdown_responsive_exposure"]
    triggers = [
        float(value) for value in exposure_config["candidate_drawdown_triggers_pct"]
    ]
    multipliers = [
        float(value) for value in exposure_config["candidate_risk_multipliers"]
    ]
    if (
        len(triggers) * len(multipliers)
        != int(exposure_config["expected_candidates"])
        or len(set(triggers)) != len(triggers)
        or len(set(multipliers)) != len(multipliers)
        or any(value <= 0.0 or value >= 20.0 for value in triggers)
        or any(value <= 0.0 or value >= 1.0 for value in multipliers)
    ):
        raise RuntimeError("drawdown-responsive exposure grid is invalid")

    epochs = [
        {
            "id": str(item["id"]),
            "start_time": datetime.strptime(item["start"], TIME_FORMAT),
            "end_time": datetime.strptime(item["end"], TIME_FORMAT),
        }
        for item in config["selection_epochs"]
    ]
    scaled_reserve = float(exposure_config["per_scaled_position_modeling_reserve_usd"])
    global_profit_reserve = float(
        exposure_config["selection_profit_uncertainty_reserve_usd"]
    )
    qualified_actual = float(config["qualified_anchor"]["selection_actual_net_usd"])
    qualified_stressed = float(config["qualified_anchor"]["selection_stressed_net_usd"])
    qualified_dd_floor = float(
        config["qualified_anchor"]["selection_native_equity_drawdown_pct"]
    ) + float(dd_config["qualified_native_floor_reserve_percentage_points"])
    state_reserve = float(
        dd_config["state_dependent_scaling_and_lattice_reserve_percentage_points"]
    )
    hard_dd = float(dd_config["hard_native_mt5_equity_drawdown_pct"])

    records: list[dict[str, Any]] = []
    for trigger in triggers:
        for multiplier in multipliers:
            simulation = simulate_candidate(
                selection_events,
                reference,
                arming_balance,
                trigger,
                multiplier,
                scaled_reserve,
                epochs,
                components,
            )
            if (
                simulation["activation_time"] != selection_structure["activation_time"]
                or abs(
                    simulation["activation_actual_balance_usd"]
                    - selection_structure["activation_actual_balance_usd"]
                )
                > 1.0e-7
                or abs(
                    simulation["activation_stressed_balance_usd"]
                    - selection_structure["activation_stressed_balance_usd"]
                )
                > 1.0e-7
                or simulation["post_arm_births"]
                != int(selection_config["post_activation_births"])
                or simulation["scaled_births"] <= 0
            ):
                raise RuntimeError("candidate activation or binding mismatch")
            conservative_actual = simulation["actual_net_usd"] - global_profit_reserve
            conservative_stressed = (
                simulation["stressed_net_usd"] - global_profit_reserve
            )
            budgeted_dd = max(
                qualified_dd_floor,
                simulation["raw_worse_closed_balance_drawdown_pct"]
                + observed_gap
                + state_reserve,
            )
            positive_gate = (
                simulation["actual_net_usd"] > 0.0
                and simulation["stressed_net_usd"] > 0.0
            )
            profit_gate = (
                conservative_actual > qualified_actual
                and conservative_stressed > qualified_stressed
            )
            capital_gate = (
                simulation["minimum_actual_closed_balance_usd"] > 0.0
                and simulation["minimum_stressed_closed_balance_usd"] > 0.0
            )
            epoch_gate = all(value > 0.0 for value in simulation["epoch_actual"]) and all(
                value > 0.0 for value in simulation["epoch_stressed"]
            )
            dd_gate = budgeted_dd <= hard_dd + 1.0e-12
            combined = positive_gate and profit_gate and capital_gate and epoch_gate and dd_gate
            records.append(
                {
                    "drawdown_trigger_pct": trigger,
                    "risk_multiplier": multiplier,
                    "scaled_births": simulation["scaled_births"],
                    "full_exposure_post_arm_births": simulation["full_exposure_births"],
                    "risk_off_episodes": simulation["risk_off_episodes"],
                    "first_scaled_birth_time_server": simulation[
                        "first_scaled_time"
                    ].strftime(TIME_FORMAT),
                    "last_scaled_birth_time_server": simulation[
                        "last_scaled_time"
                    ].strftime(TIME_FORMAT),
                    "minimum_scaled_birth_drawdown_pct": simulation[
                        "minimum_scaled_birth_drawdown_pct"
                    ],
                    "maximum_scaled_birth_drawdown_pct": simulation[
                        "maximum_scaled_birth_drawdown_pct"
                    ],
                    "actual_net_usd": simulation["actual_net_usd"],
                    "stressed_net_usd": simulation["stressed_net_usd"],
                    "conservative_actual_net_usd": conservative_actual,
                    "conservative_stressed_net_usd": conservative_stressed,
                    "actual_uplift_over_accelerated_usd": simulation[
                        "actual_net_usd"
                    ]
                    - float(selection_config["actual_net_usd"]),
                    "stressed_uplift_over_accelerated_usd": simulation[
                        "stressed_net_usd"
                    ]
                    - float(selection_config["stressed_net_usd"]),
                    "actual_closed_balance_drawdown_pct": simulation[
                        "actual_closed_balance_drawdown_pct"
                    ],
                    "stressed_closed_balance_drawdown_pct": simulation[
                        "stressed_closed_balance_drawdown_pct"
                    ],
                    "raw_worse_closed_balance_drawdown_pct": simulation[
                        "raw_worse_closed_balance_drawdown_pct"
                    ],
                    "budgeted_native_equity_drawdown_pct": budgeted_dd,
                    "minimum_actual_closed_balance_usd": simulation[
                        "minimum_actual_closed_balance_usd"
                    ],
                    "minimum_stressed_closed_balance_usd": simulation[
                        "minimum_stressed_closed_balance_usd"
                    ],
                    "epochs": [
                        {
                            "id": epoch["id"],
                            "actual_net_usd": simulation["epoch_actual"][index],
                            "stressed_net_usd": simulation["epoch_stressed"][index],
                        }
                        for index, epoch in enumerate(epochs)
                    ],
                    "components": [
                        {
                            "component_id": component,
                            **simulation["components"][component],
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
                        "drawdown_responsive_exposure_armed": False,
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

    def rank_key(record: dict[str, Any]) -> tuple[Any, ...]:
        return (
            -float(record["conservative_stressed_net_usd"]),
            -float(record["conservative_actual_net_usd"]),
            -float(record["epochs"][-1]["stressed_net_usd"]),
            float(record["budgeted_native_equity_drawdown_pct"]),
            -float(record["drawdown_trigger_pct"]),
            -float(record["risk_multiplier"]),
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
        "positive_capital",
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
        "schema": "zeta-dd20-drawdown-responsive-exposure-proxy-raw-result-v1",
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
            "profit_realization_result_identity_gate": "PASS",
            "selection_drawdown_state_structure_gate": "PASS",
            "forward_never_arms_gate": "PASS",
        },
        "search": {
            "candidate_combinations": len(records),
            "drawdown_triggers": triggers,
            "risk_multipliers": multipliers,
            "all_candidates_bind_in_selection": True,
            "forward_drawdown_responsive_exposure_armed": False,
            "selection_individual_gate_counts": gate_counts,
            "selection_role": config["selection_role"],
        },
        "calibration": {
            "qualified_native_floor_pct": qualified_dd_floor,
            "accelerated_native_minus_raw_closed_balance_gap_percentage_points": observed_gap,
            "state_dependent_scaling_and_lattice_reserve_percentage_points": state_reserve,
            "per_scaled_position_modeling_reserve_usd": scaled_reserve,
            "selection_profit_uncertainty_reserve_usd": global_profit_reserve,
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
                    "drawdown_trigger_pct": winner["drawdown_trigger_pct"],
                    "risk_multiplier": winner["risk_multiplier"],
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
            "state_dependent_nonterminal_exposure_control": True,
            "existing_positions_resized": False,
            "later_original_births_retained": True,
            "freed_capacity_synthetic_births": False,
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
