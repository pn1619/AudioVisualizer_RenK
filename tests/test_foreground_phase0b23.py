"""Phase 0B.23: foreground color override, lightning flash level + ground impact,
Flames+/Meteors+ behavior, and the smoother edge glow."""

from __future__ import annotations

import pygame

from audio_visualizer.config import (
    FG_COLOR_RGB,
    FG_METEOR_EMBER_MAX,
    FG_METEOR_LIFE,
    FG_METEOR_LIFE_MIN,
    FG_SHOCK_COLOR,
    ONSET_THRESHOLD,
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


# -- color override ------------------------------------------------------------
def test_base_color_auto_keeps_natural() -> None:
    fg = _fg("shockwave", color="auto")
    assert fg._base_color(FG_SHOCK_COLOR) == FG_SHOCK_COLOR


def test_base_color_named_overrides_hue() -> None:
    fg = _fg("shockwave", color="red")
    assert fg._base_color(FG_SHOCK_COLOR) == FG_COLOR_RGB["red"]


def test_base_color_theme_is_valid_rgb() -> None:
    fg = _fg("shockwave", color="theme")
    col = fg._base_color(FG_SHOCK_COLOR)
    assert len(col) == 3 and all(0 <= c <= 255 for c in col)


def test_ramp_color_named_runs_white_to_hue_to_dark() -> None:
    fg = _fg("flames", color="blue")
    hot = fg._ramp_color(((255, 0, 0),), 0.0)  # young -> white-hot
    mid = fg._ramp_color(((255, 0, 0),), 0.5)  # mid -> chosen hue
    cold = fg._ramp_color(((255, 0, 0),), 1.0)  # old -> near-black ash
    assert hot == (255, 255, 255)
    assert mid == FG_COLOR_RGB["blue"]
    assert sum(cold) < sum(mid)


def test_ramp_color_auto_uses_palette() -> None:
    fg = _fg("flames", color="auto")
    palette = ((10, 20, 30), (200, 100, 50))
    assert fg._ramp_color(palette, 0.0) == (10, 20, 30)


# -- lightning flash level -----------------------------------------------------
def test_flash_off_suppresses_white_flash(make_frame) -> None:
    surface = pygame.Surface((200, 150))
    fg = _fg("lightning", flash=0.0)
    fg.draw(surface, _beat(make_frame), 1 / 60)
    assert fg._flash == 0.0  # no flash envelope when the level is Off


def test_flash_full_builds_envelope(make_frame) -> None:
    fg = _fg("lightning", flash=1.0)
    fg.draw(pygame.Surface((200, 150)), _beat(make_frame), 1 / 60)
    assert fg._flash > 0.0


# -- lightning+ ground impact --------------------------------------------------
def test_strike_to_bottom_spawns_impact() -> None:
    fg = _fg("lightning", direction="top")  # bolts run top -> bottom (the "ground")
    fg._spawn_bolts((300, 200), 1.0)
    assert fg._impacts  # a ground strike kicks up an impact burst
    imp = fg._impacts[0]
    assert isinstance(imp["angles"], list) and imp["angles"]


def test_impacts_expire(make_frame) -> None:
    surface = pygame.Surface((300, 200))
    fg = _fg("lightning", direction="top")
    fg.draw(surface, _beat(make_frame), 1 / 60)
    silent = make_frame(level=0.0, onset=0.0)
    for _ in range(120):
        fg.draw(surface, silent, 1 / 60)
    assert fg._impacts == []


# -- meteors+ ------------------------------------------------------------------
def test_meteor_life_varies_within_range() -> None:
    fg = _fg("meteors")
    lives = [float(fg._spawn_meteor((400, 300), "top")["life"]) for _ in range(40)]
    assert all(FG_METEOR_LIFE_MIN <= v <= FG_METEOR_LIFE for v in lives)
    assert max(lives) - min(lives) > 0.1  # genuinely variable


def test_meteor_sheds_embers(make_frame) -> None:
    surface = pygame.Surface((400, 300))
    fg = _fg("meteors", intensity=2.0)
    for _ in range(10):
        fg.draw(surface, _beat(make_frame), 1 / 60)
    assert fg._m_embers  # a tail of ember particles forms
    assert len(fg._m_embers) <= FG_METEOR_EMBER_MAX


def test_meteor_head_fade_reaches_zero() -> None:
    fg = _fg("meteors")
    m: dict[str, object] = {"age": 1.0, "life": 1.0}
    assert fg._meteor_fade(m) == 0.0  # fully faded at end of life
    m["age"] = 0.0
    assert fg._meteor_fade(m) == 1.0  # full brightness early on


# -- edge glow -----------------------------------------------------------------
def test_glow_alpha_falls_off_monotonically() -> None:
    fg = _fg("edgeglow")
    vals = [fg._glow_alpha(i, 40, 120.0) for i in range(40)]
    assert vals[0] >= vals[-1]
    assert all(a >= b for a, b in zip(vals, vals[1:], strict=False))


def test_edgeglow_renders_with_color_override(make_frame) -> None:
    surface = pygame.Surface((200, 150))
    fg = _fg("edgeglow", color="green")
    for _ in range(3):
        fg.draw(surface, _beat(make_frame), 1 / 60)
    assert surface.get_at((0, 75))[1] > 0  # green channel lit along the left border


def test_edgeglow_breathes_with_level_between_beats(make_frame) -> None:
    """Continuous floor: a loud, beat-free frame still lights the border."""
    surface = pygame.Surface((200, 150))
    fg = _fg("edgeglow")
    fg.draw(surface, make_frame(level=0.9, onset=0.0), 1 / 60)
    assert any(surface.get_at((0, 75))[:3])  # lit even with no onset


# -- combo modes ---------------------------------------------------------------
def test_storm_combo_runs_rain_and_lightning(make_frame) -> None:
    surface = pygame.Surface((240, 180))
    fg = _fg("storm")
    fg.draw(surface, _beat(make_frame), 1 / 60)
    assert fg._rain  # rain field is maintained
    assert fg._bolts  # and lightning fires on the beat


def test_party_combo_runs_fireworks_and_sparks(make_frame) -> None:
    surface = pygame.Surface((240, 180))
    fg = _fg("party")
    fg.draw(surface, _beat(make_frame), 1 / 60)
    assert fg._fireworks and fg._spark_ps


# -- reactivity ----------------------------------------------------------------
def test_reactivity_widens_onset_sensitivity(make_frame) -> None:
    soft = make_frame(level=0.5, onset=ONSET_THRESHOLD * 0.6)
    assert _fg("flames", reactivity=0.5)._beat(soft) == 0.0  # too soft to fire
    assert _fg("flames", reactivity=2.0)._beat(soft) > 0.0  # frantic catches it


# -- wind ----------------------------------------------------------------------
def test_wind_pushes_particles_horizontally() -> None:
    fg = _fg("sparks", wind=900.0)
    fg._dt = 0.1
    spark = {"x": 0.0, "y": 0.0, "vx": 0.0, "vy": 0.0, "age": 0.0, "life": 1.0, "size": 3.0}
    fg._spark_ps = [spark]
    fg._step_sparks()
    assert fg._spark_ps[0]["vx"] > 0.0  # blown to the right
