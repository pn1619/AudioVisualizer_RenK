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
│     ├─ settings.py            # load/save JSON settings in %APPDATA% (schema_version=10, migrate-or-default; v7 remaps merged mode keys, v8 adds source_id, v9 adds active_look, v10 adds random_pool+random_interval)
│     ├─ looks.py               # Phase 0B-b: user looks ("My Looks") store — Look dataclass + load/save/CRUD/export/import (own looks.json, schema_version=1)
│     ├─ platform_win.py        # DPI awareness + Windows-specific shims (guarded, no-op off Windows)
│     ├─ resources.py           # Phase 9: locate bundled assets/ in dev + frozen (_MEIPASS) runs
│     │
│     ├─ assets/
│     │  └─ renk_logo.png        # Phase 9: RenK logo art (glowing glass-tube wordmark + ring)
│     │
│     ├─ audio/
│     │  ├─ __init__.py
│     │  ├─ frame.py            # AnalysisFrame dataclass (immutable snapshot)
│     │  ├─ source.py           # AudioSource interface + SyntheticSource (test tone)
│     │  ├─ capture.py          # LoopbackSource(device_id): WASAPI loopback/input via pyaudiowpatch + ring buffer
│     │  ├─ devices.py          # Phase 0B-a: enumerate selectable sources (list_sources / find_device_info)
│     │  └─ analysis.py         # Analyzer: window + FFT + RMS/peak + log bands -> AnalysisFrame
│     │
│     ├─ visuals/
│     │  ├─ __init__.py
│     │  ├─ base.py             # BaseVisualizer + lifecycle hooks; Theme + ModeOption/OptionChoice (per-mode options)
│     │  ├─ registry.py         # @register decorator + discover() auto-import; ordered mode list
│     │  ├─ _helpers.py         # shared draw utils (color lerp, ring_points/draw_ring, RingPops, SparkField); skipped by discovery
│     │  ├─ _transition.py       # Phase 0B-c: ModeTransition (auto-cycle cross-fade clock/alpha); skipped by discovery
│     │  ├─ logo.py             # Phase 9: RenkLogo global overlay (NOT a mode; drawn by app over every mode)
│     │  ├─ background.py       # Phase 10: Background layer (NOT a mode; drawn by app BEHIND every mode): black/spectrum/filaments/mirror/ribbon/gradient/aurora/starfield/vignette + sensitivity/opacity
│     │  ├─ waveform.py         # @register("waveform"); optional Particles + Mirror (absorbed waveform_2, 10.07)
│     │  ├─ spectrum.py         # @register("spectrum"); + Mirror/Glow (10.07)
│     │  ├─ lightshow.py        # @register("lightshow"); Particles Off=solid beams / on=bead beams+emit (absorbed lightshow_2, 10.07)
│     │  ├─ waveform_circle.py  # "Waveform Rings": Rings 1/3/6/12 + Particles (absorbed the 4 circle modes, 10.07)
│     │  ├─ particles.py        # Phase 2; Emitter Field/Spiral (absorbed particles_spiral, 10.07)
│     │  ├─ laser.py            # Phase 2; selectable figure + Particles-driven emit (absorbed laser_2, 10.07)
│     │  ├─ snowfall.py         # Phase 3 (bass wind, mid-band flake size)
│     │  ├─ spectrogram.py      # Phase 10.02 (scrolling magnitude heatmap / waterfall)
│     │  ├─ radial_spectrum.py  # Phase 10.02 ("Audio Sun": radial spectrum bars + core)
│     │  ├─ plasma.py           # Phase 10.02 (bass sine-interference field, low-res upscaled)
│     │  ├─ tunnel.py           # Phase 10.02 (rings flying outward; beats spawn; STROBES)
│     │  ├─ fireworks.py        # Phase 10.02 (onset rockets -> gravity spark bursts)
│     │  ├─ kaleidoscope.py     # Phase 10.02 (mirrored/rotated wedge mandala)
│     │  ├─ terrain.py          # Phase 10.06 ("Synthwave Horizon": scrolling wireframe terrain; Speed)
│     │  ├─ vectorscope.py      # Phase 10.06 (L/R phase scope; Thickness + Mirror)
│     │  ├─ meters.py           # Phase 10.06 ("VU Meters": per-band VU bars; Glow)
│     │  ├─ matrix.py           # Phase 10.06 ("Dot Matrix": falling glyph columns; Glow)
│     │  ├─ pulse_rings.py      # Phase 10.06 (onset-spawned expanding rings; Color + Thickness)
│     │  └─ ripples.py          # Phase 10.06 (water-like ripples; Color + Speed)
│     │      # add a mode = drop one new file here (subclass + @register); no other edits
│     │
│     └─ ui/
│        ├─ __init__.py
│        ├─ layout.py           # Layout: computes control-bar/canvas/HUD rects from current surface size
│        ├─ button.py           # minimal clickable Button (rect + label + hover)
│        ├─ chip.py             # read-only value Chip (shows current Sens/Smooth/Size/Speed)
│        ├─ dropdown.py         # minimal Dropdown widget (mode/color/per-mode options; optional title)
│        ├─ controls.py         # two-row control bar: buttons + chips + color/option dropdowns (+ BG/RenK/About buttons)
│        ├─ logo_panel.py       # Phase 9: RenK logo settings modal (clickable value-cycling rows)
│        ├─ appearance_panel.py # Phase 9.03: UI style/accent/font modal
│        ├─ background_panel.py # Phase 10: Background modal (mode/sensitivity/opacity/height; opened by BG button)
│        ├─ source_panel.py     # Phase 0B-a: Sound-source modal (selectable capture device; opened by Src button)
│        ├─ looks_panel.py      # Phase 0B-b: My Looks save/manage modal (name + Save/Update, load/Dup/Del)
│        ├─ text_input.py       # Phase 0B-b: reusable single-line text input (look naming)
│        ├─ shuffle_panel.py    # Phase 0B-c: auto-cycle modal (Auto toggle + interval + mode checklist)
│        ├─ about.py            # Phase 9: About modal (owner/license/version/build date)
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
│  ├─ test_visuals_phase{3,4,5,6,8}.py  # per-phase visual/option/color coverage
│  ├─ test_modes_phase{1002,1006,1007}.py # Phase 10 mode batches + 10.07 merges/migration/presets/sweeps
│  ├─ test_background_phase{10,1001}.py    # background layer modes + panel/persistence
│  ├─ test_devices_phase0b01.py # Phase 0B-a: source enumeration/resolution + panel + v8 migration
│  ├─ test_looks_phase0b02.py   # Phase 0B-b: My Looks store/persistence + app capture/apply + panel + v9 migration
│  ├─ test_autocycle_phase0b03.py # Phase 0B-c: auto-cycle scheduler/cross-fade + Shuffle panel + v10 migration
│  ├─ test_ui_phase903.py       # appearance (style/accent/font) panel
│  ├─ test_logo_phase9.py       # RenK logo overlay + settings migration + panel/About modals
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
Plain constants and defaults only (no logic): `APP_VERSION`, `SAMPLE_RATE_FALLBACK`, `FFT_SIZE`, `BAND_COUNT`, `MIN_HZ`, `MAX_HZ`, `TARGET_FPS`, `SETTINGS_SCHEMA_VERSION`, `MERGED_MODE_KEYS`, color palette, smoothing factors, sensitivity range, window size, and the **shared visual tunables** (theme ranges, particle/snow caps, `REDUCE_MOTION_BURST_DIVISOR`, `IDLE_LINE_HUE`, circle-layout fractions, …). **Magic-number policy:** shared/cross-mode tunables live here as `UPPER_SNAKE_CASE`; mode-local "feel" numbers live as commented `_UPPER_SNAKE` constants atop their mode file. **Mode keys do *not* live here** — they're declared on each class via `@register(key=...)` (the registry is the single source of truth).

### `settings.py`
Load/save user settings as JSON at `%APPDATA%\AudioVisualizer\settings.json`. Includes `schema_version` (currently **8**); on load, **migrate or fall back to defaults** for unknown/corrupt files (never crash) — v7 remaps deprecated mode keys to their survivor via `config.MERGED_MODE_KEYS`, v8 adds the selectable capture `source_id`. Persists active mode, sensitivity, smoothing, reduce-motion, fullscreen pref, window size, first-run-notice acknowledgement, size/speed scale, color scheme, appearance (style/accent/font), background, RenK logo prefs, and `source_id`. Per-mode option/preset indices are not persisted.

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
Shared, reusable drawing utilities so new modes don't reinvent primitives: color helpers (`lerp_color`, `palette_color`, `scale_color`, `rainbow_color` — which wraps hue with `t % 1.0` so Rainbow+ is continuous, `themed_color(scheme, t, palette, phase)`), the spectrum-slicing helper `range_energies(bands, slices)` (shared by the multi-ring modes), the circular-waveform helpers `ring_points`, `draw_ring`, and the reusable `RingPops` pop-particle field, plus the reusable `SparkField` (free particles in normalized space with an optional fading "shadow" trail) and the shared `TRAIL_OPTION` (used by `lightshow`/`laser`), plus the shared `PARTICLES_OPTION`/`MIRROR_OPTION`/`GLOW_OPTION` axes folded into the merged modes (Phase 10.07). Leading underscore → **skipped by `discover()`**.

### `visuals/*.py` (the modes)
Each mode = **one file**: subclass `BaseVisualizer`, decorate with `@register`, implement `draw`. `waveform` draws the mono line; `spectrum` draws log bars + peak caps; `lightshow` draws radial beams + bloom; `particles` and `laser` are Phase 2. A mode that raises during `draw` is caught by `App` (logged + fail-soft), never crashing the app.

### `ui/layout.py`
`Layout` — computes the control-bar, main-canvas, and HUD rectangles from the **current surface size** every frame (with the minimum-size clamp). Single place that owns positioning, so resizing/fullscreen never produces clipping or stretching and no module hard-codes pixel coordinates.

### `ui/style.py`
The single source of the UI look: a process-wide `STYLE` (Flat/Glass + accent) that every widget reads at draw time, `draw_panel(...)` (the one place the two styles are drawn, with hover/accent states), and `fit_text(font, text, max_width)` (ellipsis truncation so nothing spills out of a box).

### `ui/fonts.py`
`get_ui_fonts(choice)` — resolves the **Mono** (terminal-style monospace) or **Sans** UI fonts via pygame `SysFont` (with fallbacks), so the user-chosen font applies everywhere.

### `ui/button.py`
`Button` — rect, label, hover/press state, `handle_event(event) -> bool`, `draw(surface, font)`; draws via `ui/style.draw_panel` and truncates its label to fit.

### `ui/chip.py`
`Chip` — a non-interactive labelled value box; the control bar uses these to show `Sens/Smooth/Size/Speed <value>` between the `−`/`+` steppers.

### `ui/dropdown.py`
`Dropdown` — header + expandable option list; optional `title` prefixes the current label (e.g. `Fall: Normal`). Header + option text **truncate to fit**, and the open list is clamped to stay within the window's right edge (`set_bound_right`). Used for the Menu, mode picker, color scheme, and per-mode options.

### `ui/controls.py`
Builds the control bar and **flows/wraps** its widgets to the window width (global controls + value steppers, then color + per-mode option dropdowns), so nothing runs off-screen even at the minimum window size; `content_height(width)` reports the height the App feeds to `Layout.compute`. Translates clicks into `App` actions (start/stop, mode, sensitivity/smoothing/size/speed, color, per-mode option changes, fullscreen, Appearance). `set_mode_options(specs)` rebuilds the per-mode dropdowns when the active mode changes; only one dropdown stays open at a time.

### `ui/appearance_panel.py` & `ui/background_panel.py` & `ui/about.py` & `ui/logo_panel.py`
Centered modal dialogs (dim backdrop, click-row-to-cycle or Close). **Appearance** picks the UI **style** (Flat/Glass), **accent** (Cyan/Aurora gradient/Neon green), and **font** (Mono/Sans); **Background** (the `BG` button) picks the backdrop **mode** (Black/Spectrum/Filaments/Mirror/Ribbon/Gradient/Aurora/Starfield/Vignette), **sensitivity**, **opacity**, and **spectrum height**; **RenK** configures the logo overlay; **About** shows owner/license/version/build/runtime. All draw via `ui/style.draw_panel`, which centralizes both styles and the (optionally gradient) accent (its glass radius is capped so large panels stay rounded rectangles).

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
