# macOS development tools

Parallel to the Windows `tools/*.ps1` scripts. **Do not mix** — on macOS use only
this folder; on Windows use only `tools/*.ps1`.

## Requirements

- **macOS** (Apple Silicon or Intel)
- **Python 3.12+** (64-bit)
- Separate dependency files: `requirements-mac.txt` / `requirements-mac-dev.txt`
  (Windows uses `requirements.txt` / `requirements-dev.txt`)

Install Python if needed:

```bash
brew install python@3.12
python3.12 --version
```

## First-time setup

From the repo root:

```bash
./tools/mac/check-deps.sh    # read-only: see what's missing
./tools/mac/setup.sh         # create .venv + install macOS dev deps
./tools/mac/check-deps.sh    # should report ready
```

## Daily workflow

| Script | What it does |
|--------|----------------|
| `check-deps.sh` | Verify Python, `.venv`, packages, headless pygame |
| `setup.sh` | Create `.venv`, install `requirements-mac-dev.txt`, pre-commit |
| `run.sh` | Launch the app (`--selftest`, `--debug`, `--mode spectrum`, …) |
| `test.sh` | pytest headless (`SDL_VIDEODRIVER=dummy`) |
| `lint.sh` | ruff + black --check + mypy (non-blocking) |
| `format.sh` | black + ruff --fix |

```bash
./tools/mac/test.sh
./tools/mac/run.sh --selftest
./tools/mac/run.sh --debug --mode spectrum   # needs a display
```

Activate the venv manually:

```bash
source .venv/bin/activate
export PYTHONPATH=src
```

## VS Code / Cursor

1. **Python interpreter:** select `.venv/bin/python` (Command Palette → *Python: Select Interpreter*).
2. **PYTHONPATH:** launch configs in `.vscode/launch.json` already set `PYTHONPATH=src`.
3. Windows-specific `settings.json` paths (`.venv/Scripts/python.exe`) do not apply on macOS — pick the interpreter once per machine.

## What works today vs. what the port will add

| Area | Today (macOS dev) | Port work (later) |
|------|-------------------|-------------------|
| Visual modes / UI | Runs (GUI + headless tests) | Polish, macOS windowing |
| Tests / lint | Full pytest suite | Same |
| Audio capture | `SyntheticSource` only | Core Audio system loopback |
| Settings path | `~/.config/AudioVisualizer` (via `platform_win.py`) | May rename/split platform module |
| Packaging | N/A | `.app` bundle (PyInstaller or other) |

Audio loopback (`pyaudiowpatch`) is **Windows-only**. The app already runs on macOS for
development using synthetic audio and headless self-tests; real “what you hear” capture is
the main porting task.

## Shared helper scripts

These live in `tools/` and work on any platform with the venv active:

- `tools/preview_mode.py` — render a mode to PNG (headless)
- `tools/prep_icon.py` — bake icons (needs Pillow, in `requirements-mac-dev.txt`)

Every `tools/mac/*.sh` script supports `-h` / `--help`.
