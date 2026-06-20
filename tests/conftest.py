"""Shared pytest fixtures + helpers (headless SDL, one pygame session, frames).

Every test runs headless: SDL drivers are forced to ``dummy`` *before* pygame is
imported anywhere. A single session-scoped fixture initializes pygame (+ a dummy
display and the visual registry) once and tears it down at the end, so individual
test modules no longer each init/quit pygame. A ``make_frame`` factory builds
``AnalysisFrame`` instances without every module rolling its own.
"""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from collections.abc import Callable

import numpy as np
import pytest

from audio_visualizer.audio.frame import AnalysisFrame

FrameFactory = Callable[..., AnalysisFrame]


@pytest.fixture(scope="module", autouse=True)
def _pygame_ready():
    """Init pygame + a dummy display + the visual registry for each test module.

    Module-scoped so any test module gets a ready pygame without declaring its
    own fixture; ``registry.discover()`` is idempotent so calling it here is safe.
    """
    import pygame

    from audio_visualizer.visuals import registry

    pygame.init()
    pygame.display.set_mode((10, 10))
    registry.discover()
    yield
    pygame.quit()


@pytest.fixture
def make_frame() -> FrameFactory:
    """Factory for ``AnalysisFrame`` with sensible, overridable defaults."""

    def _make(
        bands: int = 48,
        level: float = 0.4,
        *,
        rms: float | None = None,
        peak: float | None = None,
        onset: float = 0.0,
        sample_rate: int = 48000,
        waveform: np.ndarray | None = None,
    ) -> AnalysisFrame:
        if waveform is None:
            waveform = np.sin(np.linspace(0.0, 6.28, 256)).astype(np.float32)
        return AnalysisFrame(
            waveform_mono=waveform.astype(np.float32),
            band_energies=np.full(bands, level, dtype=np.float32),
            rms=level if rms is None else rms,
            peak=level if peak is None else peak,
            sample_rate=sample_rate,
            timestamp=0.0,
            onset=onset,
        )

    return _make
