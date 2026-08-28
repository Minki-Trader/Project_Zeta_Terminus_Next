# DD20 Deferred Profit Accelerator Proxy V1

This independent fast proxy addresses the economic finding that a low capital-addition step creates DD too early even when its final multiplier is capped. It keeps the first fully qualified component mix `1.6 / 0.8 / 0.4 / 3.2 / 1.2 / 0`, `0.04 / 0.18` risk admission and the exact `$150` capital-growth slope until a causal stressed closed-profit buffer exists. Only then does a faster, capped profit regime begin.

## Frozen deferred search

- Activation is based only on `max(0, stressed closed balance - $100)` available at the first source event of each server day.
- Activation-growth thresholds are `$300, $450, $600, $750, $900, $1,050, $1,200, $1,350`.
- Post-activation addition steps are `$25, $50, $75, $100`.
- Maximum day-multiplier caps are `14, 16, 18, 20, 24, 30, 40, 60`.
- The full Cartesian product contains exactly `256` new paths. Every threshold is an exact `$150` multiple, and every cap exceeds the baseline multiplier at activation. Thus the pre-activation path is exactly the qualified baseline slope and every candidate leaves executable room for the later regime.
- The multiplier is `min(cap, 1 + floor(min(growth, threshold) / 150) + floor(max(0, growth - threshold) / post-step))`.
- The closed `$150` uncapped qualified path is appended only as the 257th calibration row using an unreachable activation threshold. It is not a candidate and is not rerun in MT5.

Selection DD adds the same-composition native-minus-raw gap `2.1221507541` percentage points plus `0.25` before the hard `20%` gate. Only `50%` of incremental proxy profit over the closed `$150` proxy is credited, another `$50` is deducted, and conservative actual/stressed selection nets must strictly exceed the qualified observed `+$1,691.54 / +$1,626.26`.

The four selection epochs remain positive with positive balances and raw DD at or below `20%`. Full paired-forward DD adds `3.2281682805` points plus `0.5`; June, raw July and conservative July retain all prior gates, including the `$6.08 / $6.476` continuous-July shortfalls plus `$1`.

Exactly one role may freeze: maximum conservative stressed selection profit, then conservative actual, raw stressed, recent-selection stressed, conservative July stressed, full-pair stressed, weaker-month stressed and lower budgeted DD. An exact economic tie prefers the lower cap, later activation and larger post-activation step. The proxy may nominate at most one MT5 hypothesis.

## Result

The single proxy process exited `0` in `1.0472407` seconds and evaluated all `256` new deferred paths plus the closed calibration row. Every input, native/proxy anchor, predecessor identity and candidate-construction gate passed.

The funnel retained `206` profit-passing, `106` DD-passing, `149` all-epoch-passing and `56` combined selection paths. All `56` also passed full paired-forward, June, raw July and conservative July. Exactly one maximum-profit role froze: activation at `+$450` stressed closed profit, `$50` post-activation step and maximum multiplier `14`.

The winner's proxy actual/stressed selection net is `+$2,647.4747 / +$2,554.1534`; after the 50%-incremental credit and `$50` reserve it remains `+$2,083.5364 / +$2,006.6757`, improving the qualified observed anchor by `+$391.9964 / +$380.4157`. Raw/calibrated/budgeted DD is `17.428221% / 19.550372% / 19.800372%`, leaving `0.199628` percentage points. Every epoch is positive. Fresh June/July remain unchanged at proxy stressed `+$18.48 / +$8.756`, and conservative July stressed is `+$1.28`.

This valid proxy nominates one MT5 hypothesis but does not prove its native equity DD or realized profit. Freeze and push this result, then materialize only this deferred accelerator in one new dedicated MT5 family for one selection and one independently initialized full June/July forward. No grid, anchor, prior candidate or original 15 combinations rerun.
