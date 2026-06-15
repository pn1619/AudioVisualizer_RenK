"""Shared drawing helpers for visual modes (skipped by registry discovery)."""

from __future__ import annotations

import colorsys
import math
import random
from dataclasses import dataclass

import numpy as np
import pygame
from numpy.typing import NDArray

from audio_visualizer.config import COLOR_ACCENT, PALETTE, PARTICLE_BRIGHTNESS_FLOOR

Color = tuple[int, int, int]

# RingPops tuning: initial outward speed = base + energy * gain (radius-fraction/sec).
_POP_SPEED_BASE = 0.08
_POP_SPEED_ENERGY_GAIN = 0.30
# Pop radius (px) = base + envelope * growth, scaled by the size control.
_POP_RADIUS_BASE = 1
_POP_RADIUS_GROWTH = 5


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


def rainbow_color(t: float) -> Color:
    """Full-saturation hue sweep around the wheel; ``t`` wraps continuously.

    ``t`` is taken modulo 1.0 (so 0.0 and 1.0 are the same red and the sweep is
    seamless). Crucially we wrap **before** any clamp, so a hue past the end rolls
    smoothly back to the start instead of sticking at red.
    """
    r, g, b = colorsys.hsv_to_rgb(t % 1.0, 1.0, 1.0)
    return (int(r * 255), int(g * 255), int(b * 255))


def themed_color(scheme: str, t: float, palette: tuple[Color, ...], phase: float = 0.0) -> Color:
    """Pick a color for position ``t`` honoring the active color scheme.

    ``phase`` (0..1) only matters for ``rainbow_plus``, where it shifts every hue
    over time so colors cycle continuously.
    """
    if scheme == "rainbow":
        return rainbow_color(t)
    if scheme == "rainbow_plus":
        return rainbow_color(t + phase)
    return palette_color(palette, t)


# --- Circular waveform helpers (shared by the waveform-circle modes) ----------
def resample_to(values: NDArray[np.float32], n: int) -> NDArray[np.float32]:
    """Resample ``values`` to exactly ``n`` points (nearest-index, allocation-light)."""
    arr = np.asarray(values, dtype=np.float32)
    if arr.size == 0:
        return np.zeros(n, dtype=np.float32)
    idx = np.linspace(0, arr.size - 1, n).astype(np.int64)
    return arr[idx]


def range_energies(bands: NDArray[np.float32], slices: int) -> NDArray[np.float32]:
    """Mean energy of each of ``slices`` equal sub-ranges of the spectrum.

    Used by the multi-ring circular modes to drive one ring per frequency range.
    Empty input yields zeros so callers can render a quiescent shape.
    """
    if bands.size == 0:
        return np.zeros(slices, dtype=np.float32)
    edges = np.linspace(0, bands.size, slices + 1).astype(int)
    return np.array(
        [bands[edges[i] : max(edges[i] + 1, edges[i + 1])].mean() for i in range(slices)],
        dtype=np.float32,
    )


def ring_points(
    cx: float,
    cy: float,
    base_r: float,
    amplitude: float,
    values: NDArray[np.float32],
    points: int = 240,
) -> list[tuple[float, float]]:
    """Map ``values`` around a circle: radius = ``base_r + value * amplitude``."""
    vals = resample_to(values, points)
    ang = np.linspace(0.0, 2.0 * np.pi, points, endpoint=False)
    radii = base_r + vals * amplitude
    xs = cx + np.cos(ang) * radii
    ys = cy + np.sin(ang) * radii
    return [(float(x), float(y)) for x, y in zip(xs, ys, strict=False)]


def draw_ring(
    surface: pygame.Surface,
    scheme: str,
    phase: float,
    points_list: list[tuple[float, float]],
    width: int,
    hue_offset: float = 0.0,
) -> None:
    """Draw a closed ring; colored schemes hue each segment, classic is solid accent."""
    if len(points_list) < 2:
        return
    if scheme == "classic":
        pygame.draw.lines(surface, COLOR_ACCENT, True, points_list, width)
        return
    n = len(points_list)
    for i in range(n):
        a = points_list[i]
        b = points_list[(i + 1) % n]
        color = themed_color(scheme, i / n + hue_offset, PALETTE, phase)
        pygame.draw.line(surface, color, a, b, width)


@dataclass
class _RingPop:
    """A spark anchored in polar space (angle + normalized radius) that pops out."""

    theta: float
    r: float
    vr: float
    life: float
    max_life: float
    hue: float


class RingPops:
    """Reusable pop-particle field for the circular-waveform "2" modes.

    Particles spawn on a ring and drift radially while swelling then fading, so a
    mode just spawns on energy/onset and renders each frame. Polar coordinates keep
    it resolution-independent (radius is a fraction of the drawing scale).
    """

    def __init__(self, cap: int, lifetime: float = 0.7) -> None:
        self._cap = cap
        self._lifetime = lifetime
        self._pops: list[_RingPop] = []

    def clear(self) -> None:
        self._pops.clear()

    @property
    def count(self) -> int:
        return len(self._pops)

    def spawn(self, rng: random.Random, count: int, base_r: float, energy: float) -> None:
        """Spawn ``count`` particles on the ring at normalized radius ``base_r``."""
        for _ in range(count):
            if len(self._pops) >= self._cap:
                break
            theta = rng.uniform(0.0, 2.0 * math.pi)
            self._pops.append(
                _RingPop(
                    theta=theta,
                    r=base_r,
                    vr=(_POP_SPEED_BASE + energy * _POP_SPEED_ENERGY_GAIN) * rng.uniform(0.5, 1.0),
                    life=self._lifetime,
                    max_life=self._lifetime,
                    hue=theta / (2.0 * math.pi),
                )
            )

    def advance(self, dt: float, speed_scale: float) -> None:
        move_dt = dt * speed_scale
        alive: list[_RingPop] = []
        for p in self._pops:
            p.life -= dt  # lifetime is wall-clock; only motion honors speed_scale
            if p.life <= 0.0:
                continue
            p.r += p.vr * move_dt
            alive.append(p)
        self._pops = alive

    def render(
        self,
        surface: pygame.Surface,
        scheme: str,
        phase: float,
        cx: float,
        cy: float,
        scale: float,
        size_scale: float,
    ) -> None:
        for p in self._pops:
            progress = clamp(1.0 - p.life / p.max_life)
            envelope = math.sin(math.pi * progress)  # 0 -> 1 -> 0
            radius = max(1, int((_POP_RADIUS_BASE + envelope * _POP_RADIUS_GROWTH) * size_scale))
            color = scale_color(
                themed_color(scheme, p.hue, PALETTE, phase), PARTICLE_BRIGHTNESS_FLOOR + envelope
            )
            x = int(cx + math.cos(p.theta) * p.r * scale)
            y = int(cy + math.sin(p.theta) * p.r * scale)
            pygame.draw.circle(surface, color, (x, y), radius)
