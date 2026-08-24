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
EMITTER_TYPES = ("risk_blocked", "expired_unfilled", "combined")
WINDOWS_MINUTES = (30, 60, 120, 240, 480, 1440, 2880)
HALF_LIVES_MINUTES = (30, 60, 120, 240, 480, 1440, 2880)


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


def detail_value(detail: str, key: str) -> str | None:
    match = re.search(rf"(?:^| ){re.escape(key)}=([^ ]+)", detail)
    return match.group(1) if match else None


def remaining_volume(detail: str) -> float:
    value = detail_value(detail, "remaining")
    return float(value) if value is not None else 0.0


def reconstruct(
    opportunities: list[dict[str, Any]], events: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    by_id = {opportunity["id"]: opportunity for opportunity in opportunities}
    active: dict[int, dict[str, Any]] = {}
    pending_passive_id: int | None = None
    trades: list[dict[str, Any]] = []
    expired_emitters: list[dict[str, Any]] = []
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
            "partial_closes": 0,
        }

    for event in sorted(events, key=lambda item: item["sequence"]):
        name = event["name"]
        component = event["component"]
        if name == "PASSIVE_PLACE":
            pending_passive_id = event["opportunity"]
        elif name == "PASSIVE_EXPIRE":
            if pending_passive_id is None:
                diagnostics["passive_expire_without_pending"] += 1
            else:
                opportunity = by_id.get(pending_passive_id)
                if opportunity is None:
                    diagnostics["passive_expire_without_opportunity"] += 1
                else:
                    expired_emitters.append(
                        {
                            "kind": "expired_unfilled",
                            "server": event["server"],
                            "source_server": opportunity["server"],
                            "source_id": opportunity["id"],
                            "component": opportunity["component"],
                            "symbol": opportunity["symbol"],
                            "direction": opportunity["direction"],
                            "signal": opportunity["signal"],
                        }
                    )
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
            trade["partial_closes"] += 1
            if remaining_volume(event["detail"]) <= 1e-9:
                trade["close_server"] = event["server"]
                trade["duration_minutes"] = (
                    event["server"] - trade["fill_server"]
                ) / 60.0
                trade["close_kind"] = name
                trade["close_reason"] = detail_value(event["detail"], "reason") or ""
                trades.append(trade)
                del active[component]

    risk_emitters = [
        {
            "kind": "risk_blocked",
            "server": opportunity["server"],
            "source_server": opportunity["server"],
            "source_id": opportunity["id"],
            "component": opportunity["component"],
            "symbol": opportunity["symbol"],
            "direction": opportunity["direction"],
            "signal": opportunity["signal"],
        }
        for opportunity in opportunities
        if opportunity["outcome"] == "PROTECTION_OR_RISK_BLOCKED"
    ]
    emitters = sorted(
        risk_emitters + expired_emitters,
        key=lambda item: (item["server"], item["source_id"], item["kind"]),
    )
    diagnostics["open_at_end"] = len(active)
    diagnostics["pending_at_end"] = int(pending_passive_id is not None)
    diagnostics["risk_emitters"] = len(risk_emitters)
    diagnostics["expired_emitters"] = len(expired_emitters)
    return trades, emitters, dict(diagnostics)


def relation_to_receiver(emitter: dict[str, Any], trade: dict[str, Any]) -> int:
    return 1 if emitter["direction"] == trade["direction"] else -1


def emitter_pool(
    emitters: list[dict[str, Any]], emitter_type: str
) -> list[dict[str, Any]]:
    if emitter_type == "combined":
        return emitters
    return [emitter for emitter in emitters if emitter["kind"] == emitter_type]


def decorate_trades(
    trades: list[dict[str, Any]],
    opportunities: list[dict[str, Any]],
    emitters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {opportunity["id"]: opportunity for opportunity in opportunities}
    decorated: list[dict[str, Any]] = []

    for trade in trades:
        current = by_id[trade["opportunity_id"]]
        causal_emitters = [
            emitter
            for emitter in emitters
            if emitter["server"] < current["server"]
        ]
        afterimages: dict[str, Any] = {}
        for emitter_type in EMITTER_TYPES:
            pool = emitter_pool(causal_emitters, emitter_type)
            last = pool[-1] if pool else None
            windows: dict[str, Any] = {}
            for window in WINDOWS_MINUTES:
                recent = [
                    emitter
                    for emitter in pool
                    if current["server"] - emitter["server"] <= window * 60
                ]
                relations = [relation_to_receiver(emitter, trade) for emitter in recent]
                windows[str(window)] = {
                    "count": len(recent),
                    "same_direction": sum(relation > 0 for relation in relations),
                    "opposite_direction": sum(relation < 0 for relation in relations),
                    "same_component": sum(
                        emitter["component"] == trade["component"]
                        for emitter in recent
                    ),
                    "other_component": sum(
                        emitter["component"] != trade["component"]
                        for emitter in recent
                    ),
                    "cross_symbol": sum(
                        emitter["symbol"] != current["symbol"] for emitter in recent
                    ),
                    "signed_balance": sum(relations),
                    "source_components": sorted(
                        {emitter["component"] for emitter in recent}
                    ),
                }

            decays: dict[str, Any] = {}
            for half_life in HALF_LIVES_MINUTES:
                weighted: list[tuple[dict[str, Any], float, int]] = []
                for emitter in pool:
                    age_minutes = (current["server"] - emitter["server"]) / 60.0
                    if age_minutes > half_life * 8:
                        continue
                    weight = 0.5 ** (age_minutes / half_life)
                    weighted.append((emitter, weight, relation_to_receiver(emitter, trade)))
                energy = sum(weight for _, weight, _ in weighted)
                signed_energy = sum(weight * relation for _, weight, relation in weighted)
                decays[str(half_life)] = {
                    "energy": energy,
                    "signed_energy": signed_energy,
                    "dominance": signed_energy / energy if energy > 0.0 else 0.0,
                    "same_energy": sum(
                        weight for _, weight, relation in weighted if relation > 0
                    ),
                    "opposite_energy": sum(
                        weight for _, weight, relation in weighted if relation < 0
                    ),
                    "same_component_energy": sum(
                        weight
                        for emitter, weight, _ in weighted
                        if emitter["component"] == trade["component"]
                    ),
                    "cross_symbol_energy": sum(
                        weight
                        for emitter, weight, _ in weighted
                        if emitter["symbol"] != current["symbol"]
                    ),
                }

            afterimages[emitter_type] = {
                "total_prior": len(pool),
                "last_gap_minutes": (
                    (current["server"] - last["server"]) / 60.0 if last else None
                ),
                "last_relation": relation_to_receiver(last, trade) if last else 0,
                "last_component": last["component"] if last else None,
                "last_same_component": (
                    last["component"] == trade["component"] if last else False
                ),
                "last_cross_symbol": (
                    last["symbol"] != current["symbol"] if last else False
                ),
                "windows": windows,
                "decays": decays,
            }

        enriched = dict(trade)
        enriched.update(
            {
                "symbol": current["symbol"],
                "source_outcome": current["outcome"],
                "afterimages": afterimages,
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
    wins = [value for value in values if value > 0.0]
    losses = [value for value in values if value < 0.0]
    gross_profit = sum(wins)
    gross_loss = -sum(losses)
    mean = statistics.fmean(values) if values else 0.0
    deviation = statistics.pstdev(values) if len(values) > 1 else 0.0
    durations = [trade["duration_minutes"] for trade in trades]
    return {
        "count": len(values),
        "actual_net": rounded(sum(actual_values)),
        "stressed_net": rounded(sum(values)),
        "mean_stressed": rounded(mean),
        "win_rate": rounded(len(wins) / len(values)) if values else None,
        "profit_factor": rounded(gross_profit / gross_loss) if gross_loss > 0.0 else None,
        "gross_loss": rounded(gross_loss),
        "mean_loss": rounded(statistics.fmean(losses)) if losses else None,
        "closed_drawdown": rounded(max_drawdown),
        "net_to_drawdown": rounded(sum(values) / max_drawdown)
        if max_drawdown > 0.0
        else None,
        "sl_rate": rounded(
            sum(trade["close_reason"] == "DEAL_REASON_SL" for trade in trades)
            / len(trades)
        )
        if trades
        else None,
        "mean_duration_minutes": rounded(statistics.fmean(durations))
        if durations
        else None,
    }


def split_metrics(
    selected: list[dict[str, Any]], split_server: int, universe_count: int
) -> dict[str, Any]:
    early = [trade for trade in selected if trade["decision_server"] < split_server]
    late = [trade for trade in selected if trade["decision_server"] >= split_server]
    return {
        "full": lens_metrics(selected),
        "early": lens_metrics(early),
        "late": lens_metrics(late),
        "coverage_pct": rounded(100.0 * len(selected) / universe_count)
        if universe_count
        else None,
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

    for emitter_type in EMITTER_TYPES:
        for window in WINDOWS_MINUTES:
            for relation_name, relation in (("same", 1), ("opposite", -1)):
                add(
                    "last_trace",
                    f"{emitter_type}_last_{relation_name}_{window}m",
                    {
                        "emitter_type": emitter_type,
                        "window_minutes": window,
                        "relation": relation_name,
                    },
                    lambda trade, emitter_type=emitter_type, window=window, relation=relation: (
                        trade["afterimages"][emitter_type]["last_gap_minutes"]
                        is not None
                        and trade["afterimages"][emitter_type]["last_gap_minutes"]
                        <= window
                        and trade["afterimages"][emitter_type]["last_relation"]
                        == relation
                    ),
                )
                add(
                    "cross_symbol_trace",
                    f"{emitter_type}_cross_last_{relation_name}_{window}m",
                    {
                        "emitter_type": emitter_type,
                        "window_minutes": window,
                        "relation": relation_name,
                        "cross_symbol": True,
                    },
                    lambda trade, emitter_type=emitter_type, window=window, relation=relation: (
                        trade["afterimages"][emitter_type]["last_gap_minutes"]
                        is not None
                        and trade["afterimages"][emitter_type]["last_gap_minutes"]
                        <= window
                        and trade["afterimages"][emitter_type]["last_relation"]
                        == relation
                        and trade["afterimages"][emitter_type]["last_cross_symbol"]
                    ),
                )
                add(
                    "same_component_trace",
                    f"{emitter_type}_self_last_{relation_name}_{window}m",
                    {
                        "emitter_type": emitter_type,
                        "window_minutes": window,
                        "relation": relation_name,
                        "same_component": True,
                    },
                    lambda trade, emitter_type=emitter_type, window=window, relation=relation: (
                        trade["afterimages"][emitter_type]["last_gap_minutes"]
                        is not None
                        and trade["afterimages"][emitter_type]["last_gap_minutes"]
                        <= window
                        and trade["afterimages"][emitter_type]["last_relation"]
                        == relation
                        and trade["afterimages"][emitter_type]["last_same_component"]
                    ),
                )

    for emitter_type in EMITTER_TYPES:
        for window in WINDOWS_MINUTES:
            for minimum in (1, 2, 3):
                for relation_name, field in (
                    ("same", "same_direction"),
                    ("opposite", "opposite_direction"),
                ):
                    add(
                        "afterimage_cluster",
                        f"{emitter_type}_{relation_name}_{window}m_n{minimum}",
                        {
                            "emitter_type": emitter_type,
                            "window_minutes": window,
                            "minimum": minimum,
                            "relation": relation_name,
                        },
                        lambda trade, emitter_type=emitter_type, window=window, minimum=minimum, field=field: (
                            trade["afterimages"][emitter_type]["windows"][str(window)][
                                field
                            ]
                            >= minimum
                        ),
                    )

    for emitter_type in EMITTER_TYPES:
        for half_life in HALF_LIVES_MINUTES:
            for minimum_energy in (0.25, 0.5, 1.0, 1.5, 2.0):
                for relation_name, boundary in (("same", 0.25), ("opposite", -0.25)):
                    add(
                        "decaying_charge",
                        f"{emitter_type}_{relation_name}_h{half_life}_e{minimum_energy}",
                        {
                            "emitter_type": emitter_type,
                            "half_life_minutes": half_life,
                            "minimum_energy": minimum_energy,
                            "dominance": boundary,
                        },
                        lambda trade, emitter_type=emitter_type, half_life=half_life, minimum_energy=minimum_energy, relation_name=relation_name: (
                            trade["afterimages"][emitter_type]["decays"][str(half_life)][
                                "energy"
                            ]
                            >= minimum_energy
                            and (
                                trade["afterimages"][emitter_type]["decays"][
                                    str(half_life)
                                ]["dominance"]
                                >= 0.25
                                if relation_name == "same"
                                else trade["afterimages"][emitter_type]["decays"][
                                    str(half_life)
                                ]["dominance"]
                                <= -0.25
                            )
                        ),
                    )

    for emitter_type in ("risk_blocked", "expired_unfilled"):
        for source_component in COMPONENTS:
            for window in (120, 240, 480, 1440, 2880):
                for relation_name, relation in (("same", 1), ("opposite", -1)):
                    add(
                        "source_receiver_transfer",
                        f"{emitter_type}_c{source_component}_{relation_name}_{window}m",
                        {
                            "emitter_type": emitter_type,
                            "source_component": source_component,
                            "window_minutes": window,
                            "relation": relation_name,
                        },
                        lambda trade, emitter_type=emitter_type, source_component=source_component, window=window, relation=relation: (
                            trade["afterimages"][emitter_type]["last_gap_minutes"]
                            is not None
                            and trade["afterimages"][emitter_type]["last_gap_minutes"]
                            <= window
                            and trade["afterimages"][emitter_type]["last_component"]
                            == source_component
                            and trade["afterimages"][emitter_type]["last_relation"]
                            == relation
                        ),
                    )

    for half_life in (60, 120, 240, 480, 1440):
        for relation_name, relation_test in (
            ("aligned_same", lambda risk, expired: risk >= 0.25 and expired >= 0.25),
            (
                "aligned_opposite",
                lambda risk, expired: risk <= -0.25 and expired <= -0.25,
            ),
            ("risk_same_expired_opposite", lambda risk, expired: risk >= 0.25 and expired <= -0.25),
            ("risk_opposite_expired_same", lambda risk, expired: risk <= -0.25 and expired >= 0.25),
        ):
            add(
                "mixed_memory",
                f"{relation_name}_h{half_life}",
                {"half_life_minutes": half_life, "relation": relation_name},
                lambda trade, half_life=half_life, relation_test=relation_test: (
                    trade["afterimages"]["risk_blocked"]["decays"][str(half_life)][
                        "energy"
                    ]
                    >= 0.25
                    and trade["afterimages"]["expired_unfilled"]["decays"][
                        str(half_life)
                    ]["energy"]
                    >= 0.25
                    and relation_test(
                        trade["afterimages"]["risk_blocked"]["decays"][
                            str(half_life)
                        ]["dominance"],
                        trade["afterimages"]["expired_unfilled"]["decays"][
                            str(half_life)
                        ]["dominance"],
                    )
                ),
            )
    return candidates


def score_favorable(metrics: dict[str, Any]) -> float | None:
    full = metrics["full"]
    early = metrics["early"]
    late = metrics["late"]
    if full["count"] < 10 or early["count"] < 3 or late["count"] < 3:
        return None
    floor = min(early["mean_stressed"], late["mean_stressed"])
    if floor <= 0.0:
        return None
    return rounded(floor * math.sqrt(full["count"]))


def score_loss_containment(metrics: dict[str, Any]) -> float | None:
    full = metrics["full"]
    early = metrics["early"]
    late = metrics["late"]
    if full["count"] < 10 or early["count"] < 3 or late["count"] < 3:
        return None
    floor = min(-early["mean_stressed"], -late["mean_stressed"])
    if floor <= 0.0:
        return None
    return rounded(floor * math.sqrt(full["count"]))


def score_stable_drag(metrics: dict[str, Any], base: dict[str, Any]) -> float | None:
    full = metrics["full"]
    if full["count"] < 10 or metrics["early"]["count"] < 3 or metrics["late"]["count"] < 3:
        return None
    early_drag = base["early"]["mean_stressed"] - metrics["early"]["mean_stressed"]
    late_drag = base["late"]["mean_stressed"] - metrics["late"]["mean_stressed"]
    floor = min(early_drag, late_drag)
    if floor <= 0.0:
        return None
    return rounded(floor * math.sqrt(full["count"]))


def candidate_key(receiver: int | None, name: str) -> str:
    return f"receiver={receiver if receiver is not None else 'all'}|{name}"


def evaluate_dataset(
    trades: list[dict[str, Any]], candidates: list[Candidate]
) -> tuple[int, dict[str, Any], dict[str, dict[str, Any]]]:
    split_server = trades[len(trades) // 2]["decision_server"]
    base_by_receiver: dict[str, Any] = {}
    rows: dict[str, dict[str, Any]] = {}
    for receiver in (None, *COMPONENTS.keys()):
        universe = [
            trade
            for trade in trades
            if receiver is None or trade["component"] == receiver
        ]
        base = split_metrics(universe, split_server, len(universe))
        receiver_name = "all" if receiver is None else COMPONENTS[receiver]["name"]
        base_by_receiver[receiver_name] = base
        for family, name, params, predicate in candidates:
            selected = [trade for trade in universe if predicate(trade)]
            metrics = split_metrics(selected, split_server, len(universe))
            key = candidate_key(receiver, name)
            rows[key] = {
                "family": family,
                "name": name,
                "params": params,
                "receiver": receiver,
                "receiver_name": receiver_name,
                "metrics": metrics,
                "favorable_score": score_favorable(metrics),
                "loss_containment_score": score_loss_containment(metrics),
                "stable_drag_score": score_stable_drag(metrics, base),
            }
    return split_server, base_by_receiver, rows


def compact(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "family": row["family"],
        "name": row["name"],
        "params": row["params"],
        "receiver": row["receiver_name"],
        "scores": {
            "favorable": row["favorable_score"],
            "loss_containment": row["loss_containment_score"],
            "stable_drag": row["stable_drag_score"],
        },
        "metrics": row["metrics"],
    }


def emitter_summary(emitters: list[dict[str, Any]]) -> dict[str, Any]:
    by_kind = Counter(emitter["kind"] for emitter in emitters)
    by_kind_component: dict[str, dict[str, int]] = {}
    for kind in ("risk_blocked", "expired_unfilled"):
        by_kind_component[kind] = dict(
            Counter(
                COMPONENTS[emitter["component"]]["name"]
                for emitter in emitters
                if emitter["kind"] == kind
            )
        )
    return {"by_kind": dict(by_kind), "by_kind_component": by_kind_component}


def main() -> None:
    candidates = hypotheses()
    datasets: dict[str, dict[str, Any]] = {}
    for label, source_log in SOURCE_LOGS.items():
        opportunities, events = read_journal(source_log)
        trades, emitters, reconstruction = reconstruct(opportunities, events)
        decorated = decorate_trades(trades, opportunities, emitters)
        split_server, base_by_receiver, rows = evaluate_dataset(decorated, candidates)
        datasets[label] = {
            "source_log": source_log,
            "opportunities": opportunities,
            "events": events,
            "trades": decorated,
            "emitters": emitters,
            "reconstruction": reconstruction,
            "split_server": split_server,
            "base_by_receiver": base_by_receiver,
            "rows": rows,
        }

    primary = datasets["capital_100"]
    primary_rows = list(primary["rows"].values())
    favorable = [row for row in primary_rows if row["favorable_score"] is not None]
    containment = [
        row for row in primary_rows if row["loss_containment_score"] is not None
    ]
    drag = [row for row in primary_rows if row["stable_drag_score"] is not None]
    favorable.sort(key=lambda row: row["favorable_score"], reverse=True)
    containment.sort(key=lambda row: row["loss_containment_score"], reverse=True)
    drag.sort(key=lambda row: row["stable_drag_score"], reverse=True)

    capital_robust: list[dict[str, Any]] = []
    for key, primary_row in primary["rows"].items():
        observations = {
            label: dataset["rows"][key] for label, dataset in datasets.items()
        }
        favorable_scores = [
            row["favorable_score"] for row in observations.values()
        ]
        containment_scores = [
            row["loss_containment_score"] for row in observations.values()
        ]
        drag_scores = [row["stable_drag_score"] for row in observations.values()]
        robust_favorable = (
            min(favorable_scores)
            if all(score is not None for score in favorable_scores)
            else None
        )
        robust_containment = (
            min(containment_scores)
            if all(score is not None for score in containment_scores)
            else None
        )
        robust_drag = (
            min(drag_scores)
            if all(score is not None for score in drag_scores)
            else None
        )
        if robust_favorable is None and robust_containment is None and robust_drag is None:
            continue
        capital_robust.append(
            {
                "family": primary_row["family"],
                "name": primary_row["name"],
                "params": primary_row["params"],
                "receiver": primary_row["receiver_name"],
                "robust_scores": {
                    "favorable": robust_favorable,
                    "loss_containment": robust_containment,
                    "stable_drag": robust_drag,
                },
                "capital_metrics": {
                    label: row["metrics"] for label, row in observations.items()
                },
            }
        )

    robust_favorable = sorted(
        [
            row
            for row in capital_robust
            if row["robust_scores"]["favorable"] is not None
        ],
        key=lambda row: row["robust_scores"]["favorable"],
        reverse=True,
    )
    robust_containment = sorted(
        [
            row
            for row in capital_robust
            if row["robust_scores"]["loss_containment"] is not None
        ],
        key=lambda row: row["robust_scores"]["loss_containment"],
        reverse=True,
    )
    robust_drag = sorted(
        [
            row
            for row in capital_robust
            if row["robust_scores"]["stable_drag"] is not None
        ],
        key=lambda row: row["robust_scores"]["stable_drag"],
        reverse=True,
    )

    family_leaders: dict[str, Any] = {}
    for family in sorted({row["family"] for row in primary_rows}):
        family_leaders[family] = {
            "favorable": next(
                (compact(row) for row in favorable if row["family"] == family),
                None,
            ),
            "loss_containment": next(
                (compact(row) for row in containment if row["family"] == family),
                None,
            ),
            "stable_drag": next(
                (compact(row) for row in drag if row["family"] == family),
                None,
            ),
        }

    outcome_counts = {
        label: dict(Counter(opportunity["outcome"] for opportunity in dataset["opportunities"]))
        for label, dataset in datasets.items()
    }
    document = {
        "unit": "opportunity-afterimage-002",
        "question": "Do blocked and expired-unfilled opportunities leave decaying directional afterimages that change later receiver economics without suppressing base entries?",
        "sources": {
            label: str(dataset["source_log"].relative_to(ROOT)).replace("\\", "/")
            for label, dataset in datasets.items()
        },
        "causality": "Risk-blocked memory begins at its decision second. Expired-unfilled memory begins only when expiration is observed. Receivers use emitters from strictly earlier server seconds.",
        "economic_interpretation": {
            "favorable": "Potential entry-preserving add-on state; no base trade is removed in the proxy.",
            "loss_containment": "Potential receiver-specific protection or exit-geometry state; the entry remains present.",
            "stable_drag": "State underperforms that receiver's own unconditional mean in both temporal halves.",
        },
        "search": {
            "hypotheses": len(candidates),
            "receiver_lenses_per_hypothesis": 1 + len(COMPONENTS),
            "evaluations_per_capital": len(primary_rows),
            "capital_levels": len(datasets),
        },
        "outcome_counts": outcome_counts,
        "capital": {
            label: {
                "counts": {
                    "opportunities": len(dataset["opportunities"]),
                    "events": len(dataset["events"]),
                    "completed_trades": len(dataset["trades"]),
                    "emitters": len(dataset["emitters"]),
                },
                "emitters": emitter_summary(dataset["emitters"]),
                "reconstruction": dataset["reconstruction"],
                "split_server": dataset["split_server"],
                "base_by_receiver": dataset["base_by_receiver"],
            }
            for label, dataset in datasets.items()
        },
        "primary_leaders": {
            "favorable": [compact(row) for row in favorable[:40]],
            "loss_containment": [compact(row) for row in containment[:40]],
            "stable_drag": [compact(row) for row in drag[:40]],
        },
        "capital_robust_leaders": {
            "favorable": robust_favorable[:40],
            "loss_containment": robust_containment[:40],
            "stable_drag": robust_drag[:40],
        },
        "family_leaders": family_leaders,
        "limits": [
            "Afterimage membership is descriptive and causal, but it does not reveal the counterfactual path of a blocked or expired opportunity.",
            "The proxy identifies later receiver states; only an MT5 runtime can determine whether altered protection or exit geometry improves those trades.",
            "Sparse receiver-transfer cells are retained as hypothesis seeds, not treated as validation evidence.",
        ],
    }
    OUTPUT_PATH.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
