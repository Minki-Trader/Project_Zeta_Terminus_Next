# 예치자본·위험용량 연구

이 연구는 실제 계좌에 현금을 더 넣는 행위와 EA가 그 자본을 경제적으로 사용하는 행위를 분리한다. 현재 V7을 그대로 둔 `$200/$300` 계좌, 예치금에 맞춰 `0.01/0.02/0.03` lot과 위험 달러를 선형 확대하는 계좌, 그리고 같은 12%를 더 많은 전략 슬롯이나 손실 제동에 쓰는 계좌를 비교한다.

## 순서

1. 이미 소비된 2024 fresh-`$100` 결합·단독 실틱 원장으로 경제 가설을 빠르게 프록시한다.
2. 직접 질문인 `LINEAR_CAPITAL`과, capacity 계열 및 sizing-governor 계열에서 하나씩만 EA로 만든다. 프록시 부적격 계열도 최고 순위 하나는 `DIAGNOSTIC_ONLY`로 구현한다.
3. 모든 EA와 비교군은 2025-01-01에 `$100/$200/$300` 중 선언된 금액으로 새로 시작한다.
4. 2025 상·하반기와 연간을 모두 통과한 한 정책만 2026-01-01~2026-06-01 확인으로 갈 수 있다.
5. 2026년 6~7월과 8월 일부는 V1에서 열지 않는다.

## 해석 경계

- 단순 입금 대조군은 내부 기준자본 `$100`, `0.01` lot, 포지션 `$4`, 합산 `$12`를 유지한다.
- 선형 자본군은 시작 예치금과 lot, 포지션·합산 위험 달러, 추가 lot 단계가 같은 비율로 움직인다.
- capacity 프록시는 여섯 단독 생애를 물리적 진입 순서로 합친다. 거절 뒤 생겼을 대체 신호, 공유 equity·margin, Passive 대기주문과 RC4 경로 피드백은 실제 EA만 확인할 수 있다.
- 손절폭이 바뀌는 정책은 관측 종가손익의 notional 경로와 관측 stressed-R 경로를 둘 다 계산하며, 거래별 더 나쁜 값을 선별 기준으로 쓴다.
- 결과는 Live 승격이나 설정 변경 권한이 아니다.

기계 사전선언은 [`lab/evidence/DEPOSIT_CAPITAL_RISK_CAPACITY_DECLARATION_V1.json`](../../evidence/DEPOSIT_CAPITAL_RISK_CAPACITY_DECLARATION_V1.json)에 있다.

## 동결 프록시 결과

- `LINEAR_CAPITAL`: 직접 질문이라 사전 고정된 필수 구조 앵커. 2024 경로를 `$200/$300`에 선형 확대하면 스트레스 수익률 `54.663%`, 폐쇄 DD `17.779%`가 유지됐다.
- `BREADTH_DOLLAR_SLOTS`: capacity 계열 유일 적격. `0.01` lot과 약 `$4` 위험을 유지하고 여섯 슬롯까지 허용한 독립경로 프록시는 571건, `+$62.6900`, `$200` 기준 수익률 `31.345%`, DD `7.589%`, net/DD `4.1303`이었다.
- `FIXED_LOT_LADDER`: sizing-governor 계열은 모두 부적격이었고, 사전선언의 진단 fallback으로 선택됐다. `$300`에서 36개 진입 크기가 달라졌으나 수익률 `48.1792%`, DD `17.7896%`로 선형 확대보다 약했다.
- 3% 4슬롯, 2% 6슬롯, symbol bucket과 6% drawdown brake는 EA로 가지 않는다.

프록시 원본은 [`lab/evidence/DEPOSIT_CAPITAL_RISK_CAPACITY_PROXY_V1.json`](../../evidence/DEPOSIT_CAPITAL_RISK_CAPACITY_PROXY_V1.json)이다.
