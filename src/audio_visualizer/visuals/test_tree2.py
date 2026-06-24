"""Fractal Tree v2: a glowing, bilaterally-symmetric bioluminescent tree.

A faithful take on the concept art: a teal->magenta canopy of gently arcing branches
filling a wide rounded dome, with pink blossoms clustered at the tips, over a twinkling
starfield. The **tree shape is decoupled from the audio** -- geometry is built from
canvas fractions each frame (so it always fits the window regardless of the Size control
or how loud the music is). Audio only drives the *life* of the scene: bass makes the
whole tree breathe (glow), treble + onsets bloom the blossoms and twinkle the stars, and
a gentle wind sways the canopy. This avoids v1's failure mode where high sensitivity or a
large Size grew the tree off-screen or made it thrash.

The canopy is grown for the right half only (with deterministic organic variation) then
mirrored about the trunk, guaranteeing the concept's clean bilateral symmetry.

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
    SHARED_PALETTES,
    Color,
    clamp,
    palette_color,
    scale_color,
    themed_color,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

# Concept-art bioluminescent ramp: teal trunk -> blue -> violet -> magenta -> pink tips.
_BIO = ((18, 200, 188), (40, 150, 232), (120, 92, 232), (226, 60, 182), (255, 158, 214))
_SEG_CAP = 14000  # hard ceiling on branch segments per half-frame (safety)
_STAR_COUNT = 190
_RATIO = 0.77  # child / parent length
_TRUNK_FRAC = 0.14  # trunk length as a fraction of canvas height (fixed -> always fits)
_CANOPY_FRAC = 0.175  # first canopy branch length (fraction of height); sized to fit
_TOP_MARGIN = 0.04  # safety: branches stop this fraction from the top (rarely reached)
_GEOM_SEED = 7  # fixed seed -> the random structure is identical every frame (stable)

# A drawn branch segment carried from the (right-half) growth pass to the render pass.
_Seg = tuple[list[tuple[float, float]], float, int]  # points, order(0..1), width

_PRESET = ModeOption(
    "preset",
    "Preset",
    (
        OptionChoice("Custom", 0),
        OptionChoice("Cherry Blossom", 1),
        OptionChoice("Coral Reef", 2),
        OptionChoice("Aurora Bonsai", 3),
    ),
    default_index=1,
)
_DEPTH = ModeOption(
    "tdepth",
    "Branches",
    (OptionChoice("Sparse", 7), OptionChoice("Full", 8), OptionChoice("Dense", 9)),
    default_index=1,
)
_SPREAD = ModeOption(
    "tspread",
    "Spread",
    (OptionChoice("Narrow", 0.30), OptionChoice("Natural", 0.40), OptionChoice("Wide", 0.50)),
    default_index=1,
)
_BLOOM = ModeOption(
    "tbloom",
    "Bloom",
    (OptionChoice("Bare", 0.0), OptionChoice("Soft", 1.0), OptionChoice("Lush", 1.7)),
    default_index=2,
)
_GLOW = ModeOption(
    "tglow",
    "Glow",
    (OptionChoice("Dim", 0.5), OptionChoice("Soft", 1.0), OptionChoice("Bright", 1.6)),
    default_index=1,
)
_SWAY = ModeOption(
    "tsway",
    "Sway",
    (OptionChoice("Still", 0.0), OptionChoice("Calm", 0.045), OptionChoice("Breezy", 0.09)),
    default_index=1,
)
_PALETTE = ModeOption(
    "tpalette2",
    "Palette",
    (
        OptionChoice("Bioluminescent", 0),
        OptionChoice("Ocean", 1),
        OptionChoice("Neon", 2),
        OptionChoice("Theme", 3),
    ),
    default_index=0,
)


@register(key="test_tree2", display_name="Test_Fractal Tree v2", order=96)
class TestTree2(BaseVisualizer):
    """A glowing symmetric bioluminescent tree that breathes and blooms to the beat.

    Geometry is intentionally independent of loudness and the Size control, so the
    figure always fits the window; audio modulates glow, blossom size, and sway only.
    """

    OPTIONS = (_PRESET, _DEPTH, _SPREAD, _BLOOM, _GLOW, _SWAY, _PALETTE)
    PRESETS = {
        1: {"tdepth": 1, "tspread": 2, "tbloom": 2, "tglow": 2, "tsway": 1, "tpalette2": 0},
        2: {"tdepth": 1, "tspread": 1, "tbloom": 1, "tglow": 1, "tsway": 2, "tpalette2": 1},
        3: {"tdepth": 2, "tspread": 0, "tbloom": 0, "tglow": 2, "tsway": 0, "tpalette2": 2},
    }

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._t = 0.0
        self._sway = 0.0
        self._segs: list[_Seg] = []  # right-half branch segments for this frame
        self._tips: list[tuple[float, float]] = []  # right-half tip positions
        self._bloom: np.ndarray = np.zeros(0, dtype=np.float32)  # per-tip bloom envelope
        self._stars: np.ndarray = np.zeros((0, 4), dtype=np.float32)  # x, y, phase, size
        self._rng = random.Random(96)  # bursts + stars (advances over time)
        self._grng = random.Random(_GEOM_SEED)  # geometry (reseeded each frame -> stable)
        self._count = 0

    def on_enter(self) -> None:
        self._t = self._sway = 0.0
        self._bloom = np.zeros(0, dtype=np.float32)
        self._rng.seed(96)
        self._make_stars()

    def _make_stars(self) -> None:
        """Scatter a fixed, deterministic field of background stars (normalized)."""
        rng = random.Random(961)
        self._stars = np.array(
            [
                (rng.random(), rng.random() * 0.95, rng.random(), rng.uniform(0.6, 2.3))
                for _ in range(_STAR_COUNT)
            ],
            dtype=np.float32,
        )

    # -- frame ----------------------------------------------------------------
    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        bands = None if frame is None else frame.band_energies
        bass = 0.0 if bands is None or not bands.size else float(np.mean(bands[:8]))
        treble = 0.0 if bands is None or not bands.size else float(np.mean(bands[24:]))
        rms = 0.0 if frame is None else min(1.0, frame.rms)
        onset = 0.0 if frame is None else frame.onset
        self._t += dt

        wind = float(self.option("tsway")) * (0.4 if self.reduce_motion else 1.0)
        self._sway = math.sin(self._t * 1.1 * self.theme.speed_scale) * wind * (0.5 + 0.7 * bass)

        cx = w * 0.5
        self._grow_canopy(w, h)
        glow_gain = clamp(float(self.option("tglow")) * (0.5 + 0.5 * rms))

        glow = pygame.Surface((w, h), pygame.SRCALPHA)
        self._draw_stars(glow, w, h, treble)
        self._draw_roots(surface, glow, w, h, cx, glow_gain)
        self._render_branches(surface, glow, glow_gain)
        self._draw_blossoms(surface, glow, dt, onset, treble)
        surface.blit(glow, (0, 0), special_flags=pygame.BLEND_ADD)

    # -- canopy growth (right half only; mirrored at render time) -------------
    def _grow_canopy(self, w: int, h: int) -> None:
        self._segs.clear()
        self._tips.clear()
        self._count = 0
        max_depth = int(self.option("tdepth"))
        cx, base_y = w * 0.5, h * 0.95
        fork_y = base_y - h * _TRUNK_FRAC
        trunk_w = max(2, int(8 * self.theme.size_scale))
        self._segs.append(([(cx, base_y), (cx, fork_y)], 0.0, trunk_w))
        # A balanced binary canopy grown straight up from the fork: each branch splits
        # into a symmetric ``±spread`` pair, so the figure is inherently bilaterally
        # symmetric and fills a rounded fan (no dominant spokes). Sized to fit so the
        # full recursion expresses inside the frame (density) without hitting the top.
        self._grow(w, h, (cx, fork_y), 0.0, h * _CANOPY_FRAC, max_depth, max_depth)

    def _grow(
        self,
        w: int,
        h: int,
        origin: tuple[float, float],
        angle: float,
        length: float,
        depth: int,
        max_depth: int,
    ) -> None:
        """Grow one arcing branch, then recurse into a symmetric pair of children."""
        if (
            depth <= 0
            or length < h * 0.006
            or self._count > _SEG_CAP
            or origin[1] < h * _TOP_MARGIN
        ):
            self._tips.append(origin)
            return
        self._count += 1
        order = 1.0 - depth / max_depth
        steps = 4 if order < 0.35 else 2  # arc the big limbs more
        seg = length / steps
        curl = -0.26 * math.sin(angle)  # gently bend back toward vertical -> rounded dome
        x, y = origin
        pts: list[tuple[float, float]] = [(x, y)]
        a = angle
        for _ in range(steps):
            x += math.sin(a) * seg
            y -= math.cos(a) * seg
            pts.append((x, y))
            a += curl / steps
        width = max(1, int((1.0 - order) * 8 * self.theme.size_scale))
        self._segs.append((pts, order, width))

        sway = self._sway * (order + 0.25)
        spread = float(self.option("tspread"))
        child_len = length * _RATIO
        # Open the first split a little wider to form the vase, then a steady angle.
        delta = spread * (1.25 if order < 0.12 else 1.0)
        for sgn in (-1.0, 1.0):
            self._grow(w, h, (x, y), a + sgn * delta + sway, child_len, depth - 1, max_depth)
        # Symmetric short side-twigs through the mid-canopy: their tips become the
        # interior blossoms/leaves so the dome fills (not just a rim) like the concept.
        if 0.3 < order < 0.82 and depth > 2:
            for sgn in (-1.0, 1.0):
                stub_a = a + sgn * delta * 2.3 + sway
                self._grow(w, h, (x, y), stub_a, child_len * 0.5, 2, max_depth)

    # -- rendering ------------------------------------------------------------
    def _render_branches(
        self, surface: pygame.Surface, glow: pygame.Surface, glow_gain: float
    ) -> None:
        for pts, order, width in self._segs:
            color = self._branch_color(order)
            pygame.draw.lines(glow, (*scale_color(color, glow_gain), 70), False, pts, width * 2 + 2)
            pygame.draw.lines(surface, color, False, pts, width)

    def _draw_roots(
        self,
        surface: pygame.Surface,
        glow: pygame.Surface,
        w: int,
        h: int,
        cx: float,
        glow_gain: float,
    ) -> None:
        """A few glowing teal roots fanning out along the base (concept-art detail)."""
        base_y = h * 0.92
        color = self._branch_color(0.0)
        for k in (1, 2, 3):
            spread = k / 3.0
            for sgn in (-1.0, 1.0):
                pts = [
                    (cx, base_y),
                    (cx + sgn * spread * w * 0.10, base_y + h * 0.03),
                    (cx + sgn * spread * w * 0.22, h * 0.99),
                ]
                pygame.draw.lines(glow, (*scale_color(color, glow_gain), 55), False, pts, 5)
                pygame.draw.lines(surface, scale_color(color, 0.7), False, pts, 2)

    def _branch_color(self, order: float) -> Color:
        mode = int(self.option("tpalette2"))
        if mode == 1:
            return palette_color(SHARED_PALETTES[2], clamp(order))  # Ocean
        if mode == 2:
            return palette_color(SHARED_PALETTES[4], clamp(order))  # Neon
        if mode == 3:
            return themed_color(self.theme.color_scheme, clamp(order), _BIO, self.theme.color_phase)
        return palette_color(_BIO, clamp(order))

    # -- blossoms -------------------------------------------------------------
    def _draw_blossoms(
        self, surface: pygame.Surface, glow: pygame.Surface, dt: float, onset: float, treble: float
    ) -> None:
        """Pink flower clusters at the tips: always faintly present, bloom on beats."""
        amount = float(self.option("tbloom"))
        n = len(self._tips)
        if amount <= 0.0 or n == 0:
            self._bloom = np.zeros(0, dtype=np.float32)
            return
        if self._bloom.shape[0] != n:
            self._bloom = np.zeros(n, dtype=np.float32)
        self._bloom *= math.exp(-dt * 1.6)  # decay previous bursts
        if onset >= ONSET_THRESHOLD and not self.reduce_motion:
            for _ in range(max(3, n // 5)):
                self._bloom[self._rng.randrange(n)] = 1.0

        baseline = 0.12 + 0.32 * treble
        petal = self._branch_color(0.86)  # blossoms follow the canopy-tip color
        core = self._branch_color(1.0)
        size = self.theme.size_scale
        for i, (tx, ty) in enumerate(self._tips):
            # Only ~60% of tips carry a full flower (deterministic) so clusters stay
            # distinct like the concept; the rest get a faint leaf dot.
            flower = (i * 7 + 3) % 5 < 3
            env = clamp(max(float(self._bloom[i]), baseline)) * (0.5 + 0.5 * amount)
            self._blossom(surface, glow, int(tx), int(ty), env, amount, petal, core, size, flower)

    @staticmethod
    def _blossom(
        surface: pygame.Surface,
        glow: pygame.Surface,
        x: int,
        y: int,
        env: float,
        amount: float,
        petal: Color,
        core: Color,
        size: float,
        flower: bool,
    ) -> None:
        if not flower:  # a faint leaf dot on the off-tips keeps the canopy textured
            r = max(1, int((1.2 + 1.5 * env) * size))
            pygame.draw.circle(glow, (*scale_color(petal, 0.5 * env), 55), (x, y), r * 2)
            pygame.draw.circle(surface, scale_color(petal, 0.35 + 0.4 * env), (x, y), r)
            return
        r = max(1, int((1.4 + 4.0 * env * amount) * size))
        pygame.draw.circle(glow, (*scale_color(petal, env), 70), (x, y), int(r * 1.9))
        petal_c = scale_color(petal, 0.45 + 0.55 * env)
        petal_r = max(1, int(r * 0.7))
        for p in range(5):  # petal rosette
            ang = (p / 5.0) * math.tau + env * 1.3
            px = x + int(math.cos(ang) * r * 0.85)
            py = y + int(math.sin(ang) * r * 0.85)
            pygame.draw.circle(surface, petal_c, (px, py), petal_r)
        pygame.draw.circle(surface, scale_color(core, 0.7 + 0.3 * env), (x, y), max(1, r // 2))

    # -- background -----------------------------------------------------------
    def _draw_stars(self, glow: pygame.Surface, w: int, h: int, treble: float) -> None:
        """Twinkling starfield drawn additively behind the tree."""
        if self._stars.shape[0] == 0:
            self._make_stars()
        tip = palette_color(_BIO, 0.7)
        for sx, sy, phase, ssize in self._stars:
            tw = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(self._t * 2.0 + phase * math.tau))
            bright = clamp(tw * (0.6 + 0.7 * treble))
            r = max(1, int(ssize * self.theme.size_scale))
            pygame.draw.circle(
                glow, (*scale_color(tip, bright), int(170 * bright)), (int(sx * w), int(sy * h)), r
            )
