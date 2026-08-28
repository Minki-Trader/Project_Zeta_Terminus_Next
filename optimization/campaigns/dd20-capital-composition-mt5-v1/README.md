# DD20 Capital Composition MT5 V1

This independent tester-only campaign materializes exactly the sole survivor from `dd20-capital-composition-proxy-v1`; it is not a new allocation search and does not rerun the completed 15-point risk-cap matrix.

## Frozen economic hypothesis

- Preserved MT5 parent: position risk `0.04`, aggregate risk `0.18`.
- Component order: range-61 / range-64 / US100 cross / US30 intraday pressure / US30 return / US100 impulse-passive.
- Component exposure multipliers: `3.0 / 3.0 / 1.0 / 2.5 / 1.0 / 0.0`.
- Effective per-position risk budgets before the unchanged global aggregate cap: `0.12 / 0.12 / 0.04 / 0.10 / 0.04 / disabled`.
- Aggregate planned-risk cap remains `0.18`; all signals, clocks, directions, volume ladder, costs, order types, stops, holds, ordering and execution logic otherwise remain inherited.

The zero-weight impulse-passive component is explicitly disabled in this tester-only family. Positive multipliers scale component volume and its planned-risk budget together, preserving the parent's stop geometry up to executable volume-step quantization. Real MT5 feedback through aggregate admission, overlap, margin and the existing sizing ladder is intentionally allowed because that is what the close-order proxy could not establish.

## Economic run

The single candidate uses real ticks from 2022-08-01 through 2026-06-01 for selection and a second isolated real-tick run from 2026-06-01 through 2026-08-01. The preserved `0.04 / 0.18` reports remain the exact economic comparator; they are not rerun. The hard decision budget is `20%` MT5 equity drawdown in both intervals, with actual and doubled-cost-stressed net retained.

Only complete valid economic output can decide this hypothesis. Compilation, runtime, history, configuration, report, logging, design or engineering defects are correction states without an economic verdict or retry limit.

The EA has unique Optimization identity, Magic `260828811..260828816`, state, research paths, source root, settings and dedicated Portable runtime. It is tester-only and has no Live or Lab authority.

## Current boundary

The corrected candidate completed both declared intervals with valid MT5 economics. Selection produced actual/stressed net `+$2,822.33 / +$2,648.883`, but native MT5 maximum relative equity drawdown was `27.072835%`, above the hard `20%` budget. Forward produced `+$36.67 / +$34.6175` at `15.850525%` MT5 equity drawdown. The exact `3/3/1/2.5/1/0` candidate is therefore closed as `EXPLOSIVE_PROFIT_CONFIRMED_BUT_SELECTION_MT5_DD_EXCEEDS_20_PERCENT`; it is not an improvement under the active objective and will not be rerun.

The complete selection artifact was preserved before the forward run. Its nested HTML report directory had not been precreated, but the native single-test cache contains the exact MT5 statistic block anchored by deposit, profit and OnTester values; the cache and extraction offsets are frozen in result evidence. The subsequent forward run emitted a normal HTML report after the report directory correction. Missing selection HTML was an invocation artifact, not an economic failure.
