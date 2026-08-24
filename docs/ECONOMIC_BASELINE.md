# 승계 경제 기준

## 현재 동결 계약

- 시장·계좌: FPMarkets US100/US30/US500, USD, leverage `1:100`
- 참조자본: `$100`
- 구성요소: RC16, RC4, Cross, Pressure, Return, Passive
- 기본 크기: `0.01` lot, stage balance 증가단위 `$150`
- 위험: 포지션당 최대 4%, 합산 최대 12%, margin 최대 45%, unmodelled reserve 25%, stop-placement headroom 25%
- 실행: 전체 실제 Bid/Ask·변동 spread·관측비용 및 고정 2배 비용 스트레스

## Accepted V5와 B70

- Accepted V5의 동결 binding 실행은 `2,225` lifecycle, 실제 `$100 → $1,132.17`, 2배 관측비용 잔고 `$1,057.2515`, 최대 상대 equity DD `13.44%`였다. 최근 실행은 실제 `$106.54`, 2배 비용 `$104.9995`였다.
- B48은 V5 진입을 그대로 두고 RC4에 25%-remaining-loss adverse compression을 추가해 latest 실제/2배 비용을 `+$1.31/+$1.338`, binding을 `+$11.00/+$8.235` 개선했다.
- B70 V6R6 binding은 `2,235` first fills, 실제 net `+$1,019.04`, 고정 2배 비용 net `+$940.6585`; latest는 `84` first fills, 실제 net `-$1.11`, 2배 비용 net `-$2.819`이었다. Latest의 손실은 현재 환경 증거이며 B48/B70 선택을 다시 수행한 것이 아니다.

## V7 승계 규칙

V7은 경제 후보가 아니다. V6R6의 모든 진입, 방향, 주문, 수량, 비용, 보호, 관리, 보유기간과 위험 결과를 identity-only 정규화 후 정확히 재현해야 한다. 차이는 구현 오류로 취급하며, 더 좋은 결과도 구조 이전 중에는 채택하지 않는다.

