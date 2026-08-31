# DD20 V8 Clean Executable Microfrontier Proxy V2

V2 is the corrected Stage A of `V8-OPT-U001-PORTFOLIO-DD`. It preserves the V8-only question and temporal gates while replacing V1's invalid source-volume/base-risk rescaling with the actual V8 daily sizing and admission order.

## Exact-V8-only inputs

- Clean candidate lifecycle ledger: `1,753,587` bytes / `7C8405F487A0DE96737A22587D0EB2471029CFA337FD4C47C3E1B5E6D62C1791`.
- Clean candidate decision/admission ledger: `5,469,352` bytes / `D428D881F667F24531CB41ED85FF20575A6A771596F7091AFD62D96F57601678`.
- The `965` unique `POSITION_OPEN` rows must join one-to-one by component and server time to the `965` lifecycle BIRTH rows before any outcome is valid.

No V7, Lab, legacy Optimization or external economics selects or tunes V2.

## Correct executable model

For each replay period the actual and stressed balances start at `$100`. At each new server day, candidate `day_volume_multiplier` becomes `1 + floor(max(0, stressed_balance - 100) / 150)`. Base volume is `0.01`; component volume is `round(0.01 × day_multiplier × component_weight / 0.01) × 0.01`.

Base position risk stays exact V8 `0.04`. Candidate executable component multiplier is component volume divided by that day's normalized base volume. Position budget is conservative replay capital times `0.04` times that executable multiplier; aggregate budget is conservative capital times the candidate aggregate fraction. The clean pre-order source `risk_capital/account_balance` ratio at the matched V8 birth can reduce but never increase replay risk capital. This avoids using the post-open equity already reduced by the new trade's spread. Actual/stressed source close net scales linearly by candidate/source volume. No source-rejected opportunity receives an invented outcome.

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

## Final Stage-A result

The exact anchor reproduced all `965` births, volumes, pre-order risk-capital contexts and position caps, actual/stressed `+$409.81 / +$367.818`, actual closed-balance DD `35.46%`, and zero source-path aggregate skips. The frozen `8,640`-point map produced `1,344` primary-eligible points and a `1,340`-point development plateau.

The selected center is `1.25 / 1.5 / 2 / 2.25 / 1.25 / 0`, position risk `0.04`, aggregate cap `0.12`. Its whole accepted-source replay is actual/stressed `+$351.7647 / +$322.3487`, actual/stressed-counterfactual closed-balance DD `24.0998% / 25.3032%`, with fresh validation `+$76.214 / +$70.9607` and locked holdout `+$23.3743 / +$21.5323`. Two other ranked centers are economically identical because the V8 lot step quantizes their declared parameter differences.

Final status is `VALID_PROXY_COMPLETE_STAGE_A_SURVIVOR_STAGE_B_REQUIRED_NO_MT5`. This is a broad executable basin, not a unique optimum or native MT5 shortlist. Mandatory Stage B refines weights by `0.125` and aggregate cap by `0.015` around all three frozen centers; Stage C changes future volume/effective risk causally at fixed `0.04`. No MT5, Lab, new-entry or Live change occurred.
