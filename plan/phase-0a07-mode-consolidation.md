# Phase 10.07 — Mode consolidation + smarter options (`v00.0A.07`) — SHIPPED

Goal: cut the mode list's duplication (a base mode and its "+particles" twin, four
near-identical circle modes) by folding the variants into options/presets, so every
look stays reachable from **fewer, smarter** modes. Registered modes: **26 → 19**.

## Merges

| Survivor (`key`) | Absorbed | How it's reached now |
|---|---|---|
| `waveform` | `waveform_2` | shared **Particles** (Off·Sparse·Dense) axis; on = popping sparks. Also gained **Mirror**. |
| `waveform_circle` ("Waveform Rings") | `waveform_circle_2`, `waveform_circle_multiple`, `waveform_circle_multiple_2` | **Rings** (1·3·6·12): 1 = single oscilloscope ring, more = per-band concentric rings; **Particles** sheds sparks. |
| `lightshow` | `lightshow_2` | **Particles** Off = clean solid beams (classic); on = bead beams that emit sparks. Keeps shapeable **Core**. |
| `laser` | `laser_2` | keeps selectable **Shape** (Lissajous/rose/star/spiral/heart); **Particles** controls emitted sparks. |
| `particles` | `particles_spiral` | **Emitter** (Field·Spiral): Field bursts outward with gravity; Spiral traces per-band rotating arms. |

7 mode files deleted: `waveform_2.py`, `waveform_circle_2.py`,
`waveform_circle_multiple.py`, `waveform_circle_multiple_2.py`, `lightshow_2.py`,
`laser_2.py`, `particles_spiral.py`.

## Smarter options

- **Shared `PARTICLES_OPTION`** (`Off`=0.0 / `Sparse`=1.0 / `Dense`=2.0, a spawn-rate
  multiplier) in `visuals/_helpers.py` is the common "+particles" axis.
- **Per-mode presets**: `BaseVisualizer.PRESETS = {preset_index: {option_key: choice_index}}`
  + a leading `preset` `ModeOption` (first choice = no-op "Custom"). Selecting a preset
  snaps the listed sibling options; handled generically in
  `BaseVisualizer.on_option_change` → `_apply_preset` (subclasses that override
  `on_option_change` must call `super()`).
- **Shared-option retrofit**: **Mirror** added to `spectrum`, `vectorscope`; **Glow**
  (a cheap dim-halo) added to `spectrum`, `meters`.

## Settings migration (schema v6 → v7)

Per-mode option indices were **never persisted** (only the active `mode` key + global
theme are), so migration is a key remap only: `config.MERGED_MODE_KEYS` maps each
removed key to its survivor, applied in `settings._from_dict`. Any other key (and a
fresh install) is unaffected; a bad/old file still falls back to defaults.

## Verification

- ruff / black / mypy **clean**; full pytest suite **passes** (incl. `test_modes_phase1007.py`:
  merges registered, old keys remap, preset snapping, option-sweep over every merged mode;
  the older phase 3/4/6/8 tests were re-pointed at the merged modes).
- `--selftest` exit **0** (logs the v6→v7 migration); exe builds + self-tests.
