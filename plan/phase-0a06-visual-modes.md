# Phase 0A.06 — new visual modes (plan)

Status: **shipped** in `v00.0A.06`. All six modes implemented (`terrain`, `vectorscope`,
`meters`, `matrix`, `pulse_rings`, `ripples`) with shared option presets in
`visuals/_helpers.py`; timings recorded in `CHANGELOG.md`. Goal was a batch of new modes
that are (1) **cheap to render** and (2) **deeply customizable**.

> Cross-references: shipped/proposed list in `plan/visual-mode-ideas.md` (don't repeat),
> mode contract in `.cursor/skills/audio-visualizer/SKILL.md`, decisions in
> `audio-visualizer-plan.md` §8.

---

## 1. Goals & non-negotiables

- **Performance budget:** each mode ≤ **~3 ms/frame at 1920×1080** on a typical laptop
  (so 60 FPS with headroom for background + logo). Verified with a quick timing harness like
  we used for Kaleidoscope (4 ms at 16 segments was our ceiling; aim lower).
- **Customizable:** target **5–7 `OPTIONS` per mode** (current modes have 2–4). The control
  bar flows/wraps, so more options are fine; group related ones. Every option is a discrete
  cycle (`ModeOption`/`OptionChoice`) — no free-form input.
- **Contract unchanged:** one file per mode, `@register`, read-only `AnalysisFrame` + surface
  + `dt` + `Theme`. Pure pygame-2D + numpy. `reduce_motion` honored. `STROBES=True` only when
  it truly flashes. A `draw` that raises is caught upstream (fail-soft) — but we still guard.
- **Resolution-independent:** layout from `surface.get_size()`; normalized coords; no
  hard-coded pixels. Recompute on resize (cache by size, like spectrogram/plasma).

## 2. Performance techniques to reuse (checklist per mode)

- **Vectorize with numpy**, then hand pygame a small number of draw calls (batch points into
  `pygame.draw.lines`/`aalines` rather than per-point circles where possible).
- **Low-res compute → `smoothscale`** for any per-pixel field (plasma pattern).
- **Persistent surface + `scroll`** for time-scrolling history (spectrogram pattern).
- **Caps + `reduce_motion` divisors** for any particle/objects list; pre-size arrays.
- **Cache** anything keyed by canvas size (meshgrids, gradients, static geometry).
- **Avoid per-frame `SRCALPHA` surface allocation** in hot paths; allocate once / by size.

## 3. Reusable option building blocks (implement once, share)

To get "as much customization as possible" without copy-paste, add shared option presets in
`visuals/_helpers.py` (alongside the existing `TRAIL_OPTION`):

- `COLOR_OPTION` — Classic / Per-band / Velocity / Mono-accent (where a mode supports it).
- `MIRROR_OPTION` — Off / Horizontal / Vertical / Quad.
- `GLOW_OPTION` — Off / Soft / Bloom (additive halo pass; Bloom only when cheap).
- `THICKNESS_OPTION` — Fine / Normal / Bold.
- `SPEED_OPTION` — Slow / Normal / Fast (multiplies the mode's internal rate; separate from
  the global Theme speed).

Modes opt in by including the shared option in their `OPTIONS` tuple and reading it. This
keeps option *names/values* consistent across modes (good UX) and centralizes behavior.

---

## 4. Candidate modes (all drawn from the proposed list; all cheap)

Each entry: concept · inputs · `OPTIONS` (the customization) · perf · strobe/reduce-motion.

### A. `meters` — "VU Meters" (retro hi-fi)
- **Concept:** a row of segmented LED ladder meters (or analog needles), one per frequency
  group; segments light up to the band level with a falling peak-hold pip.
- **Inputs:** `band_energies` (grouped), `peak`.
- **OPTIONS (7):** Style (Ladder / Needle / Bar), Groups (4 / 8 / 12 / 24), Segments
  (10 / 16 / 24), Peak-hold (On/Off), Decay (Slow/Med/Fast), Orientation (Vert/Horiz),
  Color (Classic / Per-band / Green-amber-red zones).
- **Perf:** just rectangles/lines; trivially < 1 ms. Pre-compute segment rects per size.
- **Strobe:** no. **Reduce-motion:** slower decay, no needle overshoot.

### B. `matrix` — "Dot Matrix" (LED panel)
- **Concept:** a grid of LEDs; each column is a band, lighting rows from the bottom by energy
  (arcade equalizer). Optional time-scroll so it reads like a marquee.
- **Inputs:** `band_energies`, `peak`.
- **OPTIONS (7):** Grid (24×12 / 32×16 / 48×24), Dot (Round / Square / Diamond), Gap
  (Tight/Normal/Wide), Lit (Solid / Heat / Per-column), Peak-dot (On/Off),
  Mode (Columns / Scroll), Glow (Off/Soft).
- **Perf:** N×M small blits; cap grid at 48×24 ≈ 1152 cells. Batch by precomputing cell
  rects; draw only lit cells. ~1–2 ms. **Scroll** variant reuses the spectrogram surface trick.
- **Strobe:** no. **Reduce-motion:** no scroll shimmer; gentler on-set flashes.

### C. `terrain` — "Synthwave Horizon" (scrolling terrain)
- **Concept:** spectrum becomes a mountain silhouette on a horizon; parallax layers scroll;
  optional retro sun + grid floor + mirrored reflection. The "wow" mode of the batch.
- **Inputs:** `band_energies` (ridge height), `rms` (sun pulse), `onset` (ridge jolt).
- **OPTIONS (7):** Layers (1 / 2 / 3 parallax), Fill (Solid / Gradient / Wireframe),
  Sun (On/Off), Grid floor (On/Off), Reflection (On/Off), Scroll (Slow/Normal/Fast),
  Palette (Sunset / Ice / Mono-accent).
- **Perf:** each layer is one filled polygon (`pygame.draw.polygon`) from ~120 points; sun is
  a cached gradient circle; grid is a handful of lines. ~1–2 ms. Reflection = vertical flip
  blit of the lower strip (cheap).
- **Strobe:** no. **Reduce-motion:** slower scroll, no sun flicker.

### D. `vectorscope` — "XY Vector Scope" (analog scope)
- **Concept:** classic oscilloscope X-Y mode — plot `waveform_mono` against a **delayed** copy
  of itself, producing the looping Lissajous curves real scopes show. Phosphor-style persistence.
- **Inputs:** `waveform_mono`.
- **OPTIONS (7):** Delay (samples: 1 / 4 / 16 / 64), Persistence (None/Short/Long phosphor
  trail), Draw (Line / Dots), Thickness (Fine/Normal/Bold), Color (Phosphor-green / Rainbow /
  Velocity), Rotation (Off/Slow/Fast), Grid (On/Off).
- **Perf:** one `aalines` polyline of ≤ 512 pts; persistence = fade the previous frame
  surface (blit a dim black) rather than clearing. ~1 ms. (Persistence needs a kept surface,
  but the canvas isn't cleared by modes anyway — we keep a private faded layer.)
- **Strobe:** no. **Reduce-motion:** no rotation; shorter persistence.

### E. `pulse_rings` — "Pulse Rings" (concentric breathing)
- **Concept:** one concentric ring per band group; each ring's radius/thickness/brightness
  breathes with its band; beats send a bright pulse outward through the stack.
- **Inputs:** `band_energies`, `onset`.
- **OPTIONS (6):** Rings (6 / 12 / 24), Draw (Outline / Filled / Dashed), Thickness
  (band-scaled / uniform), Rotation (Off / Spin / Counter per ring), Color (Per-ring /
  Rainbow / Mono), Beat-pulse (On/Off).
- **Perf:** N circle/arc draws; ≤ 24. ~1 ms. Dashed via arc segments.
- **Strobe:** no. **Reduce-motion:** no rotation, gentle breathing.

### F. `ripples` — "Bloom Ripples" (shockwaves)
- **Concept:** onsets drop expanding ring shockwaves (like rain on water) that thin and fade;
  loud beats make bigger/brighter rings; optional refraction wobble.
- **Inputs:** `onset`, `peak`, `rms`.
- **OPTIONS (6):** Spawn (Onset / Beat-grid / Continuous), Origin (Center / Random /
  Bass-follow), Style (Ring / Double-ring / Filled-fade), Max rings (8 / 16 / 32),
  Speed (Slow/Normal/Fast), Color (Rainbow / Mono / Per-spawn).
- **Perf:** a small list of rings, each one circle outline; capped. ~1 ms.
- **Strobe:** borderline — default no; "Continuous" + fast could flash, so cap brightness.
  **Reduce-motion:** fewer rings, slower.

---

## 5. Recommended scope for 0A.06

All six are cheap and additive (one file each, no shared-code edits beyond the optional
`_helpers.py` option presets). Suggested split:

- **Tier 1 (highest visual payoff):** `terrain`, `vectorscope`, `meters`.
- **Tier 2:** `matrix`, `pulse_rings`, `ripples`.

We can ship all six, or Tier 1 first then Tier 2 in 0A.07. Implementation order would be:
shared `_helpers.py` option presets → modes one-by-one → per-mode timing check → tests
(each renders idle+active, both motion settings, like `test_modes_phase1002.py`) → docs +
catalog move (Proposed → Shipped) → version bump → exe build.

## 6. Locked decisions (2026-06-18)

- **Scope:** ship **all six** modes in 0A.06 (`terrain`, `vectorscope`, `meters`, `matrix`,
  `pulse_rings`, `ripples`).
- **Customization ceiling:** **push to 6–7 options/mode** (max control). Control bar
  flows/wraps; group related options.
- **Shared presets:** **yes** — build the reusable option presets in `_helpers.py`
  (`COLOR_OPTION`, `MIRROR_OPTION`, `GLOW_OPTION`, `THICKNESS_OPTION`, `SPEED_OPTION`) first,
  then have modes opt in.

## 7. Implementation roadmap (when we move to build)

1. Add shared option presets + any shared draw helpers to `visuals/_helpers.py` (with tests).
2. Implement modes one file at a time, Tier 1 first (`terrain`, `vectorscope`, `meters`),
   then Tier 2 (`matrix`, `pulse_rings`, `ripples`); each `@register`s, no central edits.
3. Per-mode **timing check** (≤ ~3 ms/frame @1080p) + visual preview render.
4. Tests: extend the pattern in `tests/test_modes_phase1002.py` (each mode renders idle +
   active, both motion settings; filling modes paint something).
5. Docs: move the six from **Proposed → Shipped** in `plan/visual-mode-ideas.md`; update
   `repository-and-code-layout.md`, SKILL, CHANGELOG; bump `APP_VERSION` to `00.0A.06`.
6. Full pipeline: ruff/black/mypy, suite, `--selftest`, exe build + self-test.
