"""Phase 10: global background layer, gradient accent, and settings v4."""

from __future__ import annotations

import json

import numpy as np
import pygame
import pytest

from audio_visualizer import settings as settings_mod
from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import BG_MODES
from audio_visualizer.settings import Settings
from audio_visualizer.ui.style import STYLE, draw_panel
from audio_visualizer.visuals.background import Background
from audio_visualizer.visuals.base import Theme


@pytest.fixture(scope="module", autouse=True)
def _pygame_ready():
    pygame.init()
    pygame.display.set_mode((10, 10))
    yield
    pygame.quit()


def _frame(level: float = 0.6) -> AnalysisFrame:
    return AnalysisFrame(
        waveform_mono=np.zeros(64, dtype=np.float32),
        band_energies=np.full(48, level, dtype=np.float32),
        rms=level,
        peak=level,
        sample_rate=48000,
        timestamp=0.0,
    )


def test_black_background_is_a_noop() -> None:
    surface = pygame.Surface((200, 120))
    surface.fill((10, 10, 18))
    bg = Background(theme=Theme())
    bg.mode = "black"
    bg.draw(surface, _frame(), 0.016)
    assert surface.get_at((100, 60))[:3] == (10, 10, 18)


def test_spectrum_background_paints_bottom_edge() -> None:
    surface = pygame.Surface((240, 160))
    surface.fill((10, 10, 18))
    bg = Background(theme=Theme())
    bg.mode = "spectrum"
    bg.height_key = "tall"
    # Smoothing ramps up over frames, so advance a few.
    for _ in range(20):
        bg.draw(surface, _frame(1.0), 0.05)
    bottom_row = [surface.get_at((x, 159))[:3] for x in range(0, 240, 12)]
    assert any(rgb != (10, 10, 18) for rgb in bottom_row), "spectrum should paint the bottom edge"
    # The very top should stay untouched by the bottom spectrum line.
    assert surface.get_at((120, 2))[:3] == (10, 10, 18)


def test_all_background_modes_render_without_error() -> None:
    surface = pygame.Surface((200, 120))
    bg = Background(theme=Theme())
    for mode in BG_MODES:
        bg.mode = mode
        surface.fill((10, 10, 18))
        for _ in range(3):
            bg.draw(surface, _frame(), 0.05)  # must not raise


def test_gradient_accent_sets_endpoints_and_draws() -> None:
    try:
        STYLE.set_accent("aurora")
        assert STYLE.accent_grad is not None
        surface = pygame.Surface((120, 30), pygame.SRCALPHA)
        rect = pygame.Rect(0, 0, 120, 30)
        draw_panel(surface, rect, accent_fill=True)  # gradient fill path
        draw_panel(surface, rect, accent_border=True)  # gradient ring path
    finally:
        STYLE.set_accent("cyan")
        assert STYLE.accent_grad is None


def test_settings_v5_roundtrip_and_migration(tmp_path) -> None:
    path = tmp_path / "settings.json"
    saved = Settings(ui_accent="aurora", bg_mode="spectrum", bg_height="high")
    assert settings_mod.save(saved, path)
    loaded = settings_mod.load(path)
    assert loaded.schema_version == 5
    assert (loaded.ui_accent, loaded.bg_mode, loaded.bg_height) == ("aurora", "spectrum", "high")

    # An old v3 file (no Phase-10 keys) migrates to the new defaults.
    path.write_text(json.dumps({"schema_version": 3, "ui_style": "glass"}), encoding="utf-8")
    migrated = settings_mod.load(path)
    assert migrated.schema_version == 5
    assert (migrated.ui_accent, migrated.bg_mode, migrated.bg_height) == ("cyan", "black", "medium")
