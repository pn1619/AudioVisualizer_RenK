"""Tunnel Warp: glowing concentric rings rushing toward the viewer.

Rings spawn at the center and grow outward; energy speeds the rush and each onset
spawns an extra ring, so beats read as a pulse flying past. Hue cycles with each
ring's age. Flagged ``STROBES`` because of the fast motion + beat flashes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import PALETTE
from audio_visualizer.visuals._helpers import clamp, themed_color
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_SPAWN_INTERVAL = 0.22  # seconds between rings at rest (faster when loud)
_GROW_BASE = 0.18  # ring radius growth (fraction of max radius) per second
_GROW_ENERGY_GAIN = 0.9  # extra growth driven by loudness
_RING_MAX = 48
_WIDTH_NEAR = 6  # outline width for the nearest (largest) rings

_SHAPE = ModeOption(
    "shape",
    "Shape",
    (OptionChoice("Circle", 0), OptionChoice("Hexagon", 6), OptionChoice("Square", 4)),
    default_index=0,
)


@dataclass
class _Ring:
    r: float  # 0..~1.2 normalized to the half-diagonal
    hue: float


@register(key="tunnel", display_name="Tunnel Warp", order=75)
class Tunnel(BaseVisualizer):
    """Concentric rings flying outward from a vanishing point; beats spawn rings."""

    STROBES = True

    OPTIONS = (_SHAPE,)

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._rings: list[_Ring] = []
        self._spawn_timer = 0.0
        self._hue = 0.0

    def on_enter(self) -> None:
        self._rings.clear()
        self._spawn_timer = 0.0

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        cx, cy = w / 2.0, h / 2.0
        max_r = math.hypot(w, h) / 2.0
        energy = 0.0 if frame is None or frame.is_silent else clamp(frame.rms * 2.0)
        onset = 0.0 if frame is None else frame.onset

        self._update(dt, energy, onset)
        sides = int(self.option("shape"))
        scheme, phase = self.theme.color_scheme, self.theme.color_phase
        for ring in self._rings:
            radius = ring.r * max_r
            if radius < 2:
                continue
            width = max(1, int(_WIDTH_NEAR * ring.r))
            color = themed_color(scheme, ring.hue, PALETTE, phase)
            _draw_shape(surface, cx, cy, radius, sides, color, width)

    def _update(self, dt: float, energy: float, onset: float) -> None:
        speed = self.theme.speed_scale * (0.5 if self.reduce_motion else 1.0)
        grow = (_GROW_BASE + energy * _GROW_ENERGY_GAIN) * speed
        for ring in self._rings:
            ring.r += grow * dt
        self._rings = [r for r in self._rings if r.r < 1.25]

        self._spawn_timer -= dt * speed * (1.0 + energy * 2.0)
        if self._spawn_timer <= 0.0:
            self._spawn_timer = _SPAWN_INTERVAL
            self._spawn()
        if onset > 0.4 and len(self._rings) < _RING_MAX:
            self._spawn()

    def _spawn(self) -> None:
        if len(self._rings) >= _RING_MAX:
            return
        self._rings.append(_Ring(r=0.01, hue=self._hue))
        self._hue = (self._hue + 0.13) % 1.0  # step the hue so rings rainbow outward


def _draw_shape(
    surface: pygame.Surface,
    cx: float,
    cy: float,
    radius: float,
    sides: int,
    color: tuple[int, int, int],
    width: int,
) -> None:
    if sides < 3:
        pygame.draw.circle(surface, color, (int(cx), int(cy)), int(radius), width)
        return
    pts = [
        (cx + math.cos(math.tau * k / sides) * radius, cy + math.sin(math.tau * k / sides) * radius)
        for k in range(sides)
    ]
    pygame.draw.lines(surface, color, True, pts, width)
