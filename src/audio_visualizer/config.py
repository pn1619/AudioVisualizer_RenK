"""Project-wide constants and defaults (no logic lives here).

Version scheme ``PP.FF.BB``:
    PP  pre-release marker (stays ``00`` until we ship)
    FF  development phase (``00`` = Phase 0/0.5, ``01`` = Phase 1, ...)
    BB  build/iteration within that phase
So ``00.01.00`` == "Phase 1, build 0". See plan/development-phases.md.

Magic-number policy (see .cursor/rules/python-coding-style.mdc):
    - **Shared / global / cross-mode** tunables live here as ``UPPER_SNAKE_CASE``.
    - **Mode-local "feel" numbers** live as commented ``_UPPER_SNAKE`` module
      constants at the top of that mode's file (close to where they're used).
    Either way, no unexplained literals sit inside logic.
"""

from __future__ import annotations

APP_NAME = "AudioVisualizer"
# Each PP.FF.BB part is HEX (parsed base-16), so BB counts 08, 09, 0A, 0B, … 0F, 10.
# FF is the development phase ("0A", "0B", …); BB is the build within the phase.
# (Builds 0A-0F were briefly mis-tagged in decimal as .10-.15; corrected to hex.)
APP_VERSION = "00.0B.15"
# Shown in the About dialog. BUILD_DATE is bumped when a build is cut.
APP_OWNER = "pn1619"
APP_BUILD_DATE = "2026-06-19"

# --- Window / rendering -------------------------------------------------------
DEFAULT_WINDOW_SIZE: tuple[int, int] = (1280, 720)
MIN_WINDOW_SIZE: tuple[int, int] = (640, 360)
TARGET_FPS = 60
# Baseline two-row control-bar height (global controls + color/per-mode options).
# The bar now flows/wraps its widgets to the window width and grows taller as
# needed (see ControlBar.content_height); this stays the default for Layout.
CONTROL_BAR_HEIGHT = 88

# --- Control-bar flow layout --------------------------------------------------
# Widgets flow left-to-right and wrap to a new line when they'd leave the window,
# so nothing ever spills off-screen (even at MIN_WINDOW_SIZE). All derived; no
# hard-coded widget coordinates live outside ControlBar.
CONTROL_ROW_HEIGHT = 30  # height of one widget / one flowed row
CONTROL_GAP = 6  # gap between widgets and between wrapped rows

# --- Colors (RGB) -------------------------------------------------------------
COLOR_BG = (10, 10, 18)
# Control-bar strip: between the canvas bg and the widget panels so widgets pop.
COLOR_BAR = (16, 16, 26)
COLOR_PANEL = (30, 30, 46)
COLOR_PANEL_HOVER = (48, 48, 72)
# Subtle always-on widget outline (flat style) for definition without noise.
COLOR_BORDER = (58, 58, 84)
COLOR_TEXT = (228, 228, 240)
COLOR_TEXT_DIM = (140, 140, 160)
COLOR_ACCENT = (90, 200, 255)
COLOR_WARN = (240, 180, 80)
COLOR_ERROR = (240, 90, 90)

# --- UI appearance (user-selectable; persisted) -------------------------------
# Control-bar / widget look. "flat" = solid rounded panels with crisp borders;
# "glass" = pill-shaped translucent panels with an accent glow. Read at draw time
# from ui/style.py so the look switches live from the Appearance panel.
UI_STYLES: tuple[str, ...] = ("flat", "glass")
UI_STYLE_DEFAULT = "flat"
UI_STYLE_LABELS: dict[str, str] = {"flat": "Flat", "glass": "Glass"}

# Text font family. "mono" = a modern terminal-style monospace (Cascadia/Consolas,
# like Cursor's terminal); "sans" = a clean UI sans. We pass the comma-separated
# preference list to pygame's SysFont, which picks the first installed family.
UI_FONTS: tuple[str, ...] = ("mono", "sans")
UI_FONT_DEFAULT = "mono"
UI_FONT_LABELS: dict[str, str] = {"mono": "Mono (terminal)", "sans": "Sans"}
UI_FONT_FAMILIES: dict[str, str] = {
    "mono": "cascadiamono,cascadiacode,consolas,jetbrainsmono,couriernew,monospace",
    "sans": "segoeui,inter,arial,helvetica,sans",
}
UI_FONT_SIZE = 15
UI_FONT_SIZE_SMALL = 14

# Accent color for active/hover highlights. "cyan"/"green" are solid; "aurora" is a
# magenta->cyan horizontal gradient glow (the premium Concept-B look). The gradient
# entry's text color falls back to its cyan end so labels stay readable.
UI_ACCENTS: tuple[str, ...] = ("cyan", "aurora", "green")
UI_ACCENT_DEFAULT = "cyan"
UI_ACCENT_LABELS: dict[str, str] = {
    "cyan": "Cyan",
    "aurora": "Aurora (magenta->cyan)",
    "green": "Neon green",
}
# Solid accent RGB per key (the gradient entry uses its B endpoint here for text).
UI_ACCENT_COLORS: dict[str, tuple[int, int, int]] = {
    "cyan": (90, 200, 255),
    "aurora": (90, 200, 255),
    "green": (110, 240, 150),
}
# Two-color horizontal gradient for gradient accents (A on the left -> B on right);
# None means the accent is a flat color.
UI_ACCENT_GRADIENTS: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]] | None] = {
    "cyan": None,
    "aurora": ((255, 70, 200), (90, 200, 255)),
    "green": None,
}

# Palette used by spectrum / light-show modes (low -> high frequency).
PALETTE: tuple[tuple[int, int, int], ...] = (
    (90, 200, 255),
    (120, 160, 255),
    (180, 130, 255),
    (255, 110, 200),
    (255, 140, 100),
    (255, 210, 90),
)

# --- Audio / DSP --------------------------------------------------------------
SAMPLE_RATE_FALLBACK = 48000
RING_BUFFER_SECONDS = 0.5
FFT_SIZE = 2048
BAND_COUNT = 48
MIN_HZ = 30.0
MAX_HZ = 16000.0

# Attack/release smoothing factors for displayed band energies (0..1 per frame).
SMOOTH_ATTACK = 0.6
SMOOTH_RELEASE = 0.15

# User smoothing control: 0 = snappy/raw, 1 = very smooth. The level maps onto
# attack/release coefficients (higher level -> slower release -> smoother).
SMOOTHING_DEFAULT = 0.5
SMOOTHING_STEP = 0.1
# Endpoints the 0..1 smoothing level interpolates between (see App._smoothing_to_coeffs).
SMOOTHING_ATTACK_AT_0 = 0.85  # snappy: fast attack at level 0
SMOOTHING_ATTACK_AT_1 = 0.35  # smooth: slower attack at level 1
SMOOTHING_RELEASE_AT_0 = 0.35
SMOOTHING_RELEASE_AT_1 = 0.04  # very slow release -> calm decay at level 1

# Sensitivity multiplies band energies before display (clamped to 0..1 after).
SENSITIVITY_MIN = 0.25
SENSITIVITY_MAX = 4.0
SENSITIVITY_STEP = 0.25

# --- Visual theme tunables (shared across modes, adjustable at runtime) --------
# Global multiplier on particle/flake sizes.
SIZE_SCALE_DEFAULT = 1.0
SIZE_SCALE_MIN = 0.3
SIZE_SCALE_MAX = 3.0
SIZE_SCALE_STEP = 0.25

# Global multiplier on animation speed (fall/wind/rotation/particle motion).
SPEED_SCALE_DEFAULT = 1.0
SPEED_SCALE_MIN = 0.25
SPEED_SCALE_MAX = 3.0
SPEED_SCALE_STEP = 0.25

# Color schemes selectable at runtime:
#   classic       -> PALETTE (each mode's own palette)
#   rainbow       -> hue by position (static)
#   rainbow_plus  -> hue by position + a time offset, so colors cycle over time
#   <theme>       -> a fixed curated palette (sunset/ocean/... in THEME_PALETTES)
#   solid         -> one flat user-picked color (the Custom hue)
#   mono          -> a light->dark ramp of the user-picked hue
COLOR_SCHEMES: tuple[str, ...] = (
    "classic",
    "rainbow",
    "rainbow_plus",
    "sunset",
    "ocean",
    "forest",
    "fire",
    "ice",
    "candy",
    "grayscale",
    "solid",
    "mono",
)
COLOR_SCHEME_DEFAULT = "classic"
# Human-friendly labels for the color dropdown.
COLOR_SCHEME_LABELS: dict[str, str] = {
    "classic": "Classic",
    "rainbow": "Rainbow",
    "rainbow_plus": "Rainbow+",
    "sunset": "Sunset",
    "ocean": "Ocean",
    "forest": "Forest",
    "fire": "Fire",
    "ice": "Ice",
    "candy": "Candy",
    "grayscale": "Grayscale",
    "solid": "Solid (pick)",
    "mono": "Mono (pick)",
}
# Curated fixed palettes (low->high position) for the preset "theme" color schemes.
THEME_PALETTES: dict[str, tuple[tuple[int, int, int], ...]] = {
    "sunset": ((60, 20, 90), (200, 60, 120), (255, 110, 90), (255, 170, 70), (255, 230, 130)),
    "ocean": ((8, 30, 80), (20, 90, 170), (30, 160, 210), (90, 220, 220), (200, 250, 245)),
    "forest": ((15, 50, 30), (40, 110, 50), (110, 170, 60), (190, 215, 90), (240, 245, 170)),
    "fire": ((30, 0, 0), (120, 15, 10), (220, 60, 20), (255, 140, 30), (255, 230, 120)),
    "ice": ((10, 35, 80), (40, 110, 180), (110, 185, 230), (190, 230, 250), (245, 250, 255)),
    "candy": ((255, 120, 200), (200, 120, 255), (130, 170, 255), (120, 245, 215), (255, 245, 160)),
    "grayscale": ((30, 30, 34), (90, 92, 100), (150, 152, 160), (205, 207, 214), (255, 255, 255)),
}
# Color schemes that use the user-picked Custom hue (vs a fixed palette or rainbow).
COLOR_PICK_SCHEMES: frozenset[str] = frozenset({"solid", "mono"})
# The user's picked hue (0..1 around the wheel) for the Solid/Mono schemes. Saturation
# is held high so the picked color stays vivid; Mono ramps brightness across position.
COLOR_HUE_DEFAULT = 0.55
COLOR_PICK_SATURATION = 0.85
# How fast rainbow_plus sweeps the hue wheel (cycles per second).
COLOR_CYCLE_RATE = 0.15

# --- Global background layer (drawn behind every visual mode) -----------------
# A process-wide backdrop the user picks in the Background panel. "black" is the
# plain default; the others render *behind* the active mode (modes never clear the
# canvas, so the backdrop shows through wherever the mode doesn't paint).
BG_MODES: tuple[str, ...] = (
    "black",
    "spectrum",
    "filaments",
    "mirror",
    "ribbon",
    "gradient",
    "aurora",
    "starfield",
    "vignette",
)
BG_MODE_DEFAULT = "black"
BG_MODE_LABELS: dict[str, str] = {
    "black": "Black",
    "spectrum": "Spectrum line",
    "filaments": "Filaments (hair)",
    "mirror": "Spectrum mirror",
    "ribbon": "Waveform ribbon",
    "gradient": "Gradient",
    "aurora": "Aurora",
    "starfield": "Starfield",
    "vignette": "Beat vignette",
}
# Spectrum-family height presets -> max bar/band height as a fraction of canvas height.
BG_HEIGHTS: tuple[str, ...] = ("low", "medium", "high", "tall")
BG_HEIGHT_DEFAULT = "medium"
BG_HEIGHT_LABELS: dict[str, str] = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "tall": "Tall",
}
BG_HEIGHT_FRACTIONS: dict[str, float] = {
    "low": 0.08,
    "medium": 0.16,
    "high": 0.26,
    "tall": 0.40,
}
# Per-backdrop reactivity gain and overall opacity, both cycled in the Background
# panel so the layer can be tuned from a quiet hint to a loud wall.
BG_SENSITIVITY_CHOICES: tuple[float, ...] = (0.5, 0.75, 1.0, 1.5, 2.0, 3.0)
BG_SENSITIVITY_DEFAULT = 1.0
BG_OPACITY_CHOICES: tuple[float, ...] = (0.25, 0.5, 0.75, 1.0)
BG_OPACITY_DEFAULT = 1.0
# Beat/onset pulse envelope decay (per second) shared by vignette + aurora kicks.
BG_PULSE_DECAY = 5.0

# Magenta->cyan palette the spectrum/gradient/aurora sample across (low->high x).
BG_PALETTE: tuple[tuple[int, int, int], ...] = (
    (255, 70, 200),
    (180, 90, 255),
    (90, 150, 255),
    (90, 220, 255),
)
# Spectrum look: target on-screen bar pitch (px) and base opacity, plus attack/
# release smoothing for a calm line and a faint resting baseline when idle.
BG_SPECTRUM_BAR_PITCH = 6
BG_SPECTRUM_ALPHA = 200
BG_SPECTRUM_ATTACK = 0.5
BG_SPECTRUM_RELEASE = 0.12
BG_SPECTRUM_IDLE_FRACTION = 0.04
# Filaments: hair-thin (1px) rainbow lines at a tight pitch; brighter than spectrum.
BG_FILAMENT_PITCH = 3
BG_FILAMENT_ALPHA = 230
BG_FILAMENT_HUE_SPREAD = 1.5  # rainbow wheel turns across the canvas width
# Waveform ribbon: scrolling oscilloscope band along the bottom edge.
BG_RIBBON_SCROLL_PX = 3
BG_RIBBON_ALPHA = 190
# Gradient backdrop: bottom tint the canvas fades toward.
BG_GRADIENT_BOTTOM = (26, 18, 44)
# Aurora backdrop: drifting soft blobs; beats push them off-path + swell their size.
BG_AURORA_BLOBS = 4
BG_AURORA_ALPHA = 64
BG_AURORA_DRIFT = 0.05
BG_AURORA_PULSE_PUSH = 80  # px a beat shoves a blob outward before it springs back
BG_AURORA_SIZE_GAIN = 0.6  # how much loudness swells the blob radius
# Starfield: one star per this many px^2; slow drift + treble/onset twinkle.
BG_STARFIELD_AREA_PER_STAR = 7000
BG_STARFIELD_DRIFT = 10.0  # px/s base drift
BG_STARFIELD_BASE_ALPHA = 120
# Beat vignette: resting edge glow + how much a beat brightens the edges.
BG_VIGNETTE_BASE_ALPHA = 40
BG_VIGNETTE_PULSE_ALPHA = 170

# Onset (beat) detection: spectral flux is normalized to 0..1 via this gain;
# a frame is treated as an onset when its strength clears the threshold.
ONSET_FLUX_GAIN = 6.0
ONSET_THRESHOLD = 0.35

# Below this RMS we consider the signal "silent" (idle state).
IDLE_RMS_THRESHOLD = 1e-3

# --- Shared visual rendering constants (used across several modes) ------------
# Onset bursts are divided by this when reduce-motion is on (calmer, fewer sparks).
REDUCE_MOTION_BURST_DIVISOR = 3
# Hue used for the idle (silent) line/ring under rainbow color schemes.
IDLE_LINE_HUE = 0.5
# Minimum brightness multiplier for a live particle (so sparks never go fully dark).
PARTICLE_BRIGHTNESS_FLOOR = 0.4
# Show the "No audio detected" banner only after the signal has been silent this
# long (seconds). Brief gaps between tracks shouldn't flash the banner; the app
# never auto-quits on silence — the user quits when they want.
IDLE_BANNER_DELAY = 5.0

# --- Circular waveform modes --------------------------------------------------
# Base radius of the oscilloscope circle as a fraction of half the min side.
CIRCLE_BASE_RADIUS = 0.32
# How strongly waveform samples push the ring in/out (fraction of min side).
CIRCLE_WAVE_AMPLITUDE = 0.18
# Multi-ring layout (fractions of half the min side): innermost ring radius and the
# outer bound that the rings are spread across before the Spacing option is applied.
CIRCLE_INNER_FRACTION = 0.12
CIRCLE_OUTER_FRACTION = 0.82
# Per-ring wobble = (this base + ring energy) * the shared wave amplitude * this factor.
CIRCLE_RING_AMP_BASE = 0.4
CIRCLE_RING_AMP_FACTOR = 0.6

# --- Particles ----------------------------------------------------------------
PARTICLE_MAX = 600
PARTICLE_MAX_REDUCED = 120  # cap when reduce-motion is on
PARTICLE_BURST = 24  # particles spawned per detected onset
PARTICLE_LIFETIME = 1.6  # seconds

# --- Spark field (shared free-particle system: lightshow / laser) -------------
# Free particles "shot out" / "emitted" by beam modes, with optional fading trails.
SPARK_MAX = 500
SPARK_MAX_REDUCED = 100  # cap when reduce-motion is on
SPARK_LIFETIME = 1.1  # seconds
SPARK_TRAIL_LEN = 6  # recent positions kept for the fading "shadow" trail

# --- Spiral particles ---------------------------------------------------------
SPIRAL_MAX = 700
SPIRAL_MAX_REDUCED = 140
SPIRAL_BURST = 18  # particles per spawn step (scaled by energy)
SPIRAL_LIFETIME = 2.2

# --- Snowfall -----------------------------------------------------------------
SNOW_FLAKES = 220  # flake pool size (normalized-space, resolution-independent)
SNOW_FLAKES_REDUCED = 120
SNOW_WIND_SCALE = 0.9  # bass energy -> horizontal drift
SNOW_WIND_SCALE_REDUCED = 0.25
SNOW_SIZE_SCALE = 2.5  # mid-band energy -> flake radius growth

# --- RenK logo overlay (global; drawn over every visual mode) -----------------
# The logo is a transparent PNG bundled under the package's ``assets/`` dir.
LOGO_FILENAME = "renk_logo.png"
# Square app/window icon (RenK emblem on a rounded badge) for the title bar/taskbar.
APP_ICON_FILENAME = "renk_icon.png"
# Whether the logo is shown by default (user can toggle it on/off in any mode).
LOGO_ENABLED_DEFAULT = True
# Slow "circling" spin, in degrees/second at speed_scale 1.0 (honors the speed control).
LOGO_SPIN_DEG_PER_SEC = 18.0
# Audio-reactive extra spin: bass energy adds up to this many deg/sec on top.
LOGO_SPIN_ENERGY_GAIN = 36.0
# Subtle "breathing" pulse: the logo scales by ±this fraction with overall energy.
LOGO_PULSE_AMOUNT = 0.06

# Discrete size presets -> logo height as a fraction of the canvas's min side.
# "micro" is intentionally smaller than "tiny" for a subtle corner watermark.
LOGO_SIZES: tuple[str, ...] = ("micro", "tiny", "small", "medium", "large", "xlarge", "huge")
LOGO_SIZE_DEFAULT = "medium"
LOGO_SIZE_LABELS: dict[str, str] = {
    "micro": "Micro",
    "tiny": "Tiny",
    "small": "Small",
    "medium": "Medium",
    "large": "Large",
    "xlarge": "X-Large",
    "huge": "Huge",
}
LOGO_SIZE_FRACTIONS: dict[str, float] = {
    "micro": 0.07,
    "tiny": 0.15,
    "small": 0.25,
    "medium": 0.40,
    "large": 0.55,
    "xlarge": 0.72,
    "huge": 0.90,
}

# Spin direction for the logo's slow circling rotation.
LOGO_SPIN_DIRS: tuple[str, ...] = ("cw", "ccw")
LOGO_SPIN_DIR_DEFAULT = "cw"
LOGO_SPIN_DIR_LABELS: dict[str, str] = {"cw": "Clockwise", "ccw": "Counter-CW"}

# Discrete on-screen anchors. Center is the default; the rest are the four corners.
LOGO_POSITIONS: tuple[str, ...] = (
    "center",
    "top_left",
    "top_right",
    "bottom_left",
    "bottom_right",
)
LOGO_POSITION_DEFAULT = "center"
LOGO_POSITION_LABELS: dict[str, str] = {
    "center": "Center",
    "top_left": "Top-Left",
    "top_right": "Top-Right",
    "bottom_left": "Bottom-Left",
    "bottom_right": "Bottom-Right",
}
# Inset of a corner-anchored logo from the canvas edge (fraction of min side).
LOGO_CORNER_MARGIN = 0.03

# Opacity presets (0..1 alpha multiplier) so the logo can sit quietly behind visuals.
LOGO_OPACITIES: tuple[float, ...] = (0.25, 0.5, 0.75, 1.0)
LOGO_OPACITY_DEFAULT = 0.75

# Color modes: "default" keeps the baked rainbow picture; "rainbow_plus" paints a
# swirling multi-color rainbow over a luminance copy (hue varies by angle + radius and
# cycles over time), so the glow shows many colors at once instead of one flat hue.
LOGO_COLOR_MODES: tuple[str, ...] = ("default", "rainbow_plus")
LOGO_COLOR_DEFAULT = "default"
LOGO_COLOR_LABELS: dict[str, str] = {"default": "Default", "rainbow_plus": "Rainbow+"}
# Rainbow+ swirl: how many extra hue turns are added across the radius (more = more
# colors at once / a tighter spiral). Hue = angle + radius * this, then + time phase.
LOGO_RAINBOW_SWIRL = 1.5

# Optional particle emission from the logo ring (reuses the shared SparkField).
LOGO_EMIT_DEFAULT = False
LOGO_EMIT_PER_ONSET = 10  # sparks released on a detected beat
LOGO_EMIT_SPEED = 0.18  # outward spark speed in normalized units/sec

# Extra logo effects, each an independent on/off (all can run at once alongside Emit):
#   shockwave -> an expanding translucent ring fires outward on a beat
#   glow      -> the logo brightness swells on a beat and decays back
#   throb     -> a continuous size "breathing" beyond the subtle baseline pulse
LOGO_SHOCKWAVE_DEFAULT = False
LOGO_GLOW_DEFAULT = False
LOGO_THROB_DEFAULT = False
# Shockwave ring: expansion speed (fraction of min-side per second), how many can be
# alive at once, and the onset strength needed to spawn one.
LOGO_SHOCKWAVE_SPEED = 0.9
LOGO_SHOCKWAVE_MAX = 4
LOGO_SHOCKWAVE_ONSET_MIN = 0.25
# Glow: extra brightness multiplier added at a full beat, decaying per second.
LOGO_GLOW_GAIN = 0.8
LOGO_GLOW_DECAY = 3.0
# Throb: continuous breathing amplitude (added on top of LOGO_PULSE_AMOUNT) and rate.
LOGO_THROB_AMOUNT = 0.10
LOGO_THROB_RATE = 2.2

# --- Settings persistence -----------------------------------------------------
SETTINGS_FILENAME = "settings.json"
# v2 added the RenK logo overlay preferences (logo_*). v3 added UI appearance
# (ui_style, ui_font). v4 added the accent color + global background layer
# (ui_accent, bg_mode, bg_height). v5 added per-backdrop reactivity + opacity
# (bg_sensitivity, bg_opacity). v6 added logo_spin. v7 (Phase 10.07) merged several
# modes, so a saved `mode` key is remapped to its canonical survivor on load.
# v8 (Phase 0B-a) added the selectable capture source (source_id).
# v9 (Phase 0B-b) added the last-active user look id (active_look).
# v10 (Phase 0B-c) added the auto-cycle pool + interval (random_pool, random_interval).
# v11 (Phase 0B-c) added the shuffle "randomize options" toggle (random_options).
# v12 (Phase 0B-c) added the user-adjustable cross-fade time (random_fade).
SETTINGS_SCHEMA_VERSION = 17

# --- User looks ("My Looks") persistence (Phase 0B-b) -------------------------
# Saved user looks live in their own file (sibling to settings.json) so a bad
# look can never corrupt core settings. The file carries its own schema_version.
LOOKS_FILENAME = "looks.json"
# Default filename when the user exports their whole My Looks library to a file
# next to the application (portable backup / share); see looks.export_library.
LOOKS_EXPORT_FILENAME = "AudioVisualizer-looks.json"
LOOKS_SCHEMA_VERSION = 1
LOOKS_MAX = 100  # guard rail: cap how many looks we keep/show
LOOK_NAME_MAX = 60  # guard rail: trim look names to this length

# Phase 10.07 mode merges: old mode keys -> the canonical mode that absorbed them.
# Per-mode option indices were never persisted, so only the active key is remapped.
MERGED_MODE_KEYS: dict[str, str] = {
    "waveform_2": "waveform",
    "waveform_circle_2": "waveform_circle",
    "waveform_circle_multiple": "waveform_circle",
    "waveform_circle_multiple_2": "waveform_circle",
    "lightshow_2": "lightshow",
    "laser_2": "laser",
    "particles_spiral": "particles",
}

# --- Auto-cycle / shuffle (Phase 0B-c) ----------------------------------------
# An optional "shuffle" that auto-switches the active visual every interval
# seconds, cross-fading rather than hard-cutting. The rotation pool holds both
# built-in modes ("mode:<key>") and saved looks ("look:<id>"). A switch freezes
# the canvas and applies the next item live, then dissolves the frozen scene out
# (see visuals/_transition.py), so it works uniformly for modes and full looks.
RANDOM_INTERVAL_DEFAULT = 20.0  # seconds between auto-switches
RANDOM_INTERVAL_MIN = 3.0
RANDOM_INTERVAL_MAX = 300.0
RANDOM_INTERVAL_STEP = 5.0
# Cross-fade length when auto-switching, user-adjustable in the Shuffle modal and
# persisted as ``random_fade``. A mode->mode switch renders **both** visuals live
# while the fade is in flight (the outgoing one keeps animating); a switch onto a
# saved look uses a frozen-snapshot dissolve (it also changes background/logo/theme).
# Reduce-motion (or a 0s fade) hard-cuts with no double-render.
TRANSITION_DURATION = 0.6  # default fade seconds (RANDOM_FADE_DEFAULT)
RANDOM_FADE_DEFAULT = TRANSITION_DURATION
RANDOM_FADE_MIN = 0.0  # 0 = instant hard cut
RANDOM_FADE_MAX = 3.0
RANDOM_FADE_STEP = 0.1

# Session look history (the Prev/Next back-forward queue). Each entry is a small
# in-memory Look snapshot, never persisted, so the cap is generous and costs
# nothing per frame (we only apply one on demand). Oldest entries roll off.
HISTORY_MAX = 200

# --- Beat Buttons (music-driven auto-triggers, Phase 0B-c) --------------------
# Music onsets can "press" actions for you. Each action carries its own
# sensitivity level; the engine fires when an onset spikes above a running
# baseline (so it adapts to how loud/busy the track is) AND a per-level cooldown
# has elapsed, so triggers are sensibly spaced (never a machine-gun, never once
# an age). Silence emits nothing (the baseline decays and the floor gate blocks).
# Sensitivity ladder from "rarely fires, well spaced" up to "fires on almost any
# energy". Higher = lower threshold ratio + floor + shorter cooldown. The very top
# levels drop the ratio toward (and below) 1.0 so they still trigger on compressed /
# steady music that never really "spikes" — at the cost of firing more often.
BEAT_SENSITIVITY_LABELS = (
    "Off",
    "Min",
    "Low",
    "Med",
    "High",
    "Fast",
    "Rapid",
    "Max",
    "Wild",
    "Insane",
)
# Per level (indexes 1..9): (signal:baseline ratio to fire, absolute energy floor,
# minimum seconds between fires). Index 0 (Off) is ``None``. Cooldown keeps it sane:
# Min ~8s (only big hits) ... Insane ~0.18s and ratio < 1 (fires on almost anything).
BEAT_SENSITIVITY_PARAMS: tuple[tuple[float, float, float] | None, ...] = (
    None,  # Off
    (2.6, 0.14, 8.0),  # Min  - only strong hits, far apart
    (2.2, 0.11, 4.0),  # Low
    (1.8, 0.09, 2.2),  # Med
    (1.5, 0.07, 1.2),  # High
    (1.3, 0.05, 0.7),  # Fast
    (1.18, 0.04, 0.4),  # Rapid
    (1.08, 0.03, 0.28),  # Max
    (1.0, 0.02, 0.22),  # Wild   - fires whenever energy beats its own average
    (0.92, 0.015, 0.18),  # Insane - fires on almost any sustained energy (<= ~5/s)
)
# Frequency band each action listens to (in table order: key, label). The engine
# watches that band's energy for the spike that fires the action.
BEAT_BANDS: tuple[tuple[str, str], ...] = (
    ("all", "All"),
    ("bass", "Bass"),
    ("mid", "Mid"),
    ("high", "High"),
)
BEAT_BAND_DEFAULT = "all"
# Actions the beat engine can trigger, in table order: (key, label).
BEAT_ACTIONS: tuple[tuple[str, str], ...] = (
    ("randomize", "Rnd  \u2014 randomize current mode"),
    ("next", "Next \u2014 shuffle to next item"),
)
# Time constant (seconds) the per-band baseline tracks toward live energy. Short
# enough that beats stand out, long enough not to chase every transient.
BEAT_BASELINE_TAU = 0.5
# How fast the indicator's trigger "flash" fades (seconds).
BEAT_FLASH_TAU = 0.28
# Beat "Fade": the cross-fade transition duration (seconds) used when a beat fires a
# look change (Rnd / Next) — same idea as the Shuffle fade, picked from a dropdown.
# (key, label, seconds). "cut" = 0 = an instant hard cut, no fade.
BEAT_FADE_CHOICES: tuple[tuple[str, str, float], ...] = (
    ("cut", "Cut", 0.0),
    ("short", "0.3 s", 0.3),
    ("medium", "0.6 s", 0.6),
    ("long", "1.0 s", 1.0),
    ("xlong", "1.5 s", 1.5),
    ("vlong", "2.5 s", 2.5),
)
BEAT_FADE_DEFAULT = "medium"
# On-screen indicator shapes. All draw with transparency and a soft expanding halo
# on a fire; "burst" / "star" add extra spokes. (key, label).
BEAT_INDICATOR_SHAPES: tuple[tuple[str, str], ...] = (
    ("dot", "Dot"),
    ("ring", "Ring"),
    ("pulse", "Pulse"),
    ("diamond", "Diamond"),
    ("star", "Star"),
    ("burst", "Burst"),
)
BEAT_INDICATOR_SHAPE_DEFAULT = "dot"
# How see-through the indicator is over the visual behind it: (key, label, 0..1 alpha
# multiplier applied to the whole indicator). 100% = fully drawn (current look).
BEAT_INDICATOR_OPACITY_CHOICES: tuple[tuple[str, str, float], ...] = (
    ("25", "25%", 0.25),
    ("50", "50%", 0.5),
    ("75", "75%", 0.75),
    ("100", "100%", 1.0),
)
BEAT_INDICATOR_OPACITY_DEFAULT = "100"
# On-screen beat indicator: a small pulsing dot whose hue tracks the listened band
# and whose brightness tracks how close the beat is to firing. (key, label).
BEAT_INDICATOR_POSITIONS: tuple[tuple[str, str], ...] = (
    ("top-right", "Top-right"),
    ("top-left", "Top-left"),
    ("bottom-right", "Bottom-right"),
    ("bottom-left", "Bottom-left"),
    ("center", "Center"),
)
BEAT_INDICATOR_POSITION_DEFAULT = "top-right"
BEAT_INDICATOR_ENABLED_DEFAULT = False

# --- Sensitivity frequency focus ----------------------------------------------
# The global Sensitivity gain can target one frequency band instead of the whole
# spectrum, so e.g. only the bass drives the visuals harder. (key, label).
SENS_BANDS: tuple[tuple[str, str], ...] = (
    ("all", "All"),
    ("bass", "Bass"),
    ("mid", "Mid"),
    ("high", "High"),
)
SENS_BAND_DEFAULT = "all"

# --- Device-change recovery ---------------------------------------------------
DEVICE_RECOVER_INTERVAL = 2.0  # seconds between auto-reopen attempts after error

# --- Self-test ----------------------------------------------------------------
SELFTEST_FRAMES = 60
