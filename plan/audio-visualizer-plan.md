# Windows System-Audio Visualizer — Product & Engineering Plan

> **Guiding principle (read this first):** *Simple but works beats complicated but broken.*
> Every decision below favors the path that gets a **moving, audio-reactive window on screen reliably**, with code that is easy to read, comment, debug, and extend.

This document is the **single source of truth** for the project. Companion docs:

- `plan/development-phases.md` — **detailed per-phase build guide**: scope, tests, exit criteria, time estimates, and future work (expands §7 below).
- `plan/repository-and-code-layout.md` — folder tree, module responsibilities, how pieces connect.
- `plan/testing.md` — how we prove the code works and the window actually runs.
- `plan/git-and-versioning.md` — branching model, commit style, `PP.FF.BB` versioning, and per-phase tagging.
- `.cursor/rules/python-audio-visualizer.mdc` — enforced project conventions (always applied).
- `.cursor/rules/python-coding-style.mdc` — enforced Python style.
- `.cursor/skills/audio-visualizer/SKILL.md` — implementation checklist for the next agent.

---

## 0. Vision

A **Windows desktop app** that captures **what you hear** (system playback / loopback) and renders **real-time visuals**: waveform, spectrum, light show, particles, laser, snowfall, and many more (full list in §3.3). Runs locally, no cloud. Ships as a **single `.exe`**.

**User story:** *"I play music or a game and get a responsive visualization on screen — fullscreen optional — without needing a microphone."*

---

## 1. Language, coding style, structure, comments, debugging

### 1.1 Language (chosen)

**Python 3.12+** (3.12 or newer — this is the version the project targets and tests against). Rationale tied to the guiding principle:

- WASAPI **loopback capture works reliably** via `pyaudiowpatch` (a maintained PyAudio fork with loopback support).
- **pygame** gives immediate 2D drawing — waveform, bars, particles, lasers are all easy.
- **numpy** does the FFT/DSP fast and correctly with a few lines.
- **Debugging is trivial**: standard `logging`, breakpoints, no native runtime/bootstrap layer (the previous WinUI attempt died on bootstrap — avoided entirely here).

A **`.python-version`** file pins `3.12` for `pyenv`/tooling, and `pyproject.toml` sets `requires-python = ">=3.12"`. `check-deps.ps1` and the README both verify/announce this (see §1.6).

### 1.2 Coding style (summary; full rules in `.cursor/rules/python-coding-style.mdc`)

- **PEP 8**, enforced by **ruff** (lint) + **black** (format). Line length 100.
- **Type hints everywhere** (params + returns). Run **mypy** in CI (non-blocking at first, then blocking).
- Naming: `snake_case` functions/vars, `PascalCase` classes, `UPPER_SNAKE_CASE` constants, modules `snake_case.py`.
- **Docstrings** on every public module, class, and function: one-line summary; add `Args:`/`Returns:`/`Raises:` when not obvious.
- **Comments explain *why*, not *what*.** No comments that restate the code.

### 1.3 Function rules ("small, clear, single-purpose")

- Each function does **one** thing; target **≤ ~30 lines**. If it grows, split it.
- A function name must read as the thing it does (`compute_log_bands`, `draw_waveform`, `open_loopback_stream`).
- No "god functions". The main loop **delegates** to capture, analysis, and the active visualizer.
- Pure functions for DSP (input → output, no side effects) so they are trivially testable.

### 1.4 Code structure (full tree in the layout doc)

Separation of concerns, one responsibility per package:

```
audio/    capture (loopback) + analysis (FFT/RMS) + AnalysisFrame snapshot
visuals/  one file per visual mode; subclass BaseVisualizer + @register (auto-discovered)
ui/       buttons, HUD/status, controls bar
app.py    window, main loop, input handling, mode switching (the "wiring")
config.py constants & defaults (FFT size, fps, colors, smoothing)
main.py   entry point: parse args, configure logging, start App
```

### 1.5 Debugging that actually works

- **`logging`** module, not `print`. A `--debug` flag sets level `DEBUG`; logs go to **console** and a rotating file `logs/app.log`.
- **On-screen debug overlay** toggled with **F3**: FPS, frame time, RMS, peak, active mode, capture device name, dropped/!available frames.
- **`--selftest`** flag: initialize everything, render **N headless frames** with a synthetic tone, then exit `0`. Used by tests/CI and to verify the built `.exe` launches.
- **Fail-soft:** capture errors render an on-screen banner ("No audio / device unavailable") and keep the window alive — never crash to desktop.
- **Crash safety:** install a global `sys.excepthook` that writes the full traceback to `logs/app.log` **before** the process exits, so a hard failure is never silent. The audio stream is always closed in a `finally`/context manager on shutdown.
- **VS Code / Cursor launch config** (debugpy) documented so breakpoints "just work" (see §1.6).

### 1.6 Development environment (Cursor + VS Code)

This project is developed in **Cursor** and **VS Code** (same engine, same config). The repo ships editor config so anyone gets a working setup immediately.

**Python requirement:** **3.12 or later**, 64-bit. The project will not run on 3.11 or earlier.

- **Install Python 3.12+:** download from [python.org/downloads/windows](https://www.python.org/downloads/windows/) (check *"Add python.exe to PATH"*), or `winget install Python.Python.3.12`. Verify with `py -3.12 --version`.
- **`check-deps.ps1`** is the single source of truth at the command line: it checks for Python **≥ 3.12**, prints the exact found version, and if missing/too old prints the **winget command + python.org link** and exits non-zero with clear next steps. The **README** repeats the same install instructions for users who haven't run the script.
- **Recommended editor extensions** (committed in `.vscode/extensions.json` so the editor prompts to install them):
  - `ms-python.python` (Python language support + debugging via debugpy)
  - `charliermarsh.ruff` (lint/format on save)
  - `ms-python.black-formatter` (or ruff-format) as the formatter
  - `ms-python.mypy-type-checker` (optional type checking)
- **`.vscode/settings.json`** (committed): select the `.venv` interpreter, format-on-save with black, ruff as the linter, and `python.testing.pytestEnabled = true` with `SDL_VIDEODRIVER=dummy` in the test env.
- **`.vscode/launch.json`** (committed) debug targets:
  - *Run app* — module `audio_visualizer`, args `--debug`.
  - *Self-test* — module `audio_visualizer`, args `--selftest` (headless).
  - *Pytest* — debug the current test file with the dummy SDL drivers set.

> Cursor reads the same `.vscode/` files, so no Cursor-specific config is required. AI guidance lives in `.cursor/rules/*` and `.cursor/skills/*`.

---

## 2. Language & framework options (for the record)

Chosen: **Python + pygame + numpy + pyaudiowpatch**, packaged with **PyInstaller** to a single `.exe`.

| Option | Capture | Visuals | "Just works" | Verdict |
|--------|---------|---------|--------------|---------|
| **Python — pygame + numpy + pyaudiowpatch** | WASAPI loopback (`pyaudiowpatch`) | pygame 2D | ⭐⭐⭐⭐⭐ | **CHOSEN** — fastest to working, easy debug, easy particles/laser |
| C# .NET 8 — WPF + NAudio + SkiaSharp | NAudio loopback | SkiaSharp | ⭐⭐⭐⭐ | Strong native alt; no WinUI bootstrap pain |
| C# .NET 8 — WinForms + NAudio + SkiaSharp/OpenTK | NAudio loopback | SkiaSharp/OpenGL | ⭐⭐⭐⭐ | Most reliable, plainest UI |
| C# .NET 8 — WinUI 3 + Win2D | NAudio loopback | Win2D | ⭐⭐ | Rejected — bootstrap/runtime failures last time |
| C++ — WASAPI + Direct2D | Raw WASAPI | Direct2D/D3D | ⭐⭐ | Max performance, slow iteration |
| Web/Electron — TS + Web Audio + WebGL | Hard on Windows | WebGL | ⭐⭐ | Capture is the blocker |

---

## 3. UI / UX design

### 3.1 Window & layout

- Resizable window, default **1280×720**, **minimum 640×360**, dark background (`#0A0A12`).
- **Top control bar** (auto-hides in fullscreen): buttons + status text.
- **Main canvas**: the visualization fills the rest of the window.
- **Status line**: capture device, RMS/Peak, FPS, active mode.

### 3.1.1 Display quality, resizing & fullscreen (no blur, no weird layout)

This is a first-class requirement, not a nice-to-have. The rules:

- **Render at the window's real pixel size — never upscale a fixed-size buffer.** We do **not** use pygame's `SCALED` flag for the main canvas (it renders to a fixed logical size and stretches → blur). On `VIDEORESIZE` we recreate the display surface at the new size and redraw natively, so output is always crisp.
- **No hard-coded pixel coordinates.** Every frame, layout (control bar, canvas rect, HUD) and every visualizer derive positions/sizes from the **current surface size** (`surface.get_size()`), via a small `Layout` helper. Resizing just recomputes — nothing clips, stretches, or drifts.
- **DPI awareness on** (see §11.4) so Windows doesn't bitmap-stretch the window on scaled displays (e.g. 150%).
- **Minimum window size** clamps layout so controls never overlap or collapse.
- **Fullscreen is a user choice with two modes:**
  - **Borderless desktop fullscreen** (default): a window at the desktop resolution — instant toggle, no display-mode switch, no flicker, matches native resolution so no scaling artifacts. Toggle with `F11`, exit with `Esc`.
  - **Exclusive fullscreen** (optional, in settings): true mode-switch for users who want it; documented as the non-default path.
- The chosen mode and last window size persist in settings (§11.3); the app restores them next launch.
- **Aspect ratio:** the canvas fills available space; visuals are written resolution-independently, so any aspect ratio looks intentional (no forced letterboxing). Any future fixed-resolution effect buffer must scale with `smoothscale` and is documented as an exception.

### 3.2 Buttons & controls (user interaction)

| Control | Button | Keyboard | Action |
|---------|--------|----------|--------|
| Start/Stop capture | ▶ / ⏹ | `Space` | Toggle loopback capture |
| Previous mode | ‹ | `Left` / `[` | Cycle visual mode back |
| Next mode | › | `Right` / `]` | Cycle visual mode forward |
| Mode picker | **dropdown** (click to choose) | `1`–`9`, `D` to open | Jump to a specific mode (by registry order) |
| Sensitivity | − / + | `-` / `=` | Scale reactivity |
| Smoothing | Smooth − / + | `,` / `.` | Attack/release smoothing |
| Particle size | Size − / + | `F5` / `F6` | Scale particle/flake sizes |
| Animation speed | Speed − / + | `F7` / `F8` | Scale motion (fall/wind/rotation) |
| Color scheme | Classic/Rainbow | `C` | Cycle color scheme |
| Sound source | `Src` (modal) | — | Pick the capture device (default / output loopback / mic) — Phase 0B-a |
| Reduce motion | Motion | `M` | Cap strobing/flash |
| Fullscreen | ⛶ | `F11` | Toggle fullscreen |
| Exit fullscreen | (overlay) | `Esc` | Leave fullscreen |
| Debug overlay | — | `F3` | Toggle FPS/RMS overlay |
| Quit | `Menu` ▸ Quit | `Ctrl+Q` | Exit app (**`Esc` never quits** — it only closes a modal / leaves fullscreen) |

Buttons are a **minimal custom `Button` widget** (clickable rect + label + hover state) — no extra UI dependency, keeps it simple. (`pygame_gui` is a documented future option if richer settings are wanted.)

### 3.3 Visual modes (current registry)

All shipped modes, in registry/cycle order (`order`). Each is one auto-registered
file in `visuals/`; all honor the shared **theme** (size, speed, color scheme) and
**reduce-motion**. This table is the source of truth — keep it in sync when a mode
is added or removed.

| Mode | `key` | order | Description | Driven by | Since |
|------|-------|-------|-------------|-----------|-------|
| **Waveform** | `waveform` | 10 | Oscilloscope line; optional popping **Particles** + **Mirror** | samples + RMS/onset | Phase 1 (merged 10.07) |
| **Waveform Rings** | `waveform_circle` | 16 | **Rings (1·3·6·12)**: 1 = single oscilloscope ring, more = per-band concentric rings; optional shed **Particles** | samples + bands | Phase 6 (merged 10.07) |
| **Spectrum** | `spectrum` | 20 | Log-spaced frequency bars + peak caps; **Mirror** + **Glow** | FFT band energies | Phase 1 |
| **Light Show** | `lightshow` | 30 | Radial beams + shapeable core; **Particles** Off = solid beams, on = bead beams that emit sparks | bands + RMS/onset | Phase 1 (merged 10.07) |
| **Particles** | `particles` | 40 | **Emitter** Field (omnidirectional burst + gravity) or Spiral (per-band arms) | RMS, onset/flux | Phase 2 (merged 10.07) |
| **Laser** | `laser` | 50 | Rotating beams + selectable figure (Lissajous/rose/star/spiral/heart); **Particles** controls emitted sparks | bands + RMS/onset | Phase 2 (merged 10.07) |
| **Snowfall** | `snowfall` | 60 | Colorful flakes; bass blows the wind, mids size them | bands (low + mid) | Phase 3 |
| **Audio Sun** | `radial_spectrum` | 22 | Bars radiating from a pulsing core | FFT band energies | Phase 10.02 |
| **Spectrogram** | `spectrogram` | 25 | Scrolling time-frequency heatmap | FFT band energies | Phase 10.02 |
| **Fireworks** | `fireworks` | 45 | Onset-launched shells that burst into sparks | onset + RMS | Phase 10.02 |
| **Tunnel Warp** | `tunnel` | 75 | Forward-flying ring tunnel | RMS / onset | Phase 10.06 |
| **Plasma** | `plasma` | 80 | Classic sine-field plasma | bands / RMS | Phase 10.06 |
| **Kaleidoscope** | `kaleidoscope` | 90 | Mirrored radial segments | bands | Phase 10.02 |
| **Synthwave Horizon** | `terrain` | 100 | Scrolling wireframe terrain; **Speed** | bands | Phase 10.06 |
| **Vectorscope** | `vectorscope` | 105 | L/R phase scope; **Thickness** + **Mirror** | waveform | Phase 10.06 |
| **VU Meters** | `meters` | 110 | Per-band VU bars; **Glow** | band energies | Phase 10.06 |
| **Dot Matrix** | `matrix` | 115 | Falling glyph columns; **Glow** | bands | Phase 10.06 |
| **Pulse Rings** | `pulse_rings` | 120 | Onset-spawned expanding rings; **Color** + **Thickness** | onset / RMS | Phase 10.06 |
| **Ripples** | `ripples` | 125 | Water-like ripples; **Color** + **Speed** | onset / RMS | Phase 10.06 |
| *Shader-ish field* (stretch) | — | — | Fullscreen palette field reacting to spectrum | FFT texture | Stretch |

> **Phase 10.07** merged the `*_2` "+particles" pairs and the four circle modes into the
> rows above (**26 → 19** registered modes); a shared `PARTICLES_OPTION` axis and per-mode
> **Preset** dropdowns replace the duplicate modes. Per-mode option indices were never
> persisted, so only the saved `mode` key migrates (schema v6→v7).

All modes implement one interface and **auto-register**, so **adding a mode = adding one file** — see §3.5 and the layout doc.

### 3.4 UX principles

- **Immediate feedback**: every control changes the visuals instantly.
- **Reduce motion** toggle: caps strobing/flash intensity (accessibility; no seizure-risk defaults).
- **First-run safety notice**: a one-time, dismissible **photosensitivity/epilepsy warning** before strobing light-show/laser modes (paired with reduce-motion). Acknowledgement stored in settings.
- **"No audio detected" state**: when capture is on but the signal is silent (very common with loopback — see §11), show a calm **idle animation** + hint, never a frozen black screen.
- **Fail-soft banner** instead of a frozen or crashed window.
- **Smoothing** (attack/release) on displayed values so visuals are fluid, not jittery.
- **Shared theme tunables** (live, persisted): **particle/flake size**, **animation speed**, and **color scheme** (classic palette / rainbow / **rainbow+**, the last cycling hue over time via a shared `Theme.color_phase`). The App owns one `Theme` and every active mode reads the same reference, so adjustments apply instantly.
- **Per-mode options** (Phase 5): each mode declares its own discrete-choice tunables via `BaseVisualizer.OPTIONS` (`ModeOption`/`OptionChoice`), surfaced as bottom-row dropdowns rebuilt on mode switch (e.g. snowfall **Fall**/**Wind**/**Density**). Global tunables show their **current value inline** in the control bar.

### 3.5 Visual-mode framework (add `new_mode.py` in one file)

Extensibility is a design goal: dropping in a new mode tomorrow must be trivial and must **not** require editing the app loop, the registry, or other modes.

**The contract (one small interface).** Every mode subclasses `BaseVisualizer` (in `visuals/base.py`) and implements one required method:

```python
from audio_visualizer.visuals.base import BaseVisualizer
from audio_visualizer.visuals.registry import register

@register(key="starfield", display_name="Star Field", order=130)
class StarField(BaseVisualizer):
    """A brand-new visual mode."""

    def draw(self, surface, frame, dt):
        w, h = surface.get_size()          # always size-relative -> resize-safe
        # ... draw using frame.band_energies / frame.rms / frame.waveform_mono ...
```

That's the whole integration. To add a mode:

1. Create **one file** in `visuals/` (e.g. `starfield.py`).
2. Subclass `BaseVisualizer`, decorate the class with `@register(...)`.
3. Done — it's **auto-discovered**, appears in the cycle / `1`–`9` picker, and is selectable by `--mode starfield`. No edits anywhere else.

**Why it stays easy (framework guarantees):**

- **Auto-discovery:** `registry.discover()` imports every non-underscore module in `visuals/` at startup (via `pkgutil.iter_modules`), so the `@register` decorator wires the mode in automatically. There is **no central list to maintain**.
- **Stable, narrow input:** `draw(surface, frame, dt)` receives only the read-only `AnalysisFrame` (+ surface + delta time + a shared `theme`). Modes never touch audio capture, other modes, or global state → no coupling, easy to test in isolation.
- **Sensible defaults:** `BaseVisualizer` provides no-op lifecycle hooks (`on_enter()`, `on_exit()`, `on_resize(size)`) and a `reduce_motion` flag, so a new mode only overrides what it needs (usually just `draw`).
- **Shared drawing helpers** (`visuals/_helpers.py`): reusable glow/lerp/normalized-coordinate utilities so new modes don't reinvent primitives.
- **Ordering & identity:** `order` controls position in the cycle; `key` is the single source of truth for the mode id (used by settings + `--mode`); `display_name` is the label. No magic strings elsewhere.
- **Graceful failure:** if a mode raises while drawing, the app logs it and shows the fail-soft banner / falls back to a safe mode instead of crashing — a broken experimental mode can't take the app down.

This makes the visuals layer a lightweight **plugin surface**: one file in, one file out, zero wiring.

---

## 4. Tooling (make build/run/test/package/deps easy)

All scripts live in `tools/` as **PowerShell `*.ps1` with `*.cmd` wrappers**, every script supports **`-Help`**, prints a friendly banner, and ends with **"next steps"**. A shared `tools/_Common.ps1` holds banner/next-step helpers.

| Script | Purpose |
|--------|---------|
| `check-deps.ps1` | Verify **Python ≥ 3.12** (print found version; if missing/old, print the `winget`/python.org install command and exit non-zero), that `.venv` exists, required packages import, and an output audio device is present. |
| `setup.ps1` | Create **`.venv`** (with Python 3.12), upgrade pip, `pip install -r requirements.txt` (+ `requirements-dev.txt`), and install the **pre-commit** hook. |
| `run.ps1` | Activate venv and run the app (`python -m audio_visualizer`); passes through `--debug`, etc. |
| `test.ps1` | Run **pytest** (headless: sets `SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy`). |
| `lint.ps1` | Run **ruff** + **black --check** (+ optional **mypy**). |
| `format.ps1` | Apply **black** + `ruff --fix`. |
| `build-exe.ps1` | **PyInstaller** → `dist/AudioVisualizer.exe` (one-file by default; `-OneDir` option). |

**Code quality automation:** a committed **`.pre-commit-config.yaml`** runs **ruff** + **black** on commit so style never rots; `setup.ps1` installs it. CI also runs `lint.ps1` as a backstop.

**Build to a single `.exe` (chosen distribution):**

- `pyinstaller --onefile --name AudioVisualizer --noconsole src/audio_visualizer/__main__.py` (exact spec captured in `build-exe.ps1` and an `AudioVisualizer.spec`).
- **Bundle the PortAudio DLL** that `pyaudiowpatch` ships — this is the #1 packaging gotcha. The `.spec` uses `collect_dynamic_libs("pyaudiowpatch")` (and adds `pyaudiowpatch` to `hiddenimports` if needed). Always confirm with `--selftest` after building.
- **Set an app icon + version info** (`--icon`, version resource) and keep a single version string in `config.py` (`APP_VERSION`) surfaced in the HUD and `--version`.
- **Antivirus:** `--onefile` can trip false positives and starts slower (it unpacks to a temp dir). `-OneDir` is the documented fallback.
- **Build the exe early, not at the end.** Run `build-exe.ps1` + `dist\AudioVisualizer.exe --selftest` once during **Phase 1** to prove packaging works, then keep it green — don't discover DLL/bundling problems in Phase 3.

**Future tooling ideas:** interactive `tools/dev.ps1` menu (`[1] setup [2] run [3] test [4] build`), `--log <path>` tee for bug reports, GitHub Actions workflow calling `test.ps1` + uploading the exe artifact.

---

## 5. Testing & "prove it works"

Layered so we can trust the code **without** needing a real sound card in CI.

| Layer | What it verifies | How |
|-------|------------------|-----|
| **DSP unit** | FFT puts a pure sine's energy in the expected log band; silence → ~0; RMS/peak math | pytest, synthetic numpy signals |
| **Frame/contract** | `AnalysisFrame` immutability & shapes; log-band mapping | pytest |
| **UI logic** | Button hit-testing, mode cycling wraps correctly | pytest (no display needed) |
| **Headless smoke** | App **constructs and renders N frames without crashing** | pytest with `SDL_VIDEODRIVER=dummy`, synthetic audio source |
| **Built-exe selftest** | The packaged `.exe` actually launches | run `AudioVisualizer.exe --selftest` → exit 0 |
| **Manual** | Real loopback + visuals + fullscreen + device switch | checklist in `plan/testing.md` |

**Key enabler:** an **audio source interface** with two implementations — `LoopbackSource` (real) and `SyntheticSource` (generated tone). Tests/CI inject `SyntheticSource`, so "does the window run and react?" is verifiable headlessly.

**CI outline:** GitHub Actions `windows-latest` → setup Python → `setup.ps1` → `lint.ps1` → `test.ps1` (dummy SDL drivers). Optional: `build-exe.ps1` then run `--selftest`, upload artifact.

Full details and the manual checklist: `plan/testing.md`.

---

## 6. Documentation & layout (so the next agent can continue)

- **This plan** = product + decisions + the 7 requirements.
- **`plan/repository-and-code-layout.md`** = exact folder tree, each module's responsibility, and a **module relationship diagram**.
- **`plan/testing.md`** = test strategy, commands, manual checklist, CI.
- **`.cursor/rules/*.mdc`** = always-applied conventions (project + style).
- **`.cursor/skills/audio-visualizer/SKILL.md`** = step-by-step implementation checklist + pointers.
- A **Decisions log** (§8 below) records choices so they aren't re-litigated.

Whenever code is added or a decision changes, update the relevant doc in the same change.

---

## 7. Phased roadmap (each phase ends with something that runs)

> Short summary below — the **detailed per-phase build guide** (scope, tests, exit criteria, time estimates, future work) lives in **`plan/development-phases.md`**.

- **Phase 0 — Skeleton (runs, no audio):** project layout, `App` window opens, control bar + buttons draw, `--selftest` works, CI green. *Simple, visibly working.*
- **Phase 0.5 — Capture spike (de-risk the #1 risk):** a tiny throwaway script (`tools/spike-loopback.py`) opens `pyaudiowpatch` loopback and prints **RMS for ~5 s** while audio plays. Goal: **prove the platform actually delivers samples on the target machine before building anything on top of it** (this is exactly where past attempts died). Record the device's native sample rate / channels / dtype observed here — it feeds §11. Throwaway code; delete or fold into `capture.py`.
- **Phase 1 — MVP capture + 3 modes:** `LoopbackSource` via `pyaudiowpatch`, `analysis.py` (FFT/RMS/bands), **Waveform + Spectrum + Light Show**, status line, fullscreen. Unit + smoke tests pass. **Also: package once** (`build-exe.ps1` → `dist\AudioVisualizer.exe --selftest` exits 0) to validate PyInstaller + PortAudio DLL bundling early.
- **Phase 2 — Particles & Laser:** particle system + laser mode, onset/energy reactivity, sensitivity & smoothing controls, reduce-motion.
- **Phase 3 — Polish & ship:** settings persistence (JSON, §11.3), first-run safety notice, device-change handling, `build-exe.ps1` single-exe with icon/version, selftest on the exe, `LICENSE` + `THIRD-PARTY-NOTICES.md` (§12), README/quickstart.
- **Phase 4 — Tunables & UX:** shared `Theme` (particle **size**, animation **speed**, **color scheme** incl. rainbow) applied live across modes and persisted; **mode-picker dropdown**; new **Waveform 2** mode (waveform + popping particles). 8 modes total.
- **Phase 5 — Per-mode options & color picker:** per-mode option dropdowns (`BaseVisualizer.OPTIONS`); snowfall **Fall**/**Wind**/**Density** split; **inline value chips**; **color dropdown** with time-animated **Rainbow+**.
- **Phase 6 — Circular waveforms & polish:** **continuous Rainbow+** (seamless hue wrap); **debounced 5 s** "no audio" banner that never auto-quits; Particles Spiral **Size**/**Spacing**; four **circular waveform** modes (single / +particles / multi-ring / multi-ring +particles). **12 modes** total.
- **Phase 7 — Docs & maintainability (no behavior change):** new `architecture-and-code-flow.md` (runtime flows + framework diagrams); magic numbers replaced by named constants under a documented two-tier policy; `_range_energies` deduped into `_helpers.range_energies`; docstrings/cleanups. Formatting stays black/ruff.
- **Phase 8 — Light Show 2, Laser 2 & particle trails:** `lightshow_2` (beams of pulsing particles + shapeable Disc/Hollow/Waveform/Burst core + emitted sparks) and `laser_2` (selectable Lissajous/rose/star/spiral/heart figure + emitting beams). Shared `SparkField` + **Trail** option (fading "shadow" trails) in `_helpers.py`. **14 modes total.**
- **Phase 9 — RenK logo overlay, About dialog & ESC fix:** a global, audio-reactive **RenK logo** drawn over every mode (`visuals/logo.py`, NOT a mode) — circling spin, energy pulse, optional beat emit; configurable + persisted (Show, Default↔Rainbow+ color, transparency, size, center/corner position, emit) via the `RenK` modal. New **About** modal (owner/license/version/build date). **ESC no longer quits** (closes modal / leaves fullscreen). Logo art bundled via `resources.py`.

---

## 8. Decisions log

| # | Decision | Why |
|---|----------|-----|
| 1 | **Python 3.12+** (3.12 or newer, 64-bit) | Reliable loopback + fast iteration + easy debug; one supported runtime |
| 2 | **pygame** for UI/rendering | Simplest path to 2D visuals & custom buttons |
| 3 | **numpy** for DSP | Correct, fast FFT in a few lines |
| 4 | **pyaudiowpatch** for capture | Maintained WASAPI **loopback** support |
| 5 | **PyInstaller `--onefile`** | Single `.exe` to share (chosen distribution) |
| 6 | **ruff + black** | One enforced style, low friction |
| 7 | **Audio source interface** (Loopback vs Synthetic) | Makes the app testable headlessly in CI |
| 8 | **`--selftest` + dummy SDL drivers** | Prove the window/app runs without hardware/display |
| 9 | **Cursor + VS Code** as the dev environment, config committed in `.vscode/` | One shared, reproducible setup; Cursor reuses VS Code config |
| 10 | **Settings as JSON in `%APPDATA%\AudioVisualizer\settings.json`** with `schema_version` | User-writable location (works for an installed exe), forward-compatible |
| 11 | **pre-commit (ruff + black)** + pinned deps + `.python-version` | Reproducible, style never rots |
| 12 | **Capture spike (Phase 0.5) before UI**; build exe in Phase 1 | De-risk the two things that historically break late |
| 13 | **Render at native window size; no `SCALED`/upscaled buffer.** Borderless desktop fullscreen by default | Crisp output on resize/fullscreen/high-DPI; instant toggle (§3.1.1) |
| 14 | **Visual modes auto-register via `@register` + `discover()`** (one file, no central list) | Frictionless extension (one new file, e.g. `new_mode.py`) with zero coupling (§3.5) |
| 15 | **Git flow + `PP.FF.BB` versioning + annotated per-phase tags** (`v<APP_VERSION>`, e.g. `v00.02.00`); feature branches → PR into a green `main` | Predictable history that maps 1:1 to the phased roadmap and the in-app version. Full convention in `plan/git-and-versioning.md` |
| 16 | **Shared `Theme` (size / speed / color scheme)** passed live to every mode + a **mode-picker dropdown** | One small, persisted tunable surface that applies instantly across modes; dropdown scales past the `1`–`9` keys as modes grow (Phase 4) |
| 17 | **Per-mode options** via `BaseVisualizer.OPTIONS` (discrete `ModeOption` choices) rendered as dropdowns; **inline value chips**; **color dropdown** with time-animated **rainbow+** (`Theme.color_phase`) | Each mode keeps its own knobs without a central list (still one file per mode); showing values makes Sensitivity/Smoothing/etc. self-explanatory; rainbow+ animates color over time per request (Phase 5) |
| 18 | **Rainbow+ wraps hue before clamping** (`t % 1.0`); **idle banner debounced 5 s** and **never auto-quits**; **circular waveform** modes share `ring_points`/`draw_ring`/`RingPops` in `_helpers.py` | Pre-clamp modulo was sticking the sweep at red (discontinuous); brief track gaps shouldn't flash the banner and silence must not close the app; circular modes reuse shared helpers so each is still one small file (Phase 6) |
| 19 | **Two-tier magic-number policy** (shared/cross-mode tunables `UPPER_SNAKE_CASE` in `config.py`; mode-local "feel" numbers as commented `_UPPER_SNAKE` module constants) + new **`architecture-and-code-flow.md`**; **kept black/ruff** and **declined the space-inside-brackets** style | Removes unexplained literals while keeping tunables both discoverable *and* close to use; the locked formatter (black/ruff-format) strips inside-bracket spacing (E201/E211) and no mainstream formatter supports it, so honoring the request would break pre-commit/CI (Phase 7) |
| 20 | **Reusable `SparkField` + shared `TRAIL_OPTION`** in `_helpers.py` power the new beam modes' emitted particles and the optional fading "shadow" trail | One particle system (normalized space, optional trail) keeps the `lightshow`/`laser` beam modes thin and lets any future mode opt into emitted particles + trails without duplicating logic (Phase 8; the standalone `*_2` files were later merged into the base modes — D23) |
| 21 | **RenK logo is a global overlay (`visuals/logo.py`), drawn by `app.py` over every mode — not a `@register`ed mode** — composited **additively**; configurable + persisted (`logo_*`, schema v2) via a `RenK` modal; bundled asset loaded through `resources.py` | Branding must appear in **all** modes without touching each one or the discovery list; additive blend makes neon-on-black art glow with no bounding box; a luminance tint gives Default↔Rainbow+ from one asset; `resources.py` + spec `datas` make the PNG resolve in dev and the frozen exe (Phase 9) |
| 22 | **`Esc` no longer quits** — it only closes a modal or exits fullscreen; quit stays on the `Quit` button + `Ctrl+Q` | Accidental `Esc` quitting was hostile; modal/fullscreen dismissal is the expected behavior (Phase 9) |
| 23 | **Mode consolidation (26 → 19)**: merged the `*_2` "+particles" pairs and the four circle modes into their base modes behind a shared `PARTICLES_OPTION` axis + a `Rings` count; added per-mode **`PRESETS`** (handled in `BaseVisualizer.on_option_change`/`_apply_preset`) and retrofitted shared **Mirror**/**Glow**. Since per-mode option indices are never persisted, only the saved `mode` key migrates via `MERGED_MODE_KEYS` (schema v6→v7) | Many modes differed only by "+ particles" or ring count, cluttering the picker; folding them into options (with one-click presets for the old looks) is more flexible and removes ~7 near-duplicate files, while the key-only migration keeps upgrades crash-free (Phase 10.07) |

**Open questions** (record answers as they're decided):

1. ~~Settings storage format/location?~~ **Decided (D10):** JSON at `%APPDATA%\AudioVisualizer\settings.json` with `schema_version`.
2. Default FFT size / hop / band count (start 2048 / 50% / 48 bands; tune by feel)?
3. ~~Add `pygame_gui`?~~ **Decided:** keep the minimal custom `Button` widget for now; revisit only if a rich settings panel is needed.
4. Beat detection algorithm for particles (spectral flux threshold to start)?
5. Onset detection sensitivity defaults and per-mode reactivity scaling?
6. Fullscreen default — confirm **borderless desktop** is preferred over exclusive (current decision D13)?

---

## 9. Risks & honest constraints

- **Loopback returns silence/no data when nothing plays** — the most common "it's broken" report. Handle with an explicit idle state (§11.1), not a frozen screen.
- **Device format varies** (44.1 vs 48 kHz, stereo, float32/int16). Negotiate and downmix to mono float32 (§11.2) or the FFT math is silently wrong.
- **High-DPI Windows scaling** can make pygame render blurry or mis-sized — set DPI awareness and handle resize (§11.4).
- **DRM/protected audio** may not be loopback-captured — degrade gracefully (silence/banner), never promise bypass.
- **Exclusive-mode** apps can hold the device — handle open failure and retry.
- **PyInstaller + antivirus**: `--onefile` can trip false positives and start slower; `-OneDir` is the fallback. Bundling the **PortAudio DLL** is mandatory (§4, §11.5).
- **Performance**: keep capture light; run FFT off the audio callback; honor the budget in §11.6; profile on a laptop iGPU.

---

## 10. Success criteria

- Window opens and shows audio-reactive motion within seconds of **Start capture**; shows a clear idle state when audio is silent.
- Switching modes, fullscreen, and sensitivity all respond instantly.
- **Display stays crisp and correctly laid out** when resizing, toggling fullscreen, and on a scaled (150%) display — no blur, clipping, or stretching.
- `test.ps1` is green; `AudioVisualizer.exe --selftest` exits `0`; the **demo/acceptance check** (known audio file → expected visible reaction, see `plan/testing.md`) passes.
- `check-deps.ps1` correctly flags a non-3.12 environment with actionable install steps.
- A new contributor can add a new visual mode by creating **one file** in `visuals/` (subclass + `@register`) with **no other edits** — it auto-appears in the app.

---

## 11. Audio capture & platform details (must-handle gotchas)

These are the things that quietly break a "simple but works" audio app. Decide them up front.

### 11.1 Silence / no-data behavior

WASAPI loopback frequently delivers **silence — or no callback at all — when nothing is playing**. Treat this as a first-class state:

- `read_latest()` returning `None`/all-zeros for a short window ⇒ **"No audio detected"** idle state with a gentle idle animation and a hint ("play some audio").
- Distinguish *idle* (capture running, signal silent) from *error* (device unavailable). Both keep the window alive; only error shows the red banner.
- Don't let the FFT path divide-by-zero or NaN on pure silence — clamp/guard.

### 11.2 Device format negotiation & mono downmix

- Read the **default render device's native format** from `pyaudiowpatch` (sample rate, channels, dtype) instead of assuming 48 kHz stereo.
- **Downmix to mono** (average channels) and **normalize to float32 in `-1..1`** before analysis. `int16` input ⇒ divide by 32768.
- Carry the real `sample_rate` into `AnalysisFrame` so log-band frequency mapping is correct.

### 11.3 Settings persistence (decided)

- Location: `%APPDATA%\AudioVisualizer\settings.json` (created on first write).
- Include a top-level `schema_version` (int; currently **7** — `config.SETTINGS_SCHEMA_VERSION`). On load, migrate or fall back to defaults if the version is unknown — never crash on a bad/old settings file.
- Persisted: active mode, sensitivity, smoothing, reduce-motion, fullscreen pref, window size, first-run-notice acknowledged, size/speed scale, color scheme, **appearance** (UI style / accent / font), **background** (mode / sensitivity / opacity / height), and **RenK logo** prefs (show / color / transparency / size / position / spin / emit).
- **Migration:** v00.0A.07 remaps deprecated mode keys to their survivor via `config.MERGED_MODE_KEYS` (e.g. `waveform_2` → `waveform`). Per-mode option/preset indices are **not** persisted.
- **Selectable source (v8, Phase 0B-a):** `source_id` (`""` ⇒ default render-device loopback; otherwise a device *name*). A missing device falls back to the default loopback on load.

### 11.4 High-DPI & window resize (Windows)

- Set **DPI awareness** at startup (e.g. `ctypes.windll.shcore.SetProcessDpiAwareness(2)` on Windows, guarded for non-Windows/headless) so the window isn't blurry on scaled displays.
- Create the window **resizable**; on `VIDEORESIZE` recreate the display surface at the **new pixel size** and recompute layout. **Render natively at that size — never draw to a fixed surface and upscale** (would blur). See the full contract in §3.1.1.
- Never hard-code pixel positions that assume 1280×720; everything derives from the current surface size.

### 11.5 Packaging specifics (PyInstaller)

- Bundle the **PortAudio DLL** via `collect_dynamic_libs("pyaudiowpatch")`; add hidden imports if a clean build fails to import.
- Ship **icon + version info**; single `APP_VERSION` in `config.py`.
- Validate every build with `dist\AudioVisualizer.exe --selftest` (done early per Phase 1).

### 11.6 Performance budget (concrete targets)

- **Capture callback:** copy only, allocation-free, < ~0.5 ms.
- **Analysis:** ~60 Hz, FFT size 2048, 50% hop — runs on the main loop unless profiling says otherwise.
- **Render:** cap at **60 FPS** (`clock.tick(60)`), use real `dt`. If render outruns new analysis frames, **interpolate** visual state rather than stutter.
- Target steady 60 FPS on a laptop iGPU at 1280×720; profile before adding GPU-heavy effects.

---

## 11.7 Planned next features (design parked)

Detailed, agreed-but-unbuilt designs live in **`plan/phase-0b-candidates.md`** (targeting
**`v00.0B.00`**): a **selectable sound source** (any render-endpoint loopback or input/mic;
default unchanged), **user custom visual presets** (save/name/load), and a
**randomize/auto-cycle** across a chosen set with smooth cross-fades on a user-set interval.

---

## 12. Licensing & distribution notices

Because we ship a binary, third-party licenses must travel with it:

- Add a project **`LICENSE`** (choose one; MIT is a fine default for a hobby app).
- Add **`THIRD-PARTY-NOTICES.md`** listing the runtime deps and their licenses: **pygame (LGPL)**, **numpy (BSD)**, **pyaudiowpatch (MIT)** and the bundled **PortAudio (MIT-style)**. Note pygame's LGPL obligations (we use it unmodified, dynamically — keep the notice + a link to source).
- The README links both. CI/`build-exe.ps1` can copy `THIRD-PARTY-NOTICES.md` next to the exe for `-OneDir` builds.
