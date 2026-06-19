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

> **Current state (v00.0A.07):** **19 visual modes** (consolidated from 26 in 10.07) + a global
> RenK logo overlay and a background layer (both drawn by `app.py`, neither a `@register`ed
> mode). Modes share option axes (`PARTICLES_OPTION`, `MIRROR_OPTION`, `GLOW_OPTION`, …) and
> per-mode `PRESETS`. Settings schema is **10** (v8 adds the selectable capture `source_id`;
> v9 adds `active_look`; v10 adds the auto-cycle `random_pool`/`random_interval`).
A `Src` button opens a **Sound source** modal to pick the capture device (default / output
loopback / mic) — enumerated in `audio/devices.py`, opened on a pinned device via
`LoopbackSource(device_id=...)`. **User looks ("My Looks", v00.0B.02):** a `My Looks` dropdown
+ `Save…` button (row 1, distinct from the per-mode `Preset` dropdown) save/load a complete
look (mode + options + theme + sensitivity/smoothing + Background/Logo snapshot) via the
`looks.py` store (own `looks.json`); applying a look overlays live global and `None / Live`
restores the live (pre-look) state. **Saving bookmarks the current look without auto-activating**
(you stay on `None / Live`), so the saved entry never collides with the baseline.
**Auto-cycle ("shuffle", v00.0B.03–08):** an `Auto` toggle + `Next` button +
`Shuffle…` modal (`A` / `N` keys) auto-switch the active visual every interval. `ModeTransition`
(`visuals/_transition.py`) does a **live cross-fade for mode→mode** (the outgoing visual keeps
animating; `App._draw` re-paints it onto the frame's background) and a **frozen-snapshot dissolve**
for switches involving a saved look; reduce-motion or a `0s` fade hard-cuts. The rotation pool
(`random_pool`, tagged `mode:<key>` **and** `look:<id>`), `random_interval`, a **`random_options`**
toggle (randomize a built-in mode's own options on landing — not Background/Logo/looks), and the
user-adjustable **`random_fade`** time persist (schema v12). A small chip names the current item
(`Auto · Mode: … / Look: … · next in Ns`). Auto is never persisted on; stopping leaves the
current visual. The full, current mode catalog is
> `plan/visual-mode-ideas.md`; the build-order list below is a per-phase history.

**Mode option tweaks (v00.0B.07):** a shared **`SIZE_OPTION`** (`S`…`XXXL` multiplier, `M`=original
size) in `_helpers.py` is reused by **Vectorscope** (replaces its old size), **Pulse Rings**,
**Audio Sun**, **Kaleidoscope**. **VU Meters** gained a **`Spark`** option (needle tip throws embers;
ladder/bar spray rising rainbow sparks via the shared `SparkField`). **Pulse Rings** now shoot
expanding fading circles on beats matching the draw style (dashed→dashed) and **`Spin: Off`** truly
freezes (the angle no longer advanced regardless). **Ripples** gained a **`Size`** option (incl.
per-ring `Random`).

**Build 6 (v00.0B.08):** **Randomize** (shuffle's `random_options` *and* a new manual **`Rnd`** button /
**`R`** key) now also rolls the **global feel** — Sensitivity/Smoothing/Size/Speed — from continuous
ranges (`App._randomize_globals`); the `Rnd` button re-rolls the current mode's options + feel
**without** switching modes (`App._randomize_current_mode`). **Kaleidoscope** draws spokes
shortest-first (long rays land on top, no longer clipped where they cross near the centre; straight
spokes are one continuous line) and gained a **`Spark`** option. **My Looks** can **Export/Import** the
whole library to `AudioVisualizer-looks.json` **next to the app** (`looks.export_library`/`import_library`,
`platform_win.get_app_dir`); the `Save…` modal shows the file location + a status line. Library import is
fully lenient (missing/corrupt → imports nothing, never crashes); a failed live save logs a delete/reset hint.

**Build 7 (v00.0B.09):** **Pulse Rings** split the shoot-out into a `Shoot` toggle + `Shoot %`
opacity (drawn through a black-keyed alpha layer). **VU Meters** `Spark` is now `Off`/`Fine`/`Bold`
(size multiplier), sparks are ~½ the old size, and low meters get an emission boost so bass shoots.
**Snowfall** added `Drift`/`Light` wind steps (Light default) + a low-passed `React` (`Off`/`Subtle`/
`Strong`) so bass steers the lean smoothly. **Laser** dropped Star/Spiral/Heart for `Spiro`
(hypotrochoid), `Web` (harmonograph), `Bloom` (epicycloid). **Audio Sun** `Core` is now `Orbit`/`Dust`
(rings of orbiting particles) + a ray-tip `Spark`. **Editable value chips** (`ui/chip.py`): the
control-bar Sens/Smooth/Size/Speed chips and the Shuffle `Every…s`/`Fade…s` chips are click-to-type
(Enter/click-away applies, clamped, invalid input ignored; typing suppresses key shortcuts via
`ControlBar.is_editing()`).

**Build 8 (v00.0B.10):** **Randomize locks** — a `LockToggle` padlock (`ui/lock_toggle.py`) beside each
randomizable control holds its value through **Rnd/Next/auto** (default unlocked). Covers the global
feel chips and per-mode option dropdowns (not `preset`/single-choice). `App._locked_globals` persist
across mode switches; `App._locked_options` clear on a mode switch (honored in `_randomize_globals`/
`_randomize_mode_options`). **Menu → Hotkeys…** modal (`ui/hotkeys.py`) lists shortcuts (mirror
`_handle_key`). **My Looks** Del/Dup/Import now refresh the list live via `LooksActions.refresh_state`
→ `LooksPanel._refresh` (no close-reopen).

**Build 9 (v00.0B.11):** **Waveform** + **Waveform Rings** gained a `Trace` smoothing option
(`Rough`/`Smooth`/`Smoother`/`Sine`) via `smooth_wave` in `_helpers.py` (circular for rings, reflect
for the linear scope) plus a height scaler (`Height` / `Wave`). **VU Meters** `Spark` adds `Big`/`Huge`/
`Max` sizes, and a `Needle` style option (`Classic`/`Gauge`/`VU`/`Comet`/`Dual`, only used when
`Style = Needle`) with a pivot hub.

**Build 10 (v00.0B.12):** Randomize-lock UX. `LockToggle` is now a **dot** (filled accent = held,
hollow dim ring = free) and flips **immediately on click** (optimistic local toggle; App still re-syncs
each state refresh). Pins sit in a **tight gap** hugging the chip/dropdown they govern and stay on the
same wrap row (`ControlBar._flow`, `_LOCK_GAP`).

## Read first (canonical docs)

| Topic | Path |
|-------|------|
| Product, 7 requirements, decisions, roadmap | `plan/audio-visualizer-plan.md` |
| **Per-phase build guide** (scope, tests, exit criteria, estimates) | `plan/development-phases.md` |
| Folder tree, module responsibilities, data flow | `plan/repository-and-code-layout.md` |
| How to prove it works (tests, selftest, manual) | `plan/testing.md` |
| **Current mode catalog** (shipped + proposed visuals) | `plan/visual-mode-ideas.md` |
| Phase 10.06 / 10.07 mode specs (expansion, consolidation) | `plan/phase-0a06-visual-modes.md`, `plan/phase-0a07-mode-consolidation.md` |
| Git flow, `PP.FF.BB` versioning (`FF` hex from phase 10), per-phase tags | `plan/git-and-versioning.md` |
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
10. **Phase 7 (done):** docs + maintainability, **no behavior change**. New `plan/architecture-and-code-flow.md` (runtime flows, framework diagrams, "where to start reading"). **Magic-number policy** (two-tier): shared/cross-mode tunables → `UPPER_SNAKE_CASE` in `config.py` (`REDUCE_MOTION_BURST_DIVISOR`, `IDLE_LINE_HUE`, `PARTICLE_BRIGHTNESS_FLOOR`, `CIRCLE_*`, `SMOOTHING_*_AT_0/1`, `SENSITIVITY_*`); mode-local "feel" numbers → commented `_UPPER_SNAKE` module constants. Dedup `_range_energies` → `_helpers.range_energies`. **Formatting stays black/ruff** (locked); space-inside-brackets style declined as incompatible.
11. **Phase 8 (done):** two new beam modes + particle trails. `lightshow_2` — radial beams made of pulsing particles (per-beam **Beads** count option), shapeable **Core** (Disc/Hollow/Waveform/Burst), optional **Emit** of small sparks. `laser_2` — rotating beams + selectable **Shape** (Lissajous/Rose/Star/Spiral/Heart), optional **Emit**. New reusable `SparkField` (free particles, normalized space) + shared `TRAIL_OPTION` (fading "shadow" trail) in `_helpers.py`; shared caps `SPARK_*` in `config.py`. **14 modes total.** Keep `plan` §3.3 modes table in sync.
12. **Phase 9 (done):** global **RenK logo overlay** (`visuals/logo.py` `RenkLogo`) drawn by `app.py` **over every mode** (NOT a `@register`ed mode) — slow circling spin (+bass), energy pulse, optional beat **emit** (reuses `SparkField`); composited **additively** (neon-on-black, no box). Configurable via the `RenK` modal (`ui/logo_panel.py`): Show, Color (Default ↔ Rainbow+ luminance tint), Transparency, Size, Position (center+corners), Emit — all persisted (`Settings` schema **v2**, `logo_*`). **About** modal (`ui/about.py`) shows owner/license/version/build date (`APP_OWNER`/`APP_BUILD_DATE`). **ESC no longer quits** (closes modal / exits fullscreen only; quit = Quit button or Ctrl+Q). Bundled asset `audio_visualizer/assets/renk_logo.png` via new `resources.py` (+ spec `datas`). Shared `LOGO_*` in `config.py`. **Still 14 modes** (the logo is an overlay, not a mode). **v00.09.01 fixes:** `Menu` dropdown groups Start/Stop+Fullscreen+Quit; logo scaling **preserves aspect** (round ring, not squished); **six** size presets (Tiny→Huge); **Rainbow+** is a swirling multi-color glow (per-pixel hue map = angle + radius, + time phase, via a 256-entry LUT) instead of one flat hue. **v00.09.02:** re-baked `renk_logo.png` to a true circle. **v00.09.03 (GUI polish):** all widgets draw via one `ui/style.py` in a user-selectable **Flat/Glass** look + **Mono/Sans** font (`ui/fonts.py`, `SysFont`), chosen in the **Appearance** modal (`ui/appearance_panel.py`, Menu → `Appearance…`; `Settings` schema **v3** `ui_style`/`ui_font`). Dropdown text **truncates** (ellipsis) + open list stays on-screen; the control bar **flows/wraps** so nothing spills off-window (`ControlBar.content_height` → dynamic `Layout.compute(control_bar_height=…)`). Sens/Smooth/Size/Speed are compact `− Name 0.00 +` steppers. **App/window icon** = `assets/renk_icon.png` + `assets/icon.ico` (built by `tools/prep_icon.py`, Pillow dev-only).
13. **Phase 10 (done) — `v00.0A.00`:** **global background layer** (`visuals/background.py` `Background`) drawn by `app.py` **BEHIND every mode** (NOT a `@register`ed mode; composited first — modes never clear the canvas so it shows through): **black** (default no-op), **spectrum** (thin colorful magenta→cyan EQ along the bottom, height **Low/Medium/High/Tall**), **gradient** (calm vertical tint), **aurora** (drifting additive blobs). Plus an **accent color** — **Cyan**/**Aurora** (magenta→cyan **gradient** glow, real gradient borders+fills)/**Neon green** — implemented once in `ui/style.py` (`STYLE.accent`/`accent_grad`, `set_accent`). All chosen in the **Appearance** modal (new rows: Accent, Background, Spectrum height) and persisted (`Settings` schema **v4**: `ui_accent`/`bg_mode`/`bg_height`). Shared `UI_ACCENT_*`/`BG_*` in `config.py`. **Versioning:** `FF` is now **hex** from phase 10 (`0A`); the spec parses `PP.FF.BB` **base-16**. **Still 14 modes** (background + logo are overlays, not modes). **v00.0A.01:** four more backdrops — **filaments** (hair-thin rainbow lines), **mirror** (top+bottom spectrum), **ribbon** (scrolling waveform), **starfield** (twinkle on treble/onset), **vignette** (edge glow pulsing on beats); a dedicated **`BG`** button + **Background modal** (`ui/background_panel.py`) with **mode / sensitivity / opacity / height** (settings **schema v5** `bg_sensitivity`/`bg_opacity`); background settings left the Appearance panel. **Aurora reacts to music** (beats push blobs off-path + swell size). **Glass radius capped** so modal panels stay rounded rects, not lozenges. Future ideas (sound-source picker, custom presets, randomize/auto-cycle) are planned in `plan/phase-0b-candidates.md` for `v00.0B.00`. **v00.0A.02:** six new modes (**14 → 20**) — `spectrogram` (scrolling heatmap), `radial_spectrum` "Audio Sun" (radial spectrum bars + core), `plasma` (bass sine-field, low-res upscaled), `tunnel` (rings flying outward, beats spawn; `STROBES`), `fireworks` (onset rockets bursting via `SparkField` + gravity), `kaleidoscope` (mirrored/rotated wedge mandala). The catalog of shipped + proposed visuals lives in `plan/visual-mode-ideas.md` — **read it before generating new concept art** so ideas don't repeat. **v00.0A.03:** mode polish + more `OPTIONS` — Kaleidoscope rebuilt to draw mirrored spokes **directly as lines** (no per-frame surface rotate; ~4 ms/frame at 16 seg/1080p, AA edges) + **Center** ornament option; Plasma gained **Material**/**Flow**/**Intensity**/**Drops**; Audio Sun core is two animated **Disks** (spin/counter/still/radiate); Tunnel **Rings** style (full/broken/waveform-shaped); Spectrogram **Heat** palettes + **Butterfly** layout + beat-brighten + glowing leading edge; Spectrum **Width** (finer bars). RenK logo: **Spin** direction (cw/ccw) + **Micro** size (`Settings` schema **v6**, `logo_spin`). **v00.0A.04** fixes: Audio Sun core back to two smooth rings + glow (**Core** = Rings/Counter/Glow/Radiate; dropped the wheel+spokes); Kaleidoscope **Glow** square fixed (halo surface was clipping its largest circle) + **Spin** Solid/Counter (inner half counter-rotates); Plasma **Radial** no longer aliases (was growing coords unbounded -> now a bounded breathing zoom; higher grid res + capped turbulence); Tunnel **Width** Depth/Thin/Normal/Thick; Spectrum **None** gap (dense hairline lines). **v00.0A.06:** six new modes (**20 → 26**) — `terrain` "Synthwave Horizon" (scrolling neon mountains from a music-fed height-field + cached retro sun/sky + grid floor or reflection), `vectorscope` (XY phosphor Lissajous scope with cheap persistence bounded to the scope square; ~9.6 ms/frame at 1080p — the heaviest of the six), `meters` (frequency-grouped VU ladders/bars/needles + peak-hold), `matrix` (LED dot panel: columns EQ or scrolling dot-spectrogram), `pulse_rings` (concentric per-band breathing rings + outward beat pulses), `ripples` (beat-born expanding shockwaves). New **shared option presets** in `visuals/_helpers.py` (`COLOR_OPTION`, `MIRROR_OPTION`, `GLOW_OPTION`, `THICKNESS_OPTION`, `SPEED_OPTION` + `mode_color()`) so option names/values stay consistent across modes. A new option-sweep test renders **every choice of every option** of each new mode. **v00.0A.07:** **mode consolidation** (**26 → 19**) — merged the `*_2` "+particles" pairs into their base via a shared **`PARTICLES_OPTION`** (Off·Sparse·Dense) axis: `waveform` (absorbs `waveform_2`), `lightshow` (absorbs `lightshow_2`; `Off`=clean solid beams, on=bead beams that emit), `laser` (absorbs `laser_2`; keeps **Shape**). The four circle modes collapsed into **`waveform_circle`** "Waveform Rings" with a **Rings (1·3·6·12)** count (1=single ring, more=per-band concentric). `particles` absorbs `particles_spiral` via an **Emitter (Field·Spiral)** option. Every merged mode gains a **`PRESETS`** dict + a leading **Preset** dropdown (first choice = no-op "Custom"); preset handling lives in `BaseVisualizer.on_option_change`/`_apply_preset` (override `on_option_change` → call `super()`). **Mirror** retrofit on Spectrum/Vectorscope, **Glow** on Spectrum/VU Meters. Per-mode option indices were never persisted, so **only the active mode key migrates** (`Settings` schema **v6→v7**, remap via `MERGED_MODE_KEYS` in `config.py`). 7 mode files deleted; see `plan/phase-0a07-mode-consolidation.md`. **v00.0A.08 (cleanup):** no new features — full code audit + doc sync. Reduce-motion now re-caps `RingPops`/`SparkField` live (mid-session toggle), `Particles` clears the inactive pool on emitter/preset change, removed dead constants (`HOP`, `CIRCLE_RINGS_MAX`), *Fireworks* uses shared `ONSET_THRESHOLD`, long draw methods split, and README/plans/skill/rules brought in sync with the 19-mode codebase (schema 7).

## Implementation checklist (rules that matter)

1. **Loopback via interface:** all audio through `AudioSource`; `App`/`Analyzer` never import `pyaudiowpatch` directly. Use `SyntheticSource` for tests/CI/`--selftest`.
2. **Tiny audio callback:** copy samples into a bounded ring buffer; no allocations/blocking; heavy DSP off the callback.
3. **Pure DSP:** `analysis.py` is numpy-in → `AnalysisFrame`-out, no pygame/I/O.
4. **One file per visual mode**: subclass `BaseVisualizer` + `@register(key, display_name, order)`; `discover()` auto-imports. **Adding a mode must require zero edits elsewhere** (no central list, no `config.py` change). Modes read size from the surface, take only `AnalysisFrame`+`dt`, and are caught fail-soft if they raise.
5. **`app.py` is wiring only**; logic lives in `audio/`, `visuals/`, `ui/`.
6. **No magic numbers/strings.** Shared/cross-mode tunables → `UPPER_SNAKE_CASE` in `config.py` (FFT size, FPS, colors, smoothing, sensitivity, shared visual constants); mode-local "feel" numbers → commented `_UPPER_SNAKE` constants atop the mode file. Mode keys live on the class via `@register`, never in `config.py`.
7. **Logging not print**; `--debug` → DEBUG to console + `logs/app.log`; **F3** debug overlay.
8. **Fail-soft:** capture/device errors → on-screen banner, app keeps running. Global `sys.excepthook` logs tracebacks; close the stream in `finally`.
9. **Silence is a state, not a bug:** loopback often gives silence/no callback — show an idle animation, guard DSP against NaN/div-by-zero.
10. **Negotiate format + mono downmix** to float32 `-1..1`; never assume 48 kHz stereo. Carry real `sample_rate` in `AnalysisFrame`.
11. **DPI awareness + resizable window**; render at **native size** (no `SCALED`/upscaled buffer → no blur); recreate surface + recompute layout on `VIDEORESIZE`; enforce a min size. **Fullscreen = borderless desktop by default** (exclusive optional in settings).
12. **Reduce motion** option (caps particle count + disables strobe) + one-time **photosensitivity notice** shown before any mode with `STROBES = True`; no seizure-risk strobing by default.
13. **Settings JSON** in `%APPDATA%` with `schema_version`; migrate-or-default, never crash on a bad file.
14. **Keep `--selftest` green** — it is the cheapest proof the app runs.

## UI / buttons (shipped intent)

- Top control bar (auto-hides in fullscreen): a **`Menu`** dropdown groups **Start/Stop, Fullscreen, Appearance…, Quit**; plus ‹ / › mode + mode picker, Sens/Smooth/Size/Speed `− value +` steppers, color/option dropdowns, `Motion`, and the `RenK` / `About` buttons. Widgets **flow/wrap** to the window width (never spill off-screen) via `ui/controls.py`; positions/sizes come from `ui/layout.py` (size-relative; resize-safe). The look (Flat/Glass) + font (Mono/Sans) are user-selectable in the Appearance modal.
- Keyboard: `Space` start/stop, `←/→` or `[ ]` modes, `1`–`9` jump mode, `F11` fullscreen, `Esc` **only closes a modal / exits fullscreen — never quits** (quit = `Menu` ▸ Quit or `Ctrl+Q`), `F3` debug overlay.
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

- Update `plan/*` (esp. decisions §8, `audio-visualizer-plan.md` §3.3 modes table, `visual-mode-ideas.md`, and `git-and-versioning.md`) and this skill whenever capture strategy, modes, tooling, packaging, or the git/versioning flow change. Keep the layout doc's tree/diagram accurate and the §3.3 / architecture §6.6 mode tables in sync with the registry (the single source of truth).
