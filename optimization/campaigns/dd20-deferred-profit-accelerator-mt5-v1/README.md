# DD20 Deferred Profit Accelerator MT5 V1

This tester-only campaign materializes exactly the sole role frozen by `dd20-deferred-profit-accelerator-proxy-v1`. Component multipliers remain `1.6 / 0.8 / 0.4 / 3.2 / 1.2 / 0`; the only economic change from the qualified MT5 anchor is its causal capital-growth schedule.

## Frozen candidate

- Reference capital `$100`, base volume `0.01`, per-position planned-risk fraction `0.04`, aggregate planned-risk fraction `0.18`.
- Until stressed closed profit reaches `+$450`, the day multiplier follows the qualified `$150` addition step exactly.
- After activation, each additional `$50` adds one multiplier unit, capped at `14`.
- The formula is `min(14, 1 + floor(min(growth, 450) / 150) + floor(max(0, growth - 450) / 50))`, where growth is causal stressed closed profit observed at the first source event of each server day.
- Component risk fractions before the aggregate cap remain `0.064 / 0.032 / 0.016 / 0.128 / 0.048 / disabled`. Executable lot normalization, planned-risk admission, stop geometry and protection remain authoritative.

The proxy selection actual/stressed result was `+$2,647.4747 / +$2,554.1534`; conservative actual/stressed was `+$2,083.5364 / +$2,006.6757`. Raw/calibrated/budgeted proxy DD was `17.428221% / 19.550372% / 19.800372%`, and all four epochs passed. Full-pair proxy stressed was `+$27.236`; conservative July stressed was `+$1.28`. These figures nominate one hypothesis only. Native MT5 economics decide qualification.

## Isolation and identity

- Source is a one-time physical derivation from the fully qualified `dd20-native-gap-july-robustness-mt5-v1` implementation.
- Thirteen Include modules remain byte-identical. Domain owns the new inputs/identity, Portfolio owns the deferred sizing formula, and the EA assembly owns only its new Include root, parameter assertions, output identity and state directories.
- EA: `ZetaDD20DeferredProfitAcceleratorMT5V1`
- Include root: `ZetaOptimizationDD20DeferredProfitAcceleratorMT5V1`
- Execution/release/portfolio: `zt-opt-live-v7-dd20-deferred-profit-accelerator-mt5-v1` / `OPT-LIVE-V7-DD20DPA1-20260828` / `ZT-OPT-LIVE-V7-DD20DPA1-20260828`
- Schema and Magic: `opt-dd20-dpa-mt5-1`, `260828851..260828856`
- State, research, SET, report and future Portable paths are unique. No EX5 was copied.

## Frozen MT5 path

After a dedicated physical Portable is created and this exact source compiles, run exactly one real-tick selection from `2022-08-01` through `2026-06-01`. After any complete valid selection, run exactly one independently initialized real-tick forward from `2026-06-01` through `2026-08-01`, even if the selection misses an economic gate, so the frozen hypothesis receives one complete comparison.

Economic qualification requires selection actual/stressed net strictly above the qualified anchor `+$1,691.54 / +$1,626.26`, positive actual/stressed net in all four selection epochs, native maximum relative selection equity DD `<=20%`, positive full-forward actual/stressed net, native maximum relative forward equity DD `<=20%`, and positive continuous June and July actual/stressed slices. Environment, compilation, invocation, history, reporting or logging defects are correction states with no economic verdict.

## Implementation freeze

Declaration commit `f9ffbac83c73b8ccb577f6abf47caa9eea611fed` reached `origin/main` before a new physical Portable was copied from the stopped qualified-candidate Optimization runtime. The source had no reparse point or process owner; the new target has a distinct terminal file ID, one terminal hard link and zero reparse points.

All 19 source/configuration files match their runtime overlays. One MetaEditor build 6140 invocation produced `0 errors / 0 warnings` in `2,315 ms`; the launcher returned `1`, while that same invocation wrote the complete compile log and the expected `231,652`-byte EX5. It was not reinvoked. The runtime owns zero process and its unique report directory is empty.

## Current boundary

The exact compiled candidate is ready with selection and forward economics still unopened. Freeze and push this implementation before the single selection run. The qualified anchor, every proxy grid, all prior MT5 candidates and the original 15 combinations remain closed without rerun. No Live or Lab mutation and no broker-state query occurred.
