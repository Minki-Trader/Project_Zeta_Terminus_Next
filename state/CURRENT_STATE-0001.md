# Project Zeta Terminus Next State 0001

## STATE-0001 - 2026-08-24

- Created the separate continuity project boundary from legacy Terminus commit `4c0899255c701e2c6b53e7f44457c431aef2ad76`. The project begins with a new Git history rather than cloning the legacy 728-commit and high-volume artifact surface.
- Fixed `NEXT-E01/V7` as a behavior-preserving engineering successor to B70 V6R6. V7 receives new Magic `260824701..260824706`, identity, state and evidence, while every inherited economic and causal behavior remains frozen.
- Next Live-Dev authority is `DISABLED`. Existing legacy B70 V6R6 remains the only authorized real-account owner. B75 is paused without an opened outcome until migration completion.

## STATE-0002 - 2026-08-24

- Completed the first continuity inventory at the frozen legacy commit. `lineage/legacy-files.jsonl` records all 1,475 tracked files with repository, commit, path, Git blob, SHA-256 and byte size.
- Completed the scoped research lineage requested for migration: 359 research source files, 56 human research documents and 596 summary JSON files, exactly 1,011 records in `lineage/research-lineage.jsonl`. Unknown relationships, periods and decisions remain explicitly `unknown`; later outcomes were not backfilled.
- Reorganized the human-facing record into seven economic families under `docs/lineage/`. `Pre-V1`, `Economic`, `Axis A`, `Axis B` and `Axis C` remain provenance tags rather than the table of contents.
- Fixed the executable core line in `lineage/executable-lineage.json`: `B48 -> B49/V6R2 -> B52/V6R3 -> B66/V6R4 -> B67/V6R5 -> B70/V6R6 -> NEXT-E01/V7`, with the earlier finite-risk ancestry preserved ahead of B48.
- This inventory is descriptive continuity evidence, not new profit evidence and not a promotion result. The one-time extraction code was not retained as a project CLI, validator or test harness.

## STATE-0003 - 2026-08-24

- Created physically separate `lab/` and `live-dev/` lanes. Lab junctions resolve only under `lab/`; Live static junctions resolve only under `live-dev/package/active/`. Neither lane points into the other or into legacy source.
- Froze the eight-file B70 V6R6 control under `lab/control-v6r6/`: source, EX5, SET, binding/latest INI, B70 human record, declaration JSON and validation JSON. Every SHA-256 and byte size matches the legacy anchor manifest. Bulk backtest logs and reports remain referenced rather than copied.
- Initialized the Git-ignored Lab Tester Portable with MT5 build `5.0.0.6140` and local copies of US100, US30 and US500 required history/tick caches. Source and destination counts and byte totals match for all 12 terminal/tester history and tick directories.
- Initialized only a staged Live Portable shell at build `5.0.0.6140`. It has no `Bases`, no account or broker configuration, no EA state and no runnable V7 release. No Next terminal was started.
- Gracefully stopped the legacy Lab/Tester terminal before copying its cache. The legacy B70 V6R6 Live terminal remained running and unchanged throughout.

## STATE-0004 - 2026-08-24

- Extracted B70 V6R6 into a modular V7 without introducing a strategy registry or plug-in layer. The six strategies remain six explicit modules and six explicit calls; the main EA now owns only assembly and inherited event ordering.
- Made `ComponentDefinition`, `ComponentState`, `PortfolioState`, `ExecutionState` and `DecisionIntent` real runtime state owners. The original fields and persistence order remain behaviorally inherited; current snapshot and event records add only `schema_version`, `release_id` and `project_id` identity fields.
- Fixed candidate identity from a normalized final source/settings tree: canonical SHA-256 `2db5ef5ead1c68e6f596f78726adcc9d622ec4f58868451aec11a68a5748578e`, release `NEXT-E01-V7-2db5ef5ead1c`, Portfolio ID `ZT-PORT-NEXT-V7-2db5ef5ead1c`, Magic `260824701..260824706`.
- Preserved the B70 SET byte-for-byte and changed only Expert, preset and report identities in the two tester INIs. Their non-identity settings match B70 exactly for binding `2022-08-01` through completed `2026-08-20` and latest `2026-06-01` through `2026-07-31`.
- MetaEditor build `5.0.0.6140` compiled the 14-module source tree with `0 errors / 0 warnings`. Candidate EX5 SHA-256 is `0A722406921F76259E4828D87915C2BA6F2F345A4059CC310EEC4BC446011B53`.
- Compilation is engineering evidence only. Fixed-window V6R6/V7 real-tick equality is still pending, so this candidate is not promoted and Next Live remains `DISABLED`.

## STATE-0005 - 2026-08-24

- Re-ran frozen B70 V6R6 and modular NEXT-E01/V7 independently in the Lab Tester Portable on FPMarkets build 6140 with `Every tick based on real ticks`, fixed `$100`, `1:100`, identical cost/execution settings and all required symbols.
- Latest `2026-06-01` through completed `2026-07-31` matched at 84 first fills, actual net `-$1.11`, stressed 2x net `-$2.819`, 53 report summary rows, 178 order rows, 169 deal rows and 652 stored event rows after identity normalization.
- Binding `2022-08-01` through completed `2026-08-20` matched at 2,235 first fills, actual net `+$1,019.04`, stressed 2x net `+$940.6585`, 53 report summary rows, 4,583 order rows and 4,471 deal rows after identity normalization. All six strategy counts and stressed nets matched.
- One of 4,165 bounded binding event rows differed only in `deal_wait_ms` (`15` versus `0`), a `GetTickCount64` diagnostic not consumed by any decision. Its price, volume, stop, planned risk, order and deal fields matched, and every report order/deal row matched. The exception is explicit in `lab/evidence/NEXT_E01_V7_EQUIVALENCE.json`.
- Verdict: `ECONOMIC_AND_ORDER_EQUIVALENCE_PASSED`. This verdict is not Live authority.

## STATE-0006 - 2026-08-24

- Copied the verified source tree, EX5 and base SET once from Lab into `live-dev/package/active/`. MQ5, EX5, SET and all 14 include hashes match the candidate manifest; no automatic Lab-to-Live link exists.
- Implemented the Next-only PowerShell/WinForms operator surface: exact local snapshot status, Korean 5-second dashboard, account-cache handoff import, entries-disabled start, verified-flat stop, 0/0-to-1/1 Live start and Master terminal/dashboard launcher.
- The tools verify the frozen hashes, Git `HEAD == origin/main`, release/Portfolio/Magic/state identity, local handoff receipt, one cached account and exclusive terminal ownership. They fail closed if legacy Terminus or another Next terminal/tester is running.
- Performed only an offline read-only check. It recognized the frozen EX5 and correctly reported not ready because legacy PID `24324` remained active, runtime settings/snapshot did not exist and Live authorization was disabled. No Next terminal was started and no broker state was queried.
- Connected entries-disabled save/restart, broker reconciliation and dashboard evidence remain blocked until the natural legacy flat handoff boundary permits the stopped account cache to be imported. Next Live remains `DISABLED`; legacy B70 V6R6 is unchanged.

## STATE-0007 - 2026-08-24

- The legacy project committed and pushed its natural flat verification at `964f710`, then stopped exact B70 V6R6 normally and committed the stopped-owner boundary at `4d04a00`. The final legacy event was `STOP normal` at server `2026.08.24 09:32:58`; persisted state sequence reached `846`. Positions, pending order, margin, planned risk, RC4 lifecycle/retry/shadow and decision journal were all zero at handoff. The final project-attributable realized net is `$4.33`.
- Legacy Live authority is disabled and relevant legacy/Next terminal, tester and dashboard process count is zero. Next now records `Existing real-account owner: none` and enables only the connected V7 entries-disabled handoff preflight. V7 new entries and effective Next Live authority remain disabled.
- The user explicitly instructed complete replacement by V7 through Live. Recorded that direction as received but pending the already-required entries-disabled save/restart evidence; it does not bypass the `0/0` boundary or authorize an order before that evidence passes and the effective authorization state is committed.

## STATE-0008 - 2026-08-24

- Imported only the stopped legacy account/broker cache into the Git-ignored Next Live Portable and wrote the local handoff receipt. It pins legacy final commit `4d04a00`, the final state/event SHA-256 values, the sole cached account and prior-project realized net `$4.33`; no V6 state, position, Portfolio ID or Magic was adopted.
- The first entries-disabled invocation stopped before terminal start because a single cached account was unwrapped to a scalar and the operator attempted to read a missing `Count` property. Corrected the PowerShell collection preservation without changing the EA, package, SET economics or authorization; parsed, committed and pushed operator HEAD `1888432` before retry. No order or terminal existed during the failed invocation.
- Connected entries-disabled run 1 started exact V7 PID `27016` and passed release/Portfolio/Magic/account, `0/0` entries, positions/orders `0/0`, margin/risk `$0/$0`, balance/equity `$104.98/$104.98`, prior realized net `$4.33`, zero faults and state sequence `2`. The Korean five-second dashboard opened as a real window and displayed the same six-strategy flat state from local snapshots only.
- The exact flat-stop tool produced normal `STOP`; connected run 2 started PID `27448`, recovered with `RESUME entries-disabled`, advanced sequence through `4`, and retained exact `0/0`, flat, zero-risk, zero-fault and receipt continuity. It then stopped normally, leaving legacy and Next terminal/tester counts zero.
- The user's explicit complete V7 replacement-through-Live instruction now becomes effective because the required entries-disabled evidence passed. Next Live-Dev and V7 new-entry authorization are `ENABLED`, but the only permitted next action remains the committed Master's mandatory final `0/0` preflight followed by exact `1/1` handshake.

## STATE-0009 - 2026-08-24

- At committed and pushed Git `9ed684a`, the Master started exact V7 `0/0` preflight PID `24488`. It passed release, Portfolio, six Magic, account, broker connection, flat exposure, zero order/margin/risk, `$4.33` prior-project continuity and zero faults, then stopped normally before Live start.
- The Master then started exact V7 `1/1` Live PID `10112`. Handshake proved release `NEXT-E01-V7-2db5ef5ead1c`, Portfolio `ZT-PORT-NEXT-V7-2db5ef5ead1c`, Magic `260824701..260824706`, terminal trading and entries `1/1`, connection/binding/identity `1/1/1`, balance/equity `$104.98/$104.98`, project realized net `$4.33`, stage balance `$104.33`, and positions/order/margin/planned risk `0/0/$0/$0`. Legacy exact terminal count was zero and Next exact terminal count was one.
- The Korean five-second dashboard opened as sole PID `26868`. A subsequent bounded stabilization snapshot advanced state sequence `7 → 8` through server `2026.08.24 09:42:15` while retaining `1/1`, flat zero-risk state, all four ownership/safety fault flags zero and no alert or warning.
- Classified `V7_LIVE_HANDOFF_COMPLETE; NEXT_V7_SOLE_OWNER_HEALTHY`. The verified frozen V7 release is now the sole real-account owner; legacy must not restart. B75 `RC16 Explicit Frozen-Life HOLD Confirmation` returns as the next single research task but remains unopened at this handoff boundary.

## STATE-0010 - 2026-08-24

- Pushed Next final handoff commit `405aef63c7d46c16fb5c0157a91bf296094a9267` and annotated tag `next-live-v7-handoff-v1`. A repeated Master invocation recognized existing exact V7 PID `10112` and the sole dashboard, restored both windows and created no duplicate.
- Pushed legacy final handoff commit `3bba815d9e67e45a87a032cf3da425c92242e150` and annotated tag `terminus-final-handoff-v1`, then archived the private GitHub repository `Minki-Trader/Project_Zeta_Terminus` read-only. The private Next repository remains active and unarchived; local legacy history and runtime evidence were not deleted.
- Repository closeout changed no V7 source, EX5, SET, state, entry, management, ownership or risk behavior. Exact V7 remains the sole authorized Live owner and B75 remains the next unopened serial task.

## STATE-0011 - 2026-08-24

- The user fixed the post-migration scope to closing only the inherited B75 record and explicitly declined opening a new research axis. No successor research family, candidate or experiment is active.
- Audited the complete B45/B55/B60/B65/B68/B74 human decision records at legacy anchor `4c0899255c701e2c6b53e7f44457c431aef2ad76`. Their six Git blobs match the exact SHA-256-linked records in `lineage/research-lineage.jsonl`, and none adopted an RC16 management alternative or left a nearby rescue open.
- Closed B75 as `RC16_EXPLICIT_FROZEN_LIFE_HOLD_CONFIRMED`: after accepted fill and original catastrophic-stop ownership confirmation, retain the full accepted RC16 volume to the original catastrophic stop or fixed eight-M30 exit. This is a legacy evidence conclusion, not a new management right.
- Recorded the machine-readable closure in `lab/evidence/RC16_FROZEN_LIFE_HOLD_CONFIRMATION_B75.json`, SHA-256 `C4FFF105C9918E3F81BD8936E09053034DC65338994EC1970484FD7541BBCAFC`. No new data, outcome calculation, latest period, tester or terminal run, source, EX5, SET, identity, Magic, state, deployment or Live change opened.
- Exact V7 `NEXT-E01-V7-2db5ef5ead1c` remains the frozen sole Live owner. B75 is complete and no further Lab research is authorized without a new explicit user direction.

## STATE-0012 - 2026-08-24

- Added dashboard-only visibility for every strategy's frozen entry criterion and server evaluation window, latest evaluation slot, signal value and pass/fail state, candidate direction/price/volume/SL/planned risk, and current-position entry time/direction/volume/SL/risk.
- The dashboard continues to read only the existing local V7 snapshot. Static criterion descriptions mirror the exact frozen V7 source for display only and are not consumed by the EA or any order path. PowerShell parsing completed with zero errors and the local `-Once` renderer showed all six strategy sections.
- Restarted only the dashboard from PID `26868` to PID `24936` so the new view became active. V7 terminal PID `10112` and its start time remained unchanged; the EA stayed attached to the chart and no source, EX5, SET, state, order behavior or broker query changed.
- Dashboard SHA-256 is `5A3FB8D552511B8D16663F1E74973E57D856AD85AC28A453C7C1795A7A4BF9D6`. B75 remains closed and no research stream opened.

## STATE-0013 - 2026-08-24

- By explicit user direction, opened one new serial Lab family named `전략 독립성·위험배분 연구`; new Next research no longer uses Axis-style names, while legacy Axis labels remain provenance only.
- Fixed the design before economic execution: six tester-only `$100` single-strategy EAs, one frozen-order six-strategy shared `$100` control, full signal-passed opportunity and lifecycle event logging, fit through 2023, separate 2024 H1/H2 selection, fixed 2025 forward, and unopened 2026 until the forward gate passes.
- Predeclared first-come, stored win-probability, conservative stressed-R and overlap-aware one-slot reservation comparisons. The future-aware oracle is diagnostic only; initial scope excludes preemption, exit changes and nearby threshold rescue.
- All research identity, Magic, source, settings, state, events, reports and Portable paths remain under Lab. Exact Live V7 PID `10112`, dashboard PID `24936`, Live EA, Include, EX5, SET and state are unchanged and receive no promotion authority from this opening.
- Compiled the combined control and all six standalone wrappers with MetaEditor build 6140 at `0 errors / 0 warnings`; the hash-pinned receipt is `lab/evidence/STRATEGY_INDEPENDENCE_RISK_ALLOCATION_COMPILE_RECEIPT_V1.json`. Economic runs have not yet begun at this state boundary.

## STATE-0014 - 2026-08-24

- Completed the seven serial 2022-08-01 through 2024-12-31 observation runs in the Lab Portable. Every run had continuous opportunity IDs, exactly the intended selected component(s), one normal STOP, a complete report and zero safety, persistence, broker-identity or foreign-exposure fault lines. The shared control recorded 37 aggregate-risk admission skips.
- Before reading any 2024 policy outcome, parsed only standalone lifecycles with decision bar before 2024-01-01: RC16 `77`, RC4 `53`, Cross `306`, Pressure `35`, Return `106`, Passive `213`, total `790`. The maximum included decision bar is `2023-12-29 14:45:00`.
- Frozen Beta(1,1) predicted win probability, conservative clamped stressed-R score and 20-pseudo-observation overlap adjustments in `lab/evidence/STRATEGY_INDEPENDENCE_RISK_ALLOCATION_FIT_V1.json`, SHA-256 `82FBD9DE57FFA5D6ACF5E2873B26C7F043CCF9E946F4BF681030CA4F9135DD7B`. The record explicitly states `selection_rows_consumed=false` and pins all six source-log hashes plus the analysis source hash.
- No 2024 policy candidate, 2025 forward, 2026 confirmation, Live source or Live process changed at this fit boundary.

## STATE-0015 - 2026-08-24

- Before opening 2024 selection outcomes, fixed equal period initialization: every 2024 standalone, first-come control and policy run starts fresh at `$100` on 2024-01-01; every eventual 2025 comparison will likewise start fresh at `$100` on 2025-01-01. No fit-period state or profit carries into either period.
- Embedded only the frozen pre-2024 Beta win probabilities, conservative clamped stressed-R scores and overlap adjustments into three separately identified Lab policy EAs. Each can reserve at most one 4% slot when admitting the current candidate would consume the third slot and a higher-scored fixed evaluation window remains later that server day.
- The policies never evict an incumbent, change a signal, stop, hold or exit, and release unused capacity after the last relevant window. They use Magic `260824871..876`, `260824881..886` and `260824891..896` and hard-fail outside MQL Tester.
- All three compiled with MetaEditor build 6140 at `0 errors / 0 warnings`; `lab/evidence/STRATEGY_INDEPENDENCE_RISK_ALLOCATION_POLICY_COMPILE_RECEIPT_V1.json` pins their EX5, compile logs, fit evidence and amended declaration. No selection run or 2025/2026 data was opened at this boundary.

## STATE-0016 - 2026-08-24

- Completed ten serial fresh-`$100` 2024 real-tick selection runs: six standalone strategies, frozen first-come shared control and three predeclared one-slot reservation policies. Every analysis actual net, 2x-cost stressed net and maximum closed drawdown matched the corresponding MT5 final summary exactly; all ten source-log hashes match and all incumbent mask states resolved.
- Standalone 2024 stressed results were RC16 `+$9.0000`, RC4 `+$14.1740`, Cross `+$35.1245`, Pressure `-$5.8620`, Return `-$1.6260`, Passive `+$11.8795`. These are six separate `$100` accounts and are not summed against the shared `$100` control.
- First-come produced 554 trades, actual `+$62.75`, stressed `+$54.6630`, maximum closed DD `$17.7790`, 306 overlapping position pairs, 240 entries with an earlier incumbent and 18 hard aggregate-risk skips. All 18 blocked candidates matched standalone fills; 12 were winners, 9 of those had at least one nonpositive incumbent and 6 had a negative incumbent-result sum.
- Win-probability and conservative-R reservation lost annual and H2 stressed net. Overlap-aware reservation improved stressed net in H1, H2 and full year, including full-year `+$8.9660`, but worsened H2 DD by `$2.8540` and full-year DD by `$0.6210`; it therefore failed the predeclared risk gate. No candidate passed.
- Closed the family `NO_POLICY_PASSED_RETAIN_FIRST_COME`. Per the fixed stop rule, did not run or inspect 2025 forward, 2026 confirmation or the latest two completed months and did not attempt threshold, mixture or preemption rescue. Future-aware oracle remains diagnostic only.
- Human conclusion is `docs/lineage/STRATEGY_INDEPENDENCE_AND_RISK_ALLOCATION.md`; machine selection and closure are `lab/evidence/STRATEGY_INDEPENDENCE_RISK_ALLOCATION_SELECTION_V1.json` SHA-256 `630C0F37F7BFA67AF139B9919E518F7E5CE370C749E6E957851CEC7FB0C1D700` and `lab/evidence/STRATEGY_INDEPENDENCE_RISK_ALLOCATION_CLOSURE_V1.json` SHA-256 `637DEF903CB17F3D698E882E16A39F0820C8F0BC879AD821B1B0CC24AB758EDA`. Live V7 PID `10112`, dashboard PID `24936`, Live EA, Include, EX5, SET and state remain unchanged.

## STATE-0017 - 2026-08-24

- By explicit user direction, opened one new serial Lab family named `예치자본·위험용량 연구`. It asks whether `$200/$300` deposits should remain reserve cash, scale initial lots and risk dollars, broaden the 12% envelope across more strategies, limit symbol concentration or reduce new-entry tranches after drawdown.
- Froze the hypotheses before new analysis in `lab/evidence/DEPOSIT_CAPITAL_RISK_CAPACITY_DECLARATION_V1.json`. The proxy is not a parameter grid: each branch has one economic premise and one fixed contract. It consumes only already-opened fresh-`$100` 2024 combined and standalone ledgers.
- Fixed the EA rule before proxy outcomes: implement mandatory `LINEAR_CAPITAL`, the highest-ranked capacity hypothesis and the highest-ranked sizing-governor hypothesis; use a diagnostic fallback if a group has no proxy-eligible member. Candidate-specific selection starts fresh in 2025 at declared `$100/$200/$300` deposits.
- Conditional confirmation is only 2026-01-01 through 2026-06-01 after a 2025 pass. The latest completed 2026 June-July months and partial August are excluded from V1, and no post-outcome threshold or nearby policy rescue is allowed.
- Exact Live V7 PID `10112`, dashboard PID `24936`, Live source, Include, EX5, SET, state and order behavior remain unchanged. The new family is tester-only and grants no Live change or promotion authority.

## STATE-0018 - 2026-08-24

- Completed the predeclared 2024 proxy from 554 fresh shared-control lifecycles and 571 fresh standalone lifecycles, all at `0.01` volume. No 2025 or 2026 candidate outcome was consumed.
- Deposit-only reserve retained `+$54.6630` stressed dollars, diluting return to `27.3315%` at `$200` and `18.2210%` at `$300`. `LINEAR_CAPITAL` scaled the path to `+$109.3260` and `+$163.9890` while retaining `54.6630%` return and `17.7790%` closed DD.
- `BREADTH_DOLLAR_SLOTS` was the only capacity hypothesis to pass the proxy rule: it retained fixed `0.01`/about-`$4` trade risk, admitted all 571 standalone-observed lifecycles, produced conservative `+$62.6900`, and reduced `$200` DD to `7.5890%`, raising stressed net/DD from `3.0746` to `4.1303`.
- Four-slot 3% and six-slot 2% linear-stop hypotheses failed both halves and full-year conservative envelopes; symbol-bucket concentration also worsened efficiency and DD. Neither is eligible for an EA in V1.
- Neither sizing-governor passed. Per the predeclared diagnostic fallback, `FIXED_LOT_LADDER` outranked the 6% drawdown tranche brake and is frozen as the third EA path. At `$300`, its proxy changed 36 entries and returned `48.1792%` with `17.7896%` DD versus linear `54.6630%` / `17.7790%`.
- Frozen EA shortlist is exactly `LINEAR_CAPITAL`, `BREADTH_DOLLAR_SLOTS`, and diagnostic-only `FIXED_LOT_LADDER`. Proxy evidence SHA-256 is `C75A51F2B1AD12B092108595B9BAA8435AB4FFF444AEAFDA8E189A9FC400A894`; no post-result threshold, fourth EA or nearby rescue may be added.

## STATE-0019 - 2026-08-24

- Implemented exactly the frozen three Lab policy paths with separate Release, Portfolio, Magic `260824911..916`, `260824921..926`, `260824931..936`, state, event and lock paths. Every wrapper hard-fails outside MQL Tester.
- `LINEAR_CAPITAL` matches initial deposit/reference/base lot as `$100/0.01`, `$200/0.02`, `$300/0.03`, preserves 4%/12%, and scales the next volume step to 150% of starting deposit. `BREADTH_DOLLAR_SLOTS` retains `0.01` and `$4` position risk while 12% of `$200/$300` funds more concurrent risk capacity. `FIXED_LOT_LADDER` starts `0.02/0.03` and adds exactly `0.01` per additional `$150` stressed profit.
- Reused the frozen V7 signal, evaluation time, direction, order, protection search, cost, hold/exit, RC4 and SIRA observation lifecycle. The only changed seams are declared capital/volume/risk sizing and bounded research margin/sizing telemetry.
- All three EAs compiled with Lab MetaEditor build 6140 at `0 errors / 0 warnings`. EX5 SHA-256 values are linear `5FB498A5BC0344F9EA270DD9850BEE73DB6DC25A3B7B4B170945CB8A1D4F1376`, breadth `31A98366177062D74B409BB81B7DAFB9BF526C6F3B5BE415D60404EE0A1FA14B`, ladder `F3496145E31779B67B04FED3223359EE0612F3F2A0BF10A0B64A4E8C6495C6C5`.
- Froze ten 2025 real-tick configurations before opening selection: deposit-only control at `$100/$200/$300`, linear at `$100/$200/$300`, breadth at `$200/$300`, and ladder at `$200/$300`. Compile/preselection receipt SHA-256 is `2CED8C9FFB0DBB6BD1CDB3F97E1BD43591736FAD7D5DF1E70DE2694DCE8221C9`.
- No 2025 candidate result or 2026 data was consumed at this boundary. Exact Live V7 PID `10112`, dashboard PID `24936`, Live source, Include, EX5, SET, state and order behavior remain unchanged.

## STATE-0020 - 2026-08-24

- Completed the ten predeclared serial fresh-account 2025 MT5 build 6140 `100% 실제 틱` selection runs: deposit-only `$100/$200/$300`, linear `$100/$200/$300`, breadth `$200/$300`, and diagnostic ladder `$200/$300`. Every run had continuous opportunity IDs, one normal STOP, complete report artifacts, exact report/ledger net, DD, trade and deal agreement, and zero safety, persistence, broker-identity, foreign-exposure, protection, minimum-lot or margin/calculation fault.
- Deposit-only `.01` stress net was `+$113.0680` at `$100` and `+$113.2520` at both `$200/$300`. Extra account cash reduced hard risk skips `25 → 16` and DD percentage `28.3905% → 14.2353% → 9.4902%`, but changed stressed dollars by only `+$0.184`; returns diluted to `56.6260%` and `37.7507%`.
- `LINEAR_CAPITAL` matched the `$100` control exactly after diagnostic sizing-event normalization and passed the 0.50 percentage-point scale gate. `.01/.02/.03` produced stressed net `+$113.0680/+$226.1060/+$338.9840`, return `113.0680%/113.0530%/112.9947%`, and DD `28.3905%/28.3555%/28.3605%`. It proves consistent dollar scaling, not improved edge, percentage growth, drawdown or efficiency.
- `BREADTH_DOLLAR_SLOTS` eliminated all risk-admission skips, raised maximum concurrency from three to four and added profitable lifecycles, but shared lifecycle path deterioration outweighed them. It returned `43.1630%/23.3380%` with net/DD `3.1344/2.5990` at `$200/$300`, failing both-deposit efficiency and 90% linear-return floors.
- Diagnostic `FIXED_LOT_LADDER` beat linear by only `+$3.8840` at `$200` with unchanged DD, then underperformed linear by `-$89.2115` at `$300` and raised DD by `7.2498%p`. It failed the `$300` return, efficiency and risk gates and remained nonselectable.
- Closed `예치자본·위험용량 연구` V1 as `NO_NON_CONTROL_POLICY_PASSED_CLOSE_RETAIN_FROZEN_V7`. Per the frozen stop rule, did not open any 2026 confirmation/latest period, threshold rescue, formula mixture or fourth EA. Selection SHA-256 is `39ADE4BB8EDC1264F313BEACDE88BA3202678263FB4606C057AA0A83CA54C1B4`; closure SHA-256 is `56B64F0592AA152C88A2038C58E679F70345205EB3A4682E8BED8435F54E7452`.
- Human conclusion is `docs/lineage/DEPOSIT_CAPITAL_AND_RISK_CAPACITY.md`. Exact Live V7 PID `10112`, dashboard PID `24936`, Live source, Include, EX5, SET, state and order behavior remained unchanged; the result grants no Live or promotion authority.

## STATE-0021 - 2026-08-25

- By explicit user instruction, implemented only Checkpoint 1 of the supplied complexity-refactor work order and stopped before Checkpoint 2. No research hypothesis, economic candidate, Live change or promotion path opened.
- Derived `lab/engineering/complexity-refactor-v1/mt5/` from frozen Git commit `75bd9c9` with tester-only release `NEXT-LAB-CXR1-ENTRY-GATE`, portfolio `ZT-PORT-NEXT-LAB-CXR1-ENTRY-GATE`, Magic `260825100..260825105`, independent state/event/snapshot/lock paths and `lab/runtime/complexity-refactor-v1-portable/`.
- Split the eight-path shared market-entry gate into read-only `EvaluateEntryGate`, side-effect-owning `ApplyEntryGateResult`, and existing-persistence-backed `CommitOpportunityConsumption`. Changed only `ZetaStrategyShared.mqh` and the RC16, `ProcessRC4Both`, Pressure, Return and Cross call sites; signal math, `OpenComponent`, risk, margin, state schema, Passive and RC4 management remained frozen.
- The identity-isolated frozen control and CP1 both compiled on MetaEditor build 6140 at `0 errors / 0 warnings`; baseline/CP1 EX5 SHA-256 values are `7689706F22930B1054F5D6D07FA317B1E7C419F211E90E9096048FE5881096A7` and `7CDB41D96A88F9C46F951CFF979250B3283CF2507D087B9AF94AACC75429CEF8`.
- Fresh same-runtime Latest control/CP1 runs matched 84 lifecycles, final `$98.89`, stressed `-$2.819`, final order/deal `178/169`, and all 411 report rows. Binding control/CP1 matched 2,234 lifecycles, final `$1,242.00`, stressed `+$1,058.630`, final order/deal `4581/4469`, and all 9,114 report rows.
- State A/B, current snapshot A/B and ownership lock hashes matched in both windows. Each event comparison had one raw `deal_wait_ms 0↔15` difference and zero differences after the pre-existing wall-clock diagnostic normalization.
- Fresh Latest reproduced the immutable frozen V7 result. Fresh Binding did not reproduce the 2026-08-24 frozen report and first diverged at 2023-04-10 protection prices despite non-identity source equality. This was recorded as a current tester replay boundary; no broader environment or economic investigation opened, and CP1 was judged only against its immediately adjacent same-runtime control.
- Evidence is `lab/evidence/COMPLEXITY_REFACTOR_ENTRY_GATE_CP1_V1.json`. Exact Live V7 PID `10112`, dashboard PID `24936`, Live source, package, EX5, SET, state and order behavior remained unchanged. Checkpoint 2 is not open; next is `none_opened_waiting_for_user`.
