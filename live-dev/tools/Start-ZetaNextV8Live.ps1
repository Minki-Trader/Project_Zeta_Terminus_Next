[CmdletBinding()]
param(
    [switch]$EnableNewEntries,
    [switch]$ConfirmLiveDev
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

if (-not $EnableNewEntries -or -not $ConfirmLiveDev) {
    throw 'Next V8 Live start requires both -EnableNewEntries and -ConfirmLiveDev.'
}

$commonModule = Join-Path $PSScriptRoot 'ZetaNextOperatorCommon.psm1'
Import-Module $commonModule -Force
$contract = Get-ZetaNextOperatorContract
$authorization = Get-Content -LiteralPath $contract.StatePath -Raw
if ($authorization -notmatch 'Next Live-Dev authorization:\s+`ENABLED`' -or
    $authorization -notmatch 'Next V8 paired-month entries-disabled preflight:\s+`PASSED`' -or
    $authorization -notmatch 'Next V8 paired-month new-entry authorization:\s+`ENABLED`') {
    throw 'CURRENT_STATE.md does not contain the separate Next V8 Live authorization and passed entries-disabled preflight.'
}
if ($authorization -notmatch 'Existing real-account owner:\s+none') {
    throw 'CURRENT_STATE.md must state that no legacy or Next real-account owner is running before the 0/0 preflight.'
}

$null = Assert-ZetaNextExclusiveTerminalBoundary -Contract $contract
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
    Write-Output "Next V8 0/0 flat preflight started (PID $($preflightProcess.Id)); waiting after sequence $preflightPriorSequence."
    $preflightStatus = Wait-ZetaNextRuntimeStatus `
        -Contract $contract `
        -RuntimeMode $preflightMode `
        -ProcessId $preflightProcess.Id `
        -MinimumStateSequenceExclusive $preflightPriorSequence `
        -TimeoutSeconds 60 `
        -Predicate { param($candidate) Test-ZetaNextFlatStatus -Status $candidate -Receipt $receipt }
    if ($null -eq $preflightStatus) {
        throw 'Next V8 preflight did not prove identity, 0/0 entries, flat exposure, zero margin/risk, and receipt continuity.'
    }
    Write-Output ("Next V8 preflight passed: release={0} portfolio={1} entries=0/0 positions=0 orders=0 margin={2:N2} balance={3:N2} equity={4:N2}." -f
        $preflightStatus.release_id,
        $preflightStatus.portfolio_id,
        [double]$preflightStatus.account_margin,
        [double]$preflightStatus.account_balance,
        [double]$preflightStatus.account_equity)
    $marketStatus = ((& $contract.MarketStatusScript `
        -AsJson `
        -ObservationSeconds 12 `
        -ExpectedProcessId $preflightProcess.Id | Out-String) | ConvertFrom-Json)
    if (-not [bool]$marketStatus.ready_for_handoff) {
        throw ("Next V8 market gate is not ready: {0}" -f (@($marketStatus.reasons) -join '; '))
    }
    Write-Output ("Next V8 market gate passed: US30 ticks={0}, max-gap={1:N3}s, synchronized timeframes={2}, server={3}." -f
        [long]$marketStatus.us30_tick_updates,
        [double]$marketStatus.us30_max_update_gap_seconds,
        (@($marketStatus.timeframes | Where-Object { [bool]$_.synchronized_and_fresh }).Count),
        [string]$marketStatus.server_time)
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
Write-Output "Next V8 1/1 Live runtime started (PID $($liveProcess.Id)); waiting for an exact handshake after sequence $livePriorSequence."

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
        [math]::Abs([double]$lastStatus.account_margin) -le 0.01 -and
        [math]::Abs([double]$lastStatus.aggregate_planned_risk) -le 0.01 -and
        [long]$lastStatus.passive_pending_order -eq 0 -and
        @($lastStatus.components | Where-Object { [long]$_.position_identifier -ne 0 }).Count -eq 0)
    if ($provedFlat -and $null -ne (Get-Process -Id $liveProcess.Id -ErrorAction SilentlyContinue)) {
        Stop-ZetaNextRuntime -Contract $contract -ProcessId $liveProcess.Id
        throw 'Next V8 1/1 handshake failed while the snapshot still proved flat. Next was stopped; RLO1 must remain retired.'
    }
    throw 'Next V8 1/1 handshake failed without proof of zero Next exposure. The Next terminal was left running so any Next-owned risk remains managed; do not restart RLO1.'
}

Write-Output ("Next V8 Live handshake passed: Git={0} release={1} portfolio={2} entries={3}/{4} PID={5}." -f
    $release.GitHead,
    $liveStatus.release_id,
    $liveStatus.portfolio_id,
    $liveStatus.new_entries_input,
    $liveStatus.new_entries_effective,
    $liveProcess.Id)
