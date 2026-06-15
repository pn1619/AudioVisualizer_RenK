---
name: audio-visualizer
description: >-
  Build and maintain a Windows system-audio visualizer in Python (pygame +
  numpy + pyaudiowpatch) that captures WASAPI loopback and renders waveform,
  spectrum, light show, particles, and laser modes, packaged as a single .exe.
  Use when implementing or editing this repo, adding audio capture, FFT/DSP,
  visual modes, UI/buttons, tooling scripts, tests, or packaging; or when the
  user mentions loopback, spectrum, waveform, light show, particles, laser,
  snowfall, or spiral visuals on Windows.
---

# Audio Visualizer — Agent Skill

> **Mantra:** *Simple but works beats complicated but broken.* Get a moving, audio-reactive window first; refine after.

## Read first (canonical docs)

| Topic | Path |
|-------|------|
| Product, 7 requirements, decisions, roadmap | `plan/audio-visualizer-plan.md` |
| **Per-phase build guide** (scope, tests, exit criteria, estimates) | `plan/development-phases.md` |
| Folder tree, module responsibilities, data flow | `plan/repository-and-code-layout.md` |
| How to prove it works (tests, selftest, manual) | `plan/testing.md` |
| Git flow, `PP.FF.BB` versioning, per-phase tags | `plan/git-and-versioning.md` |
| Project conventions (always applied) | `.cursor/rules/python-audio-visualizer.mdc` |
| Python style (always applied) | `.cursor/rules/python-coding-style.mdc` |

## Stack

- **Python 3.12+** (3.12 or newer, 64-bit), **pygame**, **numpy**, **pyaudiowpatch** (WASAPI loopback), **PyInstaller** (single `.exe`).
- Dev in **Cursor + VS Code**; shared config in committed `.vscode/`. `check-deps.ps1` + README enforce/announce Python ≥ 3.12.
- Lint/format: **ruff** + **black** (pre-commit); tests: **pytest** (headless).

## Build order (each step ends with something that runs)

> Follow `plan/development-phases.md` for full per-phase scope, tests, exit criteria, and estimates. Summary:

1. **Scaffold** the layout from the layout doc (`src/audio_visualizer/...`, `tests/`, `tools/`, `.vscode/`, `requirements*.txt`, `pyproject.toml`, `.python-version`, `.pre-commit-config.yaml`).
2. **Phase 0 — skeleton:** `config.py`, `app.py` opens a pygame window + control bar buttons (custom `Button`), `main.py` args + logging + `sys.excepthook`, DPI awareness via `platform_win`, `--selftest` renders N headless frames and exits 0. Add `test_smoke.py`. CI green.
3. **Phase 0.5 — capture spike (do before Phase 1):** `tools/spike-loopback.py` opens `pyaudiowpatch` loopback and prints RMS for ~5 s. **Prove the machine delivers samples**; note its native sample rate/channels/dtype. This de-risks the #1 failure point.
4. **Phase 1 — capture + analysis + 3 modes:**
   - `audio/source.py` (`AudioSource`, `SyntheticSource`), `audio/capture.py` (`LoopbackSource` via `pyaudiowpatch`: **negotiate format, downmix to mono float32**, ring buffer, idle-vs-error state), `audio/frame.py` (`AnalysisFrame` w/ real `sample_rate`), `audio/analysis.py` (Hann + rfft + RMS/peak + log bands, **silence-guarded**).
   - `visuals/base.py` (`BaseVisualizer`) + `registry.py` (`@register` + `discover()`) + `_helpers.py`; `waveform.py`, `spectrum.py`, `lightshow.py` each auto-register; idle animation for the "no audio" state. `ui/layout.py` computes rects from surface size.
   - Wire start/stop, mode cycling, status line, **window resize** in `app.py`. Add `test_analysis.py`, `test_source.py`, `test_frame.py`, `test_ui_logic.py`.
   - **Package once now:** `build-exe.ps1` → `dist\AudioVisualizer.exe --selftest` exits 0 (validates PortAudio DLL bundling early).
5. **Phase 2:** `particles.py`, `laser.py` (onset/spectral-flux detection lives in `analysis.py` → `AnalysisFrame.onset`), sensitivity/smoothing controls (`Analyzer.set_smoothing`), reduce-motion toggle, first-run safety notice (strobing modes set `BaseVisualizer.STROBES = True`; notice acknowledged in memory until Phase 3 settings).
6. **Phase 3 (done):** `settings.py` (JSON in `%APPDATA%`, `schema_version`, migrate-or-default; load on start / save on exit), device-change recovery (auto-reopen on capture error + banner), version-stamped spec (`+` optional `assets/icon.ico`), `--selftest` on the exe, CI (`.github/workflows/ci.yml`), `LICENSE` + `THIRD-PARTY-NOTICES.md`, README quickstart. Two added modes: `snowfall.py`, `particles_spiral.py` (7 modes total).
7. **Phase 4 (done):** shared `Theme` (`visuals/base.py`: `size_scale`/`speed_scale`/`color_scheme`) passed live to every mode + persisted; `themed_color`/`rainbow_color` in `_helpers.py`; **mode-picker dropdown** (`ui/dropdown.py`); new `waveform_2.py` (waveform + popping particles) → **8 modes total**. Controls: `Size −/+` (F5/F6), `Speed −/+` (F7/F8), color cycle (C), dropdown (D). Keep `plan` §3.3 modes table in sync when adding/removing a mode.
8. **Phase 5 (done):** **per-mode options** — declare `OPTIONS: tuple[ModeOption, ...]` on a mode (each a labelled set of `OptionChoice`s) and read `self.option(key)` in `draw`; the App renders them as bottom-row dropdowns (`set_mode_options`/`_refresh_mode_options`), rebuilt on mode switch. Snowfall now has independent **Fall**/**Wind**/**Density**. **Value chips** (`ui/chip.py`) show current Sens/Smooth/Size/Speed. **Color dropdown** adds `rainbow_plus` (time-animated via `Theme.color_phase`; `themed_color(..., phase)`). Two-row control bar (`CONTROL_BAR_HEIGHT = 88`). Adding options to a mode stays one-file; never add a central option list.
9. **Phase 6 (done):** `rainbow_color` wraps hue with `t % 1.0` **before** clamping (continuous Rainbow+). Idle banner debounced by `IDLE_BANNER_DELAY` (App `_silent_seconds`); **never auto-quit on silence**. Particles Spiral adds `reach` (Size) + `spacing`. **Four circular waveform modes** — `waveform_circle`, `waveform_circle_2`, `waveform_circle_multiple` (≤10 per-band rings), `waveform_circle_multiple_2` — sharing `ring_points`/`draw_ring`/`RingPops` in `visuals/_helpers.py`. **12 modes total.** Keep `plan` §3.3 modes table in sync.

## Implementation checklist (rules that matter)

1. **Loopback via interface:** all audio through `AudioSource`; `App`/`Analyzer` never import `pyaudiowpatch` directly. Use `SyntheticSource` for tests/CI/`--selftest`.
2. **Tiny audio callback:** copy samples into a bounded ring buffer; no allocations/blocking; heavy DSP off the callback.
3. **Pure DSP:** `analysis.py` is numpy-in → `AnalysisFrame`-out, no pygame/I/O.
4. **One file per visual mode**: subclass `BaseVisualizer` + `@register(key, display_name, order)`; `discover()` auto-imports. **Adding a mode must require zero edits elsewhere** (no central list, no `config.py` change). Modes read size from the surface, take only `AnalysisFrame`+`dt`, and are caught fail-soft if they raise.
5. **`app.py` is wiring only**; logic lives in `audio/`, `visuals/`, `ui/`.
6. **Constants in `config.py`** as `UPPER_SNAKE_CASE` (mode keys, FFT size, FPS, colors, smoothing). No magic strings.
7. **Logging not print**; `--debug` → DEBUG to console + `logs/app.log`; **F3** debug overlay.
8. **Fail-soft:** capture/device errors → on-screen banner, app keeps running. Global `sys.excepthook` logs tracebacks; close the stream in `finally`.
9. **Silence is a state, not a bug:** loopback often gives silence/no callback — show an idle animation, guard DSP against NaN/div-by-zero.
10. **Negotiate format + mono downmix** to float32 `-1..1`; never assume 48 kHz stereo. Carry real `sample_rate` in `AnalysisFrame`.
11. **DPI awareness + resizable window**; render at **native size** (no `SCALED`/upscaled buffer → no blur); recreate surface + recompute layout on `VIDEORESIZE`; enforce a min size. **Fullscreen = borderless desktop by default** (exclusive optional in settings).
12. **Reduce motion** option (caps particle count + disables strobe) + one-time **photosensitivity notice** shown before any mode with `STROBES = True`; no seizure-risk strobing by default.
13. **Settings JSON** in `%APPDATA%` with `schema_version`; migrate-or-default, never crash on a bad file.
14. **Keep `--selftest` green** — it is the cheapest proof the app runs.

## UI / buttons (shipped intent)

- Top control bar (auto-hides in fullscreen) with buttons: Start/Stop, ‹ / › mode, mode name, sensitivity − / +, Fullscreen, Quit. Positions come from `ui/layout.py` (size-relative; resize-safe).
- Keyboard: `Space` start/stop, `←/→` or `[ ]` modes, `1`–`9` jump mode, `F11` fullscreen, `Esc` exit fullscreen, `F3` debug overlay.
- Fullscreen is borderless-desktop by default (instant, native resolution); exclusive is an optional setting. Status line: device, RMS/peak, FPS, mode.

## Audio capture reference (pyaudiowpatch)

- Get the WASAPI host API, find the default output device's **loopback** counterpart, read its native **rate/channels/dtype**, open an input stream with a callback that **downmixes to mono float32** and copies frames to the ring buffer. Handle "loopback device not found" and open errors by setting an **error** state (banner), not raising to top; treat sustained zeros as the **idle** state.
- Bundle the **PortAudio DLL** in PyInstaller (`collect_dynamic_libs("pyaudiowpatch")`); confirm with `--selftest` on the built exe.

## Tooling

- `tools/*.ps1` (+ `.cmd`), each with `-Help`, banner, next steps; shared `tools/_Common.ps1`.
- `check-deps`, `setup` (.venv + pip), `run`, `test` (headless dummy SDL drivers), `lint` (ruff+black), `format`, `build-exe` (PyInstaller `--onefile`, `-OneDir` option).

## Testing (see `plan/testing.md`)

- pytest layers: DSP (incl. silence + sample-rate), audio format/downmix, frame contract, settings migration, UI logic, headless smoke (incl. idle frame).
- Prove the window runs: `python -m audio_visualizer --selftest` and `dist\AudioVisualizer.exe --selftest` exit 0.
- Demo/acceptance: reference tone → expected band/RMS reaction (objective "it reacts").
- Manual checklist: real audio → motion, **idle state when silent**, mode switching, fullscreen, **resize/high-DPI**, device change, F3 overlay.

## Version control & releases

- Develop on `feature/<topic>` branches → **PR into a green `main`** (pytest + ruff + black + `--selftest`). Conventional commit prefixes; body says *why*.
- One version string `APP_VERSION` in `config.py` (`PP.FF.BB`); bump it + add a `CHANGELOG.md` entry when a phase/build advances. **Tag each completed phase** with an annotated `v<APP_VERSION>` (e.g. `v00.02.00`) and push it. Never edit global git config; use per-command flags (and `http.sslBackend=schannel` behind SSL-inspecting proxies). Full convention: `plan/git-and-versioning.md`.

## Documentation hygiene

- Update `plan/*` (esp. decisions §8, and `git-and-versioning.md`) and this skill whenever capture strategy, modes, tooling, packaging, or the git/versioning flow change. Keep the layout doc's tree/diagram accurate.
