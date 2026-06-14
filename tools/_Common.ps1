<#
.SYNOPSIS
    Shared helpers for the Audio Visualizer tools/*.ps1 scripts.

.DESCRIPTION
    Dot-source this from any tool script:

        . "$PSScriptRoot/_Common.ps1"

    Provides a consistent banner, status lines, "next steps" footer, repo-root
    resolution, and a Python 3.12+ interpreter finder shared by check-deps and setup.
    No side effects on dot-source (only defines functions / one constant).
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Repo root is the parent of the tools/ folder that holds this file.
$script:RepoRoot = Split-Path -Parent $PSScriptRoot

# Minimum Python the project supports (see plan/audio-visualizer-plan.md §1.1).
$script:MinPython = [version]"3.12"

function Get-RepoRoot {
    <# Returns the absolute path to the repository root. #>
    return $script:RepoRoot
}

function Get-MinPythonVersion {
    <# Returns the minimum supported Python [version] (3.12). #>
    return $script:MinPython
}

function Write-Banner {
    <# Prints a titled banner box for a tool script. #>
    param(
        [Parameter(Mandatory)][string]$Title,
        [string]$Subtitle
    )
    $line = "=" * 64
    Write-Host ""
    Write-Host $line -ForegroundColor Cyan
    Write-Host ("  " + $Title) -ForegroundColor Cyan
    if ($Subtitle) { Write-Host ("  " + $Subtitle) -ForegroundColor DarkGray }
    Write-Host $line -ForegroundColor Cyan
    Write-Host ""
}

function Write-Section {
    <# Prints a section heading. #>
    param([Parameter(Mandatory)][string]$Title)
    Write-Host ""
    Write-Host ("-- " + $Title) -ForegroundColor White
}

function Write-Ok {
    param([Parameter(Mandatory)][string]$Message)
    Write-Host ("  [ OK ]  " + $Message) -ForegroundColor Green
}

function Write-Info {
    param([Parameter(Mandatory)][string]$Message)
    Write-Host ("  [info]  " + $Message) -ForegroundColor Gray
}

function Write-WarnLine {
    param([Parameter(Mandatory)][string]$Message)
    Write-Host ("  [warn]  " + $Message) -ForegroundColor Yellow
}

function Write-FailLine {
    param([Parameter(Mandatory)][string]$Message)
    Write-Host ("  [FAIL]  " + $Message) -ForegroundColor Red
}

function Write-NextSteps {
    <# Prints a friendly "next steps" footer from an array of strings. #>
    param([Parameter(Mandatory)][string[]]$Steps)
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    foreach ($s in $Steps) {
        Write-Host ("  -> " + $s) -ForegroundColor Cyan
    }
    Write-Host ""
}

function Get-PythonInstallHelp {
    <#
    .SYNOPSIS
        Returns ready-to-print lines telling the user how to install Python 3.12+.
    #>
    return @(
        "Install Python 3.12 or newer (64-bit), then re-run this script:",
        "  winget install -e --id Python.Python.3.12",
        "  - or download from https://www.python.org/downloads/windows/",
        "    (tick 'Add python.exe to PATH' during install)",
        "Verify with:  py -3.12 --version"
    )
}

function Find-Python {
    <#
    .SYNOPSIS
        Finds an installed Python interpreter that satisfies the minimum version.

    .DESCRIPTION
        Probes the common Windows launchers/commands in priority order and returns
        the first interpreter whose version is >= MinVersion. If none qualifies but
        some Python was found, the returned object reports the best (too-old) version
        so callers can give an actionable message.

    .OUTPUTS
        [pscustomobject] with:
            Command    - exe to invoke (e.g. 'py' or 'python')
            BaseArgs   - string[] prefix args (e.g. @('-3.12')) or @()
            Version    - [version] detected, or $null
            Satisfies  - [bool] whether Version >= MinVersion
            Display    - human-readable invocation string
        Returns $null when no Python interpreter could be found at all.
    #>
    param([version]$MinVersion = $script:MinPython)

    # NOTE: no double quotes in this snippet on purpose. PowerShell (esp. 5.1)
    # strips embedded double quotes when passing args to native exes, which would
    # corrupt the code. Print space-separated ints and parse them here instead.
    $verCode = 'import sys; print(sys.version_info.major, sys.version_info.minor, sys.version_info.micro)'

    # Probe order: prefer the launcher pinned to 3.12, then any py3, then PATH python.
    $candidates = @(
        @{ Command = "py";      BaseArgs = @("-3.12") },
        @{ Command = "py";      BaseArgs = @("-3")    },
        @{ Command = "python";  BaseArgs = @()        },
        @{ Command = "python3"; BaseArgs = @()        }
    )

    $best = $null
    foreach ($c in $candidates) {
        if (-not (Get-Command $c.Command -ErrorAction SilentlyContinue)) { continue }

        $raw = $null
        try {
            $raw = (& $c.Command @($c.BaseArgs) -c $verCode 2>$null | Select-Object -First 1)
        } catch {
            continue
        }
        if (-not $raw) { continue }

        # $raw looks like "3 12 1" -> turn into a [version].
        $nums = ($raw.Trim() -split '\s+')
        if ($nums.Count -lt 2) { continue }
        $parsed = $null
        $verText = ($nums[0..2] -join ".")
        if (-not [version]::TryParse($verText, [ref]$parsed)) { continue }

        $argText = if ($c.BaseArgs.Count) { " " + ($c.BaseArgs -join " ") } else { "" }
        $obj = [pscustomobject]@{
            Command   = $c.Command
            BaseArgs  = $c.BaseArgs
            Version   = $parsed
            Satisfies = ($parsed -ge $MinVersion)
            Display   = ($c.Command + $argText)
        }

        if ($obj.Satisfies) { return $obj }                     # first good one wins
        if (-not $best -or $parsed -gt $best.Version) { $best = $obj }  # remember best too-old
    }

    return $best   # $null if nothing found; otherwise a too-old interpreter
}
