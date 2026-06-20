"""Liquid Orb: a smooth, filled blob in the center that morphs with the spectrum.

A closed, symmetric shape whose per-angle radius is driven by the frequency
spectrum (mirrored so the blob stays seamless), low-passed into a liquid wobble,
slowly rotating, pulsing with the beat, and filled with a glowing radial gradient.

Different from **Waveform Rings** (a thin oscilloscope line) and **Audio Sun**
(discrete radial bars): this is a *solid* organic body with a soft halo. Honors
the shared Theme (color scheme/phase, size, speed) and reduce-motion.
"""

from __future__ import annotations

import math

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.visuals._helpers import (
    PALETTE,
    clamp,
    resample_to,
    scale_color,
    smooth_wave,
    themed_color,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_POINTS = 240  # vertices around the blob (even, so the mirror seam is clean)
_BASE_FRAC = 0.26  # resting radius as a fraction of the canvas half-size
_AMP_FRAC = 0.5  # how far the spectrum can push the rim outward
_PULSE_AMP = 0.18  # beat pulse swells the whole orb by up to this fraction
_RMS_AMP = 0.12  # loudness adds a little steady swell on top
_PULSE_DECAY = 3.0  # beat-pulse envelope falloff per second
_SPIN_RAD_PER_SEC = 0.22  # slow idle rotation (× speed scale)
_IDLE_BREATHE = 0.06  # gentle breathing radius when silent
_FILL_LAYERS = 12  # nested polygons that fake a radial gradient

_SIZE = ModeOption(
    "size",
    "Size",
    (OptionChoice("Small", 0.75), OptionChoice("Normal", 1.0), OptionChoice("Large", 1.3)),
    default_index=1,
)
_REACT = ModeOption(
    "react",
    "React",
    (OptionChoice("Calm", 0.6), OptionChoice("Normal", 1.0), OptionChoice("Wild", 1.7)),
    default_index=1,
)
# Circular low-pass radius (fraction of the rim sample count): higher = rounder blob.
_SMOOTH = ModeOption(
    "smooth",
    "Surface",
    (OptionChoice("Spiky", 0.015), OptionChoice("Liquid", 0.04), OptionChoice("Blobby", 0.09)),
    default_index=1,
)
_FILL = ModeOption(
    "fill",
    "Fill",
    (OptionChoice("Gradient", 0), OptionChoice("Solid", 1), OptionChoice("Outline", 2)),
    default_index=0,
)
_GLOW = ModeOption(
    "glow",
    "Glow",
    (OptionChoice("Off", 0), OptionChoice("Soft", 1), OptionChoice("Bright", 2)),
    default_index=1,
)


@register(key="orb", display_name="Liquid Orb", order=82)
class Orb(BaseVisualizer):
    """A filled, morphing blob driven by the spectrum, with a soft glow halo."""

    OPTIONS = (_SIZE, _REACT, _SMOOTH, _FILL, _GLOW)

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._angle = 0.0
        self._pulse = 0.0
        self._breathe = 0.0

    def on_enter(self) -> None:
        self._pulse = 0.0

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 4 or h < 4:
            return
        cx, cy = w / 2.0, h / 2.0
        half = min(w, h) * 0.5
        self._advance(frame, dt)

        radii = self._radius_profile(frame, half)
        ang = np.linspace(0.0, 2.0 * np.pi, _POINTS, endpoint=False) + self._angle
        xs = cx + np.cos(ang) * radii
        ys = cy + np.sin(ang) * radii
        points = [(float(x), float(y)) for x, y in zip(xs, ys, strict=False)]

        scheme = self.theme.color_scheme
        phase = self.theme.color_phase
        glow = int(self.option("glow"))
        if glow > 0:
            self._draw_glow(surface, points, cx, cy, scheme, phase, glow)
        self._draw_body(surface, points, cx, cy, scheme, phase)

    # -- state ---------------------------------------------------------------
    def _advance(self, frame: AnalysisFrame | None, dt: float) -> None:
        if not self.reduce_motion:
            self._angle = (self._angle + _SPIN_RAD_PER_SEC * dt * self.theme.speed_scale) % (
                2.0 * math.pi
            )
        self._breathe = (self._breathe + dt * 1.3 * self.theme.speed_scale) % (2.0 * math.pi)
        self._pulse = max(0.0, self._pulse - _PULSE_DECAY * dt)
        if frame is not None and not frame.is_silent:
            kick = 0.0 if self.reduce_motion else clamp(frame.onset)
            self._pulse = max(self._pulse, kick)

    def _radius_profile(self, frame: AnalysisFrame | None, half: float) -> np.ndarray:
        """Per-vertex radius: a mirrored, smoothed spectrum rim + beat/breath swell."""
        size = float(self.option("size"))
        react = float(self.option("react"))
        if frame is None or frame.is_silent:
            profile = np.zeros(_POINTS, dtype=np.float32)
            breathe = _IDLE_BREATHE * (0.5 + 0.5 * math.sin(self._breathe))
            rms = 0.0
        else:
            half_n = _POINTS // 2
            slice_ = resample_to(frame.band_energies, half_n)
            profile = np.concatenate([slice_, slice_[::-1]]).astype(np.float32)  # seamless mirror
            breathe = 0.0
            rms = clamp(frame.rms)
        profile = smooth_wave(profile, float(self.option("smooth")), circular=True)
        swell = 1.0 + _PULSE_AMP * self._pulse + _RMS_AMP * rms + breathe
        base = half * _BASE_FRAC * size * swell
        amp = half * _AMP_FRAC * size * react
        return base + profile * amp

    # -- drawing -------------------------------------------------------------
    @staticmethod
    def _scaled(
        points: list[tuple[float, float]], cx: float, cy: float, factor: float
    ) -> list[tuple[float, float]]:
        return [(cx + (x - cx) * factor, cy + (y - cy) * factor) for x, y in points]

    def _draw_glow(
        self,
        surface: pygame.Surface,
        points: list[tuple[float, float]],
        cx: float,
        cy: float,
        scheme: str,
        phase: float,
        glow: int,
    ) -> None:
        """Additive translucent halos just outside the rim (cheap soft bloom)."""
        layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        base = themed_color(scheme, 0.85, PALETTE, phase)
        rings = 3 if glow >= 2 else 2
        for k in range(rings):
            factor = 1.0 + 0.05 * (k + 1)
            alpha = int((70 if glow >= 2 else 45) * (1.0 - k / (rings + 0.5)))
            pygame.draw.polygon(layer, (*base, alpha), self._scaled(points, cx, cy, factor))
        surface.blit(layer, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_body(
        self,
        surface: pygame.Surface,
        points: list[tuple[float, float]],
        cx: float,
        cy: float,
        scheme: str,
        phase: float,
    ) -> None:
        fill = int(self.option("fill"))
        if fill == 2:  # outline only
            color = themed_color(scheme, 0.6, PALETTE, phase)
            pygame.draw.lines(surface, color, True, points, 2)
            return
        if fill == 1:  # solid
            pygame.draw.polygon(surface, themed_color(scheme, 0.5, PALETTE, phase), points)
        else:  # gradient: nested polygons from a dim rim to a bright core
            for k in range(_FILL_LAYERS):
                t = k / (_FILL_LAYERS - 1)  # 0 = outer rim .. 1 = center
                factor = 1.0 - t * 0.92
                bright = 0.55 + 0.45 * t  # core glows brighter
                color = scale_color(themed_color(scheme, 1.0 - t, PALETTE, phase), bright)
                pygame.draw.polygon(surface, color, self._scaled(points, cx, cy, factor))
        # A crisp rim keeps the blob readable over busy backgrounds.
        pygame.draw.lines(surface, themed_color(scheme, 0.9, PALETTE, phase), True, points, 2)
