#!/usr/bin/env python3
"""Fixed Unit 125 aggregation for frequency-lane core-growth quarantine."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


REFERENCE_CAPITAL_USD = 100.0
ADDITION_STEP_USD = 150.0
H4_CLOSE_PATTERN = re.compile(
    r"(?P<time>20\d{2}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}).*"
    r"H4_OVERLAY close .*actual_net=(?P<actual>-?\d+\.\d+).*"
    r"stressed_net=(?P<stressed>-?\d+\.\d+)"
)

EXPECTED_INPUTS = {
    "authority/combined-result.json": (
        13144,
        "ECD977098A4B06E4C8252EF63DD0C169DB98C95CF538C8D3EA5E283499597D63",
    ),
    "authority/paired-control-result.json": (
        9880,
        "AD35D41CD6010AEA8901B34BFAEBCAA08DB67A883886E73E8DE14D9D62EF66C2",
    ),
    "authority/standalone-h4-result.json": (
        19589,
        "EE34D231896BA7CD3F1041FEA03A54CDD9C69E9CDE12095946930B113A479BB1",
    ),
    "combined/agent.log": (
        4237718,
        "A06577903D4D11EB8E7B4E5237881A927AEC5B807FBC4BA141AF90DA4DF5DB52",
    ),
    "combined/events-a.csv": (
        1051949,
        "44D8B321E205B6F93BCB6224CE746A10831DD5A7C02DBDDDB31C0683EA32EC33",
    ),
    "combined/events-b.csv": (
        1674789,
        "13B37B2E649A9B25AD9BF78B3E6287C1517272DA5A5043DF61865F963250578D",
    ),
    "combined/research-candidates.csv": (
        8591083,
        "A4AE3AA85674899D216BEBCA28DA7E3B1628E9676FAC9E51C2AAE6155DA3602D",
    ),
    "combined/research-lifecycles.csv": (
        2770449,
        "164202E9629EC1380560CD2DDC41B394ADA8564827A3F68F02F8491B14BF3A33",
    ),
    "control/events-a.csv": (
        956741,
        "0C4325BDD94A33031EF61EE62A40E9D284F34F8FA11B9D758AF4BEE025EC98EB",
    ),
    "control/events-b.csv": (
        1620721,
        "079A47AA12742054E225510C5506CD65DA9443E7A8797D858546DE730624EEFC",
    ),
    "control/research-candidates.csv": (
        8290085,
        "B3231924CD1357072C4198D6A530B5DA932C96EA6A050E35600E2279CAD1007A",
    ),
    "control/research-lifecycles.csv": (
        2685969,
        "7C187B8CE5068A67355FB9FE1F0D7E41E1E65BD88FBCEBBD3B63360E163B0F8B",
    ),
}

EPOCHS = (
    ("E1", "2022.08.01 00:00:00", "2023.06.01 00:00:00"),
    ("E2", "2023.06.01 00:00:00", "2024.06.01 00:00:00"),
    ("E3", "2024.06.01 00:00:00", "2025.06.01 00:00:00"),
    ("E4", "2025.06.01 00:00:00", "2026.06.01 00:00:00"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def verify_inputs(raw_root: Path) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for relative, (expected_bytes, expected_sha256) in EXPECTED_INPUTS.items():
        path = raw_root / relative
        actual_bytes = path.stat().st_size
        actual_sha256 = sha256_file(path)
        if actual_bytes != expected_bytes or actual_sha256 != expected_sha256:
            raise RuntimeError(
                f"immutable input mismatch: {relative} "
                f"bytes={actual_bytes}/{expected_bytes} "
                f"sha256={actual_sha256}/{expected_sha256}"
            )
        receipts.append(
            {
                "path": relative,
                "bytes": actual_bytes,
                "sha256": actual_sha256,
            }
        )
    return receipts


def read_csv_map(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = row["record_id"]
            if key in rows:
                raise RuntimeError(f"duplicate record_id in {path}: {key}")
            rows[key] = row
    return rows


def read_event_rows(paths: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen_rows: set[tuple[tuple[str, str], ...]] = set()
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                identity = tuple(sorted(row.items()))
                if identity in seen_rows:
                    raise RuntimeError(f"exact duplicate event row in {path}")
                seen_rows.add(identity)
                rows.append(row)
    rows.sort(
        key=lambda row: (
            int(row["state_sequence"]),
            row["server_time"],
            row["event"],
            row["component_id"],
            row["detail"],
        )
    )
    return rows


def read_h4_closes(path: Path) -> list[dict[str, Any]]:
    closes: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-16", errors="replace") as handle:
        for line in handle:
            match = H4_CLOSE_PATTERN.search(line)
            if not match:
                continue
            closes.append(
                {
                    "time": match.group("time"),
                    "actual_net_usd": float(match.group("actual")),
                    "stressed_net_usd": float(match.group("stressed")),
                }
            )
    if not closes:
        # Some MT5 agent logs are UTF-8/ANSI despite the usual UTF-16 container.
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                match = H4_CLOSE_PATTERN.search(line)
                if not match:
                    continue
                closes.append(
                    {
                        "time": match.group("time"),
                        "actual_net_usd": float(match.group("actual")),
                        "stressed_net_usd": float(match.group("stressed")),
                    }
                )
    closes.sort(key=lambda row: row["time"])
    return closes


def day_multiplier(stressed_balance: float) -> int:
    growth = max(0.0, stressed_balance - REFERENCE_CAPITAL_USD)
    return max(1, 1 + math.floor(growth / ADDITION_STEP_USD + 1.0e-9))


def first_size_day(rows: list[dict[str, str]], date: str) -> dict[str, str]:
    matches = [
        row
        for row in rows
        if row["event"] == "SIZE_DAY" and row["detail"] == date
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one SIZE_DAY for {date}, found {len(matches)}")
    return matches[0]


def sum_field(rows: list[dict[str, Any]], field: str) -> float:
    return math.fsum(float(row[field]) for row in rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    raw_root = args.raw_root.resolve()
    receipts = verify_inputs(raw_root)

    control = read_csv_map(raw_root / "control/research-candidates.csv")
    combined = read_csv_map(raw_root / "combined/research-candidates.csv")
    common_ids = sorted(set(control) & set(combined))
    control_only = sorted(set(control) - set(combined))
    combined_only = sorted(set(combined) - set(control))

    immutable_fields = (
        "server_time",
        "component_id",
        "stage",
        "signal_known",
        "signal_passed",
        "feature",
        "direction",
    )
    immutable_mismatches = 0
    common_result_mismatches = 0
    volume_differences: list[dict[str, Any]] = []
    for record_id in common_ids:
        left = control[record_id]
        right = combined[record_id]
        immutable_mismatches += any(
            left[field] != right[field] for field in immutable_fields
        )
        common_result_mismatches += left["result"] != right["result"]
        left_volume = float(left["volume"])
        right_volume = float(right["volume"])
        if not math.isclose(left_volume, right_volume, abs_tol=1.0e-12):
            volume_differences.append(
                {
                    "record_id": record_id,
                    "server_time": left["server_time"],
                    "component_id": left["component_id"],
                    "stage": left["stage"],
                    "result": left["result"],
                    "control_volume": left_volume,
                    "combined_volume": right_volume,
                    "control_balance": float(left["account_balance"]),
                    "combined_balance": float(right["account_balance"]),
                    "control_risk_capital": float(left["risk_capital_usd"]),
                    "combined_risk_capital": float(right["risk_capital_usd"]),
                }
            )
    volume_differences.sort(key=lambda row: (row["server_time"], row["record_id"]))
    if not volume_differences:
        raise RuntimeError("no common-record volume divergence found")

    first_divergence = volume_differences[0]
    first_divergence_time = first_divergence["server_time"]
    first_divergence_date = first_divergence_time[:10]

    h4_closes = read_h4_closes(raw_root / "combined/agent.log")
    h4_before_first_divergence = [
        row for row in h4_closes if row["time"] < first_divergence_time
    ]
    first_h4_close_time = h4_closes[0]["time"]
    volume_differences_before_first_h4_close = sum(
        row["server_time"] < first_h4_close_time for row in volume_differences
    )

    control_events = read_event_rows(
        [raw_root / "control/events-a.csv", raw_root / "control/events-b.csv"]
    )
    combined_events = read_event_rows(
        [raw_root / "combined/events-a.csv", raw_root / "combined/events-b.csv"]
    )
    control_size_day = first_size_day(control_events, first_divergence_date)
    combined_size_day = first_size_day(combined_events, first_divergence_date)

    h4_stressed_before = sum_field(h4_before_first_divergence, "stressed_net_usd")
    combined_stressed_balance = float(combined_size_day["value_a"])
    control_stressed_balance = float(control_size_day["value_a"])
    quarantined_stressed_balance = combined_stressed_balance - h4_stressed_before

    control_multiplier = int(round(float(control_size_day["value_b"])))
    combined_multiplier = int(round(float(combined_size_day["value_b"])))
    quarantined_multiplier = day_multiplier(quarantined_stressed_balance)

    epoch_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for close in h4_closes:
        for epoch, start, end in EPOCHS:
            if start <= close["time"] < end:
                epoch_rows[epoch].append(close)
                break
    h4_epochs = []
    for epoch, _, _ in EPOCHS:
        rows = epoch_rows[epoch]
        h4_epochs.append(
            {
                "epoch": epoch,
                "closes": len(rows),
                "actual_net_usd": sum_field(rows, "actual_net_usd") if rows else 0.0,
                "stressed_net_usd": sum_field(rows, "stressed_net_usd") if rows else 0.0,
                "positive_stressed_closes": sum(
                    row["stressed_net_usd"] > 0.0 for row in rows
                ),
                "negative_stressed_closes": sum(
                    row["stressed_net_usd"] < 0.0 for row in rows
                ),
            }
        )

    with (raw_root / "authority/combined-result.json").open(
        "r", encoding="utf-8"
    ) as handle:
        combined_result = json.load(handle)
    h4_result = combined_result["selection"]["low_frequency_lane"]
    comparison = combined_result["economic_comparison"]

    positive_active_epochs = sum(
        row["closes"] > 0 and row["stressed_net_usd"] > 0.0 for row in h4_epochs
    )
    h4_actual_total = sum_field(h4_closes, "actual_net_usd")
    h4_stressed_total = sum_field(h4_closes, "stressed_net_usd")

    gates = {
        "immutable_inputs_passed": len(receipts) == len(EXPECTED_INPUTS),
        "candidate_identity_passed": immutable_mismatches == 0,
        "common_result_identity_passed": common_result_mismatches == 0,
        "no_volume_divergence_before_first_h4_close": (
            volume_differences_before_first_h4_close == 0
        ),
        "shared_growth_first_divergence_crosses_quantum": (
            combined_multiplier != control_multiplier
        ),
        "quarantine_recovers_control_multiplier_at_first_divergence": (
            quarantined_multiplier == control_multiplier
        ),
        "h4_closes_at_least_40": len(h4_closes) >= 40,
        "h4_actual_and_stressed_positive": (
            h4_actual_total > 0.0 and h4_stressed_total > 0.0
        ),
        "h4_positive_in_at_least_two_active_epochs": positive_active_epochs >= 2,
        "h4_margin_and_fault_path_clean": (
            h4_result["margin_skips"] == 0 and h4_result["faults"] == 0
        ),
        "core_dilution_material_and_opposite_h4_sign": (
            comparison["core_stressed_delta_vs_qualified_control_usd"] <= -100.0
            and h4_stressed_total > 0.0
        ),
    }
    all_gates_passed = all(gates.values())
    verdict = (
        "PASS_CORE_GROWTH_QUANTUM_CONTAMINATION_RETAIN_ONE_QUARANTINED_RECOMBINATION_MT5_SEED"
        if all_gates_passed
        else "NO_MATERIAL_CORE_GROWTH_QUANTUM_CONTAMINATION_NO_RECOMBINATION_SEED"
    )

    result = {
        "schema": "zeta-next-frequency-lane-core-growth-quarantine-result-v1",
        "status": "UNIT_125_ONE_FIXED_AGGREGATION_COMPLETE",
        "unit": "frequency-lane-core-growth-quarantine-125",
        "family": "frequency-lane-core-growth-quarantine-v1",
        "integrity": {
            "passed": gates["immutable_inputs_passed"],
            "inputs": receipts,
            "control_candidate_rows": len(control),
            "combined_candidate_rows": len(combined),
            "common_record_ids": len(common_ids),
            "control_only_record_ids": len(control_only),
            "combined_only_record_ids": len(combined_only),
            "immutable_field_mismatches": immutable_mismatches,
            "common_result_mismatches": common_result_mismatches,
        },
        "fixed_mechanism": {
            "reference_capital_usd": REFERENCE_CAPITAL_USD,
            "core_addition_step_usd": ADDITION_STEP_USD,
            "h4_parameters_changed": False,
            "core_parameters_changed": False,
            "counterfactual": (
                "Track H4 actual/stressed closes in a low-frequency lane ledger; "
                "exclude them from core project_realized_net and stressed_balance "
                "used by core stage capital and daily lot multiplier; keep real "
                "account equity, margin and safety shared."
            ),
        },
        "matched_path": {
            "common_volume_differences": len(volume_differences),
            "volume_differences_before_first_h4_close": (
                volume_differences_before_first_h4_close
            ),
            "first_h4_close_time": first_h4_close_time,
            "first_common_volume_divergence": first_divergence,
        },
        "first_quantum_boundary": {
            "date": first_divergence_date,
            "h4_closes_before_boundary": len(h4_before_first_divergence),
            "cumulative_h4_actual_net_usd": sum_field(
                h4_before_first_divergence, "actual_net_usd"
            ),
            "cumulative_h4_stressed_net_usd": h4_stressed_before,
            "control_stressed_balance": control_stressed_balance,
            "shared_combined_stressed_balance": combined_stressed_balance,
            "quarantined_core_stressed_balance": quarantined_stressed_balance,
            "control_multiplier": control_multiplier,
            "shared_combined_multiplier": combined_multiplier,
            "quarantined_multiplier": quarantined_multiplier,
        },
        "h4_direct_value": {
            "closes": len(h4_closes),
            "actual_net_usd": h4_actual_total,
            "stressed_net_usd": h4_stressed_total,
            "positive_active_epochs": positive_active_epochs,
            "epochs": h4_epochs,
            "margin_skips": h4_result["margin_skips"],
            "faults": h4_result["faults"],
        },
        "prior_native_transmission": {
            "core_actual_delta_vs_control_usd": comparison[
                "core_actual_delta_vs_qualified_control_usd"
            ],
            "core_stressed_delta_vs_control_usd": comparison[
                "core_stressed_delta_vs_qualified_control_usd"
            ],
            "h4_direct_actual_net_usd": comparison["h4_direct_actual_net_usd"],
            "h4_direct_stressed_net_usd": comparison[
                "h4_direct_stressed_net_usd"
            ],
            "total_actual_delta_vs_control_usd": comparison[
                "actual_delta_vs_qualified_control_usd"
            ],
            "total_stressed_delta_vs_control_usd": comparison[
                "stressed_delta_vs_qualified_control_usd"
            ],
        },
        "gates": {**gates, "all_passed": all_gates_passed},
        "verdict": verdict,
        "decision_translation": {
            "retained_seed": (
                "EXACT_H4_CORE_GROWTH_QUARANTINED_RECOMBINATION"
                if all_gates_passed
                else None
            ),
            "optimization_candidate": None,
            "mt5_shortlist": None,
            "live_candidate": None,
            "automatic_promotion": False,
            "next_if_passed": (
                "Freeze one isolated Optimization campaign implementing only the "
                "declared lane-accounting separation, then require complete native "
                "selection and conditional forward against the paired control."
            ),
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
