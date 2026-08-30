from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


FAMILY = "us100-realized-variance-asymmetry-response-environment-correction-v1"
ROOT = Path(__file__).resolve().parents[4]
FAMILY_ROOT = ROOT / "lab" / "research" / FAMILY
RAW_ROOT = ROOT / "lab" / "artifacts" / "raw" / FAMILY
INPUT_ROOT = RAW_ROOT / "input"
OUTPUT_ROOT = RAW_ROOT / "output"

DECLARATION_PATH = FAMILY_ROOT / "evidence" / "US100_RVA_ENVIRONMENT_CORRECTION_DECLARATION_V1.json"
RECEIPT_PATH = FAMILY_ROOT / "evidence" / "US100_RVA_ENVIRONMENT_CORRECTION_ACQUISITION_RECEIPT_V1.json"
BAR_PATH = INPUT_ROOT / "US100_M15_BARS_20231201_20260731.csv"
SPEC_PATH = INPUT_ROOT / "US100_SYMBOL_SPEC_V1.json"
ANCHOR_PATH = INPUT_ROOT / "UNIT096_P1_SIGNAL_STRUCTURE.csv"
RAW_RESULT_PATH = OUTPUT_ROOT / "US100_RVA_ENVIRONMENT_CORRECTION_RAW_RESULT_V1.json"
RAW_OPPORTUNITY_PATH = OUTPUT_ROOT / "US100_RVA_ENVIRONMENT_CORRECTION_OPPORTUNITIES_V1.csv"

RETURN_WINDOW = 16
MINIMUM_SIGN_COUNT = 4
HORIZON_BARS = 4
IMBALANCE_THRESHOLD = 0.35
OBSERVATION_VOLUME = Decimal("0.01")
M15_SECONDS = 900

PERIODS = (
    ("P1_2024_H1", "2024-01-01T00:00:00Z", "2024-07-01T00:00:00Z"),
    ("P2_2024_H2", "2024-07-01T00:00:00Z", "2025-01-01T00:00:00Z"),
    ("P3_2025", "2025-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
    ("P4_2026_COMPLETE_MONTHS", "2026-01-01T00:00:00Z", "2026-08-01T00:00:00Z"),
)

P1_EXPECTED = {
    "eligible_variance_days": 128,
    "eligible_variance_evaluations": 4916,
    "finalized_bars": 11703,
    "triggers": 1530,
    "resolved": 1529,
    "unresolved": 1,
}


@dataclass(frozen=True)
class Bar:
    epoch: int
    server_time: str
    open_text: str
    close: float
    spread_points: int


@dataclass(frozen=True)
class StructuralRecord:
    period: str
    opportunity_id: int
    window_end_index: int
    entry_index: int
    resolve_index: int
    market_bars_held: int
    positive_returns: int
    negative_returns: int
    zero_returns: int
    positive_energy: float
    negative_energy: float
    total_energy: float
    variance_imbalance: float
    dominant_direction: int


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def parse_iso_epoch(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def parse_server_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y.%m.%d %H:%M:%S")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def verify_frozen_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    for path in (DECLARATION_PATH, RECEIPT_PATH, BAR_PATH, SPEC_PATH, ANCHOR_PATH):
        if not path.is_file():
            raise RuntimeError(f"required frozen input missing: {path}")
    declaration = load_json(DECLARATION_PATH)
    receipt = load_json(RECEIPT_PATH)
    pins = receipt["frozen_inputs"]
    expected = {
        DECLARATION_PATH: pins["declaration_sha256"],
        Path(__file__).resolve(): pins["proxy_script_sha256"],
        BAR_PATH: pins["bar_sha256"],
        SPEC_PATH: pins["spec_sha256"],
        ANCHOR_PATH: pins["structural_anchor_sha256"],
    }
    faults = []
    for path, expected_sha in expected.items():
        actual_sha = sha256(path)
        if actual_sha != expected_sha:
            faults.append(f"{path}: expected {expected_sha}, got {actual_sha}")
    if faults:
        raise RuntimeError("frozen input hash fault: " + "; ".join(faults))
    if declaration.get("unit") != "us100-realized-variance-asymmetry-response-environment-correction-120":
        raise RuntimeError("unexpected declaration unit")
    return declaration, receipt


def load_bars() -> list[Bar]:
    bars: list[Bar] = []
    prior_epoch: int | None = None
    with BAR_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        expected = {
            "time_epoch",
            "time_server",
            "open",
            "high",
            "low",
            "close",
            "tick_volume",
            "spread",
            "real_volume",
        }
        if set(reader.fieldnames or ()) != expected:
            raise RuntimeError(f"unexpected bar schema: {reader.fieldnames}")
        for row in reader:
            epoch = int(row["time_epoch"])
            if prior_epoch is not None and epoch <= prior_epoch:
                raise RuntimeError(f"bar epochs not strictly increasing at {epoch}")
            prior_epoch = epoch
            ohlc = tuple(float(row[name]) for name in ("open", "high", "low", "close"))
            if not all(math.isfinite(value) and value > 0.0 for value in ohlc):
                raise RuntimeError(f"invalid OHLC at {epoch}")
            if int(row["spread"]) < 0:
                raise RuntimeError(f"negative spread at {epoch}")
            bars.append(
                Bar(
                    epoch=epoch,
                    server_time=row["time_server"],
                    open_text=row["open"],
                    close=ohlc[3],
                    spread_points=int(row["spread"]),
                )
            )
    if not bars:
        raise RuntimeError("bar input is empty")
    return bars


def validate_spec(spec: dict[str, Any]) -> None:
    exact = {
        "symbol": "US100",
        "digits": 2,
        "point": 0.01,
        "trade_tick_size": 0.01,
        "trade_tick_value": 0.01,
        "trade_contract_size": 1.0,
        "volume_min": 0.01,
        "volume_step": 0.01,
    }
    faults = []
    for key, expected in exact.items():
        if spec.get(key) != expected:
            faults.append(f"{key}: expected {expected!r}, got {spec.get(key)!r}")
    if spec.get("currency_profit") != "USD":
        faults.append(f"currency_profit: expected USD, got {spec.get('currency_profit')!r}")
    if faults:
        raise RuntimeError("symbol specification fault: " + "; ".join(faults))


def build_period_structure(
    bars: list[Bar], period: str, start_epoch: int, end_epoch: int
) -> tuple[list[StructuralRecord], dict[str, Any]]:
    active_indices = [index for index, bar in enumerate(bars) if start_epoch <= bar.epoch < end_epoch]
    if len(active_indices) < 2:
        raise RuntimeError(f"insufficient bars in {period}")

    records: list[StructuralRecord] = []
    eligible_dates: set[str] = set()
    eligible_evaluations = 0
    triggers = 0
    active: dict[str, Any] | None = None
    rate_faults = 0

    for index in active_indices[1:]:
        if active is not None:
            active["market_bars_held"] += 1
            if active["market_bars_held"] >= HORIZON_BARS:
                records.append(
                    StructuralRecord(
                        period=period,
                        opportunity_id=len(records) + 1,
                        window_end_index=active["window_end_index"],
                        entry_index=active["entry_index"],
                        resolve_index=index,
                        market_bars_held=active["market_bars_held"],
                        positive_returns=active["positive_returns"],
                        negative_returns=active["negative_returns"],
                        zero_returns=active["zero_returns"],
                        positive_energy=active["positive_energy"],
                        negative_energy=active["negative_energy"],
                        total_energy=active["total_energy"],
                        variance_imbalance=active["variance_imbalance"],
                        dominant_direction=active["dominant_direction"],
                    )
                )
                active = None

        if active is not None:
            continue
        if index < RETURN_WINDOW + 1:
            rate_faults += 1
            continue
        window_indices = range(index, index - RETURN_WINDOW - 2, -1)
        if any(bars[left].epoch - bars[left - 1].epoch != M15_SECONDS for left in window_indices if left > index - RETURN_WINDOW - 1):
            continue

        positive_returns = 0
        negative_returns = 0
        zero_returns = 0
        positive_energy = 0.0
        negative_energy = 0.0
        valid = True
        for offset in range(1, RETURN_WINDOW + 1):
            ratio = bars[index - offset].close / bars[index - offset - 1].close
            if ratio <= 0.0 or not math.isfinite(ratio):
                valid = False
                break
            bar_return = math.log(ratio)
            if not math.isfinite(bar_return):
                valid = False
                break
            energy = bar_return * bar_return
            if bar_return > 0.0:
                positive_returns += 1
                positive_energy += energy
            elif bar_return < 0.0:
                negative_returns += 1
                negative_energy += energy
            else:
                zero_returns += 1
        if not valid:
            rate_faults += 1
            continue
        if positive_returns < MINIMUM_SIGN_COUNT or negative_returns < MINIMUM_SIGN_COUNT:
            continue
        total_energy = positive_energy + negative_energy
        if total_energy <= 0.0 or not math.isfinite(total_energy):
            rate_faults += 1
            continue
        variance_imbalance = (positive_energy - negative_energy) / total_energy
        if not math.isfinite(variance_imbalance):
            rate_faults += 1
            continue

        eligible_evaluations += 1
        eligible_dates.add(bars[index].server_time[:10])
        if abs(variance_imbalance) < IMBALANCE_THRESHOLD:
            continue
        triggers += 1
        active = {
            "window_end_index": index - 1,
            "entry_index": index,
            "market_bars_held": 0,
            "positive_returns": positive_returns,
            "negative_returns": negative_returns,
            "zero_returns": zero_returns,
            "positive_energy": positive_energy,
            "negative_energy": negative_energy,
            "total_energy": total_energy,
            "variance_imbalance": variance_imbalance,
            "dominant_direction": 1 if variance_imbalance > 0.0 else -1,
        }

    summary = {
        "period": period,
        "first_bar": bars[active_indices[0]].server_time,
        "last_bar": bars[active_indices[-1]].server_time,
        "finalized_bars": len(active_indices) - 1,
        "eligible_variance_days": len(eligible_dates),
        "eligible_variance_evaluations": eligible_evaluations,
        "triggers": triggers,
        "resolved": len(records),
        "unresolved": 1 if active is not None else 0,
        "rate_faults": rate_faults,
    }
    return records, summary


def compare_p1_anchor(bars: list[Bar], records: list[StructuralRecord]) -> dict[str, Any]:
    with ANCHOR_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        anchor = list(csv.DictReader(handle))
    if len(anchor) != len(records):
        raise RuntimeError(f"P1 structural count mismatch: anchor {len(anchor)}, proxy {len(records)}")

    maximum_positive_energy_difference = 0.0
    maximum_negative_energy_difference = 0.0
    maximum_total_energy_difference = 0.0
    maximum_imbalance_difference = 0.0
    exact_resolve_timestamps = 0

    for expected, actual in zip(anchor, records, strict=True):
        if int(expected["opportunity_id"]) != actual.opportunity_id:
            raise RuntimeError(f"P1 opportunity id mismatch at {actual.opportunity_id}")
        if expected["window_end_bar_time"] != bars[actual.window_end_index].server_time:
            raise RuntimeError(f"P1 window-end mismatch at {actual.opportunity_id}")
        if expected["entry_bar_time"] != bars[actual.entry_index].server_time:
            raise RuntimeError(f"P1 entry-bar mismatch at {actual.opportunity_id}")
        expected_resolve = parse_server_time(expected["resolve_time"])
        actual_resolve = parse_server_time(bars[actual.resolve_index].server_time)
        expected_resolve_bar = expected_resolve.replace(
            minute=(expected_resolve.minute // 15) * 15,
            second=0,
        )
        if expected_resolve_bar != actual_resolve:
            raise RuntimeError(f"P1 resolve-bar mismatch at {actual.opportunity_id}")
        if expected_resolve == actual_resolve:
            exact_resolve_timestamps += 1
        integer_fields = {
            "market_bars_held": actual.market_bars_held,
            "positive_returns": actual.positive_returns,
            "negative_returns": actual.negative_returns,
            "zero_returns": actual.zero_returns,
            "dominant_variance_direction": actual.dominant_direction,
            "counter_variance_direction": -actual.dominant_direction,
        }
        for key, actual_value in integer_fields.items():
            if int(expected[key]) != actual_value:
                raise RuntimeError(f"P1 {key} mismatch at {actual.opportunity_id}")
        maximum_positive_energy_difference = max(
            maximum_positive_energy_difference,
            abs(float(expected["positive_energy"]) - actual.positive_energy),
        )
        maximum_negative_energy_difference = max(
            maximum_negative_energy_difference,
            abs(float(expected["negative_energy"]) - actual.negative_energy),
        )
        maximum_total_energy_difference = max(
            maximum_total_energy_difference,
            abs(float(expected["total_energy"]) - actual.total_energy),
        )
        maximum_imbalance_difference = max(
            maximum_imbalance_difference,
            abs(float(expected["variance_imbalance"]) - actual.variance_imbalance),
        )

    energy_tolerance = 5e-12
    imbalance_tolerance = 5e-10
    if max(maximum_positive_energy_difference, maximum_negative_energy_difference, maximum_total_energy_difference) > energy_tolerance:
        raise RuntimeError("P1 structural energy parity tolerance failed")
    if maximum_imbalance_difference > imbalance_tolerance:
        raise RuntimeError("P1 structural imbalance parity tolerance failed")
    return {
        "anchor_rows": len(anchor),
        "proxy_rows": len(records),
        "all_m15_bar_coordinate_horizon_count_and_direction_identities_equal": True,
        "exact_resolve_timestamp_rows_descriptive": exact_resolve_timestamps,
        "maximum_positive_energy_abs_difference": maximum_positive_energy_difference,
        "maximum_negative_energy_abs_difference": maximum_negative_energy_difference,
        "maximum_total_energy_abs_difference": maximum_total_energy_difference,
        "maximum_variance_imbalance_abs_difference": maximum_imbalance_difference,
        "energy_tolerance": energy_tolerance,
        "imbalance_tolerance": imbalance_tolerance,
    }


def money_profit(
    bars: list[Bar], spec: dict[str, Any], record: StructuralRecord, direction: int, doubled: bool
) -> Decimal:
    entry_bar = bars[record.entry_index]
    exit_bar = bars[record.resolve_index]
    point = Decimal(str(spec["point"]))
    tick_size = Decimal(str(spec["trade_tick_size"]))
    tick_value = Decimal(str(spec["trade_tick_value"]))
    entry_bid = Decimal(entry_bar.open_text)
    exit_bid = Decimal(exit_bar.open_text)
    entry_spread = Decimal(entry_bar.spread_points) * point
    exit_spread = Decimal(exit_bar.spread_points) * point
    entry_ask = entry_bid + entry_spread
    exit_ask = exit_bid + exit_spread

    if direction > 0:
        open_price = entry_ask + (entry_spread if doubled else Decimal(0))
        close_price = exit_bid - (exit_spread if doubled else Decimal(0))
        signed_distance = close_price - open_price
    else:
        open_price = entry_bid - (entry_spread if doubled else Decimal(0))
        close_price = exit_ask + (exit_spread if doubled else Decimal(0))
        signed_distance = open_price - close_price
    raw = signed_distance / tick_size * tick_value * OBSERVATION_VOLUME
    return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def metric(values: list[Decimal]) -> dict[str, Any]:
    gross_profit = sum((value for value in values if value > 0), Decimal(0))
    gross_loss = sum((value for value in values if value < 0), Decimal(0))
    net = sum(values, Decimal(0))
    peak = Decimal(0)
    cumulative = Decimal(0)
    maximum_drawdown = Decimal(0)
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        maximum_drawdown = max(maximum_drawdown, peak - cumulative)
    profit_factor = None if gross_loss == 0 else float(gross_profit / -gross_loss)
    net_over_drawdown = None if maximum_drawdown == 0 else float(net / maximum_drawdown)
    return {
        "opportunities": len(values),
        "wins": sum(value > 0 for value in values),
        "losses": sum(value < 0 for value in values),
        "zeros": sum(value == 0 for value in values),
        "gross_profit_usd": float(gross_profit),
        "gross_loss_usd": float(gross_loss),
        "net_usd": float(net),
        "profit_factor": profit_factor,
        "maximum_closed_drawdown_usd": float(maximum_drawdown),
        "net_over_maximum_closed_drawdown": net_over_drawdown,
    }


def compute_economics(
    bars: list[Bar], spec: dict[str, Any], structures: dict[str, list[StructuralRecord]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    direction_rows: dict[str, dict[str, list[Decimal]]] = {
        "DOMINANT_VARIANCE": {period: [] for period, _, _ in PERIODS},
        "COUNTER_VARIANCE": {period: [] for period, _, _ in PERIODS},
    }
    observed_rows: dict[str, dict[str, list[Decimal]]] = {
        "DOMINANT_VARIANCE": {period: [] for period, _, _ in PERIODS},
        "COUNTER_VARIANCE": {period: [] for period, _, _ in PERIODS},
    }
    raw_rows: list[dict[str, Any]] = []

    for period, _, _ in PERIODS:
        for record in structures[period]:
            dominant_observed = money_profit(bars, spec, record, record.dominant_direction, False)
            dominant_double = money_profit(bars, spec, record, record.dominant_direction, True)
            counter_observed = money_profit(bars, spec, record, -record.dominant_direction, False)
            counter_double = money_profit(bars, spec, record, -record.dominant_direction, True)
            observed_rows["DOMINANT_VARIANCE"][period].append(dominant_observed)
            observed_rows["COUNTER_VARIANCE"][period].append(counter_observed)
            direction_rows["DOMINANT_VARIANCE"][period].append(dominant_double)
            direction_rows["COUNTER_VARIANCE"][period].append(counter_double)
            raw_rows.append(
                {
                    "period": period,
                    "opportunity_id": record.opportunity_id,
                    "window_end_bar_time": bars[record.window_end_index].server_time,
                    "entry_bar_time": bars[record.entry_index].server_time,
                    "resolve_bar_time": bars[record.resolve_index].server_time,
                    "variance_imbalance": record.variance_imbalance,
                    "dominant_direction": record.dominant_direction,
                    "dominant_observed_usd": str(dominant_observed),
                    "dominant_double_spread_usd": str(dominant_double),
                    "counter_observed_usd": str(counter_observed),
                    "counter_double_spread_usd": str(counter_double),
                }
            )

    economics: dict[str, Any] = {}
    for direction in ("DOMINANT_VARIANCE", "COUNTER_VARIANCE"):
        period_metrics: dict[str, Any] = {}
        pooled_observed: list[Decimal] = []
        pooled_double: list[Decimal] = []
        positive_path_nets: list[Decimal] = []
        for period, _, _ in PERIODS:
            observed_values = observed_rows[direction][period]
            double_values = direction_rows[direction][period]
            pooled_observed.extend(observed_values)
            pooled_double.extend(double_values)
            observed_metric = metric(observed_values)
            double_metric = metric(double_values)
            period_metrics[period] = {"observed": observed_metric, "double_spread": double_metric}
            if double_metric["net_usd"] > 0:
                positive_path_nets.append(Decimal(str(double_metric["net_usd"])))
        positive_total = sum(positive_path_nets, Decimal(0))
        maximum_positive_share = (
            None if positive_total == 0 else float(max(positive_path_nets) / positive_total)
        )
        economics[direction] = {
            "paths": period_metrics,
            "pooled": {
                "observed": metric(pooled_observed),
                "double_spread": metric(pooled_double),
                "positive_paths_double_spread": len(positive_path_nets),
                "maximum_positive_path_contribution_share": maximum_positive_share,
            },
        }
    return economics, raw_rows


def write_raw_opportunities(rows: list[dict[str, Any]]) -> None:
    temp_path = RAW_OPPORTUNITY_PATH.with_suffix(RAW_OPPORTUNITY_PATH.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp_path, RAW_OPPORTUNITY_PATH)


def main() -> int:
    started = time.perf_counter()
    if RAW_RESULT_PATH.exists() or RAW_OPPORTUNITY_PATH.exists():
        raise RuntimeError("formal output already exists; do not overwrite or rerun economics")
    declaration, receipt = verify_frozen_inputs()
    bars = load_bars()
    spec = load_json(SPEC_PATH)
    validate_spec(spec)

    structures: dict[str, list[StructuralRecord]] = {}
    summaries: dict[str, Any] = {}
    for period, start, end in PERIODS:
        records, summary = build_period_structure(
            bars, period, parse_iso_epoch(start), parse_iso_epoch(end)
        )
        structures[period] = records
        summaries[period] = summary
        if summary["rate_faults"] != 0:
            raise RuntimeError(f"structural rate fault in {period}")
        if summary["resolved"] != summary["triggers"] - summary["unresolved"]:
            raise RuntimeError(f"trigger-resolution identity fault in {period}")

    p1_summary = summaries["P1_2024_H1"]
    for key, expected in P1_EXPECTED.items():
        if p1_summary[key] != expected:
            raise RuntimeError(f"P1 aggregate mismatch {key}: expected {expected}, got {p1_summary[key]}")
    p1_parity = compare_p1_anchor(bars, structures["P1_2024_H1"])

    pooled_days = sum(summary["eligible_variance_days"] for summary in summaries.values())
    pooled_resolved = sum(summary["resolved"] for summary in summaries.values())
    pooled_rate = pooled_resolved / pooled_days
    paths_at_quarter = sum(
        summary["resolved"] / summary["eligible_variance_days"] >= 0.25
        for summary in summaries.values()
    )
    frequency_gates = {
        "pooled_at_least_0_40": pooled_rate >= 0.40,
        "at_least_three_paths_at_0_25": paths_at_quarter >= 3,
        "pooled_at_least_200": pooled_resolved >= 200,
        "pooled_resolved": pooled_resolved,
        "pooled_eligible_variance_days": pooled_days,
        "pooled_opportunities_per_eligible_variance_day": pooled_rate,
        "paths_at_least_0_25": paths_at_quarter,
    }
    frequency_gates["all_pass"] = all(
        frequency_gates[key]
        for key in ("pooled_at_least_0_40", "at_least_three_paths_at_0_25", "pooled_at_least_200")
    )

    economics, raw_rows = compute_economics(bars, spec, structures)
    economic_gates: dict[str, Any] = {}
    passing_directions: list[str] = []
    for direction, result in economics.items():
        pooled = result["pooled"]
        stressed = pooled["double_spread"]
        gates = {
            "positive_pooled_double_spread_net": stressed["net_usd"] > 0,
            "pooled_double_spread_profit_factor_at_least_1_10": (
                stressed["profit_factor"] is not None and stressed["profit_factor"] >= 1.10
            ),
            "positive_double_spread_paths_at_least_three": pooled["positive_paths_double_spread"] >= 3,
            "pooled_net_over_maximum_closed_drawdown_at_least_1_50": (
                stressed["net_over_maximum_closed_drawdown"] is not None
                and stressed["net_over_maximum_closed_drawdown"] >= 1.50
            ),
            "maximum_positive_path_contribution_share_at_most_0_70": (
                pooled["maximum_positive_path_contribution_share"] is not None
                and pooled["maximum_positive_path_contribution_share"] <= 0.70
            ),
        }
        gates["all_pass"] = frequency_gates["all_pass"] and all(gates.values())
        economic_gates[direction] = gates
        if gates["all_pass"]:
            passing_directions.append(direction)

    passing_directions.sort(
        key=lambda direction: (
            economics[direction]["pooled"]["double_spread"]["net_usd"],
            economics[direction]["pooled"]["double_spread"]["profit_factor"] or -math.inf,
            economics[direction]["pooled"]["positive_paths_double_spread"],
            direction,
        ),
        reverse=True,
    )
    selected = passing_directions[0] if passing_directions else None
    verdict = (
        f"PASS_US100_REALIZED_VARIANCE_ASYMMETRY_{selected}_RETAIN_ONE_INFORMATION_SEED"
        if selected
        else "FAIL_US100_REALIZED_VARIANCE_ASYMMETRY_NO_DIRECTION_NO_SEED"
    )

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    write_raw_opportunities(raw_rows)
    result = {
        "schema": "zeta-next-us100-realized-variance-asymmetry-response-environment-correction-raw-result-v1",
        "created_at_local": "2026-08-30",
        "status": "ONE_VALID_FIXED_PROXY_AGGREGATION_COMPLETE",
        "unit": declaration["unit"],
        "family": FAMILY,
        "frozen_inputs": receipt["frozen_inputs"],
        "bar_surface": {
            "rows": len(bars),
            "first": bars[0].server_time,
            "last": bars[-1].server_time,
        },
        "symbol_spec": spec,
        "structural_integrity": {
            "all_pass": True,
            "p1_parent_parity": p1_parity,
            "period_summaries": summaries,
        },
        "frequency_gates": frequency_gates,
        "economics": economics,
        "economic_gates": economic_gates,
        "passing_directions_in_selection_order": passing_directions,
        "selected_direction": selected,
        "verdict": verdict,
        "raw_opportunity_artifact": {
            "path": str(RAW_OPPORTUNITY_PATH.relative_to(ROOT)).replace("\\", "/"),
            "rows": len(raw_rows),
            "bytes": RAW_OPPORTUNITY_PATH.stat().st_size,
            "sha256": sha256(RAW_OPPORTUNITY_PATH),
        },
        "execution": {
            "successful_fixed_proxy_aggregations": 1,
            "economic_metric_reruns": 0,
            "tester_paths": 0,
            "mql_copies_or_changes": 0,
            "orders_or_positions": 0,
            "elapsed_seconds": time.perf_counter() - started,
        },
        "program_6_opened": False,
        "broker_or_account_state_queried": False,
        "optimization_surface": "UNTOUCHED_BY_UNIT_120",
        "live_surface": "UNTOUCHED",
    }
    temp_path = RAW_RESULT_PATH.with_suffix(RAW_RESULT_PATH.suffix + ".tmp")
    temp_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp_path, RAW_RESULT_PATH)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
