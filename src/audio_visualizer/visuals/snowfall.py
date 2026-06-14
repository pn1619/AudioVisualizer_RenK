"""Snowfall mode: colorful flakes drifting down; bass blows the wind, mids size.

- **Wind** (horizontal drift) is driven by **low-frequency** energy: loud bass
  blows the snow sideways, quiet bass lets it fall straight (the wind also sways
  direction slowly over time).
- **Flake size** grows with a **mid-band** energy, so flakes swell with the music.
"""

from __future__ import annotations

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import (
    PALETTE,
    SNOW_FLAKES,
    SNOW_FLAKES_REDUCED,
    SNOW_SIZE_SCALE,
    SNOW_WIND_SCALE,
    SNOW_WIND_SCALE_REDUCED,
)
from audio_visualizer.visuals._helpers import scale_color, themed_color
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice
from audio_visualizer.visuals.registry import register

_FALL_SPEED = ModeOption(
    "fall_speed",
    "Fall",
    (OptionChoice("Slow", 0.5), OptionChoice("Normal", 1.0), OptionChoice("Fast", 2.0)),
    default_index=1,
)
_WIND_SPEED = ModeOption(
    "wind_speed",
    "Wind",
    (OptionChoice("Calm", 0.0), OptionChoice("Breezy", 1.0), OptionChoice("Windy", 2.5)),
    default_index=1,
)
_DENSITY = ModeOption(
    "density",
    "Density",
    (
        OptionChoice("Low", SNOW_FLAKES_REDUCED),
        OptionChoice("Medium", SNOW_FLAKES),
        OptionChoice("High", 360),
    ),
    default_index=1,
)


@register(key="snowfall", display_name="Snowfall", order=60)
class Snowfall(BaseVisualizer):
    """A resolution-independent flake field; calm and idle-friendly.

    Fall speed and wind speed are independent per-mode options (both still
    scaled by the global speed control); density picks the flake count.
    """

    OPTIONS = (_FALL_SPEED, _WIND_SPEED, _DENSITY)

    def __init__(self, reduce_motion: bool = False, seed: int = 2024) -> None:
        super().__init__(reduce_motion)
        self._seed = seed
        self._t = 0.0
        self._init_pool()

    @property
    def _count(self) -> int:
        base = int(self.option("density"))
        return min(base, SNOW_FLAKES_REDUCED) if self.reduce_motion else base

    def _init_pool(self) -> None:
        rng = np.random.default_rng(self._seed)
        n = self._count
        self._x = rng.random(n).astype(np.float32)
        self._y = rng.random(n).astype(np.float32)
        self._size = rng.uniform(0.003, 0.010, n).astype(np.float32)  # fraction of min side
        self._hue = rng.random(n).astype(np.float32)
        self._fall = rng.uniform(0.05, 0.18, n).astype(np.float32)  # per second
        self._sway = rng.uniform(0.01, 0.05, n).astype(np.float32)
        self._phase = rng.uniform(0.0, 2.0 * np.pi, n).astype(np.float32)

    def on_enter(self) -> None:
        self._t = 0.0
        self._init_pool()

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 2 or h < 2:
            return
        # Rebuild the pool if density (or reduce-motion) changed the flake count.
        if self._x.size != self._count:
            self._init_pool()
        self._t += dt

        fall_speed = self.option("fall_speed")
        wind_speed = self.option("wind_speed")
        low, size_energy = self._band_drivers(frame)
        wind_scale = SNOW_WIND_SCALE_REDUCED if self.reduce_motion else SNOW_WIND_SCALE
        wind = low * wind_scale * float(np.sin(self._t * 0.3)) * wind_speed

        move_dt = dt * self.theme.speed_scale
        self._y += self._fall * fall_speed * move_dt
        self._x += (wind + self._sway * wind_speed * np.sin(self._t * 1.5 + self._phase)) * move_dt
        self._y = np.where(self._y > 1.0, self._y - 1.0, self._y)
        self._x = np.mod(self._x, 1.0)

        scheme = self.theme.color_scheme
        phase = self.theme.color_phase
        min_side = min(w, h)
        radii = (
            self._size * min_side * (1.0 + size_energy * SNOW_SIZE_SCALE) * self.theme.size_scale
        )
        for i in range(self._x.size):
            radius = max(1, int(radii[i]))
            color = scale_color(themed_color(scheme, float(self._hue[i]), PALETTE, phase), 0.85)
            pygame.draw.circle(surface, color, (int(self._x[i] * w), int(self._y[i] * h)), radius)

    @staticmethod
    def _band_drivers(frame: AnalysisFrame | None) -> tuple[float, float]:
        """Return (low-band energy for wind, mid-band energy for size)."""
        if frame is None or frame.is_silent:
            return 0.0, 0.0
        bands = frame.band_energies
        if bands.size == 0:
            return 0.0, 0.0
        low = float(bands[: max(1, bands.size // 12)].mean())
        lo, hi = bands.size // 3, 2 * bands.size // 3
        size_energy = float(bands[lo:hi].mean()) if hi > lo else 0.0
        return low, size_energy
