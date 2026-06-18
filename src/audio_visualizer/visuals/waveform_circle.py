"""Waveform Rings: the oscilloscope trace wrapped around one or many rings.

With ``Rings = 1`` it's a single pulsing oscilloscope ring; with more rings the
spectrum is split into equal ranges and each concentric ring's wobble is scaled by
its range's energy (inner = bass, outer = treble). An optional particle layer sheds
sparks off the rings (louder rings/onsets shed more). Replaces the four old circle
modes (single / single+pops / xN / xN+pops) with one set of options.
"""

from __future__ import annotations

import random

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import (
    CIRCLE_BASE_RADIUS,
    CIRCLE_INNER_FRACTION,
    CIRCLE_OUTER_FRACTION,
    CIRCLE_RING_AMP_BASE,
    CIRCLE_RING_AMP_FACTOR,
    CIRCLE_WAVE_AMPLITUDE,
    REDUCE_MOTION_BURST_DIVISOR,
)
from audio_visualizer.visuals._helpers import (
    PARTICLES_OPTION,
    RingPops,
    clamp,
    draw_ring,
    range_energies,
    ring_points,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_RING_POINTS = 220
_POP_MAX = 320
_POP_MAX_REDUCED = 100
_POP_BURST = 8
_SPAWN_RMS_GAIN = 1.2
_SPAWN_ENERGY_GAIN = 1.5
_SPAWN_ONSET_GAIN = 0.5

_PRESET = ModeOption(
    "preset",
    "Preset",
    (
        OptionChoice("Custom", 0),
        OptionChoice("Single", 1),
        OptionChoice("Bloom", 2),
        OptionChoice("Galaxy", 3),
    ),
    default_index=0,
)
_RINGS = ModeOption(
    "rings",
    "Rings",
    (OptionChoice("1", 1), OptionChoice("3", 3), OptionChoice("6", 6), OptionChoice("12", 12)),
    default_index=0,
)
_SIZE = ModeOption(
    "size",
    "Size",
    (OptionChoice("Small", 0.7), OptionChoice("Normal", 1.0), OptionChoice("Large", 1.4)),
    default_index=1,
)
_SPACING = ModeOption(
    "spacing",
    "Spacing",
    (OptionChoice("Tight", 0.6), OptionChoice("Normal", 1.0), OptionChoice("Wide", 1.6)),
    default_index=1,
)
_THICKNESS = ModeOption(
    "thickness",
    "Line",
    (OptionChoice("Thin", 1), OptionChoice("Normal", 2), OptionChoice("Thick", 4)),
    default_index=1,
)


@register(key="waveform_circle", display_name="Waveform Rings", order=16)
class WaveformCircle(BaseVisualizer):
    """One or many concentric oscilloscope rings, with optional shed particles."""

    OPTIONS = (_PRESET, _RINGS, _SIZE, _SPACING, _THICKNESS, PARTICLES_OPTION)
    PRESETS = {
        1: {"rings": 0, "particles": 0},  # Single
        2: {"rings": 1, "particles": 1},  # Bloom
        3: {"rings": 3, "spacing": 2, "particles": 2},  # Galaxy
    }

    def __init__(
        self, reduce_motion: bool = False, theme: Theme | None = None, seed: int = 555
    ) -> None:
        super().__init__(reduce_motion, theme)
        self._seed = seed
        self._rng = random.Random(seed)
        cap = _POP_MAX_REDUCED if reduce_motion else _POP_MAX
        self._pops = RingPops(cap)

    def on_enter(self) -> None:
        self._pops.clear()
        self._rng.seed(self._seed)

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 2 or h < 2:
            return
        cx, cy = w / 2.0, h / 2.0
        half = min(w, h) * 0.5
        rings = int(self.option("rings"))
        if rings <= 1:
            self._draw_single(surface, frame, cx, cy, half)
        else:
            self._draw_multiple(surface, frame, cx, cy, half, rings)
        self._pops.advance(dt, self.theme.speed_scale)
        self._pops.render(
            surface,
            self.theme.color_scheme,
            self.theme.color_phase,
            cx,
            cy,
            half,
            self.theme.size_scale,
        )

    def _draw_single(
        self,
        surface: pygame.Surface,
        frame: AnalysisFrame | None,
        cx: float,
        cy: float,
        half: float,
    ) -> None:
        size = self.option("size")
        base_r = half * CIRCLE_BASE_RADIUS * size
        amplitude = half * CIRCLE_WAVE_AMPLITUDE * size
        width = int(self.option("thickness"))
        samples = (
            np.zeros(_RING_POINTS, dtype=np.float32)
            if frame is None or frame.is_silent
            else frame.waveform_mono
        )
        points = ring_points(cx, cy, base_r, amplitude, samples, _RING_POINTS)
        draw_ring(surface, self.theme.color_scheme, self.theme.color_phase, points, width)
        if self.option("particles") > 0 and frame is not None and not frame.is_silent:
            count = int(
                self._burst()
                * self.option("particles")
                * clamp(frame.rms * _SPAWN_RMS_GAIN + frame.onset)
            )
            if count > 0:
                self._pops.spawn(self._rng, count, CIRCLE_BASE_RADIUS * size, frame.rms)

    def _draw_multiple(
        self,
        surface: pygame.Surface,
        frame: AnalysisFrame | None,
        cx: float,
        cy: float,
        half: float,
        rings: int,
    ) -> None:
        size = self.option("size")
        spacing = self.option("spacing")
        width = int(self.option("thickness"))
        inner = half * CIRCLE_INNER_FRACTION * size
        gap = ((half * CIRCLE_OUTER_FRACTION * size - inner) / max(1, rings)) * spacing
        amplitude = half * CIRCLE_WAVE_AMPLITUDE * CIRCLE_RING_AMP_FACTOR * size
        if frame is None or frame.is_silent:
            samples = np.zeros(_RING_POINTS, dtype=np.float32)
            energies = np.zeros(rings, dtype=np.float32)
        else:
            samples = frame.waveform_mono
            energies = range_energies(frame.band_energies, rings)
        scheme = self.theme.color_scheme
        phase = self.theme.color_phase
        for i in range(rings):
            base_r = inner + (i + 1) * gap
            amp_i = amplitude * (CIRCLE_RING_AMP_BASE + float(energies[i]))
            points = ring_points(cx, cy, base_r, amp_i, samples, _RING_POINTS)
            draw_ring(surface, scheme, phase, points, width, hue_offset=i / max(1, rings))
        if self.option("particles") > 0 and frame is not None and not frame.is_silent:
            self._spawn_multiple(rings, inner, gap, half, energies, frame)

    def _spawn_multiple(
        self,
        rings: int,
        inner: float,
        gap: float,
        half: float,
        energies: np.ndarray,
        frame: AnalysisFrame,
    ) -> None:
        rate = self.option("particles")
        for i in range(rings):
            energy = float(energies[i])
            drive = clamp(energy * _SPAWN_ENERGY_GAIN + frame.onset * _SPAWN_ONSET_GAIN)
            count = int(self._burst() * rate * drive)
            if count <= 0:
                continue
            self._pops.spawn(self._rng, count, (inner + (i + 1) * gap) / half, energy)

    def _burst(self) -> int:
        return _POP_BURST // REDUCE_MOTION_BURST_DIVISOR if self.reduce_motion else _POP_BURST
