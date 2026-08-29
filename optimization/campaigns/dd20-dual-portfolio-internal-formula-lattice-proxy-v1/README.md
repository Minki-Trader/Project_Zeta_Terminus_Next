# DD20 Dual-Portfolio Internal-Formula Lattice Proxy V1

This independent Optimization campaign parameterizes the internal decision formulas shared by the exact active Live-derived control and the fixed `dd20-paired-month-stability-mt5-v1` replacement candidate. It asks whether a broad, causal formula surface contains an economically stable improvement that transfers across both portfolio contracts.

## Fixed paired contracts

- `LIVE_CONTROL`: weights `1 / 1 / 1 / 1 / 1 / 1`, position risk `0.04`, aggregate risk `0.12`.
- `FIXED_REPLACEMENT`: weights `2 / 1.5 / 2 / 2.5 / 1.5 / 0`, position risk `0.04`, aggregate risk `0.18`.
- Component clocks, execution priority, daily sizing ladder, positive `MathRound` lot materialization, risk reserve/headroom, stop geometry and symbol mapping remain fixed.
- The five active replacement formulas are semantically identical to the frozen Live-derived baseline after newline normalization. Passive is evaluated for `LIVE_CONTROL` and remains exactly inert in `FIXED_REPLACEMENT`.

This campaign does not optimize weights, risk, clocks or Live behavior. A shared formula point is always evaluated under both fixed contracts so formula main effects can be separated from portfolio interaction.

## Frozen broad search

The full contract is in `config/campaign-contract.json`. It includes the exact baseline, every one-axis level, central and extreme profiles, asymmetric threshold profiles, and a deterministic unscrambled Sobol atlas filled to `8,192` unique broad points. The ranges deliberately include loose, strict, short, long, continuation, reversal, raw, centered, fast, slow and economically inert/no-trade edges. A predeclared plateau stage may add at most `512` local neighbors around no more than eight E1-E3 basin medoids.

The formula surface covers:

- RC16 and RC4 compression/normal/direction windows, asymmetric thresholds, direction semantics and holds;
- Cross scale, centering, US30/US500 peer decomposition, asymmetric thresholds, direction semantics and holds;
- Pressure daily scale distribution, location center/shape, range exponent, asymmetric thresholds, direction semantics and holds;
- Return impulse/scale windows, normalization exponent, centering, overlap, asymmetric thresholds, direction semantics and holds;
- control-only Passive state/scale/entry/exit/limit/activation/hold/cooldown/direction terms;
- RC4 adverse-compression checkpoint, retained loss, ordinal asymmetry, head penalties/dynamics and vote threshold.

## Causal economic boundary

The proxy owns a one-time lean physical copy of the closed candidate Optimization Portable. Only that new runtime may export Optimization-owned market bars. Acquisition is limited to terminal initialization, symbol selection, symbol metadata and rate history; broker account, position, order and deal state are out of scope.

Signals are regenerated from causal completed bars. M1 bid OHLC and recorded spread drive entry, limit fill, stop and time exit; the additional stressed cost uses the component-calibrated larger of entry/exit M1 spread, matching the preserved native lifecycle rule. Both contracts run chronologically with their own balance, daily lot ladder, component occupancy, aggregate risk admission and closed-balance drawdown. Passive pending orders and RC4 tightened-stop shadow occupancy are modeled. Because M1 cannot establish tick ordering, slippage, exact floating-equity extrema or native RC4 stop legality, all proxy economics remain nonbinding clues.

The exact baseline point must first reproduce signal features and approximate native lifecycle counts/economics within the declared anchor tolerances. A miss is `CORRECTION_REQUIRED`, not an optimization failure, and no nonbaseline result may be judged until corrected.

## Time isolation and one-shortlist rule

- Broad selection: E1 `2022-08-01..2023-06-01`, E2 `2023-06-01..2024-06-01`, E3 `2024-06-01..2025-06-01`.
- Nominees and one possible MT5 priority role freeze from E1-E3 only.
- E4 `2025-06-01..2026-06-01` is opened afterward and cannot promote a runner-up.
- June and July 2026 are opened last as independent `$100` books and as one continuous two-month book. A failure cannot be rescued by another grid point.
- At most one exact `(contract, formula point)` may advance to a dedicated non-Master MT5 Strategy Tester, with its immediately adjacent exact control only when needed for run validity.

No proxy result changes Live or Lab and no Optimization candidate has direct Live promotion authority.

## Closed result

The final corrected surface contains `8,192` broad points plus `447` new plateau points, or `8,639` unique formula points and `17,278` paired economic tasks. The baseline feature anchor matched `5,085 / 5,085` rows within `1e-8`, and all four native control/replacement selection/forward economic anchors passed before any nonbaseline judgment.

The broad search was genuinely destructive: median stressed net was `-$21.91` for `LIVE_CONTROL` and `-$32.34` for `FIXED_REPLACEMENT`, while median anchor-proportional DD was `38.73% / 76.45%`. The exact baseline already sat at the `97.71 / 98.33` stressed-net percentiles and the `96.41 / 97.92` lower-DD percentiles. Only ten points improved the worst E1-E3 stressed epoch in both contracts.

No fixed-replacement or paired medoid survived its owned 64-point plateau. The counts are:

- core eligible: `1,277 / 1,273 / 1,037` for Live / replacement / paired;
- robust eligible: `7 / 0 / 0`;
- paired surface PBO `64.29%`, White Reality Check `p=0.516`;
- fixed-replacement surface PBO `74.29%`, White Reality Check `p=0.214`.

The descriptive fixed-replacement ceiling changes only Pressure from symmetric continuation to negative-only short. It improves E1-E3 stressed net from `$1,217.715` to `$1,356.923` and point DD from `20.257%` to `18.770%`, but its local DD ninetieth percentile is `26.736%`. It then loses `$113.592` versus baseline in E4 and `$22.432` in continuous June-July 2026. The apparent improvement is also an interaction effect: component deltas are RC16 `+$33.957`, RC4 `-$21.586`, Cross `+$8.261`, Pressure `+$33.044` and Return `+$85.531`, with the largest positive monthly deltas in March-April 2025 before the later reversal.

The Live-control ceiling changes Return overlap to pre-impulse but produces exactly zero economic difference in every opened interval. It is a flat formula alternative, not a replacement clue.

The verdict is `NO_ROBUST_SHARED_FORMULA_REPLACEMENT_CLUE_FIXED_CANDIDATE_RETAINED_LAB_ONLY_INTERACTION_SEEDS_RECORDED`. No point advances to MT5 and no runner-up can rescue the bundle. Two post-selection interaction observations are retained as Lab-only hypothesis clues, not candidates: RC4 direction fraction `0.75` with Return centering `1.0`, and RC4 direction fraction `0.75` with Pressure negative-only mode. Neither owns an unopened robustness neighborhood or later-data authority in this campaign.

Engineering corrections and invalid attempts are preserved and classified separately in `evidence/ENGINEERING_CORRECTIONS.md`. The compact durable result is `evidence/DD20_DUAL_PORTFOLIO_INTERNAL_FORMULA_LATTICE_PROXY_RESULT_V1.json`; full point, daily, freeze and advanced-analysis artifacts remain under `optimization/artifacts/raw/dd20-dual-portfolio-internal-formula-lattice-proxy-v1/`.
