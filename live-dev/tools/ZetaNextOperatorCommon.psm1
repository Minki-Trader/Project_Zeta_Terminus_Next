Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-ZetaNextOperatorContract {
    $liveDevRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
    $projectRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $liveDevRoot))
    $runtimeRoot = Join-Path $liveDevRoot 'runtime\portable'
    $packageRoot = Join-Path $liveDevRoot 'package\active'

    [pscustomobject]@{
        ProjectRoot = $projectRoot
        LiveDevRoot = $liveDevRoot
        RuntimeRoot = $runtimeRoot
        PackageRoot = $packageRoot
        TerminalPath = Join-Path $runtimeRoot 'terminal64.exe'
        StatePath = Join-Path $projectRoot 'CURRENT_STATE.md'
        StatusScript = Join-Path $PSScriptRoot 'Get-ZetaNextV7Status.ps1'
        HandoffReceiptPath = Join-Path $liveDevRoot 'runtime\handoff\legacy-final-handoff.json'
        ReleaseTransitionReceiptPath = Join-Path $liveDevRoot 'runtime\handoff\live-release-transition-cxr2.json'
        LegacyRoot = 'C:\Users\awdse\OneDrive\Desktop\Project_Zeta_Terminus'
        ProjectId = 'project-zeta-terminus-next'
        ReleaseId = 'NEXT-E01-V7-CXR2-14d84b9e4bb3'
        RootHandoffReleaseId = 'NEXT-E01-V7-2db5ef5ead1c'
        TransitionParentReleaseId = 'NEXT-E01-V7-CXR1-c0ad2f30d293'
        PortfolioId = 'ZT-PORT-NEXT-V7-2db5ef5ead1c'
        ExecutionVersion = 'zt-next-pre500-finite-risk-portfolio-v7-modular-2db5ef5ead1c'
        EconomicVersion = 'zt-next-pre500-finite-risk-portfolio-v7-modular-parent-b70-v6r6'
        FilePrefix = 'zt-next-pre500-finite-risk-portfolio-v7-modular-2db5ef5ead1c'
        SourceHash = 'D210A662A51FE5691CBC9A3FC4DD376A2826D848DC904FBD578F7B9C9911FDB1'
        ExpertHash = '620D0351AF22EAA389BE7F36CBD3AB6C9D2204D182E897CFE6A845495428CFC6'
        SetHash = 'BEBA34FE89B01EC4F1582C2C1EA4BC02E8FB73E0D78B78BAB833EEC63F8065E8'
        SourceManifestHash = 'DD2F9693015034E442B26D3B1831BB59A0C8BB83C5F06CA7BF51648235186980'
        MagicNumbers = @(260824701L, 260824702L, 260824703L, 260824704L, 260824705L, 260824706L)
        ComponentIds = @(
            'ZT-M30-US30-RANGE-COMP-61f61deaba',
            'ZT-M30-US30-RANGE-COMP-64efb16616',
            'ZT-H1-US100-CROSS-IN-14b72317b7',
            'ZT-M30-US30-INTRADAY-R-2eb111fc46',
            'ZT-H1-US30-RETURN-I-c870a788ec',
            'ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8'
        )
    }
}

function Get-NormalizedTextSha256 {
    param([Parameter(Mandatory)][string]$Path)

    $text = [System.IO.File]::ReadAllText($Path)
    $normalized = $text.Replace("`r`n", "`n").Replace("`r", "`n")
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($normalized)
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        [System.Convert]::ToHexString($sha256.ComputeHash($bytes))
    } finally {
        $sha256.Dispose()
    }
}

function Test-PathInside {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Root
    )

    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    $resolvedRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $resolvedPath.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-ZetaNextTerminalInventory {
    param([Parameter(Mandatory)]$Contract)

    $processes = @(Get-Process -Name terminal64, metatester64 -ErrorAction SilentlyContinue)
    $exactLive = @($processes | Where-Object {
        try {
            $_.Path -and
            [System.IO.Path]::GetFullPath($_.Path) -eq [System.IO.Path]::GetFullPath($Contract.TerminalPath)
        } catch { $false }
    })
    $legacy = @($processes | Where-Object {
        try { $_.Path -and (Test-PathInside -Path $_.Path -Root $Contract.LegacyRoot) } catch { $false }
    })
    $otherNext = @($processes | Where-Object {
        try {
            $_.Path -and
            (Test-PathInside -Path $_.Path -Root $Contract.ProjectRoot) -and
            [System.IO.Path]::GetFullPath($_.Path) -ne [System.IO.Path]::GetFullPath($Contract.TerminalPath)
        } catch { $false }
    })

    [pscustomobject]@{
        ExactLive = $exactLive
        Legacy = $legacy
        OtherNext = $otherNext
    }
}

function Assert-ZetaNextExclusiveTerminalBoundary {
    param(
        [Parameter(Mandatory)]$Contract,
        [switch]$AllowExactLive
    )

    $inventory = Get-ZetaNextTerminalInventory -Contract $Contract
    if (@($inventory.Legacy).Count -gt 0) {
        throw "Legacy Terminus terminal is still running (PID $(@($inventory.Legacy.Id) -join ', '))."
    }
    if (@($inventory.OtherNext).Count -gt 0) {
        throw "Another Next terminal/tester is running (PID $(@($inventory.OtherNext.Id) -join ', '))."
    }
    if (-not $AllowExactLive -and @($inventory.ExactLive).Count -gt 0) {
        throw "Next Live-Dev terminal is already running (PID $(@($inventory.ExactLive.Id) -join ', '))."
    }
    if (@($inventory.ExactLive).Count -gt 1) {
        throw "Multiple Next Live-Dev terminals are running (PID $(@($inventory.ExactLive.Id) -join ', '))."
    }
    $inventory
}

function Assert-ZetaNextReleaseIntegrity {
    param([Parameter(Mandatory)]$Contract)

    $sourcePath = Join-Path $Contract.PackageRoot 'MQL5\Experts\ZetaTerminusNext\ZetaNextPre500FiniteRiskPortfolioV7.mq5'
    $expertPath = Join-Path $Contract.PackageRoot 'MQL5\Experts\ZetaTerminusNext\ZetaNextPre500FiniteRiskPortfolioV7.ex5'
    $setPath = Join-Path $Contract.PackageRoot 'MQL5\Presets\ZetaTerminusNext\next-v7-modular.set'
    $sourceManifestPath = Join-Path $Contract.PackageRoot 'SOURCE_MANIFEST.json'
    $releaseManifestPath = Join-Path $Contract.PackageRoot 'RELEASE_MANIFEST.json'
    foreach ($path in @($sourcePath, $expertPath, $setPath, $sourceManifestPath, $releaseManifestPath, $Contract.TerminalPath, $Contract.StatusScript, $Contract.StatePath)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Required Next V7 operator file is missing: $path"
        }
    }

    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $sourcePath).Hash -ne $Contract.SourceHash -or
        (Get-FileHash -Algorithm SHA256 -LiteralPath $expertPath).Hash -ne $Contract.ExpertHash -or
        (Get-NormalizedTextSha256 -Path $setPath) -ne $Contract.SetHash -or
        (Get-FileHash -Algorithm SHA256 -LiteralPath $sourceManifestPath).Hash -ne $Contract.SourceManifestHash) {
        throw 'The frozen active V7 source, EX5, SET, or source manifest hash does not match the operator contract.'
    }

    $releaseManifest = Get-Content -LiteralPath $releaseManifestPath -Raw | ConvertFrom-Json
    if ([string]$releaseManifest.project_id -ne $Contract.ProjectId -or
        [string]$releaseManifest.release_id -ne $Contract.ReleaseId -or
        [string]$releaseManifest.parent_release_id -ne $Contract.TransitionParentReleaseId -or
        [string]$releaseManifest.portfolio_id -ne $Contract.PortfolioId -or
        [string]$releaseManifest.execution_version -ne $Contract.ExecutionVersion -or
        [string]$releaseManifest.real_tick_equivalence -ne 'passed' -or
        [string]$releaseManifest.compiled_ex5_sha256 -ne $Contract.ExpertHash -or
        [string]$releaseManifest.source_manifest_sha256 -ne $Contract.SourceManifestHash) {
        throw 'The active release manifest does not identify the verified V7 package.'
    }

    $sourceManifest = Get-Content -LiteralPath $sourceManifestPath -Raw | ConvertFrom-Json
    if ([string]$sourceManifest.release_id -ne $Contract.ReleaseId -or
        [string]$sourceManifest.execution_version -ne $Contract.ExecutionVersion -or
        [string]$sourceManifest.portfolio_id -ne $Contract.PortfolioId) {
        throw 'The source manifest identity does not match the operator contract.'
    }
    foreach ($file in @($sourceManifest.files)) {
        $relative = [string]$file.path
        if (-not $relative.StartsWith('MQL5/', [System.StringComparison]::Ordinal)) {
            throw "Unexpected source manifest path: $relative"
        }
        $packagePath = Join-Path $Contract.PackageRoot $relative.Replace('/', '\')
        if (-not (Test-PathInside -Path $packagePath -Root $Contract.PackageRoot)) {
            throw "Source manifest path escaped the active package: $relative"
        }
        if (-not (Test-Path -LiteralPath $packagePath -PathType Leaf) -or
            (Get-FileHash -Algorithm SHA256 -LiteralPath $packagePath).Hash -ne [string]$file.sha256) {
            throw "Frozen package file differs from the source manifest: $relative"
        }
    }

    $head = (& git -C $Contract.ProjectRoot rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Could not read the Next Git HEAD.' }
    $originMain = (& git -C $Contract.ProjectRoot rev-parse origin/main).Trim()
    if ($LASTEXITCODE -ne 0 -or $head -ne $originMain) {
        throw 'Local Next HEAD must match origin/main before any operator runtime starts.'
    }
    foreach ($relativePath in @(
        'CURRENT_STATE.md',
        'ZETA_NEXT_MASTER_TERMINAL_AND_DASHBOARD.cmd',
        'live-dev/package/active',
        'live-dev/tools'
    )) {
        $tracked = @(& git -C $Contract.ProjectRoot ls-files -- $relativePath)
        if ($LASTEXITCODE -ne 0 -or $tracked.Count -eq 0) {
            throw "Next operator path is not committed: $relativePath"
        }
        & git -C $Contract.ProjectRoot diff --quiet -- $relativePath
        if ($LASTEXITCODE -ne 0) { throw "Next operator path differs from HEAD: $relativePath" }
        & git -C $Contract.ProjectRoot diff --cached --quiet HEAD -- $relativePath
        if ($LASTEXITCODE -ne 0) { throw "Next operator path has staged changes: $relativePath" }
    }

    [pscustomobject]@{
        GitHead = $head
        SourcePath = $sourcePath
        ExpertPath = $expertPath
        SetPath = $setPath
        ReleaseManifest = $releaseManifest
    }
}

function Get-ZetaNextHandoffReceipt {
    param([Parameter(Mandatory)]$Contract)

    foreach ($receiptPath in @($Contract.HandoffReceiptPath, $Contract.ReleaseTransitionReceiptPath)) {
        if (-not (Test-Path -LiteralPath $receiptPath -PathType Leaf)) {
            throw "Required local handoff receipt is missing: $receiptPath"
        }
    }
    $rootReceipt = Get-Content -LiteralPath $Contract.HandoffReceiptPath -Raw | ConvertFrom-Json
    if ([string]$rootReceipt.project_id -ne $Contract.ProjectId -or
        [string]$rootReceipt.target_release_id -ne $Contract.RootHandoffReleaseId -or
        -not [bool]$rootReceipt.legacy_flat_verified -or
        -not [bool]$rootReceipt.outside_all_entry_windows -or
        -not [bool]$rootReceipt.no_incomplete_decision -or
        [long]$rootReceipt.account_login -le 0 -or
        -not ([string]$rootReceipt.legacy_final_state_sha256 -match '^[0-9A-Fa-f]{64}$') -or
        -not ([string]$rootReceipt.legacy_final_log_sha256 -match '^[0-9A-Fa-f]{64}$') -or
        -not [double]::IsFinite([double]$rootReceipt.prior_project_realized_net_usd) -or
        100.0 + [double]$rootReceipt.prior_project_realized_net_usd -le 0.0) {
        throw 'The local root handoff receipt is incomplete or does not identify the original V7 account handoff.'
    }
    $transition = Get-Content -LiteralPath $Contract.ReleaseTransitionReceiptPath -Raw | ConvertFrom-Json
    if ([string]$transition.project_id -ne $Contract.ProjectId -or
        [string]$transition.parent_release_id -ne $Contract.TransitionParentReleaseId -or
        [string]$transition.target_release_id -ne $Contract.ReleaseId -or
        [string]$transition.execution_version -ne $Contract.ExecutionVersion -or
        [string]$transition.portfolio_id -ne $Contract.PortfolioId -or
        [long]$transition.account_login -ne [long]$rootReceipt.account_login -or
        -not [bool]$transition.parent_runtime_stopped_normally -or
        -not [bool]$transition.outside_all_entry_windows -or
        -not [bool]$transition.no_incomplete_decision -or
        [long]$transition.captured_state_sequence -le 0 -or
        -not [double]::IsFinite([double]$transition.continuity.expected_project_realized_net_usd) -or
        -not [double]::IsFinite([double]$transition.continuity.expected_project_stage_balance_usd)) {
        throw 'The local release-transition receipt is incomplete or does not target the active V7 package.'
    }

    $tradesRoot = Join-Path $Contract.RuntimeRoot 'Bases\FPMarketsSC-Live\trades'
    $accounts = @(if (Test-Path -LiteralPath $tradesRoot -PathType Container) {
        Get-ChildItem -LiteralPath $tradesRoot -Directory | Where-Object Name -match '^\d+$'
    })
    if ($accounts.Count -ne 1 -or [long]$accounts[0].Name -ne [long]$rootReceipt.account_login) {
        throw 'Next Live Portable must contain exactly the account named by the flat-handoff receipt.'
    }
    [pscustomobject]@{
        account_login = [long]$rootReceipt.account_login
        prior_project_realized_net_usd = [double]$rootReceipt.prior_project_realized_net_usd
        expected_account_balance_usd = [double]$transition.continuity.expected_account_balance_usd
        expected_account_equity_usd = [double]$transition.continuity.expected_account_equity_usd
        expected_project_realized_net_usd = [double]$transition.continuity.expected_project_realized_net_usd
        expected_project_stage_balance_usd = [double]$transition.continuity.expected_project_stage_balance_usd
        expected_stressed_balance_usd = [double]$transition.continuity.expected_stressed_balance_usd
        root_handoff = $rootReceipt
        release_transition = $transition
    }
}

function Write-ZetaNextRuntimeMode {
    param(
        [Parameter(Mandatory)]$Contract,
        [Parameter(Mandatory)]$Receipt,
        [Parameter(Mandatory)][ValidateSet('EntriesDisabled', 'LivePreflight', 'Live')][string]$Mode
    )

    $modeData = switch ($Mode) {
        'EntriesDisabled' { [pscustomobject]@{ Entries = $false; AllowLiveTrading = 0; SetName = 'next-v7-entries-disabled.set'; ConfigName = 'terminal-next-v7-entries-disabled.ini' } }
        'LivePreflight' { [pscustomobject]@{ Entries = $false; AllowLiveTrading = 1; SetName = 'next-v7-live-preflight.set'; ConfigName = 'terminal-next-v7-live-preflight.ini' } }
        'Live' { [pscustomobject]@{ Entries = $true; AllowLiveTrading = 1; SetName = 'next-v7-live.set'; ConfigName = 'terminal-next-v7-live.ini' } }
    }
    $baseSetPath = Join-Path $Contract.PackageRoot 'MQL5\Presets\ZetaTerminusNext\next-v7-modular.set'
    $runtimePresetDirectory = Join-Path $Contract.RuntimeRoot 'MQL5\Presets\ZetaTerminusNextRuntime'
    $runtimeConfigDirectory = Join-Path $Contract.RuntimeRoot 'Config'
    $setPath = Join-Path $runtimePresetDirectory $modeData.SetName
    $configPath = Join-Path $runtimeConfigDirectory $modeData.ConfigName
    foreach ($path in @($runtimePresetDirectory, $runtimeConfigDirectory)) {
        if (-not (Test-PathInside -Path $path -Root $Contract.RuntimeRoot)) {
            throw "Runtime output escaped the Next Live Portable: $path"
        }
        [System.IO.Directory]::CreateDirectory($path) | Out-Null
    }

    $priorText = ([double]$Receipt.prior_project_realized_net_usd).ToString('0.###############', [Globalization.CultureInfo]::InvariantCulture)
    $accountText = ([long]$Receipt.account_login).ToString([Globalization.CultureInfo]::InvariantCulture)
    $entriesText = if ($modeData.Entries) { 'true' } else { 'false' }
    $setText = Get-Content -LiteralPath $baseSetPath -Raw
    $setText = $setText.Replace(
        'InpPriorProjectRealizedNetUSD=0.0||0.0||0.000000||0.000000||N',
        "InpPriorProjectRealizedNetUSD=$priorText||$priorText||0.000000||$priorText||N"
    )
    $setText = $setText.Replace(
        'InpAllowNewEntries=false||false||0||true||N',
        "InpAllowNewEntries=$entriesText||false||0||true||N"
    )
    $setText = $setText.Replace(
        'InpExpectedLiveAccountLogin=0||0||1||10||N',
        "InpExpectedLiveAccountLogin=$accountText||$accountText||1||$accountText||N"
    )
    if ($setText -notmatch "(?m)^InpPriorProjectRealizedNetUSD=$([regex]::Escape($priorText))\|\|" -or
        $setText -notmatch "(?m)^InpAllowNewEntries=$entriesText\|\|" -or
        $setText -notmatch "(?m)^InpExpectedLiveAccountLogin=$accountText\|\|") {
        throw "Could not construct the exact account-bound V7 SET for $Mode."
    }

    $configText = @"
[Common]
KeepPrivate=1
NewsEnable=0
CertInstall=0

[Experts]
Enabled=1
AllowLiveTrading=$($modeData.AllowLiveTrading)
AllowDllImport=0
Account=1
Profile=1

[Charts]
MaxBars=500000

[StartUp]
Expert=ZetaTerminusNext\ZetaNextPre500FiniteRiskPortfolioV7.ex5
ExpertParameters=ZetaTerminusNextRuntime\$($modeData.SetName)
Symbol=US30
Period=M30
ShutdownTerminal=0
"@
    $utf8 = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($setPath, $setText, $utf8)
    [System.IO.File]::WriteAllText($configPath, $configText, $utf8)
    [pscustomobject]@{ Mode = $Mode; SetPath = $setPath; ConfigPath = $configPath; AccountLogin = [long]$Receipt.account_login }
}

function Start-ZetaNextRuntime {
    param(
        [Parameter(Mandatory)]$Contract,
        [Parameter(Mandatory)]$RuntimeMode
    )

    Start-Process -FilePath $Contract.TerminalPath `
        -ArgumentList @('/portable', "/config:$($RuntimeMode.ConfigPath)", "/login:$($RuntimeMode.AccountLogin)") `
        -WorkingDirectory $Contract.RuntimeRoot `
        -WindowStyle Hidden `
        -PassThru
}

function Stop-ZetaNextRuntime {
    param(
        [Parameter(Mandatory)]$Contract,
        [Parameter(Mandatory)][int]$ProcessId
    )

    $process = Get-Process -Id $ProcessId -ErrorAction Stop
    if (-not $process.Path -or
        [System.IO.Path]::GetFullPath($process.Path) -ne [System.IO.Path]::GetFullPath($Contract.TerminalPath)) {
        throw "PID $ProcessId is not the exact Next Live-Dev terminal."
    }
    $closeRequested = $false
    try { $closeRequested = $process.CloseMainWindow() } catch { }
    if ($closeRequested) {
        try { Wait-Process -Id $ProcessId -Timeout 15 -ErrorAction Stop } catch { }
    }
    if ($null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $ProcessId -ErrorAction Stop
        try { Wait-Process -Id $ProcessId -Timeout 15 -ErrorAction Stop } catch { }
    }
    if ($null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) {
        throw "Next Live-Dev PID $ProcessId did not stop."
    }
}

function Get-ZetaNextRuntimeStatus {
    param(
        [Parameter(Mandatory)]$Contract,
        [Parameter(Mandatory)][ValidateSet('EntriesDisabled', 'LivePreflight', 'Live')][string]$Mode
    )

    ((& $Contract.StatusScript -AsJson -ExpectedMode $Mode | Out-String) | ConvertFrom-Json)
}

function Wait-ZetaNextRuntimeStatus {
    param(
        [Parameter(Mandatory)]$Contract,
        [Parameter(Mandatory)]$RuntimeMode,
        [Parameter(Mandatory)][int]$ProcessId,
        [Parameter(Mandatory)][scriptblock]$Predicate,
        [ValidateRange(5, 180)][int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if ($null -eq $process) { return $null }
        try {
            $processInfo = Get-CimInstance -ClassName Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction Stop
            if ([string]::IsNullOrWhiteSpace([string]$processInfo.CommandLine) -or
                ([string]$processInfo.CommandLine).IndexOf($RuntimeMode.ConfigPath, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
                return $null
            }
        } catch { return $null }
        try {
            $status = Get-ZetaNextRuntimeStatus -Contract $Contract -Mode $RuntimeMode.Mode
            if ([bool]$status.healthy -and (& $Predicate $status)) { return $status }
        } catch { }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)
    $null
}

function Test-ZetaNextFlatStatus {
    param(
        [Parameter(Mandatory)]$Status,
        [Parameter(Mandatory)]$Receipt
    )

    if ([int]$Status.new_entries_input -ne 0 -or [int]$Status.new_entries_effective -ne 0 -or
        [double]$Status.account_balance -le 0.0 -or [double]$Status.account_equity -le 0.0 -or
        [math]::Abs([double]$Status.account_balance - [double]$Status.account_equity) -gt 0.01 -or
        [math]::Abs([double]$Status.account_margin) -gt 0.01 -or
        [math]::Abs([double]$Status.aggregate_planned_risk) -gt 0.01 -or
        [long]$Status.passive_pending_order -ne 0 -or
        [long]$Status.arc.lifecycle_identifier -ne 0 -or
        [int]$Status.retry.pending -ne 0 -or [int]$Status.shadow.occupied -ne 0 -or
        @($Status.components | Where-Object { [long]$_.position_identifier -ne 0 }).Count -ne 0 -or
        [math]::Abs([double]$Status.account_balance - [double]$Receipt.expected_account_balance_usd) -gt 0.005 -or
        [math]::Abs([double]$Status.account_equity - [double]$Receipt.expected_account_equity_usd) -gt 0.005 -or
        [math]::Abs([double]$Status.project_realized_net - [double]$Receipt.expected_project_realized_net_usd) -gt 0.005 -or
        [math]::Abs([double]$Status.project_stage_balance - [double]$Receipt.expected_project_stage_balance_usd) -gt 0.005 -or
        [math]::Abs([double]$Status.stressed_balance - [double]$Receipt.expected_stressed_balance_usd) -gt 0.005) {
        return $false
    }
    $true
}

function Test-ZetaNextLiveStatus {
    param([Parameter(Mandatory)]$Status)

    if ([int]$Status.new_entries_input -ne 1 -or [int]$Status.new_entries_effective -ne 1) { return $false }
    $riskCapital = @(
        [double]$Status.stressed_balance,
        [double]$Status.project_stage_balance,
        [double]$Status.account_balance,
        [double]$Status.account_equity
    ) | Measure-Object -Minimum | Select-Object -ExpandProperty Minimum
    if ([double]$Status.aggregate_planned_risk -gt 0.12 * $riskCapital + 0.02) { return $false }
    foreach ($component in @($Status.components | Where-Object { [long]$_.position_identifier -ne 0 })) {
        if ([double]$component.entry_stop_loss -le 0.0 -or
            [double]$component.entry_planned_risk -le 0.0 -or
            [double]$component.entry_planned_risk -gt 0.04 * $riskCapital + 0.02) {
            return $false
        }
    }
    $true
}

Export-ModuleMember -Function @(
    'Get-ZetaNextOperatorContract',
    'Get-NormalizedTextSha256',
    'Test-PathInside',
    'Get-ZetaNextTerminalInventory',
    'Assert-ZetaNextExclusiveTerminalBoundary',
    'Assert-ZetaNextReleaseIntegrity',
    'Get-ZetaNextHandoffReceipt',
    'Write-ZetaNextRuntimeMode',
    'Start-ZetaNextRuntime',
    'Stop-ZetaNextRuntime',
    'Get-ZetaNextRuntimeStatus',
    'Wait-ZetaNextRuntimeStatus',
    'Test-ZetaNextFlatStatus',
    'Test-ZetaNextLiveStatus'
)
