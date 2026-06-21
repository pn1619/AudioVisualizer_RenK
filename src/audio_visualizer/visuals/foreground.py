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
* ``sparks``    - a snappy burst of small, gravity-pulled embers shot inward from the
                  chosen edge(s) on each beat (faster + shorter-lived than flames).
* ``fireworks`` - each beat detonates shell(s) into a radial burst of gravity-pulled,
                  fading particles in a vivid per-shell color.
* ``edgeglow``  - a soft border bloom that throbs on each beat then decays (the safest
                  effect; no strobing, reduce-motion lowers the cap).

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
    FG_COLOR_DEFAULT,
    FG_COLOR_RGB,
    FG_COMBO_MEMBERS,
    FG_DIRECTION_DEFAULT,
    FG_FLAME_AMBIENT,
    FG_FLAME_BUOYANCY,
    FG_FLAME_BURST,
    FG_FLAME_DRAG,
    FG_FLAME_LIFE,
    FG_FLAME_MAX,
    FG_FLAME_PALETTE,
    FG_FLAME_SIZE,
    FG_FLAME_SPEED,
    FG_FLAME_SPREAD,
    FG_FLAME_WANDER,
    FG_FLAME_WANDER_FREQ,
    FG_FLASH_ALPHA,
    FG_FLASH_ALPHA_CAP,
    FG_FLASH_DECAY,
    FG_FLASH_DEFAULT,
    FG_FW_DRAG,
    FG_FW_GRAVITY,
    FG_FW_LIFE,
    FG_FW_MAX,
    FG_FW_PALETTE,
    FG_FW_PARTICLES,
    FG_FW_SHELLS,
    FG_FW_SIZE,
    FG_FW_SPEED,
    FG_GLOW_ALPHA,
    FG_GLOW_ALPHA_CAP,
    FG_GLOW_COLOR,
    FG_GLOW_DECAY,
    FG_GLOW_DEPTH,
    FG_GLOW_LEVEL_FLOOR,
    FG_IMPACT_LIFE,
    FG_IMPACT_RADIUS,
    FG_IMPACT_SPARKS,
    FG_INTENSITY_DEFAULT,
    FG_LIGHTNING_BOLTS,
    FG_LIGHTNING_CORE,
    FG_LIGHTNING_FORK_CHANCE,
    FG_LIGHTNING_FORKS,
    FG_LIGHTNING_GLOW,
    FG_LIGHTNING_JITTER,
    FG_LIGHTNING_LIFE,
    FG_LIGHTNING_SUBDIV,
    FG_LIGHTNING_WIDTH,
    FG_METEOR_BURST,
    FG_METEOR_CORE,
    FG_METEOR_EMBER_LIFE,
    FG_METEOR_EMBER_MAX,
    FG_METEOR_EMBER_RATE,
    FG_METEOR_FADE,
    FG_METEOR_GLOW,
    FG_METEOR_LIFE,
    FG_METEOR_LIFE_MIN,
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
    FG_REACTIVITY_DEFAULT,
    FG_SHOCK_COLOR,
    FG_SHOCK_LIFE,
    FG_SHOCK_MAX,
    FG_SHOCK_REACH,
    FG_SHOCK_RINGS,
    FG_SHOCK_WIDTH,
    FG_SPARK_BURST,
    FG_SPARK_DRAG,
    FG_SPARK_GRAVITY,
    FG_SPARK_LIFE,
    FG_SPARK_MAX,
    FG_SPARK_PALETTE,
    FG_SPARK_SIZE,
    FG_SPARK_SPEED,
    FG_SPARK_SPREAD,
    FG_TRIGGER_COOLDOWN,
    FG_WIND_DEFAULT,
    ONSET_THRESHOLD,
)
from audio_visualizer.visuals._helpers import clamp, lerp_color, palette_color, themed_color
from audio_visualizer.visuals.base import Theme

Color = tuple[int, int, int]

Point = tuple[float, float]
_EDGES = ("top", "bottom", "left", "right")


class Foreground:
    """A switchable, beat-triggered overlay composited above the active mode."""

    def __init__(self, theme: Theme, reduce_motion: bool = False) -> None:
        self.mode = FG_MODE_DEFAULT
        self.intensity = FG_INTENSITY_DEFAULT
        self.direction = FG_DIRECTION_DEFAULT
        self.opacity = FG_OPACITY_DEFAULT
        self.color = FG_COLOR_DEFAULT  # "auto" | "theme" | named hue (FG_COLOR_RGB)
        self.flash = FG_FLASH_DEFAULT  # lightning flash strength (0..1), independent of opacity
        self.reactivity = FG_REACTIVITY_DEFAULT  # scales onset sensitivity + spawn rate
        self.wind = FG_WIND_DEFAULT  # steady horizontal accel (px/s^2) for flying particles
        self._level = 0.0  # latest RMS level (drives continuous/ambient effects)
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
        self._spark_ps: list[dict[str, float]] = []  # {x,y,vx,vy,age,life,size}
        self._fireworks: list[dict[str, object]] = []  # {x,y,vx,vy,age,life,color}
        self._glow = 0.0  # edge-glow envelope (0..1), jumps on beat then decays
        self._impacts: list[dict[str, object]] = []  # ground-strike bursts {x,y,age,angles}
        self._m_embers: list[dict[str, float]] = []  # meteor ember trail {x,y,vx,vy,age,life}

    # -- public ----------------------------------------------------------------
    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        """Composite the current foreground effect onto ``surface`` (no-op for off)."""
        self._t += dt
        self._dt = dt
        self._level = 0.0 if frame is None else clamp(float(frame.rms) * 2.0)
        self._cooldown = max(0.0, self._cooldown - dt)
        beat = self._beat(frame)
        for mode in FG_COMBO_MEMBERS.get(self.mode, (self.mode,)):
            handler = getattr(self, f"_draw_{mode}", None)
            if handler is not None:
                handler(surface, frame, beat)

    def _beat(self, frame: AnalysisFrame | None) -> float:
        """Onset strength (0..1) when a fresh beat clears the cooldown, else 0.

        Reactivity lowers the effective onset threshold and the spawn cooldown, so a
        higher value fires on softer/denser onsets without touching the global beat.
        """
        if frame is None or frame.is_silent or self._cooldown > 0.0:
            return 0.0
        react = max(0.1, self.reactivity)
        if frame.onset < ONSET_THRESHOLD / react:
            return 0.0
        self._cooldown = FG_TRIGGER_COOLDOWN / react
        return clamp(float(frame.onset))

    # -- shared helpers --------------------------------------------------------
    def _pick_edge(self) -> str:
        if self.direction in _EDGES:
            return self.direction
        return self._rng.choice(_EDGES)

    def _add_layer(self, surface: pygame.Surface) -> pygame.Surface:
        return pygame.Surface(surface.get_size(), pygame.SRCALPHA)

    # -- color override --------------------------------------------------------
    def _base_color(self, natural: Color) -> Color:
        """The active hue for single-color effects, honoring the color override."""
        if self.color == "auto":
            return natural
        if self.color == "theme":
            return themed_color(self.theme.color_scheme, 0.5, (natural,), self.theme.color_phase)
        return FG_COLOR_RGB.get(self.color, natural)

    def _ramp_color(self, natural_palette: tuple[Color, ...], frac: float) -> Color:
        """Color at ``frac`` (0=hot/young, 1=cool/old) honoring the color override.

        ``auto`` keeps the effect's own palette; an override builds a white -> hue ->
        dark ramp so flames/sparks/fireworks still read as cooling embers in that hue.
        """
        if self.color == "auto":
            return palette_color(natural_palette, frac)
        hue = self._base_color((255, 255, 255))
        if frac < 0.5:  # white-hot core -> the chosen hue
            return lerp_color((255, 255, 255), hue, frac / 0.5)
        return lerp_color(hue, (10, 8, 8), (frac - 0.5) / 0.5)  # hue -> near-black ash

    # -- lightning -------------------------------------------------------------
    def _draw_lightning(
        self, surface: pygame.Surface, frame: AnalysisFrame | None, beat: float
    ) -> None:
        if beat > 0.0:
            self._spawn_bolts(surface.get_size(), beat)
        for bolt in self._bolts:
            bolt["age"] = float(bolt["age"]) + self._dt  # type: ignore[arg-type]
        self._bolts = [b for b in self._bolts if float(b["age"]) < FG_LIGHTNING_LIFE]  # type: ignore[arg-type]
        for imp in self._impacts:
            imp["age"] = float(imp["age"]) + self._dt  # type: ignore[arg-type]
        self._impacts = [i for i in self._impacts if float(i["age"]) < FG_IMPACT_LIFE]  # type: ignore[arg-type]
        self._flash = max(0.0, self._flash - self._dt * FG_FLASH_DECAY * FG_FLASH_ALPHA_CAP)
        if not self._bolts and not self._impacts and self._flash <= 0.5:
            return
        layer = self._add_layer(surface)
        if self._flash > 0.5:  # flash strength is the user's flash level × opacity
            flash_a = int(min(self._flash, FG_FLASH_ALPHA_CAP) * self.opacity)
            layer.fill((*self._base_color(FG_LIGHTNING_CORE), flash_a))
        for bolt in self._bolts:
            self._draw_bolt(layer, bolt)
        for imp in self._impacts:
            self._draw_impact(layer, imp)
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
            if end[1] >= size[1] * 0.88:  # the strike reached the "ground" (bottom)
                self._spawn_impact(end)
        flash = FG_FLASH_ALPHA * self.intensity * (0.6 + 0.4 * beat) * self.flash
        if self.reduce_motion:
            flash *= 0.5
        self._flash = min(max(self._flash, flash), FG_FLASH_ALPHA_CAP)

    def _spawn_impact(self, point: Point) -> None:
        sparks = FG_IMPACT_SPARKS // 2 if self.reduce_motion else FG_IMPACT_SPARKS
        angles = [
            -math.pi / 2 + self._rng.uniform(-1.1, 1.1) for _ in range(sparks)
        ]  # debris kicks upward in a fan
        self._impacts.append({"x": point[0], "y": point[1], "age": 0.0, "angles": angles})

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
        """Grow several tapering branches off the trunk (Lightning+ branching)."""
        if len(points) < 6:
            return []
        forks: list[list[Point]] = []
        n_forks = 1 if self.reduce_motion else self._rng.randint(1, FG_LIGHTNING_FORKS)
        for _ in range(n_forks):
            if self._rng.random() > FG_LIGHTNING_FORK_CHANCE:
                continue
            i = self._rng.randrange(len(points) // 4, 3 * len(points) // 4)
            base = points[i]
            far = points[min(len(points) - 1, i + len(points) // 4)]
            target = (
                far[0] + self._rng.uniform(-0.2, 0.2) * size[0],
                far[1] + self._rng.uniform(-0.05, 0.18) * size[1],
            )
            forks.append(self._jagged(base, target, FG_LIGHTNING_JITTER * 1.5))
        return forks

    def _draw_bolt(self, layer: pygame.Surface, bolt: dict[str, object]) -> None:
        age = bolt["age"]
        points = bolt["points"]
        forks = bolt["forks"]
        if not (isinstance(age, float) and isinstance(points, list) and isinstance(forks, list)):
            return
        fade = clamp(1.0 - age / FG_LIGHTNING_LIFE)
        glow = self._base_color(FG_LIGHTNING_GLOW)
        core = self._base_color(FG_LIGHTNING_CORE)
        glow_a = int(150 * fade * self.opacity)
        core_a = int(255 * fade * self.opacity)
        self._draw_tapered(layer, points, glow, core, glow_a, core_a, 1.0)
        for pts in forks:  # branches are thinner + a touch dimmer than the trunk
            self._draw_tapered(layer, pts, glow, core, int(glow_a * 0.8), int(core_a * 0.8), 0.6)

    def _draw_tapered(
        self,
        layer: pygame.Surface,
        pts: list[Point],
        glow: Color,
        core: Color,
        glow_a: int,
        core_a: int,
        scale: float,
    ) -> None:
        """Stroke a polyline whose width tapers from the trunk to a sharp tip."""
        n = len(pts)
        if n < 2 or core_a <= 0:
            return
        trunk = max(1.0, FG_LIGHTNING_WIDTH * scale)
        for i in range(n - 1):
            taper = 1.0 - i / (n - 1)  # full at the trunk, ~0 at the tip
            cw = max(1, int(round(trunk * taper)))
            if glow_a > 0:
                pygame.draw.line(layer, (*glow, glow_a), pts[i], pts[i + 1], cw + 4)
            pygame.draw.line(layer, (*core, core_a), pts[i], pts[i + 1], cw)

    def _draw_impact(self, layer: pygame.Surface, imp: dict[str, object]) -> None:
        """A brief expanding glow + upward debris where a bolt hit the ground."""
        age = float(imp["age"])  # type: ignore[arg-type]
        fade = clamp(1.0 - age / FG_IMPACT_LIFE)
        if fade <= 0:
            return
        x, y = int(float(imp["x"])), int(float(imp["y"]))  # type: ignore[arg-type]
        glow = self._base_color(FG_LIGHTNING_GLOW)
        core = self._base_color(FG_LIGHTNING_CORE)
        grow = 0.4 + 0.6 * (age / FG_IMPACT_LIFE)  # the flash blooms as it fades
        radius = max(1, int(FG_IMPACT_RADIUS * self.intensity * grow))
        pygame.draw.circle(layer, (*glow, int(150 * fade * self.opacity)), (x, y), radius)
        core_r = max(1, radius // 3)
        pygame.draw.circle(layer, (*core, int(220 * fade * self.opacity)), (x, y), core_r)
        angles = imp["angles"]
        if not isinstance(angles, list):
            return
        reach = FG_IMPACT_RADIUS * self.intensity * (1.0 + 2.0 * (age / FG_IMPACT_LIFE))
        for ang in angles:  # debris streaks fan upward from the strike point
            ex = x + int(math.cos(ang) * reach)
            ey = y + int(math.sin(ang) * reach)
            pygame.draw.line(layer, (*core, int(200 * fade * self.opacity)), (x, y), (ex, ey), 2)

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
            bx, by = 0.0, (1.0 if edge == "top" else -1.0)
        else:
            y, vy = r.uniform(0, h), r.uniform(-spread, spread)
            x, vx = (0.0, speed) if edge == "left" else (float(w), -speed)
            bx, by = (1.0 if edge == "left" else -1.0), 0.0
        return {
            "x": x,
            "y": y,
            "vx": vx,
            "vy": vy,
            "bx": bx,  # inward "up" axis the flame rises along
            "by": by,
            "phase": r.uniform(0.0, math.tau),  # desync the flicker per particle
            "age": 0.0,
            "life": FG_FLAME_LIFE * (0.7 + 0.6 * r.random()),
            "size": FG_FLAME_SIZE * (0.6 + 0.8 * r.random()),
        }

    def _step_flames(self) -> None:
        drag = math.exp(-FG_FLAME_DRAG * self._dt)
        for p in tuple(self._flames):
            p["age"] += self._dt
        self._flames = [p for p in self._flames if p["age"] < p["life"]]
        for p in self._flames:
            bx, by = p["bx"], p["by"]
            # Flicker (turbulence) perpendicular to the rise axis -> a licking flame.
            wob = math.sin(self._t * FG_FLAME_WANDER_FREQ + p["phase"]) * FG_FLAME_WANDER
            p["vx"] += (-by * wob + bx * FG_FLAME_BUOYANCY) * self._dt
            p["vy"] += (bx * wob + by * FG_FLAME_BUOYANCY) * self._dt
            p["vx"] *= drag
            p["vy"] *= drag
            p["x"] += p["vx"] * self._dt
            p["y"] += p["vy"] * self._dt

    def _draw_flame(self, layer: pygame.Surface, p: dict[str, float]) -> None:
        frac = clamp(p["age"] / p["life"])
        color = self._ramp_color(FG_FLAME_PALETTE, frac)
        radius = max(1, int(p["size"] * (1.0 - 0.55 * frac)))
        alpha = int(160 * (1.0 - frac) * self.opacity)
        if alpha <= 0:
            return
        pos = (int(p["x"]), int(p["y"]))
        pygame.draw.circle(layer, (*color, alpha // 3), pos, max(1, radius * 2))  # soft outer glow
        pygame.draw.circle(layer, (*color, alpha), pos, radius)  # body
        if frac < 0.45:  # white-hot core only while the particle is young
            core = self._ramp_color(FG_FLAME_PALETTE, 0.0)
            pygame.draw.circle(layer, (*core, alpha), pos, max(1, radius // 2))

    # -- rain / storm ----------------------------------------------------------
    def _draw_rain(self, surface: pygame.Surface, frame: AnalysisFrame | None, beat: float) -> None:
        size = surface.get_size()
        self._step_rain(size, beat)
        if not self._rain:
            return
        layer = self._add_layer(surface)
        sx, sy = FG_RAIN_STREAK, FG_RAIN_STREAK
        alpha = int(150 * self.opacity)
        rain_color = self._base_color(FG_RAIN_COLOR)
        for d in self._rain:
            head = (int(d["x"]), int(d["y"]))
            tail = (int(d["x"] - d["vx"] * sx), int(d["y"] - d["vy"] * sy))
            pygame.draw.line(layer, (*rain_color, alpha), tail, head, 1)
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
            d["vx"] += self.wind * self._dt
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
        self._step_m_embers()
        if not self._meteors and not self._m_embers:
            return
        layer = self._add_layer(surface)
        for e in self._m_embers:  # embers under the meteors so heads stay crisp
            self._draw_m_ember(layer, e)
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
        # Variable life: some cross the whole screen, some burn out mid-flight.
        life = r.uniform(FG_METEOR_LIFE_MIN, FG_METEOR_LIFE)
        return {
            "x": x,
            "y": y,
            "vx": vx,
            "vy": vy,
            "age": 0.0,
            "life": life,
            "trail": [],
            "emit": 0.0,
        }

    def _step_meteors(self, size: tuple[int, int]) -> None:
        w, h = size
        alive: list[dict[str, object]] = []
        for m in self._meteors:
            vx = float(m["vx"]) + self.wind * self._dt  # type: ignore[arg-type]
            x = float(m["x"]) + vx * self._dt  # type: ignore[arg-type]
            y = float(m["y"]) + float(m["vy"]) * self._dt  # type: ignore[arg-type]
            age = float(m["age"]) + self._dt  # type: ignore[arg-type]
            m["vx"], m["x"], m["y"], m["age"] = vx, x, y, age
            trail = m["trail"]
            if isinstance(trail, list):
                trail.append((x, y))
                if len(trail) > FG_METEOR_TRAIL:
                    del trail[0]
            self._shed_m_embers(m, x, y)
            if age < float(m["life"]) and -80 <= x <= w + 80 and -80 <= y <= h + 80:  # type: ignore[arg-type]
                alive.append(m)
        self._meteors = alive

    def _shed_m_embers(self, m: dict[str, object], x: float, y: float) -> None:
        """Drop slow ember particles along the head so the tail reads as sparks."""
        if self.reduce_motion:
            return
        emit = float(m["emit"]) + FG_METEOR_EMBER_RATE * self.intensity * self._dt  # type: ignore[arg-type]
        r = self._rng
        while emit >= 1.0:
            emit -= 1.0
            self._m_embers.append(
                {
                    "x": x,
                    "y": y,
                    "vx": r.uniform(-40, 40),
                    "vy": r.uniform(-40, 40),
                    "age": 0.0,
                    "life": FG_METEOR_EMBER_LIFE * (0.6 + 0.8 * r.random()),
                }
            )
        m["emit"] = emit
        if len(self._m_embers) > FG_METEOR_EMBER_MAX:
            del self._m_embers[: len(self._m_embers) - FG_METEOR_EMBER_MAX]

    def _step_m_embers(self) -> None:
        drag = math.exp(-1.4 * self._dt)
        alive: list[dict[str, float]] = []
        for e in self._m_embers:
            e["age"] += self._dt
            if e["age"] >= e["life"]:
                continue
            e["vx"] += self.wind * self._dt
            e["x"] += e["vx"] * self._dt
            e["y"] += e["vy"] * self._dt
            e["vx"] *= drag
            e["vy"] = e["vy"] * drag + 60.0 * self._dt  # embers gently fall as they cool
            alive.append(e)
        self._m_embers = alive

    def _draw_m_ember(self, layer: pygame.Surface, e: dict[str, float]) -> None:
        frac = clamp(e["age"] / e["life"])
        a = int(150 * (1.0 - frac) * self.opacity)
        if a <= 0:
            return
        color = self._ramp_color((FG_METEOR_CORE, FG_METEOR_GLOW, (60, 20, 10)), frac)
        r = max(1, int(2 * (1 - frac)))
        pygame.draw.circle(layer, (*color, a), (int(e["x"]), int(e["y"])), r)

    def _draw_meteor(self, layer: pygame.Surface, m: dict[str, object]) -> None:
        trail = m["trail"]
        if not isinstance(trail, list) or len(trail) < 2:
            return
        head_fade = self._meteor_fade(m)  # graceful fade-out as the meteor dies
        if head_fade <= 0:
            return
        glow = self._base_color(FG_METEOR_GLOW)
        core = self._base_color(FG_METEOR_CORE)
        n = len(trail)
        for i in range(1, n):
            frac = i / n  # tail (dim) -> head (bright), all scaled by the head fade
            a = int(180 * frac * head_fade * self.opacity)
            if a <= 0:
                continue
            width = max(1, int(frac * 3.5))
            pygame.draw.line(layer, (*glow, a), trail[i - 1], trail[i], width)
        head = (int(float(m["x"])), int(float(m["y"])))  # type: ignore[arg-type]
        glow_a = int(150 * head_fade * self.opacity)
        core_a = int(255 * head_fade * self.opacity)
        size = FG_METEOR_SIZE * (0.4 + 0.6 * head_fade)  # head shrinks as it burns out
        pygame.draw.circle(layer, (*glow, glow_a), head, max(1, int(size * 2)))
        pygame.draw.circle(layer, (*core, core_a), head, max(1, int(size)))

    def _meteor_fade(self, m: dict[str, object]) -> float:
        """1.0 for most of the flight, easing to 0 over the last ``FG_METEOR_FADE``."""
        age = float(m["age"])  # type: ignore[arg-type]
        life = float(m["life"])  # type: ignore[arg-type]
        remain = clamp((life - age) / max(1e-3, life * FG_METEOR_FADE))
        return remain

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
        for _ in range(count):
            cx, cy = self._origin(size)  # re-rolled per ring so "random" really scatters
            self._shocks.append({"cx": cx, "cy": cy, "age": 0.0})
        if len(self._shocks) > FG_SHOCK_MAX:
            del self._shocks[: len(self._shocks) - FG_SHOCK_MAX]

    def _origin(self, size: tuple[int, int]) -> tuple[float, float]:
        """Ring origin: chosen edge's midpoint, center, or a fresh random point."""
        w, h = size
        if self.direction == "random":
            return (self._rng.uniform(0.15 * w, 0.85 * w), self._rng.uniform(0.15 * h, 0.85 * h))
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
        pygame.draw.circle(layer, (*self._base_color(FG_SHOCK_COLOR), alpha), center, radius, width)

    # -- spark shower / embers -------------------------------------------------
    def _draw_sparks(
        self, surface: pygame.Surface, frame: AnalysisFrame | None, beat: float
    ) -> None:
        size = surface.get_size()
        if beat > 0.0:
            self._emit_sparks(size, beat)
        self._step_sparks()
        if not self._spark_ps:
            return
        layer = self._add_layer(surface)
        for p in self._spark_ps:
            self._draw_spark(layer, p)
        surface.blit(layer, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _emit_sparks(self, size: tuple[int, int], beat: float) -> None:
        n = int(FG_SPARK_BURST * self.intensity * (0.5 + beat))
        if self.reduce_motion:
            n //= 2
        edges = _EDGES if self.direction == "all" else None
        for k in range(n):
            edge = edges[k % len(edges)] if edges else self._pick_edge()
            self._spark_ps.append(self._spawn_spark(size, edge))
        if len(self._spark_ps) > FG_SPARK_MAX:
            del self._spark_ps[: len(self._spark_ps) - FG_SPARK_MAX]

    def _spawn_spark(self, size: tuple[int, int], edge: str) -> dict[str, float]:
        w, h = size
        r = self._rng
        speed = FG_SPARK_SPEED * (0.5 + 0.8 * r.random())
        spread = FG_SPARK_SPEED * FG_SPARK_SPREAD
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
            "life": FG_SPARK_LIFE * (0.6 + 0.7 * r.random()),
            "size": FG_SPARK_SIZE * (0.6 + 0.8 * r.random()),
        }

    def _step_sparks(self) -> None:
        drag = math.exp(-FG_SPARK_DRAG * self._dt)
        alive: list[dict[str, float]] = []
        for p in self._spark_ps:
            p["age"] += self._dt
            if p["age"] >= p["life"]:
                continue
            p["vy"] += FG_SPARK_GRAVITY * self._dt  # gravity pulls embers down
            p["vx"] += self.wind * self._dt
            p["x"] += p["vx"] * self._dt
            p["y"] += p["vy"] * self._dt
            p["vx"] *= drag
            p["vy"] *= drag
            alive.append(p)
        self._spark_ps = alive

    def _draw_spark(self, layer: pygame.Surface, p: dict[str, float]) -> None:
        frac = clamp(p["age"] / p["life"])
        color = self._ramp_color(FG_SPARK_PALETTE, frac)
        radius = max(1, int(p["size"] * (1.0 - 0.5 * frac)))
        alpha = int(220 * (1.0 - frac) * self.opacity)
        if alpha <= 0:
            return
        pygame.draw.circle(layer, (*color, alpha), (int(p["x"]), int(p["y"])), radius)

    # -- fireworks / confetti --------------------------------------------------
    def _draw_fireworks(
        self, surface: pygame.Surface, frame: AnalysisFrame | None, beat: float
    ) -> None:
        size = surface.get_size()
        if beat > 0.0:
            self._detonate(size, beat)
        self._step_fireworks()
        if not self._fireworks:
            return
        layer = self._add_layer(surface)
        for p in self._fireworks:
            self._draw_firework(layer, p)
        surface.blit(layer, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _detonate(self, size: tuple[int, int], beat: float) -> None:
        shells = max(1, int(round(FG_FW_SHELLS * self.intensity * beat)))
        if self.reduce_motion:
            shells = 1
        count = max(8, int(FG_FW_PARTICLES * (0.7 if self.reduce_motion else 1.0)))
        for _ in range(shells):
            cx, cy = self._burst_origin(size)
            # Auto keeps the multi-color confetti; an override paints each shell one hue.
            natural = self._rng.choice(FG_FW_PALETTE)
            color = natural if self.color == "auto" else self._base_color(natural)
            for i in range(count):
                ang = (i / count) * math.tau + self._rng.uniform(-0.1, 0.1)
                speed = FG_FW_SPEED * (0.4 + 0.8 * self._rng.random())
                self._fireworks.append(
                    {
                        "x": cx,
                        "y": cy,
                        "vx": math.cos(ang) * speed,
                        "vy": math.sin(ang) * speed,
                        "age": 0.0,
                        "life": FG_FW_LIFE * (0.7 + 0.5 * self._rng.random()),
                        "color": color,
                    }
                )
        if len(self._fireworks) > FG_FW_MAX:
            del self._fireworks[: len(self._fireworks) - FG_FW_MAX]

    def _burst_origin(self, size: tuple[int, int]) -> tuple[float, float]:
        """Where a shell detonates: chosen edge, screen center, or a random point."""
        w, h = size
        r = self._rng
        if self.direction in _EDGES:
            cx, cy = self._origin(size)
            if self.direction in ("left", "right"):
                return (cx, cy)
            return (r.uniform(0.2 * w, 0.8 * w), cy)  # spread top/bottom shells across
        if self.direction == "center":
            return (w / 2, h / 2)
        return (r.uniform(0.2 * w, 0.8 * w), r.uniform(0.2 * h, 0.55 * h))

    def _step_fireworks(self) -> None:
        drag = math.exp(-FG_FW_DRAG * self._dt)
        alive: list[dict[str, object]] = []
        for p in self._fireworks:
            age = float(p["age"]) + self._dt  # type: ignore[arg-type]
            if age >= float(p["life"]):  # type: ignore[arg-type]
                continue
            vx = float(p["vx"]) * drag + self.wind * self._dt  # type: ignore[arg-type]
            vy = float(p["vy"]) * drag + FG_FW_GRAVITY * self._dt  # type: ignore[arg-type]
            p["age"] = age
            p["vx"], p["vy"] = vx, vy
            p["x"] = float(p["x"]) + vx * self._dt  # type: ignore[arg-type]
            p["y"] = float(p["y"]) + vy * self._dt  # type: ignore[arg-type]
            alive.append(p)
        self._fireworks = alive

    def _draw_firework(self, layer: pygame.Surface, p: dict[str, object]) -> None:
        frac = clamp(float(p["age"]) / float(p["life"]))  # type: ignore[arg-type]
        color = p["color"]
        if not isinstance(color, tuple):
            return
        radius = max(1, int(FG_FW_SIZE * (1.0 - 0.6 * frac)))
        alpha = int(230 * (1.0 - frac) * self.opacity)
        if alpha <= 0:
            return
        pos = (int(float(p["x"])), int(float(p["y"])))  # type: ignore[arg-type]
        pygame.draw.circle(layer, (*color, alpha), pos, radius)

    # -- edge glow pulse -------------------------------------------------------
    def _draw_edgeglow(
        self, surface: pygame.Surface, frame: AnalysisFrame | None, beat: float
    ) -> None:
        if beat > 0.0:
            self._glow = min(1.0, max(self._glow, 0.4 + 0.6 * beat))
        self._glow = max(0.0, self._glow - self._dt * FG_GLOW_DECAY)
        # Continuous breathing: the border keeps a soft floor that tracks the live
        # RMS level, so it pulses with the music even between discrete beats.
        env = max(self._glow, FG_GLOW_LEVEL_FLOOR * self._level)
        if env <= 0.01:
            return
        size = surface.get_size()
        depth = max(2, int(min(size) * FG_GLOW_DEPTH))
        cap = FG_GLOW_ALPHA_CAP * (0.5 if self.reduce_motion else 1.0)
        peak = min(FG_GLOW_ALPHA * self.intensity, cap) * env * self.opacity
        if peak <= 0:
            return
        layer = self._add_layer(surface)
        color = self._base_color(FG_GLOW_COLOR)
        for edge in self._glow_edges():
            self._draw_glow_edge(layer, size, edge, depth, peak, color)
        surface.blit(layer, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _glow_edges(self) -> tuple[str, ...]:
        """Which borders glow: a single chosen edge, else all four."""
        return (self.direction,) if self.direction in _EDGES else _EDGES

    @staticmethod
    def _glow_alpha(i: int, depth: int, peak: float) -> int:
        """Smooth (smoothstep) inward falloff for an elegant bloom, not a hard band."""
        f = 1.0 - i / depth
        return int(peak * f * f * (3.0 - 2.0 * f))

    def _draw_glow_edge(
        self,
        layer: pygame.Surface,
        size: tuple[int, int],
        edge: str,
        depth: int,
        peak: float,
        color: Color,
    ) -> None:
        w, h = size
        for i in range(depth):
            a = self._glow_alpha(i, depth, peak)
            if a <= 0:
                continue
            col = (*color, a)
            if edge == "top":
                pygame.draw.line(layer, col, (0, i), (w, i))
            elif edge == "bottom":
                pygame.draw.line(layer, col, (0, h - 1 - i), (w, h - 1 - i))
            elif edge == "left":
                pygame.draw.line(layer, col, (i, 0), (i, h))
            else:
                pygame.draw.line(layer, col, (w - 1 - i, 0), (w - 1 - i, h))
