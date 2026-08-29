#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import statistics
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


TIME_FORMAT = "%Y.%m.%d %H:%M:%S"
CONFIG_SHA256 = "77786A97A93839AD51DB272EA5B812F39A8CB693DC98B2F4571C6111A7B5429D"
SCRIPT_PATH = Path(__file__).resolve()
FAMILY_ROOT = SCRIPT_PATH.parents[1]
REPOSITORY_ROOT = SCRIPT_PATH.parents[4]
CONFIG_PATH = FAMILY_ROOT / "config" / "contract.json"


@dataclass(frozen=True)
class Close:
    server_time: datetime
    component_id: str
    position_identifier: str
    actual: float
    stressed: float


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def finite(raw: str, field: str, row_number: int) -> float:
    value = float(raw)
    if not math.isfinite(value):
        raise RuntimeError(f"non-finite {field} at CSV row {row_number}")
    return value


def load_contract() -> dict[str, Any]:
    if CONFIG_PATH.stat().st_size != 4167 or sha256(CONFIG_PATH) != CONFIG_SHA256:
        raise RuntimeError("frozen config pin mismatch")
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def manifest_hash(contract: dict[str, Any]) -> str:
    lines: list[str] = []
    for label in ("selection", "forward"):
        pin = contract["inputs"][label]
        lines.append(
            f"{Path(str(pin['path'])).name}|{int(pin['bytes'])}|{str(pin['sha256']).upper()}\n"
        )
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest().upper()


def load_population(
    label: str,
    contract: dict[str, Any],
    component_by_id: dict[str, dict[str, Any]],
) -> tuple[list[Close], dict[str, int]]:
    pin = contract["inputs"][label]
    path = REPOSITORY_ROOT / str(pin["path"])
    if path.stat().st_size != int(pin["bytes"]) or sha256(path) != str(pin["sha256"]):
        raise RuntimeError(f"{label} input pin mismatch")

    required = {
        "server_time",
        "event",
        "component_id",
        "position_identifier",
        "actual_net_usd",
        "stressed_net_usd",
    }
    counts: Counter[str] = Counter()
    births: set[str] = set()
    closes_seen: set[str] = set()
    closes: list[Close] = []
    previous_time: datetime | None = None
    negative_cost_units = 0

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise RuntimeError(f"{label} lifecycle header is incomplete")
        for row_number, row in enumerate(reader, start=2):
            event = str(row["event"])
            counts[event] += 1
            server_time = datetime.strptime(str(row["server_time"]), TIME_FORMAT)
            if previous_time is not None and server_time < previous_time:
                raise RuntimeError(f"{label} server times are not nondecreasing")
            previous_time = server_time
            position_identifier = str(row["position_identifier"])
            if event == "BIRTH":
                if not position_identifier or position_identifier in births:
                    raise RuntimeError(f"{label} duplicate or empty BIRTH identity")
                births.add(position_identifier)
                continue
            if event != "CLOSE":
                continue
            if not position_identifier or position_identifier in closes_seen:
                raise RuntimeError(f"{label} duplicate or empty CLOSE identity")
            component_id = str(row["component_id"])
            if component_id not in component_by_id:
                raise RuntimeError(f"{label} unmapped CLOSE component")
            actual = finite(str(row["actual_net_usd"]), "actual_net_usd", row_number)
            stressed = finite(
                str(row["stressed_net_usd"]), "stressed_net_usd", row_number
            )
            if actual + 1.0e-9 < stressed:
                negative_cost_units += 1
            closes_seen.add(position_identifier)
            closes.append(
                Close(
                    server_time=server_time,
                    component_id=component_id,
                    position_identifier=position_identifier,
                    actual=actual,
                    stressed=stressed,
                )
            )

    expected_events = {str(k): int(v) for k, v in pin["events"].items()}
    if dict(counts) != expected_events or sum(counts.values()) != int(pin["rows"]):
        raise RuntimeError(f"{label} event population mismatch")
    if births != closes_seen:
        raise RuntimeError(f"{label} BIRTH/CLOSE identity sets differ")
    if negative_cost_units:
        raise RuntimeError(f"{label} contains negative observed cost units")

    component_counts = Counter(close.component_id for close in closes)
    expected_count_key = f"{label}_closes"
    for component_id, row in component_by_id.items():
        if component_counts[component_id] != int(row[expected_count_key]):
            raise RuntimeError(f"{label} component close count mismatch")
    if set(component_counts) != set(component_by_id):
        raise RuntimeError(f"{label} component set mismatch")

    actual_total = sum(close.actual for close in closes)
    stressed_total = sum(close.stressed for close in closes)
    if abs(actual_total - float(pin["actual_net_anchor_usd"])) > 1.0e-7:
        raise RuntimeError(f"{label} actual net anchor mismatch")
    if abs(stressed_total - float(pin["stressed_net_anchor_usd"])) > 1.0e-7:
        raise RuntimeError(f"{label} stressed net anchor mismatch")
    return closes, dict(counts)


def frozen_sort(
    closes: list[Close], component_order: dict[str, int]
) -> list[Close]:
    return sorted(
        closes,
        key=lambda row: (
            -row.stressed,
            row.server_time,
            row.position_identifier,
            component_order[row.component_id],
        ),
    )


def bucket_id(server_time: datetime, buckets: list[dict[str, Any]]) -> str:
    for bucket in buckets:
        start = datetime.strptime(str(bucket["start"]), TIME_FORMAT)
        end = datetime.strptime(str(bucket["end"]), TIME_FORMAT)
        if start <= server_time < end:
            return str(bucket["id"])
    raise RuntimeError("CLOSE is outside every frozen time bucket")


def population_summary(closes: list[Close]) -> dict[str, float | int]:
    positive = sum(1 for row in closes if row.stressed > 0.0)
    gross_positive = sum(max(row.stressed, 0.0) for row in closes)
    return {
        "closes": len(closes),
        "positive_stressed_closes": positive,
        "actual_net_usd": sum(row.actual for row in closes),
        "stressed_net_usd": sum(row.stressed for row in closes),
        "gross_positive_stressed_usd": gross_positive,
    }


def rank_order(
    nets: dict[str, float], component_ids: list[str], component_order: dict[str, int]
) -> list[str]:
    return sorted(component_ids, key=lambda key: (-nets[key], component_order[key]))


def pair_reversals(original: list[str], residual: list[str]) -> tuple[int, float]:
    original_rank = {name: rank for rank, name in enumerate(original)}
    residual_rank = {name: rank for rank, name in enumerate(residual)}
    reversals = 0
    for left, right in itertools.combinations(original, 2):
        original_sign = original_rank[left] - original_rank[right]
        residual_sign = residual_rank[left] - residual_rank[right]
        if original_sign * residual_sign < 0:
            reversals += 1
    pairs = math.comb(len(original), 2)
    tau = (pairs - 2 * reversals) / pairs
    return reversals, tau


def grouped_time_metrics(
    closes: list[Close],
    buckets: list[dict[str, Any]],
    removed_ids: set[str],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for bucket in buckets:
        name = str(bucket["id"])
        rows = [row for row in closes if bucket_id(row.server_time, buckets) == name]
        residual = [row for row in rows if row.position_identifier not in removed_ids]
        result.append(
            {
                "id": name,
                "original_closes": len(rows),
                "removed_closes": len(rows) - len(residual),
                "original_actual_net_usd": sum(row.actual for row in rows),
                "original_stressed_net_usd": sum(row.stressed for row in rows),
                "residual_actual_net_usd": sum(row.actual for row in residual),
                "residual_stressed_net_usd": sum(row.stressed for row in residual),
            }
        )
    return result


def selection_analysis(
    closes: list[Close], contract: dict[str, Any], component_order: dict[str, int]
) -> dict[str, Any]:
    rules = contract["selection_rules"]
    component_rows = {
        component_id: [row for row in closes if row.component_id == component_id]
        for component_id in component_order
    }
    component_metrics: list[dict[str, Any]] = []
    original_nets: dict[str, float] = {}
    residual_nets: dict[str, float] = {}
    top10_ids: set[str] = set()

    for component in contract["components"]:
        component_id = str(component["component_id"])
        rows = component_rows[component_id]
        ordered = frozen_sort(rows, component_order)
        positive_count = sum(1 for row in rows if row.stressed > 0.0)
        if positive_count < int(rules["minimum_positive_closes_per_component"]):
            raise RuntimeError("selection component positive-close density failed")
        original_actual = sum(row.actual for row in rows)
        original_stressed = sum(row.stressed for row in rows)
        gross_positive = sum(max(row.stressed, 0.0) for row in rows)
        if original_stressed <= 0.0 or gross_positive <= 0.0:
            raise RuntimeError("selection component positive source anchor failed")
        metric: dict[str, Any] = {
            "name": str(component["name"]),
            "component_id": component_id,
            "closes": len(rows),
            "positive_stressed_closes": positive_count,
            "original_actual_net_usd": original_actual,
            "original_stressed_net_usd": original_stressed,
            "gross_positive_stressed_usd": gross_positive,
            "top_k": {},
        }
        for k in rules["top_k_values"]:
            k_int = int(k)
            selected = ordered[:k_int]
            selected_stressed = sum(row.stressed for row in selected)
            selected_actual = sum(row.actual for row in selected)
            metric["top_k"][str(k_int)] = {
                "gross_positive_share": sum(max(row.stressed, 0.0) for row in selected)
                / gross_positive,
                "selected_actual_net_usd": selected_actual,
                "selected_stressed_net_usd": selected_stressed,
                "residual_actual_net_usd": original_actual - selected_actual,
                "residual_stressed_net_usd": original_stressed - selected_stressed,
            }
            if k_int == 10:
                top10_ids.update(row.position_identifier for row in selected)
                residual_nets[component_id] = original_stressed - selected_stressed
        original_nets[component_id] = original_stressed
        component_metrics.append(metric)

    component_ids = list(component_order)
    original_rank = rank_order(original_nets, component_ids, component_order)
    residual_rank = rank_order(residual_nets, component_ids, component_order)
    reversals, tau = pair_reversals(original_rank, residual_rank)
    shares = [row["top_k"]["10"]["gross_positive_share"] for row in component_metrics]
    broad = rules["broad_concentration"]
    broad_count = sum(
        value >= float(broad["top10_gross_positive_share_threshold"])
        for value in shares
    )
    broad_passed = (
        broad_count
        >= int(broad["minimum_components_top10_share_at_least_threshold"])
        and statistics.median(shares)
        >= float(broad["median_top10_gross_positive_share_threshold"])
    )
    fragility = rules["sign_and_rank_fragility"]
    nonpositive = sum(value <= 1.0e-9 for value in residual_nets.values())
    fragility_passed = (
        nonpositive
        >= int(fragility["minimum_components_nonpositive_after_top10"])
        and reversals >= int(fragility["minimum_pair_reversals"])
        and tau <= float(fragility["maximum_kendall_tau_a"])
    )
    robust = rules["strong_robustness"]
    strong_robustness = (
        all(value > 1.0e-9 for value in residual_nets.values())
        and reversals <= int(robust["maximum_pair_reversals"])
    )

    if broad_passed and fragility_passed:
        verdict = "PASS_SELECTION_COMPONENT_OUTCOME_CONCENTRATION_TAIL_DEPENDENT"
    elif strong_robustness:
        verdict = "NO_MATERIAL_SELECTION_COMPONENT_OUTCOME_CONCENTRATION"
    else:
        verdict = "AMBIGUOUS_SELECTION_COMPONENT_OUTCOME_CONCENTRATION"

    residual_rows = [row for row in closes if row.position_identifier not in top10_ids]
    return {
        "population": population_summary(closes),
        "components": component_metrics,
        "leave_component_top10_portfolio": {
            "removed_closes": len(top10_ids),
            "residual_closes": len(residual_rows),
            "residual_actual_net_usd": sum(row.actual for row in residual_rows),
            "residual_stressed_net_usd": sum(row.stressed for row in residual_rows),
        },
        "leave_component_top10_epochs": grouped_time_metrics(
            closes, contract["selection_epochs"], top10_ids
        ),
        "rank_robustness": {
            "original_order": original_rank,
            "residual_order": residual_rank,
            "pair_reversals": reversals,
            "pair_count": math.comb(len(component_ids), 2),
            "kendall_tau_a": tau,
        },
        "gate_application": {
            "components_top10_share_at_least_0_30": broad_count,
            "median_top10_gross_positive_share": statistics.median(shares),
            "broad_concentration_passed": broad_passed,
            "components_nonpositive_after_top10": nonpositive,
            "sign_and_rank_fragility_passed": fragility_passed,
            "strong_robustness_falsifier_passed": strong_robustness,
        },
        "verdict": verdict,
    }


def forward_analysis(
    closes: list[Close], contract: dict[str, Any], component_order: dict[str, int]
) -> dict[str, Any]:
    rules = contract["forward_diagnostic_rules"]
    ordered = frozen_sort(closes, component_order)
    positive_count = sum(1 for row in closes if row.stressed > 0.0)
    if positive_count < int(rules["minimum_positive_closes"]):
        raise RuntimeError("forward positive-close density failed")
    gross_positive = sum(max(row.stressed, 0.0) for row in closes)
    top_metrics: dict[str, Any] = {}
    warning = False
    for k in rules["top_k_values"]:
        k_int = int(k)
        selected = ordered[:k_int]
        removed = {row.position_identifier for row in selected}
        residual = [row for row in closes if row.position_identifier not in removed]
        residual_stressed = sum(row.stressed for row in residual)
        if residual_stressed <= 1.0e-9:
            warning = True
        top_metrics[str(k_int)] = {
            "gross_positive_share": sum(max(row.stressed, 0.0) for row in selected)
            / gross_positive,
            "selected_actual_net_usd": sum(row.actual for row in selected),
            "selected_stressed_net_usd": sum(row.stressed for row in selected),
            "residual_actual_net_usd": sum(row.actual for row in residual),
            "residual_stressed_net_usd": residual_stressed,
            "months": grouped_time_metrics(
                closes, contract["forward_months"], removed
            ),
        }
    return {
        "population": population_summary(closes),
        "top_k": top_metrics,
        "small_sample_tail_warning": warning,
        "primary_verdict_gate": False,
    }


def main() -> None:
    started = time.perf_counter()
    contract = load_contract()
    components = list(contract["components"])
    component_by_id = {str(row["component_id"]): row for row in components}
    if len(component_by_id) != 5:
        raise RuntimeError("frozen component identity count mismatch")
    component_order = {
        str(row["component_id"]): index for index, row in enumerate(components)
    }
    if manifest_hash(contract) != str(contract["inputs"]["ordered_manifest_sha256"]):
        raise RuntimeError("ordered input manifest mismatch")

    selection, selection_events = load_population(
        "selection", contract, component_by_id
    )
    forward, forward_events = load_population("forward", contract, component_by_id)
    selection_result = selection_analysis(selection, contract, component_order)
    forward_result = forward_analysis(forward, contract, component_order)

    raw = {
        "schema": "zeta-next-paired-month-lifecycle-concentration-robustness-formal-result-v1",
        "created_at_local": "2026-08-30",
        "status": "VALID_COMPLETE",
        "family": str(contract["family"]),
        "unit": str(contract["unit"]),
        "pins": {
            "config_bytes": CONFIG_PATH.stat().st_size,
            "config_sha256": sha256(CONFIG_PATH),
            "input_manifest_sha256": manifest_hash(contract),
        },
        "integrity": {
            "passed": True,
            "selection_events": selection_events,
            "forward_events": forward_events,
            "selection_birth_close_identity_equal": True,
            "forward_birth_close_identity_equal": True,
            "negative_cost_units": 0,
        },
        "selection": selection_result,
        "forward_diagnostic": forward_result,
        "verdict": selection_result["verdict"],
        "execution": {
            "formal_processes": 1,
            "successful_aggregations": 1,
            "economic_metric_reruns": 0,
            "mql_or_settings_changes": 0,
            "compile_or_tester_paths": 0,
            "orders": 0,
            "elapsed_seconds": time.perf_counter() - started,
        },
        "authority_boundary": {
            "realized_winners_are_not_predictively_removable": True,
            "candidate_changed_or_retuned": False,
            "new_optimization_or_mt5_candidate": False,
            "live_authority": False,
            "lab_live_master_runtime_used": False,
        },
    }
    output_path = REPOSITORY_ROOT / str(contract["output"]["path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(raw, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(json.dumps({"output": str(output_path), "verdict": raw["verdict"]}))


if __name__ == "__main__":
    main()
