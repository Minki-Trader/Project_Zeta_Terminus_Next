5m 57s 동안 처리함

NO_READY_HYPOTHESIS

1. 동결된 AMBIGUOUS...NO_SEED 판정은 맞습니다

제시된 수치와 식별 경계 안에서는 경제적·인과적 오류가 발견되지 않습니다. 오히려 AMBIGUOUS_PAIRED_CONTROL_BLOCKED_OPPORTUNITY_VALUE_NO_SEED가 가장 엄격하고 일관된 결론입니다.

먼저 내부 산술은 서로 맞습니다.

전체 매칭률은 158 / 211 = 74.8815166%입니다. 다만 실제 경제성과가 열린 표본은 전체 158개가 아니라 selection의 141개 매칭쌍뿐입니다.

기간별 stressed 합계는
21.006 + 38.618 + 136.9443 − 295.145 = −98.5767입니다.

장부별 합계도
67.0833 − 165.66 = −98.5767입니다.

구성요소별 합계 역시
−165.66 + 72.78 − 5.6967 = −98.5767입니다.

−98.5767 / 7,663.0599 = −1.2864%도 제시된 attempted-risk 비율과 일치합니다.

유리 판정이 실패한 것은 명확합니다

후보 거래량으로 재가중한 결과는 actual −$66.8377, stressed −$98.5767, stressed PF 0.913650입니다. 따라서 다음 핵심 조건이 동시에 무너집니다.

actual 양수 실패

stressed ≥ +$109.55048 실패

PF ≥ 1.10 실패

양수 장부 2/2 실패: US30만 양수

양수 구성요소 ≥ 2/3 실패: Return만 양수

기간 breadth 3/4, 평균 stressed R, 집중도 조건이 통과했더라도, 이는 실패한 핵심 조건들을 대체하지 못합니다. 일부 통과 조건만 골라 유리 판정으로 바꾸면 바로 사후 선택이 됩니다.

강한 불리 판정도 실패한 것이 맞습니다

반대로 강한 불리 판정도 완성되지 않았습니다.

stressed −$98.5767은 ≤ −$109.55048에 도달하지 못함

PF 0.913650은 ≤ 0.90이 아님

평균 stressed R은 양수

음수 기간은 1/4

음수 장부는 1/2

구성요소가 2/3 음수라는 사실만으로 강한 불리 판정을 성립시킬 수 없습니다. 즉, 유리한 결과도 아니고 사전에 정한 강한 불리 결과도 아니므로 ambiguous가 정확합니다용.

2. 양의 평균 R과 음의 총손익은 모순이 아닙니다

이 부분은 중요한 식별 포인트입니다.

각 통제 lifecycle의 손익을 y
i
	​

, 후보 거래량과 통제 거래량의 비율을 r
i
	​

라고 하면 다음 두 수치는 서로 다른 estimand입니다.

native 통제 결과: ∑y
i
	​


후보 거래량 direct shadow: ∑r
i
	​

y
i
	​


stressed 기준으로 전자는 +$27.757, 후자는 −$98.5767입니다. 이는 거래량 비율이 큰 행들이 상대적으로 나쁜 통제 lifecycle에 더 많이 놓여 있었다는 재가중 결과를 나타낼 수 있습니다.

하지만 이것은 다음을 의미하지 않습니다.

거래량 증가가 손실을 인과적으로 발생시켰다는 것

risk cap을 줄이면 손익이 개선된다는 것

특정 weight를 낮추면 sign이 복구된다는 것

blocked candidate의 실제 손익이 −$98.5767이었다는 것

거래량 비율은 외생적으로 배정된 처치가 아니며, 사용된 stop/exit은 후보의 실제 경로가 아니라 통제 lifecycle에서 차용한 경로입니다. 따라서 sign reversal은 유효한 진단이지만 sizing 또는 cap의 인과효과는 아닙니다.

평균 R이 양수인데 재가중 달러 총액이 음수인 것도 산술 오류가 아닙니다. 전자는 행 단위 비가중 평균이고, 후자는 거래량 비율에 의해 가중된 총액이기 때문입니다. 서로 다른 질문에 답하며, 바로 그 불일치가 모호성의 일부입니다.

3. 인과적 경계도 적절하게 지켜졌습니다

정확한 component, server time, direction, feature, entry price 매칭은 141개 selection 매칭쌍에서 gross entry-timing 차이로 결과를 설명하는 가능성을 줄입니다. 다만 이 결론은 그 매칭 부분집합에만 적용됩니다.

이를 다음으로 확대하면 오류가 됩니다.

전체 211개 blocked row

매칭되지 않은 53개

June–July와 August의 아직 열리지 않은 경제성과

blocked candidate의 실제 stop/exit

후속 admission과 incumbent displacement

계좌 순서 효과와 자본 제약

margin 또는 open-equity drawdown

Live 실행 가능성

동결 closure는 이런 확대 해석을 하지 않았으므로 인과적 과장도 없습니다.

또한 selection이 사전 favorable gate를 통과하지 못한 뒤 June–July와 August 경제성과를 열지 않은 결정도 맞습니다. 그 17개 완전 매칭 결과를 지금 열어 방향을 정하면, 원래의 확인 순서를 깨고 후속 기간을 판정 구제 수단으로 사용하는 셈입니다.

4. 현재 독립적으로 READY인 가설은 없습니다

READY 가설이 되려면 결과를 보기 전에 다음 두 가지를 동시에 고정할 수 있어야 합니다.

하나의 명확한 인과적 처치와 그에 따른 경제적 행동

그 가설을 깨뜨릴 독립적인 falsifier

현재 map에서는 어느 Program도 이를 충족하지 못합니다.

Program 1: Units 120–122의 비확인이 유지되며 인접 threshold, window, direction, horizon을 다시 선택할 수 없습니다.

Program 2: expiration-week 결과는 작은 ambiguous association이고, 외부 정보원 screen들도 특정 행동과 falsifier를 고정할 단계가 아닙니다.

Program 3: 정확 매칭은 entry-timing 설명 하나를 약화시켰을 뿐 order, priority, slippage, reservation 행동을 식별하지 않았습니다.

Program 4: 후보의 실제 stop/exit 경로가 관찰되지 않았습니다. 제시된 tick 상태는 경제적 처치효과가 아니라 readiness 경계입니다.

Program 5: 유리하지도 강하게 불리하지도 않아 cap, admission, weight, priority seed가 없습니다.

Program 7: 거래량 재가중 sign reversal은 진단값일 뿐입니다. 여기서 volume ratio, risk ratio 또는 sizing rule을 선택하면 Unit 124 결과에서 직접 행동을 고르는 사후 sizing rescue입니다.

특히 다음 후보들은 모두 금지된 결과 선택에 해당합니다.

E4만 보고 기간 필터를 만드는 것

US100만 보고 book 행동을 정하는 것

Cross 또는 Pressure만 보고 component 행동을 정하는 것

손실 행의 volume ratio를 보고 cap이나 size를 바꾸는 것

PF 0.913650이 0.90에 가깝다는 이유로 adverse seed를 인정하는 것

−$98.5767이 adverse 금액 gate에 가깝다는 이유로 threshold를 이동하는 것

따라서 causal action과 falsifier를 지금 고정하려면 반드시 Unit 124의 관측된 이질성에서 선택해야 합니다. 이것이 READY 조건을 직접 위반합니다.

5. readiness를 바꿀 수 있는 최소한의 새 데이터

필요한 것은 동일 shadow 표본을 더 세분화한 자료가 아니라, Unit 124 결과와 독립적으로 발생한 하나의 새로운 외생적 배정 구조를 가진 fresh cohort입니다.

최소한 그 자료에는 다음이 함께 있어야 합니다.

현재의 cap, weight, admission, priority, reservation, ladder, sizing neighborhood에서 선택되지 않은 하나의 사전 정의된 처치

처치 여부가 현재 후보 손익이나 Unit 124의 period/book/component/volume 결과에 의해 정해지지 않는 외생적 배정 근거

처치된 관측치에서 후보 자신의 실제 entry–protective stop–exit lifecycle

같은 시점의 비교 가능한 비처치 관측치

결과를 보기 전에 고정된 경제적 성공 gate와 falsifier

순서 의존 자본효과를 주장하려면 이를 직접 관찰할 수 있는 경제경로

단순히 다음 자료를 추가하는 것은 materially new data가 아닙니다.

현재 141개를 period, book, component, row 또는 volume ratio로 다시 나누는 것

매칭되지 않은 53개를 추정으로 채우는 것

닫혀 있는 June–July 또는 August 결과를 뒤늦게 여는 것

인접 cap, weight, threshold 또는 risk ratio를 시험 대상으로 고르는 것

같은 통제 exit을 다른 배율로 재계산하는 것

6. 현재 후보의 양수 수익은 메커니즘이 아닙니다

후보의 selection, June–July, August actual/stressed 수익은 결과 변수입니다. 그것 자체는 어떤 인과적 처치도 지정하지 않습니다.

동일한 양수 총수익은 서로 다른 조합에서 나올 수 있습니다.

신호 선택

노출 크기

거래 순서

stop/exit 경로

구성요소 구성

시기별 시장 상태

자본 제약

실현되지 않은 기회의 배제

현재 경계에서는 이 요인들 중 하나를 독립적으로 변경한 반사실이 없습니다. 특히 Unit 124는 blocked candidate의 실제 protective stop과 exit을 관찰하지 않았으므로, 후보의 양수 손익과 direct shadow의 음수 손익을 연결해 “무엇을 바꾸어야 하는지”를 식별할 수 없습니다.

따라서 현재 후보가 profitable하다는 사실은 replacement-development 후보를 기술할 수는 있지만, cap·weight·admission 또는 다른 행동을 정당화하는 causal mechanism이나 Live authority가 되지는 않습니다.
