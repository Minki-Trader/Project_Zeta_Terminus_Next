# Live-Dev

이 디렉터리는 동결된 Next 배포 스냅숏과 Next 전용 운영 도구만 소유한다. 현재 Live 권한은 `DISABLED`이며 실행 가능한 V7 패키지도 아직 없다.

`package/active/`는 Lab에서 자동 연결되지 않는다. 검증된 release를 한 번 복사해 해시로 고정한 뒤에만 채운다. `runtime/portable/`은 별도 MT5 설치이며 Lab 소스, EX5, SET, 상태 또는 로그를 읽지 않는다.

계정·브로커 캐시는 최종 flat handoff 때 legacy 터미널을 정상 정지한 뒤에만 로컬 이식한다. Git에는 포함하지 않는다.
