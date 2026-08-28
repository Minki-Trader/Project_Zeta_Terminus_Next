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
$systemPowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$hostPath = Join-Path $PSScriptRoot 'Invoke-ZetaNextDetachedMasterHost.ps1'
$openPath = Join-Path $PSScriptRoot 'Open-ZetaNextMasterTerminalAndDashboard.ps1'
$dashboardPath = Join-Path $PSScriptRoot 'Show-ZetaNextV7Dashboard.ps1'
$terminalPath = Join-Path $projectRoot 'live-dev\runtime\portable\terminal64.exe'
$logPath = Join-Path $projectRoot 'live-dev\logs\master-detached-host.log'

foreach ($path in @($workerPowerShell, $systemPowerShell, $hostPath, $openPath, $dashboardPath, $terminalPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required detached-launch file is missing: $path"
    }
}

$taskName = 'Project Zeta Terminus Next Master Runtime'
$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$actionArguments = @(
    '-NoLogo',
    '-NoProfile',
    '-NonInteractive',
    '-WindowStyle',
    'Hidden',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    (Quote-WindowsArgument $hostPath),
    '-WorkerPowerShellPath',
    (Quote-WindowsArgument $workerPowerShell),
    '-OpenPath',
    (Quote-WindowsArgument $openPath),
    '-ProjectRoot',
    (Quote-WindowsArgument $projectRoot)
) -join ' '

$action = New-ScheduledTaskAction `
    -Execute $systemPowerShell `
    -Argument $actionArguments `
    -WorkingDirectory $projectRoot
$principal = New-ScheduledTaskPrincipal `
    -UserId $userId `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances Parallel `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable
$definition = New-ScheduledTask `
    -Action $action `
    -Principal $principal `
    -Settings $settings `
    -Description 'Starts the Zeta Next Master runtime outside the Codex process lifetime.'

$registered = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
$registrationMatches = $false
if ($null -ne $registered) {
    $registeredAction = @($registered.Actions) | Select-Object -First 1
    if ($null -ne $registeredAction) {
        $registrationMatches =
            ([string]$registeredAction.Execute).Equals($systemPowerShell, [System.StringComparison]::OrdinalIgnoreCase) -and
            ([string]$registeredAction.Arguments).Equals($actionArguments, [System.StringComparison]::Ordinal) -and
            ([string]$registeredAction.WorkingDirectory).Equals($projectRoot, [System.StringComparison]::OrdinalIgnoreCase)
    }
}
if (-not $registrationMatches) {
    Register-ScheduledTask -TaskName $taskName -InputObject $definition -Force | Out-Null
}

$dispatchTime = Get-Date
Start-ScheduledTask -TaskName $taskName

$deadline = $dispatchTime.AddSeconds(90)
do {
    $terminalIds = @(Get-ExactProcessIds -Name 'terminal64.exe' -ExecutablePath $terminalPath)
    $dashboardIds = @(Get-DashboardProcessIds -DashboardPath $dashboardPath)
    if ($terminalIds.Count -eq 1 -and $dashboardIds.Count -eq 1) {
        Write-Output "Detached Master is active: terminal PID $($terminalIds[0]), dashboard PID $($dashboardIds[0])."
        exit 0
    }

    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
    $taskInfo = Get-ScheduledTaskInfo -TaskName $taskName -ErrorAction Stop
    if ($task.State -ne 'Running' -and
        $taskInfo.LastRunTime -ge $dispatchTime.AddSeconds(-2) -and
        $taskInfo.LastTaskResult -ne 0) {
        $detail = ''
        if (Test-Path -LiteralPath $logPath -PathType Leaf) {
            $detail = [System.IO.File]::ReadAllText($logPath)
        }
        throw "Detached Master task failed with result $($taskInfo.LastTaskResult).`r`n$detail"
    }
    Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $deadline)

throw 'Detached Master did not expose exactly one terminal and one dashboard within 90 seconds.'
