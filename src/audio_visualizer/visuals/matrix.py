"""Dot-Matrix: a retro LED panel that lights from the spectrum.

In Columns mode each grid column is a frequency group lighting bottom-up like a
graphic equalizer; in Scroll mode the panel scrolls a dot-resolution spectrogram.
Dots can be round, square, or diamond, colored by a heat ramp, a per-column hue,
or a solid accent, with optional peak-hold caps and a soft additive glow.
"""

from __future__ import annotations

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import COLOR_ACCENT, PALETTE
from audio_visualizer.visuals._helpers import (
    GLOW_OPTION,
    palette_color,
    range_energies,
    resample_to,
    scale_color,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_SCROLL_STEPS_PER_SEC = 18.0  # columns advanced per second in Scroll mode

_GRID = ModeOption(
    "grid",
    "Grid",
    (OptionChoice("24x12", 24), OptionChoice("32x16", 32), OptionChoice("48x24", 48)),
    default_index=1,
)
_DOT = ModeOption(
    "dot",
    "Dot",
    (OptionChoice("Round", 0), OptionChoice("Square", 1), OptionChoice("Diamond", 2)),
    default_index=0,
)
_GAP = ModeOption(
    "gap",
    "Gap",
    (OptionChoice("Tight", 0.92), OptionChoice("Normal", 0.72), OptionChoice("Wide", 0.52)),
    default_index=1,
)
_LIT = ModeOption(
    "lit",
    "Color",
    (OptionChoice("Heat", 0), OptionChoice("Per-col", 1), OptionChoice("Solid", 2)),
    default_index=0,
)
_MODE = ModeOption(
    "mode",
    "Mode",
    (OptionChoice("Columns", 0), OptionChoice("Scroll", 1)),
    default_index=0,
)
_PEAK = ModeOption("peak", "Peak", (OptionChoice("On", 1), OptionChoice("Off", 0)), default_index=0)

# Heat ramp: dark -> deep red -> orange -> yellow -> white.
_HEAT = ((10, 0, 30), (170, 25, 40), (240, 120, 30), (250, 220, 80), (255, 255, 255))


@register(key="matrix", display_name="Dot Matrix", order=115)
class Matrix(BaseVisualizer):
    """LED dot panel: columns equalizer or scrolling dot-spectrogram."""

    OPTIONS = (_GRID, _DOT, _GAP, _LIT, _MODE, _PEAK, GLOW_OPTION)

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._cols = 0
        self._rows = 0
        self._field = np.zeros((0, 0), dtype=np.float32)  # [rows, cols] intensities
        self._peaks = np.zeros(0, dtype=np.float32)
        self._scroll = 0.0

    def on_enter(self) -> None:
        self._field = np.zeros((0, 0), dtype=np.float32)
        self._peaks = np.zeros(0, dtype=np.float32)
        self._scroll = 0.0

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        cols = int(self.option("grid"))
        rows = cols // 2
        self._ensure_grid(cols, rows)
        if int(self.option("mode")) == 0:
            self._update_columns(frame, dt)
        else:
            self._update_scroll(frame, dt)
        self._render(surface, w, h)

    def _ensure_grid(self, cols: int, rows: int) -> None:
        if self._cols != cols or self._rows != rows:
            self._cols, self._rows = cols, rows
            self._field = np.zeros((rows, cols), dtype=np.float32)
            self._peaks = np.zeros(cols, dtype=np.float32)

    def _update_columns(self, frame: AnalysisFrame | None, dt: float) -> None:
        if frame is None or frame.band_energies.size == 0:
            levels = np.zeros(self._cols, dtype=np.float32)
        else:
            levels = np.clip(range_energies(frame.band_energies, self._cols), 0.0, 1.0)
        # Build a [rows, cols] lit field: row r (from bottom) lit if level reaches it.
        thresh = (np.arange(self._rows)[::-1] + 1.0) / self._rows
        self._field = (levels[None, :] >= thresh[:, None]).astype(np.float32) * levels[None, :]
        self._peaks = np.maximum(levels, self._peaks - 0.5 * max(dt, 1e-3))

    def _update_scroll(self, frame: AnalysisFrame | None, dt: float) -> None:
        rate = 0.4 if self.reduce_motion else 1.0
        self._scroll += dt * self.theme.speed_scale * rate * _SCROLL_STEPS_PER_SEC
        steps = int(self._scroll)
        if steps <= 0:
            return
        self._scroll -= steps
        steps = min(steps, self._cols)
        if frame is None or frame.band_energies.size == 0:
            col = np.zeros(self._rows, dtype=np.float32)
        else:
            col = np.clip(resample_to(frame.band_energies, self._rows)[::-1], 0.0, 1.0)
        self._field = np.roll(self._field, -steps, axis=1)
        self._field[:, -steps:] = col[:, None]

    def _render(self, surface: pygame.Surface, w: int, h: int) -> None:
        cell_w = w / self._cols
        cell_h = h / self._rows
        radius = max(1, int(min(cell_w, cell_h) * float(self.option("gap")) * 0.5))
        dot = int(self.option("dot"))
        lit_mode = int(self.option("lit"))
        glow = int(self.option("glow")) == 1
        scroll_mode = int(self.option("mode")) == 1
        for r in range(self._rows):
            cy = int((r + 0.5) * cell_h)
            for c in range(self._cols):
                intensity = float(self._field[r, c])
                if intensity <= 0.02:
                    continue
                cx = int((c + 0.5) * cell_w)
                color = self._dot_color(lit_mode, intensity, c, scroll_mode, r)
                if glow:
                    self._blit_glow(surface, cx, cy, radius, color)
                self._draw_dot(surface, dot, cx, cy, radius, color)
        if int(self.option("peak")) == 1 and not scroll_mode:
            self._draw_peaks(surface, cell_w, cell_h, radius, dot)

    def _dot_color(
        self, lit_mode: int, intensity: float, c: int, scroll_mode: bool, r: int
    ) -> tuple[int, int, int]:
        if lit_mode == 0:
            return palette_color(_HEAT, intensity)
        if lit_mode == 1:
            base = palette_color(PALETTE, c / max(1, self._cols - 1))
            return scale_color(base, 0.4 + 0.6 * intensity)
        return scale_color(COLOR_ACCENT, 0.4 + 0.6 * intensity)

    @staticmethod
    def _draw_dot(
        surface: pygame.Surface,
        dot: int,
        cx: int,
        cy: int,
        radius: int,
        color: tuple[int, int, int],
    ) -> None:
        if dot == 1:
            pygame.draw.rect(surface, color, (cx - radius, cy - radius, radius * 2, radius * 2))
        elif dot == 2:
            pygame.draw.polygon(
                surface,
                color,
                [(cx, cy - radius), (cx + radius, cy), (cx, cy + radius), (cx - radius, cy)],
            )
        else:
            pygame.draw.circle(surface, color, (cx, cy), radius)

    @staticmethod
    def _blit_glow(
        surface: pygame.Surface, cx: int, cy: int, radius: int, color: tuple[int, int, int]
    ) -> None:
        gr = radius * 2
        glow = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*color, 70), (gr, gr), gr)
        surface.blit(glow, (cx - gr, cy - gr), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_peaks(
        self, surface: pygame.Surface, cell_w: float, cell_h: float, radius: int, dot: int
    ) -> None:
        for c in range(self._cols):
            peak = float(self._peaks[c])
            if peak <= 0.02:
                continue
            r = int(round(peak * self._rows))
            r = min(self._rows - 1, self._rows - r)
            cx = int((c + 0.5) * cell_w)
            cy = int((r + 0.5) * cell_h)
            self._draw_dot(surface, dot, cx, cy, radius, (255, 255, 255))
