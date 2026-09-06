[CmdletBinding()]
param(
    [switch]$ConfirmFlatStop
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

if (-not $ConfirmFlatStop) {
    throw 'Stopping the Next V7R terminal requires -ConfirmFlatStop.'
}

$commonModule = Join-Path $PSScriptRoot 'ZetaNextOperatorCommon.psm1'
Import-Module $commonModule -Force
$contract = Get-ZetaNextOperatorContract
$inventory = Assert-ZetaNextExclusiveTerminalBoundary -Contract $contract -AllowExactLive
if (@($inventory.ExactLive).Count -ne 1) {
    throw "Exactly one Next Live-Dev terminal is required; found $(@($inventory.ExactLive).Count)."
}

$status = (& $contract.StatusScript -AsJson -ExpectedMode Auto | Out-String) | ConvertFrom-Json
$flat = (
    [bool]$status.healthy -and
    [int]$status.project_terminal_pid -eq [int]$inventory.ExactLive[0].Id -and
    @($status.components).Count -eq $contract.ComponentIds.Count -and
    [int]$status.new_entries_input -eq 0 -and
    [int]$status.new_entries_effective -eq 0 -and
    [math]::Abs([double]$status.account_margin) -le 0.01 -and
    [math]::Abs([double]$status.aggregate_planned_risk) -le 0.01 -and
    [long]$status.passive_pending_order -eq 0 -and
    [long]$status.arc.lifecycle_identifier -eq 0 -and
    [int]$status.retry.pending -eq 0 -and
    [int]$status.shadow.occupied -eq 0 -and
    @($status.components | Where-Object { [long]$_.position_identifier -ne 0 }).Count -eq 0
)
if (-not $flat) {
    throw 'Refusing to stop Next V7R: the local snapshot is not 0-entry, flat, zero-margin, zero-risk, and free of pending ownership.'
}

$processId = [int]$inventory.ExactLive[0].Id
Stop-ZetaNextRuntime -Contract $contract -ProcessId $processId
Write-Output "Stopped verified-flat Next V7R runtime PID $processId. State and bounded logs were preserved."
