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
**Auto-cycle ("shuffle", v00.0B.03–08):** an `Auto` toggle + `Prev`/`Next` buttons +
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

**Build 11 (v00.0B.13):** **Beat Buttons** — music auto-presses actions. `beat_trigger.py` (`BeatTrigger`,
pure/testable) fires an action when a band's energy spikes above `baseline*ratio` + floor + a per-level
**cooldown** elapsed; silence emits nothing. Two actions wired: `randomize` (`_randomize_current_mode`)
and `next` (`_shuffle_next`). Config in `BEAT_*` (`config.py`); `App._update_beat` ticks each frame
(suppressed while a modal/notice is up). Persisted in `Settings`, off by default.

**Build 12 (v00.0B.14):** Beat Buttons polish. Moved to a `Beat…` **control-bar button** next to Shuffle
(no longer in the Menu). Sensitivity ladder expanded to `Off/Min/Slow/Low/Med/High/Fast/Max` (Min ≈ ~8s
apart, Max ≈ ≤3/s). Each action picks a **band** (`All/Bass/Mid/High`) — `BeatTrigger.update` now takes
`band_energies` and detects per-band energy-vs-baseline (`cycle_band`). Optional **on-screen indicator**
(`ui/beat_indicator.py`, off by default): a pulsing dot, hue by band, brightness/size by intensity,
white flash on fire; toggle + position (corners/center) in the panel. The engine exposes
`intensity`/`active_band`/`flash`. Persisted `beat_bands`/`beat_indicator`/`beat_indicator_pos` (schema **v14**).

**Build 13 (v00.0B.15):** Intensity + UI-control polish. **Plasma** intensity now goes
`Soft/Normal/Vivid/Intense/Blast/Max`. **VU Meters** needle adds `Dual ×2` — `Dual` sheds Spark off
**one** tip, `Dual ×2` off **both** (Spark On/Off unchanged). New **Sensitivity band** dropdown in the
control bar (`all/bass/mid/high`): scales only that third of the spectrum (`App._apply_sensitivity`,
`SENS_BANDS`, persisted `sens_band`). Beat ladder extended + lowered to
`Off/Min/Low/Med/High/Fast/Rapid/Max/Wild/Insane` — the top levels drop the threshold ratio toward (and
below) 1.0 so they still fire on compressed/steady music. **Beat panel** now uses **dropdowns** (not
click-to-cycle) for each action's band + sensitivity and the indicator position; the indicator stays an
On/Off toggle (schema **v15**).

**Build 14 (v00.0B.10):** Frequency **`Direction`** option (`FREQ_DIRECTION_OPTION` + pure
`freq_order(n, direction)` in `visuals/_helpers.py`): `Low→High` / `High→Low` / `Center→Out` /
`Out→Center`. The folded layouts mirror the spectrum about center (each half spans the full range at
~half resolution). Added to the **bar-style frequency modes only** — **Spectrum**, **VU Meters**
(reorders along the `Layout` axis), **Dot Matrix** (Columns) — by reading `bands[order[i]]`. Radial
(Audio Sun / Light Show) and time-axis modes (Waveform / Synthwave Horizon / Spectrogram) are *not*
frequency-along-an-axis, so they're excluded (they offer `Mirror` for center symmetry). No schema change.
**Versioning fix:** `BB` is HEX — builds 8–13 were mis-numbered decimal `.10`–`.15` and were re-tagged to
hex `.0A`–`.0F`; this build is the real hex `.10` (=16). Count `… 09, 0A, 0B, … 0F, 10` going forward.

**Build 16 (v00.0B.12):** **Look history** — a `Prev` button (control bar, next to `Auto`/`Next`) backed
by a session, in-memory, browser-style back/forward queue (`App._history` + `_history_pos`,
`_commit_history`/`_history_back`/`_history_next`/`_apply_history`). Any action that produces a new look
(`Rnd`, a produced `Next`/`Auto` item, a manual mode switch, selecting a saved look) commits a `Look`
snapshot; `Prev` steps back, `Next` replays forward then produces fresh at the end, and producing from a
back position **truncates the forward branch** (`Rnd` after `Prev` keeps earlier history, drops redo).
`Auto` always produces fresh (no replay). Cap `HISTORY_MAX = 200`, never persisted. A **`pos/total`
chip** between Prev/Next (`ControlBar.set_history`, `App._history_goto`) shows the position and is
click-to-edit to jump (1-based, clamps past-the-end to latest, ignores non-numeric). **Plasma** drops the
`Soft` intensity (perf cost; `Normal` is the new default). Tests: `test_history_phase0b16.py`.

**Build 17 (v00.0B.13):** UI highlights + new effects + more colors. (1) `ControlBar.set_state` takes
`beat_active` → the `Beat…` button gets accent fill when any beat action is enabled, and `Motion+` is
highlighted only in the `+`/full-motion state (`_reduce.active = not reduce_motion`). (2) Beat panel adds
**Fade** (`BEAT_FADE_CHOICES` → `BeatTrigger.set_flash_tau`, scales the indicator flash decay) and
**Shape** (`BEAT_INDICATOR_SHAPES`: dot/ring/pulse/diamond/star/burst); `ui/beat_indicator.py` now draws on
an `SRCALPHA` layer with an alpha envelope + expanding halo. (3) `RenkLogo` gains stackable effects
`fx_shockwave` (expanding ring on a beat, additive), `fx_glow` (extra additive brightness pass that decays)
and `fx_throb` (continuous size breathing) — new logo-panel rows, captured by looks. (4) New color schemes:
curated `THEME_PALETTES` (sunset/ocean/forest/fire/ice/candy/grayscale) handled in `themed_color`, plus
`solid`/`mono` which read a user **Custom hue** — `Theme.custom_hue`, published each frame via
`_helpers.set_custom_hue`, picked with a `ui/hue_bar.py` `HueBar` in the Appearance panel. Schema **v16**
(`beat_indicator_shape`, `beat_fade`, `color_hue`, `logo_shockwave`/`logo_glow`/`logo_throb`). Tests:
`test_fx_phase0b17.py`.

**Build 18 (v00.0B.14):** beat `Fade` semantics fix + indicator transparency. `Fade` in the Beat panel is
now the **look-change cross-fade duration** (like the Shuffle fade) used when the music fires `Rnd`/`Next`
— `BEAT_FADE_CHOICES` are durations (Cut/0.3/0.6/1.0/1.5/2.5 s); `_auto_advance(fade)` / `_shuffle_next(fade)`
take an override and `_beat_randomize(fade)` snapshot-dissolves a beat `Rnd`. (Build 17 wrongly mapped it to
the indicator flash decay; reverted to the fixed `BEAT_FLASH_TAU`.) New **`Opacity`** dropdown
(`BEAT_INDICATOR_OPACITY_CHOICES`, 25–100%) scales the whole indicator's alpha via a `BLEND_RGBA_MULT`
pass in `draw_beat_indicator(..., opacity)`. Schema **v17** adds `beat_indicator_opacity`. Tests extend
`test_fx_phase0b17.py`.

**Build 19 (v00.0B.15):** New mode **`Liquid Orb`** (`visuals/orb.py`, `@register key="orb" order=82`).
A *filled*, morphing blob: per-vertex radius = a **mirrored** (seamless), circularly `smooth_wave`-d
spectrum rim + a beat-pulse/RMS/breath swell, slowly rotating. Renders a layered radial-gradient body
(nested polygons scaled toward the centroid), a crisp rim, and an additive glow halo. Options `Size`,
`React`, `Surface` (smoothing), `Fill` (Gradient/Solid/Outline), `Glow`; idle = a breathing circle.
Pure single-file add (honors Theme + reduce-motion), **no schema change** — exercised by the existing
all-modes draw/registry suites. **20 modes total.**

**Build 20 (v00.0B.16):** Beat master switch + laser shapes + richer backgrounds. (1) `BeatTrigger`
gains a master `enabled` flag (`set_enabled`/`is_enabled`/`active()` = enabled ∧ `any_enabled`); the
Beat panel adds a top `Beat Buttons: On/Off` toggle (`toggle_enabled` cb) that disables the feature
without clearing per-action band/sensitivity. App uses `_beat.active()` for the `Beat…` highlight +
indicator gate; persisted `beat_enabled` (schema **v18**, default On). (2) **Laser** drops `Web`/`Bloom`
for **Star** (`_star`, spikes ride highs, bass sharpens the inner radius) and **Butterfly**
(`_butterfly`, Temple Fay curve, wings flutter on the beat phase). (3) **Background panel** is now
**dropdowns** (`BackgroundActions` = `set_mode/set_sensitivity/set_opacity/set_height` taking option
keys; numeric keys via `app._bg_num_key`/`:g`) instead of click-to-cycle. (4) Four new backdrops in
`visuals/background.py` (auto-dispatched by `_draw_<mode>`): `waves` (flowing sine bands), `plasma`
(low-res animated field upscaled), `rain` (falling neon streaks, stateful like `starfield`), `grid`
(synthwave perspective floor, scrolls + beat pulse) — added to `BG_MODES`/`BG_MODE_LABELS` + `BG_*`
tuning consts. Tests: `test_fx_phase0b19.py`.

**Build 21 (v00.0B.17):** Easy Solid/Mono color + custom mouse cursor. (1) The Appearance panel's
*Custom color* section pairs the `HueBar` with **Solid/Mono** buttons (`AppearanceActions` gains
`set_color_scheme`; `set_state(values, hue, scheme)` highlights the active one). `app._set_color_hue`
auto-switches a non-pick scheme to `solid` on drag so the bar always takes effect. (2) New custom
cursor overlay `ui/cursor.py` `Cursor` (owned by App, drawn **last** over everything in `_draw` via
`_draw_cursor`): modes `system/dot/ring/comet/spark` (`CURSOR_MODES`), themed + reactive (energy =
`frame.rms`, onset = `frame.onset`), additive glow sprite, comet trail (deque) + spark particles.
`apply_os_visibility(focused)` hides the OS arrow only for a custom mode while focused; `release()`
restores it (called on shutdown + when set back to System). Appearance gains a `Mouse cursor`
cycle row (`cycle_cursor`). Persisted `cursor_mode` (schema **v19**, default `system`). Honors
reduce-motion; fail-soft. Tests: `test_cursor_color_phase0b17.py`.

**Build 22 (v00.0B.18):** Cursor split into shape+effect, dropdown Appearance, color picker popup.
(1) `ui/cursor.py` `Cursor` now has independent **`shape`** (`CURSOR_SHAPES`: system/arrow/dot/ring/
crosshair/star/heart/diamond/triangle, drawn by `_shape_<name>`) + **`effect`** (`CURSOR_EFFECTS`:
none/glow/comet/sparkles/pulse/ripple, drawn by `_fx_<name>`); `set_shape`/`set_effect`, `is_custom`
= shape≠system ∨ effect≠none (gates drawing + OS-arrow hide). Effects layer under the shape and run
even on the system shape. (2) **Appearance panel** rewritten as **dropdowns** (`AppearanceActions` =
`set_style/set_accent/set_font/set_cursor_shape/set_cursor_effect`; built with option lists; mirrors
`BackgroundPanel`). The hue bar + Solid/Mono buttons were **removed** from it. (3) New
`ui/color_picker.py` `ColorPicker` modal (hue bar + preview swatch + Solid/Mono buttons); App opens
it from `_set_color_scheme`/`_cycle_color_scheme` when the scheme is a pick scheme (`_open_color_picker`
closes other modals first; the picker's own scheme buttons call `_pick_color_scheme`, no re-open).
Registered in `_modal_open`/`_close_modals`/`_handle_events`, drawn after Appearance. (4) Settings
**schema v20**: `cursor_mode` → `cursor_shape`+`cursor_effect`, with `_migrate` mapping the legacy
value via `CURSOR_LEGACY_MODE_MAP`. Tests: `test_cursor_color_phase0b18.py`.

**Build 23 (v00.0B.19):** Stereo color, smoother comet, test cleanup. (1) New **`stereo`** color
scheme: `themed_color("stereo", t, …)` lerps two picked hues (`_custom_hue` → `_custom_hue2`) across
position. Second hue lives on `Theme.custom_hue2`, published each frame via `set_custom_hue2`,
persisted as `color_hue2` (schema **v21**), and captured in look snapshots. `ColorPicker` gained a
**Stereo** button + a second hue bar (Left/Right channel) and a gradient preview; its layout is now
`_layout(canvas)` returning a rect dict (height grows when stereo adds the 2nd bar);
`ColorPickerActions` gains `set_hue2`; App `_set_color_hue2` switches the scheme to stereo on drag.
(2) **Comet cursor trail** rewritten to be time-based: `self._trail` holds `{x,y,age}` dicts; each
frame ages points, drops past `CURSOR_TRAIL_TTL` (so it fades when the mouse stops), bounded by
`CURSOR_TRAIL_MAX`. Rendering uses a **Catmull-Rom** spline (`_catmull_rom`, `CURSOR_TRAIL_SUBDIV`)
with tapering width + age alpha. (3) **Tests:** the duplicated per-module pygame init/quit fixture is
now one module-scoped autouse `_pygame_ready` in `tests/conftest.py` (also runs `registry.discover()`);
added a `make_frame` `AnalysisFrame` factory fixture; ~25 local fixtures removed. Tests:
`test_stereo_comet_phase0b19.py`.

**Build 24 (v00.0B.20):** Global **Foreground layer** — counterpart to `Background`, drawn as the
**last** canvas layer (above mode + logo, below UI chrome). `visuals/foreground.py::Foreground` is a
read-only render helper (`draw(surface, frame, dt)`), fail-soft, bounded. Effects are **beat-triggered**
(onset ≥ `ONSET_THRESHOLD` past `FG_TRIGGER_COOLDOWN`): **`lightning`** (jagged forked
midpoint-displacement bolts + a brightness-capped flash, `FG_FLASH_ALPHA_CAP`), **`flames`**
(additive particles shot inward from edge(s) + ambient trickle), **`rain`** (continuously maintained
directional streak field + per-beat gust), **`meteors`** (fast per-beat streaks with tapered trails),
**`shockwave`** (expanding rings from center / edge midpoint, build 25 / v00.0B.21), **`sparks`**
(gravity-pulled embers, snappier than flames), **`fireworks`** (per-beat radial shell bursts), and
**`edgeglow`** (border bloom that throbs on the beat; safest, no strobing — build 26 / v00.0B.22).
Global knobs: `intensity`, `opacity`,
`direction` (`random/top/bottom/left/right/all/center`; `center` = radial origin for shockwave/
fireworks + all-borders for edgeglow, treated as random by directional effects), plus (build 27 /
v00.0B.23) **`color`** (`auto`/`theme`/named hue via `FG_COLOR_RGB`; resolved per effect by
`Foreground._base_color` for line effects and `_ramp_color` for particle ramps) and **`flash`** (the
lightning white-flash level 0..1, independent of opacity; Off/Low/Medium/Full). Add an effect = one
`_draw_<mode>` method + a `config.py` `FG_*` block + one line in `FG_MODES`/`FG_MODE_LABELS` (the
`ForegroundPanel` auto-lists it). Control-bar **`FG`** button opens `ui/foreground_panel.py` (mirrors
`background_panel`; dropdowns mode/intensity/direction/color/opacity/flash/reactivity/wind). Also
**combo modes** (`storm` = rain+lightning, `party` = edgeglow+fireworks+sparks) defined once in
`FG_COMBO_MEMBERS` and dispatched by `draw()` (one shared beat → several `_draw_<mode>` handlers);
**`reactivity`** scales the effective onset threshold + spawn cooldown (FG-only sensitivity); **`wind`**
is a steady horizontal accel applied to free-flying particles (rain/meteors/embers/sparks/fireworks).
Persisted as `fg_*` (settings **schema v23**: `fg_color`, `fg_flash`, `fg_reactivity`, `fg_wind`) + in
Look snapshots. **v00.0B.23 polish:** Lightning+ (tapered sharp tips, multiple branching forks,
bottom-strike impact burst), Flames+ (turbulence/buoyancy + white-hot core), Meteors+ (age-faded tails
+ shed embers + variable life + graceful head fade), Shockwave `random` re-rolls origin per ring (was
center), Edge Glow smoothstep falloff + continuous RMS-level floor. Reduce-motion halves the flash and
caps counts. Tests: `test_foreground_phase0b20.py` … `test_foreground_phase0b23.py`.

**Build 28 (v00.0B.24):** **Ten new visual modes** (Phase 0B-d), each a single `@register` file, 6
`OPTIONS` + 3 `PRESETS`, within budget, cross-checked against concept art via the new headless dev
tool `tools/preview_mode.py` (renders a mode to PNG; not shipped). They ship under **temporary
`Test_` display names / `test_` keys** pending visual approval — removing the prefix later is a pure
rename (no schema change; settings stay **v23**). The modes: `test_aurora_veil` (band-reactive aurora
curtains over stars, low-res field), `test_hyperspace` (radial warp streaks; `STROBES`),
`test_skyline` (neon EQ city + water reflection), `test_dna` (beaded double-helix + spectrum rungs),
`test_harmonograph` (damped-Lissajous pen plotter + phosphor), `test_metaballs` ("Lava Lamp" gooey
blobs, low-res field), `test_tree` (L-system tree; sway + blossoms), `test_flowfield` (curl-field
particle streams + silky trails), `test_constellation` (node graph + proximity links + ripples),
`test_mandala` (k-fold petal bloom). New shared `_helpers.py` presets used across them:
**`PALETTE_OPTION`** (Theme + 6 `SHARED_PALETTES`) + **`palette_or_theme()`**, and
**`SYMMETRY_OPTION`** (4/6/8/12-fold). Concept art lives in `assets/concept-art/`. Tests:
`test_modes_phase0bd.py` (registration, idle/active render × both motion settings, every option
choice, preset application, metaball field threshold). **30 modes total** (20 + 10 `Test_`).

### Test conventions (Phase 0B.19+)
- `tests/conftest.py` owns the **headless SDL env** + a **module-scoped autouse `_pygame_ready`**
  fixture (pygame init + dummy display + `registry.discover()`); test modules must **not** redefine
  it. Use the **`make_frame`** fixture for `AnalysisFrame` instances instead of a local factory.

### UI control idiom (toggle vs dropdown vs stepper)

Pick the control by the shape of its choices — keep this consistent across the bar and the modals:

- **Toggle (`Button`/`LockToggle`)** — exactly **two states** (On/Off, held/free). One click flips it.
- **Dropdown (`ui/dropdown.py`)** — **3+ discrete named choices** (mode, color scheme, band, sensitivity,
  indicator position, per-mode `OptionChoice` sets). Prefer this over click-to-cycle: the full list is
  visible, selection is one click, and there's no hunting by repeatedly clicking. **Don't** reintroduce
  click-to-cycle for 3+ options. In a modal, draw closed dropdowns first and the open one **last** (on
  top), keep only one open at a time, and `set_bound_right` so the list stays on-screen.
- **Stepper + chip (`Button −/+` + `ui/chip.py`)** — a **continuous numeric** value (Sens/Smooth/Size/
  Speed); the chip also accepts typed entry.

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
