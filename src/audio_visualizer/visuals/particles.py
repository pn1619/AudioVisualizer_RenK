"""Particles: onset-driven sparks, as an omnidirectional burst or spiral arms.

``Emitter = Field`` bursts sparks outward from the center with gentle gravity (the
classic Particles). ``Emitter = Spiral`` blows per-band sparks out along rotating
spiral arms (the old Particles Spiral). Burst/Gravity tune the Field; Swirl/Size/
Spacing tune the Spiral.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import (
    ONSET_THRESHOLD,
    PALETTE,
    PARTICLE_BRIGHTNESS_FLOOR,
    PARTICLE_BURST,
    PARTICLE_LIFETIME,
    PARTICLE_MAX,
    PARTICLE_MAX_REDUCED,
    REDUCE_MOTION_BURST_DIVISOR,
    SPIRAL_BURST,
    SPIRAL_LIFETIME,
    SPIRAL_MAX,
    SPIRAL_MAX_REDUCED,
)
from audio_visualizer.visuals._helpers import clamp, scale_color, themed_color
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

# Field emitter tuning.
_SPEED_BASE = 0.15
_SPEED_RMS_GAIN = 0.6
_SPEED_SPREAD = (0.3, 1.0)
_FIELD_RADIUS_BASE = 2
_FIELD_RADIUS_GROWTH = 4
# Spiral emitter tuning.
_BIRTH_RADIUS = 0.02
_MAX_RADIUS = 1.2
_ANGULAR_BASE = 0.4
_RADIAL_BASE = 0.15
_RADIAL_ENERGY_GAIN = 0.5
_SWIRL_REDUCED = 1.0
_SPIRAL_SPAWN_RMS_GAIN = 1.5
_SPIRAL_RADIUS_BASE = 1
_SPIRAL_RADIUS_GROWTH = 3

_EMITTER_FIELD, _EMITTER_SPIRAL = 0, 1

_PRESET = ModeOption(
    "preset",
    "Preset",
    (OptionChoice("Custom", 0), OptionChoice("Field", 1), OptionChoice("Spiral", 2)),
    default_index=0,
)
_EMITTER = ModeOption(
    "emitter",
    "Emitter",
    (OptionChoice("Field", _EMITTER_FIELD), OptionChoice("Spiral", _EMITTER_SPIRAL)),
    default_index=0,
)
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
class _Particle:
    """A field spark in normalized (0..1) screen space."""

    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    hue: float


@dataclass
class _Spark:
    """A spiral spark in polar terms: radius (fraction of half-min-side) + angle."""

    r: float
    theta: float
    ang_speed: float
    radial_speed: float
    life: float
    max_life: float
    hue: float


@register(key="particles", display_name="Particles", order=40)
class Particles(BaseVisualizer):
    """Onset-driven sparks; Field bursts outward, Spiral traces rotating arms."""

    STROBES = True
    OPTIONS = (_PRESET, _EMITTER, _BURST, _GRAVITY, _SWIRL, _REACH, _SPACING)
    PRESETS = {
        1: {"emitter": _EMITTER_FIELD},
        2: {"emitter": _EMITTER_SPIRAL, "swirl": 1},
    }

    def __init__(
        self, reduce_motion: bool = False, theme: Theme | None = None, seed: int = 1234
    ) -> None:
        super().__init__(reduce_motion, theme)
        self._seed = seed
        self._rng = random.Random(seed)
        self._particles: list[_Particle] = []
        self._sparks: list[_Spark] = []

    def on_enter(self) -> None:
        self._particles.clear()
        self._sparks.clear()
        self._rng.seed(self._seed)

    def on_option_change(self, key: str) -> None:
        super().on_option_change(key)
        # Switching emitter (directly or via a preset) abandons the other pool so
        # dormant particles don't reappear when switching back.
        if key in ("emitter", "preset"):
            self._particles.clear()
            self._sparks.clear()

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 2 or h < 2:
            return
        if int(self.option("emitter")) == _EMITTER_SPIRAL:
            self._spawn_spiral(frame)
            self._advance_spiral(dt)
            self._render_spiral(surface, w, h)
        else:
            self._spawn_field(frame)
            self._advance_field(dt)
            self._render_field(surface, w, h)

    # -- field emitter --------------------------------------------------------
    def _spawn_field(self, frame: AnalysisFrame | None) -> None:
        if frame is None or frame.is_silent or frame.onset < ONSET_THRESHOLD:
            return
        cap = PARTICLE_MAX_REDUCED if self.reduce_motion else PARTICLE_MAX
        burst = max(1, int(PARTICLE_BURST * self.option("burst")))
        if self.reduce_motion:
            burst //= REDUCE_MOTION_BURST_DIVISOR
        speed = _SPEED_BASE + frame.rms * _SPEED_RMS_GAIN
        for _ in range(burst):
            if len(self._particles) >= cap:
                break
            angle = self._rng.uniform(0.0, 2.0 * math.pi)
            mag = speed * self._rng.uniform(*_SPEED_SPREAD)
            self._particles.append(
                _Particle(
                    0.5,
                    0.5,
                    math.cos(angle) * mag,
                    math.sin(angle) * mag,
                    PARTICLE_LIFETIME,
                    PARTICLE_LIFETIME,
                    self._rng.random(),
                )
            )

    def _advance_field(self, dt: float) -> None:
        move_dt = dt * self.theme.speed_scale
        gravity = self.option("gravity")
        alive: list[_Particle] = []
        for p in self._particles:
            p.life -= dt
            if p.life <= 0.0:
                continue
            p.x += p.vx * move_dt
            p.y += p.vy * move_dt
            p.vy += gravity * move_dt
            alive.append(p)
        self._particles = alive

    def _render_field(self, surface: pygame.Surface, w: int, h: int) -> None:
        for p in self._particles:
            t = clamp(p.life / p.max_life)
            radius = max(
                1, int((_FIELD_RADIUS_BASE + t * _FIELD_RADIUS_GROWTH) * self.theme.size_scale)
            )
            base = themed_color(self.theme.color_scheme, p.hue, PALETTE, self.theme.color_phase)
            brightness = t if self.reduce_motion else PARTICLE_BRIGHTNESS_FLOOR + t
            pygame.draw.circle(
                surface, scale_color(base, brightness), (int(p.x * w), int(p.y * h)), radius
            )

    # -- spiral emitter -------------------------------------------------------
    def _spawn_spiral(self, frame: AnalysisFrame | None) -> None:
        if frame is None or frame.is_silent or frame.band_energies.size == 0:
            return
        bands = frame.band_energies
        cap = SPIRAL_MAX_REDUCED if self.reduce_motion else SPIRAL_MAX
        base = SPIRAL_BURST // REDUCE_MOTION_BURST_DIVISOR if self.reduce_motion else SPIRAL_BURST
        n_spawn = int(base * clamp(frame.rms * _SPIRAL_SPAWN_RMS_GAIN + frame.onset))
        swirl = _SWIRL_REDUCED if self.reduce_motion else self.option("swirl")
        spacing = self.option("spacing")
        for _ in range(n_spawn):
            if len(self._sparks) >= cap:
                break
            bi = self._rng.randrange(bands.size)
            energy = float(bands[bi])
            self._sparks.append(
                _Spark(
                    _BIRTH_RADIUS,
                    self._rng.uniform(0.0, 2.0 * math.pi),
                    swirl * (_ANGULAR_BASE + energy),
                    (_RADIAL_BASE + energy * _RADIAL_ENERGY_GAIN) * spacing,
                    SPIRAL_LIFETIME,
                    SPIRAL_LIFETIME,
                    bi / bands.size,
                )
            )

    def _advance_spiral(self, dt: float) -> None:
        move_dt = dt * self.theme.speed_scale
        alive: list[_Spark] = []
        for s in self._sparks:
            s.life -= dt
            if s.life <= 0.0 or s.r > _MAX_RADIUS:
                continue
            s.r += s.radial_speed * move_dt
            s.theta += s.ang_speed * move_dt
            alive.append(s)
        self._sparks = alive

    def _render_spiral(self, surface: pygame.Surface, w: int, h: int) -> None:
        cx, cy = w / 2.0, h / 2.0
        scale = min(w, h) * 0.5 * self.option("reach")
        scheme = self.theme.color_scheme
        phase = self.theme.color_phase
        for s in self._sparks:
            t = clamp(s.life / s.max_life)
            px = int(cx + math.cos(s.theta) * s.r * scale)
            py = int(cy + math.sin(s.theta) * s.r * scale)
            radius = max(
                1, int((_SPIRAL_RADIUS_BASE + t * _SPIRAL_RADIUS_GROWTH) * self.theme.size_scale)
            )
            brightness = t if self.reduce_motion else PARTICLE_BRIGHTNESS_FLOOR + t
            pygame.draw.circle(
                surface,
                scale_color(themed_color(scheme, s.hue, PALETTE, phase), brightness),
                (px, py),
                radius,
            )
