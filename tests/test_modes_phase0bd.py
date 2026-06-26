"""Phase 0B-d: the ten new ``Test_`` visual modes render and customize safely.

Each mode must register, render idle + silent + active under both motion settings,
cycle every option choice without raising, and apply its presets. Field/filling modes
must paint pixels on an active frame. Headless (SDL dummy driver via conftest).
"""

from __future__ import annotations

import numpy as np
import pygame
import pytest

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.visuals import registry
from audio_visualizer.visuals.base import Theme

_NEW_MODES = (
    "test_aurora_veil",
    "test_hyperspace",
    "test_skyline",
    "test_dna",
    "test_harmonograph",
    "test_metaballs",
    "fractal_tree",
    "test_flowfield",
    "test_constellation",
    "test_mandala",
)
# Modes that paint (most of) the canvas, so an active frame must show pixels.
_FILLING = {"test_aurora_veil", "test_metaballs", "test_skyline", "test_flowfield"}


def _active_frame() -> AnalysisFrame:
    bands = (0.3 + 0.6 * np.abs(np.sin(np.linspace(0, 9, 64)))).astype(np.float32)
    wave = np.sin(np.linspace(0, 12, 512)).astype(np.float32) * 0.6
    return AnalysisFrame(
        wave, bands, rms=0.5, peak=0.8, sample_rate=48000, timestamp=0.0, onset=1.0
    )


def _silent_frame() -> AnalysisFrame:
    return AnalysisFrame(
        np.zeros(512, np.float32), np.zeros(64, np.float32), 0.0, 0.0, 48000, 0.0, 0.0
    )


@pytest.mark.parametrize("key", _NEW_MODES)
def test_mode_registered(key: str) -> None:
    assert key in registry.keys(), f"{key} not registered"


@pytest.mark.parametrize("key", _NEW_MODES)
@pytest.mark.parametrize("reduce_motion", [False, True])
def test_mode_renders(key: str, reduce_motion: bool) -> None:
    visual = registry.create(key, reduce_motion=reduce_motion)
    visual.theme = Theme()
    surface = pygame.Surface((360, 240))
    visual.on_enter()

    visual.draw(surface, None, 0.05)
    visual.draw(surface, _silent_frame(), 0.05)

    surface.fill((0, 0, 0))
    frame = _active_frame()
    for i in range(16):
        visual.draw(surface, frame if i % 3 else _silent_frame(), 0.05)

    if key in _FILLING:
        avg = pygame.transform.average_color(surface)[:3]
        assert sum(avg) > 0, f"{key} drew nothing on active frames"


@pytest.mark.parametrize("key", _NEW_MODES)
def test_every_option_choice_renders(key: str) -> None:
    surface = pygame.Surface((360, 240))
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


@pytest.mark.parametrize("key", _NEW_MODES)
def test_presets_apply(key: str) -> None:
    """Selecting a preset (index >= 1) snaps the listed sibling options."""
    visual = registry.create(key)
    assert visual.PRESETS, f"{key} should ship curated presets"
    for preset_idx, mapping in visual.PRESETS.items():
        visual.set_option_index("preset", preset_idx)
        for opt_key, choice in mapping.items():
            count = len(visual._option_def(opt_key).choices)
            assert visual.option_index(opt_key) == max(0, min(choice, count - 1))


def test_shared_palette_helper() -> None:
    from audio_visualizer.visuals._helpers import SHARED_PALETTES, palette_or_theme

    themed = palette_or_theme(-1, "rainbow", 0.5, 0.0)
    polar = palette_or_theme(0, "rainbow", 0.5, 0.0)
    assert isinstance(themed, tuple) and len(themed) == 3
    assert polar == _expect_palette(SHARED_PALETTES[0], 0.5)


def _expect_palette(palette, t):
    from audio_visualizer.visuals._helpers import palette_color

    return palette_color(palette, t)


def test_metaballs_field_exceeds_threshold() -> None:
    """The metaball field must rise above the merge threshold somewhere (visible goo)."""
    from audio_visualizer.visuals.test_metaballs import TestMetaballs

    visual = TestMetaballs()
    visual.theme = Theme()
    visual.on_enter()
    surface = pygame.Surface((320, 200))
    for _ in range(5):
        visual.draw(surface, _active_frame(), 0.05)
    field = visual._field(0.6)
    assert float(field.max()) > 1.0


def test_hyperspace_strobes_flag() -> None:
    from audio_visualizer.visuals.test_hyperspace import TestHyperspace

    assert TestHyperspace.STROBES is True  # Punch warp flashes; needs the notice


def test_fractal_tree_renders_artwork_and_detects_flowers() -> None:
    """The mode paints the concept artwork and finds the bright-pink blooms to animate."""
    from audio_visualizer.visuals.fractal_tree import FractalTree

    visual = FractalTree()
    visual.theme = Theme()
    visual.on_enter()
    surface = pygame.Surface((640, 426))
    visual.draw(surface, _active_frame(), 0.05)
    assert visual._scaled is not None, "must load + fit the artwork"
    assert len(visual._flowers) >= 6, "should detect the painted blooms"
    assert sum(pygame.transform.average_color(surface)[:3]) > 0, "drew nothing"


def test_fractal_tree_flowers_glow_and_emit_on_beats() -> None:
    """The flowers' effects: onsets raise the glow and spawn particles."""
    from audio_visualizer.visuals.fractal_tree import FractalTree

    visual = FractalTree()
    visual.theme = Theme()
    visual.set_option_index("preset", 1)  # Bloom: particles on
    visual.on_enter()
    surface = pygame.Surface((640, 426))
    visual.draw(surface, _silent_frame(), 0.05)
    calm = float(visual._bloom.max()) if visual._bloom.size else 0.0
    for _ in range(4):
        visual.draw(surface, _active_frame(), 0.05)  # active frame has onset = 1.0
    assert float(visual._bloom.max()) > calm, "onsets should brighten the blooms"
    assert visual._particles, "onsets should emit flower particles"


def test_fractal_tree_energy_flow_traces_the_tree() -> None:
    """The mode builds a roots->tips distance field and the running light brightens the body."""
    from audio_visualizer.visuals.fractal_tree import FractalTree

    visual = FractalTree()
    visual.theme = Theme()
    visual.set_option_index("t3body", 0)  # isolate the flow effect from the frequency glow
    visual.set_option_index("t3flow", 2)  # Surge
    visual.set_option_index("t3particles", 0)
    visual.on_enter()
    surface = pygame.Surface((640, 426))
    visual.draw(surface, _active_frame(), 0.05)
    phase = visual._phase
    assert phase is not None and float(phase.max()) > 0.5, "flow needs a roots->tips field"
    assert (phase >= 0.0).mean() > 0.1, "the tree should be reachable from the roots"
    lit = sum(pygame.transform.average_color(surface)[:3])

    off = FractalTree()
    off.theme = Theme()
    off.set_option_index("t3body", 0)
    off.set_option_index("t3flow", 0)
    off.set_option_index("t3particles", 0)
    off.on_enter()
    plain = pygame.Surface((640, 426))
    off.draw(plain, _active_frame(), 0.05)
    assert lit > sum(pygame.transform.average_color(plain)[:3]), "energy flow should add light"
