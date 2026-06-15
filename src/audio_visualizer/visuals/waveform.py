"""Waveform (oscilloscope) mode: the mono signal drawn as a line."""

from __future__ import annotations

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import COLOR_ACCENT, IDLE_LINE_HUE, PALETTE
from audio_visualizer.visuals._helpers import rainbow_color, themed_color
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice
from audio_visualizer.visuals.registry import register

# Peak trace height as a fraction of the half-canvas-height (leaves a small margin).
_AMPLITUDE_FRACTION = 0.9

_THICKNESS = ModeOption(
    "thickness",
    "Line",
    (OptionChoice("Thin", 1), OptionChoice("Normal", 2), OptionChoice("Thick", 4)),
    default_index=1,
)


@register(key="waveform", display_name="Waveform", order=10)
class Waveform(BaseVisualizer):
    """Draws the mono samples as a centered horizontal trace."""

    OPTIONS = (_THICKNESS,)

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        mid = h // 2
        width = int(self.option("thickness"))
        scheme = self.theme.color_scheme
        colored = scheme != "classic"

        if frame is None or frame.is_silent:
            idle_hue = IDLE_LINE_HUE + self.theme.color_phase
            color = rainbow_color(idle_hue) if colored else COLOR_ACCENT
            pygame.draw.line(surface, color, (0, mid), (w, mid), width)
            return

        samples = frame.waveform_mono
        if samples.size < 2 or w < 2:
            return

        # Decimate samples down to roughly one point per pixel column.
        step = max(1, samples.size // w)
        pts = samples[::step]
        n = pts.size
        amp = mid * _AMPLITUDE_FRACTION
        xs = np.linspace(0, w, n)
        ys = mid - pts * amp
        points = [(float(x), float(y)) for x, y in zip(xs, ys, strict=False)]

        if colored:
            # Color each segment by its horizontal position (hue sweep + time phase).
            phase = self.theme.color_phase
            for i in range(len(points) - 1):
                color = themed_color(scheme, i / n, PALETTE, phase)
                pygame.draw.line(surface, color, points[i], points[i + 1], width)
        else:
            pygame.draw.lines(surface, COLOR_ACCENT, False, points, width)
