[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string]$WorkerPowerShellPath,

    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string]$OpenPath,

    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string]$ProjectRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$workerPowerShell = [System.IO.Path]::GetFullPath($WorkerPowerShellPath)
$openScript = [System.IO.Path]::GetFullPath($OpenPath)
$project = [System.IO.Path]::GetFullPath($ProjectRoot)
$terminalPath = Join-Path $project 'live-dev\runtime\portable\terminal64.exe'
$dashboardPath = Join-Path $project 'live-dev\tools\Show-ZetaNextV7Dashboard.ps1'
$logPath = Join-Path $project 'live-dev\logs\master-detached-host.log'

function Write-DetachedHostLog {
    param([Parameter(Mandatory)][string]$Message)

    $line = '{0:o} PID={1} {2}{3}' -f (Get-Date), $PID, $Message, [Environment]::NewLine
    [System.IO.File]::AppendAllText($logPath, $line, [System.Text.UTF8Encoding]::new($false))
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
    @(Get-CimInstance -ClassName Win32_Process -Filter "Name='pwsh.exe'" -ErrorAction SilentlyContinue | Where-Object {
        -not [string]::IsNullOrWhiteSpace([string]$_.CommandLine) -and
        ([string]$_.CommandLine).IndexOf($dashboardPath, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    } | Select-Object -ExpandProperty ProcessId)
}

try {
    foreach ($path in @($workerPowerShell, $openScript, $terminalPath, $dashboardPath)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Required detached-host file is missing: $path"
        }
    }
    $logDirectory = Split-Path -Parent $logPath
    if (-not (Test-Path -LiteralPath $logDirectory -PathType Container)) {
        [void][System.IO.Directory]::CreateDirectory($logDirectory)
    }

    $beforeTerminalIds = @(Get-ExactProcessIds -Name 'terminal64.exe' -ExecutablePath $terminalPath)
    $beforeDashboardIds = @(Get-DashboardProcessIds)
    Write-DetachedHostLog "START terminal_before=$($beforeTerminalIds -join ',') dashboard_before=$($beforeDashboardIds -join ',')"

    $workerOutput = @(& $workerPowerShell `
        -NoLogo `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File $openScript 2>&1)
    $workerExitCode = $LASTEXITCODE
    foreach ($record in $workerOutput) {
        Write-DetachedHostLog ([string]$record)
    }
    if ($workerExitCode -ne 0) {
        throw "Master worker exited with code $workerExitCode."
    }

    $afterTerminalIds = @(Get-ExactProcessIds -Name 'terminal64.exe' -ExecutablePath $terminalPath)
    $afterDashboardIds = @(Get-DashboardProcessIds)
    if ($afterTerminalIds.Count -ne 1 -or $afterDashboardIds.Count -ne 1) {
        throw "Master worker returned without exactly one terminal and one dashboard (terminal=$($afterTerminalIds.Count), dashboard=$($afterDashboardIds.Count))."
    }

    $ownedIds = @(
        @($afterTerminalIds | Where-Object { $_ -notin $beforeTerminalIds })
        @($afterDashboardIds | Where-Object { $_ -notin $beforeDashboardIds })
    ) | Select-Object -Unique
    Write-DetachedHostLog "READY terminal=$($afterTerminalIds[0]) dashboard=$($afterDashboardIds[0]) anchored=$($ownedIds -join ',')"

    while (@($ownedIds | Where-Object { $null -ne (Get-Process -Id $_ -ErrorAction SilentlyContinue) }).Count -gt 0) {
        Start-Sleep -Seconds 5
    }
    Write-DetachedHostLog 'EXIT anchored processes are no longer active.'
    exit 0
} catch {
    try { Write-DetachedHostLog ("ERROR " + $_.Exception.Message) } catch { }
    exit 1
}
