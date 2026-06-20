"""A horizontal hue-picker bar: click or drag to choose a color (0..1 hue).

Used by the Appearance panel to pick the **Custom** color the ``Solid`` / ``Mono``
color schemes use. It paints a full rainbow gradient with a marker at the current
hue; clicking (or dragging) maps the x position to a hue and fires ``on_change``.
"""

from __future__ import annotations

from collections.abc import Callable

import pygame

from audio_visualizer.ui.style import draw_panel
from audio_visualizer.visuals._helpers import rainbow_color


class HueBar:
    """A rainbow strip; click/drag sets a hue in 0..1 and calls ``on_change``."""

    def __init__(self, on_change: Callable[[float], None]) -> None:
        self._on_change = on_change
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.hue = 0.0
        self._dragging = False

    def set_rect(self, rect: pygame.Rect) -> None:
        self.rect = rect

    def set_hue(self, hue: float) -> None:
        self.hue = float(hue) % 1.0

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Route one event. Returns True when consumed (click/drag on the bar)."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._dragging = True
                self._pick(event.pos[0])
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._dragging = False
        elif event.type == pygame.MOUSEMOTION and self._dragging:
            self._pick(event.pos[0])
            return True
        return False

    def _pick(self, x: int) -> None:
        if self.rect.width <= 0:
            return
        self.hue = max(0.0, min(1.0, (x - self.rect.left) / self.rect.width))
        self._on_change(self.hue)

    def draw(self, surface: pygame.Surface) -> None:
        if self.rect.width < 4 or self.rect.height < 4:
            return
        draw_panel(surface, self.rect)
        inner = self.rect.inflate(-4, -4)
        for i in range(inner.width):
            color = rainbow_color(i / max(1, inner.width - 1))
            pygame.draw.line(
                surface, color, (inner.left + i, inner.top), (inner.left + i, inner.bottom - 1)
            )
        mx = inner.left + int(self.hue * (inner.width - 1))
        pygame.draw.line(surface, (10, 10, 12), (mx, inner.top - 1), (mx, inner.bottom), 3)
        pygame.draw.line(surface, (255, 255, 255), (mx, inner.top - 1), (mx, inner.bottom), 1)
