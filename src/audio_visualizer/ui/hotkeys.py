"""Modal "Hotkeys" reference: lists the keyboard shortcuts the app responds to.

Mirrors :class:`AboutDialog` (dim backdrop, centered panel, Close/outside/Esc to
dismiss). The list is the single source of truth shown to the user; keep it in sync
with ``App._handle_key``.
"""

from __future__ import annotations

import pygame

from audio_visualizer.config import COLOR_BG, COLOR_TEXT, COLOR_TEXT_DIM
from audio_visualizer.ui.style import STYLE, draw_panel

_PANEL_W = 460
_PAD = 16
_LINE_GAP = 6
_CLOSE_H = 36


def _shortcut_lines() -> list[tuple[str, str]]:
    """(keys, action) rows. Mirror ``App._handle_key``."""
    return [
        ("Space", "Start / Stop capture"),
        ("\u2190 / [  ,  \u2192 / ]", "Previous / next mode"),
        ("1 - 9", "Jump to mode by number"),
        ("D", "Open the mode picker"),
        ("C", "Cycle color scheme"),
        ("R", "Randomize current mode"),
        ("A", "Toggle auto-cycle (shuffle)"),
        ("N", "Next shuffle item now"),
        ("M", "Toggle reduce-motion"),
        ("- / +", "Sensitivity down / up"),
        (", / .", "Smoothing down / up"),
        ("F5 / F6", "Size down / up"),
        ("F7 / F8", "Speed down / up"),
        ("F3", "Debug overlay"),
        ("F11", "Toggle fullscreen"),
        ("Esc", "Close modal / leave fullscreen"),
        ("Ctrl+Q", "Quit"),
    ]


class HotkeysDialog:
    """A centered modal listing keyboard shortcuts; Close/outside/Esc dismisses."""

    def __init__(self) -> None:
        self.open = False
        self._hover_close = False

    def toggle(self) -> None:
        self.open = not self.open

    def _panel_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        line_h = 22
        height = _PAD * 3 + line_h * (len(_shortcut_lines()) + 1) + _CLOSE_H
        height = min(height, canvas.height - 2 * _PAD)
        rect = pygame.Rect(0, 0, min(_PANEL_W, canvas.width - 2 * _PAD), height)
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
        title = font.render("Hotkeys", True, STYLE.accent)
        surface.blit(title, (x, y))
        y += title.get_height() + _LINE_GAP

        for keys, action in _shortcut_lines():
            key_text = font_small.render(keys, True, STYLE.accent)
            surface.blit(key_text, (x, y))
            act_text = font_small.render(action, True, COLOR_TEXT_DIM)
            surface.blit(act_text, (x + 150, y))
            y += act_text.get_height() + _LINE_GAP

        self._draw_close(surface, canvas, font)

    def _draw_close(
        self, surface: pygame.Surface, canvas: pygame.Rect, font: pygame.font.Font
    ) -> None:
        rect = self._close_rect(canvas)
        draw_panel(surface, rect, hovered=self._hover_close, accent_border=True)
        text = font.render("Close", True, COLOR_TEXT)
        surface.blit(text, text.get_rect(center=rect.center))
