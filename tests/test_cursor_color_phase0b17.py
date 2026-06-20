"""Phase 0B.17: easy Solid/Mono color picking + custom mouse cursor overlay."""

from __future__ import annotations

import json

import numpy as np
import pygame
import pytest

from audio_visualizer import settings as settings_mod
from audio_visualizer.config import CURSOR_MODES
from audio_visualizer.settings import Settings
from audio_visualizer.ui.appearance_panel import AppearanceActions, AppearancePanel
from audio_visualizer.ui.cursor import Cursor
from audio_visualizer.visuals.base import Theme


@pytest.fixture(scope="module", autouse=True)
def _pygame_ready():
    pygame.init()
    pygame.display.set_mode((10, 10))
    yield
    pygame.quit()


def _make_appearance(calls: dict[str, str]) -> AppearancePanel:
    return AppearancePanel(
        AppearanceActions(
            cycle_style=lambda: calls.__setitem__("style", "x"),
            cycle_accent=lambda: calls.__setitem__("accent", "x"),
            cycle_font=lambda: calls.__setitem__("font", "x"),
            cycle_cursor=lambda: calls.__setitem__("cursor", "x"),
            set_hue=lambda h: calls.__setitem__("hue", f"{h:.3f}"),
            set_color_scheme=lambda s: calls.__setitem__("scheme", s),
        )
    )


def test_solid_mono_buttons_route_scheme() -> None:
    calls: dict[str, str] = {}
    panel = _make_appearance(calls)
    panel.open = True
    panel.set_state({"style": "Glass", "accent": "Aqua", "font": "Mono", "cursor": "System"})
    canvas = pygame.Rect(0, 0, 1280, 720)

    for key in ("solid", "mono"):
        rect = panel._pick_button_rects(canvas)[key]
        panel.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center), canvas
        )
        assert calls["scheme"] == key


def test_hue_bar_drag_routes_hue() -> None:
    calls: dict[str, str] = {}
    panel = _make_appearance(calls)
    panel.open = True
    canvas = pygame.Rect(0, 0, 1280, 720)
    hue = panel._hue_rect(canvas)
    panel.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(hue.centerx, hue.centery)),
        canvas,
    )
    assert "hue" in calls


def test_cursor_set_mode_validates() -> None:
    cursor = Cursor(theme=Theme())
    cursor.set_mode("dot")
    assert cursor.mode == "dot"
    cursor.set_mode("not-a-mode")
    assert cursor.mode == "dot"


def test_cursor_modes_draw_without_error() -> None:
    surface = pygame.Surface((200, 200))
    cursor = Cursor(theme=Theme())
    for mode in CURSOR_MODES:
        cursor.set_mode(mode)
        # Move across frames so trail/spark cadence exercises.
        for x in range(20, 120, 10):
            cursor.draw(surface, (x, 100), focused=True, energy=0.6, onset=1.0, dt=1 / 60)


def test_cursor_system_mode_is_noop() -> None:
    surface = pygame.Surface((50, 50))
    before = pygame.surfarray.array3d(surface).copy()
    cursor = Cursor(theme=Theme())  # defaults to "system"
    cursor.draw(surface, (25, 25), focused=True, energy=1.0, onset=1.0, dt=1 / 60)
    assert np.array_equal(before, pygame.surfarray.array3d(surface))


def test_unfocused_window_skips_custom_cursor() -> None:
    surface = pygame.Surface((50, 50))
    before = pygame.surfarray.array3d(surface).copy()
    cursor = Cursor(theme=Theme())
    cursor.set_mode("dot")
    cursor.draw(surface, (25, 25), focused=False, energy=1.0, onset=1.0, dt=1 / 60)
    assert np.array_equal(before, pygame.surfarray.array3d(surface))


def test_settings_round_trip_cursor_mode(tmp_path) -> None:
    path = tmp_path / "settings.json"
    assert settings_mod.save(Settings(cursor_mode="comet"), path) is True
    assert settings_mod.load(path).cursor_mode == "comet"


def test_settings_bad_cursor_mode_falls_back(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"cursor_mode": "bogus"}), encoding="utf-8")
    assert settings_mod.load(path).cursor_mode in CURSOR_MODES
