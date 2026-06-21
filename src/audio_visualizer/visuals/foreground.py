"""Global foreground layer drawn *on top of* every visual mode.

Counterpart to :class:`~audio_visualizer.visuals.background.Background`: the App
owns one :class:`Foreground` and draws it as the **last** canvas layer (above the
mode + logo, below the UI chrome), so dramatic, beat-triggered effects punctuate
the scene. Effects:

* ``off``       - the default no-op.
* ``lightning`` - on a beat, jagged forked bolt(s) strike across the canvas plus a
                  brief, brightness-capped flash; both fade within a fraction of a
                  second.
* ``flames``    - hot particles shot inward from the chosen edge(s) on each beat
                  (plus a low ambient trickle), rendered with additive glow.
* ``rain``      - a continuously maintained field of directional streaks (storm);
                  each beat injects a heavier gust.
* ``meteors``   - a few fast streaks per beat arcing from an edge, each trailing a
                  tapered glow.
* ``shockwave`` - expanding ring(s) on each beat from screen-center (or the chosen
                  edge's midpoint).

Two global knobs apply to every effect: ``intensity`` (burst size/count/brightness)
and ``opacity`` (overall strength). ``direction`` aims the directional effects.
Like the background, this is a read-only render helper (frame + surface + dt +
Theme), fail-soft (the App wraps the call), and bounds its particle lists.

Photosensitivity: the lightning flash alpha is hard-capped (``FG_FLASH_ALPHA_CAP``)
and ``reduce_motion`` further halves it and caps bolt/particle counts.
"""

from __future__ import annotations

import math
import random

import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import (
    FG_DIRECTION_DEFAULT,
    FG_FLAME_AMBIENT,
    FG_FLAME_BURST,
    FG_FLAME_DRAG,
    FG_FLAME_LIFE,
    FG_FLAME_MAX,
    FG_FLAME_PALETTE,
    FG_FLAME_SIZE,
    FG_FLAME_SPEED,
    FG_FLAME_SPREAD,
    FG_FLASH_ALPHA,
    FG_FLASH_ALPHA_CAP,
    FG_FLASH_DECAY,
    FG_INTENSITY_DEFAULT,
    FG_LIGHTNING_BOLTS,
    FG_LIGHTNING_CORE,
    FG_LIGHTNING_FORK_CHANCE,
    FG_LIGHTNING_GLOW,
    FG_LIGHTNING_JITTER,
    FG_LIGHTNING_LIFE,
    FG_LIGHTNING_SUBDIV,
    FG_METEOR_BURST,
    FG_METEOR_CORE,
    FG_METEOR_GLOW,
    FG_METEOR_LIFE,
    FG_METEOR_MAX,
    FG_METEOR_SIZE,
    FG_METEOR_SPEED,
    FG_METEOR_TANGENT,
    FG_METEOR_TRAIL,
    FG_MODE_DEFAULT,
    FG_OPACITY_DEFAULT,
    FG_RAIN_COLOR,
    FG_RAIN_GUST,
    FG_RAIN_MAX,
    FG_RAIN_SPEED,
    FG_RAIN_STREAK,
    FG_RAIN_TARGET,
    FG_RAIN_WIND,
    FG_SHOCK_COLOR,
    FG_SHOCK_LIFE,
    FG_SHOCK_MAX,
    FG_SHOCK_REACH,
    FG_SHOCK_RINGS,
    FG_SHOCK_WIDTH,
    FG_TRIGGER_COOLDOWN,
    ONSET_THRESHOLD,
)
from audio_visualizer.visuals._helpers import clamp, palette_color
from audio_visualizer.visuals.base import Theme

Point = tuple[float, float]
_EDGES = ("top", "bottom", "left", "right")


class Foreground:
    """A switchable, beat-triggered overlay composited above the active mode."""

    def __init__(self, theme: Theme, reduce_motion: bool = False) -> None:
        self.mode = FG_MODE_DEFAULT
        self.intensity = FG_INTENSITY_DEFAULT
        self.direction = FG_DIRECTION_DEFAULT
        self.opacity = FG_OPACITY_DEFAULT
        self.theme = theme
        self.reduce_motion = reduce_motion
        self._t = 0.0
        self._dt = 0.0
        self._cooldown = 0.0  # seconds until the next beat may spawn
        self._rng = random.Random(20240620)
        self._bolts: list[dict[str, object]] = []  # {points, forks, age}
        self._flash = 0.0  # full-screen flash envelope (0..cap)
        self._flames: list[dict[str, float]] = []  # {x,y,vx,vy,age,life,size}
        self._emit_accum = 0.0  # fractional ambient-emission carry
        self._rain: list[dict[str, float]] = []  # {x,y,vx,vy}
        self._meteors: list[dict[str, object]] = []  # {x,y,vx,vy,age,trail}
        self._shocks: list[dict[str, float]] = []  # {cx,cy,age}

    # -- public ----------------------------------------------------------------
    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        """Composite the current foreground effect onto ``surface`` (no-op for off)."""
        self._t += dt
        self._dt = dt
        self._cooldown = max(0.0, self._cooldown - dt)
        beat = self._beat(frame)
        handler = getattr(self, f"_draw_{self.mode}", None)
        if handler is not None:
            handler(surface, frame, beat)

    def _beat(self, frame: AnalysisFrame | None) -> float:
        """Onset strength (0..1) when a fresh beat clears the cooldown, else 0."""
        if frame is None or frame.is_silent or self._cooldown > 0.0:
            return 0.0
        if frame.onset < ONSET_THRESHOLD:
            return 0.0
        self._cooldown = FG_TRIGGER_COOLDOWN
        return clamp(float(frame.onset))

    # -- shared helpers --------------------------------------------------------
    def _pick_edge(self) -> str:
        if self.direction in _EDGES:
            return self.direction
        return self._rng.choice(_EDGES)

    def _add_layer(self, surface: pygame.Surface) -> pygame.Surface:
        return pygame.Surface(surface.get_size(), pygame.SRCALPHA)

    # -- lightning -------------------------------------------------------------
    def _draw_lightning(
        self, surface: pygame.Surface, frame: AnalysisFrame | None, beat: float
    ) -> None:
        if beat > 0.0:
            self._spawn_bolts(surface.get_size(), beat)
        for bolt in self._bolts:
            bolt["age"] = float(bolt["age"]) + self._dt  # type: ignore[arg-type]
        self._bolts = [b for b in self._bolts if float(b["age"]) < FG_LIGHTNING_LIFE]  # type: ignore[arg-type]
        self._flash = max(0.0, self._flash - self._dt * FG_FLASH_DECAY * FG_FLASH_ALPHA_CAP)
        if not self._bolts and self._flash <= 0.5:
            return
        layer = self._add_layer(surface)
        if self._flash > 0.5:
            flash_a = int(min(self._flash, FG_FLASH_ALPHA_CAP) * self.opacity)
            layer.fill((*FG_LIGHTNING_CORE, flash_a))
        for bolt in self._bolts:
            self._draw_bolt(layer, bolt)
        surface.blit(layer, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _spawn_bolts(self, size: tuple[int, int], beat: float) -> None:
        count = max(1, int(round(FG_LIGHTNING_BOLTS * self.intensity * beat)))
        if self.reduce_motion:
            count = 1
        edges = _EDGES if self.direction == "all" else [self._pick_edge() for _ in range(count)]
        for edge in edges[: max(1, count)]:
            start, end = self._bolt_endpoints(size, edge)
            points = self._jagged(start, end, FG_LIGHTNING_JITTER)
            forks = self._make_forks(points, size)
            self._bolts.append({"points": points, "forks": forks, "age": 0.0})
        flash = FG_FLASH_ALPHA * self.intensity * (0.6 + 0.4 * beat)
        if self.reduce_motion:
            flash *= 0.5
        self._flash = min(max(self._flash, flash), FG_FLASH_ALPHA_CAP)

    def _bolt_endpoints(self, size: tuple[int, int], edge: str) -> tuple[Point, Point]:
        w, h = size
        r = self._rng
        if edge in ("top", "bottom"):
            sx, ex = r.uniform(0, w), r.uniform(w * 0.2, w * 0.8)
            return ((sx, 0.0), (ex, float(h))) if edge == "top" else ((sx, float(h)), (ex, 0.0))
        sy, ey = r.uniform(0, h), r.uniform(h * 0.2, h * 0.8)
        return ((0.0, sy), (float(w), ey)) if edge == "left" else ((float(w), sy), (0.0, ey))

    def _jagged(self, p0: Point, p1: Point, jitter: float) -> list[Point]:
        """Midpoint-displacement path from ``p0`` to ``p1`` (jagged lightning)."""
        points: list[Point] = [p0, p1]
        for _ in range(FG_LIGHTNING_SUBDIV):
            refined: list[Point] = []
            for a, b in zip(points, points[1:], strict=False):
                refined.append(a)
                dx, dy = b[0] - a[0], b[1] - a[1]
                length = math.hypot(dx, dy) or 1.0
                nx, ny = -dy / length, dx / length
                off = (self._rng.random() - 0.5) * jitter * length
                refined.append(((a[0] + b[0]) / 2 + nx * off, (a[1] + b[1]) / 2 + ny * off))
            refined.append(points[-1])
            points = refined
            jitter *= 0.6
        return points

    def _make_forks(self, points: list[Point], size: tuple[int, int]) -> list[list[Point]]:
        if self._rng.random() > FG_LIGHTNING_FORK_CHANCE or len(points) < 4:
            return []
        i = self._rng.randrange(len(points) // 3, 2 * len(points) // 3)
        base = points[i]
        end = points[min(len(points) - 1, i + len(points) // 4)]
        target = (end[0] + self._rng.uniform(-0.15, 0.15) * size[0], end[1])
        return [self._jagged(base, target, FG_LIGHTNING_JITTER * 1.4)]

    def _draw_bolt(self, layer: pygame.Surface, bolt: dict[str, object]) -> None:
        age = bolt["age"]
        points = bolt["points"]
        forks = bolt["forks"]
        if not (isinstance(age, float) and isinstance(points, list) and isinstance(forks, list)):
            return
        fade = clamp(1.0 - age / FG_LIGHTNING_LIFE)
        glow_a = int(150 * fade * self.opacity)
        core_a = int(255 * fade * self.opacity)
        for pts in [points, *forks]:
            if len(pts) >= 2:
                pygame.draw.lines(layer, (*FG_LIGHTNING_GLOW, glow_a), False, pts, 6)
                pygame.draw.lines(layer, (*FG_LIGHTNING_CORE, core_a), False, pts, 2)

    # -- flames ----------------------------------------------------------------
    def _draw_flames(
        self, surface: pygame.Surface, frame: AnalysisFrame | None, beat: float
    ) -> None:
        size = surface.get_size()
        self._emit_flames(size, beat)
        self._step_flames()
        if not self._flames:
            return
        layer = self._add_layer(surface)
        for p in self._flames:
            self._draw_flame(layer, p)
        surface.blit(layer, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _emit_flames(self, size: tuple[int, int], beat: float) -> None:
        ambient = 0.0 if self.reduce_motion else FG_FLAME_AMBIENT
        self._emit_accum += ambient * self.intensity * self._dt
        n = int(self._emit_accum)
        self._emit_accum -= n
        if beat > 0.0:
            burst = int(FG_FLAME_BURST * self.intensity * (0.5 + beat))
            n += burst // 2 if self.reduce_motion else burst
        edges = _EDGES if self.direction == "all" else None
        for k in range(n):
            edge = edges[k % len(edges)] if edges else self._pick_edge()
            self._flames.append(self._spawn_flame(size, edge))
        if len(self._flames) > FG_FLAME_MAX:
            del self._flames[: len(self._flames) - FG_FLAME_MAX]

    def _spawn_flame(self, size: tuple[int, int], edge: str) -> dict[str, float]:
        w, h = size
        r = self._rng
        speed = FG_FLAME_SPEED * (0.6 + 0.6 * r.random())
        spread = FG_FLAME_SPEED * FG_FLAME_SPREAD
        if edge in ("top", "bottom"):
            x, vx = r.uniform(0, w), r.uniform(-spread, spread)
            y, vy = (0.0, speed) if edge == "top" else (float(h), -speed)
        else:
            y, vy = r.uniform(0, h), r.uniform(-spread, spread)
            x, vx = (0.0, speed) if edge == "left" else (float(w), -speed)
        return {
            "x": x,
            "y": y,
            "vx": vx,
            "vy": vy,
            "age": 0.0,
            "life": FG_FLAME_LIFE * (0.7 + 0.6 * r.random()),
            "size": FG_FLAME_SIZE * (0.6 + 0.8 * r.random()),
        }

    def _step_flames(self) -> None:
        drag = math.exp(-FG_FLAME_DRAG * self._dt)
        alive: list[dict[str, float]] = []
        for p in self._flames:
            p["age"] += self._dt
            if p["age"] >= p["life"]:
                continue
            p["x"] += p["vx"] * self._dt
            p["y"] += p["vy"] * self._dt
            p["vx"] *= drag
            p["vy"] = p["vy"] * drag - 40.0 * self._dt  # gentle buoyancy (rise)
            alive.append(p)
        self._flames = alive

    def _draw_flame(self, layer: pygame.Surface, p: dict[str, float]) -> None:
        frac = clamp(p["age"] / p["life"])
        color = palette_color(FG_FLAME_PALETTE, frac)
        radius = max(1, int(p["size"] * (1.0 - 0.6 * frac)))
        alpha = int(170 * (1.0 - frac) * self.opacity)
        if alpha <= 0:
            return
        pygame.draw.circle(layer, (*color, alpha), (int(p["x"]), int(p["y"])), radius)
        pygame.draw.circle(
            layer, (*color, alpha // 2), (int(p["x"]), int(p["y"])), max(1, radius * 2)
        )

    # -- rain / storm ----------------------------------------------------------
    def _draw_rain(self, surface: pygame.Surface, frame: AnalysisFrame | None, beat: float) -> None:
        size = surface.get_size()
        self._step_rain(size, beat)
        if not self._rain:
            return
        layer = self._add_layer(surface)
        sx, sy = FG_RAIN_STREAK, FG_RAIN_STREAK
        alpha = int(150 * self.opacity)
        for d in self._rain:
            head = (int(d["x"]), int(d["y"]))
            tail = (int(d["x"] - d["vx"] * sx), int(d["y"] - d["vy"] * sy))
            pygame.draw.line(layer, (*FG_RAIN_COLOR, alpha), tail, head, 1)
        surface.blit(layer, (0, 0))

    def _rain_vec(self) -> tuple[float, float]:
        """Unit fall direction: random/all/top read as downward (classic rain)."""
        return {
            "bottom": (0.0, -1.0),
            "left": (1.0, 0.0),
            "right": (-1.0, 0.0),
        }.get(self.direction, (0.0, 1.0))

    def _step_rain(self, size: tuple[int, int], beat: float) -> None:
        w, h = size
        alive: list[dict[str, float]] = []
        for d in self._rain:
            d["x"] += d["vx"] * self._dt
            d["y"] += d["vy"] * self._dt
            if -80 <= d["x"] <= w + 80 and -80 <= d["y"] <= h + 80:
                alive.append(d)
        self._rain = alive
        target = int(FG_RAIN_TARGET * self.intensity)
        if self.reduce_motion:
            target //= 2
        if beat > 0.0:
            target += int(FG_RAIN_GUST * self.intensity * beat)
        target = min(target, FG_RAIN_MAX)
        vec = self._rain_vec()
        while len(self._rain) < target:
            self._rain.append(self._spawn_rain(size, vec))

    def _spawn_rain(self, size: tuple[int, int], vec: tuple[float, float]) -> dict[str, float]:
        w, h = size
        r = self._rng
        speed = FG_RAIN_SPEED * (0.85 + 0.4 * r.random())  # depth variation
        wind = (r.random() - 0.5) * 2 * FG_RAIN_WIND * speed
        if vec[1] > 0:
            x, y, vx, vy = r.uniform(0, w), r.uniform(-h, 0), wind, speed
        elif vec[1] < 0:
            x, y, vx, vy = r.uniform(0, w), r.uniform(h, 2 * h), wind, -speed
        elif vec[0] > 0:
            x, y, vx, vy = r.uniform(-w, 0), r.uniform(0, h), speed, wind
        else:
            x, y, vx, vy = r.uniform(w, 2 * w), r.uniform(0, h), -speed, wind
        return {"x": x, "y": y, "vx": vx, "vy": vy}

    # -- meteors / shooting stars ----------------------------------------------
    def _draw_meteors(
        self, surface: pygame.Surface, frame: AnalysisFrame | None, beat: float
    ) -> None:
        if beat > 0.0:
            self._spawn_meteors(surface.get_size(), beat)
        self._step_meteors(surface.get_size())
        if not self._meteors:
            return
        layer = self._add_layer(surface)
        for m in self._meteors:
            self._draw_meteor(layer, m)
        surface.blit(layer, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _spawn_meteors(self, size: tuple[int, int], beat: float) -> None:
        count = max(1, int(round(FG_METEOR_BURST * self.intensity * (0.5 + beat))))
        if self.reduce_motion:
            count = 1
        edges = _EDGES if self.direction == "all" else [self._pick_edge() for _ in range(count)]
        for edge in edges[:count]:
            self._meteors.append(self._spawn_meteor(size, edge))
        if len(self._meteors) > FG_METEOR_MAX:
            del self._meteors[: len(self._meteors) - FG_METEOR_MAX]

    def _spawn_meteor(self, size: tuple[int, int], edge: str) -> dict[str, object]:
        w, h = size
        r = self._rng
        speed = FG_METEOR_SPEED * (0.8 + 0.4 * r.random())
        tan = r.uniform(-FG_METEOR_TANGENT, FG_METEOR_TANGENT) * speed
        if edge == "top":
            x, y, vx, vy = r.uniform(0, w), -20.0, tan, speed
        elif edge == "bottom":
            x, y, vx, vy = r.uniform(0, w), h + 20.0, tan, -speed
        elif edge == "left":
            x, y, vx, vy = -20.0, r.uniform(0, h), speed, tan
        else:
            x, y, vx, vy = w + 20.0, r.uniform(0, h), -speed, tan
        return {"x": x, "y": y, "vx": vx, "vy": vy, "age": 0.0, "trail": []}

    def _step_meteors(self, size: tuple[int, int]) -> None:
        w, h = size
        alive: list[dict[str, object]] = []
        for m in self._meteors:
            x = float(m["x"]) + float(m["vx"]) * self._dt  # type: ignore[arg-type]
            y = float(m["y"]) + float(m["vy"]) * self._dt  # type: ignore[arg-type]
            age = float(m["age"]) + self._dt  # type: ignore[arg-type]
            m["x"], m["y"], m["age"] = x, y, age
            trail = m["trail"]
            if isinstance(trail, list):
                trail.append((x, y))
                if len(trail) > FG_METEOR_TRAIL:
                    del trail[0]
            if age < FG_METEOR_LIFE and -60 <= x <= w + 60 and -60 <= y <= h + 60:
                alive.append(m)
        self._meteors = alive

    def _draw_meteor(self, layer: pygame.Surface, m: dict[str, object]) -> None:
        trail = m["trail"]
        if not isinstance(trail, list) or len(trail) < 2:
            return
        n = len(trail)
        for i in range(1, n):
            frac = i / n  # tail (dim) -> head (bright)
            a = int(180 * frac * self.opacity)
            if a <= 0:
                continue
            width = max(1, int(frac * 3))
            pygame.draw.line(layer, (*FG_METEOR_GLOW, a), trail[i - 1], trail[i], width)
        head = (int(float(m["x"])), int(float(m["y"])))  # type: ignore[arg-type]
        core_a = int(255 * self.opacity)
        pygame.draw.circle(layer, (*FG_METEOR_GLOW, core_a // 2), head, int(FG_METEOR_SIZE * 2))
        pygame.draw.circle(layer, (*FG_METEOR_CORE, core_a), head, max(1, int(FG_METEOR_SIZE)))

    # -- shockwave -------------------------------------------------------------
    def _draw_shockwave(
        self, surface: pygame.Surface, frame: AnalysisFrame | None, beat: float
    ) -> None:
        size = surface.get_size()
        if beat > 0.0:
            self._spawn_shocks(size, beat)
        for s in self._shocks:
            s["age"] += self._dt
        self._shocks = [s for s in self._shocks if s["age"] < FG_SHOCK_LIFE]
        if not self._shocks:
            return
        max_r = math.hypot(*size) * FG_SHOCK_REACH
        layer = self._add_layer(surface)
        for s in self._shocks:
            self._draw_shock(layer, s, max_r)
        surface.blit(layer, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _spawn_shocks(self, size: tuple[int, int], beat: float) -> None:
        count = max(1, int(round(FG_SHOCK_RINGS * self.intensity * beat)))
        if self.reduce_motion:
            count = 1
        cx, cy = self._origin(size)
        for _ in range(count):
            self._shocks.append({"cx": cx, "cy": cy, "age": 0.0})
        if len(self._shocks) > FG_SHOCK_MAX:
            del self._shocks[: len(self._shocks) - FG_SHOCK_MAX]

    def _origin(self, size: tuple[int, int]) -> tuple[float, float]:
        """Ring origin: the chosen edge's midpoint, else screen center."""
        w, h = size
        return {
            "top": (w / 2, 0.0),
            "bottom": (w / 2, float(h)),
            "left": (0.0, h / 2),
            "right": (float(w), h / 2),
        }.get(self.direction, (w / 2, h / 2))

    def _draw_shock(self, layer: pygame.Surface, s: dict[str, float], max_r: float) -> None:
        frac = clamp(s["age"] / FG_SHOCK_LIFE)
        radius = int(max_r * frac)
        if radius < 2:
            return
        width = max(1, int(FG_SHOCK_WIDTH * (1.0 - frac)))
        alpha = int(200 * (1.0 - frac) * self.opacity)
        if alpha <= 0:
            return
        center = (int(s["cx"]), int(s["cy"]))
        pygame.draw.circle(layer, (*FG_SHOCK_COLOR, alpha), center, radius, width)
