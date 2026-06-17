# Phase 0B candidates (planning only — not implemented)

> Scope note: these are **design plans** to keep `v00.0A.0x` small and revertible.
> Target them for **`v00.0B.00`+**. Each keeps our locked stack (pygame + numpy +
> pyaudiowpatch) and the existing seams (`AudioSource`, `registry`, `ControlBar`,
> versioned `Settings`). No code yet — this is the agreed direction.

---

## 0B-a. Selectable sound source

**Goal.** Let the user pick which Windows audio endpoint drives the visuals. Default
stays today's behavior (the **default render device**, WASAPI loopback).

**Where it fits.** All capture already goes through the `AudioSource` interface, and
`LoopbackSource` wraps `pyaudiowpatch`. This stays a *capture* concern — `App` and
`Analyzer` must not learn about devices.

**Design.**
- Add a small **enumeration** API on the loopback layer (new `audio/devices.py`):
  `list_sources() -> list[SourceInfo]` where `SourceInfo` = `(id, name, kind, is_default)`.
  - `kind` ∈ `{"loopback", "input"}`: loopback of any **render** endpoint (speakers/
    headphones/HDMI) **and** real **input** devices (microphone / line-in), since
    pyaudiowpatch exposes both. This also answers "react to the mic", not just system audio.
- `LoopbackSource` gains an optional `device_id` (None ⇒ today's default-device logic),
  and **negotiates that device's native format** exactly as now (rate/channels/dtype →
  mono float32). The default-device fallback path is unchanged.
- **UI:** a **`Source`** dropdown in the control bar (or a `Source…` modal like `BG`),
  listing `list_sources()` with the current one selected; `(default)` pinned first.
- **Device changes / unplug:** selecting a source does a clean `stop()`/`start()`; the
  existing **error banner + periodic recovery** already covers a vanished device. If a
  saved device id is gone on launch, **fall back to default** (never crash).
- **Persist:** `Settings.source_id: str = ""` (`""` ⇒ default). Bump schema; migrate by
  defaulting. Hot-swap requires recreating only the `AudioSource` (loop already tolerant).

**Risks / notes.** Format negotiation differs per device; keep the downmix path central.
Don't promise exclusive-mode or DRM-protected capture (degrade gracefully, banner).

**Tests.** `SyntheticSource` unaffected; unit-test `list_sources()` parsing against a faked
pyaudiowpatch host-API table; `--selftest` stays on `SyntheticSource`.

---

## 0B-b. User custom visual presets ("My modes")

**Goal.** Let the user **save the current mode + all its knobs** under a name, then
re-select it later from a dropdown — like the built-in modes, but user-owned.

**What a preset captures.** A JSON record, *not* code:
`{ name, base_mode_key, options:{<opt_key>: index}, theme:{size, speed, color_scheme},
sensitivity, smoothing }`. (Background/logo stay global — a preset is about the *mode*.)
This composes cleanly because mode options already live as discrete `ModeOption`
indices and the theme is a single shared object — a preset is just a snapshot of them.

**Design.**
- New `presets.py` (sibling to `settings.py`): load/save a **list** of presets to
  `%APPDATA%/AudioVisualizer/presets.json` (own `schema_version`, lenient load).
- **Apply** = set active mode to `base_mode_key`, then push the saved option indices via
  the existing `set_option_index`, and copy theme/sensitivity/smoothing. Unknown option
  keys (mode changed between versions) are **ignored**, not fatal.
- **UI:** a **`Presets`** dropdown listing saved names + a **`Save preset…`** action
  (text entry for the name — needs a tiny text-input modal, the one genuinely new UI
  piece) and **`Delete`**. Keep built-in modes and presets visually distinct (a divider
  or a `★` prefix).
- **Registry stays the source of truth** for built-in modes; presets are a *layer on top*
  that drives the same public setters. **Do not** auto-register presets as fake modes.

**Risks / notes.** The only new primitive is a **text-input field**; spec it small and
reusable (we'll want it again for renaming). Validate/clamp every loaded value through the
same helpers `Settings` uses.

**Tests.** Round-trip a preset; apply a preset with a stale option key (ignored); corrupt
file ⇒ empty list, no crash.

---

## 0B-c. Randomize / auto-cycle with smooth transitions

**Goal.** A "shuffle" that automatically switches between a **user-chosen set** of modes
(built-in and/or custom presets) every **N seconds** (user-set), **cross-fading** rather
than hard-cutting.

**Design.**
- **Selection set:** a checklist (modal) of which built-in modes + presets are in the
  rotation; persisted (`Settings.random_pool: list[str]`, `Settings.random_interval: float`).
  Empty pool ⇒ feature is a no-op.
- **Scheduler** in `app.py`: when "Auto" is on, a timer fires every `interval`, picks the
  next item (shuffled, no immediate repeat), and starts a transition. Manual mode-switch
  resets the timer.
- **Cross-fade (the hard part).** Modes draw straight onto the canvas today. To blend, render
  the **outgoing** and **incoming** modes to two **offscreen surfaces** for the ~0.5–1s
  transition and alpha-composite (`incoming.set_alpha(t*255)`), then drop back to direct
  drawing. This is **opt-in and time-boxed**, so the steady-state cost is unchanged. Respect
  **reduce-motion** (shorten/skip the fade). Both modes get `on_enter`/`on_exit` correctly.
- **UI:** an **`Auto`** toggle + an interval control (reuse the `− value +` stepper) + a
  `Shuffle set…` modal. Could live in the same place as Presets.

**Risks / notes.** Double-rendering during a fade doubles cost briefly — keep transitions
short and only render two modes while `t ∈ (0,1)`. Reuse the offscreen-surface helper that
0B-c introduces for any future "picture-in-picture" idea.

**Tests.** Scheduler picks without immediate repeats; transition starts/ends and leaves
exactly one active mode; headless run with Auto on advances modes without error.

---

### Suggested sequencing
0B-a (self-contained, high value) → 0B-b (adds the reusable text-input + preset store) →
0B-c (depends on the preset store for its pool, and on a new offscreen-compositing helper).
