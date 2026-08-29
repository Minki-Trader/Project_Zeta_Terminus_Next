#!/usr/bin/env python3
"""One frozen source-free aggregation for Frontier Unit 103.

This is a research aggregation, not a validator, test harness, trading program,
or reusable CLI product.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[4]
FAMILY = REPO / "lab/research/two-index-h1-directional-lead-lag-response-v1"
DECLARATION_PATH = (
    FAMILY
    / "evidence/TWO_INDEX_H1_DIRECTIONAL_LEAD_LAG_RESPONSE_DECLARATION_V1.json"
)
TRACKED_RESULT_PATH = (
    FAMILY / "evidence/TWO_INDEX_H1_DIRECTIONAL_LEAD_LAG_RESPONSE_RESULT_V1.json"
)
RAW_ROOT = (
    REPO / "lab/artifacts/raw/two-index-h1-directional-lead-lag-response-v1"
)
INPUT_ROOT = RAW_ROOT / "input"
RAW_RESULT_PATH = RAW_ROOT / "output/proxy-result.json"

EXPECTED_COLUMNS = [
    "time_epoch",
    "time_server",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
]


@dataclass(frozen=True)
class Bar:
    epoch: int
    server_time: str
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    spread: int
    real_volume: int


@dataclass(frozen=True)
class Signal:
    variant: str
    leader: str
    follower: str
    signal_epoch: int
    signal_server_time: str
    period: str
    side: str
    direction: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def byte_count(path: Path) -> int:
    return path.stat().st_size


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def canonical_manifest(paths: Iterable[Path]) -> str:
    lines = [
        f"{path.name}|{byte_count(path)}|{sha256_file(path)}"
        for path in sorted(paths, key=lambda item: item.name)
    ]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest().upper()


def load_bars(path: Path) -> dict[int, Bar]:
    bars: dict[int, Bar] = {}
    previous = -1
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_COLUMNS:
            raise RuntimeError(f"unexpected columns in {path.name}: {reader.fieldnames}")
        for row_number, row in enumerate(reader, start=2):
            epoch = int(row["time_epoch"])
            if epoch <= previous or epoch in bars:
                raise RuntimeError(f"non-increasing epoch in {path.name}:{row_number}")
            previous = epoch
            values = [float(row[name]) for name in ("open", "high", "low", "close")]
            if not all(math.isfinite(value) and value > 0 for value in values):
                raise RuntimeError(f"invalid OHLC in {path.name}:{row_number}")
            tick_volume = int(row["tick_volume"])
            spread = int(row["spread"])
            real_volume = int(row["real_volume"])
            if tick_volume < 0 or spread < 0 or real_volume < 0:
                raise RuntimeError(f"negative volume/spread in {path.name}:{row_number}")
            bars[epoch] = Bar(
                epoch=epoch,
                server_time=row["time_server"],
                open=values[0],
                high=values[1],
                low=values[2],
                close=values[3],
                tick_volume=tick_volume,
                spread=spread,
                real_volume=real_volume,
            )
    return bars


def server_date(bar: Bar) -> str:
    return bar.server_time[:10].replace(".", "-")


def period_for(date_text: str, periods: dict[str, list[str]]) -> str | None:
    for period, bounds in periods.items():
        if bounds[0] <= date_text <= bounds[1]:
            return period
    return None


def build_structural_signals(
    variant: str,
    leader_name: str,
    follower_name: str,
    leader: dict[int, Bar],
    follower: dict[int, Bar],
    common_epochs: list[int],
    periods: dict[str, list[str]],
) -> list[Signal]:
    signals: list[Signal] = []
    last_exit_epoch = -1
    for epoch in common_epochs:
        if epoch <= last_exit_epoch:
            continue
        required = (epoch, epoch + 3600, epoch + 7200)
        if any(item not in leader or item not in follower for item in required):
            continue
        signal_bar = leader[epoch]
        date_text = server_date(signal_bar)
        period = period_for(date_text, periods)
        if period is None:
            continue
        if period_for(server_date(follower[epoch + 7200]), periods) != period:
            continue
        leader_change = signal_bar.close - signal_bar.open
        if leader_change == 0:
            continue
        direction = 1 if leader_change > 0 else -1
        signals.append(
            Signal(
                variant=variant,
                leader=leader_name,
                follower=follower_name,
                signal_epoch=epoch,
                signal_server_time=signal_bar.server_time,
                period=period,
                side="UP" if direction > 0 else "DOWN",
                direction=direction,
            )
        )
        last_exit_epoch = epoch + 7200
    return signals


def structural_summary(
    signals: list[Signal],
    common_epochs: list[int],
    follower: dict[int, Bar],
    periods: dict[str, list[str]],
) -> dict[str, Any]:
    output: dict[str, Any] = {"total": len(signals), "periods": {}, "p1_splits": {}}
    for period, bounds in periods.items():
        rows = [signal for signal in signals if signal.period == period]
        normal_days = len(
            {
                server_date(follower[epoch])
                for epoch in common_epochs
                if bounds[0] <= server_date(follower[epoch]) <= bounds[1]
            }
        )
        output["periods"][period] = {
            "normal_days": normal_days,
            "signals": len(rows),
            "signals_per_day": len(rows) / normal_days,
            "unique_signal_hours": len(
                {(row.signal_server_time[:10], row.signal_server_time[11:13]) for row in rows}
            ),
            "up": sum(row.side == "UP" for row in rows),
            "down": sum(row.side == "DOWN" for row in rows),
            "signal_dates": len({row.signal_server_time[:10] for row in rows}),
        }
    for label, start, end in (
        ("P1_2022H2", "2022-08-01", "2022-12-31"),
        ("P1_2023", "2023-01-01", "2023-12-31"),
    ):
        rows = [
            signal
            for signal in signals
            if start <= signal.signal_server_time[:10].replace(".", "-") <= end
        ]
        output["p1_splits"][label] = {
            "signals": len(rows),
            "dates": len({row.signal_server_time[:10] for row in rows}),
            "up": sum(row.side == "UP" for row in rows),
            "down": sum(row.side == "DOWN" for row in rows),
        }
    return output


def assert_nested_equal(actual: Any, expected: Any, label: str) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise RuntimeError(f"{label} keys differ")
        for key in expected:
            assert_nested_equal(actual[key], expected[key], f"{label}.{key}")
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise RuntimeError(f"{label} list differs")
        for index, value in enumerate(expected):
            assert_nested_equal(actual[index], value, f"{label}[{index}]")
        return
    if isinstance(expected, float):
        if not isinstance(actual, (int, float)) or not math.isclose(
            float(actual), expected, rel_tol=0.0, abs_tol=1e-12
        ):
            raise RuntimeError(f"{label} differs: {actual!r} != {expected!r}")
        return
    if actual != expected:
        raise RuntimeError(f"{label} differs: {actual!r} != {expected!r}")


def economic_rows(
    signals: list[Signal],
    follower_bars: dict[str, dict[int, Bar]],
    trade_specs: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    volume = 0.01
    for signal in signals:
        follower = follower_bars[signal.follower]
        entry = follower[signal.signal_epoch + 3600]
        exit_bar = follower[signal.signal_epoch + 7200]
        spec = trade_specs["symbols"][signal.follower]
        point = float(spec["point"])
        contract = float(spec["trade_contract_size"])
        entry_spread_price = entry.spread * point
        exit_spread_price = exit_bar.spread * point
        entry_mid = entry.open + 0.5 * entry_spread_price
        exit_mid = exit_bar.open + 0.5 * exit_spread_price
        gross = signal.direction * (exit_mid - entry_mid) * contract * volume
        observed = gross - 0.5 * (entry_spread_price + exit_spread_price) * contract * volume
        doubled = gross - (entry_spread_price + exit_spread_price) * contract * volume
        rows.append(
            {
                "variant": signal.variant,
                "leader": signal.leader,
                "follower": signal.follower,
                "signal_epoch": signal.signal_epoch,
                "signal_server_time": signal.signal_server_time,
                "entry_epoch": entry.epoch,
                "exit_epoch": exit_bar.epoch,
                "period": signal.period,
                "side": signal.side,
                "direction": signal.direction,
                "gross_usd": gross,
                "observed_usd": observed,
                "double_spread_usd": doubled,
            }
        )
    return rows


def book_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: (row["exit_epoch"], row["signal_epoch"]))
    pnl = [float(row["double_spread_usd"]) for row in ordered]
    positive = sum(value for value in pnl if value > 0)
    negative_abs = -sum(value for value in pnl if value < 0)
    profit_factor = positive / negative_abs if negative_abs > 0 else None
    balance = 100.0
    peak = 100.0
    maximum_drawdown = 0.0
    maximum_drawdown_percent = 0.0
    minimum_balance = 100.0
    for value in pnl:
        balance += value
        peak = max(peak, balance)
        drawdown = peak - balance
        maximum_drawdown = max(maximum_drawdown, drawdown)
        if peak > 0:
            maximum_drawdown_percent = max(maximum_drawdown_percent, 100.0 * drawdown / peak)
        minimum_balance = min(minimum_balance, balance)
    net = sum(pnl)
    return {
        "count": len(ordered),
        "gross_usd": sum(float(row["gross_usd"]) for row in ordered),
        "observed_usd": sum(float(row["observed_usd"]) for row in ordered),
        "double_spread_usd": net,
        "double_spread_wins": sum(value > 0 for value in pnl),
        "double_spread_losses": sum(value < 0 for value in pnl),
        "double_spread_zeros": sum(value == 0 for value in pnl),
        "double_spread_profit_factor": profit_factor,
        "maximum_closed_drawdown_usd": maximum_drawdown,
        "maximum_closed_drawdown_percent": maximum_drawdown_percent,
        "net_to_drawdown": net / maximum_drawdown if maximum_drawdown > 0 else None,
        "minimum_balance_usd": minimum_balance,
        "ending_balance_usd": balance,
        "win_rate": sum(value > 0 for value in pnl) / len(pnl) if pnl else None,
        "mean_double_spread_usd": statistics.fmean(pnl) if pnl else None,
        "median_double_spread_usd": statistics.median(pnl) if pnl else None,
    }


def metric_pass(value: float | None, threshold: float) -> bool:
    return value is not None and value >= threshold


def p1_views(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "pooled": book_metrics(rows),
        "calendar_splits": {
            "P1_2022H2": book_metrics(
                [row for row in rows if row["signal_server_time"][:4] == "2022"]
            ),
            "P1_2023": book_metrics(
                [row for row in rows if row["signal_server_time"][:4] == "2023"]
            ),
        },
        "signal_sides": {
            side: book_metrics([row for row in rows if row["side"] == side])
            for side in ("UP", "DOWN")
        },
    }


def p1_gate(views: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    pooled = views["pooled"]
    checks = {
        "double_spread_net_positive": pooled["double_spread_usd"] > 0,
        "profit_factor": metric_pass(
            pooled["double_spread_profit_factor"], gate["minimum_profit_factor"]
        ),
        "net_to_drawdown": metric_pass(
            pooled["net_to_drawdown"], gate["minimum_net_to_drawdown"]
        ),
        "P1_2022H2_net_positive": views["calendar_splits"]["P1_2022H2"][
            "double_spread_usd"
        ]
        > 0,
        "P1_2023_net_positive": views["calendar_splits"]["P1_2023"][
            "double_spread_usd"
        ]
        > 0,
        "UP_net_positive": views["signal_sides"]["UP"]["double_spread_usd"] > 0,
        "DOWN_net_positive": views["signal_sides"]["DOWN"]["double_spread_usd"] > 0,
    }
    return {
        "checks": checks,
        "passed_count": sum(checks.values()),
        "total_count": len(checks),
        "passed": all(checks.values()),
    }


def confirmation_gate(
    period_rows: dict[str, list[dict[str, Any]]],
    all_rows: list[dict[str, Any]],
    gate: dict[str, Any],
) -> dict[str, Any]:
    period_metrics = {
        "P1": book_metrics([row for row in all_rows if row["period"] == "P1"]),
        **{period: book_metrics(rows) for period, rows in period_rows.items()},
    }
    confirmation_rows = period_rows["P2"] + period_rows["P3"] + period_rows["P4"]
    confirmation = book_metrics(confirmation_rows)
    latest = period_metrics["P5"]
    full = book_metrics(all_rows)
    full_side = {
        side: book_metrics([row for row in all_rows if row["side"] == side])
        for side in ("UP", "DOWN")
    }
    positive_period_nets = [
        metrics["double_spread_usd"]
        for metrics in period_metrics.values()
        if metrics["double_spread_usd"] > 0
    ]
    max_period_share = (
        max(positive_period_nets) / sum(positive_period_nets)
        if positive_period_nets
        else None
    )
    checks: dict[str, bool] = {}
    for period in ("P2", "P3", "P4"):
        checks[f"{period}_net_positive"] = period_metrics[period]["double_spread_usd"] > 0
        checks[f"{period}_profit_factor"] = metric_pass(
            period_metrics[period]["double_spread_profit_factor"],
            gate["minimum_each_confirmation_profit_factor"],
        )
    checks.update(
        {
            "pooled_confirmation_profit_factor": metric_pass(
                confirmation["double_spread_profit_factor"],
                gate["minimum_pooled_confirmation_profit_factor"],
            ),
            "pooled_confirmation_net_to_drawdown": metric_pass(
                confirmation["net_to_drawdown"],
                gate["minimum_pooled_confirmation_net_to_drawdown"],
            ),
            "latest_net_positive": latest["double_spread_usd"] > 0,
            "latest_profit_factor": metric_pass(
                latest["double_spread_profit_factor"], gate["minimum_latest_profit_factor"]
            ),
            "full_profit_factor": metric_pass(
                full["double_spread_profit_factor"], gate["minimum_full_profit_factor"]
            ),
            "full_net_to_drawdown": metric_pass(
                full["net_to_drawdown"], gate["minimum_full_net_to_drawdown"]
            ),
            "full_UP_net_positive": full_side["UP"]["double_spread_usd"] > 0,
            "full_DOWN_net_positive": full_side["DOWN"]["double_spread_usd"] > 0,
            "maximum_positive_period_share": max_period_share is not None
            and max_period_share <= gate["maximum_positive_period_share"],
        }
    )
    return {
        "period_metrics": period_metrics,
        "pooled_confirmation": confirmation,
        "latest": latest,
        "full": full,
        "full_signal_sides": full_side,
        "maximum_positive_period_share": max_period_share,
        "checks": checks,
        "passed_count": sum(checks.values()),
        "total_count": len(checks),
        "passed": all(checks.values()),
    }


def run() -> dict[str, Any]:
    started = time.perf_counter()
    declaration = load_json(DECLARATION_PATH)
    if declaration["status"] != "UNIT_103_DECLARATION_FROZEN_OUTCOMES_UNOPENED":
        raise RuntimeError("declaration is not frozen and outcome-unopened")

    input_paths = [INPUT_ROOT / item["name"] for item in declaration["immutable_inputs"]["files"]]
    for expected, path in zip(declaration["immutable_inputs"]["files"], input_paths):
        if byte_count(path) != expected["bytes"] or sha256_file(path) != expected["sha256"]:
            raise RuntimeError(f"immutable input mismatch: {path.name}")
    if canonical_manifest(input_paths) != declaration["immutable_inputs"]["manifest_sha256"]:
        raise RuntimeError("input manifest mismatch")
    implementation = declaration["implementation"]
    script_path = REPO / implementation["script_path"]
    if byte_count(script_path) != implementation["script_bytes"] or sha256_file(script_path) != implementation["script_sha256"]:
        raise RuntimeError("frozen script mismatch")

    bars = {
        "US30": load_bars(INPUT_ROOT / "US30_H1_BARS_20220701_20260821.csv"),
        "US100": load_bars(INPUT_ROOT / "US100_H1_BARS_20220701_20260821.csv"),
    }
    common_epochs = sorted(set(bars["US30"]) & set(bars["US100"]))
    periods = declaration["fixed_periods"]
    variant_definitions = declaration["fixed_variants"]
    signals_by_variant: dict[str, list[Signal]] = {}
    structural_by_variant: dict[str, Any] = {}
    for variant, definition in variant_definitions.items():
        signals = build_structural_signals(
            variant,
            definition["leader"],
            definition["follower"],
            bars[definition["leader"]],
            bars[definition["follower"]],
            common_epochs,
            periods,
        )
        signals_by_variant[variant] = signals
        structural_by_variant[variant] = structural_summary(
            signals, common_epochs, bars[definition["follower"]], periods
        )

    structural = {
        "physical_rows": {
            "US30": len(bars["US30"]),
            "US100": len(bars["US100"]),
            "total": len(bars["US30"]) + len(bars["US100"]),
        },
        "common_epochs": len(common_epochs),
        "variants": structural_by_variant,
    }
    assert_nested_equal(
        structural,
        declaration["premetric_structural_feasibility"]["exact_anchors"],
        "structural",
    )

    trade_specs = load_json(INPUT_ROOT / "SYMBOL_TRADE_SPECS_V1.json")
    p1_results: dict[str, Any] = {}
    passing: list[str] = []
    for variant, signals in signals_by_variant.items():
        p1_signals = [signal for signal in signals if signal.period == "P1"]
        rows = economic_rows(p1_signals, bars, trade_specs)
        views = p1_views(rows)
        gate = p1_gate(views, declaration["fixed_p1_variant_selection_gate"])
        p1_results[variant] = {"views": views, "gate": gate}
        if gate["passed"]:
            passing.append(variant)

    selected: str | None = None
    if passing:
        selected = max(
            passing,
            key=lambda variant: (
                p1_results[variant]["views"]["pooled"]["net_to_drawdown"],
                p1_results[variant]["views"]["pooled"]["double_spread_profit_factor"],
                p1_results[variant]["views"]["pooled"]["double_spread_usd"],
                1 if variant == "US100_TO_US30" else 0,
            ),
        )

    later: dict[str, Any] | None = None
    if selected is None:
        verdict = "FAIL_H1_DIRECTIONAL_LEAD_LAG_NO_P1_VARIANT_NO_SEED"
        retained_seed = None
    else:
        all_selected_signals = signals_by_variant[selected]
        period_rows = {
            period: economic_rows(
                [signal for signal in all_selected_signals if signal.period == period],
                bars,
                trade_specs,
            )
            for period in ("P2", "P3", "P4", "P5")
        }
        p1_rows = economic_rows(
            [signal for signal in all_selected_signals if signal.period == "P1"],
            bars,
            trade_specs,
        )
        all_rows = p1_rows + period_rows["P2"] + period_rows["P3"] + period_rows["P4"] + period_rows["P5"]
        later = confirmation_gate(
            period_rows,
            all_rows,
            declaration["fixed_confirmation_latest_and_full_gate"],
        )
        if later["passed"]:
            verdict = "PASS_H1_DIRECTIONAL_LEAD_LAG_RETAIN_ONE_OPTIMIZATION_INFORMATION_SEED"
            retained_seed = f"FIXED_{selected}_ONE_HOUR_CONTINUATION"
        else:
            verdict = "FAIL_H1_DIRECTIONAL_LEAD_LAG_CONFIRMATION_OR_LATEST_NO_SEED"
            retained_seed = None

    elapsed = time.perf_counter() - started
    return {
        "schema": "zeta-next-two-index-h1-directional-lead-lag-response-result-v1",
        "created_at_local": "2026-08-29",
        "status": "UNIT_103_VALID_FIXED_AGGREGATION_COMPLETE",
        "unit": declaration["unit"],
        "family": declaration["family"],
        "declaration": {
            "path": str(DECLARATION_PATH.relative_to(REPO)).replace("\\", "/"),
            "bytes": byte_count(DECLARATION_PATH),
            "sha256": sha256_file(DECLARATION_PATH),
        },
        "execution": {
            "successful_formal_processes": 1,
            "economic_metric_reruns": 0,
            "internal_elapsed_seconds": elapsed,
            "new_data_acquisitions": 0,
            "runtime_copies": 0,
            "mql_changes": 0,
            "compile_paths": 0,
            "tester_paths": 0,
            "orders": 0,
            "broker_or_account_queries": 0,
        },
        "integrity_and_density": {
            "passed": True,
            "input_manifest_sha256": declaration["immutable_inputs"]["manifest_sha256"],
            "structural": structural,
            "faults": 0,
        },
        "P1_economics": p1_results,
        "selection": {
            "selected_variant": selected,
            "passing_variants": passing,
            "selection_tiebreak": declaration["fixed_p1_variant_selection_gate"]["selection"],
        },
        "confirmation_latest_and_full": later,
        "decision": {
            "verdict": verdict,
            "retained_seed": retained_seed,
            "P2_P5_economics_opened": selected is not None,
            "mt5_shortlist": None,
            "optimization_candidate": None,
            "live_authority": False,
        },
        "program_6_opened": False,
        "live_surface": "UNTOUCHED",
    }


def main() -> None:
    result = run()
    write_json(RAW_RESULT_PATH, result)
    write_json(TRACKED_RESULT_PATH, result)
    print(
        json.dumps(
            {
                "verdict": result["decision"]["verdict"],
                "selected_variant": result["selection"]["selected_variant"],
                "signals": sum(
                    item["total"]
                    for item in result["integrity_and_density"]["structural"]["variants"].values()
                ),
                "elapsed_seconds": result["execution"]["internal_elapsed_seconds"],
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
