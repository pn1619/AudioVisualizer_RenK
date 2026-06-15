# Repository & Code Layout

Companion to `plan/audio-visualizer-plan.md`. Defines the **exact folder tree**, **each module's job**, and **how the pieces connect**. Keep this file in sync with the code. For the detailed *runtime* flow (per-frame loop, threading, frameworks, diagrams) see **`plan/architecture-and-code-flow.md`**.

> Principle: clear boundaries, small files, one responsibility each. Adding a visual mode should mean **adding one file**, not editing five.

---

## 1. Folder tree

```
AudioVisualizer/
├─ src/
│  └─ audio_visualizer/
│     ├─ __init__.py
│     ├─ __main__.py            # enables `python -m audio_visualizer`; calls main()
│     ├─ main.py                # parse args, configure logging, install excepthook, build & run App
│     ├─ app.py                 # App: window, main loop, input, mode switching (wiring only)
│     ├─ config.py              # constants & defaults (APP_VERSION, FFT size, FPS, colors, smoothing keys)
│     ├─ settings.py            # load/save JSON settings in %APPDATA% (schema_version, migrate-or-default)
│     ├─ platform_win.py        # DPI awareness + Windows-specific shims (guarded, no-op off Windows)
│     │
│     ├─ audio/
│     │  ├─ __init__.py
│     │  ├─ frame.py            # AnalysisFrame dataclass (immutable snapshot)
│     │  ├─ source.py           # AudioSource interface + SyntheticSource (test tone)
│     │  ├─ capture.py          # LoopbackSource: WASAPI loopback via pyaudiowpatch + ring buffer
│     │  └─ analysis.py         # Analyzer: window + FFT + RMS/peak + log bands -> AnalysisFrame
│     │
│     ├─ visuals/
│     │  ├─ __init__.py
│     │  ├─ base.py             # BaseVisualizer + lifecycle hooks; Theme + ModeOption/OptionChoice (per-mode options)
│     │  ├─ registry.py         # @register decorator + discover() auto-import; ordered mode list
│     │  ├─ _helpers.py         # shared draw utils (color lerp, ring_points/draw_ring, RingPops); skipped by discovery
│     │  ├─ waveform.py         # @register("waveform", ...)
│     │  ├─ spectrum.py         # @register("spectrum", ...)
│     │  ├─ lightshow.py        # @register("lightshow", ...)
│     │  ├─ lightshow_2.py      # Phase 8 (beams of pulsing particles + shapeable core + emit)
│     │  ├─ laser_2.py          # Phase 8 (selectable figure: Lissajous/rose/star/spiral/heart + emit)
│     │  ├─ waveform_2.py       # Phase 4 (waveform + popping particles)
│     │  ├─ waveform_circle.py            # Phase 6 (oscilloscope ring)
│     │  ├─ waveform_circle_2.py          # Phase 6 (ring + popping particles)
│     │  ├─ waveform_circle_multiple.py   # Phase 6 (N per-band concentric rings)
│     │  ├─ waveform_circle_multiple_2.py # Phase 6 (multi-ring + particles)
│     │  ├─ particles.py        # Phase 2
│     │  ├─ laser.py            # Phase 2
│     │  ├─ snowfall.py         # Phase 3 (bass wind, mid-band flake size)
│     │  └─ particles_spiral.py # Phase 3 (per-band spiral arms; Phase 6 size/spacing)
│     │      # add a mode = drop one new file here (subclass + @register); no other edits
│     │
│     └─ ui/
│        ├─ __init__.py
│        ├─ layout.py           # Layout: computes control-bar/canvas/HUD rects from current surface size
│        ├─ button.py           # minimal clickable Button (rect + label + hover)
│        ├─ chip.py             # read-only value Chip (shows current Sens/Smooth/Size/Speed)
│        ├─ dropdown.py         # minimal Dropdown widget (mode/color/per-mode options; optional title)
│        ├─ controls.py         # two-row control bar: buttons + chips + color/option dropdowns
│        └─ hud.py              # status line + debug overlay (F3)
│
├─ tests/                       # headless (SDL dummy drivers); see plan/testing.md
│  ├─ conftest.py               # shared fixtures + headless env setup
│  ├─ test_analysis.py          # FFT/RMS/bands on synthetic signals
│  ├─ test_onset.py             # spectral-flux onset triggering
│  ├─ test_frame.py             # AnalysisFrame shape/immutability
│  ├─ test_source.py            # int16/float32 + stereo→mono; SyntheticSource
│  ├─ test_registry.py          # discover()/ordering/auto-register a drop-in
│  ├─ test_visuals.py           # every mode draws at many sizes + frame=None
│  ├─ test_particles.py         # deterministic particle update under a seed
│  ├─ test_dropdown.py          # dropdown open/select/click-outside
│  ├─ test_ui_logic.py          # button hit-test, mode cycling wrap
│  ├─ test_settings.py          # round-trip + corrupt/old schema → defaults
│  ├─ test_visuals_phase{3,4,5,6}.py  # per-phase visual/option/color coverage
│  └─ test_smoke.py             # headless App build + N ticks (incl. idle/resize)
│
├─ tools/
│  ├─ _Common.ps1               # shared banner / next-steps helpers (dot-sourced)
│  ├─ check-deps.ps1  / .cmd    # verifies Python >= 3.12 (prints install steps if not)
│  ├─ setup.ps1       / .cmd    # .venv + pip + install pre-commit hook
│  ├─ run.ps1         / .cmd
│  ├─ test.ps1        / .cmd
│  ├─ lint.ps1        / .cmd
│  ├─ format.ps1      / .cmd
│  ├─ build-exe.ps1   / .cmd
│  ├─ spike-loopback.py         # Phase 0.5 throwaway: prove pyaudiowpatch delivers samples
│  └─ README.md
│
├─ .vscode/                     # shared editor config (used by Cursor too)
│  ├─ extensions.json           # recommended: python, ruff, black, mypy
│  ├─ settings.json             # .venv interpreter, format-on-save, pytest headless
│  └─ launch.json               # Run app / Self-test / Pytest debug targets
│
├─ .github/
│  └─ workflows/
│     └─ ci.yml                 # CI: setup, check-deps, lint, test, build-exe + selftest, upload artifact
├─ logs/                        # rotating app.log (gitignored)
├─ dist/                        # PyInstaller output (gitignored)
├─ build/                       # PyInstaller temp (gitignored)
├─ AudioVisualizer.spec         # PyInstaller spec (committed; bundles PortAudio DLL + icon/version)
├─ .python-version              # pins 3.12 for pyenv/tooling
├─ requirements.txt             # runtime deps (pinned exact versions; Windows-only)
├─ requirements-dev.txt         # ruff, black, mypy, pytest, pre-commit, pyinstaller
├─ pyproject.toml               # requires-python >=3.12; ruff/black/mypy config + metadata
├─ .pre-commit-config.yaml      # ruff + black on commit
├─ LICENSE                      # project license (e.g. MIT)
├─ THIRD-PARTY-NOTICES.md       # pygame (LGPL), numpy, pyaudiowpatch, PortAudio notices
├─ .gitignore
└─ README.md                    # quickstart + Python 3.12 install steps; points at plan/ and tools/
```

---

## 2. Module responsibilities (one job each)

### `main.py` / `__main__.py`
Entry point. Parse CLI args (`--debug`, `--mode`, `--selftest`, `--device`, `--version`), configure `logging`, **install a global `sys.excepthook`** that logs the traceback to `logs/app.log` before exit, set DPI awareness via `platform_win`, construct `App`, run it. No business logic.

### `config.py`
Plain constants and defaults only (no logic): `APP_VERSION`, `SAMPLE_RATE_FALLBACK`, `FFT_SIZE`, `HOP`, `BAND_COUNT`, `MIN_HZ`, `MAX_HZ`, `TARGET_FPS`, color palette, smoothing factors, sensitivity range, window size, and the **shared visual tunables** (theme ranges, particle/snow caps, `REDUCE_MOTION_BURST_DIVISOR`, `IDLE_LINE_HUE`, circle-layout fractions, …). **Magic-number policy:** shared/cross-mode tunables live here as `UPPER_SNAKE_CASE`; mode-local "feel" numbers live as commented `_UPPER_SNAKE` constants atop their mode file. **Mode keys do *not* live here** — they're declared on each class via `@register(key=...)` (the registry is the single source of truth).

### `settings.py`
Load/save user settings as JSON at `%APPDATA%\AudioVisualizer\settings.json`. Includes `schema_version`; on load, **migrate or fall back to defaults** for unknown/corrupt files (never crash). Persists active mode, sensitivity, smoothing, reduce-motion, fullscreen pref, and first-run-notice acknowledgement.

### `platform_win.py`
Windows-specific shims, each **guarded** so the module imports cleanly off Windows / in CI: set process **DPI awareness**, `%APPDATA%` path resolution. No pygame, no app logic.

### `audio/frame.py`
`AnalysisFrame` — a frozen dataclass snapshot passed to visualizers:
`waveform_mono: np.ndarray`, `band_energies: np.ndarray` (0..1), `rms: float`, `peak: float`, `sample_rate: int`, `timestamp: float`. Immutable so it can cross threads safely.

### `audio/source.py`
`AudioSource` interface: `start()`, `stop()`, `read_latest() -> np.ndarray | None`, `is_running`, `device_name`. `SyntheticSource` generates a configurable sine/sweep for tests, CI, and `--selftest`.

### `audio/capture.py`
`LoopbackSource(AudioSource)` — opens the **default WASAPI loopback** device with `pyaudiowpatch`. **Negotiates the device's native format** (sample rate, channels, dtype), then runs a **callback** that **downmixes to mono float32 `-1..1`** and copies into a **bounded ring buffer** (allocation-light, never blocks). Exposes the real `sample_rate`. Handles device-not-found / open failure by surfacing an error state (no crash); reports an **idle (silent) vs error** distinction so the UI can show the right state.

### `audio/analysis.py`
`Analyzer` — pure DSP: apply **Hann window**, **numpy rfft**, magnitude → **log-spaced bands** (using the frame's real `sample_rate`), compute **RMS** and **peak**, normalize/smooth, return an `AnalysisFrame`. **Guards against silence** (no NaN/divide-by-zero on all-zero input). No pygame, no I/O → fully unit-testable.

### `visuals/base.py`
`BaseVisualizer` — the one interface every mode subclasses. Required: `draw(surface, frame: AnalysisFrame | None, dt: float)`. Provided defaults (override only if needed): `on_enter()`, `on_exit()`, `on_resize(size)`, a `reduce_motion` flag, and the shared `theme`. Class attributes `KEY`, `DISPLAY_NAME`, `ORDER` are set by the `@register` decorator. **Per-mode options:** a mode declares `OPTIONS: tuple[ModeOption, ...]` (each a labelled set of `OptionChoice`s) and reads the current value via `self.option(key)`; the App renders these as dropdowns and calls `set_option_index`. Also defined here: the `Theme` dataclass (`size_scale`, `speed_scale`, `color_scheme`, `color_phase`). Visualizers hold **only their own animation state**, read **size from the surface** (resize-safe), and never touch audio capture, other modes, or global state.

### `visuals/registry.py`
The plugin mechanism — **no central list to maintain**:
- `@register(key, display_name=None, order=100)` — class decorator that records a mode.
- `discover()` — imports every non-underscore module in the `visuals/` package (`pkgutil.iter_modules`) at startup, triggering the decorators. Skips `base`, `registry`, and `_*` helpers.
- `available()` — returns modes ordered by `ORDER` then `KEY`; `create(key)` instantiates one.
`App` calls `discover()` once, then cycles/selects by key. **Adding a mode = add one file; the registry needs no edit.**

### `visuals/_helpers.py`
Shared, reusable drawing utilities so new modes don't reinvent primitives: color helpers (`lerp_color`, `palette_color`, `scale_color`, `rainbow_color` — which wraps hue with `t % 1.0` so Rainbow+ is continuous, `themed_color(scheme, t, palette, phase)`), the spectrum-slicing helper `range_energies(bands, slices)` (shared by the multi-ring modes), the circular-waveform helpers `ring_points`, `draw_ring`, and the reusable `RingPops` pop-particle field, plus the reusable `SparkField` (free particles in normalized space with an optional fading "shadow" trail) and the shared `TRAIL_OPTION` (used by `lightshow_2`/`laser_2`). Leading underscore → **skipped by `discover()`**.

### `visuals/*.py` (the modes)
Each mode = **one file**: subclass `BaseVisualizer`, decorate with `@register`, implement `draw`. `waveform` draws the mono line; `spectrum` draws log bars + peak caps; `lightshow` draws radial beams + bloom; `particles` and `laser` are Phase 2. A mode that raises during `draw` is caught by `App` (logged + fail-soft), never crashing the app.

### `ui/layout.py`
`Layout` — computes the control-bar, main-canvas, and HUD rectangles from the **current surface size** every frame (with the minimum-size clamp). Single place that owns positioning, so resizing/fullscreen never produces clipping or stretching and no module hard-codes pixel coordinates.

### `ui/button.py`
`Button` — rect, label, hover/press state, `handle_event(event) -> bool`, `draw(surface)`. No external UI lib.

### `ui/chip.py`
`Chip` — a non-interactive labelled value box; the control bar uses these to show the current Sensitivity/Smoothing/Size/Speed values.

### `ui/dropdown.py`
`Dropdown` — header + expandable option list; optional `title` prefixes the current label (e.g. `Fall: Normal`). Used for the mode picker, color scheme, and per-mode options.

### `ui/controls.py`
Builds and lays out the **two-row** control bar (global controls + value chips on top; color and per-mode option dropdowns on the bottom); translates clicks into `App` actions (start/stop, mode, sensitivity/smoothing/size/speed, color, per-mode option changes, fullscreen). `set_mode_options(specs)` rebuilds the per-mode dropdowns when the active mode changes; only one dropdown stays open at a time.

### `ui/hud.py`
Status line (device, RMS/peak, FPS, mode) and the **F3 debug overlay**.

### `app.py`
The **wiring**: owns the pygame window, the `AudioSource`, the `Analyzer`, the active `Visualizer`, the `settings`, the `Layout`, and the UI. On startup calls `registry.discover()`. Runs the main loop: pump events → pull latest samples → analyze → draw active visual → draw UI → flip, capped at `TARGET_FPS` with real `dt`. Handles keyboard shortcuts, **window resize (`VIDEORESIZE`) → recreate surface at new size + recompute layout** (native render, no upscale), **fullscreen toggle** (borderless desktop default), idle/error states, first-run notice, and `--selftest`. Wraps each `Visualizer.draw` so a misbehaving mode is logged and fail-soft, not fatal. Closes the audio stream in a `finally` on exit.

---

## 3. Data & control flow

```
                 (background callback thread)
 ┌──────────────┐   raw PCM    ┌───────────────┐
 │ LoopbackSource│ ───────────►│  ring buffer   │
 │ (pyaudiowpatch)│             └──────┬────────┘
 └──────────────┘                     │ read_latest()
        ▲ (or SyntheticSource in tests)│
        │                              ▼
        │                       ┌───────────────┐
        │                       │   Analyzer     │  Hann + rfft + RMS/peak + log bands
        │                       └──────┬────────┘
        │                              │ AnalysisFrame (immutable)
        │                              ▼
 ┌──────┴───────────────────────────────────────────────┐
 │ App (main loop, main thread)                          │
 │   events → update → draw                              │
 │     ├─ active Visualizer.draw(surface, frame, dt)     │
 │     └─ ui (controls bar + hud/debug overlay)          │
 └───────────────────────────────────────────────────────┘
```

- **One producer (audio callback), one consumer (main loop).** The ring buffer is the only shared state; keep the callback tiny and allocation-free.
- **Analysis runs on the main loop** pulling the latest samples (simple, deterministic). If profiling shows cost, move it to a worker thread later — the `AudioSource`/`AnalysisFrame` boundary already allows it.

---

## 4. Naming & macros

- **Visual-mode keys** are declared **once** on the mode class via `@register(key=...)` (single source of truth, referenced through the registry — not a scattered magic string). This is what makes "add a mode = one file" true (no `config.py` edit needed per mode).
- **Other tunable parameter names** (FFT size, sensitivity, smoothing, colors, FPS) remain **`UPPER_SNAKE_CASE` constants in `config.py`** — never scatter magic numbers/strings (e.g. `FFT_SIZE`, `SENSITIVITY_STEP`). *Mode-local* feel numbers may instead be commented `_UPPER_SNAKE` constants at the top of that mode's file (see the magic-number policy in `config.py` and the coding-style rule).
- Files match their primary type/role (`button.py` → `Button`).

## 4.1 Recipe: add a visual mode (one file, zero wiring)

```python
# src/audio_visualizer/visuals/newvisuals.py
from audio_visualizer.visuals.base import BaseVisualizer
from audio_visualizer.visuals.registry import register
from audio_visualizer.visuals import _helpers as h


@register(key="newvisuals", display_name="New Visuals", order=60)
class NewVisuals(BaseVisualizer):
    """Describe what this mode shows and what drives it."""

    def draw(self, surface, frame, dt):
        w, h_ = surface.get_size()           # derive everything from current size
        if frame is None:                    # idle/silent: draw a calm fallback
            return
        # use frame.band_energies (0..1), frame.rms, frame.peak, frame.waveform_mono
```

No edits to `app.py`, `registry.py`, `config.py`, or any other mode. `discover()` finds it; it appears in the cycle, the `1`–`9` picker, and `--mode newvisuals`. Add a quick render check in `tests/` if it has non-trivial logic.

## 5. Output & ignored paths

- `logs/`, `dist/`, `build/`, `.venv/`, `__pycache__/`, `*.spec` build artifacts → see `.gitignore` (`AudioVisualizer.spec` is committed; PyInstaller `build/` temp is not).
