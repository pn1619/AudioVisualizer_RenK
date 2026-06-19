"""VU Meters: studio-style level meters driven by frequency-grouped energy.

Each group is one meter rendered as an LED ladder, a smooth bar, or a sweeping
needle gauge. Levels rise instantly and fall with a tunable decay; an optional
peak-hold pip floats above the level and sinks slowly. Colors can be the accent,
a per-group sweep, or classic green/amber/red broadcast zones.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import COLOR_ACCENT, PALETTE
from audio_visualizer.visuals._helpers import (
    GLOW_OPTION,
    SparkField,
    palette_color,
    range_energies,
    scale_color,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_ZONE_GREEN = (60, 220, 90)
_ZONE_AMBER = (240, 200, 50)
_ZONE_RED = (240, 70, 60)
_PEAK_DECAY = 0.35  # peak-hold pip fall speed (level fraction per second)
_SPARK_LEVEL_FLOOR = 0.05  # below this level a meter emits no sparks
_SPARK_RATE = 50.0  # expected sparks/second from a meter at full level
_SPARK_LOW_GAIN = 0.7  # extra emission for the lowest meters (bass shoots more)

_STYLE = ModeOption(
    "style",
    "Style",
    (OptionChoice("Ladder", 0), OptionChoice("Bar", 1), OptionChoice("Needle", 2)),
    default_index=0,
)
_GROUPS = ModeOption(
    "groups",
    "Meters",
    (OptionChoice("4", 4), OptionChoice("8", 8), OptionChoice("12", 12), OptionChoice("24", 24)),
    default_index=1,
)
_SEGMENTS = ModeOption(
    "segments",
    "Segments",
    (OptionChoice("10", 10), OptionChoice("16", 16), OptionChoice("24", 24)),
    default_index=1,
)
_PEAK = ModeOption("peak", "Peak", (OptionChoice("On", 1), OptionChoice("Off", 0)), default_index=0)
_DECAY = ModeOption(
    "decay",
    "Decay",
    (OptionChoice("Slow", 0.6), OptionChoice("Med", 1.4), OptionChoice("Fast", 3.0)),
    default_index=1,
)
_ORIENT = ModeOption(
    "orient",
    "Layout",
    (OptionChoice("Vertical", 0), OptionChoice("Horizontal", 1)),
    default_index=0,
)
_COLOR = ModeOption(
    "mcolor",
    "Color",
    (OptionChoice("Zones", 0), OptionChoice("Accent", 1), OptionChoice("Per-band", 2)),
    default_index=0,
)
# Emit little particles from each meter: needles shoot sparks off the tip, ladders/
# bars spray them up off the level. Hues sweep per band for a rainbow-across-boxes
# look (full rainbow under a rainbow color scheme). The value doubles as a particle
# size multiplier so the user can pick fine vs bold sparks (or turn them off).
_SPARK = ModeOption(
    "spark",
    "Spark",
    (
        OptionChoice("Off", 0.0),
        OptionChoice("Fine", 0.55),
        OptionChoice("Bold", 1.0),
        OptionChoice("Big", 1.7),
        OptionChoice("Huge", 2.5),
        OptionChoice("Max", 3.3),
    ),
    default_index=0,
)
# Look of the swinging needle (only used when Style = Needle).
_NEEDLE = ModeOption(
    "needle",
    "Needle",
    (
        OptionChoice("Classic", 0),
        OptionChoice("Gauge", 1),
        OptionChoice("VU", 2),
        OptionChoice("Comet", 3),
        OptionChoice("Dual", 4),
    ),
    default_index=0,
)


@register(key="meters", display_name="VU Meters", order=110)
class Meters(BaseVisualizer):
    """Frequency-grouped level meters (ladder / bar / needle) with peak hold."""

    OPTIONS = (
        _STYLE,
        _GROUPS,
        _SEGMENTS,
        _PEAK,
        _DECAY,
        _ORIENT,
        _COLOR,
        _NEEDLE,
        _SPARK,
        GLOW_OPTION,
    )

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._levels = np.zeros(0, dtype=np.float32)
        self._peaks = np.zeros(0, dtype=np.float32)
        self._glow = False
        self._sparks = SparkField(cap=0, lifetime=0.6, trail_len=0)
        self._rng = random.Random(11)
        self._hue_drift = 0.0
        self._spark_mult = 0.0

    def on_enter(self) -> None:
        self._levels = np.zeros(0, dtype=np.float32)
        self._peaks = np.zeros(0, dtype=np.float32)
        self._sparks.clear()
        self._hue_drift = 0.0

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        groups = int(self.option("groups"))
        self._update_levels(frame, groups, dt)
        self._glow = int(self.option("glow")) == 1

        margin = int(min(w, h) * 0.06)
        horiz = int(self.option("orient")) == 1
        style = int(self.option("style"))
        self._spark_mult = float(self.option("spark"))
        spark_on = self._spark_mult > 0.0 and not self.reduce_motion
        if spark_on:
            self._sparks.cap = max(48, groups * 12)
            self._hue_drift = (self._hue_drift + dt * 0.15) % 1.0
        for i in range(groups):
            cell = self._cell_rect(i, groups, w, h, margin, horiz)
            level = float(self._levels[i])
            peak = float(self._peaks[i])
            if style == 0:
                self._draw_ladder(surface, cell, level, peak, i, groups, horiz)
            elif style == 1:
                self._draw_bar(surface, cell, level, peak, i, groups, horiz)
            else:
                self._draw_needle(surface, cell, level, i, groups)
            if spark_on:
                self._emit(style, cell, level, i, groups, horiz, w, h, dt)
        if spark_on:
            self._render_sparks(surface, style, w, h, dt)

    def _update_levels(self, frame: AnalysisFrame | None, groups: int, dt: float) -> None:
        if self._levels.size != groups:
            self._levels = np.zeros(groups, dtype=np.float32)
            self._peaks = np.zeros(groups, dtype=np.float32)
        if frame is None or frame.band_energies.size == 0:
            target = np.zeros(groups, dtype=np.float32)
        else:
            target = np.clip(range_energies(frame.band_energies, groups), 0.0, 1.0)
        # Instant attack, tunable release so meters "fall back" smoothly.
        release = self.option("decay") * max(dt, 1e-3)
        self._levels = np.maximum(target, self._levels - release)
        self._peaks = np.maximum(self._levels, self._peaks - _PEAK_DECAY * max(dt, 1e-3))

    @staticmethod
    def _cell_rect(i: int, groups: int, w: int, h: int, margin: int, horiz: bool) -> pygame.Rect:
        if horiz:
            span = (h - 2 * margin) / groups
            gap = span * 0.18
            return pygame.Rect(
                margin, int(margin + i * span + gap / 2), w - 2 * margin, int(span - gap)
            )
        span = (w - 2 * margin) / groups
        gap = span * 0.18
        return pygame.Rect(
            int(margin + i * span + gap / 2), margin, int(span - gap), h - 2 * margin
        )

    def _color_for(self, level: float, i: int, groups: int) -> tuple[int, int, int]:
        mode = int(self.option("mcolor"))
        if mode == 1:
            return COLOR_ACCENT
        if mode == 2:
            return palette_color(PALETTE, i / max(1, groups - 1))
        if level > 0.85:
            return _ZONE_RED
        if level > 0.6:
            return _ZONE_AMBER
        return _ZONE_GREEN

    def _draw_ladder(
        self,
        surface: pygame.Surface,
        cell: pygame.Rect,
        level: float,
        peak: float,
        i: int,
        groups: int,
        horiz: bool,
    ) -> None:
        segments = int(self.option("segments"))
        lit = int(round(level * segments))
        peak_seg = int(round(peak * segments)) if int(self.option("peak")) == 1 else -1
        for s in range(segments):
            frac = (s + 0.5) / segments
            on = s < lit
            seg_color = self._color_for(frac, i, groups)
            color = seg_color if on else tuple(int(c * 0.18) for c in seg_color)
            rect = self._segment_rect(cell, s, segments, horiz)
            if on and self._glow:
                self._glow_rect(surface, rect, seg_color)
            pygame.draw.rect(surface, color, rect)
            if s == peak_seg:
                pygame.draw.rect(surface, (255, 255, 255), rect, 1)

    @staticmethod
    def _segment_rect(cell: pygame.Rect, s: int, segments: int, horiz: bool) -> pygame.Rect:
        pad = 1
        if horiz:
            sw = cell.width / segments
            return pygame.Rect(
                int(cell.left + s * sw + pad), cell.top, int(sw - 2 * pad), cell.height
            )
        sh = cell.height / segments
        y = cell.bottom - (s + 1) * sh
        return pygame.Rect(cell.left, int(y + pad), cell.width, int(sh - 2 * pad))

    def _draw_bar(
        self,
        surface: pygame.Surface,
        cell: pygame.Rect,
        level: float,
        peak: float,
        i: int,
        groups: int,
        horiz: bool,
    ) -> None:
        color = self._color_for(level, i, groups)
        pygame.draw.rect(surface, tuple(int(c * 0.16) for c in color), cell)
        if horiz:
            fill = pygame.Rect(cell.left, cell.top, int(cell.width * level), cell.height)
        else:
            fh = int(cell.height * level)
            fill = pygame.Rect(cell.left, cell.bottom - fh, cell.width, fh)
        if self._glow and (fill.width > 0 and fill.height > 0):
            self._glow_rect(surface, fill, color)
        pygame.draw.rect(surface, color, fill)
        if int(self.option("peak")) == 1:
            if horiz:
                x = cell.left + int(cell.width * peak)
                pygame.draw.line(surface, (255, 255, 255), (x, cell.top), (x, cell.bottom), 2)
            else:
                y = cell.bottom - int(cell.height * peak)
                pygame.draw.line(surface, (255, 255, 255), (cell.left, y), (cell.right, y), 2)

    def _draw_needle(
        self, surface: pygame.Surface, cell: pygame.Rect, level: float, i: int, groups: int
    ) -> None:
        pivot = (cell.centerx, cell.bottom)
        radius = min(cell.width, cell.height) * 0.9
        angle = math.radians(150 - level * 120)  # 150deg (left/idle) -> 30deg (right/hot)
        color = self._color_for(level, i, groups)
        variant = int(self.option("needle"))
        if variant == 2:
            self._needle_scale_vu(surface, pivot, radius)
        else:
            self._needle_scale_plain(surface, pivot, radius, ticks=variant == 1)
        if variant == 4:
            self._draw_needle_arm(surface, pivot, radius, math.pi - angle, color)
        self._draw_needle_arm(surface, pivot, radius, angle, color, comet=variant == 3)
        hub = max(2, int(radius * 0.06))
        pygame.draw.circle(surface, (210, 210, 220), pivot, hub)

    def _draw_needle_arm(
        self,
        surface: pygame.Surface,
        pivot: tuple[int, int],
        radius: float,
        angle: float,
        color: tuple[int, int, int],
        comet: bool = False,
    ) -> None:
        tip = (pivot[0] + math.cos(angle) * radius, pivot[1] - math.sin(angle) * radius)
        if comet:
            for frac, factor, width in ((1.0, 0.25, 9), (0.85, 0.55, 5), (0.7, 1.0, 2)):
                end = (
                    pivot[0] + math.cos(angle) * radius * frac,
                    pivot[1] - math.sin(angle) * radius * frac,
                )
                pygame.draw.line(surface, scale_color(color, factor), pivot, end, width)
            head = max(3, int(radius * 0.1))
            pygame.draw.circle(surface, color, (int(tip[0]), int(tip[1])), head)
            return
        if self._glow:
            pygame.draw.line(surface, scale_color(color, 0.4), pivot, tip, 7)
        pygame.draw.line(surface, color, pivot, tip, 3)

    @staticmethod
    def _needle_scale_plain(
        surface: pygame.Surface,
        pivot: tuple[int, int],
        radius: float,
        ticks: bool = False,
    ) -> None:
        pygame.draw.arc(
            surface,
            (60, 60, 70),
            Meters._arc_rect(pivot, radius),
            math.radians(30),
            math.radians(150),
            2,
        )
        if not ticks:
            return
        for k in range(11):
            ang = math.radians(150 - k * 12)
            outer = radius
            inner = radius * (0.82 if k % 5 else 0.72)
            pygame.draw.line(
                surface,
                (110, 110, 125),
                (pivot[0] + math.cos(ang) * inner, pivot[1] - math.sin(ang) * inner),
                (pivot[0] + math.cos(ang) * outer, pivot[1] - math.sin(ang) * outer),
                1,
            )

    @staticmethod
    def _needle_scale_vu(surface: pygame.Surface, pivot: tuple[int, int], radius: float) -> None:
        """Retro VU arc with green/amber/red broadcast zones drawn along the sweep."""
        rect = Meters._arc_rect(pivot, radius)
        for start, end, zone in (
            (30, 78, _ZONE_RED),
            (78, 102, _ZONE_AMBER),
            (102, 150, _ZONE_GREEN),
        ):
            pygame.draw.arc(surface, zone, rect, math.radians(start), math.radians(end), 4)

    @staticmethod
    def _arc_rect(pivot: tuple[int, int], radius: float) -> pygame.Rect:
        return pygame.Rect(
            int(pivot[0] - radius), int(pivot[1] - radius), int(radius * 2), int(radius * 2)
        )

    def _emit(
        self,
        style: int,
        cell: pygame.Rect,
        level: float,
        i: int,
        groups: int,
        horiz: bool,
        w: int,
        h: int,
        dt: float,
    ) -> None:
        """Spawn sparks for one meter, with count rising with its level."""
        if level < _SPARK_LEVEL_FLOOR:
            return
        # Bass meters (low i) get a gentle emission boost so they visibly shoot too.
        low_gain = 1.0 + _SPARK_LOW_GAIN * (1.0 - i / max(1, groups - 1))
        expected = (level - _SPARK_LEVEL_FLOOR) * _SPARK_RATE * low_gain * dt
        count = int(expected) + (1 if self._rng.random() < expected - int(expected) else 0)
        if count <= 0:
            return
        hue = (i + 0.5) / max(1, groups) + self._hue_drift
        if style == 2:
            self._emit_needle(cell, level, count, hue, w, h)
        else:
            self._emit_bar(cell, level, count, hue, horiz, w, h)

    def _emit_needle(
        self, cell: pygame.Rect, level: float, count: int, hue: float, w: int, h: int
    ) -> None:
        """Shoot sparks off the needle tip, flying outward along the needle's angle."""
        pivot = (cell.centerx, cell.bottom)
        radius = min(cell.width, cell.height) * 0.9
        angle = math.radians(150 - level * 120)
        tip_x = pivot[0] + math.cos(angle) * radius
        tip_y = pivot[1] - math.sin(angle) * radius
        dir_x, dir_y = math.cos(angle), -math.sin(angle)  # screen y points down
        speed = 0.25 + 0.55 * level
        for _ in range(count):
            spread = self._rng.uniform(-0.13, 0.13)
            self._sparks.spawn(
                tip_x / w,
                tip_y / h,
                (dir_x + spread) * speed,
                (dir_y + spread) * speed,
                hue + self._rng.uniform(-0.04, 0.04),
                size=self._rng.uniform(0.5, 0.95) * self._spark_mult,
            )

    def _emit_bar(
        self, cell: pygame.Rect, level: float, count: int, hue: float, horiz: bool, w: int, h: int
    ) -> None:
        """Spray sparks off the lit edge of a ladder/bar meter (up, or out when horizontal)."""
        for _ in range(count):
            if horiz:
                x = cell.left + cell.width * level
                y = self._rng.uniform(cell.top, cell.bottom)
                vx, vy = self._rng.uniform(0.06, 0.32), self._rng.uniform(-0.13, 0.13)
            else:
                x = self._rng.uniform(cell.left, cell.right)
                y = cell.bottom - cell.height * level
                vx, vy = self._rng.uniform(-0.13, 0.13), self._rng.uniform(-0.34, -0.1)
            self._sparks.spawn(
                x / w,
                y / h,
                vx,
                vy,
                hue + self._rng.uniform(-0.04, 0.04),
                size=self._rng.uniform(0.45, 0.85) * self._spark_mult,
            )

    def _render_sparks(
        self, surface: pygame.Surface, style: int, w: int, h: int, dt: float
    ) -> None:
        gravity = 0.6 if style == 2 else 0.2  # needle embers fall harder than rising bar sparks
        self._sparks.advance(dt, self.theme.speed_scale, gravity)
        size_scale = max(1.0, min(w, h) / 520.0)  # finer sparks than the old /260
        self._sparks.render(
            surface, self.theme.color_scheme, self.theme.color_phase, w, h, size_scale, trails=False
        )

    @staticmethod
    def _glow_rect(surface: pygame.Surface, rect: pygame.Rect, color: tuple[int, int, int]) -> None:
        """Cheap halo: a couple of dimmer, slightly larger rects behind ``rect``."""
        for pad, factor in ((4, 0.22), (2, 0.5)):
            pygame.draw.rect(
                surface,
                scale_color(color, factor),
                (rect.x - pad, rect.y - pad, rect.width + 2 * pad, rect.height + 2 * pad),
            )
