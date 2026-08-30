[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$powerShellPath = Join-Path $PSHOME 'pwsh.exe'
if (-not (Test-Path -LiteralPath $powerShellPath -PathType Leaf)) {
    throw "The current PowerShell 7 engine cannot be reused: $powerShellPath"
}

$commonModule = Join-Path $PSScriptRoot 'ZetaNextOperatorCommon.psm1'
$liveStartPath = Join-Path $PSScriptRoot 'Start-ZetaNextV8Live.ps1'
$dashboardPath = Join-Path $PSScriptRoot 'Show-ZetaNextV8Dashboard.ps1'
foreach ($path in @($commonModule, $liveStartPath, $dashboardPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required Next V8 operator file is missing: $path"
    }
}
Import-Module $commonModule -Force
$contract = Get-ZetaNextOperatorContract
$authorization = Get-Content -LiteralPath $contract.StatePath -Raw
if ($authorization -notmatch 'Next Live-Dev authorization:\s+`ENABLED`' -or
    $authorization -notmatch 'Next V8 paired-month new-entry authorization:\s+`ENABLED`') {
    throw 'CURRENT_STATE.md does not authorize Next V8 Live new entries.'
}

$null = Assert-ZetaNextReleaseIntegrity -Contract $contract
$inventory = Assert-ZetaNextExclusiveTerminalBoundary -Contract $contract -AllowExactLive
$terminal = @($inventory.ExactLive) | Select-Object -First 1
if ($null -eq $terminal) {
    Write-Output 'Next V8 0/0 preflight 후 1/1 Live를 시작합니다...'
    & $liveStartPath -EnableNewEntries -ConfirmLiveDev
    $inventory = Assert-ZetaNextExclusiveTerminalBoundary -Contract $contract -AllowExactLive
    $terminal = @($inventory.ExactLive) | Select-Object -First 1
    if ($null -eq $terminal) {
        throw 'Next V8 starter returned without an exact Live-Dev terminal process.'
    }
} else {
    $liveConfigPath = Join-Path $contract.RuntimeRoot 'Config\terminal-next-v8-live.ini'
    $processInfo = Get-CimInstance -ClassName Win32_Process -Filter "ProcessId=$($terminal.Id)" -ErrorAction Stop
    if ([string]::IsNullOrWhiteSpace([string]$processInfo.CommandLine) -or
        ([string]$processInfo.CommandLine).IndexOf($liveConfigPath, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw "Next PID $($terminal.Id) is not the exact V8 Live runtime; it was left untouched."
    }
    $status = Get-ZetaNextRuntimeStatus -Contract $contract -Mode Live
    if (-not [bool]$status.healthy -or -not (Test-ZetaNextLiveStatus -Status $status) -or
        [int]$status.project_terminal_pid -ne $terminal.Id) {
        throw 'The existing Next V8 terminal failed its identity/Magic/account/1/1 snapshot handshake; it was left running to manage any owned risk.'
    }
    Write-Output "기존 Next V8 Live-Dev 터미널 PID $($terminal.Id)을 확인했습니다. 중복 실행하지 않습니다."
}

if (-not ('ZetaNextWindowTools' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public static class ZetaNextWindowTools
{
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowTextLength(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool ShowWindowAsync(IntPtr hWnd, int command);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    public static IntPtr[] GetTitledWindows(int processId)
    {
        var windows = new List<IntPtr>();
        EnumWindows(delegate (IntPtr hWnd, IntPtr lParam)
        {
            uint ownerProcessId;
            GetWindowThreadProcessId(hWnd, out ownerProcessId);
            if (ownerProcessId == (uint)processId && GetWindowTextLength(hWnd) > 0)
                windows.Add(hWnd);
            return true;
        }, IntPtr.Zero);
        return windows.ToArray();
    }
}
'@
}

$terminalWindows = @()
$windowDeadline = (Get-Date).AddSeconds(20)
do {
    $terminalWindows = @([ZetaNextWindowTools]::GetTitledWindows($terminal.Id))
    if ($terminalWindows.Count -eq 0) { Start-Sleep -Milliseconds 250 }
} while ($terminalWindows.Count -eq 0 -and (Get-Date) -lt $windowDeadline)
if ($terminalWindows.Count -gt 0) {
    foreach ($window in $terminalWindows) { $null = [ZetaNextWindowTools]::ShowWindowAsync($window, 9) }
    $null = [ZetaNextWindowTools]::SetForegroundWindow($terminalWindows[0])
    Write-Output "Next V8 EA가 부착된 MT5 창을 복원했습니다 (PID $($terminal.Id))."
} else {
    Write-Warning "Next V8 MT5 PID $($terminal.Id)은 실행 중이나 창을 찾지 못했습니다."
}

$dashboardWindowTitle = 'Project Zeta Terminus Next V8 Live-Dev 대시보드'
$existingDashboard = @(Get-Process -Name pwsh -ErrorAction SilentlyContinue | Where-Object {
    $_.MainWindowTitle -eq $dashboardWindowTitle
} | Select-Object -First 1)
if ($existingDashboard.Count -eq 1 -and $existingDashboard[0].MainWindowHandle -ne 0) {
    $null = [ZetaNextWindowTools]::ShowWindowAsync($existingDashboard[0].MainWindowHandle, 9)
    $null = [ZetaNextWindowTools]::SetForegroundWindow($existingDashboard[0].MainWindowHandle)
    Write-Output '기존 Next V8 대시보드를 복원했습니다.'
} else {
    $null = Start-Process `
        -FilePath $powerShellPath `
        -ArgumentList @(
            '-NoLogo', '-NoProfile', '-STA', '-ExecutionPolicy', 'Bypass',
            '-File', "`"$dashboardPath`"", '-RefreshSeconds', '5', '-ExpectedMode', 'Live'
        ) `
        -WorkingDirectory $contract.ProjectRoot `
        -WindowStyle Normal `
        -PassThru
    Write-Output 'Next V8 한국어 대시보드를 열었습니다. 로컬 스냅숏을 5초마다 갱신합니다.'
}
