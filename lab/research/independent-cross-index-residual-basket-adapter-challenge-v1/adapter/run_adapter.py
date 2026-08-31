#!/usr/bin/env python3
"""Causal cross-index residual basket adapter and economic proxy.

Precheck is strictly structural: it never fits a pair, calculates a residual,
creates a decision, simulates a basket, or opens the locked confirmation period.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


FAMILY_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = FAMILY_ROOT / "config" / "challenge-contract.json"
DECLARATION_PATH = (
    FAMILY_ROOT
    / "evidence"
    / "INDEPENDENT_CROSS_INDEX_RESIDUAL_BASKET_ADAPTER_CHALLENGE_V1_DECLARATION.json"
)
FREEZE_PATH = (
    FAMILY_ROOT
    / "evidence"
    / "INDEPENDENT_CROSS_INDEX_RESIDUAL_BASKET_ADAPTER_CHALLENGE_V1_IMPLEMENTATION_FREEZE.json"
)
ARTIFACT_ROOT = (
    PROJECT_ROOT
    / "lab"
    / "artifacts"
    / "independent-cross-index-residual-basket-adapter-challenge-v1"
)
SYMBOLS = ("US100", "US30", "US500")
PAIRS = (("US100", "US30"), ("US100", "US500"), ("US30", "US500"))
INPUT_FILENAMES = {
    "US100": "US100_H1_BARS_20220701_20260821.csv",
    "US30": "US30_H1_BARS_20220701_20260821.csv",
    "US500": "US500_H1_BARS_20220701_20260821.csv",
}
REQUIRED_COLUMNS = (
    "time_epoch",
    "time_server",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
)
TICK_SIZE = 0.01
TICK_VALUE_PER_LOT = 0.01
DOLLARS_PER_POINT_PER_LOT = TICK_VALUE_PER_LOT / TICK_SIZE
EPS = 1e-12


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def line_count(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"not JSON serializable: {type(value)!r}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(
            payload,
            handle,
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
            default=json_default,
            allow_nan=False,
        )
        handle.write("\n")


def project_relative(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def verify_file_record(record: dict[str, Any]) -> None:
    path = PROJECT_ROOT / record["path"]
    if not path.is_file():
        raise RuntimeError(f"missing frozen file: {path}")
    if path.stat().st_size != int(record["bytes"]):
        raise RuntimeError(f"byte mismatch: {path}")
    if sha256_file(path) != str(record["sha256"]).upper():
        raise RuntimeError(f"SHA-256 mismatch: {path}")
    if "lines" in record and line_count(path) != int(record["lines"]):
        raise RuntimeError(f"line-count mismatch: {path}")


def verify_authorities(mode: str) -> tuple[dict[str, Any], dict[str, Any]]:
    contract = load_json(CONTRACT_PATH)
    declaration = load_json(DECLARATION_PATH)
    verify_file_record(declaration["frozen_files"]["readme"])
    verify_file_record(declaration["frozen_files"]["contract"])
    for symbol in SYMBOLS:
        authority = declaration["input_authorities"][symbol]
        copied = FAMILY_ROOT / "data" / "input" / INPUT_FILENAMES[symbol]
        if not copied.is_file():
            raise RuntimeError(f"missing family input: {symbol}")
        if copied.stat().st_size != int(authority["bytes"]):
            raise RuntimeError(f"input byte mismatch: {symbol}")
        if sha256_file(copied) != authority["sha256"]:
            raise RuntimeError(f"input SHA-256 mismatch: {symbol}")
    benchmark = contract["exact_v8_challenge"]
    verify_file_record(
        {
            "path": benchmark["authority_path"],
            "bytes": benchmark["authority_bytes"],
            "sha256": benchmark["authority_sha256"],
        }
    )
    if mode != "precheck":
        if not FREEZE_PATH.is_file():
            raise RuntimeError("implementation freeze is absent")
        freeze = load_json(FREEZE_PATH)
        if freeze.get("status") != "IMPLEMENTATION_FROZEN_PREDEVELOPMENT_OUTCOME":
            raise RuntimeError("implementation freeze status is not authoritative")
        for record in freeze["frozen_files"].values():
            if isinstance(record, dict) and "path" in record:
                verify_file_record(record)
            elif isinstance(record, dict):
                for nested in record.values():
                    verify_file_record(nested)
    return contract, declaration


def load_common_frame(end_exclusive: pd.Timestamp) -> pd.DataFrame:
    per_symbol: dict[str, pd.DataFrame] = {}
    common_epochs: pd.Index | None = None
    for symbol in SYMBOLS:
        path = FAMILY_ROOT / "data" / "input" / INPUT_FILENAMES[symbol]
        frame = pd.read_csv(path, usecols=list(REQUIRED_COLUMNS))
        if tuple(frame.columns) != REQUIRED_COLUMNS:
            raise RuntimeError(f"column mismatch: {symbol}")
        if frame["time_epoch"].duplicated().any():
            raise RuntimeError(f"duplicate epoch: {symbol}")
        server_time = pd.to_datetime(
            frame["time_server"], format="%Y.%m.%d %H:%M:%S", errors="raise"
        )
        epoch_time = pd.to_datetime(frame["time_epoch"], unit="s", utc=True).dt.tz_localize(
            None
        )
        if not server_time.equals(epoch_time):
            raise RuntimeError(f"server/epoch time mismatch: {symbol}")
        frame = frame.loc[server_time < end_exclusive].copy()
        frame["time"] = server_time.loc[frame.index].to_numpy()
        frame = frame.set_index("time_epoch", verify_integrity=True).sort_index()
        per_symbol[symbol] = frame
        common_epochs = (
            frame.index
            if common_epochs is None
            else common_epochs.intersection(frame.index, sort=True)
        )
    if common_epochs is None or common_epochs.empty:
        raise RuntimeError("no common H1 rows")
    common_epochs = common_epochs.sort_values()
    base_time = per_symbol[SYMBOLS[0]].loc[common_epochs, "time"].reset_index(drop=True)
    output = pd.DataFrame(
        {
            "time_epoch": common_epochs.to_numpy(dtype=np.int64),
            "time": base_time.to_numpy(),
        }
    )
    for symbol in SYMBOLS:
        aligned = per_symbol[symbol].loc[common_epochs]
        if not aligned["time"].reset_index(drop=True).equals(base_time):
            raise RuntimeError(f"common time mismatch: {symbol}")
        for column in REQUIRED_COLUMNS[2:]:
            output[f"{symbol}_{column}"] = aligned[column].to_numpy()
    if output["time"].duplicated().any() or not output["time"].is_monotonic_increasing:
        raise RuntimeError("common timeline is invalid")
    return output


def build_atr(frame: pd.DataFrame) -> dict[str, np.ndarray]:
    output: dict[str, np.ndarray] = {}
    for symbol in SYMBOLS:
        high = frame[f"{symbol}_high"].astype(float)
        low = frame[f"{symbol}_low"].astype(float)
        close = frame[f"{symbol}_close"].astype(float)
        previous_close = close.shift(1)
        true_range = pd.concat(
            [
                high - low,
                (high - previous_close).abs(),
                (low - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        output[symbol] = (
            true_range.rolling(24, min_periods=24).mean().to_numpy(dtype=np.float64)
        )
    return output


def structural_indices(
    frame: pd.DataFrame,
    atr: dict[str, np.ndarray],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> np.ndarray:
    selected: list[int] = []
    for index in range(960, len(frame) - 2):
        timestamp = pd.Timestamp(frame.at[index, "time"])
        if timestamp < start or timestamp >= end:
            continue
        if pd.Timestamp(frame.at[index + 2, "time"]) >= end:
            continue
        if any(
            not np.isfinite(atr[symbol][index - 1]) or atr[symbol][index - 1] <= 0
            for symbol in SYMBOLS
        ):
            continue
        selected.append(index)
    return np.asarray(selected, dtype=np.int64)


def normal_trading_days(
    frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp
) -> int:
    mask = (frame["time"] >= start) & (frame["time"] < end)
    counts = frame.loc[mask, "time"].dt.normalize().value_counts()
    return int((counts >= 20).sum())


@dataclass(frozen=True)
class PairVolume:
    first_volume: float
    second_volume: float
    first_planned_loss: float
    second_planned_loss: float
    planned_basket_loss: float
    leg_risk_ratio: float


def pair_volume(balance: float, first_atr: float, second_atr: float) -> PairVolume | None:
    if balance <= 0 or first_atr <= 0 or second_atr <= 0:
        return None
    target_leg_loss = balance * 0.01
    first_raw = target_leg_loss / (first_atr * DOLLARS_PER_POINT_PER_LOT)
    second_raw = target_leg_loss / (second_atr * DOLLARS_PER_POINT_PER_LOT)
    first_volume = math.floor(first_raw / 0.01 + EPS) * 0.01
    second_volume = math.floor(second_raw / 0.01 + EPS) * 0.01
    first_volume = max(0.01, round(first_volume, 2))
    second_volume = max(0.01, round(second_volume, 2))
    first_loss = first_atr * first_volume * DOLLARS_PER_POINT_PER_LOT
    second_loss = second_atr * second_volume * DOLLARS_PER_POINT_PER_LOT
    planned = first_loss + second_loss
    smaller = min(first_loss, second_loss)
    ratio = max(first_loss, second_loss) / smaller if smaller > 0 else math.inf
    if planned > balance * 0.04 + EPS or ratio > 2.5 + EPS:
        return None
    return PairVolume(
        first_volume=first_volume,
        second_volume=second_volume,
        first_planned_loss=first_loss,
        second_planned_loss=second_loss,
        planned_basket_loss=planned,
        leg_risk_ratio=ratio,
    )


@dataclass(frozen=True)
class PairState:
    pair_index: int
    first_symbol: str
    second_symbol: str
    alpha: float
    beta: float
    r_squared: float
    residual_mean: float
    residual_std: float
    residual_z: float


def calculate_pair_states(
    frame: pd.DataFrame, indices: np.ndarray
) -> tuple[dict[int, PairState], list[dict[str, Any]], dict[str, int]]:
    log_close = {
        symbol: np.log(frame[f"{symbol}_close"].to_numpy(dtype=np.float64))
        for symbol in SYMBOLS
    }
    selected_by_index: dict[int, PairState] = {}
    records: list[dict[str, Any]] = []
    valid_counts = {f"{first}_{second}": 0 for first, second in PAIRS}
    for index in indices:
        valid_states: list[PairState] = []
        for pair_index, (first, second) in enumerate(PAIRS):
            first_values = log_close[first][index - 960 : index]
            second_values = log_close[second][index - 960 : index]
            first_mean = float(first_values.mean())
            second_mean = float(second_values.mean())
            centered_first = first_values - first_mean
            centered_second = second_values - second_mean
            variance_second = float(np.mean(centered_second * centered_second))
            valid = variance_second > 0
            alpha: float | None = None
            beta: float | None = None
            r_squared: float | None = None
            residual_mean: float | None = None
            residual_std: float | None = None
            residual_z: float | None = None
            if valid:
                beta = float(np.mean(centered_first * centered_second) / variance_second)
                alpha = first_mean - beta * second_mean
                fitted_residuals = first_values - (alpha + beta * second_values)
                total_sum_squares = float(np.sum(centered_first * centered_first))
                residual_sum_squares = float(np.sum(fitted_residuals * fitted_residuals))
                r_squared = (
                    1.0 - residual_sum_squares / total_sum_squares
                    if total_sum_squares > 0
                    else -math.inf
                )
                tail = fitted_residuals[-96:]
                residual_mean = float(tail.mean())
                residual_std = float(tail.std(ddof=0))
                residual_z = (
                    float((fitted_residuals[-1] - residual_mean) / residual_std)
                    if residual_std > 0.000001
                    else None
                )
                valid = bool(
                    np.isfinite(beta)
                    and 0.5 <= beta <= 1.5
                    and np.isfinite(r_squared)
                    and r_squared >= 0.7
                    and residual_z is not None
                    and np.isfinite(residual_z)
                )
            record = {
                "decision_epoch": int(frame.at[index, "time_epoch"]),
                "decision_time": pd.Timestamp(frame.at[index, "time"]).isoformat(),
                "pair": f"{first}_{second}",
                "valid": valid,
                "alpha": alpha,
                "beta": beta,
                "r_squared": r_squared,
                "residual_mean": residual_mean,
                "residual_std": residual_std,
                "residual_z": residual_z,
            }
            records.append(record)
            if valid:
                state = PairState(
                    pair_index=pair_index,
                    first_symbol=first,
                    second_symbol=second,
                    alpha=float(alpha),
                    beta=float(beta),
                    r_squared=float(r_squared),
                    residual_mean=float(residual_mean),
                    residual_std=float(residual_std),
                    residual_z=float(residual_z),
                )
                valid_states.append(state)
                valid_counts[f"{first}_{second}"] += 1
        if valid_states:
            valid_states.sort(key=lambda state: (-abs(state.residual_z), state.pair_index))
            selected_by_index[int(index)] = valid_states[0]
    return selected_by_index, records, valid_counts


def direction_entry(
    frame: pd.DataFrame, symbol: str, index: int, direction: int
) -> tuple[float, float]:
    bid_open = float(frame.at[index, f"{symbol}_open"])
    spread_price = float(frame.at[index, f"{symbol}_spread"]) * TICK_SIZE
    entry = bid_open + spread_price if direction == 1 else bid_open
    return entry, spread_price


def leg_pnl(
    entry: float,
    bid_exit: float,
    spread_price: float,
    volume: float,
    direction: int,
) -> float:
    if direction == 1:
        price_move = bid_exit - entry
    else:
        price_move = entry - (bid_exit + spread_price)
    return price_move * volume * DOLLARS_PER_POINT_PER_LOT


def basket_path(
    frame: pd.DataFrame,
    index: int,
    state: PairState,
    volume: PairVolume,
) -> dict[str, Any]:
    if state.residual_z > 0:
        first_direction, second_direction = -1, 1
    else:
        first_direction, second_direction = 1, -1
    first_entry, first_decision_spread = direction_entry(
        frame, state.first_symbol, index, first_direction
    )
    second_entry, second_decision_spread = direction_entry(
        frame, state.second_symbol, index, second_direction
    )
    extra_stress_cost = (
        first_decision_spread * volume.first_volume
        + second_decision_spread * volume.second_volume
    ) * DOLLARS_PER_POINT_PER_LOT
    exit_index = index + 2
    exit_reason = "TIME"
    actual_pnl = 0.0
    exit_residual: float | None = None
    for future in range(index, index + 3):
        first_spread = float(frame.at[future, f"{state.first_symbol}_spread"]) * TICK_SIZE
        second_spread = (
            float(frame.at[future, f"{state.second_symbol}_spread"]) * TICK_SIZE
        )
        first_worst_bid = float(
            frame.at[
                future,
                f"{state.first_symbol}_{'low' if first_direction == 1 else 'high'}",
            ]
        )
        second_worst_bid = float(
            frame.at[
                future,
                f"{state.second_symbol}_{'low' if second_direction == 1 else 'high'}",
            ]
        )
        first_best_bid = float(
            frame.at[
                future,
                f"{state.first_symbol}_{'high' if first_direction == 1 else 'low'}",
            ]
        )
        second_best_bid = float(
            frame.at[
                future,
                f"{state.second_symbol}_{'high' if second_direction == 1 else 'low'}",
            ]
        )
        worst_pnl = leg_pnl(
            first_entry,
            first_worst_bid,
            first_spread,
            volume.first_volume,
            first_direction,
        ) + leg_pnl(
            second_entry,
            second_worst_bid,
            second_spread,
            volume.second_volume,
            second_direction,
        )
        best_pnl = leg_pnl(
            first_entry,
            first_best_bid,
            first_spread,
            volume.first_volume,
            first_direction,
        ) + leg_pnl(
            second_entry,
            second_best_bid,
            second_spread,
            volume.second_volume,
            second_direction,
        )
        if worst_pnl <= -volume.planned_basket_loss:
            exit_index = future
            exit_reason = "STOP"
            actual_pnl = -volume.planned_basket_loss
            break
        if best_pnl >= 1.5 * volume.planned_basket_loss:
            exit_index = future
            exit_reason = "TAKE"
            actual_pnl = 1.5 * volume.planned_basket_loss
            break
        first_close = float(frame.at[future, f"{state.first_symbol}_close"])
        second_close = float(frame.at[future, f"{state.second_symbol}_close"])
        actual_pnl = leg_pnl(
            first_entry,
            first_close,
            first_spread,
            volume.first_volume,
            first_direction,
        ) + leg_pnl(
            second_entry,
            second_close,
            second_spread,
            volume.second_volume,
            second_direction,
        )
        exit_residual = math.log(first_close) - (
            state.alpha + state.beta * math.log(second_close)
        )
        converged = (
            state.residual_z > 0 and exit_residual <= state.residual_mean
        ) or (state.residual_z < 0 and exit_residual >= state.residual_mean)
        if converged:
            exit_index = future
            exit_reason = "CONVERGENCE"
            break
        if future == index + 2:
            exit_index = future
            exit_reason = "TIME"
            break
    return {
        "first_direction": "LONG" if first_direction == 1 else "SHORT",
        "second_direction": "LONG" if second_direction == 1 else "SHORT",
        "first_entry": first_entry,
        "second_entry": second_entry,
        "exit_index": exit_index,
        "exit_reason": exit_reason,
        "exit_residual": exit_residual,
        "actual_pnl": actual_pnl,
        "stressed_pnl": actual_pnl - extra_stress_cost,
        "extra_stress_cost": extra_stress_cost,
    }


def simulate_role(
    frame: pd.DataFrame,
    atr: dict[str, np.ndarray],
    states: dict[int, PairState],
    role: dict[str, Any],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    threshold = float(role["minimum_absolute_residual_z"])
    actual_balance = 100.0
    stressed_balance = 100.0
    actual_peak = 100.0
    stressed_peak = 100.0
    max_actual_dd_usd = 0.0
    max_actual_dd_pct = 0.0
    max_stressed_dd_usd = 0.0
    max_stressed_dd_pct = 0.0
    minimum_actual_balance = 100.0
    minimum_stressed_balance = 100.0
    next_available = 0
    trades: list[dict[str, Any]] = []
    yearly = {
        2024: {"actual": 0.0, "stressed": 0.0, "starts": 0},
        2025: {"actual": 0.0, "stressed": 0.0, "starts": 0},
        2026: {"actual": 0.0, "stressed": 0.0, "starts": 0},
    }
    for index in sorted(states):
        timestamp = pd.Timestamp(frame.at[index, "time"])
        if timestamp < start or timestamp >= end or index < next_available:
            continue
        state = states[index]
        if abs(state.residual_z) + EPS < threshold:
            continue
        first_atr = float(atr[state.first_symbol][index - 1])
        second_atr = float(atr[state.second_symbol][index - 1])
        volume = pair_volume(actual_balance, first_atr, second_atr)
        if volume is None:
            continue
        path = basket_path(frame, index, state, volume)
        actual_balance += float(path["actual_pnl"])
        stressed_balance += float(path["stressed_pnl"])
        actual_peak = max(actual_peak, actual_balance)
        stressed_peak = max(stressed_peak, stressed_balance)
        actual_dd = actual_peak - actual_balance
        stressed_dd = stressed_peak - stressed_balance
        max_actual_dd_usd = max(max_actual_dd_usd, actual_dd)
        max_stressed_dd_usd = max(max_stressed_dd_usd, stressed_dd)
        max_actual_dd_pct = max(
            max_actual_dd_pct,
            100.0 * actual_dd / actual_peak if actual_peak > 0 else math.inf,
        )
        max_stressed_dd_pct = max(
            max_stressed_dd_pct,
            100.0 * stressed_dd / stressed_peak if stressed_peak > 0 else math.inf,
        )
        minimum_actual_balance = min(minimum_actual_balance, actual_balance)
        minimum_stressed_balance = min(minimum_stressed_balance, stressed_balance)
        exit_index = int(path["exit_index"])
        next_available = exit_index + 1
        if timestamp.year in yearly:
            yearly[timestamp.year]["actual"] += float(path["actual_pnl"])
            yearly[timestamp.year]["stressed"] += float(path["stressed_pnl"])
            yearly[timestamp.year]["starts"] += 1
        trade = {
            "role": role["role"],
            "decision_epoch": int(frame.at[index, "time_epoch"]),
            "decision_time": timestamp.isoformat(),
            "exit_epoch": int(frame.at[exit_index, "time_epoch"]),
            "exit_time": pd.Timestamp(frame.at[exit_index, "time"]).isoformat(),
            "pair": f"{state.first_symbol}_{state.second_symbol}",
            "residual_z": state.residual_z,
            "alpha": state.alpha,
            "beta": state.beta,
            "r_squared": state.r_squared,
            "residual_mean": state.residual_mean,
            "residual_std": state.residual_std,
            "first_symbol": state.first_symbol,
            "first_direction": path["first_direction"],
            "first_volume": volume.first_volume,
            "first_atr": first_atr,
            "first_planned_loss": volume.first_planned_loss,
            "second_symbol": state.second_symbol,
            "second_direction": path["second_direction"],
            "second_volume": volume.second_volume,
            "second_atr": second_atr,
            "second_planned_loss": volume.second_planned_loss,
            "planned_basket_loss": volume.planned_basket_loss,
            "leg_risk_ratio": volume.leg_risk_ratio,
            "exit_reason": path["exit_reason"],
            "hold_common_h1_bars": exit_index - index + 1,
            "actual_pnl": path["actual_pnl"],
            "stressed_pnl": path["stressed_pnl"],
            "extra_stress_cost": path["extra_stress_cost"],
            "actual_balance_after": actual_balance,
            "stressed_balance_after": stressed_balance,
        }
        trades.append(trade)
    day_count = normal_trading_days(frame, start, end)
    actual_net = actual_balance - 100.0
    stressed_net = stressed_balance - 100.0
    metrics = {
        "role": role["role"],
        "period_start": start.isoformat(),
        "period_end_exclusive": end.isoformat(),
        "basket_starts": len(trades),
        "normal_trading_days": day_count,
        "average_basket_starts_per_normal_trading_day": len(trades) / day_count,
        "actual_net_usd": actual_net,
        "stressed_net_usd": stressed_net,
        "ending_actual_balance_usd": actual_balance,
        "ending_stressed_balance_usd": stressed_balance,
        "actual_closed_balance_drawdown_usd": max_actual_dd_usd,
        "actual_closed_balance_drawdown_pct": max_actual_dd_pct,
        "stressed_closed_balance_drawdown_usd": max_stressed_dd_usd,
        "stressed_closed_balance_drawdown_pct": max_stressed_dd_pct,
        "minimum_actual_balance_usd": minimum_actual_balance,
        "minimum_stressed_balance_usd": minimum_stressed_balance,
        "robust_recovery": stressed_net / max_actual_dd_usd
        if max_actual_dd_usd > 0
        else None,
        "yearly": {str(year): values for year, values in yearly.items()},
        "pair_starts": {
            f"{first}_{second}": sum(
                1 for trade in trades if trade["pair"] == f"{first}_{second}"
            )
            for first, second in PAIRS
        },
        "pair_breadth": sum(
            1
            for first, second in PAIRS
            if any(trade["pair"] == f"{first}_{second}" for trade in trades)
        ),
        "exit_reasons": {
            reason: sum(1 for trade in trades if trade["exit_reason"] == reason)
            for reason in ("STOP", "TAKE", "CONVERGENCE", "TIME")
        },
    }
    return metrics, trades


def complete_development_pass(metrics: dict[str, Any]) -> bool:
    return bool(
        metrics["actual_net_usd"] > 149.97
        and metrics["stressed_net_usd"] > 127.786
        and metrics["actual_closed_balance_drawdown_pct"] <= 37.39
        and metrics["average_basket_starts_per_normal_trading_day"] >= 3.0
        and metrics["pair_breadth"] >= 2
        and metrics["yearly"]["2024"]["actual"] > 0
        and metrics["yearly"]["2024"]["stressed"] > 0
        and metrics["yearly"]["2025"]["actual"] > 0
        and metrics["yearly"]["2025"]["stressed"] > 0
    )


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    materialized = list(rows)
    if not materialized:
        path.write_text("", encoding="utf-8")
        return 0
    fieldnames: list[str] = []
    for row in materialized:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(materialized)
    return len(materialized)


def staging_directory(final_name: str) -> tuple[Path, Path]:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    final = ARTIFACT_ROOT / final_name
    if final.exists():
        raise RuntimeError(f"authoritative output already exists: {final}")
    temporary = Path(tempfile.mkdtemp(prefix=f".{final_name}-", dir=ARTIFACT_ROOT))
    return temporary, final


def finish_staging(temporary: Path, final: Path) -> None:
    os.replace(temporary, final)


def precheck(contract: dict[str, Any]) -> dict[str, Any]:
    start_text, end_text = contract["periods"]["development_selection"].split("/")
    start = pd.Timestamp(start_text)
    end = pd.Timestamp(end_text)
    frame = load_common_frame(end)
    atr = build_atr(frame)
    indices = structural_indices(frame, atr, start, end)
    feasible_counts = {f"{first}_{second}": 0 for first, second in PAIRS}
    any_pair_count = 0
    for index in indices:
        feasible_here = False
        for first, second in PAIRS:
            candidate = pair_volume(
                100.0, float(atr[first][index - 1]), float(atr[second][index - 1])
            )
            if candidate is not None:
                feasible_counts[f"{first}_{second}"] += 1
                feasible_here = True
        if feasible_here:
            any_pair_count += 1
    if any_pair_count == 0 or sum(value > 0 for value in feasible_counts.values()) < 2:
        raise RuntimeError("structural pair or pair-breadth density is absent")
    return {
        "status": "STRUCTURAL_PRECHECK_PASS_NO_PAIR_FIT_NO_RESIDUAL_NO_DECISION_NO_OUTCOME",
        "common_rows": len(frame),
        "first_common_time": pd.Timestamp(frame.iloc[0]["time"]).isoformat(),
        "last_common_time": pd.Timestamp(frame.iloc[-1]["time"]).isoformat(),
        "development_structural_decision_rows": len(indices),
        "development_normal_trading_days": normal_trading_days(frame, start, end),
        "fixed_100_usd_pair_volume_feasible_rows": feasible_counts,
        "fixed_100_usd_any_pair_volume_feasible_rows": any_pair_count,
        "pair_fit_rows": 0,
        "residual_rows": 0,
        "candidate_decisions": 0,
        "candidate_baskets": 0,
        "candidate_economic_metrics": 0,
        "locked_confirmation_opened": False,
        "versions": {
            "python": os.sys.version.split()[0],
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
    }


def development(contract: dict[str, Any]) -> dict[str, Any]:
    start_text, end_text = contract["periods"]["development_selection"].split("/")
    start = pd.Timestamp(start_text)
    end = pd.Timestamp(end_text)
    frame = load_common_frame(end)
    atr = build_atr(frame)
    indices = structural_indices(frame, atr, start, end)
    states, state_rows, valid_pair_counts = calculate_pair_states(frame, indices)
    temporary, final = staging_directory("development")
    try:
        role_results: list[dict[str, Any]] = []
        all_trades: list[dict[str, Any]] = []
        for role in contract["candidate_bundle"]["roles"]:
            metrics, trades = simulate_role(frame, atr, states, role, start, end)
            metrics["complete_development_pass"] = complete_development_pass(metrics)
            role_results.append(metrics)
            all_trades.extend(trades)
        passers = [item for item in role_results if item["complete_development_pass"]]
        passers.sort(
            key=lambda item: (
                -item["stressed_net_usd"],
                item["actual_closed_balance_drawdown_pct"],
                -min(
                    item["yearly"]["2024"]["stressed"],
                    item["yearly"]["2025"]["stressed"],
                ),
            )
        )
        selected_role = passers[0]["role"] if passers else None
        state_path = temporary / "pair-state-tape.csv"
        state_count = write_csv(state_path, state_rows)
        basket_path_output = temporary / "basket-tape.csv"
        basket_count = write_csv(basket_path_output, all_trades)
        result = {
            "schema": "zeta-next-independent-cross-index-residual-basket-development-result-v1",
            "status": (
                "VALID_DEVELOPMENT_PROXY_SURVIVOR_LOCKED_CONFIRMATION_REQUIRED"
                if selected_role
                else "VALID_DEVELOPMENT_NO_COMPLETE_ROLE_CLOSE_BEFORE_CONFIRMATION_EA_MT5"
            ),
            "family": project_relative(FAMILY_ROOT) + "/",
            "period": f"{start.isoformat()}/{end.isoformat()}",
            "authority": {
                "contract_sha256": sha256_file(CONTRACT_PATH),
                "declaration_sha256": sha256_file(DECLARATION_PATH),
                "implementation_freeze_sha256": sha256_file(FREEZE_PATH),
                "adapter_sha256": sha256_file(Path(__file__)),
            },
            "process": {
                "structural_decision_rows": len(indices),
                "selected_valid_pair_state_rows": len(states),
                "all_pair_state_rows": len(state_rows),
                "valid_pair_counts": valid_pair_counts,
            },
            "roles": role_results,
            "complete_pass_count": len(passers),
            "selected_role": selected_role,
            "locked_confirmation_opened": False,
            "ea_source_files": 0,
            "mt5_paths": 0,
            "live_changed": False,
            "artifacts": {
                "pair_state_tape": {
                    "path": "pair-state-tape.csv",
                    "bytes": state_path.stat().st_size,
                    "sha256": sha256_file(state_path),
                    "rows": state_count,
                },
                "basket_tape": {
                    "path": "basket-tape.csv",
                    "bytes": basket_path_output.stat().st_size,
                    "sha256": sha256_file(basket_path_output),
                    "rows": basket_count,
                },
            },
        }
        write_json(temporary / "development-result.json", result)
        finish_staging(temporary, final)
        return result
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def confirmation(contract: dict[str, Any]) -> dict[str, Any]:
    development_result_path = ARTIFACT_ROOT / "development" / "development-result.json"
    if not development_result_path.is_file():
        raise RuntimeError("development result is absent")
    development_result = load_json(development_result_path)
    selected_role_name = development_result.get("selected_role")
    if (
        development_result.get("status")
        != "VALID_DEVELOPMENT_PROXY_SURVIVOR_LOCKED_CONFIRMATION_REQUIRED"
        or not selected_role_name
        or int(development_result.get("complete_pass_count", 0)) < 1
    ):
        raise RuntimeError("development did not authorize locked confirmation")
    confirmation_start_text, confirmation_end_text = contract["periods"][
        "locked_confirmation"
    ].split("/")
    confirmation_start = pd.Timestamp(confirmation_start_text)
    confirmation_end = pd.Timestamp(confirmation_end_text)
    whole_start = pd.Timestamp(contract["periods"]["whole_v8_comparison"].split("/")[0])
    frame = load_common_frame(confirmation_end)
    atr = build_atr(frame)
    indices = structural_indices(frame, atr, whole_start, confirmation_end)
    states, state_rows, valid_pair_counts = calculate_pair_states(frame, indices)
    role = next(
        item
        for item in contract["candidate_bundle"]["roles"]
        if item["role"] == selected_role_name
    )
    whole_metrics, whole_trades = simulate_role(
        frame, atr, states, role, whole_start, confirmation_end
    )
    development_metrics = next(
        item
        for item in development_result["roles"]
        if item["role"] == selected_role_name
    )
    development_trades = [
        trade
        for trade in whole_trades
        if pd.Timestamp(trade["decision_time"]) < confirmation_start
    ]
    if not math.isclose(
        sum(float(trade["actual_pnl"]) for trade in development_trades),
        float(development_metrics["actual_net_usd"]),
        abs_tol=1e-8,
    ) or not math.isclose(
        sum(float(trade["stressed_pnl"]) for trade in development_trades),
        float(development_metrics["stressed_net_usd"]),
        abs_tol=1e-8,
    ):
        raise RuntimeError("development economics did not reproduce in whole replay")
    confirmation_trades = [
        trade
        for trade in whole_trades
        if pd.Timestamp(trade["decision_time"]) >= confirmation_start
    ]
    confirmation_actual = sum(float(trade["actual_pnl"]) for trade in confirmation_trades)
    confirmation_stressed = sum(
        float(trade["stressed_pnl"]) for trade in confirmation_trades
    )
    confirmation_days = normal_trading_days(frame, confirmation_start, confirmation_end)
    robust_recovery = whole_metrics["robust_recovery"]
    whole_pass = bool(
        confirmation_actual > 0
        and confirmation_stressed > 0
        and len(confirmation_trades) / confirmation_days >= 3.0
        and whole_metrics["actual_net_usd"] > 409.81
        and whole_metrics["stressed_net_usd"] > 367.818
        and whole_metrics["actual_closed_balance_drawdown_pct"] <= 37.39
        and robust_recovery is not None
        and robust_recovery > 3.295860215
        and all(
            whole_metrics["yearly"][str(year)][book] > 0
            for year in (2024, 2025, 2026)
            for book in ("actual", "stressed")
        )
    )
    temporary, final = staging_directory("confirmation")
    try:
        state_path = temporary / "whole-pair-state-tape.csv"
        state_count = write_csv(state_path, state_rows)
        basket_path_output = temporary / "whole-basket-tape.csv"
        basket_count = write_csv(basket_path_output, whole_trades)
        result = {
            "schema": "zeta-next-independent-cross-index-residual-basket-confirmation-result-v1",
            "status": (
                "VALID_WHOLE_PROXY_SURVIVOR_EA_AND_NATIVE_CHALLENGE_REQUIRED"
                if whole_pass
                else "VALID_LOCKED_CONFIRMATION_OR_WHOLE_PROXY_NONCONFIRMATION_CLOSE_BEFORE_EA_MT5"
            ),
            "selected_role": selected_role_name,
            "confirmation": {
                "period": f"{confirmation_start.isoformat()}/{confirmation_end.isoformat()}",
                "basket_starts": len(confirmation_trades),
                "normal_trading_days": confirmation_days,
                "average_basket_starts_per_normal_trading_day": len(
                    confirmation_trades
                )
                / confirmation_days,
                "actual_net_usd": confirmation_actual,
                "stressed_net_usd": confirmation_stressed,
            },
            "whole": whole_metrics,
            "whole_proxy_pass": whole_pass,
            "valid_pair_counts": valid_pair_counts,
            "ea_required_before_victory": whole_pass,
            "proxy_victory_claimed": False,
            "mt5_paths": 0,
            "live_changed": False,
            "artifacts": {
                "pair_state_tape": {
                    "path": "whole-pair-state-tape.csv",
                    "bytes": state_path.stat().st_size,
                    "sha256": sha256_file(state_path),
                    "rows": state_count,
                },
                "basket_tape": {
                    "path": "whole-basket-tape.csv",
                    "bytes": basket_path_output.stat().st_size,
                    "sha256": sha256_file(basket_path_output),
                    "rows": basket_count,
                },
            },
        }
        write_json(temporary / "confirmation-result.json", result)
        finish_staging(temporary, final)
        return result
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("precheck", "development", "confirmation"))
    arguments = parser.parse_args()
    contract, _ = verify_authorities(arguments.mode)
    if arguments.mode == "precheck":
        result = precheck(contract)
    elif arguments.mode == "development":
        result = development(contract)
    else:
        result = confirmation(contract)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=json_default, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
