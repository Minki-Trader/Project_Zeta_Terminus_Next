from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


FAMILY_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = FAMILY_ROOT / "config" / "contract.json"


class CorrectionRequired(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CorrectionRequired(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def finite_or_none(value: float | int | None) -> float | int | None:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def verify_inputs(config: dict[str, Any], input_root: Path) -> dict[str, Any]:
    manifest_rows: list[str] = []
    verified: list[dict[str, Any]] = []
    for item in config["immutable_inputs"]["files"]:
        path = REPO_ROOT / item["path"]
        require(path.is_file(), f"missing immutable input: {item['path']}")
        size = path.stat().st_size
        digest = sha256_file(path)
        require(size == item["bytes"], f"byte mismatch: {item['path']}")
        require(digest == item["sha256"], f"hash mismatch: {item['path']}")
        relative = path.relative_to(input_root).as_posix()
        require(relative == item["name"], f"relative-name mismatch: {item['path']}")
        manifest_rows.append(f"{relative}|{size}|{digest}")
        verified.append({"path": item["path"], "bytes": size, "sha256": digest})
    manifest_text = "\n".join(sorted(manifest_rows)).encode("utf-8")
    manifest_sha = hashlib.sha256(manifest_text).hexdigest().upper()
    require(
        manifest_sha == config["immutable_inputs"]["manifest_sha256"],
        "immutable input manifest mismatch",
    )
    receipt = load_json(input_root / "spec" / "acquisition-receipt.json")
    require(
        receipt.get("schema") == "zeta-dd20-dual-portfolio-market-acquisition-receipt-v1",
        "copied acquisition receipt schema mismatch",
    )
    series = {entry["id"]: entry for entry in receipt["series"]}
    for symbol in config["symbols"]:
        ident = f"{symbol}_M1"
        expected = next(x for x in config["immutable_inputs"]["files"] if x["name"] == config["bar_files"][symbol])
        require(ident in series, f"missing receipt series {ident}")
        require(series[ident]["rows"] == expected["rows"], f"receipt rows mismatch {ident}")
        require(series[ident]["bytes"] == expected["bytes"], f"receipt bytes mismatch {ident}")
        require(series[ident]["sha256"] == expected["sha256"], f"receipt hash mismatch {ident}")
        spec = receipt["symbols"][symbol]
        frozen = config["trade_spec"]
        for key in ("point", "trade_contract_size", "trade_tick_size", "trade_tick_value"):
            require(float(spec[key]) == float(frozen[key]), f"symbol spec mismatch {symbol} {key}")
        require(float(spec["volume_min"]) == frozen["volume"], f"minimum volume mismatch {symbol}")
        require(float(spec["volume_step"]) == frozen["volume"], f"volume step mismatch {symbol}")
    return {
        "files": verified,
        "manifest_sha256": manifest_sha,
        "receipt_sha256": sha256_file(input_root / "spec" / "acquisition-receipt.json"),
    }


def load_complete_sessions(
    symbol: str,
    config: dict[str, Any],
    input_root: Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    relative = config["bar_files"][symbol]
    expected = next(x for x in config["immutable_inputs"]["files"] if x["name"] == relative)
    path = input_root / relative
    schema = pq.read_schema(path)
    required_schema = config["required_schema"]
    require(schema.names == list(required_schema), f"column order mismatch {symbol}")
    for field in schema:
        require(str(field.type) == required_schema[field.name], f"type mismatch {symbol} {field.name}")
    frame = pd.read_parquet(path)
    require(len(frame) == expected["rows"], f"row count mismatch {symbol}")
    require(not frame.isna().any().any(), f"null value in {symbol}")
    require(frame["time"].is_monotonic_increasing, f"nonmonotonic time {symbol}")
    require(not frame["time"].duplicated().any(), f"duplicate time {symbol}")
    require(bool((frame["time"] % 60 == 0).all()), f"non-minute epoch {symbol}")
    first_utc = pd.to_datetime(int(frame["time"].iloc[0]), unit="s", utc=True).isoformat()
    last_utc = pd.to_datetime(int(frame["time"].iloc[-1]), unit="s", utc=True).isoformat()
    require(first_utc == expected["first_utc"], f"first UTC mismatch {symbol}")
    require(last_utc == expected["last_utc"], f"last UTC mismatch {symbol}")
    prices = frame[["open", "high", "low", "close"]].to_numpy(dtype=float)
    require(bool(np.isfinite(prices).all()), f"nonfinite price {symbol}")
    require(bool((prices > 0).all()), f"nonpositive price {symbol}")
    require(bool((frame["high"] >= frame[["open", "close"]].max(axis=1)).all()), f"high geometry {symbol}")
    require(bool((frame["low"] <= frame[["open", "close"]].min(axis=1)).all()), f"low geometry {symbol}")
    require(bool((frame["high"] >= frame["low"]).all()), f"range geometry {symbol}")
    require(bool((frame["tick_volume"] > 0).all()), f"nonpositive tick volume {symbol}")
    require(bool((frame["spread"] >= 0).all()), f"negative spread {symbol}")
    require(bool((frame["real_volume"] >= 0).all()), f"negative real volume {symbol}")

    timezone = config["fixed_rule"]["timezone"]
    local = pd.to_datetime(frame["time"], unit="s", utc=True).dt.tz_convert(timezone)
    frame = frame.assign(
        local_date=local.dt.tz_localize(None).dt.normalize(),
        minute=local.dt.hour * 60 + local.dt.minute,
    )
    regular = frame[(frame["minute"] >= 570) & (frame["minute"] <= 959)]
    point = float(config["trade_spec"]["point"])
    records: list[dict[str, Any]] = []
    incomplete_distribution: dict[str, int] = {}
    for date, group in regular.groupby("local_date", sort=True):
        group = group.sort_values("minute")
        minutes = group["minute"].to_numpy(dtype=int)
        complete = (
            len(group) == 390
            and np.array_equal(minutes, np.arange(570, 960, dtype=int))
        )
        if not complete:
            key = str(len(group))
            incomplete_distribution[key] = incomplete_distribution.get(key, 0) + 1
            continue
        indexed = group.set_index("minute")
        entry = indexed.loc[930]
        close = indexed.loc[959]
        entry_spread = float(entry["spread"]) * point
        exit_spread = float(close["spread"]) * point
        records.append(
            {
                "date": pd.Timestamp(date),
                "entry_epoch": int(entry["time"]),
                "exit_epoch": int(close["time"]) + 60,
                "entry_bid": float(entry["open"]),
                "entry_spread": entry_spread,
                "entry_mid": float(entry["open"]) + 0.5 * entry_spread,
                "exit_bid": float(close["close"]),
                "exit_spread": exit_spread,
                "exit_mid": float(close["close"]) + 0.5 * exit_spread,
            }
        )
    sessions = pd.DataFrame(records).set_index("date").sort_index()
    return sessions, {
        "rows": int(len(frame)),
        "first_utc": first_utc,
        "last_utc": last_utc,
        "complete_sessions": int(len(sessions)),
        "incomplete_regular_session_distribution": dict(sorted(incomplete_distribution.items(), key=lambda x: int(x[0]))),
    }


def period_for_date(date: pd.Timestamp, config: dict[str, Any]) -> str | None:
    for name, bounds in config["periods"].items():
        if pd.Timestamp(bounds["from_inclusive"]) <= date < pd.Timestamp(bounds["to_exclusive"]):
            return name
    return None


def split_for_date(date: pd.Timestamp, config: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for name, bounds in config["period_splits"].items():
        if pd.Timestamp(bounds["from_inclusive"]) <= date < pd.Timestamp(bounds["to_exclusive"]):
            names.append(name)
    return names


def build_trades(
    sessions: dict[str, pd.DataFrame],
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    symbols = config["symbols"]
    common = sessions[symbols[0]].index
    for symbol in symbols[1:]:
        common = common.intersection(sessions[symbol].index)
    common = common.sort_values()
    spec = config["trade_spec"]
    scale = float(spec["trade_contract_size"]) * float(spec["volume"])
    trades: list[dict[str, Any]] = []
    days: list[dict[str, Any]] = []
    gap_counts: dict[str, int] = {}
    eligible_all_dates = 0
    for index in range(1, len(common)):
        date = pd.Timestamp(common[index])
        prior_date = pd.Timestamp(common[index - 1])
        gap = int((date - prior_date).days)
        if gap < 1 or gap > 4:
            continue
        eligible_all_dates += 1
        gap_counts[str(gap)] = gap_counts.get(str(gap), 0) + 1
        period = period_for_date(date, config)
        if period is None:
            continue
        day_row: dict[str, Any] = {
            "date": date.date().isoformat(),
            "prior_date": prior_date.date().isoformat(),
            "gap_days": gap,
            "period": period,
        }
        signs: dict[str, int] = {}
        day_stressed = 0.0
        for symbol in symbols:
            current = sessions[symbol].loc[date]
            prior = sessions[symbol].loc[prior_date]
            predictor = float(current["entry_mid"] / prior["exit_mid"] - 1.0)
            require(predictor != 0.0, f"zero predictor {symbol} {date.date()}")
            direction = 1 if predictor > 0.0 else -1
            gross = direction * (float(current["exit_mid"]) - float(current["entry_mid"])) * scale
            spread_burden = (float(current["entry_spread"]) + float(current["exit_spread"])) * scale
            observed = gross - 0.5 * spread_burden
            stressed = gross - spread_burden
            if direction > 0:
                executable = (float(current["exit_bid"]) - (float(current["entry_bid"]) + float(current["entry_spread"]))) * scale
            else:
                executable = (float(current["entry_bid"]) - (float(current["exit_bid"]) + float(current["exit_spread"]))) * scale
            require(abs(observed - executable) <= 1e-9, f"bid-ask identity {symbol} {date.date()}")
            signs[symbol] = direction
            day_stressed += stressed
            trades.append(
                {
                    "date": date.date().isoformat(),
                    "prior_date": prior_date.date().isoformat(),
                    "period": period,
                    "splits": ";".join(split_for_date(date, config)),
                    "symbol": symbol,
                    "entry_epoch": int(current["entry_epoch"]),
                    "exit_epoch": int(current["exit_epoch"]),
                    "predictor_return": predictor,
                    "direction": direction,
                    "entry_bid": float(current["entry_bid"]),
                    "entry_spread": float(current["entry_spread"]),
                    "exit_bid": float(current["exit_bid"]),
                    "exit_spread": float(current["exit_spread"]),
                    "gross_usd": gross,
                    "observed_usd": observed,
                    "stressed_usd": stressed,
                }
            )
        day_row["US30_direction"] = signs["US30"]
        day_row["US100_direction"] = signs["US100"]
        day_row["direction_relation"] = "SAME" if signs["US30"] == signs["US100"] else "OPPOSITE"
        day_row["stressed_usd"] = day_stressed
        days.append(day_row)
    trades_frame = pd.DataFrame(trades).sort_values(["exit_epoch", "symbol", "entry_epoch"]).reset_index(drop=True)
    days_frame = pd.DataFrame(days).sort_values("date").reset_index(drop=True)
    return trades_frame, days_frame, {
        "common_complete_sessions": int(len(common)),
        "eligible_with_prior_gap_1_to_4_all_dates": eligible_all_dates,
        "gap_days": dict(sorted(gap_counts.items(), key=lambda x: int(x[0]))),
    }


def one_metric(frame: pd.DataFrame, column: str, starting_balance: float) -> dict[str, Any]:
    values = frame[column].to_numpy(dtype=float)
    count = int(len(values))
    net = float(values.sum()) if count else 0.0
    wins = values[values > 0.0]
    losses = values[values < 0.0]
    zeros = int((values == 0.0).sum())
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(losses.sum()) if len(losses) else 0.0
    profit_factor = gross_profit / abs(gross_loss) if gross_loss < 0.0 else None
    if count:
        balance = starting_balance + np.cumsum(values)
        peaks = np.maximum.accumulate(np.concatenate(([starting_balance], balance)))
        drawdowns = peaks[1:] - balance
        max_drawdown = float(drawdowns.max(initial=0.0))
        minimum_balance = float(balance.min())
    else:
        max_drawdown = 0.0
        minimum_balance = starting_balance
    net_to_drawdown = net / max_drawdown if max_drawdown > 0.0 else None
    return {
        "count": count,
        "net_usd": net,
        "gross_profit_usd": gross_profit,
        "gross_loss_usd": gross_loss,
        "profit_factor": finite_or_none(profit_factor),
        "wins": int(len(wins)),
        "losses": int(len(losses)),
        "zeros": zeros,
        "win_rate": float(len(wins) / count) if count else None,
        "mean_usd": float(values.mean()) if count else None,
        "median_usd": float(np.median(values)) if count else None,
        "minimum_usd": float(values.min()) if count else None,
        "maximum_usd": float(values.max()) if count else None,
        "max_closed_drawdown_usd": max_drawdown,
        "max_closed_drawdown_percent": max_drawdown / starting_balance * 100.0,
        "net_to_drawdown": finite_or_none(net_to_drawdown),
        "ending_balance_usd": starting_balance + net,
        "minimum_balance_usd": minimum_balance,
    }


def book(frame: pd.DataFrame, starting_balance: float) -> dict[str, Any]:
    ordered = frame.sort_values(["exit_epoch", "symbol", "entry_epoch"])
    return {
        "gross": one_metric(ordered, "gross_usd", starting_balance),
        "observed": one_metric(ordered, "observed_usd", starting_balance),
        "stressed": one_metric(ordered, "stressed_usd", starting_balance),
    }


def subset_by_bounds(frame: pd.DataFrame, bounds: dict[str, str]) -> pd.DataFrame:
    dates = pd.to_datetime(frame["date"])
    return frame[(dates >= bounds["from_inclusive"]) & (dates < bounds["to_exclusive"])]


def structural_summary(trades: pd.DataFrame, days: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name in list(config["periods"]) + ["P1A_2022H2", "P1B_2023"]:
        bounds = config["periods"].get(name, config["period_splits"].get(name))
        day_part = subset_by_bounds(days, bounds)
        trade_part = subset_by_bounds(trades, bounds)
        item: dict[str, Any] = {
            "days": int(len(day_part)),
            "starts": int(len(trade_part)),
            "same_direction_days": int((day_part["direction_relation"] == "SAME").sum()),
            "opposite_direction_days": int((day_part["direction_relation"] == "OPPOSITE").sum()),
        }
        for symbol in config["symbols"]:
            sym = trade_part[trade_part["symbol"] == symbol]
            item[symbol] = {
                "up": int((sym["direction"] > 0).sum()),
                "down": int((sym["direction"] < 0).sum()),
                "zero": int((sym["direction"] == 0).sum()),
            }
        result[name] = item
    return result


def verify_structural_counts(
    summary: dict[str, Any],
    session_meta: dict[str, Any],
    trade_meta: dict[str, Any],
    config: dict[str, Any],
) -> None:
    expected = config["premetric_feasibility"]
    for symbol in config["symbols"]:
        require(
            session_meta[symbol]["complete_sessions"] == expected["complete_sessions"][symbol],
            f"complete session count mismatch {symbol}",
        )
    require(trade_meta["common_complete_sessions"] == expected["common_complete_sessions"], "common session count mismatch")
    require(
        trade_meta["eligible_with_prior_gap_1_to_4_all_dates"] == expected["eligible_with_prior_gap_1_to_4_all_dates"],
        "eligible all-date count mismatch",
    )
    require(trade_meta["gap_days"] == expected["gap_days"], "gap distribution mismatch")
    for name, expected_period in expected["periods"].items():
        actual = summary[name]
        require(actual["days"] == expected_period["days"], f"day count mismatch {name}")
        require(actual["starts"] == expected_period["starts"], f"start count mismatch {name}")
        require(actual["same_direction_days"] == expected_period["same_direction_days"], f"same-direction mismatch {name}")
        require(actual["opposite_direction_days"] == expected_period["opposite_direction_days"], f"opposite-direction mismatch {name}")
        for symbol in config["symbols"]:
            require(actual[symbol] == expected_period[symbol], f"signal-side mismatch {name} {symbol}")


def make_views(trades: pd.DataFrame, days: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    starting = float(config["trade_spec"]["starting_balance_usd"])
    views: dict[str, Any] = {"periods": {}, "splits": {}, "monthly": {}}
    for name, bounds in config["periods"].items():
        part = subset_by_bounds(trades, bounds)
        views["periods"][name] = {
            "combined": book(part, starting),
            "symbols": {symbol: book(part[part["symbol"] == symbol], starting) for symbol in config["symbols"]},
            "predictor_sides": {
                "UP": book(part[part["direction"] > 0], starting),
                "DOWN": book(part[part["direction"] < 0], starting),
            },
        }
    for name, bounds in config["period_splits"].items():
        part = subset_by_bounds(trades, bounds)
        views["splits"][name] = {
            "combined": book(part, starting),
            "symbols": {symbol: book(part[part["symbol"] == symbol], starting) for symbol in config["symbols"]},
            "predictor_sides": {
                "UP": book(part[part["direction"] > 0], starting),
                "DOWN": book(part[part["direction"] < 0], starting),
            },
        }
    monthly_frame = trades.copy()
    monthly_frame["month"] = pd.to_datetime(monthly_frame["date"]).dt.strftime("%Y-%m")
    for month, part in monthly_frame.groupby("month", sort=True):
        views["monthly"][month] = book(part, starting)["stressed"]
    prelatest_days = subset_by_bounds(days, config["period_splits"]["P1_P4_PRELATEST"])
    positive_day_values = prelatest_days.loc[prelatest_days["stressed_usd"] > 0.0, "stressed_usd"].sort_values(ascending=False)
    positive_day_sum = float(positive_day_values.sum())
    views["concentration"] = {
        "top_five_positive_day_share": float(positive_day_values.head(5).sum() / positive_day_sum) if positive_day_sum > 0.0 else None,
        "largest_positive_day_usd": float(positive_day_values.iloc[0]) if len(positive_day_values) else None,
        "largest_negative_day_usd": float(prelatest_days["stressed_usd"].min()) if len(prelatest_days) else None,
        "positive_days": int((prelatest_days["stressed_usd"] > 0.0).sum()),
        "negative_days": int((prelatest_days["stressed_usd"] < 0.0).sum()),
        "zero_days": int((prelatest_days["stressed_usd"] == 0.0).sum()),
    }
    return views


def economic_verdict(views: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    gates = config["economic_gates"]
    periods = views["periods"]
    splits = views["splits"]
    checks: list[dict[str, Any]] = []

    def add(identifier: str, value: Any, rule: str, threshold: Any, passed: bool) -> None:
        checks.append({"id": identifier, "value": value, "rule": rule, "threshold": threshold, "passed": bool(passed)})

    p1 = periods["P1_2022H2_2023"]["combined"]["stressed"]
    add("P1_COMBINED_NET_POSITIVE", p1["net_usd"], ">", 0.0, p1["net_usd"] > 0.0)
    add("P1_PROFIT_FACTOR", p1["profit_factor"], ">=", gates["p1"]["profit_factor_min"], p1["profit_factor"] is not None and p1["profit_factor"] >= gates["p1"]["profit_factor_min"])
    add("P1_NET_TO_DRAWDOWN", p1["net_to_drawdown"], ">=", gates["p1"]["net_to_drawdown_min"], p1["net_to_drawdown"] is not None and p1["net_to_drawdown"] >= gates["p1"]["net_to_drawdown_min"])
    for split in ("P1A_2022H2", "P1B_2023"):
        value = splits[split]["combined"]["stressed"]["net_usd"]
        add(f"{split}_NET_POSITIVE", value, ">", 0.0, value > 0.0)
    for symbol in config["symbols"]:
        value = periods["P1_2022H2_2023"]["symbols"][symbol]["stressed"]["net_usd"]
        add(f"P1_{symbol}_NET_POSITIVE", value, ">", 0.0, value > 0.0)
    for side in ("UP", "DOWN"):
        value = periods["P1_2022H2_2023"]["predictor_sides"][side]["stressed"]["net_usd"]
        add(f"P1_{side}_NET_POSITIVE", value, ">", 0.0, value > 0.0)

    for period in ("P2_2024", "P3_2025", "P4_2026_JAN_MAY"):
        value = periods[period]["combined"]["stressed"]["net_usd"]
        add(f"{period}_COMBINED_NET_POSITIVE", value, ">", 0.0, value > 0.0)
    confirmation = splits["P2_P4_CONFIRMATION"]["combined"]["stressed"]
    add("P2_P4_PROFIT_FACTOR", confirmation["profit_factor"], ">=", gates["confirmation_p2_p4"]["pooled_profit_factor_min"], confirmation["profit_factor"] is not None and confirmation["profit_factor"] >= gates["confirmation_p2_p4"]["pooled_profit_factor_min"])
    add("P2_P4_NET_TO_DRAWDOWN", confirmation["net_to_drawdown"], ">=", gates["confirmation_p2_p4"]["pooled_net_to_drawdown_min"], confirmation["net_to_drawdown"] is not None and confirmation["net_to_drawdown"] >= gates["confirmation_p2_p4"]["pooled_net_to_drawdown_min"])
    for symbol in config["symbols"]:
        value = splits["P2_P4_CONFIRMATION"]["symbols"][symbol]["stressed"]["net_usd"]
        add(f"P2_P4_{symbol}_NET_POSITIVE", value, ">", 0.0, value > 0.0)
    for side in ("UP", "DOWN"):
        value = splits["P2_P4_CONFIRMATION"]["predictor_sides"][side]["stressed"]["net_usd"]
        add(f"P2_P4_{side}_NET_POSITIVE", value, ">", 0.0, value > 0.0)
    positive_cells = sum(
        periods[period]["symbols"][symbol]["stressed"]["net_usd"] > 0.0
        for period in ("P2_2024", "P3_2025", "P4_2026_JAN_MAY")
        for symbol in config["symbols"]
    )
    add("P2_P4_POSITIVE_SYMBOL_PERIOD_CELLS", positive_cells, ">=", gates["confirmation_p2_p4"]["positive_symbol_period_cells_min"], positive_cells >= gates["confirmation_p2_p4"]["positive_symbol_period_cells_min"])

    prelatest = splits["P1_P4_PRELATEST"]["combined"]["stressed"]
    add("P1_P4_PROFIT_FACTOR", prelatest["profit_factor"], ">=", gates["prelatest_p1_p4"]["profit_factor_min"], prelatest["profit_factor"] is not None and prelatest["profit_factor"] >= gates["prelatest_p1_p4"]["profit_factor_min"])
    add("P1_P4_NET_TO_DRAWDOWN", prelatest["net_to_drawdown"], ">=", gates["prelatest_p1_p4"]["net_to_drawdown_min"], prelatest["net_to_drawdown"] is not None and prelatest["net_to_drawdown"] >= gates["prelatest_p1_p4"]["net_to_drawdown_min"])
    nominal_dd_pass = prelatest["max_closed_drawdown_percent"] <= gates["prelatest_p1_p4"]["nominal_max_drawdown_percent"]
    practical_dd_pass = prelatest["max_closed_drawdown_percent"] <= gates["prelatest_p1_p4"]["practical_max_drawdown_percent"]
    add("P1_P4_NOMINAL_DD", prelatest["max_closed_drawdown_percent"], "<=", gates["prelatest_p1_p4"]["nominal_max_drawdown_percent"], nominal_dd_pass)
    add("P1_P4_PRACTICAL_DD", prelatest["max_closed_drawdown_percent"], "<=", gates["prelatest_p1_p4"]["practical_max_drawdown_percent"], practical_dd_pass)
    symbol_nets = [splits["P1_P4_PRELATEST"]["symbols"][symbol]["stressed"]["net_usd"] for symbol in config["symbols"]]
    positive_symbol_sum = sum(max(0.0, value) for value in symbol_nets)
    symbol_share = max((max(0.0, value) for value in symbol_nets), default=0.0) / positive_symbol_sum if positive_symbol_sum > 0.0 else None
    add("P1_P4_MAX_SYMBOL_SHARE", symbol_share, "<=", gates["prelatest_p1_p4"]["maximum_symbol_share_of_positive_net"], symbol_share is not None and symbol_share <= gates["prelatest_p1_p4"]["maximum_symbol_share_of_positive_net"])
    top_five = views["concentration"]["top_five_positive_day_share"]
    add("P1_P4_TOP_FIVE_POSITIVE_DAY_SHARE", top_five, "<=", gates["prelatest_p1_p4"]["maximum_top_five_positive_day_share"], top_five is not None and top_five <= gates["prelatest_p1_p4"]["maximum_top_five_positive_day_share"])

    latest = periods["P5_LATEST_2026_JUN_JUL"]["combined"]["stressed"]
    p1p4_days = sum(views["periods"][name]["combined"]["stressed"]["count"] for name in ("P1_2022H2_2023", "P2_2024", "P3_2025", "P4_2026_JAN_MAY")) / len(config["symbols"])
    p5_days = latest["count"] / len(config["symbols"])
    positive_daily_edge = max(0.0, prelatest["net_usd"] / p1p4_days) if p1p4_days > 0 else 0.0
    practical_latest_floor = -0.25 * positive_daily_edge * p5_days
    nominal_latest_pass = latest["net_usd"] >= gates["latest"]["nominal_net_min_usd"]
    practical_latest_pass = latest["net_usd"] >= practical_latest_floor
    add("P5_NOMINAL_NET", latest["net_usd"], ">=", gates["latest"]["nominal_net_min_usd"], nominal_latest_pass)
    add("P5_PRACTICAL_NET", latest["net_usd"], ">=", practical_latest_floor, practical_latest_pass)
    full = splits["P1_P5_FULL"]["combined"]["stressed"]
    add("FULL_PATH_NET_POSITIVE", full["net_usd"], ">", 0.0, full["net_usd"] > 0.0)
    add("FULL_PATH_PROFIT_FACTOR", full["profit_factor"], ">=", gates["latest"]["full_path_profit_factor_min"], full["profit_factor"] is not None and full["profit_factor"] >= gates["latest"]["full_path_profit_factor_min"])

    common_checks = [check for check in checks if check["id"] not in {"P1_P4_NOMINAL_DD", "P1_P4_PRACTICAL_DD", "P5_NOMINAL_NET", "P5_PRACTICAL_NET"}]
    common_pass = all(check["passed"] for check in common_checks)
    nominal_pass = common_pass and nominal_dd_pass and nominal_latest_pass
    practical_pass = common_pass and practical_dd_pass and practical_latest_pass
    verdicts = gates["verdicts"]
    if nominal_pass:
        verdict = verdicts["nominal_pass"]
        retained_seed = "FIXED_US30_US100_CASH_CLOSE_INTRADAY_MOMENTUM_BUNDLE"
    elif practical_pass:
        verdict = verdicts["practical_pass"]
        retained_seed = "FIXED_US30_US100_CASH_CLOSE_INTRADAY_MOMENTUM_BUNDLE"
    elif p1["net_usd"] <= 0.0 or (p1["profit_factor"] is not None and p1["profit_factor"] <= 1.0) or prelatest["net_usd"] <= 0.0:
        verdict = verdicts["nonconfirmation"]
        retained_seed = None
    else:
        verdict = verdicts["ambiguous"]
        retained_seed = None
    return {
        "verdict": verdict,
        "retained_seed": retained_seed,
        "nominal_pass": nominal_pass,
        "practical_pass": practical_pass,
        "nominal_misses": [check["id"] for check in checks if not check["passed"] and check["id"] != "P1_P4_PRACTICAL_DD" and check["id"] != "P5_PRACTICAL_NET"],
        "practical_misses": [check["id"] for check in common_checks if not check["passed"]] + ([] if practical_dd_pass else ["P1_P4_PRACTICAL_DD"]) + ([] if practical_latest_pass else ["P5_PRACTICAL_NET"]),
        "practical_latest_floor_usd": practical_latest_floor,
        "checks": checks,
    }


def main() -> None:
    started = time.perf_counter()
    config = load_json(CONFIG_PATH)
    input_root = REPO_ROOT / config["roots"]["input"]
    output_root = REPO_ROOT / config["roots"]["output"]
    verified_inputs = verify_inputs(config, input_root)
    sessions: dict[str, pd.DataFrame] = {}
    session_meta: dict[str, Any] = {}
    for symbol in config["symbols"]:
        sessions[symbol], session_meta[symbol] = load_complete_sessions(symbol, config, input_root)
    trades, days, trade_meta = build_trades(sessions, config)
    structural = structural_summary(trades, days, config)
    verify_structural_counts(structural, session_meta, trade_meta, config)
    views = make_views(trades, days, config)
    verdict = economic_verdict(views, config)
    output_root.mkdir(parents=True, exist_ok=True)
    trades.to_csv(output_root / "trades.csv", index=False, lineterminator="\n", float_format="%.12f")
    days.to_csv(output_root / "paired-days.csv", index=False, lineterminator="\n", float_format="%.12f")
    result = {
        "schema": "zeta-next-us-equity-index-cash-close-intraday-momentum-analysis-result-v1",
        "family": config["family"],
        "unit": config["unit"],
        "formal_source_free_process": 1,
        "config": {"path": CONFIG_PATH.relative_to(REPO_ROOT).as_posix(), "bytes": CONFIG_PATH.stat().st_size, "sha256": sha256_file(CONFIG_PATH)},
        "inputs": verified_inputs,
        "session_integrity": session_meta,
        "paired_calendar": trade_meta,
        "structural_reproduction": structural,
        "economics": views,
        "decision": verdict,
        "execution": {
            "elapsed_seconds": time.perf_counter() - started,
            "trades": int(len(trades)),
            "paired_days": int(len(days)),
            "direction_books": 1,
            "threshold_points": 0,
            "grid_points": 0,
            "mql_changes": 0,
            "compile_paths": 0,
            "tester_paths": 0,
            "mt5_paths": 0,
            "broker_account_queries": 0,
            "live_surface": "UNTOUCHED",
        },
    }
    result_path = output_root / "analysis-result.json"
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    receipt = {
        "result": {"path": result_path.relative_to(REPO_ROOT).as_posix(), "bytes": result_path.stat().st_size, "sha256": sha256_file(result_path)},
        "trades": {"path": (output_root / "trades.csv").relative_to(REPO_ROOT).as_posix(), "bytes": (output_root / "trades.csv").stat().st_size, "sha256": sha256_file(output_root / "trades.csv")},
        "days": {"path": (output_root / "paired-days.csv").relative_to(REPO_ROOT).as_posix(), "bytes": (output_root / "paired-days.csv").stat().st_size, "sha256": sha256_file(output_root / "paired-days.csv")},
        "verdict": verdict["verdict"],
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
