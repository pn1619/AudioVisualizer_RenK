"""Spectrum mode: log-spaced frequency bars with falling peak caps."""

from __future__ import annotations

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import PALETTE
from audio_visualizer.visuals._helpers import themed_color
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_PEAK_FALL_PER_SEC = 0.6

_CAPS = ModeOption("caps", "Caps", (OptionChoice("On", 1), OptionChoice("Off", 0)), default_index=0)
_GAP = ModeOption(
    "gap",
    "Gap",
    (OptionChoice("Tight", 1), OptionChoice("Normal", 2), OptionChoice("Wide", 5)),
    default_index=1,
)


@register(key="spectrum", display_name="Spectrum", order=20)
class Spectrum(BaseVisualizer):
    """Vertical bars, one per log-spaced band, with peak-hold caps."""

    OPTIONS = (_CAPS, _GAP)

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._peaks: np.ndarray | None = None

    def on_enter(self) -> None:
        self._peaks = None

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if frame is None:
            return

        bands = frame.band_energies
        count = bands.size
        if count == 0 or w < 2:
            return

        if self._peaks is None or self._peaks.size != count:
            self._peaks = np.zeros(count, dtype=np.float32)
        self._peaks = np.maximum(self._peaks - _PEAK_FALL_PER_SEC * dt, bands)

        scheme = self.theme.color_scheme
        phase = self.theme.color_phase
        show_caps = self.option("caps") >= 1
        gap = int(self.option("gap"))
        bar_w = max(1.0, (w - gap * (count + 1)) / count)
        for i in range(count):
            x = gap + i * (bar_w + gap)
            energy = float(bands[i])
            bar_h = energy * (h - 4)
            color = themed_color(scheme, i / max(1, count - 1), PALETTE, phase)
            if bar_h >= 1:
                pygame.draw.rect(surface, color, (x, h - bar_h, bar_w, bar_h))
            if show_caps:
                cap_y = h - float(self._peaks[i]) * (h - 4)
                pygame.draw.rect(surface, (235, 235, 245), (x, cap_y, bar_w, 2))
