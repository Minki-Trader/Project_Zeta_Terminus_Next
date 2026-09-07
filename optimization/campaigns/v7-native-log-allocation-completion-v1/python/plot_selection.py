"""Standalone figure of observed native wealth and reinvestment, after all roles."""
from datetime import datetime, timezone
from pathlib import Path
import csv
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from native_run import EVIDENCE, RAW, ROLES, binding, save, utc


def produce():
    records = {tag: json.loads((EVIDENCE / (tag + "-economics.json")).read_text(encoding="utf-8"))
               for tag in ROLES}
    if any(x["status"] != "COMPLETE_VALID_FULL2025_NATIVE_ECONOMICS" for x in records.values()):
        raise ValueError("The figure requires all four complete valid native paths")
    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True,
                             gridspec_kw={"height_ratios": [2, 2, 1]})
    styles = [("V7 control / static pair", "#6b7280", "-"),
              ("Static ONNX", "#e59c29", "-"),
              ("V7 control / online pair", "#323c4f", "--"),
              ("Online ONNX", "#008a98", "-")]
    sources = []
    for (tag, result), (label, color, linestyle) in zip(records.items(), styles):
        source = RAW / "native" / tag / "files/learning/equity.csv"
        sources.append(binding(source))
        times, actual, stress, multiplier = [], [], [], []
        last_hour = None
        last = None
        with source.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                stamp = int(row["server_time"])
                last = row
                if stamp // 3600 == last_hour:
                    continue
                last_hour = stamp // 3600
                times.append(datetime.fromtimestamp(stamp, timezone.utc))
                actual.append(float(row["equity"]))
                stress.append(float(row["conservative_mark"]))
                multiplier.append(int(row["day_multiplier"]))
        if last:
            times.append(datetime.fromtimestamp(int(last["server_time"]), timezone.utc))
            actual.append(float(last["equity"]))
            stress.append(float(last["conservative_mark"]))
            multiplier.append(int(last["day_multiplier"]))
        axes[0].plot(times, actual, color=color, ls=linestyle, lw=1.35,
                     label=f"{label}  |  end ${result['actual_terminal_wealth']:.2f}, native DD {result['native_relative_equity_dd_pct']:.2f}%")
        axes[1].plot(times, stress, color=color, ls=linestyle, lw=1.35,
                     label=f"{label}  |  end ${result['conservative_terminal_wealth']:.2f}")
        axes[2].step(times, multiplier, color=color, ls=linestyle, lw=1.6,
                     where="post", label=label)
    for ax in axes[:2]:
        ax.axhline(100, color="#bbbfc4", lw=.8)
        ax.set_ylabel("Observed wealth (USD)")
        ax.legend(loc="upper left", fontsize=8, frameon=False)
    axes[0].set_title("Actual native account equity", loc="left", fontsize=12, fontweight="bold")
    axes[1].set_title("Conservative stressed native mark", loc="left", fontsize=12, fontweight="bold")
    axes[2].set_title("Original V7 daily reinvestment multiplier", loc="left", fontsize=12, fontweight="bold")
    axes[2].set_ylabel("Multiplier")
    axes[2].set_ylim(.85, max(1.2, max(int(k) for x in records.values()
                                  for k in x["native_minute_day_multiplier_histogram"]) + .2))
    axes[2].yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    axes[2].xaxis.set_major_locator(mdates.MonthLocator())
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    for ax in axes:
        ax.grid(axis="y", color="#dce1e7", lw=.6)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Existing V7: full 2025 native ONNX allocation comparison", fontsize=15, fontweight="bold", x=.08, ha="left")
    fig.text(.08, .018, "All four paths: $100 start, leverage 1:100, 100% real ticks. Curves display hourly observations; complete minute CSVs are retained.\n"
             "DD labels use MT5 native intratick statistics. Allocation-induced larger lots at multiplier 1 do not demonstrate reinvestment.",
             fontsize=8, color="#4b5563")
    fig.subplots_adjust(left=.08, right=.98, top=.92, bottom=.09, hspace=.26)
    target = EVIDENCE / "native-selection-equity-v1.png"
    if target.exists():
        raise ValueError("Preserve existing figure identity")
    fig.savefig(target, dpi=160, facecolor="white")
    plt.close(fig)
    save(EVIDENCE / "NATIVE_SELECTION_FIGURE_V1.json", {"utc": utc(), "figure": binding(target),
         "source_complete_minute_paths": sources, "producer": binding(Path(__file__).resolve()),
         "no_synthetic_profit_or_quantity": True})
    return str(target)


if __name__ == "__main__":
    print(produce())
