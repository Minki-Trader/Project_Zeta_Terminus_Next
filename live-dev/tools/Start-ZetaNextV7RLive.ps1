[CmdletBinding()]
param(
    [switch]$EnableNewEntries,
    [switch]$ConfirmLiveDev
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

if (-not $EnableNewEntries -or -not $ConfirmLiveDev) {
    throw 'Next V7R Live start requires both -EnableNewEntries and -ConfirmLiveDev.'
}

$commonModule = Join-Path $PSScriptRoot 'ZetaNextOperatorCommon.psm1'
Import-Module $commonModule -Force
$contract = Get-ZetaNextOperatorContract
$authorization = Get-Content -LiteralPath $contract.StatePath -Raw
if ($authorization -notmatch 'Next Live-Dev authorization:\s+`ENABLED`' -or
    $authorization -notmatch 'Next V7R return entries-disabled preflight:\s+`PASSED`' -or
    $authorization -notmatch 'Next V7R return new-entry authorization:\s+`ENABLED`') {
    throw 'CURRENT_STATE.md does not contain the separate Next V7R Live authorization and passed entries-disabled preflight.'
}
$recordedOwnerAbsent = $authorization -match '(?m)^- Existing real-account owner:\s+none\b'
$recordedHealthyV7R = (
    $authorization -match '(?m)^- Existing real-account owner: exact V7R PID [1-9][0-9]*, the sole authorized order owner; all retired identities remain stopped\.\r?$' -and
    $authorization -match '(?m)^- Direct user activation phase:\s+`USER_ACTIVATED_HEALTHY_1_1`'
)
if (-not $recordedOwnerAbsent -and -not $recordedHealthyV7R) {
    throw 'CURRENT_STATE.md must identify either no running owner or the previously healthy, already-authorized exact V7R owner. An incomplete transition cannot restart automatically.'
}

# A saved PID describes the previous run, and survives a Windows reboot.
# Only the actual process inventory can prove that the terminal has stopped.
# The same frozen release still passes the full fresh 0/0 -> 1/1 sequence below.
$null = Assert-ZetaNextExclusiveTerminalBoundary -Contract $contract
if ($recordedHealthyV7R) {
    Write-Output 'The previously authorized V7R owner is no longer running. Restoring that same release through a fresh 0/0 preflight.'
}
$release = Assert-ZetaNextReleaseIntegrity -Contract $contract
$receipt = Get-ZetaNextHandoffReceipt -Contract $contract

$preflightMode = Write-ZetaNextRuntimeMode -Contract $contract -Receipt $receipt -Mode LivePreflight
$preflightPriorSequence = -1L
try {
    $preflightPriorSequence = [long](Get-ZetaNextRuntimeStatus -Contract $contract -Mode LivePreflight).state_sequence
} catch { }
$preflightProcess = $null
try {
    $preflightProcess = Start-ZetaNextRuntime -Contract $contract -RuntimeMode $preflightMode
    Write-Output "Next V7R 0/0 flat preflight started (PID $($preflightProcess.Id)); waiting after sequence $preflightPriorSequence."
    $preflightStatus = Wait-ZetaNextRuntimeStatus `
        -Contract $contract `
        -RuntimeMode $preflightMode `
        -ProcessId $preflightProcess.Id `
        -MinimumStateSequenceExclusive $preflightPriorSequence `
        -TimeoutSeconds 60 `
        -Predicate { param($candidate) Test-ZetaNextFlatStatus -Status $candidate -Receipt $receipt }
    if ($null -eq $preflightStatus) {
        throw 'Next V7R preflight did not prove identity, 0/0 entries, flat exposure, zero margin/risk, and receipt continuity.'
    }
    Write-Output ("Next V7R preflight passed: release={0} portfolio={1} entries=0/0 positions=0 orders=0 margin={2:N2} balance={3:N2} equity={4:N2}." -f
        $preflightStatus.release_id,
        $preflightStatus.portfolio_id,
        [double]$preflightStatus.account_margin,
        [double]$preflightStatus.account_balance,
        [double]$preflightStatus.account_equity)
    # User-authorized arm-and-wait startup: market activity is diagnostic only.
    # The frozen EA evaluates entries on ticks and retains its own decision
    # windows, data checks, executable quote age, session and risk guards.
    # Do not require a continuous tick stream or a deployment handoff window
    # before allowing this already-installed, recovered identity to be armed.
    Write-Output 'Next V7R recovery passed. After the 1/1 handshake, the EA will wait for its normal trading conditions; quiet ticks do not block startup.'
    Stop-ZetaNextRuntime -Contract $contract -ProcessId $preflightProcess.Id
    $preflightProcess = $null
} catch {
    if ($null -ne $preflightProcess -and $null -ne (Get-Process -Id $preflightProcess.Id -ErrorAction SilentlyContinue)) {
        try { Stop-ZetaNextRuntime -Contract $contract -ProcessId $preflightProcess.Id } catch { }
    }
    throw
}

$postStopDeadline = (Get-Date).AddSeconds(5)
do {
    $postStopInventory = Get-ZetaNextTerminalInventory -Contract $contract
    if (@($postStopInventory.ExactLive).Count -eq 0) { break }
    Start-Sleep -Milliseconds 100
} while ((Get-Date) -lt $postStopDeadline)

$null = Assert-ZetaNextExclusiveTerminalBoundary -Contract $contract
$liveMode = Write-ZetaNextRuntimeMode -Contract $contract -Receipt $receipt -Mode Live
$livePriorSequence = -1L
try {
    $livePriorSequence = [long](Get-ZetaNextRuntimeStatus -Contract $contract -Mode Live).state_sequence
} catch { }
$liveProcess = Start-ZetaNextRuntime -Contract $contract -RuntimeMode $liveMode
Write-Output "Next V7R Live runtime started (PID $($liveProcess.Id)); waiting for an exact 1/1 permission handshake after sequence $livePriorSequence."

$liveStatus = Wait-ZetaNextRuntimeStatus `
    -Contract $contract `
    -RuntimeMode $liveMode `
    -ProcessId $liveProcess.Id `
    -MinimumStateSequenceExclusive $livePriorSequence `
    -TimeoutSeconds 60 `
    -Predicate { param($candidate) Test-ZetaNextLiveStatus -Status $candidate }
if ($null -eq $liveStatus) {
    $lastStatus = $null
    try { $lastStatus = Get-ZetaNextRuntimeStatus -Contract $contract -Mode Live } catch { }
    $provedFlat = ($null -ne $lastStatus -and
        [bool]$lastStatus.healthy -and
        [int]$lastStatus.project_terminal_pid -eq $liveProcess.Id -and
        @($lastStatus.components).Count -eq 6 -and
        [math]::Abs([double]$lastStatus.account_margin) -le 0.01 -and
        [math]::Abs([double]$lastStatus.aggregate_planned_risk) -le 0.01 -and
        [long]$lastStatus.passive_pending_order -eq 0 -and
        @($lastStatus.components | Where-Object { [long]$_.position_identifier -ne 0 }).Count -eq 0)
    if ($provedFlat -and $null -ne (Get-Process -Id $liveProcess.Id -ErrorAction SilentlyContinue)) {
        Stop-ZetaNextRuntime -Contract $contract -ProcessId $liveProcess.Id
        throw 'Next V7R 1/1 handshake failed while the snapshot still proved flat. Next was stopped; RLO1 must remain retired.'
    }
    throw 'Next V7R 1/1 handshake failed without proof of zero Next exposure. The Next terminal was left running so any Next-owned risk remains managed; do not restart RLO1.'
}

Write-Output ("Next V7R Live handshake passed: Git={0} release={1} portfolio={2} entries={3}/{4} PID={5}." -f
    $release.GitHead,
    $liveStatus.release_id,
    $liveStatus.portfolio_id,
    $liveStatus.new_entries_input,
    $liveStatus.new_entries_effective,
    $liveProcess.Id)
