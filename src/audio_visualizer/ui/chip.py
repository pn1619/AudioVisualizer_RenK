"""A tiny read-only labeled value box used to surface current control values."""

from __future__ import annotations

import pygame

from audio_visualizer.config import COLOR_TEXT
from audio_visualizer.ui.style import TEXT_PAD, draw_panel, fit_text


class Chip:
    """A non-interactive box that displays a single line of text (e.g. "1.50")."""

    def __init__(self, text: str = "") -> None:
        self.text = text
        self.rect = pygame.Rect(0, 0, 0, 0)

    def set_rect(self, rect: pygame.Rect) -> None:
        self.rect = rect

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        draw_panel(surface, self.rect, accent_border=True)
        label = fit_text(font, self.text, self.rect.width - TEXT_PAD * 2)
        text = font.render(label, True, COLOR_TEXT)
        surface.blit(text, text.get_rect(center=self.rect.center))
