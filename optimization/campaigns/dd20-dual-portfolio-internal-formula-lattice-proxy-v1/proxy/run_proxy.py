from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from numba import njit, prange
from scipy import stats
from scipy.stats import qmc


FAMILY = "dd20-dual-portfolio-internal-formula-lattice-proxy-v1"
SCRIPT_PATH = Path(__file__).resolve()
CAMPAIGN_ROOT = SCRIPT_PATH.parents[1]
REPOSITORY_ROOT = SCRIPT_PATH.parents[4]
CONTRACT_PATH = CAMPAIGN_ROOT / "config" / "campaign-contract.json"
MARKET_ROOT = (
    REPOSITORY_ROOT / "optimization" / "artifacts" / "raw" / FAMILY / "market"
)
OUTPUT_ROOT = (
    REPOSITORY_ROOT / "optimization" / "artifacts" / "raw" / FAMILY / "output"
)
SELECTION_FREEZE_PATH = OUTPUT_ROOT / "selection-freeze.json"
RESULT_PATH = OUTPUT_ROOT / "proxy-result.json"
POINT_RESULT_PATH = OUTPUT_ROOT / "selection-points.parquet"
DAILY_RESULT_PATH = OUTPUT_ROOT / "selection-daily-stressed.parquet"

CANDIDATE_SELECTION_LEDGER = (
    REPOSITORY_ROOT
    / "optimization"
    / "artifacts"
    / "raw"
    / "dd20-paired-month-stability-mt5-v1"
    / "selection"
    / "ea-files"
    / "research"
    / "research-candidates.csv"
)
CANDIDATE_FORWARD_LEDGER = (
    REPOSITORY_ROOT
    / "optimization"
    / "artifacts"
    / "raw"
    / "dd20-paired-month-stability-mt5-v1"
    / "forward"
    / "ea-files"
    / "research"
    / "research-candidates.csv"
)
CANDIDATE_SELECTION_LIFECYCLE = CANDIDATE_SELECTION_LEDGER.with_name(
    "research-lifecycles.csv"
)
CANDIDATE_FORWARD_LIFECYCLE = CANDIDATE_FORWARD_LEDGER.with_name(
    "research-lifecycles.csv"
)
CONTROL_LIFECYCLE_GLOB = (
    REPOSITORY_ROOT
    / "optimization"
    / "artifacts"
    / "raw"
    / "portfolio-risk-cap-envelope-v1"
    / "completed-search-20260828T054809Z"
    / "agent-output"
)

COMPONENT_NAMES = (
    "RC16_US30_M30",
    "RC4_US30_M30",
    "CROSS_US100_H1",
    "PRESSURE_US30_M30",
    "RETURN_US30_H1",
    "PASSIVE_US100_M15",
)
LEDGER_COMPONENTS = {
    "ZT-M30-US30-RANGE-COMP-61f61deaba": 0,
    "ZT-M30-US30-RANGE-COMP-64efb16616": 1,
    "ZT-H1-US100-CROSS-IN-14b72317b7": 2,
    "ZT-M30-US30-INTRADAY-R-2eb111fc46": 3,
    "ZT-H1-US30-RETURN-I-c870a788ec": 4,
    "ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8": 5,
}

# Resolved parameter matrix columns. This exact order is also recorded in output.
AXIS_ORDER = (
    ("rc16", "compression"),
    ("rc16", "normal_window"),
    ("rc16", "direction_fraction"),
    ("rc16", "threshold"),
    ("rc16", "threshold_log_skew"),
    ("rc16", "mode"),
    ("rc16", "hold_bars"),
    ("rc4", "compression"),
    ("rc4", "normal_window"),
    ("rc4", "direction_fraction"),
    ("rc4", "threshold"),
    ("rc4", "threshold_log_skew"),
    ("rc4", "mode"),
    ("rc4", "hold_bars"),
    ("cross", "scale_window"),
    ("cross", "centering_k"),
    ("cross", "peer_total_beta"),
    ("cross", "us30_peer_share"),
    ("cross", "threshold"),
    ("cross", "threshold_log_skew"),
    ("cross", "mode"),
    ("cross", "hold_bars"),
    ("pressure", "daily_scale_window"),
    ("pressure", "daily_scale_quantile"),
    ("pressure", "location_center"),
    ("pressure", "location_power"),
    ("pressure", "range_power"),
    ("pressure", "threshold"),
    ("pressure", "threshold_log_skew"),
    ("pressure", "mode"),
    ("pressure", "hold_bars"),
    ("return", "lookback"),
    ("return", "scale_window"),
    ("return", "normalization_power"),
    ("return", "centering_k"),
    ("return", "scale_overlap"),
    ("return", "threshold"),
    ("return", "threshold_log_skew"),
    ("return", "mode"),
    ("return", "hold_bars"),
    ("passive", "lookback"),
    ("passive", "scale_window"),
    ("passive", "normalization_power"),
    ("passive", "centering_k"),
    ("passive", "entry_threshold"),
    ("passive", "exit_fraction_of_entry"),
    ("passive", "limit_offset_range_scale"),
    ("passive", "activation_bars"),
    ("passive", "maximum_hold_bars"),
    ("passive", "cooldown_bars"),
    ("passive", "mode"),
    ("arc", "checkpoint_bars"),
    ("arc", "retained_loss_fraction"),
    ("arc", "vote_threshold"),
    ("arc", "ordinal_profile"),
    ("arc", "market_penalty_scale"),
    ("arc", "decision_dynamics_scale"),
    ("arc", "negative_support_penalty_scale"),
    ("arc", "confirmation_pressure_share"),
)

# Parameter column constants used by the compiled economic loop.
(
    RC16_C,
    RC16_N,
    RC16_D,
    RC16_THR,
    RC16_SKEW,
    RC16_MODE,
    RC16_HOLD,
    RC4_C,
    RC4_N,
    RC4_D,
    RC4_THR,
    RC4_SKEW,
    RC4_MODE,
    RC4_HOLD,
    CROSS_N,
    CROSS_CENTER,
    CROSS_BETA,
    CROSS_SHARE,
    CROSS_THR,
    CROSS_SKEW,
    CROSS_MODE,
    CROSS_HOLD,
    PRESSURE_N,
    PRESSURE_QNT,
    PRESSURE_CENTER,
    PRESSURE_LOC_POWER,
    PRESSURE_RANGE_POWER,
    PRESSURE_THR,
    PRESSURE_SKEW,
    PRESSURE_MODE,
    PRESSURE_HOLD,
    RETURN_L,
    RETURN_N,
    RETURN_POWER,
    RETURN_CENTER,
    RETURN_OVERLAP,
    RETURN_THR,
    RETURN_SKEW,
    RETURN_MODE,
    RETURN_HOLD,
    PASSIVE_L,
    PASSIVE_N,
    PASSIVE_POWER,
    PASSIVE_CENTER,
    PASSIVE_ENTRY,
    PASSIVE_EXIT_FRAC,
    PASSIVE_OFFSET,
    PASSIVE_ACTIVATION,
    PASSIVE_HOLD,
    PASSIVE_COOLDOWN,
    PASSIVE_MODE,
    ARC_CHECKPOINT,
    ARC_RETAIN,
    ARC_VOTE,
    ARC_PROFILE,
    ARC_MARKET_PENALTY,
    ARC_DECISION_DYNAMICS,
    ARC_NEGATIVE_PENALTY,
    ARC_CONFIRM_SHARE,
) = range(len(AXIS_ORDER))

BLOCK_SIZE = 64
POINT_VALUE_PER_PRICE_PER_LOT = 1.0
PRICE_TICK = 0.01


@dataclass(frozen=True)
class Rates:
    time: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    spread: np.ndarray


@dataclass(frozen=True)
class Basis:
    us30_m1: Rates
    us100_m1: Rates
    us30_m30: Rates
    us30_h1: Rates
    us30_d1: Rates
    us100_m15: Rates
    us100_h1: Rates
    us500_h1: Rates
    rc16_ratio: np.ndarray
    rc16_sign: np.ndarray
    rc4_ratio: np.ndarray
    rc4_sign: np.ndarray
    cross_current: np.ndarray
    cross_mean: np.ndarray
    cross_std: np.ndarray
    pressure_fraction: np.ndarray
    pressure_running_log_range: np.ndarray
    pressure_scale: np.ndarray
    return_impulse: np.ndarray
    return_mean: np.ndarray
    return_std: np.ndarray
    passive_mean: np.ndarray
    passive_std: np.ndarray
    passive_range: np.ndarray
    arc_feature: np.ndarray
    arc_ret1_z: np.ndarray
    arc_efficiency: np.ndarray
    arc_close_location: np.ndarray
    arc_vol_ratio: np.ndarray
    arc_range_median: np.ndarray
    arc_pressure: np.ndarray
    us30_low_block: np.ndarray
    us30_high_ask: np.ndarray
    us30_high_ask_block: np.ndarray
    us100_low_block: np.ndarray
    us100_low_ask: np.ndarray
    us100_low_ask_block: np.ndarray
    us100_high_ask: np.ndarray
    us100_high_ask_block: np.ndarray
    us100_high_block: np.ndarray


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def relative(path: Path) -> str:
    return str(path.relative_to(REPOSITORY_ROOT)).replace("\\", "/")


def load_contract() -> dict[str, Any]:
    payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if payload["campaign"] != FAMILY:
        raise RuntimeError("campaign identity mismatch")
    receipt_path = MARKET_ROOT / "acquisition-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt["contract_sha256"] != sha256(CONTRACT_PATH):
        raise RuntimeError("market receipt does not match frozen contract")
    if receipt["account_position_order_deal_queries"] != 0:
        raise RuntimeError("market acquisition exceeded its allowed API boundary")
    for item in receipt["series"]:
        path = REPOSITORY_ROOT / item["path"]
        if path.stat().st_size != int(item["bytes"]) or sha256(path) != item["sha256"]:
            raise RuntimeError(f"market snapshot mismatch: {item['id']}")
    return payload


def load_rates(symbol: str, timeframe: str) -> Rates:
    frame = pd.read_parquet(MARKET_ROOT / f"{symbol}_{timeframe}.parquet")
    return Rates(
        time=frame["time"].to_numpy(dtype=np.int64),
        open=frame["open"].to_numpy(dtype=np.float64),
        high=frame["high"].to_numpy(dtype=np.float64),
        low=frame["low"].to_numpy(dtype=np.float64),
        close=frame["close"].to_numpy(dtype=np.float64),
        spread=frame["spread"].to_numpy(dtype=np.float64),
    )


def rolling_range(high: np.ndarray, low: np.ndarray, window: int) -> np.ndarray:
    highs = pd.Series(high).rolling(window, min_periods=window).max().to_numpy()
    lows = pd.Series(low).rolling(window, min_periods=window).min().to_numpy()
    result = np.full(len(high), np.nan, dtype=np.float64)
    valid = np.isfinite(highs) & np.isfinite(lows) & (lows > 0.0) & (highs >= lows)
    result[valid] = np.log(highs[valid] / lows[valid])
    return result


def positive_round(value: float) -> int:
    return int(math.floor(value + 0.5 + 1.0e-12))


def build_rc_basis(
    rates: Rates, compression_levels: list[int], normal_levels: list[int], fractions: list[float]
) -> tuple[np.ndarray, np.ndarray]:
    ratios = np.full(
        (len(compression_levels), len(normal_levels), len(rates.time)),
        np.nan,
        dtype=np.float64,
    )
    signs = np.zeros(
        (len(compression_levels), len(fractions), len(rates.time)), dtype=np.float64
    )
    for c_index, compression in enumerate(compression_levels):
        current = rolling_range(rates.high, rates.low, compression)
        for n_index, normal in enumerate(normal_levels):
            prior = (
                pd.Series(current)
                .rolling(normal, min_periods=normal)
                .median()
                .shift(1)
                .to_numpy()
            )
            valid = np.isfinite(current) & (current > 0.0) & np.isfinite(prior)
            ratios[c_index, n_index, valid] = prior[valid] / current[valid]
        for d_index, fraction in enumerate(fractions):
            lookback = max(1, positive_round(compression * fraction))
            direction = np.zeros(len(rates.time), dtype=np.float64)
            latest = np.arange(lookback, len(rates.time))
            delta = np.log(
                rates.close[latest] / rates.close[latest - lookback]
            )
            direction[latest] = np.sign(delta)
            signs[c_index, d_index] = direction
    # A formula evaluated at current bar i consumes completed bar i-1.
    return np.roll(ratios, 1, axis=2), np.roll(signs, 1, axis=2)


def aligned_close(source: Rates, target_times: np.ndarray) -> np.ndarray:
    series = pd.Series(source.close, index=source.time)
    return series.reindex(target_times).to_numpy(dtype=np.float64)


def build_cross_basis(
    own: Rates,
    us30: Rates,
    us500: Rates,
    beta_levels: list[float],
    share_levels: list[float],
    scale_levels: list[int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    peer_count = len(beta_levels) * len(share_levels)
    current = np.full((peer_count, len(own.time)), np.nan)
    means = np.full((peer_count, len(scale_levels), len(own.time)), np.nan)
    stds = np.full_like(means, np.nan)
    maximum_window = max(scale_levels)
    evaluation_indexes = np.flatnonzero(schedule_mask(own.time, 17, 0))
    for current_index in evaluation_indexes:
        latest_own = current_index - 1
        if latest_own < maximum_window + 1:
            continue
        expected_latest = own.time[latest_own]
        latest_30 = int(np.searchsorted(us30.time, expected_latest))
        latest_500 = int(np.searchsorted(us500.time, expected_latest))
        if (
            latest_30 >= len(us30.time)
            or latest_500 >= len(us500.time)
            or us30.time[latest_30] != expected_latest
            or us500.time[latest_500] != expected_latest
            or latest_30 < maximum_window + 1
            or latest_500 < maximum_window + 1
        ):
            continue
        own_closes = own.close[latest_own - maximum_window - 1 : latest_own + 1]
        close30 = us30.close[latest_30 - maximum_window - 1 : latest_30 + 1]
        close500 = us500.close[latest_500 - maximum_window - 1 : latest_500 + 1]
        own_returns = np.log(own_closes[1:] / own_closes[:-1])
        returns30 = np.log(close30[1:] / close30[:-1])
        returns500 = np.log(close500[1:] / close500[:-1])
        peer_index = 0
        for beta in beta_levels:
            for share in share_levels:
                relative = own_returns - beta * (
                    share * returns30 + (1.0 - share) * returns500
                )
                current[peer_index, current_index] = relative[-1]
                for n_index, window in enumerate(scale_levels):
                    prior = relative[-window - 1 : -1]
                    means[peer_index, n_index, current_index] = float(np.mean(prior))
                    stds[peer_index, n_index, current_index] = float(
                        np.std(prior, ddof=1)
                    )
                peer_index += 1
    return current, means, stds


def session_state(rates: Rates) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    fraction = np.full(len(rates.time), np.nan)
    running_log_range = np.full(len(rates.time), np.nan)
    latest_close = np.full(len(rates.time), np.nan)
    day = -1
    running_high = -np.inf
    running_low = np.inf
    previous_close = np.nan
    for index, epoch in enumerate(rates.time):
        current_day = int(epoch // 86400)
        if current_day != day:
            day = current_day
            running_high = -np.inf
            running_low = np.inf
            previous_close = np.nan
        if np.isfinite(previous_close) and running_high > running_low > 0.0:
            fraction[index] = (previous_close - running_low) / (running_high - running_low)
            running_log_range[index] = math.log(running_high / running_low)
            latest_close[index] = previous_close
        running_high = max(running_high, rates.high[index])
        running_low = min(running_low, rates.low[index])
        previous_close = rates.close[index]
    return fraction, running_log_range, latest_close


def build_pressure_basis(
    m30: Rates, d1: Rates, windows: list[int], quantiles: list[float]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    fraction, running_log_range, _ = session_state(m30)
    daily_ranges = np.log(d1.high / d1.low)
    d1_day = d1.time // 86400
    m30_day = m30.time // 86400
    scales = np.full((len(windows), len(quantiles), len(m30.time)), np.nan)
    for w_index, window in enumerate(windows):
        source = pd.Series(daily_ranges)
        for q_index, quantile in enumerate(quantiles):
            daily_scale = (
                source.rolling(window, min_periods=window)
                .quantile(quantile, interpolation="linear")
                .shift(1)
                .to_numpy()
            )
            mapping = pd.Series(daily_scale, index=d1_day)
            scales[w_index, q_index] = mapping.reindex(m30_day).to_numpy(dtype=float)
    return fraction, running_log_range, scales


def build_return_basis(
    rates: Rates, lookbacks: list[int], windows: list[int]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    returns = np.full(len(rates.time), np.nan)
    returns[1:] = np.log(rates.close[1:] / rates.close[:-1])
    impulse = np.full((len(lookbacks), len(rates.time)), np.nan)
    means = np.full(
        (len(lookbacks), len(windows), 2, len(rates.time)), np.nan
    )
    stds = np.full_like(means, np.nan)
    rolling_stats: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    source = pd.Series(returns)
    for window in windows:
        rolling_stats[window] = (
            source.rolling(window, min_periods=window).mean().to_numpy(),
            source.rolling(window, min_periods=window).std(ddof=1).to_numpy(),
        )
    for l_index, lookback in enumerate(lookbacks):
        indexes = np.arange(lookback + 1, len(rates.time))
        # Current bar i consumes completed close i-1.
        impulse[l_index, indexes] = np.log(
            rates.close[indexes - 1] / rates.close[indexes - 1 - lookback]
        )
        for n_index, window in enumerate(windows):
            roll_mean, roll_std = rolling_stats[window]
            baseline_source = indexes - 2
            pre_impulse_source = indexes - lookback - 1
            means[l_index, n_index, 0, indexes] = roll_mean[baseline_source]
            stds[l_index, n_index, 0, indexes] = roll_std[baseline_source]
            valid = pre_impulse_source >= 0
            target = indexes[valid]
            means[l_index, n_index, 1, target] = roll_mean[pre_impulse_source[valid]]
            stds[l_index, n_index, 1, target] = roll_std[pre_impulse_source[valid]]
    return impulse, means, stds


def build_passive_basis(
    rates: Rates, windows: list[int]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    returns = np.full(len(rates.time), np.nan)
    returns[1:] = np.log(rates.close[1:] / rates.close[:-1])
    means = np.full((len(windows), len(rates.time)), np.nan)
    stds = np.full_like(means, np.nan)
    ranges = rates.high - rates.low
    range_scale = np.full_like(means, np.nan)
    return_series = pd.Series(returns)
    range_series = pd.Series(ranges)
    for index, window in enumerate(windows):
        # Current bar i consumes scale returns through i-2 and ranges through i-2.
        means[index] = (
            return_series.rolling(window, min_periods=window).mean().shift(2).to_numpy()
        )
        stds[index] = (
            return_series.rolling(window, min_periods=window).std(ddof=1).shift(2).to_numpy()
        )
        range_scale[index] = (
            range_series.rolling(window, min_periods=window).median().shift(2).to_numpy()
        )
    return means, stds, range_scale


def block_min(values: np.ndarray) -> np.ndarray:
    blocks = math.ceil(len(values) / BLOCK_SIZE)
    result = np.full(blocks, np.inf)
    for block in range(blocks):
        start = block * BLOCK_SIZE
        result[block] = np.nanmin(values[start : start + BLOCK_SIZE])
    return result


def block_max(values: np.ndarray) -> np.ndarray:
    blocks = math.ceil(len(values) / BLOCK_SIZE)
    result = np.full(blocks, -np.inf)
    for block in range(blocks):
        start = block * BLOCK_SIZE
        result[block] = np.nanmax(values[start : start + BLOCK_SIZE])
    return result


def build_arc_basis(m30: Rates, pressure_scale: np.ndarray) -> tuple[np.ndarray, ...]:
    rc_ratio, rc_sign = build_rc_basis(m30, [4], [96], [0.5])
    feature = rc_ratio[0, 0] * rc_sign[0, 0]
    returns = np.full(len(m30.time), np.nan)
    returns[1:] = np.log(m30.close[1:] / m30.close[:-1])
    return_series = pd.Series(returns)
    prior_std = return_series.rolling(48, min_periods=48).std(ddof=1).shift(1).to_numpy()
    fast_std = return_series.rolling(4, min_periods=4).std(ddof=1).to_numpy()
    # Baseline slow window excludes the latest return.
    slow_std = return_series.rolling(24, min_periods=24).std(ddof=1).shift(1).to_numpy()
    ret1_z = np.full(len(m30.time), np.nan)
    efficiency = np.full(len(m30.time), np.nan)
    close_location = np.full(len(m30.time), np.nan)
    vol_ratio = np.full(len(m30.time), np.nan)
    range_median = (
        pd.Series(m30.high - m30.low).rolling(96, min_periods=96).median().shift(1).to_numpy()
    )
    for current in range(98, len(m30.time)):
        latest = current - 1
        if prior_std[latest] > 0.0 and slow_std[latest] >= 0.0:
            ret1_z[current] = returns[latest] / prior_std[latest]
            path = np.abs(returns[latest - 3 : latest + 1]).sum()
            efficiency[current] = abs(
                math.log(m30.close[latest] / m30.close[latest - 4])
            ) / (path + 1.0e-12)
            bar_range = m30.high[latest] - m30.low[latest]
            if bar_range > 0.0:
                close_location[current] = 2.0 * (
                    (m30.close[latest] - m30.low[latest]) / bar_range - 0.5
                )
            vol_ratio[current] = fast_std[latest] / (slow_std[latest] + 1.0e-12)
    fraction, running_log_range, _ = session_state(m30)
    scale20 = pressure_scale[3, 1]
    pressure = 2.0 * (fraction - 0.5) * running_log_range / scale20
    return (
        feature,
        ret1_z,
        efficiency,
        close_location,
        vol_ratio,
        np.roll(range_median, 1),
        pressure,
    )


def build_basis(contract: dict[str, Any]) -> Basis:
    axes = contract["parameter_axes"]
    us30_m1 = load_rates("US30", "M1")
    us30_m30 = load_rates("US30", "M30")
    us30_h1 = load_rates("US30", "H1")
    us30_d1 = load_rates("US30", "D1")
    us100_m1 = load_rates("US100", "M1")
    us100_m15 = load_rates("US100", "M15")
    us100_h1 = load_rates("US100", "H1")
    us500_h1 = load_rates("US500", "H1")
    rc16_ratio, rc16_sign = build_rc_basis(
        us30_m30,
        axes["rc16"]["compression"],
        axes["rc16"]["normal_window"],
        axes["rc16"]["direction_fraction"],
    )
    rc4_ratio, rc4_sign = build_rc_basis(
        us30_m30,
        axes["rc4"]["compression"],
        axes["rc4"]["normal_window"],
        axes["rc4"]["direction_fraction"],
    )
    cross_current, cross_mean, cross_std = build_cross_basis(
        us100_h1,
        us30_h1,
        us500_h1,
        axes["cross"]["peer_total_beta"],
        axes["cross"]["us30_peer_share"],
        axes["cross"]["scale_window"],
    )
    pressure_fraction, pressure_running, pressure_scale = build_pressure_basis(
        us30_m30,
        us30_d1,
        axes["pressure"]["daily_scale_window"],
        axes["pressure"]["daily_scale_quantile"],
    )
    return_impulse, return_mean, return_std = build_return_basis(
        us30_h1,
        axes["return"]["lookback"],
        axes["return"]["scale_window"],
    )
    passive_mean, passive_std, passive_range = build_passive_basis(
        us100_m15, axes["passive"]["scale_window"]
    )
    arc = build_arc_basis(us30_m30, pressure_scale)
    us30_spread = us30_m1.spread * 0.01
    us100_spread = us100_m1.spread * 0.01
    us30_high_ask = us30_m1.high + us30_spread
    us100_low_ask = us100_m1.low + us100_spread
    us100_high_ask = us100_m1.high + us100_spread
    return Basis(
        us30_m1,
        us100_m1,
        us30_m30,
        us30_h1,
        us30_d1,
        us100_m15,
        us100_h1,
        us500_h1,
        rc16_ratio,
        rc16_sign,
        rc4_ratio,
        rc4_sign,
        cross_current,
        cross_mean,
        cross_std,
        pressure_fraction,
        pressure_running,
        pressure_scale,
        return_impulse,
        return_mean,
        return_std,
        passive_mean,
        passive_std,
        passive_range,
        *arc,
        block_min(us30_m1.low),
        us30_high_ask,
        block_max(us30_high_ask),
        block_min(us100_m1.low),
        us100_low_ask,
        block_min(us100_low_ask),
        us100_high_ask,
        block_max(us100_high_ask),
        block_max(us100_m1.high),
    )


def canonical_payload(level_row: np.ndarray, contract: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, dict[str, Any]] = {}
    for column, (family, name) in enumerate(AXIS_ORDER):
        value = contract["parameter_axes"][family][name][int(level_row[column])]
        payload.setdefault(family, {})[name] = value
    return payload


def baseline_level_row(contract: dict[str, Any]) -> np.ndarray:
    family_offsets: dict[str, int] = {}
    result = np.zeros(len(AXIS_ORDER), dtype=np.int16)
    for column, (family, name) in enumerate(AXIS_ORDER):
        offset = family_offsets.get(family, 0)
        expected = contract["baseline_point"][family][offset]
        levels = contract["parameter_axes"][family][name]
        try:
            result[column] = levels.index(expected)
        except ValueError as exc:
            raise RuntimeError(f"baseline value absent from {family}.{name}") from exc
        family_offsets[family] = offset + 1
    return result


def add_unique_point(
    row: np.ndarray, rows: list[np.ndarray], seen: set[bytes]
) -> bool:
    key = row.astype(np.int16, copy=False).tobytes()
    if key in seen:
        return False
    seen.add(key)
    rows.append(row.astype(np.int16, copy=True))
    return True


def generate_broad_points(contract: dict[str, Any]) -> np.ndarray:
    level_counts = np.asarray(
        [len(contract["parameter_axes"][family][name]) for family, name in AXIS_ORDER],
        dtype=np.int16,
    )
    baseline = baseline_level_row(contract)
    rows: list[np.ndarray] = []
    seen: set[bytes] = set()
    add_unique_point(baseline, rows, seen)
    add_unique_point((level_counts - 1) // 2, rows, seen)
    for column, count in enumerate(level_counts):
        for value in range(int(count)):
            row = baseline.copy()
            row[column] = value
            add_unique_point(row, rows, seen)
    add_unique_point(np.zeros_like(baseline), rows, seen)
    add_unique_point(level_counts - 1, rows, seen)

    mode_columns = (RC16_MODE, RC4_MODE, CROSS_MODE, PRESSURE_MODE, RETURN_MODE)
    reversal_index = (2, 1, 1, 1, 1)
    continuation_index = (1, 0, 0, 0, 2)
    for mask in range(32):
        row = baseline.copy()
        for bit, column in enumerate(mode_columns):
            row[column] = reversal_index[bit] if mask & (1 << bit) else continuation_index[bit]
        add_unique_point(row, rows, seen)

    family_columns = {
        "rc16": range(RC16_C, RC16_HOLD + 1),
        "rc4": range(RC4_C, RC4_HOLD + 1),
        "cross": range(CROSS_N, CROSS_HOLD + 1),
        "pressure": range(PRESSURE_N, PRESSURE_HOLD + 1),
        "return": range(RETURN_L, RETURN_HOLD + 1),
        "passive": range(PASSIVE_L, PASSIVE_MODE + 1),
        "arc": range(ARC_CHECKPOINT, ARC_CONFIRM_SHARE + 1),
    }
    for columns in family_columns.values():
        for edge in (0, 1):
            row = baseline.copy()
            for column in columns:
                row[column] = 0 if edge == 0 else level_counts[column] - 1
            add_unique_point(row, rows, seen)
    skew_columns = (RC16_SKEW, RC4_SKEW, CROSS_SKEW, PRESSURE_SKEW, RETURN_SKEW)
    for mask in range(32):
        row = baseline.copy()
        for bit, column in enumerate(skew_columns):
            row[column] = 0 if mask & (1 << bit) else level_counts[column] - 1
        add_unique_point(row, rows, seen)

    sobol = qmc.Sobol(d=len(AXIS_ORDER), scramble=False)
    samples = sobol.random_base2(m=14)
    target = int(contract["point_design"]["broad_target_unique_points"])
    for sample in samples:
        row = np.minimum((sample * level_counts).astype(np.int16), level_counts - 1)
        add_unique_point(row, rows, seen)
        if len(rows) >= target:
            break
    if len(rows) != target:
        raise RuntimeError(f"broad point generation stopped at {len(rows)}")
    return np.stack(rows)


def resolve_points(
    levels: np.ndarray, contract: dict[str, Any]
) -> tuple[np.ndarray, list[str], list[str]]:
    values = np.zeros_like(levels, dtype=np.float64)
    point_ids: list[str] = []
    payloads: list[str] = []
    for row_index, row in enumerate(levels):
        payload = canonical_payload(row, contract)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        point_ids.append(hashlib.sha256(canonical.encode("utf-8")).hexdigest().upper()[:20])
        payloads.append(canonical)
        for column, (family, name) in enumerate(AXIS_ORDER):
            raw = contract["parameter_axes"][family][name][int(row[column])]
            values[row_index, column] = float(row[column]) if isinstance(raw, str) else float(raw)
    return values, point_ids, payloads


def observed_fixed_holiday(year: int, month: int, day: int) -> date:
    value = date(year, month, day)
    if value.weekday() == 5:
        return value - timedelta(days=1)
    if value.weekday() == 6:
        return value + timedelta(days=1)
    return value


def nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(
        days=(weekday - first.weekday()) % 7 + 7 * (occurrence - 1)
    )


def last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        value = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        value = date(year, month + 1, 1) - timedelta(days=1)
    return value - timedelta(days=(value.weekday() - weekday) % 7)


def easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def closure_dates(first_year: int = 2022, last_year: int = 2028) -> set[date]:
    values: set[date] = {date(2025, 1, 9)}
    for year in range(first_year, last_year + 1):
        thanksgiving = nth_weekday(year, 11, 3, 4)
        values.update(
            {
                observed_fixed_holiday(year, 1, 1),
                nth_weekday(year, 1, 0, 3),
                nth_weekday(year, 2, 0, 3),
                easter_sunday(year) - timedelta(days=2),
                last_weekday(year, 5, 0),
                observed_fixed_holiday(year, 6, 19),
                observed_fixed_holiday(year, 7, 4),
                nth_weekday(year, 9, 0, 1),
                thanksgiving,
                observed_fixed_holiday(year, 12, 25),
                thanksgiving + timedelta(days=1),
            }
        )
        july_third = date(year, 7, 3)
        christmas_eve = date(year, 12, 24)
        if july_third.weekday() < 5:
            values.add(july_third)
        if christmas_eve.weekday() < 5:
            values.add(christmas_eve)
    return values


def epoch_to_date(epoch: int) -> date:
    return datetime.fromtimestamp(int(epoch), timezone.utc).date()


def baseline_features_at(
    component: int,
    bar_index: int,
    basis: Basis,
    baseline_levels: np.ndarray,
    baseline_values: np.ndarray,
) -> float:
    if component == 0:
        return float(
            basis.rc16_ratio[
                int(baseline_levels[RC16_C]), int(baseline_levels[RC16_N]), bar_index
            ]
            * basis.rc16_sign[
                int(baseline_levels[RC16_C]), int(baseline_levels[RC16_D]), bar_index
            ]
        )
    if component == 1:
        return float(
            basis.rc4_ratio[
                int(baseline_levels[RC4_C]), int(baseline_levels[RC4_N]), bar_index
            ]
            * basis.rc4_sign[
                int(baseline_levels[RC4_C]), int(baseline_levels[RC4_D]), bar_index
            ]
        )
    if component == 2:
        peer_index = int(baseline_levels[CROSS_BETA]) * 5 + int(
            baseline_levels[CROSS_SHARE]
        )
        current = basis.cross_current[peer_index, bar_index]
        mean = basis.cross_mean[
            peer_index, int(baseline_levels[CROSS_N]), bar_index
        ]
        standard = basis.cross_std[
            peer_index, int(baseline_levels[CROSS_N]), bar_index
        ]
        if standard <= 0.0:
            return math.nan
        return float(
            (current - float(baseline_values[CROSS_CENTER]) * mean) / standard
        )
    if component == 3:
        fraction = basis.pressure_fraction[bar_index]
        running = basis.pressure_running_log_range[bar_index]
        scale = basis.pressure_scale[
            int(baseline_levels[PRESSURE_N]),
            int(baseline_levels[PRESSURE_QNT]),
            bar_index,
        ]
        location = 2.0 * (
            fraction - float(baseline_values[PRESSURE_CENTER])
        )
        return float(
            math.copysign(
                abs(location) ** float(baseline_values[PRESSURE_LOC_POWER]),
                location,
            )
            * (running / scale) ** float(baseline_values[PRESSURE_RANGE_POWER])
        )
    if component == 4:
        lookback = int(baseline_levels[RETURN_L])
        scale_index = int(baseline_levels[RETURN_N])
        overlap = int(baseline_levels[RETURN_OVERLAP])
        impulse = basis.return_impulse[lookback, bar_index]
        mean = basis.return_mean[lookback, scale_index, overlap, bar_index]
        standard = basis.return_std[lookback, scale_index, overlap, bar_index]
        lookback_value = float(baseline_values[RETURN_L])
        if standard <= 0.0:
            return math.nan
        return float(
            (
                impulse
                - float(baseline_values[RETURN_CENTER]) * mean * lookback_value
            )
            / (
                standard
                * lookback_value ** float(baseline_values[RETURN_POWER])
            )
        )
    return math.nan


def bar_index_for_component(component: int, epoch: int, basis: Basis) -> int:
    times = (
        basis.us30_m30.time
        if component in (0, 1, 3)
        else basis.us100_h1.time
        if component == 2
        else basis.us30_h1.time
        if component == 4
        else basis.us100_m15.time
    )
    index = int(np.searchsorted(times, epoch))
    return index if index < len(times) and int(times[index]) == epoch else -1


def feature_anchor(contract: dict[str, Any], basis: Basis) -> dict[str, Any]:
    baseline = baseline_level_row(contract)
    baseline_values = resolve_points(baseline[None, :], contract)[0][0]
    comparisons: list[dict[str, Any]] = []
    per_component: dict[str, list[float]] = {name: [] for name in COMPONENT_NAMES[:5]}
    for ledger_path in (CANDIDATE_SELECTION_LEDGER, CANDIDATE_FORWARD_LEDGER):
        with ledger_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                component = LEDGER_COMPONENTS.get(row["component_id"], -1)
                if component < 0 or component == 5 or row["signal_known"] != "1":
                    continue
                epoch = int(
                    datetime.strptime(row["decision_bar"], "%Y.%m.%d %H:%M")
                    .replace(tzinfo=timezone.utc)
                    .timestamp()
                )
                index = bar_index_for_component(component, epoch, basis)
                if index < 0:
                    continue
                calculated = baseline_features_at(
                    component, index, basis, baseline, baseline_values
                )
                observed = float(row["feature"])
                if not math.isfinite(calculated):
                    continue
                error = abs(calculated - observed)
                comparisons.append(
                    {
                        "component": COMPONENT_NAMES[component],
                        "epoch": epoch,
                        "observed": observed,
                        "calculated": calculated,
                        "absolute_error": error,
                    }
                )
                per_component[COMPONENT_NAMES[component]].append(error)
    if not comparisons:
        raise RuntimeError("feature anchor found no comparable observations")
    maximum_error = max(item["absolute_error"] for item in comparisons)
    exact_fraction = sum(
        item["absolute_error"] <= float(contract["anchor_gate"]["maximum_feature_absolute_error"])
        for item in comparisons
    ) / len(comparisons)
    summary = {
        "compared_rows": len(comparisons),
        "exact_within_declared_tolerance": sum(
            item["absolute_error"] <= float(contract["anchor_gate"]["maximum_feature_absolute_error"])
            for item in comparisons
        ),
        "exact_fraction": exact_fraction,
        "maximum_absolute_error": maximum_error,
        "mean_absolute_error": float(
            np.mean([item["absolute_error"] for item in comparisons])
        ),
        "components": {
            name: {
                "rows": len(errors),
                "maximum_absolute_error": max(errors) if errors else None,
                "mean_absolute_error": float(np.mean(errors)) if errors else None,
            }
            for name, errors in per_component.items()
        },
        "passed": (
            exact_fraction
            >= float(contract["anchor_gate"]["minimum_exact_feature_match_fraction"])
            and maximum_error
            <= float(contract["anchor_gate"]["maximum_feature_absolute_error"])
        ),
        "worst_rows": sorted(
            comparisons, key=lambda item: item["absolute_error"], reverse=True
        )[:10],
    }
    return summary


def lifecycle_segments(path: Path) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    current = {
        "births": [],
        "close_rows": [],
        "closes": 0,
        "actual": 0.0,
        "stressed": 0.0,
    }
    previous_sequence: int | None = None

    def finish() -> None:
        nonlocal current
        if current["closes"] or current["births"]:
            segments.append(current)
        current = {
            "births": [],
            "close_rows": [],
            "closes": 0,
            "actual": 0.0,
            "stressed": 0.0,
        }

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            sequence = int(row["research_state_sequence"])
            if previous_sequence is not None and sequence < previous_sequence:
                finish()
            previous_sequence = sequence
            if row["event"] == "BIRTH":
                current["births"].append(
                    (
                        LEDGER_COMPONENTS[row["component_id"]],
                        row["position_identifier"],
                        row["entry_time_server"],
                        float(row["volume"]),
                        float(row["entry_spread_price"]),
                    )
                )
            elif row["event"] == "CLOSE":
                current["closes"] += 1
                current["actual"] += float(row["actual_net_usd"])
                current["stressed"] += float(row["stressed_net_usd"])
                current["close_rows"].append(
                    (
                        row["position_identifier"],
                        row["server_time"],
                        float(row["actual_net_usd"]),
                        float(row["stressed_net_usd"]),
                    )
                )
    finish()
    return segments


def find_lifecycle_segment(
    segments: Iterable[dict[str, Any]], reference: dict[str, Any]
) -> dict[str, Any]:
    matches = [
        segment
        for segment in segments
        if int(segment["closes"]) == int(reference["closed_lifecycles"])
        and abs(float(segment["actual"]) - float(reference["actual_net_usd"])) <= 0.02
        and abs(float(segment["stressed"]) - float(reference["stressed_net_usd"])) <= 0.02
    ]
    if not matches:
        raise RuntimeError(f"no lifecycle segment matches {reference}")
    return matches[0]


def spread_calibration(contract: dict[str, Any], basis: Basis) -> dict[str, Any]:
    candidate_selection = lifecycle_segments(CANDIDATE_SELECTION_LIFECYCLE)
    candidate_forward = lifecycle_segments(CANDIDATE_FORWARD_LIFECYCLE)
    control_segments: list[dict[str, Any]] = []
    for path in sorted(CONTROL_LIFECYCLE_GLOB.glob("*/**/research-lifecycles.csv")):
        control_segments.extend(lifecycle_segments(path))
    sources = [
        find_lifecycle_segment(
            candidate_selection, contract["paired_contracts"][1]["reference_selection"]
        ),
        find_lifecycle_segment(
            candidate_forward, contract["paired_contracts"][1]["reference_forward"]
        ),
        find_lifecycle_segment(
            control_segments, contract["paired_contracts"][0]["reference_selection"]
        ),
        find_lifecycle_segment(
            control_segments, contract["paired_contracts"][0]["reference_forward"]
        ),
    ]
    proxy_cost = np.zeros(6, dtype=np.float64)
    native_cost = np.zeros(6, dtype=np.float64)
    row_counts = np.zeros(6, dtype=np.int64)
    for segment in sources:
        births = {item[1]: item for item in segment["births"]}
        for identifier, exit_text, actual_net, stressed_net in segment["close_rows"]:
            if identifier not in births:
                continue
            component, _, entry_text, volume, _ = births[identifier]
            entry_epoch = int(
                datetime.strptime(entry_text, "%Y.%m.%d %H:%M:%S")
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
            exit_epoch = int(
                datetime.strptime(exit_text, "%Y.%m.%d %H:%M:%S")
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
            m1 = basis.us100_m1 if component in (2, 5) else basis.us30_m1
            entry_index = int(np.searchsorted(m1.time, entry_epoch))
            exit_index = int(np.searchsorted(m1.time, exit_epoch))
            if (
                entry_index >= len(m1.time)
                or exit_index >= len(m1.time)
                or m1.time[entry_index] > entry_epoch + 120
                or m1.time[exit_index] > exit_epoch + 120
            ):
                continue
            proxy_spread = (
                max(float(m1.spread[entry_index]), float(m1.spread[exit_index]))
                * 0.01
            )
            native_additional_cost = actual_net - stressed_net
            if (
                proxy_spread <= 0.0
                or native_additional_cost < 0.0
                or volume <= 0.0
            ):
                continue
            proxy_cost[component] += proxy_spread * volume
            native_cost[component] += native_additional_cost
            row_counts[component] += 1
    multipliers = np.ones(6, dtype=np.float64)
    valid = proxy_cost > 0.0
    multipliers[valid] = native_cost[valid] / proxy_cost[valid]
    return {
        "multipliers": multipliers,
        "components": [
            {
                "component": COMPONENT_NAMES[index],
                "rows": int(row_counts[index]),
                "proxy_entry_spread_cost_usd": float(proxy_cost[index]),
                "native_entry_spread_cost_usd": float(native_cost[index]),
                "multiplier": float(multipliers[index]),
            }
            for index in range(6)
        ],
        "source_books": 4,
        "rule": "component total native stressed additional cost divided by max(entry, exit) M1 bar-spread cost for the same exact lifecycles across control/candidate selection and forward books",
    }


def schedule_mask(times: np.ndarray, hour: int, minute: int) -> np.ndarray:
    return ((times // 3600) % 24 == hour) & ((times // 60) % 60 == minute)


def first_m1_indexes(event_times: np.ndarray, m1_times: np.ndarray) -> np.ndarray:
    indexes = np.searchsorted(m1_times, event_times).astype(np.int32)
    valid = indexes < len(m1_times)
    valid &= np.where(valid, m1_times[np.minimum(indexes, len(m1_times) - 1)] <= event_times + 120, False)
    indexes[~valid] = -1
    return indexes


def build_events(
    basis: Basis, start_epoch: int, end_epoch: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    closed = closure_dates()
    records: list[tuple[int, int, int, int]] = []

    def append_scheduled(
        component: int, rates: Rates, hour: int, minute: int, exclude_closures: bool
    ) -> None:
        mask = (
            (rates.time >= start_epoch)
            & (rates.time < end_epoch)
            & schedule_mask(rates.time, hour, minute)
        )
        for bar_index in np.flatnonzero(mask):
            epoch = int(rates.time[bar_index])
            if exclude_closures and epoch_to_date(epoch) in closed:
                continue
            records.append((epoch, component, int(bar_index), 0))

    append_scheduled(1, basis.us30_m30, 13, 0, False)
    append_scheduled(0, basis.us30_m30, 13, 30, False)
    append_scheduled(3, basis.us30_m30, 15, 0, False)
    append_scheduled(4, basis.us30_h1, 16, 0, True)
    append_scheduled(2, basis.us100_h1, 17, 0, True)

    times = basis.us100_m15.time
    previous = np.roll(times, 1)
    previous_hour = (previous // 3600) % 24
    passive_mask = (
        (times >= start_epoch)
        & (times < end_epoch)
        & (np.arange(len(times)) > 0)
        & (times - previous == 900)
        & (previous_hour >= 12)
        & (previous_hour < 16)
    )
    for bar_index in np.flatnonzero(passive_mask):
        records.append((int(times[bar_index]), 5, int(bar_index), -1))

    # Passive state first at coincident timestamps, then fixed strategy order.
    priority = {5: 0, 1: 1, 0: 2, 3: 3, 4: 4, 2: 5}
    records.sort(key=lambda item: (item[0], priority[item[1]]))
    event_times = np.asarray([item[0] for item in records], dtype=np.int64)
    components = np.asarray([item[1] for item in records], dtype=np.int8)
    bar_indexes = np.asarray([item[2] for item in records], dtype=np.int32)
    m1_indexes = np.empty(len(records), dtype=np.int32)
    us30_mask = np.isin(components, np.asarray([0, 1, 3, 4], dtype=np.int8))
    us100_mask = ~us30_mask
    m1_indexes[us30_mask] = first_m1_indexes(
        event_times[us30_mask], basis.us30_m1.time
    )
    m1_indexes[us100_mask] = first_m1_indexes(
        event_times[us100_mask], basis.us100_m1.time
    )
    return event_times, components, bar_indexes, m1_indexes


@njit(cache=True)
def first_at_or_after(values: np.ndarray, target: int) -> int:
    left = 0
    right = len(values)
    while left < right:
        middle = (left + right) // 2
        if values[middle] < target:
            left = middle + 1
        else:
            right = middle
    return left


@njit(cache=True)
def first_leq(
    values: np.ndarray,
    blocks: np.ndarray,
    start: int,
    end: int,
    threshold: float,
) -> int:
    if start < 0:
        start = 0
    if end >= len(values):
        end = len(values) - 1
    if start > end:
        return -1
    index = start
    while index <= end and index % BLOCK_SIZE != 0:
        if values[index] <= threshold:
            return index
        index += 1
    while index + BLOCK_SIZE - 1 <= end:
        block = index // BLOCK_SIZE
        if blocks[block] <= threshold:
            stop = index + BLOCK_SIZE
            while index < stop:
                if values[index] <= threshold:
                    return index
                index += 1
        else:
            index += BLOCK_SIZE
    while index <= end:
        if values[index] <= threshold:
            return index
        index += 1
    return -1


@njit(cache=True)
def first_geq(
    values: np.ndarray,
    blocks: np.ndarray,
    start: int,
    end: int,
    threshold: float,
) -> int:
    if start < 0:
        start = 0
    if end >= len(values):
        end = len(values) - 1
    if start > end:
        return -1
    index = start
    while index <= end and index % BLOCK_SIZE != 0:
        if values[index] >= threshold:
            return index
        index += 1
    while index + BLOCK_SIZE - 1 <= end:
        block = index // BLOCK_SIZE
        if blocks[block] >= threshold:
            stop = index + BLOCK_SIZE
            while index < stop:
                if values[index] >= threshold:
                    return index
                index += 1
        else:
            index += BLOCK_SIZE
    while index <= end:
        if values[index] >= threshold:
            return index
        index += 1
    return -1


@njit(cache=True)
def loss_side_stop(entry: float, distance: float, direction: int) -> float:
    raw = entry - direction * distance
    units = raw / PRICE_TICK
    if direction > 0:
        return math.floor(units + 1.0e-12) * PRICE_TICK
    return math.ceil(units - 1.0e-12) * PRICE_TICK


@njit(cache=True)
def round_cents(value: float) -> float:
    if value >= 0.0:
        return math.floor(value * 100.0 + 0.5 + 1.0e-12) / 100.0
    return math.ceil(value * 100.0 - 0.5 - 1.0e-12) / 100.0


@njit(cache=True)
def general_direction(feature: float, threshold: float, skew: float, mode: int) -> int:
    positive = threshold * math.exp(skew)
    negative = threshold * math.exp(-skew)
    if mode == 0:  # symmetric continuation
        if feature >= positive:
            return 1
        if feature <= -negative:
            return -1
        return 0
    if mode == 1:  # symmetric reversion
        if feature >= positive:
            return -1
        if feature <= -negative:
            return 1
        return 0
    if mode == 2:  # positive long
        return 1 if feature >= positive else 0
    return -1 if feature <= -negative else 0


@njit(cache=True)
def rc16_direction(feature: float, threshold: float, skew: float, mode: int) -> int:
    # RC16's declared categorical order differs from the other shared families.
    if mode == 0:
        return 1 if feature >= threshold * math.exp(skew) else 0
    if mode == 1:
        return general_direction(feature, threshold, skew, 0)
    if mode == 2:
        return general_direction(feature, threshold, skew, 1)
    return -1 if feature <= -threshold * math.exp(-skew) else 0


@njit(cache=True)
def return_direction(feature: float, threshold: float, skew: float, mode: int) -> int:
    positive = threshold * math.exp(skew)
    negative = threshold * math.exp(-skew)
    if mode == 0:  # negative-long reversal
        return 1 if feature <= -negative else 0
    if mode == 1:  # symmetric reversal
        if feature >= positive:
            return -1
        if feature <= -negative:
            return 1
        return 0
    if mode == 2:  # symmetric momentum
        if feature >= positive:
            return 1
        if feature <= -negative:
            return -1
        return 0
    return -1 if feature >= positive else 0


@njit(cache=True)
def passive_feature(
    bar_index: int,
    parameter: np.ndarray,
    level: np.ndarray,
    m15_close: np.ndarray,
    passive_mean: np.ndarray,
    passive_std: np.ndarray,
) -> float:
    lookback = int(parameter[PASSIVE_L])
    scale_index = int(level[PASSIVE_N])
    latest = bar_index - 1
    earlier = latest - lookback
    if earlier < 0 or latest >= len(m15_close):
        return math.nan
    mean = passive_mean[scale_index, bar_index]
    standard = passive_std[scale_index, bar_index]
    if not math.isfinite(mean) or not math.isfinite(standard) or standard <= 0.0:
        return math.nan
    impulse = math.log(m15_close[latest] / m15_close[earlier])
    numerator = impulse - parameter[PASSIVE_CENTER] * mean * lookback
    return numerator / (standard * lookback ** parameter[PASSIVE_POWER])


@njit(cache=True)
def formula_feature_and_direction(
    component: int,
    bar_index: int,
    parameter: np.ndarray,
    level: np.ndarray,
    features: tuple,
) -> tuple[float, int]:
    (
        rc16_ratio,
        rc16_sign,
        rc4_ratio,
        rc4_sign,
        cross_current,
        cross_mean,
        cross_std,
        pressure_fraction,
        pressure_running,
        pressure_scale,
        return_impulse,
        return_mean,
        return_std,
        passive_mean,
        passive_std,
        passive_range,
        arc_feature,
        arc_ret1_z,
        arc_efficiency,
        arc_close_location,
        arc_vol_ratio,
        arc_range_median,
        arc_pressure,
    ) = features
    if component == 0:
        feature = (
            rc16_ratio[int(level[RC16_C]), int(level[RC16_N]), bar_index]
            * rc16_sign[int(level[RC16_C]), int(level[RC16_D]), bar_index]
        )
        if not math.isfinite(feature):
            return math.nan, 0
        return feature, rc16_direction(
            feature,
            parameter[RC16_THR],
            parameter[RC16_SKEW],
            int(level[RC16_MODE]),
        )
    if component == 1:
        feature = (
            rc4_ratio[int(level[RC4_C]), int(level[RC4_N]), bar_index]
            * rc4_sign[int(level[RC4_C]), int(level[RC4_D]), bar_index]
        )
        if not math.isfinite(feature):
            return math.nan, 0
        return feature, general_direction(
            feature,
            parameter[RC4_THR],
            parameter[RC4_SKEW],
            int(level[RC4_MODE]),
        )
    if component == 2:
        peer_index = int(level[CROSS_BETA]) * 5 + int(level[CROSS_SHARE])
        standard = cross_std[peer_index, int(level[CROSS_N]), bar_index]
        if not math.isfinite(standard) or standard <= 0.0:
            return math.nan, 0
        feature = (
            cross_current[peer_index, bar_index]
            - parameter[CROSS_CENTER]
            * cross_mean[peer_index, int(level[CROSS_N]), bar_index]
        ) / standard
        return feature, general_direction(
            feature,
            parameter[CROSS_THR],
            parameter[CROSS_SKEW],
            int(level[CROSS_MODE]),
        )
    if component == 3:
        scale = pressure_scale[
            int(level[PRESSURE_N]), int(level[PRESSURE_QNT]), bar_index
        ]
        fraction = pressure_fraction[bar_index]
        running = pressure_running[bar_index]
        if (
            not math.isfinite(scale)
            or scale <= 0.0
            or not math.isfinite(fraction)
            or not math.isfinite(running)
            or running <= 0.0
        ):
            return math.nan, 0
        location = 2.0 * (fraction - parameter[PRESSURE_CENTER])
        if location == 0.0:
            feature = 0.0
        else:
            feature = math.copysign(
                abs(location) ** parameter[PRESSURE_LOC_POWER], location
            ) * (running / scale) ** parameter[PRESSURE_RANGE_POWER]
        return feature, general_direction(
            feature,
            parameter[PRESSURE_THR],
            parameter[PRESSURE_SKEW],
            int(level[PRESSURE_MODE]),
        )
    lookback_index = int(level[RETURN_L])
    scale_index = int(level[RETURN_N])
    overlap_index = int(level[RETURN_OVERLAP])
    standard = return_std[lookback_index, scale_index, overlap_index, bar_index]
    if not math.isfinite(standard) or standard <= 0.0:
        return math.nan, 0
    impulse = return_impulse[lookback_index, bar_index]
    mean = return_mean[lookback_index, scale_index, overlap_index, bar_index]
    lookback = parameter[RETURN_L]
    feature = (
        impulse - parameter[RETURN_CENTER] * mean * lookback
    ) / (standard * lookback ** parameter[RETURN_POWER])
    return feature, return_direction(
        feature,
        parameter[RETURN_THR],
        parameter[RETURN_SKEW],
        int(level[RETURN_MODE]),
    )


@njit(cache=True)
def epoch_index_for_time(exit_time: int, epoch_starts: np.ndarray, epoch_ends: np.ndarray) -> int:
    for index in range(len(epoch_starts)):
        if epoch_starts[index] <= exit_time < epoch_ends[index]:
            return index
    return -1


@njit(cache=True, parallel=True)
def simulate_tasks(
    parameters: np.ndarray,
    levels: np.ndarray,
    contract_weights: np.ndarray,
    aggregate_fractions: np.ndarray,
    spread_cost_multipliers: np.ndarray,
    event_times: np.ndarray,
    event_components: np.ndarray,
    event_bar_indexes: np.ndarray,
    event_m1_indexes: np.ndarray,
    market: tuple,
    bars: tuple,
    features: tuple,
    period_start: int,
    period_end: int,
    epoch_starts: np.ndarray,
    epoch_ends: np.ndarray,
) -> tuple:
    (
        us30_m1_time,
        us30_open,
        us30_low,
        us30_low_block,
        us30_high_ask,
        us30_high_ask_block,
        us30_spread,
        us100_m1_time,
        us100_open,
        us100_low,
        us100_low_block,
        us100_low_ask,
        us100_low_ask_block,
        us100_high,
        us100_high_block,
        us100_high_ask,
        us100_high_ask_block,
        us100_spread,
    ) = market
    (
        m30_time,
        us30_h1_time,
        us100_h1_time,
        m15_time,
        m15_close,
    ) = bars
    (
        rc16_ratio,
        rc16_sign,
        rc4_ratio,
        rc4_sign,
        cross_current,
        cross_mean,
        cross_std,
        pressure_fraction,
        pressure_running,
        pressure_scale,
        return_impulse,
        return_mean,
        return_std,
        passive_mean,
        passive_std,
        passive_range,
        arc_feature,
        arc_ret1_z,
        arc_efficiency,
        arc_close_location,
        arc_vol_ratio,
        arc_range_median,
        arc_pressure,
    ) = features
    point_count = len(parameters)
    task_count = point_count * len(contract_weights)
    epoch_count = len(epoch_starts)
    day_count = int((period_end - period_start + 86399) // 86400)
    actual_net = np.zeros(task_count, dtype=np.float64)
    stressed_net = np.zeros(task_count, dtype=np.float64)
    actual_dd_pct = np.zeros(task_count, dtype=np.float64)
    stressed_dd_pct = np.zeros(task_count, dtype=np.float64)
    actual_min_balance = np.full(task_count, 100.0, dtype=np.float64)
    stressed_min_balance = np.full(task_count, 100.0, dtype=np.float64)
    actual_gross_profit = np.zeros(task_count, dtype=np.float64)
    actual_gross_loss = np.zeros(task_count, dtype=np.float64)
    stressed_gross_profit = np.zeros(task_count, dtype=np.float64)
    stressed_gross_loss = np.zeros(task_count, dtype=np.float64)
    closes = np.zeros(task_count, dtype=np.int32)
    stop_exits = np.zeros(task_count, dtype=np.int32)
    arc_exits = np.zeros(task_count, dtype=np.int32)
    arc_triggers = np.zeros(task_count, dtype=np.int32)
    risk_skips = np.zeros(task_count, dtype=np.int32)
    signal_count = np.zeros(task_count, dtype=np.int32)
    max_open_risk_fraction = np.zeros(task_count, dtype=np.float64)
    component_actual = np.zeros((task_count, 6), dtype=np.float64)
    component_stressed = np.zeros((task_count, 6), dtype=np.float64)
    component_closes = np.zeros((task_count, 6), dtype=np.int32)
    epoch_actual = np.zeros((task_count, epoch_count), dtype=np.float64)
    epoch_stressed = np.zeros((task_count, epoch_count), dtype=np.float64)
    daily_stressed = np.zeros((task_count, day_count), dtype=np.float32)

    for task in prange(task_count):
        point = task // len(contract_weights)
        contract_index = task % len(contract_weights)
        parameter = parameters[point]
        level = levels[point]
        weights = contract_weights[contract_index]
        aggregate_fraction = aggregate_fractions[contract_index]
        actual_balance = 100.0
        stressed_balance = 100.0
        actual_peak = 100.0
        stressed_peak = 100.0
        open_risk = 0.0
        day_number = -1
        day_multiplier = 1
        passive_cooldown_until = 0

        active = np.zeros(6, dtype=np.uint8)
        has_trade = np.zeros(6, dtype=np.uint8)
        exit_time = np.zeros(6, dtype=np.int64)
        exit_actual = np.zeros(6, dtype=np.float64)
        exit_stressed = np.zeros(6, dtype=np.float64)
        state_risk = np.zeros(6, dtype=np.float64)
        state_reason = np.zeros(6, dtype=np.int8)
        occupied_until = np.zeros(6, dtype=np.int64)
        passive_release_cooldown = np.zeros(6, dtype=np.int64)

        for event_index in range(len(event_times) + 1):
            now = period_end if event_index == len(event_times) else event_times[event_index]

            while True:
                selected = -1
                selected_time = period_end + 1
                for component in range(6):
                    if active[component] and exit_time[component] <= now:
                        if exit_time[component] < selected_time:
                            selected = component
                            selected_time = exit_time[component]
                if selected < 0:
                    break
                open_risk = max(0.0, open_risk - state_risk[selected])
                if has_trade[selected]:
                    actual_value = exit_actual[selected]
                    stressed_value = exit_stressed[selected]
                    actual_balance += actual_value
                    stressed_balance += stressed_value
                    closes[task] += 1
                    component_closes[task, selected] += 1
                    component_actual[task, selected] += actual_value
                    component_stressed[task, selected] += stressed_value
                    if actual_value >= 0.0:
                        actual_gross_profit[task] += actual_value
                    else:
                        actual_gross_loss[task] += actual_value
                    if stressed_value >= 0.0:
                        stressed_gross_profit[task] += stressed_value
                    else:
                        stressed_gross_loss[task] += stressed_value
                    if state_reason[selected] == 1:
                        stop_exits[task] += 1
                    elif state_reason[selected] == 2:
                        stop_exits[task] += 1
                        arc_exits[task] += 1
                    epoch = epoch_index_for_time(
                        selected_time, epoch_starts, epoch_ends
                    )
                    if epoch >= 0:
                        epoch_actual[task, epoch] += actual_value
                        epoch_stressed[task, epoch] += stressed_value
                    day_index = int((selected_time - period_start) // 86400)
                    if 0 <= day_index < day_count:
                        daily_stressed[task, day_index] += stressed_value
                    if actual_balance > actual_peak:
                        actual_peak = actual_balance
                    elif actual_peak > 0.0:
                        drawdown = (actual_peak - actual_balance) / actual_peak * 100.0
                        if drawdown > actual_dd_pct[task]:
                            actual_dd_pct[task] = drawdown
                    if stressed_balance > stressed_peak:
                        stressed_peak = stressed_balance
                    elif stressed_peak > 0.0:
                        drawdown = (
                            (stressed_peak - stressed_balance) / stressed_peak * 100.0
                        )
                        if drawdown > stressed_dd_pct[task]:
                            stressed_dd_pct[task] = drawdown
                    if actual_balance < actual_min_balance[task]:
                        actual_min_balance[task] = actual_balance
                    if stressed_balance < stressed_min_balance[task]:
                        stressed_min_balance[task] = stressed_balance
                if selected == 5 and passive_release_cooldown[selected] > passive_cooldown_until:
                    passive_cooldown_until = passive_release_cooldown[selected]
                active[selected] = 0
                has_trade[selected] = 0
                state_risk[selected] = 0.0

            if event_index == len(event_times):
                break

            component = int(event_components[event_index])
            bar_index = int(event_bar_indexes[event_index])
            entry_m1 = int(event_m1_indexes[event_index])
            if entry_m1 < 0:
                continue
            current_day = int(now // 86400)
            if current_day != day_number:
                day_multiplier = 1 + int(
                    math.floor(max(0.0, stressed_balance - 100.0) / 150.0 + 1.0e-9)
                )
                if day_multiplier < 1:
                    day_multiplier = 1
                day_number = current_day

            weight = weights[component]
            if weight <= 0.0:
                continue
            if active[component] or now < occupied_until[component]:
                continue
            if component == 5 and now < passive_cooldown_until:
                continue

            if component == 5:
                feature = passive_feature(
                    bar_index,
                    parameter,
                    level,
                    m15_close,
                    passive_mean,
                    passive_std,
                )
                if not math.isfinite(feature) or abs(feature) < parameter[PASSIVE_ENTRY]:
                    continue
                direction = 1 if feature > 0.0 else -1
                if int(level[PASSIVE_MODE]) == 0:
                    direction = -direction
                signal_count[task] += 1
                conservative = min(actual_balance, stressed_balance)
                if conservative <= 0.0:
                    continue
                volume = 0.01
                budget = conservative * 0.04
                if open_risk + budget > conservative * aggregate_fraction + 0.01:
                    risk_skips[task] += 1
                    continue
                scale = passive_range[int(level[PASSIVE_N]), bar_index]
                if not math.isfinite(scale) or scale <= 0.0:
                    continue
                decision_close = m15_close[bar_index - 1]
                raw_limit = decision_close - direction * parameter[PASSIVE_OFFSET] * scale
                if direction > 0:
                    limit_price = math.floor(raw_limit / PRICE_TICK + 1.0e-10) * PRICE_TICK
                else:
                    limit_price = math.ceil(raw_limit / PRICE_TICK - 1.0e-10) * PRICE_TICK
                bid = us100_open[entry_m1]
                ask = bid + us100_spread[entry_m1] * 0.01
                if (direction > 0 and bid - limit_price < PRICE_TICK) or (
                    direction < 0 and limit_price - ask < PRICE_TICK
                ):
                    continue
                expiration = min(
                    period_end, now + int(parameter[PASSIVE_ACTIVATION]) * 900
                )
                fill_end = first_at_or_after(us100_m1_time, expiration) - 1
                if direction > 0:
                    fill_index = first_leq(
                        us100_low_ask,
                        us100_low_ask_block,
                        entry_m1,
                        fill_end,
                        limit_price,
                    )
                else:
                    fill_index = first_geq(
                        us100_high,
                        us100_high_block,
                        entry_m1,
                        fill_end,
                        limit_price,
                    )
                open_risk += budget
                state_risk[component] = budget
                active[component] = 1
                if fill_index < 0:
                    exit_time[component] = expiration
                    occupied_until[component] = expiration
                    has_trade[component] = 0
                    continue

                fill_time = us100_m1_time[fill_index]
                fill_bar = first_at_or_after(m15_time, fill_time)
                if fill_bar >= len(m15_time) or m15_time[fill_bar] > fill_time:
                    fill_bar -= 1
                if fill_bar < 0:
                    fill_bar = 0
                maximum_bar = min(
                    len(m15_time) - 1,
                    fill_bar + int(parameter[PASSIVE_HOLD]),
                )
                target_bar = maximum_bar
                exit_strength = parameter[PASSIVE_ENTRY] * parameter[PASSIVE_EXIT_FRAC]
                for candidate_bar in range(fill_bar + 1, maximum_bar + 1):
                    if m15_time[candidate_bar] >= period_end:
                        target_bar = candidate_bar
                        break
                    held = candidate_bar - fill_bar
                    state = passive_feature(
                        candidate_bar,
                        parameter,
                        level,
                        m15_close,
                        passive_mean,
                        passive_std,
                    )
                    should_close = held >= int(parameter[PASSIVE_HOLD])
                    if math.isfinite(state):
                        desired = 1 if state > 0.0 else -1 if state < 0.0 else 0
                        if int(level[PASSIVE_MODE]) == 0:
                            desired = -desired
                        if abs(state) <= exit_strength or (
                            desired != 0 and desired != direction
                        ):
                            should_close = True
                    if should_close:
                        target_bar = candidate_bar
                        break
                target_time = min(period_end, m15_time[target_bar])
                scheduled_exit = first_at_or_after(us100_m1_time, target_time)
                if scheduled_exit >= len(us100_m1_time) or target_time >= period_end:
                    scheduled_exit = first_at_or_after(us100_m1_time, period_end) - 1
                distance = 0.5 * budget / volume
                stop = loss_side_stop(limit_price, distance, direction)
                if direction > 0:
                    stop_index = first_leq(
                        us100_low,
                        us100_low_block,
                        fill_index,
                        scheduled_exit - 1,
                        stop,
                    )
                else:
                    stop_index = first_geq(
                        us100_high_ask,
                        us100_high_ask_block,
                        fill_index,
                        scheduled_exit - 1,
                        stop,
                    )
                reason = 0
                exit_index = scheduled_exit
                exit_price = (
                    us100_open[exit_index]
                    if direction > 0
                    else us100_open[exit_index] + us100_spread[exit_index] * 0.01
                )
                if stop_index >= 0:
                    reason = 1
                    exit_index = stop_index
                    exit_price = stop
                actual_value = round_cents(
                    direction
                    * (exit_price - limit_price)
                    * volume
                    * POINT_VALUE_PER_PRICE_PER_LOT
                )
                extra_spread = (
                    max(us100_spread[fill_index], us100_spread[exit_index])
                    * 0.01
                    * volume
                    * spread_cost_multipliers[component]
                )
                exit_actual[component] = actual_value
                exit_stressed[component] = actual_value - extra_spread
                exit_time[component] = us100_m1_time[exit_index]
                state_reason[component] = reason
                has_trade[component] = 1
                occupied_until[component] = exit_time[component]
                passive_release_cooldown[component] = (
                    exit_time[component] + int(parameter[PASSIVE_COOLDOWN]) * 900
                )
            else:
                feature, direction = formula_feature_and_direction(
                    component, bar_index, parameter, level, features
                )
                if not math.isfinite(feature) or direction == 0:
                    continue
                signal_count[task] += 1
                conservative = min(actual_balance, stressed_balance)
                if conservative <= 0.0:
                    continue
                target_steps = int(math.floor(day_multiplier * weight + 0.5 + 1.0e-12))
                if target_steps <= 0:
                    continue
                volume = 0.01 * target_steps
                executable_multiplier = target_steps / day_multiplier
                budget = conservative * 0.04 * executable_multiplier
                if open_risk + budget > conservative * aggregate_fraction + 0.01:
                    risk_skips[task] += 1
                    continue

                if component in (0, 1, 3):
                    timeframe_times = m30_time
                    hold = int(
                        parameter[
                            RC16_HOLD
                            if component == 0
                            else RC4_HOLD
                            if component == 1
                            else PRESSURE_HOLD
                        ]
                    )
                    price_times = us30_m1_time
                    price_open = us30_open
                    price_spread = us30_spread
                    price_low = us30_low
                    price_low_block = us30_low_block
                    price_high_ask = us30_high_ask
                    price_high_ask_block = us30_high_ask_block
                elif component == 4:
                    timeframe_times = us30_h1_time
                    hold = int(parameter[RETURN_HOLD])
                    price_times = us30_m1_time
                    price_open = us30_open
                    price_spread = us30_spread
                    price_low = us30_low
                    price_low_block = us30_low_block
                    price_high_ask = us30_high_ask
                    price_high_ask_block = us30_high_ask_block
                else:
                    timeframe_times = us100_h1_time
                    hold = int(parameter[CROSS_HOLD])
                    price_times = us100_m1_time
                    price_open = us100_open
                    price_spread = us100_spread
                    price_low = us100_low
                    price_low_block = us100_low_block
                    price_high_ask = us100_high_ask
                    price_high_ask_block = us100_high_ask_block

                target_bar = bar_index + hold
                if target_bar < len(timeframe_times):
                    target_time = timeframe_times[target_bar]
                else:
                    target_time = period_end
                if target_time >= period_end:
                    scheduled_exit = first_at_or_after(price_times, period_end) - 1
                else:
                    scheduled_exit = first_at_or_after(price_times, target_time)
                    if scheduled_exit >= len(price_times):
                        scheduled_exit = len(price_times) - 1
                if scheduled_exit <= entry_m1:
                    continue
                entry_bid = price_open[entry_m1]
                spread_price = price_spread[entry_m1] * 0.01
                entry_price = entry_bid + spread_price if direction > 0 else entry_bid
                distance = 0.5 * budget / volume
                original_stop = loss_side_stop(entry_price, distance, direction)
                if direction > 0:
                    original_stop_index = first_leq(
                        price_low,
                        price_low_block,
                        entry_m1,
                        scheduled_exit - 1,
                        original_stop,
                    )
                else:
                    original_stop_index = first_geq(
                        price_high_ask,
                        price_high_ask_block,
                        entry_m1,
                        scheduled_exit - 1,
                        original_stop,
                    )
                reason = 0
                exit_index = scheduled_exit
                exit_price = (
                    price_open[exit_index]
                    if direction > 0
                    else price_open[exit_index] + price_spread[exit_index] * 0.01
                )
                if original_stop_index >= 0:
                    reason = 1
                    exit_index = original_stop_index
                    exit_price = original_stop
                shadow_until = price_times[exit_index]

                if component == 1:
                    checkpoint = int(parameter[ARC_CHECKPOINT])
                    checkpoint_bar = bar_index + checkpoint
                    if checkpoint < hold and checkpoint_bar < len(m30_time):
                        checkpoint_time = m30_time[checkpoint_bar]
                        if checkpoint_time < price_times[exit_index] and checkpoint_time < period_end:
                            checkpoint_m1 = first_at_or_after(us30_m1_time, checkpoint_time)
                            if (
                                checkpoint_m1 < len(us30_m1_time)
                                and checkpoint_bar >= 2
                                and math.isfinite(arc_feature[checkpoint_bar])
                                and math.isfinite(arc_feature[checkpoint_bar - 1])
                                and math.isfinite(arc_feature[checkpoint_bar - 2])
                                and math.isfinite(arc_ret1_z[checkpoint_bar])
                                and math.isfinite(arc_efficiency[checkpoint_bar])
                                and math.isfinite(arc_close_location[checkpoint_bar])
                                and math.isfinite(arc_vol_ratio[checkpoint_bar])
                                and math.isfinite(arc_range_median[checkpoint_bar])
                                and arc_range_median[checkpoint_bar] > 0.0
                                and math.isfinite(arc_pressure[checkpoint_bar])
                            ):
                                entry_support = direction * feature
                                current_support = direction * arc_feature[checkpoint_bar]
                                previous_support = direction * arc_feature[checkpoint_bar - 1]
                                two_back_support = direction * arc_feature[checkpoint_bar - 2]
                                scale = max(abs(entry_support), 1.5)
                                velocity = (current_support - previous_support) / scale
                                prior_velocity = (previous_support - two_back_support) / scale
                                curvature = velocity - prior_velocity
                                cost_scale = max(
                                    us30_spread[checkpoint_m1] * 0.01, 1.10
                                ) / arc_range_median[checkpoint_bar]
                                cost_scale = min(2.0, max(0.0, cost_scale))
                                market_head = (
                                    direction
                                    * arc_ret1_z[checkpoint_bar]
                                    * (0.40 + 0.60 * arc_efficiency[checkpoint_bar])
                                    - parameter[ARC_MARKET_PENALTY]
                                    * (
                                        0.25 * max(0.0, arc_vol_ratio[checkpoint_bar] - 1.0)
                                        + 0.20 * cost_scale
                                    )
                                )
                                decision_head = (
                                    current_support / scale
                                    + parameter[ARC_DECISION_DYNAMICS]
                                    * (0.65 * velocity + 0.35 * curvature)
                                    - (
                                        1.25 * parameter[ARC_NEGATIVE_PENALTY]
                                        if current_support < 0.0
                                        else 0.0
                                    )
                                )
                                share = parameter[ARC_CONFIRM_SHARE]
                                confirmation_head = (
                                    share * direction * arc_pressure[checkpoint_bar]
                                    + (1.0 - share)
                                    * direction
                                    * arc_close_location[checkpoint_bar]
                                )
                                profile = int(level[ARC_PROFILE])
                                lower_scale = 0.25
                                upper_scale = 0.25
                                if profile == 1:
                                    lower_scale = upper_scale = 0.5
                                elif profile == 2:
                                    lower_scale = upper_scale = 1.0
                                elif profile == 3:
                                    lower_scale = upper_scale = 2.0
                                elif profile == 4:
                                    lower_scale = upper_scale = 4.0
                                elif profile == 5:
                                    lower_scale, upper_scale = 0.5, 2.0
                                elif profile == 6:
                                    lower_scale, upper_scale = 2.0, 0.5
                                market_vote = (
                                    -1
                                    if market_head <= -0.24107458 * lower_scale
                                    else 1
                                    if market_head >= 0.31112079 * upper_scale
                                    else 0
                                )
                                decision_vote = (
                                    -1
                                    if decision_head <= -0.42656390 * lower_scale
                                    else 1
                                    if decision_head >= 0.24808705 * upper_scale
                                    else 0
                                )
                                confirmation_vote = (
                                    -1
                                    if confirmation_head <= -0.07240202 * lower_scale
                                    else 1
                                    if confirmation_head >= 0.33558626 * upper_scale
                                    else 0
                                )
                                if (
                                    market_vote + decision_vote + confirmation_vote
                                    <= int(parameter[ARC_VOTE])
                                ):
                                    arc_triggers[task] += 1
                                    tightened = loss_side_stop(
                                        entry_price,
                                        distance * parameter[ARC_RETAIN],
                                        direction,
                                    )
                                    executable = (
                                        us30_open[checkpoint_m1]
                                        if direction > 0
                                        else us30_open[checkpoint_m1]
                                        + us30_spread[checkpoint_m1] * 0.01
                                    )
                                    retained_loss = direction * (entry_price - tightened)
                                    tightening = direction * (tightened - original_stop)
                                    clearance = direction * (executable - tightened)
                                    if (
                                        retained_loss >= PRICE_TICK - 1.0e-9
                                        and tightening >= PRICE_TICK - 1.0e-9
                                        and clearance >= PRICE_TICK - 1.0e-9
                                    ):
                                        if direction > 0:
                                            tightened_index = first_leq(
                                                us30_low,
                                                us30_low_block,
                                                checkpoint_m1,
                                                exit_index - 1,
                                                tightened,
                                            )
                                        else:
                                            tightened_index = first_geq(
                                                us30_high_ask,
                                                us30_high_ask_block,
                                                checkpoint_m1,
                                                exit_index - 1,
                                                tightened,
                                            )
                                        if tightened_index >= 0:
                                            shadow_until = price_times[exit_index]
                                            reason = 2
                                            exit_index = tightened_index
                                            exit_price = tightened

                actual_value = round_cents(
                    direction
                    * (exit_price - entry_price)
                    * volume
                    * POINT_VALUE_PER_PRICE_PER_LOT
                )
                stressed_value = (
                    actual_value
                    - max(
                        spread_price,
                        price_spread[exit_index] * 0.01,
                    )
                    * volume
                    * spread_cost_multipliers[component]
                )
                open_risk += budget
                state_risk[component] = budget
                active[component] = 1
                has_trade[component] = 1
                exit_time[component] = price_times[exit_index]
                exit_actual[component] = actual_value
                exit_stressed[component] = stressed_value
                state_reason[component] = reason
                occupied_until[component] = max(
                    exit_time[component], shadow_until
                )

            conservative_after = min(actual_balance, stressed_balance)
            if conservative_after > 0.0:
                fraction = open_risk / conservative_after
                if fraction > max_open_risk_fraction[task]:
                    max_open_risk_fraction[task] = fraction

        actual_net[task] = actual_balance - 100.0
        stressed_net[task] = stressed_balance - 100.0

    return (
        actual_net,
        stressed_net,
        actual_dd_pct,
        stressed_dd_pct,
        actual_min_balance,
        stressed_min_balance,
        actual_gross_profit,
        actual_gross_loss,
        stressed_gross_profit,
        stressed_gross_loss,
        closes,
        stop_exits,
        arc_exits,
        arc_triggers,
        risk_skips,
        signal_count,
        max_open_risk_fraction,
        component_actual,
        component_stressed,
        component_closes,
        epoch_actual,
        epoch_stressed,
        daily_stressed,
    )


RESULT_KEYS = (
    "actual_net",
    "stressed_net",
    "actual_dd_pct",
    "stressed_dd_pct",
    "actual_min_balance",
    "stressed_min_balance",
    "actual_gross_profit",
    "actual_gross_loss",
    "stressed_gross_profit",
    "stressed_gross_loss",
    "closes",
    "stop_exits",
    "arc_exits",
    "arc_triggers",
    "risk_skips",
    "signal_count",
    "max_open_risk_fraction",
    "component_actual",
    "component_stressed",
    "component_closes",
    "epoch_actual",
    "epoch_stressed",
    "daily_stressed",
)


def market_tuple(basis: Basis) -> tuple:
    return (
        basis.us30_m1.time,
        basis.us30_m1.open,
        basis.us30_m1.low,
        basis.us30_low_block,
        basis.us30_high_ask,
        basis.us30_high_ask_block,
        basis.us30_m1.spread,
        basis.us100_m1.time,
        basis.us100_m1.open,
        basis.us100_m1.low,
        basis.us100_low_block,
        basis.us100_low_ask,
        basis.us100_low_ask_block,
        basis.us100_m1.high,
        basis.us100_high_block,
        basis.us100_high_ask,
        basis.us100_high_ask_block,
        basis.us100_m1.spread,
    )


def bar_tuple(basis: Basis) -> tuple:
    return (
        basis.us30_m30.time,
        basis.us30_h1.time,
        basis.us100_h1.time,
        basis.us100_m15.time,
        basis.us100_m15.close,
    )


def feature_tuple(basis: Basis) -> tuple:
    return (
        basis.rc16_ratio,
        basis.rc16_sign,
        basis.rc4_ratio,
        basis.rc4_sign,
        basis.cross_current,
        basis.cross_mean,
        basis.cross_std,
        basis.pressure_fraction,
        basis.pressure_running_log_range,
        basis.pressure_scale,
        basis.return_impulse,
        basis.return_mean,
        basis.return_std,
        basis.passive_mean,
        basis.passive_std,
        basis.passive_range,
        basis.arc_feature,
        basis.arc_ret1_z,
        basis.arc_efficiency,
        basis.arc_close_location,
        basis.arc_vol_ratio,
        basis.arc_range_median,
        basis.arc_pressure,
    )


def timestamp(value: str) -> int:
    return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp())


def run_period(
    contract: dict[str, Any],
    basis: Basis,
    parameters: np.ndarray,
    levels: np.ndarray,
    start: str,
    end: str,
    epochs: list[tuple[str, str]],
    spread_cost_multipliers: np.ndarray,
) -> dict[str, np.ndarray]:
    start_epoch = timestamp(start)
    end_epoch = timestamp(end)
    event_arrays = build_events(basis, start_epoch, end_epoch)
    weights = np.asarray(
        [item["weights"] for item in contract["paired_contracts"]], dtype=np.float64
    )
    aggregates = np.asarray(
        [item["aggregate_risk_fraction"] for item in contract["paired_contracts"]],
        dtype=np.float64,
    )
    epoch_starts = np.asarray([timestamp(item[0]) for item in epochs], dtype=np.int64)
    epoch_ends = np.asarray([timestamp(item[1]) for item in epochs], dtype=np.int64)
    values = simulate_tasks(
        parameters,
        levels,
        weights,
        aggregates,
        spread_cost_multipliers,
        *event_arrays,
        market_tuple(basis),
        bar_tuple(basis),
        feature_tuple(basis),
        start_epoch,
        end_epoch,
        epoch_starts,
        epoch_ends,
    )
    result = dict(zip(RESULT_KEYS, values, strict=True))
    result["event_count"] = np.asarray([len(event_arrays[0])], dtype=np.int64)
    result["start_epoch"] = np.asarray([start_epoch], dtype=np.int64)
    result["end_epoch"] = np.asarray([end_epoch], dtype=np.int64)
    return result


def metric_record(result: dict[str, np.ndarray], task: int) -> dict[str, Any]:
    return {
        "actual_net_usd": float(result["actual_net"][task]),
        "stressed_net_usd": float(result["stressed_net"][task]),
        "actual_closed_dd_pct": float(result["actual_dd_pct"][task]),
        "stressed_closed_dd_pct": float(result["stressed_dd_pct"][task]),
        "actual_minimum_balance_usd": float(result["actual_min_balance"][task]),
        "stressed_minimum_balance_usd": float(result["stressed_min_balance"][task]),
        "actual_gross_profit_usd": float(result["actual_gross_profit"][task]),
        "actual_gross_loss_usd": float(result["actual_gross_loss"][task]),
        "stressed_gross_profit_usd": float(result["stressed_gross_profit"][task]),
        "stressed_gross_loss_usd": float(result["stressed_gross_loss"][task]),
        "actual_profit_factor": (
            float(result["actual_gross_profit"][task])
            / abs(float(result["actual_gross_loss"][task]))
            if result["actual_gross_loss"][task] < 0.0
            else None
        ),
        "stressed_profit_factor": (
            float(result["stressed_gross_profit"][task])
            / abs(float(result["stressed_gross_loss"][task]))
            if result["stressed_gross_loss"][task] < 0.0
            else None
        ),
        "closed_lifecycles": int(result["closes"][task]),
        "stop_exits": int(result["stop_exits"][task]),
        "arc_exits": int(result["arc_exits"][task]),
        "arc_triggers": int(result["arc_triggers"][task]),
        "risk_admission_skips": int(result["risk_skips"][task]),
        "signals": int(result["signal_count"][task]),
        "maximum_open_risk_fraction": float(result["max_open_risk_fraction"][task]),
        "components": [
            {
                "component": COMPONENT_NAMES[index],
                "actual_net_usd": float(result["component_actual"][task, index]),
                "stressed_net_usd": float(result["component_stressed"][task, index]),
                "closed_lifecycles": int(result["component_closes"][task, index]),
            }
            for index in range(6)
        ],
        "epoch_actual_net_usd": [
            float(value) for value in result["epoch_actual"][task]
        ],
        "epoch_stressed_net_usd": [
            float(value) for value in result["epoch_stressed"][task]
        ],
    }


def relative_error(observed: float, reference: float, scale: float | None = None) -> float:
    denominator = max(abs(reference), 5.0 if scale is None else scale)
    return abs(observed - reference) / denominator


def economic_anchor(
    contract: dict[str, Any],
    basis: Basis,
    baseline_levels: np.ndarray,
    spread_cost_multipliers: np.ndarray,
) -> dict[str, Any]:
    baseline_values = resolve_points(baseline_levels[None, :], contract)[0]
    selection_epochs = [
        ("2022-08-01T00:00:00", "2023-06-01T00:00:00"),
        ("2023-06-01T00:00:00", "2024-06-01T00:00:00"),
        ("2024-06-01T00:00:00", "2025-06-01T00:00:00"),
        ("2025-06-01T00:00:00", "2026-06-01T00:00:00"),
    ]
    selection = run_period(
        contract,
        basis,
        baseline_values,
        baseline_levels[None, :],
        "2022-08-01T00:00:00",
        "2026-06-01T00:00:00",
        selection_epochs,
        spread_cost_multipliers,
    )
    forward = run_period(
        contract,
        basis,
        baseline_values,
        baseline_levels[None, :],
        "2026-06-01T00:00:00",
        "2026-08-01T00:00:00",
        [("2026-06-01T00:00:00", "2026-08-01T00:00:00")],
        spread_cost_multipliers,
    )
    records: dict[str, Any] = {}
    all_passed = True
    for contract_index, paired in enumerate(contract["paired_contracts"]):
        contract_record: dict[str, Any] = {}
        for period_name, result, reference_name in (
            ("selection", selection, "reference_selection"),
            ("forward", forward, "reference_forward"),
        ):
            observed = metric_record(result, contract_index)
            reference = paired[reference_name]
            actual_scale = max(
                5.0,
                0.05
                * (
                    abs(float(observed["actual_gross_profit_usd"]))
                    + abs(float(observed["actual_gross_loss_usd"]))
                ),
            )
            stressed_scale = max(
                5.0,
                0.05
                * (
                    abs(float(observed["stressed_gross_profit_usd"]))
                    + abs(float(observed["stressed_gross_loss_usd"]))
                ),
            )
            errors = {
                "actual_net_relative_error": relative_error(
                    observed["actual_net_usd"],
                    float(reference["actual_net_usd"]),
                    actual_scale,
                ),
                "stressed_net_relative_error": relative_error(
                    observed["stressed_net_usd"],
                    float(reference["stressed_net_usd"]),
                    stressed_scale,
                ),
                "closed_lifecycle_relative_error": relative_error(
                    observed["closed_lifecycles"], int(reference["closed_lifecycles"])
                ),
            }
            passed = (
                errors["actual_net_relative_error"]
                <= float(contract["anchor_gate"]["actual_net_relative_tolerance"])
                and errors["stressed_net_relative_error"]
                <= float(contract["anchor_gate"]["stressed_net_relative_tolerance"])
                and errors["closed_lifecycle_relative_error"]
                <= float(contract["anchor_gate"]["closed_lifecycle_relative_tolerance"])
            )
            all_passed &= passed
            contract_record[period_name] = {
                "observed_proxy": observed,
                "native_reference": reference,
                "relative_errors": errors,
                "net_error_scales_usd": {
                    "actual": max(abs(float(reference["actual_net_usd"])), actual_scale),
                    "stressed": max(
                        abs(float(reference["stressed_net_usd"])), stressed_scale
                    ),
                },
                "passed": passed,
            }
        records[paired["id"]] = contract_record
    return {
        "passed": all_passed,
        "net_relative_error_denominator": "max(abs(native reference net), 5 percent of matching proxy gross turnover, USD 5 economic-materiality floor)",
        "selection_events": int(selection["event_count"][0]),
        "forward_events": int(forward["event_count"][0]),
        "contracts": records,
    }


def progress(message: str) -> None:
    print(f"[{datetime.now(timezone.utc).isoformat()}] {message}", flush=True)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def atomic_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False, compression="zstd")
    os.replace(temporary, path)


def combine_period_results(
    first: dict[str, np.ndarray], second: dict[str, np.ndarray]
) -> dict[str, np.ndarray]:
    combined: dict[str, np.ndarray] = {}
    for key in RESULT_KEYS:
        combined[key] = np.concatenate((first[key], second[key]), axis=0)
    for key in ("event_count", "start_epoch", "end_epoch"):
        if not np.array_equal(first[key], second[key]):
            raise RuntimeError(f"period metadata differs while combining {key}")
        combined[key] = first[key]
    return combined


def aggregate_monthly(
    result: dict[str, np.ndarray]
) -> tuple[np.ndarray, list[str]]:
    start_epoch = int(result["start_epoch"][0])
    day_count = result["daily_stressed"].shape[1]
    days = pd.to_datetime(
        start_epoch + np.arange(day_count, dtype=np.int64) * 86400,
        unit="s",
        utc=True,
    )
    labels = days.strftime("%Y-%m").to_numpy()
    month_labels = list(dict.fromkeys(labels.tolist()))
    monthly = np.zeros(
        (result["daily_stressed"].shape[0], len(month_labels)), dtype=np.float64
    )
    for index, label in enumerate(month_labels):
        monthly[:, index] = result["daily_stressed"][:, labels == label].sum(
            axis=1, dtype=np.float64
        )
    return monthly, month_labels


def normalized_level_coordinates(
    levels: np.ndarray, contract: dict[str, Any]
) -> np.ndarray:
    maxima = np.asarray(
        [
            len(contract["parameter_axes"][family][name]) - 1
            for family, name in AXIS_ORDER
        ],
        dtype=np.float64,
    )
    maxima[maxima <= 0.0] = 1.0
    return levels.astype(np.float64) / maxima


def concentration(values: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    positive = np.maximum(values, 0.0)
    totals = positive.sum(axis=-1)
    shares = np.divide(
        positive,
        totals[..., None],
        out=np.zeros_like(positive, dtype=np.float64),
        where=totals[..., None] > 0.0,
    )
    top_share = shares.max(axis=-1)
    hhi = np.square(shares).sum(axis=-1)
    entropy = np.zeros_like(totals, dtype=np.float64)
    safe = shares > 0.0
    log_shares = np.zeros_like(shares)
    log_shares[safe] = np.log(shares[safe])
    entropy = -(shares * log_shares).sum(axis=-1)
    normalizer = math.log(values.shape[-1]) if values.shape[-1] > 1 else 1.0
    entropy /= normalizer
    return top_share, hhi, entropy


def derive_selection_arrays(
    contract: dict[str, Any],
    levels: np.ndarray,
    result: dict[str, np.ndarray],
) -> dict[str, Any]:
    point_count = len(levels)
    contract_count = len(contract["paired_contracts"])
    if contract_count != 2 or result["actual_net"].shape[0] != point_count * 2:
        raise RuntimeError("paired task geometry mismatch")
    monthly_tasks, month_labels = aggregate_monthly(result)
    monthly = monthly_tasks.reshape(point_count, contract_count, -1)

    def paired(key: str) -> np.ndarray:
        shape = result[key].shape[1:]
        return result[key].reshape((point_count, contract_count) + shape)

    actual_net = paired("actual_net")
    stressed_net = paired("stressed_net")
    actual_dd = paired("actual_dd_pct")
    stressed_dd = paired("stressed_dd_pct")
    actual_minimum = paired("actual_min_balance")
    stressed_minimum = paired("stressed_min_balance")
    closes = paired("closes")
    components = paired("component_stressed")
    component_actual = paired("component_actual")
    component_closes = paired("component_closes")
    daily = paired("daily_stressed")
    epoch_actual = paired("epoch_actual")
    epoch_stressed = paired("epoch_stressed")
    baseline_epoch = epoch_stressed[0]
    epoch_scale = np.maximum(np.abs(baseline_epoch), 5.0)
    epoch_uplift = (epoch_stressed - baseline_epoch[None, :, :]) / epoch_scale
    worst_epoch_uplift = epoch_uplift.min(axis=2)
    baseline_total = stressed_net[0]
    total_scale = np.maximum(np.abs(baseline_total), 5.0)
    total_uplift = (stressed_net - baseline_total[None, :]) / total_scale

    component_top, component_hhi, component_entropy = concentration(components)
    month_top, month_hhi, month_entropy = concentration(monthly)
    positive_components = (components > 0.0).sum(axis=2)
    positive_months = (monthly > 0.0).sum(axis=2)
    component_breadth = (component_closes > 0).sum(axis=2)
    baseline_closes = closes[0]
    minimum_closes = np.maximum(60, np.floor(baseline_closes * 0.25)).astype(
        np.int64
    )

    core_eligible = (
        np.isfinite(actual_net)
        & np.isfinite(stressed_net)
        & np.isfinite(actual_dd)
        & np.isfinite(stressed_dd)
        & (actual_minimum > 0.0)
        & (stressed_minimum > 0.0)
        & (closes >= minimum_closes[None, :])
        & (component_breadth >= 4)
        & (positive_components >= 2)
        & (positive_months >= 6)
        & (component_top <= 0.85)
        & (month_top <= 0.85)
        & (epoch_actual > 0.0).all(axis=2)
        & (epoch_stressed > 0.0).all(axis=2)
    )
    native_reference_dd = np.asarray(
        [
            float(item["reference_selection"]["native_relative_equity_dd_pct"])
            for item in contract["paired_contracts"]
        ],
        dtype=np.float64,
    )
    baseline_proxy_dd = np.maximum(stressed_dd[0], 1.0e-12)
    dd_anchor_scale = native_reference_dd / baseline_proxy_dd
    native_equivalent_dd = stressed_dd * dd_anchor_scale[None, :]
    nominal_dd_pass = stressed_dd <= 20.0
    proportional_dd_pass = native_equivalent_dd <= 20.5
    breadth_score = 0.5 * (component_entropy + month_entropy)
    normalized = normalized_level_coordinates(levels, contract)
    baseline_normalized = normalized[0]
    distance = np.sqrt(np.square(normalized - baseline_normalized).mean(axis=1))
    return {
        "actual_net": actual_net,
        "stressed_net": stressed_net,
        "actual_dd": actual_dd,
        "stressed_dd": stressed_dd,
        "actual_minimum": actual_minimum,
        "stressed_minimum": stressed_minimum,
        "closes": closes,
        "components": components,
        "component_actual": component_actual,
        "component_closes": component_closes,
        "epoch_actual": epoch_actual,
        "epoch_stressed": epoch_stressed,
        "epoch_uplift": epoch_uplift,
        "worst_epoch_uplift": worst_epoch_uplift,
        "total_uplift": total_uplift,
        "monthly": monthly,
        "daily": daily,
        "month_labels": month_labels,
        "component_top_share": component_top,
        "component_hhi": component_hhi,
        "component_entropy": component_entropy,
        "month_top_share": month_top,
        "month_hhi": month_hhi,
        "month_entropy": month_entropy,
        "positive_components": positive_components,
        "positive_months": positive_months,
        "component_breadth": component_breadth,
        "minimum_closes": minimum_closes,
        "core_eligible": core_eligible,
        "native_equivalent_dd": native_equivalent_dd,
        "nominal_dd_pass": nominal_dd_pass,
        "proportional_dd_pass": proportional_dd_pass,
        "breadth_score": breadth_score,
        "normalized_levels": normalized,
        "distance_from_baseline": distance,
    }


def choose_basin_medoids(
    arrays: dict[str, Any], point_ids: list[str], maximum: int
) -> tuple[list[int], dict[int, list[str]]]:
    selected: list[int] = []
    roles: dict[int, list[str]] = {}
    coordinates = arrays["normalized_levels"]

    def ordered_for(contract_index: int | None) -> list[int]:
        if contract_index is None:
            core = arrays["core_eligible"].all(axis=1)
            proportional = arrays["proportional_dd_pass"].all(axis=1)
            primary = arrays["worst_epoch_uplift"].min(axis=1)
            drawdown = arrays["native_equivalent_dd"].max(axis=1)
            breadth = arrays["breadth_score"].min(axis=1)
        else:
            core = arrays["core_eligible"][:, contract_index]
            proportional = arrays["proportional_dd_pass"][:, contract_index]
            primary = arrays["worst_epoch_uplift"][:, contract_index]
            drawdown = arrays["native_equivalent_dd"][:, contract_index]
            breadth = arrays["breadth_score"][:, contract_index]
        pool = np.flatnonzero(core & proportional)
        if len(pool) == 0:
            pool = np.flatnonzero(core)
        return sorted(
            pool.tolist(),
            key=lambda index: (
                -float(primary[index]),
                float(drawdown[index]),
                -float(breadth[index]),
                float(arrays["distance_from_baseline"][index]),
                point_ids[index],
            ),
        )

    allocation = (
        ("PAIRED", None, min(4, maximum)),
        ("LIVE_CONTROL", 0, min(2, max(0, maximum - 4))),
        ("FIXED_REPLACEMENT", 1, min(2, max(0, maximum - 6))),
    )
    for role, contract_index, count in allocation:
        ordered = ordered_for(contract_index)
        added_for_role = 0
        for minimum_separation in (0.12, 0.06, 0.0):
            for index in ordered:
                if index in selected:
                    if role not in roles[index]:
                        roles[index].append(role)
                    continue
                if all(
                    float(
                        np.sqrt(
                            np.square(coordinates[index] - coordinates[other]).mean()
                        )
                    )
                    >= minimum_separation
                    for other in selected
                ):
                    selected.append(index)
                    roles[index] = [role]
                    added_for_role += 1
                    if added_for_role >= count or len(selected) >= maximum:
                        break
            if added_for_role >= count or len(selected) >= maximum:
                break
        if len(selected) >= maximum:
            break
    return selected, roles


def generate_plateau_points(
    contract: dict[str, Any], broad_levels: np.ndarray, medoids: list[int]
) -> tuple[np.ndarray, dict[int, list[int]]]:
    if not medoids:
        return np.empty((0, len(AXIS_ORDER)), dtype=np.int16), {}
    stage = contract["point_design"]["plateau_stage"]
    per_basin = int(stage["neighbors_per_basin"])
    maximum = int(stage["maximum_additional_points"])
    offsets = tuple(float(item) for item in stage["normalized_offsets"])
    level_counts = np.asarray(
        [len(contract["parameter_axes"][family][name]) for family, name in AXIS_ORDER],
        dtype=np.int16,
    )
    known_indexes = {
        row.astype(np.int16, copy=False).tobytes(): index
        for index, row in enumerate(broad_levels)
    }
    rows: list[np.ndarray] = []
    neighborhoods: dict[int, list[int]] = {}
    numerical_columns = [
        column
        for column, (family, name) in enumerate(AXIS_ORDER)
        if not isinstance(contract["parameter_axes"][family][name][0], str)
    ]
    for basin_number, medoid_index in enumerate(medoids):
        neighbors: list[int] = []
        trial = 0
        while len(neighbors) < per_basin and trial < 8192:
            row = broad_levels[medoid_index].copy()
            column = numerical_columns[
                (trial + basin_number * 19) % len(numerical_columns)
            ]
            offset = offsets[
                (trial // len(numerical_columns) + column + basin_number)
                % len(offsets)
            ]
            delta = max(
                1,
                int(round(abs(offset) * max(1, int(level_counts[column]) - 1))),
            )
            signed = -delta if offset < 0.0 else delta
            row[column] = np.int16(
                min(
                    int(level_counts[column]) - 1,
                    max(0, int(row[column]) + signed),
                )
            )
            key = row.astype(np.int16, copy=False).tobytes()
            if key not in known_indexes:
                if len(rows) >= maximum:
                    trial += 1
                    continue
                known_indexes[key] = len(broad_levels) + len(rows)
                rows.append(row)
            neighbor_index = known_indexes[key]
            if neighbor_index != medoid_index and neighbor_index not in neighbors:
                neighbors.append(neighbor_index)
            trial += 1
        neighborhoods[medoid_index] = neighbors
    plateau = (
        np.stack(rows)
        if rows
        else np.empty((0, len(AXIS_ORDER)), dtype=np.int16)
    )
    return plateau, neighborhoods


def add_local_plateau_statistics(
    arrays: dict[str, Any],
    medoids: list[int],
    designed_neighborhoods: dict[int, list[int]],
) -> None:
    point_count = len(arrays["stressed_net"])
    local_q10_net = np.full((point_count, 2), np.nan, dtype=np.float64)
    local_q10_uplift = np.full((point_count, 2), np.nan, dtype=np.float64)
    local_p90_dd = np.full((point_count, 2), np.nan, dtype=np.float64)
    local_positive_fraction = np.full((point_count, 2), np.nan, dtype=np.float64)
    baseline_total = arrays["stressed_net"][0]
    total_scale = np.maximum(np.abs(baseline_total), 5.0)
    neighborhoods: dict[int, list[int]] = {}
    for medoid in medoids:
        neighborhoods[medoid] = [medoid] + designed_neighborhoods.get(medoid, [])
        indexes = np.asarray(neighborhoods[medoid], dtype=np.int64)
        for contract_index in range(2):
            neighborhood_net = arrays["stressed_net"][indexes, contract_index]
            local_q10_net[medoid, contract_index] = np.quantile(
                neighborhood_net, 0.10
            )
            neighborhood_uplift = (
                neighborhood_net - baseline_total[contract_index]
            ) / total_scale[contract_index]
            local_q10_uplift[medoid, contract_index] = np.quantile(
                neighborhood_uplift, 0.10
            )
            local_p90_dd[medoid, contract_index] = np.quantile(
                arrays["native_equivalent_dd"][indexes, contract_index], 0.90
            )
            local_positive_fraction[medoid, contract_index] = float(
                np.mean(neighborhood_net > 0.0)
            )
    arrays["plateau_neighborhoods"] = neighborhoods
    arrays["local_q10_net"] = local_q10_net
    arrays["local_q10_uplift"] = local_q10_uplift
    arrays["local_p90_dd"] = local_p90_dd
    arrays["local_positive_fraction"] = local_positive_fraction
    robust = np.zeros_like(arrays["core_eligible"], dtype=bool)
    for medoid in medoids:
        if len(designed_neighborhoods.get(medoid, [])) != 64:
            continue
        robust[medoid] = (
            arrays["core_eligible"][medoid]
            & arrays["proportional_dd_pass"][medoid]
            & (local_q10_net[medoid] > 0.0)
            & (local_p90_dd[medoid] <= 20.5)
        )
    arrays["robust_eligible"] = robust


def ranked_point(
    arrays: dict[str, Any], point_ids: list[str], contract_index: int | None
) -> int | None:
    if contract_index is None:
        eligible = arrays["robust_eligible"].all(axis=1)
        primary = arrays["worst_epoch_uplift"].min(axis=1)
        secondary = arrays["local_q10_uplift"].min(axis=1)
        drawdown = arrays["native_equivalent_dd"].max(axis=1)
        breadth = arrays["breadth_score"].min(axis=1)
    else:
        eligible = arrays["robust_eligible"][:, contract_index]
        primary = arrays["worst_epoch_uplift"][:, contract_index]
        secondary = arrays["local_q10_uplift"][:, contract_index]
        drawdown = arrays["native_equivalent_dd"][:, contract_index]
        breadth = arrays["breadth_score"][:, contract_index]
    pool = np.flatnonzero(eligible)
    if len(pool) == 0:
        return None
    return sorted(
        pool.tolist(),
        key=lambda index: (
            -float(primary[index]),
            -float(secondary[index]),
            float(drawdown[index]),
            -float(breadth[index]),
            float(arrays["distance_from_baseline"][index]),
            point_ids[index],
        ),
    )[0]


def descriptive_contract_ceiling(
    arrays: dict[str, Any], point_ids: list[str], contract_index: int
) -> int | None:
    expanded_medoid = np.isfinite(arrays["local_q10_net"][:, contract_index])
    eligible = (
        arrays["core_eligible"][:, contract_index]
        & arrays["proportional_dd_pass"][:, contract_index]
        & expanded_medoid
    )
    pool = np.flatnonzero(eligible)
    if len(pool) == 0:
        return None
    return sorted(
        pool.tolist(),
        key=lambda index: (
            -float(arrays["worst_epoch_uplift"][index, contract_index]),
            -float(arrays["local_q10_uplift"][index, contract_index]),
            float(arrays["native_equivalent_dd"][index, contract_index]),
            -float(arrays["breadth_score"][index, contract_index]),
            float(arrays["distance_from_baseline"][index]),
            point_ids[index],
        ),
    )[0]


def point_summary(
    index: int | None,
    point_ids: list[str],
    payloads: list[str],
    stages: list[str],
    arrays: dict[str, Any],
) -> dict[str, Any] | None:
    if index is None:
        return None
    def optional_float(value: float) -> float | None:
        return float(value) if math.isfinite(float(value)) else None

    contracts: dict[str, Any] = {}
    for contract_index, contract_id in enumerate(("LIVE_CONTROL", "FIXED_REPLACEMENT")):
        contracts[contract_id] = {
            "actual_net_usd": float(arrays["actual_net"][index, contract_index]),
            "stressed_net_usd": float(arrays["stressed_net"][index, contract_index]),
            "worst_epoch_stressed_uplift_fraction": float(
                arrays["worst_epoch_uplift"][index, contract_index]
            ),
            "local_q10_stressed_uplift_fraction": optional_float(
                arrays["local_q10_uplift"][index, contract_index]
            ),
            "local_q10_stressed_net_usd": optional_float(
                arrays["local_q10_net"][index, contract_index]
            ),
            "local_p90_anchor_proportional_native_equivalent_dd_pct": optional_float(
                arrays["local_p90_dd"][index, contract_index]
            ),
            "proxy_stressed_closed_dd_pct": float(
                arrays["stressed_dd"][index, contract_index]
            ),
            "anchor_proportional_native_equivalent_dd_pct": float(
                arrays["native_equivalent_dd"][index, contract_index]
            ),
            "closed_lifecycles": int(arrays["closes"][index, contract_index]),
            "positive_components": int(
                arrays["positive_components"][index, contract_index]
            ),
            "positive_months": int(arrays["positive_months"][index, contract_index]),
            "component_hhi": float(arrays["component_hhi"][index, contract_index]),
            "largest_positive_component_share": float(
                arrays["component_top_share"][index, contract_index]
            ),
            "largest_positive_month_share": float(
                arrays["month_top_share"][index, contract_index]
            ),
            "robust_eligible": bool(
                arrays["robust_eligible"][index, contract_index]
            ),
        }
    return {
        "point_index": int(index),
        "point_id": point_ids[index],
        "stage": stages[index],
        "parameter_payload": json.loads(payloads[index]),
        "normalized_distance_from_exact_baseline": float(
            arrays["distance_from_baseline"][index]
        ),
        "contracts": contracts,
    }


def build_selection_frame(
    point_ids: list[str],
    payloads: list[str],
    stages: list[str],
    arrays: dict[str, Any],
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for point_index, point_id in enumerate(point_ids):
        for contract_index, contract_id in enumerate(
            ("LIVE_CONTROL", "FIXED_REPLACEMENT")
        ):
            records.append(
                {
                    "point_index": point_index,
                    "point_id": point_id,
                    "stage": stages[point_index],
                    "contract": contract_id,
                    "parameter_payload_json": payloads[point_index],
                    "actual_net_usd": arrays["actual_net"][point_index, contract_index],
                    "stressed_net_usd": arrays["stressed_net"][point_index, contract_index],
                    "actual_closed_dd_pct": arrays["actual_dd"][point_index, contract_index],
                    "stressed_closed_dd_pct": arrays["stressed_dd"][point_index, contract_index],
                    "native_equivalent_dd_pct": arrays["native_equivalent_dd"][point_index, contract_index],
                    "actual_minimum_balance_usd": arrays["actual_minimum"][point_index, contract_index],
                    "stressed_minimum_balance_usd": arrays["stressed_minimum"][point_index, contract_index],
                    "closed_lifecycles": arrays["closes"][point_index, contract_index],
                    "epoch_actual_net_json": json.dumps(arrays["epoch_actual"][point_index, contract_index].tolist()),
                    "epoch_stressed_net_json": json.dumps(arrays["epoch_stressed"][point_index, contract_index].tolist()),
                    "worst_epoch_stressed_uplift_fraction": arrays["worst_epoch_uplift"][point_index, contract_index],
                    "total_stressed_uplift_fraction": arrays["total_uplift"][point_index, contract_index],
                    "local_q10_stressed_net_usd": arrays["local_q10_net"][point_index, contract_index],
                    "local_q10_stressed_uplift_fraction": arrays["local_q10_uplift"][point_index, contract_index],
                    "local_p90_native_equivalent_dd_pct": arrays["local_p90_dd"][point_index, contract_index],
                    "local_positive_net_fraction": arrays["local_positive_fraction"][point_index, contract_index],
                    "positive_components": arrays["positive_components"][point_index, contract_index],
                    "component_breadth": arrays["component_breadth"][point_index, contract_index],
                    "component_hhi": arrays["component_hhi"][point_index, contract_index],
                    "largest_positive_component_share": arrays["component_top_share"][point_index, contract_index],
                    "positive_months": arrays["positive_months"][point_index, contract_index],
                    "month_hhi": arrays["month_hhi"][point_index, contract_index],
                    "largest_positive_month_share": arrays["month_top_share"][point_index, contract_index],
                    "core_eligible": arrays["core_eligible"][point_index, contract_index],
                    "nominal_dd_at_or_below_20": arrays["nominal_dd_pass"][point_index, contract_index],
                    "proportional_dd_at_or_below_20_5": arrays["proportional_dd_pass"][point_index, contract_index],
                    "robust_eligible": arrays["robust_eligible"][point_index, contract_index],
                    "normalized_distance_from_baseline": arrays["distance_from_baseline"][point_index],
                }
            )
    return pd.DataFrame.from_records(records)


def write_shortlist_daily(
    selected_indexes: Iterable[int],
    point_ids: list[str],
    result: dict[str, np.ndarray],
) -> None:
    unique = sorted(set(int(index) for index in selected_indexes))
    start_epoch = int(result["start_epoch"][0])
    day_count = result["daily_stressed"].shape[1]
    dates = pd.to_datetime(
        start_epoch + np.arange(day_count, dtype=np.int64) * 86400,
        unit="s",
        utc=True,
    )
    records: list[pd.DataFrame] = []
    for point_index in unique:
        for contract_index, contract_id in enumerate(
            ("LIVE_CONTROL", "FIXED_REPLACEMENT")
        ):
            task = point_index * 2 + contract_index
            records.append(
                pd.DataFrame(
                    {
                        "date_utc": dates,
                        "point_index": point_index,
                        "point_id": point_ids[point_index],
                        "contract": contract_id,
                        "stressed_closed_pnl_usd": result["daily_stressed"][task],
                    }
                )
            )
    atomic_parquet(DAILY_RESULT_PATH, pd.concat(records, ignore_index=True))


def pnl_to_returns(monthly_pnl: np.ndarray) -> np.ndarray:
    result = np.full_like(monthly_pnl, np.nan, dtype=np.float64)
    balances = np.full(monthly_pnl.shape[:-1], 100.0, dtype=np.float64)
    for month in range(monthly_pnl.shape[-1]):
        valid = balances > 0.0
        result[..., month] = np.divide(
            monthly_pnl[..., month],
            balances,
            out=np.full_like(balances, np.nan),
            where=valid,
        )
        balances = balances + monthly_pnl[..., month]
    return result


def stationary_bootstrap_means(
    series: np.ndarray,
    resamples: int = 10000,
    expected_block: float = 3.0,
    seed: int = 20260830,
) -> np.ndarray:
    values = np.asarray(series, dtype=np.float64)
    size = len(values)
    if size == 0:
        return np.asarray([], dtype=np.float64)
    rng = np.random.default_rng(seed)
    indexes = np.empty((resamples, size), dtype=np.int32)
    indexes[:, 0] = rng.integers(0, size, size=resamples)
    restart_probability = 1.0 / expected_block
    for column in range(1, size):
        restart = rng.random(resamples) < restart_probability
        starts = rng.integers(0, size, size=resamples)
        indexes[:, column] = np.where(
            restart, starts, (indexes[:, column - 1] + 1) % size
        )
    return values[indexes].mean(axis=1)


def deflated_sharpe(
    returns: np.ndarray, trial_count: int
) -> dict[str, Any]:
    values = np.asarray(returns, dtype=np.float64)
    values = values[np.isfinite(values)]
    if len(values) < 8 or np.std(values, ddof=1) <= 0.0:
        return {"identified": False, "reason": "insufficient nonconstant months"}
    monthly_sharpe = float(np.mean(values) / np.std(values, ddof=1))
    skew = float(stats.skew(values, bias=False))
    kurtosis = float(stats.kurtosis(values, fisher=False, bias=False))
    standard_error = math.sqrt(
        max(
            1.0e-12,
            (
                1.0
                - skew * monthly_sharpe
                + ((kurtosis - 1.0) / 4.0) * monthly_sharpe * monthly_sharpe
            )
            / (len(values) - 1),
        )
    )
    trials = max(2, int(trial_count))
    euler_gamma = 0.5772156649015329
    expected_maximum = standard_error * (
        (1.0 - euler_gamma) * stats.norm.ppf(1.0 - 1.0 / trials)
        + euler_gamma * stats.norm.ppf(1.0 - 1.0 / (trials * math.e))
    )
    probability = float(
        stats.norm.cdf((monthly_sharpe - expected_maximum) / standard_error)
    )
    return {
        "identified": True,
        "months": len(values),
        "trial_count_conservative": trials,
        "monthly_sharpe": monthly_sharpe,
        "annualized_sharpe": monthly_sharpe * math.sqrt(12.0),
        "skew": skew,
        "pearson_kurtosis": kurtosis,
        "expected_maximum_monthly_sharpe_under_multiple_trials": expected_maximum,
        "deflated_sharpe_probability": probability,
    }


def cscv_pbo(
    monthly_scores: np.ndarray, eligible_indexes: np.ndarray
) -> dict[str, Any]:
    if len(eligible_indexes) < 2 or monthly_scores.shape[1] < 16:
        return {"identified": False, "reason": "insufficient candidates or months"}
    values = monthly_scores[eligible_indexes]
    blocks = np.array_split(np.arange(values.shape[1]), 8)
    logits: list[float] = []
    selections: list[int] = []
    for chosen_blocks in itertools.combinations(range(8), 4):
        chosen_set = set(chosen_blocks)
        in_sample = np.concatenate([blocks[index] for index in chosen_blocks])
        out_sample = np.concatenate(
            [blocks[index] for index in range(8) if index not in chosen_set]
        )
        in_scores = np.nanmean(values[:, in_sample], axis=1)
        best_local = int(np.nanargmax(in_scores))
        out_scores = np.nanmean(values[:, out_sample], axis=1)
        selected_score = out_scores[best_local]
        rank = (float(np.sum(out_scores <= selected_score)) - 0.5) / len(out_scores)
        rank = min(1.0 - 1.0e-9, max(1.0e-9, rank))
        logits.append(math.log(rank / (1.0 - rank)))
        selections.append(int(eligible_indexes[best_local]))
    logit_array = np.asarray(logits, dtype=np.float64)
    return {
        "identified": True,
        "blocks": 8,
        "splits": len(logits),
        "candidate_count": len(eligible_indexes),
        "probability_of_backtest_overfitting": float(np.mean(logit_array <= 0.0)),
        "median_out_of_sample_rank_logit": float(np.median(logit_array)),
        "unique_in_sample_winners": len(set(selections)),
    }


def white_reality_check(
    monthly_uplift: np.ndarray,
    candidate_indexes: np.ndarray,
    resamples: int = 10000,
    seed: int = 20260831,
) -> dict[str, Any]:
    if len(candidate_indexes) < 2:
        return {"identified": False, "reason": "fewer than two candidates"}
    means = np.nanmean(monthly_uplift[candidate_indexes], axis=1)
    ordered = candidate_indexes[np.argsort(-means)[: min(256, len(means))]]
    matrix = monthly_uplift[ordered]
    observed = float(np.nanmax(np.nanmean(matrix, axis=1)))
    centered = matrix - np.nanmean(matrix, axis=1, keepdims=True)
    rng = np.random.default_rng(seed)
    size = matrix.shape[1]
    maxima: list[np.ndarray] = []
    completed = 0
    while completed < resamples:
        batch = min(250, resamples - completed)
        indexes = np.empty((batch, size), dtype=np.int32)
        indexes[:, 0] = rng.integers(0, size, size=batch)
        for column in range(1, size):
            restart = rng.random(batch) < (1.0 / 3.0)
            starts = rng.integers(0, size, size=batch)
            indexes[:, column] = np.where(
                restart, starts, (indexes[:, column - 1] + 1) % size
            )
        sampled = centered[:, indexes]
        maxima.append(np.nanmax(np.nanmean(sampled, axis=2), axis=0))
        completed += batch
    bootstrap_maxima = np.concatenate(maxima)
    return {
        "identified": True,
        "top_candidate_count": len(ordered),
        "stationary_bootstrap_resamples": resamples,
        "expected_block_months": 3.0,
        "observed_best_mean_normalized_monthly_uplift": observed,
        "white_reality_check_p_value": float(
            (1 + np.sum(bootstrap_maxima >= observed)) / (resamples + 1)
        ),
        "bootstrap_maximum_mean_q95": float(np.quantile(bootstrap_maxima, 0.95)),
    }


def parameter_sensitivity(
    contract: dict[str, Any],
    levels: np.ndarray,
    objective: np.ndarray,
    broad_count: int,
) -> dict[str, Any]:
    y = np.asarray(objective[:broad_count], dtype=np.float64)
    finite = np.isfinite(y)
    records: list[dict[str, Any]] = []
    for column, (family, name) in enumerate(AXIS_ORDER):
        x = levels[:broad_count, column].astype(np.int64)
        valid = finite
        grand = float(np.mean(y[valid]))
        total_ss = float(np.square(y[valid] - grand).sum())
        between = 0.0
        level_means: list[float] = []
        for level_index in range(
            len(contract["parameter_axes"][family][name])
        ):
            selected = valid & (x == level_index)
            mean = float(np.mean(y[selected])) if np.any(selected) else float("nan")
            level_means.append(mean)
            if np.any(selected):
                between += int(np.sum(selected)) * (mean - grand) ** 2
        correlation = stats.spearmanr(x[valid], y[valid]).statistic
        records.append(
            {
                "family": family,
                "axis": name,
                "axis_type": (
                    "categorical"
                    if isinstance(contract["parameter_axes"][family][name][0], str)
                    else "ordered_numeric"
                ),
                "eta_squared_main_effect": between / total_ss if total_ss > 0.0 else 0.0,
                "spearman_level_vs_objective": (
                    float(correlation) if math.isfinite(correlation) else None
                ),
                "low_to_high_mean_objective_difference": (
                    float(level_means[-1] - level_means[0])
                    if math.isfinite(level_means[0]) and math.isfinite(level_means[-1])
                    else None
                ),
                "level_means": level_means,
            }
        )
    records.sort(key=lambda item: -float(item["eta_squared_main_effect"]))
    family_records: list[dict[str, Any]] = []
    for family in dict.fromkeys(item[0] for item in AXIS_ORDER):
        family_axes = [item for item in records if item["family"] == family]
        family_records.append(
            {
                "family": family,
                "mean_axis_eta_squared": float(
                    np.mean([item["eta_squared_main_effect"] for item in family_axes])
                ),
                "maximum_axis_eta_squared": float(
                    np.max([item["eta_squared_main_effect"] for item in family_axes])
                ),
            }
        )
    family_records.sort(key=lambda item: -item["mean_axis_eta_squared"])
    return {"axes": records, "families": family_records}


def closed_balance_path_diagnostics(
    daily_pnl: np.ndarray, monthly_pnl: np.ndarray
) -> dict[str, Any]:
    daily_values = np.asarray(daily_pnl, dtype=np.float64)
    monthly_values = np.asarray(monthly_pnl, dtype=np.float64)
    balances = 100.0 + np.cumsum(daily_values)
    extended = np.concatenate((np.asarray([100.0]), balances))
    peaks = np.maximum.accumulate(extended)
    drawdowns = peaks - extended
    underwater = drawdowns[1:] > 1.0e-12
    longest = 0
    current = 0
    for value in underwater:
        current = current + 1 if value else 0
        longest = max(longest, current)
    monthly_returns = pnl_to_returns(monthly_values[None, :])[0]
    finite = monthly_returns[np.isfinite(monthly_returns)]
    mean = float(np.mean(finite)) if len(finite) else 0.0
    standard = float(np.std(finite, ddof=1)) if len(finite) > 1 else 0.0
    downside = np.minimum(finite, 0.0)
    downside_deviation = (
        float(np.sqrt(np.mean(np.square(downside)))) if len(downside) else 0.0
    )
    maximum_drawdown_usd = float(np.max(drawdowns))
    total_net = float(np.sum(daily_values))
    return {
        "stressed_closed_net_usd": total_net,
        "maximum_closed_balance_drawdown_usd": maximum_drawdown_usd,
        "recovery_net_over_maximum_closed_drawdown": (
            total_net / maximum_drawdown_usd if maximum_drawdown_usd > 0.0 else None
        ),
        "calendar_days_underwater_fraction": float(np.mean(underwater)),
        "longest_closed_balance_underwater_calendar_days": int(longest),
        "positive_months": int(np.sum(monthly_values > 0.0)),
        "negative_months": int(np.sum(monthly_values < 0.0)),
        "zero_months": int(np.sum(monthly_values == 0.0)),
        "best_month_stressed_net_usd": float(np.max(monthly_values)),
        "worst_month_stressed_net_usd": float(np.min(monthly_values)),
        "mean_monthly_return": mean,
        "annualized_monthly_sharpe": (
            mean / standard * math.sqrt(12.0) if standard > 0.0 else None
        ),
        "annualized_monthly_sortino": (
            mean / downside_deviation * math.sqrt(12.0)
            if downside_deviation > 0.0
            else None
        ),
    }


def descriptive_ceiling_analysis(
    arrays: dict[str, Any],
    point_index: int,
    contract_index: int,
    trial_count: int,
) -> dict[str, Any]:
    baseline_monthly = arrays["monthly"][0, contract_index]
    monthly_scale = max(
        abs(float(arrays["stressed_net"][0, contract_index]))
        / arrays["monthly"].shape[2],
        1.0,
    )
    uplift = (
        arrays["monthly"][point_index, contract_index] - baseline_monthly
    ) / monthly_scale
    bootstrap = stationary_bootstrap_means(
        uplift, seed=20260840 + contract_index
    )
    total = float(arrays["stressed_net"][point_index, contract_index])
    return {
        "point_index": int(point_index),
        "robust_eligible": bool(
            arrays["robust_eligible"][point_index, contract_index]
        ),
        "monthly_stressed_net_usd": arrays["monthly"][
            point_index, contract_index
        ].tolist(),
        "monthly_normalized_uplift_vs_exact_baseline": uplift.tolist(),
        "stationary_block_bootstrap_of_monthly_uplift": {
            "seed": 20260840 + contract_index,
            "resamples": 10000,
            "expected_block_months": 3.0,
            "observed_mean": float(np.mean(uplift)),
            "mean_q025": float(np.quantile(bootstrap, 0.025)),
            "mean_q50": float(np.quantile(bootstrap, 0.50)),
            "mean_q975": float(np.quantile(bootstrap, 0.975)),
            "probability_mean_at_or_below_zero": float(
                np.mean(bootstrap <= 0.0)
            ),
        },
        "deflated_sharpe": deflated_sharpe(
            pnl_to_returns(
                arrays["monthly"][point_index, contract_index][None, :]
            )[0],
            trial_count,
        ),
        "closed_balance_path": closed_balance_path_diagnostics(
            arrays["daily"][point_index, contract_index],
            arrays["monthly"][point_index, contract_index],
        ),
        "component_economics": [
            {
                "component": COMPONENT_NAMES[component],
                "stressed_net_usd": float(
                    arrays["components"][point_index, contract_index, component]
                ),
                "exact_baseline_component_stressed_net_usd": float(
                    arrays["components"][0, contract_index, component]
                ),
                "component_stressed_uplift_vs_exact_baseline_usd": float(
                    arrays["components"][point_index, contract_index, component]
                    - arrays["components"][0, contract_index, component]
                ),
                "closed_lifecycles": int(
                    arrays["component_closes"][
                        point_index, contract_index, component
                    ]
                ),
                "remaining_stressed_net_if_removed_usd": float(
                    total
                    - arrays["components"][
                        point_index, contract_index, component
                    ]
                ),
            }
            for component in range(6)
        ],
    }


def advanced_selection_analysis(
    contract: dict[str, Any],
    levels: np.ndarray,
    arrays: dict[str, Any],
    broad_count: int,
    paired_nominee: int | None,
    contract_ceilings: list[int | None],
) -> dict[str, Any]:
    live_net = arrays["stressed_net"][:, 0]
    replacement_net = arrays["stressed_net"][:, 1]
    live_worst = arrays["worst_epoch_uplift"][:, 0]
    replacement_worst = arrays["worst_epoch_uplift"][:, 1]
    net_spearman = stats.spearmanr(live_net, replacement_net).statistic
    worst_spearman = stats.spearmanr(live_worst, replacement_worst).statistic
    top_count = max(1, int(math.ceil(len(levels) * 0.10)))
    live_top = set(np.argsort(-live_net)[:top_count].tolist())
    replacement_top = set(np.argsort(-replacement_net)[:top_count].tolist())
    top_jaccard = len(live_top & replacement_top) / len(live_top | replacement_top)
    paired_objective = arrays["worst_epoch_uplift"].min(axis=1)
    sensitivity = parameter_sensitivity(
        contract, levels, paired_objective, broad_count
    )
    eligible = np.flatnonzero(arrays["core_eligible"].all(axis=1))
    monthly_returns = pnl_to_returns(arrays["monthly"])
    paired_monthly_returns = np.minimum(
        monthly_returns[:, 0, :], monthly_returns[:, 1, :]
    )
    baseline_monthly = arrays["monthly"][0]
    monthly_scale = np.maximum(
        np.abs(arrays["stressed_net"][0]) / arrays["monthly"].shape[2], 1.0
    )
    normalized_monthly_uplift = (
        arrays["monthly"] - baseline_monthly[None, :, :]
    ) / monthly_scale[None, :, None]
    paired_monthly_uplift = normalized_monthly_uplift.min(axis=1)
    analysis: dict[str, Any] = {
        "surface_transfer": {
            "all_point_stressed_net_spearman": float(net_spearman),
            "all_point_worst_epoch_uplift_spearman": float(worst_spearman),
            "top_decile_jaccard": float(top_jaccard),
            "points": len(levels),
        },
        "parameter_main_effects": sensitivity,
        "cscv_pbo": cscv_pbo(paired_monthly_returns, eligible),
        "white_reality_check": white_reality_check(
            paired_monthly_uplift, eligible
        ),
        "contract_specific_search_bias": {},
        "descriptive_contract_ceilings": {},
        "exact_baseline_diagnostics": {},
    }
    for contract_index, contract_id in enumerate(
        ("LIVE_CONTROL", "FIXED_REPLACEMENT")
    ):
        contract_eligible = np.flatnonzero(
            arrays["core_eligible"][:, contract_index]
        )
        analysis["contract_specific_search_bias"][contract_id] = {
            "cscv_pbo": cscv_pbo(
                monthly_returns[:, contract_index, :], contract_eligible
            ),
            "white_reality_check": white_reality_check(
                normalized_monthly_uplift[:, contract_index, :],
                contract_eligible,
                seed=20260832 + contract_index,
            ),
        }
        analysis["exact_baseline_diagnostics"][contract_id] = (
            descriptive_ceiling_analysis(
                arrays,
                0,
                contract_index,
                max(2, len(contract_eligible)),
            )
        )
        ceiling = contract_ceilings[contract_index]
        if ceiling is not None:
            analysis["descriptive_contract_ceilings"][contract_id] = (
                descriptive_ceiling_analysis(
                    arrays,
                    ceiling,
                    contract_index,
                    max(2, len(contract_eligible)),
                )
            )
    transfer: dict[str, Any] = {}
    for source_contract, index in enumerate(contract_ceilings):
        if index is None:
            continue
        other = 1 - source_contract
        other_rank = int(np.sum(arrays["stressed_net"][:, other] <= arrays["stressed_net"][index, other]))
        transfer[("LIVE_CONTROL", "FIXED_REPLACEMENT")[source_contract]] = {
            "point_index": int(index),
            "other_contract": ("LIVE_CONTROL", "FIXED_REPLACEMENT")[other],
            "other_contract_stressed_net_percentile": float(other_rank / len(levels)),
            "other_contract_robust_eligible": bool(arrays["robust_eligible"][index, other]),
        }
    analysis["contract_ceiling_transfer"] = transfer
    if paired_nominee is not None:
        uplift_series = paired_monthly_uplift[paired_nominee]
        bootstrap = stationary_bootstrap_means(uplift_series)
        nominee: dict[str, Any] = {
            "paired_monthly_normalized_uplift": uplift_series.tolist(),
            "stationary_block_bootstrap": {
                "seed": 20260830,
                "resamples": 10000,
                "expected_block_months": 3.0,
                "observed_mean": float(np.mean(uplift_series)),
                "mean_q025": float(np.quantile(bootstrap, 0.025)),
                "mean_q50": float(np.quantile(bootstrap, 0.50)),
                "mean_q975": float(np.quantile(bootstrap, 0.975)),
                "probability_mean_at_or_below_zero": float(np.mean(bootstrap <= 0.0)),
            },
            "deflated_sharpe": {},
            "leave_one_component_out": {},
        }
        trial_count = max(2, len(eligible))
        for contract_index, contract_id in enumerate(
            ("LIVE_CONTROL", "FIXED_REPLACEMENT")
        ):
            nominee["deflated_sharpe"][contract_id] = deflated_sharpe(
                monthly_returns[paired_nominee, contract_index], trial_count
            )
            total = arrays["stressed_net"][paired_nominee, contract_index]
            nominee["leave_one_component_out"][contract_id] = [
                {
                    "removed_component": COMPONENT_NAMES[component],
                    "remaining_stressed_net_usd": float(
                        total
                        - arrays["components"][
                            paired_nominee, contract_index, component
                        ]
                    ),
                }
                for component in range(6)
            ]
        analysis["paired_nominee"] = nominee
    return analysis


def write_selection_freeze(
    contract: dict[str, Any],
    feature: dict[str, Any],
    economic: dict[str, Any],
    levels: np.ndarray,
    point_ids: list[str],
    payloads: list[str],
    stages: list[str],
    arrays: dict[str, Any],
    broad_count: int,
    plateau_medoids: list[int],
    medoid_roles: dict[int, list[str]],
    paired_nominee: int | None,
    contract_ceilings: list[int | None],
) -> dict[str, Any]:
    mt5_priority = (
        {
            "contract": "FIXED_REPLACEMENT",
            "point_id": point_ids[paired_nominee],
            "role": "paired-transfer nominee; advance only if later unopened economics confirm",
        }
        if paired_nominee is not None
        else None
    )
    freeze = {
        "schema": "zeta-dd20-dual-portfolio-formula-selection-freeze-v1",
        "campaign": FAMILY,
        "status": "E1_E3_SELECTION_FROZEN_LATER_INTERVALS_UNOPENED",
        "contract_sha256": sha256(CONTRACT_PATH),
        "feature_anchor_passed": bool(feature["passed"]),
        "economic_anchor_passed": bool(economic["passed"]),
        "selection_information_boundary": ["E1", "E2", "E3"],
        "implementation_rules_frozen_before_nonbaseline_search": {
            "minimum_closed_lifecycles": "max(60, floor(25 percent of exact baseline closes)) per contract",
            "minimum_component_breadth": 4,
            "minimum_positive_components": 2,
            "minimum_positive_months": 6,
            "maximum_single_positive_component_share": 0.85,
            "maximum_single_positive_month_share": 0.85,
            "required_epoch_sign": "every E1-E3 actual and stressed net strictly positive",
            "nominal_proxy_dd_pct": 20.0,
            "anchor_proportional_native_equivalent_dd_pct": 20.5,
            "basin_allocation": "four paired-transfer, two LIVE_CONTROL ceiling and two FIXED_REPLACEMENT ceiling medoids, all unique when available",
            "local_plateau_neighbors": "64 one-axis ordered/numeric perturbations plus the medoid; categorical regimes remain identical",
            "local_candidate_boundary": "only an E1-E3 broad medoid can become a nominee; a post-selection neighbor cannot be promoted without its own unopened neighborhood",
            "local_required_q10_stressed_net": "strictly positive",
            "local_required_p90_native_equivalent_dd_pct": 20.5,
            "tie_break": contract["selection_protocol"]["lexicographic_order"],
        },
        "search_counts": {
            "broad_points": broad_count,
            "plateau_points": len(levels) - broad_count,
            "total_unique_points": len(levels),
            "paired_economic_tasks": len(levels) * 2,
        },
        "plateau_basin_medoids": [
            {
                "allocation_roles": medoid_roles.get(index, []),
                "designed_neighbor_count": len(
                    arrays["plateau_neighborhoods"].get(index, [])
                )
                - 1,
                "medoid": point_summary(
                    index, point_ids, payloads, stages, arrays
                ),
            }
            for index in plateau_medoids
        ],
        "baseline": point_summary(0, point_ids, payloads, stages, arrays),
        "paired_nominee": point_summary(
            paired_nominee, point_ids, payloads, stages, arrays
        ),
        "contract_specific_ceilings": {
            "LIVE_CONTROL": point_summary(
                contract_ceilings[0], point_ids, payloads, stages, arrays
            ),
            "FIXED_REPLACEMENT": point_summary(
                contract_ceilings[1], point_ids, payloads, stages, arrays
            ),
        },
        "contract_specific_ceiling_authority": "descriptive E1-E3 economic ceiling among the contract's expanded medoids; a ceiling that fails robust_eligible is not a nominee and later data cannot rescue it",
        "mt5_priority_frozen_before_later_data": mt5_priority,
        "runner_up_rescue": False,
    }
    atomic_json(SELECTION_FREEZE_PATH, freeze)
    return freeze


def later_periods(
    contract: dict[str, Any],
    basis: Basis,
    all_parameters: np.ndarray,
    all_levels: np.ndarray,
    point_ids: list[str],
    selected_indexes: list[int],
    spread_cost_multipliers: np.ndarray,
) -> dict[str, Any]:
    unique = list(dict.fromkeys([0] + selected_indexes))
    parameters = all_parameters[unique]
    levels = all_levels[unique]
    definitions = (
        (
            "E4",
            "2025-06-01T00:00:00",
            "2026-06-01T00:00:00",
            [("2025-06-01T00:00:00", "2026-06-01T00:00:00")],
        ),
        (
            "JUNE_2026",
            "2026-06-01T00:00:00",
            "2026-07-01T00:00:00",
            [("2026-06-01T00:00:00", "2026-07-01T00:00:00")],
        ),
        (
            "JULY_2026",
            "2026-07-01T00:00:00",
            "2026-08-01T00:00:00",
            [("2026-07-01T00:00:00", "2026-08-01T00:00:00")],
        ),
        (
            "JUNE_JULY_CONTINUOUS",
            "2026-06-01T00:00:00",
            "2026-08-01T00:00:00",
            [
                ("2026-06-01T00:00:00", "2026-07-01T00:00:00"),
                ("2026-07-01T00:00:00", "2026-08-01T00:00:00"),
            ],
        ),
    )
    output: dict[str, Any] = {
        "point_order": [point_ids[index] for index in unique],
        "periods": {},
    }
    for period_id, start, end, epochs in definitions:
        progress(f"opening frozen later interval {period_id} for {len(unique)} points")
        result = run_period(
            contract,
            basis,
            parameters,
            levels,
            start,
            end,
            epochs,
            spread_cost_multipliers,
        )
        period: dict[str, Any] = {}
        for local_index, global_index in enumerate(unique):
            point: dict[str, Any] = {}
            for contract_index, contract_id in enumerate(
                ("LIVE_CONTROL", "FIXED_REPLACEMENT")
            ):
                record = metric_record(result, local_index * 2 + contract_index)
                baseline_record = metric_record(result, contract_index)
                record["stressed_uplift_vs_exact_baseline_usd"] = float(
                    record["stressed_net_usd"]
                    - baseline_record["stressed_net_usd"]
                )
                record["actual_uplift_vs_exact_baseline_usd"] = float(
                    record["actual_net_usd"] - baseline_record["actual_net_usd"]
                )
                point[contract_id] = record
            period[point_ids[global_index]] = point
        output["periods"][period_id] = period
    return output


def final_proxy_judgement(
    freeze: dict[str, Any], later: dict[str, Any]
) -> dict[str, Any]:
    nominee = freeze["paired_nominee"]
    if nominee is None:
        return {
            "status": "NO_ROBUST_PAIRED_FORMULA_CLUE",
            "advance_to_mt5": False,
            "reason": "E1-E3 produced no point satisfying the predeclared paired plateau economics",
        }
    point_id = nominee["point_id"]
    contract_id = "FIXED_REPLACEMENT"
    checks: dict[str, bool] = {}
    for period_id in ("E4", "JUNE_2026", "JULY_2026", "JUNE_JULY_CONTINUOUS"):
        record = later["periods"][period_id][point_id][contract_id]
        checks[f"{period_id}_actual_positive"] = record["actual_net_usd"] > 0.0
        checks[f"{period_id}_stressed_positive"] = record["stressed_net_usd"] > 0.0
        checks[f"{period_id}_stressed_beats_baseline"] = (
            record["stressed_uplift_vs_exact_baseline_usd"] > 0.0
        )
    advance = all(checks.values())
    return {
        "status": (
            "MEANINGFUL_FIXED_REPLACEMENT_FORMULA_CLUE_ADVANCE_ONE_TO_MT5"
            if advance
            else "FROZEN_PAIRED_NOMINEE_NOT_CONFIRMED_NO_RUNNER_UP_RESCUE"
        ),
        "advance_to_mt5": advance,
        "mt5_contract": contract_id if advance else None,
        "mt5_point_id": point_id if advance else None,
        "checks": checks,
        "runner_up_rescue": False,
        "authority": "proxy clue only; no Live, Lab or release authority",
    }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        choices=("feature-anchor", "anchor", "full"),
        default="full",
        help="Run only the named declared economic phase; full includes both anchors.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    started = time.perf_counter()
    contract = load_contract()
    basis = build_basis(contract)
    feature = feature_anchor(contract, basis)
    payload: dict[str, Any] = {
        "schema": "zeta-dd20-dual-portfolio-formula-anchor-v1",
        "campaign": FAMILY,
        "contract_sha256": sha256(CONTRACT_PATH),
        "feature_anchor": feature,
        "elapsed_seconds": time.perf_counter() - started,
    }
    if not feature["passed"]:
        payload["status"] = "CORRECTION_REQUIRED_FEATURE_ANCHOR"
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 2
    if arguments.phase == "feature-anchor":
        payload["status"] = "FEATURE_ANCHOR_PASSED"
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    baseline = baseline_level_row(contract)
    calibration = spread_calibration(contract, basis)
    payload["spread_cost_calibration"] = {
        key: value for key, value in calibration.items() if key != "multipliers"
    }
    economic = economic_anchor(
        contract, basis, baseline, calibration["multipliers"]
    )
    payload["economic_anchor"] = economic
    payload["elapsed_seconds"] = time.perf_counter() - started
    if not economic["passed"]:
        payload["status"] = "CORRECTION_REQUIRED_ECONOMIC_ANCHOR"
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 3
    if arguments.phase == "anchor":
        payload["status"] = "FEATURE_AND_ECONOMIC_ANCHORS_PASSED"
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    selection_epochs = [
        ("2022-08-01T00:00:00", "2023-06-01T00:00:00"),
        ("2023-06-01T00:00:00", "2024-06-01T00:00:00"),
        ("2024-06-01T00:00:00", "2025-06-01T00:00:00"),
    ]
    progress("generating frozen 8,192-point atlas and Sobol broad surface")
    broad_levels = generate_broad_points(contract)
    broad_parameters, broad_ids, broad_payloads = resolve_points(
        broad_levels, contract
    )
    progress("running paired LIVE_CONTROL/FIXED_REPLACEMENT E1-E3 broad economics")
    broad_result = run_period(
        contract,
        basis,
        broad_parameters,
        broad_levels,
        "2022-08-01T00:00:00",
        "2025-06-01T00:00:00",
        selection_epochs,
        calibration["multipliers"],
    )
    progress("selecting at most eight separated E1-E3 basin medoids")
    broad_arrays = derive_selection_arrays(contract, broad_levels, broad_result)
    plateau_medoids, medoid_roles = choose_basin_medoids(
        broad_arrays,
        broad_ids,
        int(contract["point_design"]["plateau_stage"]["maximum_basin_medoids"]),
    )
    plateau_levels, designed_neighborhoods = generate_plateau_points(
        contract, broad_levels, plateau_medoids
    )
    if len(plateau_levels) > 0:
        plateau_parameters, _, _ = resolve_points(plateau_levels, contract)
        progress(
            f"running {len(plateau_levels)} predeclared local plateau points on E1-E3"
        )
        plateau_result = run_period(
            contract,
            basis,
            plateau_parameters,
            plateau_levels,
            "2022-08-01T00:00:00",
            "2025-06-01T00:00:00",
            selection_epochs,
            calibration["multipliers"],
        )
        levels = np.concatenate((broad_levels, plateau_levels), axis=0)
        selection_result = combine_period_results(broad_result, plateau_result)
    else:
        levels = broad_levels
        selection_result = broad_result
    parameters, point_ids, parameter_payloads = resolve_points(levels, contract)
    stages = ["BROAD"] * len(broad_levels) + ["PLATEAU"] * len(plateau_levels)
    if len(set(point_ids)) != len(point_ids):
        raise RuntimeError("canonical formula point collision")
    progress("calculating paired eligibility and owned 64-neighbor plateau economics")
    arrays = derive_selection_arrays(contract, levels, selection_result)
    add_local_plateau_statistics(
        arrays, plateau_medoids, designed_neighborhoods
    )
    paired_nominee = ranked_point(arrays, point_ids, None)
    contract_ceilings = [
        descriptive_contract_ceiling(arrays, point_ids, 0),
        descriptive_contract_ceiling(arrays, point_ids, 1),
    ]
    freeze = write_selection_freeze(
        contract,
        feature,
        economic,
        levels,
        point_ids,
        parameter_payloads,
        stages,
        arrays,
        len(broad_levels),
        plateau_medoids,
        medoid_roles,
        paired_nominee,
        contract_ceilings,
    )
    progress(
        "E1-E3 nominee freeze written; later intervals remain unopened at this boundary"
    )
    selection_frame = build_selection_frame(
        point_ids, parameter_payloads, stages, arrays
    )
    atomic_parquet(POINT_RESULT_PATH, selection_frame)
    shortlisted = [0] + plateau_medoids + [
        index
        for index in [paired_nominee] + contract_ceilings
        if index is not None
    ]
    write_shortlist_daily(shortlisted, point_ids, selection_result)
    progress("running advanced selection-bias, transfer and sensitivity diagnostics")
    advanced = advanced_selection_analysis(
        contract,
        levels,
        arrays,
        len(broad_levels),
        paired_nominee,
        contract_ceilings,
    )
    later = later_periods(
        contract,
        basis,
        parameters,
        levels,
        point_ids,
        [index for index in [paired_nominee] + contract_ceilings if index is not None],
        calibration["multipliers"],
    )
    judgement = final_proxy_judgement(freeze, later)
    result_payload = {
        "schema": "zeta-dd20-dual-portfolio-formula-proxy-result-v1",
        "campaign": FAMILY,
        "status": judgement["status"],
        "contract_sha256": sha256(CONTRACT_PATH),
        "feature_anchor": feature,
        "economic_anchor": economic,
        "spread_cost_calibration": {
            key: value for key, value in calibration.items() if key != "multipliers"
        },
        "selection": {
            "broad_points": len(broad_levels),
            "plateau_points": len(plateau_levels),
            "total_points": len(levels),
            "paired_tasks": len(levels) * 2,
            "events": int(selection_result["event_count"][0]),
            "core_eligible_counts": {
                "LIVE_CONTROL": int(arrays["core_eligible"][:, 0].sum()),
                "FIXED_REPLACEMENT": int(arrays["core_eligible"][:, 1].sum()),
                "PAIRED": int(arrays["core_eligible"].all(axis=1).sum()),
            },
            "robust_eligible_counts": {
                "LIVE_CONTROL": int(arrays["robust_eligible"][:, 0].sum()),
                "FIXED_REPLACEMENT": int(arrays["robust_eligible"][:, 1].sum()),
                "PAIRED": int(arrays["robust_eligible"].all(axis=1).sum()),
            },
            "freeze": freeze,
        },
        "advanced_analysis": advanced,
        "later_unopened_at_freeze_then_verified": later,
        "proxy_judgement": judgement,
        "artifacts": {
            "selection_freeze": {
                "path": relative(SELECTION_FREEZE_PATH),
                "sha256": sha256(SELECTION_FREEZE_PATH),
            },
            "selection_points": {
                "path": relative(POINT_RESULT_PATH),
                "sha256": sha256(POINT_RESULT_PATH),
                "rows": len(selection_frame),
            },
            "shortlist_daily_stressed": {
                "path": relative(DAILY_RESULT_PATH),
                "sha256": sha256(DAILY_RESULT_PATH),
            },
        },
        "elapsed_seconds": time.perf_counter() - started,
        "authority": "Optimization proxy evidence only; no Live, Lab or release authority",
    }
    atomic_json(RESULT_PATH, result_payload)
    print(
        json.dumps(
            {
                "campaign": FAMILY,
                "status": judgement["status"],
                "paired_nominee": (
                    point_ids[paired_nominee] if paired_nominee is not None else None
                ),
                "advance_to_mt5": judgement["advance_to_mt5"],
                "result": relative(RESULT_PATH),
                "elapsed_seconds": result_payload["elapsed_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
