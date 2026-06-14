"""Particles mode: bursts spawned by onsets, pushed outward by energy."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import (
    ONSET_THRESHOLD,
    PALETTE,
    PARTICLE_BURST,
    PARTICLE_LIFETIME,
    PARTICLE_MAX,
    PARTICLE_MAX_REDUCED,
)
from audio_visualizer.visuals._helpers import clamp, scale_color, themed_color
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice
from audio_visualizer.visuals.registry import register

_BURST = ModeOption(
    "burst",
    "Burst",
    (OptionChoice("Small", 0.5), OptionChoice("Normal", 1.0), OptionChoice("Large", 2.0)),
    default_index=1,
)
_GRAVITY = ModeOption(
    "gravity",
    "Gravity",
    (OptionChoice("Low", 0.04), OptionChoice("Normal", 0.12), OptionChoice("High", 0.30)),
    default_index=1,
)


@dataclass
class _Particle:
    """A single short-lived spark in normalized (0..1) screen space."""

    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    hue: float


@register(key="particles", display_name="Particles", order=40)
class Particles(BaseVisualizer):
    """Onset-driven particle field; calmer and capped under reduce-motion."""

    STROBES = True
    OPTIONS = (_BURST, _GRAVITY)

    def __init__(self, reduce_motion: bool = False, seed: int = 1234) -> None:
        super().__init__(reduce_motion)
        self._rng = random.Random(seed)
        self._seed = seed
        self._particles: list[_Particle] = []

    def on_enter(self) -> None:
        self._particles.clear()
        self._rng.seed(self._seed)

    @property
    def _cap(self) -> int:
        return PARTICLE_MAX_REDUCED if self.reduce_motion else PARTICLE_MAX

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if frame is not None and not frame.is_silent:
            self._maybe_spawn(frame)
        self._advance(dt)
        self._render(surface, w, h)

    def _maybe_spawn(self, frame: AnalysisFrame) -> None:
        if frame.onset < ONSET_THRESHOLD:
            return
        burst = max(1, int(PARTICLE_BURST * self.option("burst")))
        if self.reduce_motion:
            burst //= 3
        speed = 0.15 + frame.rms * 0.6
        for _ in range(burst):
            if len(self._particles) >= self._cap:
                break
            angle = self._rng.uniform(0.0, 2.0 * math.pi)
            mag = speed * self._rng.uniform(0.3, 1.0)
            self._particles.append(
                _Particle(
                    x=0.5,
                    y=0.5,
                    vx=math.cos(angle) * mag,
                    vy=math.sin(angle) * mag,
                    life=PARTICLE_LIFETIME,
                    max_life=PARTICLE_LIFETIME,
                    hue=self._rng.random(),
                )
            )

    def _advance(self, dt: float) -> None:
        move_dt = dt * self.theme.speed_scale
        gravity = self.option("gravity")
        alive: list[_Particle] = []
        for p in self._particles:
            p.life -= dt  # lifetime is wall-clock; only motion honors speed_scale
            if p.life <= 0.0:
                continue
            p.x += p.vx * move_dt
            p.y += p.vy * move_dt
            p.vy += gravity * move_dt  # gentle gravity
            alive.append(p)
        self._particles = alive

    def _render(self, surface: pygame.Surface, w: int, h: int) -> None:
        for p in self._particles:
            t = clamp(p.life / p.max_life)
            radius = max(1, int((2 + t * 4) * self.theme.size_scale))
            base = themed_color(self.theme.color_scheme, p.hue, PALETTE, self.theme.color_phase)
            brightness = t if self.reduce_motion else 0.4 + t
            color = scale_color(base, brightness)
            px = int(p.x * w)
            py = int(p.y * h)
            pygame.draw.circle(surface, color, (px, py), radius)
