"""Waveform Circle: the oscilloscope trace wrapped around a ring.

Mono samples are mapped around a circle (angle = position in the buffer, radius =
base radius + sample amplitude), so the whole waveform reads as a pulsing ring.
Honors the shared theme (color scheme) and exposes its own size + thickness options.
"""

from __future__ import annotations

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import (
    CIRCLE_BASE_RADIUS,
    CIRCLE_WAVE_AMPLITUDE,
)
from audio_visualizer.visuals._helpers import draw_ring, ring_points
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
_RING_POINTS = 240


@register(key="waveform_circle", display_name="Waveform Circle", order=16)
class WaveformCircle(BaseVisualizer):
    """A single oscilloscope ring; radius wobbles with the mono samples."""

    OPTIONS = (_SIZE, _THICKNESS)

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

        if frame is None or frame.is_silent:
            samples = np.zeros(_RING_POINTS, dtype=np.float32)
        else:
            samples = frame.waveform_mono

        points = ring_points(cx, cy, base_r, amplitude, samples, _RING_POINTS)
        draw_ring(surface, self.theme.color_scheme, self.theme.color_phase, points, width)
