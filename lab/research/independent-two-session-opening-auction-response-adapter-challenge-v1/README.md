# Independent Two-Session Opening Auction Response Adapter Challenge V1

This is Independent V8 Challenge Family 006, allocated to Program 3 (`order_time_session`) at micro-to-meso height. It asks whether the first five completed US100/US30 M1 bars after the London and New York local cash opens contain persistent or mean-reverting price discovery strong enough to beat V8.

The mandatory architecture is `Python adapter + EA`:

- Python owns IANA exchange-local scheduling, exact M1 completeness, the frozen five-bar opening body/range and the `OPEN_DRIVE_5M / OPEN_FADE_5M` decisions.
- The EA must validate adapter sequence/freshness and symbol contracts, size and submit the two symbol lifecycles, own protection/timed close, aggregate risk, persistence/restart recovery and bounded evidence.
- A single-EA signal or Python-only proxy cannot claim a V8 Challenge victory.

Family 001-005 outputs and V1-V8 signals, opportunities, state and economics are excluded. Development is 2024-2025; locked 2026 January-July could have confirmed at most one unchanged response role. The authoritative contract is `config/challenge-contract.json`.

Status: closed after the one authorized development process. DRIVE/FADE started `1,008 / 1,277` lifecycles but lost actual `-$98.8627 / -$98.9047`, stressed `-$227.8451 / -$207.7592`, and reached roughly `99.1%` actual closed-balance drawdown. Capital depletion caused `884 / 615` minimum-lot risk blocks, reducing turnover below three starts per normal day. Locked 2026, EA, compile and MT5 remained unopened; the complete response/session/window/filter/risk/exit bundle has no within-family rescue authority.
