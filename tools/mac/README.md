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
| `build-app.sh` | Package `dist/AudioVisualizer.app` with PyInstaller + self-test |
| `test.sh` | pytest headless (`SDL_VIDEODRIVER=dummy`) |
| `lint.sh` | ruff + black --check + mypy (non-blocking) |
| `format.sh` | black + ruff --fix |
| `spike-capture.py` | Phase 0.5 spike: list inputs + print RMS (`sounddevice`) |

```bash
./tools/mac/spike-capture.py --list
./tools/mac/spike-capture.py --seconds 5
./tools/mac/spike-capture.py --device BlackHole
```

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

## Audio capture on macOS

The backend is selected automatically on macOS by `audio/source_factory.py`. There are
three ways to capture, all chosen in the app's **Src** modal:

1. **Microphone** (default) — PortAudio via `sounddevice`. Works out of the box; first
   launch prompts for **Microphone** permission.
2. **System audio, native tap** — pick **"System Audio (native tap)"**. Uses macOS
   **ScreenCaptureKit** (macOS 13+), *no driver install needed*. First use prompts for
   **Screen Recording** permission (System Settings → Privacy & Security → Screen
   Recording); enable it and reopen the app.
3. **System audio, BlackHole** — install
   **[BlackHole](https://existential.audio/blackhole/)** (`brew install blackhole-2ch`) or
   an *Aggregate/Multi-Output* device, route system audio into it, then select it in
   **Src** (loopback devices are listed first).

```bash
./tools/mac/run.sh --debug          # then pick a source in the Src modal
brew install blackhole-2ch          # optional: driver-based system audio
```

If a source can't start (e.g. permission not yet granted) the app shows an error banner
and keeps running — grant the permission and reselect the source.

## Build a standalone `.app`

```bash
./tools/mac/build-app.sh            # -> dist/AudioVisualizer.app (self-tested)
open dist/AudioVisualizer.app       # or double-click it in Finder
```

What the build does:

- Bundles the **PortAudio** dylib (`sounddevice`) and the **pyobjc ScreenCaptureKit**
  frameworks, plus the visual modes (discovered dynamically) and app assets.
- Generates an `.icns` from `assets/renk_icon.png` (via `sips`/`iconutil`).
- Writes `Info.plist` with `NSMicrophoneUsageDescription` and `LSMinimumSystemVersion 13.0`.
- Runs the built app with `--selftest` to prove it launches.

Notes:

- The app is **unsigned/un-notarized**. First launch may need **right-click → Open** (or
  *System Settings → Privacy & Security → Open Anyway*) to pass Gatekeeper. Signing +
  notarization for distribution is future work.
- `dist/` and `build/` are git-ignored.

## What works today vs. what the port will add

| Area | Today (macOS) | Port work (later) |
|------|---------------|-------------------|
| Visual modes / UI | Runs (GUI + headless tests) | Polish, macOS windowing |
| Tests / lint | Full pytest suite | Same |
| Mic capture | ✅ `MacInputSource` (PortAudio) | — |
| System-audio (native) | ✅ `MacSystemAudioSource` (ScreenCaptureKit) | Robustness/perf polish |
| System-audio (BlackHole) | ✅ via BlackHole / aggregate device | — |
| Packaging | ✅ `.app` via `build-app.sh` | Code signing + notarization |
| Settings path | `~/.config/AudioVisualizer` (via `platform_win.py`) | May rename/split platform module |

Windows loopback (`pyaudiowpatch`) is **Windows-only** and never imported on macOS.

## Shared helper scripts

These live in `tools/` and work on any platform with the venv active:

- `tools/preview_mode.py` — render a mode to PNG (headless)
- `tools/prep_icon.py` — bake icons (needs Pillow, in `requirements-mac-dev.txt`)

Every `tools/mac/*.sh` script supports `-h` / `--help`.
