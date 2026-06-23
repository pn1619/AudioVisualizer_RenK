"""Fractal Tree: a recursive L-system tree that sways and blossoms on beats.

A branch recurses into smaller child branches; ``bass`` sways the canopy (tips move
most), ``treble`` shimmers the leaves, and onsets pop blossom sprites from the tips.
Branch color flows from a teal trunk to bright magenta tips (bioluminescent). Geometry
is regenerated each frame with the live sway but stays cheap (depth-capped segments).

Shipped under a ``Test_`` name during evaluation; remove the prefix once approved.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import ONSET_THRESHOLD
from audio_visualizer.visuals._helpers import (
    Color,
    clamp,
    palette_color,
    scale_color,
    themed_color,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_SEG_CAP = 4000  # hard ceiling on branch segments per frame
_BIO = ((30, 210, 200), (70, 170, 255), (150, 95, 240), (240, 70, 200), (255, 140, 220))
_SEASON = ((90, 60, 30), (120, 150, 60), (90, 200, 120), (255, 180, 60), (255, 90, 120))

# species -> (child angle deltas, length ratio, max effective depth)
_SPECIES = {
    0: ((-0.42, 0.42), 0.74, 9),  # oak
    1: ((-0.30, 0.30), 0.78, 9),  # willow (narrow, drooping)
    2: ((-0.55, 0.0, 0.55), 0.66, 6),  # coral (3-way)
    3: ((-0.32, 0.0, 0.32), 0.80, 7),  # fern (feathery, central shoot)
}

_PRESET = ModeOption(
    "preset",
    "Preset",
    (
        OptionChoice("Custom", 0),
        OptionChoice("Cherry Blossom", 1),
        OptionChoice("Coral Reef", 2),
        OptionChoice("Winter Bare", 3),
    ),
    default_index=0,
)
_SPECIES_OPT = ModeOption(
    "species",
    "Species",
    (
        OptionChoice("Oak", 0),
        OptionChoice("Willow", 1),
        OptionChoice("Coral", 2),
        OptionChoice("Fern", 3),
    ),
    default_index=0,
)
_DEPTH = ModeOption(
    "tdepth",
    "Depth",
    (
        OptionChoice("5", 5),
        OptionChoice("6", 6),
        OptionChoice("7", 7),
        OptionChoice("8", 8),
        OptionChoice("9", 9),
    ),
    default_index=2,
)
_WIND = ModeOption(
    "wind",
    "Wind",
    (OptionChoice("Calm", 0.04), OptionChoice("Breezy", 0.11), OptionChoice("Gale", 0.22)),
    default_index=1,
)
_FOLIAGE = ModeOption(
    "foliage",
    "Foliage",
    (OptionChoice("Bare", 0), OptionChoice("Leaves", 1), OptionChoice("Blossoms", 2)),
    default_index=2,
)
_SYMMETRY = ModeOption(
    "tsym",
    "Symmetry",
    (OptionChoice("Natural", 0), OptionChoice("Mirrored", 1)),
    default_index=0,
)
_PALETTE = ModeOption(
    "tpalette",
    "Palette",
    (OptionChoice("Bioluminescent", 0), OptionChoice("Seasons", 1), OptionChoice("Theme", 2)),
    default_index=0,
)


class _Blossom:
    __slots__ = ("x", "y", "vy", "life", "hue")

    def __init__(self, x: float, y: float, vy: float, hue: float) -> None:
        self.x, self.y, self.vy, self.life, self.hue = x, y, vy, 1.0, hue


@register(key="test_tree", display_name="Test_Fractal Tree", order=95)
class TestTree(BaseVisualizer):
    """A swaying recursive tree with teal→magenta branches and beat blossoms."""

    OPTIONS = (_PRESET, _SPECIES_OPT, _DEPTH, _WIND, _FOLIAGE, _SYMMETRY, _PALETTE)
    PRESETS = {
        1: {"species": 0, "tdepth": 2, "wind": 1, "foliage": 2, "tsym": 0, "tpalette": 0},
        2: {"species": 2, "tdepth": 1, "wind": 1, "foliage": 1, "tsym": 0, "tpalette": 0},
        3: {"species": 0, "tdepth": 2, "wind": 0, "foliage": 0, "tsym": 1, "tpalette": 1},
    }

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._t = 0.0
        self._sway = 0.0
        self._tips: list[tuple[float, float, float]] = []  # x, y, order-fraction
        self._segs = 0
        self._blossoms: list[_Blossom] = []
        self._rng = random.Random(95)

    def on_enter(self) -> None:
        self._t = self._sway = 0.0
        self._blossoms.clear()
        self._rng.seed(95)

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        bands = None if frame is None else frame.band_energies
        bass = 0.0 if bands is None or not bands.size else float(np.mean(bands[:8]))
        treble = 0.0 if bands is None or not bands.size else float(np.mean(bands[24:]))
        onset = 0.0 if frame is None else frame.onset
        self._t += dt

        wind = float(self.option("wind")) * (0.4 if self.reduce_motion else 1.0)
        self._sway = math.sin(self._t * 1.3 * self.theme.speed_scale) * wind * (0.6 + bass)

        glow = pygame.Surface((w, h), pygame.SRCALPHA)
        self._tips.clear()
        self._segs = 0
        max_depth = int(self.option("tdepth"))
        species = int(self.option("species"))
        deltas, ratio, cap_depth = _SPECIES[species]
        depth = min(max_depth, cap_depth)
        length = h * 0.26 * self.theme.size_scale * (1.0 + 0.25 * bass)
        self._branch(
            surface, glow, w, h, w / 2.0, h * 0.96, 0.0, length, depth, depth, deltas, ratio
        )
        surface.blit(glow, (0, 0), special_flags=pygame.BLEND_ADD)
        self._foliage(surface, w, h, dt, onset, treble)

    def _branch(
        self,
        surface: pygame.Surface,
        glow: pygame.Surface,
        w: int,
        h: int,
        x: float,
        y: float,
        angle: float,
        length: float,
        depth: int,
        max_depth: int,
        deltas: tuple[float, ...],
        ratio: float,
    ) -> None:
        if depth <= 0 or length < 2.0 or self._segs > _SEG_CAP:
            self._tips.append((x, y, 1.0))
            return
        self._segs += 1
        order = 1.0 - depth / max_depth  # 0 = trunk, 1 = tip
        x2 = x + math.sin(angle) * length
        y2 = y - math.cos(angle) * length
        color = self._branch_color(order)
        width = max(1, int((depth / max_depth) * 7 * self.theme.size_scale))
        pygame.draw.line(surface, color, (int(x), int(y)), (int(x2), int(y2)), width)
        pygame.draw.line(glow, (*color, 50), (int(x), int(y)), (int(x2), int(y2)), width * 2)

        natural = int(self.option("tsym")) == 0
        for d in deltas:
            jitter = self._rng.uniform(-0.12, 0.12) if natural else 0.0
            sway = self._sway * (order + 0.3)  # tips sway more
            child = angle + d + jitter + sway
            self._branch(
                surface,
                glow,
                w,
                h,
                x2,
                y2,
                child,
                length * ratio,
                depth - 1,
                max_depth,
                deltas,
                ratio,
            )

    def _branch_color(self, order: float) -> Color:
        mode = int(self.option("tpalette"))
        if mode == 2:
            return themed_color(self.theme.color_scheme, order, _BIO, self.theme.color_phase)
        palette = _SEASON if mode == 1 else _BIO
        return palette_color(palette, clamp(order))

    def _foliage(
        self, surface: pygame.Surface, w: int, h: int, dt: float, onset: float, treble: float
    ) -> None:
        mode = int(self.option("foliage"))
        if mode == 0:
            self._blossoms.clear()
            return
        leaf_color = self._branch_color(1.0)
        if mode == 1:  # static leaves shimmering with treble
            r = max(1, int(2 + treble * 4))
            for x, y, _ in self._tips:
                c = scale_color(leaf_color, clamp(0.5 + 0.5 * treble))
                pygame.draw.circle(surface, c, (int(x), int(y)), r)
            return
        self._update_blossoms(surface, dt, onset, w, h)

    def _update_blossoms(
        self, surface: pygame.Surface, dt: float, onset: float, w: int, h: int
    ) -> None:
        if onset >= ONSET_THRESHOLD and not self.reduce_motion and self._tips:
            for _ in range(min(6, len(self._tips))):
                x, y, _ = self._rng.choice(self._tips)
                self._blossoms.append(
                    _Blossom(
                        x / w, y / h, self._rng.uniform(0.02, 0.06), self._rng.uniform(0.85, 1.0)
                    )
                )
        alive: list[_Blossom] = []
        for b in self._blossoms:
            b.life -= dt * 0.7
            if b.life <= 0:
                continue
            b.y += b.vy * dt
            color = scale_color(palette_color(_BIO, b.hue), clamp(b.life))
            r = max(1, int(3 * b.life * self.theme.size_scale))
            pygame.draw.circle(surface, color, (int(b.x * w), int(b.y * h)), r)
            alive.append(b)
        self._blossoms = alive
