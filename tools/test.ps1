<#
.SYNOPSIS
    Run the pytest suite headlessly (dummy SDL drivers).

.PARAMETER Coverage
    Also produce a coverage report (requires coverage/pytest-cov).

.PARAMETER Help
    Show usage and exit.

.EXAMPLE
    .\tools\test.ps1
#>
[CmdletBinding()]
param(
    [switch]$Coverage,
    [switch]$Help,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Passthrough
)

. "$PSScriptRoot/_Common.ps1"

if ($Help) {
    Write-Banner -Title "test" -Subtitle "Run pytest headlessly"
    Write-Host "Usage: .\tools\test.ps1 [-Coverage] [-- <pytest args>]"
    return
}

Write-Banner -Title "test" -Subtitle "Run pytest headlessly"

$repoRoot = Get-RepoRoot
$venvPy = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-FailLine ".venv not found. Run tools\setup.ps1 first."
    exit 1
}

$env:SDL_VIDEODRIVER = "dummy"
$env:SDL_AUDIODRIVER = "dummy"
$env:PYGAME_HIDE_SUPPORT_PROMPT = "1"

$pytestArgs = @()
if ($Coverage) { $pytestArgs += @("--cov=audio_visualizer", "--cov-report=term-missing") }
if ($Passthrough) { $pytestArgs += $Passthrough }

Write-Info "Running pytest ..."
& $venvPy -m pytest @pytestArgs
$code = $LASTEXITCODE
if ($code -eq 0) {
    Write-Ok "All tests passed."
    Write-NextSteps @("Run the app:  .\tools\run.ps1", "Lint:  .\tools\lint.ps1")
}
else {
    Write-FailLine "Tests failed (exit $code)."
}
exit $code
