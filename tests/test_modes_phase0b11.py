"""Phase 0B-c (build 9): smooth waveforms, taller waves, bigger sparks + needle styles."""

from __future__ import annotations

import numpy as np
import pygame
import pytest

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.visuals import registry
from audio_visualizer.visuals._helpers import smooth_wave
from audio_visualizer.visuals.base import Theme


def _noisy_wave(n: int = 512) -> np.ndarray:
    rng = np.random.default_rng(7)
    base = np.sin(np.linspace(0, 6.28, n))
    return (base + rng.normal(0, 0.5, n)).astype(np.float32)


def _active_frame(wave: np.ndarray | None = None) -> AnalysisFrame:
    bands = np.linspace(0.2, 0.9, 48).astype(np.float32)
    wave = _noisy_wave() if wave is None else wave
    return AnalysisFrame(
        wave, bands, rms=0.5, peak=0.7, sample_rate=48000, timestamp=0.0, onset=1.0
    )


def test_smooth_wave_reduces_high_frequency_detail() -> None:
    noisy = _noisy_wave()
    smoothed = smooth_wave(noisy, 0.1)
    assert smoothed.shape == noisy.shape
    # Smoothing should cut the sample-to-sample variation (roughness).
    rough = float(np.abs(np.diff(noisy)).mean())
    soft = float(np.abs(np.diff(smoothed)).mean())
    assert soft < rough * 0.5


def test_smooth_wave_zero_amount_is_identity() -> None:
    noisy = _noisy_wave()
    np.testing.assert_array_equal(smooth_wave(noisy, 0.0), noisy)


def test_smooth_wave_circular_is_seamless() -> None:
    noisy = _noisy_wave()
    out = smooth_wave(noisy, 0.08, circular=True)
    # Ends wrap, so first and last samples stay close (no visible seam on a ring).
    assert abs(float(out[0] - out[-1])) < 0.5


def test_waveform_height_scales_trace() -> None:
    """A taller Height option pushes the trace further from the mid-line."""
    surface = pygame.Surface((320, 200))
    wave = np.linspace(-0.8, 0.8, 256).astype(np.float32)
    frame = _active_frame(wave)

    def _spread(height_index: int) -> int:
        visual = registry.create("waveform")
        visual.theme = Theme()
        visual.set_option_index("smooth", 0)  # Rough
        visual.set_option_index("particles", 0)
        visual.set_option_index("mirror", 0)
        visual.set_option_index("height", height_index)
        surface.fill((0, 0, 0))
        visual.draw(surface, frame, 0.05)
        cols = pygame.surfarray.array3d(surface).sum(axis=2)
        ys = np.argwhere(cols > 0)[:, 1]
        return int(ys.max() - ys.min()) if ys.size else 0

    assert _spread(2) > _spread(1) > 0  # Tall spreads more than Normal


@pytest.mark.parametrize("smooth_index", [0, 1, 2, 3])
def test_waveform_modes_render_with_smoothing(smooth_index: int) -> None:
    for key in ("waveform", "waveform_circle"):
        visual = registry.create(key)
        visual.theme = Theme()
        visual.on_enter()
        visual.set_option_index("smooth", smooth_index)
        surface = pygame.Surface((320, 200))
        visual.draw(surface, _active_frame(), 0.05)


@pytest.mark.parametrize("needle_index", [0, 1, 2, 3, 4])
def test_meters_needle_styles_render(needle_index: int) -> None:
    from audio_visualizer.visuals.meters import Meters

    visual = Meters()
    visual.theme = Theme()
    visual.on_enter()
    visual.set_option_index("style", 2)  # Needle
    visual.set_option_index("needle", needle_index)
    surface = pygame.Surface((400, 300))
    for _ in range(4):
        visual.draw(surface, _active_frame(), 0.05)
    assert sum(pygame.transform.average_color(surface)[:3]) > 0


@pytest.mark.parametrize("spark_index", [3, 4, 5])
def test_meters_bigger_sparks_render(spark_index: int) -> None:
    from audio_visualizer.visuals.meters import Meters

    visual = Meters()
    visual.theme = Theme()
    visual.on_enter()
    visual.set_option_index("spark", spark_index)  # Big / Huge / Max
    surface = pygame.Surface((400, 300))
    for _ in range(8):
        visual.draw(surface, _active_frame(), 0.05)
    assert sum(pygame.transform.average_color(surface)[:3]) > 0
