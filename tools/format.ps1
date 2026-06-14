<#
.SYNOPSIS
    Auto-format the codebase: black + ruff --fix.

.PARAMETER Help
    Show usage and exit.

.EXAMPLE
    .\tools\format.ps1
#>
[CmdletBinding()]
param([switch]$Help)

. "$PSScriptRoot/_Common.ps1"

if ($Help) {
    Write-Banner -Title "format" -Subtitle "black + ruff --fix"
    Write-Host "Usage: .\tools\format.ps1"
    return
}

Write-Banner -Title "format" -Subtitle "black + ruff --fix"

$repoRoot = Get-RepoRoot
$venvPy = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-FailLine ".venv not found. Run tools\setup.ps1 first."
    exit 1
}

Write-Section "ruff --fix"
& $venvPy -m ruff check --fix src tests

Write-Section "black"
& $venvPy -m black src tests

Write-Ok "Formatting applied."
Write-NextSteps @("Re-check:  .\tools\lint.ps1", "Run tests:  .\tools\test.ps1")
