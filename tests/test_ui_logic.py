"""UI logic: button hit-testing and size-relative layout."""

from __future__ import annotations

import pygame
import pytest

from audio_visualizer.config import CONTROL_BAR_HEIGHT, MIN_WINDOW_SIZE
from audio_visualizer.ui.button import Button
from audio_visualizer.ui.layout import Layout


@pytest.fixture(scope="module", autouse=True)
def _pygame_ready():
    pygame.init()
    yield
    pygame.quit()


def test_button_click_inside_triggers_callback() -> None:
    clicks = []
    btn = Button("Go", lambda: clicks.append(1))
    btn.set_rect(pygame.Rect(10, 10, 100, 30))

    inside = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(20, 20))
    assert btn.handle_event(inside) is True
    assert clicks == [1]


def test_button_click_outside_does_nothing() -> None:
    clicks = []
    btn = Button("Go", lambda: clicks.append(1))
    btn.set_rect(pygame.Rect(10, 10, 100, 30))

    outside = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(500, 500))
    assert btn.handle_event(outside) is False
    assert clicks == []


def test_layout_splits_into_bar_and_canvas() -> None:
    layout = Layout.compute((1280, 720))
    assert layout.control_bar.height == CONTROL_BAR_HEIGHT
    assert layout.canvas.top == CONTROL_BAR_HEIGHT
    assert layout.canvas.height == 720 - CONTROL_BAR_HEIGHT
    assert layout.control_bar.width == 1280


def test_layout_clamps_to_minimum_size() -> None:
    layout = Layout.compute((100, 80))
    assert layout.width >= MIN_WINDOW_SIZE[0]
    assert layout.height >= MIN_WINDOW_SIZE[1]
    assert layout.canvas.height > 0


def test_layout_hidden_control_bar_gives_full_canvas() -> None:
    layout = Layout.compute((1280, 720), show_control_bar=False)
    assert layout.control_bar.height == 0
    assert layout.canvas.height == 720
