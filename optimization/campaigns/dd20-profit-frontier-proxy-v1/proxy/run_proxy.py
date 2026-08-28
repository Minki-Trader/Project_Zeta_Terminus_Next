from __future__ import annotations

import csv
import hashlib
import itertools
import json
from datetime import datetime
from pathlib import Path
from statistics import median

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
    / "dd20-profit-frontier-proxy-v1"
    / "output"
    / "proxy-result.json"
)
TIME_FORMAT = "%Y.%m.%d %H:%M:%S"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def extract_close_segment(path: Path, target_segment: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    segment = 0
    previous_sequence: int | None = None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for source in csv.DictReader(handle):
            sequence = int(source["research_state_sequence"])
            if previous_sequence is not None and sequence < previous_sequence:
                segment += 1
            previous_sequence = sequence
            if segment > target_segment:
                break
            if segment != target_segment or source["event"] != "CLOSE":
                continue
            rows.append(
                {
                    "server_time": datetime.strptime(source["server_time"], TIME_FORMAT),
                    "component": source["component_id"],
                    "actual_net_usd": float(source["actual_net_usd"]),
                    "stressed_net_usd": float(source["stressed_net_usd"]),
                }
            )
    return rows


def bind_segment(
    rows: list[dict[str, object]],
    expected: dict[str, object],
    components: list[str],
) -> None:
    actual = sum(float(row["actual_net_usd"]) for row in rows)
    stressed = sum(float(row["stressed_net_usd"]) for row in rows)
    observed_components = {str(row["component"]) for row in rows}
    if len(rows) != int(expected["closed_lifecycles"]):
        raise RuntimeError("declared lifecycle count does not match the copied input")
    if abs(actual - float(expected["actual_net_usd"])) > 1.0e-7:
        raise RuntimeError("declared actual net does not match the copied input")
    if abs(stressed - float(expected["stressed_net_usd"])) > 1.0e-7:
        raise RuntimeError("declared stressed net does not match the copied input")
    if observed_components != set(components):
        raise RuntimeError("declared component set does not match the copied input")


def component_event_matrices(
    rows: list[dict[str, object]], components: list[str]
) -> tuple[np.ndarray, np.ndarray, list[datetime]]:
    component_index = {component: index for index, component in enumerate(components)}
    actual = np.zeros((len(components), len(rows)), dtype=np.float64)
    stressed = np.zeros_like(actual)
    times: list[datetime] = []
    for event_index, row in enumerate(rows):
        index = component_index[str(row["component"])]
        actual[index, event_index] = float(row["actual_net_usd"])
        stressed[index, event_index] = float(row["stressed_net_usd"])
        times.append(row["server_time"])
    return actual, stressed, times


def drawdown_percentages(
    balances: np.ndarray,
    reference_capital: float,
    start: int,
    end: int,
) -> tuple[np.ndarray, np.ndarray]:
    if start >= end:
        raise RuntimeError("empty proxy drawdown block")
    starting_balance = (
        np.full((balances.shape[0], 1), reference_capital, dtype=np.float64)
        if start == 0
        else balances[:, start - 1 : start]
    )
    block = balances[:, start:end]
    running_peak = np.maximum.accumulate(
        np.maximum(block, starting_balance), axis=1
    )
    drawdown = np.max((running_peak - block) / running_peak * 100.0, axis=1)
    minimum_balance = np.min(block, axis=1)
    return drawdown, minimum_balance


def evaluate_selection_batch(
    weights: np.ndarray,
    actual_matrix: np.ndarray,
    stressed_matrix: np.ndarray,
    split_index: int,
    reference_capital: float,
) -> dict[str, np.ndarray]:
    actual_increments = weights @ actual_matrix
    stressed_increments = weights @ stressed_matrix
    actual_balances = reference_capital + np.cumsum(actual_increments, axis=1)
    stressed_balances = reference_capital + np.cumsum(stressed_increments, axis=1)
    event_count = actual_matrix.shape[1]

    actual_full_dd, actual_full_min = drawdown_percentages(
        actual_balances, reference_capital, 0, event_count
    )
    stressed_full_dd, stressed_full_min = drawdown_percentages(
        stressed_balances, reference_capital, 0, event_count
    )
    actual_a_dd, actual_a_min = drawdown_percentages(
        actual_balances, reference_capital, 0, split_index
    )
    stressed_a_dd, stressed_a_min = drawdown_percentages(
        stressed_balances, reference_capital, 0, split_index
    )
    actual_b_dd, actual_b_min = drawdown_percentages(
        actual_balances, reference_capital, split_index, event_count
    )
    stressed_b_dd, stressed_b_min = drawdown_percentages(
        stressed_balances, reference_capital, split_index, event_count
    )

    return {
        "full_actual_net": np.sum(actual_increments, axis=1),
        "full_stressed_net": np.sum(stressed_increments, axis=1),
        "full_proxy_dd": np.maximum(actual_full_dd, stressed_full_dd),
        "full_min_balance": np.minimum(actual_full_min, stressed_full_min),
        "a_actual_net": np.sum(actual_increments[:, :split_index], axis=1),
        "a_stressed_net": np.sum(stressed_increments[:, :split_index], axis=1),
        "a_proxy_dd": np.maximum(actual_a_dd, stressed_a_dd),
        "a_min_balance": np.minimum(actual_a_min, stressed_a_min),
        "b_actual_net": np.sum(actual_increments[:, split_index:], axis=1),
        "b_stressed_net": np.sum(stressed_increments[:, split_index:], axis=1),
        "b_proxy_dd": np.maximum(actual_b_dd, stressed_b_dd),
        "b_min_balance": np.minimum(actual_b_min, stressed_b_min),
    }


def evaluate_period(
    weights: np.ndarray,
    actual_matrix: np.ndarray,
    stressed_matrix: np.ndarray,
    reference_capital: float,
) -> dict[str, float]:
    actual_increments = weights @ actual_matrix
    stressed_increments = weights @ stressed_matrix
    actual_balances = (
        reference_capital + np.cumsum(actual_increments)
    ).reshape(1, -1)
    stressed_balances = (
        reference_capital + np.cumsum(stressed_increments)
    ).reshape(1, -1)
    actual_dd, actual_minimum = drawdown_percentages(
        actual_balances, reference_capital, 0, actual_matrix.shape[1]
    )
    stressed_dd, stressed_minimum = drawdown_percentages(
        stressed_balances, reference_capital, 0, stressed_matrix.shape[1]
    )
    return {
        "actual_net_usd": float(np.sum(actual_increments)),
        "stressed_net_usd": float(np.sum(stressed_increments)),
        "proxy_drawdown_pct": float(max(actual_dd[0], stressed_dd[0])),
        "minimum_balance_usd": float(min(actual_minimum[0], stressed_minimum[0])),
    }


def serializable_metrics(record: dict[str, object]) -> dict[str, object]:
    return {
        "weights": [float(value) for value in record["weights"]],
        "selection": {
            "actual_net_usd": float(record["full_actual_net"]),
            "stressed_net_usd": float(record["full_stressed_net"]),
            "proxy_drawdown_pct": float(record["full_proxy_dd"]),
            "minimum_balance_usd": float(record["full_min_balance"]),
        },
        "block_a": {
            "actual_net_usd": float(record["a_actual_net"]),
            "stressed_net_usd": float(record["a_stressed_net"]),
            "proxy_drawdown_pct": float(record["a_proxy_dd"]),
            "minimum_balance_usd": float(record["a_min_balance"]),
        },
        "block_b": {
            "actual_net_usd": float(record["b_actual_net"]),
            "stressed_net_usd": float(record["b_stressed_net"]),
            "proxy_drawdown_pct": float(record["b_proxy_dd"]),
            "minimum_balance_usd": float(record["b_min_balance"]),
        },
        "weaker_block_stressed_uplift_ratio": float(record["stable_ratio"]),
        "eligible_one_step_neighbors": int(record["eligible_neighbors"]),
        "broad_support_neighbors": int(record["plateau_support"]),
        "one_step_neighborhood_median_stressed_net_usd": float(
            record["plateau_median"]
        ),
    }


def rounded(value: object) -> object:
    if isinstance(value, float):
        return round(value, 10)
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [rounded(item) for item in value]
    return value


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    reference_capital = float(config["reference_capital_usd"])
    components = [str(value) for value in config["components"]]
    lifecycle_path = REPOSITORY_ROOT / str(config["input"]["lifecycle_path"])
    if sha256(lifecycle_path) != str(config["input"]["lifecycle_sha256"]):
        raise RuntimeError("copied lifecycle input hash does not match the contract")

    selection_rows = extract_close_segment(
        lifecycle_path, int(config["input"]["selection_segment_index"])
    )
    bind_segment(selection_rows, config["input"]["selection_expected"], components)
    selection_actual, selection_stressed, selection_times = component_event_matrices(
        selection_rows, components
    )
    split_time = datetime.strptime(config["selection_split_server"], TIME_FORMAT)
    split_index = next(
        (index for index, value in enumerate(selection_times) if value >= split_time),
        len(selection_times),
    )
    if split_index <= 0 or split_index >= len(selection_times):
        raise RuntimeError("selection split does not divide the lifecycle stream")

    grid = np.asarray(config["weight_grid"], dtype=np.float64)
    all_weights = np.asarray(
        list(itertools.product(grid, repeat=len(components))), dtype=np.float64
    )
    base_weights = np.ones(len(components), dtype=np.float64)
    base_batch = evaluate_selection_batch(
        base_weights.reshape(1, -1),
        selection_actual,
        selection_stressed,
        split_index,
        reference_capital,
    )
    base_a_stressed = float(base_batch["a_stressed_net"][0])
    base_b_stressed = float(base_batch["b_stressed_net"][0])
    if base_a_stressed <= 0.0 or base_b_stressed <= 0.0:
        raise RuntimeError("the declared base does not have positive stressed net in both blocks")

    hard_dd = float(config["hard_proxy_drawdown_pct"])
    eligible: list[dict[str, object]] = []
    chunk_size = 1024
    for start in range(0, len(all_weights), chunk_size):
        chunk = all_weights[start : start + chunk_size]
        result = evaluate_selection_batch(
            chunk,
            selection_actual,
            selection_stressed,
            split_index,
            reference_capital,
        )
        mask = (
            (result["full_actual_net"] > 0.0)
            & (result["full_stressed_net"] > 0.0)
            & (result["a_actual_net"] > 0.0)
            & (result["a_stressed_net"] > 0.0)
            & (result["b_actual_net"] > 0.0)
            & (result["b_stressed_net"] > 0.0)
            & (result["full_min_balance"] > 0.0)
            & (result["a_min_balance"] > 0.0)
            & (result["b_min_balance"] > 0.0)
            & (result["full_proxy_dd"] <= hard_dd + 1.0e-12)
            & (result["a_proxy_dd"] <= hard_dd + 1.0e-12)
            & (result["b_proxy_dd"] <= hard_dd + 1.0e-12)
        )
        for local_index in np.flatnonzero(mask):
            record: dict[str, object] = {
                "weights": tuple(float(value) for value in chunk[local_index])
            }
            for key, values in result.items():
                record[key] = float(values[local_index])
            record["stable_ratio"] = min(
                float(record["a_stressed_net"]) / base_a_stressed,
                float(record["b_stressed_net"]) / base_b_stressed,
            )
            eligible.append(record)

    grid_index = {float(value): index for index, value in enumerate(grid)}
    eligible_by_key = {
        tuple(grid_index[float(value)] for value in record["weights"]): record
        for record in eligible
    }
    neighbor_floor = float(config["plateau_neighbor_floor_fraction"])
    for key, record in eligible_by_key.items():
        neighbors: list[dict[str, object]] = []
        for component_index in range(len(components)):
            for delta in (-1, 1):
                neighbor_key = list(key)
                neighbor_key[component_index] += delta
                if not 0 <= neighbor_key[component_index] < len(grid):
                    continue
                neighbor = eligible_by_key.get(tuple(neighbor_key))
                if neighbor is not None:
                    neighbors.append(neighbor)
        record["eligible_neighbors"] = len(neighbors)
        record["plateau_support"] = sum(
            float(neighbor["full_stressed_net"])
            >= neighbor_floor * float(record["full_stressed_net"])
            for neighbor in neighbors
        )
        record["plateau_median"] = median(
            [float(record["full_stressed_net"])]
            + [float(neighbor["full_stressed_net"]) for neighbor in neighbors]
        )

    maximum_order = sorted(
        eligible,
        key=lambda record: (
            -float(record["full_stressed_net"]),
            -float(record["full_actual_net"]),
            float(record["full_proxy_dd"]),
            record["weights"],
        ),
    )
    plateau_order = sorted(
        eligible,
        key=lambda record: (
            -float(record["plateau_median"]),
            -int(record["plateau_support"]),
            -float(record["full_stressed_net"]),
            float(record["full_proxy_dd"]),
            record["weights"],
        ),
    )
    balanced_order = sorted(
        eligible,
        key=lambda record: (
            -float(record["stable_ratio"]),
            -float(record["full_stressed_net"]),
            float(record["full_proxy_dd"]),
            record["weights"],
        ),
    )
    role_orders = [
        ("maximum_stressed_profit", maximum_order),
        ("broad_profit_plateau", plateau_order),
        ("balanced_half_stability", balanced_order),
    ]
    selected: list[tuple[str, dict[str, object]]] = []
    used_weights: set[tuple[float, ...]] = set()
    for role, ordering in role_orders:
        winner = next(
            record for record in ordering if record["weights"] not in used_weights
        )
        used_weights.add(winner["weights"])
        selected.append((role, winner))

    # The later segment is not read until every selection role and weight is fixed.
    later_rows = extract_close_segment(
        lifecycle_path, int(config["input"]["later_segment_index"])
    )
    bind_segment(later_rows, config["input"]["later_expected"], components)
    later_actual, later_stressed, _ = component_event_matrices(later_rows, components)
    base_later = evaluate_period(
        base_weights, later_actual, later_stressed, reference_capital
    )

    selected_output: list[dict[str, object]] = []
    mt5_shortlist: list[dict[str, object]] = []
    for role, record in selected:
        weights = np.asarray(record["weights"], dtype=np.float64)
        later = evaluate_period(weights, later_actual, later_stressed, reference_capital)
        later_pass = (
            later["actual_net_usd"] > 0.0
            and later["stressed_net_usd"] > 0.0
            and later["proxy_drawdown_pct"] <= hard_dd + 1.0e-12
            and later["minimum_balance_usd"] > 0.0
        )
        item = {
            "role": role,
            **serializable_metrics(record),
            "later_observation": later,
            "later_confirmation_passed": later_pass,
        }
        selected_output.append(item)
        if later_pass:
            mt5_shortlist.append(
                {
                    "role": role,
                    "weights": item["weights"],
                    "selection_stressed_net_usd": item["selection"][
                        "stressed_net_usd"
                    ],
                    "selection_proxy_drawdown_pct": item["selection"][
                        "proxy_drawdown_pct"
                    ],
                    "later_stressed_net_usd": later["stressed_net_usd"],
                    "later_proxy_drawdown_pct": later["proxy_drawdown_pct"],
                }
            )

    base_record = {
        "weights": tuple(float(value) for value in base_weights),
        **{key: float(value[0]) for key, value in base_batch.items()},
        "stable_ratio": 1.0,
        "eligible_neighbors": 0,
        "plateau_support": 0,
        "plateau_median": float(base_batch["full_stressed_net"][0]),
    }
    output = {
        "schema": "zeta-dd20-profit-frontier-proxy-result-v1",
        "status": "PROXY_COMPLETE",
        "campaign": config["campaign"],
        "contract_sha256": sha256(CONFIG_PATH),
        "script_sha256": sha256(SCRIPT_PATH),
        "input_lifecycle_sha256": sha256(lifecycle_path),
        "selection_only_search": {
            "latest_used_in_ranking_or_weight_tuning": False,
            "component_order": components,
            "selection_lifecycles": len(selection_rows),
            "selection_split_index": split_index,
            "selection_block_a_lifecycles": split_index,
            "selection_block_b_lifecycles": len(selection_rows) - split_index,
            "grid_values": [float(value) for value in grid],
            "combinations": len(all_weights),
            "eligible_combinations": len(eligible),
            "hard_proxy_drawdown_pct": hard_dd,
        },
        "unweighted_base": {
            **serializable_metrics(base_record),
            "observed_mt5_equity_drawdown_pct": float(
                config["input"]["selection_expected"]["mt5_equity_drawdown_pct"]
            ),
            "later_observation": base_later,
            "observed_later_mt5_equity_drawdown_pct": float(
                config["input"]["later_expected"]["mt5_equity_drawdown_pct"]
            ),
        },
        "selection_roles_frozen_before_later_open": True,
        "selected_roles": selected_output,
        "mt5_shortlist": mt5_shortlist,
        "mt5_shortlist_size": len(mt5_shortlist),
        "maximum_mt5_shortlist_size": int(config["mt5"]["maximum_shortlist_size"]),
        "mt5_launched": False,
        "top_selection_stressed_profit": [
            serializable_metrics(record) for record in maximum_order[:10]
        ],
        "limitations": [
            "Fixed observed entry/exit/lifecycle order; changed weights do not feed back into stops, admissions, margin, overlap or later sizing.",
            "Closed-balance proxy drawdown is not MT5 mark-to-market equity drawdown.",
            "The known later segment confirms frozen selection roles only and never retunes or replaces them.",
            "A proxy shortlist is information for a small MT5 comparison, not economic proof or Live authority."
        ]
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(rounded(output), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": output["status"],
                "combinations": len(all_weights),
                "eligible": len(eligible),
                "selected_roles": [
                    {"role": item["role"], "weights": item["weights"]}
                    for item in selected_output
                ],
                "mt5_shortlist_size": len(mt5_shortlist),
                "output": str(OUTPUT_PATH),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
