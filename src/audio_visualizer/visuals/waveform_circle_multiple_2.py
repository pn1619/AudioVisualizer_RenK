"""Waveform Circle Multiple 2: concentric per-band rings plus popping particles.

Like Waveform Circle x N, with onset/energy-driven sparks that pop off the rings
(louder frequency ranges shed more sparks). User controls ring count, size, spacing.
"""

from __future__ import annotations

import random

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import (
    CIRCLE_INNER_FRACTION,
    CIRCLE_OUTER_FRACTION,
    CIRCLE_RING_AMP_BASE,
    CIRCLE_RING_AMP_FACTOR,
    CIRCLE_WAVE_AMPLITUDE,
    REDUCE_MOTION_BURST_DIVISOR,
)
from audio_visualizer.visuals._helpers import (
    RingPops,
    clamp,
    draw_ring,
    range_energies,
    ring_points,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice
from audio_visualizer.visuals.registry import register

_RINGS = ModeOption(
    "rings",
    "Rings",
    (
        OptionChoice("2", 2),
        OptionChoice("3", 3),
        OptionChoice("4", 4),
        OptionChoice("5", 5),
        OptionChoice("6", 6),
        OptionChoice("8", 8),
        OptionChoice("10", 10),
    ),
    default_index=2,  # 4 rings
)
_SIZE = ModeOption(
    "size",
    "Size",
    (OptionChoice("Small", 0.7), OptionChoice("Normal", 1.0), OptionChoice("Large", 1.3)),
    default_index=1,
)
_SPACING = ModeOption(
    "spacing",
    "Spacing",
    (OptionChoice("Tight", 0.6), OptionChoice("Normal", 1.0), OptionChoice("Wide", 1.6)),
    default_index=1,
)
_POP_RATE = ModeOption(
    "pop_rate",
    "Pops",
    (OptionChoice("Few", 0.5), OptionChoice("Normal", 1.0), OptionChoice("Many", 2.0)),
    default_index=1,
)
_RING_POINTS = 200
_POP_MAX = 320
_POP_MAX_REDUCED = 100
_POP_BURST = 8
# Per-ring spawn count scales with: ring energy * gain + onset * gain (clamped 0..1).
_SPAWN_ENERGY_GAIN = 1.5
_SPAWN_ONSET_GAIN = 0.5


@register(key="waveform_circle_multiple_2", display_name="Waveform Circle x N 2", order=19)
class WaveformCircleMultiple2(BaseVisualizer):
    """N per-band oscilloscope rings + popping particles shed from each ring."""

    def __init__(self, reduce_motion: bool = False, seed: int = 909) -> None:
        super().__init__(reduce_motion)
        self._seed = seed
        self._rng = random.Random(seed)
        cap = _POP_MAX_REDUCED if reduce_motion else _POP_MAX
        self._pops = RingPops(cap)

    OPTIONS = (_RINGS, _SIZE, _SPACING, _POP_RATE)

    def on_enter(self) -> None:
        self._pops.clear()
        self._rng.seed(self._seed)

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 2 or h < 2:
            return
        cx, cy = w / 2.0, h / 2.0
        half = min(w, h) * 0.5
        rings = int(self.option("rings"))
        size = self.option("size")
        spacing = self.option("spacing")

        inner = half * CIRCLE_INNER_FRACTION * size
        gap = ((half * CIRCLE_OUTER_FRACTION * size - inner) / max(1, rings)) * spacing
        amplitude = half * CIRCLE_WAVE_AMPLITUDE * CIRCLE_RING_AMP_FACTOR * size

        if frame is None or frame.is_silent:
            samples = np.zeros(_RING_POINTS, dtype=np.float32)
            energies = np.zeros(rings, dtype=np.float32)
        else:
            samples = frame.waveform_mono
            energies = range_energies(frame.band_energies, rings)

        scheme = self.theme.color_scheme
        phase = self.theme.color_phase
        for i in range(rings):
            base_r = inner + (i + 1) * gap
            amp_i = amplitude * (CIRCLE_RING_AMP_BASE + float(energies[i]))
            points = ring_points(cx, cy, base_r, amp_i, samples, _RING_POINTS)
            draw_ring(surface, scheme, phase, points, 2, hue_offset=i / max(1, rings))

        if frame is not None and not frame.is_silent:
            self._spawn(rings, inner, gap, half, energies, frame)
        self._pops.advance(dt, self.theme.speed_scale)
        self._pops.render(surface, scheme, phase, cx, cy, half, self.theme.size_scale)

    def _spawn(
        self,
        rings: int,
        inner: float,
        gap: float,
        half: float,
        energies: np.ndarray,
        frame: AnalysisFrame,
    ) -> None:
        base = _POP_BURST // REDUCE_MOTION_BURST_DIVISOR if self.reduce_motion else _POP_BURST
        rate = self.option("pop_rate")
        for i in range(rings):
            energy = float(energies[i])
            spawn_drive = clamp(energy * _SPAWN_ENERGY_GAIN + frame.onset * _SPAWN_ONSET_GAIN)
            count = int(base * rate * spawn_drive)
            if count <= 0:
                continue
            ring_fraction = (inner + (i + 1) * gap) / half
            self._pops.spawn(self._rng, count, ring_fraction, energy)
