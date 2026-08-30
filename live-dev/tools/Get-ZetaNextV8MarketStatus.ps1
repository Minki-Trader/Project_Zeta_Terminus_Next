[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateRange(1, 2147483647)]
    [int]$ExpectedProcessId,

    [ValidateRange(2, 30)]
    [int]$ObservationSeconds = 12,

    [switch]$AsJson
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$liveDevRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$runtimeRoot = Join-Path $liveDevRoot 'runtime\portable'
$terminalPath = Join-Path $runtimeRoot 'terminal64.exe'
$statusScript = Join-Path $PSScriptRoot 'Get-ZetaNextV8Status.ps1'
$pythonCommand = Get-Command python -ErrorAction Stop | Select-Object -First 1

foreach ($path in @($terminalPath, $statusScript)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required Next V8 market-status file is missing: $path"
    }
}

$exactProcesses = @(Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object {
    try {
        $_.Path -and [System.IO.Path]::GetFullPath($_.Path) -eq
            [System.IO.Path]::GetFullPath($terminalPath)
    } catch { $false }
})
if ($exactProcesses.Count -ne 1 -or [int]$exactProcesses[0].Id -ne $ExpectedProcessId) {
    throw "Expected exact Next V8 terminal PID $ExpectedProcessId; found $(@($exactProcesses.Id) -join ',')."
}

$preStatus = ((& $statusScript -AsJson -ExpectedMode Auto | Out-String) | ConvertFrom-Json)

$env:ZETA_NEXT_V8_TERMINAL_PATH = $terminalPath
$env:ZETA_NEXT_V8_OBSERVATION_SECONDS = [string]$ObservationSeconds
$python = @'
import json
import os
import time

import MetaTrader5 as mt5

terminal_path = os.environ["ZETA_NEXT_V8_TERMINAL_PATH"]
duration = int(os.environ["ZETA_NEXT_V8_OBSERVATION_SECONDS"])
symbols = ("US30", "US100", "US500")
timeframes = (
    ("M15", mt5.TIMEFRAME_M15, 15 * 60),
    ("M30", mt5.TIMEFRAME_M30, 30 * 60),
    ("H1", mt5.TIMEFRAME_H1, 60 * 60),
)
result = {
    "terminal_connected": False,
    "us30_tick_updates": 0,
    "us30_max_update_gap_seconds": float(duration),
    "us30_continuous_ticks": False,
    "all_symbol_ticks_fresh": False,
    "symbol_ticks": [],
    "timeframes": [],
    "market_data_ready": False,
    "reasons": [],
}

if not mt5.initialize(path=terminal_path, portable=True, timeout=60000):
    result["reasons"].append("MetaTrader5 IPC initialization failed: %r" % (mt5.last_error(),))
    print(json.dumps(result, separators=(",", ":")))
    raise SystemExit(0)

try:
    terminal = mt5.terminal_info()
    result["terminal_connected"] = bool(terminal and terminal.connected)
    if not result["terminal_connected"]:
        result["reasons"].append("terminal is not connected")

    for symbol in symbols:
        if not mt5.symbol_select(symbol, True):
            result["reasons"].append("symbol_select failed for " + symbol)

    started = time.monotonic()
    last_tick_msc = None
    observations = []
    while True:
        elapsed = time.monotonic() - started
        tick = mt5.symbol_info_tick("US30")
        if tick is not None and int(tick.time_msc) > 0 and int(tick.time_msc) != last_tick_msc:
            last_tick_msc = int(tick.time_msc)
            observations.append((elapsed, last_tick_msc))
        if elapsed >= duration:
            break
        time.sleep(0.2)

    result["us30_tick_updates"] = len(observations)
    if observations:
        elapsed_points = [0.0] + [item[0] for item in observations] + [float(duration)]
        gaps = [max(0.0, elapsed_points[index + 1] - elapsed_points[index])
                for index in range(len(elapsed_points) - 1)]
        result["us30_max_update_gap_seconds"] = max(gaps)
    result["us30_continuous_ticks"] = (
        len(observations) >= 3 and result["us30_max_update_gap_seconds"] <= 3.0
    )
    if not result["us30_continuous_ticks"]:
        result["reasons"].append("US30 did not produce at least three updates with every observed gap <= 3 seconds")

    wall_msc = int(time.time() * 1000)
    symbol_ticks_fresh = True
    reference_tick_epoch = 0
    for symbol in symbols:
        tick = mt5.symbol_info_tick(symbol)
        tick_msc = int(tick.time_msc) if tick is not None else 0
        age_seconds = (wall_msc - tick_msc) / 1000.0 if tick_msc > 0 else None
        fresh = age_seconds is not None and -1.0 <= age_seconds <= 5.0
        if symbol == "US30" and tick_msc > 0:
            reference_tick_epoch = tick_msc // 1000
        result["symbol_ticks"].append({
            "symbol": symbol,
            "time_msc": tick_msc,
            "age_seconds": age_seconds,
            "fresh": fresh,
        })
        symbol_ticks_fresh = symbol_ticks_fresh and fresh
    result["all_symbol_ticks_fresh"] = symbol_ticks_fresh
    if not symbol_ticks_fresh:
        result["reasons"].append("one or more US30/US100/US500 ticks are stale")

    all_timeframes_ready = reference_tick_epoch > 0
    for name, timeframe, seconds in timeframes:
        rows = []
        for symbol in symbols:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 2)
            if rates is None or len(rates) < 2:
                rows.append({"symbol": symbol, "bar_time": 0, "tick_volume": 0, "fresh": False})
                continue
            latest = rates[-1]
            bar_time = int(latest["time"])
            tick_volume = int(latest["tick_volume"])
            age = reference_tick_epoch - bar_time
            fresh = 0 <= age <= seconds + 120 and tick_volume > 0
            rows.append({
                "symbol": symbol,
                "bar_time": bar_time,
                "tick_volume": tick_volume,
                "age_seconds": age,
                "fresh": fresh,
            })
        bar_times = {row["bar_time"] for row in rows if row["bar_time"] > 0}
        synchronized = len(rows) == len(symbols) and len(bar_times) == 1
        ready = synchronized and all(bool(row["fresh"]) for row in rows)
        result["timeframes"].append({
            "timeframe": name,
            "synchronized": synchronized,
            "synchronized_and_fresh": ready,
            "symbols": rows,
        })
        all_timeframes_ready = all_timeframes_ready and ready
        if not ready:
            result["reasons"].append(name + " bars are not synchronized and fresh across US30/US100/US500")

    result["market_data_ready"] = (
        result["terminal_connected"]
        and result["us30_continuous_ticks"]
        and result["all_symbol_ticks_fresh"]
        and all_timeframes_ready
    )
finally:
    mt5.shutdown()

print(json.dumps(result, separators=(",", ":")))
'@

try {
    $pythonOutput = @($python | & $pythonCommand.Source - 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "MetaTrader5 market-status process exited with code ${LASTEXITCODE}: $($pythonOutput -join [Environment]::NewLine)"
    }
    $market = (($pythonOutput -join [Environment]::NewLine) | ConvertFrom-Json)
} finally {
    Remove-Item Env:ZETA_NEXT_V8_TERMINAL_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:ZETA_NEXT_V8_OBSERVATION_SECONDS -ErrorAction SilentlyContinue
}

$postProcesses = @(Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object {
    try {
        $_.Path -and [System.IO.Path]::GetFullPath($_.Path) -eq
            [System.IO.Path]::GetFullPath($terminalPath)
    } catch { $false }
})
$sameSoleProcess = ($postProcesses.Count -eq 1 -and [int]$postProcesses[0].Id -eq $ExpectedProcessId)
$status = ((& $statusScript -AsJson -ExpectedMode Auto | Out-String) | ConvertFrom-Json)
$serverTime = $null
$safeHandoffWindow = $false
if (-not [string]::IsNullOrWhiteSpace([string]$status.server_time)) {
    $serverTime = [datetime]::ParseExact(
        [string]$status.server_time,
        'yyyy.MM.dd HH:mm:ss',
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::None
    )
    $serverMinute = $serverTime.Hour * 60 + $serverTime.Minute
    $protectedRanges = @(
        @(12 * 60 + 58, 13 * 60 + 3),
        @(13 * 60 + 28, 13 * 60 + 33),
        @(14 * 60 + 58, 15 * 60 + 3),
        @(15 * 60 + 58, 16 * 60 + 3),
        @(16 * 60 + 58, 17 * 60 + 3)
    )
    $insideProtectedRange = $false
    foreach ($range in $protectedRanges) {
        if ($serverMinute -ge $range[0] -and $serverMinute -le $range[1]) {
            $insideProtectedRange = $true
            break
        }
    }
    $safeHandoffWindow = -not $insideProtectedRange
}
$reasons = [System.Collections.Generic.List[string]]::new()
foreach ($reason in @($market.reasons)) { $reasons.Add([string]$reason) }
if (-not $sameSoleProcess) { $reasons.Add('exact terminal process changed during market observation') }
if (-not $safeHandoffWindow) { $reasons.Add('server time is inside or too close to a protected evaluation window') }
if (-not [bool]$status.healthy) { $reasons.Add('local Next V8 runtime status is not healthy') }

$result = [ordered]@{
    observed_at_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    terminal_pid = $ExpectedProcessId
    same_sole_process = $sameSoleProcess
    pre_observation_state_sequence = [long]$preStatus.state_sequence
    post_observation_state_sequence = [long]$status.state_sequence
    local_runtime_healthy = [bool]$status.healthy
    server_time = if ($null -ne $serverTime) { $serverTime.ToString('yyyy.MM.dd HH:mm:ss') } else { $null }
    safe_handoff_window = $safeHandoffWindow
    terminal_connected = [bool]$market.terminal_connected
    observation_seconds = $ObservationSeconds
    us30_tick_updates = [long]$market.us30_tick_updates
    us30_max_update_gap_seconds = [double]$market.us30_max_update_gap_seconds
    us30_continuous_ticks = [bool]$market.us30_continuous_ticks
    all_symbol_ticks_fresh = [bool]$market.all_symbol_ticks_fresh
    symbol_ticks = @($market.symbol_ticks)
    timeframes = @($market.timeframes)
    market_data_ready = [bool]$market.market_data_ready
    ready_for_handoff = (
        $sameSoleProcess -and
        [bool]$status.healthy -and
        $safeHandoffWindow -and
        [bool]$market.market_data_ready
    )
    account_or_trade_state_queried = $false
    reasons = @($reasons)
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 8 -Compress
} else {
    [pscustomobject]$result
}
