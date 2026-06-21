# AudioVisualizer

A Windows desktop app that captures **what you hear** (system playback via WASAPI
loopback) and renders it in real time — built with Python + pygame + numpy +
pyaudiowpatch.

**19 visual modes** — Waveform, Waveform Rings, Spectrum, Audio Sun, Spectrogram,
Light Show, Particles, Fireworks, Laser, Snowfall, Tunnel Warp, Plasma, Kaleidoscope,
Synthwave Horizon, Vectorscope, VU Meters, Dot Matrix, Pulse Rings, and Ripples — each
with its own **per-mode options** (and one-click **Presets**). Adding a mode is one
drop-in file. The full catalog lives in `plan/visual-mode-ideas.md`.

> Status: **Phase 10.07 (v `00.0A.07`)** — **mode consolidation & smarter options**.
> Closely-related modes were merged into fewer, more flexible ones (a shared **Particles**
> Off/Sparse/Dense axis; **Waveform Rings** with a Rings count; **Particles** with a
> Field/Spiral **Emitter**), plus per-mode **Preset** dropdowns and **Mirror**/**Glow**
> shared options. A global **RenK logo overlay** and **background layer** sit over/behind
> every mode. **ESC never quits** (use the Quit button or Ctrl+Q). See
> `plan/development-phases.md` for the roadmap, `plan/audio-visualizer-plan.md` §3.3 for
> the mode table, and `plan/architecture-and-code-flow.md` for how it works.

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
| Per-mode options & Presets | bottom-row **option dropdowns** (incl. a **Preset** picker for curated looks) | — |
| Color scheme | **Color** dropdown (Classic / Rainbow / Rainbow+) | `C` cycles |
| Reduce motion (caps strobing) | `Motion` button | `M` |
| Appearance (style / accent / font) | `Menu` ▸ Appearance… (modal) | — |
| Background layer | `BG` button (modal: mode / sensitivity / opacity / height) | — |
| Foreground layer | `FG` button (modal: mode / intensity / direction / color / opacity / flash / reactivity / wind) — beat-triggered Lightning(+) / Flames(+) / Rain / Meteors(+) / Shockwave / Sparks / Fireworks / Edge Glow, plus **Storm** & **Party** combos, an Auto/Theme/named **color** override, lightning **flash** level, **reactivity** and **wind** | — |
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
**appearance** (style / accent / font), **background layer** (mode / sensitivity /
opacity / height), and **RenK logo preferences** (show, color, transparency, size,
position, spin, emit) are saved to `%APPDATA%\AudioVisualizer\settings.json`
(`schema_version` **7**) and restored next launch. Loading never crashes: a corrupt or
older file safely migrates or falls back to defaults — and mode keys merged in v00.0A.07
(e.g. `waveform_2`, `lightshow_2`, `particles_spiral`) are remapped to their survivor.
Per-mode option/preset selections are session-only (not persisted).

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
