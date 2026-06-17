"""Plasma / Liquid: a flowing color field driven by bass.

A classic sine-interference plasma evaluated on a small grid (then upscaled, so it
stays cheap), colored by sampling the palette and rolled over time. Bass energy adds
turbulence and speeds the flow, giving a lava-lamp / liquid feel. Calm, ambient,
idle-friendly; not a strobe.
"""

from __future__ import annotations

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import PALETTE
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_GRID_W = 200  # field is computed at this width then smoothscaled to the canvas
_FLOW_RATE = 0.4  # base time advance per second (scaled by speed)
_BASS_TURBULENCE = 2.5  # extra spatial frequency added by bass energy

_PALETTE = ModeOption(
    "palette", "Tint", (OptionChoice("Neon", 0), OptionChoice("Rainbow", 1)), default_index=0
)


@register(key="plasma", display_name="Plasma", order=80)
class Plasma(BaseVisualizer):
    """A bass-reactive sine-interference plasma field."""

    OPTIONS = (_PALETTE,)

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._t = 0.0
        self._grid: tuple[int, int] | None = None
        self._xx: np.ndarray | None = None
        self._yy: np.ndarray | None = None

    def on_enter(self) -> None:
        self._t = 0.0

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
        self._ensure_grid(w, h)
        assert self._xx is not None and self._yy is not None

        bass = 0.0 if frame is None or frame.is_silent else float(np.mean(frame.band_energies[:8]))
        speed = self.theme.speed_scale * (0.4 if self.reduce_motion else 1.0)
        self._t += dt * speed * _FLOW_RATE * (1.0 + bass)

        field = self._field(self._xx, self._yy, self._t, bass)
        rgb = self._colorize(field)  # (gh, gw, 3)
        small = pygame.surfarray.make_surface(np.transpose(rgb, (1, 0, 2)))
        scaled = pygame.transform.smoothscale(small, (w, h))
        surface.blit(scaled, (0, 0))

    def _field(self, xx: np.ndarray, yy: np.ndarray, t: float, bass: float) -> np.ndarray:
        turb = 1.0 + bass * _BASS_TURBULENCE
        v = (
            np.sin((xx * 6.0 + t) * turb)
            + np.sin(yy * 7.0 - t * 1.2)
            + np.sin((xx + yy) * 5.0 * turb + t * 0.7)
            + np.sin(np.hypot(xx - 0.5, yy - 0.5) * 14.0 - t * 1.5)
        )
        return (v / 4.0 + 0.5) % 1.0  # normalize to 0..1 and wrap for a seamless cycle

    def _colorize(self, field: np.ndarray) -> np.ndarray:
        rolled = (field + self.theme.color_phase) % 1.0
        if self.option("palette") >= 1 or self.theme.color_scheme != "classic":
            return _hsv_to_rgb(rolled)
        return _palette_lookup(rolled, PALETTE)


def _palette_lookup(values: np.ndarray, palette: tuple[tuple[int, int, int], ...]) -> np.ndarray:
    """Sample a cyclic palette across ``values`` (0..1) -> (..., 3) uint8."""
    cyc = np.array([*palette, palette[0]], dtype=np.float32)
    stops = np.linspace(0.0, 1.0, cyc.shape[0])
    out = np.empty((*values.shape, 3), dtype=np.float32)
    for c in range(3):
        out[..., c] = np.interp(values, stops, cyc[:, c])
    return out.astype(np.uint8)


def _hsv_to_rgb(hue: np.ndarray) -> np.ndarray:
    """Vectorized full-saturation HSV->RGB for a hue array in 0..1 -> (..., 3) uint8."""
    i = (hue * 6.0).astype(np.int32) % 6
    f = (hue * 6.0) - np.floor(hue * 6.0)
    q = 1.0 - f
    out = np.zeros((*hue.shape, 3), dtype=np.float32)
    out[..., 0] = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5], [1, q, 0, 0, f, 1])
    out[..., 1] = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5], [f, 1, 1, q, 0, 0])
    out[..., 2] = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5], [0, 0, f, 1, 1, q])
    return (out * 255.0).astype(np.uint8)
