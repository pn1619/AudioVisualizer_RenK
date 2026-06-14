"""Minimal clickable button widget (no external UI dependency)."""

from __future__ import annotations

from collections.abc import Callable

import pygame

from audio_visualizer.config import (
    COLOR_ACCENT,
    COLOR_PANEL,
    COLOR_PANEL_HOVER,
    COLOR_TEXT,
)


class Button:
    """A rectangle with a label that invokes a callback when clicked."""

    def __init__(self, label: str, on_click: Callable[[], None]) -> None:
        self.label = label
        self.on_click = on_click
        self.rect = pygame.Rect(0, 0, 0, 0)
        self._hover = False

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
        bg = COLOR_PANEL_HOVER if self._hover else COLOR_PANEL
        pygame.draw.rect(surface, bg, self.rect, border_radius=6)
        if self._hover:
            pygame.draw.rect(surface, COLOR_ACCENT, self.rect, width=1, border_radius=6)
        text = font.render(self.label, True, COLOR_TEXT)
        text_rect = text.get_rect(center=self.rect.center)
        surface.blit(text, text_rect)
