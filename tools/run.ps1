<#
.SYNOPSIS
    Run the Audio Visualizer app from the project virtual environment.

.DESCRIPTION
    Activates the venv's Python and launches the app. Extra arguments are passed
    through to the program (e.g. --debug, --mode spectrum, --selftest).

.PARAMETER Help
    Show usage and exit.

.EXAMPLE
    .\tools\run.ps1
.EXAMPLE
    .\tools\run.ps1 --debug --mode spectrum
#>
[CmdletBinding()]
param(
    [switch]$Help,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Passthrough
)

. "$PSScriptRoot/_Common.ps1"

if ($Help) {
    Write-Banner -Title "run" -Subtitle "Launch the app from the venv"
    Write-Host "Usage: .\tools\run.ps1 [-- <app args>]   e.g. --debug --mode spectrum --selftest"
    return
}

Write-Banner -Title "run" -Subtitle "Launch the app from the venv"

$repoRoot = Get-RepoRoot
$venvPy = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-FailLine ".venv not found. Run tools\setup.ps1 first."
    exit 1
}

$env:PYTHONPATH = Join-Path $repoRoot "src"
Write-Info ("Launching: python -m audio_visualizer " + ($Passthrough -join " "))
& $venvPy -m audio_visualizer @Passthrough
exit $LASTEXITCODE
