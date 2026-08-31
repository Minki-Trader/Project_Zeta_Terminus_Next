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

## Frozen implementation boundary

Declaration commit `3c973ee77dc8cb3dd27a938ac87abc469719a8ac` reached `origin/main` before staging. All three inputs are byte-equal, the Stage-B schema/status and three seed vectors match, and the state lattice is exactly `72 / 72 / 72`, `216` unique coordinates.

With state disabled, the implementation reproduces exact V8 whole actual/stressed `+$409.81 / +$367.818` at `35.46%` actual DD and all three static-seed development paths at `+$150.105 / +$133.103`, `24.099813585%` DD, with zero state triggers. Config is `4,935` bytes / `3EEB32DA...118AD`; source is `53,504` bytes / `E7777B1C...3D602` and passes Python `3.13.9` syntax with NumPy `2.3.4`. No raw Stage-C output exists. Execution waits for the implementation freeze to reach `origin/main`.

## Final correction-required boundary

V1 ran all `216` variants and its raw status correctly identified a whole-path-gate nonconfirmation, but it had already written one validation-passing role into `stage_d_roles` before evaluating that final gate. The role's whole stressed retention is only `55.6728%` against the frozen `75%`; therefore it cannot own Stage-D authority.

Final V1 status is `CORRECTION_REQUIRED_PRE_FINAL_STAGE_D_ROLE_SERIALIZATION_NO_ECONOMIC_VERDICT`. The state/economic numbers remain diagnostic only. V2 repeats the exact same `216` paths and changes only successor-list timing: a role is appended after and only after `final_pass`.
