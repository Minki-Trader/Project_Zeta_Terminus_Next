# DD20 portfolio occupancy exposure proxy V1

Status: closed `VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE_PORTFOLIO_OCCUPANCY_EXPOSURE_PROFIT_DD_DISJOINT`.

This source-free Optimization campaign keeps the fixed paired-month weights, signals, clocks, stops, exits, source `$150` daily capital-ladder path and `0.04 / 0.18` risk contract. It changes one global causal portfolio rule only: source executable steps may be scaled differently when the candidate book is empty versus when at least one candidate-admitted position is already open.

The outcome-free structure contains `928` empty-book and `500` occupied-book source births across all four selection epochs; five active components appear in the empty state and four in the occupied state. The fixed grid is `5 × 5`: empty-book factors `1 / 1.125 / 1.25 / 1.375 / 1.5` crossed with occupied-book factors `0 / 0.25 / 0.5 / 0.75 / 1`. Factors `1 / 1` are the exact control. No component, symbol, direction, date, clock or outcome subgroup enters the rule.

Only the `24` noncontrol selection paths are eligible. Conservative profit subtracts the worst prior observed adverse proxy overstatement plus a new `$25`; DD adds a new `0.25`-point mechanism reserve and uses the established pragmatic `21.2%` proxy ceiling while still reporting the nominal `20%` line. A deterministic maximum-profit selection winner alone may open the untouched June/July input. At most one MT5 shortlist can result.

The campaign owns one-time copies of the paired-month selection and forward lifecycle ledgers under its ignored raw input root. It executes no other campaign, Lab or Live path and has no Live authority.

## Result

Two pre-result invocations stopped before any complete candidate metric: one used the intentionally zero CLOSE-row volume, and one tried to reconstruct an MT5 capital-ladder boundary from lifecycle close totals that do not retain transaction-level settlement precision. Both were corrected as engineering/design states. One complete valid process then evaluated all `25` selection paths in `0.205494` internal seconds with exact control reproduction and no economic rerun.

The control's `928` empty-book births earned `+$3,405.42 / +$3,197.325`; its `500` occupied-book births also earned a strong `+$2,381.21 / +$2,280.199`. Mildly suppressing occupied births to `0.75` lost `-$614.6612 / -$588.1027` and worsened budgeted DD to `24.2293%`, so stacked exposure is not an identified harmful class.

Eight paths conservatively beat both profit anchors, but every one of the `24` noncontrols failed DD. The nearest complete path, empty `1.125` / occupied `1`, earned `+$6,158.027 / +$5,827.319`; even after the full frozen uncertainty charges it remained `+$90.717 / +$90.581` above the anchor. Its raw DD rose to `22.362710%` and budgeted DD to `22.468569%`, however—`1.268569` points beyond the already pragmatic `21.2%` screen. The maximum-profit `1.5 / 1` path reached `+$7,403.677 / +$6,996.597` but budgeted DD `27.106077%`.

The selection funnel is modified-decision `24/24`, 80%-admission `19/24`, positive capital `24/24`, four positive epochs `20/24`, conservative actual/stressed profit `8/24`, and DD `0/24`. The complete intersection is empty. Candidate forward outcomes therefore remained unopened, no MT5 shortlist exists, and the whole occupancy neighborhood closes without a factor or subgroup rescue. The paired-month anchor and its fixed Lab development candidate remain unchanged.
