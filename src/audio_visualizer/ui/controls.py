"""Top control bar: builds buttons, lays them out, routes clicks to actions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from audio_visualizer.config import COLOR_PANEL
from audio_visualizer.ui.button import Button


@dataclass
class ControlActions:
    """Callbacks the control bar invokes (wired to the App)."""

    toggle_capture: Callable[[], None]
    prev_mode: Callable[[], None]
    next_mode: Callable[[], None]
    sensitivity_down: Callable[[], None]
    sensitivity_up: Callable[[], None]
    smoothing_down: Callable[[], None]
    smoothing_up: Callable[[], None]
    toggle_reduce_motion: Callable[[], None]
    toggle_fullscreen: Callable[[], None]
    quit: Callable[[], None]


class ControlBar:
    """Lays out and renders the buttons in the control-bar rectangle."""

    def __init__(self, actions: ControlActions) -> None:
        self._actions = actions
        self._start = Button("Start", actions.toggle_capture)
        self._prev = Button("<", actions.prev_mode)
        self._mode = Button("Mode", actions.next_mode)
        self._next = Button(">", actions.next_mode)
        self._sens_down = Button("Sens -", actions.sensitivity_down)
        self._sens_up = Button("Sens +", actions.sensitivity_up)
        self._smooth_down = Button("Smooth -", actions.smoothing_down)
        self._smooth_up = Button("Smooth +", actions.smoothing_up)
        self._reduce = Button("Motion", actions.toggle_reduce_motion)
        self._full = Button("Full", actions.toggle_fullscreen)
        self._quit = Button("Quit", actions.quit)
        self._buttons = [
            self._start,
            self._prev,
            self._mode,
            self._next,
            self._sens_down,
            self._sens_up,
            self._smooth_down,
            self._smooth_up,
            self._reduce,
            self._full,
            self._quit,
        ]

    def set_state(self, capturing: bool, mode_label: str, reduce_motion: bool = False) -> None:
        self._start.label = "Stop" if capturing else "Start"
        self._mode.label = mode_label
        self._reduce.label = "Motion-" if reduce_motion else "Motion+"

    def relayout(self, bar: pygame.Rect) -> None:
        pad = 6
        h = bar.height - pad * 2
        y = bar.y + pad
        # Variable widths: the mode button is wider.
        widths = {
            self._start: 70,
            self._prev: 36,
            self._mode: 150,
            self._next: 36,
            self._sens_down: 70,
            self._sens_up: 70,
            self._smooth_down: 86,
            self._smooth_up: 86,
            self._reduce: 76,
            self._full: 60,
            self._quit: 60,
        }
        x = bar.x + pad
        for btn in self._buttons:
            w = widths[btn]
            btn.set_rect(pygame.Rect(x, y, w, h))
            x += w + pad

    def handle_event(self, event: pygame.event.Event) -> bool:
        clicked = False
        for btn in self._buttons:
            if btn.handle_event(event):
                clicked = True
        return clicked

    def draw(self, surface: pygame.Surface, bar: pygame.Rect, font: pygame.font.Font) -> None:
        pygame.draw.rect(surface, COLOR_PANEL, bar)
        for btn in self._buttons:
            btn.draw(surface, font)
