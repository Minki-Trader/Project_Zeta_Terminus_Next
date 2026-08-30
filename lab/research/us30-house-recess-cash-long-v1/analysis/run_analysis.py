from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[4]
FAMILY_ROOT = SCRIPT_PATH.parents[1]
CONFIG_PATH = FAMILY_ROOT / "config" / "contract.json"
PRIMARY = "FIXED_HOUSE_RECESS_US30_CASH_LONG"
OPEN_CONTROL = "HOUSE_OPEN_LONG"
UNCONDITIONAL = "UNCONDITIONAL_LONG"
VIEWS = (PRIMARY, OPEN_CONTROL, UNCONDITIONAL)
COSTS = ("gross_usd", "observed_usd", "stressed_usd")
REQUIRED_MARKET_COLUMNS = [
    "time",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def semantic_contract_sha256(config: dict[str, Any]) -> str:
    semantic = copy.deepcopy(config)
    semantic.pop("formal_declaration", None)
    payload = json.dumps(semantic, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


def verify_inputs(config: dict[str, Any], input_root: Path) -> dict[str, Any]:
    lines: list[str] = []
    receipts: list[dict[str, Any]] = []
    for expected in sorted(config["immutable_inputs"]["files"], key=lambda item: item["name"]):
        path = input_root / expected["name"]
        if not path.is_file():
            raise RuntimeError(f"missing frozen input: {path}")
        size = path.stat().st_size
        digest = sha256_file(path)
        if size != int(expected["bytes"]) or digest != expected["sha256"]:
            raise RuntimeError(f"frozen input mismatch: {expected['name']}")
        lines.append(f"{expected['name']}|{size}|{digest}")
        receipts.append({"name": expected["name"], "bytes": size, "sha256": digest})
    manifest = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest().upper()
    if manifest != config["immutable_inputs"]["manifest_sha256"]:
        raise RuntimeError("frozen input manifest mismatch")
    return {"manifest_sha256": manifest, "files": receipts}


def verify_pinned_file(expected: dict[str, Any], label: str) -> dict[str, Any]:
    if not expected.get("path") or not expected.get("bytes") or not expected.get("sha256"):
        raise RuntimeError(f"{label} pin is not frozen")
    path = REPO_ROOT / expected["path"]
    if not path.is_file():
        raise RuntimeError(f"{label} missing: {path}")
    size = path.stat().st_size
    digest = sha256_file(path)
    if size != int(expected["bytes"]) or digest != expected["sha256"]:
        raise RuntimeError(f"{label} pin mismatch")
    return {"path": expected["path"], "bytes": size, "sha256": digest}


def verify_declaration(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt = verify_pinned_file(config.get("formal_declaration", {}), "formal declaration")
    declaration = load_json(REPO_ROOT / receipt["path"])
    if declaration.get("semantic_contract_sha256") != semantic_contract_sha256(config):
        raise RuntimeError("formal declaration semantic contract mismatch")
    code_receipt = verify_pinned_file(declaration.get("analysis_code", {}), "analysis code")
    actual_path = SCRIPT_PATH.relative_to(REPO_ROOT).as_posix()
    if code_receipt["path"] != actual_path:
        raise RuntimeError("formal declaration points to a different analysis code path")
    return receipt, declaration


def period_name(value: pd.Timestamp, config: dict[str, Any]) -> str | None:
    plain = value.tz_localize(None) if value.tzinfo is not None else value
    for name, bounds in config["periods"].items():
        if pd.Timestamp(bounds["from_inclusive"]) <= plain < pd.Timestamp(bounds["to_exclusive"]):
            return name
    return None


def split_name(value: pd.Timestamp, config: dict[str, Any]) -> str | None:
    plain = value.tz_localize(None) if value.tzinfo is not None else value
    for name, bounds in config["p1_splits"].items():
        if pd.Timestamp(bounds[0]) <= plain < pd.Timestamp(bounds[1]):
            return name
    return None


def load_house_schedule(config: dict[str, Any], input_root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    path = input_root / config["files"]["house_schedule"]
    frame = pd.read_csv(path, dtype=str)
    required = [
        "date",
        "announced_next_session_values",
        "congress",
        "session",
        "source_file",
    ]
    if list(frame.columns) != required:
        raise RuntimeError("normalized House schedule schema mismatch")
    if frame.empty or frame["date"].duplicated().any():
        raise RuntimeError("normalized House schedule is empty or duplicated")
    frame["house_date"] = pd.to_datetime(frame["date"], format="%Y%m%d")
    if not frame["house_date"].is_monotonic_increasing:
        raise RuntimeError("normalized House schedule is not monotonic")

    announced: list[pd.Timestamp] = []
    for row in frame.itertuples(index=False):
        current = pd.Timestamp(row.house_date)
        candidates = sorted(
            {
                pd.to_datetime(value[:8], format="%Y%m%d")
                for value in str(row.announced_next_session_values).split(";")
                if value and pd.to_datetime(value[:8], format="%Y%m%d") > current
            }
        )
        if not candidates:
            raise RuntimeError(f"no future announced House date after {row.date}")
        announced.append(candidates[0])
    frame["announced_next_date"] = announced

    chain_faults = 0
    for index in range(len(frame) - 1):
        if frame.iloc[index]["announced_next_date"] != frame.iloc[index + 1]["house_date"]:
            chain_faults += 1
    if chain_faults:
        raise RuntimeError(f"House announced-next chain faults: {chain_faults}")
    return frame, {
        "rows": int(len(frame)),
        "first_date": frame["house_date"].iloc[0].date().isoformat(),
        "last_date": frame["house_date"].iloc[-1].date().isoformat(),
        "duplicate_dates": int(frame["house_date"].duplicated().sum()),
        "announced_next_chain_faults": chain_faults,
    }


def official_dates(config: dict[str, Any]) -> list[pd.Timestamp]:
    calendar = config["official_session_calendar"]
    closed = {pd.Timestamp(value) for value in calendar["closed_dates"]}
    dates = pd.date_range(
        calendar["from_inclusive"],
        pd.Timestamp(calendar["to_exclusive"]) - pd.Timedelta(days=1),
        freq="B",
    )
    return [pd.Timestamp(value) for value in dates if pd.Timestamp(value) not in closed]


def local_epoch(day: pd.Timestamp, hour: int, minute: int, timezone: str) -> int:
    local = pd.Timestamp(
        year=day.year,
        month=day.month,
        day=day.day,
        hour=hour,
        minute=minute,
        tz=timezone,
    )
    return int(local.tz_convert("UTC").timestamp())


def density_integrity(calendar: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    gates = config["economic_gates"]
    matched_config = config["matched_control"]
    period_counts = {
        period: int((calendar["period"] == period).sum()) for period in config["periods"]
    }
    state_counts = {
        period: {
            state: int(((calendar["period"] == period) & (calendar["house_state"] == state)).sum())
            for state in ("HOUSE_RECESS", "HOUSE_OPEN")
        }
        for period in config["periods"]
    }
    split_counts = {
        split: int((calendar["split"] == split).sum()) for split in config["p1_splits"]
    }
    split_recess_counts = {
        split: int(((calendar["split"] == split) & (calendar["house_state"] == "HOUSE_RECESS")).sum())
        for split in config["p1_splits"]
    }
    def dual_state_cells(frame: pd.DataFrame) -> int:
        return int(
            sum(
                set(cell["house_state"]) == {"HOUSE_RECESS", "HOUSE_OPEN"}
                for _, cell in frame.groupby(["calendar_month", "weekday_number"], sort=True)
            )
        )

    latest_name = gates["latest_period"]
    matched_cells = {
        "full": dual_state_cells(calendar),
        "prelatest": dual_state_cells(calendar.loc[calendar["period"] != latest_name]),
        "periods": {
            period: dual_state_cells(calendar.loc[calendar["period"] == period])
            for period in config["periods"]
        },
    }
    checks: dict[str, bool] = {}
    for period, minimum in gates["minimum_eligible_days_by_period"].items():
        checks[f"eligible_{period}"] = period_counts[period] >= int(minimum)
    for period, minima in gates["minimum_state_days_by_period"].items():
        for state, minimum in minima.items():
            checks[f"state_{period}_{state}"] = state_counts[period][state] >= int(minimum)
    for split, minimum in gates["minimum_p1_days_by_split"].items():
        checks[f"split_{split}"] = split_counts[split] >= int(minimum)
    for split, minimum in gates["minimum_p1_recess_days_by_split"].items():
        checks[f"split_recess_{split}"] = split_recess_counts[split] >= int(minimum)
    checks["causal_notice_lead_positive"] = bool((calendar["notice_lead_calendar_days"] >= 1).all())
    checks["house_membership_crosscheck"] = bool(calendar["membership_crosscheck"].all())
    checks["period_complete"] = bool(calendar["period"].notna().all())
    checks["matched_cells_full"] = matched_cells["full"] >= int(
        matched_config["minimum_dual_state_cells_full"]
    )
    checks["matched_cells_p1"] = matched_cells["periods"][gates["p1_period"]] >= int(
        matched_config["minimum_dual_state_cells_p1"]
    )
    for period in gates["confirmation_periods"]:
        checks[f"matched_cells_{period}"] = matched_cells["periods"][period] >= int(
            matched_config["minimum_dual_state_cells_confirmation_period"]
        )
    checks["matched_cells_latest"] = matched_cells["periods"][latest_name] >= int(
        matched_config["minimum_dual_state_cells_latest"]
    )
    return {
        "eligible_days_by_period": period_counts,
        "state_days_by_period": state_counts,
        "p1_split_days": split_counts,
        "p1_split_recess_days": split_recess_counts,
        "matched_dual_state_cells": matched_cells,
        "notice_lead_calendar_days": {
            "minimum": int(calendar["notice_lead_calendar_days"].min()),
            "maximum": int(calendar["notice_lead_calendar_days"].max()),
        },
        "checks": checks,
        "density_passed": bool(all(checks.values())),
    }


def build_calendar(
    config: dict[str, Any],
    input_root: Path,
    formal: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    schedule, schedule_integrity = load_house_schedule(config, input_root)
    market_path = input_root / config["files"]["bars"]
    columns = REQUIRED_MARKET_COLUMNS if formal else ["time"]
    market = pd.read_parquet(market_path, columns=columns)
    if list(market.columns) != columns:
        raise RuntimeError("US30 M1 schema mismatch")
    if market["time"].isna().any() or market["time"].duplicated().any():
        raise RuntimeError("US30 M1 timestamps are null or duplicated")
    if not market["time"].is_monotonic_increasing:
        raise RuntimeError("US30 M1 timestamps are not monotonic")
    if formal:
        numeric = market[["open", "high", "low", "close", "spread"]].apply(
            pd.to_numeric, errors="coerce"
        )
        if numeric.isna().any().any():
            raise RuntimeError("US30 M1 formal price surface is nonnumeric")
        if (numeric[["open", "high", "low", "close"]] <= 0.0).any().any():
            raise RuntimeError("US30 M1 formal price surface is nonpositive")
        if (numeric["spread"] < 0.0).any():
            raise RuntimeError("US30 M1 formal spread surface is negative")

    epochs = set(int(value) for value in market["time"].to_numpy())
    house_dates = schedule["house_date"].to_numpy(dtype="datetime64[ns]")
    house_membership = set(schedule["house_date"].tolist())
    rows: list[dict[str, Any]] = []
    timezone = config["trade_rule"]["timezone"]
    for day in official_dates(config):
        insertion = int(np.searchsorted(house_dates, np.datetime64(day), side="left"))
        if insertion <= 0:
            raise RuntimeError(f"no prior House legislative date for {day.date()}")
        prior = schedule.iloc[insertion - 1]
        prior_day = pd.Timestamp(prior["house_date"])
        announced_next = pd.Timestamp(prior["announced_next_date"])
        if day > announced_next:
            raise RuntimeError(f"House state was not causally covered on {day.date()}")
        state = "HOUSE_OPEN" if day == announced_next else "HOUSE_RECESS"
        membership = day in house_membership
        membership_crosscheck = membership == (state == "HOUSE_OPEN")
        if not membership_crosscheck:
            raise RuntimeError(f"House direct-membership mismatch on {day.date()}")
        entry_epoch = local_epoch(day, 9, 30, timezone)
        exit_epoch = local_epoch(day, 15, 59, timezone)
        rows.append(
            {
                "date": day,
                "date_iso": day.date().isoformat(),
                "period": period_name(day, config),
                "split": split_name(day, config),
                "calendar_month": day.strftime("%Y-%m"),
                "weekday": day.day_name(),
                "weekday_number": int(day.weekday()),
                "house_state": state,
                "prior_house_date": prior_day.date().isoformat(),
                "announced_next_house_date": announced_next.date().isoformat(),
                "notice_lead_calendar_days": int((day - prior_day).days),
                "membership_crosscheck": membership_crosscheck,
                "entry_epoch": entry_epoch,
                "exit_epoch": exit_epoch,
                "entry_present": entry_epoch in epochs,
                "exit_present": exit_epoch in epochs,
            }
        )
    inventory = pd.DataFrame(rows)
    eligible = inventory.loc[inventory["entry_present"] & inventory["exit_present"]].copy()
    eligible.sort_values("date", inplace=True, kind="stable")
    eligible.reset_index(drop=True, inplace=True)
    density = density_integrity(eligible, config)
    integrity = {
        "official_sessions": int(len(inventory)),
        "eligible_sessions": int(len(eligible)),
        "ineligible_boundary_sessions": int(len(inventory) - len(eligible)),
        "entry_missing_sessions": int((~inventory["entry_present"]).sum()),
        "exit_missing_sessions": int((~inventory["exit_present"]).sum()),
        "market_rows": int(len(market)),
        "first_epoch": int(market["time"].iloc[0]),
        "last_epoch": int(market["time"].iloc[-1]),
        "market_columns_loaded": columns,
        "price_or_spread_fields_loaded": formal,
        "house_schedule": schedule_integrity,
        "density": density,
    }
    return eligible, market, integrity


def premetric_payload(
    config: dict[str, Any],
    input_integrity: dict[str, Any],
    acquisition: dict[str, Any],
    eligibility: pd.DataFrame,
    integrity: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": "zeta-next-us30-house-recess-cash-long-premetric-v1",
        "date": "2026-08-30",
        "status": "COMPLETE_OUTCOME_UNOPENED_GEOMETRY",
        "family": config["family"],
        "semantic_contract_sha256": semantic_contract_sha256(config),
        "input_integrity": input_integrity,
        "acquisition_summary": acquisition,
        "eligibility_integrity": integrity,
        "eligible_surface": {
            "first_date": eligibility["date_iso"].iloc[0],
            "last_date": eligibility["date_iso"].iloc[-1],
            "calendar_months": int(eligibility["calendar_month"].nunique()),
            "weekdays": sorted(eligibility["weekday"].unique().tolist()),
        },
        "outcome_firewall": {
            "price_or_spread_fields_loaded": False,
            "entry_or_exit_price_loaded": False,
            "return_or_pnl_calculated": False,
            "profit_factor_or_drawdown_calculated": False,
            "matched_control_or_economic_gate_calculated": False,
            "verdict_calculated": False,
        },
        "predeclaration_schema_probe_disclosure": {
            "occurred_before_family_open": True,
            "rows_displayed": 4,
            "target_cash_boundary_rows_displayed": 0,
            "house_state_joined": False,
            "return_or_economic_metric_calculated": False,
        },
        "live_master_broker_account_touched": False,
    }


def build_trades(
    eligible: pd.DataFrame, market: pd.DataFrame, config: dict[str, Any]
) -> pd.DataFrame:
    by_epoch = market.set_index("time", verify_integrity=True)
    point = float(config["trade_rule"]["point"])
    multiplier = float(config["trade_rule"]["volume"]) * float(
        config["trade_rule"]["trade_contract_size"]
    )
    rows: list[dict[str, Any]] = []
    for record in eligible.itertuples(index=False):
        entry = by_epoch.loc[int(record.entry_epoch)]
        exit_row = by_epoch.loc[int(record.exit_epoch)]
        entry_bid = float(entry["open"])
        exit_bid = float(exit_row["close"])
        entry_spread_price = float(entry["spread"]) * point
        exit_spread_price = float(exit_row["spread"]) * point
        entry_mid = entry_bid + 0.5 * entry_spread_price
        exit_mid = exit_bid + 0.5 * exit_spread_price
        gross = (exit_mid - entry_mid) * multiplier
        observed = (exit_bid - entry_bid - entry_spread_price) * multiplier
        stressed = gross - (entry_spread_price + exit_spread_price) * multiplier
        identity = gross - 0.5 * (entry_spread_price + exit_spread_price) * multiplier
        if abs(observed - identity) > 1.0e-10:
            raise RuntimeError(f"executable-spread identity mismatch on {record.date_iso}")
        rows.append(
            {
                "date": record.date,
                "date_iso": record.date_iso,
                "period": record.period,
                "split": record.split,
                "calendar_month": record.calendar_month,
                "weekday": record.weekday,
                "weekday_number": record.weekday_number,
                "house_state": record.house_state,
                "prior_house_date": record.prior_house_date,
                "announced_next_house_date": record.announced_next_house_date,
                "notice_lead_calendar_days": record.notice_lead_calendar_days,
                "entry_epoch": int(record.entry_epoch),
                "exit_epoch": int(record.exit_epoch),
                "entry_bid": entry_bid,
                "exit_bid": exit_bid,
                "entry_spread_points": float(entry["spread"]),
                "exit_spread_points": float(exit_row["spread"]),
                "gross_usd": gross,
                "observed_usd": observed,
                "stressed_usd": stressed,
            }
        )
    return pd.DataFrame(rows).sort_values("date", kind="stable").reset_index(drop=True)


def select_view(trades: pd.DataFrame, view: str) -> pd.DataFrame:
    if view == PRIMARY:
        selected = trades.loc[trades["house_state"] == "HOUSE_RECESS"]
    elif view == OPEN_CONTROL:
        selected = trades.loc[trades["house_state"] == "HOUSE_OPEN"]
    elif view == UNCONDITIONAL:
        selected = trades
    else:
        raise RuntimeError(f"unknown view: {view}")
    return selected.copy().sort_values("date", kind="stable")


def series_metrics(values: pd.Series | np.ndarray, starting_balance: float) -> dict[str, Any]:
    array = np.asarray(values, dtype=float)
    if len(array) == 0:
        return {
            "count": 0,
            "net_usd": 0.0,
            "gross_profit_usd": 0.0,
            "gross_loss_usd": 0.0,
            "profit_factor": None,
            "win_rate": None,
            "mean_usd": None,
            "standard_deviation_usd": None,
            "max_closed_drawdown_usd": 0.0,
            "max_closed_drawdown_percent": 0.0,
            "net_to_drawdown": None,
        }
    positive = array[array > 0.0]
    negative = array[array < 0.0]
    gross_profit = float(positive.sum()) if len(positive) else 0.0
    gross_loss = float(negative.sum()) if len(negative) else 0.0
    net = float(array.sum())
    balance = float(starting_balance)
    peak = balance
    maximum_drawdown = 0.0
    for value in array:
        balance += float(value)
        peak = max(peak, balance)
        maximum_drawdown = max(maximum_drawdown, peak - balance)
    return {
        "count": int(len(array)),
        "net_usd": net,
        "gross_profit_usd": gross_profit,
        "gross_loss_usd": gross_loss,
        "profit_factor": gross_profit / abs(gross_loss) if gross_loss < 0.0 else None,
        "win_rate": float((array > 0.0).mean()),
        "mean_usd": float(array.mean()),
        "standard_deviation_usd": float(array.std(ddof=1)) if len(array) > 1 else 0.0,
        "max_closed_drawdown_usd": maximum_drawdown,
        "max_closed_drawdown_percent": 100.0 * maximum_drawdown / starting_balance,
        "net_to_drawdown": net / maximum_drawdown if maximum_drawdown > 0.0 else None,
    }


def summarize(frame: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    start = float(config["trade_rule"]["starting_balance_usd"])
    monthly = frame.groupby("calendar_month", sort=True)["stressed_usd"].sum()
    weekdays = frame.groupby("weekday_number", sort=True)["stressed_usd"].sum()
    positive_days = frame.loc[frame["stressed_usd"] > 0.0, "stressed_usd"].sort_values(
        ascending=False
    )
    positive_sum = float(positive_days.sum())
    return {
        "active_session_days": int(len(frame)),
        "costs": {cost.replace("_usd", ""): series_metrics(frame[cost], start) for cost in COSTS},
        "stressed_month_nets": {str(key): float(value) for key, value in monthly.items()},
        "positive_months": int((monthly > 0.0).sum()),
        "active_months": int(len(monthly)),
        "positive_month_fraction": float((monthly > 0.0).mean()) if len(monthly) else None,
        "stressed_weekday_nets": {str(int(key)): float(value) for key, value in weekdays.items()},
        "positive_weekdays": int((weekdays > 0.0).sum()),
        "top_five_positive_day_share": (
            float(positive_days.head(5).sum()) / positive_sum if positive_sum > 0.0 else None
        ),
    }


def build_views(trades: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    views: dict[str, Any] = {}
    latest = config["economic_gates"]["latest_period"]
    confirmations = set(config["economic_gates"]["confirmation_periods"])
    for view in VIEWS:
        selected = select_view(trades, view)
        views[view] = {
            "full": summarize(selected, config),
            "periods": {
                period: summarize(selected.loc[selected["period"] == period], config)
                for period in config["periods"]
            },
            "splits": {
                split: summarize(selected.loc[selected["split"] == split], config)
                for split in config["p1_splits"]
            },
            "prelatest": summarize(selected.loc[selected["period"] != latest], config),
            "confirmation_pooled": summarize(
                selected.loc[selected["period"].isin(confirmations)], config
            ),
        }
    return views


def matched_summary(frame: pd.DataFrame) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    for (month, weekday), cell in frame.groupby(["calendar_month", "weekday_number"], sort=True):
        states = set(cell["house_state"])
        if states != {"HOUSE_RECESS", "HOUSE_OPEN"}:
            continue
        recess = float(cell.loc[cell["house_state"] == "HOUSE_RECESS", "stressed_usd"].mean())
        opened = float(cell.loc[cell["house_state"] == "HOUSE_OPEN", "stressed_usd"].mean())
        cells.append(
            {
                "calendar_month": str(month),
                "weekday_number": int(weekday),
                "recess_mean_usd": recess,
                "open_mean_usd": opened,
                "difference_usd": recess - opened,
            }
        )
    differences = np.asarray([item["difference_usd"] for item in cells], dtype=float)
    return {
        "dual_state_cells": int(len(cells)),
        "equal_weight_mean_difference_usd": float(differences.mean()) if len(differences) else None,
        "positive_cells": int((differences > 0.0).sum()) if len(differences) else 0,
        "positive_cell_fraction": float((differences > 0.0).mean()) if len(differences) else None,
        "cells": cells,
    }


def build_matched(trades: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    latest = config["economic_gates"]["latest_period"]
    confirmations = set(config["economic_gates"]["confirmation_periods"])
    return {
        "full": matched_summary(trades),
        "periods": {
            period: matched_summary(trades.loc[trades["period"] == period])
            for period in config["periods"]
        },
        "prelatest": matched_summary(trades.loc[trades["period"] != latest]),
        "confirmation_pooled": matched_summary(trades.loc[trades["period"].isin(confirmations)]),
    }


def metric(summary: dict[str, Any], key: str, default: float = float("-inf")) -> float:
    value = summary["costs"]["stressed"].get(key)
    return default if value is None else float(value)


def control_check(
    primary: dict[str, Any], opened: dict[str, Any], unconditional: dict[str, Any]
) -> dict[str, bool]:
    state = metric(primary, "mean_usd") > metric(opened, "mean_usd")
    drift = metric(primary, "net_to_drawdown") > metric(unconditional, "net_to_drawdown")
    return {
        "primary_mean_exceeds_house_open": state,
        "primary_net_to_drawdown_exceeds_unconditional": drift,
        "both": bool(state and drift),
    }


def evaluate_gates(
    trades: pd.DataFrame,
    views: dict[str, Any],
    matched: dict[str, Any],
    config: dict[str, Any],
    density: dict[str, Any],
) -> dict[str, Any]:
    gates = config["economic_gates"]
    matched_config = config["matched_control"]
    p1_name = gates["p1_period"]
    latest_name = gates["latest_period"]
    primary = views[PRIMARY]
    opened = views[OPEN_CONTROL]
    unconditional = views[UNCONDITIONAL]

    p1 = primary["periods"][p1_name]
    p1_control = control_check(
        p1, opened["periods"][p1_name], unconditional["periods"][p1_name]
    )
    p1_matched = matched["periods"][p1_name]
    p1_splits = {
        split: metric(primary["splits"][split], "net_usd") > 0.0
        for split in config["p1_splits"]
    }
    p1_checks = {
        "net_positive": metric(p1, "net_usd") > 0.0,
        "profit_factor": metric(p1, "profit_factor") >= float(gates["p1_profit_factor_min"]),
        "net_to_drawdown": metric(p1, "net_to_drawdown")
        >= float(gates["p1_net_to_drawdown_min"]),
        "all_three_splits_positive": sum(p1_splits.values())
        >= int(gates["p1_positive_splits_required"]),
        "positive_month_fraction": (p1["positive_month_fraction"] or 0.0)
        >= float(gates["p1_positive_month_fraction_min"]),
        "positive_weekday_breadth": int(p1["positive_weekdays"])
        >= int(gates["p1_positive_weekdays_required"]),
        "matched_cells": int(p1_matched["dual_state_cells"])
        >= int(matched_config["minimum_dual_state_cells_p1"]),
        "matched_recess_minus_open_positive": float(
            p1_matched["equal_weight_mean_difference_usd"] or float("-inf")
        )
        > 0.0,
        "control_superiority": p1_control["both"],
    }

    confirmation_net: dict[str, bool] = {}
    confirmation_matched: dict[str, bool] = {}
    confirmation_controls: dict[str, dict[str, bool]] = {}
    confirmation_months: dict[str, bool] = {}
    confirmation_cell_density: dict[str, bool] = {}
    for name in gates["confirmation_periods"]:
        item = primary["periods"][name]
        control = control_check(item, opened["periods"][name], unconditional["periods"][name])
        match = matched["periods"][name]
        confirmation_net[name] = metric(item, "net_usd") > 0.0
        confirmation_matched[name] = float(
            match["equal_weight_mean_difference_usd"] or float("-inf")
        ) > 0.0
        confirmation_controls[name] = control
        confirmation_months[name] = (item["positive_month_fraction"] or 0.0) >= float(
            gates["confirmation_positive_month_fraction_min"]
        )
        confirmation_cell_density[name] = int(match["dual_state_cells"]) >= int(
            matched_config["minimum_dual_state_cells_confirmation_period"]
        )
    pooled = primary["confirmation_pooled"]
    confirmation_checks = {
        "all_periods_positive": sum(confirmation_net.values())
        >= int(gates["confirmation_positive_periods_required"]),
        "matched_positive_periods": sum(confirmation_matched.values())
        >= int(gates["confirmation_matched_positive_periods_required"]),
        "control_superiority_periods": sum(
            value["both"] for value in confirmation_controls.values()
        )
        >= int(gates["confirmation_control_superiority_periods_required"]),
        "positive_month_fraction_periods": sum(confirmation_months.values())
        >= int(gates["confirmation_positive_month_fraction_periods_required"]),
        "all_periods_have_matched_density": all(confirmation_cell_density.values()),
        "pooled_profit_factor": metric(pooled, "profit_factor")
        >= float(gates["confirmation_pooled_profit_factor_min"]),
        "pooled_net_to_drawdown": metric(pooled, "net_to_drawdown")
        >= float(gates["confirmation_pooled_net_to_drawdown_min"]),
    }

    prelatest = primary["prelatest"]
    prelatest_control = control_check(
        prelatest, opened["prelatest"], unconditional["prelatest"]
    )
    prelatest_matched = matched["prelatest"]
    prelatest_checks = {
        "net_positive": metric(prelatest, "net_usd") > 0.0,
        "profit_factor": metric(prelatest, "profit_factor")
        >= float(gates["prelatest_profit_factor_min"]),
        "net_to_drawdown": metric(prelatest, "net_to_drawdown")
        >= float(gates["prelatest_net_to_drawdown_min"]),
        "positive_month_fraction": (prelatest["positive_month_fraction"] or 0.0)
        >= float(gates["prelatest_positive_month_fraction_min"]),
        "top_five_positive_day_share": (
            prelatest["top_five_positive_day_share"] is not None
            and float(prelatest["top_five_positive_day_share"])
            <= float(gates["prelatest_top_five_positive_day_share_max"])
        ),
        "positive_weekday_breadth": int(prelatest["positive_weekdays"])
        >= int(gates["prelatest_positive_weekdays_required"]),
        "matched_cell_density": int(prelatest_matched["dual_state_cells"])
        >= int(matched_config["minimum_dual_state_cells_full"]),
        "matched_recess_minus_open_positive": float(
            prelatest_matched["equal_weight_mean_difference_usd"] or float("-inf")
        )
        > 0.0,
        "control_superiority": prelatest_control["both"],
    }

    latest = primary["periods"][latest_name]
    latest_days = int(latest["active_session_days"])
    positive_prelatest_mean = max(metric(prelatest, "mean_usd", 0.0), 0.0)
    latest_practical_floor = (
        -float(gates["latest_practical_reversal_fraction"])
        * positive_prelatest_mean
        * latest_days
    )
    latest_nominal = metric(latest, "net_usd") >= float(gates["latest_nominal_floor_usd"])
    latest_practical = metric(latest, "net_usd") >= latest_practical_floor

    full = primary["full"]
    full_control = control_check(full, opened["full"], unconditional["full"])
    full_matched = matched["full"]
    full_checks = {
        "net_positive": metric(full, "net_usd") > 0.0,
        "profit_factor": metric(full, "profit_factor") >= float(gates["full_profit_factor_min"]),
        "net_to_drawdown": metric(full, "net_to_drawdown")
        >= float(gates["full_net_to_drawdown_min"]),
        "positive_weekday_breadth": int(full["positive_weekdays"])
        >= int(gates["full_positive_weekdays_required"]),
        "matched_cell_density": int(full_matched["dual_state_cells"])
        >= int(matched_config["minimum_dual_state_cells_full"]),
        "matched_recess_minus_open_positive": float(
            full_matched["equal_weight_mean_difference_usd"] or float("-inf")
        )
        > 0.0,
        "control_superiority": full_control["both"],
    }

    prelatest_nominal_dd = metric(
        prelatest, "max_closed_drawdown_percent", float("inf")
    ) <= float(gates["nominal_drawdown_max_percent"])
    full_nominal_dd = metric(full, "max_closed_drawdown_percent", float("inf")) <= float(
        gates["nominal_drawdown_max_percent"]
    )
    prelatest_practical_dd = metric(
        prelatest, "max_closed_drawdown_percent", float("inf")
    ) <= float(gates["practical_drawdown_max_percent"])
    full_practical_dd = metric(full, "max_closed_drawdown_percent", float("inf")) <= float(
        gates["practical_drawdown_max_percent"]
    )
    common = (
        bool(density["density_passed"])
        and all(p1_checks.values())
        and all(confirmation_checks.values())
        and all(prelatest_checks.values())
        and all(full_checks.values())
    )
    nominal_pass = bool(
        common and prelatest_nominal_dd and full_nominal_dd and latest_nominal
    )
    practical_pass = bool(
        common and prelatest_practical_dd and full_practical_dd and latest_practical
    )
    strong_null = bool(
        metric(p1, "net_usd") <= 0.0
        and sum(confirmation_net.values()) <= 1
        and metric(prelatest, "net_usd") <= 0.0
        and metric(full, "net_usd") <= 0.0
    )
    taxonomy = config["verdict_taxonomy"]
    if nominal_pass:
        verdict = taxonomy["nominal_pass"]
    elif practical_pass:
        verdict = taxonomy["practical_pass"]
    elif strong_null:
        verdict = taxonomy["strong_null"]
    else:
        verdict = taxonomy["other_valid"]
    retained_seed = "FIXED_HOUSE_RECESS_US30_CASH_LONG" if nominal_pass or practical_pass else None
    return {
        "density": density,
        "p1": {
            "metrics": p1,
            "split_net_positive": p1_splits,
            "matched": p1_matched,
            "controls": p1_control,
            "checks": p1_checks,
        },
        "confirmation": {
            "period_net_positive": confirmation_net,
            "period_matched_positive": confirmation_matched,
            "period_controls": confirmation_controls,
            "period_positive_month_fraction": confirmation_months,
            "period_matched_density": confirmation_cell_density,
            "pooled_metrics": pooled,
            "checks": confirmation_checks,
        },
        "prelatest": {
            "metrics": prelatest,
            "matched": prelatest_matched,
            "controls": prelatest_control,
            "checks": prelatest_checks,
            "nominal_drawdown_check": prelatest_nominal_dd,
            "practical_drawdown_check": prelatest_practical_dd,
        },
        "latest": {
            "metrics": latest,
            "nominal_floor_usd": float(gates["latest_nominal_floor_usd"]),
            "practical_floor_usd": latest_practical_floor,
            "nominal_check": latest_nominal,
            "practical_check": latest_practical,
        },
        "full": {
            "metrics": full,
            "matched": full_matched,
            "controls": full_control,
            "checks": full_checks,
            "nominal_drawdown_check": full_nominal_dd,
            "practical_drawdown_check": full_practical_dd,
        },
        "nominal_pass": nominal_pass,
        "practical_pass": practical_pass,
        "strong_null": strong_null,
        "passed": bool(nominal_pass or practical_pass),
        "verdict": verdict,
        "retained_seed": retained_seed,
    }


def output_receipt(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze the frozen House-recess US30 regular-cash long transfer."
    )
    parser.add_argument("--mode", choices=("premetric", "formal"), required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    config = load_json(CONFIG_PATH)
    input_root = REPO_ROOT / config["input_root"]
    output_root = REPO_ROOT / config["output_root"]
    input_integrity = verify_inputs(config, input_root)
    acquisition = verify_pinned_file(config["acquisition_summary"], "acquisition summary")

    if args.mode == "premetric":
        eligible, _, integrity = build_calendar(config, input_root, formal=False)
        payload = premetric_payload(config, input_integrity, acquisition, eligible, integrity)
        payload["elapsed_seconds"] = time.perf_counter() - started
        print(json.dumps(json_safe(payload), indent=2, ensure_ascii=False))
        return 0

    targets = [
        output_root / "analysis-result.json",
        output_root / "trades.csv",
        output_root / "calendar.csv",
    ]
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"formal output root is not empty: {output_root}")
    declaration_receipt, declaration = verify_declaration(config)
    premetric_receipt = verify_pinned_file(
        declaration.get("premetric_receipt", {}), "premetric receipt"
    )
    premetric = load_json(REPO_ROOT / premetric_receipt["path"])
    if premetric.get("semantic_contract_sha256") != semantic_contract_sha256(config):
        raise RuntimeError("premetric semantic contract mismatch")
    if any(bool(value) for value in premetric.get("outcome_firewall", {}).values()):
        raise RuntimeError("premetric outcome firewall was not closed")

    eligible, market, integrity = build_calendar(config, input_root, formal=True)
    prior = premetric["eligibility_integrity"]
    for key in (
        "official_sessions",
        "eligible_sessions",
        "ineligible_boundary_sessions",
        "entry_missing_sessions",
        "exit_missing_sessions",
        "market_rows",
        "first_epoch",
        "last_epoch",
        "house_schedule",
        "density",
    ):
        if json_safe(integrity[key]) != prior[key]:
            raise RuntimeError(f"formal geometry drift from premetric receipt: {key}")

    trades = build_trades(eligible, market, config)
    views = build_views(trades, config)
    matched = build_matched(trades, config)
    evaluation = evaluate_gates(
        trades, views, matched, config, integrity["density"]
    )
    result = {
        "schema": "zeta-next-us30-house-recess-cash-long-analysis-v1",
        "date": "2026-08-30",
        "status": "COMPLETE_VALID_ECONOMIC_AGGREGATION",
        "family": config["family"],
        "semantic_contract_sha256": semantic_contract_sha256(config),
        "input_integrity": input_integrity,
        "acquisition_summary": acquisition,
        "formal_declaration": declaration_receipt,
        "premetric_receipt": premetric_receipt,
        "eligibility_integrity": integrity,
        "economic_identity": {
            "symbol": config["trade_rule"]["symbol"],
            "volume": config["trade_rule"]["volume"],
            "point": config["trade_rule"]["point"],
            "trade_contract_size": config["trade_rule"]["trade_contract_size"],
            "entry": config["trade_rule"]["entry"],
            "exit": config["trade_rule"]["exit"],
            "binding_measure": config["trade_rule"]["binding_measure"],
            "commission_swap_financing_usd": 0.0,
        },
        "views": views,
        "matched_control": matched,
        "evaluation": evaluation,
        "formal_run_count": 1,
        "mt5_calls": 0,
        "strategy_tester_calls": 0,
        "master_terminal_touched": False,
        "broker_account_position_order_deal_calls": 0,
        "elapsed_seconds": time.perf_counter() - started,
    }
    output_root.mkdir(parents=True, exist_ok=False)
    targets[0].write_text(
        json.dumps(json_safe(result), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    trades.drop(columns=["date"]).to_csv(targets[1], index=False, lineterminator="\n")
    eligible.drop(columns=["date"]).to_csv(targets[2], index=False, lineterminator="\n")
    print(
        json.dumps(
            {
                "verdict": evaluation["verdict"],
                "retained_seed": evaluation["retained_seed"],
                "eligible_sessions": integrity["eligible_sessions"],
                "recess_sessions": int((trades["house_state"] == "HOUSE_RECESS").sum()),
                "open_sessions": int((trades["house_state"] == "HOUSE_OPEN").sum()),
                "primary_full": views[PRIMARY]["full"]["costs"],
                "primary_period_stressed": {
                    name: item["costs"]["stressed"]
                    for name, item in views[PRIMARY]["periods"].items()
                },
                "matched_full": matched["full"],
                "evaluation": evaluation,
                "outputs": [output_receipt(path) for path in targets],
                "elapsed_seconds": result["elapsed_seconds"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
