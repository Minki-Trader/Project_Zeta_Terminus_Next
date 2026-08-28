# DD20 Capital Composition Proxy V1

This serial optimization campaign asks a different question from the closed gross-allocation proxy. Instead of letting every component independently consume the entire drawdown budget, it fixes four whole-portfolio gross multiplier budgets and reallocates each budget among the six components.

## Why this direction

The prior proxy showed that near-uniform gross leverage nearly doubled selection profit but amplified the known later loss and breached the `20%` proxy-DD cap. A 15-point risk-cap response surface would require weak extrapolation beyond a discontinuous observed rectangle, while a dynamic timing or drawdown governor cannot be causally reconstructed from close-only fixed-path evidence. Fixed-budget component composition is the distinct proxy direction that the preserved lifecycle stream directly supports.

## Frozen proxy contract

- Source path: the same observed `0.04 / 0.18` maximum-profit lifecycle path, copied again into this campaign's own raw input.
- Component multiplier lattice: `0.0 / 0.5 / 1.0 / 1.5 / 2.0 / 2.5 / 3.0`.
- Whole-portfolio gross multiplier budgets: `6.0 / 7.5 / 9.0 / 10.5`, corresponding to mean multipliers `1.00 / 1.25 / 1.50 / 1.75` across six components.
- At least four components must retain a positive multiplier. This permits radical portfolio reconstruction without allowing a one- or two-component hindsight book.
- Exactly `29,016` discrete compositions satisfy the lattice, budget and breadth contract.
- Actual and doubled-cost-stressed lifecycle nets are accumulated in original close order from `$100`. Proxy DD is the worse actual/stressed peak-to-current closed-balance percentage drawdown and is never calibrated downward.
- Full selection plus four frozen epochs must keep actual/stressed net positive, balances positive and proxy DD at or below `20%`.
- Role 1 maximizes full-selection stressed net. Role 2 maximizes the final twelve selection months beginning 2025-06-01 while all earlier epochs still pass. Role 3 maximizes the weakest epoch's stressed-net uplift ratio versus the unweighted base. Duplicate role winners advance to the next distinct result under that role's fixed ordering.
- The already known 2026-06/07 segment is not read by the selection search. After all three roles freeze, it confirms only positive actual/stressed net, positive balance and proxy DD at or below `20%`. No failed role is retuned or rescued.

This remains an allocation proxy, not MT5 profit or mark-to-market DD proof. It changes no MT5, MQL, Live, Lab or broker state and can nominate at most three MT5 candidates. The declaration is `evidence/DD20_CAPITAL_COMPOSITION_PROXY_DECLARATION_V1.json`.

## Closed boundary

The proxy completed all `29,016` compositions in `12.55` seconds. Of `12,330` selection-eligible compositions, the predeclared recent-selection role at weights `3.0 / 3.0 / 1.0 / 2.5 / 1.0 / 0.0` was the sole isolated-later survivor. It produced selection actual/stressed net `$2,557.205 / $2,430.3735` at `19.850887%` proxy DD and later actual/stressed net `+$16.955 / +$13.855` at `16.810504%` proxy DD.

Status is `VALID_PROXY_COMPLETE_ONE_MT5_SHORTLIST`. The frozen survivor is one MT5 hypothesis, not MT5 proof and not Live authority. The two failed roles remain failed without retuning. Durable result evidence is `evidence/DD20_CAPITAL_COMPOSITION_PROXY_RESULT_V1.json`.
