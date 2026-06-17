"""Fireworks: beats launch shells that burst into gravity-driven spark showers.

Each onset (and the occasional loud moment) launches a rocket from the bottom; at
its apex it bursts into a radial spray of sparks that arc and fall with gravity,
trailing embers. Burst size scales with ``peak``. Reuses the shared ``SparkField``.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import PALETTE, REDUCE_MOTION_BURST_DIVISOR
from audio_visualizer.visuals._helpers import SparkField, clamp, scale_color, themed_color
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice
from audio_visualizer.visuals.registry import register

_SPARK_CAP = 700
_SPARK_CAP_REDUCED = 220
_GRAVITY = 0.55  # normalized units / s^2 pulling sparks (and rockets) down
_ROCKET_VY = (-0.95, -0.7)  # initial upward speed range (normalized / s)
_BURST_SPARKS = 60  # sparks per shell at full peak
_BURST_SPEED = (0.08, 0.42)  # radial spark speed range
_ONSET_THRESHOLD = 0.35
_LAUNCH_COOLDOWN = 0.12  # min seconds between onset-triggered launches

_BURSTS = ModeOption(
    "size",
    "Burst",
    (OptionChoice("Small", 0.5), OptionChoice("Normal", 1.0), OptionChoice("Big", 1.7)),
    default_index=1,
)


@dataclass
class _Rocket:
    x: float
    y: float
    vy: float
    hue: float


@register(key="fireworks", display_name="Fireworks", order=45)
class Fireworks(BaseVisualizer):
    """Onset-launched rockets that burst into falling spark showers."""

    OPTIONS = (_BURSTS,)

    def __init__(self, reduce_motion: bool = False, seed: int = 4242) -> None:
        super().__init__(reduce_motion)
        self._seed = seed
        self._rng = random.Random(seed)
        cap = _SPARK_CAP_REDUCED if reduce_motion else _SPARK_CAP
        self._sparks = SparkField(cap, lifetime=1.3, trail_len=5)
        self._rockets: list[_Rocket] = []
        self._cooldown = 0.0

    def on_enter(self) -> None:
        self._sparks.clear()
        self._rockets.clear()
        self._rng.seed(self._seed)
        self._cooldown = 0.0

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        self._cooldown = max(0.0, self._cooldown - dt)
        if frame is not None and not frame.is_silent:
            self._maybe_launch(frame)
        self._advance(dt, w, h)
        self._render(surface, w, h)

    def _maybe_launch(self, frame: AnalysisFrame) -> None:
        max_rockets = 2 if self.reduce_motion else 5
        if (
            frame.onset > _ONSET_THRESHOLD
            and self._cooldown <= 0.0
            and len(self._rockets) < max_rockets
        ):
            self._cooldown = _LAUNCH_COOLDOWN
            self._rockets.append(
                _Rocket(
                    x=self._rng.uniform(0.2, 0.8),
                    y=1.02,
                    vy=self._rng.uniform(*_ROCKET_VY),
                    hue=self._rng.random(),
                )
            )

    def _advance(self, dt: float, w: int, h: int) -> None:
        move = dt * self.theme.speed_scale
        still_flying: list[_Rocket] = []
        for r in self._rockets:
            r.y += r.vy * move
            r.vy += _GRAVITY * move
            if r.vy >= 0.0 or r.y < 0.12:  # apex reached -> burst
                self._burst(r)
            else:
                still_flying.append(r)
        self._rockets = still_flying
        self._sparks.advance(dt, self.theme.speed_scale, gravity=_GRAVITY)

    def _burst(self, rocket: _Rocket) -> None:
        peak_gain = 0.4 + 0.6 * clamp(abs(rocket.vy) * 1.5)
        base = _BURST_SPARKS * self.option("size") * peak_gain
        count = int(base / REDUCE_MOTION_BURST_DIVISOR if self.reduce_motion else base)
        for _ in range(max(8, count)):
            ang = self._rng.uniform(0.0, math.tau)
            spd = self._rng.uniform(*_BURST_SPEED)
            self._sparks.spawn(
                rocket.x,
                rocket.y,
                math.cos(ang) * spd,
                math.sin(ang) * spd,
                hue=(rocket.hue + self._rng.uniform(-0.05, 0.05)) % 1.0,
                size=self._rng.uniform(0.7, 1.3),
            )

    def _render(self, surface: pygame.Surface, w: int, h: int) -> None:
        scheme, phase = self.theme.color_scheme, self.theme.color_phase
        for r in self._rockets:  # bright rising head
            color = scale_color(themed_color(scheme, r.hue, PALETTE, phase), 1.0)
            pygame.draw.circle(surface, color, (int(r.x * w), int(r.y * h)), 2)
        self._sparks.render(surface, scheme, phase, w, h, self.theme.size_scale, trails=True)
