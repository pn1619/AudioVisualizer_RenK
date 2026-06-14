"""A tiny read-only labeled value box used to surface current control values."""

from __future__ import annotations

import pygame

from audio_visualizer.config import COLOR_ACCENT, COLOR_BG, COLOR_TEXT


class Chip:
    """A non-interactive box that displays a single line of text (e.g. "1.50")."""

    def __init__(self, text: str = "") -> None:
        self.text = text
        self.rect = pygame.Rect(0, 0, 0, 0)

    def set_rect(self, rect: pygame.Rect) -> None:
        self.rect = rect

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        pygame.draw.rect(surface, COLOR_BG, self.rect, border_radius=6)
        pygame.draw.rect(surface, COLOR_ACCENT, self.rect, width=1, border_radius=6)
        label = font.render(self.text, True, COLOR_TEXT)
        surface.blit(label, label.get_rect(center=self.rect.center))
