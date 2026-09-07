"""Own fixed V7 Passive quote-quantile model production and 2025 selection.

These are distribution forecasts and approximate quote touches, not cash or
native economic simulation. All original eligible opportunities are retained.
"""
from pathlib import Path
from collections import Counter, deque
import csv
import datetime as dt
import hashlib
import json
import shutil

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper
import onnxruntime as ort

FAMILY = Path(__file__).resolve().parent
ROOT = FAMILY.parents[2]
RAW = ROOT / "optimization/artifacts/raw/v7-onnx-online-passive-execution-v1"
EVIDENCE = FAMILY / "evidence"
Q = 0.35
FEATURE_NAMES = ["abs_state", "direction", "range_bps", "bar_range_ratio",
                 "aligned_body", "aligned_four_bar_move", "aligned_location12", "slot"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def epoch(text):
    # Numeric native-server calendar coordinate, not an assertion of physical UTC.
    return int(np.datetime64(text, "s").astype(np.int64))


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def opportunities():
    a = np.load(RAW / "input/US100-M1-202312-202512.npy", mmap_mode="r")
    time = a["time"]
    if np.any(np.diff(time) <= 0):
        raise RuntimeError("Native M1 ordering requires correction")
    groups = time // 900 * 900
    first = np.r_[0, np.flatnonzero(np.diff(groups)) + 1]
    last = np.r_[first[1:] - 1, len(a) - 1]
    bt = groups[first]
    op = a["open"][first]
    hi = np.maximum.reduceat(a["high"], first)
    lo = np.minimum.reduceat(a["low"], first)
    cl = a["close"][last]
    counts = Counter()
    records = []
    population = []
    lower, upper = epoch("2024-01-01"), epoch("2026-01-01")
    for j in range(98, len(bt)):
        t = int(bt[j])
        if not lower <= t < upper:
            continue
        decision = int(bt[j - 1])
        minute = (decision % 86400) // 60
        if not 720 <= minute < 960:
            continue
        year = "2024" if t < epoch("2025-01-01") else "2025"
        counts[year + "_session_slots"] += 1
        state = None
        reason = "AVAILABLE"
        closes = cl[j - 98:j]
        ranges = hi[j - 97:j - 1] - lo[j - 97:j - 1]
        if t - decision != 900:
            reason = "DECISION_BAR_GAP"
        elif (not np.all(np.isfinite(closes)) or np.any(closes <= 0)
              or not np.all(np.isfinite(ranges)) or np.any(ranges <= 0)
              or np.any(lo[j - 97:j - 1] <= 0)):
            reason = "ORIGINAL_LOOKBACK_UNAVAILABLE"
        else:
            returns = np.log(closes[1:97] / closes[:96])
            sd = np.std(returns, ddof=1)
            scale = float(np.median(ranges))
            if not np.isfinite(sd) or sd <= 0 or scale <= 0:
                reason = "ORIGINAL_SCALE_UNAVAILABLE"
            else:
                state = float(np.log(closes[-1] / closes[-13]) / (sd * np.sqrt(12.0)))
                if abs(state) < 1.0:
                    reason = "ORIGINAL_NO_SIGNAL"
        population.append({"forecast_bar": t, "decision_bar": decision,
                           "year": year, "state": state, "result": reason})
        counts[year + "_" + reason] += 1
        if reason != "AVAILABLE":
            continue
        direction = -1 if state > 0 else 1
        close = float(cl[j - 1])
        high12, low12 = float(np.max(hi[j - 12:j])), float(np.min(lo[j - 12:j]))
        features = np.array([
            abs(state), direction, scale / close * 10000.0,
            (hi[j - 1] - lo[j - 1]) / scale,
            direction * (close - op[j - 1]) / scale,
            direction * (close - cl[j - 5]) / scale,
            direction * (2.0 * (close - low12) / (high12 - low12) - 1.0),
            (minute - 720) / 240.0,
        ], dtype=np.float64)
        if not np.all(np.isfinite(features)):
            raise RuntimeError("Feature arithmetic requires correction")
        start, end = np.searchsorted(time, [t, t + 3600])
        label = None
        complete = (end - start == 60 and
                    np.array_equal(time[start:end], t + np.arange(60) * 60))
        if complete:
            future = a[start:end]
            valid = (np.all(np.isfinite(future["high"])) and
                     np.all(np.isfinite(future["low"])) and
                     np.all(future["high"] >= future["low"]) and
                     np.all(future["low"] > 0) and np.all(future["spread"] >= 0))
            if not valid:
                raise RuntimeError("Future quote label data requires correction")
            if direction < 0:
                label = float((np.max(future["high"]) - close) / scale)
            else:
                label = float((close - np.min(future["low"] + future["spread"] * 0.01)) / scale)
        counts[year + ("_COMPLETE_LABEL" if label is not None else "_INCOMPLETE_LABEL")] += 1
        records.append({"t": t, "decision": decision, "year": year,
                        "end": t + 3600, "direction": direction, "state": state,
                        "scale": scale, "close": close, "x": features, "y": label})
    with (RAW / "population.csv").open("w", encoding="utf-8", newline="") as h:
        writer = csv.DictWriter(h, fieldnames=list(population[0]))
        writer.writeheader()
        writer.writerows(population)
    return records, dict(counts)


def train(records):
    fit = [r for r in records if r["year"] == "2024" and r["y"] is not None
           and r["end"] < epoch("2025-01-01")]
    xraw = np.stack([r["x"] for r in fit])
    raw_y = np.array([r["y"] for r in fit])[:, None]
    y = np.clip(raw_y, -4.0, 4.0)
    mean, std = xraw.mean(axis=0), np.maximum(xraw.std(axis=0), 1.0e-6)
    x = np.clip((xraw - mean) / std, -6.0, 6.0)
    rng = np.random.default_rng(20260907)
    params = [rng.normal(0.0, np.sqrt(1.0 / 8), (8, 12)), np.zeros((1, 12)),
              rng.normal(0.0, 0.05, (12, 1)), np.zeros((1, 1))]
    m = [np.zeros_like(p) for p in params]
    v = [np.zeros_like(p) for p in params]
    n = len(x)
    for step in range(1, 1201):
        w1, b1, w2, b2 = params
        hidden = np.tanh(x @ w1 + b1)
        pred = hidden @ w2 + b2
        grad_out = ((pred > y).astype(np.float64) - Q) / n
        grad_hidden = (grad_out @ w2.T) * (1.0 - hidden ** 2)
        grads = [x.T @ grad_hidden + 0.0002 * w1, grad_hidden.sum(axis=0, keepdims=True),
                 hidden.T @ grad_out + 0.0002 * w2, grad_out.sum(axis=0, keepdims=True)]
        for k, grad in enumerate(grads):
            m[k] = 0.9 * m[k] + 0.1 * grad
            v[k] = 0.999 * v[k] + 0.001 * grad * grad
            params[k] -= 0.005 * (m[k] / (1.0 - 0.9 ** step)) / (
                np.sqrt(v[k] / (1.0 - 0.999 ** step)) + 1.0e-8)
    if not all(np.all(np.isfinite(p)) for p in params):
        raise RuntimeError("Nonfinite model production")
    baseline = float(np.quantile(raw_y[:, 0], Q))
    stats = {"fit_records": len(fit), "features": FEATURE_NAMES,
             "first_forecast_bar": fit[0]["t"], "last_label_end": max(r["end"] for r in fit),
             "raw_target_min": float(raw_y.min()), "raw_target_max": float(raw_y.max()),
             "clipped_fit_targets": int(np.sum(raw_y != y)), "constant_reference": baseline,
             "steps": 1200, "seed": 20260907,
             "normalization_mean": mean.tolist(), "normalization_std": std.tolist()}
    return params, mean, std, baseline, stats


def export_model(params, mean, std):
    initializers = [numpy_helper.from_array(np.asarray(a, dtype=np.float32), name)
                    for name, a in [("mean", mean.reshape(1, 8)), ("std", std.reshape(1, 8)),
                                    ("clip_low", np.array(-6.0)), ("clip_high", np.array(6.0)),
                                    ("w1", params[0]), ("b1", params[1]),
                                    ("w2", params[2]), ("b2", params[3])]]
    nodes = [helper.make_node("Sub", ["features", "mean"], ["centered"]),
             helper.make_node("Div", ["centered", "std"], ["scaled"]),
             helper.make_node("Clip", ["scaled", "clip_low", "clip_high"], ["x"]),
             helper.make_node("MatMul", ["x", "w1"], ["h0"]),
             helper.make_node("Add", ["h0", "b1"], ["h1"]),
             helper.make_node("Tanh", ["h1"], ["hidden"]),
             helper.make_node("MatMul", ["hidden", "w2"], ["p0"]),
             helper.make_node("Add", ["p0", "b2"], ["p1"]),
             helper.make_node("Add", ["p1", "online_bias"], ["quantile"])]
    graph = helper.make_graph(nodes, "V7PassiveQuoteQuantile",
                              [helper.make_tensor_value_info("features", TensorProto.FLOAT, [1, 8]),
                               helper.make_tensor_value_info("online_bias", TensorProto.FLOAT, [1, 1])],
                              [helper.make_tensor_value_info("quantile", TensorProto.FLOAT, [1, 1])],
                              initializers)
    model = helper.make_model(graph, producer_name="v7-passive-execution-v1",
                              opset_imports=[helper.make_opsetid("", 17)], ir_version=8)
    path = FAMILY / "models/passive-quantile.onnx"
    path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, path)
    return path


def price(close, scale, direction, offset):
    raw = close - direction * offset * scale
    units = raw / 0.01
    rounded = np.floor(units + 1.0e-10) if direction > 0 else np.ceil(units - 1.0e-10)
    return float(np.round(rounded * 0.01, 2))


def pinball(y, forecast):
    error = y - forecast
    return max(Q * error, (Q - 1.0) * error)


def evaluate(records, model_path, baseline):
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    session = ort.InferenceSession(str(model_path), sess_options=options,
                                   providers=["CPUExecutionProvider"])
    rows = [r for r in records if r["year"] == "2025"]
    biases = {-1: 0.0, 1: 0.0}
    pending = deque()
    forecasts = []
    updates = []
    for r in rows:
        while pending and pending[0]["end"] < r["t"]:
            label = pending.popleft()
            if label["y"] is None:
                continue
            direction = label["direction"]
            before = biases[direction]
            biases[direction] = float(np.clip(before + 0.02 * (Q - (label["y"] < label["pred"])), -0.5, 0.5))
            updates.append({"forecast_bar": label["t"], "available_bar": label["end"],
                            "applied_at_forecast_bar": r["t"], "direction": direction,
                            "raw_label": label["y"], "stored_prediction": label["pred"],
                            "bias_before": before, "bias_after": biases[direction]})
        original_price = price(r["close"], r["scale"], r["direction"], 0.25)
        original_offset = -r["direction"] * (original_price - r["close"]) / r["scale"]
        online_prediction = None
        for role in ["static", "online"]:
            bias = 0.0 if role == "static" else biases[r["direction"]]
            pred = float(session.run(None, {"features": r["x"].astype(np.float32).reshape(1, 8),
                                           "online_bias": np.array([[bias]], dtype=np.float32)})[0][0, 0])
            if not np.isfinite(pred):
                raise RuntimeError("ONNX inference requires correction")
            offset = float(np.clip(pred, 0.05, 1.0))
            candidate_price = price(r["close"], r["scale"], r["direction"], offset)
            effective_offset = -r["direction"] * (candidate_price - r["close"]) / r["scale"]
            y = r["y"]
            forecasts.append({"role": role, "forecast_bar": r["t"],
                              "decision_bar": r["decision"], "label_available_bar": r["end"],
                              "half": "H1" if r["t"] < epoch("2025-07-01") else "H2",
                              "direction": r["direction"], "feature_vector": "|".join(map(str, r["x"])),
                              "bias": bias, "raw_prediction": pred, "clamped_offset": offset,
                              "raw_label": y, "candidate_price": candidate_price,
                              "original_price": original_price,
                              "original_potential_touch": None if y is None else int(y >= original_offset),
                              "candidate_potential_touch": None if y is None else int(y >= effective_offset),
                              "changed_one_tick": int(abs(candidate_price - original_price) >= 0.01 - 1.0e-9),
                              "pinball": None if y is None else pinball(y, pred),
                              "constant_pinball": None if y is None else pinball(y, baseline)})
            if role == "online":
                online_prediction = pred
        pending.append({"t": r["t"], "end": r["end"], "direction": r["direction"],
                        "y": r["y"], "pred": online_prediction})
    for filename, values in [("forecasts.csv", forecasts), ("online-updates.csv", updates)]:
        with (RAW / filename).open("w", encoding="utf-8", newline="") as h:
            writer = csv.DictWriter(h, fieldnames=list(values[0]))
            writer.writeheader()
            writer.writerows(values)
    summaries = {}
    for role in ["static", "online"]:
        all_rows = [r for r in forecasts if r["role"] == role]
        scored = [r for r in all_rows if r["raw_label"] is not None]
        loss = float(np.mean([r["pinball"] for r in scored]))
        reference = float(np.mean([r["constant_pinball"] for r in scored]))
        original_touches = sum(r["original_potential_touch"] for r in scored)
        candidate_touches = sum(r["candidate_potential_touch"] for r in scored)
        halves = {}
        for half in ["H1", "H2"]:
            sub = [r for r in scored if r["half"] == half]
            halves[half] = {"scored": len(sub), "loss": float(np.mean([r["pinball"] for r in sub])),
                            "reference": float(np.mean([r["constant_pinball"] for r in sub]))}
            halves[half]["loss_ratio"] = halves[half]["loss"] / halves[half]["reference"]
        gates = {"pinball_improves_2pct": loss <= reference * 0.98,
                 "both_halves_within_5pct": all(h["loss_ratio"] <= 1.05 for h in halves.values()),
                 "potential_touch_supply_75pct": candidate_touches >= original_touches * 0.75,
                 "changed_at_least_5pct": sum(r["changed_one_tick"] for r in all_rows) >= 0.05 * len(all_rows)}
        summaries[role] = {"forecasts": len(all_rows), "complete_labels": len(scored),
                           "incomplete_labels": len(all_rows) - len(scored), "raw_pinball": loss,
                           "constant_raw_pinball": reference, "loss_improvement": 1.0 - loss / reference,
                           "original_potential_touches": original_touches,
                           "candidate_potential_touches": candidate_touches,
                           "changed_one_tick": sum(r["changed_one_tick"] for r in all_rows),
                           "halves": halves, "gates": gates, "qualifies": all(gates.values())}
    qualified = [r for r in ["static", "online"] if summaries[r]["qualifies"]]
    survivor = min(qualified, key=lambda r: (summaries[r]["raw_pinball"], r != "static")) if qualified else None
    return {"roles": summaries, "survivor": survivor,
            "online_updates": len(updates), "online_pending_at_last_forecast": len(pending),
            "online_final_bias": biases,
            "calendar_days_2025": 365,
            "observed_opportunity_dates": len(set(r["t"] // 86400 for r in rows)),
            "last_forecast_bar": rows[-1]["t"],
            "scope": "distribution selection and approximate quote touch only; no cash or native DD verdict"}


def main():
    if (EVIDENCE / "MODEL_SELECTION_V1.json").exists():
        raise RuntimeError("Existing model/selection evidence must remain immutable")
    if shutil.disk_usage(ROOT).free < 30 * 1024 ** 3:
        raise RuntimeError("30 GiB reserve must be restored before model production")
    records, population = opportunities()
    params, mean, std, baseline, fit_stats = train(records)
    model_path = export_model(params, mean, std)
    selection = evaluate(records, model_path, baseline)
    output = {"utc": dt.datetime.now(dt.timezone.utc).isoformat(), "population": population,
              "fit": fit_stats, "selection": selection,
              "model": {"path": model_path.relative_to(ROOT).as_posix(),
                        "bytes": model_path.stat().st_size, "sha256": sha(model_path)},
              "files": [{"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size,
                         "sha256": sha(p)} for p in sorted(RAW.glob("*.csv"))],
              "candidate_2026_values_opened": False,
              "free_bytes": shutil.disk_usage(ROOT).free}
    save_json(EVIDENCE / "MODEL_SELECTION_V1.json", output)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
