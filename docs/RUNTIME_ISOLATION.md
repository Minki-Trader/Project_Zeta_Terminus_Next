# Live-Dev와 Lab 격리

## Lab

`lab/mt5/`는 변경 중인 V7 소스와 Tester 설정을 소유한다. `lab/control-v6r6/`는 legacy anchor에서 복사한 B70 V6R6 동결 대조군이다. `lab/runtime/tester-portable/`은 Git에 포함되지 않는 별도 MT5 Portable이며, 그 junction은 `lab/` 내부만 가리킨다.

Lab은 `live-dev/`의 소스, EX5, SET, 상태 또는 로그를 읽지 않는다. 실틱 결과와 EA 파일 출력도 `lab/artifacts/`에만 쓴다.

## Live-Dev

`live-dev/package/active/`는 승인 직전 한 번 동결 복사되는 정확한 배포 스냅숏이다. `live-dev/runtime/portable/`의 정적 EA·Include·Preset junction은 이 패키지만 가리킨다. 터미널이 만드는 상태와 로그는 Live Portable 내부에 남으며 Lab 경로로 연결되지 않는다.

Lab 변경은 Live 패키지에 자동 반영되지 않는다. 패키지 교체에는 새 release identity, 소스·EX5·SET 해시와 별도 기록이 필요하다.

## 현재 상태

Lab Tester Portable은 현재 MT5 build 6140 실행 파일과 US100·US30·US500 실틱 캐시를 로컬 복제해 구성한다. Live Portable은 계정·브로커 캐시 없이 실행 파일과 빈 패키지 경계만 준비한다. Legacy Live 터미널이 정상 정지하고 V7 인계 승인을 받은 뒤에만 그 캐시를 로컬 이식할 수 있다.
