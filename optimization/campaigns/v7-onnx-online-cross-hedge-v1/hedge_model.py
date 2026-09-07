"""Produce causal native-price beta estimates and protected hedge selection.

The standalone quote approximation cannot establish candidate account economics.
"""
from collections import Counter
from pathlib import Path
import csv
import datetime as dt
import hashlib
import json
import math
import shutil

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper
import onnxruntime as ort

FAMILY = Path(__file__).resolve().parent
ROOT = FAMILY.parents[2]
RAW = ROOT / "optimization/artifacts/raw/v7-onnx-online-cross-hedge-v1"
CROSS_ID = "ZT-H1-US100-CROSS-IN-14b72317b7"


def epoch(text):
    return int(np.datetime64(text, "s").astype(np.int64))


def server(text):
    return int(dt.datetime.strptime(text, "%Y.%m.%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def csv_save(path, rows):
    if not rows:
        raise RuntimeError("Empty required production tape")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def hourly_inputs():
    market, hourly = {}, {}
    for symbol in ("US100", "US500"):
        a = np.load(RAW / "input" / f"{symbol}-M1-202312-202512.npy", mmap_mode="r")
        if np.any(np.diff(a["time"]) <= 0):
            raise RuntimeError("Native ordering correction required")
        groups = a["time"] // 3600 * 3600
        first = np.r_[0, np.flatnonzero(np.diff(groups)) + 1]
        last = np.r_[first[1:] - 1, len(a) - 1]
        market[symbol] = a
        hourly[symbol] = {int(t): float(c) for t, c in zip(groups[first], a["close"][last])}
    samples, population = [], []
    for t in sorted(hourly["US100"]):
        if not epoch("2024-01-01") <= t < epoch("2026-01-01"):
            continue
        complete = all(t in hourly[s] and t - 3600 in hourly[s] for s in hourly)
        population.append({"bar": t, "end": t + 3600, "year": 2024 if t < epoch("2025-01-01") else 2025,
                           "status": "COMPLETE_PAIRED_RETURN" if complete else "MISSING_CONSECUTIVE_PAIRED_H1"})
        if not complete:
            continue
        values = [hourly[s][u] for s in hourly for u in (t - 3600, t)]
        if any(not math.isfinite(v) or v <= 0 for v in values):
            raise RuntimeError("Invalid native close")
        samples.append({"bar": t, "end": t + 3600,
                        "r100": math.log(hourly["US100"][t] / hourly["US100"][t - 3600]),
                        "r500": math.log(hourly["US500"][t] / hourly["US500"][t - 3600])})
    csv_save(RAW / "hourly-population.csv", population)
    return market, hourly, samples, Counter(r["status"] for r in population)


def graph_session():
    specs = [helper.make_tensor_value_info(name, TensorProto.FLOAT, [1, 1])
             for name in ("covariance", "variance", "notional_ratio")]
    outputs = [helper.make_tensor_value_info(name, TensorProto.FLOAT, [1, 1]) for name in ("beta", "lots")]
    constants = [numpy_helper.from_array(np.array(value, dtype=np.float32), name)
                 for name, value in (("lower", .25), ("upper", 3.0), ("fraction", .5))]
    nodes = [helper.make_node("Div", ["covariance", "variance"], ["raw_beta"]),
             helper.make_node("Clip", ["raw_beta", "lower", "upper"], ["beta"]),
             helper.make_node("Mul", ["beta", "notional_ratio"], ["full_lots"]),
             helper.make_node("Mul", ["full_lots", "fraction"], ["lots"])]
    model = helper.make_model(helper.make_graph(nodes, "V7CommonMarketHedge", specs, outputs, constants),
                              producer_name="v7-cross-hedge", opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8
    path = FAMILY / "models/hedge-beta.onnx"
    path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, path)
    return ort.InferenceSession(str(path), providers=["CPUExecutionProvider"]), path


def infer(session, xy, xx, ratio):
    if xx <= 0 or not all(math.isfinite(v) for v in (xy, xx, ratio)):
        raise RuntimeError("Invalid own moment state")
    result = session.run(None, {name: np.array([[value]], dtype=np.float32)
                        for name, value in (("covariance", xy), ("variance", xx), ("notional_ratio", ratio))})
    beta, lots = (float(r[0, 0]) for r in result)
    if not math.isfinite(beta) or not math.isfinite(lots):
        raise RuntimeError("Nonfinite ONNX inference")
    return beta, lots


def parent_rows():
    births, closes = {}, {}
    with (RAW / "input/original-lifecycles-2024-2025.csv").open(encoding="utf-8", newline="") as handle:
        for r in csv.DictReader(handle):
            if r["component_id"] != CROSS_ID or not r["entry_time_server"].startswith("2025."):
                continue
            dest = births if r["event"] == "BIRTH" else closes
            identity = r["position_identifier"]
            if identity in dest:
                raise RuntimeError("Duplicate original lifecycle endpoint")
            dest[identity] = r
    if set(births) != set(closes):
        raise RuntimeError("Original lifecycle endpoint population requires correction")
    return [(b, closes[key]) for key, b in sorted(births.items(), key=lambda pair: pair[1]["entry_time_server"])]


def hedge_quote(role, birth, close, moments, session, market):
    entry_time, end_time = server(birth["entry_time_server"]), server(close["server_time"])
    row = {"role": role, "parent_id": birth["position_identifier"], "parent_entry": entry_time,
           "parent_close": end_time, "half": "H1" if birth["entry_time_server"] < "2025.07.01" else "H2",
           "status": "NO_HEADROOM", "beta": None, "volume": 0.0, "entry_time": None,
           "exit_time": None, "direction": -int(birth["direction"]), "entry": None,
           "stop": None, "exit": None, "gross_budget": .5 * float(birth["planned_risk_usd"]),
           "quote_actual": None, "quote_stressed": None, "stop_exit": 0,
           "headroom": float(birth["entry_aggregate_headroom_usd"]),
           "required_headroom": float(birth["planned_risk_usd"]), "moment_bar": None,
           "updates_known": None, "proposed": 0}
    if row["headroom"] < row["required_headroom"]:
        return row
    a = market["US500"]
    target_entry, target_exit = (entry_time + 59) // 60 * 60, (end_time + 59) // 60 * 60
    start = int(np.searchsorted(a["time"], target_entry))
    if start >= len(a) or int(a["time"][start]) > entry_time + 120:
        row["status"] = "ENTRY_QUOTE_UNAVAILABLE"
        row["proposed"] = 1
        return row
    t = int(a["time"][start])
    if t >= target_exit:
        row["status"] = "PARENT_FINISHED_BEFORE_PROXY_ENTRY"
        return row
    moment_bar = t // 3600 * 3600
    if moment_bar not in moments:
        raise RuntimeError("Causal beta state unavailable for own quote")
    xy, xx, known = moments[moment_bar][role]
    entry_bid = float(a["open"][start])
    ratio = float(birth["volume"]) * float(birth["entry_price"]) / entry_bid
    beta, target_lots = infer(session, xy, xx, ratio)
    volume = math.floor(target_lots / .01 + 1e-9) * .01
    row.update(beta=beta, moment_bar=moment_bar, updates_known=known, volume=volume)
    if volume < .01:
        row["status"] = "SUB_MINIMUM_VOLUME"
        return row
    row["proposed"] = 1
    entry_spread = float(a["spread"][start]) * .01
    direction = row["direction"]
    entry = entry_bid + (entry_spread if direction > 0 else 0.0)
    raw_stop = entry - direction * row["gross_budget"] / volume
    stop = (math.ceil(raw_stop / .01 - 1e-9) if direction > 0 else math.floor(raw_stop / .01 + 1e-9)) * .01
    row.update(entry_time=t, entry=entry, stop=stop)
    if stop <= 0 or direction * (entry - stop) < .01 - 1e-9:
        row["status"] = "PROTECTION_UNAVAILABLE"
        row["proposed"] = 0
        return row
    # Exact native stop/freeze checks use actual quotes. Prototype retains
    # at least one tick behind the executable opposite quote.
    if (direction > 0 and stop > entry_bid - .01 + 1e-9) or (
            direction < 0 and stop < entry_bid + entry_spread + .01 - 1e-9):
        row["status"] = "PROTECTION_UNAVAILABLE"
        row["proposed"] = 0
        return row
    final = int(np.searchsorted(a["time"], target_exit))
    if final >= len(a) or int(a["time"][final]) > end_time + 120:
        row["status"] = "EXIT_QUOTE_UNAVAILABLE"
        return row
    expected = t
    for index in range(start, final + 1):
        bar = a[index]
        bt = int(bar["time"])
        if bt != expected:
            row["status"] = "OPEN_PATH_MINUTE_MISSING"
            return row
        expected += 60
        spread = float(bar["spread"]) * .01
        op, high, low = (float(bar[name]) for name in ("open", "high", "low"))
        if not all(math.isfinite(v) and v > 0 for v in (op, high, low)) or spread < 0 or high < low:
            raise RuntimeError("Invalid hedge price path requires correction")
        stopped = low <= stop if direction > 0 else high + spread >= stop
        if stopped:
            exit_price = min(stop, op) if direction > 0 else max(stop, op + spread)
        elif index == final:
            exit_price = op if direction > 0 else op + spread
        else:
            continue
        if bt // 86400 != t // 86400:
            # A whole overnight contract/financing observation is needed;
            # no zero-cost or positive-swap assumption can pass selection.
            row["status"] = "OVERNIGHT_FINANCING_UNOBSERVED"
            return row
        actual = direction * (exit_price - entry) * volume
        stress = actual - .5 * (entry_spread + spread) * volume
        row.update(status="COMPLETE", exit_time=bt, exit=exit_price, quote_actual=actual,
                   quote_stressed=stress, stop_exit=int(stopped))
        return row
    raise RuntimeError("Unterminated admitted hedge path")


def main():
    if (FAMILY / "evidence/MODEL_SELECTION_V1.json").exists():
        raise RuntimeError("Completed output is immutable")
    if shutil.disk_usage(ROOT).free < 30 * 2**30 + 128 * 2**20:
        raise RuntimeError("Storage reserve")
    market, hourly, samples, counts = hourly_inputs()
    fit = [s for s in samples if s["bar"] >= epoch("2024-01-01") and s["end"] < epoch("2025-01-01")]
    online_labels = [s for s in samples if s["bar"] >= epoch("2025-01-01")]
    fixed_xy = 1e-6 + sum(s["r500"] * s["r100"] for s in fit)
    fixed_xx = 1e-6 + sum(s["r500"] ** 2 for s in fit)
    session, model_path = graph_session()
    save(FAMILY / "models/initial-moments.json", {"fit_rows": len(fit), "sxy": fixed_xy, "sxx": fixed_xx,
         "beta": infer(session, fixed_xy, fixed_xx, 1.0)[0], "hedge_fraction": .5})
    xy, xx, cursor = fixed_xy, fixed_xx, 0
    moments, updates, forecasts = {}, [], []
    forecast_bars = [t for t in sorted(hourly["US100"]) if epoch("2025-01-01") <= t < epoch("2026-01-01")]
    for t in forecast_bars:
        while cursor < len(online_labels) and online_labels[cursor]["end"] < t:
            label = online_labels[cursor]
            before = infer(session, xy, xx, 1.0)[0]
            xy = .995 * xy + label["r500"] * label["r100"]
            xx = .995 * xx + label["r500"] ** 2
            cursor += 1
            updates.append({"applied_at": t, **label, "beta_before": before,
                            "beta_after": infer(session, xy, xx, 1.0)[0], "sxy": xy, "sxx": xx})
        moments[t] = {"static": (fixed_xy, fixed_xx, 0), "online": (xy, xx, cursor)}
        for role, values in moments[t].items():
            beta, lots = infer(session, values[0], values[1], 1.0)
            forecasts.append({"t": t, "role": role, "sxy": values[0], "sxx": values[1],
                              "updates_known": values[2], "beta": beta, "lots_per_notional_ratio": lots})
    csv_save(RAW / "hourly-forecasts.csv", forecasts)
    csv_save(RAW / "online-updates.csv", updates)
    parents = parent_rows()
    rows = [hedge_quote(role, birth, close, moments, session, market)
            for birth, close in parents for role in ("static", "online")]
    csv_save(RAW / "hedge-opportunities.csv", rows)
    calendar_rows = []
    for day in range(365):
        start_day = epoch("2025-01-01") + day * 86400
        day_rows = [r for r in rows if start_day <= r["parent_entry"] < start_day + 86400]
        calendar_rows.append({"date": str(np.datetime64(start_day, "s").astype("datetime64[D]")),
                              "original_parents": sum(r["role"] == "static" for r in day_rows),
                              "static_complete": sum(r["role"] == "static" and r["status"] == "COMPLETE" for r in day_rows),
                              "online_complete": sum(r["role"] == "online" and r["status"] == "COMPLETE" for r in day_rows)})
    csv_save(RAW / "calendar-2025.csv", calendar_rows)
    save(FAMILY / "models/final-online-moments.json", {"sxy": xy, "sxx": xx, "updates": cursor,
         "pending_labels": len(online_labels) - cursor, "last_forecast": forecast_bars[-1]})
    results = {}
    for role in ("static", "online"):
        own = [r for r in rows if r["role"] == role]
        complete = [r for r in own if r["status"] == "COMPLETE"]
        unscored = [r for r in own if r["proposed"] and r["status"] != "COMPLETE"]
        halves = {h: {"parents": sum(r["half"] == h for r in own),
                      "complete_hedges": sum(r["half"] == h for r in complete),
                      "quote_actual": sum(r["quote_actual"] for r in complete if r["half"] == h),
                      "quote_stressed": sum(r["quote_stressed"] for r in complete if r["half"] == h)}
                  for h in ("H1", "H2")}
        actual, stress = (sum(r[key] for r in complete) for key in ("quote_actual", "quote_stressed"))
        gates = {"all_proposed_paths_complete": not unscored,
                 "minimum25_and40pct_parent_supply": len(complete) >= max(25, .4 * len(own)),
                 "positive_total_stressed_increment": stress > 0,
                 "nonnegative_both_halves": all(h["quote_stressed"] >= 0 for h in halves.values())}
        results[role] = {"parents": len(own), "status_counts": dict(Counter(r["status"] for r in own)),
                         "complete_hedges": len(complete), "unscored_proposals": len(unscored),
                         "quote_actual": actual, "quote_stressed": stress,
                         "stop_exits": sum(r["stop_exit"] for r in complete), "halves": halves,
                         "gates": gates, "qualifies": all(gates.values())}
    candidates = [r for r in ("static", "online") if results[r]["qualifies"]]
    survivor = max(candidates, key=lambda role: results[role]["quote_stressed"]) if candidates else None
    files = [Path(__file__), model_path, *sorted((FAMILY / "models").glob("*.json")), *sorted(RAW.glob("*.csv"))]
    result = {"status": "COMPLETE_FROZEN_HEDGE_SELECTION", "fit_rows": len(fit),
              "hourly_population": dict(counts), "hourly_forecasts_per_role": len(forecast_bars),
              "online_updates": cursor, "pending_labels_at_last_forecast": len(online_labels) - cursor,
              "initial_beta": infer(session, fixed_xy, fixed_xx, 1.0)[0], "roles": results,
              "selected_survivor": survivor, "candidate_2026_values_opened": False,
              "native_economic_verdict": None,
              "artifacts": [{"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)} for p in files],
              "free_bytes": shutil.disk_usage(ROOT).free}
    save(FAMILY / "evidence/MODEL_SELECTION_V1.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "artifacts"}, indent=2))


if __name__ == "__main__":
    main()
