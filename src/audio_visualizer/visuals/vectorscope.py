"""XY Vectorscope: a phosphor oscilloscope that plots the waveform against itself.

X is the sample, Y is the sample delayed by N taps, so periodic audio traces Lissajous
loops on a glowing CRT. An optional persistence surface (cheap multiply-fade + additive
blit) leaves trailing afterglow, and the trace can slowly rotate. Color can be classic
phosphor, a rainbow sweep along the trace, or velocity-mapped (fast segments glow hot).
"""

from __future__ import annotations

import math

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.visuals._helpers import (
    MIRROR_OPTION,
    SIZE_OPTION,
    THICKNESS_OPTION,
    clamp,
    mirror_points,
    rainbow_color,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_POINTS = 256  # trace resolution (waveform resampled to this)
_PHOSPHOR = (70, 255, 130)
# Auto-gain: scale each frame so its loudest sample reaches the scope edge. The
# floor caps the gain so quiet passages stay small instead of amplifying noise.
_NORM_FLOOR = 0.25

# Scope radius as a fraction of the smaller window edge, before the shared Size
# multiplier. ``M`` (×1.0) lands on this; the larger steps (XL/XXL/XXXL) spill past
# the short edge to fill — or overflow — the canvas.
_SIZE_BASE = 0.6

_DELAY = ModeOption(
    "delay",
    "Phase",
    (OptionChoice("1", 1), OptionChoice("4", 4), OptionChoice("16", 16), OptionChoice("64", 64)),
    default_index=1,
)
_PERSIST = ModeOption(
    "persist",
    "Trail",
    (OptionChoice("None", 0), OptionChoice("Short", 1), OptionChoice("Long", 2)),
    default_index=1,
)
_DRAW = ModeOption(
    "draw", "Draw", (OptionChoice("Line", 0), OptionChoice("Dots", 1)), default_index=0
)
_COLOR = ModeOption(
    "vcolor",
    "Color",
    (OptionChoice("Phosphor", 0), OptionChoice("Rainbow", 1), OptionChoice("Velocity", 2)),
    default_index=0,
)
_ROTATE = ModeOption(
    "rotate",
    "Spin",
    (OptionChoice("Off", 0), OptionChoice("Slow", 0.05), OptionChoice("Fast", 0.2)),
    default_index=0,
)
_GRID = ModeOption("grid", "Grid", (OptionChoice("On", 1), OptionChoice("Off", 0)), default_index=0)

# Per-frame multiply factor for the persistence afterglow (lower = longer trail).
_FADE = {1: 0.80, 2: 0.92}


@register(key="vectorscope", display_name="Vectorscope", order=105)
class Vectorscope(BaseVisualizer):
    """Lissajous XY scope with phosphor persistence and optional rotation."""

    OPTIONS = (
        _DELAY,
        _PERSIST,
        _DRAW,
        THICKNESS_OPTION,
        _COLOR,
        _ROTATE,
        _GRID,
        SIZE_OPTION,
        MIRROR_OPTION,
    )

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._persist: pygame.Surface | None = None
        self._persist_size = (0, 0)
        self._angle = 0.0

    def on_enter(self) -> None:
        self._angle = 0.0
        if self._persist is not None:
            self._persist.fill((0, 0, 0))

    def on_resize(self, size: tuple[int, int]) -> None:
        self._persist = None

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        rate = 0.0 if self.reduce_motion else self.option("rotate")
        self._angle += dt * self.theme.speed_scale * rate * 2.0 * math.pi

        mirror = int(self.option("mirror"))
        persist_mode = int(self.option("persist"))
        cx, cy = w / 2.0, h / 2.0
        radius = min(w, h) * _SIZE_BASE * float(self.option("size"))
        if persist_mode == 0:
            self._blit_grid(surface, w, h, radius)
            pts = self._trace_points(frame, cx, cy, radius)
            for copy in mirror_points(pts, cx, cy, mirror):
                self._render(surface, copy)
            return

        # The persistence surface is full-canvas so any Size (incl. XL spilling past
        # the short edge) is held without clipping; the fade/add blits cover it.
        target = self._ensure_persist(w, h)
        target.fill((int(255 * _FADE[persist_mode]),) * 3, special_flags=pygame.BLEND_RGB_MULT)
        pts = self._trace_points(frame, cx, cy, radius)
        for copy in mirror_points(pts, cx, cy, mirror):
            self._render(target, copy)
        self._blit_grid(surface, w, h, radius)
        surface.blit(target, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _ensure_persist(self, w: int, h: int) -> pygame.Surface:
        if self._persist is None or self._persist_size != (w, h):
            self._persist = pygame.Surface((w, h))
            self._persist_size = (w, h)
        return self._persist

    def _trace_points(
        self, frame: AnalysisFrame | None, cx: float, cy: float, half: float
    ) -> list[tuple[float, float]]:
        if frame is None or frame.waveform_mono.size < 4:
            # Idle: a quiescent dot at center keeps the scope alive without strobing.
            return [(cx, cy)]
        wav = np.asarray(frame.waveform_mono, dtype=np.float32)
        # Auto-gain to the frame's peak so a typical (sub-unity) waveform fills the
        # scope instead of a tiny central blob; the floor keeps quiet audio modest.
        gain = 1.0 / max(float(np.max(np.abs(wav))), _NORM_FLOOR)
        delay = int(self.option("delay"))
        ys_src = np.roll(wav, delay)
        idx = np.linspace(0, wav.size - 1, _POINTS).astype(np.int64)
        x = wav[idx] * gain
        y = ys_src[idx] * gain
        if self._angle:
            cos_a, sin_a = math.cos(self._angle), math.sin(self._angle)
            x, y = x * cos_a - y * sin_a, x * sin_a + y * cos_a
        px = cx + x * half
        py = cy - y * half
        return [(float(a), float(b)) for a, b in zip(px, py, strict=False)]

    def _render(self, surface: pygame.Surface, pts: list[tuple[float, float]]) -> None:
        width = max(1, int(self.option("thickness")))
        color_mode = int(self.option("vcolor"))
        phase = self.theme.color_phase
        if int(self.option("draw")) == 1 or len(pts) < 2:
            for i, (x, y) in enumerate(pts):
                pygame.draw.circle(
                    surface,
                    self._seg_color(color_mode, i, len(pts), phase, pts),
                    (int(x), int(y)),
                    width,
                )
            return
        if color_mode == 0:
            pygame.draw.aalines(surface, _PHOSPHOR, False, pts)
            if width > 1:
                pygame.draw.lines(surface, _PHOSPHOR, False, pts, width)
            return
        for i in range(len(pts) - 1):
            pygame.draw.line(
                surface,
                self._seg_color(color_mode, i, len(pts), phase, pts),
                pts[i],
                pts[i + 1],
                width,
            )

    @staticmethod
    def _seg_color(
        mode: int, i: int, n: int, phase: float, pts: list[tuple[float, float]]
    ) -> tuple[int, int, int]:
        if mode == 0:
            return _PHOSPHOR
        if mode == 1:
            return rainbow_color(i / max(1, n) + phase)
        # Velocity: hue from how far this segment moved (fast = toward the warm end).
        if i + 1 < len(pts):
            dx = pts[i + 1][0] - pts[i][0]
            dy = pts[i + 1][1] - pts[i][1]
            speed = clamp(math.hypot(dx, dy) / 40.0)
        else:
            speed = 0.0
        return rainbow_color(0.55 - 0.55 * speed + phase)

    def _blit_grid(self, surface: pygame.Surface, w: int, h: int, radius: float) -> None:
        if int(self.option("grid")) == 0:
            return
        cx, cy = w // 2, h // 2
        r = int(radius)
        color = (30, 60, 40)
        pygame.draw.line(surface, color, (cx, cy - r), (cx, cy + r))
        pygame.draw.line(surface, color, (cx - r, cy), (cx + r, cy))
        pygame.draw.circle(surface, color, (cx, cy), r, 1)
        pygame.draw.circle(surface, color, (cx, cy), r // 2, 1)
