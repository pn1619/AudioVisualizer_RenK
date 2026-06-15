# Development Phases — Build Guide

Companion to `plan/audio-visualizer-plan.md` (§7 is the short roadmap; **this file is the detailed, per-phase work order**). It is the primary guide the agent follows when implementing each phase.

> **Golden rule:** *every phase ends with something that runs.* Do **not** start the next phase until the current phase's **exit criteria** and **tests** are green. Update the docs in the same change (see "Documentation hygiene" in the rules).

**Related docs:** `repository-and-code-layout.md` (where each file goes) · `testing.md` (test strategy + commands) · `git-and-versioning.md` (branching, `PP.FF.BB` versioning, per-phase tags) · `.cursor/skills/audio-visualizer/SKILL.md` (implementation checklist).

---

## At a glance

| Phase | Goal (one line) | Runnable result | Est. coding time |
|-------|-----------------|-----------------|------------------|
| **0 — Skeleton** | Window + controls open, no audio | App window with control bar; `--selftest` exits 0 | **0.5–1 day** |
| **0.5 — Capture spike** | Prove loopback delivers samples | Script prints live RMS from system audio | **1–2 hours** |
| **1 — MVP capture + 3 modes** | Real audio-reactive visuals | Waveform / Spectrum / Light Show react to sound | **2–4 days** |
| **2 — Particles & Laser** | Richer modes + user controls | 5 modes, sensitivity/smoothing, reduce-motion | **2–3 days** |
| **3 — Polish & ship** | Settings, resilience, single `.exe` | Installable `AudioVisualizer.exe` + README | **2–3 days** |
| **4+ — Future** | Growth & quality | See "Future phases" below | ongoing |

> **Time estimates** assume focused work by one developer (AI agent + reviewer) on the locked stack, and *include* writing the phase's tests. They are planning aids, not commitments; treat the range's high end as "with normal debugging."

---

## Phase 0 — Skeleton (runs, no audio)

**Goal:** A real, visibly-working app shell with the full dev workflow in place — before any audio complexity.

### Scope / deliverables
- Project scaffold per `repository-and-code-layout.md`: `src/audio_visualizer/` with `__init__.py`, `__main__.py`, `main.py`, `config.py`, `app.py`, `platform_win.py`.
- `ui/`: `layout.py` (rects from surface size), `button.py`, `controls.py` (control bar), `hud.py` (status line + F3 overlay placeholder).
- `main.py`: arg parsing (`--debug`, `--selftest`, `--mode`, `--version`), `logging` config (console + rotating `logs/app.log`), global `sys.excepthook`.
- `app.py`: open a **resizable** pygame window at native size, draw the control bar + an empty canvas, run the main loop capped at `TARGET_FPS`, handle `VIDEORESIZE` (recreate surface + recompute layout), `F11`/`Esc` fullscreen (borderless desktop), `Ctrl+Q` quit, and a headless `--selftest` (render N frames, exit 0).
- `platform_win.py`: DPI awareness (guarded), `%APPDATA%` path helper.
- Project config: `pyproject.toml` (`requires-python=">=3.12"`, ruff/black/mypy), `.python-version`, `.pre-commit-config.yaml`, `.vscode/` (extensions, settings, launch).
- Tooling: `run.ps1`, `test.ps1`, `lint.ps1`, `format.ps1` (+ `.cmd` wrappers) using `_Common.ps1`.

### Testing plan
- `tests/test_ui_logic.py` — `Button.handle_event` hit-testing; `Layout` recomputes rects across sizes incl. the **minimum size** (no overlap/negative rects).
- `tests/test_smoke.py` — `App` constructs and renders **N frames** headless (`SDL_VIDEODRIVER=dummy`) without crashing; includes a resize event.
- `lint.ps1` clean (ruff + black --check); `mypy` runs (non-blocking).

### Exit criteria
- [ ] `run.ps1` opens a window; control bar buttons draw and respond to hover/click; window resizes and toggles fullscreen with no visual breakage.
- [ ] `python -m audio_visualizer --selftest` exits `0`.
- [ ] `test.ps1` green; `lint.ps1` clean.
- [ ] `check-deps.ps1` still green.

**Estimate: 0.5–1 day.**

---

## Phase 0.5 — Capture spike (de-risk the #1 risk)

**Goal:** Prove on the target machine that `pyaudiowpatch` WASAPI loopback actually delivers audio samples **before** building the capture/analysis stack on top of it. (`check-deps.ps1` already confirmed a loopback *endpoint* exists; this confirms a working *data stream*.)

### Scope / deliverables
- `tools/spike-loopback.py` — opens the default loopback device, reads ~5 s, prints **RMS per chunk** and the device's **native sample rate / channels / dtype**.
- A short note (in this file or a scratch log) recording the observed format — it feeds `audio/capture.py` defaults in Phase 1.

### Testing plan
- **Manual only** (needs real hardware; not in CI): run with audio playing → RMS rises; with silence → RMS ≈ 0 (confirms the silence behavior from plan §11.1).

### Exit criteria
- [ ] RMS visibly tracks playing audio; silence reads ~0.
- [ ] Native format recorded.
- [ ] Decision: keep the spike as a throwaway or fold its open/format logic into `capture.py`.

**Estimate: 1–2 hours.**

---

## Phase 1 — MVP: capture + analysis + 3 modes

**Goal:** The core product — a window that reacts to whatever is playing, in three modes, packaged once to prove the `.exe` path.

### Scope / deliverables
- `audio/source.py` — `AudioSource` interface + `SyntheticSource` (sine/sweep/silence).
- `audio/capture.py` — `LoopbackSource`: negotiate native format, **downmix to mono float32 `-1..1`**, bounded ring buffer, tiny callback, **idle vs error** state.
- `audio/frame.py` — `AnalysisFrame` (frozen; carries real `sample_rate`).
- `audio/analysis.py` — Hann window + `rfft` + RMS/peak + **log-spaced bands**, silence-guarded, smoothing.
- `visuals/base.py` (`BaseVisualizer`), `visuals/registry.py` (`@register` + `discover()`), `visuals/_helpers.py`, and **3 modes**: `waveform.py`, `spectrum.py`, `lightshow.py`.
- `app.py` wiring: start/stop capture, mode cycling + `1`–`9` picker, status line (device/RMS/peak/FPS/mode), idle + fail-soft banner, F3 overlay populated.
- **Package once:** `build-exe.ps1` → run `dist\AudioVisualizer.exe --selftest` (validates PyInstaller + PortAudio DLL bundling early).

### Testing plan
- `tests/test_analysis.py` — pure 1 kHz sine → energy in expected log band; silence → bands ≈ 0, no NaN; RMS/peak correct; band mapping respects `sample_rate` (44.1 vs 48 kHz).
- `tests/test_source.py` — int16 & float32 → float32 `-1..1`; stereo → mono; `SyntheticSource` honors sample rate.
- `tests/test_frame.py` — `AnalysisFrame` frozen; array shapes/dtypes.
- `tests/test_registry.py` — `discover()` finds the 3 modes; unique `KEY`s; `available()` ordered; a temp drop-in module auto-registers.
- `tests/test_visuals.py` — each mode `draw()`s at several sizes incl. tiny and `frame=None` without error.
- `tests/test_smoke.py` — App runs N frames with `SyntheticSource`, incl. an idle (silent) frame.
- `AudioVisualizer.exe --selftest` exits `0`.

### Exit criteria
- [ ] Play audio → Waveform/Spectrum/Light Show visibly react within seconds of Start.
- [ ] Silence shows the **idle state**, not a frozen screen; device error shows the banner and keeps running.
- [ ] Resize / fullscreen / 150% scaling stay crisp and correctly laid out.
- [ ] All unit + smoke tests green; **demo/acceptance check** (reference tone → expected band/RMS) passes.
- [ ] Built `.exe` self-tests `0`.

**Estimate: 2–4 days.**

---

## Phase 2 — Particles & Laser + user controls

**Goal:** Depth and tunability — two energetic modes plus the controls that make it feel responsive and safe.

### Scope / deliverables
- `visuals/particles.py` — particle system driven by RMS/energy + **onset/beat** detection (spectral-flux threshold to start).
- `visuals/laser.py` — rotating beams / Lissajous driven by bands + phase.
- Onset/energy detection helper in `audio/analysis.py` (or `_helpers`), unit-testable.
- Controls: **sensitivity** (−/+), **smoothing** (attack/release), **reduce-motion** toggle, **first-run photosensitivity notice** (one-time, acknowledged in memory now / settings in Phase 3).

### Testing plan
- `tests/test_onset.py` — synthetic transient triggers an onset; steady tone does not.
- `tests/test_visuals.py` (extend) — particles/laser render across sizes & with `frame=None`; **reduce-motion** caps intensity (assert a measurable cap, e.g. max alpha/strobe disabled).
- Particle update is deterministic under a fixed seed (testable without rendering).
- Smoke test covers all 5 modes.

### Exit criteria
- [x] 5 modes selectable and stable; cycling never errors. *(smoke test cycles all modes)*
- [x] Sensitivity & smoothing visibly change reactivity; reduce-motion removes strobing. *(smoothing maps to attack/release; reduce-motion caps particles/strobe)*
- [x] First-run notice shows once before strobing modes. *(acknowledged in memory; persists to settings in Phase 3)*
- [x] Tests green; performance still hits the §11.6 budget (60 FPS at 1280×720 on an iGPU). *(60-frame `--selftest` exits 0; iGPU FPS = manual check)*

**Estimate: 2–3 days.** *(done — onset detection, particles, laser, smoothing/reduce-motion controls, photosensitivity notice)*

---

## Phase 3 — Polish & ship

**Goal:** Make it durable and distributable — a single `.exe` a non-developer can run.

### Scope / deliverables
- `settings.py` — JSON at `%APPDATA%\AudioVisualizer\settings.json` with `schema_version`; **migrate or fall back to defaults** on unknown/corrupt files. Persist: active mode, sensitivity, smoothing, reduce-motion, fullscreen mode, window size, first-run acknowledged.
- **Device-change handling** — survive default-output switch / sleep-wake (re-open, banner, recover).
- `build-exe.ps1` finalized — `--onefile`, **icon + version info**, PortAudio DLL bundled; `-OneDir` fallback.
- CI: add the exe build + `--selftest`; upload artifact.
- `LICENSE` + `THIRD-PARTY-NOTICES.md` (pygame LGPL, numpy, pyaudiowpatch, PortAudio).
- `README.md` quickstart incl. **Python 3.12 install** + how to run the exe.
- **Two extra visual modes** (added by request this phase): `snowfall.py` (bass-driven wind, mid-band flake size, colorful) and `particles_spiral.py` (per-band spiral arms). Each is still one auto-registered file.

### Testing plan
- `tests/test_settings.py` — round-trip; unknown/old/corrupt `schema_version` → defaults, no crash.
- Manual: device hot-swap (speakers ↔ headphones) while running → recovers, no crash; sleep/wake.
- CI runs `AudioVisualizer.exe --selftest` (exit 0).
- Full **manual checklist** in `testing.md` passes on a real machine.

### Exit criteria
- [x] Settings persist and restore across launches; bad settings file never crashes the app. *(`settings.py` + `test_settings.py`: round-trip, corrupt/unknown/bad-type → defaults)*
- [x] Default-device change is survived gracefully. *(App auto-reopens on capture ERROR with banner; `test_app_recovers_from_device_error`. Real hot-swap = manual check)*
- [x] One `.exe` runs on a clean Windows user profile; self-tests `0`; notices shipped. *(spec carries version info + optional icon; `THIRD-PARTY-NOTICES.md` shipped; CI builds + self-tests. Clean-profile run = manual)*
- [x] README lets a new user install + run from scratch.
- [~] All plan §10 success criteria met. *(automated ones green; visual/manual ones via `testing.md` checklist)*

**Estimate: 2–3 days.** *(done — settings persistence, device-change recovery, version-stamped exe, CI, notices, plus snowfall + particles-spiral modes)*

---

## Phase 4 — Tunables & UX (v `00.04.00`)

**Goal:** give the user live, persisted control over how visuals look/move, make the
mode picker scale past `1`–`9`, and add a new waveform variant.

### Scope
- **Shared `Theme`** (`visuals/base.py`): `size_scale`, `speed_scale`, `color_scheme`.
  The App owns one instance and passes the same reference to every mode (`_make_visual`),
  so changes apply instantly. Persisted in settings (schema unchanged; new keys default).
- **Particle/flake size control** and **animation-speed control** applied across the
  motion/particle modes (snowfall, particles, particles-spiral, waveform-2; speed also
  drives lightshow/laser rotation). Buttons `Size −/+`, `Speed −/+`; keys `F5/F6`, `F7/F8`.
- **Color schemes** (`classic` palette / `rainbow` hue-sweep) via `themed_color`/`rainbow_color`
  in `_helpers.py`, used by waveform(-2), spectrum, lightshow, laser, snowfall, spiral.
  Button cycles; key `C`.
- **Mode-picker dropdown** (`ui/dropdown.py`): replaces the click-to-cycle label; lists all
  registered modes (`registry.options()`), opens over the canvas. Key `D` toggles it.
- **New mode `waveform_2.py`** (Waveform 2): the trace plus particles that pop in/out of the
  line (onset/energy-driven), honoring theme size/speed/color.

### Tests
- `test_dropdown.py`: header toggle, option select + close, click-outside closes.
- `test_visuals_phase4.py`: color-helper behavior, waveform-2 determinism + reduce-motion cap,
  speed-scale moves spiral particles further.
- `test_settings.py`: new keys round-trip; invalid `color_scheme` → default.
- `test_smoke.py`: App shares the one live `Theme` with the active visual across mode switches.

### Exit criteria
- [x] Size, speed, and color-scheme adjust live and persist across launches.
- [x] Mode dropdown selects any registered mode; `1`–`9`/`</>` still work.
- [x] New Waveform 2 mode renders and is auto-discovered (8 modes total).
- [x] `plan/audio-visualizer-plan.md` §3.3 lists **all** modes (kept in sync).
- [x] lint/mypy clean, `test.ps1` green, `--selftest` exit 0, exe builds + self-tests.

**Estimate: 1–2 days.** *(done)*

---

## Phase 5 — Per-mode options, value display & color dropdown (v `00.05.00`)

**Goal:** make controls self-explanatory (show current values) and give each mode its own
tunables, plus a dedicated color picker with a time-animated scheme.

### Scope
- **Per-mode option framework** (`visuals/base.py`): `ModeOption`/`OptionChoice` dataclasses
  and `BaseVisualizer.OPTIONS` + `option`/`option_index`/`set_option_index`/`on_option_change`.
  Each mode declares discrete-choice options read in `draw`. Adding/declaring options is still
  one file per mode — no central list.
- **Per-mode option dropdowns** in the control bar's bottom row; rebuilt on mode switch
  (`App._refresh_mode_options`). Options added: waveform/waveform-2 **Line**; waveform-2
  **Pops**; spectrum **Caps**+**Gap**; lightshow **Beam**; laser **Beams**; particles
  **Burst**+**Gravity**; spiral **Swirl**; snowfall **Fall**/**Wind**/**Density**.
- **Snowfall fall vs. wind** as independent options (both still scaled by global speed);
  **Density** rebuilds the flake pool.
- **Inline value chips** (`ui/chip.py`): Sensitivity/Smoothing/Size/Speed values shown
  between their −/+ buttons.
- **Color dropdown** (Classic / Rainbow / **Rainbow+**). `rainbow_plus` advances a shared
  `Theme.color_phase` each frame so colored elements cycle hue over time; `themed_color`
  gains a `phase` arg. Key `C` still cycles.
- **Two-row control bar** (`CONTROL_BAR_HEIGHT` 48 → 88); one dropdown open at a time.

### Tests
- `test_visuals_phase5.py`: option default/clamp, `rainbow_plus` phase offset, snowfall
  fall/wind/density behavior, control-bar value chips + option-dropdown routing.

### Exit criteria
- [x] Each mode shows its own option dropdowns; switching modes rebuilds them.
- [x] Snowfall fall and wind adjust independently; density changes flake count.
- [x] Sensitivity/Smoothing/Size/Speed values are visible in the bar.
- [x] Color dropdown selects Classic/Rainbow/Rainbow+; Rainbow+ animates over time.
- [x] lint clean, `test.ps1` green (59), `--selftest` exit 0, exe builds + self-tests.

**Estimate: 1–2 days.** *(done)*

---

## Phase 6 — Circular waveforms & polish (v `00.06.00`)

**Goal:** smoother color cycling, calmer idle behavior, richer spiral control, and a new
family of circular oscilloscope modes.

### Scope
- **Continuous Rainbow+** — `rainbow_color` wraps the hue with `t % 1.0` **before** any clamp
  so the sweep is seamless (no stick-at-red discontinuity).
- **Idle banner debounce** — `App` tracks `_silent_seconds`; the HUD idle banner only shows
  after `IDLE_BANNER_DELAY` (5 s). Silence never auto-quits the app.
- **Particles Spiral** options **Size** (`reach`, render radius) + **Spacing** (radial gap).
- **Four circular waveform modes** (one file each, auto-registered): `waveform_circle`,
  `waveform_circle_2`, `waveform_circle_multiple` (up to 10 per-band rings), and
  `waveform_circle_multiple_2`. Shared helpers `ring_points`, `draw_ring`, `RingPops` live in
  `visuals/_helpers.py`. **12 modes total.**

### Tests
- `test_visuals_phase6.py`: rainbow wrap continuity, spiral size/spacing options, ring helpers
  (`ring_points`/`RingPops`), all four circle modes render (loud + idle), ring-count option.
- `test_smoke.py`: idle banner waits for the delay and the app doesn't auto-quit on silence.

### Exit criteria
- [x] Rainbow+ cycles smoothly with no red discontinuity.
- [x] "No audio" banner waits ~5 s; app keeps running on silence.
- [x] Spiral Size/Spacing adjust live; four circle modes render and auto-discover (12 total).
- [x] lint clean, `test.ps1` green (69), `--selftest` exit 0, exe builds + self-tests.

**Estimate: 1–2 days.** *(done)*

---

## Future phases (7+) — improvements & growth

Not scheduled; pull items in as priorities dictate. Each should still land behind tests and keep the "simple but works" bar.

**More visuals**
- Shader-ish fullscreen palette field (uses a fixed-resolution effect buffer + `smoothscale` — the documented scaling exception).
- 3D-ish / Lissajous variants, beat-synced scene changes, palette themes.
- Thanks to the §3.5 framework, each new mode is still **one file**.

**Audio & DSP**
- In-app **device selector** (choose which output to capture; mic-input option).
- Move analysis to a **worker thread** if profiling shows main-loop cost (the `AudioSource`/`AnalysisFrame` boundary already allows it).
- Better beat/tempo detection; per-mode reactivity scaling.

**UX & accessibility**
- Optional `pygame_gui` settings panel; preset system (**versioned JSON**, plan §9).
- Multi-monitor / monitor selection; remember-per-monitor window placement.
- Configurable color themes; on-screen keybinding help.

**Platform & distribution**
- Installer (Inno Setup / MSIX) and/or auto-update.
- Optional `-OneDir` distribution for faster start / fewer AV false-positives.
- Code-signing the exe to reduce SmartScreen/AV friction.

**Extensibility / integrations**
- A documented external **plug-in** surface for third-party visuals (narrow, thread-safe — plan rules).
- OSC / MIDI input to drive or sync visuals; audio-file playback mode.

**Engineering quality**
- Coverage gate; make `mypy` blocking; perf soak test (memory stability over hours).
- GitHub Actions matrix; nightly exe artifact.

---

## How to use this doc each phase

1. Read the phase's **Scope** and confirm the relevant files in `repository-and-code-layout.md`.
2. Implement in small, reviewable steps; keep `--selftest` and tests green as you go.
3. Write the phase's **tests** alongside the code (not after).
4. Verify every **exit-criteria** checkbox.
5. Update affected docs (plan §8 decisions, layout, testing, skill) in the same change.
6. **Bump `APP_VERSION`** (`config.py`) + add a `CHANGELOG.md` entry, then **tag the phase**: annotated `v<APP_VERSION>` (e.g. `v00.02.00`) on the green commit and push it. See `git-and-versioning.md`.
7. Only then start the next phase.
