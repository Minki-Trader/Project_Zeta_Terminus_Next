# DD20 Native-Gap July-Robustness MT5 V1

This tester-only campaign materializes exactly the sole role frozen by `dd20-native-gap-july-robustness-proxy-v1`: component multipliers `1.6 / 0.8 / 0.4 / 3.2 / 1.2 / 0` in range-61 / range-64 / US100 cross / US30 intraday pressure / US30 return / impulse-passive order. It does not reopen the nearby proxy rows, the three prior MT5 candidates or the original 15 combinations.

## Frozen candidate

- Reference capital `$100`, base volume `0.01`, stressed-balance addition step `$150`, per-position planned-risk fraction `0.04`, aggregate planned-risk fraction `0.18`.
- Pre-cap component risk fractions are `0.064 / 0.032 / 0.016 / 0.128 / 0.048 / disabled`. Executable lot normalization and the aggregate cap remain authoritative.
- Proxy selection actual/stressed was `+$1,763.4819 / +$1,693.3221`; raw/calibrated/budgeted DD was `17.428221% / 19.210908% / 19.960908%`.
- Proxy full-pair actual/stressed was `+$28.87 / +$27.236` at budgeted DD `15.310773%`. Continuous-error-adjusted July actual/stressed remained `+$1.48 / +$0.9025` after the frozen shortfalls and `$1` reserve.
- These figures nominate one hypothesis only. Native MT5 economics decide qualification.

## Isolation and identity

- Source is a one-time physical derivation from the final corrected `dd20-exposure-margin-mt5-v1` implementation. Fourteen non-Domain Include modules remain byte-identical; Domain identity/default multipliers and the EA assembly are the only source changes.
- EA: `ZetaDD20NativeGapJulyRobustnessMT5V1`
- Include root: `ZetaOptimizationDD20NativeGapJulyRobustnessMT5V1`
- Execution/release/portfolio: `zt-opt-live-v7-dd20-native-gap-july-robustness-mt5-v1` / `OPT-LIVE-V7-DD20NGJR1-20260828` / `ZT-OPT-LIVE-V7-DD20NGJR1-20260828`
- Schema and Magic: `opt-dd20-ngjr-mt5-1`, `260828841..260828846`
- State, research, SET, report and future Portable paths are unique to this campaign. No EX5 was copied.

## Frozen MT5 path

After a dedicated physical Portable is created and this exact source compiles, run exactly one real-tick selection from `2022-08-01` through `2026-06-01`. After a complete valid selection, run exactly one independently initialized real-tick forward from `2026-06-01` through `2026-08-01`, even if selection economics do not qualify, so the frozen hypothesis receives one complete comparison.

Economic qualification requires selection actual/stressed net above the preserved `+$1,166.89 / +$1,085.408` comparator, positive actual/stressed net in all four selection epochs, native maximum relative selection equity DD `<=20%`, positive full-forward actual/stressed net, native maximum relative forward equity DD `<=20%`, and positive continuous June and July actual/stressed slices. Environment, compilation, invocation, history, reporting or logging defects are correction states with no economic verdict.

## Current boundary

Source and configuration are frozen with compilation and all Tester economics unopened. Commit and push this declaration before creating the dedicated runtime.
