"""Spiral particles mode: sparks blow out from the center along spiral arms.

Each spawned particle is tied to a frequency band, so different parts of the
spectrum paint differently colored arms (hue = band index). Particles gain a
constant angular velocity while their radius grows, tracing a spiral outward.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import (
    PALETTE,
    SPIRAL_BURST,
    SPIRAL_LIFETIME,
    SPIRAL_MAX,
    SPIRAL_MAX_REDUCED,
)
from audio_visualizer.visuals._helpers import clamp, palette_color, scale_color
from audio_visualizer.visuals.base import BaseVisualizer
from audio_visualizer.visuals.registry import register


@dataclass
class _Spark:
    """A particle in polar terms: radius (0..~1.2 of half-min-side) + angle."""

    r: float
    theta: float
    ang_speed: float
    radial_speed: float
    life: float
    max_life: float
    hue: float


@register(key="particles_spiral", display_name="Particles Spiral", order=70)
class ParticlesSpiral(BaseVisualizer):
    """Energy/onset spawn rate; per-band hue; reduce-motion calms and caps it."""

    STROBES = True

    def __init__(self, reduce_motion: bool = False, seed: int = 4321) -> None:
        super().__init__(reduce_motion)
        self._seed = seed
        self._rng = random.Random(seed)
        self._sparks: list[_Spark] = []

    def on_enter(self) -> None:
        self._sparks.clear()
        self._rng.seed(self._seed)

    @property
    def _cap(self) -> int:
        return SPIRAL_MAX_REDUCED if self.reduce_motion else SPIRAL_MAX

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 2 or h < 2:
            return
        if frame is not None and not frame.is_silent:
            self._spawn(frame)
        self._advance(dt)
        self._render(surface, w, h)

    def _spawn(self, frame: AnalysisFrame) -> None:
        bands = frame.band_energies
        if bands.size == 0:
            return
        base = SPIRAL_BURST // 3 if self.reduce_motion else SPIRAL_BURST
        n_spawn = int(base * clamp(frame.rms * 1.5 + frame.onset))
        swirl = 1.0 if self.reduce_motion else 2.6
        for _ in range(n_spawn):
            if len(self._sparks) >= self._cap:
                break
            bi = self._rng.randrange(bands.size)
            energy = float(bands[bi])
            self._sparks.append(
                _Spark(
                    r=0.02,
                    theta=self._rng.uniform(0.0, 2.0 * math.pi),
                    ang_speed=swirl * (0.4 + energy),
                    radial_speed=0.15 + energy * 0.5,
                    life=SPIRAL_LIFETIME,
                    max_life=SPIRAL_LIFETIME,
                    hue=bi / bands.size,
                )
            )

    def _advance(self, dt: float) -> None:
        alive: list[_Spark] = []
        for s in self._sparks:
            s.life -= dt
            if s.life <= 0.0 or s.r > 1.2:
                continue
            s.r += s.radial_speed * dt
            s.theta += s.ang_speed * dt
            alive.append(s)
        self._sparks = alive

    def _render(self, surface: pygame.Surface, w: int, h: int) -> None:
        cx, cy = w / 2.0, h / 2.0
        scale = min(w, h) * 0.5
        for s in self._sparks:
            t = clamp(s.life / s.max_life)
            px = int(cx + math.cos(s.theta) * s.r * scale)
            py = int(cy + math.sin(s.theta) * s.r * scale)
            radius = max(1, int(1 + t * 3))
            brightness = t if self.reduce_motion else 0.4 + t
            color = scale_color(palette_color(PALETTE, s.hue), brightness)
            pygame.draw.circle(surface, color, (px, py), radius)
