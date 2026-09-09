# This interactive entrypoint is for direct user operation only.
# Never invoke it from an assistant, heartbeat, scheduler, or unattended worker.
# No authority or runtime change occurs before the user clicks the named button.
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
if ($PSVersionTable.PSVersion.Major -lt 7 -or -not [Environment]::UserInteractive) {
    throw 'PowerShell 7 and a direct interactive Windows session are required.'
}

$zetaMutex = [Threading.Mutex]::new($false, 'Local\ZetaNextV7RUserTradingActivation')
$zetaOwnsMutex = $false
$zetaDispatched = $false
$zetaLiveVerified = $false
$zetaRecorded = $false
$zetaResultPath = $null
$zetaDispatchUtc = [DateTime]::MinValue

function Invoke-ZetaUserGit {
    param([Parameter(Mandatory)][string[]]$GitArguments)
    $result = @(& git -C $script:zetaContract.ProjectRoot @GitArguments 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "Git 작업이 완료되지 않았습니다: $($GitArguments[0])`n$($result -join "`n")"
    }
    $result | ForEach-Object { [string]$_ }
}

function Assert-ZetaUserRecordOwnership {
    if ((Invoke-ZetaUserGit -GitArguments @('rev-parse', 'HEAD')).Trim() -ne $script:zetaExpectedHead) {
        throw '다른 작업이 Git 기록을 바꿨습니다. 현재 전환을 중단합니다.'
    }
    foreach ($path in $script:zetaRecordPaths) {
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $script:zetaExpectedHashes[$path]) {
            throw '다른 작업이 운영 기록을 바꿨습니다. 해당 변경을 덮어쓰지 않습니다.'
        }
    }
    $staged = @(Invoke-ZetaUserGit -GitArguments @('diff', '--cached', '--name-only'))
    if (@($staged | Where-Object { $_ -notin @('CURRENT_STATE.md', 'state/CURRENT_STATE-0002.md') }).Count -gt 0) {
        throw '다른 파일이 커밋 대기 중입니다. 해당 파일은 커밋하지 않습니다.'
    }
}

function Save-ZetaUserActivationRecord {
    param(
        [Parameter(Mandatory)][ValidateSet('ENABLED', 'DISABLED')][string]$Authority,
        [Parameter(Mandatory)][string]$Phase,
        [Parameter(Mandatory)][string]$OwnerText,
        [Parameter(Mandatory)][string]$Observation,
        [Parameter(Mandatory)][string]$HistoryText
    )

    Assert-ZetaUserRecordOwnership
    $stateText = [IO.File]::ReadAllText($script:zetaContract.StatePath)
    $chunkText = [IO.File]::ReadAllText($script:zetaChunkPath)
    $stateIds = [regex]::Matches($stateText, '(?m)^- Latest state ID: `STATE-(\d+)`\r?$')
    $blocks = [regex]::Matches($stateText, '(?s)<!-- V7R_USER_ACTIVATION_BEGIN -->.*?<!-- V7R_USER_ACTIVATION_END -->')
    if ($stateIds.Count -ne 1 -or $blocks.Count -ne 1 -or
        $stateText -notmatch 'state/CURRENT_STATE-0002\.md') {
        throw '운영 기록 형식이 변경되었습니다. 자동으로 수정하지 않습니다.'
    }
    $nextId = 'STATE-{0:D4}' -f (1 + [int]$stateIds[0].Groups[1].Value)
    if ($chunkText -match "(?m)^## $nextId\b") { throw '새 운영 기록 번호가 이미 존재합니다.' }
    $utc = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    $date = (Get-Date).ToString('yyyy-MM-dd')
    $block = @(
        '<!-- V7R_USER_ACTIVATION_BEGIN -->',
        '- Next Live-Dev authorization: `ENABLED` for exact `NEXT-E03-V7R-RLO1-0bba2ca045fe`. Direct user activation arms the recovered EA to wait for its existing trading conditions; current market activity is not a startup gate.',
        '- Next V7R return entries-disabled preflight: `PASSED`',
        ('- Next V7R return new-entry authorization: `' + $Authority + '`'),
        "- Existing real-account owner: $OwnerText",
        ('- Direct user activation phase: `' + $Phase + '`; recorded at ' + $utc + '.'),
        "- Latest activation observation: $Observation",
        '<!-- V7R_USER_ACTIVATION_END -->'
    ) -join "`n"
    $stateText = $stateText.Replace($blocks[0].Value, $block)
    $stateText = $stateText.Replace($stateIds[0].Value, ('- Latest state ID: `' + $nextId + '`'))
    $stateText = [regex]::Replace($stateText, '(?m)^Last updated: .*$', "Last updated: $date")
    $chunkText = $chunkText.TrimEnd() + "`n`n## $nextId - $date`n`n- $utc. $HistoryText`n- Exact release, EA, settings, risk contract and retired identities are unchanged. This transition was initiated by the user's direct interactive button; it does not resume research or its paused heartbeat.`n"
    $utf8 = [Text.UTF8Encoding]::new($false)
    [IO.File]::WriteAllText($script:zetaContract.StatePath, $stateText, $utf8)
    [IO.File]::WriteAllText($script:zetaChunkPath, $chunkText, $utf8)
    $script:zetaRecorded = $true
    foreach ($path in $script:zetaRecordPaths) {
        $script:zetaExpectedHashes[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    }
    $null = Invoke-ZetaUserGit -GitArguments @('add', '--', 'CURRENT_STATE.md', 'state/CURRENT_STATE-0002.md')
    $null = Invoke-ZetaUserGit -GitArguments @('commit', '--only', '-m', "Record direct user V7R activation: $Phase", '--', 'CURRENT_STATE.md', 'state/CURRENT_STATE-0002.md')
    $script:zetaExpectedHead = (Invoke-ZetaUserGit -GitArguments @('rev-parse', 'HEAD')).Trim()
    $null = Invoke-ZetaUserGit -GitArguments @('push', 'origin', 'HEAD:main')
    if ((Invoke-ZetaUserGit -GitArguments @('rev-parse', 'origin/main')).Trim() -ne $script:zetaExpectedHead) {
        throw '운영 기록이 origin/main과 일치하지 않습니다.'
    }
}

try {
    try { $zetaOwnsMutex = $zetaMutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $zetaOwnsMutex = $true }
    if (-not $zetaOwnsMutex) { throw 'V7R 실거래 실행 창이 이미 열려 있습니다.' }
    Add-Type -AssemblyName System.Windows.Forms
    [Windows.Forms.Application]::EnableVisualStyles()
    $form = [Windows.Forms.Form]::new()
    $form.Text = 'V7R 실제 자동매매 켜기'
    $form.ClientSize = [Drawing.Size]::new(560, 230)
    $form.StartPosition = 'CenterScreen'
    $form.FormBorderStyle = 'FixedDialog'
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $form.Font = [Drawing.Font]::new('맑은 고딕', 10)
    $label = [Windows.Forms.Label]::new()
    $label.SetBounds(24, 20, 512, 126)
    $label.Text = "버튼을 누르면 실제 계좌의 V7R 자동매매를 켭니다.`r`n`r`n켜진 뒤 거래 시간·신호를 기다리고, 조건 충족 시 주문합니다.`r`n기존 설정: 포지션 위험 4%, 합산 한도 12%, Passive 0.01 lot.`r`n계정·복구 확인 후 EA와 대시보드가 열립니다."
    $start = [Windows.Forms.Button]::new()
    $start.Text = '실제 자동매매 켜기'
    $start.SetBounds(24, 164, 326, 42)
    $start.DialogResult = [Windows.Forms.DialogResult]::OK
    $cancel = [Windows.Forms.Button]::new()
    $cancel.Text = '취소'
    $cancel.SetBounds(372, 164, 164, 42)
    $cancel.DialogResult = [Windows.Forms.DialogResult]::Cancel
    $form.Controls.AddRange(@($label, $start, $cancel))
    $form.AcceptButton = $cancel
    $form.CancelButton = $cancel
    $form.ActiveControl = $cancel
    try { $choice = $form.ShowDialog() } finally { $form.Dispose() }
    if ($choice -ne [Windows.Forms.DialogResult]::OK) {
        Write-Host '취소했습니다. 운영 권한과 실행 상태를 변경하지 않았습니다.'
        exit 0
    }

    # Everything below this point runs only after the direct user button action.
    Import-Module (Join-Path $PSScriptRoot 'ZetaNextOperatorCommon.psm1') -Force
    $script:zetaContract = Get-ZetaNextOperatorContract
    $script:zetaChunkPath = Join-Path $zetaContract.ProjectRoot 'state\CURRENT_STATE-0002.md'
    $script:zetaRecordPaths = @($zetaContract.StatePath, $zetaChunkPath)
    $script:zetaExpectedHashes = @{}
    $script:zetaExpectedHead = (Invoke-ZetaUserGit -GitArguments @('rev-parse', 'HEAD')).Trim()
    if ((Invoke-ZetaUserGit -GitArguments @('branch', '--show-current')).Trim() -ne 'main') { throw 'main 브랜치가 아닙니다.' }
    if (@(Invoke-ZetaUserGit -GitArguments @('diff', '--cached', '--name-only')).Count -ne 0) { throw '커밋 대기 중인 변경이 있습니다.' }
    $userPaths = @('CURRENT_STATE.md', 'state/CURRENT_STATE-0002.md', 'ZETA_NEXT_V7R_TRADING_ON.cmd', 'live-dev/tools/Open-ZetaNextV7RTradingOn.ps1')
    $null = Invoke-ZetaUserGit -GitArguments (@('ls-files', '--error-unmatch', '--') + $userPaths)
    $null = Invoke-ZetaUserGit -GitArguments (@('diff', '--quiet', '--') + $userPaths)
    foreach ($path in $zetaRecordPaths) { $zetaExpectedHashes[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash }
    $stateText = [IO.File]::ReadAllText($zetaContract.StatePath)
    if ($stateText -notmatch 'Next Live-Dev authorization:\s+`ENABLED`' -or
        $stateText -notmatch 'Next V7R return entries-disabled preflight:\s+`PASSED`' -or
        $stateText -notmatch 'Next V7R return new-entry authorization:\s+`DISABLED`' -or
        [regex]::Matches($stateText, '(?s)<!-- V7R_USER_ACTIVATION_BEGIN -->.*?<!-- V7R_USER_ACTIVATION_END -->').Count -ne 1) {
        throw '이미 활성화되었거나 다른 전환 기록이 있습니다. 재부팅 후 재실행은 ZETA_NEXT_MASTER_TERMINAL_AND_DASHBOARD.cmd를 사용하세요. 전환 오류가 있다면 현재 실행 상태를 먼저 확인해야 합니다.'
    }
    Write-Host '1/4  배포본과 저장된 운영 기록을 확인합니다.'
    $null = Assert-ZetaNextReleaseIntegrity -Contract $zetaContract
    $null = Get-ZetaNextHandoffReceipt -Contract $zetaContract
    $remote = @(Invoke-ZetaUserGit -GitArguments @('ls-remote', '--exit-code', 'origin', 'refs/heads/main'))
    if ($remote.Count -ne 1 -or ($remote[0] -split '\s+')[0] -ne $zetaExpectedHead) {
        throw '원격 main이 현재 기록과 다릅니다. 자동 병합이나 강제 푸시를 하지 않습니다.'
    }
    $inventory = Assert-ZetaNextExclusiveTerminalBoundary -Contract $zetaContract -AllowExactLive
    # Arming does not require an active market. The existing flat stopper and
    # fresh recovery/1/1 handshakes still validate the user-operated transition.
    Write-Host '2/4  기존 OFF 실행본의 무노출 상태를 확인하고 정상 종료합니다.'
    if (@($inventory.ExactLive).Count -eq 1) {
        & (Join-Path $PSScriptRoot 'Stop-ZetaNextV7RFlatRuntime.ps1') -ConfirmFlatStop
    }
    $null = Assert-ZetaNextExclusiveTerminalBoundary -Contract $zetaContract
    Save-ZetaUserActivationRecord -Authority ENABLED -Phase USER_REQUESTED_PENDING_FRESH_HANDOFF `
        -OwnerText 'none; the entries-disabled V7R runtime has stopped normally or no exact runtime was present. No retired identity may start.' `
        -Observation 'The user requested arm-and-wait activation. Final fresh preflight and 1/1 handshake are not yet complete; current market activity is not a startup requirement.' `
        -HistoryText 'Direct user activation button accepted under the arm-and-wait policy. Existing 0/0 runtime stopped through the unchanged verified-flat operator when present; exact terminal boundary is empty. Commit/push this separate new-entry authorization before dispatching the Master. No 1/1 success is claimed.'
    Write-Host '3/4  새 0/0 계정·복구 확인 후 1/1로 켭니다. EA가 거래 조건을 기다립니다.'
    $zetaResultPath = Join-Path $zetaContract.LiveDevRoot ('logs\user-activation-' + [Guid]::NewGuid().ToString('N') + '.json')
    $zetaDispatchUtc = [DateTime]::UtcNow
    $zetaDispatched = $true
    $powerShellPath = Join-Path $PSHOME 'pwsh.exe'
    & $powerShellPath -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'Start-ZetaNextDetachedMaster.ps1') -WorkerPowerShellPath $powerShellPath -ResultPath $zetaResultPath -RequiredMode Live
    if ($LASTEXITCODE -ne 0) { throw '기존 Master가 완료를 보고하지 않았습니다. 실행 중인 프로세스는 유지합니다.' }
    $status = Get-ZetaNextRuntimeStatus -Contract $zetaContract -Mode Live
    $inventory = Assert-ZetaNextExclusiveTerminalBoundary -Contract $zetaContract -AllowExactLive
    if (@($inventory.ExactLive).Count -ne 1 -or -not [bool]$status.healthy -or
        [int]$status.project_terminal_pid -ne [int]$inventory.ExactLive[0].Id -or
        -not (Test-ZetaNextLiveStatus -Status $status)) {
        throw '마지막 1/1 상태 확인이 완료되지 않았습니다. 실행 중인 EA는 유지합니다.'
    }
    $zetaLiveVerified = $true
    Write-Host '4/4  자동매매 ON(1/1)을 확인했습니다. 거래 조건 충족 시 주문하며, 완료 기록을 저장합니다.'
    Save-ZetaUserActivationRecord -Authority ENABLED -Phase USER_ACTIVATED_HEALTHY_1_1 `
        -OwnerText "exact V7R PID $($status.project_terminal_pid), the sole authorized order owner; all retired identities remain stopped." `
        -Observation "Healthy exact 1/1 at $($status.observed_at_utc), sequence $($status.state_sequence); the detached Master confirmed EA and dashboard startup under the arm-and-wait policy. This confirms entry permission, not an order or a signal." `
        -HistoryText "Master returned success. Final local status confirms sole exact V7R PID $($status.project_terminal_pid), healthy 1/1 and sequence $($status.state_sequence). Current market activity was not a startup gate; frozen EA decision/quote/session/risk checks, package and retired state are unchanged."
    $null = [Windows.Forms.MessageBox]::Show('V7R 실제 자동매매가 ON(1/1)입니다. EA와 대시보드를 켜두면 거래 조건을 기다렸다가 조건 충족 시 주문합니다.', 'V7R 시작 완료', 'OK', 'Information')
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    if ($zetaLiveVerified) {
        Write-Host '실거래 ON은 확인됐지만 마지막 기록 저장이 끝나지 않았습니다. EA를 강제 종료하지 마세요.' -ForegroundColor Yellow
    } elseif ($zetaDispatched) {
        $recoveredDisabled = $false
        try {
            # A missing/timed-out worker result is never treated as a stopped handoff.
            $result = if ($zetaResultPath -and (Test-Path -LiteralPath $zetaResultPath)) {
                Get-Content -LiteralPath $zetaResultPath -Raw | ConvertFrom-Json
            } else { $null }
            if ($null -ne $result -and [string]$result.schema -eq 'zeta-detached-master-result-v1' -and
                [string]$result.outcome -eq 'FAILED' -and [bool]$result.worker_finished -and
                [bool]$result.matched_completion_marker -and [string]$result.required_mode -eq 'Live') {
                $null = Assert-ZetaNextExclusiveTerminalBoundary -Contract $zetaContract
                $otherWorkers = @(Get-CimInstance Win32_Process -Filter "Name='pwsh.exe' OR Name='powershell.exe'" -ErrorAction Stop | Where-Object {
                    $_.ProcessId -ne $PID -and $_.CommandLine -and
                    ($_.CommandLine.IndexOf((Join-Path $PSScriptRoot 'Invoke-ZetaNextDetachedMasterOnce.ps1'), [StringComparison]::OrdinalIgnoreCase) -ge 0 -or
                     $_.CommandLine.IndexOf((Join-Path $PSScriptRoot 'Start-ZetaNextDetachedMaster.ps1'), [StringComparison]::OrdinalIgnoreCase) -ge 0)
                })
                if ($otherWorkers.Count -ne 0) { throw '아직 Master 작업이 실행 중입니다.' }
                $stopped = Get-ZetaNextRuntimeStatus -Contract $zetaContract -Mode EntriesDisabled
                $lastEvent = @($stopped.latest_events | Sort-Object { [long]$_.state_sequence } -Descending | Select-Object -First 1)
                if ([string]$stopped.release_id -ne $zetaContract.ReleaseId -or
                    @($stopped.components).Count -ne 6 -or
                    -not (Test-ZetaNextFlatStatus -Status $stopped -Receipt (Get-ZetaNextHandoffReceipt -Contract $zetaContract)) -or
                    $lastEvent.Count -ne 1 -or [string]$lastEvent[0].event -ne 'STOP' -or
                    [string]$lastEvent[0].detail -ne 'normal' -or
                    [long]$stopped.state_sequence -ne 1 + [long]$lastEvent[0].state_sequence) {
                    throw '이번 실행의 정상 종료와 0/0 무노출을 입증하지 못했습니다.'
                }
                $stoppedUtc = [DateTime]::ParseExact([string]$lastEvent[0].utc, 'yyyy.MM.dd HH:mm:ss',
                    [Globalization.CultureInfo]::InvariantCulture,
                    ([Globalization.DateTimeStyles]::AssumeUniversal -bor [Globalization.DateTimeStyles]::AdjustToUniversal))
                if ($stoppedUtc -lt $zetaDispatchUtc) { throw '종료 기록이 이번 기동 요청보다 오래됐습니다.' }
                Save-ZetaUserActivationRecord -Authority DISABLED -Phase USER_HANDOFF_FAILED_PROVED_STOPPED_0_0 `
                    -OwnerText 'none; the failed Master worker has completed and exact V7R stopped normally at 0/0 with zero exposure.' `
                    -Observation "Failed launch $($result.launch_id) completed; normal STOP at $($lastEvent[0].utc), final sequence $($stopped.state_sequence). Restore entries-disabled operation only." `
                    -HistoryText "User-operated handoff failed before a verified Live start. Matching completed worker receipt, no other worker/terminal, exact 0/0 flat snapshot and a normal STOP after dispatch prove a stopped boundary. New-entry authority is DISABLED; only entries-disabled recovery follows."
                & $powerShellPath -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'Start-ZetaNextDetachedMaster.ps1') -WorkerPowerShellPath $powerShellPath -RequiredMode EntriesDisabled
                if ($LASTEXITCODE -ne 0) { throw 'OFF 권한은 복구했지만 EA 재기동 확인은 완료되지 않았습니다.' }
                $disabled = Get-ZetaNextRuntimeStatus -Contract $zetaContract -Mode EntriesDisabled
                if (-not [bool]$disabled.healthy -or
                    -not (Test-ZetaNextFlatStatus -Status $disabled -Receipt (Get-ZetaNextHandoffReceipt -Contract $zetaContract))) {
                    throw 'OFF 재기동 상태 확인이 완료되지 않았습니다.'
                }
                $recoveredDisabled = $true
                Save-ZetaUserActivationRecord -Authority DISABLED -Phase USER_HANDOFF_FAILED_RECOVERED_0_0 `
                    -OwnerText "none with permission for new orders; exact V7R entries-disabled PID $($disabled.project_terminal_pid) is running with its dashboard." `
                    -Observation "Recovered healthy 0/0 at $($disabled.observed_at_utc), sequence $($disabled.state_sequence). A new user button action is required for another activation attempt." `
                    -HistoryText "Failed handoff recovery completed as exact healthy 0/0 PID $($disabled.project_terminal_pid), sequence $($disabled.state_sequence), with EA/dashboard restored. No live retry or gate relaxation occurred."
                Write-Host '실거래는 OFF입니다. EA와 대시보드를 주문 차단 상태로 복구했습니다. 표시된 기동 오류를 해결한 뒤 같은 버튼으로 다시 시도할 수 있습니다.' -ForegroundColor Yellow
            }
        } catch { Write-Host "실패 후 복구 확인: $($_.Exception.Message)" -ForegroundColor Yellow }
        if (-not $recoveredDisabled) {
            Write-Host '기동 이후 상태를 완전히 확인하지 못했습니다. OFF라고 단정하지 않습니다. 재실행하거나 MT5를 강제 종료하지 말고 상태를 확인하세요.' -ForegroundColor Yellow
        }
    } else {
        Write-Host '실거래 기동 요청은 보내지 않았습니다.' -ForegroundColor Yellow
        if ($zetaRecorded) {
            try {
                $null = Assert-ZetaNextExclusiveTerminalBoundary -Contract $zetaContract
                Save-ZetaUserActivationRecord -Authority DISABLED -Phase USER_ACTIVATION_STOPPED_BEFORE_DISPATCH `
                    -OwnerText 'none; no Master activation was dispatched and no exact runtime is running.' `
                    -Observation 'The user-operated preparation failed before activation dispatch; new-entry authority is closed.' `
                    -HistoryText 'User-operated preparation stopped before Master dispatch. Exact terminal boundary is empty; new-entry authority returned to DISABLED. No real trading activation was attempted.'
            } catch { Write-Host "운영 기록 복구도 완료되지 않았습니다: $($_.Exception.Message)" -ForegroundColor Yellow }
        }
    }
    exit 1
} finally {
    if ($zetaOwnsMutex) { $zetaMutex.ReleaseMutex() }
    $zetaMutex.Dispose()
}
