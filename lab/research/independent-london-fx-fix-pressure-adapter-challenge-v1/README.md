# Independent London FX Fix Pressure Adapter Challenge V1

This is Independent V8 Challenge Family 010. The method was selected autonomously from independence, causal clarity, source constructibility, USD 100 minimum-lot plausibility, repeated opportunity supply and cost-survival plausibility. Program 3 / micro-to-meso is an administrative tag applied only after selection.

The candidate trades AUDUSD, EURUSD, GBPUSD and NZDUSD directly around the institutional London 16:00 FX benchmark. Python owns fresh M1/specification integrity, broker-wall-clock normalization, Europe/London event geometry, ATR and direction decisions, portfolio sequence and the immutable decision tape. A later family-owned multi-symbol EA may only validate and execute those decisions, size from broker/account state, own hard protection and timed exits, reconcile orders, persist/recover state and emit bounded native evidence. A standalone EA or Python-only proxy cannot win the Challenge.

One related bundle is frozen. `LONDON_FIX_PRE_FLOW_CONTINUATION` uses the completed 15:45..15:54 London Bid move, enters in its direction at 15:55 and exits at 16:05 after traversing the current five-minute fixing window. `LONDON_FIX_POST_PRESSURE_REVERSAL` uses the completed 15:55..16:04 move, enters opposite at 16:05 and exits at 16:30. Both use a fixed hard stop at the greater of five causal ATR20 or four entry spreads, with adverse-first H1-minute bar handling and no take profit.

Each symbol targets 1.5% of the same actual-balance snapshot, permits a minimum lot only within a 3% hard cap, and shares an 8% aggregate original-stop-risk cap. Actual economics use direction-specific Bid/Ask, signed broker swap if any boundary is crossed, and zero unrecorded commission; stress subtracts the observed direction-specific lifecycle spread burden once more.

Development is 2024-2025 after warmup from 2023. Locked 2026 January-July remains unacquired and unopened for at most one unchanged complete development passer. Both variants and one same-process improvement audit must complete before closure. The audit covers every complete signal at 1/5/10/20/25/30 held M1 bars, MFE/MAE, pair/year/direction stability, ordinary versus month/quarter-end dates, costs, risk blocks and stop/time truncation. It may retain one bounded seed but cannot execute a nearby clock, window, threshold, pair, direction, stop, hold, risk or sizing rescue.

Primary mechanism evidence is Ito-Yamada's post-reform London-fix study, Melvin-Prins on benchmark-linked equity hedging pressure, and the Bank of England's March 2025 FXJSC minutes reporting continuing widespread Fix use and increased flow. None validates this broker, exact bars, direction, costs, risk or V8 gates.

Status: declared preruntime, preacquisition, prefeature, predecision and preoutcome. The authoritative contract is `config/challenge-contract.json`.
