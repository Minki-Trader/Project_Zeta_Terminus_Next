# Portfolio Risk-Cap Envelope V1

Active continuous-optimization campaign derived once from the frozen optimization copy of Live release NEXT-E01-V7-RLO1-b32e7e176f2e.

## Economic question

With all six parent signals, clocks, directions, orders, costs, stops, holds, sizing ladder and portfolio ordering unchanged, does a different pair of per-position and aggregate planned-risk caps improve the whole portfolio?

The complete selection grid is:

- InpMaximumPositionRiskFraction: 0.03 / 0.04 / 0.05
- InpMaximumAggregateRiskFraction: 0.10 / 0.12 / 0.14 / 0.16 / 0.18
- 15 exhaustive combinations, including the parent 0.04 / 0.12

Selection uses 2022-07-01 through 2026-06-01. The latest two completed months, 2026-06-01 through 2026-08-01, are the MT5 custom forward interval and do not select parameters.

The custom economic criterion is robust recovery: the lesser of actual and doubled-cost stressed net divided by the greater of actual equity and stressed closed drawdown. The full result also retains actual/stressed net, both drawdowns, lifecycle count, risk skips, stop exits and component economics.

## Decision

A candidate can replace the parent risk caps only if its selection economics are not dominated by 0.04 / 0.12, its robust recovery improves by at least 5%, it retains at least 90% of parent lifecycles, no parent-positive component becomes nonpositive, and the isolated latest interval improves robust net without worsening robust drawdown. Otherwise retain the parent caps and continue to the next optimization stage.

Only valid complete economic output can reach that decision. Runtime, history, compilation, report, logging, design or engineering faults are CORRECTION_REQUIRED, repaired without an arbitrary count limit and never classified as optimization failure.

This EA is tester-only, owns Magic 260828801..260828806, and uses only the dedicated optimization/runtime/portfolio-risk-cap-envelope-v1-portable/ terminal. It has no Live or Lab authority.

## Current boundary

The final CRLF/UTF-8 source compiled on MetaEditor build 6140 at `0 errors / 0 warnings`. The frozen EX5 SHA-256 is `795E22154D389C3FEBCE0B8E37D3A2E4AECD08F71BADEB3B7AE1F51BE7D40D22`. No Tester path or economic result has been opened; the exact implementation boundary is recorded in `evidence/PORTFOLIO_RISK_CAP_ENVELOPE_IMPLEMENTATION_FREEZE_V1.json`.
