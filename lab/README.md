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
- `research/prior-vix-relative-regime-context-implementation-correction-v1/`: 닫힌 유효-null Program 2 / Unit 045 구현교정 sibling; 정확한 2,233건에서 LOW `-0.01456R/-0.02067 stop`, HIGH `+0.01779R/+0.03526 stop`로 양쪽 모두 `0.10R/0.05` 크기와 반대부호 관문 실패, VIX-context seed·인접 구제 없음
- `research/rc4-adverse-compression-resolution-state-v1/`: 닫힌 무효 Program 4 / Unit 046 source-free family; selector가 RC16 272건을 함께 받아 RC4 `206 → 478`로 무결성 실패, 계산된 효과 전부 비권위·수정/재실행/인접 후속 없음
- `research/rc4-adverse-compression-resolution-state-implementation-correction-v1/`: 닫힌 부분통과 Program 4 / Unit 046 구현교정 sibling; 정확한 RC4 206건에서 adverse vote는 `-0.27187R/+0.42057 stop`·4/4기간·양방향으로 통과했으나 compression-applied는 `+0.33235R/+0.09534 stop`로 stop 감소 관문 실패, 기존 RC4 관리 보존·후속 규칙 없음
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
- `research/scheduled-us-macro-decision-regime-v1/`: 닫힌 무효 Program 2 / meso Unit 058 source-free family; 선언의 FOMC ±120분 후보 0행 전제가 동일 입력에서 14행·5/5 이벤트로 반증되어 채널 잔차 계산 전에 중단, BLS 의사결정 regime·FOMC rescue·후속 없음
- `research/cross-component-same-symbol-signal-state-v1/`: 닫힌 Program 1 / meso Unit 059 source-free family; PERSIST−REVERSE는 `+0.09741R/-0.09897 stop`이나 R 크기와 Return/US30 집중 관문 실패, same-component US100도 같은 방향으로 material하여 cross-component 고유 field·후속·정책 없음
- `research/native-hold-schedule-curve-v1/`: 닫힌 무효 Program 4 / meso Unit 060 family; 독립 source/config/EX5/runtime과 3개 보유시간 벡터는 정상 동결됐지만 첫 P1 NATIVE 상세 로그에서 US30·US100·US500 모두 생성 tick 대체가 확인되어 경제판정 전 중단, 나머지 11경로·후보·인접 환경구제 없음
- `research/candidate-funnel-turnover-risk-contract-v1/`: 닫힌 무효 Program 5 / macro Unit 061 source-free family; `reserved_slots`가 active mask를 포함하는 union인데 선언이 active와 합산해 3-slot 체계에서 4·6을 만든 의미 오류로 risk-contract 판정 무효, 공식·정책 후보·같은-family 수리 없음
- `research/market-stop-reverse-lot-sizing-v1/`: 닫힌 무효 Program 5 / micro→macro Unit 062 family; fit 상세 real-tick 로그는 깨끗했지만 필수 HTML이 생성되지 않았고 사전 전체 환경 manifest도 동기화 중 변해 중앙값·후보 SET·selection/latest를 열지 않음. native stop/lot 보존, 같은-family 실행 수리 없음
- `research/all-slot-evaluation-clock-shape-v1/`: 닫힌 밀도부족 Program 3 / meso Unit 063 source-free family; 19,604개 바·151개 네이티브 판단 parity 뒤 로컬 회전율은 통과했지만 Q4 밀도와 전체 시계 폭·네이티브 비고유성·집중·기간안정 관문이 실패해 13:30 보존, 특정 시각·all-slot 후보 없음
- `research/cross-common-beta-decomposition-v1/`: 닫힌 Program 1 / meso Unit 064 source-free family; 공통분산 50.75%·제거가능분산 74.27%와 lot 중간/p90 자본 `$550/$1,000`은 확인했지만 공통평균 near-zero와 전기간·양방향 품질개선이 실패해 단일 US100 Cross 보존, 3-leg hedge seed·후보 없음
- `research/portfolio-drift-benchmark-attribution-v1/`: 닫힌 Program 5 / macro Unit 065 source-free family; pooled 순롱 `40.32%`에도 일별 시장 R² `10.01%`로 drift 귀속은 실패했고 equity-DD 정합 signed/gross benchmark가 실제를 `0/4` 기간만 이긴 반면 전략 효율은 `4/4`·pooled 통과하여 기존 절대경제 보존, benchmark/DD 규칙·후보 없음
- `research/loss-channel-risk-contract-attribution-v1/`: 닫힌 Program 4 / micro→macro Unit 066 source-free family; NONSTOP은 CP2 stressed 패자 `78.54%`이나 손실질량 `55.52%`, binding 실제 손실질량 `49.43%`, 폭 `1/4·3/6`으로 지배 관문 실패했고 STOP 사용률 중앙값이 `0.50373R` 대 `0.10325R`라 현 stop-tail 위험 해석 보존, 후보 없음
- `research/intraday-sizing-risk-clock-ratchet-v1/`: 닫힌 Program 3 / meso Unit 067 source-free family; 일중 위험자본 비율 중앙값은 CP2·binding 모두 `1.0`, 시장 lot 불일치는 `0/1,102`·`4/294`, 음성 부동손익의 불리한 결과 전달은 `0/4` 기간이라 daily sizing과 admission별 conservative risk 보존, 후보 없음
- `research/rc-compression-horizon-slot-independence-v1/`: 닫힌 Program 5 / meso→macro Unit 068 source-free family; RC 신호연관 `phi 0.224`·90일 전부 동시점유는 확인했지만 방향일치 `53.33%`, 공동손실 `1.169x`가 대조쌍 중앙 `1.506x`보다 낮고 RC 손실질량 `14.27%`라 RC16·RC4 별도 slot 보존, 후보 없음
- `research/performance-endogenous-risk-geometry-v1/`: 닫힌 부분통과 Program 4 / micro→macro Unit 069 source-free family; 전역/시간통제 자본-스톱-비용 scale은 통과했지만 국소 stop률 차이 `-0.00092`, 폭 `2/4·2/6`, stressed R `-0.05646`로 유리한 hazard 전달이 실패해 현 4%/12% 계약·gate 보존, 후보 없음
- `research/rc16-long-drift-signal-specificity-v1/`: 닫힌 애매함 Program 1 / meso Unit 070 source-free family; pooled 신호초과 `+1.330 ATR`는 passive beta 단정을 막지만 2025 방향대조 초과 `+0.069 ATR`·MAE `+0.392 ATR` 대 2026 `+2.892/-0.668 ATR`로 압축 고유가치가 기간 불안정, 후보 없음
- `research/server-calendar-drift-segmentation-v1/`: 닫힌 Program 2 / meso→macro Unit 071 source-free family; pooled gap은 양의 calendar drift의 `16.96%`, intraday는 `83.04%`이고 `4/4` 기간·`3/3` 심볼에서 intraday 우세, short gap은 작은 gap 채널의 `94.92%`지만 overnight 후보 없음
- `research/us100-book-economic-role-v1/`: 닫힌 Program 5 / macro Unit 072 source-free family; US100은 CP2 `4/4`·binding `+$162.3525`로 양수이고 US30 보호 gate는 실패, 오히려 US30→US100 상쇄 `1.57271`가 통과해 보험전용 재분류·후보 없음
- `research/order-type-realized-entry-cost-v1/`: 닫힌 Program 3 / micro→meso Unit 073 source-free family; Cross 129·Passive 92 cost-known fills 모두 기록 burden `0R`, Passive 체결 spread는 좁지만 배치 quote·미체결 반사실 부재로 비용우위·역선택·후보 없음
- `research/turnover-value-frontier-v1/`: 닫힌 애매함 Program 5 / macro Unit 074 source-free family; binding rho `-0.771` 대 CP2 `-0.429`, 3/4 기간 음수지만 P2 `+0.543` 역전·median `-0.343`로 안정 frontier 실패, fill 목표·후보 변경 없음
- `research/predecision-market-participation-state-v1/`: 닫힌 애매함 Program 2 / meso Unit 084 family; broad H1 참여상태는 유효했지만 HIGH-LOW `+0.01698R/+0.04462 stop`, 양 book `0/2`·기간 `1/4`·component `1/6` 방향폭으로 처리 후보 없음
- `research/predecision-gold-yen-risk-state-v1/`: 닫힌 애매함 Program 2 / meso Unit 088 source-free family; risk-off minus risk-on은 `+0.00766R/+0.02506 stop`, 양 book은 반대 방향이고 기간 concordance는 `0/4`; strong-null stop 경계를 `0.000057` 넘겨 처리 후보 없이 종료
- `research/cftc-leveraged-money-relative-flow-v1/`: 닫힌 no-field Program 2 / meso→macro Unit 089 source-free family; 공식 공표일 이후 CFTC Nasdaq-DJIA leveraged-money flow의 US100-US30 DID는 `+0.04807R/-0.01238 stop`으로 strong-null 통과, unconditional book 처리 보존·risk/lot seed 없음
- `research/standard-options-expiration-week-state-v1/`: 닫힌 무효 Program 2 / meso Unit 090 source-free family; 공식 Cboe 6개 원문과 49행 schedule은 저장됐지만 허용 교정 소진 뒤 acquisition receipt 직렬화가 실패해 portfolio 결과 전 무효, 만기주간 경제판정·risk/slot seed 없음
- `research/standard-options-expiration-week-state-implementation-correction-v1/`: 닫힌 애매함 Unit 090 구현교정 sibling; V1 계약을 그대로 상속한 첫 유효 경제판정은 `+0.01649R/-0.03172 stop`, 기간·component·요일 방향폭은 있었지만 크기·양 book 일치·RC4 `51.37%` 집중 gate 실패, seed·MQL·Tester·Live 없음
- `research/prior-cash-breadth-book-rotation-v1/`: 닫힌 무효 Program 1 / meso→macro Unit 091 source-free family; 공식 RSP/SPY 원문 4개와 1,044행 외부상태 CSV는 저장됐지만 허용 교정 소진 뒤 acquisition receipt 객체 구성이 실패해 CP2 결과 전 무효, breadth-conditioned book/risk/slot seed 없음
- `research/prior-cash-breadth-book-rotation-implementation-correction-v1/`: 닫힌 애매함 Unit 091 구현교정 sibling; V1 계약 그대로 첫 유효 경제판정은 US30-US100 DID `-0.00247R/-0.00109 stop`, 기간 `2:2`·양 book 동방향으로 directional 실패, component orientation 때문에 strong-null도 미완성, seed·MQL·Tester·Live 없음
- `research/cross-relative-convergence-sleeve-v1/`: 닫힌 Program 1 / meso→macro Unit 093 단일 실험 family; build 6140 V7·환경 V5의 고정 4경로가 전부 무결성 통과했다. DUAL_APPEND는 binding에서 `3.08173` starts/day와 `$72.2779` appended stressed net을 냈지만 actual max DD `$58.94 > $37.862` 한계를 넘었고 US500 binding 기여가 `-$5.4221`; latest는 `2.86667 < 3.0` starts/day였다. 불가분 US30+US500 묶음 verdict `NO_CROSS_RELATIVE_CONVERGENCE_SLEEVE_PASSED_PRESERVE_SIX_COMPONENTS`, 6전략 baseline 보존, 개별 symbol·threshold·clock·hold·risk·exit 구제나 retained seed 없음
- `research/round-number-crossing-response-v1/`: 열린 Program 1 / micro→meso Unit 094 단일 실험 family; 실제 라운드넘버와 반 칸 placebo를 비교하는 무거래 observer 1개, 12개 고정 설정과 무링크 전용 runtime이 build 6140 `0/0` 및 exact 환경으로 동결됐다. P1 US30→US100→US500 뒤 최대 한 방향만 동일 계약 P2-P4로 확인하며 구현 교정은 실험 경계가 아니다
- `engineering/protective-exit-order-reconciliation-v1/`: 현재 forward baseline을 소유하는 닫힌 정상 SL 과도주문 소유권 대조 수리 family; P4 실틱 경제 완전동등성, CXR2 `0/0 → 1/1` 승격과 다중 영속 healthy snapshot 통과
- `engineering/live-research-observation-ledger-v1/`: 검증·동결된 Lab 공학 원본; dashboard·경제·주문·core 상태 계약을 유지한 별도 candidate/lifecycle ledger가 build 6140 `0 errors / 0 warnings`, P4 `100% 실제 틱`, 현재 명세 부모와 `2,676` core payload 행 완전동등성을 통과했고, 별도 manifest의 RLO1 Live 번역은 정식 `0/0 → 1/1` 경계를 거쳐 현재 활성 소유자로 부착 완료
- `runtime/`: Git 제외, family별 독립 Portable과 임시 산출물
- `artifacts/`: 실틱 결과, EA 출력과 빌드 로그
- `tools/`: 정상 Lab compile·MT5 실행 도구

새 family는 `research/<family>/` 또는 `engineering/<family>/` 하나에 source·config·evidence를 함께 둔다. 다른 family root를 include하거나 닫힌 root를 다시 열지 않는다. 상세 강제 규칙은 `docs/OPERATING_DIRECTION.md`의 `Source topology discipline`이 권위다.

용량 정리는 같은 문서의 `Research artifact retention and storage hygiene` 단일 규칙을 따른다. 매월 첫 주말 또는 시스템 드라이브 여유 `30 GiB` 미만에서 sweep하되, 증거가 가리키는 산출물과 canonical candidate/lifecycle ledger는 보존하고 닫힌 family의 중복 Portable·Tester cache·미참조 임시 산출물만 정확한 절대경로 확인 뒤 정리한다.
