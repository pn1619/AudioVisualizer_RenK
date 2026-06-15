"""Waveform Circle 2: the oscilloscope ring plus particles popping off of it.

Same ring as Waveform Circle, with onset/energy-driven sparks that pop in and out
along the ring and drift outward (the circular analog of Waveform 2).
"""

from __future__ import annotations

import random

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import (
    CIRCLE_BASE_RADIUS,
    CIRCLE_WAVE_AMPLITUDE,
)
from audio_visualizer.visuals._helpers import RingPops, clamp, draw_ring, ring_points
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice
from audio_visualizer.visuals.registry import register

_SIZE = ModeOption(
    "size",
    "Size",
    (OptionChoice("Small", 0.7), OptionChoice("Normal", 1.0), OptionChoice("Large", 1.4)),
    default_index=1,
)
_THICKNESS = ModeOption(
    "thickness",
    "Line",
    (OptionChoice("Thin", 1), OptionChoice("Normal", 2), OptionChoice("Thick", 4)),
    default_index=1,
)
_POP_RATE = ModeOption(
    "pop_rate",
    "Pops",
    (OptionChoice("Few", 0.5), OptionChoice("Normal", 1.0), OptionChoice("Many", 2.0)),
    default_index=1,
)
_RING_POINTS = 240
_POP_MAX = 260
_POP_MAX_REDUCED = 80
_POP_BURST = 10


@register(key="waveform_circle_2", display_name="Waveform Circle 2", order=17)
class WaveformCircle2(BaseVisualizer):
    """Oscilloscope ring + onset/energy-driven popping particles."""

    def __init__(self, reduce_motion: bool = False, seed: int = 555) -> None:
        super().__init__(reduce_motion)
        self._seed = seed
        self._rng = random.Random(seed)
        cap = _POP_MAX_REDUCED if reduce_motion else _POP_MAX
        self._pops = RingPops(cap)

    OPTIONS = (_SIZE, _THICKNESS, _POP_RATE)

    def on_enter(self) -> None:
        self._pops.clear()
        self._rng.seed(self._seed)

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 2 or h < 2:
            return
        cx, cy = w / 2.0, h / 2.0
        half = min(w, h) * 0.5
        size = self.option("size")
        base_r = half * CIRCLE_BASE_RADIUS * size
        amplitude = half * CIRCLE_WAVE_AMPLITUDE * size
        width = int(self.option("thickness"))

        samples = (
            np.zeros(_RING_POINTS, dtype=np.float32)
            if frame is None or frame.is_silent
            else frame.waveform_mono
        )
        points = ring_points(cx, cy, base_r, amplitude, samples, _RING_POINTS)
        draw_ring(surface, self.theme.color_scheme, self.theme.color_phase, points, width)

        if frame is not None and not frame.is_silent:
            self._spawn(frame)
        self._pops.advance(dt, self.theme.speed_scale)
        # Particles live in radius-fractions of ``half`` so the ring and pops align.
        self._pops.render(
            surface,
            self.theme.color_scheme,
            self.theme.color_phase,
            cx,
            cy,
            half,
            self.theme.size_scale,
        )

    def _spawn(self, frame: AnalysisFrame) -> None:
        base = _POP_BURST // 3 if self.reduce_motion else _POP_BURST
        count = int(base * self.option("pop_rate") * clamp(frame.rms * 1.2 + frame.onset))
        if count <= 0:
            return
        size = self.option("size")
        ring_fraction = CIRCLE_BASE_RADIUS * size  # normalized radius of the ring
        self._pops.spawn(self._rng, count, ring_fraction, frame.rms)
