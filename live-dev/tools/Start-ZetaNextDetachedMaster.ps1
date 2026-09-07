[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string]$WorkerPowerShellPath,

    [string]$ResultPath,

    [ValidateSet('Auto', 'EntriesDisabled', 'Live')]
    [string]$RequiredMode = 'Auto'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Quote-WindowsArgument {
    param([Parameter(Mandatory)][string]$Value)

    if ($Value -notmatch '[\s"]') {
        return $Value
    }
    return '"' + $Value.Replace('"', '\"') + '"'
}

function Get-ExactProcessIds {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$ExecutablePath
    )

    $expected = [System.IO.Path]::GetFullPath($ExecutablePath)
    @(Get-CimInstance -ClassName Win32_Process -Filter "Name='$Name'" -ErrorAction SilentlyContinue | Where-Object {
        -not [string]::IsNullOrWhiteSpace([string]$_.ExecutablePath) -and
        [System.IO.Path]::GetFullPath([string]$_.ExecutablePath).Equals(
            $expected,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    } | Select-Object -ExpandProperty ProcessId)
}

function Get-DashboardProcessIds {
    param([Parameter(Mandatory)][string]$DashboardPath)

    @(Get-CimInstance -ClassName Win32_Process -Filter "Name='pwsh.exe'" -ErrorAction SilentlyContinue | Where-Object {
        -not [string]::IsNullOrWhiteSpace([string]$_.CommandLine) -and
        ([string]$_.CommandLine).IndexOf($DashboardPath, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    } | Select-Object -ExpandProperty ProcessId)
}

$projectRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
$workerPowerShell = [System.IO.Path]::GetFullPath($WorkerPowerShellPath)
$oncePath = Join-Path $PSScriptRoot 'Invoke-ZetaNextDetachedMasterOnce.ps1'
$openPath = Join-Path $PSScriptRoot 'Open-ZetaNextMasterTerminalAndDashboard.ps1'
$dashboardPath = Join-Path $PSScriptRoot 'Show-ZetaNextV7RDashboard.ps1'
$terminalPath = Join-Path $projectRoot 'live-dev\runtime\portable\terminal64.exe'
$logPath = Join-Path $projectRoot 'live-dev\logs\master-detached-once.log'

if (-not [string]::IsNullOrWhiteSpace($ResultPath)) {
    $ResultPath = [System.IO.Path]::GetFullPath($ResultPath)
    $allowedDirectory = [System.IO.Path]::GetFullPath((Split-Path -Parent $logPath))
    if (-not (Split-Path -Parent $ResultPath).Equals($allowedDirectory, [StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetFileName($ResultPath) -notmatch '^user-activation-[0-9a-f]{32}\.json$' -or
        (Test-Path -LiteralPath $ResultPath)) {
        throw 'A detached result must use a new user-activation GUID file in the private Live logs directory.'
    }
}

function Write-DetachedResult {
    param([string]$Outcome, [bool]$WorkerFinished, [bool]$MatchedMarker)

    if ([string]::IsNullOrWhiteSpace($ResultPath)) { return }
    $record = [ordered]@{
        schema = 'zeta-detached-master-result-v1'
        launch_id = $launchId
        worker_pid = $workerProcessId
        worker_finished = $WorkerFinished
        matched_completion_marker = $MatchedMarker
        outcome = $Outcome
        required_mode = $RequiredMode
        observed_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    }
    [void][IO.Directory]::CreateDirectory((Split-Path -Parent $ResultPath))
    [IO.File]::WriteAllText($ResultPath, ($record | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
}

foreach ($path in @($workerPowerShell, $oncePath, $openPath, $dashboardPath, $terminalPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required detached-launch file is missing: $path"
    }
}

$launchId = [Guid]::NewGuid().ToString('N')
$commandLine = @(
    (Quote-WindowsArgument $workerPowerShell),
    '-NoLogo',
    '-NoProfile',
    '-WindowStyle',
    'Hidden',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    (Quote-WindowsArgument $oncePath),
    '-OpenPath',
    (Quote-WindowsArgument $openPath),
    '-ProjectRoot',
    (Quote-WindowsArgument $projectRoot),
    '-LaunchId',
    $launchId,
    '-RequiredMode',
    $RequiredMode
) -join ' '

$created = Invoke-CimMethod `
    -ClassName Win32_Process `
    -MethodName Create `
    -Arguments @{ CommandLine = $commandLine; CurrentDirectory = $projectRoot }
if ([uint32]$created.ReturnValue -ne 0 -or [uint32]$created.ProcessId -eq 0) {
    throw "The Windows one-shot process broker failed with result $($created.ReturnValue)."
}

$workerProcessId = [uint32]$created.ProcessId
$deadline = (Get-Date).AddSeconds(150)
do {
    $worker = Get-CimInstance -ClassName Win32_Process -Filter "ProcessId=$workerProcessId" -ErrorAction SilentlyContinue
    if ($null -eq $worker) {
        $detail = ''
        if (Test-Path -LiteralPath $logPath -PathType Leaf) {
            $detail = [System.IO.File]::ReadAllText($logPath)
        }
        $terminalIds = @(Get-ExactProcessIds -Name 'terminal64.exe' -ExecutablePath $terminalPath)
        $dashboardIds = @(Get-DashboardProcessIds -DashboardPath $dashboardPath)
        $successMarker = "LAUNCH=$launchId RESULT=OK"
        if ($detail.IndexOf($successMarker, [System.StringComparison]::Ordinal) -ge 0 -and
            $terminalIds.Count -eq 1 -and $dashboardIds.Count -eq 1) {
            Write-DetachedResult -Outcome SUCCESS -WorkerFinished $true -MatchedMarker $true
            Write-Output "Detached Master is active: terminal PID $($terminalIds[0]), dashboard PID $($dashboardIds[0])."
            exit 0
        }
        $failedMarker = $detail.IndexOf("LAUNCH=$launchId RESULT=ERROR", [StringComparison]::Ordinal) -ge 0
        $outcome = if ($failedMarker) { 'FAILED' } else { 'UNKNOWN' }
        Write-DetachedResult -Outcome $outcome -WorkerFinished $true -MatchedMarker $failedMarker
        throw "Detached Master launch failed.`r`n$detail"
    }
    Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $deadline)

Write-DetachedResult -Outcome UNKNOWN -WorkerFinished $false -MatchedMarker $false
throw "Detached Master one-shot worker PID $workerProcessId did not finish within 150 seconds; it was left untouched."
