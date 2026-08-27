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

Core operational lineage: `B48 → B49/V6R2 → B52/V6R3 → B66/V6R4 → B67/V6R5 → B70/V6R6 → NEXT-E01/V7`.

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

This successor adds only the verified read-only research observation hooks and a separate `ZetaTerminusNext\research\canonical` namespace. Candidate/lifecycle ledgers append and flush; the Live EA has no reset/delete call, no automatic rotation or cleanup exists, and the dashboard continues to consume only the unchanged core Live snapshot. CXR2 stopped normally at server `2026.08.27 05:56:29`, before every current-day evaluation window, with entries `1/0`, no position/order/margin/risk/retry/shadow/ARC state and no consumed 2026-08-27 opportunity. Committed RLO1 entries-disabled PIDs `21400/16484` passed create/recovery at exact `0/0`; final preflight PID `3424` stopped normally and exact Live PID `8080` passed `1/1`. PID `8080` and dashboard PID `28332` were later lost together during the 2026-08-27 Codex MSIX replacement boundary without a normal MT5 shutdown footer; the last local snapshot at `17:00:23` was flat and zero-risk. Recovery commit `41473c378289f87d3f5f82e2a3cb95dfa99c2800` reached origin, fresh preflight PID `22108` passed exact `0/0` and stopped, and replacement Live PID `9976` plus dashboard PID `14324` are healthy.

## Authority boundary

- Legacy B70 V6R6 Live-Dev: stopped at the verified flat boundary and `DISABLED`.
- Next V7 Live-Dev authorization: `ENABLED`; exact restarted RLO1 PID `9976` is the verified sole owner at entries `1/1` after recovery preflight PID `22108` proved `0/0`, flat exposure and zero risk and stopped.
- V7 may not import or adopt B70 positions or state.
- The original V7 PID `10112`, CXR1 PID `21548`, prior entries-disabled/preflight PIDs including CXR2 `21944/24820/28148` and RLO1 `21400/16484/3424/22108`, dashboard PIDs `4712/4284/28508/28332`, CXR2 PIDs `13328/15080`, and former RLO1 PID `8080` are no longer active. Exact RLO1 PID `9976` and Korean dashboard PID `14324` are active; Legacy, parent V7, CXR1 and CXR2 must not restart.

## Completed legacy closure

B75 `RC16 Explicit Frozen-Life HOLD Confirmation` resumed after migration and is complete as an evidence-only Next closure. The exact frozen B45/B55/B60/B65/B68/B74 records support keeping the full accepted RC16 volume to its original catastrophic stop or fixed eight-M30 exit. No new data, outcome, executable, identity, deployment, Live change, or successor research stream opened.
