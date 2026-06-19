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
# FF is the development phase; from phase 10 it is written in hex ("0A", "0B", …)
# so it stays two digits. The build spec parses each PP.FF.BB part base-16.
APP_VERSION = "00.0B.05"
# Shown in the About dialog. BUILD_DATE is bumped when a build is cut.
APP_OWNER = "pn1619"
APP_BUILD_DATE = "2026-06-18"

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
#   classic       -> PALETTE
#   rainbow       -> hue by position (static)
#   rainbow_plus  -> hue by position + a time offset, so colors cycle over time
COLOR_SCHEMES: tuple[str, ...] = ("classic", "rainbow", "rainbow_plus")
COLOR_SCHEME_DEFAULT = "classic"
# Human-friendly labels for the color dropdown.
COLOR_SCHEME_LABELS: dict[str, str] = {
    "classic": "Classic",
    "rainbow": "Rainbow",
    "rainbow_plus": "Rainbow+",
}
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
SETTINGS_SCHEMA_VERSION = 11

# --- User looks ("My Looks") persistence (Phase 0B-b) -------------------------
# Saved user looks live in their own file (sibling to settings.json) so a bad
# look can never corrupt core settings. The file carries its own schema_version.
LOOKS_FILENAME = "looks.json"
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
# Cross-fade length when auto-switching. Two modes are rendered to offscreen
# surfaces only while a fade is in flight, so steady-state cost is unchanged.
# Reduce-motion shortens this to a hard cut (no double-render).
TRANSITION_DURATION = 0.6

# --- Device-change recovery ---------------------------------------------------
DEVICE_RECOVER_INTERVAL = 2.0  # seconds between auto-reopen attempts after error

# --- Self-test ----------------------------------------------------------------
SELFTEST_FRAMES = 60
