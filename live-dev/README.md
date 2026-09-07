# Live-Dev

이 디렉터리는 동결된 Next 배포 스냅숏과 Next 전용 운영 도구만 소유한다. Live 권한은 오직 `CURRENT_STATE.md`가 결정한다.

직접 사용자 ON 진입점은 루트의 `ZETA_NEXT_V7R_TRADING_ON.cmd`와 `tools/Open-ZetaNextV7RTradingOn.ps1`이다. 명시적인 **실제 자동매매 켜기** 버튼 뒤에만 기존 flat 종료, CURRENT_STATE/번호 상태 기록 커밋·푸시, 변경 없는 detached Master를 호출한다. 취소·창 닫기는 아무 운영 변경도 하지 않는다. 소스·EX5·SET·위험 계약과 기존 검사 구현은 그대로다. Git 충돌이나 기록 변경을 자동 병합하지 않으며, 기동 후 확인 실패는 OFF로 표시하거나 위험을 관리하는 EA를 강제 종료하지 않는다. 이 진입점은 assistant·heartbeat·스케줄러용이 아니다.

현재 `package/active/`는 닫힌 Lab `v7-rlo1-return-requalification-v1/candidate/`에서 한 번 복사한 `NEXT-E03-V7R-RLO1-0bba2ca045fe`다. 원래 V7의 position risk 4%, aggregate cap 12%, 여섯 전략과 Passive 고정 0.01 lot을 유지한다. V8과의 새 장기 비교에서 actual/stressed +$313.36/+$284.138, native relative equity DD 19.5024%로 사전 기준을 통과했다. 최근 7~8월은 +$4.66/+$3.209이며 7월 손실과 V8 대비 약한 최근 수익은 그대로 공개한다.

V8은 신규진입을 막은 상태로 복구해 total positions/orders 0/0, margin/risk 0/0, fault 0을 확인하고 최종 sequence 5340에서 정상 종료했다. 최신 잔액/평가금액은 $100.25/$100.25이며 최종 누적 프로젝트 실현손익 -$0.40만 새 실행본에 이월한다. 원래 V7과 V8의 state, 연구 ledger, 주문 identity는 채택하지 않는다.

새 Portfolio는 `ZT-PORT-NEXT-V7R-RLO1-20260907`, Magic은 `260907701..260907706`, schema는 `7R1`, 실행 버전은 `zt-next-v7-rlo1-return-portfolio-v1`이다. 새 namespace는 `ZetaTerminusNext\live\v7r-rlo1\state|research`다. `runtime/portable/`은 Live 전용 물리 설치이며 Lab/Optimization의 EA, Include, SET, 상태나 로그를 읽지 않는다.

운영 도구는 `Get-ZetaNextV7RStatus.ps1`, `Show-ZetaNextV7RDashboard.ps1`, `Start-ZetaNextV7REntriesDisabled.ps1`, `Start-ZetaNextV7RLive.ps1`이다. Master는 CURRENT_STATE의 정확한 허용 모드로 EA와 한국어 대시보드를 중복 없이 연다. 최초 기동/재시작 복구는 0/0 상태에서 하고 실제 연속 틱, 모든 심볼/타임프레임 동기화, flatness, sole owner, 해시와 fault gate를 통과해야 1/1을 허용한다. 폐장이면 EA를 신규진입 금지 상태로 유지한다.

계정과 전환 receipt는 Git 밖에 유지한다. 설치 증거는 `evidence/V7R_RETURN_INSTALLATION_V1.json`이며 후속 운영 결과는 CURRENT_STATE와 Live 증거가 소유한다. 정확한 절차는 [`Live 인계 절차`](../docs/LIVE_HANDOFF_RUNBOOK.md)를 따른다. 과거 V8의 사용자 위험수용 예외 및 activation 증거는 역사 기록으로 보존된다.
