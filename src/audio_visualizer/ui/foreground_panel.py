"""Modal panel for the global foreground layer (dropdown menus).

Mirror of :mod:`~audio_visualizer.ui.background_panel`: each row is a ``Label`` +
a **dropdown**. The App owns the panel, feeds current selections via
:meth:`set_state`, and wires each dropdown to a callback that mutates + persists.
Opened from the ``FG`` control-bar button.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from audio_visualizer.config import COLOR_BG, COLOR_TEXT
from audio_visualizer.ui.dropdown import Dropdown
from audio_visualizer.ui.style import STYLE, draw_panel

_ROW_KEYS: tuple[str, ...] = (
    "mode",
    "intensity",
    "direction",
    "color",
    "opacity",
    "flash",
    "reactivity",
    "wind",
)
_ROW_LABELS: dict[str, str] = {
    "mode": "Foreground",
    "intensity": "Intensity",
    "direction": "Direction",
    "color": "Color",
    "opacity": "Opacity",
    "flash": "Flash (Lightning)",
    "reactivity": "Reactivity",
    "wind": "Wind",
}

_PANEL_W = 400
_ROW_H = 34
_PAD = 14
_GAP = 8
_LABEL_W = 150


@dataclass
class ForegroundActions:
    """Callbacks invoked when a dropdown value is chosen (App mutates + persists)."""

    set_mode: Callable[[str], None]
    set_intensity: Callable[[str], None]
    set_direction: Callable[[str], None]
    set_color: Callable[[str], None]
    set_opacity: Callable[[str], None]
    set_flash: Callable[[str], None]
    set_reactivity: Callable[[str], None]
    set_wind: Callable[[str], None]


class ForegroundPanel:
    """A centered modal listing foreground settings; each row is a dropdown."""

    def __init__(
        self,
        actions: ForegroundActions,
        mode_options: list[tuple[str, str]],
        intensity_options: list[tuple[str, str]],
        direction_options: list[tuple[str, str]],
        color_options: list[tuple[str, str]],
        opacity_options: list[tuple[str, str]],
        flash_options: list[tuple[str, str]],
        reactivity_options: list[tuple[str, str]],
        wind_options: list[tuple[str, str]],
    ) -> None:
        self.open = False
        self._hover_close = False
        self._dd: dict[str, Dropdown] = {
            "mode": Dropdown(actions.set_mode),
            "intensity": Dropdown(actions.set_intensity),
            "direction": Dropdown(actions.set_direction),
            "color": Dropdown(actions.set_color),
            "opacity": Dropdown(actions.set_opacity),
            "flash": Dropdown(actions.set_flash),
            "reactivity": Dropdown(actions.set_reactivity),
            "wind": Dropdown(actions.set_wind),
        }
        self._dd["mode"].set_options(mode_options)
        self._dd["intensity"].set_options(intensity_options)
        self._dd["direction"].set_options(direction_options)
        self._dd["color"].set_options(color_options)
        self._dd["opacity"].set_options(opacity_options)
        self._dd["flash"].set_options(flash_options)
        self._dd["reactivity"].set_options(reactivity_options)
        self._dd["wind"].set_options(wind_options)

    def set_state(self, values: dict[str, str]) -> None:
        """Select each dropdown's current option by key."""
        for key, dd in self._dd.items():
            if key in values:
                dd.set_selected(values[key])

    def toggle(self) -> None:
        self.open = not self.open
        if not self.open:
            self._close_dropdowns()

    def _dropdowns(self) -> list[Dropdown]:
        return [self._dd[key] for key in _ROW_KEYS]

    def _close_dropdowns(self) -> None:
        for dd in self._dropdowns():
            dd.open = False

    # -- geometry -------------------------------------------------------------
    def _panel_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        height = _PAD * 2 + len(_ROW_KEYS) * (_ROW_H + _GAP) + _GAP + _ROW_H  # rows + close
        rect = pygame.Rect(0, 0, _PANEL_W, height)
        rect.center = canvas.center
        return rect

    def _row_rects(self, canvas: pygame.Rect) -> list[tuple[str, pygame.Rect, pygame.Rect]]:
        """(key, label_rect, dropdown_rect) for each row."""
        panel = self._panel_rect(canvas)
        x = panel.x + _PAD
        w = panel.width - _PAD * 2
        rows: list[tuple[str, pygame.Rect, pygame.Rect]] = []
        y = panel.y + _PAD
        for key in _ROW_KEYS:
            label = pygame.Rect(x, y, _LABEL_W, _ROW_H)
            dd = pygame.Rect(x + _LABEL_W, y, w - _LABEL_W, _ROW_H)
            rows.append((key, label, dd))
            y += _ROW_H + _GAP
        return rows

    def _close_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        panel = self._panel_rect(canvas)
        return pygame.Rect(
            panel.x + _PAD, panel.bottom - _PAD - _ROW_H, panel.width - _PAD * 2, _ROW_H
        )

    def _sync_widgets(self, canvas: pygame.Rect) -> None:
        panel = self._panel_rect(canvas)
        for key, _label, dd_rect in self._row_rects(canvas):
            self._dd[key].set_rect(dd_rect)
            self._dd[key].set_bound_right(panel.right - _PAD)

    # -- input ----------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event, canvas: pygame.Rect) -> bool:
        if not self.open:
            return False
        self._sync_widgets(canvas)
        for dd in self._dropdowns():
            if dd.handle_event(event):
                if dd.open:  # keep only the just-opened dropdown expanded
                    for other in self._dropdowns():
                        if other is not dd:
                            other.open = False
                return True
        if event.type == pygame.MOUSEMOTION:
            self._hover_close = self._close_rect(canvas).collidepoint(event.pos)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._close_rect(canvas).collidepoint(event.pos):
                self.open = False
                self._close_dropdowns()
                return True
            if not self._panel_rect(canvas).collidepoint(event.pos):
                self.open = False
                self._close_dropdowns()
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
        self._sync_widgets(canvas)

        title = font.render("Foreground", True, STYLE.accent)
        surface.blit(title, (panel.x + _PAD, panel.y - title.get_height() - 4))

        for key, label_rect, _dd_rect in self._row_rects(canvas):
            label = font.render(_ROW_LABELS[key], True, COLOR_TEXT)
            surface.blit(label, label.get_rect(midleft=(label_rect.x, label_rect.centery)))

        self._draw_close(surface, canvas, font)

        dds = self._dropdowns()
        open_dd = next((dd for dd in dds if dd.open), None)
        for dd in dds:
            if dd is not open_dd:
                dd.draw(surface, font_small)
        if open_dd is not None:
            open_dd.draw(surface, font_small)

    def _draw_close(
        self, surface: pygame.Surface, canvas: pygame.Rect, font: pygame.font.Font
    ) -> None:
        rect = self._close_rect(canvas)
        draw_panel(surface, rect, hovered=self._hover_close, accent_border=True)
        text = font.render("Close", True, COLOR_TEXT)
        surface.blit(text, text.get_rect(center=rect.center))
