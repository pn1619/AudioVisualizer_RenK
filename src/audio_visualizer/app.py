"""The App: owns the window + main loop and wires audio, analysis, visuals, UI.

Business logic lives in ``audio/``, ``visuals/``, and ``ui/``; this module is
the wiring (events, resize, fullscreen, mode switching, drawing order).
"""

from __future__ import annotations

import dataclasses
import logging

import numpy as np
import pygame

from audio_visualizer.audio.analysis import Analyzer
from audio_visualizer.audio.capture import LoopbackSource
from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.audio.source import AudioSource, SourceStatus, SyntheticSource
from audio_visualizer.config import (
    APP_NAME,
    APP_VERSION,
    COLOR_BG,
    DEFAULT_WINDOW_SIZE,
    FFT_SIZE,
    MIN_WINDOW_SIZE,
    SMOOTHING_DEFAULT,
    SMOOTHING_STEP,
    TARGET_FPS,
)
from audio_visualizer.ui.controls import ControlActions, ControlBar
from audio_visualizer.ui.hud import Hud, HudState
from audio_visualizer.ui.layout import Layout
from audio_visualizer.visuals import registry
from audio_visualizer.visuals.base import BaseVisualizer

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

    def __init__(self, start_mode: str | None = None) -> None:
        pygame.init()
        pygame.display.set_caption(f"{APP_NAME} {APP_VERSION}")

        registry.discover()
        self._mode_keys = registry.keys()
        if not self._mode_keys:
            raise RuntimeError("No visual modes registered")
        self._mode_index = self._resolve_start_index(start_mode)

        self._screen = pygame.display.set_mode(DEFAULT_WINDOW_SIZE, pygame.RESIZABLE)
        self._font = pygame.font.Font(None, 22)
        self._font_small = pygame.font.Font(None, 20)
        self._clock = pygame.time.Clock()

        self._fullscreen = False
        self._windowed_size = DEFAULT_WINDOW_SIZE
        self._sensitivity = 1.0
        self._reduce_motion = False
        self._smoothing = SMOOTHING_DEFAULT
        self._notice_acknowledged = False

        self._source: AudioSource = LoopbackSource()
        self._analyzer = Analyzer()
        self._analyzer.set_smoothing(*_smoothing_to_coeffs(self._smoothing))
        self._frame: AnalysisFrame | None = None
        self._capturing = False
        self._error = False

        self._visual: BaseVisualizer = self._make_visual()
        self._visual.on_enter()

        self._hud = Hud()
        self._controls = ControlBar(self._build_actions())
        self._layout = Layout.compute(self._screen.get_size())
        self._controls.relayout(self._layout.control_bar)

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
        return registry.create(key, reduce_motion=self._reduce_motion)

    def _build_actions(self) -> ControlActions:
        return ControlActions(
            toggle_capture=self._toggle_capture,
            prev_mode=lambda: self._cycle_mode(-1),
            next_mode=lambda: self._cycle_mode(1),
            sensitivity_down=lambda: self._adjust_sensitivity(-_SENS_STEP),
            sensitivity_up=lambda: self._adjust_sensitivity(_SENS_STEP),
            smoothing_down=lambda: self._adjust_smoothing(-SMOOTHING_STEP),
            smoothing_up=lambda: self._adjust_smoothing(SMOOTHING_STEP),
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
                self._update()
                self._draw(dt)
                pygame.display.flip()
        finally:
            self._shutdown()
        return 0

    def run_selftest(self, frames: int) -> int:
        """Headless: render ``frames`` with a synthetic tone, then exit 0."""
        self._source = SyntheticSource(mode="sweep", sample_rate=48000)
        self._start_capture()
        try:
            for _ in range(max(1, frames)):
                dt = self._clock.tick(TARGET_FPS) / 1000.0
                pygame.event.pump()
                self._update()
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

    def _set_mode_index(self, index: int) -> None:
        if index == self._mode_index:
            return
        self._mode_index = index
        self._visual.on_exit()
        self._visual = self._make_visual()
        self._visual.on_resize(self._layout.canvas.size)
        self._visual.on_enter()

    def _adjust_sensitivity(self, delta: float) -> None:
        self._sensitivity = float(np.clip(self._sensitivity + delta, _SENS_MIN, _SENS_MAX))
        logger.debug("Sensitivity = %.2f", self._sensitivity)

    def _adjust_smoothing(self, delta: float) -> None:
        self._smoothing = float(np.clip(self._smoothing + delta, 0.0, 1.0))
        self._analyzer.set_smoothing(*_smoothing_to_coeffs(self._smoothing))
        logger.debug("Smoothing = %.2f", self._smoothing)

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
        elif key == pygame.K_m:
            self._toggle_reduce_motion()
        elif pygame.K_1 <= key <= pygame.K_9:
            self._set_mode_index(min(key - pygame.K_1, len(self._mode_keys) - 1))

    def _relayout(self, size: tuple[int, int]) -> None:
        self._layout = Layout.compute(size, show_control_bar=not self._fullscreen)
        self._controls.relayout(self._layout.control_bar)
        self._visual.on_resize(self._layout.canvas.size)

    def _update(self) -> None:
        if not self._capturing:
            return
        self._error = self._source.status is SourceStatus.ERROR
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

        canvas = self._layout.canvas
        try:
            sub = screen.subsurface(canvas)
            self._visual.draw(sub, self._frame, dt)
        except Exception:  # fail-soft: a broken mode must not crash the app
            logger.exception("Visual %r failed to draw", self._visual.KEY)

        if self._layout.show_control_bar:
            self._controls.set_state(
                self._capturing, self._visual.DISPLAY_NAME, self._reduce_motion
            )
            self._controls.draw(screen, self._layout.control_bar, self._font)

        self._hud.draw(screen, canvas, self._hud_state(), self._font_small)
        if self._notice_visible():
            self._hud.draw_notice(screen, canvas, self._font, self._font_small)

    def _hud_state(self) -> HudState:
        idle = self._capturing and (self._frame is None or self._frame.is_silent)
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

    def _shutdown(self) -> None:
        try:
            self._source.stop()
        finally:
            pygame.quit()
