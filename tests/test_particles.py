"""Particles mode: deterministic under a fixed seed; reduce-motion caps count."""

from __future__ import annotations

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import PARTICLE_MAX_REDUCED
from audio_visualizer.visuals.particles import Particles


def _onset_frame() -> AnalysisFrame:
    return AnalysisFrame(
        waveform_mono=np.zeros(8, dtype=np.float32),
        band_energies=np.full(48, 0.6, dtype=np.float32),
        rms=0.5,
        peak=0.8,
        sample_rate=48000,
        timestamp=0.0,
        onset=1.0,
    )


def test_particles_deterministic_with_seed() -> None:
    surface = pygame.Surface((640, 360))
    frame = _onset_frame()
    runs = []
    for _ in range(2):
        p = Particles(seed=7)
        p.on_enter()
        for _ in range(20):
            p.draw(surface, frame, 0.01)
        runs.append([(round(part.x, 6), round(part.y, 6)) for part in p._particles])
    assert runs[0] == runs[1]
    assert len(runs[0]) > 0


def test_reduce_motion_caps_particle_count() -> None:
    surface = pygame.Surface((640, 360))
    frame = _onset_frame()
    p = Particles(reduce_motion=True, seed=1)
    p.on_enter()
    for _ in range(200):
        p.draw(surface, frame, 0.001)  # tiny dt so particles accumulate
    assert len(p._particles) <= PARTICLE_MAX_REDUCED
