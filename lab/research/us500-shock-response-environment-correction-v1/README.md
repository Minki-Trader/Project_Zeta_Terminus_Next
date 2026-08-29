# US500 shock-response environment correction V1

Status: closed `FAIL_US500_SHOCK_RESPONSE_NO_DIRECTION_NO_SEED`, one valid
bar-open/spread proxy aggregation. Frontier Unit 105 under Program 1
`signal_market_structure` at meso to micro height.

Unit027 asked whether a completed-M15 volatility-normalized 60-minute US500
shock produces a frequent and cost-positive four-market-bar continuation or
reversion response. It never reached an economic judgment. Both stable P1
observer paths produced 1,264 rows with zero observer faults, but each path was
invalidated because its environment contract bound unrelated future and
current monthly tick files to the old P1 period. A mutable 2026-08 tick file
therefore invalidated a 2022-08 through 2023-12 result.

Unit105 is an environment and design correction, not a new adjacent research
hypothesis. It keeps the exact score `2.0`, rearm `1.0`, four-bar impulse,
32-return sample-volatility baseline, four-market-bar horizon, non-overlap,
fixed `0.01` observation volume, four periods, continuation/reversion books,
additional entry-and-exit spread stress and economic selection gates. It opens
no threshold, window, subgroup, symbol, session, stop, size or portfolio
variant.

Before declaration, only six non-economic structural columns were copied once
from the byte-identical invalid parent output: trigger time, resolution time,
bars held, score, signed impulse and sign. Entry, exit, spread and profit fields
were not copied or used. The invalid Unit027 economics remain excluded.

One minimal physical Portable was copied from the neutral Lab runtime. Through
MetaTrader5 Python `5.0.5640`, one acquisition called only `initialize`,
`symbol_select`, `symbol_info`, one US500 M15 `copy_rates_range` and `shutdown`.
It queried no account, position, order, deal, margin or trading state. The
family-owned immutable surface contains `97,707` bars from
`2022.07.01 01:00:00` through `2026.08.21 23:45:00`; visible US500 economics
are digits/point/tick size/tick value/contract size/minimum volume/step
`2 / 0.01 / 0.01 / 0.01 / 1.0 / 0.01 / 0.01`.

The proxy uses each M15 open as bid, adds the acquired bar spread for ask and
applies the original extra trigger and resolution spread stress. Profit is
signed tick distance times tick value and fixed volume. This is a proxy, not
real-tick fill evidence, promotion evidence or a deployable rule.

## Integrity

The first protected invocation stopped before economics because the initial
parity gate incorrectly demanded exact real-tick seconds even though the
declared proxy records bar-open timestamps. The parent had `54` nonzero trigger
seconds and `74` nonzero resolution seconds, up to `37` and `13` seconds. This
was corrected before any Unit105 economic value was calculated.

The corrected premetric pass reproduced every parent aggregate: P1 has `366`
normal days, `33,453` evaluations, `1,264` triggers and resolutions, zero
unresolved and zero rate/tick/profit faults. All `1,264` trigger and resolution
M15 coordinates, four-bar horizons and impulse signs match. Maximum score and
signed-impulse differences are only `4.996e-13` and `4.999e-13`, inside their
frozen tolerances. Exact tick timestamps are retained only descriptively
(`1,147/1,264` whole-row identities).

The later paths also completed structurally without faults:

- P2 2024: `259` normal days, `23,675` evaluations, `877` resolutions.
- P3 2025: `258` normal days, `23,502` evaluations, `816` resolutions.
- P4 2026 YTD: `166` normal days, `15,161` evaluations, `489` resolutions.

The pooled frequency gate passes strongly: `3,446` opportunities over `1,049`
normal days, or `3.285033` per day; all four periods exceed `0.25` per day.

## Economic result

Continuation proxy economics at fixed `0.01` volume were:

- Observed pooled net `-$16.7491`, PF `0.901327`, maximum closed drawdown
  `$17.7718`.
- Double-spread pooled net `-$46.7692`, PF `0.749145`, maximum closed drawdown
  `$47.6413`, net/DD `-0.981694`.
- Double-spread period nets P1/P2/P3/P4 were
  `-$18.3765 / -$8.5191 / -$14.3713 / -$5.5023`; positive periods `0/4`.

Reversion proxy economics were:

- Observed pooled net `-$13.2710`, PF `0.920866`, maximum closed drawdown
  `$21.2285`.
- Double-spread pooled net `-$43.2911`, PF `0.764673`, maximum closed drawdown
  `$48.1220`, net/DD `-0.899611`.
- Double-spread period nets P1/P2/P3/P4 were
  `-$19.3389 / -$14.6847 / -$7.4348 / -$1.8327`; positive periods `0/4`.

Both directions pass every frequency requirement but pass `0/5` economic
requirements. This is not a marginal nominal miss: both pooled books are
negative even before the extra spread, remain negative after stress in every
period, have PF well below `1.0`, and have no positive path from which a
distributed profit could arise.

The fixed question therefore closes with complete valid economic
nonconfirmation. There is no retained seed, MT5 clue, Strategy Tester path,
Optimization candidate, MQL change or Live authority. Score, rearm, impulse,
baseline, horizon, session, direction subgroup, spread stress, symbol, period,
stop, size and portfolio rescues close together.

The useful ignored raw bundle is preserved: the 97,707-bar surface, symbol
specification, six-field structural anchor and 3,446-row opportunity output
total `7,853,422` bytes. The reproducible dedicated runtime was kept
cloud-recoverable and marked OneDrive online-only after acquisition. One exact
dedicated-path terminal appeared again during closeout and was stopped by that
path alone; no other process was touched and no useful artifact was deleted.
Master and Live were never started or queried.
