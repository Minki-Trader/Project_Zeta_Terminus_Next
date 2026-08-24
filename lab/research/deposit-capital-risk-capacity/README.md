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

## 동결 EA 경로

- `ZetaDcrcLinearCapitalV1`: `$100/$200/$300 → 0.01/0.02/0.03`, 4%/12%, 다음 lot 단계는 시작자본의 150% 이익마다 같은 배율로 증가.
- `ZetaDcrcBreadthDollarSlotsV1`: `$200/$300`에서도 `0.01`, 포지션 약 `$4`, 합산한도는 시작자본의 12%라 최대 여섯 전략이 함께 존재할 수 있음.
- `ZetaDcrcFixedLotLadderV1`: `$200/$300 → 0.02/0.03`, 이후 누적 스트레스 이익 `+$150`마다 정확히 `+0.01`.

세 EA는 build 6140 `0 errors / 0 warnings`이고 Tester 밖에서 초기화에 실패한다. 2025 결과를 열기 전 동결한 컴파일·설정 영수증은 [`lab/evidence/DEPOSIT_CAPITAL_RISK_CAPACITY_COMPILE_RECEIPT_V1.json`](../../evidence/DEPOSIT_CAPITAL_RISK_CAPACITY_COMPILE_RECEIPT_V1.json)이다.

## 2025 선택과 폐쇄

10개 fresh-account 2025 `100% 실제 틱` 실행은 모두 정상 STOP, 리포트/원장 일치, 안전·영속성·브로커·외부노출·보호·마진 오류 0이었다.

- 예치만 추가: `.01`을 유지한 스트레스 순익은 `$100 +113.068`, `$200/$300 +113.252`로 거의 같았다. DD율은 `28.3905% → 14.2353% → 9.4902%`로 낮아졌지만 수익률도 `113.068% → 56.626% → 37.7507%`로 희석됐다.
- `LINEAR_CAPITAL`: `$100/$200/$300` 스트레스 순익 `+113.068/+226.106/+338.984`, 수익률 `113.068/113.053/112.9947%`, DD율 `28.3905/28.3555/28.3605%`. 구조 앵커는 통과했지만 같은 위험률의 달러 확대이지 엣지 개선은 아니다.
- `BREADTH_DOLLAR_SLOTS`: 위험 차단 `0`, 최대 동시포지션 `4`, 거래 `576/577`로 폭은 늘었지만 수익률 `43.163/23.338%`, net/DD `3.1344/2.5990`으로 선형 대비 효율·수익률 바닥을 실패했다.
- `FIXED_LOT_LADDER`: `$200`은 선형보다 `+$3.884` 좋아졌지만, `$300`은 `-$89.2115` 나빠지고 DD율이 `+7.2498%p` 악화됐다. 양쪽 예치금 일관성 게이트를 실패했다.

통과한 비통제 정책이 없어 2026 확인 구간은 열지 않았다. 최종 판정은 `NO_NON_CONTROL_POLICY_PASSED_CLOSE_RETAIN_FROZEN_V7`이다. 기계 결과는 [`DEPOSIT_CAPITAL_RISK_CAPACITY_SELECTION_V1.json`](../../evidence/DEPOSIT_CAPITAL_RISK_CAPACITY_SELECTION_V1.json), 폐쇄는 [`DEPOSIT_CAPITAL_RISK_CAPACITY_CLOSURE_V1.json`](../../evidence/DEPOSIT_CAPITAL_RISK_CAPACITY_CLOSURE_V1.json), 사람이 읽는 상세 결론은 [`docs/lineage/DEPOSIT_CAPITAL_AND_RISK_CAPACITY.md`](../../../docs/lineage/DEPOSIT_CAPITAL_AND_RISK_CAPACITY.md)에 있다.
