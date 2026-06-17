"""Global background layer drawn *behind* every visual mode.

The App owns one :class:`Background` and draws it onto the canvas before the
active mode (which never clears the canvas), so the backdrop shows through
wherever the mode doesn't paint. Backdrops:

* ``black``     - the plain default (no-op; the App already cleared to COLOR_BG).
* ``spectrum``  - a thin colorful equalizer along the bottom edge (height-tunable).
* ``filaments`` - hair-thin (1px) rainbow lines at a tight pitch.
* ``mirror``    - a spectrum mirrored across the vertical center (top + bottom).
* ``ribbon``    - a scrolling oscilloscope waveform band along the bottom.
* ``gradient``  - a calm vertical magenta-tinted gradient.
* ``aurora``    - drifting soft color blobs; beats shove + swell them.
* ``starfield`` - slow drifting dots that twinkle on treble/onsets.
* ``vignette``  - edge glow that pulses on each beat.

Two global knobs apply to every reactive backdrop: ``sensitivity`` (reactivity
gain) and ``opacity`` (overall strength, so it can be a quiet hint). Backdrops are
read-only render helpers (frame + surface + dt + Theme), and fail-soft (the App
wraps the call). Heavy surfaces are cached by size.
"""

from __future__ import annotations

import math

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import (
    BG_AURORA_ALPHA,
    BG_AURORA_BLOBS,
    BG_AURORA_DRIFT,
    BG_AURORA_PULSE_PUSH,
    BG_AURORA_SIZE_GAIN,
    BG_FILAMENT_ALPHA,
    BG_FILAMENT_HUE_SPREAD,
    BG_FILAMENT_PITCH,
    BG_GRADIENT_BOTTOM,
    BG_HEIGHT_DEFAULT,
    BG_HEIGHT_FRACTIONS,
    BG_MODE_DEFAULT,
    BG_OPACITY_DEFAULT,
    BG_PALETTE,
    BG_PULSE_DECAY,
    BG_RIBBON_ALPHA,
    BG_RIBBON_SCROLL_PX,
    BG_SENSITIVITY_DEFAULT,
    BG_SPECTRUM_ALPHA,
    BG_SPECTRUM_ATTACK,
    BG_SPECTRUM_BAR_PITCH,
    BG_SPECTRUM_IDLE_FRACTION,
    BG_SPECTRUM_RELEASE,
    BG_STARFIELD_AREA_PER_STAR,
    BG_STARFIELD_BASE_ALPHA,
    BG_STARFIELD_DRIFT,
    BG_VIGNETTE_BASE_ALPHA,
    BG_VIGNETTE_PULSE_ALPHA,
    COLOR_BG,
)
from audio_visualizer.visuals._helpers import (
    clamp,
    palette_color,
    rainbow_color,
    resample_to,
    scale_color,
    themed_color,
)
from audio_visualizer.visuals.base import Theme

_AURORA_SPRITE_SIZE = 256
_VIGNETTE_TINT = (150, 90, 255)


class Background:
    """A switchable, audio-reactive backdrop composited beneath the active mode."""

    def __init__(self, theme: Theme, reduce_motion: bool = False) -> None:
        self.mode = BG_MODE_DEFAULT
        self.height_key = BG_HEIGHT_DEFAULT
        self.sensitivity = BG_SENSITIVITY_DEFAULT
        self.opacity = BG_OPACITY_DEFAULT
        self.theme = theme
        self.reduce_motion = reduce_motion
        self._t = 0.0
        self._dt = 0.0
        self._pulse = 0.0  # decaying beat/onset envelope (shared)
        self._spectrum_env: np.ndarray | None = None
        self._ribbon: np.ndarray | None = None
        self._grad_cache: tuple[tuple[int, int], pygame.Surface] | None = None
        self._aurora_sprite: pygame.Surface | None = None
        self._vignette_cache: tuple[tuple[int, int], pygame.Surface] | None = None
        self._stars: dict[str, np.ndarray] | None = None
        self._stars_size: tuple[int, int] | None = None

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        """Composite the current backdrop onto ``surface`` (no-op for ``black``)."""
        self._t += dt
        self._dt = dt
        self._pulse = max(self._pulse - dt * BG_PULSE_DECAY, 0.0)
        if frame is not None and not frame.is_silent:
            self._pulse = max(self._pulse, clamp(frame.onset * self.sensitivity))
        handler = getattr(self, f"_draw_{self.mode}", None)
        if handler is not None:
            handler(surface, frame)

    # -- shared helpers -------------------------------------------------------
    def _max_fraction(self) -> float:
        return BG_HEIGHT_FRACTIONS.get(self.height_key, BG_HEIGHT_FRACTIONS[BG_HEIGHT_DEFAULT])

    def _bar_envelope(self, frame: AnalysisFrame | None, n: int) -> np.ndarray:
        """Sensitivity-scaled, attack/release-smoothed bar heights in 0..1."""
        if frame is not None and not frame.is_silent:
            target = np.clip(
                resample_to(frame.band_energies.astype(np.float32), n) * self.sensitivity, 0.0, 1.0
            )
        else:
            target = np.full(n, BG_SPECTRUM_IDLE_FRACTION, dtype=np.float32)
        self._spectrum_env = _smooth_toward(self._spectrum_env, target)
        return self._spectrum_env

    def _alpha(self, base: int) -> int:
        return int(clamp(base * self.opacity, 0.0, 255.0))

    def _level(self, frame: AnalysisFrame | None) -> float:
        if frame is None or frame.is_silent:
            return 0.0
        return clamp(float(np.mean(frame.band_energies)) * self.sensitivity)

    def _treble(self, frame: AnalysisFrame | None) -> float:
        if frame is None or frame.is_silent:
            return 0.0
        bands = frame.band_energies
        return clamp(float(np.mean(bands[max(1, len(bands) * 2 // 3) :])) * self.sensitivity)

    # -- spectrum family ------------------------------------------------------
    def _draw_spectrum(self, surface: pygame.Surface, frame: AnalysisFrame | None) -> None:
        w, h = surface.get_size()
        n = max(8, w // BG_SPECTRUM_BAR_PITCH)
        env = self._bar_envelope(frame, n)
        max_h = h * self._max_fraction()
        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        bar_w = w / n
        alpha = self._alpha(BG_SPECTRUM_ALPHA)
        for i in range(n):
            bar_h = int(float(env[i]) * max_h)
            if bar_h < 1:
                continue
            x = int(i * bar_w)
            width = max(1, int(bar_w) - 1)
            color = themed_color(
                self.theme.color_scheme, i / max(1, n - 1), BG_PALETTE, self.theme.color_phase
            )
            pygame.draw.rect(layer, (*color, alpha), (x, h - bar_h, width, bar_h))
            pygame.draw.rect(layer, (*scale_color(color, 1.4), alpha), (x, h - bar_h, width, 2))
        surface.blit(layer, (0, 0))

    def _draw_mirror(self, surface: pygame.Surface, frame: AnalysisFrame | None) -> None:
        w, h = surface.get_size()
        n = max(8, w // BG_SPECTRUM_BAR_PITCH)
        env = self._bar_envelope(frame, n)
        max_h = h * self._max_fraction() * 0.5
        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        bar_w = w / n
        alpha = self._alpha(BG_SPECTRUM_ALPHA)
        for i in range(n):
            bar_h = int(float(env[i]) * max_h)
            if bar_h < 1:
                continue
            x = int(i * bar_w)
            width = max(1, int(bar_w) - 1)
            color = themed_color(
                self.theme.color_scheme, i / max(1, n - 1), BG_PALETTE, self.theme.color_phase
            )
            pygame.draw.rect(layer, (*color, alpha), (x, h - bar_h, width, bar_h))  # bottom
            pygame.draw.rect(layer, (*color, alpha), (x, 0, width, bar_h))  # top (mirror)
        surface.blit(layer, (0, 0))

    def _draw_filaments(self, surface: pygame.Surface, frame: AnalysisFrame | None) -> None:
        w, h = surface.get_size()
        n = max(16, w // BG_FILAMENT_PITCH)
        env = self._bar_envelope(frame, n)
        max_h = h * self._max_fraction()
        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        alpha = self._alpha(BG_FILAMENT_ALPHA)
        for i in range(n):
            bar_h = int(float(env[i]) * max_h)
            if bar_h < 1:
                continue
            x = int(i * w / n)
            hue = (i / n) * BG_FILAMENT_HUE_SPREAD + self.theme.color_phase
            color = rainbow_color(hue)
            pygame.draw.line(layer, (*color, alpha), (x, h), (x, h - bar_h))
            layer.set_at((x, max(0, h - bar_h)), (*scale_color(color, 1.6), alpha))
        surface.blit(layer, (0, 0))

    def _draw_ribbon(self, surface: pygame.Surface, frame: AnalysisFrame | None) -> None:
        w, h = surface.get_size()
        if self._ribbon is None or self._ribbon.shape[0] != w:
            self._ribbon = np.zeros(w, dtype=np.float32)
        k = max(1, BG_RIBBON_SCROLL_PX)
        self._ribbon = np.roll(self._ribbon, -k)
        if frame is not None and not frame.is_silent and frame.waveform_mono.size:
            chunk = resample_to(frame.waveform_mono.astype(np.float32), k) * self.sensitivity
            self._ribbon[-k:] = np.clip(chunk, -1.0, 1.0)
        else:
            self._ribbon[-k:] = 0.0
        band = h * self._max_fraction()
        center = h - band * 0.5
        amp = band * 0.5
        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        alpha = self._alpha(BG_RIBBON_ALPHA)
        for x in range(w):
            y = int(center - float(self._ribbon[x]) * amp)
            color = palette_color(BG_PALETTE, x / max(1, w - 1))
            lo, hi = (y, int(center)) if y < center else (int(center), y)
            pygame.draw.line(layer, (*color, alpha), (x, lo), (x, hi))
        surface.blit(layer, (0, 0))

    # -- gradient -------------------------------------------------------------
    def _draw_gradient(self, surface: pygame.Surface, frame: AnalysisFrame | None) -> None:
        size = surface.get_size()
        if self._grad_cache is None or self._grad_cache[0] != size:
            self._grad_cache = (size, _build_vertical_gradient(size, COLOR_BG, BG_GRADIENT_BOTTOM))
        surface.blit(self._grad_cache[1], (0, 0))
        if self.opacity < 1.0:  # fade the gradient back toward the black base
            veil = pygame.Surface(size, pygame.SRCALPHA)
            veil.fill((*COLOR_BG, int((1.0 - self.opacity) * 255)))
            surface.blit(veil, (0, 0))

    # -- aurora ---------------------------------------------------------------
    def _draw_aurora(self, surface: pygame.Surface, frame: AnalysisFrame | None) -> None:
        w, h = surface.get_size()
        if self._aurora_sprite is None:
            self._aurora_sprite = _build_radial_sprite(_AURORA_SPRITE_SIZE)
        level = self._level(frame)
        drift = BG_AURORA_DRIFT * (0.4 if self.reduce_motion else 1.0)
        base_radius = min(w, h) * 0.75
        radius = int(base_radius * (1.0 + BG_AURORA_SIZE_GAIN * level))
        push = self._pulse * BG_AURORA_PULSE_PUSH  # beats shove blobs off their path
        for i in range(BG_AURORA_BLOBS):
            phase = i * (math.tau / BG_AURORA_BLOBS)
            cx = w * (0.5 + 0.42 * math.sin(self._t * drift * math.tau + phase))
            cy = h * (0.5 + 0.42 * math.cos(self._t * drift * math.tau * 0.8 + phase * 1.3))
            cx += math.cos(phase) * push
            cy += math.sin(phase) * push
            tint = palette_color(BG_PALETTE, i / max(1, BG_AURORA_BLOBS - 1))
            intensity = (BG_AURORA_ALPHA / 255.0) * self.opacity * (0.6 + 0.8 * level)
            blob = self._aurora_sprite.copy()
            blob.fill((*scale_color(tint, intensity), 255), special_flags=pygame.BLEND_RGB_MULT)
            blob = pygame.transform.smoothscale(blob, (radius, radius))
            surface.blit(
                blob,
                (int(cx - radius / 2), int(cy - radius / 2)),
                special_flags=pygame.BLEND_RGB_ADD,
            )

    # -- starfield ------------------------------------------------------------
    def _draw_starfield(self, surface: pygame.Surface, frame: AnalysisFrame | None) -> None:
        w, h = surface.get_size()
        self._ensure_stars((w, h))
        stars = self._stars
        assert stars is not None
        drift = BG_STARFIELD_DRIFT * (0.35 if self.reduce_motion else 1.0)
        stars["y"] = (stars["y"] + drift * self._dt * stars["depth"]) % h
        twinkle = 0.5 + 0.5 * np.sin(self._t * 2.0 + stars["phase"])
        treble = self._treble(frame)
        brightness = (
            BG_STARFIELD_BASE_ALPHA * stars["depth"] * twinkle
            + treble * stars["depth"] * 220.0
            + self._pulse * 160.0
        )
        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(stars["x"].shape[0]):
            a = self._alpha(int(min(255.0, brightness[i])))
            if a <= 2:
                continue
            x, y = int(stars["x"][i]), int(stars["y"][i])
            r = 2 if stars["depth"][i] > 0.8 else 1
            pygame.draw.circle(layer, (235, 240, 255, a), (x, y), r)
        surface.blit(layer, (0, 0))

    def _ensure_stars(self, size: tuple[int, int]) -> None:
        if self._stars is not None and self._stars_size == size:
            return
        w, h = size
        count = max(24, (w * h) // BG_STARFIELD_AREA_PER_STAR)
        rng = np.random.default_rng(1234)
        self._stars = {
            "x": rng.uniform(0, w, count).astype(np.float32),
            "y": rng.uniform(0, h, count).astype(np.float32),
            "depth": rng.uniform(0.3, 1.0, count).astype(np.float32),
            "phase": rng.uniform(0, math.tau, count).astype(np.float32),
        }
        self._stars_size = size

    # -- vignette -------------------------------------------------------------
    def _draw_vignette(self, surface: pygame.Surface, frame: AnalysisFrame | None) -> None:
        size = surface.get_size()
        if self._vignette_cache is None or self._vignette_cache[0] != size:
            self._vignette_cache = (size, _build_vignette(size, _VIGNETTE_TINT))
        glow = BG_VIGNETTE_BASE_ALPHA + clamp(self._pulse) * BG_VIGNETTE_PULSE_ALPHA
        a = self._alpha(int(glow))
        if a <= 0:
            return
        tmp = self._vignette_cache[1].copy()
        tmp.fill((255, 255, 255, a), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(tmp, (0, 0))


def _smooth_toward(env: np.ndarray | None, target: np.ndarray) -> np.ndarray:
    """Attack/release smoothing of a bar envelope toward ``target`` (per element)."""
    if env is None or env.shape != target.shape:
        return target.copy()
    rising = target > env
    rate = np.where(rising, BG_SPECTRUM_ATTACK, BG_SPECTRUM_RELEASE).astype(np.float32)
    return env + (target - env) * rate


def _build_vertical_gradient(
    size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]
) -> pygame.Surface:
    """Opaque vertical gradient surface from ``top`` (y=0) to ``bottom`` (y=h)."""
    w, h = max(1, size[0]), max(1, size[1])
    column = np.zeros((h, 3), dtype=np.float32)
    for c in range(3):
        column[:, c] = np.linspace(top[c], bottom[c], h)
    arr = np.repeat(column[np.newaxis, :, :], w, axis=0)  # (w, h, 3) for surfarray
    surf = pygame.Surface((w, h))
    pygame.surfarray.blit_array(surf, arr.astype(np.uint8))
    return surf


def _build_radial_sprite(diameter: int) -> pygame.Surface:
    """An RGB radial sprite: white center fading to black at the edge (for additive)."""
    coords = np.linspace(-1.0, 1.0, diameter, dtype=np.float32)
    yy, xx = np.meshgrid(coords, coords, indexing="ij")
    dist = np.sqrt(xx * xx + yy * yy)
    falloff = np.clip(1.0 - dist, 0.0, 1.0) ** 2
    value = (falloff * 255.0).astype(np.uint8)
    arr = np.repeat(value[:, :, np.newaxis], 3, axis=2)
    surf = pygame.Surface((diameter, diameter))
    pygame.surfarray.blit_array(surf, arr)
    return surf


def _build_vignette(size: tuple[int, int], tint: tuple[int, int, int]) -> pygame.Surface:
    """A tinted edge-glow: transparent center fading to ``tint`` at the corners."""
    w, h = max(1, size[0]), max(1, size[1])
    xs = np.linspace(-1.0, 1.0, w, dtype=np.float32)
    ys = np.linspace(-1.0, 1.0, h, dtype=np.float32)
    xx, yy = np.meshgrid(xs, ys, indexing="ij")  # (w, h)
    dist = np.sqrt(xx * xx + yy * yy) / math.sqrt(2.0)
    alpha = (np.clip((dist - 0.45) / 0.55, 0.0, 1.0) ** 1.5 * 255.0).astype(np.uint8)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    rgb = pygame.surfarray.pixels3d(surf)
    rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2] = tint
    del rgb  # unlock before touching alpha
    pygame.surfarray.pixels_alpha(surf)[:] = alpha
    return surf
