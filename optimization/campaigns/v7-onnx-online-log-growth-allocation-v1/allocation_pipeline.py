"""Ordinary V7 joint log-growth fitting and sequential ONNX allocation."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnx import TensorProto, helper, numpy_helper
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
RAW = REPO/"optimization/artifacts/raw/v7-onnx-online-log-growth-allocation-v1"
EVI = ROOT/"evidence"
IDS = ["ZT-M30-US30-RANGE-COMP-61f61deaba", "ZT-M30-US30-RANGE-COMP-64efb16616",
       "ZT-H1-US100-CROSS-IN-14b72317b7", "ZT-M30-US30-INTRADAY-R-2eb111fc46",
       "ZT-H1-US30-RETURN-I-c870a788ec", "ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8"]


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest().upper()


def ref(path):
    return {"path": Path(path).relative_to(REPO).as_posix(),
            "bytes": Path(path).stat().st_size, "sha256": sha(path)}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"Production output already exists: {path}")
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def now():
    return datetime.now(timezone.utc).isoformat()


def reserve(growth=0):
    free = shutil.disk_usage(REPO).free
    if free < 30*1024**3+growth:
        raise RuntimeError("Insufficient space above 30 GiB reserve")
    return free/1024**3


def prepare():
    reserve(64*1024**2)
    spec = json.loads((EVI/"DECLARATION_V1.json").read_text())["source"]
    source = REPO/spec["path"]
    target = RAW/"input/lifecycles.csv"
    if sha(source) != spec["sha256"] or target.exists():
        raise RuntimeError("Original changed or input already exists")
    target.parent.mkdir(parents=True)
    shutil.copyfile(source, target)
    if sha(target) != spec["sha256"] or sha(source) != spec["sha256"]:
        raise RuntimeError("Physical source copy mismatch")
    save(EVI/"INPUT_COPY_V1.json", {"time_utc": now(), "file": ref(target),
                                   "features_or_outcomes_decoded": False, "free_gib": reserve()})


def read_trades(cutoff):
    path = RAW/"input/lifecycles.csv"
    expected = json.loads((EVI/"INPUT_COPY_V1.json").read_text())["file"]
    if sha(path) != expected["sha256"]:
        raise RuntimeError("Own original input changed")
    births, closes = {}, {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            # Cut timestamp before reading any numeric future label.
            if row["server_time"] >= cutoff or row["event"] not in ("BIRTH", "CLOSE"):
                continue
            if row["release_id"] != "NEXT-E03-V7R-RLO1-0bba2ca045fe":
                raise RuntimeError("Wrong original release")
            if int(row["partial_observation"]) or int(row["research_dropped_records"]):
                raise RuntimeError("Incomplete lifecycle evidence")
            dest = births if row["event"] == "BIRTH" else closes
            key = row["position_identifier"]
            if key in dest:
                raise RuntimeError("Duplicate birth/close")
            dest[key] = row
    if not closes.keys() <= births.keys():
        raise RuntimeError("Missing original birth")
    result = []
    for key, birth in births.items():
        close = closes.get(key)
        risk = float(birth["planned_risk_usd"])
        if risk <= 0:
            raise RuntimeError("Invalid original planned risk")
        result.append({"id": key, "component": IDS.index(birth["component_id"]),
                       "entry": birth["server_time"], "close": close["server_time"] if close else None,
                       "risk": risk, "actual": float(close["actual_net_usd"]) if close else None,
                       "stress": float(close["stressed_net_usd"]) if close else None})
    return sorted(result, key=lambda t: (t["entry"], int(t["id"])))


def calendar(start, end):
    current = start
    while current < end:
        yield current.strftime("%Y.%m.%d")
        current += timedelta(days=1)


def daily_vectors(trades, days):
    vectors = {day: np.zeros(6) for day in days}
    for trade in trades:
        if trade["close"] is not None and trade["close"][:10] in vectors:
            vectors[trade["close"][:10]][trade["component"]] += trade["stress"]/trade["risk"]
    return vectors


def project(scores):
    scores = np.asarray(scores, dtype=np.float64)
    if scores.shape != (5,) or not np.isfinite(scores).all() or np.any(scores <= 0):
        raise RuntimeError("Invalid ONNX allocation scores")
    low, high = 0.0, 5.0/float(scores.min())
    for _ in range(80):
        mid = (low+high)/2
        if np.clip(mid*scores, 0.25, 2).sum() < 5:
            low = mid
        else:
            high = mid
    weights = np.clip((low+high)/2*scores, 0.25, 2)
    if abs(weights.sum()-5) > 1e-9:
        raise RuntimeError("Allocation normalization failed")
    return np.append(weights, 1.0)


def fit():
    reserve(64*1024**2)
    trades = [t for t in read_trades("2025.01.01") if t["close"] is not None and t["entry"] >= "2024.01.01"]
    if len(trades) < 120:
        raise RuntimeError("Declared fit sample unavailable")
    days = list(calendar(date(2024, 1, 1), date(2025, 1, 1)))
    vectors = daily_vectors(trades, days)
    matrix = np.array([vectors[d] for d in days])

    def objective(weights):
        arguments = 1+0.04*(matrix[:, :5]@weights+matrix[:, 5])
        if np.any(arguments <= 0):
            raise RuntimeError("Nonpositive declared log-growth argument")
        value = -np.log(arguments).mean()+0.0001*np.square(weights-1).sum()
        gradient = -(0.04*matrix[:, :5]/arguments[:, None]).mean(axis=0)+0.0002*(weights-1)
        return value, gradient

    result = minimize(objective, np.ones(5), jac=True, method="SLSQP",
                      bounds=[(0.25, 2)]*5,
                      constraints=[{"type": "eq", "fun": lambda w: w.sum()-5,
                                    "jac": lambda w: np.ones(5)}],
                      options={"ftol": 1e-12, "maxiter": 1000})
    if not result.success or abs(result.x.sum()-5) > 1e-8:
        raise RuntimeError(f"Fit engineering correction required: {result.message}")
    learned_log = np.log(result.x).astype(np.float32)
    nodes = [helper.make_node("Add", ["online_log_state", "learned_log"], ["combined"]),
             helper.make_node("Clip", ["combined", "low", "high"], ["bounded"]),
             helper.make_node("Exp", ["bounded"], ["allocation_scores"])]
    initializers = [numpy_helper.from_array(learned_log, "learned_log"),
                    numpy_helper.from_array(np.array(-4, np.float32), "low"),
                    numpy_helper.from_array(np.array(4, np.float32), "high")]
    graph = helper.make_graph(nodes, "V7_Joint_Log_Growth_2024",
                              [helper.make_tensor_value_info("online_log_state", TensorProto.FLOAT, [1, 5])],
                              [helper.make_tensor_value_info("allocation_scores", TensorProto.FLOAT, [1, 5])], initializers)
    model = helper.make_model(graph, producer_name="Zeta isolated V7 log allocation",
                              opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8
    destination = ROOT/"models/allocation.onnx"
    destination.parent.mkdir(exist_ok=True)
    if destination.exists():
        raise RuntimeError("Frozen model already exists")
    onnx.save_model(model, destination)
    save(ROOT/"models/parameters.json", {"learned_log": learned_log.tolist(),
                                         "full_precision_fit_weights": result.x.tolist(),
                                         "passive_weight": 1, "daily_eta": 1,
                                         "log_state_bound": 2, "cap": [0.25, 2], "sum": 5})
    save(EVI/"FIT_RESULT_V1.json", {"time_utc": now(), "trades": len(trades), "calendar_days": len(days),
                                   "nonzero_close_days": int(np.any(matrix != 0, axis=1).sum()),
                                   "component_counts": dict(Counter(t["component"] for t in trades)),
                                   "weights": result.x.tolist()+[1.0], "solver_iterations": result.nit,
                                   "objective_value": float(result.fun), "control_objective": float(objective(np.ones(5))[0]),
                                   "model": ref(destination), "source": ref(Path(__file__)),
                                   "candidate_2025_or_2026_values_opened": False, "free_gib": reserve()})


def cash_metrics(trades, allocations, middle):
    rows = []
    for trade in trades:
        if trade["close"] is None:
            raise RuntimeError("Censored original lifecycle prevents complete screen")
        weight = float(allocations[trade["entry"][:10]][trade["component"]])
        rows.append({"id": trade["id"], "component": trade["component"], "entry": trade["entry"],
                     "close": trade["close"], "weight": weight,
                     "actual": trade["actual"]*weight, "stress": trade["stress"]*weight})
    rows.sort(key=lambda r: (r["close"], int(r["id"])))
    balance, peak, dd, index = 100.0, 100.0, 0.0, 0
    while index < len(rows):
        end = index+1
        while end < len(rows) and rows[end]["close"] == rows[index]["close"]:
            end += 1
        balance += sum(r["actual"] for r in rows[index:end])
        peak = max(peak, balance)
        dd = max(dd, 100*(peak-balance)/peak)
        index = end
    halves = {}
    for name, part in (("first", [r for r in rows if r["close"] < middle]),
                       ("second", [r for r in rows if r["close"] >= middle])):
        halves[name] = {"count": len(part), "actual": sum(r["actual"] for r in part),
                        "stress": sum(r["stress"] for r in part)}
    return {"count": len(rows), "actual": sum(r["actual"] for r in rows),
            "stress": sum(r["stress"] for r in rows), "closed_balance_dd_pct": dd,
            "halves": halves, "component_counts": dict(Counter(r["component"] for r in rows))}, rows


def development():
    reserve(64*1024**2)
    trades = [t for t in read_trades("2026.01.01") if t["entry"] >= "2025.01.01"]
    days = list(calendar(date(2025, 1, 1), date(2026, 1, 1)))
    vectors = daily_vectors(trades, days)
    output = RAW/"development"
    if output.exists():
        raise RuntimeError("Selection output already exists")
    output.mkdir(parents=True)
    session = ort.InferenceSession(str(ROOT/"models/allocation.onnx"), providers=["CPUExecutionProvider"])
    state = np.zeros(5)
    allocations = {"ONNX_FROZEN_LOG_ALLOCATION": {}, "ONNX_ONLINE_LOG_ALLOCATION": {}}
    daily_tape = []
    previous_day, previous_weights = None, None
    for day in days:
        if previous_day is not None:
            past = vectors[previous_day]
            denominator = 1+0.04*float(previous_weights@past)
            if denominator <= 0:
                raise RuntimeError("Nonpositive online utility argument")
            state = np.clip(state+0.04*past[:5]/denominator, -2, 2)
        for role in allocations:
            supplied = state if role == "ONNX_ONLINE_LOG_ALLOCATION" else np.zeros(5)
            scores = session.run(["allocation_scores"], {"online_log_state": supplied.astype(np.float32).reshape(1, 5)})[0][0]
            weights = project(scores)
            allocations[role][day] = weights
            daily_tape.append({"day_server": day, "role": role, "weights": weights.tolist(),
                               "online_log_state": supplied.tolist(), "last_consumed_day": previous_day})
        previous_day = day
        previous_weights = allocations["ONNX_ONLINE_LOG_ALLOCATION"][day]
    save(output/"daily_allocations.json", daily_tape)
    control, _ = cash_metrics(trades, {d: np.ones(6) for d in days}, "2025.07.01")
    roles, eligible = {}, []
    for role, weights in allocations.items():
        metrics, rows = cash_metrics(trades, weights, "2025.07.01")
        gates = {"actual_improves": metrics["actual"] > control["actual"],
                 "stress_improves_at_least_5pct": metrics["stress"] >= 1.05*control["stress"],
                 "halves_positive": all(h["actual"] > 0 and h["stress"] > 0 for h in metrics["halves"].values()),
                 "closed_dd_tolerance": metrics["closed_balance_dd_pct"] <= 1.10*control["closed_balance_dd_pct"],
                 "all_source_trades_represented": metrics["count"] == control["count"]}
        roles[role] = {"metrics": metrics, "gates": gates, "eligible": all(gates.values())}
        if all(gates.values()):
            eligible.append(role)
        save(output/f"{role}.json", rows)
    chosen = max(eligible, key=lambda r: (roles[r]["metrics"]["stress"], r == "ONNX_ONLINE_LOG_ALLOCATION")) if eligible else None
    save(EVI/"DEVELOPMENT_RESULT_V1.json", {"time_utc": now(), "control": control, "roles": roles,
                                           "selected_role": chosen, "daily_allocations": ref(output/"daily_allocations.json"),
                                           "role_tapes": [ref(output/f"{r}.json") for r in roles],
                                           "source": ref(Path(__file__)), "model": ref(ROOT/"models/allocation.onnx"),
                                           "limitation": "Fixed-source basket selection only; scaled historical dollars cannot prove new rounding, geometry, admission, own-label path, compound profits or native equity DD.",
                                           "candidate_2026_values_opened": False, "free_gib": reserve()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["prepare", "fit", "development"])
    phase = parser.parse_args().phase
    {"prepare": prepare, "fit": fit, "development": development}[phase]()
    print(json.dumps({"phase": phase, "status": "COMPLETE", "free_gib": reserve()}))
