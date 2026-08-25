# Complexity Refactor V1 — Checkpoint 2

Date: 2026-08-25 KST
Verdict: `MARKET_ENTRY_TRANSACTION_EQUIVALENCE_PASSED`
Next: `CP3_HOLD_CP2_SUFFICIENT_NO_ADDITIONAL_VALUE`

## Boundary

Checkpoint 2 continues from durable Checkpoint 1 commit `5393fed733835a3d50e285c1e9fadfcbf621d149`. It changes only the isolated candidate's `Execution/ZetaOrders.mqh` market-open path plus two tester INIs. Live, the moving `lab/mt5` tree, persistence schema, strategy math, risk math, Passive, close, cancel, and RC4 modify/shadow behavior were not changed.

The candidate keeps release `NEXT-LAB-CXR1-ENTRY-GATE`, portfolio `ZT-PORT-NEXT-LAB-CXR1-ENTRY-GATE`, Magic `260825100..260825105`, independent state/event/snapshot/lock paths, and its independent tester-only Portable runtime.

## Implemented transaction boundary

`OpenComponent()` retains its public signature and strategy call sites. Its market-entry path is now the following explicit sequence:

```text
BuildMarketEntryPlan
→ PersistMarketEntryIntent
→ SubmitMarketEntry
→ ObserveMarketEntry
→ SeedProvisionalMarketLifecycle
→ ValidateMarketEntry
→ AdoptMarketEntry
→ FinalizeMarketEntry
```

The local transient types `MarketEntryPlan`, `MarketSubmitReceipt`, `MarketEntryObservation`, and `MarketEntryOutcome` remain inside `ZetaOrders.mqh`; they are not Domain state and are not persisted. No state field, journal stage, event schema, broker call, or save boundary was added or removed.

### Branch and result-code map

| Existing behavior | Owning stage | Result code | Existing external result |
|---|---|---|---|
| entry disabled or invalid direction | Plan | `MARKET_ENTRY_ENTRY_BLOCKED` | `ENTRY_BLOCKED` |
| ownership audit or foreign exposure | Plan | `MARKET_ENTRY_OWNERSHIP_BLOCKED` | `OWNERSHIP_BLOCKED` |
| existing owned exposure | Plan | `MARKET_ENTRY_EXISTING_EXPOSURE` | `EXISTING_EXPOSURE` |
| rounded volume invalid | Plan | `MARKET_ENTRY_VOLUME_INVALID` | `VOLUME_INVALID` |
| executable quote unavailable | Plan | `MARKET_ENTRY_QUOTE_UNAVAILABLE` | `QUOTE_UNAVAILABLE` |
| protection or risk admission blocked | Plan | `MARKET_ENTRY_PROTECTION_OR_RISK_BLOCKED` | `PROTECTION_OR_RISK_BLOCKED` |
| trade session blocked | Plan | `MARKET_ENTRY_SESSION_BLOCKED` | `TRADE_SESSION_BLOCKED` |
| margin blocked | Plan | `MARKET_ENTRY_MARGIN_BLOCKED` | `MARGIN_BLOCKED` |
| durable `ORDER_ATTEMPTED` failed | Durable Intent | `MARKET_ENTRY_DURABLE_INTENT_FAILED` | `PERSISTENCE_FAILED` |
| request false or non-success retcode | Submit | `MARKET_ENTRY_SUBMIT_REJECTED` | `BROKER_REJECTED` |
| position/deal observation failed | Observe | `MARKET_ENTRY_OBSERVATION_FAILED` | `SAFETY_STOP` |
| broker execution identity mismatch | Validate | `MARKET_ENTRY_IDENTITY_MISMATCH` | `SAFETY_STOP` |
| actual protection/risk mismatch | Validate | `MARKET_ENTRY_PROTECTION_MISMATCH` | `SAFETY_STOP` |
| broker-adoption persistence failed | Adopt | `MARKET_ENTRY_ADOPTION_PERSIST_FAILED` | `SAFETY_STOP` |
| final state persistence failed | Finalize | `MARKET_ENTRY_FINAL_PERSIST_FAILED` | `POSITION_OPEN` plus safety stop |
| protected position finalized | Finalize | `MARKET_ENTRY_POSITION_OPEN` | `POSITION_OPEN` |

### Side-effect ownership

| State or effect | Sole market-entry owner after CP2 |
|---|---|
| candidate volume/price/stop/risk observation | `BuildMarketEntryPlan()` application block |
| CTrade settings and durable journal plan | `PersistMarketEntryIntent()` |
| `trade_operation_active`, Buy/Sell, and Result capture | `SubmitMarketEntry()` |
| broker position/deal reads | `ObserveMarketEntry()` |
| provisional component lifecycle | `SeedProvisionalMarketLifecycle()` |
| mismatch events, safety stop, and protective close decision | `ValidateMarketEntry()` |
| durable broker adoption | `AdoptMarketEntry()` |
| `OPEN` event and final state save | `FinalizeMarketEntry()` |

The original ordering remains CTrade settings → journal plan → durable `ORDER_ATTEMPTED` → one Buy/Sell call → Result capture → broker observation → provisional seed → validation → durable adoption → `OPEN` → final save. Caller-owned `FinalizeDecisionJournal()` remains at all five strategy call sites.

## Complexity result

| `OpenComponent()` direct surface | CP1 | CP2 |
|---|---:|---:|
| lines through the next function boundary | 348 | 38 |
| direct `if` branches | 18 | 6 |
| direct `trade.*` calls | 13 | 0 |
| direct `SaveState()` calls | 3 | 0 |
| direct `RecordEvent()` calls | 4 | 0 |
| direct `decision_intent` field accesses | 7 | 0 |
| direct journal writer calls | 2 | 0 |
| direct `trade_operation_active` writes | 2 | 0 |

The orchestrator now exposes the transaction order without owning broker, persistence, validation, or lifecycle details. A reviewer can inspect one named stage and its direct dependency instead of following all stages simultaneously.

## Compile and real-tick equivalence

MetaEditor build 6140 compiled CP2 at `0 errors / 0 warnings`. CP2 EX5 SHA-256 is `B0627195DC38F07B65B6E84699DF10E0D2A83A3EE82991FEAA289608404E5BA3`.

| Window | CP1 and CP2 first fills | Final balance | Actual net | Stressed 2x net | Report rows | Differences |
|---|---:|---:|---:|---:|---:|---:|
| Latest `2026-06-01/2026-08-01` | 84 | `$98.89` | `-$1.11` | `-$2.819` | 411 | 0 |
| Binding `2022-08-01/2026-08-21` | 2,234 | `$1,242.00` | `+$1,142.00` | `+$1,058.630` | 9,114 | 0 |

All five state/current/lock files and all four report graphs were hash-equal in both windows. Latest had 652 stored event rows and Binding had 4,149. Each window had one raw `OPEN` row differing only in existing `deal_wait_ms` wall-clock telemetry (`15` versus `0`); normalized event differences were zero.

Binding contained 417 market `OPEN` events. Every one had the exact same-component sequence `SIGNAL_DECIDED → ORDER_ATTEMPTED → BROKER_STATE_ADOPTED → OPEN → DECISION_JOURNAL_FINAL`; sequence mismatches were zero.

## Rare failure and restart boundary

Normal runs observed no `OPEN_FAIL`, `OPEN_EXECUTION_MISMATCH`, or `OPEN_PROTECTION_MISMATCH`; no claim of exercised broker ambiguity, persistence failure, or process termination is made. Source review confirms that CP2 adds no durable state and preserves every existing restart boundary:

- before durable intent: the existing `SIGNAL_DECIDED` no-replay path remains;
- after `ORDER_ATTEMPTED`, including process loss during submit: startup reconciliation sees the same durable journal and never resubmits automatically;
- after broker observation or provisional seed: no new save occurs, so startup reconstructs the broker position from the same last durable state;
- validation failure: the existing event, safety stop, pending reconcile, and protective close order remains;
- after durable adoption: the same `BROKER_STATE_ADOPTED` state is available to startup reconciliation;
- after `OPEN` with final-save failure: the protected broker position remains and new entries fail closed, with no new automatic close.

This is normal-path real-tick equivalence plus explicit source-reviewed rare-path preservation, not injected failure evidence. No test-only CLI, validator, or failure harness was created.

## Checkpoint 2 Gate and Checkpoint 3 value decision

1. The simultaneous reasoning surface decreased: `OpenComponent()` is a 38-line stage graph with no direct broker, save, event, journal, or lifecycle ownership.
2. Every market-entry failure is distinguishable by `EMarketEntryResultCode`.
3. Broker calls and state writes are exposed by the owning function names.
4. All transient types remain local to `ZetaOrders.mqh` and did not become a Domain/global state object.

All four Checkpoint 2 Gate questions pass. Checkpoint 3 implementation is nevertheless held because every ownership restriction it permits is already true after CP1+CP2. `SubmitMarketEntry()` is already the sole market-open Buy/Sell and Result owner. Moving it to a new broker file would add an include and an additional file without reducing writers; moving CTrade settings with it would also cross the durable-intent ordering boundary. Therefore the smallest valuable CP3 change is no source change.

Verdict: `CP3_HOLD_CP2_SUFFICIENT_NO_ADDITIONAL_VALUE`. Passive and RC4 direct CTrade sites remain listed current contracts and are not modified or opened as follow-up work.

## Frozen-reference replay note

As at Checkpoint 1, the immutable 2026-08-24 Binding report is not treated as the direct CP2 comparator because the fresh CP1-era runtime already diverged from it at 2023-04-10 protective-stop prices. CP2 is judged only against the immediately adjacent CP1 artifacts from the same isolated runtime and current tester environment. No environment or economic hypothesis was opened.
