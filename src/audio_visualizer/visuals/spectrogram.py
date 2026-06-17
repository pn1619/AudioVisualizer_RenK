"""Spectrogram mode: a scrolling frequency heatmap (waterfall).

Frequency runs bottom (low) to top (high); time scrolls right-to-left. Each frame
appends one fresh column built from ``band_energies`` and shifts the history left,
so the screen reads like a real spectrogram. Magnitude maps through an intensity
heat ramp (dark → magenta → blue → cyan → white), independent of the color scheme
because a spectrogram's color *is* its data.
"""

from __future__ import annotations

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.visuals._helpers import resample_to
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

# Intensity heat ramp (equal stops 0..1): dark navy → magenta → blue → cyan → white.
_HEAT: np.ndarray = np.array(
    [(8, 6, 18), (150, 30, 150), (70, 110, 255), (70, 230, 255), (255, 255, 255)],
    dtype=np.float32,
)
# Gamma < 1 lifts quiet detail so the floor isn't a dead black wall.
_GAMMA = 0.6

_SPEED = ModeOption(
    "speed",
    "Scroll",
    (OptionChoice("Slow", 1), OptionChoice("Normal", 2), OptionChoice("Fast", 4)),
    default_index=1,
)


@register(key="spectrogram", display_name="Spectrogram", order=25)
class Spectrogram(BaseVisualizer):
    """A scrolling magnitude heatmap of the log-spaced spectrum."""

    OPTIONS = (_SPEED,)

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
        column = self._build_column(frame, h)  # (h, 3), row 0 = top = high freq
        strip = np.repeat(column[np.newaxis, :, :], step, axis=0)  # (step, h, 3) for surfarray
        pygame.surfarray.blit_array(self._surf.subsurface((w - step, 0, step, h)), strip)
        surface.blit(self._surf, (0, 0))

    def _build_column(self, frame: AnalysisFrame | None, h: int) -> np.ndarray:
        if frame is None or frame.band_energies.size == 0:
            rows = np.zeros(h, dtype=np.float32)
        else:
            rows = resample_to(frame.band_energies.astype(np.float32), h)
        rows = np.clip(rows, 0.0, 1.0) ** _GAMMA
        rows = rows[::-1]  # put low frequencies at the bottom of the column
        return _heat(rows)


def _heat(values: np.ndarray) -> np.ndarray:
    """Map intensities in 0..1 to the heat ramp -> (N, 3) uint8."""
    stops = np.linspace(0.0, 1.0, _HEAT.shape[0])
    out = np.empty((values.shape[0], 3), dtype=np.float32)
    for c in range(3):
        out[:, c] = np.interp(values, stops, _HEAT[:, c])
    return out.astype(np.uint8)
