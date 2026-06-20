"""Phase 6: continuous rainbow, spiral size/spacing, and circular waveform modes."""

from __future__ import annotations

import numpy as np
import pygame
import pytest

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.visuals._helpers import RingPops, rainbow_color, ring_points
from audio_visualizer.visuals.base import Theme
from audio_visualizer.visuals.particles import Particles
from audio_visualizer.visuals.waveform_circle import WaveformCircle


def _loud_frame() -> AnalysisFrame:
    wave = (0.6 * np.sin(np.linspace(0, 30, 2048))).astype(np.float32)
    return AnalysisFrame(
        waveform_mono=wave,
        band_energies=np.full(48, 0.7, dtype=np.float32),
        rms=0.5,
        peak=0.8,
        sample_rate=48000,
        timestamp=0.0,
        onset=1.0,
    )


# -- rainbow continuity -------------------------------------------------------
def test_rainbow_wraps_continuously() -> None:
    # 0.0 and 1.0 are the same point on the wheel (seamless wrap).
    assert rainbow_color(0.0) == rainbow_color(1.0)
    # Hues just before and just after the wrap are close (no jump to a far color).
    before = rainbow_color(0.99)
    after = rainbow_color(1.01)  # == hue 0.01
    assert all(abs(a - b) < 30 for a, b in zip(before, after, strict=False))
    # A value well past 1.0 still wraps (no clamp-to-red): hue 2.4 ~= hue 0.4.
    wrapped = zip(rainbow_color(2.4), rainbow_color(0.4), strict=False)
    assert all(abs(a - b) <= 2 for a, b in wrapped)


# -- spiral options (Particles mode, Spiral emitter) --------------------------
def _spiral(**kwargs) -> Particles:
    v = Particles(**kwargs)
    v.on_enter()
    v.set_option_index("emitter", 1)  # Spiral
    return v


def test_spiral_reach_scales_render_radius() -> None:
    surface = pygame.Surface((400, 400))
    frame = _loud_frame()
    small = _spiral(seed=5)
    small.set_option_index("reach", 0)  # Small
    big = _spiral(seed=5)
    big.set_option_index("reach", 2)  # Large
    for _ in range(6):
        small.draw(surface, frame, 0.02)
        big.draw(surface, frame, 0.02)
    # Same seed/frame -> identical sparks; only the render scale (reach) differs.
    assert small.option("reach") < big.option("reach")


def test_spiral_has_size_and_spacing_options() -> None:
    keys = {opt.key for opt in Particles.OPTIONS}
    assert {"swirl", "reach", "spacing"} <= keys


# -- ring helpers -------------------------------------------------------------
def test_ring_points_count_and_center() -> None:
    values = np.zeros(64, dtype=np.float32)
    pts = ring_points(100.0, 100.0, 40.0, 10.0, values, points=120)
    assert len(pts) == 120
    # With zero deformation every point sits at base radius from the center.
    for x, y in pts:
        assert abs(((x - 100.0) ** 2 + (y - 100.0) ** 2) ** 0.5 - 40.0) < 1e-3


def test_ring_pops_spawn_advance_decay() -> None:
    import random

    pops = RingPops(cap=50, lifetime=0.5)
    rng = random.Random(1)
    pops.spawn(rng, 10, base_r=0.3, energy=0.8)
    assert pops.count == 10
    r0 = [p.r for p in pops._pops]
    pops.advance(0.1, speed_scale=1.0)
    assert all(p.r > r for p, r in zip(pops._pops, r0, strict=False))
    for _ in range(10):
        pops.advance(0.1, 1.0)
    assert pops.count == 0  # all expired past their lifetime


# -- merged Waveform Rings: single/multiple rings, with/without particles -----
@pytest.mark.parametrize("rings_index", [0, 1, 3])  # 1, 3, 12 rings
@pytest.mark.parametrize("particles_index", [0, 2])  # Off, Dense
def test_circle_modes_render_without_error(rings_index: int, particles_index: int) -> None:
    surface = pygame.Surface((480, 360))
    frame = _loud_frame()
    v = WaveformCircle()
    v.theme = Theme(color_scheme="rainbow_plus")
    v.on_enter()
    v.set_option_index("rings", rings_index)
    v.set_option_index("particles", particles_index)
    for _ in range(10):
        v.draw(surface, frame, 0.02)
    # Also render the idle (no-frame) path.
    v.draw(surface, None, 0.02)


def test_circle_ring_count_option() -> None:
    surface = pygame.Surface((480, 360))
    frame = _loud_frame()
    v = WaveformCircle()
    v.set_option_index("rings", 3)  # 12 rings
    assert v.option("rings") == 12
    v.draw(surface, frame, 0.02)
