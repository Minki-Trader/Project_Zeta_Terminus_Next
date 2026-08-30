# ADS Business Conditions Above-Normal Portfolio State V1

Status: `CLOSED_VALID_AMBIGUOUS_NO_CANDIDATE`

Frontier Unit 119 is one bounded Program 2 / meso-to-macro Lab detour from the active Optimization Goal. It asks whether the latest strictly prior real-time Philadelphia Fed Aruoba-Diebold-Scotti (ADS) business-conditions vintage being above its model-imposed zero baseline identifies a materially favorable or adverse state for the frozen six-component portfolio.

The treatment is fixed before lifecycle economics:

- use the official all-vintages workbook, not the currently revised ADS history;
- for each official vintage column, retain only its last finite daily estimate;
- a lifecycle can use only a vintage whose publication date is strictly earlier than its server date, so the new same-day release is never used;
- `ABOVE_NORMAL` is ADS `> 0`; `AT_OR_BELOW_NORMAL` is ADS `<= 0`;
- compare the two states once over all 2,233 complete immutable CP2 lifecycles after component-period centering;
- require material stressed-R and stop effects, both-book, three-of-four-period and four-of-six-component breadth, plus contribution caps.

No ADS magnitude, change, persistence, subcomponent, release type, lag, percentile, rolling transform, book, component, period, direction or threshold rescue belongs to this family. GSCPI, financial-stress, rates, event-window and other external-series substitutions are also excluded. A directional pass may retain only one nonautomatic whole-portfolio state question for a later whole-map comparison; it does not create an Optimization candidate, MT5 path or Live authority by itself.

The ignored raw official workbook archive is preserved under `lab/artifacts/raw/ads-business-conditions-above-normal-portfolio-state-v1/`. Curated source pins, the causal schedule, declaration, derived rows, result and closure live under this family. No MQL, EA, compiler, Strategy Tester, broker/account query or Live surface is used.

## Complete economic result

The one fixed aggregation reproduced all `16,477` source events, `2,233` complete lifecycles, `206` stops, actual net `+$444.19` and doubled-cost stressed net `+$407.0477`. `ABOVE_NORMAL` contains `1,100` lifecycles and actual/stressed `+$265.70 / +$246.228`; `AT_OR_BELOW_NORMAL` contains `1,133` and `+$178.49 / +$160.8197`.

The relevant per-lifecycle contrast is much smaller than the unequal raw dollar totals. Above minus at-or-below is raw `+0.0192185R / +0.009894 stop` and component-period centered `+0.0200005R / +0.0268415 stop`. Thus positive ADS combines a small favorable R difference with more stops. Both books are nonconcordant; three of four periods and five of six components are nonconcordant. P2 2024 and Return are the sole adverse cells, while no book, period or component is favorable under the joint R/stop definition.

Neither material direction gate passes. The strong-null gate also does not pass because the centered stop difference exceeds its fixed `0.025` ceiling by `0.00184145`; every other strong-null clause passes. This is therefore `AMBIGUOUS_ADS_ABOVE_NORMAL_PORTFOLIO_STATE_NO_CANDIDATE`, not a threshold-near pass, optimization failure or engineering failure. No ADS threshold relaxation, magnitude, change, persistence, transition, subcomponent, subgroup or substitute-series rescue opens.

## Closure

The declaration was committed and pushed at `13fcb9877f56873f57c54445ab7ee52efa4b9076` before the first economic read. Three source-acquisition compatibility corrections occurred before any derived schedule or portfolio economics existed; the complete economic aggregation then succeeded once with zero metric reruns. The raw official archive and all useful curated/derived evidence remain. No temporary cache, MQL, SET, compile, Tester, MT5, broker/account or Live path exists. The fixed Optimization development candidate is unchanged and Unit 119 returns to the serial whole-map boundary with no retained seed.
