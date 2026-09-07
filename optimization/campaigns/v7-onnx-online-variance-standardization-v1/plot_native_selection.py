"""Render the complete V2 native asset and observed entry-volume paths.

This is a normal factual report producer.  It requires all three immutable
native episode inputs and their completed native-result JSON records, writes
one PNG plus one manifest, and makes no role ranking or economic gate decision.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import sys

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from variance_signal import FAMILY, RAW, ROOT, record


SCHEMA = "v7-vs-native-selection-path-plot-manifest-v1"
RESULT_SCHEMA = "v7-vs-native-economic-report-v1"
TAGS = (
    "selection-control-static-v2",
    "selection-static-v2",
    "selection-online-v2",
)
ROLE_SPEC = {
    "selection-control-static-v2": {
        "role": "control-static", "label": "Control", "color": "#1f77b4"
    },
    "selection-static-v2": {
        "role": "static", "label": "Static", "color": "#2ca02c"
    },
    "selection-online-v2": {
        "role": "online", "label": "Online", "color": "#9467bd"
    },
}
PNG_NAME = "selection-v2-native-asset-quantity-paths.png"
MANIFEST_NAME = "selection-v2-native-asset-quantity-paths-manifest.json"
FREE_FLOOR_BYTES = 30 * 1024**3
RAW_LIMIT_BYTES = 1024**3
PNG_TARGET_BYTES = 2 * 1024**2
DISPLAY_INTERVAL_SECONDS = 3600
NATIVE_EPOCH = datetime(1970, 1, 1)


def fail(message: str) -> None:
    raise RuntimeError(message)


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def file_digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(4 * 1024 * 1024):
            hasher.update(block)
    return hasher.hexdigest().upper()


def byte_digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def text_encoding(path: Path) -> str:
    with path.open("rb") as stream:
        prefix = stream.read(4096)
    if prefix.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    if b"\x00" in prefix:
        return "utf-16-le"
    try:
        prefix.decode("utf-8-sig")
        return "utf-8-sig"
    except UnicodeDecodeError:
        return "cp949"


def clean_header(reader: csv.DictReader) -> list[str]:
    header = list(reader.fieldnames or [])
    if header:
        header[0] = header[0].lstrip("\ufeff")
        reader.fieldnames = header
    return header


def finite_float(value: object, context: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        fail(f"{context} is not numeric")
    if not math.isfinite(number):
        fail(f"{context} is not finite")
    return number


def integer(value: object, context: str) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        fail(f"{context} is not an integer")


def native_datetime(epoch: int) -> datetime:
    """Map the numeric native epoch directly to a naive displayed datetime."""
    return NATIVE_EPOCH + timedelta(seconds=epoch)


def result_inputs(tag: str) -> dict[str, Path]:
    episode = RAW / "native" / tag
    return {
        "equity": episode / "Files" / "equity.csv",
        "lifecycles": episode / "Files" / "research" / "research-lifecycles.csv",
        "native_result": RAW / "native-results" / f"{tag}.json",
    }


def require_all_inputs() -> dict[str, dict[str, Path]]:
    paths = {tag: result_inputs(tag) for tag in TAGS}
    missing = [rel(path) for group in paths.values() for path in group.values()
               if not path.is_file()]
    if missing:
        fail("all three completed role inputs are required; missing: " + ", ".join(missing))
    return paths


def input_record(path: Path) -> dict[str, object]:
    return {"path": rel(path), "bytes": path.stat().st_size, "sha256": file_digest(path)}


def require_bound_record(
    inventory: list[dict[str, object]], current: dict[str, object], context: str
) -> None:
    matches = [item for item in inventory if item.get("path") == current["path"]]
    if len(matches) != 1:
        fail(f"{context} is not uniquely bound in its native-result input inventory")
    expected = matches[0]
    if expected.get("bytes") != current["bytes"] or expected.get("sha256") != current["sha256"]:
        fail(f"{context} differs from its completed native-result input binding")


def load_native_result(
    tag: str, paths: dict[str, Path], records: dict[str, dict[str, object]]
) -> tuple[dict[str, object], dict[str, float]]:
    with paths["native_result"].open("r", encoding="utf-8") as stream:
        result = json.load(stream)
    spec = ROLE_SPEC[tag]
    if result.get("schema") != RESULT_SCHEMA:
        fail(f"{tag} native-result schema differs")
    if result.get("observation_tag") != tag or result.get("role") != spec["role"]:
        fail(f"{tag} native-result identity differs")
    completeness = result.get("completeness")
    if not isinstance(completeness, dict):
        fail(f"{tag} has no artifact-completeness record")
    if completeness.get("unknowns") or completeness.get("missing_or_ambiguous_files"):
        fail(f"{tag} native-result artifact completeness is unresolved")
    for name in ("agent_log_present", "terminal_log_present", "report_html_present"):
        if completeness.get(name) is not True:
            fail(f"{tag} native-result lacks completed {name}")

    inventory = result.get("input_inventory", {}).get("files", [])
    if not isinstance(inventory, list):
        fail(f"{tag} native-result input inventory is unavailable")
    require_bound_record(inventory, records["equity"], f"{tag} equity.csv")
    require_bound_record(inventory, records["lifecycles"], f"{tag} research-lifecycles.csv")

    native = result.get("native_summary_observations", {}).get("v7rr1_native")
    totals = result.get("lifecycles", {}).get("full_close_totals")
    if not isinstance(native, dict) or not isinstance(native.get("fields"), dict):
        fail(f"{tag} completed native DD observation is unavailable")
    if not isinstance(totals, dict):
        fail(f"{tag} completed lifecycle totals are unavailable")
    numbers = {
        "native_relative_equity_dd_pct": finite_float(
            native["fields"].get("equity_dd_relative_pct"),
            f"{tag} native relative equity DD",
        ),
        "actual_net_usd": finite_float(totals.get("actual_net_usd"), f"{tag} actual net"),
        "stressed_net_usd": finite_float(
            totals.get("stressed_net_usd"), f"{tag} stressed net"
        ),
    }
    producer = result.get("producer")
    if not isinstance(producer, dict) or not producer.get("sha256") or not producer.get("path"):
        fail(f"{tag} native-result producer binding is unavailable")
    return result, numbers


def load_equity_path(path: Path) -> dict[str, object]:
    path_label = rel(path)
    required = {
        "server_time_epoch", "forced", "actual_equity",
        "conservative_stressed_mark", "conservative_mark_known",
    }
    times: list[datetime] = []
    actual_equity: list[float] = []
    conservative_mark: list[float] = []
    raw_rows = 0
    unknown_mark_rows = 0
    previous_epoch: int | None = None
    previous_known: bool | None = None
    next_display_epoch: int | None = None
    last_observation: tuple[int, float, float] | None = None
    last_appended: tuple[int, float, float] | None = None

    def append(observation: tuple[int, float, float]) -> None:
        nonlocal last_appended
        epoch, equity, mark = observation
        times.append(native_datetime(epoch))
        actual_equity.append(equity)
        conservative_mark.append(mark)
        last_appended = observation

    with path.open("r", encoding=text_encoding(path), errors="replace", newline="") as stream:
        reader = csv.DictReader(stream)
        header = clean_header(reader)
        if not required.issubset(header):
            fail(f"{path_label} lacks the authored account-path columns")
        for raw in reader:
            raw_rows += 1
            epoch = integer(raw.get("server_time_epoch", ""), f"{path_label} row {raw_rows} epoch")
            if previous_epoch is not None and epoch < previous_epoch:
                fail(f"{path_label} native epochs are not nondecreasing")
            equity = finite_float(raw.get("actual_equity", ""), f"{path_label} row {raw_rows} equity")
            mark_known = raw.get("conservative_mark_known", "").strip() == "1"
            if mark_known:
                mark = finite_float(
                    raw.get("conservative_stressed_mark", ""),
                    f"{path_label} row {raw_rows} conservative mark",
                )
            else:
                mark = math.nan
                unknown_mark_rows += 1
            observation = (epoch, equity, mark)
            forced = raw.get("forced", "").strip() == "1"
            transition = previous_known is not None and mark_known != previous_known
            if next_display_epoch is None:
                append(observation)
                next_display_epoch = ((epoch // DISPLAY_INTERVAL_SECONDS) + 1) * DISPLAY_INTERVAL_SECONDS
            elif epoch >= next_display_epoch or forced or transition:
                append(observation)
                if epoch >= next_display_epoch:
                    next_display_epoch = (
                        (epoch // DISPLAY_INTERVAL_SECONDS) + 1
                    ) * DISPLAY_INTERVAL_SECONDS
            previous_epoch = epoch
            previous_known = mark_known
            last_observation = observation
    if raw_rows == 0 or last_observation is None:
        fail(f"{path_label} contains no account observations")
    if last_appended != last_observation:
        append(last_observation)
    return {
        "times": times,
        "actual_equity": actual_equity,
        "conservative_mark": conservative_mark,
        "raw_rows": raw_rows,
        "display_points": len(times),
        "unknown_mark_rows": unknown_mark_rows,
        "first_native_datetime": times[0].isoformat(sep=" "),
        "last_native_datetime": times[-1].isoformat(sep=" "),
    }


def parse_server_datetime(value: str, context: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y.%m.%d %H:%M:%S")
    except ValueError:
        fail(f"{context} has an unreadable native server_time")


def load_daily_birth_volume(path: Path) -> dict[str, object]:
    path_label = rel(path)
    required = {"event", "server_time", "volume"}
    daily: dict[date, Decimal] = {}
    birth_rows = 0
    with path.open("r", encoding=text_encoding(path), errors="replace", newline="") as stream:
        reader = csv.DictReader(stream)
        header = clean_header(reader)
        if not required.issubset(header):
            fail(f"{path_label} lacks the authored lifecycle columns")
        for raw in reader:
            if raw.get("event", "").strip() != "BIRTH":
                continue
            birth_rows += 1
            observed = parse_server_datetime(
                raw.get("server_time", "").strip(), f"{path_label} BIRTH row {birth_rows}"
            )
            try:
                volume = Decimal(raw.get("volume", "").strip())
            except InvalidOperation:
                fail(f"{path_label} BIRTH row {birth_rows} has unreadable volume")
            if not volume.is_finite() or volume < 0:
                fail(f"{path_label} BIRTH row {birth_rows} has invalid volume")
            day = observed.date()
            if day not in daily or volume > daily[day]:
                daily[day] = volume
    dates = [datetime.combine(day, datetime.min.time()) for day in sorted(daily)]
    volumes = [float(daily[day]) for day in sorted(daily)]
    return {
        "dates": dates,
        "volumes": volumes,
        "birth_rows": birth_rows,
        "observed_birth_days": len(dates),
        "no_trade_days_filled": 0,
    }


def raw_logical_bytes() -> int:
    return sum(path.stat().st_size for path in RAW.rglob("*") if path.is_file())


def money(value: float) -> str:
    return f"${value:+.2f}"


def render_png(role_data: list[dict[str, object]]) -> bytes:
    plt.rcParams.update({
        "font.size": 9,
        "axes.titlesize": 11,
        "axes.labelsize": 9,
        "legend.fontsize": 9,
    })
    fig, axes = plt.subplots(3, 1, figsize=(13.0, 9.2), sharex=True)
    fig.suptitle("V7 Native 2025 Asset and Observed Entry-Volume Paths", fontsize=14)

    all_dates: list[datetime] = []
    for item in role_data:
        spec = item["spec"]
        equity = item["equity_path"]
        volume = item["birth_volume"]
        axes[0].plot(
            equity["times"], equity["actual_equity"],
            color=spec["color"], linewidth=1.0, label=spec["label"],
        )
        axes[1].plot(
            equity["times"], equity["conservative_mark"],
            color=spec["color"], linewidth=1.0,
        )
        axes[2].scatter(
            volume["dates"], volume["volumes"],
            color=spec["color"], s=13, alpha=0.78, edgecolors="none",
        )
        all_dates.extend(equity["times"])
        all_dates.extend(volume["dates"])

    if not all_dates:
        fail("no native dates are available for the plot")
    for axis in axes[:2]:
        axis.axhline(100.0, color="#777777", linestyle="--", linewidth=0.8, alpha=0.8)
    axes[0].set_title("Actual account equity")
    axes[1].set_title("Conservative stressed mark (unknown observations remain gaps)")
    axes[2].set_title("Maximum actual BIRTH volume by observed trade day")
    axes[0].set_ylabel("USD")
    axes[1].set_ylabel("USD")
    axes[2].set_ylabel("Volume")
    axes[2].set_xlabel("Native server date (naive; no timezone conversion)")
    axes[0].legend(loc="upper left", ncol=3, frameon=False)
    for axis in axes:
        axis.grid(True, color="#dddddd", linewidth=0.6, alpha=0.7)
        axis.set_xlim(min(all_dates), max(all_dates))
    axes[2].set_ylim(bottom=0.0)
    axes[2].xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    table_rows = []
    for item in role_data:
        numbers = item["numbers"]
        table_rows.append([
            item["spec"]["label"],
            f"{numbers['native_relative_equity_dd_pct']:.3f}%",
            money(numbers["actual_net_usd"]),
            money(numbers["stressed_net_usd"]),
        ])
    table = axes[2].table(
        cellText=table_rows,
        colLabels=["Role", "Native equity DD", "Actual net", "Stressed net"],
        cellLoc="center",
        bbox=[0.13, -0.66, 0.74, 0.42],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8.5)
    fig.text(
        0.5, 0.018,
        "Economic figures are copied from completed native-result JSON. "
        "Lines use observed hourly display samples; no interpolation or future fill is added. "
        "Volume dots exist only on observed BIRTH dates.",
        ha="center", va="bottom", fontsize=8, color="#444444",
    )
    fig.subplots_adjust(left=0.08, right=0.98, top=0.91, bottom=0.27, hspace=0.18)
    buffer = io.BytesIO()
    fig.savefig(
        buffer, format="png", dpi=135, facecolor="white",
        metadata={"Software": "Project Zeta Terminus Next native factual report producer"},
    )
    plt.close(fig)
    return buffer.getvalue()


def exclusive_write(path: Path, payload: bytes) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        fail(f"immutable output already exists: {rel(path)}")


def main() -> int:
    if len(sys.argv) != 1:
        fail("this fixed V2 report producer accepts no arguments")
    if FAMILY != Path(__file__).resolve().parent:
        fail("variance_signal family binding differs from this plot producer")
    output_dir = RAW / "native-results"
    png_path = output_dir / PNG_NAME
    manifest_path = output_dir / MANIFEST_NAME
    if png_path.exists() or manifest_path.exists():
        fail("immutable native selection plot output already exists")

    inputs = require_all_inputs()
    free_before = shutil.disk_usage(RAW).free
    raw_before = raw_logical_bytes()
    if free_before < FREE_FLOOR_BYTES:
        fail("less than the required 30 GiB free-space floor")
    if raw_before > RAW_LIMIT_BYTES:
        fail("family RAW already exceeds the 1 GiB logical-byte budget")

    role_data: list[dict[str, object]] = []
    for tag in TAGS:
        paths = inputs[tag]
        records = {name: input_record(path) for name, path in paths.items()}
        result, numbers = load_native_result(tag, paths, records)
        role_data.append({
            "tag": tag,
            "spec": ROLE_SPEC[tag],
            "paths": paths,
            "records": records,
            "result": result,
            "numbers": numbers,
            "equity_path": load_equity_path(paths["equity"]),
            "birth_volume": load_daily_birth_volume(paths["lifecycles"]),
        })

    png = render_png(role_data)
    if len(png) > PNG_TARGET_BYTES:
        fail(f"rendered PNG exceeds the 2 MiB target: {len(png)} bytes")

    native_dates = [dt for item in role_data for dt in item["equity_path"]["times"]]
    manifest = {
        "schema": SCHEMA,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        ),
        "family": "v7-onnx-online-variance-standardization-v1",
        "producer": record(Path(__file__).resolve()),
        "purpose": "Factual visualization of completed native asset and observed quantity paths.",
        "judgment": {
            "role_ranking": None,
            "economic_gate": None,
            "winner": None,
            "successor_or_candidate_decision": None,
        },
        "plot_contract": {
            "roles": list(TAGS),
            "panels": [
                "actual_equity",
                "conservative_stressed_mark",
                "daily_maximum_observed_birth_volume",
            ],
            "native_epoch_display": "numeric epoch mapped directly from 1970-01-01 to naive datetime; no timezone conversion",
            "account_display_sampling": (
                "first, final, forced, conservative-mark known/unknown transitions, and at least "
                "one observed row per 3600 native seconds"
            ),
            "conservative_mark_unknown": "NaN gap; no interpolation or future fill",
            "volume_rendering": "scatter on observed BIRTH dates only; no no-trade-day fill or carry-forward",
            "initial_usd_reference": 100.0,
            "legend_count": 1,
            "economic_numbers_source": "completed native-result JSON only",
        },
        "common_native_date_range": {
            "first": min(native_dates).isoformat(sep=" "),
            "last": max(native_dates).isoformat(sep=" "),
        },
        "roles": [
            {
                "tag": item["tag"],
                "role": item["spec"]["role"],
                "label": item["spec"]["label"],
                "color": item["spec"]["color"],
                "inputs": item["records"],
                "native_result_producer": item["result"]["producer"],
                "reported_economic_values": item["numbers"],
                "account_path_observation": {
                    key: item["equity_path"][key]
                    for key in (
                        "raw_rows", "display_points", "unknown_mark_rows",
                        "first_native_datetime", "last_native_datetime",
                    )
                },
                "birth_volume_observation": {
                    key: item["birth_volume"][key]
                    for key in ("birth_rows", "observed_birth_days", "no_trade_days_filled")
                },
            }
            for item in role_data
        ],
        "png": {
            "path": rel(png_path),
            "bytes": len(png),
            "sha256": byte_digest(png),
            "target_max_bytes": PNG_TARGET_BYTES,
            "matplotlib_version": matplotlib.__version__,
        },
        "storage": {
            "free_bytes_before": free_before,
            "required_free_floor_bytes": FREE_FLOOR_BYTES,
            "raw_logical_bytes_before": raw_before,
            "raw_logical_limit_bytes": RAW_LIMIT_BYTES,
            "projected_raw_logical_bytes_after": 0,
        },
    }
    manifest_payload = b""
    for _ in range(6):
        manifest_payload = (
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
        ).encode("utf-8")
        projected = raw_before + len(png) + len(manifest_payload)
        if manifest["storage"]["projected_raw_logical_bytes_after"] == projected:
            break
        manifest["storage"]["projected_raw_logical_bytes_after"] = projected
    manifest_payload = (
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode("utf-8")
    projected = raw_before + len(png) + len(manifest_payload)
    if projected > RAW_LIMIT_BYTES:
        fail("PNG and manifest would exceed the family RAW 1 GiB budget")
    if free_before - len(png) - len(manifest_payload) < FREE_FLOOR_BYTES:
        fail("PNG and manifest would cross the required 30 GiB free-space floor")

    exclusive_write(png_path, png)
    exclusive_write(manifest_path, manifest_payload)
    print(json.dumps({
        "png": input_record(png_path),
        "manifest": input_record(manifest_path),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"native selection plot production failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
