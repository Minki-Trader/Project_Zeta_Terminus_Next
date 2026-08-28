# DD20 Chronological Stability Proxy V1

This independent proxy keeps the user's maximum-profit objective but adds a chronological stability requirement before another MT5 run is allowed.

## Why this direction

The prior executable-lattice proxy found a selection winner with stressed profit `+$6,588.5518` at `19.278821%` DD, but it lost `-$12.808` at `28.019366%` DD in the untouched June/July segment. US100-cross alone contributed `-$37.278` there. A second selection-only maximum would repeat the same instability, so this campaign deliberately converts June 2026 into a small development checkpoint while preserving July 2026 as an untouched final confirmation.

## Frozen search

- The campaign owns fresh copies of the parent lifecycle/report and the two selection MT5 calibration anchors. It imports or links no source or mutable output from another campaign.
- All six weights again use `0 / 0.5 / 1 / 1.5 / 2 / 2.5 / 3`, with at least four active: exactly `112,752` compositions.
- The corrected event-driven model replays the `0.01` lot lattice, `$150` stressed-balance sizing ladder, impulse reservation volume, `0.04` position risk and `0.18` tracked aggregate admission.
- Long selection still requires positive actual/stressed full and four-epoch results, positive balances, full upward-only calibrated DD at or below `20%`, and every epoch raw DD at or below `20%`.
- Only selection-eligible candidates enter June 2026 development. June starts independently at `$100` and must have positive actual/stressed net, positive balance and raw DD at or below `20%`.
- One role then freezes: maximize full selection stressed net, followed by June stressed net, selection actual, June actual, recent-selection stressed net, lower calibrated DD and deterministic lexicographic weights.
- July 2026 contains exactly `43` births and closes, has no position crossing its month boundary, starts independently at `$100`, and remains unopened until the winner freezes. It cannot rank, tune or rescue the winner. Positive actual/stressed net, positive balance and raw DD at or below `20%` are required for the sole possible MT5 shortlist position.

The proxy still preserves source exits and cannot model candidate-specific signal recovery, stop-path changes, complete floating equity, margin or broker execution. It is a fast economic screen, not MT5 proof, and it never reruns the original 15 combinations.
