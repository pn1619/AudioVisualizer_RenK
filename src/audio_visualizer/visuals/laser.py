"""Laser: rotating beams + a selectable parametric figure that can emit particles.

Beams sweep around the center while a central figure (Lissajous, rose, spiro,
star, or butterfly) traces the spectrum. With ``Particles = Off`` it's clean beams +
figure (the classic Laser); turning particles on makes the beams shoot small sparks
outward on onsets (which can leave a fading trail). All shapes are driven by band
energy — spiro is a roulette web, the star's spikes ride the highs, and the
butterfly's wings flutter with the beat for a modern, kinetic neon look.
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
    PARTICLES_OPTION,
    TRAIL_OPTION,
    SparkField,
    scale_color,
    themed_color,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_CURVE_POINTS = 160
_SPIN_REDUCED = 0.4
_SPIN_BASE = 1.0
_SPIN_RMS_GAIN = 2.5
_EXTENT = 0.36
_BEAM_LENGTH_BASE = 0.3
_BEAM_WIDTH_GAIN = 4
_BEAM_BRIGHTNESS_BASE = 0.5
_CURVE_WIDTH = 2
_CURVE_BRIGHTNESS_BASE = 0.6
_EMIT_SPEED = 0.12
_EMIT_SMALL_SIZE = 0.6
_ROSE_PETALS_BASE = 3
_ROSE_PETALS_GAIN = 4
_LISSA_FREQ_X_BASE = 2.0
_LISSA_FREQ_Y_BASE = 3.0
_LISSA_FREQ_GAIN = 3.0
# Spiro: a hypotrochoid whose inner radius / pen offset breathe with the audio,
# drawn over several loops so the strands weave a dense neon web.
_SPIRO_LOOPS = 5
_SPIRO_FIT = 0.72
# Star: a sharp N-point star; the spike count rides the highs and the spikes get
# pointier (smaller inner radius) with more bass.
_STAR_SPIKES_BASE = 5
_STAR_SPIKES_GAIN = 4
_STAR_INNER_BASE = 0.62  # inner radius as a fraction of the outer (blunt resting)
_STAR_INNER_GAIN = 0.42  # bass sharpens the spikes (pulls the inner radius in)
# Butterfly: the Temple Fay curve; its wings flutter with the beat phase.
_BFLY_FREQ_BASE = 3.0
_BFLY_FREQ_GAIN = 3.0
_BFLY_SPAN = 24.0  # radians traced (the curve closes near 24π ~= 12 lobes)
_BFLY_FIT = 0.17  # normalize the curve's ~5.7 peak radius into the figure box

_SHAPE_LISSAJOUS, _SHAPE_ROSE, _SHAPE_SPIRO, _SHAPE_STAR, _SHAPE_BUTTERFLY = 0, 1, 2, 3, 4

_PRESET = ModeOption(
    "preset",
    "Preset",
    (
        OptionChoice("Custom", 0),
        OptionChoice("Classic", 1),
        OptionChoice("Rose", 2),
        OptionChoice("Spiro", 3),
    ),
    default_index=0,
)
_SHAPE = ModeOption(
    "shape",
    "Shape",
    (
        OptionChoice("Lissajous", _SHAPE_LISSAJOUS),
        OptionChoice("Rose", _SHAPE_ROSE),
        OptionChoice("Spiro", _SHAPE_SPIRO),
        OptionChoice("Star", _SHAPE_STAR),
        OptionChoice("Butterfly", _SHAPE_BUTTERFLY),
    ),
    default_index=0,
)
_BEAMS = ModeOption(
    "beams",
    "Beams",
    (OptionChoice("4", 4), OptionChoice("8", 8), OptionChoice("12", 12)),
    default_index=1,
)


@register(key="laser", display_name="Laser", order=50)
class Laser(BaseVisualizer):
    """Rotating beams + a selectable parametric figure; beams can emit trailing sparks."""

    STROBES = True
    OPTIONS = (_PRESET, _SHAPE, _BEAMS, PARTICLES_OPTION, TRAIL_OPTION)
    PRESETS = {
        1: {"shape": 0, "particles": 0},  # Classic Lissajous beams
        2: {"shape": 1, "particles": 1},  # Rose + sparks
        3: {"shape": 2, "particles": 2},  # Spiro + dense sparks
    }

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

        # Honor a mid-session reduce-motion toggle (cap is fixed at construction).
        self._sparks.cap = SPARK_MAX_REDUCED if self.reduce_motion else SPARK_MAX
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
        emit = self.option("particles") > 0 and not self.reduce_motion
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
        mid = bands.size // 2
        low = float(bands[:mid].mean()) if mid > 0 else float(bands.mean())
        high = float(bands[mid:].mean())  # mid < size whenever size > 0 (guarded by caller)
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
        if shape == _SHAPE_ROSE:
            return self._rose(cx, cy, ax, ay, low)
        if shape == _SHAPE_SPIRO:
            return self._spiro(cx, cy, ax, ay, low, high)
        if shape == _SHAPE_STAR:
            return self._star(cx, cy, ax, ay, low, high)
        if shape == _SHAPE_BUTTERFLY:
            return self._butterfly(cx, cy, ax, ay, low, high)
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

    def _spiro(
        self, cx: float, cy: float, ax: float, ay: float, low: float, high: float
    ) -> list[tuple[float, float]]:
        """A hypotrochoid that weaves a neon web; bass sets density, highs the reach."""
        r = 0.30 + low * 0.45  # rolling-circle radius (fraction of the outer circle)
        d = 0.45 + high * 0.55  # pen offset -> how far the strands swing out
        ratio = (1.0 - r) / max(r, 1e-3)
        pts = []
        steps = _CURVE_POINTS * _SPIRO_LOOPS
        for k in range(steps + 1):
            t = 2.0 * math.pi * _SPIRO_LOOPS * k / steps
            x = (1.0 - r) * math.cos(t) + d * r * math.cos(ratio * t + self._phase)
            y = (1.0 - r) * math.sin(t) - d * r * math.sin(ratio * t + self._phase)
            pts.append((cx + x * ax * _SPIRO_FIT, cy + y * ay * _SPIRO_FIT))
        return pts

    def _star(
        self, cx: float, cy: float, ax: float, ay: float, low: float, high: float
    ) -> list[tuple[float, float]]:
        """A sharp N-point star; highs add spikes, bass sharpens (pulls the inner radius in)."""
        spikes = _STAR_SPIKES_BASE + int(high * _STAR_SPIKES_GAIN)
        inner = _STAR_INNER_BASE - low * _STAR_INNER_GAIN
        pts = []
        steps = spikes * 2
        for k in range(steps + 1):
            t = math.pi * k / spikes + self._phase  # alternate outer/inner every half-step
            r = 1.0 if k % 2 == 0 else inner
            pts.append((cx + math.cos(t) * ax * r, cy + math.sin(t) * ay * r))
        return pts

    def _butterfly(
        self, cx: float, cy: float, ax: float, ay: float, low: float, high: float
    ) -> list[tuple[float, float]]:
        """Temple Fay butterfly curve; bass swells it and the beat flutters its wings."""
        wings = _BFLY_FREQ_BASE + high * _BFLY_FREQ_GAIN
        scale = _BFLY_FIT * (0.85 + low * 0.4)
        pts = []
        steps = _CURVE_POINTS * 3
        for k in range(steps + 1):
            t = _BFLY_SPAN * k / steps
            r = (
                math.exp(math.cos(t))
                - 2.0 * math.cos(wings * t + self._phase)
                + math.sin(t / 12.0) ** 5
            )
            rr = r * scale
            pts.append((cx + math.sin(t) * ax * rr, cy + math.cos(t) * ay * rr))
        return pts
