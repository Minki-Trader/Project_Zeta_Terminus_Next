[CmdletBinding()]
param(
    [switch]$AsJson,
    [ValidateSet('Auto', 'EntriesDisabled', 'LivePreflight', 'Live')]
    [string]$ExpectedMode = 'Auto'
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$liveDevRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$projectRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $liveDevRoot))
$runtimeRoot = Join-Path $liveDevRoot 'runtime\portable'
$terminalPath = Join-Path $runtimeRoot 'terminal64.exe'
$expertPath = Join-Path $runtimeRoot 'MQL5\Experts\ZetaTerminusNext\ZetaNextPre500FiniteRiskPortfolioV7.ex5'
$liveDirectory = Join-Path $runtimeRoot 'MQL5\Files\ZetaTerminusNext\live'
$statePath = Join-Path $projectRoot 'CURRENT_STATE.md'
$legacyRoot = 'C:\Users\awdse\OneDrive\Desktop\Project_Zeta_Terminus'
$runtimeModes = [ordered]@{
    EntriesDisabled = [pscustomobject]@{
        OperatorMode = 'NEXT_V7_ENTRIES_DISABLED'
        ConfigPath = Join-Path $runtimeRoot 'config\terminal-next-v7-entries-disabled.ini'
        SetPath = Join-Path $runtimeRoot 'MQL5\Presets\ZetaTerminusNextRuntime\next-v7-entries-disabled.set'
        ExpectedEntries = 0
        AllowLiveTrading = 0
    }
    LivePreflight = [pscustomobject]@{
        OperatorMode = 'NEXT_V7_LIVE_PREFLIGHT'
        ConfigPath = Join-Path $runtimeRoot 'config\terminal-next-v7-live-preflight.ini'
        SetPath = Join-Path $runtimeRoot 'MQL5\Presets\ZetaTerminusNextRuntime\next-v7-live-preflight.set'
        ExpectedEntries = 0
        AllowLiveTrading = 1
    }
    Live = [pscustomobject]@{
        OperatorMode = 'NEXT_V7_LIVE'
        ConfigPath = Join-Path $runtimeRoot 'config\terminal-next-v7-live.ini'
        SetPath = Join-Path $runtimeRoot 'MQL5\Presets\ZetaTerminusNextRuntime\next-v7-live.set'
        ExpectedEntries = 1
        AllowLiveTrading = 1
    }
}

$expectedExpertHash = 'CB225D97DA7BCEC30599B472F615C7A3775C359A0F8FA8293FBB9C222795775B'
$expectedSchemaVersion = '7'
$expectedReleaseId = 'NEXT-E01-V7-RLO1-b32e7e176f2e'
$expectedProjectId = 'project-zeta-terminus-next'
$expectedExecutionVersion = 'zt-next-pre500-finite-risk-portfolio-v7-modular-2db5ef5ead1c'
$expectedEconomicVersion = 'zt-next-pre500-finite-risk-portfolio-v7-modular-parent-b70-v6r6'
$expectedPortfolioId = 'ZT-PORT-NEXT-V7-2db5ef5ead1c'
$filePrefix = 'zt-next-pre500-finite-risk-portfolio-v7-modular-2db5ef5ead1c'
$expectedComponents = [ordered]@{
    'ZT-M30-US30-RANGE-COMP-61f61deaba' = 260824701L
    'ZT-M30-US30-RANGE-COMP-64efb16616' = 260824702L
    'ZT-H1-US100-CROSS-IN-14b72317b7' = 260824703L
    'ZT-M30-US30-INTRADAY-R-2eb111fc46' = 260824704L
    'ZT-H1-US30-RETURN-I-c870a788ec' = 260824705L
    'ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8' = 260824706L
}

function Read-SharedText {
    param([Parameter(Mandatory)][string]$Path)

    for ($attempt = 0; $attempt -lt 10; $attempt++) {
        $stream = $null
        try {
            $stream = [System.IO.File]::Open(
                $Path,
                [System.IO.FileMode]::Open,
                [System.IO.FileAccess]::Read,
                [System.IO.FileShare]::ReadWrite
            )
            $reader = [System.IO.StreamReader]::new($stream)
            try {
                return $reader.ReadToEnd()
            } finally {
                $reader.Dispose()
                $stream = $null
            }
        } catch {
            if ($null -ne $stream) { $stream.Dispose() }
            if ($attempt -eq 9) { throw }
            Start-Sleep -Milliseconds 100
        }
    }
}

function Convert-CsvPair {
    param(
        [Parameter(Mandatory)][string[]]$Lines,
        [Parameter(Mandatory)][string]$HeaderPrefix
    )

    $index = -1
    for ($i = 0; $i -lt $Lines.Count - 1; $i++) {
        if ($Lines[$i].StartsWith($HeaderPrefix, [System.StringComparison]::Ordinal)) {
            $index = $i
            break
        }
    }
    if ($index -lt 0) { return $null }
    return @($Lines[$index], $Lines[$index + 1]) | ConvertFrom-Csv | Select-Object -First 1
}

function Read-V7Snapshot {
    param([Parameter(Mandatory)][string]$Path)

    $lines = @((Read-SharedText -Path $Path) -split "`r?`n" | Where-Object { $_.Length -gt 0 })
    if ($lines.Count -lt 15) { return $null }
    $snapshot = @($lines[0], $lines[1]) | ConvertFrom-Csv | Select-Object -First 1
    $retry = Convert-CsvPair -Lines $lines -HeaderPrefix 'rc4_modify_retry,'
    $shadow = Convert-CsvPair -Lines $lines -HeaderPrefix 'rc4_shadow_recovery,'
    $seal = Convert-CsvPair -Lines $lines -HeaderPrefix 'rc4_shadow_activation_seal,'

    $componentHeader = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i].StartsWith('component_id,magic,', [System.StringComparison]::Ordinal)) {
            $componentHeader = $i
            break
        }
    }
    if ($componentHeader -lt 0 -or $componentHeader + $expectedComponents.Count -ge $lines.Count) {
        return $null
    }
    $componentCsv = @($lines[$componentHeader]) + @($lines[($componentHeader + 1)..($componentHeader + $expectedComponents.Count)])
    $components = @($componentCsv | ConvertFrom-Csv)
    if ($null -eq $snapshot -or $null -eq $retry -or $null -eq $shadow -or $null -eq $seal) {
        return $null
    }
    return [pscustomobject]@{
        File = [System.IO.Path]::GetFileName($Path)
        Snapshot = $snapshot
        Retry = $retry
        Components = $components
        Shadow = $shadow
        Seal = $seal
    }
}

$processes = @(Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object {
    try {
        $_.Path -and
        ([System.IO.Path]::GetFullPath($_.Path) -eq [System.IO.Path]::GetFullPath($terminalPath))
    } catch {
        $false
    }
})
$allTerminalProcesses = @(Get-Process -Name terminal64 -ErrorAction SilentlyContinue)
$legacyProcesses = @($allTerminalProcesses | Where-Object {
    try {
        $_.Path -and [System.IO.Path]::GetFullPath($_.Path).StartsWith(
            [System.IO.Path]::GetFullPath($legacyRoot) + [System.IO.Path]::DirectorySeparatorChar,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    } catch { $false }
})
$otherNextProcesses = @($allTerminalProcesses | Where-Object {
    try {
        if (-not $_.Path) { return $false }
        $resolved = [System.IO.Path]::GetFullPath($_.Path)
        $insideNext = $resolved.StartsWith(
            [System.IO.Path]::GetFullPath($projectRoot) + [System.IO.Path]::DirectorySeparatorChar,
            [System.StringComparison]::OrdinalIgnoreCase
        )
        $insideNext -and $resolved -ne [System.IO.Path]::GetFullPath($terminalPath)
    } catch { $false }
})

$authorizationText = if (Test-Path -LiteralPath $statePath -PathType Leaf) {
    Get-Content -LiteralPath $statePath -Raw
} else {
    ''
}
$livePromotionAuthorized = $authorizationText -match 'Next V7 new-entry authorization:\s+`ENABLED`'
$detectedMode = $null
$processCommandLine = $null
if ($processes.Count -eq 1) {
    try {
        $processInfo = Get-CimInstance -ClassName Win32_Process -Filter "ProcessId=$($processes[0].Id)" -ErrorAction Stop
        $processCommandLine = [string]$processInfo.CommandLine
        foreach ($modeName in $runtimeModes.Keys) {
            if ($processCommandLine.IndexOf(
                    [string]$runtimeModes[$modeName].ConfigPath,
                    [System.StringComparison]::OrdinalIgnoreCase
                ) -ge 0) {
                $detectedMode = [string]$modeName
                break
            }
        }
    } catch {
        $processCommandLine = $null
    }
}

$activeMode = if ($ExpectedMode -ne 'Auto') {
    $ExpectedMode
} elseif (-not [string]::IsNullOrWhiteSpace($detectedMode)) {
    $detectedMode
} elseif ($livePromotionAuthorized) {
    'Live'
} else {
    'EntriesDisabled'
}
$modeContract = $runtimeModes[$activeMode]

$snapshots = @()
if (Test-Path -LiteralPath $liveDirectory -PathType Container) {
    foreach ($file in Get-ChildItem -LiteralPath $liveDirectory -File -Filter "$filePrefix-current-?.csv") {
        try {
            $parsed = Read-V7Snapshot -Path $file.FullName
            if ($null -ne $parsed -and [long]$parsed.Snapshot.state_sequence -ge 0) {
                $snapshots += $parsed
            }
        } catch {
            # The alternating peer remains available while one file is being replaced.
        }
    }
}
$latest = $snapshots | Sort-Object { [long]$_.Snapshot.state_sequence } -Descending | Select-Object -First 1

$events = @()
if (Test-Path -LiteralPath $liveDirectory -PathType Container) {
    foreach ($file in Get-ChildItem -LiteralPath $liveDirectory -File -Filter "$filePrefix-events-?.csv") {
        try {
            $events += @((Read-SharedText -Path $file.FullName) | ConvertFrom-Csv)
        } catch {
            # A rotating segment may be replaced between enumeration and read.
        }
    }
}
$latestEvents = @($events |
    Where-Object { $_.event -and $_.event -ne 'event' } |
    Sort-Object { [long]$_.state_sequence } -Descending |
    Select-Object -First 10 |
    Sort-Object { [long]$_.state_sequence })

$alerts = [System.Collections.Generic.List[string]]::new()
$warnings = [System.Collections.Generic.List[string]]::new()
if ($processes.Count -ne 1) {
    $alerts.Add("project_terminal_process_count=$($processes.Count)")
}
if ($legacyProcesses.Count -gt 0) {
    $alerts.Add("legacy_terminus_terminal_running=$(@($legacyProcesses.Id) -join ',')")
}
if ($otherNextProcesses.Count -gt 0) {
    $alerts.Add("other_next_terminal_running=$(@($otherNextProcesses.Id) -join ',')")
}
if (-not (Test-Path -LiteralPath $expertPath -PathType Leaf)) {
    $alerts.Add('next_v7_ex5_missing')
} elseif ((Get-FileHash -Algorithm SHA256 -LiteralPath $expertPath).Hash -ne $expectedExpertHash) {
    $alerts.Add('next_v7_ex5_hash_mismatch')
}
if ($processes.Count -eq 1 -and [string]::IsNullOrWhiteSpace($detectedMode)) {
    $alerts.Add('runtime_mode_unrecognized')
} elseif ($ExpectedMode -ne 'Auto' -and $processes.Count -eq 1 -and $detectedMode -ne $ExpectedMode) {
    $alerts.Add("runtime_mode=$detectedMode,expected=$ExpectedMode")
}
if ($activeMode -eq 'Live' -and -not $livePromotionAuthorized) {
    $alerts.Add('next_v7_live_authorization_missing')
}

$terminalAllowLiveTrading = $null
if (-not (Test-Path -LiteralPath $modeContract.ConfigPath -PathType Leaf)) {
    $alerts.Add("runtime_config_missing=$activeMode")
} else {
    $runtimeConfigText = Get-Content -LiteralPath $modeContract.ConfigPath -Raw
    if ($runtimeConfigText -match '(?m)^AllowLiveTrading=([01])\s*$') {
        $terminalAllowLiveTrading = [int]$Matches[1]
    }
    if ($terminalAllowLiveTrading -ne [int]$modeContract.AllowLiveTrading) {
        $alerts.Add("terminal_allow_live_trading=$terminalAllowLiveTrading,expected=$($modeContract.AllowLiveTrading)")
    }
}
if (-not (Test-Path -LiteralPath $modeContract.SetPath -PathType Leaf)) {
    $alerts.Add("runtime_set_missing=$activeMode")
} else {
    $runtimeSetText = Get-Content -LiteralPath $modeContract.SetPath -Raw
    $expectedEntriesText = if ([int]$modeContract.ExpectedEntries -eq 1) { 'true' } else { 'false' }
    if ($runtimeSetText -notmatch "(?m)^InpAllowNewEntries=$expectedEntriesText\|\|") {
        $alerts.Add("runtime_set_entries_mismatch=$activeMode")
    }
}
if ($null -eq $latest) {
    $alerts.Add('next_v7_current_snapshot_unavailable')
}

$snapshotAgeSeconds = $null
$snapshot = $null
$retry = $null
$shadow = $null
$seal = $null
$components = @()
if ($null -ne $latest) {
    $snapshot = $latest.Snapshot
    $retry = $latest.Retry
    $shadow = $latest.Shadow
    $seal = $latest.Seal
    $components = @($latest.Components)

    if ([string]$snapshot.schema_version -ne $expectedSchemaVersion -or
        [string]$snapshot.release_id -ne $expectedReleaseId -or
        [string]$snapshot.project_id -ne $expectedProjectId -or
        [string]$snapshot.execution_version -ne $expectedExecutionVersion -or
        [string]$snapshot.economic_version -ne $expectedEconomicVersion -or
        [string]$snapshot.portfolio_id -ne $expectedPortfolioId) {
        $alerts.Add("snapshot_identity=$($snapshot.schema_version)/$($snapshot.release_id)/$($snapshot.project_id)/$($snapshot.execution_version)/$($snapshot.economic_version)/$($snapshot.portfolio_id)")
    }
    if ($components.Count -ne $expectedComponents.Count) {
        $alerts.Add("component_count=$($components.Count),expected=$($expectedComponents.Count)")
    } else {
        $seenIds = [System.Collections.Generic.HashSet[string]]::new()
        $seenMagics = [System.Collections.Generic.HashSet[long]]::new()
        foreach ($component in $components) {
            $id = [string]$component.component_id
            $magic = [long]$component.magic
            if (-not $seenIds.Add($id) -or -not $seenMagics.Add($magic)) {
                $alerts.Add("duplicate_component_identity=$id/$magic")
            } elseif (-not $expectedComponents.Contains($id) -or [long]$expectedComponents[$id] -ne $magic) {
                $alerts.Add("component_identity=$id/$magic")
            }
        }
    }

    try {
        $snapshotUtc = [datetime]::ParseExact(
            [string]$snapshot.utc,
            'yyyy.MM.dd HH:mm:ss',
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::AssumeUniversal -bor [Globalization.DateTimeStyles]::AdjustToUniversal
        )
        $snapshotAgeSeconds = [math]::Max(0, [int]((Get-Date).ToUniversalTime() - $snapshotUtc).TotalSeconds)
        if ($snapshotAgeSeconds -gt 180) {
            $alerts.Add("stale_snapshot_seconds=$snapshotAgeSeconds")
        }
    } catch {
        $alerts.Add('snapshot_time_invalid')
    }

    foreach ($name in @('safety_stopped', 'persistence_failed', 'broker_mismatch', 'foreign_exposure')) {
        if ([int]$snapshot.$name -ne 0) { $alerts.Add("$name=$($snapshot.$name)") }
    }
    if ([int]$snapshot.terminal_connected -ne 1) { $alerts.Add("terminal_connected=$($snapshot.terminal_connected)") }
    if ([int]$snapshot.account_binding_configured -ne 1) { $alerts.Add("account_binding_configured=$($snapshot.account_binding_configured)") }
    if ([int]$snapshot.account_identity_match -ne 1) { $alerts.Add("account_identity_match=$($snapshot.account_identity_match)") }
    $expectedEntries = [int]$modeContract.ExpectedEntries
    if ([int]$snapshot.new_entries_input -ne $expectedEntries -or
        [int]$snapshot.new_entries_effective -ne $expectedEntries) {
        $alerts.Add("entries=$($snapshot.new_entries_input)/$($snapshot.new_entries_effective),expected=$expectedEntries/$expectedEntries")
    }

    foreach ($field in @('catchup_failures', 'checkpoint_save_failures', 'checkpoint_readback_failures',
            'checkpoint_event_failures', 'checkpoint_duplicate_bucket_failures', 'checkpoint_cursor_regressions')) {
        if ([long]$shadow.$field -ne 0) { $alerts.Add("rc4_shadow_$field=$($shadow.$field)") }
    }
    foreach ($field in @('save_failures', 'readback_failures', 'failures', 'ambiguities', 'pre_boundary_consumed')) {
        if ([long]$seal.$field -ne 0) { $alerts.Add("rc4_activation_seal_$field=$($seal.$field)") }
    }
    if ([int]$snapshot.arc_modify_pending -ne 0) { $warnings.Add('rc4_protection_modify_pending') }
    if ([int]$retry.pending -ne 0) { $warnings.Add('rc4_single_retry_pending') }
    if ([int]$shadow.catchup_required -ne 0) { $warnings.Add('rc4_shadow_catchup_active') }
    if ([int]$shadow.checkpoint_pending -ne 0) { $warnings.Add('rc4_cursor_checkpoint_pending') }
    if ([long]$seal.pending -gt 0) { $warnings.Add('rc4_activation_seal_pending') }
}

$status = [ordered]@{
    healthy = ($alerts.Count -eq 0)
    operator_mode = [string]$modeContract.OperatorMode
    detected_runtime_mode = $detectedMode
    live_promotion_authorized = [bool]$livePromotionAuthorized
    terminal_allow_live_trading = $terminalAllowLiveTrading
    expected_new_entries = [int]$modeContract.ExpectedEntries
    observed_at_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    project_terminal_process_count = $processes.Count
    project_terminal_pid = if ($processes.Count -eq 1) { $processes[0].Id } else { $null }
    legacy_terminal_pids = @($legacyProcesses | ForEach-Object { $_.Id })
    other_next_terminal_pids = @($otherNextProcesses | ForEach-Object { $_.Id })
    state_directory = $liveDirectory
    accepted_ex5_hash = if (Test-Path -LiteralPath $expertPath -PathType Leaf) {
        (Get-FileHash -Algorithm SHA256 -LiteralPath $expertPath).Hash
    } else { $null }
    snapshot_file = if ($null -ne $latest) { $latest.File } else { $null }
    snapshot_age_seconds = $snapshotAgeSeconds
    schema_version = if ($null -ne $snapshot) { [string]$snapshot.schema_version } else { $null }
    release_id = if ($null -ne $snapshot) { [string]$snapshot.release_id } else { $null }
    project_id = if ($null -ne $snapshot) { [string]$snapshot.project_id } else { $null }
    execution_version = if ($null -ne $snapshot) { [string]$snapshot.execution_version } else { $null }
    economic_version = if ($null -ne $snapshot) { [string]$snapshot.economic_version } else { $null }
    portfolio_id = if ($null -ne $snapshot) { [string]$snapshot.portfolio_id } else { $null }
    state_sequence = if ($null -ne $snapshot) { [long]$snapshot.state_sequence } else { $null }
    server_time = if ($null -ne $snapshot) { [string]$snapshot.server_time } else { $null }
    new_entries_input = if ($null -ne $snapshot) { [int]$snapshot.new_entries_input } else { $null }
    new_entries_effective = if ($null -ne $snapshot) { [int]$snapshot.new_entries_effective } else { $null }
    terminal_connected = if ($null -ne $snapshot) { [int]$snapshot.terminal_connected } else { $null }
    account_binding_configured = if ($null -ne $snapshot) { [int]$snapshot.account_binding_configured } else { $null }
    account_identity_match = if ($null -ne $snapshot) { [int]$snapshot.account_identity_match } else { $null }
    safety_stopped = if ($null -ne $snapshot) { [int]$snapshot.safety_stopped } else { $null }
    persistence_failed = if ($null -ne $snapshot) { [int]$snapshot.persistence_failed } else { $null }
    broker_mismatch = if ($null -ne $snapshot) { [int]$snapshot.broker_mismatch } else { $null }
    foreign_exposure = if ($null -ne $snapshot) { [int]$snapshot.foreign_exposure } else { $null }
    account_balance = if ($null -ne $snapshot) { [double]$snapshot.account_balance } else { $null }
    account_equity = if ($null -ne $snapshot) { [double]$snapshot.account_equity } else { $null }
    account_margin = if ($null -ne $snapshot) { [double]$snapshot.account_margin } else { $null }
    project_realized_net = if ($null -ne $snapshot) { [double]$snapshot.project_realized_net } else { $null }
    project_stage_balance = if ($null -ne $snapshot) { [double]$snapshot.project_stage_balance } else { $null }
    stressed_balance = if ($null -ne $snapshot) { [double]$snapshot.stressed_balance } else { $null }
    aggregate_planned_risk = if ($null -ne $snapshot) { [double]$snapshot.aggregate_planned_risk } else { $null }
    maximum_aggregate_planned_risk = if ($null -ne $snapshot) { [double]$snapshot.maximum_aggregate_planned_risk } else { $null }
    passive_pending_order = if ($null -ne $snapshot) { [long]$snapshot.passive_pending_order } else { $null }
    arc = if ($null -ne $snapshot) {
        [ordered]@{
            lifecycle_identifier = [long]$snapshot.arc_lifecycle_identifier
            modify_pending = [int]$snapshot.arc_modify_pending
            pending_stop = [double]$snapshot.arc_pending_stop
            lifecycle_compressed = [int]$snapshot.arc_lifecycle_compressed
            original_stop = [double]$snapshot.arc_original_stop
        }
    } else { $null }
    retry = if ($null -ne $retry) {
        [ordered]@{
            pending = [int]$retry.pending
            consumed = [int]$retry.consumed
            after_msc = [long]$retry.after_msc
            initial_retcode = [long]$retry.initial_retcode
            intents = [long]$retry.intents
            attempts = [long]$retry.attempts
            successes = [long]$retry.successes
            adoptions = [long]$retry.adoptions
            holds = [long]$retry.holds
        }
    } else { $null }
    shadow = if ($null -ne $snapshot -and $null -ne $shadow) {
        [ordered]@{
            occupied = [int]$snapshot.rc4_shadow_occupied
            source_identifier = [long]$snapshot.rc4_shadow_source_identifier
            entry_time = [long]$snapshot.rc4_shadow_entry_time
            direction = [int]$snapshot.rc4_shadow_direction
            original_stop = [double]$snapshot.rc4_shadow_original_stop
            last_observed_msc = [long]$shadow.last_observed_msc
            cursor_ordinal = [long]$shadow.cursor_ordinal
            catchup_required = [int]$shadow.catchup_required
            catchup_scans = [long]$shadow.catchup_scans
            catchup_ticks = [long]$shadow.catchup_ticks
            catchup_stop_releases = [long]$shadow.catchup_stop_releases
            catchup_failures = [long]$shadow.catchup_failures
            checkpoint_eligible = [long]$shadow.checkpoint_eligible
            checkpoint_persisted = [long]$shadow.checkpoint_persisted
            checkpoint_pending = [int]$shadow.checkpoint_pending
        }
    } else { $null }
    activation_seal = if ($null -ne $seal) {
        [ordered]@{
            eligible = [long]$seal.eligible
            sealed = [long]$seal.sealed
            pending = [long]$seal.pending
            failures = [long]$seal.failures
            ambiguities = [long]$seal.ambiguities
            pre_boundary_consumed = [long]$seal.pre_boundary_consumed
            sealed_msc = [long]$seal.sealed_msc
            sealed_ordinal = [long]$seal.sealed_ordinal
        }
    } else { $null }
    components = $components
    latest_events = $latestEvents
    warnings = @($warnings)
    alerts = @($alerts)
}

if ($AsJson) {
    $status | ConvertTo-Json -Depth 8 -Compress
} else {
    [pscustomobject]$status
}
