# Independent Multi-Asset H4 Donchian Trend Adapter Challenge V1

This is Independent V8 Challenge Family 009. The user authorized autonomous method selection; Program 1 / macro is attached only as the policy-required administrative tag after selection and did not constrain the design.

The candidate is a direct seven-market trend portfolio over AUDUSD, EURUSD, GBPUSD, NZDUSD, US100, US30 and US500. Python owns original-broker H4/specification integrity, broker-wall-clock normalization, causal Donchian/ATR state, simultaneous-entry priority, portfolio risk reservations and the immutable decision tape. A later family-owned EA may only validate and execute those decisions, own orders/protection/channel and timed exits, persistence/recovery and bounded evidence. A standalone EA or Python-only proxy cannot win the Challenge.

Two related horizons are frozen before data: MULTI_ASSET_DONCHIAN_120_60 and MULTI_ASSET_DONCHIAN_240_120. Both use strict completed-close breakouts, ATR20, a fixed two-ATR hard stop, at most 480 held H4 bars, 4% position risk, a 6% minimum-lot hard cap and an 18% aggregate initial-stop-risk cap. Direction-specific Bid/Ask, one extra observed-spread stress charge and pinned broker swap economics are mandatory.

Both horizons and a same-process improvement audit must complete before closure. The audit covers raw 1/3/6/12-H4 paths, MFE/MAE, horizon overlap and unique starts, year/symbol/asset-class/direction stability, observed/doubled spread plus swap burden, risk blocks and stop/channel/max-hold attribution. It may retain one bounded seed but cannot execute an undeclared rescue.

Development is 2024-2025 after source warmup from 2022. Locked 2026 January-July remains unacquired and unopened for at most one unchanged complete development passer. The authoritative contract is `config/challenge-contract.json`.

The build-6140 platform may populate currently selected default-symbol cache while establishing an original-broker session even when no rates API is called. Such bootstrap files are not candidate sources: they are purged before acquisition, every persisted CSV is bounded from raw timestamps by the declared development request, and any transient `2026.hcc` is purged again after the stopped acquisition before evidence. The adapter never reads a runtime history cache. Fresh specifications identified `CURRENCY_SYMBOL` swap for all three indices; because their base and deposit currencies are both USD, the official base-currency money amount converts one-for-one and is now frozen as signed rate times volume times rollover multiplier.

Every judged entry must have its entry bar plus 479 later observed same-symbol H4 bars inside that same judged period. This timestamp-only maturation rule prevents an undeclared period-end liquidation and prevents 2026 rows from resolving a 2025 entry; it is applied before signals or outcomes and also defines the active-date denominator.

The complete family-owned adapter now freezes authority-gated `precheck / development / confirmation`, causal channels and ATR, the exact cross-symbol event sequence, balance-compounded risk reservations, Bid/Ask and signed-swap economics, complete-period maturation, the same-process path audit, no-overwrite output and conditional locked/native escalation. Its candidate-local outcome-free precheck found `920 / 684` medium/slow signals over `530` active dates and evaluated zero future exit path, lifecycle, economic metric or improvement value.

Status: implementation is frozen predevelopment-outcome. Development economics, audit paths, locked 2026, EA source, compile and MT5 Tester remain zero until the implementation-freeze boundary reaches `origin/main`.
