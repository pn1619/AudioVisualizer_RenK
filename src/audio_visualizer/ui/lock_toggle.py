"""A tiny pin toggle: click to hold/free a randomizable option.

A *held* (locked) item is not re-rolled by Randomize / Next / auto-shuffle. The
indicator is a small dot drawn with primitives (no font/emoji dependency): a
**filled accent dot** when held and a **hollow dim ring** when free, so the state
reads at a glance. Clicking flips the dot **immediately** (optimistic) and notifies
the owner; the App remains the source of truth and re-syncs :attr:`locked` on the
next state refresh.
"""

from __future__ import annotations

from collections.abc import Callable

import pygame

from audio_visualizer.config import COLOR_TEXT_DIM
from audio_visualizer.ui.style import STYLE, draw_panel


class LockToggle:
    """A small clickable pin/dot indicator for one randomizable option."""

    def __init__(self, on_click: Callable[[], None]) -> None:
        self.on_click = on_click
        self.locked = False
        self.rect = pygame.Rect(0, 0, 0, 0)
        self._hover = False

    def set_rect(self, rect: pygame.Rect) -> None:
        self.rect = rect

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self._hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                # Flip locally first so the dot updates this very frame, even if the
                # owner only re-pushes state on a mode rebuild.
                self.locked = not self.locked
                self.on_click()
                return True
        return False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        draw_panel(surface, self.rect, hovered=self._hover)
        center = self.rect.center
        radius = max(4, int(min(self.rect.width, self.rect.height) * 0.30))
        if self.locked:
            pygame.draw.circle(surface, STYLE.accent, center, radius)
            pygame.draw.circle(surface, STYLE.accent, center, radius + 2, 1)
        else:
            color = (235, 235, 245) if self._hover else COLOR_TEXT_DIM
            pygame.draw.circle(surface, color, center, radius, 2)
