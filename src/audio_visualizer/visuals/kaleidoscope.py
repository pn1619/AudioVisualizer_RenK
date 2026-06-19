"""Kaleidoscope: an audio-driven wedge mirrored into a symmetric mandala.

Spectrum spokes fill one wedge; each wedge is reflected about its own axis and
repeated around N segments, giving true dihedral (mirror + rotation) symmetry. We
draw the spokes **directly as lines** (computing the mirrored/rotated endpoints in
math) instead of rotating a full-canvas surface every frame — far cheaper and the
edges stay smooth (anti-aliased). The center ornament is configurable.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import PALETTE
from audio_visualizer.visuals._helpers import (
    SIZE_OPTION,
    SparkField,
    clamp,
    resample_to,
    themed_color,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_SPOKES = 16  # spectrum rays drawn across one wedge
_CORE_FRACTION = 0.03
_LEN_FRACTION = 0.48  # max spoke length as a fraction of min(w, h)/2
_SPIN_RATE = 0.03  # base revolutions / second (scaled by speed)
_SPARK_RATE = 60.0  # expected sparks/second at full overall energy
_SPARK_LEVEL_FLOOR = 0.15  # a spoke must be at least this loud to throw sparks

_SEGMENTS = ModeOption(
    "segments",
    "Segments",
    (OptionChoice("6", 6), OptionChoice("8", 8), OptionChoice("12", 12), OptionChoice("16", 16)),
    default_index=1,
)
# Center ornament: filled disc, hollow ring, soft additive glow, or nothing.
_CENTER = ModeOption(
    "center",
    "Center",
    (
        OptionChoice("Disc", 0),
        OptionChoice("Ring", 1),
        OptionChoice("Glow", 2),
        OptionChoice("Off", 3),
    ),
    default_index=2,
)
# Spin: rotate the whole figure as one ("Solid") or let the inner half of each spoke
# counter-rotate against the outer half ("Counter") for a layered, churning mandala.
_SPIN = ModeOption(
    "spin", "Spin", (OptionChoice("Solid", 0), OptionChoice("Counter", 1)), default_index=0
)
# Emit little sparks off the spoke tips that drift outward and fade.
_SPARK = ModeOption(
    "spark", "Spark", (OptionChoice("Off", 0), OptionChoice("On", 1)), default_index=0
)


@register(key="kaleidoscope", display_name="Kaleidoscope", order=90)
class Kaleidoscope(BaseVisualizer):
    """Mirrors an audio-driven wedge into a rotating symmetric mandala."""

    OPTIONS = (_SEGMENTS, _CENTER, _SPIN, _SPARK, SIZE_OPTION)

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._spin = 0.0  # outer-half rotation
        self._spin_inner = 0.0  # inner-half rotation (opposite when "Counter")
        self._sparks = SparkField(cap=0, lifetime=0.7, trail_len=0)
        self._rng = random.Random(23)

    def on_enter(self) -> None:
        self._spin = 0.0
        self._spin_inner = 0.0
        self._sparks.clear()

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 16 or h < 16:
            return
        cx, cy = w / 2.0, h / 2.0
        scale = min(w, h) / 2.0 * float(self.option("size"))
        core_r = scale * _CORE_FRACTION
        max_len = scale * _LEN_FRACTION
        segments = int(self.option("segments"))
        sector = math.tau / segments
        half = sector / 2.0
        scheme, phase = self.theme.color_scheme, self.theme.color_phase

        rate = 0.0 if self.reduce_motion else _SPIN_RATE
        adv = dt * self.theme.speed_scale * rate * math.tau
        counter = int(self.option("spin")) == 1
        self._spin = (self._spin + adv) % math.tau
        self._spin_inner = (self._spin_inner + (-adv if counter else adv)) % math.tau

        if frame is not None and frame.band_energies.size:
            vals = resample_to(frame.band_energies.astype(np.float32), _SPOKES)
        else:
            vals = np.full(_SPOKES, 0.04, dtype=np.float32)

        line_w = max(2, int(scale / 130))
        lengths = core_r + vals.astype(np.float32) * max_len
        # Draw the shortest spokes first so the long ones land on top and are never
        # clipped where they cross a neighbouring spoke near the centre.
        order = sorted(range(_SPOKES), key=lambda i: float(lengths[i]))
        if counter:
            # Counter churn: every inner half (near the core) first, then the long
            # outer halves on top — short→long so none get cut.
            for i in range(_SPOKES):
                mid = core_r + 0.5 * (float(lengths[i]) - core_r)
                self._draw_copies(
                    surface,
                    cx,
                    cy,
                    self._spin_inner,
                    segments,
                    sector,
                    half,
                    i,
                    core_r,
                    mid,
                    scheme,
                    phase,
                    line_w,
                    tip=False,
                )
            for i in order:
                mid = core_r + 0.5 * (float(lengths[i]) - core_r)
                self._draw_copies(
                    surface,
                    cx,
                    cy,
                    self._spin,
                    segments,
                    sector,
                    half,
                    i,
                    mid,
                    float(lengths[i]),
                    scheme,
                    phase,
                    line_w,
                    tip=True,
                )
        else:
            for i in order:
                self._draw_copies(
                    surface,
                    cx,
                    cy,
                    self._spin,
                    segments,
                    sector,
                    half,
                    i,
                    core_r,
                    float(lengths[i]),
                    scheme,
                    phase,
                    line_w,
                    tip=True,
                )

        if int(self.option("spark")) == 1 and not self.reduce_motion:
            self._emit_sparks(cx, cy, segments, sector, half, vals, lengths, w, h, dt)
            self._render_sparks(surface, w, h, dt)
        self._draw_center(surface, cx, cy, core_r, frame)

    def _draw_copies(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        spin: float,
        segments: int,
        sector: float,
        half: float,
        i: int,
        r0: float,
        r1: float,
        scheme: str,
        phase: float,
        line_w: int,
        tip: bool,
    ) -> None:
        """Draw spoke ``i`` (radial span ``r0``..``r1``) mirrored into every segment."""
        frac = i / max(1, _SPOKES - 1)
        color = themed_color(scheme, frac, PALETTE, phase)
        offset = frac * half
        for k in range(segments):
            base = k * sector
            for sign in (1.0, -1.0):  # mirror about each segment axis
                ang = spin + base + sign * offset
                self._spoke(surface, cx, cy, ang, r0, r1, color, line_w, tip=tip)

    def _emit_sparks(
        self,
        cx: float,
        cy: float,
        segments: int,
        sector: float,
        half: float,
        vals: np.ndarray,
        lengths: np.ndarray,
        w: int,
        h: int,
        dt: float,
    ) -> None:
        """Throw sparks off the loud spokes' tips, outward along each spoke."""
        self._sparks.cap = max(80, segments * _SPOKES)
        liveliness = float(np.clip(vals.mean() * 4.0, 0.0, 1.5))
        expected = liveliness * _SPARK_RATE * dt
        count = int(expected) + (1 if self._rng.random() < expected - int(expected) else 0)
        for _ in range(count):
            i = self._rng.randrange(_SPOKES)
            if float(vals[i]) < _SPARK_LEVEL_FLOOR:
                continue
            frac = i / max(1, _SPOKES - 1)
            ang = self._spin + self._rng.randrange(segments) * sector
            ang += self._rng.choice((1.0, -1.0)) * frac * half
            r = float(lengths[i])
            speed = 0.12 + 0.4 * float(vals[i])
            spread = self._rng.uniform(-0.1, 0.1)
            self._sparks.spawn(
                (cx + math.cos(ang) * r) / w,
                (cy + math.sin(ang) * r) / h,
                (math.cos(ang) + spread) * speed,
                (math.sin(ang) + spread) * speed,
                frac,
                size=self._rng.uniform(0.6, 1.2),
            )

    def _render_sparks(self, surface: pygame.Surface, w: int, h: int, dt: float) -> None:
        self._sparks.advance(dt, self.theme.speed_scale, gravity=0.0)
        size_scale = max(1.0, min(w, h) / 300.0)
        self._sparks.render(
            surface, self.theme.color_scheme, self.theme.color_phase, w, h, size_scale, trails=False
        )

    def _spoke(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        ang: float,
        r0: float,
        r1: float,
        color: tuple[int, int, int],
        width: int,
        tip: bool = True,
    ) -> None:
        ca, sa = math.cos(ang), math.sin(ang)
        p0 = (cx + ca * r0, cy + sa * r0)
        p1 = (cx + ca * r1, cy + sa * r1)
        pygame.draw.line(surface, color, p0, p1, width)
        pygame.draw.aaline(surface, color, p0, p1)  # smooth the edges
        if tip:
            pygame.draw.circle(surface, color, (int(p1[0]), int(p1[1])), max(2, width))

    def _draw_center(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        core_r: float,
        frame: AnalysisFrame | None,
    ) -> None:
        mode = int(self.option("center"))
        if mode == 3:
            return
        level = 0.0 if frame is None or frame.is_silent else clamp(frame.rms * 2.0)
        radius = max(3, int(core_r + min(surface.get_size()) * 0.05 * (0.4 + 0.6 * level)))
        color = themed_color(self.theme.color_scheme, self.theme.color_phase, PALETTE, 0.0)
        if mode == 0:  # filled, color-shifting disc
            pygame.draw.circle(surface, color, (int(cx), int(cy)), radius)
        elif mode == 1:  # hollow ring
            pygame.draw.circle(surface, color, (int(cx), int(cy)), radius, max(2, radius // 6))
        else:  # soft additive glow (transparent layered halo)
            self._glow(surface, cx, cy, radius, color, level)

    @staticmethod
    def _glow(
        surface: pygame.Surface,
        cx: float,
        cy: float,
        radius: int,
        color: tuple[int, int, int],
        level: float,
    ) -> None:
        # Surface must be big enough that the largest halo circle isn't clipped to a
        # square: half-size is 3*radius, the biggest circle is 2*radius.
        size = radius * 6
        glow = pygame.Surface((size, size), pygame.SRCALPHA)
        gc = (size // 2, size // 2)
        for ring in range(5, 0, -1):
            r = int(radius * 0.4 * ring)
            alpha = int(28 * ring * (0.5 + 0.5 * level))
            pygame.draw.circle(glow, (*color, alpha), gc, r)
        surface.blit(
            glow, glow.get_rect(center=(int(cx), int(cy))), special_flags=pygame.BLEND_RGB_ADD
        )
