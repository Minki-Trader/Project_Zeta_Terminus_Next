from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[3]
AGENT_ROOT = ROOT / "lab" / "runtime" / "tester-portable" / "Tester"
OUTPUT_PATH = Path(__file__).with_name("proxy.json")
SESSION_MARKER = "zt-next-frontier-expiration-counterfactual-v1 initialized"
LABEL_MARKER = "ZETA_FRONTIER_EXPIRATION_LABEL|"
SUMMARY_MARKER = "ZETA_FRONTIER_EXPIRATION_SUMMARY|"
OUTCOME_PREFIXES = ("original", "reprice50", "reprice75", "market")
HORIZONS = {
    "original": (15, 30, 60, 120, 240),
    "reprice50": (15, 30, 60),
    "reprice75": (15, 30, 60),
    "market": (0,),
}


def fields_after(line: str, marker: str) -> dict[str, str] | None:
    offset = line.find(marker)
    if offset < 0:
        return None
    fields: dict[str, str] = {}
    for token in line[offset + len(marker) :].strip().split("|"):
        if "=" in token:
            key, value = token.split("=", 1)
            fields[key] = value
    return fields


def latest_session() -> tuple[Path, list[str]]:
    paths = sorted(
        AGENT_ROOT.glob("Agent-*/logs/*.log"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in paths:
        lines = path.read_text(encoding="utf-16-le").splitlines()
        starts = [index for index, line in enumerate(lines) if SESSION_MARKER in line]
        if not starts:
            continue
        start = starts[-1]
        for end in range(start, len(lines)):
            if SUMMARY_MARKER in lines[end]:
                return path, lines[start : end + 1]
    raise RuntimeError("No completed expiration-counterfactual session was found")


def as_int(fields: dict[str, str], key: str) -> int:
    return int(float(fields[key]))


def as_float(fields: dict[str, str], key: str) -> float:
    return float(fields[key])


def parse_outcome(line: str, prefix: str) -> dict[str, Any] | None:
    source = fields_after(line, f"{prefix}_")
    if source is None:
        return None
    raw = {
        (key[len(prefix) + 1 :] if key.startswith(f"{prefix}_") else key): value
        for key, value in source.items()
    }
    return {
        "touched": bool(as_int(raw, "touched")),
        "touch_seconds": as_int(raw, "touch_seconds"),
        "stopped": bool(as_int(raw, "stopped")),
        "stop_seconds": as_int(raw, "stop_seconds"),
        "complete": bool(as_int(raw, "complete")),
        "fill": as_float(raw, "fill"),
        "stop": as_float(raw, "stop"),
        "net_ratio": as_float(raw, "net_ratio"),
        "mfe_ratio": as_float(raw, "mfe_ratio"),
        "mae_ratio": as_float(raw, "mae_ratio"),
    }


def read_labels(
    lines: list[str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    labels: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    summary: dict[str, int] = {}
    for line in lines:
        raw = fields_after(line, LABEL_MARKER)
        if raw is not None:
            current = {
                "expiration": as_int(raw, "expiration"),
                "direction": as_int(raw, "direction"),
                "feature": as_float(raw, "feature"),
                "feature_abs": abs(as_float(raw, "feature")),
                "limit": as_float(raw, "limit"),
                "stop": as_float(raw, "stop"),
                "span": as_float(raw, "span"),
                "post_ticks": as_int(raw, "post_ticks"),
                "pre_closest": as_float(raw, "pre_closest"),
                "pre_endpoint": as_float(raw, "pre_endpoint"),
                "pre_efficiency": as_float(raw, "pre_efficiency"),
                "pre_persistence": as_float(raw, "pre_persistence"),
                "expiration_executable": as_float(raw, "expiration_executable"),
                "reprice_50": as_float(raw, "reprice_50"),
                "reprice_75": as_float(raw, "reprice_75"),
                "outcomes": {},
            }
            current["expiration_gap_ratio"] = abs(
                current["expiration_executable"] - current["limit"]
            ) / current["span"]
            labels.append(current)
            continue

        if current is not None:
            for prefix in OUTCOME_PREFIXES:
                outcome = parse_outcome(line, prefix)
                if outcome is not None:
                    current["outcomes"][prefix] = outcome
                    break

        raw = fields_after(line, SUMMARY_MARKER)
        if raw is not None:
            summary = {key: as_int(raw, key) for key in raw}

    complete = [
        label
        for label in labels
        if set(label["outcomes"]) == set(OUTCOME_PREFIXES)
    ]
    if len(complete) != len(labels):
        raise RuntimeError("At least one expiration label lacks an outcome block")
    return sorted(labels, key=lambda item: item["expiration"]), summary


def rounded(value: float | None) -> float | None:
    return round(value, 6) if value is not None and math.isfinite(value) else None


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * probability)]


def distribution(values: list[float]) -> dict[str, float]:
    return {
        "minimum": rounded(min(values)),
        "q25": rounded(quantile(values, 0.25)),
        "median": rounded(quantile(values, 0.50)),
        "q75": rounded(quantile(values, 0.75)),
        "maximum": rounded(max(values)),
        "mean": rounded(statistics.fmean(values)),
    }


def action_name(prefix: str, horizon: int) -> str:
    return "market_at_expiration" if prefix == "market" else f"{prefix}_{horizon}m"


def action_result(
    label: dict[str, Any], prefix: str, horizon: int
) -> tuple[bool, float, dict[str, Any]]:
    outcome = label["outcomes"][prefix]
    filled = outcome["touched"] and (
        prefix == "market" or outcome["touch_seconds"] <= horizon * 60
    )
    return filled, outcome["net_ratio"] if filled else 0.0, outcome


def closed_drawdown(values: list[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    drawdown = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        drawdown = max(drawdown, peak - cumulative)
    return drawdown


def action_metrics(
    labels: list[dict[str, Any]],
    prefix: str,
    horizon: int,
    split_expiration: int,
) -> dict[str, Any]:
    def lens(subset: list[dict[str, Any]]) -> dict[str, Any]:
        results = [action_result(label, prefix, horizon) for label in subset]
        values = [result[1] for result in results]
        filled = [result for result in results if result[0]]
        filled_values = [result[1] for result in filled]
        stopped = [result for result in filled if result[2]["stopped"]]
        return {
            "eligible": len(subset),
            "filled": len(filled),
            "fill_rate": rounded(len(filled) / len(subset)) if subset else None,
            "stopped": len(stopped),
            "stop_rate_filled": rounded(len(stopped) / len(filled)) if filled else None,
            "positive": sum(value > 0.0 for value in filled_values),
            "win_rate_filled": rounded(
                sum(value > 0.0 for value in filled_values) / len(filled_values)
            )
            if filled_values
            else None,
            "total_net_ratio": rounded(sum(values)),
            "mean_net_per_eligible": rounded(statistics.fmean(values))
            if values
            else None,
            "mean_net_per_fill": rounded(statistics.fmean(filled_values))
            if filled_values
            else None,
            "closed_drawdown_ratio": rounded(closed_drawdown(values)),
            "mean_mfe_per_fill": rounded(
                statistics.fmean(result[2]["mfe_ratio"] for result in filled)
            )
            if filled
            else None,
            "mean_mae_per_fill": rounded(
                statistics.fmean(result[2]["mae_ratio"] for result in filled)
            )
            if filled
            else None,
        }

    return {
        "full": lens(labels),
        "early": lens(
            [label for label in labels if label["expiration"] < split_expiration]
        ),
        "late": lens(
            [label for label in labels if label["expiration"] >= split_expiration]
        ),
    }


Selector = tuple[str, str, dict[str, Any], Callable[[dict[str, Any]], bool]]


def selectors(labels: list[dict[str, Any]]) -> list[Selector]:
    result: list[Selector] = [("all", "all", {}, lambda label: True)]

    def add(
        family: str,
        name: str,
        params: dict[str, Any],
        predicate: Callable[[dict[str, Any]], bool],
    ) -> None:
        result.append((family, name, params, predicate))

    add("direction", "long", {"direction": 1}, lambda label: label["direction"] == 1)
    add("direction", "short", {"direction": -1}, lambda label: label["direction"] == -1)

    fields = (
        "feature_abs",
        "pre_closest",
        "pre_endpoint",
        "pre_efficiency",
        "pre_persistence",
        "expiration_gap_ratio",
    )
    thresholds: dict[str, dict[str, float]] = {}
    for field in fields:
        values = [label[field] for label in labels]
        thresholds[field] = {
            "q25": quantile(values, 0.25),
            "q50": quantile(values, 0.50),
            "q75": quantile(values, 0.75),
        }
        for quantile_name, threshold in thresholds[field].items():
            add(
                "field_high",
                f"{field}_high_{quantile_name}",
                {"field": field, "minimum": threshold},
                lambda label, field=field, threshold=threshold: label[field] >= threshold,
            )
            add(
                "field_low",
                f"{field}_low_{quantile_name}",
                {"field": field, "maximum": threshold},
                lambda label, field=field, threshold=threshold: label[field] <= threshold,
            )

    q = thresholds
    add(
        "path_shape",
        "near_expiry_hover",
        {"endpoint": "q25-", "persistence": "q50-"},
        lambda label: label["pre_endpoint"] <= q["pre_endpoint"]["q25"]
        and label["pre_persistence"] <= q["pre_persistence"]["q50"],
    )
    add(
        "path_shape",
        "persistent_escape",
        {"endpoint": "q50+", "persistence": "q75+"},
        lambda label: label["pre_endpoint"] >= q["pre_endpoint"]["q50"]
        and label["pre_persistence"] >= q["pre_persistence"]["q75"],
    )
    add(
        "path_shape",
        "noisy_return",
        {"efficiency": "q25-", "endpoint": "q50-"},
        lambda label: label["pre_efficiency"] <= q["pre_efficiency"]["q25"]
        and label["pre_endpoint"] <= q["pre_endpoint"]["q50"],
    )
    add(
        "path_shape",
        "clean_escape",
        {"efficiency": "q75+", "endpoint": "q50+"},
        lambda label: label["pre_efficiency"] >= q["pre_efficiency"]["q75"]
        and label["pre_endpoint"] >= q["pre_endpoint"]["q50"],
    )
    add(
        "path_shape",
        "near_miss_then_escape",
        {"closest": "q25-", "endpoint": "q75+"},
        lambda label: label["pre_closest"] <= q["pre_closest"]["q25"]
        and label["pre_endpoint"] >= q["pre_endpoint"]["q75"],
    )
    add(
        "path_shape",
        "weak_signal_near_expiry",
        {"feature_abs": "q25-", "endpoint": "q25-"},
        lambda label: label["feature_abs"] <= q["feature_abs"]["q25"]
        and label["pre_endpoint"] <= q["pre_endpoint"]["q25"],
    )
    return result


def stable_score(metrics: dict[str, Any], positive: bool) -> float | None:
    full = metrics["full"]
    early = metrics["early"]
    late = metrics["late"]
    if (
        full["eligible"] < 6
        or full["filled"] < 4
        or early["eligible"] < 2
        or late["eligible"] < 2
    ):
        return None
    early_mean = early["mean_net_per_eligible"]
    late_mean = late["mean_net_per_eligible"]
    if early_mean is None or late_mean is None:
        return None
    floor = min(early_mean, late_mean) if positive else min(-early_mean, -late_mean)
    if floor <= 0.0:
        return None
    return rounded(floor * math.sqrt(full["eligible"]))


def compact(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": row["action"],
        "selector_family": row["selector_family"],
        "selector": row["selector"],
        "params": row["params"],
        "stable_value_score": row["stable_value_score"],
        "stable_die_score": row["stable_die_score"],
        "metrics": row["metrics"],
    }


def main() -> None:
    source_log, lines = latest_session()
    labels, measurement_summary = read_labels(lines)
    split_expiration = labels[len(labels) // 2]["expiration"]
    selector_list = selectors(labels)

    action_rows: list[dict[str, Any]] = []
    unconditional: dict[str, Any] = {}
    for prefix, horizons in HORIZONS.items():
        for horizon in horizons:
            name = action_name(prefix, horizon)
            unconditional[name] = action_metrics(
                labels, prefix, horizon, split_expiration
            )
            for family, selector_name, params, predicate in selector_list:
                selected = [label for label in labels if predicate(label)]
                metrics = action_metrics(selected, prefix, horizon, split_expiration)
                action_rows.append(
                    {
                        "action": name,
                        "selector_family": family,
                        "selector": selector_name,
                        "params": params,
                        "metrics": metrics,
                        "stable_value_score": stable_score(metrics, True),
                        "stable_die_score": stable_score(metrics, False),
                    }
                )

    value_rows = [row for row in action_rows if row["stable_value_score"] is not None]
    die_rows = [row for row in action_rows if row["stable_die_score"] is not None]
    value_rows.sort(key=lambda row: row["stable_value_score"], reverse=True)
    die_rows.sort(key=lambda row: row["stable_die_score"], reverse=True)

    fields = (
        "feature_abs",
        "pre_closest",
        "pre_endpoint",
        "pre_efficiency",
        "pre_persistence",
        "expiration_gap_ratio",
    )
    document = {
        "unit": "expiration-counterfactual-005",
        "question": "Which expired Passive limits were early rather than economically wrong?",
        "source_log": str(source_log.relative_to(ROOT)).replace("\\", "/"),
        "causality": "Selectors use only direction, signal strength, and tick geometry known at expiration. Shadow outcomes begin strictly after expiration.",
        "measurement_summary": measurement_summary,
        "counts": {
            "expirations": len(labels),
            "actions": len(unconditional),
            "selectors": len(selector_list),
            "evaluations": len(action_rows),
            "stable_value_cells": len(value_rows),
            "stable_die_cells": len(die_rows),
        },
        "feature_distribution": {
            field: distribution([label[field] for label in labels]) for field in fields
        },
        "unconditional_actions": unconditional,
        "stable_value_leaders": [compact(row) for row in value_rows[:60]],
        "stable_die_leaders": [compact(row) for row in die_rows[:60]],
        "labels": labels,
        "split_expiration": split_expiration,
        "limits": [
            "Shadow exits use a fixed four-hour hold or the shifted one-span stop, not the native state-dependent Passive exit.",
            "Normalized ratios omit commissions, slippage, portfolio slot conflicts, and risk-admission interactions.",
            "Only 29 expirations exist, so cells are hypothesis generators for a few causal EA runs.",
        ],
    }
    OUTPUT_PATH.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
