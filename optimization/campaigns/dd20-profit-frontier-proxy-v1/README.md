# DD20 Profit Frontier Proxy V1

This serial optimization campaign explores aggressive component capital allocation before any further MT5 run. It is derived from the completed `0.04 / 0.18` maximum-profit observation of `portfolio-risk-cap-envelope-v1`, copied into a campaign-owned raw input bundle rather than linked to another campaign at execution time.

## Economic question

Holding the observed `0.04 / 0.18` entry, exit and lifecycle order fixed, can a static six-component risk-allocation multiplier produce materially larger actual and doubled-cost-stressed profit while keeping a conservative closed-balance drawdown proxy at or below the user's hard `20%` equity-drawdown budget?

This is selection research, not MT5 profit proof. It does not simulate changed stops, admissions, margin, overlapping mark-to-market equity, order execution or feedback from a changed balance into later sizing. Its only authority is to shrink a large search space to at most three economically distinct MT5 candidates.

## Frozen proxy contract

- Input stream: exact copied agent-3002 lifecycle ledger from the completed 15-point campaign.
- Selection stream: segment 3, pass 13, `0.04 / 0.18`, 2022-08-01 through 2026-06-01.
- Later observation: segment 6, pass 13 forward, 2026-06-01 through 2026-08-01. It is never used to rank or alter selection weights.
- Component multipliers: exhaustive Cartesian grid `0.50 / 0.75 / 1.00 / 1.25 / 1.50 / 1.75 / 2.00` for all six components; `117,649` combinations.
- Proxy actual and stressed balances start at `$100` and add each lifecycle's corresponding net multiplied by its component weight in original close order.
- Proxy drawdown is the worse of actual and stressed peak-to-current closed-balance percentage drawdowns. It is intentionally not calibrated downward to the lower observed MT5 percentage.
- Selection is split at 2024-07-01 into two equal 23-month blocks. Full selection and both blocks must keep actual/stressed balance positive, actual/stressed net positive and proxy drawdown at or below `20%`.
- Role 1 maximizes full-selection stressed net. Role 2 maximizes one-step-neighborhood median stressed net with broad support. Role 3 maximizes the weaker block's stressed-net uplift versus the unweighted base. Duplicate role winners are replaced by the next distinct result under that role's frozen ordering.
- Only after the three role weights are fixed is the later segment opened. Positive later actual net, positive later stressed net and proxy drawdown at or below `20%` are required to enter the MT5 shortlist. No failed later role is rescued or retuned.

The campaign uses no MT5 runtime, MQL source, broker state, Lab path, Live path, validator, parity checker or test harness. The frozen declaration is `evidence/DD20_PROFIT_FRONTIER_PROXY_DECLARATION_V1.json`.

## Result

The deterministic proxy completed all `117,649` combinations in about 26 seconds; `105,330` passed the selection gates. The three frozen roles raised selection stressed net from `$1,085.408` to `$2,129.046-$2,138.484` while using `19.81-19.99%` proxy drawdown.

After those weights were fixed, all three failed the later confirmation: actual net was `-$3.77` to `-$4.98`, stressed net was `-$7.595` to `-$8.762`, and proxy drawdown was `25.15-26.02%`. No role was rescued or retuned. The result is `VALID_PROXY_COMPLETE_NO_MT5_SHORTLIST`, and this campaign launches no MT5 path. Exact evidence is `evidence/DD20_PROFIT_FRONTIER_PROXY_RESULT_V1.json`.
