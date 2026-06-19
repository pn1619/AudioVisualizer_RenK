"""The App: owns the window + main loop and wires audio, analysis, visuals, UI.

Business logic lives in ``audio/``, ``visuals/``, and ``ui/``; this module is
the wiring (events, resize, fullscreen, mode switching, drawing order).
"""

from __future__ import annotations

import dataclasses
import logging
import math
import random
from typing import TypeVar

import numpy as np
import pygame
from numpy.typing import NDArray

from audio_visualizer import looks as looks_mod
from audio_visualizer import settings as settings_mod
from audio_visualizer.audio.analysis import Analyzer
from audio_visualizer.audio.capture import LoopbackSource
from audio_visualizer.audio.devices import list_sources
from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.audio.source import AudioSource, SourceStatus, SyntheticSource
from audio_visualizer.beat_trigger import BeatTrigger
from audio_visualizer.config import (
    APP_ICON_FILENAME,
    APP_NAME,
    APP_VERSION,
    BEAT_INDICATOR_POSITIONS,
    BG_HEIGHT_LABELS,
    BG_HEIGHTS,
    BG_MODE_LABELS,
    BG_MODES,
    BG_OPACITY_CHOICES,
    BG_SENSITIVITY_CHOICES,
    COLOR_BAR,
    COLOR_BG,
    COLOR_CYCLE_RATE,
    COLOR_SCHEMES,
    COLOR_TEXT_DIM,
    DEVICE_RECOVER_INTERVAL,
    FFT_SIZE,
    HISTORY_MAX,
    IDLE_BANNER_DELAY,
    LOGO_COLOR_LABELS,
    LOGO_COLOR_MODES,
    LOGO_FILENAME,
    LOGO_OPACITIES,
    LOGO_POSITION_LABELS,
    LOGO_POSITIONS,
    LOGO_SIZE_LABELS,
    LOGO_SIZES,
    LOGO_SPIN_DIR_LABELS,
    LOGO_SPIN_DIRS,
    MERGED_MODE_KEYS,
    MIN_WINDOW_SIZE,
    RANDOM_FADE_MAX,
    RANDOM_FADE_MIN,
    RANDOM_FADE_STEP,
    RANDOM_INTERVAL_MAX,
    RANDOM_INTERVAL_MIN,
    RANDOM_INTERVAL_STEP,
    SENS_BANDS,
    SENSITIVITY_MAX,
    SENSITIVITY_MIN,
    SENSITIVITY_STEP,
    SIZE_SCALE_MAX,
    SIZE_SCALE_MIN,
    SIZE_SCALE_STEP,
    SMOOTHING_ATTACK_AT_0,
    SMOOTHING_ATTACK_AT_1,
    SMOOTHING_RELEASE_AT_0,
    SMOOTHING_RELEASE_AT_1,
    SMOOTHING_STEP,
    SPEED_SCALE_MAX,
    SPEED_SCALE_MIN,
    SPEED_SCALE_STEP,
    TARGET_FPS,
    UI_ACCENT_LABELS,
    UI_ACCENTS,
    UI_FONT_LABELS,
    UI_FONTS,
    UI_STYLE_LABELS,
    UI_STYLES,
)
from audio_visualizer.looks import LINK_LOCAL, Look
from audio_visualizer.resources import asset_path
from audio_visualizer.settings import Settings
from audio_visualizer.ui.about import AboutDialog
from audio_visualizer.ui.appearance_panel import AppearanceActions, AppearancePanel
from audio_visualizer.ui.background_panel import BackgroundActions, BackgroundPanel
from audio_visualizer.ui.beat_indicator import draw_beat_indicator
from audio_visualizer.ui.beat_panel import BeatPanel
from audio_visualizer.ui.controls import ControlActions, ControlBar, OptionSpec
from audio_visualizer.ui.fonts import get_ui_fonts
from audio_visualizer.ui.hotkeys import HotkeysDialog
from audio_visualizer.ui.hud import Hud, HudState
from audio_visualizer.ui.layout import Layout
from audio_visualizer.ui.logo_panel import LogoPanel, LogoPanelActions
from audio_visualizer.ui.looks_panel import LooksActions, LooksPanel
from audio_visualizer.ui.shuffle_panel import ShuffleActions, ShufflePanel
from audio_visualizer.ui.source_panel import SourceActions, SourcePanel
from audio_visualizer.ui.style import STYLE
from audio_visualizer.visuals import registry
from audio_visualizer.visuals._transition import ModeTransition
from audio_visualizer.visuals.background import Background
from audio_visualizer.visuals.base import BaseVisualizer, Theme
from audio_visualizer.visuals.logo import RenkLogo

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

# Zero band-energies fed to the beat engine while idle (so baselines keep decaying).
_EMPTY_BANDS = np.zeros(0, dtype=np.float32)


def _smoothing_to_coeffs(level: float) -> tuple[float, float]:
    """Map a 0..1 smoothing level to (attack, release) coefficients.

    Linearly interpolates between the "snappy" endpoints (level 0) and the
    "smooth" endpoints (level 1). Higher level -> slower release -> calmer visuals.
    """
    level = float(np.clip(level, 0.0, 1.0))
    attack = SMOOTHING_ATTACK_AT_0 + (SMOOTHING_ATTACK_AT_1 - SMOOTHING_ATTACK_AT_0) * level
    release = SMOOTHING_RELEASE_AT_0 + (SMOOTHING_RELEASE_AT_1 - SMOOTHING_RELEASE_AT_0) * level
    return attack, release


def _nearest(value: object, choices: tuple[float, ...], default: float) -> float:
    """Snap a stored number to the nearest allowed choice (lenient on type)."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    return min(choices, key=lambda choice: abs(choice - float(value)))


def _parse_float(text: str) -> float | None:
    """Parse user-typed text to a finite float, or None if it isn't a usable number.

    Used by the editable value chips: a blank or nonsense entry is simply ignored
    (returns None) so a bad keystroke never raises or crashes the app.
    """
    try:
        value = float(text.strip())
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


class App:
    """The application window and main loop."""

    def __init__(self, start_mode: str | None = None, load_settings: bool = True) -> None:
        pygame.init()
        pygame.display.set_caption(f"{APP_NAME} {APP_VERSION}")

        self._settings: Settings = settings_mod.load() if load_settings else Settings()
        self._persist = load_settings

        # UI appearance (style + font) is user-selectable and applied before any
        # widget draws; STYLE is the process-wide look read by widgets.
        self._ui_style = self._settings.ui_style
        self._ui_font = self._settings.ui_font
        self._ui_accent = self._settings.ui_accent
        STYLE.set_style(self._ui_style)
        STYLE.set_accent(self._ui_accent)

        registry.discover()
        self._mode_keys = registry.keys()
        if not self._mode_keys:
            raise RuntimeError("No visual modes registered")
        self._mode_index = self._resolve_start_index(start_mode or self._settings.mode or None)

        self._sensitivity = float(
            np.clip(self._settings.sensitivity, SENSITIVITY_MIN, SENSITIVITY_MAX)
        )
        self._sens_band = self._settings.sens_band
        self._smoothing = float(np.clip(self._settings.smoothing, 0.0, 1.0))
        self._reduce_motion = self._settings.reduce_motion
        self._notice_acknowledged = self._settings.notice_acknowledged
        self._theme = Theme(
            size_scale=float(np.clip(self._settings.size_scale, SIZE_SCALE_MIN, SIZE_SCALE_MAX)),
            speed_scale=float(
                np.clip(self._settings.speed_scale, SPEED_SCALE_MIN, SPEED_SCALE_MAX)
            ),
            color_scheme=self._settings.color_scheme,
        )

        self._fullscreen = self._settings.fullscreen
        self._windowed_size = (
            max(MIN_WINDOW_SIZE[0], self._settings.window_size[0]),
            max(MIN_WINDOW_SIZE[1], self._settings.window_size[1]),
        )
        if self._fullscreen:
            self._screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self._screen = pygame.display.set_mode(self._windowed_size, pygame.RESIZABLE)
        self._set_window_icon()

        self._font, self._font_small = get_ui_fonts(self._ui_font)
        self._clock = pygame.time.Clock()

        self._source_id = self._settings.source_id
        self._source: AudioSource = LoopbackSource(device_id=self._source_id)
        self._analyzer = Analyzer()
        self._analyzer.set_smoothing(*_smoothing_to_coeffs(self._smoothing))
        self._frame: AnalysisFrame | None = None
        self._capturing = False
        self._error = False
        self._recover_timer = 0.0
        self._silent_seconds = 0.0  # how long the signal has been silent

        self._visual: BaseVisualizer = self._make_visual()
        self._visual.on_enter()

        self._background = Background(theme=self._theme, reduce_motion=self._reduce_motion)
        self._background.mode = self._settings.bg_mode
        self._background.height_key = self._settings.bg_height
        self._background.sensitivity = self._settings.bg_sensitivity
        self._background.opacity = self._settings.bg_opacity

        self._logo = RenkLogo(reduce_motion=self._reduce_motion, theme=self._theme)
        self._apply_logo_settings()
        self._logo_panel = LogoPanel(self._build_logo_panel_actions())
        self._appearance = AppearancePanel(self._build_appearance_actions())
        self._background_panel = BackgroundPanel(self._build_background_actions())
        self._source_panel = SourcePanel(SourceActions(select=self._select_source))
        self._about = AboutDialog()
        self._hotkeys = HotkeysDialog()
        # Beat Buttons: music onsets auto-press actions (Rnd / Next). Levels/bands +
        # the on-screen indicator persist.
        self._beat = BeatTrigger(self._settings.beat_levels, self._settings.beat_bands)
        self._beat_indicator = bool(self._settings.beat_indicator)
        self._beat_indicator_pos = self._settings.beat_indicator_pos
        self._beat_panel = BeatPanel(
            set_level=self._set_beat_level,
            set_band=self._set_beat_band,
            toggle_indicator=self._toggle_beat_indicator,
            set_position=self._set_beat_indicator_pos,
        )

        # User looks ("My Looks", Phase 0B-b): a saved-look store + its modal. The
        # active look is an overlay on the live global; entering one snapshots the
        # live state so deselecting ("None / Live") restores it untouched.
        self._looks_store = looks_mod.load()
        self._active_look_id = (
            self._settings.active_look
            if self._looks_store.get(self._settings.active_look) is not None
            else ""
        )
        self._look_baseline: Look | None = None
        self._looks_panel = LooksPanel(self._build_looks_actions())

        # Auto-cycle ("shuffle", Phase 0B-c): rotate the active visual every
        # interval, cross-fading. The pool is a set of tagged ids — "mode:<key>"
        # (built-in modes) and "look:<id>" (saved looks). Empty pool ⇒ no shuffle.
        # A switch freezes the canvas into a ModeTransition and applies the next
        # item live; stopping leaves you on whatever is currently showing.
        self._auto = False  # never persisted on; off each launch
        self._auto_pool: set[str] = {
            tag for tag in self._settings.random_pool if self._pool_tag_valid(tag)
        }
        self._auto_current = ""  # last item shuffle landed on (for no-immediate-repeat)
        # Session look history (Prev/Next). A list of Look snapshots with a cursor;
        # commit truncates any forward branch, navigation just moves the cursor.
        self._history: list[Look] = []
        self._history_pos = -1
        self._auto_interval = float(
            min(RANDOM_INTERVAL_MAX, max(RANDOM_INTERVAL_MIN, self._settings.random_interval))
        )
        self._auto_fade = float(
            min(RANDOM_FADE_MAX, max(RANDOM_FADE_MIN, self._settings.random_fade))
        )
        self._auto_elapsed = 0.0
        # When on, shuffling to a built-in mode also randomizes that mode's own
        # options (Background/Logo stay put; saved looks keep their captured options).
        self._auto_random_options = bool(self._settings.random_options)
        # Randomize "locks": a locked item is held (not re-rolled) by Rnd / Next / auto.
        # Global locks persist across mode switches; per-mode option locks reset on a
        # mode switch (the new mode has a different option set).
        self._locked_globals: set[str] = set()
        self._locked_options: set[str] = set()
        self._transition: ModeTransition | None = None
        self._shuffle_panel = ShufflePanel(self._build_shuffle_actions())

        self._hud = Hud()
        self._controls = ControlBar(self._build_actions(), registry.options())
        self._refresh_mode_options()  # populates option dropdowns + lays out the bar

        # Re-apply the last active look now that the visual/theme/overlays exist.
        if self._active_look_id:
            self._look_baseline = self._capture_look("baseline")
            self._apply_look(self._looks_store.get(self._active_look_id))

        # Seed history entry 0 with the launch look so Prev can return to it.
        self._commit_history()

        self._running = False

    def _set_window_icon(self) -> None:
        """Set the title-bar/taskbar icon from the RenK emblem (best effort)."""
        path = asset_path(APP_ICON_FILENAME) or asset_path(LOGO_FILENAME)
        if path is None:
            return
        try:
            icon = pygame.image.load(str(path)).convert_alpha()
            pygame.display.set_icon(pygame.transform.smoothscale(icon, (64, 64)))
        except pygame.error:
            logger.warning("Could not set window icon from %s", path, exc_info=True)

    # -- setup helpers --------------------------------------------------------
    def _resolve_start_index(self, start_mode: str | None) -> int:
        if start_mode and start_mode in self._mode_keys:
            return self._mode_keys.index(start_mode)
        if start_mode:
            logger.warning("Unknown --mode %r; using default", start_mode)
        return 0

    def _make_visual(self) -> BaseVisualizer:
        key = self._mode_keys[self._mode_index]
        visual = registry.create(key, reduce_motion=self._reduce_motion)
        visual.theme = self._theme  # share the one live theme so changes apply instantly
        return visual

    def _build_actions(self) -> ControlActions:
        return ControlActions(
            toggle_capture=self._toggle_capture,
            prev_mode=lambda: self._cycle_mode(-1),
            next_mode=lambda: self._cycle_mode(1),
            select_mode=self._set_mode_key,
            sensitivity_down=lambda: self._adjust_sensitivity(-SENSITIVITY_STEP),
            sensitivity_up=lambda: self._adjust_sensitivity(SENSITIVITY_STEP),
            smoothing_down=lambda: self._adjust_smoothing(-SMOOTHING_STEP),
            smoothing_up=lambda: self._adjust_smoothing(SMOOTHING_STEP),
            size_down=lambda: self._adjust_size(-SIZE_SCALE_STEP),
            size_up=lambda: self._adjust_size(SIZE_SCALE_STEP),
            speed_down=lambda: self._adjust_speed(-SPEED_SCALE_STEP),
            speed_up=lambda: self._adjust_speed(SPEED_SCALE_STEP),
            cycle_color_scheme=self._cycle_color_scheme,
            select_color=self._set_color_scheme,
            option_change=self._set_mode_option,
            toggle_reduce_motion=self._toggle_reduce_motion,
            open_logo_panel=lambda: self._logo_panel.toggle(),
            open_about=lambda: self._about.toggle(),
            toggle_fullscreen=self._toggle_fullscreen,
            quit=self._request_quit,
            open_appearance=lambda: self._appearance.toggle(),
            open_background=lambda: self._background_panel.toggle(),
            open_source=self._open_source_panel,
            select_look=self._select_look,
            open_looks=self._open_looks_panel,
            toggle_auto=self._toggle_auto,
            open_shuffle=self._open_shuffle_panel,
            shuffle_next=self._history_next,
            previous=self._history_back,
            history_goto=self._history_goto,
            randomize_current=self._randomize_current_mode,
            set_sensitivity_value=self._set_sensitivity_text,
            set_smoothing_value=self._set_smoothing_text,
            set_size_value=self._set_size_text,
            set_speed_value=self._set_speed_text,
            toggle_global_lock=self._toggle_global_lock,
            toggle_option_lock=self._toggle_option_lock,
            open_hotkeys=lambda: self._hotkeys.toggle(),
            open_beat=self._open_beat_panel,
            select_sens_band=self._set_sens_band,
        )

    def _build_shuffle_actions(self) -> ShuffleActions:
        return ShuffleActions(
            toggle_auto=self._toggle_auto,
            shuffle_next=self._history_next,
            interval_down=lambda: self._adjust_interval(-RANDOM_INTERVAL_STEP),
            interval_up=lambda: self._adjust_interval(RANDOM_INTERVAL_STEP),
            fade_down=lambda: self._adjust_fade(-RANDOM_FADE_STEP),
            fade_up=lambda: self._adjust_fade(RANDOM_FADE_STEP),
            toggle_item=self._toggle_pool_item,
            set_all=self._set_pool_all,
            toggle_random_options=self._toggle_random_options,
            set_interval_value=self._set_interval_text,
            set_fade_value=self._set_fade_text,
        )

    def _build_looks_actions(self) -> LooksActions:
        return LooksActions(
            save_new=self._save_new_look,
            update_active=self._update_active_look,
            load=self._select_look,
            delete=self._delete_look,
            duplicate=self._duplicate_look,
            export_library=self._export_looks,
            import_library=self._import_looks,
            library_path=lambda: str(looks_mod.default_library_path()),
            refresh_state=lambda: (
                self._saved_look_rows(),
                self._active_look_id,
                self._active_look_name(),
            ),
        )

    def _build_appearance_actions(self) -> AppearanceActions:
        return AppearanceActions(
            cycle_style=self._cycle_ui_style,
            cycle_accent=self._cycle_ui_accent,
            cycle_font=self._cycle_ui_font,
        )

    def _build_background_actions(self) -> BackgroundActions:
        return BackgroundActions(
            cycle_mode=self._cycle_background,
            cycle_sensitivity=self._cycle_bg_sensitivity,
            cycle_opacity=self._cycle_bg_opacity,
            cycle_height=self._cycle_bg_height,
        )

    def _build_logo_panel_actions(self) -> LogoPanelActions:
        return LogoPanelActions(
            toggle_enabled=self._toggle_logo_enabled,
            cycle_color=self._cycle_logo_color,
            cycle_opacity=self._cycle_logo_opacity,
            cycle_size=self._cycle_logo_size,
            cycle_position=self._cycle_logo_position,
            cycle_spin=self._cycle_logo_spin,
            toggle_emit=self._toggle_logo_emit,
        )

    def _apply_logo_settings(self) -> None:
        """Copy the persisted logo preferences onto the live logo overlay."""
        s = self._settings
        self._logo.enabled = s.logo_enabled
        self._logo.size_key = s.logo_size
        self._logo.position = s.logo_position
        self._logo.opacity = s.logo_opacity
        self._logo.color_mode = s.logo_color
        self._logo.emit = s.logo_emit
        self._logo.spin_dir = s.logo_spin

    # -- public entry points --------------------------------------------------
    def run(self) -> int:
        """Run the interactive app until the user quits. Returns exit code."""
        self._running = True
        self._start_capture()
        try:
            while self._running:
                dt = self._clock.tick(TARGET_FPS) / 1000.0
                self._handle_events()
                self._update(dt)
                self._draw(dt)
                pygame.display.flip()
        finally:
            self._shutdown()
        return 0

    def run_selftest(self, frames: int) -> int:
        """Headless: render ``frames`` with a synthetic tone, then exit 0."""
        self._persist = False
        self._source = SyntheticSource(mode="sweep", sample_rate=48000)
        self._start_capture()
        try:
            for _ in range(max(1, frames)):
                dt = self._clock.tick(TARGET_FPS) / 1000.0
                pygame.event.pump()
                self._update(dt)
                self._draw(dt)
                pygame.display.flip()
        finally:
            self._shutdown()
        logger.info("Self-test OK (%d frames)", frames)
        return 0

    # -- actions --------------------------------------------------------------
    def _start_capture(self) -> None:
        self._analyzer.reset()
        self._source.start()
        self._capturing = self._source.status is SourceStatus.RUNNING
        self._error = self._source.status is SourceStatus.ERROR

    def _stop_capture(self) -> None:
        self._source.stop()
        self._capturing = False
        self._frame = None

    def _toggle_capture(self) -> None:
        if self._capturing:
            self._stop_capture()
        else:
            self._start_capture()

    # -- selectable source ----------------------------------------------------
    def _open_source_panel(self) -> None:
        """Refresh the device list (only when opening) and show the Source modal."""
        if not self._source_panel.open:
            self._source_panel.set_state(self._source_rows(), self._source_id)
        self._source_panel.toggle()

    def _source_rows(self) -> list[tuple[str, str]]:
        """(source_id, label) rows for the Source panel: default first, then devices."""
        rows: list[tuple[str, str]] = [("", "Default (system audio)")]
        for s in list_sources():
            prefix = "Output" if s.kind == "loopback" else "Input"
            suffix = "  (current default)" if s.is_default else ""
            rows.append((s.id, f"{prefix}: {s.name}{suffix}"))
        return rows

    def _select_source(self, source_id: str) -> None:
        """Switch the capture device (clean stop/recreate/start) and persist it."""
        self._source_id = source_id
        self._source.stop()
        self._source = LoopbackSource(device_id=source_id)
        self._start_capture()
        logger.info("Selected source %r", source_id or "(default)")

    # -- user looks ("My Looks") ---------------------------------------------
    def _capture_look(self, name: str, look_id: str = "") -> Look:
        """Snapshot the current live look into a :class:`Look` record."""
        return Look(
            id=look_id or looks_mod.new_id(),
            name=name,
            base_mode_key=self._mode_keys[self._mode_index],
            options={
                opt.key: self._visual.option_index(opt.key) for opt in type(self._visual).OPTIONS
            },
            theme={
                "size_scale": self._theme.size_scale,
                "speed_scale": self._theme.speed_scale,
                "color_scheme": self._theme.color_scheme,
            },
            sensitivity=self._sensitivity,
            smoothing=self._smoothing,
            background={
                "link": LINK_LOCAL,
                "value": {
                    "bg_mode": self._background.mode,
                    "bg_height": self._background.height_key,
                    "bg_sensitivity": self._background.sensitivity,
                    "bg_opacity": self._background.opacity,
                },
            },
            logo={
                "link": LINK_LOCAL,
                "value": {
                    "logo_enabled": self._logo.enabled,
                    "logo_size": self._logo.size_key,
                    "logo_position": self._logo.position,
                    "logo_opacity": self._logo.opacity,
                    "logo_color": self._logo.color_mode,
                    "logo_emit": self._logo.emit,
                    "logo_spin": self._logo.spin_dir,
                },
            },
            app_version=APP_VERSION,
        )

    def _apply_look(self, look: Look | None) -> None:
        """Push a saved look onto the live global (mode, options, theme, overlays).

        Unknown option keys and out-of-range values are ignored/clamped, never
        fatal; a missing/renamed mode falls back gracefully.
        """
        if look is None:
            return
        key = MERGED_MODE_KEYS.get(look.base_mode_key, look.base_mode_key)
        if key in self._mode_keys:
            self._set_mode_index(self._mode_keys.index(key))
        for opt in type(self._visual).OPTIONS:
            if opt.key in look.options:
                self._visual.set_option_index(opt.key, int(look.options[opt.key]))
        self._refresh_mode_options()
        self._apply_look_theme(look.theme)
        self._sensitivity = float(np.clip(look.sensitivity, SENSITIVITY_MIN, SENSITIVITY_MAX))
        self._smoothing = float(np.clip(look.smoothing, 0.0, 1.0))
        self._analyzer.set_smoothing(*_smoothing_to_coeffs(self._smoothing))
        if look.background.get("link") == LINK_LOCAL:
            self._apply_bg_value(look.background.get("value"))
        if look.logo.get("link") == LINK_LOCAL:
            self._apply_logo_value(look.logo.get("value"))

    def _apply_look_theme(self, theme: dict[str, object]) -> None:
        size = theme.get("size_scale")
        if isinstance(size, int | float) and not isinstance(size, bool):
            self._theme.size_scale = float(np.clip(size, SIZE_SCALE_MIN, SIZE_SCALE_MAX))
        speed = theme.get("speed_scale")
        if isinstance(speed, int | float) and not isinstance(speed, bool):
            self._theme.speed_scale = float(np.clip(speed, SPEED_SCALE_MIN, SPEED_SCALE_MAX))
        scheme = theme.get("color_scheme")
        if isinstance(scheme, str) and scheme in COLOR_SCHEMES:
            self._theme.color_scheme = scheme

    def _apply_bg_value(self, value: object) -> None:
        if not isinstance(value, dict):
            return
        if value.get("bg_mode") in BG_MODES:
            self._background.mode = value["bg_mode"]
        if value.get("bg_height") in BG_HEIGHTS:
            self._background.height_key = value["bg_height"]
        self._background.sensitivity = _nearest(
            value.get("bg_sensitivity"), BG_SENSITIVITY_CHOICES, self._background.sensitivity
        )
        self._background.opacity = _nearest(
            value.get("bg_opacity"), BG_OPACITY_CHOICES, self._background.opacity
        )

    def _apply_logo_value(self, value: object) -> None:
        if not isinstance(value, dict):
            return
        if isinstance(value.get("logo_enabled"), bool):
            self._logo.enabled = value["logo_enabled"]
        if value.get("logo_size") in LOGO_SIZES:
            self._logo.size_key = value["logo_size"]
        if value.get("logo_position") in LOGO_POSITIONS:
            self._logo.position = value["logo_position"]
        self._logo.opacity = _nearest(value.get("logo_opacity"), LOGO_OPACITIES, self._logo.opacity)
        if value.get("logo_color") in LOGO_COLOR_MODES:
            self._logo.color_mode = value["logo_color"]
        if isinstance(value.get("logo_emit"), bool):
            self._logo.emit = value["logo_emit"]
        if value.get("logo_spin") in LOGO_SPIN_DIRS:
            self._logo.spin_dir = value["logo_spin"]

    def _open_looks_panel(self) -> None:
        self._looks_panel.set_state(
            self._saved_look_rows(), self._active_look_id, self._active_look_name()
        )
        self._looks_panel.toggle()

    def _saved_look_rows(self) -> list[tuple[str, str]]:
        """(id, name) rows for saved looks only (the modal's managed list)."""
        return [(look.id, look.name) for look in self._looks_store.looks]

    def _looks_rows(self) -> list[tuple[str, str]]:
        """Dropdown rows: None/Live first, then saved looks (active marked dirty)."""
        rows: list[tuple[str, str]] = [("", "None / Live")]
        for look in self._looks_store.looks:
            name = look.name
            if look.id == self._active_look_id and self._is_active_dirty():
                name += " *"
            rows.append((look.id, name))
        return rows

    def _active_look_name(self) -> str:
        look = self._looks_store.get(self._active_look_id)
        return look.name if look else ""

    def _is_active_dirty(self) -> bool:
        """True when the live look differs from the stored active look."""
        look = self._looks_store.get(self._active_look_id)
        if look is None:
            return False
        return not self._capture_look(look.name).matches_payload(look)

    def _select_look(self, look_id: str) -> None:
        """Activate a saved look, or restore the live baseline for None/Live."""
        if look_id == self._active_look_id:
            return
        if not look_id:
            self._apply_look(self._look_baseline)
            self._look_baseline = None
            self._active_look_id = ""
            self._commit_history()
            return
        look = self._looks_store.get(look_id)
        if look is None:
            return
        if not self._active_look_id:
            self._look_baseline = self._capture_look("baseline")
        self._apply_look(look)
        self._active_look_id = look_id
        self._commit_history()

    def _save_new_look(self, name: str) -> None:
        """Bookmark the current live look. Stays on None/Live (never auto-applies).

        Activating the new look here would capture a baseline equal to it, so
        "None / Live" would then restore the saved snapshot (and re-picking the
        already-active look would be a no-op) — which reads as the two dropdown
        entries being swapped. Keeping the user on None/Live makes the saved look
        a distinct entry: selecting it applies the look, None/Live keeps the live.
        """
        created = self._looks_store.add(self._capture_look(name or "My look"))
        if created is not None:
            self._persist_looks()

    def _update_active_look(self) -> None:
        if not self._active_look_id:
            return
        cap = self._capture_look(self._active_look_name(), self._active_look_id)
        self._looks_store.update(
            self._active_look_id,
            base_mode_key=cap.base_mode_key,
            options=cap.options,
            theme=cap.theme,
            sensitivity=cap.sensitivity,
            smoothing=cap.smoothing,
            background=cap.background,
            logo=cap.logo,
        )
        self._persist_looks()

    def _delete_look(self, look_id: str) -> None:
        if look_id == self._active_look_id:
            self._select_look("")  # deselect first so the live baseline is restored
        if self._looks_store.delete(look_id):
            self._persist_looks()

    def _duplicate_look(self, look_id: str) -> None:
        if self._looks_store.duplicate(look_id) is not None:
            self._persist_looks()

    def _persist_looks(self) -> None:
        """Save the live looks file; log a clear hint if the write fails."""
        if not self._persist:
            return
        if not looks_mod.save(self._looks_store):
            logger.warning(
                "Could not save My Looks to %s. If this keeps happening the file may be "
                "locked or corrupt — close other instances or delete it to reset.",
                looks_mod.looks_path(),
            )

    def _export_looks(self) -> str:
        """Export the whole library to the companion file; return a status message."""
        path = looks_mod.default_library_path()
        if looks_mod.export_library(self._looks_store, path):
            n = len(self._looks_store.looks)
            return f"Exported {n} look{'s' if n != 1 else ''} to {path.name}."
        return f"Export failed — could not write {path.name} (see logs)."

    def _import_looks(self) -> str:
        """Merge the companion file into the library; return a status message."""
        path = looks_mod.default_library_path()
        imported = looks_mod.import_library(path)
        if not imported:
            return f"Nothing imported — {path.name} missing, empty, or corrupt."
        added = 0
        for look in imported:
            if self._looks_store.add(look) is not None:
                added += 1
        self._persist_looks()
        self._looks_panel.set_state(
            self._saved_look_rows(), self._active_look_id, self._active_look_name()
        )
        return f"Imported {added} look{'s' if added != 1 else ''} from {path.name}."

    # -- auto-cycle ("shuffle") ----------------------------------------------
    def _open_shuffle_panel(self) -> None:
        self._shuffle_panel.set_state(
            self._shuffle_rows(),
            self._interval_label(),
            self._auto,
            self._auto_random_options,
            self._fade_label(),
        )
        self._shuffle_panel.toggle()

    def _pool_tag_valid(self, tag: str) -> bool:
        """True if a tagged pool id still points at an existing mode or saved look."""
        if tag.startswith("mode:"):
            return tag.removeprefix("mode:") in self._mode_keys
        if tag.startswith("look:"):
            return self._looks_store.get(tag.removeprefix("look:")) is not None
        return False

    def _all_pool_tags(self) -> set[str]:
        """Every selectable rotation item: all built-in modes + all saved looks."""
        tags = {f"mode:{key}" for key in self._mode_keys}
        tags |= {f"look:{look.id}" for look in self._looks_store.looks}
        return tags

    def _ordered_pool_tags(self) -> list[str]:
        """Pooled items in stable display order (modes first, then saved looks)."""
        order = [f"mode:{key}" for key in self._mode_keys]
        order += [f"look:{look.id}" for look in self._looks_store.looks]
        return [tag for tag in order if tag in self._auto_pool]

    def _shuffle_rows(self) -> list[tuple[str, str, bool]]:
        """(tag, label, in_pool) rows for the Shuffle checklist (modes, then looks)."""
        rows = [
            (f"mode:{key}", name, f"mode:{key}" in self._auto_pool)
            for key, name in registry.options()
        ]
        rows += [
            (f"look:{look.id}", f"\u2605 {look.name}", f"look:{look.id}" in self._auto_pool)
            for look in self._looks_store.looks
        ]
        return rows

    def _interval_label(self) -> str:
        return f"Every {self._auto_interval:g}s"

    def _fade_label(self) -> str:
        return "Fade: cut" if self._auto_fade <= 0.0 else f"Fade: {self._auto_fade:.1f}s"

    def _toggle_auto(self) -> None:
        """Flip auto-cycle. Turning it on with an empty pool selects everything."""
        self._auto = not self._auto
        if self._auto and not self._auto_pool:
            self._auto_pool = self._all_pool_tags()
        self._auto_elapsed = 0.0
        logger.debug("Auto-cycle = %s (pool=%d)", self._auto, len(self._auto_pool))

    def _adjust_interval(self, delta: float) -> None:
        self._auto_interval = float(
            min(RANDOM_INTERVAL_MAX, max(RANDOM_INTERVAL_MIN, self._auto_interval + delta))
        )

    def _adjust_fade(self, delta: float) -> None:
        # Round to the step grid so repeated +/- never drifts off clean tenths.
        value = round((self._auto_fade + delta) / RANDOM_FADE_STEP) * RANDOM_FADE_STEP
        self._auto_fade = float(min(RANDOM_FADE_MAX, max(RANDOM_FADE_MIN, value)))

    def _set_interval_text(self, text: str) -> None:
        value = _parse_float(text)
        if value is not None:
            self._auto_interval = float(min(RANDOM_INTERVAL_MAX, max(RANDOM_INTERVAL_MIN, value)))

    def _set_fade_text(self, text: str) -> None:
        value = _parse_float(text)
        if value is not None:
            self._auto_fade = float(min(RANDOM_FADE_MAX, max(RANDOM_FADE_MIN, value)))

    def _toggle_pool_item(self, tag: str) -> None:
        if tag not in self._all_pool_tags():
            return
        if tag in self._auto_pool:
            self._auto_pool.discard(tag)
        else:
            self._auto_pool.add(tag)

    def _set_pool_all(self, on: bool) -> None:
        self._auto_pool = self._all_pool_tags() if on else set()

    def _toggle_random_options(self) -> None:
        """Flip whether shuffling to a mode also randomizes that mode's options."""
        self._auto_random_options = not self._auto_random_options
        logger.debug("Shuffle randomize-options = %s", self._auto_random_options)

    def _valid_pool(self) -> list[str]:
        """Pooled items that still exist, in stable order."""
        return self._ordered_pool_tags()

    def _shuffle_next(self) -> None:
        """Advance to the next rotation item now (works whether or not Auto is on)."""
        if not self._auto_pool:
            self._auto_pool = self._all_pool_tags()
        self._transition = None  # snap any in-flight fade to its end, then advance
        self._auto_elapsed = 0.0
        self._auto_advance()

    # -- Look history (Prev/Next back-forward queue) -------------------------
    def _commit_history(self) -> None:
        """Record the current live look, truncating any forward (redo) branch.

        Called after any user action that produces a *new* look (Rnd, a produced
        Next/Auto item, a manual mode switch, selecting a saved look). Navigating
        with Prev/Next does not commit — it only moves the cursor.
        """
        look = self._capture_look("")
        del self._history[self._history_pos + 1 :]
        self._history.append(look)
        if len(self._history) > HISTORY_MAX:
            self._history.pop(0)
        self._history_pos = len(self._history) - 1

    def _history_back(self) -> None:
        """Step back to the previously shown look (no-op at the oldest entry)."""
        if self._history_pos <= 0:
            return
        self._history_pos -= 1
        self._apply_history(self._history[self._history_pos])

    def _history_next(self) -> None:
        """Replay forward through history; at the newest entry, produce a new item."""
        if self._history_pos < len(self._history) - 1:
            self._history_pos += 1
            self._apply_history(self._history[self._history_pos])
        else:
            self._shuffle_next()  # produces a new item and commits it to history

    def _history_goto(self, text: str) -> None:
        """Jump to a 1-based history position typed into the chip (clamped to latest)."""
        try:
            target = int(text)
        except ValueError:
            return  # non-numeric input is ignored, never fatal
        if not self._history:
            return
        idx = max(0, min(target - 1, len(self._history) - 1))
        if idx == self._history_pos:
            return
        self._history_pos = idx
        self._apply_history(self._history[idx])

    def _apply_history(self, look: Look) -> None:
        """Re-apply a stored look with the usual snapshot dissolve (no commit)."""
        snapshot = self._screen.subsurface(self._layout.canvas).copy()
        self._apply_look(look)
        self._auto_elapsed = 0.0
        if self._reduce_motion or self._auto_fade <= 0.0:
            self._transition = None
        else:
            self._transition = ModeTransition(duration=self._auto_fade, snapshot=snapshot)

    def _update_auto(self, dt: float) -> None:
        """Advance any active fade, else tick the timer and start the next switch."""
        if self._transition is not None:
            if self._transition.advance(dt):
                self._transition = None
            return
        if not self._auto or self._modal_open() or self._notice_visible():
            return
        if not self._valid_pool():
            return
        self._auto_elapsed += dt
        if self._auto_elapsed >= self._auto_interval:
            self._auto_elapsed = 0.0
            self._auto_advance()

    # -- Beat Buttons (music-driven auto-triggers) ---------------------------
    def _refresh_beat_panel(self) -> None:
        self._beat_panel.set_state(
            self._beat.levels_dict(),
            self._beat.bands_dict(),
            self._beat_indicator,
            self._beat_indicator_pos,
        )

    def _open_beat_panel(self) -> None:
        self._refresh_beat_panel()
        self._beat_panel.toggle()

    def _set_beat_level(self, action: str, index: int) -> None:
        """Set an action's beat sensitivity level directly (from the dropdown)."""
        self._beat.set_level(action, index)
        self._refresh_beat_panel()
        logger.debug("Beat %s sensitivity = %d", action, self._beat.level(action))

    def _set_beat_band(self, action: str, band: str) -> None:
        """Set an action's listened band directly (from the dropdown)."""
        self._beat.set_band(action, band)
        self._refresh_beat_panel()
        logger.debug("Beat %s band = %s", action, self._beat.band(action))

    def _toggle_beat_indicator(self) -> None:
        self._beat_indicator = not self._beat_indicator
        self._refresh_beat_panel()

    def _set_beat_indicator_pos(self, position: str) -> None:
        keys = [key for key, _label in BEAT_INDICATOR_POSITIONS]
        if position in keys:
            self._beat_indicator_pos = position
            self._refresh_beat_panel()

    def _update_beat(self, dt: float) -> None:
        """Let the music auto-press actions; suppressed while a modal/notice is up."""
        frame = self._frame
        bands = frame.band_energies if frame is not None else _EMPTY_BANDS
        idle = not self._capturing or frame is None or frame.is_silent
        if self._modal_open() or self._notice_visible():
            self._beat.update(bands, is_silent=True, dt=dt)  # keep baseline/cooldowns ticking
            return
        for action in self._beat.update(bands, idle, dt):
            if action == "randomize":
                self._randomize_current_mode()
            elif action == "next":
                self._shuffle_next()

    def _pick_next(self) -> str | None:
        """Choose the next pooled item at random, never repeating the current one."""
        pool = self._valid_pool()
        choices = [tag for tag in pool if tag != self._auto_current]
        return random.choice(choices) if choices else None

    def _auto_advance(self) -> None:
        """Apply the next rotation item live and start a fade from the old scene.

        A **mode -> mode** switch keeps the outgoing visual alive and cross-fades
        both **live** (they keep animating); any switch involving a saved look
        uses a frozen-snapshot dissolve. Reduce-motion or a 0s fade hard-cuts.
        """
        nxt = self._pick_next()
        if nxt is None:
            return
        live = self._can_live_crossfade(nxt)
        prev_visual = self._visual if live else None
        snapshot = None if live else self._screen.subsurface(self._layout.canvas).copy()
        self._apply_pool_tag(nxt)
        self._auto_current = nxt
        self._commit_history()  # a produced item is a new look; record it
        if self._reduce_motion or self._auto_fade <= 0.0:  # hard cut, no double-render
            self._transition = None
            return
        if live:
            self._transition = ModeTransition(duration=self._auto_fade, prev_visual=prev_visual)
        else:
            self._transition = ModeTransition(duration=self._auto_fade, snapshot=snapshot)

    def _can_live_crossfade(self, nxt: str) -> bool:
        """True when both outgoing and incoming items are plain built-in modes.

        A live cross-fade re-renders the outgoing visual each frame, which only
        works when the outgoing state is a mode (not a look — a look also owns
        background/logo/theme, which we can't cheaply run a second copy of).
        """
        outgoing_is_mode = self._auto_current.startswith("mode:") or (
            self._auto_current == "" and not self._active_look_id
        )
        return outgoing_is_mode and nxt.startswith("mode:")

    def _apply_pool_tag(self, tag: str) -> None:
        """Apply a rotation item to the live global (a mode swap or a full look)."""
        if tag.startswith("mode:"):
            key = tag.removeprefix("mode:")
            if key in self._mode_keys:
                self._set_mode_index(self._mode_keys.index(key))
                if self._auto_random_options:
                    self._randomize_mode_options()
                    self._randomize_globals()
        elif tag.startswith("look:"):
            self._apply_look(self._looks_store.get(tag.removeprefix("look:")))

    def _randomize_mode_options(self) -> None:
        """Pick a random choice for each of the active mode's options.

        A ``preset`` option (if any) is forced to its "Custom" choice so the
        sibling options it would otherwise snap stay freely randomized and the
        dropdown does not advertise a preset whose values were overwritten.
        Background/Logo are global overlays, not mode options, so they are
        untouched here by design.
        """
        for opt in type(self._visual).OPTIONS:
            if opt.key in self._locked_options:
                continue  # held by the user's lock toggle
            if opt.key == "preset":
                self._visual.set_option_index(opt.key, 0)
            elif len(opt.choices) > 1:
                self._visual.set_option_index(opt.key, random.randrange(len(opt.choices)))
        self._refresh_mode_options()

    def _randomize_globals(self) -> None:
        """Randomize the global feel (sensitivity/smoothing/size/speed) across full ranges.

        Drawn from continuous uniform ranges (not a couple of preset steps) so each
        shuffle/Randomize genuinely varies — the chips will rarely repeat a value.
        """
        if "sensitivity" not in self._locked_globals:
            self._sensitivity = round(random.uniform(SENSITIVITY_MIN, SENSITIVITY_MAX), 2)
        if "smoothing" not in self._locked_globals:
            self._smoothing = round(random.uniform(0.0, 0.9), 2)
            self._analyzer.set_smoothing(*_smoothing_to_coeffs(self._smoothing))
        if "size" not in self._locked_globals:
            self._theme.size_scale = round(random.uniform(SIZE_SCALE_MIN, SIZE_SCALE_MAX), 2)
        if "speed" not in self._locked_globals:
            self._theme.speed_scale = round(random.uniform(SPEED_SCALE_MIN, SPEED_SCALE_MAX), 2)
        logger.debug(
            "Randomized globals: sens=%.2f smooth=%.2f size=%.2f speed=%.2f",
            self._sensitivity,
            self._smoothing,
            self._theme.size_scale,
            self._theme.speed_scale,
        )

    def _randomize_current_mode(self) -> None:
        """Randomize the active mode's options + global feel, keeping the same mode.

        This is the manual ``Rnd`` button / ``R`` key: it never switches modes, it
        just rolls fresh options and feel for whatever is on screen now.
        """
        self._randomize_mode_options()
        self._randomize_globals()
        self._commit_history()

    def _toggle_global_lock(self, key: str) -> None:
        """Toggle a global-feel lock (sensitivity/smoothing/size/speed)."""
        self._locked_globals ^= {key}
        logger.debug("Global lock %s -> %s", key, key in self._locked_globals)

    def _toggle_option_lock(self, key: str) -> None:
        """Toggle a per-mode option lock (cleared automatically on a mode switch)."""
        self._locked_options ^= {key}
        logger.debug("Option lock %s -> %s", key, key in self._locked_options)

    def _cycle_mode(self, delta: int) -> None:
        self._set_mode_index((self._mode_index + delta) % len(self._mode_keys))
        self._commit_history()

    def _set_mode_key(self, key: str) -> None:
        if key in self._mode_keys:
            self._set_mode_index(self._mode_keys.index(key))
            self._commit_history()

    def _set_mode_index(self, index: int) -> None:
        # A manual switch resets the auto timer so a shuffle never yanks a mode
        # the user just chose; the current-item marker keeps no-repeat honest.
        # (Auto-advance applies the next item *before* arming its fade, so the
        # clear here only ever cancels a fade the user is interrupting.)
        self._auto_elapsed = 0.0
        self._transition = None
        self._auto_current = f"mode:{self._mode_keys[index]}"
        if index == self._mode_index:
            return
        self._mode_index = index
        self._locked_options.clear()  # per-mode locks don't carry to a new mode
        self._visual.on_exit()
        self._visual = self._make_visual()
        self._visual.on_resize(self._layout.canvas.size)
        self._visual.on_enter()
        self._refresh_mode_options()

    def _refresh_mode_options(self) -> None:
        """Rebuild the control bar's per-mode option dropdowns for the active mode."""
        specs = [
            OptionSpec(
                opt.key,
                opt.label,
                tuple(choice.label for choice in opt.choices),
                self._visual.option_index(opt.key),
                # Only options that Rnd actually re-rolls can be locked (a single-choice
                # option or the "preset" selector isn't randomized, so no lock).
                lockable=opt.key != "preset" and len(opt.choices) > 1,
                locked=opt.key in self._locked_options,
            )
            for opt in type(self._visual).OPTIONS
        ]
        self._controls.set_mode_options(specs)
        # Option count changes the bar's flowed height, so recompute the layout.
        self._relayout(self._screen.get_size())

    def _set_mode_option(self, key: str, index: int) -> None:
        self._visual.set_option_index(key, index)
        logger.debug("Mode %s option %s = %d", self._visual.KEY, key, index)

    def _adjust_sensitivity(self, delta: float) -> None:
        self._sensitivity = float(
            np.clip(self._sensitivity + delta, SENSITIVITY_MIN, SENSITIVITY_MAX)
        )
        logger.debug("Sensitivity = %.2f", self._sensitivity)

    def _adjust_smoothing(self, delta: float) -> None:
        self._smoothing = float(np.clip(self._smoothing + delta, 0.0, 1.0))
        self._analyzer.set_smoothing(*_smoothing_to_coeffs(self._smoothing))
        logger.debug("Smoothing = %.2f", self._smoothing)

    def _adjust_size(self, delta: float) -> None:
        self._theme.size_scale = float(
            np.clip(self._theme.size_scale + delta, SIZE_SCALE_MIN, SIZE_SCALE_MAX)
        )
        logger.debug("Size scale = %.2f", self._theme.size_scale)

    def _adjust_speed(self, delta: float) -> None:
        self._theme.speed_scale = float(
            np.clip(self._theme.speed_scale + delta, SPEED_SCALE_MIN, SPEED_SCALE_MAX)
        )
        logger.debug("Speed scale = %.2f", self._theme.speed_scale)

    def _set_sensitivity_text(self, text: str) -> None:
        value = _parse_float(text)
        if value is not None:
            self._sensitivity = float(np.clip(value, SENSITIVITY_MIN, SENSITIVITY_MAX))
            logger.debug("Sensitivity = %.2f (typed)", self._sensitivity)

    def _set_sens_band(self, band: str) -> None:
        if band in {key for key, _label in SENS_BANDS}:
            self._sens_band = band
            logger.debug("Sensitivity band = %s", band)

    def _set_smoothing_text(self, text: str) -> None:
        value = _parse_float(text)
        if value is not None:
            self._smoothing = float(np.clip(value, 0.0, 1.0))
            self._analyzer.set_smoothing(*_smoothing_to_coeffs(self._smoothing))
            logger.debug("Smoothing = %.2f (typed)", self._smoothing)

    def _set_size_text(self, text: str) -> None:
        value = _parse_float(text)
        if value is not None:
            self._theme.size_scale = float(np.clip(value, SIZE_SCALE_MIN, SIZE_SCALE_MAX))
            logger.debug("Size scale = %.2f (typed)", self._theme.size_scale)

    def _set_speed_text(self, text: str) -> None:
        value = _parse_float(text)
        if value is not None:
            self._theme.speed_scale = float(np.clip(value, SPEED_SCALE_MIN, SPEED_SCALE_MAX))
            logger.debug("Speed scale = %.2f (typed)", self._theme.speed_scale)

    def _cycle_color_scheme(self) -> None:
        idx = (
            COLOR_SCHEMES.index(self._theme.color_scheme)
            if (self._theme.color_scheme in COLOR_SCHEMES)
            else 0
        )
        self._theme.color_scheme = COLOR_SCHEMES[(idx + 1) % len(COLOR_SCHEMES)]
        logger.debug("Color scheme = %s", self._theme.color_scheme)

    def _set_color_scheme(self, key: str) -> None:
        if key in COLOR_SCHEMES:
            self._theme.color_scheme = key
            logger.debug("Color scheme = %s", self._theme.color_scheme)

    def _toggle_reduce_motion(self) -> None:
        self._reduce_motion = not self._reduce_motion
        self._visual.reduce_motion = self._reduce_motion
        self._logo.reduce_motion = self._reduce_motion
        self._background.reduce_motion = self._reduce_motion
        logger.debug("Reduce motion = %s", self._reduce_motion)

    # -- RenK logo overlay ----------------------------------------------------
    @staticmethod
    def _cycle_next(seq: tuple[_T, ...], current: _T) -> _T:
        """Return the value after ``current`` in ``seq`` (wrapping)."""
        idx = seq.index(current) if current in seq else -1
        return seq[(idx + 1) % len(seq)]

    def _toggle_logo_enabled(self) -> None:
        self._logo.enabled = not self._logo.enabled
        logger.debug("Logo enabled = %s", self._logo.enabled)

    def _cycle_logo_color(self) -> None:
        self._logo.color_mode = self._cycle_next(LOGO_COLOR_MODES, self._logo.color_mode)

    def _cycle_logo_opacity(self) -> None:
        self._logo.opacity = self._cycle_next(LOGO_OPACITIES, self._logo.opacity)

    def _cycle_logo_size(self) -> None:
        self._logo.size_key = self._cycle_next(LOGO_SIZES, self._logo.size_key)

    def _cycle_logo_position(self) -> None:
        self._logo.position = self._cycle_next(LOGO_POSITIONS, self._logo.position)

    def _cycle_logo_spin(self) -> None:
        self._logo.spin_dir = self._cycle_next(LOGO_SPIN_DIRS, self._logo.spin_dir)

    def _toggle_logo_emit(self) -> None:
        self._logo.emit = not self._logo.emit

    def _logo_panel_values(self) -> dict[str, str]:
        """Human-readable current values for the logo settings panel rows."""
        return {
            "enabled": "On" if self._logo.enabled else "Off",
            "color": LOGO_COLOR_LABELS.get(self._logo.color_mode, self._logo.color_mode),
            "opacity": f"{int(self._logo.opacity * 100)}%",
            "size": LOGO_SIZE_LABELS.get(self._logo.size_key, self._logo.size_key),
            "position": LOGO_POSITION_LABELS.get(self._logo.position, self._logo.position),
            "spin": LOGO_SPIN_DIR_LABELS.get(self._logo.spin_dir, self._logo.spin_dir),
            "emit": "On" if self._logo.emit else "Off",
        }

    # -- UI appearance --------------------------------------------------------
    def _cycle_ui_style(self) -> None:
        self._ui_style = self._cycle_next(UI_STYLES, self._ui_style)
        STYLE.set_style(self._ui_style)
        logger.debug("UI style = %s", self._ui_style)

    def _cycle_ui_font(self) -> None:
        self._ui_font = self._cycle_next(UI_FONTS, self._ui_font)
        self._font, self._font_small = get_ui_fonts(self._ui_font)
        logger.debug("UI font = %s", self._ui_font)

    def _cycle_ui_accent(self) -> None:
        self._ui_accent = self._cycle_next(UI_ACCENTS, self._ui_accent)
        STYLE.set_accent(self._ui_accent)
        logger.debug("UI accent = %s", self._ui_accent)

    def _appearance_values(self) -> dict[str, str]:
        """Human-readable current values for the Appearance panel rows."""
        return {
            "style": UI_STYLE_LABELS.get(self._ui_style, self._ui_style),
            "accent": UI_ACCENT_LABELS.get(self._ui_accent, self._ui_accent),
            "font": UI_FONT_LABELS.get(self._ui_font, self._ui_font),
        }

    # -- Background layer -----------------------------------------------------
    def _cycle_background(self) -> None:
        self._background.mode = self._cycle_next(BG_MODES, self._background.mode)
        logger.debug("Background = %s", self._background.mode)

    def _cycle_bg_height(self) -> None:
        self._background.height_key = self._cycle_next(BG_HEIGHTS, self._background.height_key)
        logger.debug("Background height = %s", self._background.height_key)

    def _cycle_bg_sensitivity(self) -> None:
        self._background.sensitivity = self._cycle_next(
            BG_SENSITIVITY_CHOICES, self._background.sensitivity
        )
        logger.debug("Background sensitivity = %s", self._background.sensitivity)

    def _cycle_bg_opacity(self) -> None:
        self._background.opacity = self._cycle_next(BG_OPACITY_CHOICES, self._background.opacity)
        logger.debug("Background opacity = %s", self._background.opacity)

    def _background_values(self) -> dict[str, str]:
        """Human-readable current values for the Background panel rows."""
        return {
            "mode": BG_MODE_LABELS.get(self._background.mode, self._background.mode),
            "sensitivity": f"x{self._background.sensitivity:.2f}",
            "opacity": f"{int(self._background.opacity * 100)}%",
            "height": BG_HEIGHT_LABELS.get(
                self._background.height_key, self._background.height_key
            ),
        }

    def _notice_visible(self) -> bool:
        """The one-time photosensitivity notice shows before strobing modes."""
        return not self._notice_acknowledged and self._visual.STROBES

    def _dismiss_notice(self) -> None:
        self._notice_acknowledged = True

    def _toggle_fullscreen(self) -> None:
        self._fullscreen = not self._fullscreen
        if self._fullscreen:
            self._windowed_size = self._screen.get_size()
            self._screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self._screen = pygame.display.set_mode(self._windowed_size, pygame.RESIZABLE)
        self._relayout(self._screen.get_size())

    def _request_quit(self) -> None:
        self._running = False

    def _modal_open(self) -> bool:
        return (
            self._logo_panel.open
            or self._about.open
            or self._appearance.open
            or self._background_panel.open
            or self._source_panel.open
            or self._looks_panel.open
            or self._shuffle_panel.open
            or self._hotkeys.open
            or self._beat_panel.open
        )

    def _close_modals(self) -> None:
        self._logo_panel.open = False
        self._about.open = False
        self._appearance.open = False
        self._background_panel.open = False
        self._source_panel.open = False
        self._looks_panel.open = False
        self._shuffle_panel.open = False
        self._hotkeys.open = False
        self._beat_panel.open = False

    # -- loop body ------------------------------------------------------------
    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
                continue
            # While the safety notice is up, the first key/click only dismisses it.
            if self._notice_visible() and event.type in (
                pygame.KEYDOWN,
                pygame.MOUSEBUTTONDOWN,
            ):
                self._dismiss_notice()
                continue
            # A modal (logo settings / About) captures input while open.
            if self._modal_open():
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self._close_modals()
                else:
                    canvas = self._layout.canvas
                    self._logo_panel.handle_event(event, canvas)
                    self._appearance.handle_event(event, canvas)
                    self._background_panel.handle_event(event, canvas)
                    self._source_panel.handle_event(event, canvas)
                    self._looks_panel.handle_event(event, canvas)
                    self._shuffle_panel.handle_event(event, canvas)
                    self._about.handle_event(event, canvas)
                    self._hotkeys.handle_event(event, canvas)
                    self._beat_panel.handle_event(event, canvas)
                continue
            if event.type == pygame.VIDEORESIZE and not self._fullscreen:
                size = (max(MIN_WINDOW_SIZE[0], event.w), max(MIN_WINDOW_SIZE[1], event.h))
                self._screen = pygame.display.set_mode(size, pygame.RESIZABLE)
                self._relayout(size)
            elif event.type == pygame.KEYDOWN:
                # While a value chip is capturing typed input, keystrokes belong to it
                # (don't let single-key shortcuts fire under the typist).
                if not (self._layout.show_control_bar and self._controls.is_editing()):
                    self._handle_key(event)
            if self._layout.show_control_bar:
                self._controls.handle_event(event)

    def _handle_key(self, event: pygame.event.Event) -> None:
        key = event.key
        mods = event.mod
        if key == pygame.K_q and (mods & pygame.KMOD_CTRL):
            self._running = False
        elif key == pygame.K_ESCAPE:
            # ESC never quits: it only closes a modal or leaves fullscreen.
            if self._fullscreen:
                self._toggle_fullscreen()
        elif key == pygame.K_SPACE:
            self._toggle_capture()
        elif key in (pygame.K_LEFT, pygame.K_LEFTBRACKET):
            self._cycle_mode(-1)
        elif key in (pygame.K_RIGHT, pygame.K_RIGHTBRACKET):
            self._cycle_mode(1)
        elif key == pygame.K_F11:
            self._toggle_fullscreen()
        elif key == pygame.K_F3:
            self._hud.toggle_debug()
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self._adjust_sensitivity(-SENSITIVITY_STEP)
        elif key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            self._adjust_sensitivity(SENSITIVITY_STEP)
        elif key == pygame.K_COMMA:
            self._adjust_smoothing(-SMOOTHING_STEP)
        elif key == pygame.K_PERIOD:
            self._adjust_smoothing(SMOOTHING_STEP)
        elif key == pygame.K_F5:
            self._adjust_size(-SIZE_SCALE_STEP)
        elif key == pygame.K_F6:
            self._adjust_size(SIZE_SCALE_STEP)
        elif key == pygame.K_F7:
            self._adjust_speed(-SPEED_SCALE_STEP)
        elif key == pygame.K_F8:
            self._adjust_speed(SPEED_SCALE_STEP)
        elif key == pygame.K_c:
            self._cycle_color_scheme()
        elif key == pygame.K_d:
            self._controls.toggle_mode_dropdown()
        elif key == pygame.K_m:
            self._toggle_reduce_motion()
        elif key == pygame.K_a:
            self._toggle_auto()
        elif key == pygame.K_n:
            self._shuffle_next()
        elif key == pygame.K_r:
            self._randomize_current_mode()
        elif pygame.K_1 <= key <= pygame.K_9:
            self._set_mode_index(min(key - pygame.K_1, len(self._mode_keys) - 1))

    def _relayout(self, size: tuple[int, int]) -> None:
        show = not self._fullscreen
        width = max(MIN_WINDOW_SIZE[0], int(size[0]))
        bar_h = self._controls.content_height(width) if show else 0
        self._layout = Layout.compute(size, show_control_bar=show, control_bar_height=bar_h)
        self._controls.relayout(self._layout.control_bar)
        self._visual.on_resize(self._layout.canvas.size)
        if self._transition is not None and self._transition.prev_visual is not None:
            self._transition.prev_visual.on_resize(self._layout.canvas.size)

    def _update(self, dt: float = 0.0) -> None:
        # Auto-cycle runs regardless of capture/silence (it's a visual choice).
        self._update_auto(dt)
        # Beat Buttons read the latest frame's onset; tick before the capture guard so
        # the baseline/cooldowns keep advancing (and decay) even while idle.
        self._update_beat(dt)
        if not self._capturing:
            return
        self._error = self._source.status is SourceStatus.ERROR
        if self._error:
            self._attempt_recovery(dt)
            self._frame = None
            return
        self._recover_timer = 0.0
        samples = self._source.read_latest(FFT_SIZE)
        if samples is None:
            self._frame = None
            return
        frame = self._analyzer.analyze(samples, self._source.sample_rate)
        if self._sensitivity != 1.0:
            bands = self._apply_sensitivity(frame.band_energies)
            frame = dataclasses.replace(frame, band_energies=bands)
        self._frame = frame

    def _apply_sensitivity(self, bands: NDArray[np.float32]) -> NDArray[np.float32]:
        """Scale band energies by Sensitivity, focused on ``self._sens_band``.

        ``all`` scales the whole spectrum (legacy); bass/mid/high scale only that
        third so the gain emphasizes one frequency range instead of everything.
        """
        if self._sens_band == "all":
            return np.clip(bands * self._sensitivity, 0.0, 1.0).astype(np.float32)
        n = bands.size
        third = max(1, n // 3)
        spans = {
            "bass": slice(0, third),
            "mid": slice(third, 2 * third),
            "high": slice(2 * third, n),
        }
        out = bands.copy()
        span = spans.get(self._sens_band, slice(0, 0))
        out[span] = np.clip(bands[span] * self._sensitivity, 0.0, 1.0)
        return out.astype(np.float32)

    def _draw(self, dt: float) -> None:
        screen = self._screen
        screen.fill(COLOR_BG)

        # Advance the shared hue phase so rainbow_plus cycles colors over time.
        self._theme.color_phase = (self._theme.color_phase + dt * COLOR_CYCLE_RATE) % 1.0

        # Track how long we've been silent so the idle banner only shows after a
        # short delay (brief track gaps shouldn't flash it). Never auto-quits.
        if self._capturing and (self._frame is None or self._frame.is_silent):
            self._silent_seconds += dt
        else:
            self._silent_seconds = 0.0

        canvas = self._layout.canvas
        try:
            sub = screen.subsurface(canvas)
            # The background layer is composited first, behind the active mode.
            self._background.draw(sub, self._frame, dt)
            # For a live cross-fade we need the freshly-drawn background to re-render
            # the *outgoing* mode onto; grab it before the new mode paints over it.
            live = self._transition is not None and self._transition.is_live
            bg_copy = sub.copy() if live else None
            self._visual.draw(sub, self._frame, dt)
            # The RenK logo is a global overlay: drawn over every mode's output.
            self._logo.draw(sub, self._frame, dt)
            # A shuffle switch fades the outgoing scene out over the live one.
            if self._transition is not None:
                self._draw_transition(sub, dt, bg_copy)
        except Exception:  # fail-soft: a broken mode must not crash the app
            logger.exception("Visual %r failed to draw", self._visual.KEY)

        if self._layout.show_control_bar:
            self._controls.set_state(
                self._capturing,
                self._visual.KEY,
                self._reduce_motion,
                self._theme.color_scheme,
                self._sensitivity,
                self._smoothing,
                self._theme.size_scale,
                self._theme.speed_scale,
                self._auto,
                self._locked_globals,
                self._sens_band,
            )
            self._controls.set_looks(self._looks_rows(), self._active_look_id)
            self._controls.set_history(self._history_pos + 1, len(self._history))
            self._controls.draw(screen, self._layout.control_bar, self._font)

        self._hud.draw(screen, canvas, self._hud_state(), self._font_small)
        self._draw_auto_status(screen, canvas)
        if self._beat_indicator and self._beat.any_enabled():
            draw_beat_indicator(
                screen,
                canvas,
                self._beat_indicator_pos,
                self._beat.intensity,
                self._beat.active_band,
                self._beat.flash,
            )
        if self._notice_visible():
            self._hud.draw_notice(screen, canvas, self._font, self._font_small)

        # Modals draw last so they sit above the canvas, controls, and HUD.
        self._logo_panel.set_state(self._logo_panel_values())
        self._logo_panel.draw(screen, canvas, self._font, self._font_small)
        self._appearance.set_state(self._appearance_values())
        self._appearance.draw(screen, canvas, self._font, self._font_small)
        self._background_panel.set_state(self._background_values())
        self._background_panel.draw(screen, canvas, self._font, self._font_small)
        self._source_panel.draw(screen, canvas, self._font, self._font_small)
        self._looks_panel.update(dt)
        self._looks_panel.draw(screen, canvas, self._font, self._font_small)
        self._shuffle_panel.set_state(
            self._shuffle_rows(),
            self._interval_label(),
            self._auto,
            self._auto_random_options,
            self._fade_label(),
        )
        self._shuffle_panel.draw(screen, canvas, self._font, self._font_small)
        self._about.draw(screen, canvas, self._font, self._font_small)
        self._hotkeys.draw(screen, canvas, self._font, self._font_small)
        self._beat_panel.draw(screen, canvas, self._font, self._font_small)

    def _draw_transition(
        self, sub: pygame.Surface, dt: float, bg_copy: pygame.Surface | None
    ) -> None:
        """Overlay the outgoing scene at a falling alpha (it fades away).

        Live cross-fade (``prev_visual``): re-render the outgoing mode + logo onto
        ``bg_copy`` (this frame's background) so it keeps animating, then blit it on
        top. Frozen dissolve (``snapshot``): blit the captured scene. The live (new)
        scene is already on ``sub``.
        """
        trans = self._transition
        if trans is None:
            return
        alpha = trans.overlay_alpha()
        if trans.prev_visual is not None and bg_copy is not None:
            try:
                trans.prev_visual.draw(bg_copy, self._frame, dt)
                self._logo.draw(bg_copy, self._frame, 0.0)  # 0 dt: don't double-spin
            except Exception:  # a dying mode must not crash the fade
                logger.exception("Outgoing visual failed mid cross-fade")
            bg_copy.set_alpha(alpha)
            sub.blit(bg_copy, (0, 0))
            return
        snapshot = trans.snapshot
        if snapshot is None:
            return
        if snapshot.get_size() != sub.get_size():
            snapshot = pygame.transform.smoothscale(snapshot, sub.get_size())
        snapshot.set_alpha(alpha)
        sub.blit(snapshot, (0, 0))

    def _current_item_label(self) -> str:
        """Human label for the item shuffle is currently showing (mode vs look)."""
        tag = self._auto_current
        if tag.startswith("look:"):
            look = self._looks_store.get(tag.removeprefix("look:"))
            return f"Look: {look.name}" if look is not None else "Look"
        return f"Mode: {self._visual.DISPLAY_NAME}"

    def _draw_auto_status(self, screen: pygame.Surface, canvas: pygame.Rect) -> None:
        """Small top-right chip naming the current item + countdown while shuffle runs."""
        if not self._auto or not self._valid_pool():
            return
        if self._transition is not None:
            tail = "switching\u2026"
        else:
            remaining = max(1, math.ceil(self._auto_interval - self._auto_elapsed))
            tail = f"next in {remaining}s"
        text = f"Auto \u00b7 {self._current_item_label()} \u00b7 {tail}"
        label = self._font_small.render(text, True, COLOR_TEXT_DIM)
        pad = 6
        box = pygame.Surface(
            (label.get_width() + pad * 2, label.get_height() + pad * 2), pygame.SRCALPHA
        )
        box.fill((*COLOR_BAR, 190))
        bx = canvas.right - box.get_width() - 10
        by = canvas.top + 10
        screen.blit(box, (bx, by))
        screen.blit(label, (bx + pad, by + pad))

    def _hud_state(self) -> HudState:
        idle = self._capturing and self._silent_seconds >= IDLE_BANNER_DELAY
        return HudState(
            device_name=self._source.device_name if self._capturing else "",
            mode_label=self._visual.DISPLAY_NAME,
            fps=self._clock.get_fps(),
            rms=self._frame.rms if self._frame else 0.0,
            peak=self._frame.peak if self._frame else 0.0,
            capturing=self._capturing,
            idle=idle,
            error=self._error,
        )

    def _attempt_recovery(self, dt: float) -> None:
        """After a capture/device error, periodically try to re-open the stream."""
        self._recover_timer += dt
        if self._recover_timer < DEVICE_RECOVER_INTERVAL:
            return
        self._recover_timer = 0.0
        logger.info("Attempting capture recovery after device error")
        self._source.stop()
        self._source.start()
        self._capturing = self._source.status is SourceStatus.RUNNING
        self._error = self._source.status is SourceStatus.ERROR

    def _current_settings(self) -> Settings:
        size = self._windowed_size if self._fullscreen else self._screen.get_size()
        return Settings(
            mode=self._mode_keys[self._mode_index],
            sensitivity=self._sensitivity,
            sens_band=self._sens_band,
            smoothing=self._smoothing,
            reduce_motion=self._reduce_motion,
            fullscreen=self._fullscreen,
            window_size=(int(size[0]), int(size[1])),
            notice_acknowledged=self._notice_acknowledged,
            size_scale=self._theme.size_scale,
            speed_scale=self._theme.speed_scale,
            color_scheme=self._theme.color_scheme,
            logo_enabled=self._logo.enabled,
            logo_size=self._logo.size_key,
            logo_position=self._logo.position,
            logo_opacity=self._logo.opacity,
            logo_color=self._logo.color_mode,
            logo_emit=self._logo.emit,
            logo_spin=self._logo.spin_dir,
            ui_style=self._ui_style,
            ui_font=self._ui_font,
            ui_accent=self._ui_accent,
            bg_mode=self._background.mode,
            bg_height=self._background.height_key,
            bg_sensitivity=self._background.sensitivity,
            bg_opacity=self._background.opacity,
            source_id=self._source_id,
            active_look=self._active_look_id,
            random_pool=self._ordered_pool_tags(),
            random_interval=self._auto_interval,
            random_options=self._auto_random_options,
            random_fade=self._auto_fade,
            beat_levels=self._beat.levels_dict(),
            beat_bands=self._beat.bands_dict(),
            beat_indicator=self._beat_indicator,
            beat_indicator_pos=self._beat_indicator_pos,
        )

    def _shutdown(self) -> None:
        try:
            self._source.stop()
            if self._persist:
                settings_mod.save(self._current_settings())
        finally:
            pygame.quit()
