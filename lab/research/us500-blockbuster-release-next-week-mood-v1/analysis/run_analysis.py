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
VIEW_NAMES = ("PRIMARY_COUNT", "SAME_WEEK_COUNT", "ZERO_RELEASE_LONG", "UNCONDITIONAL_LONG")


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


def verify_pinned_file(expected: dict[str, Any], label: str) -> dict[str, Any]:
    if not expected.get("path") or not expected.get("bytes") or not expected.get("sha256"):
        raise RuntimeError(f"{label} pin is not frozen")
    path = REPO_ROOT / expected["path"]
    if not path.is_file():
        raise RuntimeError(f"{label} missing: {path}")
    size = path.stat().st_size
    digest = sha256_file(path)
    if size != expected["bytes"] or digest != expected["sha256"]:
        raise RuntimeError(f"{label} pin mismatch")
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


def load_events(config: dict[str, Any], input_root: Path) -> pd.DataFrame:
    path = input_root / config["files"]["events"]
    events = pd.read_csv(path)
    required = config["required_event_schema"]
    if list(events.columns) != required:
        raise RuntimeError(f"unexpected event schema: {list(events.columns)}")
    if len(events) != int(config["immutable_inputs"]["event_rows"]):
        raise RuntimeError("event row count mismatch")
    if events.isna().any().any():
        raise RuntimeError("event surface contains null values")
    for column in ("release_date", "release_week_monday", "target_week_monday"):
        events[column] = pd.to_datetime(events[column], errors="raise")
    events["opening_theaters"] = pd.to_numeric(events["opening_theaters"], errors="raise").astype(int)
    if (events["opening_theaters"] <= 4000).any():
        raise RuntimeError("event surface violates the strict over-4,000-theater rule")
    if events.duplicated(["release", "release_date"]).any():
        raise RuntimeError("event surface contains a duplicate release identity")
    if not (events["release_week_monday"].dt.weekday == 0).all():
        raise RuntimeError("release weeks are not Monday anchored")
    if not (events["target_week_monday"].dt.weekday == 0).all():
        raise RuntimeError("target weeks are not Monday anchored")
    if not (
        events["target_week_monday"] - events["release_week_monday"] == pd.Timedelta(days=7)
    ).all():
        raise RuntimeError("target week is not exactly one calendar week after release week")
    expected_period = events["target_week_monday"].map(
        lambda value: period_name(value, config) or "OUTSIDE_TARGET"
    )
    if not expected_period.equals(events["target_period"]):
        raise RuntimeError("event target-period classification mismatch")
    return events.sort_values(["release_date", "release"], kind="stable").reset_index(drop=True)


def assign_event_roles(
    sessions: pd.DataFrame,
    inventory: pd.DataFrame,
    events: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    calendar_config = config["official_session_calendar"]
    closed_dates = pd.to_datetime(calendar_config["closed_dates"])
    if closed_dates.duplicated().any():
        raise RuntimeError("official closure calendar contains duplicate dates")
    if any(value.weekday() >= 5 for value in closed_dates):
        raise RuntimeError("official closure calendar contains a weekend date")
    start = min(pd.Timestamp(value["from_inclusive"]) for value in config["periods"].values())
    end_exclusive = max(pd.Timestamp(value["to_exclusive"]) for value in config["periods"].values())
    weekday_dates = pd.date_range(start, end_exclusive - pd.Timedelta(days=1), freq="B")
    active_closed = closed_dates[(closed_dates >= start) & (closed_dates < end_exclusive)]
    official_dates = weekday_dates[~weekday_dates.isin(active_closed)]
    calendar = pd.DataFrame({"date": official_dates})
    calendar = calendar.merge(inventory, on="date", how="left", validate="one_to_one")
    calendar["observed_cash_bars"] = calendar["observed_cash_bars"].fillna(0).astype(int)
    calendar["full_bar_geometry"] = (
        calendar["full_bar_geometry"].astype("boolean").fillna(False).astype(bool)
    )
    calendar["complete"] = calendar["complete"].astype("boolean").fillna(False).astype(bool)
    official_date_set = set(official_dates)
    observed_target = inventory.loc[(inventory["date"] >= start) & (inventory["date"] < end_exclusive)]
    unofficial_observed = observed_target.loc[~observed_target["date"].isin(official_date_set)]
    calendar["period"] = calendar["date"].map(lambda value: period_name(value, config))
    calendar["split"] = calendar["date"].map(lambda value: split_name(value, config))
    calendar["calendar_month"] = calendar["date"].dt.strftime("%Y-%m")
    calendar["week_monday"] = calendar["date"] - pd.to_timedelta(calendar["date"].dt.weekday, unit="D")

    target_events = events.loc[events["target_period"] != "OUTSIDE_TARGET"].copy()
    target_groups = (
        target_events.groupby("target_week_monday", sort=True)
        .agg(
            target_release_count=("release", "size"),
            target_releases=("release", lambda values: " | ".join(values)),
            target_opening_theaters=(
                "opening_theaters",
                lambda values: " | ".join(str(int(value)) for value in values),
            ),
        )
        .reset_index()
        .rename(columns={"target_week_monday": "week_monday"})
    )
    same_week_events = target_events.loc[target_events["release_week_monday"] >= start].copy()
    same_groups = (
        same_week_events.groupby("release_week_monday", sort=True)
        .agg(
            same_week_release_count=("release", "size"),
            same_week_releases=("release", lambda values: " | ".join(values)),
        )
        .reset_index()
        .rename(columns={"release_week_monday": "week_monday"})
    )
    calendar = calendar.merge(target_groups, on="week_monday", how="left", validate="many_to_one")
    calendar = calendar.merge(same_groups, on="week_monday", how="left", validate="many_to_one")
    for column in ("target_release_count", "same_week_release_count"):
        calendar[column] = calendar[column].fillna(0).astype(int)
    for column in ("target_releases", "target_opening_theaters", "same_week_releases"):
        calendar[column] = calendar[column].fillna("")

    joined = calendar.merge(sessions, on="date", how="left", validate="one_to_one")
    declared = joined.loc[joined["complete"]].copy().reset_index(drop=True)
    if declared[["entry_utc", "exit_utc"]].isna().any().any():
        raise RuntimeError("official complete session lacks trade boundary fields")
    primary = declared.loc[declared["target_release_count"] > 0].copy()
    if primary.empty:
        raise RuntimeError("no declared next-week blockbuster sessions")

    target_titles_by_period = {
        name: int((target_events["target_period"] == name).sum()) for name in config["periods"]
    }
    target_weeks_by_period = {
        name: int(
            target_events.loc[target_events["target_period"] == name, "target_week_monday"].nunique()
        )
        for name in config["periods"]
    }
    primary_days_by_period = {
        name: int((primary["period"] == name).sum()) for name in config["periods"]
    }
    primary_tranche_days_by_period = {
        name: int(primary.loc[primary["period"] == name, "target_release_count"].sum())
        for name in config["periods"]
    }
    primary_weeks_by_split = {
        name: int(primary.loc[primary["split"] == name, "week_monday"].nunique())
        for name in config["p1_splits"]
    }
    primary_days_by_split = {
        name: int((primary["split"] == name).sum()) for name in config["p1_splits"]
    }
    gates = config["economic_gates"]
    week_density = {
        name: target_weeks_by_period[name] >= int(gates["minimum_event_weeks_by_period"][name])
        for name in gates["minimum_event_weeks_by_period"]
    }
    day_density = {
        name: primary_days_by_period[name] >= int(gates["minimum_primary_days_by_period"][name])
        for name in gates["minimum_primary_days_by_period"]
    }
    split_density = {
        name: primary_weeks_by_split[name] >= int(gates["minimum_p1_event_weeks_by_split"][name])
        for name in gates["minimum_p1_event_weeks_by_split"]
    }
    source_weeks = set(target_groups["week_monday"])
    observed_primary_weeks = set(primary["week_monday"])
    missing_target_weeks = sorted(source_weeks.difference(observed_primary_weeks))
    selected_incomplete = calendar.loc[(calendar["target_release_count"] > 0) & ~calendar["complete"]]
    density_checks = {
        "event_weeks_by_period": week_density,
        "primary_days_by_period": day_density,
        "p1_event_weeks_by_split": split_density,
        "all_target_weeks_have_eligible_sessions": len(missing_target_weeks) == 0,
    }
    density_passed = (
        all(week_density.values())
        and all(day_density.values())
        and all(split_density.values())
        and not missing_target_weeks
    )
    return declared, calendar, {
        "official_calendar_sources": calendar_config["sources"],
        "official_session_dates": int(len(calendar)),
        "official_closure_dates_in_target_range": int(len(active_closed)),
        "official_closure_dates": active_closed.date.astype(str).tolist(),
        "observed_cfd_dates_not_official_sessions": int(len(unofficial_observed)),
        "observed_cfd_dates_not_official_session_dates": unofficial_observed["date"].dt.date.astype(str).tolist(),
        "official_sessions_without_observed_cash_bars": int((calendar["observed_cash_bars"] == 0).sum()),
        "official_sessions_without_trade_boundaries": int(
            ((calendar["observed_cash_bars"] > 0) & ~calendar["complete"]).sum()
        ),
        "official_sessions_without_full_26_bar_geometry": int((~calendar["full_bar_geometry"]).sum()),
        "declared_complete_sessions": int(len(declared)),
        "source_titles_over_4000": int(len(events)),
        "target_titles": int(len(target_events)),
        "target_titles_by_period": target_titles_by_period,
        "target_event_weeks_by_period": target_weeks_by_period,
        "primary_days": int(len(primary)),
        "primary_days_by_period": primary_days_by_period,
        "primary_tranche_days_by_period": primary_tranche_days_by_period,
        "primary_event_weeks_by_p1_split": primary_weeks_by_split,
        "primary_days_by_p1_split": primary_days_by_split,
        "maximum_release_count_in_one_week": int(primary["target_release_count"].max()),
        "two_release_target_weeks": sorted(
            primary.loc[primary["target_release_count"] == 2, "week_monday"]
            .drop_duplicates()
            .dt.date.astype(str)
            .tolist()
        ),
        "selected_boundary_ineligible_days_excluded": int(len(selected_incomplete)),
        "selected_boundary_ineligible_dates": selected_incomplete["date"].dt.date.astype(str).tolist(),
        "target_weeks_without_any_eligible_session": [value.date().isoformat() for value in missing_target_weeks],
        "density_checks": density_checks,
        "density_passed": bool(density_passed),
    }


def premetric_payload(
    input_integrity: dict[str, Any],
    acquisition_summary: dict[str, Any],
    session_integrity: dict[str, Any],
    event_integrity: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": "zeta-next-us500-blockbuster-release-next-week-mood-premetric-v1",
        "status": "COMPLETE_SOURCE_EVENT_AND_SESSION_GEOMETRY_TARGET_ECONOMICS_UNOPENED",
        "input_integrity": input_integrity,
        "acquisition_summary": acquisition_summary,
        "session_integrity": session_integrity,
        "event_integrity": event_integrity,
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
    maximum_count = int(
        max(trades["target_release_count"].max(), trades["same_week_release_count"].max())
    )
    if volume * maximum_count > float(spec["volume_max"]):
        raise RuntimeError("count-scaled exposure exceeds symbol maximum volume")
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
    columns = [
        "date",
        "calendar_month",
        "week_monday",
        "period",
        "split",
        "target_release_count",
        "target_releases",
        "target_opening_theaters",
        "same_week_release_count",
        "same_week_releases",
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
    tranche_sessions = int(frame["exposure_tranches"].sum()) if len(frame) else 0
    result: dict[str, Any] = {
        "active_session_days": int(len(frame)),
        "tranche_sessions": tranche_sessions,
    }
    for cost in COST_COLUMNS:
        metrics = series_metrics(frame[cost], starting_balance)
        metrics["mean_per_tranche_session_usd"] = (
            metrics["net_usd"] / tranche_sessions if tranche_sessions else None
        )
        result[cost.replace("_usd", "")] = metrics
    return result


def select_view(trades: pd.DataFrame, name: str) -> pd.DataFrame:
    if name == "PRIMARY_COUNT":
        selected = trades.loc[trades["target_release_count"] > 0].copy()
        selected["exposure_tranches"] = selected["target_release_count"].astype(int)
    elif name == "SAME_WEEK_COUNT":
        selected = trades.loc[trades["same_week_release_count"] > 0].copy()
        selected["exposure_tranches"] = selected["same_week_release_count"].astype(int)
    elif name == "ZERO_RELEASE_LONG":
        selected = trades.loc[trades["target_release_count"] == 0].copy()
        selected["exposure_tranches"] = 1
    elif name == "UNCONDITIONAL_LONG":
        selected = trades.copy()
        selected["exposure_tranches"] = 1
    else:
        raise RuntimeError(f"unknown view: {name}")
    for cost in COST_COLUMNS:
        selected[cost] = selected[cost] * selected["exposure_tranches"]
    return selected


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
        month_nets = selected.groupby("calendar_month", sort=True)["stressed_usd"].sum().astype(float).to_dict()
        week_nets = (
            selected.groupby("week_monday", sort=True)["stressed_usd"]
            .sum()
            .rename_axis("week_monday")
        )
        views[name] = {
            "full": summarize_slice(selected, config),
            "periods": periods,
            "splits": splits,
            "stressed_month_nets": month_nets,
            "stressed_week_nets": {
                index.date().isoformat(): float(value) for index, value in week_nets.items()
            },
        }
    return views


def metric_value(metric: dict[str, Any], key: str, default: float = float("-inf")) -> float:
    value = metric.get(key)
    return default if value is None else float(value)


def evaluate_gates(
    trades: pd.DataFrame, views: dict[str, Any], config: dict[str, Any], event_integrity: dict[str, Any]
) -> dict[str, Any]:
    gates = config["economic_gates"]
    p1_name = gates["p1_period"]
    latest_name = gates["latest_period"]
    primary = views["PRIMARY_COUNT"]
    p1 = primary["periods"][p1_name]["stressed"]
    p1_splits = {
        name: metric_value(primary["splits"][name]["stressed"], "net_usd") > 0.0
        for name in config["p1_splits"]
    }
    p1_frame = select_view(trades, "PRIMARY_COUNT")
    p1_frame = p1_frame.loc[p1_frame["period"] == p1_name].copy()
    p1_week_nets = p1_frame.groupby("week_monday", sort=True)["stressed_usd"].sum()
    p1_positive_week_fraction = float((p1_week_nets > 0.0).mean())
    p1_mean = metric_value(p1, "mean_per_tranche_session_usd")
    p1_zero_mean = metric_value(
        views["ZERO_RELEASE_LONG"]["periods"][p1_name]["stressed"],
        "mean_per_tranche_session_usd",
    )
    p1_same_week_mean = metric_value(
        views["SAME_WEEK_COUNT"]["periods"][p1_name]["stressed"],
        "mean_per_tranche_session_usd",
    )
    p1_checks = {
        "net_positive": metric_value(p1, "net_usd") > 0.0,
        "profit_factor": metric_value(p1, "profit_factor") >= float(gates["p1_profit_factor_min"]),
        "net_to_drawdown": metric_value(p1, "net_to_drawdown") >= float(gates["p1_net_to_drawdown_min"]),
        "positive_splits": sum(p1_splits.values()) >= int(gates["p1_positive_splits_required"]),
        "positive_event_week_fraction": p1_positive_week_fraction
        >= float(gates["p1_positive_event_week_fraction_min"]),
        "mean_above_zero_release": p1_mean > p1_zero_mean,
        "mean_above_same_week": p1_mean > p1_same_week_mean,
    }

    confirmation_periods = gates["confirmation_periods"]
    confirmation_net_checks: dict[str, bool] = {}
    confirmation_zero_mean_checks: dict[str, bool] = {}
    confirmation_positive_week_checks: dict[str, bool] = {}
    confirmation_positive_week_fractions: dict[str, float] = {}
    for period in confirmation_periods:
        primary_metric = primary["periods"][period]["stressed"]
        zero_metric = views["ZERO_RELEASE_LONG"]["periods"][period]["stressed"]
        confirmation_net_checks[period] = metric_value(primary_metric, "net_usd") > 0.0
        confirmation_zero_mean_checks[period] = metric_value(
            primary_metric, "mean_per_tranche_session_usd"
        ) > metric_value(
            zero_metric, "mean_per_tranche_session_usd"
        )
        period_frame = select_view(trades, "PRIMARY_COUNT")
        period_frame = period_frame.loc[period_frame["period"] == period]
        week_nets = period_frame.groupby("week_monday", sort=True)["stressed_usd"].sum()
        fraction = float((week_nets > 0.0).mean())
        confirmation_positive_week_fractions[period] = fraction
        confirmation_positive_week_checks[period] = fraction >= float(
            gates["confirmation_positive_event_week_fraction_min"]
        )
    confirmation_checks = {
        "positive_periods": sum(confirmation_net_checks.values())
        >= int(gates["confirmation_positive_periods_required"]),
        "mean_above_zero_release_periods": sum(confirmation_zero_mean_checks.values())
        >= int(gates["confirmation_mean_above_zero_release_periods_required"]),
        "positive_event_week_fraction_periods": sum(confirmation_positive_week_checks.values())
        >= int(gates["confirmation_positive_event_week_fraction_periods_required"]),
    }

    prelatest_frame = select_view(trades, "PRIMARY_COUNT")
    prelatest_frame = prelatest_frame.loc[prelatest_frame["period"] != latest_name].sort_values(
        "date", kind="stable"
    )
    prelatest = summarize_slice(prelatest_frame, config)["stressed"]
    prelatest_zero_frame = select_view(trades, "ZERO_RELEASE_LONG")
    prelatest_zero_frame = prelatest_zero_frame.loc[prelatest_zero_frame["period"] != latest_name]
    prelatest_zero = summarize_slice(prelatest_zero_frame, config)["stressed"]
    prelatest_same_frame = select_view(trades, "SAME_WEEK_COUNT")
    prelatest_same_frame = prelatest_same_frame.loc[prelatest_same_frame["period"] != latest_name]
    prelatest_same = summarize_slice(prelatest_same_frame, config)["stressed"]
    week_nets = prelatest_frame.groupby("week_monday", sort=True)["stressed_usd"].sum()
    positive_weeks = int((week_nets > 0.0).sum())
    active_weeks = int(len(week_nets))
    positive_week_values = week_nets.loc[week_nets > 0.0].sort_values(ascending=False)
    positive_week_sum = float(positive_week_values.sum())
    top_five_positive_week_share = (
        float(positive_week_values.head(5).sum()) / positive_week_sum
        if positive_week_sum > 0.0
        else None
    )
    prelatest_common = {
        "net_positive": metric_value(prelatest, "net_usd") > 0.0,
        "profit_factor": metric_value(prelatest, "profit_factor") >= float(gates["prelatest_profit_factor_min"]),
        "net_to_drawdown": metric_value(prelatest, "net_to_drawdown")
        >= float(gates["prelatest_net_to_drawdown_min"]),
        "positive_event_week_fraction": active_weeks > 0
        and positive_weeks / active_weeks >= float(gates["prelatest_positive_event_week_fraction_min"]),
        "top_five_positive_week_share": top_five_positive_week_share is not None
        and top_five_positive_week_share <= float(gates["prelatest_top_five_positive_week_share_max"]),
        "mean_above_zero_release": metric_value(prelatest, "mean_per_tranche_session_usd")
        > metric_value(prelatest_zero, "mean_per_tranche_session_usd"),
        "mean_above_same_week": metric_value(prelatest, "mean_per_tranche_session_usd")
        > metric_value(prelatest_same, "mean_per_tranche_session_usd"),
    }
    prelatest_nominal_dd = metric_value(prelatest, "max_closed_drawdown_percent", float("inf")) <= float(
        gates["nominal_drawdown_max_percent"]
    )
    prelatest_practical_dd = metric_value(prelatest, "max_closed_drawdown_percent", float("inf")) <= float(
        gates["practical_drawdown_max_percent"]
    )

    latest_summary = primary["periods"][latest_name]
    latest = latest_summary["stressed"]
    latest_net = metric_value(latest, "net_usd")
    positive_prelatest_mean = max(
        metric_value(prelatest, "mean_per_tranche_session_usd", 0.0), 0.0
    )
    latest_practical_floor = (
        -float(gates["latest_practical_reversal_fraction"])
        * positive_prelatest_mean
        * int(latest_summary["tranche_sessions"])
    )
    latest_nominal = latest_net >= float(gates["latest_nominal_floor_usd"])
    latest_practical = latest_net >= latest_practical_floor

    full = primary["full"]["stressed"]
    full_checks = {
        "net_positive": metric_value(full, "net_usd") > 0.0,
        "profit_factor": metric_value(full, "profit_factor") >= float(gates["full_profit_factor_min"]),
        "net_to_drawdown": metric_value(full, "net_to_drawdown") >= float(gates["full_net_to_drawdown_min"]),
    }
    density_passed = bool(event_integrity["density_passed"])
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
        verdict = "PASS_RETAIN_ONE_FIXED_BLOCKBUSTER_RELEASE_NEXT_WEEK_US500_CASH_LONG_SEED"
    elif practical_pass:
        verdict = (
            "PASS_PRACTICAL_RETAIN_ONE_FIXED_BLOCKBUSTER_RELEASE_NEXT_WEEK_US500_CASH_LONG_SEED"
        )
    elif strong_null:
        verdict = "VALID_NO_BLOCKBUSTER_RELEASE_NEXT_WEEK_US500_CASH_EFFECT_AFTER_COST_NO_SEED"
    else:
        verdict = "AMBIGUOUS_BLOCKBUSTER_RELEASE_NEXT_WEEK_US500_CASH_TRANSFER_NO_SEED"
    retained_seed = (
        "FIXED_HONG_WEI_BLOCKBUSTER_COUNT_NEXT_WEEK_US500_CASH_LONG"
        if nominal_pass or practical_pass
        else None
    )
    return {
        "density": event_integrity["density_checks"],
        "p1": p1_checks,
        "p1_splits": p1_splits,
        "p1_positive_event_week_fraction": p1_positive_week_fraction,
        "p1_control_means_per_tranche_session_usd": {
            "primary": p1_mean,
            "zero_release": p1_zero_mean,
            "same_week": p1_same_week_mean,
        },
        "confirmation": {
            "period_net_positive": confirmation_net_checks,
            "mean_above_zero_release": confirmation_zero_mean_checks,
            "positive_event_week_fractions": confirmation_positive_week_fractions,
            "positive_event_week_fraction_checks": confirmation_positive_week_checks,
            "summary": confirmation_checks,
        },
        "prelatest": {
            "metrics": prelatest,
            "zero_release_control": prelatest_zero,
            "same_week_control": prelatest_same,
            "positive_event_weeks": positive_weeks,
            "active_event_weeks": active_weeks,
            "positive_event_week_fraction": positive_weeks / active_weeks if active_weeks else None,
            "top_five_positive_week_share": top_five_positive_week_share,
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
        description="Analyze the fixed Hong-Wei blockbuster-count next-week US500 cash transfer."
    )
    parser.add_argument("--mode", choices=("premetric", "formal"), required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    config = load_json(CONFIG_PATH)
    input_root = REPO_ROOT / config["input_root"]
    output_root = REPO_ROOT / config["output_root"]
    input_integrity = verify_inputs(config, input_root)
    acquisition_summary = verify_pinned_file(config["acquisition_summary"], "acquisition summary")
    events = load_events(config, input_root)

    if args.mode == "premetric":
        sessions, inventory, session_integrity = load_calendar(config, input_root, formal=False)
        _, _, event_integrity = assign_event_roles(sessions, inventory, events, config)
        payload = premetric_payload(
            input_integrity, acquisition_summary, session_integrity, event_integrity
        )
        payload["elapsed_seconds"] = time.perf_counter() - started
        receipt_path = REPO_ROOT / config["premetric_receipt_path"]
        if receipt_path.exists():
            raise RuntimeError("premetric receipt already exists")
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_bytes(
            (json.dumps(json_safe(payload), indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
        print(json.dumps(json_safe(payload), indent=2, sort_keys=True))
        return 0

    declaration = verify_declaration(config)
    sessions, inventory, session_integrity = load_calendar(config, input_root, formal=True)
    declared, event_calendar, event_integrity = assign_event_roles(
        sessions, inventory, events, config
    )
    if not event_integrity["density_passed"]:
        raise RuntimeError("declared primary density gate failed before economic aggregation")
    spec = load_spec(config, input_root)
    trades = build_trades(declared, spec, config)
    views = build_views(trades, config)
    decision = evaluate_gates(trades, views, config, event_integrity)
    primary_rows = trades.loc[trades["target_release_count"] > 0]
    payload = {
        "schema": "zeta-next-us500-blockbuster-release-next-week-mood-analysis-v1",
        "status": "COMPLETE_VALID_SOURCE_FIXED_ECONOMIC_AGGREGATION",
        "input_integrity": input_integrity,
        "acquisition_summary": acquisition_summary,
        "declaration": declaration,
        "session_integrity": session_integrity,
        "event_integrity": event_integrity,
        "trade_integrity": {
            "rows": int(len(trades)),
            "primary_rows": int(len(primary_rows)),
            "primary_tranche_sessions": int(primary_rows["target_release_count"].sum()),
            "primary_event_weeks": int(primary_rows["week_monday"].nunique()),
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
    export_trades["week_monday"] = export_trades["week_monday"].dt.date.astype(str)
    export_trades.to_csv(targets[1], index=False, lineterminator="\n")
    export_calendar = event_calendar.copy()
    export_calendar["date"] = export_calendar["date"].dt.date.astype(str)
    export_calendar["week_monday"] = export_calendar["week_monday"].dt.date.astype(str)
    export_calendar.to_csv(targets[2], index=False, lineterminator="\n")
    print(json.dumps(json_safe(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
