from __future__ import annotations

import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIRECTORY = (
    ROOT / "lab" / "artifacts" / "backtests" / "deposit-capital-risk-capacity"
)
SOURCE_LOGS = {
    "capital_100": SOURCE_DIRECTORY / "selection-2025-control-100-agent.log",
    "capital_200": SOURCE_DIRECTORY / "selection-2025-control-200-agent.log",
    "capital_300": SOURCE_DIRECTORY / "selection-2025-control-300-agent.log",
}
OUTPUT_PATH = Path(__file__).with_name("proxy.json")

COMPONENTS = {
    0: {"name": "compression_16", "symbol": "US30"},
    1: {"name": "compression_4", "symbol": "US30"},
    2: {"name": "cross_market", "symbol": "US100"},
    3: {"name": "pressure", "symbol": "US30"},
    4: {"name": "return", "symbol": "US30"},
    5: {"name": "passive", "symbol": "US100"},
}
WINDOWS_MINUTES = (15, 30, 60, 120, 240, 480, 1440)


def fields_after(line: str, marker: str) -> dict[str, str] | None:
    offset = line.find(marker)
    if offset < 0:
        return None
    payload = line[offset + len(marker) :].strip()
    fields: dict[str, str] = {}
    for token in payload.split("|"):
        if "=" in token:
            key, value = token.split("=", 1)
            fields[key] = value
    return fields


def as_int(fields: dict[str, str], key: str) -> int:
    return int(float(fields[key]))


def as_float(fields: dict[str, str], key: str) -> float:
    return float(fields[key])


def read_journal(
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
                        "active_mask": as_int(raw, "active_mask"),
                        "aggregate_risk": as_float(raw, "aggregate_risk"),
                        "risk_capital": as_float(raw, "risk_capital"),
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


def remaining_volume(detail: str) -> float:
    match = re.search(r"(?:^| )remaining=([-+0-9.]+)", detail)
    return float(match.group(1)) if match else 0.0


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
            "source_volume": opportunity["volume"],
            "planned_risk": opportunity["planned_risk"],
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
                trade["close_kind"] = name
                trades.append(trade)
                del active[component]

    diagnostics["open_at_end"] = len(active)
    diagnostics["pending_at_end"] = int(pending_passive_id is not None)
    return trades, dict(diagnostics)


def decorate_trades(
    trades: list[dict[str, Any]], opportunities: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    ordered_opportunities = sorted(
        opportunities, key=lambda item: (item["server"], item["id"])
    )
    by_id = {opportunity["id"]: opportunity for opportunity in opportunities}
    decorated: list[dict[str, Any]] = []

    for trade in trades:
        current = by_id[trade["opportunity_id"]]
        causal_prior = [
            opportunity
            for opportunity in ordered_opportunities
            if (opportunity["server"], opportunity["id"])
            < (current["server"], current["id"])
        ]
        same_component_prior = [
            opportunity
            for opportunity in causal_prior
            if opportunity["component"] == current["component"]
        ]
        other_component_prior = [
            opportunity
            for opportunity in causal_prior
            if opportunity["component"] != current["component"]
        ]

        def gap_minutes(pool: list[dict[str, Any]]) -> float | None:
            if not pool:
                return None
            return (current["server"] - pool[-1]["server"]) / 60.0

        window_features: dict[str, dict[str, Any]] = {}
        for window in WINDOWS_MINUTES:
            recent = [
                opportunity
                for opportunity in causal_prior
                if current["server"] - opportunity["server"] <= window * 60
            ]
            same_direction = sum(
                opportunity["direction"] == current["direction"]
                for opportunity in recent
            )
            opposite_direction = sum(
                opportunity["direction"] == -current["direction"]
                for opportunity in recent
            )
            cross_symbol = [
                opportunity
                for opportunity in recent
                if opportunity["symbol"] != current["symbol"]
            ]
            window_features[str(window)] = {
                "count": len(recent),
                "same_direction": same_direction,
                "opposite_direction": opposite_direction,
                "agreement": (
                    (same_direction - opposite_direction) / len(recent)
                    if recent
                    else 0.0
                ),
                "distinct_components": len(
                    {opportunity["component"] for opportunity in recent}
                ),
                "cross_symbol": len(cross_symbol),
                "cross_same_direction": sum(
                    opportunity["direction"] == current["direction"]
                    for opportunity in cross_symbol
                ),
                "cross_opposite_direction": sum(
                    opportunity["direction"] == -current["direction"]
                    for opportunity in cross_symbol
                ),
            }

        prior_hour = sum(
            60 * 60 < current["server"] - opportunity["server"] <= 120 * 60
            for opportunity in causal_prior
        )
        active_count = int(current["active_mask"]).bit_count()
        risk_capital = current["risk_capital"]
        enriched = dict(trade)
        enriched.update(
            {
                "symbol": current["symbol"],
                "source_outcome": current["outcome"],
                "active_count": active_count,
                "risk_load": (
                    current["aggregate_risk"] / risk_capital
                    if risk_capital > 0.0
                    else 0.0
                ),
                "same_cycle_prior": sum(
                    opportunity["server"] == current["server"]
                    for opportunity in causal_prior
                ),
                "gap_any_minutes": gap_minutes(causal_prior),
                "gap_same_component_minutes": gap_minutes(same_component_prior),
                "gap_other_component_minutes": gap_minutes(other_component_prior),
                "prior_hour_count": prior_hour,
                "windows": window_features,
            }
        )
        decorated.append(enriched)
    return sorted(decorated, key=lambda item: item["decision_server"])


def rounded(value: float | None) -> float | None:
    return round(value, 6) if value is not None and math.isfinite(value) else None


def lens_metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    values = [trade["stressed_net"] for trade in trades]
    actual_values = [trade["actual_net"] for trade in trades]
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        max_drawdown = max(max_drawdown, peak - cumulative)
    wins = sum(value > 0.0 for value in values)
    gross_profit = sum(value for value in values if value > 0.0)
    gross_loss = -sum(value for value in values if value < 0.0)
    mean = statistics.fmean(values) if values else 0.0
    deviation = statistics.pstdev(values) if len(values) > 1 else 0.0
    quality = mean / deviation * math.sqrt(len(values)) if deviation > 0.0 else 0.0
    return {
        "count": len(values),
        "actual_net": rounded(sum(actual_values)),
        "stressed_net": rounded(sum(values)),
        "mean_stressed": rounded(mean),
        "win_rate": rounded(wins / len(values)) if values else None,
        "profit_factor": rounded(gross_profit / gross_loss) if gross_loss > 0.0 else None,
        "closed_drawdown": rounded(max_drawdown),
        "net_to_drawdown": rounded(sum(values) / max_drawdown)
        if max_drawdown > 0.0
        else None,
        "quality": rounded(quality),
    }


def candidate_metrics(
    selected: list[dict[str, Any]], split_server: int, base_count: int
) -> dict[str, Any]:
    early = [trade for trade in selected if trade["decision_server"] < split_server]
    late = [trade for trade in selected if trade["decision_server"] >= split_server]
    component_rows: dict[str, Any] = {}
    for component, identity in COMPONENTS.items():
        component_rows[identity["name"]] = lens_metrics(
            [trade for trade in selected if trade["component"] == component]
        )
    return {
        "full": lens_metrics(selected),
        "early": lens_metrics(early),
        "late": lens_metrics(late),
        "component_coverage": sum(
            any(trade["component"] == component for trade in selected)
            for component in COMPONENTS
        ),
        "entry_frequency_additions": len(selected),
        "entry_frequency_delta_pct": rounded(100.0 * len(selected) / base_count),
        "components": component_rows,
    }


Candidate = tuple[str, str, dict[str, Any], Callable[[dict[str, Any]], bool]]


def hypotheses() -> list[Candidate]:
    candidates: list[Candidate] = []

    def add(
        family: str,
        name: str,
        params: dict[str, Any],
        predicate: Callable[[dict[str, Any]], bool],
    ) -> None:
        candidates.append((family, name, params, predicate))

    for gap in (30, 60, 120, 240, 480, 720, 1440, 2880):
        add(
            "silence_revival",
            f"any_gap_at_least_{gap}m",
            {"gap_minutes": gap},
            lambda trade, gap=gap: trade["gap_any_minutes"] is not None
            and trade["gap_any_minutes"] >= gap,
        )

    for gap in (120, 240, 480, 720, 1440, 2880, 7200):
        add(
            "component_recharge",
            f"component_gap_at_least_{gap}m",
            {"gap_minutes": gap},
            lambda trade, gap=gap: trade["gap_same_component_minutes"] is not None
            and trade["gap_same_component_minutes"] >= gap,
        )

    for window in (15, 30, 60, 120, 240, 480):
        for minimum in (1, 2, 3, 4):
            for agreement in (0.0, 0.34, 0.67, 1.0):
                add(
                    "directional_echo",
                    f"echo_{window}m_n{minimum}_a{agreement}",
                    {"window_minutes": window, "minimum": minimum, "agreement": agreement},
                    lambda trade, window=window, minimum=minimum, agreement=agreement: (
                        trade["windows"][str(window)]["count"] >= minimum
                        and trade["windows"][str(window)]["agreement"] >= agreement
                    ),
                )
                add(
                    "directional_conflict",
                    f"conflict_{window}m_n{minimum}_a{agreement}",
                    {"window_minutes": window, "minimum": minimum, "agreement": -agreement},
                    lambda trade, window=window, minimum=minimum, agreement=agreement: (
                        trade["windows"][str(window)]["count"] >= minimum
                        and trade["windows"][str(window)]["agreement"] <= -agreement
                    ),
                )

    for window in (15, 30, 60, 120, 240, 480):
        for minimum in (1, 2, 3):
            add(
                "cross_symbol_relay",
                f"cross_same_{window}m_n{minimum}",
                {"window_minutes": window, "minimum": minimum, "relation": "same"},
                lambda trade, window=window, minimum=minimum: trade["windows"][str(window)][
                    "cross_same_direction"
                ]
                >= minimum,
            )
            add(
                "cross_symbol_relay",
                f"cross_opposite_{window}m_n{minimum}",
                {"window_minutes": window, "minimum": minimum, "relation": "opposite"},
                lambda trade, window=window, minimum=minimum: trade["windows"][str(window)][
                    "cross_opposite_direction"
                ]
                >= minimum,
            )

    for window in (30, 60, 120, 240, 480):
        for distinct in (2, 3, 4):
            for agreement in (0.0, 0.34, 0.67):
                add(
                    "multi_strategy_chorus",
                    f"chorus_{window}m_d{distinct}_a{agreement}",
                    {
                        "window_minutes": window,
                        "distinct_components": distinct,
                        "agreement": agreement,
                    },
                    lambda trade, window=window, distinct=distinct, agreement=agreement: (
                        trade["windows"][str(window)]["distinct_components"] >= distinct
                        and trade["windows"][str(window)]["agreement"] >= agreement
                    ),
                )

    for active_count in (0, 1, 2, 3):
        add(
            "position_ecology",
            f"active_exactly_{active_count}",
            {"active_count": active_count},
            lambda trade, active_count=active_count: trade["active_count"] == active_count,
        )
    for active_count in (1, 2, 3):
        for window in (60, 120, 240):
            add(
                "occupied_resonance",
                f"active_{active_count}plus_echo_{window}m",
                {"minimum_active": active_count, "window_minutes": window},
                lambda trade, active_count=active_count, window=window: (
                    trade["active_count"] >= active_count
                    and trade["windows"][str(window)]["count"] >= 1
                    and trade["windows"][str(window)]["agreement"] > 0.0
                ),
            )

    for threshold in (0.02, 0.04, 0.06, 0.08):
        add(
            "risk_headroom",
            f"risk_load_at_most_{threshold}",
            {"maximum_risk_load": threshold},
            lambda trade, threshold=threshold: trade["risk_load"] <= threshold,
        )
        add(
            "risk_occupation",
            f"risk_load_at_least_{threshold}",
            {"minimum_risk_load": threshold},
            lambda trade, threshold=threshold: trade["risk_load"] >= threshold,
        )

    for recent_minimum in (1, 2, 3):
        for lead in (1, 2):
            add(
                "tempo_acceleration",
                f"recent_hour_{recent_minimum}plus_lead_{lead}",
                {"recent_minimum": recent_minimum, "lead_over_prior_hour": lead},
                lambda trade, recent_minimum=recent_minimum, lead=lead: (
                    trade["windows"]["60"]["count"] >= recent_minimum
                    and trade["windows"]["60"]["count"] - trade["prior_hour_count"] >= lead
                ),
            )
        add(
            "tempo_release",
            f"prior_hour_{recent_minimum}plus_current_silence",
            {"prior_hour_minimum": recent_minimum, "recent_hour_maximum": 0},
            lambda trade, recent_minimum=recent_minimum: (
                trade["prior_hour_count"] >= recent_minimum
                and trade["windows"]["60"]["count"] == 0
            ),
        )

    for same_cycle in (1, 2, 3):
        add(
            "physical_sequence",
            f"same_cycle_prior_at_least_{same_cycle}",
            {"same_cycle_prior": same_cycle},
            lambda trade, same_cycle=same_cycle: trade["same_cycle_prior"] >= same_cycle,
        )
    return candidates


def discovery_score(metrics: dict[str, Any]) -> float | None:
    full = metrics["full"]
    early = metrics["early"]
    late = metrics["late"]
    if (
        full["count"] < 20
        or early["count"] < 6
        or late["count"] < 6
        or metrics["component_coverage"] < 4
    ):
        return None
    early_quality = early["quality"] or 0.0
    late_quality = late["quality"] or 0.0
    full_quality = full["quality"] or 0.0
    score = min(early_quality, late_quality) + 0.25 * full_quality
    return rounded(score)


def compact_candidate(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "family": row["family"],
        "name": row["name"],
        "params": row["params"],
        "score": row["score"],
        "metrics": row["metrics"],
    }


def evaluate(
    trades: list[dict[str, Any]],
) -> tuple[int, dict[str, Any], list[dict[str, Any]]]:
    split_server = trades[len(trades) // 2]["decision_server"]
    base_metrics = candidate_metrics(trades, split_server, len(trades))
    evaluated: list[dict[str, Any]] = []
    for family, name, params, predicate in hypotheses():
        selected = [trade for trade in trades if predicate(trade)]
        metrics = candidate_metrics(selected, split_server, len(trades))
        evaluated.append(
            {
                "family": family,
                "name": name,
                "params": params,
                "score": discovery_score(metrics),
                "metrics": metrics,
            }
        )
    return split_server, base_metrics, evaluated


def main() -> None:
    datasets: dict[str, dict[str, Any]] = {}
    for label, source_log in SOURCE_LOGS.items():
        opportunities, events = read_journal(source_log)
        trades, reconstruction = reconstruct_trades(opportunities, events)
        trades = decorate_trades(trades, opportunities)
        split_server, base_metrics, evaluated = evaluate(trades)
        datasets[label] = {
            "source_log": source_log,
            "opportunities": opportunities,
            "events": events,
            "trades": trades,
            "reconstruction": reconstruction,
            "split_server": split_server,
            "base_metrics": base_metrics,
            "evaluated": evaluated,
        }

    primary = datasets["capital_100"]
    opportunities = primary["opportunities"]
    events = primary["events"]
    trades = primary["trades"]
    reconstruction = primary["reconstruction"]
    split_server = primary["split_server"]
    base_metrics = primary["base_metrics"]
    evaluated = primary["evaluated"]

    eligible = [row for row in evaluated if row["score"] is not None]
    eligible.sort(key=lambda row: row["score"], reverse=True)
    balanced = [
        row
        for row in eligible
        if row["metrics"]["early"]["stressed_net"] > 0.0
        and row["metrics"]["late"]["stressed_net"] > 0.0
    ]

    family_leaders = []
    for family in sorted({row["family"] for row in evaluated}):
        family_rows = [row for row in eligible if row["family"] == family]
        if family_rows:
            family_leaders.append(compact_candidate(family_rows[0]))

    capital_robust: list[dict[str, Any]] = []
    for index, row in enumerate(evaluated):
        observations = {
            label: dataset["evaluated"][index]
            for label, dataset in datasets.items()
        }
        scores = [observation["score"] for observation in observations.values()]
        if any(score is None for score in scores):
            continue
        capital_robust.append(
            {
                "family": row["family"],
                "name": row["name"],
                "params": row["params"],
                "score": rounded(min(scores)),
                "all_lenses_positive": all(
                    observation["metrics"][lens]["stressed_net"] > 0.0
                    for observation in observations.values()
                    for lens in ("early", "late")
                ),
                "capital_lenses": {
                    label: observation["metrics"]
                    for label, observation in observations.items()
                },
            }
        )
    capital_robust.sort(key=lambda row: row["score"], reverse=True)
    capital_balanced = [row for row in capital_robust if row["all_lenses_positive"]]

    opportunity_outcomes = Counter(
        opportunity["outcome"] for opportunity in opportunities
    )
    opportunity_components = Counter(
        COMPONENTS[opportunity["component"]]["name"] for opportunity in opportunities
    )
    document = {
        "unit": "opportunity-ecology-001",
        "question": "Can causal portfolio rhythm identify additive economic states without suppressing base entries?",
        "sources": {
            label: str(dataset["source_log"].relative_to(ROOT)).replace("\\", "/")
            for label, dataset in datasets.items()
        },
        "causality": "Only prior opportunity IDs are visible; same-server lower IDs represent already-processed physical sequence.",
        "overlay_interpretation": "Each selected completed base trade is one hypothetical same-direction satellite. Base trades remain unchanged.",
        "split_server": split_server,
        "counts": {
            "opportunities": len(opportunities),
            "events": len(events),
            "completed_trades": len(trades),
            "hypotheses_evaluated": len(evaluated),
            "eligible_hypotheses": len(eligible),
            "balanced_hypotheses": len(balanced),
        },
        "opportunity_outcomes": dict(opportunity_outcomes),
        "opportunity_components": dict(opportunity_components),
        "reconstruction": reconstruction,
        "base": base_metrics,
        "capital_base_lenses": {
            label: {
                "split_server": dataset["split_server"],
                "counts": {
                    "opportunities": len(dataset["opportunities"]),
                    "events": len(dataset["events"]),
                    "completed_trades": len(dataset["trades"]),
                },
                "reconstruction": dataset["reconstruction"],
                "base": dataset["base_metrics"],
            }
            for label, dataset in datasets.items()
        },
        "capital_balanced_leaders": capital_balanced[:20],
        "capital_robust_leaders": capital_robust[:20],
        "balanced_leaders": [compact_candidate(row) for row in balanced[:20]],
        "overall_leaders": [compact_candidate(row) for row in eligible[:20]],
        "family_leaders": family_leaders,
        "limits": [
            "The satellite reuses the source trade path and therefore is an economic proxy, not a runtime fill simulation.",
            "The journals cover fresh 2025 Next Lab observations at three capital levels; early/late and capital lenses are descriptive, not a validation gate.",
            "Adding a full minimum-lot satellite may alter shared-account risk capacity, so runtime architecture must isolate or explicitly reserve its risk budget.",
        ],
    }
    OUTPUT_PATH.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
