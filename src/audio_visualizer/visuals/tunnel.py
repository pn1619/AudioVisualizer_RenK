"""Tunnel Warp: glowing rings rushing toward the viewer.

Rings spawn at the center and grow outward; energy speeds the rush and each onset
spawns an extra ring, so beats read as a pulse flying past. Hue cycles per ring.
Rings can be **full** outlines, **broken** (gapped arcs / dashed polygons that read
as a strobing wormhole), or **waveform** — each ring frozen into the shape of the
audio waveform at the instant it was born. Flagged ``STROBES`` (fast motion).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import PALETTE
from audio_visualizer.visuals._helpers import clamp, ring_points, themed_color
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_SPAWN_INTERVAL = 0.22  # seconds between rings at rest (faster when loud)
_GROW_BASE = 0.18  # ring radius growth (fraction of max radius) per second
_GROW_ENERGY_GAIN = 0.9  # extra growth driven by loudness
_RING_MAX = 48
_WIDTH_NEAR = 6  # outline width for the nearest (largest) rings
_WAVE_POINTS = 120  # samples captured/drawn for a waveform-shaped ring

_SHAPE = ModeOption(
    "shape",
    "Shape",
    (OptionChoice("Circle", 0), OptionChoice("Hexagon", 6), OptionChoice("Square", 4)),
    default_index=0,
)
_STYLE = ModeOption(
    "style",
    "Rings",
    (OptionChoice("Full", 0), OptionChoice("Broken", 1), OptionChoice("Waveform", 2)),
    default_index=0,
)


@dataclass
class _Ring:
    r: float  # 0..~1.2 normalized to the half-diagonal
    hue: float
    gap: float = 0.0  # angular offset for "broken" gaps
    wave: np.ndarray | None = field(default=None)  # snapshot for "waveform" style


@register(key="tunnel", display_name="Tunnel Warp", order=75)
class Tunnel(BaseVisualizer):
    """Concentric rings flying outward from a vanishing point; beats spawn rings."""

    STROBES = True

    OPTIONS = (_SHAPE, _STYLE)

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._rings: list[_Ring] = []
        self._spawn_timer = 0.0
        self._hue = 0.0
        self._rng = random.Random(99)

    def on_enter(self) -> None:
        self._rings.clear()
        self._spawn_timer = 0.0
        self._rng.seed(99)

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        cx, cy = w / 2.0, h / 2.0
        max_r = math.hypot(w, h) / 2.0
        energy = 0.0 if frame is None or frame.is_silent else clamp(frame.rms * 2.0)
        onset = 0.0 if frame is None else frame.onset

        self._update(dt, energy, onset, frame)
        sides = int(self.option("shape"))
        style = int(self.option("style"))
        scheme, phase = self.theme.color_scheme, self.theme.color_phase
        for ring in self._rings:
            radius = ring.r * max_r
            if radius < 2:
                continue
            width = max(1, int(_WIDTH_NEAR * ring.r))
            color = themed_color(scheme, ring.hue + phase, PALETTE, 0.0)
            self._draw_ring(surface, cx, cy, radius, sides, style, color, width, ring)

    def _update(self, dt: float, energy: float, onset: float, frame: AnalysisFrame | None) -> None:
        speed = self.theme.speed_scale * (0.5 if self.reduce_motion else 1.0)
        grow = (_GROW_BASE + energy * _GROW_ENERGY_GAIN) * speed
        for ring in self._rings:
            ring.r += grow * dt
        self._rings = [r for r in self._rings if r.r < 1.25]

        self._spawn_timer -= dt * speed * (1.0 + energy * 2.0)
        if self._spawn_timer <= 0.0:
            self._spawn_timer = _SPAWN_INTERVAL
            self._spawn(frame)
        if onset > 0.4 and len(self._rings) < _RING_MAX:
            self._spawn(frame)

    def _spawn(self, frame: AnalysisFrame | None) -> None:
        if len(self._rings) >= _RING_MAX:
            return
        wave: np.ndarray | None = None
        if int(self.option("style")) == 2 and frame is not None and frame.waveform_mono.size > 1:
            idx = np.linspace(0, frame.waveform_mono.size - 1, _WAVE_POINTS).astype(np.int64)
            wave = frame.waveform_mono[idx].astype(np.float32)
        self._rings.append(
            _Ring(r=0.01, hue=self._hue, gap=self._rng.uniform(0.0, math.tau), wave=wave)
        )
        self._hue = (self._hue + 0.13) % 1.0  # step the hue so rings rainbow outward

    def _draw_ring(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        radius: float,
        sides: int,
        style: int,
        color: tuple[int, int, int],
        width: int,
        ring: _Ring,
    ) -> None:
        if style == 2 and ring.wave is not None:  # waveform-shaped ring
            pts = ring_points(cx, cy, radius, radius * 0.16, ring.wave, points=_WAVE_POINTS)
            pygame.draw.lines(surface, color, True, pts, width)
            return
        if style == 1:  # broken
            _draw_broken(surface, cx, cy, radius, sides, color, width, ring.gap)
            return
        _draw_full(surface, cx, cy, radius, sides, color, width)


def _polygon(cx: float, cy: float, radius: float, sides: int) -> list[tuple[float, float]]:
    return [
        (cx + math.cos(math.tau * k / sides) * radius, cy + math.sin(math.tau * k / sides) * radius)
        for k in range(sides)
    ]


def _draw_full(
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
    pygame.draw.lines(surface, color, True, _polygon(cx, cy, radius, sides), width)


def _draw_broken(
    surface: pygame.Surface,
    cx: float,
    cy: float,
    radius: float,
    sides: int,
    color: tuple[int, int, int],
    width: int,
    gap: float,
) -> None:
    if sides < 3:  # circle -> dashed arcs with gaps
        segs = 5
        span = math.tau / segs
        rect = pygame.Rect(cx - radius, cy - radius, radius * 2, radius * 2)
        for k in range(segs):
            a0 = gap + k * span
            pygame.draw.arc(surface, color, rect, a0, a0 + span * 0.6, width)
        return
    pts = _polygon(cx, cy, radius, sides)  # polygon -> skip alternating edges
    offset = int(gap) % 2
    for k in range(sides):
        if (k + offset) % 2 == 0:
            pygame.draw.line(surface, color, pts[k], pts[(k + 1) % sides], width)
