# Live 인계 절차

## 현재 절차: RLO1에서 paired-month V8으로 한 번만 교체

현재 target은 `NEXT-E02-V8-PMLR1-b1c77d3b6356`, Portfolio `ZT-PORT-NEXT-V8-PMLR1-20260831`, Magic `260831901..260831906`이다. Canonical source/settings SHA-256은 `B1C77D3B635626EAA000F3A605F2CB1BC5A4D0C43709E8C3B3F693469F126B95`, EX5 SHA-256은 `E61CA9D50F8C6BF4849A9C2E857B08A6E9C4FD390B1B8DC0493EB741689D9274`다. 고정 경제 계약은 component multiplier `2 / 1.5 / 2 / 2.5 / 1.5 / 0`, base position risk `0.04`, aggregate cap `0.18`, Passive disabled다.

Clean V2 pair는 유효했지만 CANDIDATE가 actual/stressed `+$409.81 / +$367.818`, relative equity DD `37.39%`, control delta `+$36.51 / +$25.1525`, recovery `3.29586`로 재자격에 실패했다. 이 판정은 그대로 보존한다. 사용자는 이 수치를 확인한 뒤 exact V8의 완전 교체와 최상위 승인기준 변경을 명시했으므로, `docs/OPERATING_DIRECTION.md`의 2026-08-31 1회성 사용자 위험수용 예외만 경제 승인 근거가 된다. 이 예외는 아래 운영 안전 gate를 하나도 완화하지 않는다.

이 1회 교체는 완료됐다. 첫 final starter는 market gate에서 `1/1` 전에 안전 종료했고, 두 번째는 US30 `11` updates, maximum gap `2.605s`, synchronized fresh timeframes `3/3`을 통과하여 PID `33388`, sequence `468`, exact `1/1` handshake를 완료했다. 현재 owner와 더 최신 상태는 오직 `CURRENT_STATE.md`와 V8 status reader가 결정한다.

1. RLO1은 신규진입 금지로 한 번만 기동해 exact identity와 `0/0`, owned positions/pending orders/margin/planned risk `0/0/0/0`, fault `0`, 미완료 decision `0`을 확인하고 정상 정지한다. 이 경계는 sequence `6425`, balance/equity `$105.20/$105.20`, project realized net `+$4.55`, project stage balance `$104.55`로 완료됐다.
2. RLO1 core/research state, current/event 파일, order/deal, Magic와 `runtime.lock`은 퇴역 historical read-only다. V8은 이를 복구·채택·merge·append·rotate·clean·rewrite하지 않는다. 기존 `Import-ZetaNextLegacyRuntimeHandoff.ps1`은 V8에 사용하지 않는다. 로컬 `live-release-transition-pmlr1.json`은 동일 계정과 최종 귀속 실현손익만 묶는다.
3. `CURRENT_STATE.md`가 V8 entries-disabled preflight를 `ENABLED`로 기록하고 exact package commit이 `origin/main`에 도달한 뒤 `Start-ZetaNextV8EntriesDisabled.ps1 -ConfirmEntriesDisabled`를 실행한다. 터미널이 꺼져 있으면 실행기가 직접 정확한 Portable을 켠다. 신규 namespace가 처음 생성되고 exact release/Portfolio/Magic/account, entries `0/0`, zero exposure/risk/fault, 증가하는 snapshot을 통과해야 한다.
4. `Show-ZetaNextV8Dashboard.ps1 -Once -ExpectedMode EntriesDisabled`로 새 snapshot만 확인한다. `Stop-ZetaNextV8FlatRuntime.ps1 -ConfirmFlatStop`으로 정상 정지한 뒤 같은 starter로 재기동하여 fresh-state recovery, sequence 증가, 동일한 `0/0`와 append behavior를 확인한다. RLO1 파일 해시는 전후 동일해야 한다.
5. `Get-ZetaNextV8MarketStatus.ps1`은 계정·포지션·주문·deal을 조회하지 않고 실제 FPMarkets US30 tick 연속성과 US30/US100/US500 M15/M30/H1의 synchronized/non-stale bar만 관찰한다. 시장 폐장이나 tick 부재는 실패나 일시정지 사유가 아니다. MT5를 entries-disabled로 계속 두고 실제 tick이 돌아올 때까지 기다린다. 첫 tick을 놓치면 그 다음 가장 이른 안전한 window를 쓴다. 평가 시각 보호구간 안에서는 handoff하지 않는다.
6. exact entries-disabled owner를 다시 직접 확인해 position/order/margin/risk `0`, 모든 fault `0`인 flat 경계를 증명하고 `Stop-ZetaNextV8FlatRuntime.ps1 -ConfirmFlatStop`으로 정상 정지한다. 2026-08-31 exact-release 예외, V2 nonconfirmation 및 중지 경계를 함께 기록한 뒤 `CURRENT_STATE.md`의 Live와 V8 new-entry authorization을 `ENABLED`, owner를 `none`으로 커밋·푸시한다. 추가 사용자 확인은 필요하지 않다.
7. `Start-ZetaNextV8Live.ps1 -EnableNewEntries -ConfirmLiveDev`만 사용한다. 실행기는 정확한 Portable이 꺼져 있으면 스스로 켜고, fresh exact `0/0` preflight에서 sole PID, identity, account, flatness와 fault를 다시 증명한 뒤 연속 tick, 세 symbol/timeframe sync, unchanged `3.0`-second freshness 및 평가시각 보호구간까지 통과해야만 `1/1`을 연다. 시세 gate가 실패하면 preflight를 정상 정지하고 안전 window에서 다시 시도한다. handshake 실패 때 무노출이 입증되면 정상 정지 후 수정·재시도하고, 무노출을 입증할 수 없거나 주문·포지션이 생겼다면 V8을 계속 실행해 관리하며 RLO1을 절대 재시작하지 않는다.
8. `1/1`, continuous ticks, synchronized data, persistent healthy sequence, sole owner, zero alert/warning/fault와 퇴역 파일 불변성을 안정화한 후 evidence, manifests, `CURRENT_STATE.md`를 마감하고 `main == origin/main`, clean worktree를 증명한다.

아래 V6R6→V7 및 V7 patch 절차는 완료된 역사 기록이며 현재 V8에 재사용하거나 소유권을 부여하지 않는다.

## 역사 절차: V6R6에서 Next V7으로 한 번만 인계

이 문서는 완료된 실행 순서다. 1~7단계, 양쪽 최종 태그와 legacy GitHub archive가 모두 완료됐고 정확한 V7이 유일한 Live 소유자다. 운영 재시작은 Next 전용 소유권 절차를 유지한다.

## 1. 이미 완료된 준비

- `NEXT-E01-V7-2db5ef5ead1c`
- Portfolio ID `ZT-PORT-NEXT-V7-2db5ef5ead1c`
- Magic `260824701..260824706`
- MQ5 SHA-256 `D210A662A51FE5691CBC9A3FC4DD376A2826D848DC904FBD578F7B9C9911FDB1`
- EX5 SHA-256 `0A722406921F76259E4828D87915C2BA6F2F345A4059CC310EEC4BC446011B53`
- Latest와 Binding 실틱 경제·주문 동등성 통과
- `live-dev/package/active/` 일방향 동결 복사 완료

## 2. 자연 flat 경계

Legacy V6R6의 포지션, 대기주문, margin, 계획위험이 모두 `0`이고 모든 전략의 진입 허용 시각 밖이며 미완료 결정이 없을 때만 진행한다. 이 확인 전에는 Legacy를 정지하거나 Next 계정 캐시를 만들지 않는다.

조건이 맞으면 Legacy 상태 문서에 아래 사실을 기록하고 커밋·푸시한다.

- `Handoff flat verification: PASSED`
- `Handoff entry-window check: PASSED`
- `Handoff incomplete decisions: 0`

그 뒤 Legacy를 정상 정지하고 최종 상태와 로그를 동결한다. Next `CURRENT_STATE.md`는 다음처럼 바꿔 커밋·푸시한다.

- `Next V7 entries-disabled preflight: ENABLED`
- `Next V7 new-entry authorization: DISABLED`
- `Existing real-account owner: none`

## 3. 계정·브로커 캐시의 로컬 이식

Legacy와 모든 Next 터미널/테스터가 정지한 상태에서만 `Import-ZetaNextLegacyRuntimeHandoff.ps1`을 실행한다. 최종 프로젝트 귀속 실현손익, Legacy 최종 상태 파일과 로그 파일을 인자로 준다. 이 도구는 Legacy V6 상태나 포지션을 V7 상태로 복사하지 않는다.

도구가 이식하는 것은 정지된 MT5 계정·브로커 캐시뿐이다. Git 밖에 `legacy-final-handoff.json`을 만들고 계정, 최종 실현손익, Legacy 커밋과 상태·로그 해시를 기록한다.

## 4. 정상 entries-disabled 저장·재시작

`Start-ZetaNextV7EntriesDisabled.ps1 -ConfirmEntriesDisabled`를 실행한다. 다음을 모두 만족해야 터미널이 열린 상태로 남는다.

- 정확한 release, EX5, Portfolio ID, Magic, 상태 경로
- `HEAD == origin/main`
- Legacy와 다른 Next 터미널 없음
- 신규진입 `0/0`
- 포지션·주문·margin·계획위험 `0`
- handoff receipt의 계정과 선행 실현손익 일치
- 소유권, 저장, 브로커 재조정, 안전 카운터 정상

`Show-ZetaNextV7Dashboard.ps1 -ExpectedMode EntriesDisabled`로 5초 로컬 스냅숏을 확인한다. `Stop-ZetaNextV7FlatRuntime.ps1 -ConfirmFlatStop`으로 정상 정지하고 같은 entries-disabled 실행기를 다시 시작해 `RESUME`, 증가한 state sequence, 동일한 0/0·flat 상태를 확인한다. 별도 테스트 하네스는 만들지 않는다.

증거를 상태 기록에 남긴 뒤 Next 상태를 `Next V7 entries-disabled preflight: PASSED`로 바꾸고 커밋·푸시한다.

## 5. 별도 사용자 Live 승인

정확한 V7 ID, Magic, Latest/Binding 결과와 entries-disabled 재시작 증거를 사용자에게 제시한다. 사용자가 새 V7 Live와 신규 주문을 명시적으로 승인한 뒤에만 다음 두 값을 `ENABLED`로 바꾸고 커밋·푸시한다.

- `Next Live-Dev authorization`
- `Next V7 new-entry authorization`

## 6. 한 번의 0/0 → 1/1 인계

[`ZETA_NEXT_MASTER_TERMINAL_AND_DASHBOARD.cmd`](../ZETA_NEXT_MASTER_TERMINAL_AND_DASHBOARD.cmd)를 실행한다. Master는 Windows `Win32_Process.Create` one-shot broker를 통해 Codex 프로세스 수명 밖에서 한 번 시작된다. 먼저 AllowLiveTrading `1`, entries `0/0`인 flat preflight를 열어 exact handshake를 확인하고 정상 정지한 뒤에만 entries `1/1` Live와 한국어 대시보드를 연다. 시작 worker는 창 복원까지 끝나면 종료되며 예약 작업, 상주 launcher, PID/health 감시 또는 자동 재시작은 남지 않는다.

1/1 handshake가 실패했지만 Next가 flat임을 로컬 스냅숏으로 입증하면 Next를 정지한다. Legacy 복구는 별도 운영 판단이다. Next 노출이 없다고 입증할 수 없거나 주문·포지션이 생겼다면 Next를 계속 실행해 그 위험을 관리하고 Legacy를 재시작하지 않는다.

## 7. 안정화 뒤 마감

안정적인 V7 인계 후 Legacy에 최종 handoff 기록과 `terminus-final-handoff-v1` 태그를 푸시하고 GitHub 저장소를 archive한다. Next에는 `next-live-v7-handoff-v1` 태그를 남긴다. 그때 B75를 다음 단일 연구 작업으로 복원한다.

## 8. 2026-08-25 CP1+CP2 patch 전환 완료

- Parent release `NEXT-E01-V7-2db5ef5ead1c`를 첫 진입 구간 전 flat에서 정상 정지했다.
- Target release `NEXT-E01-V7-CXR1-c0ad2f30d293`, EX5 SHA-256 `F0B7D64BE36F81304C8764A89DFFA2499CD5F4ACED73A7A1837F950EFECC919F`는 검증된 CP1·CP2 구현 파일만 승격했다.
- Release ID만 새로 부여했고 execution version, Portfolio, Magic, state marker/schema/path, base SET과 경제 계약은 부모와 같게 유지했다.
- 두 차례 entries-disabled recovery/restart와 최종 preflight PID `26112`의 `0/0`가 통과한 뒤 Live PID `21548`이 exact `1/1` handshake를 통과했다.
- 첫 final invocation은 preflight PID 종료 직후의 짧은 process visibility race에서 fail-closed로 멈췄다. 최대 5초의 bounded process-exit wait만 운영기에 추가한 뒤 재실행했으며, 그 사이 신규 주문이나 소유 exposure는 없었다.
- Dashboard PID `4712`가 exact Live local snapshot만 표시한다. Parent V7과 legacy는 재시작하지 않는다.

## 9. 2026-08-26 CXR2 protective-exit 전환 완료

- CXR1 PID `21548`은 safety-stopped `1/0`이면서 positions/order/margin/risk와 retry/shadow/ARC가 모두 0인 서버 `18:12:03` 경계에서 정상 정지했다. 만료된 Cross 진입을 사후 재생하지 않았다.
- Target `NEXT-E01-V7-CXR2-14d84b9e4bb3`, EX5 SHA-256 `620D0351AF22EAA389BE7F36CBD3AB6C9D2204D182E897CFE6A845495428CFC6`는 검증된 `ZetaOwnership.mqh` 하나와 release ID만 승격했다. Execution, Portfolio, Magic, state schema/path와 SET은 CXR1과 같다.
- 정지된 state A/B는 원본을 백업한 뒤 `safety_stopped` 한 바이트씩만 `1 → 0`으로 바꿨다. 다른 모든 바이트와 current/event 파일은 보존됐고 `broker_mismatch`는 런타임 재대조에서 0으로 복구됐다.
- Committed entries-disabled PID `21944`와 final preflight PID `24820`이 각각 exact `0/0`을 통과하고 정상 정지한 뒤 Live PID `13328`이 exact `1/1`을 통과했다. Persistent sequence `2008 → 2009 → 2010`에서 fault/warning/alert가 모두 0이다.
- Dashboard PID `4284`가 새 CXR2 로컬 스냅숏을 표시한다. CXR1과 이전 runtime은 재시작하지 않는다.

## 10. 2026-08-27 RLO1 연구 관찰 ledger 전환 완료

- CXR2 PID `15080`은 실제 MT5 Algo Trading을 꺼 entries `1/0`으로 만든 뒤, 서버 `05:56:29`의 pre-window flat에서 정상 정지했다. 포지션·주문·margin·계획위험·retry·shadow·ARC는 모두 0이었고 2026-08-27 기회는 하나도 소비하거나 건너뛰지 않았다.
- Target `NEXT-E01-V7-RLO1-b32e7e176f2e`, EX5 SHA-256 `CB225D97DA7BCEC30599B472F615C7A3775C359A0F8FA8293FBB9C222795775B`는 검증된 관찰 모듈과 후행 기록 훅만 승격했다. Execution, economic version, Portfolio, Magic, core state marker/schema/path와 SET은 CXR2와 같다.
- 별도 `ZetaTerminusNext\research\canonical` namespace의 candidate/lifecycle ledger는 append-only이며 자동 교체·회전·정리 대상이 아니다. Live main은 연구 reset/delete를 호출하지 않는다. 대시보드는 연구 파일을 읽지 않고 기존 core snapshot만 표시한다.
- Committed entries-disabled PIDs `21400/16484`가 observer 생성과 복구를 포함한 exact `0/0`을 통과하고 정상 정지했다. Final preflight PID `3424`도 exact `0/0`을 통과하고 정지한 뒤 Live PID `8080`이 exact `1/1`을 통과했다.
- 실제 `US30,M30` 차트에서 EA 부착과 Algo Trading 활성화를 확인했다. Persistent healthy sequences `3838 → 3840 → 3841`에서 fault/warning/alert는 모두 0이고 research state A/B가 계속 갱신된다. 자연스러운 첫 평가 전에는 검증을 위해 candidate/lifecycle 행을 인위적으로 만들지 않는다.
- Dashboard PID `28332`가 변경 없는 한국어 UI를 표시한다. CXR2와 이전 runtime은 재시작하지 않는다.
