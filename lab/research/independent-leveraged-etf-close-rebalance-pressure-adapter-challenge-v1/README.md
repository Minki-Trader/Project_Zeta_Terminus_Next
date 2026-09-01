# Independent Leveraged ETF Close Rebalance Pressure Adapter Challenge V1

This is Independent V8 Challenge Family 008, allocated to Program 2 (external_market_event) at meso height. It asks whether a completed, unusually large and coherent QQQ/TQQQ regular-session move creates causal leveraged-product rebalance pressure that continues through the final US100 half hour strongly enough to beat V8.

The mandatory architecture is Python adapter + EA:

- Python owns fresh QQQ/TQQQ source validation, broker-server `Europe/Helsinki` wall-clock normalization to true UTC, `America/New_York` scheduling, complete-session returns, the causal prior-60 QQQ magnitude rank, coherence and direction, the prior-20 US100 risk distance, immutable sequence/freshness evidence and the byte-pinned decision tape.
- The EA must validate the adapter contract, size and submit the US100 lifecycle, own symbol/risk checks, protection, timed close, persistence/restart recovery and bounded execution evidence.
- A single-EA signal, Python-only proxy or reused closed-family output cannot claim a V8 Challenge victory.

The family freezes one signal population and two related exits before outcomes: LEVERAGED_ETF_CLOSE_PRESSURE_TIME_CLOSE and LEVERAGED_ETF_CLOSE_PRESSURE_TAKE_1P5R. Both variants and the mandatory MFE/MAE, cost, risk-block, exit-truncation and year-stability improvement-potential audit must complete before the family can close.

Development is 2024-2025. QQQ/TQQQ 2026 January-July remains unacquired and locked for at most one unchanged complete development passer. The authoritative contract is config/challenge-contract.json. The original declaration used selection-metadata aliases QQQ.xnms/TQQQ.xnms; connected original-broker metadata canonicalized them to QQQ/TQQQ before any price row or outcome.

The acquisition files preserve MT5's raw Unix-like epoch rendering, but the connected broker encoded its server wall-clock rather than semantic UTC. A time-column-only preimplementation diagnostic therefore froze `Europe/Helsinki` attachment followed by true-UTC/New-York conversion. Exact completeness still excludes half days, missing minutes and US/Europe DST-mismatch weeks; no clock, window or economic rule changed.

Status: original-broker development sources are pinned and the raw-time semantic correction is frozen before adapter implementation, price-derived state or outcomes.
