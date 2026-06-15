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
# Beam spin (radians/sec): a calm fixed rate under reduce-motion, else base + rms gain.
_SPIN_REDUCED = 0.4
_SPIN_BASE = 1.2
_SPIN_RMS_GAIN = 3.0
# Beam length = radius * (this + band energy).
_BEAM_LENGTH_BASE = 0.3
# Beam line width = 1 + energy * this (full-motion only).
_BEAM_WIDTH_GAIN = 4
# Baseline beam brightness before per-beam energy is added.
_BEAM_BRIGHTNESS_BASE = 0.5
# Lissajous figure half-extent as a fraction of the canvas width/height.
_LISSAJOUS_EXTENT = 0.35
# Lissajous x/y frequencies = base + (band-half energy * gain).
_LISSAJOUS_FREQ_X_BASE = 2.0
_LISSAJOUS_FREQ_Y_BASE = 3.0
_LISSAJOUS_FREQ_GAIN = 3.0
# Lissajous brightness floor before rms is added.
_LISSAJOUS_BRIGHTNESS_BASE = 0.6

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

        spin = _SPIN_REDUCED if self.reduce_motion else _SPIN_BASE + frame.rms * _SPIN_RMS_GAIN
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
            length = radius * (_BEAM_LENGTH_BASE + energy)
            for direction in (1.0, -1.0):
                ex = cx + math.cos(angle) * length * direction
                ey = cy + math.sin(angle) * length * direction
                color = scale_color(
                    themed_color(self.theme.color_scheme, i / beams, PALETTE, phase),
                    _BEAM_BRIGHTNESS_BASE + energy,
                )
                width = 1 if self.reduce_motion else max(1, int(1 + energy * _BEAM_WIDTH_GAIN))
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
        ax = w * _LISSAJOUS_EXTENT
        ay = h * _LISSAJOUS_EXTENT
        bands = frame.band_energies
        low_mean = bands[: bands.size // 2].mean()
        high_mean = bands[bands.size // 2 :].mean()
        a = _LISSAJOUS_FREQ_X_BASE + low_mean * _LISSAJOUS_FREQ_GAIN
        b = _LISSAJOUS_FREQ_Y_BASE + high_mean * _LISSAJOUS_FREQ_GAIN
        color = scale_color(
            themed_color(self.theme.color_scheme, frame.peak, PALETTE, self.theme.color_phase),
            _LISSAJOUS_BRIGHTNESS_BASE + frame.rms,
        )
        points: list[tuple[float, float]] = []
        for k in range(_LISSAJOUS_POINTS + 1):
            t = 2.0 * math.pi * k / _LISSAJOUS_POINTS
            x = cx + math.sin(a * t + self._phase) * ax
            y = cy + math.sin(b * t) * ay
            points.append((x, y))
        if len(points) >= 2:
            pygame.draw.lines(surface, color, False, points, 2)
