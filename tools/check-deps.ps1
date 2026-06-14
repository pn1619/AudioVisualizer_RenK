<#
.SYNOPSIS
    Verify this machine has everything needed to develop/run the Audio Visualizer.

.DESCRIPTION
    Checks, in order:
      1. Python >= 3.12 is installed (prints exact version found).
      2. A project virtual environment (.venv) exists.
      3. Required packages import inside the venv (numpy, pygame, pyaudiowpatch).
      4. A default audio OUTPUT (render) device is present for loopback capture.

    Read-only: it never installs or changes anything. Run tools\setup.ps1 to fix
    a missing venv / packages. Exit code 0 = ready, non-zero = something to fix.

.PARAMETER Help
    Show usage and exit.

.EXAMPLE
    .\tools\check-deps.ps1
#>
[CmdletBinding()]
param(
    [switch]$Help
)

. "$PSScriptRoot/_Common.ps1"

if ($Help) {
    Write-Banner -Title "check-deps" -Subtitle "Verify the dev/runtime environment (read-only)"
    Write-Host "Usage: .\tools\check-deps.ps1 [-Help]"
    Write-Host ""
    Write-Host "Checks Python >= 3.12, the .venv, required packages, and an audio output device."
    Write-Host "Makes no changes. Run tools\setup.ps1 to create the venv and install packages."
    return
}

Write-Banner -Title "check-deps" -Subtitle "Verify the dev/runtime environment (read-only)"

$repoRoot = Get-RepoRoot
$minPy    = Get-MinPythonVersion
$venvPy   = Join-Path $repoRoot ".venv\Scripts\python.exe"

$problems = New-Object System.Collections.Generic.List[string]

# 1) Python >= 3.12 -----------------------------------------------------------
Write-Section "Python >= $minPy"
$py = Find-Python -MinVersion $minPy
if (-not $py) {
    Write-FailLine "No Python interpreter found on PATH or via the 'py' launcher."
    foreach ($l in (Get-PythonInstallHelp)) { Write-Info $l }
    $problems.Add("Install Python $minPy or newer.")
}
elseif (-not $py.Satisfies) {
    Write-FailLine ("Found Python {0} ({1}) but {2}+ is required." -f $py.Version, $py.Display, $minPy)
    foreach ($l in (Get-PythonInstallHelp)) { Write-Info $l }
    $problems.Add("Upgrade Python to $minPy or newer.")
}
else {
    Write-Ok ("Python {0} via '{1}'" -f $py.Version, $py.Display)
}

# 2) Virtual environment ------------------------------------------------------
Write-Section "Virtual environment (.venv)"
$venvOk = Test-Path $venvPy
if ($venvOk) {
    Write-Ok ".venv found ($venvPy)"
}
else {
    Write-WarnLine ".venv not found."
    $problems.Add("Create the virtual environment: run tools\setup.ps1")
}

# 3) Required packages import inside the venv ---------------------------------
Write-Section "Required packages"
$required = @("numpy", "pygame", "pyaudiowpatch")
if ($venvOk) {
    # Keep pygame's import banner out of our captured output.
    $env:PYGAME_HIDE_SUPPORT_PROMPT = "1"
    foreach ($pkg in $required) {
        $probe = "import importlib,sys; m=importlib.import_module('$pkg'); print(getattr(m,'__version__','?'))"
        $ver = $null
        try { $ver = (& $venvPy -c $probe 2>$null | Select-Object -First 1) } catch { }
        if ($ver) {
            Write-Ok ("{0} {1}" -f $pkg, $ver.Trim())
        }
        else {
            Write-FailLine ("{0} is not importable in the venv." -f $pkg)
            $problems.Add("Install dependencies: run tools\setup.ps1")
        }
    }
}
else {
    Write-Info "Skipped (no .venv yet)."
}

# 4) Default audio output (render) device -------------------------------------
Write-Section "Audio output device (for WASAPI loopback)"
if ($venvOk) {
    # Single quotes only (no double quotes): PowerShell mangles embedded double
    # quotes when passing -c to a native exe.
    $audioCode = @'
import sys
try:
    import pyaudiowpatch as pa
except Exception as e:
    print('ERR import pyaudiowpatch:', e); sys.exit(3)
try:
    with pa.PyAudio() as p:
        info = p.get_default_wasapi_loopback()
        print('OK', info.get('name', '?'))
except Exception as e:
    print('ERR no loopback device:', e); sys.exit(4)
'@
    $out = $null
    try { $out = (& $venvPy -c $audioCode 2>&1 | Select-Object -First 1) } catch { }
    if ($out -and $out.StartsWith("OK ")) {
        Write-Ok ("Default loopback endpoint: " + $out.Substring(3))
    }
    else {
        Write-WarnLine ("Could not confirm a loopback device. " + ($out -as [string]))
        Write-Info "Not fatal now; needed once audio capture is implemented."
    }
}
else {
    Write-Info "Skipped (no .venv yet)."
}

# Summary ---------------------------------------------------------------------
Write-Section "Summary"
if ($problems.Count -eq 0) {
    Write-Ok "Environment looks ready."
    Write-NextSteps @(
        "Run the test suite once it exists:  .\tools\test.ps1",
        "Start the app (after Phase 0):       .\tools\run.ps1"
    )
    exit 0
}
else {
    Write-FailLine ("{0} item(s) need attention:" -f $problems.Count)
    foreach ($p in $problems) { Write-Host ("        - " + $p) -ForegroundColor Yellow }
    Write-NextSteps @(
        "Fix the items above (most are solved by:  .\tools\setup.ps1).",
        "Re-run:  .\tools\check-deps.ps1"
    )
    exit 1
}
