# Live-Dev

이 디렉터리는 동결된 Next 배포 스냅숏과 Next 전용 운영 도구만 소유한다. Live 권한은 오직 `CURRENT_STATE.md`가 결정한다.

`package/active/`는 Lab에서 자동 연결되지 않는다. 현재 `NEXT-E01-V7-RLO1-b32e7e176f2e`의 검증된 연구 관찰 ledger 소스, EX5, base SET과 두 manifest가 한 번 승격돼 있다. 실행·Portfolio·Magic·core state schema/path와 경제 설정은 CXR2와 같고, release ID 및 별도 `ZetaTerminusNext\research\canonical` append-only namespace만 새롭다. `runtime/portable/`은 별도 MT5 설치이며 Lab 소스, EX5, SET, 상태 또는 로그를 읽지 않는다.

계정·브로커 캐시와 release 전환 receipt는 검증된 flat 경계에서만 갱신하며 Git에는 포함하지 않는다.

상태 조회기와 대시보드는 Portable의 `MQL5/Files/ZetaTerminusNext/live` 로컬 스냅숏만 읽으며 연구 ledger를 표시하거나 소비하지 않는다. 정식 연구 candidate/lifecycle ledger는 자동 교체·회전·정리 대상이 아니다. Master 실행기는 Legacy 또는 다른 Next 터미널이 실행 중이면 실패 폐쇄한다. 정확한 순서는 [`docs/LIVE_HANDOFF_RUNBOOK.md`](../docs/LIVE_HANDOFF_RUNBOOK.md)를 따른다.
