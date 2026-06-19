"""Audio Sun: spectrum bars radiating outward in a full circle.

One ray per spectrum slice points out from a glowing core; ray length follows that
band's energy and hue sweeps around the ring. The core can be a hue-flowing ring of
orbiting particles (Orbit), two counter-spinning particle rings (Dust), a plain glow,
or radiating beat rings. With ``Spark = On`` the brightest rays also fling small
particles off their tips on onsets. A faint oscilloscope ring threads the ray bases.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import (
    COLOR_ACCENT,
    ONSET_THRESHOLD,
    PALETTE,
    SPARK_MAX,
    SPARK_MAX_REDUCED,
)
from audio_visualizer.visuals._helpers import (
    SIZE_OPTION,
    SparkField,
    clamp,
    draw_ring,
    resample_to,
    ring_points,
    themed_color,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_RAYS = 120  # rays placed around the ring (bands are resampled to this)
_CORE_FRACTION = 0.16  # ray-base radius as a fraction of min(w, h)/2
_LEN_FRACTION = 0.62  # max ray length as a fraction of min(w, h)/2
_ROTATE_RATE = 0.04  # base ray-ring revolutions per second (scaled by speed)
_DISK_RATE = 0.12  # base core-ring color-flow revolutions per second
_CORE_DOTS = 36  # particles around the orbit core ring
_SPARK_RAY_FLOOR = 0.5  # rays above this energy fling sparks on onsets
_SPARK_STRIDE = 6  # only every Nth ray emits, to keep the spray sparse
_SPARK_SPEED = 0.16  # outward speed of a flung spark (fraction of canvas/sec)

_MIRROR = ModeOption(
    "mirror", "Mirror", (OptionChoice("On", 1), OptionChoice("Off", 0)), default_index=0
)
_THICKNESS = ModeOption(
    "thickness",
    "Rays",
    (OptionChoice("Thin", 2), OptionChoice("Normal", 3), OptionChoice("Bold", 5)),
    default_index=1,
)
# How the core behaves: Orbit/Dust are rings of orbiting particles.
_DISKS = ModeOption(
    "disks",
    "Core",
    (
        OptionChoice("Orbit", 0),
        OptionChoice("Dust", 1),
        OptionChoice("Glow", 2),
        OptionChoice("Radiate", 3),
    ),
    default_index=0,
)
# Fling small particles off the brightest ray tips on onsets.
_SPARK = ModeOption(
    "spark", "Spark", (OptionChoice("Off", 0), OptionChoice("On", 1)), default_index=0
)


@register(key="radial_spectrum", display_name="Audio Sun", order=22)
class RadialSpectrum(BaseVisualizer):
    """Radial spectrum rays around a particle/glow core + an oscilloscope ring."""

    OPTIONS = (_MIRROR, _THICKNESS, _DISKS, _SPARK, SIZE_OPTION)

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._angle = 0.0
        self._outer = 0.0  # outer-ring color-flow offset (0..1)
        self._inner = 0.0  # inner-ring color-flow offset (0..1)
        self._rings: list[float] = []  # normalized radii of radiating beat rings
        cap = SPARK_MAX_REDUCED if reduce_motion else SPARK_MAX
        self._sparks = SparkField(cap)
        self._rng = random.Random(909)

    def on_enter(self) -> None:
        self._angle = self._outer = self._inner = 0.0
        self._rings.clear()
        self._sparks.clear()

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        cx, cy = w / 2.0, h / 2.0
        scale = min(w, h) / 2.0 * float(self.option("size"))
        core_r = scale * _CORE_FRACTION
        max_len = scale * _LEN_FRACTION
        scheme, phase = self.theme.color_scheme, self.theme.color_phase

        spin = 0.0 if self.reduce_motion else _ROTATE_RATE
        self._angle = (self._angle + dt * self.theme.speed_scale * spin * math.tau) % math.tau

        self._draw_core(surface, cx, cy, core_r, scale, frame, dt)
        if frame is not None and frame.waveform_mono.size > 1:
            pts = ring_points(cx, cy, core_r, scale * 0.05, frame.waveform_mono, points=180)
            draw_ring(surface, scheme, phase, pts, width=1)

        rays = self._ray_energies(frame)
        width = int(self.option("thickness"))
        spark_on = int(self.option("spark")) == 1 and not self.reduce_motion
        onset = 0.0 if frame is None else frame.onset
        fire = spark_on and onset >= ONSET_THRESHOLD
        for i, energy in enumerate(rays):
            ang = self._angle + (i / _RAYS) * math.tau
            length = core_r + float(energy) * max_len
            ix, iy = cx + math.cos(ang) * core_r, cy + math.sin(ang) * core_r
            ox, oy = cx + math.cos(ang) * length, cy + math.sin(ang) * length
            color = themed_color(scheme, i / _RAYS, PALETTE, phase)
            pygame.draw.line(surface, color, (ix, iy), (ox, oy), width)
            if fire and energy > _SPARK_RAY_FLOOR and i % _SPARK_STRIDE == 0:
                self._emit_tip(ox, oy, math.cos(ang), math.sin(ang), i / _RAYS, w, h)

        if spark_on:
            self._sparks.advance(dt, self.theme.speed_scale)
            self._sparks.render(surface, scheme, phase, w, h, self.theme.size_scale, trails=False)

    def _emit_tip(
        self, ox: float, oy: float, dx: float, dy: float, hue: float, w: int, h: int
    ) -> None:
        speed = _SPARK_SPEED * self._rng.uniform(0.7, 1.3)
        spread = self._rng.uniform(-0.12, 0.12)
        self._sparks.spawn(
            x=ox / w,
            y=oy / h,
            vx=(dx + spread) * speed,
            vy=(dy + spread) * speed,
            hue=hue,
            size=self._rng.uniform(0.5, 0.9),
        )

    def _ray_energies(self, frame: AnalysisFrame | None) -> np.ndarray:
        if frame is None or frame.band_energies.size == 0:
            return np.zeros(_RAYS, dtype=np.float32)
        if self.option("mirror") >= 1:
            half = resample_to(frame.band_energies.astype(np.float32), _RAYS // 2)
            return np.concatenate([half, half[::-1]])
        return resample_to(frame.band_energies.astype(np.float32), _RAYS)

    def _draw_core(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        core_r: float,
        scale: float,
        frame: AnalysisFrame | None,
        dt: float,
    ) -> None:
        level = 0.0 if frame is None else min(1.0, frame.rms * 2.0)
        onset = 0.0 if frame is None else frame.onset
        mode = int(self.option("disks"))
        scheme, phase = self.theme.color_scheme, self.theme.color_phase

        step = 0.0 if self.reduce_motion else dt * self.theme.speed_scale * _DISK_RATE
        self._outer = (self._outer + step) % 1.0
        inner_dir = -1.0 if mode == 1 else 1.0  # "Counter" flows the inner ring backwards
        self._inner = (self._inner + inner_dir * step * 1.4) % 1.0

        self._glow(surface, cx, cy, core_r, level)
        if mode == 3:
            self._update_rings(surface, cx, cy, core_r, scale, onset, dt, scheme, phase)
        if mode in (0, 1):
            self._particle_core(surface, cx, cy, core_r, level, scheme, phase, dual=mode == 1)

    def _particle_core(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        core_r: float,
        level: float,
        scheme: str,
        phase: float,
        dual: bool,
    ) -> None:
        """Render the core as a ring of orbiting particles whose hue flows around it."""
        self._dots(surface, cx, cy, core_r, level, scheme, phase, self._outer, _CORE_DOTS, 0.16)
        if dual:  # Dust: a denser, counter-spinning inner ring
            self._dots(
                surface, cx, cy, core_r * 0.6, level, scheme, phase, self._inner, _CORE_DOTS, 0.11
            )

    @staticmethod
    def _dots(
        surface: pygame.Surface,
        cx: float,
        cy: float,
        radius: float,
        level: float,
        scheme: str,
        phase: float,
        offset: float,
        count: int,
        dot_frac: float,
    ) -> None:
        dot_r = max(2, int(radius * dot_frac * (0.8 + 0.5 * level)))
        for k in range(count):
            base = k / count
            ang = (base + offset) * math.tau
            rr = radius * (1.0 + 0.06 * math.sin(ang * 3.0 + offset * math.tau))
            x = cx + math.cos(ang) * rr
            y = cy + math.sin(ang) * rr
            color = themed_color(scheme, (base + offset) % 1.0, PALETTE, phase)
            pygame.draw.circle(surface, color, (int(x), int(y)), dot_r)

    @staticmethod
    def _glow(surface: pygame.Surface, cx: float, cy: float, core_r: float, level: float) -> None:
        """Soft translucent halo behind the core (restored from v00.0A.02).

        Drawn with a normal (alpha) blit, not additive, so it reads as a gentle glow
        rather than a solid bright disc. The largest ring fits the surface exactly, so
        nothing clips to a square.
        """
        size = int(core_r * 4) + 2
        glow = pygame.Surface((size, size), pygame.SRCALPHA)
        gc = (size // 2, size // 2)
        for ring in range(4, 0, -1):
            radius = int(core_r * (0.4 + 0.4 * ring))  # max ~2.0*core_r, half-size is 2.0*core_r
            alpha = int(40 * ring * (0.5 + 0.5 * level))
            pygame.draw.circle(glow, (*COLOR_ACCENT, alpha), gc, radius)
        surface.blit(glow, glow.get_rect(center=(int(cx), int(cy))))

    def _update_rings(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        core_r: float,
        scale: float,
        onset: float,
        dt: float,
        scheme: str,
        phase: float,
    ) -> None:
        if onset > 0.4 and len(self._rings) < 12:
            self._rings.append(core_r)
        grow = scale * 1.4 * dt * self.theme.speed_scale
        kept: list[float] = []
        for r in self._rings:
            r += grow
            if r < scale * 1.2:
                kept.append(r)
                fade = clamp(1.0 - r / (scale * 1.2))
                color = _shade(themed_color(scheme, phase, PALETTE, 0.0), 0.3 + 0.7 * fade)
                pygame.draw.circle(surface, color, (int(cx), int(cy)), int(r), 2)
        self._rings = kept


def _shade(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    f = clamp(factor)
    return (int(color[0] * f), int(color[1] * f), int(color[2] * f))
