from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[4]
FAMILY_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = FAMILY_ROOT / "config" / "contract.json"
COST_COLUMNS = ("gross_usd", "observed_usd", "stressed_usd")
VIEW_NAMES = ("TOM_ALL", "PRE4", "POST4", "ROM", "UNCONDITIONAL")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
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
        return None if not math.isfinite(float(value)) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def verify_inputs(config: dict[str, Any], input_root: Path) -> dict[str, Any]:
    lines: list[str] = []
    files: list[dict[str, Any]] = []
    for expected in sorted(config["immutable_inputs"]["files"], key=lambda item: item["name"]):
        path = input_root / expected["name"]
        if not path.is_file():
            raise RuntimeError(f"missing frozen input: {path}")
        size = path.stat().st_size
        digest = sha256_file(path)
        if size != expected["bytes"] or digest != expected["sha256"]:
            raise RuntimeError(f"frozen input mismatch: {expected['name']}")
        lines.append(f"{expected['name']}|{size}|{digest}")
        files.append({"name": expected["name"], "bytes": size, "sha256": digest})
    manifest = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest().upper()
    if manifest != config["immutable_inputs"]["manifest_sha256"]:
        raise RuntimeError("frozen input manifest mismatch")
    return {"manifest_sha256": manifest, "files": files}


def verify_declaration(config: dict[str, Any]) -> dict[str, Any]:
    expected = config.get("formal_declaration", {})
    if not expected.get("path") or not expected.get("bytes") or not expected.get("sha256"):
        raise RuntimeError("formal declaration pin is not frozen")
    path = REPO_ROOT / expected["path"]
    if not path.is_file():
        raise RuntimeError(f"formal declaration missing: {path}")
    size = path.stat().st_size
    digest = sha256_file(path)
    if size != expected["bytes"] or digest != expected["sha256"]:
        raise RuntimeError("formal declaration pin mismatch")
    return {"path": expected["path"], "bytes": size, "sha256": digest}


def period_name(date: pd.Timestamp, config: dict[str, Any]) -> str | None:
    for name, boundary in config["periods"].items():
        if pd.Timestamp(boundary["from_inclusive"]) <= date < pd.Timestamp(boundary["to_exclusive"]):
            return name
    return None


def split_name(date: pd.Timestamp, config: dict[str, Any]) -> str | None:
    for name, boundary in config["p1_splits"].items():
        if pd.Timestamp(boundary[0]) <= date < pd.Timestamp(boundary[1]):
            return name
    return None


def load_calendar(
    config: dict[str, Any], input_root: Path, formal: bool
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    path = input_root / config["files"]["bars"]
    header = pd.read_csv(path, nrows=0)
    required = config["required_bar_schema"]
    if list(header.columns) != required:
        raise RuntimeError(f"unexpected bar schema: {list(header.columns)}")
    usecols = required if formal else ["time_epoch", "time_server"]
    frame = pd.read_csv(path, usecols=usecols)
    if len(frame) != config["immutable_inputs"]["bar_rows"]:
        raise RuntimeError("bar row count mismatch")
    if frame.isna().any().any():
        raise RuntimeError("loaded bar fields contain null values")
    epoch = frame["time_epoch"].astype(np.int64)
    if epoch.duplicated().any() or not epoch.is_monotonic_increasing:
        raise RuntimeError("bar epochs are not unique and increasing")
    if formal:
        if (frame[["open", "high", "low", "close"]] <= 0.0).any().any():
            raise RuntimeError("bar surface contains nonpositive prices")
        if (frame["spread"] < 0).any():
            raise RuntimeError("bar surface contains a negative spread")

    utc = pd.to_datetime(epoch, unit="s", utc=True)
    et = utc.dt.tz_convert(config["calendar_rule"]["timezone"])
    mask = (et.dt.weekday < 5) & (
        ((et.dt.hour == 9) & (et.dt.minute >= 30))
        | ((et.dt.hour >= 10) & (et.dt.hour < 16))
    )
    selected_columns = ["time_epoch"]
    if formal:
        selected_columns += ["open", "high", "low", "close", "spread"]
    cash = frame.loc[mask, selected_columns].copy()
    cash["utc"] = utc.loc[cash.index]
    cash["et"] = et.loc[cash.index]
    cash["date"] = cash["et"].dt.tz_localize(None).dt.normalize()
    cash["minute_of_day"] = cash["et"].dt.hour * 60 + cash["et"].dt.minute

    expected_minutes = list(range(9 * 60 + 30, 16 * 60, 15))
    entry_minute = expected_minutes[0]
    exit_minute = expected_minutes[-1]
    inventory_rows: list[dict[str, Any]] = []
    session_rows: list[dict[str, Any]] = []
    for date, group in cash.groupby("date", sort=True):
        ordered = group.sort_values("minute_of_day", kind="stable")
        minutes = ordered["minute_of_day"].astype(int).tolist()
        full_bar_geometry = minutes == expected_minutes
        boundary_eligible = minutes.count(entry_minute) == 1 and minutes.count(exit_minute) == 1
        inventory_rows.append(
            {
                "date": date,
                "observed_cash_bars": int(len(ordered)),
                "full_bar_geometry": bool(full_bar_geometry),
                "complete": bool(boundary_eligible),
            }
        )
        if not boundary_eligible:
            continue
        entry_row = ordered.loc[ordered["minute_of_day"] == entry_minute].iloc[0]
        exit_row = ordered.loc[ordered["minute_of_day"] == exit_minute].iloc[0]
        row: dict[str, Any] = {
            "date": date,
            "entry_utc": entry_row["utc"],
            "exit_utc": exit_row["utc"] + pd.Timedelta(minutes=15),
        }
        if formal:
            row.update(
                {
                    "entry_bid": float(entry_row["open"]),
                    "exit_bid": float(exit_row["close"]),
                    "entry_spread_points": int(entry_row["spread"]),
                    "exit_spread_points": int(exit_row["spread"]),
                }
            )
        session_rows.append(row)

    inventory = pd.DataFrame(inventory_rows).sort_values("date", kind="stable").reset_index(drop=True)
    sessions = pd.DataFrame(session_rows).sort_values("date", kind="stable").reset_index(drop=True)
    if inventory.empty or sessions.empty:
        raise RuntimeError("cash-session calendar is empty")
    return sessions, inventory, {
        "bar_rows": int(len(frame)),
        "first_utc": utc.iloc[0].isoformat(),
        "last_utc": utc.iloc[-1].isoformat(),
        "observed_cash_session_dates": int(len(inventory)),
        "trade_boundary_eligible_cash_sessions": int(len(sessions)),
        "trade_boundary_ineligible_cash_session_dates": int((~inventory["complete"]).sum()),
        "full_26_bar_cash_sessions": int(inventory["full_bar_geometry"].sum()),
        "non_full_26_bar_cash_session_dates": int((~inventory["full_bar_geometry"]).sum()),
        "first_observed_date": inventory["date"].iloc[0].date().isoformat(),
        "last_observed_date": inventory["date"].iloc[-1].date().isoformat(),
        "first_trade_boundary_eligible_date": sessions["date"].iloc[0].date().isoformat(),
        "last_trade_boundary_eligible_date": sessions["date"].iloc[-1].date().isoformat(),
        "full_bar_geometry_count": len(expected_minutes),
        "price_or_spread_fields_loaded": formal,
    }


def assign_calendar_roles(
    sessions: pd.DataFrame, inventory: pd.DataFrame, config: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    calendar_config = config["official_session_calendar"]
    closed_dates = pd.to_datetime(calendar_config["closed_dates"])
    if closed_dates.duplicated().any():
        raise RuntimeError("official closure calendar contains duplicate dates")
    if any(date.weekday() >= 5 for date in closed_dates):
        raise RuntimeError("official closure calendar contains a weekend date")
    first_observed = inventory["date"].min()
    last_observed = inventory["date"].max()
    weekday_dates = pd.date_range(first_observed, last_observed, freq="B")
    active_closed = closed_dates[(closed_dates >= first_observed) & (closed_dates <= last_observed)]
    official_dates = weekday_dates[~weekday_dates.isin(active_closed)]
    ranked = pd.DataFrame({"date": official_dates})
    ranked = ranked.merge(inventory, on="date", how="left", validate="one_to_one")
    ranked["observed_cash_bars"] = ranked["observed_cash_bars"].fillna(0).astype(int)
    ranked["full_bar_geometry"] = ranked["full_bar_geometry"].astype("boolean").fillna(False).astype(bool)
    ranked["complete"] = ranked["complete"].astype("boolean").fillna(False).astype(bool)
    official_date_set = set(official_dates)
    unofficial_observed = inventory.loc[~inventory["date"].isin(official_date_set)].copy()
    ranked["month"] = ranked["date"].dt.to_period("M").astype(str)
    ranked["role"] = "ROM"
    month_counts: dict[str, int] = {}
    for month, group in ranked.groupby("month", sort=True):
        ordered = group.sort_values("date", kind="stable")
        count = int(len(ordered))
        month_counts[str(month)] = count
        if count <= 8:
            raise RuntimeError(f"calendar month has no disjoint PRE4/POST4 roles: {month}")
        post_indices = ordered.index[:4]
        pre_indices = ordered.index[-4:]
        if set(post_indices).intersection(set(pre_indices)):
            raise RuntimeError(f"calendar role overlap: {month}")
        ranked.loc[post_indices, "role"] = "POST4"
        ranked.loc[pre_indices, "role"] = "PRE4"
    ranked["period"] = ranked["date"].map(lambda value: period_name(value, config))
    ranked["split"] = ranked["date"].map(lambda value: split_name(value, config))
    ranked["declared"] = ranked["period"].notna()

    role_columns = ["date", "month", "role", "period", "split", "complete"]
    joined = ranked[role_columns].merge(sessions, on="date", how="left", validate="one_to_one")
    eligible = joined.loc[joined["complete"]].copy()
    if eligible[["entry_utc", "exit_utc"]].isna().any().any():
        raise RuntimeError("official complete session lacks trade boundary fields")
    declared = eligible.loc[eligible["period"].notna()].copy().reset_index(drop=True)
    primary = declared.loc[declared["role"].isin(["PRE4", "POST4"])].copy()
    if primary.empty:
        raise RuntimeError("no declared turn-of-month sessions")

    period_counts = {
        name: int((primary["period"] == name).sum()) for name in config["periods"]
    }
    role_period_counts = {
        role: {
            name: int(((primary["role"] == role) & (primary["period"] == name)).sum())
            for name in config["periods"]
        }
        for role in ("PRE4", "POST4")
    }
    split_counts = {
        name: int((primary["split"] == name).sum()) for name in config["p1_splits"]
    }
    minimums = config["economic_gates"]["minimum_primary_days_by_period"]
    density = {name: period_counts[name] >= int(minimums[name]) for name in minimums}
    selected_incomplete = ranked.loc[
        ranked["declared"] & ranked["role"].isin(["PRE4", "POST4"]) & ~ranked["complete"]
    ]
    return declared, ranked, {
        "official_calendar_sources": calendar_config["sources"],
        "official_session_dates": int(len(ranked)),
        "official_calendar_months": int(ranked["month"].nunique()),
        "official_closure_dates_in_observed_range": int(len(active_closed)),
        "official_closure_dates": active_closed.date.astype(str).tolist(),
        "observed_cfd_dates_not_official_sessions": int(len(unofficial_observed)),
        "observed_cfd_dates_not_official_session_dates": unofficial_observed["date"].dt.date.astype(str).tolist(),
        "official_sessions_without_observed_cash_bars": int((ranked["observed_cash_bars"] == 0).sum()),
        "official_sessions_without_trade_boundaries": int(
            ((ranked["observed_cash_bars"] > 0) & ~ranked["complete"]).sum()
        ),
        "official_sessions_without_full_26_bar_geometry": int((~ranked["full_bar_geometry"]).sum()),
        "month_trading_date_counts": month_counts,
        "declared_complete_sessions": int(len(declared)),
        "primary_days": int(len(primary)),
        "primary_days_by_period": period_counts,
        "primary_days_by_role_and_period": role_period_counts,
        "primary_days_by_p1_split": split_counts,
        "selected_boundary_ineligible_days_excluded": int(len(selected_incomplete)),
        "selected_boundary_ineligible_dates": selected_incomplete["date"].dt.date.astype(str).tolist(),
        "selected_boundary_ineligible_details": [
            {
                "date": row.date.date().isoformat(),
                "role": str(row.role),
                "observed_cash_bars": int(row.observed_cash_bars),
            }
            for row in selected_incomplete.itertuples(index=False)
        ],
        "density_checks": density,
        "density_passed": bool(all(density.values())),
    }


def premetric_payload(
    input_integrity: dict[str, Any],
    session_integrity: dict[str, Any],
    calendar_integrity: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": "zeta-next-us500-turn-of-month-cash-session-rebalancing-premetric-v1",
        "status": "COMPLETE_PREDICTOR_ONLY_GEOMETRY_ECONOMICS_UNOPENED",
        "input_integrity": input_integrity,
        "session_integrity": session_integrity,
        "calendar_integrity": calendar_integrity,
        "outcome_firewall": {
            "price_or_spread_fields_loaded": False,
            "entry_to_exit_returns_calculated": False,
            "gross_observed_or_stressed_usd_calculated": False,
            "profit_factor_or_drawdown_calculated": False,
            "gate_or_verdict_calculated": False,
        },
    }


def load_spec(config: dict[str, Any], input_root: Path) -> dict[str, Any]:
    spec = load_json(input_root / config["files"]["spec"])
    required = (
        "symbol",
        "point",
        "trade_contract_size",
        "trade_tick_size",
        "trade_tick_value",
        "volume_min",
        "volume_max",
        "volume_step",
    )
    if any(name not in spec for name in required):
        raise RuntimeError("symbol specification lacks required fields")
    if spec["symbol"] != config["trade_rule"]["symbol"]:
        raise RuntimeError("symbol specification mismatch")
    volume = float(config["trade_rule"]["volume"])
    minimum = float(spec["volume_min"])
    maximum = float(spec["volume_max"])
    step = float(spec["volume_step"])
    if volume < minimum or volume > maximum:
        raise RuntimeError("declared volume is outside the symbol volume range")
    step_units = (volume - minimum) / step
    if abs(step_units - round(step_units)) > 1e-9:
        raise RuntimeError("declared volume is not aligned to the symbol volume step")
    point = float(spec["point"])
    contract_size = float(spec["trade_contract_size"])
    tick_size = float(spec["trade_tick_size"])
    tick_value = float(spec["trade_tick_value"])
    if point <= 0.0 or contract_size <= 0.0 or tick_size <= 0.0 or tick_value <= 0.0:
        raise RuntimeError("symbol specification contains a nonpositive economic field")
    if abs(tick_size * contract_size - tick_value) > 1e-10:
        raise RuntimeError("symbol tick-value identity mismatch")
    return {
        **spec,
        "contract_size": contract_size,
        "tick_value": tick_value,
        "minimum_volume": minimum,
    }


def build_trades(declared: pd.DataFrame, spec: dict[str, Any], config: dict[str, Any]) -> pd.DataFrame:
    trades = declared.copy().sort_values("date", kind="stable").reset_index(drop=True)
    point = float(spec["point"])
    contract_size = float(spec["contract_size"])
    volume = float(config["trade_rule"]["volume"])
    entry_spread_usd = trades["entry_spread_points"].astype(float) * point * contract_size * volume
    exit_spread_usd = trades["exit_spread_points"].astype(float) * point * contract_size * volume
    entry_mid = trades["entry_bid"].astype(float) + 0.5 * trades["entry_spread_points"].astype(float) * point
    exit_mid = trades["exit_bid"].astype(float) + 0.5 * trades["exit_spread_points"].astype(float) * point
    gross = (exit_mid - entry_mid) * contract_size * volume
    observed = (
        trades["exit_bid"].astype(float)
        - (trades["entry_bid"].astype(float) + trades["entry_spread_points"].astype(float) * point)
    ) * contract_size * volume
    observed_identity = gross - 0.5 * (entry_spread_usd + exit_spread_usd)
    if float(np.max(np.abs(observed.to_numpy() - observed_identity.to_numpy()))) > 1e-10:
        raise RuntimeError("observed bid/ask identity mismatch")
    stressed = gross - (entry_spread_usd + exit_spread_usd)
    trades["entry_mid"] = entry_mid
    trades["exit_mid"] = exit_mid
    trades["gross_usd"] = gross
    trades["observed_usd"] = observed
    trades["stressed_usd"] = stressed
    trades["entry_spread_usd"] = entry_spread_usd
    trades["exit_spread_usd"] = exit_spread_usd
    trades["calendar_month"] = trades["date"].dt.strftime("%Y-%m")
    columns = [
        "date",
        "month",
        "calendar_month",
        "role",
        "period",
        "split",
        "entry_utc",
        "exit_utc",
        "entry_bid",
        "exit_bid",
        "entry_mid",
        "exit_mid",
        "entry_spread_points",
        "exit_spread_points",
        "entry_spread_usd",
        "exit_spread_usd",
        "gross_usd",
        "observed_usd",
        "stressed_usd",
    ]
    return trades[columns]


def series_metrics(values: pd.Series | np.ndarray, starting_balance: float) -> dict[str, Any]:
    array = np.asarray(values, dtype=float)
    count = int(len(array))
    if count == 0:
        return {
            "count": 0,
            "net_usd": 0.0,
            "gross_profit_usd": 0.0,
            "gross_loss_usd": 0.0,
            "profit_factor": None,
            "win_rate": None,
            "mean_usd": None,
            "standard_deviation_usd": None,
            "mean_to_standard_deviation": None,
            "max_closed_drawdown_usd": 0.0,
            "max_closed_drawdown_percent": 0.0,
            "net_to_drawdown": None,
        }
    gross_profit = float(array[array > 0.0].sum()) if np.any(array > 0.0) else 0.0
    gross_loss = float(array[array < 0.0].sum()) if np.any(array < 0.0) else 0.0
    net = float(array.sum())
    profit_factor = gross_profit / abs(gross_loss) if gross_loss < 0.0 else None
    mean = float(array.mean())
    standard_deviation = float(array.std(ddof=1)) if count > 1 else 0.0
    mean_to_standard_deviation = mean / standard_deviation if standard_deviation > 0.0 else None
    balance = float(starting_balance)
    peak = balance
    max_drawdown = 0.0
    for value in array:
        balance += float(value)
        peak = max(peak, balance)
        max_drawdown = max(max_drawdown, peak - balance)
    net_to_drawdown = net / max_drawdown if max_drawdown > 0.0 else None
    return {
        "count": count,
        "net_usd": net,
        "gross_profit_usd": gross_profit,
        "gross_loss_usd": gross_loss,
        "profit_factor": profit_factor,
        "win_rate": float((array > 0.0).mean()),
        "mean_usd": mean,
        "standard_deviation_usd": standard_deviation,
        "mean_to_standard_deviation": mean_to_standard_deviation,
        "max_closed_drawdown_usd": max_drawdown,
        "max_closed_drawdown_percent": 100.0 * max_drawdown / float(starting_balance),
        "net_to_drawdown": net_to_drawdown,
    }


def summarize_slice(frame: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    starting_balance = float(config["trade_rule"]["starting_balance_usd"])
    return {
        cost.replace("_usd", ""): series_metrics(frame[cost], starting_balance)
        for cost in COST_COLUMNS
    }


def select_view(trades: pd.DataFrame, name: str) -> pd.DataFrame:
    if name == "TOM_ALL":
        return trades.loc[trades["role"].isin(["PRE4", "POST4"])].copy()
    if name in ("PRE4", "POST4", "ROM"):
        return trades.loc[trades["role"] == name].copy()
    if name == "UNCONDITIONAL":
        return trades.copy()
    raise RuntimeError(f"unknown view: {name}")


def build_views(trades: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    views: dict[str, Any] = {}
    for name in VIEW_NAMES:
        selected = select_view(trades, name).sort_values("date", kind="stable")
        periods = {
            period: summarize_slice(selected.loc[selected["period"] == period], config)
            for period in config["periods"]
        }
        splits = {
            split: summarize_slice(selected.loc[selected["split"] == split], config)
            for split in config["p1_splits"]
        }
        month_nets = (
            selected.groupby("calendar_month", sort=True)["stressed_usd"].sum().astype(float).to_dict()
        )
        views[name] = {
            "full": summarize_slice(selected, config),
            "periods": periods,
            "splits": splits,
            "stressed_month_nets": month_nets,
        }
    return views


def metric_value(metric: dict[str, Any], key: str, default: float = float("-inf")) -> float:
    value = metric.get(key)
    return default if value is None else float(value)


def evaluate_gates(
    trades: pd.DataFrame, views: dict[str, Any], config: dict[str, Any], calendar_integrity: dict[str, Any]
) -> dict[str, Any]:
    gates = config["economic_gates"]
    p1_name = gates["p1_period"]
    latest_name = gates["latest_period"]
    primary = views["TOM_ALL"]
    p1 = primary["periods"][p1_name]["stressed"]
    p1_splits = {
        name: metric_value(primary["splits"][name]["stressed"], "net_usd") > 0.0
        for name in config["p1_splits"]
    }
    p1_roles = {
        role: metric_value(views[role]["periods"][p1_name]["stressed"], "net_usd") > 0.0
        for role in ("PRE4", "POST4")
    }
    p1_mean = metric_value(p1, "mean_usd")
    p1_rom_mean = metric_value(views["ROM"]["periods"][p1_name]["stressed"], "mean_usd")
    p1_unconditional_mean = metric_value(
        views["UNCONDITIONAL"]["periods"][p1_name]["stressed"], "mean_usd"
    )
    p1_checks = {
        "net_positive": metric_value(p1, "net_usd") > 0.0,
        "profit_factor": metric_value(p1, "profit_factor") >= float(gates["p1_profit_factor_min"]),
        "net_to_drawdown": metric_value(p1, "net_to_drawdown") >= float(gates["p1_net_to_drawdown_min"]),
        "positive_splits": sum(p1_splits.values()) >= int(gates["p1_positive_splits_required"]),
        "positive_roles": sum(p1_roles.values()) >= int(gates["p1_positive_roles_required"]),
        "mean_above_rom": p1_mean > p1_rom_mean,
        "mean_above_unconditional": p1_mean > p1_unconditional_mean,
    }

    confirmation_periods = gates["confirmation_periods"]
    confirmation_net_checks: dict[str, bool] = {}
    confirmation_mean_checks: dict[str, bool] = {}
    role_period_checks: dict[str, bool] = {}
    for period in confirmation_periods:
        primary_metric = primary["periods"][period]["stressed"]
        rom_metric = views["ROM"]["periods"][period]["stressed"]
        confirmation_net_checks[period] = metric_value(primary_metric, "net_usd") > 0.0
        confirmation_mean_checks[period] = metric_value(primary_metric, "mean_usd") > metric_value(
            rom_metric, "mean_usd"
        )
        for role in ("PRE4", "POST4"):
            role_period_checks[f"{role}:{period}"] = (
                metric_value(views[role]["periods"][period]["stressed"], "net_usd") > 0.0
            )
    confirmation_checks = {
        "positive_periods": sum(confirmation_net_checks.values())
        >= int(gates["confirmation_positive_periods_required"]),
        "positive_role_period_cells": sum(role_period_checks.values())
        >= int(gates["confirmation_positive_role_period_cells_required"]),
        "mean_above_rom_periods": sum(confirmation_mean_checks.values())
        >= int(gates["confirmation_mean_above_rom_periods_required"]),
    }

    prelatest_frame = select_view(trades.loc[trades["period"] != latest_name], "TOM_ALL").sort_values(
        "date", kind="stable"
    )
    prelatest = summarize_slice(prelatest_frame, config)["stressed"]
    prelatest_rom = summarize_slice(
        trades.loc[(trades["period"] != latest_name) & (trades["role"] == "ROM")], config
    )["stressed"]
    prelatest_unconditional = summarize_slice(trades.loc[trades["period"] != latest_name], config)["stressed"]
    month_nets = prelatest_frame.groupby("calendar_month", sort=True)["stressed_usd"].sum()
    positive_months = int((month_nets > 0.0).sum())
    active_months = int(len(month_nets))
    positive_days = prelatest_frame.loc[prelatest_frame["stressed_usd"] > 0.0, "stressed_usd"].sort_values(
        ascending=False
    )
    positive_day_sum = float(positive_days.sum())
    top_five_positive_day_share = (
        float(positive_days.head(5).sum()) / positive_day_sum if positive_day_sum > 0.0 else None
    )
    prelatest_common = {
        "net_positive": metric_value(prelatest, "net_usd") > 0.0,
        "profit_factor": metric_value(prelatest, "profit_factor") >= float(gates["prelatest_profit_factor_min"]),
        "net_to_drawdown": metric_value(prelatest, "net_to_drawdown")
        >= float(gates["prelatest_net_to_drawdown_min"]),
        "positive_month_fraction": active_months > 0
        and positive_months / active_months >= float(gates["prelatest_positive_month_fraction_min"]),
        "top_five_positive_day_share": top_five_positive_day_share is not None
        and top_five_positive_day_share <= float(gates["prelatest_top_five_positive_day_share_max"]),
        "mean_above_rom": metric_value(prelatest, "mean_usd") > metric_value(prelatest_rom, "mean_usd"),
        "mean_above_unconditional": metric_value(prelatest, "mean_usd")
        > metric_value(prelatest_unconditional, "mean_usd"),
    }
    prelatest_nominal_dd = metric_value(prelatest, "max_closed_drawdown_percent", float("inf")) <= float(
        gates["nominal_drawdown_max_percent"]
    )
    prelatest_practical_dd = metric_value(prelatest, "max_closed_drawdown_percent", float("inf")) <= float(
        gates["practical_drawdown_max_percent"]
    )

    latest = primary["periods"][latest_name]["stressed"]
    latest_net = metric_value(latest, "net_usd")
    positive_prelatest_mean = max(metric_value(prelatest, "mean_usd", 0.0), 0.0)
    latest_practical_floor = -float(gates["latest_practical_reversal_fraction"]) * positive_prelatest_mean * int(
        latest["count"]
    )
    latest_nominal = latest_net >= float(gates["latest_nominal_floor_usd"])
    latest_practical = latest_net >= latest_practical_floor

    full = primary["full"]["stressed"]
    full_checks = {
        "net_positive": metric_value(full, "net_usd") > 0.0,
        "profit_factor": metric_value(full, "profit_factor") >= float(gates["full_profit_factor_min"]),
        "net_to_drawdown": metric_value(full, "net_to_drawdown") >= float(gates["full_net_to_drawdown_min"]),
    }
    density_passed = bool(calendar_integrity["density_passed"])
    common_pass = (
        density_passed
        and all(p1_checks.values())
        and all(confirmation_checks.values())
        and all(prelatest_common.values())
        and all(full_checks.values())
    )
    nominal_pass = common_pass and prelatest_nominal_dd and latest_nominal
    practical_pass = common_pass and prelatest_practical_dd and latest_practical
    confirmation_positive_periods = int(sum(confirmation_net_checks.values()))
    strong_null = (
        metric_value(p1, "net_usd") <= 0.0
        and confirmation_positive_periods <= 1
        and metric_value(prelatest, "net_usd") <= 0.0
        and metric_value(full, "net_usd") <= 0.0
    )
    if nominal_pass:
        verdict = "PASS_RETAIN_ONE_FIXED_US500_TURN_OF_MONTH_CASH_SESSION_SEED"
    elif practical_pass:
        verdict = "PASS_PRACTICAL_MARGINAL_LATEST_OR_DD_RETAIN_ONE_FIXED_US500_TURN_OF_MONTH_CASH_SESSION_SEED"
    elif strong_null:
        verdict = "VALID_NO_US500_TURN_OF_MONTH_CASH_SESSION_EFFECT_AFTER_COST_NO_SEED"
    else:
        verdict = "AMBIGUOUS_US500_TURN_OF_MONTH_CASH_SESSION_TRANSFER_NO_SEED"
    retained_seed = (
        "FIXED_LAST4_FIRST4_US500_CASH_SESSION_LONG" if nominal_pass or practical_pass else None
    )
    return {
        "density": calendar_integrity["density_checks"],
        "p1": p1_checks,
        "p1_splits": p1_splits,
        "p1_roles": p1_roles,
        "confirmation": {
            "period_net_positive": confirmation_net_checks,
            "mean_above_rom": confirmation_mean_checks,
            "role_period_net_positive": role_period_checks,
            "summary": confirmation_checks,
        },
        "prelatest": {
            "metrics": prelatest,
            "rom_control": prelatest_rom,
            "unconditional_control": prelatest_unconditional,
            "positive_months": positive_months,
            "active_months": active_months,
            "positive_month_fraction": positive_months / active_months if active_months else None,
            "top_five_positive_day_share": top_five_positive_day_share,
            "common_checks": prelatest_common,
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
        "full": {"metrics": full, "checks": full_checks},
        "nominal_pass": nominal_pass,
        "practical_pass": practical_pass,
        "strong_null": strong_null,
        "passed": bool(nominal_pass or practical_pass),
        "verdict": verdict,
        "retained_seed": retained_seed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze the fixed US500 turn-of-month cash-session rebalancing transfer."
    )
    parser.add_argument("--mode", choices=("premetric", "formal"), required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    config = load_json(CONFIG_PATH)
    input_root = REPO_ROOT / config["input_root"]
    output_root = REPO_ROOT / config["output_root"]
    input_integrity = verify_inputs(config, input_root)

    if args.mode == "premetric":
        sessions, inventory, session_integrity = load_calendar(config, input_root, formal=False)
        _, _, calendar_integrity = assign_calendar_roles(sessions, inventory, config)
        payload = premetric_payload(input_integrity, session_integrity, calendar_integrity)
        payload["elapsed_seconds"] = time.perf_counter() - started
        print(json.dumps(json_safe(payload), indent=2, sort_keys=True))
        return 0

    declaration = verify_declaration(config)
    sessions, inventory, session_integrity = load_calendar(config, input_root, formal=True)
    declared, ranked_calendar, calendar_integrity = assign_calendar_roles(sessions, inventory, config)
    if not calendar_integrity["density_passed"]:
        raise RuntimeError("declared primary density gate failed before economic aggregation")
    spec = load_spec(config, input_root)
    trades = build_trades(declared, spec, config)
    views = build_views(trades, config)
    decision = evaluate_gates(trades, views, config, calendar_integrity)
    payload = {
        "schema": "zeta-next-us500-turn-of-month-cash-session-rebalancing-analysis-v1",
        "status": "COMPLETE_VALID_ECONOMIC_AGGREGATION",
        "input_integrity": input_integrity,
        "declaration": declaration,
        "session_integrity": session_integrity,
        "calendar_integrity": calendar_integrity,
        "trade_integrity": {
            "rows": int(len(trades)),
            "tom_rows": int(trades["role"].isin(["PRE4", "POST4"]).sum()),
            "rom_rows": int((trades["role"] == "ROM").sum()),
            "first_date": trades["date"].iloc[0].date().isoformat(),
            "last_date": trades["date"].iloc[-1].date().isoformat(),
            "zero_entry_spread_rows": int((trades["entry_spread_points"] == 0).sum()),
            "zero_exit_spread_rows": int((trades["exit_spread_points"] == 0).sum()),
        },
        "views": views,
        "decision": decision,
        "elapsed_seconds": time.perf_counter() - started,
    }
    targets = [
        output_root / "analysis-result.json",
        output_root / "trades.csv",
        output_root / "calendar.csv",
    ]
    if any(path.exists() for path in targets):
        raise RuntimeError("formal output target already exists")
    output_root.mkdir(parents=True, exist_ok=True)
    targets[0].write_text(json.dumps(json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    export_trades = trades.copy()
    export_trades["date"] = export_trades["date"].dt.date.astype(str)
    export_trades.to_csv(targets[1], index=False, lineterminator="\n")
    export_calendar = ranked_calendar.copy()
    export_calendar["date"] = export_calendar["date"].dt.date.astype(str)
    export_calendar.to_csv(targets[2], index=False, lineterminator="\n")
    print(json.dumps(json_safe(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
