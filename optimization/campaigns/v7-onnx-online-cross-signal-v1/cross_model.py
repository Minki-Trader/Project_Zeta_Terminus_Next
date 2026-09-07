"""Produce the frozen direct Cross ONNX/RLS model and complete quote selection.

Native portfolio execution is conditional; quote scores are not economic proof.
"""
from collections import Counter, deque
from pathlib import Path
import calendar
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
RAW = ROOT / "optimization/artifacts/raw/v7-onnx-online-cross-signal-v1"
SYMBOLS = ("US30", "US100", "US500")


def ep(date):
    return int(np.datetime64(date, "s").astype(np.int64))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def tape(path, rows):
    if not rows:
        raise RuntimeError("Empty declared output population")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def closure_dates(year):
    # Direct translation of the original V7 native calendar, without acquisition.
    def fixed(month, day):
        d = dt.date(year, month, day)
        return d + dt.timedelta(days=(-1 if d.weekday() == 5 else 1 if d.weekday() == 6 else 0))

    def nth(month, weekday, n):
        d = dt.date(year, month, 1)
        return d + dt.timedelta(days=(weekday - d.weekday()) % 7 + 7 * (n - 1))

    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    easter = dt.date(year, (h + l - 7 * m + 114) // 31, (h + l - 7 * m + 114) % 31 + 1)
    last_may = dt.date(year, 5, 31)
    memorial = last_may - dt.timedelta(days=last_may.weekday())
    thanks = nth(11, 3, 4)
    result = {fixed(1, 1), nth(1, 0, 3), nth(2, 0, 3), easter - dt.timedelta(days=2),
              memorial, fixed(6, 19), fixed(7, 4), nth(9, 0, 1), thanks,
              fixed(12, 25), thanks + dt.timedelta(days=1)}
    for month, day in ((7, 3), (12, 24)):
        date = dt.date(year, month, day)
        if date.weekday() < 5:
            result.add(date)
    if year == 2025:
        result.add(dt.date(2025, 1, 9))
    return result


def source_population():
    arrays, hours = {}, {}
    for symbol in SYMBOLS:
        a = np.load(RAW / "input" / f"{symbol}-M1-202312-202512.npy", mmap_mode="r")
        if np.any(np.diff(a["time"]) <= 0):
            raise RuntimeError("Source ordering requires correction")
        groups = a["time"] // 3600 * 3600
        first = np.r_[0, np.flatnonzero(np.diff(groups)) + 1]
        last = np.r_[first[1:] - 1, len(a) - 1]
        arrays[symbol] = a
        hours[symbol] = {"t": groups[first], "c": a["close"][last],
                         "last": last, "last_time": a["time"][last]}
    own, a = hours["US100"], arrays["US100"]
    records, population = [], []
    counts = Counter()
    holidays = {year: closure_dates(year) for year in (2024, 2025)}
    for j, raw_t in enumerate(own["t"]):
        t = int(raw_t)
        if not ep("2024-01-01") <= t < ep("2026-01-01"):
            continue
        date = dt.datetime.fromtimestamp(t, dt.timezone.utc).date()
        year, hour = date.year, t % 86400 // 3600
        # Epoch here encodes native server calendar, without UTC conversion.
        calendar_open = date.weekday() < 5 and date not in holidays[year]
        reason = "AVAILABLE"
        closes = []
        if j < 122 or own["t"][j - 1] != t - 3600:
            reason = "LATEST_COMPLETED_H1_UNAVAILABLE"
        else:
            wanted = own["t"][j - 122:j]
            for symbol in SYMBOLS:
                h = hours[symbol]
                k = int(np.searchsorted(h["t"], t - 3600))
                if (k < 121 or k >= len(h["t"]) or h["t"][k] != t - 3600
                        or not np.array_equal(h["t"][k - 121:k + 1], wanted)):
                    reason = "SYNCHRONIZED122_UNAVAILABLE"
                    break
                closes.append(h["c"][k - 121:k + 1])
        if reason == "AVAILABLE":
            values = np.asarray(closes, dtype=np.float64)
            if not np.all(np.isfinite(values)) or np.any(values <= 0):
                raise RuntimeError("Invalid completed prices require correction")
            returns = np.log(values[:, 1:] / values[:, :-1])
            sd = np.std(returns[:, :120], axis=1, ddof=1)
            relative = returns[1] - .5 * (returns[0] + returns[2])
            rel_sd = float(np.std(relative[:120], ddof=1))
            if np.any(sd <= 0) or not np.all(np.isfinite(sd)) or rel_sd <= 0:
                reason = "PRIOR_SCALE_UNAVAILABLE"
            # The final observed M1 inside the completed bar is causal even
            # when no quote was recorded during its final minute.
        pop = {"t": t, "year": year, "hour": hour, "date": str(date),
               "calendar_open": int(calendar_open), "reason": reason}
        population.append(pop)
        counts[f"{year}_{reason}"] += 1
        if reason != "AVAILABLE":
            continue
        original_z = float(relative[-1] / rel_sd)
        x = np.array([*(returns[:, -1] / sd), original_z,
                      np.sum(returns[1, -4:]) / (2 * sd[1]),
                      np.sum(relative[-4:]) / (2 * rel_sd),
                      math.sin(2 * math.pi * hour / 24),
                      math.cos(2 * math.pi * hour / 24)])
        if not np.all(np.isfinite(x)):
            raise RuntimeError("Nonfinite causal feature")
        close = float(values[1, -1])
        past_spread = float(a["spread"][own["last"][j - 1]]) * .01
        if past_spread < 0:
            raise RuntimeError("Invalid past spread")
        start, end = np.searchsorted(a["time"], [t, t + 14400])
        y, future_close, future_spread = None, None, None
        complete = end - start == 240 and np.array_equal(a["time"][start:end], t + np.arange(240) * 60)
        if complete:
            future = a[start:end]
            if (np.any(~np.isfinite(future["close"])) or np.any(future["close"] <= 0)
                    or np.any(future["spread"] < 0)):
                raise RuntimeError("Invalid label price requires correction")
            future_close = float(future["close"][-1])
            future_spread = float(future["spread"][-1]) * .01
            y = math.log(future_close / close) / (2 * float(sd[1]))
        counts[f"{year}_" + ("COMPLETE_LABEL" if complete else "INCOMPLETE_LABEL")] += 1
        records.append({**pop, "x": x, "z": original_z, "close": close,
                        "sd4": 2 * float(sd[1]), "spread": past_spread,
                        "end": t + 14400, "y": y, "future_close": future_close,
                        "future_spread": future_spread})
    tape(RAW / "population.csv", population)
    date_rows = []
    by_date = {r["date"]: r for r in population if r["year"] == 2025 and r["hour"] == 17}
    for day in range(365):
        date = dt.date(2025, 1, 1) + dt.timedelta(days=day)
        p = by_date.get(str(date))
        date_rows.append({"date": str(date), "calendar_open": int(date.weekday() < 5 and date not in holidays[2025]),
                          "source_17h": int(p is not None), "feature_status": p["reason"] if p else "NO_SOURCE_BAR"})
    tape(RAW / "calendar-2025.csv", date_rows)
    return records, dict(counts)


def main():
    if shutil.disk_usage(ROOT).free < 30 * 2**30 + 256 * 2**20:
        raise RuntimeError("Storage reserve")
    if (FAMILY / "evidence/MODEL_SELECTION_V1.json").exists():
        raise RuntimeError("Completed bundle is immutable")
    records, counts = source_population()
    train = [r for r in records if r["year"] == 2024 and r["y"] is not None and r["end"] < ep("2025-01-01")]
    selected = [r for r in records if r["year"] == 2025]
    x = np.array([r["x"] for r in train])
    y_raw = np.array([r["y"] for r in train])
    mean, scale = np.mean(x, axis=0), np.maximum(np.std(x, axis=0), 1e-6)

    def transform(value):
        return np.r_[1.0, np.clip((value - mean) / scale, -6, 6)].astype(np.float32)

    design = np.array([transform(r["x"]) for r in train], dtype=np.float64)
    precision = design.T @ design + np.diag([1.0] + [100.0] * 8)
    covariance = np.linalg.inv(precision)
    fitted = np.linalg.solve(precision, design.T @ np.clip(y_raw, -3, 3))
    constant = float(np.mean(y_raw))
    graph = helper.make_graph([helper.make_node("MatMul", ["features", "weights"], ["prediction"])],
                              "V7DirectCross", [helper.make_tensor_value_info("features", TensorProto.FLOAT, [1, 9]),
                              helper.make_tensor_value_info("weights", TensorProto.FLOAT, [9, 1])],
                              [helper.make_tensor_value_info("prediction", TensorProto.FLOAT, [1, 1])])
    model = helper.make_model(graph, producer_name="v7-cross-direct", opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8
    model_path = FAMILY / "models/cross-direct.onnx"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, model_path)
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    dump(FAMILY / "models/initial-state.json", {"mean": mean.tolist(), "scale": scale.tolist(),
         "weights": fitted.tolist(), "covariance": covariance.tolist(), "constant_raw_mean": constant,
         "fit_rows": len(train), "fit_clipped_labels": int(np.count_nonzero(np.abs(y_raw) > 3))})
    weights, pending = fitted.copy(), deque()
    forecasts, updates, scored = [], [], {"static": [], "online": []}
    for r in selected:
        while pending and pending[0][0]["end"] < r["t"]:
            old, phi, old_pred = pending.popleft()
            vector = phi.astype(np.float64)
            px = covariance @ vector
            denominator = float(1 + vector @ px)
            if denominator <= 0 or not np.isfinite(denominator):
                raise RuntimeError("RLS numerical correction needed")
            gain = px / denominator
            current_pred = float(weights @ vector)
            residual = float(np.clip(old["y"], -3, 3) - current_pred)
            weights += gain * residual
            covariance -= np.outer(gain, vector @ covariance)
            if not np.all(np.isfinite(weights)) or not np.all(np.isfinite(covariance)):
                raise RuntimeError("Nonfinite RLS state")
            updates.append({"applied_at": r["t"], "source_t": old["t"], "label_end": old["end"],
                            "raw_label": old["y"], "stored_prediction": old_pred,
                            "update_prediction": current_pred, "denominator": denominator,
                            "weights": json.dumps(weights.tolist(), separators=(",", ":"))})
        phi = transform(r["x"])
        role_predictions = {}
        daily = r["hour"] == 17 and bool(r["calendar_open"])
        reference = int(np.sign(r["z"])) if abs(r["z"]) >= .5 else 0
        for role, w in (("static", fitted), ("online", weights)):
            prediction = float(session.run(None, {"features": phi.reshape(1, 9),
                                   "weights": w.astype(np.float32).reshape(9, 1)})[0][0, 0])
            if not math.isfinite(prediction):
                raise RuntimeError("Invalid ONNX inference")
            role_predictions[role] = prediction
            predicted_move = r["close"] * math.expm1(prediction * r["sd4"])
            direction = int(np.sign(predicted_move)) if abs(predicted_move) > 2 * max(.01, r["spread"]) else 0
            score, ref_score = None, None
            if r["y"] is not None:
                delta = r["future_close"] - r["close"]
                cost = 2 * max(.01, r["spread"], r["future_spread"])
                score = (direction * delta - (cost if direction else 0)) / r["close"] * 10000
                ref_score = (reference * delta - (cost if reference else 0)) / r["close"] * 10000
            row = {"role": role, "t": r["t"], "date": r["date"], "hour": r["hour"],
                   "daily_eligible": int(daily), "label_end": r["end"], "prediction": prediction,
                   "raw_label": r["y"], "complete_label": int(r["y"] is not None),
                   "phi": json.dumps(phi.astype(float).tolist(), separators=(",", ":")),
                   "prior_updates": len(updates) if role == "online" else 0,
                   "direction": direction, "reference_direction": reference,
                   "predicted_price_move": predicted_move, "past_spread": r["spread"],
                   "quote_score_bp": score, "reference_quote_score_bp": ref_score}
            forecasts.append(row)
            scored[role].append(row)
        if r["y"] is not None:
            pending.append((r, phi, role_predictions["online"]))
    tape(RAW / "forecasts.csv", forecasts)
    tape(RAW / "online-updates.csv", updates)
    dump(FAMILY / "models/final-online-state.json", {"weights": weights.tolist(), "covariance": covariance.tolist(),
         "updates": len(updates), "pending_at_last_forecast": len(pending), "last_forecast": selected[-1]["t"]})
    results = {}
    for role, rows in scored.items():
        complete = [r for r in rows if r["complete_label"]]
        daily_all = [r for r in rows if r["daily_eligible"]]
        daily = [r for r in daily_all if r["complete_label"]]
        mse = float(np.mean([(r["prediction"] - r["raw_label"]) ** 2 for r in complete]))
        mse_reference = float(np.mean([(constant - r["raw_label"]) ** 2 for r in complete]))
        count = sum(r["direction"] != 0 for r in daily)
        original_count = sum(r["reference_direction"] != 0 for r in daily)
        total = sum(r["quote_score_bp"] for r in daily)
        original_total = sum(r["reference_quote_score_bp"] for r in daily)
        changed = sum(r["direction"] != r["reference_direction"] for r in daily_all)
        halves = {}
        for name, check in (("H1", lambda r: r["date"] < "2025-07-01"),
                            ("H2", lambda r: r["date"] >= "2025-07-01")):
            group = [r for r in daily if check(r)]
            halves[name] = {"opportunities": len(group), "intentions": sum(r["direction"] != 0 for r in group),
                            "quote_score_bp": sum(r["quote_score_bp"] for r in group),
                            "reference_quote_score_bp": sum(r["reference_quote_score_bp"] for r in group)}
        gates = {"mse_within_2pct": mse <= 1.02 * mse_reference,
                 "positive_and_beats_reference": total > 0 and total > original_total,
                 "positive_both_halves": all(h["quote_score_bp"] > 0 for h in halves.values()),
                 "intentions_half_reference_and25": count >= max(25, .5 * original_count),
                 "changes5pct": changed >= .05 * len(daily_all),
                 "daily_labels_complete": len(daily) == len(daily_all)}
        results[role] = {"forecasts": len(rows), "complete_labels": len(complete),
                         "incomplete_labels": len(rows) - len(complete), "raw_mse": mse,
                         "reference_raw_mse": mse_reference, "daily_opportunities": len(daily_all),
                         "daily_complete_labels": len(daily), "intentions": count,
                         "reference_intentions": original_count, "changed_opportunities": changed,
                         "quote_score_bp": total, "reference_quote_score_bp": original_total,
                         "halves": halves, "gates": gates, "qualifies": all(gates.values())}
    qualifying = [role for role in ("static", "online") if results[role]["qualifies"]]
    survivor = max(qualifying, key=lambda role: results[role]["quote_score_bp"]) if qualifying else None
    files = [Path(__file__), model_path, *sorted((FAMILY / "models").glob("*.json")),
             *sorted(RAW.glob("*.csv"))]
    manifest = [{"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size, "sha256": digest(p)} for p in files]
    result = {"status": "COMPLETE_FROZEN_MODEL_SELECTION", "fit_rows": len(train), "counts": counts,
              "roles": results, "online_updates": len(updates), "pending_at_last_forecast": len(pending),
              "selected_survivor": survivor, "candidate_2026_values_opened": False,
              "native_economic_verdict": None, "calendar_dates": 365, "artifacts": manifest,
              "free_bytes": shutil.disk_usage(ROOT).free}
    dump(FAMILY / "evidence/MODEL_SELECTION_V1.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "artifacts"}, indent=2))


if __name__ == "__main__":
    main()
