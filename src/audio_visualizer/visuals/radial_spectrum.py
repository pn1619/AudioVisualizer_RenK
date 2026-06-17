"""Audio Sun: spectrum bars radiating outward in a full circle.

One ray per spectrum slice points out from a glowing core; ray length follows that
band's energy and hue sweeps around the ring. The core is built from two smooth
concentric rings (plus a soft glow) whose colors flow around the circumference — they
can rotate together, counter-rotate, sit as a plain glow, or radiate beat rings. A
faint oscilloscope ring threads the ray bases.
"""

from __future__ import annotations

import math

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import COLOR_ACCENT, PALETTE
from audio_visualizer.visuals._helpers import (
    clamp,
    draw_ring,
    resample_to,
    ring_points,
    themed_color,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_RAYS = 120  # rays placed around the ring (bands are resampled to this)
_CORE_FRACTION = 0.16  # ray-base radius as a fraction of min(w, h)/2
_LEN_FRACTION = 0.62  # max ray length as a fraction of min(w, h)/2
_ROTATE_RATE = 0.04  # base ray-ring revolutions per second (scaled by speed)
_DISK_RATE = 0.12  # base core-ring color-flow revolutions per second
_RING_POINTS = 180  # smoothness of the core rings
_CIRCLE = np.zeros(_RING_POINTS, dtype=np.float32)  # flat values -> a perfect circle

_MIRROR = ModeOption(
    "mirror", "Mirror", (OptionChoice("On", 1), OptionChoice("Off", 0)), default_index=0
)
_THICKNESS = ModeOption(
    "thickness",
    "Rays",
    (OptionChoice("Thin", 2), OptionChoice("Normal", 3), OptionChoice("Bold", 5)),
    default_index=1,
)
# How the two core rings behave.
_DISKS = ModeOption(
    "disks",
    "Core",
    (
        OptionChoice("Rings", 0),
        OptionChoice("Counter", 1),
        OptionChoice("Glow", 2),
        OptionChoice("Radiate", 3),
    ),
    default_index=0,
)


@register(key="radial_spectrum", display_name="Audio Sun", order=22)
class RadialSpectrum(BaseVisualizer):
    """Radial spectrum rays around a glowing two-ring core + an oscilloscope ring."""

    OPTIONS = (_MIRROR, _THICKNESS, _DISKS)

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._angle = 0.0
        self._outer = 0.0  # outer-ring color-flow offset (0..1)
        self._inner = 0.0  # inner-ring color-flow offset (0..1)
        self._rings: list[float] = []  # normalized radii of radiating beat rings

    def on_enter(self) -> None:
        self._angle = self._outer = self._inner = 0.0
        self._rings.clear()

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

        self._draw_core(surface, cx, cy, core_r, scale, frame, dt)
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
        scale: float,
        frame: AnalysisFrame | None,
        dt: float,
    ) -> None:
        level = 0.0 if frame is None else min(1.0, frame.rms * 2.0)
        onset = 0.0 if frame is None else frame.onset
        mode = int(self.option("disks"))
        scheme, phase = self.theme.color_scheme, self.theme.color_phase

        step = 0.0 if self.reduce_motion else dt * self.theme.speed_scale * _DISK_RATE
        self._outer = (self._outer + step) % 1.0
        inner_dir = -1.0 if mode == 1 else 1.0  # "Counter" flows the inner ring backwards
        self._inner = (self._inner + inner_dir * step * 1.4) % 1.0

        self._glow(surface, cx, cy, core_r, level)
        if mode == 3:
            self._update_rings(surface, cx, cy, core_r, scale, onset, dt, scheme, phase)
        if mode in (0, 1):
            self._ring(
                surface, cx, cy, core_r, max(3, int(core_r * 0.22)), scheme, phase, self._outer
            )
            self._ring(
                surface,
                cx,
                cy,
                core_r * 0.58,
                max(2, int(core_r * 0.16)),
                scheme,
                phase,
                self._inner,
            )

    @staticmethod
    def _ring(
        surface: pygame.Surface,
        cx: float,
        cy: float,
        radius: float,
        width: int,
        scheme: str,
        phase: float,
        hue_offset: float,
    ) -> None:
        """A smooth circle whose hue flows around the circumference (no gaps)."""
        pts = ring_points(cx, cy, radius, 0.0, _CIRCLE, points=_RING_POINTS)
        draw_ring(surface, scheme, phase, pts, width, hue_offset=hue_offset)

    @staticmethod
    def _glow(surface: pygame.Surface, cx: float, cy: float, core_r: float, level: float) -> None:
        """Soft additive halo behind the core (the classic Audio Sun look)."""
        size = int(core_r * 6) + 2
        glow = pygame.Surface((size, size), pygame.SRCALPHA)
        gc = (size // 2, size // 2)
        for ring in range(5, 0, -1):
            r = int(core_r * 0.45 * ring)  # max 2.25*core_r < the 3*core_r half-size (no clipping)
            alpha = int(32 * ring * (0.5 + 0.5 * level))
            pygame.draw.circle(glow, (*COLOR_ACCENT, alpha), gc, r)
        surface.blit(
            glow, glow.get_rect(center=(int(cx), int(cy))), special_flags=pygame.BLEND_RGB_ADD
        )

    def _update_rings(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        core_r: float,
        scale: float,
        onset: float,
        dt: float,
        scheme: str,
        phase: float,
    ) -> None:
        if onset > 0.4 and len(self._rings) < 12:
            self._rings.append(core_r)
        grow = scale * 1.4 * dt * self.theme.speed_scale
        kept: list[float] = []
        for r in self._rings:
            r += grow
            if r < scale * 1.2:
                kept.append(r)
                fade = clamp(1.0 - r / (scale * 1.2))
                color = _shade(themed_color(scheme, phase, PALETTE, 0.0), 0.3 + 0.7 * fade)
                pygame.draw.circle(surface, color, (int(cx), int(cy)), int(r), 2)
        self._rings = kept


def _shade(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    f = clamp(factor)
    return (int(color[0] * f), int(color[1] * f), int(color[2] * f))
