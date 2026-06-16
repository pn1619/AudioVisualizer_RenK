"""Shared, runtime-switchable UI look (flat vs glass, accent color) + text helper.

Widgets read the module-level :data:`STYLE` singleton at draw time instead of
hard-coding colors/shapes, so the Appearance panel can flip the whole UI's style,
accent, and font live. All panel/button/dropdown backgrounds go through
:func:`draw_panel` so the styles + the (optional gradient) accent live in one place.
"""

from __future__ import annotations

import pygame

from audio_visualizer.config import (
    COLOR_BORDER,
    COLOR_PANEL,
    COLOR_PANEL_HOVER,
    UI_ACCENT_COLORS,
    UI_ACCENT_DEFAULT,
    UI_ACCENT_GRADIENTS,
    UI_ACCENTS,
    UI_STYLE_DEFAULT,
    UI_STYLES,
)

# Padding between a widget's edge and its text (used for truncation + draw).
TEXT_PAD = 8
# Flat-style corner radius (glass uses a full pill radius instead).
_FLAT_RADIUS = 8

Color = tuple[int, int, int]


class UiStyle:
    """Mutable, process-wide UI appearance state read by widgets at draw time."""

    def __init__(self) -> None:
        self.style: str = UI_STYLE_DEFAULT
        self.accent: Color = UI_ACCENT_COLORS[UI_ACCENT_DEFAULT]
        # Two endpoints when the accent is a horizontal gradient, else None.
        self.accent_grad: tuple[Color, Color] | None = UI_ACCENT_GRADIENTS[UI_ACCENT_DEFAULT]

    def set_style(self, style: str) -> None:
        if style in UI_STYLES:
            self.style = style

    def set_accent(self, accent: str) -> None:
        if accent in UI_ACCENTS:
            self.accent = UI_ACCENT_COLORS[accent]
            self.accent_grad = UI_ACCENT_GRADIENTS[accent]


STYLE = UiStyle()


def _radius(rect: pygame.Rect) -> int:
    """Corner radius for ``rect`` under the current style (pill for glass)."""
    return rect.height // 2 if STYLE.style == "glass" else _FLAT_RADIUS


def _mix(a: Color, b: Color, t: float) -> Color:
    """Blend color ``a`` toward ``b`` by ``t`` in 0..1."""
    return (
        int(round(a[0] + (b[0] - a[0]) * t)),
        int(round(a[1] + (b[1] - a[1]) * t)),
        int(round(a[2] + (b[2] - a[2]) * t)),
    )


def _accent_gradient(size: tuple[int, int], radius: int, alpha: int) -> pygame.Surface:
    """A rounded, horizontal magenta->cyan (accent) gradient surface at ``alpha``."""
    a, b = STYLE.accent_grad  # type: ignore[misc]  # caller guards None
    w, h = max(1, size[0]), max(1, size[1])
    grad = pygame.Surface((w, h)).convert_alpha()
    for x in range(w):
        pygame.draw.line(grad, _mix(a, b, x / max(1, w - 1)), (x, 0), (x, h))
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, alpha), mask.get_rect(), border_radius=radius)
    grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return grad


def _draw_accent_border(surface: pygame.Surface, rect: pygame.Rect, radius: int) -> None:
    """Outline ``rect`` in the accent (a true gradient ring for gradient accents)."""
    if STYLE.accent_grad is None:
        pygame.draw.rect(surface, STYLE.accent, rect, width=1, border_radius=radius)
        return
    ring = _accent_gradient(rect.size, radius, 255)
    inner = ring.get_rect().inflate(-2, -2)
    # pygame.draw overwrites pixels (incl. alpha) on SRCALPHA surfaces, so this
    # punches the interior transparent, leaving only the gradient ring.
    pygame.draw.rect(ring, (0, 0, 0, 0), inner, border_radius=max(0, radius - 1))
    surface.blit(ring, rect.topleft)


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
    The accent may be a solid color or a magenta->cyan gradient (Aurora).
    """
    radius = _radius(rect)
    glass = STYLE.style == "glass"
    show_accent = accent_border or accent_fill or hovered

    if glass:
        surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        body = surf.get_rect()
        if accent_fill and STYLE.accent_grad is not None:
            surf.blit(_accent_gradient(rect.size, radius, 90), (0, 0))
        elif accent_fill:
            pygame.draw.rect(surf, (*STYLE.accent, 70), body, border_radius=radius)
        else:
            base = COLOR_PANEL_HOVER if hovered else COLOR_PANEL
            pygame.draw.rect(surf, (*base, 200 if hovered else 150), body, border_radius=radius)
        surface.blit(surf, rect.topleft)
    elif accent_fill and STYLE.accent_grad is not None:
        surface.blit(_accent_gradient(rect.size, radius, 235), rect.topleft)
    else:
        if accent_fill:
            fill = _mix(COLOR_PANEL, STYLE.accent, 0.30)
        elif hovered:
            fill = COLOR_PANEL_HOVER
        else:
            fill = COLOR_PANEL
        pygame.draw.rect(surface, fill, rect, border_radius=radius)

    if show_accent:
        _draw_accent_border(surface, rect, radius)
    else:
        pygame.draw.rect(surface, COLOR_BORDER, rect, width=1, border_radius=radius)


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
