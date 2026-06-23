"""Harmonograph: a synthesized pen-plotter tracing damped Lissajous figures.

Band-driven oscillators sweep one (or several) "pens" through Lissajous/rosette curves
on a persistent phosphor surface that fades slowly, so the figure breathes and leaves
glowing trails. ``rms`` sets brightness, ``bass`` detunes the oscillators, and onsets
re-seed the phases for a fresh figure. Distinct from Vectorscope, which plots raw L/R.

Shipped under a ``Test_`` name during evaluation; remove the prefix once approved.
"""

from __future__ import annotations

import math

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import ONSET_THRESHOLD
from audio_visualizer.visuals._helpers import Color, clamp, rainbow_color, scale_color, themed_color
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_SPAN = 22.0  # parameter range swept per frame (smaller = more open figure)
_POINTS = 900  # samples along the figure
_FADE = {0: 26, 1: 10, 2: 4}  # persistence -> per-frame RGB subtract
_PEN_HUES = (0.55, 0.88, 0.12)  # cyan, magenta, gold

_PRESET = ModeOption(
    "preset",
    "Preset",
    (
        OptionChoice("Custom", 0),
        OptionChoice("Single Pen", 1),
        OptionChoice("Spirograph", 2),
        OptionChoice("Phosphor", 3),
    ),
    default_index=0,
)
_PENS = ModeOption(
    "pens",
    "Pens",
    (OptionChoice("1", 1), OptionChoice("2", 2), OptionChoice("3", 3)),
    default_index=1,
)
_PERSIST = ModeOption(
    "persist",
    "Persistence",
    (OptionChoice("Short", 0), OptionChoice("Long", 1), OptionChoice("Phosphor", 2)),
    default_index=1,
)
_DAMPING = ModeOption(
    "damping",
    "Damping",
    (OptionChoice("Tight", 0.4), OptionChoice("Loose", 0.9)),
    default_index=0,
)
_SYMMETRY = ModeOption(
    "hsym",
    "Symmetry",
    (OptionChoice("Off", 0), OptionChoice("Mirror", 1), OptionChoice("Radial", 2)),
    default_index=0,
)
_LINE = ModeOption(
    "line",
    "Line",
    (OptionChoice("Hairline", 0), OptionChoice("Glow", 1), OptionChoice("Ribbon", 2)),
    default_index=1,
)
_COLOR = ModeOption(
    "hcolor",
    "Color",
    (OptionChoice("Per-Pen", 0), OptionChoice("Theme", 1), OptionChoice("Rainbow", 2)),
    default_index=0,
)


@register(key="test_harmonograph", display_name="Test_Harmonograph", order=106)
class TestHarmonograph(BaseVisualizer):
    """Damped Lissajous pen plotter with phosphor persistence and symmetry."""

    OPTIONS = (_PRESET, _PENS, _PERSIST, _DAMPING, _SYMMETRY, _LINE, _COLOR)
    PRESETS = {
        1: {"pens": 0, "persist": 1, "damping": 0, "hsym": 0, "line": 1, "hcolor": 0},  # Single
        2: {"pens": 2, "persist": 1, "damping": 1, "hsym": 2, "line": 0, "hcolor": 0},  # Spirograph
        3: {"pens": 1, "persist": 2, "damping": 0, "hsym": 1, "line": 1, "hcolor": 2},  # Phosphor
    }

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._t = 0.0
        self._phase = np.zeros(0, dtype=np.float32)
        self._surface: pygame.Surface | None = None
        self._size: tuple[int, int] = (0, 0)
        self._rng = np.random.default_rng(50)

    def on_enter(self) -> None:
        self._t = 0.0
        self._surface = None
        self._reseed()

    def _reseed(self) -> None:
        self._phase = self._rng.uniform(0, 2 * math.pi, 12).astype(np.float32)

    def _ensure_surface(self, w: int, h: int) -> None:
        if self._surface is None or self._size != (w, h):
            self._surface = pygame.Surface((w, h))
            self._size = (w, h)

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        self._ensure_surface(w, h)
        assert self._surface is not None
        self._t += dt * self.theme.speed_scale

        bands = None if frame is None else frame.band_energies
        bass = 0.0 if bands is None or not bands.size else float(np.mean(bands[:8]))
        level = 0.0 if frame is None or frame.is_silent else clamp(frame.rms * 2.0)
        onset = 0.0 if frame is None else frame.onset
        if onset >= ONSET_THRESHOLD and not self.reduce_motion:
            self._reseed()

        fade = _FADE[int(self.option("persist"))]
        self._surface.fill((fade, fade, fade), special_flags=pygame.BLEND_RGB_SUB)

        cx, cy = w / 2.0, h / 2.0
        radius = min(w, h) * 0.42
        pens = int(self.option("pens"))
        for k in range(pens):
            pts = self._figure(k, bass, radius, cx, cy)
            self._draw_pen(self._surface, k, pts, cx, cy, level)
        surface.blit(self._surface, (0, 0))

    def _figure(self, k: int, bass: float, radius: float, cx: float, cy: float) -> np.ndarray:
        t = np.linspace(0.0, _SPAN, _POINTS, dtype=np.float32) + self._t * 0.04
        detune = 0.008 + 0.03 * bass
        w1 = float(self.option("damping"))
        ph = self._phase
        fx0, fx1, fy0, fy1 = 2 + k, 3 + k, 3 + k * 0.5, 2 + k
        x = np.sin(fx0 * t + ph[k * 4]) + w1 * np.sin((fx1 + detune) * t + ph[k * 4 + 1])
        y = np.sin(fy0 * t + ph[k * 4 + 2]) + w1 * np.sin((fy1 + detune) * t + ph[k * 4 + 3])
        scale = radius / (1.0 + w1)
        return np.stack([cx + x * scale, cy + y * scale], axis=1)

    def _draw_pen(
        self,
        target: pygame.Surface,
        k: int,
        pts: np.ndarray,
        cx: float,
        cy: float,
        level: float,
    ) -> None:
        color = self._pen_color(k, level)
        for poly in self._symmetry_copies(pts, cx, cy):
            ipts = [(int(px), int(py)) for px, py in poly]
            line = int(self.option("line"))
            if line == 2:  # ribbon
                pygame.draw.lines(target, color, False, ipts, 3)
            elif line == 1:  # glow: a dim wide pass under a bright thin pass
                pygame.draw.lines(target, scale_color(color, 0.4), False, ipts, 4)
                pygame.draw.aalines(target, color, False, ipts)
            else:  # hairline
                pygame.draw.aalines(target, color, False, ipts)

    def _symmetry_copies(self, pts: np.ndarray, cx: float, cy: float) -> list[np.ndarray]:
        mode = int(self.option("hsym"))
        if mode == 1:  # mirror about the vertical axis
            mirrored = pts.copy()
            mirrored[:, 0] = 2 * cx - mirrored[:, 0]
            return [pts, mirrored]
        if mode == 2:  # radial: rotated copies
            out = []
            for i in range(3):
                a = i * (2 * math.pi / 3)
                ca, sa = math.cos(a), math.sin(a)
                dx, dy = pts[:, 0] - cx, pts[:, 1] - cy
                rot = np.stack([cx + dx * ca - dy * sa, cy + dx * sa + dy * ca], axis=1)
                out.append(rot)
            return out
        return [pts]

    def _pen_color(self, k: int, level: float) -> Color:
        mode = int(self.option("hcolor"))
        bright = clamp(0.55 + 0.45 * level)
        if mode == 1:
            return scale_color(
                themed_color(
                    self.theme.color_scheme, k / 3.0, (rainbow_color(0.5),), self.theme.color_phase
                ),
                bright,
            )
        if mode == 2:
            return scale_color(rainbow_color((self._t * 0.05 + k * 0.33) % 1.0), bright)
        return scale_color(rainbow_color(_PEN_HUES[k % 3]), bright)
