"""Every registered mode renders at several sizes without error, incl. None frame."""

from __future__ import annotations

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.visuals import registry

_SIZES = [(640, 360), (1280, 720), (50, 40)]


def _frame(bands: int = 48, rms: float = 0.4) -> AnalysisFrame:
    return AnalysisFrame(
        waveform_mono=(0.3 * np.sin(np.linspace(0, 20, 2048))).astype(np.float32),
        band_energies=np.linspace(0, 1, bands).astype(np.float32),
        rms=rms,
        peak=0.7,
        sample_rate=48000,
        timestamp=0.0,
    )


def test_each_mode_draws_across_sizes() -> None:
    registry.discover()
    keys = registry.keys()
    assert keys, "no visual modes discovered"
    for key in keys:
        visual = registry.create(key)
        visual.on_enter()
        for size in _SIZES:
            surface = pygame.Surface(size)
            visual.on_resize(size)
            visual.draw(surface, _frame(), 0.016)  # normal frame
            visual.draw(surface, None, 0.016)  # idle / no data
        visual.on_exit()
