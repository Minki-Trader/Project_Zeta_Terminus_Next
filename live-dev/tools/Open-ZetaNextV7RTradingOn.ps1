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
        '- Next Live-Dev authorization: `ENABLED` for exact `NEXT-E03-V7R-RLO1-0bba2ca045fe`. Trading activation is a direct user action through the unchanged operating gates.',
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
    $label.Text = "버튼을 누르면 실제 계좌의 V7R 자동매매를 시작합니다.`r`n`r`n기존 설정: 포지션 위험 4%, 합산 한도 12%, Passive 0.01 lot.`r`n정상 종료 · 운영 기록 저장 · 현재 시세와 복구 검사를 거칩니다.`r`n검사 중에는 진행 창이 유지되며, 완료 후 대시보드가 열립니다."
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
        throw '이미 활성화되었거나 다른 전환 기록이 있습니다. 현재 실행 상태를 먼저 확인해야 합니다.'
    }
    Write-Host '1/4  배포본과 저장된 운영 기록을 확인합니다.'
    $null = Assert-ZetaNextReleaseIntegrity -Contract $zetaContract
    $null = Get-ZetaNextHandoffReceipt -Contract $zetaContract
    $remote = @(Invoke-ZetaUserGit -GitArguments @('ls-remote', '--exit-code', 'origin', 'refs/heads/main'))
    if ($remote.Count -ne 1 -or ($remote[0] -split '\s+')[0] -ne $zetaExpectedHead) {
        throw '원격 main이 현재 기록과 다릅니다. 자동 병합이나 강제 푸시를 하지 않습니다.'
    }
    $inventory = Assert-ZetaNextExclusiveTerminalBoundary -Contract $zetaContract -AllowExactLive
    Write-Host '2/4  기존 OFF 실행본의 무노출 상태를 확인하고 정상 종료합니다.'
    if (@($inventory.ExactLive).Count -eq 1) {
        & (Join-Path $PSScriptRoot 'Stop-ZetaNextV7RFlatRuntime.ps1') -ConfirmFlatStop
    }
    $null = Assert-ZetaNextExclusiveTerminalBoundary -Contract $zetaContract
    Save-ZetaUserActivationRecord -Authority ENABLED -Phase USER_REQUESTED_PENDING_FRESH_HANDOFF `
        -OwnerText 'none; the entries-disabled V7R runtime has stopped normally or no exact runtime was present. No retired identity may start.' `
        -Observation 'The user requested activation. Final fresh preflight and 1/1 handshake are not yet complete.' `
        -HistoryText 'Direct user activation button accepted. Existing 0/0 runtime stopped through the unchanged verified-flat operator when present; exact terminal boundary is empty. Commit/push this separate new-entry authorization before dispatching the unchanged Master. No 1/1 success is claimed.'
    Write-Host '3/4  새 0/0 복구와 실제 틱을 검사한 뒤 기존 실행기로 기동합니다.'
    $zetaDispatched = $true
    $powerShellPath = Join-Path $PSHOME 'pwsh.exe'
    & $powerShellPath -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'Start-ZetaNextDetachedMaster.ps1') -WorkerPowerShellPath $powerShellPath
    if ($LASTEXITCODE -ne 0) { throw '기존 Master가 완료를 보고하지 않았습니다. 실행 중인 프로세스는 유지합니다.' }
    $status = Get-ZetaNextRuntimeStatus -Contract $zetaContract -Mode Live
    $inventory = Assert-ZetaNextExclusiveTerminalBoundary -Contract $zetaContract -AllowExactLive
    if (@($inventory.ExactLive).Count -ne 1 -or -not [bool]$status.healthy -or
        [int]$status.project_terminal_pid -ne [int]$inventory.ExactLive[0].Id -or
        -not (Test-ZetaNextLiveStatus -Status $status)) {
        throw '마지막 1/1 상태 확인이 완료되지 않았습니다. 실행 중인 EA는 유지합니다.'
    }
    $zetaLiveVerified = $true
    Write-Host '4/4  실제 주문 ON(1/1)을 확인했습니다. 완료 기록을 저장합니다.'
    Save-ZetaUserActivationRecord -Authority ENABLED -Phase USER_ACTIVATED_HEALTHY_1_1 `
        -OwnerText "exact V7R PID $($status.project_terminal_pid), the sole authorized order owner; all retired identities remain stopped." `
        -Observation "Healthy exact 1/1 at $($status.observed_at_utc), sequence $($status.state_sequence); the unchanged detached Master confirmed EA and dashboard startup." `
        -HistoryText "Unchanged Master returned success. Final local status confirms sole exact V7R PID $($status.project_terminal_pid), healthy 1/1 and sequence $($status.state_sequence). No gates, package, risk settings or retired state changed."
    $null = [Windows.Forms.MessageBox]::Show('V7R 실제 자동매매가 ON(1/1)입니다. EA와 대시보드가 실행 중입니다.', 'V7R 시작 완료', 'OK', 'Information')
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    if ($zetaLiveVerified) {
        Write-Host '실거래 ON은 확인됐지만 마지막 기록 저장이 끝나지 않았습니다. EA를 강제 종료하지 마세요.' -ForegroundColor Yellow
    } elseif ($zetaDispatched) {
        Write-Host '기동을 요청했지만 완료 확인이 안 됐습니다. OFF라고 단정할 수 없습니다. 재실행하거나 MT5를 강제 종료하지 말고 상태를 확인하세요.' -ForegroundColor Yellow
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
