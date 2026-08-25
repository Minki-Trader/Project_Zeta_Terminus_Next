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

## STATE-0022 - 2026-08-25

- By explicit user instruction, opened Complexity Refactor V1 Checkpoint 2 and conditionally evaluated Checkpoint 3 only if CP2 demonstrated additional value. The work remained one serial tester-only engineering stream rooted at durable CP1 commit `5393fed733835a3d50e285c1e9fadfcbf621d149`.
- Split the market-open transaction in the isolated candidate's `ZetaOrders.mqh` into `BuildMarketEntryPlan`, `PersistMarketEntryIntent`, `SubmitMarketEntry`, `ObserveMarketEntry`, `SeedProvisionalMarketLifecycle`, `ValidateMarketEntry`, `AdoptMarketEntry`, and `FinalizeMarketEntry`. The public `OpenComponent()` signature, all five strategy call sites, strategy/risk/margin math, persistence and journal schemas, broker call count, Passive, close/cancel, and RC4 behavior remained unchanged.
- `OpenComponent()` decreased from 348 to 38 lines, 18 to 6 direct branches, 13 to zero direct CTrade calls, and zero direct save, event, decision-intent, journal-writer or `trade_operation_active` writes. Local plan/receipt/observation/outcome types remain inside `ZetaOrders.mqh` and are not durable Domain state.
- MetaEditor build 6140 compiled CP2 at `0 errors / 0 warnings`; CP2 EX5 SHA-256 is `B0627195DC38F07B65B6E84699DF10E0D2A83A3EE82991FEAA289608404E5BA3`.
- Fresh CP2 Latest matched CP1 at 84 first fills, final `$98.89`, stressed `-$2.819`, all 411 report rows, all five state/current/lock hashes and all four graph hashes. Fresh CP2 Binding matched CP1 at 2,234 first fills, final `$1,242.00`, stressed `+$1,058.630`, all 9,114 report rows and the same state/graph hashes.
- Latest 652 and Binding 4,149 event rows differed only in one existing `deal_wait_ms 15↔0` wall-clock field each and normalized to zero. All 417 Binding market `OPEN` rows retained exact `SIGNAL_DECIDED → ORDER_ATTEMPTED → BROKER_STATE_ADOPTED → OPEN → DECISION_JOURNAL_FINAL` ordering.
- Rare broker, identity, protection, persistence-failure and process-termination paths were not induced or claimed as observed. Source review confirms no new durable state or restart window and preserves the original no-replay, reconstruction, safety-stop and protective-close ordering.
- All four CP2 Gate questions passed. CP3 was held without source changes as `CP3_HOLD_CP2_SUFFICIENT_NO_ADDITIONAL_VALUE`: CP1+CP2 already satisfy every permitted writer boundary, and a new broker file would add a file/include without reducing writers while risking the durable-intent order. Passive and RC4 follow-up work was not opened.
- Evidence is `lab/evidence/COMPLEXITY_REFACTOR_MARKET_ENTRY_CP2_V1.json`. Exact Live V7 PID `10112`, dashboard PID `24936`, Live source/package/EX5/SET/state and moving `lab/mt5` remained unchanged; no new research or economic hypothesis opened.

## STATE-0023 - 2026-08-25

- By explicit user instruction, opened only the Live promotion of already-verified Complexity Refactor CP1 and CP2 plus mandatory source-topology governance. No CP3 change, Passive/RC4 follow-up, economic hypothesis or new research family opened.
- Made `docs/OPERATING_DIRECTION.md` and `AGENTS.md` enforce one frozen forward Lab baseline, isolated family roots, no cross-root Includes, immutable closed families and no future MQL additions under historical mixed `lab/mt5/`. The sole forward baseline is frozen CP2 root `lab/engineering/complexity-refactor-v1/mt5/` at commit `9d1cbeeea232eec1e574dc7e4e3b0e65adf412b5`.
- At a fresh local snapshot with server `2026.08.25 09:15:01`, positions/order/margin/planned risk `0/0/$0/$0`, balance/equity `$106.52/$106.52`, project realized net `$5.87`, no RC4/Passive pending ownership and zero faults, stopped parent V7 PID `10112` normally before the first decision interval. Dashboard PID `24936` also stopped.
- Promoted exactly seven implementation files byte-equal to the CP2 candidate into a new frozen package release `NEXT-E01-V7-CXR1-c0ad2f30d293`. Parent execution version, Portfolio `ZT-PORT-NEXT-V7-2db5ef5ead1c`, Magic `260824701..260824706`, state marker/schema/paths, economic SET and all non-CP implementation files remain unchanged.
- Canonical source/settings SHA-256 is `C0AD2F30D293AD538A91DE74A6D0A14A560FA19222F1DB043E1C533C103A7DD7`. Isolated MetaEditor build 6140 compiled at `0 errors / 0 warnings`; EX5 SHA-256 is `F0B7D64BE36F81304C8764A89DFFA2499CD5F4ACED73A7A1837F950EFECC919F`.
- Replaced the misleading copied `LAB_CANDIDATE_MANIFEST.json` in the Live package with exact `SOURCE_MANIFEST.json`, retained one `RELEASE_MANIFEST.json`, and pinned the stopped-flat parent continuity in a Git-ignored release-transition receipt. No terminal currently owns the account; target entries remain disabled until committed entries-disabled recovery passes.

## STATE-0024 - 2026-08-25

- At committed and pushed Git `9f30ce783f8d42411597ca2946e50a1c223f4b72`, exact CP1+CP2 release `NEXT-E01-V7-CXR1-c0ad2f30d293` passed connected entries-disabled state recovery twice with no Lab link and new entries blocked by both input and terminal mode.
- Run 1 PID `28168` recovered parent state at sequence `1463`; release, execution, Portfolio, Magic, account, source/EX5/SET manifests, flat exposure and `$5.87/$105.87/$101.49` realized/stage/stressed continuity all matched. It stopped normally.
- Run 2 PID `17656` resumed the saved target state and advanced through sequence `1465`. It retained entries `0/0`, positions/order/margin/planned risk `0/0/$0/$0`, balance/equity `$106.52/$106.52`, zero safety/persistence/broker/foreign faults and no warning or alert, then stopped normally.
- Target-release events contain exact `RESUME entries-disabled → STOP normal → RESUME entries-disabled` continuity. The same execution/Portfolio/Magic/state namespace was continued deliberately; no position, broker history, state schema or economic input was converted.
- Entries-disabled recovery and restart are `PASSED`. The user's explicit CP1+CP2 Live direction is now effective, but the only permitted next action is the committed operator's final exact `0/0` preflight followed by `1/1` handshake. No terminal currently owns the account.

## STATE-0025 - 2026-08-25

- The first final invocation passed exact target `0/0` preflight at PID `4132` but stopped before any `1/1` start when Windows briefly reported the just-closed preflight PID as still present. The operator failed closed; subsequent process and local snapshot inspection proved terminal count zero, entries `0/0`, flat exposure and state sequence `1466`.
- Added only a bounded five-second post-preflight process-exit wait to `Start-ZetaNextV7Live.ps1`, committed and pushed as `51078aeb7656107b9c3147bc2163810a842fadea`. No EA, source package, SET economics, state or authorization changed.
- The repeated exact `0/0` preflight PID `26112` passed release `NEXT-E01-V7-CXR1-c0ad2f30d293`, Portfolio `ZT-PORT-NEXT-V7-2db5ef5ead1c`, Magic, account, flat exposure, zero margin/risk and continuity, then stopped normally.
- Exact target `1/1` Live PID `21548` passed the committed handshake. The Master recognized that sole terminal without duplication, restored its MT5 window and opened the sole Korean dashboard PID `4712`.
- Bounded stabilization advanced to sequence `1470` at server `2026.08.25 09:35:11`. Entries remained `1/1`; positions/order/margin/planned risk were `0/0/$0/$0`; balance/equity were `$106.52/$106.52`; project realized/stage/stressed values remained `$5.87/$105.87/$101.49`; all ownership, safety, persistence, broker and foreign-exposure faults were zero with no alert or warning.
- Classified `CXR1_LIVE_PROMOTION_COMPLETE; CXR1_SOLE_OWNER_HEALTHY; SOURCE_TOPOLOGY_GUARD_ACTIVE`. Parent V7 and legacy must not restart. The CP2 Lab root and active Live package are frozen, and no new engineering or research family is open.

## STATE-0026 - 2026-08-25

- Corrected only operational and machine metadata; no MQL, EX5, SET, package, runtime, state payload, process, order or Live authority changed.
- Appended a closure clarification to `lab/frontier/ledger.jsonl`: the configured 2025-01-01 through 2026-08-24 Frontier path, including completed 2026 June-July and partial August through the last observed 2026-08-21 trading date, is consumed exploratory evidence and is not a clean holdout, confirmation or promotion basis. The Frontier remains closed with `promotion=none` and `none_opened_waiting_for_user`.
- Extended machine executable `core_line` through the already-existing active `NEXT-E01/V7-CXR1` node and removed the stale no-Live-change family sentence from current active work. Exact CXR1 remains the unchanged sole healthy Live owner.

## STATE-0027 - 2026-08-25

- By explicit user direction, performed a read-only forensic review of actual V1 through V7 Live-Dev performance, simultaneous US30/US100 exposure and locally evidenced terminal/chart interruptions. Opened no exit-policy hypothesis and made no Live, MQL, EA, Adapter, settings, state or runtime change.
- Reconstructed 14 completed real-account lifecycles through server `2026-08-24 21:59:59`: project-stage balance `$100.00 → $105.87`, project realized net `+$5.87`, 9 wins / 5 losses, gross `+$10.78/-$4.91`, profit factor `2.195519`. The broker balance is `$106.52` because the account carried a prior `$0.65` adjustment.
- Separated the V1 entry-deal publication-race close and V2 stale/zero-result-price protection close, totaling `-$0.08`, from 12 economic lifecycles that produced `+$5.95` with 9 wins / 3 losses. V6/V6R2/V6R6 produced no completed real lifecycle.
- Replayed the 12 economic position paths from isolated Lab US30/US100 ticks using executable-side marks. Every economic loser had crossed positive first; the three losses gave back `$3.8435/$1.6340/$2.6615`, totaling `$8.1390` or 69.7998% of all `$11.6605` measured MFE-to-final giveback.
- Confirmed the user's concurrency observation. The 2026-08-20 `SELL/BUY/BUY` triple had all legs positive for 71.3687% of its overlap and peaked at `+$3.3585`. The 2026-08-24 `BUY/BUY/SELL` triple had all legs positive for 94.6766%, recorded exact account equity `$108.69` at third entry and reached a hindsight tick-equity proxy of `$109.7725`.
- The user's manual-close estimate is materially plausible but not an exact strategy result. `$108.69` is causally recorded, `$109.77` is a V7 hindsight ceiling, and applying two event-observable close-all snapshots while assuming unchanged later signals gives a path-dependent `$109.83` proxy. The `$111` upper edge is not directly established.
- The local interruptions did not reduce realized P/L over the reconstructed interval. The 2026-08-19 V3-to-V5 gap missed one Cross short whose preserved continuous path would have timed out at about `-$0.53`; the 2026-08-21 unavailable decision interval had no RC4, RC16 or Passive threshold-qualified entry; the later interruption was during the weekend.
- Closed the descriptive family at `lab/research/live-dev-performance-forensics/` as `CLOSE_WITHOUT_NEW_HYPOTHESIS`. Machine evidence is `evidence/LIVE_DEV_PERFORMANCE_FORENSICS_V1.json`, SHA-256 `26E059C33F952E4FB2921101B9295921021828C13282E8C876B54DE36054B52F`. Exact CXR1 Live owner remains unchanged; next is `none_opened_waiting_for_user`.

## STATE-0028 - 2026-08-25

- By explicit user direction, opened one new serial Tester-only Lab family, `동시수익 보존·청산조정 연구` at `lab/research/portfolio-exit-coordination-v1/`. It uses the closed Live performance forensics only as motivation and opens no Live change or promotion authority.
- Before implementation or outcome consumption, froze exactly four paths: inert frozen-CP2 control; positive-aggregate cohort close at the first frozen natural exit; zero-dollar group floor after every member has been positive; and a 0.25 summed-risk activation with a 50% combined-peak trail after every member is positive. No hybrid, strategy/symbol/time exception or threshold rescue is allowed.
- Froze four fresh `$100` actual-tick periods: 2022-08-01 through 2023, calendar 2024, calendar 2025, and 2026-01-01 through 2026-08-21. The matrix is exactly 16 serial runs with unchanged V7 entry, sizing, protection, admission, session-clock and solo-exit economics.
- All historical paths are already consumed exploratory evidence. Even a passing path may be named only `EXPLORATORY_CANDIDATE_ONLY`; V1 cannot claim a clean holdout, confirmation or Live suitability. The fixed gate requires operational integrity, at least 20 triggers, broad actual/stressed-net improvement, higher pooled stressed net by max(`$5`, 5%), and non-worse pooled/period drawdown.
- Declaration is `lab/research/portfolio-exit-coordination-v1/evidence/PORTFOLIO_EXIT_COORDINATION_DECLARATION_V1.json`, SHA-256 `94906550F35998C0A9D59021404E6B671A4B7F46A6CC8B42979DDB6801B089C2`. Parent is the one-time-copy-only frozen CP2 root at commit `9d1cbeeea232eec1e574dc7e4e3b0e65adf412b5`, tree `7dbd1e0999a3921ab0f2601ff90ebe12f0f2c4ff`; outcomes consumed remains false. Exact CXR1 Live PID `21548`, source, package, SET, state and order behavior remain unchanged.

## STATE-0029 - 2026-08-25

- Implemented exactly the four predeclared PEC V1 Tester-only paths in the self-contained `lab/research/portfolio-exit-coordination-v1/mt5/` root. The family owns 20 MQL source files, one SET, 16 fixed period INIs and a dedicated Git-ignored Portable with copied Lab US30/US100/US500 market data; it has no Live or other-family Include/link.
- Eleven frozen parent Include modules remain byte-equal. Only the family-owned Domain identity/path declarations, fixed/Passive natural-close calls and one new coordination module/assembly differ. Entry signals, timing, market/passive order construction, stops, risk admission, sizing, session clock, reconciliation and original solo exits remain frozen.
- All four entrypoints compiled on MetaEditor build 6140 at `0 errors / 0 warnings`. EX5 SHA-256 values are control `B9F255A0356E8BC8183E451879EC0291FB217A800DF1F116F20DFBBC365F3C1E`, first-natural-exit `0967B54BE8F8333B9033CE6E06DF233CAD67FA4895A3DEE8A3DC007E7B019954`, zero-floor `78F7CDF2F797BE0947599C41B0EFA4A559FF23D5A55A6E4F6A46549E521362C5`, and quarter-R/half-peak `8A7B49005C74E0F7830FA198A53F5556349B6E8FF278AE24154A99E8ACE017E3`.
- Source/config aggregate SHA-256 values are `3F5DABD3EF52D9F35BE3178FFD13DCC19D87B9502957A8EEFDDD8C87C9380000` and `9DCDA371538636C3BE7620CAD7DAB8FA7CD931652A9297506E3F3C357755CD75`. Compile receipt is `lab/research/portfolio-exit-coordination-v1/evidence/PORTFOLIO_EXIT_COORDINATION_COMPILE_RECEIPT_V1.json`, SHA-256 `E96917319AAECD005422161E86F4221CD7007F37F5CDF0D647A45A485B3173F3`; no backtest outcome has been opened.
- The next and only allowed action is the 16 frozen serial real-tick configurations. Exact CXR1 Live PID `21548`, source, package, SET, state and order behavior remain unchanged.

## STATE-0030 - 2026-08-25

- Completed exactly the 16 predeclared serial fresh-`$100` build-6140 real-tick configurations for `portfolio-exit-coordination-v1`. Every report used 100% real ticks and ended normally; report net/trade/deal totals reconciled to final snapshot/component evidence, all requested coordination closes succeeded, and all safety, persistence, broker, foreign, protection and coordination-close faults were zero.
- Pooled control actual/stressed net and summed stressed closed DD were `$444.19/$407.0477/$96.1393`. First-natural-exit was `$343.93/$306.8285/$88.3285`, zero-floor `$319.62/$280.6710/$80.8470`, and quarter-R/half-peak `$424.74/$387.2135/$93.6940`.
- The motivating 2026-08-20 overlap was reproduced causally: first-natural-exit closed the three-position cohort at `+$2.89` gross versus the control cohort's eventual `+$0.84`. Across the frozen matrix, however, its 394 triggers lost `$100.2192` stressed net versus control. The episode is real, but the fixed rule is an economically harmful generalization.
- No candidate passed pooled stressed-net improvement or three-of-four actual/stressed breadth; every candidate had lower stressed-net/DD efficiency than control. Zero-floor also failed the P1 115%-of-control period-DD limit. Quarter-R/half-peak was least bad but won only 2024 and remained `$19.8342` stressed net below control overall.
- Selection is `lab/research/portfolio-exit-coordination-v1/evidence/PORTFOLIO_EXIT_COORDINATION_SELECTION_V1.json`, SHA-256 `991FBCB8CE3B81EA14C0FC04EDF5B75B4E9BE5E7523835B8D4EE3938A7A3F88A`; closure is `PORTFOLIO_EXIT_COORDINATION_CLOSURE_V1.json`, SHA-256 `C6BA432F8CFC8E5A55E470843A63FA6675C20F6F4AA6B260004A8E2FBBB1B3EE`.
- Closed `NO_MECHANISM_PASSED_RETAIN_FROZEN_V7`. No seventeenth rescue path, hybrid, threshold/date/strategy exception or successor opened. Exact CXR1 Live PID `21548`, source, package, SET, state and order behavior remained unchanged; next is `none_opened_waiting_for_user`.

## STATE-0031 - 2026-08-25

- Under the user's autonomous-research direction, closed one read-only Lab family, `tester-replay-financing-drift-v1`, around the unresolved frozen-versus-fresh V7 Binding replay difference. It created no MQL, EA, Adapter, Tester path, economic candidate or Live authority.
- The two immutable Binding reports are equal through balance `$224.69`. Their first external economic difference is the same 2023-04-10 02:00 US30 sell close at `33578.90`, volume `0.01` and profit `+$1.02` receiving swap `+$0.40` in the 2026-08-24 replay and `$0.00` in the 2026-08-25 replay.
- That `$0.40` balance delta immediately changed the next same-entry US100 protection from `13488.99` to `13488.19`, then propagated through the balance-scaled 4%/12% risk system into a first stop execution-price difference on 2024-01-30, first ex-swap realized difference on 2024-02-13 and first lot difference on 2025-02-21. Matched financing line items differ by `$3.05`; final actual net differs by `$122.96` and first fills by one.
- Source economics and SET inputs remained frozen; the exact April 2023 US30/US100 ticks and 2023 bars are byte-identical with pre-run timestamps and equal full-period tick count. The latest no-swap window reproduced, while fresh baseline, CP1 and CP2 remained equal inside the same synchronized environment, so price-history change and unbounded nondeterminism are not supported.
- The FPMarkets symbol database was broker-refreshed at 2026-08-25 11:19 between the two Binding reports, and Tester logs synchronize symbol information separately from price history. The old specification blob was overwritten, preventing an exact old-rate field diff. Closed with high confidence as `CLOSE_CAUSE_BOUNDED_TO_TESTER_FINANCING_SPEC_DRIFT`; the earlier protection-price mismatch was a downstream symptom.
- Same-fingerprint within-family control/candidate judgments remain valid, but absolute historical profit is point-in-time contract evidence and unmatched cross-day reports cannot establish exact economic parity. `docs/OPERATING_DIRECTION.md` now requires before/after symbol database and required-symbol contract/swap fingerprints, adjacent controls and full-matrix rerun on mismatch.
- Machine evidence is `lab/research/tester-replay-financing-drift-v1/evidence/TESTER_REPLAY_FINANCING_DRIFT_V1.json`, SHA-256 `DDD639FB41C8F21EE95051B83089D74C6B01FB8DDA1F5563EC33A66F80481555`. Exact CXR1 Live PID `21548`, source, package, SET, state and order behavior remained unchanged; no successor is open.

## STATE-0032 - 2026-08-25

- Under the active Frontier Foundry Goal, opened and closed one source-free diagnostic family at `lab/research/strategy-frontier-coverage-v1/`. It used only the four already-consumed immutable control event paths from `portfolio-exit-coordination-v1` and created no MQL, EA, Adapter, Tester execution, new outcome data or Live authority.
- Before aggregation, froze the lifecycle pairing, occupied-hour metric, eligibility gates and lexicographic selection order. The corrected aggregation reconstructed every lifecycle with zero duplicate rows, unmatched starts/closes or negative durations; an initial in-memory PowerShell object-type defect was corrected before any economic verdict.
- RC16 pooled 272 lifecycles, `+$114.438` stressed net and `+$0.102661142` per occupied hour; RC4 pooled 206, `+$79.068` and `+$0.066366053`; Pressure pooled 118, `+$34.170` and `+$0.078680195`. Each was positive in all four periods.
- Closed `NO_UNDEREXAMINED_STRUCTURAL_SLOT_VALUE_TARGET`: none met the frozen two-negative-period plus nonpositive-pooled gate. RC4's 2026 YTD compression and Pressure's contemporaneous expansion remain only a pairwise US30 regime-rotation seed, not a single-strategy failure, mechanism, candidate or promotion verdict.
- Declaration and result SHA-256 values are `C97B6E6BB6634914034AEAC7D1FCF385B3AEA2848F6466406BED05466A7AEF56` and `2D84A35247B51C5B9329D4DA4BBE19EBB40772D1C715E0AAAE9BFFE4B169E8C2`. Exact CXR1 Live PID `21548`, source, package, SET, state and order behavior remained untouched; no successor is open at this durable boundary.

## STATE-0033 - 2026-08-25

- Opened and closed the source-free `us30-context-rotation-v1` Proxy around the only retained pairwise seed from STATE-0032. It used the same already-consumed immutable Next control events, no future information, no MQL, no Tester run and no Live surface.
- At each admitted 15:00 Pressure decision, context priority was an active RC4 lifecycle, otherwise an earlier same-server-day 13:00 RC4 signal, otherwise none. All 118 Pressure lifecycles reconstructed with zero unmatched lifecycle, planned-risk, duration, RC4-direction or context-conflict fault.
- Only 17 Pressure lifecycles had RC4 context. Discovery P1+P2 had aligned/opposed counts `2/1`; P3 had `6/3`; P4 had `3/2`. The fixed density gate required discovery `10/10` and each later slice `3/3`, so it failed before mechanism selection.
- Opposed context had the larger discovery, P3 and pooled mean stressed-R, but P4's aligned-minus-opposed effect reversed slightly to `+0.01392019R`. Closed `INSUFFICIENT_CONTEXT_DENSITY`; no Pressure maturity measurement, EA, threshold rescue, candidate or promotion path opened.
- Declaration and result SHA-256 values are `A3E25181D3898C840D9282D6AF8AB5EB1B664AC001388A5155B7084974E0591E` and `7E16BE35B0C8E989353D3AC9627729E2DB84AC56F9C76CD416C4EBAE0DBE6609`. Exact CXR1 Live PID `21548`, source, package, SET, state and order behavior remained untouched; no successor is open at this durable boundary.

## STATE-0034 - 2026-08-25

- Opened and closed the self-contained Tester-only `receiver-time-field-generalization-v1` family from a one-time frozen CP2 copy. It owns 19 MQL source files, one SET, 12 fixed INIs and a dedicated Portable; ten inherited Include modules remain byte-equal and there is no Live or cross-family source/settings/state/log dependency.
- Before outcomes, froze CONTROL, Return three-H1-bar contraction after causal expired-Passive decay qualification, and the paired Cross positive-at-four-H1-bar extension to six H1 bars. All three compiled on build 6140 at `0 errors / 0 warnings`; source/config hashes remained `40C8E920A643E268088470E9C84C826FF35FF15CB0852C111B9EDF583D317785` / `286683DA6CBC0E4910F0DA11799E706B7FDFF9A4F996606DADE13107BAC52129`.
- Completed exactly 12 serial fresh-`$100` 100%-real-tick runs across P1 2022H2-2023, P2 2024, P3 2025 and P4 2026 YTD. All ended normally; report and component totals reconciled and safety, persistence, broker, foreign, protection, close and 64-slot afterimage-capacity faults were zero.
- Pooled control actual/stressed net and summed stressed closed DD were `$444.19/$407.0477/$96.1393`. Return contraction was `$449.76/$412.6860/$95.1845`; the paired receiver field was `$453.86/$416.8158/$96.2400`. Required stressed improvement was `$20.352385`, versus observed `$5.6383/$9.7681`.
- Both candidates recorded 2,232 trades versus control 2,233. The exact miss was the 2022-10-07 17:00 Cross SELL: candidate path economics widened the 16:00 Return stop, so control released risk at 16:59:07 while candidates retained Return+Passive until 17:01:24 and incurred one extra risk-admission skip.
- The clean P3 implementation reproduced the retained 2025 Return/combined deltas within `$0.03/$0.02`, and samples were dense at 40 Return and 84 Cross admitted qualified lifecycles. The failure is temporal concentration and path interaction, not reconstruction error or sparse data.
- Closed `NO_MECHANISM_PASSED_RETAIN_FROZEN_CP2`; transition reserve consolidation was rejected and no Live change or promotion opened. Selection/closure SHA-256 values are `BC215AEAC86C53797E9D0E1C4E00637D06E86CA077F0171867526E7CCD32E3CC` / `A2843AB82E0626E14DBB9B6B63115A8FDEFAA7C71F689A516A92AECC641BC32A`. Only the unopened `censored_passive_refusal_depth` seed remains at this durable boundary.

## STATE-0035 - 2026-08-25

- Opened the single-stream Tester-only `passive-refusal-depth-observation-v1` family from a one-time frozen CP2 copy. It has independent source, identity, configuration and a dedicated Git-ignored Portable boundary; no closed family or Live source is included or linked.
- Before compile or outcome consumption, froze exactly four economically inert `$100` real-tick paths: P1 2022H2-2023, P2 2024, P3 2025 and P4 2026 YTD. No fifth, rescue, alternate horizon or threshold path is allowed.
- The observer samples only the latest causal US100 quote available on each US30 chart tick. For actually observed Passive expirations it records initial/minimum/final executable distance, depth approached, rebound and time-to-nearest, then attaches only the most recent strictly earlier same-direction emitter within 48 hours to native Return or Cross lifecycle stressed outcomes.
- Frozen primary tails are SHALLOW `<1/3` and DEEP `>=2/3` approach. Rebound, nearest-time and the middle bin are descriptive and cannot rescue a failed depth gate. This unit can at most justify one later entry-preserving selector experiment; it cannot modify economics or authorize Live.
- Before any outcome, the mandatory start/end contract-and-swap evidence calls were added and the source was re-frozen without economic change. Final pre-run source/config manifests are `0742692EF02E8494023EBCCE4FEF97D3E0C37A5EEB2C9510CFD8AADD61D49C8E` / `EE799B865127F6ED0C36C674BB77417FF5FC0EE176117DC05A7662DB12023A8E`; outcomes remain unopened. Exact CXR1 Live PID `21548`, source, package, settings, state and order behavior remain untouched.

## STATE-0036 - 2026-08-25

- The first P1 invocation synchronized the dedicated terminal's symbol database before EA START, changing its fingerprint from `83BD46...` to `1C7165...`. That otherwise equivalent outcome was preserved as an invalid environment preflight and excluded; source, config and binary remained frozen, and the declared four-run matrix restarted at P1 without adding an economic or rescue path.
- Completed exactly four valid serial fresh-`$100` 100%-real-tick paths. The symbols fingerprint remained `1C7165D6BD59F0A7A22BC009DFC822614E8B5CA220930036A0B33C785B2000CE`; all US30, US100 and US500 start/end contract rows matched. All runs stopped normally with zero safety, persistence, broker, foreign, protection, ownership or measurement fault.
- The inert observer reproduced frozen CP2 exactly: pooled actual/stressed net `$444.19/$407.0477`, 2,233 trades, 4,466 deals, 78 risk skips, 206 stop exits and 113 Passive expirations. All 238 Return and 805 Cross adopted lifecycles closed with one observation row; 29 Return and 84 Cross lifecycles matched a causal prior same-direction expiration.
- Return failed the fixed gate with only 7 pooled DEEP samples, Spearman `-0.076136509` and DEEP-minus-SHALLOW stressed mean `-$0.103339286`. Cross passed pooled Spearman `+0.217986452` and tail magnitude `+$0.507015610`, but period tail signs were positive only in P2/P3 and negative in P1/P4, failing the required three-period sign breadth.
- Closed `NO_DEPTH_SELECTOR_VALUE_RETAIN_FROZEN_CP2`. Rebound, nearest-time, MIDDLE-bin behavior, alternate thresholds and additional runs were not used as rescue. No selector or Live authority opened. Selection/closure SHA-256 values are `503FA898AC50E40F08359D595801D670BFF266B849CD64C18C736A67010B66FE` / `D716138FCBFE362105AFE125F25CF466F76ECF9317C90EF4EBF6D369E40EB50B`; exact CXR1 Live PID `21548` and all Live surfaces remained untouched.

## STATE-0037 - 2026-08-25

- Opened and closed the source-free `risk-capacity-release-window-v1` diagnostic over the six immutable valid event files from STATE-0036. It added no MQL, EA, Tester execution, new market outcome or Live authority.
- Before release-time aggregation, froze the exact recorded decision deadline, active-owner transition rules, overflow formula and density gate. A disclosed feasibility inspection had seen only candidate/blocker topology, not release latency or recoverability.
- The single aggregation exposed a declaration defect: `state_sequence` is a persisted-state version rather than an event primary key. There were 76 groups of distinct valid events sharing a sequence and server second, including ARC seal plus external close and cursor checkpoint plus close; zero groups were exact duplicate rows. The frozen uniqueness requirement therefore failed without evidence of data corruption.
- Because outcomes were open, the key was not corrected. The formal selection gate was not reached. A non-authoritative sensitivity that preserved all distinct rows found only 3 exact-deadline release proxies among 78 risk skips—Passive in P2/P4 and Cross in P3—versus frozen pooled/period/receiver minima `8`, `2 in 3 periods` and `6`.
- Closed `INVALID_EVENT_KEY_CONTRACT_NO_DEFERRED_ADMISSION_CANDIDATE`. No key-repair rerun, longer window, alternate overflow, retry EA or Live change opened. Declaration/result/closure SHA-256 values are `3D633073C863F1FB88930642A3FAE721C611DE4239B7D595524AC53094FD47DA` / `3AF7E7577F3321790663ADCC92840907BEAA09D0D613A1F7FDBEF64E0BB29986` / `3A10EFE6E7ED2FD34DF2B71E0FD2EDA4672D0D5FA0A33E4E1E32462B07C1EB3E`. Exact CXR1 Live PID `21548` and all Live surfaces remained untouched.

## STATE-0038 - 2026-08-25

- Opened and closed the source-free `native-signal-strength-value-v1` diagnostic over the same immutable four-period CP2 event matrix. It tested all six strategies with one fixed field, `abs(SIGNAL_DECIDED.value_a)`, against native stressed return divided by birth planned risk; no MQL, MT5 execution, new outcome or Live authority was added.
- Reconstructed exactly 2,233 lifecycles and `$407.0477` stressed net with zero exact duplicate, signal reuse/link, same-strategy overlap, planned-risk, fill, expiration or close fault. One read-only PowerShell invocation stopped on invalid filter syntax before producing a judgment; only that syntax was corrected and the single successful fixed aggregation was judged.
- All six passed the frozen sample floors but none reached absolute pooled Spearman `0.20`: RC16 `+0.087373013`, RC4 `-0.080628854`, Cross `+0.051826376`, Pressure `-0.156252853`, Return `-0.012432132`, Passive `+0.042462032`.
- Pressure had the largest absolute pooled association but reversed positive in P4 after negative P1-P3. RC16's pooled HIGH-minus-LOW difference was `+0.098904551R`, narrowly below `0.10R`, while its correlation remained only `+0.087373013` and its P4 tail reversed.
- Closed `NO_NATIVE_STRENGTH_FIELD_PASSED`. No signed/margin feature, nonlinear or ML transform, alternate tertile, direction/period split, sizing/allocation candidate or Live change opened. Declaration/result/closure SHA-256 values are `59E9DD06450DDE32FDAC7C2DA0A13D064908F00782C8F94111DB81D66E74E4AC` / `E87F0CF00A4673FFEC6D6F783F118D8A0974BA111C86B62EEE413C92B6009E27` / `4E8B28B29F78FDE0C8ED6B0E32B575B35F1C73F4CAD4D64A2D32E0685B1FE62A`. Exact CXR1 Live PID `21548` and all Live surfaces remained untouched.

## STATE-0039 - 2026-08-25

- Opened and closed the source-free `entry-time-crowding-value-v1` diagnostic over the immutable four-period CP2 event matrix. It classified every admitted entry as SOLO or CROWDED using only the active position count immediately before that ordered birth event; pending orders, identities, directions and later outcomes were excluded from the field.
- All 2,233 lifecycles, `$407.0477` stressed net and 206 stop-loss exits reconstructed with zero duplicate, signal, overlap, risk, fill, expiration, close or incumbent-count fault. One initial read-only invocation stopped on invalid duplicate-filter syntax before any metric or judgment; only that syntax was corrected.
- RC16, Cross, Pressure, Return and Passive passed group density, but their largest absolute pooled stressed-R and stop-rate effects were only `0.046802089R` and `0.067355641`, below the fixed `0.10R/0.10` requirements.
- RC4's CROWDED-minus-SOLO observation was `+0.227281851R` with stop-rate effect `-0.133682373`, but CROWDED had only 15 lifecycles and only P1 had at least five. It failed the pooled 20 and three-period density requirements before economic selection.
- Closed `NO_ENTRY_TIME_CROWDING_FIELD_PASSED`. No incumbent identity/direction, two-plus threshold, exact cohort, symbol, pending, time/period subgroup, management candidate or Live change opened. Declaration/result/closure SHA-256 values are `5983F8925F7DB4FEC4AB70E41DACDABD04A3AF447C739C1E202D1B1C69038C97` / `E27397FBD0D40BCA98D117394FE395E63AFABC3EAC24934B0166ADA3C6EE0E54` / `0B233FB0E23E049935A347EEB7D302C449E4F734FDD7DFB3BA537286A592B34F`. Exact CXR1 Live PID `21548` and all Live surfaces remained untouched.

## STATE-0040 - 2026-08-25

- Opened and closed the source-free `server-day-carry-burden-v1` diagnostic over the immutable four-period CP2 event matrix. It classified native lifecycles only by whether close server date equaled or exceeded entry server date; no MQL, MT5 run, new outcome or Live authority was added.
- Reconstructed all 2,233 lifecycles, `$407.0477` stressed net and 206 stop exits with zero duplicate, pairing, overlap, risk or time fault. Exactly 2,230 lifecycles, or 99.8657%, closed on their entry server date.
- Cross, Pressure, Return and Passive had no carried lifecycle. RC16 had one three-day carry in P1 at `+0.115226243R`. RC4 had one one-day carry in P3 and one three-day carry in P4, averaging `-0.312586177R` versus `+0.068855545R` for its 204 same-day lifecycles.
- Every strategy failed the frozen pooled 20 and three-period density gates. Both RC4 carry losses ended by `DEAL_REASON_EXPERT`, so carry stop incidence was zero versus 25.9804% same-day and the required higher-stop burden pointed the opposite way.
- Closed `NO_SERVER_DAY_CARRY_BURDEN_FIELD_PASSED`. Server-date crossing does not represent the motivating overnight-like giveback in this evidence, but local-day, rollover, weekday, multi-day, swap, direction and symbol variants were not opened as rescue. Declaration/result/closure SHA-256 values are `D5AEEA8A48B4F62A6418B8BF87C58312C898E1F2E1A308CCF80C8FB9B794747E` / `1C80CEFCAB293B61AED77CEFE415AE4A34826E22032B1E91F264849A210B1EE5` / `A0FFB92619E7AF4F40E1E8E7EE5F5F750080BED76FAC44CB45088FEFCB7CBF2F`. Exact CXR1 Live PID `21548` and all Live surfaces remained untouched.

## STATE-0041 - 2026-08-26

- The active CXR1 Live owner latched `SAFETY_STOP` at server `2026.08.25 16:32:01` with `owned pending order on mismatched component`. Terminal evidence shows Pressure's saved SL created current market close order `246921084`, which became stop-loss deal `231614197` milliseconds later. The owner audit incorrectly treated every owned non-Passive current order as an impossible pending order.
- The post-close local snapshot remained flat at positions/order/margin/planned risk `0/0/$0/$0`, but flags stayed safety/broker `1/1` and entries `1/0`. The later server-17:00 Cross component was not evaluated; no late replacement order is authorized after its two-minute deadline.
- Under the user's explicit repair direction, derived the independent `lab/engineering/protective-exit-order-reconciliation-v1/` family once from the frozen CP2 baseline. Its sole behavioral change recognizes only a selected market BUY/SELL with exact component Magic/symbol, `ORDER_REASON_SL`, opposite direction, exact volume, active local lifecycle and zero-or-matching position identifier. Every other current-order mismatch remains fail-closed.
- Dedicated build-6140 MetaEditor compiled at `0 errors / 0 warnings`. The only frozen fresh-`$100` P4 2026 YTD 100%-real-tick path matched CP2 exactly at actual/stressed net `+$96.30/+$90.4732`, 356 trades, 712 deals, 14 risk skips, 42 stop exits and `$31.1908` stressed closed DD; all safety, persistence, broker, foreign, ownership and protection faults were zero.
- The candidate is source/config/binary frozen and approved for a controlled flat Live promotion, not yet applied. Declaration/compile/result SHA-256 values are `16A5428E6E587716E2DF3D512C0D0CFCCD38B5AF672DB1492CA33ECA3EB18B10` / `0C520F6AC64015885AED55BABFA669F5C277C971D7DF2FB896D125C9C267BA01` / `9D8455E83386FCA309DA9AC0677C8BF2BD134A0CE50CD4AC264B93F1BD1FCA43`. Existing Live PID `21548` remains the sole safety-stopped flat owner pending the committed release transition.

## STATE-0042 - 2026-08-26

- Pushed the frozen Lab candidate at commit `0d4032786cecb7d7e8a4c3074609db5b105fa107`, then re-proved CXR1 PID `21548` at server `2026.08.25 18:12:03` with entries `1/0`, positions/order/margin/planned risk `0/0/$0/$0`, and retry/shadow/ARC ownership all zero. The committed flat-stop operator stopped it normally; no late replacement was created for the expired Cross window.
- Backed up all five stopped runtime files. In each redundant state snapshot, changed only CSV field index 18 `safety_stopped` from byte `1` to `0`: A `1460B882... → C0FA88E8...`, B `0D9C1C4E... → 74D33765...`; each file had exactly one changed byte, while current A/B and the event file remained hash-identical. `broker_mismatch` is runtime-only and was not edited.
- Promoted only candidate `ZetaOwnership.mqh`, byte-equal at `0D4C619B3251F9E99113883108BF3E15A5C2E50B2EA436A9BB2BE8EA6919049A`, plus release identity into `NEXT-E01-V7-CXR2-14d84b9e4bb3`. Execution, economic version, Portfolio, Magic, state marker/schema/path, main MQ5 and base SET are unchanged. Canonical source/settings SHA-256 is `14D84B9E4BB30A4CBCCE51B4841859912FEE9BDC1E7FCFFEFEE228C55823C072`.
- The first Live compile setup lacked MetaQuotes standard `Trade.mqh` and failed before code generation; restored the CXR1 EX5 backup, copied only the vendor Include library into the independent Live Portable, and compiled again using exclusively the Live package Zeta tree. The successful build-6140 log is `0 errors / 0 warnings`; CXR2 EX5 is `620D0351AF22EAA389BE7F36CBD3AB6C9D2204D182E897CFE6A845495428CFC6`, and source manifest is `DD2F9693015034E442B26D3B1831BB59A0C8BB83C5F06CA7BF51648235186980`.
- Local transition receipt SHA-256 is `FB8FBB5C491B8170FA1449F2BDC19B90EB0B023F1695A54A77A9DAD5EB4AB954`. No terminal or dashboard now owns the account. New entries remain disabled until the committed CXR2 package passes the connected `0/0` recovery.

## STATE-0043 - 2026-08-26

- At committed and pushed Git `3fc500f06e7a0a711cb2f2ddb34eff60fcc58536`, the operator revalidated the CXR2 source manifest, EX5, SET, Git boundary and local transition receipt before starting any terminal.
- Entries-disabled PID `21944` recovered exact release `NEXT-E01-V7-CXR2-14d84b9e4bb3`, Portfolio, Magic and account at sequence `2006`. It proved entries/positions/orders `0/0/0/0`, margin/risk `$0/$0`, balance/equity `$104.48/$104.48`, project realized `$3.83` and stressed balance `$99.418`.
- Safety, persistence, broker and foreign flags were `0/0/0/0`; warnings and alerts were zero. The preserved status SHA-256 is `6D76996A175B5DDDC48C0311620394E45C711930395A15DF9C9B7FEDA4489822`.
- The committed flat-stop operator then stopped PID `21944` normally. No terminal now owns the account; the user-authorized final `0/0 → 1/1` handshake is the only remaining promotion action.

## STATE-0044 - 2026-08-26

- At committed and pushed Git `f224a48101bd7508567dc7024467b1f51090dca4`, final CXR2 preflight PID `24820` repeated exact `0/0`, flat release/Portfolio/Magic/account and balance continuity, then stopped normally before any entry-enabled process started.
- Exact CXR2 Live PID `13328` then passed the operator's `1/1` handshake. Persistent snapshots advanced `2008 → 2009 → 2010` through server `2026.08.25 18:29:24` with positions/order/margin/planned risk `0/0/$0/$0`, balance/equity `$104.48/$104.48`, project realized `$3.83`, stressed balance `$99.418`, and safety/persistence/broker/foreign `0/0/0/0`.
- Warnings and alerts remained zero. Preserved first/second/final status SHA-256 values are `9BBBA55CEEC47392A40975CF93B9E82A90D21D7867B55AB06AC5B4C59A816A64` / `351A1C577D2E3FF297F877FB0AA1635F684DDD176973E57E8840189A4A4DDD1A` / `5FCE9BB77F0BBFE2CE291F7D9AE4E1D6FE90B459382413CB022CD10C4338C8FE`. Terminal PID `13328` and dashboard PID `4284` are each sole.
- Closed `protective-exit-order-reconciliation-019` as `PROMOTION_COMPLETE_HEALTHY_FUTURE_ENTRY_READINESS_RESTORED`. Live promotion evidence SHA-256 is `C43426647091BED461E976CFBD74F24814F8327D9A905E48E5B31EE7E8C0E7BB`; the source-frozen family is now the one forward Lab baseline. A future natural SL is bounded operating confirmation of the repaired transient branch, not an open research hypothesis.
