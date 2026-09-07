"""Own volatility quantile production and full-lifecycle ratchet selection.

The fixed-volume quote ledger is only an architecture selection input. Complete
native control/candidate equity and costs remain the economic authority.
"""
from collections import Counter, deque
from pathlib import Path
import csv
import datetime as dt
import hashlib
import json
import math
import shutil
import sys

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper
import onnxruntime as ort

FAMILY = Path(__file__).resolve().parent
ROOT = FAMILY.parents[2]
RAW = ROOT / "optimization/artifacts/raw/v7-onnx-online-volatility-ratchet-v1"
EVI = FAMILY / "evidence"
START = 1704067200
BOUNDARY = 1735689600
END = 1767225600


def epoch(label):
    # Numeric encoding of the original server calendar, no timezone conversion.
    return int(dt.datetime.strptime(label, "%Y.%m.%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp())


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest().upper()


def ref(path):
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError("Immutable output exists: " + str(path))
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def tape(path, rows):
    if not rows:
        raise RuntimeError("Empty declared population")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def reserve():
    free = shutil.disk_usage(ROOT).free
    if free < 30 * 2**30 + 512 * 2**20:
        raise RuntimeError("Storage reserve requires correction")
    return free


def prepare():
    reserve()
    declaration = json.loads((EVI / "DECLARATION_V1.json").read_text(encoding="utf-8"))
    target = RAW / "input"
    target.mkdir(parents=True, exist_ok=False)
    files = []
    for item in declaration["sources"]:
        source = ROOT / item["path"]
        if sha(source) != item["sha256"]:
            raise RuntimeError("Declared source binding changed")
        if item["name"] == "lifecycles":
            path = target / "lifecycles.csv"
            with source.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = [row for row in reader if "2024.01.01" <= row["server_time"] < "2026.01.01" and row["event"] in ("BIRTH", "CLOSE")]
            tape(path, rows)
            count = len(rows)
        else:
            a = np.load(source, mmap_mode="r", allow_pickle=False)
            lo, hi = np.searchsorted(a["time"], [epoch("2023.12.01 00:00:00"), END])
            path = target / (item["name"] + "-M1.npy")
            np.save(path, np.asarray(a[lo:hi]), allow_pickle=False)
            count = int(hi - lo)
            del a
        if sha(source) != item["sha256"]:
            raise RuntimeError("Original changed during own physical copy")
        files.append({**ref(path), "rows": count, "original": item})
    save(EVI / "INPUT_COPY_V1.json", {"status": "OWN_TIMESTAMP_CUT_INPUT_COMPLETE", "files": files,
         "candidate_2026_values_opened": False, "live_changes": False, "free_bytes": reserve()})
    print(json.dumps({"input_files": files, "free_bytes": reserve()}, indent=2))


def aggregate(a):
    buckets = a["time"] // 1800 * 1800
    starts = np.r_[0, np.flatnonzero(np.diff(buckets)) + 1]
    ends = np.r_[starts[1:], len(a)]
    result = []
    for lo, hi in zip(starts, ends):
        group = a[lo:hi]
        result.append((int(buckets[lo]), float(group["high"].max()), float(group["low"].min()),
                       float(group["close"][-1]), float(group["tick_volume"].sum()),
                       float(group["spread"][-1]) * .01,
                       float(np.max(group["high"] + .01 * group["spread"])), len(group), int(group["time"][-1])))
    return np.array(result, dtype=[("time", "<i8"), ("high", "<f8"), ("low", "<f8"),
                    ("close", "<f8"), ("volume", "<f8"), ("spread", "<f8"), ("ask_high", "<f8"), ("minutes", "<i8"), ("last_quote_minute", "<i8")])


def observations(symbol, bars):
    records = []
    for when in range(START, END, 1800):
        idx = int(np.searchsorted(bars["time"], when))
        ready = idx >= 48 and bars["time"][idx - 1] == when - 1800 and bars["time"][idx - 48] >= when - 7 * 86400
        for direction in (-1, 1):
            r = {"time": when, "symbol": symbol, "direction": direction, "status": "MISSING_COMPLETED_PREFIX",
                 "scale": None, "last_quote": None, "last_quote_minute": None, "x": None, "label": None, "loglabel": None, "available": when + 1800}
            if ready:
                past = bars[idx - 48:idx]
                ranges = past["high"] - past["low"]
                scale = max(.01, float(np.median(ranges)))
                hour = (when % 86400) / 3600
                x = np.array([int(symbol == "US100"), direction,
                              math.log(max(.01, float(ranges[-6:].mean())) / scale), ranges[-1] / scale,
                              direction * (past["close"][-1] - past["close"][-2]) / scale,
                              direction * (past["close"][-1] - past["close"][-7]) / scale,
                              math.log((1 + past["volume"][-6:].mean()) / (1 + past["volume"].mean())),
                              past["spread"][-1] / scale, math.sin(2 * math.pi * hour / 24), math.cos(2 * math.pi * hour / 24)], dtype=np.float64)
                quote = float(past["close"][-1] + (past["spread"][-1] if direction < 0 else 0))
                if not np.all(np.isfinite(x)):
                    raise RuntimeError("Feature arithmetic correction required")
                r.update(status="MISSING_LABEL", scale=scale, last_quote=quote, last_quote_minute=int(past["last_quote_minute"][-1]), x=x)
                if idx < len(bars) and bars["time"][idx] == when:
                    label = max(0.0, (quote - bars["low"][idx]) / scale if direction > 0 else (bars["ask_high"][idx] - quote) / scale)
                    r.update(status="COMPLETE", label=float(label), loglabel=math.log(max(.05, label)))
            records.append(r)
    return records


def produce_model(records, output):
    fit = [r for r in records if r["time"] < BOUNDARY and r["available"] < BOUNDARY and r["status"] == "COMPLETE"]
    xs = np.array([r["x"] for r in fit])
    mean, scale = xs.mean(axis=0), np.maximum(xs.std(axis=0), 1e-6)

    def features(x):
        return np.r_[1., np.clip((x - mean) / scale, -6, 6)].astype(np.float32)

    design = np.array([features(r["x"]) for r in fit], dtype=np.float64)
    y = np.array([r["loglabel"] for r in fit])
    weights_fit = np.linalg.solve(design.T @ design + np.diag([1.] + [50.] * 10), design.T @ np.clip(y, -3, 3))
    calibration = float(np.quantile(y - design @ weights_fit, .9))
    nodes = [helper.make_node("MatMul", ["features", "weights"], ["mean"]),
             helper.make_node("Add", ["mean", "offset"], ["logquantile"]),
             helper.make_node("Exp", ["logquantile"], ["distance"]),
             helper.make_node("Clip", ["distance", "minimum", "maximum"], ["quantile"])]
    graph = helper.make_graph(nodes, "V7AdverseExcursionRatchet", [
        helper.make_tensor_value_info("features", TensorProto.FLOAT, [1, 11]),
        helper.make_tensor_value_info("weights", TensorProto.FLOAT, [11, 1]),
        helper.make_tensor_value_info("offset", TensorProto.FLOAT, [1, 1])],
        [helper.make_tensor_value_info("quantile", TensorProto.FLOAT, [1, 1])],
        [numpy_helper.from_array(np.array(.25, dtype=np.float32), "minimum"),
         numpy_helper.from_array(np.array(8., dtype=np.float32), "maximum")])
    model = helper.make_model(graph, producer_name="v7-volatility-ratchet", opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8
    path = FAMILY / "models/volatility-ratchet.onnx"
    path.parent.mkdir(exist_ok=False)
    onnx.save(model, path)
    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    save(path.parent / "initial-state.json", {"fit_rows": len(fit), "mean": mean.tolist(), "scale": scale.tolist(),
         "weights": weights_fit.tolist(), "calibration": calibration})
    selection = sorted([r for r in records if r["time"] >= BOUNDARY], key=lambda r: (r["time"], r["symbol"], r["direction"]))
    weights, shift, pending = weights_fit.copy(), 0., deque()
    updates, forecasts, lookup = [], [], {}
    for r in selection:
        while pending and pending[0][0]["available"] < r["time"]:
            old, x, oldlogq = pending.popleft()
            v = x.astype(np.float64)
            residual = float(np.clip(old["loglabel"], -3, 3) - weights @ v)
            weights = np.clip(weights + .01 * residual * v / (1 + v @ v), -5, 5)
            shift = float(np.clip(shift + .01 * (.9 - int(old["loglabel"] <= oldlogq)), -1, 1))
            updates.append({"time": r["time"], "source_time": old["time"], "symbol": old["symbol"],
                            "direction": old["direction"], "available": old["available"], "label": old["label"],
                            "stored_logquantile": oldlogq, "shift": shift, "weights": json.dumps(weights.tolist(), separators=(",", ":"))})
        for role, w, offset in (("static", weights_fit, calibration), ("online", weights, calibration + shift)):
            quantile, logq = None, None
            if r["x"] is not None:
                x = features(r["x"])
                quantile = float(session.run(None, {"features": x.reshape(1, 11), "weights": w.astype(np.float32).reshape(11, 1),
                                                   "offset": np.array([[offset]], dtype=np.float32)})[0][0, 0])
                logq = float(w @ x.astype(np.float64) + offset)
                if not math.isfinite(quantile):
                    raise RuntimeError("ONNX inference correction required")
            item = {"role": role, "time": r["time"], "symbol": r["symbol"], "direction": r["direction"],
                    "status": r["status"], "quantile": quantile, "scale": r["scale"], "last_quote": r["last_quote"], "last_quote_minute": r["last_quote_minute"],
                    "label": r["label"], "available": r["available"], "updates_known": len(updates) if role == "online" else 0}
            forecasts.append(item)
            lookup[(role, r["symbol"], r["direction"], r["time"])] = item
            if role == "online" and r["status"] == "COMPLETE":
                pending.append((r, x, logq))
    tape(output / "forecasts.csv", forecasts)
    tape(output / "online-updates.csv", updates)
    save(path.parent / "final-online-state.json", {"weights": weights.tolist(), "calibration_shift": shift,
         "updates": len(updates), "pending": len(pending)})
    calibration_stats = {}
    for role in ("static", "online"):
        subset = [r for r in forecasts if r["role"] == role and r["label"] is not None]
        calibration_stats[role] = {"complete": len(subset), "coverage": float(np.mean([r["label"] <= r["quantile"] for r in subset])),
                                  "pinball": float(np.mean([(.9 - int(r["label"] < r["quantile"])) * (r["label"] - r["quantile"]) for r in subset]))}
    return lookup, {"fit_rows": len(fit), "forecasts_per_role": len(selection), "updates": len(updates),
                    "pending": len(pending), "calibration": calibration_stats, "model": ref(path)}


def read_trades():
    births, closes = {}, {}
    with (RAW / "input/lifecycles.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["release_id"] != "NEXT-E03-V7R-RLO1-0bba2ca045fe" or int(row["partial_observation"]) or int(row["research_dropped_records"]):
                raise RuntimeError("Source lifecycle binding correction required")
            dest = births if row["event"] == "BIRTH" else closes
            key = row["position_identifier"]
            if key in dest:
                raise RuntimeError("Partial/duplicate lifecycle requires correction")
            dest[key] = row
    trades = []
    for key, b in births.items():
        if not b["entry_time_server"].startswith("2025."):
            continue
        c = closes.get(key)
        if c is None:
            raise RuntimeError("Incomplete original lifecycle requires correction")
        d, v = int(b["direction"]), float(b["volume"])
        entry, exit_price = float(b["entry_price"]), float(c["exit_price"])
        actual, stress = float(c["actual_net_usd"]), float(c["stressed_net_usd"])
        trades.append({"id": key, "component": b["component_id"], "symbol": b["symbol"], "direction": d,
                       "entry_time": epoch(b["entry_time_server"]), "close_time": epoch(c["server_time"]),
                       "entry_price": entry, "volume": v, "entry_spread": float(b["entry_spread_price"]),
                       "initial_stop": float(b["stop_loss"]), "original_exit": exit_price,
                       "original_actual": actual, "original_stress": stress,
                       "retained_nonprice": min(0., actual - d * (exit_price - entry) * v),
                       "original_extra": actual - stress})
    return sorted(trades, key=lambda r: (r["entry_time"], int(r["id"])))


def portfolio(trades, market, lookup, role):
    ledger, decisions = [], []
    for trade in trades:
        d, entry, v = trade["direction"], trade["entry_price"], trade["volume"]
        peak, stop, lastbar, modifications, unavailable = d * entry, None, None, 0, 0
        record = {**trade, "role": role, "exit_time": trade["close_time"], "exit_price": trade["original_exit"],
                  "actual": trade["original_actual"], "stress": trade["original_stress"], "exit_kind": "ORIGINAL", "modifications": 0,
                  "unavailable_decisions": 0}
        a = market[trade["symbol"]]
        lo, hi = np.searchsorted(a["time"], [trade["entry_time"], trade["close_time"]])
        for minute in a[lo:hi]:
            t = int(minute["time"])
            # Native original close inside the minute wins this unresolved order.
            if t + 60 > trade["close_time"]:
                break
            spread = .01 * int(minute["spread"])
            opening = float(minute["open"] + (spread if d < 0 else 0))
            adverse = float(minute["low"] if d > 0 else minute["high"] + spread)

            def hit():
                return stop is not None and d * (adverse - stop) <= 0

            def close_at_stop():
                price = min(opening, stop) if d > 0 else max(opening, stop)
                gap = max(0., d * (stop - opening))
                actual = d * (price - entry) * v + trade["retained_nonprice"]
                stress = actual - trade["original_extra"] - max(0., spread - trade["entry_spread"]) * v - gap * v
                record.update(exit_time=t, exit_price=price, actual=actual, stress=stress, exit_kind="RATCHET_SL")

            if hit():
                close_at_stop()
                break
            bar = t // 1800 * 1800
            if lastbar != bar and bar > trade["entry_time"] and t <= bar + 120:
                lastbar = bar
                forecast = lookup.get((role, trade["symbol"], d, bar))
                status, proposed = "MISSING_FORECAST", None
                if forecast and forecast["quantile"] is not None:
                    # Do not turn a stale pre-entry last quote into earned MFE.
                    # A minute beginning before entry is also excluded here,
                    # because its final tick ordinal is unavailable in M1 input.
                    if forecast["last_quote_minute"] >= trade["entry_time"]:
                        peak = max(peak, d * forecast["last_quote"])
                    raw_stop = d * (peak - forecast["quantile"] * forecast["scale"])
                    proposed = (math.floor(raw_stop / .01 + 1e-8) if d > 0 else math.ceil(raw_stop / .01 - 1e-8)) * .01
                    existing = stop if stop is not None else trade["initial_stop"]
                    if d * (proposed - entry) <= trade["entry_spread"]:
                        status = "NOT_PROFIT_PROTECTING"
                    elif d * (proposed - existing) < .01 - 1e-8:
                        status = "NOT_TIGHTER"
                    elif d * (opening - proposed) < .01 - 1e-8:
                        status = "NO_QUOTE_CLEARANCE"
                    else:
                        stop, status = proposed, "INSTALLED"
                        modifications += 1
                else:
                    unavailable += 1
                decisions.append({"role": role, "id": trade["id"], "time": t, "bar": bar, "peak": peak,
                                  "proposed_stop": proposed, "status": status, "installed_stop": stop})
                if hit():
                    close_at_stop()
                    break
        record.update(modifications=modifications, unavailable_decisions=unavailable)
        ledger.append(record)
    return ledger, decisions


def economics(rows, original=False):
    actual_key, stress_key = ("original_actual", "original_stress") if original else ("actual", "stress")
    time_key = "close_time" if original else "exit_time"
    balance, peak, dd = 100., 100., 0.
    for r in sorted(rows, key=lambda q: (q[time_key], int(q["id"]))):
        balance += r[stress_key]
        peak = max(peak, balance)
        dd = max(dd, 100 * (peak - balance) / peak)
    halves = {}
    for h, before in (("H1", True), ("H2", False)):
        group = [r for r in rows if (r["entry_time"] < epoch("2025.07.01 00:00:00")) == before]
        halves[h] = {"trades": len(group), "actual": sum(r[actual_key] for r in group), "stress": sum(r[stress_key] for r in group),
                     "earlier_exits": 0 if original else sum(r["exit_kind"] == "RATCHET_SL" for r in group)}
    return {"trades": len(rows), "actual": sum(r[actual_key] for r in rows), "stress": sum(r[stress_key] for r in rows),
            "closed_stressed_cash_dd_pct": dd, "halves": halves,
            "earlier_exits": 0 if original else sum(r["exit_kind"] == "RATCHET_SL" for r in rows)}


def main():
    reserve()
    if (EVI / "MODEL_SELECTION_V1.json").exists():
        raise RuntimeError("Completed production is immutable")
    inputs = json.loads((EVI / "INPUT_COPY_V1.json").read_text(encoding="utf-8"))
    for item in inputs["files"]:
        if sha(ROOT / item["path"]) != item["sha256"]:
            raise RuntimeError("Own input binding changed")
    output = RAW / "selection"
    output.mkdir(exist_ok=False)
    market = {s: np.load(RAW / f"input/{s}-M1.npy", allow_pickle=False) for s in ("US30", "US100")}
    records = []
    for symbol, a in market.items():
        records.extend(observations(symbol, aggregate(a)))
    tape(output / "market-population.csv", [{**r, "x": json.dumps(r["x"].tolist(), separators=(",", ":")) if r["x"] is not None else None} for r in records])
    lookup, model_info = produce_model(records, output)
    trades = read_trades()
    control = economics(trades, original=True)
    roles = {}
    for role in ("static", "online"):
        ledger, decisions = portfolio(trades, market, lookup, role)
        tape(output / f"{role}-lifecycles.csv", ledger)
        tape(output / f"{role}-ratchets.csv", decisions)
        result = economics(ledger)
        gates = {"all_original_lifecycles": len(ledger) == len(trades),
                 "minimum_activity": result["earlier_exits"] >= 20 and all(h["earlier_exits"] >= 5 for h in result["halves"].values()),
                 "both_profits_improve": result["actual"] > control["actual"] and result["stress"] > control["stress"],
                 "both_halves_positive": all(h["actual"] > 0 and h["stress"] > 0 for h in result["halves"].values()),
                 "closed_cash_dd": result["closed_stressed_cash_dd_pct"] <= 1.10 * control["closed_stressed_cash_dd_pct"]}
        roles[role] = {**result, "decisions": dict(Counter(r["status"] for r in decisions)), "gates": gates, "qualifies": all(gates.values())}
    calendar = []
    for day in range(365):
        start = BOUNDARY + day * 86400
        calendar.append({"date": str(dt.date(2025, 1, 1) + dt.timedelta(days=day)),
                         "original_births": sum(start <= t["entry_time"] < start + 86400 for t in trades)})
    tape(output / "calendar-2025.csv", calendar)
    qualifying = [r for r in ("static", "online") if roles[r]["qualifies"]]
    survivor = max(qualifying, key=lambda r: roles[r]["stress"]) if qualifying else None
    files = [Path(__file__), *sorted((FAMILY / "models").glob("*")), *sorted(output.glob("*.csv"))]
    result = {"status": "COMPLETE_FROZEN_VOLATILITY_RATCHET_SELECTION", "model": model_info, "control": control, "roles": roles,
              "market_status_counts": {str(y): dict(Counter(r["status"] for r in records if (r["time"] < BOUNDARY) == (y == 2024))) for y in (2024, 2025)},
              "selected_survivor": survivor, "native_economic_verdict": None, "candidate_2026_values_opened": False,
              "artifacts": [ref(p) for p in files], "free_bytes": reserve()}
    save(EVI / "MODEL_SELECTION_V1.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "artifacts"}, indent=2))


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "prepare":
        prepare()
    elif len(sys.argv) == 1:
        main()
    else:
        raise SystemExit("Use prepare for physical inputs, or no argument for model production")
