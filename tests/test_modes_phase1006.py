"""Phase 0A.06: the six new visual modes render (idle + active, every option) safely."""

from __future__ import annotations

import numpy as np
import pygame
import pytest

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.visuals import registry
from audio_visualizer.visuals.base import Theme

_NEW_MODES = ("terrain", "vectorscope", "meters", "matrix", "pulse_rings", "ripples")
# These paint the whole canvas (sky / meter cells), so an active frame must show pixels.
_FILLING = {"terrain", "meters"}


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

    visual.draw(surface, None, 0.05)
    visual.draw(surface, _silent_frame(), 0.05)

    surface.fill((0, 0, 0))
    frame = _active_frame()
    for _ in range(12):
        visual.draw(surface, frame, 0.05)

    if key in _FILLING:
        nonblack = pygame.transform.average_color(surface)[:3]
        assert sum(nonblack) > 0, f"{key} drew nothing on an active frame"


@pytest.mark.parametrize("key", _NEW_MODES)
def test_every_option_choice_renders(key: str) -> None:
    """Cycle through every choice of every option; each must render without raising."""
    surface = pygame.Surface((320, 200))
    frame = _active_frame()
    for opt in registry.create(key).OPTIONS:
        for index in range(len(opt.choices)):
            visual = registry.create(key)
            visual.theme = Theme()
            visual.on_enter()
            visual.set_option_index(opt.key, index)
            for _ in range(4):
                visual.draw(surface, frame, 0.05)
            visual.draw(surface, None, 0.05)


def test_vectorscope_size_option_scales_trace() -> None:
    from audio_visualizer.visuals.vectorscope import Vectorscope

    visual = Vectorscope()
    visual.theme = Theme()
    visual.on_enter()
    frame = _active_frame()

    from audio_visualizer.visuals.vectorscope import _SIZE_BASE

    def trace_span(size_index: int) -> float:
        visual.set_option_index("size", size_index)
        radius = min(320, 200) * _SIZE_BASE * float(visual.option("size"))
        pts = visual._trace_points(frame, 160.0, 100.0, radius)
        xs = [p[0] for p in pts]
        return max(xs) - min(xs)

    assert trace_span(0) < trace_span(5)  # S is smaller than XXXL


def test_ripples_width_option() -> None:
    from audio_visualizer.visuals.ripples import Ripples, _Ripple

    rp = _Ripple(x=0.5, y=0.5, radius=0.2, life=1.0, hue=0.3, strength=1.0, width_mul=2.0)
    thin = Ripples._line_width(1.0, rp)
    thick = Ripples._line_width(6.0, rp)
    auto = Ripples._line_width(-1.0, rp)
    rand = Ripples._line_width(-2.0, rp)
    assert thick > thin >= 1
    assert rand >= auto  # Random scales the auto width by width_mul (2.0 here)


def test_size_option_present_on_scaling_modes() -> None:
    """Audio Sun / Kaleidoscope / Pulse Rings / Vectorscope expose the shared Size axis."""
    for key in ("radial_spectrum", "kaleidoscope", "pulse_rings", "vectorscope"):
        keys = {opt.key for opt in registry.create(key).OPTIONS}
        assert "size" in keys, f"{key} is missing the Size option"


def test_pulse_rings_spin_off_freezes_angle() -> None:
    from audio_visualizer.visuals.pulse_rings import PulseRings

    visual = PulseRings()
    visual.theme = Theme()
    visual.on_enter()
    visual.set_option_index("rrotate", 0)  # Off
    for _ in range(10):
        visual._advance(_active_frame(), 0.05)
    assert visual._angle == 0.0  # "Off" must not rotate the dashed arcs

    visual.on_enter()
    visual.set_option_index("rrotate", 1)  # Spin
    for _ in range(10):
        visual._advance(_active_frame(), 0.05)
    assert visual._angle > 0.0


def test_pulse_rings_beat_shoots_fading_pulses() -> None:
    from audio_visualizer.visuals.pulse_rings import PulseRings

    visual = PulseRings()
    visual.theme = Theme()
    visual.on_enter()
    visual.set_option_index("beat", 0)  # On (index 0 == value 1)
    surface = pygame.Surface((320, 200))
    # An onset (frame.onset == 1.0) after a quiet prev frame must birth a pulse.
    visual._advance(_silent_frame(), 0.05)
    visual._advance(_active_frame(), 0.05)
    assert visual._pulses, "an onset should shoot out a pulse"
    visual.draw(surface, _active_frame(), 0.05)  # renders the expanding circle safely


def test_meters_spark_emits_particles() -> None:
    from audio_visualizer.visuals.meters import Meters

    visual = Meters()
    visual.theme = Theme()
    visual.on_enter()
    visual.set_option_index("spark", 1)  # On
    surface = pygame.Surface((320, 200))
    for _ in range(20):
        visual.draw(surface, _active_frame(), 0.05)
    assert visual._sparks.count > 0, "spark On should emit particles on a loud frame"
