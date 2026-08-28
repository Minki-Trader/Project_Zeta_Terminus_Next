[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string]$WorkerPowerShellPath
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
$dashboardPath = Join-Path $PSScriptRoot 'Show-ZetaNextV7Dashboard.ps1'
$terminalPath = Join-Path $projectRoot 'live-dev\runtime\portable\terminal64.exe'
$logPath = Join-Path $projectRoot 'live-dev\logs\master-detached-once.log'

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
    $launchId
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
        if ($detail -match "(?m)^LAUNCH=$launchId RESULT=OK$" -and
            $terminalIds.Count -eq 1 -and $dashboardIds.Count -eq 1) {
            Write-Output "Detached Master is active: terminal PID $($terminalIds[0]), dashboard PID $($dashboardIds[0])."
            exit 0
        }
        throw "Detached Master launch failed.`r`n$detail"
    }
    Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $deadline)

throw "Detached Master one-shot worker PID $workerProcessId did not finish within 150 seconds; it was left untouched."
