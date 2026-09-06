"""Frozen Family 011 causal direction/management adapter and development proxy.

No broker, account, network, other-family code, model fitting or native authority.
The ordinary run emits the common intent population and complete account paths.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd


FAMILY = Path(__file__).resolve().parents[1]
WORKSPACE = FAMILY.parents[2]
CONTRACT_PATH = FAMILY / "config/contract.json"
DECLARATION_PATH = FAMILY / "evidence/DECLARATION_V2_BINDING.json"
RESULT_ROOT = WORKSPACE / "lab/artifacts/raw" / FAMILY.name / "development-final"
H4 = 14400


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest().upper()


def wall_epoch(label: str) -> int:
    # UTC only encodes the supplied wall-clock digits, never a broker conversion.
    return int(pd.Timestamp(label).tz_localize("UTC").timestamp())


def wall_label(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).replace(tzinfo=None).isoformat()


def day_label(epoch: int) -> str:
    return wall_label(epoch)[:10]


def authority(path: Path) -> dict:
    return {
        "path": path.relative_to(WORKSPACE).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    }


def load_sources(contract: dict, declaration: dict) -> tuple[dict, dict, dict]:
    frames, specs, receipt = {}, {}, {}
    start = wall_epoch(contract["warmup"].split(" through ")[0])
    end = wall_epoch(contract["development"][1])
    for record in declaration["input_copies"]:
        path = (WORKSPACE / record["path"]).resolve()
        own_input = (WORKSPACE / "lab/artifacts/raw" / FAMILY.name / "input").resolve()
        if not path.is_relative_to(own_input):
            raise RuntimeError("source path is not an own-family physical input")
        if path.stat().st_size != record["bytes"] or digest(path) != record["sha256"]:
            raise RuntimeError(f"input authority mismatch: {path.name}")
        symbol = record["symbol"]
        if record["kind"] == "spec":
            spec = json.loads(path.read_text(encoding="utf-8-sig"))
            if spec["currency_profit"] != "USD":
                raise RuntimeError(f"unsupported profit currency: {symbol}")
            unit = spec["trade_tick_value_loss"] / spec["trade_tick_size"]
            if not math.isclose(unit, spec["trade_contract_size"], rel_tol=1e-9):
                raise RuntimeError(f"money conversion mismatch: {symbol}")
            if not math.isclose(spec["trade_tick_value_loss"], spec["trade_tick_value_profit"]):
                raise RuntimeError(f"asymmetric tick values require explicit handling: {symbol}")
            if spec["swap_mode"] not in (0, 1, 2):
                raise RuntimeError(f"unsupported numeric swap mode: {symbol}")
            if spec["swap_mode"] == 2 and spec["currency_base"] != "USD":
                raise RuntimeError(f"swap requires a currency conversion: {symbol}")
            specs[symbol] = spec
            continue
        frame = pd.read_csv(path, usecols=["time", "open", "high", "low", "close", "spread"])
        frame = frame.loc[(frame["time"] >= start) & (frame["time"] < end)].copy()
        frame = frame.reset_index(drop=True)
        frame["time"] = frame["time"].astype("int64")
        if frame.empty or not frame["time"].is_unique or not frame["time"].is_monotonic_increasing:
            raise RuntimeError(f"empty/duplicate/unordered source: {symbol}")
        if (frame["time"] % H4 != 0).any():
            raise RuntimeError("off-grid H4 data cannot use this batch chronology")
        values = frame[["open", "high", "low", "close", "spread"]].to_numpy(dtype=float)
        if not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4] < 0).any():
            raise RuntimeError(f"invalid source values: {symbol}")
        if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
            raise RuntimeError(f"high geometry: {symbol}")
        if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
            raise RuntimeError(f"low geometry: {symbol}")
        prior = frame["close"].shift(1)
        true_range = pd.concat(
            [frame["high"] - frame["low"], (frame["high"] - prior).abs(), (frame["low"] - prior).abs()],
            axis=1,
        ).max(axis=1)
        frame["entry_atr"] = true_range.rolling(contract["atr_bars"], min_periods=contract["atr_bars"]).mean().shift(1)
        frames[symbol] = frame.to_dict("records")
        receipt[symbol] = {
            "warmup_and_development_rows_used": len(frame),
            "first_server_wall": wall_label(int(frame["time"].iloc[0])),
            "last_server_wall": wall_label(int(frame["time"].iloc[-1])),
            "h4_grid_remainders": [0],
        }
    if set(frames) != set(contract["symbols"]) or set(specs) != set(frames):
        raise RuntimeError("incomplete universe")
    return frames, specs, receipt


def flow_direction(symbol: str, epoch: int) -> int:
    text = f"ZT-CH011-FLOW-V1|{symbol}|{epoch}"
    return 1 if hashlib.sha256(text.encode("ascii")).digest()[0] & 1 else -1


def priority(symbol: str, epoch: int) -> bytes:
    return hashlib.sha256(f"ZT-CH011-PRIORITY-V1|{epoch}|{symbol}".encode("ascii")).digest()


def money(price_distance: float, lots: float, spec: dict) -> float:
    return price_distance * spec["trade_contract_size"] * lots


def liquidation(mark: dict, direction: int, column: str, spec: dict) -> float:
    return float(mark[column]) + (float(mark["spread"]) * spec["point"] if direction < 0 else 0.0)


def swap_cost(position: dict, exit_epoch: int, spec: dict) -> tuple[float, int]:
    if exit_epoch < position["entry_epoch"]:
        raise RuntimeError("swap time goes backwards")
    entry = datetime.fromtimestamp(position["entry_epoch"], timezone.utc)
    end = datetime.fromtimestamp(exit_epoch, timezone.utc)
    boundary = entry.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    units = 0
    while boundary <= end:
        ending_day = boundary - timedelta(days=1)
        if ending_day.weekday() < 5:
            mql_day = (ending_day.weekday() + 1) % 7
            units += 3 if mql_day == int(spec["swap_rollover3days"]) else 1
        boundary += timedelta(days=1)
    rate = float(spec["swap_long"] if position["direction"] > 0 else spec["swap_short"])
    mode = int(spec["swap_mode"])
    if mode == 0:
        return 0.0, units
    if mode == 1:
        return money(rate * spec["point"], position["lots"], spec) * units, units
    if mode == 2 and spec["currency_base"] == "USD":
        return rate * position["lots"] * units, units
    raise RuntimeError("unhandled swap mode")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def simulate(role: str, contract: dict, frames: dict, specs: dict) -> dict:
    start, end = map(wall_epoch, contract["development"])
    cutoff = end - contract["new_entry_cutoff_calendar_days_before_period_end"] * 86400
    batches = defaultdict(dict)
    for symbol, rows in frames.items():
        for index, row in enumerate(rows):
            epoch = int(row["time"])
            if start <= epoch < end:
                batches[epoch][symbol] = (index, row)
    normal_dates = sorted({day_label(epoch) for epoch in batches})
    balance = stressed = mid_stressed = float(contract["risk"]["initial_deposit_usd"])
    positions, latest = {}, {}
    intents, trades, marks = [], [], []
    peak = balance
    max_dd_money = max_dd_pct = 0.0
    trade_counter = 0

    def close_position(symbol: str, epoch: int, price: float, spread: float, reason: str) -> None:
        nonlocal balance, stressed, mid_stressed
        position = positions.pop(symbol)
        spec = specs[symbol]
        price_pnl = money(position["direction"] * (price - position["entry_price"]), position["lots"], spec)
        swap, swap_units = swap_cost(position, epoch, spec)
        primary_spread = position["entry_spread"] if position["direction"] > 0 else spread
        burden = money(primary_spread, position["lots"], spec)
        mid_burden = money((position["entry_spread"] + spread) / 2.0, position["lots"], spec)
        actual_pnl = price_pnl + swap
        stress_pnl, mid_pnl = actual_pnl - burden, actual_pnl - mid_burden
        record = {
            "role": role, "trade_id": position["trade_id"], "symbol": symbol,
            "direction": position["direction"], "entry_server_wall": wall_label(position["entry_epoch"]),
            "exit_server_wall": wall_label(epoch), "entry_year": int(day_label(position["entry_epoch"])[:4]),
            "exit_year": int(day_label(epoch)[:4]), "entry_raw_epoch": position["entry_epoch"], "exit_raw_epoch": epoch,
            "lots": position["lots"], "entry_price": position["entry_price"], "exit_price": price,
            "entry_atr": position["entry_atr"], "initial_stop": position["initial_stop"],
            "last_stop": position["stop"], "initial_risk_usd": position["initial_risk"],
            "completed_held_bars_before_exit": position["held"], "exit_reason": reason,
            "price_pnl_usd": price_pnl, "snapshot_swap_usd": swap, "rollover_units": swap_units,
            "spread_burden_usd": burden, "midquote_spread_burden_usd": mid_burden,
            "actual_pnl_usd": actual_pnl, "stressed_pnl_usd": stress_pnl, "midquote_stressed_pnl_usd": mid_pnl,
            "actual_balance_before": balance, "actual_balance_after": balance + actual_pnl,
        }
        trades.append(record)
        balance += actual_pnl
        stressed += stress_pnl
        mid_stressed += mid_pnl
        intents[position["intent_index"]]["closed_trade_id"] = position["trade_id"]

    def record_mark(epoch: int, phase: str, column: str) -> None:
        nonlocal peak, max_dd_money, max_dd_pct
        floating = floating_swap = 0.0
        for symbol, position in positions.items():
            mark = latest[symbol]
            value = liquidation(mark, position["direction"], column, specs[symbol])
            floating += money(position["direction"] * (value - position["entry_price"]), position["lots"], specs[symbol])
            floating_swap += swap_cost(position, epoch, specs[symbol])[0]
        equity = balance + floating + floating_swap
        peak = max(peak, equity)
        dd = peak - equity
        max_dd_money = max(max_dd_money, dd)
        max_dd_pct = max(max_dd_pct, 100.0 * dd / peak)
        marks.append({
            "role": role, "server_wall": wall_label(epoch), "phase": phase, "actual_balance": balance,
            "stressed_balance": stressed, "midquote_stressed_balance": mid_stressed,
            "open_price_pnl": floating, "open_snapshot_swap": floating_swap, "marked_actual_equity": equity,
            "equity_peak": peak, "drawdown_pct": 100.0 * dd / peak, "open_positions": len(positions),
            "reserved_original_stop_risk": sum(p["initial_risk"] for p in positions.values()),
        })

    for epoch in sorted(batches):
        current = batches[epoch]
        # All opening marks precede all uses of this batch's future high/low.
        for symbol, (_, row) in current.items():
            latest[symbol] = {"open": row["open"], "close": row["open"], "spread": row["spread"]}
        record_mark(epoch, "OPEN_BEFORE_CLOSES", "open")
        for symbol in sorted(current):
            position = positions.get(symbol)
            if position is None:
                continue
            _, row = current[symbol]
            spec = specs[symbol]
            value = liquidation(row, position["direction"], "open", spec)
            crossed = (value - position["stop"]) * position["direction"] <= 0.0
            if crossed:
                close_position(symbol, epoch, value, row["spread"] * spec["point"], "GAP_STOP")
            elif position["pending_exit"]:
                close_position(symbol, epoch, value, row["spread"] * spec["point"], position["pending_exit"])
        snapshot = balance
        reservation = sum(p["initial_risk"] for p in positions.values())
        for symbol in sorted(current, key=lambda s: priority(s, epoch)):
            index, row = current[symbol]
            atr = float(row["entry_atr"])
            if epoch >= cutoff or not math.isfinite(atr) or atr <= 0:
                continue
            spec = specs[symbol]
            direction = flow_direction(symbol, epoch)
            spread = float(row["spread"]) * spec["point"]
            entry = float(row["open"]) + (spread if direction > 0 else 0.0)
            distance = contract["initial_stop_atr"] * atr
            raw_stop = entry - direction * distance
            tick = float(spec["trade_tick_size"])
            # Round outward; risk uses the actual rounded stop distance.
            stop = math.floor(raw_stop / tick + 1e-9) * tick if direction > 0 else math.ceil(raw_stop / tick - 1e-9) * tick
            per_lot = money(abs(entry - stop), 1.0, spec)
            state = {
                "role": role, "raw_epoch": epoch, "server_wall": wall_label(epoch), "symbol": symbol,
                "direction": direction, "entry_atr": atr, "entry_price": entry, "initial_stop": stop,
                "balance_snapshot": snapshot, "reservation_before": reservation, "status": "BLOCKED",
                "reason": "", "lots": 0.0, "initial_risk_usd": 0.0, "trade_id": 0, "closed_trade_id": 0,
            }
            intents.append(state)
            if symbol in positions:
                state["reason"] = "SYMBOL_ALREADY_OPEN"
                continue
            if snapshot <= 0:
                state["reason"] = "NONPOSITIVE_BALANCE"
                continue
            current_liquidation = liquidation(row, direction, "open", spec)
            if stop <= 0 or (current_liquidation - stop) * direction <= 0:
                state["reason"] = "INVALID_INITIAL_PROTECTION_GEOMETRY"
                continue
            step = float(spec["volume_step"])
            lots = math.floor(min(spec["volume_max"], snapshot * contract["risk"]["target_position_fraction"] / per_lot) / step + 1e-10) * step
            lots = round(max(lots, float(spec["volume_min"])), 8)
            planned = per_lot * lots
            if planned > snapshot * contract["risk"]["minimum_lot_hard_cap_fraction"] + 1e-8:
                state["reason"] = "MINIMUM_LOT_HARD_CAP"
                continue
            if reservation + planned > snapshot * contract["risk"]["aggregate_original_stop_risk_fraction"] + 1e-8:
                state["reason"] = "AGGREGATE_ORIGINAL_STOP_RISK"
                continue
            trade_counter += 1
            state.update(status="ACCEPTED", reason="", lots=lots, initial_risk_usd=planned, trade_id=trade_counter)
            positions[symbol] = {
                "trade_id": trade_counter, "intent_index": len(intents) - 1, "entry_epoch": epoch,
                "entry_index": index, "direction": direction, "lots": lots, "entry_price": entry,
                "entry_spread": spread, "entry_atr": atr, "initial_stop": stop, "stop": stop,
                "initial_risk": planned, "held": 0, "best": None, "pending_exit": "",
            }
            reservation += planned
        record_mark(epoch, "OPEN_AFTER_ADMISSION", "open")
        # No new entries are admitted after any current-bar high/low is consumed.
        for symbol in sorted(current):
            position = positions.get(symbol)
            if position is None:
                continue
            _, row = current[symbol]
            spec = specs[symbol]
            direction = position["direction"]
            adverse = liquidation(row, direction, "low" if direction > 0 else "high", spec)
            if (adverse - position["stop"]) * direction <= 0.0:
                close_position(symbol, epoch + H4 - 1, position["stop"], row["spread"] * spec["point"], "INTRABAR_STOP")
                continue
            position["held"] += 1
            close = liquidation(row, direction, "close", spec)
            if position["held"] >= contract["max_held_bars"]:
                position["pending_exit"] = "HOLD8_NEXT_OPEN"
            elif role == "NO_PROGRESS_3B" and position["held"] == 3 and (close - position["entry_price"]) * direction <= 0:
                position["pending_exit"] = "NO_PROGRESS_NEXT_OPEN"
            if role == "CLOSE_TRAIL_2ATR":
                favorable = liquidation(row, direction, "high" if direction > 0 else "low", spec)
                best = position["best"]
                position["best"] = favorable if best is None else (max(best, favorable) if direction > 0 else min(best, favorable))
                raw_stop = position["best"] - direction * 2.0 * position["entry_atr"]
                tick = spec["trade_tick_size"]
                proposal = math.floor(raw_stop / tick + 1e-9) * tick if direction > 0 else math.ceil(raw_stop / tick - 1e-9) * tick
                position["stop"] = max(position["stop"], proposal) if direction > 0 else min(position["stop"], proposal)
        for symbol, (_, row) in current.items():
            latest[symbol] = {"open": row["close"], "close": row["close"], "spread": row["spread"]}
        record_mark(epoch + H4 - 1, "CLOSE", "close")
    if positions:
        raise RuntimeError(f"terminal entry cutoff left unresolved positions: {sorted(positions)}")
    accepted = [row for row in intents if row["status"] == "ACCEPTED"]
    if len(accepted) != trade_counter or trade_counter != len(trades):
        raise RuntimeError("accepted/trade reconciliation failed")
    if any(row["closed_trade_id"] != row["trade_id"] for row in accepted):
        raise RuntimeError("accepted intent has no exact close")
    if not math.isclose(balance - 100, sum(t["actual_pnl_usd"] for t in trades), abs_tol=1e-7):
        raise RuntimeError("cash reconciliation failed")
    if not math.isclose(balance - stressed, sum(t["spread_burden_usd"] for t in trades), abs_tol=1e-7):
        raise RuntimeError("spread stress reconciliation failed")
    by_year = {}
    for year in (2024, 2025):
        closing = [t for t in trades if t["exit_year"] == year]
        entering = [t for t in trades if t["entry_year"] == year]
        by_year[str(year)] = {
            "starts": len(entering), "closed_trades": len(closing),
            "actual_profit": sum(t["actual_pnl_usd"] for t in closing),
            "stressed_profit": sum(t["stressed_pnl_usd"] for t in closing),
            "midquote_stressed_profit": sum(t["midquote_stressed_pnl_usd"] for t in closing),
        }
    gate = contract["development_gates"]
    actual_net, stress_net, mid_net = balance - 100, stressed - 100, mid_stressed - 100
    checks = {
        "actual_profit": actual_net > gate["actual_profit_strictly_above"],
        "stressed_profit": min(stress_net, mid_net) > gate["stressed_profit_strictly_above"],
        "both_years_positive": all(min(y["actual_profit"], y["stressed_profit"], y["midquote_stressed_profit"]) > 0 for y in by_year.values()),
        "marked_equity_dd": max_dd_pct <= gate["proxy_marked_equity_drawdown_pct_at_most"],
        "turnover": len(trades) / len(normal_dates) >= gate["first_fills_per_normal_broker_date_at_least"],
        "each_year_starts": min(y["starts"] for y in by_year.values()) >= gate["first_fills_each_year_at_least"],
        "symbol_breadth": len({t["symbol"] for t in trades}) >= gate["traded_symbols_at_least"],
        "both_directions": {t["direction"] for t in trades} == {-1, 1},
    }
    role_root = RESULT_ROOT / role
    role_root.mkdir()
    write_csv(role_root / "intents.csv", intents)
    write_csv(role_root / "trades.csv", trades)
    write_csv(role_root / "equity.csv", marks)
    return {
        "role": role, "actual_profit_usd": actual_net, "stressed_profit_usd": stress_net,
        "midquote_stressed_profit_usd": mid_net, "snapshot_swap_usd": sum(t["snapshot_swap_usd"] for t in trades),
        "spread_burden_usd": sum(t["spread_burden_usd"] for t in trades),
        "proxy_marked_equity_dd_pct": max_dd_pct, "proxy_marked_equity_dd_usd": max_dd_money,
        "proxy_stressed_recovery": stress_net / max_dd_money if max_dd_money > 0 else None,
        "normal_broker_dates": len(normal_dates), "first_fills": len(trades),
        "first_fills_per_normal_date": len(trades) / len(normal_dates), "intents": len(intents),
        "blocked_reasons": dict(Counter(i["reason"] for i in intents if i["status"] == "BLOCKED")),
        "trades_by_symbol": dict(Counter(t["symbol"] for t in trades)),
        "trades_by_direction": dict(Counter(t["direction"] for t in trades)),
        "exit_reasons": dict(Counter(t["exit_reason"] for t in trades)), "by_year": by_year,
        "gates": checks, "passed": all(checks.values()), "final_open_positions": 0,
        "artifacts": [authority(role_root / filename) for filename in ("intents.csv", "trades.csv", "equity.csv")],
    }


def main() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    declaration = json.loads(DECLARATION_PATH.read_text(encoding="utf-8"))
    freeze_path = FAMILY / "evidence/IMPLEMENTATION_FREEZE_V1.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if digest(CONTRACT_PATH) != declaration["contract"]["sha256"]:
        raise RuntimeError("contract is not the binding declaration")
    if digest(Path(__file__)) != freeze["adapter"]["sha256"] or digest(DECLARATION_PATH) != freeze["declaration"]["sha256"]:
        raise RuntimeError("implementation/declaration changed after freeze")
    capacity = shutil.disk_usage(WORKSPACE).free
    if capacity - 128 * 1024**2 < contract["storage_reserve_bytes"]:
        raise RuntimeError("insufficient free space with bounded output reserve")
    if RESULT_ROOT.exists():
        raise RuntimeError("result root already exists; never overwrite an economic run")
    frames, specs, input_receipt = load_sources(contract, declaration)
    RESULT_ROOT.mkdir(parents=True)
    roles = []
    for role in contract["role_order"]:
        if shutil.disk_usage(WORKSPACE).free - 64 * 1024**2 < contract["storage_reserve_bytes"]:
            raise RuntimeError("storage reserve threatened before next serial role")
        print(f"Running frozen role {role}", flush=True)
        result = simulate(role, contract, frames, specs)
        roles.append(result)
        print(json.dumps({k: result[k] for k in ("role", "actual_profit_usd", "stressed_profit_usd", "proxy_marked_equity_dd_pct", "first_fills", "passed")}), flush=True)
    passing = [r for r in roles if r["passed"]]
    passing.sort(key=lambda r: (-r["stressed_profit_usd"], r["proxy_marked_equity_dd_pct"], -min(y["stressed_profit"] for y in r["by_year"].values()), contract["role_order"].index(r["role"])))
    summary = {
        "schema": "zeta-independent-exogenous-flow-h4-exit-development-v1",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "status": "COMPLETE_PROXY_SURVIVOR_REQUIRES_CONFIRMATION_AUTHORITY" if passing else "COMPLETE_PROXY_ADVERSE_NO_PASSER",
        "family": FAMILY.relative_to(WORKSPACE).as_posix(), "primary_macro_program": 4,
        "declaration": authority(DECLARATION_PATH), "implementation_freeze": authority(freeze_path),
        "adapter": authority(Path(__file__)), "input_receipt": input_receipt, "roles": roles,
        "selected_role": passing[0]["role"] if passing else None,
        "limits": contract["economics"] | {"margin": contract["risk"]["margin"], "proxy_is_native_victory": False},
        "locked_2026_opened": False, "native_EA_or_runtime_opened": False,
        "free_bytes_after": shutil.disk_usage(WORKSPACE).free,
        "output_bytes": sum(p.stat().st_size for p in RESULT_ROOT.rglob("*") if p.is_file()),
    }
    path = RESULT_ROOT / "summary.json"
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"summary": str(path), "status": summary["status"], "selected_role": summary["selected_role"], "free_GiB": summary["free_bytes_after"] / 1024**3}), flush=True)


if __name__ == "__main__":
    main()
