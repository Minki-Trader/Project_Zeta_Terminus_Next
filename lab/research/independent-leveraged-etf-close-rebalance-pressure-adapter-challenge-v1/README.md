# Independent Leveraged ETF Close Rebalance Pressure Adapter Challenge V1

This is Independent V8 Challenge Family 008, allocated to Program 2 (external_market_event) at meso height. It asks whether a completed, unusually large and coherent QQQ/TQQQ regular-session move creates causal leveraged-product rebalance pressure that continues through the final US100 half hour strongly enough to beat V8.

The mandatory architecture is Python adapter + EA:

- Python owns fresh QQQ/TQQQ source validation, broker-server `Europe/Helsinki` wall-clock normalization to true UTC, `America/New_York` scheduling, complete-session returns, the causal prior-60 QQQ magnitude rank, coherence and direction, the prior-20 US100 risk distance, immutable sequence/freshness evidence and the byte-pinned decision tape.
- The EA must validate the adapter contract, size and submit the US100 lifecycle, own symbol/risk checks, protection, timed close, persistence/restart recovery and bounded execution evidence.
- A single-EA signal, Python-only proxy or reused closed-family output cannot claim a V8 Challenge victory.

The family freezes one signal population and two related exits before outcomes: LEVERAGED_ETF_CLOSE_PRESSURE_TIME_CLOSE and LEVERAGED_ETF_CLOSE_PRESSURE_TAKE_1P5R. Both variants and the mandatory MFE/MAE, cost, risk-block, exit-truncation and year-stability improvement-potential audit must complete before the family can close.

Development is 2024-2025. QQQ/TQQQ 2026 January-July remains unacquired and locked for at most one unchanged complete development passer. The authoritative contract is config/challenge-contract.json. The original declaration used selection-metadata aliases QQQ.xnms/TQQQ.xnms; connected original-broker metadata canonicalized them to QQQ/TQQQ before any price row or outcome.

The acquisition files preserve MT5's raw Unix-like epoch rendering, but the connected broker encoded its server wall-clock rather than semantic UTC. A time-column-only preimplementation diagnostic therefore froze `Europe/Helsinki` attachment followed by true-UTC/New-York conversion. Exact completeness still excludes half days, missing minutes and US/Europe DST-mismatch weeks; no clock, window or economic rule changed.

The complete adapter is `adapter/run_adapter.py` with modes `precheck`, `development` and `confirmation`. Because the longest evidence paths exceed the default Windows legacy path boundary, invocations temporarily map this workspace and the candidate runtime to short drive letters and remove both mappings afterward; the adapter deliberately preserves those short roots rather than resolving them back to the long physical path.

The outcome-free precheck found 442 exact development common days and 117 gated events (57 negative, 60 positive), or 0.264705882 starts per normal day per variant. All 117 initial minimum-lot risks are feasible at $100. It simulated zero future exit path, lifecycle, PnL or improvement value and wrote zero persistent output.

The sole development process completed all 117 signals for both variants. TIME_CLOSE returned actual/stressed `-$57.71415 / -$62.84485` with `61.35935%` drawdown; TAKE_1P5R returned `-$54.91960 / -$60.18480` with `58.098775%` drawdown. Both lost in 2024 and 2025. The mandatory audit found raw stressed full-hold expectancy below zero in both years and both external signs; the take exit changed only ten paths, improved five and worsened five, avoided no later stop and supplied no broad improvement headroom.

Status: closed valid adverse development with no passer, no bounded successor seed, no locked-2026 acquisition, no EA and no MT5 Tester run. This source/configuration/economic bundle is immutable.
