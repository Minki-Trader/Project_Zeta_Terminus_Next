# DD20 Paired Clean Requalification MT5 V2

This is the versioned validity-design correction to `dd20-paired-clean-requal-mt5-v1`. V1 stopped before CANDIDATE because its exact V8-derived CONTROL completed on clean 100%-real-tick history but emitted the inherited aggregate `data_unavailable=12` RC4-management counter. V1 had frozen a zero counter without requiring reason telemetry, so it cannot distinguish missing input from an exact-policy no-action on a complete but mathematically undefined market window. V1 is `CORRECTION_REQUIRED`, not an economic success, failure or nonconfirmation; its observed money is quarantined and cannot change this campaign's treatment or gates.

## Fixed comparison

V2 keeps the same continuous `2024-01-01` through `2026-08-01` interval, Model 4, `$100`, `1:100`, `US30 M30` primary path and required US30/US100/US500 history. CONTROL is exactly `1 / 1 / 1 / 1 / 1 / 1` at position/aggregate risk `0.04 / 0.18`. CANDIDATE remains the exact V8 economic tuple `2 / 1.5 / 2 / 2.5 / 1.5 / 0` at `0.04 / 0.18`. Control runs first and a complete valid control is immediately followed by the candidate in the same dedicated non-Master Portable. No weight, risk, cap, signal, hold, exit, stop, protection, sizing, rounding, capital-ladder, margin, admission or aggregate-risk change is permitted.

## Corrected integrity design

The only behavioral-source addition is read-only telemetry that assigns every failed RC4 head calculation one exact reason while retaining the same evaluation order, calls, returns, persistence and retry behavior. A short history copy, invalid/nonpositive price or tick, invalid direction, nonfinite value or unclassified reason invalidates the pair. A deterministic policy no-action may remain valid only when the new row proves that all requested input was present on the unchanged complete 100%-real-tick corpus and the calculation was undefined solely because an observed bar/window had zero range or zero variance, or because a session boundary had no completed current-day bar. Every aggregate unavailable count must reconcile one-for-one to unique reason rows, with zero diagnostic drop or unresolved pending state.

This correction does not convert the V1 count into valid evidence. Both V2 paths must independently re-prove their own reason rows, detailed-history cleanliness, contract/swap equality and all other fingerprints. Any other reason remains an environment or engineering correction with no economic verdict.

## Economic gate

The economic gate is unchanged from V1. The candidate must be positive actual and doubled-cost-stressed, exceed the control by at least `$100` in both measures, reach at least `2.0x` positive control actual and stressed net, improve stressed-net-to-native-equity-DD, keep native maximum relative equity DD at or below the separately disclosed pragmatic `21.2%` envelope, remain positive actual and stressed in calendar 2024, calendar 2025 and 2026 through July, keep all five active components positive actual and stressed, produce zero Passive close and finish with zero true fault or pending state. The nominal `20.0%` line remains separately reported.

A pass opens only a separately named Lab economic-handoff correction. A valid nonconfirmation leaves V8 entries disabled and returns the serial stream to whole-map family ranking. Neither result authorizes direct Live promotion.

## Boundary

The dedicated future runtime is `optimization/runtime/dd20-pcr2-portable/`. Declaration is frozen before source derivation, configuration, runtime creation, compilation or Tester execution. Live, Lab and every other Optimization campaign remain isolated. V8 PID `30592` remains the exact entries-disabled `0/0` owner and is outside this campaign.

