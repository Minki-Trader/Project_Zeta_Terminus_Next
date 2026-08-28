# DD20 Capital Composition MT5 V1

This independent tester-only campaign materializes exactly the sole survivor from `dd20-capital-composition-proxy-v1`; it is not a new allocation search and does not rerun the completed 15-point risk-cap matrix.

## Frozen economic hypothesis

- Preserved MT5 parent: position risk `0.04`, aggregate risk `0.18`.
- Component order: range-61 / range-64 / US100 cross / US30 intraday pressure / US30 return / US100 impulse-passive.
- Component risk multipliers: `3.0 / 3.0 / 1.0 / 2.5 / 1.0 / 0.0`.
- Effective per-position risk budgets before the unchanged global aggregate cap: `0.12 / 0.12 / 0.04 / 0.10 / 0.04 / disabled`.
- Aggregate planned-risk cap remains `0.18`; all signals, clocks, directions, volume ladder, costs, order types, stops, holds, ordering and execution logic otherwise remain inherited.

The zero-weight impulse-passive component is explicitly disabled in this tester-only family. Positive multipliers scale only that component's protective-stop risk budget. Real MT5 feedback through stop geometry, aggregate admission, overlap, margin and the existing sizing ladder is intentionally allowed because that is what the close-order proxy could not establish.

## Economic run

The single candidate uses real ticks from 2022-08-01 through 2026-06-01 for selection and the already isolated 2026-06-01 through 2026-08-01 custom forward interval. The preserved `0.04 / 0.18` reports remain the exact economic comparator; they are not rerun. The hard decision budget is `20%` MT5 equity drawdown in both intervals, with actual and doubled-cost-stressed net retained.

Only complete valid economic output can decide this hypothesis. Compilation, runtime, history, configuration, report, logging, design or engineering defects are correction states without an economic verdict or retry limit.

The EA has unique Optimization identity, Magic `260828811..260828816`, state, research paths, source root, settings and dedicated Portable runtime. It is tester-only and has no Live or Lab authority.

## Current boundary

The isolated EA compiled with MetaEditor build 6140 at `0 errors / 0 warnings`. Source, configuration, EX5 and the physical dedicated Portable are frozen with no MT5 economic output opened. The implementation declaration is `evidence/DD20_CAPITAL_COMPOSITION_MT5_IMPLEMENTATION_FREEZE_V1.json`; commit and push it before the one-candidate run.
