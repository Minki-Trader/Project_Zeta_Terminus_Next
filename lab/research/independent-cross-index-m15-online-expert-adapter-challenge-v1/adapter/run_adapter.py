#!/usr/bin/env python3
"""Causal M15 online-expert adapter and bounded economic proxy.

The precheck path is outcome-free.  It constructs synchronized M15 bars,
materializes expert directions, and checks state/risk feasibility, but it does
not calculate a virtual outcome, rank an expert, create a candidate decision,
or calculate candidate economics.
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

import numpy as np
import pandas as pd


FAMILY_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = FAMILY_ROOT / "config" / "challenge-contract.json"
DECLARATION_PATH = (
    FAMILY_ROOT
    / "evidence"
    / "INDEPENDENT_CROSS_INDEX_M15_ONLINE_EXPERT_ADAPTER_CHALLENGE_V1_DECLARATION.json"
)
FREEZE_PATH = (
    FAMILY_ROOT
    / "evidence"
    / "INDEPENDENT_CROSS_INDEX_M15_ONLINE_EXPERT_ADAPTER_CHALLENGE_V1_IMPLEMENTATION_FREEZE.json"
)
DEVELOPMENT_EVIDENCE_PATH = (
    FAMILY_ROOT
    / "evidence"
    / "INDEPENDENT_CROSS_INDEX_M15_ONLINE_EXPERT_ADAPTER_CHALLENGE_V1_DEVELOPMENT_RESULT.json"
)
ARTIFACT_ROOT = (
    PROJECT_ROOT
    / "lab"
    / "artifacts"
    / "independent-cross-index-m15-online-expert-adapter-challenge-v1"
)

SYMBOLS = ("US100", "US30", "US500")
HORIZONS = (1, 2, 4, 8, 16)
MODES = ("MOMENTUM", "REVERSION")
ROLE_HALFLIVES = {
    "ONLINE_HL32": 32,
    "ONLINE_HL96": 96,
    "ONLINE_HL256": 256,
}
INPUT_FILENAMES = {
    "US30": "US30_M1.parquet",
    "US100": "US100_M1.parquet",
    "US500": "US500_M15_BARS_20220701_20260821.csv",
}
M1_COLUMNS = (
    "time",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
)
M15_COLUMNS = (
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

INITIAL_BALANCE_USD = 100.0
POINT = 0.01
TICK_SIZE = 0.01
TICK_VALUE_PER_LOT = 0.01
DOLLARS_PER_PRICE_POINT_PER_LOT = TICK_VALUE_PER_LOT / TICK_SIZE
VOLUME_MIN = 0.01
VOLUME_STEP = 0.01
TARGET_RISK_FRACTION = 0.02
HARD_RISK_FRACTION = 0.04
ATR_BARS = 64
SIGNAL_MATERIALITY_ATR = 0.10
MINIMUM_MATURED = 256
STOP_R = -1.0
TAKE_R = 1.5
HOLD_BARS = 4
EPSILON = 1e-12


@dataclass(frozen=True)
class Expert:
    index: int
    symbol: str
    symbol_index: int
    horizon: int
    mode: str
    name: str


@dataclass
class OnlineMoments:
    half_life: int
    count: np.ndarray
    weight: np.ndarray
    first: np.ndarray
    second: np.ndarray

    @classmethod
    def create(cls, half_life: int, expert_count: int) -> "OnlineMoments":
        return cls(
            half_life=half_life,
            count=np.zeros(expert_count, dtype=np.int64),
            weight=np.zeros(expert_count, dtype=np.float64),
            first=np.zeros(expert_count, dtype=np.float64),
            second=np.zeros(expert_count, dtype=np.float64),
        )

    @property
    def decay(self) -> float:
        return float(0.5 ** (1.0 / self.half_life))

    def update(self, mask: np.ndarray, values: np.ndarray) -> None:
        if not np.any(mask):
            return
        decay = self.decay
        self.count[mask] += 1
        self.weight[mask] = decay * self.weight[mask] + 1.0
        self.first[mask] = decay * self.first[mask] + values[mask]
        self.second[mask] = decay * self.second[mask] + values[mask] ** 2

    def scores(self) -> np.ndarray:
        output = np.full(self.count.shape, np.nan, dtype=np.float64)
        ready = (self.count >= MINIMUM_MATURED) & (self.weight > 0.0)
        if not np.any(ready):
            return output
        mean = self.first[ready] / self.weight[ready]
        second_moment = self.second[ready] / self.weight[ready]
        variance = np.maximum(second_moment - mean * mean, 0.0)
        effective_limit = (1.0 + self.decay) / (1.0 - self.decay)
        effective_n = np.minimum(self.count[ready].astype(float), effective_limit)
        output[ready] = mean - 0.25 * np.sqrt(variance / effective_n)
        return output


@dataclass
class RoleBook:
    name: str
    actual_balance: float = INITIAL_BALANCE_USD
    stressed_balance: float = INITIAL_BALANCE_USD
    next_available_index: int = 0
    accepted_starts: int = 0
    capacity_blocks: int = 0
    nonpositive_score_blocks: int = 0
    infeasible_risk_blocks: int = 0
    pending_settlement_index: int | None = None
    pending_actual_pnl: float = 0.0
    pending_stressed_pnl: float = 0.0


def experts() -> tuple[Expert, ...]:
    population: list[Expert] = []
    for symbol_index, symbol in enumerate(SYMBOLS):
        for horizon in HORIZONS:
            for mode in MODES:
                population.append(
                    Expert(
                        index=len(population),
                        symbol=symbol,
                        symbol_index=symbol_index,
                        horizon=horizon,
                        mode=mode,
                        name=f"{symbol}_H{horizon}_{mode}",
                    )
                )
    return tuple(population)


EXPERTS = experts()


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


def file_record(path: Path, reported_path: Path | None = None) -> dict[str, Any]:
    record = {
        "path": project_relative(reported_path or path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if path.suffix.lower() in {".py", ".csv", ".json", ".md"}:
        record["lines"] = line_count(path)
    return record


def verify_file_record(record: dict[str, Any]) -> None:
    path = PROJECT_ROOT / str(record["path"])
    if not path.is_file():
        raise RuntimeError(f"missing frozen file: {path}")
    if path.stat().st_size != int(record["bytes"]):
        raise RuntimeError(f"byte mismatch: {path}")
    if sha256_file(path) != str(record["sha256"]).upper():
        raise RuntimeError(f"SHA-256 mismatch: {path}")
    if "lines" in record and line_count(path) != int(record["lines"]):
        raise RuntimeError(f"line-count mismatch: {path}")


def nested_file_records(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if {"path", "bytes", "sha256"}.issubset(value):
            yield value
        else:
            for nested in value.values():
                yield from nested_file_records(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from nested_file_records(nested)


def verify_authorities(
    mode: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    contract = load_json(CONTRACT_PATH)
    declaration = load_json(DECLARATION_PATH)
    if contract.get("schema") != (
        "zeta-next-independent-cross-index-m15-online-expert-adapter-"
        "challenge-v1-contract"
    ):
        raise RuntimeError("contract schema mismatch")
    if declaration.get("status") != (
        "DECLARED_PREINPUT_PREM15_PREEXPERT_PREIMPLEMENTATION_PREOUTCOME"
    ):
        raise RuntimeError("declaration status mismatch")
    for record in declaration["frozen_files"].values():
        verify_file_record(record)
    verify_file_record(declaration["selection_authority"])
    for symbol_key, authority in declaration["source_authorities"].items():
        verify_file_record(authority)
        symbol = symbol_key.split("_", 1)[0]
        copied = FAMILY_ROOT / "data" / "input" / INPUT_FILENAMES[symbol]
        if not copied.is_file():
            raise RuntimeError(f"missing family input: {symbol}")
        if copied.stat().st_size != int(authority["bytes"]):
            raise RuntimeError(f"family input byte mismatch: {symbol}")
        if sha256_file(copied) != str(authority["sha256"]).upper():
            raise RuntimeError(f"family input SHA-256 mismatch: {symbol}")
    challenge = contract["exact_v8_challenge"]
    verify_file_record(
        {
            "path": challenge["authority_path"],
            "bytes": challenge["authority_bytes"],
            "sha256": challenge["authority_sha256"],
        }
    )
    freeze: dict[str, Any] | None = None
    if mode != "precheck":
        if not FREEZE_PATH.is_file():
            raise RuntimeError("implementation freeze is absent")
        freeze = load_json(FREEZE_PATH)
        if freeze.get("status") != "IMPLEMENTATION_FROZEN_PREDEVELOPMENT_OUTCOME":
            raise RuntimeError("implementation freeze status mismatch")
        records = list(nested_file_records(freeze.get("frozen_files", {})))
        if not records:
            raise RuntimeError("implementation freeze has no frozen files")
        for record in records:
            verify_file_record(record)
    return contract, declaration, freeze


def validate_price_frame(frame: pd.DataFrame, symbol: str) -> None:
    numeric = frame[["open", "high", "low", "close"]].to_numpy(dtype=float)
    if not np.isfinite(numeric).all() or np.any(numeric <= 0.0):
        raise RuntimeError(f"invalid price value: {symbol}")
    if np.any(frame["high"].to_numpy(dtype=float) < frame["low"].to_numpy(dtype=float)):
        raise RuntimeError(f"high/low inversion: {symbol}")
    if np.any(frame["high"].to_numpy(dtype=float) < frame[["open", "close"]].max(axis=1)):
        raise RuntimeError(f"high below open/close: {symbol}")
    if np.any(frame["low"].to_numpy(dtype=float) > frame[["open", "close"]].min(axis=1)):
        raise RuntimeError(f"low above open/close: {symbol}")
    if np.any(frame["spread"].to_numpy(dtype=float) < 0.0):
        raise RuntimeError(f"negative spread: {symbol}")


def aggregate_m1_to_m15(path: Path, symbol: str, end_epoch: int) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=list(M1_COLUMNS))
    if tuple(frame.columns) != M1_COLUMNS:
        raise RuntimeError(f"M1 column mismatch: {symbol}")
    if frame["time"].duplicated().any():
        raise RuntimeError(f"duplicate M1 epoch: {symbol}")
    frame = frame.loc[frame["time"] < end_epoch].copy()
    frame = frame.sort_values("time", kind="mergesort").reset_index(drop=True)
    epoch = frame["time"].to_numpy(dtype=np.int64)
    if np.any(epoch % 60 != 0) or np.any(np.diff(epoch) <= 0):
        raise RuntimeError(f"invalid M1 cadence: {symbol}")
    validate_price_frame(frame, symbol)
    frame["slot"] = frame["time"] - (frame["time"] % 900)
    grouped = frame.groupby("slot", sort=True, observed=True)
    bars = grouped.agg(
        row_count=("time", "size"),
        first_epoch=("time", "first"),
        last_epoch=("time", "last"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        tick_volume=("tick_volume", "sum"),
        spread_entry=("spread", "first"),
        spread_exit=("spread", "last"),
        real_volume=("real_volume", "sum"),
    )
    complete = (
        (bars["row_count"] == 15)
        & (bars["first_epoch"] == bars.index)
        & (bars["last_epoch"] == bars.index + 840)
    )
    bars = bars.loc[complete].drop(columns=["row_count", "first_epoch", "last_epoch"])
    bars.index = bars.index.astype(np.int64)
    bars.index.name = "time_epoch"
    return bars


def load_native_m15(path: Path, symbol: str, end_epoch: int) -> pd.DataFrame:
    frame = pd.read_csv(path, usecols=list(M15_COLUMNS))
    if tuple(frame.columns) != M15_COLUMNS:
        raise RuntimeError(f"M15 column mismatch: {symbol}")
    if frame["time_epoch"].duplicated().any():
        raise RuntimeError(f"duplicate M15 epoch: {symbol}")
    server_time = pd.to_datetime(
        frame["time_server"], format="%Y.%m.%d %H:%M:%S", errors="raise"
    )
    epoch_time = pd.to_datetime(frame["time_epoch"], unit="s", utc=True).dt.tz_localize(
        None
    )
    if not server_time.equals(epoch_time):
        raise RuntimeError(f"server/epoch mismatch: {symbol}")
    frame = frame.loc[frame["time_epoch"] < end_epoch].copy()
    frame = frame.sort_values("time_epoch", kind="mergesort").reset_index(drop=True)
    epoch = frame["time_epoch"].to_numpy(dtype=np.int64)
    if np.any(epoch % 900 != 0) or np.any(np.diff(epoch) <= 0):
        raise RuntimeError(f"invalid native M15 cadence: {symbol}")
    validate_price_frame(frame, symbol)
    output = frame.set_index("time_epoch", verify_integrity=True)[
        ["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
    ].copy()
    output["spread_entry"] = output.pop("spread")
    output["spread_exit"] = output["spread_entry"]
    return output[
        [
            "open",
            "high",
            "low",
            "close",
            "tick_volume",
            "spread_entry",
            "spread_exit",
            "real_volume",
        ]
    ]


def load_common_m15(end_exclusive: pd.Timestamp) -> tuple[pd.DataFrame, dict[str, Any]]:
    end_epoch = int(end_exclusive.timestamp())
    per_symbol: dict[str, pd.DataFrame] = {}
    for symbol in ("US30", "US100"):
        per_symbol[symbol] = aggregate_m1_to_m15(
            FAMILY_ROOT / "data" / "input" / INPUT_FILENAMES[symbol],
            symbol,
            end_epoch,
        )
    per_symbol["US500"] = load_native_m15(
        FAMILY_ROOT / "data" / "input" / INPUT_FILENAMES["US500"],
        "US500",
        end_epoch,
    )
    common: pd.DataFrame | None = None
    for symbol in SYMBOLS:
        renamed = per_symbol[symbol].rename(
            columns={column: f"{symbol}_{column}" for column in per_symbol[symbol].columns}
        )
        common = renamed if common is None else common.join(renamed, how="inner")
    if common is None or common.empty:
        raise RuntimeError("no common M15 rows")
    common = common.sort_index()
    common.insert(0, "time", pd.to_datetime(common.index, unit="s", utc=True).tz_localize(None))
    if common.index.duplicated().any() or not common.index.is_monotonic_increasing:
        raise RuntimeError("common M15 timeline is invalid")
    construction = {
        "source_complete_m15_rows": {
            symbol: int(len(per_symbol[symbol])) for symbol in SYMBOLS
        },
        "common_rows": int(len(common)),
        "first_common_time": common["time"].iloc[0].isoformat(),
        "last_common_time": common["time"].iloc[-1].isoformat(),
        "common_start_minute_counts": {
            str(minute): int((common["time"].dt.minute == minute).sum())
            for minute in (0, 15, 30, 45)
        },
    }
    return common, construction


def build_atr(frame: pd.DataFrame) -> np.ndarray:
    output = np.full((len(frame), len(SYMBOLS)), np.nan, dtype=np.float64)
    for symbol_index, symbol in enumerate(SYMBOLS):
        high = frame[f"{symbol}_high"].to_numpy(dtype=np.float64)
        low = frame[f"{symbol}_low"].to_numpy(dtype=np.float64)
        close = frame[f"{symbol}_close"].to_numpy(dtype=np.float64)
        previous = np.roll(close, 1)
        previous[0] = np.nan
        true_range = np.maximum.reduce(
            [high - low, np.abs(high - previous), np.abs(low - previous)]
        )
        output[:, symbol_index] = (
            pd.Series(true_range)
            .rolling(ATR_BARS, min_periods=ATR_BARS)
            .mean()
            .to_numpy(dtype=np.float64)
        )
    return output


def build_directions(frame: pd.DataFrame, atr: np.ndarray) -> np.ndarray:
    directions = np.zeros((len(frame), len(EXPERTS)), dtype=np.int8)
    for expert in EXPERTS:
        close = frame[f"{expert.symbol}_close"].to_numpy(dtype=np.float64)
        current = np.roll(close, 1)
        current[0] = np.nan
        prior = np.roll(close, 1 + expert.horizon)
        prior[: 1 + expert.horizon] = np.nan
        log_return = np.log(current / prior)
        prior_atr = np.roll(atr[:, expert.symbol_index], 1)
        prior_atr[0] = np.nan
        normalized_atr = prior_atr / current
        valid = (
            np.isfinite(log_return)
            & np.isfinite(normalized_atr)
            & (np.abs(log_return) >= SIGNAL_MATERIALITY_ATR * normalized_atr)
            & (log_return != 0.0)
        )
        sign = np.zeros(len(frame), dtype=np.int8)
        sign[valid & (log_return > 0.0)] = 1
        sign[valid & (log_return < 0.0)] = -1
        if expert.mode == "REVERSION":
            sign = -sign
        directions[valid, expert.index] = sign[valid]
    return directions


def time_mask(
    frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp
) -> np.ndarray:
    time = frame["time"].to_numpy(dtype="datetime64[ns]")
    return (time >= np.datetime64(start)) & (time < np.datetime64(end))


def normal_trading_days(
    frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp
) -> tuple[int, dict[str, int]]:
    selected = frame.loc[time_mask(frame, start, end), "time"]
    counts = selected.dt.date.value_counts().sort_index()
    distribution = {
        "calendar_dates": int(len(counts)),
        "dates_at_least_60_common_bars": int((counts >= 60).sum()),
        "dates_at_least_80_common_bars": int((counts >= 80).sum()),
        "median_common_bars": int(counts.median()) if len(counts) else 0,
    }
    return distribution["dates_at_least_60_common_bars"], distribution


def planned_volume(balance: float, atr_price: float) -> tuple[float | None, str]:
    if not math.isfinite(balance) or balance <= 0.0:
        return None, "NONPOSITIVE_ACTUAL_BALANCE"
    risk_per_lot = atr_price * DOLLARS_PER_PRICE_POINT_PER_LOT
    if not math.isfinite(risk_per_lot) or risk_per_lot <= 0.0:
        return None, "INVALID_ATR_RISK"
    target = balance * TARGET_RISK_FRACTION
    raw = target / risk_per_lot
    steps = math.floor((raw + EPSILON) / VOLUME_STEP)
    volume = round(steps * VOLUME_STEP, 2)
    if volume < VOLUME_MIN:
        volume = VOLUME_MIN
    planned_loss = volume * risk_per_lot
    if planned_loss > balance * HARD_RISK_FRACTION + EPSILON:
        return None, "MINIMUM_LOT_HARD_RISK_CAP"
    return volume, "FEASIBLE"


def simulate_path(
    frame: pd.DataFrame,
    entry_index: int,
    symbol_index: int,
    direction: int,
    atr_price: float,
) -> dict[str, Any]:
    if direction not in (-1, 1):
        raise ValueError("direction must be -1 or +1")
    if entry_index + HOLD_BARS - 1 >= len(frame):
        raise RuntimeError("incomplete four-bar path")
    symbol = SYMBOLS[symbol_index]
    entry_bid = float(frame[f"{symbol}_open"].iat[entry_index])
    entry_spread = float(frame[f"{symbol}_spread_entry"].iat[entry_index]) * POINT
    entry_price = entry_bid + entry_spread if direction > 0 else entry_bid
    stop_price = entry_price + STOP_R * atr_price * direction
    take_price = entry_price + TAKE_R * atr_price * direction
    exit_index = entry_index + HOLD_BARS - 1
    exit_reason = "TIME_4_M15"
    exit_spread = float(frame[f"{symbol}_spread_exit"].iat[exit_index]) * POINT
    exit_price = float(frame[f"{symbol}_close"].iat[exit_index])
    if direction < 0:
        exit_price += exit_spread
    for bar_index in range(entry_index, entry_index + HOLD_BARS):
        high_bid = float(frame[f"{symbol}_high"].iat[bar_index])
        low_bid = float(frame[f"{symbol}_low"].iat[bar_index])
        bar_spread = float(frame[f"{symbol}_spread_entry"].iat[bar_index]) * POINT
        if direction > 0:
            stop_hit = low_bid <= stop_price
            take_hit = high_bid >= take_price
        else:
            high_ask = high_bid + bar_spread
            low_ask = low_bid + bar_spread
            stop_hit = high_ask >= stop_price
            take_hit = low_ask <= take_price
        if stop_hit:
            exit_index = bar_index
            exit_reason = "STOP_ADVERSE_FIRST"
            exit_price = stop_price
            exit_spread = bar_spread
            break
        if take_hit:
            exit_index = bar_index
            exit_reason = "TAKE"
            exit_price = take_price
            exit_spread = bar_spread
            break
    actual_per_lot = (
        direction
        * (exit_price - entry_price)
        * DOLLARS_PER_PRICE_POINT_PER_LOT
    )
    extra_stress_per_lot = entry_spread if direction > 0 else exit_spread
    planned_risk_per_lot = atr_price * DOLLARS_PER_PRICE_POINT_PER_LOT
    actual_r = actual_per_lot / planned_risk_per_lot
    return {
        "entry_index": entry_index,
        "exit_index": exit_index,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "entry_spread_price": entry_spread,
        "exit_spread_price": exit_spread,
        "exit_reason": exit_reason,
        "planned_risk_per_lot": planned_risk_per_lot,
        "actual_pnl_per_lot": actual_per_lot,
        "extra_stress_cost_per_lot": extra_stress_per_lot,
        "actual_r": actual_r,
    }


def structural_precheck(contract: dict[str, Any]) -> dict[str, Any]:
    development_start = pd.Timestamp("2024-01-01T00:00:00")
    development_end = pd.Timestamp("2026-01-01T00:00:00")
    frame, construction = load_common_m15(development_end)
    atr = build_atr(frame)
    directions = build_directions(frame, atr)
    decision_mask = time_mask(frame, development_start, development_end)
    complete_future = np.arange(len(frame)) + HOLD_BARS - 1 < len(frame)
    decision_mask &= complete_future
    decision_indices = np.flatnonzero(decision_mask)
    normal_days, day_distribution = normal_trading_days(
        frame, development_start, development_end
    )
    expert_density: dict[str, Any] = {}
    for expert in EXPERTS:
        valid = directions[:, expert.index] != 0
        matured_before_end = np.zeros(len(frame), dtype=np.int64)
        if len(frame) > HOLD_BARS:
            matured_before_end[HOLD_BARS:] = np.cumsum(valid[:-HOLD_BARS])
        ready_dev = decision_mask & (matured_before_end >= MINIMUM_MATURED)
        first_ready = frame["time"].iloc[np.flatnonzero(ready_dev)[0]].isoformat() if np.any(ready_dev) else None
        expert_density[expert.name] = {
            "development_valid_directions": int((valid & decision_mask).sum()),
            "matured_observations_available_before_development_end": int(
                valid[:-HOLD_BARS].sum() if len(valid) > HOLD_BARS else 0
            ),
            "development_rows_after_256_maturity": int(ready_dev.sum()),
            "first_development_time_after_256_maturity": first_ready,
        }
    risk_feasibility: dict[str, Any] = {}
    for symbol_index, symbol in enumerate(SYMBOLS):
        feasible = 0
        hard_cap = 0
        invalid = 0
        for index in decision_indices:
            volume, reason = planned_volume(INITIAL_BALANCE_USD, atr[index - 1, symbol_index])
            if volume is not None:
                feasible += 1
            elif reason == "MINIMUM_LOT_HARD_RISK_CAP":
                hard_cap += 1
            else:
                invalid += 1
        risk_feasibility[symbol] = {
            "fixed_100_usd_feasible_rows": feasible,
            "minimum_lot_hard_cap_rows": hard_cap,
            "invalid_atr_or_balance_rows": invalid,
        }
    return {
        "schema": (
            "zeta-next-independent-cross-index-m15-online-expert-adapter-"
            "challenge-v1-structural-precheck"
        ),
        "status": "STRUCTURAL_PRECHECK_PASS_NO_VIRTUAL_OR_CANDIDATE_OUTCOME",
        "authorities": {
            "contract": file_record(CONTRACT_PATH),
            "declaration": file_record(DECLARATION_PATH),
            "adapter": file_record(Path(__file__).resolve()),
        },
        "construction": construction,
        "development_structure": {
            "decision_rows_with_complete_four_bar_path": int(len(decision_indices)),
            "normal_trading_days": normal_days,
            "day_distribution": day_distribution,
        },
        "expert_state_feasibility": expert_density,
        "risk_feasibility_at_initial_100_usd": risk_feasibility,
        "attestation": {
            "virtual_outcomes_calculated": 0,
            "online_scores_calculated": 0,
            "experts_ranked": 0,
            "candidate_decisions": 0,
            "candidate_lifecycles": 0,
            "candidate_economic_metrics": 0,
            "locked_confirmation_rows_used": 0,
            "ea_source_files": 0,
            "mt5_paths": 0,
        },
        "contract_initial_balance_interpretation": {
            "initial_deposit_usd": INITIAL_BALANCE_USD,
            "authority": "exact V8 benchmark initial_deposit_usd",
        },
    }


def precompute_virtual_outcomes(
    frame: pd.DataFrame, atr: np.ndarray
) -> np.ndarray:
    outcomes = np.full(
        (len(frame), len(SYMBOLS), 2), np.nan, dtype=np.float64
    )
    for index in range(len(frame) - HOLD_BARS + 1):
        prior_index = index - 1
        if prior_index < 0:
            continue
        for symbol_index in range(len(SYMBOLS)):
            risk = atr[prior_index, symbol_index]
            if not math.isfinite(float(risk)) or risk <= 0.0:
                continue
            for direction_slot, direction in enumerate((-1, 1)):
                path = simulate_path(frame, index, symbol_index, direction, float(risk))
                outcomes[index, symbol_index, direction_slot] = float(
                    np.clip(path["actual_r"], -3.0, 3.0)
                )
    return outcomes


def matured_values(
    matured_directions: np.ndarray,
    virtual_outcomes: np.ndarray,
    launch_index: int,
) -> tuple[np.ndarray, np.ndarray]:
    values = np.full(len(EXPERTS), np.nan, dtype=np.float64)
    for expert in EXPERTS:
        direction = int(matured_directions[expert.index])
        if direction == 0:
            continue
        direction_slot = 1 if direction > 0 else 0
        values[expert.index] = virtual_outcomes[
            launch_index, expert.symbol_index, direction_slot
        ]
    mask = np.isfinite(values)
    return mask, values


def select_expert(
    state: OnlineMoments, current_directions: np.ndarray
) -> tuple[int | None, np.ndarray, int, int]:
    scores = state.scores()
    valid_now = current_directions != 0
    ready_now = valid_now & np.isfinite(scores)
    positive = ready_now & (scores > 0.0)
    if not np.any(positive):
        return None, scores, int(ready_now.sum()), 0
    ranked = np.where(positive, scores, -np.inf)
    selected = int(np.argmax(ranked))
    return selected, scores, int(ready_now.sum()), int(positive.sum())


def run_online_roles(
    frame: pd.DataFrame,
    trade_start: pd.Timestamp,
    trade_end: pd.Timestamp,
    role_names: Iterable[str],
) -> tuple[dict[str, RoleBook], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    atr = build_atr(frame)
    directions = build_directions(frame, atr)
    virtual_outcomes = precompute_virtual_outcomes(frame, atr)
    role_names = tuple(role_names)
    states = {
        role: OnlineMoments.create(ROLE_HALFLIVES[role], len(EXPERTS))
        for role in role_names
    }
    books = {role: RoleBook(role) for role in role_names}
    trades: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []
    trade_time_mask = time_mask(frame, trade_start, trade_end)
    complete_future = np.arange(len(frame)) + HOLD_BARS - 1 < len(frame)
    candidate_rows = trade_time_mask & complete_future
    virtual_update_count = 0
    for index in range(len(frame)):
        launch_index = index - HOLD_BARS
        update_mask = np.zeros(len(EXPERTS), dtype=bool)
        update_values = np.full(len(EXPERTS), np.nan, dtype=np.float64)
        if launch_index >= 0:
            update_mask, update_values = matured_values(
                directions[launch_index], virtual_outcomes, launch_index
            )
            virtual_update_count += int(update_mask.sum())
            for state in states.values():
                state.update(update_mask, update_values)
        for book in books.values():
            if (
                book.pending_settlement_index is not None
                and index >= book.pending_settlement_index
            ):
                book.actual_balance += book.pending_actual_pnl
                book.stressed_balance += book.pending_stressed_pnl
                book.pending_settlement_index = None
                book.pending_actual_pnl = 0.0
                book.pending_stressed_pnl = 0.0
        if not candidate_rows[index]:
            continue
        for role in role_names:
            state = states[role]
            book = books[role]
            selected, scores, ready_count, positive_count = select_expert(
                state, directions[index]
            )
            slot_available = index >= book.next_available_index
            accepted = False
            rejection = ""
            selected_name = ""
            selected_score: float | None = None
            if not slot_available:
                book.capacity_blocks += 1
                rejection = "GLOBAL_SLOT_OCCUPIED"
            elif selected is None:
                book.nonpositive_score_blocks += 1
                rejection = "NO_POSITIVE_CURRENT_EXPERT"
            else:
                expert = EXPERTS[selected]
                selected_name = expert.name
                selected_score = float(scores[selected])
                direction = int(directions[index, selected])
                risk = float(atr[index - 1, expert.symbol_index])
                volume, reason = planned_volume(book.actual_balance, risk)
                if volume is None:
                    book.infeasible_risk_blocks += 1
                    rejection = reason
                else:
                    path = simulate_path(
                        frame, index, expert.symbol_index, direction, risk
                    )
                    actual_pnl = float(path["actual_pnl_per_lot"] * volume)
                    extra_stress_cost = float(
                        path["extra_stress_cost_per_lot"] * volume
                    )
                    stressed_pnl = actual_pnl - extra_stress_cost
                    actual_before = book.actual_balance
                    stressed_before = book.stressed_balance
                    book.next_available_index = int(path["exit_index"]) + 1
                    book.pending_settlement_index = book.next_available_index
                    book.pending_actual_pnl = actual_pnl
                    book.pending_stressed_pnl = stressed_pnl
                    book.accepted_starts += 1
                    accepted = True
                    trade = {
                        "role": role,
                        "sequence": book.accepted_starts,
                        "entry_time_epoch": int(frame.index[index]),
                        "entry_time": frame["time"].iat[index].isoformat(),
                        "exit_time_epoch": int(frame.index[int(path["exit_index"])]),
                        "exit_time": frame["time"].iat[int(path["exit_index"])].isoformat(),
                        "expert": expert.name,
                        "symbol": expert.symbol,
                        "horizon": expert.horizon,
                        "mode": expert.mode,
                        "direction": "LONG" if direction > 0 else "SHORT",
                        "online_score_R": selected_score,
                        "matured_observations": int(state.count[selected]),
                        "atr_price": risk,
                        "volume_lots": volume,
                        "planned_risk_usd": volume * path["planned_risk_per_lot"],
                        "entry_price": path["entry_price"],
                        "exit_price": path["exit_price"],
                        "exit_reason": path["exit_reason"],
                        "actual_pnl_usd": actual_pnl,
                        "extra_stress_cost_usd": extra_stress_cost,
                        "stressed_pnl_usd": stressed_pnl,
                        "actual_balance_before_usd": actual_before,
                        "actual_balance_after_usd": actual_before + actual_pnl,
                        "stressed_balance_before_usd": stressed_before,
                        "stressed_balance_after_usd": stressed_before + stressed_pnl,
                    }
                    trades.append(trade)
            state_rows.append(
                {
                    "time_epoch": int(frame.index[index]),
                    "time": frame["time"].iat[index].isoformat(),
                    "role": role,
                    "total_matured_observations": int(state.count.sum()),
                    "experts_at_256_maturity": int((state.count >= MINIMUM_MATURED).sum()),
                    "current_valid_experts_with_score": ready_count,
                    "current_positive_experts": positive_count,
                    "selected_expert": selected_name,
                    "selected_score_R": selected_score,
                    "slot_available": int(slot_available),
                    "accepted": int(accepted),
                    "rejection": rejection,
                    "settled_actual_balance_usd": book.actual_balance,
                }
            )
    for book in books.values():
        if book.pending_settlement_index is not None:
            book.actual_balance += book.pending_actual_pnl
            book.stressed_balance += book.pending_stressed_pnl
            book.pending_settlement_index = None
            book.pending_actual_pnl = 0.0
            book.pending_stressed_pnl = 0.0
    diagnostics = {
        "common_rows_processed": int(len(frame)),
        "virtual_outcome_updates_applied_per_role": virtual_update_count,
        "candidate_decision_rows_per_role": int(candidate_rows.sum()),
        "role_book_counters": {
            role: {
                "accepted_starts": books[role].accepted_starts,
                "capacity_blocks": books[role].capacity_blocks,
                "nonpositive_score_blocks": books[role].nonpositive_score_blocks,
                "infeasible_risk_blocks": books[role].infeasible_risk_blocks,
            }
            for role in role_names
        },
    }
    return books, trades, state_rows, diagnostics


def metrics_from_trades(
    trades: list[dict[str, Any]], normal_days: int, years: Iterable[int]
) -> dict[str, Any]:
    actual_balance = INITIAL_BALANCE_USD
    stressed_balance = INITIAL_BALANCE_USD
    actual_peak = INITIAL_BALANCE_USD
    stressed_peak = INITIAL_BALANCE_USD
    max_actual_dd_usd = 0.0
    max_actual_dd_pct = 0.0
    max_stressed_dd_usd = 0.0
    max_stressed_dd_pct = 0.0
    minimum_actual = INITIAL_BALANCE_USD
    minimum_stressed = INITIAL_BALANCE_USD
    yearly = {
        str(year): {"starts": 0, "actual_net_usd": 0.0, "stressed_net_usd": 0.0}
        for year in years
    }
    symbols = {
        symbol: {"starts": 0, "actual_net_usd": 0.0, "stressed_net_usd": 0.0}
        for symbol in SYMBOLS
    }
    exits: dict[str, int] = {}
    for trade in trades:
        actual = float(trade["actual_pnl_usd"])
        stressed = float(trade["stressed_pnl_usd"])
        actual_balance += actual
        stressed_balance += stressed
        actual_peak = max(actual_peak, actual_balance)
        stressed_peak = max(stressed_peak, stressed_balance)
        actual_dd = actual_peak - actual_balance
        stressed_dd = stressed_peak - stressed_balance
        max_actual_dd_usd = max(max_actual_dd_usd, actual_dd)
        max_stressed_dd_usd = max(max_stressed_dd_usd, stressed_dd)
        max_actual_dd_pct = max(
            max_actual_dd_pct,
            100.0 * actual_dd / actual_peak if actual_peak > 0.0 else 0.0,
        )
        max_stressed_dd_pct = max(
            max_stressed_dd_pct,
            100.0 * stressed_dd / stressed_peak if stressed_peak > 0.0 else 0.0,
        )
        minimum_actual = min(minimum_actual, actual_balance)
        minimum_stressed = min(minimum_stressed, stressed_balance)
        year = str(pd.Timestamp(trade["entry_time"]).year)
        if year in yearly:
            yearly[year]["starts"] += 1
            yearly[year]["actual_net_usd"] += actual
            yearly[year]["stressed_net_usd"] += stressed
        symbol = str(trade["symbol"])
        symbols[symbol]["starts"] += 1
        symbols[symbol]["actual_net_usd"] += actual
        symbols[symbol]["stressed_net_usd"] += stressed
        reason = str(trade["exit_reason"])
        exits[reason] = exits.get(reason, 0) + 1
    actual_net = actual_balance - INITIAL_BALANCE_USD
    stressed_net = stressed_balance - INITIAL_BALANCE_USD
    return {
        "starts": len(trades),
        "normal_trading_days": normal_days,
        "average_starts_per_normal_trading_day": (
            len(trades) / normal_days if normal_days else 0.0
        ),
        "actual_net_usd": actual_net,
        "stressed_net_usd": stressed_net,
        "actual_ending_balance_usd": actual_balance,
        "stressed_ending_balance_usd": stressed_balance,
        "actual_closed_balance_drawdown_usd": max_actual_dd_usd,
        "actual_closed_balance_drawdown_pct": max_actual_dd_pct,
        "stressed_closed_balance_drawdown_usd": max_stressed_dd_usd,
        "stressed_closed_balance_drawdown_pct": max_stressed_dd_pct,
        "minimum_actual_balance_usd": minimum_actual,
        "minimum_stressed_balance_usd": minimum_stressed,
        "robust_recovery_proxy": (
            stressed_net / max_actual_dd_usd if max_actual_dd_usd > 0.0 else None
        ),
        "symbol_breadth": sum(values["starts"] > 0 for values in symbols.values()),
        "symbols": symbols,
        "years": yearly,
        "exit_reasons": exits,
    }


def development_gates(
    metrics: dict[str, Any], contract: dict[str, Any]
) -> dict[str, bool]:
    gates = contract["development_gates"]
    return {
        "both_2024_and_2025_actual_positive": all(
            metrics["years"][str(year)]["actual_net_usd"] > 0.0
            for year in (2024, 2025)
        ),
        "both_2024_and_2025_stressed_positive": all(
            metrics["years"][str(year)]["stressed_net_usd"] > 0.0
            for year in (2024, 2025)
        ),
        "development_actual_net_strictly_above_v8": metrics["actual_net_usd"]
        > float(gates["development_actual_net_strictly_above_v8"]),
        "development_stressed_net_strictly_above_v8": metrics["stressed_net_usd"]
        > float(gates["development_stressed_net_strictly_above_v8"]),
        "actual_closed_balance_drawdown_pct_max": metrics[
            "actual_closed_balance_drawdown_pct"
        ]
        <= float(gates["actual_closed_balance_drawdown_pct_max"]),
        "normal_trading_day_average_lifecycle_starts_min": metrics[
            "average_starts_per_normal_trading_day"
        ]
        >= float(gates["normal_trading_day_average_lifecycle_starts_min"]),
        "symbol_breadth_min": metrics["symbol_breadth"]
        >= int(gates["symbol_breadth_min"]),
    }


def write_csv_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"refusing empty evidence tape: {path.name}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def ordered_manifest(records: Iterable[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in records:
        line = f"{record['path']}|{record['bytes']}|{record['sha256']}\n"
        digest.update(line.encode("utf-8"))
    return digest.hexdigest().upper()


def atomic_output_directory(name: str) -> tuple[Path, Path]:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    final = ARTIFACT_ROOT / name
    if final.exists():
        raise RuntimeError(f"artifact destination already exists: {final}")
    temporary = Path(tempfile.mkdtemp(prefix=f".{name}-", dir=ARTIFACT_ROOT))
    return temporary, final


def finalize_output_directory(temporary: Path, final: Path) -> None:
    if final.exists():
        raise RuntimeError(f"artifact destination appeared during run: {final}")
    os.replace(temporary, final)


def run_development(
    contract: dict[str, Any], freeze: dict[str, Any]
) -> dict[str, Any]:
    development_start = pd.Timestamp("2024-01-01T00:00:00")
    development_end = pd.Timestamp("2026-01-01T00:00:00")
    frame, construction = load_common_m15(development_end)
    normal_days, day_distribution = normal_trading_days(
        frame, development_start, development_end
    )
    books, trades, state_rows, diagnostics = run_online_roles(
        frame,
        development_start,
        development_end,
        ROLE_HALFLIVES.keys(),
    )
    role_results: dict[str, Any] = {}
    passers: list[str] = []
    for role in ROLE_HALFLIVES:
        role_trades = [trade for trade in trades if trade["role"] == role]
        metrics = metrics_from_trades(role_trades, normal_days, (2024, 2025))
        gate_results = development_gates(metrics, contract)
        complete_pass = all(gate_results.values())
        if complete_pass:
            passers.append(role)
        role_results[role] = {
            "half_life_matured_observations": ROLE_HALFLIVES[role],
            "metrics": metrics,
            "gates": gate_results,
            "complete_pass": complete_pass,
            "book_counters": diagnostics["role_book_counters"][role],
            "final_actual_balance_crosscheck": books[role].actual_balance,
            "final_stressed_balance_crosscheck": books[role].stressed_balance,
        }
    passers.sort(
        key=lambda role: (
            -role_results[role]["metrics"]["stressed_net_usd"],
            role_results[role]["metrics"]["actual_closed_balance_drawdown_pct"],
            -min(
                role_results[role]["metrics"]["years"][str(year)][
                    "stressed_net_usd"
                ]
                for year in (2024, 2025)
            ),
        )
    )
    selected_role = passers[0] if passers else None
    temporary, final = atomic_output_directory("development")
    try:
        state_path = temporary / "expert-state-tape.csv"
        trade_path = temporary / "trade-tape.csv"
        write_csv_rows(state_path, state_rows)
        if trades:
            write_csv_rows(trade_path, trades)
        else:
            with trade_path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(
                    "role,sequence,entry_time_epoch,entry_time,exit_time_epoch,"
                    "exit_time,expert,symbol,horizon,mode,direction,online_score_R,"
                    "matured_observations,atr_price,volume_lots,planned_risk_usd,"
                    "entry_price,exit_price,exit_reason,actual_pnl_usd,"
                    "extra_stress_cost_usd,stressed_pnl_usd,"
                    "actual_balance_before_usd,actual_balance_after_usd,"
                    "stressed_balance_before_usd,stressed_balance_after_usd\n"
                )
        state_record = file_record(state_path, final / state_path.name)
        trade_record = file_record(trade_path, final / trade_path.name)
        result = {
            "schema": (
                "zeta-next-independent-cross-index-m15-online-expert-adapter-"
                "challenge-v1-development-result"
            ),
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": (
                "VALID_DEVELOPMENT_COMPLETE_PASSER_SELECTED_CONFIRMATION_NOT_YET_AUTHORIZED"
                if selected_role
                else "VALID_DEVELOPMENT_NO_COMPLETE_ROLE_FAMILY_CLOSE_BEFORE_CONFIRMATION_EA_MT5"
            ),
            "authorities": {
                "contract": file_record(CONTRACT_PATH),
                "declaration": file_record(DECLARATION_PATH),
                "implementation_freeze": file_record(FREEZE_PATH),
                "adapter": file_record(Path(__file__).resolve()),
            },
            "construction": construction,
            "development": {
                "period": "2024-01-01T00:00:00/2026-01-01T00:00:00",
                "initial_deposit_usd": INITIAL_BALANCE_USD,
                "normal_trading_days": normal_days,
                "day_distribution": day_distribution,
                "diagnostics": diagnostics,
                "roles": role_results,
                "complete_passer_count": len(passers),
                "complete_passers_ranked": passers,
                "selected_role": selected_role,
            },
            "raw_evidence": {
                "expert_state_tape": state_record,
                "trade_tape": trade_record,
                "ordered_two_tape_manifest_sha256": ordered_manifest(
                    (state_record, trade_record)
                ),
            },
            "attestation": {
                "one_complete_development_process": True,
                "locked_confirmation_rows_used": 0,
                "candidate_ea_source_files": 0,
                "candidate_mt5_paths": 0,
                "native_v8_victory_claimed": False,
                "live_changed": False,
            },
            "next_authorized_action": (
                "write and commit one durable development authority selecting the unchanged role before locked confirmation"
                if selected_role
                else "write the durable adverse result and family closure; do not open locked confirmation, EA, or MT5"
            ),
        }
        result_path = temporary / "result.json"
        write_json(result_path, result)
        finalize_output_directory(temporary, final)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return load_json(final / "result.json")


def verify_development_evidence() -> tuple[dict[str, Any], dict[str, Any]]:
    if not DEVELOPMENT_EVIDENCE_PATH.is_file():
        raise RuntimeError("durable development evidence is absent")
    evidence = load_json(DEVELOPMENT_EVIDENCE_PATH)
    if evidence.get("status") != (
        "VALID_DEVELOPMENT_COMPLETE_PASSER_SELECTED_CONFIRMATION_AUTHORIZED"
    ):
        raise RuntimeError("durable development evidence does not authorize confirmation")
    raw_record = evidence.get("raw_development_result")
    if not isinstance(raw_record, dict):
        raise RuntimeError("durable development evidence lacks raw result authority")
    verify_file_record(raw_record)
    raw = load_json(PROJECT_ROOT / raw_record["path"])
    selected = evidence.get("selected_role")
    if selected not in ROLE_HALFLIVES:
        raise RuntimeError("invalid selected role in durable development evidence")
    if raw["development"]["selected_role"] != selected:
        raise RuntimeError("selected role mismatch between durable and raw evidence")
    if not raw["development"]["roles"][selected]["complete_pass"]:
        raise RuntimeError("selected development role is not a complete passer")
    return evidence, raw


def comparable_metrics_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    keys = (
        "starts",
        "normal_trading_days",
        "actual_net_usd",
        "stressed_net_usd",
        "actual_closed_balance_drawdown_usd",
        "actual_closed_balance_drawdown_pct",
        "stressed_closed_balance_drawdown_usd",
        "stressed_closed_balance_drawdown_pct",
        "symbol_breadth",
    )
    for key in keys:
        if isinstance(left[key], float) or isinstance(right[key], float):
            if not math.isclose(float(left[key]), float(right[key]), rel_tol=0.0, abs_tol=1e-10):
                return False
        elif left[key] != right[key]:
            return False
    return left["years"] == right["years"] and left["symbols"] == right["symbols"]


def run_confirmation(
    contract: dict[str, Any], freeze: dict[str, Any]
) -> dict[str, Any]:
    development_evidence, raw_development = verify_development_evidence()
    selected_role = str(development_evidence["selected_role"])
    trade_start = pd.Timestamp("2024-01-01T00:00:00")
    development_end = pd.Timestamp("2026-01-01T00:00:00")
    confirmation_end = pd.Timestamp("2026-08-01T00:00:00")
    frame, construction = load_common_m15(confirmation_end)
    _, trades, state_rows, diagnostics = run_online_roles(
        frame, trade_start, confirmation_end, (selected_role,)
    )
    development_trades = [
        trade
        for trade in trades
        if pd.Timestamp(trade["entry_time"]) < development_end
    ]
    confirmation_trades = [
        trade
        for trade in trades
        if pd.Timestamp(trade["entry_time"]) >= development_end
    ]
    development_days, _ = normal_trading_days(frame, trade_start, development_end)
    confirmation_days, confirmation_distribution = normal_trading_days(
        frame, development_end, confirmation_end
    )
    whole_days, whole_distribution = normal_trading_days(
        frame, trade_start, confirmation_end
    )
    reproduced_development = metrics_from_trades(
        development_trades, development_days, (2024, 2025)
    )
    original_development = raw_development["development"]["roles"][selected_role][
        "metrics"
    ]
    if not comparable_metrics_equal(reproduced_development, original_development):
        raise RuntimeError("development metrics did not reproduce before confirmation")
    confirmation_metrics = metrics_from_trades(
        confirmation_trades, confirmation_days, (2026,)
    )
    whole_metrics = metrics_from_trades(trades, whole_days, (2024, 2025, 2026))
    challenge = contract["exact_v8_challenge"]
    recovery = whole_metrics["robust_recovery_proxy"]
    proxy_gates = {
        "confirmation_actual_positive": confirmation_metrics["actual_net_usd"] > 0.0,
        "confirmation_stressed_positive": confirmation_metrics["stressed_net_usd"] > 0.0,
        "whole_actual_net_strictly_above_v8": whole_metrics["actual_net_usd"]
        > float(challenge["actual_net_usd_strictly_above"]),
        "whole_stressed_net_strictly_above_v8": whole_metrics["stressed_net_usd"]
        > float(challenge["doubled_cost_stressed_net_usd_strictly_above"]),
        "closed_balance_drawdown_proxy_at_or_below_native_v8_line": whole_metrics[
            "actual_closed_balance_drawdown_pct"
        ]
        <= float(challenge["native_relative_equity_drawdown_pct_at_or_below"]),
        "robust_recovery_proxy_strictly_above_v8": recovery is not None
        and recovery > float(challenge["robust_recovery_strictly_above"]),
        "each_calendar_epoch_actual_and_stressed_positive": all(
            whole_metrics["years"][str(year)][book] > 0.0
            for year in (2024, 2025, 2026)
            for book in ("actual_net_usd", "stressed_net_usd")
        ),
        "normal_trading_day_average_lifecycle_starts_min": whole_metrics[
            "average_starts_per_normal_trading_day"
        ]
        >= float(challenge["normal_trading_day_average_lifecycle_starts_min"]),
        "symbol_breadth_three": whole_metrics["symbol_breadth"] == 3,
    }
    proxy_survivor = all(proxy_gates.values())
    temporary, final = atomic_output_directory("confirmation")
    try:
        state_path = temporary / "expert-state-tape.csv"
        trade_path = temporary / "trade-tape.csv"
        write_csv_rows(state_path, state_rows)
        write_csv_rows(trade_path, trades)
        state_record = file_record(state_path, final / state_path.name)
        trade_record = file_record(trade_path, final / trade_path.name)
        result = {
            "schema": (
                "zeta-next-independent-cross-index-m15-online-expert-adapter-"
                "challenge-v1-confirmation-result"
            ),
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": (
                "VALID_WHOLE_PROXY_SURVIVOR_EA_IMPLEMENTATION_AUTHORIZED_NOT_NATIVE_VICTORY"
                if proxy_survivor
                else "VALID_LOCKED_CONFIRMATION_OR_WHOLE_PROXY_NONCONFIRMATION_FAMILY_CLOSE"
            ),
            "authorities": {
                "contract": file_record(CONTRACT_PATH),
                "declaration": file_record(DECLARATION_PATH),
                "implementation_freeze": file_record(FREEZE_PATH),
                "adapter": file_record(Path(__file__).resolve()),
                "development_evidence": file_record(DEVELOPMENT_EVIDENCE_PATH),
            },
            "construction": construction,
            "selected_role": selected_role,
            "development_reproduction": {
                "exact": True,
                "metrics": reproduced_development,
            },
            "locked_confirmation": {
                "period": "2026-01-01T00:00:00/2026-08-01T00:00:00",
                "day_distribution": confirmation_distribution,
                "metrics": confirmation_metrics,
            },
            "whole_proxy": {
                "period": "2024-01-01T00:00:00/2026-08-01T00:00:00",
                "day_distribution": whole_distribution,
                "metrics": whole_metrics,
                "gates": proxy_gates,
                "complete_proxy_survivor": proxy_survivor,
                "native_relative_equity_drawdown_still_required": True,
            },
            "diagnostics": diagnostics,
            "raw_evidence": {
                "expert_state_tape": state_record,
                "trade_tape": trade_record,
                "ordered_two_tape_manifest_sha256": ordered_manifest(
                    (state_record, trade_record)
                ),
            },
            "attestation": {
                "maximum_confirmation_roles": 1,
                "confirmation_roles_run": 1,
                "candidate_ea_source_files": 0,
                "candidate_mt5_paths": 0,
                "native_v8_victory_claimed": False,
                "live_changed": False,
            },
            "next_authorized_action": (
                "freeze and implement one self-contained EA for the unchanged adapter role; proxy still cannot claim victory"
                if proxy_survivor
                else "write the durable confirmation result and close before EA or MT5"
            ),
        }
        result_path = temporary / "result.json"
        write_json(result_path, result)
        finalize_output_directory(temporary, final)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return load_json(final / "result.json")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Independent cross-index M15 online-expert adapter"
    )
    parser.add_argument(
        "--mode", choices=("precheck", "development", "confirmation"), required=True
    )
    args = parser.parse_args()
    contract, declaration, freeze = verify_authorities(args.mode)
    if args.mode == "precheck":
        result = structural_precheck(contract)
    elif args.mode == "development":
        if freeze is None:
            raise RuntimeError("development requires implementation freeze")
        result = run_development(contract, freeze)
    else:
        if freeze is None:
            raise RuntimeError("confirmation requires implementation freeze")
        result = run_confirmation(contract, freeze)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=json_default, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
