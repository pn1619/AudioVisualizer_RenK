# Phase 0B-d — visual modes expansion (plan)

Status: **BUILT in `v00.0B.24`** (concepts approved 2026-06-23; all 10 modes implemented + tested,
shipping under temporary `Test_` names pending visual approval). Goal: a batch of **10 new visual
modes**, each (1) within the render budget, (2) **deeply customizable** via `OPTIONS` + `PRESETS`,
and (3) one file with `@register` — no central edits.

> **Build notes (2026-06-24):** all 10 ship as `test_<key>` / `Test_<Name>` (the registry key + the
> display name). Removing the prefix later is a pure rename (no settings migration needed yet). Each
> mode was cross-checked against its concept art with `tools/preview_mode.py` (headless PNG render);
> the concept art is preserved in `assets/concept-art/`. Two small concessions vs. the AI art: the
> Mandala/Tree read more pastel/sparser than the idealized art, and Flow Field is necessarily less
> dense than a pre-rendered still — all faithful to the concept's intent within the real-time budget.

> Cross-references: catalog (don't repeat) `plan/visual-mode-ideas.md`; mode contract
> `.cursor/skills/audio-visualizer/SKILL.md`; prior batch template `plan/phase-0a06-visual-modes.md`;
> decisions log `audio-visualizer-plan.md` §8. Concept art lives in `assets/concept-art/`.

---

## 1. Goals & non-negotiables (inherited from 0A.06)

- **Performance budget:** ≤ **~3 ms/frame @ 1920×1080** on a typical laptop (60 FPS with
  headroom for background + logo + foreground). Field-based modes use the low-res-compute →
  `smoothscale` trick (the Plasma pattern) and stay within budget.
- **Customizable:** target **5–7 `OPTIONS` per mode** plus **2–3 curated `PRESETS`** (the
  "submodes" the user asked for). Every option is a discrete cycle (`ModeOption`/`OptionChoice`).
  Reuse the shared presets in `_helpers.py` (`COLOR_OPTION`, `MIRROR_OPTION`, `GLOW_OPTION`,
  `THICKNESS_OPTION`, `SPEED_OPTION`, `SIZE_OPTION`, `TRAIL_OPTION`, `PARTICLES_OPTION`) wherever
  they fit, so names/values stay consistent across modes.
- **Contract unchanged:** one file per mode, `@register(key, display_name, order)`, read-only
  `AnalysisFrame` (`waveform_mono`, `band_energies`, `rms`, `peak`, `onset`, `sample_rate`) +
  surface + `dt` + shared `Theme`. Pure pygame-2D + numpy. `reduce_motion` honored.
  `STROBES=True` only when it truly flashes. `draw` is fail-soft upstream — still guard.
- **Resolution-independent:** geometry from `surface.get_size()`; cache anything keyed by size
  (meshgrids, gradients, static geometry); recompute on resize. No hard-coded pixels.

## 2. Overlap resolution (must read)

`plan/visual-mode-ideas.md` already lists **`aurora`** and **`starfield`** as *Background layers*
and warns: don't propose a *mode* that "merely duplicates a backdrop." Two of our concepts touch
those names, so we differentiate hard:

- **Aurora (mode)** vs background aurora: the **mode** is a full-screen, **band-reactive** curtain
  field (per-band columns, onset flares, turbulence, 6 submodes). The background layer stays a
  subtle, low-contrast backdrop. Different layer, different intent. To avoid name confusion the
  mode ships as **"Aurora Veil"** (`aurora_veil`).
- **Hyperspace (mode)** vs background starfield: the background is a slow static drift; the **mode**
  is a **warp/jump** experience (level→speed, beat→punch, camera roll). Ships as **"Hyperspace"**
  (`hyperspace`). No shared code with the backdrop.

`dna` and a galaxy/vortex were already in the Proposed list — `dna` is included here; the vortex
idea is folded into **Flow Field**'s "Vortex" field option rather than a separate mode.

## 3. Performance techniques to reuse (checklist)

- Vectorize with numpy; hand pygame few draw calls (`aalines`/`lines`, batched points).
- Low-res numpy field → `smoothscale` for per-pixel modes (Aurora Veil, Lava Lamp, Flow Field).
- Persistent faded surface for phosphor/trail persistence (Vectorscope pattern) — Harmonograph,
  Flow Field, Constellation.
- Caps + `reduce_motion` divisors for every particle/object list; pre-size arrays.
- Cache size-keyed data (meshgrids, gradients, petal/branch geometry, link grids).
- Allocate `SRCALPHA` layers once / by size, not per frame.

---

## 4. The 10 modes

Each entry: concept · inputs · algorithm sketch · `OPTIONS` (5–7) · `PRESETS` · perf ·
strobe/reduce-motion. `order` values slot them sensibly among existing modes (lower = earlier).

### 1. `aurora_veil` — "Aurora Veil"  (order ~70)
- **Concept:** vertical curtains of light; each curtain's height/shimmer rides a frequency band,
  drifting slowly over an optional starfield.
- **Inputs:** `band_energies` (curtain heights), `onset` (flare), `rms` (overall glow).
- **Sketch:** N vertical band columns; per-column height = smoothed band energy; render as a
  low-res numpy alpha field (gaussian falloff in x, gradient in y) tinted per palette → upscale.
- **OPTIONS (6):** Curtains (2/3/4/5) · Style (Curtains/Ribbons/Veil) · Drift (Still/Slow/Fast) ·
  Turbulence (Calm/Wavy/Stormy) · Palette (Polar/Solar/Theme) · Stars (Off/Few/Many).
- **PRESETS:** Polar Night · Solar Storm · Calm Veil.
- **Perf:** low-res field + smoothscale ≈ 2 ms. **Strobe:** no. **Reduce-motion:** less drift/turbulence, no flare spikes.

### 2. `hyperspace` — "Hyperspace"  (order ~78)
- **Concept:** radial starfield warping from a vanishing point; the beat lurches forward.
- **Inputs:** `rms`/`level` (warp speed), `onset` (jump/punch), `band_energies[high]` (twinkle).
- **Sketch:** array of stars (angle, radius, depth); each frame radius += speed·depth; project to
  screen, draw a streak from previous→current position; recycle past the edge; onset adds a speed impulse.
- **OPTIONS (6):** Density (Sparse/Medium/Dense) · Warp (Cruise/Jump-on-beat/Punch) ·
  Trails (Dots/Short/Long) · Center (Fixed/Wander) · Color (White/Cyan/Theme/Rainbow) ·
  Roll (Off/Slow spin).
- **PRESETS:** Cruise · Jump to Lightspeed · Nebula Drift.
- **Perf:** ≤ ~1500 streaks via batched `lines` ≈ 1–2 ms. **Strobe:** borderline (Punch); cap flash. **Reduce-motion:** no punch lurch, shorter trails.

### 3. `skyline` — "Frequency Skyline"  (order ~24)
- **Concept:** an EQ city — each building is a frequency bar; window rows light by amplitude;
  optional water reflection.
- **Inputs:** `band_energies` (heights + lit windows), `bass` (ground pulse), `onset` (flash).
- **Sketch:** map bands → building rects across x; building height = band energy; draw window grid,
  lighting rows up to energy; reflection = vertical-flip blit of the lower strip with alpha.
- **OPTIONS (6):** View (Flat/Perspective/Isometric) · Reflection (Off/Water/Mirror) ·
  Windows (Off/Lit/Animated) · Skyline (Even/Random/City) · Palette (Synthwave/Mono/Theme) ·
  Bars (24/48/64).
- **PRESETS:** Neon Bay · Mono Metropolis · Sunset Strip.
- **Perf:** rects + cached window grid ≈ 1–2 ms. **Strobe:** no. **Reduce-motion:** gentler window flicker.

### 4. `dna` — "DNA Helix"  (order ~84)
- **Concept:** rotating double-helix; each rung is a band; pulses travel the strands.
- **Inputs:** `band_energies` (rung length/color), `rms` (rotation rate), `onset` (pulse).
- **Sketch:** parametric helix y∈[0,h], x = cx + A·sin(phase + k·y); two strands offset by π; rungs
  connect strand points at sampled y, colored/scaled by band; depth via sin → size/alpha.
- **OPTIONS (6):** Strands (1/2/3) · Twist (Slow/Med/Fast) · Rung style (Bars/Beads/Lightning) ·
  Orientation (Vertical/Horizontal/Diagonal) · Color (Spectrum/Duotone/Theme) · `GLOW_OPTION`.
- **PRESETS:** Classic · Triple Helix · Bio-Neon.
- **Perf:** ~64 rungs + 2 polylines ≈ 1 ms. **Strobe:** no. **Reduce-motion:** slower twist, no pulse strobe.

### 5. `harmonograph` — "Harmonograph"  (order ~106)
- **Concept:** a synthesized pen plotter tracing damped Lissajous loops with phosphor trails.
  *(Distinct from `vectorscope`, which plots raw L/R; this is generated from band-driven oscillators.)*
- **Inputs:** `band_energies` (oscillator freqs/amps), `onset` (re-seed), `rms` (brightness).
- **Sketch:** x(t)=Σ Aᵢ·sin(fᵢ·t+pᵢ)·e^(−dᵢt), y(t) similar; sample T points into a polyline;
  persistence = fade a kept private surface instead of clearing.
- **OPTIONS (6):** Pens (1/2/3) · Persistence (Short/Long/Phosphor) · Damping (Tight/Loose) ·
  Symmetry (Off/Mirror/Radial) · Line (Hairline/Glow/Ribbon) · Color (Per-pen/Theme/Rainbow).
- **PRESETS:** Single Pen · Spirograph · Phosphor Trails.
- **Perf:** ≤ 3 polylines of ~512 pts + fade blit ≈ 1–2 ms. **Strobe:** no. **Reduce-motion:** shorter persistence, no re-seed jolt.

### 6. `metaballs` — "Lava Lamp"  (order ~83)
- **Concept:** gooey metaball blobs merging/splitting, driven by bass.
- **Inputs:** `bass`/`band_energies[low]` (blob size), `onset` (spawn/split), `mids` (drift).
- **Sketch:** M blobs (pos, radius); on a low-res grid sum field = Σ rᵢ²/dist² ; threshold →
  filled/outline; tint by field magnitude; upscale. Reuse Plasma's low-res buffer approach.
- **OPTIONS (6):** Blobs (Few/Some/Many) · Viscosity (Thick/Smooth/Runny) ·
  Surface (Filled/Outline/Gooey glow) · Gravity (Float/Up/Down) · Palette (Lava/Plasma/Theme) ·
  Reactivity (Calm/Normal/Wild).
- **PRESETS:** Classic Lava · Plasma Goo · Zero-G.
- **Perf:** low-res grid (e.g. 160×90) field + smoothscale ≈ 2–3 ms. **Strobe:** no. **Reduce-motion:** slower drift, fewer spawns.

### 7 (dropped). `tree` / `tree2` — procedural Fractal Tree attempts
- The procedural L-system tree (`test_tree`) and the concept-faithful symmetric fractal (`test_tree2`),
  plus interim `v3-realistic`/`v4` experiments, never read like the concept art and were **deleted**.
  The single official tree is `fractal_tree` below, which renders the artwork itself.

### 7. `fractal_tree` — "Fractal Tree"  (official; order 95)
- **Why:** several procedural attempts never read like the concept art. The official mode takes the
  literal route: **render the concept art itself**, keep the tree **completely static**, and put the
  only effects on the **flowers** and the **glow** of the body.
- **The tree (static):** the artwork `concept-07-fractaltree.png` is bundled as
  `audio_visualizer/assets/fractal_tree.png`, loaded once via `asset_path()`, fit to the canvas
  (contain → letterboxed so the whole tree is always visible), scaled-and-**cached per size**
  (converted to the target pixel format), and simply blitted each frame. Its near-black background
  is **luminance-keyed to transparent** (`SRCALPHA`, alpha from luma with a gentle ramp) and the
  mode **does not fill the canvas**, so it **composites over the app's background layer** rather
  than overwriting it — the dark gaps show the background through. The bundled PNG is
  the concept art with its **"FRACTAL TREE" title/legend/equalizer corner inpainted out** (feathered
  dark fill + faint stars), regenerated from the pristine concept art so it stays reproducible.
- **Flower detection (once):** a small image scan downsamples the art and finds **bright-magenta
  blobs** (R high, B high, G low) via grid-pooling + non-max suppression → ~15 bloom centres in
  image-normalised coords. Each bloom's particle tint is **sampled from the art** beneath it.
- **Shape-matched flower glow:** for each bloom a **masked patch of its own pixels** (non-petal
  pixels zeroed) is extracted at build; per frame it's brightened (treble/rms baseline + onset pops)
  and added back over itself, so the glow **overlays the flower exactly** (no circular blob) and
  swells slightly on the beat. Onsets also **emit drifting particles** (mostly pink, some teal) with
  Float/Burst/Swirl motion.
- **Frequency tree-body glow:** precomputed **cool (teal) and warm (pink) colour masks** of the
  image are modulated by **bass → trunk/roots** and **treble → foliage** and added back, so the body
  reacts to the spectrum.
- **Energy flow (running light):** the tree is only an image, so a **multi-source BFS over the bright
  pixels seeded at the trunk base** recovers a normalised **distance-from-roots** field once per size
  (coarse grid + 1px dilation, cached). Per frame, narrow `cos^8` bands ride that field and sweep
  **root → tips**, tinted by the brightened local tree colour, so light **runs up the real branches
  to the blooms**. Brightness scales with RMS and the bands run **faster when louder**.
- **Compositing:** glow + flow are summed into a **reused low-res accumulator** and applied in **one**
  upscale + additive blit (phase terms precomputed); ~19 ms/frame at 1280×800, ~26 ms at 1080p.
  Missing-artwork is fail-soft. Tree Glow / Energy Flow / Particles all have an Off for max FPS.
- **OPTIONS (6):** Flower Glow (Soft/Normal/Bright) · Tree Glow (Off/Subtle/Pulse) · Energy Flow
  (Off/Stream/Surge) · Particles (Off/Soft/Lush) · Reactivity (Calm/Normal/Punch) · Drift
  (Float/Burst/Swirl).
- **PRESETS:** Bloom (default) · Sparkle · Calm.
- **Strobe:** no. **Reduce-motion:** steady baseline glow, no onset bursts or particles.
- **Packaging:** the PNG ships automatically (the `.spec` bundles all of
  `src/audio_visualizer/assets/`).

### 8. `flowfield` — "Flow Field"  (order ~42)
- **Concept:** particles streaming along a curl-noise vector field that the audio bends.
- **Inputs:** `rms` (flow speed), `bass` (turbulence), `onset` (vortex impulse), `treble` (sparkle).
- **Sketch:** precomputed noise angle grid; each particle samples grid → velocity; integrate;
  draw short streak; trails via faded surface; onset injects a transient vortex term.
- **OPTIONS (6):** Particles (count) · Field (Curl/Swirl/Grid/Radial) · `TRAIL_OPTION` ·
  Color-by (Velocity/Angle/Theme) · Vortex-on-beat (Off/On) · `SPEED_OPTION`.
- **PRESETS:** Silk · Storm · Vortex.
- **Perf:** numpy-vectorized particle integration (positions as arrays) + batched draws; cap count ≈ 2–3 ms. **Strobe:** no. **Reduce-motion:** fewer particles, no vortex.

### 9. `constellation` — "Constellation"  (order ~88)
- **Concept:** drifting nodes that draw glowing links when near; beats ripple through the graph.
- **Inputs:** `rms` (jitter/count), `band_energies` (link brightness), `onset` (ripple), `bass` (node size).
- **Sketch:** N nodes drifting; spatial bucket to find pairs within link distance; draw line with
  alpha ∝ (1 − dist/maxdist); onset spawns a radius that brightens links it passes.
- **OPTIONS (6):** Nodes (Few/Medium/Many) · Link distance (Short/Med/Long) ·
  Motion (Drift/Orbit/Repel-from-cursor) · Link style (Lines/Glow/Pulse-travel) ·
  Color (Cyan-gold/Theme/Rainbow) · Depth (Flat/Parallax).
- **PRESETS:** Night Sky · Neural Net · Plexus.
- **Perf:** node count capped (~120) with spatial buckets to keep pair tests cheap ≈ 2 ms. **Strobe:** no. **Reduce-motion:** fewer nodes, slower drift.

### 10. `mandala` — "Mandala Bloom"  (order ~91)
- **Concept:** a symmetric generative flower whose petal-rings breathe with the spectrum.
- **Inputs:** `band_energies` (ring radii), `onset` (bloom pulse / new layer), `rms` (rotation).
- **Sketch:** for each layer, draw a petal polygon repeated around `symmetry` angles; petal radius =
  band energy; rotate slowly; mirror via the symmetry repetition; cache petal shape, transform per frame.
- **OPTIONS (6):** Symmetry (4/6/8/12-fold) · Layers (3/5/7) · Bloom (Breathe/Pulse/Unfold) ·
  Petal (Lotus/Star/Leaf/Geometric) · Palette (Jewel/Theme/Rainbow) · Spin (Off/Slow/Fast).
- **PRESETS:** Lotus · Sacred Geometry · Kaleido-bloom.
- **Perf:** ≤ symmetry×layers polygons (≤ ~84) ≈ 1 ms. **Strobe:** no. **Reduce-motion:** slow spin, gentle breathe.

---

## 5. Proposed phasing (batches → version bumps)

Ship in batches (each a self-contained build + version bump + exe self-test), grouped by render
technique so we validate the hard parts early:

- **Batch 1 — geometric/cheap (warm-up):** `dna`, `mandala`, `skyline`. (vector draws only.)
- **Batch 2 — particle/trail systems:** `hyperspace`, `constellation`, `flowfield`. (shared faded-surface + spatial buckets.)
- **Batch 3 — field/organic (heaviest):** `aurora_veil`, `metaballs`, `tree`, `harmonograph`.

Rationale: prove the polyline/preset pattern first, then the trail/particle infra, then the
numpy-field + recursion work that needs the most perf care. We can collapse batches if timings are
comfortable.

## 6. Locked decisions (2026-06-23)

1. **Scope/batching:** ship **all 10 modes in a single build** (one version bump). §5's batches
   become the *implementation order* (geometric → particle → field/organic) to de-risk timings,
   but they release together.
2. **Naming:** confirmed **"Aurora Veil"** (`aurora_veil`) and **"Hyperspace"** (`hyperspace`) to
   disambiguate from the background layers (§2).
3. **Shared presets:** **add `PALETTE_OPTION` + `SYMMETRY_OPTION`** to `_helpers.py` and have modes
   opt in (alongside the existing shared presets).
4. **Customization ceiling:** **6 `OPTIONS` per mode** (+ 2–3 `PRESETS`), as drafted.

## 7. Implementation roadmap (per batch, when we build)

1. Add any new shared presets/draw helpers to `visuals/_helpers.py` (+ tests).
2. Implement modes one file at a time; each `@register`s, no central edits.
3. Per-mode **timing check** (≤ ~3 ms/frame @1080p) + a quick preview render.
4. Tests: extend the `tests/test_modes_*` pattern — each mode renders idle + active, both motion
   settings; field/filling modes paint something; options/presets switch without error.
5. Docs: move modes **Proposed → Shipped** in `plan/visual-mode-ideas.md`; update
   `repository-and-code-layout.md`, SKILL, CHANGELOG; bump `APP_VERSION`.
6. Full pipeline: ruff/black/mypy, suite, `--selftest`, exe build + self-test.
