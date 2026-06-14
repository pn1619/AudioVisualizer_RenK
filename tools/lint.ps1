<#
.SYNOPSIS
    Lint and format-check the codebase (ruff + black --check + optional mypy).

.PARAMETER Help
    Show usage and exit.

.EXAMPLE
    .\tools\lint.ps1
#>
[CmdletBinding()]
param([switch]$Help)

. "$PSScriptRoot/_Common.ps1"

if ($Help) {
    Write-Banner -Title "lint" -Subtitle "ruff + black --check (+ mypy)"
    Write-Host "Usage: .\tools\lint.ps1"
    Write-Host "Read-only checks. Use tools\format.ps1 to auto-fix."
    return
}

Write-Banner -Title "lint" -Subtitle "ruff + black --check (+ mypy)"

$repoRoot = Get-RepoRoot
$venvPy = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-FailLine ".venv not found. Run tools\setup.ps1 first."
    exit 1
}

$failed = 0

Write-Section "ruff (lint)"
& $venvPy -m ruff check src tests
if ($LASTEXITCODE -ne 0) { $failed = 1 }

Write-Section "black (format check)"
& $venvPy -m black --check src tests
if ($LASTEXITCODE -ne 0) { $failed = 1 }

Write-Section "mypy (types, non-blocking)"
& $venvPy -m mypy src
if ($LASTEXITCODE -ne 0) { Write-WarnLine "mypy reported issues (non-blocking)." }

if ($failed -eq 0) {
    Write-Ok "Lint + format checks passed."
    exit 0
}
Write-FailLine "Lint/format issues found. Fix with: .\tools\format.ps1"
exit 1
