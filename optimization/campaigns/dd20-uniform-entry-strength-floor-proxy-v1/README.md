# DD20 Uniform Entry-Strength Floor Proxy V1

This source-free Optimization campaign tests one bounded parameter axis on the current qualified paired-month anchor: multiply every active component's already-existing entry threshold by the same factor while preserving direction, signal formula, exits, weights, risk, order type and all portfolio rules.

## Whole-map role

The capital, aggregate-risk, executable-volume, static-composition, profit-realization, drawdown-governor, component-equity-state, gain-reserve, US500 H4 and frequency-lane families are closed. This family does not retune any of them and does not use the three-row Live post-forward result to choose a component. It applies one blind global multiplier to the five positive-exposure components, with no component-specific value and no threshold loosening.

This is direct optimization of existing hard-coded thresholds, not a new predictor or explanatory research hypothesis, so no Lab detour opens. The current anchor's selection and forward lifecycle ledgers are copied once into this campaign's ignored raw input root and hash-pinned. The proxy reads only that snapshot.

## Frozen proxy contract

- Global multipliers: `1.00, 1.05, 1.10, 1.15, 1.20, 1.30, 1.50`.
- Native thresholds: RC16 `feature >= 1.5`; RC4 `|feature| >= 1.5`; Cross and Pressure `|feature| >= 0.5`; Return `feature <= -0.5`.
- The candidate proxy may only remove an already accepted native lifecycle whose normalized entry strength is below the global floor. It does not synthesize newly admitted trades, rescale retained trades, or claim native floating-equity behavior.
- Selection ranking is fixed before outcomes. A candidate must improve both actual and stressed selection net over the anchor, keep all four selection epochs positive, preserve all five active components, remain balance-positive, and have calibrated closed-balance DD no worse than the anchor and below the fixed pragmatic `21.2%` line.
- The maximum-selection-stressed-profit eligible factor is the only factor allowed to open the full June and July snapshot. Both months must independently remain actual/stressed positive, balance-positive and below `21.2%` raw closed-balance DD.
- At most one separate MT5 shortlist may survive. Proxy output cannot establish native profit or native equity DD.

No MQL, SET, compile, terminal, Tester, Live, Master, Lab or broker/account operation belongs to this proxy campaign.

## Result

The sole formal proxy process completed in `0.0789036` seconds and reproduced the anchor's `1,428` selection closes at actual/stressed `+$5,786.63 / +$5,477.524`. Its conservative closed-balance DD is `20.4010291664%`; because this is already slightly above the native `20.2568875652%`, calibration never reduces it.

No stronger factor passed selection. The economically best noncontrol factor, `1.05`, removed `84` closes and fell to `+$4,842.47 / +$4,555.237` while DD rose to `25.4226851397%`. The lowest-DD noncontrol factor was `1.20`, but even it reached `24.2785491901%` while profit fell to `+$3,822.97 / +$3,579.443`. All six stronger factors lost both actual and stressed profit and exceeded the anchor DD and pragmatic `21.2%` line; `1.50` also made E2 stressed net negative.

Status is `VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE_UNIFORM_FLOOR_DEGRADES_PROFIT_AND_DRAWDOWN`. With zero selection-eligible factors, June and July stayed unopened, no MT5 shortlist exists, and the paired-month anchor remains unchanged. This global-floor family is frozen without any component, direction, period, subgroup or nearby-threshold rescue.
