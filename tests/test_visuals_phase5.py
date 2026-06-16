"""Phase 5: per-mode options, rainbow_plus, snowfall fall/wind, control bar."""

from __future__ import annotations

import numpy as np
import pygame
import pytest

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import PALETTE
from audio_visualizer.ui.controls import ControlActions, ControlBar, OptionSpec
from audio_visualizer.visuals._helpers import rainbow_color, themed_color
from audio_visualizer.visuals.snowfall import Snowfall
from audio_visualizer.visuals.waveform import Waveform


@pytest.fixture(scope="module", autouse=True)
def _pygame_ready():
    pygame.init()
    yield
    pygame.quit()


def _loud_frame() -> AnalysisFrame:
    wave = (0.6 * np.sin(np.linspace(0, 30, 2048))).astype(np.float32)
    return AnalysisFrame(
        waveform_mono=wave,
        band_energies=np.full(48, 0.8, dtype=np.float32),
        rms=0.5,
        peak=0.8,
        sample_rate=48000,
        timestamp=0.0,
        onset=1.0,
    )


# -- option framework ---------------------------------------------------------
def test_option_default_and_set_with_clamp() -> None:
    w = Waveform()
    assert w.option("thickness") == 2  # Normal default
    w.set_option_index("thickness", 0)
    assert w.option("thickness") == 1
    w.set_option_index("thickness", 99)  # clamped to the last choice
    assert w.option("thickness") == 4
    assert w.option_index("thickness") == 2


# -- rainbow_plus -------------------------------------------------------------
def test_rainbow_plus_uses_phase_offset() -> None:
    assert themed_color("rainbow_plus", 0.2, PALETTE, 0.0) == rainbow_color(0.2)
    assert themed_color("rainbow_plus", 0.2, PALETTE, 0.3) == rainbow_color(0.5)
    # Different phases generally yield different colors.
    assert themed_color("rainbow_plus", 0.2, PALETTE, 0.0) != themed_color(
        "rainbow_plus", 0.2, PALETTE, 0.25
    )


# -- snowfall fall / wind / density ------------------------------------------
def test_snowfall_fall_speed_moves_further() -> None:
    surface = pygame.Surface((400, 400))
    slow = Snowfall(seed=7)
    slow.on_enter()
    slow._y[:] = 0.0
    slow.set_option_index("fall_speed", 0)  # Slow
    fast = Snowfall(seed=7)
    fast.on_enter()
    fast._y[:] = 0.0
    fast.set_option_index("fall_speed", 2)  # Fast
    for _ in range(10):
        slow.draw(surface, None, 0.02)
        fast.draw(surface, None, 0.02)
    assert fast._y.mean() > slow._y.mean()


def test_snowfall_wind_speed_controls_horizontal_drift() -> None:
    surface = pygame.Surface((400, 400))
    frame = _loud_frame()
    calm = Snowfall(seed=9)
    calm.on_enter()
    calm.set_option_index("wind_speed", 0)  # Calm = no horizontal drift
    x0 = calm._x.copy()
    windy = Snowfall(seed=9)
    windy.on_enter()
    windy.set_option_index("wind_speed", 2)  # Windy
    x0_windy = windy._x.copy()
    for _ in range(8):
        calm.draw(surface, frame, 0.02)
        windy.draw(surface, frame, 0.02)
    assert np.allclose(calm._x, x0)
    assert not np.allclose(windy._x, x0_windy)


def test_snowfall_density_rebuilds_pool() -> None:
    surface = pygame.Surface((400, 400))
    snow = Snowfall(seed=3)
    snow.on_enter()
    snow.set_option_index("density", 2)  # High
    snow.draw(surface, None, 0.01)
    assert snow._x.size == int(snow.option("density"))


# -- control bar --------------------------------------------------------------
def _noop_actions() -> tuple[ControlActions, dict]:
    calls: dict = {}
    actions = ControlActions(
        toggle_capture=lambda: None,
        prev_mode=lambda: None,
        next_mode=lambda: None,
        select_mode=lambda key: None,
        sensitivity_down=lambda: None,
        sensitivity_up=lambda: None,
        smoothing_down=lambda: None,
        smoothing_up=lambda: None,
        size_down=lambda: None,
        size_up=lambda: None,
        speed_down=lambda: None,
        speed_up=lambda: None,
        cycle_color_scheme=lambda: None,
        select_color=lambda key: calls.setdefault("color", key),
        option_change=lambda key, idx: calls.setdefault("option", (key, idx)),
        toggle_reduce_motion=lambda: None,
        open_logo_panel=lambda: None,
        open_about=lambda: None,
        toggle_fullscreen=lambda: None,
        quit=lambda: None,
    )
    return actions, calls


def test_control_bar_shows_values_and_routes_options() -> None:
    actions, calls = _noop_actions()
    bar = ControlBar(actions, [("waveform", "Waveform")])
    bar.relayout(pygame.Rect(0, 0, 1280, 88))
    bar.set_state(
        capturing=True,
        mode_key="waveform",
        reduce_motion=False,
        color_scheme="rainbow_plus",
        sensitivity=1.5,
        smoothing=0.5,
        size_scale=1.0,
        speed_scale=1.25,
    )
    assert bar._sens_chip.text == "1.50"
    assert bar._speed_chip.text == "1.25"

    bar.set_mode_options([OptionSpec("thickness", "Line", ("Thin", "Normal", "Thick"), 1)])
    assert len(bar._option_dropdowns) == 1
    bar._option_dropdowns[0]._on_select("2")
    assert calls["option"] == ("thickness", 2)
