"""The RenK logo: a global, audio-reactive overlay drawn over every visual mode.

This is **not** a visual mode (it never ``@register``s, so discovery ignores it).
The App owns one instance and draws it on top of the active mode each frame, so the
branding appears everywhere. It honors the shared :class:`Theme` (speed/color) and
the reduce-motion setting, and reuses the shared :class:`SparkField` for emission.

The logo is a transparent PNG (a glowing glass-tube wordmark in a ring). "Default"
color blits the picture as-is; "Rainbow+" tints a luminance copy with a hue that
cycles over time, so the same glass-tube shape glows through the spectrum.
"""

from __future__ import annotations

import logging

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import (
    LOGO_COLOR_DEFAULT,
    LOGO_CORNER_MARGIN,
    LOGO_EMIT_DEFAULT,
    LOGO_EMIT_PER_ONSET,
    LOGO_EMIT_SPEED,
    LOGO_ENABLED_DEFAULT,
    LOGO_FILENAME,
    LOGO_OPACITY_DEFAULT,
    LOGO_POSITION_DEFAULT,
    LOGO_PULSE_AMOUNT,
    LOGO_SIZE_DEFAULT,
    LOGO_SIZE_FRACTIONS,
    LOGO_SPIN_DEG_PER_SEC,
    LOGO_SPIN_ENERGY_GAIN,
    SPARK_MAX,
)
from audio_visualizer.resources import asset_path
from audio_visualizer.visuals._helpers import SparkField, clamp, rainbow_color
from audio_visualizer.visuals.base import Theme

logger = logging.getLogger(__name__)

# Fraction of the spectrum (low end) treated as "bass" for spin/emit reactivity.
_BASS_FRACTION = 0.125
# Emit only when onset strength clears this (avoids a constant dribble of sparks).
_EMIT_ONSET_MIN = 0.2


def _load_logo_surface() -> pygame.Surface | None:
    """Load the bundled logo PNG with alpha, or ``None`` if unavailable."""
    path = asset_path(LOGO_FILENAME)
    if path is None:
        return None
    try:
        return pygame.image.load(str(path)).convert_alpha()
    except (pygame.error, FileNotFoundError):
        logger.warning("Could not load logo image %s", path, exc_info=True)
        return None


def _to_luminance(surface: pygame.Surface) -> pygame.Surface:
    """Return a grayscale copy (RGB = luminance) that keeps the original alpha.

    Used as a tintable mask: multiplying it by a hue gives the same glass-tube glow
    in any color, so Rainbow+ can cycle the hue without a second baked asset.
    """
    rgb = pygame.surfarray.array3d(surface).astype(np.float32)
    alpha = pygame.surfarray.array_alpha(surface)
    gray = (rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)).astype(np.uint8)
    # Build the SRCALPHA surface directly (no convert_alpha -> no display required).
    lum = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    rgb_view = pygame.surfarray.pixels3d(lum)
    rgb_view[:] = np.dstack([gray, gray, gray])
    del rgb_view  # unlock before touching the alpha view
    alpha_view = pygame.surfarray.pixels_alpha(lum)
    alpha_view[:] = alpha
    del alpha_view  # unlock the surface
    return lum


class RenkLogo:
    """Audio-reactive branding overlay shared across all visual modes.

    Public attributes are plain preferences the App sets from settings/UI:
    ``enabled``, ``size_key``, ``position``, ``opacity``, ``color_mode``, ``emit``.
    """

    def __init__(
        self,
        reduce_motion: bool = False,
        theme: Theme | None = None,
        surface: pygame.Surface | None = None,
    ) -> None:
        self.reduce_motion = reduce_motion
        self.theme = theme if theme is not None else Theme()

        self.enabled = LOGO_ENABLED_DEFAULT
        self.size_key = LOGO_SIZE_DEFAULT
        self.position = LOGO_POSITION_DEFAULT
        self.opacity = LOGO_OPACITY_DEFAULT
        self.color_mode = LOGO_COLOR_DEFAULT
        self.emit = LOGO_EMIT_DEFAULT

        # ``surface`` lets tests inject a tiny image; otherwise load the asset.
        self._base = surface if surface is not None else _load_logo_surface()
        self._lum = _to_luminance(self._base) if self._base is not None else None

        self._angle = 0.0
        self._sparks = SparkField(SPARK_MAX)
        # Cache the scaled artwork; rebuilt when the target diameter changes.
        self._cached_diameter = -1
        self._scaled_colored: pygame.Surface | None = None
        self._scaled_lum: pygame.Surface | None = None

    @property
    def available(self) -> bool:
        """True when the logo image loaded and can be drawn."""
        return self._base is not None

    def _diameter(self, canvas: tuple[int, int]) -> int:
        min_side = min(canvas)
        return max(1, int(LOGO_SIZE_FRACTIONS.get(self.size_key, 0.4) * min_side))

    def _anchor_center(self, canvas: tuple[int, int], radius: float) -> tuple[float, float]:
        """Center point for the current position anchor (corners inset by margin)."""
        w, h = canvas
        margin = LOGO_CORNER_MARGIN * min(canvas) + radius
        anchors = {
            "center": (w / 2, h / 2),
            "top_left": (margin, margin),
            "top_right": (w - margin, margin),
            "bottom_left": (margin, h - margin),
            "bottom_right": (w - margin, h - margin),
        }
        return anchors.get(self.position, (w / 2, h / 2))

    def _ensure_scaled(self, diameter: int) -> None:
        """(Re)build the scaled artwork caches when the target size changes."""
        if diameter == self._cached_diameter or self._base is None:
            return
        size = (diameter, diameter)
        self._scaled_colored = pygame.transform.smoothscale(self._base, size)
        if self._lum is not None:
            self._scaled_lum = pygame.transform.smoothscale(self._lum, size)
        self._cached_diameter = diameter

    def _tinted_lum(self) -> pygame.Surface | None:
        """The luminance art multiplied by the current cycling hue (Rainbow+)."""
        if self._scaled_lum is None:
            return None
        hue = self.theme.color_phase % 1.0
        tinted = self._scaled_lum.copy()
        tinted.fill((*rainbow_color(hue), 255), special_flags=pygame.BLEND_RGB_MULT)
        return tinted

    def _frame_art(self) -> pygame.Surface | None:
        """Pick the base artwork for this frame (colored picture or tinted hue)."""
        if self.color_mode == "rainbow_plus":
            return self._tinted_lum()
        return self._scaled_colored

    def _bass(self, frame: AnalysisFrame | None) -> float:
        if frame is None or frame.band_energies.size == 0:
            return 0.0
        n = max(1, int(frame.band_energies.size * _BASS_FRACTION))
        return float(frame.band_energies[:n].mean())

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        """Render the logo (and its sparks) onto ``surface`` for this frame."""
        if not self.enabled or self._base is None:
            return

        canvas = surface.get_size()
        diameter = self._diameter(canvas)
        self._ensure_scaled(diameter)

        energy = clamp(frame.rms) if frame is not None else 0.0
        bass = 0.0 if self.reduce_motion else self._bass(frame)

        self._angle = (self._angle + self._spin_step(bass, dt)) % 360.0
        pulse = 1.0 if self.reduce_motion else 1.0 + LOGO_PULSE_AMOUNT * energy

        center = self._anchor_center(canvas, diameter / 2.0)
        self._blit_logo(surface, center, pulse)
        self._update_sparks(surface, frame, center, canvas, dt)

    def _spin_step(self, bass: float, dt: float) -> float:
        speed = self.theme.speed_scale
        gain = 0.0 if self.reduce_motion else LOGO_SPIN_ENERGY_GAIN * bass
        return (LOGO_SPIN_DEG_PER_SEC + gain) * dt * speed

    def _blit_logo(
        self, surface: pygame.Surface, center: tuple[float, float], pulse: float
    ) -> None:
        art = self._frame_art()
        if art is None:
            return
        # Neon-on-black art is composited additively: black pixels add nothing (so
        # there is never a visible bounding box), and opacity scales glow intensity.
        if self.opacity < 1.0:
            art = art.copy()
            value = int(self.opacity * 255)
            art.fill((value, value, value, 255), special_flags=pygame.BLEND_RGB_MULT)
        rotated = pygame.transform.rotozoom(art, self._angle, pulse)
        rect = rotated.get_rect(center=(int(center[0]), int(center[1])))
        surface.blit(rotated, rect, special_flags=pygame.BLEND_RGB_ADD)

    def _update_sparks(
        self,
        surface: pygame.Surface,
        frame: AnalysisFrame | None,
        center: tuple[float, float],
        canvas: tuple[int, int],
        dt: float,
    ) -> None:
        if self.emit and not self.reduce_motion and frame is not None:
            self._emit(frame, center, canvas)
        self._sparks.advance(dt, self.theme.speed_scale)
        self._sparks.render(
            surface,
            self.theme.color_scheme,
            self.theme.color_phase,
            canvas[0],
            canvas[1],
            self.theme.size_scale,
            trails=False,
        )

    def _emit(
        self, frame: AnalysisFrame, center: tuple[float, float], canvas: tuple[int, int]
    ) -> None:
        """Shoot sparks radially outward from the logo center on a beat."""
        if frame.onset <= _EMIT_ONSET_MIN:
            return
        count = max(1, int(LOGO_EMIT_PER_ONSET * frame.onset))
        cx = center[0] / canvas[0]
        cy = center[1] / canvas[1]
        for i in range(count):
            ang = (i / count) * 2.0 * np.pi + np.radians(self._angle)
            vx = float(np.cos(ang)) * LOGO_EMIT_SPEED
            vy = float(np.sin(ang)) * LOGO_EMIT_SPEED
            self._sparks.spawn(cx, cy, vx, vy, hue=(ang / (2.0 * np.pi)) % 1.0)
