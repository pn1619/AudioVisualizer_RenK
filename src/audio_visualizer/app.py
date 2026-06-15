"""The App: owns the window + main loop and wires audio, analysis, visuals, UI.

Business logic lives in ``audio/``, ``visuals/``, and ``ui/``; this module is
the wiring (events, resize, fullscreen, mode switching, drawing order).
"""

from __future__ import annotations

import dataclasses
import logging

import numpy as np
import pygame

from audio_visualizer import settings as settings_mod
from audio_visualizer.audio.analysis import Analyzer
from audio_visualizer.audio.capture import LoopbackSource
from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.audio.source import AudioSource, SourceStatus, SyntheticSource
from audio_visualizer.config import (
    APP_NAME,
    APP_VERSION,
    COLOR_BG,
    COLOR_CYCLE_RATE,
    COLOR_SCHEMES,
    DEVICE_RECOVER_INTERVAL,
    FFT_SIZE,
    IDLE_BANNER_DELAY,
    MIN_WINDOW_SIZE,
    SIZE_SCALE_MAX,
    SIZE_SCALE_MIN,
    SIZE_SCALE_STEP,
    SMOOTHING_STEP,
    SPEED_SCALE_MAX,
    SPEED_SCALE_MIN,
    SPEED_SCALE_STEP,
    TARGET_FPS,
)
from audio_visualizer.settings import Settings
from audio_visualizer.ui.controls import ControlActions, ControlBar, OptionSpec
from audio_visualizer.ui.hud import Hud, HudState
from audio_visualizer.ui.layout import Layout
from audio_visualizer.visuals import registry
from audio_visualizer.visuals.base import BaseVisualizer, Theme

logger = logging.getLogger(__name__)

_SENS_MIN, _SENS_MAX, _SENS_STEP = 0.25, 4.0, 0.25


def _smoothing_to_coeffs(level: float) -> tuple[float, float]:
    """Map a 0..1 smoothing level to (attack, release) coefficients.

    Higher level -> slower release -> smoother, calmer visuals.
    """
    level = float(np.clip(level, 0.0, 1.0))
    attack = 0.85 + (0.35 - 0.85) * level
    release = 0.35 + (0.04 - 0.35) * level
    return attack, release


class App:
    """The application window and main loop."""

    def __init__(self, start_mode: str | None = None, load_settings: bool = True) -> None:
        pygame.init()
        pygame.display.set_caption(f"{APP_NAME} {APP_VERSION}")

        self._settings: Settings = settings_mod.load() if load_settings else Settings()
        self._persist = load_settings

        registry.discover()
        self._mode_keys = registry.keys()
        if not self._mode_keys:
            raise RuntimeError("No visual modes registered")
        self._mode_index = self._resolve_start_index(start_mode or self._settings.mode or None)

        self._sensitivity = float(np.clip(self._settings.sensitivity, _SENS_MIN, _SENS_MAX))
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

        self._font = pygame.font.Font(None, 22)
        self._font_small = pygame.font.Font(None, 20)
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

        self._hud = Hud()
        self._controls = ControlBar(self._build_actions(), registry.options())
        self._layout = Layout.compute(
            self._screen.get_size(), show_control_bar=not self._fullscreen
        )
        self._controls.relayout(self._layout.control_bar)
        self._refresh_mode_options()

        self._running = False

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
            sensitivity_down=lambda: self._adjust_sensitivity(-_SENS_STEP),
            sensitivity_up=lambda: self._adjust_sensitivity(_SENS_STEP),
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
            toggle_fullscreen=self._toggle_fullscreen,
            quit=self._request_quit,
        )

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

    def _set_mode_option(self, key: str, index: int) -> None:
        self._visual.set_option_index(key, index)
        logger.debug("Mode %s option %s = %d", self._visual.KEY, key, index)

    def _adjust_sensitivity(self, delta: float) -> None:
        self._sensitivity = float(np.clip(self._sensitivity + delta, _SENS_MIN, _SENS_MAX))
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
        logger.debug("Reduce motion = %s", self._reduce_motion)

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
            if self._fullscreen:
                self._toggle_fullscreen()
            else:
                self._running = False
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
            self._adjust_sensitivity(-_SENS_STEP)
        elif key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            self._adjust_sensitivity(_SENS_STEP)
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
        self._layout = Layout.compute(size, show_control_bar=not self._fullscreen)
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
        )

    def _shutdown(self) -> None:
        try:
            self._source.stop()
            if self._persist:
                settings_mod.save(self._current_settings())
        finally:
            pygame.quit()
