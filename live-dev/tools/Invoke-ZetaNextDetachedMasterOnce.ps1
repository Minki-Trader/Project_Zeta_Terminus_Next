[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string]$OpenPath,

    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string]$ProjectRoot,

    [Parameter(Mandatory)]
    [ValidatePattern('^[0-9a-f]{32}$')]
    [string]$LaunchId
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$openScript = [System.IO.Path]::GetFullPath($OpenPath)
$project = [System.IO.Path]::GetFullPath($ProjectRoot)
$logPath = Join-Path $project 'live-dev\logs\master-detached-once.log'
$utf8 = [System.Text.UTF8Encoding]::new($false)

function Write-OnceLog {
    param([Parameter(Mandatory)][string]$Message)

    $line = '{0:o} PID={1} {2}{3}' -f (Get-Date), $PID, $Message, [Environment]::NewLine
    [System.IO.File]::AppendAllText($logPath, $line, $utf8)
}

try {
    if (-not (Test-Path -LiteralPath $openScript -PathType Leaf)) {
        throw "Master worker is missing: $openScript"
    }
    $logDirectory = Split-Path -Parent $logPath
    if (-not (Test-Path -LiteralPath $logDirectory -PathType Container)) {
        [void][System.IO.Directory]::CreateDirectory($logDirectory)
    }
    [System.IO.File]::WriteAllText(
        $logPath,
        ('LAUNCH={0}{1}' -f $LaunchId, [Environment]::NewLine),
        $utf8
    )

    & $openScript 2>&1 | ForEach-Object { Write-OnceLog ([string]$_) }
    [System.IO.File]::AppendAllText(
        $logPath,
        ('LAUNCH={0} RESULT=OK{1}' -f $LaunchId, [Environment]::NewLine),
        $utf8
    )
    exit 0
} catch {
    try {
        Write-OnceLog ('ERROR ' + ($_ | Out-String).Trim())
        [System.IO.File]::AppendAllText(
            $logPath,
            ('LAUNCH={0} RESULT=ERROR{1}' -f $LaunchId, [Environment]::NewLine),
            $utf8
        )
    } catch { }
    exit 1
}
