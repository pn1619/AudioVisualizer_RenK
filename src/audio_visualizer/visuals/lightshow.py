"""Light-show mode: radial beams from center + a pulsing core driven by energy."""

from __future__ import annotations

import math

import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import PALETTE
from audio_visualizer.visuals._helpers import scale_color, themed_color
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_BEAM_WIDTH = ModeOption(
    "beam_width",
    "Beam",
    (OptionChoice("Thin", 1), OptionChoice("Normal", 3), OptionChoice("Thick", 6)),
    default_index=1,
)


@register(key="lightshow", display_name="Light Show", order=30)
class LightShow(BaseVisualizer):
    """Beams radiate from the center; length/brightness follow band energy."""

    STROBES = True
    OPTIONS = (_BEAM_WIDTH,)

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._angle = 0.0

    def on_enter(self) -> None:
        self._angle = 0.0

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        cx, cy = w / 2.0, h / 2.0
        max_len = min(w, h) * 0.48

        if frame is None:
            return

        bands = frame.band_energies
        count = bands.size
        if count == 0:
            return

        scheme = self.theme.color_scheme
        phase = self.theme.color_phase
        max_width = int(self.option("beam_width"))
        # Slow rotation for life; disabled when reduce-motion is on.
        if not self.reduce_motion:
            self._angle = (self._angle + dt * 0.3 * self.theme.speed_scale) % (2.0 * math.pi)

        # Pulsing core from overall level.
        core_r = max(2.0, frame.rms * max_len * 1.5)
        core_color = scale_color(themed_color(scheme, frame.peak, PALETTE, phase), 1.0)
        pygame.draw.circle(surface, core_color, (int(cx), int(cy)), int(core_r))

        for i in range(count):
            energy = float(bands[i])
            if energy <= 0.01:
                continue
            angle = self._angle + (2.0 * math.pi * i / count)
            length = energy * max_len
            ex = cx + math.cos(angle) * length
            ey = cy + math.sin(angle) * length
            color = scale_color(
                themed_color(scheme, i / max(1, count - 1), PALETTE, phase), 0.5 + energy
            )
            width = 1 if self.reduce_motion else max(1, int(1 + energy * max_width))
            pygame.draw.line(surface, color, (cx, cy), (ex, ey), width)
