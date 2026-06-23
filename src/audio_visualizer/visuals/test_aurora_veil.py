"""Aurora Veil: full-screen curtains of light, each riding a frequency band.

Vertical curtains shimmer and drift over a dark starfield; each curtain's height/reach
rides a band of the spectrum, onsets flare them brighter, and ``rms`` lifts the overall
glow. Rendered as a low-resolution alpha field that is tinted per palette and upscaled
(the Plasma trick), so it stays cheap. A full-screen *mode*, distinct from the subtle
background aurora layer.

Shipped under a ``Test_`` name during evaluation; remove the prefix once approved.
"""

from __future__ import annotations

import numpy as np
import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import ONSET_THRESHOLD
from audio_visualizer.visuals._helpers import SHARED_PALETTES, clamp, palette_color, themed_color
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

_GRID_W = 180
_POLAR = SHARED_PALETTES[0]
_SOLAR = SHARED_PALETTES[1]
_STARS = {0: 0, 1: 90, 2: 200}
_SKY = (5, 7, 16)

_PRESET = ModeOption(
    "preset",
    "Preset",
    (
        OptionChoice("Custom", 0),
        OptionChoice("Polar Night", 1),
        OptionChoice("Solar Storm", 2),
        OptionChoice("Calm Veil", 3),
    ),
    default_index=0,
)
_CURTAINS = ModeOption(
    "curtains",
    "Curtains",
    (OptionChoice("2", 2), OptionChoice("3", 3), OptionChoice("4", 4), OptionChoice("5", 5)),
    default_index=1,
)
_STYLE = ModeOption(
    "style",
    "Style",
    (OptionChoice("Curtains", 0), OptionChoice("Ribbons", 1), OptionChoice("Veil", 2)),
    default_index=0,
)
_DRIFT = ModeOption(
    "drift",
    "Drift",
    (OptionChoice("Still", 0.0), OptionChoice("Slow", 0.06), OptionChoice("Fast", 0.16)),
    default_index=1,
)
_TURBULENCE = ModeOption(
    "turb",
    "Turbulence",
    (OptionChoice("Calm", 0.02), OptionChoice("Wavy", 0.06), OptionChoice("Stormy", 0.12)),
    default_index=1,
)
_PALETTE = ModeOption(
    "apalette",
    "Palette",
    (OptionChoice("Polar", 0), OptionChoice("Solar", 1), OptionChoice("Theme", 2)),
    default_index=0,
)
_STARSOPT = ModeOption(
    "stars",
    "Stars",
    (OptionChoice("Off", 0), OptionChoice("Few", 1), OptionChoice("Many", 2)),
    default_index=1,
)


@register(key="test_aurora_veil", display_name="Test_Aurora Veil", order=70)
class TestAuroraVeil(BaseVisualizer):
    """Band-reactive aurora curtains over a starfield, as a low-res tinted field."""

    OPTIONS = (_PRESET, _CURTAINS, _STYLE, _DRIFT, _TURBULENCE, _PALETTE, _STARSOPT)
    PRESETS = {
        1: {"curtains": 1, "style": 0, "drift": 1, "turb": 1, "apalette": 0, "stars": 1},
        2: {"curtains": 3, "style": 0, "drift": 2, "turb": 2, "apalette": 1, "stars": 0},
        3: {"curtains": 0, "style": 2, "drift": 1, "turb": 0, "apalette": 0, "stars": 2},
    }

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._t = 0.0
        self._drift = 0.0
        self._flare = 0.0
        self._grid: tuple[int, int] | None = None
        self._xx: np.ndarray | None = None
        self._yy: np.ndarray | None = None
        self._vcol: np.ndarray | None = None  # per-row color ramp (GH, 3)
        self._stars: np.ndarray | None = None
        self._star_n = -1
        self._rng = np.random.default_rng(70)
        self._lut_key: tuple[int, str] = (-1, "")
        self._palette = _POLAR

    def on_enter(self) -> None:
        self._t = self._drift = self._flare = 0.0
        self._grid = None
        self._stars = None
        self._star_n = -1
        self._rng = np.random.default_rng(70)

    def _ensure_grid(self, w: int, h: int) -> None:
        gw = _GRID_W
        gh = max(2, int(gw * h / w))
        if self._grid == (gw, gh):
            return
        xs = np.linspace(0.0, 1.0, gw, dtype=np.float32)
        ys = np.linspace(0.0, 1.0, gh, dtype=np.float32)
        self._xx, self._yy = np.meshgrid(xs, ys)
        self._grid = (gw, gh)
        self._refresh_ramp(gh)

    def _refresh_ramp(self, gh: int) -> None:
        self._ensure_palette()
        ys = np.linspace(0.0, 1.0, gh)
        self._vcol = np.array([palette_color(self._palette, 1.0 - y) for y in ys], dtype=np.float32)

    def _ensure_palette(self) -> None:
        mode = int(self.option("apalette"))
        scheme = self.theme.color_scheme
        if self._lut_key == (mode, scheme):
            return
        if mode == 2:
            self._palette = tuple(
                themed_color(scheme, i / 4.0, _POLAR, self.theme.color_phase) for i in range(5)
            )
        else:
            self._palette = _SOLAR if mode == 1 else _POLAR
        self._lut_key = (mode, scheme)
        if self._grid is not None:
            self._refresh_ramp(self._grid[1])

    def _ensure_stars(self, w: int, h: int) -> None:
        n = _STARS[int(self.option("stars"))]
        if n == self._star_n:
            return
        if n == 0:
            self._stars = None
        else:
            xs = self._rng.uniform(0, 1, n)
            ys = self._rng.uniform(0, 0.85, n)  # mostly upper sky
            br = self._rng.uniform(0.3, 1.0, n)
            self._stars = np.stack([xs, ys, br], axis=1).astype(np.float32)
        self._star_n = n

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        self._ensure_palette()
        self._ensure_grid(w, h)
        self._ensure_stars(w, h)
        assert self._xx is not None and self._yy is not None and self._vcol is not None

        level = 0.0 if frame is None or frame.is_silent else clamp(frame.rms * 2.0)
        onset = 0.0 if frame is None else frame.onset
        self._t += dt * self.theme.speed_scale * (0.4 if self.reduce_motion else 1.0)
        self._drift += dt * float(self.option("drift")) * self.theme.speed_scale
        self._flare = max(self._flare - dt * 2.0, onset if onset >= ONSET_THRESHOLD else 0.0)

        surface.fill(_SKY)
        self._draw_stars(surface, w, h)
        intensity = self._field(frame, level)
        rgb = np.clip(self._vcol[:, None, :] * intensity[..., None], 0, 255).astype(np.uint8)
        small = pygame.surfarray.make_surface(np.transpose(rgb, (1, 0, 2)))
        surface.blit(
            pygame.transform.smoothscale(small, (w, h)), (0, 0), special_flags=pygame.BLEND_ADD
        )

    def _field(self, frame: AnalysisFrame | None, level: float) -> np.ndarray:
        assert self._xx is not None and self._yy is not None
        xs, ys = self._xx, self._yy
        curtains = int(self.option("curtains"))
        energy = self._curtain_energy(frame, curtains, xs.shape[1])  # (GW,)
        turb = float(self.option("turb")) * (0.5 if self.reduce_motion else 1.0)
        style = int(self.option("style"))

        warp = turb * np.sin(ys * 9.0 + self._t * 1.5)
        # Sample energy at the warped x (clamped, not wrapped, so there is no seam); the
        # drift only rides the seamless sine phases below, sliding the shimmer sideways.
        idx = np.clip(((xs + warp) * (energy.size - 1)), 0, energy.size - 1).astype(np.int32)
        e = energy[idx]
        col_h = 0.3 + 0.65 * e
        v = np.clip(1.0 - ys / np.maximum(col_h, 1e-3), 0.0, 1.0)
        dph = self._drift * 6.0
        shimmer = 0.55 + 0.45 * np.sin((xs * 22.0) + ys * 3.0 + self._t * 2.0 + dph)
        striations = 0.7 + 0.3 * np.sin(xs * 90.0 + dph)
        base = e * v
        if style == 0:  # curtains: sharp vertical striations
            inten = base * shimmer * striations
        elif style == 1:  # ribbons: horizontal flowing bands
            inten = base * (0.5 + 0.5 * np.sin(ys * 10.0 - self._t * 2.0)) * shimmer
        else:  # veil: smooth wash
            inten = base * (0.7 + 0.3 * shimmer)
        gain = (0.5 + 0.9 * level) * (1.0 + 1.2 * self._flare)
        return np.clip(inten * gain * 1.6, 0.0, 1.0)

    def _curtain_energy(self, frame: AnalysisFrame | None, curtains: int, gw: int) -> np.ndarray:
        from audio_visualizer.visuals._helpers import resample_to, smooth_wave

        if frame is None or not frame.band_energies.size:
            grouped = np.full(curtains, 0.12, dtype=np.float32)
        else:
            grouped = resample_to(frame.band_energies.astype(np.float32), curtains)
        wide = resample_to(grouped, gw)
        return smooth_wave(wide, 0.05)

    def _draw_stars(self, surface: pygame.Surface, w: int, h: int) -> None:
        if self._stars is None:
            return
        twinkle = 0.6 + 0.4 * np.sin(self._t * 3.0 + self._stars[:, 0] * 30.0)
        for (sx, sy, br), tw in zip(self._stars, twinkle, strict=False):
            c = int(clamp(float(br) * float(tw)) * 220) + 20
            surface.set_at((int(sx * w), int(sy * h)), (c, c, min(255, c + 20)))
