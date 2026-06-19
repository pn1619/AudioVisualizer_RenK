"""Build 13 (v00.0B.15): Plasma/Beat intensity + UI-dropdown polish.

Covers the expanded Plasma intensity ladder, the VU-Meters ``Dual ×2`` needle
(both-tip Spark), the lowered Beat sensitivity ladder, and the new control-bar
Sensitivity-band dropdown (select + persistence).
"""

from __future__ import annotations

import numpy as np
import pygame
import pytest

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import (
    BEAT_SENSITIVITY_PARAMS,
    SENS_BAND_DEFAULT,
    SENS_BANDS,
)
from audio_visualizer.ui.controls import ControlActions, ControlBar
from audio_visualizer.visuals.meters import Meters
from audio_visualizer.visuals.plasma import Plasma


@pytest.fixture(scope="module", autouse=True)
def _pygame_ready():
    pygame.init()
    pygame.display.set_mode((10, 10))
    yield
    pygame.quit()


def _frame(n: int = 48, level: float = 0.8) -> AnalysisFrame:
    return AnalysisFrame(
        waveform_mono=np.zeros(256, dtype=np.float32),
        band_energies=np.full(n, level, dtype=np.float32),
        rms=level,
        peak=level,
        sample_rate=48000,
        timestamp=0.0,
        onset=0.9,
    )


def test_plasma_intensity_ladder_extended() -> None:
    option = next(o for o in Plasma.OPTIONS if o.key == "intensity")
    labels = [c.label for c in option.choices]
    # "Soft" was dropped (build 16); Normal is now the default first choice.
    assert labels == ["Normal", "Vivid", "Intense", "Blast", "Max"]
    assert "Soft" not in labels
    assert option.choices[-1].value > option.choices[0].value  # Max is the strongest


def test_plasma_draws_at_max_intensity() -> None:
    plasma = Plasma()
    option = next(o for o in Plasma.OPTIONS if o.key == "intensity")
    plasma.set_option_index("intensity", len(option.choices) - 1)
    surface = pygame.Surface((160, 120))
    plasma.draw(surface, _frame(), dt=1 / 60)  # must not raise


def test_meters_needle_has_dual_double() -> None:
    option = next(o for o in Meters.OPTIONS if o.key == "needle")
    labels = [c.label for c in option.choices]
    assert "Dual" in labels
    assert "Dual \u00d72" in labels


def test_meters_dual_double_draws_with_spark() -> None:
    """Needle ``Dual ×2`` with Spark on emits from both tips without error."""
    meters = Meters()
    meters.set_option_index("style", 2)  # needle style
    meters.set_option_index("needle", 5)  # Dual ×2
    meters.set_option_index("spark", 1)  # Spark on
    meters.on_enter()
    surface = pygame.Surface((400, 300))
    for _ in range(10):
        meters.draw(surface, _frame(), dt=1 / 60)  # must not raise


def test_beat_ladder_top_levels_fire_on_steady_music() -> None:
    """The lowered top levels drop the ratio toward/below 1.0 so steady tones fire."""
    assert BEAT_SENSITIVITY_PARAMS[0] is None
    ratios = [p[0] for p in BEAT_SENSITIVITY_PARAMS if p is not None]
    assert ratios == sorted(ratios, reverse=True)  # monotonically easier to fire
    assert ratios[-1] <= 1.0  # top level fires on energy that merely beats its average


def test_control_bar_sens_band_dropdown_routes() -> None:
    chosen: list[str] = []
    noop = lambda *_: None  # noqa: E731 - tiny test stub
    actions = ControlActions(
        toggle_capture=noop,
        prev_mode=noop,
        next_mode=noop,
        select_mode=noop,
        sensitivity_down=noop,
        sensitivity_up=noop,
        smoothing_down=noop,
        smoothing_up=noop,
        size_down=noop,
        size_up=noop,
        speed_down=noop,
        speed_up=noop,
        cycle_color_scheme=noop,
        select_color=noop,
        option_change=noop,
        toggle_reduce_motion=noop,
        open_logo_panel=noop,
        open_about=noop,
        toggle_fullscreen=noop,
        quit=noop,
        select_sens_band=chosen.append,
    )
    bar = ControlBar(actions, [("waveform", "Waveform")])
    bar.relayout(pygame.Rect(0, 0, 1600, 160))
    dd = bar._sens_band
    bar.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=dd.rect.center))
    bar.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=dd._option_rects()[1].center)
    )
    assert chosen == [SENS_BANDS[1][0]]


def test_sens_band_settings_round_trip(tmp_path) -> None:
    from audio_visualizer import settings as settings_mod

    path = tmp_path / "settings.json"
    assert settings_mod.save(settings_mod.Settings(sens_band="bass"), path) is True
    assert settings_mod.load(path).sens_band == "bass"
    # Junk falls back to the default rather than crashing.
    assert settings_mod.save(settings_mod.Settings(sens_band="not-a-band"), path) is True
    assert settings_mod.load(path).sens_band == SENS_BAND_DEFAULT
