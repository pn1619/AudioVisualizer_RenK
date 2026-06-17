"""Phase 10.02: the six new visual modes render (idle + active) without crashing."""

from __future__ import annotations

import numpy as np
import pygame
import pytest

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.visuals import registry
from audio_visualizer.visuals.base import Theme

_NEW_MODES = ("spectrogram", "radial_spectrum", "plasma", "tunnel", "fireworks", "kaleidoscope")
# These fill the canvas every frame, so an active frame must paint something.
_FILLING = {"spectrogram", "plasma"}


@pytest.fixture(scope="module", autouse=True)
def _pygame_ready():
    pygame.init()
    pygame.display.set_mode((10, 10))
    registry.discover()
    yield
    pygame.quit()


def _active_frame() -> AnalysisFrame:
    bands = np.linspace(0.2, 0.9, 48).astype(np.float32)
    wave = np.sin(np.linspace(0, 12, 256)).astype(np.float32) * 0.6
    return AnalysisFrame(
        wave, bands, rms=0.5, peak=0.7, sample_rate=48000, timestamp=0.0, onset=1.0
    )


def _silent_frame() -> AnalysisFrame:
    return AnalysisFrame(
        np.zeros(256, np.float32), np.zeros(48, np.float32), 0.0, 0.0, 48000, 0.0, 0.0
    )


@pytest.mark.parametrize("key", _NEW_MODES)
@pytest.mark.parametrize("reduce_motion", [False, True])
def test_new_mode_renders(key: str, reduce_motion: bool) -> None:
    assert key in registry.keys(), f"{key} not registered"
    visual = registry.create(key, reduce_motion=reduce_motion)
    visual.theme = Theme()
    surface = pygame.Surface((320, 200))
    visual.on_enter()

    # Idle (None) and silent frames must be safe.
    visual.draw(surface, None, 0.05)
    visual.draw(surface, _silent_frame(), 0.05)

    # Active frames across several ticks exercise spawn/advance/scroll paths.
    surface.fill((0, 0, 0))
    frame = _active_frame()
    for _ in range(12):
        visual.draw(surface, frame, 0.05)

    if key in _FILLING:
        nonblack = pygame.transform.average_color(surface)[:3]
        assert sum(nonblack) > 0, f"{key} drew nothing on an active frame"
