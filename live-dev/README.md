# Live-Dev

이 디렉터리는 동결된 Next 배포 스냅숏과 Next 전용 운영 도구만 소유한다. Live 권한은 오직 `CURRENT_STATE.md`가 결정한다.

`package/active/`는 Lab에서 자동 연결되지 않는다. 현재 고정 paired-month 후보가 닫힌 `paired-month-live-replacement-handoff-v1`에서 한 번만 번역된 `NEXT-E02-V8-PMLR1-b1c77d3b6356` 소스, EX5, base SET과 두 manifest를 가진다. 경제 계약은 weights `2 / 1.5 / 2 / 2.5 / 1.5 / 0`, position risk `0.04`, aggregate cap `0.18`, Passive disabled로 동결됐다. V8은 새 실행·Portfolio·Magic·schema와 `ZetaTerminusNext\live\v8-pmlr1\state|research` namespace를 사용하며 RLO1 상태·주문·포지션·연구 ledger를 채택하지 않는다. `runtime/portable/`은 별도 MT5 설치이며 Lab 또는 Optimization의 소스, EX5, SET, 상태나 로그를 읽지 않는다.

현재 V8의 exact identity·package bytes·compile·entries-disabled create/recovery는 유효하다. 새 clean adjacent V2 pair는 무결하게 완료됐지만 CANDIDATE가 actual/stressed `+$409.81 / +$367.818`, relative equity DD `37.39%`, control 대비 `+$36.51 / +$25.1525`, recovery `3.29586`로 고정 경제 gate를 통과하지 못했다. 이 nonconfirmation은 그대로 유효하다. 다만 사용자가 그 불리한 수치를 확인한 뒤 이 정확한 release를 실계좌 연구로 완전 교체하고 최상위 승인 기준까지 바꾸라고 명시했으므로, `docs/OPERATING_DIRECTION.md`의 2026-08-31 1회성 exact-release 예외와 `live-dev/evidence/V8_USER_ACCEPTED_LIVE_RESEARCH_OVERRIDE_V1.json`에 한해 `CURRENT_STATE.md`가 `1/1`을 승인할 수 있다. 이는 다른 후보·release·risk contract에 전파되지 않으며 market freshness, 동기화, flatness, sole-owner, exact-hash와 zero-fault gate는 완화하지 않는다.

그 exact 예외에 따른 최종 교체는 완료됐다. 첫 시도는 시세/M15 gate에서 `1/1` 전에 안전 종료했고, 두 번째 시도는 US30 `11` updates, maximum gap `2.605s`, required timeframes `3/3`을 통과한 뒤 exact Live PID `33388`, sequence `468`, entries `1/1`, zero position/order/margin/risk/fault로 handshake했다. 현재 소유권과 이후 sequence는 항상 `CURRENT_STATE.md` 및 로컬 상태 조회기로 다시 확인하며, durable activation은 `evidence/V8_USER_ACCEPTED_LIVE_RESEARCH_ACTIVATION_V1.json`이다.

계정·브로커 캐시와 release 전환 receipt는 검증된 flat 경계에서만 갱신하며 Git에는 포함하지 않는다. RLO1은 sequence `6425`, entries `0/0`, position/order/margin/risk `0/0/0/0`에서 정상 정지했고, 최종 프로젝트 귀속 실현손익 `+$4.55`만 V8 초기 계약에 이월된다.

V8 상태 조회기와 대시보드는 새 로컬 namespace의 스냅숏만 읽는다. 퇴역 RLO1 core/research 파일은 historical read-only이며 자동 교체·회전·정리·append 대상이 아니다. Master 실행기는 Legacy 또는 다른 Next 터미널이 실행 중이면 실패 폐쇄한다. 정확한 순서는 [`docs/LIVE_HANDOFF_RUNBOOK.md`](../docs/LIVE_HANDOFF_RUNBOOK.md)를 따른다.
