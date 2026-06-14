<#
.SYNOPSIS
    Build the single-file Windows executable with PyInstaller.

.DESCRIPTION
    Runs PyInstaller against AudioVisualizer.spec (which bundles the PortAudio
    DLL from pyaudiowpatch) and produces dist\AudioVisualizer.exe. After the
    build it runs the exe with --selftest to prove it launches.

.PARAMETER NoSelfTest
    Skip the post-build --selftest verification.

.PARAMETER Help
    Show usage and exit.

.EXAMPLE
    .\tools\build-exe.ps1
#>
[CmdletBinding()]
param(
    [switch]$NoSelfTest,
    [switch]$Help
)

. "$PSScriptRoot/_Common.ps1"

if ($Help) {
    Write-Banner -Title "build-exe" -Subtitle "PyInstaller -> dist\AudioVisualizer.exe"
    Write-Host "Usage: .\tools\build-exe.ps1 [-NoSelfTest]"
    Write-Host "Bundles the PortAudio DLL and self-tests the built exe."
    return
}

Write-Banner -Title "build-exe" -Subtitle "PyInstaller -> dist\AudioVisualizer.exe"

$repoRoot = Get-RepoRoot
$venvPy = Join-Path $repoRoot ".venv\Scripts\python.exe"
$spec = Join-Path $repoRoot "AudioVisualizer.spec"
$exe = Join-Path $repoRoot "dist\AudioVisualizer.exe"

if (-not (Test-Path $venvPy)) {
    Write-FailLine ".venv not found. Run tools\setup.ps1 first."
    exit 1
}

Write-Section "Running PyInstaller"
& $venvPy -m PyInstaller --noconfirm --clean $spec
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $exe)) {
    Write-FailLine "Build failed."
    exit 1
}
Write-Ok "Built $exe"

if (-not $NoSelfTest) {
    Write-Section "Self-test the built exe"
    # The exe is windowed (no console), so '& $exe' would not block. Use
    # Start-Process -Wait to actually wait and capture the real exit code.
    $proc = Start-Process -FilePath $exe -ArgumentList "--selftest" -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        Write-FailLine "Built exe failed --selftest (exit $($proc.ExitCode)). See logs\app.log."
        exit 1
    }
    Write-Ok "Built exe passed --selftest."
}

Write-NextSteps @(
    "Share / run:  .\dist\AudioVisualizer.exe",
    "Note: --onefile starts slower and may trip AV; -OneDir is a future option."
)
