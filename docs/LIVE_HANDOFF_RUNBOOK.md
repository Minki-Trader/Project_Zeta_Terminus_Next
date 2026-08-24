# V6R6에서 Next V7으로 한 번만 인계하는 절차

이 문서는 실행 순서다. 현재 상태에서는 1단계까지만 완료됐고 Next Live 권한은 없다.

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

[`ZETA_NEXT_MASTER_TERMINAL_AND_DASHBOARD.cmd`](../ZETA_NEXT_MASTER_TERMINAL_AND_DASHBOARD.cmd)를 실행한다. Master는 먼저 AllowLiveTrading `1`, entries `0/0`인 flat preflight를 열어 exact handshake를 확인하고 정상 정지한다. 그 뒤에만 entries `1/1` Live를 시작하고 한국어 대시보드를 연다.

1/1 handshake가 실패했지만 Next가 flat임을 로컬 스냅숏으로 입증하면 Next를 정지한다. Legacy 복구는 별도 운영 판단이다. Next 노출이 없다고 입증할 수 없거나 주문·포지션이 생겼다면 Next를 계속 실행해 그 위험을 관리하고 Legacy를 재시작하지 않는다.

## 7. 안정화 뒤 마감

안정적인 V7 인계 후 Legacy에 최종 handoff 기록과 `terminus-final-handoff-v1` 태그를 푸시하고 GitHub 저장소를 archive한다. Next에는 `next-live-v7-handoff-v1` 태그를 남긴다. 그때 B75를 다음 단일 연구 작업으로 복원한다.
