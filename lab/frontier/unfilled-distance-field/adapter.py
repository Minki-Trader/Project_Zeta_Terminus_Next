from __future__ import annotations

import json
import math
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[3]
TESTER_LOG_DIRECTORY = ROOT / "lab" / "runtime" / "tester-portable" / "Tester" / "logs"
ECONOMIC_JOURNAL = (
    ROOT
    / "lab"
    / "artifacts"
    / "backtests"
    / "deposit-capital-risk-capacity"
    / "selection-2025-control-100-agent.log"
)
OUTPUT_PATH = Path(__file__).with_name("proxy.json")

COMPONENTS = {
    0: {"name": "compression_16", "symbol": "US30"},
    1: {"name": "compression_4", "symbol": "US30"},
    2: {"name": "cross_market", "symbol": "US100"},
    3: {"name": "pressure", "symbol": "US30"},
    4: {"name": "return", "symbol": "US30"},
    5: {"name": "passive", "symbol": "US100"},
}
WINDOWS_MINUTES = (720, 1440, 2880, 4320)
MEASUREMENT_MARKER = "zt-next-frontier-unfilled-distance-field-v1 initialized"
MEASUREMENT_END_MARKER = "ZETA_FRONTIER_UNFILLED_DISTANCE_SUMMARY|"
GEOMETRY_MARKER = "ZETA_FRONTIER_UNFILLED_GEOMETRY|"


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


def as_int(fields: dict[str, str], key: str) -> int:
    return int(float(fields[key]))


def as_float(fields: dict[str, str], key: str) -> float:
    return float(fields[key])


def latest_measurement_session() -> tuple[Path, list[str]]:
    for path in sorted(
        TESTER_LOG_DIRECTORY.glob("*.log"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        lines = path.read_text(encoding="utf-16-le").splitlines()
        starts = [index for index, line in enumerate(lines) if MEASUREMENT_MARKER in line]
        if not starts:
            continue
        start = starts[-1]
        for end in range(start, len(lines)):
            if MEASUREMENT_END_MARKER in lines[end]:
                return path, lines[start : end + 1]
    raise RuntimeError("No completed unfilled-distance measurement session was found")


def read_session(
    lines: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    opportunities: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    geometries: list[dict[str, Any]] = []
    summary: dict[str, int] = {}
    for line in lines:
        raw = fields_after(line, "SIRA_OPPORTUNITY|")
        if raw is not None:
            component = as_int(raw, "component")
            opportunities.append(
                {
                    "id": as_int(raw, "id"),
                    "server": as_int(raw, "server"),
                    "component": component,
                    "symbol": COMPONENTS[component]["symbol"],
                    "direction": as_int(raw, "direction"),
                    "signal": as_float(raw, "signal"),
                    "outcome": raw["outcome"],
                    "volume": as_float(raw, "volume"),
                    "planned_risk": as_float(raw, "planned_risk"),
                }
            )
            continue

        raw = fields_after(line, "SIRA_EVENT|")
        if raw is not None:
            events.append(
                {
                    "server": as_int(raw, "server"),
                    "opportunity": as_int(raw, "opportunity"),
                    "component": as_int(raw, "component"),
                    "name": raw["name"],
                    "value_a": as_float(raw, "value_a"),
                    "value_b": as_float(raw, "value_b"),
                    "detail": raw.get("detail", ""),
                    "sequence": as_int(raw, "sequence"),
                }
            )
            continue

        raw = fields_after(line, GEOMETRY_MARKER)
        if raw is not None:
            farthest = as_float(raw, "farthest_ratio")
            endpoint = as_float(raw, "endpoint_ratio")
            geometry = {
                "server": as_int(raw, "server"),
                "placed": as_int(raw, "placed"),
                "expiration": as_int(raw, "expiration"),
                "direction": as_int(raw, "direction"),
                "feature": as_float(raw, "feature"),
                "feature_abs": abs(as_float(raw, "feature")),
                "limit": as_float(raw, "limit"),
                "stop": as_float(raw, "stop"),
                "span": as_float(raw, "span"),
                "ticks": as_int(raw, "ticks"),
                "first_ratio": as_float(raw, "first_ratio"),
                "closest_ratio": as_float(raw, "closest_ratio"),
                "farthest_ratio": farthest,
                "endpoint_ratio": endpoint,
                "escape_ratio": as_float(raw, "escape_ratio"),
                "travel_ratio": as_float(raw, "travel_ratio"),
                "path_efficiency": as_float(raw, "path_efficiency"),
                "endpoint_speed": as_float(raw, "endpoint_speed"),
                "terminal_persistence": endpoint / farthest if farthest > 0.0 else 0.0,
            }
            geometries.append(geometry)
            continue

        raw = fields_after(line, MEASUREMENT_END_MARKER)
        if raw is not None:
            summary = {key: as_int(raw, key) for key in raw}
    return opportunities, events, geometries, summary


def read_economic_journal(
    source_log: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    opportunities: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    with source_log.open("r", encoding="utf-16-le") as handle:
        for line in handle:
            raw = fields_after(line, "SIRA_OPPORTUNITY|")
            if raw is not None:
                component = as_int(raw, "component")
                opportunities.append(
                    {
                        "id": as_int(raw, "id"),
                        "server": as_int(raw, "server"),
                        "component": component,
                        "symbol": COMPONENTS[component]["symbol"],
                        "direction": as_int(raw, "direction"),
                        "signal": as_float(raw, "signal"),
                        "outcome": raw["outcome"],
                        "volume": as_float(raw, "volume"),
                        "planned_risk": as_float(raw, "planned_risk"),
                    }
                )
                continue

            raw = fields_after(line, "SIRA_EVENT|")
            if raw is not None:
                events.append(
                    {
                        "server": as_int(raw, "server"),
                        "opportunity": as_int(raw, "opportunity"),
                        "component": as_int(raw, "component"),
                        "name": raw["name"],
                        "value_a": as_float(raw, "value_a"),
                        "value_b": as_float(raw, "value_b"),
                        "detail": raw.get("detail", ""),
                        "sequence": as_int(raw, "sequence"),
                    }
                )
    return opportunities, events


def detail_value(detail: str, key: str) -> str | None:
    match = re.search(rf"(?:^| ){re.escape(key)}=([^ ]+)", detail)
    return match.group(1) if match else None


def remaining_volume(detail: str) -> float:
    value = detail_value(detail, "remaining")
    return float(value) if value is not None else 0.0


def reconstruct_trades(
    opportunities: list[dict[str, Any]], events: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    by_id = {opportunity["id"]: opportunity for opportunity in opportunities}
    active: dict[int, dict[str, Any]] = {}
    pending_passive_id: int | None = None
    trades: list[dict[str, Any]] = []
    diagnostics: Counter[str] = Counter()

    def start_trade(opportunity_id: int, fill_server: int) -> None:
        opportunity = by_id.get(opportunity_id)
        if opportunity is None:
            diagnostics["entry_without_opportunity"] += 1
            return
        component = opportunity["component"]
        if component in active:
            diagnostics["entry_while_component_active"] += 1
            return
        active[component] = {
            "opportunity_id": opportunity_id,
            "component": component,
            "decision_server": opportunity["server"],
            "fill_server": fill_server,
            "direction": opportunity["direction"],
            "actual_net": 0.0,
            "stressed_net": 0.0,
        }

    for event in sorted(events, key=lambda item: item["sequence"]):
        name = event["name"]
        component = event["component"]
        if name == "PASSIVE_PLACE":
            pending_passive_id = event["opportunity"]
        elif name == "PASSIVE_EXPIRE":
            pending_passive_id = None
        elif name == "OPEN":
            start_trade(event["opportunity"], event["server"])
        elif name == "PASSIVE_FILL":
            if pending_passive_id is None:
                diagnostics["passive_fill_without_pending"] += 1
            else:
                start_trade(pending_passive_id, event["server"])
                pending_passive_id = None
        elif name in {"CLOSE", "EXTERNAL_CLOSE"}:
            trade = active.get(component)
            if trade is None:
                diagnostics["close_without_entry"] += 1
                continue
            trade["actual_net"] += event["value_a"]
            trade["stressed_net"] += event["value_b"]
            if remaining_volume(event["detail"]) <= 1e-9:
                trade["close_server"] = event["server"]
                trade["duration_minutes"] = (
                    event["server"] - trade["fill_server"]
                ) / 60.0
                trade["close_reason"] = detail_value(event["detail"], "reason") or ""
                trades.append(trade)
                del active[component]

    diagnostics["open_at_end"] = len(active)
    diagnostics["pending_at_end"] = int(pending_passive_id is not None)
    return trades, dict(diagnostics)


def decorate_trades(
    trades: list[dict[str, Any]], geometries: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    decorated: list[dict[str, Any]] = []
    for trade in trades:
        prior = [
            geometry
            for geometry in geometries
            if geometry["server"] < trade["decision_server"]
        ]
        enriched = dict(trade)
        enriched["prior_geometries"] = prior
        decorated.append(enriched)
    return sorted(decorated, key=lambda item: item["decision_server"])


def rounded(value: float | None) -> float | None:
    return round(value, 6) if value is not None and math.isfinite(value) else None


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = round((len(ordered) - 1) * probability)
    return ordered[index]


def geometry_distribution(geometries: list[dict[str, Any]]) -> dict[str, Any]:
    fields = (
        "first_ratio",
        "closest_ratio",
        "farthest_ratio",
        "endpoint_ratio",
        "escape_ratio",
        "travel_ratio",
        "path_efficiency",
        "endpoint_speed",
        "terminal_persistence",
        "feature_abs",
    )
    result: dict[str, Any] = {}
    for field in fields:
        values = [geometry[field] for geometry in geometries]
        result[field] = {
            "minimum": rounded(min(values)),
            "q25": rounded(quantile(values, 0.25)),
            "median": rounded(quantile(values, 0.50)),
            "q75": rounded(quantile(values, 0.75)),
            "maximum": rounded(max(values)),
            "mean": rounded(statistics.fmean(values)),
        }
    return result


EmitterPredicate = Callable[[dict[str, Any]], bool]
EmitterCandidate = tuple[str, str, dict[str, Any], EmitterPredicate]


def emitter_hypotheses(
    geometries: list[dict[str, Any]],
) -> list[EmitterCandidate]:
    candidates: list[EmitterCandidate] = [
        ("direction_only", "any_refusal", {}, lambda geometry: True)
    ]

    def add(
        family: str,
        name: str,
        params: dict[str, Any],
        predicate: EmitterPredicate,
    ) -> None:
        candidates.append((family, name, params, predicate))

    fields = (
        "closest_ratio",
        "endpoint_ratio",
        "escape_ratio",
        "travel_ratio",
        "path_efficiency",
        "terminal_persistence",
        "feature_abs",
    )
    thresholds: dict[str, dict[str, float]] = {}
    for field in fields:
        values = [geometry[field] for geometry in geometries]
        thresholds[field] = {
            "q25": quantile(values, 0.25),
            "q50": quantile(values, 0.50),
            "q75": quantile(values, 0.75),
        }
        for label, threshold in thresholds[field].items():
            add(
                "geometry_high",
                f"{field}_high_{label}",
                {"field": field, "minimum": threshold},
                lambda geometry, field=field, threshold=threshold: geometry[field]
                >= threshold,
            )
            add(
                "geometry_low",
                f"{field}_low_{label}",
                {"field": field, "maximum": threshold},
                lambda geometry, field=field, threshold=threshold: geometry[field]
                <= threshold,
            )

    q = thresholds
    add(
        "path_shape",
        "runaway_terminal",
        {"endpoint": "q75+", "terminal_persistence": 0.75},
        lambda geometry: geometry["endpoint_ratio"] >= q["endpoint_ratio"]["q75"]
        and geometry["terminal_persistence"] >= 0.75,
    )
    add(
        "path_shape",
        "deep_fade",
        {"endpoint": "q75+", "terminal_persistence": 0.50},
        lambda geometry: geometry["farthest_ratio"] >= q["endpoint_ratio"]["q75"]
        and geometry["terminal_persistence"] <= 0.50,
    )
    add(
        "path_shape",
        "near_miss_snapaway",
        {"closest": "q25-", "escape": "q75+", "persistence": 0.75},
        lambda geometry: geometry["closest_ratio"] <= q["closest_ratio"]["q25"]
        and geometry["escape_ratio"] >= q["escape_ratio"]["q75"]
        and geometry["terminal_persistence"] >= 0.75,
    )
    add(
        "path_shape",
        "clean_escape",
        {"endpoint": "q50+", "travel": "q50-", "efficiency": "q50+"},
        lambda geometry: geometry["endpoint_ratio"] >= q["endpoint_ratio"]["q50"]
        and geometry["travel_ratio"] <= q["travel_ratio"]["q50"]
        and geometry["path_efficiency"] >= q["path_efficiency"]["q50"],
    )
    add(
        "path_shape",
        "noisy_escape",
        {"endpoint": "q50+", "travel": "q75+"},
        lambda geometry: geometry["endpoint_ratio"] >= q["endpoint_ratio"]["q50"]
        and geometry["travel_ratio"] >= q["travel_ratio"]["q75"],
    )
    add(
        "path_shape",
        "late_escape",
        {"closest": "q50-", "endpoint": "q75+"},
        lambda geometry: geometry["closest_ratio"] <= q["closest_ratio"]["q50"]
        and geometry["endpoint_ratio"] >= q["endpoint_ratio"]["q75"],
    )
    add(
        "path_shape",
        "strong_signal_escape",
        {"feature_abs": "q75+", "endpoint": "q50+"},
        lambda geometry: geometry["feature_abs"] >= q["feature_abs"]["q75"]
        and geometry["endpoint_ratio"] >= q["endpoint_ratio"]["q50"],
    )
    add(
        "path_shape",
        "weak_signal_escape",
        {"feature_abs": "q25-", "endpoint": "q50+"},
        lambda geometry: geometry["feature_abs"] <= q["feature_abs"]["q25"]
        and geometry["endpoint_ratio"] >= q["endpoint_ratio"]["q50"],
    )
    return candidates


def trade_matches(
    trade: dict[str, Any],
    window_minutes: int,
    relation: int,
    emitter_predicate: EmitterPredicate,
) -> bool:
    for geometry in trade["prior_geometries"]:
        age_seconds = trade["decision_server"] - geometry["server"]
        if age_seconds > window_minutes * 60:
            continue
        direction_relation = 1 if geometry["direction"] == trade["direction"] else -1
        if direction_relation == relation and emitter_predicate(geometry):
            return True
    return False


def lens_metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    values = [trade["stressed_net"] for trade in trades]
    actual = [trade["actual_net"] for trade in trades]
    cumulative = 0.0
    peak = 0.0
    drawdown = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        drawdown = max(drawdown, peak - cumulative)
    wins = [value for value in values if value > 0.0]
    losses = [value for value in values if value < 0.0]
    return {
        "count": len(values),
        "actual_net": rounded(sum(actual)),
        "stressed_net": rounded(sum(values)),
        "mean_stressed": rounded(statistics.fmean(values)) if values else 0.0,
        "win_rate": rounded(len(wins) / len(values)) if values else None,
        "profit_factor": rounded(sum(wins) / -sum(losses)) if losses else None,
        "closed_drawdown": rounded(drawdown),
        "sl_rate": rounded(
            sum(trade["close_reason"] == "DEAL_REASON_SL" for trade in trades)
            / len(trades)
        )
        if trades
        else None,
        "mean_duration_minutes": rounded(
            statistics.fmean(trade["duration_minutes"] for trade in trades)
        )
        if trades
        else None,
    }


def split_metrics(selected: list[dict[str, Any]], split_server: int) -> dict[str, Any]:
    return {
        "full": lens_metrics(selected),
        "early": lens_metrics(
            [trade for trade in selected if trade["decision_server"] < split_server]
        ),
        "late": lens_metrics(
            [trade for trade in selected if trade["decision_server"] >= split_server]
        ),
    }


def stable_increment_score(metrics: dict[str, Any], baseline: dict[str, Any]) -> float | None:
    if (
        metrics["full"]["count"] < 6
        or metrics["early"]["count"] < 2
        or metrics["late"]["count"] < 2
    ):
        return None
    early = metrics["early"]["mean_stressed"] - baseline["early"]["mean_stressed"]
    late = metrics["late"]["mean_stressed"] - baseline["late"]["mean_stressed"]
    floor = min(early, late)
    if floor <= 0.0:
        return None
    return rounded(floor * math.sqrt(metrics["full"]["count"]))


def stable_drag_score(metrics: dict[str, Any], baseline: dict[str, Any]) -> float | None:
    if (
        metrics["full"]["count"] < 6
        or metrics["early"]["count"] < 2
        or metrics["late"]["count"] < 2
    ):
        return None
    early = baseline["early"]["mean_stressed"] - metrics["early"]["mean_stressed"]
    late = baseline["late"]["mean_stressed"] - metrics["late"]["mean_stressed"]
    floor = min(early, late)
    if floor <= 0.0:
        return None
    return rounded(floor * math.sqrt(metrics["full"]["count"]))


def compact(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "family": row["family"],
        "name": row["name"],
        "params": row["params"],
        "receiver": row["receiver_name"],
        "window_minutes": row["window_minutes"],
        "relation": row["relation_name"],
        "increment_score": row["increment_score"],
        "drag_score": row["drag_score"],
        "metrics": row["metrics"],
        "direction_only_baseline": row["baseline"],
    }


def main() -> None:
    measurement_log, lines = latest_measurement_session()
    _, _, geometries, measurement_summary = read_session(lines)
    opportunities, events = read_economic_journal(ECONOMIC_JOURNAL)
    trades, reconstruction = reconstruct_trades(opportunities, events)
    trades = decorate_trades(trades, geometries)
    split_server = trades[len(trades) // 2]["decision_server"]
    emitter_candidates = emitter_hypotheses(geometries)

    direction_baselines: dict[tuple[int | None, int, int], dict[str, Any]] = {}
    for receiver in (None, *COMPONENTS.keys()):
        universe = [
            trade for trade in trades if receiver is None or trade["component"] == receiver
        ]
        for window in WINDOWS_MINUTES:
            for relation in (1, -1):
                selected = [
                    trade
                    for trade in universe
                    if trade_matches(trade, window, relation, lambda geometry: True)
                ]
                direction_baselines[(receiver, window, relation)] = split_metrics(
                    selected, split_server
                )

    rows: list[dict[str, Any]] = []
    for receiver in (None, *COMPONENTS.keys()):
        receiver_name = "all" if receiver is None else COMPONENTS[receiver]["name"]
        universe = [
            trade for trade in trades if receiver is None or trade["component"] == receiver
        ]
        for family, name, params, emitter_predicate in emitter_candidates:
            if family == "direction_only":
                continue
            for window in WINDOWS_MINUTES:
                for relation_name, relation in (("same", 1), ("opposite", -1)):
                    selected = [
                        trade
                        for trade in universe
                        if trade_matches(trade, window, relation, emitter_predicate)
                    ]
                    metrics = split_metrics(selected, split_server)
                    baseline = direction_baselines[(receiver, window, relation)]
                    rows.append(
                        {
                            "family": family,
                            "name": name,
                            "params": params,
                            "receiver": receiver,
                            "receiver_name": receiver_name,
                            "window_minutes": window,
                            "relation_name": relation_name,
                            "metrics": metrics,
                            "baseline": baseline,
                            "increment_score": stable_increment_score(metrics, baseline),
                            "drag_score": stable_drag_score(metrics, baseline),
                        }
                    )

    increments = [row for row in rows if row["increment_score"] is not None]
    drags = [row for row in rows if row["drag_score"] is not None]
    increments.sort(key=lambda row: row["increment_score"], reverse=True)
    drags.sort(key=lambda row: row["drag_score"], reverse=True)
    family_leaders: dict[str, Any] = {}
    for family in sorted({row["family"] for row in rows}):
        family_leaders[family] = {
            "increment": next(
                (compact(row) for row in increments if row["family"] == family), None
            ),
            "drag": next(
                (compact(row) for row in drags if row["family"] == family), None
            ),
        }

    direction_only: dict[str, Any] = {}
    for receiver in COMPONENTS:
        receiver_name = COMPONENTS[receiver]["name"]
        direction_only[receiver_name] = {}
        for window in WINDOWS_MINUTES:
            direction_only[receiver_name][str(window)] = {
                relation_name: direction_baselines[(receiver, window, relation)]
                for relation_name, relation in (("same", 1), ("opposite", -1))
            }

    document = {
        "unit": "unfilled-distance-field-004",
        "question": "Does the normalized path by which price refuses an expiring Passive limit explain later receiver economics beyond direction alone?",
        "measurement_log": str(measurement_log.relative_to(ROOT)).replace("\\", "/"),
        "economic_journal": str(ECONOMIC_JOURNAL.relative_to(ROOT)).replace("\\", "/"),
        "causality": "Geometry is emitted only after broker-observed expiration. Receiver decisions see strictly earlier expiration seconds.",
        "measurement": {
            "summary": measurement_summary,
            "geometry_count": len(geometries),
            "geometry_distribution": geometry_distribution(geometries),
            "geometries": geometries,
        },
        "counts": {
            "opportunities": len(opportunities),
            "events": len(events),
            "completed_trades": len(trades),
            "emitter_hypotheses": len(emitter_candidates),
            "evaluations": len(rows),
            "increment_candidates": len(increments),
            "drag_candidates": len(drags),
        },
        "opportunity_outcomes": dict(
            Counter(opportunity["outcome"] for opportunity in opportunities)
        ),
        "reconstruction": reconstruction,
        "base": split_metrics(trades, split_server),
        "split_server": split_server,
        "direction_only_receiver_lenses": direction_only,
        "geometry_increment_leaders": [compact(row) for row in increments[:50]],
        "geometry_drag_leaders": [compact(row) for row in drags[:50]],
        "family_leaders": family_leaders,
        "limits": [
            "Only expired orders are measured; filled Passive orders are a different censoring outcome.",
            "Geometry cells are descriptive seeds from 29 expirations, not validation evidence.",
            "The measurement preserves the exact parent economic path but its runtime log is local and intentionally not promoted to Live.",
        ],
    }
    OUTPUT_PATH.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
