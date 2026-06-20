"""Popup to pick the Solid/Mono custom color (hue bar + a live preview).

Opened from the control-bar **Color** dropdown when the user selects *Solid* or
*Mono* (so the picker appears right where the choice is made, instead of being
buried in the Appearance panel). It pairs a :class:`HueBar` with a preview swatch
and **Solid** / **Mono** buttons; the App wires the hue + scheme callbacks.
"""

from __future__ import annotations

import colorsys
from collections.abc import Callable
from dataclasses import dataclass

import pygame

from audio_visualizer.config import COLOR_BG, COLOR_PICK_SATURATION, COLOR_TEXT, COLOR_TEXT_DIM
from audio_visualizer.ui.hue_bar import HueBar
from audio_visualizer.ui.style import STYLE, TEXT_PAD, draw_panel, fit_text

_PANEL_W = 340
_PAD = 16
_HUE_H = 28
_PREVIEW_H = 34
_BTN_H = 34
_GAP = 10
_CAPTION_H = 18


@dataclass
class ColorPickerActions:
    """Callbacks invoked by the picker (App mutates theme + persists)."""

    set_hue: Callable[[float], None]
    set_scheme: Callable[[str], None]


class ColorPicker:
    """A small centered popup: hue bar + preview + Solid/Mono buttons."""

    def __init__(self, actions: ColorPickerActions) -> None:
        self.open = False
        self._set_scheme = actions.set_scheme
        self._hue = 0.0
        self._scheme = "solid"
        self._hover_close = False
        self._hue_bar = HueBar(self._on_hue)
        self._on_hue_cb = actions.set_hue

    def _on_hue(self, hue: float) -> None:
        self._hue = hue
        self._on_hue_cb(hue)

    def set_state(self, hue: float, scheme: str) -> None:
        self._hue = hue % 1.0
        self._hue_bar.set_hue(hue)
        self._scheme = scheme

    def toggle(self) -> None:
        self.open = not self.open

    # -- geometry -------------------------------------------------------------
    def _panel_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        height = (
            _PAD
            + _CAPTION_H
            + _HUE_H
            + _GAP
            + _PREVIEW_H
            + _GAP
            + _BTN_H
            + _GAP
            + _BTN_H  # close
            + _PAD
        )
        rect = pygame.Rect(0, 0, _PANEL_W, height)
        rect.center = canvas.center
        return rect

    def _hue_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        panel = self._panel_rect(canvas)
        y = panel.y + _PAD + _CAPTION_H
        return pygame.Rect(panel.x + _PAD, y, panel.width - _PAD * 2, _HUE_H)

    def _preview_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        hue = self._hue_rect(canvas)
        return pygame.Rect(hue.x, hue.bottom + _GAP, hue.width, _PREVIEW_H)

    def _button_rects(self, canvas: pygame.Rect) -> dict[str, pygame.Rect]:
        prev = self._preview_rect(canvas)
        gap = 8
        half = (prev.width - gap) // 2
        y = prev.bottom + _GAP
        return {
            "solid": pygame.Rect(prev.x, y, half, _BTN_H),
            "mono": pygame.Rect(prev.x + half + gap, y, prev.width - half - gap, _BTN_H),
        }

    def _close_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        panel = self._panel_rect(canvas)
        return pygame.Rect(
            panel.x + _PAD, panel.bottom - _PAD - _BTN_H, panel.width - _PAD * 2, _BTN_H
        )

    # -- input ----------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event, canvas: pygame.Rect) -> bool:
        if not self.open:
            return False
        self._hue_bar.set_rect(self._hue_rect(canvas))
        if self._hue_bar.handle_event(event):
            return True
        if event.type == pygame.MOUSEMOTION:
            self._hover_close = self._close_rect(canvas).collidepoint(event.pos)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._close_rect(canvas).collidepoint(event.pos):
                self.open = False
                return True
            for key, rect in self._button_rects(canvas).items():
                if rect.collidepoint(event.pos):
                    self._scheme = key
                    self._set_scheme(key)
                    return True
            if not self._panel_rect(canvas).collidepoint(event.pos):
                self.open = False
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

        title = font.render("Custom color", True, STYLE.accent)
        surface.blit(title, (panel.x + _PAD, panel.y - title.get_height() - 4))

        hue = self._hue_rect(canvas)
        caption = font_small.render("Drag to pick a hue:", True, COLOR_TEXT_DIM)
        surface.blit(caption, (hue.x, hue.y - caption.get_height() - 2))
        self._hue_bar.set_rect(hue)
        self._hue_bar.draw(surface)

        self._draw_preview(surface, self._preview_rect(canvas))

        for key, rect in self._button_rects(canvas).items():
            self._draw_button(
                surface, rect, key.capitalize(), font_small, active=self._scheme == key
            )

        rect = self._close_rect(canvas)
        draw_panel(surface, rect, hovered=self._hover_close, accent_border=True)
        text = font.render("Close", True, COLOR_TEXT)
        surface.blit(text, text.get_rect(center=rect.center))

    def _draw_preview(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Flat swatch for Solid; a light->dark ramp of the hue for Mono."""
        inner = rect.inflate(-4, -4)
        if self._scheme == "mono":
            for i in range(inner.width):
                val = 0.25 + 0.75 * (i / max(1, inner.width - 1))
                r, g, b = colorsys.hsv_to_rgb(self._hue, COLOR_PICK_SATURATION, val)
                col = (int(r * 255), int(g * 255), int(b * 255))
                x = inner.left + i
                pygame.draw.line(surface, col, (x, inner.top), (x, inner.bottom - 1))
        else:
            r, g, b = colorsys.hsv_to_rgb(self._hue, COLOR_PICK_SATURATION, 1.0)
            surface.fill((int(r * 255), int(g * 255), int(b * 255)), inner)
        pygame.draw.rect(surface, (255, 255, 255), rect, 1, border_radius=4)

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
