# DD20 Profit-Protected Risk Ceiling Proxy V1

This proxy follows the valid MT5 rejection of the deferred accelerator without rerunning it. The fixed component weights and causal `$150 → $50 after +$450`, cap-`14` volume schedule remain unchanged. The new economic mechanism decouples aggregate admission capacity from accumulated profit by adding a fixed dollar ceiling to total planned risk.

## Why this is distinct

The rejected accelerator earned selection actual/stressed `+$2,185.39 / +$2,095.664`, but native maximum relative equity DD reached `28.087819%`. Its copied MT5 lifecycle reached `$340.666971` aggregate planned risk; the independent forward reached only `$20.79136`. The maximum DD window also contained several `$186..207` planned-risk intraday losses. A fixed aggregate dollar ceiling can therefore bind only the high-capital selection path while leaving the fresh June/July account unchanged.

This is not a nearby activation-threshold, post-step or multiplier-cap rescue. Those frozen controls do not vary. Only the new dollar-risk admission governor varies.

## Frozen proxy

- Candidate caps are exactly `$30..$330` by `$10`, or `31` new values.
- Every candidate is above the observed forward maximum aggregate planned risk and below the rejected selection maximum. The proxy must prove every cap is nonbinding across all `30` forward lifecycles and binding at least once in selection.
- At each copied accelerated-path birth, retain the position only when retained open planned risk plus its frozen planned risk is no greater than the candidate cap plus `$0.01`.
- Rejected births contribute no risk or close economics. Freed capacity does not synthesize opportunities that the original accelerated path hid; this retained-path restriction makes the proxy explicit rather than treating it as MT5 proof.
- Retained position volume, stop geometry, planned risk, exit and actual/stressed close economics remain frozen from the valid accelerator MT5 lifecycle.

## Economic gates

Selection starts from `$100`. Conservative actual and stressed net each subtract a `$50` uncertainty reserve, then must strictly exceed the qualified MT5 anchor `+$1,691.54 / +$1,626.26`. All four epochs must keep actual and stressed net positive.

The retained-path raw DD is the worse of actual and doubled-cost-stressed closed-balance relative DD. Budgeted native DD is the larger of:

- qualified native DD `19.550372%` plus `0.25` points; and
- candidate raw DD plus the rejected accelerator's observed native-minus-raw gap `5.126601` points plus `0.5` points.

Budgeted DD must remain at or below the hard `20%` limit. The sole role, if any, maximizes conservative stressed selection profit, then conservative actual profit, raw stressed profit and recent-epoch stressed profit, before preferring lower budgeted DD and a lower dollar cap.

The full forward, June and July must remain exactly `+$23.01 / +$21.256`, `+$19.79 / +$18.976` and `+$3.22 / +$2.280`; native forward DD remains the observed `12.436759%`. No MT5 may launch during this proxy and at most one role may be shortlisted afterward.

## Current boundary

Ten copied input files total `8,120,013` bytes at canonical manifest `5EB9F1D5CD25B7E915A2CEF066259C9A500B2EAE5EE449FA21472DAEB4E58D20`. Candidate economics, gate counts, ranking and output are unopened. The rejected accelerator, its 256-path proxy, the qualified anchor, every prior candidate and the original 15 combinations remain closed without rerun. No Live or Lab mutation and no broker-state query occurred.
