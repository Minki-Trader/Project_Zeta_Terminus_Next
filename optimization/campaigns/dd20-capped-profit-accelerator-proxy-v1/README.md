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

## Result

The single proxy process exited `0` in `1.0329898` seconds and evaluated all `168` new binding-cap paths plus the closed calibration row. Every lifecycle/native/proxy anchor and the closed-path construction gate passed.

All `168` candidates were positive and conservatively exceeded the qualified MT5 profit floor. However, `0` passed budgeted DD and `0` passed every epoch, so the selection conjunction and all conditional forward/month counts are zero. There is no MT5 shortlist.

The maximum-profit diagnostic was step `$50`, cap `60`: proxy actual/stressed `+$13,015.3142 / +$12,517.3760`, conservative `+$7,267.4562 / +$6,988.2869`, but budgeted DD remained `48.924974%`. A hard terminal cap therefore preserves much of the explosive profit but does not fix the earlier low-step exposure ramp that creates the DD and epoch failures.

This is a valid economic empty frontier. The qualified MT5 result remains the active success anchor. This capped grid, the constant ladder, all MT5 anchors and the original 15 combinations remain closed without rerun. The next distinct proxy will delay acceleration until a stressed closed-profit buffer has accumulated, retain the `$150` baseline slope before that point, and cap only the later accelerated regime.
