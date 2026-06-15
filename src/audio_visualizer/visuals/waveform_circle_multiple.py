"""Waveform Circle Multiple: concentric oscilloscope rings, one per frequency band.

The spectrum is split into N equal ranges (N chosen by the user, up to 10). Each
concentric ring uses the mono waveform for its shape but its wobble amplitude is
scaled by that frequency range's energy, so low rings react to bass and outer rings
to treble. The user also controls overall size and the spacing between rings.
"""

from __future__ import annotations

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import CIRCLE_WAVE_AMPLITUDE
from audio_visualizer.visuals._helpers import draw_ring, ring_points
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
    default_index=3,  # 5 rings
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
_THICKNESS = ModeOption(
    "thickness",
    "Line",
    (OptionChoice("Thin", 1), OptionChoice("Normal", 2), OptionChoice("Thick", 3)),
    default_index=1,
)
_RING_POINTS = 200


@register(key="waveform_circle_multiple", display_name="Waveform Circle x N", order=18)
class WaveformCircleMultiple(BaseVisualizer):
    """N concentric oscilloscope rings, each driven by one equal spectrum slice."""

    OPTIONS = (_RINGS, _SIZE, _SPACING, _THICKNESS)

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 2 or h < 2:
            return
        cx, cy = w / 2.0, h / 2.0
        half = min(w, h) * 0.5
        rings = int(self.option("rings"))
        size = self.option("size")
        spacing = self.option("spacing")
        width = int(self.option("thickness"))

        inner = half * 0.12 * size
        gap = (half * 0.82 * size - inner) / max(1, rings)
        gap *= spacing
        amplitude = half * CIRCLE_WAVE_AMPLITUDE * 0.6 * size

        if frame is None or frame.is_silent:
            samples = np.zeros(_RING_POINTS, dtype=np.float32)
            energies = np.zeros(rings, dtype=np.float32)
        else:
            samples = frame.waveform_mono
            energies = self._range_energies(frame.band_energies, rings)

        scheme = self.theme.color_scheme
        phase = self.theme.color_phase
        for i in range(rings):
            base_r = inner + (i + 1) * gap
            amp_i = amplitude * (0.4 + float(energies[i]))
            points = ring_points(cx, cy, base_r, amp_i, samples, _RING_POINTS)
            draw_ring(surface, scheme, phase, points, width, hue_offset=i / max(1, rings))

    @staticmethod
    def _range_energies(bands: np.ndarray, rings: int) -> np.ndarray:
        """Mean energy of each of ``rings`` equal slices of the spectrum."""
        if bands.size == 0:
            return np.zeros(rings, dtype=np.float32)
        edges = np.linspace(0, bands.size, rings + 1).astype(int)
        return np.array(
            [bands[edges[i] : max(edges[i] + 1, edges[i + 1])].mean() for i in range(rings)],
            dtype=np.float32,
        )
