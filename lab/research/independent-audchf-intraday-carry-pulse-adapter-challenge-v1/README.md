# Independent AUDCHF Intraday Carry Pulse Adapter Challenge V1

This is Independent V8 Challenge Family 007, allocated to Program 2 (`external_market_event`) at micro-to-meso height. It asks whether a completed broker-native AUDCHF half-hour carry-risk impulse transfers into, or mean-reverts against, the next US100 and US30 half hour strongly and frequently enough to beat V8.

The mandatory architecture is `Python adapter + EA`:

- Python owns New York local-time scheduling, fresh AUDCHF source validation, the causal same-slot 60-session rank reference, the frozen `AUDCHF_PULSE_FOLLOW / AUDCHF_PULSE_FADE` decision and immutable sequence/freshness evidence.
- The EA must validate the adapter contract, size and submit both target lifecycles, own symbol/risk checks, protection, timed close, aggregate exposure, persistence/restart recovery and bounded execution evidence.
- A single-EA signal, Python-only proxy or a reused closed-family output cannot claim a V8 Challenge victory.

Family 001-006 outputs and V1-V8 signals, opportunities, states and economics are excluded. Development is 2024-2025; locked 2026 January-July can open for at most one unchanged complete role. The authoritative frozen contract is `config/challenge-contract.json`.

Status: the dedicated Portable now uses a one-time project-local original-broker account/server support copy from a stopped non-Master Lab donor. The prior 15,144-byte Default/demo AUDCHF placeholder was deleted. Fresh development authority contains 930,039 AUDCHF M1 rows through 2025-12-31, and the complete adapter passed its outcome-free structural/risk precheck and is frozen before development economics. Locked 2026, candidate lifecycles/economics, EA and native MT5 remain unopened.
