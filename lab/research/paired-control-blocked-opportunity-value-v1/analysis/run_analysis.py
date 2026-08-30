from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


FAMILY_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = FAMILY_ROOT / "config" / "contract.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def as_float(row: dict[str, str], field: str) -> float:
    value = float(row[field])
    if not math.isfinite(value):
        raise ValueError(f"non-finite {field}")
    return value


def count(rows: Iterable[dict[str, str]], field: str, value: str) -> int:
    return sum(row[field] == value for row in rows)


def period_id(config: dict[str, Any], timestamp: str) -> str:
    for period in config["periods"]:
        if period["start"] <= timestamp < period["end_exclusive"]:
            return period["id"]
    raise ValueError(f"timestamp outside frozen periods: {timestamp}")


def selection_control_rows(config: dict[str, Any], rows: list[dict[str, str]]) -> list[dict[str, str]]:
    starts = [
        index
        for index, row in enumerate(rows)
        if row["event"] == "BIRTH" and row["position_identifier"] == "2"
    ]
    expected = config["extraction"]["selection_control_position_two_birth_row_starts_zero_based"]
    if starts != expected:
        raise ValueError(f"selection segment starts changed: {starts}")
    segment = config["extraction"]["selection_control_segment_index_zero_based"]
    return rows[starts[segment] : starts[segment + 1]]


def forward_control_rows(config: dict[str, Any], rows: list[dict[str, str]]) -> list[dict[str, str]]:
    target_run = config["extraction"]["forward_control_birth_time_decrease_run_index_zero_based"]
    minimum_time = config["extraction"]["forward_control_minimum_entry_time"]
    run = 0
    previous_birth = ""
    selected: list[dict[str, str]] = []
    for row in rows:
        if row["event"] == "BIRTH":
            birth_time = row["entry_time_server"]
            if previous_birth and birth_time < previous_birth:
                run += 1
            previous_birth = birth_time
        if run == target_run and row["entry_time_server"] >= minimum_time:
            selected.append(row)
    return selected


def build_window_matches(
    config: dict[str, Any],
    window: str,
    candidate_rows: list[dict[str, str]],
    control_rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    block_filter = config["block_filter"]
    blocks = [
        row
        for row in candidate_rows
        if row["stage"] == block_filter["stage"] and row["result"] == block_filter["result"]
    ]
    expected_blocks = block_filter["expected_blocks"][window]
    if len(blocks) != expected_blocks:
        raise ValueError(f"{window} block count changed: {len(blocks)}")
    block_keys = [(row["component_id"], row["server_time"], row["direction"]) for row in blocks]
    if len(block_keys) != len(set(block_keys)):
        raise ValueError(f"{window} candidate block keys are not unique")

    births_by_key: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    closes_by_key: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in control_rows:
        if row["event"] == "BIRTH":
            key = (row["component_id"], row["entry_time_server"], row["direction"])
            births_by_key[key].append(row)
        elif row["event"] == "CLOSE":
            key = (row["position_identifier"], row["entry_time_server"], row["component_id"])
            closes_by_key[key].append(row)

    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    tolerance = config["match_contract"]["entry_price_abs_tolerance"]
    feature_tolerance = config["match_contract"]["entry_feature_abs_tolerance"]
    for block in blocks:
        birth_key = (block["component_id"], block["server_time"], block["direction"])
        births = births_by_key.get(birth_key, [])
        if len(births) != 1:
            unmatched.append(
                {
                    "window": window,
                    "server_time": block["server_time"],
                    "component_id": block["component_id"],
                    "symbol": block["symbol"],
                    "direction": int(block["direction"]),
                    "reason": f"control_birth_count_{len(births)}",
                }
            )
            continue
        birth = births[0]
        close_key = (birth["position_identifier"], birth["entry_time_server"], birth["component_id"])
        closes = closes_by_key.get(close_key, [])
        if len(closes) != 1:
            unmatched.append(
                {
                    "window": window,
                    "server_time": block["server_time"],
                    "component_id": block["component_id"],
                    "symbol": block["symbol"],
                    "direction": int(block["direction"]),
                    "reason": f"control_close_count_{len(closes)}",
                }
            )
            continue
        candidate_price = as_float(block, "order_price")
        control_price = as_float(birth, "entry_price")
        price_difference = abs(candidate_price - control_price)
        if price_difference > tolerance:
            raise ValueError(f"{window} matched entry price differs by {price_difference}")
        feature_difference = abs(as_float(block, "feature") - as_float(birth, "entry_feature"))
        if feature_difference > feature_tolerance:
            raise ValueError(f"{window} matched entry feature differs by {feature_difference}")
        candidate_volume = as_float(block, "volume")
        control_volume = as_float(birth, "volume")
        if candidate_volume <= 0 or control_volume <= 0:
            raise ValueError(f"{window} nonpositive matched volume")
        candidate_attempted_risk = as_float(block, "attempted_planned_risk_usd")
        control_planned_risk = as_float(birth, "planned_risk_usd")
        if candidate_attempted_risk <= 0 or control_planned_risk <= 0:
            raise ValueError(f"{window} nonpositive matched risk")
        matched.append(
            {
                "window": window,
                "period": period_id(config, block["server_time"]),
                "block": block,
                "birth": birth,
                "close": closes[0],
                "entry_price_abs_difference": price_difference,
                "entry_feature_abs_difference": feature_difference,
                "candidate_volume": candidate_volume,
                "control_volume": control_volume,
                "volume_ratio": candidate_volume / control_volume,
                "candidate_attempted_risk_usd": candidate_attempted_risk,
                "control_planned_risk_usd": control_planned_risk,
            }
        )
    return matched, unmatched, {"blocks": len(blocks), "births": count(control_rows, "event", "BIRTH"), "closes": count(control_rows, "event", "CLOSE")}


def profit_factor(values: list[float]) -> float | None:
    positive = sum(value for value in values if value > 0)
    negative = -sum(value for value in values if value < 0)
    if negative == 0:
        return None if positive == 0 else math.inf
    return positive / negative


def group_net(rows: list[dict[str, Any]], field: str) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        totals[str(row[field])] += row["shadow_stressed_usd"]
    return dict(sorted(totals.items()))


def absolute_group_share(groups: dict[str, float]) -> float:
    denominator = sum(abs(value) for value in groups.values())
    if denominator == 0:
        return 0.0
    return max(abs(value) for value in groups.values()) / denominator


def economic_rows(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for match in matches:
        close = match["close"]
        control_risk = match["control_planned_risk_usd"]
        if control_risk <= 0:
            raise ValueError("nonpositive paired-control planned risk")
        actual = as_float(close, "actual_net_usd")
        stressed = as_float(close, "stressed_net_usd")
        ratio = match["volume_ratio"]
        output.append(
            {
                "window": match["window"],
                "period": match["period"],
                "server_time": match["block"]["server_time"],
                "component_id": match["block"]["component_id"],
                "symbol": match["block"]["symbol"],
                "direction": int(match["block"]["direction"]),
                "candidate_order_price": as_float(match["block"], "order_price"),
                "control_entry_price": as_float(match["birth"], "entry_price"),
                "control_exit_price": as_float(close, "exit_price"),
                "control_exit_time_server": close["server_time"],
                "control_exit_class": close["exit_class"],
                "candidate_volume": match["candidate_volume"],
                "control_volume": match["control_volume"],
                "volume_ratio": ratio,
                "candidate_attempted_risk_usd": match["candidate_attempted_risk_usd"],
                "control_planned_risk_usd": control_risk,
                "control_actual_net_usd": actual,
                "control_stressed_net_usd": stressed,
                "actual_r": actual / control_risk,
                "stressed_r": stressed / control_risk,
                "shadow_actual_usd": actual * ratio,
                "shadow_stressed_usd": stressed * ratio,
            }
        )
    return output


def summarize(rows: list[dict[str, Any]], period_domain: list[str]) -> dict[str, Any]:
    actual_values = [row["shadow_actual_usd"] for row in rows]
    stressed_values = [row["shadow_stressed_usd"] for row in rows]
    control_actual_values = [row["control_actual_net_usd"] for row in rows]
    control_stressed_values = [row["control_stressed_net_usd"] for row in rows]
    attempted_risks = [row["candidate_attempted_risk_usd"] for row in rows]
    volume_ratios = sorted(row["volume_ratio"] for row in rows)
    attempted_to_control_risk_ratios = sorted(
        row["candidate_attempted_risk_usd"] / row["control_planned_risk_usd"] for row in rows
    )
    periods = group_net(rows, "period")
    books = group_net(rows, "symbol")
    components = group_net(rows, "component_id")
    for period in period_domain:
        periods.setdefault(period, 0.0)
    single_denominator = sum(abs(value) for value in stressed_values)
    return {
        "matched_rows": len(rows),
        "paired_control_actual_net_usd": sum(control_actual_values),
        "paired_control_stressed_net_usd": sum(control_stressed_values),
        "paired_control_actual_profit_factor": profit_factor(control_actual_values),
        "paired_control_stressed_profit_factor": profit_factor(control_stressed_values),
        "shadow_actual_net_usd": sum(actual_values),
        "shadow_stressed_net_usd": sum(stressed_values),
        "shadow_actual_profit_factor": profit_factor(actual_values),
        "shadow_stressed_profit_factor": profit_factor(stressed_values),
        "mean_actual_r": sum(row["actual_r"] for row in rows) / len(rows),
        "mean_stressed_r": sum(row["stressed_r"] for row in rows) / len(rows),
        "median_stressed_r": sorted(row["stressed_r"] for row in rows)[len(rows) // 2],
        "candidate_attempted_risk_usd": sum(attempted_risks),
        "shadow_actual_net_over_candidate_attempted_risk": sum(actual_values) / sum(attempted_risks),
        "shadow_stressed_net_over_candidate_attempted_risk": sum(stressed_values) / sum(attempted_risks),
        "volume_ratio_min_median_max": [volume_ratios[0], volume_ratios[len(rows) // 2], volume_ratios[-1]],
        "candidate_attempted_to_control_risk_ratio_min_median_max": [
            attempted_to_control_risk_ratios[0],
            attempted_to_control_risk_ratios[len(rows) // 2],
            attempted_to_control_risk_ratios[-1],
        ],
        "stop_rate": sum(row["control_exit_class"] == "STOP" for row in rows) / len(rows),
        "period_stressed_net_usd": dict(sorted(periods.items())),
        "book_stressed_net_usd": books,
        "component_stressed_net_usd": components,
        "positive_periods": sum(periods[period] > 0 for period in period_domain),
        "negative_periods": sum(periods[period] < 0 for period in period_domain),
        "positive_books": sum(value > 0 for value in books.values()),
        "negative_books": sum(value < 0 for value in books.values()),
        "positive_components": sum(value > 0 for value in components.values()),
        "negative_components": sum(value < 0 for value in components.values()),
        "maximum_absolute_period_net_share": absolute_group_share(periods),
        "maximum_absolute_component_net_share": absolute_group_share(components),
        "maximum_single_row_absolute_net_share": (
            max(abs(value) for value in stressed_values) / single_denominator if single_denominator else 0.0
        ),
    }


def finite_json_value(value: Any) -> Any:
    if isinstance(value, float) and math.isinf(value):
        return "INF"
    if isinstance(value, dict):
        return {key: finite_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [finite_json_value(item) for item in value]
    return value


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "window",
        "period",
        "server_time",
        "component_id",
        "symbol",
        "direction",
        "candidate_order_price",
        "control_entry_price",
        "control_exit_price",
        "control_exit_time_server",
        "control_exit_class",
        "candidate_volume",
        "control_volume",
        "volume_ratio",
        "candidate_attempted_risk_usd",
        "control_planned_risk_usd",
        "control_actual_net_usd",
        "control_stressed_net_usd",
        "actual_r",
        "stressed_r",
        "shadow_actual_usd",
        "shadow_stressed_usd",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    input_root = REPO_ROOT / config["input_root"]
    input_receipt: list[dict[str, Any]] = []
    for declared in config["inputs"]:
        path = input_root / declared["name"]
        actual = {"name": declared["name"], "bytes": path.stat().st_size, "sha256": sha256(path)}
        if actual["bytes"] != declared["bytes"] or actual["sha256"] != declared["sha256"]:
            raise ValueError(f"input pin mismatch: {declared['name']}")
        input_receipt.append(actual)

    selection_candidates = load_csv(input_root / "candidate-selection-candidates.csv")
    selection_control = selection_control_rows(
        config, load_csv(input_root / "control-selection-agent3000-lifecycles.csv")
    )
    forward_candidates = load_csv(input_root / "candidate-forward-candidates.csv")
    forward_control = forward_control_rows(
        config, load_csv(input_root / "control-forward-agent3001-lifecycles.csv")
    )
    august_candidates = load_csv(input_root / "candidate-august-candidates.csv")
    august_control = load_csv(input_root / "control-august-lifecycles.csv")

    expected = config["extraction"]
    integrity_counts = {
        "selection_control_births": count(selection_control, "event", "BIRTH"),
        "selection_control_closes": count(selection_control, "event", "CLOSE"),
        "forward_control_births": count(forward_control, "event", "BIRTH"),
        "forward_control_closes": count(forward_control, "event", "CLOSE"),
        "august_control_births": count(august_control, "event", "BIRTH"),
        "august_control_closes": count(august_control, "event", "CLOSE"),
    }
    required_counts = {
        "selection_control_births": expected["selection_expected_births"],
        "selection_control_closes": expected["selection_expected_closes"],
        "forward_control_births": expected["forward_expected_births"],
        "forward_control_closes": expected["forward_expected_closes"],
        "august_control_births": expected["august_expected_births"],
        "august_control_closes": expected["august_expected_closes"],
    }
    if integrity_counts != required_counts:
        raise ValueError(f"control extraction counts changed: {integrity_counts}")

    windows = {
        "selection": build_window_matches(config, "selection", selection_candidates, selection_control),
        "forward": build_window_matches(config, "forward", forward_candidates, forward_control),
        "august": build_window_matches(config, "august", august_candidates, august_control),
    }
    complete_matches = {name: len(value[0]) for name, value in windows.items()}
    expected_matches = config["match_contract"]["expected_complete_matches"]
    if any(complete_matches[name] != expected_matches[name] for name in windows):
        raise ValueError(f"complete match counts changed: {complete_matches}")
    total_matches = sum(complete_matches.values())
    if total_matches != expected_matches["total"]:
        raise ValueError(f"total complete matches changed: {total_matches}")

    total_blocks = sum(value[2]["blocks"] for value in windows.values())
    match_fraction = total_matches / total_blocks
    matched_all = [match for value in windows.values() for match in value[0]]
    components = sorted({match["block"]["component_id"] for match in matched_all})
    symbols = sorted({match["block"]["symbol"] for match in matched_all})
    periods = sorted({match["period"] for match in matched_all})
    if match_fraction < config["match_contract"]["minimum_total_match_fraction"]:
        raise ValueError("matched fraction below frozen structural gate")
    if components != sorted(config["match_contract"]["required_components"]):
        raise ValueError(f"component coverage changed: {components}")
    if symbols != sorted(config["match_contract"]["required_symbols"]):
        raise ValueError(f"symbol coverage changed: {symbols}")
    if periods != sorted(config["match_contract"]["required_periods"]):
        raise ValueError(f"period coverage changed: {periods}")

    selection_rows = economic_rows(windows["selection"][0])
    selection = summarize(selection_rows, ["E1", "E2", "E3", "E4"])
    favorable = config["selection_favorable_gates"]
    selection_favorable_gates = {
        "shadow_actual_net_strictly_positive": selection["shadow_actual_net_usd"] > 0,
        "shadow_stressed_net_min_usd": selection["shadow_stressed_net_usd"] >= favorable["shadow_stressed_net_min_usd"],
        "shadow_stressed_profit_factor_min": selection["shadow_stressed_profit_factor"] is not None
        and selection["shadow_stressed_profit_factor"] >= favorable["shadow_stressed_profit_factor_min"],
        "mean_stressed_r_min": selection["mean_stressed_r"] >= favorable["mean_stressed_r_min"],
        "positive_periods_min_of_four": selection["positive_periods"] >= favorable["positive_periods_min_of_four"],
        "positive_books_required": selection["positive_books"] >= favorable["positive_books_required"],
        "positive_components_min_of_three": selection["positive_components"] >= favorable["positive_components_min_of_three"],
        "maximum_absolute_component_net_share": selection["maximum_absolute_component_net_share"]
        <= favorable["maximum_absolute_component_net_share"],
        "maximum_absolute_period_net_share": selection["maximum_absolute_period_net_share"]
        <= favorable["maximum_absolute_period_net_share"],
    }
    selection_favorable = all(selection_favorable_gates.values())

    adverse = config["selection_strong_adverse_gates"]
    selection_strong_adverse_gates = {
        "shadow_stressed_net_max_usd": selection["shadow_stressed_net_usd"] <= adverse["shadow_stressed_net_max_usd"],
        "shadow_stressed_profit_factor_max": selection["shadow_stressed_profit_factor"] is not None
        and selection["shadow_stressed_profit_factor"] <= adverse["shadow_stressed_profit_factor_max"],
        "mean_stressed_r_max": selection["mean_stressed_r"] <= adverse["mean_stressed_r_max"],
        "negative_periods_min_of_four": selection["negative_periods"] >= adverse["negative_periods_min_of_four"],
        "negative_books_required": selection["negative_books"] >= adverse["negative_books_required"],
        "negative_components_min_of_three": selection["negative_components"] >= adverse["negative_components_min_of_three"],
    }
    selection_strong_adverse = all(selection_strong_adverse_gates.values())

    confirmation_opened = selection_favorable
    confirmation_rows: list[dict[str, Any]] = []
    confirmation: dict[str, Any] | None = None
    confirmation_gates: dict[str, bool] | None = None
    confirmation_favorable = False
    if confirmation_opened:
        confirmation_rows = economic_rows(windows["forward"][0] + windows["august"][0])
        confirmation = summarize(confirmation_rows, ["JUNE", "JULY", "AUGUST"])
        confirm = config["confirmation_favorable_gates"]
        confirmation_gates = {
            "shadow_actual_net_strictly_positive": confirmation["shadow_actual_net_usd"] > 0,
            "shadow_stressed_net_min_usd": confirmation["shadow_stressed_net_usd"] >= confirm["shadow_stressed_net_min_usd"],
            "shadow_stressed_profit_factor_min": confirmation["shadow_stressed_profit_factor"] is not None
            and confirmation["shadow_stressed_profit_factor"] >= confirm["shadow_stressed_profit_factor_min"],
            "mean_stressed_r_min": confirmation["mean_stressed_r"] >= confirm["mean_stressed_r_min"],
            "positive_periods_min_of_three": confirmation["positive_periods"] >= confirm["positive_periods_min_of_three"],
            "positive_books_required": confirmation["positive_books"] >= confirm["positive_books_required"],
            "positive_components_min_of_three": confirmation["positive_components"] >= confirm["positive_components_min_of_three"],
            "maximum_absolute_component_net_share": confirmation["maximum_absolute_component_net_share"]
            <= confirm["maximum_absolute_component_net_share"],
            "maximum_single_row_absolute_net_share": confirmation["maximum_single_row_absolute_net_share"]
            <= confirm["maximum_single_row_absolute_net_share"],
        }
        confirmation_favorable = all(confirmation_gates.values())

    verdicts = config["verdicts"]
    if selection_favorable and confirmation_favorable:
        verdict = verdicts["favorable_confirmed"]
        retained_seed = "ONE_NONAUTOMATIC_SHARED_ACCOUNT_ADMISSION_DISPLACEMENT_CAUSAL_QUESTION"
    elif selection_favorable:
        verdict = verdicts["favorable_not_confirmed"]
        retained_seed = None
    elif selection_strong_adverse:
        verdict = verdicts["strong_adverse"]
        retained_seed = None
    else:
        verdict = verdicts["ambiguous"]
        retained_seed = None

    output_rows = selection_rows + confirmation_rows
    matched_path = REPO_ROOT / config["outputs"]["matched_rows"]
    write_rows(matched_path, output_rows)
    result = {
        "schema": "zeta-next-paired-control-blocked-opportunity-value-result-v1",
        "recorded_date_local": "2026-08-31",
        "unit": 124,
        "family": config["family"],
        "status": "COMPLETE_VALID_ECONOMIC_AGGREGATION",
        "input_receipt": input_receipt,
        "structural_integrity": {
            "passed": True,
            **integrity_counts,
            "blocks": {name: value[2]["blocks"] for name, value in windows.items()},
            "complete_matches": complete_matches | {"total": total_matches},
            "unmatched": {name: len(value[1]) for name, value in windows.items()},
            "total_match_fraction": match_fraction,
            "entry_price_exact_matches": total_matches,
            "entry_feature_exact_matches": total_matches,
            "unique_candidate_block_keys": total_blocks,
            "components": components,
            "symbols": symbols,
            "periods": periods,
        },
        "selection": finite_json_value(selection),
        "selection_favorable_gates": selection_favorable_gates | {"passed": selection_favorable},
        "selection_strong_adverse_gates": selection_strong_adverse_gates | {"passed": selection_strong_adverse},
        "confirmation_opened": confirmation_opened,
        "confirmation": finite_json_value(confirmation),
        "confirmation_favorable_gates": confirmation_gates | {"passed": confirmation_favorable}
        if confirmation_gates is not None
        else None,
        "matched_rows_artifact": {
            "path": config["outputs"]["matched_rows"],
            "rows": len(output_rows),
        },
        "causal_limit": config["economic_contract"]["causal_limit"],
        "verdict": verdict,
        "retained_seed": retained_seed,
        "optimization_candidate": None,
        "mt5_shortlist": None,
        "live_authority": False,
        "economic_aggregations": 1,
        "economic_metric_reruns": 0,
        "marker": "FRONTIER_UNIT_124_PAIRED_CONTROL_BLOCKED_OPPORTUNITY_VALUE_AGGREGATED_PENDING_CLOSURE",
    }
    result_path = REPO_ROOT / config["outputs"]["result"]
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(finite_json_value(result), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
