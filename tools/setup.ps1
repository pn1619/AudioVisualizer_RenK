<#
.SYNOPSIS
    Create the project virtual environment and install dependencies.

.DESCRIPTION
    1. Locates Python >= 3.12 (prints install help and stops if missing).
    2. Creates .venv at the repo root (skips if it already exists, unless -Recreate).
    3. Upgrades pip and installs requirements-dev.txt (which pulls in requirements.txt).
    4. Installs the pre-commit git hook when .pre-commit-config.yaml is present.

.PARAMETER Recreate
    Delete and rebuild .venv from scratch.

.PARAMETER Help
    Show usage and exit.

.EXAMPLE
    .\tools\setup.ps1

.EXAMPLE
    .\tools\setup.ps1 -Recreate
#>
[CmdletBinding()]
param(
    [switch]$Recreate,
    [switch]$Help
)

. "$PSScriptRoot/_Common.ps1"

if ($Help) {
    Write-Banner -Title "setup" -Subtitle "Create .venv and install dependencies"
    Write-Host "Usage: .\tools\setup.ps1 [-Recreate] [-Help]"
    Write-Host ""
    Write-Host "  -Recreate   Delete and rebuild the virtual environment."
    Write-Host ""
    Write-Host "Requires Python >= 3.12. Run tools\check-deps.ps1 to inspect the environment."
    return
}

Write-Banner -Title "setup" -Subtitle "Create .venv and install dependencies"

$repoRoot = Get-RepoRoot
$minPy    = Get-MinPythonVersion
$venvDir  = Join-Path $repoRoot ".venv"
$venvPy   = Join-Path $venvDir "Scripts\python.exe"
$reqsDev  = Join-Path $repoRoot "requirements-dev.txt"
$reqs     = Join-Path $repoRoot "requirements.txt"
$precfg   = Join-Path $repoRoot ".pre-commit-config.yaml"

# 1) Python -------------------------------------------------------------------
Write-Section "Locate Python >= $minPy"
$py = Find-Python -MinVersion $minPy
if (-not $py -or -not $py.Satisfies) {
    if ($py) { Write-FailLine ("Found Python {0} but {1}+ is required." -f $py.Version, $minPy) }
    else     { Write-FailLine "No Python interpreter found." }
    foreach ($l in (Get-PythonInstallHelp)) { Write-Info $l }
    Write-NextSteps @("Install Python $minPy+, then re-run:  .\tools\setup.ps1")
    exit 1
}
Write-Ok ("Using Python {0} via '{1}'" -f $py.Version, $py.Display)

# 2) Virtual environment ------------------------------------------------------
Write-Section "Virtual environment"
if ($Recreate -and (Test-Path $venvDir)) {
    Write-Info "Removing existing .venv (-Recreate)..."
    Remove-Item -Recurse -Force $venvDir
}
if (Test-Path $venvPy) {
    Write-Ok ".venv already exists (use -Recreate to rebuild)."
}
else {
    Write-Info "Creating .venv ..."
    & $py.Command @($py.BaseArgs) -m venv $venvDir
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPy)) {
        Write-FailLine "Failed to create the virtual environment."
        exit 1
    }
    Write-Ok ".venv created."
}

# 3) pip + dependencies -------------------------------------------------------
Write-Section "Install dependencies"
Write-Info "Upgrading pip ..."
& $venvPy -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Write-FailLine "pip upgrade failed."; exit 1 }

$reqFile = if (Test-Path $reqsDev) { $reqsDev } elseif (Test-Path $reqs) { $reqs } else { $null }
if (-not $reqFile) {
    Write-WarnLine "No requirements file found; skipping package install."
}
else {
    Write-Info ("Installing from {0} ..." -f (Split-Path -Leaf $reqFile))
    & $venvPy -m pip install -r $reqFile
    if ($LASTEXITCODE -ne 0) { Write-FailLine "Dependency install failed."; exit 1 }
    Write-Ok "Dependencies installed."
}

# 4) pre-commit hook ----------------------------------------------------------
Write-Section "pre-commit hook"
$inGitRepo = Test-Path (Join-Path $repoRoot ".git")
if (Test-Path $precfg) {
    if ($inGitRepo) {
        & $venvPy -m pre_commit install 2>$null
        if ($LASTEXITCODE -eq 0) { Write-Ok "pre-commit hook installed." }
        else { Write-WarnLine "Could not install pre-commit (is it in requirements-dev.txt?)." }
    }
    else {
        Write-Info "Not a git repo yet; skipping pre-commit hook install."
    }
}
else {
    Write-Info "No .pre-commit-config.yaml yet; skipping."
}

Write-Section "Done"
Write-Ok "Environment is set up."
Write-NextSteps @(
    "Verify everything:  .\tools\check-deps.ps1",
    "Activate the venv:  .\.venv\Scripts\Activate.ps1",
    "Run tests/app once they exist:  .\tools\test.ps1  /  .\tools\run.ps1"
)
