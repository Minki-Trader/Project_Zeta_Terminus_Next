# DD20 Fixed-Pair August Relative MT5 V1

This closed independent Optimization campaign is the single native escalation authorized by `dd20-fixed-pair-august-relative-proxy-v1`. It tested whether the already fixed replacement-development contract materially outperformed the exact active Live-derived control from the start of August through the last completed session on August 28, 2026.

## Frozen adjacent pair

One self-contained EA accepts exactly two economic tuples and rejects every other risk or weight combination:

- `CONTROL`: weights `1 / 1 / 1 / 1 / 1 / 1`, position risk `0.04`, aggregate risk `0.12`.
- `CANDIDATE`: weights `2 / 1.5 / 2 / 2.5 / 1.5 / 0`, position risk `0.04`, aggregate risk `0.18`.

All formulas, component clocks, execution priority, stops, daily sizing, reserve/headroom, cost observation and Tester settings remain identical. The exact control runs first and the exact candidate runs immediately afterward in the same dedicated non-Master Portable with the same compiled EX5 and tick/history fingerprint. Only the declared contract parameters and role-specific report/output archive differ.

The earlier candidate-only August result remains a native anchor. It cannot substitute for this pair. If the paired candidate does not reproduce `+$29.62 / +$28.586`, `29` closes and the same report economics, the matrix is an engineering-correction state rather than an economic result.

## Economic judgment

Both paths must finish normally with complete finite evidence and `100%` real ticks. The candidate must preserve positive actual and doubled-observed-cost-stressed net, exceed control stressed net by at least `$5`, and have higher stressed profit factor. Native drawdown, week breadth, active-component breadth and concentration are disclosed under the nominal and practical rules frozen before either path opens in the declaration.

This campaign performs no grid, retune, formula change, strategy change or successor selection. It has no Live, Lab, release or promotion authority.

## Closed result

Both adjacent roles completed normally at `100%` real ticks under one byte-identical EX5 and one unchanged 18-file Tester-consumed market fingerprint. The candidate exactly reproduced its frozen `+$29.62 / +$28.586 / 29 closes / 13.44% equity DD` anchor. The exact Live-derived control earned `+$13.05 / +$12.455` across `44` closes at `6.06%` native relative equity DD.

The candidate therefore added `+$16.57` actual and `+$16.131` doubled-cost-stressed net, raised exact stressed PF from `1.5427` to `1.8833`, won three of four weekly comparisons, kept all five active components positive and limited its largest stressed-net component share to `32.52%`. It did so with `34.09%` fewer closes and `3.48x` control stressed net per close.

The qualification is material: native relative equity DD rose by `7.38pp`, missing the frozen nominal `+5pp` allowance but remaining inside the separately frozen practical `+7.5pp` allowance. The final week was worse (`-$1.118` versus `-$0.151`), the worst day was much deeper, and native recovery factor fell from `1.83` to `1.65`. The fixed practical rule nevertheless passes because every core condition and all three non-DD contextual checks passed.

The closed classification is `VALID_FIXED_REPLACEMENT_RELATIVE_AUGUST_MT5_SUPPORT`. This strengthens the already fixed replacement development candidate; it does not retune it, authorize Live promotion or open an adjacent risk/weight rescue.
