"""Phase 8: Light Show 2 / Laser 2 modes and the shared SparkField trail option."""

from __future__ import annotations

import numpy as np
import pygame
import pytest

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.visuals._helpers import TRAIL_OPTION, SparkField
from audio_visualizer.visuals.base import Theme
from audio_visualizer.visuals.laser import Laser
from audio_visualizer.visuals.lightshow import LightShow


@pytest.fixture(scope="module", autouse=True)
def _pygame_ready():
    pygame.init()
    yield
    pygame.quit()


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


# -- SparkField ---------------------------------------------------------------
def test_sparkfield_spawn_advance_decay() -> None:
    field = SparkField(cap=10, lifetime=0.5, trail_len=4)
    field.spawn(x=0.5, y=0.5, vx=0.1, vy=0.0, hue=0.2)
    assert field.count == 1
    field.advance(0.1, speed_scale=1.0)
    # moved right; a trail point was recorded
    assert field._sparks[0].x > 0.5
    assert len(field._sparks[0].trail) == 1
    for _ in range(10):
        field.advance(0.1, 1.0)
    assert field.count == 0  # expired past lifetime


def test_sparkfield_respects_cap() -> None:
    field = SparkField(cap=3)
    for _ in range(10):
        field.spawn(0.5, 0.5, 0.0, 0.0, 0.1)
    assert field.count == 3


def test_sparkfield_trail_length_bounded() -> None:
    field = SparkField(cap=5, trail_len=3)
    field.spawn(0.1, 0.1, 0.05, 0.05, 0.3)
    for _ in range(10):
        field.advance(0.05, 1.0)
    assert len(field._sparks[0].trail) <= 3


@pytest.mark.parametrize("trails", [False, True])
def test_sparkfield_render_paths(trails: bool) -> None:
    surface = pygame.Surface((200, 200))
    field = SparkField(cap=20)
    for i in range(5):
        field.spawn(0.5, 0.5, 0.02 * i, -0.01 * i, hue=i / 5)
    for _ in range(4):
        field.advance(0.05, 1.0)
    field.render(surface, "rainbow_plus", 0.3, 200, 200, size_scale=1.0, trails=trails)


# -- shared trail option ------------------------------------------------------
def test_both_modes_expose_trail_option() -> None:
    assert TRAIL_OPTION in LightShow.OPTIONS
    assert TRAIL_OPTION in Laser.OPTIONS


# -- Light Show (merged: Particles axis adds beads + emit) --------------------
def test_lightshow_renders_loud_and_idle() -> None:
    surface = pygame.Surface((480, 360))
    frame = _loud_frame()
    v = LightShow(seed=7)
    v.theme = Theme(color_scheme="rainbow_plus")
    v.on_enter()
    for _ in range(10):
        v.draw(surface, frame, 0.02)
    v.draw(surface, None, 0.02)  # idle path must not raise


@pytest.mark.parametrize("core_index", [0, 1, 2, 3])
def test_lightshow_core_shapes_render(core_index: int) -> None:
    surface = pygame.Surface((400, 400))
    v = LightShow(seed=1)
    v.on_enter()
    v.set_option_index("core", core_index)
    v.draw(surface, _loud_frame(), 0.02)


def test_lightshow_particles_on_spawns_sparks() -> None:
    surface = pygame.Surface((400, 400))
    frame = _loud_frame()
    v = LightShow(seed=3)
    v.on_enter()
    v.set_option_index("particles", 2)  # Dense -> bead beams that emit
    for _ in range(5):
        v.draw(surface, frame, 0.02)
    assert v._sparks.count > 0


def test_lightshow_reduce_motion_no_emission() -> None:
    surface = pygame.Surface((400, 400))
    frame = _loud_frame()
    v = LightShow(reduce_motion=True, seed=3)
    v.on_enter()
    v.set_option_index("particles", 2)
    for _ in range(5):
        v.draw(surface, frame, 0.02)
    assert v._sparks.count == 0  # reduce-motion disables shooting


def test_lightshow_has_expected_options() -> None:
    keys = {opt.key for opt in LightShow.OPTIONS}
    assert {"beams", "particles", "core", "trails"} <= keys


# -- Laser (merged: Particles axis controls emit) -----------------------------
@pytest.mark.parametrize("shape_index", [0, 1, 2, 3, 4])
def test_laser_all_shapes_render(shape_index: int) -> None:
    surface = pygame.Surface((480, 360))
    v = Laser(seed=2)
    v.theme = Theme(color_scheme="rainbow")
    v.on_enter()
    v.set_option_index("shape", shape_index)
    for _ in range(6):
        v.draw(surface, _loud_frame(), 0.02)
    v.draw(surface, None, 0.02)  # idle path


def test_laser_particles_on_spawns_sparks() -> None:
    surface = pygame.Surface((400, 400))
    frame = _loud_frame()
    v = Laser(seed=9)
    v.on_enter()
    v.set_option_index("particles", 2)  # Dense -> beams emit sparks
    v.set_option_index("trails", 1)
    for _ in range(5):
        v.draw(surface, frame, 0.02)
    assert v._sparks.count > 0


def test_laser_tiny_surface_safe() -> None:
    v = Laser(seed=1)
    v.on_enter()
    v.draw(pygame.Surface((1, 1)), _loud_frame(), 0.02)  # below min, returns early
    v.draw(pygame.Surface((40, 30)), _loud_frame(), 0.02)
