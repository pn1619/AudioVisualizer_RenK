"""Audio Sun: spectrum bars radiating outward in a full circle.

One ray per spectrum slice points out from an animated core; ray length follows that
band's energy and hue sweeps around the ring. The core is built from two disks — a
segmented outer ring and a spoked inner disk — that can spin, counter-spin,
color-shift, or radiate beat rings. A faint oscilloscope ring threads the ray bases.
"""

from __future__ import annotations

import math

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import PALETTE
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
_CORE_FRACTION = 0.16  # inner radius (ray bases) as a fraction of min(w, h)/2
_LEN_FRACTION = 0.62  # max ray length as a fraction of min(w, h)/2
_ROTATE_RATE = 0.04  # base ray-ring revolutions per second (scaled by speed)
_DISK_RATE = 0.18  # base core-disk revolutions per second (scaled by speed)
_OUTER_SEGMENTS = 24  # colored arc segments in the outer disk
_INNER_SPOKES = 6  # spokes in the inner disk

_MIRROR = ModeOption(
    "mirror", "Mirror", (OptionChoice("On", 1), OptionChoice("Off", 0)), default_index=0
)
_THICKNESS = ModeOption(
    "thickness",
    "Rays",
    (OptionChoice("Thin", 2), OptionChoice("Normal", 3), OptionChoice("Bold", 5)),
    default_index=1,
)
# How the two core disks behave.
_DISKS = ModeOption(
    "disks",
    "Disks",
    (
        OptionChoice("Spin", 0),
        OptionChoice("Counter", 1),
        OptionChoice("Still", 2),
        OptionChoice("Radiate", 3),
    ),
    default_index=1,
)


@register(key="radial_spectrum", display_name="Audio Sun", order=22)
class RadialSpectrum(BaseVisualizer):
    """Radial spectrum rays around an animated two-disk core + an oscilloscope ring."""

    OPTIONS = (_MIRROR, _THICKNESS, _DISKS)

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._angle = 0.0
        self._outer = 0.0
        self._inner = 0.0
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

        step = (
            0.0 if (self.reduce_motion or mode == 2) else dt * self.theme.speed_scale * _DISK_RATE
        )
        self._outer = (self._outer + step * math.tau) % math.tau
        inner_dir = -1.0 if mode == 1 else 1.0  # "Counter" spins the inner disk the other way
        self._inner = (self._inner + inner_dir * step * 1.6 * math.tau) % math.tau

        if mode == 3:
            self._update_rings(surface, cx, cy, core_r, scale, onset, dt, scheme, phase)

        self._draw_outer_disk(surface, cx, cy, core_r, level, scheme, phase)
        self._draw_inner_disk(surface, cx, cy, core_r, level, scheme, phase)

    def _draw_outer_disk(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        core_r: float,
        level: float,
        scheme: str,
        phase: float,
    ) -> None:
        r_out = core_r * (0.95 + 0.1 * level)
        width = max(3, int(core_r * 0.35))
        seg = math.tau / _OUTER_SEGMENTS
        for k in range(_OUTER_SEGMENTS):
            if k % 2 == 0:  # dashed ring -> reads as a rotating disk
                continue
            a0 = self._outer + k * seg
            color = themed_color(scheme, k / _OUTER_SEGMENTS, PALETTE, phase)
            pygame.draw.arc(
                surface,
                color,
                pygame.Rect(cx - r_out, cy - r_out, r_out * 2, r_out * 2),
                a0,
                a0 + seg,
                width,
            )

    def _draw_inner_disk(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        core_r: float,
        level: float,
        scheme: str,
        phase: float,
    ) -> None:
        r_in = core_r * (0.55 + 0.15 * level)
        base = themed_color(scheme, phase, PALETTE, 0.0)
        pygame.draw.circle(surface, _shade(base, 0.25), (int(cx), int(cy)), int(r_in))
        for k in range(_INNER_SPOKES):
            ang = self._inner + k * (math.tau / _INNER_SPOKES)
            color = themed_color(scheme, k / _INNER_SPOKES + phase, PALETTE, 0.0)
            ox, oy = cx + math.cos(ang) * r_in, cy + math.sin(ang) * r_in
            pygame.draw.line(surface, color, (cx, cy), (ox, oy), max(2, int(core_r * 0.12)))

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
