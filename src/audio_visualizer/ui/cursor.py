"""Optional custom mouse cursor drawn over everything (Phase 0B-c).

The App owns one :class:`Cursor`. ``system`` keeps the normal OS arrow (no-op);
the other modes hide the OS cursor and paint a themed, audio-reactive cursor at
the mouse position — a glowing dot, a pulsing ring, a comet with a fading trail,
or a sparkle emitter. It reads the shared :class:`Theme` for color and a small
energy/onset signal for the beat pulse, and is fail-soft (the App wraps the call).

Drawn last (above the canvas, controls, HUD, and modals) so it behaves like a
real pointer. Honors reduce-motion (shorter trail, fewer sparks, calmer pulse).
"""

from __future__ import annotations

import math
import random
from collections import deque

import pygame

from audio_visualizer.config import (
    CURSOR_BASE_RADIUS,
    CURSOR_ENERGY_GAIN,
    CURSOR_MODE_DEFAULT,
    CURSOR_MODES,
    CURSOR_PULSE_DECAY,
    CURSOR_PULSE_GAIN,
    CURSOR_SPARK_MAX,
    CURSOR_SPARK_MAX_REDUCED,
    CURSOR_SPARK_PER_MOVE,
    CURSOR_TRAIL_LEN,
    CURSOR_TRAIL_LEN_REDUCED,
    PALETTE,
)
from audio_visualizer.visuals._helpers import clamp, scale_color, themed_color
from audio_visualizer.visuals.base import Theme

_GLOW_DIAMETER = 64  # radial glow sprite size (scaled per-frame)
_MIN_MOVE = 2.0  # px the mouse must move to shed a spark / extend the trail


class Cursor:
    """A switchable, audio-reactive pointer composited above everything."""

    def __init__(self, theme: Theme, reduce_motion: bool = False) -> None:
        self.mode = CURSOR_MODE_DEFAULT
        self.theme = theme
        self.reduce_motion = reduce_motion
        self._t = 0.0
        self._pulse = 0.0
        self._trail: deque[tuple[float, float]] = deque(maxlen=CURSOR_TRAIL_LEN)
        self._sparks: list[dict[str, float]] = []
        self._rng = random.Random(99)
        self._last_pos: tuple[float, float] | None = None
        self._glow = _build_glow_sprite(_GLOW_DIAMETER)
        self._os_hidden = False

    def set_mode(self, mode: str) -> None:
        if mode in CURSOR_MODES:
            self.mode = mode
            if mode == "system":  # leaving a custom mode clears its transient state
                self._trail.clear()
                self._sparks.clear()

    def apply_os_visibility(self, focused: bool) -> None:
        """Hide the OS arrow only for a custom mode while the window has focus."""
        want_hidden = self.mode != "system" and focused
        if want_hidden == self._os_hidden:
            return
        try:
            pygame.mouse.set_visible(not want_hidden)
            self._os_hidden = want_hidden
        except pygame.error:
            pass

    def release(self) -> None:
        """Restore the OS cursor (call on shutdown / when disabling)."""
        try:
            pygame.mouse.set_visible(True)
        except pygame.error:
            pass
        self._os_hidden = False

    def _color(self, t: float = 0.5) -> tuple[int, int, int]:
        return themed_color(self.theme.color_scheme, t, PALETTE, self.theme.color_phase)

    def draw(
        self,
        surface: pygame.Surface,
        pos: tuple[int, int],
        focused: bool,
        energy: float,
        onset: float,
        dt: float,
    ) -> None:
        """Paint the cursor at ``pos`` (no-op for ``system`` or an unfocused window)."""
        self._t += dt
        self._pulse = max(0.0, self._pulse - dt * CURSOR_PULSE_DECAY)
        if onset > 0.0 and not self.reduce_motion:
            self._pulse = max(self._pulse, clamp(onset))
        if self.mode == "system" or not focused:
            return
        radius = self._radius(energy)
        moved = self._advance_motion(pos)
        handler = getattr(self, f"_draw_{self.mode}", None)
        if handler is not None:
            handler(surface, pos, radius, moved)

    def _radius(self, energy: float) -> float:
        pulse = 0.0 if self.reduce_motion else self._pulse
        swell = 1.0 + CURSOR_PULSE_GAIN * pulse + CURSOR_ENERGY_GAIN * clamp(energy)
        return CURSOR_BASE_RADIUS * swell

    def _advance_motion(self, pos: tuple[int, int]) -> bool:
        """Update the trail/spawn cadence; return True when the mouse just moved."""
        fpos = (float(pos[0]), float(pos[1]))
        moved = self._last_pos is None or math.dist(fpos, self._last_pos) >= _MIN_MOVE
        cap = CURSOR_TRAIL_LEN_REDUCED if self.reduce_motion else CURSOR_TRAIL_LEN
        if self._trail.maxlen != cap:
            self._trail = deque(self._trail, maxlen=cap)
        if moved:
            self._trail.append(fpos)
            self._last_pos = fpos
        return moved

    # -- glow helper ----------------------------------------------------------
    def _blit_glow(
        self,
        surface: pygame.Surface,
        x: float,
        y: float,
        radius: float,
        color: tuple[int, int, int],
    ) -> None:
        size = max(2, int(radius * 2.4))
        sprite = pygame.transform.smoothscale(self._glow, (size, size))
        sprite.fill((*color, 255), special_flags=pygame.BLEND_RGB_MULT)
        surface.blit(
            sprite, (int(x - size / 2), int(y - size / 2)), special_flags=pygame.BLEND_RGB_ADD
        )

    # -- modes ----------------------------------------------------------------
    def _draw_dot(
        self, surface: pygame.Surface, pos: tuple[int, int], radius: float, moved: bool
    ) -> None:
        color = self._color(0.5)
        self._blit_glow(surface, pos[0], pos[1], radius * 1.6, scale_color(color, 0.7))
        pygame.draw.circle(surface, color, pos, max(2, int(radius)))
        pygame.draw.circle(surface, (255, 255, 255), pos, max(1, int(radius * 0.4)))

    def _draw_ring(
        self, surface: pygame.Surface, pos: tuple[int, int], radius: float, moved: bool
    ) -> None:
        color = self._color(0.6)
        self._blit_glow(surface, pos[0], pos[1], radius * 1.4, scale_color(color, 0.5))
        width = max(2, int(radius * 0.35))
        pygame.draw.circle(surface, color, pos, max(3, int(radius * 1.3)), width)
        pygame.draw.circle(surface, (255, 255, 255), pos, max(1, int(radius * 0.18)))

    def _draw_comet(
        self, surface: pygame.Surface, pos: tuple[int, int], radius: float, moved: bool
    ) -> None:
        pts = list(self._trail)
        n = len(pts)
        if n >= 2:
            layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            for i in range(1, n):
                frac = i / n  # older = dimmer + thinner
                color = self._color(frac)
                alpha = int(180 * frac)
                width = max(1, int(radius * 0.7 * frac))
                pygame.draw.line(layer, (*color, alpha), pts[i - 1], pts[i], width)
            surface.blit(layer, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        self._draw_dot(surface, pos, radius, moved)

    def _draw_spark(
        self, surface: pygame.Surface, pos: tuple[int, int], radius: float, moved: bool
    ) -> None:
        self._advance_sparks()
        if moved or self._pulse > 0.2:
            self._spawn_sparks(pos)
        layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        for s in self._sparks:
            life = s["life"]
            color = self._color(s["hue"])
            alpha = int(220 * clamp(life))
            r = max(1, int(2 + 3 * life))
            pygame.draw.circle(layer, (*color, alpha), (int(s["x"]), int(s["y"])), r)
        surface.blit(layer, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        self._draw_dot(surface, pos, radius * 0.8, moved)

    def _advance_sparks(self) -> None:
        dt = 1.0 / 60.0
        for s in self._sparks:
            s["x"] += s["vx"] * dt
            s["y"] += s["vy"] * dt
            s["vy"] += 140.0 * dt  # gentle gravity
            s["life"] -= dt / 0.7
        self._sparks = [s for s in self._sparks if s["life"] > 0.0]

    def _spawn_sparks(self, pos: tuple[int, int]) -> None:
        cap = CURSOR_SPARK_MAX_REDUCED if self.reduce_motion else CURSOR_SPARK_MAX
        count = max(1, CURSOR_SPARK_PER_MOVE + int(self._pulse * 4))
        for _ in range(count):
            if len(self._sparks) >= cap:
                break
            ang = self._rng.uniform(0, math.tau)
            speed = self._rng.uniform(20.0, 90.0) * (1.0 + self._pulse)
            self._sparks.append(
                {
                    "x": float(pos[0]),
                    "y": float(pos[1]),
                    "vx": math.cos(ang) * speed,
                    "vy": math.sin(ang) * speed - 30.0,
                    "life": 1.0,
                    "hue": self._rng.random(),
                }
            )


def _build_glow_sprite(diameter: int) -> pygame.Surface:
    """A white radial sprite (bright center fading to black) for additive glow."""
    surf = pygame.Surface((diameter, diameter))
    cx = cy = diameter / 2.0
    for y in range(diameter):
        for x in range(diameter):
            d = math.hypot(x - cx, y - cy) / cx
            v = max(0, int((1.0 - min(1.0, d)) ** 2 * 255))
            surf.set_at((x, y), (v, v, v))
    return surf
