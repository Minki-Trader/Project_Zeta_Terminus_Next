"""Ordinary shared-account execution proxy for the frozen intrinsic-event bundle."""
from collections import Counter, defaultdict
from pathlib import Path
import csv
import datetime as dt
import hashlib
import json
import math
import shutil

import numpy as np

FAMILY_ROOT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]


def fingerprint(path):
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest().upper()
    return {"path": path.relative_to(REPO).as_posix(), "bytes": path.stat().st_size, "sha256": digest}


def epoch(label):
    return int(dt.datetime.fromisoformat(label).replace(tzinfo=dt.timezone.utc).timestamp())


def day_year(timestamp):
    return dt.datetime.fromtimestamp(int(timestamp), dt.timezone.utc).year


def role_direction(role, event):
    sign = int(event["new_direction"])
    if role == "DC_FADE":
        return -sign
    if role == "DC_OVERSHOOT_CONTEXT" and event["completed_overshoot"] >= event["trigger_delta"]:
        return -sign
    return sign


class Account:
    def __init__(self, role, contract, specs, output):
        self.role, self.contract, self.specs = role, contract, specs
        self.cash = contract["risk"]["initial_deposit_usd"]
        self.initial = self.cash
        self.positions = {}
        self.marks = {}
        self.trades, self.financing = [], []
        self.admission_counts = Counter()
        self.starts_year, self.starts_symbol, self.starts_direction = Counter(), Counter(), Counter()
        self.realized_year = defaultdict(float)
        self.year_end = {}
        self.extra_direction = self.extra_mid = self.positive_swap = 0.0
        self.peak = self.cash
        self.dd = 0.0
        self.sequence = 0
        self.last_time = None
        self.output = output
        output.mkdir()
        self.handles = []
        def writer(name, fields):
            handle = (output / name).open("w", encoding="utf-8", newline="")
            self.handles.append(handle)
            w = csv.writer(handle)
            w.writerow(fields)
            return w
        self.admission_writer = writer("admissions.csv", [
            "time", "symbol", "event_sequence", "direction", "status", "trade_id",
            "reference_equity", "volume", "original_stop_risk"])
        self.equity_writer = writer("equity.csv", [
            "time", "opening_equity", "closing_equity", "closing_cash",
            "direction_stress_equity", "midpoint_stress_equity",
            "no_positive_credit_stress_equity", "open_positions"])

    def equity(self):
        value = self.cash
        for symbol, position in self.positions.items():
            bid, ask = self.marks[symbol]
            exit_price = bid if position["direction"] == 1 else ask
            value += position["direction"] * (exit_price - position["entry_price"]) * position["value_per_price"]
        return value

    def observe_dd(self, equity):
        self.peak = max(self.peak, equity)
        self.dd = max(self.dd, 100.0 * (self.peak - equity) / self.peak)

    def accrue_financing(self, timestamp):
        if self.last_time is None:
            return
        boundary = (self.last_time // 86400 + 1) * 86400
        while boundary <= timestamp:
            ending_day = dt.datetime.fromtimestamp(boundary - 1, dt.timezone.utc)
            if ending_day.weekday() < 5:
                mql_weekday = (ending_day.weekday() + 1) % 7
                for symbol, position in self.positions.items():
                    if position["entry_time"] >= boundary:
                        continue
                    spec = self.specs[symbol]
                    rate = spec["swap_long"] if position["direction"] == 1 else spec["swap_short"]
                    factor = 3 if mql_weekday == spec["swap_rollover3days"] else 1
                    amount = rate * position["volume"] * factor
                    position["swap"] += amount
                    position["positive_swap"] += max(0.0, amount)
                    self.cash += amount
                    self.positive_swap += max(0.0, amount)
                    self.realized_year[day_year(boundary)] += amount
                    self.financing.append({"time": boundary, "trade_id": position["trade_id"],
                        "symbol": symbol, "rate": rate, "factor": factor, "volume": position["volume"],
                        "amount": amount})
            boundary += 86400

    def close(self, symbol, timestamp, price, reason, spread):
        position = self.positions.pop(symbol)
        pnl = position["direction"] * (price - position["entry_price"]) * position["value_per_price"]
        exit_burden = spread * position["value_per_price"]
        direction_extra = position["entry_spread_cost"] if position["direction"] == 1 else exit_burden
        mid_extra = (position["entry_spread_cost"] + exit_burden) / 2.0
        self.cash += pnl
        self.realized_year[day_year(timestamp)] += pnl
        # Entry-side burdens already accrued when the lifecycle started.
        self.extra_direction += exit_burden if position["direction"] == -1 else 0.0
        self.extra_mid += exit_burden / 2.0
        net = pnl + position["swap"]
        self.trades.append({**{key: position[key] for key in (
            "trade_id", "entry_time", "symbol", "direction", "entry_price", "stop", "volume",
            "original_stop_risk", "entry_event_sequence")},
            "exit_time": timestamp, "exit_price": price, "exit_reason": reason,
            "price_pnl": pnl, "swap": position["swap"], "positive_swap": position["positive_swap"],
            "actual_net": net, "direction_extra": direction_extra, "midpoint_extra": mid_extra,
            "direction_stressed_net": net - direction_extra,
            "midpoint_stressed_net": net - mid_extra,
            "no_positive_credit_stressed_net": net - direction_extra - position["positive_swap"]})

    def opening_exits(self, timestamp, present, events):
        for event in events:
            position = self.positions.get(event["symbol"])
            if position is not None:
                position["event_exit_pending"] = True
        for symbol in self.contract["symbols"]:
            position = self.positions.get(symbol)
            if position is None or symbol not in present:
                continue
            opening, high, low, close, spread = present[symbol]
            liquidation = opening if position["direction"] == 1 else opening + spread
            stop_hit = (liquidation <= position["stop"] if position["direction"] == 1
                        else liquidation >= position["stop"])
            if stop_hit:
                self.close(symbol, timestamp, liquidation, "GAP_STOP", spread)
            elif position["event_exit_pending"]:
                self.close(symbol, timestamp, liquidation, "NEXT_INTRINSIC_EVENT", spread)
            elif timestamp >= position["entry_time"] + self.contract["geometry"]["maximum_nominal_m1_minutes"] * 60:
                self.close(symbol, timestamp, liquidation, "TIMEOUT_FIRST_AVAILABLE", spread)

    def admit(self, timestamp, event, present, reference):
        if not event["entry_allowed"]:
            return
        symbol = event["symbol"]
        direction = role_direction(self.role, event)
        status, volume, stop_risk, trade_id = "ACCEPTED", 0.0, 0.0, 0
        risk = self.contract["risk"]
        spec = self.specs[symbol]
        if symbol not in present:
            status = "MISSING_EXACT_ENTRY_QUOTE"
        elif symbol in self.positions:
            status = "OWNED_POSITION_NOT_CLOSED"
        elif reference <= 0:
            status = "NONPOSITIVE_REFERENCE"
        else:
            opening, high, low, close, spread = present[symbol]
            entry = opening + spread if direction == 1 else opening
            tick = spec["trade_tick_size"]
            distance = self.contract["geometry"]["initial_stop_event_delta"] * event["trigger_delta"]
            stop = (math.floor((entry - distance) / tick + 1e-9) * tick if direction == 1
                    else math.ceil((entry + distance) / tick - 1e-9) * tick)
            per_lot_risk = abs(entry - stop) * spec["trade_contract_size"]
            valid_stop = stop < opening if direction == 1 else stop > opening + spread
            if not valid_stop or per_lot_risk <= 0:
                status = "STOP_NOT_BEYOND_LIQUIDATION"
            else:
                target = reference * risk["target_position_fraction"] / per_lot_risk
                step = spec["volume_step"]
                volume = math.floor(min(target, spec["volume_max"]) / step + 1e-12) * step
                volume = max(spec["volume_min"], round(volume, 10))
                stop_risk = volume * per_lot_risk
                if stop_risk > reference * risk["minimum_lot_hard_cap_fraction"] + 1e-9:
                    status = "MINIMUM_LOT_RISK_CAP"
                elif sum(p["original_stop_risk"] for p in self.positions.values()) + stop_risk > reference * risk["aggregate_original_stop_risk_fraction"] + 1e-9:
                    status = "AGGREGATE_RISK_CAP"
                else:
                    self.sequence += 1
                    trade_id = self.sequence
                    self.positions[symbol] = {
                        "trade_id": trade_id, "entry_time": timestamp, "symbol": symbol,
                        "direction": direction, "entry_price": entry, "stop": stop,
                        "volume": volume, "original_stop_risk": stop_risk,
                        "entry_event_sequence": event["event_sequence"],
                        "value_per_price": volume * spec["trade_contract_size"],
                        "entry_spread_cost": spread * volume * spec["trade_contract_size"],
                        "swap": 0.0, "positive_swap": 0.0, "event_exit_pending": False}
                    entry_burden = self.positions[symbol]["entry_spread_cost"]
                    self.extra_direction += entry_burden if direction == 1 else 0.0
                    self.extra_mid += entry_burden / 2.0
                    self.starts_year[str(day_year(timestamp))] += 1
                    self.starts_symbol[symbol] += 1
                    self.starts_direction[str(direction)] += 1
        self.admission_counts[status] += 1
        self.admission_writer.writerow([timestamp, symbol, event["event_sequence"], direction,
                                       status, trade_id, reference, volume, stop_risk])

    def step(self, timestamp, present, events):
        self.accrue_financing(timestamp)
        for symbol, (opening, high, low, close, spread) in present.items():
            self.marks[symbol] = (opening, opening + spread)
        # Record the risk already present at this opening before any exits.
        self.observe_dd(self.equity())
        self.opening_exits(timestamp, present, events)
        reference = min(self.cash, self.equity())
        for event in events:
            self.admit(timestamp, event, present, reference)
        opening_equity = self.equity()
        self.observe_dd(opening_equity)
        # Only now can current-bar high/low affect any trade.
        for symbol in self.contract["symbols"]:
            position = self.positions.get(symbol)
            if position is None or symbol not in present:
                continue
            opening, high, low, close, spread = present[symbol]
            hit = low <= position["stop"] if position["direction"] == 1 else high + spread >= position["stop"]
            if hit:
                self.close(symbol, timestamp, position["stop"], "INTRABAR_STOP", spread)
        for symbol, (opening, high, low, close, spread) in present.items():
            self.marks[symbol] = (close, close + spread)
        equity = self.equity()
        self.observe_dd(equity)
        valuations = [equity, equity - self.extra_direction, equity - self.extra_mid,
                      equity - self.extra_direction - self.positive_swap]
        self.year_end[day_year(timestamp)] = valuations
        self.equity_writer.writerow([timestamp, opening_equity, equity, self.cash,
                                     *valuations[1:], len(self.positions)])
        self.last_time = timestamp

    def finish(self, normal_dates, event_count):
        for handle in self.handles:
            handle.close()
        if self.positions:
            raise RuntimeError("Incomplete final closure; cannot judge economics")
        actual = self.cash - self.initial
        residuals = {
            "cash_minus_trade_net": actual - sum(t["actual_net"] for t in self.trades),
            "swap_tape_minus_trade_swap": sum(x["amount"] for x in self.financing) - sum(t["swap"] for t in self.trades),
            "direction_stress_minus_tape": self.extra_direction - sum(t["direction_extra"] for t in self.trades),
            "midpoint_stress_minus_tape": self.extra_mid - sum(t["midpoint_extra"] for t in self.trades),
            "positive_credit_minus_tape": self.positive_swap - sum(t["positive_swap"] for t in self.trades),
            "cash_minus_realized_epochs": actual - sum(self.realized_year.values())}
        if self.sequence != len(self.trades) or self.admission_counts["ACCEPTED"] != len(self.trades):
            raise RuntimeError("Start/full-close accounting mismatch")
        if sum(self.admission_counts.values()) != event_count or any(abs(x) > 1e-7 for x in residuals.values()):
            raise RuntimeError("Ordinary result accounting failed")
        for name, rows, empty_fields in (
            ("trades.csv", self.trades, ["trade_id"]),
            ("financing.csv", self.financing, ["time", "trade_id", "symbol", "rate", "factor", "volume", "amount"])):
            with (self.output / name).open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else empty_fields)
                writer.writeheader()
                writer.writerows(rows)
        previous = [self.initial] * 4
        epochs = {}
        for year in (2024, 2025):
            current = self.year_end[year]
            epochs[str(year)] = dict(zip(
                ["actual_marked_net", "direction_stressed_marked_net",
                 "midpoint_stressed_marked_net", "no_positive_credit_stressed_marked_net"],
                [a-b for a, b in zip(current, previous)]))
            epochs[str(year)]["realized_cash_net"] = self.realized_year[year]
            previous = current
        stress = [actual-self.extra_direction, actual-self.extra_mid,
                  actual-self.extra_direction-self.positive_swap]
        g = self.contract["development_gates"]
        gates = {
            "actual_profit": actual > g["actual_profit_strictly_above"],
            "all_stressed_profit": all(x > g["each_stressed_profit_series_strictly_above"] for x in stress),
            "all_marked_epochs_positive": all(value > 0 for data in epochs.values() for key, value in data.items() if key != "realized_cash_net"),
            "proxy_marked_drawdown": self.dd <= g["proxy_marked_equity_drawdown_pct_at_most"],
            "first_fill_density": len(self.trades)/normal_dates >= g["genuine_first_fills_per_normal_date_at_least"],
            "each_year_fill_count": all(self.starts_year[str(year)] >= g["genuine_first_fills_each_year_at_least"] for year in (2024, 2025)),
            "three_traded_symbols": len(self.starts_symbol) >= g["traded_symbols_at_least"],
            "both_directions": all(self.starts_direction[str(sign)] > 0 for sign in (-1, 1))}
        return {
            "role": self.role, "actual_net": actual,
            "direction_stressed_net": stress[0], "midpoint_stressed_net": stress[1],
            "no_positive_credit_stressed_net": stress[2], "proxy_marked_equity_drawdown_pct": self.dd,
            "first_fills": len(self.trades), "first_fills_per_normal_date": len(self.trades)/normal_dates,
            "normal_dates": normal_dates, "epochs": epochs, "starts_each_year": dict(self.starts_year),
            "starts_by_symbol": dict(self.starts_symbol), "starts_by_direction": dict(self.starts_direction),
            "admissions": dict(self.admission_counts), "exit_reasons": dict(Counter(t["exit_reason"] for t in self.trades)),
            "swap_net": sum(t["swap"] for t in self.trades), "positive_swap_credits": self.positive_swap,
            "direction_extra_spread": self.extra_direction, "midpoint_extra_spread": self.extra_mid,
            "accounting_residuals": residuals, "final_position_count": 0, "gates": gates,
            "complete_passer": all(gates.values()),
            "artifacts": [fingerprint(self.output/name) for name in ("admissions.csv", "equity.csv", "trades.csv", "financing.csv")]}


def main():
    cpath = FAMILY_ROOT/"config/contract.json"
    contract = json.loads(cpath.read_text(encoding="utf-8-sig"))
    artifact = REPO/"lab/artifacts/raw"/contract["family"]
    free = shutil.disk_usage(REPO).free
    if free - contract["initial_artifact_allowance_bytes"] < contract["storage_reserve_bytes"]:
        raise RuntimeError("Storage reserve")
    structural_path = FAMILY_ROOT/"evidence/STRUCTURAL_RESULT_V1.json"
    structural = json.loads(structural_path.read_text(encoding="utf-8-sig"))
    if not all(structural["necessary_gates"].values()):
        raise RuntimeError("No structural authority for economics")
    freeze = json.loads((FAMILY_ROOT/"evidence/ECONOMIC_IMPLEMENTATION_FREEZE_V1.json").read_text(encoding="utf-8-sig"))
    receipt = json.loads((FAMILY_ROOT/"evidence/INPUT_COPY_V1.json").read_text(encoding="utf-8-sig"))
    for item in freeze["files"] + structural["artifacts"]:
        if fingerprint(REPO/item["path"]) != item:
            raise RuntimeError("Frozen source or event identity mismatch")
    market, specs = {}, {}
    start, end = map(epoch, contract["periods"]["development"])
    for symbol in contract["symbols"]:
        for kind in ("market", "spec"):
            expected = receipt[kind][symbol]["copy"]
            if fingerprint(REPO/expected["path"]) != expected:
                raise RuntimeError("Owned input identity mismatch")
        spec = json.loads((artifact/"input/spec"/(symbol+"_SYMBOL_SPEC.json")).read_text(encoding="utf-8-sig"))
        if spec["swap_mode"] != 2 or any(spec[key] != "USD" for key in ("currency_base", "currency_profit")):
            raise RuntimeError("Unsupported native contract")
        rows = np.load(artifact/"input/market"/(symbol+"-M1.npy"), mmap_mode="r", allow_pickle=False)
        times = rows["time"]
        market[symbol] = rows[np.searchsorted(times, start):np.searchsorted(times, end)]
        if np.any(market[symbol]["spread"] < 0):
            raise RuntimeError("Invalid observed spread")
        specs[symbol] = spec
    events = defaultdict(list)
    with (artifact/"structural-v1/events.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            event = {key: (value if key == "symbol" else float(value)) for key, value in row.items()}
            for key in ("decision_time", "signal_bar_time", "event_sequence", "new_direction", "entry_allowed"):
                event[key] = int(event[key])
            events[event["decision_time"]].append(event)
    timeline = np.unique(np.concatenate([rows["time"] for rows in market.values()] + [np.array(list(events), dtype=np.int64)]))
    normal_dates = len(np.unique(np.concatenate([rows["time"]//86400 for rows in market.values()])))
    if normal_dates != structural["normal_dates"]:
        raise RuntimeError("All-source denominator drift")
    output = artifact/"development-v1"
    output.mkdir(exist_ok=False)
    results = []
    for role in contract["role_order"]:
        account = Account(role, contract, specs, output/role)
        indexes = {symbol: 0 for symbol in contract["symbols"]}
        for number, raw in enumerate(timeline):
            timestamp = int(raw)
            present = {}
            for symbol, rows in market.items():
                index = indexes[symbol]
                if index < len(rows) and int(rows[index]["time"]) == timestamp:
                    row = rows[index]
                    present[symbol] = (float(row["open"]), float(row["high"]), float(row["low"]),
                                       float(row["close"]), int(row["spread"])*specs[symbol]["point"])
                    indexes[symbol] += 1
            account.step(timestamp, present, events.get(timestamp, ()))
            if number % 100000 == 0:
                if shutil.disk_usage(REPO).free < contract["storage_reserve_bytes"]:
                    raise RuntimeError("Storage reserve correction required")
                print(json.dumps({"role": role, "completed_source_instants": number}), flush=True)
        result = account.finish(normal_dates, structural["optimistic_entry_events"])
        results.append(result)
        print(json.dumps({key: result[key] for key in ("role", "actual_net", "direction_stressed_net",
              "no_positive_credit_stressed_net", "proxy_marked_equity_drawdown_pct", "first_fills", "complete_passer")}), flush=True)
    passers = [x for x in results if x["complete_passer"]]
    passers.sort(key=lambda x: (-x["no_positive_credit_stressed_net"], x["proxy_marked_equity_drawdown_pct"],
        -min(e["no_positive_credit_stressed_marked_net"] for e in x["epochs"].values()), contract["role_order"].index(x["role"])))
    summary = {"schema": "zeta-ch013-complete-development-result-v1",
        "recorded_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "COMPLETE_PROXY_PASSER_REQUIRES_LOCKED_CONFIRMATION" if passers else "COMPLETE_VALID_ADVERSE_NO_PASSER",
        "contract": fingerprint(cpath), "adapter": fingerprint(Path(__file__)),
        "structural_result": fingerprint(structural_path), "normal_dates": normal_dates, "roles": results,
        "selected_unchanged_survivor": passers[0]["role"] if passers else None,
        "candidate_2026_price_opened": False, "EA_or_native_opened": False,
        "limits": contract["costs_and_proxy"], "historical_margin_limit": contract["risk"]["margin_limit"],
        "free_bytes_after": shutil.disk_usage(REPO).free}
    encoded = json.dumps(summary, indent=2, ensure_ascii=False)+"\n"
    (output/"summary.json").write_text(encoded, encoding="utf-8", newline="\n")
    evidence = FAMILY_ROOT/"evidence/DEVELOPMENT_RESULT_V1.json"
    if evidence.exists():
        raise RuntimeError("Refusing to overwrite economic evidence")
    evidence.write_text(encoded, encoding="utf-8", newline="\n")
    print(json.dumps({"status": summary["status"], "selected": summary["selected_unchanged_survivor"],
                      "free_gib": summary["free_bytes_after"]/1024**3}), flush=True)


if __name__ == "__main__":
    main()
