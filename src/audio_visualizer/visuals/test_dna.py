"""DNA Helix: a rotating double-helix whose rungs ride the spectrum.

Two (or 1/3) beaded strands wind around an axis; horizontal rungs connect them, each
rung colored/brightened by a frequency band (low at one end, high at the other). The
twist rate rides ``rms`` and onsets send bright pulses travelling along the strands.
A depth cue (front beads larger/brighter than back) gives the helix its 3-D read.

Shipped under a ``Test_`` name during evaluation; remove the prefix once approved.
"""

from __future__ import annotations

import math

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import ONSET_THRESHOLD
from audio_visualizer.visuals._helpers import (
    GLOW_OPTION,
    SHARED_PALETTES,
    clamp,
    palette_color,
    rainbow_color,
    resample_to,
    scale_color,
    themed_color,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_SAMPLES = 132  # points sampled along each strand
_TURNS = 3.0  # helical turns across the axis span
_AMP_FRACTION = 0.13  # strand sway amplitude as a fraction of min(w, h)
_RUNGS = 26  # connecting rungs (resampled from band_energies)
_COOL = SHARED_PALETTES[4]  # neon blue/violet stops for the strands in Spectrum mode

_PRESET = ModeOption(
    "preset",
    "Preset",
    (
        OptionChoice("Custom", 0),
        OptionChoice("Classic", 1),
        OptionChoice("Triple", 2),
        OptionChoice("Bio-Neon", 3),
    ),
    default_index=0,
)
_STRANDS = ModeOption(
    "strands",
    "Strands",
    (OptionChoice("1", 1), OptionChoice("2", 2), OptionChoice("3", 3)),
    default_index=1,
)
_TWIST = ModeOption(
    "twist",
    "Twist",
    (OptionChoice("Slow", 0.5), OptionChoice("Med", 1.0), OptionChoice("Fast", 2.0)),
    default_index=1,
)
_RUNG = ModeOption(
    "rung",
    "Rungs",
    (OptionChoice("Bars", 0), OptionChoice("Beads", 1), OptionChoice("Lightning", 2)),
    default_index=0,
)
_ORIENT = ModeOption(
    "orient",
    "Orientation",
    (OptionChoice("Vertical", 0), OptionChoice("Horizontal", 1), OptionChoice("Diagonal", 2)),
    default_index=0,
)
_COLOR = ModeOption(
    "dcolor",
    "Color",
    (OptionChoice("Spectrum", 0), OptionChoice("Duotone", 1), OptionChoice("Theme", 2)),
    default_index=0,
)


@register(key="test_dna", display_name="Test_DNA Helix", order=84)
class TestDna(BaseVisualizer):
    """A band-reactive double helix with beaded strands, spectrum rungs, and pulses."""

    OPTIONS = (_PRESET, _STRANDS, _TWIST, _RUNG, _ORIENT, _COLOR, GLOW_OPTION)
    PRESETS = {
        1: {"strands": 1, "rung": 0, "dcolor": 0, "glow": 1},  # Classic double helix
        2: {"strands": 2, "rung": 1, "dcolor": 0, "glow": 1},  # Triple helix, beaded
        3: {"strands": 1, "rung": 2, "dcolor": 1, "glow": 1},  # Bio-Neon lightning rungs
    }

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._phase = 0.0
        self._pulses: list[float] = []  # positions (0..1) of pulses travelling the axis

    def on_enter(self) -> None:
        self._phase = 0.0
        self._pulses.clear()

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        level = 0.0 if frame is None or frame.is_silent else clamp(frame.rms * 2.0)
        onset = 0.0 if frame is None else frame.onset
        twist = float(self.option("twist")) * (0.4 if self.reduce_motion else 1.0)
        self._phase += dt * self.theme.speed_scale * twist * (0.6 + level) * math.tau * 0.25
        self._advance_pulses(dt, onset)

        bands = self._rung_energies(frame)
        glow = pygame.Surface((w, h), pygame.SRCALPHA) if int(self.option("glow")) else None

        strands = int(self.option("strands"))
        self._draw_rungs(surface, glow, w, h, strands, bands, level)
        for s in range(strands):
            self._draw_strand(surface, glow, w, h, s, strands, level)
        if glow is not None:
            surface.blit(glow, (0, 0), special_flags=pygame.BLEND_ADD)

    # -- geometry -------------------------------------------------------------
    def _project(self, u: float, perp: float, w: int, h: int) -> tuple[float, float]:
        """Map axis position ``u`` (0..1) + perpendicular offset ``perp`` to pixels."""
        orient = int(self.option("orient"))
        amp = min(w, h) * _AMP_FRACTION
        if orient == 1:  # horizontal
            return 0.08 * w + u * 0.84 * w, h * 0.5 + perp * amp
        if orient == 2:  # diagonal (along the main diagonal, perp rotated 90°)
            ax, ay = 0.1 * w + u * 0.8 * w, 0.1 * h + u * 0.8 * h
            length = math.hypot(0.8 * w, 0.8 * h)
            nx, ny = -0.8 * h / length, 0.8 * w / length
            return ax + perp * amp * nx, ay + perp * amp * ny
        return w * 0.5 + perp * amp, 0.08 * h + u * 0.84 * h  # vertical

    def _strand_point(
        self, u: float, s: int, strands: int, w: int, h: int
    ) -> tuple[float, float, float]:
        """Return ``(x, y, depth01)`` for strand ``s`` at axis position ``u``."""
        ang = self._phase + u * _TURNS * math.tau + s * (math.tau / max(1, strands))
        x, y = self._project(u, math.cos(ang), w, h)
        return x, y, (math.sin(ang) + 1.0) * 0.5  # depth 0 (back) .. 1 (front)

    def _advance_pulses(self, dt: float, onset: float) -> None:
        if onset >= ONSET_THRESHOLD and not self.reduce_motion and len(self._pulses) < 8:
            self._pulses.append(0.0)
        speed = dt * self.theme.speed_scale * 0.9
        self._pulses = [p + speed for p in self._pulses if p + speed <= 1.0]

    def _pulse_boost(self, u: float) -> float:
        """Extra brightness near a travelling pulse (0..~1)."""
        return max((math.exp(-((u - p) ** 2) / 0.0015) for p in self._pulses), default=0.0)

    # -- colors ---------------------------------------------------------------
    def _strand_color(self, s: int, u: float, depth: float) -> tuple[int, int, int]:
        mode = int(self.option("dcolor"))
        scheme, phase = self.theme.color_scheme, self.theme.color_phase
        if mode == 2:
            return themed_color(scheme, u, _COOL, phase)
        if mode == 1:
            return rainbow_color(0.58 + s * 0.12)
        return palette_color(_COOL, 0.2 + 0.7 * depth)  # spectrum: cool beaded strands

    def _rung_color(self, t: float) -> tuple[int, int, int]:
        mode = int(self.option("dcolor"))
        if mode == 2:
            return themed_color(self.theme.color_scheme, t, _COOL, self.theme.color_phase)
        if mode == 1:
            return rainbow_color(0.55 + 0.25 * t)
        return rainbow_color(t)  # spectrum: low->high across the helix

    # -- drawing --------------------------------------------------------------
    def _draw_strand(
        self,
        surface: pygame.Surface,
        glow: pygame.Surface | None,
        w: int,
        h: int,
        s: int,
        strands: int,
        level: float,
    ) -> None:
        base_r = max(2.0, min(w, h) * 0.012) * self.theme.size_scale
        for i in range(_SAMPLES):
            u = i / (_SAMPLES - 1)
            x, y, depth = self._strand_point(u, s, strands, w, h)
            boost = self._pulse_boost(u)
            radius = max(1, int(base_r * (0.45 + 0.9 * depth) * (0.8 + 0.4 * level) + boost * 3))
            bright = clamp(0.35 + 0.65 * depth + boost)
            color = scale_color(self._strand_color(s, u, depth), bright)
            pygame.draw.circle(surface, color, (int(x), int(y)), radius)
            if glow is not None:
                pygame.draw.circle(glow, (*color, 70), (int(x), int(y)), radius * 2)

    def _draw_rungs(
        self,
        surface: pygame.Surface,
        glow: pygame.Surface | None,
        w: int,
        h: int,
        strands: int,
        bands: np.ndarray,
        level: float,
    ) -> None:
        if strands < 2:
            return
        for j in range(_RUNGS):
            u = j / (_RUNGS - 1)
            energy = float(bands[j])
            bright = clamp(0.4 + 0.6 * energy + self._pulse_boost(u))
            color = scale_color(self._rung_color(u), bright)
            width = max(1, int(1 + energy * 5 * self.theme.size_scale))
            pts = [self._strand_point(u, s, strands, w, h)[:2] for s in range(strands)]
            self._draw_rung(surface, glow, color, pts, width)

    def _draw_rung(
        self,
        surface: pygame.Surface,
        glow: pygame.Surface | None,
        color: tuple[int, int, int],
        pts: list[tuple[float, float]],
        width: int,
    ) -> None:
        style = int(self.option("rung"))
        ipts = [(int(x), int(y)) for x, y in pts]
        if style == 2:  # lightning: jagged midpoints between strand ends
            ipts = _jagged(ipts)
        pygame.draw.lines(surface, color, False, ipts, width)
        if style == 1:  # beads: dots at the strand ends
            for x, y in ipts:
                pygame.draw.circle(surface, color, (x, y), width + 1)
        if glow is not None and len(ipts) >= 2:
            pygame.draw.lines(glow, (*color, 60), False, ipts, width * 3)

    def _rung_energies(self, frame: AnalysisFrame | None) -> np.ndarray:
        if frame is None or frame.band_energies.size == 0:
            return np.full(_RUNGS, 0.12, dtype=np.float32)
        return resample_to(frame.band_energies.astype(np.float32), _RUNGS)


def _jagged(pts: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Insert a small zig midpoint between each pair so rungs read as lightning."""
    out: list[tuple[int, int]] = []
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        mx, my = (x0 + x1) // 2, (y0 + y1) // 2
        out.extend([(x0, y0), (mx, my + (8 if i % 2 == 0 else -8))])
    out.append(pts[-1])
    return out
