# AudioVisualizer

A Windows desktop app that captures **what you hear** (system playback via WASAPI
loopback) and renders it in real time — built with Python + pygame + numpy +
pyaudiowpatch.

Visual modes: **waveform, waveform 2, waveform circle (x4), spectrum, light show
(x2), particles, laser (x2), snowfall, and particles spiral** — 14 total; adding a
mode is one drop-in file.

> Status: **Phase 9 (v `00.09.00`)** — a global **RenK logo overlay** that appears over
> every mode: it slowly circles, pulses with the music, and can emit sparks on the beat.
> Configure it from the **RenK** panel — show on/off, Default ↔ **Rainbow+** color,
> transparency, size, and center/corner position — and read app info in the new **About**
> dialog. **ESC no longer quits** (use the Quit button or Ctrl+Q). Builds on Phase 8's 14
> visual modes. See `plan/development-phases.md` for the roadmap and
> `plan/architecture-and-code-flow.md` for how it works.

## Requirements

- **Windows 10/11**
- **Python 3.12 or newer** (64-bit)

Install Python if needed:

```powershell
winget install -e --id Python.Python.3.12
# or download from https://www.python.org/downloads/windows/  (tick "Add to PATH")
```

## Quick start (from source)

```powershell
.\tools\check-deps.ps1     # verify Python 3.12+, venv, packages, audio device
.\tools\setup.ps1          # create .venv and install dependencies
.\tools\run.ps1            # launch the app
```

Useful variants:

```powershell
.\tools\run.ps1 --debug --mode spectrum
.\tools\run.ps1 --selftest      # headless: render a few frames, exit 0
```

## Run the packaged app (no Python needed)

Build a single executable, then run it:

```powershell
.\tools\build-exe.ps1            # produces dist\AudioVisualizer.exe (+ self-test)
.\dist\AudioVisualizer.exe       # launch
.\dist\AudioVisualizer.exe --selftest   # headless check, exits 0
```

The exe bundles the PortAudio DLL and a Windows version resource. Drop an
`assets\icon.ico` into the repo before building to brand the exe.

## Controls

| Action | Mouse | Keyboard |
|--------|-------|----------|
| Start/stop capture | `Menu` ▸ Start/Stop | `Space` |
| Previous / next mode | `<` / `>` buttons | `Left`/`Right` or `[` / `]` |
| Jump to mode | mode **dropdown** (click to choose) | `1`–`9` (`D` opens dropdown) |
| Sensitivity down/up | `Sens -` / `Sens +` (value shown between) | `-` / `=` |
| Smoothing down/up | `Smooth -` / `Smooth +` (value shown between) | `,` / `.` |
| Particle size down/up | `Size -` / `Size +` (value shown between) | `F5` / `F6` |
| Animation speed down/up | `Speed -` / `Speed +` (value shown between) | `F7` / `F8` |
| Per-mode options | bottom-row **option dropdowns** (one per option of the active mode) | — |
| Color scheme | **Color** dropdown (Classic / Rainbow / Rainbow+) | `C` cycles |
| Reduce motion (caps strobing) | `Motion` button | `M` |
| RenK logo settings | `RenK` button (modal panel) | — |
| About (owner/license/version) | `About` button | — |
| Fullscreen | `Menu` ▸ Fullscreen | `F11` (exit with `Esc`) |
| Debug overlay | — | `F3` |
| Quit | `Menu` ▸ Quit | `Ctrl+Q` |
| Close modal / exit fullscreen | — | `Esc` |

A one-time **photosensitivity notice** appears before strobing modes; reduce-motion
caps flashing. **`Esc` never quits the app** — it only closes an open panel or leaves
fullscreen (quit via the `Quit` button or `Ctrl+Q`). Your mode, sensitivity, smoothing,
particle size, animation speed, color scheme, reduce-motion, fullscreen, window size,
and **RenK logo preferences** (show, color, transparency, size, position, emit) are
saved to `%APPDATA%\AudioVisualizer\settings.json` and restored next launch (a corrupt
file safely falls back to defaults).

## Developing

```powershell
.\tools\test.ps1      # pytest (headless)
.\tools\lint.ps1      # ruff + black --check + mypy
.\tools\format.ps1    # auto-fix: black + ruff --fix
.\tools\build-exe.ps1 # build dist\AudioVisualizer.exe and self-test it
```

Project docs live in `plan/` (product plan, phases, layout, testing) and AI
guidance in `.cursor/`. To **add a visual mode**, drop one file in
`src/audio_visualizer/visuals/` (subclass `BaseVisualizer` + `@register`) — it is
auto-discovered, no other edits required.

## Notes & limitations

- Captures system output (loopback); when nothing is playing it shows a "No audio
  detected" idle state. DRM-protected / exclusive-mode audio may not be captured.
- The single-file exe starts a little slower on first launch and can trip
  antivirus false-positives (a `-OneDir` build is a future option).

## License

AudioVisualizer is proprietary software — all rights reserved (see `LICENSE`).
No use, copying, or distribution is permitted without the copyright holder's
written consent. Bundled third-party components keep their own licenses and are
listed in `THIRD-PARTY-NOTICES.md` (pygame is LGPL; numpy, pyaudiowpatch, and
PortAudio are BSD/MIT-style).
