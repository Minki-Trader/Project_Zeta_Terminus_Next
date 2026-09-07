"""Ordinary, campaign-owned V7 model fitting and causal selection production.

No broker API, cross-family executable, synthetic trial or native-DD estimate.
The sole input is the attributable original V7 BIRTH/CLOSE tape copied here.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnx import TensorProto, helper, numpy_helper

CAMPAIGN = Path(__file__).resolve().parent
REPO = CAMPAIGN.parents[2]
RAW = REPO / "optimization/artifacts/raw/v7-onnx-online-compounding-v1"
EVIDENCE = CAMPAIGN / "evidence"
MODEL = CAMPAIGN / "models"
COMPONENTS = [
    "ZT-M30-US30-RANGE-COMP-61f61deaba",
    "ZT-M30-US30-RANGE-COMP-64efb16616",
    "ZT-H1-US100-CROSS-IN-14b72317b7",
    "ZT-M30-US30-INTRADAY-R-2eb111fc46",
    "ZT-H1-US30-RETURN-I-c870a788ec",
    "ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8",
]


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest().upper()


def receipt(path):
    path = Path(path)
    return {"path": path.relative_to(REPO).as_posix(),
            "bytes": path.stat().st_size, "sha256": digest(path)}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite production evidence: {path}")
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def reserve(additional=0):
    free = shutil.disk_usage(REPO).free
    if free < 30 * 1024**3 + additional:
        raise RuntimeError("30 GiB reserve would be breached")
    return free / 1024**3


def stamp():
    return datetime.now(timezone.utc).isoformat()


def prepare():
    declaration = json.loads((EVIDENCE / "DECLARATION_V1.json").read_text(encoding="utf-8"))
    records = []
    reserve(64 * 1024**2)
    for item in declaration["sources"]:
        source, target = REPO / item["path"], REPO / item["copy_to"]
        if digest(source) != item["sha256"] or source.stat().st_size != item["bytes"]:
            raise RuntimeError("Declared source content mismatch")
        if target.exists():
            raise RuntimeError("Own input already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if digest(target) != item["sha256"] or digest(source) != item["sha256"]:
            raise RuntimeError("Physical input copy mismatch")
        records.append(receipt(target))
    write_json(EVIDENCE / "INPUT_COPY_V1.json", {
        "time_utc": stamp(), "files": records, "free_gib": reserve(),
        "candidate_values_decoded": False,
        "source_and_target_unchanged": True,
    })


def raw_features(birth):
    component = COMPONENTS.index(birth["component_id"])
    feature = float(birth["entry_feature"])
    direction = int(birth["direction"])
    previous = int(birth["prior_signal_direction"])
    if not math.isfinite(feature) or abs(direction) != 1 or abs(previous) > 1:
        raise RuntimeError("Invalid pre-entry feature")
    x = np.zeros(14, dtype=np.float32)
    x[component] = 1
    x[6 + component] = math.copysign(math.log1p(abs(feature)), feature)
    x[12], x[13] = direction, direction * previous
    return component, x


def observations(cutoff):
    """Cut on native server timestamp before decoding numeric outcome fields."""
    own = RAW / "input/original-v7-lifecycles.csv"
    expected = json.loads((EVIDENCE / "INPUT_COPY_V1.json").read_text())["files"][0]
    if digest(own) != expected["sha256"]:
        raise RuntimeError("Own canonical input changed")
    births, closes = {}, {}
    with own.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["server_time"] >= cutoff:
                continue
            if row["event"] not in ("BIRTH", "CLOSE"):
                continue
            if row["release_id"] != "NEXT-E03-V7R-RLO1-0bba2ca045fe":
                raise RuntimeError("Wrong original identity")
            if int(row["partial_observation"]) or int(row["research_dropped_records"]):
                raise RuntimeError("Incomplete original observation")
            key = row["position_identifier"]
            target = births if row["event"] == "BIRTH" else closes
            if key in target:
                raise RuntimeError(f"Duplicate {row['event']}: {key}")
            target[key] = row
    if not closes.keys() <= births.keys():
        raise RuntimeError("Close without birth")
    trades = []
    for key, birth in births.items():
        c, x = raw_features(birth)
        risk = float(birth["planned_risk_usd"])
        if risk <= 0:
            raise RuntimeError("Invalid original entry risk")
        close = closes.get(key)
        trade = {"id": key, "component": c, "entry": birth["server_time"],
                 "x": x, "risk": risk, "close": None, "r": None, "actual_r": None}
        if close is not None:
            if close["server_time"] < birth["server_time"]:
                raise RuntimeError("Noncausal original lifecycle")
            trade.update(close=close["server_time"],
                         r=float(close["stressed_net_usd"]) / risk,
                         actual_r=float(close["actual_net_usd"]) / risk)
            if not math.isfinite(trade["r"]) or not math.isfinite(trade["actual_r"]):
                raise RuntimeError("Nonfinite original label")
        trades.append(trade)
    return sorted(trades, key=lambda t: (t["entry"], int(t["id"])))


def fit():
    reserve(64 * 1024**2)
    trades = [t for t in observations("2025.01.01")
              if t["entry"] >= "2024.01.01" and t["close"] is not None]
    counts = Counter(t["component"] for t in trades)
    if len(trades) < 120 or any(counts[c] < 10 for c in range(6)):
        raise RuntimeError("Declared fit density not available; no substitute fit period")
    x = np.asarray([t["x"] for t in trades], dtype=np.float64)
    y = np.clip([t["r"] for t in trades], -2, 2)
    mean = x.mean(axis=0).astype(np.float32)
    scale = x.std(axis=0).astype(np.float32)
    scale[scale < 1e-8] = 1
    z = np.clip((x-mean)/scale, -5, 5)
    design = np.column_stack([z, np.ones(len(z))])
    penalty = np.eye(15) * 20
    penalty[-1, -1] = 0
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ y)
    weight = coefficients[:-1].astype(np.float32).reshape(14, 1)
    bias = coefficients[-1:].astype(np.float32)
    tensors = {"mean": mean, "scale": scale, "low": np.array(-5, dtype=np.float32),
               "high": np.array(5, dtype=np.float32), "weight": weight, "bias": bias}
    nodes = [helper.make_node("Sub", ["features", "mean"], ["centered"]),
             helper.make_node("Div", ["centered", "scale"], ["standardized"]),
             helper.make_node("Clip", ["standardized", "low", "high"], ["bounded"]),
             helper.make_node("MatMul", ["bounded", "weight"], ["linear"]),
             helper.make_node("Add", ["linear", "bias"], ["score"])]
    graph = helper.make_graph(nodes, "V7_RiskScore_2024_Frozen",
                              [helper.make_tensor_value_info("features", TensorProto.FLOAT, [1, 14])],
                              [helper.make_tensor_value_info("score", TensorProto.FLOAT, [1, 1])],
                              [numpy_helper.from_array(v, k) for k, v in tensors.items()])
    model = helper.make_model(graph, producer_name="Zeta V7 isolated Optimization",
                              opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8
    MODEL.mkdir(exist_ok=True)
    destination = MODEL / "v7-risk-score.onnx"
    if destination.exists():
        raise RuntimeError("Frozen model already exists")
    onnx.save_model(model, destination)
    write_json(MODEL / "model.json", {
        "features": 14, "component_ids": COMPONENTS,
        "mean": mean.tolist(), "scale": scale.tolist(),
        "weight": weight[:, 0].tolist(), "bias": float(bias[0]),
        "onnx": receipt(destination), "fit_cutoff_server": "2025.01.01",
        "online_learning_rate": 0.03, "online_bias_limit_r": 0.5,
    })
    write_json(EVIDENCE / "FIT_RESULT_V1.json", {
        "time_utc": stamp(), "fit_trades": len(trades), "component_counts": dict(counts),
        "max_label_time_server": max(t["close"] for t in trades),
        "onnx": receipt(destination), "model_parameters": receipt(MODEL / "model.json"),
        "source": receipt(Path(__file__)), "declaration": receipt(EVIDENCE / "DECLARATION_V1.json"),
        "fit_is_not_out_of_sample": True, "development_or_confirmation_values_opened": False,
        "free_gib": reserve(),
    })


def multiplier(score, component):
    # Passive is frozen at original geometry, quantity and risk.
    return 1.0 if component == 5 else max(0.25, min(1.0, 0.75 + 0.5 * math.tanh(score / 0.25)))


def summarize(rows, weights, predictions):
    r = np.array([t["r"] for t in rows])
    weights = np.asarray(weights)
    wr = weights * r
    downside = float(np.sqrt(np.square(np.minimum(wr, 0)).sum()))
    return {"count": len(rows), "component_counts": dict(Counter(t["component"] for t in rows)),
            "unclipped_stressed_r_sum": float(r.sum()), "weighted_stressed_r_sum": float(wr.sum()),
            "weighted_downside_norm_r": downside,
            "risk_efficiency": float(wr.sum() / downside) if downside else None,
            "stressed_r_retention": float(wr.sum() / r.sum()) if r.sum() > 0 else None,
            "mean_weight": float(weights.mean()), "min_weight": float(weights.min()),
            "max_weight": float(weights.max()),
            "score_mse_clipped_target": float(np.mean((np.asarray(predictions)-np.clip(r, -2, 2))**2))}


def evaluate(phase):
    reserve(64 * 1024**2)
    if phase == "development":
        cutoff, start, middle = "2026.01.01", "2025.01.01", "2025.07.01"
        roles = ["ONNX_COMPOUND", "ONNX_ONLINE_COMPOUND"]
    else:
        prior = json.loads((EVIDENCE / "DEVELOPMENT_RESULT_V1.json").read_text())
        if prior["selected_role"] is None:
            raise RuntimeError("No declared development survivor authorizes confirmation")
        roles = [prior["selected_role"]]
        cutoff, start, middle = "2026.07.01", "2026.01.01", "2026.04.01"
    output = RAW / phase
    if output.exists():
        raise RuntimeError("This prospective stage already has output")
    output.mkdir(parents=True)
    session = ort.InferenceSession(str(MODEL / "v7-risk-score.onnx"), providers=["CPUExecutionProvider"])
    observations_all = [t for t in observations(cutoff) if t["entry"] >= "2025.01.01"]
    # Keep every decision in the forecast tape; labels cross the cutoff as censored.
    ends = sorted([t for t in observations_all if t["close"] is not None],
                  key=lambda t: (t["close"], int(t["id"])))
    end_cursor = 0
    frozen_predictions = {}
    biases = np.zeros(6)
    all_predictions = {role: {} for role in roles}
    updates = 0
    with (output / "forecasts.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["entry_server", "position_id", "component", "frozen_score", "prior_online_bias",
                         "static_weight", "online_weight", "mature_updates_before_decision"])
        for trade in observations_all:
            while end_cursor < len(ends) and ends[end_cursor]["close"] < trade["entry"]:
                ended = ends[end_cursor]
                c = ended["component"]
                if ended["id"] not in frozen_predictions:
                    raise RuntimeError("Mature label preceded its own prediction")
                residual = np.clip(ended["r"], -2, 2) - frozen_predictions[ended["id"]]
                biases[c] = np.clip(0.97*biases[c]+0.03*residual, -0.5, 0.5)
                updates += 1
                end_cursor += 1
            score = float(session.run(["score"], {"features": trade["x"].reshape(1, 14)})[0][0, 0])
            if not math.isfinite(score):
                raise RuntimeError("Nonfinite ONNX inference")
            frozen_predictions[trade["id"]] = score
            online_score = score + biases[trade["component"]]
            for role in roles:
                all_predictions[role][trade["id"]] = online_score if role == "ONNX_ONLINE_COMPOUND" else score
            writer.writerow([trade["entry"], trade["id"], trade["component"], score,
                             biases[trade["component"]], multiplier(score, trade["component"]),
                             multiplier(online_score, trade["component"]), updates])
    judged = [t for t in observations_all if t["entry"] >= start and t["close"] is not None]
    slices = {"whole": judged, "first_half": [t for t in judged if t["entry"] < middle],
              "second_half": [t for t in judged if t["entry"] >= middle]}
    controls = {name: summarize(rows, np.ones(len(rows)), np.zeros(len(rows))) for name, rows in slices.items()}
    results, eligible = {}, []
    for role in roles:
        scores = all_predictions[role]
        metrics = {name: summarize(rows, [multiplier(scores[t["id"]], t["component"]) for t in rows],
                                  [scores[t["id"]] for t in rows]) for name, rows in slices.items()}
        gates = {"positive_halves": all(metrics[k]["weighted_stressed_r_sum"] > 0 for k in ("first_half", "second_half")),
                 "pooled_retention_at_least_90pct": metrics["whole"]["stressed_r_retention"] is not None and metrics["whole"]["stressed_r_retention"] >= 0.90,
                 "risk_efficiency_improves": metrics["whole"]["risk_efficiency"] > controls["whole"]["risk_efficiency"],
                 "all_component_rows_preserved": metrics["whole"]["component_counts"] == controls["whole"]["component_counts"]}
        results[role] = {"metrics": metrics, "gates": gates, "eligible": all(gates.values())}
        if all(gates.values()):
            eligible.append(role)
    selected = max(eligible, key=lambda r: (results[r]["metrics"]["whole"]["risk_efficiency"],
                                           r == "ONNX_ONLINE_COMPOUND")) if eligible else None
    write_json(EVIDENCE / f"{phase.upper()}_RESULT_V1.json", {
        "time_utc": stamp(), "stage": phase, "roles": results, "control": controls,
        "selected_role": selected, "period_start_server": start, "cutoff_server": cutoff,
        "forecast_count_including_2025_online_history": len(observations_all),
        "censored_decisions_in_judgment_period": sum(t["entry"] >= start and t["close"] is None for t in observations_all),
        "native_economic_or_dd_verdict": None,
        "limitation": "Teacher-population risk-normalized selection only. Altered native sizing/stops and own-label online adaptation are not replayed. No compound profit or native DD is claimed.",
        "forecasts": receipt(output / "forecasts.csv"), "model": receipt(MODEL / "v7-risk-score.onnx"),
        "source": receipt(Path(__file__)), "free_gib": reserve(),
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["prepare", "fit", "development", "confirmation"])
    command = parser.parse_args().phase
    {"prepare": prepare, "fit": fit, "development": lambda: evaluate("development"),
     "confirmation": lambda: evaluate("confirmation")}[command]()
    print(json.dumps({"phase": command, "status": "COMPLETE", "free_gib": reserve()}))
