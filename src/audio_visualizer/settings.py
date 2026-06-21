"""User settings persisted as JSON in ``%APPDATA%\\AudioVisualizer``.

Loading never crashes: an unknown ``schema_version`` or a corrupt/missing file
falls back to defaults (migrating known older versions where possible). Saving
is best-effort and logs on failure rather than raising.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from audio_visualizer.config import (
    BEAT_ACTIONS,
    BEAT_BANDS,
    BEAT_ENABLED_DEFAULT,
    BEAT_FADE_CHOICES,
    BEAT_FADE_DEFAULT,
    BEAT_INDICATOR_ENABLED_DEFAULT,
    BEAT_INDICATOR_OPACITY_CHOICES,
    BEAT_INDICATOR_OPACITY_DEFAULT,
    BEAT_INDICATOR_POSITION_DEFAULT,
    BEAT_INDICATOR_POSITIONS,
    BEAT_INDICATOR_SHAPE_DEFAULT,
    BEAT_INDICATOR_SHAPES,
    BEAT_SENSITIVITY_LABELS,
    BG_HEIGHT_DEFAULT,
    BG_HEIGHTS,
    BG_MODE_DEFAULT,
    BG_MODES,
    BG_OPACITY_CHOICES,
    BG_OPACITY_DEFAULT,
    BG_SENSITIVITY_CHOICES,
    BG_SENSITIVITY_DEFAULT,
    COLOR_HUE2_DEFAULT,
    COLOR_HUE_DEFAULT,
    COLOR_SCHEME_DEFAULT,
    COLOR_SCHEMES,
    CURSOR_EFFECT_DEFAULT,
    CURSOR_EFFECTS,
    CURSOR_LEGACY_MODE_MAP,
    CURSOR_SHAPE_DEFAULT,
    CURSOR_SHAPES,
    DEFAULT_WINDOW_SIZE,
    FG_COLOR_CHOICES,
    FG_COLOR_DEFAULT,
    FG_DIRECTION_DEFAULT,
    FG_DIRECTIONS,
    FG_FLASH_CHOICES,
    FG_FLASH_DEFAULT,
    FG_INTENSITY_CHOICES,
    FG_INTENSITY_DEFAULT,
    FG_MODE_DEFAULT,
    FG_MODES,
    FG_OPACITY_CHOICES,
    FG_OPACITY_DEFAULT,
    FG_REACTIVITY_CHOICES,
    FG_REACTIVITY_DEFAULT,
    FG_WIND_CHOICES,
    FG_WIND_DEFAULT,
    LOGO_COLOR_DEFAULT,
    LOGO_COLOR_MODES,
    LOGO_EMIT_DEFAULT,
    LOGO_ENABLED_DEFAULT,
    LOGO_GLOW_DEFAULT,
    LOGO_OPACITIES,
    LOGO_OPACITY_DEFAULT,
    LOGO_POSITION_DEFAULT,
    LOGO_POSITIONS,
    LOGO_SHOCKWAVE_DEFAULT,
    LOGO_SIZE_DEFAULT,
    LOGO_SIZES,
    LOGO_SPIN_DIR_DEFAULT,
    LOGO_SPIN_DIRS,
    LOGO_THROB_DEFAULT,
    MERGED_MODE_KEYS,
    RANDOM_FADE_DEFAULT,
    RANDOM_FADE_MAX,
    RANDOM_FADE_MIN,
    RANDOM_INTERVAL_DEFAULT,
    RANDOM_INTERVAL_MAX,
    RANDOM_INTERVAL_MIN,
    SENS_BAND_DEFAULT,
    SENS_BANDS,
    SETTINGS_FILENAME,
    SETTINGS_SCHEMA_VERSION,
    SIZE_SCALE_DEFAULT,
    SMOOTHING_DEFAULT,
    SPEED_SCALE_DEFAULT,
    UI_ACCENT_DEFAULT,
    UI_ACCENTS,
    UI_FONT_DEFAULT,
    UI_FONTS,
    UI_STYLE_DEFAULT,
    UI_STYLES,
)
from audio_visualizer.platform_win import get_appdata_dir

logger = logging.getLogger(__name__)


@dataclass
class Settings:
    """Persisted user preferences restored on the next launch."""

    schema_version: int = SETTINGS_SCHEMA_VERSION
    mode: str = ""  # active visual-mode key ("" -> app default)
    sensitivity: float = 1.0
    # Which frequency band the Sensitivity gain targets (schema v15). "all" scales the
    # whole spectrum (legacy behavior); bass/mid/high scale only that third.
    sens_band: str = SENS_BAND_DEFAULT
    smoothing: float = SMOOTHING_DEFAULT
    reduce_motion: bool = False
    fullscreen: bool = False
    window_size: tuple[int, int] = field(default_factory=lambda: DEFAULT_WINDOW_SIZE)
    notice_acknowledged: bool = False
    size_scale: float = SIZE_SCALE_DEFAULT
    speed_scale: float = SPEED_SCALE_DEFAULT
    color_scheme: str = COLOR_SCHEME_DEFAULT
    # RenK logo overlay (Phase 9 / schema v2).
    logo_enabled: bool = LOGO_ENABLED_DEFAULT
    logo_size: str = LOGO_SIZE_DEFAULT
    logo_position: str = LOGO_POSITION_DEFAULT
    logo_opacity: float = LOGO_OPACITY_DEFAULT
    logo_color: str = LOGO_COLOR_DEFAULT
    logo_emit: bool = LOGO_EMIT_DEFAULT
    # Extra logo effects, each independent (schema v16): expanding shockwave ring on a
    # beat, a brightness glow kick, and a continuous size throb.
    logo_shockwave: bool = LOGO_SHOCKWAVE_DEFAULT
    logo_glow: bool = LOGO_GLOW_DEFAULT
    logo_throb: bool = LOGO_THROB_DEFAULT
    # Logo spin direction (Phase 10.03 / schema v6).
    logo_spin: str = LOGO_SPIN_DIR_DEFAULT
    # UI appearance (Phase 9.03 / schema v3).
    ui_style: str = UI_STYLE_DEFAULT
    ui_font: str = UI_FONT_DEFAULT
    # Accent color + global background layer (Phase 10 / schema v4).
    ui_accent: str = UI_ACCENT_DEFAULT
    # Custom in-app mouse cursor (schema v20): an independent shape + reactive
    # effect. "system"/"none" keep the plain OS arrow. (Replaces v19 cursor_mode.)
    cursor_shape: str = CURSOR_SHAPE_DEFAULT
    cursor_effect: str = CURSOR_EFFECT_DEFAULT
    bg_mode: str = BG_MODE_DEFAULT
    bg_height: str = BG_HEIGHT_DEFAULT
    # Per-backdrop reactivity + opacity (Phase 10.01 / schema v5).
    bg_sensitivity: float = BG_SENSITIVITY_DEFAULT
    bg_opacity: float = BG_OPACITY_DEFAULT
    # Global foreground overlay layer (schema v22; color + flash added in v23).
    fg_mode: str = FG_MODE_DEFAULT
    fg_intensity: float = FG_INTENSITY_DEFAULT
    fg_direction: str = FG_DIRECTION_DEFAULT
    fg_opacity: float = FG_OPACITY_DEFAULT
    fg_color: str = FG_COLOR_DEFAULT
    fg_flash: float = FG_FLASH_DEFAULT
    fg_reactivity: float = FG_REACTIVITY_DEFAULT
    fg_wind: float = FG_WIND_DEFAULT
    # Selectable capture source (Phase 0B-a / schema v8). "" -> default render
    # device loopback; otherwise a device *name* from audio.devices.
    source_id: str = ""
    # Last active user look (Phase 0B-b / schema v9). "" -> None/Live (no look).
    # Stores the look's stable *id* (not name) so a rename never breaks restore.
    active_look: str = ""
    # Auto-cycle / shuffle (Phase 0B-c / schema v10). The pool is a list of tagged
    # identifiers ("mode:<key>"; "look:<id>" is reserved for a later build); an
    # empty pool means no shuffle. Auto is never persisted on (off each launch).
    random_pool: list[str] = field(default_factory=list)
    random_interval: float = RANDOM_INTERVAL_DEFAULT
    # When on, shuffling to a built-in mode also randomizes that mode's own
    # options (e.g. Ripples' spawn origin). Background/Logo are never touched
    # by this. Saved looks keep their own captured options. (schema v11)
    random_options: bool = False
    # User-adjustable cross-fade length (seconds) for auto-cycle switches. (schema v12)
    random_fade: float = RANDOM_FADE_DEFAULT
    # Beat Buttons master switch (schema v18): when off the feature fires nothing,
    # regardless of each action's level (per-action settings below are preserved).
    beat_enabled: bool = BEAT_ENABLED_DEFAULT
    # Beat Buttons (schema v13): per-action music-trigger sensitivity index
    # (0 = Off ... Max), keyed by action ("randomize"/"next"). Default all Off.
    beat_levels: dict[str, int] = field(default_factory=dict)
    # Beat Buttons frequency band + on-screen indicator (schema v14). ``beat_bands``
    # maps each action to the band it listens to ("all"/"bass"/"mid"/"high").
    beat_bands: dict[str, str] = field(default_factory=dict)
    beat_indicator: bool = BEAT_INDICATOR_ENABLED_DEFAULT
    beat_indicator_pos: str = BEAT_INDICATOR_POSITION_DEFAULT
    # Beat indicator shape + transparency, the beat look-change cross-fade time, and the
    # Solid/Mono custom hue (schema v16).
    beat_indicator_shape: str = BEAT_INDICATOR_SHAPE_DEFAULT
    beat_indicator_opacity: str = BEAT_INDICATOR_OPACITY_DEFAULT
    beat_fade: str = BEAT_FADE_DEFAULT
    color_hue: float = COLOR_HUE_DEFAULT
    # Second Stereo-scheme hue (schema v21).
    color_hue2: float = COLOR_HUE2_DEFAULT

    def to_json(self) -> dict:
        """Serializable dict (tuples become JSON lists)."""
        data = asdict(self)
        data["window_size"] = list(self.window_size)
        return data


def settings_path() -> Path:
    """Full path to the settings file under the app-data directory."""
    return get_appdata_dir() / SETTINGS_FILENAME


def load(path: Path | None = None) -> Settings:
    """Load settings, falling back to defaults on any problem (never raises)."""
    path = path or settings_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Settings()
    except (OSError, ValueError):
        logger.warning("Settings file unreadable/corrupt; using defaults", exc_info=True)
        return Settings()

    if not isinstance(raw, dict):
        logger.warning("Settings file is not an object; using defaults")
        return Settings()

    return _from_dict(_migrate(raw))


def save(settings: Settings, path: Path | None = None) -> bool:
    """Write settings atomically. Returns True on success (never raises)."""
    path = path or settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(settings.to_json(), indent=2), encoding="utf-8")
        tmp.replace(path)
        return True
    except OSError:
        logger.warning("Could not save settings to %s", path, exc_info=True)
        return False


def _migrate(raw: dict) -> dict:
    """Bring an older/unknown payload toward the current schema (best effort).

    Unknown future versions are read leniently: known keys are still honored and
    missing ones default. There are no breaking older versions yet.
    """
    version = raw.get("schema_version")
    if version != SETTINGS_SCHEMA_VERSION:
        logger.info("Migrating settings from schema %r to %d", version, SETTINGS_SCHEMA_VERSION)
    # v19 -> v20: the single "cursor_mode" became a (shape, effect) pair.
    legacy = raw.get("cursor_mode")
    if isinstance(legacy, str) and "cursor_shape" not in raw:
        default = (CURSOR_SHAPE_DEFAULT, CURSOR_EFFECT_DEFAULT)
        shape, effect = CURSOR_LEGACY_MODE_MAP.get(legacy, default)
        raw["cursor_shape"] = shape
        raw["cursor_effect"] = effect
    return raw


def _from_dict(raw: dict) -> Settings:
    """Build Settings from a dict, type-checking each key and ignoring extras."""
    defaults = Settings()
    mode = _str(raw.get("mode"), defaults.mode)
    return Settings(
        schema_version=SETTINGS_SCHEMA_VERSION,
        mode=MERGED_MODE_KEYS.get(mode, mode),  # remap modes merged in Phase 10.07
        sensitivity=_float(raw.get("sensitivity"), defaults.sensitivity),
        sens_band=_choice(
            raw.get("sens_band"), tuple(key for key, _label in SENS_BANDS), defaults.sens_band
        ),
        smoothing=_float(raw.get("smoothing"), defaults.smoothing),
        reduce_motion=_bool(raw.get("reduce_motion"), defaults.reduce_motion),
        fullscreen=_bool(raw.get("fullscreen"), defaults.fullscreen),
        window_size=_size(raw.get("window_size"), defaults.window_size),
        notice_acknowledged=_bool(raw.get("notice_acknowledged"), defaults.notice_acknowledged),
        size_scale=_float(raw.get("size_scale"), defaults.size_scale),
        speed_scale=_float(raw.get("speed_scale"), defaults.speed_scale),
        color_scheme=_choice(raw.get("color_scheme"), COLOR_SCHEMES, defaults.color_scheme),
        logo_enabled=_bool(raw.get("logo_enabled"), defaults.logo_enabled),
        logo_size=_choice(raw.get("logo_size"), LOGO_SIZES, defaults.logo_size),
        logo_position=_choice(raw.get("logo_position"), LOGO_POSITIONS, defaults.logo_position),
        logo_opacity=_opacity(raw.get("logo_opacity"), defaults.logo_opacity),
        logo_color=_choice(raw.get("logo_color"), LOGO_COLOR_MODES, defaults.logo_color),
        logo_emit=_bool(raw.get("logo_emit"), defaults.logo_emit),
        logo_shockwave=_bool(raw.get("logo_shockwave"), defaults.logo_shockwave),
        logo_glow=_bool(raw.get("logo_glow"), defaults.logo_glow),
        logo_throb=_bool(raw.get("logo_throb"), defaults.logo_throb),
        logo_spin=_choice(raw.get("logo_spin"), LOGO_SPIN_DIRS, defaults.logo_spin),
        ui_style=_choice(raw.get("ui_style"), UI_STYLES, defaults.ui_style),
        ui_font=_choice(raw.get("ui_font"), UI_FONTS, defaults.ui_font),
        ui_accent=_choice(raw.get("ui_accent"), UI_ACCENTS, defaults.ui_accent),
        cursor_shape=_choice(raw.get("cursor_shape"), CURSOR_SHAPES, defaults.cursor_shape),
        cursor_effect=_choice(raw.get("cursor_effect"), CURSOR_EFFECTS, defaults.cursor_effect),
        bg_mode=_choice(raw.get("bg_mode"), BG_MODES, defaults.bg_mode),
        bg_height=_choice(raw.get("bg_height"), BG_HEIGHTS, defaults.bg_height),
        bg_sensitivity=_snap(
            raw.get("bg_sensitivity"), BG_SENSITIVITY_CHOICES, defaults.bg_sensitivity
        ),
        bg_opacity=_snap(raw.get("bg_opacity"), BG_OPACITY_CHOICES, defaults.bg_opacity),
        fg_mode=_choice(raw.get("fg_mode"), FG_MODES, defaults.fg_mode),
        fg_intensity=_snap(raw.get("fg_intensity"), FG_INTENSITY_CHOICES, defaults.fg_intensity),
        fg_direction=_choice(raw.get("fg_direction"), FG_DIRECTIONS, defaults.fg_direction),
        fg_color=_choice(raw.get("fg_color"), FG_COLOR_CHOICES, defaults.fg_color),
        fg_opacity=_snap(raw.get("fg_opacity"), FG_OPACITY_CHOICES, defaults.fg_opacity),
        fg_flash=_snap(raw.get("fg_flash"), FG_FLASH_CHOICES, defaults.fg_flash),
        fg_reactivity=_snap(
            raw.get("fg_reactivity"), FG_REACTIVITY_CHOICES, defaults.fg_reactivity
        ),
        fg_wind=_snap(raw.get("fg_wind"), FG_WIND_CHOICES, defaults.fg_wind),
        source_id=_str(raw.get("source_id"), defaults.source_id),
        active_look=_str(raw.get("active_look"), defaults.active_look),
        random_pool=_str_list(raw.get("random_pool"), defaults.random_pool),
        random_interval=_interval(raw.get("random_interval"), defaults.random_interval),
        random_options=_bool(raw.get("random_options"), defaults.random_options),
        random_fade=_fade(raw.get("random_fade"), defaults.random_fade),
        beat_enabled=_bool(raw.get("beat_enabled"), defaults.beat_enabled),
        beat_levels=_beat_levels(raw.get("beat_levels"), defaults.beat_levels),
        beat_bands=_beat_bands(raw.get("beat_bands"), defaults.beat_bands),
        beat_indicator=_bool(raw.get("beat_indicator"), defaults.beat_indicator),
        beat_indicator_pos=_choice(
            raw.get("beat_indicator_pos"),
            tuple(key for key, _label in BEAT_INDICATOR_POSITIONS),
            defaults.beat_indicator_pos,
        ),
        beat_indicator_shape=_choice(
            raw.get("beat_indicator_shape"),
            tuple(key for key, _label in BEAT_INDICATOR_SHAPES),
            defaults.beat_indicator_shape,
        ),
        beat_indicator_opacity=_choice(
            raw.get("beat_indicator_opacity"),
            tuple(key for key, _label, _v in BEAT_INDICATOR_OPACITY_CHOICES),
            defaults.beat_indicator_opacity,
        ),
        beat_fade=_choice(
            raw.get("beat_fade"),
            tuple(key for key, _label, _s in BEAT_FADE_CHOICES),
            defaults.beat_fade,
        ),
        color_hue=max(0.0, min(1.0, _float(raw.get("color_hue"), defaults.color_hue))),
        color_hue2=max(0.0, min(1.0, _float(raw.get("color_hue2"), defaults.color_hue2))),
    )


def _beat_levels(value: object, default: dict[str, int]) -> dict[str, int]:
    """Keep only known action keys with in-range level indexes (lenient on junk)."""
    if not isinstance(value, dict):
        return dict(default)
    valid_keys = {key for key, _label in BEAT_ACTIONS}
    max_level = len(BEAT_SENSITIVITY_LABELS) - 1
    out: dict[str, int] = {}
    for key, level in value.items():
        if key in valid_keys and isinstance(level, int) and not isinstance(level, bool):
            out[key] = max(0, min(max_level, level))
    return out


def _beat_bands(value: object, default: dict[str, str]) -> dict[str, str]:
    """Keep only known action keys mapped to a known band id (lenient on junk)."""
    if not isinstance(value, dict):
        return dict(default)
    valid_actions = {key for key, _label in BEAT_ACTIONS}
    valid_bands = {key for key, _label in BEAT_BANDS}
    return {
        key: band
        for key, band in value.items()
        if key in valid_actions and isinstance(band, str) and band in valid_bands
    }


def _str(value: object, default: str) -> str:
    return value if isinstance(value, str) else default


def _str_list(value: object, default: list[str]) -> list[str]:
    """Keep only the string entries of a stored list (lenient on junk)."""
    if not isinstance(value, list):
        return list(default)
    return [item for item in value if isinstance(item, str)]


def _interval(value: object, default: float) -> float:
    """Clamp a stored auto-cycle interval into the allowed range (lenient)."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    return float(min(RANDOM_INTERVAL_MAX, max(RANDOM_INTERVAL_MIN, float(value))))


def _fade(value: object, default: float) -> float:
    """Clamp a stored cross-fade length into the allowed range (lenient)."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    return float(min(RANDOM_FADE_MAX, max(RANDOM_FADE_MIN, float(value))))


def _bool(value: object, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _choice(value: object, allowed: tuple[str, ...], default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def _float(value: object, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    return float(value)


def _opacity(value: object, default: float) -> float:
    """Snap a stored opacity to the nearest allowed preset (lenient on type)."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    return min(LOGO_OPACITIES, key=lambda preset: abs(preset - float(value)))


def _snap(value: object, choices: tuple[float, ...], default: float) -> float:
    """Snap a stored float to the nearest value in ``choices`` (lenient on type)."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    return min(choices, key=lambda preset: abs(preset - float(value)))


def _size(value: object, default: tuple[int, int]) -> tuple[int, int]:
    if (
        isinstance(value, list | tuple)
        and len(value) == 2
        and all(isinstance(v, int | float) and not isinstance(v, bool) for v in value)
    ):
        return (int(value[0]), int(value[1]))
    return default
