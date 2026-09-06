"""Complete ordinary three-policy historical economics for Family 014; no trading API."""
from pathlib import Path
import calendar
import datetime as dt
import hashlib
import json
import math
import shutil

import numpy as np
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
# Each symbol owns either one pending instruction or one complete position.
STATUS, DIRECTION, VOLUME, ENTRY, STOP, TAKE, RISK = range(7)
SIGNAL_CLOSE, SIGMA, REFERENCE, EVENT, PLACED_MS, PLACED_MONTH, PLACED_ROW = range(7, 14)
PLACED_ORD, FILLED_MS, FILLED_MONTH, FILLED_ROW, FILLED_ORD, EXPIRY, TIMEOUT = range(14, 21)
ENTRY_SPREAD, FINANCING, POSITIVE_FINANCING, SIGNAL_END, LIFE = range(21, 26)
CASH, DIR_COST, MID_COST, CREDIT, PRICE_PNL, FIN_NET, STARTS, CLOSES = range(8)
PLACEMENTS, CANCELLATIONS, EXPIRATIONS, REJECTIONS, INTENTS, ENTRY_COST, EXIT_COST, NEG_FIN = range(8, 16)
ACTION_COLUMNS = (
    "role", "symbol", "action", "reason", "observed_msc", "effective_msc", "month",
    "quote_row", "source_ordinal", "event_id", "lifecycle_id", "direction", "volume",
    "price", "stop", "take", "original_risk", "financing_delta", "cash_after",
    "directional_spread_accrued", "midpoint_spread_accrued", "positive_credit_removed", "observed_quote_symbol")
TRADE_COLUMNS = (
    "role", "symbol", "lifecycle_id", "event_id", "direction", "volume",
    "placed_msc", "filled_msc", "closed_msc", "entry", "exit", "stop", "take",
    "original_risk", "entry_spread_points", "exit_spread_points", "price_profit",
    "financing", "positive_financing", "actual_net", "directional_extra_spread",
    "midpoint_extra_spread", "directional_stressed_net", "midpoint_stressed_net",
    "no_credit_stressed_net", "exit_reason", "placed_month", "placed_row",
    "filled_month", "filled_row", "closed_month", "closed_row", "filled_source_ordinal",
    "closed_source_ordinal", "signal_nominal_end_msc")
EQUITY_COLUMNS = ("observed_msc", "month", "quote_row", "source_ordinal", "symbol",
                  "role", "cash", "actual_equity", "directional_equity",
                  "midpoint_equity", "no_credit_equity")
ACTION_NAMES = {1: "INTENT_REJECTED", 2: "PENDING_PLACED", 3: "FIRST_FILL",
                4: "FULL_CLOSE", 5: "CAUSAL_CANCEL", 6: "SPECIFIED_EXPIRY", 7: "FINANCING"}
REASON_NAMES = {0: "NONE", 1: "OWNED_LIABILITY", 2: "OUTSIDE_ENTRY_PERIOD",
                3: "STALE_DISCOVERY", 4: "REFERENCE_ALREADY_RECOVERED",
                5: "RESTING_LIMIT_MARKETABLE", 6: "INVALID_PROTECTION",
                7: "NONPOSITIVE_RISK_BASIS", 8: "MINIMUM_LOT_HARD_CAP",
                9: "AGGREGATE_ORIGINAL_RISK", 10: "STOP", 11: "TAKE", 12: "TIMEOUT"}


def fp(path):
    with path.open("rb") as h:
        digest = hashlib.file_digest(h, "sha256").hexdigest().upper()
    return {"path": path.relative_to(REPO).as_posix(), "bytes": path.stat().st_size, "sha256": digest}


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path, value):
    if path.exists():
        raise RuntimeError("Preserve the existing economic production evidence")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8", newline="\n")
    temporary.replace(path)


def save_array(path, array):
    if path.exists():
        raise RuntimeError("Preserve an existing economic tape")
    with path.with_name(path.name + ".partial").open("wb") as handle:
        np.save(handle, array, allow_pickle=False)
    path.with_name(path.name + ".partial").replace(path)
    return fp(path)


@njit(cache=True)
def emit_action(tape, n, role, symbol, code, reason, time, effective, month, row, ordinal,
                book, account, price, financing_delta, quote_symbol=-1):
    if n >= len(tape):
        raise RuntimeError("Normal action tape capacity exceeded")
    out = tape[n]
    out[0], out[1], out[2], out[3] = role, symbol, code, reason
    out[4], out[5], out[6], out[7], out[8] = time, effective, month, row, ordinal
    out[9], out[10], out[11], out[12] = book[EVENT], book[LIFE], book[DIRECTION], book[VOLUME]
    out[13], out[14], out[15], out[16] = price, book[STOP], book[TAKE], book[RISK]
    out[17], out[18] = financing_delta, account[CASH]
    out[19], out[20], out[21] = account[DIR_COST], account[MID_COST], account[CREDIT]
    out[22] = symbol if quote_symbol < 0 else quote_symbol
    return n + 1


@njit(cache=True)
def liquidation(role, books, accounts, quotes, specs):
    value = accounts[role, CASH]
    for symbol in range(3):
        b = books[role, symbol]
        if b[STATUS] == 2:
            exit_price = quotes[symbol, 0] if b[DIRECTION] == 1 else quotes[symbol, 1]
            value += b[DIRECTION] * (exit_price - b[ENTRY]) * b[VOLUME] * specs[symbol, 1]
    return value


@njit(cache=True)
def mark(role, books, accounts, quotes, specs, metrics, time, symbol, month, row, ordinal):
    value = liquidation(role, books, accounts, quotes, specs)
    a = accounts[role]
    for series in range(4):
        equity = value
        if series == 1:
            equity -= a[DIR_COST]
        elif series == 2:
            equity -= a[MID_COST]
        elif series == 3:
            equity -= a[DIR_COST] + a[CREDIT]
        m = metrics[role, series]
        m[0] = equity
        if equity > m[1]:
            m[1], m[2] = equity, time
        dollars = m[1] - equity
        percent = 100.0 * dollars / m[1]
        if percent > m[3]:
            m[3] = percent
            m[5], m[6], m[7], m[8] = m[1], equity, m[2], time
            m[9], m[10], m[11], m[12] = symbol, month, row, ordinal
        if dollars > m[4]:
            m[4] = dollars
            m[13], m[14], m[15], m[16] = m[1], equity, m[2], time
            m[17], m[18], m[19] = symbol, month, row


@njit(cache=True)
def fill(role, symbol, books, accounts, specs, quotes, actions, na, time, month, row, ordinal,
         hold_ms):
    b, a = books[role, symbol], accounts[role]
    b[STATUS] = 2
    b[FILLED_MS], b[FILLED_MONTH], b[FILLED_ROW], b[FILLED_ORD] = time, month, row, ordinal
    b[TIMEOUT] = time + hold_ms
    b[ENTRY_SPREAD] = quotes[symbol, 1] - quotes[symbol, 0]
    a[STARTS] += 1
    b[LIFE] = a[STARTS]
    cost = b[ENTRY_SPREAD] * b[VOLUME] * specs[symbol, 1]
    a[ENTRY_COST] += cost
    a[MID_COST] += 0.5 * cost
    if b[DIRECTION] == 1:
        a[DIR_COST] += cost
    return emit_action(actions, na, role, symbol, 3, 0, time, time, month, row, ordinal,
                       b, a, b[ENTRY], 0.0)


@njit(cache=True)
def close(role, symbol, books, accounts, specs, quotes, actions, trades, na, nt,
          time, month, row, ordinal, price, reason):
    if nt >= len(trades):
        raise RuntimeError("Normal trade tape capacity exceeded")
    b, a = books[role, symbol], accounts[role]
    multiplier = b[VOLUME] * specs[symbol, 1]
    spread_out = quotes[symbol, 1] - quotes[symbol, 0]
    entry_cost, exit_cost = b[ENTRY_SPREAD] * multiplier, spread_out * multiplier
    pnl = b[DIRECTION] * (price - b[ENTRY]) * multiplier
    a[CASH] += pnl
    a[PRICE_PNL] += pnl
    a[CLOSES] += 1
    a[EXIT_COST] += exit_cost
    a[MID_COST] += 0.5 * exit_cost
    if b[DIRECTION] == -1:
        a[DIR_COST] += exit_cost
    directional = entry_cost if b[DIRECTION] == 1 else exit_cost
    midpoint = 0.5 * (entry_cost + exit_cost)
    actual = pnl + b[FINANCING]
    out = trades[nt]
    out[0], out[1], out[2], out[3] = role, symbol, b[LIFE], b[EVENT]
    out[4], out[5], out[6], out[7], out[8] = b[DIRECTION], b[VOLUME], b[PLACED_MS], b[FILLED_MS], time
    out[9], out[10], out[11], out[12], out[13] = b[ENTRY], price, b[STOP], b[TAKE], b[RISK]
    out[14], out[15], out[16], out[17], out[18] = b[ENTRY_SPREAD], spread_out, pnl, b[FINANCING], b[POSITIVE_FINANCING]
    out[19], out[20], out[21] = actual, directional, midpoint
    out[22], out[23], out[24], out[25] = actual-directional, actual-midpoint, actual-directional-b[POSITIVE_FINANCING], reason
    out[26], out[27], out[28], out[29] = b[PLACED_MONTH], b[PLACED_ROW], b[FILLED_MONTH], b[FILLED_ROW]
    out[30], out[31], out[32], out[33], out[34] = month, row, b[FILLED_ORD], ordinal, b[SIGNAL_END]
    na = emit_action(actions, na, role, symbol, 4, reason, time, time, month, row, ordinal,
                     b, a, price, 0.0)
    b[:] = 0.0
    return na, nt + 1


@njit(cache=True)
def emit_equity(tape, n, meta, accounts, metrics):
    for role in range(3):
        if n >= len(tape):
            raise RuntimeError("Normal minute equity capacity exceeded")
        out = tape[n]
        out[0], out[1], out[2], out[3], out[4] = meta[0], meta[2], meta[3], meta[4], meta[1]
        out[5], out[6] = role, accounts[role, CASH]
        for series in range(4):
            out[7 + series] = metrics[role, series, 0]
        n += 1
    meta[6] = meta[0] // 60000
    return n


@njit(cache=True)
def consume_month(ticks, events, bars, offsets, month, books, accounts, quotes, metrics, meta,
                  specs, parameters, actions, trades, equity):
    index, ei, bi = np.zeros(3, dtype=np.int64), np.zeros(3, dtype=np.int64), np.zeros(3, dtype=np.int64)
    na, nt, ne, consumed = 0, 0, 0, 0
    total = len(ticks[0]) + len(ticks[1]) + len(ticks[2])
    # Parameters are the already-declared economics; no fitted quantities enter.
    limit_sigma, cancel_sigma, expiry_ms, stop_sigma, hold_ms = parameters[:5]
    target_fraction, minimum_cap, aggregate_cap, freshness_ms = parameters[5:9]
    empty = np.zeros(26, dtype=np.float64)
    while consumed < total:
        symbol, time = -1, 9223372036854775807
        for s in range(3):
            if index[s] < len(ticks[s]):
                candidate = ticks[s][index[s]]["time_msc"]
                # Strict < retains fixed symbol rank at equal milliseconds.
                if candidate < time:
                    symbol, time = s, candidate
        row = index[symbol]
        ordinal = offsets[symbol] + row
        if meta[0] >= 0 and time < meta[0]:
            raise RuntimeError("Global source chronology reversed")
        if meta[0] >= 0 and time // 60000 != meta[0] // 60000 and meta[6] != meta[0] // 60000:
            ne = emit_equity(equity, ne, meta, accounts, metrics)
        day = time // 86400000
        if meta[5] < 0:
            meta[5] = day
        elif day > meta[5]:
            for boundary_day in range(meta[5] + 1, day + 1):
                weekday_held = (boundary_day - 1 + 3) % 7
                if weekday_held >= 5:
                    continue
                charge_time = boundary_day * 86400000
                for role in range(3):
                    for s in range(3):
                        b, a = books[role, s], accounts[role]
                        if b[STATUS] != 2:
                            continue
                        factor = 3.0 if weekday_held == int(specs[s, 7]) else 1.0
                        rate = specs[s, 5] if b[DIRECTION] == 1 else specs[s, 6]
                        delta = b[VOLUME] * rate * factor
                        b[FINANCING] += delta
                        a[CASH] += delta
                        a[FIN_NET] += delta
                        if delta > 0:
                            b[POSITIVE_FINANCING] += delta
                            a[CREDIT] += delta
                        elif delta < 0:
                            a[NEG_FIN] -= delta
                        na = emit_action(actions, na, role, s, 7, 0, time, charge_time, month,
                                         row, ordinal, b, a, 0.0, delta, symbol)
                        mark(role, books, accounts, quotes, specs, metrics, charge_time, -1,
                             month, -1, -1)
            meta[5] = day
        pending_changed = False
        if time >= meta[7]:
            for role in range(3):
                for s in range(3):
                    b, a = books[role, s], accounts[role]
                    if b[STATUS] == 1 and time >= b[EXPIRY]:
                        a[EXPIRATIONS] += 1
                        na = emit_action(actions, na, role, s, 6, 0, time, b[EXPIRY], month,
                                         row, ordinal, b, a, b[ENTRY], 0.0, symbol)
                        b[:] = 0.0
                        pending_changed = True
        tick = ticks[symbol][row]
        quotes[symbol, 0], quotes[symbol, 1] = tick["bid"], tick["ask"]
        bid, ask = tick["bid"], tick["ask"]
        has_bar = bi[symbol] < len(bars[symbol]) and bars[symbol][bi[symbol]]["discovery_row"] == row
        has_event = ei[symbol] < len(events[symbol]) and events[symbol][ei[symbol]]["discovery_row"] == row
        for role in range(3):
            b, a = books[role, symbol], accounts[role]
            changed = False
            if b[STATUS] == 1:
                hit = ask <= b[ENTRY] if b[DIRECTION] == 1 else bid >= b[ENTRY]
                if hit:
                    if ordinal <= b[PLACED_ORD]:
                        raise RuntimeError("A pending instruction cannot fill on submission ordinal")
                    na = fill(role, symbol, books, accounts, specs, quotes, actions, na,
                              time, month, row, ordinal, hold_ms)
                    changed, pending_changed = True, True
            # Server protection includes an adverse gap through a just-activated limit.
            if b[STATUS] == 2:
                liquidation_side = bid if b[DIRECTION] == 1 else ask
                stop_hit = liquidation_side <= b[STOP] if b[DIRECTION] == 1 else liquidation_side >= b[STOP]
                take_hit = liquidation_side >= b[TAKE] if b[DIRECTION] == 1 else liquidation_side <= b[TAKE]
                if stop_hit:
                    na, nt = close(role, symbol, books, accounts, specs, quotes, actions, trades,
                                   na, nt, time, month, row, ordinal, liquidation_side, 10)
                elif take_hit:
                    na, nt = close(role, symbol, books, accounts, specs, quotes, actions, trades,
                                   na, nt, time, month, row, ordinal, b[TAKE], 11)
                changed = True
            # Account marks follow the quote's server actions, before EA decisions.
            if changed:
                mark(role, books, accounts, quotes, specs, metrics, time, symbol, month, row, ordinal)
            if b[STATUS] == 2 and time >= b[TIMEOUT]:
                liquidation_side = bid if b[DIRECTION] == 1 else ask
                na, nt = close(role, symbol, books, accounts, specs, quotes, actions, trades,
                               na, nt, time, month, row, ordinal, liquidation_side, 12)
                mark(role, books, accounts, quotes, specs, metrics, time, symbol, month, row, ordinal)
            if role == 2 and b[STATUS] == 1 and has_bar:
                bar = bars[symbol][bi[symbol]]
                completed_mid = (bar["close_bid"] + bar["close_ask"]) / 2
                later = (bar["minute"] + 1) * 60000 > b[SIGNAL_END]
                if later and b[DIRECTION] * (completed_mid - b[SIGNAL_CLOSE]) <= -cancel_sigma * b[SIGMA]:
                    a[CANCELLATIONS] += 1
                    na = emit_action(actions, na, role, symbol, 5, 0, time, time, month,
                                     row, ordinal, b, a, b[ENTRY], 0.0)
                    b[:] = 0.0
                    pending_changed = True
            if has_event:
                event = events[symbol][ei[symbol]]
                if event["discovery_source_ordinal"] != ordinal or event["discovery_msc"] != time:
                    raise RuntimeError("Frozen event lost its exact quote source identity")
                a[INTENTS] += 1
                direction, sd, reference = event["direction"], event["sigma"], event["reference"]
                reason, volume, risk, entry, stop, take = 0, 0.0, 0.0, 0.0, 0.0, 0.0
                if b[STATUS] != 0:
                    reason = 1
                elif not event["optimistic_entry_period"]:
                    reason = 2
                elif time - event["nominal_bar_end_msc"] > freshness_ms:
                    reason = 3
                elif direction * ((bid + ask) / 2 - reference) >= 0:
                    reason = 4
                tick_size, contract_size = specs[symbol, 0], specs[symbol, 1]
                if reason == 0:
                    if role == 0:
                        entry = ask if direction == 1 else bid
                    else:
                        raw_limit = event["mid_close"] - direction * limit_sigma * sd
                        entry = (math.floor(raw_limit/tick_size + 1e-9) if direction == 1 else
                                 math.ceil(raw_limit/tick_size - 1e-9)) * tick_size
                        if (direction == 1 and entry >= ask) or (direction == -1 and entry <= bid):
                            reason = 5
                    raw_stop = entry - direction * stop_sigma * sd
                    stop = (math.floor(raw_stop/tick_size + 1e-9) if direction == 1 else
                            math.ceil(raw_stop/tick_size - 1e-9)) * tick_size
                    take = (math.floor(reference/tick_size + 1e-9) if direction == 1 else
                            math.ceil(reference/tick_size - 1e-9)) * tick_size
                    if direction*(entry-stop) <= 0 or direction*(take-entry) <= 0:
                        reason = 6
                    elif role == 0 and ((direction == 1 and stop >= bid) or
                                        (direction == -1 and stop <= ask)):
                        reason = 6
                if reason == 0:
                    basis = min(a[CASH], liquidation(role, books, accounts, quotes, specs))
                    per_lot = abs(entry-stop) * contract_size
                    if basis <= 0 or not math.isfinite(basis) or per_lot <= 0:
                        reason = 7
                    else:
                        volume = math.floor((basis*target_fraction/per_lot + 1e-12)/specs[symbol, 3]) * specs[symbol, 3]
                        if volume < specs[symbol, 2]:
                            volume = specs[symbol, 2]
                            if volume*per_lot > basis*minimum_cap + 1e-10:
                                reason = 8
                        volume = min(volume, specs[symbol, 4])
                        risk = volume * per_lot
                        reserved = 0.0
                        for s in range(3):
                            if books[role, s, STATUS] != 0:
                                reserved += books[role, s, RISK]
                        if reason == 0 and reserved + risk > basis*aggregate_cap + 1e-10:
                            reason = 9
                if reason != 0:
                    a[REJECTIONS] += 1
                    empty[EVENT], empty[DIRECTION] = event["event_id"], direction
                    na = emit_action(actions, na, role, symbol, 1, reason, time, time, month,
                                     row, ordinal, empty, a, 0.0, 0.0)
                else:
                    b[:] = 0.0
                    b[STATUS], b[DIRECTION], b[VOLUME], b[ENTRY] = 1, direction, volume, entry
                    b[STOP], b[TAKE], b[RISK] = stop, take, risk
                    b[SIGNAL_CLOSE], b[SIGMA], b[REFERENCE], b[EVENT] = event["mid_close"], sd, reference, event["event_id"]
                    b[PLACED_MS], b[PLACED_MONTH], b[PLACED_ROW], b[PLACED_ORD] = time, month, row, ordinal
                    b[EXPIRY], b[SIGNAL_END] = time+expiry_ms, event["nominal_bar_end_msc"]
                    if role == 0:
                        na = fill(role, symbol, books, accounts, specs, quotes, actions, na,
                                  time, month, row, ordinal, hold_ms)
                        mark(role, books, accounts, quotes, specs, metrics, time, symbol, month, row, ordinal)
                    else:
                        a[PLACEMENTS] += 1
                        na = emit_action(actions, na, role, symbol, 2, 0, time, time, month,
                                         row, ordinal, b, a, entry, 0.0)
                        pending_changed = True
        if pending_changed:
            meta[7] = 9223372036854775807
            for role in range(3):
                for s in range(3):
                    if books[role, s, STATUS] == 1:
                        meta[7] = min(meta[7], int(books[role, s, EXPIRY]))
        if has_bar:
            bi[symbol] += 1
        if has_event:
            ei[symbol] += 1
        meta[0], meta[1], meta[2], meta[3], meta[4] = time, symbol, month, row, ordinal
        index[symbol] += 1
        consumed += 1
    if meta[0] >= 0 and meta[6] != meta[0] // 60000:
        ne = emit_equity(equity, ne, meta, accounts, metrics)
    for s in range(3):
        if ei[s] != len(events[s]) or bi[s] != len(bars[s]):
            raise RuntimeError("Not every declared event/bar discovery was consumed")
    return na, nt, ne, consumed


def main():
    contract = read(ROOT / "config/contract.json")
    artifact = REPO / "lab/artifacts/raw" / contract["family"]
    output = artifact / "economics/attempt-01"
    freeze_path = ROOT / "evidence/ECONOMIC_IMPLEMENTATION_FREEZE_V1.json"
    freeze = read(freeze_path)
    for record in freeze["files"]:
        if fp(REPO / record["path"]) != record:
            raise RuntimeError("Frozen economic source/input authority drift")
    supply = read(ROOT / "evidence/STRUCTURAL_SUPPLY_V1.json")
    if not all(supply["necessary_gates"].values()):
        raise RuntimeError("Necessary supply did not authorize economics")
    if output.exists():
        raise RuntimeError("An existing economic attempt needs attributable continuation/correction")
    acquisition = read(ROOT / "evidence/INPUT_ACQUISITION_V1.json")
    source = read(artifact / "input/spec/current-contract-source.json")
    if (not read(ROOT / "evidence/SOURCE_READER_SHUTDOWN_V1.json")["normal_exit_completed"] or
            acquisition["status"] != "COMPLETE_SOURCE_INPUTS_FEATURES_UNOPENED"):
        raise RuntimeError("Own source reader must already be stopped after complete acquisition")
    runtime = REPO / contract["identity"]["source_runtime"]
    used = sum(p.stat().st_size for root in (artifact, runtime) for p in root.rglob("*") if p.is_file())
    output_allowance = 2 * 1024**3
    if (used + output_allowance > contract["storage"]["initial_acquisition_and_results_allowance_bytes"] or
            shutil.disk_usage(REPO).free - output_allowance < contract["storage"]["minimum_free_bytes"]):
        raise RuntimeError("Bounded economic output would exceed declared storage/reserve")
    output.mkdir(parents=True)
    specs = np.zeros((3, 8), dtype=np.float64)
    all_events, all_bars = [], []
    for s, symbol in enumerate(contract["symbols"]):
        spec = source["symbols"][symbol]
        if spec["swap_mode"] != 2 or spec["currency_profit"] != "USD":
            raise RuntimeError("Undeclared contract currency/financing conversion")
        specs[s] = [spec["trade_tick_size"], spec["trade_contract_size"], spec["volume_min"],
                    spec["volume_step"], spec["volume_max"], spec["swap_long"], spec["swap_short"],
                    (spec["swap_rollover3days"] + 6) % 7]
        for suffix, collection in (("events", all_events), ("completed-bars", all_bars)):
            path = artifact / "features" / f"{symbol}-{suffix}.npy"
            expected = next(q for q in supply["outputs"] if q["path"] == path.relative_to(REPO).as_posix())
            if fp(path) != expected:
                raise RuntimeError("Frozen structural tape drift")
            collection.append(np.load(path, mmap_mode="r", allow_pickle=False))
    accounts, books = np.zeros((3, 16)), np.zeros((3, 3, 26))
    accounts[:, CASH] = contract["risk"]["initial_deposit_usd"]
    quotes, metrics = np.full((3, 2), np.nan), np.zeros((3, 4, 20))
    metrics[:, :, 0:2] = contract["risk"]["initial_deposit_usd"]
    metrics[:, :, 2] = -1
    meta = np.array([-1, -1, 0, -1, -1, -1, -1, 9223372036854775807], dtype=np.int64)
    parameters = np.array([
        contract["order_policies"]["limit_additional_sigma"],
        contract["order_policies"]["cancel_additional_sigma"],
        contract["order_policies"]["expiry_minutes"]*60000,
        contract["geometry"]["stop_sigma_from_entry"],
        contract["geometry"]["maximum_hold_minutes"]*60000,
        contract["risk"]["target_position_fraction"],
        contract["risk"]["minimum_lot_hard_cap_fraction"],
        contract["risk"]["aggregate_original_stop_risk_fraction"],
        contract["signal"]["freshness_ms"]], dtype=np.float64)
    cumulative, source_offsets = [0, 0, 0], {}
    for symbol_index, symbol in enumerate(contract["symbols"]):
        for chunk in sorted((c for c in acquisition["completed"] if c["symbol"] == symbol),
                            key=lambda c: c["month"]):
            source_offsets[(symbol, chunk["month"])] = cumulative[symbol_index]
            cumulative[symbol_index] += chunk["rows"]
    snapshots, manifest = {}, []
    trade_sums = np.zeros((3, 9))
    trade_counts, long_counts, short_counts = np.zeros(3, dtype=np.int64), np.zeros(3, dtype=np.int64), np.zeros(3, dtype=np.int64)
    by_symbol = np.zeros((3, 3), dtype=np.int64)
    counts_by_year = {str(year): np.zeros(3, dtype=np.int64) for year in (2024, 2025)}
    cash_by_year = {str(year): np.zeros((3, 2)) for year in (2024, 2025)}
    reason_counts = np.zeros((3, 13), dtype=np.int64)
    action_counts = np.zeros((3, 8), dtype=np.int64)
    source_rows, all_action_rows, all_trade_rows, all_equity_rows = 0, 0, 0, 0
    try:
        for year in (2024, 2025):
            for month_number in range(1, 13):
                month = f"{year}{month_number:02d}"
                native, events, bars, offsets = [], [], [], []
                for s, symbol in enumerate(contract["symbols"]):
                    chunk = next(c for c in acquisition["completed"] if c["symbol"] == symbol and c["month"] == month)
                    path = REPO / chunk["ticks"]["path"]
                    if fp(path) != chunk["ticks"]:
                        raise RuntimeError("Owned economic tick input changed")
                    native.append(np.load(path, mmap_mode="r", allow_pickle=False))
                    events.append(np.array(all_events[s][all_events[s]["discovery_month"] == int(month)]))
                    bars.append(np.array(all_bars[s][all_bars[s]["discovery_month"] == int(month)]))
                    offsets.append(source_offsets[(symbol, month)])
                intent_capacity = sum(len(e) for e in events) * 3
                actions = np.empty(((intent_capacity + 9) * 8 + 400, len(ACTION_COLUMNS)))
                trades = np.empty((intent_capacity + 9, len(TRADE_COLUMNS)))
                equity = np.empty(((calendar.monthrange(year, month_number)[1]*1440+2)*3, len(EQUITY_COLUMNS)))
                na, nt, ne, consumed = consume_month(
                    native, events, bars, np.array(offsets, dtype=np.int64), int(month),
                    books, accounts, quotes, metrics, meta, specs, parameters, actions, trades, equity)
                actions, trades, equity = actions[:na], trades[:nt], equity[:ne]
                if not (np.all(np.isfinite(accounts)) and np.all(np.isfinite(metrics))):
                    raise RuntimeError("Nonfinite complete accounting")
                for role in range(3):
                    ta = trades[trades[:, 0] == role]
                    aa = actions[actions[:, 0] == role]
                    trade_counts[role] += len(ta)
                    long_counts[role] += np.count_nonzero(ta[:, 4] == 1)
                    short_counts[role] += np.count_nonzero(ta[:, 4] == -1)
                    for s in range(3):
                        by_symbol[role, s] += np.count_nonzero(ta[:, 1] == s)
                    # Complete trade sums reconcile only at the final flat boundary.
                    for target, column in enumerate((16, 17, 18, 19, 20, 21, 22, 23, 24)):
                        trade_sums[role, target] += ta[:, column].sum()
                    for code in range(1, 8):
                        action_counts[role, code] += np.count_nonzero(aa[:, 2] == code)
                    for reason in range(1, 10):
                        reason_counts[role, reason] += np.count_nonzero((aa[:, 2] == 1) & (aa[:, 3] == reason))
                    fills = aa[aa[:, 2] == 3]
                    for event in fills:
                        fy = str(dt.datetime.fromtimestamp(event[4]/1000, tz=dt.timezone.utc).year)
                        counts_by_year[fy][role] += 1
                    for trade in ta:
                        cy = str(dt.datetime.fromtimestamp(trade[8]/1000, tz=dt.timezone.utc).year)
                        cash_by_year[cy][role, 0] += trade[16]
                    for financing in aa[aa[:, 2] == 7]:
                        cy = str(dt.datetime.fromtimestamp(financing[5]/1000, tz=dt.timezone.utc).year)
                        cash_by_year[cy][role, 1] += financing[17]
                for label, values in (("actions", actions), ("trades", trades), ("minute-equity", equity)):
                    manifest.append(save_array(output / f"{month}-{label}.npy", values))
                source_rows += consumed
                all_action_rows += na
                all_trade_rows += nt
                all_equity_rows += ne
                snapshots[month] = {"accounts": accounts.tolist(), "equity": metrics[:, :, 0].tolist(),
                                    "book_status": books[:, :, STATUS].astype(int).tolist(),
                                    "last_quote_raw_ms": int(meta[0])}
                save_json(output / f"{month}-checkpoint.json", {
                    "schema": "zeta-ch014-ordinary-month-checkpoint-v1", "month": month,
                    "economic_freeze": fp(freeze_path), "books": books.tolist(), "accounts": accounts.tolist(),
                    "quotes": quotes.tolist(), "metrics": metrics.tolist(), "meta": meta.tolist(),
                    "source_rows_consumed": source_rows,
                    "interpretation": "Intermediate production checkpoint only, no selection or economic verdict."})
                if (shutil.disk_usage(REPO).free < contract["storage"]["minimum_free_bytes"] or
                        sum(x["bytes"] for x in manifest) > output_allowance):
                    raise RuntimeError("Bounded economic storage reserve needs correction")
                print(json.dumps({"status": "ORDINARY_MONTH_COMPLETE", "month": month,
                                  "source_rows_consumed": source_rows,
                                  "months_complete": len(snapshots)}), flush=True)
                del native, events, bars, actions, trades, equity
        if np.any(books[:, :, STATUS] != 0):
            raise RuntimeError("Frozen cutoff/normal exits did not produce complete flat evidence")
        periods = {}
        initial = np.full((3, 4), contract["risk"]["initial_deposit_usd"])
        previous_cash = np.full(3, contract["risk"]["initial_deposit_usd"])
        for year in ("2024", "2025"):
            snapshot = snapshots[year+"12"]
            closing = np.array(snapshot["equity"])
            cash = np.array(snapshot["accounts"])[:, CASH]
            cash_delta = cash - previous_cash
            residual = cash_by_year[year].sum(axis=1) - cash_delta
            if np.max(np.abs(residual)) > 1e-7:
                raise RuntimeError("Calendar cash and booking evidence does not reconcile")
            periods[year] = {"marked_changes": (closing-initial).tolist(),
                             "cash_changes": cash_delta.tolist(),
                             "cash_price_and_financing": cash_by_year[year].tolist(),
                             "cash_reconciliation_residual": residual.tolist(),
                             "first_fills": counts_by_year[year].tolist()}
            initial, previous_cash = closing, cash
        roles = {}
        for role, name in enumerate(contract["role_order"]):
            a, totals = accounts[role], trade_sums[role]
            nets = [a[CASH]-100, a[CASH]-100-a[DIR_COST], a[CASH]-100-a[MID_COST],
                    a[CASH]-100-a[DIR_COST]-a[CREDIT]]
            expected = np.array([a[PRICE_PNL], a[FIN_NET], a[CREDIT], *nets[:1], a[DIR_COST], a[MID_COST], *nets[1:]])
            residual = totals - expected
            count_ok = (int(a[STARTS]) == int(a[CLOSES]) == int(trade_counts[role]) ==
                        int(action_counts[role, 3]) == int(action_counts[role, 4]))
            pending_ok = (int(a[PLACEMENTS]) == (0 if role == 0 else int(a[STARTS])) +
                          int(a[CANCELLATIONS]) + int(a[EXPIRATIONS]))
            intents_ok = int(a[INTENTS]) == int(a[REJECTIONS]) + (int(a[STARTS]) if role == 0 else int(a[PLACEMENTS]))
            cash_ok = abs(a[CASH] - 100 - a[PRICE_PNL] - a[FIN_NET]) <= 1e-7
            if not (count_ok and pending_ok and intents_ok and cash_ok and np.max(np.abs(residual)) <= 1e-7):
                raise RuntimeError("Complete trade/order/cash/cost accounting failed")
            yearly = {y: periods[y]["marked_changes"][role] for y in periods}
            gates = {
                "actual_profit": nets[0] > contract["development_gates"]["actual_profit_strictly_above"],
                "all_stressed_profit": all(v > contract["development_gates"]["all_stressed_profit_series_strictly_above"] for v in nets[1:]),
                "both_years_all_valuations_positive": all(v > 0 for y in yearly.values() for v in y),
                "equity_drawdown": metrics[role, 0, 3] <= contract["development_gates"]["proxy_equity_drawdown_pct_at_most"],
                "genuine_lifecycle_turnover": a[STARTS]/supply["calendar"]["union_dates"] >= contract["development_gates"]["genuine_first_fills_per_normal_date_at_least"],
                "minimum_each_year": all(counts_by_year[y][role] >= contract["development_gates"]["genuine_first_fills_each_year_at_least"] for y in counts_by_year),
                "three_symbols": int(np.count_nonzero(by_symbol[role])) == 3,
                "both_directions": long_counts[role] > 0 and short_counts[role] > 0}
            roles[name] = {
                "actual_net": nets[0], "directional_stressed_net": nets[1], "midpoint_stressed_net": nets[2],
                "no_positive_credit_stressed_net": nets[3], "actual_marked_equity_dd_pct": metrics[role, 0, 3],
                "drawdown_metrics_by_valuation": metrics[role].tolist(), "calendar_marked_changes": yearly,
                "first_fills": int(a[STARTS]), "first_fills_per_normal_date": a[STARTS]/supply["calendar"]["union_dates"],
                "first_fills_by_year": {y: int(counts_by_year[y][role]) for y in counts_by_year},
                "closed_lifecycles_by_symbol": {s: int(by_symbol[role, i]) for i, s in enumerate(contract["symbols"])},
                "long_short_lifecycles": [int(long_counts[role]), int(short_counts[role])],
                "placed_pending": int(a[PLACEMENTS]), "causal_cancellations": int(a[CANCELLATIONS]),
                "specified_expirations": int(a[EXPIRATIONS]), "intents": int(a[INTENTS]),
                "rejection_reasons": {REASON_NAMES[i]: int(reason_counts[role, i]) for i in range(1, 10)},
                "price_profit": a[PRICE_PNL], "net_financing": a[FIN_NET], "positive_financing_removed": a[CREDIT],
                "negative_financing_charges": a[NEG_FIN], "directional_extra_spread": a[DIR_COST],
                "midpoint_extra_spread": a[MID_COST], "entry_spread_total": a[ENTRY_COST], "exit_spread_total": a[EXIT_COST],
                "complete_accounting": {"full_close_count": count_ok, "pending_ownership": pending_ok,
                    "all_intents_classified": intents_ok, "cash": cash_ok, "trade_sum_residuals": residual.tolist(),
                    "final_pending": 0, "final_positions": 0},
                "gates": gates, "passed": all(gates.values())}
        survivors = [name for name in contract["role_order"] if roles[name]["passed"]]
        survivors.sort(key=lambda name: (-roles[name]["no_positive_credit_stressed_net"],
                                         roles[name]["actual_marked_equity_dd_pct"],
                                         -min(v[3] for v in roles[name]["calendar_marked_changes"].values()),
                                         contract["role_order"].index(name)))
        # Every raw checkpoint is owned and hashed, alongside the primary tapes.
        for path in sorted(output.glob("*-checkpoint.json")):
            manifest.append(fp(path))
        result = {
            "schema": "zeta-ch014-complete-development-result-v1",
            "recorded_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "status": "COMPLETE_DEVELOPMENT_SURVIVOR_REQUIRES_LOCKED_CONFIRMATION" if survivors else
                      "COMPLETE_VALID_ADVERSE_DEVELOPMENT_NO_SURVIVOR",
            "economic_freeze": fp(freeze_path), "input_seal": fp(ROOT/"evidence/INPUT_SEAL_V1.json"),
            "structural_authority": fp(ROOT/"evidence/STRUCTURAL_SUPPLY_V1.json"),
            "normal_source_dates": supply["calendar"]["union_dates"], "roles": roles, "calendar_periods": periods,
            "selected_unchanged_role": survivors[0] if survivors else None, "complete_passers": survivors,
            "source_rows_consumed_once_for_three_roles": source_rows,
            "action_rows": all_action_rows, "complete_trade_rows": all_trade_rows,
            "minute_equity_rows": all_equity_rows, "output_files": manifest,
            "output_bytes": sum(x["bytes"] for x in manifest),
            "columns": {"actions": ACTION_COLUMNS, "trades": TRADE_COLUMNS, "minute_equity": EQUITY_COLUMNS},
            "action_codes": ACTION_NAMES, "reason_codes": REASON_NAMES,
            "metric_columns": ["last_equity", "peak", "peak_msc", "max_dd_pct", "max_dd_usd",
                               "pct_peak", "pct_bottom", "pct_peak_msc", "pct_bottom_msc", "pct_bottom_symbol",
                               "pct_month", "pct_quote_row", "pct_source_ordinal",
                               "usd_peak", "usd_bottom", "usd_peak_msc", "usd_bottom_msc",
                               "usd_bottom_symbol", "usd_month", "usd_quote_row"],
            "valuation_order": ["actual", "directional_doubled_spread", "midpoint_doubled_spread", "directional_no_positive_credit"],
            "limitations": [
                "Observed quotes do not certify depth, latency, partial fill, historical permission, margin or broker stop-out. Risk-only admission and zero commission are explicit optimistic proxy limits.",
                "Frozen current swap mode 2 is only a dated 2024-2025 financing approximation. Crossed raw-day charges use recorded weekday/Friday triple convention, not a certified historical UTC/broker bridge.",
                "Fixed cross-symbol same-ms rank, exact-limit/no-favorable-gap fills and post-server-action quote marks are disclosed proxy semantics. No synthetic M1 intrabar path or native equity-DD claim.",
                "All stress accrues at actual executed entry/exit and financing events on the actual-sized path. Yearly marked changes and separately reconciled realized cash are both retained.",
                "All numeric tape columns are float64; every stored millisecond, ordinal and ID is below 2^53 and exactly representable. Column schemas preserve their integer interpretation."
            ],
            "locked_2026_opened": False, "candidate_EA_or_native_opened": False, "real_trading_API_calls": 0,
            "free_bytes_after": shutil.disk_usage(REPO).free}
        save_json(ROOT / "evidence/DEVELOPMENT_RESULT_V1.json", result)
        print(json.dumps({"status": result["status"], "selected_unchanged_role": result["selected_unchanged_role"],
                          "roles": {n: {k: x[k] for k in ("actual_net", "directional_stressed_net",
                            "midpoint_stressed_net", "no_positive_credit_stressed_net",
                            "actual_marked_equity_dd_pct", "first_fills", "first_fills_per_normal_date", "passed")}
                                    for n, x in roles.items()}}), flush=True)
    except BaseException as exc:
        save_json(output / "INCOMPLETE_PRODUCTION.json", {
            "schema": "zeta-ch014-incomplete-economic-production-v1",
            "recorded_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "economic_freeze": fp(freeze_path), "complete_months": list(snapshots),
            "error": type(exc).__name__ + ": " + str(exc),
            "status": "ENGINEERING_OR_SOURCE_CORRECTION_REQUIRED_NOT_AN_ECONOMIC_VERDICT"})
        raise


if __name__ == "__main__":
    main()
