"""Minimal clickable button widget (no external UI dependency)."""

from __future__ import annotations

from collections.abc import Callable

import pygame

from audio_visualizer.config import COLOR_TEXT
from audio_visualizer.ui.style import TEXT_PAD, draw_panel, fit_text


class Button:
    """A rectangle with a label that invokes a callback when clicked."""

    def __init__(self, label: str, on_click: Callable[[], None]) -> None:
        self.label = label
        self.on_click = on_click
        self.rect = pygame.Rect(0, 0, 0, 0)
        self._hover = False
        # When True the button paints with the accent fill (an on/off toggle look).
        self.active = False

    def set_rect(self, rect: pygame.Rect) -> None:
        self.rect = rect

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Update hover/click state. Returns True if this button was clicked."""
        if event.type == pygame.MOUSEMOTION:
            self._hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.on_click()
                return True
        return False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        draw_panel(surface, self.rect, hovered=self._hover, accent_fill=self.active)
        label = fit_text(font, self.label, self.rect.width - TEXT_PAD * 2)
        text = font.render(label, True, COLOR_TEXT)
        surface.blit(text, text.get_rect(center=self.rect.center))
