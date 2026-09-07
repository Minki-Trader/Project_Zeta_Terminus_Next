"""Campaign-owned native-price continuation learning and fixed-volume selection.

All executable code and mutable outputs belong to this family. Native broker
wall-clock epochs are stored as integer labels, without external-time inference.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import heapq
import json
import math
import shutil
import warnings
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnx import TensorProto, helper, numpy_helper
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPRegressor

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
RAW = REPO / "optimization/artifacts/raw/v7-onnx-online-continuation-exit-v1"
EVI = ROOT / "evidence"
IDS = ["ZT-M30-US30-RANGE-COMP-61f61deaba", "ZT-M30-US30-RANGE-COMP-64efb16616",
       "ZT-H1-US100-CROSS-IN-14b72317b7", "ZT-M30-US30-INTRADAY-R-2eb111fc46",
       "ZT-H1-US30-RETURN-I-c870a788ec", "ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8"]
HALF = [7200, 10800, 7200, 7200, 10800, 7200]


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest().upper()


def ref(path):
    return {"path": Path(path).relative_to(REPO).as_posix(),
            "bytes": Path(path).stat().st_size, "sha256": sha(path)}


def save(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite existing production: {path}")
    path.write_text(json.dumps(record, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def now():
    return datetime.now(timezone.utc).isoformat()


def epoch(label):
    # UTC here is a numeric calendar encoder, not a physical-time claim.
    return int(datetime.strptime(label, "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())


def reserve(growth=0):
    free = shutil.disk_usage(REPO).free
    if free < 30*1024**3 + growth:
        raise RuntimeError("Insufficient capacity above 30 GiB reserve")
    return free/1024**3


def prepare():
    reserve(512*1024**2)
    declaration = json.loads((EVI/"DECLARATION_V1.json").read_text())
    destination = RAW/"input"
    if destination.exists():
        raise RuntimeError("Own input already exists")
    destination.mkdir(parents=True)
    records = []
    start, end = epoch("2023.12.01 00:00:00"), epoch("2026.01.01 00:00:00")
    for source in declaration["sources"]:
        original = REPO/source["path"]
        if sha(original) != source["sha256"]:
            raise RuntimeError("Source hash differs from declaration")
        if source["name"] == "lifecycles":
            target = destination/"lifecycles.csv"
            shutil.copyfile(original, target)
            if sha(target) != source["sha256"]:
                raise RuntimeError("Lifecycle copy differs")
            item = ref(target)
        else:
            array = np.load(original, mmap_mode="r", allow_pickle=False)
            if array.dtype.itemsize != 60 or array.dtype.names != (
                    "time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"):
                raise RuntimeError("Unexpected native M1 record schema")
            left, right = np.searchsorted(array["time"], [start, end])
            target = destination/f"{source['name']}-M1.npy"
            np.save(target, np.asarray(array[left:right]), allow_pickle=False)
            item = {**ref(target), "rows": int(right-left), "source_rows": len(array),
                    "selected_start": start, "selected_end_exclusive": end, "record_bytes": 60}
            del array
        if sha(original) != source["sha256"]:
            raise RuntimeError("Original changed during physical copying")
        item["original"] = source
        records.append(item)
    save(EVI/"INPUT_COPY_V1.json", {"time_utc": now(), "files": records,
                                   "candidate_features_or_outcomes": False,
                                   "candidate_2026_price_rows_copied": False, "free_gib": reserve()})


def read_trades(cutoff):
    births, closes = {}, {}
    with (RAW/"input/lifecycles.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["server_time"] >= cutoff or row["event"] not in ("BIRTH", "CLOSE"):
                continue
            if row["release_id"] != "NEXT-E03-V7R-RLO1-0bba2ca045fe":
                raise RuntimeError("Original identity mismatch")
            if int(row["research_dropped_records"]) or int(row["partial_observation"]):
                raise RuntimeError("Incomplete source observation")
            dest = births if row["event"] == "BIRTH" else closes
            key = row["position_identifier"]
            if key in dest:
                raise RuntimeError("Duplicate original lifecycle row")
            dest[key] = row
    if not closes.keys() <= births.keys():
        raise RuntimeError("Missing source birth")
    result = []
    for key, birth in births.items():
        component = IDS.index(birth["component_id"])
        entry = epoch(birth["server_time"])
        volume, risk = float(birth["volume"]), float(birth["planned_risk_usd"])
        direction = int(birth["direction"])
        if risk <= 0 or volume <= 0 or abs(direction) != 1:
            raise RuntimeError("Invalid original entry")
        close = closes.get(key)
        result.append({"id": key, "component": component, "symbol": birth["symbol"],
                       "entry": entry, "entry_label": birth["server_time"],
                       "checkpoint": ((entry+HALF[component]+59)//60)*60,
                       "volume": volume, "risk": risk, "unit_risk": risk/volume,
                       "direction": direction, "entry_price": float(birth["entry_price"]),
                       "entry_feature": float(birth["entry_feature"]),
                       "close": epoch(close["server_time"]) if close else None,
                       "close_price": float(close["exit_price"]) if close else None,
                       "actual": float(close["actual_net_usd"]) if close else None,
                       "stress": float(close["stressed_net_usd"]) if close else None})
    return sorted(result, key=lambda t: (t["checkpoint"], int(t["id"])))


def market_inputs():
    record = json.loads((EVI/"INPUT_COPY_V1.json").read_text())
    for item in record["files"]:
        if sha(REPO/item["path"]) != item["sha256"]:
            raise RuntimeError("Own input changed")
    return {symbol: np.load(RAW/f"input/{symbol}-M1.npy", mmap_mode="r", allow_pickle=False)
            for symbol in ("US30", "US100")}


def exact_row(array, time):
    idx = int(np.searchsorted(array["time"], time))
    return array[idx] if idx < len(array) and array["time"][idx] == time else None


def side_price(row, direction, field="close"):
    return float(row[field]) + (int(row["spread"])*0.01 if direction < 0 else 0)


def state_at_checkpoint(trade, array):
    t = trade["checkpoint"]
    if trade["close"] is not None and trade["close"] <= t:
        return None, "ORIGINAL_ALREADY_CLOSED"
    right = int(np.searchsorted(array["time"], t))
    if right < 121:
        return None, "MISSING_COMPLETED_PREFIX"
    past = array[right-121:right]
    if not np.array_equal(past["time"], np.arange(t-121*60, t, 60)):
        return None, "MISSING_COMPLETED_PREFIX"
    if np.any(past["close"] <= 0) or np.any(past["spread"] < 0):
        raise RuntimeError("Invalid completed market data")
    d, unit = trade["direction"], trade["unit_risk"]
    quote = side_price(past[-1], d)
    x = np.zeros(14, np.float32)
    x[trade["component"]] = 1
    x[6] = d
    x[7] = d*(quote-trade["entry_price"])/unit
    x[8] = d*(quote-side_price(past[-31], d))/unit
    x[9] = d*(quote-side_price(past[0], d))/unit
    x[10] = (float(past[-30:]["high"].max())-float(past[-30:]["low"].min()))/unit
    x[11] = math.sqrt(30)*float(np.diff(past[-31:]["close"]).std())/unit
    x[12] = math.copysign(math.log1p(abs(trade["entry_feature"])), trade["entry_feature"])
    x[13] = int(past[-1]["spread"])*0.01/unit
    if not np.isfinite(x).all():
        raise RuntimeError("Nonfinite causal feature")
    return {"x": x, "quote": quote, "availability": t+1800}, "READY"


def matured_quote_label(trade, state, array, exclusive_end):
    # Called for training, or only after inference for sequential production.
    if state["availability"] >= exclusive_end:
        return None
    future = exact_row(array, trade["checkpoint"]+29*60)
    if future is None:
        return None
    return trade["direction"]*(side_price(future, trade["direction"])-state["quote"])/trade["unit_risk"]


def fit():
    reserve(128*1024**2)
    arrays = market_inputs()
    cutoff = epoch("2025.01.01 00:00:00")
    examples, targets, counts = [], [], Counter()
    for trade in read_trades("2025.01.01"):
        if trade["entry_label"] < "2024.01.01" or trade["checkpoint"] >= cutoff:
            continue
        state, status = state_at_checkpoint(trade, arrays[trade["symbol"]])
        counts[status] += 1
        if state is None:
            continue
        target = matured_quote_label(trade, state, arrays[trade["symbol"]], cutoff)
        if target is None:
            counts["MISSING_OR_UNMATURED_LABEL"] += 1
            continue
        examples.append(state["x"])
        targets.append(target)
    if len(examples) < 100:
        raise RuntimeError("Declared fit supply unavailable; no automatic alternative")
    x = np.asarray(examples, dtype=np.float64)
    mean = x.mean(axis=0).astype(np.float32)
    scale = x.std(axis=0).astype(np.float32)
    scale[scale < 1e-8] = 1
    z = np.clip((x-mean)/scale, -5, 5)
    network = MLPRegressor(hidden_layer_sizes=(16,), activation="tanh", solver="lbfgs",
                           alpha=10, max_iter=1000, tol=1e-8, random_state=70907)
    with warnings.catch_warnings(record=True) as messages:
        warnings.simplefilter("always")
        network.fit(z, np.clip(targets, -1, 1))
    if any(issubclass(m.category, ConvergenceWarning) for m in messages):
        raise RuntimeError("Declared fit did not converge; engineering correction before selection required")
    tensors = {"mean": mean, "scale": scale,
               "low": np.array(-5, np.float32), "high": np.array(5, np.float32),
               "w1": network.coefs_[0].astype(np.float32), "b1": network.intercepts_[0].astype(np.float32),
               "w2": network.coefs_[1].astype(np.float32), "b2": network.intercepts_[1].astype(np.float32)}
    nodes = [helper.make_node("Sub", ["features", "mean"], ["centered"]),
             helper.make_node("Div", ["centered", "scale"], ["scaled"]),
             helper.make_node("Clip", ["scaled", "low", "high"], ["bounded"]),
             helper.make_node("MatMul", ["bounded", "w1"], ["h0"]),
             helper.make_node("Add", ["h0", "b1"], ["h1"]),
             helper.make_node("Tanh", ["h1"], ["hidden"]),
             helper.make_node("MatMul", ["hidden", "w2"], ["y0"]),
             helper.make_node("Add", ["y0", "b2"], ["score"])]
    graph = helper.make_graph(nodes, "V7_Continuation_2024",
                              [helper.make_tensor_value_info("features", TensorProto.FLOAT, [1, 14])],
                              [helper.make_tensor_value_info("score", TensorProto.FLOAT, [1, 1])],
                              [numpy_helper.from_array(v, k) for k, v in tensors.items()])
    model = helper.make_model(graph, producer_name="Zeta V7 isolated continuation exit",
                              opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8
    destination = ROOT/"models/continuation.onnx"
    destination.parent.mkdir(exist_ok=True)
    if destination.exists():
        raise RuntimeError("Frozen model already exists")
    onnx.save_model(model, destination)
    save(ROOT/"models/parameters.json", {k: v.tolist() for k, v in tensors.items()})
    save(EVI/"FIT_RESULT_V1.json", {"time_utc": now(), "labels": len(targets),
                                   "observation_counts": dict(counts), "fit_iterations": network.n_iter_,
                                   "fit_loss": float(network.loss_), "model": ref(destination),
                                   "source": ref(Path(__file__)), "selection_opened": False,
                                   "candidate_2026_values_opened": False, "free_gib": reserve()})


def economics(trades, decisions):
    results = []
    for trade in trades:
        if trade["close"] is None:
            raise RuntimeError("Censored source lifecycle: complete economics unavailable")
        close = decisions.get(trade["id"])
        actual, stress, time, early = trade["actual"], trade["stress"], trade["close"], False
        if close is not None:
            gross_original = trade["direction"]*(trade["close_price"]-trade["entry_price"])*trade["volume"]
            retained_cost = min(0.0, trade["actual"]-gross_original)
            actual = trade["direction"]*(close["price"]-trade["entry_price"])*trade["volume"]+retained_cost
            debit = max(trade["actual"]-trade["stress"], close["spread"]*trade["volume"]+2*abs(retained_cost))
            stress = actual-debit
            time, early = trade["checkpoint"], True
        results.append({"id": trade["id"], "entry": trade["entry"], "close": time,
                        "component": trade["component"], "actual": actual, "stress": stress, "early": early})
    results.sort(key=lambda r: (r["close"], int(r["id"])))
    equity, peak, dd = 100.0, 100.0, 0.0
    # All same-second closes are batched before observing closed-equity DD.
    cursor = 0
    while cursor < len(results):
        end = cursor+1
        while end < len(results) and results[end]["close"] == results[cursor]["close"]:
            end += 1
        equity += sum(r["actual"] for r in results[cursor:end])
        peak = max(peak, equity)
        dd = max(dd, 100*(peak-equity)/peak)
        cursor = end
    middle = epoch("2025.07.01 00:00:00")
    halves = {}
    for label, rows in (("first", [r for r in results if r["entry"] < middle]),
                        ("second", [r for r in results if r["entry"] >= middle])):
        halves[label] = {"count": len(rows), "actual": sum(r["actual"] for r in rows),
                         "stress": sum(r["stress"] for r in rows), "early": sum(r["early"] for r in rows)}
    return {"count": len(results), "actual": sum(r["actual"] for r in results),
            "stress": sum(r["stress"] for r in results), "early": sum(r["early"] for r in results),
            "closed_balance_dd_pct": dd, "halves": halves,
            "component_counts": dict(Counter(r["component"] for r in results))}, results


def development():
    reserve(128*1024**2)
    arrays = market_inputs()
    output = RAW/"development"
    if output.exists():
        raise RuntimeError("Selection output already exists")
    output.mkdir(parents=True)
    cutoff = epoch("2026.01.01 00:00:00")
    trades = [t for t in read_trades("2026.01.01") if t["entry_label"] >= "2025.01.01"]
    session = ort.InferenceSession(str(ROOT/"models/continuation.onnx"), providers=["CPUExecutionProvider"])
    pending, biases, update_count = [], np.zeros(6), 0
    decisions = {"ONNX_CONTINUATION_EXIT": {}, "ONNX_ONLINE_CONTINUATION_EXIT": {}}
    counts = Counter()
    forecast_rows = []
    for trade in trades:
        t, c = trade["checkpoint"], trade["component"]
        if t >= cutoff:
            counts["CHECKPOINT_AFTER_BOUNDARY_HOLD"] += 1
            continue
        while pending and pending[0][0] < t:
            _, _, component, residual = heapq.heappop(pending)
            biases[component] = np.clip(0.97*biases[component]+0.03*residual, -0.25, 0.25)
            update_count += 1
        state, status = state_at_checkpoint(trade, arrays[trade["symbol"]])
        counts[status] += 1
        if state is None:
            continue
        frozen = float(session.run(["score"], {"features": state["x"].reshape(1, 14)})[0][0, 0])
        if not math.isfinite(frozen):
            raise RuntimeError("Invalid ONNX inference")
        scores = {"ONNX_CONTINUATION_EXIT": frozen, "ONNX_ONLINE_CONTINUATION_EXIT": frozen+biases[c]}
        threshold = -(float(state["x"][13])+0.02)
        actions = {role: score < threshold for role, score in scores.items()}
        # Execution quote access follows the immutable feature/decision calculation.
        opening = exact_row(arrays[trade["symbol"]], t) if any(actions.values()) else None
        for role, early in actions.items():
            if early and opening is not None:
                decisions[role][trade["id"]] = {"price": side_price(opening, trade["direction"], "open"),
                                               "spread": int(opening["spread"])*0.01}
            elif early:
                counts["MISSING_EXECUTION_QUOTE_HOLD"] += 1
        forecast_rows.append([t, trade["id"], c, frozen, biases[c], threshold,
                              int(actions["ONNX_CONTINUATION_EXIT"]), int(actions["ONNX_ONLINE_CONTINUATION_EXIT"]), update_count])
        # Future data cannot change the already-recorded decision. Label application
        # is deferred until its fixed availability time is strictly in the past.
        label = matured_quote_label(trade, state, arrays[trade["symbol"]], cutoff)
        if label is None:
            counts["MISSING_OR_UNMATURED_ONLINE_LABEL"] += 1
        else:
            heapq.heappush(pending, (state["availability"], int(trade["id"]), c, float(np.clip(label, -1, 1))-frozen))
    with (output/"forecasts.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["checkpoint_server_epoch", "position_id", "component", "frozen_score", "prior_bias", "threshold", "static_intent", "online_intent", "prior_updates"])
        writer.writerows(forecast_rows)
    control, _ = economics(trades, {})
    roles, eligible = {}, []
    for role, exits in decisions.items():
        metrics, tape = economics(trades, exits)
        gates = {"actual_improves": metrics["actual"] > control["actual"],
                 "stress_improves": metrics["stress"] > control["stress"],
                 "both_halves_positive": all(h["actual"] > 0 and h["stress"] > 0 for h in metrics["halves"].values()),
                 "early_close_supply": metrics["early"] >= 20 and all(h["early"] >= 5 for h in metrics["halves"].values()),
                 "closed_dd_tolerance": metrics["closed_balance_dd_pct"] <= 1.10*control["closed_balance_dd_pct"],
                 "all_source_trades_preserved": metrics["count"] == control["count"]}
        roles[role] = {"metrics": metrics, "gates": gates, "eligible": all(gates.values())}
        if all(gates.values()):
            eligible.append(role)
        save(output/f"{role}.json", tape)
    selected = max(eligible, key=lambda r: (roles[r]["metrics"]["stress"], r == "ONNX_ONLINE_CONTINUATION_EXIT")) if eligible else None
    save(EVI/"DEVELOPMENT_RESULT_V1.json", {"time_utc": now(), "control": control, "roles": roles,
                                           "selected_role": selected, "state_counts": dict(counts),
                                           "forecasts": ref(output/"forecasts.csv"),
                                           "role_tapes": [ref(output/f"{r}.json") for r in roles],
                                           "source": ref(Path(__file__)), "model": ref(ROOT/"models/continuation.onnx"),
                                           "limits": "Fixed original volume/occupancy. Representative M1 opening spread, conservative retained costs; no freed-capacity credit, altered native trajectory, compound-growth or native equity-DD claim.",
                                           "candidate_2026_values_opened": False, "free_gib": reserve()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["prepare", "fit", "development"])
    phase = parser.parse_args().phase
    {"prepare": prepare, "fit": fit, "development": development}[phase]()
    print(json.dumps({"phase": phase, "status": "COMPLETE", "free_gib": reserve()}))
