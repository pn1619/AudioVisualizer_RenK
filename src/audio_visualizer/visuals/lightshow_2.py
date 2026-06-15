"""Light Show 2: radial beams built from pulsing particles + a shapeable core.

Each radial beam is a string of particles (count is an option) running out from the
center. Every particle swells/shrinks with the music, and — when ``Emit`` is on —
beams occasionally shoot out smaller free particles (which can leave a fading trail).
The pulsing core can take several shapes (disc / hollow ring / waveform ring / burst).
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
    draw_ring,
    ring_points,
    scale_color,
    themed_color,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

# Longest beam as a fraction of half the min canvas side.
_MAX_LEN_FRACTION = 0.46
# Beam length = max_len * (this base + beam energy).
_BEAM_LENGTH_BASE = 0.25
# Beam rotation rate in radians/sec (scaled by the global speed control).
_ROTATE_RATE = 0.25
# Per-particle size pulsing rate (radians/sec) so beads "breathe" out of phase.
_PULSE_RATE = 4.0
# Particle radius (px) = base + (energy + pulse) * gain, then × the size control.
_PARTICLE_SIZE_BASE = 2.0
_PARTICLE_SIZE_GAIN = 6.0
# Baseline beam-particle brightness before per-beam energy is added.
_BEAM_BRIGHTNESS_BASE = 0.45
# Pulsing-core radius = rms * max_len * this.
_CORE_SIZE_FACTOR = 1.3
# Core ring/burst line width (px) and how far the waveform core wobbles.
_CORE_LINE_WIDTH = 3
_CORE_WAVE_AMPLITUDE = 0.35
# "Burst" core: number of short spokes.
_CORE_BURST_SPOKES = 12
# Emitted sparks: outward speed (normalized units/sec) and beams firing per onset.
_EMIT_SPEED = 0.11
_EMIT_SMALL_SIZE = 0.6  # emitted sparks are smaller than the beam beads

# Core-shape option values.
_CORE_DISC, _CORE_HOLLOW, _CORE_WAVE, _CORE_BURST = 0, 1, 2, 3

_BEAMS = ModeOption(
    "beams",
    "Beams",
    (OptionChoice("8", 8), OptionChoice("16", 16), OptionChoice("24", 24)),
    default_index=1,
)
_PARTICLES = ModeOption(
    "particles",
    "Beads",
    (OptionChoice("Few", 6), OptionChoice("Normal", 10), OptionChoice("Many", 16)),
    default_index=1,
)
_CORE = ModeOption(
    "core",
    "Core",
    (
        OptionChoice("Disc", _CORE_DISC),
        OptionChoice("Hollow", _CORE_HOLLOW),
        OptionChoice("Waveform", _CORE_WAVE),
        OptionChoice("Burst", _CORE_BURST),
    ),
    default_index=0,
)
_EMIT = ModeOption(
    "emit",
    "Emit",
    (OptionChoice("Off", 0), OptionChoice("On", 1)),
    default_index=1,
)


@register(key="lightshow_2", display_name="Light Show 2", order=35)
class LightShow2(BaseVisualizer):
    """Radial beams made of pulsing particles, optional emitted sparks + shapeable core."""

    STROBES = True
    OPTIONS = (_BEAMS, _PARTICLES, _CORE, _EMIT, TRAIL_OPTION)

    def __init__(
        self, reduce_motion: bool = False, theme: Theme | None = None, seed: int = 4242
    ) -> None:
        super().__init__(reduce_motion, theme)
        self._seed = seed
        self._rng = random.Random(seed)
        self._angle = 0.0
        self._t = 0.0
        cap = SPARK_MAX_REDUCED if reduce_motion else SPARK_MAX
        self._sparks = SparkField(cap)

    def on_enter(self) -> None:
        self._angle = 0.0
        self._t = 0.0
        self._rng.seed(self._seed)
        self._sparks.clear()

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 2 or h < 2:
            return
        cx, cy = w / 2.0, h / 2.0
        max_len = min(w, h) * _MAX_LEN_FRACTION
        scheme = self.theme.color_scheme
        phase = self.theme.color_phase

        self._t += dt
        if not self.reduce_motion:
            self._angle = (self._angle + dt * _ROTATE_RATE * self.theme.speed_scale) % (
                2.0 * math.pi
            )

        rms = frame.rms if frame is not None else 0.0
        peak = frame.peak if frame is not None else 0.0
        self._draw_core(surface, cx, cy, max_len, rms, peak, frame, scheme, phase)

        if frame is not None and not frame.is_silent and frame.band_energies.size > 0:
            self._draw_beams(surface, cx, cy, max_len, w, h, frame, scheme, phase)

        self._sparks.advance(dt, self.theme.speed_scale)
        trails = self.option("trails") >= 1
        self._sparks.render(surface, scheme, phase, w, h, self.theme.size_scale, trails)

    # -- beams ----------------------------------------------------------------
    def _draw_beams(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        max_len: float,
        w: int,
        h: int,
        frame: AnalysisFrame,
        scheme: str,
        phase: float,
    ) -> None:
        bands = frame.band_energies
        beams = int(self.option("beams"))
        beads = int(self.option("particles"))
        emit = self.option("emit") >= 1 and not self.reduce_motion
        fire = emit and frame.onset >= ONSET_THRESHOLD
        for i in range(beams):
            energy = float(bands[i * bands.size // beams])
            angle = self._angle + (2.0 * math.pi * i / beams)
            length = max_len * (_BEAM_LENGTH_BASE + energy)
            dx, dy = math.cos(angle), math.sin(angle)
            self._draw_beam_beads(
                surface, cx, cy, dx, dy, length, beads, i, beams, energy, scheme, phase
            )
            if fire:
                self._emit_from_tip(cx + dx * length, cy + dy * length, dx, dy, w, h, i / beams)

    def _draw_beam_beads(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        dx: float,
        dy: float,
        length: float,
        beads: int,
        i: int,
        beams: int,
        energy: float,
        scheme: str,
        phase: float,
    ) -> None:
        size_scale = self.theme.size_scale
        for j in range(beads):
            frac = (j + 1) / beads
            px = cx + dx * length * frac
            py = cy + dy * length * frac
            pulse = 0.5 * (1.0 + math.sin(self._t * _PULSE_RATE + i + j))
            radius = max(
                1, int((_PARTICLE_SIZE_BASE + (energy + pulse) * _PARTICLE_SIZE_GAIN) * size_scale)
            )
            color = scale_color(
                themed_color(scheme, frac + i / beams, PALETTE, phase),
                _BEAM_BRIGHTNESS_BASE + energy,
            )
            pygame.draw.circle(surface, color, (int(px), int(py)), radius)

    def _emit_from_tip(
        self, ex: float, ey: float, dx: float, dy: float, w: int, h: int, hue: float
    ) -> None:
        """Shoot a small spark outward from a beam tip (normalized space)."""
        speed = _EMIT_SPEED * self._rng.uniform(0.7, 1.3)
        self._sparks.spawn(
            x=ex / w,
            y=ey / h,
            vx=dx * speed,
            vy=dy * speed,
            hue=hue,
            size=_EMIT_SMALL_SIZE,
        )

    # -- core -----------------------------------------------------------------
    def _draw_core(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        max_len: float,
        rms: float,
        peak: float,
        frame: AnalysisFrame | None,
        scheme: str,
        phase: float,
    ) -> None:
        shape = int(self.option("core"))
        core_r = max(3.0, rms * max_len * _CORE_SIZE_FACTOR)
        color = scale_color(themed_color(scheme, peak, PALETTE, phase), 1.0)
        center = (int(cx), int(cy))
        if shape == _CORE_DISC:
            pygame.draw.circle(surface, color, center, int(core_r))
        elif shape == _CORE_HOLLOW:
            pygame.draw.circle(surface, color, center, int(core_r), _CORE_LINE_WIDTH)
        elif shape == _CORE_WAVE:
            self._draw_wave_core(surface, cx, cy, core_r, frame, scheme, phase)
        else:  # _CORE_BURST
            self._draw_burst_core(surface, cx, cy, core_r, color)

    def _draw_wave_core(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        core_r: float,
        frame: AnalysisFrame | None,
        scheme: str,
        phase: float,
    ) -> None:
        samples = (
            frame.waveform_mono if frame is not None and frame.waveform_mono.size > 0 else None
        )
        if samples is None:
            pygame.draw.circle(
                surface,
                themed_color(scheme, 0.5, PALETTE, phase),
                (int(cx), int(cy)),
                int(core_r),
                _CORE_LINE_WIDTH,
            )
            return
        pts = ring_points(cx, cy, core_r, core_r * _CORE_WAVE_AMPLITUDE, samples, points=160)
        draw_ring(surface, scheme, phase, pts, _CORE_LINE_WIDTH)

    def _draw_burst_core(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        core_r: float,
        color: tuple[int, int, int],
    ) -> None:
        for k in range(_CORE_BURST_SPOKES):
            a = self._angle * 2.0 + (2.0 * math.pi * k / _CORE_BURST_SPOKES)
            ex = cx + math.cos(a) * core_r
            ey = cy + math.sin(a) * core_r
            pygame.draw.line(
                surface, color, (int(cx), int(cy)), (int(ex), int(ey)), _CORE_LINE_WIDTH
            )
