# DD20 Executable Volume Lattice Proxy V1

This independent proxy searches for the highest doubled-cost-stressed selection profit inside the user's prospective `20%` MT5 equity-drawdown budget before another MT5 run is allowed.

## Why this direction

The closed `3 / 3 / 1 / 2.5 / 1 / 0` MT5 candidate confirmed explosive profit but reached `27.072835%` maximum relative equity drawdown. Its earlier close-only linear proxy estimated only `19.850887%`. This successor keeps the useful allocation information while explicitly replaying the EA's executable volume and risk-cap feedback.

## Frozen search

- All six component weights use `0 / 0.5 / 1 / 1.5 / 2 / 2.5 / 3`; at least four remain active. This yields exactly `112,752` compositions.
- Every candidate starts at `$100`. On each server day, its stressed closed balance recomputes the exact `$150` sizing ladder.
- Each birth normalizes component volume to the `0.01` lot lattice with positive `MathRound` semantics, translates that volume to executable exposure, and recomputes `0.04` position planned risk.
- Open planned risk is tracked until the source close. A source birth is skipped when the candidate would exceed the `0.18` aggregate cap.
- Accepted close economics scale by candidate normalized volume divided by the source birth volume. Actual and doubled-cost-stressed balances, drawdown and four selection epochs are accumulated in source event order.
- Full-selection proxy DD is calibrated only from the two already preserved selection MT5 anchors. The calibrated value is the maximum of raw DD and the affine two-anchor estimate, so calibration never lowers a raw proxy DD.
- Eligibility requires positive actual/stressed profit in the full selection and all four epochs, positive balances, calibrated full DD at or below `20%`, and every epoch's raw DD at or below `20%`.
- One role only is frozen from selection: maximum full stressed profit, then actual profit, recent-selection stressed profit, lower calibrated DD and deterministic lexicographic weights.
- The isolated 2026-06/07 segment is opened only after that one role freezes. It cannot rank, tune or rescue the winner. It must show positive actual/stressed profit, positive balance and raw DD at or below `20%` to nominate the sole MT5 shortlist position.

This is a substantially closer economic proxy, not MT5 proof. It cannot reconstruct parent-skipped signals, candidate-specific protective-stop exits, margin, broker rounding or the complete floating-equity path. The frozen declaration is `evidence/DD20_EXECUTABLE_VOLUME_LATTICE_PROXY_DECLARATION_V1.json`; no MT5, Live, Lab or broker state is touched during this campaign.
