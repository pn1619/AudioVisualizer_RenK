# macOS Port — Plan & Dev Environment

Companion to `plan/audio-visualizer-plan.md`. The Windows app ships today; **macOS is an
in-progress port** developed in parallel in the **same repo** without breaking Windows.

> Principle: *both platforms must keep working.* macOS-only pieces stay isolated so Windows
> CI, packaging, and capture never regress.

---

## 1. Parallel development rules (mandatory)

| Rule | Windows | macOS |
|------|---------|-------|
| **Runtime deps** | `requirements.txt` | `requirements-mac.txt` |
| **Dev deps** | `requirements-dev.txt` | `requirements-mac-dev.txt` |
| **Tooling** | `tools/*.ps1` (+ `.cmd`) | `tools/mac/*.sh` |
| **Do not** | Add mac-only packages to `requirements.txt` | Add `pyaudiowpatch` to mac requirements |
| **Shared code** | `src/`, `tests/`, `pyproject.toml` | same — one codebase |

### Isolation for platform-specific code

When port work touches Python (not just tooling):

1. **Never import mac-only libraries from shared modules** (`app.py`, `analysis.py`, modes).
2. **Capture stays behind `AudioSource`** — add a macOS `LoopbackSource` (or sibling) in
   `audio/`; `App`/`Analyzer` never import Core Audio / PortAudio directly.
3. **Platform shims** live in dedicated modules (`platform_win.py` today; add
   `platform_mac.py` or rename to `platform_paths.py` when the port lands). Guard with
   `sys.platform`; each shim must import cleanly on the other OS.
4. **Optional deps** use `sys_platform` markers in the **mac** requirements file, or lazy
   imports inside the mac capture module — never in `requirements.txt` unless Windows also
   needs them.
5. **CI:** Windows `build` workflow stays unchanged until a separate macOS job is added;
   mac dev proves green via `./tools/mac/test.sh` + `./tools/mac/run.sh --selftest` locally.

---

## 2. What works on macOS today (dev, pre-port)

| Area | Status |
|------|--------|
| Python 3.12+ venv | `./tools/mac/setup.sh` |
| Visual modes / UI | Runs (GUI + headless) |
| Full pytest suite | `./tools/mac/test.sh` (498+ tests) |
| `--selftest` | `./tools/mac/run.sh --selftest` |
| Settings | `~/.config/AudioVisualizer/` via guarded `platform_win.get_appdata_dir()` |
| System-audio capture | **Not yet** — `SyntheticSource` / tests only |

Windows capture (`pyaudiowpatch` / WASAPI) is unchanged and required only on Windows.

---

## 3. macOS dev quickstart

```bash
./tools/mac/check-deps.sh
./tools/mac/setup.sh
./tools/mac/test.sh
./tools/mac/run.sh --selftest
./tools/mac/run.sh --debug --mode spectrum   # needs a display
```

See `tools/mac/README.md` for the full script table and VS Code notes.

---

## 4. Porting work (later — not started)

Record decisions in `plan/audio-visualizer-plan.md` §8 as they are made.

### macOS port PR roadmap (`A0` milestone)

| Version | PR | Scope |
|---------|-----|--------|
| **`A0.00.01`** | version + CI + **capture spike** | `APP_VERSION_MAC`, `version_info`, mac CI job, `tools/mac/spike-capture.py`, decision #30 |
| **`A0.00.02`** | capture implementation | `capture_mac.py` + `source_factory`, `sounddevice` ring buffer, mic default |
| **`A0.00.03`** | device picker + BlackHole | `devices_mac.py`, Src modal, BlackHole docs |
| **`A0.00.04`** | native loopback (optional) | ScreenCaptureKit system-audio tap |

| Workstream | Notes |
|------------|-------|
| **System-audio capture** | Decision #30: `sounddevice` → BlackHole → ScreenCaptureKit. Spike: `tools/mac/spike-capture.py`. |
| **Device enumeration** | mac analogue of `audio/devices.py`; keep Windows path untouched. |
| **Platform module** | Split/rename `platform_win.py` paths; Retina/windowing polish. |
| **Packaging** | `.app` bundle (PyInstaller or native); separate from `build-exe.ps1`. |
| **CI** | Job `mac` runs `tools/mac/test.sh` + `--selftest`; spike is **manual** (`--list` safe in CI later). |

Open questions (decide before implementation):

1. Capture strategy — virtual loopback driver vs system audio tap API?
2. Minimum macOS version?
3. Code signing / notarization for distribution?

---

## 6. Versioning & tags (macOS line)

Uses the shared `PP.FF.BB` scheme with a **platform prefix in `PP`** (decision #29):

| `PP` | Platform |
|------|----------|
| `00`–`09` | Windows (unchanged) |
| `A0`–`F0` | macOS — **A** = first milestone (dev env), **B**–**F** = later major port steps |

- **First mac milestone (dev env ready):** `A0.00.00` → tag **`vA0.00.00`**
- **`FF` / `BB`:** same as Windows — hex sub-phase and build within the milestone
- **`APP_VERSION`** / **`APP_VERSION_MAC`** in `config.py`; runtime pick via
  **`version_info.app_version()`** (About, window title, `--version`, saved looks)

Full convention: `plan/git-and-versioning.md` §3.1–§4.

---

## 7. CI (GitHub Actions)

| Job | Runner | What it proves |
|-----|--------|----------------|
| **`build`** | `windows-latest` | lint, pytest, PyInstaller `.exe`, `--selftest` (required for merge) |
| **`mac`** | `macos-latest` | `tools/mac/setup.sh`, check-deps, pytest, `--selftest` |

The **`mac`** job is additive — it does not replace Windows **`build`**. To require mac
green before merge, add the `mac` status check to the branch ruleset.

---

## 5. Verification checklist (mac dev env)

Before starting port PRs, confirm:

- [ ] `./tools/mac/check-deps.sh` → ready
- [ ] `./tools/mac/test.sh` → all green
- [ ] `./tools/mac/run.sh --selftest` → exit 0
- [ ] No edits to `requirements.txt` / `tools/*.ps1` unless fixing Windows too
- [ ] New mac-only code lives under `tools/mac/`, `requirements-mac*.txt`, or guarded `audio/` / `platform_*` modules
