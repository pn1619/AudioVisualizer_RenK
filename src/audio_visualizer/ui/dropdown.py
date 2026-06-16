"""A minimal dropdown (combo) widget for picking a value from a list.

Closed it shows the current label + a caret; open it lists options below the
header (drawn on top of the canvas). Header and option text are truncated to fit
their box (never spill out), and the open list is nudged left so it stays inside
the window even when the header sits near the right edge.
"""

from __future__ import annotations

from collections.abc import Callable

import pygame

from audio_visualizer.config import COLOR_TEXT
from audio_visualizer.ui.style import TEXT_PAD, draw_panel, fit_text

_ROW_H = 28
# The open list is at least this wide so options stay readable even when the
# header box is narrow; it never grows past the right bound (set by the bar).
_MIN_LIST_W = 150


class Dropdown:
    """Header + expandable option list; calls ``on_select(key)`` on choice."""

    def __init__(
        self, on_select: Callable[[str], None], title: str = "", static_label: str = ""
    ) -> None:
        self._on_select = on_select
        self._title = title
        # When set, the header always shows this text (an action menu, not a value
        # picker) instead of the currently selected option.
        self._static_label = static_label
        self._options: list[tuple[str, str]] = []  # (key, label)
        self._selected_key = ""
        self.open = False
        self.rect = pygame.Rect(0, 0, 0, 0)
        self._hover_index = -1
        # Right edge the open list must stay within (window width); None = unbounded.
        self._bound_right: int | None = None

    def set_options(self, options: list[tuple[str, str]]) -> None:
        self._options = list(options)

    def set_selected(self, key: str) -> None:
        self._selected_key = key

    def set_rect(self, rect: pygame.Rect) -> None:
        self.rect = rect

    def set_bound_right(self, right: int) -> None:
        """Keep the open option list within ``right`` (the window's right edge)."""
        self._bound_right = right

    def toggle(self) -> None:
        self.open = not self.open

    @property
    def current_label(self) -> str:
        if self._static_label:
            return self._static_label
        selected = "Mode"
        for key, label in self._options:
            if key == self._selected_key:
                selected = label
                break
        return f"{self._title}: {selected}" if self._title else selected

    def _list_geometry(self) -> tuple[int, int]:
        """(x, width) of the open list, clamped to stay within the right bound."""
        width = max(self.rect.width, _MIN_LIST_W)
        x = self.rect.x
        if self._bound_right is not None:
            width = min(width, max(self.rect.width, self._bound_right - TEXT_PAD))
            if x + width > self._bound_right:
                x = max(0, self._bound_right - width)
        return x, width

    def _option_rects(self) -> list[pygame.Rect]:
        x, width = self._list_geometry()
        return [
            pygame.Rect(x, self.rect.bottom + i * _ROW_H, width, _ROW_H)
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
        if not self.open:
            return
        for i, rect in enumerate(self._option_rects()):
            key, label = self._options[i]
            draw_panel(
                surface, rect, hovered=i == self._hover_index, accent_fill=key == self._selected_key
            )
            fitted = fit_text(font, label, rect.width - TEXT_PAD * 2)
            text = font.render(fitted, True, COLOR_TEXT)
            surface.blit(text, text.get_rect(midleft=(rect.x + TEXT_PAD, rect.centery)))

    def _draw_header(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        draw_panel(surface, self.rect, accent_border=self.open)
        caret = "\u25b2" if self.open else "\u25bc"
        caret_surf = font.render(caret, True, COLOR_TEXT)
        # Reserve room for the caret on the right, then truncate the label to fit.
        label_w = self.rect.width - TEXT_PAD * 2 - caret_surf.get_width() - 4
        label = font.render(fit_text(font, self.current_label, label_w), True, COLOR_TEXT)
        surface.blit(label, label.get_rect(midleft=(self.rect.x + TEXT_PAD, self.rect.centery)))
        surface.blit(
            caret_surf,
            caret_surf.get_rect(midright=(self.rect.right - TEXT_PAD, self.rect.centery)),
        )
