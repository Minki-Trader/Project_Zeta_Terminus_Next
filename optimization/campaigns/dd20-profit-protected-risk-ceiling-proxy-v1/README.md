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

## Proxy result

One process completed all `31` hard caps in `0.2861833` seconds. Every candidate was positive, `18` conservatively exceeded the qualified profit floor, and `17` kept every epoch, but **zero** passed budgeted native DD. The maximum-profit caps `$250/$260/$270` tied at actual/stressed `+$2,233.75 / +$2,144.808`; the ranked `$250` diagnostic budgeted `26.490668%` DD and failed the epoch gate.

The best cap passing both profit and epoch gates was `$200`: actual/stressed `+$2,033.62 / +$1,950.222`, conservative `+$1,983.62 / +$1,900.222`, but budgeted DD was `25.237963%`. The lowest-DD `$30` cap reached raw/budgeted `15.053137% / 20.679738%`, still missed the hard budget by `0.679738` points and retained only conservative stressed `+$453.1055`. Profit and DD regions are therefore disjoint.

This is a valid economic empty frontier, not an environment or engineering failure. The independent forward was unchanged for all candidates at `+$23.01 / +$21.256`, with positive June and July. No MT5 shortlist exists. The fixed dollar ceiling, rejected accelerator, its 256-path proxy, qualified anchor, all prior candidates and the original 15 combinations remain closed without rerun. Continue proxy-first with a distinct equity high-watermark giveback or open-profit realization mechanism.
