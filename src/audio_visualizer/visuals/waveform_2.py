"""Waveform 2: the oscilloscope trace with particles popping in/out of the line.

Sparks spawn along the waveform (more where the signal is loud / on onsets),
swell from nothing to full size and shrink back ("pop in and out") while drifting
away from the center line. Honors the shared theme (size, speed, color scheme).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import (
    COLOR_ACCENT,
    IDLE_LINE_HUE,
    PALETTE,
    PARTICLE_BRIGHTNESS_FLOOR,
    REDUCE_MOTION_BURST_DIVISOR,
)
from audio_visualizer.visuals._helpers import clamp, rainbow_color, scale_color, themed_color
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice
from audio_visualizer.visuals.registry import register

_POP_MAX = 260
_POP_MAX_REDUCED = 80
_POP_BURST = 10
_POP_LIFETIME = 0.7
# Peak trace height as a fraction of the half-canvas-height.
_AMPLITUDE_FRACTION = 0.9
# Spawn count scales with this * rms + onset (clamped to 0..1).
_SPAWN_RMS_GAIN = 1.2
# Pop initial vertical speed = this base + rms * gain (normalized units/sec).
_POP_SPEED_BASE = 0.10
_POP_SPEED_RMS_GAIN = 0.25
# A spark sits this far off the line (fraction) for a full-scale sample.
_POP_OFFSET_FRACTION = 0.45
# Pop radius (px) = base + envelope * growth, scaled by the size control.
_POP_RADIUS_BASE = 1
_POP_RADIUS_GROWTH = 5

_POP_RATE = ModeOption(
    "pop_rate",
    "Pops",
    (OptionChoice("Few", 0.5), OptionChoice("Normal", 1.0), OptionChoice("Many", 2.0)),
    default_index=1,
)
_THICKNESS = ModeOption(
    "thickness",
    "Line",
    (OptionChoice("Thin", 1), OptionChoice("Normal", 2), OptionChoice("Thick", 4)),
    default_index=1,
)


@dataclass
class _Pop:
    """A spark in normalized (0..1) space that swells then fades."""

    x: float
    y: float
    vy: float
    life: float
    max_life: float
    hue: float


@register(key="waveform_2", display_name="Waveform 2", order=15)
class Waveform2(BaseVisualizer):
    """Oscilloscope line plus onset/energy-driven popping particles."""

    OPTIONS = (_POP_RATE, _THICKNESS)

    def __init__(self, reduce_motion: bool = False, seed: int = 777) -> None:
        super().__init__(reduce_motion)
        self._seed = seed
        self._rng = random.Random(seed)
        self._pops: list[_Pop] = []

    def on_enter(self) -> None:
        self._pops.clear()
        self._rng.seed(self._seed)

    @property
    def _cap(self) -> int:
        return _POP_MAX_REDUCED if self.reduce_motion else _POP_MAX

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 2 or h < 2:
            return
        self._draw_trace(surface, frame, w, h)
        if frame is not None and not frame.is_silent:
            self._spawn(frame)
        self._advance(dt)
        self._render(surface, w, h)

    def _draw_trace(
        self, surface: pygame.Surface, frame: AnalysisFrame | None, w: int, h: int
    ) -> None:
        mid = h // 2
        scheme = self.theme.color_scheme
        phase = self.theme.color_phase
        colored = scheme != "classic"
        width = int(self.option("thickness"))
        if frame is None or frame.is_silent:
            color = rainbow_color(IDLE_LINE_HUE + phase) if colored else COLOR_ACCENT
            pygame.draw.line(surface, color, (0, mid), (w, mid), width)
            return
        samples = frame.waveform_mono
        if samples.size < 2:
            return
        step = max(1, samples.size // w)
        pts = samples[::step]
        n = pts.size
        xs = np.linspace(0, w, n)
        ys = mid - pts * (mid * _AMPLITUDE_FRACTION)
        points = [(float(x), float(y)) for x, y in zip(xs, ys, strict=False)]
        if colored:
            for i in range(len(points) - 1):
                col = themed_color(scheme, i / n, PALETTE, phase)
                pygame.draw.line(surface, col, points[i], points[i + 1], width)
        else:
            pygame.draw.lines(surface, COLOR_ACCENT, False, points, width)

    def _sample_at(self, samples: np.ndarray, x: float) -> float:
        idx = int(clamp(x) * (samples.size - 1))
        return float(samples[idx])

    def _spawn(self, frame: AnalysisFrame) -> None:
        samples = frame.waveform_mono
        if samples.size < 2:
            return
        base = _POP_BURST // REDUCE_MOTION_BURST_DIVISOR if self.reduce_motion else _POP_BURST
        count = int(
            base * self.option("pop_rate") * clamp(frame.rms * _SPAWN_RMS_GAIN + frame.onset)
        )
        for _ in range(count):
            if len(self._pops) >= self._cap:
                break
            x = self._rng.random()
            value = self._sample_at(samples, x)
            y = 0.5 - value * _POP_OFFSET_FRACTION
            direction = -1.0 if value >= 0 else 1.0  # pop away from the center line
            speed = _POP_SPEED_BASE + frame.rms * _POP_SPEED_RMS_GAIN
            self._pops.append(
                _Pop(
                    x=x,
                    y=y,
                    vy=direction * speed * self._rng.uniform(0.5, 1.0),
                    life=_POP_LIFETIME,
                    max_life=_POP_LIFETIME,
                    hue=x,
                )
            )

    def _advance(self, dt: float) -> None:
        move_dt = dt * self.theme.speed_scale
        alive: list[_Pop] = []
        for p in self._pops:
            p.life -= dt
            if p.life <= 0.0:
                continue
            p.y += p.vy * move_dt
            alive.append(p)
        self._pops = alive

    def _render(self, surface: pygame.Surface, w: int, h: int) -> None:
        scheme = self.theme.color_scheme
        phase = self.theme.color_phase
        for p in self._pops:
            progress = clamp(1.0 - p.life / p.max_life)
            envelope = math.sin(math.pi * progress)  # 0 -> 1 -> 0 (pop in/out)
            radius = max(
                1, int((_POP_RADIUS_BASE + envelope * _POP_RADIUS_GROWTH) * self.theme.size_scale)
            )
            color = scale_color(
                themed_color(scheme, p.hue, PALETTE, phase), PARTICLE_BRIGHTNESS_FLOOR + envelope
            )
            pygame.draw.circle(surface, color, (int(p.x * w), int(p.y * h)), radius)
