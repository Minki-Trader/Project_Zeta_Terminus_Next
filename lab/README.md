# Lab

이 디렉터리는 Live와 분리된 연구·공학 작업만 소유한다. 어떤 파일도 `live-dev/`를 include하거나 Live 상태·로그를 읽어서는 안 된다.

## 거시 연구 배분

Frontier 단위는 `1 진입 신호·시장 구조 / 2 외부시장·이벤트 / 3 주문·시각·세션 / 4 포지션 관리·청산 / 5 포트폴리오·자본·위험 / 7 진단·인과·메타` 중 주 프로그램 하나만 가진다. Program 6 `실행·복구·브로커 안전`은 현재 Goal 밖이다. 한 선언은 한 거시 질문에 필요한 관련 변형 2–3개를 한 번만 묶을 수 있고, 종료 뒤에는 전 프로그램을 다시 비교한다. 같은 주제의 인접 임계값·창·하위집단·심볼·이벤트·청산·사이징이나 보존 seed를 자동으로 이어서 열지 않는다.

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
- `research/cross-index-residual-response-v1/`: 닫힌 Unit 022 family; 두 번째 selected-symbol 지문 변경과 반복 rate 무결성 fault로 경제 판정 전 무효, latest·후속 prototype 없음
- `research/same-strategy-outcome-memory-v1/`: 닫힌 Unit 023 source-free family; 2,233 lifecycle·2,209 인과쌍 무결성 통과 뒤 전 전략이 pooled `0.10R` 효과 게이트 미달, 반응 후보·변형 구제 없음
- `research/passive-fill-age-value-v1/`: 닫힌 Unit 024 source-free family; 594 fill 무결성 통과 뒤 pooled `rho=-0.10138`, tail `-0.02895R`, stop 효과·일관성 미달로 반응 후보 없음
- `research/initial-stop-geometry-value-v1/`: 닫힌 Unit 025 source-free family; 전 전략 pooled `|rho|<0.20`, tail `|효과|<0.10R`, RC4·Return 근접값도 기간·stop 일관성 미달로 후보 없음
- `research/closed-drawdown-state-value-v1/`: 닫힌 Unit 026 source-free family; 전 전략 pooled `|rho|<0.20`, RC16 tail 크기는 통과했으나 P3 집중·기간/stop 폭 미달로 반응 후보 없음
- `research/us500-shock-response-v1/`: 닫힌 Unit 027 fresh observer family; P1과 허용된 clean 재실행 모두 현재월 필수 US500 `Bases` 틱 지문이 바뀌어 경제 집계 전 무효, P2-P4·prototype 없음
- `research/us100-session-reopen-discontinuity-v1/`: 닫힌 Unit 028 family; 보존 P1 상세 로그의 `every tick generation used`를 Unit 031에서 뒤늦게 확인해 경제판정 권위 철회, prototype 없음은 유지
- `research/us30-compression-break-response-v1/`: 닫힌 Unit 029 fresh observer family; P1 원자료가 `every tick generation used`로 100% 실제 틱 관문을 실패해 경제행 미열람, P2-P4·prototype 없음
- `research/us100-tick-flow-imbalance-response-v1/`: 닫힌 Unit 030 family; 보존 P1 상세 로그의 생성 대체 때문에 경제판정 권위 철회, prototype 없음은 유지
- `research/us100-failed-extreme-auction-response-v1/`: 닫힌 Unit 031 family; P1 HTML 100% 표기와 달리 상세 로그가 1,920분 부재·484분 폐기 및 생성 대체를 증명해 4,129 경제행 미열람, prototype 없음
- `research/us100-realized-variance-asymmetry-response-v1/`: 닫힌 Unit 032 fresh observer family; 경로길이 교정 뒤 P1은 정상 종료·상세 경고 0이었으나 HTML이 `99% 실제 틱`으로 고정 100% 관문 실패, 1,529 경제행 미열람·P2-P4·prototype 없음
- `research/us100-directional-path-efficiency-response-v1/`: 닫힌 Unit 033 fresh observer family; P1은 1,127건 정상 해결·상세 경고 0이었으나 HTML `99% 실제 틱`으로 고정 100% 관문 실패, 경제행 미열람·P2-P3·prototype 없음
- `research/native-direction-asymmetry-value-v1/`: 닫힌 Unit 034 source-free family; 전 전략 return `|SELL-BUY|<0.10R`, RC4 stop 부담은 컸으나 수익효과 미달로 방향 처리 후보 없음
- `research/same-strategy-interbirth-gap-value-v1/`: 닫힌 Unit 035 source-free family; 전 전략 밀도는 통과했으나 pooled `|rho|<0.20`이고 RC16 근접 tail도 `0.08111R/-0.03409`로 수익·stop 크기 미달, cadence 처리 후보 없음
- `research/us500-close-location-pressure-response-v1/`: 닫힌 Unit 036 fresh observer family; P1은 3,088건 정상 해결·상세 경고 0이었으나 HTML `99% 실제 틱`으로 고정 100% 관문 실패, 경제행 미열람·P2-P3·prototype 없음
- `research/strategy-occupancy-slot-value-v1/`: 닫힌 Unit 037 source-free family; 선행 슬롯가치 순위 상관 `-0.257/-0.257/+0.143`, 단순 R 대비 증분 중앙값 `-0.114`로 우선순위 Proxy 없음
- `research/us500-ordinal-acceleration-response-v1/`: 닫힌 Unit 038 fresh observer family; 정렬 P1 `100% 실제 틱`·739건 빈도 통과, double-spread continuation/reversion `-$12.81/-$7.86`로 방향·prototype 없음
- `research/portfolio-cost-resilience-envelope-v1/`: 닫힌 Program 5 / Unit 039 source-free family; 전체 포트폴리오는 4x에도 `+$332.7631`, RC16·RC4·Cross가 고정 관문 통과, RC16 추가-lot Proxy seed 하나만 보존하되 자동 후속은 열지 않음
- `research/one-hour-adverse-exit-management-v1/`: 닫힌 Program 4 / Unit 040 family; P1 control HTML은 100%였으나 상세 tick 생성대체·시장/심볼 지문 변이·swap anchor 불일치로 경제판정 전 무효, 나머지 15경로·후보 없음
- `research/scheduled-us-macro-event-exposure-v1/`: 닫힌 Program 2 / Unit 041 source-free family; 보유 노출 residual `+0.11686R`, 발표 후 진입 `+0.03362R`로 두 역할 모두 광범위 악화 관문 실패, mark-path seed·인접 이벤트 구제 없음
- `research/server-new-york-dst-mismatch-session-v1/`: 닫힌 Program 3 / Unit 042 source-free family; 봄 `-0.03823R/+0.04509` stop, 가을 `+0.06071R/-0.05218` stop으로 크기·기간 폭·공통 방향 관문 실패, clock-remap seed·인접 세션 후속 없음
- `research/frontier-evidence-path-yield-audit-v1/`: 닫힌 Program 7 / Unit 043 source-free meta family; 권위 경제판정 도달은 추적증거 `10/10`, fresh observer `1/9`, 후자는 무결성 이탈 `8/9`; 이는 alpha·기본 연구경로 증명이 아니며 seed 1개·거래후보 0개, 후속 없음
- `research/rc16-deposit-funded-incremental-volume-proxy-v1/`: 닫힌 무효 Program 5 / Unit 044 source-free family; 선택배분은 순수 경제 관문을 모두 통과했으나 `$200/$300`에서 고정 4% position cap을 `229/231`회 위반해 allocation·EA seed 없음, 인접 sizing 구제 없음
- `research/prior-vix-relative-regime-context-v1/`: 닫힌 무효 Program 2 / Unit 045 source-free family; 공식 Cboe 스냅샷과 16,477행은 통과했으나 period selector가 0 lifecycle을 반환해 경제판정 전 무효, VIX-context seed·구제 없음
- `research/rc4-adverse-compression-resolution-state-v1/`: 닫힌 무효 Program 4 / Unit 046 source-free family; selector가 RC16 272건을 함께 받아 RC4 `206 → 478`로 무결성 실패, 계산된 효과 전부 비권위·수정/재실행/인접 후속 없음
- `research/new-york-week-edge-entry-state-v1/`: 닫힌 Program 3 / Unit 047 source-free family; 월요일 `-0.00544R/-0.00894 stop`, 금요일 `+0.00315R/+0.01697 stop`으로 둘 다 크기·일관성 관문 실패, 인접 달력/세션 후속 없음
- `research/bidirectional-signal-transition-state-v1/`: 닫힌 Program 1 / Unit 048 source-free family; US30 지속-반전 `+0.04204R/-0.05170 stop`은 수익크기·양전략 stop 일관성 실패, US100 `+0.00925R/+0.00198 stop`은 무정보, 인접 신호 후속 없음
- `research/prior-treasury-curve-move-context-v1/`: 닫힌 Program 2 / Unit 049 source-free family; 공식 미 재무부 2Y·10Y 동반상승 `-0.01578R/+0.00529 stop`, 동반하락 `+0.01560R/-0.00898 stop`으로 둘 다 크기·폭 관문 실패, 인접 금리 후속 없음
- `research/natural-book-drawdown-complementarity-v1/`: 닫힌 Program 5 / Unit 050 source-free family; US30은 US100 최대 DD를 4/4 기간 광범위하게 상쇄했지만 역방향은 20% 기준 2/4와 P4 손실증폭으로 실패, 일방향 진단만 유지하고 배분·lot·slot 후속 없음
- `research/macro-frontier-attrition-topology-v1/`: 닫힌 Program 7 / Unit 051 source-free family; Unit 039-050 funnel `12→8→3→0`, 권위 `4/12`·구분력 `5/8`·후보번역 `3/3` 모두 실질 attrition으로 단일 병목 없음, 후속 감사·기본 lane·프로그램 억제 없음
- `research/held-position-first-peer-exit-state-v1/`: 닫힌 Program 4 / Unit 052 source-free family; peer stop `+0.05546R/+0.00736 stop`, peer native `+0.03656R/-0.08223 stop`이나 전자는 크기·일관성, 후자는 R크기·Return 집중 실패, 관리 후속 없음
- `research/us500-monthly-range-break-response-v1/`: 닫힌 Program 1 / Unit 053 family; P1 2025 무결성·H1/H2 `10/12`는 통과했으나 upper/lower `18/4`로 양방향 최소 `5/5` 미달, 경제행·P2·prototype 미개봉
- `research/portfolio-loss-cooccurrence-topology-v1/`: 닫힌 Program 5 / Unit 054 source-free family; 다전략 손실일 `1.0226x`, 양 자연책 손실일 `1.0554x` 독립기대 발생으로 둘 다 `1.25x` 관문 미달, 공통손실 대응·배분·lot·slot 후속 없음
- `research/macro-context-composition-confounding-v1/`: 닫힌 Program 7 / Unit 055 source-free family; 12개 맥락 대비의 R 보정은 전부 `0.05R` 미만, stop 민감 4건도 Units 041/052·Programs 2/4에 집중되어 광범위 구성혼재 진단 실패, 인접 estimator·weighting·meta 후속 없음
- `research/intraday-portfolio-entry-handoff-v1/`: 닫힌 Program 3 / meso Unit 056 source-free family; incumbent 진입은 `+0.02331R/+0.01179 stop`, 자연청산 완전-flat 뒤 재진입은 `-0.00221R/+0.04228 stop`으로 크기·일관성 관문 실패, density 보조값 오류는 정확한 기출력 count로 공개 정정했고 재집계·인접 timing 후속 없음
- `research/first-peer-profit-memory-checkpoint-v1/`: 닫힌 Program 4 / micro Unit 057 source-free family; 첫 peer 자연청산 때 이익 유지 상태는 최종 `+0.36149R/-0.10313 stop`로 넓게 좋았지만 이후 잔여경로는 `+0.02200R`뿐이라 현재 가치 표식으로만 판정, 관리·확대관찰·인접 후속 없음
- `research/scheduled-us-macro-decision-regime-v1/`: 열린 Program 2 / meso Unit 058 source-free family; 공식 CPI·고용 발표 전후 120분의 평가·신호·기존노출 gate·총위험 열을 정확한 동일 component/요일/시각 비발표 행과 비교하도록 선언 동결, 결과·후속 미개봉
- `engineering/protective-exit-order-reconciliation-v1/`: 현재 forward baseline을 소유하는 닫힌 정상 SL 과도주문 소유권 대조 수리 family; P4 실틱 경제 완전동등성, CXR2 `0/0 → 1/1` 승격과 다중 영속 healthy snapshot 통과
- `engineering/live-research-observation-ledger-v1/`: 검증·동결된 단일 공학 후보; dashboard·경제·주문·core 상태 계약을 유지한 별도 candidate/lifecycle ledger가 build 6140 `0 errors / 0 warnings`, P4 `100% 실제 틱`, 현재 명세 부모와 `2,676` core payload 행 완전동등성을 통과했으며 오늘 기회 보존을 위해 Live 승격만 대기
- `runtime/`: Git 제외, family별 독립 Portable과 임시 산출물
- `artifacts/`: 실틱 결과, EA 출력과 빌드 로그
- `tools/`: 정상 Lab compile·MT5 실행 도구

새 family는 `research/<family>/` 또는 `engineering/<family>/` 하나에 source·config·evidence를 함께 둔다. 다른 family root를 include하거나 닫힌 root를 다시 열지 않는다. 상세 강제 규칙은 `docs/OPERATING_DIRECTION.md`의 `Source topology discipline`이 권위다.

용량 정리는 같은 문서의 `Research artifact retention and storage hygiene` 단일 규칙을 따른다. 매월 첫 주말 또는 시스템 드라이브 여유 `30 GiB` 미만에서 sweep하되, 증거가 가리키는 산출물과 canonical candidate/lifecycle ledger는 보존하고 닫힌 family의 중복 Portable·Tester cache·미참조 임시 산출물만 정확한 절대경로 확인 뒤 정리한다.
