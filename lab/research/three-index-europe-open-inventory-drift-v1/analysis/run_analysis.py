from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


REPO_ROOT = Path(__file__).resolve().parents[4]
FAMILY_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = FAMILY_ROOT / "config" / "contract.json"
COST_COLUMNS = ("gross_usd", "observed_usd", "stressed_usd")
WEEKDAY_NAMES = ("MON", "TUE", "WED", "THU", "FRI")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_inputs(config: dict[str, Any], input_root: Path) -> dict[str, Any]:
    lines: list[str] = []
    files: list[dict[str, Any]] = []
    for expected in sorted(config["immutable_inputs"]["files"], key=lambda x: x["name"]):
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


def load_symbol(symbol: str, config: dict[str, Any], input_root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    path = input_root / config["bar_files"][symbol]
    schema = pq.read_schema(path)
    actual_schema = {field.name: str(field.type) for field in schema}
    if actual_schema != config["required_schema"]:
        raise RuntimeError(f"schema mismatch for {symbol}: {actual_schema}")
    frame = pd.read_parquet(path)
    expected = next(item for item in config["immutable_inputs"]["files"] if item["name"] == config["bar_files"][symbol])
    if len(frame) != expected["rows"]:
        raise RuntimeError(f"row-count mismatch for {symbol}")
    if frame.isna().any().any():
        raise RuntimeError(f"null market value for {symbol}")
    utc = pd.to_datetime(frame["time"], unit="s", utc=True)
    if not utc.is_monotonic_increasing or utc.duplicated().any():
        raise RuntimeError(f"time integrity mismatch for {symbol}")
    if utc.iloc[0].isoformat() != expected["first_utc"] or utc.iloc[-1].isoformat() != expected["last_utc"]:
        raise RuntimeError(f"time boundary mismatch for {symbol}")
    if (frame[["open", "high", "low", "close"]] <= 0.0).any().any():
        raise RuntimeError(f"nonpositive price for {symbol}")
    if (frame["spread"] < 0).any():
        raise RuntimeError(f"negative spread for {symbol}")
    et = utc.dt.tz_convert(config["fixed_rule"]["timezone"])
    eligible = frame.loc[
        (et.dt.weekday < 5)
        & et.dt.hour.isin([2, 3])
        & et.dt.minute.eq(0)
        & et.dt.second.eq(0),
        ["open", "spread"],
    ].copy()
    eligible["utc"] = utc.loc[eligible.index]
    eligible["et"] = et.loc[eligible.index]
    eligible["date"] = eligible["et"].dt.tz_localize(None).dt.normalize()
    eligible["hour"] = eligible["et"].dt.hour
    rows: list[dict[str, Any]] = []
    for date, group in eligible.groupby("date", sort=True):
        entry = group.loc[group["hour"] == 2]
        exit_ = group.loc[group["hour"] == 3]
        if len(entry) == 1 and len(exit_) == 1:
            erow = entry.iloc[0]
            xrow = exit_.iloc[0]
            if erow["et"].date() != xrow["et"].date():
                raise RuntimeError(f"New York date crossed for {symbol} {date}")
            rows.append(
                {
                    "date": date,
                    "entry_utc": erow["utc"],
                    "exit_utc": xrow["utc"],
                    "entry_bid": float(erow["open"]),
                    "exit_bid": float(xrow["open"]),
                    "entry_spread_points": int(erow["spread"]),
                    "exit_spread_points": int(xrow["spread"]),
                }
            )
    paired = pd.DataFrame(rows).set_index("date", drop=False)
    return paired, {
        "rows": int(len(frame)),
        "first_utc": utc.iloc[0].isoformat(),
        "last_utc": utc.iloc[-1].isoformat(),
        "duplicate_utc": int(utc.duplicated().sum()),
        "exact_02_rows": int((eligible["hour"] == 2).sum()),
        "exact_03_rows": int((eligible["hour"] == 3).sum()),
        "eligible_dates": int(len(paired)),
        "zero_entry_spread_dates": int((paired["entry_spread_points"] == 0).sum()),
        "zero_exit_spread_dates": int((paired["exit_spread_points"] == 0).sum()),
    }


def build_trades(
    symbol_frames: dict[str, pd.DataFrame], config: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    common = set.intersection(*(set(frame.index) for frame in symbol_frames.values()))
    start = pd.Timestamp(config["fixed_rule"]["date_range"][0])
    end = pd.Timestamp(config["fixed_rule"]["date_range"][1])
    research_dates = sorted(date for date in common if start <= date < end)
    spec = config["trade_spec"]
    point = float(spec["point"])
    volume = float(spec["volume"])
    contract_size = float(spec["trade_contract_size"])
    trades: list[dict[str, Any]] = []
    for date in research_dates:
        for symbol in config["symbols"]:
            row = symbol_frames[symbol].loc[date]
            entry_spread_usd = row["entry_spread_points"] * point * contract_size * volume
            exit_spread_usd = row["exit_spread_points"] * point * contract_size * volume
            entry_mid = row["entry_bid"] + 0.5 * row["entry_spread_points"] * point
            exit_mid = row["exit_bid"] + 0.5 * row["exit_spread_points"] * point
            gross = (exit_mid - entry_mid) * contract_size * volume
            observed = (row["exit_bid"] - (row["entry_bid"] + row["entry_spread_points"] * point)) * contract_size * volume
            observed_identity = gross - 0.5 * (entry_spread_usd + exit_spread_usd)
            if abs(observed - observed_identity) > 1e-10:
                raise RuntimeError(f"bid/ask identity mismatch for {symbol} {date.date()}")
            stressed = gross - (entry_spread_usd + exit_spread_usd)
            trades.append(
                {
                    "date": date,
                    "month": date.strftime("%Y-%m"),
                    "weekday": WEEKDAY_NAMES[date.weekday()],
                    "symbol": symbol,
                    "direction": "LONG",
                    "entry_utc": row["entry_utc"],
                    "exit_utc": row["exit_utc"],
                    "entry_bid": row["entry_bid"],
                    "exit_bid": row["exit_bid"],
                    "entry_spread_points": row["entry_spread_points"],
                    "exit_spread_points": row["exit_spread_points"],
                    "entry_mid": entry_mid,
                    "exit_mid": exit_mid,
                    "gross_usd": gross,
                    "observed_usd": observed,
                    "stressed_usd": stressed,
                }
            )
    trade_frame = pd.DataFrame(trades).sort_values(["date", "symbol"], kind="stable").reset_index(drop=True)
    daily = trade_frame.groupby(["date", "month", "weekday"], as_index=False)[list(COST_COLUMNS)].sum()
    daily = daily.sort_values("date", kind="stable").reset_index(drop=True)
    return trade_frame, daily, {
        "common_eligible_all_dates": int(len(common)),
        "research_dates": int(len(research_dates)),
        "research_trades": int(len(trade_frame)),
        "first_date": research_dates[0].date().isoformat(),
        "last_date": research_dates[-1].date().isoformat(),
        "starts_per_day": int(len(config["symbols"])),
    }


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
            "average_usd": None,
            "max_closed_drawdown_usd": 0.0,
            "max_closed_drawdown_percent": 0.0,
            "net_to_drawdown": None,
        }
    net = float(array.sum())
    gross_profit = float(array[array > 0.0].sum())
    gross_loss = float(array[array < 0.0].sum())
    pf = gross_profit / abs(gross_loss) if gross_loss < 0.0 else None
    cumulative = np.cumsum(array)
    peaks = np.maximum.accumulate(np.concatenate(([0.0], cumulative)))
    drawdowns = peaks[1:] - cumulative
    max_dd = float(drawdowns.max(initial=0.0))
    return {
        "count": int(len(array)),
        "net_usd": net,
        "gross_profit_usd": gross_profit,
        "gross_loss_usd": gross_loss,
        "profit_factor": float(pf) if pf is not None else None,
        "win_rate": float(np.mean(array > 0.0)),
        "average_usd": float(np.mean(array)),
        "max_closed_drawdown_usd": max_dd,
        "max_closed_drawdown_percent": max_dd / starting_balance * 100.0,
        "net_to_drawdown": net / max_dd if max_dd > 0.0 else None,
    }


def summarize(trades: pd.DataFrame, days: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    balance = float(config["trade_spec"]["starting_balance_usd"])
    combined = {cost.removesuffix("_usd"): series_metrics(days[cost], balance) for cost in COST_COLUMNS}
    symbols = {
        symbol: {cost.removesuffix("_usd"): series_metrics(trades.loc[trades["symbol"] == symbol, cost], balance) for cost in COST_COLUMNS}
        for symbol in config["symbols"]
    }
    weekdays = {
        weekday: {cost.removesuffix("_usd"): series_metrics(days.loc[days["weekday"] == weekday, cost], balance) for cost in COST_COLUMNS}
        for weekday in WEEKDAY_NAMES
    }
    month_nets = {
        cost.removesuffix("_usd"): {str(month): float(value) for month, value in days.groupby("month")[cost].sum().items()}
        for cost in COST_COLUMNS
    }
    return {"combined": combined, "symbols": symbols, "weekdays": weekdays, "month_nets": month_nets}


def slice_between(frame: pd.DataFrame, boundary: dict[str, str]) -> pd.DataFrame:
    return frame.loc[
        (frame["date"] >= pd.Timestamp(boundary["from_inclusive"]))
        & (frame["date"] < pd.Timestamp(boundary["to_exclusive"]))
    ].copy()


def make_views(trades: pd.DataFrame, days: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    periods: dict[str, Any] = {}
    splits: dict[str, Any] = {}
    for name, boundary in config["periods"].items():
        periods[name] = summarize(slice_between(trades, boundary), slice_between(days, boundary), config)
    for name, boundary in config["period_splits"].items():
        splits[name] = summarize(slice_between(trades, boundary), slice_between(days, boundary), config)
    prelatest_days = slice_between(days, config["period_splits"]["P1_P4_PRELATEST"])
    positive_days = prelatest_days.loc[prelatest_days["stressed_usd"] > 0.0, "stressed_usd"].sort_values(ascending=False)
    top_five_share = float(positive_days.head(5).sum() / positive_days.sum()) if positive_days.sum() > 0.0 else None
    symbol_nets = {
        symbol: splits["P1_P4_PRELATEST"]["symbols"][symbol]["stressed"]["net_usd"]
        for symbol in config["symbols"]
    }
    positive_symbol_sum = sum(max(0.0, value) for value in symbol_nets.values())
    symbol_shares = {
        symbol: (max(0.0, value) / positive_symbol_sum if positive_symbol_sum > 0.0 else None)
        for symbol, value in symbol_nets.items()
    }
    return {
        "periods": periods,
        "splits": splits,
        "concentration": {
            "top_five_positive_day_share": top_five_share,
            "prelatest_symbol_stressed_nets": symbol_nets,
            "positive_net_symbol_shares": symbol_shares,
        },
    }


def verify_structural(
    symbol_meta: dict[str, Any], trade_meta: dict[str, Any], trades: pd.DataFrame, days: pd.DataFrame, config: dict[str, Any]
) -> dict[str, Any]:
    expected = config["premetric_feasibility"]
    if trade_meta["common_eligible_all_dates"] != expected["common_eligible_all_dates"]:
        raise RuntimeError("common eligible-date count changed")
    for symbol in config["symbols"]:
        for key in ("exact_02_rows", "exact_03_rows", "eligible_dates", "duplicate_utc"):
            if symbol_meta[symbol][key] != expected["symbols"][symbol][key]:
                raise RuntimeError(f"premetric mismatch: {symbol} {key}")
    periods: dict[str, Any] = {}
    all_boundaries = {**config["periods"], **config["period_splits"]}
    for name, frozen in expected["periods"].items():
        boundary = all_boundaries[name]
        d = slice_between(days, boundary)
        t = slice_between(trades, boundary)
        weekday_counts = [int((d["weekday"] == weekday).sum()) for weekday in WEEKDAY_NAMES]
        if len(d) != frozen["days"] or len(t) != frozen["starts"] or weekday_counts != frozen["weekday_counts_mon0"]:
            raise RuntimeError(f"period structural mismatch: {name}")
        periods[name] = {
            "days": int(len(d)),
            "starts": int(len(t)),
            "weekday_counts_mon0": weekday_counts,
            "months": int(d["month"].nunique()),
        }
    return {
        "common_eligible_all_dates": trade_meta["common_eligible_all_dates"],
        "research_dates": trade_meta["research_dates"],
        "research_trades": trade_meta["research_trades"],
        "starts_per_day": trade_meta["starts_per_day"],
        "periods": periods,
        "symbols": symbol_meta,
    }


def economic_verdict(views: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    gates = config["economic_gates"]
    periods = views["periods"]
    splits = views["splits"]
    checks: list[dict[str, Any]] = []

    def add(identifier: str, value: Any, operator: str, threshold: Any, passed: bool) -> None:
        checks.append({"id": identifier, "value": value, "operator": operator, "threshold": threshold, "passed": bool(passed)})

    p1 = periods["P1_2022H2_2023"]["combined"]["stressed"]
    add("P1_NET_POSITIVE", p1["net_usd"], ">", 0.0, p1["net_usd"] > 0.0)
    add("P1_PROFIT_FACTOR", p1["profit_factor"], ">=", gates["p1"]["profit_factor_min"], p1["profit_factor"] is not None and p1["profit_factor"] >= gates["p1"]["profit_factor_min"])
    add("P1_NET_TO_DRAWDOWN", p1["net_to_drawdown"], ">=", gates["p1"]["net_to_drawdown_min"], p1["net_to_drawdown"] is not None and p1["net_to_drawdown"] >= gates["p1"]["net_to_drawdown_min"])
    for split in ("P1A_2022H2", "P1B_2023"):
        value = splits[split]["combined"]["stressed"]["net_usd"]
        add(f"{split}_NET_POSITIVE", value, ">", 0.0, value > 0.0)
    for symbol in config["symbols"]:
        value = periods["P1_2022H2_2023"]["symbols"][symbol]["stressed"]["net_usd"]
        add(f"P1_{symbol}_NET_POSITIVE", value, ">", 0.0, value > 0.0)
    p1_weekdays = sum(periods["P1_2022H2_2023"]["weekdays"][day]["stressed"]["net_usd"] > 0.0 for day in WEEKDAY_NAMES)
    add("P1_POSITIVE_WEEKDAYS", p1_weekdays, ">=", gates["p1"]["positive_weekdays_min"], p1_weekdays >= gates["p1"]["positive_weekdays_min"])

    for period in ("P2_2024", "P3_2025", "P4_2026_JAN_MAY"):
        value = periods[period]["combined"]["stressed"]["net_usd"]
        add(f"{period}_NET_POSITIVE", value, ">", 0.0, value > 0.0)
    confirmation = splits["P2_P4_CONFIRMATION"]["combined"]["stressed"]
    add("P2_P4_PROFIT_FACTOR", confirmation["profit_factor"], ">=", gates["confirmation_p2_p4"]["pooled_profit_factor_min"], confirmation["profit_factor"] is not None and confirmation["profit_factor"] >= gates["confirmation_p2_p4"]["pooled_profit_factor_min"])
    add("P2_P4_NET_TO_DRAWDOWN", confirmation["net_to_drawdown"], ">=", gates["confirmation_p2_p4"]["pooled_net_to_drawdown_min"], confirmation["net_to_drawdown"] is not None and confirmation["net_to_drawdown"] >= gates["confirmation_p2_p4"]["pooled_net_to_drawdown_min"])
    for symbol in config["symbols"]:
        value = splits["P2_P4_CONFIRMATION"]["symbols"][symbol]["stressed"]["net_usd"]
        add(f"P2_P4_{symbol}_NET_POSITIVE", value, ">", 0.0, value > 0.0)
    positive_cells = sum(
        periods[period]["symbols"][symbol]["stressed"]["net_usd"] > 0.0
        for period in ("P2_2024", "P3_2025", "P4_2026_JAN_MAY")
        for symbol in config["symbols"]
    )
    add("P2_P4_POSITIVE_SYMBOL_PERIOD_CELLS", positive_cells, ">=", gates["confirmation_p2_p4"]["positive_symbol_period_cells_min"], positive_cells >= gates["confirmation_p2_p4"]["positive_symbol_period_cells_min"])
    confirmation_weekdays = sum(splits["P2_P4_CONFIRMATION"]["weekdays"][day]["stressed"]["net_usd"] > 0.0 for day in WEEKDAY_NAMES)
    add("P2_P4_POSITIVE_WEEKDAYS", confirmation_weekdays, ">=", gates["confirmation_p2_p4"]["positive_weekdays_min"], confirmation_weekdays >= gates["confirmation_p2_p4"]["positive_weekdays_min"])

    prelatest = splits["P1_P4_PRELATEST"]["combined"]["stressed"]
    add("P1_P4_PROFIT_FACTOR", prelatest["profit_factor"], ">=", gates["prelatest_p1_p4"]["profit_factor_min"], prelatest["profit_factor"] is not None and prelatest["profit_factor"] >= gates["prelatest_p1_p4"]["profit_factor_min"])
    add("P1_P4_NET_TO_DRAWDOWN", prelatest["net_to_drawdown"], ">=", gates["prelatest_p1_p4"]["net_to_drawdown_min"], prelatest["net_to_drawdown"] is not None and prelatest["net_to_drawdown"] >= gates["prelatest_p1_p4"]["net_to_drawdown_min"])
    nominal_dd_pass = prelatest["max_closed_drawdown_percent"] <= gates["prelatest_p1_p4"]["nominal_max_drawdown_percent"]
    practical_dd_pass = prelatest["max_closed_drawdown_percent"] <= gates["prelatest_p1_p4"]["practical_max_drawdown_percent"]
    add("P1_P4_NOMINAL_DD", prelatest["max_closed_drawdown_percent"], "<=", gates["prelatest_p1_p4"]["nominal_max_drawdown_percent"], nominal_dd_pass)
    add("P1_P4_PRACTICAL_DD", prelatest["max_closed_drawdown_percent"], "<=", gates["prelatest_p1_p4"]["practical_max_drawdown_percent"], practical_dd_pass)
    month_nets = splits["P1_P4_PRELATEST"]["month_nets"]["stressed"]
    positive_months = sum(value > 0.0 for value in month_nets.values())
    add("P1_P4_POSITIVE_MONTHS", positive_months, ">=", gates["prelatest_p1_p4"]["positive_months_min"], positive_months >= gates["prelatest_p1_p4"]["positive_months_min"])
    top_five = views["concentration"]["top_five_positive_day_share"]
    add("P1_P4_TOP_FIVE_POSITIVE_DAY_SHARE", top_five, "<=", gates["prelatest_p1_p4"]["maximum_top_five_positive_day_share"], top_five is not None and top_five <= gates["prelatest_p1_p4"]["maximum_top_five_positive_day_share"])

    latest = periods["P5_LATEST_2026_JUN_JUL"]["combined"]["stressed"]
    prelatest_days = prelatest["count"]
    positive_daily_edge = max(0.0, prelatest["net_usd"] / prelatest_days) if prelatest_days else 0.0
    practical_latest_floor = -0.25 * positive_daily_edge * latest["count"]
    nominal_latest_pass = latest["net_usd"] >= gates["latest"]["nominal_net_min_usd"]
    practical_latest_pass = latest["net_usd"] >= practical_latest_floor
    add("P5_NOMINAL_NET", latest["net_usd"], ">=", gates["latest"]["nominal_net_min_usd"], nominal_latest_pass)
    add("P5_PRACTICAL_NET", latest["net_usd"], ">=", practical_latest_floor, practical_latest_pass)
    full = splits["P1_P5_FULL"]["combined"]["stressed"]
    add("FULL_PATH_NET_POSITIVE", full["net_usd"], ">", 0.0, full["net_usd"] > 0.0)
    add("FULL_PATH_PROFIT_FACTOR", full["profit_factor"], ">=", gates["latest"]["full_path_profit_factor_min"], full["profit_factor"] is not None and full["profit_factor"] >= gates["latest"]["full_path_profit_factor_min"])

    alternative_ids = {"P1_P4_NOMINAL_DD", "P1_P4_PRACTICAL_DD", "P5_NOMINAL_NET", "P5_PRACTICAL_NET"}
    common_checks = [check for check in checks if check["id"] not in alternative_ids]
    common_pass = all(check["passed"] for check in common_checks)
    nominal_pass = common_pass and nominal_dd_pass and nominal_latest_pass
    practical_pass = common_pass and practical_dd_pass and practical_latest_pass
    verdicts = gates["verdicts"]
    retained_seed: str | None = None
    if nominal_pass:
        verdict = verdicts["nominal_pass"]
        retained_seed = "FIXED_US30_US100_US500_0200_0300_ET_LONG_BUNDLE"
    elif practical_pass:
        verdict = verdicts["practical_pass"]
        retained_seed = "FIXED_US30_US100_US500_0200_0300_ET_LONG_BUNDLE"
    elif p1["net_usd"] <= 0.0 or (p1["profit_factor"] is not None and p1["profit_factor"] <= 1.0) or prelatest["net_usd"] <= 0.0 or full["net_usd"] <= 0.0:
        verdict = verdicts["nonconfirmation"]
    else:
        verdict = verdicts["ambiguous"]
    return {
        "verdict": verdict,
        "retained_seed": retained_seed,
        "nominal_pass": nominal_pass,
        "practical_pass": practical_pass,
        "nominal_misses": [check["id"] for check in common_checks if not check["passed"]] + ([] if nominal_dd_pass else ["P1_P4_NOMINAL_DD"]) + ([] if nominal_latest_pass else ["P5_NOMINAL_NET"]),
        "practical_misses": [check["id"] for check in common_checks if not check["passed"]] + ([] if practical_dd_pass else ["P1_P4_PRACTICAL_DD"]) + ([] if practical_latest_pass else ["P5_PRACTICAL_NET"]),
        "practical_latest_floor_usd": practical_latest_floor,
        "positive_months_p1_p4": positive_months,
        "positive_months_total_p1_p4": len(month_nets),
        "positive_weekdays_p1": p1_weekdays,
        "positive_weekdays_p2_p4": confirmation_weekdays,
        "positive_symbol_period_cells_p2_p4": positive_cells,
        "checks": checks,
    }


def main() -> None:
    started = time.perf_counter()
    config = load_json(CONFIG_PATH)
    input_root = REPO_ROOT / config["roots"]["input"]
    output_root = REPO_ROOT / config["roots"]["output"]
    verified_inputs = verify_inputs(config, input_root)
    symbol_frames: dict[str, pd.DataFrame] = {}
    symbol_meta: dict[str, Any] = {}
    for symbol in config["symbols"]:
        symbol_frames[symbol], symbol_meta[symbol] = load_symbol(symbol, config, input_root)
    trades, days, trade_meta = build_trades(symbol_frames, config)
    structural = verify_structural(symbol_meta, trade_meta, trades, days, config)
    views = make_views(trades, days, config)
    decision = economic_verdict(views, config)
    output_root.mkdir(parents=True, exist_ok=True)
    trades_path = output_root / "trades.csv"
    days_path = output_root / "bundle-days.csv"
    result_path = output_root / "analysis-result.json"
    trades.to_csv(trades_path, index=False, lineterminator="\n", float_format="%.12f")
    days.to_csv(days_path, index=False, lineterminator="\n", float_format="%.12f")
    result = {
        "schema": "zeta-next-three-index-europe-open-inventory-drift-analysis-result-v1",
        "family": config["family"],
        "unit": config["unit"],
        "formal_source_free_process": 1,
        "config": {"path": CONFIG_PATH.relative_to(REPO_ROOT).as_posix(), "bytes": CONFIG_PATH.stat().st_size, "sha256": sha256_file(CONFIG_PATH)},
        "inputs": verified_inputs,
        "symbol_integrity": symbol_meta,
        "structural_reproduction": structural,
        "economics": views,
        "decision": decision,
        "execution": {
            "elapsed_seconds": time.perf_counter() - started,
            "trades": int(len(trades)),
            "bundle_days": int(len(days)),
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
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    receipt = {
        "result": {"path": result_path.relative_to(REPO_ROOT).as_posix(), "bytes": result_path.stat().st_size, "sha256": sha256_file(result_path)},
        "trades": {"path": trades_path.relative_to(REPO_ROOT).as_posix(), "bytes": trades_path.stat().st_size, "sha256": sha256_file(trades_path)},
        "days": {"path": days_path.relative_to(REPO_ROOT).as_posix(), "bytes": days_path.stat().st_size, "sha256": sha256_file(days_path)},
        "verdict": decision["verdict"],
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
