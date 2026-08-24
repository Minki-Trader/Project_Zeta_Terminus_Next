# NEXT-E01/V7 실틱 동등성

V7은 새 전략이 아니라 B70 V6R6을 모듈로 나눈 구조적 후계다. 2026-08-24에 같은 FPMarkets build 6140, 같은 `$100`, `1:100`, 비용, 실틱, SET으로 대조 실행했다.

## 판정

`ECONOMIC_AND_ORDER_EQUIVALENCE_PASSED`

- 최근 2개월: 84 first fill, 실제 순익 `-$1.11`, 2배 비용 순익 `-$2.819`, 주문 178행과 딜 169행의 경제 필드 차이 `0`
- Binding: 2,235 first fill, 실제 순익 `+$1,019.04`, 2배 비용 순익 `+$940.6585`, 주문 4,583행과 딜 4,471행의 경제 필드 차이 `0`
- 두 구간 모두 보고서 성과 53행과 6개 전략별 종료 횟수·2배 비용 손익이 일치했다.
- Binding 보존 이벤트 4,165행 중 한 행의 `deal_wait_ms`만 `15 ms`와 `0 ms`로 달랐다. 이는 `GetTickCount64` 로컬 경과시간 진단값이며 의사결정에 읽히지 않는다. 그 값을 제외한 같은 행의 가격, 수량, 보호, 위험, 주문·딜 티켓은 일치했고 전체 보고서 주문·딜도 일치했다.

완전한 수치, 여섯 전략 분해, 원시 증거 SHA-256은 [`lab/evidence/NEXT_E01_V7_EQUIVALENCE.json`](../lab/evidence/NEXT_E01_V7_EQUIVALENCE.json)에 있다. 대용량 보고서·로그·회전 이벤트 원본은 Git에 넣지 않고 `lab/artifacts/backtests/equivalence/`의 로컬 동결 증거로 유지한다.

이 판정은 Live 권한이 아니다. 정상 연결된 entries-disabled 저장·재시작, flat 인계 조건, 사용자 재승인과 0/0 → 1/1 handshake가 남아 있다.
