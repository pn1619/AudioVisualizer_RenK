"""Lava Lamp: gooey metaball blobs that merge and split, driven by the bass.

Blobs roam a low-resolution scalar field (``Σ rᵢ²/dist²``); thresholding it gives the
classic gooey merge/split look, tinted by field magnitude and upscaled (the Plasma
pattern, so it stays cheap). Bass swells the blobs, onsets spawn/split them, and a
gravity option floats them up or sinks them down.

Shipped under a ``Test_`` name during evaluation; remove the prefix once approved.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import ONSET_THRESHOLD
from audio_visualizer.visuals._helpers import SHARED_PALETTES, clamp, palette_color, themed_color
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_GRID_W = 200  # field computed at this width then smoothscaled
_COUNTS = {0: 5, 1: 8, 2: 13}
_LAVA = SHARED_PALETTES[3]
_PLASMA = SHARED_PALETTES[4]

_PRESET = ModeOption(
    "preset",
    "Preset",
    (
        OptionChoice("Custom", 0),
        OptionChoice("Classic Lava", 1),
        OptionChoice("Plasma Goo", 2),
        OptionChoice("Zero-G", 3),
    ),
    default_index=0,
)
_BLOBS = ModeOption(
    "blobs",
    "Blobs",
    (OptionChoice("Few", 0), OptionChoice("Some", 1), OptionChoice("Many", 2)),
    default_index=1,
)
_VISCOSITY = ModeOption(
    "viscosity",
    "Viscosity",
    (OptionChoice("Thick", 0), OptionChoice("Smooth", 1), OptionChoice("Runny", 2)),
    default_index=1,
)
_SURFACE = ModeOption(
    "surface",
    "Surface",
    (OptionChoice("Filled", 0), OptionChoice("Outline", 1), OptionChoice("Gooey", 2)),
    default_index=2,
)
_GRAVITY = ModeOption(
    "gravity",
    "Gravity",
    (OptionChoice("Float", 0), OptionChoice("Up", 1), OptionChoice("Down", 2)),
    default_index=0,
)
_PALETTE = ModeOption(
    "mpalette",
    "Palette",
    (OptionChoice("Lava", 0), OptionChoice("Plasma", 1), OptionChoice("Theme", 2)),
    default_index=0,
)
_REACTIVITY = ModeOption(
    "reactivity",
    "Reactivity",
    (OptionChoice("Calm", 0.6), OptionChoice("Normal", 1.0), OptionChoice("Wild", 1.7)),
    default_index=1,
)


@dataclass
class _Blob:
    x: float
    y: float
    vx: float
    vy: float
    r: float


@register(key="test_metaballs", display_name="Test_Lava Lamp", order=83)
class TestMetaballs(BaseVisualizer):
    """Bass-reactive gooey metaballs on a low-res scalar field."""

    OPTIONS = (_PRESET, _BLOBS, _VISCOSITY, _SURFACE, _GRAVITY, _PALETTE, _REACTIVITY)
    PRESETS = {
        1: {"blobs": 1, "viscosity": 1, "surface": 2, "gravity": 0, "mpalette": 0},  # Classic Lava
        2: {"blobs": 2, "viscosity": 2, "surface": 2, "gravity": 0, "mpalette": 1},  # Plasma Goo
        3: {"blobs": 1, "viscosity": 1, "surface": 0, "gravity": 0, "mpalette": 1},  # Zero-G
    }

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._blobs: list[_Blob] = []
        self._n = -1
        self._grid: tuple[int, int] | None = None
        self._xx: np.ndarray | None = None
        self._yy: np.ndarray | None = None
        self._lut = _build_lut(_LAVA)
        self._lut_key: tuple[int, str] = (-1, "")
        self._rng = random.Random(63)

    def on_enter(self) -> None:
        self._blobs.clear()
        self._n = -1
        self._rng.seed(63)

    def _ensure_blobs(self) -> None:
        n = _COUNTS[int(self.option("blobs"))]
        if self.reduce_motion:
            n = max(3, n - 3)
        if n == self._n:
            return
        self._blobs = [
            _Blob(
                self._rng.uniform(0.15, 0.85),
                self._rng.uniform(0.15, 0.85),
                self._rng.uniform(-0.07, 0.07),
                self._rng.uniform(-0.07, 0.07),
                self._rng.uniform(0.05, 0.1),
            )
            for _ in range(n)
        ]
        self._n = n

    def _ensure_grid(self, w: int, h: int) -> None:
        gw = _GRID_W
        gh = max(2, int(gw * h / w))
        if self._grid == (gw, gh):
            return
        xs = np.linspace(0.0, 1.0, gw, dtype=np.float32)
        ys = np.linspace(0.0, 1.0, gh, dtype=np.float32)
        self._xx, self._yy = np.meshgrid(xs, ys)
        self._grid = (gw, gh)

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        self._ensure_blobs()
        self._ensure_grid(w, h)
        assert self._xx is not None and self._yy is not None

        bass = (
            0.0
            if frame is None or not frame.band_energies.size
            else float(np.mean(frame.band_energies[:8]))
        )
        mids = (
            0.0
            if frame is None or not frame.band_energies.size
            else float(np.mean(frame.band_energies[8:24]))
        )
        onset = 0.0 if frame is None else frame.onset
        react = float(self.option("reactivity"))
        self._move(dt, bass, mids, onset, react)

        field = self._field(bass)
        rgb = self._colorize(field)
        small = pygame.surfarray.make_surface(np.transpose(rgb, (1, 0, 2)))
        surface.blit(pygame.transform.smoothscale(small, (w, h)), (0, 0))

    def _move(self, dt: float, bass: float, mids: float, onset: float, react: float) -> None:
        grav = int(self.option("gravity"))
        gy = {0: 0.0, 1: -0.06, 2: 0.06}[grav]
        speed = dt * self.theme.speed_scale * react * (0.6 if self.reduce_motion else 1.0)
        for b in self._blobs:
            b.vy += gy * speed + (mids - 0.3) * 0.04 * speed
            b.x += b.vx * speed
            b.y += b.vy * speed
            if b.x < 0.08 or b.x > 0.92:
                b.vx *= -1
                b.x = clamp(b.x, 0.08, 0.92)
            if b.y < 0.08 or b.y > 0.92:
                b.vy *= -1
                b.y = clamp(b.y, 0.08, 0.92)
            target = (0.05 + 0.09 * bass) * (0.75 + 0.45 * react)
            b.r += (target - b.r) * 0.1
        if onset >= ONSET_THRESHOLD and not self.reduce_motion:  # beat nudge / split
            b = self._rng.choice(self._blobs)
            b.vx += self._rng.uniform(-0.1, 0.1) * react
            b.vy += self._rng.uniform(-0.1, 0.1) * react

    def _field(self, bass: float) -> np.ndarray:
        assert self._xx is not None and self._yy is not None
        field = np.zeros_like(self._xx)
        for b in self._blobs:
            r2 = b.r * b.r  # classic metaball: field ~= 1 at distance r from the blob
            field += r2 / ((self._xx - b.x) ** 2 + (self._yy - b.y) ** 2 + 0.0006)
        return field

    def _colorize(self, field: np.ndarray) -> np.ndarray:
        self._ensure_lut()
        visc = int(self.option("viscosity"))
        thr = {0: 1.7, 1: 1.15, 2: 0.8}[visc]
        surface_mode = int(self.option("surface"))
        intensity = np.clip(field / (thr * 2.4), 0.0, 1.0)
        idx = (intensity * 255).astype(np.int32)
        rgb = self._lut[idx].astype(np.float32)
        if surface_mode == 1:  # outline: keep only the threshold band
            band = np.clip(1.0 - np.abs(field - thr) / (thr * 0.25), 0.0, 1.0)
            edge = band[..., None]
        else:  # filled / gooey: smooth falloff across the threshold
            edge = np.clip((field - thr) / (thr * 0.5) + 0.6, 0.0, 1.0)[..., None]
            if surface_mode == 2:  # gooey: extra inner glow
                edge = np.clip(edge * 1.3, 0.0, 1.0)
        return (rgb * edge).astype(np.uint8)

    def _ensure_lut(self) -> None:
        mode = int(self.option("mpalette"))
        scheme = self.theme.color_scheme
        if self._lut_key == (mode, scheme):
            return
        if mode == 2:
            ramp = tuple(
                themed_color(scheme, i / 6.0, _LAVA, self.theme.color_phase) for i in range(7)
            )
        else:
            ramp = _PLASMA if mode == 1 else _LAVA
        self._lut = _build_lut(ramp)
        self._lut_key = (mode, scheme)


def _build_lut(palette: tuple[tuple[int, int, int], ...]) -> np.ndarray:
    lut = np.empty((256, 3), dtype=np.uint8)
    for i in range(256):
        lut[i] = palette_color(palette, i / 255.0)
    return lut
