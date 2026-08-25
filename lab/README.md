# Lab

이 디렉터리는 Live와 분리된 연구·공학 작업만 소유한다. 어떤 파일도 `live-dev/`를 include하거나 Live 상태·로그를 읽어서는 안 된다.

## 앞으로의 단 하나의 기준

- 기준 root: `engineering/complexity-refactor-v1/mt5/`
- 기준 commit: `9d1cbeeea232eec1e574dc7e4e3b0e65adf412b5`
- 상태: CP1·CP2 동등성 통과 후 동결; CP3 소스 변경 없음
- 사용법: 새 작업은 이 root를 수정하지 않고 자기 family root로 한 번 복사해 시작한다.

`mt5/`는 과거 기준 V7과 종료된 Frontier EA·Adapter가 섞여 있는 역사적 workspace다. 증거 참조를 보존하기 위해 현재 위치에서 동결하며, 앞으로 `.mq5`, `.mqh`, EA 또는 Adapter를 추가하거나 수정하지 않는다.

## Root 역할

- `control-v6r6/`: legacy anchor의 동결 대조군
- `mt5/`: 동결된 역사적 V7/Frontier workspace; 신규 작업 금지
- `engineering/complexity-refactor-v1/`: 현재 forward baseline을 소유하는 닫힌 공학 family
- `research/strategy-independence-risk-allocation/`: 닫힌 전략 독립성·위험배분 family
- `research/deposit-capital-risk-capacity/`: 닫힌 예치자본·위험용량 family
- `research/live-dev-performance-forensics/`: 닫힌 V1-V7 실운영 성과·동시보유·중단 포렌식 family; 소스 없음
- `research/portfolio-exit-coordination-v1/`: 닫힌 동시수익 보존·청산조정 family; 16개 실틱 경로에서 후보 없음, 동결 V7 청산 유지
- `runtime/`: Git 제외, family별 독립 Portable과 임시 산출물
- `artifacts/`: 실틱 결과, EA 출력과 빌드 로그
- `tools/`: 정상 Lab compile·MT5 실행 도구

새 family는 `research/<family>/` 또는 `engineering/<family>/` 하나에 source·config·evidence를 함께 둔다. 다른 family root를 include하거나 닫힌 root를 다시 열지 않는다. 상세 강제 규칙은 `docs/OPERATING_DIRECTION.md`의 `Source topology discipline`이 권위다.
