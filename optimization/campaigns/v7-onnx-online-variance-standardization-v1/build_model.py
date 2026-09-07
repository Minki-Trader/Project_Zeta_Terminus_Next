"""Produce the campaign's attributed native-price slice and 2024 RMS models."""
import datetime as dt
import json
import shutil
import numpy as np
import onnx
from onnx import helper, TensorProto, numpy_helper
from scipy.optimize import minimize
from variance_signal import (FAMILY, ROOT, RAW, START, FIT_START, SERIES, record,
                             digest, make_bar_series, samples, standardized, ratios, qlike)


def main():
    declaration = json.loads((FAMILY / "evidence/DECLARATION_V1.json").read_text())
    if (FAMILY / "evidence/MODEL_FREEZE_V1.json").exists():
        raise RuntimeError("The fitted model is immutable; no repeated fit.")
    remaining = 256 * 2**20 + 40 * 2**20
    if shutil.disk_usage(ROOT).free - remaining < 30 * 2**30:
        raise RuntimeError("Storage reserve cannot fund the declared initial stage.")
    inputs_dir = RAW / "inputs"
    models_dir = FAMILY / "model"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)
    sources = []
    inputs = {}
    for symbol in ("US30", "US100", "US500"):
        source = ROOT / declaration["inputs"]["source_root"] / f"{symbol}-M1.npy"
        expected = declaration["inputs"][f"{symbol}_sha256"]
        if digest(source) != expected:
            raise RuntimeError(f"Original {symbol} input changed.")
        original = np.load(source, mmap_mode="r", allow_pickle=False)
        # Timestamp-only cut occurs before accessing numeric price columns.
        lo = int(np.searchsorted(original["time"], 1701388800))
        hi = int(np.searchsorted(original["time"], 1767225600))
        target = inputs_dir / f"{symbol}-M1.npy"
        if target.exists():
            raise RuntimeError("Input destination already exists; preserve it.")
        np.save(target, np.array(original[lo:hi], copy=True), allow_pickle=False)
        if digest(source) != expected:
            raise RuntimeError("Original input changed during the physical copy.")
        sources.append({"source": record(source), "own": record(target),
                        "timestamp_slice": [lo, hi]})
        inputs[symbol] = np.load(target, mmap_mode="r", allow_pickle=False)
    bar_series = make_bar_series(inputs)
    models = {}
    fit_rows = {}
    for kind in SERIES:
        bars_path = inputs_dir / f"{kind}-bars.npz"
        np.savez_compressed(bars_path, **bar_series[kind])
        sample = samples(kind, bar_series[kind])
        mask = ((sample["origin"] >= FIT_START) & (sample["origin"] < START) &
                sample["complete"] & (sample["availability"] < START))
        rawx, y = sample["xraw"][mask], sample["y"][mask]
        if len(y) < 256:
            raise RuntimeError(f"Insufficient declared {kind} fit rows.")
        model = {"mean": rawx.mean(axis=0).tolist(),
                 "sd": np.maximum(rawx.std(axis=0), 1e-6).tolist()}
        x = standardized(rawx, model).astype(np.float64)
        def objective(w):
            t = np.tanh(x @ w / 3.0)
            v = np.exp(3.0 * t)
            loss = np.mean(np.log(v) + y / v) + 0.01 * np.dot(w[1:], w[1:])
            grad = x.T @ ((1 - y / v) * (1 - t * t)) / len(y)
            grad[1:] += 0.02 * w[1:]
            return float(loss), grad
        fit = minimize(objective, np.zeros(8), jac=True, method="L-BFGS-B",
                       options={"maxiter": 500, "ftol": 1e-12})
        if not fit.success or not np.isfinite(fit.x).all():
            raise RuntimeError(f"Fit engineering correction required: {kind}: {fit.message}")
        model.update({"weights": fit.x.tolist(),
                      "constant_ratio": float(np.clip(y.mean(), np.exp(-3), np.exp(3))),
                      "fit_rows": len(y), "optimizer_iterations": int(fit.nit),
                      "optimizer_message": str(fit.message),
                      "fit_raw_qlike": float(np.mean(np.log(ratios(x, fit.x)) + y / ratios(x, fit.x))),
                      "fit_excess_qlike": float(np.mean(qlike(y, ratios(x, fit.x)))),
                      "last_fit_label_available": int(sample["availability"][mask].max())})
        models[kind] = model
        fit_rows[kind] = len(y)
    graph = helper.make_graph([
        helper.make_node("MatMul", ["x", "weights"], ["z"]),
        helper.make_node("Div", ["z", "three"], ["bounded_input"]),
        helper.make_node("Tanh", ["bounded_input"], ["bounded"]),
        helper.make_node("Mul", ["bounded", "three"], ["log_ratio"]),
        helper.make_node("Exp", ["log_ratio"], ["ratio"]),
    ], "V7ExAnteRMS", [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 8]),
                        helper.make_tensor_value_info("weights", TensorProto.FLOAT, [8, 1])],
       [helper.make_tensor_value_info("ratio", TensorProto.FLOAT, [1, 1])],
       [numpy_helper.from_array(np.array([3.0], dtype=np.float32), "three")])
    graph_model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)],
                                    producer_name="V7 variance standardization")
    graph_model.ir_version = 8
    onnx.save_model(graph_model, models_dir / "variance.onnx")
    model_path = models_dir / "initial.json"
    model_path.write_text(json.dumps(models, indent=2) + "\n", encoding="utf-8")
    evidence = {"utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "status": "ALL_THREE_2024_MODELS_FITTED_ONCE_SELECTION_NOT_RUN",
                "declaration": record(FAMILY / "evidence/DECLARATION_V1.json"),
                "source_inputs": sources,
                "own_inputs": [record(p) for p in sorted(inputs_dir.iterdir())],
                "source_model": [record(FAMILY / p) for p in
                                 ("variance_signal.py", "build_model.py", "run_selection.py",
                                  "model/initial.json", "model/variance.onnx")],
                "fit_rows": fit_rows, "candidate_2026_values_opened": False,
                "raw_bytes": sum(p.stat().st_size for p in RAW.rglob("*") if p.is_file()),
                "free_bytes": shutil.disk_usage(ROOT).free,
                "live_changes": False}
    (FAMILY / "evidence/MODEL_FREEZE_V1.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": evidence["status"], "fit_rows": fit_rows,
                      "raw_bytes": evidence["raw_bytes"], "free_bytes": evidence["free_bytes"],
                      "models": models}, indent=2))


if __name__ == "__main__":
    main()
