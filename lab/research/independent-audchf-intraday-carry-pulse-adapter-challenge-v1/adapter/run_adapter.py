from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pyarrow.dataset as ds


FAMILY = "independent-audchf-intraday-carry-pulse-adapter-challenge-v1"
ROLES = ["AUDCHF_PULSE_FOLLOW", "AUDCHF_PULSE_FADE"]
SYMBOLS = ["US100", "US30"]
SYMBOL_ORDER = {symbol: index for index, symbol in enumerate(SYMBOLS)}
NEW_YORK = ZoneInfo("America/New_York")
DECISION_TIMES = [
    time(hour=hour, minute=minute)
    for hour, minute in [
        (10, 0),
        (10, 30),
        (11, 0),
        (11, 30),
        (12, 0),
        (12, 30),
        (13, 0),
        (13, 30),
        (14, 0),
        (14, 30),
        (15, 0),
        (15, 30),
    ]
]
WARMUP_START = datetime(2023, 7, 1, tzinfo=UTC)
DEVELOPMENT_START = datetime(2024, 1, 1, tzinfo=UTC)
LOCKED_START = datetime(2026, 1, 1, tzinfo=UTC)
WHOLE_END = datetime(2026, 8, 1, tzinfo=UTC)
POINT = 0.01
TICK_SIZE = 0.01
TICK_VALUE_PER_LOT = 0.01
VOLUME_MIN = 0.01
VOLUME_STEP = 0.01
VOLUME_MAX = 200.0
INITIAL_DEPOSIT = 100.0
POSITION_RISK = 0.02
POSITION_HARD_CAP = 0.04
AGGREGATE_HARD_CAP = 0.08
EXPECTED = {
    "selection_audit": "1AFE04FEA5D4DA5C16A85215AD409CFC252A8B0F09214203063229CCAA299E32",
    "contract": "BCFF0204EDFB65D34298A54F1E69859BD7C924566C36526999A391D1E6D197F5",
    "declaration": "0CEBC92B0F7BE5469FF6CBEE20E8AF3BBC36907EA95FF784E03AE8A411E7799C",
    "engineering_correction": "70EB0501B2458D40D35F87AA27DADAB1F90EE75F6410615E2CFC204B54DFDEF2",
    "original_broker_acquisition_correction": "0BC953B96A0A205E4A71FBAD6BFD15CAA4861C838388F87DE8461003232EA88E",
    "target_receipt": "079326EC53FE72995515516318760E0DEC4089496B156192C527A36737B46C5D",
    "US100": "634A8545D83C7A520E81A07E273255BD3FA771AA0EC29381D04E6D25A64C6BB2",
    "US30": "8CD68BC54A736BF49CC020ED7CF41C62BBA5305FA7C1453603EF65173F83B063",
}


@dataclass(frozen=True)
class Paths:
    workspace: Path
    family_root: Path
    raw_root: Path
    output_root: Path
    selection_audit: Path
    contract: Path
    declaration: Path
    engineering_correction: Path
    original_broker_acquisition_correction: Path
    target_receipt: Path
    implementation_freeze: Path
    external_development: Path
    external_development_receipt: Path
    external_locked: Path
    external_locked_receipt: Path
    external_combined: Path
    external_final_receipt: Path
    external_spec: Path
    target_files: dict[str, Path]
    raw_development_result: Path
    raw_development_states: Path
    raw_development_trades: Path
    durable_development_result: Path
    raw_confirmation_result: Path
    raw_confirmation_states: Path
    raw_confirmation_trades: Path
    raw_native_decisions: Path


@dataclass
class RoleLedger:
    role: str
    actual_balance: float = INITIAL_DEPOSIT
    stressed_balance: float = INITIAL_DEPOSIT
    actual_peak: float = INITIAL_DEPOSIT
    max_drawdown_usd: float = 0.0
    max_drawdown_pct: float = 0.0
    risk_blocks: int = 0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root is not an object: {path}")
    return value


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def finite(value: object, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise RuntimeError(f"nonfinite {name}: {value}")
    return number


def make_paths() -> Paths:
    script = Path(__file__).resolve()
    family_root = script.parents[1]
    workspace = script.parents[4]
    expected_root = workspace / "lab" / "research" / FAMILY
    if family_root != expected_root:
        raise RuntimeError(f"unexpected family root: {family_root}")
    raw_root = workspace / "lab" / "artifacts" / "raw" / FAMILY
    output_root = raw_root / "output"
    evidence = family_root / "evidence"
    external = raw_root / "input" / "external"
    target = raw_root / "input" / "target"
    return Paths(
        workspace=workspace,
        family_root=family_root,
        raw_root=raw_root,
        output_root=output_root,
        selection_audit=workspace
        / "lab"
        / "evidence"
        / "INDEPENDENT_V8_CHALLENGE_POST_FAMILY_006_WHOLE_MAP_RECOMPARE_V1.json",
        contract=family_root / "config" / "challenge-contract.json",
        declaration=evidence
        / "INDEPENDENT_AUDCHF_INTRADAY_CARRY_PULSE_ADAPTER_CHALLENGE_V1_DECLARATION.json",
        engineering_correction=evidence
        / "INDEPENDENT_AUDCHF_INTRADAY_CARRY_PULSE_ADAPTER_CHALLENGE_V1_ACQUISITION_ENGINEERING_CORRECTION.json",
        original_broker_acquisition_correction=evidence
        / "INDEPENDENT_AUDCHF_INTRADAY_CARRY_PULSE_ADAPTER_CHALLENGE_V1_ORIGINAL_BROKER_ACQUISITION_CORRECTION_V2.json",
        target_receipt=evidence
        / "INDEPENDENT_AUDCHF_INTRADAY_CARRY_PULSE_ADAPTER_CHALLENGE_V1_TARGET_MATERIALIZATION_RECEIPT.json",
        implementation_freeze=evidence
        / "INDEPENDENT_AUDCHF_INTRADAY_CARRY_PULSE_ADAPTER_CHALLENGE_V1_IMPLEMENTATION_FREEZE.json",
        external_development=external / "AUDCHF_M1_DEVELOPMENT.csv",
        external_development_receipt=external
        / "AUDCHF_DEVELOPMENT_ACQUISITION_RECEIPT.json",
        external_locked=external / "AUDCHF_M1_LOCKED.csv",
        external_locked_receipt=external / "AUDCHF_LOCKED_ACQUISITION_RECEIPT.json",
        external_combined=external / "AUDCHF_M1.csv",
        external_final_receipt=external / "AUDCHF_ACQUISITION_RECEIPT.json",
        external_spec=external / "AUDCHF_SYMBOL_SPEC.json",
        target_files={symbol: target / f"{symbol}_M1.parquet" for symbol in SYMBOLS},
        raw_development_result=output_root / "development-result.json",
        raw_development_states=output_root / "development-states.csv",
        raw_development_trades=output_root / "development-trades.csv",
        durable_development_result=evidence
        / "INDEPENDENT_AUDCHF_INTRADAY_CARRY_PULSE_ADAPTER_CHALLENGE_V1_DEVELOPMENT_RESULT.json",
        raw_confirmation_result=output_root / "confirmation-result.json",
        raw_confirmation_states=output_root / "confirmation-states.csv",
        raw_confirmation_trades=output_root / "confirmation-trades.csv",
        raw_native_decisions=output_root / "native-decisions.csv",
    )


def check_hash(path: Path, expected: str, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing {label}: {path}")
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError(f"{label} SHA-256 mismatch: {actual} != {expected}")
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": actual}


def validate_static_authorities(paths: Paths) -> dict[str, Any]:
    authorities = {
        "selection_audit": check_hash(
            paths.selection_audit, EXPECTED["selection_audit"], "selection audit"
        ),
        "contract": check_hash(paths.contract, EXPECTED["contract"], "contract"),
        "declaration": check_hash(
            paths.declaration, EXPECTED["declaration"], "declaration"
        ),
        "engineering_correction": check_hash(
            paths.engineering_correction,
            EXPECTED["engineering_correction"],
            "engineering correction",
        ),
        "original_broker_acquisition_correction": check_hash(
            paths.original_broker_acquisition_correction,
            EXPECTED["original_broker_acquisition_correction"],
            "original broker acquisition correction",
        ),
        "target_receipt": check_hash(
            paths.target_receipt, EXPECTED["target_receipt"], "target receipt"
        ),
    }
    for symbol in SYMBOLS:
        authorities[symbol] = check_hash(
            paths.target_files[symbol], EXPECTED[symbol], f"{symbol} target copy"
        )
    declaration = read_json(paths.declaration)
    if declaration.get("status") != (
        "DECLARED_PRERUNTIME_PREACQUISITION_PREINPUT_PRERANK_"
        "PREIMPLEMENTATION_PREOUTCOME"
    ):
        raise RuntimeError("unexpected declaration status")
    contract = read_json(paths.contract)
    if contract.get("family") != f"lab/research/{FAMILY}/":
        raise RuntimeError("contract family mismatch")
    return authorities


def validate_external_development(paths: Paths) -> dict[str, Any]:
    required = [
        paths.external_development,
        paths.external_development_receipt,
        paths.external_spec,
    ]
    if any(not path.is_file() for path in required):
        raise RuntimeError("fresh AUDCHF development authority is incomplete")
    receipt = read_json(paths.external_development_receipt)
    if receipt.get("status") != (
        "COMPLETE_FRESH_DEDICATED_PORTABLE_DEVELOPMENT_ACQUISITION"
    ):
        raise RuntimeError("unexpected development acquisition status")
    if receipt.get("locked_external_values_acquired") is not False:
        raise RuntimeError("development receipt did not preserve locked boundary")
    output = receipt.get("output", {})
    if int(output.get("rows", 0)) < 500_000:
        raise RuntimeError("insufficient external development rows in receipt")
    if int(output.get("bytes", -1)) != paths.external_development.stat().st_size:
        raise RuntimeError("external development byte count mismatch")
    if str(output.get("sha256")) != sha256(paths.external_development):
        raise RuntimeError("external development SHA-256 mismatch")
    spec_receipt = receipt.get("symbol_spec", {})
    if int(spec_receipt.get("bytes", -1)) != paths.external_spec.stat().st_size:
        raise RuntimeError("external symbol-spec byte count mismatch")
    if str(spec_receipt.get("sha256")) != sha256(paths.external_spec):
        raise RuntimeError("external symbol-spec SHA-256 mismatch")
    spec = read_json(paths.external_spec)
    if spec.get("symbol") != "AUDCHF" or int(spec.get("digits", 0)) <= 0:
        raise RuntimeError("invalid external symbol specification")
    return {
        "development_csv": {
            "path": str(paths.external_development),
            "bytes": paths.external_development.stat().st_size,
            "rows": int(output["rows"]),
            "sha256": output["sha256"],
        },
        "development_receipt": {
            "path": str(paths.external_development_receipt),
            "bytes": paths.external_development_receipt.stat().st_size,
            "sha256": sha256(paths.external_development_receipt),
        },
        "symbol_spec": {
            "path": str(paths.external_spec),
            "bytes": paths.external_spec.stat().st_size,
            "sha256": sha256(paths.external_spec),
        },
    }


def validate_external_locked(paths: Paths) -> dict[str, Any]:
    required = [
        paths.external_locked,
        paths.external_locked_receipt,
        paths.external_combined,
        paths.external_final_receipt,
    ]
    if any(not path.is_file() for path in required):
        raise RuntimeError("locked/full AUDCHF authority is incomplete")
    receipt = read_json(paths.external_final_receipt)
    if receipt.get("status") != (
        "COMPLETE_STAGED_FRESH_DEDICATED_PORTABLE_ACQUISITION"
    ):
        raise RuntimeError("unexpected final acquisition status")
    output = receipt.get("output", {})
    if int(output.get("bytes", -1)) != paths.external_combined.stat().st_size:
        raise RuntimeError("combined external byte count mismatch")
    if str(output.get("sha256")) != sha256(paths.external_combined):
        raise RuntimeError("combined external SHA-256 mismatch")
    locked_receipt = read_json(paths.external_locked_receipt)
    if locked_receipt.get("status") != (
        "COMPLETE_FRESH_DEDICATED_PORTABLE_LOCKED_ACQUISITION"
    ):
        raise RuntimeError("unexpected locked acquisition status")
    locked_output = locked_receipt.get("output", {})
    if int(locked_output.get("bytes", -1)) != paths.external_locked.stat().st_size:
        raise RuntimeError("locked external byte count mismatch")
    if str(locked_output.get("sha256")) != sha256(paths.external_locked):
        raise RuntimeError("locked external SHA-256 mismatch")
    return {
        "locked_csv": {
            "path": str(paths.external_locked),
            "bytes": paths.external_locked.stat().st_size,
            "rows": int(locked_output["rows"]),
            "sha256": locked_output["sha256"],
        },
        "combined_csv": {
            "path": str(paths.external_combined),
            "bytes": paths.external_combined.stat().st_size,
            "rows": int(output["rows"]),
            "sha256": output["sha256"],
        },
    }


def validate_implementation_freeze(paths: Paths) -> dict[str, Any]:
    if not paths.implementation_freeze.is_file():
        raise RuntimeError("implementation freeze is absent")
    freeze = read_json(paths.implementation_freeze)
    if freeze.get("status") != "IMPLEMENTATION_FROZEN_PREDEVELOPMENT_OUTCOME":
        raise RuntimeError("unexpected implementation-freeze status")
    adapter = freeze.get("adapter", {})
    this_path = Path(__file__).resolve()
    if int(adapter.get("bytes", -1)) != this_path.stat().st_size:
        raise RuntimeError("frozen adapter byte count mismatch")
    if str(adapter.get("sha256")) != sha256(this_path):
        raise RuntimeError("frozen adapter SHA-256 mismatch")
    return {
        "path": str(paths.implementation_freeze),
        "bytes": paths.implementation_freeze.stat().st_size,
        "sha256": sha256(paths.implementation_freeze),
    }


def load_external(path: Path, end_exclusive: datetime) -> pd.DataFrame:
    columns = [
        "time",
        "open",
        "high",
        "low",
        "close",
        "tick_volume",
        "spread",
        "real_volume",
    ]
    frame = pd.read_csv(path, usecols=columns)
    frame = frame[
        (frame["time"] >= int(WARMUP_START.timestamp()))
        & (frame["time"] < int(end_exclusive.timestamp()))
    ].copy()
    validate_market_frame(frame, "AUDCHF")
    return frame.set_index("time", drop=False)


def load_target(path: Path, end_exclusive: datetime, symbol: str) -> pd.DataFrame:
    dataset = ds.dataset(path, format="parquet")
    expression = (ds.field("time") >= int(WARMUP_START.timestamp())) & (
        ds.field("time") < int(end_exclusive.timestamp())
    )
    table = dataset.to_table(
        columns=[
            "time",
            "open",
            "high",
            "low",
            "close",
            "tick_volume",
            "spread",
            "real_volume",
        ],
        filter=expression,
    )
    frame = table.to_pandas()
    validate_market_frame(frame, symbol)
    return frame.set_index("time", drop=False)


def validate_market_frame(frame: pd.DataFrame, label: str) -> None:
    required = {
        "time",
        "open",
        "high",
        "low",
        "close",
        "tick_volume",
        "spread",
        "real_volume",
    }
    if set(frame.columns) != required:
        raise RuntimeError(f"{label} columns mismatch: {list(frame.columns)}")
    if frame.empty or frame["time"].duplicated().any():
        raise RuntimeError(f"{label} empty or duplicate timestamps")
    if not frame["time"].is_monotonic_increasing:
        raise RuntimeError(f"{label} timestamps are not strictly increasing")
    values = frame[["open", "high", "low", "close"]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise RuntimeError(f"{label} contains nonfinite OHLC")
    if not (frame["high"] >= frame[["open", "close", "low"]].max(axis=1)).all():
        raise RuntimeError(f"{label} high invariant failed")
    if not (frame["low"] <= frame[["open", "close", "high"]].min(axis=1)).all():
        raise RuntimeError(f"{label} low invariant failed")
    if (frame["spread"] < 0).any():
        raise RuntimeError(f"{label} has negative spread")


def exact_rows(frame: pd.DataFrame, epochs: list[int]) -> pd.DataFrame | None:
    positions = frame.index.get_indexer(epochs)
    if (positions < 0).any():
        return None
    return frame.iloc[positions]


def decision_schedule(end_exclusive: datetime) -> Iterable[tuple[date, str, int]]:
    local_start = WARMUP_START.astimezone(NEW_YORK).date()
    local_end = (end_exclusive - timedelta(seconds=1)).astimezone(NEW_YORK).date()
    current = local_start
    while current <= local_end:
        for slot_time in DECISION_TIMES:
            local_dt = datetime.combine(current, slot_time, tzinfo=NEW_YORK)
            utc_dt = local_dt.astimezone(UTC)
            if WARMUP_START <= utc_dt < end_exclusive:
                yield current, slot_time.strftime("%H:%M"), int(utc_dt.timestamp())
        current += timedelta(days=1)


def nearest_rank_75(values: deque[float]) -> float:
    if len(values) != 60:
        raise RuntimeError(f"rank reference length is {len(values)}, expected 60")
    ordered = sorted(finite(value, "rank value") for value in values)
    return ordered[44]


def arithmetic_median_20(values: deque[float]) -> float:
    if len(values) != 20:
        raise RuntimeError(f"risk reference length is {len(values)}, expected 20")
    ordered = sorted(finite(value, "risk-range value") for value in values)
    return (ordered[9] + ordered[10]) / 2.0


def build_states(
    external: pd.DataFrame,
    targets: dict[str, pd.DataFrame],
    end_exclusive: datetime,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    external_history: dict[str, deque[float]] = {
        slot.strftime("%H:%M"): deque(maxlen=60) for slot in DECISION_TIMES
    }
    risk_history: dict[tuple[str, str], deque[float]] = {
        (symbol, slot.strftime("%H:%M")): deque(maxlen=20)
        for symbol in SYMBOLS
        for slot in DECISION_TIMES
    }
    states: list[dict[str, Any]] = []
    normal_dates: set[str] = set()
    structural_slot_counts: dict[str, int] = defaultdict(int)
    gated_slot_counts: dict[str, int] = defaultdict(int)
    sign_counts: dict[str, int] = defaultdict(int)
    warmup_ready_slots = 0
    external_complete_intervals = 0
    target_complete_intervals: dict[str, int] = defaultdict(int)

    for local_date, slot, decision_epoch in decision_schedule(end_exclusive):
        external_epochs = [decision_epoch - 60 * offset for offset in range(30, 0, -1)]
        holding_epochs = [decision_epoch + 60 * offset for offset in range(30)]
        external_rows = exact_rows(external, external_epochs)
        target_rows = {
            symbol: exact_rows(targets[symbol], holding_epochs) for symbol in SYMBOLS
        }
        external_return: float | None = None
        current_ranges: dict[str, float] = {}
        if external_rows is not None:
            external_complete_intervals += 1
            first_open = finite(external_rows["open"].iloc[0], "external open")
            final_close = finite(external_rows["close"].iloc[-1], "external close")
            if first_open <= 0:
                raise RuntimeError("nonpositive external interval open")
            external_return = final_close / first_open - 1.0
        for symbol in SYMBOLS:
            rows = target_rows[symbol]
            if rows is not None:
                target_complete_intervals[symbol] += 1
                current_ranges[symbol] = finite(
                    rows["high"].max() - rows["low"].min(),
                    f"{symbol} holding range",
                )
                if current_ranges[symbol] < 0:
                    raise RuntimeError(f"negative {symbol} holding range")

        external_ready = external_return is not None and len(external_history[slot]) == 60
        risk_ready = all(len(risk_history[(symbol, slot)]) == 20 for symbol in SYMBOLS)
        target_complete = all(target_rows[symbol] is not None for symbol in SYMBOLS)
        structurally_complete = external_ready and risk_ready and target_complete
        if structurally_complete:
            warmup_ready_slots += 1
            if decision_epoch >= int(DEVELOPMENT_START.timestamp()):
                date_text = local_date.isoformat()
                normal_dates.add(date_text)
                structural_slot_counts[slot] += 1
                threshold = nearest_rank_75(external_history[slot])
                absolute_return = abs(finite(external_return, "external return"))
                risk_distances = {
                    symbol: max(
                        POINT, arithmetic_median_20(risk_history[(symbol, slot)])
                    )
                    for symbol in SYMBOLS
                }
                if absolute_return > 0.0 and absolute_return >= threshold:
                    external_sign = "positive" if external_return > 0 else "negative"
                    gated_slot_counts[slot] += 1
                    sign_counts[external_sign] += 1
                    states.append(
                        {
                            "state_sequence": len(states) + 1,
                            "decision_epoch": decision_epoch,
                            "decision_utc": datetime.fromtimestamp(
                                decision_epoch, tz=UTC
                            ).isoformat().replace("+00:00", "Z"),
                            "local_date": date_text,
                            "slot": slot,
                            "external_interval_start_epoch": external_epochs[0],
                            "external_interval_end_epoch": external_epochs[-1],
                            "external_return": external_return,
                            "external_absolute_return": absolute_return,
                            "rank_threshold": threshold,
                            "external_sign": external_sign,
                            "US100_risk_distance": risk_distances["US100"],
                            "US30_risk_distance": risk_distances["US30"],
                        }
                    )

        if external_return is not None:
            external_history[slot].append(abs(external_return))
        for symbol in SYMBOLS:
            if symbol in current_ranges:
                risk_history[(symbol, slot)].append(current_ranges[symbol])

    states.sort(key=lambda row: int(row["decision_epoch"]))
    for expected_sequence, state in enumerate(states, start=1):
        state["state_sequence"] = expected_sequence
    structure = {
        "normal_trading_days": len(normal_dates),
        "normal_trading_dates": sorted(normal_dates),
        "structural_complete_slots": int(sum(structural_slot_counts.values())),
        "structural_slot_counts": dict(sorted(structural_slot_counts.items())),
        "gated_events": len(states),
        "gated_slot_counts": dict(sorted(gated_slot_counts.items())),
        "external_sign_counts": dict(sorted(sign_counts.items())),
        "two_symbol_structural_starts_per_role": 2 * len(states),
        "structural_starts_per_normal_day_per_role": (
            2.0 * len(states) / len(normal_dates) if normal_dates else 0.0
        ),
        "warmup_ready_slots_including_predevelopment": warmup_ready_slots,
        "external_complete_intervals": external_complete_intervals,
        "target_complete_intervals": dict(target_complete_intervals),
    }
    return states, structure


def role_direction(role: str, external_sign: str) -> int:
    sign = 1 if external_sign == "positive" else -1
    if role == "AUDCHF_PULSE_FOLLOW":
        return sign
    if role == "AUDCHF_PULSE_FADE":
        return -sign
    raise RuntimeError(f"unknown role: {role}")


def floor_volume(raw_volume: float) -> float:
    if raw_volume <= 0 or not math.isfinite(raw_volume):
        return 0.0
    steps = math.floor((raw_volume + 1e-12) / VOLUME_STEP)
    return min(VOLUME_MAX, steps * VOLUME_STEP)


def planned_volume(balance: float, risk_distance: float) -> tuple[float, float, str]:
    if not math.isfinite(balance) or balance <= 0:
        return 0.0, 0.0, "NONPOSITIVE_BALANCE"
    risk_per_lot = risk_distance / TICK_SIZE * TICK_VALUE_PER_LOT
    if not math.isfinite(risk_per_lot) or risk_per_lot <= 0:
        raise RuntimeError("nonpositive risk per lot")
    volume = floor_volume(balance * POSITION_RISK / risk_per_lot)
    if volume < VOLUME_MIN:
        minimum_loss = VOLUME_MIN * risk_per_lot
        if minimum_loss <= balance * POSITION_HARD_CAP + 1e-12:
            volume = VOLUME_MIN
        else:
            return 0.0, minimum_loss, "MINIMUM_LOT_HARD_CAP"
    planned_loss = volume * risk_per_lot
    if planned_loss > balance * POSITION_HARD_CAP + 1e-9:
        raise RuntimeError("planned position risk exceeds hard cap")
    return volume, planned_loss, "ACCEPTED"


def money_from_price(price_distance: float, volume: float) -> float:
    return price_distance / TICK_SIZE * TICK_VALUE_PER_LOT * volume


def simulate_trade(
    state: dict[str, Any],
    symbol: str,
    role: str,
    direction: int,
    volume: float,
    planned_loss: float,
    target: pd.DataFrame,
) -> dict[str, Any]:
    decision_epoch = int(state["decision_epoch"])
    epochs = [decision_epoch + 60 * offset for offset in range(30)]
    rows = exact_rows(target, epochs)
    if rows is None:
        raise RuntimeError(f"missing frozen future path for {symbol}")
    risk_distance = finite(state[f"{symbol}_risk_distance"], "risk distance")
    entry_spread_price = finite(rows["spread"].iloc[0], "entry spread") * POINT
    entry_bid = finite(rows["open"].iloc[0], "entry bid")
    if direction > 0:
        entry_price = entry_bid + entry_spread_price
        stop_price = entry_price - risk_distance
        take_price = entry_price + 1.5 * risk_distance
    else:
        entry_price = entry_bid
        stop_price = entry_price + risk_distance
        take_price = entry_price - 1.5 * risk_distance

    exit_reason = "TIME"
    exit_price = 0.0
    exit_epoch = decision_epoch + 30 * 60
    exit_spread_price = finite(rows["spread"].iloc[-1], "exit spread") * POINT
    for _, row in rows.iterrows():
        row_epoch = int(row["time"])
        spread_price = finite(row["spread"], "row spread") * POINT
        bid_low = finite(row["low"], "bid low")
        bid_high = finite(row["high"], "bid high")
        if direction > 0:
            stop_hit = bid_low <= stop_price
            take_hit = bid_high >= take_price
        else:
            ask_low = bid_low + spread_price
            ask_high = bid_high + spread_price
            stop_hit = ask_high >= stop_price
            take_hit = ask_low <= take_price
        if stop_hit:
            exit_reason = "STOP"
            exit_price = stop_price
            exit_epoch = row_epoch + 60
            exit_spread_price = spread_price
            break
        if take_hit:
            exit_reason = "TAKE"
            exit_price = take_price
            exit_epoch = row_epoch + 60
            exit_spread_price = spread_price
            break
    if exit_reason == "TIME":
        final = rows.iloc[-1]
        bid_close = finite(final["close"], "time-exit bid close")
        exit_price = bid_close if direction > 0 else bid_close + exit_spread_price

    price_pnl = exit_price - entry_price if direction > 0 else entry_price - exit_price
    actual_pnl = money_from_price(price_pnl, volume)
    observed_spread_price = entry_spread_price if direction > 0 else exit_spread_price
    observed_spread_burden = money_from_price(observed_spread_price, volume)
    stressed_pnl = actual_pnl - observed_spread_burden
    if not all(
        math.isfinite(value)
        for value in [actual_pnl, stressed_pnl, observed_spread_burden]
    ):
        raise RuntimeError("nonfinite simulated trade economics")
    return {
        "role": role,
        "state_sequence": int(state["state_sequence"]),
        "symbol": symbol,
        "local_date": state["local_date"],
        "slot": state["slot"],
        "external_sign": state["external_sign"],
        "direction": "LONG" if direction > 0 else "SHORT",
        "entry_epoch": decision_epoch,
        "entry_utc": state["decision_utc"],
        "exit_epoch": exit_epoch,
        "exit_utc": datetime.fromtimestamp(exit_epoch, tz=UTC)
        .isoformat()
        .replace("+00:00", "Z"),
        "exit_reason": exit_reason,
        "risk_distance": risk_distance,
        "volume": volume,
        "planned_loss": planned_loss,
        "entry_price": entry_price,
        "stop_price": stop_price,
        "take_price": take_price,
        "exit_price": exit_price,
        "observed_spread_burden": observed_spread_burden,
        "actual_pnl": actual_pnl,
        "stressed_pnl": stressed_pnl,
    }


def update_drawdown(ledger: RoleLedger) -> None:
    ledger.actual_peak = max(ledger.actual_peak, ledger.actual_balance)
    if ledger.actual_peak <= 0.0:
        raise RuntimeError("nonpositive actual peak in drawdown calculation")
    drawdown_usd = ledger.actual_peak - ledger.actual_balance
    drawdown_pct = drawdown_usd / ledger.actual_peak * 100.0
    ledger.max_drawdown_usd = max(ledger.max_drawdown_usd, drawdown_usd)
    ledger.max_drawdown_pct = max(ledger.max_drawdown_pct, drawdown_pct)


def run_role(
    role: str,
    states: list[dict[str, Any]],
    structure: dict[str, Any],
    targets: dict[str, pd.DataFrame],
    epoch_years: list[int],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    ledger = RoleLedger(role=role)
    trades: list[dict[str, Any]] = []
    for state in states:
        snapshot = ledger.actual_balance
        aggregate_planned_loss = 0.0
        pending: list[dict[str, Any]] = []
        for symbol in SYMBOLS:
            risk_distance = finite(state[f"{symbol}_risk_distance"], "risk distance")
            volume, planned_loss, decision = planned_volume(snapshot, risk_distance)
            if decision != "ACCEPTED":
                ledger.risk_blocks += 1
                continue
            if aggregate_planned_loss + planned_loss > snapshot * AGGREGATE_HARD_CAP + 1e-9:
                ledger.risk_blocks += 1
                continue
            aggregate_planned_loss += planned_loss
            direction = role_direction(role, str(state["external_sign"]))
            pending.append(
                simulate_trade(
                    state,
                    symbol,
                    role,
                    direction,
                    volume,
                    planned_loss,
                    targets[symbol],
                )
            )
        pending.sort(key=lambda row: (int(row["exit_epoch"]), SYMBOL_ORDER[row["symbol"]]))
        for trade in pending:
            trade["actual_balance_before"] = ledger.actual_balance
            trade["stressed_balance_before"] = ledger.stressed_balance
            ledger.actual_balance += finite(trade["actual_pnl"], "actual pnl")
            ledger.stressed_balance += finite(trade["stressed_pnl"], "stressed pnl")
            trade["actual_balance_after"] = ledger.actual_balance
            trade["stressed_balance_after"] = ledger.stressed_balance
            update_drawdown(ledger)
            trades.append(trade)

    normal_days = int(structure["normal_trading_days"])
    yearly = {
        str(year): {
            "starts": 0,
            "actual_net_usd": 0.0,
            "stressed_net_usd": 0.0,
        }
        for year in epoch_years
    }
    for trade in trades:
        year = str(int(str(trade["local_date"])[:4]))
        if year in yearly:
            yearly[year]["starts"] += 1
            yearly[year]["actual_net_usd"] += finite(
                trade["actual_pnl"], "year actual pnl"
            )
            yearly[year]["stressed_net_usd"] += finite(
                trade["stressed_pnl"], "year stressed pnl"
            )
    actual_net = ledger.actual_balance - INITIAL_DEPOSIT
    stressed_net = ledger.stressed_balance - INITIAL_DEPOSIT
    starts_per_day = len(trades) / normal_days if normal_days else 0.0
    symbol_breadth = len({trade["symbol"] for trade in trades})
    slot_breadth = len({trade["slot"] for trade in trades})
    sign_breadth = sorted({trade["external_sign"] for trade in trades})
    robust_recovery_unbounded_positive = (
        ledger.max_drawdown_usd == 0.0 and stressed_net > 0.0
    )
    robust_recovery = (
        stressed_net / ledger.max_drawdown_usd
        if ledger.max_drawdown_usd > 0.0
        else None
    )
    metrics = {
        "role": role,
        "starts": len(trades),
        "normal_trading_days": normal_days,
        "starts_per_normal_day": starts_per_day,
        "actual_net_usd": actual_net,
        "stressed_net_usd": stressed_net,
        "ending_actual_balance": ledger.actual_balance,
        "ending_stressed_balance": ledger.stressed_balance,
        "actual_closed_balance_drawdown_usd": ledger.max_drawdown_usd,
        "actual_closed_balance_drawdown_pct": ledger.max_drawdown_pct,
        "robust_recovery": robust_recovery,
        "robust_recovery_unbounded_positive": robust_recovery_unbounded_positive,
        "risk_blocks": ledger.risk_blocks,
        "symbol_breadth": symbol_breadth,
        "decision_slot_breadth": slot_breadth,
        "external_sign_breadth": sign_breadth,
        "epoch_metrics": yearly,
        "exit_counts": {
            str(reason): int(count)
            for reason, count in sorted(
                pd.Series(
                    [trade["exit_reason"] for trade in trades], dtype="string"
                )
                .value_counts()
                .to_dict()
                .items()
            )
        }
        if trades
        else {},
    }
    return metrics, trades


def development_gates(metrics: dict[str, Any]) -> dict[str, bool]:
    epochs = metrics["epoch_metrics"]
    gates = {
        "both_2024_2025_actual_positive": all(
            finite(epochs[str(year)]["actual_net_usd"], "epoch actual") > 0
            for year in [2024, 2025]
        ),
        "both_2024_2025_stressed_positive": all(
            finite(epochs[str(year)]["stressed_net_usd"], "epoch stressed") > 0
            for year in [2024, 2025]
        ),
        "development_actual_strictly_above_149_97": finite(
            metrics["actual_net_usd"], "actual net"
        )
        > 149.97,
        "development_stressed_strictly_above_127_786": finite(
            metrics["stressed_net_usd"], "stressed net"
        )
        > 127.786,
        "drawdown_at_most_37_39_pct": finite(
            metrics["actual_closed_balance_drawdown_pct"], "drawdown"
        )
        <= 37.39,
        "starts_per_normal_day_at_least_3": finite(
            metrics["starts_per_normal_day"], "starts per day"
        )
        >= 3.0,
        "symbol_breadth_at_least_2": int(metrics["symbol_breadth"]) >= 2,
        "decision_slot_breadth_at_least_8": int(metrics["decision_slot_breadth"])
        >= 8,
        "both_external_signs": metrics["external_sign_breadth"]
        == ["negative", "positive"],
    }
    gates["passed"] = all(gates.values())
    return gates


def ranked_development_passers(
    candidate_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    passers = [row for row in candidate_results if row["gates"]["passed"]]
    passers.sort(
        key=lambda row: (
            -finite(row["stressed_net_usd"], "stressed net"),
            finite(row["actual_closed_balance_drawdown_pct"], "drawdown"),
            -min(
                finite(row["epoch_metrics"][str(year)]["stressed_net_usd"], "epoch")
                for year in [2024, 2025]
            ),
            ROLES.index(row["role"]),
        )
    )
    return passers


def whole_gates(metrics: dict[str, Any]) -> dict[str, bool]:
    epochs = metrics["epoch_metrics"]
    gates = {
        "all_2024_2025_2026_actual_positive": all(
            finite(epochs[str(year)]["actual_net_usd"], "epoch actual") > 0
            for year in [2024, 2025, 2026]
        ),
        "all_2024_2025_2026_stressed_positive": all(
            finite(epochs[str(year)]["stressed_net_usd"], "epoch stressed") > 0
            for year in [2024, 2025, 2026]
        ),
        "whole_actual_strictly_above_409_81": finite(
            metrics["actual_net_usd"], "actual net"
        )
        > 409.81,
        "whole_stressed_strictly_above_367_818": finite(
            metrics["stressed_net_usd"], "stressed net"
        )
        > 367.818,
        "drawdown_at_most_37_39_pct": finite(
            metrics["actual_closed_balance_drawdown_pct"], "drawdown"
        )
        <= 37.39,
        "robust_recovery_strictly_above_3_295860215": bool(
            metrics["robust_recovery_unbounded_positive"]
        )
        or (
            metrics["robust_recovery"] is not None
            and finite(metrics["robust_recovery"], "robust recovery")
            > 3.295860215
        ),
        "starts_per_normal_day_at_least_3": finite(
            metrics["starts_per_normal_day"], "starts per day"
        )
        >= 3.0,
        "symbol_breadth_at_least_2": int(metrics["symbol_breadth"]) >= 2,
        "decision_slot_breadth_at_least_8": int(metrics["decision_slot_breadth"])
        >= 8,
        "both_external_signs": metrics["external_sign_breadth"]
        == ["negative", "positive"],
    }
    gates["passed"] = all(gates.values())
    return gates


def min_lot_feasibility(states: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {symbol: 0 for symbol in SYMBOLS}
    maxima = {symbol: 0.0 for symbol in SYMBOLS}
    for state in states:
        for symbol in SYMBOLS:
            risk_distance = finite(state[f"{symbol}_risk_distance"], "risk distance")
            minimum_loss = money_from_price(risk_distance, VOLUME_MIN)
            maxima[symbol] = max(maxima[symbol], minimum_loss)
            if minimum_loss <= INITIAL_DEPOSIT * POSITION_HARD_CAP + 1e-12:
                counts[symbol] += 1
    return {
        "accepted_state_counts_at_initial_100_usd": counts,
        "total_states": len(states),
        "maximum_minimum_lot_planned_loss_usd": maxima,
        "both_symbols_feasible_on_every_state": all(
            counts[symbol] == len(states) for symbol in SYMBOLS
        ),
    }


def atomic_write_outputs(
    outputs: list[tuple[Path, bytes | str]],
) -> None:
    if any(path.exists() for path, _ in outputs):
        existing = [str(path) for path, _ in outputs if path.exists()]
        raise RuntimeError(f"refusing to overwrite output artifacts: {existing}")
    if not outputs:
        return
    for path, _ in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="zeta-f007-adapter-"))
    try:
        staged: list[tuple[Path, Path]] = []
        for index, (final_path, content) in enumerate(outputs):
            stage = staging / f"{index:02d}-{final_path.name}"
            if isinstance(content, bytes):
                stage.write_bytes(content)
            else:
                stage.write_text(content, encoding="utf-8", newline="\n")
            staged.append((stage, final_path))
        for stage, final_path in staged:
            os.replace(stage, final_path)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def dataframe_csv_bytes(frame: pd.DataFrame) -> bytes:
    text = frame.to_csv(
        index=False,
        lineterminator="\n",
        float_format="%.12f",
        quoting=csv.QUOTE_MINIMAL,
    )
    return text.encode("utf-8")


def sanitized_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(metrics, allow_nan=False))
    return result


def precheck(paths: Paths) -> int:
    authorities = validate_static_authorities(paths)
    authorities["external"] = validate_external_development(paths)
    if any(
        path.exists()
        for path in [
            paths.raw_development_result,
            paths.raw_development_states,
            paths.raw_development_trades,
            paths.raw_confirmation_result,
            paths.raw_confirmation_states,
            paths.raw_confirmation_trades,
            paths.raw_native_decisions,
        ]
    ):
        raise RuntimeError("precheck requires an empty output surface")
    external = load_external(paths.external_development, LOCKED_START)
    targets = {
        symbol: load_target(paths.target_files[symbol], LOCKED_START, symbol)
        for symbol in SYMBOLS
    }
    states, structure = build_states(external, targets, LOCKED_START)
    feasibility = min_lot_feasibility(states)
    output = {
        "schema": "zeta-next-independent-audchf-intraday-carry-pulse-adapter-challenge-v1-precheck",
        "status": "VALID_OUTCOME_FREE_PRECHECK",
        "authorities": authorities,
        "structure": structure,
        "minimum_lot_feasibility": feasibility,
        "future_trade_path_simulations": 0,
        "candidate_lifecycles_or_economic_metrics": 0,
        "locked_external_or_target_values_loaded": False,
        "persistent_files_written": 0,
        "broker_account_position_order_or_deal_queries": 0,
    }
    print(json.dumps(output, indent=2, allow_nan=False), flush=True)
    return 0


def development(paths: Paths) -> int:
    authorities = validate_static_authorities(paths)
    authorities["external"] = validate_external_development(paths)
    authorities["implementation_freeze"] = validate_implementation_freeze(paths)
    external = load_external(paths.external_development, LOCKED_START)
    targets = {
        symbol: load_target(paths.target_files[symbol], LOCKED_START, symbol)
        for symbol in SYMBOLS
    }
    states, structure = build_states(external, targets, LOCKED_START)
    candidate_results: list[dict[str, Any]] = []
    all_trades: list[dict[str, Any]] = []
    for role in ROLES:
        metrics, trades = run_role(role, states, structure, targets, [2024, 2025])
        metrics["gates"] = development_gates(metrics)
        candidate_results.append(sanitized_metrics(metrics))
        all_trades.extend(trades)
    passers = ranked_development_passers(candidate_results)
    selected_role = passers[0]["role"] if passers else None
    states_frame = pd.DataFrame(states)
    trades_frame = pd.DataFrame(all_trades)
    states_bytes = dataframe_csv_bytes(states_frame)
    trades_bytes = dataframe_csv_bytes(trades_frame)
    result = {
        "schema": "zeta-next-independent-audchf-intraday-carry-pulse-adapter-challenge-v1-development-result",
        "recorded_at_utc": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "status": (
            "VALID_DEVELOPMENT_COMPLETE_ONE_SELECTED_PASSER"
            if selected_role
            else "VALID_DEVELOPMENT_COMPLETE_NO_PASSER"
        ),
        "family": FAMILY,
        "period": "2024-01-01T00:00:00Z/2026-01-01T00:00:00Z",
        "authorities": authorities,
        "adapter": {
            "path": str(Path(__file__).resolve()),
            "bytes": Path(__file__).stat().st_size,
            "sha256": sha256(Path(__file__).resolve()),
        },
        "structure": structure,
        "minimum_lot_feasibility": min_lot_feasibility(states),
        "candidate_results": candidate_results,
        "complete_passer_count": len(passers),
        "selected_role": selected_role,
        "raw_outputs": {
            "states": {
                "path": str(paths.raw_development_states.relative_to(paths.workspace)).replace("\\", "/"),
                "rows": len(states_frame),
                "bytes": len(states_bytes),
                "sha256": hashlib.sha256(states_bytes).hexdigest().upper(),
            },
            "trades": {
                "path": str(paths.raw_development_trades.relative_to(paths.workspace)).replace("\\", "/"),
                "rows": len(trades_frame),
                "bytes": len(trades_bytes),
                "sha256": hashlib.sha256(trades_bytes).hexdigest().upper(),
            },
        },
        "locked_external_or_target_values_loaded": False,
        "ea_source_files": 0,
        "mt5_compile_or_tester_paths": 0,
        "broker_account_position_order_or_deal_queries": 0,
    }
    result_text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    atomic_write_outputs(
        [
            (paths.raw_development_states, states_bytes),
            (paths.raw_development_trades, trades_bytes),
            (paths.raw_development_result, result_text),
        ]
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "complete_passer_count": result["complete_passer_count"],
                "selected_role": selected_role,
                "candidate_results": candidate_results,
            },
            indent=2,
            allow_nan=False,
        ),
        flush=True,
    )
    return 0


def confirmation(paths: Paths) -> int:
    authorities = validate_static_authorities(paths)
    authorities["external_development"] = validate_external_development(paths)
    authorities["external_locked"] = validate_external_locked(paths)
    authorities["implementation_freeze"] = validate_implementation_freeze(paths)
    if not paths.raw_development_result.is_file() or not paths.durable_development_result.is_file():
        raise RuntimeError("confirmation requires raw and durable development results")
    if sha256(paths.raw_development_result) != sha256(paths.durable_development_result):
        raise RuntimeError("raw and durable development results are not byte-identical")
    development_result = read_json(paths.raw_development_result)
    durable_result = read_json(paths.durable_development_result)
    if development_result != durable_result:
        raise RuntimeError("raw and durable development result objects differ")
    if development_result.get("status") != "VALID_DEVELOPMENT_COMPLETE_ONE_SELECTED_PASSER":
        raise RuntimeError("confirmation requires a valid one-passer development status")
    complete_passer_count = int(development_result.get("complete_passer_count", 0))
    if complete_passer_count < 1:
        raise RuntimeError("confirmation requires at least one complete development passer")
    selected_role = str(development_result.get("selected_role"))
    if selected_role not in ROLES or durable_result.get("selected_role") != selected_role:
        raise RuntimeError("durable/raw selected role mismatch")
    candidate_results = development_result.get("candidate_results")
    if not isinstance(candidate_results, list) or len(candidate_results) != len(ROLES):
        raise RuntimeError("development candidate bundle is incomplete")
    result_roles = [str(row.get("role")) for row in candidate_results]
    if result_roles != ROLES:
        raise RuntimeError("development candidate role order changed")
    ranked_passers = ranked_development_passers(candidate_results)
    if (
        len(ranked_passers) != complete_passer_count
        or not ranked_passers
        or ranked_passers[0]["role"] != selected_role
    ):
        raise RuntimeError("selected role does not match the frozen passer ranking")
    recorded_adapter = development_result.get("adapter", {})
    this_path = Path(__file__).resolve()
    if (
        int(recorded_adapter.get("bytes", -1)) != this_path.stat().st_size
        or str(recorded_adapter.get("sha256")) != sha256(this_path)
    ):
        raise RuntimeError("development result was not produced by the frozen adapter")
    external = load_external(paths.external_combined, WHOLE_END)
    targets = {
        symbol: load_target(paths.target_files[symbol], WHOLE_END, symbol)
        for symbol in SYMBOLS
    }
    states, structure = build_states(external, targets, WHOLE_END)
    metrics, trades = run_role(
        selected_role, states, structure, targets, [2024, 2025, 2026]
    )
    metrics["gates"] = whole_gates(metrics)
    states_frame = pd.DataFrame(states)
    trades_frame = pd.DataFrame(trades)
    states_bytes = dataframe_csv_bytes(states_frame)
    trades_bytes = dataframe_csv_bytes(trades_frame)
    decisions: list[dict[str, Any]] = []
    if metrics["gates"]["passed"]:
        for state in states:
            direction = role_direction(selected_role, str(state["external_sign"]))
            for symbol in SYMBOLS:
                decisions.append(
                    {
                        "sequence": len(decisions) + 1,
                        "role": selected_role,
                        "decision_epoch": int(state["decision_epoch"]),
                        "decision_utc": state["decision_utc"],
                        "valid_until_epoch": int(state["decision_epoch"]) + 59,
                        "symbol": symbol,
                        "direction": "LONG" if direction > 0 else "SHORT",
                        "risk_distance": state[f"{symbol}_risk_distance"],
                        "external_sign": state["external_sign"],
                        "slot": state["slot"],
                    }
                )
    decision_bytes = dataframe_csv_bytes(pd.DataFrame(decisions)) if decisions else b""
    result = {
        "schema": "zeta-next-independent-audchf-intraday-carry-pulse-adapter-challenge-v1-confirmation-result",
        "recorded_at_utc": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "status": (
            "VALID_WHOLE_PROXY_PASS_NATIVE_ESCALATION_READY"
            if metrics["gates"]["passed"]
            else "VALID_WHOLE_PROXY_NONCONFIRMATION"
        ),
        "family": FAMILY,
        "selected_role": selected_role,
        "authorities": authorities,
        "structure": structure,
        "metrics": sanitized_metrics(metrics),
        "native_decision_tape_written": bool(decisions),
        "raw_outputs": {
            "states": {
                "rows": len(states_frame),
                "bytes": len(states_bytes),
                "sha256": hashlib.sha256(states_bytes).hexdigest().upper(),
            },
            "trades": {
                "rows": len(trades_frame),
                "bytes": len(trades_bytes),
                "sha256": hashlib.sha256(trades_bytes).hexdigest().upper(),
            },
            "native_decisions": {
                "rows": len(decisions),
                "bytes": len(decision_bytes),
                "sha256": hashlib.sha256(decision_bytes).hexdigest().upper()
                if decisions
                else None,
            },
        },
        "broker_account_position_order_or_deal_queries": 0,
        "proxy_victory_claimed": False,
    }
    outputs: list[tuple[Path, bytes | str]] = [
        (paths.raw_confirmation_states, states_bytes),
        (paths.raw_confirmation_trades, trades_bytes),
        (
            paths.raw_confirmation_result,
            json.dumps(result, indent=2, allow_nan=False) + "\n",
        ),
    ]
    if decisions:
        outputs.append((paths.raw_native_decisions, decision_bytes))
    atomic_write_outputs(outputs)
    print(json.dumps(result, indent=2, allow_nan=False), flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", required=True, choices=["precheck", "development", "confirmation"]
    )
    args = parser.parse_args()
    paths = make_paths()
    if args.mode == "precheck":
        return precheck(paths)
    if args.mode == "development":
        return development(paths)
    return confirmation(paths)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ADAPTER_ERROR: {exc}", file=sys.stderr, flush=True)
        raise
