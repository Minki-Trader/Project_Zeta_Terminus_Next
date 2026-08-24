# NEXT-E01 V7 모듈 구조

V7은 새 경제 전략이 아니라 B70 V6R6의 구조적 후계다. 여섯 진입, 시각, 방향, 주문, 수량, 보호, 비용, RC4 관리와 위험 계약은 그대로 두고 한 파일의 책임만 아래처럼 분리했다.

| 모듈 | 책임 |
|---|---|
| `Domain/ZetaDomain.mqh` | 고정 구성요소, `ComponentDefinition`, `ComponentState`, `PortfolioState`, `ExecutionState`, `DecisionIntent`, 입력과 상태 선언 |
| `Time/ZetaSessionClock.mqh` | FPMarkets 서버시각, 뉴욕 시간, 휴장일과 세션 계약 |
| `Strategies/ZetaRC16.mqh` | RC16 명시적 진입 |
| `Strategies/ZetaRC4.mqh` | RC4 명시적 진입과 동결 adverse compression·Shadow·Seal·Retry |
| `Strategies/ZetaCross.mqh` | US100 Cross 명시적 진입 |
| `Strategies/ZetaPressure.mqh` | US30 Pressure 명시적 진입 |
| `Strategies/ZetaReturn.mqh` | US30 Return 명시적 진입 |
| `Strategies/ZetaPassive.mqh` | US100 Passive 명시적 주문과 생명주기 |
| `Portfolio/ZetaPortfolioRisk.mqh` | `$100` stage, 크기, margin, stop, aggregate risk |
| `Execution/ZetaOwnership.mqh` | 계정·Magic·단일 소유권과 환경 계약 |
| `Execution/ZetaOrders.mqh` | 주문, deal 집계, lifecycle 복구와 진입·청산 |
| `Execution/ZetaProtectionAndReconciliation.mqh` | 보호 일치, Passive·broker 재조정과 기존 위험 안전화 |
| `Persistence/ZetaStateAndEvents.mqh` | 새 V7 상태, bounded event, 현재 snapshot과 결정 저널 |

메인 EA는 조립과 이벤트 순서만 가진다. 상속된 정상 `OnTick` 순서는 `위험 갱신 → 소유권 감사 → 재조정 → 청산 → Passive → Shadow → RC4 → RC16 → Pressure → Return → Cross → RC4 관리`다. Tester의 every-tick Shadow 관찰과 dispatch gate도 V6R6 순서를 유지한다.

여섯 전략은 동적 플러그인이나 범용 등록기로 바꾸지 않았다. 각각 명시적인 파일과 명시적인 호출로 남아 있다.
