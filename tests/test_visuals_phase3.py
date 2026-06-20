"""Phase 3 modes: snowfall + spiral determinism and reduce-motion behavior."""

from __future__ import annotations

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import (
    SNOW_FLAKES,
    SNOW_FLAKES_REDUCED,
    SPIRAL_MAX_REDUCED,
)
from audio_visualizer.visuals.particles import Particles
from audio_visualizer.visuals.snowfall import Snowfall


def _spiral(**kwargs) -> Particles:
    """A Particles mode switched to its Spiral emitter (the old ParticlesSpiral)."""
    v = Particles(**kwargs)
    v.on_enter()
    v.set_option_index("emitter", 1)  # Spiral
    return v


def _loud_frame() -> AnalysisFrame:
    return AnalysisFrame(
        waveform_mono=np.zeros(8, dtype=np.float32),
        band_energies=np.full(48, 0.6, dtype=np.float32),
        rms=0.5,
        peak=0.8,
        sample_rate=48000,
        timestamp=0.0,
        onset=1.0,
    )


def test_snowfall_reduce_motion_uses_fewer_flakes() -> None:
    full = Snowfall(reduce_motion=False)
    full.on_enter()
    reduced = Snowfall(reduce_motion=True)
    reduced.on_enter()
    assert full._x.size == SNOW_FLAKES
    assert reduced._x.size == SNOW_FLAKES_REDUCED
    assert reduced._x.size < full._x.size


def test_snowfall_deterministic_with_seed() -> None:
    a = Snowfall(seed=5)
    a.on_enter()
    b = Snowfall(seed=5)
    b.on_enter()
    assert np.array_equal(a._x, b._x)
    assert np.array_equal(a._y, b._y)


def test_snowfall_draws_idle_without_frame() -> None:
    surface = pygame.Surface((640, 360))
    snow = Snowfall(seed=1)
    snow.on_enter()
    snow.draw(surface, None, 0.016)  # no audio -> gentle fall, no error


def test_spiral_deterministic_with_seed() -> None:
    surface = pygame.Surface((640, 360))
    frame = _loud_frame()
    runs = []
    for _ in range(2):
        p = _spiral(seed=9)
        for _ in range(20):
            p.draw(surface, frame, 0.01)
        runs.append([(round(s.r, 6), round(s.theta, 6)) for s in p._sparks])
    assert runs[0] == runs[1]
    assert len(runs[0]) > 0


def test_spiral_reduce_motion_caps_count() -> None:
    surface = pygame.Surface((640, 360))
    frame = _loud_frame()
    p = _spiral(reduce_motion=True, seed=1)
    for _ in range(300):
        p.draw(surface, frame, 0.001)
    assert len(p._sparks) <= SPIRAL_MAX_REDUCED
