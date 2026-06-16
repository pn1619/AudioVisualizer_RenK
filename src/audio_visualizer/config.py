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
APP_VERSION = "00.09.00"
# Shown in the About dialog. BUILD_DATE is bumped when a build is cut.
APP_OWNER = "pn1619"
APP_BUILD_DATE = "2026-06-16"

# --- Window / rendering -------------------------------------------------------
DEFAULT_WINDOW_SIZE: tuple[int, int] = (1280, 720)
MIN_WINDOW_SIZE: tuple[int, int] = (640, 360)
TARGET_FPS = 60
# Two stacked rows: global controls (top) + color/per-mode options (bottom).
CONTROL_BAR_HEIGHT = 88

# --- Colors (RGB) -------------------------------------------------------------
COLOR_BG = (10, 10, 18)
COLOR_PANEL = (22, 22, 34)
COLOR_PANEL_HOVER = (38, 38, 56)
COLOR_TEXT = (224, 224, 236)
COLOR_TEXT_DIM = (140, 140, 160)
COLOR_ACCENT = (90, 200, 255)
COLOR_WARN = (240, 180, 80)
COLOR_ERROR = (240, 90, 90)

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
HOP = 1024
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
# Multi-ring mode: how many concentric rings the user may stack.
CIRCLE_RINGS_MAX = 10
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

# --- Spark field (shared free-particle system: lightshow_2 / laser_2) ---------
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
# Whether the logo is shown by default (user can toggle it on/off in any mode).
LOGO_ENABLED_DEFAULT = True
# Slow "circling" spin, in degrees/second at speed_scale 1.0 (honors the speed control).
LOGO_SPIN_DEG_PER_SEC = 18.0
# Audio-reactive extra spin: bass energy adds up to this many deg/sec on top.
LOGO_SPIN_ENERGY_GAIN = 36.0
# Subtle "breathing" pulse: the logo scales by ±this fraction with overall energy.
LOGO_PULSE_AMOUNT = 0.06

# Discrete size presets -> diameter as a fraction of the canvas's min side.
LOGO_SIZES: tuple[str, ...] = ("small", "medium", "large")
LOGO_SIZE_DEFAULT = "medium"
LOGO_SIZE_LABELS: dict[str, str] = {"small": "Small", "medium": "Medium", "large": "Large"}
LOGO_SIZE_FRACTIONS: dict[str, float] = {"small": 0.22, "medium": 0.40, "large": 0.62}

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

# Color modes: "default" keeps the baked rainbow picture; "rainbow_plus" cycles the
# hue over time using a luminance copy of the image (so the glass-tube shape matches).
LOGO_COLOR_MODES: tuple[str, ...] = ("default", "rainbow_plus")
LOGO_COLOR_DEFAULT = "default"
LOGO_COLOR_LABELS: dict[str, str] = {"default": "Default", "rainbow_plus": "Rainbow+"}

# Optional particle emission from the logo ring (reuses the shared SparkField).
LOGO_EMIT_DEFAULT = False
LOGO_EMIT_PER_ONSET = 10  # sparks released on a detected beat
LOGO_EMIT_SPEED = 0.18  # outward spark speed in normalized units/sec

# --- Settings persistence -----------------------------------------------------
SETTINGS_FILENAME = "settings.json"
# v2 added the RenK logo overlay preferences (logo_*). Older files migrate by
# defaulting the new keys.
SETTINGS_SCHEMA_VERSION = 2

# --- Device-change recovery ---------------------------------------------------
DEVICE_RECOVER_INTERVAL = 2.0  # seconds between auto-reopen attempts after error

# --- Self-test ----------------------------------------------------------------
SELFTEST_FRAMES = 60
