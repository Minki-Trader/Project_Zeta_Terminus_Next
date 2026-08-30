# Live-Dev

이 디렉터리는 동결된 Next 배포 스냅숏과 Next 전용 운영 도구만 소유한다. Live 권한은 오직 `CURRENT_STATE.md`가 결정한다.

`package/active/`는 Lab에서 자동 연결되지 않는다. 현재 고정 paired-month 후보가 닫힌 `paired-month-live-replacement-handoff-v1`에서 한 번만 번역된 `NEXT-E02-V8-PMLR1-b1c77d3b6356` 소스, EX5, base SET과 두 manifest를 가진다. 경제 계약은 weights `2 / 1.5 / 2 / 2.5 / 1.5 / 0`, position risk `0.04`, aggregate cap `0.18`, Passive disabled로 동결됐다. V8은 새 실행·Portfolio·Magic·schema와 `ZetaTerminusNext\live\v8-pmlr1\state|research` namespace를 사용하며 RLO1 상태·주문·포지션·연구 ledger를 채택하지 않는다. `runtime/portable/`은 별도 MT5 설치이며 Lab 또는 Optimization의 소스, EX5, SET, 상태나 로그를 읽지 않는다.

계정·브로커 캐시와 release 전환 receipt는 검증된 flat 경계에서만 갱신하며 Git에는 포함하지 않는다. RLO1은 sequence `6425`, entries `0/0`, position/order/margin/risk `0/0/0/0`에서 정상 정지했고, 최종 프로젝트 귀속 실현손익 `+$4.55`만 V8 초기 계약에 이월된다.

V8 상태 조회기와 대시보드는 새 로컬 namespace의 스냅숏만 읽는다. 퇴역 RLO1 core/research 파일은 historical read-only이며 자동 교체·회전·정리·append 대상이 아니다. Master 실행기는 Legacy 또는 다른 Next 터미널이 실행 중이면 실패 폐쇄한다. 정확한 순서는 [`docs/LIVE_HANDOFF_RUNBOOK.md`](../docs/LIVE_HANDOFF_RUNBOOK.md)를 따른다.
