"""Pulse Rings: concentric rings that breathe with the spectrum and ripple on beats.

Inner rings track low frequencies, outer rings the highs; each ring's radius,
thickness, and brightness swell with its band. On an onset a bright pulse is born
at the center and sweeps outward, momentarily lighting each ring it passes. Rings
can be solid outlines, thick fills, or rotating dashed arcs.
"""

from __future__ import annotations

import math

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.visuals._helpers import (
    COLOR_OPTION,
    THICKNESS_OPTION,
    clamp,
    mode_color,
    range_energies,
    scale_color,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_PULSE_SPEED = 0.9  # beat pulse outward speed (normalized radius per second)
_ONSET_TRIGGER = 0.3  # onset strength needed to birth a pulse
_DASH_SEGMENTS = 24  # arc segments per dashed ring

_RINGS = ModeOption(
    "rings",
    "Rings",
    (OptionChoice("6", 6), OptionChoice("12", 12), OptionChoice("24", 24)),
    default_index=1,
)
_DRAW = ModeOption(
    "rdraw",
    "Draw",
    (OptionChoice("Outline", 0), OptionChoice("Filled", 1), OptionChoice("Dashed", 2)),
    default_index=0,
)
_ROTATE = ModeOption(
    "rrotate",
    "Spin",
    (OptionChoice("Off", 0), OptionChoice("Spin", 1), OptionChoice("Counter", 2)),
    default_index=0,
)
_BEAT = ModeOption("beat", "Beat", (OptionChoice("On", 1), OptionChoice("Off", 0)), default_index=0)


@register(key="pulse_rings", display_name="Pulse Rings", order=120)
class PulseRings(BaseVisualizer):
    """Concentric breathing rings with outward beat pulses."""

    OPTIONS = (_RINGS, _DRAW, THICKNESS_OPTION, _ROTATE, COLOR_OPTION, _BEAT)

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._pulses: list[float] = []
        self._angle = 0.0
        self._prev_onset = 0.0

    def on_enter(self) -> None:
        self._pulses.clear()
        self._angle = 0.0
        self._prev_onset = 0.0

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        rings = int(self.option("rings"))
        energies = self._energies(frame, rings)
        self._advance(frame, dt)

        cx, cy = w / 2.0, h / 2.0
        max_r = min(w, h) * 0.46
        draw_mode = int(self.option("rdraw"))
        base_w = int(self.option("thickness"))
        color_opt = int(self.option("color"))
        scheme, phase = self.theme.color_scheme, self.theme.color_phase
        for i in range(rings):
            energy = float(energies[i])
            boost = self._pulse_boost((i + 1) / rings) if int(self.option("beat")) == 1 else 0.0
            r = ((i + 1) / rings) * max_r * (0.9 + 0.12 * energy)
            bright = clamp(0.25 + 0.75 * energy + boost)
            color = scale_color(mode_color(color_opt, scheme, i / rings, phase), bright)
            width = max(1, int(base_w * (1 + 2 * energy) + boost * 4))
            self._draw_ring(surface, draw_mode, cx, cy, r, width, color, i)

    def _energies(self, frame: AnalysisFrame | None, rings: int) -> np.ndarray:
        if frame is None or frame.band_energies.size == 0:
            return np.zeros(rings, dtype=np.float32)
        return np.clip(range_energies(frame.band_energies, rings), 0.0, 1.0)

    def _advance(self, frame: AnalysisFrame | None, dt: float) -> None:
        speed = dt * self.theme.speed_scale
        onset = 0.0 if frame is None else frame.onset
        if onset > _ONSET_TRIGGER and self._prev_onset <= _ONSET_TRIGGER:
            self._pulses.append(0.0)
        self._prev_onset = onset
        self._pulses = [p + _PULSE_SPEED * speed for p in self._pulses if p < 1.25]
        rate = 0.0 if self.reduce_motion else 1.0
        self._angle += speed * rate * 0.6

    def _pulse_boost(self, ring_norm: float) -> float:
        boost = 0.0
        for p in self._pulses:
            d = abs(ring_norm - p)
            if d < 0.12:
                boost += (1.0 - d / 0.12) * 0.8
        return min(boost, 1.0)

    def _draw_ring(
        self,
        surface: pygame.Surface,
        draw_mode: int,
        cx: float,
        cy: float,
        r: float,
        width: int,
        color: tuple[int, int, int],
        i: int,
    ) -> None:
        center = (int(cx), int(cy))
        ir = int(r)
        if ir < 1:
            return
        if draw_mode == 1:  # filled: thick ring
            pygame.draw.circle(surface, color, center, ir, min(ir, max(2, width * 2)))
        elif draw_mode == 2:  # dashed arcs, rotating (counter-rotate odd rings)
            direction = -1 if (int(self.option("rrotate")) == 2 and i % 2) else 1
            start = self._angle * direction
            rect = pygame.Rect(int(cx - r), int(cy - r), ir * 2, ir * 2)
            for s in range(_DASH_SEGMENTS):
                if s % 2:
                    continue
                a0 = start + s / _DASH_SEGMENTS * 2 * math.pi
                a1 = a0 + (1.0 / _DASH_SEGMENTS) * 2 * math.pi
                pygame.draw.arc(surface, color, rect, a0, a1, width)
        else:
            pygame.draw.circle(surface, color, center, ir, width)
