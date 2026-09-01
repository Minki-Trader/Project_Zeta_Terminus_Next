# Independent AUDCHF Intraday Carry Pulse Adapter Challenge V1

This is Independent V8 Challenge Family 007, allocated to Program 2 (`external_market_event`) at micro-to-meso height. It asks whether a completed broker-native AUDCHF half-hour carry-risk impulse transfers into, or mean-reverts against, the next US100 and US30 half hour strongly and frequently enough to beat V8.

The mandatory architecture is `Python adapter + EA`:

- Python owns New York local-time scheduling, fresh AUDCHF source validation, the causal same-slot 60-session rank reference, the frozen `AUDCHF_PULSE_FOLLOW / AUDCHF_PULSE_FADE` decision and immutable sequence/freshness evidence.
- The EA must validate the adapter contract, size and submit both target lifecycles, own symbol/risk checks, protection, timed close, aggregate exposure, persistence/restart recovery and bounded execution evidence.
- A single-EA signal, Python-only proxy or a reused closed-family output cannot claim a V8 Challenge victory.

Family 001-006 outputs and V1-V8 signals, opportunities, states and economics are excluded. Development is 2024-2025; locked 2026 January-July can open for at most one unchanged complete role. The authoritative frozen contract is `config/challenge-contract.json`.

Status: closed after one valid complete 2024-2025 development process. FOLLOW lost actual/stressed `-$53.708425 / -$135.688025` with `82.475678%` drawdown; FADE lost `-$74.118175 / -$129.559175` with `81.646377%` drawdown. Both years were adverse for both roles, so complete passer count is zero. Locked 2026, EA and native MT5 remain unopened, and the entire adjacent rank/window/subgroup/risk/exit rescue bundle is closed.
