# Testing & Verification

Companion to `plan/audio-visualizer-plan.md`. Goal: **prove the code works and the window actually runs** — without needing a real sound card or display in CI.

> Principle: tests should be fast, deterministic, and runnable headlessly. Real-hardware checks are a short manual checklist.

---

## 1. The enabler: an injectable audio source

`audio/source.py` defines `AudioSource` with two implementations:

- `LoopbackSource` — real WASAPI loopback (`pyaudiowpatch`).
- `SyntheticSource` — generates a known signal (sine at a chosen frequency, sweep, or silence).

Because `App` and `Analyzer` depend on the **interface**, tests and `--selftest` inject `SyntheticSource`. This makes "does it react to audio?" verifiable with **no hardware**.

---

## 2. Test layers

| Layer | File | Verifies |
|-------|------|----------|
| DSP unit | `tests/test_analysis.py` | Pure 1 kHz sine → energy concentrates in the expected log band; **silence → bands ≈ 0 with no NaN/div-by-zero**; RMS/peak correct for known inputs; **band mapping respects the frame's `sample_rate`** (44.1 vs 48 kHz) |
| Audio format | `tests/test_source.py` | **int16 and float32 inputs** normalize to float32 `-1..1`; **stereo downmixes to mono** correctly; `SyntheticSource` honors requested sample rate |
| Frame/contract | `tests/test_frame.py` | `AnalysisFrame` is frozen; arrays have expected lengths/dtypes |
| Settings | `tests/test_settings.py` | Round-trips JSON; **unknown/corrupt/old `schema_version` falls back to defaults without crashing** |
| UI logic | `tests/test_ui_logic.py` | `Button.handle_event` hit-testing; mode cycling wraps (next from last → first); `Layout` recomputes rects from size (no overlap at min size) |
| Visual registry | `tests/test_registry.py` | `discover()` finds all modes; each `BaseVisualizer` subclass has unique `KEY`; `available()` ordered by `ORDER`; a dummy mode dropped in a temp package auto-registers (proves "one file" works) |
| Visual render | `tests/test_visuals.py` | Each registered mode `draw()`s on a dummy surface at several sizes (incl. tiny + with `frame=None`) without error; a mode that raises is isolated, not fatal |
| Onset detection | `tests/test_onset.py` | A broadband transient (after silence) clears `ONSET_THRESHOLD`; a steady tone does not; silence reads exactly 0 |
| Particles | `tests/test_particles.py` | Particle update is **deterministic under a fixed seed**; **reduce-motion caps** the live particle count |
| Headless smoke | `tests/test_smoke.py` | `App` constructs and renders **N frames** with `SyntheticSource` and **does not crash**; renders an **idle (silent) frame**; **cycles through all 5 modes** without error |

### Headless rendering in CI

Set these before importing pygame so no display/audio device is needed:

```python
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
```

`tools/test.ps1` sets the same env vars, so `pytest` runs headlessly on a dev box or CI.

---

## 3. Commands

```powershell
# From repo root (after tools\setup.ps1 once):
.\tools\test.ps1                 # pytest, headless
.\tools\test.ps1 -Coverage       # optional coverage report
.\tools\lint.ps1                 # ruff + black --check (+ mypy)
```

Direct equivalent:

```powershell
$env:SDL_VIDEODRIVER = "dummy"; $env:SDL_AUDIODRIVER = "dummy"
.\.venv\Scripts\python -m pytest -q
```

---

## 4. Verifying the window/app actually runs

Two complementary checks beyond unit tests:

1. **`--selftest` (headless):** the app initializes capture (synthetic), analysis, UI, renders N frames, then exits `0`. Run it on the **source** and on the **built exe**:

```powershell
.\.venv\Scripts\python -m audio_visualizer --selftest
.\dist\AudioVisualizer.exe --selftest        # proves the packaged exe launches
```

2. **Manual loopback smoke test (real hardware):**
   - `tools\run.ps1` to launch the app.
   - With **no audio playing**, Start capture → app shows the **"No audio detected" idle state** (not a frozen black screen).
   - Play any audio (browser/Spotify/game).
   - Click **Start capture** → waveform/spectrum should move; **RMS/Peak** in the status line should change.
   - Cycle modes (Waveform → Spectrum → Light Show → Particles → Laser) — each renders without error.
   - Toggle **Fullscreen (F11)**, then **Esc**.
   - **Resize the window** and run on a **scaled (150%) display** → UI stays crisp and laid out correctly.
   - Switch the default output device (speakers ↔ headphones) while running → app shows a banner / recovers, does not crash.
   - Toggle **F3** debug overlay → FPS/RMS/peak/device update live.

### Demo / acceptance check (objective "it reacts")

Keep a short known input so "working" isn't subjective:

- A committed/test-generated **reference WAV** (e.g. a 1 kHz tone or a short sweep) played through the default output (or fed via `SyntheticSource`).
- Expected, written-down result: spectrum energy lands in the matching band, RMS rises from idle, waveform shows the tone. Record this in the PR/manual log.

---

## 5. CI outline (GitHub Actions, `windows-latest`)

```
setup-python (3.12)
  → .\tools\check-deps.ps1     # fails fast if Python < 3.12
  → .\tools\setup.ps1
  → .\tools\lint.ps1          # ruff + black --check
  → .\tools\test.ps1          # pytest headless (dummy SDL drivers)
  → .\tools\build-exe.ps1     # from Phase 1 onward (validates PortAudio DLL bundling)
  → .\dist\AudioVisualizer.exe --selftest
  → (optional) upload dist\AudioVisualizer.exe as artifact
```

Start with lint + tests required. **Add the exe build + `--selftest` to CI from Phase 1** (not Phase 3) so packaging regressions are caught immediately.

---

## 6. What "done/working" means

- `tools\test.ps1` green (all layers).
- `python -m audio_visualizer --selftest` and `AudioVisualizer.exe --selftest` exit `0`.
- The **demo/acceptance check** passes (reference tone → expected band/RMS reaction).
- Manual checklist passes on a real machine: visible, audio-reactive, **idle state when silent**, mode switching, fullscreen, **resize/high-DPI**, device-change survival.
