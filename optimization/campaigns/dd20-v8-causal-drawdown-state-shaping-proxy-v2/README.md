# DD20 V8 Causal Drawdown State Shaping Proxy V2

V2 is the result-authority correction for Stage C of `V8-OPT-U001-PORTFOLIO-DD`. V1's state transition, volume, admission and economic arithmetic exposed no fault, but its serialized `stage_d_roles` list was populated after validation and before the frozen whole-path gate. V2 makes final succession coherent.

## Unchanged economic experiment

V2 keeps the exact same three static seeds, `216` state variants, inputs, causal transition order, actual/stressed arithmetic, periods, primary/fallback gates, fine-neighbor robustness, validation, locked holdout and whole-path gates. It uses no new outcome, parameter, threshold, neighbor or alternate.

The sole code-authority correction is:

- validation-passing centers remain visible as diagnostics;
- a role is written to `stage_d_roles` only after the same frozen role passes locked holdout and the whole-path `75%` stressed-retention plus five-point DD-improvement gate;
- if the whole gate fails, the list is empty and mandatory Stage D opens only an empty closure/recomparison boundary.

The complete V1 raw result is pinned as correction parity input. V2 must reproduce all frozen key economic values and counts while correcting only the final status/Stage-D role authority and implementation metadata.

No input staging, implementation or replay begins until the V1 correction closure and this V2 declaration reach `origin/main`. MT5, Lab, new-entry and Live authority remain zero.
