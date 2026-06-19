"""A tiny padlock toggle: click to lock/unlock a randomizable option.

A *locked* item is held (not re-rolled) by Randomize / Next / auto-shuffle. The
icon is drawn with primitives (no font/emoji dependency): a body rectangle plus a
shackle arc that sits closed when locked and lifted/open when unlocked. The owner
sets :attr:`locked` each frame (the App is the source of truth) and wires
``on_click`` to flip it.
"""

from __future__ import annotations

from collections.abc import Callable

import pygame

from audio_visualizer.config import COLOR_TEXT_DIM
from audio_visualizer.ui.style import STYLE, draw_panel


class LockToggle:
    """A small clickable padlock indicator for one randomizable option."""

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
                self.on_click()
                return True
        return False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        draw_panel(surface, self.rect, hovered=self._hover, accent_fill=self.locked)
        color = STYLE.accent if self.locked else COLOR_TEXT_DIM
        # Geometry derived from the rect so it scales with the bar (no fixed pixels).
        size = min(self.rect.width, self.rect.height)
        body_w = max(6, int(size * 0.5))
        body_h = max(5, int(size * 0.38))
        cx = self.rect.centerx
        body = pygame.Rect(0, 0, body_w, body_h)
        body.center = (cx, self.rect.centery + int(size * 0.12))
        pygame.draw.rect(surface, color, body, border_radius=2)
        # Shackle: a half-ring above the body. Unlocked lifts it and opens the right leg.
        shackle_w = int(body_w * 0.6)
        radius = shackle_w // 2
        top = body.top - radius - (2 if self.locked else 4)
        arc_rect = pygame.Rect(cx - radius, top, shackle_w, radius * 2)
        pygame.draw.arc(surface, color, arc_rect, 0.0, 3.14159, 2)
        left_x = cx - radius
        pygame.draw.line(surface, color, (left_x, arc_rect.centery), (left_x, body.top), 2)
        right_x = cx + radius
        if self.locked:  # closed: right leg meets the body
            pygame.draw.line(surface, color, (right_x, arc_rect.centery), (right_x, body.top), 2)
        else:  # open: right leg stays up, leaving a gap
            pygame.draw.line(
                surface, color, (right_x, arc_rect.centery), (right_x, arc_rect.centery + 3), 2
            )
