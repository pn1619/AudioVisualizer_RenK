"""Headless smoke test: the App builds and renders frames without crashing."""

from __future__ import annotations

import pygame

from audio_visualizer.app import App
from audio_visualizer.audio.source import SyntheticSource


def _run_frames(app: App, n: int) -> None:
    clock = pygame.time.Clock()
    for _ in range(n):
        dt = clock.tick(0) / 1000.0
        pygame.event.pump()
        app._update()
        app._draw(dt)


def test_app_constructs_and_renders() -> None:
    app = App()
    try:
        app._source = SyntheticSource(mode="sweep")
        app._start_capture()
        _run_frames(app, 10)
    finally:
        app._shutdown()


def test_app_renders_idle_when_silent() -> None:
    app = App()
    try:
        app._source = SyntheticSource(mode="silence")
        app._start_capture()
        _run_frames(app, 5)
        state = app._hud_state()
        assert state.idle is True
    finally:
        app._shutdown()


def test_app_cycles_all_modes() -> None:
    app = App()
    try:
        app._source = SyntheticSource(mode="sweep")
        app._start_capture()
        assert len(app._mode_keys) >= 5
        for _ in range(len(app._mode_keys)):
            _run_frames(app, 2)
            app._cycle_mode(1)
    finally:
        app._shutdown()


def test_selftest_entry_point_returns_zero() -> None:
    app = App()
    assert app.run_selftest(5) == 0
