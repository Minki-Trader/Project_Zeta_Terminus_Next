#!/usr/bin/env python3
"""Causal temporal-barrier training, ONNX export, and proxy execution.

The precheck path never constructs a label, fits a model, exports ONNX, opens the
locked period, or calculates candidate economics. Development and confirmation
are separately authority-gated by frozen repository evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import onnx
import onnxruntime as ort
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F


FAMILY_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = FAMILY_ROOT / "config" / "challenge-contract.json"
DECLARATION_PATH = (
    FAMILY_ROOT
    / "evidence"
    / "INDEPENDENT_CROSS_INDEX_FOUR_HOUR_BARRIER_ONNX_CHALLENGE_V1_DECLARATION.json"
)
FREEZE_PATH = (
    FAMILY_ROOT
    / "evidence"
    / "INDEPENDENT_CROSS_INDEX_FOUR_HOUR_BARRIER_ONNX_CHALLENGE_V1_IMPLEMENTATION_FREEZE.json"
)
ARTIFACT_ROOT = (
    PROJECT_ROOT
    / "lab"
    / "artifacts"
    / "independent-cross-index-four-hour-barrier-onnx-challenge-v1"
)
SYMBOLS = ("US100", "US30", "US500")
CLASSES = ("FLAT", "LONG", "SHORT")
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
INPUT_FILENAMES = {
    "US100": "US100_H1_BARS_20220701_20260821.csv",
    "US30": "US30_H1_BARS_20220701_20260821.csv",
    "US500": "US500_H1_BARS_20220701_20260821.csv",
}
SEED = 260831
TICK_SIZE = 0.01
TICK_VALUE_PER_LOT = 0.01
DOLLARS_PER_PRICE_POINT_PER_LOT = TICK_VALUE_PER_LOT / TICK_SIZE
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
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp,)):
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
    verify_file_record(declaration["frozen_files"]["contract"])
    verify_file_record(declaration["frozen_files"]["readme"])
    for symbol in SYMBOLS:
        authority = declaration["input_authorities"][symbol]
        copied = FAMILY_ROOT / "data" / "input" / INPUT_FILENAMES[symbol]
        if not copied.is_file():
            raise RuntimeError(f"missing family input copy: {copied}")
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
            raise RuntimeError(f"column contract mismatch: {symbol}")
        if frame["time_epoch"].duplicated().any():
            raise RuntimeError(f"duplicate epoch: {symbol}")
        parsed_server = pd.to_datetime(
            frame["time_server"], format="%Y.%m.%d %H:%M:%S", errors="raise"
        )
        parsed_epoch = pd.to_datetime(frame["time_epoch"], unit="s", utc=True).dt.tz_localize(None)
        if not parsed_server.equals(parsed_epoch):
            mismatch = int((parsed_server != parsed_epoch).sum())
            raise RuntimeError(f"server/epoch mismatch {symbol}: {mismatch}")
        frame = frame.loc[parsed_server < end_exclusive].copy()
        frame["time"] = parsed_server.loc[frame.index].to_numpy()
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
    base_times = per_symbol[SYMBOLS[0]].loc[common_epochs, "time"].reset_index(drop=True)
    output = pd.DataFrame(
        {
            "time_epoch": common_epochs.to_numpy(dtype=np.int64),
            "time": base_times.to_numpy(),
        }
    )
    for symbol in SYMBOLS:
        aligned = per_symbol[symbol].loc[common_epochs]
        other_times = aligned["time"].reset_index(drop=True)
        if not other_times.equals(base_times):
            raise RuntimeError(f"common server-time mismatch: {symbol}")
        for column in REQUIRED_COLUMNS[2:]:
            output[f"{symbol}_{column}"] = aligned[column].to_numpy()
    if output["time"].duplicated().any() or not output["time"].is_monotonic_increasing:
        raise RuntimeError("common H1 timeline is not unique and increasing")
    return output


@dataclass(frozen=True)
class FeatureState:
    values: np.ndarray
    valid: np.ndarray
    atr: dict[str, np.ndarray]


def build_price_features(frame: pd.DataFrame) -> FeatureState:
    channels: list[np.ndarray] = []
    atr_by_symbol: dict[str, np.ndarray] = {}
    for symbol in SYMBOLS:
        open_ = frame[f"{symbol}_open"].astype(float)
        high = frame[f"{symbol}_high"].astype(float)
        low = frame[f"{symbol}_low"].astype(float)
        close = frame[f"{symbol}_close"].astype(float)
        volume = frame[f"{symbol}_tick_volume"].astype(float)
        spread_price = frame[f"{symbol}_spread"].astype(float) * TICK_SIZE
        previous_close = close.shift(1)
        true_range = pd.concat(
            [
                high - low,
                (high - previous_close).abs(),
                (low - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = true_range.rolling(24, min_periods=24).mean()
        log_volume = np.log1p(volume)
        prior_volume_mean = log_volume.shift(1).rolling(24, min_periods=24).mean()
        prior_volume_std = log_volume.shift(1).rolling(24, min_periods=24).std(ddof=0)
        volume_z = (log_volume - prior_volume_mean) / prior_volume_std.where(
            prior_volume_std >= 1e-8, 1.0
        )
        symbol_channels = [
            np.log(close / previous_close),
            true_range / atr,
            (close - open_) / atr,
            volume_z,
            spread_price / atr,
        ]
        channels.extend(np.asarray(item, dtype=np.float64) for item in symbol_channels)
        atr_by_symbol[symbol] = atr.to_numpy(dtype=np.float64)
    values = np.column_stack(channels).astype(np.float32)
    valid = np.isfinite(values).all(axis=1)
    return FeatureState(values=values, valid=valid, atr=atr_by_symbol)


def structural_indices(
    frame: pd.DataFrame,
    feature_state: FeatureState,
    start: pd.Timestamp | None,
    end: pd.Timestamp,
) -> np.ndarray:
    times = frame["time"].to_numpy(dtype="datetime64[ns]")
    valid_prefix = np.concatenate(([0], np.cumsum(feature_state.valid.astype(np.int64))))
    selected: list[int] = []
    start64 = None if start is None else start.to_datetime64()
    end64 = end.to_datetime64()
    for index in range(96, len(frame) - 3):
        timestamp = times[index]
        if start64 is not None and timestamp < start64:
            continue
        if timestamp >= end64 or times[index + 3] >= end64:
            continue
        if valid_prefix[index] - valid_prefix[index - 48] != 48:
            continue
        if not all(
            np.isfinite(feature_state.atr[symbol][index - 1])
            and feature_state.atr[symbol][index - 1] > 0
            for symbol in SYMBOLS
        ):
            continue
        selected.append(index)
    return np.asarray(selected, dtype=np.int64)


def build_sequences(
    frame: pd.DataFrame, feature_state: FeatureState, indices: np.ndarray
) -> np.ndarray:
    output = np.empty((len(indices), 19, 48), dtype=np.float32)
    times = pd.DatetimeIndex(frame["time"])
    for row, index in enumerate(indices):
        output[row, :15, :] = feature_state.values[index - 48 : index].T
        decision = times[index]
        hour_angle = 2.0 * math.pi * decision.hour / 24.0
        weekday_angle = 2.0 * math.pi * decision.dayofweek / 7.0
        calendar = np.asarray(
            [
                math.sin(hour_angle),
                math.cos(hour_angle),
                math.sin(weekday_angle),
                math.cos(weekday_angle),
            ],
            dtype=np.float32,
        )
        output[row, 15:, :] = calendar[:, None]
    return output


def direction_wins(
    frame: pd.DataFrame,
    symbol: str,
    index: int,
    direction: int,
    atr: float,
) -> bool:
    spread_price = float(frame.at[index, f"{symbol}_spread"]) * TICK_SIZE
    decision_open = float(frame.at[index, f"{symbol}_open"])
    if direction == 1:
        entry = decision_open + spread_price
        stop = entry - atr
        take = entry + 1.5 * atr
        for future in range(index, index + 4):
            stop_hit = float(frame.at[future, f"{symbol}_low"]) <= stop
            take_hit = float(frame.at[future, f"{symbol}_high"]) >= take
            if stop_hit:
                return False
            if take_hit:
                return True
    else:
        entry = decision_open
        stop = entry + atr
        take = entry - 1.5 * atr
        for future in range(index, index + 4):
            ask_high = float(frame.at[future, f"{symbol}_high"]) + spread_price
            ask_low = float(frame.at[future, f"{symbol}_low"]) + spread_price
            stop_hit = ask_high >= stop
            take_hit = ask_low <= take
            if stop_hit:
                return False
            if take_hit:
                return True
    return False


def build_labels(
    frame: pd.DataFrame, feature_state: FeatureState, indices: np.ndarray
) -> np.ndarray:
    labels = np.zeros((len(indices), len(SYMBOLS)), dtype=np.int64)
    for row, index in enumerate(indices):
        for symbol_index, symbol in enumerate(SYMBOLS):
            atr = float(feature_state.atr[symbol][index - 1])
            long_positive = direction_wins(frame, symbol, index, 1, atr)
            short_positive = direction_wins(frame, symbol, index, 2, atr)
            if long_positive and not short_positive:
                labels[row, symbol_index] = 1
            elif short_positive and not long_positive:
                labels[row, symbol_index] = 2
    return labels


class TemporalBarrierNet(nn.Module):
    def __init__(self, channel_mean: np.ndarray, channel_std: np.ndarray) -> None:
        super().__init__()
        self.register_buffer(
            "channel_mean",
            torch.as_tensor(channel_mean, dtype=torch.float32).reshape(1, 19, 1),
        )
        self.register_buffer(
            "channel_std",
            torch.as_tensor(channel_std, dtype=torch.float32).reshape(1, 19, 1),
        )
        self.conv1 = nn.Conv1d(19, 32, kernel_size=5, padding=2)
        self.conv2 = nn.Conv1d(32, 32, kernel_size=3, padding=1)
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.linear1 = nn.Linear(32, 32)
        self.linear2 = nn.Linear(32, 9)

    def logits(self, sequence: torch.Tensor) -> torch.Tensor:
        value = (sequence - self.channel_mean) / self.channel_std
        value = F.gelu(self.conv1(value))
        value = F.gelu(self.conv2(value))
        value = self.pool(value).squeeze(-1)
        value = F.gelu(self.linear1(value))
        return self.linear2(value).reshape(-1, 3, 3)

    def forward(self, sequence: torch.Tensor) -> torch.Tensor:
        return torch.softmax(self.logits(sequence), dim=-1)


def seed_everything() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.use_deterministic_algorithms(True)


def channel_statistics(sequence: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = sequence.mean(axis=(0, 2), dtype=np.float64).astype(np.float32)
    std = sequence.std(axis=(0, 2), dtype=np.float64).astype(np.float32)
    std = np.where(std < 1e-8, 1.0, std).astype(np.float32)
    return mean, std


def class_weights(labels: np.ndarray) -> np.ndarray:
    weights = np.empty((3, 3), dtype=np.float32)
    for symbol_index in range(3):
        counts = np.bincount(labels[:, symbol_index], minlength=3).astype(np.float64)
        raw = 1.0 / np.sqrt(np.maximum(counts, 1.0))
        raw /= raw.mean()
        weights[symbol_index] = np.clip(raw, 0.5, 3.0).astype(np.float32)
    return weights


def weighted_loss(
    logits: torch.Tensor, targets: torch.Tensor, weights: torch.Tensor
) -> torch.Tensor:
    losses = [
        F.cross_entropy(logits[:, index, :], targets[:, index], weight=weights[index])
        for index in range(3)
    ]
    return torch.stack(losses).mean()


def train_epochs(
    model: TemporalBarrierNet,
    sequence: np.ndarray,
    labels: np.ndarray,
    weights_array: np.ndarray,
    epochs: int,
) -> None:
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=0.001, weight_decay=0.0001
    )
    weights = torch.from_numpy(weights_array)
    generator = torch.Generator().manual_seed(SEED)
    model.train()
    for _ in range(epochs):
        order = torch.randperm(len(sequence), generator=generator).numpy()
        for offset in range(0, len(order), 256):
            batch_indices = order[offset : offset + 256]
            batch_x = torch.from_numpy(sequence[batch_indices])
            batch_y = torch.from_numpy(labels[batch_indices])
            optimizer.zero_grad(set_to_none=True)
            loss = weighted_loss(model.logits(batch_x), batch_y, weights)
            loss.backward()
            optimizer.step()


def validation_loss(
    model: TemporalBarrierNet,
    sequence: np.ndarray,
    labels: np.ndarray,
    weights_array: np.ndarray,
) -> float:
    weights = torch.from_numpy(weights_array)
    total = 0.0
    count = 0
    model.eval()
    with torch.inference_mode():
        for offset in range(0, len(sequence), 512):
            batch_x = torch.from_numpy(sequence[offset : offset + 512])
            batch_y = torch.from_numpy(labels[offset : offset + 512])
            batch_loss = weighted_loss(model.logits(batch_x), batch_y, weights)
            batch_count = len(batch_x)
            total += float(batch_loss) * batch_count
            count += batch_count
    return total / count


def select_best_epoch(
    train_x: np.ndarray,
    train_y: np.ndarray,
    validation_x: np.ndarray,
    validation_y: np.ndarray,
) -> tuple[int, float, int]:
    seed_everything()
    mean, std = channel_statistics(train_x)
    weights = class_weights(train_y)
    model = TemporalBarrierNet(mean, std)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=0.001, weight_decay=0.0001
    )
    weight_tensor = torch.from_numpy(weights)
    generator = torch.Generator().manual_seed(SEED)
    best_epoch = 0
    best_loss = math.inf
    stale_epochs = 0
    completed_epochs = 0
    for epoch in range(1, 41):
        model.train()
        order = torch.randperm(len(train_x), generator=generator).numpy()
        for offset in range(0, len(order), 256):
            batch_indices = order[offset : offset + 256]
            batch_x = torch.from_numpy(train_x[batch_indices])
            batch_y = torch.from_numpy(train_y[batch_indices])
            optimizer.zero_grad(set_to_none=True)
            loss = weighted_loss(model.logits(batch_x), batch_y, weight_tensor)
            loss.backward()
            optimizer.step()
        completed_epochs = epoch
        observed = validation_loss(model, validation_x, validation_y, weights)
        if observed < best_loss - 0.00001:
            best_loss = observed
            best_epoch = epoch
            stale_epochs = 0
        else:
            stale_epochs += 1
            if stale_epochs >= 6:
                break
    if best_epoch < 1:
        raise RuntimeError("validation failed to select an epoch")
    return best_epoch, best_loss, completed_epochs


def fit_final_model(
    sequence: np.ndarray, labels: np.ndarray, epochs: int
) -> tuple[TemporalBarrierNet, np.ndarray]:
    seed_everything()
    mean, std = channel_statistics(sequence)
    weights = class_weights(labels)
    model = TemporalBarrierNet(mean, std)
    train_epochs(model, sequence, labels, weights, epochs)
    model.eval()
    return model, weights


def infer_torch(model: TemporalBarrierNet, sequence: np.ndarray) -> np.ndarray:
    batches: list[np.ndarray] = []
    model.eval()
    with torch.inference_mode():
        for offset in range(0, len(sequence), 512):
            output = model(torch.from_numpy(sequence[offset : offset + 512]))
            batches.append(output.numpy())
    return np.concatenate(batches, axis=0).astype(np.float32)


def export_and_verify_onnx(
    model: TemporalBarrierNet, sequence: np.ndarray, output_path: Path
) -> tuple[np.ndarray, dict[str, Any]]:
    if len(sequence) == 0:
        raise RuntimeError("cannot export a model without decision sequences")
    dummy = torch.from_numpy(sequence[: min(2, len(sequence))])
    torch.onnx.export(
        model,
        dummy,
        str(output_path),
        input_names=["sequence"],
        output_names=["probabilities"],
        dynamic_axes={"sequence": {0: "batch"}, "probabilities": {0: "batch"}},
        opset_version=17,
        do_constant_folding=True,
        dynamo=False,
    )
    checked = onnx.load(output_path)
    onnx.checker.check_model(checked)
    torch_probabilities = infer_torch(model, sequence)
    session = ort.InferenceSession(
        str(output_path), providers=["CPUExecutionProvider"]
    )
    ort_batches: list[np.ndarray] = []
    for offset in range(0, len(sequence), 512):
        ort_batches.append(
            session.run(
                ["probabilities"],
                {"sequence": sequence[offset : offset + 512]},
            )[0]
        )
    ort_probabilities = np.concatenate(ort_batches, axis=0).astype(np.float32)
    max_difference = float(np.max(np.abs(torch_probabilities - ort_probabilities)))
    argmax_mismatches = int(
        np.count_nonzero(
            np.argmax(torch_probabilities, axis=-1)
            != np.argmax(ort_probabilities, axis=-1)
        )
    )
    if max_difference > 0.00001 or argmax_mismatches != 0:
        raise RuntimeError(
            f"ONNX parity failure: difference={max_difference}, mismatches={argmax_mismatches}"
        )
    return ort_probabilities, {
        "path": output_path.name,
        "bytes": output_path.stat().st_size,
        "sha256": sha256_file(output_path),
        "parity_sequences": len(sequence),
        "maximum_absolute_probability_difference": max_difference,
        "argmax_mismatches": argmax_mismatches,
    }


def quarter_starts(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    values: list[pd.Timestamp] = []
    current = start
    while current < end:
        values.append(current)
        current = current + pd.DateOffset(months=3)
    return values


def quarter_name(timestamp: pd.Timestamp) -> str:
    return f"{timestamp.year}Q{((timestamp.month - 1) // 3) + 1}"


def label_distribution(labels: np.ndarray) -> dict[str, dict[str, int]]:
    output: dict[str, dict[str, int]] = {}
    for symbol_index, symbol in enumerate(SYMBOLS):
        counts = np.bincount(labels[:, symbol_index], minlength=3)
        output[symbol] = {
            class_name: int(counts[class_index])
            for class_index, class_name in enumerate(CLASSES)
        }
    return output


def train_period_models(
    frame: pd.DataFrame,
    feature_state: FeatureState,
    prediction_start: pd.Timestamp,
    prediction_end: pd.Timestamp,
    model_directory: Path,
) -> tuple[np.ndarray, list[dict[str, Any]], int]:
    all_indices = structural_indices(frame, feature_state, None, prediction_end)
    all_sequence = build_sequences(frame, feature_state, all_indices)
    all_labels = build_labels(frame, feature_state, all_indices)
    decision_times = pd.DatetimeIndex(frame.loc[all_indices, "time"])
    availability_times = pd.DatetimeIndex(
        frame.loc[all_indices + 3, "time"].to_numpy()
    ) + pd.Timedelta(hours=1)
    probabilities = np.full((len(frame), 3, 3), np.nan, dtype=np.float32)
    manifests: list[dict[str, Any]] = []
    total_fits = 0
    for quarter_start in quarter_starts(prediction_start, prediction_end):
        quarter_end = min(quarter_start + pd.DateOffset(months=3), prediction_end)
        lookback_start = quarter_start - pd.DateOffset(months=18)
        validation_start = quarter_start - pd.DateOffset(months=3)
        full_mask = (
            (decision_times >= lookback_start)
            & (availability_times <= quarter_start)
        )
        train_mask = full_mask & (decision_times < validation_start)
        validation_mask = full_mask & (decision_times >= validation_start)
        prediction_mask = (
            (decision_times >= quarter_start) & (decision_times < quarter_end)
        )
        full_count = int(full_mask.sum())
        train_count = int(train_mask.sum())
        validation_count = int(validation_mask.sum())
        prediction_count = int(prediction_mask.sum())
        if full_count < 2500:
            raise RuntimeError(
                f"minimum training sequences failed {quarter_name(quarter_start)}: {full_count}"
            )
        if train_count == 0 or validation_count == 0 or prediction_count == 0:
            raise RuntimeError(f"empty quarterly partition: {quarter_name(quarter_start)}")
        best_epoch, best_loss, validation_epochs = select_best_epoch(
            all_sequence[train_mask],
            all_labels[train_mask],
            all_sequence[validation_mask],
            all_labels[validation_mask],
        )
        total_fits += 1
        final_model, final_weights = fit_final_model(
            all_sequence[full_mask], all_labels[full_mask], best_epoch
        )
        total_fits += 1
        model_path = model_directory / f"barrier-{quarter_name(quarter_start)}.onnx"
        quarter_probabilities, onnx_record = export_and_verify_onnx(
            final_model, all_sequence[prediction_mask], model_path
        )
        prediction_indices = all_indices[prediction_mask]
        probabilities[prediction_indices] = quarter_probabilities
        manifests.append(
            {
                "quarter": quarter_name(quarter_start),
                "quarter_start": quarter_start.isoformat(),
                "quarter_end_exclusive": quarter_end.isoformat(),
                "lookback_start": lookback_start.isoformat(),
                "validation_start": validation_start.isoformat(),
                "training_sequences_full": full_count,
                "training_sequences_pre_validation": train_count,
                "validation_sequences": validation_count,
                "prediction_sequences": prediction_count,
                "best_validation_epoch": best_epoch,
                "completed_validation_epochs": validation_epochs,
                "best_validation_loss": best_loss,
                "full_training_label_distribution": label_distribution(
                    all_labels[full_mask]
                ),
                "final_class_weights": final_weights.tolist(),
                "onnx": onnx_record,
            }
        )
    return probabilities, manifests, total_fits


def normal_trading_days(
    frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp
) -> int:
    mask = (frame["time"] >= start) & (frame["time"] < end)
    dates = frame.loc[mask, "time"].dt.normalize()
    counts = dates.value_counts()
    return int((counts >= 20).sum())


def trade_path(
    frame: pd.DataFrame,
    symbol: str,
    index: int,
    direction: int,
    atr: float,
) -> dict[str, Any]:
    spread_price = float(frame.at[index, f"{symbol}_spread"]) * TICK_SIZE
    decision_open = float(frame.at[index, f"{symbol}_open"])
    exit_index = index + 3
    exit_reason = "TIME"
    if direction == 1:
        entry = decision_open + spread_price
        stop = entry - atr
        take = entry + 1.5 * atr
        exit_price = float(frame.at[exit_index, f"{symbol}_close"])
        for future in range(index, index + 4):
            if float(frame.at[future, f"{symbol}_low"]) <= stop:
                exit_index = future
                exit_price = stop
                exit_reason = "STOP"
                break
            if float(frame.at[future, f"{symbol}_high"]) >= take:
                exit_index = future
                exit_price = take
                exit_reason = "TAKE"
                break
        price_move = exit_price - entry
    else:
        entry = decision_open
        stop = entry + atr
        take = entry - 1.5 * atr
        exit_price = float(frame.at[exit_index, f"{symbol}_close"]) + spread_price
        for future in range(index, index + 4):
            ask_high = float(frame.at[future, f"{symbol}_high"]) + spread_price
            ask_low = float(frame.at[future, f"{symbol}_low"]) + spread_price
            if ask_high >= stop:
                exit_index = future
                exit_price = stop
                exit_reason = "STOP"
                break
            if ask_low <= take:
                exit_index = future
                exit_price = take
                exit_reason = "TAKE"
                break
        price_move = entry - exit_price
    return {
        "entry_price": entry,
        "exit_price": exit_price,
        "exit_index": exit_index,
        "exit_reason": exit_reason,
        "actual_price_move": price_move,
        "stressed_price_move": price_move - spread_price,
        "spread_price": spread_price,
        "stop_price": stop,
        "take_price": take,
    }


def select_candidate(
    probabilities: np.ndarray, role: dict[str, Any]
) -> tuple[int, int, float] | None:
    candidates: list[tuple[float, int, int]] = []
    threshold = float(role["minimum_direction_probability"])
    flat_margin = float(role["minimum_margin_over_flat"])
    opposite_margin = float(role["minimum_margin_over_opposite_direction"])
    for symbol_index in range(3):
        flat_probability = float(probabilities[symbol_index, 0])
        for direction in (1, 2):
            probability = float(probabilities[symbol_index, direction])
            opposite = float(probabilities[symbol_index, 3 - direction])
            if (
                probability + EPS >= threshold
                and probability - flat_probability + EPS >= flat_margin
                and probability - opposite + EPS >= opposite_margin
            ):
                candidates.append((probability, symbol_index, direction))
    if not candidates:
        return None
    candidates.sort(key=lambda value: (-value[0], value[1], value[2]))
    probability, symbol_index, direction = candidates[0]
    return symbol_index, direction, probability


def rounded_volume(balance: float, atr: float) -> float:
    if balance <= 0 or atr <= 0:
        return 0.0
    target_risk = balance * 0.02
    raw_volume = target_risk / (atr * DOLLARS_PER_PRICE_POINT_PER_LOT)
    volume = math.floor(raw_volume / 0.01 + EPS) * 0.01
    if volume >= 0.01:
        return round(volume, 2)
    minimum_lot_loss = atr * 0.01 * DOLLARS_PER_PRICE_POINT_PER_LOT
    if minimum_lot_loss <= balance * 0.04 + EPS:
        return 0.01
    return 0.0


def simulate_role(
    frame: pd.DataFrame,
    feature_state: FeatureState,
    probabilities: np.ndarray,
    role: dict[str, Any],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    decision_indices = np.flatnonzero(np.isfinite(probabilities).all(axis=(1, 2)))
    actual_balance = 100.0
    stressed_balance = 100.0
    actual_peak = 100.0
    stressed_peak = 100.0
    max_actual_drawdown_dollars = 0.0
    max_actual_drawdown_pct = 0.0
    max_stressed_drawdown_dollars = 0.0
    max_stressed_drawdown_pct = 0.0
    minimum_actual_balance = 100.0
    minimum_stressed_balance = 100.0
    next_available_index = 0
    trades: list[dict[str, Any]] = []
    yearly = {
        2024: {"actual": 0.0, "stressed": 0.0, "starts": 0},
        2025: {"actual": 0.0, "stressed": 0.0, "starts": 0},
        2026: {"actual": 0.0, "stressed": 0.0, "starts": 0},
    }
    for index in decision_indices:
        timestamp = pd.Timestamp(frame.at[index, "time"])
        if timestamp < start or timestamp >= end or index < next_available_index:
            continue
        selected = select_candidate(probabilities[index], role)
        if selected is None:
            continue
        symbol_index, direction, selected_probability = selected
        symbol = SYMBOLS[symbol_index]
        atr = float(feature_state.atr[symbol][index - 1])
        volume = rounded_volume(actual_balance, atr)
        if volume <= 0:
            continue
        path = trade_path(frame, symbol, index, direction, atr)
        actual_pnl = (
            float(path["actual_price_move"])
            * volume
            * DOLLARS_PER_PRICE_POINT_PER_LOT
        )
        stressed_pnl = (
            float(path["stressed_price_move"])
            * volume
            * DOLLARS_PER_PRICE_POINT_PER_LOT
        )
        actual_balance += actual_pnl
        stressed_balance += stressed_pnl
        actual_peak = max(actual_peak, actual_balance)
        stressed_peak = max(stressed_peak, stressed_balance)
        actual_drawdown_dollars = actual_peak - actual_balance
        stressed_drawdown_dollars = stressed_peak - stressed_balance
        max_actual_drawdown_dollars = max(
            max_actual_drawdown_dollars, actual_drawdown_dollars
        )
        max_stressed_drawdown_dollars = max(
            max_stressed_drawdown_dollars, stressed_drawdown_dollars
        )
        max_actual_drawdown_pct = max(
            max_actual_drawdown_pct,
            100.0 * actual_drawdown_dollars / actual_peak if actual_peak else math.inf,
        )
        max_stressed_drawdown_pct = max(
            max_stressed_drawdown_pct,
            100.0 * stressed_drawdown_dollars / stressed_peak
            if stressed_peak
            else math.inf,
        )
        minimum_actual_balance = min(minimum_actual_balance, actual_balance)
        minimum_stressed_balance = min(minimum_stressed_balance, stressed_balance)
        exit_index = int(path["exit_index"])
        next_available_index = exit_index + 1
        year = timestamp.year
        if year in yearly:
            yearly[year]["actual"] += actual_pnl
            yearly[year]["stressed"] += stressed_pnl
            yearly[year]["starts"] += 1
        trade = {
            "role": role["role"],
            "decision_epoch": int(frame.at[index, "time_epoch"]),
            "decision_time": timestamp.isoformat(),
            "exit_epoch": int(frame.at[exit_index, "time_epoch"]),
            "exit_time": pd.Timestamp(frame.at[exit_index, "time"]).isoformat(),
            "symbol": symbol,
            "direction": CLASSES[direction],
            "selected_probability": selected_probability,
            "flat_probability": float(probabilities[index, symbol_index, 0]),
            "opposite_probability": float(
                probabilities[index, symbol_index, 3 - direction]
            ),
            "atr": atr,
            "volume": volume,
            "planned_stop_loss_usd": atr
            * volume
            * DOLLARS_PER_PRICE_POINT_PER_LOT,
            "entry_price": path["entry_price"],
            "stop_price": path["stop_price"],
            "take_price": path["take_price"],
            "exit_price": path["exit_price"],
            "exit_reason": path["exit_reason"],
            "hold_common_h1_bars": exit_index - index + 1,
            "actual_pnl": actual_pnl,
            "stressed_pnl": stressed_pnl,
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
        "lifecycle_starts": len(trades),
        "normal_trading_days": day_count,
        "average_lifecycle_starts_per_normal_trading_day": len(trades) / day_count,
        "actual_net_usd": actual_net,
        "stressed_net_usd": stressed_net,
        "ending_actual_balance_usd": actual_balance,
        "ending_stressed_balance_usd": stressed_balance,
        "actual_closed_balance_drawdown_usd": max_actual_drawdown_dollars,
        "actual_closed_balance_drawdown_pct": max_actual_drawdown_pct,
        "stressed_closed_balance_drawdown_usd": max_stressed_drawdown_dollars,
        "stressed_closed_balance_drawdown_pct": max_stressed_drawdown_pct,
        "minimum_actual_balance_usd": minimum_actual_balance,
        "minimum_stressed_balance_usd": minimum_stressed_balance,
        "robust_recovery": stressed_net / max_actual_drawdown_dollars
        if max_actual_drawdown_dollars > 0
        else math.inf,
        "yearly": {str(year): values for year, values in yearly.items()},
        "symbol_starts": {
            symbol: sum(1 for trade in trades if trade["symbol"] == symbol)
            for symbol in SYMBOLS
        },
        "exit_reasons": {
            reason: sum(1 for trade in trades if trade["exit_reason"] == reason)
            for reason in ("STOP", "TAKE", "TIME")
        },
    }
    return metrics, trades


def development_pass(metrics: dict[str, Any], parity_passed: bool) -> bool:
    return bool(
        parity_passed
        and metrics["actual_net_usd"] > 149.97
        and metrics["stressed_net_usd"] > 127.786
        and metrics["actual_closed_balance_drawdown_pct"] <= 37.39
        and metrics["average_lifecycle_starts_per_normal_trading_day"] >= 3.0
        and metrics["yearly"]["2024"]["actual"] > 0
        and metrics["yearly"]["2024"]["stressed"] > 0
        and metrics["yearly"]["2025"]["actual"] > 0
        and metrics["yearly"]["2025"]["stressed"] > 0
    )


def write_trade_tape(path: Path, trades: Iterable[dict[str, Any]]) -> int:
    rows = list(trades)
    if not rows:
        path.write_text("", encoding="utf-8")
        return 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


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
    end = pd.Timestamp(contract["periods"]["development_selection"].split("/")[1])
    start = pd.Timestamp(contract["periods"]["development_selection"].split("/")[0])
    frame = load_common_frame(end)
    feature_state = build_price_features(frame)
    all_indices = structural_indices(frame, feature_state, None, end)
    development_indices = structural_indices(frame, feature_state, start, end)
    decision_times = pd.DatetimeIndex(frame.loc[all_indices, "time"])
    availability_times = pd.DatetimeIndex(
        frame.loc[all_indices + 3, "time"].to_numpy()
    ) + pd.Timedelta(hours=1)
    quarters: list[dict[str, Any]] = []
    for quarter_start in quarter_starts(start, end):
        quarter_end = min(quarter_start + pd.DateOffset(months=3), end)
        lookback_start = quarter_start - pd.DateOffset(months=18)
        validation_start = quarter_start - pd.DateOffset(months=3)
        full_mask = (
            (decision_times >= lookback_start)
            & (availability_times <= quarter_start)
        )
        train_mask = full_mask & (decision_times < validation_start)
        validation_mask = full_mask & (decision_times >= validation_start)
        prediction_mask = (
            (decision_times >= quarter_start) & (decision_times < quarter_end)
        )
        quarters.append(
            {
                "quarter": quarter_name(quarter_start),
                "training_sequences_full": int(full_mask.sum()),
                "training_sequences_pre_validation": int(train_mask.sum()),
                "validation_sequences": int(validation_mask.sum()),
                "prediction_sequences": int(prediction_mask.sum()),
            }
        )
    dummy_sequence = build_sequences(frame, feature_state, development_indices[:1])
    seed_everything()
    dummy_model = TemporalBarrierNet(np.zeros(19, np.float32), np.ones(19, np.float32))
    with torch.inference_mode():
        dummy_output = dummy_model(torch.from_numpy(dummy_sequence)).numpy()
    if dummy_output.shape != (1, 3, 3):
        raise RuntimeError(f"dummy model output mismatch: {dummy_output.shape}")
    if not np.allclose(dummy_output.sum(axis=-1), 1.0, atol=1e-6):
        raise RuntimeError("dummy model probabilities do not sum to one")
    if any(item["training_sequences_full"] < 2500 for item in quarters):
        raise RuntimeError("at least one quarterly structural training count is below 2500")
    return {
        "status": "STRUCTURAL_PRECHECK_PASS_NO_LABEL_NO_FIT_NO_OUTCOME_NO_ONNX",
        "common_rows": len(frame),
        "first_common_time": pd.Timestamp(frame.iloc[0]["time"]).isoformat(),
        "last_common_time": pd.Timestamp(frame.iloc[-1]["time"]).isoformat(),
        "complete_feature_rows": int(feature_state.valid.sum()),
        "structural_sequences_through_development": len(all_indices),
        "development_decision_sequences": len(development_indices),
        "development_normal_trading_days": normal_trading_days(frame, start, end),
        "quarterly_partitions": quarters,
        "dummy_input_shape": list(dummy_sequence.shape),
        "dummy_output_shape": list(dummy_output.shape),
        "labels_constructed": 0,
        "model_fits": 0,
        "onnx_files": 0,
        "candidate_predictions": 0,
        "candidate_trades": 0,
        "locked_confirmation_opened": False,
        "versions": {
            "python": os.sys.version.split()[0],
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "torch": torch.__version__,
            "onnx": onnx.__version__,
            "onnxruntime": ort.__version__,
        },
    }


def development(contract: dict[str, Any]) -> dict[str, Any]:
    start_text, end_text = contract["periods"]["development_selection"].split("/")
    start = pd.Timestamp(start_text)
    end = pd.Timestamp(end_text)
    frame = load_common_frame(end)
    feature_state = build_price_features(frame)
    temporary, final = staging_directory("development")
    try:
        model_directory = temporary / "models"
        model_directory.mkdir()
        probabilities, model_manifest, total_fits = train_period_models(
            frame, feature_state, start, end, model_directory
        )
        parity_passed = all(
            item["onnx"]["maximum_absolute_probability_difference"] <= 0.00001
            and item["onnx"]["argmax_mismatches"] == 0
            for item in model_manifest
        )
        role_results: list[dict[str, Any]] = []
        all_trades: list[dict[str, Any]] = []
        for role in contract["candidate_bundle"]["roles"]:
            metrics, trades = simulate_role(
                frame, feature_state, probabilities, role, start, end
            )
            metrics["complete_development_pass"] = development_pass(
                metrics, parity_passed
            )
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
        probability_indices = np.flatnonzero(
            np.isfinite(probabilities).all(axis=(1, 2))
        )
        probability_path = temporary / "development-probabilities.npz"
        np.savez_compressed(
            probability_path,
            decision_epochs=frame.loc[probability_indices, "time_epoch"].to_numpy(
                dtype=np.int64
            ),
            probabilities=probabilities[probability_indices],
        )
        manifest_path = temporary / "model-manifest.json"
        write_json(
            manifest_path,
            {
                "status": "VALID_COMPLETE_DEVELOPMENT_MODEL_MANIFEST",
                "models": model_manifest,
                "model_count": len(model_manifest),
                "total_model_fits": total_fits,
            },
        )
        tape_path = temporary / "decision-tape.csv"
        tape_rows = write_trade_tape(tape_path, all_trades)
        result = {
            "schema": "zeta-next-independent-four-hour-barrier-onnx-development-result-v1",
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
                "quarterly_models": len(model_manifest),
                "total_model_fits": total_fits,
                "onnx_parity_passed": parity_passed,
                "maximum_probability_difference": max(
                    item["onnx"]["maximum_absolute_probability_difference"]
                    for item in model_manifest
                ),
                "argmax_mismatches": sum(
                    item["onnx"]["argmax_mismatches"] for item in model_manifest
                ),
            },
            "roles": role_results,
            "complete_pass_count": len(passers),
            "selected_role": selected_role,
            "locked_confirmation_opened": False,
            "ea_source_files": 0,
            "mt5_paths": 0,
            "live_changed": False,
            "artifacts": {
                "model_manifest": {
                    "path": "model-manifest.json",
                    "bytes": manifest_path.stat().st_size,
                    "sha256": sha256_file(manifest_path),
                },
                "probabilities": {
                    "path": "development-probabilities.npz",
                    "bytes": probability_path.stat().st_size,
                    "sha256": sha256_file(probability_path),
                    "decision_rows": len(probability_indices),
                },
                "decision_tape": {
                    "path": "decision-tape.csv",
                    "bytes": tape_path.stat().st_size,
                    "sha256": sha256_file(tape_path),
                    "rows": tape_rows,
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
    development_directory = ARTIFACT_ROOT / "development"
    development_result_path = development_directory / "development-result.json"
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
    probability_record = development_result["artifacts"]["probabilities"]
    development_probability_path = development_directory / probability_record["path"]
    if (
        development_probability_path.stat().st_size != probability_record["bytes"]
        or sha256_file(development_probability_path) != probability_record["sha256"]
    ):
        raise RuntimeError("development probability authority mismatch")
    confirmation_start_text, confirmation_end_text = contract["periods"][
        "locked_confirmation"
    ].split("/")
    confirmation_start = pd.Timestamp(confirmation_start_text)
    confirmation_end = pd.Timestamp(confirmation_end_text)
    whole_start = pd.Timestamp(contract["periods"]["whole_v8_comparison"].split("/")[0])
    frame = load_common_frame(confirmation_end)
    feature_state = build_price_features(frame)
    temporary, final = staging_directory("confirmation")
    try:
        model_directory = temporary / "models"
        model_directory.mkdir()
        confirmation_probabilities, model_manifest, total_fits = train_period_models(
            frame,
            feature_state,
            confirmation_start,
            confirmation_end,
            model_directory,
        )
        combined_probabilities = confirmation_probabilities
        with np.load(development_probability_path) as stored:
            development_epochs = stored["decision_epochs"]
            development_probabilities = stored["probabilities"]
        epoch_to_index = {
            int(epoch): index for index, epoch in enumerate(frame["time_epoch"].to_numpy())
        }
        for epoch, values in zip(
            development_epochs, development_probabilities, strict=True
        ):
            index = epoch_to_index.get(int(epoch))
            if index is None:
                raise RuntimeError(f"development decision epoch missing: {epoch}")
            combined_probabilities[index] = values
        role = next(
            item
            for item in contract["candidate_bundle"]["roles"]
            if item["role"] == selected_role_name
        )
        whole_metrics, whole_trades = simulate_role(
            frame,
            feature_state,
            combined_probabilities,
            role,
            whole_start,
            confirmation_end,
        )
        development_metrics = next(
            item
            for item in development_result["roles"]
            if item["role"] == selected_role_name
        )
        development_actual_from_whole = sum(
            trade["actual_pnl"]
            for trade in whole_trades
            if pd.Timestamp(trade["decision_time"]) < confirmation_start
        )
        development_stressed_from_whole = sum(
            trade["stressed_pnl"]
            for trade in whole_trades
            if pd.Timestamp(trade["decision_time"]) < confirmation_start
        )
        if not math.isclose(
            development_actual_from_whole,
            development_metrics["actual_net_usd"],
            abs_tol=1e-8,
        ) or not math.isclose(
            development_stressed_from_whole,
            development_metrics["stressed_net_usd"],
            abs_tol=1e-8,
        ):
            raise RuntimeError("development economics did not reproduce in whole replay")
        confirmation_trades = [
            trade
            for trade in whole_trades
            if pd.Timestamp(trade["decision_time"]) >= confirmation_start
        ]
        confirmation_actual = sum(trade["actual_pnl"] for trade in confirmation_trades)
        confirmation_stressed = sum(
            trade["stressed_pnl"] for trade in confirmation_trades
        )
        confirmation_days = normal_trading_days(
            frame, confirmation_start, confirmation_end
        )
        whole_pass = bool(
            confirmation_actual > 0
            and confirmation_stressed > 0
            and len(confirmation_trades) / confirmation_days >= 3.0
            and whole_metrics["actual_net_usd"] > 409.81
            and whole_metrics["stressed_net_usd"] > 367.818
            and whole_metrics["actual_closed_balance_drawdown_pct"] <= 37.39
            and whole_metrics["robust_recovery"] > 3.295860215
            and all(
                whole_metrics["yearly"][str(year)][book] > 0
                for year in (2024, 2025, 2026)
                for book in ("actual", "stressed")
            )
        )
        manifest_path = temporary / "model-manifest.json"
        write_json(
            manifest_path,
            {
                "status": "VALID_COMPLETE_LOCKED_CONFIRMATION_MODEL_MANIFEST",
                "models": model_manifest,
                "model_count": len(model_manifest),
                "total_model_fits": total_fits,
            },
        )
        tape_path = temporary / "whole-decision-tape.csv"
        tape_rows = write_trade_tape(tape_path, whole_trades)
        result = {
            "schema": "zeta-next-independent-four-hour-barrier-onnx-confirmation-result-v1",
            "status": (
                "VALID_WHOLE_PROXY_SURVIVOR_EA_AND_NATIVE_CHALLENGE_REQUIRED"
                if whole_pass
                else "VALID_LOCKED_CONFIRMATION_OR_WHOLE_PROXY_NONCONFIRMATION_CLOSE_BEFORE_EA_MT5"
            ),
            "selected_role": selected_role_name,
            "confirmation": {
                "period": f"{confirmation_start.isoformat()}/{confirmation_end.isoformat()}",
                "lifecycle_starts": len(confirmation_trades),
                "normal_trading_days": confirmation_days,
                "average_lifecycle_starts_per_normal_trading_day": len(
                    confirmation_trades
                )
                / confirmation_days,
                "actual_net_usd": confirmation_actual,
                "stressed_net_usd": confirmation_stressed,
            },
            "whole": whole_metrics,
            "whole_proxy_pass": whole_pass,
            "quarterly_models": len(model_manifest),
            "total_model_fits": total_fits,
            "ea_required_before_victory": whole_pass,
            "proxy_victory_claimed": False,
            "mt5_paths": 0,
            "live_changed": False,
            "artifacts": {
                "model_manifest": {
                    "path": "model-manifest.json",
                    "bytes": manifest_path.stat().st_size,
                    "sha256": sha256_file(manifest_path),
                },
                "whole_decision_tape": {
                    "path": "whole-decision-tape.csv",
                    "bytes": tape_path.stat().st_size,
                    "sha256": sha256_file(tape_path),
                    "rows": tape_rows,
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
    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    contract, _ = verify_authorities(arguments.mode)
    if arguments.mode == "precheck":
        result = precheck(contract)
    elif arguments.mode == "development":
        result = development(contract)
    else:
        result = confirmation(contract)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
