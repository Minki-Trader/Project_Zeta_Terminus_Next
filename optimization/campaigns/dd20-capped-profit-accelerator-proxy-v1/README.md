# DD20 Capped Profit Accelerator Proxy V1

This independent fast proxy keeps the first fully qualified component mix `1.6 / 0.8 / 0.4 / 3.2 / 1.2 / 0`, the `0.04 / 0.18` risk contract and the stressed-balance capital ladder. It introduces one economically distinct control: a hard maximum on the day multiplier. The purpose is to retain the early compounding of low addition steps while preventing the uncapped path from expanding to the extreme exposure that produced the closed `$50` ladder's `48.924974%` budgeted DD.

## Frozen accelerator search

- Addition steps are the 18 closed profit-region values `$50..$135` by `$5`.
- Maximum day-multiplier caps are `12, 13, 14, 15, 16, 18, 20, 24, 30, 40, 60`.
- A pair is admitted only when its cap is strictly below that step's already observed uncapped maximum multiplier. This leaves exactly `168` new paths and guarantees the cap binds; no closed constant-ladder path is rerun.
- The day multiplier is `min(cap, 1 + floor(max(0, stressed closed balance - $100) / addition step))`, frozen on the first source event of each server day.
- The closed `$150` uncapped qualified path is appended only as the 169th calibration row. It is not a candidate and is not rerun in MT5.

Selection DD adds the same-composition native-minus-raw gap `2.1221507541` percentage points plus `0.25` points before the hard `20%` gate. Candidate incremental proxy profit receives only `50%` credit relative to the closed `$150` proxy result and then loses another `$50`; conservative actual and stressed selection nets must strictly exceed the observed qualified MT5 result `+$1,691.54 / +$1,626.26`.

Full paired-forward DD adds `3.2281682805` points plus `0.5`. Independent July subtracts the same-composition proxy-to-continuous shortfalls `$6.08 / $6.476` plus `$1`. Full selection and all four epochs, the full June/July pair, June, raw July and conservative July retain their positive balance, positive net and DD gates.

Exactly one role may freeze: maximum conservative stressed selection profit, then conservative actual, raw stressed, recent-selection stressed, conservative July stressed, full-pair stressed, weaker-month stressed and lower budgeted DD; an exact economic tie prefers the lower cap and then the larger addition step. The proxy records individual gate counts and top diagnostics and may nominate at most one MT5 hypothesis.

## Current boundary

The independent input is eight copied files totaling `21,289,416` bytes, including the closed constant-ladder result used only to prove every new cap binds. Candidate selection, paired-forward, June, July, ranking and shortlist economics are unopened. Commit and push this declaration before the single proxy invocation. No MT5, Live, Lab, broker-state query, prior candidate or original-15 rerun is authorized.
