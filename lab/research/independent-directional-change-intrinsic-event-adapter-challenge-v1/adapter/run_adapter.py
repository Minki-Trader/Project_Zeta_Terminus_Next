"""Causal intrinsic-event production for the frozen Family 013 contract."""
from collections import Counter, deque
from pathlib import Path
import csv
import datetime as dt
import hashlib
import json
import shutil

import numpy as np

FAMILY_ROOT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]


def fingerprint(path):
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest().upper()
    return {"path": path.relative_to(REPO).as_posix(),
            "bytes": path.stat().st_size, "sha256": digest}


def epoch(label):
    return int(dt.datetime.fromisoformat(label).replace(tzinfo=dt.timezone.utc).timestamp())


def raw_date(value):
    return dt.datetime.fromtimestamp(int(value), dt.timezone.utc).date().isoformat()


def produce_events(rows, symbol, contract):
    """Only the completed prefix is consumed; no entry/exit path lookup."""
    signal = contract["signal"]
    length = signal["prior_true_range_bars"]
    multiplier = signal["scale_multiple"]
    start, end = map(epoch, contract["periods"]["development"])
    cutoff = end - 86400 * contract["periods"]["new_entry_cutoff_calendar_days_before_end"]
    ranges = deque()
    total = 0.0
    last_time = None
    last_close = None
    direction = 0
    anchor = None
    extreme = None
    delta = None
    event_sequence = 0
    resets = 0
    events = []
    for row in rows:
        timestamp = int(row["time"])
        high, low, close = float(row["high"]), float(row["low"]), float(row["close"])
        if last_time is None or timestamp != last_time + 60:
            ranges.clear()
            total = 0.0
            last_close = None
            direction = 0
            anchor = extreme = delta = None
            resets += 1
        # The current range is deliberately added only after state decisions.
        prior_mean = total / length if len(ranges) == length else None
        if prior_mean is not None and prior_mean > 0:
            new_delta = multiplier * prior_mean
            if anchor is None:
                anchor = extreme = close
                delta = new_delta
            elif direction == 0:
                distance = close - anchor
                if abs(distance) >= delta:
                    direction = 1 if distance > 0 else -1
                    anchor = extreme = close
                    delta = new_delta
                    # Initial leg has no completed overshoot: no tradable event.
            else:
                extreme = max(extreme, close) if direction == 1 else min(extreme, close)
                changed = (direction == 1 and close <= extreme - delta) or (
                    direction == -1 and close >= extreme + delta)
                if changed:
                    overshoot = max(0.0, direction * (extreme - anchor))
                    direction = -direction
                    decision = timestamp + 60
                    event_sequence += 1
                    if start <= decision < end:
                        events.append({
                            "decision_time": decision, "signal_bar_time": timestamp,
                            "symbol": symbol, "event_sequence": event_sequence,
                            "new_direction": direction, "trigger_delta": delta,
                            "completed_overshoot": overshoot,
                            "overshoot_ratio": overshoot / delta,
                            "new_leg_delta": new_delta, "prior_mean_true_range": prior_mean,
                            "entry_allowed": int(decision < cutoff)})
                    anchor = extreme = close
                    delta = new_delta
        true_range = high - low
        if last_close is not None:
            true_range = max(true_range, abs(high - last_close), abs(low - last_close))
        if len(ranges) == length:
            total -= ranges.popleft()
        ranges.append(true_range)
        total += true_range
        last_time, last_close = timestamp, close
    return events, resets


def main():
    contract_path = FAMILY_ROOT / "config/contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
    artifact = REPO / "lab/artifacts/raw" / contract["family"]
    if shutil.disk_usage(REPO).free - contract["initial_artifact_allowance_bytes"] < contract["storage_reserve_bytes"]:
        raise RuntimeError("Storage reserve would be threatened")
    receipt_path = FAMILY_ROOT / "evidence/INPUT_COPY_V1.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    output = artifact / "structural-v1"
    if output.exists():
        raise RuntimeError("Preserve prior output; a correction requires a new attributable run")
    start, end = map(epoch, contract["periods"]["development"])
    all_events, normal_dates, source_summaries = [], set(), []
    for symbol in contract["symbols"]:
        source = artifact / "input/market" / (symbol + "-M1.npy")
        actual = fingerprint(source)
        expected = receipt["market"][symbol]["copy"]
        if actual["sha256"] != expected["sha256"] or actual["bytes"] != expected["bytes"]:
            raise RuntimeError("Input identity mismatch: " + symbol)
        rows = np.load(source, mmap_mode="r", allow_pickle=False)
        times = rows["time"]
        if len(rows) == 0 or np.any(np.diff(times) <= 0) or np.any(times % 60):
            raise RuntimeError("Invalid chronological input: " + symbol)
        if int(times.min()) < epoch(contract["periods"]["warmup"][0]) or int(times.max()) >= end:
            raise RuntimeError("Input crossed declared price bounds")
        for field in ("open", "high", "low", "close"):
            if not np.all(np.isfinite(rows[field])) or np.any(rows[field] <= 0):
                raise RuntimeError("Non-finite or invalid market observation")
        if np.any(rows["high"] < np.maximum(rows["open"], rows["close"])) or np.any(
                rows["low"] > np.minimum(rows["open"], rows["close"])):
            raise RuntimeError("Invalid OHLC geometry")
        days = {raw_date(t) for t in np.unique((times[(times >= start) & (times < end)] // 86400) * 86400)}
        normal_dates.update(days)
        events, resets = produce_events(rows, symbol, contract)
        all_events.extend(events)
        source_summaries.append({"symbol": symbol, "input": actual, "rows": len(rows),
                                 "normal_dates": len(days), "causal_resets": resets,
                                 "all_development_events": len(events)})
    all_events.sort(key=lambda e: (e["decision_time"], contract["symbols"].index(e["symbol"])))
    eligible = [event for event in all_events if event["entry_allowed"]]
    by_year = Counter(raw_date(event["decision_time"])[:4] for event in eligible)
    by_symbol = Counter(event["symbol"] for event in eligible)
    by_direction = Counter(str(event["new_direction"]) for event in eligible)
    by_date = Counter(raw_date(event["decision_time"]) for event in eligible)
    stage = contract["structural_stage"]
    density = len(eligible) / len(normal_dates)
    gates = {
        "optimistic_turnover": density >= stage["minimum_optimistic_events_per_normal_date"],
        "each_year_count": all(by_year[str(year)] >= stage["minimum_optimistic_events_each_year"]
                               for year in (2024, 2025)),
        "three_symbols": len(by_symbol) >= stage["minimum_symbols_with_events"],
        "both_directions": all(by_direction[str(sign)] > 0 for sign in (-1, 1))}
    output.mkdir(parents=True)
    fields = ["decision_time", "signal_bar_time", "symbol", "event_sequence", "new_direction",
              "trigger_delta", "completed_overshoot", "overshoot_ratio", "new_leg_delta",
              "prior_mean_true_range", "entry_allowed"]
    with (output / "events.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_events)
    with (output / "normal-days.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["raw_date", "optimistic_entry_events"])
        writer.writerows((day, by_date[day]) for day in sorted(normal_dates))
    summary = {
        "schema": "zeta-ch013-intrinsic-event-structural-result-v1",
        "recorded_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "STRUCTURAL_PASS_ECONOMICS_UNOPENED" if all(gates.values()) else
                  "STRUCTURAL_REJECTION_NO_ECONOMIC_CLAIM",
        "contract": fingerprint(contract_path), "adapter": fingerprint(Path(__file__)),
        "input_receipt": fingerprint(receipt_path),
        "source_summaries": source_summaries, "normal_dates": len(normal_dates),
        "zero_event_normal_dates": sum(by_date[d] == 0 for d in normal_dates),
        "all_events": len(all_events), "optimistic_entry_events": len(eligible),
        "events_after_calendar_entry_cutoff": len(all_events) - len(eligible),
        "optimistic_events_per_normal_date": density,
        "events_on_dates_outside_source_denominator": sum(n for day, n in by_date.items() if day not in normal_dates),
        "events_each_year": dict(by_year), "events_by_symbol": dict(by_symbol),
        "events_by_direction": dict(by_direction), "necessary_gates": gates,
        "economic_path_or_forward_return_computed": False,
        "candidate_2026_price_opened": False, "native_runtime_count": 0,
        "artifacts": [fingerprint(output / "events.csv"), fingerprint(output / "normal-days.csv")],
        "free_bytes_after": shutil.disk_usage(REPO).free}
    encoded = json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    (output / "summary.json").write_text(encoded, encoding="utf-8", newline="\n")
    evidence = FAMILY_ROOT / "evidence/STRUCTURAL_RESULT_V1.json"
    if evidence.exists():
        raise RuntimeError("Refusing to overwrite structural evidence")
    evidence.write_text(encoded, encoding="utf-8", newline="\n")
    print(json.dumps({key: summary[key] for key in (
        "status", "normal_dates", "optimistic_entry_events", "optimistic_events_per_normal_date",
        "events_each_year", "events_by_symbol", "necessary_gates", "free_bytes_after")}, indent=2))


if __name__ == "__main__":
    main()

