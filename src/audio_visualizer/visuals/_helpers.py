"""Shared drawing helpers for visual modes (skipped by registry discovery)."""

from __future__ import annotations

Color = tuple[int, int, int]


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp ``value`` into ``[low, high]``."""
    return max(low, min(high, value))


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolate from ``a`` to ``b`` by ``t`` in ``0..1``."""
    return a + (b - a) * t


def lerp_color(a: Color, b: Color, t: float) -> Color:
    """Interpolate between two RGB colors."""
    t = clamp(t)
    return (
        int(lerp(a[0], b[0], t)),
        int(lerp(a[1], b[1], t)),
        int(lerp(a[2], b[2], t)),
    )


def palette_color(palette: tuple[Color, ...], t: float) -> Color:
    """Sample a color from a palette at position ``t`` in ``0..1``."""
    if not palette:
        return (255, 255, 255)
    if len(palette) == 1:
        return palette[0]
    t = clamp(t)
    scaled = t * (len(palette) - 1)
    i = int(scaled)
    if i >= len(palette) - 1:
        return palette[-1]
    return lerp_color(palette[i], palette[i + 1], scaled - i)


def scale_color(color: Color, factor: float) -> Color:
    """Multiply an RGB color by ``factor`` (brightness), clamped to 0..255."""
    return (
        int(clamp(color[0] * factor, 0, 255)),
        int(clamp(color[1] * factor, 0, 255)),
        int(clamp(color[2] * factor, 0, 255)),
    )
