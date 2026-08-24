[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ConfigurationPath,
    [switch]$Wait
)

$ErrorActionPreference = 'Stop'

$projectRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
$labRoot = Join-Path $projectRoot 'lab'
$runtimeRoot = Join-Path $labRoot 'runtime\tester-portable'
$terminalPath = Join-Path $runtimeRoot 'terminal64.exe'
$resolvedConfiguration = [System.IO.Path]::GetFullPath($ConfigurationPath)
$labPrefix = $labRoot.TrimEnd('\') + '\'

if (-not $resolvedConfiguration.StartsWith($labPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Tester configuration must be inside Lab: $resolvedConfiguration"
}
if (-not (Test-Path -LiteralPath $resolvedConfiguration -PathType Leaf)) {
    throw "Tester configuration does not exist: $resolvedConfiguration"
}
if (-not (Test-Path -LiteralPath $terminalPath -PathType Leaf)) {
    throw 'Lab Portable is missing. Run Initialize-ZetaNextLabMt5.ps1 first.'
}

$arguments = @('/portable', "/config:`"$resolvedConfiguration`"")
$parameters = @{
    FilePath = $terminalPath
    ArgumentList = $arguments
    WorkingDirectory = $runtimeRoot
    PassThru = $true
}
if ($Wait) {
    $parameters.Wait = $true
    $parameters.WindowStyle = 'Hidden'
}
$process = Start-Process @parameters
Write-Output "Started Next Lab tester (PID $($process.Id)) with $resolvedConfiguration"
