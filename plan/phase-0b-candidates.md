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

**Goal.** Let the user **save a complete look** — the mode + all its knobs, the theme, and
(per-domain, optionally) the global Background/Logo — under a name, then re-select it later
from a dropdown, like the built-in modes but user-owned.

> **Not the same as the shipped per-mode Preset dropdown.** v00.0A.07 added curated,
> developer-authored `BaseVisualizer.PRESETS` (a leading **Preset** option that loads a
> fixed combo of that mode's other options; session-only). 0B-b is **user-authored,
> persisted** presets stored in `presets.json` — a layer on top of the registry, not a
> mode's built-in `PRESETS`.

**A preset captures everything about a *look*** — the mode and its knobs, the theme, and
(optionally) the global Background/Logo. The trick is letting Background/Logo be either a
**frozen snapshot** baked into the preset or a **live pointer** to the global setting,
chosen **per domain**, without the act of using a preset ever corrupting the real global.

**Core invariant (this is what makes it safe).** There is **one canonical "live global"**
state (today's `Settings`: Background, Logo, Theme, sensitivity, smoothing). **A preset is a
read-only overlay on top of it — applying or switching a preset NEVER writes into live
global.** Effective display = `live global`, with the preset's pinned domains overriding it.
Because global is never clobbered, a preset that *links* a domain always re-derives from the
true, untouched global — even right after a different preset *pinned* that same domain. So
`app.py` renders Background/Logo/Theme by asking a small **resolver** ("give me the effective
config") rather than reading `Settings` directly.

**Local vs Global, per domain.** Each preset marks **Background** and **Logo**
independently as:
- **Local** — a **frozen snapshot** of those values, captured at save time and shown when
  the preset is active. (Mode, options, theme, sensitivity, smoothing are *always* Local —
  a preset is fundamentally a captured look.)
- **Global** — no stored values; the domain **follows live global**, so it shows whatever
  the user's current global Background/Logo is.

**What a preset captures.** A JSON record, *not* code:
```jsonc
{
  "name": "Neon night",
  "base_mode_key": "lightshow",
  "options": { "particles": 2, "core": 1 },   // mode knobs (always captured)
  "theme": { "size": 1.0, "speed": 1.2, "color_scheme": "rainbow_plus" },
  "sensitivity": 1.3, "smoothing": 0.6,
  "background": { "link": "local",  "value": { "mode": "aurora", "opacity": 0.6, ... } },
  "logo":       { "link": "global" }           // no value -> follow live global
}
```
This composes cleanly because mode options already live as discrete `ModeOption` indices,
the theme is one shared object, and Background/Logo configs are plain dicts in `Settings`.

**Editing rules while a preset is active** (one consistent rule):
- Editing a **pinned aspect** (mode options, theme via the steppers, sensitivity/smoothing,
  or a Background/Logo domain set to **Local**) edits the **active preset** and marks it
  **dirty** → offer **Update preset** / **Save as new** / **Revert**.
- Editing a **Global-linked** Background/Logo domain edits the **real live global** (so the
  change is intentionally visible in every Global-linked preset and in the no-preset
  baseline). The active preset stays clean.
- With **no preset active ("None / Live")**, every control edits live global — today's
  behavior, unchanged.

**Design.**
- New `presets.py` (sibling to `settings.py`): load/save a **list** of presets to
  `%APPDATA%/AudioVisualizer/presets.json` (own `schema_version`, lenient load).
- A small **resolver** owns "effective config": `effective_theme()`, `effective_background()`,
  `effective_logo()` = preset snapshot when Local, else live global. `app.py` and the
  overlays read through it; live global remains the single source of truth.
- **Apply** = set active mode to `base_mode_key`, push saved option indices via the existing
  `set_option_index`, install the theme/sens/smoothing + Local Background/Logo as overlay
  overrides (NOT into `Settings`). Unknown option keys (mode changed between versions) are
  **ignored**, not fatal.
- **UI:** a **`Presets`** dropdown that always starts with **`None / Live`** (deselect → pure
  global), then saved names (visually distinct from built-in modes — a divider or `★`).
  Actions: **`Save preset…`** (tiny text-input modal — the one genuinely new UI primitive),
  **`Update`**, **`Delete`**, **`Rename`**. The Save/edit affordance exposes the per-domain
  **Background: Local | Global** and **Logo: Local | Global** dropdowns.
- **Relaunch:** remember the **last active preset** (`Settings.active_preset: str = ""`,
  `""` ⇒ None/Live; bump settings schema, migrate by defaulting). On load, re-select it and
  re-derive its Global-linked domains from the *current* global (which may have changed).
- **Registry stays the source of truth** for built-in modes; presets are a *layer on top*
  that drives the same public setters. **Do not** auto-register presets as fake modes.

**Risks / notes.**
- The **resolver indirection** is the key structural change — without it, "apply" tends to
  write into `Settings` and silently destroys the global the user expected to come back to.
- New primitive is a **text-input field**; spec it small and reusable (rename needs it too).
- Validate/clamp every loaded value through the same helpers `Settings` uses; a Local
  Background/Logo snapshot from an older schema must clamp/migrate, never crash.
- A deleted/edited mode referenced by a preset must degrade (ignore stale keys; if the
  `base_mode_key` is gone, mark the preset unavailable, don't crash).

**Tests.** Round-trip a preset (Local and Global domains); **applying a preset does not
mutate live global** (the invariant — assert global dict is byte-identical after apply +
switch + deselect); switch Local→Global preset re-derives from live global; editing a
Global-linked domain updates global and leaves the preset clean; editing a pinned aspect
marks the preset dirty; stale option key ignored; missing `base_mode_key` is non-fatal;
corrupt file ⇒ empty list, no crash; last-active-preset restored on reload.

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
