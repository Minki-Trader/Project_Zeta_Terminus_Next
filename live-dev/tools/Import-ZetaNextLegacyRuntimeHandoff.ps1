[CmdletBinding()]
param(
    [Parameter(Mandatory)][double]$PriorProjectRealizedNetUSD,
    [Parameter(Mandatory)][string]$LegacyFinalStatePath,
    [Parameter(Mandatory)][string]$LegacyFinalLogPath,
    [switch]$ConfirmLegacyFlat,
    [switch]$ConfirmOutsideAllEntryWindows,
    [switch]$ConfirmNoIncompleteDecision
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

if (-not $ConfirmLegacyFlat -or -not $ConfirmOutsideAllEntryWindows -or -not $ConfirmNoIncompleteDecision) {
    throw 'Runtime handoff import requires all three flat/window/decision confirmations.'
}
if (-not [double]::IsFinite($PriorProjectRealizedNetUSD) -or 100.0 + $PriorProjectRealizedNetUSD -le 0.0) {
    throw 'The final project-attributable realized net would make the inherited stage capital invalid.'
}

$commonModule = Join-Path $PSScriptRoot 'ZetaNextOperatorCommon.psm1'
Import-Module $commonModule -Force
$contract = Get-ZetaNextOperatorContract
$null = Assert-ZetaNextExclusiveTerminalBoundary -Contract $contract
$null = Assert-ZetaNextReleaseIntegrity -Contract $contract

$authorization = Get-Content -LiteralPath $contract.StatePath -Raw
if ($authorization -notmatch 'Next V7 entries-disabled preflight:\s+`ENABLED`' -or
    $authorization -notmatch 'Next V7 new-entry authorization:\s+`DISABLED`' -or
    $authorization -notmatch 'Existing real-account owner:\s+none') {
    throw 'CURRENT_STATE.md does not place the project in the flat, entries-disabled handoff boundary.'
}
$legacyStateText = Get-Content -LiteralPath (Join-Path $contract.LegacyRoot 'CURRENT_STATE.md') -Raw
if ($legacyStateText -notmatch 'Handoff flat verification:\s+`PASSED`' -or
    $legacyStateText -notmatch 'Handoff entry-window check:\s+`PASSED`' -or
    $legacyStateText -notmatch 'Handoff incomplete decisions:\s+`0`') {
    throw 'Legacy CURRENT_STATE.md does not contain the final flat/window/no-decision handoff record.'
}

$legacyFinalState = [System.IO.Path]::GetFullPath($LegacyFinalStatePath)
$legacyFinalLog = [System.IO.Path]::GetFullPath($LegacyFinalLogPath)
foreach ($path in @($legacyFinalState, $legacyFinalLog)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
        -not (Test-PathInside -Path $path -Root $contract.LegacyRoot)) {
        throw "Legacy final evidence is missing or outside the legacy repository: $path"
    }
}

$legacyRuntime = Join-Path $contract.LegacyRoot 'mt5\runtime'
$sourceBrokerCache = Join-Path $legacyRuntime 'Bases\FPMarketsSC-Live'
$sourceConfig = Join-Path $legacyRuntime 'Config'
foreach ($path in @($sourceBrokerCache, $sourceConfig)) {
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        throw "Legacy runtime cache is missing: $path"
    }
}
$sourceAccounts = @(Get-ChildItem -LiteralPath (Join-Path $sourceBrokerCache 'trades') -Directory | Where-Object Name -match '^\d+$')
if ($sourceAccounts.Count -ne 1) {
    throw 'Legacy runtime must expose exactly one locally cached FPMarkets account at handoff.'
}
$accountLogin = [long]$sourceAccounts[0].Name

$targetBases = Join-Path $contract.RuntimeRoot 'Bases'
$targetBrokerCache = Join-Path $targetBases 'FPMarketsSC-Live'
$targetConfig = Join-Path $contract.RuntimeRoot 'Config'
$targetHandoffDirectory = Split-Path -Parent $contract.HandoffReceiptPath
foreach ($path in @($targetBrokerCache, $targetConfig, $targetHandoffDirectory)) {
    if (-not (Test-PathInside -Path $path -Root $contract.LiveDevRoot)) {
        throw "Handoff target escaped live-dev: $path"
    }
}
if (Test-Path -LiteralPath $targetBrokerCache) {
    throw "Next broker cache target already exists; refusing overwrite: $targetBrokerCache"
}
if (Test-Path -LiteralPath $contract.HandoffReceiptPath -PathType Leaf) {
    throw "Next handoff receipt already exists; refusing overwrite: $($contract.HandoffReceiptPath)"
}
if ((Test-Path -LiteralPath $targetConfig -PathType Container) -and
    @(Get-ChildItem -LiteralPath $targetConfig -Force).Count -gt 0) {
    throw 'Next Config directory is not empty; refusing to merge account cache.'
}

[System.IO.Directory]::CreateDirectory($targetBases) | Out-Null
[System.IO.Directory]::CreateDirectory($targetConfig) | Out-Null
[System.IO.Directory]::CreateDirectory($targetHandoffDirectory) | Out-Null
Copy-Item -LiteralPath $sourceBrokerCache -Destination $targetBases -Recurse
Get-ChildItem -LiteralPath $sourceConfig -Force | Copy-Item -Destination $targetConfig -Recurse

$copiedAccounts = @(Get-ChildItem -LiteralPath (Join-Path $targetBrokerCache 'trades') -Directory | Where-Object Name -match '^\d+$')
if ($copiedAccounts.Count -ne 1 -or [long]$copiedAccounts[0].Name -ne $accountLogin) {
    throw 'Copied Next broker cache does not expose the exact legacy account.'
}
$legacyCommit = (& git -C $contract.LegacyRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $legacyCommit -notmatch '^[0-9a-f]{40}$') {
    throw 'Could not record the final legacy Git commit.'
}
$receipt = [ordered]@{
    schema_version = 1
    project_id = $contract.ProjectId
    target_release_id = $contract.ReleaseId
    account_login = $accountLogin
    prior_project_realized_net_usd = $PriorProjectRealizedNetUSD
    legacy_repository = 'Minki-Trader/Project_Zeta_Terminus'
    legacy_final_commit = $legacyCommit
    legacy_final_state_path = [System.IO.Path]::GetRelativePath($contract.LegacyRoot, $legacyFinalState).Replace('\', '/')
    legacy_final_state_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $legacyFinalState).Hash
    legacy_final_log_path = [System.IO.Path]::GetRelativePath($contract.LegacyRoot, $legacyFinalLog).Replace('\', '/')
    legacy_final_log_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $legacyFinalLog).Hash
    legacy_flat_verified = $true
    outside_all_entry_windows = $true
    no_incomplete_decision = $true
    imported_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    git_included = $false
}
$utf8 = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText(
    $contract.HandoffReceiptPath,
    ($receipt | ConvertTo-Json -Depth 5) + [Environment]::NewLine,
    $utf8
)

Write-Output "Imported the stopped legacy account/broker cache into the Next Live Portable for account $accountLogin."
Write-Output "Wrote local handoff receipt: $($contract.HandoffReceiptPath)"
Write-Output 'No terminal was started and Next new-entry authorization remains disabled.'
