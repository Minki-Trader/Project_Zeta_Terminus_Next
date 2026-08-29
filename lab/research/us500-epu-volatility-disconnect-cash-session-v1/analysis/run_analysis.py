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
STATE_NAMES = (
    "HIGH_D_LOW_V",
    "HIGH_D_HIGH_V",
    "LOW_D_LOW_V",
    "LOW_D_HIGH_V",
)
COST_COLUMNS = ("gross_usd", "observed_usd", "stressed_usd")


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
    if isinstance(value, (pd.Timestamp,)):
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
    if not expected.get("path") or not expected.get("sha256") or not expected.get("bytes"):
        raise RuntimeError("formal declaration pin is not frozen")
    path = REPO_ROOT / expected["path"]
    if not path.is_file():
        raise RuntimeError(f"formal declaration missing: {path}")
    size = path.stat().st_size
    digest = sha256_file(path)
    if size != expected["bytes"] or digest != expected["sha256"]:
        raise RuntimeError("formal declaration pin mismatch")
    return {"path": expected["path"], "bytes": size, "sha256": digest}


def load_epu(config: dict[str, Any], input_root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    path = input_root / config["files"]["epu"]
    frame = pd.read_csv(path)
    required = ["day", "month", "year", "daily_policy_index"]
    if list(frame.columns) != required:
        raise RuntimeError(f"unexpected EPU schema: {list(frame.columns)}")
    if len(frame) != config["immutable_inputs"]["epu_rows"]:
        raise RuntimeError("EPU row count mismatch")
    if frame.isna().any().any():
        raise RuntimeError("EPU contains null values")
    dates = pd.to_datetime(frame[["year", "month", "day"]], errors="raise")
    if dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise RuntimeError("EPU dates are not unique and increasing")
    values = frame["daily_policy_index"].astype(float)
    if (~np.isfinite(values)).any() or (values < 0.0).any():
        raise RuntimeError("EPU values are invalid")
    result = pd.DataFrame({"date": dates.dt.normalize(), "epu": values})
    return result, {
        "rows": int(len(result)),
        "first_date": result["date"].iloc[0].date().isoformat(),
        "last_date": result["date"].iloc[-1].date().isoformat(),
        "duplicate_dates": int(result["date"].duplicated().sum()),
        "null_values": int(result["epu"].isna().sum()),
    }


def load_sessions(config: dict[str, Any], input_root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    path = input_root / config["files"]["bars"]
    frame = pd.read_csv(path)
    required = config["required_bar_schema"]
    if list(frame.columns) != required:
        raise RuntimeError(f"unexpected bar schema: {list(frame.columns)}")
    if len(frame) != config["immutable_inputs"]["bar_rows"]:
        raise RuntimeError("bar row count mismatch")
    if frame.isna().any().any():
        raise RuntimeError("bar surface contains null values")
    epoch = frame["time_epoch"].astype(np.int64)
    if epoch.duplicated().any() or not epoch.is_monotonic_increasing:
        raise RuntimeError("bar epochs are not unique and increasing")
    if (frame[["open", "high", "low", "close"]] <= 0.0).any().any():
        raise RuntimeError("bar surface contains nonpositive prices")
    if (frame["spread"] < 0).any():
        raise RuntimeError("bar surface contains a negative spread")

    utc = pd.to_datetime(epoch, unit="s", utc=True)
    et = utc.dt.tz_convert(config["state_rule"]["timezone"])
    cash = frame.loc[
        (et.dt.weekday < 5)
        & (
            ((et.dt.hour == 9) & (et.dt.minute >= 30))
            | ((et.dt.hour >= 10) & (et.dt.hour < 16))
        ),
        ["time_epoch", "open", "high", "low", "close", "spread"],
    ].copy()
    cash["utc"] = utc.loc[cash.index]
    cash["et"] = et.loc[cash.index]
    cash["date"] = cash["et"].dt.tz_localize(None).dt.normalize()
    cash["minute_of_day"] = cash["et"].dt.hour * 60 + cash["et"].dt.minute

    expected_minutes = list(range(9 * 60 + 30, 16 * 60, 15))
    sessions: list[dict[str, Any]] = []
    incomplete = 0
    for date, group in cash.groupby("date", sort=True):
        ordered = group.sort_values("minute_of_day", kind="stable")
        minutes = ordered["minute_of_day"].astype(int).tolist()
        if minutes != expected_minutes:
            incomplete += 1
            continue
        closes = ordered["close"].astype(float).to_numpy()
        first_open = float(ordered["open"].iloc[0])
        prior = np.concatenate(([first_open], closes[:-1]))
        log_returns = np.log(closes / prior)
        realized_variance = float(np.square(log_returns).sum())
        sessions.append(
            {
                "date": date,
                "week_monday": date - pd.Timedelta(days=int(date.weekday())),
                "realized_variance": realized_variance,
                "entry_utc": ordered["utc"].iloc[0],
                "exit_utc": ordered["utc"].iloc[-1] + pd.Timedelta(minutes=15),
                "entry_bid": first_open,
                "exit_bid": float(ordered["close"].iloc[-1]),
                "entry_spread_points": int(ordered["spread"].iloc[0]),
                "exit_spread_points": int(ordered["spread"].iloc[-1]),
            }
        )
    result = pd.DataFrame(sessions).sort_values("date", kind="stable").reset_index(drop=True)
    if result.empty:
        raise RuntimeError("no complete cash sessions")
    return result, {
        "bar_rows": int(len(frame)),
        "first_utc": utc.iloc[0].isoformat(),
        "last_utc": utc.iloc[-1].isoformat(),
        "complete_cash_sessions": int(len(result)),
        "incomplete_cash_session_dates": int(incomplete),
        "first_complete_date": result["date"].iloc[0].date().isoformat(),
        "last_complete_date": result["date"].iloc[-1].date().isoformat(),
        "bars_per_complete_session": len(expected_minutes),
    }


def build_states(
    sessions: pd.DataFrame, epu: pd.DataFrame, config: dict[str, Any]
) -> tuple[pd.DataFrame, dict[str, Any]]:
    merged = sessions[["date", "week_monday", "realized_variance"]].merge(epu, on="date", how="left", validate="one_to_one")
    if merged["epu"].isna().any():
        missing = merged.loc[merged["epu"].isna(), "date"].dt.date.astype(str).tolist()
        raise RuntimeError(f"EPU missing on complete cash sessions: {missing[:5]}")

    source_weeks: list[dict[str, Any]] = []
    for monday, group in merged.groupby("week_monday", sort=True):
        if len(group) != 5:
            continue
        weekdays = sorted(group["date"].dt.weekday.astype(int).tolist())
        if weekdays != [0, 1, 2, 3, 4]:
            continue
        source_weeks.append(
            {
                "source_week_monday": monday,
                "source_week_friday": monday + pd.Timedelta(days=4),
                "uncertainty": float(group["epu"].mean()),
                "realized_volatility": float(math.sqrt(group["realized_variance"].sum())),
            }
        )
    weekly = pd.DataFrame(source_weeks).sort_values("source_week_monday", kind="stable").reset_index(drop=True)
    weekly["disconnect"] = weekly["uncertainty"] / weekly["realized_volatility"]
    if (~np.isfinite(weekly["disconnect"])).any() or (weekly["disconnect"] <= 0.0).any():
        raise RuntimeError("weekly uncertainty-volatility disconnect is invalid")
    warmup = int(config["state_rule"]["expanding_warmup_complete_weeks"])
    multiplier = float(config["state_rule"]["high_threshold_standard_deviations"])
    lag_weeks = int(config["state_rule"]["publication_safe_lag_calendar_weeks"])
    state_rows: list[dict[str, Any]] = []
    for position in range(warmup, len(weekly)):
        history = weekly.iloc[:position]
        current = weekly.iloc[position]
        d_threshold = float(history["disconnect"].mean() + multiplier * history["disconnect"].std(ddof=1))
        v_threshold = float(
            history["realized_volatility"].mean()
            + multiplier * history["realized_volatility"].std(ddof=1)
        )
        d_high = bool(current["disconnect"] > d_threshold)
        v_high = bool(current["realized_volatility"] > v_threshold)
        if d_high and not v_high:
            state = "HIGH_D_LOW_V"
        elif d_high and v_high:
            state = "HIGH_D_HIGH_V"
        elif not d_high and not v_high:
            state = "LOW_D_LOW_V"
        else:
            state = "LOW_D_HIGH_V"
        target_monday = current["source_week_monday"] + pd.Timedelta(weeks=lag_weeks)
        finalized_age_days = int((target_monday - current["source_week_friday"]).days)
        state_rows.append(
            {
                "source_week_monday": current["source_week_monday"],
                "source_week_friday": current["source_week_friday"],
                "target_week_monday": target_monday,
                "finalized_age_days": finalized_age_days,
                "uncertainty": float(current["uncertainty"]),
                "realized_volatility": float(current["realized_volatility"]),
                "disconnect": float(current["disconnect"]),
                "disconnect_threshold": d_threshold,
                "volatility_threshold": v_threshold,
                "disconnect_high": d_high,
                "volatility_high": v_high,
                "state": state,
            }
        )
    states = pd.DataFrame(state_rows).sort_values("target_week_monday", kind="stable").reset_index(drop=True)
    if states.empty:
        raise RuntimeError("no causal states after warmup")
    if int(states["finalized_age_days"].min()) <= int(config["state_rule"]["epu_revision_window_days"]):
        raise RuntimeError("publication-safe lag does not exceed the EPU revision window")
    return states, {
        "complete_source_weeks": int(len(weekly)),
        "expanding_warmup_complete_weeks": warmup,
        "causal_state_weeks": int(len(states)),
        "first_source_week_monday": states["source_week_monday"].iloc[0].date().isoformat(),
        "last_source_week_monday": states["source_week_monday"].iloc[-1].date().isoformat(),
        "first_target_week_monday": states["target_week_monday"].iloc[0].date().isoformat(),
        "last_target_week_monday": states["target_week_monday"].iloc[-1].date().isoformat(),
        "minimum_finalized_age_days": int(states["finalized_age_days"].min()),
        "state_week_counts": {name: int((states["state"] == name).sum()) for name in STATE_NAMES},
    }


def period_name(date: pd.Timestamp, config: dict[str, Any]) -> str | None:
    for name, boundary in config["periods"].items():
        if pd.Timestamp(boundary["from_inclusive"]) <= date < pd.Timestamp(boundary["to_exclusive"]):
            return name
    return None


def premetric_payload(
    input_integrity: dict[str, Any],
    epu_integrity: dict[str, Any],
    session_integrity: dict[str, Any],
    sessions: pd.DataFrame,
    states: pd.DataFrame,
    state_integrity: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    target = sessions.merge(
        states[["target_week_monday", "state"]],
        left_on="week_monday",
        right_on="target_week_monday",
        how="inner",
        validate="many_to_one",
    )
    target["period"] = target["date"].apply(lambda value: period_name(value, config))
    target = target.loc[target["period"].notna()].copy()
    target["half"] = target["date"].dt.year.astype(str) + "H" + np.where(target["date"].dt.month <= 6, "1", "2")
    period_state_days: dict[str, dict[str, int]] = {}
    for period in config["periods"]:
        subset = target.loc[target["period"] == period]
        period_state_days[period] = {name: int((subset["state"] == name).sum()) for name in STATE_NAMES}
    return {
        "schema": "zeta-next-us500-epu-volatility-disconnect-cash-session-premetric-v1",
        "status": "PREDICTOR_AND_DENSITY_ONLY_ECONOMIC_OUTCOMES_UNOPENED",
        "input_integrity": input_integrity,
        "epu_integrity": epu_integrity,
        "session_integrity": session_integrity,
        "state_integrity": state_integrity,
        "target_density": {
            "target_days_in_declared_periods": int(len(target)),
            "first_target_date": target["date"].iloc[0].date().isoformat() if len(target) else None,
            "last_target_date": target["date"].iloc[-1].date().isoformat() if len(target) else None,
            "state_day_counts": {name: int((target["state"] == name).sum()) for name in STATE_NAMES},
            "period_state_day_counts": period_state_days,
            "half_state_day_counts": {
                str(half): {name: int((group["state"] == name).sum()) for name in STATE_NAMES}
                for half, group in target.groupby("half", sort=True)
            },
        },
        "economic_outcomes_opened": False,
        "forbidden_fields_not_calculated": [
            "entry_to_exit_return",
            "gross_usd",
            "observed_usd",
            "stressed_usd",
            "profit_factor",
            "drawdown",
            "gate",
            "verdict",
        ],
    }


def build_trades(
    sessions: pd.DataFrame, states: pd.DataFrame, config: dict[str, Any]
) -> pd.DataFrame:
    joined = sessions.merge(states, left_on="week_monday", right_on="target_week_monday", how="inner", validate="many_to_one")
    joined["period"] = joined["date"].apply(lambda value: period_name(value, config))
    joined = joined.loc[joined["period"].notna()].copy()
    spec = load_json(REPO_ROOT / config["input_root"] / config["files"]["spec"])
    point = float(spec["point"])
    contract_size = float(spec["trade_contract_size"])
    volume = float(config["trade_rule"]["volume"])
    entry_spread_usd = joined["entry_spread_points"].astype(float) * point * contract_size * volume
    exit_spread_usd = joined["exit_spread_points"].astype(float) * point * contract_size * volume
    entry_mid = joined["entry_bid"].astype(float) + 0.5 * joined["entry_spread_points"].astype(float) * point
    exit_mid = joined["exit_bid"].astype(float) + 0.5 * joined["exit_spread_points"].astype(float) * point
    gross = (exit_mid - entry_mid) * contract_size * volume
    observed = (joined["exit_bid"].astype(float) - (joined["entry_bid"].astype(float) + joined["entry_spread_points"].astype(float) * point)) * contract_size * volume
    observed_identity = gross - 0.5 * (entry_spread_usd + exit_spread_usd)
    if float(np.max(np.abs(observed - observed_identity))) > 1e-10:
        raise RuntimeError("bid/ask observed-cost identity mismatch")
    stressed = gross - (entry_spread_usd + exit_spread_usd)
    joined["entry_mid"] = entry_mid
    joined["exit_mid"] = exit_mid
    joined["gross_usd"] = gross
    joined["observed_usd"] = observed
    joined["stressed_usd"] = stressed
    joined["month"] = joined["date"].dt.strftime("%Y-%m")
    joined["half"] = joined["date"].dt.year.astype(str) + "H" + np.where(joined["date"].dt.month <= 6, "1", "2")
    columns = [
        "date",
        "month",
        "half",
        "period",
        "state",
        "source_week_monday",
        "source_week_friday",
        "target_week_monday",
        "finalized_age_days",
        "uncertainty",
        "realized_volatility",
        "disconnect",
        "disconnect_threshold",
        "volatility_threshold",
        "entry_utc",
        "exit_utc",
        "entry_bid",
        "exit_bid",
        "entry_spread_points",
        "exit_spread_points",
        "entry_mid",
        "exit_mid",
        "gross_usd",
        "observed_usd",
        "stressed_usd",
    ]
    return joined[columns].sort_values("date", kind="stable").reset_index(drop=True)


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
            "mean_to_standard_deviation": None,
            "max_closed_drawdown_usd": 0.0,
            "max_closed_drawdown_percent": 0.0,
            "net_to_drawdown": None,
        }
    net = float(array.sum())
    profit = float(array[array > 0.0].sum())
    loss = float(array[array < 0.0].sum())
    pf = profit / abs(loss) if loss < 0.0 else None
    mean = float(array.mean())
    standard_deviation = float(array.std(ddof=1)) if len(array) > 1 else 0.0
    cumulative = np.cumsum(array)
    peaks = np.maximum.accumulate(np.concatenate(([0.0], cumulative)))
    drawdowns = peaks[1:] - cumulative
    max_drawdown = float(drawdowns.max(initial=0.0))
    return {
        "count": int(len(array)),
        "net_usd": net,
        "gross_profit_usd": profit,
        "gross_loss_usd": loss,
        "profit_factor": float(pf) if pf is not None else None,
        "win_rate": float(np.mean(array > 0.0)),
        "mean_usd": mean,
        "standard_deviation_usd": standard_deviation,
        "mean_to_standard_deviation": mean / standard_deviation if standard_deviation > 0.0 else None,
        "max_closed_drawdown_usd": max_drawdown,
        "max_closed_drawdown_percent": max_drawdown / starting_balance * 100.0,
        "net_to_drawdown": net / max_drawdown if max_drawdown > 0.0 else None,
    }


def summarize_slice(frame: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    balance = float(config["trade_rule"]["starting_balance_usd"])
    return {column.removesuffix("_usd"): series_metrics(frame[column], balance) for column in COST_COLUMNS}


def select_view(trades: pd.DataFrame, name: str) -> pd.DataFrame:
    if name == "UNCONDITIONAL":
        return trades
    if name == "HIGH_D_POOLED":
        return trades.loc[trades["state"].isin(["HIGH_D_LOW_V", "HIGH_D_HIGH_V"])]
    if name == "LOW_D_POOLED":
        return trades.loc[trades["state"].isin(["LOW_D_LOW_V", "LOW_D_HIGH_V"])]
    return trades.loc[trades["state"] == name]


def build_views(trades: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    names = list(STATE_NAMES) + ["HIGH_D_POOLED", "LOW_D_POOLED", "UNCONDITIONAL"]
    views: dict[str, Any] = {}
    for name in names:
        subset = select_view(trades, name)
        views[name] = {
            "full": summarize_slice(subset, config),
            "periods": {
                period: summarize_slice(subset.loc[subset["period"] == period], config)
                for period in config["periods"]
            },
            "halves": {
                half: summarize_slice(group, config)
                for half, group in subset.groupby("half", sort=True)
            },
            "stressed_month_nets": {
                str(month): float(value)
                for month, value in subset.groupby("month")["stressed_usd"].sum().items()
            },
        }
    return views


def positive(value: float | None) -> bool:
    return value is not None and math.isfinite(float(value)) and float(value) > 0.0


def at_least(value: float | None, threshold: float) -> bool:
    return value is not None and math.isfinite(float(value)) and float(value) >= threshold


def evaluate_gates(views: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    primary = views["HIGH_D_LOW_V"]
    low_disconnect = views["LOW_D_POOLED"]
    unconditional = views["UNCONDITIONAL"]
    high_disconnect = views["HIGH_D_POOLED"]
    g = config["economic_gates"]
    binding = "stressed"

    density: dict[str, bool] = {}
    for period, floor in g["minimum_primary_days_by_period"].items():
        density[period] = primary["periods"][period][binding]["count"] >= int(floor)

    p1_name = g["p1_period"]
    p1 = primary["periods"][p1_name][binding]
    p1_halves = [primary["halves"].get(half, {}).get(binding, {}) for half in g["p1_halves"]]
    p1_gate = {
        "net_positive": positive(p1["net_usd"]),
        "profit_factor": at_least(p1["profit_factor"], float(g["p1_profit_factor_min"])),
        "net_to_drawdown": at_least(p1["net_to_drawdown"], float(g["p1_net_to_drawdown_min"])),
        "both_halves_positive": all(positive(item.get("net_usd")) for item in p1_halves),
        "mean_above_low_disconnect": p1["mean_usd"] > low_disconnect["periods"][p1_name][binding]["mean_usd"],
        "mean_above_unconditional": p1["mean_usd"] > unconditional["periods"][p1_name][binding]["mean_usd"],
    }

    confirmation: dict[str, Any] = {}
    mean_breadth = 0
    high_disconnect_positive = 0
    primary_positive = 0
    for period in g["confirmation_periods"]:
        p = primary["periods"][period][binding]
        low = low_disconnect["periods"][period][binding]
        high = high_disconnect["periods"][period][binding]
        item = {
            "primary_net_positive": positive(p["net_usd"]),
            "primary_mean_above_low_disconnect": p["mean_usd"] is not None and low["mean_usd"] is not None and p["mean_usd"] > low["mean_usd"],
            "high_disconnect_pooled_net_positive": positive(high["net_usd"]),
        }
        confirmation[period] = item
        primary_positive += int(item["primary_net_positive"])
        mean_breadth += int(item["primary_mean_above_low_disconnect"])
        high_disconnect_positive += int(item["high_disconnect_pooled_net_positive"])

    pooled = primary["full"][binding]
    confirmation_gate = {
        "all_primary_periods_positive": primary_positive == len(g["confirmation_periods"]),
        "primary_mean_above_low_disconnect_breadth": mean_breadth >= int(g["confirmation_mean_breadth_min"]),
        "high_disconnect_pooled_positive_breadth": high_disconnect_positive >= int(g["high_disconnect_positive_breadth_min"]),
    }
    latest_name = g["latest_period"]
    latest = primary["periods"][latest_name][binding]
    latest_gate = {
        "nominal_net_nonnegative": latest["net_usd"] is not None and latest["net_usd"] >= 0.0,
        "full_net_positive": positive(pooled["net_usd"]),
        "full_profit_factor": at_least(pooled["profit_factor"], float(g["full_profit_factor_min"])),
    }
    return {
        "density": density,
        "p1": p1_gate,
        "confirmation": confirmation,
        "confirmation_summary": confirmation_gate,
        "latest_and_full": latest_gate,
    }


def finalize_gate_verdict(gates: dict[str, Any], views: dict[str, Any], trades: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    g = config["economic_gates"]
    primary_prelatest = trades.loc[
        (trades["state"] == "HIGH_D_LOW_V") & (trades["period"] != g["latest_period"])
    ]
    prelatest = summarize_slice(primary_prelatest, config)["stressed"]
    low_disconnect_prelatest = trades.loc[
        trades["state"].isin(["LOW_D_LOW_V", "LOW_D_HIGH_V"]) & (trades["period"] != g["latest_period"])
    ]
    high_disconnect_high_vol_prelatest = trades.loc[
        (trades["state"] == "HIGH_D_HIGH_V") & (trades["period"] != g["latest_period"])
    ]
    unconditional_prelatest = trades.loc[trades["period"] != g["latest_period"]]
    low = summarize_slice(low_disconnect_prelatest, config)["stressed"]
    high_vol = summarize_slice(high_disconnect_high_vol_prelatest, config)["stressed"]
    control = summarize_slice(unconditional_prelatest, config)["stressed"]
    primary_months = primary_prelatest.groupby("month")["stressed_usd"].sum()
    prelatest_gate = {
        "net_positive": positive(prelatest["net_usd"]),
        "profit_factor": at_least(prelatest["profit_factor"], float(g["prelatest_profit_factor_min"])),
        "net_to_drawdown": at_least(prelatest["net_to_drawdown"], float(g["prelatest_net_to_drawdown_min"])),
        "drawdown_nominal": prelatest["max_closed_drawdown_percent"] <= float(g["nominal_drawdown_max_percent"]),
        "mean_above_low_disconnect": prelatest["mean_usd"] > low["mean_usd"],
        "mean_above_unconditional": prelatest["mean_usd"] > control["mean_usd"],
        "risk_adjusted_above_low_disconnect": prelatest["mean_to_standard_deviation"] > low["mean_to_standard_deviation"],
        "risk_adjusted_above_high_disconnect_high_vol": prelatest["mean_to_standard_deviation"] > high_vol["mean_to_standard_deviation"],
        "positive_months": int((primary_months > 0.0).sum()) >= int(g["prelatest_positive_months_min"]),
    }
    gates["prelatest"] = prelatest_gate
    gates["prelatest_metrics"] = {
        "primary": prelatest,
        "low_disconnect_control": low,
        "high_disconnect_high_vol_control": high_vol,
        "unconditional_control": control,
        "primary_months": int(len(primary_months)),
        "primary_positive_months": int((primary_months > 0.0).sum()),
    }
    all_checks: list[bool] = []
    all_checks.extend(gates["density"].values())
    all_checks.extend(gates["p1"].values())
    all_checks.extend(gates["confirmation_summary"].values())
    all_checks.extend(gates["prelatest"].values())
    all_checks.extend(gates["latest_and_full"].values())
    passed = all(all_checks)
    if passed:
        verdict = "PASS_RETAIN_ONE_FINALIZED_HIGH_DISCONNECT_LOW_VOL_US500_CASH_SESSION_SEED"
    elif not all(gates["density"].values()):
        verdict = "INVALID_PRIMARY_STATE_DENSITY_NO_ECONOMIC_VERDICT"
    elif not positive(prelatest["net_usd"]):
        verdict = "VALID_NO_HIGH_DISCONNECT_LOW_VOL_US500_CASH_SESSION_EDGE_NO_SEED"
    else:
        verdict = "AMBIGUOUS_EPU_VOLATILITY_DISCONNECT_TRANSFER_NO_SEED"
    return {"passed": passed, "verdict": verdict, "checks": gates}


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze the fixed US500 EPU/volatility-disconnect cash-session transfer.")
    parser.add_argument("--mode", choices=("premetric", "formal"), required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    config = load_json(CONFIG_PATH)
    input_root = REPO_ROOT / config["input_root"]
    output_root = REPO_ROOT / config["output_root"]
    input_integrity = verify_inputs(config, input_root)
    epu, epu_integrity = load_epu(config, input_root)
    sessions, session_integrity = load_sessions(config, input_root)
    states, state_integrity = build_states(sessions, epu, config)

    if args.mode == "premetric":
        payload = premetric_payload(
            input_integrity,
            epu_integrity,
            session_integrity,
            sessions,
            states,
            state_integrity,
            config,
        )
        payload["elapsed_seconds"] = time.perf_counter() - started
        print(json.dumps(json_safe(payload), indent=2, sort_keys=True))
        return 0

    declaration = verify_declaration(config)
    trades = build_trades(sessions, states, config)
    views = build_views(trades, config)
    gates = evaluate_gates(views, config)
    decision = finalize_gate_verdict(gates, views, trades, config)
    payload = {
        "schema": "zeta-next-us500-epu-volatility-disconnect-cash-session-analysis-v1",
        "status": "COMPLETE_VALID_ECONOMIC_AGGREGATION",
        "declaration": declaration,
        "input_integrity": input_integrity,
        "epu_integrity": epu_integrity,
        "session_integrity": session_integrity,
        "state_integrity": state_integrity,
        "trade_integrity": {
            "rows": int(len(trades)),
            "first_date": trades["date"].iloc[0].date().isoformat(),
            "last_date": trades["date"].iloc[-1].date().isoformat(),
            "state_day_counts": {name: int((trades["state"] == name).sum()) for name in STATE_NAMES},
            "zero_entry_spread_rows": int((trades["entry_spread_points"] == 0).sum()),
            "zero_exit_spread_rows": int((trades["exit_spread_points"] == 0).sum()),
        },
        "views": views,
        "decision": decision,
        "elapsed_seconds": time.perf_counter() - started,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    result_path = output_root / "analysis-result.json"
    trades_path = output_root / "trades.csv"
    states_path = output_root / "states.csv"
    result_path.write_text(json.dumps(json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    trades.to_csv(trades_path, index=False, lineterminator="\n")
    states.to_csv(states_path, index=False, lineterminator="\n")
    print(json.dumps(json_safe(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
