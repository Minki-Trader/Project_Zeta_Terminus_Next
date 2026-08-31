# Independent Two-Session Opening Auction Response Adapter Challenge V1

This is Independent V8 Challenge Family 006, allocated to Program 3 (`order_time_session`) at micro-to-meso height. It asks whether the first five completed US100/US30 M1 bars after the London and New York local cash opens contain persistent or mean-reverting price discovery strong enough to beat V8.

The mandatory architecture is `Python adapter + EA`:

- Python owns IANA exchange-local scheduling, exact M1 completeness, the frozen five-bar opening body/range and the `OPEN_DRIVE_5M / OPEN_FADE_5M` decisions.
- The EA must validate adapter sequence/freshness and symbol contracts, size and submit the two symbol lifecycles, own protection/timed close, aggregate risk, persistence/restart recovery and bounded evidence.
- A single-EA signal or Python-only proxy cannot claim a V8 Challenge victory.

Family 001-005 outputs and V1-V8 signals, opportunities, state and economics are excluded. Development is 2024-2025; locked 2026 January-July may confirm at most one unchanged response role. The authoritative contract is `config/challenge-contract.json`.
