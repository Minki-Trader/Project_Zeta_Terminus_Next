# DD20 Capital Addition Ladder Proxy V1

This independent fast proxy keeps the first fully qualified component mix `1.6 / 0.8 / 0.4 / 3.2 / 1.2 / 0` and changes only the stressed-balance profit-compounding ladder. The existing `$150` step is a closed calibration anchor, not a candidate. Smaller steps can add executable `0.01`-lot units earlier after realized profit without increasing the fresh-account starting size.

## Frozen ladder search

- Candidate addition steps are `$50..$145` and `$155..$300`, each by `$5`: exactly `50` new values. `$150` is excluded and appended only as the closed anchor, yielding `51` evaluation rows.
- On the first source event of each server day, the multiplier remains `1 + floor(max(0, stressed closed balance - $100) / candidate step)`. Component weights, positive MathRound volume normalization, passive reservation basis, `0.04` position risk and `0.18` aggregate admission are unchanged.
- Selection DD adds the same-composition observed native-minus-raw gap `2.1221507541` percentage points plus `0.25` points before the hard `20%` gate.
- Candidate incremental proxy profit receives only `50%` credit relative to the closed `$150` proxy result, then loses another `$50`. Both conservative actual and stressed selection nets must strictly exceed the observed qualified MT5 result `+$1,691.54 / +$1,626.26`.
- Full June/July DD adds the same-composition observed gap `3.2281682805` points plus `0.5`. Independent July subtracts the same-composition proxy-to-continuous shortfalls `$6.08 / $6.476` plus `$1`.
- Full selection and every epoch, full pair, June and raw/conservative July remain actual/stressed positive with positive balances and their DD gates.
- Exactly one role may freeze: maximum conservative stressed selection profit, then conservative actual, raw stressed, recent-selection stressed, conservative July stressed, full-pair stressed and lower budgeted DD.

The proxy predeclares individual selection-gate counts and top economic diagnostics even if the conjunction is empty. Its independent input is seven files totaling `20,922,675` bytes, containing only the parent lifecycle/reports and qualified-anchor lifecycle/native-cache facts. No closed candidate, static grid or original 15 combinations rerun, and the proxy launches no MT5. A valid result may nominate at most one new ladder hypothesis.

## Current boundary

All candidate selection, paired-forward, June, July, ranking and shortlist economics are unopened. Commit and push this declaration before the single proxy invocation.
