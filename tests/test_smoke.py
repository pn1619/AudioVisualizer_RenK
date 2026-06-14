"""Headless smoke test: the App builds and renders frames without crashing."""

from __future__ import annotations

import numpy as np
import pygame

from audio_visualizer.app import App
from audio_visualizer.audio.source import SourceStatus, SyntheticSource
from audio_visualizer.config import DEVICE_RECOVER_INTERVAL


class _StubSource:
    """Minimal AudioSource whose start() always succeeds (for recovery tests)."""

    def __init__(self) -> None:
        self.sample_rate = 48000
        self.channels = 1
        self.device_name = "Stub"
        self.status = SourceStatus.STOPPED
        self.start_calls = 0

    def start(self) -> None:
        self.start_calls += 1
        self.status = SourceStatus.RUNNING

    def stop(self) -> None:
        self.status = SourceStatus.STOPPED

    def read_latest(self, n: int):
        if self.status is not SourceStatus.RUNNING:
            return None
        return np.zeros(int(n), dtype=np.float32)


def _run_frames(app: App, n: int) -> None:
    clock = pygame.time.Clock()
    for _ in range(n):
        dt = clock.tick(0) / 1000.0
        pygame.event.pump()
        app._update()
        app._draw(dt)


def test_app_constructs_and_renders() -> None:
    app = App(load_settings=False)
    try:
        app._source = SyntheticSource(mode="sweep")
        app._start_capture()
        _run_frames(app, 10)
    finally:
        app._shutdown()


def test_app_renders_idle_when_silent() -> None:
    app = App(load_settings=False)
    try:
        app._source = SyntheticSource(mode="silence")
        app._start_capture()
        _run_frames(app, 5)
        state = app._hud_state()
        assert state.idle is True
    finally:
        app._shutdown()


def test_app_cycles_all_modes() -> None:
    app = App(load_settings=False)
    try:
        app._source = SyntheticSource(mode="sweep")
        app._start_capture()
        assert len(app._mode_keys) >= 8
        for _ in range(len(app._mode_keys)):
            _run_frames(app, 2)
            app._cycle_mode(1)
    finally:
        app._shutdown()


def test_app_recovers_from_device_error() -> None:
    app = App(load_settings=False)
    try:
        src = _StubSource()
        app._source = src
        app._start_capture()  # RUNNING, capturing
        assert app._capturing is True
        src.status = SourceStatus.ERROR  # simulate device loss mid-run
        app._update(0.0)  # detect error, start the recovery clock
        assert app._error is True
        app._update(DEVICE_RECOVER_INTERVAL + 0.01)  # clock elapses -> re-open
        assert src.start_calls >= 2
        assert app._capturing is True
        assert app._error is False
    finally:
        app._shutdown()


def test_app_shares_live_theme_with_visual() -> None:
    app = App(load_settings=False)
    try:
        assert app._visual.theme is app._theme
        before = app._theme.size_scale
        app._adjust_size(0.25)
        assert app._theme.size_scale != before
        scheme0 = app._theme.color_scheme
        app._cycle_color_scheme()
        assert app._theme.color_scheme != scheme0
        # Switching modes keeps the same shared theme reference.
        app._cycle_mode(1)
        assert app._visual.theme is app._theme
    finally:
        app._shutdown()


def test_selftest_entry_point_returns_zero() -> None:
    app = App(load_settings=False)
    assert app.run_selftest(5) == 0
