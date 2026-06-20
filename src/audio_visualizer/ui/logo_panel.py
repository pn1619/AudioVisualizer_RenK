"""Modal panel for the RenK logo overlay settings (clickable, value-cycling rows).

Kept deliberately simple: each row shows ``Label … Value`` and clicking it cycles
to the next value (or toggles on/off). The App owns the panel, feeds it the current
values via :meth:`set_state`, and wires each row to a callback.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from audio_visualizer.config import COLOR_BG, COLOR_TEXT
from audio_visualizer.ui.style import STYLE, draw_panel

_ROW_KEYS: tuple[str, ...] = (
    "enabled",
    "color",
    "opacity",
    "size",
    "position",
    "spin",
    "emit",
    "shockwave",
    "glow",
    "throb",
)
_ROW_LABELS: dict[str, str] = {
    "enabled": "Show logo",
    "color": "Color",
    "opacity": "Transparency",
    "size": "Size",
    "position": "Position",
    "spin": "Spin",
    "emit": "Emit particles",
    "shockwave": "Shockwave ring",
    "glow": "Beat glow",
    "throb": "Throb",
}

_PANEL_W = 360
_ROW_H = 40
_PAD = 12


@dataclass
class LogoPanelActions:
    """Callbacks invoked when a row is clicked (App mutates state + persists)."""

    toggle_enabled: Callable[[], None]
    cycle_color: Callable[[], None]
    cycle_opacity: Callable[[], None]
    cycle_size: Callable[[], None]
    cycle_position: Callable[[], None]
    cycle_spin: Callable[[], None]
    toggle_emit: Callable[[], None]
    toggle_shockwave: Callable[[], None]
    toggle_glow: Callable[[], None]
    toggle_throb: Callable[[], None]


class LogoPanel:
    """A centered modal listing the logo settings; rows cycle their value on click."""

    def __init__(self, actions: LogoPanelActions) -> None:
        self._actions: dict[str, Callable[[], None]] = {
            "enabled": actions.toggle_enabled,
            "color": actions.cycle_color,
            "opacity": actions.cycle_opacity,
            "size": actions.cycle_size,
            "position": actions.cycle_position,
            "spin": actions.cycle_spin,
            "emit": actions.toggle_emit,
            "shockwave": actions.toggle_shockwave,
            "glow": actions.toggle_glow,
            "throb": actions.toggle_throb,
        }
        self.open = False
        self._values: dict[str, str] = {key: "" for key in _ROW_KEYS}
        self._hover_key: str | None = None
        self._hover_close = False

    def set_state(self, values: dict[str, str]) -> None:
        """Update the displayed value text for each row."""
        self._values.update(values)

    def toggle(self) -> None:
        self.open = not self.open

    # -- geometry -------------------------------------------------------------
    def _panel_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        height = _PAD * 3 + _ROW_H * (len(_ROW_KEYS) + 1)  # rows + close button
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

    def _close_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        panel = self._panel_rect(canvas)
        return pygame.Rect(
            panel.x + _PAD, panel.bottom - _PAD - _ROW_H, panel.width - _PAD * 2, _ROW_H
        )

    # -- input ----------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event, canvas: pygame.Rect) -> bool:
        """Consume events while open: row clicks cycle values; outside/close dismisses."""
        if not self.open:
            return False
        if event.type == pygame.MOUSEMOTION:
            self._hover_key = next(
                (k for k, r in self._row_rects(canvas) if r.collidepoint(event.pos)), None
            )
            self._hover_close = self._close_rect(canvas).collidepoint(event.pos)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._close_rect(canvas).collidepoint(event.pos):
                self.open = False
                return True
            for key, rect in self._row_rects(canvas):
                if rect.collidepoint(event.pos):
                    self._actions[key]()
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

        title = font.render("RenK Logo", True, STYLE.accent)
        surface.blit(title, (panel.x + _PAD, panel.y - title.get_height() - 4))

        for key, rect in self._row_rects(canvas):
            self._draw_row(surface, rect, key, font, font_small, hovered=key == self._hover_key)
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
        surface.blit(label, label.get_rect(midleft=(rect.x + 10, rect.centery)))
        value = font_small.render(self._values.get(key, ""), True, STYLE.accent)
        surface.blit(value, value.get_rect(midright=(rect.right - 10, rect.centery)))

    def _draw_close(
        self, surface: pygame.Surface, canvas: pygame.Rect, font: pygame.font.Font
    ) -> None:
        rect = self._close_rect(canvas)
        draw_panel(surface, rect, hovered=self._hover_close, accent_border=True)
        text = font.render("Close", True, COLOR_TEXT)
        surface.blit(text, text.get_rect(center=rect.center))
