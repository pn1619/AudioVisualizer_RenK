"""Top control bar: builds buttons + a mode dropdown, lays them out, routes clicks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from audio_visualizer.config import COLOR_PANEL
from audio_visualizer.ui.button import Button
from audio_visualizer.ui.dropdown import Dropdown


@dataclass
class ControlActions:
    """Callbacks the control bar invokes (wired to the App)."""

    toggle_capture: Callable[[], None]
    prev_mode: Callable[[], None]
    next_mode: Callable[[], None]
    select_mode: Callable[[str], None]
    sensitivity_down: Callable[[], None]
    sensitivity_up: Callable[[], None]
    smoothing_down: Callable[[], None]
    smoothing_up: Callable[[], None]
    size_down: Callable[[], None]
    size_up: Callable[[], None]
    speed_down: Callable[[], None]
    speed_up: Callable[[], None]
    cycle_color_scheme: Callable[[], None]
    toggle_reduce_motion: Callable[[], None]
    toggle_fullscreen: Callable[[], None]
    quit: Callable[[], None]


class ControlBar:
    """Lays out and renders the buttons + mode dropdown in the control bar."""

    def __init__(self, actions: ControlActions, mode_options: list[tuple[str, str]]) -> None:
        self._actions = actions
        self._start = Button("Start", actions.toggle_capture)
        self._prev = Button("<", actions.prev_mode)
        self._dropdown = Dropdown(actions.select_mode)
        self._dropdown.set_options(mode_options)
        self._next = Button(">", actions.next_mode)
        self._sens_down = Button("Sens -", actions.sensitivity_down)
        self._sens_up = Button("Sens +", actions.sensitivity_up)
        self._smooth_down = Button("Smooth -", actions.smoothing_down)
        self._smooth_up = Button("Smooth +", actions.smoothing_up)
        self._size_down = Button("Size -", actions.size_down)
        self._size_up = Button("Size +", actions.size_up)
        self._speed_down = Button("Speed -", actions.speed_down)
        self._speed_up = Button("Speed +", actions.speed_up)
        self._color = Button("Classic", actions.cycle_color_scheme)
        self._reduce = Button("Motion+", actions.toggle_reduce_motion)
        self._full = Button("Full", actions.toggle_fullscreen)
        self._quit = Button("Quit", actions.quit)
        # (widget, width) in display order; the dropdown is interleaved with buttons.
        self._items: list[tuple[Button | Dropdown, int]] = [
            (self._start, 60),
            (self._prev, 30),
            (self._dropdown, 140),
            (self._next, 30),
            (self._sens_down, 54),
            (self._sens_up, 54),
            (self._smooth_down, 74),
            (self._smooth_up, 74),
            (self._size_down, 54),
            (self._size_up, 54),
            (self._speed_down, 58),
            (self._speed_up, 58),
            (self._color, 96),
            (self._reduce, 70),
            (self._full, 48),
            (self._quit, 48),
        ]
        self._buttons = [w for w, _ in self._items if isinstance(w, Button)]

    def set_state(
        self, capturing: bool, mode_key: str, reduce_motion: bool, color_scheme: str
    ) -> None:
        self._start.label = "Stop" if capturing else "Start"
        self._dropdown.set_selected(mode_key)
        self._reduce.label = "Motion-" if reduce_motion else "Motion+"
        self._color.label = color_scheme.capitalize()

    def toggle_mode_dropdown(self) -> None:
        self._dropdown.toggle()

    def relayout(self, bar: pygame.Rect) -> None:
        pad = 6
        h = bar.height - pad * 2
        y = bar.y + pad
        x = bar.x + pad
        for widget, w in self._items:
            widget.set_rect(pygame.Rect(x, y, w, h))
            x += w + pad

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self._dropdown.handle_event(event):
            return True
        clicked = False
        for btn in self._buttons:
            if btn.handle_event(event):
                clicked = True
        return clicked

    def draw(self, surface: pygame.Surface, bar: pygame.Rect, font: pygame.font.Font) -> None:
        pygame.draw.rect(surface, COLOR_PANEL, bar)
        for btn in self._buttons:
            btn.draw(surface, font)
        # Draw the dropdown last so its open list overlays the canvas + neighbors.
        self._dropdown.draw(surface, font)
