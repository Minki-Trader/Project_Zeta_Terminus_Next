# Complexity Refactor V1

This is a tester-only engineering candidate derived from Git commit `75bd9c9` and the frozen `NEXT-E01/V7` behavior contract.

- Candidate release: `NEXT-LAB-CXR1-ENTRY-GATE`
- Candidate portfolio: `ZT-PORT-NEXT-LAB-CXR1-ENTRY-GATE`
- Candidate Magic: `260825100..260825105`
- Source root: `lab/engineering/complexity-refactor-v1/mt5/`
- Local runtime: `lab/runtime/complexity-refactor-v1-portable/`
- Live authority: none

Checkpoint 1 refactors only the shared market-entry gate and the five explicit market-strategy call sites. Signal math, execution, risk, persistence schema, Passive, and RC4 management remain frozen.

Checkpoint 1 verdict: `ENTRY_GATE_EQUIVALENCE_PASSED_STOP_BEFORE_CP2`.

Evidence:

- `CHECKPOINT_1.md`
- `lab/evidence/COMPLEXITY_REFACTOR_ENTRY_GATE_CP1_V1.json`

Checkpoint 2 separates the market-open transaction inside `ZetaOrders.mqh` into explicit Plan, Durable Intent, Submit, Observe, Provisional Seed, Validate, Adopt, and Finalize stages without changing strategy call sites, persistence schema, broker calls, or economic behavior.

Checkpoint 2 verdict: `MARKET_ENTRY_TRANSACTION_EQUIVALENCE_PASSED`.

Evidence:

- `CHECKPOINT_2.md`
- `lab/evidence/COMPLEXITY_REFACTOR_MARKET_ENTRY_CP2_V1.json`

The Checkpoint 3 value gate is `CP3_HOLD_CP2_SUFFICIENT_NO_ADDITIONAL_VALUE`. CP1+CP2 already provide every permitted direct-writer boundary; no CP3 source change, architecture file, Passive change, or RC4 change was opened.
