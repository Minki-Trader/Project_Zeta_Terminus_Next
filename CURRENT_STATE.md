# Project Zeta Terminus Next Current State

Last updated: 2026-08-25

## State record

- Active chunk: [`state/CURRENT_STATE-0001.md`](state/CURRENT_STATE-0001.md)
- Latest state ID: `STATE-0030`
- Legacy migration anchor: `4c0899255c701e2c6b53e7f44457c431aef2ad76`

## Authorization

- Development: `ENABLED`, one serial stream only
- Next Live-Dev authorization: `ENABLED` by the user's explicit 2026-08-25 instruction to apply verified CP1 and CP2 to Live-Dev, subject to the same stopped-flat, entries-disabled recovery and final `0/0 → 1/1` boundary.
- Next V7 entries-disabled preflight: `PASSED`
- Next V7 new-entry authorization: `ENABLED` by the user's explicit CP1+CP2 Live-Dev instruction; the committed final `0/0` preflight and exact `1/1` handshake passed.
- Existing real-account owner: CP1+CP2 V7 release `NEXT-E01-V7-CXR1-c0ad2f30d293`, Portfolio `ZT-PORT-NEXT-V7-2db5ef5ead1c`, Magic `260824701..260824706`, terminal PID `21548`
- User V7 Live direction: `EFFECTIVE`

Legacy B70 V6R6 and parent V7 are stopped and disabled. Exact CP1+CP2 release is now the sole account owner at entries `1/1`. Its bounded stabilization snapshot at sequence `1470` has positions/order/margin/planned risk `0/0/$0/$0`, balance/equity `$106.52/$106.52`, project realized net `$5.87`, zero faults, and no alert or warning.

## Active work

- Active engineering boundary: none; CP1+CP2 Live promotion is complete and the release is frozen
- Active research boundary: none; `portfolio-exit-coordination-v1` is closed as `NO_MECHANISM_PASSED_RETAIN_FROZEN_V7`, no successor or rescue path is open, and all historical market paths remain consumed exploratory evidence
- Frozen parent: B70 V6R6
- V7 release ID: `NEXT-E01-V7-CXR1-c0ad2f30d293`
- V7 parent release ID: `NEXT-E01-V7-2db5ef5ead1c`
- V7 Portfolio ID: `ZT-PORT-NEXT-V7-2db5ef5ead1c`
- V7 Magic: `260824701..260824706`
- Forward Lab baseline: frozen `lab/engineering/complexity-refactor-v1/mt5/` at `9d1cbeeea232eec1e574dc7e4e3b0e65adf412b5`; `lab/mt5/` is historical and receives no new MQL source
- Required isolation: Live-Dev and Lab share no source Include tree, EX5, settings, Portable runtime, state, or logs
- B75: closed in Next solely as the inherited RC16 frozen-life HOLD confirmation

## Completed migration evidence

- Complete tracked-file manifest: `lineage/legacy-files.jsonl`, 1,475 records
- Complete scoped research index: `lineage/research-lineage.jsonl`, 1,011 records
  - research source: 359
  - human research document: 56
  - summary JSON: 596
- Human economic-family summaries: `docs/lineage/`
- Executable ancestry: `lineage/executable-lineage.json`
- Frozen B70 control: `lab/control-v6r6/`, eight files verified against its manifest
- Lab Portable: local MT5 build 6140 with copied US100/US30/US500 real-tick data
- Initial Live Portable shell: local MT5 build 6140, created without account/broker cache or executable V7 release
- Modular V7: 14 include modules plus assembly EA, MetaEditor build 6140 `0 errors / 0 warnings`
- Original modular V7 EX5 SHA-256: `0A722406921F76259E4828D87915C2BA6F2F345A4059CC310EEC4BC446011B53`
- V7 fixed-window evidence: `ECONOMIC_AND_ORDER_EQUIVALENCE_PASSED`
  - Latest: 84 first fills, actual `-$1.11`, stressed 2x `-$2.819`
  - Binding: 2,235 first fills, actual `+$1,019.04`, stressed 2x `+$940.6585`
  - After identity normalization, report summaries, all order rows and all deal rows have zero differences in both windows
- Original modular V7 package completed the one-way Lab-to-Live copy and remains frozen in Git history; `live-dev/package/active/` now holds the separately manifested CP1+CP2 successor
- Next status reader, Korean 5-second dashboard, entries-disabled starter, 0/0-to-1/1 Live starter, Master launcher, flat stop and local cache-handoff tools are implemented
- Offline operator check correctly refused readiness while legacy PID `24324` remained active; that legacy runtime has now stopped without a Next process starting
- Local handoff receipt pins legacy final commit `4d04a00`, final state/event hashes, the sole cached account and prior project realized net `$4.33`; it copies no V6 state or position
- Connected entries-disabled run 1: exact V7 identity, Magic and account; entries/positions/orders `0/0/0/0`; margin/risk `$0/$0`; balance/equity `$104.98/$104.98`; sequence `2`; Korean dashboard window and local five-second view verified
- Connected entries-disabled restart: normal `STOP`, then `RESUME entries-disabled`; state sequence advanced through `4`; the same exact flat, ownership, receipt and zero-fault state remained
- Corrected the operator's single-account array handling before any Next terminal started; committed operator HEAD `1888432` passed both connected entries-disabled runs
- Final Master handoff at Git `9ed684a`: exact `0/0` preflight PID `24488` passed and stopped, then exact V7 `1/1` PID `10112` passed release/Portfolio/Magic/account handshake; sole Korean dashboard PID `26868` opened
- Bounded stabilization advanced state sequence `7 → 8` through server `2026.08.24 09:42:15` with entries `1/1`, positions/order/margin/risk `0/0/$0/$0`, balance/equity `$104.98/$104.98`, zero ownership/safety/persistence/broker/foreign fault, and no alert or warning
- Final repository closeout: Next tag `next-live-v7-handoff-v1` points to completed handoff commit `405aef6`; legacy final commit/tag is `3bba815` / `terminus-final-handoff-v1`; private GitHub legacy repository is archived read-only while the private Next repository remains active

## Completed legacy closure

- Audited the exact B45/B55/B60/B65/B68/B74 human decision records at legacy anchor `4c0899255c701e2c6b53e7f44457c431aef2ad76`; all six Git blobs match `lineage/research-lineage.jsonl`
- Confirmed B75 `RC16 Explicit Frozen-Life HOLD Confirmation`: keep the full accepted RC16 volume to the original catastrophic stop or fixed eight-M30 exit
- Machine-readable record: `lab/evidence/RC16_FROZEN_LIFE_HOLD_CONFIRMATION_B75.json`, SHA-256 `C4FFF105C9918E3F81BD8936E09053034DC65338994EC1970484FD7541BBCAFC`
- The later explicit user direction opens only the separate Lab `전략 독립성·위험배분 연구`; it does not reopen B75

## Completed strategy independence and risk allocation research

- Declaration: `lab/evidence/STRATEGY_INDEPENDENCE_RISK_ALLOCATION_DECLARATION_V1.json`
- Frozen observation design: six tester-only single-strategy `$100` EAs plus one six-strategy shared `$100` first-come control, all with separate research identity and full opportunity/event logging
- Compile receipt: all seven Lab EAs MetaEditor build 6140 `0 errors / 0 warnings`, `lab/evidence/STRATEGY_INDEPENDENCE_RISK_ALLOCATION_COMPILE_RECEIPT_V1.json`
- Fit boundary: 790 standalone lifecycles through 2023 only; constants and source-log hashes frozen in `lab/evidence/STRATEGY_INDEPENDENCE_RISK_ALLOCATION_FIT_V1.json` before consuming any 2024 policy outcome
- 2024 result: first-come stress `+$54.6630`, DD `$17.7790`; all three reservation policies failed the fixed half-year/net/DD/breadth gate, so no policy was selected
- Fit: 2022-08-01 through 2023-12-31; selection: 2024 H1/H2; the predeclared 2025 forward and 2026 confirmation were not opened because no selection policy passed
- Conflict finding: 18 hard risk skips, 12 matched standalone winners, 9 winners with at least one nonpositive incumbent; descriptive headroom exists but was not causally predictable within the fixed variants
- 2025 and 2026 remain unconsumed because no policy passed 2024; future oracle is diagnostic only; no preemption, nearby rescue or Live change
- Closure: `lab/evidence/STRATEGY_INDEPENDENCE_RISK_ALLOCATION_CLOSURE_V1.json`, SHA-256 `637DEF903CB17F3D698E882E16A39F0820C8F0BC879AD821B1B0CC24AB758EDA`
- Live V7 terminal PID `10112` and dashboard PID `24936` remain outside the Lab research boundary and unchanged

## Completed operator improvement

- The Korean dashboard now shows each strategy's frozen entry criterion and server evaluation window, latest evaluation slot, signal value and verdict, candidate direction/price/volume/SL/planned risk, and current-position entry details
- The display uses only fields already present in the EA local snapshot plus display-only descriptions copied from the frozen V7 source; it sends no order and performs no broker history query
- Dashboard SHA-256: `5A3FB8D552511B8D16663F1E74973E57D856AD85AC28A453C7C1795A7A4BF9D6`
- Only the dashboard process restarted from PID `26868` to PID `24936`; exact V7 terminal PID `10112`, its start time, chart attachment, EA, EX5, SET and runtime state remained unchanged

## Completed deposit capital and risk capacity research

- User-authorized descriptive family: `예치자본·위험용량 연구` (`deposit-capital-risk-capacity`)
- Predeclared declaration: `lab/evidence/DEPOSIT_CAPITAL_RISK_CAPACITY_DECLARATION_V1.json`
- Proxy uses only the already-consumed fresh-`$100` 2024 combined and six standalone Lab ledgers and compares economic hypotheses rather than a parameter grid
- Exactly three Lab EA paths are allowed by the frozen shortlist rule: mandatory deposit-proportional `LINEAR_CAPITAL`, one capacity hypothesis and one sizing-governor hypothesis
- Proxy result: `LINEAR_CAPITAL` mandatory, `BREADTH_DOLLAR_SLOTS` capacity-eligible, `FIXED_LOT_LADDER` sizing diagnostic fallback; no fourth EA may be added in V1
- At `$200`, the 2024 conservative proxy was linear `54.663%` return / `17.779%` closed DD versus breadth `31.345%` / `7.589%`; breadth raised stressed net-to-DD from `3.0746` to `4.1303` while retaining fixed `$4` trade risk
- Four-slot 3% and six-slot 2% linear variants failed both halves and full-year conservative proxy; the fixed-lot ladder missed the efficiency/DD proxy gate and remains diagnostic only
- Proxy evidence: `lab/evidence/DEPOSIT_CAPITAL_RISK_CAPACITY_PROXY_V1.json`, SHA-256 `C75A51F2B1AD12B092108595B9BAA8435AB4FFF444AEAFDA8E189A9FC400A894`
- Three separately identified tester-only EA paths compiled on build 6140 at `0 errors / 0 warnings`; the frozen SIRA combined EA remains the deposit-only control
- Ten fresh 2025 serial configurations are frozen before outcome consumption: control `$100/$200/$300`, linear `$100/$200/$300`, breadth `$200/$300`, and ladder `$200/$300`
- Compile/preselection receipt: `lab/evidence/DEPOSIT_CAPITAL_RISK_CAPACITY_COMPILE_RECEIPT_V1.json`, SHA-256 `2CED8C9FFB0DBB6BD1CDB3F97E1BD43591736FAD7D5DF1E70DE2694DCE8221C9`
- Completed all ten serial fresh-account 2025 real-tick runs. Every MT5 report net/DD/trade/deal total matched the lifecycle ledger; all runs stopped normally with zero safety, persistence, broker, foreign, protection or margin/calculation fault
- Deposit-only `.01` produced stressed `+$113.068/+113.252/+113.252` at `$100/$200/$300`: extra cash mostly lowered DD% and diluted return rather than increasing dollar growth
- `LINEAR_CAPITAL` passed its structural anchor: stressed `+$113.068/+226.106/+338.984`, return `113.068/113.053/112.9947%`, DD `28.3905/28.3555/28.3605%`. It scaled dollar P/L and dollar DD, not edge or risk-adjusted performance
- `BREADTH_DOLLAR_SLOTS` removed every hard risk skip and reached four concurrent positions, but failed efficiency and the 90% return floor at both deposits; `FIXED_LOT_LADDER` was mildly positive versus linear at `$200` but failed return, efficiency and DD at `$300`
- No non-control policy passed. Per the fixed stop rule, 2026 January-May, June-July and partial August remained unopened; no nearby threshold rescue or fourth EA was attempted
- Selection: `lab/evidence/DEPOSIT_CAPITAL_RISK_CAPACITY_SELECTION_V1.json`, SHA-256 `39ADE4BB8EDC1264F313BEACDE88BA3202678263FB4606C057AA0A83CA54C1B4`
- Closure: `lab/evidence/DEPOSIT_CAPITAL_RISK_CAPACITY_CLOSURE_V1.json`, SHA-256 `56B64F0592AA152C88A2038C58E679F70345205EB3A4682E8BED8435F54E7452`
- Human conclusion: `docs/lineage/DEPOSIT_CAPITAL_AND_RISK_CAPACITY.md`; exact Live V7 PID `10112`, dashboard PID `24936`, source, package, SET, state and order behavior remained unchanged

## Completed complexity refactor Checkpoints 1 and 2

- Derived a fully independent tester-only engineering candidate from frozen source commit `75bd9c9`, not from moving `lab/mt5` and not as a Live dependency
- Candidate identity is release `NEXT-LAB-CXR1-ENTRY-GATE`, portfolio `ZT-PORT-NEXT-LAB-CXR1-ENTRY-GATE`, Magic `260825100..260825105`, with independent source, EX5, SET, state/event/snapshot/lock paths and Portable runtime
- Replaced the shared boolean `PrepareEntry` gate with read-only `EvaluateEntryGate`, side-effect-owning `ApplyEntryGateResult`, and thin `CommitOpportunityConsumption`; changed only the five market-strategy call sites, with RC4 limited to `ProcessRC4Both`
- MetaEditor build 6140 compiled the isolated frozen control and CP1 at `0 errors / 0 warnings`; CP1 EX5 SHA-256 is `7CDB41D96A88F9C46F951CFF979250B3283CF2507D087B9AF94AACC75429CEF8`
- Same-runtime Latest and Binding real-tick reports matched at all `411` and `9,114` structured rows respectively; state/current/lock hashes were equal and event differences normalized to zero after excluding one `deal_wait_ms` wall-clock diagnostic in each window
- The fresh Latest control reproduced frozen V7. The fresh Binding control differed from the immutable 2026-08-24 report beginning with 2023-04-10 protection prices despite source equality, so CP1 was judged only against its immediately adjacent same-runtime control and no broader environment/economic hypothesis was opened
- CP2 split `OpenComponent()` into explicit Plan, Durable Intent, Submit, Observe, Provisional Seed, Validate, Adopt and Finalize stages inside `ZetaOrders.mqh`; the public signature and all five strategy call sites stayed unchanged
- The direct `OpenComponent()` surface fell from `348 → 38` lines, `18 → 6` branches, `13 → 0` direct `trade.*` calls, and zero direct save, event, decision-intent, journal-writer or trade-operation writes
- CP2 compiled at `0 errors / 0 warnings`; same-runtime Latest and Binding again matched all `411` and `9,114` report rows, all five state/current/lock hashes and all four graphs, with only the same non-decision `deal_wait_ms` row in each window
- CP3 was evaluated and held with no source change: every permitted writer is already uniquely owned after CP1+CP2, while a broker file would add an include/file without reducing writers and could cross the durable-intent order
- Evidence: `lab/evidence/COMPLEXITY_REFACTOR_ENTRY_GATE_CP1_V1.json` and `lab/evidence/COMPLEXITY_REFACTOR_MARKET_ENTRY_CP2_V1.json`; no Live source, package, SET, state, terminal or dashboard changed

## Completed CP1 and CP2 Live promotion

- Explicit user authorization received on 2026-08-25 to apply the already-verified CP1 and CP2 implementation to Live-Dev
- Frozen target release: `NEXT-E01-V7-CXR1-c0ad2f30d293`; canonical source/settings SHA-256 `C0AD2F30D293AD538A91DE74A6D0A14A560FA19222F1DB043E1C533C103A7DD7`
- Exact seven promoted implementation files are byte-equal to the CP2 candidate; Live main assembly, economic SET, execution version, Portfolio, Magic, state marker/schema/paths and all non-CP implementation files remain unchanged
- MetaEditor build 6140 compiled the isolated exact promotion source at `0 errors / 0 warnings`; target EX5 SHA-256 is `F0B7D64BE36F81304C8764A89DFFA2499CD5F4ACED73A7A1837F950EFECC919F`
- Parent PID `10112` and dashboard PID `24936` stopped at the fresh pre-window flat boundary. Target entries-disabled PIDs `28168` and `17656` both recovered the exact parent state, passed `0/0` and stopped normally
- Final preflight PID `26112` passed exact `0/0` and stopped; exact target Live PID `21548` passed release/Portfolio/Magic/account `1/1` handshake. Sole Korean dashboard PID `4712` is active
- Bounded stabilization advanced to sequence `1470` at server `2026.08.25 09:35:11` with entries `1/1`, flat zero-risk state, balance/equity `$106.52/$106.52`, zero faults and no warning or alert
- Source topology is now mandatory in `docs/OPERATING_DIRECTION.md` and `AGENTS.md`: `lab/mt5` is frozen historical material, the CP2 root is the sole forward baseline, and every future family must own an isolated root

## Completed Live-Dev performance forensics

- Closed one read-only Lab family at `lab/research/live-dev-performance-forensics/`; it added no MQL, EA, Adapter, settings, runtime dependency, broker query, exit candidate or Live authority
- Reconstructed 14 completed V1/V2/V3/V5/V7 real-account lifecycles through server `2026-08-24 21:59:59`: project net `+$5.87`, 9 wins / 5 losses, gross `+$10.78/-$4.91`, profit factor `2.195519`; V6/V6R2/V6R6 produced no completed real lifecycle
- Separated two V1/V2 execution-control incidents totaling `-$0.08`; the remaining 12 economic lifecycles produced `+$5.95` with 9 wins / 3 losses
- All three economic losers had first been profitable. Their MFE-to-final giveback was `$8.1390`, 69.7998% of the `$11.6605` total measured giveback across the 12 tick paths
- On 2026-08-20 the `SELL/BUY/BUY` triple had all three legs positive for 71.3687% of overlap and peaked at `+$3.3585`; on 2026-08-24 the `BUY/BUY/SELL` V7 triple had all three positive for 94.6766%, recorded account equity `$108.69` at third entry and reached a hindsight tick-equity proxy of `$109.7725`
- The user's `$108-$111` manual-close estimate is directionally supported but bounded: `$108.69` is directly recorded, `$109.77` is a hindsight V7 peak, and applying two event-observable snapshots while holding later paths unchanged gives a non-guaranteed `$109.83` proxy; `$111` is not directly established
- The preserved availability gaps did not lower realized performance in the reconstructed interval: the 2026-08-19 gap probably avoided an approximately `-$0.53` Cross time-exit, the 2026-08-21 gap missed zero threshold-qualified RC4/RC16/Passive entries, and the later gap was during the weekend
- Evidence: `lab/research/live-dev-performance-forensics/evidence/LIVE_DEV_PERFORMANCE_FORENSICS_V1.json`, SHA-256 `26E059C33F952E4FB2921101B9295921021828C13282E8C876B54DE36054B52F`; closure is `CLOSE_WITHOUT_NEW_HYPOTHESIS`

## Completed portfolio exit coordination research

- Predeclared and completed exactly 16 serial fresh-`$100` build-6140 real-tick paths: frozen CP2 V7 control plus first-natural-exit positive-cohort close, all-green zero floor and all-green 0.25R/50%-peak trail across P1 2022H2-2023, 2024, 2025 and 2026 YTD through August 20
- All runs stopped normally at 100% real ticks; report net/trade/deal totals reconciled to final snapshot/component evidence, all coordination close requests succeeded, and safety, persistence, broker, foreign, protection and coordination-close faults were zero
- Control pooled actual/stressed net and summed stressed closed DD were `$444.19/$407.0477/$96.1393`. First-exit was `$343.93/$306.8285/$88.3285`, zero-floor `$319.62/$280.6710/$80.8470`, and quarter-R/half-peak `$424.74/$387.2135/$93.6940`
- The 2026-08-20 motivating cohort is real: first-exit preserved `+$2.89` gross at 17:45 versus the control cohort's eventual `+$0.84`. But the rule triggered 394 times and lost `$100.2192` stressed net across the fixed matrix, so that single useful intervention did not generalize
- No candidate reached the required pooled stressed-net improvement or three-of-four actual/stressed breadth; all had lower stressed-net/DD efficiency than control. Zero-floor also exceeded 115% of control DD in P1. The least-bad quarter-R/half-peak path won only 2024 and remained `$19.8342` stressed net below control overall
- Selection is `lab/research/portfolio-exit-coordination-v1/evidence/PORTFOLIO_EXIT_COORDINATION_SELECTION_V1.json`, SHA-256 `991FBCB8CE3B81EA14C0FC04EDF5B75B4E9BE5E7523835B8D4EE3938A7A3F88A`; closure is `PORTFOLIO_EXIT_COORDINATION_CLOSURE_V1.json`, SHA-256 `C6BA432F8CFC8E5A55E470843A63FA6675C20F6F4AA6B260004A8E2FBBB1B3EE`
- Closed `NO_MECHANISM_PASSED_RETAIN_FROZEN_V7`. No seventeenth run, hybrid, adjusted threshold, date/strategy exception, successor family, Live source/package/settings/state/process change or promotion authority opened; exact Live PID `21548` remained separate and locally active

## Required completion evidence

1. concise human lineage summaries and complete hash-anchored legacy indexes
2. independent Live-Dev and Lab runtime/package structure
3. modular V7 compile with zero errors and warnings
4. ~~exact fixed latest and binding real-tick behavior after identity normalization~~
5. ~~bounded connected entries-disabled restart, ownership, reconciliation, and dashboard evidence after legacy flat stop~~
6. ~~separate user authorization, final 0/0 preflight, and exact 1/1 handshake before any V7 real order~~

## Current verdict

`LEGACY_REPOSITORY_ARCHIVED; B75_RC16_FROZEN_LIFE_HOLD_CONFIRMED; STRATEGY_INDEPENDENCE_RISK_ALLOCATION_V1_CLOSED_RETAIN_FIRST_COME; DEPOSIT_CAPITAL_RISK_CAPACITY_V1_CLOSED_RETAIN_FROZEN_V7; FRONTIER_2025_THROUGH_2026_08_21_CONSUMED_EXPLORATORY_ONLY; COMPLEXITY_REFACTOR_CP1_ENTRY_GATE_EQUIVALENCE_PASSED; COMPLEXITY_REFACTOR_CP2_MARKET_ENTRY_EQUIVALENCE_PASSED; CP3_HOLD_CP2_SUFFICIENT_NO_ADDITIONAL_VALUE; CXR1_LIVE_PROMOTION_COMPLETE; CXR1_SOLE_OWNER_HEALTHY; SOURCE_TOPOLOGY_GUARD_ACTIVE; LIVE_DEV_PERFORMANCE_FORENSICS_V1_CLOSED_NO_EXIT_HYPOTHESIS`
