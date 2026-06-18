"""Synthwave Horizon: the spectrum as scrolling neon mountains over a retro sun.

A cached sky gradient + retro sun sit behind one to three parallax mountain ridges
built from a scrolling height-field that the music keeps feeding (bass drives the
front ridge, highs the far ones). An optional perspective grid floor or a mirrored
reflection fills the foreground. Cheap: a few filled polygons + cached gradients.
"""

from __future__ import annotations

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.visuals._helpers import SPEED_OPTION, lerp_color, scale_color
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_POINTS = 160  # ridge resolution (sampled across the width)
_HORIZON = 0.60  # horizon line as a fraction of the canvas height
_SCROLL_PTS_PER_SEC = 14.0  # height-field columns added per second (× Speed × theme)

# Palette: (sky_top, sky_horizon, ground, ridge, sun_hi, sun_lo).
_Palette = tuple[tuple[int, int, int], ...]
_PALETTES: dict[int, _Palette] = {
    0: (
        (12, 6, 40),
        (90, 20, 90),
        (8, 4, 20),
        (255, 60, 180),
        (255, 230, 80),
        (255, 60, 140),
    ),  # sunset
    1: (
        (4, 14, 40),
        (20, 70, 120),
        (4, 10, 24),
        (80, 220, 255),
        (200, 255, 255),
        (60, 170, 255),
    ),  # ice
    2: (
        (6, 10, 16),
        (30, 40, 50),
        (4, 6, 10),
        (90, 230, 160),
        (220, 255, 230),
        (60, 200, 150),
    ),  # mono
}

_LAYERS = ModeOption(
    "layers",
    "Layers",
    (OptionChoice("1", 1), OptionChoice("2", 2), OptionChoice("3", 3)),
    default_index=2,
)
_FILL = ModeOption(
    "fill",
    "Fill",
    (OptionChoice("Solid", 0), OptionChoice("Gradient", 1), OptionChoice("Wire", 2)),
    default_index=0,
)
_SUN = ModeOption("sun", "Sun", (OptionChoice("On", 1), OptionChoice("Off", 0)), default_index=0)
_FLOOR = ModeOption(
    "floor",
    "Floor",
    (OptionChoice("Grid", 0), OptionChoice("Mirror", 1), OptionChoice("Off", 2)),
    default_index=0,
)
_PALETTE = ModeOption(
    "palette",
    "Palette",
    (OptionChoice("Sunset", 0), OptionChoice("Ice", 1), OptionChoice("Mono", 2)),
    default_index=0,
)
_PEAKS = ModeOption(
    "peaks", "Caps", (OptionChoice("Off", 0), OptionChoice("On", 1)), default_index=0
)


@register(key="terrain", display_name="Synthwave Horizon", order=100)
class Terrain(BaseVisualizer):
    """Scrolling neon mountains + retro sun + grid floor, driven by the spectrum."""

    OPTIONS = (_LAYERS, _FILL, _SUN, _FLOOR, SPEED_OPTION, _PALETTE, _PEAKS)

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._fields = [np.zeros(_POINTS, dtype=np.float32) for _ in range(3)]
        self._scroll = 0.0
        self._grid_phase = 0.0
        self._sky: pygame.Surface | None = None
        self._sky_key: tuple[int, int, int] | None = None
        self._sun: pygame.Surface | None = None
        self._sun_key: tuple[int, int] | None = None

    def on_enter(self) -> None:
        for f in self._fields:
            f.fill(0.0)
        self._scroll = 0.0
        self._grid_phase = 0.0

    def on_resize(self, size: tuple[int, int]) -> None:
        self._sky = None
        self._sun = None

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        pal = _PALETTES[int(self.option("palette"))]
        horizon = int(h * _HORIZON)

        self._advance(frame, dt)
        self._blit_sky(surface, w, h, horizon, pal)
        if int(self.option("sun")) == 1:
            self._blit_sun(surface, w, horizon, pal)

        layers = int(self.option("layers"))
        fill = int(self.option("fill"))
        for layer in range(layers - 1, -1, -1):  # far -> near
            self._draw_ridge(surface, w, h, horizon, layer, layers, fill, pal)

        floor = int(self.option("floor"))
        if floor == 0:
            self._draw_grid(surface, w, h, horizon, pal)
        elif floor == 1:
            self._reflect(surface, w, h, horizon)

    def _advance(self, frame: AnalysisFrame | None, dt: float) -> None:
        rate = self.option("rate") * (0.5 if self.reduce_motion else 1.0)
        self._scroll += dt * self.theme.speed_scale * rate * _SCROLL_PTS_PER_SEC
        self._grid_phase = (self._grid_phase + dt * self.theme.speed_scale * rate * 0.3) % 1.0
        steps = int(self._scroll)
        if steps <= 0:
            return
        self._scroll -= steps
        bands = None if frame is None else frame.band_energies
        for layer, field in enumerate(self._fields):
            new = self._sample_band(bands, layer)
            shifted = np.roll(field, -steps)
            shifted[-steps:] = new
            self._fields[layer] = shifted

    @staticmethod
    def _sample_band(bands: np.ndarray | None, layer: int) -> float:
        if bands is None or bands.size == 0:
            return 0.0
        n = bands.size
        lo, hi = [(0, n // 3), (n // 3, 2 * n // 3), (2 * n // 3, n)][layer]
        return float(np.mean(bands[lo:hi]) ** 0.8)

    def _draw_ridge(
        self,
        surface: pygame.Surface,
        w: int,
        h: int,
        horizon: int,
        layer: int,
        layers: int,
        fill: int,
        pal: _Palette,
    ) -> None:
        depth = 1.0 - layer / max(1, layers)  # 1 (front) .. smaller (back)
        amp = horizon * (0.28 + 0.32 * depth)
        field = self._fields[layer]
        xs = np.linspace(0, w, _POINTS)
        ys = horizon - field * amp
        ridge = [(float(x), float(y)) for x, y in zip(xs, ys, strict=False)]
        color = scale_color(pal[3], 0.35 + 0.65 * depth)
        if fill == 2:  # wireframe
            pygame.draw.lines(surface, color, False, ridge, max(1, int(2 * depth) + 1))
        else:
            poly = [*ridge, (w, h), (0, h)]
            pygame.draw.polygon(surface, scale_color(color, 0.5 if fill == 1 else 1.0), poly)
            if fill == 1:  # gradient look: bright ridge crest line on top of the dim fill
                pygame.draw.lines(surface, color, False, ridge, 2)
        if int(self.option("peaks")) == 1 and layer == 0:
            self._draw_caps(surface, ridge, field)

    @staticmethod
    def _draw_caps(
        surface: pygame.Surface, ridge: list[tuple[float, float]], field: np.ndarray
    ) -> None:
        for (x, y), e in zip(ridge, field, strict=False):
            if e > 0.6:
                pygame.draw.circle(surface, (245, 245, 255), (int(x), int(y)), 2)

    def _draw_grid(
        self, surface: pygame.Surface, w: int, h: int, horizon: int, pal: _Palette
    ) -> None:
        color = scale_color(pal[3], 0.6)
        vp = (w // 2, horizon)
        for i in range(-6, 7):  # verticals converging to the vanishing point
            x = w // 2 + i * (w // 12)
            pygame.draw.line(surface, color, (x, h), vp, 1)
        depth = h - horizon
        for k in range(1, 12):  # horizontals, denser toward the horizon, scrolling forward
            frac = ((k + self._grid_phase) / 12.0) ** 2.2
            y = horizon + int(frac * depth)
            pygame.draw.line(surface, color, (0, y), (w, y), 1)

    @staticmethod
    def _reflect(surface: pygame.Surface, w: int, h: int, horizon: int) -> None:
        strip_h = min(horizon, h - horizon)
        if strip_h < 2:
            return
        top = surface.subsurface((0, horizon - strip_h, w, strip_h)).copy()
        flipped = pygame.transform.flip(top, False, True)
        flipped.set_alpha(90)
        surface.blit(flipped, (0, horizon))

    def _blit_sky(
        self, surface: pygame.Surface, w: int, h: int, horizon: int, pal: _Palette
    ) -> None:
        key = (w, h, int(self.option("palette")))
        if self._sky is None or self._sky_key != key:
            sky = pygame.Surface((w, h))
            for y in range(horizon):  # vertical gradient: sky_top -> sky_horizon
                sky_c = lerp_color(pal[0], pal[1], y / max(1, horizon))
                pygame.draw.line(sky, sky_c, (0, y), (w, y))
            sky.fill(pal[2], (0, horizon, w, h - horizon))  # ground
            self._sky = sky
            self._sky_key = key
        surface.blit(self._sky, (0, 0))

    def _blit_sun(self, surface: pygame.Surface, w: int, horizon: int, pal: _Palette) -> None:
        r = max(8, int(min(w, horizon) * 0.28))
        key = (r, int(self.option("palette")))
        if self._sun is None or self._sun_key != key:
            size = r * 2
            sun = pygame.Surface((size, size), pygame.SRCALPHA)
            for y in range(size):  # vertical gradient disc
                col = lerp_color(pal[4], pal[5], y / size)
                pygame.draw.line(sun, col, (0, y), (size, y))
            mask = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.circle(mask, (255, 255, 255, 255), (r, r), r)
            sun.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            for i in range(1, 7):  # retro horizontal slits across the lower half
                y = r + int(i * r / 7)
                pygame.draw.line(sun, (0, 0, 0, 0), (0, y), (size, y), max(1, r // 14))
            self._sun = sun
            self._sun_key = key
        surface.blit(self._sun, (w // 2 - r, horizon - int(r * 1.35)))
