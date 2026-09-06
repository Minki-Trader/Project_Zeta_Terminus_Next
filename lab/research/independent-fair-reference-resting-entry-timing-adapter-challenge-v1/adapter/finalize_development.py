"""Finalize the existing complete Family 014 production; never rerun quote economics.

The ordinary reduction/report clauses are copied once from the frozen executed producer.
Only NumPy scalar JSON conversion and sealed-output recovery are added.
"""
import datetime as dt
import json
import shutil
import numpy as np
from simulate_development import (
    ROOT, REPO, fp, read, STATUS, CASH, DIR_COST, MID_COST, CREDIT, PRICE_PNL,
    FIN_NET, STARTS, CLOSES, PLACEMENTS, CANCELLATIONS, EXPIRATIONS, REJECTIONS,
    INTENTS, ENTRY_COST, EXIT_COST, NEG_FIN, ACTION_COLUMNS, TRADE_COLUMNS,
    EQUITY_COLUMNS, ACTION_NAMES, REASON_NAMES)


def scalar(value):
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError("Unsupported report value " + type(value).__name__)


def save_json(path, value):
    if path.exists():
        raise RuntimeError("Preserve existing completed report")
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=scalar) + "\n",
                         encoding="utf-8", newline="\n")
    temporary.replace(path)


def main():
    report_freeze_path = ROOT / "evidence/REPORT_FINALIZATION_FREEZE_V1.json"
    correction_path = ROOT / "evidence/REPORT_SERIALIZATION_CORRECTION_V1.json"
    for item in read(report_freeze_path)["files"]:
        if fp(REPO / item["path"]) != item:
            raise RuntimeError("Frozen reporting implementation/authority drift")
    freeze_path = ROOT / "evidence/ECONOMIC_IMPLEMENTATION_FREEZE_V1.json"
    for item in read(freeze_path)["files"]:
        if fp(REPO / item["path"]) != item:
            raise RuntimeError("Original executed economic contract/source drift")
    correction = read(correction_path)
    expected_months = [f"{year}{month:02d}" for year in (2024, 2025) for month in range(1, 13)]
    if correction["completed_months"] != expected_months:
        raise RuntimeError("No complete original development traversal exists")
    for item in correction["preserved_original_outputs"]:
        if fp(REPO / item["path"]) != item:
            raise RuntimeError("Original complete production tape changed")
    contract = read(ROOT / "config/contract.json")
    supply = read(ROOT / "evidence/STRUCTURAL_SUPPLY_V1.json")
    output = REPO / "lab/artifacts/raw" / contract["family"] / "economics/attempt-01"
    snapshots, manifest = {}, []
    trade_sums = np.zeros((3, 9))
    trade_counts, long_counts, short_counts = np.zeros(3, dtype=np.int64), np.zeros(3, dtype=np.int64), np.zeros(3, dtype=np.int64)
    by_symbol = np.zeros((3, 3), dtype=np.int64)
    counts_by_year = {str(year): np.zeros(3, dtype=np.int64) for year in (2024, 2025)}
    cash_by_year = {str(year): np.zeros((3, 2)) for year in (2024, 2025)}
    reason_counts = np.zeros((3, 13), dtype=np.int64)
    action_counts = np.zeros((3, 8), dtype=np.int64)
    source_rows, all_action_rows, all_trade_rows, all_equity_rows = 0, 0, 0, 0
    closed_ids, filled_ids = [set() for _ in range(3)], [set() for _ in range(3)]
    for month in expected_months:
        checkpoint = read(output / f"{month}-checkpoint.json")
        accounts = np.array(checkpoint["accounts"])
        books = np.array(checkpoint["books"])
        metrics = np.array(checkpoint["metrics"])
        meta = np.array(checkpoint["meta"], dtype=np.int64)
        if not (np.all(np.isfinite(accounts)) and np.all(np.isfinite(metrics))):
            raise RuntimeError("Nonfinite original completed accounting")
        actions = np.load(output / f"{month}-actions.npy", mmap_mode="r", allow_pickle=False)
        trades = np.load(output / f"{month}-trades.npy", mmap_mode="r", allow_pickle=False)
        equity = np.load(output / f"{month}-minute-equity.npy", mmap_mode="r", allow_pickle=False)
        na, nt, ne = len(actions), len(trades), len(equity)
        for role in range(3):
            ta = trades[trades[:, 0] == role]
            aa = actions[actions[:, 0] == role]
            trade_counts[role] += len(ta)
            long_counts[role] += np.count_nonzero(ta[:, 4] == 1)
            short_counts[role] += np.count_nonzero(ta[:, 4] == -1)
            for s in range(3):
                by_symbol[role, s] += np.count_nonzero(ta[:, 1] == s)
            # Complete trade sums reconcile only at the final flat boundary.
            for target, column in enumerate((16, 17, 18, 19, 20, 21, 22, 23, 24)):
                trade_sums[role, target] += ta[:, column].sum()
            for code in range(1, 8):
                action_counts[role, code] += np.count_nonzero(aa[:, 2] == code)
            for reason in range(1, 10):
                reason_counts[role, reason] += np.count_nonzero((aa[:, 2] == 1) & (aa[:, 3] == reason))
            fills = aa[aa[:, 2] == 3]
            for event in fills:
                fy = str(dt.datetime.fromtimestamp(event[4]/1000, tz=dt.timezone.utc).year)
                counts_by_year[fy][role] += 1
            for trade in ta:
                cy = str(dt.datetime.fromtimestamp(trade[8]/1000, tz=dt.timezone.utc).year)
                cash_by_year[cy][role, 0] += trade[16]
            for financing in aa[aa[:, 2] == 7]:
                cy = str(dt.datetime.fromtimestamp(financing[5]/1000, tz=dt.timezone.utc).year)
                cash_by_year[cy][role, 1] += financing[17]
        for role in range(3):
            new_closes = [int(v) for v in trades[trades[:, 0] == role, 2]]
            new_fills = [int(v) for v in actions[(actions[:, 0] == role) & (actions[:, 2] == 3), 10]]
            if len(set(new_closes)) != len(new_closes) or closed_ids[role].intersection(new_closes):
                raise RuntimeError("Duplicate closed lifecycle in original ordinary tape")
            if len(set(new_fills)) != len(new_fills) or filled_ids[role].intersection(new_fills):
                raise RuntimeError("Duplicate first-fill lifecycle in original ordinary tape")
            closed_ids[role].update(new_closes)
            filled_ids[role].update(new_fills)
        for label in ("actions", "trades", "minute-equity"):
            manifest.append(fp(output / f"{month}-{label}.npy"))
        source_rows = checkpoint["source_rows_consumed"]
        all_action_rows += na
        all_trade_rows += nt
        all_equity_rows += ne
        snapshots[month] = {"accounts": accounts.tolist(), "equity": metrics[:, :, 0].tolist(),
                            "book_status": books[:, :, STATUS].astype(int).tolist(),
                            "last_quote_raw_ms": int(meta[0])}
    for role in range(3):
        if filled_ids[role] != closed_ids[role] or len(filled_ids[role]) != int(accounts[role, STARTS]):
            raise RuntimeError("First fills and complete closes are not a one-to-one lifecycle set")
    if np.any(books[:, :, STATUS] != 0):
        raise RuntimeError("Frozen cutoff/normal exits did not produce complete flat evidence")
    periods = {}
    initial = np.full((3, 4), contract["risk"]["initial_deposit_usd"])
    previous_cash = np.full(3, contract["risk"]["initial_deposit_usd"])
    for year in ("2024", "2025"):
        snapshot = snapshots[year+"12"]
        closing = np.array(snapshot["equity"])
        cash = np.array(snapshot["accounts"])[:, CASH]
        cash_delta = cash - previous_cash
        residual = cash_by_year[year].sum(axis=1) - cash_delta
        if np.max(np.abs(residual)) > 1e-7:
            raise RuntimeError("Calendar cash and booking evidence does not reconcile")
        periods[year] = {"marked_changes": (closing-initial).tolist(),
                         "cash_changes": cash_delta.tolist(),
                         "cash_price_and_financing": cash_by_year[year].tolist(),
                         "cash_reconciliation_residual": residual.tolist(),
                         "first_fills": counts_by_year[year].tolist()}
        initial, previous_cash = closing, cash
    roles = {}
    for role, name in enumerate(contract["role_order"]):
        a, totals = accounts[role], trade_sums[role]
        nets = [a[CASH]-100, a[CASH]-100-a[DIR_COST], a[CASH]-100-a[MID_COST],
                a[CASH]-100-a[DIR_COST]-a[CREDIT]]
        expected = np.array([a[PRICE_PNL], a[FIN_NET], a[CREDIT], *nets[:1], a[DIR_COST], a[MID_COST], *nets[1:]])
        residual = totals - expected
        count_ok = (int(a[STARTS]) == int(a[CLOSES]) == int(trade_counts[role]) ==
                    int(action_counts[role, 3]) == int(action_counts[role, 4]))
        pending_ok = (int(a[PLACEMENTS]) == (0 if role == 0 else int(a[STARTS])) +
                      int(a[CANCELLATIONS]) + int(a[EXPIRATIONS]))
        intents_ok = int(a[INTENTS]) == int(a[REJECTIONS]) + (int(a[STARTS]) if role == 0 else int(a[PLACEMENTS]))
        cash_ok = abs(a[CASH] - 100 - a[PRICE_PNL] - a[FIN_NET]) <= 1e-7
        if not (count_ok and pending_ok and intents_ok and cash_ok and np.max(np.abs(residual)) <= 1e-7):
            raise RuntimeError("Complete trade/order/cash/cost accounting failed")
        yearly = {y: periods[y]["marked_changes"][role] for y in periods}
        gates = {
            "actual_profit": nets[0] > contract["development_gates"]["actual_profit_strictly_above"],
            "all_stressed_profit": all(v > contract["development_gates"]["all_stressed_profit_series_strictly_above"] for v in nets[1:]),
            "both_years_all_valuations_positive": all(v > 0 for y in yearly.values() for v in y),
            "equity_drawdown": metrics[role, 0, 3] <= contract["development_gates"]["proxy_equity_drawdown_pct_at_most"],
            "genuine_lifecycle_turnover": a[STARTS]/supply["calendar"]["union_dates"] >= contract["development_gates"]["genuine_first_fills_per_normal_date_at_least"],
            "minimum_each_year": all(counts_by_year[y][role] >= contract["development_gates"]["genuine_first_fills_each_year_at_least"] for y in counts_by_year),
            "three_symbols": int(np.count_nonzero(by_symbol[role])) == 3,
            "both_directions": long_counts[role] > 0 and short_counts[role] > 0}
        roles[name] = {
            "actual_net": nets[0], "directional_stressed_net": nets[1], "midpoint_stressed_net": nets[2],
            "no_positive_credit_stressed_net": nets[3], "actual_marked_equity_dd_pct": metrics[role, 0, 3],
            "drawdown_metrics_by_valuation": metrics[role].tolist(), "calendar_marked_changes": yearly,
            "first_fills": int(a[STARTS]), "first_fills_per_normal_date": a[STARTS]/supply["calendar"]["union_dates"],
            "first_fills_by_year": {y: int(counts_by_year[y][role]) for y in counts_by_year},
            "closed_lifecycles_by_symbol": {s: int(by_symbol[role, i]) for i, s in enumerate(contract["symbols"])},
            "long_short_lifecycles": [int(long_counts[role]), int(short_counts[role])],
            "placed_pending": int(a[PLACEMENTS]), "causal_cancellations": int(a[CANCELLATIONS]),
            "specified_expirations": int(a[EXPIRATIONS]), "intents": int(a[INTENTS]),
            "rejection_reasons": {REASON_NAMES[i]: int(reason_counts[role, i]) for i in range(1, 10)},
            "price_profit": a[PRICE_PNL], "net_financing": a[FIN_NET], "positive_financing_removed": a[CREDIT],
            "negative_financing_charges": a[NEG_FIN], "directional_extra_spread": a[DIR_COST],
            "midpoint_extra_spread": a[MID_COST], "entry_spread_total": a[ENTRY_COST], "exit_spread_total": a[EXIT_COST],
            "complete_accounting": {"full_close_count": count_ok, "pending_ownership": pending_ok,
                "all_intents_classified": intents_ok, "cash": cash_ok, "trade_sum_residuals": residual.tolist(),
                "final_pending": 0, "final_positions": 0},
            "gates": gates, "passed": all(gates.values())}
    survivors = [name for name in contract["role_order"] if roles[name]["passed"]]
    survivors.sort(key=lambda name: (-roles[name]["no_positive_credit_stressed_net"],
                                     roles[name]["actual_marked_equity_dd_pct"],
                                     -min(v[3] for v in roles[name]["calendar_marked_changes"].values()),
                                     contract["role_order"].index(name)))
    # Every raw checkpoint is owned and hashed, alongside the primary tapes.
    for path in sorted(output.glob("*-checkpoint.json")):
        manifest.append(fp(path))
    result = {
        "schema": "zeta-ch014-complete-development-result-v1",
        "recorded_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "COMPLETE_DEVELOPMENT_SURVIVOR_REQUIRES_LOCKED_CONFIRMATION" if survivors else
                  "COMPLETE_VALID_ADVERSE_DEVELOPMENT_NO_SURVIVOR",
        "economic_freeze": fp(freeze_path), "input_seal": fp(ROOT/"evidence/INPUT_SEAL_V1.json"),
        "structural_authority": fp(ROOT/"evidence/STRUCTURAL_SUPPLY_V1.json"),
        "normal_source_dates": supply["calendar"]["union_dates"], "roles": roles, "calendar_periods": periods,
        "selected_unchanged_role": survivors[0] if survivors else None, "complete_passers": survivors,
        "source_rows_consumed_once_for_three_roles": source_rows,
        "action_rows": all_action_rows, "complete_trade_rows": all_trade_rows,
        "minute_equity_rows": all_equity_rows, "output_files": manifest,
        "output_bytes": sum(x["bytes"] for x in manifest),
        "columns": {"actions": ACTION_COLUMNS, "trades": TRADE_COLUMNS, "minute_equity": EQUITY_COLUMNS},
        "action_codes": ACTION_NAMES, "reason_codes": REASON_NAMES,
        "metric_columns": ["last_equity", "peak", "peak_msc", "max_dd_pct", "max_dd_usd",
                           "pct_peak", "pct_bottom", "pct_peak_msc", "pct_bottom_msc", "pct_bottom_symbol",
                           "pct_month", "pct_quote_row", "pct_source_ordinal",
                           "usd_peak", "usd_bottom", "usd_peak_msc", "usd_bottom_msc",
                           "usd_bottom_symbol", "usd_month", "usd_quote_row"],
        "valuation_order": ["actual", "directional_doubled_spread", "midpoint_doubled_spread", "directional_no_positive_credit"],
        "limitations": [
            "Observed quotes do not certify depth, latency, partial fill, historical permission, margin or broker stop-out. Risk-only admission and zero commission are explicit optimistic proxy limits.",
            "Frozen current swap mode 2 is only a dated 2024-2025 financing approximation. Crossed raw-day charges use recorded weekday/Friday triple convention, not a certified historical UTC/broker bridge.",
            "Fixed cross-symbol same-ms rank, exact-limit/no-favorable-gap fills and post-server-action quote marks are disclosed proxy semantics. No synthetic M1 intrabar path or native equity-DD claim.",
            "All stress accrues at actual executed entry/exit and financing events on the actual-sized path. Yearly marked changes and separately reconciled realized cash are both retained.",
            "All numeric tape columns are float64; every stored millisecond, ordinal and ID is below 2^53 and exactly representable. Column schemas preserve their integer interpretation."
        ],
        "locked_2026_opened": False, "candidate_EA_or_native_opened": False, "real_trading_API_calls": 0,
        "free_bytes_after": shutil.disk_usage(REPO).free}
    result["report_recovery"] = {"report_freeze": fp(report_freeze_path), "serialization_correction": fp(correction_path), "economic_traversals": 1, "economic_path_rerun": False, "complete_lifecycle_id_bijection": True}
    save_json(ROOT / "evidence/DEVELOPMENT_RESULT_V1.json", result)
    print(json.dumps({"status": result["status"], "selected_unchanged_role": result["selected_unchanged_role"],
                      "roles": {n: {k: x[k] for k in ("actual_net", "directional_stressed_net",
                        "midpoint_stressed_net", "no_positive_credit_stressed_net",
                        "actual_marked_equity_dd_pct", "first_fills", "first_fills_per_normal_date", "passed")}
                                for n, x in roles.items()}}), flush=True)


if __name__ == "__main__":
    main()
