# 연구 계보 요약

이 문서는 기존 Axis 이름을 개발의 실제 내용으로 오해하지 않도록 연구를 경제적 계열로 다시 묶은 입구다. `Pre-V1`, `Economic`, `Axis A/B/C`는 각 기록의 출처 태그로만 남는다.

| 계열 | 핵심 질문 | 현재 결론 |
|---|---|---|
| [진입 신호·시장 구조](ENTRY_SIGNAL_AND_MARKET_STRUCTURE.md) | 언제 어느 방향으로 최초 진입할 것인가 | 현재 여섯 진입 스트림은 동결됐고, A01~A73에서 별도 Axis A 생존자는 없음 |
| [외부시장·이벤트](EXTERNAL_INTERMARKET_AND_EVENTS.md) | 외부 정보가 독립적이고 제때 쓸 수 있는가 | 일부 상태 설명력은 있으나 현재 실행체를 바꿀 반복 가능한 경제 효과는 없음 |
| [주문·시각·세션](ORDER_TIMING_AND_ENTRY_MECHANICS.md) | 신호를 어떤 주문과 시각으로 실행할 것인가 | 현재 서버시각·2분 admission·Passive 계약을 유지 |
| [포지션 관리·청산](POSITION_MANAGEMENT_AND_EXITS.md) | 진입 후 HOLD보다 나은 조치가 있는가 | RC4 B48 압축만 채택; B75가 RC16 동결 생명주기 HOLD를 명시적으로 확인했고 나머지 전략도 기존 HOLD 유지 |
| [포트폴리오·자본·위험](PORTFOLIO_CAPITAL_AND_RISK.md) | 공유 `$100`에서 생존 가능한가 | 여섯 구성요소와 유한위험 계약 유지 |
| [전략 독립성·위험배분](STRATEGY_INDEPENDENCE_AND_RISK_ALLOCATION.md) | 선진입 슬롯 점유로 더 좋은 후속 전략이 막히며 이를 당시 정보로 개선할 수 있는가 | 차단 headroom은 확인; 세 인과 예약 정책은 2024 위험·반기 기준 미통과, 선착순 유지 |
| [실행·복구·브로커 안전](EXECUTION_PERSISTENCE_AND_BROKER_SAFETY.md) | 동일 경제를 실계좌에서 안전하게 소유할 수 있는가 | B70 V6R6이 현재 Legacy Live 부모; V7은 구조적 후계 개발 중 |
| [진단·인과·메타 연구](DESCRIPTIVE_CAUSAL_AND_META_RESEARCH.md) | 무엇을 알며 무엇을 아직 모르는가 | 설명적 headroom은 있으나 자동 정책이나 열화 예측 모델 근거는 부족 |

완전 파일 색인은 `lineage/legacy-files.jsonl`, 연구 관련 완전 색인은 `lineage/research-lineage.jsonl`, 실행체 계보는 `lineage/executable-lineage.json`에 있다.
