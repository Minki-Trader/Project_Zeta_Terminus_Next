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
VIEW_DIRECTIONS = {
    "PRIMARY": "primary_direction",
    "NO_FLIP": "no_flip_direction",
    "LONG_ONLY": "long_only_direction",
}


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
    if isinstance(value, pd.Period):
        return str(value)
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


def verify_pinned_file(pin: dict[str, Any], label: str) -> dict[str, Any]:
    if not pin.get("path") or not pin.get("bytes") or not pin.get("sha256"):
        raise RuntimeError(f"{label} pin is not frozen")
    path = REPO_ROOT / pin["path"]
    if not path.is_file():
        raise RuntimeError(f"{label} missing: {path}")
    size = path.stat().st_size
    digest = sha256_file(path)
    if size != pin["bytes"] or digest != pin["sha256"]:
        raise RuntimeError(f"{label} pin mismatch")
    return {"path": pin["path"], "bytes": size, "sha256": digest}


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


def load_predictor(
    config: dict[str, Any], input_root: Path
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    author_path = input_root / config["files"]["author_returns"]
    author = pd.read_csv(author_path, sep="\t")
    if list(author.columns) != config["required_author_schema"]:
        raise RuntimeError(f"unexpected author-return schema: {list(author.columns)}")
    if len(author) != int(config["immutable_inputs"]["author_rows"]):
        raise RuntimeError("author-return row count mismatch")
    author["date"] = pd.to_datetime(author["date"], errors="raise")
    author["month"] = author["date"].dt.to_period("M")
    author["monthly_return"] = pd.to_numeric(author["vwretd"], errors="coerce")
    if author["month"].duplicated().any() or not author["month"].is_monotonic_increasing:
        raise RuntimeError("author months are not unique and increasing")
    if int(author["monthly_return"].notna().sum()) != int(
        config["immutable_inputs"]["author_nonmissing_returns"]
    ):
        raise RuntimeError("author nonmissing-return count mismatch")
    if str(author["month"].iloc[0]) != "1925-12" or str(author["month"].iloc[-1]) != "2021-06":
        raise RuntimeError("unexpected author-return range")
    if author.loc[author["monthly_return"].isna(), "month"].astype(str).tolist() != ["1925-12"]:
        raise RuntimeError("unexpected author-return missingness")

    d1_path = input_root / config["files"]["d1_bars"]
    d1_header = pd.read_csv(d1_path, nrows=0)
    if list(d1_header.columns) != config["required_d1_schema"]:
        raise RuntimeError(f"unexpected D1 schema: {list(d1_header.columns)}")
    d1 = pd.read_csv(d1_path, usecols=["time_epoch", "close"])
    if len(d1) != int(config["immutable_inputs"]["d1_rows"]):
        raise RuntimeError("D1 row count mismatch")
    if d1.isna().any().any() or (d1["close"] <= 0.0).any():
        raise RuntimeError("D1 predictor surface contains null or nonpositive values")
    epoch = d1["time_epoch"].astype(np.int64)
    if epoch.duplicated().any() or not epoch.is_monotonic_increasing:
        raise RuntimeError("D1 epochs are not unique and increasing")
    d1["utc"] = pd.to_datetime(epoch, unit="s", utc=True)
    d1["month"] = d1["utc"].dt.tz_localize(None).dt.to_period("M")
    monthly_close = d1.sort_values("time_epoch", kind="stable").groupby("month", sort=True)["close"].last()
    broker_return = monthly_close.pct_change()
    expected_broker_months = pd.period_range("2021-06", "2026-08", freq="M")
    if not monthly_close.index.equals(expected_broker_months):
        missing = expected_broker_months.difference(monthly_close.index).astype(str).tolist()
        raise RuntimeError(f"broker D1 monthly geometry is incomplete: {missing}")

    author_series = author.set_index("month")["monthly_return"].loc[: pd.Period("2021-06", freq="M")]
    bridge_series = broker_return.loc[
        pd.Period("2021-07", freq="M") : pd.Period("2026-07", freq="M")
    ]
    combined = pd.concat([author_series, bridge_series])
    combined.name = "monthly_return"
    expected_combined = pd.period_range("1925-12", "2026-07", freq="M")
    if not combined.index.equals(expected_combined):
        raise RuntimeError("combined monthly return index is not continuous")
    if combined.iloc[1:].isna().any():
        raise RuntimeError("combined monthly return history contains a post-start null")

    newsy_months = set(int(value) for value in config["source_signal_rule"]["newsy_target_months"])
    signal_rows: list[dict[str, Any]] = []
    for origin in combined.index:
        target = origin + 1
        available_newsy = [
            month
            for month in combined.index
            if month <= origin and month.month in newsy_months and pd.notna(combined.loc[month])
        ]
        if len(available_newsy) < 4:
            continue
        selected = available_newsy[-4:]
        raw_sum = float(combined.loc[selected].sum())
        signal_rows.append(
            {
                "origin_month": origin,
                "target_month": target,
                "target_type": "NEWSY" if target.month in newsy_months else "NON_NEWSY",
                "latest_four_newsy_months": ",".join(str(month) for month in selected),
                "raw_four_newsy_sum": raw_sum,
                "future_return": float(combined.loc[target]) if target in combined.index else np.nan,
            }
        )
    signals = pd.DataFrame(signal_rows)
    if signals.empty:
        raise RuntimeError("source predictor construction produced no rows")
    signals["raw_sum_expanding_mean_prior"] = (
        signals["raw_four_newsy_sum"].shift(1).expanding(min_periods=1).mean()
    )
    signals["demeaned_unflipped"] = (
        signals["raw_four_newsy_sum"] - signals["raw_sum_expanding_mean_prior"]
    )
    signals["flipped_demeaned"] = np.where(
        signals["target_type"] == "NEWSY",
        -signals["demeaned_unflipped"],
        signals["demeaned_unflipped"],
    )

    slopes: list[float] = []
    intercepts: list[float] = []
    training_counts: list[int] = []
    training_last_targets: list[str | None] = []
    for index in range(len(signals)):
        prior = signals.iloc[:index]
        valid = prior[["flipped_demeaned", "future_return"]].dropna()
        if len(valid) < 6:
            slopes.append(np.nan)
            intercepts.append(np.nan)
            training_counts.append(int(len(valid)))
            training_last_targets.append(None)
            continue
        design = np.column_stack(
            [valid["flipped_demeaned"].to_numpy(dtype=float), np.ones(len(valid), dtype=float)]
        )
        slope, intercept = np.linalg.lstsq(
            design, valid["future_return"].to_numpy(dtype=float), rcond=None
        )[0]
        slopes.append(float(slope))
        intercepts.append(float(intercept))
        training_counts.append(int(len(valid)))
        last_valid_index = valid.index[-1]
        training_last_targets.append(str(signals.loc[last_valid_index, "target_month"]))
    signals["expanding_beta"] = slopes
    signals["expanding_intercept"] = intercepts
    signals["training_observations"] = training_counts
    signals["training_last_target_month"] = training_last_targets
    signals["paper_excess_weight"] = signals["expanding_beta"] * signals["flipped_demeaned"]
    signals["no_flip_weight"] = signals["expanding_beta"] * signals["demeaned_unflipped"]
    signals["primary_direction"] = np.sign(signals["paper_excess_weight"]).astype("Int64")
    signals["no_flip_direction"] = np.sign(signals["no_flip_weight"]).astype("Int64")
    signals["long_only_direction"] = 1

    target_start = pd.Period(config["return_splice"]["target_start"], freq="M")
    target_end = pd.Period(config["return_splice"]["target_end_exclusive"], freq="M")
    targets = signals.loc[
        (signals["target_month"] >= target_start) & (signals["target_month"] < target_end)
    ].copy()
    if not targets["target_month"].reset_index(drop=True).equals(
        pd.Series(pd.period_range(target_start, target_end - 1, freq="M"))
    ):
        raise RuntimeError("declared target-month predictor coverage is incomplete")
    required_predictor = [
        "raw_sum_expanding_mean_prior",
        "demeaned_unflipped",
        "flipped_demeaned",
        "expanding_beta",
        "paper_excess_weight",
        "no_flip_weight",
        "primary_direction",
        "no_flip_direction",
    ]
    if targets[required_predictor].isna().any().any():
        raise RuntimeError("declared target-month predictor contains a null")
    causal = targets.apply(
        lambda row: pd.Period(row["training_last_target_month"], freq="M") <= row["origin_month"],
        axis=1,
    )
    if not causal.all():
        raise RuntimeError("expanding regression uses a target not known by the origin month")

    direction_counts = {
        "LONG": int((targets["primary_direction"] > 0).sum()),
        "SHORT": int((targets["primary_direction"] < 0).sum()),
        "FLAT": int((targets["primary_direction"] == 0).sum()),
    }
    no_flip_counts = {
        "LONG": int((targets["no_flip_direction"] > 0).sum()),
        "SHORT": int((targets["no_flip_direction"] < 0).sum()),
        "FLAT": int((targets["no_flip_direction"] == 0).sum()),
    }
    integrity = {
        "author_rows": int(len(author)),
        "author_nonmissing_returns": int(author["monthly_return"].notna().sum()),
        "author_first_month": str(author["month"].iloc[0]),
        "author_last_month": str(author["month"].iloc[-1]),
        "broker_d1_rows": int(len(d1)),
        "broker_d1_first_utc": d1["utc"].iloc[0].isoformat(),
        "broker_d1_last_utc": d1["utc"].iloc[-1].isoformat(),
        "broker_months": int(len(monthly_close)),
        "broker_bridge_months": int(len(bridge_series)),
        "combined_months": int(len(combined)),
        "combined_first_month": str(combined.index[0]),
        "combined_last_complete_month": str(combined.index[-1]),
        "target_months": int(len(targets)),
        "target_first_month": str(targets["target_month"].iloc[0]),
        "target_last_month": str(targets["target_month"].iloc[-1]),
        "target_type_month_counts": {
            str(key): int(value) for key, value in targets["target_type"].value_counts().sort_index().items()
        },
        "primary_direction_month_counts": direction_counts,
        "no_flip_direction_month_counts": no_flip_counts,
        "primary_no_flip_direction_disagreement_months": int(
            (targets["primary_direction"] != targets["no_flip_direction"]).sum()
        ),
        "expanding_beta_min": float(targets["expanding_beta"].min()),
        "expanding_beta_max": float(targets["expanding_beta"].max()),
        "minimum_training_observations": int(targets["training_observations"].min()),
        "maximum_training_observations": int(targets["training_observations"].max()),
        "strictly_causal_expanding_regressions": bool(causal.all()),
        "target_economic_fields_opened": False,
    }
    combined_frame = combined.rename_axis("month").reset_index(name="monthly_return")
    return targets.reset_index(drop=True), combined_frame, integrity


def load_sessions(
    config: dict[str, Any], input_root: Path, signals: pd.DataFrame, formal: bool
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    path = input_root / config["files"]["m15_bars"]
    header = pd.read_csv(path, nrows=0)
    required = config["required_m15_schema"]
    if list(header.columns) != required:
        raise RuntimeError(f"unexpected M15 schema: {list(header.columns)}")
    usecols = required if formal else ["time_epoch"]
    frame = pd.read_csv(path, usecols=usecols)
    if len(frame) != int(config["immutable_inputs"]["m15_rows"]):
        raise RuntimeError("M15 row count mismatch")
    if frame.isna().any().any():
        raise RuntimeError("loaded M15 fields contain null values")
    epoch = frame["time_epoch"].astype(np.int64)
    if epoch.duplicated().any() or not epoch.is_monotonic_increasing:
        raise RuntimeError("M15 epochs are not unique and increasing")
    if formal:
        if (frame[["open", "high", "low", "close"]] <= 0.0).any().any():
            raise RuntimeError("M15 surface contains nonpositive prices")
        if (frame["spread"] < 0).any():
            raise RuntimeError("M15 surface contains a negative spread")

    utc = pd.to_datetime(epoch, unit="s", utc=True)
    et = utc.dt.tz_convert(config["trade_rule"]["timezone"])
    entry_minute = int(config["trade_rule"]["entry_minute"])
    exit_minute = int(config["trade_rule"]["exit_bar_minute"])
    minute_of_day = et.dt.hour * 60 + et.dt.minute
    cash_mask = (et.dt.weekday < 5) & (minute_of_day >= entry_minute) & (minute_of_day <= exit_minute)
    selected_columns = ["time_epoch"]
    if formal:
        selected_columns += ["open", "high", "low", "close", "spread"]
    cash = frame.loc[cash_mask, selected_columns].copy()
    cash["utc"] = utc.loc[cash.index]
    cash["et"] = et.loc[cash.index]
    cash["date"] = cash["et"].dt.tz_localize(None).dt.normalize()
    cash["minute_of_day"] = minute_of_day.loc[cash.index]

    expected_minutes = list(range(entry_minute, exit_minute + 1, 15))
    inventory_rows: list[dict[str, Any]] = []
    session_rows: list[dict[str, Any]] = []
    for date, group in cash.groupby("date", sort=True):
        ordered = group.sort_values("minute_of_day", kind="stable")
        minutes = ordered["minute_of_day"].astype(int).tolist()
        full_geometry = minutes == expected_minutes
        boundary_eligible = minutes.count(entry_minute) == 1 and minutes.count(exit_minute) == 1
        inventory_rows.append(
            {
                "date": date,
                "observed_cash_bars": int(len(ordered)),
                "full_bar_geometry": bool(full_geometry),
                "boundary_eligible": bool(boundary_eligible),
            }
        )
        if not boundary_eligible:
            continue
        entry = ordered.loc[ordered["minute_of_day"] == entry_minute].iloc[0]
        exit_row = ordered.loc[ordered["minute_of_day"] == exit_minute].iloc[0]
        row: dict[str, Any] = {
            "date": date,
            "entry_utc": entry["utc"],
            "exit_utc": exit_row["utc"] + pd.Timedelta(minutes=15),
        }
        if formal:
            row.update(
                {
                    "entry_bid": float(entry["open"]),
                    "exit_bid": float(exit_row["close"]),
                    "entry_spread_points": int(entry["spread"]),
                    "exit_spread_points": int(exit_row["spread"]),
                }
            )
        session_rows.append(row)
    inventory = pd.DataFrame(inventory_rows).sort_values("date", kind="stable").reset_index(drop=True)
    sessions = pd.DataFrame(session_rows).sort_values("date", kind="stable").reset_index(drop=True)
    if inventory.empty or sessions.empty:
        raise RuntimeError("cash-session geometry is empty")

    start = min(pd.Timestamp(value["from_inclusive"]) for value in config["periods"].values())
    end_exclusive = max(pd.Timestamp(value["to_exclusive"]) for value in config["periods"].values())
    official_dates = pd.date_range(start, end_exclusive - pd.Timedelta(days=1), freq="B")
    closed_dates = pd.to_datetime(config["official_session_calendar"]["closed_dates"])
    active_closed = closed_dates[(closed_dates >= start) & (closed_dates < end_exclusive)]
    official_dates = official_dates[~official_dates.isin(active_closed)]
    calendar = pd.DataFrame({"date": official_dates})
    calendar = calendar.merge(inventory, on="date", how="left", validate="one_to_one")
    calendar["observed_cash_bars"] = calendar["observed_cash_bars"].fillna(0).astype(int)
    calendar["full_bar_geometry"] = (
        calendar["full_bar_geometry"].astype("boolean").fillna(False).astype(bool)
    )
    calendar["boundary_eligible"] = (
        calendar["boundary_eligible"].astype("boolean").fillna(False).astype(bool)
    )
    observed_target = inventory.loc[(inventory["date"] >= start) & (inventory["date"] < end_exclusive)]
    unofficial_observed = observed_target.loc[~observed_target["date"].isin(set(official_dates))]

    joined = calendar.merge(sessions, on="date", how="left", validate="one_to_one")
    declared = joined.loc[joined["boundary_eligible"]].copy()
    if declared[["entry_utc", "exit_utc"]].isna().any().any():
        raise RuntimeError("eligible official session lacks a fixed boundary")
    declared["period"] = declared["date"].map(lambda value: period_name(value, config))
    declared["split"] = declared["date"].map(lambda value: split_name(value, config))
    declared["target_month"] = declared["date"].dt.to_period("M")
    signal_columns = [
        "target_month",
        "origin_month",
        "target_type",
        "latest_four_newsy_months",
        "raw_four_newsy_sum",
        "raw_sum_expanding_mean_prior",
        "demeaned_unflipped",
        "flipped_demeaned",
        "expanding_beta",
        "expanding_intercept",
        "training_observations",
        "training_last_target_month",
        "paper_excess_weight",
        "no_flip_weight",
        "primary_direction",
        "no_flip_direction",
        "long_only_direction",
    ]
    declared = declared.merge(signals[signal_columns], on="target_month", how="left", validate="many_to_one")
    if declared[signal_columns[1:]].isna().any().any():
        raise RuntimeError("eligible session lacks a causal monthly signal")
    declared["primary_direction_label"] = np.where(
        declared["primary_direction"] > 0,
        "LONG",
        np.where(declared["primary_direction"] < 0, "SHORT", "FLAT"),
    )
    declared["no_flip_direction_label"] = np.where(
        declared["no_flip_direction"] > 0,
        "LONG",
        np.where(declared["no_flip_direction"] < 0, "SHORT", "FLAT"),
    )
    declared = declared.sort_values("date", kind="stable").reset_index(drop=True)

    period_counts = {name: int((declared["period"] == name).sum()) for name in config["periods"]}
    minimums = config["economic_gates"]["minimum_days_by_period"]
    density_checks = {name: period_counts[name] >= int(minimums[name]) for name in minimums}
    target_type_period_counts = {
        target_type: {
            period: int(((declared["target_type"] == target_type) & (declared["period"] == period)).sum())
            for period in config["periods"]
        }
        for target_type in ("NEWSY", "NON_NEWSY")
    }
    direction_period_counts = {
        direction: {
            period: int(
                ((declared["primary_direction_label"] == direction) & (declared["period"] == period)).sum()
            )
            for period in config["periods"]
        }
        for direction in ("LONG", "SHORT", "FLAT")
    }
    split_counts = {name: int((declared["split"] == name).sum()) for name in config["p1_splits"]}
    boundary_ineligible = calendar.loc[~calendar["boundary_eligible"]]
    integrity = {
        "m15_rows": int(len(frame)),
        "m15_first_utc": utc.iloc[0].isoformat(),
        "m15_last_utc": utc.iloc[-1].isoformat(),
        "observed_cash_session_dates": int(len(inventory)),
        "official_target_sessions": int(len(calendar)),
        "official_closure_dates_in_target_range": int(len(active_closed)),
        "declared_boundary_eligible_sessions": int(len(declared)),
        "official_sessions_without_observed_cash_bars": int((calendar["observed_cash_bars"] == 0).sum()),
        "official_sessions_with_bars_but_without_boundaries": int(
            ((calendar["observed_cash_bars"] > 0) & ~calendar["boundary_eligible"]).sum()
        ),
        "official_sessions_without_full_geometry": int((~calendar["full_bar_geometry"]).sum()),
        "boundary_ineligible_dates": boundary_ineligible["date"].dt.date.astype(str).tolist(),
        "observed_cfd_dates_not_official_sessions": int(len(unofficial_observed)),
        "observed_cfd_dates_not_official_session_dates": unofficial_observed["date"].dt.date.astype(str).tolist(),
        "days_by_period": period_counts,
        "days_by_p1_split": split_counts,
        "days_by_target_type_and_period": target_type_period_counts,
        "days_by_primary_direction_and_period": direction_period_counts,
        "primary_no_flip_direction_disagreement_days": int(
            (declared["primary_direction"] != declared["no_flip_direction"]).sum()
        ),
        "density_checks": density_checks,
        "density_passed": bool(all(density_checks.values())),
        "target_price_or_spread_fields_loaded": formal,
    }
    return declared, calendar, integrity


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
    return {**spec, "contract_size": contract_size, "tick_value": tick_value}


def build_trades(sessions: pd.DataFrame, spec: dict[str, Any], config: dict[str, Any]) -> pd.DataFrame:
    point = float(spec["point"])
    contract_size = float(spec["contract_size"])
    volume = float(config["trade_rule"]["volume"])
    base = sessions.copy().sort_values("date", kind="stable").reset_index(drop=True)
    base["entry_mid"] = base["entry_bid"].astype(float) + 0.5 * base["entry_spread_points"].astype(float) * point
    base["exit_mid"] = base["exit_bid"].astype(float) + 0.5 * base["exit_spread_points"].astype(float) * point
    base["entry_spread_usd"] = base["entry_spread_points"].astype(float) * point * contract_size * volume
    base["exit_spread_usd"] = base["exit_spread_points"].astype(float) * point * contract_size * volume
    full_burden = base["entry_spread_usd"] + base["exit_spread_usd"]
    rows: list[pd.DataFrame] = []
    for view, direction_column in VIEW_DIRECTIONS.items():
        frame = base.copy()
        frame["view"] = view
        frame["direction"] = frame[direction_column].astype(int)
        frame["direction_label"] = np.where(
            frame["direction"] > 0,
            "LONG",
            np.where(frame["direction"] < 0, "SHORT", "FLAT"),
        )
        active = frame["direction"].abs().astype(float)
        frame["gross_usd"] = (
            frame["direction"].astype(float)
            * (frame["exit_mid"] - frame["entry_mid"])
            * contract_size
            * volume
        )
        frame["observed_usd"] = frame["gross_usd"] - active * 0.5 * full_burden
        frame["stressed_usd"] = frame["gross_usd"] - active * full_burden
        rows.append(frame)
    trades = pd.concat(rows, ignore_index=True)
    trades["calendar_month"] = trades["date"].dt.strftime("%Y-%m")
    columns = [
        "date",
        "calendar_month",
        "period",
        "split",
        "target_month",
        "origin_month",
        "target_type",
        "view",
        "direction",
        "direction_label",
        "latest_four_newsy_months",
        "raw_four_newsy_sum",
        "raw_sum_expanding_mean_prior",
        "demeaned_unflipped",
        "flipped_demeaned",
        "expanding_beta",
        "expanding_intercept",
        "training_observations",
        "training_last_target_month",
        "paper_excess_weight",
        "no_flip_weight",
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
    return trades[columns].sort_values(["view", "date"], kind="stable").reset_index(drop=True)


def series_metrics(frame: pd.DataFrame, value_column: str, starting_balance: float) -> dict[str, Any]:
    ordered = frame.sort_values("date", kind="stable")
    array = ordered[value_column].to_numpy(dtype=float)
    count = int(len(array))
    trade_count = int((ordered["direction"] != 0).sum()) if count else 0
    if count == 0:
        return {
            "eligible_days": 0,
            "trade_count": 0,
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
    max_drawdown = 0.0
    for value in array:
        balance += float(value)
        peak = max(peak, balance)
        max_drawdown = max(max_drawdown, peak - balance)
    return {
        "eligible_days": count,
        "trade_count": trade_count,
        "net_usd": net,
        "gross_profit_usd": gross_profit,
        "gross_loss_usd": gross_loss,
        "profit_factor": profit_factor,
        "win_rate": float((array > 0.0).mean()),
        "mean_usd": mean,
        "standard_deviation_usd": standard_deviation,
        "mean_to_standard_deviation": mean / standard_deviation if standard_deviation > 0.0 else None,
        "max_closed_drawdown_usd": max_drawdown,
        "max_closed_drawdown_percent": 100.0 * max_drawdown / float(starting_balance),
        "net_to_drawdown": net / max_drawdown if max_drawdown > 0.0 else None,
    }


def summarize_slice(frame: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    starting_balance = float(config["trade_rule"]["starting_balance_usd"])
    return {
        column.replace("_usd", ""): series_metrics(frame, column, starting_balance)
        for column in COST_COLUMNS
    }


def build_views(trades: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    views: dict[str, Any] = {}
    for view in VIEW_DIRECTIONS:
        selected = trades.loc[trades["view"] == view].copy()
        views[view] = {
            "full": summarize_slice(selected, config),
            "periods": {
                period: summarize_slice(selected.loc[selected["period"] == period], config)
                for period in config["periods"]
            },
            "splits": {
                split: summarize_slice(selected.loc[selected["split"] == split], config)
                for split in config["p1_splits"]
            },
            "target_types": {
                target_type: {
                    "full": summarize_slice(selected.loc[selected["target_type"] == target_type], config),
                    "periods": {
                        period: summarize_slice(
                            selected.loc[
                                (selected["target_type"] == target_type) & (selected["period"] == period)
                            ],
                            config,
                        )
                        for period in config["periods"]
                    },
                }
                for target_type in ("NEWSY", "NON_NEWSY")
            },
            "directions": {
                direction: {
                    "full": summarize_slice(selected.loc[selected["direction_label"] == direction], config),
                    "periods": {
                        period: summarize_slice(
                            selected.loc[
                                (selected["direction_label"] == direction) & (selected["period"] == period)
                            ],
                            config,
                        )
                        for period in config["periods"]
                    },
                }
                for direction in ("LONG", "SHORT", "FLAT")
            },
            "stressed_month_nets": (
                selected.groupby("calendar_month", sort=True)["stressed_usd"].sum().astype(float).to_dict()
            ),
        }
    return views


def metric_value(metric: dict[str, Any], key: str, default: float = float("-inf")) -> float:
    value = metric.get(key)
    return default if value is None else float(value)


def evaluate_gates(
    trades: pd.DataFrame, views: dict[str, Any], config: dict[str, Any], session_integrity: dict[str, Any]
) -> dict[str, Any]:
    gates = config["economic_gates"]
    p1_name = gates["p1_period"]
    latest_name = gates["latest_period"]
    primary = views["PRIMARY"]
    p1 = primary["periods"][p1_name]["stressed"]
    p1_splits = {
        name: metric_value(primary["splits"][name]["stressed"], "net_usd") > 0.0
        for name in config["p1_splits"]
    }
    p1_target_types = {
        target_type: metric_value(
            primary["target_types"][target_type]["periods"][p1_name]["stressed"], "net_usd"
        )
        > 0.0
        for target_type in ("NEWSY", "NON_NEWSY")
    }
    p1_directions = {
        direction: metric_value(
            primary["directions"][direction]["periods"][p1_name]["stressed"], "net_usd"
        )
        > 0.0
        for direction in ("LONG", "SHORT")
    }
    p1_mean = metric_value(p1, "mean_usd")
    p1_no_flip_mean = metric_value(views["NO_FLIP"]["periods"][p1_name]["stressed"], "mean_usd")
    p1_long_mean = metric_value(views["LONG_ONLY"]["periods"][p1_name]["stressed"], "mean_usd")
    p1_checks = {
        "net_positive": metric_value(p1, "net_usd") > 0.0,
        "profit_factor": metric_value(p1, "profit_factor") >= float(gates["p1_profit_factor_min"]),
        "net_to_drawdown": metric_value(p1, "net_to_drawdown")
        >= float(gates["p1_net_to_drawdown_min"]),
        "positive_splits": sum(p1_splits.values()) >= int(gates["p1_positive_splits_required"]),
        "positive_target_types": sum(p1_target_types.values())
        >= int(gates["p1_positive_target_types_required"]),
        "positive_directions": sum(p1_directions.values())
        >= int(gates["p1_positive_directions_required"]),
        "mean_above_no_flip": p1_mean > p1_no_flip_mean,
        "mean_above_long_only": p1_mean > p1_long_mean,
    }

    confirmation_periods = gates["confirmation_periods"]
    period_positive: dict[str, bool] = {}
    target_type_cells: dict[str, bool] = {}
    control_checks: dict[str, dict[str, bool]] = {}
    for period in confirmation_periods:
        primary_metric = primary["periods"][period]["stressed"]
        primary_mean = metric_value(primary_metric, "mean_usd")
        period_positive[period] = metric_value(primary_metric, "net_usd") > 0.0
        for target_type in ("NEWSY", "NON_NEWSY"):
            target_type_cells[f"{target_type}:{period}"] = metric_value(
                primary["target_types"][target_type]["periods"][period]["stressed"], "net_usd"
            ) > 0.0
        control_checks[period] = {
            "mean_above_no_flip": primary_mean
            > metric_value(views["NO_FLIP"]["periods"][period]["stressed"], "mean_usd"),
            "mean_above_long_only": primary_mean
            > metric_value(views["LONG_ONLY"]["periods"][period]["stressed"], "mean_usd"),
        }
    confirmation_summary = {
        "positive_periods": sum(period_positive.values())
        >= int(gates["confirmation_positive_periods_required"]),
        "positive_target_type_period_cells": sum(target_type_cells.values())
        >= int(gates["confirmation_positive_target_type_period_cells_required"]),
        "mean_above_each_control_periods": sum(all(value.values()) for value in control_checks.values())
        >= int(gates["confirmation_mean_above_each_control_periods_required"]),
    }

    primary_rows = trades.loc[trades["view"] == "PRIMARY"].copy()
    prelatest_frame = primary_rows.loc[primary_rows["period"] != latest_name].copy()
    prelatest = summarize_slice(prelatest_frame, config)["stressed"]
    prelatest_controls = {
        view: summarize_slice(
            trades.loc[(trades["view"] == view) & (trades["period"] != latest_name)], config
        )["stressed"]
        for view in ("NO_FLIP", "LONG_ONLY")
    }
    month_nets = prelatest_frame.groupby("calendar_month", sort=True)["stressed_usd"].sum()
    positive_months = int((month_nets > 0.0).sum())
    active_months = int(len(month_nets))
    positive_days = prelatest_frame.loc[prelatest_frame["stressed_usd"] > 0.0, "stressed_usd"].sort_values(
        ascending=False
    )
    positive_day_sum = float(positive_days.sum())
    top_five_share = float(positive_days.head(5).sum()) / positive_day_sum if positive_day_sum > 0.0 else None
    prelatest_directions = {
        direction: metric_value(
            summarize_slice(prelatest_frame.loc[prelatest_frame["direction_label"] == direction], config)[
                "stressed"
            ],
            "net_usd",
        )
        > 0.0
        for direction in ("LONG", "SHORT")
    }
    prelatest_mean = metric_value(prelatest, "mean_usd")
    prelatest_common = {
        "net_positive": metric_value(prelatest, "net_usd") > 0.0,
        "profit_factor": metric_value(prelatest, "profit_factor")
        >= float(gates["prelatest_profit_factor_min"]),
        "net_to_drawdown": metric_value(prelatest, "net_to_drawdown")
        >= float(gates["prelatest_net_to_drawdown_min"]),
        "positive_month_fraction": active_months > 0
        and positive_months / active_months >= float(gates["prelatest_positive_month_fraction_min"]),
        "top_five_positive_day_share": top_five_share is not None
        and top_five_share <= float(gates["prelatest_top_five_positive_day_share_max"]),
        "positive_directions": sum(prelatest_directions.values())
        >= int(gates["prelatest_positive_directions_required"]),
        "mean_above_no_flip": prelatest_mean > metric_value(prelatest_controls["NO_FLIP"], "mean_usd"),
        "mean_above_long_only": prelatest_mean > metric_value(prelatest_controls["LONG_ONLY"], "mean_usd"),
    }
    nominal_dd = metric_value(prelatest, "max_closed_drawdown_percent", float("inf")) <= float(
        gates["nominal_drawdown_max_percent"]
    )
    practical_dd = metric_value(prelatest, "max_closed_drawdown_percent", float("inf")) <= float(
        gates["practical_drawdown_max_percent"]
    )

    latest = primary["periods"][latest_name]["stressed"]
    latest_net = metric_value(latest, "net_usd")
    positive_prelatest_mean = max(metric_value(prelatest, "mean_usd", 0.0), 0.0)
    latest_practical_floor = -float(gates["latest_practical_reversal_fraction"]) * positive_prelatest_mean * int(
        latest["eligible_days"]
    )
    latest_nominal = latest_net >= float(gates["latest_nominal_floor_usd"])
    latest_practical = latest_net >= latest_practical_floor

    full = primary["full"]["stressed"]
    full_checks = {
        "net_positive": metric_value(full, "net_usd") > 0.0,
        "profit_factor": metric_value(full, "profit_factor") >= float(gates["full_profit_factor_min"]),
        "net_to_drawdown": metric_value(full, "net_to_drawdown")
        >= float(gates["full_net_to_drawdown_min"]),
    }
    common_pass = (
        bool(session_integrity["density_passed"])
        and all(p1_checks.values())
        and all(confirmation_summary.values())
        and all(prelatest_common.values())
        and all(full_checks.values())
    )
    nominal_pass = common_pass and nominal_dd and latest_nominal
    practical_pass = common_pass and practical_dd and latest_practical
    strong_null = (
        metric_value(p1, "net_usd") <= 0.0
        and sum(period_positive.values()) <= 1
        and metric_value(prelatest, "net_usd") <= 0.0
        and metric_value(full, "net_usd") <= 0.0
    )
    if nominal_pass:
        verdict = "PASS_RETAIN_ONE_RFS_NEWSY_MONTH_US500_CASH_SESSION_DIRECTION_SEED"
    elif practical_pass:
        verdict = "PASS_PRACTICAL_RETAIN_ONE_RFS_NEWSY_MONTH_US500_CASH_SESSION_DIRECTION_SEED"
    elif strong_null:
        verdict = "VALID_NO_RFS_NEWSY_MONTH_US500_CASH_SESSION_DIRECTION_AFTER_COST_NO_SEED"
    else:
        verdict = "AMBIGUOUS_RFS_NEWSY_MONTH_US500_CASH_SESSION_DIRECTION_NO_SEED"
    retained_seed = (
        "FIXED_RFS_NEWSY_MONTH_US500_CASH_SESSION_DIRECTION"
        if nominal_pass or practical_pass
        else None
    )
    return {
        "density": session_integrity["density_checks"],
        "p1": p1_checks,
        "p1_splits": p1_splits,
        "p1_target_types": p1_target_types,
        "p1_directions": p1_directions,
        "p1_controls": {
            "primary_mean_usd": p1_mean,
            "no_flip_mean_usd": p1_no_flip_mean,
            "long_only_mean_usd": p1_long_mean,
        },
        "confirmation": {
            "period_net_positive": period_positive,
            "target_type_period_net_positive": target_type_cells,
            "control_comparisons": control_checks,
            "summary": confirmation_summary,
        },
        "prelatest": {
            "metrics": prelatest,
            "controls": prelatest_controls,
            "direction_net_positive": prelatest_directions,
            "positive_months": positive_months,
            "active_months": active_months,
            "positive_month_fraction": positive_months / active_months if active_months else None,
            "top_five_positive_day_share": top_five_share,
            "common_checks": prelatest_common,
            "nominal_drawdown_check": nominal_dd,
            "practical_drawdown_check": practical_dd,
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
        description="Analyze the fixed RFS earnings-extrapolation monthly signal on US500 cash sessions."
    )
    parser.add_argument("--mode", choices=("premetric", "formal"), required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    config = load_json(CONFIG_PATH)
    input_root = REPO_ROOT / config["input_root"]
    output_root = REPO_ROOT / config["output_root"]
    input_integrity = verify_inputs(config, input_root)
    acquisition = verify_pinned_file(config["acquisition_summary"], "acquisition summary")
    signals, combined_returns, predictor_integrity = load_predictor(config, input_root)

    if args.mode == "premetric":
        sessions, _, session_integrity = load_sessions(config, input_root, signals, formal=False)
        payload = {
            "schema": "zeta-next-us500-earnings-extrapolation-monthly-signal-premetric-v1",
            "status": "COMPLETE_SOURCE_PREDICTOR_AND_SESSION_GEOMETRY_TARGET_ECONOMICS_UNOPENED",
            "input_integrity": input_integrity,
            "acquisition_summary": acquisition,
            "predictor_integrity": predictor_integrity,
            "session_integrity": session_integrity,
            "session_rows": int(len(sessions)),
            "outcome_firewall": {
                "target_m15_price_or_spread_fields_loaded": False,
                "cash_session_return_calculated": False,
                "gross_observed_or_stressed_usd_calculated": False,
                "profit_factor_or_drawdown_calculated": False,
                "economic_gate_or_verdict_calculated": False,
            },
            "elapsed_seconds": time.perf_counter() - started,
        }
        print(json.dumps(json_safe(payload), indent=2, sort_keys=True))
        return 0

    declaration = verify_pinned_file(config["formal_declaration"], "formal declaration")
    sessions, calendar, session_integrity = load_sessions(config, input_root, signals, formal=True)
    if not session_integrity["density_passed"]:
        raise RuntimeError("declared session density failed before economic aggregation")
    spec = load_spec(config, input_root)
    trades = build_trades(sessions, spec, config)
    views = build_views(trades, config)
    decision = evaluate_gates(trades, views, config, session_integrity)
    primary_rows = trades.loc[trades["view"] == "PRIMARY"]
    payload = {
        "schema": "zeta-next-us500-earnings-extrapolation-monthly-signal-analysis-v1",
        "status": "COMPLETE_VALID_SOURCE_FIXED_ECONOMIC_AGGREGATION",
        "input_integrity": input_integrity,
        "acquisition_summary": acquisition,
        "declaration": declaration,
        "predictor_integrity": predictor_integrity,
        "session_integrity": session_integrity,
        "trade_integrity": {
            "all_view_rows": int(len(trades)),
            "primary_rows": int(len(primary_rows)),
            "primary_long_days": int((primary_rows["direction"] > 0).sum()),
            "primary_short_days": int((primary_rows["direction"] < 0).sum()),
            "primary_flat_days": int((primary_rows["direction"] == 0).sum()),
            "first_date": primary_rows["date"].iloc[0].date().isoformat(),
            "last_date": primary_rows["date"].iloc[-1].date().isoformat(),
            "zero_entry_spread_rows_primary": int((primary_rows["entry_spread_points"] == 0).sum()),
            "zero_exit_spread_rows_primary": int((primary_rows["exit_spread_points"] == 0).sum()),
        },
        "views": views,
        "decision": decision,
        "elapsed_seconds": time.perf_counter() - started,
    }
    targets = [
        output_root / "analysis-result.json",
        output_root / "trades.csv",
        output_root / "signals.csv",
        output_root / "combined-monthly-returns.csv",
        output_root / "calendar.csv",
    ]
    if any(path.exists() for path in targets):
        raise RuntimeError("formal output target already exists")
    output_root.mkdir(parents=True, exist_ok=True)
    targets[0].write_text(json.dumps(json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    export_trades = trades.copy()
    export_trades["date"] = export_trades["date"].dt.date.astype(str)
    export_trades["target_month"] = export_trades["target_month"].astype(str)
    export_trades["origin_month"] = export_trades["origin_month"].astype(str)
    export_trades.to_csv(targets[1], index=False, lineterminator="\n")
    export_signals = signals.copy()
    export_signals["target_month"] = export_signals["target_month"].astype(str)
    export_signals["origin_month"] = export_signals["origin_month"].astype(str)
    export_signals.to_csv(targets[2], index=False, lineterminator="\n")
    export_returns = combined_returns.copy()
    export_returns["month"] = export_returns["month"].astype(str)
    export_returns.to_csv(targets[3], index=False, lineterminator="\n")
    export_calendar = calendar.copy()
    export_calendar["date"] = export_calendar["date"].dt.date.astype(str)
    export_calendar.to_csv(targets[4], index=False, lineterminator="\n")
    print(json.dumps(json_safe(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
