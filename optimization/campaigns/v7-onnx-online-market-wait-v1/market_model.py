"""Produce the fixed market-wait ONNX policy and causal quote selection.

Quote savings are selection inputs. Actual risk, fills, capital and drawdown
remain properties of a later complete native portfolio run.
"""
from collections import Counter, deque
from pathlib import Path
import csv
import datetime as dt
import hashlib
import json
import math
import shutil

import numpy as np
import onnx
from onnx import TensorProto, helper
import onnxruntime as ort

FAMILY = Path(__file__).resolve().parent
ROOT = FAMILY.parents[2]
RAW = ROOT / "optimization/artifacts/raw/v7-onnx-online-market-wait-v1"
OUTPUT = RAW / "selection-v2"
MODELS = FAMILY / "models/v2"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def tape(path, rows):
    if not rows:
        raise RuntimeError("Declared population is empty")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def observation(window, birth):
    t = int(window["source_entry_epoch"])
    period = 1800 if birth["component_id"].startswith("ZT-M30-") else 3600
    if not birth["component_id"].startswith(("ZT-M30-", "ZT-H1-")):
        raise RuntimeError("Unknown original market timeframe")
    deadline = (t // period * period + 120) * 1000
    r = {"index": window["index"], "position_id": window["position_id"],
         "symbol": birth["symbol"], "component_id": birth["component_id"],
         "date": birth["entry_time_server"][:10].replace(".", "-"),
         "year": int(birth["entry_time_server"][:4]), "source_second": t,
         "direction": int(birth["direction"]), "volume": float(birth["volume"]),
         "deadline_ms": deadline, "forecast_ms": None, "decision_ordinal": None,
         "status": "INITIAL_QUOTE_UNAVAILABLE", "eligible": int(t * 1000 + 30000 <= deadline),
         "x": None, "immediate_price": None, "spread": None, "label": None,
         "label_available_ms": None, "wait_price": None, "wait_spread": None,
         "wait_ms": None, "wait_ordinal": None, "wait_kind": None,
         "all_wait_actual_saving": None, "all_wait_stressed_saving": None}
    if not r["eligible"]:
        r["status"] = "WAIT_WINDOW_UNAVAILABLE"
        return r
    path = ROOT / window["path"]
    if digest(path) != window["sha256"]:
        raise RuntimeError("Own raw tick window changed")
    raw = np.load(path)
    valid = np.isfinite(raw["bid"]) & np.isfinite(raw["ask"]) & (raw["bid"] > 0) & (raw["ask"] > raw["bid"])
    ordinals = np.flatnonzero(valid)
    a = raw[valid]
    at = int(np.searchsorted(a["time_msc"], t * 1000))
    if at >= len(a) or int(a["time_msc"][at]) > t * 1000 + 3000:
        return r
    decision = a[at]
    ms = int(decision["time_msc"])
    r.update(forecast_ms=ms, decision_ordinal=int(ordinals[at]), label_available_ms=ms + 33000)
    if ms + 30000 > deadline:
        r.update(status="WAIT_WINDOW_UNAVAILABLE", eligible=0)
        return r
    # All history is strictly before the current millisecond. The current
    # executable quote is supplied separately. No same-ms future tail enters
    # a feature, including in a native CopyTicksRange implementation.
    prior = a[(a["time_msc"] >= ms - 60000) & (a["time_msc"] < ms)]
    anchor60 = np.flatnonzero(a["time_msc"] <= ms - 60000)
    anchor10 = np.flatnonzero(a["time_msc"] <= ms - 10000)
    coverage = np.any((a["time_msc"] >= ms - 61000) & (a["time_msc"] <= ms - 55000))
    if len(prior) < 2 or not len(anchor60) or not len(anchor10) or not coverage:
        r["status"] = "PRIOR_TICK_FEATURE_UNAVAILABLE"
        return r
    spread = float(decision["ask"] - decision["bid"])
    mid = float(.5 * (decision["ask"] + decision["bid"]))
    mid60 = float(.5 * (a["ask"][anchor60[-1]] + a["bid"][anchor60[-1]]))
    mid10 = float(.5 * (a["ask"][anchor10[-1]] + a["bid"][anchor10[-1]]))
    mids = .5 * (prior["ask"] + prior["bid"])
    direction = r["direction"]
    x = np.array([int(r["symbol"] == "US100"), direction, math.log1p(len(prior)),
                  spread / float(np.median(prior["ask"] - prior["bid"])),
                  direction * (mid - mid60) / spread, direction * (mid - mid10) / spread,
                  float(np.max(mids) - np.min(mids)) / spread,
                  direction * float(np.mean(np.sign(np.diff(mids))))], dtype=np.float64)
    if not np.all(np.isfinite(x)):
        raise RuntimeError("Causal feature arithmetic correction required")
    immediate = float(decision["ask"] if direction > 0 else decision["bid"])
    target = float(decision["bid"] if direction > 0 else decision["ask"])
    r.update(x=x, spread=spread, immediate_price=immediate, status="FUTURE_QUOTE_UNAVAILABLE")
    chosen, kind = None, None
    for index in range(at + 1, len(a)):
        future = a[index]
        fm = int(future["time_msc"])
        executable = float(future["ask"] if direction > 0 else future["bid"])
        improves = executable <= target if direction > 0 else executable >= target
        if fm <= ms + 30000 and improves:
            chosen, kind = index, "IMPROVING_QUOTE"
            break
        if fm >= ms + 30000:
            if fm <= ms + 33000 and fm <= deadline:
                chosen, kind = index, "MARKET_FALLBACK"
            break
    if chosen is None:
        return r
    future = a[chosen]
    price = float(future["ask"] if direction > 0 else future["bid"])
    later_spread = float(future["ask"] - future["bid"])
    label = direction * (immediate - price) / spread
    actual = direction * (immediate - price) * r["volume"]
    # Original V7 adds max(entry spread, exit spread), not an average.
    # With the same unknown future exit spread held equal, min(0,s0-s1)
    # is a conservative lower bound on the incremental extra-cost saving.
    stress = actual + min(0.0, spread - later_spread) * r["volume"]
    r.update(status="COMPLETE", label=label, wait_price=price, wait_spread=later_spread,
             wait_ms=int(future["time_msc"]), wait_ordinal=int(ordinals[chosen]), wait_kind=kind,
             all_wait_actual_saving=actual, all_wait_stressed_saving=stress)
    return r


def main():
    result_path = FAMILY / "evidence/MODEL_SELECTION_V2.json"
    if result_path.exists():
        raise RuntimeError("Completed bundle is immutable")
    if shutil.disk_usage(ROOT).free < 30 * 2**30 + 64 * 2**20:
        raise RuntimeError("Storage reserve")
    input_manifest = json.loads((FAMILY / "evidence/TICK_INPUT_V2.json").read_text(encoding="utf-8"))
    if input_manifest["status"] != "COMPLETE_INPUT_EXPORT" or input_manifest["binding_changed"]:
        raise RuntimeError("Input binding needs correction before modeling")
    ledger = RAW / "input/original-market-births-2024-2025.csv"
    if digest(ledger) != input_manifest["source_ledger_sha256"]:
        raise RuntimeError("Own source population changed")
    with ledger.open(encoding="utf-8", newline="") as handle:
        births = {r["position_identifier"]: r for r in csv.DictReader(handle)}
    OUTPUT.mkdir(exist_ok=False)
    records = [observation(w, births[w["position_id"]]) for w in input_manifest["windows"]]
    population = [{**r, "x": json.dumps(r["x"].tolist(), separators=(",", ":")) if r["x"] is not None else None}
                  for r in records]
    tape(OUTPUT / "quote-population.csv", population)
    boundary = int(np.datetime64("2025-01-01", "ms").astype(np.int64))
    train = [r for r in records if r["year"] == 2024 and r["status"] == "COMPLETE" and r["label_available_ms"] < boundary]
    fit_x = np.array([r["x"] for r in train])
    raw_y = np.array([r["label"] for r in train])
    mean, scale = np.mean(fit_x, axis=0), np.maximum(np.std(fit_x, axis=0), 1e-6)

    def features(x):
        return np.r_[1.0, np.clip((x - mean) / scale, -6, 6)].astype(np.float32)

    design = np.array([features(r["x"]) for r in train], dtype=np.float64)
    w_fit = np.linalg.solve(design.T @ design + np.diag([1.0] + [50.0] * 8),
                            design.T @ np.clip(raw_y, -10, 10))
    graph = helper.make_graph([helper.make_node("MatMul", ["features", "weights"], ["prediction"])],
                              "V7ShortMarketWait", [helper.make_tensor_value_info("features", TensorProto.FLOAT, [1, 9]),
                              helper.make_tensor_value_info("weights", TensorProto.FLOAT, [9, 1])],
                              [helper.make_tensor_value_info("prediction", TensorProto.FLOAT, [1, 1])])
    model = helper.make_model(graph, producer_name="v7-market-wait", opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8
    model_path = MODELS / "market-wait.onnx"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, model_path)
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    save(MODELS / "initial-state.json", {"mean": mean.tolist(), "scale": scale.tolist(),
         "weights": w_fit.tolist(), "fit_rows": len(train), "fit_clipped_labels": int(np.sum(np.abs(raw_y) > 10))})
    selection = sorted([r for r in records if r["year"] == 2025], key=lambda r: (r["forecast_ms"] or r["source_second"] * 1000, r["index"]))
    weights, pending, forecasts, updates = w_fit.copy(), deque(), [], []
    for r in selection:
        if r["x"] is not None:
            while pending and pending[0][0]["label_available_ms"] < r["forecast_ms"]:
                old, old_x, old_pred = pending.popleft()
                vector = old_x.astype(np.float64)
                update_prediction = float(weights @ vector)
                residual = float(np.clip(old["label"], -10, 10) - update_prediction)
                weights = np.clip(weights + .02 * residual * vector / (1 + vector @ vector), -5, 5)
                if not np.all(np.isfinite(weights)):
                    raise RuntimeError("Nonfinite online state")
                updates.append({"applied_at_ms": r["forecast_ms"], "source_index": old["index"],
                                "source_ms": old["forecast_ms"], "available_ms": old["label_available_ms"],
                                "label": old["label"], "stored_prediction": old_pred,
                                "update_prediction": update_prediction,
                                "weights": json.dumps(weights.tolist(), separators=(",", ":"))})
        predictions = {}
        for role, w in (("static", w_fit), ("online", weights)):
            prediction, wait = None, False
            if r["x"] is not None:
                x = features(r["x"])
                prediction = float(session.run(None, {"features": x.reshape(1, 9), "weights": w.astype(np.float32).reshape(9, 1)})[0][0, 0])
                if not math.isfinite(prediction):
                    raise RuntimeError("ONNX inference requires correction")
                wait = prediction > .10
            predictions[role] = prediction
            complete = r["status"] == "COMPLETE"
            forecasts.append({"role": role, "index": r["index"], "position_id": r["position_id"],
                              "date": r["date"], "symbol": r["symbol"], "forecast_ms": r["forecast_ms"],
                              "eligible": r["eligible"], "status": r["status"], "prediction": prediction,
                              "label": r["label"], "label_available_ms": r["label_available_ms"],
                              "wait": int(wait), "wait_kind": r["wait_kind"] if wait else "IMMEDIATE",
                              "quote_actual_saving": r["all_wait_actual_saving"] if complete and wait else 0.0 if complete or not r["eligible"] else None,
                              "quote_stressed_saving": r["all_wait_stressed_saving"] if complete and wait else 0.0 if complete or not r["eligible"] else None,
                              "updates_known": len(updates) if role == "online" else 0})
        if r["status"] == "COMPLETE":
            pending.append((r, features(r["x"]), predictions["online"]))
    tape(OUTPUT / "forecasts.csv", forecasts)
    tape(OUTPUT / "online-updates.csv", updates)
    save(MODELS / "final-online-state.json", {"weights": weights.tolist(), "updates": len(updates),
         "pending_at_last_forecast": len(pending), "last_forecast_ms": max(r["forecast_ms"] or 0 for r in selection)})
    calendar_rows = []
    for day in range(365):
        date = str(dt.date(2025, 1, 1) + dt.timedelta(days=day))
        group = [r for r in selection if r["date"] == date]
        calendar_rows.append({"date": date, "original_market_births": len(group),
                              "eligible": sum(r["eligible"] for r in group),
                              "complete": sum(r["status"] == "COMPLETE" for r in group)})
    tape(OUTPUT / "calendar-2025.csv", calendar_rows)
    results = {}
    for role in ("static", "online"):
        rows = [r for r in forecasts if r["role"] == role]
        complete = [r for r in rows if r["status"] == "COMPLETE"]
        wait_count = sum(r["wait"] for r in complete)
        actual, stress = (sum(r[key] for r in complete) for key in ("quote_actual_saving", "quote_stressed_saving"))
        missing = sum(r["eligible"] and r["status"] != "COMPLETE" for r in rows)
        halves = {}
        for half, before in (("H1", True), ("H2", False)):
            group = [r for r in complete if (r["date"] < "2025-07-01") == before]
            halves[half] = {"complete": len(group), "waits": sum(r["wait"] for r in group),
                            "quote_actual_saving": sum(r["quote_actual_saving"] for r in group),
                            "quote_stressed_saving": sum(r["quote_stressed_saving"] for r in group)}
        gates = {"all_eligible_quotes_complete": missing == 0, "at_least25waits": wait_count >= 25,
                 "stressed_saving_at_least2USD": stress >= 2,
                 "positive_both_halves": all(h["quote_stressed_saving"] > 0 for h in halves.values())}
        results[role] = {"source_births": len(rows), "eligible": sum(r["eligible"] for r in rows),
                         "complete": len(complete), "unscored_eligible": missing,
                         "status_counts": dict(Counter(r["status"] for r in rows)), "waits": wait_count,
                         "wait_kinds": dict(Counter(r["wait_kind"] for r in complete if r["wait"])),
                         "quote_actual_saving": actual, "quote_stressed_saving": stress,
                         "raw_prediction_mse": float(np.mean([(r["prediction"] - r["label"]) ** 2 for r in complete])),
                         "halves": halves, "gates": gates, "qualifies": all(gates.values())}
    qualifying = [role for role in ("static", "online") if results[role]["qualifies"]]
    survivor = max(qualifying, key=lambda role: results[role]["quote_stressed_saving"]) if qualifying else None
    files = [Path(__file__), model_path, *sorted(MODELS.glob("*.json")), *sorted(OUTPUT.glob("*.csv"))]
    result = {"status": "COMPLETE_FROZEN_MARKET_WAIT_SELECTION", "fit_rows": len(train),
              "source_status_counts": {str(y): dict(Counter(r["status"] for r in records if r["year"] == y)) for y in (2024, 2025)},
              "roles": results, "online_updates": len(updates), "pending_at_last_forecast": len(pending),
              "selected_survivor": survivor, "candidate_2026_values_opened": False, "native_economic_verdict": None,
              "artifacts": [{"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size, "sha256": digest(p)} for p in files],
              "free_bytes": shutil.disk_usage(ROOT).free}
    save(result_path, result)
    print(json.dumps({k: v for k, v in result.items() if k != "artifacts"}, indent=2))


if __name__ == "__main__":
    main()
