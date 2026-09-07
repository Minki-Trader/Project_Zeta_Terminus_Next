# Terminus to Next Continuity

## Legacy anchor

- Repository: `https://github.com/Minki-Trader/Project_Zeta_Terminus.git`
- Initial migration anchor: `4c0899255c701e2c6b53e7f44457c431aef2ad76`
- Anchor date: 2026-08-24 KST
- Role: complete historical evidence and archived read-only former B70 V6R6 Live-Dev repository after verified V7 handoff

The legacy repository is read-only to Next except for the explicit anchored paths in the machine lineage indexes. No adjacent local project may be used as a source.

## Frozen executable parent

- Candidate: `B70`
- Execution: `zt-pre500-finite-risk-portfolio-v6r6-rc4-transient-protection-modify-retry`
- Portfolio ID: `ZT-PORT-PRE500-FR6R6-RC4MR-cda6e28b13f4`
- Magic: `260823301..260823306`
- Source SHA-256: `7B98E33E093502DD1E582FA53260E06AD6BEA5820C74CDEEC691239F701446AA`
- EX5 SHA-256: `C5E569092B492F350A0B47DBF060A82293A302002F73A842FA52465BE2716E92`
- Tester SET SHA-256: `BEBA34FE89B01EC4F1582C2C1EA4BC02E8FB73E0D78B78BAB833EEC63F8065E8`

Core operational lineage: `B48 → B49/V6R2 → B52/V6R3 → B66/V6R4 → B67/V6R5 → B70/V6R6 → NEXT-E01/V7 → NEXT-E01/V7-RLO1 → NEXT-E02/V8-PMLR1 → NEXT-E03/V7R-RLO1`.

## Verified structural successor

- Release: `NEXT-E01-V7-2db5ef5ead1c`
- Execution: `zt-next-pre500-finite-risk-portfolio-v7-modular-2db5ef5ead1c`
- Portfolio ID: `ZT-PORT-NEXT-V7-2db5ef5ead1c`
- Magic: `260824701..260824706`
- Canonical source/settings SHA-256: `2db5ef5ead1c68e6f596f78726adcc9d622ec4f58868451aec11a68a5748578e`
- MQ5 SHA-256: `D210A662A51FE5691CBC9A3FC4DD376A2826D848DC904FBD578F7B9C9911FDB1`
- EX5 SHA-256: `0A722406921F76259E4828D87915C2BA6F2F345A4059CC310EEC4BC446011B53`
- Fixed Latest/Binding verdict: `ECONOMIC_AND_ORDER_EQUIVALENCE_PASSED`

This successor completed the original Live handoff and is now the frozen parent of the CP1+CP2 patch release.

## Verified structural patch successor

- Release: `NEXT-E01-V7-CXR1-c0ad2f30d293`
- Parent release: `NEXT-E01-V7-2db5ef5ead1c`
- Execution and Portfolio: unchanged from the parent V7
- Magic: unchanged `260824701..260824706`
- Canonical source/settings SHA-256: `C0AD2F30D293AD538A91DE74A6D0A14A560FA19222F1DB043E1C533C103A7DD7`
- MQ5 SHA-256: `D210A662A51FE5691CBC9A3FC4DD376A2826D848DC904FBD578F7B9C9911FDB1`
- EX5 SHA-256: `F0B7D64BE36F81304C8764A89DFFA2499CD5F4ACED73A7A1837F950EFECC919F`
- Engineering verdicts: `ENTRY_GATE_EQUIVALENCE_PASSED; MARKET_ENTRY_TRANSACTION_EQUIVALENCE_PASSED; CP3_HOLD`

The patch changes only the verified CP1 Entry Gate and CP2 market-entry transaction ownership boundaries plus the release ID. Economic settings, execution/state identity, persistence schema and state paths remain the parent V7 contract. Exact durable-state continuation passed stopped-flat entries-disabled recovery, restart and final `0/0 → 1/1` handoff.

## Verified protective-exit patch successor

- Release: `NEXT-E01-V7-CXR2-14d84b9e4bb3`
- Parent release: `NEXT-E01-V7-CXR1-c0ad2f30d293`
- Execution, Portfolio and Magic: unchanged from CXR1
- Canonical source/settings SHA-256: `14D84B9E4BB30A4CBCCE51B4841859912FEE9BDC1E7FCFFEFEE228C55823C072`
- MQ5 SHA-256: `D210A662A51FE5691CBC9A3FC4DD376A2826D848DC904FBD578F7B9C9911FDB1`
- EX5 SHA-256: `620D0351AF22EAA389BE7F36CBD3AB6C9D2204D182E897CFE6A845495428CFC6`
- Engineering verdict: `PROTECTIVE_EXIT_ORDER_RECONCILIATION_EXACT_EQUIVALENCE_PASSED`

This successor changes only current-order ownership classification for an exact broker-generated SL market order in transit plus the release ID. CXR1 stopped at a verified flat boundary, and both redundant state files had only the persisted false-positive safety latch cleared. CXR2 passed exact connected entries-disabled recovery, final `0/0 → 1/1` handoff and three persistent healthy snapshots.

## Verified research-observation successor

- Release: `NEXT-E01-V7-RLO1-b32e7e176f2e`
- Parent release: `NEXT-E01-V7-CXR2-14d84b9e4bb3`
- Execution, Portfolio, Magic, core state marker/schema/paths and SET: unchanged from CXR2
- Canonical source/settings SHA-256: `B32E7E176F2EF1B4A7AA6E9FB91D59FAC685325CC83A79DAA1947F5A431CA178`
- MQ5 SHA-256: `1AC7F4F6A1EB99EE00A7BFA77182641D8CE5585BBEB05075C960459C98918D26`
- EX5 SHA-256: `CB225D97DA7BCEC30599B472F615C7A3775C359A0F8FA8293FBB9C222795775B`
- Engineering verdict: `PASS_SAME_SPEC_EXACT_NON_INTERFERENCE_APPROVE_CONTROLLED_LIVE_PROMOTION`

This successor adds only the verified read-only research observation hooks and a separate `ZetaTerminusNext\research\canonical` namespace. Candidate/lifecycle ledgers append and flush; the Live EA has no reset/delete call, no automatic rotation or cleanup exists, and the dashboard continues to consume only the unchanged core Live snapshot. CXR2 stopped normally at server `2026.08.27 05:56:29`, before every current-day evaluation window, with entries `1/0`, no position/order/margin/risk/retry/shadow/ARC state and no consumed 2026-08-27 opportunity. Committed RLO1 entries-disabled PIDs `21400/16484` passed create/recovery at exact `0/0`; final preflight PID `3424` stopped normally and exact Live PID `8080` passed `1/1`. PID `8080` and dashboard PID `28332` were later lost together during the 2026-08-27 Codex MSIX replacement boundary without a normal MT5 shutdown footer; the last local snapshot at `17:00:23` was flat and zero-risk. Recovery commit `41473c378289f87d3f5f82e2a3cb95dfa99c2800` reached origin, fresh preflight PID `22108` passed exact `0/0` and stopped, and replacement Live PID `9976` plus dashboard PID `14324` resumed before the remaining evaluation windows. Those replacement processes were again lost together at the next Codex shutdown/update boundary; the last local core snapshot at `2026-08-28 09:49:02` was flat and zero-risk. Detached preflight PID `31064` then passed `0/0` and stopped before exact Live PID `23180` and dashboard PID `19280` recovered. The temporary scheduled/resident implementation was removed after the user clarified scope; commits `e0349a2cb882e8a9f033144ead5223968655b778` / `626375543bfc07a111cab6787a0542136d3df6c2` now use only a one-shot Windows process broker. No scheduled task, resident launcher, PID/health monitor or automatic restart remains.

## Verified paired-month Live translation successor

- Release: `NEXT-E02-V8-PMLR1-b1c77d3b6356`
- Parent release: `NEXT-E01-V7-RLO1-b32e7e176f2e`
- Execution: `zt-next-paired-month-live-portfolio-v8`
- Economic version: `zt-next-paired-month-live-replacement-economic-v1`
- Portfolio ID: `ZT-PORT-NEXT-V8-PMLR1-20260831`
- Magic: `260831901..260831906`
- Canonical source/settings SHA-256: `B1C77D3B635626EAA000F3A605F2CB1BC5A4D0C43709E8C3B3F693469F126B95`
- MQ5 SHA-256: `3D89719BA633D1FAB4BCE07284FD676205592CEFE164D06A7162190037440E5E`
- EX5 SHA-256: `E61CA9D50F8C6BF4849A9C2E857B08A6E9C4FD390B1B8DC0493EB741689D9274`
- Engineering verdict: `PASS_EXACT_FIXED_CANDIDATE_LIVE_IDENTITY_TRANSLATION_PENDING_CONNECTED_V8_PREFLIGHT`

The fixed candidate comes only from `optimization/campaigns/dd20-paired-month-stability-mt5-v1/` through the closed verified `lab/engineering/paired-month-live-replacement-handoff-v1/`. Its weights `2 / 1.5 / 2 / 2.5 / 1.5 / 0`, base risk `0.04`, aggregate cap `0.18` and Passive-disabled contract did not change. The translation changes only release/execution/Portfolio/Magic/schema identity, isolated `ZetaTerminusNext\live\v8-pmlr1\state|research` namespaces, SET/manifests and operators. RLO1 retired normally at sequence `6425`, entries `0/0`, zero position/order/margin/risk and project realized net `+$4.55`; only that realized P/L continuity may carry. Its state, current/event files and canonical research ledgers are immutable and are not V8 recovery material. Those V8 operating gates subsequently completed. V8 is now retired after the 2026-09-07 fresh stopped-flat handoff recorded below; the historical translation verdict is not current restart authority.

## Verified exact-V7 return in a new identity

- Release: `NEXT-E03-V7R-RLO1-0bba2ca045fe`
- Execution: `zt-next-v7-rlo1-return-portfolio-v1`
- Economic version: `zt-next-pre500-finite-risk-portfolio-v7-modular-parent-b70-v6r6`
- Portfolio ID: `ZT-PORT-NEXT-V7R-RLO1-20260907`
- Magic: `260907701..260907706`; new schema `7R1`
- Canonical source/settings SHA-256: `0BBA2CA045FEDCA95950C0569C385F5BFE408DDDE419851AAFCFCA5430FB4B7E`
- MQ5 SHA-256: `953BF5F1365D1181382CAF939261BCF0D50D74589696C2C11D55C68EB784C298`
- EX5 SHA-256: `30283FBB46C40527578DD06B72D0EFBA5A2E2959BBFCA5F57C4CAC6B7F05E657`

The user's conditional replacement request was accepted only after the complete unchanged native comparison in `lab/engineering/v7-rlo1-return-requalification-v1/`. Long V7 actual/stressed `+$313.36/+$284.138`, native DD `19.502399843%` and robust recovery `4.833923103` pass the frozen return standard against contemporaneous V8 `+$409.81/+$367.818`, DD `37.391909353%`. Recent V7 pooled actual/stressed `+$4.66/+$3.209` is weaker than V8 and includes a disclosed July loss. These are exact-return gates, not a Challenge victory.

V8 recovered with entries disabled, proved a fresh account-bound flat boundary and stopped normally at sequence `5340` on 2026-09-06T16:25:04Z. Old state, ledgers, package and operators are preserved privately. Only attributable project realized net `-$0.40` carries into V7R: project stage balance is `$99.60`, while new component stressed balances start at `$100.00`. No old positions, tickets or mutable state are adopted. New identity create/normal STOP/RESUME is healthy in `0/0`; the detached Master opened its EA and Korean dashboard. Current ticks were absent at installation. The later 07:02 KST read-only follow-up confirmed actual ticks and synchronized current bars, notified the user and paused its heartbeat. The EA remains entries-disabled; final trading activation is a direct user step under CURRENT_STATE. See `live-dev/evidence/V7R_RETURN_INSTALLATION_V1.json`, `live-dev/evidence/V7R_RETURN_ENTRIES_DISABLED_RECOVERY_V1.json` and `live-dev/evidence/V7R_READ_ONLY_MARKET_READY_20260907_V1.json`.

## Historical optimization ancestry and corrected economic authority

- Original frozen parent: `NEXT-E01-V7-RLO1-b32e7e176f2e`, derived at `f4e1effb647d5ef81921eddc64fcd6bef2289f57`.
- Frozen copy: `optimization/baseline/NEXT-E01-V7-RLO1-b32e7e176f2e/`; manifest SHA-256 `7A968666241AD90629F14ADF48E983AB04A4DD88053F1413EBB209FB51976698`.
- Historical V8 selection family: `optimization/campaigns/dd20-paired-month-stability-mt5-v1/`. Its reported `+$5,786.63/+$5,477.524` at DD `20.256887565%` is **descriptive only**, not a qualified anchor: detailed required-symbol tick-generation fallback supersedes the report label.
- Binding correction: `lineage/OPTIMIZATION_REAL_TICK_CONTINUITY_AUTHORITY_CORRECTION_V1.json`. Every original result remains immutable; the correction defines precisely which historical evidence lost authority.
- Current independent Challenge benchmark: `optimization/campaigns/dd20-paired-clean-requal-mt5-v2/evidence/DD20_PAIRED_CLEAN_REQUAL_MT5_V2_VALID_NONCONFIRMATION_V1.json`, actual/stressed `+$409.81/+$367.818`, native DD `37.39%`, robust recovery `3.295860215` over 2024-01-01 through 2026-08-01 exclusive.

The former optimization frontier, including exact-V8 Units U001-U004, closed at STATE-0499. Optimization has no active campaign or runtime. The later user direction instead authorizes the independent Python-adapter/ONNX-plus-EA Challenge, now resumed on 2026-09-07 with a minimum 30 GB free-space requirement implemented as the stricter 30 GiB floor. All current gates and the sole research unit belong in CURRENT_STATE. Historical Unit 120-123 accounts, the proxy-selected June-July interval and August comparisons remain in their immutable evidence/state history; the earlier narrative at commit `b07aa73` is historical and cannot restore superseded economic or operating authority.

## Challenge clock authority addendum

`lineage/CHALLENGE_BROKER_CLOCK_AUTHORITY_CORRECTION_V1.json` closes the 2026-09-07 source/timestamp audit without changing any old family. Families 006/007 directly indexed broker-wall epochs using UTC session schedules, so their adverse outputs do not adjudicate the declared external-local sessions. Families 008/010 used Helsinki, which differs from the nominal New York-close broker convention during 40 development weekdays; Family 010 includes 38 such dates among its 514 complete events. Rolling references can extend the impact beyond the misaligned dates. Family 009 retains its adverse H4 development judgment for this issue because bar indices, common ordering, dates, year boundaries and raw-server swap timing are unchanged; only UTC labels need correction.

QQQ/TQQQ 2025-03-10..14 raw session labels also require independent source authority before any exact external-session successor. No formula replacement is a universal history certificate, no favorable outcome is inferred, and no closed candidate automatically reopens. The audit does not affect exact V7R broker-native verification.

## Opening-admission authority addendum

`lineage/CHALLENGE_OPENING_ADMISSION_AUTHORITY_CORRECTION_V1.json` records a further source-confirmed defect confined to original Family 006. Its declared entry is anchor+5, but it constructs events only when both symbols have every timestamp through +74. The implemented mapping retains 965 of 999 prefix-plus-entry-complete events by using future availability; 34 exclusions include one unused-tail case. Its 515-date denominator omits 2025-02-04 and 2025-11-28 from 517 original observation dates. Original source, numbers and closure remain immutable descriptions of the implemented population, not a complete causal-policy economic judgment.

Exact external-session raw-time authority remains unresolved. MetaQuotes API documentation describes UTC output while the broker documents a server New-York-close convention; the original receipt lacks a field-specific bridge. US100 and US30 also show 2025-03-10..14 raw-session exceptions, extending the source concern beyond the previously observed ETF example. Earlier nominal offset statements remain conditional, not physical-time certificates. No favorable clock, deleted date, rerun or corrected candidate is authorized by this addendum. A new whole-map selection and complete prospective declaration would be required after independently defensible source authority.

## Authority boundary

Latest 2026-09-07 user direction resumes development specifically from existing V7, using ONNX/online learning and internal EA/MQH information for compound growth with comparable DD. The isolated Optimization campaign and new exact-V7R baseline named in CURRENT_STATE own this work; V8 Challenge stays paused and FRBSF remains permanently cancelled. All of Live-Dev and its direct-user 1/1 activation are preserved. Older pause/benchmark paragraphs below remain historical context; the latest scoped Operating Direction governs.

On 2026-09-07 the user permanently cancelled `lab/research/frbsf-news-sentiment-publication-readiness-v1/`, including future resumption. Its declaration and documentary metadata remain cancelled history; source-readiness and economic judgments are null. The broader Goal remains paused. A separate user-operated V7R activation reached fresh 0/0 but stopped at the unchanged market gate before Live; exact outcome, correction and entries-disabled recovery belong to CURRENT_STATE and Live evidence.

- Legacy B70 V6R6, original V7, CXR1, CXR2, original RLO1 and V8 are retired/stopped. No old identity may restart or adopt another identity's state.
- Exact V7R is installed with current new-entry authority governed only by CURRENT_STATE. The user's later 2026-09-07 arm-and-wait request removes current-market diagnostics from ordinary startup: after fresh account-bound flat `0/0` recovery, direct user activation may establish `1/1` while the unchanged EA waits for its trading conditions. Deployment tick-frequency/synchronization/window observations are diagnostic only; the EA's execution guards remain frozen. The assistant still cannot perform trading activation. A historical PID or earlier permission cannot override current authority.
- The one-shot detached Master leaves no resident launcher or OS trading monitor. The temporary same-task Codex follow-up checks read-only market/operating readiness, notifies the remaining direct user activation step and then pauses; research reaches a safe boundary before that serial check. It cannot enable new entries or Algo Trading, execute Start-ZetaNextV7RLive, or change trading authority.
- All other development remains physically isolated. No research or optimization result grants Live promotion.

## Completed legacy closure

B75 `RC16 Explicit Frozen-Life HOLD Confirmation` resumed after migration and is complete as an evidence-only Next closure. The exact frozen B45/B55/B60/B65/B68/B74 records support keeping the full accepted RC16 volume to its original catastrophic stop or fixed eight-M30 exit. No new data, outcome, executable, identity, deployment, Live change, or successor research stream opened.
