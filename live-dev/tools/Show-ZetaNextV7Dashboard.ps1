[CmdletBinding()]
param(
    [ValidateRange(2, 60)]
    [int]$RefreshSeconds = 5,
    [ValidateSet('Auto', 'EntriesDisabled', 'LivePreflight', 'Live')]
    [string]$ExpectedMode = 'Auto',
    [switch]$Once
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$liveDevRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$projectRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $liveDevRoot))
$statePath = Join-Path $projectRoot 'CURRENT_STATE.md'
$statusScript = Join-Path $PSScriptRoot 'Get-ZetaNextV7Status.ps1'
$windowTitle = 'Project Zeta Terminus Next V7 Live-Dev 대시보드'
$script:RenderingForGui = $false

foreach ($requiredPath in @($statePath, $statusScript)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required Next V7 dashboard file is missing: $requiredPath"
    }
}

function Test-V7OperatorAuthorized {
    $text = Get-Content -LiteralPath $statePath -Raw
    return $text -match 'Next V7 new-entry authorization:\s+`ENABLED`'
}

function Write-UiLine {
    param(
        [AllowEmptyString()][string]$Text = '',
        [ConsoleColor]$Color = [ConsoleColor]::Gray
    )
    Write-Host $Text -ForegroundColor $Color
}

function Write-Rule {
    param([string]$Title = '')
    $width = 92
    try { $width = [math]::Max(70, [math]::Min(120, [Console]::WindowWidth - 1)) } catch { }
    if ([string]::IsNullOrWhiteSpace($Title)) {
        Write-UiLine -Text ('─' * $width) -Color DarkGray
        return
    }
    $prefix = "── $Title "
    $tail = [math]::Max(2, $width - $prefix.Length)
    Write-UiLine -Text ($prefix + ('─' * $tail)) -Color DarkCyan
}

function Format-Money {
    param($Value)
    if ($null -eq $Value) { return '—' }
    return ('$' + ('{0:N2}' -f [double]$Value))
}

function Format-Price {
    param($Value)
    if ($null -eq $Value -or [double]$Value -le 0) { return '—' }
    return ('{0:0.00###}' -f [double]$Value)
}

function Format-Volume {
    param($Value)
    if ($null -eq $Value -or [double]$Value -le 0) { return '—' }
    return ('{0:0.00###}' -f [double]$Value)
}

function Format-PositiveMoney {
    param($Value)
    if ($null -eq $Value -or [double]$Value -le 0) { return '—' }
    return (Format-Money -Value $Value)
}

function Format-ServerEpochTime {
    param($Value)

    if ($null -eq $Value -or [long]$Value -le 0) { return '—' }
    try {
        $epochWallClock = [datetime]::SpecifyKind(
            [datetime]'1970-01-01 00:00:00',
            [DateTimeKind]::Unspecified
        )
        return $epochWallClock.AddSeconds([long]$Value).ToString('yyyy-MM-dd HH:mm')
    } catch {
        return '—'
    }
}

function Format-SignalValue {
    param($Known, $Value)
    if ($null -eq $Known -or [int]$Known -ne 1 -or $null -eq $Value) { return '—' }
    return ('{0:0.0000}' -f [double]$Value)
}

function Get-KoreanDirection {
    param($Direction)
    if ($null -eq $Direction) { return '—' }
    switch ([int]$Direction) {
        1 { '매수' }
        -1 { '매도' }
        default { '—' }
    }
}

function Get-KoreanSignalDecision {
    param($Known, $Passed)
    if ($null -eq $Known -or [int]$Known -ne 1) { return '미산출' }
    if ([int]$Passed -eq 1) { return '통과' }
    if ([int]$Passed -eq 0) { return '미충족' }
    return '판정 전'
}

function Get-KoreanEntryResult {
    param([string]$Result)
    switch ($Result) {
        'NOT_EVALUATED_SINCE_START' { '시작 후 평가 전' }
        'CHECKING_SIGNAL' { '신호 계산 중' }
        'SIGNAL_NOT_MET' { '진입 기준 미충족' }
        'SIGNAL_MET_ORDER_CHECK' { '신호 통과 · 주문 점검' }
        'SESSION_EXCLUDED' { '휴장일 제외' }
        'OUTSIDE_DECISION_SESSION' { '평가 세션 밖' }
        'DATA_UNAVAILABLE' { '평가 데이터 대기' }
        'ENTRY_DELAY_EXCEEDED' { '평가 허용 지연 초과' }
        'COOLDOWN' { '재진입 대기' }
        'ENTRY_BLOCKED' { '신규 진입 차단' }
        'OWNERSHIP_BLOCKED' { '소유권 점검 차단' }
        'EXISTING_EXPOSURE' { '기존 포지션 보유 중' }
        'DUPLICATE_EXPOSURE' { '중복 포지션 감지' }
        'SHADOW_ACCEPTED_OCCUPANCY' { 'RC4 그림자 포지션 점유' }
        'QUOTE_UNAVAILABLE' { '실행 호가 대기' }
        'VOLUME_INVALID' { '주문 수량 부적합' }
        'LIMIT_PRICE_INVALID' { '지정가 계산 실패' }
        'PRICE_DISTANCE_BLOCKED' { '지정가 거리 조건 차단' }
        'PROTECTION_OR_RISK_BLOCKED' { '보호선·위험 심사 차단' }
        'TRADE_SESSION_BLOCKED' { '거래 세션 차단' }
        'MARGIN_BLOCKED' { '증거금 심사 차단' }
        'PERSISTENCE_FAILED' { '상태 저장 실패' }
        'BROKER_REJECTED' { '브로커 주문 거절' }
        'PENDING_ORDER' { '지정가 주문 대기 중' }
        'POSITION_OPEN' { '포지션 진입 완료' }
        'SAFETY_STOP' { '안전 정지' }
        default {
            if ([string]::IsNullOrWhiteSpace($Result)) { '—' } else { $Result }
        }
    }
}

function Get-EstimatedServerEpoch {
    param([Parameter(Mandatory)]$Status)

    if ([string]::IsNullOrWhiteSpace([string]$Status.server_time) -or
        $null -eq $Status.snapshot_age_seconds) {
        return $null
    }
    try {
        $serverSnapshot = [datetime]::ParseExact(
            [string]$Status.server_time,
            'yyyy.MM.dd HH:mm:ss',
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::None
        )
        $serverNow = $serverSnapshot.AddSeconds([double]$Status.snapshot_age_seconds)
        $epochWallClock = [datetime]::SpecifyKind(
            [datetime]'1970-01-01 00:00:00',
            [DateTimeKind]::Unspecified
        )
        return [long][math]::Floor(($serverNow - $epochWallClock).TotalSeconds)
    } catch {
        return $null
    }
}

function Format-RemainingHold {
    param($Seconds)

    if ($null -eq $Seconds) { return '시간 확인 불가' }
    $totalSeconds = [math]::Max(0L, [long]$Seconds)
    if ($totalSeconds -eq 0) { return '청산 확인 중' }
    $hours = [math]::Floor($totalSeconds / 3600)
    $minutes = [math]::Floor(($totalSeconds % 3600) / 60)
    $secondsPart = $totalSeconds % 60
    return '{0:00}:{1:00}:{2:00}' -f $hours, $minutes, $secondsPart
}

function Get-ComponentView {
    param([string]$ComponentId)
    # Display-only descriptions mirror the frozen active V7 source. They are
    # never consumed by the EA and cannot alter an entry decision.
    switch ($ComponentId) {
        'ZT-M30-US30-RANGE-COMP-61f61deaba' {
            return [pscustomobject]@{ Short = 'RC16'; Name = 'US30 M30 16봉 범위압축'; HoldMinutes = 240; TimeframeSeconds = 1800; HoldBars = 8; EarlyExit = $false; SignalLabel = '압축값'; EntryRule = '16봉 압축값 ≥ +1.5 · 매수'; EvaluationWindow = '서버 13:30~13:32' }
        }
        'ZT-M30-US30-RANGE-COMP-64efb16616' {
            return [pscustomobject]@{ Short = 'RC4'; Name = 'US30 M30 4봉 범위압축'; HoldMinutes = 360; TimeframeSeconds = 1800; HoldBars = 12; EarlyExit = $false; SignalLabel = '압축값'; EntryRule = '4봉 압축 절대값 ≥ 1.5 · 부호 방향'; EvaluationWindow = '서버 13:00~13:02' }
        }
        'ZT-H1-US100-CROSS-IN-14b72317b7' {
            return [pscustomobject]@{ Short = 'Cross'; Name = 'US100 H1 상대모멘텀'; HoldMinutes = 240; TimeframeSeconds = 3600; HoldBars = 4; EarlyExit = $false; SignalLabel = '상대 z'; EntryRule = 'US100 상대모멘텀 |z| ≥ 0.5 · 부호 방향'; EvaluationWindow = '서버 17:00~17:02' }
        }
        'ZT-M30-US30-INTRADAY-R-2eb111fc46' {
            return [pscustomobject]@{ Short = 'Pressure'; Name = 'US30 M30 장중 압력'; HoldMinutes = 240; TimeframeSeconds = 1800; HoldBars = 8; EarlyExit = $false; SignalLabel = '압력값'; EntryRule = '장중 압력 절대값 ≥ 0.5 · 부호 방향'; EvaluationWindow = '서버 15:00~15:02' }
        }
        'ZT-H1-US30-RETURN-I-c870a788ec' {
            return [pscustomobject]@{ Short = 'Return'; Name = 'US30 H1 충격 반전'; HoldMinutes = 360; TimeframeSeconds = 3600; HoldBars = 6; EarlyExit = $false; SignalLabel = '4H 충격'; EntryRule = '4H 정규화 수익충격 ≤ -0.5 · 매수'; EvaluationWindow = '서버 16:00~16:02' }
        }
        'ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8' {
            return [pscustomobject]@{ Short = 'Passive'; Name = 'US100 M15 충격 확장 지정가'; HoldMinutes = 240; TimeframeSeconds = 900; HoldBars = 16; EarlyExit = $true; SignalLabel = '충격상태'; EntryRule = '12봉 충격상태 |값| ≥ 1.0 · 역방향 지정가'; EvaluationWindow = '완료봉 서버 12:00~15:45 · 다음 M15 시작 후 2분' }
        }
        default {
            return [pscustomobject]@{ Short = 'Unknown'; Name = $ComponentId; HoldMinutes = 0; TimeframeSeconds = 0; HoldBars = 0; EarlyExit = $false; SignalLabel = '신호값'; EntryRule = '기준 확인 불가'; EvaluationWindow = '평가 시각 확인 불가' }
        }
    }
}

function Get-KoreanEvent {
    param([string]$Name)
    switch ($Name) {
        'START' { 'EA 시작' }
        'RESUME' { 'EA 재시작 복구' }
        'STOP' { 'EA 정상 종료' }
        'SIGNAL_DECIDED' { '신호 결정 기록' }
        'ORDER_ATTEMPTED' { '주문 시도 기록' }
        'BROKER_STATE_ADOPTED' { '브로커 상태 대조 완료' }
        'ARC_CHECKPOINT' { 'RC4 손절선 조정 판단' }
        'ARC_COMPRESSED' { 'RC4 보호선 압축 성공' }
        'ARC_REFUSED' { 'RC4 기존 손절 유지' }
        'ARC_MODIFY_ALREADY_APPLIED' { 'RC4 목표 보호선 이미 적용' }
        'ARC_MODIFY_RETRY_INTENT' { 'RC4 동일 목표 1회 재시도 예약' }
        'ARC_MODIFY_RETRY_HOLD' { 'RC4 재시도 실패 · 기존 손절 유지' }
        'ARC_MODIFY_NONRETRYABLE_HOLD' { 'RC4 비재시도 오류 · 기존 손절 유지' }
        'ARC_MODIFY_RETRY_ILLEGAL_HOLD' { 'RC4 재시도 조건 불법 · 기존 손절 유지' }
        'ARC_MODIFY_RECOVERED' { 'RC4 보호선 재대조 복구' }
        'ARC_MODIFY_RESTART_HOLD' { 'RC4 재시작 대조 · 기존 손절 유지' }
        'ARC_SHADOW_ACTIVATION_SEALED' { 'RC4 그림자 시작경계 봉인' }
        'ARC_SHADOW_ACTIVATION_SEAL_PENDING' { 'RC4 그림자 경계 봉인 대기' }
        'ARC_SHADOW_CURSOR_CHECKPOINT' { 'RC4 그림자 커서 저장' }
        'ARC_SHADOW_GAP_COMPLETE' { 'RC4 누락구간 재구성 완료' }
        'ARC_SHADOW_RELEASED' { 'RC4 그림자 점유 해제' }
        'SAFETY_STOP' { '안전 정지' }
        default { $Name }
    }
}

function Get-KoreanAlert {
    param([string]$Alert)
    if ($Alert -like 'project_terminal_process_count=*') { return 'Zeta MT5 프로세스가 정확히 하나가 아님' }
    if ($Alert -like 'stale_snapshot_seconds=*') { return 'EA 상태 갱신이 3분 넘게 멈춤' }
    if ($Alert -like 'entries=*') { return '신규 주문 허용값이 실행 모드와 다름' }
    if ($Alert -like 'terminal_allow_live_trading=*') { return '터미널 자동매매 설정이 실행 모드와 다름' }
    if ($Alert -like 'runtime_config_missing=*') { return '현재 실행 모드의 터미널 설정이 없음' }
    if ($Alert -like 'runtime_set_missing=*' -or $Alert -like 'runtime_set_entries_mismatch=*') { return '현재 실행 모드의 EA 설정이 잘못됨' }
    if ($Alert -eq 'runtime_mode_unrecognized' -or $Alert -like 'runtime_mode=*') { return '실행 중인 MT5 모드를 확인할 수 없음' }
    if ($Alert -eq 'next_v7_live_authorization_missing') { return 'Next V7 신규 주문 권한이 상태 문서에 없음' }
    if ($Alert -eq 'next_v7_current_snapshot_unavailable') { return 'Next V7 상태 파일을 아직 읽을 수 없음' }
    if ($Alert -eq 'next_v7_ex5_missing' -or $Alert -eq 'next_v7_ex5_hash_mismatch') { return '동결된 V7 EX5가 없거나 해시가 다름' }
    if ($Alert -like 'legacy_terminus_terminal_running=*') { return 'Legacy Terminus 터미널이 실행 중이므로 Next는 시작할 수 없음' }
    if ($Alert -like 'other_next_terminal_running=*') { return '다른 Next 터미널이 실행 중임' }
    if ($Alert -like 'snapshot_identity=*') { return '실행 중 EA의 Next V7 신분이 다름' }
    if ($Alert -like 'component_identity=*' -or $Alert -like 'duplicate_component_identity=*') { return '전략 Magic 또는 구성요소 신분 불일치' }
    if ($Alert -like 'safety_stopped=*') { return 'EA 안전 정지 발생' }
    if ($Alert -like 'persistence_failed=*') { return '상태 저장 실패' }
    if ($Alert -like 'broker_mismatch=*') { return '브로커/로컬 상태 불일치' }
    if ($Alert -like 'foreign_exposure=*') { return '소유권 밖 노출 감지' }
    if ($Alert -like 'rc4_shadow_*' -or $Alert -like 'rc4_activation_seal_*') { return "RC4 복구·봉인 오류: $Alert" }
    return $Alert
}

function Render-Dashboard {
    param([Parameter(Mandatory)]$Status)

    if (-not $Once -and -not $script:RenderingForGui) { Clear-Host }
    $healthy = [bool]$Status.healthy
    $healthText = if ($healthy) { '● 정상' } else { '● 확인 필요' }
    $healthColor = if ($healthy) { [ConsoleColor]::Green } else { [ConsoleColor]::Red }
    $hasSnapshot = -not [string]::IsNullOrWhiteSpace([string]$Status.execution_version)
    $liveMode = ([string]$Status.operator_mode -eq 'NEXT_V7_LIVE')
    $entryReady = ($hasSnapshot -and $liveMode -and
        [int]$Status.new_entries_input -eq 1 -and
        [int]$Status.new_entries_effective -eq 1)
    $entriesDisabledReady = ($hasSnapshot -and [int]$Status.expected_new_entries -eq 0 -and
        [int]$Status.new_entries_input -eq 0 -and
        [int]$Status.new_entries_effective -eq 0)
    $entryText = if (-not $hasSnapshot) { '상태 대기' } elseif ($entryReady) { '허용 정상 (1/1)' } elseif ($entriesDisabledReady) { '차단 정상 (0/0)' } else { '실행 모드 불일치' }
    $entryColor = if (-not $hasSnapshot) { [ConsoleColor]::Yellow } elseif ($entryReady -or $entriesDisabledReady) { [ConsoleColor]::Green } else { [ConsoleColor]::Red }
    $terminalTradingText = if ([int]$Status.terminal_allow_live_trading -eq 1) { 'ON' } else { 'OFF' }
    $liveAuthorityText = if ([bool]$Status.live_promotion_authorized) { '허용' } else { '없음' }
    $modeLine = if ($entryReady) {
        '신규 주문 허용 · Next V7 전용 Magic/상태 사용'
    } elseif ($entriesDisabledReady) {
        '신규 주문 차단 · Next V7 전용 Magic/상태 사용'
    } else {
        '신규 주문 준비 안 됨 · 아래 안전상태와 경고 확인'
    }
    $modeColor = if ($entryReady -or $entriesDisabledReady) { [ConsoleColor]::Green } else { [ConsoleColor]::Red }

    Write-UiLine -Text 'PROJECT ZETA TERMINUS NEXT · V7 LIVE-DEV' -Color White
    Write-UiLine -Text $modeLine -Color $modeColor
    Write-UiLine -Text ("{0}  |  KST {1}  |  서버 {2}" -f $healthText, (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $Status.server_time) -Color $healthColor
    Write-UiLine -Text ("PID {0}  ·  상태순번 {1}  ·  스냅샷 {2}초 전  ·  {3}초마다 갱신" -f $Status.project_terminal_pid, $Status.state_sequence, $Status.snapshot_age_seconds, $RefreshSeconds) -Color Gray

    Write-Rule -Title '가장 중요한 안전상태'
    Write-UiLine -Text ("신규 주문: {0}  |  터미널 자동매매: {1}  |  Next Live 권한: {2}" -f $entryText, $terminalTradingText, $liveAuthorityText) -Color $entryColor
    $identityOk = ($hasSnapshot -and [int]$Status.account_binding_configured -eq 1 -and [int]$Status.account_identity_match -eq 1)
    $identityText = if (-not $hasSnapshot) { '계좌 대조 대기' } elseif ($identityOk) { '계좌 일치' } else { '계좌 불일치' }
    $faultOk = ($hasSnapshot -and [int]$Status.safety_stopped -eq 0 -and [int]$Status.persistence_failed -eq 0 -and [int]$Status.broker_mismatch -eq 0 -and [int]$Status.foreign_exposure -eq 0)
    $faultText = if (-not $hasSnapshot) { '결함판정 대기' } elseif ($faultOk) { '치명 결함 없음' } else { '결함 감지' }
    $safetyColor = if (-not $hasSnapshot) { [ConsoleColor]::Yellow } elseif ($identityOk -and $faultOk) { [ConsoleColor]::Green } else { [ConsoleColor]::Red }
    $connectionText = if ($hasSnapshot) { [string]$Status.terminal_connected } else { '대기' }
    Write-UiLine -Text ("연결 {0}  |  {1}  |  {2}" -f $connectionText, $identityText, $faultText) -Color $safetyColor

    Write-Rule -Title '계좌 · 위험 (EA 로컬 스냅샷)'
    Write-UiLine -Text ("잔고 {0}  |  자산 {1}  |  증거금 {2}" -f (Format-Money $Status.account_balance), (Format-Money $Status.account_equity), (Format-Money $Status.account_margin)) -Color Cyan
    Write-UiLine -Text ("프로젝트 실현손익 {0}  |  단계잔고 {1}  |  2x비용 스트레스잔고 {2}" -f (Format-Money $Status.project_realized_net), (Format-Money $Status.project_stage_balance), (Format-Money $Status.stressed_balance)) -Color Gray
    Write-UiLine -Text ("현재 계획위험 {0}  |  관측 최대 계획위험 {1}" -f (Format-Money $Status.aggregate_planned_risk), (Format-Money $Status.maximum_aggregate_planned_risk)) -Color Gray

    Write-Rule -Title '6개 전략 · 보유 및 진입평가'
    $estimatedServerEpoch = Get-EstimatedServerEpoch -Status $Status
    foreach ($component in @($Status.components)) {
        $view = Get-ComponentView -ComponentId ([string]$component.component_id)
        $holdLabel = if ([bool]$view.EarlyExit) {
            "최장 보유 $($view.HoldMinutes)분"
        } else {
            "보유 $($view.HoldMinutes)분"
        }
        $hasPosition = ([long]$component.position_identifier -gt 0)
        $positionState = if ($hasPosition) {
            $remainingSeconds = $null
            if ([long]$component.entry_time -gt 0 -and
                [long]$view.TimeframeSeconds -gt 0 -and
                [long]$view.HoldBars -gt 0 -and
                $null -ne $estimatedServerEpoch) {
                $entryBarTime = [long]([math]::Floor([long]$component.entry_time / [long]$view.TimeframeSeconds) * [long]$view.TimeframeSeconds)
                $scheduledCloseTime = $entryBarTime + ([long]$view.HoldBars * [long]$view.TimeframeSeconds)
                $remainingSeconds = [math]::Max(0L, $scheduledCloseTime - [long]$estimatedServerEpoch)
            }
            "$(Get-KoreanDirection $component.entry_direction) $(Format-Volume $component.entry_volume) · 진입 서버 $(Format-ServerEpochTime $component.entry_time) · SL $(Format-Price $component.entry_stop_loss) · 위험 $(Format-PositiveMoney $component.entry_planned_risk)"
        } else {
            '현재 보유 없음'
        }
        $managementState = if ($hasPosition) {
            "$holdLabel · 남은 $(Format-RemainingHold -Seconds $remainingSeconds)"
        } else {
            $holdLabel
        }
        $evaluationTime = Format-ServerEpochTime $component.entry_check_bar
        $signalValue = Format-SignalValue $component.entry_check_signal_known $component.entry_check_signal_value
        $signalDecision = Get-KoreanSignalDecision $component.entry_check_signal_known $component.entry_check_signal_passed
        $entryResult = Get-KoreanEntryResult ([string]$component.entry_check_result)
        $color = if ($hasPosition) { [ConsoleColor]::Yellow } else { [ConsoleColor]::Gray }
        Write-UiLine -Text ("[{0}] {1}  ·  Magic {2}" -f $view.Short, $view.Name, $component.magic) -Color White
        Write-UiLine -Text ("     보유: {0}  ·  관리: {1}" -f $positionState, $managementState) -Color $color
        Write-UiLine -Text ("     기준: {0}  ·  평가창: {1}" -f $view.EntryRule, $view.EvaluationWindow) -Color DarkCyan
        Write-UiLine -Text ("     최근평가: 서버 {0}  ·  {1} {2}  ·  신호 {3}  ·  {4}" -f $evaluationTime, $view.SignalLabel, $signalValue, $signalDecision, $entryResult) -Color Gray
        Write-UiLine -Text ("     주문후보: {0}  ·  가격 {1}  ·  수량 {2}  ·  SL {3}  ·  위험 {4}" -f (Get-KoreanDirection $component.entry_check_direction), (Format-Price $component.entry_check_order_price), (Format-Volume $component.entry_check_volume), (Format-Price $component.entry_check_stop_loss), (Format-PositiveMoney $component.entry_check_planned_risk)) -Color Gray
    }

    Write-Rule -Title '최근 V7 이벤트'
    $events = @($Status.latest_events)
    if ($events.Count -eq 0) {
        Write-UiLine -Text '기록된 이벤트 없음' -Color DarkGray
    } else {
        foreach ($event in $events) {
            $eventColor = if ([string]$event.event -match 'FAIL|MISMATCH|SAFETY|PRE_BOUNDARY') { [ConsoleColor]::Red } elseif ([string]$event.event -match 'RETRY|PENDING|HOLD|REFUSED') { [ConsoleColor]::Yellow } else { [ConsoleColor]::Gray }
            Write-UiLine -Text ("{0}  {1}  ·  {2}  ·  {3}" -f $event.server_time, (Get-KoreanEvent ([string]$event.event)), $event.component_id, $event.detail) -Color $eventColor
        }
    }

    if (@($Status.warnings).Count -gt 0) {
        Write-Rule -Title '진행 중 상태'
        foreach ($warning in @($Status.warnings)) {
            Write-UiLine -Text ("△ {0}" -f $warning) -Color Yellow
        }
    }
    if (@($Status.alerts).Count -gt 0) {
        Write-Rule -Title '긴급 확인'
        foreach ($alert in @($Status.alerts)) {
            Write-UiLine -Text ("! {0}" -f (Get-KoreanAlert ([string]$alert))) -Color Red
        }
    }

    Write-Rule
    $footer = if ($script:RenderingForGui) {
        '새로고침 버튼 또는 자동 갱신 · 이 화면은 주문을 보내거나 브로커 내역을 조회하지 않음'
    } else {
        '이 화면은 주문을 보내거나 브로커 내역을 조회하지 않음'
    }
    Write-UiLine -Text $footer -Color DarkGray
}

function Render-Failure {
    param([string]$Message)
    if (-not $Once -and -not $script:RenderingForGui) { Clear-Host }
    Write-UiLine -Text 'PROJECT ZETA TERMINUS NEXT · V7 LIVE-DEV' -Color White
    Write-UiLine -Text "상태 판독 실패: $Message" -Color Red
}

function Get-DashboardText {
    param([Parameter(Mandatory)]$Status)

    $script:RenderingForGui = $true
    try {
        $records = @(& { Render-Dashboard -Status $Status } 6>&1)
        return (@($records | ForEach-Object { $_.ToString() }) -join "`r`n")
    } finally {
        $script:RenderingForGui = $false
    }
}

function Show-GraphicalDashboard {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    [System.Windows.Forms.Application]::EnableVisualStyles()

    $createdNew = $false
    $mutex = [System.Threading.Mutex]::new(
        $true,
        'Local\ProjectZetaTerminusNextV7LiveDevDashboard',
        [ref]$createdNew
    )
    if (-not $createdNew) {
        $mutex.Dispose()
        return
    }

    $form = [System.Windows.Forms.Form]::new()
    $form.Text = $windowTitle
    $form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
    $form.Size = [System.Drawing.Size]::new(1280, 940)
    $form.MinimumSize = [System.Drawing.Size]::new(1000, 720)
    $form.BackColor = [System.Drawing.Color]::FromArgb(18, 22, 30)
    $form.ForeColor = [System.Drawing.Color]::WhiteSmoke

    $titleLabel = [System.Windows.Forms.Label]::new()
    $titleLabel.Text = 'PROJECT ZETA TERMINUS NEXT  ·  V7 LIVE-DEV'
    $titleLabel.Font = [System.Drawing.Font]::new('Malgun Gothic', 18, [System.Drawing.FontStyle]::Bold)
    $titleLabel.ForeColor = [System.Drawing.Color]::White
    $titleLabel.AutoSize = $true
    $titleLabel.Location = [System.Drawing.Point]::new(22, 18)

    $modeLabel = [System.Windows.Forms.Label]::new()
    $modeLabel.Text = 'Next V7 Live-Dev 상태 확인 중'
    $modeLabel.Font = [System.Drawing.Font]::new('Malgun Gothic', 10, [System.Drawing.FontStyle]::Bold)
    $modeLabel.ForeColor = [System.Drawing.Color]::FromArgb(255, 196, 64)
    $modeLabel.AutoSize = $true
    $modeLabel.Location = [System.Drawing.Point]::new(25, 58)

    $healthLabel = [System.Windows.Forms.Label]::new()
    $healthLabel.Font = [System.Drawing.Font]::new('Malgun Gothic', 11, [System.Drawing.FontStyle]::Bold)
    $healthLabel.AutoSize = $true
    $healthLabel.Location = [System.Drawing.Point]::new(25, 88)

    $body = [System.Windows.Forms.RichTextBox]::new()
    $body.ReadOnly = $true
    $body.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
    $body.BackColor = [System.Drawing.Color]::FromArgb(9, 12, 18)
    $body.ForeColor = [System.Drawing.Color]::Gainsboro
    $body.Font = [System.Drawing.Font]::new('Malgun Gothic', 10)
    $body.WordWrap = $false
    $body.ScrollBars = [System.Windows.Forms.RichTextBoxScrollBars]::Both
    $body.Location = [System.Drawing.Point]::new(25, 120)
    $body.Anchor = [System.Windows.Forms.AnchorStyles]::Top -bor
        [System.Windows.Forms.AnchorStyles]::Bottom -bor
        [System.Windows.Forms.AnchorStyles]::Left -bor
        [System.Windows.Forms.AnchorStyles]::Right
    $body.Size = [System.Drawing.Size]::new(1212, 730)

    $refreshButton = [System.Windows.Forms.Button]::new()
    $refreshButton.Text = '지금 새로고침'
    $refreshButton.Font = [System.Drawing.Font]::new('Malgun Gothic', 9, [System.Drawing.FontStyle]::Bold)
    $refreshButton.Size = [System.Drawing.Size]::new(130, 34)
    $refreshButton.Location = [System.Drawing.Point]::new(25, 860)
    $refreshButton.Anchor = [System.Windows.Forms.AnchorStyles]::Bottom -bor [System.Windows.Forms.AnchorStyles]::Left

    $closeButton = [System.Windows.Forms.Button]::new()
    $closeButton.Text = '대시보드 닫기'
    $closeButton.Font = [System.Drawing.Font]::new('Malgun Gothic', 9, [System.Drawing.FontStyle]::Bold)
    $closeButton.Size = [System.Drawing.Size]::new(130, 34)
    $closeButton.Location = [System.Drawing.Point]::new(1107, 860)
    $closeButton.Anchor = [System.Windows.Forms.AnchorStyles]::Bottom -bor [System.Windows.Forms.AnchorStyles]::Right

    $updatedLabel = [System.Windows.Forms.Label]::new()
    $updatedLabel.Font = [System.Drawing.Font]::new('Malgun Gothic', 9)
    $updatedLabel.ForeColor = [System.Drawing.Color]::Silver
    $updatedLabel.AutoSize = $true
    $updatedLabel.Location = [System.Drawing.Point]::new(175, 868)
    $updatedLabel.Anchor = [System.Windows.Forms.AnchorStyles]::Bottom -bor [System.Windows.Forms.AnchorStyles]::Left

    $form.Controls.AddRange(@($titleLabel, $modeLabel, $healthLabel, $body, $refreshButton, $closeButton, $updatedLabel))

    $updateAction = {
        try {
            $status = ((& $statusScript -AsJson -ExpectedMode $ExpectedMode | Out-String) | ConvertFrom-Json)
            $firstVisibleLine = 0
            if ($body.TextLength -gt 0) {
                $firstVisibleCharacter = $body.GetCharIndexFromPosition([System.Drawing.Point]::new(1, 1))
                $firstVisibleLine = [math]::Max(0, $body.GetLineFromCharIndex($firstVisibleCharacter))
            }
            $body.Text = Get-DashboardText -Status $status
            $maximumLine = [math]::Max(0, $body.Lines.Count - 1)
            $targetLine = [math]::Min($firstVisibleLine, $maximumLine)
            $targetCharacter = $body.GetFirstCharIndexFromLine($targetLine)
            $body.SelectionStart = [math]::Max(0, $targetCharacter)
            $body.ScrollToCaret()
            if ([bool]$status.healthy) {
                $healthLabel.Text = "● 정상 작동  ·  PID $($status.project_terminal_pid)  ·  신규진입 $($status.new_entries_input)/$($status.new_entries_effective)"
                $healthLabel.ForeColor = [System.Drawing.Color]::FromArgb(68, 214, 117)
                $modeLabel.Text = if ([int]$status.expected_new_entries -eq 1) {
                    '신규 주문 허용 · Next V7 Live-Dev'
                } else {
                    '신규 주문 차단 · Next V7 점검 모드'
                }
                $modeLabel.ForeColor = [System.Drawing.Color]::FromArgb(68, 214, 117)
            } else {
                $healthLabel.Text = "● 확인 필요  ·  경고 $(@($status.alerts).Count)개"
                $healthLabel.ForeColor = [System.Drawing.Color]::FromArgb(255, 92, 92)
                $modeLabel.Text = '신규 주문 준비 안 됨 · 아래 경고 확인'
                $modeLabel.ForeColor = [System.Drawing.Color]::FromArgb(255, 92, 92)
            }
            $updatedLabel.Text = "마지막 갱신: $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))  ·  ${RefreshSeconds}초 자동 갱신"
        } catch {
            $healthLabel.Text = '● 상태 판독 실패'
            $healthLabel.ForeColor = [System.Drawing.Color]::FromArgb(255, 92, 92)
            $body.Text = "상태 판독 실패: $($_.Exception.Message)"
            $updatedLabel.Text = "마지막 시도: $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))"
        }
    }

    $timer = [System.Windows.Forms.Timer]::new()
    $timer.Interval = $RefreshSeconds * 1000
    $timer.Add_Tick($updateAction)
    $refreshButton.Add_Click($updateAction)
    $closeButton.Add_Click({ $form.Close() })
    $form.Add_Shown({
        & $updateAction
        $timer.Start()
        $form.Activate()
    })
    $form.Add_FormClosed({ $timer.Stop() })

    try {
        [System.Windows.Forms.Application]::Run($form)
    } finally {
        $timer.Dispose()
        $form.Dispose()
        $mutex.ReleaseMutex()
        $mutex.Dispose()
    }
}

if ($Once) {
    try {
        $Host.UI.RawUI.WindowTitle = $windowTitle
    } catch { }
    try {
        $status = ((& $statusScript -AsJson -ExpectedMode $ExpectedMode | Out-String) | ConvertFrom-Json)
        Render-Dashboard -Status $status
    } catch {
        Render-Failure -Message $_.Exception.Message
    }
} else {
    Show-GraphicalDashboard
}
