# Market Stop Reverse-Lot Sizing — Unit 062 Implementation Correction

This sibling completes the already declared Unit 062 economic experiment without changing its question, intervention, periods, gates, terminal decisions, or exclusions.

- The closed `market-stop-reverse-lot-sizing-v1` root remains immutable.
- Source is derived once from the frozen forward baseline `lab/engineering/protective-exit-order-reconciliation-v1/mt5/` at commit `0d4032786cecb7d7e8a4c3074609db5b105fa107`.
- Pure implementation, invocation, report-path, and environment-freeze defects are corrected as often as needed before a valid result; they do not create additional experiments.
- A maximum of five economically valid Tester paths remains inherited: one fit path, two selection paths, and, only after a selection pass, two latest paths.
- No Live, broker/account state, Program 6, adjacent ATR, sizing, stop, component, period, or subgroup rescue is authorized.

The binding pre-outcome declaration is in `evidence/MARKET_STOP_REVERSE_LOT_SIZING_IMPLEMENTATION_CORRECTION_DECLARATION_V1.json`.

Closed result: the one valid fit and adjacent native/candidate selection pair completed with full integrity. Native stop-to-ATR drift was material, but the fitted profile blocked `23/74` sizing attempts at broker minimum lot, changed volume on `0/50` accepted entries and materially worsened selection value, turnover, efficiency, breadth and stop loss. Verdict `MARKET_STOP_REVERSE_LOT_INFEASIBLE_AT_REFERENCE_CAPITAL`; native stop/lot is preserved and latest remains unopened. See `evidence/MARKET_STOP_REVERSE_LOT_SIZING_RESULT_V2.json` and `evidence/MARKET_STOP_REVERSE_LOT_SIZING_CLOSURE_V2.json`.
