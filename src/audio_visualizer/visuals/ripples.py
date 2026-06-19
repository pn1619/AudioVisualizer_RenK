"""Ripples: expanding shockwaves born from beats that spread across the canvas.

Each onset (or a steady beat grid / continuous trickle) spawns a ring that grows
outward and fades, like a drop hitting water. Origins can sit at the center, scatter
randomly, or burst from the center on bass hits. Rings render as a single outline,
a double wave, or a soft filled bloom.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.visuals._helpers import (
    COLOR_OPTION,
    SPEED_OPTION,
    clamp,
    mode_color,
    scale_color,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_ONSET_TRIGGER = 0.3
_GRID_INTERVAL = 0.45  # seconds between beat-grid spawns
_CONTINUOUS_INTERVAL = 0.12  # min seconds between continuous spawns
_GROW = 0.55  # ring growth speed as a fraction of the diagonal per second
_LIFETIME = 1.6

_SPAWN = ModeOption(
    "spawn",
    "Spawn",
    (OptionChoice("Onset", 0), OptionChoice("Beat-grid", 1), OptionChoice("Continuous", 2)),
    default_index=0,
)
_ORIGIN = ModeOption(
    "origin",
    "Origin",
    (OptionChoice("Center", 0), OptionChoice("Random", 1), OptionChoice("Bass", 2)),
    default_index=0,
)
_STYLE = ModeOption(
    "rstyle",
    "Style",
    (OptionChoice("Ring", 0), OptionChoice("Double", 1), OptionChoice("Filled", 2)),
    default_index=0,
)
_MAX = ModeOption(
    "rmax",
    "Max",
    (OptionChoice("8", 8), OptionChoice("16", 16), OptionChoice("32", 32)),
    default_index=1,
)
# Line thickness. ``Auto`` (-1) keeps the original strength-driven width; ``Random``
# (-2) gives each ring its own width; the fixed choices set a base width in px.
_WIDTH = ModeOption(
    "rwidth",
    "Width",
    (
        OptionChoice("Auto", -1.0),
        OptionChoice("Thin", 1.0),
        OptionChoice("Normal", 3.0),
        OptionChoice("Thick", 6.0),
        OptionChoice("Random", -2.0),
    ),
    default_index=0,
)


@dataclass
class _Ripple:
    """A shockwave in normalized space: ``radius`` is a fraction of the diagonal."""

    x: float
    y: float
    radius: float
    life: float
    hue: float
    strength: float
    width_mul: float = 1.0  # per-ring random factor, used only by the "Random" width


@register(key="ripples", display_name="Ripples", order=125)
class Ripples(BaseVisualizer):
    """Beat-born expanding rings that grow and fade across the canvas."""

    OPTIONS = (_SPAWN, _ORIGIN, _STYLE, _WIDTH, _MAX, SPEED_OPTION, COLOR_OPTION)

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._ripples: list[_Ripple] = []
        self._rng = random.Random(7)
        self._prev_onset = 0.0
        self._timer = 0.0

    def on_enter(self) -> None:
        self._ripples.clear()
        self._prev_onset = 0.0
        self._timer = 0.0

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        speed = self.option("rate") * (0.5 if self.reduce_motion else 1.0)
        self._spawn(frame, dt)
        self._advance(dt * self.theme.speed_scale * speed)
        self._render(surface, w, h)

    def _spawn(self, frame: AnalysisFrame | None, dt: float) -> None:
        mode = int(self.option("spawn"))
        onset = 0.0 if frame is None else frame.onset
        strength = 0.0 if frame is None else clamp(frame.rms * 4.0)
        self._timer += dt
        if mode == 0:
            if onset > _ONSET_TRIGGER and self._prev_onset <= _ONSET_TRIGGER:
                self._add(frame, onset)
        elif mode == 1:
            if self._timer >= _GRID_INTERVAL:
                self._timer = 0.0
                self._add(frame, max(0.4, strength))
        elif strength > 0.05 and self._timer >= _CONTINUOUS_INTERVAL:
            self._timer = 0.0
            self._add(frame, strength)
        self._prev_onset = onset

    def _add(self, frame: AnalysisFrame | None, strength: float) -> None:
        if len(self._ripples) >= int(self.option("rmax")):
            self._ripples.pop(0)
        origin = int(self.option("origin"))
        if origin == 1:
            x, y = self._rng.random(), self._rng.random()
        else:  # Center and Bass both burst from the middle
            x, y = 0.5, 0.5
        self._ripples.append(
            _Ripple(
                x=x,
                y=y,
                radius=0.0,
                life=_LIFETIME,
                hue=self._rng.random(),
                strength=clamp(strength),
                width_mul=self._rng.uniform(0.4, 2.6),
            )
        )

    def _advance(self, move: float) -> None:
        alive: list[_Ripple] = []
        for rp in self._ripples:
            rp.radius += _GROW * move
            rp.life -= move
            if rp.life > 0.0 and rp.radius < 1.5:
                alive.append(rp)
        self._ripples = alive

    def _render(self, surface: pygame.Surface, w: int, h: int) -> None:
        diag = (w**2 + h**2) ** 0.5
        style = int(self.option("rstyle"))
        color_opt = int(self.option("color"))
        width_opt = self.option("rwidth")
        scheme, phase = self.theme.color_scheme, self.theme.color_phase
        for rp in self._ripples:
            cx, cy = int(rp.x * w), int(rp.y * h)
            r = int(rp.radius * diag * 0.5)
            if r < 1:
                continue
            fade = clamp(rp.life / _LIFETIME)
            color = scale_color(mode_color(color_opt, scheme, rp.hue, phase), fade)
            width = self._line_width(width_opt, rp)
            if style == 2:
                self._filled(surface, cx, cy, r, color, fade)
            elif style == 1:
                pygame.draw.circle(surface, color, (cx, cy), r, width)
                inner = int(r * 0.7)
                if inner > 0:
                    pygame.draw.circle(
                        surface, scale_color(color, 0.6), (cx, cy), inner, max(1, width - 1)
                    )
            else:
                pygame.draw.circle(surface, color, (cx, cy), r, width)

    @staticmethod
    def _line_width(width_opt: float, rp: _Ripple) -> int:
        """Resolve the ring's stroke width from the Width option + ripple strength."""
        auto = 2.0 + rp.strength * 5.0  # original loudness-driven width
        if width_opt == -1.0:  # Auto
            value = auto
        elif width_opt == -2.0:  # Random: scale the auto width per ring
            value = auto * rp.width_mul
        else:  # fixed base, nudged a little by strength
            value = width_opt + rp.strength * 2.0
        return max(1, int(value))

    @staticmethod
    def _filled(
        surface: pygame.Surface,
        cx: int,
        cy: int,
        r: int,
        color: tuple[int, int, int],
        fade: float,
    ) -> None:
        glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*color, int(120 * fade)), (r, r), r)
        surface.blit(glow, (cx - r, cy - r), special_flags=pygame.BLEND_RGB_ADD)
