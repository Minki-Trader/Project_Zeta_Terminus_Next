# Lab

이 디렉터리는 변경 가능한 V7 소스, 동결 V6R6 대조군, Tester 설정과 DEV 산출물만 소유한다. 어떤 파일도 `live-dev/`를 include하거나 Live 상태·로그를 읽어서는 안 된다.

- `control-v6r6/`: legacy anchor의 작은 동결 대조군
- `mt5/`: V7 소스와 설정
- `research/strategy-independence-risk-allocation/`: Lab 전용 `전략 독립성·위험배분 연구`; 여섯 단독 `$100` EA와 결합 대조군, 사전 선언 및 분석
- `runtime/tester-portable/`: Git 제외, Lab 전용 MT5 Portable
- `artifacts/`: 실틱 결과, EA 출력과 빌드 로그
- `tools/`: Lab Portable 초기화·컴파일·정상 백테스트 실행기
