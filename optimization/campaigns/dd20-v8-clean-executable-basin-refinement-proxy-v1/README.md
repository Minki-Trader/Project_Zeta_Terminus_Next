# DD20 V8 Clean Executable Basin Refinement Proxy V1

This campaign is mandatory Stage B of `V8-OPT-U001-PORTFOLIO-DD`. It refines the three valid Stage-A executable centers at half weight and aggregate-cap steps before any causal state rule, stability layer or native MT5 path may open.

## Exact-V8-only ancestry

- Economic parent: `NEXT-E02-V8-PMLR1-b1c77d3b6356`.
- Exact clean lifecycle and decision ledgers remain byte-equal to Stage A.
- The complete frozen Stage-A raw result is an input only to identify the three preselected centers.
- V7, Lab, legacy Optimization and external economics do not select or tune this stage.

## Frozen local union

Each center receives offsets `-0.125 / 0 / +0.125` on RC61, RC64, Cross, Intraday and Return and `-0.015 / 0 / +0.015` on aggregate risk. Values clip to the Stage-A monotone bounds, Passive stays `0`, and base position risk stays exact V8 `0.04`. Duplicate exact parameter vectors are removed.

The three center-local sets contain `144 / 216 / 144` vectors and their exact union contains `504`. Fine neighbors differ by one declared fine step on exactly one axis. Eligibility requires at least four eligible fine neighbors spanning at least three axes.

Development, fresh validation, locked holdout, primary/fallback gates, ranking and no-holdout-substitution remain unchanged. At most three Stage-B centers may pass to mandatory Stage C. No MT5 path may run in Stage B.

## Scope boundary

This stage may only suppress, reorder or resize exact-V8 opportunities through the frozen portfolio axes. It does not add a symbol, timeframe, signal, direction or opportunity timestamp. Later isolated Optimization stages may change code/mechanisms, remove existing components or reconstruct the V8 portfolio, but a new entry strategy remains Lab and is not opened under this Goal.

## Frozen implementation boundary

Declaration commit `7f36ba276a2575fb8246760705692c79e77b7f46` reached `origin/main` before staging. The three inputs are byte-equal, the Stage-A schema/status and all three center vectors match, and the local counts reproduce `144 / 216 / 144` with an exact `504 / 504` value/coordinate union. The inherited Stage-A executable model is unchanged.

Config is `5,146` bytes / `AF5211E7...F84DE`; the Python source is `43,915` bytes / `51DB529A...739CD` and passes Python `3.13.9` syntax compilation with NumPy `2.3.4`. No Stage-B output exists. Execution waits until the implementation-freeze boundary reaches `origin/main`.

## Final Stage-B result

The unchanged run completed `504` candidates in `0.5285798s`: `216` primary-eligible, `324` fallback-eligible and all `216` active-tier points on the fine-neighbor plateau. The three selected centers are the three exact Stage-A seeds, each with seven eligible neighbors across five axes and identical development/validation economics. No half-step nonseed displaced a seed.

All three validation roles pass and advance as static Stage-C seeds. Frozen canonical order selected `1.25 / 1.5 / 1.5 / 2 / 1.25 / 0`, risk `0.04`, cap `0.12` for the sole holdout; it passed actual/stressed `+$23.3743 / +$21.5323` at `13.8019%` actual DD. Its continuous whole replay is `+$311.327 / +$281.3365` at `24.0998%` actual DD, retaining `76.4880%` of exact-V8 stressed net. Other seeds did not receive post-hoc holdout/whole treatment, so whole-path identity among the three is not claimed.

Final status is `VALID_PROXY_COMPLETE_STAGE_B_SURVIVOR_STAGE_C_REQUIRED_NO_MT5`. Stage B confirms the local static basin without improving it; mandatory causal Stage C opens next with zero MT5, Lab, new-entry or Live authority.
