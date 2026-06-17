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
    BG_HEIGHT_DEFAULT,
    BG_HEIGHTS,
    BG_MODE_DEFAULT,
    BG_MODES,
    BG_OPACITY_CHOICES,
    BG_OPACITY_DEFAULT,
    BG_SENSITIVITY_CHOICES,
    BG_SENSITIVITY_DEFAULT,
    COLOR_SCHEME_DEFAULT,
    COLOR_SCHEMES,
    DEFAULT_WINDOW_SIZE,
    LOGO_COLOR_DEFAULT,
    LOGO_COLOR_MODES,
    LOGO_EMIT_DEFAULT,
    LOGO_ENABLED_DEFAULT,
    LOGO_OPACITIES,
    LOGO_OPACITY_DEFAULT,
    LOGO_POSITION_DEFAULT,
    LOGO_POSITIONS,
    LOGO_SIZE_DEFAULT,
    LOGO_SIZES,
    LOGO_SPIN_DIR_DEFAULT,
    LOGO_SPIN_DIRS,
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
    # Logo spin direction (Phase 10.03 / schema v6).
    logo_spin: str = LOGO_SPIN_DIR_DEFAULT
    # UI appearance (Phase 9.03 / schema v3).
    ui_style: str = UI_STYLE_DEFAULT
    ui_font: str = UI_FONT_DEFAULT
    # Accent color + global background layer (Phase 10 / schema v4).
    ui_accent: str = UI_ACCENT_DEFAULT
    bg_mode: str = BG_MODE_DEFAULT
    bg_height: str = BG_HEIGHT_DEFAULT
    # Per-backdrop reactivity + opacity (Phase 10.01 / schema v5).
    bg_sensitivity: float = BG_SENSITIVITY_DEFAULT
    bg_opacity: float = BG_OPACITY_DEFAULT

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
    return raw


def _from_dict(raw: dict) -> Settings:
    """Build Settings from a dict, type-checking each key and ignoring extras."""
    defaults = Settings()
    return Settings(
        schema_version=SETTINGS_SCHEMA_VERSION,
        mode=_str(raw.get("mode"), defaults.mode),
        sensitivity=_float(raw.get("sensitivity"), defaults.sensitivity),
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
        logo_spin=_choice(raw.get("logo_spin"), LOGO_SPIN_DIRS, defaults.logo_spin),
        ui_style=_choice(raw.get("ui_style"), UI_STYLES, defaults.ui_style),
        ui_font=_choice(raw.get("ui_font"), UI_FONTS, defaults.ui_font),
        ui_accent=_choice(raw.get("ui_accent"), UI_ACCENTS, defaults.ui_accent),
        bg_mode=_choice(raw.get("bg_mode"), BG_MODES, defaults.bg_mode),
        bg_height=_choice(raw.get("bg_height"), BG_HEIGHTS, defaults.bg_height),
        bg_sensitivity=_snap(
            raw.get("bg_sensitivity"), BG_SENSITIVITY_CHOICES, defaults.bg_sensitivity
        ),
        bg_opacity=_snap(raw.get("bg_opacity"), BG_OPACITY_CHOICES, defaults.bg_opacity),
    )


def _str(value: object, default: str) -> str:
    return value if isinstance(value, str) else default


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
