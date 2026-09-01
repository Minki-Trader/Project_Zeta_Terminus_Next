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
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pyarrow.dataset as ds


FAMILY = "independent-leveraged-etf-close-rebalance-pressure-adapter-challenge-v1"
VARIANTS = [
    "LEVERAGED_ETF_CLOSE_PRESSURE_TIME_CLOSE",
    "LEVERAGED_ETF_CLOSE_PRESSURE_TAKE_1P5R",
]
EXTERNAL_SYMBOLS = ["QQQ", "TQQQ"]
TARGET_SYMBOL = "US100"
NEW_YORK = ZoneInfo("America/New_York")
SERVER_ZONE = ZoneInfo("Europe/Helsinki")
DECISION_LOCAL_TIME = time(15, 30)
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
POSITION_RISK = 0.04
POSITION_HARD_CAP = 0.06
AGGREGATE_HARD_CAP = 0.06
RANK_REFERENCE_LENGTH = 60
RISK_REFERENCE_LENGTH = 20
AUDIT_MINIMUM_SLICE_EVENTS = 10

EXPECTED = {
    "selection_audit": "F76BE1617FE412BFE1C4997DA1B4CAEAE5E6DD5C66E3C04D553872D1392256FF",
    "contract": "801764B6E7F89E7909DE6C2D87354CF93A5EFCB6D3B9FFBD03AF3420A9906460",
    "declaration": "A8D22D6737CEBE4F5C188AE05E769183CB63A58B1B10707E60BF68CC81C91798",
    "source_correction": "24A875B43D5CB58FF34A9B3F03DA720D4C65AE2D85BD67324FA262AB29AC9024",
    "source_receipt": "0DF4B566B320B97391CCFAA8CC7675B32A014C404D01A41B3D8CCDC93F871362",
    "time_correction": "EDD382D7319E7A19BB5E2A5047650BFFD9D0ACA6E57B38F2EEC9D5DC9894A7A7",
    "external_receipt": "BE5B134375B849D600698183BAC83964BD4FAFBA4EE898479E97D32BE65A0692",
    "QQQ": "1E02B68F542A89FF94DE3B5C0B91C728D2F6A6562920D8C2DFD02AD88F8B6EF4",
    "TQQQ": "8CE67D515A94546F403995C50227B1B13FFD925B35C7968FF464989E37638F4C",
    "QQQ_spec": "8EE242F4460D9D743D94D38A273299FA67D9E827709882F677DB905D8D374FDB",
    "TQQQ_spec": "3EF090872A9EBD98D1578C4AC3E03C40EC99C114204D0B22498B8111F95ECC1C",
    "US100": "634A8545D83C7A520E81A07E273255BD3FA771AA0EC29381D04E6D25A64C6BB2",
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
    source_correction: Path
    source_receipt: Path
    time_correction: Path
    implementation_freeze: Path
    requirements: Path
    external_development_receipt: Path
    external_locked_receipt: Path
    external_final_receipt: Path
    external_development: dict[str, Path]
    external_locked: dict[str, Path]
    external_combined: dict[str, Path]
    external_specs: dict[str, Path]
    target: Path
    raw_development_result: Path
    raw_development_states: Path
    raw_development_trades: Path
    raw_development_audit: Path
    raw_development_audit_paths: Path
    durable_development_result: Path
    durable_development_audit: Path
    raw_confirmation_result: Path
    raw_confirmation_states: Path
    raw_confirmation_trades: Path
    raw_native_decisions: Path


@dataclass
class VariantLedger:
    variant: str
    actual_balance: float = INITIAL_DEPOSIT
    stressed_balance: float = INITIAL_DEPOSIT
    actual_peak: float = INITIAL_DEPOSIT
    max_drawdown_usd: float = 0.0
    max_drawdown_pct: float = 0.0
    risk_block_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    first_risk_block: dict[str, Any] | None = None


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


def finite(value: object, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise RuntimeError(f"nonfinite {name}: {value}")
    return number


def rel(path: Path, workspace: Path) -> str:
    return str(path.absolute().relative_to(workspace.absolute())).replace("\\", "/")


def make_paths() -> Paths:
    script = Path(__file__).absolute()
    family_root = script.parents[1]
    workspace = script.parents[4]
    expected_root = workspace / "lab" / "research" / FAMILY
    if family_root != expected_root:
        raise RuntimeError(f"unexpected family root: {family_root}")
    raw_root = workspace / "lab" / "artifacts" / "raw" / FAMILY
    output_root = raw_root / "output"
    evidence = family_root / "evidence"
    external = raw_root / "input" / "external"
    return Paths(
        workspace=workspace,
        family_root=family_root,
        raw_root=raw_root,
        output_root=output_root,
        selection_audit=workspace
        / "lab"
        / "evidence"
        / "INDEPENDENT_V8_CHALLENGE_POST_FAMILY_007_WHOLE_MAP_RECOMPARE_V1.json",
        contract=family_root / "config" / "challenge-contract.json",
        declaration=evidence
        / "INDEPENDENT_LEVERAGED_ETF_CLOSE_REBALANCE_PRESSURE_ADAPTER_CHALLENGE_V1_DECLARATION.json",
        source_correction=evidence
        / "INDEPENDENT_LEVERAGED_ETF_CLOSE_REBALANCE_PRESSURE_ADAPTER_CHALLENGE_V1_SOURCE_CANONICALIZATION_CORRECTION.json",
        source_receipt=evidence
        / "INDEPENDENT_LEVERAGED_ETF_CLOSE_REBALANCE_PRESSURE_ADAPTER_CHALLENGE_V1_DEVELOPMENT_SOURCE_RECEIPT.json",
        time_correction=evidence
        / "INDEPENDENT_LEVERAGED_ETF_CLOSE_REBALANCE_PRESSURE_ADAPTER_CHALLENGE_V1_RAW_TIME_SEMANTICS_CORRECTION.json",
        implementation_freeze=evidence
        / "INDEPENDENT_LEVERAGED_ETF_CLOSE_REBALANCE_PRESSURE_ADAPTER_CHALLENGE_V1_IMPLEMENTATION_FREEZE.json",
        requirements=family_root / "adapter" / "requirements-adapter.txt",
        external_development_receipt=external
        / "EXTERNAL_DEVELOPMENT_ACQUISITION_RECEIPT.json",
        external_locked_receipt=external / "EXTERNAL_LOCKED_ACQUISITION_RECEIPT.json",
        external_final_receipt=external / "EXTERNAL_ACQUISITION_RECEIPT.json",
        external_development={
            symbol: external / f"{symbol}_M1_DEVELOPMENT.csv"
            for symbol in EXTERNAL_SYMBOLS
        },
        external_locked={
            symbol: external / f"{symbol}_M1_LOCKED.csv"
            for symbol in EXTERNAL_SYMBOLS
        },
        external_combined={
            symbol: external / f"{symbol}_M1.csv" for symbol in EXTERNAL_SYMBOLS
        },
        external_specs={
            symbol: external / f"{symbol}_SYMBOL_SPEC.json"
            for symbol in EXTERNAL_SYMBOLS
        },
        target=raw_root / "input" / "target" / "US100_M1.parquet",
        raw_development_result=output_root / "development-result.json",
        raw_development_states=output_root / "development-states.csv",
        raw_development_trades=output_root / "development-trades.csv",
        raw_development_audit=output_root / "development-improvement-audit.json",
        raw_development_audit_paths=output_root
        / "development-improvement-paths.csv",
        durable_development_result=evidence
        / "INDEPENDENT_LEVERAGED_ETF_CLOSE_REBALANCE_PRESSURE_ADAPTER_CHALLENGE_V1_DEVELOPMENT_RESULT.json",
        durable_development_audit=evidence
        / "INDEPENDENT_LEVERAGED_ETF_CLOSE_REBALANCE_PRESSURE_ADAPTER_CHALLENGE_V1_DEVELOPMENT_IMPROVEMENT_AUDIT.json",
        raw_confirmation_result=output_root / "confirmation-result.json",
        raw_confirmation_states=output_root / "confirmation-states.csv",
        raw_confirmation_trades=output_root / "confirmation-trades.csv",
        raw_native_decisions=output_root / "native-decisions.csv",
    )


def check_hash(path: Path, expected: str, label: str, workspace: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing {label}: {path}")
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError(f"{label} SHA-256 mismatch: {actual} != {expected}")
    return {"path": rel(path, workspace), "bytes": path.stat().st_size, "sha256": actual}


def validate_static_authorities(paths: Paths) -> dict[str, Any]:
    authorities = {
        "selection_audit": check_hash(
            paths.selection_audit,
            EXPECTED["selection_audit"],
            "selection audit",
            paths.workspace,
        ),
        "contract": check_hash(
            paths.contract, EXPECTED["contract"], "contract", paths.workspace
        ),
        "declaration": check_hash(
            paths.declaration,
            EXPECTED["declaration"],
            "declaration",
            paths.workspace,
        ),
        "source_correction": check_hash(
            paths.source_correction,
            EXPECTED["source_correction"],
            "source canonicalization correction",
            paths.workspace,
        ),
        "source_receipt": check_hash(
            paths.source_receipt,
            EXPECTED["source_receipt"],
            "development source receipt",
            paths.workspace,
        ),
        "time_correction": check_hash(
            paths.time_correction,
            EXPECTED["time_correction"],
            "raw-time semantic correction",
            paths.workspace,
        ),
        TARGET_SYMBOL: check_hash(
            paths.target, EXPECTED[TARGET_SYMBOL], "US100 target", paths.workspace
        ),
    }
    contract = read_json(paths.contract)
    if contract.get("family") != f"lab/research/{FAMILY}/":
        raise RuntimeError("contract family mismatch")
    time_contract = contract.get("session_clock", {}).get("raw_time_semantics", {})
    if (
        time_contract.get("broker_server_iana_zone") != "Europe/Helsinki"
        or time_contract.get("no_economic_geometry_change") is not True
    ):
        raise RuntimeError("contract raw-time semantics mismatch")
    declaration = read_json(paths.declaration)
    if declaration.get("status") != (
        "DECLARED_PRERUNTIME_PREACQUISITION_PREINPUT_PRERANK_"
        "PREIMPLEMENTATION_PREOUTCOME"
    ):
        raise RuntimeError("unexpected declaration status")
    source_receipt = read_json(paths.source_receipt)
    if source_receipt.get("status") != (
        "COMPLETE_FRESH_ORIGINAL_BROKER_DEVELOPMENT_SOURCE_AND_BYTE_EQUAL_TARGET"
    ):
        raise RuntimeError("unexpected development source receipt status")
    time_correction = read_json(paths.time_correction)
    if time_correction.get("status") != (
        "RAW_TIME_SEMANTICS_CORRECTED_PREIMPLEMENTATION_"
        "PREPRICE_DERIVATION_PREOUTCOME"
    ):
        raise RuntimeError("unexpected raw-time correction status")
    return authorities


def validate_development_inputs(paths: Paths) -> dict[str, Any]:
    receipt_info = check_hash(
        paths.external_development_receipt,
        EXPECTED["external_receipt"],
        "external development receipt",
        paths.workspace,
    )
    receipt = read_json(paths.external_development_receipt)
    if receipt.get("status") != "COMPLETE_FRESH_DEDICATED_PORTABLE_DEVELOPMENT_ACQUISITION":
        raise RuntimeError("unexpected external development status")
    if receipt.get("locked_external_values_acquired") is not False:
        raise RuntimeError("development receipt did not preserve the locked boundary")
    if receipt.get("source", {}).get("broker_account_position_order_or_deal_queries") != 0:
        raise RuntimeError("external receipt contains a forbidden broker-state query")
    outputs = receipt.get("outputs", {})
    specs = receipt.get("symbol_specs", {})
    authority: dict[str, Any] = {"receipt": receipt_info, "symbols": {}}
    for symbol in EXTERNAL_SYMBOLS:
        output = outputs.get(symbol, {})
        path = paths.external_development[symbol]
        info = check_hash(path, EXPECTED[symbol], f"{symbol} development CSV", paths.workspace)
        if (
            int(output.get("bytes", -1)) != path.stat().st_size
            or int(output.get("rows", 0)) < 200_000
            or str(output.get("sha256")) != EXPECTED[symbol]
        ):
            raise RuntimeError(f"{symbol} development receipt mismatch")
        spec_path = paths.external_specs[symbol]
        spec_info = check_hash(
            spec_path,
            EXPECTED[f"{symbol}_spec"],
            f"{symbol} specification",
            paths.workspace,
        )
        spec_receipt = specs.get(symbol, {})
        if (
            int(spec_receipt.get("bytes", -1)) != spec_path.stat().st_size
            or str(spec_receipt.get("sha256")) != EXPECTED[f"{symbol}_spec"]
        ):
            raise RuntimeError(f"{symbol} specification receipt mismatch")
        spec = read_json(spec_path)
        if spec.get("symbol") != symbol or spec.get("signal_uses_external_spread") is not False:
            raise RuntimeError(f"invalid {symbol} signal specification")
        authority["symbols"][symbol] = {"csv": info, "specification": spec_info}
    return authority


def validate_locked_inputs(paths: Paths) -> dict[str, Any]:
    required = [
        paths.external_locked_receipt,
        paths.external_final_receipt,
        *paths.external_locked.values(),
        *paths.external_combined.values(),
    ]
    if any(not path.is_file() for path in required):
        raise RuntimeError("locked/combined external authority is incomplete")
    locked_receipt = read_json(paths.external_locked_receipt)
    final_receipt = read_json(paths.external_final_receipt)
    if locked_receipt.get("status") != "COMPLETE_FRESH_DEDICATED_PORTABLE_LOCKED_ACQUISITION":
        raise RuntimeError("unexpected locked external status")
    if final_receipt.get("status") != "COMPLETE_STAGED_FRESH_DEDICATED_PORTABLE_ACQUISITION":
        raise RuntimeError("unexpected final external status")
    locked_outputs = locked_receipt.get("outputs", {})
    combined_outputs = final_receipt.get("outputs", {})
    authority: dict[str, Any] = {
        "locked_receipt": {
            "path": rel(paths.external_locked_receipt, paths.workspace),
            "bytes": paths.external_locked_receipt.stat().st_size,
            "sha256": sha256(paths.external_locked_receipt),
        },
        "final_receipt": {
            "path": rel(paths.external_final_receipt, paths.workspace),
            "bytes": paths.external_final_receipt.stat().st_size,
            "sha256": sha256(paths.external_final_receipt),
        },
        "symbols": {},
    }
    for symbol in EXTERNAL_SYMBOLS:
        locked_path = paths.external_locked[symbol]
        combined_path = paths.external_combined[symbol]
        locked_info = locked_outputs.get(symbol, {})
        combined_info = combined_outputs.get(symbol, {})
        locked_hash = sha256(locked_path)
        combined_hash = sha256(combined_path)
        if (
            int(locked_info.get("bytes", -1)) != locked_path.stat().st_size
            or str(locked_info.get("sha256")) != locked_hash
            or int(combined_info.get("bytes", -1)) != combined_path.stat().st_size
            or str(combined_info.get("sha256")) != combined_hash
        ):
            raise RuntimeError(f"{symbol} locked/final receipt mismatch")
        authority["symbols"][symbol] = {
            "locked": {
                "path": rel(locked_path, paths.workspace),
                "bytes": locked_path.stat().st_size,
                "sha256": locked_hash,
            },
            "combined": {
                "path": rel(combined_path, paths.workspace),
                "bytes": combined_path.stat().st_size,
                "sha256": combined_hash,
            },
        }
    return authority


def validate_implementation_freeze(paths: Paths) -> dict[str, Any]:
    if not paths.implementation_freeze.is_file():
        raise RuntimeError("implementation freeze is absent")
    freeze = read_json(paths.implementation_freeze)
    if freeze.get("status") != "IMPLEMENTATION_FROZEN_PREDEVELOPMENT_OUTCOME":
        raise RuntimeError("unexpected implementation-freeze status")
    adapter = freeze.get("adapter", {})
    requirements = freeze.get("requirements", {})
    this_path = Path(__file__).absolute()
    if (
        int(adapter.get("bytes", -1)) != this_path.stat().st_size
        or str(adapter.get("sha256")) != sha256(this_path)
    ):
        raise RuntimeError("frozen adapter identity mismatch")
    if (
        int(requirements.get("bytes", -1)) != paths.requirements.stat().st_size
        or str(requirements.get("sha256")) != sha256(paths.requirements)
    ):
        raise RuntimeError("frozen adapter requirements identity mismatch")
    return {
        "path": rel(paths.implementation_freeze, paths.workspace),
        "bytes": paths.implementation_freeze.stat().st_size,
        "sha256": sha256(paths.implementation_freeze),
    }


def raw_wall_epoch_for_true_boundary(boundary: datetime) -> int:
    if boundary.tzinfo is None:
        raise RuntimeError("true boundary must be timezone-aware")
    server = boundary.astimezone(SERVER_ZONE)
    encoded = server.replace(tzinfo=UTC)
    return int(encoded.timestamp())


def normalize_server_wall_time(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    raw = pd.to_numeric(frame["time"], errors="raise").astype("int64")
    if raw.duplicated().any() or not raw.is_monotonic_increasing:
        raise RuntimeError(f"{label} raw timestamps are not unique and increasing")
    naive = pd.to_datetime(raw, unit="s", utc=True).dt.tz_localize(None)
    try:
        true_utc = naive.dt.tz_localize(
            SERVER_ZONE, ambiguous="raise", nonexistent="raise"
        ).dt.tz_convert(UTC)
    except Exception as exc:
        raise RuntimeError(f"{label} ambiguous/nonexistent server wall-clock") from exc
    nanoseconds = true_utc.astype("int64")
    if (nanoseconds % 1_000_000_000 != 0).any():
        raise RuntimeError(f"{label} normalized timestamps are not exact seconds")
    result = frame.copy()
    result.insert(0, "raw_time", raw.to_numpy())
    result["time"] = (nanoseconds // 1_000_000_000).astype("int64")
    if result["time"].duplicated().any() or not result["time"].is_monotonic_increasing:
        raise RuntimeError(f"{label} normalized timestamps are not unique and increasing")
    return result


def validate_market_frame(frame: pd.DataFrame, label: str) -> None:
    required = {
        "raw_time",
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
    if frame.empty:
        raise RuntimeError(f"{label} is empty")
    values = frame[["open", "high", "low", "close"]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise RuntimeError(f"{label} contains nonfinite OHLC")
    if not (frame["high"] >= frame[["open", "close", "low"]].max(axis=1)).all():
        raise RuntimeError(f"{label} high invariant failed")
    if not (frame["low"] <= frame[["open", "close", "high"]].min(axis=1)).all():
        raise RuntimeError(f"{label} low invariant failed")
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        raise RuntimeError(f"{label} contains nonpositive OHLC")
    if (frame["spread"] < 0).any():
        raise RuntimeError(f"{label} has negative spread")


def market_columns() -> list[str]:
    return [
        "time",
        "open",
        "high",
        "low",
        "close",
        "tick_volume",
        "spread",
        "real_volume",
    ]


def load_external(path: Path, end_exclusive: datetime, label: str) -> pd.DataFrame:
    frame = pd.read_csv(path, usecols=market_columns())
    frame = normalize_server_wall_time(frame, label)
    start_epoch = int(WARMUP_START.timestamp())
    end_epoch = int(end_exclusive.timestamp())
    frame = frame[(frame["time"] >= start_epoch) & (frame["time"] < end_epoch)].copy()
    validate_market_frame(frame, label)
    return frame.set_index("time", drop=False)


def load_target(path: Path, end_exclusive: datetime) -> pd.DataFrame:
    dataset = ds.dataset(path, format="parquet")
    raw_start = raw_wall_epoch_for_true_boundary(WARMUP_START)
    raw_end = raw_wall_epoch_for_true_boundary(end_exclusive)
    expression = (ds.field("time") >= raw_start) & (ds.field("time") < raw_end)
    table = dataset.to_table(columns=market_columns(), filter=expression)
    frame = normalize_server_wall_time(table.to_pandas(), TARGET_SYMBOL)
    start_epoch = int(WARMUP_START.timestamp())
    end_epoch = int(end_exclusive.timestamp())
    frame = frame[(frame["time"] >= start_epoch) & (frame["time"] < end_epoch)].copy()
    validate_market_frame(frame, TARGET_SYMBOL)
    if frame["time"].max() >= end_epoch:
        raise RuntimeError("target loader crossed its true-UTC upper boundary")
    return frame.set_index("time", drop=False)


def exact_rows(frame: pd.DataFrame, epochs: Sequence[int]) -> pd.DataFrame | None:
    positions = frame.index.get_indexer(epochs)
    if (positions < 0).any():
        return None
    rows = frame.iloc[positions]
    if rows["time"].tolist() != list(epochs):
        raise RuntimeError("exact-row lookup returned a misordered timestamp set")
    return rows


def decision_schedule(end_exclusive: datetime) -> Iterable[tuple[date, int]]:
    first_local = WARMUP_START.astimezone(NEW_YORK).date()
    last_local = (end_exclusive - timedelta(seconds=1)).astimezone(NEW_YORK).date()
    current = first_local
    while current <= last_local:
        local_dt = datetime.combine(current, DECISION_LOCAL_TIME, tzinfo=NEW_YORK)
        utc_dt = local_dt.astimezone(UTC)
        if WARMUP_START <= utc_dt < end_exclusive:
            yield current, int(utc_dt.timestamp())
        current += timedelta(days=1)


def nearest_rank_75(values: deque[float]) -> float:
    if len(values) != RANK_REFERENCE_LENGTH:
        raise RuntimeError("rank history length mismatch")
    ordered = sorted(finite(value, "rank value") for value in values)
    return ordered[44]


def arithmetic_median_20(values: deque[float]) -> float:
    if len(values) != RISK_REFERENCE_LENGTH:
        raise RuntimeError("risk history length mismatch")
    ordered = sorted(finite(value, "risk range") for value in values)
    return (ordered[9] + ordered[10]) / 2.0


def date_list_hash(values: Sequence[str]) -> str:
    return hashlib.sha256(("\n".join(values) + "\n").encode("utf-8")).hexdigest().upper()


def build_states(
    external: dict[str, pd.DataFrame],
    target: pd.DataFrame,
    end_exclusive: datetime,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    qqq_history: deque[float] = deque(maxlen=RANK_REFERENCE_LENGTH)
    risk_history: deque[float] = deque(maxlen=RISK_REFERENCE_LENGTH)
    states: list[dict[str, Any]] = []
    normal_dates: list[str] = []
    epoch_normal_days: dict[str, int] = defaultdict(int)
    common_complete_days = 0
    structurally_ready_days = 0
    nonzero_qqq_days = 0
    coherence_pass_days = 0
    rank_pass_days = 0
    sign_counts: dict[str, int] = defaultdict(int)

    for local_date, decision_epoch in decision_schedule(end_exclusive):
        signal_epochs = [decision_epoch - 3600 * 6 + offset * 60 for offset in range(360)]
        path_epochs = [decision_epoch + offset * 60 for offset in range(30)]
        qqq_rows = exact_rows(external["QQQ"], signal_epochs)
        tqqq_rows = exact_rows(external["TQQQ"], signal_epochs)
        target_rows = exact_rows(target, path_epochs)
        if qqq_rows is None or tqqq_rows is None or target_rows is None:
            continue
        common_complete_days += 1
        qqq_open = finite(qqq_rows["open"].iloc[0], "QQQ open")
        tqqq_open = finite(tqqq_rows["open"].iloc[0], "TQQQ open")
        if qqq_open <= 0 or tqqq_open <= 0:
            raise RuntimeError("nonpositive external session open")
        qqq_return = finite(qqq_rows["close"].iloc[-1], "QQQ close") / qqq_open - 1.0
        tqqq_return = finite(tqqq_rows["close"].iloc[-1], "TQQQ close") / tqqq_open - 1.0
        current_range = finite(
            target_rows["high"].max() - target_rows["low"].min(),
            "US100 close-half-hour range",
        )
        if current_range < 0:
            raise RuntimeError("negative US100 close-half-hour range")
        ready = (
            len(qqq_history) == RANK_REFERENCE_LENGTH
            and len(risk_history) == RISK_REFERENCE_LENGTH
        )
        if ready:
            structurally_ready_days += 1
            if decision_epoch >= int(DEVELOPMENT_START.timestamp()):
                date_text = local_date.isoformat()
                normal_dates.append(date_text)
                epoch_normal_days[str(local_date.year)] += 1
                qqq_abs = abs(qqq_return)
                threshold = nearest_rank_75(qqq_history)
                risk_distance = max(1.0, arithmetic_median_20(risk_history))
                nonzero = qqq_return != 0.0 and math.isfinite(qqq_return)
                same_sign = (
                    nonzero
                    and tqqq_return != 0.0
                    and math.copysign(1.0, qqq_return) == math.copysign(1.0, tqqq_return)
                )
                coherence = same_sign and abs(tqqq_return) >= 2.0 * qqq_abs
                rank_pass = nonzero and qqq_abs >= threshold
                if nonzero:
                    nonzero_qqq_days += 1
                if coherence:
                    coherence_pass_days += 1
                if rank_pass:
                    rank_pass_days += 1
                if coherence and rank_pass:
                    external_sign = "positive" if qqq_return > 0 else "negative"
                    sign_counts[external_sign] += 1
                    states.append(
                        {
                            "state_sequence": len(states) + 1,
                            "decision_epoch": decision_epoch,
                            "decision_utc": datetime.fromtimestamp(decision_epoch, tz=UTC)
                            .isoformat()
                            .replace("+00:00", "Z"),
                            "local_date": date_text,
                            "external_interval_start_epoch": signal_epochs[0],
                            "external_interval_end_epoch": signal_epochs[-1],
                            "target_path_start_epoch": path_epochs[0],
                            "target_path_end_epoch": path_epochs[-1],
                            "QQQ_return": qqq_return,
                            "TQQQ_return": tqqq_return,
                            "QQQ_absolute_return": qqq_abs,
                            "TQQQ_to_QQQ_absolute_ratio": abs(tqqq_return) / qqq_abs,
                            "QQQ_rank_threshold": threshold,
                            "external_sign": external_sign,
                            "US100_risk_distance": risk_distance,
                        }
                    )
        qqq_history.append(abs(qqq_return))
        risk_history.append(current_range)

    for expected_sequence, state in enumerate(states, start=1):
        if int(state["state_sequence"]) != expected_sequence:
            raise RuntimeError("state sequence is not contiguous")
    structure = {
        "server_wall_clock_zone": "Europe/Helsinki",
        "decision_zone": "America/New_York",
        "common_complete_days_including_warmup": common_complete_days,
        "structurally_ready_days_including_predevelopment": structurally_ready_days,
        "normal_trading_days": len(normal_dates),
        "normal_trading_dates_first": normal_dates[0] if normal_dates else None,
        "normal_trading_dates_last": normal_dates[-1] if normal_dates else None,
        "normal_trading_dates_sha256": date_list_hash(normal_dates),
        "epoch_normal_days": dict(sorted(epoch_normal_days.items())),
        "nonzero_QQQ_days": nonzero_qqq_days,
        "coherence_pass_days": coherence_pass_days,
        "rank_pass_days": rank_pass_days,
        "gated_events": len(states),
        "external_sign_counts": dict(sorted(sign_counts.items())),
        "structural_starts_per_normal_day_per_variant": (
            len(states) / len(normal_dates) if normal_dates else 0.0
        ),
        "future_trade_path_simulations_during_state_construction": 0,
    }
    return states, structure


def direction_from_sign(external_sign: str) -> int:
    if external_sign == "positive":
        return 1
    if external_sign == "negative":
        return -1
    raise RuntimeError(f"unknown external sign: {external_sign}")


def floor_volume(raw_volume: float) -> float:
    if raw_volume <= 0 or not math.isfinite(raw_volume):
        return 0.0
    steps = math.floor((raw_volume + 1e-12) / VOLUME_STEP)
    return min(VOLUME_MAX, steps * VOLUME_STEP)


def money_from_price(price_distance: float, volume: float) -> float:
    return price_distance / TICK_SIZE * TICK_VALUE_PER_LOT * volume


def planned_volume(balance: float, risk_distance: float) -> tuple[float, float, str]:
    if not math.isfinite(balance) or balance <= 0:
        return 0.0, 0.0, "NONPOSITIVE_BALANCE"
    risk_per_lot = money_from_price(risk_distance, 1.0)
    if risk_per_lot <= 0 or not math.isfinite(risk_per_lot):
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
        raise RuntimeError("planned position loss exceeds hard cap")
    return volume, planned_loss, "ACCEPTED"


def frozen_path_rows(state: dict[str, Any], target: pd.DataFrame) -> pd.DataFrame:
    decision_epoch = int(state["decision_epoch"])
    rows = exact_rows(target, [decision_epoch + offset * 60 for offset in range(30)])
    if rows is None:
        raise RuntimeError("missing frozen US100 future path")
    return rows


def simulate_trade(
    state: dict[str, Any],
    variant: str,
    volume: float,
    planned_loss: float,
    target: pd.DataFrame,
) -> dict[str, Any]:
    if variant not in VARIANTS:
        raise RuntimeError(f"unknown variant: {variant}")
    rows = frozen_path_rows(state, target)
    direction = direction_from_sign(str(state["external_sign"]))
    decision_epoch = int(state["decision_epoch"])
    risk_distance = finite(state["US100_risk_distance"], "risk distance")
    entry_bid = finite(rows["open"].iloc[0], "entry Bid")
    entry_spread_price = finite(rows["spread"].iloc[0], "entry spread") * POINT
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
    exit_spread_price = finite(rows["spread"].iloc[-1], "final spread") * POINT
    for _, row in rows.iterrows():
        row_epoch = int(row["time"])
        spread_price = finite(row["spread"], "row spread") * POINT
        bid_low = finite(row["low"], "Bid low")
        bid_high = finite(row["high"], "Bid high")
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
        if variant == VARIANTS[1] and take_hit:
            exit_reason = "TAKE"
            exit_price = take_price
            exit_epoch = row_epoch + 60
            exit_spread_price = spread_price
            break
    if exit_reason == "TIME":
        final_bid_close = finite(rows["close"].iloc[-1], "time-exit Bid close")
        exit_price = final_bid_close if direction > 0 else final_bid_close + exit_spread_price

    price_pnl = exit_price - entry_price if direction > 0 else entry_price - exit_price
    actual_pnl = money_from_price(price_pnl, volume)
    observed_spread_price = entry_spread_price if direction > 0 else exit_spread_price
    observed_spread_burden = money_from_price(observed_spread_price, volume)
    stressed_pnl = actual_pnl - observed_spread_burden
    risk_money = money_from_price(risk_distance, volume)
    if not all(
        math.isfinite(value)
        for value in [
            actual_pnl,
            stressed_pnl,
            observed_spread_burden,
            price_pnl,
            risk_money,
        ]
    ):
        raise RuntimeError("nonfinite simulated trade economics")
    return {
        "variant": variant,
        "state_sequence": int(state["state_sequence"]),
        "symbol": TARGET_SYMBOL,
        "local_date": state["local_date"],
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
        "take_price": take_price if variant == VARIANTS[1] else None,
        "exit_price": exit_price,
        "observed_spread_burden": observed_spread_burden,
        "actual_pnl": actual_pnl,
        "stressed_pnl": stressed_pnl,
        "actual_R": actual_pnl / risk_money if risk_money > 0 else None,
        "stressed_R": stressed_pnl / risk_money if risk_money > 0 else None,
    }


def update_drawdown(ledger: VariantLedger) -> None:
    ledger.actual_peak = max(ledger.actual_peak, ledger.actual_balance)
    if ledger.actual_peak <= 0:
        raise RuntimeError("nonpositive actual peak")
    drawdown_usd = ledger.actual_peak - ledger.actual_balance
    drawdown_pct = drawdown_usd / ledger.actual_peak * 100.0
    ledger.max_drawdown_usd = max(ledger.max_drawdown_usd, drawdown_usd)
    ledger.max_drawdown_pct = max(ledger.max_drawdown_pct, drawdown_pct)


def run_variant(
    variant: str,
    states: list[dict[str, Any]],
    structure: dict[str, Any],
    target: pd.DataFrame,
    epoch_years: Sequence[int],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    ledger = VariantLedger(variant=variant)
    trades: list[dict[str, Any]] = []
    for state in states:
        snapshot = ledger.actual_balance
        risk_distance = finite(state["US100_risk_distance"], "risk distance")
        volume, planned_loss, decision = planned_volume(snapshot, risk_distance)
        if decision == "ACCEPTED" and planned_loss > snapshot * AGGREGATE_HARD_CAP + 1e-9:
            decision = "AGGREGATE_HARD_CAP"
        if decision != "ACCEPTED":
            ledger.risk_block_counts[decision] += 1
            if ledger.first_risk_block is None:
                ledger.first_risk_block = {
                    "state_sequence": int(state["state_sequence"]),
                    "local_date": state["local_date"],
                    "reason": decision,
                    "actual_balance": snapshot,
                    "minimum_or_planned_loss": planned_loss,
                }
            continue
        trade = simulate_trade(state, variant, volume, planned_loss, target)
        trade["actual_balance_before"] = ledger.actual_balance
        trade["stressed_balance_before"] = ledger.stressed_balance
        ledger.actual_balance += finite(trade["actual_pnl"], "actual PnL")
        ledger.stressed_balance += finite(trade["stressed_pnl"], "stressed PnL")
        trade["actual_balance_after"] = ledger.actual_balance
        trade["stressed_balance_after"] = ledger.stressed_balance
        update_drawdown(ledger)
        trades.append(trade)

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
            yearly[year]["actual_net_usd"] += finite(trade["actual_pnl"], "year actual")
            yearly[year]["stressed_net_usd"] += finite(
                trade["stressed_pnl"], "year stressed"
            )
    actual_net = ledger.actual_balance - INITIAL_DEPOSIT
    stressed_net = ledger.stressed_balance - INITIAL_DEPOSIT
    normal_days = int(structure["normal_trading_days"])
    robust_recovery_unbounded_positive = ledger.max_drawdown_usd == 0 and stressed_net > 0
    robust_recovery = (
        stressed_net / ledger.max_drawdown_usd if ledger.max_drawdown_usd > 0 else None
    )
    exit_counts: dict[str, int] = defaultdict(int)
    sign_counts: dict[str, int] = defaultdict(int)
    for trade in trades:
        exit_counts[str(trade["exit_reason"])] += 1
        sign_counts[str(trade["external_sign"])] += 1
    metrics = {
        "variant": variant,
        "starts": len(trades),
        "normal_trading_days": normal_days,
        "starts_per_normal_day": len(trades) / normal_days if normal_days else 0.0,
        "actual_net_usd": actual_net,
        "stressed_net_usd": stressed_net,
        "ending_actual_balance": ledger.actual_balance,
        "ending_stressed_balance": ledger.stressed_balance,
        "actual_closed_balance_drawdown_usd": ledger.max_drawdown_usd,
        "actual_closed_balance_drawdown_pct": ledger.max_drawdown_pct,
        "robust_recovery": robust_recovery,
        "robust_recovery_unbounded_positive": robust_recovery_unbounded_positive,
        "risk_blocks": int(sum(ledger.risk_block_counts.values())),
        "risk_block_counts": dict(sorted(ledger.risk_block_counts.items())),
        "first_risk_block": ledger.first_risk_block,
        "external_sign_breadth": sorted(sign_counts),
        "external_sign_start_counts": dict(sorted(sign_counts.items())),
        "epoch_metrics": yearly,
        "exit_counts": dict(sorted(exit_counts.items())),
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
        "starts_per_normal_day_at_least_0_2": finite(
            metrics["starts_per_normal_day"], "starts per day"
        )
        >= 0.2,
        "at_least_40_starts_in_each_development_year": all(
            int(epochs[str(year)]["starts"]) >= 40 for year in [2024, 2025]
        ),
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
            VARIANTS.index(str(row["variant"])),
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
        "whole_actual_strictly_above_409_81": finite(metrics["actual_net_usd"], "actual")
        > 409.81,
        "whole_stressed_strictly_above_367_818": finite(
            metrics["stressed_net_usd"], "stressed"
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
            and finite(metrics["robust_recovery"], "robust recovery") > 3.295860215
        ),
        "starts_per_normal_day_at_least_0_2": finite(
            metrics["starts_per_normal_day"], "starts per day"
        )
        >= 0.2,
        "at_least_40_starts_in_each_epoch": all(
            int(epochs[str(year)]["starts"]) >= 40 for year in [2024, 2025, 2026]
        ),
        "both_external_signs": metrics["external_sign_breadth"]
        == ["negative", "positive"],
    }
    gates["passed"] = all(gates.values())
    return gates


def build_improvement_paths(
    states: list[dict[str, Any]], target: pd.DataFrame
) -> list[dict[str, Any]]:
    rows_out: list[dict[str, Any]] = []
    for state in states:
        rows = frozen_path_rows(state, target)
        direction = direction_from_sign(str(state["external_sign"]))
        risk_distance = finite(state["US100_risk_distance"], "audit risk distance")
        entry_bid = finite(rows["open"].iloc[0], "audit entry Bid")
        entry_spread_price = finite(rows["spread"].iloc[0], "audit entry spread") * POINT
        final_bid = finite(rows["close"].iloc[-1], "audit final Bid")
        final_spread_price = finite(rows["spread"].iloc[-1], "audit final spread") * POINT
        gross_price = direction * (final_bid - entry_bid)
        observed_cost_price = entry_spread_price if direction > 0 else final_spread_price
        actual_full_hold_price = gross_price - observed_cost_price
        stressed_full_hold_price = gross_price - 2.0 * observed_cost_price
        if direction > 0:
            execution_entry = entry_bid + entry_spread_price
            mfe_price = max(0.0, finite(rows["high"].max(), "audit max Bid") - execution_entry)
            mae_price = max(0.0, execution_entry - finite(rows["low"].min(), "audit min Bid"))
        else:
            ask_low = rows["low"].astype(float) + rows["spread"].astype(float) * POINT
            ask_high = rows["high"].astype(float) + rows["spread"].astype(float) * POINT
            execution_entry = entry_bid
            mfe_price = max(0.0, execution_entry - finite(ask_low.min(), "audit min Ask"))
            mae_price = max(0.0, finite(ask_high.max(), "audit max Ask") - execution_entry)
        risk_money_one_lot = money_from_price(risk_distance, 1.0)
        time_trade = simulate_trade(
            state,
            VARIANTS[0],
            1.0,
            risk_money_one_lot,
            target,
        )
        take_trade = simulate_trade(
            state,
            VARIANTS[1],
            1.0,
            risk_money_one_lot,
            target,
        )
        time_actual_r = finite(time_trade["actual_R"], "time actual R")
        time_stressed_r = finite(time_trade["stressed_R"], "time stressed R")
        take_actual_r = finite(take_trade["actual_R"], "take actual R")
        take_stressed_r = finite(take_trade["stressed_R"], "take stressed R")
        delta_actual_r = take_actual_r - time_actual_r
        delta_stressed_r = take_stressed_r - time_stressed_r
        rows_out.append(
            {
                "state_sequence": int(state["state_sequence"]),
                "local_date": state["local_date"],
                "year": int(str(state["local_date"])[:4]),
                "external_sign": state["external_sign"],
                "direction": "LONG" if direction > 0 else "SHORT",
                "risk_distance": risk_distance,
                "raw_gross_full_hold_price": gross_price,
                "raw_actual_full_hold_price": actual_full_hold_price,
                "raw_stressed_full_hold_price": stressed_full_hold_price,
                "raw_gross_full_hold_R": gross_price / risk_distance,
                "raw_actual_full_hold_R": actual_full_hold_price / risk_distance,
                "raw_stressed_full_hold_R": stressed_full_hold_price / risk_distance,
                "observed_cost_price": observed_cost_price,
                "observed_cost_R": observed_cost_price / risk_distance,
                "doubled_cost_price": 2.0 * observed_cost_price,
                "doubled_cost_R": 2.0 * observed_cost_price / risk_distance,
                "MFE_price": mfe_price,
                "MAE_price": mae_price,
                "MFE_R": mfe_price / risk_distance,
                "MAE_R": mae_price / risk_distance,
                "TIME_exit_reason": time_trade["exit_reason"],
                "TIME_actual_R": time_actual_r,
                "TIME_stressed_R": time_stressed_r,
                "TAKE_1P5R_exit_reason": take_trade["exit_reason"],
                "TAKE_1P5R_actual_R": take_actual_r,
                "TAKE_1P5R_stressed_R": take_stressed_r,
                "TAKE_minus_TIME_actual_R": delta_actual_r,
                "TAKE_minus_TIME_stressed_R": delta_stressed_r,
                "shared_stop": (
                    time_trade["exit_reason"] == "STOP"
                    and take_trade["exit_reason"] == "STOP"
                ),
                "take_avoided_later_time_variant_stop": (
                    take_trade["exit_reason"] == "TAKE"
                    and time_trade["exit_reason"] == "STOP"
                ),
                "take_truncated_greater_time_variant_profit": (
                    take_trade["exit_reason"] == "TAKE" and delta_actual_r < -1e-12
                ),
            }
        )
    return rows_out


def mean(values: Sequence[float]) -> float | None:
    return float(np.mean(values)) if values else None


def quantile(values: Sequence[float], probability: float) -> float | None:
    return float(np.quantile(values, probability)) if values else None


def raw_edge_summary(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    gross_r = [finite(row["raw_gross_full_hold_R"], "gross R") for row in rows]
    actual_r = [finite(row["raw_actual_full_hold_R"], "actual R") for row in rows]
    stressed_r = [finite(row["raw_stressed_full_hold_R"], "stressed R") for row in rows]
    mfe_r = [finite(row["MFE_R"], "MFE R") for row in rows]
    mae_r = [finite(row["MAE_R"], "MAE R") for row in rows]
    absolute_gross_price = sum(
        abs(finite(row["raw_gross_full_hold_price"], "gross price")) for row in rows
    )
    observed_cost_price = sum(
        finite(row["observed_cost_price"], "observed cost") for row in rows
    )
    return {
        "events": len(rows),
        "mean_raw_gross_full_hold_R": mean(gross_r),
        "mean_raw_actual_full_hold_R": mean(actual_r),
        "mean_raw_stressed_full_hold_R": mean(stressed_r),
        "raw_gross_positive_rate": (
            sum(value > 0 for value in gross_r) / len(gross_r) if gross_r else None
        ),
        "raw_actual_positive_rate": (
            sum(value > 0 for value in actual_r) / len(actual_r) if actual_r else None
        ),
        "raw_stressed_positive_rate": (
            sum(value > 0 for value in stressed_r) / len(stressed_r)
            if stressed_r
            else None
        ),
        "mean_MFE_R": mean(mfe_r),
        "median_MFE_R": quantile(mfe_r, 0.5),
        "p90_MFE_R": quantile(mfe_r, 0.9),
        "mean_MAE_R": mean(mae_r),
        "median_MAE_R": quantile(mae_r, 0.5),
        "p90_MAE_R": quantile(mae_r, 0.9),
        "sum_absolute_raw_gross_price": absolute_gross_price,
        "sum_observed_cost_price": observed_cost_price,
        "observed_cost_share_of_absolute_raw_gross": (
            observed_cost_price / absolute_gross_price if absolute_gross_price > 0 else None
        ),
        "doubled_cost_share_of_absolute_raw_gross": (
            2.0 * observed_cost_price / absolute_gross_price
            if absolute_gross_price > 0
            else None
        ),
    }


def exit_comparison_summary(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    actual_delta = [
        finite(row["TAKE_minus_TIME_actual_R"], "take-time actual delta") for row in rows
    ]
    stressed_delta = [
        finite(row["TAKE_minus_TIME_stressed_R"], "take-time stressed delta")
        for row in rows
    ]
    return {
        "events": len(rows),
        "mean_TAKE_minus_TIME_actual_R": mean(actual_delta),
        "mean_TAKE_minus_TIME_stressed_R": mean(stressed_delta),
        "positive_delta_events": sum(value > 1e-12 for value in actual_delta),
        "negative_delta_events": sum(value < -1e-12 for value in actual_delta),
        "zero_delta_events": sum(abs(value) <= 1e-12 for value in actual_delta),
        "shared_stop_events": sum(bool(row["shared_stop"]) for row in rows),
        "TAKE_exit_events": sum(
            row["TAKE_1P5R_exit_reason"] == "TAKE" for row in rows
        ),
        "TAKE_avoided_later_TIME_stop_events": sum(
            bool(row["take_avoided_later_time_variant_stop"]) for row in rows
        ),
        "TAKE_truncated_greater_TIME_profit_events": sum(
            bool(row["take_truncated_greater_time_variant_profit"]) for row in rows
        ),
    }


def slice_rows(
    rows: Sequence[dict[str, Any]], field_name: str, value: object
) -> list[dict[str, Any]]:
    return [row for row in rows if row[field_name] == value]


def build_improvement_audit(
    paths_rows: list[dict[str, Any]],
    candidate_results: list[dict[str, Any]],
) -> dict[str, Any]:
    raw_by_year = {
        str(year): raw_edge_summary(slice_rows(paths_rows, "year", year))
        for year in [2024, 2025]
    }
    raw_by_sign = {
        sign: raw_edge_summary(slice_rows(paths_rows, "external_sign", sign))
        for sign in ["negative", "positive"]
    }
    exit_by_year = {
        str(year): exit_comparison_summary(slice_rows(paths_rows, "year", year))
        for year in [2024, 2025]
    }
    exit_by_sign = {
        sign: exit_comparison_summary(slice_rows(paths_rows, "external_sign", sign))
        for sign in ["negative", "positive"]
    }
    raw_slices = [*raw_by_year.values(), *raw_by_sign.values()]
    exit_slices = [*exit_by_year.values(), *exit_by_sign.values()]
    raw_edge_broad = all(
        int(summary["events"]) >= AUDIT_MINIMUM_SLICE_EVENTS
        and finite(summary["mean_raw_stressed_full_hold_R"], "slice stressed edge") > 0
        for summary in raw_slices
    )
    exit_improvement_broad = all(
        int(summary["events"]) >= AUDIT_MINIMUM_SLICE_EVENTS
        and finite(
            summary["mean_TAKE_minus_TIME_stressed_R"], "slice stressed exit delta"
        )
        > 0
        for summary in exit_slices
    )
    overall_exit = exit_comparison_summary(paths_rows)
    exit_improvement_broad = (
        exit_improvement_broad
        and int(overall_exit["positive_delta_events"])
        > int(overall_exit["negative_delta_events"])
    )
    broad_headroom = raw_edge_broad or exit_improvement_broad
    variant_risk = {
        str(result["variant"]): {
            "starts": result["starts"],
            "risk_blocks": result["risk_blocks"],
            "risk_block_counts": result["risk_block_counts"],
            "first_risk_block": result["first_risk_block"],
            "ending_actual_balance": result["ending_actual_balance"],
            "ending_stressed_balance": result["ending_stressed_balance"],
            "epoch_metrics": result["epoch_metrics"],
        }
        for result in candidate_results
    }
    if raw_edge_broad and exit_improvement_broad:
        seed = "BROAD_COST_SURVIVING_RAW_EDGE_AND_EXIT_TRUNCATION_SUCCESSOR_SEED"
    elif raw_edge_broad:
        seed = "BROAD_COST_SURVIVING_RAW_EDGE_SUCCESSOR_SEED"
    elif exit_improvement_broad:
        seed = "BROAD_EXIT_TRUNCATION_SUCCESSOR_SEED"
    else:
        seed = None
    return {
        "schema": "zeta-next-independent-leveraged-etf-close-rebalance-pressure-adapter-challenge-v1-improvement-audit",
        "status": "COMPLETE_FROZEN_IMPROVEMENT_POTENTIAL_AUDIT",
        "family": FAMILY,
        "definitions": {
            "raw_full_hold": "directional 15:30 Bid open to 15:59 Bid close before the shared stop or favorable barrier",
            "actual_full_hold": "raw full-hold direction less the observed direction-specific entry or exit spread",
            "stressed_full_hold": "raw full-hold direction less twice the observed direction-specific spread",
            "MFE_MAE": "nonnegative execution-price excursions over the exact fixed thirty-row path, divided by the frozen risk distance for R",
            "exit_delta": "one-lot normalized TAKE_1P5R outcome minus TIME_CLOSE outcome under identical state, entry, stop and risk distance",
            "broad_slice_minimum_events": AUDIT_MINIMUM_SLICE_EVENTS,
            "broad_raw_edge_rule": "mean stressed full-hold R must be positive in both calendar years and both external-sign slices, each with the minimum event count",
            "broad_exit_rule": "mean stressed take-minus-time R must be positive in both years and both signs, each with the minimum event count, and positive actual deltas must outnumber negative deltas overall",
        },
        "raw_signal_direction": {
            "overall": raw_edge_summary(paths_rows),
            "by_year": raw_by_year,
            "by_external_sign": raw_by_sign,
        },
        "exit_truncation_and_stop_overlap": {
            "overall": overall_exit,
            "by_year": exit_by_year,
            "by_external_sign": exit_by_sign,
        },
        "risk_blocks_and_capital_depletion": variant_risk,
        "broad_cost_surviving_raw_edge": raw_edge_broad,
        "broad_exit_truncation_improvement": exit_improvement_broad,
        "broad_causal_improvement_headroom": broad_headroom,
        "bounded_successor_seed": seed,
        "closure_recommendation": (
            "RECOMPARE_ALL_PROGRAMS_BEFORE_ANY_SEPARATELY_DECLARED_SUCCESSOR"
            if broad_headroom
            else "CLOSE_FAMILY_NO_BROAD_CAUSAL_IMPROVEMENT_HEADROOM"
        ),
        "undeclared_variant_executions": 0,
        "audit_authorizes_automatic_followup": False,
    }


def min_lot_feasibility(states: Sequence[dict[str, Any]]) -> dict[str, Any]:
    accepted = 0
    maximum_minimum_loss = 0.0
    for state in states:
        risk_distance = finite(state["US100_risk_distance"], "risk distance")
        minimum_loss = money_from_price(risk_distance, VOLUME_MIN)
        maximum_minimum_loss = max(maximum_minimum_loss, minimum_loss)
        if minimum_loss <= INITIAL_DEPOSIT * POSITION_HARD_CAP + 1e-12:
            accepted += 1
    return {
        "total_states": len(states),
        "accepted_states_at_initial_100_usd": accepted,
        "maximum_minimum_lot_planned_loss_usd": maximum_minimum_loss,
        "feasible_on_every_state": accepted == len(states),
    }


def dataframe_csv_bytes(frame: pd.DataFrame) -> bytes:
    text = frame.to_csv(
        index=False,
        lineterminator="\n",
        float_format="%.12f",
        quoting=csv.QUOTE_MINIMAL,
    )
    return text.encode("utf-8")


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode(
        "utf-8"
    )


def sanitized(value: object) -> Any:
    return json.loads(json.dumps(value, allow_nan=False))


def atomic_write_outputs(outputs: list[tuple[Path, bytes]]) -> None:
    existing = [str(path) for path, _ in outputs if path.exists()]
    if existing:
        raise RuntimeError(f"refusing to overwrite output artifacts: {existing}")
    if not outputs:
        return
    for path, _ in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="zeta-f008-adapter-"))
    try:
        staged: list[tuple[Path, Path]] = []
        for index, (final_path, content) in enumerate(outputs):
            stage = staging / f"{index:02d}-{final_path.name}"
            stage.write_bytes(content)
            staged.append((stage, final_path))
        for stage, final_path in staged:
            os.replace(stage, final_path)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def empty_output_surface(paths: Paths, mode: str) -> None:
    development = [
        paths.raw_development_result,
        paths.raw_development_states,
        paths.raw_development_trades,
        paths.raw_development_audit,
        paths.raw_development_audit_paths,
    ]
    confirmation = [
        paths.raw_confirmation_result,
        paths.raw_confirmation_states,
        paths.raw_confirmation_trades,
        paths.raw_native_decisions,
    ]
    check = development + confirmation if mode == "precheck" else (
        development if mode == "development" else confirmation
    )
    existing = [rel(path, paths.workspace) for path in check if path.exists()]
    if existing:
        raise RuntimeError(f"{mode} requires an empty output surface: {existing}")


def load_development_market(
    paths: Paths,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    external = {
        symbol: load_external(paths.external_development[symbol], LOCKED_START, symbol)
        for symbol in EXTERNAL_SYMBOLS
    }
    target = load_target(paths.target, LOCKED_START)
    return external, target


def precheck(paths: Paths) -> int:
    authorities = validate_static_authorities(paths)
    authorities["development_inputs"] = validate_development_inputs(paths)
    empty_output_surface(paths, "precheck")
    external, target = load_development_market(paths)
    states, structure = build_states(external, target, LOCKED_START)
    if not states:
        raise RuntimeError("outcome-free precheck found no gated event")
    feasibility = min_lot_feasibility(states)
    output = {
        "schema": "zeta-next-independent-leveraged-etf-close-rebalance-pressure-adapter-challenge-v1-precheck",
        "status": "VALID_OUTCOME_FREE_PRECHECK",
        "family": FAMILY,
        "authorities": authorities,
        "structure": structure,
        "minimum_lot_feasibility": feasibility,
        "time_normalization": {
            "raw_encoding": "Europe/Helsinki server wall-clock encoded as Unix-like seconds",
            "normalized_to": "true UTC then America/New_York",
            "ambiguous_or_nonexistent_server_wall_clock": "fail closed",
        },
        "current_day_target_range_used_for_same_day_entry_risk": False,
        "future_trade_path_simulations": 0,
        "variant_exit_outcomes": 0,
        "candidate_lifecycles_or_economic_metrics": 0,
        "improvement_audit_values": 0,
        "locked_external_or_target_rows_loaded": False,
        "persistent_files_written": 0,
        "broker_account_position_order_or_deal_queries": 0,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False), flush=True)
    return 0


def output_receipt(path: Path, content: bytes, rows: int, workspace: Path) -> dict[str, Any]:
    return {
        "path": rel(path, workspace),
        "rows": rows,
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest().upper(),
    }


def ordered_manifest(items: Sequence[tuple[str, bytes]]) -> str:
    text = "".join(
        f"{name}\t{len(content)}\t{hashlib.sha256(content).hexdigest().upper()}\n"
        for name, content in items
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def development(paths: Paths) -> int:
    authorities = validate_static_authorities(paths)
    authorities["development_inputs"] = validate_development_inputs(paths)
    authorities["implementation_freeze"] = validate_implementation_freeze(paths)
    empty_output_surface(paths, "development")
    external, target = load_development_market(paths)
    states, structure = build_states(external, target, LOCKED_START)
    if not states:
        raise RuntimeError("development found no gated state")

    candidate_results: list[dict[str, Any]] = []
    all_trades: list[dict[str, Any]] = []
    for variant in VARIANTS:
        metrics, trades = run_variant(
            variant, states, structure, target, epoch_years=[2024, 2025]
        )
        metrics["gates"] = development_gates(metrics)
        candidate_results.append(sanitized(metrics))
        all_trades.extend(trades)
    for tape_sequence, trade in enumerate(all_trades, start=1):
        trade["tape_sequence"] = tape_sequence
    passers = ranked_development_passers(candidate_results)
    selected_variant = str(passers[0]["variant"]) if passers else None

    improvement_paths = build_improvement_paths(states, target)
    audit = build_improvement_audit(improvement_paths, candidate_results)
    recorded_at = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
    adapter_identity = {
        "path": rel(Path(__file__).absolute(), paths.workspace),
        "bytes": Path(__file__).stat().st_size,
        "sha256": sha256(Path(__file__).absolute()),
    }
    requirements_identity = {
        "path": rel(paths.requirements, paths.workspace),
        "bytes": paths.requirements.stat().st_size,
        "sha256": sha256(paths.requirements),
    }
    states_bytes = dataframe_csv_bytes(pd.DataFrame(states))
    trades_bytes = dataframe_csv_bytes(pd.DataFrame(all_trades))
    audit_paths_bytes = dataframe_csv_bytes(pd.DataFrame(improvement_paths))
    audit["recorded_at_utc"] = recorded_at
    audit["authorities"] = authorities
    audit["adapter"] = adapter_identity
    audit["requirements"] = requirements_identity
    audit["path_tape"] = output_receipt(
        paths.raw_development_audit_paths,
        audit_paths_bytes,
        len(improvement_paths),
        paths.workspace,
    )
    audit_bytes = json_bytes(audit)

    raw_outputs = {
        "states": output_receipt(
            paths.raw_development_states, states_bytes, len(states), paths.workspace
        ),
        "trades": output_receipt(
            paths.raw_development_trades,
            trades_bytes,
            len(all_trades),
            paths.workspace,
        ),
        "improvement_paths": output_receipt(
            paths.raw_development_audit_paths,
            audit_paths_bytes,
            len(improvement_paths),
            paths.workspace,
        ),
        "improvement_audit": output_receipt(
            paths.raw_development_audit, audit_bytes, 1, paths.workspace
        ),
    }
    manifest_items = [
        ("development-states.csv", states_bytes),
        ("development-trades.csv", trades_bytes),
        ("development-improvement-paths.csv", audit_paths_bytes),
        ("development-improvement-audit.json", audit_bytes),
    ]
    result = {
        "schema": "zeta-next-independent-leveraged-etf-close-rebalance-pressure-adapter-challenge-v1-development-result",
        "recorded_at_utc": recorded_at,
        "status": (
            "VALID_DEVELOPMENT_COMPLETE_ONE_SELECTED_PASSER"
            if selected_variant
            else "VALID_DEVELOPMENT_COMPLETE_NO_PASSER"
        ),
        "family": FAMILY,
        "period": "2024-01-01T00:00:00Z/2026-01-01T00:00:00Z",
        "authorities": authorities,
        "adapter": adapter_identity,
        "requirements": requirements_identity,
        "structure": structure,
        "minimum_lot_feasibility": min_lot_feasibility(states),
        "candidate_results": candidate_results,
        "complete_passer_count": len(passers),
        "selected_variant": selected_variant,
        "improvement_audit": {
            "complete": True,
            "status": audit["status"],
            "broad_causal_improvement_headroom": audit[
                "broad_causal_improvement_headroom"
            ],
            "bounded_successor_seed": audit["bounded_successor_seed"],
            "closure_recommendation": audit["closure_recommendation"],
        },
        "raw_outputs": raw_outputs,
        "ordered_four_artifact_manifest_sha256": ordered_manifest(manifest_items),
        "locked_external_or_target_rows_loaded": False,
        "undeclared_variant_executions": 0,
        "ea_source_files": 0,
        "mt5_compile_or_tester_paths": 0,
        "broker_account_position_order_or_deal_queries": 0,
    }
    result_bytes = json_bytes(result)
    atomic_write_outputs(
        [
            (paths.raw_development_states, states_bytes),
            (paths.raw_development_trades, trades_bytes),
            (paths.raw_development_audit_paths, audit_paths_bytes),
            (paths.raw_development_audit, audit_bytes),
            (paths.raw_development_result, result_bytes),
        ]
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "complete_passer_count": len(passers),
                "selected_variant": selected_variant,
                "candidate_results": candidate_results,
                "improvement_audit": result["improvement_audit"],
            },
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        ),
        flush=True,
    )
    return 0


def validate_development_for_confirmation(paths: Paths) -> tuple[dict[str, Any], str]:
    required = [
        paths.raw_development_result,
        paths.durable_development_result,
        paths.raw_development_audit,
        paths.durable_development_audit,
    ]
    if any(not path.is_file() for path in required):
        raise RuntimeError("confirmation requires raw and durable development result/audit")
    if sha256(paths.raw_development_result) != sha256(paths.durable_development_result):
        raise RuntimeError("raw and durable development results are not byte-identical")
    if sha256(paths.raw_development_audit) != sha256(paths.durable_development_audit):
        raise RuntimeError("raw and durable improvement audits are not byte-identical")
    result = read_json(paths.durable_development_result)
    audit = read_json(paths.durable_development_audit)
    if result.get("status") != "VALID_DEVELOPMENT_COMPLETE_ONE_SELECTED_PASSER":
        raise RuntimeError("confirmation requires a valid selected development passer")
    if audit.get("status") != "COMPLETE_FROZEN_IMPROVEMENT_POTENTIAL_AUDIT":
        raise RuntimeError("confirmation requires the complete frozen improvement audit")
    candidates = result.get("candidate_results")
    if not isinstance(candidates, list) or [row.get("variant") for row in candidates] != VARIANTS:
        raise RuntimeError("development candidate bundle is incomplete or reordered")
    passers = ranked_development_passers(candidates)
    selected = str(result.get("selected_variant"))
    if (
        not passers
        or selected not in VARIANTS
        or passers[0]["variant"] != selected
        or len(passers) != int(result.get("complete_passer_count", -1))
    ):
        raise RuntimeError("development selected-variant ranking mismatch")
    recorded_adapter = result.get("adapter", {})
    this_path = Path(__file__).absolute()
    if (
        int(recorded_adapter.get("bytes", -1)) != this_path.stat().st_size
        or str(recorded_adapter.get("sha256")) != sha256(this_path)
    ):
        raise RuntimeError("development result adapter identity mismatch")
    return result, selected


def confirmation(paths: Paths) -> int:
    authorities = validate_static_authorities(paths)
    authorities["development_inputs"] = validate_development_inputs(paths)
    authorities["locked_inputs"] = validate_locked_inputs(paths)
    authorities["implementation_freeze"] = validate_implementation_freeze(paths)
    development_result, selected_variant = validate_development_for_confirmation(paths)
    empty_output_surface(paths, "confirmation")
    external = {
        symbol: load_external(paths.external_combined[symbol], WHOLE_END, symbol)
        for symbol in EXTERNAL_SYMBOLS
    }
    target = load_target(paths.target, WHOLE_END)
    states, structure = build_states(external, target, WHOLE_END)
    metrics, trades = run_variant(
        selected_variant,
        states,
        structure,
        target,
        epoch_years=[2024, 2025, 2026],
    )
    metrics["gates"] = whole_gates(metrics)
    metrics = sanitized(metrics)
    for tape_sequence, trade in enumerate(trades, start=1):
        trade["tape_sequence"] = tape_sequence
    decisions: list[dict[str, Any]] = []
    if metrics["gates"]["passed"]:
        for state in states:
            direction = direction_from_sign(str(state["external_sign"]))
            decisions.append(
                {
                    "sequence": len(decisions) + 1,
                    "variant": selected_variant,
                    "decision_epoch": int(state["decision_epoch"]),
                    "decision_utc": state["decision_utc"],
                    "valid_until_epoch": int(state["decision_epoch"]) + 59,
                    "symbol": TARGET_SYMBOL,
                    "direction": "LONG" if direction > 0 else "SHORT",
                    "risk_distance": state["US100_risk_distance"],
                    "external_sign": state["external_sign"],
                }
            )
    states_bytes = dataframe_csv_bytes(pd.DataFrame(states))
    trades_bytes = dataframe_csv_bytes(pd.DataFrame(trades))
    decisions_bytes = (
        dataframe_csv_bytes(pd.DataFrame(decisions)) if decisions else b""
    )
    result = {
        "schema": "zeta-next-independent-leveraged-etf-close-rebalance-pressure-adapter-challenge-v1-confirmation-result",
        "recorded_at_utc": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "status": (
            "VALID_WHOLE_PROXY_PASS_NATIVE_ESCALATION_READY"
            if metrics["gates"]["passed"]
            else "VALID_WHOLE_PROXY_NONCONFIRMATION"
        ),
        "family": FAMILY,
        "selected_variant": selected_variant,
        "development_result_sha256": sha256(paths.durable_development_result),
        "development_improvement_audit_sha256": sha256(paths.durable_development_audit),
        "authorities": authorities,
        "structure": structure,
        "metrics": metrics,
        "native_decision_tape_written": bool(decisions),
        "raw_outputs": {
            "states": output_receipt(
                paths.raw_confirmation_states, states_bytes, len(states), paths.workspace
            ),
            "trades": output_receipt(
                paths.raw_confirmation_trades, trades_bytes, len(trades), paths.workspace
            ),
            "native_decisions": (
                output_receipt(
                    paths.raw_native_decisions,
                    decisions_bytes,
                    len(decisions),
                    paths.workspace,
                )
                if decisions
                else {"rows": 0, "bytes": 0, "sha256": None}
            ),
        },
        "broker_account_position_order_or_deal_queries": 0,
        "proxy_victory_claimed": False,
    }
    outputs = [
        (paths.raw_confirmation_states, states_bytes),
        (paths.raw_confirmation_trades, trades_bytes),
        (paths.raw_confirmation_result, json_bytes(result)),
    ]
    if decisions:
        outputs.append((paths.raw_native_decisions, decisions_bytes))
    atomic_write_outputs(outputs)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False), flush=True)
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
