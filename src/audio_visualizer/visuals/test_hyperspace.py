"""Hyperspace: a radial starfield warping out of a vanishing point.

Stars stream outward from the center; level sets warp speed, depth sets per-star
speed/streak length (perspective), and onsets lurch the field forward. Roll slowly
spins the field; the center can wander. Distinct from the background starfield: this
is a "jump to lightspeed" experience, not a quiet backdrop.

Shipped under a ``Test_`` name during evaluation; remove the prefix once approved.
"""

from __future__ import annotations

import math

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import ONSET_THRESHOLD
from audio_visualizer.visuals._helpers import Color, clamp, rainbow_color, scale_color, themed_color
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_BASE_SPEED = 0.36  # normalized radius per second at full warp
_COUNTS = {0: 420, 1: 850, 2: 1500}  # density -> star count
_TRAILS = {0: 0.0, 1: 0.09, 2: 0.22}  # trail option -> streak length factor

_PRESET = ModeOption(
    "preset",
    "Preset",
    (
        OptionChoice("Custom", 0),
        OptionChoice("Cruise", 1),
        OptionChoice("Lightspeed", 2),
        OptionChoice("Nebula", 3),
    ),
    default_index=0,
)
_DENSITY = ModeOption(
    "density",
    "Density",
    (OptionChoice("Sparse", 0), OptionChoice("Medium", 1), OptionChoice("Dense", 2)),
    default_index=1,
)
_WARP = ModeOption(
    "warp",
    "Warp",
    (OptionChoice("Cruise", 0), OptionChoice("Jump", 1), OptionChoice("Punch", 2)),
    default_index=1,
)
_TRAIL = ModeOption(
    "htrail",
    "Trails",
    (OptionChoice("Dots", 0), OptionChoice("Short", 1), OptionChoice("Long", 2)),
    default_index=1,
)
_CENTER = ModeOption(
    "center",
    "Center",
    (OptionChoice("Fixed", 0), OptionChoice("Wander", 1)),
    default_index=0,
)
_COLOR = ModeOption(
    "hcolor",
    "Color",
    (
        OptionChoice("White", 0),
        OptionChoice("Cyan", 1),
        OptionChoice("Theme", 2),
        OptionChoice("Rainbow", 3),
    ),
    default_index=1,
)
_ROLL = ModeOption(
    "roll",
    "Roll",
    (OptionChoice("Off", 0.0), OptionChoice("Slow", 0.15)),
    default_index=0,
)


@register(key="test_hyperspace", display_name="Test_Hyperspace", order=78)
class TestHyperspace(BaseVisualizer):
    """A warp-speed radial starfield; level drives speed, beats punch it forward."""

    STROBES = True  # Punch flashes on heavy onsets
    OPTIONS = (_PRESET, _DENSITY, _WARP, _TRAIL, _CENTER, _COLOR, _ROLL)
    PRESETS = {
        1: {"density": 1, "warp": 0, "htrail": 1, "hcolor": 0, "roll": 0},  # Cruise
        2: {"density": 2, "warp": 2, "htrail": 2, "hcolor": 1, "roll": 1},  # Jump to Lightspeed
        3: {"density": 2, "warp": 1, "htrail": 1, "hcolor": 2, "roll": 1},  # Nebula Drift
    }

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._t = 0.0
        self._roll = 0.0
        self._warp = 1.0  # decaying warp multiplier (impulse on beats)
        self._flash = 0.0
        self._n = 0
        self._rng = np.random.default_rng(7)
        self._ang = self._rad = self._dep = np.zeros(0, dtype=np.float32)

    def on_enter(self) -> None:
        self._t = self._roll = self._flash = 0.0
        self._warp = 1.0
        self._rng = np.random.default_rng(7)
        self._n = 0

    def _ensure_stars(self) -> None:
        n = _COUNTS[int(self.option("density"))]
        if self.reduce_motion:
            n //= 2
        if n == self._n:
            return
        self._ang = self._rng.uniform(0, 2 * math.pi, n).astype(np.float32)
        self._rad = self._rng.uniform(0.0, 1.0, n).astype(np.float32)
        self._dep = self._rng.uniform(0.35, 1.0, n).astype(np.float32)
        self._n = n

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        self._ensure_stars()
        self._t += dt
        level = 0.0 if frame is None or frame.is_silent else clamp(frame.rms * 2.0)
        onset = 0.0 if frame is None else frame.onset
        self._update_warp(onset, dt)

        roll_rate = float(self.option("roll")) * (0.4 if self.reduce_motion else 1.0)
        self._roll += dt * self.theme.speed_scale * roll_rate
        cx, cy = self._center(w, h)
        max_r = math.hypot(w, h) * 0.52

        speed = _BASE_SPEED * (0.35 + 1.5 * level) * self._warp * self.theme.speed_scale
        self._rad = self._rad + speed * self._dep * dt
        self._recycle()

        self._render(surface, w, h, cx, cy, max_r, speed)
        if self._flash > 0.01:
            self._draw_flash(surface, w, h)

    def _update_warp(self, onset: float, dt: float) -> None:
        mode = int(self.option("warp"))
        if mode != 0 and onset >= ONSET_THRESHOLD and not self.reduce_motion:
            self._warp = max(self._warp, 1.0 + (3.0 if mode == 2 else 1.6) * onset)
            if mode == 2:
                self._flash = max(self._flash, 0.5 * onset)
        self._warp = max(1.0, self._warp - dt * 4.0)
        self._flash = max(0.0, self._flash - dt * 2.5)

    def _center(self, w: int, h: int) -> tuple[float, float]:
        if int(self.option("center")) == 1:
            return (
                w * 0.5 + math.sin(self._t * 0.3) * w * 0.08,
                h * 0.5 + math.cos(self._t * 0.23) * h * 0.08,
            )
        return w * 0.5, h * 0.5

    def _recycle(self) -> None:
        mask = self._rad > 1.03
        cnt = int(mask.sum())
        if cnt:
            self._rad[mask] = self._rng.uniform(0.0, 0.06, cnt).astype(np.float32)
            self._ang[mask] = self._rng.uniform(0, 2 * math.pi, cnt).astype(np.float32)
            self._dep[mask] = self._rng.uniform(0.35, 1.0, cnt).astype(np.float32)

    def _render(
        self,
        surface: pygame.Surface,
        w: int,
        h: int,
        cx: float,
        cy: float,
        max_r: float,
        speed: float,
    ) -> None:
        ang = self._ang + self._roll
        ca, sa = np.cos(ang), np.sin(ang)
        trail = _TRAILS[int(self.option("htrail"))] * (0.5 if self.reduce_motion else 1.0)
        streak = trail * (0.25 + self._rad) + speed * self._dep * 0.03
        prev = np.clip(self._rad - streak, 0.0, 1.1)
        cur_px = self._rad * max_r
        prev_px = prev * max_r
        x1, y1 = cx + ca * cur_px, cy + sa * cur_px
        x0, y0 = cx + ca * prev_px, cy + sa * prev_px
        cmode = int(self.option("hcolor"))
        for i in range(self._n):
            r = float(self._rad[i])
            bright = clamp(0.25 + r * (0.9 + 0.4 * self._dep[i]))
            color = self._star_color(cmode, float(ang[i]), r, bright)
            width = 1 if r < 0.45 else 2
            if trail <= 0.0:
                pygame.draw.circle(surface, color, (int(x1[i]), int(y1[i])), width)
            else:
                pygame.draw.line(
                    surface, color, (int(x0[i]), int(y0[i])), (int(x1[i]), int(y1[i])), width
                )

    def _star_color(self, cmode: int, ang: float, r: float, bright: float) -> Color:
        if cmode == 0:
            base = (210, 230, 255)
        elif cmode == 1:
            base = (90, 200, 255)
        elif cmode == 2:
            base = themed_color(
                self.theme.color_scheme,
                ang / (2 * math.pi) % 1.0,
                ((90, 200, 255),),
                self.theme.color_phase,
            )
        else:
            base = rainbow_color(ang / (2 * math.pi))
        hot = clamp(bright + 0.35 * r)  # streaks go white-hot near the edge
        return scale_color(
            (
                int(base[0] + (255 - base[0]) * hot * 0.5),
                int(base[1] + (255 - base[1]) * hot * 0.5),
                int(base[2] + (255 - base[2]) * hot * 0.5),
            ),
            bright,
        )

    def _draw_flash(self, surface: pygame.Surface, w: int, h: int) -> None:
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((200, 230, 255, int(70 * clamp(self._flash))))
        surface.blit(overlay, (0, 0), special_flags=pygame.BLEND_ADD)
