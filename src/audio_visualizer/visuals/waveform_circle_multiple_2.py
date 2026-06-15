"""Waveform Circle Multiple 2: concentric per-band rings plus popping particles.

Like Waveform Circle x N, with onset/energy-driven sparks that pop off the rings
(louder frequency ranges shed more sparks). User controls ring count, size, spacing.
"""

from __future__ import annotations

import random

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import CIRCLE_WAVE_AMPLITUDE
from audio_visualizer.visuals._helpers import RingPops, clamp, draw_ring, ring_points
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

        inner = half * 0.12 * size
        gap = ((half * 0.82 * size - inner) / max(1, rings)) * spacing
        amplitude = half * CIRCLE_WAVE_AMPLITUDE * 0.6 * size

        if frame is None or frame.is_silent:
            samples = np.zeros(_RING_POINTS, dtype=np.float32)
            energies = np.zeros(rings, dtype=np.float32)
        else:
            samples = frame.waveform_mono
            energies = _range_energies(frame.band_energies, rings)

        scheme = self.theme.color_scheme
        phase = self.theme.color_phase
        for i in range(rings):
            base_r = inner + (i + 1) * gap
            amp_i = amplitude * (0.4 + float(energies[i]))
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
        base = _POP_BURST // 3 if self.reduce_motion else _POP_BURST
        rate = self.option("pop_rate")
        for i in range(rings):
            energy = float(energies[i])
            count = int(base * rate * clamp(energy * 1.5 + frame.onset * 0.5))
            if count <= 0:
                continue
            ring_fraction = (inner + (i + 1) * gap) / half
            self._pops.spawn(self._rng, count, ring_fraction, energy)


def _range_energies(bands: np.ndarray, rings: int) -> np.ndarray:
    """Mean energy of each of ``rings`` equal slices of the spectrum."""
    if bands.size == 0:
        return np.zeros(rings, dtype=np.float32)
    edges = np.linspace(0, bands.size, rings + 1).astype(int)
    return np.array(
        [bands[edges[i] : max(edges[i] + 1, edges[i + 1])].mean() for i in range(rings)],
        dtype=np.float32,
    )
