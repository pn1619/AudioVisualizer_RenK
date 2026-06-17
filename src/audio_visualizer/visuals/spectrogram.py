"""Spectrogram mode: a scrolling frequency heatmap (waterfall).

Frequency runs bottom (low) to top (high); time scrolls right-to-left. Each frame
appends a fresh column built from ``band_energies`` and shifts the history left.
To make it lively: pick a heat palette (Neon/Fire/Ice), optionally **mirror** it into
a center-out "butterfly" (bass in the middle), beats brighten the whole column
(``peak``), and the newest "now" column glows as a bright leading edge.
"""

from __future__ import annotations

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.visuals._helpers import resample_to
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

# Heat ramps (equal stops 0..1), each dark floor -> hot white peak.
_HEATS: dict[int, np.ndarray] = {
    0: np.array(  # neon
        [(8, 6, 18), (150, 30, 150), (70, 110, 255), (70, 230, 255), (255, 255, 255)], np.float32
    ),
    1: np.array(  # fire
        [(4, 2, 0), (120, 20, 0), (235, 90, 0), (255, 200, 45), (255, 255, 215)], np.float32
    ),
    2: np.array(  # ice
        [(2, 6, 20), (10, 60, 120), (40, 145, 210), (150, 220, 245), (255, 255, 255)], np.float32
    ),
}
_GAMMA = 0.6  # < 1 lifts quiet detail so the floor isn't a dead black wall
_BEAT_BOOST = 0.9  # how much a full-peak beat brightens/raises the column

_SPEED = ModeOption(
    "speed",
    "Scroll",
    (OptionChoice("Slow", 1), OptionChoice("Normal", 2), OptionChoice("Fast", 4)),
    default_index=1,
)
_HEAT = ModeOption(
    "heat",
    "Heat",
    (OptionChoice("Neon", 0), OptionChoice("Fire", 1), OptionChoice("Ice", 2)),
    default_index=0,
)
_MIRROR = ModeOption(
    "mirror",
    "Layout",
    (OptionChoice("Up", 0), OptionChoice("Butterfly", 1)),
    default_index=1,
)


@register(key="spectrogram", display_name="Spectrogram", order=25)
class Spectrogram(BaseVisualizer):
    """A scrolling magnitude heatmap of the log-spaced spectrum."""

    OPTIONS = (_SPEED, _HEAT, _MIRROR)

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._surf: pygame.Surface | None = None
        self._size: tuple[int, int] | None = None

    def on_enter(self) -> None:
        self._surf = None

    def on_resize(self, size: tuple[int, int]) -> None:
        self._surf = None

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 4 or h < 4:
            return
        if self._surf is None or self._size != (w, h):
            self._surf = pygame.Surface((w, h))
            self._size = (w, h)

        step = max(1, int(self.option("speed")))
        self._surf.scroll(-step, 0)  # shift history left; the right strip is overwritten
        column = self._build_column(frame, h)  # (h, 3), row 0 = top
        strip = np.repeat(column[np.newaxis, :, :], step, axis=0)  # (step, h, 3) for surfarray
        pygame.surfarray.blit_array(self._surf.subsurface((w - step, 0, step, h)), strip)
        surface.blit(self._surf, (0, 0))
        self._leading_edge(surface, column, w, h)

    def _build_column(self, frame: AnalysisFrame | None, h: int) -> np.ndarray:
        heat = _HEATS[int(self.option("heat"))]
        butterfly = int(self.option("mirror")) == 1
        rows_n = h // 2 if butterfly else h
        if frame is None or frame.band_energies.size == 0:
            mags = np.zeros(rows_n, dtype=np.float32)
        else:
            mags = resample_to(frame.band_energies.astype(np.float32), rows_n)
            boost = 1.0 + _BEAT_BOOST * float(frame.peak)
            mags = np.clip(mags * boost, 0.0, 1.0)
        mags = mags**_GAMMA
        colors = _heat(mags, heat)  # row 0 = low frequency
        if butterfly:  # low in the center, high toward both edges
            top = colors[::-1]
            bottom = colors
            col = np.concatenate([top, bottom])
            if col.shape[0] < h:  # pad odd heights
                col = np.concatenate([col, col[-1:]])
            return col[:h]
        return colors[::-1]  # low frequency at the bottom

    def _leading_edge(self, surface: pygame.Surface, column: np.ndarray, w: int, h: int) -> None:
        """Draw the newest column extra-bright at the right edge as a glowing 'now' line."""
        bright = np.clip(column.astype(np.uint16) + 60, 0, 255).astype(np.uint8)
        edge = np.repeat(bright[np.newaxis, :, :], 2, axis=0)
        x = max(0, w - 2)
        pygame.surfarray.blit_array(surface.subsurface((x, 0, 2, h)), edge)


def _heat(values: np.ndarray, ramp: np.ndarray) -> np.ndarray:
    """Map intensities in 0..1 to the heat ramp -> (N, 3) uint8."""
    stops = np.linspace(0.0, 1.0, ramp.shape[0])
    out = np.empty((values.shape[0], 3), dtype=np.float32)
    for c in range(3):
        out[:, c] = np.interp(values, stops, ramp[:, c])
    return out.astype(np.uint8)
