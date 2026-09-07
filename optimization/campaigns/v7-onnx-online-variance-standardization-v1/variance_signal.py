"""Original V7 return-scale inputs and the declared conditional RMS model."""
from pathlib import Path
import hashlib
import math
import numpy as np

FAMILY = Path(__file__).resolve().parent
ROOT = FAMILY.parents[2]
RAW = ROOT / "optimization/artifacts/raw/v7-onnx-online-variance-standardization-v1"
START = 1735689600  # 2025-01-01, native server epoch convention
END = 1767225600    # 2026-01-01, exclusive
FIT_START = 1704067200
SERIES = {
    "cross": {"minutes": 60, "horizon": 1, "window": 120},
    "return": {"minutes": 60, "horizon": 4, "window": 120},
    "passive": {"minutes": 15, "horizon": 12, "window": 96},
}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        while block := f.read(4 * 1024 * 1024):
            h.update(block)
    return h.hexdigest().upper()


def record(path):
    path = Path(path)
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": digest(path)}


def aggregate(m1, minutes):
    bucket = (m1["time"] // (minutes * 60)) * (minutes * 60)
    times, starts, counts = np.unique(bucket, return_index=True, return_counts=True)
    return {"time": times, "open": m1["open"][starts],
            "high": np.maximum.reduceat(m1["high"], starts),
            "low": np.minimum.reduceat(m1["low"], starts),
            "close": m1["close"][starts + counts - 1],
            "observed_minutes": counts}


def make_bar_series(inputs):
    hourly = {s: aggregate(inputs[s], 60) for s in inputs}
    passive = aggregate(inputs["US100"], 15)
    own = hourly["US100"]
    log_price = np.log(own["close"])
    matched = np.ones(len(log_price), dtype=bool)
    consecutive = np.ones(len(log_price), dtype=bool)
    peer_maps = []
    for symbol in ("US30", "US500"):
        peer = hourly[symbol]
        ix = np.searchsorted(peer["time"], own["time"])
        in_range = ix < len(peer["time"])
        safe = np.minimum(ix, len(peer["time"]) - 1)
        ok = in_range & (peer["time"][safe] == own["time"])
        matched &= ok
        consecutive[1:] &= np.diff(ix) == 1
        log_price -= 0.5 * np.log(peer["close"][safe])
        peer_maps.append((peer, ix))
    cross_return = np.r_[np.nan, np.diff(log_price)]
    valid_return = matched & np.r_[False, matched[:-1]] & consecutive
    cross_return[~valid_return] = np.nan
    original_numerator = np.full(len(log_price), np.nan)
    original_variance = np.full(len(log_price), np.nan)
    for n in np.flatnonzero(matched):
        if n < 121 or any(ix[n] < 121 for _, ix in peer_maps):
            continue
        paired = np.log(own["close"][n - 121:n + 1]).copy()
        for peer, ix in peer_maps:
            p = ix[n]
            paired -= 0.5 * np.log(peer["close"][p - 121:p + 1])
        relative = np.diff(paired)
        original_numerator[n] = relative[-1]
        original_variance[n] = np.var(relative[:-1], ddof=1)
    return {
        "cross": {"time": own["time"], "log_price": log_price,
                  "r": cross_return, "matched": matched,
                  "original_numerator": original_numerator,
                  "original_variance": original_variance},
        "return": {"time": hourly["US30"]["time"],
                   "log_price": np.log(hourly["US30"]["close"]),
                   "r": np.r_[np.nan, np.diff(np.log(hourly["US30"]["close"]))]},
        "passive": {"time": passive["time"], "log_price": np.log(passive["close"]),
                    "r": np.r_[np.nan, np.diff(np.log(passive["close"]))]},
    }


def rolling(values, width, operation):
    out = np.full(len(values), np.nan)
    windows = np.lib.stride_tricks.sliding_window_view(values, width)
    if operation == "var":
        out[width - 1:] = np.var(windows, axis=1, ddof=1)
    elif operation == "mean":
        out[width - 1:] = np.mean(windows, axis=1)
    else:
        raise ValueError(operation)
    return out


def samples(kind, bars):
    cfg = SERIES[kind]
    r, times = bars["r"], bars["time"]
    horizon, width = cfg["horizon"], cfg["window"]
    origin = times + cfg["minutes"] * 60
    v0 = rolling(r, width, "var")
    square = r * r
    first = np.column_stack((square, rolling(square, 4, "mean"),
                             rolling(square, 24, "mean")))
    with np.errstate(invalid="ignore", divide="ignore"):
        first = np.log1p(first / v0[:, None])
    phase = (origin % 86400) * (2.0 * np.pi / 86400.0)
    xraw = np.column_stack((first, np.sin(phase), np.cos(phase),
                           np.sin(2 * phase), np.cos(2 * phase)))
    feature_ready = (v0 > 0) & np.isfinite(v0) & np.isfinite(xraw).all(axis=1)
    if kind == "cross":
        # W finite relative returns prove the last W+1 constituent bars align.
        feature_ready &= bars["matched"]
    index = np.flatnonzero(feature_ready)
    target_index = index + horizon
    complete = target_index < len(times)
    target = np.full(len(index), np.nan)
    availability = np.zeros(len(index), dtype=np.int64)
    for k in np.flatnonzero(complete):
        j, n = index[k], target_index[k]
        future = r[j + 1:n + 1]
        if len(future) != horizon or not np.isfinite(future).all():
            complete[k] = False
            availability[k] = origin[n]
            continue
        target[k] = float(np.sum(future)) ** 2 / (horizon * v0[j])
        availability[k] = origin[n]
    return {"index": index, "origin": origin[index], "target_index": target_index,
            "availability": availability, "complete": complete, "y": target,
            "xraw": xraw[index], "v0": v0[index],
            "all_origins": origin, "feature_ready": feature_ready}


def standardized(xraw, model):
    values = np.clip((xraw - np.asarray(model["mean"])) /
                     np.asarray(model["sd"]), -6.0, 6.0)
    # Float32 feature storage is the actual ONNX/native forecasting interface.
    return np.column_stack((np.ones(len(values)), values)).astype(np.float32)


def ratios(x, w):
    return np.exp(3.0 * np.tanh(np.asarray(x, dtype=np.float64) @ w / 3.0))


def qlike(y, v):
    ratio = np.maximum(y, 1e-10) / v
    return ratio - np.log(ratio) - 1.0


def original_scheduled(kind, bars):
    cfg = SERIES[kind]
    r, times = bars["r"], bars["time"]
    available = times + cfg["minutes"] * 60
    variance = np.r_[np.nan, rolling(r, cfg["window"], "var")[:-1]]
    numerator = np.full(len(r), np.nan)
    h = cfg["horizon"]
    for n in range(h, len(r)):
        part = r[n - h + 1:n + 1]
        if np.isfinite(part).all():
            numerator[n] = np.sum(part)
    if kind == "cross":
        numerator = bars["original_numerator"]
        variance = bars["original_variance"]
    with np.errstate(invalid="ignore", divide="ignore"):
        feature = numerator / np.sqrt(h * variance)
    if kind == "cross":
        schedule = (available % 86400 == 17 * 3600)
    elif kind == "return":
        schedule = (available % 86400 == 16 * 3600)
    else:
        schedule = ((times % 86400 >= 12 * 3600) &
                    (times % 86400 < 16 * 3600))
    schedule &= ((available >= START) & (available < END) & np.isfinite(feature))
    return {"index": np.flatnonzero(schedule), "feature": feature,
            "numerator": numerator, "available": available}


def passes(kind, values):
    return values <= -0.5 if kind == "return" else np.abs(values) >= (1.0 if kind == "passive" else 0.5)
