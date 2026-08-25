# Complexity Refactor V1 — Checkpoint 1

Date: 2026-08-25 KST
Verdict: `ENTRY_GATE_EQUIVALENCE_PASSED_STOP_BEFORE_CP2`

## Boundary

The candidate is a tester-only copy derived from Git commit `75bd9c9`, with release `NEXT-LAB-CXR1-ENTRY-GATE`, portfolio `ZT-PORT-NEXT-LAB-CXR1-ENTRY-GATE`, Magic `260825100..260825105`, independent state/event/snapshot/lock paths, and an independent Portable runtime. Live and the moving `lab/mt5` tree were not modified.

Checkpoint 1 changed only `ZetaStrategyShared.mqh` and the gate call sites in RC16, `ProcessRC4Both`, Pressure, Return, and Cross. `OpenComponent`, risk, margin, persistence schema, Passive, and RC4 management were not changed.

## Gate mapping

| Frozen branch | Explicit result | Consumed | Application effect |
|---|---|---:|---|
| current bar unavailable | `ENTRY_GATE_BAR_UNAVAILABLE` | no | none |
| same durable decision bar | `ENTRY_GATE_ALREADY_CONSUMED` | no new write | none |
| owned positions > 1 | `ENTRY_GATE_DUPLICATE_EXPOSURE` | yes | observation → mismatch → safety stop → decision save |
| owned positions == 1 | `ENTRY_GATE_EXISTING_EXPOSURE` | yes | observation → decision save |
| RC4 shadow occupied | `ENTRY_GATE_RC4_SHADOW_OCCUPIED` | yes | observation → counter → decision save |
| outside entry window | `ENTRY_GATE_NOT_IN_WINDOW` | no | none |
| elapsed > 2 minutes | `ENTRY_GATE_DELAY_EXCEEDED` | yes | observation → `SKIP_DELAY` → decision save |
| otherwise | `ENTRY_GATE_READY` | no | `CHECKING_SIGNAL`, then the frozen strategy path |

`EvaluateEntryGate` retains the frozen observation order `iTime → same-bar short circuit → CountOwnedPositions → RC4 shadow → TimeCurrent → delay`. It writes no global state, file, event, safety flag, or broker state. `ApplyEntryGateResult` owns the existing side effects, and `CommitOpportunityConsumption` remains a thin call to the existing `PersistDecision`.

## Compile and direct comparison

MetaEditor build 6140 compiled both the identity-isolated frozen control and CP1 at `0 errors / 0 warnings`.

| Window | Control / CP1 lifecycle count | Final balance | Stressed 2x net | Final order / deal | Report row differences | Event differences after diagnostic normalization |
|---|---:|---:|---:|---:|---:|---:|
| Latest, 2026-06-01 through 2026-07-31 | `84 / 84` | `$98.89 / $98.89` | `-$2.819 / -$2.819` | `178 / 169` | `0 / 411` | `0 / 652` |
| Binding, 2022-08-01 through 2026-08-20 | `2234 / 2234` | `$1,242.00 / $1,242.00` | `+$1,058.630 / +$1,058.630` | `4581 / 4469` | `0 / 9,114` | `0 / 4,149` |

The only raw event difference in each window was one `OPEN` row's `deal_wait_ms` (`0` versus `15`), an existing `GetTickCount64` wall-clock diagnostic that is not read by any decision. State A/B, current snapshot A/B, and ownership-lock hashes were equal in both windows.

## Frozen-reference replay note

The fresh Latest control reproduced the frozen V7 result exactly. The fresh Binding control did not reproduce the 2026-08-24 frozen report: its first report difference appears on 2023-04-10 in protective-stop prices, despite all non-identity source being text-equal to the frozen active package. The frozen report remains immutable evidence. Checkpoint 1 was therefore judged only by the immediately adjacent control and CP1 runs in the same independent runtime and current tester environment. No broader environment or economic hypothesis was opened.

Checkpoint 2 is not open and requires a separate user instruction.
