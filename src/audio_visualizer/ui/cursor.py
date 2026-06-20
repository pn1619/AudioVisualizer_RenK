"""Optional custom mouse cursor drawn over everything (Phase 0B-c).

The App owns one :class:`Cursor`. It is split into two independent choices:

* **shape** — the pointer drawn (``arrow``/``dot``/``ring``/``crosshair``/``star``/
  ``heart``/``diamond``/``triangle``), or ``system`` to keep the plain OS arrow.
* **effect** — an audio-reactive decoration layered on it (``glow``/``comet``/
  ``sparkles``/``pulse``/``ripple``), or ``none``.

Effects render even with the ``system`` shape (e.g. sparkles around the OS arrow).
It reads the shared :class:`Theme` for color and an energy/onset signal for the
beat reaction, is fail-soft (the App wraps the call), drawn last (above the canvas,
controls, HUD, and modals), and honors reduce-motion (shorter trail, fewer sparks,
no beat swell).
"""

from __future__ import annotations

import math
import random

import pygame

from audio_visualizer.config import (
    CURSOR_BASE_RADIUS,
    CURSOR_EFFECT_DEFAULT,
    CURSOR_EFFECTS,
    CURSOR_ENERGY_GAIN,
    CURSOR_PULSE_DECAY,
    CURSOR_PULSE_GAIN,
    CURSOR_RIPPLE_MAX,
    CURSOR_SHAPE_DEFAULT,
    CURSOR_SHAPES,
    CURSOR_SPARK_MAX,
    CURSOR_SPARK_MAX_REDUCED,
    CURSOR_SPARK_PER_MOVE,
    CURSOR_TRAIL_MAX,
    CURSOR_TRAIL_SUBDIV,
    CURSOR_TRAIL_TTL,
    CURSOR_TRAIL_TTL_REDUCED,
    PALETTE,
)
from audio_visualizer.visuals._helpers import clamp, lerp, scale_color, themed_color
from audio_visualizer.visuals.base import Theme

_GLOW_DIAMETER = 64  # radial glow sprite size (scaled per-frame)
_MIN_MOVE = 2.0  # px the mouse must move to shed a spark / extend the trail

# Unit arrow polygon (tip at 0,0, pointing up-left) scaled per-frame by radius.
_ARROW_POLY: tuple[tuple[float, float], ...] = (
    (0.0, 0.0),
    (0.0, 1.9),
    (0.45, 1.45),
    (0.8, 2.2),
    (1.15, 2.05),
    (0.72, 1.32),
    (1.4, 1.32),
)


class Cursor:
    """A switchable, audio-reactive pointer (shape + effect) drawn above all."""

    def __init__(self, theme: Theme, reduce_motion: bool = False) -> None:
        self.shape = CURSOR_SHAPE_DEFAULT
        self.effect = CURSOR_EFFECT_DEFAULT
        self.theme = theme
        self.reduce_motion = reduce_motion
        self._t = 0.0
        self._dt = 1.0 / 60.0
        self._pulse = 0.0
        # Comet trail: recent samples with an age (s); points fade + drop past TTL.
        self._trail: list[dict[str, float]] = []
        self._sparks: list[dict[str, float]] = []
        self._ripples: list[dict[str, float]] = []
        self._rng = random.Random(99)
        self._last_pos: tuple[float, float] | None = None
        self._glow = _build_glow_sprite(_GLOW_DIAMETER)
        self._os_hidden = False

    def set_shape(self, shape: str) -> None:
        if shape in CURSOR_SHAPES:
            self.shape = shape

    def set_effect(self, effect: str) -> None:
        if effect in CURSOR_EFFECTS:
            self.effect = effect
            if effect != "comet":
                self._trail.clear()

    def apply_os_visibility(self, focused: bool) -> None:
        """Hide the OS arrow only for a custom shape while the window has focus."""
        want_hidden = self.shape != "system" and focused
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

    @property
    def is_custom(self) -> bool:
        return self.shape != "system" or self.effect != "none"

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
        """Paint the cursor at ``pos`` (no-op when unfocused or fully default)."""
        self._t += dt
        self._dt = max(1e-4, dt)
        self._pulse = max(0.0, self._pulse - dt * CURSOR_PULSE_DECAY)
        if onset > 0.0 and not self.reduce_motion:
            self._pulse = max(self._pulse, clamp(onset))
        if not focused or not self.is_custom:
            return
        radius = self._radius(energy)
        moved = self._advance_motion(pos)
        if self.effect != "none":
            handler = getattr(self, f"_fx_{self.effect}", None)
            if handler is not None:
                handler(surface, pos, radius, moved, onset)
        if self.shape != "system":
            shape = getattr(self, f"_shape_{self.shape}", None)
            if shape is not None:
                shape(surface, pos, radius)

    def _radius(self, energy: float) -> float:
        swell = 1.0 + CURSOR_ENERGY_GAIN * clamp(energy)
        if self.effect == "pulse" and not self.reduce_motion:
            swell += CURSOR_PULSE_GAIN * self._pulse
        return CURSOR_BASE_RADIUS * swell

    def _advance_motion(self, pos: tuple[int, int]) -> bool:
        """Return True when the mouse just moved (drives spark/trail cadence)."""
        fpos = (float(pos[0]), float(pos[1]))
        moved = self._last_pos is None or math.dist(fpos, self._last_pos) >= _MIN_MOVE
        if moved:
            self._last_pos = fpos
        return moved

    # -- shapes ---------------------------------------------------------------
    def _shape_dot(self, surface: pygame.Surface, pos: tuple[int, int], radius: float) -> None:
        color = self._color(0.5)
        pygame.draw.circle(surface, color, pos, max(2, int(radius)))
        pygame.draw.circle(surface, (255, 255, 255), pos, max(1, int(radius * 0.4)))

    def _shape_ring(self, surface: pygame.Surface, pos: tuple[int, int], radius: float) -> None:
        color = self._color(0.6)
        width = max(2, int(radius * 0.35))
        pygame.draw.circle(surface, color, pos, max(3, int(radius * 1.3)), width)
        pygame.draw.circle(surface, (255, 255, 255), pos, max(1, int(radius * 0.18)))

    def _shape_crosshair(
        self, surface: pygame.Surface, pos: tuple[int, int], radius: float
    ) -> None:
        color = self._color(0.5)
        x, y = pos
        arm = int(radius * 1.8)
        gap = max(2, int(radius * 0.4))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(
                surface, color, (x + dx * gap, y + dy * gap), (x + dx * arm, y + dy * arm), 2
            )
        pygame.draw.circle(surface, color, pos, max(3, int(radius)), 2)
        pygame.draw.circle(surface, (255, 255, 255), pos, 1)

    def _shape_arrow(self, surface: pygame.Surface, pos: tuple[int, int], radius: float) -> None:
        scale = radius * 0.9
        pts = [(pos[0] + px * scale, pos[1] + py * scale) for px, py in _ARROW_POLY]
        pygame.draw.polygon(surface, self._color(0.5), pts)
        pygame.draw.polygon(surface, (255, 255, 255), pts, 1)

    def _shape_star(self, surface: pygame.Surface, pos: tuple[int, int], radius: float) -> None:
        self._draw_star_poly(surface, pos, radius * 1.5, radius * 0.62, 5, self._t * 0.6)

    def _shape_diamond(self, surface: pygame.Surface, pos: tuple[int, int], radius: float) -> None:
        r = radius * 1.4
        x, y = pos
        pts = [(x, y - r), (x + r * 0.72, y), (x, y + r), (x - r * 0.72, y)]
        pygame.draw.polygon(surface, self._color(0.55), pts)
        pygame.draw.polygon(surface, (255, 255, 255), pts, 1)

    def _shape_triangle(self, surface: pygame.Surface, pos: tuple[int, int], radius: float) -> None:
        r = radius * 1.5
        x, y = pos
        pts = [
            (x, y - r),
            (x + r * 0.87, y + r * 0.5),
            (x - r * 0.87, y + r * 0.5),
        ]
        pygame.draw.polygon(surface, self._color(0.45), pts)
        pygame.draw.polygon(surface, (255, 255, 255), pts, 1)

    def _shape_heart(self, surface: pygame.Surface, pos: tuple[int, int], radius: float) -> None:
        color = self._color(0.0)
        scale = radius / 15.0
        x0, y0 = pos
        pts: list[tuple[float, float]] = []
        steps = 22
        for i in range(steps):
            a = math.tau * i / steps
            hx = 16 * math.sin(a) ** 3
            hy = 13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)
            pts.append((x0 + hx * scale, y0 - hy * scale))
        pygame.draw.polygon(surface, color, pts)
        pygame.draw.polygon(surface, (255, 255, 255), pts, 1)

    def _draw_star_poly(
        self,
        surface: pygame.Surface,
        pos: tuple[int, int],
        outer: float,
        inner: float,
        points: int,
        rot: float,
    ) -> None:
        x0, y0 = pos
        verts: list[tuple[float, float]] = []
        for i in range(points * 2):
            r = outer if i % 2 == 0 else inner
            a = rot + math.pi * i / points
            verts.append((x0 + math.cos(a) * r, y0 + math.sin(a) * r))
        pygame.draw.polygon(surface, self._color(0.7), verts)
        pygame.draw.polygon(surface, (255, 255, 255), verts, 1)

    # -- effects --------------------------------------------------------------
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

    def _fx_glow(
        self,
        surface: pygame.Surface,
        pos: tuple[int, int],
        radius: float,
        moved: bool,
        onset: float,
    ) -> None:
        bright = 0.45 + 0.55 * self._pulse
        color = scale_color(self._color(0.5), bright)
        self._blit_glow(surface, pos[0], pos[1], radius * (2.2 + self._pulse), color)

    def _fx_comet(
        self,
        surface: pygame.Surface,
        pos: tuple[int, int],
        radius: float,
        moved: bool,
        onset: float,
    ) -> None:
        ttl = CURSOR_TRAIL_TTL_REDUCED if self.reduce_motion else CURSOR_TRAIL_TTL
        self._age_trail(pos, moved, ttl)
        n = len(self._trail)
        if n < 2:
            return
        pts = [(p["x"], p["y"]) for p in self._trail]  # oldest -> newest
        alphas = [clamp(1.0 - p["age"] / ttl) for p in self._trail]
        layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        pad = [pts[0], *pts, pts[-1]]  # clamp ends for Catmull-Rom
        for i in range(1, len(pad) - 2):
            self._draw_comet_segment(layer, pad[i - 1 : i + 3], i - 1, n, alphas, radius)
        surface.blit(layer, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _age_trail(self, pos: tuple[int, int], moved: bool, ttl: float) -> None:
        """Age existing trail points, drop expired ones, and sample the new pos."""
        for p in self._trail:
            p["age"] += self._dt
        if moved or not self._trail:
            self._trail.append({"x": float(pos[0]), "y": float(pos[1]), "age": 0.0})
        self._trail = [p for p in self._trail if p["age"] < ttl][-CURSOR_TRAIL_MAX:]

    def _draw_comet_segment(
        self,
        layer: pygame.Surface,
        cps: list[tuple[float, float]],
        idx: int,
        n: int,
        alphas: list[float],
        radius: float,
    ) -> None:
        """Draw one Catmull-Rom span (between cps[1] and cps[2]) with taper + fade."""
        p0, p1, p2, p3 = cps
        a0, a1 = alphas[idx], alphas[min(idx + 1, n - 1)]
        w0 = radius * 0.85 * (idx / max(1, n - 1))
        w1 = radius * 0.85 * ((idx + 1) / max(1, n - 1))
        color = self._color(idx / n)
        prev = p1
        for j in range(1, CURSOR_TRAIL_SUBDIV + 1):
            t = j / CURSOR_TRAIL_SUBDIV
            cur = _catmull_rom(p0, p1, p2, p3, t)
            alpha = int(200 * lerp(a0, a1, t))
            width = max(1, int(lerp(w0, w1, t)))
            if alpha > 0:
                pygame.draw.line(layer, (*color, alpha), prev, cur, width)
            prev = cur

    def _fx_sparkles(
        self,
        surface: pygame.Surface,
        pos: tuple[int, int],
        radius: float,
        moved: bool,
        onset: float,
    ) -> None:
        self._advance_sparks()
        if moved or self._pulse > 0.2:
            self._spawn_sparks(pos)
        if not self._sparks:
            return
        layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        for s in self._sparks:
            life = s["life"]
            color = self._color(s["hue"])
            alpha = int(220 * clamp(life))
            r = max(1, int(2 + 3 * life))
            pygame.draw.circle(layer, (*color, alpha), (int(s["x"]), int(s["y"])), r)
        surface.blit(layer, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _fx_pulse(
        self,
        surface: pygame.Surface,
        pos: tuple[int, int],
        radius: float,
        moved: bool,
        onset: float,
    ) -> None:
        # The beat swell is applied to ``radius`` already; add a soft halo so the
        # throb reads even on a small shape (and when shape == system).
        if self._pulse <= 0.02:
            return
        color = scale_color(self._color(0.5), self._pulse)
        self._blit_glow(surface, pos[0], pos[1], radius * 2.0, color)

    def _fx_ripple(
        self,
        surface: pygame.Surface,
        pos: tuple[int, int],
        radius: float,
        moved: bool,
        onset: float,
    ) -> None:
        if onset > 0.0 and not self.reduce_motion and len(self._ripples) < CURSOR_RIPPLE_MAX:
            self._ripples.append({"x": float(pos[0]), "y": float(pos[1]), "life": 1.0})
        if not self._ripples:
            return
        layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        for rp in self._ripples:
            rp["life"] -= 1.0 / 45.0
            r = int(radius + (1.0 - rp["life"]) * radius * 9.0)
            alpha = int(180 * clamp(rp["life"]))
            color = self._color(0.6)
            pygame.draw.circle(layer, (*color, alpha), (int(rp["x"]), int(rp["y"])), max(2, r), 2)
        self._ripples = [rp for rp in self._ripples if rp["life"] > 0.0]
        surface.blit(layer, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

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


def _catmull_rom(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    """Centripetal-ish Catmull-Rom point at ``t`` in 0..1 between ``p1`` and ``p2``."""
    t2 = t * t
    t3 = t2 * t
    out: list[float] = []
    for a, b, c, d in zip(p0, p1, p2, p3, strict=True):
        out.append(
            0.5
            * (
                (2 * b)
                + (-a + c) * t
                + (2 * a - 5 * b + 4 * c - d) * t2
                + (-a + 3 * b - 3 * c + d) * t3
            )
        )
    return (out[0], out[1])


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
