#!/usr/bin/env python3
"""Causal Python decision adapter for Independent V8 Challenge Family 001.

The adapter has three normal modes:

* precheck: validate pinned inputs and causal feature/schedule structure without
  fitting a model or calculating a candidate economic outcome.
* development: fit the frozen monthly models and evaluate only 2024-2025.
* confirmation: require a pinned development result and evaluate its sole
  unchanged survivor through the locked 2026 January-July interval.

It never connects to MetaTrader, a broker account, Live state, or another
family. A separately owned EA is mandatory before any native Challenge claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor


FAMILY_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = FAMILY_ROOT.parents[2]
CONTRACT_PATH = FAMILY_ROOT / "config" / "challenge-contract.json"
INPUT_ROOT = FAMILY_ROOT / "data" / "input"
DEFAULT_ARTIFACT_ROOT = (
    REPOSITORY_ROOT
    / "lab"
    / "artifacts"
    / "independent-cross-index-hourly-adapter-challenge-v1"
)

SYMBOLS = ("US100", "US30", "US500")
ROLES = {
    "BREADTH_Q80": 0.80,
    "BALANCED_Q85": 0.85,
    "SELECTIVE_Q90": 0.90,
}
POINT = 0.01
VOLUME_MIN = 0.01
VOLUME_STEP = 0.01
EPSILON = 1.0e-12


class AdapterError(RuntimeError):
    """A deterministic contract, input, or execution error."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def source_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def load_contract() -> dict[str, Any]:
    with CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        contract = json.load(handle)
    expected_schema = (
        "zeta-next-independent-cross-index-hourly-adapter-challenge-v1-contract"
    )
    if contract.get("schema") != expected_schema:
        raise AdapterError(f"unexpected contract schema: {contract.get('schema')}")
    if contract["candidate_bundle"]["roles"] != [
        {"role": name, "minimum_absolute_score": f"monthly causal calibration q{int(q * 100)}"}
        for name, q in ROLES.items()
    ]:
        raise AdapterError("candidate role order or quantile differs from frozen contract")
    return contract


def expected_input_path(contract: dict[str, Any], symbol: str) -> Path:
    source_name = Path(
        contract["source_inputs"]["symbols"][symbol]["source_path"]
    ).name
    return INPUT_ROOT / source_name


def verify_input_files(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for symbol in SYMBOLS:
        expected = contract["source_inputs"]["symbols"][symbol]
        path = expected_input_path(contract, symbol)
        if not path.is_file():
            raise AdapterError(f"missing materialized input for {symbol}: {path}")
        actual = {
            "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        if actual["bytes"] != expected["bytes"]:
            raise AdapterError(
                f"{symbol} byte mismatch: {actual['bytes']} != {expected['bytes']}"
            )
        if actual["sha256"] != expected["sha256"]:
            raise AdapterError(
                f"{symbol} hash mismatch: {actual['sha256']} != {expected['sha256']}"
            )
        records[symbol] = actual
    return records


def load_aligned_bars(
    contract: dict[str, Any], cutoff_exclusive: pd.Timestamp
) -> tuple[pd.DataFrame, dict[str, int]]:
    frames: list[pd.DataFrame] = []
    source_rows: dict[str, int] = {}
    required = contract["source_inputs"]["required_columns"]

    for symbol in SYMBOLS:
        path = expected_input_path(contract, symbol)
        frame = pd.read_csv(path)
        source_rows[symbol] = int(len(frame))
        if list(frame.columns) != required:
            raise AdapterError(
                f"{symbol} columns differ from frozen contract: {list(frame.columns)}"
            )
        if frame["time_epoch"].duplicated().any():
            raise AdapterError(f"{symbol} contains duplicate time_epoch values")
        if not frame["time_epoch"].is_monotonic_increasing:
            raise AdapterError(f"{symbol} time_epoch is not strictly ordered")
        parsed_server = pd.to_datetime(
            frame["time_server"], format="%Y.%m.%d %H:%M:%S", errors="raise"
        )
        frame = frame.assign(time_server_parsed=parsed_server)
        renamed = {
            column: f"{symbol}_{column}"
            for column in required
            if column not in {"time_epoch", "time_server"}
        }
        keep = ["time_epoch", "time_server_parsed"] + list(renamed.values())
        frame = frame.rename(columns=renamed)[keep]
        frame = frame.rename(
            columns={"time_server_parsed": f"{symbol}_time_server"}
        )
        frames.append(frame)

    merged = frames[0]
    for frame in frames[1:]:
        merged = merged.merge(frame, on="time_epoch", how="inner", validate="one_to_one")
    merged = merged.sort_values("time_epoch").reset_index(drop=True)
    if merged.empty:
        raise AdapterError("three-symbol inner join is empty")

    reference_time = merged["US100_time_server"]
    for symbol in SYMBOLS[1:]:
        mismatch = reference_time != merged[f"{symbol}_time_server"]
        if bool(mismatch.any()):
            first = int(np.flatnonzero(mismatch.to_numpy())[0])
            raise AdapterError(
                f"server-time mismatch at joined row {first}: US100 vs {symbol}"
            )
    merged.insert(1, "time_server", reference_time)
    merged = merged.drop(columns=[f"{symbol}_time_server" for symbol in SYMBOLS])
    merged = merged.loc[merged["time_server"] < cutoff_exclusive].copy()
    merged = merged.set_index("time_server", drop=False)
    if merged.index.has_duplicates or not merged.index.is_monotonic_increasing:
        raise AdapterError("joined server-time index is not unique and ordered")
    return merged, source_rows


def build_feature_frame(
    bars: pd.DataFrame, include_targets: bool
) -> tuple[pd.DataFrame, list[str]]:
    data = bars.copy()
    feature_columns: list[str] = []
    completed_returns_1: dict[str, pd.Series] = {}
    completed_returns_4: dict[str, pd.Series] = {}

    for symbol in SYMBOLS:
        open_price = data[f"{symbol}_open"].astype(float)
        high = data[f"{symbol}_high"].astype(float)
        low = data[f"{symbol}_low"].astype(float)
        close = data[f"{symbol}_close"].astype(float)
        tick_volume = data[f"{symbol}_tick_volume"].astype(float)
        spread_price = data[f"{symbol}_spread"].astype(float) * POINT

        previous_close = close.shift(1)
        true_range = pd.concat(
            [
                high - low,
                (high - previous_close).abs(),
                (low - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr24 = true_range.rolling(24, min_periods=24).mean()
        return_1 = np.log(close / close.shift(1))
        return_2 = np.log(close / close.shift(2))
        return_4 = np.log(close / close.shift(4))
        return_8 = np.log(close / close.shift(8))
        return_24 = np.log(close / close.shift(24))
        range_price = high - low
        close_location = pd.Series(
            np.where(
                range_price.abs() > EPSILON,
                (2.0 * close - high - low) / range_price,
                0.0,
            ),
            index=data.index,
        )
        log_volume = np.log1p(tick_volume)
        volume_mean = log_volume.rolling(24, min_periods=24).mean()
        volume_std = log_volume.rolling(24, min_periods=24).std(ddof=0)

        completed = {
            "ret_1": return_1,
            "ret_2": return_2,
            "ret_4": return_4,
            "ret_8": return_8,
            "ret_24": return_24,
            "body_atr": (close - open_price) / atr24,
            "range_atr": range_price / atr24,
            "close_location": close_location,
            "vol_6": return_1.rolling(6, min_periods=6).std(ddof=0),
            "vol_24": return_1.rolling(24, min_periods=24).std(ddof=0),
            "atr_relative": atr24 / close,
            "volume_z_24": (log_volume - volume_mean) / volume_std,
            "spread_atr": spread_price / atr24,
        }
        for name, values in completed.items():
            feature_name = f"feature_{symbol}_{name}"
            data[feature_name] = values.shift(1)
            feature_columns.append(feature_name)

        completed_returns_1[symbol] = return_1.shift(1)
        completed_returns_4[symbol] = return_4.shift(1)
        data[f"available_{symbol}_atr24"] = atr24.shift(1)
        data[f"available_{symbol}_spread_price"] = spread_price
        data[f"next_{symbol}_open"] = open_price.shift(-1)
        data[f"next_{symbol}_spread_price"] = spread_price.shift(-1)

        if include_targets:
            data[f"target_{symbol}"] = (
                open_price.shift(-1) - open_price
            ) / atr24.shift(1)

    return_1_frame = pd.DataFrame(completed_returns_1)
    return_4_frame = pd.DataFrame(completed_returns_4)
    data["feature_cross_dispersion_ret_1"] = return_1_frame.std(axis=1, ddof=0)
    data["feature_cross_dispersion_ret_4"] = return_4_frame.std(axis=1, ddof=0)
    feature_columns.extend(
        ["feature_cross_dispersion_ret_1", "feature_cross_dispersion_ret_4"]
    )
    for symbol in SYMBOLS:
        name_1 = f"feature_{symbol}_residual_ret_1"
        name_4 = f"feature_{symbol}_residual_ret_4"
        data[name_1] = return_1_frame[symbol] - return_1_frame.mean(axis=1)
        data[name_4] = return_4_frame[symbol] - return_4_frame.mean(axis=1)
        feature_columns.extend([name_1, name_4])

    hour = data["time_server"].dt.hour.astype(float)
    weekday = data["time_server"].dt.weekday.astype(float)
    data["feature_calendar_hour_sin"] = np.sin(2.0 * np.pi * hour / 24.0)
    data["feature_calendar_hour_cos"] = np.cos(2.0 * np.pi * hour / 24.0)
    data["feature_calendar_weekday_sin"] = np.sin(2.0 * np.pi * weekday / 7.0)
    data["feature_calendar_weekday_cos"] = np.cos(2.0 * np.pi * weekday / 7.0)
    feature_columns.extend(
        [
            "feature_calendar_hour_sin",
            "feature_calendar_hour_cos",
            "feature_calendar_weekday_sin",
            "feature_calendar_weekday_cos",
        ]
    )

    data[feature_columns] = data[feature_columns].replace([np.inf, -np.inf], np.nan)
    return data, feature_columns


def month_starts(start: pd.Timestamp, end_exclusive: pd.Timestamp) -> list[pd.Timestamp]:
    return list(pd.date_range(start=start, end=end_exclusive, freq="MS", inclusive="left"))


def complete_feature_mask(frame: pd.DataFrame, feature_columns: list[str]) -> pd.Series:
    return frame[feature_columns].notna().all(axis=1)


def run_precheck(contract: dict[str, Any]) -> dict[str, Any]:
    inputs = verify_input_files(contract)
    development_end = pd.Timestamp(contract["periods"]["development_selection"].split("/")[1])
    bars, source_rows = load_aligned_bars(contract, development_end)
    frame, feature_columns = build_feature_frame(bars, include_targets=False)
    finite = complete_feature_mask(frame, feature_columns)
    development_start = pd.Timestamp(
        contract["periods"]["development_selection"].split("/")[0]
    )

    schedules: list[dict[str, Any]] = []
    for month in month_starts(development_start, development_end):
        lookback = month - pd.DateOffset(months=contract["model"]["lookback_calendar_months"])
        training_rows = int((finite & (frame.index >= lookback) & (frame.index < month)).sum())
        decision_rows = int(
            (
                finite
                & (frame.index >= month)
                & (frame.index < month + pd.DateOffset(months=1))
            ).sum()
        )
        schedules.append(
            {
                "month": month.strftime("%Y-%m"),
                "training_feature_rows": training_rows,
                "decision_feature_rows": decision_rows,
            }
        )
    if min(item["training_feature_rows"] for item in schedules) < contract["model"]["minimum_training_rows"]:
        raise AdapterError("at least one development month lacks frozen minimum training rows")
    if any(item["decision_feature_rows"] <= 0 for item in schedules):
        raise AdapterError("at least one development month has no complete decision feature row")

    return {
        "schema": "zeta-next-independent-cross-index-hourly-adapter-challenge-v1-precheck",
        "status": "STRUCTURAL_PRECHECK_PASSED_NO_MODEL_FIT_NO_CANDIDATE_OUTCOME",
        "contract": source_record(CONTRACT_PATH),
        "adapter": source_record(Path(__file__).resolve()),
        "inputs": inputs,
        "source_rows": source_rows,
        "joined_rows_before_2026": int(len(frame)),
        "joined_first_server_time": frame.index.min().isoformat(),
        "joined_last_server_time": frame.index.max().isoformat(),
        "feature_count": len(feature_columns),
        "complete_feature_rows": int(finite.sum()),
        "development_complete_feature_rows": int(
            (finite & (frame.index >= development_start) & (frame.index < development_end)).sum()
        ),
        "development_months": len(schedules),
        "minimum_monthly_training_feature_rows": min(
            item["training_feature_rows"] for item in schedules
        ),
        "minimum_monthly_decision_feature_rows": min(
            item["decision_feature_rows"] for item in schedules
        ),
        "schedule": schedules,
        "model_fits": 0,
        "candidate_metric_rows": 0,
        "locked_confirmation_opened": False,
        "mt5_paths": 0,
    }


def make_model(contract: dict[str, Any]) -> HistGradientBoostingRegressor:
    params = contract["model"]["hyperparameters"]
    return HistGradientBoostingRegressor(
        loss=params["loss"],
        learning_rate=params["learning_rate"],
        max_iter=params["max_iter"],
        max_leaf_nodes=params["max_leaf_nodes"],
        min_samples_leaf=params["min_samples_leaf"],
        l2_regularization=params["l2_regularization"],
        max_bins=params["max_bins"],
        early_stopping=params["early_stopping"],
        random_state=params["random_state"],
    )


def generate_monthly_predictions(
    contract: dict[str, Any],
    frame: pd.DataFrame,
    feature_columns: list[str],
    period_start: pd.Timestamp,
    period_end: pd.Timestamp,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    finite_features = complete_feature_mask(frame, feature_columns)
    execution_columns = []
    for symbol in SYMBOLS:
        execution_columns.extend(
            [
                f"{symbol}_open",
                f"{symbol}_high",
                f"{symbol}_low",
                f"available_{symbol}_atr24",
                f"available_{symbol}_spread_price",
                f"next_{symbol}_open",
                f"next_{symbol}_spread_price",
            ]
        )
    executable_rows = frame[execution_columns].notna().all(axis=1)
    output_parts: list[pd.DataFrame] = []
    receipts: list[dict[str, Any]] = []
    fit_count = 0

    for month in month_starts(period_start, period_end):
        month_end = min(month + pd.DateOffset(months=1), period_end)
        lookback = month - pd.DateOffset(months=contract["model"]["lookback_calendar_months"])
        calibration_start = month - pd.DateOffset(
            months=contract["model"]["calibration_tail_calendar_months"]
        )
        train_mask = finite_features & (frame.index >= lookback) & (frame.index < month)
        early_mask = train_mask & (frame.index < calibration_start)
        calibration_mask = train_mask & (frame.index >= calibration_start)
        decision_mask = (
            finite_features
            & executable_rows
            & (frame.index >= month)
            & (frame.index < month_end)
        )

        if int(train_mask.sum()) < contract["model"]["minimum_training_rows"]:
            raise AdapterError(f"{month:%Y-%m} lacks minimum complete training rows")
        if int(early_mask.sum()) <= 0 or int(calibration_mask.sum()) <= 0:
            raise AdapterError(f"{month:%Y-%m} lacks early/calibration rows")
        if int(decision_mask.sum()) <= 0:
            raise AdapterError(f"{month:%Y-%m} lacks decision rows")

        prediction_part = frame.loc[decision_mask].copy()
        pooled_calibration_scores: list[np.ndarray] = []
        target_rows: dict[str, int] = {}

        for symbol in SYMBOLS:
            target_column = f"target_{symbol}"
            early_symbol = early_mask & frame[target_column].notna()
            calibration_symbol = calibration_mask & frame[target_column].notna()
            full_symbol = train_mask & frame[target_column].notna()
            if int(early_symbol.sum()) <= 0 or int(calibration_symbol.sum()) <= 0:
                raise AdapterError(f"{month:%Y-%m} {symbol} has incomplete calibration split")

            provisional = make_model(contract)
            provisional.fit(
                frame.loc[early_symbol, feature_columns],
                frame.loc[early_symbol, target_column],
            )
            calibration_prediction = provisional.predict(
                frame.loc[calibration_symbol, feature_columns]
            )
            pooled_calibration_scores.append(np.abs(calibration_prediction))
            fit_count += 1

            final_model = make_model(contract)
            final_model.fit(
                frame.loc[full_symbol, feature_columns],
                frame.loc[full_symbol, target_column],
            )
            prediction_part[f"prediction_{symbol}"] = final_model.predict(
                prediction_part[feature_columns]
            )
            fit_count += 1
            target_rows[symbol] = int(full_symbol.sum())

        pooled = np.concatenate(pooled_calibration_scores)
        if pooled.size <= 0 or not np.isfinite(pooled).all():
            raise AdapterError(f"{month:%Y-%m} calibration score pool is invalid")
        thresholds = {
            name: float(np.quantile(pooled, quantile, method="linear"))
            for name, quantile in ROLES.items()
        }
        for role_name, threshold in thresholds.items():
            prediction_part[f"threshold_{role_name}"] = threshold
        prediction_part["model_month"] = month.strftime("%Y-%m")
        output_parts.append(prediction_part)
        receipts.append(
            {
                "month": month.strftime("%Y-%m"),
                "lookback_start": lookback.isoformat(),
                "calibration_start": calibration_start.isoformat(),
                "early_rows": int(early_mask.sum()),
                "calibration_rows": int(calibration_mask.sum()),
                "full_target_rows": target_rows,
                "decision_rows": int(decision_mask.sum()),
                "pooled_calibration_predictions": int(pooled.size),
                "thresholds": thresholds,
            }
        )

    predictions = pd.concat(output_parts).sort_index()
    if predictions.index.has_duplicates:
        raise AdapterError("monthly prediction frame contains duplicate decision times")
    expected_fit_count = len(receipts) * len(SYMBOLS) * 2
    if fit_count != expected_fit_count:
        raise AdapterError(f"model fit count mismatch: {fit_count} != {expected_fit_count}")
    return predictions, receipts


def floor_volume(raw_volume: float) -> float:
    steps = math.floor((raw_volume + EPSILON) / VOLUME_STEP)
    return round(steps * VOLUME_STEP, 2)


def planned_volume(
    balance: float, stop_distance: float, target_fraction: float, hard_cap: float
) -> float | None:
    if not math.isfinite(balance) or not math.isfinite(stop_distance):
        return None
    if balance <= 0.0 or stop_distance <= 0.0:
        return None
    target_usd = balance * target_fraction
    volume = floor_volume(target_usd / stop_distance)
    if volume < VOLUME_MIN:
        volume = VOLUME_MIN
    planned_loss = stop_distance * volume
    if planned_loss > balance * hard_cap + EPSILON:
        return None
    return volume


@dataclass
class PathState:
    role: str
    actual_balance: float = 100.0
    stressed_balance: float = 100.0
    actual_peak: float = 100.0
    stressed_peak: float = 100.0
    actual_max_drawdown_usd: float = 0.0
    actual_max_drawdown_pct: float = 0.0
    stressed_max_drawdown_usd: float = 0.0
    stressed_max_drawdown_pct: float = 0.0
    actual_minimum_balance: float = 100.0
    stressed_minimum_balance: float = 100.0

    def apply(self, actual_pnl: float, stressed_pnl: float) -> None:
        self.actual_balance += actual_pnl
        self.stressed_balance += stressed_pnl
        self.actual_peak = max(self.actual_peak, self.actual_balance)
        self.stressed_peak = max(self.stressed_peak, self.stressed_balance)
        actual_dd = self.actual_peak - self.actual_balance
        stressed_dd = self.stressed_peak - self.stressed_balance
        self.actual_max_drawdown_usd = max(self.actual_max_drawdown_usd, actual_dd)
        self.stressed_max_drawdown_usd = max(self.stressed_max_drawdown_usd, stressed_dd)
        if self.actual_peak > 0.0:
            self.actual_max_drawdown_pct = max(
                self.actual_max_drawdown_pct, 100.0 * actual_dd / self.actual_peak
            )
        if self.stressed_peak > 0.0:
            self.stressed_max_drawdown_pct = max(
                self.stressed_max_drawdown_pct, 100.0 * stressed_dd / self.stressed_peak
            )
        self.actual_minimum_balance = min(self.actual_minimum_balance, self.actual_balance)
        self.stressed_minimum_balance = min(
            self.stressed_minimum_balance, self.stressed_balance
        )


def evaluate_trade(
    row: pd.Series, symbol: str, direction: int, stop_distance: float, volume: float
) -> tuple[float, float, str, float]:
    open_price = float(row[f"{symbol}_open"])
    high = float(row[f"{symbol}_high"])
    low = float(row[f"{symbol}_low"])
    next_open = float(row[f"next_{symbol}_open"])
    entry_spread = float(row[f"available_{symbol}_spread_price"])
    next_spread = float(row[f"next_{symbol}_spread_price"])

    if direction > 0:
        entry_price = open_price + entry_spread
        stop_price = entry_price - stop_distance
        stopped = low <= stop_price + EPSILON
        if stopped:
            actual_price_pnl = -stop_distance
            stress_extra_spread = entry_spread
            exit_reason = "STOP"
        else:
            actual_price_pnl = next_open - entry_price
            stress_extra_spread = entry_spread
            exit_reason = "H1_CLOSE"
    else:
        entry_price = open_price
        stop_ask = entry_price + stop_distance
        stopped = high + entry_spread >= stop_ask - EPSILON
        if stopped:
            actual_price_pnl = -stop_distance
            stress_extra_spread = entry_spread
            exit_reason = "STOP"
        else:
            exit_ask = next_open + next_spread
            actual_price_pnl = entry_price - exit_ask
            stress_extra_spread = next_spread
            exit_reason = "H1_CLOSE"

    actual_pnl = actual_price_pnl * volume
    stressed_pnl = (actual_price_pnl - stress_extra_spread) * volume
    return actual_pnl, stressed_pnl, exit_reason, stress_extra_spread * volume


def normal_trading_days(
    frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp
) -> int:
    rows = frame.loc[(frame.index >= start) & (frame.index < end)]
    return int(rows["time_server"].dt.normalize().nunique())


def simulate_role(
    contract: dict[str, Any],
    predictions: pd.DataFrame,
    role: str,
    period_start: pd.Timestamp,
    period_end: pd.Timestamp,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    execution = contract["position_and_proxy_execution"]
    state = PathState(role=role)
    decisions: list[dict[str, Any]] = []
    by_year: dict[str, dict[str, float | int]] = {}
    symbol_counts = {symbol: 0 for symbol in SYMBOLS}
    stop_count = 0
    total_extra_stress_cost = 0.0

    active_rows = predictions.loc[
        (predictions.index >= period_start) & (predictions.index < period_end)
    ]
    for decision_time, row in active_rows.iterrows():
        threshold = float(row[f"threshold_{role}"])
        ranked: list[tuple[float, str, int, float, float]] = []
        for symbol in SYMBOLS:
            score = float(row[f"prediction_{symbol}"])
            atr = float(row[f"available_{symbol}_atr24"])
            spread = float(row[f"available_{symbol}_spread_price"])
            required_cost_score = 2.0 * spread / atr if atr > 0.0 else math.inf
            if not all(math.isfinite(value) for value in (score, atr, spread)):
                continue
            if abs(score) + EPSILON < threshold:
                continue
            if abs(score) + EPSILON < required_cost_score:
                continue
            direction = 1 if score > 0.0 else -1
            stop_distance = 1.5 * atr
            volume = planned_volume(
                state.actual_balance,
                stop_distance,
                execution["target_position_risk_fraction_of_current_balance"],
                execution["hard_planned_risk_cap_fraction_after_minimum_lot_rounding"],
            )
            if volume is None:
                continue
            ranked.append((abs(score), symbol, direction, stop_distance, volume))

        if not ranked:
            continue
        ranked.sort(key=lambda item: (-item[0], SYMBOLS.index(item[1])))
        absolute_score, symbol, direction, stop_distance, volume = ranked[0]
        actual_pnl, stressed_pnl, exit_reason, extra_cost = evaluate_trade(
            row, symbol, direction, stop_distance, volume
        )
        actual_before = state.actual_balance
        stressed_before = state.stressed_balance
        state.apply(actual_pnl, stressed_pnl)
        total_extra_stress_cost += extra_cost
        symbol_counts[symbol] += 1
        stop_count += int(exit_reason == "STOP")

        year = str(decision_time.year)
        year_record = by_year.setdefault(
            year,
            {"starts": 0, "actual_net_usd": 0.0, "stressed_net_usd": 0.0},
        )
        year_record["starts"] = int(year_record["starts"]) + 1
        year_record["actual_net_usd"] = float(year_record["actual_net_usd"]) + actual_pnl
        year_record["stressed_net_usd"] = (
            float(year_record["stressed_net_usd"]) + stressed_pnl
        )
        decisions.append(
            {
                "role": role,
                "decision_time": decision_time.strftime("%Y-%m-%d %H:%M:%S"),
                "model_month": row["model_month"],
                "symbol": symbol,
                "direction": "LONG" if direction > 0 else "SHORT",
                "prediction": float(row[f"prediction_{symbol}"]),
                "absolute_prediction": absolute_score,
                "threshold": threshold,
                "atr24": float(row[f"available_{symbol}_atr24"]),
                "stop_distance": stop_distance,
                "volume": volume,
                "exit_reason": exit_reason,
                "actual_pnl_usd": actual_pnl,
                "stressed_pnl_usd": stressed_pnl,
                "extra_stress_cost_usd": extra_cost,
                "actual_balance_before": actual_before,
                "actual_balance_after": state.actual_balance,
                "stressed_balance_before": stressed_before,
                "stressed_balance_after": state.stressed_balance,
            }
        )

    days = normal_trading_days(predictions, period_start, period_end)
    starts = len(decisions)
    actual_net = state.actual_balance - 100.0
    stressed_net = state.stressed_balance - 100.0
    robust_recovery = (
        stressed_net / max(state.actual_max_drawdown_usd, EPSILON)
        if stressed_net > 0.0
        else 0.0
    )
    metrics = {
        "role": role,
        "period": f"{period_start.isoformat()}/{period_end.isoformat()}",
        "normal_trading_days": days,
        "lifecycle_starts": starts,
        "average_starts_per_normal_trading_day": starts / days if days else 0.0,
        "stop_exits": stop_count,
        "symbol_starts": symbol_counts,
        "actual_net_usd": actual_net,
        "stressed_net_usd": stressed_net,
        "actual_final_balance_usd": state.actual_balance,
        "stressed_final_balance_usd": state.stressed_balance,
        "actual_closed_balance_drawdown_usd": state.actual_max_drawdown_usd,
        "actual_closed_balance_drawdown_pct": state.actual_max_drawdown_pct,
        "stressed_closed_balance_drawdown_usd": state.stressed_max_drawdown_usd,
        "stressed_closed_balance_drawdown_pct": state.stressed_max_drawdown_pct,
        "actual_minimum_balance_usd": state.actual_minimum_balance,
        "stressed_minimum_balance_usd": state.stressed_minimum_balance,
        "robust_recovery_proxy": robust_recovery,
        "extra_doubled_cost_usd": total_extra_stress_cost,
        "years": by_year,
    }
    return metrics, decisions


def apply_development_gates(
    contract: dict[str, Any], metrics: dict[str, Any]
) -> dict[str, Any]:
    gates = contract["development_gates"]
    years = metrics["years"]
    actual_year_positive = all(
        year in years and float(years[year]["actual_net_usd"]) > 0.0
        for year in ("2024", "2025")
    )
    stressed_year_positive = all(
        year in years and float(years[year]["stressed_net_usd"]) > 0.0
        for year in ("2024", "2025")
    )
    checks = {
        "both_2024_and_2025_actual_net_positive": actual_year_positive,
        "both_2024_and_2025_stressed_net_positive": stressed_year_positive,
        "development_actual_net_above_v8": metrics["actual_net_usd"]
        > gates["development_actual_net_above_v8"],
        "development_stressed_net_above_v8": metrics["stressed_net_usd"]
        > gates["development_stressed_net_above_v8"],
        "development_closed_balance_drawdown_pct_max": metrics[
            "actual_closed_balance_drawdown_pct"
        ]
        <= gates["development_closed_balance_drawdown_pct_max"],
        "normal_trading_day_average_lifecycle_starts_min": metrics[
            "average_starts_per_normal_trading_day"
        ]
        >= gates["normal_trading_day_average_lifecycle_starts_min"],
        "actual_and_stressed_minimum_balance_positive": metrics[
            "actual_minimum_balance_usd"
        ]
        > 0.0
        and metrics["stressed_minimum_balance_usd"] > 0.0,
    }
    return {"checks": checks, "passed": all(checks.values())}


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    temporary.replace(path)


def write_decisions(path: Path, decisions: Iterable[dict[str, Any]]) -> None:
    frame = pd.DataFrame(list(decisions))
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, lineterminator="\n")


def runtime_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__,
    }


def run_development(
    contract: dict[str, Any], artifact_root: Path
) -> dict[str, Any]:
    inputs = verify_input_files(contract)
    start_text, end_text = contract["periods"]["development_selection"].split("/")
    period_start = pd.Timestamp(start_text)
    period_end = pd.Timestamp(end_text)
    bars, source_rows = load_aligned_bars(contract, period_end)
    frame, feature_columns = build_feature_frame(bars, include_targets=True)
    predictions, model_receipts = generate_monthly_predictions(
        contract, frame, feature_columns, period_start, period_end
    )

    role_results: list[dict[str, Any]] = []
    all_decisions: list[dict[str, Any]] = []
    for role in ROLES:
        metrics, decisions = simulate_role(
            contract, predictions, role, period_start, period_end
        )
        gate = apply_development_gates(contract, metrics)
        role_results.append({"metrics": metrics, "development_gate": gate})
        all_decisions.extend(decisions)

    passers = [item for item in role_results if item["development_gate"]["passed"]]
    passers.sort(
        key=lambda item: (
            -item["metrics"]["stressed_net_usd"],
            item["metrics"]["actual_closed_balance_drawdown_pct"],
            -min(
                float(record["stressed_net_usd"])
                for record in item["metrics"]["years"].values()
            ),
        )
    )
    selected_role = passers[0]["metrics"]["role"] if passers else None
    status = (
        "VALID_DEVELOPMENT_SELECTION_ONE_ROLE_LOCKED_CONFIRMATION_REQUIRED"
        if selected_role
        else "VALID_DEVELOPMENT_NO_ROLE_PASSED_LOCKED_CONFIRMATION_MUST_REMAIN_CLOSED"
    )

    result = {
        "schema": "zeta-next-independent-cross-index-hourly-adapter-challenge-v1-development-result",
        "status": status,
        "family": contract["family"],
        "contract": source_record(CONTRACT_PATH),
        "adapter": source_record(Path(__file__).resolve()),
        "inputs": inputs,
        "source_rows": source_rows,
        "runtime_versions": runtime_versions(),
        "feature_count": len(feature_columns),
        "model_months": len(model_receipts),
        "model_fits": len(model_receipts) * len(SYMBOLS) * 2,
        "model_receipts": model_receipts,
        "role_results": role_results,
        "development_pass_count": len(passers),
        "selected_role": selected_role,
        "locked_confirmation_opened": False,
        "ea_implemented": False,
        "mt5_paths": 0,
        "proxy_can_claim_v8_victory": False,
    }
    output_dir = artifact_root / "development"
    result_path = output_dir / "development-result.json"
    decisions_path = output_dir / "development-decisions.csv"
    write_decisions(decisions_path, all_decisions)
    result["decision_tape"] = source_record(decisions_path)
    atomic_write_json(result_path, result)
    return {
        "result_path": result_path,
        "result": result,
    }


def verify_selection_authority(
    path: Path, expected_sha256: str | None
) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise AdapterError(f"selection authority is missing: {path}")
    actual_sha = sha256_file(path)
    if expected_sha256 and actual_sha != expected_sha256.upper():
        raise AdapterError(
            f"selection authority hash mismatch: {actual_sha} != {expected_sha256.upper()}"
        )
    with path.open("r", encoding="utf-8") as handle:
        result = json.load(handle)
    expected_schema = (
        "zeta-next-independent-cross-index-hourly-adapter-challenge-v1-development-result"
    )
    if result.get("schema") != expected_schema:
        raise AdapterError("selection authority has the wrong schema")
    if result.get("status") != (
        "VALID_DEVELOPMENT_SELECTION_ONE_ROLE_LOCKED_CONFIRMATION_REQUIRED"
    ):
        raise AdapterError("selection authority does not authorize locked confirmation")
    selected_role = result.get("selected_role")
    if selected_role not in ROLES:
        raise AdapterError(f"invalid selected role: {selected_role}")
    if result.get("development_pass_count", 0) <= 0:
        raise AdapterError("selection authority contains no development passer")
    return result, actual_sha


def subset_metrics_from_decisions(
    decisions: list[dict[str, Any]],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    selected = [
        row
        for row in decisions
        if start
        <= pd.Timestamp(row["decision_time"])
        < end
    ]
    actual = sum(float(row["actual_pnl_usd"]) for row in selected)
    stressed = sum(float(row["stressed_pnl_usd"]) for row in selected)
    years: dict[str, dict[str, float | int]] = {}
    for row in selected:
        year = row["decision_time"][:4]
        record = years.setdefault(
            year, {"starts": 0, "actual_net_usd": 0.0, "stressed_net_usd": 0.0}
        )
        record["starts"] = int(record["starts"]) + 1
        record["actual_net_usd"] = float(record["actual_net_usd"]) + float(
            row["actual_pnl_usd"]
        )
        record["stressed_net_usd"] = float(record["stressed_net_usd"]) + float(
            row["stressed_pnl_usd"]
        )
    return {
        "starts": len(selected),
        "actual_net_usd": actual,
        "stressed_net_usd": stressed,
        "years": years,
    }


def run_confirmation(
    contract: dict[str, Any],
    artifact_root: Path,
    selection_authority: Path,
    selection_sha256: str | None,
) -> dict[str, Any]:
    development_result, authority_sha = verify_selection_authority(
        selection_authority, selection_sha256
    )
    selected_role = development_result["selected_role"]
    inputs = verify_input_files(contract)
    whole_start_text, whole_end_text = contract["periods"]["whole_v8_comparison"].split("/")
    whole_start = pd.Timestamp(whole_start_text)
    whole_end = pd.Timestamp(whole_end_text)
    confirmation_start_text, confirmation_end_text = contract["periods"][
        "locked_confirmation"
    ].split("/")
    confirmation_start = pd.Timestamp(confirmation_start_text)
    confirmation_end = pd.Timestamp(confirmation_end_text)

    bars, source_rows = load_aligned_bars(contract, whole_end)
    frame, feature_columns = build_feature_frame(bars, include_targets=True)
    predictions, model_receipts = generate_monthly_predictions(
        contract, frame, feature_columns, whole_start, whole_end
    )
    whole_metrics, decisions = simulate_role(
        contract, predictions, selected_role, whole_start, whole_end
    )
    development_subset = subset_metrics_from_decisions(
        decisions, whole_start, confirmation_start
    )
    confirmation_subset = subset_metrics_from_decisions(
        decisions, confirmation_start, confirmation_end
    )

    frozen_development = next(
        item["metrics"]
        for item in development_result["role_results"]
        if item["metrics"]["role"] == selected_role
    )
    for field in ("lifecycle_starts", "actual_net_usd", "stressed_net_usd"):
        observed_field = "starts" if field == "lifecycle_starts" else field
        observed = development_subset[observed_field]
        expected = frozen_development[field]
        if isinstance(expected, int):
            if int(observed) != expected:
                raise AdapterError(
                    f"development reproduction mismatch for {field}: {observed} != {expected}"
                )
        elif not math.isclose(float(observed), float(expected), rel_tol=0.0, abs_tol=1e-9):
            raise AdapterError(
                f"development reproduction mismatch for {field}: {observed} != {expected}"
            )

    challenge = contract["exact_v8_challenge"]
    whole_years_positive = all(
        float(record["actual_net_usd"]) > 0.0
        and float(record["stressed_net_usd"]) > 0.0
        for record in whole_metrics["years"].values()
    ) and set(whole_metrics["years"]) == {"2024", "2025", "2026"}
    confirmation_positive = (
        confirmation_subset["actual_net_usd"] > 0.0
        and confirmation_subset["stressed_net_usd"] > 0.0
    )
    checks = {
        "locked_confirmation_actual_and_stressed_positive": confirmation_positive,
        "actual_net_strictly_above_v8": whole_metrics["actual_net_usd"]
        > challenge["actual_net_usd_strictly_above"],
        "stressed_net_strictly_above_v8": whole_metrics["stressed_net_usd"]
        > challenge["doubled_cost_stressed_net_usd_strictly_above"],
        "closed_balance_drawdown_proxy_at_or_below_v8_native_equity_dd": whole_metrics[
            "actual_closed_balance_drawdown_pct"
        ]
        <= challenge["native_relative_equity_drawdown_pct_at_or_below"],
        "robust_recovery_proxy_strictly_above_v8": whole_metrics[
            "robust_recovery_proxy"
        ]
        > challenge["robust_recovery_strictly_above"],
        "each_calendar_epoch_actual_and_stressed_positive": whole_years_positive,
        "normal_trading_day_average_lifecycle_starts_min": whole_metrics[
            "average_starts_per_normal_trading_day"
        ]
        >= challenge["normal_trading_day_average_lifecycle_starts_min"],
        "actual_and_stressed_minimum_balance_positive": whole_metrics[
            "actual_minimum_balance_usd"
        ]
        > 0.0
        and whole_metrics["stressed_minimum_balance_usd"] > 0.0,
    }
    proxy_survivor = all(checks.values())
    status = (
        "VALID_PROXY_CHALLENGE_SURVIVOR_COMPLETE_EA_AND_NATIVE_STAGE_REQUIRED"
        if proxy_survivor
        else "VALID_LOCKED_CONFIRMATION_OR_WHOLE_PROXY_CHALLENGE_FAILED_NO_EA_NO_MT5"
    )

    result = {
        "schema": "zeta-next-independent-cross-index-hourly-adapter-challenge-v1-confirmation-result",
        "status": status,
        "family": contract["family"],
        "contract": source_record(CONTRACT_PATH),
        "adapter": source_record(Path(__file__).resolve()),
        "inputs": inputs,
        "source_rows": source_rows,
        "runtime_versions": runtime_versions(),
        "selection_authority": {
            "path": selection_authority.relative_to(REPOSITORY_ROOT).as_posix(),
            "bytes": selection_authority.stat().st_size,
            "sha256": authority_sha,
        },
        "selected_role": selected_role,
        "feature_count": len(feature_columns),
        "model_months": len(model_receipts),
        "model_fits": len(model_receipts) * len(SYMBOLS) * 2,
        "model_receipts": model_receipts,
        "development_reproduction": development_subset,
        "locked_confirmation": confirmation_subset,
        "whole_metrics": whole_metrics,
        "proxy_challenge_checks": checks,
        "proxy_challenge_passed": proxy_survivor,
        "proxy_can_claim_v8_victory": False,
        "ea_implemented": False,
        "mt5_paths": 0,
    }
    output_dir = artifact_root / "confirmation"
    result_path = output_dir / "confirmation-result.json"
    decisions_path = output_dir / "selected-role-decisions.csv"
    write_decisions(decisions_path, decisions)
    result["decision_tape"] = source_record(decisions_path)
    atomic_write_json(result_path, result)
    return {"result_path": result_path, "result": result}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("precheck", "development", "confirmation"), required=True
    )
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=DEFAULT_ARTIFACT_ROOT,
        help="campaign-owned generated output root",
    )
    parser.add_argument(
        "--selection-authority",
        type=Path,
        help="pinned development result required by confirmation mode",
    )
    parser.add_argument(
        "--selection-sha256",
        help="expected SHA-256 of the development selection authority",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    contract = load_contract()
    if args.mode == "precheck":
        payload = run_precheck(contract)
    elif args.mode == "development":
        outcome = run_development(contract, args.artifact_root.resolve())
        payload = {
            "status": outcome["result"]["status"],
            "result_path": outcome["result_path"].relative_to(REPOSITORY_ROOT).as_posix(),
            "selected_role": outcome["result"]["selected_role"],
            "development_pass_count": outcome["result"]["development_pass_count"],
        }
    else:
        if args.selection_authority is None:
            raise AdapterError("confirmation mode requires --selection-authority")
        outcome = run_confirmation(
            contract,
            args.artifact_root.resolve(),
            args.selection_authority.resolve(),
            args.selection_sha256,
        )
        payload = {
            "status": outcome["result"]["status"],
            "result_path": outcome["result_path"].relative_to(REPOSITORY_ROOT).as_posix(),
            "selected_role": outcome["result"]["selected_role"],
            "proxy_challenge_passed": outcome["result"]["proxy_challenge_passed"],
        }
    print(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AdapterError as error:
        print(f"ADAPTER_ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
