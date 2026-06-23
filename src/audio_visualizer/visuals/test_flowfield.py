"""Flow Field: particles streaming along a curl-noise field, bent by the audio.

A few thousand particles sample an analytic vector field and integrate their motion,
leaving silky trails on a persistent (slowly fading) surface. ``rms`` sets flow speed,
``bass`` adds turbulence, and an onset can inject a transient vortex. Colors follow a
blue→purple→magenta ramp by velocity, angle, or the theme.

Shipped under a ``Test_`` name during evaluation; remove the prefix once approved.
"""

from __future__ import annotations

import math

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import ONSET_THRESHOLD
from audio_visualizer.visuals._helpers import (
    SPEED_OPTION,
    TRAIL_OPTION,
    clamp,
    palette_color,
    themed_color,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_COUNTS = {0: 800, 1: 1500, 2: 2400}
_FLOW_PALETTE = ((40, 90, 220), (110, 70, 230), (190, 60, 220), (240, 60, 150), (255, 120, 110))
_BASE_SPEED = 0.13  # normalized units/sec at unit speed
_FADE = (4, 4, 5)  # per-frame RGB subtracted from the trail surface (lower = longer trails)

_PRESET = ModeOption(
    "preset",
    "Preset",
    (
        OptionChoice("Custom", 0),
        OptionChoice("Silk", 1),
        OptionChoice("Storm", 2),
        OptionChoice("Vortex", 3),
    ),
    default_index=0,
)
_PARTICLES = ModeOption(
    "fcount",
    "Particles",
    (OptionChoice("Few", 0), OptionChoice("Some", 1), OptionChoice("Many", 2)),
    default_index=1,
)
_FIELD = ModeOption(
    "field",
    "Field",
    (
        OptionChoice("Curl", 0),
        OptionChoice("Swirl", 1),
        OptionChoice("Grid", 2),
        OptionChoice("Radial", 3),
    ),
    default_index=0,
)
_COLORBY = ModeOption(
    "colorby",
    "Color By",
    (OptionChoice("Velocity", 0), OptionChoice("Angle", 1), OptionChoice("Theme", 2)),
    default_index=1,
)
_VORTEX = ModeOption(
    "vortex",
    "Vortex Beat",
    (OptionChoice("Off", 0), OptionChoice("On", 1)),
    default_index=1,
)


@register(key="test_flowfield", display_name="Test_Flow Field", order=42)
class TestFlowField(BaseVisualizer):
    """Curl-field particle streams with persistent silky trails."""

    OPTIONS = (_PRESET, _PARTICLES, _FIELD, TRAIL_OPTION, _COLORBY, _VORTEX, SPEED_OPTION)
    PRESETS = {
        1: {"fcount": 1, "field": 0, "trails": 1, "colorby": 1, "vortex": 0, "rate": 0},  # Silk
        2: {"fcount": 2, "field": 0, "trails": 1, "colorby": 0, "vortex": 1, "rate": 2},  # Storm
        3: {"fcount": 1, "field": 1, "trails": 1, "colorby": 1, "vortex": 1, "rate": 1},  # Vortex
    }

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._n = 0
        self._rng = np.random.default_rng(41)
        self._x = self._y = self._spd = np.zeros(0, dtype=np.float32)
        self._t = 0.0
        self._trail: pygame.Surface | None = None
        self._trail_size: tuple[int, int] = (0, 0)
        self._vortex: tuple[float, float, float] | None = None  # x, y, strength
        self._lut = _build_lut(_FLOW_PALETTE)
        self._lut_scheme = ""

    def on_enter(self) -> None:
        self._t = 0.0
        self._rng = np.random.default_rng(41)
        self._n = 0
        self._trail = None
        self._vortex = None

    def _ensure_particles(self) -> None:
        n = _COUNTS[int(self.option("fcount"))]
        if self.reduce_motion:
            n //= 2
        if n == self._n:
            return
        self._x = self._rng.uniform(0, 1, n).astype(np.float32)
        self._y = self._rng.uniform(0, 1, n).astype(np.float32)
        self._spd = self._rng.uniform(0.6, 1.3, n).astype(np.float32)
        self._n = n

    def _ensure_trail(self, w: int, h: int) -> None:
        if self._trail is None or self._trail_size != (w, h):
            self._trail = pygame.Surface((w, h))
            self._trail_size = (w, h)

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        self._ensure_particles()
        self._ensure_trail(w, h)
        assert self._trail is not None
        self._t += dt * self.theme.speed_scale * float(self.option("rate"))

        level = 0.0 if frame is None or frame.is_silent else clamp(frame.rms * 2.0)
        bass = (
            0.0
            if frame is None or not frame.band_energies.size
            else float(np.mean(frame.band_energies[:8]))
        )
        onset = 0.0 if frame is None else frame.onset
        self._update_vortex(onset, dt)

        ang = self._angles(self._x, self._y, self._t, bass, int(self.option("field")))
        speed = _BASE_SPEED * (0.4 + 1.6 * level) * float(self.option("rate")) * self._spd
        vx, vy = np.cos(ang) * speed, np.sin(ang) * speed
        prevx, prevy = self._x.copy(), self._y.copy()
        self._x = (self._x + vx * dt) % 1.0
        self._y = (self._y + vy * dt) % 1.0

        trails_on = int(self.option("trails")) == 1
        if trails_on:
            self._trail.fill(_FADE, special_flags=pygame.BLEND_RGB_SUB)
        else:
            self._trail.fill((0, 0, 0))
        self._render(ang, speed, prevx, prevy, w, h, level)
        surface.blit(self._trail, (0, 0))

    def _update_vortex(self, onset: float, dt: float) -> None:
        if int(self.option("vortex")) == 1 and onset >= ONSET_THRESHOLD and not self.reduce_motion:
            self._vortex = (
                float(self._rng.uniform(0.2, 0.8)),
                float(self._rng.uniform(0.2, 0.8)),
                1.0,
            )
        if self._vortex is not None:
            x, y, s = self._vortex
            s -= dt * 1.2
            self._vortex = None if s <= 0.0 else (x, y, s)

    def _angles(
        self, x: np.ndarray, y: np.ndarray, t: float, bass: float, field: int
    ) -> np.ndarray:
        if field == 1:  # swirl around center
            a = np.arctan2(y - 0.5, x - 0.5) + math.pi / 2
        elif field == 3:  # radial outward
            a = np.arctan2(y - 0.5, x - 0.5)
        else:  # curl-noise-ish interference
            f = 2.5 + bass * 3.0
            a = (
                np.sin(x * f + t) + np.cos(y * f - t * 0.7) + np.sin((x + y) * f * 0.5 + t * 0.3)
            ) * math.pi
            if field == 2:  # grid: snap to 4 cardinal directions
                a = np.round(a / (math.pi / 2)) * (math.pi / 2)
        if self._vortex is not None:
            vx, vy, s = self._vortex
            dd = (x - vx) ** 2 + (y - vy) ** 2
            infl = s * np.exp(-dd / 0.02)
            a = a + infl * 3.0
        return a

    def _render(
        self,
        ang: np.ndarray,
        speed: np.ndarray,
        prevx: np.ndarray,
        prevy: np.ndarray,
        w: int,
        h: int,
        level: float,
    ) -> None:
        assert self._trail is not None
        colors = self._colors(ang, speed)
        x1 = (self._x * w).astype(np.int32)
        y1 = (self._y * h).astype(np.int32)
        x0 = (prevx * w).astype(np.int32)
        y0 = (prevy * h).astype(np.int32)
        wrapped = (np.abs(x1 - x0) > w * 0.5) | (np.abs(y1 - y0) > h * 0.5)
        trail = self._trail
        for i in range(self._n):
            c = (int(colors[i, 0]), int(colors[i, 1]), int(colors[i, 2]))
            if wrapped[i]:
                trail.set_at((int(x1[i]), int(y1[i])), c)
            else:
                pygame.draw.line(trail, c, (int(x0[i]), int(y0[i])), (int(x1[i]), int(y1[i])), 1)

    def _colors(self, ang: np.ndarray, speed: np.ndarray) -> np.ndarray:
        mode = int(self.option("colorby"))
        if mode == 0:  # velocity
            t = np.clip((self._spd - 0.6) / 0.7, 0.0, 1.0)
        elif mode == 1:  # angle
            t = (ang / (2 * math.pi)) % 1.0
        else:  # theme
            self._ensure_theme_lut()
            t = self._x  # left->right ramp through the theme
        idx = np.clip((t * 255).astype(np.int32), 0, 255)
        return self._lut[idx]

    def _ensure_theme_lut(self) -> None:
        scheme = self.theme.color_scheme
        if self._lut_scheme == scheme:
            return
        ramp = tuple(
            themed_color(scheme, i / 6.0, _FLOW_PALETTE, self.theme.color_phase) for i in range(7)
        )
        self._lut = _build_lut(ramp)
        self._lut_scheme = scheme

    def on_option_change(self, key: str) -> None:
        super().on_option_change(key)
        if key in ("colorby", "preset"):
            self._lut = _build_lut(_FLOW_PALETTE)  # reset; theme LUT rebuilds on demand
            self._lut_scheme = ""


def _build_lut(palette: tuple[tuple[int, int, int], ...]) -> np.ndarray:
    """Precompute a 256-entry RGB ramp from a palette for cheap per-particle coloring."""
    lut = np.empty((256, 3), dtype=np.uint8)
    for i in range(256):
        lut[i] = palette_color(palette, i / 255.0)
    return lut
