"""A tiny on-screen Beat indicator: a pulsing dot that previews the next fire.

Optional and unobtrusive (off by default). Its **hue** tracks the band the beat
engine is listening to (bass = warm, mid = green, high = cyan, all = accent), its
**brightness/size** track how close the beat is to firing, and it flashes white on
an actual trigger — so you can watch it "charge up" and see the button fire.
"""

from __future__ import annotations

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


def _base_color(band: str) -> tuple[int, int, int]:
    return _BAND_COLORS.get(band, STYLE.accent)


def _blend(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))  # type: ignore[return-value]


def draw_beat_indicator(
    surface: pygame.Surface,
    canvas: pygame.Rect,
    position: str,
    intensity: float,
    band: str,
    flash: float,
) -> None:
    """Draw the indicator within ``canvas`` at ``position`` (no-op for empty canvas)."""
    if canvas.width < 8 or canvas.height < 8:
        return
    unit = min(canvas.width, canvas.height)
    max_r = max(8, int(unit * 0.028))
    margin = max_r + int(unit * 0.02)
    ax, ay = _POSITION_ANCHORS.get(position, _POSITION_ANCHORS["top-right"])
    cx = canvas.left + margin + int((canvas.width - 2 * margin) * ax)
    cy = canvas.top + margin + int((canvas.height - 2 * margin) * ay)

    intensity = max(0.0, min(1.0, intensity))
    flash = max(0.0, min(1.0, flash))
    base = _base_color(band)

    # Dim outer ring is always visible so the user can find it; inner dot grows and
    # brightens with intensity and blends to white on a fire.
    ring_color = tuple(int(c * 0.35) for c in base)
    pygame.draw.circle(surface, ring_color, (cx, cy), max_r, 2)

    brightness = 0.25 + 0.75 * intensity
    dot_color = _blend(tuple(int(c * brightness) for c in base), (255, 255, 255), flash)
    radius = max(2, int(max_r * (0.35 + 0.65 * intensity)))
    pygame.draw.circle(surface, dot_color, (cx, cy), radius)
    if flash > 0.0:  # a quick halo on trigger
        pygame.draw.circle(surface, _blend(base, (255, 255, 255), flash), (cx, cy), max_r + 3, 2)
