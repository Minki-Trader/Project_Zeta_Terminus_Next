from __future__ import annotations

import csv
import hashlib
import itertools
import json
from datetime import datetime
from pathlib import Path

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
    / "dd20-capital-composition-proxy-v1"
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
    if len(rows) != int(expected["closed_lifecycles"]):
        raise RuntimeError("declared lifecycle count does not match the copied input")
    if abs(actual - float(expected["actual_net_usd"])) > 1.0e-7:
        raise RuntimeError("declared actual net does not match the copied input")
    if abs(stressed - float(expected["stressed_net_usd"])) > 1.0e-7:
        raise RuntimeError("declared stressed net does not match the copied input")
    if {str(row["component"]) for row in rows} != set(components):
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


def drawdown_and_minimum(
    balances: np.ndarray,
    reference_capital: float,
    start: int,
    end: int,
) -> tuple[np.ndarray, np.ndarray]:
    if start >= end:
        raise RuntimeError("empty proxy epoch")
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
    return drawdown, np.min(block, axis=1)


def evaluate_batch(
    weights: np.ndarray,
    actual_matrix: np.ndarray,
    stressed_matrix: np.ndarray,
    epochs: list[dict[str, object]],
    reference_capital: float,
) -> dict[str, np.ndarray]:
    actual_increments = weights @ actual_matrix
    stressed_increments = weights @ stressed_matrix
    actual_balances = reference_capital + np.cumsum(actual_increments, axis=1)
    stressed_balances = reference_capital + np.cumsum(stressed_increments, axis=1)
    event_count = actual_matrix.shape[1]
    actual_dd, actual_minimum = drawdown_and_minimum(
        actual_balances, reference_capital, 0, event_count
    )
    stressed_dd, stressed_minimum = drawdown_and_minimum(
        stressed_balances, reference_capital, 0, event_count
    )
    result: dict[str, np.ndarray] = {
        "full_actual_net": np.sum(actual_increments, axis=1),
        "full_stressed_net": np.sum(stressed_increments, axis=1),
        "full_proxy_dd": np.maximum(actual_dd, stressed_dd),
        "full_min_balance": np.minimum(actual_minimum, stressed_minimum),
    }
    for epoch in epochs:
        epoch_id = str(epoch["id"])
        start = int(epoch["start_index"])
        end = int(epoch["end_index"])
        epoch_actual_dd, epoch_actual_minimum = drawdown_and_minimum(
            actual_balances, reference_capital, start, end
        )
        epoch_stressed_dd, epoch_stressed_minimum = drawdown_and_minimum(
            stressed_balances, reference_capital, start, end
        )
        result[f"{epoch_id}_actual_net"] = np.sum(
            actual_increments[:, start:end], axis=1
        )
        result[f"{epoch_id}_stressed_net"] = np.sum(
            stressed_increments[:, start:end], axis=1
        )
        result[f"{epoch_id}_proxy_dd"] = np.maximum(
            epoch_actual_dd, epoch_stressed_dd
        )
        result[f"{epoch_id}_min_balance"] = np.minimum(
            epoch_actual_minimum, epoch_stressed_minimum
        )
    return result


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
    actual_dd, actual_minimum = drawdown_and_minimum(
        actual_balances, reference_capital, 0, actual_matrix.shape[1]
    )
    stressed_dd, stressed_minimum = drawdown_and_minimum(
        stressed_balances, reference_capital, 0, stressed_matrix.shape[1]
    )
    return {
        "actual_net_usd": float(np.sum(actual_increments)),
        "stressed_net_usd": float(np.sum(stressed_increments)),
        "proxy_drawdown_pct": float(max(actual_dd[0], stressed_dd[0])),
        "minimum_balance_usd": float(min(actual_minimum[0], stressed_minimum[0])),
    }


def serializable_record(
    record: dict[str, object], epochs: list[dict[str, object]]
) -> dict[str, object]:
    output: dict[str, object] = {
        "weights": [float(value) for value in record["weights"]],
        "gross_weight_budget": float(record["gross_weight_budget"]),
        "active_components": int(record["active_components"]),
        "selection": {
            "actual_net_usd": float(record["full_actual_net"]),
            "stressed_net_usd": float(record["full_stressed_net"]),
            "proxy_drawdown_pct": float(record["full_proxy_dd"]),
            "minimum_balance_usd": float(record["full_min_balance"]),
        },
        "weakest_epoch_stressed_uplift_ratio": float(record["weakest_epoch_ratio"]),
        "epochs": [],
    }
    epoch_output: list[dict[str, object]] = []
    for epoch in epochs:
        epoch_id = str(epoch["id"])
        epoch_output.append(
            {
                "id": epoch_id,
                "actual_net_usd": float(record[f"{epoch_id}_actual_net"]),
                "stressed_net_usd": float(record[f"{epoch_id}_stressed_net"]),
                "proxy_drawdown_pct": float(record[f"{epoch_id}_proxy_dd"]),
                "minimum_balance_usd": float(record[f"{epoch_id}_min_balance"]),
            }
        )
    output["epochs"] = epoch_output
    return output


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
    epochs: list[dict[str, object]] = []
    for declared in config["selection_epochs"]:
        start_time = datetime.strptime(declared["start"], TIME_FORMAT)
        end_time = datetime.strptime(declared["end"], TIME_FORMAT)
        start_index = next(
            (index for index, value in enumerate(selection_times) if value >= start_time),
            len(selection_times),
        )
        end_index = next(
            (index for index, value in enumerate(selection_times) if value >= end_time),
            len(selection_times),
        )
        if start_index >= end_index:
            raise RuntimeError("declared selection epoch is empty")
        epochs.append(
            {
                "id": str(declared["id"]),
                "start": declared["start"],
                "end": declared["end"],
                "start_index": start_index,
                "end_index": end_index,
            }
        )
    if int(epochs[0]["start_index"]) != 0 or int(epochs[-1]["end_index"]) != len(
        selection_rows
    ):
        raise RuntimeError("declared epochs do not cover the selection lifecycle stream")
    for left, right in zip(epochs, epochs[1:]):
        if int(left["end_index"]) != int(right["start_index"]):
            raise RuntimeError("declared epochs are not contiguous")

    grid = np.asarray(config["weight_grid"], dtype=np.float64)
    budgets = np.asarray(config["gross_weight_budgets"], dtype=np.float64)
    candidate_weights = np.asarray(
        [
            weights
            for weights in itertools.product(grid, repeat=len(components))
            if np.any(np.isclose(sum(weights), budgets, atol=1.0e-12, rtol=0.0))
            and sum(value > 0.0 for value in weights)
            >= int(config["minimum_active_components"])
        ],
        dtype=np.float64,
    )
    if len(candidate_weights) != int(config["expected_compositions"]):
        raise RuntimeError("composition count does not match the frozen contract")

    base_weights = np.ones(len(components), dtype=np.float64)
    base_batch = evaluate_batch(
        base_weights.reshape(1, -1),
        selection_actual,
        selection_stressed,
        epochs,
        reference_capital,
    )
    base_epoch_stressed = {
        str(epoch["id"]): float(base_batch[f"{epoch['id']}_stressed_net"][0])
        for epoch in epochs
    }
    if any(value <= 0.0 for value in base_epoch_stressed.values()):
        raise RuntimeError("unweighted base has a nonpositive declared epoch")

    hard_dd = float(config["hard_proxy_drawdown_pct"])
    eligible: list[dict[str, object]] = []
    chunk_size = 1024
    for start in range(0, len(candidate_weights), chunk_size):
        chunk = candidate_weights[start : start + chunk_size]
        result = evaluate_batch(
            chunk,
            selection_actual,
            selection_stressed,
            epochs,
            reference_capital,
        )
        mask = (
            (result["full_actual_net"] > 0.0)
            & (result["full_stressed_net"] > 0.0)
            & (result["full_min_balance"] > 0.0)
            & (result["full_proxy_dd"] <= hard_dd + 1.0e-12)
        )
        for epoch in epochs:
            epoch_id = str(epoch["id"])
            mask &= (
                (result[f"{epoch_id}_actual_net"] > 0.0)
                & (result[f"{epoch_id}_stressed_net"] > 0.0)
                & (result[f"{epoch_id}_min_balance"] > 0.0)
                & (result[f"{epoch_id}_proxy_dd"] <= hard_dd + 1.0e-12)
            )
        for local_index in np.flatnonzero(mask):
            weights = tuple(float(value) for value in chunk[local_index])
            record: dict[str, object] = {
                "weights": weights,
                "gross_weight_budget": sum(weights),
                "active_components": sum(value > 0.0 for value in weights),
            }
            for key, values in result.items():
                record[key] = float(values[local_index])
            record["weakest_epoch_ratio"] = min(
                float(record[f"{epoch['id']}_stressed_net"])
                / base_epoch_stressed[str(epoch["id"])]
                for epoch in epochs
            )
            eligible.append(record)

    recent_epoch_id = str(epochs[-1]["id"])
    maximum_order = sorted(
        eligible,
        key=lambda record: (
            -float(record["full_stressed_net"]),
            -float(record["full_actual_net"]),
            float(record["full_proxy_dd"]),
            record["weights"],
        ),
    )
    recent_order = sorted(
        eligible,
        key=lambda record: (
            -float(record[f"{recent_epoch_id}_stressed_net"]),
            -float(record["full_stressed_net"]),
            float(record["full_proxy_dd"]),
            record["weights"],
        ),
    )
    stability_order = sorted(
        eligible,
        key=lambda record: (
            -float(record["weakest_epoch_ratio"]),
            -float(record["full_stressed_net"]),
            float(record["full_proxy_dd"]),
            record["weights"],
        ),
    )
    role_orders = [
        ("maximum_full_stressed_profit", maximum_order),
        ("maximum_recent_selection_stressed_profit", recent_order),
        ("maximum_weakest_epoch_uplift", stability_order),
    ]
    selected: list[tuple[str, dict[str, object]]] = []
    used_weights: set[tuple[float, ...]] = set()
    for role, ordering in role_orders:
        winner = next(
            record for record in ordering if record["weights"] not in used_weights
        )
        used_weights.add(winner["weights"])
        selected.append((role, winner))

    # The known later segment is not read until all selection roles are fixed.
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
            and later["minimum_balance_usd"] > 0.0
            and later["proxy_drawdown_pct"] <= hard_dd + 1.0e-12
        )
        item = {
            "role": role,
            **serializable_record(record, epochs),
            "later_observation": later,
            "later_confirmation_passed": later_pass,
        }
        selected_output.append(item)
        if later_pass:
            mt5_shortlist.append(
                {
                    "role": role,
                    "weights": item["weights"],
                    "gross_weight_budget": item["gross_weight_budget"],
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

    base_record: dict[str, object] = {
        "weights": tuple(float(value) for value in base_weights),
        "gross_weight_budget": float(np.sum(base_weights)),
        "active_components": len(components),
        **{key: float(value[0]) for key, value in base_batch.items()},
        "weakest_epoch_ratio": 1.0,
    }
    output = {
        "schema": "zeta-dd20-capital-composition-proxy-result-v1",
        "status": "PROXY_COMPLETE",
        "campaign": config["campaign"],
        "contract_sha256": sha256(CONFIG_PATH),
        "script_sha256": sha256(SCRIPT_PATH),
        "input_lifecycle_sha256": sha256(lifecycle_path),
        "selection_only_search": {
            "known_later_used_in_ranking_or_weight_tuning": False,
            "component_order": components,
            "selection_lifecycles": len(selection_rows),
            "weight_grid": [float(value) for value in grid],
            "gross_weight_budgets": [float(value) for value in budgets],
            "minimum_active_components": int(config["minimum_active_components"]),
            "compositions": len(candidate_weights),
            "eligible_compositions": len(eligible),
            "hard_proxy_drawdown_pct": hard_dd,
            "epochs": [
                {
                    "id": epoch["id"],
                    "start": epoch["start"],
                    "end": epoch["end"],
                    "lifecycles": int(epoch["end_index"]) - int(epoch["start_index"]),
                }
                for epoch in epochs
            ],
        },
        "unweighted_base": {
            **serializable_record(base_record, epochs),
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
        "top_full_stressed_profit": [
            serializable_record(record, epochs) for record in maximum_order[:10]
        ],
        "top_recent_selection_stressed_profit": [
            serializable_record(record, epochs) for record in recent_order[:10]
        ],
        "top_weakest_epoch_uplift": [
            serializable_record(record, epochs) for record in stability_order[:10]
        ],
        "limitations": [
            "Fixed observed entry/exit order; composition does not feed back into stops, admission, margin, overlap or later sizing.",
            "Closed-balance proxy drawdown is not MT5 mark-to-market equity drawdown.",
            "The known later segment confirms frozen selection roles only and never retunes them.",
            "A surviving proxy composition is a bounded MT5 hypothesis, not economic proof or Live authority."
        ],
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
                "compositions": len(candidate_weights),
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
