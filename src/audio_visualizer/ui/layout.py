"""Computes UI rectangles from the current surface size (resize-safe).

Single owner of positioning so no other module hard-codes pixel coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from audio_visualizer.config import CONTROL_BAR_HEIGHT, MIN_WINDOW_SIZE


@dataclass(frozen=True)
class Layout:
    """Rectangles for the control bar and main canvas at a given size."""

    width: int
    height: int
    control_bar: pygame.Rect
    canvas: pygame.Rect
    show_control_bar: bool

    @classmethod
    def compute(
        cls,
        size: tuple[int, int],
        show_control_bar: bool = True,
        control_bar_height: int | None = None,
    ) -> Layout:
        """Derive layout rects from ``size``, clamped to the minimum window size.

        ``control_bar_height`` lets the caller (App) pass the bar's flowed height,
        which grows when widgets wrap on narrow windows; it defaults to the static
        :data:`CONTROL_BAR_HEIGHT`. Hidden bar -> 0.
        """
        w = max(MIN_WINDOW_SIZE[0], int(size[0]))
        h = max(MIN_WINDOW_SIZE[1], int(size[1]))
        if not show_control_bar:
            bar_h = 0
        elif control_bar_height is not None:
            bar_h = max(0, int(control_bar_height))
        else:
            bar_h = CONTROL_BAR_HEIGHT
        control_bar = pygame.Rect(0, 0, w, bar_h)
        canvas = pygame.Rect(0, bar_h, w, h - bar_h)
        return cls(w, h, control_bar, canvas, show_control_bar)
