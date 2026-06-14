"""A minimal dropdown (combo) widget for picking a value from a list.

Closed it shows the current label + a caret; open it lists options below the
header (drawn on top of the canvas). No external UI dependency.
"""

from __future__ import annotations

from collections.abc import Callable

import pygame

from audio_visualizer.config import (
    COLOR_ACCENT,
    COLOR_PANEL,
    COLOR_PANEL_HOVER,
    COLOR_TEXT,
)

_ROW_H = 28


class Dropdown:
    """Header + expandable option list; calls ``on_select(key)`` on choice."""

    def __init__(self, on_select: Callable[[str], None], title: str = "") -> None:
        self._on_select = on_select
        self._title = title
        self._options: list[tuple[str, str]] = []  # (key, label)
        self._selected_key = ""
        self.open = False
        self.rect = pygame.Rect(0, 0, 0, 0)
        self._hover_index = -1

    def set_options(self, options: list[tuple[str, str]]) -> None:
        self._options = list(options)

    def set_selected(self, key: str) -> None:
        self._selected_key = key

    def set_rect(self, rect: pygame.Rect) -> None:
        self.rect = rect

    def toggle(self) -> None:
        self.open = not self.open

    @property
    def current_label(self) -> str:
        selected = "Mode"
        for key, label in self._options:
            if key == self._selected_key:
                selected = label
                break
        return f"{self._title}: {selected}" if self._title else selected

    def _option_rects(self) -> list[pygame.Rect]:
        return [
            pygame.Rect(self.rect.x, self.rect.bottom + i * _ROW_H, self.rect.width, _ROW_H)
            for i in range(len(self._options))
        ]

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True if the event was consumed by the dropdown."""
        if event.type == pygame.MOUSEMOTION and self.open:
            self._hover_index = -1
            for i, r in enumerate(self._option_rects()):
                if r.collidepoint(event.pos):
                    self._hover_index = i
                    break
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.open = not self.open
                return True
            if self.open:
                for i, r in enumerate(self._option_rects()):
                    if r.collidepoint(event.pos):
                        self.open = False
                        self._selected_key = self._options[i][0]
                        self._on_select(self._selected_key)
                        return True
                self.open = False  # click outside the open list just closes it
                return True
        return False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        self._draw_header(surface, font)
        if self.open:
            for i, (key, label) in enumerate(self._options):
                rect = self._option_rects()[i]
                hovered = i == self._hover_index
                bg = COLOR_PANEL_HOVER if hovered else COLOR_PANEL
                pygame.draw.rect(surface, bg, rect)
                if key == self._selected_key:
                    pygame.draw.rect(surface, COLOR_ACCENT, rect, width=1)
                text = font.render(label, True, COLOR_TEXT)
                surface.blit(text, text.get_rect(midleft=(rect.x + 8, rect.centery)))

    def _draw_header(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        pygame.draw.rect(surface, COLOR_PANEL, self.rect, border_radius=6)
        if self.open:
            pygame.draw.rect(surface, COLOR_ACCENT, self.rect, width=1, border_radius=6)
        caret = "\u25b2" if self.open else "\u25bc"
        text = font.render(f"{self.current_label}  {caret}", True, COLOR_TEXT)
        surface.blit(text, text.get_rect(midleft=(self.rect.x + 8, self.rect.centery)))
