#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import math
import re
import time
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


CONFIG_BYTES = 5376
CONFIG_SHA256 = "7F8636F8B9B599586C31F52BC3EB5D5267227482FEED5A882CE5438B07002E0F"
SCRIPT_PATH = Path(__file__).resolve()
FAMILY_ROOT = SCRIPT_PATH.parents[1]
REPOSITORY_ROOT = SCRIPT_PATH.parents[4]
CONFIG_PATH = FAMILY_ROOT / "config" / "contract.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def finite(value: Any, label: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise RuntimeError(f"non-finite {label}")
    return parsed


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root is not an object: {path}")
    return value


def load_contract() -> dict[str, Any]:
    if CONFIG_PATH.stat().st_size != CONFIG_BYTES or sha256(CONFIG_PATH) != CONFIG_SHA256:
        raise RuntimeError("frozen config pin mismatch")
    return load_json(CONFIG_PATH)


def load_inputs(contract: dict[str, Any]) -> tuple[dict[str, Path], str, int]:
    paths: dict[str, Path] = {}
    manifest_lines: list[str] = []
    total_bytes = 0
    for pin in contract["inputs"]:
        name = str(pin["name"])
        path = REPOSITORY_ROOT / str(pin["path"])
        actual_bytes = path.stat().st_size
        actual_sha = sha256(path)
        if actual_bytes != int(pin["bytes"]) or actual_sha != str(pin["sha256"]):
            raise RuntimeError(f"input pin mismatch: {name}")
        paths[name] = path
        total_bytes += actual_bytes
        manifest_lines.append(f"{name}|{actual_bytes}|{actual_sha}\n")
    manifest = hashlib.sha256("".join(manifest_lines).encode("utf-8")).hexdigest().upper()
    if len(paths) != int(contract["input_files"]):
        raise RuntimeError("input file count mismatch")
    if total_bytes != int(contract["input_bytes"]):
        raise RuntimeError("input byte total mismatch")
    if manifest != str(contract["input_manifest_sha256"]):
        raise RuntimeError("input manifest mismatch")
    return paths, manifest, total_bytes


class TableCellParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_td = False
        self._parts: list[str] = []
        self.cells: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "td":
            if self._in_td:
                raise RuntimeError("nested td in native report")
            self._in_td = True
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "td":
            return
        if not self._in_td:
            raise RuntimeError("closing td without opening td in native report")
        self._in_td = False
        value = html.unescape("".join(self._parts))
        self.cells.append(" ".join(value.replace("\xa0", " ").split()))

    def handle_data(self, data: str) -> None:
        if self._in_td:
            self._parts.append(data)


def parse_number(text: str, label: str) -> float:
    cleaned = text.replace("\xa0", " ").replace(" ", "").replace(",", "")
    parsed = finite(cleaned, label)
    return parsed


def next_cell(cells: list[str], label: str) -> str:
    indices = [index for index, value in enumerate(cells) if value == label]
    if len(indices) != 1:
        raise RuntimeError(f"expected one native report label {label}, found {len(indices)}")
    index = indices[0]
    if index + 1 >= len(cells):
        raise RuntimeError(f"native report label has no value: {label}")
    return cells[index + 1]


def parse_maximal_drawdown(text: str, label: str) -> tuple[float, float]:
    match = re.fullmatch(r"\s*([0-9 .-]+)\s*\(([0-9.]+)%\)\s*", text)
    if not match:
        raise RuntimeError(f"cannot parse maximal drawdown {label}: {text}")
    return parse_number(match.group(1), f"{label} usd"), parse_number(match.group(2), f"{label} pct")


def parse_relative_drawdown(text: str, label: str) -> tuple[float, float]:
    match = re.fullmatch(r"\s*([0-9.]+)%\s*\(([0-9 .-]+)\)\s*", text)
    if not match:
        raise RuntimeError(f"cannot parse relative drawdown {label}: {text}")
    return parse_number(match.group(1), f"{label} pct"), parse_number(match.group(2), f"{label} usd")


def parse_candidate_report(path: Path, label: str) -> dict[str, float | str]:
    parser = TableCellParser()
    parser.feed(path.read_text(encoding="utf-16"))
    cells = parser.cells
    history_quality = next_cell(cells, "히스토리 품질:")
    if history_quality != "100% 실제 틱":
        raise RuntimeError(f"candidate {label} history quality mismatch: {history_quality}")
    maximal_usd, maximal_pct = parse_maximal_drawdown(next_cell(cells, "Equity Drawdown Maximal:"), f"candidate {label} maximal equity dd")
    relative_pct, relative_usd = parse_relative_drawdown(next_cell(cells, "Equity Drawdown Relative:"), f"candidate {label} relative equity dd")
    return {
        "history_quality": history_quality,
        "actual_net_usd": parse_number(next_cell(cells, "총수입:"), f"candidate {label} net"),
        "gross_profit_usd": parse_number(next_cell(cells, "누적 수익:"), f"candidate {label} gross profit"),
        "gross_loss_usd": parse_number(next_cell(cells, "누적 손실:"), f"candidate {label} gross loss"),
        "maximal_equity_dd_usd": maximal_usd,
        "maximal_equity_dd_pct_at_amount": maximal_pct,
        "relative_equity_dd_pct": relative_pct,
        "relative_equity_dd_usd_at_pct": relative_usd,
        "profit_factor_displayed": parse_number(next_cell(cells, "Profit Factor:"), f"candidate {label} displayed pf"),
        "expected_payoff_displayed_usd": parse_number(next_cell(cells, "예상 비용:"), f"candidate {label} displayed expected payoff"),
        "recovery_factor_displayed": parse_number(next_cell(cells, "Recovery Factor:"), f"candidate {label} displayed recovery"),
        "sharpe_displayed": parse_number(next_cell(cells, "Sharpe Ratio:"), f"candidate {label} displayed sharpe"),
    }


def parse_optimization_row(path: Path, selected_pass: int) -> dict[str, float]:
    namespace = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}
    root = ET.parse(path).getroot()
    rows = root.findall(".//ss:Worksheet/ss:Table/ss:Row", namespace)
    if not rows:
        raise RuntimeError(f"no optimization rows: {path}")
    headers = [str(cell.text) for cell in rows[0].findall("ss:Cell/ss:Data", namespace)]
    selected: list[dict[str, str]] = []
    for row in rows[1:]:
        values = [str(cell.text) for cell in row.findall("ss:Cell/ss:Data", namespace)]
        if len(values) != len(headers):
            raise RuntimeError(f"optimization row width mismatch: {path}")
        mapped = dict(zip(headers, values, strict=True))
        if int(mapped["Pass"]) == selected_pass:
            selected.append(mapped)
    if len(selected) != 1:
        raise RuntimeError(f"expected one pass {selected_pass} row in {path}, found {len(selected)}")
    row = selected[0]
    return {
        "actual_net_usd": finite(row["Profit"], "control actual net"),
        "expected_payoff_usd": finite(row["Expected Payoff"], "control expected payoff"),
        "profit_factor": finite(row["Profit Factor"], "control profit factor"),
        "recovery_factor": finite(row["Recovery Factor"], "control recovery factor"),
        "sharpe": finite(row["Sharpe Ratio"], "control sharpe"),
        "relative_equity_dd_pct": finite(row["Equity DD %"], "control relative equity dd"),
        "trades": finite(row["Trades"], "control trades"),
        "position_risk_fraction": finite(row["InpMaximumPositionRiskFraction"], "control position risk"),
        "aggregate_risk_fraction": finite(row["InpMaximumAggregateRiskFraction"], "control aggregate risk"),
    }


def close(left: float, right: float, tolerance: float, label: str) -> None:
    if abs(left - right) > tolerance:
        raise RuntimeError(f"anchor mismatch {label}: {left} versus {right}")


def candidate_native_metrics(report: dict[str, float | str], source: dict[str, Any], label: str) -> dict[str, float]:
    actual_net = finite(report["actual_net_usd"], f"candidate {label} report net")
    source_net_key = "actual_net_usd"
    source_dd_key = "mt5_equity_drawdown_relative_pct" if label == "selection" else "mt5_equity_drawdown_maximal_and_relative_pct"
    source_net = finite(source[source_net_key], f"candidate {label} source net")
    source_dd = finite(source[source_dd_key], f"candidate {label} source dd")
    closes = int(source["closed_lifecycles"])
    close(actual_net, source_net, 1.0e-9, f"candidate {label} report net")
    close(finite(report["relative_equity_dd_pct"], "candidate report dd"), round(source_dd, 2), 1.0e-9, f"candidate {label} displayed relative dd")
    gross_profit = finite(report["gross_profit_usd"], f"candidate {label} gross profit")
    gross_loss = finite(report["gross_loss_usd"], f"candidate {label} gross loss")
    if gross_profit <= 0 or gross_loss >= 0:
        raise RuntimeError(f"candidate {label} gross book signs invalid")
    maximal_dd_usd = finite(report["maximal_equity_dd_usd"], f"candidate {label} maximal equity dd")
    if maximal_dd_usd <= 0 or closes <= 0:
        raise RuntimeError(f"candidate {label} denominator invalid")
    profit_factor = gross_profit / abs(gross_loss)
    expected_payoff = actual_net / closes
    recovery_factor = actual_net / maximal_dd_usd
    close(finite(report["profit_factor_displayed"], "displayed pf"), round(profit_factor, 2), 1.0e-9, f"candidate {label} displayed pf")
    close(finite(report["expected_payoff_displayed_usd"], "displayed expected payoff"), round(expected_payoff, 2), 1.0e-9, f"candidate {label} displayed expected payoff")
    close(finite(report["recovery_factor_displayed"], "displayed recovery"), round(recovery_factor, 2), 1.0e-9, f"candidate {label} displayed recovery")
    return {
        "actual_net_usd": actual_net,
        "closed_lifecycles": closes,
        "expected_payoff_usd": expected_payoff,
        "profit_factor": profit_factor,
        "recovery_factor": recovery_factor,
        "recovery_factor_displayed": finite(report["recovery_factor_displayed"], "candidate displayed recovery"),
        "sharpe_displayed": finite(report["sharpe_displayed"], "candidate displayed sharpe"),
        "maximal_equity_dd_usd": maximal_dd_usd,
        "relative_equity_dd_pct_exact": source_dd,
        "relative_equity_dd_pct_displayed": finite(report["relative_equity_dd_pct"], "candidate displayed relative dd"),
    }


def main() -> None:
    started = time.perf_counter()
    contract = load_contract()
    paths, manifest, input_bytes = load_inputs(contract)
    candidate = load_json(paths["candidate-result.json"])
    control = load_json(paths["live-control-result.json"])
    efficiency = load_json(paths["economic-efficiency-result.json"])

    fixed = contract["fixed_candidate"]
    candidate_identity = candidate["candidate"]
    if [finite(value, "candidate weight") for value in candidate_identity["component_exposure_multipliers"]] != [finite(value, "contract weight") for value in fixed["weights"]]:
        raise RuntimeError("candidate weight identity mismatch")
    close(finite(candidate_identity["position_risk_fraction"], "candidate position risk"), finite(fixed["position_risk_fraction"], "contract position risk"), 0, "candidate position risk")
    close(finite(candidate_identity["aggregate_risk_fraction"], "candidate aggregate risk"), finite(fixed["aggregate_risk_fraction"], "contract aggregate risk"), 0, "candidate aggregate risk")

    selected_pass = int(contract["active_live_control"]["selection_pass"])
    selection_control = parse_optimization_row(paths["control-selection-optimization.xml"], selected_pass)
    forward_control = parse_optimization_row(paths["control-forward-optimization.xml"], selected_pass)
    for label, row in (("selection", selection_control), ("forward", forward_control)):
        close(row["position_risk_fraction"], finite(contract["active_live_control"]["position_risk_fraction"], "contract control position risk"), 0, f"control {label} position risk")
        close(row["aggregate_risk_fraction"], finite(contract["active_live_control"]["aggregate_risk_fraction"], "contract control aggregate risk"), 0, f"control {label} aggregate risk")

    selection_control_source = next(row for row in control["selection_matrix"] if int(row["pass"]) == selected_pass)
    forward_control_source = next(row for row in control["forward_matrix"] if int(row["pass"]) == selected_pass)
    for label, row, source in (("selection", selection_control, selection_control_source), ("forward", forward_control, forward_control_source)):
        close(row["actual_net_usd"], finite(source["actual_net_usd"], f"control {label} source net"), 1.0e-9, f"control {label} net")
        close(row["relative_equity_dd_pct"], finite(source["equity_drawdown_pct"], f"control {label} source dd"), 1.0e-9, f"control {label} dd")
        close(row["trades"], float(source["closed_lifecycles"]), 0, f"control {label} trades")

    selection_candidate = candidate_native_metrics(
        parse_candidate_report(paths["candidate-selection-report.htm"], "selection"),
        candidate["selection"],
        "selection",
    )
    forward_candidate = candidate_native_metrics(
        parse_candidate_report(paths["candidate-forward-report.htm"], "forward"),
        candidate["forward"],
        "forward",
    )

    efficiency_verdict = "PASS_FIXED_DEVELOPMENT_CANDIDATE_ECONOMIC_EFFICIENCY_WITH_LOWER_TURNOVER_DISCLOSED"
    efficiency_pass = str(efficiency["verdict"]) == efficiency_verdict and bool(efficiency["gate_application"]["all_declared_gates_passed"])
    if not efficiency_pass:
        raise RuntimeError("prior economic-efficiency context mismatch")

    selection_comparison = {
        "candidate_minus_control_expected_payoff_usd": selection_candidate["expected_payoff_usd"] - selection_control["expected_payoff_usd"],
        "candidate_to_control_expected_payoff_ratio": selection_candidate["expected_payoff_usd"] / selection_control["expected_payoff_usd"],
        "candidate_minus_control_profit_factor": selection_candidate["profit_factor"] - selection_control["profit_factor"],
        "candidate_to_control_profit_factor_ratio": selection_candidate["profit_factor"] / selection_control["profit_factor"],
        "candidate_minus_control_recovery_factor": selection_candidate["recovery_factor"] - selection_control["recovery_factor"],
        "candidate_to_control_recovery_factor_ratio": selection_candidate["recovery_factor"] / selection_control["recovery_factor"],
        "candidate_minus_control_sharpe": selection_candidate["sharpe_displayed"] - selection_control["sharpe"],
        "candidate_to_control_sharpe_ratio": selection_candidate["sharpe_displayed"] / selection_control["sharpe"],
        "candidate_has_higher_profit_factor": selection_candidate["profit_factor"] > selection_control["profit_factor"],
        "candidate_has_lower_recovery_factor": selection_candidate["recovery_factor"] < selection_control["recovery_factor"],
        "candidate_has_lower_sharpe": selection_candidate["sharpe_displayed"] < selection_control["sharpe"],
    }
    forward_comparison = {
        "candidate_minus_control_expected_payoff_usd": forward_candidate["expected_payoff_usd"] - forward_control["expected_payoff_usd"],
        "candidate_minus_control_profit_factor": forward_candidate["profit_factor"] - forward_control["profit_factor"],
        "candidate_to_control_profit_factor_ratio": forward_candidate["profit_factor"] / forward_control["profit_factor"],
        "candidate_minus_control_recovery_factor": forward_candidate["recovery_factor"] - forward_control["recovery_factor"],
        "candidate_minus_control_sharpe": forward_candidate["sharpe_displayed"] - forward_control["sharpe"],
        "control_recovery_or_sharpe_ratios_reported": False,
        "ratio_boundary": "Control forward recovery factor and Sharpe are nonpositive, so ratios are not economically meaningful.",
        "candidate_has_higher_profit_factor": forward_candidate["profit_factor"] > forward_control["profit_factor"],
        "candidate_has_higher_recovery_factor": forward_candidate["recovery_factor"] > forward_control["recovery_factor"],
        "candidate_has_higher_sharpe": forward_candidate["sharpe_displayed"] > forward_control["sharpe"],
    }

    dominance = bool(
        selection_comparison["candidate_has_higher_profit_factor"]
        and selection_candidate["recovery_factor"] > selection_control["recovery_factor"]
        and selection_candidate["sharpe_displayed"] > selection_control["sharpe"]
        and forward_comparison["candidate_has_higher_profit_factor"]
        and forward_comparison["candidate_has_higher_recovery_factor"]
        and forward_comparison["candidate_has_higher_sharpe"]
        and efficiency_pass
    )
    tradeoff = bool(
        selection_comparison["candidate_has_higher_profit_factor"]
        and (selection_comparison["candidate_has_lower_recovery_factor"] or selection_comparison["candidate_has_lower_sharpe"])
        and forward_comparison["candidate_has_higher_profit_factor"]
        and forward_comparison["candidate_has_higher_recovery_factor"]
        and forward_comparison["candidate_has_higher_sharpe"]
        and efficiency_pass
    )
    if dominance:
        verdict = str(contract["verdicts"]["dominance"])
    elif tradeoff:
        verdict = str(contract["verdicts"]["tradeoff"])
    else:
        verdict = str(contract["verdicts"]["nonconfirmation"])

    result = {
        "schema": "zeta-dd20-paired-month-live-control-native-quality-recomparison-formal-result-v1",
        "recorded_at_local": "2026-08-30",
        "status": "VALID_COMPLETE",
        "campaign": str(contract["campaign"]),
        "integrity": {
            "passed": True,
            "config_bytes": CONFIG_BYTES,
            "config_sha256": CONFIG_SHA256,
            "input_files": len(paths),
            "input_bytes": input_bytes,
            "input_manifest_sha256": manifest,
            "candidate_identity_exact": True,
            "control_pass_and_risk_identity_exact": True,
            "candidate_reports_match_frozen_result_anchors": True,
            "control_xml_rows_match_frozen_result_anchors": True,
            "prior_economic_efficiency_pass_exact": efficiency_pass,
        },
        "selection": {
            "candidate": selection_candidate,
            "active_live_control": selection_control,
            "comparison": selection_comparison,
        },
        "forward": {
            "candidate": forward_candidate,
            "active_live_control": forward_control,
            "comparison": forward_comparison,
        },
        "classification": {
            "native_quality_dominance": dominance,
            "selection_native_quality_tradeoff": tradeoff,
            "forward_native_quality_dominance": bool(
                forward_comparison["candidate_has_higher_profit_factor"]
                and forward_comparison["candidate_has_higher_recovery_factor"]
                and forward_comparison["candidate_has_higher_sharpe"]
            ),
            "prior_economic_efficiency_pass_retained": efficiency_pass,
        },
        "verdict": verdict,
        "economic_boundary": {
            "candidate_sharpe_source_precision": "two decimals as displayed by the native MT5 HTML report",
            "control_xml_precision_retained": True,
            "selection_tradeoff_does_not_erase_prior_net_stressed_net_or_per_dd_point_dominance": True,
            "fixed_candidate_changed_or_retuned": False,
            "new_candidate_or_mt5_shortlist": False,
            "live_authority": False,
        },
        "execution": {
            "formal_source_free_processes": 1,
            "complete_fixed_policy_comparisons": 1,
            "economic_metric_reruns": 0,
            "mql_or_settings_changes": 0,
            "compile_or_tester_paths": 0,
            "orders": 0,
            "elapsed_seconds": time.perf_counter() - started,
        },
    }
    output_path = REPOSITORY_ROOT / str(contract["output"]["path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output_path), "verdict": verdict}, ensure_ascii=False))


if __name__ == "__main__":
    main()
