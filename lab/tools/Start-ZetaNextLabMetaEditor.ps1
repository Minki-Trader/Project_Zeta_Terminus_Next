[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$CompilePath,
    [string]$LogPath
)

$ErrorActionPreference = 'Stop'

$projectRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
$labRoot = Join-Path $projectRoot 'lab'
$runtimeRoot = Join-Path $labRoot 'runtime\tester-portable'
$editorPath = Join-Path $runtimeRoot 'MetaEditor64.exe'
$resolvedCompilePath = [System.IO.Path]::GetFullPath($CompilePath)
$labPrefix = $labRoot.TrimEnd('\') + '\'

if (-not $resolvedCompilePath.StartsWith($labPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Compile source must be inside Lab: $resolvedCompilePath"
}
if (-not (Test-Path -LiteralPath $resolvedCompilePath -PathType Leaf)) {
    throw "Compile source does not exist: $resolvedCompilePath"
}
if (-not (Test-Path -LiteralPath $editorPath -PathType Leaf)) {
    throw 'Lab Portable is missing. Run Initialize-ZetaNextLabMt5.ps1 first.'
}
if (-not $LogPath) {
    $LogPath = Join-Path $labRoot 'artifacts\logs\metaeditor-command.log'
}
$resolvedLogPath = [System.IO.Path]::GetFullPath($LogPath)
if (-not $resolvedLogPath.StartsWith($labPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Compile log must stay inside Lab: $resolvedLogPath"
}
New-Item -ItemType Directory -Path (Split-Path -Parent $resolvedLogPath) -Force | Out-Null

$arguments = @('/portable', "/compile:`"$resolvedCompilePath`"", "/log:`"$resolvedLogPath`"")
Start-Process -FilePath $editorPath -ArgumentList $arguments -WorkingDirectory $runtimeRoot -WindowStyle Hidden -Wait | Out-Null
if (-not (Test-Path -LiteralPath $resolvedLogPath -PathType Leaf)) {
    throw "MetaEditor did not create the compile log: $resolvedLogPath"
}
$compileLog = Get-Content -Raw -LiteralPath $resolvedLogPath
Write-Output $compileLog.TrimEnd()
if ($compileLog -notmatch '0 errors, 0 warnings') {
    throw "MetaEditor compilation failed: $resolvedCompilePath"
}
