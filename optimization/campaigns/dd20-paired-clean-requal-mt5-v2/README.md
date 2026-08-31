# DD20 Paired Clean Requalification MT5 V2

This is the versioned validity-design correction to `dd20-paired-clean-requal-mt5-v1`. V1 stopped before CANDIDATE because its exact V8-derived CONTROL completed on clean 100%-real-tick history but emitted the inherited aggregate `data_unavailable=12` RC4-management counter. V1 had frozen a zero counter without requiring reason telemetry, so it cannot distinguish missing input from an exact-policy no-action on a complete but mathematically undefined market window. V1 is `CORRECTION_REQUIRED`, not an economic success, failure or nonconfirmation; its observed money is quarantined and cannot change this campaign's treatment or gates.

## Fixed comparison

V2 keeps the same continuous `2024-01-01` through `2026-08-01` interval, Model 4, `$100`, `1:100`, `US30 M30` primary path and required US30/US100/US500 history. CONTROL is exactly `1 / 1 / 1 / 1 / 1 / 1` at position/aggregate risk `0.04 / 0.18`. CANDIDATE remains the exact V8 economic tuple `2 / 1.5 / 2 / 2.5 / 1.5 / 0` at `0.04 / 0.18`. Control runs first and a complete valid control is immediately followed by the candidate in the same dedicated non-Master Portable. No weight, risk, cap, signal, hold, exit, stop, protection, sizing, rounding, capital-ladder, margin, admission or aggregate-risk change is permitted.

## Corrected integrity design

The only behavioral-source addition is read-only telemetry that assigns every failed RC4 head calculation one exact reason while retaining the same evaluation order, calls, returns, persistence and retry behavior. A short history copy, invalid/nonpositive price or tick, invalid direction, nonfinite value or unclassified reason invalidates the pair. A deterministic policy no-action may remain valid only when the new row proves that all requested input was present on the unchanged complete 100%-real-tick corpus and the calculation was undefined solely because an observed bar/window had zero range or zero variance, or because a session boundary had no completed current-day bar. Every aggregate unavailable count must reconcile one-for-one to unique reason rows, with zero diagnostic drop or unresolved pending state.

This correction does not convert the V1 count into valid evidence. Both V2 paths must independently re-prove their own reason rows, detailed-history cleanliness, contract/swap equality and all other fingerprints. Any other reason remains an environment or engineering correction with no economic verdict.

## Economic gate

The economic gate is unchanged from V1. The candidate must be positive actual and doubled-cost-stressed, exceed the control by at least `$100` in both measures, reach at least `2.0x` positive control actual and stressed net, improve stressed-net-to-native-equity-DD, keep native maximum relative equity DD at or below the separately disclosed pragmatic `21.2%` envelope, remain positive actual and stressed in calendar 2024, calendar 2025 and 2026 through July, keep all five active components positive actual and stressed, produce zero Passive close and finish with zero true fault or pending state. The nominal `20.0%` line remains separately reported.

A pass would have opened only a separately named Lab economic-handoff correction. The completed fixed pair is instead a valid nonconfirmation, so this campaign itself grants no Lab or Live authority and opens no adjacent retuning. The user's later one-time exact-release Live research exception is recorded separately; it does not change this campaign's verdict or failed gates and creates no authority for another release.

## Boundary

The declaration and implementation freeze each reached `origin/main` before their next phase. Two invalid CONTROL environment attempts were preserved without economic verdict. After the full symbols database was frozen read-only, the adjacent CONTROL and unchanged CANDIDATE both completed on the same `114,350,355`-tick, `30,487`-bar, 100%-real-tick corpus with zero required-symbol fallback or true fault and twelve fully reconciled `COMPLETE_ZERO_RANGE_WINDOW` reason rows per path. CONTROL produced actual/stressed `+$373.30 / +$342.6655`, native relative equity DD `14.14%` and robust recovery `6.32347`; CANDIDATE produced `+$409.81 / +$367.818`, native relative equity DD `37.39%` and robust recovery `3.29586`.

CANDIDATE missed the frozen `+$100` deltas (`+$36.51 / +$25.1525`), `2.0x` multiples (`1.0978x / 1.0734x`), recovery improvement, `21.2%` relative-equity-DD envelope and all-active-components-stressed-positive gate because Cross was `-$2.56` stressed. V2 is therefore closed `VALID_CLEAN_HISTORY_FIXED_PAIRED_CANDIDATE_NOT_REQUALIFIED_NO_LIVE_AUTHORITY`. The durable record is `evidence/DD20_PAIRED_CLEAN_REQUAL_MT5_V2_VALID_NONCONFIRMATION_V1.json`; Live, Lab and every other Optimization campaign remained isolated.
