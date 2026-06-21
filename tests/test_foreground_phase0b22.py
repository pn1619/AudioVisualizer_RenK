"""Phase 0B.22: foreground sparks, fireworks, edge glow + the 'center' direction."""

from __future__ import annotations

import pygame

from audio_visualizer.config import (
    FG_DIRECTIONS,
    FG_FW_MAX,
    FG_SPARK_MAX,
)
from audio_visualizer.visuals.base import Theme
from audio_visualizer.visuals.foreground import Foreground


def _beat(make_frame, onset: float = 0.95):
    return make_frame(level=0.8, onset=onset)


def _fg(mode: str, **kw) -> Foreground:
    fg = Foreground(theme=Theme(), reduce_motion=kw.pop("reduce_motion", False))
    fg.mode = mode
    for key, val in kw.items():
        setattr(fg, key, val)
    return fg


# -- center direction ----------------------------------------------------------
def test_center_is_a_valid_direction() -> None:
    assert "center" in FG_DIRECTIONS


def test_shockwave_center_direction_origins_at_center() -> None:
    fg = _fg("shockwave", direction="center")
    assert fg._origin((200, 120)) == (100.0, 60.0)


def test_fireworks_center_origin_is_screen_center() -> None:
    fg = _fg("fireworks", direction="center")
    assert fg._burst_origin((300, 200)) == (150.0, 100.0)


# -- sparks --------------------------------------------------------------------
def test_sparks_burst_on_beat_then_fade(make_frame) -> None:
    surface = pygame.Surface((240, 180))
    fg = _fg("sparks")
    fg.draw(surface, _beat(make_frame), 1 / 60)
    assert fg._spark_ps
    silent = make_frame(level=0.0, onset=0.0)
    for _ in range(120):
        fg.draw(surface, silent, 1 / 60)
    assert fg._spark_ps == []


def test_sparks_stay_bounded(make_frame) -> None:
    surface = pygame.Surface((300, 220))
    fg = _fg("sparks", intensity=2.0)
    for _ in range(200):
        fg.draw(surface, _beat(make_frame), 1 / 240)
    assert len(fg._spark_ps) <= FG_SPARK_MAX


def test_sparks_fall_under_gravity(make_frame) -> None:
    surface = pygame.Surface((240, 180))
    fg = _fg("sparks", direction="left")  # launched horizontally -> gravity adds vy
    fg.draw(surface, _beat(make_frame), 1 / 60)
    for _ in range(5):
        fg.draw(surface, make_frame(level=0.0, onset=0.0), 1 / 60)
    assert any(p["vy"] > 0 for p in fg._spark_ps)


# -- fireworks -----------------------------------------------------------------
def test_fireworks_detonate_on_beat_and_fade(make_frame) -> None:
    surface = pygame.Surface((240, 180))
    fg = _fg("fireworks")
    fg.draw(surface, _beat(make_frame), 1 / 60)
    assert len(fg._fireworks) > 8  # a radial burst of many particles
    silent = make_frame(level=0.0, onset=0.0)
    for _ in range(150):
        fg.draw(surface, silent, 1 / 60)
    assert fg._fireworks == []


def test_fireworks_stay_bounded(make_frame) -> None:
    surface = pygame.Surface((300, 220))
    fg = _fg("fireworks", intensity=2.0)
    for _ in range(200):
        fg.draw(surface, _beat(make_frame), 1 / 240)
    assert len(fg._fireworks) <= FG_FW_MAX


# -- edge glow -----------------------------------------------------------------
def test_edgeglow_pulses_on_beat_and_decays(make_frame) -> None:
    surface = pygame.Surface((200, 150))
    fg = _fg("edgeglow")
    fg.draw(surface, _beat(make_frame), 1 / 60)
    assert fg._glow > 0.0
    silent = make_frame(level=0.0, onset=0.0)
    for _ in range(120):
        fg.draw(surface, silent, 1 / 60)
    assert fg._glow <= 0.01


def test_edgeglow_single_edge_vs_all() -> None:
    fg = _fg("edgeglow", direction="top")
    assert fg._glow_edges() == ("top",)
    fg.direction = "center"
    assert set(fg._glow_edges()) == {"top", "bottom", "left", "right"}


def test_edgeglow_renders_without_error(make_frame) -> None:
    surface = pygame.Surface((160, 120))
    fg = _fg("edgeglow", intensity=2.0)
    for _ in range(10):
        fg.draw(surface, _beat(make_frame), 1 / 60)  # must not raise
