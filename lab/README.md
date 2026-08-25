# Lab

이 디렉터리는 Live와 분리된 연구·공학 작업만 소유한다. 어떤 파일도 `live-dev/`를 include하거나 Live 상태·로그를 읽어서는 안 된다.

## 앞으로의 단 하나의 기준

- 기준 root: `engineering/protective-exit-order-reconciliation-v1/mt5/`
- 기준 commit: `0d4032786cecb7d7e8a4c3074609db5b105fa107`
- 상태: CP1·CP2 위에서 보호성 SL 과도주문 대조 수리와 정확 경제 동등성 통과 후 동결; CXR2 Live 승격 완료
- 사용법: 새 작업은 이 root를 수정하지 않고 자기 family root로 한 번 복사해 시작한다.

`mt5/`는 과거 기준 V7과 종료된 Frontier EA·Adapter가 섞여 있는 역사적 workspace다. 증거 참조를 보존하기 위해 현재 위치에서 동결하며, 앞으로 `.mq5`, `.mqh`, EA 또는 Adapter를 추가하거나 수정하지 않는다.

## Root 역할

- `control-v6r6/`: legacy anchor의 동결 대조군
- `mt5/`: 동결된 역사적 V7/Frontier workspace; 신규 작업 금지
- `engineering/complexity-refactor-v1/`: 동결된 CP1·CP2 predecessor 공학 family
- `research/strategy-independence-risk-allocation/`: 닫힌 전략 독립성·위험배분 family
- `research/deposit-capital-risk-capacity/`: 닫힌 예치자본·위험용량 family
- `research/live-dev-performance-forensics/`: 닫힌 V1-V7 실운영 성과·동시보유·중단 포렌식 family; 소스 없음
- `research/portfolio-exit-coordination-v1/`: 닫힌 동시수익 보존·청산조정 family; 16개 실틱 경로에서 후보 없음, 동결 V7 청산 유지
- `research/tester-replay-financing-drift-v1/`: 닫힌 테스터 재생·금융비용 포렌식 family; 스왑 심볼명세 드리프트를 원인 경계로 확정, 소스·추가 실행 없음
- `research/strategy-frontier-coverage-v1/`: 닫힌 전략 프론티어 커버리지 진단 family; RC16·RC4·Pressure 모두 네 기간 양의 점유시간당 stressed 손익으로 단일 약체 대상 없음, 소스·추가 실행 없음
- `research/us30-context-rotation-v1/`: 닫힌 RC4→Pressure 인과 맥락 Proxy family; 118건 중 맥락 17건으로 고정 표본 게이트 미달, 소스·추가 실행 없음
- `research/receiver-time-field-generalization-v1/`: 닫힌 Passive 만료→Return/Cross 수신시간장 일반화 family; 12개 실틱 경로에서 2025 재현은 성공했으나 전체 개선·DD·진입수 게이트 미달, CP2 유지
- `research/passive-refusal-depth-observation-v1/`: 닫힌 Passive 미체결 접근깊이 관찰 family; 4개 실틱 경로에서 Return은 다중 게이트 미달, Cross는 pooled 신호가 있었으나 기간별 tail 방향 2/4로 폭넓음 게이트 미달, selector 없이 CP2 유지
- `research/risk-capacity-release-window-v1/`: 닫힌 위험용량 해제창 진단 family; event-key 계약 결함으로 정식 판정 무효, 비권위 민감도도 exact deadline 해제 3/78로 기준 미달, retry 후보 없음
- `research/native-signal-strength-value-v1/`: 닫힌 6전략 native feature 정보가치 진단 family; 2,233 lifecycle 정확 복원, 모든 전략 pooled Spearman `|rho|<0.20`으로 strength allocation 후보 없음
- `research/entry-time-crowding-value-v1/`: 닫힌 진입시점 포트폴리오 crowding 진단 family; 5개 dense 전략 효과 미미, RC4 관찰은 crowded 15건·폭 1기간으로 밀도 미달, 관리 후보 없음
- `research/server-day-carry-burden-v1/`: 닫힌 서버 날짜 이월부담 진단 family; 2,233건 중 이월은 RC16 1건·RC4 2건뿐이고 나머지는 0건으로 밀도 미달, 날짜경계 관리 후보 없음
- `research/actual-live-position-economics-v1/`: 닫힌 Unit 020 실포지션 경제경로 family; T03-T15에서 개별 수익기억 부담과 늦은 성숙 승자 제약이 함께 통과해 넓은 역사 관찰 Unit 021 하나만 유지, 관리 규칙·임계값·Live 후보 없음
- `research/profit-memory-state-observation-v1/`: 닫힌 Unit 021 family; P1 대조군·관찰자 뒤 심볼 DB 지문 변경으로 전체 행렬이 경제 판정 전 무효, 남은 6경로·clean rerun·관리 후보 없음
- `engineering/protective-exit-order-reconciliation-v1/`: 현재 forward baseline을 소유하는 닫힌 정상 SL 과도주문 소유권 대조 수리 family; P4 실틱 경제 완전동등성, CXR2 `0/0 → 1/1` 승격과 다중 영속 healthy snapshot 통과
- `runtime/`: Git 제외, family별 독립 Portable과 임시 산출물
- `artifacts/`: 실틱 결과, EA 출력과 빌드 로그
- `tools/`: 정상 Lab compile·MT5 실행 도구

새 family는 `research/<family>/` 또는 `engineering/<family>/` 하나에 source·config·evidence를 함께 둔다. 다른 family root를 include하거나 닫힌 root를 다시 열지 않는다. 상세 강제 규칙은 `docs/OPERATING_DIRECTION.md`의 `Source topology discipline`이 권위다.
