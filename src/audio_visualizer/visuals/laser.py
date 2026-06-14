"""Laser mode: rotating beams plus a Lissajous figure driven by band energy."""

from __future__ import annotations

import math

import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import PALETTE
from audio_visualizer.visuals._helpers import scale_color, themed_color
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_LISSAJOUS_POINTS = 96

_BEAMS_OPT = ModeOption(
    "beams",
    "Beams",
    (OptionChoice("4", 4), OptionChoice("8", 8), OptionChoice("12", 12)),
    default_index=1,
)


@register(key="laser", display_name="Laser", order=50)
class Laser(BaseVisualizer):
    """Beams sweep around the center; a Lissajous curve traces the spectrum."""

    STROBES = True
    OPTIONS = (_BEAMS_OPT,)

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._phase = 0.0

    def on_enter(self) -> None:
        self._phase = 0.0

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        cx, cy = w / 2.0, h / 2.0
        if frame is None or frame.is_silent:
            return

        bands = frame.band_energies
        if bands.size == 0 or w < 2 or h < 2:
            return

        spin = 0.4 if self.reduce_motion else 1.2 + frame.rms * 3.0
        self._phase = (self._phase + dt * spin * self.theme.speed_scale) % (2.0 * math.pi)

        self._draw_beams(surface, cx, cy, min(w, h) * 0.5, frame)
        self._draw_lissajous(surface, cx, cy, w, h, frame)

    def _draw_beams(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        radius: float,
        frame: AnalysisFrame,
    ) -> None:
        bands = frame.band_energies
        beams = int(self.option("beams"))
        phase = self.theme.color_phase
        for i in range(beams):
            energy = float(bands[i * bands.size // beams])
            angle = self._phase + (math.pi * i / beams)
            length = radius * (0.3 + energy)
            for direction in (1.0, -1.0):
                ex = cx + math.cos(angle) * length * direction
                ey = cy + math.sin(angle) * length * direction
                color = scale_color(
                    themed_color(self.theme.color_scheme, i / beams, PALETTE, phase), 0.5 + energy
                )
                width = 1 if self.reduce_motion else max(1, int(1 + energy * 4))
                pygame.draw.line(surface, color, (cx, cy), (ex, ey), width)

    def _draw_lissajous(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        w: int,
        h: int,
        frame: AnalysisFrame,
    ) -> None:
        ax = w * 0.35
        ay = h * 0.35
        a = 2.0 + frame.band_energies[: frame.band_energies.size // 2].mean() * 3.0
        b = 3.0 + frame.band_energies[frame.band_energies.size // 2 :].mean() * 3.0
        color = scale_color(
            themed_color(self.theme.color_scheme, frame.peak, PALETTE, self.theme.color_phase),
            0.6 + frame.rms,
        )
        points: list[tuple[float, float]] = []
        for k in range(_LISSAJOUS_POINTS + 1):
            t = 2.0 * math.pi * k / _LISSAJOUS_POINTS
            x = cx + math.sin(a * t + self._phase) * ax
            y = cy + math.sin(b * t) * ay
            points.append((x, y))
        if len(points) >= 2:
            pygame.draw.lines(surface, color, False, points, 2)
