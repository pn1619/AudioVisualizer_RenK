"""Dropdown widget: header toggles open, option click selects + closes."""

from __future__ import annotations

import pygame
import pytest

from audio_visualizer.ui.dropdown import Dropdown


@pytest.fixture(scope="module", autouse=True)
def _pygame_ready():
    pygame.init()
    yield
    pygame.quit()


def _click(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)


def test_header_click_toggles_open() -> None:
    d = Dropdown(lambda key: None)
    d.set_options([("a", "Alpha"), ("b", "Beta")])
    d.set_rect(pygame.Rect(0, 0, 120, 30))
    assert d.open is False
    assert d.handle_event(_click((10, 10))) is True
    assert d.open is True


def test_option_click_selects_and_closes() -> None:
    chosen: list[str] = []
    d = Dropdown(chosen.append)
    d.set_options([("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")])
    d.set_selected("a")
    d.set_rect(pygame.Rect(0, 0, 120, 30))
    d.handle_event(_click((10, 10)))  # open
    # Options stack below the header (each 28px); the 2nd row is "Beta".
    assert d.handle_event(_click((10, 60))) is True
    assert chosen == ["b"]
    assert d.open is False
    assert d.current_label == "Beta"


def test_click_outside_closes_without_selecting() -> None:
    chosen: list[str] = []
    d = Dropdown(chosen.append)
    d.set_options([("a", "Alpha")])
    d.set_rect(pygame.Rect(0, 0, 120, 30))
    d.handle_event(_click((10, 10)))  # open
    assert d.open is True
    assert d.handle_event(_click((600, 600))) is True
    assert d.open is False
    assert chosen == []
