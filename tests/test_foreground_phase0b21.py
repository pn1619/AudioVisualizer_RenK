"""Phase 0B.21: new foreground effects — rain/storm, meteors, shockwave."""

from __future__ import annotations

import pygame

from audio_visualizer.config import (
    FG_METEOR_MAX,
    FG_RAIN_MAX,
    FG_SHOCK_MAX,
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


# -- rain ----------------------------------------------------------------------
def test_rain_builds_a_continuous_field_even_without_beats(make_frame) -> None:
    surface = pygame.Surface((240, 180))
    fg = _fg("rain")
    quiet = make_frame(level=0.0, onset=0.0)  # no beats at all
    for _ in range(20):
        fg.draw(surface, quiet, 1 / 60)
    assert len(fg._rain) > 0  # the storm sustains itself between beats


def test_rain_stays_bounded(make_frame) -> None:
    surface = pygame.Surface((300, 220))
    fg = _fg("rain", intensity=2.0)
    for _ in range(120):
        fg.draw(surface, _beat(make_frame), 1 / 120)
    assert len(fg._rain) <= FG_RAIN_MAX


def test_rain_direction_sets_fall_vector() -> None:
    fg = _fg("rain", direction="left")
    vx, vy = fg._rain_vec()
    assert vx > 0 and vy == 0  # "from left" travels rightward
    fg.direction = "random"
    assert fg._rain_vec() == (0.0, 1.0)  # random reads as downward


# -- meteors -------------------------------------------------------------------
def test_meteors_spawn_on_beat_and_fade_when_silent(make_frame) -> None:
    surface = pygame.Surface((240, 180))
    fg = _fg("meteors")
    fg.draw(surface, _beat(make_frame), 1 / 60)
    assert fg._meteors
    silent = make_frame(level=0.0, onset=0.0)
    for _ in range(120):
        fg.draw(surface, silent, 1 / 60)
    assert fg._meteors == []


def test_meteors_stay_bounded(make_frame) -> None:
    surface = pygame.Surface((300, 220))
    fg = _fg("meteors", intensity=2.0)
    for _ in range(200):
        fg.draw(surface, _beat(make_frame), 1 / 240)
    assert len(fg._meteors) <= FG_METEOR_MAX


def test_reduce_motion_caps_meteors(make_frame) -> None:
    surface = pygame.Surface((240, 180))
    fg = _fg("meteors", intensity=2.0, reduce_motion=True)
    fg.draw(surface, _beat(make_frame, onset=1.0), 1 / 60)
    assert len(fg._meteors) == 1


# -- shockwave -----------------------------------------------------------------
def test_shockwave_spawns_on_beat_and_fades(make_frame) -> None:
    surface = pygame.Surface((240, 180))
    fg = _fg("shockwave")
    fg.draw(surface, _beat(make_frame), 1 / 60)
    assert fg._shocks
    silent = make_frame(level=0.0, onset=0.0)
    for _ in range(60):
        fg.draw(surface, silent, 1 / 60)
    assert fg._shocks == []


def test_shockwave_origin_follows_direction() -> None:
    fg = _fg("shockwave", direction="top")
    assert fg._origin((200, 100)) == (100.0, 0.0)
    fg.direction = "center"
    assert fg._origin((200, 100)) == (100.0, 50.0)


def test_shockwave_random_origin_actually_scatters() -> None:
    """Random direction must re-roll the origin (not collapse to screen center)."""
    fg = _fg("shockwave", direction="random")
    points = {fg._origin((400, 300)) for _ in range(40)}
    assert len(points) > 5  # many distinct points, not a single fixed spot
    for x, y in points:
        assert 0 <= x <= 400 and 0 <= y <= 300


def test_shockwave_stays_bounded(make_frame) -> None:
    surface = pygame.Surface((200, 200))
    fg = _fg("shockwave", intensity=2.0)
    for _ in range(200):
        fg.draw(surface, _beat(make_frame), 1 / 240)
    assert len(fg._shocks) <= FG_SHOCK_MAX
