# AudioVisualizer

A Windows desktop app that captures **what you hear** (system playback via WASAPI
loopback) and renders it in real time — built with Python + pygame + numpy +
pyaudiowpatch.

Visual modes: **waveform, waveform 2, spectrum, light show, particles, laser,
snowfall, and particles spiral** — adding a mode is one drop-in file.

> Status: **Phase 4 (v `00.04.00`)** — live, persisted **size / speed / color-scheme**
> tunables, a **mode dropdown**, the new **Waveform 2** mode (8 total), on top of
> Phase 3's settings persistence, device recovery, and version-stamped `.exe`.
> See `plan/development-phases.md` for the roadmap.

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
| Start/stop capture | Start/Stop button | `Space` |
| Previous / next mode | `<` / `>` buttons | `Left`/`Right` or `[` / `]` |
| Jump to mode | mode **dropdown** (click to choose) | `1`–`9` (`D` opens dropdown) |
| Sensitivity down/up | `Sens -` / `Sens +` | `-` / `=` |
| Smoothing down/up | `Smooth -` / `Smooth +` | `,` / `.` |
| Particle size down/up | `Size -` / `Size +` | `F5` / `F6` |
| Animation speed down/up | `Speed -` / `Speed +` | `F7` / `F8` |
| Color scheme (classic/rainbow) | `Classic`/`Rainbow` button | `C` |
| Reduce motion (caps strobing) | `Motion` button | `M` |
| Fullscreen | `Full` button | `F11` (exit with `Esc`) |
| Debug overlay | — | `F3` |
| Quit | `Quit` button | `Esc` / `Ctrl+Q` |

A one-time **photosensitivity notice** appears before strobing modes; reduce-motion
caps flashing. Your mode, sensitivity, smoothing, particle size, animation speed,
color scheme, reduce-motion, fullscreen, and window size are saved to
`%APPDATA%\AudioVisualizer\settings.json` and restored next launch (a corrupt file
safely falls back to defaults).

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

AudioVisualizer is released under the MIT License (see `LICENSE`). Bundled
third-party components and their licenses are listed in `THIRD-PARTY-NOTICES.md`
(pygame is LGPL; numpy, pyaudiowpatch, and PortAudio are BSD/MIT-style).
