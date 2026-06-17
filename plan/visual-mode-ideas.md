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
| `waveform` | Waveform | Centered horizontal oscilloscope trace. |
| `waveform_2` | Waveform 2 | Oscilloscope line + onset/energy popping particles. |
| `waveform_circle` | Waveform Circle | Single oscilloscope ring; radius wobbles with samples. |
| `waveform_circle_2` | Waveform Circle 2 | Oscilloscope ring + popping particles. |
| `waveform_circle_multiple` | Waveform Circle x N | N concentric rings, each driven by a spectrum slice. |
| `waveform_circle_multiple_2` | Waveform Circle x N 2 | N per-band rings + shed particles. |
| `spectrum` | Spectrum | Vertical log-band bars with peak-hold caps. |
| `lightshow` | Light Show | Beams radiate from center; length/brightness = band energy. |
| `lightshow_2` | Light Show 2 | Radial beams of pulsing particles + shapeable core + emit. |
| `laser` | Laser | Sweeping beams + a Lissajous curve tracing the spectrum. |
| `laser_2` | Laser 2 | Rotating beams + selectable parametric figure + emit. |
| `particles` | Particles | Onset-driven particle field. |
| `particles_spiral` | Particles Spiral | Spiral particle emitter; per-band hue. |
| `snowfall` | Snowfall | Calm resolution-independent flake field. |
| `spectrogram` | Spectrogram | Scrolling magnitude heatmap (freq Y, time X). |
| `radial_spectrum` | Audio Sun | Spectrum bars radiating from a glowing core + osc ring. |
| `plasma` | Plasma | Bass-reactive sine-interference color field (low-res upscaled). |
| `tunnel` | Tunnel Warp | Concentric rings flying outward; beats spawn rings. `STROBES`. |
| `fireworks` | Fireworks | Onset rockets bursting into gravity spark showers. |
| `kaleidoscope` | Kaleidoscope | Audio wedge mirrored/rotated into a symmetric mandala. |

**Also not modes (global layers):** RenK logo overlay (`visuals/logo.py`) and the Background
layer (`visuals/background.py`: black, spectrum line, filaments, mirror, ribbon, gradient,
aurora, starfield, vignette). Don't propose a *mode* that merely duplicates a backdrop.

---

## Proposed (not yet built — fair game for future versions)

- **VU / LED meters** — retro hi-fi ladder meters or needle gauges per band group.
- **Dot-matrix grid** — an LED matrix; columns = bands lighting rows by energy (arcade).
- **Scrolling terrain** — spectrum as a mountain-silhouette horizon scrolling into a landscape.
- **Concentric pulse rings** — one ring per band; thickness/brightness = energy; breathing.
- **XY vector scope** — true Lissajous from `waveform_mono` vs a delayed copy (analog scope).
- **DNA double-helix** — two intertwined sine strands modulated by the waveform; rungs flash.
- **Bloom ripples** — onsets drop expanding water-ripple shockwaves.
- **Galaxy / vortex** — rotating spiral arms whose length/brightness follow bands.
