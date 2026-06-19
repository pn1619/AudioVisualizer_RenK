"""Phase 00.0B.09: pulse-shoot transparency, finer meter sparks, snowfall React,
modern laser shapes, Audio Sun particles, and editable value chips."""

from __future__ import annotations

import numpy as np
import pygame
import pytest

from audio_visualizer.app import _parse_float
from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.ui.chip import Chip
from audio_visualizer.visuals import registry
from audio_visualizer.visuals.base import Theme
from audio_visualizer.visuals.laser import Laser
from audio_visualizer.visuals.snowfall import Snowfall


@pytest.fixture(scope="module", autouse=True)
def _pygame_ready():
    pygame.init()
    registry.discover()
    yield
    pygame.quit()


def _loud_frame() -> AnalysisFrame:
    wave = (0.6 * np.sin(np.linspace(0, 30, 2048))).astype(np.float32)
    return AnalysisFrame(
        waveform_mono=wave,
        band_energies=np.full(48, 0.8, dtype=np.float32),
        rms=0.6,
        peak=0.9,
        sample_rate=48000,
        timestamp=0.0,
        onset=1.0,
    )


# -- per-mode option sweeps (none may raise on audio or idle) -----------------
@pytest.mark.parametrize("key", ("pulse_rings", "meters", "snowfall", "laser", "radial_spectrum"))
def test_updated_mode_option_sweep_renders(key: str) -> None:
    frame = _loud_frame()
    surface = pygame.Surface((480, 360))
    for opt in registry.create(key).OPTIONS:
        for index in range(len(opt.choices)):
            v = registry.create(key)
            v.theme = Theme(color_scheme="rainbow_plus")
            v.on_enter()
            v.set_option_index(opt.key, index)
            for _ in range(4):
                v.draw(surface, frame, 0.02)
            v.draw(surface, None, 0.02)  # idle path must not raise


# -- pulse rings shoot toggle -------------------------------------------------
def test_pulse_rings_shoot_toggle_gates_pulses() -> None:
    surface = pygame.Surface((400, 400))
    frame = _loud_frame()
    on = registry.create("pulse_rings")
    on.on_enter()
    on.set_option_index("beat", 1)  # Off
    on.set_option_index("shoot", 0)  # On
    for _ in range(3):
        on.draw(surface, frame, 0.02)
    assert len(on._pulses) > 0  # shoot alone still spawns pulses

    off = registry.create("pulse_rings")
    off.on_enter()
    off.set_option_index("beat", 1)  # Off
    off.set_option_index("shoot", 1)  # Off
    for _ in range(3):
        off.draw(surface, frame, 0.02)
    assert len(off._pulses) == 0  # nothing consumes pulses -> none spawned


# -- snowfall React + extra wind options --------------------------------------
def test_snowfall_has_extra_wind_choices_and_react() -> None:
    snow = Snowfall()
    wind = next(o for o in snow.OPTIONS if o.key == "wind_speed")
    assert len(wind.choices) >= 5  # Calm/Drift/Light/Breezy/Windy
    assert any(o.key == "react" for o in snow.OPTIONS)


def test_snowfall_react_adds_drift_versus_off() -> None:
    surface = pygame.Surface((400, 400))
    frame = _loud_frame()
    base = Snowfall(seed=5)
    base.on_enter()
    base.set_option_index("wind_speed", 3)  # Breezy
    base.set_option_index("react", 0)  # Off
    react = Snowfall(seed=5)
    react.on_enter()
    react.set_option_index("wind_speed", 3)  # Breezy
    react.set_option_index("react", 2)  # Strong
    for _ in range(20):
        base.draw(surface, frame, 0.02)
        react.draw(surface, frame, 0.02)
    # React steers the field differently than the plain wind sway.
    assert not np.allclose(base._x, react._x)


# -- laser modern shapes ------------------------------------------------------
def test_laser_shapes_are_modern_set() -> None:
    laser = Laser()
    shape = next(o for o in laser.OPTIONS if o.key == "shape")
    labels = [c.label for c in shape.choices]
    assert labels == ["Lissajous", "Rose", "Spiro", "Web", "Bloom"]


# -- editable value chip ------------------------------------------------------
def test_chip_editing_parses_and_ignores_garbage() -> None:
    got: list[str] = []
    chip = Chip(on_submit=got.append)
    chip.set_rect(pygame.Rect(0, 0, 100, 30))
    chip.begin_edit()
    for ch in "1.25":
        chip.handle_event(pygame.event.Event(pygame.TEXTINPUT, text=ch))
    chip.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert got == ["1.25"]
    assert not chip.editing


def test_chip_escape_cancels_without_submitting() -> None:
    got: list[str] = []
    chip = Chip(on_submit=got.append)
    chip.set_rect(pygame.Rect(0, 0, 100, 30))
    chip.begin_edit()
    chip.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="9"))
    chip.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert got == []
    assert not chip.editing


def test_chip_rejects_letters_while_editing() -> None:
    chip = Chip(on_submit=lambda _s: None)
    chip.set_rect(pygame.Rect(0, 0, 100, 30))
    chip.begin_edit()
    chip.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="a"))
    chip.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="2"))
    assert chip._buffer == "2"


def test_non_editable_chip_ignores_clicks() -> None:
    chip = Chip("Sens 1.50")
    chip.set_rect(pygame.Rect(0, 0, 100, 30))
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(10, 10))
    assert chip.handle_event(event) is False
    assert not chip.editing


# -- numeric parsing helper ---------------------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [("1.25", 1.25), ("  3 ", 3.0), ("-2", -2.0), ("", None), ("abc", None), ("nan", None)],
)
def test_parse_float(text: str, expected: float | None) -> None:
    assert _parse_float(text) == expected
