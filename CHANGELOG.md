# Changelog

Version scheme `PP.FF.BB` — `PP` pre-release (`00` until ship), `FF` development
phase, `BB` build within the phase. The string lives once as `APP_VERSION` in
`config.py`. Each completed phase is tagged with an annotated git tag
`v<APP_VERSION>` (e.g. `v00.02.00`), so entries below map 1:1 to tags. See
`plan/development-phases.md` and `plan/git-and-versioning.md`.

All three initial phases were implemented in one pass; the entries below record
what each phase delivered and its verification results.

---

## `00.0B.05` — Phase 0B-c (build 3): looks/shuffle fixes + bigger Vectorscope

Three fixes on top of `00.0B.04`.

- **My Looks dropdown no longer "swaps" with one save.** Saving a look now **bookmarks** it
  without auto-activating, so you stay on **None / Live**. Previously a fresh save activated the
  look *and* captured a baseline equal to it, so "None / Live" restored the saved snapshot (and
  re-picking the active look was a no-op) — which read as the two entries being swapped. Now the
  saved look is a distinct entry: selecting it applies the look; **None / Live keeps your live
  edits** (the pre-look state) instead of reverting to the save.
- **Shuffle can randomize mode options.** New **`Randomize mode options: On/Off`** toggle in the
  `Shuffle…` modal: when on, landing on a built-in mode also rolls that mode's own options (e.g.
  Ripples' spawn origin). A mode's `preset` option is forced to **Custom** so siblings stay free.
  **Background and Logo are never touched** by this; saved looks keep their captured options.
  Persisted as `random_options` (settings schema **v10 → v11**).
- **Vectorscope fills the scope.** The XY trace now **auto-gains** to each frame's peak (with a
  floor so quiet passages stay modest), so a typical sub-unity waveform fills the figure instead
  of a tiny central blob, and the scope radius grew (`0.40 → 0.46` of the smaller window edge).
- Tests: updated the looks save/select cases for the new "stay on live" semantics, added settings
  round-trip + app-level coverage for randomize-options (on/off), and a Vectorscope fill smoke.

---

## `00.0B.04` — Phase 0B-c (build 2): looks in the shuffle + Next + countdown

Builds on `00.0B.03` so the shuffle is a complete, controllable rotation.

- **Saved looks now join the rotation.** The pool holds both `mode:<key>` and `look:<id>`
  items; the `Shuffle…` checklist lists built-in modes **and** your saved looks (marked **★**),
  with `All` / `None` covering everything. When the shuffle lands on a look it applies the whole
  look (mode + options + theme + Background + Logo), and **stops where it is** when you turn Auto
  off (no hidden state — shuffle simply drives the live global like rapid manual switching).
- **`Next` button + `N` key** to skip ahead to the next rotation item immediately (works whether
  or not Auto is running; resets the interval timer). The Shuffle modal also has a **Next ⏭** button.
- **Small `Auto · next in Ns` chip** in the canvas's top-right while shuffle is running (shows
  `switching…` during a fade), so you can see when the next change is coming.
- **Cross-fade reworked to a frozen-snapshot dissolve** (`visuals/_transition.py`): a switch grabs
  the current canvas, applies the next item live, then blits the frozen old scene on top at a
  falling alpha. This renders the live scene **only once** (cheaper than the old two-mode blend)
  and dissolves **full looks** (changing Background/Logo/theme) just as cleanly as a mode swap.
  Reduce-motion still hard-cuts. No settings-schema change (v10 already stores tagged pool ids;
  stale `look:` ids are skipped).
- Tests (`tests/test_autocycle_phase0b03.py`, now 21 cases): adds tagged-pool toggle / valid /
  no-repeat picking, **look applied on advance**, **Next** (incl. empty-pool fill), the
  snapshot-dissolve lifecycle, stale-look exclusion, and the countdown overlay.

---

## `00.0B.03` — Phase 0B-c (build 1): auto-cycle ("shuffle")

The visualizer can now **shuffle itself** — automatically switching the active mode
every few seconds with a smooth **cross-fade** instead of a hard cut.

- **New `Auto` toggle + `Shuffle…` button** in the control bar's top row (and the **`A`**
  key toggles Auto). `Auto` paints accent-filled while running.
- **`Shuffle…` modal**: an Auto on/off row, an **interval stepper** (`Every Ns`, clamped to
  `RANDOM_INTERVAL_MIN..MAX`), and a **checklist of which built-in modes are in the rotation**
  (with `All` / `None`). An empty rotation means nothing auto-switches; turning Auto on with
  an empty pool selects every mode so it works out of the box.
- **Scheduler** (`app.py`): while Auto is on, a timer fires every interval and picks the next
  pooled mode at random with **no immediate repeat**. Any **manual** mode change (keys, picker,
  applying a look) **resets the timer and cancels an in-flight fade**, so a shuffle never yanks a
  mode you just chose. Auto-advance **pauses while a modal is open** or the safety notice is up.
- **Cross-fade** (`visuals/_transition.py` + `App._draw_transition`): the outgoing and incoming
  modes render onto opaque copies of a **single** background layer (advanced once) and the whole
  scene dissolves; the RenK logo draws once on top. Two modes are rendered **only** while a fade
  is in flight, so steady-state cost is unchanged. **Reduce-motion** switches with a hard **cut**
  (no double-render).
- **Persistence (settings schema v9 → v10):** the rotation persists as `random_pool` (tagged
  `mode:<key>` ids; `look:<id>` is reserved for a later build, and unknown/stale entries are
  skipped) and `random_interval`. **Auto is never persisted on** — it starts off each launch.
- Tests (`tests/test_autocycle_phase0b03.py`, 15 cases): v9→v10 migration, pool/interval
  round-trip + junk/clamp handling, transition alpha progression, pool toggle / All-None /
  valid-index filtering, interval clamp, cut vs cross-fade, transition lifecycle (exactly one
  active mode), manual-switch cancels a fade, a fade frame renders without error, and the
  Shuffle modal routes its clicks.
- **Deferred to build 2 (after the 0B-b overlay resolver):** **saved looks in the rotation**
  (they mutate live global per tick, so they need the clean pre-shuffle snapshot/restore the
  resolver provides), plus optional dip-to-black / beat-synced transition styles.

---

## `00.0B.02` — Phase 0B-b (build 1): user looks ("My Looks")

You can now **save the current visual look under a name and re-load it later** — the
first slice of the "My Looks" feature designed in `00.0B.00`.

- **New `My Looks` dropdown + `Save…` button** in the control bar's top row (global
  controls, deliberately separate from the per-mode **`Preset`** dropdown in row 2 so the
  two never read alike). The dropdown starts with **`None / Live`**, then your saved looks;
  the active look shows a trailing `*` when it has unsaved edits.
- **A *look* captures a complete look:** the mode + its option indices, the theme
  (size/speed/color), sensitivity/smoothing, and a snapshot of the Background and Logo state.
- **`Save…` modal** to name + save (create-new or **Update** the active look), and manage
  saved looks (load, **Dup**licate, **Del**ete with a click-twice confirm). A small reusable
  **text-input** widget backs the name field (`ui/text_input.py`).
- **Applying a look is an overlay, not a clobber:** entering a look snapshots your live
  state, and selecting **`None / Live`** restores it. Unknown option keys / out-of-range
  values are ignored or clamped, and a missing/renamed mode degrades gracefully.
- **Persistence:** looks live in their own **`looks.json`** (sibling to `settings.json`) with
  their own `schema_version`, atomic writes + a `.bak`, and a lenient load that **skips one
  malformed look** rather than dropping the file. Unknown future keys **round-trip** intact.
  The store also supports export/import a single `.look.json` and guard rails (count cap, name
  sanitize, id dedupe). The last active look persists via **settings schema v8 → v9**
  (`active_look`, stores the stable **id** so a rename never breaks restore).
- Tests (`tests/test_looks_phase0b02.py`, 17 cases): store CRUD/duplicate/reorder/cap,
  JSON round-trip + unknown-key preservation, malformed-record skip, corrupt/missing →
  empty, `.bak` rotation, export/import fresh-id, settings v8→v9 migration, and app-level
  capture/apply round-trip, dirty tracking, baseline restore, and non-fatal missing mode.
- **Deferred to build 2:** per-domain Background/Logo **Local | Global** linking, reorder /
  export / import in the modal UI, name-collision prompts, and shipped read-only starter looks.

---

## `00.0B.01` — Phase 0B-a: selectable sound source

You can now choose **which audio device drives the visuals** instead of always
using the default speakers' loopback.

- **New `Src` button → Sound source modal.** Lists the **default** (system audio), every
  **output** endpoint's loopback (speakers / headphones / HDMI), and real **inputs**
  (microphone / line-in). Click one to switch; the active source is marked.
- **`audio/devices.py`** enumerates sources via `pyaudiowpatch` (`list_sources()`), fully
  defensive — any failure yields an empty list rather than crashing.
- **`LoopbackSource(device_id=...)`** opens a pinned device by **name** (stable across
  replugs, unlike indices) and negotiates its native format → mono float32, exactly as
  before. If the saved device is gone at launch, it **falls back to the default loopback**.
- **Selecting a source** does a clean stop → recreate → start, so it takes effect
  immediately; the choice persists as `source_id` (**settings schema v7 → v8**, migrates by
  defaulting to the system default). The existing error-banner + periodic recovery still
  cover a device that vanishes mid-session.
- Tests: device enumeration (loopback first, inputs filtered/deduped), device resolution
  with default fallback, settings round-trip + v7→v8 migration, and the panel's
  select/dismiss behavior.

---

## `00.0B.00` — Phase 0B kickoff: custom-preset design

Planning checkpoint that opens Phase 0B (`FF = 0B`). **No runtime/behavior change** — only
the design plan and the version stamp move.

- **`plan/phase-0b-candidates.md` — expanded 0B-b ("My modes" user presets).** A preset now
  captures a complete *look* (mode + knobs + theme) and can **optionally** include the global
  **Background** and **Logo**, chosen **per domain** as **Local** (frozen snapshot baked into
  the preset) or **Global** (follow live global).
- **Core invariant recorded:** a preset is a **read-only overlay** — applying/switching one
  **never writes into live global** (a small "effective config" **resolver** sits between the
  overlays and `Settings`). This is what lets a Global-linked domain always re-derive from the
  true, untouched global after another preset pinned it.
- Captured the editing rules (edit a pinned aspect → marks the preset dirty; edit a
  Global-linked domain → edits real global), the JSON record shape, `None / Live` deselect,
  last-active-preset restore on relaunch, degradation rules, and an invariant-focused test list.

---

## `00.0A.08` — Phase 10.08: code cleanup + documentation sync

A maintenance pass: no new modes or user-facing features. Focused on code-quality
fixes surfaced by a full audit, plus bringing the docs/plans/skill/rules back in sync
with the post-consolidation (19-mode) codebase.

**Code cleanup**

- **Live reduce-motion re-capping.** Toggling reduce-motion mid-session now takes effect
  immediately for the shared particle fields: `RingPops`/`SparkField` expose a `cap`
  setter and *Waveform Rings*, *Light Show*, and *Laser* re-apply the reduced cap each
  frame (previously the cap was frozen at construction).
- **Particles emitter lifecycle.** Switching the *Particles* **Emitter** (Field ↔ Spiral),
  directly or via a preset, now clears the inactive pool so dormant particles don't
  reappear on switch-back.
- **Dead code removed.** Dropped the unused `HOP` and `CIRCLE_RINGS_MAX` config constants;
  *Fireworks* now uses the shared `config.ONSET_THRESHOLD` instead of a duplicate literal.
- **Readability.** Split the over-long `particles`/`lightshow` draw methods into focused
  spawn/advance/render helpers; refreshed stale comments/docstrings that named deleted
  modules; added a degenerate-band guard in *Laser*.
- **Tests.** Added coverage for live reduce-motion re-capping and emitter pool clearing.

**Documentation sync**

- **README** rewritten for v00.0A.07 / **19 modes** (was Phase 9 / 14 modes): current mode
  list, per-mode options & presets, appearance/background controls, and settings schema 7
  + mode-key migration.
- **Plans** updated: `architecture-and-code-flow.md` §6.6 modes table (now 19) + presets +
  settings schema; `audio-visualizer-plan.md` §3.3 expanded to all 19 modes, Quit/`Esc`
  row, §3.5/§8 examples, §11.3 persisted fields; `repository-and-code-layout.md` tree +
  test inventory; `development-phases.md` gained a Phase 10 section; `testing.md` test
  layers; `git-and-versioning.md` documents hex `FF` from phase 10; `phase-0b-candidates.md`
  clarifies user presets vs the shipped per-mode `PRESETS`.
- **Skill & rules** updated with a current-state callout, the new shared-option/`PRESETS`/
  `MERGED_MODE_KEYS` patterns, and the mid-session reduce-motion caveat.
- **tools/README** lists `run`/`test`/`lint`/`format`/`build-exe` (and the helper scripts)
  as available.

Verified: `ruff` + `black --check` + `mypy` clean; full pytest suite green; `--selftest`
exits 0; exe builds and self-tests.

---

## `00.0A.07` — Phase 10.07: mode consolidation + smarter options

Merged closely-related modes into single, more flexible ones, cutting the mode list
from **26 to 19** while keeping every look reachable through options. Per-mode option
indices were never persisted, so the only saved state affected is the active mode key,
which is **remapped on load** (settings schema **v6 → v7**).

- **Merged the `*_2` "+particles" pairs** into their base mode via a shared **Particles
  (Off · Sparse · Dense)** axis:
  - **Waveform** absorbs *Waveform 2* — `Off` is the clean trace; on adds popping sparks.
    Also gains a **Mirror** option (Off · Horizontal · Vertical · Quad).
  - **Light Show** absorbs *Light Show 2* — `Off` draws clean solid beams (classic), on
    rebuilds beams from pulsing beads that emit trailing sparks. Keeps the shapeable
    **Core** (Disc · Hollow · Waveform · Burst).
  - **Laser** absorbs *Laser 2* — keeps the selectable **Shape** (Lissajous · Rose · Star ·
    Spiral · Heart); Particles controls whether beams shoot sparks.
- **Waveform Rings** (`waveform_circle`) replaces the **four** circle modes (single /
  single+pops / ×N / ×N+pops) with one: a **Rings (1 · 3 · 6 · 12)** count (1 = single
  oscilloscope ring, more = per-band concentric rings) plus the shared **Particles** axis.
- **Particles** absorbs *Particles Spiral* via an **Emitter (Field · Spiral)** option —
  Field bursts outward with gravity; Spiral blows per-band sparks along rotating arms.
- **Presets** — every merged mode gains a **Preset** dropdown of curated option combos
  (e.g. Waveform: *Plain · Sparks · Mirror*; Waveform Rings: *Single · Bloom · Galaxy*;
  Laser: *Classic · Rose · Star*) for one-click looks; "Custom" leaves options untouched.
- **Shared-option retrofit** — **Mirror** added to *Spectrum* and *Vectorscope*; **Glow**
  (a cheap halo) added to *Spectrum* and *VU Meters*.

**Migration** — old saved mode keys (`waveform_2`, `waveform_circle_2`,
`waveform_circle_multiple[_2]`, `lightshow_2`, `laser_2`, `particles_spiral`) load as
their canonical survivor; any other key (and a fresh install) is unaffected.

**Verification** — ruff / black / mypy **clean**; full suite **passes** (new tests cover
the merges, the v6→v7 remap, preset snapping, and an option-sweep over every merged
mode); `--selftest` exit **0**; exe builds + self-tests.

---

## `00.0A.06` — Phase 10.06: six new visual modes

Six brand-new modes, each with deep per-mode options and built to a strict 1080p
frame budget. New shared, reusable option presets (`COLOR_OPTION`, `MIRROR_OPTION`,
`GLOW_OPTION`, `THICKNESS_OPTION`, `SPEED_OPTION` + a `mode_color()` helper) keep
option names/values consistent across modes.

- **Synthwave Horizon** (`terrain`) — the spectrum as scrolling neon mountains (1–3
  parallax ridges fed by a music-driven height-field) over a cached retro sun and sky,
  with a perspective grid floor or a mirrored reflection. Options: **Layers / Fill
  (Solid·Gradient·Wire) / Sun / Floor (Grid·Mirror·Off) / Speed / Palette
  (Sunset·Ice·Mono) / Caps**.
- **Vectorscope** (`vectorscope`) — XY phosphor scope plotting the waveform against a
  delayed copy (Lissajous loops) with cheap CRT persistence (confined to the scope
  square so the full-canvas blends stay light). Options: **Phase / Trail
  (None·Short·Long) / Draw / Width / Color (Phosphor·Rainbow·Velocity) / Spin / Grid**.
- **VU Meters** (`meters`) — frequency-grouped level meters as LED ladders, bars, or
  needle gauges with instant attack, tunable release, and peak-hold. Options: **Style /
  Meters (4–24) / Segments / Peak / Decay / Layout / Color (Zones·Accent·Per-band)**.
- **Dot Matrix** (`matrix`) — retro LED panel: a columns equalizer or a scrolling
  dot-resolution spectrogram. Options: **Grid / Dot (Round·Square·Diamond) / Gap /
  Color (Heat·Per-col·Solid) / Mode (Columns·Scroll) / Peak / Glow**.
- **Pulse Rings** (`pulse_rings`) — concentric rings that breathe per band; onsets birth
  a bright pulse that sweeps outward. Options: **Rings / Draw (Outline·Filled·Dashed) /
  Width / Spin / Color / Beat**.
- **Ripples** (`ripples`) — beat-born shockwaves that grow and fade. Options: **Spawn
  (Onset·Beat-grid·Continuous) / Origin / Style (Ring·Double·Filled) / Max / Speed /
  Color**.

**Performance** (1080p, headless, per-frame): terrain ~2.9 ms, vectorscope ~9.6 ms
(heaviest, persistence path; bounded to the scope square), meters ~4.6 ms, matrix
~2.5 ms, pulse_rings ~0.6 ms, ripples ~0.1 ms — all within the 60 fps budget.

**Verification** — ruff / black / mypy **clean**; full suite **passes** (incl. an
option-sweep test that renders every choice of every option); `--selftest` exit **0**;
exe builds + self-tests.

---

## `00.0A.05` — Phase 10.05: Audio Sun & Kaleidoscope fixes

- **Audio Sun** — the core glow was blitting **additively** and oversized, so it read as a
  big solid blue disc. Restored the softer **v00.0A.02** halo (normal alpha blit, sized so
  nothing clips) behind the two color rings.
- **Kaleidoscope** — in **Counter** spin the outer spokes were being cut by other segments'
  inner spokes; now drawn in two passes (all inner halves first, then all outer halves on
  top) so the outer layer is never clipped.

**Verification** — ruff / black / mypy **clean**; full suite **passes**; `--selftest` exit
**0**; exe builds + self-tests.

---

## `00.0A.04` — Phase 10.04: mode fixes & feel tweaks

- **Audio Sun** — dropped the dashed color-wheel + inner spokes (they looked off);
  the core is back to two **smooth concentric rings** + a soft glow whose colors flow
  around the circumference. **Core** option: **Rings** / **Counter** (inner ring flows
  the other way) / **Glow** (plain halo, the classic look) / **Radiate** (beat rings).
- **Kaleidoscope** — fixed the **Glow** center rendering as a square (the halo circle was
  larger than its own surface and got clipped); the glow surface is now sized correctly.
  New **Spin** option: **Solid** (whole figure rotates) or **Counter** (each spoke's inner
  half counter-rotates against its outer half).
- **Plasma** — fixed the **Radial** flow looking grainy/distorted (it grew the coordinates
  without bound, so the field aliased over time); it's now a smooth bounded breathing zoom.
  Raised the field resolution and capped turbulence so **Soft** intensity stays smooth too.
- **Tunnel Warp** — new **Width** option: **Depth** (thickness grows with the ring radius,
  the old non-uniform look) or uniform **Thin / Normal / Thick**.
- **Spectrum** — added a **None** gap choice (no spacing); pair with **Hairline** width for
  dense, fine lines.

**Verification** — ruff / black / mypy **clean**; full suite **passes**; `--selftest` exit
**0**; exe builds + self-tests.

---

## `00.0A.03` — Phase 10.03: mode polish, more options & a faster Kaleidoscope

**Changed / fixed**
- **Kaleidoscope** — rebuilt to draw mirrored spokes **directly as lines** (computing
  rotated/reflected endpoints) instead of rotating a full-canvas surface every frame:
  ~**4 ms/frame** at 16 segments / 1080p (was choppy) and the edges are now anti-aliased.
  New **Center** ornament option: Disc / Ring / Glow / Off; **16** segments added.
- **Plasma** — now has **Material** (Marble/Oil/Water/Lava/Silk, each its own palette +
  feel), **Flow** direction (Drift/Right/Up/Swirl/Radial), **Intensity** (Soft/Normal/Vivid
  contrast + turbulence), and an optional **Drops** overlay (Ripple / Rain / Blobs).
- **Audio Sun** — the core is now two animated disks (segmented outer ring + spoked inner
  disk) with a **Disks** option: Spin / Counter / Still / Radiate (beat rings).
- **Tunnel Warp** — new **Rings** style option: Full / **Broken** (gapped arcs / dashed
  polygons) / **Waveform** (each ring frozen into the waveform shape at its birth).
- **Spectrogram** — more lively: **Heat** palettes (Neon/Fire/Ice), **Layout** Up or
  **Butterfly** (bass-in-the-center mirror), beats brighten the column (`peak`), and the
  newest "now" column glows as a bright leading edge.
- **Spectrum** — new **Width** option (Hairline/Fine/Normal/Full) for finer, thinner bars.
- **RenK logo** — new **Spin** direction (Clockwise / Counter-CW) and a new **Micro** size
  (smaller than Tiny). Persisted (`Settings` schema **v6**, `logo_spin`).

**Verification** — ruff / black / mypy **clean**; full suite **passes** (schema-version
tests updated to v6, logo-panel test covers the new Spin row); `--selftest` exit **0**; exe
builds + self-tests.

---

## `00.0A.02` — Phase 10.02: six new visual modes

**Added** — six new modes (each one new file, auto-registered; **14 → 20 modes**):
- **Spectrogram** (`spectrogram`) — a scrolling magnitude heatmap (frequency on Y, time
  scrolling on X), intensity heat ramp.
- **Audio Sun** (`radial_spectrum`) — spectrum bars radiating from a glowing core, hue swept
  around the ring, with a faint oscilloscope ring; optional mirror symmetry.
- **Plasma** (`plasma`) — a bass-reactive sine-interference color field (computed small,
  upscaled), neon or rainbow tint.
- **Tunnel Warp** (`tunnel`) — concentric rings flying outward from a vanishing point; energy
  speeds the rush and beats spawn rings (circle/hexagon/square). Flagged `STROBES`.
- **Fireworks** (`fireworks`) — onsets launch rockets that burst into gravity-driven spark
  showers with ember trails; burst size scales with `peak`.
- **Kaleidoscope** (`kaleidoscope`) — an audio-driven wedge mirrored/rotated into a rotating
  symmetric mandala (6/8/12 segments).

**Docs**
- New `plan/visual-mode-ideas.md` — the catalog of shipped + proposed visualizations, and the
  reference to consult before generating new concept art so ideas don't repeat.

**Tests / verification**
- Added `tests/test_modes_phase1002.py` (each new mode renders idle + active, both motion
  settings); the existing "cycle all modes" smoke test now covers 20 modes. ruff / black /
  mypy **clean**; full suite **passes**; `--selftest` exit **0**; exe builds + self-tests.

---

## `00.0A.01` — Phase 10.01: more backgrounds, a Background panel & a glass fix

**Added**
- **Four new backdrops** (Background panel): **Filaments (hair)** — dense hair-thin
  rainbow lines; **Spectrum mirror** — a spectrum mirrored top + bottom; **Waveform
  ribbon** — a scrolling oscilloscope band along the bottom; **Starfield** — slow
  drifting dots that twinkle on treble/onsets; **Beat vignette** — edge glow that pulses
  on each beat.
- **Dedicated `BG` button** (next to `RenK`) opening a **Background** modal with
  **Background** (mode), **Sensitivity** (reactivity gain), **Opacity** (overall
  strength), and **Spectrum height**. Background settings moved out of *Appearance* into
  this panel; both `bg_sensitivity` + `bg_opacity` persist (settings **schema v5**).
- **Aurora now reacts to music**: beats shove the blobs off their drift path (springing
  back) and loudness swells their size, instead of a fixed path.

**Fixed**
- **Glass control style** no longer turns the **Appearance / About / RenK / Background**
  panels into a lozenge — the glass corner radius is now capped for large surfaces while
  small controls stay full pills (`ui/style.py`).

**Planned (no code yet — see `plan/phase-0b-candidates.md`, targeting `v00.0B.00`)**
- Selectable **sound source** (any render endpoint loopback or input/mic; default
  unchanged); user **custom visual presets** (save/name/load); **randomize/auto-cycle**
  across a chosen set with smooth cross-fades on a user-set interval.

**Tests / verification**
- Added `tests/test_background_phase1001.py` (Background panel rows, opacity scales the
  spectrum alpha, new modes render, glass-radius cap, settings v5 round-trip + snap).
  ruff / black / mypy **clean**; full suite **passes**; `--selftest` exit **0**; exe builds.

---

## `00.0A.00` — Phase 10: global backgrounds & accent colors

**Added**
- **Background layer** (Appearance → **Background**) drawn *behind* every visual mode,
  with the height-controlled spectrum from the concept art:
  - **Black** (default), **Spectrum line** (a thin, colorful magenta→cyan equalizer along
    the bottom edge — height: Low/Medium/High/Tall via **Spectrum height**), **Gradient**
    (calm vertical tint), and **Aurora** (softly drifting additive color blobs).
  - New `visuals/background.py` (`Background`); composited first in `app.py` (modes never
    clear the canvas, so it shows through). Honors the color scheme + reduce-motion.
- **Accent color** (Appearance → **Accent color**): **Cyan** (default), **Aurora**
  (magenta→cyan **gradient** glow — the premium Concept-B look, real gradient borders/fills),
  or **Neon green**. Implemented once in `ui/style.py`.
- All three persist (settings **schema v4**: `ui_accent`, `bg_mode`, `bg_height`).

**Changed**
- Version scheme: `FF` (phase) is now written **hex** from phase 10 (`0A`), so it stays two
  digits; the PyInstaller spec parses `PP.FF.BB` base-16 for the Windows version resource.

**Tests / verification**
- Added `tests/test_background_phase10.py` (black no-op, spectrum paints the bottom edge,
  every backdrop renders, gradient-accent draw paths, settings v4 round-trip + migration).
- ruff / black / mypy **clean**; full suite **passes**; `--selftest` exit **0**; exe builds
  + self-tests.

---

## `00.09.03` — Phase 9 polish: modern GUI, selectable look & font, app icon

**Added**
- **Appearance panel** (Menu → `Appearance…`) to pick the UI look and font live, both
  **persisted** (settings **schema v3**): **Control style** — **Flat** (solid rounded
  panels, crisp borders) or **Glass** (pill-shaped, translucent) — and **Text font** —
  **Mono** (a modern terminal-style monospace: Cascadia/Consolas, like Cursor's terminal)
  or **Sans** (Segoe UI). New `ui/fonts.py` resolves the family via `SysFont`.
- **App / window icon** — the RenK emblem on a rounded badge is set as the title-bar/taskbar
  icon (`assets/renk_icon.png`) and baked into the `.exe` (`assets/icon.ico`, all sizes).
  Reproducible via `tools/prep_icon.py` (Pillow, dev-only).

**Changed / Fixed**
- **No more text spilling out of controls** — dropdown headers and option rows truncate
  with an ellipsis to fit their box, and the open option list is nudged left to stay
  inside the window (item 2).
- **Control bar flows & wraps** — widgets now reflow onto extra rows instead of running off
  the right edge, and the bar grows taller as needed; on small windows everything stays
  on-screen (item 3). `Layout.compute` accepts a dynamic `control_bar_height`.
- **Nicer widgets** — a single `ui/style.py` draws every panel/button/chip/dropdown in the
  chosen style with clear hover/active states and an accent (cyan) highlight; the bar sits
  on a darker strip (`COLOR_BAR`) with a separator so controls read as distinct buttons.
- **Compact value steppers** — Sens/Smooth/Size/Speed are now `−  Name 0.00  +` (name+value
  in the chip), so the wider UI font never truncates them.

**Tests / verification**
- Added `tests/test_ui_phase903.py` (text fitting, flow/wrap + dynamic height, dropdown
  bounds, Appearance panel routing, settings v3 round-trip + migration).
- ruff / black / mypy **clean**; full suite **passes**; `--selftest` exit **0**; exe builds
  + self-tests.

---

## `00.09.02` — Phase 9 fix: RenK logo ring is now a true circle

**Fixed**
- The logo's ring read as an **ellipse** — the source art's ring was ~9% wider than
  tall (measured 1086×995). Re-baked the bundled `renk_logo.png` with a horizontal
  correction so the ring is now circular (993×992, ratio ≈ 1.00). No code/logic change;
  the aspect-preserving scaler now reproduces a true circle.

**Tests / verification**
- `tools\test.ps1` → **112 passed**; ruff / black / mypy **clean**; `--selftest` exit
  **0**; exe builds + self-tests.

---

## `00.09.01` — Phase 9 fixes: Menu group, round logo, more sizes, swirling Rainbow+

**Fixed / changed**
- **Control bar `Menu`** — Start/Stop, Fullscreen, and Quit are grouped into a single
  **`Menu`** dropdown (less clutter); the first item reflects the capture state
  (Start/Stop). Keyboard shortcuts (`Space`, `F11`, `Ctrl+Q`) are unchanged.
- **RenK logo no longer squished** — scaling now **preserves the art's aspect ratio**, so
  the ring renders as a proper circle (was distorted by forcing a square).
- **More logo sizes** — six presets: **Tiny / Small / Medium / Large / X-Large / Huge**
  (height = 15–90% of the min canvas side).
- **Swirling Rainbow+** — the logo's Rainbow+ color is now a **multi-color, radiant glow**
  (hue varies by angle + radius and cycles over time via a precomputed hue map + LUT)
  instead of one flat, uniform hue.

**Tests / verification**
- `tools\test.ps1` → **112 passed** (adds aspect-ratio, size-preset ordering, varied
  hue-map, and `Menu` action-routing tests).
- ruff / black / mypy **clean**; `--selftest` exit **0**; exe builds + self-tests.

---

## `00.09.00` — Phase 9: RenK logo overlay, About dialog & ESC fix

**Delivered**
- **RenK logo overlay** — a global, audio-reactive branding overlay drawn **over every
  visual mode** (not a mode itself). It slowly "circles" (spins, faster on bass), gently
  pulses with energy, and can **emit sparks** on the beat (reusing the shared `SparkField`).
  Implemented as `visuals/logo.py` (`RenkLogo`), owned by the App and composited
  **additively** so the neon-on-black art glows with no bounding box.
- **Fully configurable** via a `RenK` settings panel (modal): **Show** on/off (works in
  all modes), **Color** (Default picture ↔ animated **Rainbow+** via a luminance tint),
  **Transparency** (25/50/75/100%), **Size** (Small/Medium/Large), **Position** (Center +
  4 corners), and **Emit** particles on/off. All preferences **persist** (settings
  schema **v2**, older files migrate by defaulting the new keys).
- **About dialog** (`About` button) — owner, license, version, build date, Python/pygame.
- **ESC no longer quits the app** — it now only closes an open modal or leaves fullscreen.
  Quit remains on the **Quit** button and **Ctrl+Q**.
- Logo art bundled at `audio_visualizer/assets/renk_logo.png` and packaged into the exe.

**Tests / verification**
- `tools\test.ps1` → **108 passed** (adds `test_logo_phase9.py`: logo renders across all
  positions/sizes, disabled/spin/rainbow/opacity paths, emit on onset, reduce-motion
  disables emission, luminance helper, settings round-trip + migration + opacity snap,
  and the panel/About modal interactions).
- `tools\lint.ps1` → ruff **clean**, black **clean**, mypy **clean**.
- `--selftest` → exit **0**.

---

## `00.08.00` — Phase 8: Light Show 2, Laser 2 & particle trails

**Delivered**
- **New mode `lightshow_2` (Light Show 2)** — radial beams built from many pulsing
  particles (per-beam **bead** count is an option); each bead swells/shrinks with the
  music. Beams rotate and grow with energy. The pulsing **core** is selectable between
  **Disc / Hollow / Waveform / Burst** shapes. When **Emit** is on, beam tips shoot out
  smaller free particles.
- **New mode `laser_2` (Laser 2)** — rotating beams plus a selectable parametric
  **figure**: **Lissajous / Rose / Star / Spiral / Heart** (all energy-driven). When
  **Emit** is on, the beams shoot out particles.
- **Particle trails (shadow trails)** — a shared **Trail** option (Off/On). When on,
  emitted particles leave a trail of fading, shrinking "shadows". Implemented once as
  the reusable `SparkField` + `TRAIL_OPTION` in `visuals/_helpers.py`.
- **14 modes total.**

**Tests / verification**
- `tools\test.ps1` → **90 passed** (adds `test_visuals_phase8.py`: `SparkField`
  spawn/advance/decay/cap/trail + render paths, both modes render loud/idle/tiny, all
  core shapes, all figure shapes, Emit spawns sparks, reduce-motion disables emission).
- `tools\lint.ps1` → ruff **clean**, black **clean**, mypy **clean**.
- `--selftest --mode lightshow_2` and `--mode laser_2` → exit **0**.

---

## `00.07.00` — Phase 7: docs, maintainability & magic-number cleanup

No user-facing behavior change — clarity and maintainability only.

**Delivered**
- **New doc `plan/architecture-and-code-flow.md`** — the detailed "how it works": startup
  and per-frame flows, the threading model, the audio/DSP/visual/UI frameworks, mermaid
  diagrams, conventions, and a "where to start reading" map. Linked from the layout doc.
- **Magic numbers → named constants (a common, documented home).** A two-tier policy:
  shared/cross-mode tunables as `UPPER_SNAKE_CASE` in `config.py` (new
  `REDUCE_MOTION_BURST_DIVISOR`, `IDLE_LINE_HUE`, `PARTICLE_BRIGHTNESS_FLOOR`, `CIRCLE_*`
  layout fractions, `SMOOTHING_*_AT_0/1`, `SENSITIVITY_MIN/MAX/STEP`); mode-local "feel"
  numbers as commented `_UPPER_SNAKE` module constants. Inline literals removed across the
  modes, `_helpers.py`, and `app.py`.
- **Refactor:** deduplicated the per-band slicing into `_helpers.range_energies` (was copied
  in both multi-ring modes); added/extended docstrings; small readability cleanups.
- **Convention codified** in `.cursor/rules/python-coding-style.mdc`; docs/SKILL synced.
- **Formatting decision:** kept the locked **black + ruff** toolchain (PEP 8). The requested
  space-inside-brackets style is incompatible with black/ruff-format and was declined; the
  readability effort went into names, docstrings, and structure instead.

**Tests / verification**
- `tools\test.ps1` → **69 passed** (value-preserving refactor; suite unchanged).
- `tools\lint.ps1` → ruff **clean**, black **clean**, mypy **clean**.
- `python -m audio_visualizer --selftest` → exit **0**.

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
