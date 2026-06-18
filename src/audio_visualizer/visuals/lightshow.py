"""Light Show: radial beams from a pulsing core, driven by band energy.

With ``Particles = Off`` the beams are clean solid rays (the classic look). Turning
particles on rebuilds each beam from a string of pulsing beads and lets the beams
shoot small sparks outward on onsets (which can leave a fading trail). The core can
be a disc, a hollow ring, a waveform ring, or a radiating burst.
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
    draw_ring,
    ring_points,
    scale_color,
    themed_color,
)
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_MAX_LEN_FRACTION = 0.47
_BEAM_LENGTH_BASE = 0.25
_ROTATE_RATE = 0.27
_PULSE_RATE = 4.0
_PARTICLE_SIZE_BASE = 2.0
_PARTICLE_SIZE_GAIN = 6.0
_BEAM_BRIGHTNESS_BASE = 0.5
_CORE_SIZE_FACTOR = 1.4
_CORE_LINE_WIDTH = 3
_CORE_WAVE_AMPLITUDE = 0.35
_CORE_BURST_SPOKES = 12
_EMIT_SPEED = 0.11
_EMIT_SMALL_SIZE = 0.6
_SOLID_WIDTH_GAIN = 5  # solid-beam width = 1 + energy * this

_CORE_DISC, _CORE_HOLLOW, _CORE_WAVE, _CORE_BURST = 0, 1, 2, 3

_PRESET = ModeOption(
    "preset",
    "Preset",
    (
        OptionChoice("Custom", 0),
        OptionChoice("Classic", 1),
        OptionChoice("Beads", 2),
        OptionChoice("Burst", 3),
    ),
    default_index=0,
)
_BEAMS = ModeOption(
    "beams",
    "Beams",
    (OptionChoice("16", 16), OptionChoice("24", 24), OptionChoice("48", 48)),
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


@register(key="lightshow", display_name="Light Show", order=30)
class LightShow(BaseVisualizer):
    """Radial beams + shapeable core; particles turn beams into bead strings + sparks."""

    STROBES = True
    OPTIONS = (_PRESET, _BEAMS, _CORE, PARTICLES_OPTION, TRAIL_OPTION)
    PRESETS = {
        1: {"particles": 0, "core": 0},  # Classic solid beams
        2: {"particles": 1, "core": 0},  # Bead beams
        3: {"particles": 2, "core": 3},  # Dense beads + burst core
    }

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

        # Honor a mid-session reduce-motion toggle (cap is fixed at construction).
        self._sparks.cap = SPARK_MAX_REDUCED if self.reduce_motion else SPARK_MAX
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
        beams = int(self.option("beams"))
        if self.option("particles") > 0:
            self._draw_bead_beams(surface, cx, cy, max_len, w, h, frame, beams, scheme, phase)
        else:
            self._draw_solid_beams(surface, cx, cy, max_len, frame, beams, scheme, phase)

    def _draw_bead_beams(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        max_len: float,
        w: int,
        h: int,
        frame: AnalysisFrame,
        beams: int,
        scheme: str,
        phase: float,
    ) -> None:
        bands = frame.band_energies
        beads = int(6 + 4 * self.option("particles"))
        emit = not self.reduce_motion and frame.onset >= ONSET_THRESHOLD
        for i in range(beams):
            energy = float(bands[i * bands.size // beams])
            angle = self._angle + (2.0 * math.pi * i / beams)
            dx, dy = math.cos(angle), math.sin(angle)
            length = max_len * (_BEAM_LENGTH_BASE + energy)
            self._draw_beads(
                surface, cx, cy, dx, dy, length, beads, i, beams, energy, scheme, phase
            )
            if emit:
                self._emit_from_tip(cx + dx * length, cy + dy * length, dx, dy, w, h, i / beams)

    def _draw_solid_beams(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
        max_len: float,
        frame: AnalysisFrame,
        beams: int,
        scheme: str,
        phase: float,
    ) -> None:
        bands = frame.band_energies
        for i in range(beams):
            energy = float(bands[i * bands.size // beams])
            if energy <= 0.01:
                continue
            angle = self._angle + (2.0 * math.pi * i / beams)
            dx, dy = math.cos(angle), math.sin(angle)
            length = energy * max_len
            color = scale_color(
                themed_color(scheme, i / max(1, beams - 1), PALETTE, phase),
                _BEAM_BRIGHTNESS_BASE + energy,
            )
            width = 1 if self.reduce_motion else max(1, int(1 + energy * _SOLID_WIDTH_GAIN))
            pygame.draw.line(surface, color, (cx, cy), (cx + dx * length, cy + dy * length), width)

    def _draw_beads(
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
        speed = _EMIT_SPEED * self._rng.uniform(0.7, 1.3)
        self._sparks.spawn(
            x=ex / w, y=ey / h, vx=dx * speed, vy=dy * speed, hue=hue, size=_EMIT_SMALL_SIZE
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
        else:
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
