[CmdletBinding()]
param(
    [string]$SourceBinaryDirectory = 'C:\Users\awdse\OneDrive\Desktop\Project_Zeta_Terminus\mt5\runtime'
)

$ErrorActionPreference = 'Stop'

$projectRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
$liveRoot = Join-Path $projectRoot 'live-dev'
$runtimeRoot = Join-Path $liveRoot 'runtime\portable'
$packageRoot = Join-Path $liveRoot 'package\active'
$sourceRoot = [System.IO.Path]::GetFullPath($SourceBinaryDirectory)

function Assert-WithinLiveDev {
    param([Parameter(Mandatory = $true)][string]$Path)

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $prefix = $liveRoot.TrimEnd('\') + '\'
    if (-not $fullPath.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to modify a path outside live-dev: $fullPath"
    }
}

function Ensure-Directory {
    param([Parameter(Mandatory = $true)][string]$Path)

    Assert-WithinLiveDev -Path $Path
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Ensure-PackageJunction {
    param(
        [Parameter(Mandatory = $true)][string]$Link,
        [Parameter(Mandatory = $true)][string]$Target
    )

    Assert-WithinLiveDev -Path $Link
    Assert-WithinLiveDev -Path $Target
    $packagePrefix = $packageRoot.TrimEnd('\') + '\'
    if (-not [System.IO.Path]::GetFullPath($Target).StartsWith($packagePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Live junction target must be inside the active frozen package: $Target"
    }
    Ensure-Directory -Path $Target
    Ensure-Directory -Path (Split-Path -Parent $Link)
    if (Test-Path -LiteralPath $Link) {
        $item = Get-Item -LiteralPath $Link -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 -and $item.LinkType -eq 'Junction') {
            $actual = [System.IO.Path]::GetFullPath([string]@($item.Target)[0])
            if ($actual -eq [System.IO.Path]::GetFullPath($Target)) {
                return
            }
            throw "Existing junction has a different target: $Link -> $actual"
        }
        if ($item.PSIsContainer -and @(Get-ChildItem -LiteralPath $Link -Force).Count -eq 0) {
            Remove-Item -LiteralPath $Link
        } else {
            throw "Cannot replace a non-empty non-junction path: $Link"
        }
    }
    New-Item -ItemType Junction -Path $Link -Target $Target | Out-Null
}

foreach ($name in @('terminal64.exe', 'MetaEditor64.exe', 'metatester64.exe')) {
    if (-not (Test-Path -LiteralPath (Join-Path $sourceRoot $name) -PathType Leaf)) {
        throw "Required MT5 executable is missing: $name"
    }
}

Ensure-Directory -Path $runtimeRoot
foreach ($name in @('terminal64.exe', 'MetaEditor64.exe', 'metatester64.exe', 'Terminal.ico')) {
    $source = Join-Path $sourceRoot $name
    if (Test-Path -LiteralPath $source -PathType Leaf) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $runtimeRoot $name) -Force
    }
}

$junctions = @(
    @{ Link = 'MQL5\Experts\ZetaTerminusNext'; Target = 'MQL5\Experts\ZetaTerminusNext' },
    @{ Link = 'MQL5\Include\ZetaTerminusNext'; Target = 'MQL5\Include\ZetaTerminusNext' },
    @{ Link = 'MQL5\Presets\ZetaTerminusNext'; Target = 'MQL5\Presets\ZetaTerminusNext' }
)
foreach ($junction in $junctions) {
    Ensure-PackageJunction -Link (Join-Path $runtimeRoot $junction.Link) -Target (Join-Path $packageRoot $junction.Target)
}
Ensure-Directory -Path (Join-Path $runtimeRoot 'MQL5\Files\ZetaTerminusNext')
Ensure-Directory -Path (Join-Path $runtimeRoot 'Config')
Ensure-Directory -Path (Join-Path $runtimeRoot 'logs')

$terminal = Get-Item -LiteralPath (Join-Path $runtimeRoot 'terminal64.exe')
$marker = [ordered]@{
    schemaVersion = 1
    initializedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
    projectId = 'project-zeta-terminus-next'
    lane = 'live-dev'
    mode = 'portable-staged'
    terminalVersion = $terminal.VersionInfo.FileVersion
    terminalSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $terminal.FullName).Hash.ToLowerInvariant()
    packageRoot = $packageRoot
    accountCacheImported = $false
    liveAuthorized = $false
}
$marker | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $runtimeRoot '.zeta-next-live-runtime.json') -Encoding UTF8

Write-Output "Next Live-Dev MT5 shell initialized at $runtimeRoot"
Write-Output 'No account or broker cache was imported. No terminal was started.'
Write-Output 'Every static junction target is inside live-dev/package/active.'
