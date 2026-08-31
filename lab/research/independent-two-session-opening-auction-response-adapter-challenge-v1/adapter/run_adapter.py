from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


FAMILY_NAME = "independent-two-session-opening-auction-response-adapter-challenge-v1"
FAMILY_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = FAMILY_ROOT / "config" / "challenge-contract.json"
DECLARATION_PATH = (
    FAMILY_ROOT
    / "evidence"
    / "INDEPENDENT_TWO_SESSION_OPENING_AUCTION_RESPONSE_ADAPTER_CHALLENGE_V1_DECLARATION.json"
)
IMPLEMENTATION_FREEZE_PATH = (
    FAMILY_ROOT
    / "evidence"
    / "INDEPENDENT_TWO_SESSION_OPENING_AUCTION_RESPONSE_ADAPTER_CHALLENGE_V1_IMPLEMENTATION_FREEZE.json"
)
DEVELOPMENT_AUTHORIZATION_PATH = (
    FAMILY_ROOT
    / "evidence"
    / "INDEPENDENT_TWO_SESSION_OPENING_AUCTION_RESPONSE_ADAPTER_CHALLENGE_V1_DEVELOPMENT_AUTHORIZATION.json"
)
ARTIFACT_ROOT = PROJECT_ROOT / "lab" / "artifacts" / FAMILY_NAME
INPUT_ROOT = FAMILY_ROOT / "data" / "input"
SOURCE_PATH = Path(__file__).resolve()

EXPECTED_AUTHORITIES = {
    "contract": {
        "path": CONTRACT_PATH,
        "bytes": 14180,
        "sha256": "FE988AA12CF91979AA5FEBBC7B1E8ADEA3F11CA54104C673F4250DF25551F5D5",
    },
    "declaration": {
        "path": DECLARATION_PATH,
        "bytes": 8144,
        "sha256": "540EE1A718B5281DF5D60838A98DEC6EFEF187448BFCA4DC7644465B448DE701",
    },
    "US30_M1": {
        "path": INPUT_ROOT / "US30_M1.parquet",
        "bytes": 19018323,
        "sha256": "8CD68BC54A736BF49CC020ED7CF41C62BBA5305FA7C1453603EF65173F83B063",
    },
    "US100_M1": {
        "path": INPUT_ROOT / "US100_M1.parquet",
        "bytes": 21213599,
        "sha256": "634A8545D83C7A520E81A07E273255BD3FA771AA0EC29381D04E6D25A64C6BB2",
    },
}

SYMBOL_ORDER = ("US100", "US30")
ROLE_ORDER = ("OPEN_DRIVE_5M", "OPEN_FADE_5M")
SESSION_SPECS = (
    ("LONDON_0800", "Europe/London", time(8, 0)),
    ("NEW_YORK_0930", "America/New_York", time(9, 30)),
)
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

POINT = 0.01
TICK_SIZE = 0.01
TICK_VALUE_PER_LOT = 0.01
DOLLARS_PER_PRICE_POINT_PER_LOT = TICK_VALUE_PER_LOT / TICK_SIZE
VOLUME_MIN = 0.01
VOLUME_STEP = 0.01
VOLUME_MAX = 200.0
TARGET_POSITION_RISK_FRACTION = 0.02
HARD_POSITION_RISK_FRACTION = 0.04
HARD_AGGREGATE_RISK_FRACTION = 0.08
INITIAL_BALANCE_USD = 100.0
TAKE_MULTIPLE = 1.5
HOLD_BARS = 60
EPSILON = 1e-12

STRUCTURAL_START = date(2022, 7, 1)
DEVELOPMENT_START = date(2024, 1, 1)
LOCKED_START = date(2026, 1, 1)
LOCKED_END = date(2026, 8, 1)
STRUCTURAL_START_EPOCH = int(
    datetime.combine(STRUCTURAL_START, time(0), timezone.utc).timestamp()
)
LOCKED_START_EPOCH = int(datetime.combine(LOCKED_START, time(0), timezone.utc).timestamp())
LOCKED_END_EPOCH = int(datetime.combine(LOCKED_END, time(0), timezone.utc).timestamp())

DEVELOPMENT_ACTUAL_GATE_USD = 149.97
DEVELOPMENT_STRESSED_GATE_USD = 127.786
WHOLE_ACTUAL_GATE_USD = 409.81
WHOLE_STRESSED_GATE_USD = 367.818
DRAWDOWN_GATE_PCT = 37.39
RECOVERY_GATE = 3.295860215
TURNOVER_GATE = 3.0

STATE_FIELDS = (
    "anchor_epoch",
    "anchor_time",
    "date",
    "session",
    "symbol",
    "opening_body_price",
    "opening_range_price",
    "body_sign",
    "drive_direction",
    "fade_direction",
    "entry_epoch",
    "entry_time",
    "entry_bid_open",
    "entry_spread_points",
    "entry_spread_price",
    "minimum_lot_planned_risk_usd",
    "minimum_lot_within_four_percent_at_100_usd",
)

TRADE_FIELDS = (
    "role",
    "sequence",
    "session",
    "symbol",
    "direction",
    "anchor_epoch",
    "anchor_time",
    "entry_epoch",
    "entry_time",
    "exit_epoch",
    "exit_time",
    "opening_body_price",
    "opening_range_price",
    "volume_lots",
    "planned_risk_usd",
    "entry_bid",
    "entry_ask",
    "exit_bid",
    "exit_ask",
    "observed_spread_burden_price",
    "exit_reason",
    "actual_R",
    "actual_pnl_usd",
    "extra_stress_cost_usd",
    "stressed_pnl_usd",
    "actual_balance_before_usd",
    "actual_balance_after_usd",
    "stressed_balance_before_usd",
    "stressed_balance_after_usd",
)


@dataclass(frozen=True)
class SessionEvent:
    anchor_epoch: int
    anchor_time: str
    local_date: date
    session: str


@dataclass
class RoleBook:
    role: str
    actual_balance: float = INITIAL_BALANCE_USD
    stressed_balance: float = INITIAL_BALANCE_USD
    actual_peak: float = INITIAL_BALANCE_USD
    stressed_peak: float = INITIAL_BALANCE_USD
    actual_drawdown_usd: float = 0.0
    actual_drawdown_pct: float = 0.0
    stressed_drawdown_usd: float = 0.0
    stressed_drawdown_pct: float = 0.0
    minimum_actual_balance: float = INITIAL_BALANCE_USD
    minimum_stressed_balance: float = INITIAL_BALANCE_USD
    starts: int = 0
    signal_blocks: int = 0
    risk_blocks: int = 0
    aggregate_risk_blocks: int = 0
    capacity_blocks: int = 0
    symbol_starts: Counter[str] = field(default_factory=Counter)
    session_starts: Counter[str] = field(default_factory=Counter)
    exit_reasons: Counter[str] = field(default_factory=Counter)
    yearly: dict[int, dict[str, float | int]] = field(
        default_factory=lambda: defaultdict(
            lambda: {"starts": 0, "actual_net_usd": 0.0, "stressed_net_usd": 0.0}
        )
    )
    last_exit_epoch: int | None = None

    def settle(self, trade: dict[str, Any]) -> None:
        actual_before = self.actual_balance
        stressed_before = self.stressed_balance
        self.actual_balance += float(trade["actual_pnl_usd"])
        self.stressed_balance += float(trade["stressed_pnl_usd"])
        self.actual_peak = max(self.actual_peak, self.actual_balance)
        self.stressed_peak = max(self.stressed_peak, self.stressed_balance)
        actual_dd = self.actual_peak - self.actual_balance
        stressed_dd = self.stressed_peak - self.stressed_balance
        actual_dd_pct = actual_dd / self.actual_peak * 100.0 if self.actual_peak > 0 else math.inf
        stressed_dd_pct = (
            stressed_dd / self.stressed_peak * 100.0 if self.stressed_peak > 0 else math.inf
        )
        self.actual_drawdown_usd = max(self.actual_drawdown_usd, actual_dd)
        self.stressed_drawdown_usd = max(self.stressed_drawdown_usd, stressed_dd)
        self.actual_drawdown_pct = max(self.actual_drawdown_pct, actual_dd_pct)
        self.stressed_drawdown_pct = max(self.stressed_drawdown_pct, stressed_dd_pct)
        self.minimum_actual_balance = min(self.minimum_actual_balance, self.actual_balance)
        self.minimum_stressed_balance = min(self.minimum_stressed_balance, self.stressed_balance)
        self.starts += 1
        self.symbol_starts[str(trade["symbol"])] += 1
        self.session_starts[str(trade["session"])] += 1
        self.exit_reasons[str(trade["exit_reason"])] += 1
        year = datetime.fromtimestamp(int(trade["entry_epoch"]), timezone.utc).year
        year_record = self.yearly[year]
        year_record["starts"] = int(year_record["starts"]) + 1
        year_record["actual_net_usd"] = float(year_record["actual_net_usd"]) + float(
            trade["actual_pnl_usd"]
        )
        year_record["stressed_net_usd"] = float(year_record["stressed_net_usd"]) + float(
            trade["stressed_pnl_usd"]
        )
        self.last_exit_epoch = max(self.last_exit_epoch or 0, int(trade["exit_epoch"]))
        trade["actual_balance_before_usd"] = actual_before
        trade["actual_balance_after_usd"] = self.actual_balance
        trade["stressed_balance_before_usd"] = stressed_before
        trade["stressed_balance_after_usd"] = self.stressed_balance


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def line_count(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def relative_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def file_record(path: Path, reported_path: Path | None = None) -> dict[str, Any]:
    item = path.stat()
    record: dict[str, Any] = {
        "path": relative_path(reported_path or path),
        "bytes": item.st_size,
        "sha256": sha256_file(path),
    }
    if path.suffix.lower() in {".json", ".csv", ".md", ".py"}:
        record["lines"] = line_count(path)
    return record


def verify_file(path: Path, expected_bytes: int, expected_sha256: str) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing required authority: {path}")
    actual_bytes = path.stat().st_size
    actual_sha256 = sha256_file(path)
    if actual_bytes != expected_bytes or actual_sha256 != expected_sha256:
        raise RuntimeError(
            f"authority mismatch: {path} expected {expected_bytes}/{expected_sha256} "
            f"got {actual_bytes}/{actual_sha256}"
        )
    return file_record(path)


def verify_static_authorities() -> dict[str, dict[str, Any]]:
    verified: dict[str, dict[str, Any]] = {}
    for name, expected in EXPECTED_AUTHORITIES.items():
        verified[name] = verify_file(
            Path(expected["path"]), int(expected["bytes"]), str(expected["sha256"])
        )
    return verified


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    encoded = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    path.write_text(encoded, encoding="utf-8", newline="\n")


def write_csv(path: Path, fields: Iterable[str], rows: list[dict[str, Any]]) -> None:
    field_list = list(fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=field_list, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def ordered_manifest(records: Iterable[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(
            f"{record['path']}|{record['bytes']}|{record['sha256']}\n".encode("utf-8")
        )
    return digest.hexdigest().upper()


def utc_text(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).replace(tzinfo=None).isoformat()


def require_finite(value: float, label: str) -> float:
    if not math.isfinite(value):
        raise RuntimeError(f"nonfinite {label}: {value}")
    return value


def load_market(maximum_epoch_exclusive: int) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for symbol in SYMBOL_ORDER:
        path = INPUT_ROOT / f"{symbol}_M1.parquet"
        frame = pd.read_parquet(
            path,
            columns=list(REQUIRED_COLUMNS),
            filters=[
                ("time", ">=", STRUCTURAL_START_EPOCH - 1800),
                ("time", "<", maximum_epoch_exclusive),
            ],
        )
        missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
        if missing:
            raise RuntimeError(f"{symbol} missing columns: {missing}")
        frame = frame.loc[
            (frame["time"].astype("int64") >= STRUCTURAL_START_EPOCH - 1800)
            & (frame["time"].astype("int64") < maximum_epoch_exclusive)
        ].copy()
        frame["time"] = frame["time"].astype("int64")
        frame.sort_values("time", inplace=True)
        if frame.empty:
            raise RuntimeError(f"empty market frame: {symbol}")
        if frame["time"].duplicated().any():
            raise RuntimeError(f"duplicate M1 epochs: {symbol}")
        if bool((frame["time"] % 60 != 0).any()):
            raise RuntimeError(f"non-minute epoch: {symbol}")
        numeric = frame[["open", "high", "low", "close", "spread"]].to_numpy(
            dtype=np.float64
        )
        if not np.isfinite(numeric).all():
            raise RuntimeError(f"nonfinite price or spread: {symbol}")
        if bool((frame[["open", "high", "low", "close"]] <= 0).any().any()):
            raise RuntimeError(f"nonpositive OHLC: {symbol}")
        if bool((frame["spread"] < 0).any()):
            raise RuntimeError(f"negative spread: {symbol}")
        if bool(
            (
                frame["high"]
                < frame[["open", "close", "low"]].max(axis=1) - EPSILON
            ).any()
        ):
            raise RuntimeError(f"invalid high: {symbol}")
        if bool(
            (
                frame["low"]
                > frame[["open", "close", "high"]].min(axis=1) + EPSILON
            ).any()
        ):
            raise RuntimeError(f"invalid low: {symbol}")
        frame.set_index("time", inplace=True, drop=False)
        frames[symbol] = frame
    return frames


def session_anchor(local_date: date, zone_name: str, local_time: time) -> int:
    local = datetime.combine(local_date, local_time, ZoneInfo(zone_name))
    return int(local.astimezone(timezone.utc).timestamp())


def complete_session_events(
    frames: dict[str, pd.DataFrame], start: date, end: date
) -> list[SessionEvent]:
    time_sets = {symbol: set(frame.index.astype("int64")) for symbol, frame in frames.items()}
    events: list[SessionEvent] = []
    cursor = start
    while cursor < end:
        for session_name, zone_name, local_time in SESSION_SPECS:
            anchor = session_anchor(cursor, zone_name, local_time)
            required = range(anchor - 30 * 60, anchor + 75 * 60, 60)
            if all(all(epoch in time_sets[symbol] for epoch in required) for symbol in SYMBOL_ORDER):
                events.append(
                    SessionEvent(
                        anchor_epoch=anchor,
                        anchor_time=utc_text(anchor),
                        local_date=cursor,
                        session=session_name,
                    )
                )
        cursor += timedelta(days=1)
    events.sort(key=lambda item: (item.anchor_epoch, item.session))
    return events


def opening_state(frame: pd.DataFrame, event: SessionEvent) -> dict[str, Any]:
    opening_epochs = [event.anchor_epoch + offset * 60 for offset in range(5)]
    opening = frame.loc[opening_epochs]
    body = require_finite(
        float(opening.iloc[-1]["close"] - opening.iloc[0]["open"]), "opening body"
    )
    opening_range = require_finite(
        float(opening["high"].max() - opening["low"].min()), "opening range"
    )
    entry_epoch = event.anchor_epoch + 5 * 60
    entry = frame.loc[entry_epoch]
    spread_points = require_finite(float(entry["spread"]), "entry spread points")
    spread_price = spread_points * POINT
    if body > 0:
        body_sign = 1
        drive = "LONG"
        fade = "SHORT"
    elif body < 0:
        body_sign = -1
        drive = "SHORT"
        fade = "LONG"
    else:
        body_sign = 0
        drive = "NONE"
        fade = "NONE"
    return {
        "body": body,
        "range": opening_range,
        "body_sign": body_sign,
        "drive": drive,
        "fade": fade,
        "entry_epoch": entry_epoch,
        "entry_bid": float(entry["open"]),
        "entry_spread_points": spread_points,
        "entry_spread_price": spread_price,
    }


def state_row(event: SessionEvent, symbol: str, state: dict[str, Any]) -> dict[str, Any]:
    min_lot_risk = float(state["range"]) * VOLUME_MIN * DOLLARS_PER_PRICE_POINT_PER_LOT
    return {
        "anchor_epoch": event.anchor_epoch,
        "anchor_time": event.anchor_time,
        "date": event.local_date.isoformat(),
        "session": event.session,
        "symbol": symbol,
        "opening_body_price": state["body"],
        "opening_range_price": state["range"],
        "body_sign": state["body_sign"],
        "drive_direction": state["drive"],
        "fade_direction": state["fade"],
        "entry_epoch": state["entry_epoch"],
        "entry_time": utc_text(int(state["entry_epoch"])),
        "entry_bid_open": state["entry_bid"],
        "entry_spread_points": state["entry_spread_points"],
        "entry_spread_price": state["entry_spread_price"],
        "minimum_lot_planned_risk_usd": min_lot_risk,
        "minimum_lot_within_four_percent_at_100_usd": min_lot_risk
        <= INITIAL_BALANCE_USD * HARD_POSITION_RISK_FRACTION + EPSILON,
    }


def direction_for_role(role: str, state: dict[str, Any]) -> str:
    if role == "OPEN_DRIVE_5M":
        return str(state["drive"])
    if role == "OPEN_FADE_5M":
        return str(state["fade"])
    raise RuntimeError(f"unknown role: {role}")


def risk_volume(balance: float, distance: float) -> tuple[float | None, float]:
    if not math.isfinite(balance) or balance <= 0 or not math.isfinite(distance) or distance <= 0:
        return None, 0.0
    dollars_per_lot = distance * DOLLARS_PER_PRICE_POINT_PER_LOT
    raw_volume = balance * TARGET_POSITION_RISK_FRACTION / dollars_per_lot
    steps = math.floor((raw_volume + EPSILON) / VOLUME_STEP)
    volume = min(VOLUME_MAX, steps * VOLUME_STEP)
    if volume + EPSILON < VOLUME_MIN:
        volume = VOLUME_MIN
    volume = round(volume, 2)
    planned_risk = distance * volume * DOLLARS_PER_PRICE_POINT_PER_LOT
    if planned_risk > balance * HARD_POSITION_RISK_FRACTION + 1e-9:
        return None, planned_risk
    return volume, planned_risk


def simulate_trade(
    role: str,
    event: SessionEvent,
    symbol: str,
    direction: str,
    state: dict[str, Any],
    frame: pd.DataFrame,
    volume: float,
    planned_risk: float,
) -> dict[str, Any]:
    entry_epoch = int(state["entry_epoch"])
    entry_bid = float(state["entry_bid"])
    entry_ask = entry_bid + float(state["entry_spread_price"])
    distance = float(state["range"])
    path_epochs = [entry_epoch + offset * 60 for offset in range(HOLD_BARS)]
    exit_epoch = path_epochs[-1]
    exit_reason = "TIME_60_M1"
    exit_bid = float(frame.loc[exit_epoch]["close"])
    exit_spread_price = float(frame.loc[exit_epoch]["spread"]) * POINT
    exit_ask = exit_bid + exit_spread_price

    if direction == "LONG":
        stop_bid = entry_ask - distance
        take_bid = entry_ask + TAKE_MULTIPLE * distance
        for epoch in path_epochs:
            row = frame.loc[epoch]
            stop_hit = float(row["low"]) <= stop_bid + EPSILON
            take_hit = float(row["high"]) >= take_bid - EPSILON
            if stop_hit:
                exit_epoch = epoch
                exit_reason = "STOP_ADVERSE_FIRST"
                exit_bid = stop_bid
                exit_spread_price = float(row["spread"]) * POINT
                exit_ask = exit_bid + exit_spread_price
                break
            if take_hit:
                exit_epoch = epoch
                exit_reason = "TAKE"
                exit_bid = take_bid
                exit_spread_price = float(row["spread"]) * POINT
                exit_ask = exit_bid + exit_spread_price
                break
        actual_price_pnl = exit_bid - entry_ask
        observed_spread_burden = float(state["entry_spread_price"])
    elif direction == "SHORT":
        stop_ask = entry_bid + distance
        take_ask = entry_bid - TAKE_MULTIPLE * distance
        for epoch in path_epochs:
            row = frame.loc[epoch]
            row_spread = float(row["spread"]) * POINT
            ask_high = float(row["high"]) + row_spread
            ask_low = float(row["low"]) + row_spread
            stop_hit = ask_high >= stop_ask - EPSILON
            take_hit = ask_low <= take_ask + EPSILON
            if stop_hit:
                exit_epoch = epoch
                exit_reason = "STOP_ADVERSE_FIRST"
                exit_spread_price = row_spread
                exit_ask = stop_ask
                exit_bid = exit_ask - exit_spread_price
                break
            if take_hit:
                exit_epoch = epoch
                exit_reason = "TAKE"
                exit_spread_price = row_spread
                exit_ask = take_ask
                exit_bid = exit_ask - exit_spread_price
                break
        actual_price_pnl = entry_bid - exit_ask
        observed_spread_burden = exit_spread_price
    else:
        raise RuntimeError(f"non-executable direction: {direction}")

    actual_pnl = actual_price_pnl * volume * DOLLARS_PER_PRICE_POINT_PER_LOT
    extra_stress = observed_spread_burden * volume * DOLLARS_PER_PRICE_POINT_PER_LOT
    stressed_pnl = actual_pnl - extra_stress
    actual_r = actual_pnl / planned_risk if planned_risk > 0 else math.nan
    for label, value in {
        "actual pnl": actual_pnl,
        "extra stress": extra_stress,
        "stressed pnl": stressed_pnl,
        "actual R": actual_r,
    }.items():
        require_finite(float(value), label)
    return {
        "role": role,
        "sequence": 0,
        "session": event.session,
        "symbol": symbol,
        "direction": direction,
        "anchor_epoch": event.anchor_epoch,
        "anchor_time": event.anchor_time,
        "entry_epoch": entry_epoch,
        "entry_time": utc_text(entry_epoch),
        "exit_epoch": exit_epoch,
        "exit_time": utc_text(exit_epoch),
        "opening_body_price": state["body"],
        "opening_range_price": distance,
        "volume_lots": volume,
        "planned_risk_usd": planned_risk,
        "entry_bid": entry_bid,
        "entry_ask": entry_ask,
        "exit_bid": exit_bid,
        "exit_ask": exit_ask,
        "observed_spread_burden_price": observed_spread_burden,
        "exit_reason": exit_reason,
        "actual_R": actual_r,
        "actual_pnl_usd": actual_pnl,
        "extra_stress_cost_usd": extra_stress,
        "stressed_pnl_usd": stressed_pnl,
        "actual_balance_before_usd": 0.0,
        "actual_balance_after_usd": 0.0,
        "stressed_balance_before_usd": 0.0,
        "stressed_balance_after_usd": 0.0,
    }


def normal_day_count(events: list[SessionEvent]) -> int:
    return len({event.local_date.isoformat() for event in events})


def simulate_roles(
    frames: dict[str, pd.DataFrame], events: list[SessionEvent], roles: Iterable[str]
) -> tuple[dict[str, RoleBook], list[dict[str, Any]], list[dict[str, Any]]]:
    role_list = list(roles)
    books = {role: RoleBook(role=role) for role in role_list}
    states: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    sequence = Counter()

    for event in events:
        event_states = {
            symbol: opening_state(frames[symbol], event) for symbol in SYMBOL_ORDER
        }
        for symbol in SYMBOL_ORDER:
            states.append(state_row(event, symbol, event_states[symbol]))

        for role in role_list:
            book = books[role]
            entry_epoch = event.anchor_epoch + 5 * 60
            if book.last_exit_epoch is not None and book.last_exit_epoch >= entry_epoch:
                book.capacity_blocks += len(SYMBOL_ORDER)
                continue
            session_balance = book.actual_balance
            planned_batch_risk = 0.0
            pending: list[dict[str, Any]] = []
            for symbol in SYMBOL_ORDER:
                state = event_states[symbol]
                direction = direction_for_role(role, state)
                if direction == "NONE" or float(state["range"]) <= 0:
                    book.signal_blocks += 1
                    continue
                volume, planned_risk = risk_volume(session_balance, float(state["range"]))
                if volume is None:
                    book.risk_blocks += 1
                    continue
                if (
                    planned_batch_risk + planned_risk
                    > session_balance * HARD_AGGREGATE_RISK_FRACTION + 1e-9
                ):
                    book.aggregate_risk_blocks += 1
                    continue
                planned_batch_risk += planned_risk
                pending.append(
                    simulate_trade(
                        role,
                        event,
                        symbol,
                        direction,
                        state,
                        frames[symbol],
                        volume,
                        planned_risk,
                    )
                )
            pending.sort(
                key=lambda trade: (
                    int(trade["exit_epoch"]),
                    SYMBOL_ORDER.index(str(trade["symbol"])),
                )
            )
            for trade in pending:
                sequence[role] += 1
                trade["sequence"] = sequence[role]
                book.settle(trade)
                trades.append(trade)

    trades.sort(key=lambda trade: (ROLE_ORDER.index(str(trade["role"])), int(trade["sequence"])))
    return books, states, trades


def role_metrics(book: RoleBook, normal_days: int, years: Iterable[int]) -> dict[str, Any]:
    actual_net = book.actual_balance - INITIAL_BALANCE_USD
    stressed_net = book.stressed_balance - INITIAL_BALANCE_USD
    recovery = (
        stressed_net / book.actual_drawdown_usd if book.actual_drawdown_usd > 0 else None
    )
    yearly: dict[str, Any] = {}
    for year in years:
        record = book.yearly.get(
            year, {"starts": 0, "actual_net_usd": 0.0, "stressed_net_usd": 0.0}
        )
        yearly[str(year)] = {
            "starts": int(record["starts"]),
            "actual_net_usd": float(record["actual_net_usd"]),
            "stressed_net_usd": float(record["stressed_net_usd"]),
        }
    return {
        "starts": book.starts,
        "normal_trading_days": normal_days,
        "average_starts_per_normal_trading_day": book.starts / normal_days if normal_days else 0.0,
        "actual_net_usd": actual_net,
        "stressed_net_usd": stressed_net,
        "actual_ending_balance_usd": book.actual_balance,
        "stressed_ending_balance_usd": book.stressed_balance,
        "actual_closed_balance_drawdown_usd": book.actual_drawdown_usd,
        "actual_closed_balance_drawdown_pct": book.actual_drawdown_pct,
        "stressed_closed_balance_drawdown_usd": book.stressed_drawdown_usd,
        "stressed_closed_balance_drawdown_pct": book.stressed_drawdown_pct,
        "minimum_actual_balance_usd": book.minimum_actual_balance,
        "minimum_stressed_balance_usd": book.minimum_stressed_balance,
        "robust_recovery_proxy": recovery,
        "symbol_breadth": sum(book.symbol_starts[symbol] > 0 for symbol in SYMBOL_ORDER),
        "session_breadth": sum(
            book.session_starts[session[0]] > 0 for session in SESSION_SPECS
        ),
        "years": yearly,
        "symbols": {
            symbol: {"starts": book.symbol_starts[symbol]} for symbol in SYMBOL_ORDER
        },
        "sessions": {
            session[0]: {"starts": book.session_starts[session[0]]}
            for session in SESSION_SPECS
        },
        "exit_reasons": dict(sorted(book.exit_reasons.items())),
        "signal_blocks": book.signal_blocks,
        "risk_blocks": book.risk_blocks,
        "aggregate_risk_blocks": book.aggregate_risk_blocks,
        "capacity_blocks": book.capacity_blocks,
        "final_actual_balance_crosscheck": book.actual_balance,
        "final_stressed_balance_crosscheck": book.stressed_balance,
    }


def development_role_result(book: RoleBook, normal_days: int) -> dict[str, Any]:
    metrics = role_metrics(book, normal_days, (2024, 2025))
    gates = {
        "both_2024_and_2025_actual_positive": all(
            float(metrics["years"][str(year)]["actual_net_usd"]) > 0 for year in (2024, 2025)
        ),
        "both_2024_and_2025_stressed_positive": all(
            float(metrics["years"][str(year)]["stressed_net_usd"]) > 0 for year in (2024, 2025)
        ),
        "development_actual_net_strictly_above_v8": float(metrics["actual_net_usd"])
        > DEVELOPMENT_ACTUAL_GATE_USD,
        "development_stressed_net_strictly_above_v8": float(metrics["stressed_net_usd"])
        > DEVELOPMENT_STRESSED_GATE_USD,
        "actual_closed_balance_drawdown_pct_max": float(
            metrics["actual_closed_balance_drawdown_pct"]
        )
        <= DRAWDOWN_GATE_PCT,
        "normal_trading_day_average_lifecycle_starts_min": float(
            metrics["average_starts_per_normal_trading_day"]
        )
        >= TURNOVER_GATE,
        "symbol_breadth_min": int(metrics["symbol_breadth"]) >= 2,
        "session_breadth_min": int(metrics["session_breadth"]) >= 2,
    }
    return {"metrics": metrics, "gates": gates, "complete_pass": all(gates.values())}


def whole_role_result(book: RoleBook, normal_days: int) -> dict[str, Any]:
    metrics = role_metrics(book, normal_days, (2024, 2025, 2026))
    locked_actual = float(metrics["years"]["2026"]["actual_net_usd"])
    locked_stressed = float(metrics["years"]["2026"]["stressed_net_usd"])
    gates = {
        "each_epoch_actual_positive": all(
            float(metrics["years"][str(year)]["actual_net_usd"]) > 0
            for year in (2024, 2025, 2026)
        ),
        "each_epoch_stressed_positive": all(
            float(metrics["years"][str(year)]["stressed_net_usd"]) > 0
            for year in (2024, 2025, 2026)
        ),
        "locked_2026_actual_positive": locked_actual > 0,
        "locked_2026_stressed_positive": locked_stressed > 0,
        "whole_actual_net_strictly_above_v8": float(metrics["actual_net_usd"])
        > WHOLE_ACTUAL_GATE_USD,
        "whole_stressed_net_strictly_above_v8": float(metrics["stressed_net_usd"])
        > WHOLE_STRESSED_GATE_USD,
        "whole_closed_balance_drawdown_pct_max": float(
            metrics["actual_closed_balance_drawdown_pct"]
        )
        <= DRAWDOWN_GATE_PCT,
        "whole_robust_recovery_strictly_above": metrics["robust_recovery_proxy"] is not None
        and float(metrics["robust_recovery_proxy"]) > RECOVERY_GATE,
        "normal_trading_day_average_lifecycle_starts_min": float(
            metrics["average_starts_per_normal_trading_day"]
        )
        >= TURNOVER_GATE,
        "symbol_breadth_min": int(metrics["symbol_breadth"]) >= 2,
        "session_breadth_min": int(metrics["session_breadth"]) >= 2,
    }
    return {"metrics": metrics, "gates": gates, "complete_pass": all(gates.values())}


def structural_summary(
    frames: dict[str, pd.DataFrame], events: list[SessionEvent]
) -> dict[str, Any]:
    session_counts = Counter(event.session for event in events)
    dates = defaultdict(set)
    direction_counts: dict[str, Counter[str]] = {
        symbol: Counter() for symbol in SYMBOL_ORDER
    }
    ranges: dict[str, list[float]] = {symbol: [] for symbol in SYMBOL_ORDER}
    feasible = Counter()
    state_count = 0
    for event in events:
        dates[event.local_date.isoformat()].add(event.session)
        for symbol in SYMBOL_ORDER:
            state = opening_state(frames[symbol], event)
            state_count += 1
            direction_counts[symbol][str(state["drive"])] += 1
            if float(state["range"]) > 0:
                ranges[symbol].append(float(state["range"]))
                min_risk = float(state["range"]) * VOLUME_MIN
                if min_risk <= INITIAL_BALANCE_USD * HARD_POSITION_RISK_FRACTION + EPSILON:
                    feasible[symbol] += 1
    range_summary: dict[str, Any] = {}
    for symbol in SYMBOL_ORDER:
        values = np.asarray(ranges[symbol], dtype=np.float64)
        range_summary[symbol] = {
            "positive_ranges": int(values.size),
            "minimum": float(np.min(values)) if values.size else None,
            "median": float(np.median(values)) if values.size else None,
            "p90": float(np.quantile(values, 0.9)) if values.size else None,
            "maximum": float(np.max(values)) if values.size else None,
        }
    distribution = Counter(len(value) for value in dates.values())
    return {
        "session_events": len(events),
        "two_symbol_state_rows": state_count,
        "active_dates": len(dates),
        "events_by_session": dict(sorted(session_counts.items())),
        "dates_by_complete_session_count": {
            str(key): value for key, value in sorted(distribution.items())
        },
        "average_two_symbol_opportunities_per_active_date": state_count / len(dates)
        if dates
        else 0.0,
        "drive_direction_counts": {
            symbol: dict(sorted(direction_counts[symbol].items())) for symbol in SYMBOL_ORDER
        },
        "opening_range_summary": range_summary,
        "minimum_lot_risk_feasible_at_100_usd": {
            symbol: feasible[symbol] for symbol in SYMBOL_ORDER
        },
    }


def verify_implementation_freeze(authorities: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not IMPLEMENTATION_FREEZE_PATH.is_file():
        raise RuntimeError("implementation freeze is absent")
    freeze = load_json(IMPLEMENTATION_FREEZE_PATH)
    if freeze.get("status") != "IMPLEMENTATION_FROZEN_PREDEVELOPMENT_OUTCOME":
        raise RuntimeError("implementation freeze status does not authorize development")
    frozen_authorities = freeze.get("authorities")
    if not isinstance(frozen_authorities, dict):
        raise RuntimeError("implementation freeze authorities missing")
    for key in ("contract", "declaration", "adapter"):
        record = frozen_authorities.get(key)
        if not isinstance(record, dict):
            raise RuntimeError(f"implementation freeze missing {key}")
        if key == "adapter":
            actual = file_record(SOURCE_PATH)
        else:
            actual = authorities[key]
        if int(record.get("bytes", -1)) != int(actual["bytes"]) or str(
            record.get("sha256")
        ) != str(actual["sha256"]):
            raise RuntimeError(f"implementation freeze {key} mismatch")
    return file_record(IMPLEMENTATION_FREEZE_PATH)


def atomic_output_directory(name: str) -> tuple[Path, Path]:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    final = ARTIFACT_ROOT / name
    if final.exists():
        raise RuntimeError(f"artifact destination already exists: {final}")
    temporary = Path(tempfile.mkdtemp(prefix=f".{name}-", dir=ARTIFACT_ROOT))
    return temporary, final


def finalize_output(temporary: Path, final: Path) -> None:
    if final.exists():
        raise RuntimeError(f"refusing overwrite: {final}")
    temporary.replace(final)


def authority_result(authorities: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result = {
        "contract": authorities["contract"],
        "declaration": authorities["declaration"],
        "adapter": file_record(SOURCE_PATH),
        "US100_M1": authorities["US100_M1"],
        "US30_M1": authorities["US30_M1"],
    }
    return result


def run_precheck() -> dict[str, Any]:
    authorities = verify_static_authorities()
    frames = load_market(LOCKED_START_EPOCH)
    structural_events = complete_session_events(
        frames, STRUCTURAL_START, DEVELOPMENT_START
    )
    development_events = complete_session_events(frames, DEVELOPMENT_START, LOCKED_START)
    return {
        "schema": "zeta-next-independent-two-session-opening-auction-response-adapter-challenge-v1-precheck",
        "status": "STRUCTURAL_PRECHECK_PASS_PREDEVELOPMENT_OUTCOME",
        "authorities": authority_result(authorities),
        "loaded_maximum_epoch_exclusive": LOCKED_START_EPOCH,
        "locked_2026_price_rows_loaded": 0,
        "structural_history": structural_summary(frames, structural_events),
        "development": structural_summary(frames, development_events),
        "attestation": {
            "future_trade_paths_evaluated": 0,
            "candidate_lifecycles": 0,
            "candidate_economic_metrics": 0,
            "persistent_output_files": 0,
            "ea_source_files": 0,
            "mt5_paths": 0,
            "live_changed": False,
        },
        "next_authorized_action": "write and commit the implementation freeze before one development process",
    }


def run_development() -> dict[str, Any]:
    authorities = verify_static_authorities()
    authorities["adapter"] = file_record(SOURCE_PATH)
    freeze_record = verify_implementation_freeze(authorities)
    frames = load_market(LOCKED_START_EPOCH)
    events = complete_session_events(frames, DEVELOPMENT_START, LOCKED_START)
    books, state_rows, trade_rows = simulate_roles(frames, events, ROLE_ORDER)
    normal_days = normal_day_count(events)
    role_results = {
        role: development_role_result(books[role], normal_days) for role in ROLE_ORDER
    }
    passers = [role for role in ROLE_ORDER if role_results[role]["complete_pass"]]
    passers.sort(
        key=lambda role: (
            -float(role_results[role]["metrics"]["stressed_net_usd"]),
            float(role_results[role]["metrics"]["actual_closed_balance_drawdown_pct"]),
            -min(
                float(role_results[role]["metrics"]["years"][str(year)]["stressed_net_usd"])
                for year in (2024, 2025)
            ),
            ROLE_ORDER.index(role),
        )
    )
    selected_role = passers[0] if passers else None
    temporary, final = atomic_output_directory("development")
    try:
        state_path = temporary / "session-state-tape.csv"
        trade_path = temporary / "trade-tape.csv"
        write_csv(state_path, STATE_FIELDS, state_rows)
        write_csv(trade_path, TRADE_FIELDS, trade_rows)
        state_record = file_record(state_path, final / state_path.name)
        trade_record = file_record(trade_path, final / trade_path.name)
        raw_records = [state_record, trade_record]
        result = {
            "schema": "zeta-next-independent-two-session-opening-auction-response-adapter-challenge-v1-development-result",
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": (
                "VALID_DEVELOPMENT_COMPLETE_PASSER_SELECTED_CONFIRMATION_NOT_YET_AUTHORIZED"
                if selected_role
                else "VALID_DEVELOPMENT_NO_COMPLETE_ROLE_FAMILY_CLOSE_BEFORE_CONFIRMATION_EA_MT5"
            ),
            "authorities": {
                **authority_result(authorities),
                "implementation_freeze": freeze_record,
            },
            "process": {
                "development_period": "2024-01-01T00:00:00/2026-01-01T00:00:00",
                "complete_session_events": len(events),
                "two_symbol_state_rows": len(state_rows),
                "normal_trading_days": normal_days,
                "trade_rows": len(trade_rows),
                "initial_deposit_usd": INITIAL_BALANCE_USD,
            },
            "development": {
                "roles": role_results,
                "complete_passer_count": len(passers),
                "complete_passers_ranked": passers,
                "selected_role": selected_role,
            },
            "raw_evidence": {
                "session_state_tape": state_record,
                "trade_tape": trade_record,
                "ordered_two_tape_manifest_sha256": ordered_manifest(raw_records),
                "two_tape_bytes": sum(int(record["bytes"]) for record in raw_records),
            },
            "attestation": {
                "one_complete_development_process": True,
                "economic_rerun_count": 0,
                "locked_confirmation_rows_used": 0,
                "candidate_ea_source_files": 0,
                "candidate_mt5_paths": 0,
                "native_v8_victory_claimed": False,
                "live_changed": False,
            },
            "next_authorized_action": (
                "write and commit one durable development authority selecting the unchanged role before locked confirmation"
                if selected_role
                else "write the durable adverse result and family closure; do not open locked confirmation, EA or MT5"
            ),
        }
        result_path = temporary / "result.json"
        write_json(result_path, result)
        finalize_output(temporary, final)
        return result
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def verify_development_authorization() -> tuple[str, dict[str, Any]]:
    if not DEVELOPMENT_AUTHORIZATION_PATH.is_file():
        raise RuntimeError("development authorization is absent")
    authority = load_json(DEVELOPMENT_AUTHORIZATION_PATH)
    if (
        authority.get("status")
        != "VALID_DEVELOPMENT_COMPLETE_PASSER_SELECTED_CONFIRMATION_AUTHORIZED"
    ):
        raise RuntimeError("development authorization status does not permit confirmation")
    selected_role = authority.get("selected_role")
    if selected_role not in ROLE_ORDER:
        raise RuntimeError("invalid selected role in development authorization")
    return str(selected_role), authority


def run_confirmation() -> dict[str, Any]:
    authorities = verify_static_authorities()
    authorities["adapter"] = file_record(SOURCE_PATH)
    freeze_record = verify_implementation_freeze(authorities)
    selected_role, development_authority = verify_development_authorization()
    frames = load_market(LOCKED_END_EPOCH)
    events = complete_session_events(frames, DEVELOPMENT_START, LOCKED_END)
    books, state_rows, trade_rows = simulate_roles(frames, events, (selected_role,))
    normal_days = normal_day_count(events)
    role_result = whole_role_result(books[selected_role], normal_days)
    temporary, final = atomic_output_directory("confirmation")
    try:
        state_path = temporary / "session-state-tape.csv"
        trade_path = temporary / "trade-tape.csv"
        write_csv(state_path, STATE_FIELDS, state_rows)
        write_csv(trade_path, TRADE_FIELDS, trade_rows)
        state_record = file_record(state_path, final / state_path.name)
        trade_record = file_record(trade_path, final / trade_path.name)
        raw_records = [state_record, trade_record]
        result = {
            "schema": "zeta-next-independent-two-session-opening-auction-response-adapter-challenge-v1-confirmation-result",
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": (
                "VALID_WHOLE_PROXY_COMPLETE_PASS_NATIVE_EA_MT5_AUTHORITY_REQUIRED"
                if role_result["complete_pass"]
                else "VALID_CONFIRMATION_OR_WHOLE_PROXY_NONCONFIRMATION_CLOSE_BEFORE_EA_MT5"
            ),
            "authorities": {
                **authority_result(authorities),
                "implementation_freeze": freeze_record,
                "development_authorization": file_record(DEVELOPMENT_AUTHORIZATION_PATH),
            },
            "selected_role": selected_role,
            "development_authority_status": development_authority["status"],
            "whole_period": "2024-01-01T00:00:00/2026-08-01T00:00:00",
            "whole": role_result,
            "raw_evidence": {
                "session_state_tape": state_record,
                "trade_tape": trade_record,
                "ordered_two_tape_manifest_sha256": ordered_manifest(raw_records),
                "two_tape_bytes": sum(int(record["bytes"]) for record in raw_records),
            },
            "attestation": {
                "unchanged_selected_role_only": True,
                "candidate_ea_source_files": 0,
                "candidate_mt5_paths": 0,
                "native_v8_victory_claimed": False,
                "live_changed": False,
            },
            "next_authorized_action": (
                "write a durable whole-proxy authority before implementing the self-contained Python adapter plus EA native candidate"
                if role_result["complete_pass"]
                else "write the durable nonconfirmation and close before EA or MT5"
            ),
        }
        result_path = temporary / "result.json"
        write_json(result_path, result)
        finalize_output(temporary, final)
        return result
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=("precheck", "development", "confirmation"), required=True
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.mode == "precheck":
        result = run_precheck()
    elif args.mode == "development":
        result = run_development()
    else:
        result = run_confirmation()
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
