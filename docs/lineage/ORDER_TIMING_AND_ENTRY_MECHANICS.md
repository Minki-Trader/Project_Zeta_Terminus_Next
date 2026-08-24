# 주문 형태·진입 시각·세션

- 과거 UTC/서버시각 불일치를 수정한 뒤 FPMarkets GMT+2/GMT+3 서버시각을 경제 변수로 고정했다.
- 시장가, Stop, Passive Limit, stale-price 거절, 브로커 처리지연과 다중심볼 bar 동기화를 별개 문제로 다뤘다.
- 반복 Extra timing 연구는 현재 최대 2분의 최초 admission, 전략별 결정시각, Passive 원결정봉+60분 만료를 대체할 안정적인 구조를 찾지 못했다.
- V7은 현재 순서와 시각, `RC4 → RC16 → Pressure → Return → Cross` 처리 순서 및 Passive 선처리를 그대로 유지한다.

