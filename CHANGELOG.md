# Changelog

Version scheme `PP.FF.BB` — `PP` pre-release (`00` until ship), `FF` development
phase, `BB` build within the phase. The string lives once as `APP_VERSION` in
`config.py`. Each completed phase is tagged with an annotated git tag
`v<APP_VERSION>` (e.g. `v00.02.00`), so entries below map 1:1 to tags. See
`plan/development-phases.md` and `plan/git-and-versioning.md`.

All three initial phases were implemented in one pass; the entries below record
what each phase delivered and its verification results.

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
