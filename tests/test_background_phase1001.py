"""Phase 10.01: Background modal + reactivity/opacity knobs, new modes, glass fix."""

from __future__ import annotations

import numpy as np
import pygame
import pytest

from audio_visualizer import settings as settings_mod
from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.settings import Settings
from audio_visualizer.ui.background_panel import BackgroundActions, BackgroundPanel
from audio_visualizer.ui.style import _GLASS_MAX_RADIUS, STYLE, _radius
from audio_visualizer.visuals.background import Background
from audio_visualizer.visuals.base import Theme


@pytest.fixture(scope="module", autouse=True)
def _pygame_ready():
    pygame.init()
    pygame.display.set_mode((10, 10))
    yield
    pygame.quit()


def _frame(level: float = 0.8, onset: float = 1.0) -> AnalysisFrame:
    return AnalysisFrame(
        waveform_mono=np.sin(np.linspace(0, 6.28, 256)).astype(np.float32),
        band_energies=np.full(48, level, dtype=np.float32),
        rms=level,
        peak=level,
        sample_rate=48000,
        timestamp=0.0,
        onset=onset,
    )


def _make_bg_panel(calls: dict[str, str]) -> BackgroundPanel:
    return BackgroundPanel(
        BackgroundActions(
            set_mode=lambda v: calls.__setitem__("mode", v),
            set_sensitivity=lambda v: calls.__setitem__("sensitivity", v),
            set_opacity=lambda v: calls.__setitem__("opacity", v),
            set_height=lambda v: calls.__setitem__("height", v),
        ),
        mode_options=[("black", "Black"), ("spectrum", "Spectrum line")],
        sensitivity_options=[("1", "x1.00"), ("2", "x2.00")],
        opacity_options=[("0.5", "50%"), ("1", "100%")],
        height_options=[("low", "Low"), ("tall", "Tall")],
    )


def test_background_panel_dropdowns_route_callbacks() -> None:
    calls: dict[str, str] = {}
    panel = _make_bg_panel(calls)
    panel.open = True
    canvas = pygame.Rect(0, 0, 1280, 720)

    def _click(pos: tuple[int, int]) -> None:
        panel.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos), canvas)

    rows = {key: dd for key, _label, dd in panel._row_rects(canvas)}
    panel._sync_widgets(canvas)
    # Open the Background (mode) dropdown and pick the second option.
    _click(rows["mode"].center)
    _click(panel._dd["mode"]._option_rects()[1].center)
    # Open the Sensitivity dropdown and pick the second option.
    _click(rows["sensitivity"].center)
    _click(panel._dd["sensitivity"]._option_rects()[1].center)

    assert calls["mode"] == "spectrum"
    assert calls["sensitivity"] == "2"


def test_opacity_scales_spectrum_alpha() -> None:
    def peak_alpha(opacity: float) -> int:
        surface = pygame.Surface((240, 160), pygame.SRCALPHA)
        bg = Background(theme=Theme())
        bg.mode = "spectrum"
        bg.height_key = "tall"
        bg.opacity = opacity
        for _ in range(20):
            surface.fill((0, 0, 0, 0))
            bg.draw(surface, _frame(1.0), 0.05)
        return max(surface.get_at((x, 159))[3] for x in range(0, 240, 8))

    assert peak_alpha(1.0) > peak_alpha(0.25) > 0


def test_new_modes_render_without_error() -> None:
    surface = pygame.Surface((200, 140))
    bg = Background(theme=Theme())
    for mode in (
        "filaments",
        "mirror",
        "ribbon",
        "waves",
        "plasma",
        "starfield",
        "rain",
        "grid",
        "vignette",
    ):
        bg.mode = mode
        surface.fill((8, 8, 14))
        for _ in range(5):
            bg.draw(surface, _frame(), 0.05)  # must not raise


def test_glass_radius_is_capped_for_large_panels() -> None:
    try:
        STYLE.set_style("glass")
        assert _radius(pygame.Rect(0, 0, 30, 30)) == 15  # small control stays a pill
        assert _radius(pygame.Rect(0, 0, 360, 300)) == _GLASS_MAX_RADIUS  # panel is capped
    finally:
        STYLE.set_style("flat")


def test_settings_v5_persists_bg_sensitivity_and_opacity(tmp_path) -> None:
    path = tmp_path / "settings.json"
    assert settings_mod.save(Settings(bg_sensitivity=2.0, bg_opacity=0.5), path)
    loaded = settings_mod.load(path)
    assert loaded.schema_version == settings_mod.SETTINGS_SCHEMA_VERSION
    assert loaded.bg_sensitivity == 2.0
    assert loaded.bg_opacity == 0.5
    # Out-of-grid stored values snap to the nearest preset.
    path.write_text('{"schema_version": 5, "bg_opacity": 0.6}', encoding="utf-8")
    assert settings_mod.load(path).bg_opacity == 0.5
