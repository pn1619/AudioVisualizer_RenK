"""Phase 0B.18: cursor shape + effect split (dropdowns) and the color picker popup."""

from __future__ import annotations

import json

import numpy as np
import pygame
import pytest

from audio_visualizer import settings as settings_mod
from audio_visualizer.config import CURSOR_EFFECTS, CURSOR_SHAPES
from audio_visualizer.settings import Settings
from audio_visualizer.ui.color_picker import ColorPicker, ColorPickerActions
from audio_visualizer.ui.cursor import Cursor
from audio_visualizer.visuals.base import Theme


@pytest.fixture(scope="module", autouse=True)
def _pygame_ready():
    pygame.init()
    pygame.display.set_mode((10, 10))
    yield
    pygame.quit()


# -- cursor: shape + effect ----------------------------------------------------
def test_cursor_set_shape_and_effect_validate() -> None:
    cursor = Cursor(theme=Theme())
    cursor.set_shape("star")
    cursor.set_effect("comet")
    assert (cursor.shape, cursor.effect) == ("star", "comet")
    cursor.set_shape("bogus")
    cursor.set_effect("bogus")
    assert (cursor.shape, cursor.effect) == ("star", "comet")  # invalid ignored


def test_cursor_is_custom_only_when_non_default() -> None:
    cursor = Cursor(theme=Theme())
    assert cursor.is_custom is False  # system + none
    cursor.set_effect("sparkles")  # an effect alone counts as custom
    assert cursor.is_custom is True
    cursor.set_effect("none")
    cursor.set_shape("dot")  # a shape alone counts as custom
    assert cursor.is_custom is True


def test_every_shape_effect_combo_draws_without_error() -> None:
    surface = pygame.Surface((220, 220))
    cursor = Cursor(theme=Theme())
    for shape in CURSOR_SHAPES:
        for effect in CURSOR_EFFECTS:
            cursor.set_shape(shape)
            cursor.set_effect(effect)
            for x in range(20, 140, 12):  # move so trail/spark/ripple cadence runs
                cursor.draw(surface, (x, 110), focused=True, energy=0.7, onset=1.0, dt=1 / 60)


def test_default_cursor_is_noop() -> None:
    surface = pygame.Surface((50, 50))
    before = pygame.surfarray.array3d(surface).copy()
    Cursor(theme=Theme()).draw(surface, (25, 25), focused=True, energy=1.0, onset=1.0, dt=1 / 60)
    assert np.array_equal(before, pygame.surfarray.array3d(surface))


def test_unfocused_window_skips_custom_cursor() -> None:
    surface = pygame.Surface((50, 50))
    before = pygame.surfarray.array3d(surface).copy()
    cursor = Cursor(theme=Theme())
    cursor.set_shape("star")
    cursor.set_effect("glow")
    cursor.draw(surface, (25, 25), focused=False, energy=1.0, onset=1.0, dt=1 / 60)
    assert np.array_equal(before, pygame.surfarray.array3d(surface))


# -- color picker --------------------------------------------------------------
def test_color_picker_hue_drag_and_scheme_buttons() -> None:
    calls: dict[str, object] = {}
    picker = ColorPicker(
        ColorPickerActions(
            set_hue=lambda h: calls.__setitem__("hue", h),
            set_scheme=lambda s: calls.__setitem__("scheme", s),
        )
    )
    picker.open = True
    picker.set_state(0.3, "solid")
    canvas = pygame.Rect(0, 0, 1280, 720)

    hue = picker._hue_rect(canvas)
    picker.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(hue.centerx, hue.centery)), canvas
    )
    assert "hue" in calls

    for key in ("solid", "mono"):
        rect = picker._button_rects(canvas)[key]
        picker.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center), canvas
        )
        assert calls["scheme"] == key


def test_color_picker_close_button() -> None:
    picker = ColorPicker(ColorPickerActions(set_hue=lambda h: None, set_scheme=lambda s: None))
    picker.open = True
    canvas = pygame.Rect(0, 0, 1280, 720)
    rect = picker._close_rect(canvas)
    picker.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center), canvas
    )
    assert picker.open is False


# -- settings ------------------------------------------------------------------
def test_settings_round_trip_cursor_fields(tmp_path) -> None:
    path = tmp_path / "settings.json"
    assert settings_mod.save(Settings(cursor_shape="heart", cursor_effect="ripple"), path) is True
    loaded = settings_mod.load(path)
    assert loaded.cursor_shape == "heart"
    assert loaded.cursor_effect == "ripple"


def test_settings_migrates_legacy_cursor_mode(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"schema_version": 19, "cursor_mode": "comet"}), encoding="utf-8")
    loaded = settings_mod.load(path)
    assert loaded.cursor_shape == "dot"
    assert loaded.cursor_effect == "comet"


def test_settings_bad_cursor_values_fall_back(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"cursor_shape": "nope", "cursor_effect": "nope"}), encoding="utf-8")
    loaded = settings_mod.load(path)
    assert loaded.cursor_shape in CURSOR_SHAPES
    assert loaded.cursor_effect in CURSOR_EFFECTS
