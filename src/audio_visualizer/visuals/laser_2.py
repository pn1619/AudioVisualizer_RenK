"""Laser 2: rotating beams + a selectable parametric figure that can emit particles.

Like Laser, but the central figure can be one of several shapes (Lissajous, rose,
star, spiral, heart) and — when ``Emit`` is on — the rotating beams shoot out small
particles (which can leave a fading trail). All shapes are driven by band energy.
"""

from __future__ import annotations

import math
import random

import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import (
    ONSET_THRESHOLD,
    PALETTE,
    SPARK_MAX,
    SPARK_MAX_REDUCED,
)
from audio_visualizer.visuals._helpers import (
    TRAIL_OPTION,
    SparkField,
    scale_color,
    themed_color,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_CURVE_POINTS = 160
# Beam spin (radians/sec): calm fixed rate under reduce-motion, else base + rms gain.
_SPIN_REDUCED = 0.4
_SPIN_BASE = 1.0
_SPIN_RMS_GAIN = 2.5
# Figure half-extent as a fraction of the canvas width/height.
_EXTENT = 0.36
# Beam length = radius * (this + band energy); width = 1 + energy * gain.
_BEAM_LENGTH_BASE = 0.3
_BEAM_WIDTH_GAIN = 4
_BEAM_BRIGHTNESS_BASE = 0.5
# Figure stroke width (px) and brightness floor before rms is added.
_CURVE_WIDTH = 2
_CURVE_BRIGHTNESS_BASE = 0.6
# Emitted sparks: outward speed (normalized units/sec) and smaller size.
_EMIT_SPEED = 0.12
_EMIT_SMALL_SIZE = 0.6
# Shape parameters driven (partly) by energy.
_ROSE_PETALS_BASE = 3  # petals = base + a few from low-band energy
_ROSE_PETALS_GAIN = 4
_SPIRAL_TURNS = 3
_STAR_SPIKES = 5
_STAR_OUTER = 1.0
_STAR_INNER = 0.45
_LISSA_FREQ_X_BASE = 2.0
_LISSA_FREQ_Y_BASE = 3.0
_LISSA_FREQ_GAIN = 3.0

# Shape option values.
_SHAPE_LISSAJOUS, _SHAPE_ROSE, _SHAPE_STAR, _SHAPE_SPIRAL, _SHAPE_HEART = 0, 1, 2, 3, 4

_SHAPE = ModeOption(
    "shape",
    "Shape",
    (
        OptionChoice("Lissajous", _SHAPE_LISSAJOUS),
        OptionChoice("Rose", _SHAPE_ROSE),
        OptionChoice("Star", _SHAPE_STAR),
        OptionChoice("Spiral", _SHAPE_SPIRAL),
        OptionChoice("Heart", _SHAPE_HEART),
    ),
    default_index=0,
)
_BEAMS = ModeOption(
    "beams",
    "Beams",
    (OptionChoice("4", 4), OptionChoice("8", 8), OptionChoice("12", 12)),
    default_index=1,
)
_EMIT = ModeOption(
    "emit",
    "Emit",
    (OptionChoice("Off", 0), OptionChoice("On", 1)),
    default_index=1,
)


@register(key="laser_2", display_name="Laser 2", order=55)
class Laser2(BaseVisualizer):
    """Rotating beams + a selectable parametric figure; beams can emit trailing sparks."""

    STROBES = True
    OPTIONS = (_SHAPE, _BEAMS, _EMIT, TRAIL_OPTION)

    def __init__(
        self, reduce_motion: bool = False, theme: Theme | None = None, seed: int = 1357
    ) -> None:
        super().__init__(reduce_motion, theme)
        self._seed = seed
        self._rng = random.Random(seed)
        self._phase = 0.0
        cap = SPARK_MAX_REDUCED if reduce_motion else SPARK_MAX
        self._sparks = SparkField(cap)

    def on_enter(self) -> None:
        self._phase = 0.0
        self._rng.seed(self._seed)
        self._sparks.clear()

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 2 or h < 2:
            return
        cx, cy = w / 2.0, h / 2.0
        scheme = self.theme.color_scheme
        phase_c = self.theme.color_phase

        rms = frame.rms if frame is not None else 0.0
        spin = _SPIN_REDUCED if self.reduce_motion else _SPIN_BASE + rms * _SPIN_RMS_GAIN
        self._phase = (self._phase + dt * spin * self.theme.speed_scale) % (2.0 * math.pi)

        if frame is not None and not frame.is_silent and frame.band_energies.size > 0:
            self._draw_beams(surface, cx, cy, min(w, h) * 0.5, w, h, frame, scheme, phase_c)
            self._draw_figure(surface, cx, cy, w, h, frame, scheme, phase_c)

        self._sparks.advance(dt, self.theme.speed_scale)
        trails = self.option("trails") >= 1
        self._sparks.render(surface, scheme, phase_c, w, h, self.theme.size_scale, trails)

    # -- beams ----------------------------------------------------------------
    def _draw_beams(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        radius: float,
        w: int,
        h: int,
        frame: AnalysisFrame,
        scheme: str,
        phase_c: float,
    ) -> None:
        bands = frame.band_energies
        beams = int(self.option("beams"))
        emit = self.option("emit") >= 1 and not self.reduce_motion
        fire = emit and frame.onset >= ONSET_THRESHOLD
        for i in range(beams):
            energy = float(bands[i * bands.size // beams])
            angle = self._phase + (math.pi * i / beams)
            length = radius * (_BEAM_LENGTH_BASE + energy)
            color = scale_color(
                themed_color(scheme, i / beams, PALETTE, phase_c), _BEAM_BRIGHTNESS_BASE + energy
            )
            width = 1 if self.reduce_motion else max(1, int(1 + energy * _BEAM_WIDTH_GAIN))
            for direction in (1.0, -1.0):
                dx, dy = math.cos(angle) * direction, math.sin(angle) * direction
                ex, ey = cx + dx * length, cy + dy * length
                pygame.draw.line(surface, color, (cx, cy), (ex, ey), width)
                if fire:
                    self._emit_from_tip(ex, ey, dx, dy, w, h, i / beams)

    def _emit_from_tip(
        self, ex: float, ey: float, dx: float, dy: float, w: int, h: int, hue: float
    ) -> None:
        speed = _EMIT_SPEED * self._rng.uniform(0.7, 1.3)
        self._sparks.spawn(
            x=ex / w, y=ey / h, vx=dx * speed, vy=dy * speed, hue=hue, size=_EMIT_SMALL_SIZE
        )

    # -- figure ---------------------------------------------------------------
    def _draw_figure(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        w: int,
        h: int,
        frame: AnalysisFrame,
        scheme: str,
        phase_c: float,
    ) -> None:
        ax, ay = w * _EXTENT, h * _EXTENT
        bands = frame.band_energies
        low = float(bands[: bands.size // 2].mean())
        high = float(bands[bands.size // 2 :].mean())
        points = self._figure_points(int(self.option("shape")), cx, cy, ax, ay, low, high)
        if len(points) < 2:
            return
        color = scale_color(
            themed_color(scheme, frame.peak, PALETTE, phase_c), _CURVE_BRIGHTNESS_BASE + frame.rms
        )
        pygame.draw.lines(surface, color, False, points, _CURVE_WIDTH)

    def _figure_points(
        self, shape: int, cx: float, cy: float, ax: float, ay: float, low: float, high: float
    ) -> list[tuple[float, float]]:
        """Build the parametric figure's point list for the selected shape."""
        if shape == _SHAPE_ROSE:
            return self._rose(cx, cy, ax, ay, low)
        if shape == _SHAPE_STAR:
            return self._star(cx, cy, ax, ay, high)
        if shape == _SHAPE_SPIRAL:
            return self._spiral(cx, cy, ax, ay)
        if shape == _SHAPE_HEART:
            return self._heart(cx, cy, ax, ay, low)
        return self._lissajous(cx, cy, ax, ay, low, high)

    def _lissajous(
        self, cx: float, cy: float, ax: float, ay: float, low: float, high: float
    ) -> list[tuple[float, float]]:
        a = _LISSA_FREQ_X_BASE + low * _LISSA_FREQ_GAIN
        b = _LISSA_FREQ_Y_BASE + high * _LISSA_FREQ_GAIN
        pts = []
        for k in range(_CURVE_POINTS + 1):
            t = 2.0 * math.pi * k / _CURVE_POINTS
            pts.append((cx + math.sin(a * t + self._phase) * ax, cy + math.sin(b * t) * ay))
        return pts

    def _rose(
        self, cx: float, cy: float, ax: float, ay: float, low: float
    ) -> list[tuple[float, float]]:
        petals = _ROSE_PETALS_BASE + int(low * _ROSE_PETALS_GAIN)
        pts = []
        for k in range(_CURVE_POINTS + 1):
            t = 2.0 * math.pi * k / _CURVE_POINTS
            r = math.cos(petals * t)
            pts.append(
                (cx + ax * r * math.cos(t + self._phase), cy + ay * r * math.sin(t + self._phase))
            )
        return pts

    def _star(
        self, cx: float, cy: float, ax: float, ay: float, high: float
    ) -> list[tuple[float, float]]:
        outer = _STAR_OUTER * (0.85 + high)
        pts = []
        for k in range(_STAR_SPIKES * 2 + 1):
            ang = self._phase + math.pi * k / _STAR_SPIKES
            r = outer if k % 2 == 0 else _STAR_INNER
            pts.append((cx + math.cos(ang) * ax * r, cy + math.sin(ang) * ay * r))
        return pts

    def _spiral(self, cx: float, cy: float, ax: float, ay: float) -> list[tuple[float, float]]:
        pts = []
        total = _CURVE_POINTS
        for k in range(total + 1):
            t = 2.0 * math.pi * _SPIRAL_TURNS * k / total
            rr = k / total
            pts.append(
                (cx + ax * rr * math.cos(t + self._phase), cy + ay * rr * math.sin(t + self._phase))
            )
        return pts

    def _heart(
        self, cx: float, cy: float, ax: float, ay: float, low: float
    ) -> list[tuple[float, float]]:
        scale = 0.85 + low * 0.3
        pts = []
        for k in range(_CURVE_POINTS + 1):
            t = 2.0 * math.pi * k / _CURVE_POINTS + self._phase
            hx = 16.0 * math.sin(t) ** 3
            hy = (
                13.0 * math.cos(t) - 5.0 * math.cos(2 * t) - 2.0 * math.cos(3 * t) - math.cos(4 * t)
            )
            pts.append((cx + ax * (hx / 16.0) * scale, cy - ay * (hy / 16.0) * scale))
        return pts
