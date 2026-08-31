# DD20 V8 Clean Executable Microfrontier Proxy V2

V2 is the corrected Stage A of `V8-OPT-U001-PORTFOLIO-DD`. It preserves the V8-only question and temporal gates while replacing V1's invalid source-volume/base-risk rescaling with the actual V8 daily sizing and admission order.

## Exact-V8-only inputs

- Clean candidate lifecycle ledger: `1,753,587` bytes / `7C8405F487A0DE96737A22587D0EB2471029CFA337FD4C47C3E1B5E6D62C1791`.
- Clean candidate decision/admission ledger: `5,469,352` bytes / `D428D881F667F24531CB41ED85FF20575A6A771596F7091AFD62D96F57601678`.
- The `965` unique `POSITION_OPEN` rows must join one-to-one by component and server time to the `965` lifecycle BIRTH rows before any outcome is valid.

No V7, Lab, legacy Optimization or external economics selects or tunes V2.

## Correct executable model

For each replay period the actual and stressed balances start at `$100`. At each new server day, candidate `day_volume_multiplier` becomes `1 + floor(max(0, stressed_balance - 100) / 150)`. Base volume is `0.01`; component volume is `round(0.01 × day_multiplier × component_weight / 0.01) × 0.01`.

Base position risk stays exact V8 `0.04`. Candidate executable component multiplier is component volume divided by that day's normalized base volume. Position budget is conservative replay capital times `0.04` times that executable multiplier; aggregate budget is conservative capital times the candidate aggregate fraction. The clean source equity/balance ratio at the matched V8 birth can reduce but never increase replay risk capital. Actual/stressed source close net scales linearly by candidate/source volume. No source-rejected opportunity receives an invented outcome.

This accepted-path proxy cannot prove newly freed-capacity economics, altered open-equity DD, or an exact native protective-stop path when a different capital ladder changes stop quantization. Those remain native MT5 responsibilities for the sole final candidate.

## Frozen corrected Stage-A lattice

- RC61: `1.25 / 1.50 / 1.75 / 2.00`
- RC64: `0.75 / 1.00 / 1.25 / 1.50`
- Cross: `0 / 0.25 / 0.50 / 0.75 / 1.00 / 1.25 / 1.50 / 1.75 / 2.00`
- Intraday: `1.50 / 1.75 / 2.00 / 2.25 / 2.50`
- Return: `0.75 / 1.00 / 1.25 / 1.50`
- Passive: fixed `0`
- Base position risk: fixed `0.04`
- Aggregate risk: `0.12 / 0.15 / 0.18`

Exactly `8,640` parameterizations are declared. Component weights never exceed exact V8. Development remains 2024-2025, validation remains fresh `$100` 2026 January-May, and locked holdout remains fresh `$100` June-July. The primary/fallback profit-retention, DD-improvement, positivity, multi-axis-neighbor and no-holdout-substitution gates remain the same as V1.

V2 is still only Stage A. Its valid outcome cannot close the Unit. Mandatory Stage B refines weight by `0.125` and aggregate cap by `0.015` around up to three V2 basins; base-position-risk is no longer a lifecycle-proxy axis. Stage C changes future volume/effective risk causally at fixed `0.04` rather than pretending base-position-risk is a volume multiplier.

No V2 input staging, configuration, implementation or outcome begins until the declaration boundary reaches `origin/main`.
