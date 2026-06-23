"""Constellation: drifting nodes that link up when near, rippling on beats.

Nodes drift (or orbit / repel) across the field; whenever two pass within the link
distance a glowing line connects them, brighter the closer they are. Node size rides
the bass, link brightness rides the spectrum, and each onset sends an expanding ripple
that lights up the nodes and links it sweeps through.

Shipped under a ``Test_`` name during evaluation; remove the prefix once approved.
"""

from __future__ import annotations

import math

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import ONSET_THRESHOLD
from audio_visualizer.visuals._helpers import (
    Color,
    clamp,
    lerp_color,
    rainbow_color,
    scale_color,
    themed_color,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_COUNTS = {0: 55, 1: 95, 2: 130}
_LINKDIST = {0: 0.13, 1: 0.18, 2: 0.25}
_CYAN = (90, 200, 255)
_GOLD = (255, 200, 90)

_PRESET = ModeOption(
    "preset",
    "Preset",
    (
        OptionChoice("Custom", 0),
        OptionChoice("Night Sky", 1),
        OptionChoice("Neural Net", 2),
        OptionChoice("Plexus", 3),
    ),
    default_index=0,
)
_NODES = ModeOption(
    "nodes",
    "Nodes",
    (OptionChoice("Few", 0), OptionChoice("Medium", 1), OptionChoice("Many", 2)),
    default_index=1,
)
_LINKDISTOPT = ModeOption(
    "linkdist",
    "Link Dist",
    (OptionChoice("Short", 0), OptionChoice("Med", 1), OptionChoice("Long", 2)),
    default_index=1,
)
_MOTION = ModeOption(
    "motion",
    "Motion",
    (OptionChoice("Drift", 0), OptionChoice("Orbit", 1), OptionChoice("Repel", 2)),
    default_index=0,
)
_LINKSTYLE = ModeOption(
    "linkstyle",
    "Links",
    (OptionChoice("Lines", 0), OptionChoice("Glow", 1), OptionChoice("Pulse", 2)),
    default_index=1,
)
_COLOR = ModeOption(
    "ccolor",
    "Color",
    (OptionChoice("Cyan-Gold", 0), OptionChoice("Theme", 1), OptionChoice("Rainbow", 2)),
    default_index=0,
)
_DEPTH = ModeOption(
    "depth",
    "Depth",
    (OptionChoice("Flat", 0), OptionChoice("Parallax", 1)),
    default_index=1,
)


@register(key="test_constellation", display_name="Test_Constellation", order=88)
class TestConstellation(BaseVisualizer):
    """A drifting node graph with proximity links and onset ripples."""

    OPTIONS = (_PRESET, _NODES, _LINKDISTOPT, _MOTION, _LINKSTYLE, _COLOR, _DEPTH)
    PRESETS = {
        1: {"nodes": 0, "linkdist": 0, "motion": 0, "linkstyle": 1, "ccolor": 0, "depth": 1},
        2: {"nodes": 2, "linkdist": 1, "motion": 0, "linkstyle": 2, "ccolor": 0, "depth": 0},
        3: {"nodes": 2, "linkdist": 2, "motion": 1, "linkstyle": 1, "ccolor": 2, "depth": 1},
    }

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._t = 0.0
        self._n = 0
        self._rng = np.random.default_rng(23)
        self._x = self._y = self._vx = self._vy = self._z = np.zeros(0, dtype=np.float32)
        self._gold = np.zeros(0, dtype=bool)
        self._ripples: list[float] = []  # expanding ripple radii (normalized)
        self._ripple_pos: list[tuple[float, float]] = []

    def on_enter(self) -> None:
        self._t = 0.0
        self._rng = np.random.default_rng(23)
        self._n = 0
        self._ripples.clear()
        self._ripple_pos.clear()

    def _ensure_nodes(self) -> None:
        n = _COUNTS[int(self.option("nodes"))]
        if self.reduce_motion:
            n = int(n * 0.6)
        if n == self._n:
            return
        r = self._rng
        self._x = r.uniform(0, 1, n).astype(np.float32)
        self._y = r.uniform(0, 1, n).astype(np.float32)
        ang = r.uniform(0, 2 * math.pi, n)
        spd = r.uniform(0.01, 0.05, n)
        self._vx = (np.cos(ang) * spd).astype(np.float32)
        self._vy = (np.sin(ang) * spd).astype(np.float32)
        self._z = r.uniform(0.3, 1.0, n).astype(np.float32)
        self._gold = r.uniform(0, 1, n) < 0.3
        self._n = n

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        self._ensure_nodes()
        self._t += dt
        level = 0.0 if frame is None or frame.is_silent else clamp(frame.rms * 2.0)
        bass = (
            level
            if frame is None
            else (
                clamp(float(np.mean(frame.band_energies[:8])) * 1.5)
                if frame.band_energies.size
                else level
            )
        )
        onset = 0.0 if frame is None else frame.onset
        self._move(dt)
        self._update_ripples(dt, onset)

        depth = int(self.option("depth")) == 1
        px = self._x * w
        py = self._y * h
        zf = (0.4 + 0.6 * self._z) if depth else np.ones(self._n, dtype=np.float32)

        glow = pygame.Surface((w, h), pygame.SRCALPHA)
        self._draw_links(surface, glow, px, py, zf, w, h, level)
        self._draw_nodes(surface, glow, px, py, zf, bass)
        surface.blit(glow, (0, 0), special_flags=pygame.BLEND_ADD)

    def _move(self, dt: float) -> None:
        motion = int(self.option("motion"))
        step = dt * self.theme.speed_scale * (0.5 if self.reduce_motion else 1.0)
        if motion == 1:  # orbit around the center
            dx, dy = self._x - 0.5, self._y - 0.5
            a = step * 0.4
            nx = 0.5 + dx * math.cos(a) - dy * math.sin(a)
            ny = 0.5 + dx * math.sin(a) + dy * math.cos(a)
            self._x, self._y = nx.astype(np.float32), ny.astype(np.float32)
        else:
            vx, vy = self._vx, self._vy
            if motion == 2:  # repel from center
                dx, dy = self._x - 0.5, self._y - 0.5
                vx = vx + dx * 0.04
                vy = vy + dy * 0.04
            self._x = (self._x + vx * step) % 1.0
            self._y = (self._y + vy * step) % 1.0

    def _update_ripples(self, dt: float, onset: float) -> None:
        if onset >= ONSET_THRESHOLD and not self.reduce_motion and len(self._ripples) < 6:
            i = int(self._rng.integers(0, max(1, self._n)))
            self._ripples.append(0.0)
            self._ripple_pos.append((float(self._x[i]), float(self._y[i])))
        speed = dt * self.theme.speed_scale * 0.8
        kept_r, kept_p = [], []
        for r, p in zip(self._ripples, self._ripple_pos, strict=False):
            if r + speed < 1.4:
                kept_r.append(r + speed)
                kept_p.append(p)
        self._ripples, self._ripple_pos = kept_r, kept_p

    def _ripple_boost(self, x: float, y: float) -> float:
        boost = 0.0
        for r, (rx, ry) in zip(self._ripples, self._ripple_pos, strict=False):
            d = math.hypot(x - rx, y - ry)
            boost = max(boost, math.exp(-((d - r) ** 2) / 0.004))
        return boost

    def _node_color(self, i: int) -> Color:
        mode = int(self.option("ccolor"))
        if mode == 1:
            return themed_color(
                self.theme.color_scheme, (i * 0.137) % 1.0, (_CYAN,), self.theme.color_phase
            )
        if mode == 2:
            return rainbow_color((i * 0.0618) % 1.0)
        return _GOLD if self._gold[i] else _CYAN

    def _draw_links(
        self,
        surface: pygame.Surface,
        glow: pygame.Surface,
        px: np.ndarray,
        py: np.ndarray,
        zf: np.ndarray,
        w: int,
        h: int,
        level: float,
    ) -> None:
        maxd = _LINKDIST[int(self.option("linkdist"))]
        dx = self._x[:, None] - self._x[None, :]
        dy = self._y[:, None] - self._y[None, :]
        d2 = dx * dx + dy * dy
        iu, ju = np.triu_indices(self._n, k=1)
        m = d2[iu, ju] < (maxd * maxd)
        ia, ja = iu[m], ju[m]
        style = int(self.option("linkstyle"))
        for a, b in zip(ia.tolist(), ja.tolist(), strict=False):
            dist = math.sqrt(float(d2[a, b]))
            prox = 1.0 - dist / maxd
            mid = ((self._x[a] + self._x[b]) * 0.5, (self._y[a] + self._y[b]) * 0.5)
            boost = self._ripple_boost(*mid)
            alpha = clamp(prox * (0.35 + 0.6 * level) + boost)
            color = lerp_color(self._node_color(a), self._node_color(b), 0.5)
            p0 = (int(px[a]), int(py[a]))
            p1 = (int(px[b]), int(py[b]))
            if style == 1:  # glow: faint wide line on the additive layer
                pygame.draw.line(glow, (*color, int(120 * alpha)), p0, p1, 2)
            pygame.draw.line(surface, scale_color(color, alpha), p0, p1, 1)
            if style == 2:  # pulse travelling along the link
                t = (self._t * 0.6 + a * 0.05) % 1.0
                pp = (int(px[a] + (px[b] - px[a]) * t), int(py[a] + (py[b] - py[a]) * t))
                pygame.draw.circle(surface, scale_color(color, clamp(alpha + 0.3)), pp, 2)

    def _draw_nodes(
        self,
        surface: pygame.Surface,
        glow: pygame.Surface,
        px: np.ndarray,
        py: np.ndarray,
        zf: np.ndarray,
        bass: float,
    ) -> None:
        base = max(1.5, min(*surface.get_size()) * 0.004) * self.theme.size_scale
        for i in range(self._n):
            boost = self._ripple_boost(float(self._x[i]), float(self._y[i]))
            radius = max(1, int(base * zf[i] * (1.0 + 0.8 * bass + boost)))
            color = self._node_color(i)
            pygame.draw.circle(glow, (*color, 90), (int(px[i]), int(py[i])), radius * 3)
            pygame.draw.circle(
                surface,
                scale_color(color, clamp(0.6 + 0.4 * zf[i] + boost)),
                (int(px[i]), int(py[i])),
                radius,
            )
