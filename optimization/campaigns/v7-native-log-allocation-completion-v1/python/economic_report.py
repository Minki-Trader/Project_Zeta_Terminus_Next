"""Produce monetary, drawdown, calendar and actual-quantity evidence from MT5.

The archived native path is the economic source. This program does not change
an EA, model, signal, period or gate, and does not manufacture scaled profits.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import csv
import json
import math
import re
import sys

from native_run import FAMILY, ROOT, RAW, EVIDENCE, binding, save, utc


def decode(path):
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe"):
        return data.decode("utf-16")
    if data.count(b"\0") > len(data) // 5:
        return data.decode("utf-16-le")
    return data.decode("utf-8-sig")


class ReportRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        if tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def tokens(line):
    return dict(re.findall(r"(\w+)=([^\s]+)", line))


def unique_marker(log, marker):
    rows = [line for line in log.splitlines() if marker in line]
    if len(rows) != 1:
        raise ValueError(f"Complete native {marker} count must be one, observed {len(rows)}")
    return tokens(rows[0])


def produce(tag):
    output = EVIDENCE / (tag + "-economics.json")
    if output.exists():
        raise ValueError("Preserve existing economics; use a new report identity for corrections")
    archive_file = EVIDENCE / (tag + "-archive.json")
    archive = json.loads(archive_file.read_text())
    path = RAW / "native" / tag
    logs = [p for p in (path / "logs/Tester").rglob("*.log") if "Agent-" in str(p)]
    log = "\n".join(decode(p) for p in logs)
    native = unique_marker(log, "V7RR1_NATIVE ")
    core = unique_marker(log, "V7RR1_RESULT ")
    learning = unique_marker(log, "V7LAC_RESULT ")
    if "V7LAC_FAULT" in log or "critical error" in log.lower() or core["status"] != "ECONOMIC":
        raise ValueError("Native execution requires engineering correction, not economic judgment")
    if any(int(learning[k]) != 0 for k in ["faults", "unknown_marks", "positions"]):
        raise ValueError("Incomplete native learning/equity evidence")
    reports = list((path / "reports").glob("*.htm")) + list((path / "reports").glob("*.html"))
    if len(reports) != 1:
        raise ValueError("One full native HTML economic report is required")
    parser = ReportRows()
    parser.feed(decode(reports[0]))
    pairs = defaultdict(list)
    for row in parser.rows:
        for i, cell in enumerate(row[:-1]):
            if cell.endswith(":"):
                pairs[cell].append(row[i + 1])
    quality = (pairs.get("히스토리 품질:") or pairs.get("History Quality:") or [None])[0]
    if quality is None or not quality.startswith("100%") or not any(s in quality.lower() for s in ["실제 틱", "real ticks"]):
        raise ValueError("Native history quality is not the required 100% real ticks")
    period = (pairs.get("주기:") or pairs.get("Period:") or [None])[0]
    deposit = (pairs.get("입금액:") or pairs.get("Initial Deposit:") or [None])[0]
    leverage = (pairs.get("레버리지:") or pairs.get("Leverage:") or [None])[0]
    if period != "M30 (2025.01.01 - 2026.01.01)" or deposit != "100.00" or leverage != "1:100":
        raise ValueError("Native report period, reference capital or leverage differs from the declaration")
    coverage = {}
    for symbol in ["US30", "US100", "US500"]:
        match = re.search(re.escape(symbol) + r": generate (\d+) ticks.*?passed to tester (\d+) ticks", log)
        if not match:
            raise ValueError("Native all-symbol tick coverage missing: " + symbol)
        coverage[symbol] = {"generated_ticks": int(match[1]), "passed_ticks": int(match[2])}
    contracts = defaultdict(dict)
    for line in log.splitlines():
        if "V7RR1_CONTRACT " in line:
            row = tokens(line)
            stage, symbol = row.pop("stage"), row.pop("symbol")
            contracts[stage][symbol] = row
    if set(contracts["START"]) != set(coverage) or contracts["START"] != contracts["END"]:
        raise ValueError("Native contract/financing fingerprints changed or are incomplete")
    if archive["exit_code"] != 0 or archive["changed_frozen_files"]:
        raise ValueError("Native exit or immutable source/history binding is invalid")
    history_file = EVIDENCE / (tag + "-history.json")
    history = json.loads(history_file.read_text())
    if not history["all_twelve_streams_match_initial"] or not history["contracts_match_initial"]:
        raise ValueError("Native post-run complete bars or synchronized contracts changed")

    entries = list(csv_rows(path / "files/learning/entries.csv"))
    closes = list(csv_rows(path / "files/learning/closes.csv"))
    days = list(csv_rows(path / "files/learning/days.csv"))
    initial = {row["position_id"]: row for row in entries}
    if len(initial) != len(entries):
        raise ValueError("Duplicate initial lifecycle attribution")
    lives = defaultdict(lambda: {"actual": 0.0, "stressed": 0.0, "positive_swap": 0.0, "full": 0})
    for row in closes:
        identity = row["position_id"]
        if identity not in initial:
            raise ValueError("Completed deal has no original entry risk attribution")
        life = lives[identity]
        life["actual"] += float(row["deal_actual"])
        life["stressed"] += float(row["deal_stressed"])
        life["positive_swap"] += float(row["deal_positive_swap"])
        life["component"] = int(row["component"])
        if int(row["full_exit"]):
            life["full"] += 1
            life["close_msc"] = int(row["close_msc"])
            life["r"] = float(row["completed_r"])
            if abs(life["stressed"] / float(initial[identity]["reserved_entry_risk"]) - life["r"]) > 1e-8:
                raise ValueError("Completed label does not reconcile to own initial reserved risk")
    if set(lives) != set(initial) or any(v["full"] != 1 for v in lives.values()):
        raise ValueError("Native complete lifecycle accounting is not flat and one-to-one")
    if len(lives) != int(learning["labels"]) or len(lives) != int(learning["births"]) or len(lives) != int(core["closed"]):
        raise ValueError("Native lifecycle counts do not reconcile")
    for day in days:
        midnight = int(day["completed_day"]) + 86400
        if int(day["observed_server"]) < midnight or int(day["max_close_msc"]) >= midnight * 1000:
            raise ValueError("A day allocation used a non-mature label")
    actual = sum(v["actual"] for v in lives.values())
    original_stress = sum(v["stressed"] for v in lives.values())
    positive_swap = sum(v["positive_swap"] for v in lives.values())
    conservative = original_stress - positive_swap
    if abs(actual - float(native["profit"])) > 1e-5 or abs(original_stress - float(core["stressed_net"])) > 1e-5:
        raise ValueError("Whole-path native money does not reconcile")
    boundary = int(datetime(2025, 7, 1, tzinfo=timezone.utc).timestamp())
    epochs = {"2025H1": {"actual_closed": 0.0, "conservative_closed": 0.0},
              "2025H2": {"actual_closed": 0.0, "conservative_closed": 0.0}}
    for life in lives.values():
        key = "2025H1" if life["close_msc"] < boundary * 1000 else "2025H2"
        epochs[key]["actual_closed"] += life["actual"]
        epochs[key]["conservative_closed"] += life["stressed"] - life["positive_swap"]
    peaks = {"actual": 100.0, "stress": 100.0}
    sampled_dd = {"actual": 0.0, "stress": 0.0}
    equity_count = 0
    last = None
    boundary_before = None
    boundary_after = None
    minute_quantity = Counter()
    curve = []
    last_day = None
    for row in csv_rows(path / "files/learning/equity.csv"):
        if int(row["known"]) != 1 or int(row["faults"]) != 0:
            raise ValueError("Unknown native capital mark")
        stamp = int(row["server_time"])
        account = float(row["equity"])
        stress = float(row["conservative_mark"])
        for key, value in [("actual", account), ("stress", stress)]:
            peaks[key] = max(peaks[key], value)
            sampled_dd[key] = max(sampled_dd[key], peaks[key] - value)
        if stamp < boundary:
            boundary_before = row
        elif boundary_after is None:
            boundary_after = row
        minute_quantity[row["day_multiplier"]] += 1
        day = stamp // 86400
        if day != last_day:
            curve.append({"server_time": stamp, "equity": account, "conservative_mark": stress,
                          "day_multiplier": int(row["day_multiplier"])})
            last_day = day
        equity_count += 1
        last = row
    if last is None or equity_count != int(learning["equity_rows"]) or int(last["positions"]) != 0:
        raise ValueError("Incomplete final equity path")
    if abs(float(last["equity"]) - 100 - actual) > 1e-5 or abs(float(last["conservative_mark"]) - 100 - conservative) > 1e-5:
        raise ValueError("Final flat native marks do not reconcile")
    if boundary_before is None or boundary_after is None:
        raise ValueError("Half-year marked evidence is missing")
    # Carry the final observed pre-boundary mark into the next epoch. Record the
    # first following quote as well; no synthetic midnight market price is invented.
    mid_actual = float(boundary_before["equity"])
    mid_stress = float(boundary_before["conservative_mark"])
    epochs["2025H1"].update(actual_marked=mid_actual - 100, conservative_marked=mid_stress - 100)
    epochs["2025H2"].update(actual_marked=100 + actual - mid_actual, conservative_marked=100 + conservative - mid_stress)
    cash_dd = float(native["equity_dd"])
    closed_dd = float(core["stressed_dd"])
    denominator = max(cash_dd, closed_dd, sampled_dd["stress"], .01)
    quantity = Counter(row["volume"] for row in entries)
    by_component = defaultdict(Counter)
    for row in entries:
        by_component[row["component"]][row["volume"]] += 1
    result = {"utc": utc(), "status": "COMPLETE_VALID_FULL2025_NATIVE_ECONOMICS", "tag": tag,
              "archive": binding(archive_file), "native_html": binding(reports[0]), "history": binding(history_file),
              "producer": binding(Path(__file__).resolve()), "initial_capital": 100,
              "period": "2025-01-01 through2026-01-01 exclusive", "history_quality": quality,
              "native_report_contract": {"period": period, "deposit": deposit, "leverage": leverage},
              "tick_coverage": coverage, "contract_fingerprints": dict(contracts), "native": native,
              "core": core, "learning": learning, "closed_lifecycles": len(lives),
              "actual_net": actual, "original_stressed_net": original_stress,
              "positive_realized_swap": positive_swap, "conservative_stressed_net": conservative,
              "actual_terminal_wealth": 100 + actual, "conservative_terminal_wealth": 100 + conservative,
              "actual_log_growth": math.log((100 + actual) / 100) if 100 + actual > 0 else None,
              "conservative_log_growth": math.log((100 + conservative) / 100) if 100 + conservative > 0 else None,
              "native_relative_equity_dd_pct": float(native["equity_dd_relative_pct"]),
              "native_cash_equity_dd": cash_dd, "original_stressed_closed_dd": closed_dd,
              "conservative_minute_mark_dd": sampled_dd["stress"], "actual_minute_mark_dd": sampled_dd["actual"],
              "robust_recovery": min(actual, conservative) / denominator, "recovery_denominator": denominator,
              "epochs": epochs, "epoch_marks": {"last_before": boundary_before, "first_after": boundary_after},
              "entry_volume_histogram": dict(quantity), "component_entry_volumes": dict(by_component),
              "entry_day_multiplier_histogram": dict(Counter(row["day_multiplier"] for row in entries)),
              "native_minute_day_multiplier_histogram": dict(minute_quantity),
              "actual_reinvestment_births": sum(int(row["day_multiplier"]) > 1 for row in entries),
              "quantity_caveat": "Allocation-induced .02 lots at multiplier1 are not reinvestment. Only "
              "actual entry quantity together with a higher original daily staircase proves reinvestment.",
              "daily_first_observation_curve": curve,
              "dd_caveat": "Native relative equity DD governs the DD gate. Conservative stressed DD uses "
              "recorded native minute marks; daily chart samples are descriptive only.",
              "candidate_2026_values_opened": False, "economic_bundle_judgment": None}
    save(output, result)
    return {k: result[k] for k in ["tag", "status", "actual_net", "conservative_stressed_net",
                                   "native_relative_equity_dd_pct", "robust_recovery", "closed_lifecycles",
                                   "actual_reinvestment_births"]}


if __name__ == "__main__":
    print(json.dumps(produce(sys.argv[1])))
