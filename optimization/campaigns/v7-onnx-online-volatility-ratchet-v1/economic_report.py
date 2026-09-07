"""Summarize the complete frozen native pair and its capital/lot path.

This is the campaign economic reporting step, consuming retained normal MT5
outputs. It neither executes a strategy nor replaces missing native evidence.
"""
from collections import Counter, defaultdict
from pathlib import Path
import csv
import datetime as dt
import hashlib
import json
import re

FAMILY = Path(__file__).resolve().parent
ROOT = FAMILY.parents[2]
RAW = ROOT / "optimization/artifacts/raw/v7-onnx-online-volatility-ratchet-v1"
PERIOD_DAYS = (dt.date(2026, 9, 1) - dt.date(2025, 1, 1)).days


def decoded(path):
    value = path.read_bytes()
    return value.decode("utf-16" if value[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", errors="strict")


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest().upper()


def fields(line):
    return dict(re.findall(r"(\w+)=([^\s]+)", line))


def epoch_name(label):
    if label < "2025.07.01":
        return "2025-H1"
    if label < "2026.01.01":
        return "2025-H2"
    if label < "2026.07.01":
        return "2026-H1-confirmation"
    return "2026-JulAug-latest"


def role_report(role, namespace):
    folder = RAW / (role + "-final")
    log = decoded(folder / "agent.log")
    lines = log.splitlines()
    own = [line for line in lines if namespace + " (" in line]
    native_lines = [line for line in own if "V7RR1_NATIVE " in line]
    result_lines = [line for line in own if "V7RR1_RESULT " in line]
    if len(native_lines) != 1 or len(result_lines) != 1:
        raise RuntimeError("Complete unique native result is required for " + role)
    summary = {**fields(native_lines[0]), **fields(result_lines[0])}
    research = folder / "Files" / namespace / "optimization/volatility-ratchet/research"
    with (research / "research-lifecycles.csv").open(encoding="utf-8-sig", newline="") as handle:
        events = list(csv.DictReader(handle))
    births = [r for r in events if r["event"] == "BIRTH"]
    closes = [r for r in events if r["event"] == "CLOSE"]
    periods, months, components = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in closes:
        periods[epoch_name(row["server_time"])].append(row)
        months[row["server_time"][:7]].append(row)
        components[row["component_id"]].append(row)

    def totals(rows):
        return {"closed": len(rows), "actual": sum(float(r["actual_net_usd"]) for r in rows),
                "stress": sum(float(r["stressed_net_usd"]) for r in rows)}

    actual, stress = float(summary["actual_net"]), float(summary["stressed_net"])
    native_dd = float(summary["equity_dd"])
    conservative_recovery = min(actual, stress) / max(.01, native_dd, float(summary["stressed_dd"]))
    history_lines = [line for line in lines if re.search(r"US(?:30|100|500).*real ticks begin|US(?:30|100|500): generate", line)]
    faults = [line for line in lines if any(tag in line for tag in ("\tTicks\t", "\tHistory\t", "\tTester\t")) and re.search(r"real ticks (?:absent|discarded)|mismatch|not synchronized|no history|generat.*based on minute", line, re.I)]
    contracts = [line.split("V7RR1_CONTRACT ", 1)[1] for line in own if "V7RR1_CONTRACT " in line]
    quality_text = decoded(folder / "report.htm")
    quality = bool(re.search(r"100\s*%\s*real ticks", re.sub(r"<[^>]+>", " ", quality_text), re.I))
    daily, transitions, sampled_ticks = {}, [], 0
    last_multiplier = None
    path_file = research / "economic-path.csv"
    with path_file.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            time = int(row["minute_server_epoch"])
            date = str(dt.datetime.fromtimestamp(time, tz=dt.timezone.utc).date())
            daily[date] = {"equity_close": float(row["equity_close"]), "balance_close": float(row["balance_close"]),
                           "known_core_stress_close": float(row["core_stressed_close"])}
            multiplier = int(row["day_lot_multiplier"])
            if multiplier != last_multiplier:
                transitions.append({"server_epoch": time, "date": date, "multiplier": multiplier,
                                    "known_stressed_balance": float(row["core_stressed_close"])})
                last_multiplier = multiplier
            sampled_ticks += int(row["ticks"])
    result = {"summary": summary, "events": dict(Counter(r["event"] for r in events)),
              "partial_rows": sum(int(r["partial_observation"]) != 0 for r in events),
              "dropped_records_max": max(int(r["research_dropped_records"]) for r in events),
              "unclosed_lifecycle_ids": sorted(set(r["position_identifier"] for r in births) - set(r["position_identifier"] for r in closes)),
              "periods": {k: totals(v) for k, v in periods.items()}, "months": {k: totals(v) for k, v in months.items()},
              "components": {k: totals(v) for k, v in components.items()}, "native_contracts": contracts,
              "native_history_lines": history_lines, "native_history_fault_lines": faults,
              "reported_100_percent_real_ticks": quality,
              "capital": {"initial": 100., "terminal_actual": 100 + actual, "terminal_stress": 100 + stress,
                          "actual_wealth_multiple": 1 + actual / 100, "stress_wealth_multiple": 1 + stress / 100,
                          "actual_cagr": ((1 + actual / 100) ** (365.25 / PERIOD_DAYS) - 1) if actual > -100 else None,
                          "stress_cagr": ((1 + stress / 100) ** (365.25 / PERIOD_DAYS) - 1) if stress > -100 else None,
                          "native_conservative_recovery": conservative_recovery},
              "volume_counts": dict(Counter(r["volume"] for r in births)), "daily_multiplier_transitions": transitions,
              "equity_path_rows_scope": "Every delivered EA tick aggregated into minute extrema; full tester equity DD uses TesterStatistics.",
              "delivered_ticks_in_equity_path": sampled_ticks, "daily_path": daily,
              "model_lines": [line for line in own if "V7VR_MODEL " in line],
              "path_lines": [line for line in own if "V7VR_PATH " in line],
              "artifact_hashes": {p.relative_to(folder).as_posix(): sha(p) for p in (folder / "agent.log", folder / "report.htm", research / "research-lifecycles.csv", path_file)}}
    return result


def main():
    path = FAMILY / "evidence/NATIVE_PAIR_RESULTS_V1.json"
    if path.exists():
        raise RuntimeError("Completed native report is immutable")
    roles = {r: role_report(r, n) for r, n in (("control", "ZetaV7VRControl"), ("candidate", "ZetaV7VRStatic"))}
    c, s = roles["control"], roles["candidate"]
    dd_c, dd_s = float(c["summary"]["equity_dd_relative_pct"]), float(s["summary"]["equity_dd_relative_pct"])
    ceiling = min(dd_c + 1.5, dd_c * 1.10)
    stress_gain = float(s["summary"]["stressed_net"]) / float(c["summary"]["stressed_net"]) - 1
    gates = {"actual_wealth_improves": s["capital"]["terminal_actual"] > c["capital"]["terminal_actual"],
             "stressed_profit_gain_at_least5pct": stress_gain >= .05,
             "native_dd_nominal": dd_s <= dd_c, "native_dd_effective": dd_s <= ceiling,
             "recovery_improves": s["capital"]["native_conservative_recovery"] > c["capital"]["native_conservative_recovery"],
             "positive_all_four_epochs": len(s["periods"]) == 4 and all(v["actual"] > 0 and v["stress"] > 0 for v in s["periods"].values())}
    output = {"status": "COMPLETE_NATIVE_PAIR_ECONOMIC_REPORT_PENDING_ROOT_BINDING_JUDGMENT", "interval": "2025-01-01..2026-09-01 exclusive",
              "roles": roles, "economic_gates": gates, "dd_effective_ceiling_pct": ceiling,
              "stressed_profit_gain_fraction": stress_gain, "live_changes": False,
              "scope": "Actual independent native capital and original daily reinvestment. No hypothetical scaling of prior dollar PNL. Validity and common before/between/after history/contracts are recorded separately by the owning native phase."}
    path.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    render_paths(roles)
    print(json.dumps({"economic_gates": gates, "stressed_profit_gain_fraction": stress_gain,
                      "control": c["capital"], "candidate": s["capital"], "native_dd": [dd_c, dd_s]}, indent=2))


def render_paths(roles):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True, gridspec_kw={"height_ratios": [2, 2, 1]})
    palette = {"control": "#65758b", "candidate": "#14785c"}
    names = {"control": "Original V7", "candidate": "ONNX static ratchet"}
    for role, result in roles.items():
        dates = [dt.datetime.fromisoformat(day) for day in result["daily_path"]]
        rows = list(result["daily_path"].values())
        axes[0].plot(dates, [v["equity_close"] for v in rows], color=palette[role], linewidth=1.6, label=names[role])
        axes[1].plot(dates, [v["known_core_stress_close"] for v in rows], color=palette[role], linewidth=1.6)
        changes = result["daily_multiplier_transitions"]
        steps_x = [dt.datetime.fromisoformat(x["date"]) for x in changes] + [dt.datetime(2026, 9, 1)]
        steps_y = [x["multiplier"] for x in changes] + [changes[-1]["multiplier"]]
        axes[2].step(steps_x, steps_y, where="post", color=palette[role], linewidth=1.6)
    axes[0].set_title("Native V7 compound-growth comparison | $100 initial capital", loc="left", fontsize=15, fontweight="bold")
    axes[0].set_ylabel("Daily closing equity, USD")
    axes[1].set_ylabel("Known stressed cash, USD")
    axes[2].set_ylabel("Daily market\nlot multiplier")
    axes[0].legend(frameon=False, loc="upper left")
    axes[2].xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    for ax in axes:
        ax.grid(axis="y", alpha=.18)
        ax.spines[["top", "right"]].set_visible(False)
    fig.text(.08, .015, "2025-01-01 to 2026-09-01 exclusive. Actual independent native capital; original $150 daily lot staircase.\n"
             "Paths aggregate delivered EA ticks. Full tester equity drawdown is reported separately from TesterStatistics.",
             color="#465366", fontsize=9)
    fig.tight_layout(rect=(0, .055, 1, 1))
    fig.savefig(FAMILY / "evidence/native-compounding-path.png", dpi=160, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
