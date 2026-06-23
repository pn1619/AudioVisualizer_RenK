"""Frequency Skyline: an EQ city where each building is a frequency band.

Bands map left→right to a row of neon buildings; building height = band energy,
colored along a synthwave gradient (pink→purple→cyan). Lit "floors" climb each tower
with its energy, a bass pulse glows along the ground, and onsets flash the roofs. An
optional water reflection mirrors the city below the horizon.

Shipped under a ``Test_`` name during evaluation; remove the prefix once approved.
"""

from __future__ import annotations

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

_SYNTHWAVE = ((255, 40, 130), (210, 40, 220), (130, 60, 240), (60, 120, 255), (40, 230, 255))
_HORIZON = 0.62  # ground line as a fraction of height
_FLOOR_FRAC = 0.05  # floor (window row) height as a fraction of building height

_PRESET = ModeOption(
    "preset",
    "Preset",
    (
        OptionChoice("Custom", 0),
        OptionChoice("Neon Bay", 1),
        OptionChoice("Mono Metro", 2),
        OptionChoice("Sunset Strip", 3),
    ),
    default_index=0,
)
_VIEW = ModeOption(
    "view",
    "View",
    (OptionChoice("Flat", 0), OptionChoice("Perspective", 1), OptionChoice("Isometric", 2)),
    default_index=0,
)
_REFLECT = ModeOption(
    "reflect",
    "Reflection",
    (OptionChoice("Off", 0), OptionChoice("Water", 1), OptionChoice("Mirror", 2)),
    default_index=1,
)
_WINDOWS = ModeOption(
    "windows",
    "Windows",
    (OptionChoice("Off", 0), OptionChoice("Lit", 1), OptionChoice("Animated", 2)),
    default_index=1,
)
_SKYLINE = ModeOption(
    "skyline",
    "Skyline",
    (OptionChoice("Even", 0), OptionChoice("Random", 1), OptionChoice("City", 2)),
    default_index=2,
)
_PALETTE = ModeOption(
    "spalette",
    "Palette",
    (OptionChoice("Synthwave", 0), OptionChoice("Mono", 1), OptionChoice("Theme", 2)),
    default_index=0,
)
_BARS = ModeOption(
    "bars",
    "Bars",
    (OptionChoice("24", 24), OptionChoice("48", 48), OptionChoice("64", 64)),
    default_index=1,
)


@register(key="test_skyline", display_name="Test_Frequency Skyline", order=24)
class TestSkyline(BaseVisualizer):
    """A synthwave EQ city: bands as buildings, lit floors, and a water reflection."""

    OPTIONS = (_PRESET, _VIEW, _REFLECT, _WINDOWS, _SKYLINE, _PALETTE, _BARS)
    PRESETS = {
        1: {"view": 0, "reflect": 1, "windows": 1, "skyline": 2, "spalette": 0},  # Neon Bay
        2: {"view": 1, "reflect": 2, "windows": 1, "skyline": 1, "spalette": 1},  # Mono Metro
        3: {"view": 0, "reflect": 1, "windows": 2, "skyline": 2, "spalette": 0},  # Sunset Strip
    }

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._profile: np.ndarray | None = None
        self._profile_key: tuple[int, int] = (-1, -1)
        self._flash = 0.0
        self._rng = random.Random(71)

    def on_enter(self) -> None:
        self._flash = 0.0
        self._profile = None

    def _ensure_profile(self, n: int) -> None:
        kind = int(self.option("skyline"))
        if self._profile is not None and self._profile_key == (n, kind):
            return
        rng = random.Random(71)
        if kind == 0:  # even
            prof = np.full(n, 0.08, dtype=np.float32)
        else:
            prof = np.array([rng.uniform(0.05, 0.4) for _ in range(n)], dtype=np.float32)
            if kind == 2:  # city: scatter a few skyscrapers
                for _ in range(max(2, n // 10)):
                    prof[rng.randrange(n)] = rng.uniform(0.55, 0.85)
        self._profile, self._profile_key = prof, (n, kind)

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 16 or h < 16:
            return
        n = int(self.option("bars"))
        self._ensure_profile(n)
        ground_y = int(h * _HORIZON)
        max_h = ground_y * 0.95

        energies = self._bar_energies(frame, n)
        bass = 0.0 if frame is None else float(np.mean(energies[: max(1, n // 8)]))
        onset = 0.0 if frame is None else frame.onset
        self._flash = max(self._flash - dt * 3.0, onset if onset >= ONSET_THRESHOLD else 0.0)

        city = pygame.Surface((w, ground_y), pygame.SRCALPHA)
        bw = w / n
        assert self._profile is not None
        for i in range(n):
            energy = clamp(float(self._profile[i]) + float(energies[i]) * 0.95)
            self._draw_building(city, i, n, bw, ground_y, max_h, energy)

        surface.blit(city, (0, 0))
        self._draw_reflection(surface, city, w, h, ground_y)
        self._draw_ground(surface, w, ground_y, bass)

    def _building_color(self, i: int, n: int) -> Color:
        mode = int(self.option("spalette"))
        frac = i / max(1, n - 1)
        if mode == 2:
            return themed_color(self.theme.color_scheme, frac, _SYNTHWAVE, self.theme.color_phase)
        if mode == 1:
            return themed_color("mono", frac, _SYNTHWAVE)
        return palette_color(_SYNTHWAVE, frac)

    def _draw_building(
        self,
        city: pygame.Surface,
        i: int,
        n: int,
        bw: float,
        ground_y: int,
        max_h: float,
        energy: float,
    ) -> None:
        color = self._building_color(i, n)
        height = max(2.0, energy * max_h)
        inset = 1 + (int(bw) // 8)
        x = int(i * bw) + inset
        bwi = max(2, int(bw) - inset * 2)
        if int(self.option("view")) == 1:  # perspective: taper toward the edges
            edge = abs(i / (n - 1) - 0.5) * 2.0 if n > 1 else 0.0
            bwi = max(2, int(bwi * (1.0 - 0.35 * edge)))
        top = int(ground_y - height)
        pygame.draw.rect(city, scale_color(color, 0.16), (x, top, bwi, int(height)))
        self._draw_windows(city, x, top, bwi, int(height), color, energy)
        roof = scale_color(color, clamp(1.0 + self._flash))  # bright neon roof line
        pygame.draw.rect(city, roof, (x, top, bwi, max(2, int(height * 0.03))))
        if int(self.option("view")) == 2:  # isometric: a small top face
            d = max(2, bwi // 4)
            face = [(x, top), (x + d, top - d), (x + bwi + d, top - d), (x + bwi, top)]
            pygame.draw.polygon(city, scale_color(color, 0.6), face)

    def _draw_windows(
        self,
        city: pygame.Surface,
        x: int,
        top: int,
        bwi: int,
        height: int,
        color: Color,
        energy: float,
    ) -> None:
        mode = int(self.option("windows"))
        if mode == 0 or height < 6:
            pygame.draw.rect(city, scale_color(color, 0.5), (x, top, bwi, height))
            return
        floor_h = max(2, int(height * _FLOOR_FRAC))
        floors = max(1, height // floor_h)
        lit = int(floors * clamp(energy * 1.15))
        for f in range(floors):
            fy = top + height - (f + 1) * floor_h
            on = f < lit
            if mode == 2 and on:  # animated flicker
                on = self._rng.random() > 0.18
            shade = (1.1 if on else 0.22) * (0.85 + 0.3 * (f / floors))
            pygame.draw.rect(city, scale_color(color, shade), (x, fy, bwi, floor_h - 1))

    def _draw_reflection(
        self, surface: pygame.Surface, city: pygame.Surface, w: int, h: int, ground_y: int
    ) -> None:
        mode = int(self.option("reflect"))
        if mode == 0:
            return
        refl_h = h - ground_y
        flipped = pygame.transform.flip(city, False, True)
        if mode == 1:  # water: softer + slightly squashed shimmer
            flipped = pygame.transform.smoothscale(flipped, (w, refl_h))
            flipped.set_alpha(95)
        else:  # mirror: sharper
            flipped = flipped.subsurface((0, 0, w, min(refl_h, ground_y))).copy()
            flipped.set_alpha(150)
        surface.blit(flipped, (0, ground_y))

    def _draw_ground(self, surface: pygame.Surface, w: int, ground_y: int, bass: float) -> None:
        glow = scale_color((120, 90, 255), clamp(0.4 + 0.6 * bass + self._flash))
        pygame.draw.line(surface, glow, (0, ground_y), (w, ground_y), max(2, int(2 + bass * 4)))

    def _bar_energies(self, frame: AnalysisFrame | None, n: int) -> np.ndarray:
        from audio_visualizer.visuals._helpers import resample_to

        if frame is None or frame.band_energies.size == 0:
            return np.zeros(n, dtype=np.float32)
        return resample_to(frame.band_energies.astype(np.float32), n)
