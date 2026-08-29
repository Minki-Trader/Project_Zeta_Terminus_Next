#!/usr/bin/env python3
"""Run the frozen Unit 100 account-contribution label analysis once."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


FAMILY = "router-account-contribution-label-alignment-v1"
REPO_ROOT = Path(__file__).resolve().parents[4]
INPUT_ROOT = REPO_ROOT / "lab" / "artifacts" / "raw" / FAMILY / "input"
OUTPUT_ROOT = REPO_ROOT / "lab" / "artifacts" / "raw" / FAMILY / "output"
ROUTER_PATH = INPUT_ROOT / "router-decisions.csv"
ANCHOR_PATH = INPUT_ROOT / "anchor-lifecycles.csv"
RESULT_PATH = OUTPUT_ROOT / "result.json"
MATCHED_PATH = OUTPUT_ROOT / "matched-lifecycles.csv"

EXPECTED_ROUTER = {
    "bytes": 274_974,
    "sha256": "D9CB0A7A89573896274348ED4AB188C38F15A4C974D14B99C94BE628A5BE2FCE",
    "rows": 1_620,
}
EXPECTED_ANCHOR = {
    "bytes": 2_685_969,
    "sha256": "7C187B8CE5068A67355FB9FE1F0D7E41E1E65BD88FBCEBBD3B63360E163B0F8B",
    "closed_lifecycles": 1_428,
    "actual_net_usd": 5_786.63,
    "stressed_net_usd": 5_477.524,
}

COMPONENTS = [
    "ZT-M30-US30-RANGE-COMP-61f61deaba",
    "ZT-M30-US30-RANGE-COMP-64efb16616",
    "ZT-H1-US100-CROSS-IN-14b72317b7",
    "ZT-M30-US30-INTRADAY-R-2eb111fc46",
    "ZT-H1-US30-RETURN-I-c870a788ec",
]
COMPONENT_INDEX = {component: index for index, component in enumerate(COMPONENTS)}

EPOCHS = [
    ("E1", datetime(2022, 8, 1), datetime(2023, 6, 1)),
    ("E2", datetime(2023, 6, 1), datetime(2024, 6, 1)),
    ("E3", datetime(2024, 6, 1), datetime(2025, 6, 1)),
    ("E4", datetime(2025, 6, 1), datetime(2026, 6, 1)),
]

RIDGE_ALPHA = 10.0
MINIMUM_TOTAL = 80
MINIMUM_PER_COMPONENT = 8
LOWER_QUANTILE = 0.02
UPPER_QUANTILE = 0.98
MATCH_FRACTION_MINIMUM = 0.95
MODEL_READY_MATCHED_MINIMUM = 500
POOLED_SPEARMAN_MINIMUM = 0.10
POSITIVE_COMPONENTS_MINIMUM = 4
QUARTILE_GAP_MINIMUM_R = 0.10
BOTTOM_STRESSED_MAXIMUM_USD = 0.0
BOTTOM_NONPOSITIVE_EPOCHS_MINIMUM = 3


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_receipt(path: Path) -> dict[str, Any]:
    return {"path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"), "bytes": path.stat().st_size, "sha256": sha256(path)}


def parse_server_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y.%m.%d %H:%M:%S")


def parse_server_minute(value: str) -> datetime:
    for pattern in ("%Y.%m.%d %H:%M", "%Y.%m.%d %H:%M:%S"):
        try:
            return datetime.strptime(value, pattern).replace(second=0, microsecond=0)
        except ValueError:
            pass
    raise ValueError(f"unsupported server time: {value!r}")


def key_for(component: str, moment: datetime, direction: int) -> tuple[str, datetime, int]:
    return component, moment.replace(second=0, microsecond=0), direction


def quarter_start(moment: datetime) -> datetime:
    month = ((moment.month - 1) // 3) * 3 + 1
    return datetime(moment.year, month, 1)


def quarter_key(moment: datetime) -> int:
    return moment.year * 4 + (moment.month - 1) // 3


def build_features(component: str, direction: int, raw_feature: float, moment: datetime) -> list[float]:
    clipped = max(-20.0, min(20.0, raw_feature))
    angle = 2.0 * math.pi * moment.weekday() / 5.0
    indicators = [1.0 if component == candidate else 0.0 for candidate in COMPONENTS]
    return [clipped, abs(clipped), float(direction), math.sin(angle), math.cos(angle), *indicators]


def quantile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("quantile requires values")
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def solve_system(matrix: list[list[float]], target: list[float]) -> list[float]:
    size = len(target)
    system = [matrix[row][:] + [target[row]] for row in range(size)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(system[row][column]))
        if abs(system[pivot][column]) <= 1.0e-12:
            raise ArithmeticError("ridge system is singular")
        if pivot != column:
            system[column], system[pivot] = system[pivot], system[column]
        divisor = system[column][column]
        for item in range(column, size + 1):
            system[column][item] /= divisor
        for row in range(size):
            if row == column:
                continue
            factor = system[row][column]
            if abs(factor) <= 1.0e-18:
                continue
            for item in range(column, size + 1):
                system[row][item] -= factor * system[column][item]
    return [system[row][size] for row in range(size)]


def fit_ridge(training: list[dict[str, Any]]) -> dict[str, Any] | None:
    component_counts = Counter(row["component"] for row in training)
    if len(training) < MINIMUM_TOTAL or any(component_counts[component] < MINIMUM_PER_COMPONENT for component in COMPONENTS):
        return None

    feature_count = 10
    means = [sum(row["features"][index] for row in training) / len(training) for index in range(feature_count)]
    scales = []
    for index in range(feature_count):
        variance = sum((row["features"][index] - means[index]) ** 2 for row in training) / len(training)
        scale = math.sqrt(variance)
        scales.append(1.0 if scale <= 1.0e-12 else scale)

    labels = sorted(row["stressed_r"] for row in training)
    lower = quantile(labels, LOWER_QUANTILE)
    upper = quantile(labels, UPPER_QUANTILE)
    clipped_labels = [max(lower, min(upper, row["stressed_r"])) for row in training]
    intercept = sum(clipped_labels) / len(clipped_labels)

    system = [[0.0 for _ in range(feature_count)] for _ in range(feature_count)]
    target = [0.0 for _ in range(feature_count)]
    for row, label in zip(training, clipped_labels):
        standardized = [(row["features"][index] - means[index]) / scales[index] for index in range(feature_count)]
        centered_label = label - intercept
        for left in range(feature_count):
            target[left] += standardized[left] * centered_label
            for right in range(feature_count):
                system[left][right] += standardized[left] * standardized[right]
    for index in range(feature_count):
        system[index][index] += RIDGE_ALPHA
    coefficients = solve_system(system, target)

    return {
        "means": means,
        "scales": scales,
        "coefficients": coefficients,
        "intercept": intercept,
        "clip_lower": lower,
        "clip_upper": upper,
        "component_counts": dict(component_counts),
    }


def predict(model: dict[str, Any], features: list[float]) -> float:
    return model["intercept"] + sum(
        coefficient * ((features[index] - model["means"][index]) / model["scales"][index])
        for index, coefficient in enumerate(model["coefficients"])
    )


def average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        average = ((start + 1) + end) / 2.0
        for location in range(start, end):
            ranks[order[location]] = average
        start = end
    return ranks


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    left_sum = sum((x - left_mean) ** 2 for x in left)
    right_sum = sum((y - right_mean) ** 2 for y in right)
    denominator = math.sqrt(left_sum * right_sum)
    if denominator <= 0.0:
        return None
    return numerator / denominator


def spearman(left: list[float], right: list[float]) -> float | None:
    return pearson(average_ranks(left), average_ranks(right))


def safe_mean(rows: list[dict[str, Any]], field: str) -> float | None:
    return sum(row[field] for row in rows) / len(rows) if rows else None


def epoch_name(moment: datetime) -> str | None:
    for name, start, end in EPOCHS:
        if start <= moment < end:
            return name
    return None


def variant_metrics(rows: list[dict[str, Any]], rank_field: str) -> dict[str, Any]:
    bottom = [row for row in rows if row[rank_field] < 0.25]
    top = [row for row in rows if row[rank_field] >= 0.75]
    component_metrics: dict[str, Any] = {}
    for component in COMPONENTS:
        subset = [row for row in rows if row["component"] == component]
        component_metrics[component] = {
            "rows": len(subset),
            "spearman_rank_vs_stressed_r": spearman(
                [row[rank_field] for row in subset], [row["stressed_r"] for row in subset]
            ),
            "actual_net_usd": sum(row["actual_net_usd"] for row in subset),
            "stressed_net_usd": sum(row["stressed_net_usd"] for row in subset),
        }

    epoch_bottom: dict[str, Any] = {}
    for name, _, _ in EPOCHS:
        subset = [row for row in bottom if row["epoch"] == name]
        total = sum(row["stressed_net_usd"] for row in subset)
        epoch_bottom[name] = {"rows": len(subset), "stressed_net_usd": total, "nonpositive_with_rows": bool(subset) and total <= 0.0}

    top_mean = safe_mean(top, "stressed_r")
    bottom_mean = safe_mean(bottom, "stressed_r")
    gap = None if top_mean is None or bottom_mean is None else top_mean - bottom_mean
    return {
        "rows": len(rows),
        "component_coverage": sum(1 for component in COMPONENTS if any(row["component"] == component for row in rows)),
        "pooled_spearman_rank_vs_stressed_r": spearman(
            [row[rank_field] for row in rows], [row["stressed_r"] for row in rows]
        ),
        "components": component_metrics,
        "components_with_positive_spearman": sum(
            1 for value in component_metrics.values() if value["spearman_rank_vs_stressed_r"] is not None and value["spearman_rank_vs_stressed_r"] > 0.0
        ),
        "actual_net_usd": sum(row["actual_net_usd"] for row in rows),
        "stressed_net_usd": sum(row["stressed_net_usd"] for row in rows),
        "bottom_quartile": {
            "definition": "rank < 0.25",
            "rows": len(bottom),
            "mean_stressed_r": bottom_mean,
            "actual_net_usd": sum(row["actual_net_usd"] for row in bottom),
            "stressed_net_usd": sum(row["stressed_net_usd"] for row in bottom),
            "epochs": epoch_bottom,
            "nonpositive_stressed_epochs_with_rows": sum(value["nonpositive_with_rows"] for value in epoch_bottom.values()),
        },
        "top_quartile": {
            "definition": "rank >= 0.75",
            "rows": len(top),
            "mean_stressed_r": top_mean,
            "actual_net_usd": sum(row["actual_net_usd"] for row in top),
            "stressed_net_usd": sum(row["stressed_net_usd"] for row in top),
        },
        "top_minus_bottom_mean_stressed_r": gap,
    }


def read_inputs() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    router_receipt = file_receipt(ROUTER_PATH)
    anchor_receipt = file_receipt(ANCHOR_PATH)

    with ROUTER_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        raw_router = list(csv.DictReader(handle, delimiter="\t"))
    router_rows: list[dict[str, Any]] = []
    for source in raw_router:
        moment = parse_server_minute(source["decision_bar"])
        component = source["component_id"]
        direction = int(source["direction"])
        raw_feature = float(source["feature"])
        router_rows.append(
            {
                "component": component,
                "decision_time": moment,
                "direction": direction,
                "raw_feature": raw_feature,
                "features": build_features(component, direction, raw_feature, moment),
                "original_rank": float(source["rank"]),
                "original_model_ready": int(source["model_ready"]) == 1,
                "economic_window": int(source["economic_window"]),
                "source_quarter_key": int(source["quarter_key"]),
                "key": key_for(component, moment, direction),
            }
        )

    with ANCHOR_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        raw_anchor = list(csv.DictReader(handle))
    anchor_rows: list[dict[str, Any]] = []
    for source in raw_anchor:
        if source["event"] != "CLOSE" or source["partial_observation"] != "0":
            continue
        component = source["component_id"]
        entry_time = parse_server_time(source["entry_time_server"])
        close_time = parse_server_time(source["server_time"])
        direction = int(source["direction"])
        risk = float(source["planned_risk_usd"])
        stressed = float(source["stressed_net_usd"])
        anchor_rows.append(
            {
                "record_id": source["record_id"],
                "component": component,
                "entry_time": entry_time,
                "close_time": close_time,
                "direction": direction,
                "entry_feature": float(source["entry_feature"]),
                "planned_risk_usd": risk,
                "actual_net_usd": float(source["actual_net_usd"]),
                "stressed_net_usd": stressed,
                "stressed_r": stressed / risk if risk > 0.0 else math.nan,
                "key": key_for(component, entry_time, direction),
            }
        )

    receipts = {
        "router": {**router_receipt, "rows": len(router_rows)},
        "anchor": {**anchor_receipt, "closed_lifecycles": len(anchor_rows)},
        "analysis_script": file_receipt(Path(__file__).resolve()),
    }
    return router_rows, anchor_rows, receipts


def main() -> None:
    started_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    router_rows, anchor_rows, receipts = read_inputs()

    router_counts = Counter(row["key"] for row in router_rows)
    anchor_counts = Counter(row["key"] for row in anchor_rows)
    router_duplicate_keys = [key for key, count in router_counts.items() if count != 1]
    anchor_duplicate_keys = [key for key, count in anchor_counts.items() if count != 1]
    router_index = {row["key"]: row for row in router_rows if router_counts[row["key"]] == 1}

    matched: list[dict[str, Any]] = []
    unmatched_anchor: list[dict[str, Any]] = []
    feature_mismatches: list[dict[str, Any]] = []
    for anchor in anchor_rows:
        router = router_index.get(anchor["key"])
        if router is None:
            unmatched_anchor.append(anchor)
            continue
        tolerance = 1.0e-9 * max(1.0, abs(anchor["entry_feature"]))
        difference = abs(anchor["entry_feature"] - router["raw_feature"])
        if difference > tolerance:
            feature_mismatches.append({"record_id": anchor["record_id"], "difference": difference, "tolerance": tolerance})
            continue
        matched.append(
            {
                **anchor,
                "features": router["features"],
                "original_rank": router["original_rank"],
                "original_model_ready": router["original_model_ready"],
                "account_rank": None,
                "account_model_ready": False,
                "account_score": None,
                "epoch": epoch_name(anchor["entry_time"]),
            }
        )

    matched_index = {row["key"]: row for row in matched}
    quarter_receipts: list[dict[str, Any]] = []
    fit_attempts = 0
    fit_successes = 0
    for start in sorted({quarter_start(row["decision_time"]) for row in router_rows}):
        fit_attempts += 1
        training = [row for row in matched if row["close_time"] < start]
        model = fit_ridge(training)
        decisions = [row for row in router_rows if quarter_start(row["decision_time"]) == start]
        receipt: dict[str, Any] = {
            "quarter_key": quarter_key(start),
            "quarter_start": start.isoformat(sep=" "),
            "training_rows": len(training),
            "training_component_counts": dict(Counter(row["component"] for row in training)),
            "decision_rows": len(decisions),
            "model_ready": model is not None,
        }
        if model is not None:
            fit_successes += 1
            training_predictions = [(row["component"], predict(model, row["features"])) for row in training]
            by_component: dict[str, list[float]] = {
                component: [score for training_component, score in training_predictions if training_component == component]
                for component in COMPONENTS
            }
            scored_matches = 0
            for decision in decisions:
                score = predict(model, decision["features"])
                reference = by_component[decision["component"]]
                rank = sum(training_score <= score for training_score in reference) / len(reference)
                anchor = matched_index.get(decision["key"])
                if anchor is not None:
                    anchor["account_rank"] = rank
                    anchor["account_model_ready"] = True
                    anchor["account_score"] = score
                    scored_matches += 1
            receipt.update(
                {
                    "clip_lower_stressed_r": model["clip_lower"],
                    "clip_upper_stressed_r": model["clip_upper"],
                    "scored_matched_rows": scored_matches,
                }
            )
        quarter_receipts.append(receipt)

    expected_router_ok = (
        receipts["router"]["bytes"] == EXPECTED_ROUTER["bytes"]
        and receipts["router"]["sha256"] == EXPECTED_ROUTER["sha256"]
        and receipts["router"]["rows"] == EXPECTED_ROUTER["rows"]
    )
    anchor_actual = sum(row["actual_net_usd"] for row in anchor_rows)
    anchor_stressed = sum(row["stressed_net_usd"] for row in anchor_rows)
    expected_anchor_ok = (
        receipts["anchor"]["bytes"] == EXPECTED_ANCHOR["bytes"]
        and receipts["anchor"]["sha256"] == EXPECTED_ANCHOR["sha256"]
        and receipts["anchor"]["closed_lifecycles"] == EXPECTED_ANCHOR["closed_lifecycles"]
        and abs(anchor_actual - EXPECTED_ANCHOR["actual_net_usd"]) <= 1.0e-6
        and abs(anchor_stressed - EXPECTED_ANCHOR["stressed_net_usd"]) <= 1.0e-6
    )
    known_components = all(row["component"] in COMPONENT_INDEX for row in router_rows + anchor_rows)
    positive_risks = all(row["planned_risk_usd"] > 0.0 and math.isfinite(row["stressed_r"]) for row in anchor_rows)
    quarter_keys_match = all(row["source_quarter_key"] == quarter_key(row["decision_time"]) for row in router_rows)
    economic_window_rows = sum(row["economic_window"] == 1 for row in router_rows)
    valid_for_economic_judgment = all(
        [
            expected_router_ok,
            expected_anchor_ok,
            not router_duplicate_keys,
            not anchor_duplicate_keys,
            not feature_mismatches,
            known_components,
            positive_risks,
            quarter_keys_match,
            economic_window_rows == len(router_rows),
        ]
    )

    original_rows = [row for row in matched if row["original_model_ready"]]
    account_rows = [row for row in matched if row["account_model_ready"]]
    original_metrics = variant_metrics(original_rows, "original_rank")
    account_metrics = variant_metrics(account_rows, "account_rank")
    match_fraction = len(matched) / len(anchor_rows) if anchor_rows else 0.0

    pooled = account_metrics["pooled_spearman_rank_vs_stressed_r"]
    gap = account_metrics["top_minus_bottom_mean_stressed_r"]
    gates = {
        "unique_match_fraction_at_least_0.95": match_fraction >= MATCH_FRACTION_MINIMUM,
        "model_ready_matched_rows_at_least_500": len(account_rows) >= MODEL_READY_MATCHED_MINIMUM,
        "all_five_components_covered": account_metrics["component_coverage"] == len(COMPONENTS),
        "pooled_spearman_at_least_0.10": pooled is not None and pooled >= POOLED_SPEARMAN_MINIMUM,
        "at_least_four_positive_component_spearman": account_metrics["components_with_positive_spearman"] >= POSITIVE_COMPONENTS_MINIMUM,
        "top_minus_bottom_mean_stressed_r_at_least_0.10": gap is not None and gap >= QUARTILE_GAP_MINIMUM_R,
        "bottom_quartile_full_stressed_net_nonpositive": account_metrics["bottom_quartile"]["stressed_net_usd"] <= BOTTOM_STRESSED_MAXIMUM_USD,
        "bottom_quartile_nonpositive_in_at_least_three_epochs": account_metrics["bottom_quartile"]["nonpositive_stressed_epochs_with_rows"] >= BOTTOM_NONPOSITIVE_EPOCHS_MINIMUM,
    }
    all_gates_pass = valid_for_economic_judgment and all(gates.values())

    result = {
        "schema": "zeta-next-router-account-contribution-label-alignment-result-v1",
        "family": FAMILY,
        "unit": 100,
        "primary_program": "diagnostics_causal_meta",
        "formal_analysis_process": 1,
        "started_at_utc": started_at,
        "completed_at_utc": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "inputs": receipts,
        "integrity": {
            "valid_for_economic_judgment": valid_for_economic_judgment,
            "expected_router_snapshot": expected_router_ok,
            "expected_anchor_snapshot_and_totals": expected_anchor_ok,
            "router_rows": len(router_rows),
            "router_economic_window_rows": economic_window_rows,
            "anchor_closed_lifecycles": len(anchor_rows),
            "anchor_actual_net_usd": anchor_actual,
            "anchor_stressed_net_usd": anchor_stressed,
            "router_duplicate_key_count": len(router_duplicate_keys),
            "anchor_duplicate_key_count": len(anchor_duplicate_keys),
            "feature_mismatch_count": len(feature_mismatches),
            "known_components": known_components,
            "positive_planned_risks": positive_risks,
            "router_quarter_keys_match_reconstruction": quarter_keys_match,
        },
        "matching": {
            "matched_anchor_closes": len(matched),
            "unmatched_anchor_closes": len(unmatched_anchor),
            "match_fraction": match_fraction,
            "matched_component_counts": dict(Counter(row["component"] for row in matched)),
        },
        "model_process": {
            "fit_attempts": fit_attempts,
            "fit_successes": fit_successes,
            "ridge_alpha": RIDGE_ALPHA,
            "minimum_total": MINIMUM_TOTAL,
            "minimum_per_component": MINIMUM_PER_COMPONENT,
            "label_clip_quantiles": [LOWER_QUANTILE, UPPER_QUANTILE],
            "quarters": quarter_receipts,
        },
        "variants": {
            "ORIGINAL_VIRTUAL_NET_RANK": original_metrics,
            "PRIOR_QUARTER_ACCOUNT_STRESSED_R_RIDGE": account_metrics,
        },
        "prospective_account_r_gates": gates,
        "all_prospective_account_r_gates_pass": all_gates_pass,
        "retained_seed": "CAUSAL_PRIOR_QUARTER_ACCOUNT_STRESSED_R_RIDGE_ROUTER" if all_gates_pass else None,
        "classification": (
            "VALID_ACCOUNT_CONTRIBUTION_LABEL_SEED_RETAINED"
            if all_gates_pass
            else "VALID_ACCOUNT_CONTRIBUTION_LABEL_NONCONFIRMATION_NO_SEED"
            if valid_for_economic_judgment
            else "ENGINEERING_OR_INPUT_CORRECTION_REQUIRED_NO_ECONOMIC_VERDICT"
        ),
    }

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    with RESULT_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")

    matched_fields = [
        "record_id",
        "component",
        "entry_time",
        "close_time",
        "direction",
        "entry_feature",
        "planned_risk_usd",
        "actual_net_usd",
        "stressed_net_usd",
        "stressed_r",
        "epoch",
        "original_model_ready",
        "original_rank",
        "account_model_ready",
        "account_score",
        "account_rank",
    ]
    with MATCHED_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=matched_fields)
        writer.writeheader()
        for row in matched:
            writer.writerow(
                {
                    field: row[field].isoformat(sep=" ") if isinstance(row[field], datetime) else row[field]
                    for field in matched_fields
                }
            )

    print(json.dumps({"classification": result["classification"], "result": str(RESULT_PATH), "matched": str(MATCHED_PATH)}))


if __name__ == "__main__":
    main()
