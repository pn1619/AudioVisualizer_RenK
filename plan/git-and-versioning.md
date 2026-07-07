# Git Workflow & Version/Tag Conventions

Companion to `plan/audio-visualizer-plan.md`. The **single source of truth** for
how we branch, commit, version, and tag. Keep it in sync with `config.py`
(`APP_VERSION`) and `CHANGELOG.md`.

> Principle (same as everywhere): *simple but works*. A small, predictable git
> flow that maps cleanly onto the phased roadmap.

---

## 1. Branching model

- **`main` is always releasable and green** (tests + lint + `--selftest` pass).
  Don't develop directly on `main`; it only advances through reviewed merges.
- Do work on a short-lived **`feature/<topic>`** branch (e.g.
  `feature/audio-visualizer-phases-0-2`, `feature/settings-persistence`).
- Open a **pull request into `main`**. A PR must be green (pytest, ruff, black,
  `--selftest`) before merge.
- Keep one logical change per PR where practical; prefer small, reviewable PRs.

## 1.1 Pull-request-only policy (mandatory — humans and AI agents)

`main` is **protected**: everything lands through a reviewed pull request. This is
enforced by a GitHub **branch ruleset** on `main` *and* is a hard rule for any AI
agent working in this repo.

- **Never commit or push directly to `main`.** Always branch `feature/<topic>`,
  push the branch, and open a PR. Direct pushes to `main` are rejected by the ruleset.
- **AI agents only create commits / pushes / PRs when the repo owner explicitly asks.**
  Do not commit or push proactively; make the edits and stop until asked.
- **AI agents never merge and never approve PRs.** Open the PR, hand the owner the
  PR link, and stop. The repo owner **pn1619** reviews the diff and merges.
- **CI (`build`) must be green before merge** (pytest + ruff + black + `--selftest`
  + exe build). The ruleset requires the `build` status check to pass.
- **`main` blocks force-pushes and deletion.** The owner (`pn1619`, Repository admin)
  is on the ruleset **bypass list**, so only they retain force-merge/override for
  emergencies — agents must not attempt to bypass, force-push, or override.
- One logical change per PR where practical; prefer small, reviewable PRs.

> Setup reference: repo → Settings → Rules → Rulesets → a ruleset named `Protect main`
> targeting the default branch, with *Require a pull request before merging*
> (0 required approvals — a solo owner can't self-approve, so the **merge** is the
> control gate), *Require status checks to pass* → `build`, *Block force pushes*,
> *Restrict deletions*, and a **bypass = Repository admin** so `pn1619` keeps
> force-merge. Recorded in `plan/audio-visualizer-plan.md` §8 (decision 27).

## 2. Commit messages

- Imperative summary with a conventional prefix:
  `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`, `build:`.
- The body explains **why**, not just what (matches the code-comment rule).
- Example: `feat: import Audio Visualizer (Phases 0-2)`.

## 3. Versioning — `PP.FF.BB`

The version string lives **once** in `config.py` as `APP_VERSION` and is surfaced
in the HUD and `--version`. Format `PP.FF.BB` (zero-padded, two digits each):

| Field | Meaning | Rule |
|-------|---------|------|
| `PP` | Pre-release marker | Stays `00` until the first public ship; bumps thereafter. |
| `FF` | Development phase (**hex**, two digits) | `00` = Phase 0/0.5, `01` = Phase 1, … `09` = Phase 9, **`0A` = Phase 10**, `0B` = Phase 11, … |
| `BB` | Build/iteration within the phase (hex) | Starts at `00` each phase; bump for notable intra-phase builds. |

- `FF`/`BB` are **two-digit hex** so phase 10+ stays two characters: Phase 10 is `0A`,
  and its intra-phase builds count `…06`, `07`, `08` (Phase 10.08 → `BB = 08`).
- **Bump `APP_VERSION` in the same change** that advances the phase/build, and add
  a matching `CHANGELOG.md` entry.
- Examples: `00.00.00` (Phase 0), `00.01.00` (Phase 1), `00.03.00` (Phase 3),
  `00.0A.07` (Phase 10.07), `00.0A.08` (Phase 10.08).

### 3.1 Platform encoding in `PP` (Windows vs macOS)

The **first character of `PP`** (high nibble, hex) identifies the **platform line** so
git tags and releases never collide across Windows and macOS, while **`FF` and `BB` keep
the same meaning** (development sub-phase and build, both hex).

| `PP` range | Platform | Rule |
|------------|----------|------|
| **`00`–`09`** | **Windows** | Existing shipped line. `00` = pre-ship; bump `PP` at the first public Windows release. Current: `00.0B.2D`. |
| **`A0`–`F0`** | **macOS** | Port line. **One letter per major mac milestone** — `A0` = first mac milestone (dev env / scaffolding), `B0` = next (e.g. capture), … `F0` = sixth reserved bucket. |

**How to read a mac version:** `A0.FF.BB` — `A0` is the mac milestone; `FF`/`BB` count
sub-phases and builds **inside** that milestone exactly like Windows.

**Examples**

| Version | Tag | Meaning |
|---------|-----|---------|
| `00.0B.2D` | `v00.0B.2D` | Windows build (current `main`) |
| `A0.00.00` | `vA0.00.00` | macOS milestone A — dev environment ready |
| `A0.01.00` | `vA0.01.00` | macOS milestone A — next sub-phase (e.g. capture spike) |
| `B0.00.00` | `vB0.00.00` | macOS milestone B — major next step (e.g. capture shipped) |

**In-app version string**

- `config.py` **`APP_VERSION`** is the **Windows canonical** version (CI, `.exe`
  version resource). **`APP_VERSION_MAC`** is the **macOS canonical** version.
  **`version_info.app_version()`** picks at runtime (`darwin` → mac line).
- A single commit may carry **both** tags when a change is platform-neutral (e.g.
  `v00.0B.2E` + `vA0.00.00` on the mac-dev-env merge).

**CHANGELOG:** Windows entries stay under `00.x.x`; add a **macOS** section (or
sub-entries) keyed to `A0`/`B0`/… versions when mac milestones land. See
`plan/macos-port.md`.

## 4. Tags & releases

### Windows

- Tag a **completed phase** (after its exit criteria + tests/lint/`--selftest` are
  green) with an **annotated** tag named **`v` + the exact `APP_VERSION`**:
  - Phase 2 → `v00.02.00`, Phase 3 → `v00.03.00`, etc.
- The tag name maps **1:1** to `APP_VERSION` so `git tag` and the in-app version
  always agree on Windows builds.

### macOS

- Use the **`A0`–`F0` `PP` line** (§3.1). Tag mac milestones the same way:
  **`v` + mac version** (e.g. `vA0.00.00` when the dev environment is complete).
- macOS tags are **independent** of Windows tags — both may point at the same commit.
- macOS GitHub Releases (when added) attach the `.app` / disk image, not the `.exe`.
- Create it on the commit that completes the phase, then push the tag:

```powershell
git tag -a v00.03.00 -m "Phase 3: settings, device-change resilience, single .exe"
git push origin v00.03.00
```

- Optionally promote a tag to a **GitHub Release** (attach the built
  `AudioVisualizer.exe` once Phase 3's packaging is final).
- Intra-phase milestones may bump `BB` and tag `v00.FF.BB` if useful, but a tag
  per phase is the baseline expectation.
- **Renaming a tag** = create the new tag on the same commit, delete the old one
  locally (`git tag -d <old>`) and on the remote (`git push origin --delete <old>`),
  then push the new tag. (This is how `v0.2.0` → `v00.02.00` was fixed.)

## 5. Environment notes (not committed config)

- **NEVER change global git config as part of automated work**; pass per-command
  flags instead.
- Behind an SSL-inspecting corporate proxy, push with the Windows cert store:
  `git -c http.sslBackend=schannel push …` (avoid disabling `http.sslVerify`).
- If git has no user identity in this environment, author per-command with
  `git -c user.name=… -c user.email=… commit …` rather than writing global config.

## 6. Where this is referenced

- `plan/audio-visualizer-plan.md` §8 (decision) and companion-docs list.
- `plan/development-phases.md` ("tag the phase" in the per-phase checklist).
- `.cursor/rules/python-audio-visualizer.mdc` ("Version control & releases").
- `.cursor/skills/audio-visualizer/SKILL.md` ("Read first" table).
- `CHANGELOG.md` (version-scheme header; entries map to tags).
