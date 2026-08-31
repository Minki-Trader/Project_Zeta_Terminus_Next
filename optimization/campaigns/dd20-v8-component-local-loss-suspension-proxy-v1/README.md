# DD20 V8 Component-Local Loss Suspension Proxy V1

This is mandatory Stage C of `V8-OPT-U002-MEMBERSHIP-RECONSTRUCTION`. Stage B froze three static allocations. Stage C tests one neutral role plus nine component-local causal suspension roles for each seed before opening validation.

## Mechanism

Each active strategy tracks only its own admitted closes. After `2 / 3 / 4` consecutive losing closes, only that strategy's next `2 / 4 / 8` accepted-source births are suppressed. Suppression affects strictly future V8 opportunities, never force-closes an existing position and never creates an entry. A suppressed source birth consumes one suspension slot and contributes zero on its later close.

The full grid is `3 seeds × (1 neutral + 9 causal) = 30` roles. State starts clean for each fresh period. The proxy gives zero profit credit to unknown capacity-freed opportunities.

## Selection and validation

Nonneutral roles must actually trigger and suppress an otherwise executable birth. Robustness requires two eligible immediate N/K neighbors spanning both axes. Within each seed, a robust causal role displaces neutral only when it improves weakest annual stressed net, or ties that metric and improves stressed-net-to-DD efficiency. Exactly one immutable role per seed then receives fresh January-May validation.

Validation requires positive actual/stressed/minimum balance, DD no more than `30%`, and at least `65%` exact-V8 validation stressed retention. All passing roles, at most three, advance unchanged to Stage D. June-July remains locked.

## Current boundary

The campaign is declared pre-input, pre-implementation and pre-outcome. It changes an isolated Optimization mechanism but no Live/Lab code, and it has zero MT5 authority.
