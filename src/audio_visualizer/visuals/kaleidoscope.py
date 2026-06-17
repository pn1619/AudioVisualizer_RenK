"""Kaleidoscope: an audio-driven wedge mirrored into a symmetric mandala.

Spectrum spokes are drawn into a single wedge on an offscreen surface, then that
wedge is rotated (and mirror-flipped) around the center N times and composited
additively, so the spectrum blooms into a rotating, symmetric mandala. Hue sweeps
the spokes; bass brightens the core; the whole figure slowly rotates.
"""

from __future__ import annotations

import math

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import PALETTE
from audio_visualizer.visuals._helpers import clamp, resample_to, themed_color
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_SPOKES = 14  # spectrum rays drawn inside one wedge
_CORE_FRACTION = 0.04
_LEN_FRACTION = 0.46  # max spoke length as a fraction of the square side
_SPIN_RATE = 0.03  # base revolutions / second (scaled by speed)

_SEGMENTS = ModeOption(
    "segments",
    "Segments",
    (OptionChoice("6", 6), OptionChoice("8", 8), OptionChoice("12", 12)),
    default_index=0,
)


@register(key="kaleidoscope", display_name="Kaleidoscope", order=90)
class Kaleidoscope(BaseVisualizer):
    """Mirrors an audio-driven wedge into a rotating symmetric mandala."""

    OPTIONS = (_SEGMENTS,)

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._spin = 0.0

    def on_enter(self) -> None:
        self._spin = 0.0

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 16 or h < 16:
            return
        segments = int(self.option("segments"))
        sector = math.tau / segments
        side = min(w, h)
        rate = 0.0 if self.reduce_motion else _SPIN_RATE
        self._spin = (self._spin + dt * self.theme.speed_scale * rate * math.tau) % math.tau

        wedge = self._render_wedge(side, sector, frame)
        center = (w // 2, h // 2)
        for k in range(segments):
            angle = math.degrees(k * sector + self._spin)
            rot = pygame.transform.rotate(wedge, angle)
            surface.blit(rot, rot.get_rect(center=center), special_flags=pygame.BLEND_RGB_ADD)
            flip = pygame.transform.flip(rot, True, False)
            surface.blit(flip, flip.get_rect(center=center), special_flags=pygame.BLEND_RGB_ADD)

    def _render_wedge(
        self, side: int, sector: float, frame: AnalysisFrame | None
    ) -> pygame.Surface:
        wedge = pygame.Surface((side, side), pygame.SRCALPHA)
        c = side / 2.0
        core_r = side * _CORE_FRACTION
        max_len = side * _LEN_FRACTION
        scheme, phase = self.theme.color_scheme, self.theme.color_phase

        if frame is not None and frame.band_energies.size:
            vals = resample_to(frame.band_energies.astype(np.float32), _SPOKES)
        else:
            vals = np.full(_SPOKES, 0.03, dtype=np.float32)

        up = -math.pi / 2.0
        for i in range(_SPOKES):
            frac = i / max(1, _SPOKES - 1)
            ang = up - sector / 2.0 + frac * sector
            length = core_r + float(vals[i]) * max_len
            color = themed_color(scheme, frac, PALETTE, phase)
            x1, y1 = c + math.cos(ang) * core_r, c + math.sin(ang) * core_r
            x2, y2 = c + math.cos(ang) * length, c + math.sin(ang) * length
            pygame.draw.line(wedge, color, (x1, y1), (x2, y2), 3)
            pygame.draw.circle(wedge, color, (int(x2), int(y2)), 3)

        level = 0.0 if frame is None or frame.is_silent else clamp(frame.rms * 2.0)
        pygame.draw.circle(wedge, _core_color(level), (int(c), int(c)), max(2, int(core_r)))
        return wedge


def _core_color(level: float) -> tuple[int, int, int]:
    v = int(120 + 135 * level)
    return (v, v, v)
