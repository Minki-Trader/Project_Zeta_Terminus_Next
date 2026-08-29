# DD20 Protective Stop Headroom Proxy V1

This source-free Optimization campaign changes one existing global risk input on the qualified paired-month anchor: `InpStopPlacementHeadroomFraction`. Volume, the `4% / 18%` position/aggregate risk contract, the `0.25` unmodelled-risk reserve, component weights, signals, exits and every other portfolio rule remain fixed.

## Whole-map role

The prior uniform entry-strength family is closed with no candidate. Capital, volume, static composition, profit-side exits, drawdown governors, component state, gain reserve, peer exits, US500 H4 and frequency lanes also remain frozen. This family is the first bounded loss-side protective-geometry axis. It is direct optimization of an existing input, not a new predictor or explanatory research hypothesis, so no Lab detour opens.

## Frozen proxy contract

- Headroom grid: `0.25, 0.30, 0.35, 0.40, 0.45, 0.50`.
- `InpUnmodelledRiskReserveFraction` stays `0.25`; candidate gross stop-risk fractions are therefore `0.50, 0.45, 0.40, 0.35, 0.30, 0.25` of the unchanged planned-risk budget.
- The exact anchor lifecycle snapshots supply planned risk, trough marked R, trough time and native actual/stressed close economics.
- When a candidate's tighter stop lies inside the observed trough, the fixed-path proxy books actual net at the candidate gross-risk fraction and carries the observed extra-cost stress penalty. Otherwise it preserves the native close net. It never changes volume or synthesizes later admissions.
- First threshold-crossing time is not observed. Each factor is therefore judged under two related bounds: book a hypothetical stop at the observed trough timestamp, and book it at the original native close timestamp. Selection and holdout must pass both.
- A candidate must improve anchor actual and stressed selection profit, keep all four epochs and all five components positive/present under both timing bounds, remain balance-positive, and keep conservative calibrated DD no worse than the native anchor and below the pragmatic `21.2%` line.
- The maximum stressed-profit eligible factor alone may open the June and July snapshots. Both months and both timing bounds must independently pass positive actual/stressed net, positive balance and the DD line.
- At most one separate MT5 shortlist may survive. The proxy cannot establish native stop fills, minimum-distance feasibility, profit or floating-equity DD.

No MQL, SET, compile, terminal, Tester, Live, Master, Lab or broker/account operation belongs to this proxy campaign.

## Result

The sole formal proxy process completed normally in `0.102509` seconds and reproduced all `1,428` anchor closes at actual/stressed `+$5,786.63 / +$5,477.524`. The control conservative closed-balance DD is `20.4010291664%`; calibration never reduces that raw value.

No tighter headroom passed selection under either timing bound. The smallest move, headroom `0.30` and gross stop-risk fraction `0.45`, converted `142` lifecycles into hypothetical protective stops. Actual/stressed net fell to `+$5,065.455772 / +$4,756.349772`, down `$721.174228 / $721.174228`, while DD rose to `23.1906669156%`. Larger headrooms produced `187..425` hypothetical stops, lower profit and DD up to `36.6057471411%`. All four epochs remained positive, but every noncontrol candidate failed both mandatory profit gates and both DD gates.

Status is `VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE_TIGHTER_PROTECTIVE_STOPS_DEGRADE_PROFIT_AND_DRAWDOWN`. With zero selection-eligible factors, June and July remained unopened, no MT5 shortlist exists, and the paired-month anchor remains unchanged. This protective-headroom family is frozen without a component, symbol, direction, epoch, reserve, risk, volume or nearby-headroom rescue.
