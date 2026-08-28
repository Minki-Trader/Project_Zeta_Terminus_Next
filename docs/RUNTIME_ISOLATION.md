# Live-Dev, Optimization, Lab 격리

## Lab

`lab/engineering/protective-exit-order-reconciliation-v1/mt5/`가 현재 동결된 Lab forward baseline이다. `lab/mt5/`는 과거 V7/Frontier 혼합 workspace로 동결되어 신규 소스를 받지 않는다. `lab/control-v6r6/`는 legacy anchor에서 복사한 B70 V6R6 동결 대조군이다. 각 `lab/runtime/` Portable은 Git에 포함되지 않으며 Lab 내부 source만 사용한다.

Lab은 `live-dev/`의 소스, EX5, SET, 상태 또는 로그를 읽지 않는다. 실틱 결과와 EA 파일 출력도 `lab/artifacts/`에만 쓴다.

## Optimization

`optimization/baseline/`은 `CURRENT_STATE.md`가 지목한 정확한 활성 Live 패키지의 한 번 복사된 읽기 전용 스냅숏이다. 각 `optimization/campaigns/<family>/`는 그 기준을 한 번 복사하고 실행 전 별도 identity와 상태·출력 경로를 갖는다. 생성 런타임과 큰 결과는 각각 `optimization/runtime/`과 `optimization/artifacts/`에만 둔다.

최적화는 Master 또는 `live-dev/runtime/portable/`을 사용하지 않고 전용 물리 Portable에서만 실행한다. Lab Portable, Lab source, Live state/log 및 다른 optimization campaign을 include·link·execute하지 않는다.

## Live-Dev

`live-dev/package/active/`는 검증 후 한 번 복사된 현재 V7 배포 스냅숏이다. `live-dev/runtime/portable/`의 정적 EA·Include·base Preset junction은 이 패키지만 가리킨다. 계좌 바인딩 0/0·1/1 SET은 별도 물리 디렉터리 `MQL5/Presets/ZetaTerminusNextRuntime/`에 로컬 생성된다. 터미널이 만드는 상태와 로그는 Live Portable 내부에 남으며 Lab 경로로 연결되지 않는다.

Lab과 optimization 변경은 Live 패키지에 자동 반영되지 않는다. 패키지 교체에는 새 release identity, 소스·EX5·SET 해시, source/release manifest와 별도 상태 기록이 필요하다. Optimization 결과는 직접 승격하지 않고, 사용자 승인 뒤 별도 Lab engineering handoff에서 검증된 구현 파일만 Live로 한 번 복사하며 Include junction을 Lab이나 optimization으로 돌리지 않는다.

## 현재 상태

Lab Tester Portable은 MT5 build 6140 실행 파일과 US100·US30·US500 실틱 캐시를 로컬 복제해 구성한다. Optimization Portable도 같은 build와 필요한 시장자료를 물리적으로 복사하지만 별도 source/EX5/SET/state/log를 소유하고 계정 주문 권한을 갖지 않는다. Live Portable에는 같은 build, 동결 V7 패키지, 계정·브로커 캐시와 V7 전용 상태가 있다. V6 상태나 포지션은 복사하지 않았다. 2026-08-25 CP1+CP2 승격은 부모 V7을 pre-window flat에서 정상 정지한 뒤 동일 execution/Portfolio/Magic/state 계약으로 entries-disabled recovery·restart와 최종 `0/0 → 1/1`을 통과했다. Exact patch release만 현재 Live owner다.
