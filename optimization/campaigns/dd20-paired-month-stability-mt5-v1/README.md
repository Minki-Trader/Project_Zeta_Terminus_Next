# DD20 Paired-Month Stability MT5 V1

This independent tester-only campaign materializes exactly the sole survivor from `dd20-paired-month-stability-proxy-v1`. It is not another allocation search and does not rerun either the completed 15-point risk-cap matrix or the rejected `3 / 3 / 1 / 2.5 / 1 / 0` MT5 candidate.

## Frozen economic hypothesis

- Preserved MT5 parent: position risk `0.04`, aggregate risk `0.18`.
- Component order: range-61 / range-64 / US100 cross / US30 intraday pressure / US30 return / US100 impulse-passive.
- Component exposure multipliers: `2.0 / 1.5 / 2.0 / 2.5 / 1.5 / 0.0`.
- Effective per-position risk budgets before the unchanged global aggregate cap: `0.08 / 0.06 / 0.08 / 0.10 / 0.06 / disabled`.
- Proxy selection actual/stressed net: `+$5,551.563583 / +$5,237.142726` at `19.423399%` proxy DD.
- Independent June actual/stressed net: `+$29.21 / +$27.474`; independent July: `+$4.10 / +$3.00`.

The zero-weight impulse-passive component is explicitly disabled. Positive multipliers scale component executable volume and its planned-risk budget together while preserving stop geometry up to volume-step quantization. Real MT5 aggregate admission, overlap, margin, floating equity and execution feedback are the purpose of this confirmation.

The source is a one-time self-contained derivation from the final corrected executable-volume and protective-stop implementation of `dd20-capital-composition-mt5-v1`. Fourteen inherited Include modules remain byte-identical; only the Domain identity/default multipliers and EA assembly identity/assertions differ. There is no source or Include link back to that frozen family.

## Economic run

One real-tick selection covers 2022-08-01 through 2026-06-01. After a complete valid selection, one separately initialized real-tick forward covers the full paired months 2026-06-01 through 2026-08-01. Both declared intervals are retained even if the selection misses an economic gate; neither result authorizes rescue or retuning inside this campaign.

The preserved `0.04 / 0.18` reports remain the comparator and are not rerun. A confirmed candidate must exceed comparator selection actual/stressed net `+$1,166.89 / +$1,085.408`, keep selection maximum relative MT5 equity DD at or below `20%`, retain positive actual and doubled-cost-stressed forward net, and keep forward maximum relative MT5 equity DD at or below `20%`.

Only complete valid economic output can decide the hypothesis. Compilation, runtime, history, configuration, report, logging, design or engineering defects are correction states without an economic verdict or retry limit.

The EA has unique Optimization identity, Magic `260828821..260828826`, state, research paths, source root, settings and dedicated Portable runtime. It is tester-only and has no Live or Lab authority.

## Current boundary

The hypothesis, source and configuration were frozen before compilation or outcome access. The dedicated physical Portable now holds the exact files and the EA compiled on build 6140 at `0 errors / 0 warnings`; EX5 SHA-256 is `7CBB59370764B8299406DF14A8A7546BFC6DFFCBE80B5FD0F43DA227F68C0DBD`. No MT5 tester, report or economic result has opened yet. Commit this implementation freeze before the one declared selection and full June/July forward.
