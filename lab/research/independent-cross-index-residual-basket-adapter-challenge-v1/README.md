# Independent Cross-Index Residual Basket Adapter Challenge V1

This is Independent V8 Challenge Family 003, allocated to Program 5 (`portfolio_capital_risk`). It asks whether a causal rolling relationship among US100, US30 and US500 can support a high-turnover two-leg convergence basket after both-leg costs and minimum-lot distortion.

The architecture is mandatory `Python adapter + EA`:

- Python estimates each ordered pair's rolling log-price hedge relation from completed H1 bars, standardizes the current residual, chooses at most one most-displaced pair, and emits both legs plus frozen basket-risk metadata.
- A separate EA must reproduce the causal state, validate adapter freshness and both symbol contracts, size and submit the pair fail-closed, reconcile partial submission, protect the basket, perform convergence/PnL/time closes, recover state and write bounded evidence.
- A Python-only proxy or a single EA that owns the new residual decision cannot claim a V8 Challenge victory.

Families 001 and 002 features, labels, predictions, decisions, models and outcomes are excluded. The same three original H1 price authorities may be copied only after the declaration reaches `origin/main`. Development is 2024-2025; the still-unopened 2026 January-July interval may confirm at most one unchanged role.

The authoritative contract is `config/challenge-contract.json`. One paired basket counts as one lifecycle start, never two starts for its legs.

## Development result

The one complete 2024-2025 process is closed valid with no survivor. `RESIDUAL_Z075 / Z100 / Z125` produced `488 / 466 / 426` baskets, only `0.961 / 0.917 / 0.839` starts per normal day, and actual/stressed net of `-$88.505 / -$103.836`, `-$88.125 / -$103.292`, and `-$87.225 / -$101.340`. Actual closed-balance drawdown was `87.54%..88.50%`.

All three pairs produced valid causal states, so this is an economic and turnover nonconfirmation rather than a source, fit or implementation fault. Locked 2026, the EA, compile and MT5 remain unopened. The residual-z threshold, pair/window/gate, direction, exit, risk and subgroup neighborhood is frozen with this closure.
