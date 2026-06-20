"""Build 17 (v00.0B.13): highlights, beat fade/shapes, logo effects, more colors.

Covers the new color schemes (theme palettes + Solid/Mono custom hue), the
selectable beat-indicator fade time and shapes, the extra logo effects, the
Beat/Motion control-bar highlights, and settings persistence (schema v16).
"""

from __future__ import annotations

import numpy as np
import pygame
import pytest

from audio_visualizer.app import _beat_fade_seconds
from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.beat_trigger import BeatTrigger
from audio_visualizer.config import (
    BEAT_FADE_CHOICES,
    BEAT_FADE_DEFAULT,
    BEAT_INDICATOR_SHAPES,
    COLOR_SCHEMES,
    PALETTE,
    SETTINGS_SCHEMA_VERSION,
    THEME_PALETTES,
)
from audio_visualizer.settings import Settings
from audio_visualizer.settings import load as load_settings
from audio_visualizer.settings import save as save_settings
from audio_visualizer.ui.beat_indicator import draw_beat_indicator
from audio_visualizer.visuals._helpers import set_custom_hue, themed_color
from audio_visualizer.visuals.logo import RenkLogo


# -- colors -------------------------------------------------------------------
def test_new_color_schemes_registered() -> None:
    for key in THEME_PALETTES:
        assert key in COLOR_SCHEMES
    assert "solid" in COLOR_SCHEMES
    assert "mono" in COLOR_SCHEMES


def test_theme_palette_scheme_uses_its_palette() -> None:
    # A theme scheme ignores the per-mode palette and samples its own.
    col = themed_color("ocean", 0.0, PALETTE)
    assert col == THEME_PALETTES["ocean"][0]


def test_solid_scheme_ignores_position_and_tracks_hue() -> None:
    set_custom_hue(0.0)  # red
    a = themed_color("solid", 0.1, PALETTE)
    b = themed_color("solid", 0.9, PALETTE)
    assert a == b  # one flat color regardless of position
    set_custom_hue(0.33)  # green
    assert themed_color("solid", 0.1, PALETTE) != a


def test_mono_scheme_ramps_brightness_with_position() -> None:
    set_custom_hue(0.6)
    dark = themed_color("mono", 0.0, PALETTE)
    bright = themed_color("mono", 1.0, PALETTE)
    assert sum(bright) > sum(dark)


# -- beat fade + shapes -------------------------------------------------------
def test_beat_fade_seconds_maps_each_choice() -> None:
    for key, _label, seconds in BEAT_FADE_CHOICES:
        assert _beat_fade_seconds(key) == seconds
    assert _beat_fade_seconds("nope") == _beat_fade_seconds(BEAT_FADE_DEFAULT)


def test_set_flash_tau_changes_decay_rate() -> None:
    bt = BeatTrigger()
    bt.set_flash_tau(1.0)
    bt.flash = 1.0
    bt.update(np.zeros(48, dtype=np.float32), is_silent=True, dt=0.5)
    assert bt.flash == pytest.approx(0.5, abs=0.02)  # tau=1s -> halves over 0.5s


def test_indicator_all_shapes_draw_without_error() -> None:
    surface = pygame.Surface((240, 180))
    canvas = surface.get_rect()
    for key, _label in BEAT_INDICATOR_SHAPES:
        for flash in (0.0, 0.8):
            draw_beat_indicator(surface, canvas, "center", 0.7, "bass", flash, key)


# -- logo effects -------------------------------------------------------------
def _logo_surface(size: int = 32) -> pygame.Surface:
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(surf, (40, 200, 255, 255), (size // 2, size // 2), size // 2, width=3)
    return surf


def _onset_frame(onset: float = 1.0) -> AnalysisFrame:
    return AnalysisFrame(
        waveform_mono=np.zeros(8, dtype=np.float32),
        band_energies=np.full(48, 0.6, dtype=np.float32),
        rms=0.5,
        peak=0.8,
        sample_rate=48000,
        timestamp=0.0,
        onset=onset,
    )


def test_logo_effects_draw_and_shockwave_spawns() -> None:
    logo = RenkLogo(surface=_logo_surface())
    logo.enabled = True
    logo.fx_shockwave = True
    logo.fx_glow = True
    logo.fx_throb = True
    screen = pygame.Surface((240, 200))
    # First frame at rest establishes the onset baseline; the second crosses it.
    logo.draw(screen, _onset_frame(onset=0.0), 0.016)
    logo.draw(screen, _onset_frame(onset=1.0), 0.016)
    assert logo._shockwaves  # a beat spawned a ring
    assert logo._glow > 0.0  # a beat kicked the glow


def test_logo_effects_off_spawn_nothing() -> None:
    logo = RenkLogo(surface=_logo_surface())
    logo.enabled = True
    logo.fx_shockwave = False
    logo.fx_glow = False
    screen = pygame.Surface((240, 200))
    logo.draw(screen, _onset_frame(onset=0.0), 0.016)
    logo.draw(screen, _onset_frame(onset=1.0), 0.016)
    assert not logo._shockwaves
    assert logo._glow == 0.0


# -- settings persistence -----------------------------------------------------
def test_new_settings_roundtrip(tmp_path) -> None:
    path = tmp_path / "settings.json"
    save_settings(
        Settings(
            beat_indicator_shape="star",
            beat_fade="slow",
            color_hue=0.42,
            logo_shockwave=True,
            logo_glow=True,
            logo_throb=True,
        ),
        path,
    )
    loaded = load_settings(path)
    assert loaded.schema_version >= 16
    assert loaded.beat_indicator_shape == "star"
    assert loaded.beat_fade == "slow"
    assert loaded.color_hue == pytest.approx(0.42)
    assert loaded.logo_shockwave is True
    assert loaded.logo_glow is True
    assert loaded.logo_throb is True


def test_settings_clamps_bad_values(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        '{"schema_version": 16, "beat_indicator_shape": "bogus", "beat_fade": "x",'
        ' "color_hue": 9.0}',
        encoding="utf-8",
    )
    loaded = load_settings(path)
    assert loaded.beat_indicator_shape == BEAT_INDICATOR_SHAPES[0][0]  # default
    assert loaded.beat_fade == BEAT_FADE_DEFAULT
    assert 0.0 <= loaded.color_hue <= 1.0


def test_schema_version_is_16_or_newer() -> None:
    assert SETTINGS_SCHEMA_VERSION >= 16
