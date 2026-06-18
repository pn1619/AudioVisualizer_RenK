"""Modal panel for choosing the capture source (clickable device rows).

Mirrors :mod:`ui.background_panel`, but the rows are **dynamic**: the App
refreshes them from :func:`audio.devices.list_sources` when the panel opens and
feeds them via :meth:`set_state`. Clicking a row selects that source and closes;
the currently active row is marked. Opened from the ``Src`` button.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from audio_visualizer.config import COLOR_BG, COLOR_TEXT
from audio_visualizer.ui.style import STYLE, draw_panel

_PANEL_W = 460
_ROW_H = 38
_PAD = 12


@dataclass
class SourceActions:
    """Callback invoked when a device row is clicked (App switches + persists)."""

    select: Callable[[str], None]


class SourcePanel:
    """A centered modal listing capture sources; clicking a row selects it."""

    def __init__(self, actions: SourceActions) -> None:
        self._select = actions.select
        self.open = False
        # (source_id, label) rows; the App rebuilds this on open.
        self._rows: list[tuple[str, str]] = [("", "Default (system audio)")]
        self._active_id = ""
        self._hover_index: int | None = None
        self._hover_close = False

    def set_state(self, rows: list[tuple[str, str]], active_id: str) -> None:
        """Replace the device list and mark the active source."""
        self._rows = rows or [("", "Default (system audio)")]
        self._active_id = active_id

    def toggle(self) -> None:
        self.open = not self.open

    # -- geometry -------------------------------------------------------------
    def _panel_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        height = _PAD * 3 + _ROW_H * (len(self._rows) + 1)  # rows + close button
        height = min(height, max(_ROW_H * 3, canvas.height - 2 * _PAD))
        rect = pygame.Rect(0, 0, min(_PANEL_W, canvas.width - 2 * _PAD), height)
        rect.center = canvas.center
        return rect

    def _row_rects(self, canvas: pygame.Rect) -> list[tuple[int, pygame.Rect]]:
        panel = self._panel_rect(canvas)
        x = panel.x + _PAD
        w = panel.width - _PAD * 2
        rows: list[tuple[int, pygame.Rect]] = []
        y = panel.y + _PAD
        for i in range(len(self._rows)):
            rows.append((i, pygame.Rect(x, y, w, _ROW_H)))
            y += _ROW_H
        return rows

    def _close_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        panel = self._panel_rect(canvas)
        return pygame.Rect(
            panel.x + _PAD, panel.bottom - _PAD - _ROW_H, panel.width - _PAD * 2, _ROW_H
        )

    # -- input ----------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event, canvas: pygame.Rect) -> bool:
        """Consume events while open: a row click selects + closes; outside/Close dismisses."""
        if not self.open:
            return False
        if event.type == pygame.MOUSEMOTION:
            self._hover_index = next(
                (i for i, r in self._row_rects(canvas) if r.collidepoint(event.pos)), None
            )
            self._hover_close = self._close_rect(canvas).collidepoint(event.pos)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._close_rect(canvas).collidepoint(event.pos):
                self.open = False
                return True
            for i, rect in self._row_rects(canvas):
                if rect.collidepoint(event.pos):
                    self._select(self._rows[i][0])
                    self.open = False
                    return True
            if not self._panel_rect(canvas).collidepoint(event.pos):
                self.open = False  # click outside the panel closes it
            return True
        return False

    # -- draw -----------------------------------------------------------------
    def draw(
        self,
        surface: pygame.Surface,
        canvas: pygame.Rect,
        font: pygame.font.Font,
        font_small: pygame.font.Font,
    ) -> None:
        if not self.open:
            return
        dim = pygame.Surface(canvas.size, pygame.SRCALPHA)
        dim.fill((*COLOR_BG, 200))
        surface.blit(dim, canvas.topleft)

        panel = self._panel_rect(canvas)
        draw_panel(surface, panel, accent_border=True)

        title = font.render("Sound source", True, STYLE.accent)
        surface.blit(title, (panel.x + _PAD, panel.y - title.get_height() - 4))

        for i, rect in self._row_rects(canvas):
            self._draw_row(surface, rect, i, font, font_small)
        self._draw_close(surface, canvas, font)

    def _draw_row(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        index: int,
        font: pygame.font.Font,
        font_small: pygame.font.Font,
    ) -> None:
        source_id, label = self._rows[index]
        active = source_id == self._active_id
        draw_panel(surface, rect, hovered=index == self._hover_index, accent_border=active)
        text = font_small.render(label, True, COLOR_TEXT)
        # Clip overly long device names to the row width.
        max_w = rect.width - 70
        if text.get_width() > max_w > 0:
            text = text.subsurface((0, 0, max_w, text.get_height()))
        surface.blit(text, text.get_rect(midleft=(rect.x + 10, rect.centery)))
        if active:
            mark = font_small.render("active", True, STYLE.accent)
            surface.blit(mark, mark.get_rect(midright=(rect.right - 10, rect.centery)))

    def _draw_close(
        self, surface: pygame.Surface, canvas: pygame.Rect, font: pygame.font.Font
    ) -> None:
        rect = self._close_rect(canvas)
        draw_panel(surface, rect, hovered=self._hover_close, accent_border=True)
        text = font.render("Close", True, COLOR_TEXT)
        surface.blit(text, text.get_rect(center=rect.center))
