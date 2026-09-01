# Independent Multi-Asset H4 Donchian Trend Adapter Challenge V1

This is Independent V8 Challenge Family 009. The user authorized autonomous method selection; Program 1 / macro is attached only as the policy-required administrative tag after selection and did not constrain the design.

The candidate is a direct seven-market trend portfolio over AUDUSD, EURUSD, GBPUSD, NZDUSD, US100, US30 and US500. Python owns original-broker H4/specification integrity, broker-wall-clock normalization, causal Donchian/ATR state, simultaneous-entry priority, portfolio risk reservations and the immutable decision tape. A later family-owned EA may only validate and execute those decisions, own orders/protection/channel and timed exits, persistence/recovery and bounded evidence. A standalone EA or Python-only proxy cannot win the Challenge.

Two related horizons are frozen before data: MULTI_ASSET_DONCHIAN_120_60 and MULTI_ASSET_DONCHIAN_240_120. Both use strict completed-close breakouts, ATR20, a fixed two-ATR hard stop, at most 480 held H4 bars, 4% position risk, a 6% minimum-lot hard cap and an 18% aggregate initial-stop-risk cap. Direction-specific Bid/Ask, one extra observed-spread stress charge and pinned broker swap economics are mandatory.

Both horizons and a same-process improvement audit must complete before closure. The audit covers raw 1/3/6/12-H4 paths, MFE/MAE, horizon overlap and unique starts, year/symbol/asset-class/direction stability, observed/doubled spread plus swap burden, risk blocks and stop/channel/max-hold attribution. It may retain one bounded seed but cannot execute an undeclared rescue.

Development is 2024-2025 after source warmup from 2022. Locked 2026 January-July remains unacquired and unopened for at most one unchanged complete development passer. The authoritative contract is `config/challenge-contract.json`.

The build-6140 platform may populate currently selected default-symbol cache while establishing an original-broker session even when no rates API is called. Such bootstrap files are not candidate sources: they are purged before acquisition, every persisted CSV is bounded from raw timestamps by the declared development request, and any transient `2026.hcc` is purged again after the stopped acquisition before evidence. The adapter never reads a runtime history cache. Fresh specifications identified `CURRENCY_SYMBOL` swap for all three indices; because their base and deposit currencies are both USD, the official base-currency money amount converts one-for-one and is now frozen as signed rate times volume times rollover multiplier.

Status: complete fresh 2022-2025 original-broker H4/specification source is frozen with the CURRENCY_SYMBOL swap correction; channel/ATR construction, adapter implementation, lifecycle simulation, improvement values and outcomes remain zero.
