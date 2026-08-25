# Lab

이 디렉터리는 변경 가능한 V7 소스, 동결 V6R6 대조군, Tester 설정과 DEV 산출물만 소유한다. 어떤 파일도 `live-dev/`를 include하거나 Live 상태·로그를 읽어서는 안 된다.

- `control-v6r6/`: legacy anchor의 작은 동결 대조군
- `mt5/`: V7 소스와 설정
- `research/strategy-independence-risk-allocation/`: Lab 전용 `전략 독립성·위험배분 연구`; 여섯 단독 `$100` EA와 결합 대조군, 사전 선언 및 분석
- `research/deposit-capital-risk-capacity/`: 폐쇄된 Lab 전용 `예치자본·위험용량 연구`; 예치금별 lot tranche와 12% 위험용량 프록시·EA, 최종 `RETAIN_FROZEN_V7`
- `engineering/complexity-refactor-v1/`: 동결 V7에서 분기한 tester-only 공학 후보; CP1 Entry Gate와 CP2 Market Entry Transaction 분리 동등성 통과, CP3는 추가 가치 없음으로 보류
- `runtime/tester-portable/`: Git 제외, Lab 전용 MT5 Portable
- `runtime/complexity-refactor-v1-portable/`: Git 제외, complexity-refactor 후보 전용 MT5 Portable
- `artifacts/`: 실틱 결과, EA 출력과 빌드 로그
- `tools/`: Lab Portable 초기화·컴파일·정상 백테스트 실행기
