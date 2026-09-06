"""Causal repo-conditioned M30 impulse producer for the frozen CH012 bundle.

This normal adapter stage produces decisions for both proposed EA directions.
It never measures forward returns or equates its optimistic supply with fills.
"""

from bisect import bisect_right
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import csv
import json
import shutil

import numpy as np


FAMILY = Path(__file__).resolve().parents[1]
REPO = FAMILY.parents[2]
RAW = REPO / "lab" / "artifacts" / "raw" / FAMILY.name
EPOCH = date(1970, 1, 1)


def digest(path):
    with path.open("rb") as source:
        return sha256(source.read()).hexdigest().upper()


def record(path):
    return {"path": path.relative_to(REPO).as_posix(),
            "bytes": path.stat().st_size, "sha256": digest(path)}


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")


def day_number(label):
    return (date.fromisoformat(label) - EPOCH).days


def day_label(number):
    return (EPOCH + timedelta(days=int(number))).isoformat()


def raw_label(value):
    return (datetime(1970, 1, 1) + timedelta(seconds=int(value))).isoformat()


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_repo_observations(path, contract):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        original = list(csv.DictReader(stream))
    prior_count = contract["prior_source_dates"]
    delay = contract["availability_delay_calendar_days"]
    values, rows, availability = [], [], []
    last_day = None
    for source in original:
        effective_day = day_number(source["effective_date"])
        if last_day is not None and effective_day <= last_day:
            raise ValueError("Nonmonotone or duplicate repo effective date")
        last_day = effective_day
        basis = int(source["sofr_rate_bp"]) - int(source["tgcr_rate_bp"])
        median_twice = None
        if len(values) >= prior_count:
            ordered = sorted(values[-prior_count:])
            median_twice = ordered[prior_count // 2 - 1] + ordered[prior_count // 2]
        deviation_twice = None if median_twice is None else 2 * basis - median_twice
        rows.append({"effective_day": effective_day, "basis_bp": basis,
                     "median_twice_bp": median_twice,
                     "deviation_twice_bp": deviation_twice})
        availability.append(effective_day + delay)
        values.append(basis)
    return availability, rows


def market_impulses(path, symbol, contract, availability, repo_rows):
    rates = np.load(path, mmap_mode="r", allow_pickle=False)
    times = rates["time"]
    begin = day_number(contract["periods"]["development"][0]) * 86400
    end = day_number(contract["periods"]["development"][1]) * 86400
    warmup = day_number(contract["periods"]["warmup"][0]) * 86400
    cutoff = end - contract["periods"]["new_entry_cutoff_calendar_days_before_end"] * 86400
    if len(times) == 0 or int(times[0]) < warmup or int(times[-1]) >= end:
        raise ValueError(f"{symbol}: input outside frozen warmup/development")
    if np.any(np.diff(times) <= 0) or np.any(times % 60):
        raise ValueError(f"{symbol}: duplicate/nonmonotone/non-M1 source")
    prices = [rates[name] for name in ("open", "high", "low", "close")]
    if any(np.any(~np.isfinite(x)) or np.any(x <= 0) for x in prices):
        raise ValueError(f"{symbol}: invalid source price")
    op, hi, lo, cl = prices
    if (np.any(hi < np.maximum(op, cl)) or np.any(lo > np.minimum(op, cl))
            or np.any(hi < lo) or np.any(rates["spread"] < 0)):
        raise ValueError(f"{symbol}: inconsistent OHLC/spread")

    source_days = set(map(int, np.unique(times[(times >= begin) & (times < end)] // 86400)))
    seconds = contract["signal"]["bar_seconds"]
    buckets, first, count = np.unique(times // seconds, return_index=True, return_counts=True)
    last = first + count - 1
    full = ((count == seconds // 60) & (times[first] == buckets * seconds)
            & (times[last] == buckets * seconds + seconds - 60)
            & (np.minimum.reduceat(rates["tick_volume"], first) > 0))
    bar_time = buckets[full] * seconds
    bar_open = op[first[full]].astype(float)
    bar_close = cl[last[full]].astype(float)
    bar_high = np.maximum.reduceat(hi, first)[full]
    bar_low = np.minimum.reduceat(lo, first)[full]
    if len(bar_time) <= contract["signal"]["atr_bars"]:
        raise ValueError(f"{symbol}: insufficient complete M30 warmup")
    tr = bar_high - bar_low
    tr[1:] = np.maximum(tr[1:], np.maximum(np.abs(bar_high[1:] - bar_close[:-1]),
                                         np.abs(bar_low[1:] - bar_close[:-1])))
    cumulative = np.concatenate(([0.0], np.cumsum(tr, dtype=float)))
    lookback = contract["signal"]["atr_bars"]
    prior_atr = np.full(len(tr), np.nan)
    indices = np.arange(lookback, len(tr))
    prior_atr[indices] = (cumulative[indices] - cumulative[indices - lookback]) / lookback
    decision_time = bar_time + seconds
    body = bar_close - bar_open
    eligible = ((decision_time >= begin) & (decision_time < cutoff)
                & np.isfinite(prior_atr) & (prior_atr > 0)
                & (np.abs(body) >= contract["signal"]["minimum_body_prior_atr"] * prior_atr)
                & (body != 0))
    signals = []
    reasons = Counter()
    max_age = contract["repo"]["maximum_effective_date_age_calendar_days"]
    for i in np.flatnonzero(eligible):
        when = int(decision_time[i])
        day = when // 86400
        source_index = bisect_right(availability, day) - 1
        if source_index < 0:
            reasons["repo_not_available"] += 1
            continue
        source = repo_rows[source_index]
        age = day - source["effective_day"]
        deviation = source["deviation_twice_bp"]
        if age > max_age:
            reasons["repo_stale"] += 1
            continue
        if deviation is None:
            reasons["repo_median_warmup"] += 1
            continue
        if deviation == 0:
            reasons["repo_tied"] += 1
            continue
        sign = 1 if body[i] > 0 else -1
        if (deviation > 0 and sign > 0) or (deviation < 0 and sign < 0):
            reasons["shock_repo_sign_mismatch"] += 1
            continue
        entry_index = int(np.searchsorted(times, when))
        has_entry_minute = entry_index < len(times) and int(times[entry_index]) == when
        # Availability is disclosed, never used to suppress the optimistic bound.
        signals.append({
            "symbol": symbol, "decision_raw_epoch": when, "decision_broker_label": raw_label(when),
            "shock_bar_raw_epoch": int(bar_time[i]), "shock_body": float(body[i]),
            "prior_atr14": float(prior_atr[i]), "shock_body_prior_atr": float(body[i] / prior_atr[i]),
            "repo_effective_date": day_label(source["effective_day"]), "repo_age_calendar_days": age,
            "repo_basis_bp": source["basis_bp"], "repo_prior20_median_twice_bp": source["median_twice_bp"],
            "repo_deviation_twice_bp": deviation, "SHOCK_PROPAGATION": sign, "SHOCK_REVERSAL": -sign,
            "original_stop_distance": float(contract["geometry"]["initial_stop_prior_atr"] * prior_atr[i]),
            "original_take_distance": float(contract["geometry"]["initial_take_prior_atr"] * prior_atr[i]),
            "exact_entry_minute_observed": int(has_entry_minute),
            "priority": sha256(f"ZT-CH012-PRIORITY-V1|{when}|{symbol}".encode("ascii")).hexdigest()
        })
        reasons["qualifying_impulse"] += 1
    meta = {
        "symbol": symbol, "input_rows": len(times), "first_broker_label": raw_label(times[0]),
        "last_broker_label": raw_label(times[-1]), "normal_source_dates": len(source_days),
        "observed_m30_buckets": len(buckets), "complete_m30_bars": int(np.sum(full)),
        "incomplete_m30_buckets": int(np.sum(~full)),
        "completed_development_shocks_before_repo_condition": int(np.sum(eligible)),
        "source_condition_counts": dict(reasons), "impulses": len(signals),
        "impulses_without_exact_entry_minute": sum(1 - x["exact_entry_minute_observed"] for x in signals),
        "forward_returns_or_trade_paths_computed": False
    }
    return signals, source_days, meta


def main():
    contract_path = FAMILY / "config" / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if shutil.disk_usage(REPO).free < contract["storage_reserve_bytes"] + 64 * 1024 * 1024:
        raise RuntimeError("Insufficient 30 GiB reserve plus bounded output allowance")
    freeze_path = FAMILY / "evidence" / "STRUCTURAL_IMPLEMENTATION_FREEZE_V1.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    for item in freeze["bound_files"]:
        path = REPO / item["path"]
        if path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
            raise RuntimeError(f"Changed frozen source/contract: {item['path']}")
    receipt_path = FAMILY / "evidence" / "INPUT_COPY_V1.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    own_input = (RAW / "input").resolve()
    for item in receipt["inputs"]:
        path = (REPO / item["path"]).resolve()
        if not path.is_relative_to(own_input):
            raise RuntimeError("Cross-root input prohibited")
        if path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
            raise RuntimeError(f"Changed input: {item['path']}")
    output = RAW / "structural-final"
    if output.exists():
        raise RuntimeError("Preserved output already exists; do not overwrite a judged run")
    availability, repo_rows = load_repo_observations(
        RAW / "input" / "repo" / "HEADLINE_BASIS_SOURCE_TABLE_V1.csv", contract["repo"])
    signals, days, coverage = [], set(), []
    for symbol in contract["symbols"]:
        found, source_days, meta = market_impulses(
            RAW / "input" / "market" / f"{symbol}-M1.npy", symbol, contract, availability, repo_rows)
        signals.extend(found)
        days.update(source_days)
        coverage.append(meta)
    signals.sort(key=lambda x: (x["decision_raw_epoch"], x["priority"]))
    counts = Counter(x["decision_raw_epoch"] // 86400 for x in signals)
    years = {}
    for year in (2024, 2025):
        ndays = sum(day_label(d).startswith(str(year)) for d in days)
        impulses = sum(day_label(x["decision_raw_epoch"] // 86400).startswith(str(year)) for x in signals)
        years[str(year)] = {"normal_dates": ndays, "optimistic_impulses": impulses,
                            "optimistic_impulses_per_normal_date": impulses / ndays if ndays else 0}
    n = len(signals)
    density = n / len(days) if days else 0
    stage = contract["structural_stage"]
    gates = {
        "optimistic_supply_at_least_three_per_normal_date": density >= stage["minimum_optimistic_impulses_per_normal_date"],
        "optimistic_yearly_count": all(y["optimistic_impulses"] >= stage["minimum_optimistic_impulses_each_year"] for y in years.values()),
        "symbol_breadth": len({x["symbol"] for x in signals}) >= stage["minimum_symbols_with_impulses"],
        "both_shock_signs": {x["SHOCK_PROPAGATION"] for x in signals} == {-1, 1}
    }
    output.mkdir(parents=True, exist_ok=False)
    signal_fields = ["symbol", "decision_raw_epoch", "decision_broker_label", "shock_bar_raw_epoch",
                     "shock_body", "prior_atr14", "shock_body_prior_atr", "repo_effective_date",
                     "repo_age_calendar_days", "repo_basis_bp", "repo_prior20_median_twice_bp",
                     "repo_deviation_twice_bp", "SHOCK_PROPAGATION", "SHOCK_REVERSAL",
                     "original_stop_distance", "original_take_distance", "exact_entry_minute_observed", "priority"]
    write_csv(output / "impulses.csv", signal_fields, signals)
    day_rows = [{"broker_date": day_label(d), "normal_source_date": int(d in days),
                 "optimistic_impulses": counts[d]} for d in sorted(days | set(counts))]
    write_csv(output / "normal-days.csv", ["broker_date", "normal_source_date", "optimistic_impulses"], day_rows)
    write_json(output / "market-source-summary.json", coverage)
    summary = {
        "schema": "zeta-ch012-causal-impulse-structural-result-v1",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "family_number": 12, "primary_macro_program": 2,
        "status": "STRUCTURALLY_FEASIBLE_ECONOMICS_PENDING" if all(gates.values()) else "STRUCTURALLY_INFEASIBLE_FROZEN_BUNDLE_NO_ECONOMICS",
        "contract": record(contract_path), "implementation_freeze": record(freeze_path),
        "input_copy_receipt": record(receipt_path), "normal_dates": len(days),
        "optimistic_impulses_per_role": n, "optimistic_impulses_per_normal_date": density,
        "required_optimistic_impulses": stage["minimum_optimistic_impulses_per_normal_date"] * len(days),
        "yearly": years, "symbols": dict(Counter(x["symbol"] for x in signals)),
        "shock_signs": dict(Counter(str(x["SHOCK_PROPAGATION"]) for x in signals)),
        "normal_dates_without_impulses": sum(counts[d] == 0 for d in days),
        "normal_dates_below_three_impulses": sum(counts[d] < 3 for d in days),
        "impulses_on_non_source_dates": sum(counts[d] for d in counts if d not in days),
        "impulses_without_exact_entry_minute": sum(1 - x["exact_entry_minute_observed"] for x in signals),
        "gates": gates, "economic_stage_authorized_by_structural_gates": all(gates.values()),
        "interpretation": "Optimistic impulse supply is an upper bound on genuine first fills. Overlap, volume, risk, margin and unavailable-entry losses can only reduce executable supply. No monetary or raw-alpha conclusion follows.",
        "forward_return_or_stop_take_or_profit_computed": False,
        "locked_2026_price_input_present": False, "EA_or_MT5_opened": False,
        "artifacts": [record(output / name) for name in ("impulses.csv", "normal-days.csv", "market-source-summary.json")],
        "storage_free_bytes": shutil.disk_usage(REPO).free,
        "storage_reserve_bytes": contract["storage_reserve_bytes"]
    }
    write_json(output / "summary.json", summary)
    print(json.dumps({key: summary[key] for key in ("status", "normal_dates", "optimistic_impulses_per_role",
                     "optimistic_impulses_per_normal_date", "yearly", "gates", "storage_free_bytes")}, indent=2))


if __name__ == "__main__":
    main()
