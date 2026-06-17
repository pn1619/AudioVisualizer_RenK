"""Audio Sun: spectrum bars radiating outward in a full circle.

One ray per spectrum slice points out from a glowing core; ray length follows that
band's energy and hue sweeps around the ring. A faint oscilloscope ring threads the
ray bases. Differs from the waveform-circle modes (those are *lines*; this is radial
*bars*). Optional mirroring makes the ring left-right symmetric.
"""

from __future__ import annotations

import math

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import COLOR_ACCENT, PALETTE
from audio_visualizer.visuals._helpers import draw_ring, resample_to, ring_points, themed_color
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_RAYS = 120  # rays placed around the ring (bands are resampled to this)
_CORE_FRACTION = 0.16  # inner radius (ray bases) as a fraction of min(w, h)/2
_LEN_FRACTION = 0.62  # max ray length as a fraction of min(w, h)/2
_ROTATE_RATE = 0.04  # base revolutions per second (scaled by speed)

_MIRROR = ModeOption(
    "mirror", "Mirror", (OptionChoice("On", 1), OptionChoice("Off", 0)), default_index=0
)
_THICKNESS = ModeOption(
    "thickness",
    "Rays",
    (OptionChoice("Thin", 2), OptionChoice("Normal", 3), OptionChoice("Bold", 5)),
    default_index=1,
)


@register(key="radial_spectrum", display_name="Audio Sun", order=22)
class RadialSpectrum(BaseVisualizer):
    """Radial spectrum rays around a glowing core + a thin oscilloscope ring."""

    OPTIONS = (_MIRROR, _THICKNESS)

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._angle = 0.0

    def on_enter(self) -> None:
        self._angle = 0.0

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        cx, cy = w / 2.0, h / 2.0
        scale = min(w, h) / 2.0
        core_r = scale * _CORE_FRACTION
        max_len = scale * _LEN_FRACTION
        scheme, phase = self.theme.color_scheme, self.theme.color_phase

        spin = 0.0 if self.reduce_motion else _ROTATE_RATE
        self._angle = (self._angle + dt * self.theme.speed_scale * spin * math.tau) % math.tau

        self._draw_core(surface, cx, cy, core_r, frame)
        if frame is not None and frame.waveform_mono.size > 1:
            pts = ring_points(cx, cy, core_r, scale * 0.05, frame.waveform_mono, points=180)
            draw_ring(surface, scheme, phase, pts, width=1)

        rays = self._ray_energies(frame)
        width = int(self.option("thickness"))
        for i, energy in enumerate(rays):
            ang = self._angle + (i / _RAYS) * math.tau
            length = core_r + float(energy) * max_len
            ix, iy = cx + math.cos(ang) * core_r, cy + math.sin(ang) * core_r
            ox, oy = cx + math.cos(ang) * length, cy + math.sin(ang) * length
            color = themed_color(scheme, i / _RAYS, PALETTE, phase)
            pygame.draw.line(surface, color, (ix, iy), (ox, oy), width)

    def _ray_energies(self, frame: AnalysisFrame | None) -> np.ndarray:
        if frame is None or frame.band_energies.size == 0:
            return np.zeros(_RAYS, dtype=np.float32)
        if self.option("mirror") >= 1:
            half = resample_to(frame.band_energies.astype(np.float32), _RAYS // 2)
            return np.concatenate([half, half[::-1]])
        return resample_to(frame.band_energies.astype(np.float32), _RAYS)

    def _draw_core(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        core_r: float,
        frame: AnalysisFrame | None,
    ) -> None:
        level = 0.0 if frame is None else min(1.0, frame.rms * 2.0)
        glow = pygame.Surface((int(core_r * 4), int(core_r * 4)), pygame.SRCALPHA)
        gc = glow.get_rect().center
        for ring in range(4, 0, -1):
            radius = int(core_r * (0.4 + 0.4 * ring))
            alpha = int(40 * ring * (0.5 + 0.5 * level))
            pygame.draw.circle(glow, (*COLOR_ACCENT, alpha), gc, radius)
        surface.blit(glow, glow.get_rect(center=(int(cx), int(cy))))
