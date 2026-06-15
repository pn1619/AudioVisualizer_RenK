# Changelog

Version scheme `PP.FF.BB` — `PP` pre-release (`00` until ship), `FF` development
phase, `BB` build within the phase. The string lives once as `APP_VERSION` in
`config.py`. Each completed phase is tagged with an annotated git tag
`v<APP_VERSION>` (e.g. `v00.02.00`), so entries below map 1:1 to tags. See
`plan/development-phases.md` and `plan/git-and-versioning.md`.

All three initial phases were implemented in one pass; the entries below record
what each phase delivered and its verification results.

---

## `00.06.00` — Phase 6: continuous Rainbow+, idle delay & circular waveforms

**Delivered**
- **Continuous Rainbow+** — `rainbow_color` now wraps the hue **before** clamping (`t % 1.0`),
  so the sweep is seamless (0.0 == 1.0) instead of sticking at red and jumping back.
- **Idle banner debounce** — the "No audio detected" banner only appears after the signal
  has been silent for `IDLE_BANNER_DELAY` (5 s); brief track gaps no longer flash it. The
  app **never auto-quits** on silence — the user quits when they want.
- **Particles Spiral** gains **Size** (overall circle reach) and **Spacing** (gap between
  sparks) options, alongside the existing Swirl.
- **Four new circular waveform modes** (now **12 modes** total):
  - `waveform_circle` — the oscilloscope wrapped around a ring (Size, Line options).
  - `waveform_circle_2` — the ring plus popping particles (adds Pops).
  - `waveform_circle_multiple` — up to **10 concentric rings**, one per equal spectrum slice;
    Rings / Size / Spacing / Line options.
  - `waveform_circle_multiple_2` — the multi-ring mode plus per-ring popping particles.
- Shared circular helpers in `visuals/_helpers.py`: `ring_points`, `draw_ring`, and a reusable
  `RingPops` pop-particle field.

**Tests / verification**
- `tools\test.ps1` → **69 passed** (adds `test_visuals_phase6.py`; idle test updated for the delay).
- `tools\lint.ps1` → ruff **clean**, black **clean**.
- `python -m audio_visualizer --selftest` → exit **0**.

---

## `00.05.00` — Phase 5: per-mode options, color dropdown & Rainbow+

**Delivered**
- **Per-mode option dropdowns** — a small `ModeOption`/`OptionChoice` framework on
  `BaseVisualizer` (`OPTIONS`, `option`, `option_index`, `set_option_index`). Each mode
  exposes its own tunables as labelled, discrete-choice dropdowns that rebuild when the
  active mode changes. New options: waveform/waveform-2 **Line** thickness; waveform-2
  **Pops** rate; spectrum **Caps** + **Gap**; light show **Beam** width; laser **Beams**
  count; particles **Burst** + **Gravity**; particles-spiral **Swirl**; snowfall **Fall**,
  **Wind**, **Density**.
- **Snowfall fall vs. wind** are now independent options (each still scaled by the global
  speed control); **Density** picks the flake count (Low/Medium/High).
- **Inline value display** — the control bar shows current **Sensitivity / Smoothing /
  Size / Speed** values in read-only chips (`ui/chip.py`) between their −/+ buttons.
- **Color scheme dropdown** (its own control) with **Classic**, **Rainbow**, and the new
  **Rainbow+** — `rainbow_plus` adds a time-advanced hue phase so every colored element
  (particles, beams, Lissajous, radial beams, bars, oscilloscope, flakes) cycles color
  over time. Key `C` still cycles; `themed_color` gains a `phase` argument; the App owns
  a shared `Theme.color_phase` advanced each frame.
- **Two-row control bar** (`CONTROL_BAR_HEIGHT` 48 → 88): global controls on top, color +
  per-mode option dropdowns on the bottom. Only one dropdown stays open at a time.

**Tests / verification**
- `tools\test.ps1` → **59 passed** (adds `test_visuals_phase5.py`).
- `tools\lint.ps1` → ruff **clean**, black **clean**.
- `python -m audio_visualizer --selftest` → exit **0**.

---

## `00.04.00` — Phase 4: tunables, mode dropdown & Waveform 2

**Delivered**
- **Shared `Theme`** (`visuals/base.py`): `size_scale`, `speed_scale`, `color_scheme`.
  The App owns one instance and passes the same reference to every mode, so changes
  apply instantly; all three are persisted in settings.
- **Particle/flake size control** and **animation-speed control** applied across the
  motion/particle modes (snowfall, particles, particles-spiral, waveform-2; speed also
  drives lightshow/laser rotation). Buttons `Size −/+`, `Speed −/+`; keys `F5/F6`,
  `F7/F8`.
- **Color schemes** — `classic` palette and `rainbow` hue-sweep — via new
  `rainbow_color`/`themed_color` helpers, used by waveform, waveform 2, spectrum,
  light show, laser, snowfall, and particles spiral. Button cycles; key `C`.
- **Mode-picker dropdown** (`ui/dropdown.py`) replacing the click-to-cycle label;
  lists every registered mode and opens over the canvas. Key `D` toggles it.
- **New mode `waveform_2.py`** (Waveform 2): the oscilloscope trace plus particles
  that pop in/out of the line (onset/energy-driven). **8 modes total.**
- `plan/audio-visualizer-plan.md` §3.3 now lists **all** visual modes (kept in sync).

**Tests / verification**
- `tools\test.ps1` → **53 passed** (adds `test_dropdown.py`, `test_visuals_phase4.py`,
  extends `test_settings.py` + `test_smoke.py`).
- `tools\lint.ps1` → ruff **clean**, black **clean**, mypy **no issues**.
- `python -m audio_visualizer --selftest` → exit **0**.

---

## `00.03.00` — Phase 3: polish, persistence & ship + 2 modes

**Delivered**
- `settings.py` — JSON at `%APPDATA%\AudioVisualizer\settings.json` with
  `schema_version`; load **migrates or falls back to defaults** on
  missing/corrupt/unknown/bad-type files (never crashes). Persists mode,
  sensitivity, smoothing, reduce-motion, fullscreen, window size, and the
  first-run notice acknowledgement.
- App wiring: load settings on startup (CLI `--mode` still wins), apply them, and
  save on exit. Restores fullscreen + window size.
- **Device-change resilience:** capture errors flip to a banner and the app
  auto-reopens the stream on an interval (`DEVICE_RECOVER_INTERVAL`), recovering
  without a crash.
- **Two new visual modes** (by request): `snowfall.py` (bass-driven wind, mid-band
  flake size, colorful, idle-friendly) and `particles_spiral.py` (per-band spiral
  arms; energy/onset spawn rate). Total modes: **7**.
- Packaging: `AudioVisualizer.spec` now stamps a **Windows version resource**
  from `APP_VERSION` and uses `assets/icon.ico` if present.
- CI: `.github/workflows/ci.yml` (setup → check-deps → lint → test → build-exe +
  self-test → upload exe artifact).
- Docs: `THIRD-PARTY-NOTICES.md` added; README updated (status, new modes,
  controls, exe run, settings, license).

**Tests / verification**
- `tools\test.ps1` → **43 passed** (adds `test_settings.py`, device-recovery
  smoke test, snowfall/spiral determinism + reduce-motion caps).
- `tools\lint.ps1` → ruff **clean**, black **clean**, mypy **no issues**.
- `python -m audio_visualizer --selftest` → exit **0**.

---

## `00.01.00` — Phase 1: MVP capture + analysis + 3 modes

**Delivered**
- Audio pipeline:
  - `audio/source.py` — `AudioSource` protocol + `SyntheticSource` (sine/sweep/silence).
  - `audio/capture.py` — `LoopbackSource`: negotiates the device's native format,
    downmixes to **mono float32 -1..1**, bounded ring buffer, tiny callback,
    running/error status. Failures set ERROR instead of raising.
  - `audio/frame.py` — frozen `AnalysisFrame` (carries real `sample_rate`, `is_silent`).
  - `audio/analysis.py` — Hann window + rfft + **log-spaced bands** + RMS/peak,
    attack/release smoothing, silence-guarded (no NaN), band map rebuilt per rate.
- Visual framework + 3 modes:
  - `visuals/base.py` (`BaseVisualizer`), `visuals/registry.py` (`@register` +
    `discover()`), `visuals/_helpers.py`.
  - `waveform.py`, `spectrum.py` (peak caps), `lightshow.py` (radial beams + core).
- App wiring: start/stop, mode cycling + `1`–`9` picker, **sensitivity** control,
  status line, F3 debug overlay, idle/error banners, fail-soft visual draw.
- Packaging: `AudioVisualizer.spec` (bundles PortAudio DLL via
  `collect_dynamic_libs`; collects visual submodules via `collect_submodules`),
  `tools/build-exe.ps1` (+ `.cmd`).
- `README.md` quickstart.

**Tests / verification**
- `tools\test.ps1` → **25 passed** (analysis, source/downmix, frame, registry
  incl. drop-in auto-register, visuals across sizes + None frame, UI logic, smoke
  incl. idle, selftest entry point).
- `tools\lint.ps1` → ruff **clean**, black **clean**, mypy **no issues**.
- `python -m audio_visualizer --selftest` → exit **0**.
- `tools\build-exe.ps1` → `dist\AudioVisualizer.exe` (25.4 MB); built exe
  `--selftest` → exit **0** (waited process).

**Bugs found & fixed during the phase**
- Frozen exe reported "No visual modes registered" — dynamic discovery hid the
  modes from PyInstaller's static analysis. Fixed by `collect_submodules` in the spec.
- `build-exe.ps1` falsely passed because a windowed exe isn't awaited by `& $exe`;
  switched to `Start-Process -Wait -PassThru` (and cleaned up two leftover processes
  that had locked the output file).

---

## `00.00.01` — Phase 0.5: capture spike (de-risk)

**Delivered**
- `tools/spike-loopback.py` — opens WASAPI loopback, prints RMS + native format.

**Verification**
- Ran on this machine: device **"Realtek HD Audio 2nd output [Loopback]"**,
  native format **48000 Hz, 2 ch, int16**. Callback fires reliably; with no audio
  playing RMS reads ~0 (confirms the expected silence/idle behavior). Capture path
  validated before building the analysis stack on top of it.

---

## `00.00.00` — Phase 0: skeleton (runs, no audio)

**Delivered**
- Package scaffold under `src/audio_visualizer/`: `__init__`, `__main__`, `main.py`
  (args + logging + `sys.excepthook`), `config.py` (incl. `APP_VERSION`),
  `platform_win.py` (DPI awareness + `%APPDATA%` helper), `app.py` (resizable
  window, native-size render, fullscreen toggle, main loop, `--selftest`).
- UI: `ui/layout.py` (size-relative rects + min-size clamp), `ui/button.py`,
  `ui/controls.py` (control bar), `ui/hud.py` (status line, banners, F3 overlay).
- Project config: `pyproject.toml` (`requires-python>=3.12`, ruff/black/mypy/pytest),
  `.python-version`, `.pre-commit-config.yaml`, `.vscode/` (extensions/settings/launch).
- Tooling: `run.ps1`, `test.ps1`, `lint.ps1`, `format.ps1` (+ `.cmd`), shared
  `_Common.ps1`; pre-existing `check-deps.ps1`, `setup.ps1`.
- Tests: `test_ui_logic.py`, `test_smoke.py` (+ `conftest.py` forcing dummy SDL).

**Verification**
- Window opens with a control bar; `--selftest` exits **0**; headless smoke tests pass.
