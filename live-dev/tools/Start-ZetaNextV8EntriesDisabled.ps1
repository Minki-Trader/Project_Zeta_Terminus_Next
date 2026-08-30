[CmdletBinding()]
param(
    [switch]$ConfirmEntriesDisabled
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

if (-not $ConfirmEntriesDisabled) {
    throw 'Next V8 entries-disabled start requires -ConfirmEntriesDisabled.'
}

$commonModule = Join-Path $PSScriptRoot 'ZetaNextOperatorCommon.psm1'
if (-not (Test-Path -LiteralPath $commonModule -PathType Leaf)) {
    throw "Next V8 operator module is missing: $commonModule"
}
Import-Module $commonModule -Force

$contract = Get-ZetaNextOperatorContract
$authorization = Get-Content -LiteralPath $contract.StatePath -Raw
if ($authorization -notmatch 'Next V8 paired-month entries-disabled preflight:\s+`(?:ENABLED|PASSED)`') {
    throw 'CURRENT_STATE.md does not authorize the Next V8 paired-month entries-disabled runtime.'
}
if ($authorization -notmatch 'Next V8 paired-month new-entry authorization:\s+`DISABLED`') {
    throw 'Entries-disabled mode requires Next V8 paired-month new-entry authorization to remain DISABLED.'
}
if ($authorization -notmatch 'Existing real-account owner:\s+none') {
    throw 'CURRENT_STATE.md must state that no legacy or Next real-account owner is running during flat handoff.'
}

$null = Assert-ZetaNextExclusiveTerminalBoundary -Contract $contract
$release = Assert-ZetaNextReleaseIntegrity -Contract $contract
$receipt = Get-ZetaNextHandoffReceipt -Contract $contract
$runtimeMode = Write-ZetaNextRuntimeMode -Contract $contract -Receipt $receipt -Mode EntriesDisabled
$priorSequence = -1L
try {
    $priorSequence = [long](Get-ZetaNextRuntimeStatus -Contract $contract -Mode EntriesDisabled).state_sequence
} catch { }

$process = $null
try {
    $process = Start-ZetaNextRuntime -Contract $contract -RuntimeMode $runtimeMode
    Write-Output "Next V8 entries-disabled runtime started (PID $($process.Id)); waiting for a new 0/0 flat snapshot after sequence $priorSequence."
    $status = Wait-ZetaNextRuntimeStatus `
        -Contract $contract `
        -RuntimeMode $runtimeMode `
        -ProcessId $process.Id `
        -MinimumStateSequenceExclusive $priorSequence `
        -TimeoutSeconds 60 `
        -Predicate { param($candidate) Test-ZetaNextFlatStatus -Status $candidate -Receipt $receipt }
    if ($null -eq $status) {
        throw 'Next V8 entries-disabled runtime did not prove exact identity, 0/0 entries, flat exposure, zero margin/risk, and receipt continuity.'
    }
    Write-Output ("Next V8 entries-disabled handshake passed: release={0} portfolio={1} entries=0/0 positions=0 orders=0 margin={2:N2} balance={3:N2} equity={4:N2} sequence={5}." -f
        $status.release_id,
        $status.portfolio_id,
        [double]$status.account_margin,
        [double]$status.account_balance,
        [double]$status.account_equity,
        [long]$status.state_sequence)
    Write-Output "Git HEAD $($release.GitHead); runtime remains open for normal entries-disabled observation."
} catch {
    if ($null -ne $process -and $null -ne (Get-Process -Id $process.Id -ErrorAction SilentlyContinue)) {
        try { Stop-ZetaNextRuntime -Contract $contract -ProcessId $process.Id } catch { }
    }
    throw
}
