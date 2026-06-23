"""Mandala Bloom: a symmetric generative flower that breathes with the spectrum.

Concentric rings of petals repeat around a chosen rotational symmetry (4/6/8/12-fold).
Each ring's petal length rides a frequency band, the figure slowly spins on ``rms``, and
onsets pulse a bloom outward. A warm glowing core anchors the center. Rings draw
outer→inner so the bright heart sits on top.

Shipped under a ``Test_`` name during evaluation; remove the prefix once approved.
"""

from __future__ import annotations

import math

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import ONSET_THRESHOLD
from audio_visualizer.visuals._helpers import (
    PALETTE_OPTION,
    SYMMETRY_OPTION,
    clamp,
    palette_or_theme,
    resample_to,
    scale_color,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_MAX_R = 0.48  # outer reach as a fraction of min(w, h)
_CORE_HUE = (255, 220, 120)

_PRESET = ModeOption(
    "preset",
    "Preset",
    (
        OptionChoice("Custom", 0),
        OptionChoice("Lotus", 1),
        OptionChoice("Sacred", 2),
        OptionChoice("Kaleido", 3),
    ),
    default_index=0,
)
_LAYERS = ModeOption(
    "layers",
    "Layers",
    (OptionChoice("3", 3), OptionChoice("5", 5), OptionChoice("7", 7)),
    default_index=1,
)
_BLOOM = ModeOption(
    "bloom",
    "Bloom",
    (OptionChoice("Breathe", 0), OptionChoice("Pulse", 1), OptionChoice("Unfold", 2)),
    default_index=0,
)
_PETAL = ModeOption(
    "petal",
    "Petal",
    (
        OptionChoice("Lotus", 0),
        OptionChoice("Star", 1),
        OptionChoice("Leaf", 2),
        OptionChoice("Geometric", 3),
    ),
    default_index=0,
)
_SPIN = ModeOption(
    "spin",
    "Spin",
    (OptionChoice("Off", 0.0), OptionChoice("Slow", 1.0), OptionChoice("Fast", 2.5)),
    default_index=1,
)


@register(key="test_mandala", display_name="Test_Mandala Bloom", order=91)
class TestMandala(BaseVisualizer):
    """A k-fold symmetric petal flower whose rings breathe with the spectrum."""

    OPTIONS = (_PRESET, SYMMETRY_OPTION, _LAYERS, _BLOOM, _PETAL, PALETTE_OPTION, _SPIN)
    PRESETS = {
        1: {"symmetry": 1, "layers": 1, "petal": 0, "palette": 6, "bloom": 0},  # Lotus (6-fold)
        2: {"symmetry": 3, "layers": 2, "petal": 3, "palette": 0, "bloom": 1},  # Sacred geometry
        3: {"symmetry": 3, "layers": 2, "petal": 1, "palette": 6, "bloom": 0, "spin": 2},  # Kaleido
    }

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._t = 0.0
        self._angle = 0.0
        self._pulse = 0.0

    def on_enter(self) -> None:
        self._t = self._angle = self._pulse = 0.0

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        cx, cy = w / 2.0, h / 2.0
        max_r = min(w, h) * _MAX_R * self.theme.size_scale
        level = 0.0 if frame is None or frame.is_silent else clamp(frame.rms * 2.0)
        onset = 0.0 if frame is None else frame.onset

        self._t += dt
        spin = float(self.option("spin")) * (0.4 if self.reduce_motion else 1.0)
        self._angle += dt * self.theme.speed_scale * spin * (0.15 + 0.25 * level)
        self._pulse = max(self._pulse - dt * 1.5, onset if onset >= ONSET_THRESHOLD else 0.0)

        layers = int(self.option("layers"))
        sym = int(self.option("symmetry"))
        energies = self._layer_energies(frame, layers)
        petal = _petal_outline(int(self.option("petal")))
        glow = pygame.Surface((w, h), pygame.SRCALPHA)

        for layer in range(layers - 1, -1, -1):  # outer first so the core sits on top
            self._draw_layer(
                surface,
                glow,
                cx,
                cy,
                max_r,
                layer,
                layers,
                sym,
                float(energies[layer]),
                petal,
                level,
            )
        self._draw_core(glow, cx, cy, max_r, level)
        surface.blit(glow, (0, 0), special_flags=pygame.BLEND_ADD)

    def _draw_layer(
        self,
        surface: pygame.Surface,
        glow: pygame.Surface,
        cx: float,
        cy: float,
        max_r: float,
        layer: int,
        layers: int,
        sym: int,
        energy: float,
        petal: list[tuple[float, float]],
        level: float,
    ) -> None:
        ring_step = max_r / layers
        inner_r = ring_step * layer * 0.7
        length = ring_step * 2.2 * self._bloom_factor(layer, layers, energy)
        if length < 2:
            return
        frac = (layer + 1) / layers
        color = palette_or_theme(
            int(self.option("palette")),
            self.theme.color_scheme,
            1.0 - frac * 0.85,
            self.theme.color_phase,
        )
        offset = self._angle + (layer * math.pi / sym)  # interleave alternate rings
        for k in range(sym):
            ang = offset + k * (math.tau / sym)
            pts = _place(petal, cx, cy, ang, inner_r, length)
            pygame.draw.polygon(surface, scale_color(color, 0.4), pts)
            pygame.draw.polygon(surface, scale_color(color, 1.0 + 0.4 * level), pts, 2)
            pygame.draw.polygon(glow, (*color, 55), pts)

    def _bloom_factor(self, layer: int, layers: int, energy: float) -> float:
        mode = int(self.option("bloom"))
        if mode == 1:  # Pulse: onset kicks every ring outward
            return 0.6 + 0.7 * energy + 0.6 * self._pulse
        if mode == 2:  # Unfold: outer rings grow in over the first second(s)
            grow = clamp(self._t * 0.8 * layers - layer)
            return (0.5 + 0.7 * energy) * grow
        breathe = 0.12 * math.sin(self._t * math.tau * 0.25 + layer * 0.7)  # Breathe
        return 0.75 + 0.7 * energy + breathe

    def _draw_core(
        self, glow: pygame.Surface, cx: float, cy: float, max_r: float, level: float
    ) -> None:
        """Warm additive halo at the heart of the bloom (brightest in the center)."""
        r = max(3, int(max_r * 0.06 * (0.8 + 0.6 * level)))
        for ring, alpha in ((4, 45), (3, 80), (2, 140), (1, 230)):
            pygame.draw.circle(glow, (*_CORE_HUE, alpha), (int(cx), int(cy)), r * ring)

    def _layer_energies(self, frame: AnalysisFrame | None, layers: int) -> np.ndarray:
        if frame is None or frame.band_energies.size == 0:
            return np.full(layers, 0.2, dtype=np.float32)
        return resample_to(frame.band_energies.astype(np.float32), layers)


def _petal_outline(shape: int) -> list[tuple[float, float]]:
    """Unit petal outline as ``(along 0..1, perp)`` points, tip at ``along=1``."""
    if shape == 3:  # geometric diamond
        return [(0.0, 0.0), (0.5, 0.32), (1.0, 0.0), (0.5, -0.32)]
    width, power = {0: (0.34, 0.7), 1: (0.14, 1.6), 2: (0.46, 0.5)}.get(shape, (0.34, 0.7))
    n = 12
    upper = [(a, width * math.sin(math.pi * a) ** power) for a in np.linspace(0.0, 1.0, n)]
    lower = [(a, -p) for a, p in reversed(upper)]
    return upper + lower


def _place(
    petal: list[tuple[float, float]],
    cx: float,
    cy: float,
    ang: float,
    inner_r: float,
    length: float,
) -> list[tuple[int, int]]:
    """Transform a unit petal to world space at angle ``ang`` and radius ``inner_r``."""
    ca, sa = math.cos(ang), math.sin(ang)
    out: list[tuple[int, int]] = []
    for a, p in petal:
        rr = inner_r + a * length
        pp = p * length
        x = cx + ca * rr - sa * pp
        y = cy + sa * rr + ca * pp
        out.append((int(x), int(y)))
    return out
