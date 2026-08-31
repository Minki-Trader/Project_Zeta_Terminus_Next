# DD20 V8 Causal Drawdown State Shaping Proxy V1

This campaign is mandatory Stage C of `V8-OPT-U001-PORTFOLIO-DD`. It tests a deployable closed-balance drawdown response around all three frozen Stage-B static seeds. The mechanism changes only the volume and effective risk of future opportunities exact V8 already emits.

## Causal state

Each candidate owns an actual realized closed-balance high-water mark. After an accepted lifecycle closes, current drawdown is `(high-water balance - actual balance) / high-water balance`. Crossing the frozen trigger activates a risk multiplier only for later births. Existing positions are never resized or force-closed.

The active multiplier is applied before V8's `0.01` lot-step rounding to `0.01 × daily_multiplier × static_component_weight × state_multiplier`. Position risk remains `0.04`; executable volume therefore changes the future effective component multiplier and position budget. Aggregate cap remains the static seed's `0.12`.

Release requires both the frozen number of subsequent accepted closes and recovery to `trigger - hysteresis` or better. The triggering close is excluded from the hold count. Repeated causal trigger/release cycles are allowed. Each fresh replay period starts at `$100` with inactive state and no future, open-equity, period-label or holdout oracle.

## Frozen variants

For each of three Stage-B seeds:

- trigger drawdown: `0.05 / 0.075 / 0.10 / 0.125`
- active future-birth multiplier: `0.50 / 0.65 / 0.80`
- release hysteresis: `0.025 / 0.05`
- minimum subsequent accepted closes: `5 / 10 / 20`

That is `72` variants per seed and `216` total. Fine robustness uses immediate neighbors within the same static seed and requires four eligible neighbors across three state axes. At most one robust center per static seed and three total may advance to validation and mandatory Stage D.

No input staging, implementation or outcome begins until the Stage-B result and this Stage-C declaration reach `origin/main`. Stage C has zero MT5 authority and cannot close the Unit.
