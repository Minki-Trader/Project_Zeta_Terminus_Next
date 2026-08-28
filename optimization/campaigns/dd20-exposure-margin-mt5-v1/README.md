# DD20 Exposure Margin MT5 V1

This independent tester-only campaign materializes exactly the sole survivor from `dd20-mt5-calibrated-exposure-margin-proxy-v1`. It is not another allocation search and does not rerun the completed 15-point risk-cap matrix, the rejected `3 / 3 / 1 / 2.5 / 1 / 0` candidate, or the `2 / 1.5 / 2 / 2.5 / 1.5 / 0` near miss.

## Frozen economic hypothesis

- Preserved MT5 parent: position risk `0.04`, aggregate risk `0.18`.
- Component order: range-61 / range-64 / US100 cross / US30 intraday pressure / US30 return / US100 impulse-passive.
- Component exposure multipliers: `1.8 / 1.3 / 1.4 / 2.6 / 1.5 / 0.0`.
- Effective per-position risk budgets before the unchanged global aggregate cap: `0.072 / 0.052 / 0.056 / 0.104 / 0.06 / disabled`.
- Proxy selection actual/stressed net: `+$4,425.620214 / +$4,176.476000` at calibrated/budgeted DD `19.288409% / 19.788409%`.
- Full paired-forward actual/stressed net: `+$26.42 / +$23.987` at calibrated/budgeted DD `15.593967% / 15.843967%`; independent June and July stressed nets are `+$19.371 / +$4.616`.

The zero-weight impulse-passive component is explicitly disabled. Positive multipliers scale component executable volume and its planned-risk budget together while preserving stop geometry up to volume-step quantization. Real MT5 aggregate admission, overlap, margin, floating equity and execution feedback are the purpose of this confirmation.

The source is a one-time self-contained derivation from the final corrected executable-volume and protective-stop implementation of `dd20-paired-month-stability-mt5-v1`. Fourteen inherited Include modules remain byte-identical; only the Domain identity/default multipliers and EA assembly identity/assertions differ. There is no source or Include link back to that frozen family.

## Economic run

One real-tick selection covers 2022-08-01 through 2026-06-01. After a complete valid selection, one separately initialized real-tick forward covers the full paired months 2026-06-01 through 2026-08-01. Both declared intervals are retained even if the selection misses an economic gate; neither result authorizes rescue or retuning inside this campaign.

The preserved `0.04 / 0.18` reports remain the comparator and are not rerun. A confirmed candidate must exceed comparator selection actual/stressed net `+$1,166.89 / +$1,085.408`, keep selection maximum relative MT5 equity DD at or below `20%`, retain positive actual and doubled-cost-stressed forward net, and keep forward maximum relative MT5 equity DD at or below `20%`.

Only complete valid economic output can decide the hypothesis. Compilation, runtime, history, configuration, report, logging, design or engineering defects are correction states without an economic verdict or retry limit.

The EA has unique Optimization identity, Magic `260828831..260828836`, state, research paths, source root, settings and a dedicated Portable runtime. It is tester-only and has no Live or Lab authority.

## Current boundary

Source and fixed configuration are derived and frozen with all compilation, runtime, Tester, reports and economic output still unopened. Commit and push this declaration before creating the dedicated runtime.
