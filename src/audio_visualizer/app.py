"""The App: owns the window + main loop and wires audio, analysis, visuals, UI.

Business logic lives in ``audio/``, ``visuals/``, and ``ui/``; this module is
the wiring (events, resize, fullscreen, mode switching, drawing order).
"""

from __future__ import annotations

import dataclasses
import logging
from typing import TypeVar

import numpy as np
import pygame

from audio_visualizer import settings as settings_mod
from audio_visualizer.audio.analysis import Analyzer
from audio_visualizer.audio.capture import LoopbackSource
from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.audio.source import AudioSource, SourceStatus, SyntheticSource
from audio_visualizer.config import (
    APP_ICON_FILENAME,
    APP_NAME,
    APP_VERSION,
    COLOR_BG,
    COLOR_CYCLE_RATE,
    COLOR_SCHEMES,
    DEVICE_RECOVER_INTERVAL,
    FFT_SIZE,
    IDLE_BANNER_DELAY,
    LOGO_COLOR_LABELS,
    LOGO_COLOR_MODES,
    LOGO_FILENAME,
    LOGO_OPACITIES,
    LOGO_POSITION_LABELS,
    LOGO_POSITIONS,
    LOGO_SIZE_LABELS,
    LOGO_SIZES,
    MIN_WINDOW_SIZE,
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
    UI_FONT_LABELS,
    UI_FONTS,
    UI_STYLE_LABELS,
    UI_STYLES,
)
from audio_visualizer.resources import asset_path
from audio_visualizer.settings import Settings
from audio_visualizer.ui.about import AboutDialog
from audio_visualizer.ui.appearance_panel import AppearanceActions, AppearancePanel
from audio_visualizer.ui.controls import ControlActions, ControlBar, OptionSpec
from audio_visualizer.ui.fonts import get_ui_fonts
from audio_visualizer.ui.hud import Hud, HudState
from audio_visualizer.ui.layout import Layout
from audio_visualizer.ui.logo_panel import LogoPanel, LogoPanelActions
from audio_visualizer.ui.style import STYLE
from audio_visualizer.visuals import registry
from audio_visualizer.visuals.base import BaseVisualizer, Theme
from audio_visualizer.visuals.logo import RenkLogo

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


def _smoothing_to_coeffs(level: float) -> tuple[float, float]:
    """Map a 0..1 smoothing level to (attack, release) coefficients.

    Linearly interpolates between the "snappy" endpoints (level 0) and the
    "smooth" endpoints (level 1). Higher level -> slower release -> calmer visuals.
    """
    level = float(np.clip(level, 0.0, 1.0))
    attack = SMOOTHING_ATTACK_AT_0 + (SMOOTHING_ATTACK_AT_1 - SMOOTHING_ATTACK_AT_0) * level
    release = SMOOTHING_RELEASE_AT_0 + (SMOOTHING_RELEASE_AT_1 - SMOOTHING_RELEASE_AT_0) * level
    return attack, release


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
        STYLE.set_style(self._ui_style)

        registry.discover()
        self._mode_keys = registry.keys()
        if not self._mode_keys:
            raise RuntimeError("No visual modes registered")
        self._mode_index = self._resolve_start_index(start_mode or self._settings.mode or None)

        self._sensitivity = float(
            np.clip(self._settings.sensitivity, SENSITIVITY_MIN, SENSITIVITY_MAX)
        )
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

        self._source: AudioSource = LoopbackSource()
        self._analyzer = Analyzer()
        self._analyzer.set_smoothing(*_smoothing_to_coeffs(self._smoothing))
        self._frame: AnalysisFrame | None = None
        self._capturing = False
        self._error = False
        self._recover_timer = 0.0
        self._silent_seconds = 0.0  # how long the signal has been silent

        self._visual: BaseVisualizer = self._make_visual()
        self._visual.on_enter()

        self._logo = RenkLogo(reduce_motion=self._reduce_motion, theme=self._theme)
        self._apply_logo_settings()
        self._logo_panel = LogoPanel(self._build_logo_panel_actions())
        self._appearance = AppearancePanel(self._build_appearance_actions())
        self._about = AboutDialog()

        self._hud = Hud()
        self._controls = ControlBar(self._build_actions(), registry.options())
        self._refresh_mode_options()  # populates option dropdowns + lays out the bar

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
        )

    def _build_appearance_actions(self) -> AppearanceActions:
        return AppearanceActions(
            cycle_style=self._cycle_ui_style,
            cycle_font=self._cycle_ui_font,
        )

    def _build_logo_panel_actions(self) -> LogoPanelActions:
        return LogoPanelActions(
            toggle_enabled=self._toggle_logo_enabled,
            cycle_color=self._cycle_logo_color,
            cycle_opacity=self._cycle_logo_opacity,
            cycle_size=self._cycle_logo_size,
            cycle_position=self._cycle_logo_position,
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

    def _cycle_mode(self, delta: int) -> None:
        self._set_mode_index((self._mode_index + delta) % len(self._mode_keys))

    def _set_mode_key(self, key: str) -> None:
        if key in self._mode_keys:
            self._set_mode_index(self._mode_keys.index(key))

    def _set_mode_index(self, index: int) -> None:
        if index == self._mode_index:
            return
        self._mode_index = index
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

    def _appearance_values(self) -> dict[str, str]:
        """Human-readable current values for the Appearance panel rows."""
        return {
            "style": UI_STYLE_LABELS.get(self._ui_style, self._ui_style),
            "font": UI_FONT_LABELS.get(self._ui_font, self._ui_font),
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
        return self._logo_panel.open or self._about.open or self._appearance.open

    def _close_modals(self) -> None:
        self._logo_panel.open = False
        self._about.open = False
        self._appearance.open = False

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
                    self._about.handle_event(event, canvas)
                continue
            if event.type == pygame.VIDEORESIZE and not self._fullscreen:
                size = (max(MIN_WINDOW_SIZE[0], event.w), max(MIN_WINDOW_SIZE[1], event.h))
                self._screen = pygame.display.set_mode(size, pygame.RESIZABLE)
                self._relayout(size)
            elif event.type == pygame.KEYDOWN:
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
        elif pygame.K_1 <= key <= pygame.K_9:
            self._set_mode_index(min(key - pygame.K_1, len(self._mode_keys) - 1))

    def _relayout(self, size: tuple[int, int]) -> None:
        show = not self._fullscreen
        width = max(MIN_WINDOW_SIZE[0], int(size[0]))
        bar_h = self._controls.content_height(width) if show else 0
        self._layout = Layout.compute(size, show_control_bar=show, control_bar_height=bar_h)
        self._controls.relayout(self._layout.control_bar)
        self._visual.on_resize(self._layout.canvas.size)

    def _update(self, dt: float = 0.0) -> None:
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
            bands = np.clip(frame.band_energies * self._sensitivity, 0.0, 1.0)
            frame = dataclasses.replace(frame, band_energies=bands.astype(np.float32))
        self._frame = frame

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
            self._visual.draw(sub, self._frame, dt)
            # The RenK logo is a global overlay: drawn over every mode's output.
            self._logo.draw(sub, self._frame, dt)
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
            )
            self._controls.draw(screen, self._layout.control_bar, self._font)

        self._hud.draw(screen, canvas, self._hud_state(), self._font_small)
        if self._notice_visible():
            self._hud.draw_notice(screen, canvas, self._font, self._font_small)

        # Modals draw last so they sit above the canvas, controls, and HUD.
        self._logo_panel.set_state(self._logo_panel_values())
        self._logo_panel.draw(screen, canvas, self._font, self._font_small)
        self._appearance.set_state(self._appearance_values())
        self._appearance.draw(screen, canvas, self._font, self._font_small)
        self._about.draw(screen, canvas, self._font, self._font_small)

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
            ui_style=self._ui_style,
            ui_font=self._ui_font,
        )

    def _shutdown(self) -> None:
        try:
            self._source.stop()
            if self._persist:
                settings_mod.save(self._current_settings())
        finally:
            pygame.quit()
