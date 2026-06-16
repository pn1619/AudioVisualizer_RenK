"""Global background layer drawn *behind* every visual mode.

The App owns one :class:`Background` and draws it onto the canvas before the
active mode (which never clears the canvas), so the backdrop shows through
wherever the mode doesn't paint. Backdrops:

* ``black``    - the plain default (no-op; the App already cleared to COLOR_BG).
* ``spectrum`` - a thin, colorful audio-reactive equalizer along the bottom edge
  whose height is user-selectable.
* ``gradient`` - a calm vertical magenta-tinted gradient.
* ``aurora``   - a few large, softly drifting color blobs (additive glow).

Backdrops are pure-ish render helpers: read-only ``AnalysisFrame`` + surface +
``dt`` (+ the shared Theme), no capture/global state, and they fail-soft (the App
wraps the call). Heavy surfaces (gradient ramp, aurora sprite) are cached by size.
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
    BG_GRADIENT_BOTTOM,
    BG_HEIGHT_DEFAULT,
    BG_HEIGHT_FRACTIONS,
    BG_MODE_DEFAULT,
    BG_PALETTE,
    BG_SPECTRUM_ALPHA,
    BG_SPECTRUM_ATTACK,
    BG_SPECTRUM_BAR_PITCH,
    BG_SPECTRUM_IDLE_FRACTION,
    BG_SPECTRUM_RELEASE,
    COLOR_BG,
)
from audio_visualizer.visuals._helpers import (
    palette_color,
    resample_to,
    scale_color,
    themed_color,
)
from audio_visualizer.visuals.base import Theme

_AURORA_SPRITE_SIZE = 256


class Background:
    """A switchable, audio-reactive backdrop composited beneath the active mode."""

    def __init__(self, theme: Theme, reduce_motion: bool = False) -> None:
        self.mode = BG_MODE_DEFAULT
        self.height_key = BG_HEIGHT_DEFAULT
        self.theme = theme
        self.reduce_motion = reduce_motion
        self._t = 0.0
        self._spectrum_env: np.ndarray | None = None  # smoothed bar envelope
        self._grad_cache: tuple[tuple[int, int], pygame.Surface] | None = None
        self._aurora_sprite: pygame.Surface | None = None

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        """Composite the current backdrop onto ``surface`` (no-op for ``black``)."""
        self._t += dt
        if self.mode == "spectrum":
            self._draw_spectrum(surface, frame)
        elif self.mode == "gradient":
            self._draw_gradient(surface, frame)
        elif self.mode == "aurora":
            self._draw_aurora(surface, frame)

    # -- spectrum -------------------------------------------------------------
    def _draw_spectrum(self, surface: pygame.Surface, frame: AnalysisFrame | None) -> None:
        w, h = surface.get_size()
        n = max(8, w // BG_SPECTRUM_BAR_PITCH)
        if frame is not None and not frame.is_silent:
            target = resample_to(frame.band_energies.astype(np.float32), n)
        else:
            target = np.full(n, BG_SPECTRUM_IDLE_FRACTION, dtype=np.float32)
        self._spectrum_env = _smooth_toward(self._spectrum_env, target)

        max_h = h * BG_HEIGHT_FRACTIONS.get(self.height_key, BG_HEIGHT_FRACTIONS[BG_HEIGHT_DEFAULT])
        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        bar_w = w / n
        scheme, phase = self.theme.color_scheme, self.theme.color_phase
        for i in range(n):
            bar_h = int(float(self._spectrum_env[i]) * max_h)
            if bar_h < 1:
                continue
            x = int(i * bar_w)
            width = max(1, int(bar_w) - 1)
            color = themed_color(scheme, i / max(1, n - 1), BG_PALETTE, phase)
            pygame.draw.rect(layer, (*color, BG_SPECTRUM_ALPHA), (x, h - bar_h, width, bar_h))
            # Brighter 2px cap so the line reads as a glowing edge.
            cap = scale_color(color, 1.4)
            pygame.draw.rect(layer, (*cap, BG_SPECTRUM_ALPHA), (x, h - bar_h, width, 2))
        surface.blit(layer, (0, 0))

    # -- gradient -------------------------------------------------------------
    def _draw_gradient(self, surface: pygame.Surface, frame: AnalysisFrame | None) -> None:
        size = surface.get_size()
        if self._grad_cache is None or self._grad_cache[0] != size:
            self._grad_cache = (size, _build_vertical_gradient(size, COLOR_BG, BG_GRADIENT_BOTTOM))
        surface.blit(self._grad_cache[1], (0, 0))

    # -- aurora ---------------------------------------------------------------
    def _draw_aurora(self, surface: pygame.Surface, frame: AnalysisFrame | None) -> None:
        w, h = surface.get_size()
        if self._aurora_sprite is None:
            self._aurora_sprite = _build_radial_sprite(_AURORA_SPRITE_SIZE)
        level = _energy_level(frame)
        drift = BG_AURORA_DRIFT * (0.4 if self.reduce_motion else 1.0)
        radius = int(min(w, h) * 0.75)
        for i in range(BG_AURORA_BLOBS):
            phase = i * (math.tau / BG_AURORA_BLOBS)
            cx = w * (0.5 + 0.42 * math.sin(self._t * drift * math.tau + phase))
            cy = h * (0.5 + 0.42 * math.cos(self._t * drift * math.tau * 0.8 + phase * 1.3))
            tint = palette_color(BG_PALETTE, (i / max(1, BG_AURORA_BLOBS - 1)))
            intensity = (BG_AURORA_ALPHA / 255.0) * (0.6 + 0.8 * level)
            blob = self._aurora_sprite.copy()
            blob.fill((*scale_color(tint, intensity), 255), special_flags=pygame.BLEND_RGB_MULT)
            blob = pygame.transform.smoothscale(blob, (radius, radius))
            surface.blit(
                blob,
                (int(cx - radius / 2), int(cy - radius / 2)),
                special_flags=pygame.BLEND_RGB_ADD,
            )


def _smooth_toward(env: np.ndarray | None, target: np.ndarray) -> np.ndarray:
    """Attack/release smoothing of a bar envelope toward ``target`` (per element)."""
    if env is None or env.shape != target.shape:
        return target.copy()
    rising = target > env
    rate = np.where(rising, BG_SPECTRUM_ATTACK, BG_SPECTRUM_RELEASE).astype(np.float32)
    return env + (target - env) * rate


def _energy_level(frame: AnalysisFrame | None) -> float:
    """A calm 0..1 loudness proxy from the band energies (0 when idle)."""
    if frame is None or frame.is_silent:
        return 0.0
    return float(np.clip(np.mean(frame.band_energies), 0.0, 1.0))


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
