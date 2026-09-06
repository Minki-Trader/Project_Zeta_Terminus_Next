"""Normal frozen M1 economic stage for the unchanged CH012 impulse bundle."""

from collections import Counter, defaultdict
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from datetime import datetime, timezone
from pathlib import Path
import csv
import json
import math
import shutil

import numpy as np

from run_adapter import FAMILY, REPO, RAW, EPOCH, digest, record, day_number, day_label, write_json, write_csv


def protective_level(entry, sign, distance, tick, is_stop):
    desired = Decimal(str(entry)) + Decimal(sign * (-1 if is_stop else 1)) * Decimal(str(distance))
    rounding = ROUND_FLOOR if (is_stop and sign > 0) or (not is_stop and sign < 0) else ROUND_CEILING
    return float((desired / Decimal(str(tick))).to_integral_value(rounding=rounding) * Decimal(str(tick)))


class Portfolio:
    def __init__(self, role, contract, specs):
        self.role, self.c, self.specs = role, contract, specs
        self.cash = contract["risk"]["initial_deposit_usd"]
        self.owned, self.quotes = {}, {}
        self.actual_epoch, self.extra_epoch, self.mid_epoch = Counter(), Counter(), Counter()
        self.extra, self.mid_extra = 0.0, 0.0
        self.peak, self.max_dd_pct, self.max_dd_money = self.cash, 0.0, 0.0
        self.trades, self.admissions, self.equity, self.financing = [], [], [], []
        self.next_id = 1

    def cash_flow(self, amount, when):
        self.cash += amount
        self.actual_epoch[day_label(when // 86400)[:4]] += amount

    def cost_flow(self, extra, mid_extra, when):
        self.extra += extra
        self.mid_extra += mid_extra
        year = day_label(when // 86400)[:4]
        self.extra_epoch[year] += extra
        self.mid_epoch[year] += mid_extra

    def mark(self, when, phase):
        equity = self.cash
        for symbol, pos in self.owned.items():
            bid, spread = self.quotes[symbol]
            liquidation = bid if pos["sign"] > 0 else bid + spread
            equity += pos["sign"] * (liquidation - pos["entry_price"]) * pos["money_per_price"]
        self.peak = max(self.peak, equity)
        self.max_dd_money = max(self.max_dd_money, self.peak - equity)
        self.max_dd_pct = max(self.max_dd_pct, 100.0 * (self.peak - equity) / self.peak)
        self.equity.append({"raw_epoch": when, "phase": phase, "cash_usd": self.cash,
                            "equity_usd": equity, "open_positions": len(self.owned),
                            "original_stop_risk_usd": sum(p["original_risk"] for p in self.owned.values())})

    def roll(self, when):
        for symbol, pos in self.owned.items():
            spec = self.specs[symbol]
            while pos["next_roll"] <= when:
                boundary = pos["next_roll"]
                previous_day = EPOCH.fromordinal(EPOCH.toordinal() + boundary // 86400 - 1)
                if previous_day.weekday() < 5:
                    mql_weekday = (previous_day.weekday() + 1) % 7
                    multiplier = 3 if mql_weekday == int(spec["swap_rollover3days"]) else 1
                    quoted = spec["swap_long"] if pos["sign"] > 0 else spec["swap_short"]
                    amount = float(quoted) * pos["lots"] * multiplier
                    self.cash_flow(amount, boundary)
                    pos["swap_usd"] += amount
                    self.financing.append({"lifecycle_id": pos["id"], "symbol": symbol,
                                           "boundary_raw_epoch": boundary, "observed_global_raw_epoch": when,
                                           "multiplier": multiplier, "swap_usd": amount})
                pos["next_roll"] += 86400

    def close(self, symbol, price, spread, when, reason):
        pos = self.owned.pop(symbol)
        gross = pos["sign"] * (price - pos["entry_price"]) * pos["money_per_price"]
        exit_commission = self.c["costs_and_proxy"]["commission_usd_per_lot_per_side"] * pos["lots"]
        self.cash_flow(gross - exit_commission, when)
        exit_spread_money = spread * pos["money_per_price"]
        directional_exit_extra = exit_spread_money if pos["sign"] < 0 else 0.0
        self.cost_flow(directional_exit_extra, 0.5 * exit_spread_money, when)
        actual = gross + pos["swap_usd"] - pos["entry_commission"] - exit_commission
        extra = pos["directional_entry_extra"] + directional_exit_extra
        mid_extra = 0.5 * (pos["entry_spread_money"] + exit_spread_money)
        self.trades.append({"lifecycle_id": pos["id"], "symbol": symbol, "sign": pos["sign"],
                            "entry_raw_epoch": pos["entry_time"], "exit_proxy_raw_epoch": when,
                            "exit_reason": reason, "lots": pos["lots"], "entry_price": pos["entry_price"],
                            "exit_price": price, "original_stop": pos["stop"], "original_take": pos["take"],
                            "original_risk_usd": pos["original_risk"], "entry_atr14": pos["atr"],
                            "gross_usd": gross, "swap_usd": pos["swap_usd"],
                            "commission_usd": pos["entry_commission"] + exit_commission,
                            "extra_directional_spread_usd": extra, "extra_midquote_spread_usd": mid_extra,
                            "actual_usd": actual, "stressed_usd": actual - extra,
                            "midquote_stressed_usd": actual - mid_extra})

    def admit(self, impulse, current, when, batch_cash):
        symbol = impulse["symbol"]
        reason = None
        if symbol in self.owned:
            reason = "SYMBOL_OCCUPIED"
        elif symbol not in current:
            reason = "NO_EXACT_ENTRY_M1"
        elif batch_cash <= 0:
            reason = "NONPOSITIVE_CASH"
        entry, stop, take, lots, original_risk = None, None, None, None, None
        sign = int(impulse[self.role])
        if reason is None:
            spec = self.specs[symbol]
            bar = current[symbol]
            spread = float(bar["spread"]) * spec["point"]
            entry = round(float(bar["open"]) + (spread if sign > 0 else 0.0), spec["digits"])
            atr = float(impulse["prior_atr14"])
            stop = protective_level(entry, sign, self.c["geometry"]["initial_stop_prior_atr"] * atr,
                                    spec["trade_tick_size"], True)
            take = protective_level(entry, sign, self.c["geometry"]["initial_take_prior_atr"] * atr,
                                    spec["trade_tick_size"], False)
            unit_risk = abs(entry - stop) * spec["trade_contract_size"]
            if not math.isfinite(unit_risk) or unit_risk <= 0:
                raise ValueError("Invalid original stop risk")
            risk = self.c["risk"]
            target = batch_cash * risk["target_position_fraction"] / unit_risk
            steps = math.floor(min(target, spec["volume_max"]) / spec["volume_step"] + 1e-10)
            lots = round(max(spec["volume_min"], steps * spec["volume_step"]), 8)
            original_risk = lots * unit_risk
            if original_risk > batch_cash * risk["minimum_lot_hard_cap_fraction"] + 1e-9:
                reason = "MINIMUM_LOT_RISK_CAP"
            elif original_risk + sum(p["original_risk"] for p in self.owned.values()) > batch_cash * risk["aggregate_original_stop_risk_fraction"] + 1e-9:
                reason = "AGGREGATE_ORIGINAL_RISK_CAP"
            else:
                money_per_price = lots * spec["trade_contract_size"]
                entry_spread_money = spread * money_per_price
                directional_extra = entry_spread_money if sign > 0 else 0.0
                commission = self.c["costs_and_proxy"]["commission_usd_per_lot_per_side"] * lots
                self.cash_flow(-commission, when)
                self.cost_flow(directional_extra, 0.5 * entry_spread_money, when)
                self.owned[symbol] = {"id": self.next_id, "sign": sign, "entry_time": when,
                                      "entry_price": entry, "stop": stop, "take": take,
                                      "lots": lots, "original_risk": original_risk, "atr": atr,
                                      "money_per_price": money_per_price, "swap_usd": 0.0,
                                      "next_roll": (when // 86400 + 1) * 86400,
                                      "due": when + self.c["geometry"]["maximum_completed_m30_intervals"] * self.c["signal"]["bar_seconds"],
                                      "entry_commission": commission, "entry_spread_money": entry_spread_money,
                                      "directional_entry_extra": directional_extra}
                self.next_id += 1
                reason = "ACCEPTED"
        self.admissions.append({"symbol": symbol, "decision_raw_epoch": when, "sign": sign,
                                "decision": reason, "batch_cash_usd": batch_cash, "entry_price": entry,
                                "original_stop": stop, "original_take": take, "lots": lots,
                                "original_stop_risk_usd": original_risk})

    def step(self, when, current, impulses):
        self.roll(when)
        for symbol, bar in current.items():
            self.quotes[symbol] = (float(bar["open"]), float(bar["spread"]) * self.specs[symbol]["point"])
        # All opening exits precede one common admission cash snapshot.
        for symbol in list(self.owned):
            if symbol not in current:
                continue
            pos = self.owned[symbol]
            bid, spread = self.quotes[symbol]
            price = bid if pos["sign"] > 0 else round(bid + spread, self.specs[symbol]["digits"])
            adverse_gap = (price <= pos["stop"]) if pos["sign"] > 0 else (price >= pos["stop"])
            favorable_gap = (price >= pos["take"]) if pos["sign"] > 0 else (price <= pos["take"])
            if adverse_gap:
                self.close(symbol, price, spread, when, "GAP_STOP")
            elif favorable_gap:
                self.close(symbol, pos["take"], spread, when, "GAP_TAKE_CAPPED")
            elif when >= pos["due"]:
                self.close(symbol, price, spread, when, "FOUR_M30_TIME")
        self.mark(when, "OPEN_AFTER_EXITS")
        batch_cash = self.cash
        for impulse in impulses:
            self.admit(impulse, current, when, batch_cash)
        if impulses:
            self.mark(when, "OPEN_AFTER_ADMISSIONS")
        # No further entry or sizing occurs after any current-minute high/low.
        for symbol in list(self.owned):
            if symbol not in current:
                continue
            pos, bar = self.owned[symbol], current[symbol]
            spread = self.quotes[symbol][1]
            addition = spread if pos["sign"] < 0 else 0.0
            high, low = float(bar["high"]) + addition, float(bar["low"]) + addition
            stopped = low <= pos["stop"] if pos["sign"] > 0 else high >= pos["stop"]
            taken = high >= pos["take"] if pos["sign"] > 0 else low <= pos["take"]
            if stopped:
                self.close(symbol, pos["stop"], spread, when + 59,
                           "M1_STOP_AMBIGUOUS_STOP_FIRST" if taken else "M1_STOP")
            elif taken:
                self.close(symbol, pos["take"], spread, when + 59, "M1_TAKE")
        for symbol, bar in current.items():
            self.quotes[symbol] = (float(bar["close"]), float(bar["spread"]) * self.specs[symbol]["point"])
        self.mark(when + 60, "M1_CLOSE")

    def finish(self, output, normal_dates, total_impulses):
        initial = self.c["risk"]["initial_deposit_usd"]
        counts = Counter(x["decision"] for x in self.admissions)
        actual = self.cash - initial
        integrity = {"all_flat": not self.owned,
                     "every_impulse_decided": len(self.admissions) == total_impulses,
                     "accepted_equals_unique_closed": counts["ACCEPTED"] == len(self.trades) == len({x["lifecycle_id"] for x in self.trades}),
                     "cash_reconciles": abs(actual - sum(x["actual_usd"] for x in self.trades)) < 1e-7,
                     "directional_spread_reconciles": abs(self.extra - sum(x["extra_directional_spread_usd"] for x in self.trades)) < 1e-7,
                     "midquote_spread_reconciles": abs(self.mid_extra - sum(x["extra_midquote_spread_usd"] for x in self.trades)) < 1e-7,
                     "cash_epochs_reconcile": abs(actual - sum(self.actual_epoch.values())) < 1e-7}
        if not all(integrity.values()):
            raise RuntimeError(f"Incomplete ordinary economic result: {integrity}")
        yearly = {y: {"actual_usd": self.actual_epoch[y],
                       "stressed_usd": self.actual_epoch[y] - self.extra_epoch[y],
                       "midquote_stressed_usd": self.actual_epoch[y] - self.mid_epoch[y],
                       "first_fills": sum(day_label(x["entry_raw_epoch"] // 86400).startswith(y) for x in self.trades)}
                  for y in ("2024", "2025")}
        density = len(self.trades) / normal_dates
        g = self.c["development_gates"]
        gates = {"actual_profit": actual > g["actual_profit_strictly_above"],
                 "both_stressed_profits": min(actual - self.extra, actual - self.mid_extra) > g["both_stressed_profit_series_strictly_above"],
                 "each_epoch_positive_actual_and_both_stressed": all(min(y["actual_usd"], y["stressed_usd"], y["midquote_stressed_usd"]) > 0 for y in yearly.values()),
                 "marked_equity_drawdown": self.max_dd_pct <= g["proxy_marked_equity_drawdown_pct_at_most"],
                 "genuine_first_fill_turnover": density >= g["genuine_first_fills_per_normal_date_at_least"],
                 "yearly_first_fill_count": all(y["first_fills"] >= g["genuine_first_fills_each_year_at_least"] for y in yearly.values()),
                 "three_symbol_breadth": len({x["symbol"] for x in self.trades}) >= g["traded_symbols_at_least"],
                 "both_directions": {x["sign"] for x in self.trades} == {-1, 1}}
        output.mkdir(parents=True, exist_ok=False)
        write_csv(output / "admissions.csv", ["symbol", "decision_raw_epoch", "sign", "decision", "batch_cash_usd", "entry_price", "original_stop", "original_take", "lots", "original_stop_risk_usd"], self.admissions)
        trade_fields = ["lifecycle_id", "symbol", "sign", "entry_raw_epoch", "exit_proxy_raw_epoch", "exit_reason", "lots", "entry_price", "exit_price", "original_stop", "original_take", "original_risk_usd", "entry_atr14", "gross_usd", "swap_usd", "commission_usd", "extra_directional_spread_usd", "extra_midquote_spread_usd", "actual_usd", "stressed_usd", "midquote_stressed_usd"]
        write_csv(output / "trades.csv", trade_fields, self.trades)
        write_csv(output / "equity.csv", ["raw_epoch", "phase", "cash_usd", "equity_usd", "open_positions", "original_stop_risk_usd"], self.equity)
        write_csv(output / "financing.csv", ["lifecycle_id", "symbol", "boundary_raw_epoch", "observed_global_raw_epoch", "multiplier", "swap_usd"], self.financing)
        return {"role": self.role, "actual_usd": actual, "stressed_usd": actual - self.extra,
                "midquote_stressed_usd": actual - self.mid_extra, "extra_directional_spread_usd": self.extra,
                "extra_midquote_spread_usd": self.mid_extra, "swap_usd": sum(x["swap_usd"] for x in self.trades),
                "marked_equity_drawdown_pct": self.max_dd_pct, "marked_equity_max_drawdown_usd": self.max_dd_money,
                "proxy_stressed_profit_over_actual_marked_max_drawdown_money": (actual - self.extra) / self.max_dd_money if self.max_dd_money else None,
                "normal_dates": normal_dates, "first_fills": len(self.trades), "first_fills_per_normal_date": density,
                "yearly": yearly, "admission_counts": dict(counts),
                "symbol_first_fills": dict(Counter(x["symbol"] for x in self.trades)),
                "direction_first_fills": dict(Counter(str(x["sign"]) for x in self.trades)),
                "exit_reasons": dict(Counter(x["exit_reason"] for x in self.trades)),
                "integrity": integrity, "gates": gates, "passes_all_development_gates": all(gates.values()),
                "artifacts": [record(output / n) for n in ("admissions.csv", "trades.csv", "equity.csv", "financing.csv")]}


def main():
    contract_path = FAMILY / "config" / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    freeze_path = FAMILY / "evidence" / "ECONOMIC_IMPLEMENTATION_FREEZE_V1.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if shutil.disk_usage(REPO).free < contract["storage_reserve_bytes"] + contract["initial_artifact_allowance_bytes"]:
        raise RuntimeError("Preserve 30 GiB reserve plus the complete output allowance")
    for item in freeze["bound_files"]:
        path = REPO / item["path"]
        if path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
            raise RuntimeError(f"Changed frozen economic input/source: {item['path']}")
    receipt = json.loads((FAMILY / "evidence/INPUT_COPY_V1.json").read_text(encoding="utf-8"))
    for item in receipt["inputs"]:
        path = (REPO / item["path"]).resolve()
        if not path.is_relative_to((RAW / "input").resolve()) or digest(path) != item["sha256"]:
            raise RuntimeError("Changed or cross-root physical input")
    source_result = json.loads((RAW / "structural-final/summary.json").read_text(encoding="utf-8"))
    if not source_result["economic_stage_authorized_by_structural_gates"]:
        raise RuntimeError("Fixed structural gate did not permit economic work")
    with (RAW / "structural-final/impulses.csv").open(encoding="utf-8", newline="") as stream:
        impulses = list(csv.DictReader(stream))
    by_time = defaultdict(list)
    for impulse in impulses:
        by_time[int(impulse["decision_raw_epoch"])].append(impulse)
    for bundle in by_time.values():
        bundle.sort(key=lambda x: x["priority"])
    begin = day_number(contract["periods"]["development"][0]) * 86400
    end = day_number(contract["periods"]["development"][1]) * 86400
    markets, specs = {}, {}
    for symbol in contract["symbols"]:
        rates = np.load(RAW / "input/market" / f"{symbol}-M1.npy", mmap_mode="r", allow_pickle=False)
        start = int(np.searchsorted(rates["time"], begin))
        markets[symbol] = rates[start:]
        if int(markets[symbol]["time"][-1]) >= end:
            raise RuntimeError("Locked price observation in development input")
        spec = json.loads((RAW / "input/spec" / f"{symbol}_SYMBOL_SPEC.json").read_text(encoding="utf-8-sig"))
        if spec["currency_base"] != "USD" or spec["currency_profit"] != "USD" or spec["swap_mode"] != 2:
            raise RuntimeError("Snapshot outside frozen USD money/financing semantics")
        specs[symbol] = spec
    timeline = np.unique(np.concatenate([x["time"] for x in markets.values()] + [np.array(list(by_time), dtype=np.int64)]))
    lookup = {symbol: np.searchsorted(rates["time"], timeline) for symbol, rates in markets.items()}
    output = RAW / "development-final"
    if output.exists():
        raise RuntimeError("Preserve an existing economic output; never overwrite a judged path")
    results = []
    for role in contract["role_order"]:
        portfolio = Portfolio(role, contract, specs)
        portfolio.mark(begin, "INITIAL")
        for k, raw_time in enumerate(timeline):
            when = int(raw_time)
            at_time = by_time.get(when, ())
            if not portfolio.owned and not at_time:
                continue
            current = {}
            for symbol, rates in markets.items():
                index = int(lookup[symbol][k])
                if index < len(rates) and int(rates["time"][index]) == when:
                    current[symbol] = rates[index]
            portfolio.step(when, current, at_time)
        if portfolio.owned:
            raise RuntimeError("Incomplete natural closure at fixed period end")
        portfolio.mark(end, "FINAL_FLAT")
        results.append(portfolio.finish(output / role, source_result["normal_dates"], len(impulses)))
    passing = [x for x in results if x["passes_all_development_gates"]]
    passing.sort(key=lambda x: (-x["stressed_usd"], x["marked_equity_drawdown_pct"],
                                -min(y["stressed_usd"] for y in x["yearly"].values()), contract["role_order"].index(x["role"])))
    summary = {"schema": "zeta-ch012-complete-fixed-two-role-development-result-v1",
               "recorded_utc": datetime.now(timezone.utc).isoformat(), "family_number": 12,
               "status": "COMPLETE_PROXY_SURVIVOR_CONFIRMATION_AUTHORITY_PENDING" if passing else "COMPLETE_VALID_PROXY_ADVERSE_BUNDLE_NO_PASSER",
               "economic_freeze": record(freeze_path), "contract": record(contract_path),
               "roles": results, "selected_role": passing[0]["role"] if passing else None,
               "valid_economic_roles_completed": len(results), "2026_candidate_outcomes_opened": False,
               "EA_or_MT5_opened": False, "native_V8_victory": False,
               "limits": freeze["proxy_execution_limits"], "storage_free_bytes": shutil.disk_usage(REPO).free,
               "storage_reserve_bytes": contract["storage_reserve_bytes"]}
    write_json(output / "summary.json", summary)
    print(json.dumps({"status": summary["status"], "selected_role": summary["selected_role"],
                      "roles": [{k: x[k] for k in ("role", "actual_usd", "stressed_usd", "midquote_stressed_usd",
                                 "marked_equity_drawdown_pct", "first_fills", "first_fills_per_normal_date", "yearly", "gates", "integrity")} for x in results],
                      "free_gib": summary["storage_free_bytes"] / 2**30}, indent=2))


if __name__ == "__main__":
    main()
