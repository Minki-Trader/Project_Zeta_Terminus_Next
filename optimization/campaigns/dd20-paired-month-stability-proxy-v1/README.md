# DD20 Paired-Month Stability Proxy V1

This independent proxy asks for the highest long-selection stressed profit among executable-lattice candidates that are separately profitable and DD-safe in both June and July 2026.

## Why this direction

The selection-only maximum failed the combined recent segment, and the next June-stable maximum still failed untouched July. Both failures concentrated in US100-cross. Another one-month confirmation would repeat the same weakness. This campaign therefore makes both recent months explicit stability gates before spending a single MT5 run.

## Frozen search

- All six weights use `0 / 0.5 / 1 / 1.5 / 2 / 2.5 / 3`, with at least four active: exactly `112,752` compositions.
- The event-driven model is the already corrected executable-lattice model: `0.01` lot materialization, impulse reservation volume, `$150` stressed-balance sizing ladder, `0.04` position risk and `0.18` aggregate admission.
- Long selection requires positive actual/stressed full and four-epoch results, positive balances, full upward-only calibrated DD at or below `20%`, and every epoch raw DD at or below `20%`.
- Selection-eligible candidates must then pass June independently from `$100`: positive actual/stressed net, positive balance and raw DD at or below `20%`.
- June-qualified candidates must separately pass July from `$100` under the same conditions.
- One role freezes from the paired-month-qualified population: maximize long-selection stressed net, then the weaker monthly stressed net, the two-month stressed sum, selection actual, recent-selection stressed, lower calibrated DD and deterministic lexicographic weights.
- Both months are development gates in this campaign. No proxy holdout remains afterward. A passing role authorizes exactly one MT5 selection plus full June/July forward hypothesis; MT5 real-tick economics and maximum relative equity DD remain the confirmation.

The original 15 combinations, the rejected `3/3/1/2.5/1/0` MT5 candidate and both closed proxy winners remain untouched. This campaign has no Live or Lab authority.
