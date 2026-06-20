"""On-screen Beat indicator: a translucent shape that previews the next fire.

Optional and unobtrusive (off by default). Its **hue** tracks the band the beat
engine is listening to (bass = warm, mid = green, high = cyan, all = accent), its
**brightness/size/alpha** track how close the beat is to firing, and it flashes
white with an expanding halo on an actual trigger.

The user can pick a **shape** (dot / ring / pulse / diamond / star / burst). All
shapes draw with transparency onto an ``SRCALPHA`` layer so they sit lightly over
the visual, and the trigger flash adds a soft expanding halo on top.
"""

from __future__ import annotations

import math

import pygame

from audio_visualizer.ui.style import STYLE

# Base color per listened band (hue cue; brightness comes from intensity).
_BAND_COLORS: dict[str, tuple[int, int, int]] = {
    "bass": (240, 80, 55),
    "mid": (90, 220, 110),
    "high": (70, 200, 245),
}
_POSITION_ANCHORS = {
    "top-left": (0.0, 0.0),
    "top-right": (1.0, 0.0),
    "bottom-left": (0.0, 1.0),
    "bottom-right": (1.0, 1.0),
    "center": (0.5, 0.5),
}
_WHITE = (255, 255, 255)


def _base_color(band: str) -> tuple[int, int, int]:
    return _BAND_COLORS.get(band, STYLE.accent)


def _blend(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        int(round(a[0] + (b[0] - a[0]) * t)),
        int(round(a[1] + (b[1] - a[1]) * t)),
        int(round(a[2] + (b[2] - a[2]) * t)),
    )


def _polygon_points(
    cx: float, cy: float, radius: float, sides: int, rotation: float = 0.0
) -> list[tuple[float, float]]:
    """Vertices of a regular ``sides``-gon (``rotation`` in radians)."""
    return [
        (
            cx + radius * math.cos(rotation + i * 2.0 * math.pi / sides),
            cy + radius * math.sin(rotation + i * 2.0 * math.pi / sides),
        )
        for i in range(sides)
    ]


def _star_points(
    cx: float, cy: float, outer: float, inner: float, points: int
) -> list[tuple[float, float]]:
    """Vertices of a ``points``-pointed star alternating outer/inner radii."""
    out: list[tuple[float, float]] = []
    for i in range(points * 2):
        r = outer if i % 2 == 0 else inner
        ang = -math.pi / 2 + i * math.pi / points
        out.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return out


def _draw_shape(
    layer: pygame.Surface,
    shape: str,
    center: tuple[float, float],
    radius: float,
    color: tuple[int, int, int],
    alpha: int,
    intensity: float,
) -> None:
    """Draw the chosen indicator shape onto the translucent ``layer``."""
    cx, cy = center
    rgba = (*color, alpha)
    r = max(2.0, radius)
    if shape == "ring":
        width = max(2, int(r * 0.32))
        pygame.draw.circle(layer, rgba, (int(cx), int(cy)), int(r), width)
    elif shape == "pulse":
        for k in range(3):  # concentric rings fading outward
            rr = r * (0.45 + 0.45 * k)
            fade = int(alpha * (1.0 - 0.3 * k))
            pygame.draw.circle(layer, (*color, max(0, fade)), (int(cx), int(cy)), int(rr), 2)
    elif shape == "diamond":
        pygame.draw.polygon(layer, rgba, _polygon_points(cx, cy, r, 4, math.pi / 4))
    elif shape == "star":
        pygame.draw.polygon(layer, rgba, _star_points(cx, cy, r, r * 0.45, 5))
    elif shape == "burst":
        spokes = 8
        length = r * (1.0 + 0.6 * intensity)
        for i in range(spokes):
            ang = i * 2.0 * math.pi / spokes
            ex = cx + length * math.cos(ang)
            ey = cy + length * math.sin(ang)
            pygame.draw.line(layer, rgba, (int(cx), int(cy)), (int(ex), int(ey)), 2)
        pygame.draw.circle(layer, rgba, (int(cx), int(cy)), max(2, int(r * 0.4)))
    else:  # "dot"
        pygame.draw.circle(layer, rgba, (int(cx), int(cy)), int(r))


def draw_beat_indicator(
    surface: pygame.Surface,
    canvas: pygame.Rect,
    position: str,
    intensity: float,
    band: str,
    flash: float,
    shape: str = "dot",
    opacity: float = 1.0,
) -> None:
    """Draw the indicator within ``canvas`` at ``position`` (no-op for empty canvas).

    ``opacity`` (0..1) scales how see-through the whole indicator is over the visual.
    """
    if canvas.width < 8 or canvas.height < 8 or opacity <= 0.0:
        return
    unit = min(canvas.width, canvas.height)
    max_r = max(8, int(unit * 0.030))
    margin = max_r + int(unit * 0.02)
    ax, ay = _POSITION_ANCHORS.get(position, _POSITION_ANCHORS["top-right"])
    cx = canvas.left + margin + int((canvas.width - 2 * margin) * ax)
    cy = canvas.top + margin + int((canvas.height - 2 * margin) * ay)

    intensity = max(0.0, min(1.0, intensity))
    flash = max(0.0, min(1.0, flash))
    base = _base_color(band)

    # Everything is drawn translucent onto its own layer so the indicator sits
    # lightly over the visual; the layer is big enough for the expanding halo.
    pad = max_r * 3
    size = pad * 2
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    lc = (pad, pad)

    # A faint resting ring so the user can always find it.
    pygame.draw.circle(layer, (*tuple(int(c * 0.4) for c in base), 90), lc, max_r, 2)

    # Core shape: brightens/grows with intensity, whitens on a fire, and rides an
    # alpha envelope so it fades in/out rather than hard-popping.
    brightness = 0.3 + 0.7 * intensity
    dimmed = (int(base[0] * brightness), int(base[1] * brightness), int(base[2] * brightness))
    color = _blend(dimmed, _WHITE, flash)
    alpha = int(110 + 110 * intensity + 35 * flash)
    radius = max_r * (0.4 + 0.6 * intensity)
    _draw_shape(layer, shape, lc, radius, color, min(255, alpha), intensity)

    # Expanding halo on a trigger (fades as it grows outward).
    if flash > 0.0:
        halo_r = int(max_r * (1.1 + 1.6 * (1.0 - flash)))
        halo_a = int(180 * flash)
        pygame.draw.circle(layer, (*_blend(base, _WHITE, flash), halo_a), lc, halo_r, 2)

    # Scale the whole layer's per-pixel alpha for the user's transparency choice.
    if opacity < 1.0:
        layer.fill((255, 255, 255, int(opacity * 255)), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(layer, (cx - pad, cy - pad))
