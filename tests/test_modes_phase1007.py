"""Phase 10.07: merged modes, settings remap, presets, and a merged-mode sweep."""

from __future__ import annotations

import json

import numpy as np
import pygame
import pytest

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import (
    MERGED_MODE_KEYS,
    SETTINGS_SCHEMA_VERSION,
    SPARK_MAX,
    SPARK_MAX_REDUCED,
)
from audio_visualizer.settings import load as load_settings
from audio_visualizer.visuals import registry
from audio_visualizer.visuals.base import Theme

_MERGED_KEYS = ("waveform", "waveform_circle", "lightshow", "laser", "particles")


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
        band_energies=np.full(48, 0.7, dtype=np.float32),
        rms=0.5,
        peak=0.8,
        sample_rate=48000,
        timestamp=0.0,
        onset=1.0,
    )


def test_merged_modes_registered_and_old_keys_gone() -> None:
    keys = set(registry.keys())
    assert set(_MERGED_KEYS) <= keys
    for old_key in MERGED_MODE_KEYS:
        assert old_key not in keys


def test_settings_remaps_merged_mode_keys(tmp_path) -> None:
    for old_key, new_key in MERGED_MODE_KEYS.items():
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"schema_version": 6, "mode": old_key}), encoding="utf-8")
        loaded = load_settings(path)
        assert loaded.mode == new_key
        assert loaded.schema_version == SETTINGS_SCHEMA_VERSION


def test_surviving_mode_key_is_preserved(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"schema_version": 6, "mode": "spectrum"}), encoding="utf-8")
    assert load_settings(path).mode == "spectrum"


@pytest.mark.parametrize("key", _MERGED_KEYS)
def test_preset_snaps_sibling_options(key: str) -> None:
    v = registry.create(key)
    v.on_enter()
    assert "preset" in {opt.key for opt in type(v).OPTIONS}
    for preset_index, mapping in type(v).PRESETS.items():
        v.set_option_index("preset", preset_index)
        for opt_key, choice in mapping.items():
            assert v.option_index(opt_key) == choice


@pytest.mark.parametrize("key", ("lightshow", "laser"))
def test_reduce_motion_toggle_recaps_sparkfield(key: str) -> None:
    surface = pygame.Surface((400, 400))
    frame = _loud_frame()
    v = registry.create(key, reduce_motion=False)
    v.on_enter()
    v.set_option_index("particles", 2)  # ensure the field is in use
    v.draw(surface, frame, 0.02)
    assert v._sparks.cap == SPARK_MAX
    # Toggling reduce-motion mid-session must re-cap the live field on next draw.
    v.reduce_motion = True
    v.draw(surface, frame, 0.02)
    assert v._sparks.cap == SPARK_MAX_REDUCED


def test_particles_emitter_switch_clears_other_pool() -> None:
    surface = pygame.Surface((400, 400))
    frame = _loud_frame()
    v = registry.create("particles")
    v.on_enter()  # default emitter = Field
    for _ in range(5):
        v.draw(surface, frame, 0.02)
    assert len(v._particles) > 0
    v.set_option_index("emitter", 1)  # Spiral -> abandons the field pool
    assert len(v._particles) == 0


@pytest.mark.parametrize("key", _MERGED_KEYS)
def test_merged_mode_option_sweep_renders(key: str) -> None:
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
