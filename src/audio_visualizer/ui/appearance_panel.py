"""Modal panel to pick the UI appearance: control style, accent, font, cursor + color.

The first rows show ``Label … Value`` and clicking cycles to the next value. Below
them a **Custom color** section pairs a hue bar with **Solid** / **Mono** buttons so
the user can pick a single/mono color from one place (dragging the bar also switches
to a pick scheme so it takes effect immediately). The App owns the panel, feeds
current values via :meth:`set_state`, and wires each control to a callback.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from audio_visualizer.config import COLOR_BG, COLOR_TEXT, COLOR_TEXT_DIM
from audio_visualizer.ui.hue_bar import HueBar
from audio_visualizer.ui.style import STYLE, TEXT_PAD, draw_panel, fit_text

_ROW_KEYS: tuple[str, ...] = ("style", "accent", "font", "cursor")
_ROW_LABELS: dict[str, str] = {
    "style": "Control style",
    "accent": "Accent color",
    "font": "Text font",
    "cursor": "Mouse cursor",
}

_PANEL_W = 360
_ROW_H = 42
_PAD = 14
_HUE_H = 26  # height of the custom-color hue bar
_BTN_H = 30  # Solid / Mono buttons under the hue bar


@dataclass
class AppearanceActions:
    """Callbacks invoked when a control is used (App mutates state + persists)."""

    cycle_style: Callable[[], None]
    cycle_accent: Callable[[], None]
    cycle_font: Callable[[], None]
    cycle_cursor: Callable[[], None]
    set_hue: Callable[[float], None]
    set_color_scheme: Callable[[str], None]


class AppearancePanel:
    """A centered modal listing UI appearance settings + a custom-color picker."""

    def __init__(self, actions: AppearanceActions) -> None:
        self._actions: dict[str, Callable[[], None]] = {
            "style": actions.cycle_style,
            "accent": actions.cycle_accent,
            "font": actions.cycle_font,
            "cursor": actions.cycle_cursor,
        }
        self._set_color_scheme = actions.set_color_scheme
        self.open = False
        self._values: dict[str, str] = {key: "" for key in _ROW_KEYS}
        self._scheme = ""
        self._hover_key: str | None = None
        self._hover_close = False
        self._hue_bar = HueBar(actions.set_hue)

    def set_state(self, values: dict[str, str], hue: float = 0.0, scheme: str = "") -> None:
        self._values.update(values)
        self._hue_bar.set_hue(hue)
        self._scheme = scheme

    def toggle(self) -> None:
        self.open = not self.open

    # -- geometry -------------------------------------------------------------
    def _panel_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        height = (
            _PAD
            + _ROW_H * len(_ROW_KEYS)
            + 20  # section caption
            + _HUE_H
            + 8
            + _BTN_H  # Solid / Mono buttons
            + _PAD
            + _ROW_H  # close button
            + _PAD
        )
        rect = pygame.Rect(0, 0, _PANEL_W, height)
        rect.center = canvas.center
        return rect

    def _row_rects(self, canvas: pygame.Rect) -> list[tuple[str, pygame.Rect]]:
        panel = self._panel_rect(canvas)
        x = panel.x + _PAD
        w = panel.width - _PAD * 2
        rows: list[tuple[str, pygame.Rect]] = []
        y = panel.y + _PAD
        for key in _ROW_KEYS:
            rows.append((key, pygame.Rect(x, y, w, _ROW_H)))
            y += _ROW_H
        return rows

    def _hue_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        panel = self._panel_rect(canvas)
        x = panel.x + _PAD
        w = panel.width - _PAD * 2
        y = panel.y + _PAD + _ROW_H * len(_ROW_KEYS) + 20
        return pygame.Rect(x, y, w, _HUE_H)

    def _pick_button_rects(self, canvas: pygame.Rect) -> dict[str, pygame.Rect]:
        hue = self._hue_rect(canvas)
        gap = 8
        half = (hue.width - gap) // 2
        y = hue.bottom + 8
        return {
            "solid": pygame.Rect(hue.x, y, half, _BTN_H),
            "mono": pygame.Rect(hue.x + half + gap, y, hue.width - half - gap, _BTN_H),
        }

    def _close_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        panel = self._panel_rect(canvas)
        return pygame.Rect(
            panel.x + _PAD, panel.bottom - _PAD - _ROW_H, panel.width - _PAD * 2, _ROW_H
        )

    # -- input ----------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event, canvas: pygame.Rect) -> bool:
        if not self.open:
            return False
        self._hue_bar.set_rect(self._hue_rect(canvas))
        if self._hue_bar.handle_event(event):
            return True
        if event.type == pygame.MOUSEMOTION:
            self._hover_key = next(
                (k for k, r in self._row_rects(canvas) if r.collidepoint(event.pos)), None
            )
            self._hover_close = self._close_rect(canvas).collidepoint(event.pos)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._handle_click(event.pos, canvas)
        return False

    def _handle_click(self, pos: tuple[int, int], canvas: pygame.Rect) -> bool:
        if self._close_rect(canvas).collidepoint(pos):
            self.open = False
            return True
        for key, rect in self._pick_button_rects(canvas).items():
            if rect.collidepoint(pos):
                self._set_color_scheme(key)
                return True
        for key, rect in self._row_rects(canvas):
            if rect.collidepoint(pos):
                self._actions[key]()
                return True
        if not self._panel_rect(canvas).collidepoint(pos):
            self.open = False  # click outside the panel closes it
        return True

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

        title = font.render("Appearance", True, STYLE.accent)
        surface.blit(title, (panel.x + _PAD, panel.y - title.get_height() - 4))

        for key, rect in self._row_rects(canvas):
            self._draw_row(surface, rect, key, font, font_small, hovered=key == self._hover_key)

        hue = self._hue_rect(canvas)
        caption = font_small.render("Custom color \u2014 pick a hue, then:", True, COLOR_TEXT_DIM)
        surface.blit(caption, (hue.x, hue.y - caption.get_height() - 3))
        self._hue_bar.set_rect(hue)
        self._hue_bar.draw(surface)
        for key, rect in self._pick_button_rects(canvas).items():
            self._draw_button(
                surface, rect, key.capitalize(), font_small, active=self._scheme == key
            )

        self._draw_close(surface, canvas, font)

    def _draw_row(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        key: str,
        font: pygame.font.Font,
        font_small: pygame.font.Font,
        hovered: bool,
    ) -> None:
        draw_panel(surface, rect, hovered=hovered)
        label = font.render(_ROW_LABELS[key], True, COLOR_TEXT)
        surface.blit(label, label.get_rect(midleft=(rect.x + 12, rect.centery)))
        value = font_small.render(self._values.get(key, ""), True, STYLE.accent)
        surface.blit(value, value.get_rect(midright=(rect.right - 12, rect.centery)))

    @staticmethod
    def _draw_button(
        surface: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        font: pygame.font.Font,
        active: bool = False,
    ) -> None:
        draw_panel(surface, rect, accent_fill=active)
        text = font.render(fit_text(font, label, rect.width - TEXT_PAD * 2), True, COLOR_TEXT)
        surface.blit(text, text.get_rect(center=rect.center))

    def _draw_close(
        self, surface: pygame.Surface, canvas: pygame.Rect, font: pygame.font.Font
    ) -> None:
        rect = self._close_rect(canvas)
        draw_panel(surface, rect, hovered=self._hover_close, accent_border=True)
        text = font.render("Close", True, COLOR_TEXT)
        surface.blit(text, text.get_rect(center=rect.center))
