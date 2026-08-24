[CmdletBinding()]
param(
    [string]$SourcePortable = 'C:\Users\awdse\OneDrive\Desktop\Project_Zeta_Terminus\mt5\tester-runtime',
    [bool]$CopyRequiredMarketData = $true
)

$ErrorActionPreference = 'Stop'

$projectRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
$labRoot = Join-Path $projectRoot 'lab'
$runtimeRoot = Join-Path $labRoot 'runtime\tester-portable'
$sourceRoot = [System.IO.Path]::GetFullPath($SourcePortable)

function Assert-WithinLab {
    param([Parameter(Mandatory = $true)][string]$Path)

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $prefix = $labRoot.TrimEnd('\') + '\'
    if (-not $fullPath.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to modify a path outside Lab: $fullPath"
    }
}

function Ensure-Directory {
    param([Parameter(Mandatory = $true)][string]$Path)

    Assert-WithinLab -Path $Path
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Copy-Tree {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [string[]]$ExcludeDirectories = @()
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        return
    }
    Assert-WithinLab -Path $Destination
    Ensure-Directory -Path $Destination
    $arguments = @($Source, $Destination, '/E', '/COPY:DAT', '/DCOPY:DAT', '/R:2', '/W:1', '/NFL', '/NDL', '/NJH', '/NJS', '/NP')
    if ($ExcludeDirectories.Count -gt 0) {
        $arguments += '/XD'
        $arguments += $ExcludeDirectories
    }
    & robocopy.exe @arguments | Out-Null
    if ($LASTEXITCODE -gt 7) {
        throw "Robocopy failed with exit code ${LASTEXITCODE}: $Source -> $Destination"
    }
}

function Ensure-Junction {
    param(
        [Parameter(Mandatory = $true)][string]$Link,
        [Parameter(Mandatory = $true)][string]$Target
    )

    Assert-WithinLab -Path $Link
    Assert-WithinLab -Path $Target
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

if (-not (Test-Path -LiteralPath $sourceRoot -PathType Container)) {
    throw "Source Portable does not exist: $sourceRoot"
}
if ($sourceRoot -eq [System.IO.Path]::GetFullPath($runtimeRoot)) {
    throw 'Source and destination Portable paths must differ.'
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

Copy-Tree -Source (Join-Path $sourceRoot 'Config') -Destination (Join-Path $runtimeRoot 'Config')
Copy-Tree -Source (Join-Path $sourceRoot 'Sounds') -Destination (Join-Path $runtimeRoot 'Sounds')
Copy-Tree -Source (Join-Path $sourceRoot 'MQL5\Include') -Destination (Join-Path $runtimeRoot 'MQL5\Include') -ExcludeDirectories @((Join-Path $sourceRoot 'MQL5\Include\ZetaTerminus'))
Copy-Tree -Source (Join-Path $sourceRoot 'MQL5\Libraries') -Destination (Join-Path $runtimeRoot 'MQL5\Libraries') -ExcludeDirectories @((Join-Path $sourceRoot 'MQL5\Libraries\ZetaTerminus'))

if ($CopyRequiredMarketData) {
    $serverRoots = @('Bases\FPMarketsSC-Live', 'Tester\bases\FPMarketsSC-Live')
    foreach ($serverRelative in $serverRoots) {
        $sourceServer = Join-Path $sourceRoot $serverRelative
        $destinationServer = Join-Path $runtimeRoot $serverRelative
        Ensure-Directory -Path $destinationServer
        Get-ChildItem -LiteralPath $sourceServer -File -Force -ErrorAction SilentlyContinue | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $destinationServer $_.Name) -Force
        }
        Copy-Tree -Source (Join-Path $sourceServer 'symbols') -Destination (Join-Path $destinationServer 'symbols')
        foreach ($symbol in @('US100', 'US30', 'US500')) {
            Copy-Tree -Source (Join-Path $sourceServer "history\$symbol") -Destination (Join-Path $destinationServer "history\$symbol")
            Copy-Tree -Source (Join-Path $sourceServer "ticks\$symbol") -Destination (Join-Path $destinationServer "ticks\$symbol")
        }
    }
}

$junctions = @(
    @{ Link = 'MQL5\Experts\ZetaTerminus'; Target = 'control-v6r6\src\Experts' },
    @{ Link = 'MQL5\Profiles\Tester\ZetaTerminus'; Target = 'control-v6r6\config\tester' },
    @{ Link = 'MQL5\Files\ZetaTerminus'; Target = 'artifacts\ea-files\control-v6r6' },
    @{ Link = 'MQL5\Experts\ZetaTerminusNext'; Target = 'mt5\src\Experts' },
    @{ Link = 'MQL5\Include\ZetaTerminusNext'; Target = 'mt5\src\Include\ZetaTerminusNext' },
    @{ Link = 'MQL5\Profiles\Tester\ZetaTerminusNext'; Target = 'mt5\config\tester' },
    @{ Link = 'MQL5\Files\ZetaTerminusNext'; Target = 'artifacts\ea-files\v7' },
    @{ Link = 'reports'; Target = 'artifacts\backtests' }
)
foreach ($junction in $junctions) {
    Ensure-Junction -Link (Join-Path $runtimeRoot $junction.Link) -Target (Join-Path $labRoot $junction.Target)
}

$terminal = Get-Item -LiteralPath (Join-Path $runtimeRoot 'terminal64.exe')
$marker = [ordered]@{
    schemaVersion = 1
    initializedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
    projectId = 'project-zeta-terminus-next'
    lane = 'lab'
    mode = 'portable'
    sourcePortable = $sourceRoot
    terminalVersion = $terminal.VersionInfo.FileVersion
    terminalSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $terminal.FullName).Hash.ToLowerInvariant()
    copiedSymbols = @('US100', 'US30', 'US500')
    liveAuthorized = $false
}
$marker | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $runtimeRoot '.zeta-next-lab-runtime.json') -Encoding UTF8

Write-Output "Next Lab MT5 runtime initialized at $runtimeRoot"
Write-Output "Terminal version: $($terminal.VersionInfo.FileVersion)"
Write-Output 'Junction targets are confined to lab/.'
