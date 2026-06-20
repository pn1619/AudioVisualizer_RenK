"""Phase 0B.19: Stereo 2-color scheme + time-fading, smoothed comet trail."""

from __future__ import annotations

import numpy as np
import pygame

from audio_visualizer import settings as settings_mod
from audio_visualizer.config import COLOR_HUE_DEFAULT, PALETTE
from audio_visualizer.settings import Settings
from audio_visualizer.ui.cursor import Cursor
from audio_visualizer.visuals import _helpers
from audio_visualizer.visuals.base import Theme


# -- Stereo color scheme -------------------------------------------------------
def test_stereo_blends_two_hues_across_position() -> None:
    _helpers.set_custom_hue(0.0)  # red-ish
    _helpers.set_custom_hue2(0.66)  # blue-ish
    left = _helpers.themed_color("stereo", 0.0, PALETTE)
    mid = _helpers.themed_color("stereo", 0.5, PALETTE)
    right = _helpers.themed_color("stereo", 1.0, PALETTE)
    assert left != right  # the two channels differ
    # The midpoint is a blend: each channel sits between the two endpoints.
    for c in range(3):
        lo, hi = sorted((left[c], right[c]))
        assert lo <= mid[c] <= hi


def test_stereo_endpoints_match_each_hue() -> None:
    _helpers.set_custom_hue(0.1)
    _helpers.set_custom_hue2(0.7)
    solid_a = _helpers.themed_color("solid", 0.0, PALETTE)
    _helpers.set_custom_hue(0.1)
    stereo_left = _helpers.themed_color("stereo", 0.0, PALETTE)
    assert stereo_left == solid_a  # t=0 == the first hue's solid color


def test_settings_round_trip_color_hue2(tmp_path) -> None:
    path = tmp_path / "settings.json"
    assert settings_mod.save(Settings(color_scheme="stereo", color_hue2=0.42), path) is True
    loaded = settings_mod.load(path)
    assert loaded.color_scheme == "stereo"
    assert loaded.color_hue2 == 0.42


def test_settings_color_hue2_defaults_when_missing(tmp_path) -> None:
    path = tmp_path / "settings.json"
    assert settings_mod.save(Settings(), path) is True
    loaded = settings_mod.load(path)
    assert 0.0 <= loaded.color_hue2 <= 1.0


# -- Comet trail: time-based fade + smoothing ----------------------------------
def _comet() -> Cursor:
    cursor = Cursor(theme=Theme())
    cursor.set_shape("dot")
    cursor.set_effect("comet")
    return cursor


def test_comet_trail_fades_to_empty_when_stationary() -> None:
    surface = pygame.Surface((200, 200))
    cursor = _comet()
    # Build a trail by moving.
    for x in range(20, 120, 6):
        cursor.draw(surface, (x, 100), focused=True, energy=0.5, onset=0.0, dt=1 / 60)
    assert len(cursor._trail) > 1
    # Hold still well past the TTL: every point should age out and be dropped.
    for _ in range(120):
        cursor.draw(surface, (115, 100), focused=True, energy=0.0, onset=0.0, dt=1 / 60)
    assert len(cursor._trail) <= 1


def test_comet_trail_is_bounded() -> None:
    from audio_visualizer.config import CURSOR_TRAIL_MAX

    surface = pygame.Surface((400, 400))
    cursor = _comet()
    for i in range(2000):
        cursor.draw(surface, (i % 380 + 5, 200), focused=True, energy=0.5, onset=0.0, dt=1 / 240)
    assert len(cursor._trail) <= CURSOR_TRAIL_MAX


def test_comet_resets_when_effect_changes() -> None:
    surface = pygame.Surface((200, 200))
    cursor = _comet()
    for x in range(20, 100, 6):
        cursor.draw(surface, (x, 100), focused=True, energy=0.5, onset=0.0, dt=1 / 60)
    assert cursor._trail
    cursor.set_effect("glow")
    assert cursor._trail == []


def test_theme_has_second_hue_default() -> None:
    assert Theme().custom_hue == COLOR_HUE_DEFAULT
    assert isinstance(Theme().custom_hue2, float)


def test_default_solid_unaffected_by_array_helpers() -> None:
    # Guard: themed_color still returns a 3-tuple for stereo (used widely).
    color = _helpers.themed_color("stereo", 0.25, PALETTE)
    assert isinstance(color, tuple) and len(color) == 3
    assert all(0 <= ch <= 255 for ch in color)
    np.asarray(color)  # smoke: usable as an RGB triple
