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
    PARTICLE_BRIGHTNESS_FLOOR,
    REDUCE_MOTION_BURST_DIVISOR,
    SPIRAL_BURST,
    SPIRAL_LIFETIME,
    SPIRAL_MAX,
    SPIRAL_MAX_REDUCED,
)
from audio_visualizer.visuals._helpers import clamp, scale_color, themed_color
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice
from audio_visualizer.visuals.registry import register

# Spark birth radius (fraction of the drawing scale) — just off the center.
_BIRTH_RADIUS = 0.02
# Sparks are recycled once they pass this radius (just past the canvas edge).
_MAX_RADIUS = 1.2
# Angular speed = swirl * (this base + band energy).
_ANGULAR_BASE = 0.4
# Radial speed = (this base + energy * gain) * the spacing option.
_RADIAL_BASE = 0.15
_RADIAL_ENERGY_GAIN = 0.5
# Swirl is pinned to this calm value under reduce-motion.
_SWIRL_REDUCED = 1.0
# Spawn count scales with this * rms + onset (clamped to 0..1).
_SPAWN_RMS_GAIN = 1.5
# Spark radius (px) = base + life-fraction * growth, scaled by the size control.
_RADIUS_BASE = 1
_RADIUS_GROWTH = 3

_SWIRL = ModeOption(
    "swirl",
    "Swirl",
    (OptionChoice("Gentle", 1.4), OptionChoice("Normal", 2.6), OptionChoice("Wild", 4.5)),
    default_index=1,
)
_REACH = ModeOption(
    "reach",
    "Size",
    (OptionChoice("Small", 0.6), OptionChoice("Normal", 1.0), OptionChoice("Large", 1.5)),
    default_index=1,
)
_SPACING = ModeOption(
    "spacing",
    "Spacing",
    (OptionChoice("Tight", 0.6), OptionChoice("Normal", 1.0), OptionChoice("Wide", 1.8)),
    default_index=1,
)


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
    OPTIONS = (_SWIRL, _REACH, _SPACING)

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
        base = SPIRAL_BURST // REDUCE_MOTION_BURST_DIVISOR if self.reduce_motion else SPIRAL_BURST
        n_spawn = int(base * clamp(frame.rms * _SPAWN_RMS_GAIN + frame.onset))
        swirl = _SWIRL_REDUCED if self.reduce_motion else self.option("swirl")
        spacing = self.option("spacing")
        for _ in range(n_spawn):
            if len(self._sparks) >= self._cap:
                break
            bi = self._rng.randrange(bands.size)
            energy = float(bands[bi])
            self._sparks.append(
                _Spark(
                    r=_BIRTH_RADIUS,
                    theta=self._rng.uniform(0.0, 2.0 * math.pi),
                    ang_speed=swirl * (_ANGULAR_BASE + energy),
                    radial_speed=(_RADIAL_BASE + energy * _RADIAL_ENERGY_GAIN) * spacing,
                    life=SPIRAL_LIFETIME,
                    max_life=SPIRAL_LIFETIME,
                    hue=bi / bands.size,
                )
            )

    def _advance(self, dt: float) -> None:
        move_dt = dt * self.theme.speed_scale
        alive: list[_Spark] = []
        for s in self._sparks:
            s.life -= dt  # lifetime is wall-clock; only motion honors speed_scale
            if s.life <= 0.0 or s.r > _MAX_RADIUS:
                continue
            s.r += s.radial_speed * move_dt
            s.theta += s.ang_speed * move_dt
            alive.append(s)
        self._sparks = alive

    def _render(self, surface: pygame.Surface, w: int, h: int) -> None:
        cx, cy = w / 2.0, h / 2.0
        scale = min(w, h) * 0.5 * self.option("reach")
        scheme = self.theme.color_scheme
        phase = self.theme.color_phase
        for s in self._sparks:
            t = clamp(s.life / s.max_life)
            px = int(cx + math.cos(s.theta) * s.r * scale)
            py = int(cy + math.sin(s.theta) * s.r * scale)
            radius = max(1, int((_RADIUS_BASE + t * _RADIUS_GROWTH) * self.theme.size_scale))
            brightness = t if self.reduce_motion else PARTICLE_BRIGHTNESS_FLOOR + t
            color = scale_color(themed_color(scheme, s.hue, PALETTE, phase), brightness)
            pygame.draw.circle(surface, color, (px, py), radius)
