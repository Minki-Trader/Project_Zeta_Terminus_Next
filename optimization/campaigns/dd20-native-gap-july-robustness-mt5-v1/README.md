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

## Closed result

Implementation commit `954b659492e2c06026335d3d783bce888bed9e5e` reached `origin/main` before exactly one selection and one independently initialized full June-July forward ran. Both passes used build 6140 real ticks, reported `100% real ticks`, stopped normally, produced complete HTML/native-cache/EA economics and ended with zero safety, persistence, broker, foreign, protection or catchup fault.

Selection actual/stressed net is `+$1,691.54 / +$1,626.26` across `1,295` closed lifecycles. This beats the preserved comparator by `+$524.65 / +$540.852`, or `44.9614% / 49.8294%`. All four chronological epochs are positive. Native maximum relative equity DD is `19.550371765%`, leaving `0.449628235` percentage points under the hard `20%` cap.

The independent full forward earned actual/stressed `+$23.01 / +$21.256` at native maximum relative equity DD `12.436759043%`. Its continuous slices are June `+$19.79 / +$18.976` and July `+$3.22 / +$2.280`; all required actual and stressed gates pass. The proxy's deliberately conservative July estimate remained below the observed positive result.

Selection raw evidence is preserved as `24` files / `53,559,254` bytes / canonical manifest `1C1222D9DC407440A135D0E01BC305595E1805707B71D21D8BBA828D345523B9`. Forward evidence is `20` files / `27,819,980` bytes / manifest `80F49175F770B9536DD9E0F10870C1826F1C1139B2CCFB21EAA423DFC9F20BF9`. The original 15 combinations and all prior candidates remain closed without rerun.

Status is `VALID_MT5_COMPLETE_ALL_ECONOMIC_GATES_PASS`; classification is `MT5_CONFIRMED_DD20_NATIVE_GAP_JULY_ROBUST_PROFIT_UPLIFT_CANDIDATE`. This is a qualified optimization success anchor, not an automatic Live promotion. The Goal continues with a distinct proxy-first search for more stressed profit through component redistribution inside the native DD budget.
