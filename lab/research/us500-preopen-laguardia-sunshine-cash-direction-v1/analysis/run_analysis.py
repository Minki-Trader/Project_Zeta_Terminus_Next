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


REPO_ROOT = Path(__file__).resolve().parents[4]
FAMILY_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = FAMILY_ROOT / "config" / "contract.json"
COST_COLUMNS = ("gross_usd", "observed_usd", "stressed_usd")
VIEW_NAMES = (
    "PRIMARY_WEATHER_DIRECTION",
    "SUNNY_LONG_ONLY",
    "CLOUDY_SHORT_ONLY",
    "UNCONDITIONAL_LONG",
)


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


def semantic_contract_sha256(config: dict[str, Any]) -> str:
    semantic = copy.deepcopy(config)
    semantic.pop("formal_declaration", None)
    payload = json.dumps(semantic, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


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


def verify_declaration(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt = verify_pinned_file(config.get("formal_declaration", {}), "formal declaration")
    declaration = load_json(REPO_ROOT / receipt["path"])
    if declaration.get("semantic_contract_sha256") != semantic_contract_sha256(config):
        raise RuntimeError("formal declaration semantic contract mismatch")
    code_receipt = verify_pinned_file(declaration.get("analysis_code", {}), "analysis code")
    if Path(code_receipt["path"]).as_posix() != Path(__file__).resolve().relative_to(REPO_ROOT).as_posix():
        raise RuntimeError("formal declaration points to a different analysis code path")
    return receipt, declaration


def period_name(value: pd.Timestamp, config: dict[str, Any]) -> str | None:
    for name, boundary in config["periods"].items():
        if pd.Timestamp(boundary["from_inclusive"]) <= value < pd.Timestamp(boundary["to_exclusive"]):
            return name
    return None


def split_name(value: pd.Timestamp, config: dict[str, Any]) -> str | None:
    for name, boundary in config["p1_splits"].items():
        if pd.Timestamp(boundary[0]) <= value < pd.Timestamp(boundary[1]):
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
    if len(frame) != int(config["immutable_inputs"]["bar_rows"]):
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
    et = utc.dt.tz_convert(config["weather_rule"]["timezone"])
    cash_mask = (et.dt.weekday < 5) & (
        ((et.dt.hour == 9) & (et.dt.minute >= 30))
        | ((et.dt.hour >= 10) & (et.dt.hour < 16))
    )
    columns = ["time_epoch"]
    if formal:
        columns += ["open", "high", "low", "close", "spread"]
    cash = frame.loc[cash_mask, columns].copy()
    cash["utc"] = utc.loc[cash.index]
    cash["et"] = et.loc[cash.index]
    cash["date"] = cash["et"].dt.tz_localize(None).dt.normalize()
    cash["minute_of_day"] = cash["et"].dt.hour * 60 + cash["et"].dt.minute

    expected_minutes = list(range(9 * 60 + 30, 16 * 60, 15))
    entry_minute = expected_minutes[0]
    exit_minute = expected_minutes[-1]
    inventory_rows: list[dict[str, Any]] = []
    session_rows: list[dict[str, Any]] = []
    for session_date, group in cash.groupby("date", sort=True):
        ordered = group.sort_values("minute_of_day", kind="stable")
        minutes = ordered["minute_of_day"].astype(int).tolist()
        full_geometry = minutes == expected_minutes
        boundary_eligible = minutes.count(entry_minute) == 1 and minutes.count(exit_minute) == 1
        inventory_rows.append(
            {
                "date": session_date,
                "observed_cash_bars": int(len(ordered)),
                "full_bar_geometry": bool(full_geometry),
                "market_boundary_complete": bool(boundary_eligible),
            }
        )
        if not boundary_eligible:
            continue
        entry_row = ordered.loc[ordered["minute_of_day"] == entry_minute].iloc[0]
        exit_row = ordered.loc[ordered["minute_of_day"] == exit_minute].iloc[0]
        row: dict[str, Any] = {
            "date": session_date,
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
        "trade_boundary_ineligible_cash_session_dates": int((~inventory["market_boundary_complete"]).sum()),
        "full_26_bar_cash_sessions": int(inventory["full_bar_geometry"].sum()),
        "non_full_26_bar_cash_session_dates": int((~inventory["full_bar_geometry"]).sum()),
        "first_observed_date": inventory["date"].iloc[0].date().isoformat(),
        "last_observed_date": inventory["date"].iloc[-1].date().isoformat(),
        "first_trade_boundary_eligible_date": sessions["date"].iloc[0].date().isoformat(),
        "last_trade_boundary_eligible_date": sessions["date"].iloc[-1].date().isoformat(),
        "full_bar_geometry_count": len(expected_minutes),
        "price_or_spread_fields_loaded": formal,
    }


def load_weather(config: dict[str, Any], input_root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    path = input_root / config["files"]["weather"]
    weather = pd.read_csv(path)
    required = config["required_weather_schema"]
    if list(weather.columns) != required:
        raise RuntimeError(f"unexpected weather schema: {list(weather.columns)}")
    if len(weather) != int(config["immutable_inputs"]["weather_rows"]):
        raise RuntimeError("weather row count mismatch")
    weather["date"] = pd.to_datetime(weather["date"], errors="raise")
    if weather["date"].duplicated().any() or not weather["date"].is_monotonic_increasing:
        raise RuntimeError("weather dates are not unique and increasing")
    expected_dates = pd.date_range(weather["date"].iloc[0], weather["date"].iloc[-1], freq="D")
    if not weather["date"].reset_index(drop=True).equals(pd.Series(expected_dates)):
        raise RuntimeError("weather daily surface is not calendar-contiguous")
    expected_period = weather["date"].map(lambda value: period_name(value, config) or "OUTSIDE_TARGET")
    if not expected_period.equals(weather["period"]):
        raise RuntimeError("weather period classification mismatch")

    weather["weather_complete"] = weather["complete_four_hours"].astype(int) == 1
    weather["direction"] = weather["direction"].fillna("")
    weather["sky_cover_mean_oktas"] = pd.to_numeric(
        weather["sky_cover_mean_oktas"], errors="coerce"
    )
    complete = weather["weather_complete"]
    if not (weather.loc[complete, "observation_count"].astype(int) == 4).all():
        raise RuntimeError("complete weather day does not have four observations")
    sky_columns = [f"sky_{hour:02d}_oktas" for hour in config["weather_rule"]["hours"]]
    sky = weather[sky_columns].apply(pd.to_numeric, errors="coerce")
    if sky.loc[complete].isna().any().any():
        raise RuntimeError("complete weather day has a missing sky amount")
    if not np.allclose(
        sky.loc[complete].mean(axis=1).to_numpy(),
        weather.loc[complete, "sky_cover_mean_oktas"].to_numpy(),
        rtol=0.0,
        atol=1e-9,
    ):
        raise RuntimeError("daily weather mean identity mismatch")
    expected_direction = np.where(
        weather.loc[complete, "sky_cover_mean_oktas"].to_numpy() <= 4.0,
        "LONG",
        "SHORT",
    )
    if not np.array_equal(weather.loc[complete, "direction"].to_numpy(), expected_direction):
        raise RuntimeError("weather direction threshold mismatch")

    observation_columns = [f"obs_{hour:02d}_utc" for hour in config["weather_rule"]["hours"]]
    parsed_observations: list[pd.Series] = []
    for hour, column in zip(config["weather_rule"]["hours"], observation_columns):
        parsed = pd.to_datetime(weather[column], utc=True, errors="coerce")
        if parsed.loc[complete].isna().any():
            raise RuntimeError(f"complete weather day lacks {column}")
        local = parsed.loc[complete].dt.tz_convert(config["weather_rule"]["timezone"])
        if not (local.dt.hour == int(hour)).all():
            raise RuntimeError(f"{column} is not in its declared actual local hour")
        if not np.array_equal(
            local.dt.tz_localize(None).dt.normalize().to_numpy(),
            weather.loc[complete, "date"].to_numpy(),
        ):
            raise RuntimeError(f"{column} local date mismatch")
        weather[column] = parsed
        parsed_observations.append(parsed)
    weather["latest_weather_utc"] = pd.concat(parsed_observations, axis=1).max(axis=1)
    weather = weather.rename(columns={"period": "weather_period"})
    counts = {
        period: {
            "complete_days": int(
                ((weather["weather_period"] == period) & weather["weather_complete"]).sum()
            ),
            "long_days": int(
                ((weather["weather_period"] == period) & (weather["direction"] == "LONG")).sum()
            ),
            "short_days": int(
                ((weather["weather_period"] == period) & (weather["direction"] == "SHORT")).sum()
            ),
        }
        for period in config["periods"]
    }
    return weather, {
        "rows": int(len(weather)),
        "complete_days": int(weather["weather_complete"].sum()),
        "incomplete_days": int((~weather["weather_complete"]).sum()),
        "first_date": weather["date"].iloc[0].date().isoformat(),
        "last_date": weather["date"].iloc[-1].date().isoformat(),
        "period_counts": counts,
        "price_or_spread_fields_loaded": False,
    }


def assign_weather_roles(
    sessions: pd.DataFrame,
    inventory: pd.DataFrame,
    weather: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    calendar_config = config["official_session_calendar"]
    closed_dates = pd.to_datetime(calendar_config["closed_dates"])
    if closed_dates.duplicated().any() or any(value.weekday() >= 5 for value in closed_dates):
        raise RuntimeError("official closure calendar is malformed")
    start = min(pd.Timestamp(value["from_inclusive"]) for value in config["periods"].values())
    end_exclusive = max(pd.Timestamp(value["to_exclusive"]) for value in config["periods"].values())
    weekday_dates = pd.date_range(start, end_exclusive - pd.Timedelta(days=1), freq="B")
    active_closed = closed_dates[(closed_dates >= start) & (closed_dates < end_exclusive)]
    official_dates = weekday_dates[~weekday_dates.isin(active_closed)]

    calendar = pd.DataFrame({"date": official_dates})
    calendar = calendar.merge(inventory, on="date", how="left", validate="one_to_one")
    calendar = calendar.merge(weather, on="date", how="left", validate="one_to_one")
    calendar["observed_cash_bars"] = calendar["observed_cash_bars"].fillna(0).astype(int)
    for column in ("full_bar_geometry", "market_boundary_complete", "weather_complete"):
        calendar[column] = calendar[column].astype("boolean").fillna(False).astype(bool)
    calendar["direction"] = calendar["direction"].fillna("")
    calendar["period"] = calendar["date"].map(lambda value: period_name(value, config))
    calendar["split"] = calendar["date"].map(lambda value: split_name(value, config))
    calendar["calendar_month"] = calendar["date"].dt.strftime("%Y-%m")
    joined = calendar.merge(sessions, on="date", how="left", validate="one_to_one")
    joined["eligible"] = joined["market_boundary_complete"] & joined["weather_complete"]
    declared = joined.loc[joined["eligible"]].copy().reset_index(drop=True)
    if declared.empty:
        raise RuntimeError("weather-and-market eligible session surface is empty")
    if declared[["entry_utc", "exit_utc", "latest_weather_utc"]].isna().any().any():
        raise RuntimeError("eligible session lacks time boundary")
    declared["preopen_lead_minutes"] = (
        (declared["entry_utc"] - declared["latest_weather_utc"]).dt.total_seconds() / 60.0
    )
    preopen_all = bool((declared["preopen_lead_minutes"] > 0.0).all())

    gates = config["economic_gates"]
    eligible_days = {
        period: int((declared["period"] == period).sum()) for period in config["periods"]
    }
    direction_days = {
        period: {
            direction: int(
                ((declared["period"] == period) & (declared["direction"] == direction)).sum()
            )
            for direction in ("LONG", "SHORT")
        }
        for period in config["periods"]
    }
    split_days = {
        split: int((declared["split"] == split).sum()) for split in config["p1_splits"]
    }
    eligible_checks = {
        period: eligible_days[period] >= int(minimum)
        for period, minimum in gates["minimum_eligible_days_by_period"].items()
    }
    direction_checks = {
        period: {
            direction: direction_days[period][direction] >= int(minimum)
            for direction, minimum in minima.items()
        }
        for period, minima in gates["minimum_direction_days_by_period"].items()
    }
    split_checks = {
        split: split_days[split] >= int(minimum)
        for split, minimum in gates["minimum_p1_days_by_split"].items()
    }
    density_checks = {
        "eligible_days_by_period": eligible_checks,
        "both_directions_by_period": direction_checks,
        "p1_days_by_split": split_checks,
        "all_latest_weather_observations_precede_entry": preopen_all,
    }
    density_passed = (
        all(eligible_checks.values())
        and all(all(values.values()) for values in direction_checks.values())
        and all(split_checks.values())
        and preopen_all
    )
    observed_target = inventory.loc[(inventory["date"] >= start) & (inventory["date"] < end_exclusive)]
    unofficial_observed = observed_target.loc[~observed_target["date"].isin(set(official_dates))]
    return declared, joined, {
        "official_calendar_sources": calendar_config["sources"],
        "official_session_dates": int(len(calendar)),
        "official_closure_dates_in_target_range": int(len(active_closed)),
        "official_closure_dates": active_closed.date.astype(str).tolist(),
        "observed_cfd_dates_not_official_sessions": int(len(unofficial_observed)),
        "observed_cfd_dates_not_official_session_dates": unofficial_observed["date"].dt.date.astype(str).tolist(),
        "official_sessions_without_observed_cash_bars": int((calendar["observed_cash_bars"] == 0).sum()),
        "official_sessions_without_trade_boundaries": int(
            ((calendar["observed_cash_bars"] > 0) & ~calendar["market_boundary_complete"]).sum()
        ),
        "official_sessions_without_complete_weather": int((~calendar["weather_complete"]).sum()),
        "eligible_sessions": int(len(declared)),
        "eligible_days_by_period": eligible_days,
        "direction_days_by_period": direction_days,
        "eligible_days_by_p1_split": split_days,
        "minimum_preopen_lead_minutes": float(declared["preopen_lead_minutes"].min()),
        "maximum_preopen_lead_minutes": float(declared["preopen_lead_minutes"].max()),
        "weather_complete_but_market_boundary_ineligible_dates": calendar.loc[
            calendar["weather_complete"] & ~calendar["market_boundary_complete"], "date"
        ].dt.date.astype(str).tolist(),
        "market_boundary_complete_but_weather_incomplete_dates": calendar.loc[
            calendar["market_boundary_complete"] & ~calendar["weather_complete"], "date"
        ].dt.date.astype(str).tolist(),
        "density_checks": density_checks,
        "density_passed": bool(density_passed),
    }


def premetric_payload(
    semantic_hash: str,
    input_integrity: dict[str, Any],
    acquisition_summary: dict[str, Any],
    session_integrity: dict[str, Any],
    weather_integrity: dict[str, Any],
    eligibility_integrity: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": "zeta-next-us500-preopen-laguardia-sunshine-premetric-v1",
        "status": "COMPLETE_SOURCE_WEATHER_AND_SESSION_GEOMETRY_TARGET_ECONOMICS_UNOPENED",
        "semantic_contract_sha256": semantic_hash,
        "input_integrity": input_integrity,
        "acquisition_summary": acquisition_summary,
        "session_integrity": session_integrity,
        "weather_integrity": weather_integrity,
        "eligibility_integrity": eligibility_integrity,
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
    if abs((volume - minimum) / step - round((volume - minimum) / step)) > 1e-9:
        raise RuntimeError("declared volume is not aligned to the symbol volume step")
    point = float(spec["point"])
    contract_size = float(spec["trade_contract_size"])
    tick_size = float(spec["trade_tick_size"])
    tick_value = float(spec["trade_tick_value"])
    if min(point, contract_size, tick_size, tick_value) <= 0.0:
        raise RuntimeError("symbol specification contains a nonpositive economic field")
    if abs(tick_size * contract_size - tick_value) > 1e-10:
        raise RuntimeError("symbol tick-value identity mismatch")
    return {**spec, "contract_size": contract_size}


def build_trades(declared: pd.DataFrame, spec: dict[str, Any], config: dict[str, Any]) -> pd.DataFrame:
    trades = declared.copy().sort_values("date", kind="stable").reset_index(drop=True)
    point = float(spec["point"])
    contract_size = float(spec["contract_size"])
    volume = float(config["trade_rule"]["volume"])
    entry_spread_usd = trades["entry_spread_points"].astype(float) * point * contract_size * volume
    exit_spread_usd = trades["exit_spread_points"].astype(float) * point * contract_size * volume
    entry_mid = trades["entry_bid"].astype(float) + 0.5 * trades["entry_spread_points"].astype(float) * point
    exit_mid = trades["exit_bid"].astype(float) + 0.5 * trades["exit_spread_points"].astype(float) * point
    long_gross = (exit_mid - entry_mid) * contract_size * volume
    half_burden = 0.5 * (entry_spread_usd + exit_spread_usd)
    full_burden = entry_spread_usd + exit_spread_usd
    long_observed = (
        trades["exit_bid"].astype(float)
        - (trades["entry_bid"].astype(float) + trades["entry_spread_points"].astype(float) * point)
    ) * contract_size * volume
    short_observed = (
        trades["entry_bid"].astype(float)
        - (trades["exit_bid"].astype(float) + trades["exit_spread_points"].astype(float) * point)
    ) * contract_size * volume
    if float(np.max(np.abs(long_observed.to_numpy() - (long_gross - half_burden).to_numpy()))) > 1e-10:
        raise RuntimeError("LONG observed bid/ask identity mismatch")
    if float(np.max(np.abs(short_observed.to_numpy() - (-long_gross - half_burden).to_numpy()))) > 1e-10:
        raise RuntimeError("SHORT observed bid/ask identity mismatch")
    direction_multiplier = trades["direction"].map({"LONG": 1.0, "SHORT": -1.0})
    if direction_multiplier.isna().any():
        raise RuntimeError("eligible trade has an unknown direction")
    primary_gross = direction_multiplier * long_gross
    primary_observed = np.where(direction_multiplier > 0.0, long_observed, short_observed)
    primary_stressed = primary_gross - full_burden

    trades["direction_multiplier"] = direction_multiplier
    trades["entry_mid"] = entry_mid
    trades["exit_mid"] = exit_mid
    trades["entry_spread_usd"] = entry_spread_usd
    trades["exit_spread_usd"] = exit_spread_usd
    trades["gross_usd"] = primary_gross
    trades["observed_usd"] = primary_observed
    trades["stressed_usd"] = primary_stressed
    trades["long_gross_usd"] = long_gross
    trades["long_observed_usd"] = long_observed
    trades["long_stressed_usd"] = long_gross - full_burden
    columns = [
        "date",
        "calendar_month",
        "period",
        "split",
        "direction",
        "classification",
        "sky_cover_mean_oktas",
        "sky_05_oktas",
        "sky_06_oktas",
        "sky_07_oktas",
        "sky_08_oktas",
        "latest_weather_utc",
        "preopen_lead_minutes",
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
        "long_gross_usd",
        "long_observed_usd",
        "long_stressed_usd",
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
    balance = float(starting_balance)
    peak = balance
    maximum_drawdown = 0.0
    for value in array:
        balance += float(value)
        peak = max(peak, balance)
        maximum_drawdown = max(maximum_drawdown, peak - balance)
    return {
        "count": count,
        "net_usd": net,
        "gross_profit_usd": gross_profit,
        "gross_loss_usd": gross_loss,
        "profit_factor": profit_factor,
        "win_rate": float((array > 0.0).mean()),
        "mean_usd": mean,
        "standard_deviation_usd": standard_deviation,
        "mean_to_standard_deviation": mean / standard_deviation if standard_deviation > 0.0 else None,
        "max_closed_drawdown_usd": maximum_drawdown,
        "max_closed_drawdown_percent": 100.0 * maximum_drawdown / float(starting_balance),
        "net_to_drawdown": net / maximum_drawdown if maximum_drawdown > 0.0 else None,
    }


def summarize_slice(frame: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "active_session_days": int(len(frame)),
        "long_days": int((frame["direction"] == "LONG").sum()),
        "short_days": int((frame["direction"] == "SHORT").sum()),
    }
    starting_balance = float(config["trade_rule"]["starting_balance_usd"])
    for cost in COST_COLUMNS:
        result[cost.replace("_usd", "")] = series_metrics(frame[cost], starting_balance)
    return result


def select_view(trades: pd.DataFrame, name: str) -> pd.DataFrame:
    if name == "PRIMARY_WEATHER_DIRECTION":
        selected = trades.copy()
    elif name == "SUNNY_LONG_ONLY":
        selected = trades.loc[trades["direction"] == "LONG"].copy()
    elif name == "CLOUDY_SHORT_ONLY":
        selected = trades.loc[trades["direction"] == "SHORT"].copy()
    elif name == "UNCONDITIONAL_LONG":
        selected = trades.copy()
        for cost in COST_COLUMNS:
            selected[cost] = selected[f"long_{cost}"]
    else:
        raise RuntimeError(f"unknown view: {name}")
    return selected.sort_values("date", kind="stable")


def build_views(trades: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    views: dict[str, Any] = {}
    for name in VIEW_NAMES:
        selected = select_view(trades, name)
        month_nets = selected.groupby("calendar_month", sort=True)["stressed_usd"].sum().astype(float)
        views[name] = {
            "full": summarize_slice(selected, config),
            "periods": {
                period: summarize_slice(selected.loc[selected["period"] == period], config)
                for period in config["periods"]
            },
            "splits": {
                split: summarize_slice(selected.loc[selected["split"] == split], config)
                for split in config["p1_splits"]
            },
            "stressed_month_nets": {str(index): float(value) for index, value in month_nets.items()},
        }
    return views


def metric_value(metric: dict[str, Any], key: str, default: float = float("-inf")) -> float:
    value = metric.get(key)
    return default if value is None else float(value)


def positive_month_fraction(frame: pd.DataFrame) -> tuple[int, int, float | None]:
    month_nets = frame.groupby("calendar_month", sort=True)["stressed_usd"].sum()
    positive = int((month_nets > 0.0).sum())
    active = int(len(month_nets))
    return positive, active, positive / active if active else None


def side_positive(views: dict[str, Any], scope: str, name: str | None = None) -> bool:
    if scope == "periods" and name is not None:
        sunny = views["SUNNY_LONG_ONLY"]["periods"][name]["stressed"]
        cloudy = views["CLOUDY_SHORT_ONLY"]["periods"][name]["stressed"]
    elif scope == "splits" and name is not None:
        sunny = views["SUNNY_LONG_ONLY"]["splits"][name]["stressed"]
        cloudy = views["CLOUDY_SHORT_ONLY"]["splits"][name]["stressed"]
    elif scope == "full":
        sunny = views["SUNNY_LONG_ONLY"]["full"]["stressed"]
        cloudy = views["CLOUDY_SHORT_ONLY"]["full"]["stressed"]
    else:
        raise RuntimeError("unknown side-positive scope")
    return metric_value(sunny, "net_usd") > 0.0 and metric_value(cloudy, "net_usd") > 0.0


def evaluate_gates(
    trades: pd.DataFrame,
    views: dict[str, Any],
    config: dict[str, Any],
    eligibility_integrity: dict[str, Any],
) -> dict[str, Any]:
    gates = config["economic_gates"]
    p1_name = gates["p1_period"]
    latest_name = gates["latest_period"]
    primary = views["PRIMARY_WEATHER_DIRECTION"]
    unconditional = views["UNCONDITIONAL_LONG"]
    p1 = primary["periods"][p1_name]["stressed"]
    p1_frame = select_view(trades, "PRIMARY_WEATHER_DIRECTION")
    p1_frame = p1_frame.loc[p1_frame["period"] == p1_name]
    p1_positive_months, p1_active_months, p1_month_fraction = positive_month_fraction(p1_frame)
    p1_split_checks = {
        split: metric_value(primary["splits"][split]["stressed"], "net_usd") > 0.0
        for split in config["p1_splits"]
    }
    p1_side_positive = side_positive(views, "periods", p1_name)
    p1_beat_unconditional = metric_value(p1, "net_usd") > metric_value(
        unconditional["periods"][p1_name]["stressed"], "net_usd"
    )
    p1_checks = {
        "net_positive": metric_value(p1, "net_usd") > 0.0,
        "profit_factor": metric_value(p1, "profit_factor") >= float(gates["p1_profit_factor_min"]),
        "net_to_drawdown": metric_value(p1, "net_to_drawdown") >= float(gates["p1_net_to_drawdown_min"]),
        "positive_splits": sum(p1_split_checks.values()) >= int(gates["p1_positive_splits_required"]),
        "positive_month_fraction": p1_month_fraction is not None
        and p1_month_fraction >= float(gates["p1_positive_month_fraction_min"]),
        "both_direction_sides_positive": p1_side_positive,
        "beats_unconditional_long": p1_beat_unconditional,
    }

    confirmation_net: dict[str, bool] = {}
    confirmation_beat: dict[str, bool] = {}
    confirmation_sides: dict[str, bool] = {}
    confirmation_month_fractions: dict[str, float | None] = {}
    confirmation_month_checks: dict[str, bool] = {}
    for period in gates["confirmation_periods"]:
        primary_metric = primary["periods"][period]["stressed"]
        unconditional_metric = unconditional["periods"][period]["stressed"]
        period_frame = select_view(trades, "PRIMARY_WEATHER_DIRECTION")
        period_frame = period_frame.loc[period_frame["period"] == period]
        _, _, fraction = positive_month_fraction(period_frame)
        confirmation_net[period] = metric_value(primary_metric, "net_usd") > 0.0
        confirmation_beat[period] = metric_value(primary_metric, "net_usd") > metric_value(
            unconditional_metric, "net_usd"
        )
        confirmation_sides[period] = side_positive(views, "periods", period)
        confirmation_month_fractions[period] = fraction
        confirmation_month_checks[period] = fraction is not None and fraction >= float(
            gates["confirmation_positive_month_fraction_min"]
        )
    confirmation_checks = {
        "positive_periods": sum(confirmation_net.values())
        >= int(gates["confirmation_positive_periods_required"]),
        "beats_unconditional_long_periods": sum(confirmation_beat.values())
        >= int(gates["confirmation_beat_unconditional_periods_required"]),
        "both_sides_positive_periods": sum(confirmation_sides.values())
        >= int(gates["confirmation_both_sides_positive_periods_required"]),
        "positive_month_fraction_periods": sum(confirmation_month_checks.values())
        >= int(gates["confirmation_positive_month_fraction_periods_required"]),
    }

    prelatest_frame = select_view(trades, "PRIMARY_WEATHER_DIRECTION")
    prelatest_frame = prelatest_frame.loc[prelatest_frame["period"] != latest_name]
    prelatest = summarize_slice(prelatest_frame, config)["stressed"]
    prelatest_unconditional_frame = select_view(trades, "UNCONDITIONAL_LONG")
    prelatest_unconditional_frame = prelatest_unconditional_frame.loc[
        prelatest_unconditional_frame["period"] != latest_name
    ]
    prelatest_unconditional = summarize_slice(prelatest_unconditional_frame, config)["stressed"]
    prelatest_sunny = select_view(trades, "SUNNY_LONG_ONLY")
    prelatest_sunny = prelatest_sunny.loc[prelatest_sunny["period"] != latest_name]
    prelatest_cloudy = select_view(trades, "CLOUDY_SHORT_ONLY")
    prelatest_cloudy = prelatest_cloudy.loc[prelatest_cloudy["period"] != latest_name]
    prelatest_sides_positive = (
        metric_value(summarize_slice(prelatest_sunny, config)["stressed"], "net_usd") > 0.0
        and metric_value(summarize_slice(prelatest_cloudy, config)["stressed"], "net_usd") > 0.0
    )
    prelatest_positive_months, prelatest_active_months, prelatest_month_fraction = positive_month_fraction(
        prelatest_frame
    )
    positive_days = prelatest_frame.loc[prelatest_frame["stressed_usd"] > 0.0, "stressed_usd"].sort_values(
        ascending=False
    )
    positive_day_sum = float(positive_days.sum())
    top_five_positive_day_share = (
        float(positive_days.head(5).sum()) / positive_day_sum if positive_day_sum > 0.0 else None
    )
    prelatest_checks = {
        "net_positive": metric_value(prelatest, "net_usd") > 0.0,
        "profit_factor": metric_value(prelatest, "profit_factor")
        >= float(gates["prelatest_profit_factor_min"]),
        "net_to_drawdown": metric_value(prelatest, "net_to_drawdown")
        >= float(gates["prelatest_net_to_drawdown_min"]),
        "positive_month_fraction": prelatest_month_fraction is not None
        and prelatest_month_fraction >= float(gates["prelatest_positive_month_fraction_min"]),
        "top_five_positive_day_share": top_five_positive_day_share is not None
        and top_five_positive_day_share <= float(gates["prelatest_top_five_positive_day_share_max"]),
        "both_direction_sides_positive": prelatest_sides_positive,
        "beats_unconditional_long": metric_value(prelatest, "net_usd")
        > metric_value(prelatest_unconditional, "net_usd"),
    }
    prelatest_nominal_dd = metric_value(
        prelatest, "max_closed_drawdown_percent", float("inf")
    ) <= float(gates["nominal_drawdown_max_percent"])
    prelatest_practical_dd = metric_value(
        prelatest, "max_closed_drawdown_percent", float("inf")
    ) <= float(gates["practical_drawdown_max_percent"])

    latest = primary["periods"][latest_name]["stressed"]
    latest_days = int(primary["periods"][latest_name]["active_session_days"])
    positive_prelatest_mean = max(metric_value(prelatest, "mean_usd", 0.0), 0.0)
    latest_practical_floor = (
        -float(gates["latest_practical_reversal_fraction"])
        * positive_prelatest_mean
        * latest_days
    )
    latest_nominal = metric_value(latest, "net_usd") >= float(gates["latest_nominal_floor_usd"])
    latest_practical = metric_value(latest, "net_usd") >= latest_practical_floor

    full = primary["full"]["stressed"]
    full_side_positive = side_positive(views, "full")
    full_beat_unconditional = metric_value(full, "net_usd") > metric_value(
        unconditional["full"]["stressed"], "net_usd"
    )
    full_checks = {
        "net_positive": metric_value(full, "net_usd") > 0.0,
        "profit_factor": metric_value(full, "profit_factor") >= float(gates["full_profit_factor_min"]),
        "net_to_drawdown": metric_value(full, "net_to_drawdown")
        >= float(gates["full_net_to_drawdown_min"]),
        "both_direction_sides_positive": full_side_positive,
        "beats_unconditional_long": full_beat_unconditional,
    }
    density_passed = bool(eligibility_integrity["density_passed"])
    common_pass = (
        density_passed
        and all(p1_checks.values())
        and all(confirmation_checks.values())
        and all(prelatest_checks.values())
        and all(full_checks.values())
    )
    nominal_pass = common_pass and prelatest_nominal_dd and latest_nominal
    practical_pass = common_pass and prelatest_practical_dd and latest_practical
    strong_null = (
        metric_value(p1, "net_usd") <= 0.0
        and sum(confirmation_net.values()) <= 1
        and metric_value(prelatest, "net_usd") <= 0.0
        and metric_value(full, "net_usd") <= 0.0
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
    retained_seed = (
        "FIXED_LAGUARDIA_0500_0800_SKY_MEAN_0_TO_4_LONG_ELSE_SHORT_US500_CASH"
        if nominal_pass or practical_pass
        else None
    )
    return {
        "density": eligibility_integrity["density_checks"],
        "p1": {
            "checks": p1_checks,
            "split_net_positive": p1_split_checks,
            "positive_months": p1_positive_months,
            "active_months": p1_active_months,
            "positive_month_fraction": p1_month_fraction,
            "primary_stressed": p1,
            "unconditional_long_stressed": unconditional["periods"][p1_name]["stressed"],
        },
        "confirmation": {
            "period_net_positive": confirmation_net,
            "beats_unconditional_long": confirmation_beat,
            "both_sides_positive": confirmation_sides,
            "positive_month_fractions": confirmation_month_fractions,
            "positive_month_fraction_checks": confirmation_month_checks,
            "summary": confirmation_checks,
        },
        "prelatest": {
            "metrics": prelatest,
            "unconditional_long": prelatest_unconditional,
            "positive_months": prelatest_positive_months,
            "active_months": prelatest_active_months,
            "positive_month_fraction": prelatest_month_fraction,
            "top_five_positive_day_share": top_five_positive_day_share,
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
            "unconditional_long": unconditional["full"]["stressed"],
            "checks": full_checks,
        },
        "nominal_pass": nominal_pass,
        "practical_pass": practical_pass,
        "strong_null": strong_null,
        "passed": bool(nominal_pass or practical_pass),
        "verdict": verdict,
        "retained_seed": retained_seed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze the fixed LaGuardia morning-sky US500 cash-direction transfer."
    )
    parser.add_argument("--mode", choices=("premetric", "formal"), required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    config = load_json(CONFIG_PATH)
    input_root = REPO_ROOT / config["input_root"]
    output_root = REPO_ROOT / config["output_root"]
    semantic_hash = semantic_contract_sha256(config)
    input_integrity = verify_inputs(config, input_root)
    acquisition_summary = verify_pinned_file(config["acquisition_summary"], "acquisition summary")
    weather, weather_integrity = load_weather(config, input_root)

    if args.mode == "premetric":
        sessions, inventory, session_integrity = load_calendar(config, input_root, formal=False)
        _, _, eligibility_integrity = assign_weather_roles(
            sessions, inventory, weather, config
        )
        payload = premetric_payload(
            semantic_hash,
            input_integrity,
            acquisition_summary,
            session_integrity,
            weather_integrity,
            eligibility_integrity,
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

    declaration_receipt, declaration = verify_declaration(config)
    premetric_receipt = verify_pinned_file(
        declaration.get("premetric_receipt", {}), "premetric receipt"
    )
    premetric = load_json(REPO_ROOT / premetric_receipt["path"])
    if premetric.get("semantic_contract_sha256") != semantic_hash:
        raise RuntimeError("premetric semantic contract mismatch")
    if any(bool(value) for value in premetric.get("outcome_firewall", {}).values()):
        raise RuntimeError("premetric outcome firewall was not closed")

    sessions, inventory, session_integrity = load_calendar(config, input_root, formal=True)
    declared, event_calendar, eligibility_integrity = assign_weather_roles(
        sessions, inventory, weather, config
    )
    if not eligibility_integrity["density_passed"]:
        raise RuntimeError("declared weather/session density failed before economic aggregation")
    premetric_eligibility = premetric["eligibility_integrity"]
    for key in (
        "official_session_dates",
        "eligible_sessions",
        "eligible_days_by_period",
        "direction_days_by_period",
        "eligible_days_by_p1_split",
        "minimum_preopen_lead_minutes",
        "maximum_preopen_lead_minutes",
        "density_checks",
        "density_passed",
    ):
        if json_safe(eligibility_integrity[key]) != premetric_eligibility[key]:
            raise RuntimeError(f"formal eligibility drift from premetric receipt: {key}")

    spec = load_spec(config, input_root)
    trades = build_trades(declared, spec, config)
    views = build_views(trades, config)
    decision = evaluate_gates(trades, views, config, eligibility_integrity)
    payload = {
        "schema": "zeta-next-us500-preopen-laguardia-sunshine-cash-direction-analysis-v1",
        "status": "COMPLETE_VALID_SOURCE_FIXED_ECONOMIC_AGGREGATION",
        "semantic_contract_sha256": semantic_hash,
        "input_integrity": input_integrity,
        "acquisition_summary": acquisition_summary,
        "premetric_receipt": premetric_receipt,
        "declaration": declaration_receipt,
        "session_integrity": session_integrity,
        "weather_integrity": weather_integrity,
        "eligibility_integrity": eligibility_integrity,
        "trade_integrity": {
            "rows": int(len(trades)),
            "long_rows": int((trades["direction"] == "LONG").sum()),
            "short_rows": int((trades["direction"] == "SHORT").sum()),
            "first_date": trades["date"].iloc[0].date().isoformat(),
            "last_date": trades["date"].iloc[-1].date().isoformat(),
            "minimum_preopen_lead_minutes": float(trades["preopen_lead_minutes"].min()),
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
    targets[0].write_text(
        json.dumps(json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    export_trades = trades.copy()
    export_trades["date"] = export_trades["date"].dt.date.astype(str)
    export_trades.to_csv(targets[1], index=False, lineterminator="\n")
    export_calendar = event_calendar.copy()
    export_calendar["date"] = export_calendar["date"].dt.date.astype(str)
    export_calendar.to_csv(targets[2], index=False, lineterminator="\n")
    print(json.dumps(json_safe(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
