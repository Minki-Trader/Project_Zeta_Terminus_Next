from __future__ import annotations

import csv
import hashlib
import json
import math
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
CAMPAIGN_ROOT = SCRIPT_PATH.parents[1]
REPOSITORY_ROOT = SCRIPT_PATH.parents[4]
CONFIG_PATH = CAMPAIGN_ROOT / "config" / "proxy-contract.json"
TIME_FORMAT = "%Y.%m.%d %H:%M:%S"
EPSILON = 1.0e-9


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def receipt(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(REPOSITORY_ROOT)).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def rounded(value: Any) -> Any:
    if isinstance(value, float):
        if math.isinf(value):
            return "POSITIVE_INFINITY" if value > 0 else "NEGATIVE_INFINITY"
        return round(value, 12)
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [rounded(item) for item in value]
    return value


def verify_inputs(config: dict[str, Any]) -> tuple[Path, dict[str, Path]]:
    input_root = REPOSITORY_ROOT / str(config["input"]["root"])
    paths: dict[str, Path] = {}
    manifest_rows: list[str] = []
    total = 0
    for declared in config["input"]["files"]:
        name = str(declared["name"])
        path = input_root / name
        if name in paths or not path.is_file():
            raise RuntimeError(f"missing or duplicate input: {name}")
        file_hash = sha256(path)
        if path.stat().st_size != int(declared["bytes"]):
            raise RuntimeError(f"input byte mismatch: {name}")
        if file_hash != str(declared["sha256"]):
            raise RuntimeError(f"input hash mismatch: {name}")
        paths[name] = path
        total += path.stat().st_size
        manifest_rows.append(f"{name}|{path.stat().st_size}|{file_hash}")
    if len(paths) != int(config["input"]["files_count"]):
        raise RuntimeError("input file-count mismatch")
    if total != int(config["input"]["bytes_total"]):
        raise RuntimeError("input byte-total mismatch")
    manifest = hashlib.sha256("\n".join(manifest_rows).encode("utf-8")).hexdigest().upper()
    if manifest != str(config["input"]["bundle_manifest_sha256"]):
        raise RuntimeError("input bundle-manifest mismatch")
    return input_root, paths


def exact_number(actual: float, expected: float, label: str, tolerance: float = 1.0e-6) -> None:
    if abs(actual - expected) > tolerance:
        raise RuntimeError(f"{label} mismatch: {actual} != {expected}")


def load_and_verify_source_results(
    paths: dict[str, Path], config: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    live = json.loads(paths["live-control-result.json"].read_text(encoding="utf-8"))
    candidate = json.loads(paths["paired-candidate-result.json"].read_text(encoding="utf-8"))
    if live.get("campaign") != "portfolio-risk-cap-envelope-v1":
        raise RuntimeError("unexpected active Live control source campaign")
    if candidate.get("campaign") != "dd20-paired-month-stability-mt5-v1":
        raise RuntimeError("unexpected paired candidate source campaign")

    parent = config["active_live_control"]
    if live.get("parent") != {
        "position_risk_fraction": float(parent["position_risk_fraction"]),
        "aggregate_risk_fraction": float(parent["aggregate_risk_fraction"]),
    }:
        raise RuntimeError("active Live control identity mismatch")
    selection_rows = [
        row
        for row in live["selection_matrix"]
        if int(row["pass"]) == int(parent["selection_pass"])
    ]
    forward_rows = [
        row
        for row in live["forward_matrix"]
        if int(row["pass"]) == int(parent["selection_pass"])
    ]
    if len(selection_rows) != 1 or len(forward_rows) != 1:
        raise RuntimeError("active Live control pass is missing or duplicated")
    control_selection = selection_rows[0]
    control_forward = forward_rows[0]
    for key, expected_key in (
        ("actual_net_usd", "actual_net_usd"),
        ("stressed_net_usd", "stressed_2x_net_usd"),
        ("equity_drawdown_pct", "native_relative_equity_drawdown_pct"),
        ("closed_lifecycles", "closed_lifecycles"),
    ):
        exact_number(
            float(control_selection[key]),
            float(parent["selection"][expected_key]),
            f"control selection {key}",
        )
        exact_number(
            float(control_forward[key]),
            float(parent["forward"][expected_key]),
            f"control forward {key}",
        )

    declared_candidate = config["candidate"]
    if [float(value) for value in candidate["candidate"]["component_exposure_multipliers"]] != [
        float(value) for value in declared_candidate["weights"]
    ]:
        raise RuntimeError("paired candidate weight mismatch")
    exact_number(
        float(candidate["candidate"]["position_risk_fraction"]),
        float(declared_candidate["position_risk_fraction"]),
        "paired candidate position risk",
    )
    exact_number(
        float(candidate["candidate"]["aggregate_risk_fraction"]),
        float(declared_candidate["aggregate_risk_fraction"]),
        "paired candidate aggregate risk",
    )
    for segment in ("selection", "forward"):
        source = candidate[segment]
        expected = declared_candidate[segment]
        exact_number(float(source["actual_net_usd"]), float(expected["actual_net_usd"]), f"candidate {segment} actual")
        exact_number(
            float(source["stressed_2x_cost_net_usd"]),
            float(expected["stressed_2x_net_usd"]),
            f"candidate {segment} stressed",
        )
        exact_number(
            float(source["mt5_equity_drawdown_relative_pct"] if segment == "selection" else source["mt5_equity_drawdown_maximal_and_relative_pct"]),
            float(expected["native_relative_equity_drawdown_pct"]),
            f"candidate {segment} native DD",
        )
    return live, candidate, control_selection, control_forward


def load_closes(path: Path, expected: dict[str, Any], components: list[str]) -> list[dict[str, Any]]:
    component_set = set(components)
    rows = 0
    births: set[str] = set()
    closes: list[dict[str, Any]] = []
    close_ids: set[str] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for source in csv.DictReader(handle):
            rows += 1
            event = str(source["event"])
            position = str(source["position_identifier"])
            component = str(source["component_id"])
            if component not in component_set:
                raise RuntimeError(f"unknown component in lifecycle source: {component}")
            if event == "BIRTH":
                if position in births:
                    raise RuntimeError("duplicate lifecycle birth")
                births.add(position)
            elif event == "CLOSE":
                if position in close_ids:
                    raise RuntimeError("duplicate lifecycle close")
                if str(source.get("partial_observation", "0")) != "0":
                    raise RuntimeError("partial close observation in fixed input")
                actual = float(source["actual_net_usd"])
                stressed = float(source["stressed_net_usd"])
                cost = actual - stressed
                if not all(math.isfinite(value) for value in (actual, stressed, cost)):
                    raise RuntimeError("nonfinite lifecycle economics")
                if cost < -1.0e-6:
                    raise RuntimeError("negative observed cost unit")
                close_ids.add(position)
                closes.append(
                    {
                        "time": datetime.strptime(str(source["server_time"]), TIME_FORMAT),
                        "record_id": str(source["record_id"]),
                        "position": position,
                        "component": component,
                        "actual": actual,
                        "stressed": stressed,
                        "cost": max(0.0, cost),
                    }
                )
    if rows != int(expected["rows"]):
        raise RuntimeError("lifecycle row-count mismatch")
    if len(births) != int(expected["births"]) or len(closes) != int(expected["closes"]):
        raise RuntimeError("lifecycle birth/close count mismatch")
    if births != close_ids:
        raise RuntimeError("lifecycle birth/close identity mismatch")
    closes.sort(key=lambda row: (row["time"], row["record_id"], row["position"]))
    exact_number(sum(row["actual"] for row in closes), float(expected["actual_net_usd"]), "lifecycle actual anchor")
    exact_number(sum(row["stressed"] for row in closes), float(expected["stressed_2x_net_usd"]), "lifecycle stressed anchor")
    return closes


def period_rows(rows: list[dict[str, Any]], period: dict[str, Any]) -> list[dict[str, Any]]:
    start = datetime.strptime(str(period["start"]), TIME_FORMAT)
    end = datetime.strptime(str(period["end"]), TIME_FORMAT)
    selected = [row for row in rows if start <= row["time"] < end]
    if not selected:
        raise RuntimeError(f"empty fixed period: {period['id']}")
    return selected


def economics(rows: list[dict[str, Any]], multiplier: int) -> dict[str, Any]:
    increments = [row["actual"] - (multiplier - 1) * row["cost"] for row in rows]
    gross_profit = sum(value for value in increments if value > 0.0)
    gross_loss = -sum(value for value in increments if value < 0.0)
    profit_factor = gross_profit / gross_loss if gross_loss > EPSILON else math.inf
    balance = 100.0
    peak = 100.0
    maximum_dd_usd = 0.0
    maximum_relative_dd = 0.0
    minimum_balance = 100.0
    for increment in increments:
        balance += increment
        peak = max(peak, balance)
        maximum_dd_usd = max(maximum_dd_usd, peak - balance)
        if peak > 0.0:
            maximum_relative_dd = max(maximum_relative_dd, (peak - balance) / peak)
        minimum_balance = min(minimum_balance, balance)
    return {
        "multiplier": multiplier,
        "closes": len(rows),
        "net_usd": sum(increments),
        "gross_profit_usd": gross_profit,
        "gross_loss_usd": gross_loss,
        "profit_factor": profit_factor,
        "closed_balance_drawdown_usd": maximum_dd_usd,
        "closed_balance_drawdown_pct": maximum_relative_dd * 100.0,
        "minimum_closed_balance_usd": minimum_balance,
        "ending_closed_balance_usd": balance,
    }


def aggregate_books(rows: list[dict[str, Any]], multipliers: list[int]) -> list[dict[str, Any]]:
    return [economics(rows, multiplier) for multiplier in multipliers]


def book_by_multiplier(books: list[dict[str, Any]], multiplier: int) -> dict[str, Any]:
    matches = [book for book in books if int(book["multiplier"]) == multiplier]
    if len(matches) != 1:
        raise RuntimeError(f"missing or duplicate cost book: {multiplier}")
    return matches[0]


def aggregate_periods(
    rows: list[dict[str, Any]], periods: list[dict[str, Any]], multiplier: int
) -> list[dict[str, Any]]:
    records = []
    for period in periods:
        record = economics(period_rows(rows, period), multiplier)
        record["id"] = str(period["id"])
        record["start"] = str(period["start"])
        record["end"] = str(period["end"])
        records.append(record)
    return records


def aggregate_components(
    rows: list[dict[str, Any]], components: list[str], multiplier: int
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["component"]].append(row)
    return [
        {"component": component, **economics(grouped[component], multiplier)}
        if grouped[component]
        else {
            "component": component,
            "multiplier": multiplier,
            "closes": 0,
            "net_usd": 0.0,
            "gross_profit_usd": 0.0,
            "gross_loss_usd": 0.0,
            "profit_factor": 0.0,
            "closed_balance_drawdown_usd": 0.0,
            "closed_balance_drawdown_pct": 0.0,
            "minimum_closed_balance_usd": 100.0,
            "ending_closed_balance_usd": 100.0,
        }
        for component in components
    ]


def aggregate_control(row: dict[str, Any], multipliers: list[int]) -> list[dict[str, Any]]:
    actual = float(row["actual_net_usd"])
    stressed = float(row["stressed_net_usd"])
    cost = actual - stressed
    if cost < -1.0e-6:
        raise RuntimeError("active Live control has negative cost unit")
    return [
        {
            "multiplier": multiplier,
            "net_usd": actual - (multiplier - 1) * max(0.0, cost),
            "closed_lifecycles": int(row["closed_lifecycles"]),
            "native_relative_equity_drawdown_pct_at_1x": float(row["equity_drawdown_pct"]),
            "path_level_3x_4x_drawdown_available": False,
        }
        for multiplier in multipliers
    ]


def control_book(books: list[dict[str, Any]], multiplier: int) -> dict[str, Any]:
    matches = [book for book in books if int(book["multiplier"]) == multiplier]
    if len(matches) != 1:
        raise RuntimeError("control cost book missing or duplicated")
    return matches[0]


def main() -> None:
    started = time.perf_counter()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    _, paths = verify_inputs(config)
    _, candidate_source, control_selection_row, control_forward_row = load_and_verify_source_results(paths, config)
    components = [str(value) for value in config["components"]]
    selection_rows = load_closes(paths["candidate-selection-lifecycles.csv"], config["candidate"]["selection"], components)
    forward_rows = load_closes(paths["candidate-forward-lifecycles.csv"], config["candidate"]["forward"], components)
    multipliers = [int(value) for value in config["cost_books"]["multipliers"]]

    candidate_selection_books = aggregate_books(selection_rows, multipliers)
    candidate_forward_books = aggregate_books(forward_rows, multipliers)
    control_selection_books = aggregate_control(control_selection_row, multipliers)
    control_forward_books = aggregate_control(control_forward_row, multipliers)
    selection_epochs_4x = aggregate_periods(selection_rows, config["selection_epochs"], 4)
    forward_periods_4x = aggregate_periods(forward_rows, config["forward_periods"], 4)
    selection_components_4x = aggregate_components(selection_rows, components, 4)

    candidate_selection_1x = book_by_multiplier(candidate_selection_books, 1)
    candidate_selection_4x = book_by_multiplier(candidate_selection_books, 4)
    candidate_forward_1x = book_by_multiplier(candidate_forward_books, 1)
    candidate_forward_4x = book_by_multiplier(candidate_forward_books, 4)
    control_selection_4x = control_book(control_selection_books, 4)
    control_forward_4x = control_book(control_forward_books, 4)
    forward_period_map = {str(item["id"]): item for item in forward_periods_4x}
    july_loss = max(0.0, -float(forward_period_map["JULY"]["net_usd"]))
    july_loss_share = (
        july_loss / float(candidate_forward_4x["net_usd"])
        if float(candidate_forward_4x["net_usd"]) > 0.0
        else math.inf
    )
    gate_config = config["gates"]
    active_components = [
        item for item in selection_components_4x if int(item["closes"]) > 0
    ]
    gates = {
        "selection_4x_net_strictly_positive": candidate_selection_4x["net_usd"] > 0.0,
        "selection_4x_profit_factor": candidate_selection_4x["profit_factor"]
        >= float(gate_config["selection_4x_profit_factor_minimum"]),
        "selection_4x_to_1x_net_retention": candidate_selection_4x["net_usd"]
        / candidate_selection_1x["net_usd"]
        >= float(gate_config["selection_4x_to_1x_net_retention_minimum"]),
        "selection_all_four_epochs_4x_positive": all(item["net_usd"] > 0.0 for item in selection_epochs_4x),
        "selection_all_five_active_components_4x_positive": len(active_components) == 5
        and all(item["net_usd"] > 0.0 for item in active_components),
        "selection_candidate_4x_strictly_above_active_live_control_4x": candidate_selection_4x["net_usd"]
        > control_selection_4x["net_usd"],
        "forward_4x_net_strictly_positive": candidate_forward_4x["net_usd"] > 0.0,
        "forward_4x_profit_factor": candidate_forward_4x["profit_factor"]
        >= float(gate_config["forward_4x_profit_factor_minimum"]),
        "forward_4x_to_1x_net_retention": candidate_forward_4x["net_usd"]
        / candidate_forward_1x["net_usd"]
        >= float(gate_config["forward_4x_to_1x_net_retention_minimum"]),
        "forward_candidate_4x_strictly_above_active_live_control_4x": candidate_forward_4x["net_usd"]
        > control_forward_4x["net_usd"],
        "june_4x_net_strictly_positive": forward_period_map["JUNE"]["net_usd"] > 0.0,
        "july_4x_absolute_loss_within_bound": july_loss
        <= float(gate_config["july_4x_maximum_absolute_loss_usd"]) + EPSILON,
        "july_4x_loss_share_within_bound": july_loss_share
        <= float(gate_config["july_4x_maximum_loss_share_of_positive_full_forward"]) + EPSILON,
    }
    passed = all(gates.values())
    result = {
        "schema": "zeta-dd20-paired-month-live-control-cost-resilience-proxy-raw-result-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "VALID_COMPLETE",
        "campaign": config["campaign"],
        "input": {
            "files": [receipt(paths[item["name"]]) for item in config["input"]["files"]],
            "bundle_manifest_sha256": config["input"]["bundle_manifest_sha256"],
        },
        "execution": {
            "formal_process_invocations": 1,
            "candidate_paths": 1,
            "cost_books_per_path": len(multipliers),
            "metric_reruns": 0,
            "tester_paths": 0,
            "mql_or_settings_changes": 0,
            "elapsed_internal_seconds": time.perf_counter() - started,
        },
        "candidate_identity": {
            "weights": config["candidate"]["weights"],
            "position_risk_fraction": config["candidate"]["position_risk_fraction"],
            "aggregate_risk_fraction": config["candidate"]["aggregate_risk_fraction"],
            "source_release": candidate_source["candidate"]["release_id"],
            "development_candidate_changed": False,
        },
        "candidate_selection_cost_books": candidate_selection_books,
        "candidate_selection_epochs_4x": selection_epochs_4x,
        "candidate_selection_components_4x": selection_components_4x,
        "candidate_forward_cost_books": candidate_forward_books,
        "candidate_forward_periods_4x": forward_periods_4x,
        "active_live_control_selection_cost_books": control_selection_books,
        "active_live_control_forward_cost_books": control_forward_books,
        "comparison_4x": {
            "selection_candidate_minus_control_usd": candidate_selection_4x["net_usd"]
            - control_selection_4x["net_usd"],
            "selection_candidate_to_control_net_ratio": candidate_selection_4x["net_usd"]
            / control_selection_4x["net_usd"],
            "forward_candidate_minus_control_usd": candidate_forward_4x["net_usd"]
            - control_forward_4x["net_usd"],
            "selection_candidate_4x_to_1x_retention": candidate_selection_4x["net_usd"]
            / candidate_selection_1x["net_usd"],
            "forward_candidate_4x_to_1x_retention": candidate_forward_4x["net_usd"]
            / candidate_forward_1x["net_usd"],
            "july_candidate_4x_loss_usd": july_loss,
            "july_candidate_4x_loss_share_of_full_forward": july_loss_share,
        },
        "gates": gates,
        "verdict": (
            "PASS_FIXED_DEVELOPMENT_CANDIDATE_COST_RESILIENCE_VS_ACTIVE_LIVE_CONTROL"
            if passed
            else "VALID_FIXED_DEVELOPMENT_CANDIDATE_COST_RESILIENCE_NOT_CONFIRMED"
        ),
        "interpretation_limit": config["cost_books"]["scope_limit"],
        "native_drawdown_context": {
            "candidate_selection_pct": config["candidate"]["selection"]["native_relative_equity_drawdown_pct"],
            "candidate_forward_pct": config["candidate"]["forward"]["native_relative_equity_drawdown_pct"],
            "active_live_control_selection_pct": config["active_live_control"]["selection"]["native_relative_equity_drawdown_pct"],
            "active_live_control_forward_pct": config["active_live_control"]["forward"]["native_relative_equity_drawdown_pct"],
            "arithmetic_3x_4x_native_open_equity_dd_available": False,
        },
        "boundary": {
            "fixed_candidate_replaced_or_retuned": False,
            "new_candidate_or_mt5_shortlist": False,
            "live_lab_or_master_touched": False,
            "broker_account_positions_orders_or_deals_queried": False,
        },
    }
    output_path = REPOSITORY_ROOT / str(config["output"]["path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(rounded(result), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "verdict": result["verdict"], "output": str(output_path), "sha256": sha256(output_path)}))


if __name__ == "__main__":
    main()
