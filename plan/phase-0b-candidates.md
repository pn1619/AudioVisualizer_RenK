# Phase 0B candidates (planning only — not implemented)

> Scope note: these are **design plans** to keep `v00.0A.0x` small and revertible.
> Target them for **`v00.0B.00`+**. Each keeps our locked stack (pygame + numpy +
> pyaudiowpatch) and the existing seams (`AudioSource`, `registry`, `ControlBar`,
> versioned `Settings`). No code yet — this is the agreed direction.

---

## 0B-a. Selectable sound source

> **Status: implemented in `v00.0B.01`.** Shipped as `audio/devices.py`
> (`list_sources`/`find_device_info`), `LoopbackSource(device_id=...)`, a `Src` button +
> `ui/source_panel.py` modal, and `Settings.source_id` (schema v8). The notes below are the
> original design and remain accurate.

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

## 0B-b. User custom visual looks ("My Looks")

> **Status: build 1 implemented in `v00.0B.02`.** Shipped `looks.py` (store + CRUD +
> export/import), `ui/text_input.py`, `ui/looks_panel.py`, the `My Looks` dropdown + `Save…`
> button, capture/apply/baseline-restore + dirty tracking in `app.py`, and `Settings.active_look`
> (schema v9). **Deferred to build 2:** per-domain Background/Logo **Local | Global** linking
> (currently both captured as Local), the full read-only **overlay resolver**, reorder /
> export / import in the modal UI, name-collision prompts, and shipped read-only starter looks.
> The notes below remain the target design.

**Goal.** Let the user **save a complete look** — the mode + all its knobs, the theme, and
(per-domain, optionally) the global Background/Logo — under a name, then re-select it later
from a dropdown, like the built-in modes but user-owned.

> **Naming (important — do not conflate with the per-mode "Preset" dropdown).** The word
> **"Preset"** is reserved for the shipped, developer-authored `BaseVisualizer.PRESETS` (a
> leading **Preset** option that loads a fixed combo of *that one mode's* other options;
> session-only, in memory). This 0B-b feature is **user-authored and persisted**, called
> **"My Looks"** in the UI; each saved item is a **"look"** stored in `looks.json`. It is a
> layer on top of the registry, **not** a mode's built-in `PRESETS`. The two never share a
> label: the bar reads `Preset: Classic` (per-mode) vs `My Looks: Neon night` (user-saved).
>
> Two separate UI affordances (also do not conflate): a **Save button/action**
> (`Save look…`) that writes the current look, and a **separate Load dropdown** (`My Looks`)
> that re-selects a saved look.

**A look captures everything about a *look*** — the mode and its knobs, the theme, and
(optionally) the global Background/Logo. The trick is letting Background/Logo be either a
**frozen snapshot** baked into the look or a **live pointer** to the global setting,
chosen **per domain**, without the act of using a look ever corrupting the real global.

**Core invariant (this is what makes it safe).** There is **one canonical "live global"**
state (today's `Settings`: Background, Logo, Theme, sensitivity, smoothing). **A look is a
read-only overlay on top of it — applying or switching a look NEVER writes into live
global.** Effective display = `live global`, with the look's pinned domains overriding it.
Because global is never clobbered, a look that *links* a domain always re-derives from the
true, untouched global — even right after a different look *pinned* that same domain. So
`app.py` renders Background/Logo/Theme by asking a small **resolver** ("give me the effective
config") rather than reading `Settings` directly.

**Local vs Global, per domain.** Each look marks **Background** and **Logo**
independently as:
- **Local** — a **frozen snapshot** of those values, captured at save time and shown when
  the look is active. (Mode, options, theme, sensitivity, smoothing are *always* Local —
  a look is fundamentally a captured look.)
- **Global** — no stored values; the domain **follows live global**, so it shows whatever
  the user's current global Background/Logo is.

**What a look captures.** A JSON record, *not* code:
```jsonc
{
  "id": "b3f1…",                               // stable uuid4; referenced by active_look
  "name": "Neon night",                        // user-editable label
  "base_mode_key": "lightshow",
  "options": { "particles": 2, "core": 1 },    // mode knobs (always captured)
  "theme": { "size": 1.0, "speed": 1.2, "color_scheme": "rainbow_plus" },
  "sensitivity": 1.3, "smoothing": 0.6,
  "background": { "link": "local",  "value": { "mode": "aurora", "opacity": 0.6, ... } },
  "logo":       { "link": "global" },          // no value -> follow live global
  "created_at": "2026-06-18T20:00:00Z",        // metadata
  "updated_at": "2026-06-18T20:00:00Z",
  "app_version": "00.0B.0x"                     // for diagnostics / future migration
  // "readonly": true                          // only on shipped starter looks; never persisted to looks.json
}
```
This composes cleanly because mode options already live as discrete `ModeOption` indices,
the theme is one shared object, and Background/Logo configs are plain dicts in `Settings`.

**Editing rules while a look is active** (one consistent rule):
- Editing a **pinned aspect** (mode options, theme via the steppers, sensitivity/smoothing,
  or a Background/Logo domain set to **Local**) edits the **active look** and marks it
  **dirty** → offer **Update look** / **Save as new** / **Revert**.
- Editing a **Global-linked** Background/Logo domain edits the **real live global** (so the
  change is intentionally visible in every Global-linked look and in the no-look
  baseline). The active look stays clean.
- With **no look active ("None / Live")**, every control edits live global — today's
  behavior, unchanged.

**Design.**
- New `looks.py` (sibling to `settings.py`): load/save a **list** of looks to
  `%APPDATA%/AudioVisualizer/looks.json` (own `schema_version`, lenient load).
- A small **resolver** owns "effective config": `effective_theme()`, `effective_background()`,
  `effective_logo()` = look snapshot when Local, else live global. `app.py` and the
  overlays read through it; live global remains the single source of truth.
- **Apply** = set active mode to `base_mode_key`, push saved option indices via the existing
  `set_option_index`, install the theme/sens/smoothing + Local Background/Logo as overlay
  overrides (NOT into `Settings`). Unknown option keys (mode changed between versions) are
  **ignored**, not fatal.
- **UI (two distinct affordances — keep them separate):**
  - a **Load dropdown** labeled **`My Looks`** that always starts with **`None / Live`**
    (deselect → pure global), then saved names (visually distinct from built-in modes — a
    divider or `★`). This is the "load what I saved" control.
  - a **Save button/action** **`Save look…`** (tiny text-input modal — the one genuinely
    new UI primitive) plus **`Update`**, **`Delete`**, **`Rename`**. The Save/edit affordance
    exposes the per-domain **Background: Local | Global** and **Logo: Local | Global**
    dropdowns.
- **UI clarity (must not be confused with the per-mode `Preset` dropdown).** The per-mode
  `Preset` lives in **row 2** with the other mode-option dropdowns (`ui/controls.py`
  `_row2_items`). To keep the two visually and conceptually distinct:
  - **Place `My Looks` + `Save look…` in row 1** (the global controls row, near the mode
    picker `< [mode] >`) — a *different row* from `Preset`, since a look is global/cross-mode
    while a preset tweaks the current mode.
  - **Two separate widgets, not one combo:** a **`Dropdown(title="My Looks")`** for loading
    and a **distinct `Button` labeled `Save…`** (with a save glyph) immediately to its right,
    so "pick a saved look" vs "create a new one" read as two obviously different controls.
  - **Distinct labels:** the dropdown title is **`My Looks`** (never "Preset"); its first
    row is the **`None / Live`** sentinel; saved entries get a divider/`★`. The per-mode one
    keeps its **`Preset`** title. Different title + different row = no collision.
  - When a look is **dirty**, mark it visibly (e.g. trailing `*` on the `My Looks` label) so
    Save/Update intent is obvious; keep within the existing bar/font styling (no new theme).
- **Relaunch:** remember the **last active look** by its **stable id**
  (`Settings.active_look: str = ""`, `""` ⇒ None/Live; bump settings schema, migrate by
  defaulting). On load, re-select it and re-derive its Global-linked domains from the
  *current* global (which may have changed). Using the **id, not the name**, means a rename
  never breaks restore.
- **Registry stays the source of truth** for built-in modes; looks are a *layer on top*
  that drives the same public setters. **Do not** auto-register looks as fake modes.

### Persistence & save interface (the durable contract)

**(1) Format, structure & file — where saved looks live.** Reuse the **proven `settings.py`
idioms verbatim** so we don't invent a second persistence story:
- **Separate JSON file** `%APPDATA%/AudioVisualizer/looks.json` (sibling to `settings.json`,
  via `platform_win.get_appdata_dir()`). **Not** folded into `settings.json` — a malformed
  look must never be able to break core settings, and the diffs/blast-radius stay small.
- **Top-level object, not a bare array**, so we can version and extend it:
  ```jsonc
  {
    "schema_version": 1,
    "looks": [ { /* look record */ }, { /* look record */ } ]   // order == dropdown order
  }
  ```
- **Each look record** carries a **stable `id` (uuid4) + editable `name`** (so rename/
  duplicate are clean and `active_look` survives renames), plus the captured look (the JSON
  in "What a look captures" above), plus light metadata: `created_at` / `updated_at` (ISO
  8601) and `app_version` at save time (diagnostics + future migration hints).
- **Atomic, best-effort writes** exactly like `settings.save`: write `looks.json.tmp`, then
  `tmp.replace(path)`; return `bool`, never raise. **Keep one `looks.json.bak`** of the last
  good file before replacing, so a crash mid-write is recoverable.
- **Lenient load** like `settings.load`: missing/corrupt file ⇒ **empty list** (feature just
  shows `None / Live`), never crash.

**(2) Versioning & compatibility — looks must survive future app versions.** This is the part
most likely to bite, so spell it out:
- **Own `schema_version`** on the file (independent of the settings schema). A `_migrate()`
  walks known older versions forward; an **unknown/newer** version is read **leniently**
  (honor recognized keys, default the rest) — same philosophy as `settings._migrate`.
- **Per-look isolation (key difference from settings).** Settings is one object; looks are a
  **list**, so validate **each look independently** and **skip a single bad look** (logged)
  instead of discarding the whole file. One corrupt entry never loses the others.
- **Forward-compatible round-trip (prevents silent data loss).** When an *older* app opens a
  *newer* file, stash each look's **unrecognized keys in a per-look `_extra` bag and re-emit
  them on save**. Without this, an old build that re-saves would strip fields a newer build
  added — quietly corrupting the user's looks. With it, looks degrade and round-trip losslessly.
- **Value drift is clamped, never fatal**, through the **same validators `settings.py` uses**
  (`_choice`, `_snap`, `_opacity`, …) and **`MERGED_MODE_KEYS`** for renamed modes: a removed
  color scheme snaps to default, a renamed `base_mode_key` remaps, stale option keys are
  ignored, missing options default.
- **Missing mode degrades, doesn't delete.** If `base_mode_key` no longer exists, **keep the
  record**, mark the look **unavailable** (greyed/disabled in the dropdown) — never auto-delete
  a user's data on load. Answer to "will my looks break?": **no** — worst case a look is
  shown disabled until that mode returns; everything else loads.

**(3) Save UX — create-new vs overwrite (your idea, refined).** Hitting **`Save look…`** opens
a small modal that makes the choice explicit instead of guessing:
- Fields: a **name text input** (prefilled) + a **`Create new` / `Overwrite existing`** choice
  (Overwrite reveals a picker of existing looks) + the per-domain **Background/Logo
  Local|Global** toggles.
- **Smart default:** if a look is **active and dirty**, default to **Overwrite "<that look>"**;
  if none is active, default to **Create new** with a suggested name.
- **Name-collision guard:** `Create new` with an existing name ⇒ prompt **Overwrite or
  Rename?** — never silently clobber, never silently duplicate.
- **Confirm destructive actions:** overwrite ("Replace the saved 'X'?") and **Delete**.
- **Two quick paths in the bar** so the common cases skip the modal: **`Update`** (overwrite
  the active look in place) and **`Save as new…`** (always creates). The modal is for first
  save / ambiguous cases / renaming.

**(4) Library management — in scope for 0B-b.** These are **committed**, not optional; they
fall out cheaply once looks have stable ids + a list file, and they make the feature feel
finished:
- **Duplicate** a look (clone → tweak). New `id`, name suffixed `" copy"`; inserted right
  after the source so it's easy to find.
- **Reorder** looks (move up / move down) since list order == dropdown order; the new order
  is persisted on change.
- **Export / Import** a single look as a `.look.json` file. Export writes one look record
  (carrying its `schema_version`); import validates/clamps through the same loaders, assigns
  a **fresh `id`** (never trust an imported id — avoids collisions), and resolves name clashes
  with the same Overwrite/Rename prompt as Save. Looks are self-contained JSON, so this is the
  shareability win for a shippable app.
- **Built-in starter looks** shipped **read-only** (a couple of curated looks that showcase
  the feature). `Update`/`Delete`/`Rename` are disabled on them, but **Duplicate** lets a user
  base their own editable look on one. Marked via a `readonly: true` flag (and never written
  back to `looks.json`; they live in code/asset and merge in at load, deduped by id).
- **Revert** while a look is dirty: re-apply the saved values, clearing the dirty mark.
- **Guard rails:** cap count (e.g. ≤100), cap/trim/sanitize names, dedupe ids on load. Keeps
  the file small and the dropdown usable.
- **Deferred (explicitly out of 0B-b):** per-look **thumbnail** previews — heavier (screenshot
  capture + storage); revisit after the core library ships.

**Library UI surface.** The `Save/edit` modal (or a small **`Manage looks…`** modal reachable
from the `My Looks` area) hosts the management actions — **Duplicate, Move ↑/↓, Export…,
Import…, Rename, Delete, Revert** — so row 1 stays uncluttered (just the `My Looks` dropdown +
`Save…` button). Read-only starter looks render with a lock/★ and disabled destructive actions.

**Risks / notes.**
- The **resolver indirection** is the key structural change — without it, "apply" tends to
  write into `Settings` and silently destroys the global the user expected to come back to.
- New primitive is a **text-input field**; spec it small and reusable (rename needs it too).
- Validate/clamp every loaded value through the same helpers `Settings` uses; a Local
  Background/Logo snapshot from an older schema must clamp/migrate, never crash.
- A deleted/edited mode referenced by a look must degrade (ignore stale keys; if the
  `base_mode_key` is gone, mark the look unavailable, don't crash).

**Tests.** Round-trip a look (Local and Global domains); **applying a look does not
mutate live global** (the invariant — assert global dict is byte-identical after apply +
switch + deselect); switch Local→Global look re-derives from live global; editing a
Global-linked domain updates global and leaves the look clean; editing a pinned aspect
marks the look dirty; stale option key ignored; missing `base_mode_key` is non-fatal
(look kept + marked unavailable, not deleted); last-active-look restored **by id** after a
rename. Persistence specifics: atomic save writes `.tmp`+`.bak` and never raises; **corrupt
file ⇒ empty list**, no crash; **one malformed look is skipped, the rest load**; **unknown
future keys survive a load→save round-trip** (forward-compat `_extra` bag); removed
color-scheme/option values **clamp to defaults** via the shared validators; save modal
**create-new vs overwrite** picks the right target and **name collision prompts** instead of
clobbering. Library management: **duplicate** yields a new id + `" copy"` name and preserves
the original; **move up/down** reorders and persists; **export then import** round-trips a
single look and the **import assigns a fresh id** (never reuses the file's id) and prompts on
name clash; **read-only starter looks** can be duplicated but not updated/deleted/renamed and
are never written into `looks.json`; **revert** restores saved values and clears dirty; guard
rails enforce the **count cap** and **name sanitize/trim**, and **ids are deduped on load**.

---

## 0B-c. Randomize / auto-cycle with smooth transitions

> **Build plan.** **Build 1 (`v00.0B.03`) = built-in modes only**, crossfade + cut
> (reduce-motion → cut). Modes-only auto-cycle touches **no global state** (Background/Logo/
> theme are untouched by a mode swap), so it needs **no overlay resolver**. **Build 2** adds
> **saved looks** to the pool — that mutates live global per tick, so it lands **after** the
> 0B-b build-2 overlay resolver, which gives a clean pre-shuffle snapshot/restore.
>
> **Status: build 1 implemented in `v00.0B.03`.** Shipped as `visuals/_transition.py`
> (`ModeTransition`), `App._update_auto`/`_auto_advance`/`_draw_transition`, an `Auto` toggle +
> `Shuffle…` button (and the `A` key), `ui/shuffle_panel.py`, and `Settings.random_pool` /
> `random_interval` (schema v10). Auto is never persisted on. The notes below are the original
> design; **saved looks in the pool + dip-to-black / beat-synced styles remain for build 2.**

**Goal.** A "shuffle" that automatically switches between a **user-chosen set** of modes
(built-in and/or saved looks) every **N seconds** (user-set), **cross-fading** rather
than hard-cutting.

**Design.**
- **Selection set:** a checklist (modal) of which built-in modes + looks are in the
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
  `Shuffle set…` modal. Could live in the same place as My Looks.

**Risks / notes.** Double-rendering during a fade doubles cost briefly — keep transitions
short and only render two modes while `t ∈ (0,1)`. Reuse the offscreen-surface helper that
0B-c introduces for any future "picture-in-picture" idea.

**Tests.** Scheduler picks without immediate repeats; transition starts/ends and leaves
exactly one active mode; headless run with Auto on advances modes without error.

---

### Suggested sequencing
0B-a (self-contained, high value) → 0B-b (adds the reusable text-input + looks store) →
0B-c (depends on the looks store for its pool, and on a new offscreen-compositing helper).
