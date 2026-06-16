"""Shared, runtime-switchable UI look (flat vs glass) + a small text helper.

Widgets read the module-level :data:`STYLE` singleton at draw time instead of
hard-coding colors/shapes, so the Appearance panel can flip the whole UI's style
live. All panel/button/dropdown backgrounds go through :func:`draw_panel` so the
two styles live in exactly one place.
"""

from __future__ import annotations

import pygame

from audio_visualizer.config import (
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_PANEL,
    COLOR_PANEL_HOVER,
    UI_STYLE_DEFAULT,
    UI_STYLES,
)

# Padding between a widget's edge and its text (used for truncation + draw).
TEXT_PAD = 8
# Flat-style corner radius (glass uses a full pill radius instead).
_FLAT_RADIUS = 8


class UiStyle:
    """Mutable, process-wide UI appearance state read by widgets at draw time."""

    def __init__(self) -> None:
        self.style: str = UI_STYLE_DEFAULT
        self.accent: tuple[int, int, int] = COLOR_ACCENT

    def set_style(self, style: str) -> None:
        if style in UI_STYLES:
            self.style = style


STYLE = UiStyle()


def _radius(rect: pygame.Rect) -> int:
    """Corner radius for ``rect`` under the current style (pill for glass)."""
    return rect.height // 2 if STYLE.style == "glass" else _FLAT_RADIUS


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    """Blend color ``a`` toward ``b`` by ``t`` in 0..1."""
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))  # type: ignore[return-value]


def draw_panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    *,
    hovered: bool = False,
    accent_border: bool = False,
    accent_fill: bool = False,
) -> None:
    """Draw a widget background in the current style.

    ``hovered`` lightens the fill; ``accent_border`` outlines in the accent;
    ``accent_fill`` tints the fill toward the accent (selected/active controls).
    """
    radius = _radius(rect)
    accent = STYLE.accent
    if STYLE.style == "glass":
        surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        body = surf.get_rect()
        if accent_fill:
            pygame.draw.rect(surf, (*accent, 70), body, border_radius=radius)
        else:
            base = COLOR_PANEL_HOVER if hovered else COLOR_PANEL
            alpha = 200 if hovered else 150
            pygame.draw.rect(surf, (*base, alpha), body, border_radius=radius)
        surface.blit(surf, rect.topleft)
        edge = accent if (accent_border or accent_fill or hovered) else COLOR_BORDER
        pygame.draw.rect(surface, edge, rect, width=1, border_radius=radius)
        return
    # Flat style.
    if accent_fill:
        fill = _mix(COLOR_PANEL, accent, 0.30)
    elif hovered:
        fill = COLOR_PANEL_HOVER
    else:
        fill = COLOR_PANEL
    pygame.draw.rect(surface, fill, rect, border_radius=radius)
    edge = accent if (accent_border or accent_fill or hovered) else COLOR_BORDER
    pygame.draw.rect(surface, edge, rect, width=1, border_radius=radius)


def fit_text(font: pygame.font.Font, text: str, max_width: int) -> str:
    """Trim ``text`` (appending an ellipsis) so it fits within ``max_width`` px.

    Returns the original text when it already fits. Guards against zero/negative
    widths so a tiny widget never crashes the draw.
    """
    if max_width <= 0 or not text:
        return text
    if font.size(text)[0] <= max_width:
        return text
    ellipsis = "\u2026"
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi) // 2
        if font.size(text[:mid] + ellipsis)[0] <= max_width:
            lo = mid + 1
        else:
            hi = mid
    return (text[: lo - 1] + ellipsis) if lo > 1 else ellipsis
