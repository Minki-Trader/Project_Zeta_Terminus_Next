# Live-Dev와 Lab 격리

## Lab

`lab/engineering/complexity-refactor-v1/mt5/`가 현재 동결된 forward baseline이다. `lab/mt5/`는 과거 V7/Frontier 혼합 workspace로 동결되어 신규 소스를 받지 않는다. `lab/control-v6r6/`는 legacy anchor에서 복사한 B70 V6R6 동결 대조군이다. 각 `lab/runtime/` Portable은 Git에 포함되지 않으며 Lab 내부 source만 사용한다.

Lab은 `live-dev/`의 소스, EX5, SET, 상태 또는 로그를 읽지 않는다. 실틱 결과와 EA 파일 출력도 `lab/artifacts/`에만 쓴다.

## Live-Dev

`live-dev/package/active/`는 검증 후 한 번 복사된 현재 V7 배포 스냅숏이다. `live-dev/runtime/portable/`의 정적 EA·Include·base Preset junction은 이 패키지만 가리킨다. 계좌 바인딩 0/0·1/1 SET은 별도 물리 디렉터리 `MQL5/Presets/ZetaTerminusNextRuntime/`에 로컬 생성된다. 터미널이 만드는 상태와 로그는 Live Portable 내부에 남으며 Lab 경로로 연결되지 않는다.

Lab 변경은 Live 패키지에 자동 반영되지 않는다. 패키지 교체에는 새 release identity, 소스·EX5·SET 해시, source/release manifest와 별도 상태 기록이 필요하다. 검증된 구현 파일만 Lab에서 Live로 한 번 복사하며 Include junction을 Lab으로 돌리지 않는다.

## 현재 상태

Lab Tester Portable은 MT5 build 6140 실행 파일과 US100·US30·US500 실틱 캐시를 로컬 복제해 구성한다. Live Portable에는 같은 build, 동결 V7 패키지, 계정·브로커 캐시와 V7 전용 상태가 있다. V6 상태나 포지션은 복사하지 않았다. 2026-08-25 CP1+CP2 승격에서는 부모 V7을 pre-window flat에서 정상 정지했고, 동일 execution/Portfolio/Magic/state 계약을 가진 새 release의 entries-disabled recovery를 다음 경계로 고정했다.
