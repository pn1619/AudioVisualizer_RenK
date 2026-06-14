# tools/

Developer scripts for the Audio Visualizer. Each `*.ps1` has a `*.cmd` wrapper
(so it works from `cmd.exe` or a double-click), supports `-Help`, prints a banner,
and ends with "next steps". Shared helpers live in `_Common.ps1`.

> Requires **Python 3.12+** (64-bit). On Windows, run from the repo root in
> PowerShell. If scripts are blocked, the `.cmd` wrappers already pass
> `-ExecutionPolicy Bypass`.

## Available now

| Script | What it does |
|--------|--------------|
| `check-deps.ps1` | Read-only check: Python ≥ 3.12, `.venv`, required packages import, audio output device present. Fixes nothing. |
| `setup.ps1` | Create `.venv`, upgrade pip, install `requirements-dev.txt`, install the pre-commit hook. `-Recreate` rebuilds the venv. |

## Typical first run

```powershell
# from the repo root
.\tools\check-deps.ps1     # see what's missing (Python, venv, packages)
.\tools\setup.ps1          # create .venv and install everything
.\tools\check-deps.ps1     # confirm: should report "Environment looks ready."
```

If `check-deps` says Python is missing or too old:

```powershell
winget install -e --id Python.Python.3.12
# or download from https://www.python.org/downloads/windows/  (tick "Add to PATH")
```

## Planned (added as the project grows)

`run.ps1`, `test.ps1`, `lint.ps1`, `format.ps1`, `build-exe.ps1`,
`spike-loopback.py` — see `plan/audio-visualizer-plan.md` §4 and
`plan/repository-and-code-layout.md`.
