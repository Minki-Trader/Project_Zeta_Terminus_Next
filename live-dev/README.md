# Live-Dev

이 디렉터리는 동결된 Next 배포 스냅숏과 Next 전용 운영 도구만 소유한다. 검증된 V7 패키지는 동결됐지만 현재 Live 권한은 `DISABLED`다.

`package/active/`는 Lab에서 자동 연결되지 않는다. 현재 `NEXT-E01-V7-2db5ef5ead1c`의 소스, EX5, base SET과 manifest가 한 번 복사돼 있다. `runtime/portable/`은 별도 MT5 설치이며 Lab 소스, EX5, SET, 상태 또는 로그를 읽지 않는다.

계정·브로커 캐시는 최종 flat handoff 때 legacy 터미널을 정상 정지한 뒤에만 로컬 이식한다. Git에는 포함하지 않는다.

상태 조회기와 대시보드는 Portable의 `MQL5/Files/ZetaTerminusNext/live` 로컬 스냅숏만 읽는다. Master 실행기는 Legacy 또는 다른 Next 터미널이 실행 중이면 실패 폐쇄한다. 정확한 순서는 [`docs/LIVE_HANDOFF_RUNBOOK.md`](../docs/LIVE_HANDOFF_RUNBOOK.md)를 따른다.
