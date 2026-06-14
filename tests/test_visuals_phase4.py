"""Phase 4: color helpers, theme-driven size/speed, and the waveform_2 mode."""

from __future__ import annotations

import numpy as np
import pygame
import pytest

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import PALETTE
from audio_visualizer.visuals._helpers import palette_color, rainbow_color, themed_color
from audio_visualizer.visuals.base import Theme
from audio_visualizer.visuals.particles_spiral import ParticlesSpiral
from audio_visualizer.visuals.waveform_2 import _POP_MAX_REDUCED, Waveform2


@pytest.fixture(scope="module", autouse=True)
def _pygame_ready():
    pygame.init()
    yield
    pygame.quit()


def _loud_frame() -> AnalysisFrame:
    wave = (0.6 * np.sin(np.linspace(0, 30, 2048))).astype(np.float32)
    return AnalysisFrame(
        waveform_mono=wave,
        band_energies=np.full(48, 0.6, dtype=np.float32),
        rms=0.5,
        peak=0.8,
        sample_rate=48000,
        timestamp=0.0,
        onset=1.0,
    )


def test_rainbow_color_varies_with_position() -> None:
    assert rainbow_color(0.0) != rainbow_color(0.33)
    assert all(0 <= c <= 255 for c in rainbow_color(0.7))


def test_themed_color_selects_scheme() -> None:
    assert themed_color("classic", 0.5, PALETTE) == palette_color(PALETTE, 0.5)
    assert themed_color("rainbow", 0.5, PALETTE) == rainbow_color(0.5)


def test_waveform2_deterministic_with_seed() -> None:
    surface = pygame.Surface((640, 360))
    frame = _loud_frame()
    runs = []
    for _ in range(2):
        v = Waveform2(seed=3)
        v.on_enter()
        for _ in range(20):
            v.draw(surface, frame, 0.01)
        runs.append([(round(p.x, 6), round(p.y, 6)) for p in v._pops])
    assert runs[0] == runs[1]
    assert len(runs[0]) > 0


def test_waveform2_reduce_motion_caps_count() -> None:
    surface = pygame.Surface((640, 360))
    frame = _loud_frame()
    v = Waveform2(reduce_motion=True, seed=1)
    v.on_enter()
    for _ in range(300):
        v.draw(surface, frame, 0.001)
    assert len(v._pops) <= _POP_MAX_REDUCED


def test_speed_scale_moves_spiral_further() -> None:
    surface = pygame.Surface((400, 400))
    frame = _loud_frame()
    slow = ParticlesSpiral(seed=5)
    slow.on_enter()
    slow.theme = Theme(speed_scale=1.0)
    fast = ParticlesSpiral(seed=5)
    fast.on_enter()
    fast.theme = Theme(speed_scale=2.0)
    for _ in range(15):
        slow.draw(surface, frame, 0.02)
        fast.draw(surface, frame, 0.02)
    assert max(s.r for s in fast._sparks) > max(s.r for s in slow._sparks)
