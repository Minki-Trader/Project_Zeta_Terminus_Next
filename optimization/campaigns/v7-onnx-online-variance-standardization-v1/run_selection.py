"""Produce the complete fixed 2025 ONNX forecast and original-signal report."""
import datetime as dt
import gzip
import heapq
import json
import math
import shutil
import numpy as np
import onnxruntime as ort
from variance_signal import (FAMILY, ROOT, RAW, START, END, SERIES, record, digest,
                             samples, standardized, qlike, original_scheduled, passes)


def main():
    result_path = FAMILY / "evidence/SELECTION_RESULT_V1.json"
    output_dir = RAW / "selection"
    if result_path.exists() or output_dir.exists():
        raise RuntimeError("The complete selection is immutable; preserve prior output.")
    current_raw = sum(p.stat().st_size for p in RAW.rglob("*") if p.is_file())
    if shutil.disk_usage(ROOT).free - (256 * 2**20 - current_raw) < 30 * 2**30:
        raise RuntimeError("The remaining declared raw cap is not funded above 30 GiB.")
    freeze = json.loads((FAMILY / "evidence/MODEL_FREEZE_V1.json").read_text())
    bound = freeze["own_inputs"] + freeze["source_model"] + [freeze["declaration"]]
    for item in bound:
        if digest(ROOT / item["path"]) != item["sha256"]:
            raise RuntimeError(f"Frozen input changed: {item['path']}")
    models = json.loads((FAMILY / "model/initial.json").read_text())
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(FAMILY / "model/variance.onnx"), options,
                                   providers=["CPUExecutionProvider"])
    output_dir.mkdir(parents=True)
    results = {role: {"series": {}} for role in ("static", "online")}
    tape = output_dir / "forecasts.jsonl.gz"
    updates_path = output_dir / "online-updates.jsonl.gz"
    source_counts = {}
    with gzip.open(tape, "wt", encoding="utf-8") as tape_file, \
            gzip.open(updates_path, "wt", encoding="utf-8") as update_file:
        for kind, config in SERIES.items():
            with np.load(RAW / "inputs" / f"{kind}-bars.npz", allow_pickle=False) as source:
                bars = {k: source[k] for k in source.files}
            all_sample = samples(kind, bars)
            which = np.flatnonzero((all_sample["origin"] >= START) &
                                   (all_sample["origin"] < END))
            sample = {k: v[which] for k, v in all_sample.items()
                      if k not in ("all_origins", "feature_ready")}
            model = models[kind]
            x = standardized(sample["xraw"], model)
            original_w = np.asarray(model["weights"], dtype=np.float64)
            online_w = original_w.copy()
            predictions = {r: np.empty(len(which)) for r in results}
            pending = []
            update_count = 0
            for i, origin in enumerate(sample["origin"]):
                while pending and pending[0][0] < origin:
                    available, k = heapq.heappop(pending)
                    stored_x = x[k].astype(np.float64)
                    z = float(stored_x @ online_w)
                    tangent = math.tanh(z / 3.0)
                    variance_ratio = math.exp(3.0 * tangent)
                    gradient = ((1.0 - sample["y"][k] / variance_ratio) *
                                (1.0 - tangent * tangent)) * stored_x
                    norm = float(np.linalg.norm(gradient))
                    if norm > 10.0:
                        gradient *= 10.0 / norm
                    online_w -= 0.001 * gradient
                    update_count += 1
                    update_file.write(json.dumps({"series": kind, "number": update_count,
                        "label_origin": int(sample["origin"][k]),
                        "label_available": int(available), "consumed_before_origin": int(origin),
                        "y": float(sample["y"][k]), "stored_x": stored_x.tolist(),
                        "weights_after": online_w.tolist()}, separators=(",", ":")) + "\n")
                for role, w in (("static", original_w), ("online", online_w)):
                    value = float(session.run(["ratio"], {
                        "x": x[i:i + 1], "weights": w.astype(np.float32).reshape(8, 1)})[0][0, 0])
                    if not math.isfinite(value) or value <= 0:
                        raise RuntimeError("Nonfinite ONNX inference requires engineering correction.")
                    predictions[role][i] = value
                if sample["complete"][i] and sample["availability"][i] < END:
                    heapq.heappush(pending, (int(sample["availability"][i]), i))
                tape_file.write(json.dumps({"series": kind, "origin": int(origin),
                    "origin_index": int(sample["index"][i]),
                    "target_index": int(sample["target_index"][i]),
                    "label_available": int(sample["availability"][i]),
                    "label_complete": bool(sample["complete"][i]),
                    "y": float(sample["y"][i]) if sample["complete"][i] else None,
                    "v0": float(sample["v0"][i]), "x": x[i].tolist(),
                    "static": float(predictions["static"][i]),
                    "online": float(predictions["online"][i]),
                    "online_updates_before_forecast": update_count}, separators=(",", ":")) + "\n")
            score_mask = (sample["complete"] & (sample["availability"] < END))
            due = ((sample["availability"] > 0) & (sample["availability"] < END))
            scheduled = original_scheduled(kind, bars)
            target_map = {int(n): i for i, n in enumerate(sample["target_index"])}
            scheduled_indices = scheduled["index"]
            origin_times = bars["time"] + config["minutes"] * 60
            past_initial = np.array([n >= config["horizon"] and
                                    origin_times[n - config["horizon"]] >= START
                                    for n in scheduled_indices])
            available_prediction = np.array([int(n) in target_map for n in scheduled_indices])
            forecast_coverage = (float(np.mean(available_prediction[past_initial]))
                                 if past_initial.any() else 0.0)
            label_coverage = float(score_mask.sum() / due.sum()) if due.any() else 0.0
            original_feature = scheduled["feature"][scheduled_indices]
            original_pass = passes(kind, original_feature)
            source_counts[kind] = {"forecasts": len(which), "scored_labels": int(score_mask.sum()),
                "labels_due": int(due.sum()), "terminal_immature": int((~due).sum()),
                "causally_unavailable_origins": int(np.sum(
                    (all_sample["all_origins"] >= START) & (all_sample["all_origins"] < END) &
                    ~all_sample["feature_ready"])),
                "scheduled_original_evaluations": len(scheduled_indices),
                "scheduled_after_initial_warmup": int(past_initial.sum()),
                "scheduled_forecast_coverage": forecast_coverage,
                "due_label_coverage": label_coverage, "online_updates": update_count,
                "pending_mature_by_end_not_consumed_without_later_origin": len(pending)}
            for role in results:
                pred = predictions[role]
                v = pred[score_mask]
                y = sample["y"][score_mask]
                origins = sample["origin"][score_mask]
                constant = model["constant_ratio"]
                changed_feature = original_feature.copy()
                for j, n in enumerate(scheduled_indices):
                    if int(n) not in target_map:
                        continue
                    k = target_map[int(n)]
                    denominator = math.sqrt(config["horizon"] * sample["v0"][k] * pred[k])
                    changed_feature[j] = scheduled["numerator"][n] / denominator
                candidate_pass = passes(kind, changed_feature)
                detail = {"qlike": float(np.mean(qlike(y, v))),
                    "constant_qlike": float(np.mean(qlike(y, constant))),
                    "ratio_one_qlike": float(np.mean(qlike(y, 1.0))),
                    "raw_qlike": float(np.mean(np.log(v) + y / v)),
                    "scheduled_count": len(scheduled_indices),
                    "original_pass_count": int(original_pass.sum()),
                    "candidate_pass_count": int(candidate_pass.sum()),
                    "changed_pass_flags": int(np.sum(original_pass != candidate_pass)),
                    "signal_supply_ratio": float(candidate_pass.sum() / original_pass.sum()) if original_pass.any() else None,
                    "scheduled_forecast_coverage": forecast_coverage,
                    "due_label_coverage": label_coverage, "halves": {}}
                for name, half in (("H1", origins < 1751328000), ("H2", origins >= 1751328000)):
                    detail["halves"][name] = {"rows": int(half.sum()),
                        "qlike": float(np.mean(qlike(y[half], v[half]))),
                        "constant_qlike": float(np.mean(qlike(y[half], constant)))}
                results[role]["series"][kind] = detail
    for role, result in results.items():
        items = list(result["series"].values())
        result["pooled_qlike"] = float(np.mean([s["qlike"] for s in items]))
        result["pooled_constant_qlike"] = float(np.mean([s["constant_qlike"] for s in items]))
        result["relative_pooled_improvement"] = 1 - result["pooled_qlike"] / result["pooled_constant_qlike"]
        result["pooled_halves"] = {h: {k: float(np.mean([s["halves"][h][k] for s in items]))
                                              for k in ("qlike", "constant_qlike")} for h in ("H1", "H2")}
        result["changed_flag_fraction"] = sum(s["changed_pass_flags"] for s in items) / sum(s["scheduled_count"] for s in items)
        result["gates"] = {
            "scheduled_coverage": all(s["scheduled_forecast_coverage"] >= 0.95 for s in items),
            "mature_label_coverage": all(s["due_label_coverage"] >= 0.99 for s in items),
            "pooled_prediction_gain_2pct": result["relative_pooled_improvement"] >= 0.02,
            "both_halves_not_worse": all(s["qlike"] <= s["constant_qlike"] for s in result["pooled_halves"].values()),
            "each_series_not_worse_5pct": all(s["qlike"] <= 1.05 * s["constant_qlike"] for s in items),
            "changed_flags_5pct": result["changed_flag_fraction"] >= 0.05,
            "each_series_supply_75_to_150pct": all(s["signal_supply_ratio"] is not None and 0.75 <= s["signal_supply_ratio"] <= 1.50 for s in items),
        }
        result["qualifies"] = all(result["gates"].values())
    qualifying = [r for r in results if results[r]["qualifies"]]
    survivor = min(qualifying, key=lambda r: (results[r]["pooled_qlike"], r != "static")) if qualifying else None
    for item in bound:
        if digest(ROOT / item["path"]) != item["sha256"]:
            raise RuntimeError(f"Frozen input changed during selection: {item['path']}")
    result = {"utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "COMPLETE_FIXED_2025_PREDICTIVE_SELECTION", "survivor": survivor,
        "source_counts": source_counts, "roles": results, "native_economics": None,
        "candidate_2026_values_opened": False, "all_frozen_inputs_unchanged": True,
        "outputs": [record(tape), record(updates_path)],
        "model_freeze": record(FAMILY / "evidence/MODEL_FREEZE_V1.json"),
        "raw_bytes": sum(p.stat().st_size for p in RAW.rglob("*") if p.is_file()),
        "free_bytes": shutil.disk_usage(ROOT).free, "live_changes": False}
    if result["raw_bytes"] > 256 * 2**20:
        raise RuntimeError("Declared raw cap exceeded; preserve output for correction.")
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("outputs", "model_freeze")}, indent=2))


if __name__ == "__main__":
    main()
