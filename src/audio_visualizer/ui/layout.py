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
    def compute(cls, size: tuple[int, int], show_control_bar: bool = True) -> Layout:
        """Derive layout rects from ``size``, clamped to the minimum window size."""
        w = max(MIN_WINDOW_SIZE[0], int(size[0]))
        h = max(MIN_WINDOW_SIZE[1], int(size[1]))
        bar_h = CONTROL_BAR_HEIGHT if show_control_bar else 0
        control_bar = pygame.Rect(0, 0, w, bar_h)
        canvas = pygame.Rect(0, bar_h, w, h - bar_h)
        return cls(w, h, control_bar, canvas, show_control_bar)
