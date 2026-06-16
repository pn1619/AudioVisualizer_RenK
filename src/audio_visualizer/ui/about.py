"""Modal "About" dialog: owner, license, version, build date, and runtime info."""

from __future__ import annotations

import platform

import pygame

from audio_visualizer.config import (
    APP_BUILD_DATE,
    APP_NAME,
    APP_OWNER,
    APP_VERSION,
    COLOR_BG,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
)
from audio_visualizer.ui.style import STYLE, draw_panel

_PANEL_W = 420
_PAD = 16
_LINE_GAP = 6
_CLOSE_H = 36


def _info_lines() -> list[tuple[str, str]]:
    """(label, value) rows shown in the dialog."""
    return [
        ("Owner", APP_OWNER),
        ("License", "Proprietary - all rights reserved"),
        ("Version", APP_VERSION),
        ("Build date", APP_BUILD_DATE),
        ("Python", platform.python_version()),
        ("pygame", getattr(pygame, "version", None) and pygame.version.ver or "?"),
    ]


class AboutDialog:
    """A centered modal showing app/build info; click Close or outside to dismiss."""

    def __init__(self) -> None:
        self.open = False
        self._hover_close = False

    def toggle(self) -> None:
        self.open = not self.open

    def _panel_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        line_h = 24
        height = _PAD * 3 + line_h * (len(_info_lines()) + 1) + _CLOSE_H
        rect = pygame.Rect(0, 0, _PANEL_W, height)
        rect.center = canvas.center
        return rect

    def _close_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        panel = self._panel_rect(canvas)
        return pygame.Rect(
            panel.x + _PAD, panel.bottom - _PAD - _CLOSE_H, panel.width - _PAD * 2, _CLOSE_H
        )

    def handle_event(self, event: pygame.event.Event, canvas: pygame.Rect) -> bool:
        if not self.open:
            return False
        if event.type == pygame.MOUSEMOTION:
            self._hover_close = self._close_rect(canvas).collidepoint(event.pos)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self._panel_rect(canvas).collidepoint(event.pos) or self._close_rect(
                canvas
            ).collidepoint(event.pos):
                self.open = False
            return True
        return False

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

        x = panel.x + _PAD
        y = panel.y + _PAD
        title = font.render(APP_NAME, True, STYLE.accent)
        surface.blit(title, (x, y))
        y += title.get_height() + _LINE_GAP

        for label, value in _info_lines():
            text = font_small.render(f"{label}:", True, COLOR_TEXT_DIM)
            surface.blit(text, (x, y))
            val = font_small.render(value, True, COLOR_TEXT)
            surface.blit(val, (x + 110, y))
            y += val.get_height() + _LINE_GAP

        self._draw_close(surface, canvas, font)

    def _draw_close(
        self, surface: pygame.Surface, canvas: pygame.Rect, font: pygame.font.Font
    ) -> None:
        rect = self._close_rect(canvas)
        draw_panel(surface, rect, hovered=self._hover_close, accent_border=True)
        text = font.render("Close", True, COLOR_TEXT)
        surface.blit(text, text.get_rect(center=rect.center))
