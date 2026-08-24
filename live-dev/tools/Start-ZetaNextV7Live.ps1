[CmdletBinding()]
param(
    [switch]$EnableNewEntries,
    [switch]$ConfirmLiveDev
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

if (-not $EnableNewEntries -or -not $ConfirmLiveDev) {
    throw 'Next V7 Live start requires both -EnableNewEntries and -ConfirmLiveDev.'
}

$commonModule = Join-Path $PSScriptRoot 'ZetaNextOperatorCommon.psm1'
Import-Module $commonModule -Force
$contract = Get-ZetaNextOperatorContract
$authorization = Get-Content -LiteralPath $contract.StatePath -Raw
if ($authorization -notmatch 'Next Live-Dev authorization:\s+`ENABLED`' -or
    $authorization -notmatch 'Next V7 entries-disabled preflight:\s+`PASSED`' -or
    $authorization -notmatch 'Next V7 new-entry authorization:\s+`ENABLED`') {
    throw 'CURRENT_STATE.md does not contain the separate Next V7 Live authorization and passed entries-disabled preflight.'
}
if ($authorization -notmatch 'Existing real-account owner:\s+none') {
    throw 'CURRENT_STATE.md must state that no legacy or Next real-account owner is running before the 0/0 preflight.'
}

$null = Assert-ZetaNextExclusiveTerminalBoundary -Contract $contract
$release = Assert-ZetaNextReleaseIntegrity -Contract $contract
$receipt = Get-ZetaNextHandoffReceipt -Contract $contract

$preflightMode = Write-ZetaNextRuntimeMode -Contract $contract -Receipt $receipt -Mode LivePreflight
$preflightProcess = $null
try {
    $preflightProcess = Start-ZetaNextRuntime -Contract $contract -RuntimeMode $preflightMode
    Write-Output "Next V7 0/0 flat preflight started (PID $($preflightProcess.Id))."
    $preflightStatus = Wait-ZetaNextRuntimeStatus `
        -Contract $contract `
        -RuntimeMode $preflightMode `
        -ProcessId $preflightProcess.Id `
        -TimeoutSeconds 60 `
        -Predicate { param($candidate) Test-ZetaNextFlatStatus -Status $candidate -Receipt $receipt }
    if ($null -eq $preflightStatus) {
        throw 'Next V7 preflight did not prove identity, 0/0 entries, flat exposure, zero margin/risk, and receipt continuity.'
    }
    Write-Output ("Next V7 preflight passed: release={0} portfolio={1} entries=0/0 positions=0 orders=0 margin={2:N2} balance={3:N2} equity={4:N2}." -f
        $preflightStatus.release_id,
        $preflightStatus.portfolio_id,
        [double]$preflightStatus.account_margin,
        [double]$preflightStatus.account_balance,
        [double]$preflightStatus.account_equity)
    Stop-ZetaNextRuntime -Contract $contract -ProcessId $preflightProcess.Id
    $preflightProcess = $null
} catch {
    if ($null -ne $preflightProcess -and $null -ne (Get-Process -Id $preflightProcess.Id -ErrorAction SilentlyContinue)) {
        try { Stop-ZetaNextRuntime -Contract $contract -ProcessId $preflightProcess.Id } catch { }
    }
    throw
}

$null = Assert-ZetaNextExclusiveTerminalBoundary -Contract $contract
$liveMode = Write-ZetaNextRuntimeMode -Contract $contract -Receipt $receipt -Mode Live
$liveProcess = Start-ZetaNextRuntime -Contract $contract -RuntimeMode $liveMode
Write-Output "Next V7 1/1 Live runtime started (PID $($liveProcess.Id)); waiting for exact handshake."

$liveStatus = Wait-ZetaNextRuntimeStatus `
    -Contract $contract `
    -RuntimeMode $liveMode `
    -ProcessId $liveProcess.Id `
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
        throw 'Next V7 1/1 handshake failed while the snapshot still proved flat. Next was stopped; legacy recovery remains a separate operator action.'
    }
    throw 'Next V7 1/1 handshake failed without proof of zero Next exposure. The Next terminal was left running so any Next-owned risk remains managed; do not restart legacy.'
}

Write-Output ("Next V7 Live handshake passed: Git={0} release={1} portfolio={2} entries={3}/{4} PID={5}." -f
    $release.GitHead,
    $liveStatus.release_id,
    $liveStatus.portfolio_id,
    $liveStatus.new_entries_input,
    $liveStatus.new_entries_effective,
    $liveProcess.Id)
