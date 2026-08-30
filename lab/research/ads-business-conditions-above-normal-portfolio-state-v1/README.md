# ADS Business Conditions Above-Normal Portfolio State V1

Status: `OPEN_OUTCOMES_UNREAD`

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
