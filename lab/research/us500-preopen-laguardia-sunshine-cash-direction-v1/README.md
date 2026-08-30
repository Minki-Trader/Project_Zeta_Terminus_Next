# US500 pre-open LaGuardia sunshine cash direction

Status: Unit 114 declared; target economics unopened.

This is one Program 2 / micro-to-meso Lab detour from the continuous
Optimization Goal. Hirshleifer and Shumway's 2003 *Journal of Finance* paper
defines morning weather from average 5 a.m.-through-8 a.m. local sky cover and
evaluates a transaction-cost strategy that is LONG when that average is from
zero through four inclusive and SHORT otherwise. This family transfers exactly
that sign rule from New York morning weather to same-day FPMarkets US500 regular
cash economics. It does not estimate or grid a new threshold.

Five frozen NOAA NCEI LCDv2 station/year files provide LaGuardia
`USW00014732` routine `FM-15` observations from July 2022 through July 2026.
LCDv2 `DATE` is local standard time, so each timestamp is first interpreted at
fixed UTC-05:00 and then converted to actual `America/New_York` time. One row
nearest minute 51 is selected in each actual local hour 05, 06, 07 and 08. The
maximum decoded sky condition in each row maps `CLR/SKC/NSC/NCD=0`, `FEW=2`,
`SCT=4`, `BKN=7`, and `OVC/VV/X=8`. Partial days are excluded without
imputation.

The first direct GHCNh acquisition exposed an environment gap: LaGuardia
routine FM15 rows stopped on 2026-04-13 and therefore provided zero complete
latest-period days. No price or spread field had opened. The entire provisional
weather surface was discarded and replaced, for every period, by one uniform
current NOAA LCDv2 series. This is an input-environment correction, not a
research failure or a mixed-source patch.

The outcome-free geometry contains 985 eligible official sessions. P1/P2/P3/
P4/latest have `370/247/234/91/43` days; LONG counts are
`132/80/66/25/15` and SHORT counts are `238/167/168/66/28`. P1 splits contain
`123/123/124` days. The latest weather observation precedes the 09:30 entry by
36 to 40 minutes on every eligible date. All density and causal timing gates
pass while OHLC and spread fields remain unopened.

The primary opens 0.01 lot at the exact 09:30 ET M15 open and closes at the
exact 15:45 ET M15 close representing 16:00. Gross uses midpoint direction,
observed uses direction-correct executable bid/ask, and binding stress subtracts
the full entry-plus-exit spread burden. `SUNNY_LONG_ONLY`,
`CLOUDY_SHORT_ONLY`, and `UNCONDITIONAL_LONG` are frozen diagnostics only and
cannot be promoted after outcomes.

P1, three independent confirmation periods, prelatest, latest, full-sample,
both-side, drift-control, monthly breadth, concentration, PF, net/DD and
nominal/practical `20.0%/21.2%` DD gates are frozen in `config/contract.json`.
At most one exact weather-direction information seed can survive. Every adjacent
station, hour, threshold, transform, weather field, horizon, direction, cost,
size and fixed-candidate integration rescue closes with this bundle.

No MQL, SET, compile, MT5 runtime, Strategy Tester, account query, Live source,
Live state or Optimization candidate is involved. Fixed candidate
`dd20-paired-month-stability-mt5-v1` remains unchanged. After the declaration
reaches `origin/main`, exactly one complete formal economic aggregation may
open; engineering corrections retain no arbitrary retry cap.

Marker:
`FRONTIER_UNIT_114_LAGUARDIA_MORNING_SUNSHINE_US500_CASH_DIRECTION_DECLARED_ECONOMICS_UNOPENED`.
