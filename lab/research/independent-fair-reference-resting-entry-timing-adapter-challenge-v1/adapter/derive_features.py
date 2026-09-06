"""Produce causal Family 014 M1 features and structural supply from sealed own ticks."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import math
import shutil

import numpy as np
from numba import njit

FAMILY_ROOT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
BAR_DTYPE = np.dtype([
    ("minute", "<i8"), ("close_msc", "<i8"), ("close_bid", "<f8"), ("close_ask", "<f8"),
    ("close_month", "<i4"), ("close_row", "<i8"), ("close_source_ordinal", "<i8"),
    ("discovery_msc", "<i8"), ("discovery_month", "<i4"), ("discovery_row", "<i8"),
    ("discovery_source_ordinal", "<i8")])
EVENT_DTYPE = np.dtype(BAR_DTYPE.descr + [
    ("event_id", "<i8"), ("nominal_bar_end_msc", "<i8"),
    ("mid_close", "<f8"), ("reference", "<f8"), ("sigma", "<f8"),
    ("direction", "i1"), ("age_ms", "<i8"), ("fresh", "?"),
    ("optimistic_entry_period", "?")])


def fingerprint(path):
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest().upper()
    return {"path": path.relative_to(REPO).as_posix(),
            "bytes": path.stat().st_size, "sha256": digest}


def save_json(path, value):
    if path.exists():
        raise RuntimeError("Existing sealed feature output must remain attributable")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8", newline="\n")
    temporary.replace(path)


def save_array(path, values):
    if path.exists():
        raise RuntimeError("Existing feature tape is not overwritten by a rerun")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    with temporary.open("wb") as handle:
        np.save(handle, values, allow_pickle=False)
    temporary.replace(path)
    return fingerprint(path)


def ms(date):
    return int(dt.datetime.fromisoformat(date).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def make_block(ticks, ending_rows, discovery_rows, month, offset):
    block = np.empty(len(ending_rows), dtype=BAR_DTYPE)
    block["minute"] = ticks["time_msc"][ending_rows] // 60000
    block["close_msc"] = ticks["time_msc"][ending_rows]
    block["close_bid"], block["close_ask"] = ticks["bid"][ending_rows], ticks["ask"][ending_rows]
    block["close_month"] = month
    block["close_row"], block["close_source_ordinal"] = ending_rows, ending_rows + offset
    block["discovery_msc"] = ticks["time_msc"][discovery_rows]
    block["discovery_month"] = month
    block["discovery_row"], block["discovery_source_ordinal"] = discovery_rows, discovery_rows + offset
    return block


def completed_bars(chunks):
    """A later quote finalizes a prefix; a later gap never removes that prefix."""
    blocks, pending, offset = [], None, 0
    for chunk in chunks:
        path = REPO / chunk["ticks"]["path"]
        if fingerprint(path) != chunk["ticks"]:
            raise RuntimeError("Owned sealed tick input drift")
        ticks = np.load(path, mmap_mode="r", allow_pickle=False)
        if len(ticks) != chunk["rows"] or ticks.dtype.itemsize != 60:
            raise RuntimeError("Unexpected native tick record layout/count")
        minute = ticks["time_msc"] // 60000
        month = int(chunk["month"])
        if pending is not None:
            if minute[0] < pending["minute"]:
                raise RuntimeError("Monthly source chronology reversed")
            if minute[0] > pending["minute"]:
                block = np.empty(1, dtype=BAR_DTYPE)
                for key in ("minute", "close_msc", "close_bid", "close_ask", "close_month",
                            "close_row", "close_source_ordinal"):
                    block[key] = pending[key]
                block["discovery_msc"] = ticks["time_msc"][0]
                block["discovery_month"] = month
                block["discovery_row"], block["discovery_source_ordinal"] = 0, offset
                blocks.append(block)
        changes = np.flatnonzero(minute[1:] != minute[:-1]) + 1
        if len(changes):
            blocks.append(make_block(ticks, changes - 1, changes, month, offset))
        last = len(ticks) - 1
        pending = {"minute": int(minute[last]), "close_msc": int(ticks["time_msc"][last]),
                   "close_bid": float(ticks["bid"][last]), "close_ask": float(ticks["ask"][last]),
                   "close_month": month, "close_row": last, "close_source_ordinal": offset + last}
        offset += len(ticks)
        del ticks, minute, changes
    if not blocks:
        raise RuntimeError("No completed source bars")
    bars = np.concatenate(blocks)
    if (np.any(np.diff(bars["minute"]) <= 0) or
            np.any(np.diff(bars["discovery_source_ordinal"]) <= 0) or
            np.any(bars["discovery_msc"] < (bars["minute"] + 1) * 60000)):
        raise RuntimeError("Causal bar chronology is inconsistent")
    return bars, pending, offset


@njit(cache=True)
def causal_excursions(minutes, midpoints, lookback, minimum_sigma):
    size = len(minutes)
    reference = np.full(size, np.nan)
    sigma = np.full(size, np.nan)
    direction = np.zeros(size, dtype=np.int8)
    window = np.zeros(lookback, dtype=np.float64)
    count, cursor, previous = 0, 0, -1
    armed = False
    gap_count, qualified_bars, low_sigma_bars = 0, 0, 0
    for i in range(size):
        if previous >= 0 and minutes[i] != previous + 1:
            count, cursor, armed = 0, 0, False
            gap_count += 1
        if count == lookback:
            mean = 0.0
            for j in range(lookback):
                mean += window[j]
            mean /= lookback
            variance = 0.0
            for j in range(lookback):
                residual = window[j] - mean
                variance += residual * residual
            sd = math.sqrt(variance / lookback)
            reference[i], sigma[i] = mean, sd
            qualified_bars += 1
            if sd < minimum_sigma:
                low_sigma_bars += 1
            distance = midpoints[i] - mean
            if abs(distance) <= sd:
                armed = True
            elif armed and sd >= minimum_sigma:
                direction[i] = 1 if distance < 0 else -1
                armed = False
        window[cursor] = midpoints[i]
        cursor = (cursor + 1) % lookback
        if count < lookback:
            count += 1
        previous = minutes[i]
    return reference, sigma, direction, gap_count, qualified_bars, low_sigma_bars


def main():
    contract = json.loads((FAMILY_ROOT / "config/contract.json").read_text(encoding="utf-8-sig"))
    artifact = REPO / "lab/artifacts/raw" / contract["family"]
    feature_root = artifact / "features"
    freeze = json.loads((FAMILY_ROOT / "evidence/PREFEATURE_IMPLEMENTATION_FREEZE_V1.json").read_text(encoding="utf-8-sig"))
    for item in freeze["files"]:
        if fingerprint(REPO / item["path"]) != item:
            raise RuntimeError("Frozen feature implementation/source authority drift")
    acquisition_path = FAMILY_ROOT / "evidence/INPUT_ACQUISITION_V1.json"
    acquisition = json.loads(acquisition_path.read_text(encoding="utf-8-sig"))
    shutdown = json.loads((FAMILY_ROOT / "evidence/SOURCE_READER_SHUTDOWN_V1.json").read_text(encoding="utf-8-sig"))
    if (acquisition["status"] != "COMPLETE_SOURCE_INPUTS_FEATURES_UNOPENED" or
            len(acquisition["completed"]) != 75 or not shutdown["normal_exit_completed"] or
            shutdown["remaining_exact_path_process_count"] != 0 or shutdown["capture_exit_code"] != 0):
        raise RuntimeError("Complete sealed inputs and normal source shutdown are prerequisites")
    if shutil.disk_usage(REPO).free - 1024**3 < contract["storage"]["minimum_free_bytes"]:
        raise RuntimeError("Structural output would threaten 30 GiB storage reserve")
    if feature_root.exists():
        raise RuntimeError("Do not overwrite an existing feature production attempt")
    feature_root.mkdir(parents=True)
    source = json.loads((artifact / "input/spec/current-contract-source.json").read_text(encoding="utf-8-sig"))
    start, end = map(ms, contract["periods"]["development"])
    cutoff = end - contract["periods"]["new_entry_cutoff_calendar_days_before_end"] * 86400000
    m1_days, tick_days = set(), set()
    by_symbol, by_year, by_direction, by_day, outputs = {}, {}, {}, {}, []
    for chunk in acquisition["completed"]:
        if "202401" <= chunk["month"] <= "202512":
            m1_days.update(chunk["source_m1_calendar_days_raw_epoch"])
            tick_days.update(chunk["quote_days_raw_epoch"])
    normal_days = sorted(m1_days | tick_days)
    if not normal_days:
        raise RuntimeError("All-source development calendar is empty")
    total_optimistic, total_fresh = 0, 0
    for symbol in contract["symbols"]:
        chunks = sorted((x for x in acquisition["completed"] if x["symbol"] == symbol),
                        key=lambda x: x["month"])
        bars, unresolved, consumed = completed_bars(chunks)
        mid = (bars["close_bid"] + bars["close_ask"]) / 2
        result = causal_excursions(
            bars["minute"], mid, contract["signal"]["reference_completed_M1_bars"],
            source["symbols"][symbol]["trade_tick_size"] * contract["signal"]["minimum_sigma_tick_sizes"])
        reference, sigma, directions, gaps, qualified, low_sigma = result
        # Emission belongs to actual discovery, with nominal age preserved separately.
        selected = np.flatnonzero((directions != 0) & (bars["discovery_msc"] >= start) &
                                  (bars["discovery_msc"] < end))
        events = np.empty(len(selected), dtype=EVENT_DTYPE)
        for name in BAR_DTYPE.names:
            events[name] = bars[name][selected]
        events["event_id"] = np.arange(1, len(selected) + 1)
        events["nominal_bar_end_msc"] = (bars["minute"][selected] + 1) * 60000
        events["mid_close"], events["reference"], events["sigma"] = mid[selected], reference[selected], sigma[selected]
        events["direction"] = directions[selected]
        events["age_ms"] = events["discovery_msc"] - events["nominal_bar_end_msc"]
        events["fresh"] = events["age_ms"] <= contract["signal"]["freshness_ms"]
        events["optimistic_entry_period"] = ((events["nominal_bar_end_msc"] >= start) &
            (events["nominal_bar_end_msc"] < cutoff) & (events["discovery_msc"] < cutoff))
        optimistic = events[events["optimistic_entry_period"]]
        fresh_count = int(np.count_nonzero(optimistic["fresh"]))
        total_optimistic += len(optimistic)
        total_fresh += fresh_count
        for item in optimistic:
            day = int(item["discovery_msc"] // 86400000)
            if day not in m1_days and day not in tick_days:
                raise RuntimeError("An emitted event is missing from all-source dates")
            date = dt.datetime.fromtimestamp(day * 86400, tz=dt.timezone.utc)
            year, day_text = str(date.year), date.date().isoformat()
            sign = "LONG" if item["direction"] == 1 else "SHORT"
            by_year[year] = by_year.get(year, 0) + 1
            by_direction[sign] = by_direction.get(sign, 0) + 1
            by_day[day_text] = by_day.get(day_text, 0) + 1
        outputs.append(save_array(feature_root / f"{symbol}-completed-bars.npy", bars))
        outputs.append(save_array(feature_root / f"{symbol}-events.npy", events))
        by_symbol[symbol] = {
            "tick_rows_consumed": consumed, "completed_bars": len(bars),
            "complete_reference_bars": int(qualified), "gap_resets": int(gaps),
            "below_tick_sigma_bars": int(low_sigma), "development_excursions": len(events),
            "optimistic_pre_cutoff_events": len(optimistic), "fresh_pre_cutoff_events": fresh_count,
            "late_pre_cutoff_events_retained": len(optimistic) - fresh_count,
            "last_observed_bar_unfinalized_without_later_quote": {
                key: value for key, value in unresolved.items()
                if key not in ("close_bid", "close_ask")},
            "long": int(np.count_nonzero(optimistic["direction"] == 1)),
            "short": int(np.count_nonzero(optimistic["direction"] == -1))}
        print(json.dumps({"status": "STRUCTURAL_SYMBOL_COMPLETE", "symbol": symbol,
                          "optimistic_events": len(optimistic), "fresh_events": fresh_count}), flush=True)
        del bars, mid, reference, sigma, directions, events, optimistic, result
    dates = [dt.datetime.fromtimestamp(day * 86400, tz=dt.timezone.utc).date().isoformat()
             for day in normal_days]
    for day_text in dates:
        by_day.setdefault(day_text, 0)
    gates = {
        "optimistic_supply": total_optimistic / len(dates) >= contract["structural_stage"]["minimum_optimistic_events_per_normal_date"],
        "each_year": all(by_year.get(year, 0) >= contract["structural_stage"]["minimum_events_each_year"]
                         for year in ("2024", "2025")),
        "three_symbols": sum(x["optimistic_pre_cutoff_events"] > 0 for x in by_symbol.values()) >= 3,
        "both_directions": all(by_direction.get(sign, 0) > 0 for sign in ("LONG", "SHORT"))}
    result = {
        "schema": "zeta-ch014-structural-supply-v1",
        "recorded_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "NECESSARY_STRUCTURAL_SUPPLY_PASSED_NO_ECONOMICS" if all(gates.values()) else
                  "NECESSARY_STRUCTURAL_SUPPLY_FAILED_NO_ECONOMICS",
        "input_authority": fingerprint(acquisition_path), "feature_freeze": fingerprint(
            FAMILY_ROOT / "evidence/PREFEATURE_IMPLEMENTATION_FREEZE_V1.json"),
        "contract": fingerprint(FAMILY_ROOT / "config/contract.json"),
        "calendar": {"source_m1_dates": len(m1_days), "source_tick_dates": len(tick_days),
                     "union_dates": len(dates), "m1_only_days": sorted(m1_days - tick_days),
                     "tick_only_days": sorted(tick_days - m1_days), "dates": dates},
        "optimistic_events": total_optimistic, "optimistic_events_per_normal_date": total_optimistic / len(dates),
        "fresh_pre_cutoff_events": total_fresh,
        "zero_optimistic_event_dates": sum(count == 0 for count in by_day.values()),
        "events_by_year": by_year, "events_by_direction": by_direction,
        "events_by_day": dict(sorted(by_day.items())), "symbols": by_symbol,
        "necessary_gates": gates, "outputs": outputs,
        "structural_interpretation": "Pre-cutoff upper-bound supply ignores freshness expiry, pending expiry, existing liability, geometry, volume and margin rejection. Late events remain recorded; fresh subset is separately reported. Every real fill later must pass the original 5000 ms gate and all monetary rules.",
        "discovery_chronology": "Events belong to their first actual discovery quote. Record nominal bar end and age; don't drop a valid-prefix event because a later gap was discovered. Last bar without a later quote is unfinalized, not force-closed.",
        "economics_fills_forward_returns_computed": False,
        "locked_2026_or_native_candidate_opened": False,
        "free_bytes_after": shutil.disk_usage(REPO).free}
    save_json(FAMILY_ROOT / "evidence/STRUCTURAL_SUPPLY_V1.json", result)
    print(json.dumps({key: result[key] for key in ("status", "optimistic_events",
                      "optimistic_events_per_normal_date", "fresh_pre_cutoff_events", "necessary_gates")}), flush=True)


if __name__ == "__main__":
    main()
