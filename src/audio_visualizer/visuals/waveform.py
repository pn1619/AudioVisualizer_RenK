"""Waveform (oscilloscope) mode: the mono signal drawn as a line."""

from __future__ import annotations

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import COLOR_ACCENT
from audio_visualizer.visuals._helpers import rainbow_color
from audio_visualizer.visuals.base import BaseVisualizer
from audio_visualizer.visuals.registry import register


@register(key="waveform", display_name="Waveform", order=10)
class Waveform(BaseVisualizer):
    """Draws the mono samples as a centered horizontal trace."""

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        mid = h // 2
        rainbow = self.theme.color_scheme == "rainbow"

        if frame is None or frame.is_silent:
            color = rainbow_color(0.5) if rainbow else COLOR_ACCENT
            pygame.draw.line(surface, color, (0, mid), (w, mid), 2)
            return

        samples = frame.waveform_mono
        if samples.size < 2 or w < 2:
            return

        # Decimate samples down to roughly one point per pixel column.
        step = max(1, samples.size // w)
        pts = samples[::step]
        n = pts.size
        amp = mid * 0.9
        xs = np.linspace(0, w, n)
        ys = mid - pts * amp
        points = [(float(x), float(y)) for x, y in zip(xs, ys, strict=False)]

        if rainbow:
            # Color each segment by its horizontal position (hue sweep).
            for i in range(len(points) - 1):
                pygame.draw.line(surface, rainbow_color(i / n), points[i], points[i + 1], 2)
        else:
            pygame.draw.lines(surface, COLOR_ACCENT, False, points, 2)
