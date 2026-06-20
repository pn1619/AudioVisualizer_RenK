"""Popup to pick the Solid / Mono / Stereo custom color(s).

Opened from the control-bar **Color** dropdown when the user selects *Solid*,
*Mono* or *Stereo* (so the picker appears right where the choice is made, instead
of being buried in the Appearance panel). It pairs a :class:`HueBar` with a live
preview swatch and **Solid / Mono / Stereo** buttons; Stereo reveals a *second*
hue bar (left channel + right channel) and previews the gradient between them.
The App wires the hue + scheme callbacks.
"""

from __future__ import annotations

import colorsys
from collections.abc import Callable
from dataclasses import dataclass

import pygame

from audio_visualizer.config import COLOR_BG, COLOR_PICK_SATURATION, COLOR_TEXT, COLOR_TEXT_DIM
from audio_visualizer.ui.hue_bar import HueBar
from audio_visualizer.ui.style import STYLE, TEXT_PAD, draw_panel, fit_text

_PANEL_W = 360
_PAD = 16
_HUE_H = 28
_PREVIEW_H = 34
_BTN_H = 34
_GAP = 10
_CAPTION_H = 18


def _hsv(hue: float, val: float = 1.0) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(hue % 1.0, COLOR_PICK_SATURATION, val)
    return (int(r * 255), int(g * 255), int(b * 255))


@dataclass
class ColorPickerActions:
    """Callbacks invoked by the picker (App mutates theme + persists)."""

    set_hue: Callable[[float], None]
    set_hue2: Callable[[float], None]
    set_scheme: Callable[[str], None]


class ColorPicker:
    """A small centered popup: hue bar(s) + preview + Solid/Mono/Stereo buttons."""

    def __init__(self, actions: ColorPickerActions) -> None:
        self.open = False
        self._set_scheme = actions.set_scheme
        self._hue = 0.0
        self._hue2 = 0.0
        self._scheme = "solid"
        self._hover_close = False
        self._hue_bar = HueBar(actions.set_hue)
        self._hue_bar2 = HueBar(actions.set_hue2)

    def set_state(self, hue: float, scheme: str, hue2: float = 0.0) -> None:
        self._hue = hue % 1.0
        self._hue2 = hue2 % 1.0
        self._hue_bar.set_hue(hue)
        self._hue_bar2.set_hue(hue2)
        self._scheme = scheme

    def toggle(self) -> None:
        self.open = not self.open

    @property
    def _is_stereo(self) -> bool:
        return self._scheme == "stereo"

    # -- geometry -------------------------------------------------------------
    def _layout(self, canvas: pygame.Rect) -> dict[str, pygame.Rect]:
        """Stack the sections top-down; height grows when Stereo adds a 2nd bar."""
        rows = 2 if self._is_stereo else 1  # hue bar rows
        height = (
            _PAD
            + rows * (_CAPTION_H + _HUE_H + _GAP)
            + _PREVIEW_H
            + _GAP
            + _BTN_H
            + _GAP
            + _BTN_H  # close
            + _PAD
        )
        panel = pygame.Rect(0, 0, _PANEL_W, height)
        panel.center = canvas.center
        x = panel.x + _PAD
        w = panel.width - _PAD * 2
        rects: dict[str, pygame.Rect] = {"panel": panel}
        y = panel.y + _PAD + _CAPTION_H
        rects["hue"] = pygame.Rect(x, y, w, _HUE_H)
        y += _HUE_H + _GAP
        if self._is_stereo:
            y += _CAPTION_H
            rects["hue2"] = pygame.Rect(x, y, w, _HUE_H)
            y += _HUE_H + _GAP
        rects["preview"] = pygame.Rect(x, y, w, _PREVIEW_H)
        y += _PREVIEW_H + _GAP
        third = (w - 2 * 8) // 3
        rects["solid"] = pygame.Rect(x, y, third, _BTN_H)
        rects["mono"] = pygame.Rect(x + third + 8, y, third, _BTN_H)
        rects["stereo"] = pygame.Rect(x + 2 * (third + 8), y, w - 2 * (third + 8), _BTN_H)
        rects["close"] = pygame.Rect(x, panel.bottom - _PAD - _BTN_H, w, _BTN_H)
        return rects

    # -- input ----------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event, canvas: pygame.Rect) -> bool:
        if not self.open:
            return False
        rects = self._layout(canvas)
        self._hue_bar.set_rect(rects["hue"])
        if self._hue_bar.handle_event(event):
            return True
        if self._is_stereo:
            self._hue_bar2.set_rect(rects["hue2"])
            if self._hue_bar2.handle_event(event):
                return True
        if event.type == pygame.MOUSEMOTION:
            self._hover_close = rects["close"].collidepoint(event.pos)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if rects["close"].collidepoint(event.pos):
                self.open = False
                return True
            for key in ("solid", "mono", "stereo"):
                if rects[key].collidepoint(event.pos):
                    self._scheme = key
                    self._set_scheme(key)
                    return True
            if not rects["panel"].collidepoint(event.pos):
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

        rects = self._layout(canvas)
        panel = rects["panel"]
        draw_panel(surface, panel, accent_border=True)

        title = font.render("Custom color", True, STYLE.accent)
        surface.blit(title, (panel.x + _PAD, panel.y - title.get_height() - 4))

        primary_label = "Left channel:" if self._is_stereo else "Drag to pick a hue:"
        self._draw_bar(surface, rects["hue"], primary_label, self._hue_bar, font_small)
        if self._is_stereo:
            self._draw_bar(surface, rects["hue2"], "Right channel:", self._hue_bar2, font_small)

        self._draw_preview(surface, rects["preview"])

        for key in ("solid", "mono", "stereo"):
            self._draw_button(
                surface, rects[key], key.capitalize(), font_small, active=self._scheme == key
            )

        draw_panel(surface, rects["close"], hovered=self._hover_close, accent_border=True)
        text = font.render("Close", True, COLOR_TEXT)
        surface.blit(text, text.get_rect(center=rects["close"].center))

    @staticmethod
    def _draw_bar(
        surface: pygame.Surface,
        rect: pygame.Rect,
        caption: str,
        bar: HueBar,
        font: pygame.font.Font,
    ) -> None:
        label = font.render(caption, True, COLOR_TEXT_DIM)
        surface.blit(label, (rect.x, rect.y - label.get_height() - 2))
        bar.set_rect(rect)
        bar.draw(surface)

    def _draw_preview(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Flat swatch (Solid), light->dark ramp (Mono) or hue gradient (Stereo)."""
        inner = rect.inflate(-4, -4)
        if self._scheme == "solid":
            surface.fill(_hsv(self._hue, 1.0), inner)
        else:
            for i in range(inner.width):
                f = i / max(1, inner.width - 1)
                if self._scheme == "mono":
                    col = _hsv(self._hue, 0.25 + 0.75 * f)
                else:  # stereo gradient: left hue -> right hue
                    col = (
                        int(_hsv(self._hue)[0] * (1 - f) + _hsv(self._hue2)[0] * f),
                        int(_hsv(self._hue)[1] * (1 - f) + _hsv(self._hue2)[1] * f),
                        int(_hsv(self._hue)[2] * (1 - f) + _hsv(self._hue2)[2] * f),
                    )
                x = inner.left + i
                pygame.draw.line(surface, col, (x, inner.top), (x, inner.bottom - 1))
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
