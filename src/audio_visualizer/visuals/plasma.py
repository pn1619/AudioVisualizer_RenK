"""Plasma / Liquid: a flowing color field driven by bass, with material styles.

A sine-interference field is evaluated on a small grid (then upscaled, so it stays
cheap), colored by a per-material palette and animated over time. Bass adds
turbulence. Choose the **material** (marble/oil/water/lava/silk), the **flow**
direction (drift/horizontal/vertical/swirl/radial), the **intensity** (contrast +
turbulence), and an optional **drops** overlay (ripples / rain / blobs) on beats.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.visuals._helpers import clamp
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_GRID_W = 200  # field is computed at this width then smoothscaled to the canvas
_FLOW_RATE = 0.4  # base time advance per second (scaled by speed)
_BASS_TURBULENCE = 2.5  # extra spatial frequency added by bass energy
_DROP_CAP = 140

# Per-material palette stops (0..1) and a spatial-frequency factor.
_MATERIALS: dict[int, tuple[tuple[tuple[int, int, int], ...], float]] = {
    0: (
        ((10, 4, 30), (190, 30, 160), (40, 90, 230), (60, 230, 255), (255, 255, 255)),
        1.0,
    ),  # marble
    1: (((6, 8, 12), (40, 10, 70), (10, 95, 95), (190, 150, 40), (230, 220, 255)), 0.55),  # oil
    2: (
        ((2, 10, 30), (10, 60, 120), (20, 130, 200), (120, 210, 240), (240, 255, 255)),
        0.8,
    ),  # water
    3: (((4, 2, 2), (80, 8, 4), (200, 40, 10), (250, 150, 20), (255, 240, 160)), 0.7),  # lava
    4: (
        ((30, 10, 40), (120, 40, 140), (220, 120, 200), (150, 170, 255), (245, 235, 255)),
        0.6,
    ),  # silk
}

_STYLE = ModeOption(
    "style",
    "Material",
    (
        OptionChoice("Marble", 0),
        OptionChoice("Oil", 1),
        OptionChoice("Water", 2),
        OptionChoice("Lava", 3),
        OptionChoice("Silk", 4),
    ),
    default_index=0,
)
_FLOW = ModeOption(
    "flow",
    "Flow",
    (
        OptionChoice("Drift", 0),
        OptionChoice("Right", 1),
        OptionChoice("Up", 2),
        OptionChoice("Swirl", 3),
        OptionChoice("Radial", 4),
    ),
    default_index=0,
)
_INTENSITY = ModeOption(
    "intensity",
    "Intensity",
    (OptionChoice("Soft", 0.7), OptionChoice("Normal", 1.3), OptionChoice("Vivid", 2.3)),
    default_index=1,
)
_DROPS = ModeOption(
    "drops",
    "Drops",
    (
        OptionChoice("Off", 0),
        OptionChoice("Ripple", 1),
        OptionChoice("Rain", 2),
        OptionChoice("Blobs", 3),
    ),
    default_index=0,
)


@dataclass
class _Drop:
    """A normalized-space droplet; behavior depends on the active drops kind."""

    x: float
    y: float
    vy: float
    r: float
    life: float
    max_life: float


@register(key="plasma", display_name="Plasma", order=80)
class Plasma(BaseVisualizer):
    """A bass-reactive sine-interference plasma with materials, flow, and drops."""

    OPTIONS = (_STYLE, _FLOW, _INTENSITY, _DROPS)

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._t = 0.0
        self._phase = 0.0  # directional-flow phase
        self._grid: tuple[int, int] | None = None
        self._xx: np.ndarray | None = None
        self._yy: np.ndarray | None = None
        self._drops: list[_Drop] = []
        self._rng = random.Random(2027)

    def on_enter(self) -> None:
        self._t = self._phase = 0.0
        self._drops.clear()
        self._rng.seed(2027)

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
        self._phase += dt * speed * 0.15

        material = int(self.option("style"))
        palette, freq = _MATERIALS[material]
        xx, yy = self._flow_coords(self._xx, self._yy, int(self.option("flow")))
        field = self._field(xx, yy, self._t, bass, material, freq)
        field = self._apply_intensity(field, float(self.option("intensity")))
        rgb = _palette_lookup(field, palette)
        small = pygame.surfarray.make_surface(np.transpose(rgb, (1, 0, 2)))
        surface.blit(pygame.transform.smoothscale(small, (w, h)), (0, 0))

        if int(self.option("drops")) != 0:
            self._draw_drops(surface, frame, dt, w, h)

    def _flow_coords(
        self, xx: np.ndarray, yy: np.ndarray, flow: int
    ) -> tuple[np.ndarray, np.ndarray]:
        if flow == 1:  # right
            return xx + self._phase, yy
        if flow == 2:  # up
            return xx, yy + self._phase
        if flow == 3:  # swirl: rotate coords about the center over time
            a = self._phase * math.tau
            dx, dy = xx - 0.5, yy - 0.5
            return 0.5 + dx * math.cos(a) - dy * math.sin(a), 0.5 + dx * math.sin(
                a
            ) + dy * math.cos(a)
        if flow == 4:  # radial: push outward over time
            dx, dy = xx - 0.5, yy - 0.5
            r = np.hypot(dx, dy) + self._phase
            ang = np.arctan2(dy, dx)
            return 0.5 + np.cos(ang) * r, 0.5 + np.sin(ang) * r
        return xx, yy  # drift

    def _field(
        self, xx: np.ndarray, yy: np.ndarray, t: float, bass: float, material: int, freq: float
    ) -> np.ndarray:
        turb = (1.0 + bass * _BASS_TURBULENCE) * freq
        v = (
            np.sin((xx * 6.0 + t) * turb)
            + np.sin((yy * 7.0 - t * 1.2) * freq)
            + np.sin((xx + yy) * 5.0 * turb + t * 0.7)
            + np.sin(np.hypot(xx - 0.5, yy - 0.5) * 14.0 * freq - t * 1.5)
        )
        if material == 3:  # lava: rising vertical bias
            v += 1.4 * np.sin((yy * 9.0 - t * 2.6) * freq)
        elif material == 2:  # water: extra radial ripples
            v += 1.2 * np.sin(np.hypot(xx - 0.5, yy - 0.5) * 26.0 - t * 3.0)
        return (v / 5.0 + 0.5) % 1.0  # normalize and wrap for a seamless cycle

    def _apply_intensity(self, field: np.ndarray, k: float) -> np.ndarray:
        return np.clip((field - 0.5) * k + 0.5, 0.0, 1.0)

    def _draw_drops(
        self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float, w: int, h: int
    ) -> None:
        kind = int(self.option("drops"))
        self._spawn_drops(frame, kind)
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        alive: list[_Drop] = []
        move = dt * self.theme.speed_scale
        for d in self._drops:
            d.life -= dt
            if d.life <= 0.0:
                continue
            t = clamp(d.life / d.max_life)
            if kind == 1:  # expanding ripple ring
                d.r += move * 0.5
                rad = int(d.r * min(w, h))
                pygame.draw.circle(
                    overlay,
                    (210, 235, 255, int(150 * t)),
                    (int(d.x * w), int(d.y * h)),
                    max(1, rad),
                    2,
                )
            elif kind == 2:  # falling rain streak
                d.y += d.vy * move
                x, y = int(d.x * w), int(d.y * h)
                pygame.draw.line(
                    overlay, (200, 225, 255, int(180 * t)), (x, y), (x, y + int(h * 0.04)), 2
                )
                if d.y < 1.05:
                    alive.append(d)
                continue
            else:  # slow translucent blob (oil)
                rad = int(d.r * min(w, h) * (1.3 - t))
                pygame.draw.circle(
                    overlay, (255, 230, 180, int(90 * t)), (int(d.x * w), int(d.y * h)), max(1, rad)
                )
            if d.life > 0.0 and not (kind == 1 and d.r > 1.0):
                alive.append(d)
        self._drops = alive
        surface.blit(overlay, (0, 0))

    def _spawn_drops(self, frame: AnalysisFrame | None, kind: int) -> None:
        if frame is None or frame.is_silent or len(self._drops) >= _DROP_CAP:
            return
        onset = frame.onset
        if onset <= 0.35 and self._rng.random() > 0.04:
            return
        count = 1 if kind == 2 else max(1, int(onset * 3))
        for _ in range(count):
            if len(self._drops) >= _DROP_CAP:
                break
            if kind == 2:  # rain starts at the top
                self._drops.append(
                    _Drop(self._rng.random(), -0.02, self._rng.uniform(0.6, 1.1), 0.0, 1.4, 1.4)
                )
            else:
                self._drops.append(
                    _Drop(
                        self._rng.random(),
                        self._rng.random(),
                        0.0,
                        self._rng.uniform(0.02, 0.06),
                        1.2,
                        1.2,
                    )
                )


def _palette_lookup(values: np.ndarray, palette: tuple[tuple[int, int, int], ...]) -> np.ndarray:
    """Sample a cyclic palette across ``values`` (0..1) -> (..., 3) uint8."""
    cyc = np.array([*palette, palette[0]], dtype=np.float32)
    stops = np.linspace(0.0, 1.0, cyc.shape[0])
    out = np.empty((*values.shape, 3), dtype=np.float32)
    for c in range(3):
        out[..., c] = np.interp(values, stops, cyc[:, c])
    return out.astype(np.uint8)
