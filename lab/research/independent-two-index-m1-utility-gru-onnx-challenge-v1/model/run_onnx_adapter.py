#!/usr/bin/env python3
"""Causal M1 four-action utility training, ONNX export and proxy execution.

Precheck constructs only timestamps and causal feature tensors and runs a
dummy-network ONNX parity check.  It never constructs an action label, fits a
model, emits a candidate prediction, simulates candidate economics, or opens
the locked confirmation period.
"""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import math
import os
import random
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

import numpy as np
import onnx
import onnxruntime as ort
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset


FAMILY_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = FAMILY_ROOT / "config" / "challenge-contract.json"
DECLARATION_PATH = (
    FAMILY_ROOT
    / "evidence"
    / "INDEPENDENT_TWO_INDEX_M1_UTILITY_GRU_ONNX_CHALLENGE_V1_DECLARATION.json"
)
FREEZE_PATH = (
    FAMILY_ROOT
    / "evidence"
    / "INDEPENDENT_TWO_INDEX_M1_UTILITY_GRU_ONNX_CHALLENGE_V1_IMPLEMENTATION_FREEZE.json"
)
DEVELOPMENT_EVIDENCE_PATH = (
    FAMILY_ROOT
    / "evidence"
    / "INDEPENDENT_TWO_INDEX_M1_UTILITY_GRU_ONNX_CHALLENGE_V1_DEVELOPMENT_RESULT.json"
)
ARTIFACT_ROOT = (
    PROJECT_ROOT
    / "lab"
    / "artifacts"
    / "independent-two-index-m1-utility-gru-onnx-challenge-v1"
)

SYMBOLS = ("US100", "US30")
ACTIONS = (
    ("US100_LONG", 0, 1),
    ("US100_SHORT", 0, -1),
    ("US30_LONG", 1, 1),
    ("US30_SHORT", 1, -1),
)
ROLE_THRESHOLDS = {
    "UTILITY_EDGE_R010": 0.10,
    "UTILITY_EDGE_R020": 0.20,
    "UTILITY_EDGE_R030": 0.30,
}
INPUT_FILENAMES = {
    "US100": "US100_M1.parquet",
    "US30": "US30_M1.parquet",
}
REQUIRED_COLUMNS = (
    "time",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
)
FEATURE_NAMES = (
    "US100_log_close_over_open",
    "US100_log_high_over_open",
    "US100_log_low_over_open",
    "US100_log_high_over_low",
    "US100_true_range_over_previous_close",
    "US100_log1p_tick_volume",
    "US100_spread_price_over_open",
    "US30_log_close_over_open",
    "US30_log_high_over_open",
    "US30_log_low_over_open",
    "US30_log_high_over_low",
    "US30_true_range_over_previous_close",
    "US30_log1p_tick_volume",
    "US30_spread_price_over_open",
    "US100_minus_US30_log_close_over_open",
)
TEST_BLOCKS = (
    ("2024Q1", "2024-01-01", "2024-04-01"),
    ("2024Q2", "2024-04-01", "2024-07-01"),
    ("2024Q3", "2024-07-01", "2024-10-01"),
    ("2024Q4", "2024-10-01", "2025-01-01"),
    ("2025Q1", "2025-01-01", "2025-04-01"),
    ("2025Q2", "2025-04-01", "2025-07-01"),
    ("2025Q3", "2025-07-01", "2025-10-01"),
    ("2025Q4", "2025-10-01", "2026-01-01"),
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
SEQUENCE_ROWS = 60
FEATURE_COUNT = 15
LABEL_BARS = 15
STOP_R = -1.0
TAKE_R = 1.5
MODEL_SEED = 260831005
INITIAL_TRAINING_START_EPOCH = int(pd.Timestamp("2022-07-01T00:00:00").timestamp())
GRU_HIDDEN = 32
HEAD_HIDDEN = 32
EPOCHS = 8
BATCH_SIZE = 512
LEARNING_RATE = 0.001
WEIGHT_DECAY = 0.0001
HUBER_DELTA = 0.25
STANDARD_DEVIATION_FLOOR = 1e-8
STANDARDIZED_CLIP = 8.0
EPSILON = 1e-12


@dataclass
class PreparedData:
    frame: pd.DataFrame
    decision_positions: np.ndarray
    decision_epochs: np.ndarray
    decision_times: pd.DatetimeIndex
    features: np.ndarray
    true_range: np.ndarray


@dataclass
class ActionPaths:
    actual_r: np.ndarray
    extra_stress_r: np.ndarray
    exit_offset: np.ndarray
    exit_reason: np.ndarray
    atr_price: np.ndarray


@dataclass
class RoleBook:
    role: str
    actual_balance: float = INITIAL_BALANCE_USD
    stressed_balance: float = INITIAL_BALANCE_USD
    starts: int = 0
    threshold_blocks: int = 0
    risk_blocks: int = 0


class UtilityGRU(nn.Module):
    def __init__(self, feature_mean: np.ndarray, feature_std: np.ndarray) -> None:
        super().__init__()
        mean = torch.as_tensor(feature_mean, dtype=torch.float32).reshape(1, 1, -1)
        std = torch.as_tensor(feature_std, dtype=torch.float32).reshape(1, 1, -1)
        self.register_buffer("feature_mean", mean)
        self.register_buffer("feature_std", std)
        self.gru = nn.GRU(
            input_size=FEATURE_COUNT,
            hidden_size=GRU_HIDDEN,
            num_layers=1,
            batch_first=True,
        )
        self.hidden = nn.Linear(GRU_HIDDEN, HEAD_HIDDEN)
        self.activation = nn.GELU()
        self.output = nn.Linear(HEAD_HIDDEN, len(ACTIONS))

    def forward(self, sequence: torch.Tensor) -> torch.Tensor:
        normalized = (sequence - self.feature_mean) / self.feature_std
        normalized = torch.clamp(normalized, -STANDARDIZED_CLIP, STANDARDIZED_CLIP)
        _, last = self.gru(normalized)
        hidden = self.activation(self.hidden(last[-1]))
        return self.output(hidden)


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
            allow_nan=False,
            default=json_default,
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
        "zeta-next-independent-two-index-m1-utility-gru-onnx-challenge-v1-contract"
    ):
        raise RuntimeError("contract schema mismatch")
    if declaration.get("status") != (
        "DECLARED_PREINPUT_PRETENSOR_PRELABEL_PREFIT_PREONNX_PREOUTCOME"
    ):
        raise RuntimeError("declaration status mismatch")
    for record in declaration["frozen_files"].values():
        verify_file_record(record)
    verify_file_record(declaration["selection_authority"])
    for key, authority in declaration["source_authorities"].items():
        verify_file_record(authority)
        symbol = key.split("_", 1)[0]
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


def validate_source(frame: pd.DataFrame, symbol: str) -> None:
    if tuple(frame.columns) != REQUIRED_COLUMNS:
        raise RuntimeError(f"source column mismatch: {symbol}")
    if frame["time"].duplicated().any():
        raise RuntimeError(f"duplicate source epoch: {symbol}")
    frame.sort_values("time", inplace=True, kind="mergesort")
    epoch = frame["time"].to_numpy(dtype=np.int64)
    if np.any(epoch % 60 != 0) or np.any(np.diff(epoch) <= 0):
        raise RuntimeError(f"invalid M1 timestamp cadence: {symbol}")
    prices = frame[["open", "high", "low", "close"]].to_numpy(dtype=np.float64)
    if not np.isfinite(prices).all() or np.any(prices <= 0.0):
        raise RuntimeError(f"invalid source price: {symbol}")
    if np.any(frame["high"].to_numpy() < frame[["open", "close"]].max(axis=1)):
        raise RuntimeError(f"high below open/close: {symbol}")
    if np.any(frame["low"].to_numpy() > frame[["open", "close"]].min(axis=1)):
        raise RuntimeError(f"low above open/close: {symbol}")
    if np.any(frame["spread"].to_numpy(dtype=float) < 0.0):
        raise RuntimeError(f"negative spread: {symbol}")


def load_common_frame(end_exclusive: pd.Timestamp) -> pd.DataFrame:
    end_epoch = int(end_exclusive.timestamp())
    frames: dict[str, pd.DataFrame] = {}
    for symbol in SYMBOLS:
        path = FAMILY_ROOT / "data" / "input" / INPUT_FILENAMES[symbol]
        frame = pd.read_parquet(path, columns=list(REQUIRED_COLUMNS))
        validate_source(frame, symbol)
        frame = frame.loc[frame["time"] < end_epoch].copy()
        frame.set_index("time", inplace=True, verify_integrity=True)
        frame = frame[
            ["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
        ].rename(columns=lambda column: f"{symbol}_{column}")
        frames[symbol] = frame
    common = frames[SYMBOLS[0]].join(frames[SYMBOLS[1]], how="inner").sort_index()
    if common.empty or common.index.duplicated().any():
        raise RuntimeError("common M1 frame is empty or duplicated")
    epoch = common.index.to_numpy(dtype=np.int64)
    if np.any(epoch % 60 != 0) or np.any(np.diff(epoch) <= 0):
        raise RuntimeError("common M1 timeline is invalid")
    common.insert(0, "time", pd.to_datetime(epoch, unit="s", utc=True).tz_localize(None))
    return common


def complete_decision_positions(frame: pd.DataFrame) -> np.ndarray:
    epoch = frame.index.to_numpy(dtype=np.int64)
    candidates = np.flatnonzero(epoch % 900 == 0)
    candidates = candidates[
        (candidates >= SEQUENCE_ROWS + 1)
        & (candidates + LABEL_BARS - 1 < len(frame))
    ]
    valid = (
        (epoch[candidates - (SEQUENCE_ROWS + 1)] == epoch[candidates] - 3660)
        & (epoch[candidates - 1] == epoch[candidates] - 60)
        & (epoch[candidates + LABEL_BARS - 1] == epoch[candidates] + 840)
    )
    return candidates[valid].astype(np.int64)


def build_row_features(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    rows = np.empty((len(frame), FEATURE_COUNT), dtype=np.float32)
    true_ranges = np.empty((len(frame), len(SYMBOLS)), dtype=np.float64)
    body_features: list[np.ndarray] = []
    for symbol_index, symbol in enumerate(SYMBOLS):
        open_price = frame[f"{symbol}_open"].to_numpy(dtype=np.float64)
        high = frame[f"{symbol}_high"].to_numpy(dtype=np.float64)
        low = frame[f"{symbol}_low"].to_numpy(dtype=np.float64)
        close = frame[f"{symbol}_close"].to_numpy(dtype=np.float64)
        volume = frame[f"{symbol}_tick_volume"].to_numpy(dtype=np.float64)
        spread = frame[f"{symbol}_spread"].to_numpy(dtype=np.float64) * POINT
        previous_close = np.roll(close, 1)
        previous_close[0] = np.nan
        true_range = np.maximum.reduce(
            [high - low, np.abs(high - previous_close), np.abs(low - previous_close)]
        )
        true_ranges[:, symbol_index] = true_range
        body = np.log(close / open_price)
        body_features.append(body)
        offset = symbol_index * 7
        rows[:, offset + 0] = body.astype(np.float32)
        rows[:, offset + 1] = np.log(high / open_price).astype(np.float32)
        rows[:, offset + 2] = np.log(low / open_price).astype(np.float32)
        rows[:, offset + 3] = np.log(high / low).astype(np.float32)
        rows[:, offset + 4] = (true_range / previous_close).astype(np.float32)
        rows[:, offset + 5] = np.log1p(volume).astype(np.float32)
        rows[:, offset + 6] = (spread / open_price).astype(np.float32)
    rows[:, 14] = (body_features[0] - body_features[1]).astype(np.float32)
    return rows, true_ranges


def construct_feature_sequences(
    row_features: np.ndarray, decision_positions: np.ndarray
) -> np.ndarray:
    sequences = np.empty(
        (len(decision_positions), SEQUENCE_ROWS, FEATURE_COUNT), dtype=np.float32
    )
    for output_index, position in enumerate(decision_positions):
        sequences[output_index] = row_features[position - SEQUENCE_ROWS : position]
    if not np.isfinite(sequences).all():
        raise RuntimeError("nonfinite causal feature tensor")
    return sequences


def prepare_data(end_exclusive: pd.Timestamp) -> PreparedData:
    frame = load_common_frame(end_exclusive)
    positions = complete_decision_positions(frame)
    frame_epochs = frame.index.to_numpy(dtype=np.int64)
    positions = positions[frame_epochs[positions] >= INITIAL_TRAINING_START_EPOCH]
    row_features, true_range = build_row_features(frame)
    features = construct_feature_sequences(row_features, positions)
    epochs = frame_epochs[positions]
    times = pd.to_datetime(epochs, unit="s", utc=True).tz_localize(None)
    return PreparedData(
        frame=frame,
        decision_positions=positions,
        decision_epochs=epochs,
        decision_times=times,
        features=features,
        true_range=true_range,
    )


def period_mask(
    times: pd.DatetimeIndex, start: pd.Timestamp, end: pd.Timestamp
) -> np.ndarray:
    return np.asarray((times >= start) & (times < end), dtype=bool)


def normal_trading_days(
    times: pd.DatetimeIndex, start: pd.Timestamp, end: pd.Timestamp
) -> tuple[int, dict[str, int]]:
    selected = times[(times >= start) & (times < end)]
    counts = pd.Series(selected.date).value_counts().sort_index()
    distribution = {
        "calendar_dates": int(len(counts)),
        "dates_at_least_60_complete_windows": int((counts >= 60).sum()),
        "dates_at_least_80_complete_windows": int((counts >= 80).sum()),
        "median_complete_windows": int(counts.median()) if len(counts) else 0,
    }
    return distribution["dates_at_least_60_complete_windows"], distribution


def fit_geometry(times: pd.DatetimeIndex) -> list[dict[str, Any]]:
    initial_start = pd.Timestamp("2022-07-01T00:00:00")
    geometry: list[dict[str, Any]] = []
    for name, start_text, end_text in TEST_BLOCKS:
        start = pd.Timestamp(start_text)
        end = pd.Timestamp(end_text)
        matured = times + pd.Timedelta(minutes=LABEL_BARS)
        train = (times >= initial_start) & (matured < start)
        test = (times >= start) & (times < end)
        geometry.append(
            {
                "block": name,
                "train_rows": int(train.sum()),
                "test_rows": int(test.sum()),
                "first_train": times[train][0].isoformat() if np.any(train) else None,
                "last_train": times[train][-1].isoformat() if np.any(train) else None,
                "first_test": times[test][0].isoformat() if np.any(test) else None,
                "last_test": times[test][-1].isoformat() if np.any(test) else None,
            }
        )
    return geometry


def set_deterministic_seed() -> None:
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    random.seed(MODEL_SEED)
    np.random.seed(MODEL_SEED)
    torch.manual_seed(MODEL_SEED)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(min(4, max(1, os.cpu_count() or 1)))


def feature_normalization(sequences: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    flattened = sequences.reshape(-1, FEATURE_COUNT).astype(np.float64)
    mean = flattened.mean(axis=0)
    std = flattened.std(axis=0, ddof=0)
    std = np.maximum(std, STANDARD_DEVIATION_FLOOR)
    return mean.astype(np.float32), std.astype(np.float32)


def train_model(
    train_x: np.ndarray,
    train_y: np.ndarray,
    feature_mean: np.ndarray,
    feature_std: np.ndarray,
) -> tuple[UtilityGRU, list[float]]:
    set_deterministic_seed()
    model = UtilityGRU(feature_mean, feature_std)
    dataset = TensorDataset(
        torch.from_numpy(np.ascontiguousarray(train_x)),
        torch.from_numpy(np.ascontiguousarray(train_y.astype(np.float32))),
    )
    generator = torch.Generator().manual_seed(MODEL_SEED)
    loader = DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=0,
        generator=generator,
        drop_last=False,
    )
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY
    )
    loss_function = nn.HuberLoss(delta=HUBER_DELTA, reduction="mean")
    losses: list[float] = []
    model.train()
    for _ in range(EPOCHS):
        weighted_loss = 0.0
        samples = 0
        for batch_x, batch_y in loader:
            optimizer.zero_grad(set_to_none=True)
            prediction = model(batch_x)
            loss = loss_function(prediction, batch_y)
            loss.backward()
            optimizer.step()
            batch_count = len(batch_x)
            weighted_loss += float(loss.detach()) * batch_count
            samples += batch_count
        losses.append(weighted_loss / samples)
    model.eval()
    return model, losses


def infer_torch(model: UtilityGRU, sequences: np.ndarray) -> np.ndarray:
    outputs: list[np.ndarray] = []
    model.eval()
    with torch.no_grad():
        for offset in range(0, len(sequences), 2048):
            batch = torch.from_numpy(np.ascontiguousarray(sequences[offset : offset + 2048]))
            outputs.append(model(batch).cpu().numpy())
    return np.concatenate(outputs, axis=0).astype(np.float32)


def export_and_compare(
    model: UtilityGRU, sequences: np.ndarray, output_path: Path
) -> tuple[np.ndarray, dict[str, Any]]:
    if len(sequences) == 0:
        raise RuntimeError("cannot export without parity sequences")
    dummy = torch.from_numpy(np.ascontiguousarray(sequences[:1]))
    torch.onnx.export(
        model,
        dummy,
        str(output_path),
        input_names=["micro_sequence"],
        output_names=["action_utility_R"],
        dynamic_axes={
            "micro_sequence": {0: "batch"},
            "action_utility_R": {0: "batch"},
        },
        opset_version=17,
        do_constant_folding=True,
        dynamo=False,
    )
    checked = onnx.load(output_path)
    onnx.checker.check_model(checked)
    torch_predictions = infer_torch(model, sequences)
    session = ort.InferenceSession(str(output_path), providers=["CPUExecutionProvider"])
    ort_outputs: list[np.ndarray] = []
    for offset in range(0, len(sequences), 2048):
        batch = np.ascontiguousarray(sequences[offset : offset + 2048])
        ort_outputs.append(session.run(["action_utility_R"], {"micro_sequence": batch})[0])
    onnx_predictions = np.concatenate(ort_outputs, axis=0).astype(np.float32)
    difference = np.abs(torch_predictions - onnx_predictions)
    max_difference = float(difference.max())
    argmax_mismatch = int(
        (np.argmax(torch_predictions, axis=1) != np.argmax(onnx_predictions, axis=1)).sum()
    )
    return onnx_predictions, {
        "rows": len(sequences),
        "maximum_absolute_difference": max_difference,
        "action_argmax_mismatch_count": argmax_mismatch,
        "passed": max_difference <= 0.00001 and argmax_mismatch == 0,
    }


def structural_precheck(contract: dict[str, Any]) -> dict[str, Any]:
    data = prepare_data(pd.Timestamp("2026-01-01T00:00:00"))
    initial_mask = period_mask(
        data.decision_times,
        pd.Timestamp("2022-07-01T00:00:00"),
        pd.Timestamp("2024-01-01T00:00:00"),
    )
    development_mask = period_mask(
        data.decision_times,
        pd.Timestamp("2024-01-01T00:00:00"),
        pd.Timestamp("2026-01-01T00:00:00"),
    )
    normal_days, day_distribution = normal_trading_days(
        data.decision_times,
        pd.Timestamp("2024-01-01T00:00:00"),
        pd.Timestamp("2026-01-01T00:00:00"),
    )
    set_deterministic_seed()
    dummy_model = UtilityGRU(
        np.zeros(FEATURE_COUNT, dtype=np.float32),
        np.ones(FEATURE_COUNT, dtype=np.float32),
    )
    parity_sequences = data.features[development_mask][:64]
    with tempfile.TemporaryDirectory(prefix="zeta-m1-gru-dummy-") as temp:
        dummy_path = Path(temp) / "dummy.onnx"
        _, parity = export_and_compare(dummy_model, parity_sequences, dummy_path)
        persistent_after = int(dummy_path.exists())
    if not parity["passed"]:
        raise RuntimeError("dummy ONNX parity failed")
    feature_min = data.features.min(axis=(0, 1)).astype(float)
    feature_max = data.features.max(axis=(0, 1)).astype(float)
    return {
        "schema": (
            "zeta-next-independent-two-index-m1-utility-gru-onnx-"
            "challenge-v1-structural-precheck"
        ),
        "status": "STRUCTURAL_TENSOR_AND_DUMMY_ONNX_PRECHECK_PASS_NO_LABEL_OR_OUTCOME",
        "authorities": {
            "contract": file_record(CONTRACT_PATH),
            "declaration": file_record(DECLARATION_PATH),
            "trainer": file_record(Path(__file__).resolve()),
        },
        "common_m1": {
            "rows": len(data.frame),
            "first": data.frame["time"].iloc[0].isoformat(),
            "last": data.frame["time"].iloc[-1].isoformat(),
        },
        "complete_windows": {
            "initial_rows": int(initial_mask.sum()),
            "development_rows": int(development_mask.sum()),
            "normal_trading_days": normal_days,
            "day_distribution": day_distribution,
            "fit_geometry": fit_geometry(data.decision_times),
        },
        "feature_tensor": {
            "all_initial_and_development_shape": list(data.features.shape),
            "finite": bool(np.isfinite(data.features).all()),
            "feature_names": list(FEATURE_NAMES),
            "per_feature_min": feature_min.tolist(),
            "per_feature_max": feature_max.tolist(),
        },
        "dummy_onnx": {
            "input_shape": [1, SEQUENCE_ROWS, FEATURE_COUNT],
            "output_shape": [1, len(ACTIONS)],
            "opset": 17,
            "parity": parity,
            "persistent_dummy_onnx_files_after_temp_cleanup": 0,
            "dummy_existed_inside_temporary_directory": persistent_after,
        },
        "environment": {
            "python": os.sys.version.split()[0],
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "torch": torch.__version__,
            "onnx": onnx.__version__,
            "onnxruntime": ort.__version__,
        },
        "attestation": {
            "action_labels_constructed": 0,
            "model_fits": 0,
            "persistent_onnx_files": 0,
            "candidate_predictions": 0,
            "candidate_rankings": 0,
            "candidate_lifecycles": 0,
            "candidate_economic_metrics": 0,
            "locked_confirmation_rows_used": 0,
            "ea_source_files": 0,
            "mt5_paths": 0,
        },
    }


def simulate_action(
    frame: pd.DataFrame,
    position: int,
    action_index: int,
    atr_price: float,
) -> tuple[float, float, int, str]:
    _, symbol_index, direction = ACTIONS[action_index]
    symbol = SYMBOLS[symbol_index]
    entry_bid = float(frame[f"{symbol}_open"].iat[position])
    entry_spread = float(frame[f"{symbol}_spread"].iat[position]) * POINT
    entry_price = entry_bid + entry_spread if direction > 0 else entry_bid
    stop_price = entry_price + STOP_R * atr_price * direction
    take_price = entry_price + TAKE_R * atr_price * direction
    exit_offset = LABEL_BARS - 1
    exit_reason = "TIME_15_M1"
    exit_spread = float(frame[f"{symbol}_spread"].iat[position + exit_offset]) * POINT
    exit_price = float(frame[f"{symbol}_close"].iat[position + exit_offset])
    if direction < 0:
        exit_price += exit_spread
    for offset in range(LABEL_BARS):
        row = position + offset
        high_bid = float(frame[f"{symbol}_high"].iat[row])
        low_bid = float(frame[f"{symbol}_low"].iat[row])
        spread = float(frame[f"{symbol}_spread"].iat[row]) * POINT
        if direction > 0:
            stop_hit = low_bid <= stop_price
            take_hit = high_bid >= take_price
        else:
            stop_hit = high_bid + spread >= stop_price
            take_hit = low_bid + spread <= take_price
        if stop_hit:
            exit_offset = offset
            exit_reason = "STOP_ADVERSE_FIRST"
            exit_price = stop_price
            exit_spread = spread
            break
        if take_hit:
            exit_offset = offset
            exit_reason = "TAKE"
            exit_price = take_price
            exit_spread = spread
            break
    actual_per_lot = (
        direction
        * (exit_price - entry_price)
        * DOLLARS_PER_PRICE_POINT_PER_LOT
    )
    planned_risk_per_lot = atr_price * DOLLARS_PER_PRICE_POINT_PER_LOT
    actual_r = actual_per_lot / planned_risk_per_lot
    extra_spread = entry_spread if direction > 0 else exit_spread
    extra_stress_r = (
        extra_spread * DOLLARS_PER_PRICE_POINT_PER_LOT / planned_risk_per_lot
    )
    return actual_r, extra_stress_r, exit_offset, exit_reason


def build_action_paths(data: PreparedData) -> ActionPaths:
    rows = len(data.decision_positions)
    actual_r = np.empty((rows, len(ACTIONS)), dtype=np.float32)
    extra_r = np.empty_like(actual_r)
    exit_offset = np.empty((rows, len(ACTIONS)), dtype=np.int8)
    exit_reason = np.empty((rows, len(ACTIONS)), dtype="U20")
    atr_price = np.empty((rows, len(SYMBOLS)), dtype=np.float64)
    for row, position in enumerate(data.decision_positions):
        for symbol_index in range(len(SYMBOLS)):
            atr = float(
                np.mean(
                    data.true_range[
                        position - SEQUENCE_ROWS : position, symbol_index
                    ]
                )
            )
            if not math.isfinite(atr) or atr <= 0.0:
                raise RuntimeError("invalid prior ATR in action path")
            atr_price[row, symbol_index] = atr
        for action_index, (_, symbol_index, _) in enumerate(ACTIONS):
            values = simulate_action(
                data.frame,
                int(position),
                action_index,
                float(atr_price[row, symbol_index]),
            )
            actual_r[row, action_index] = values[0]
            extra_r[row, action_index] = values[1]
            exit_offset[row, action_index] = values[2]
            exit_reason[row, action_index] = values[3]
    if not np.isfinite(actual_r).all() or not np.isfinite(extra_r).all():
        raise RuntimeError("nonfinite action utility label")
    return ActionPaths(actual_r, extra_r, exit_offset, exit_reason, atr_price)


def planned_volume(balance: float, atr_price: float) -> tuple[float | None, str]:
    if not math.isfinite(balance) or balance <= 0.0:
        return None, "NONPOSITIVE_ACTUAL_BALANCE"
    risk_per_lot = atr_price * DOLLARS_PER_PRICE_POINT_PER_LOT
    if not math.isfinite(risk_per_lot) or risk_per_lot <= 0.0:
        return None, "INVALID_ATR_RISK"
    raw = balance * TARGET_RISK_FRACTION / risk_per_lot
    steps = math.floor((raw + EPSILON) / VOLUME_STEP)
    volume = round(max(steps * VOLUME_STEP, VOLUME_MIN), 2)
    if volume * risk_per_lot > balance * HARD_RISK_FRACTION + EPSILON:
        return None, "MINIMUM_LOT_HARD_RISK_CAP"
    return volume, "FEASIBLE"


def run_candidate_roles(
    data: PreparedData,
    paths: ActionPaths,
    predictions: np.ndarray,
    candidate_mask: np.ndarray,
    role_thresholds: dict[str, float],
    starting_balances: dict[str, tuple[float, float]] | None = None,
    starting_sequences: dict[str, int] | None = None,
) -> tuple[dict[str, RoleBook], list[dict[str, Any]]]:
    books: dict[str, RoleBook] = {}
    for role in role_thresholds:
        actual, stressed = (
            starting_balances[role]
            if starting_balances is not None
            else (INITIAL_BALANCE_USD, INITIAL_BALANCE_USD)
        )
        books[role] = RoleBook(role, actual_balance=actual, stressed_balance=stressed)
    trades: list[dict[str, Any]] = []
    for row in np.flatnonzero(candidate_mask):
        utilities = predictions[row]
        if not np.isfinite(utilities).all():
            raise RuntimeError("nonfinite frozen prediction")
        action_index = int(np.argmax(utilities))
        predicted_utility = float(utilities[action_index])
        action_name, symbol_index, direction = ACTIONS[action_index]
        symbol = SYMBOLS[symbol_index]
        for role, threshold in role_thresholds.items():
            book = books[role]
            if not predicted_utility > threshold:
                book.threshold_blocks += 1
                continue
            atr = float(paths.atr_price[row, symbol_index])
            volume, reason = planned_volume(book.actual_balance, atr)
            if volume is None:
                book.risk_blocks += 1
                continue
            planned_risk = volume * atr * DOLLARS_PER_PRICE_POINT_PER_LOT
            actual_r = float(paths.actual_r[row, action_index])
            extra_r = float(paths.extra_stress_r[row, action_index])
            actual_pnl = actual_r * planned_risk
            extra_stress = extra_r * planned_risk
            stressed_pnl = actual_pnl - extra_stress
            actual_before = book.actual_balance
            stressed_before = book.stressed_balance
            book.actual_balance += actual_pnl
            book.stressed_balance += stressed_pnl
            book.starts += 1
            base_sequence = starting_sequences.get(role, 0) if starting_sequences else 0
            exit_position = int(data.decision_positions[row]) + int(
                paths.exit_offset[row, action_index]
            )
            trades.append(
                {
                    "role": role,
                    "sequence": base_sequence + book.starts,
                    "entry_time_epoch": int(data.decision_epochs[row]),
                    "entry_time": data.decision_times[row].isoformat(),
                    "exit_time_epoch": int(data.frame.index[exit_position]),
                    "exit_time": data.frame["time"].iat[exit_position].isoformat(),
                    "action": action_name,
                    "symbol": symbol,
                    "direction": "LONG" if direction > 0 else "SHORT",
                    "predicted_actual_utility_R": predicted_utility,
                    "actual_utility_R": actual_r,
                    "extra_stress_R": extra_r,
                    "atr_price": atr,
                    "volume_lots": volume,
                    "planned_risk_usd": planned_risk,
                    "exit_reason": str(paths.exit_reason[row, action_index]),
                    "actual_pnl_usd": actual_pnl,
                    "extra_stress_cost_usd": extra_stress,
                    "stressed_pnl_usd": stressed_pnl,
                    "actual_balance_before_usd": actual_before,
                    "actual_balance_after_usd": book.actual_balance,
                    "stressed_balance_before_usd": stressed_before,
                    "stressed_balance_after_usd": book.stressed_balance,
                }
            )
    return books, trades


def metrics_from_trades(
    trades: list[dict[str, Any]],
    normal_days: int,
    years: Iterable[int],
    initial_actual: float = INITIAL_BALANCE_USD,
    initial_stressed: float = INITIAL_BALANCE_USD,
) -> dict[str, Any]:
    actual_balance = initial_actual
    stressed_balance = initial_stressed
    actual_peak = initial_actual
    stressed_peak = initial_stressed
    max_actual_dd_usd = 0.0
    max_actual_dd_pct = 0.0
    max_stressed_dd_usd = 0.0
    max_stressed_dd_pct = 0.0
    minimum_actual = initial_actual
    minimum_stressed = initial_stressed
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
    actual_net = actual_balance - initial_actual
    stressed_net = stressed_balance - initial_stressed
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
        "years": yearly,
        "symbols": symbols,
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
        writer.writerows(rows)


def ordered_manifest(records: Iterable[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(
            f"{record['path']}|{record['bytes']}|{record['sha256']}\n".encode("utf-8")
        )
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


def prediction_rows(
    data: PreparedData, predictions: np.ndarray, block_by_row: np.ndarray, mask: np.ndarray
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in np.flatnonzero(mask):
        row = {
            "time_epoch": int(data.decision_epochs[index]),
            "time": data.decision_times[index].isoformat(),
            "model_block": str(block_by_row[index]),
        }
        for action_index, (action, _, _) in enumerate(ACTIONS):
            row[f"predicted_{action}_R"] = float(predictions[index, action_index])
        rows.append(row)
    return rows


def label_rows(
    data: PreparedData, paths: ActionPaths, mask: np.ndarray
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in np.flatnonzero(mask):
        row: dict[str, Any] = {
            "time_epoch": int(data.decision_epochs[index]),
            "time": data.decision_times[index].isoformat(),
            "US100_ATR60": float(paths.atr_price[index, 0]),
            "US30_ATR60": float(paths.atr_price[index, 1]),
        }
        for action_index, (action, _, _) in enumerate(ACTIONS):
            row[f"{action}_actual_R"] = float(paths.actual_r[index, action_index])
            row[f"{action}_extra_stress_R"] = float(
                paths.extra_stress_r[index, action_index]
            )
            row[f"{action}_exit_offset"] = int(paths.exit_offset[index, action_index])
            row[f"{action}_exit_reason"] = str(paths.exit_reason[index, action_index])
        rows.append(row)
    return rows


def run_development(
    contract: dict[str, Any], freeze: dict[str, Any]
) -> dict[str, Any]:
    data = prepare_data(pd.Timestamp("2026-01-01T00:00:00"))
    paths = build_action_paths(data)
    initial_start = pd.Timestamp("2022-07-01T00:00:00")
    development_start = pd.Timestamp("2024-01-01T00:00:00")
    development_end = pd.Timestamp("2026-01-01T00:00:00")
    development_mask = period_mask(data.decision_times, development_start, development_end)
    predictions = np.full((len(data.decision_times), len(ACTIONS)), np.nan, dtype=np.float32)
    block_by_row = np.full(len(data.decision_times), "", dtype="U8")
    temporary, final = atomic_output_directory("development")
    try:
        model_records: list[dict[str, Any]] = []
        fit_records: list[dict[str, Any]] = []
        matured_times = data.decision_times + pd.Timedelta(minutes=LABEL_BARS)
        for fit_index, (name, start_text, end_text) in enumerate(TEST_BLOCKS, start=1):
            start = pd.Timestamp(start_text)
            end = pd.Timestamp(end_text)
            train_mask = (data.decision_times >= initial_start) & (matured_times < start)
            test_mask = period_mask(data.decision_times, start, end)
            train_indices = np.flatnonzero(train_mask)
            test_indices = np.flatnonzero(test_mask)
            if len(train_indices) == 0 or len(test_indices) == 0:
                raise RuntimeError(f"empty fit partition: {name}")
            mean, std = feature_normalization(data.features[train_indices])
            model, losses = train_model(
                data.features[train_indices],
                paths.actual_r[train_indices],
                mean,
                std,
            )
            model_path = temporary / f"utility-gru-{fit_index:02d}-{name}.onnx"
            onnx_predictions, parity = export_and_compare(
                model, data.features[test_indices], model_path
            )
            if not parity["passed"]:
                raise RuntimeError(f"ONNX parity failed: {name}")
            predictions[test_indices] = onnx_predictions
            block_by_row[test_indices] = name
            model_record = file_record(model_path, final / model_path.name)
            model_records.append(model_record)
            fit_records.append(
                {
                    "fit_index": fit_index,
                    "block": name,
                    "train_rows": len(train_indices),
                    "test_rows": len(test_indices),
                    "first_train": data.decision_times[train_indices[0]].isoformat(),
                    "last_train": data.decision_times[train_indices[-1]].isoformat(),
                    "first_test": data.decision_times[test_indices[0]].isoformat(),
                    "last_test": data.decision_times[test_indices[-1]].isoformat(),
                    "feature_mean": mean.astype(float).tolist(),
                    "feature_std": std.astype(float).tolist(),
                    "epoch_losses": losses,
                    "parity": parity,
                    "onnx": model_record,
                }
            )
            del model
            gc.collect()
        if not np.isfinite(predictions[development_mask]).all():
            raise RuntimeError("development predictions are incomplete")
        if np.any(block_by_row[development_mask] == ""):
            raise RuntimeError("development model schedule is incomplete")
        normal_days, day_distribution = normal_trading_days(
            data.decision_times, development_start, development_end
        )
        books, trades = run_candidate_roles(
            data,
            paths,
            predictions,
            development_mask,
            ROLE_THRESHOLDS,
        )
        role_results: dict[str, Any] = {}
        passers: list[str] = []
        for role in ROLE_THRESHOLDS:
            role_trades = [trade for trade in trades if trade["role"] == role]
            metrics = metrics_from_trades(role_trades, normal_days, (2024, 2025))
            gates = development_gates(metrics, contract)
            complete = all(gates.values())
            if complete:
                passers.append(role)
            role_results[role] = {
                "minimum_predicted_actual_utility_R_exclusive": ROLE_THRESHOLDS[role],
                "metrics": metrics,
                "gates": gates,
                "complete_pass": complete,
                "threshold_blocks": books[role].threshold_blocks,
                "risk_blocks": books[role].risk_blocks,
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
        manifest_path = temporary / "model-manifest.json"
        model_manifest = {
            "schema": "zeta-next-m1-utility-gru-development-model-manifest-v1",
            "model_seed": MODEL_SEED,
            "architecture": "GRU32-Linear32-GELU-Linear4",
            "feature_names": list(FEATURE_NAMES),
            "action_order": [action[0] for action in ACTIONS],
            "fits": fit_records,
            "ordered_model_manifest_sha256": ordered_manifest(model_records),
        }
        write_json(manifest_path, model_manifest)
        predictions_path = temporary / "prediction-tape.csv"
        labels_path = temporary / "action-utility-tape.csv"
        trades_path = temporary / "trade-tape.csv"
        write_csv_rows(
            predictions_path,
            prediction_rows(data, predictions, block_by_row, development_mask),
        )
        write_csv_rows(labels_path, label_rows(data, paths, development_mask))
        if trades:
            write_csv_rows(trades_path, trades)
        else:
            with trades_path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(
                    "role,sequence,entry_time_epoch,entry_time,exit_time_epoch,exit_time,"
                    "action,symbol,direction,predicted_actual_utility_R,actual_utility_R,"
                    "extra_stress_R,atr_price,volume_lots,planned_risk_usd,exit_reason,"
                    "actual_pnl_usd,extra_stress_cost_usd,stressed_pnl_usd,"
                    "actual_balance_before_usd,actual_balance_after_usd,"
                    "stressed_balance_before_usd,stressed_balance_after_usd\n"
                )
        manifest_record = file_record(manifest_path, final / manifest_path.name)
        prediction_record = file_record(predictions_path, final / predictions_path.name)
        label_record = file_record(labels_path, final / labels_path.name)
        trade_record = file_record(trades_path, final / trades_path.name)
        all_records = [
            *model_records,
            manifest_record,
            prediction_record,
            label_record,
            trade_record,
        ]
        result = {
            "schema": (
                "zeta-next-independent-two-index-m1-utility-gru-onnx-"
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
                "trainer": file_record(Path(__file__).resolve()),
            },
            "process": {
                "initial_rows": int(
                    period_mask(
                        data.decision_times,
                        initial_start,
                        development_start,
                    ).sum()
                ),
                "development_rows": int(development_mask.sum()),
                "normal_trading_days": normal_days,
                "day_distribution": day_distribution,
                "fit_count": len(fit_records),
                "all_fit_parity_pass": all(fit["parity"]["passed"] for fit in fit_records),
                "maximum_parity_difference": max(
                    fit["parity"]["maximum_absolute_difference"] for fit in fit_records
                ),
                "total_argmax_mismatch_count": sum(
                    fit["parity"]["action_argmax_mismatch_count"] for fit in fit_records
                ),
            },
            "development": {
                "period": "2024-01-01T00:00:00/2026-01-01T00:00:00",
                "initial_deposit_usd": INITIAL_BALANCE_USD,
                "roles": role_results,
                "complete_passer_count": len(passers),
                "complete_passers_ranked": passers,
                "selected_role": selected_role,
            },
            "raw_evidence": {
                "models": model_records,
                "model_manifest": manifest_record,
                "prediction_tape": prediction_record,
                "action_utility_tape": label_record,
                "trade_tape": trade_record,
                "ordered_all_artifact_manifest_sha256": ordered_manifest(all_records),
                "all_artifact_bytes": sum(int(record["bytes"]) for record in all_records),
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
                "write and commit one durable development authority selecting the unchanged role before final fit and locked confirmation"
                if selected_role
                else "write the durable adverse result and family closure; do not open final fit, locked confirmation, EA, or MT5"
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
    if selected not in ROLE_THRESHOLDS:
        raise RuntimeError("invalid selected role")
    if raw["development"]["selected_role"] != selected:
        raise RuntimeError("selected role mismatch")
    if not raw["development"]["roles"][selected]["complete_pass"]:
        raise RuntimeError("selected role is not a complete passer")
    return evidence, raw


def run_confirmation(
    contract: dict[str, Any], freeze: dict[str, Any]
) -> dict[str, Any]:
    development_evidence, raw_development = verify_development_evidence()
    selected_role = str(development_evidence["selected_role"])
    data = prepare_data(pd.Timestamp("2026-08-01T00:00:00"))
    paths = build_action_paths(data)
    initial_start = pd.Timestamp("2022-07-01T00:00:00")
    confirmation_start = pd.Timestamp("2026-01-01T00:00:00")
    confirmation_end = pd.Timestamp("2026-08-01T00:00:00")
    matured_times = data.decision_times + pd.Timedelta(minutes=LABEL_BARS)
    train_mask = (data.decision_times >= initial_start) & (matured_times < confirmation_start)
    locked_mask = period_mask(data.decision_times, confirmation_start, confirmation_end)
    train_indices = np.flatnonzero(train_mask)
    locked_indices = np.flatnonzero(locked_mask)
    mean, std = feature_normalization(data.features[train_indices])
    model, losses = train_model(
        data.features[train_indices],
        paths.actual_r[train_indices],
        mean,
        std,
    )
    temporary, final = atomic_output_directory("confirmation")
    try:
        model_path = temporary / "utility-gru-final-2026.onnx"
        locked_predictions, parity = export_and_compare(
            model, data.features[locked_indices], model_path
        )
        if not parity["passed"]:
            raise RuntimeError("final locked ONNX parity failed")
        predictions = np.full((len(data.decision_times), len(ACTIONS)), np.nan, dtype=np.float32)
        predictions[locked_indices] = locked_predictions
        block_by_row = np.full(len(data.decision_times), "", dtype="U16")
        block_by_row[locked_indices] = "FINAL_2026"
        development_metrics = raw_development["development"]["roles"][selected_role][
            "metrics"
        ]
        starting_balances = {
            selected_role: (
                float(development_metrics["actual_ending_balance_usd"]),
                float(development_metrics["stressed_ending_balance_usd"]),
            )
        }
        starting_sequences = {
            selected_role: int(development_metrics["starts"])
        }
        books, locked_trades = run_candidate_roles(
            data,
            paths,
            predictions,
            locked_mask,
            {selected_role: ROLE_THRESHOLDS[selected_role]},
            starting_balances,
            starting_sequences,
        )
        raw_trade_record = development_evidence.get("raw_development_trade_tape")
        if not isinstance(raw_trade_record, dict):
            raise RuntimeError("durable development evidence lacks trade tape")
        verify_file_record(raw_trade_record)
        development_trade_frame = pd.read_csv(PROJECT_ROOT / raw_trade_record["path"])
        selected_frame = development_trade_frame.loc[
            development_trade_frame["role"] == selected_role
        ]
        development_trades = selected_frame.to_dict(orient="records")
        whole_trades = development_trades + locked_trades
        confirmation_days, confirmation_distribution = normal_trading_days(
            data.decision_times, confirmation_start, confirmation_end
        )
        whole_days, whole_distribution = normal_trading_days(
            data.decision_times,
            pd.Timestamp("2024-01-01T00:00:00"),
            confirmation_end,
        )
        confirmation_metrics = metrics_from_trades(
            locked_trades,
            confirmation_days,
            (2026,),
            initial_actual=starting_balances[selected_role][0],
            initial_stressed=starting_balances[selected_role][1],
        )
        whole_metrics = metrics_from_trades(
            whole_trades, whole_days, (2024, 2025, 2026)
        )
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
            "symbol_breadth_two": whole_metrics["symbol_breadth"] == 2,
        }
        proxy_survivor = all(proxy_gates.values())
        prediction_path = temporary / "locked-prediction-tape.csv"
        label_path = temporary / "locked-action-utility-tape.csv"
        trade_path = temporary / "locked-trade-tape.csv"
        write_csv_rows(
            prediction_path,
            prediction_rows(data, predictions, block_by_row, locked_mask),
        )
        write_csv_rows(label_path, label_rows(data, paths, locked_mask))
        if locked_trades:
            write_csv_rows(trade_path, locked_trades)
        else:
            with trade_path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write("role,sequence\n")
        records = [
            file_record(model_path, final / model_path.name),
            file_record(prediction_path, final / prediction_path.name),
            file_record(label_path, final / label_path.name),
            file_record(trade_path, final / trade_path.name),
        ]
        result = {
            "schema": (
                "zeta-next-independent-two-index-m1-utility-gru-onnx-"
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
                "trainer": file_record(Path(__file__).resolve()),
                "development_evidence": file_record(DEVELOPMENT_EVIDENCE_PATH),
            },
            "selected_role": selected_role,
            "final_fit": {
                "train_rows": len(train_indices),
                "locked_rows": len(locked_indices),
                "feature_mean": mean.astype(float).tolist(),
                "feature_std": std.astype(float).tolist(),
                "epoch_losses": losses,
                "parity": parity,
            },
            "locked_confirmation": {
                "day_distribution": confirmation_distribution,
                "metrics": confirmation_metrics,
            },
            "whole_proxy": {
                "day_distribution": whole_distribution,
                "metrics": whole_metrics,
                "gates": proxy_gates,
                "complete_proxy_survivor": proxy_survivor,
                "native_relative_equity_drawdown_still_required": True,
            },
            "raw_evidence": {
                "files": records,
                "ordered_manifest_sha256": ordered_manifest(records),
            },
            "attestation": {
                "confirmation_roles_run": 1,
                "candidate_ea_source_files": 0,
                "candidate_mt5_paths": 0,
                "native_v8_victory_claimed": False,
                "live_changed": False,
            },
            "next_authorized_action": (
                "freeze and implement one self-contained EA with the unchanged nine-model schedule; proxy still cannot claim victory"
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
        description="Independent two-index M1 utility GRU ONNX adapter"
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
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
            default=json_default,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
