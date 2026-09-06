# 지정가 주문 계약 확인

세 지수 US100·US30·US500의 현재 계약은 지정가, 손절·익절, 시각 지정 만료를 허용한다. order_mode=127, expiration_mode=15, filling_mode=3이며 BOC 플래그는 없다. 현재 손절/동결 최소 거리는 모두 0 points다. 해석 근거는 [MetaQuotes Symbol Properties](https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants)다.

대기 주문은 보내는 순간 체결하는 주문과 구분해야 한다. [MetaQuotes Order Properties](https://www.mql5.com/en/docs/constants/tradingconstants/orderproperties)는 pending 요청에 ORDER_FILLING_RETURN을 사용하도록 설명한다. Market Execution의 즉시 주문 RETURN 제한을 그대로 대기 주문 금지로 해석하지 않는다. 거래소 호가장 우선권이나 스프레드 획득도 이 CFD 계약에서 보증되지 않는다.

기존 Lab의 일반 플랫폼과 접속 자료만 별도 reader에 물리 복사했다. build 6140/API 5.0.5640의 정확한 자체 data_path와 connected=true, trade_allowed=false를 확인했고 계약 필드만 얻었다. 계좌·포지션·주문·체결 이력·가격 이력·주문 실행 호출은 없었다. PID 33328의 CloseMainWindow/정상 종료와 이후 소유 프로세스 0을 확인했다. 연결 자료는 정확한 runtime Git 제외 규칙 아래 보존하며 Git에 올리지 않았다.

이것은 현재 시점의 계약 관측이다. 예전 스냅샷과 달리 현재 USD/lot 금융비용(long/short)은 US100 -4.34/+1.82, US30 -7.87/+3.34, US500 -1.14/+0.48이다. 과거 비용을 소급 보증하거나 닫힌 후보를 다시 계산할 권한은 아니다. margin_initial=0 역시 증거금이 없다는 뜻이 아니다.

정적 주문 지원 준비는 통과했지만, 실제 체결 시간순 자료는 새 후보의 선언 이후 자체 입력으로 확보해야 한다. M1 고가·저가 순서를 수익에 유리하게 가정하지 않는다. 72개 월별 TKC의 존재와 약 1.15GB 크기만 확인했고, 이 단계에서 틱을 해독하거나 완전성을 판정하지 않았다. 출처 단계는 종료하고 전체 거시 비교를 거쳐 새 독립 계약을 선언한다.
