# Visual mode ideas & catalog

> **Purpose:** the single source of truth for *which visualizations exist or have been
> proposed*, so we don't reinvent or re-render the same concept twice.
>
> **When generating new concept art / mode ideas:** first read this file and **avoid
> repeating any visual already listed here** (shipped, planned, or proposed). Add the new
> idea to "Proposed" before producing art, and move it down the list as its status changes.
> Concept art is disposable — the *descriptions here* are what we keep.

Reminder of the contract every mode honors (so ideas stay feasible): a mode subclasses
`BaseVisualizer`, auto-registers with `@register(key, display_name, order)`, and its only
inputs are a read-only `AnalysisFrame` (`waveform_mono`, `band_energies`, `rms`, `peak`,
`onset`, `sample_rate`), the target surface, `dt`, and the shared `Theme`. Pure pygame-2D +
numpy. Flashing modes set `STROBES = True`. Respect `reduce_motion`. **One mode = one file.**

---

## Shipped modes (do not re-propose these)

| Key | Name | Gist |
|---|---|---|
| `waveform` | Waveform | Oscilloscope trace; optional popping **Particles** + **Mirror**. |
| `waveform_circle` | Waveform Rings | **Rings 1/3/6/12** (single ring → per-band concentric) + optional shed **Particles**. |
| `spectrum` | Spectrum | Vertical log-band bars with peak-hold caps; **Mirror** + **Glow**. |
| `lightshow` | Light Show | Radial beams + shapeable core; **Particles** Off=solid beams / on=bead beams + emit. |
| `laser` | Laser | Sweeping beams + selectable parametric figure; **Particles** = emitted sparks. |
| `particles` | Particles | Onset-driven sparks; **Emitter** Field (burst+gravity) or Spiral (per-band arms). |
| `snowfall` | Snowfall | Calm resolution-independent flake field. |
| `spectrogram` | Spectrogram | Scrolling magnitude heatmap (freq Y, time X). |
| `radial_spectrum` | Audio Sun | Spectrum bars radiating from a glowing core + osc ring. |
| `plasma` | Plasma | Bass-reactive sine-interference color field (low-res upscaled). |
| `tunnel` | Tunnel Warp | Concentric rings flying outward; beats spawn rings. `STROBES`. |
| `fireworks` | Fireworks | Onset rockets bursting into gravity spark showers. |
| `kaleidoscope` | Kaleidoscope | Audio wedge mirrored/rotated into a symmetric mandala. |
| `terrain` | Synthwave Horizon | Music-fed scrolling neon mountains over a retro sun + grid floor. |
| `vectorscope` | Vectorscope | XY phosphor Lissajous scope (waveform vs delayed copy) + persistence. |
| `meters` | VU Meters | Frequency-grouped LED ladders / bars / needle gauges + peak-hold. |
| `matrix` | Dot Matrix | LED dot panel: columns equalizer or scrolling dot-spectrogram. |
| `pulse_rings` | Pulse Rings | Concentric per-band breathing rings + outward beat pulses. |
| `ripples` | Ripples | Beat-born expanding water-ripple shockwaves. |

**Also not modes (global layers):** RenK logo overlay (`visuals/logo.py`) and the Background
layer (`visuals/background.py`: black, spectrum line, filaments, mirror, ribbon, gradient,
aurora, starfield, vignette). Don't propose a *mode* that merely duplicates a backdrop.

---

## Proposed (not yet built — fair game for future versions)

- **DNA double-helix** — two intertwined sine strands modulated by the waveform; rungs flash.
- **Galaxy / vortex** — rotating spiral arms whose length/brightness follow bands.

_(Shipped in `v00.0A.06`: VU meters, dot-matrix, scrolling terrain, pulse rings, XY
vectorscope, bloom ripples — see the Shipped table above.)_

_(Consolidated in `v00.0A.07`: the old `waveform_2`, `waveform_circle_2`,
`waveform_circle_multiple[_2]`, `lightshow_2`, `laser_2`, and `particles_spiral`
modes were folded into their base modes as options/presets — don't re-propose them.)_
