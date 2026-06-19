"""Phase 0B-c build 1: auto-cycle ("shuffle") scheduler, cross-fade, persistence."""

from __future__ import annotations

import pygame
import pytest

from audio_visualizer.app import App
from audio_visualizer.config import (
    RANDOM_INTERVAL_DEFAULT,
    RANDOM_INTERVAL_MAX,
    RANDOM_INTERVAL_MIN,
    TRANSITION_DURATION,
)
from audio_visualizer.settings import Settings
from audio_visualizer.settings import load as load_settings
from audio_visualizer.settings import save as save_settings
from audio_visualizer.ui.shuffle_panel import ShuffleActions, ShufflePanel
from audio_visualizer.visuals._transition import ModeTransition


# -- settings persistence -----------------------------------------------------
def test_random_pool_and_interval_roundtrip(tmp_path) -> None:
    path = tmp_path / "settings.json"
    save_settings(Settings(random_pool=["mode:spectrum", "look:x"], random_interval=42.0), path)
    loaded = load_settings(path)
    assert loaded.random_pool == ["mode:spectrum", "look:x"]
    assert loaded.random_interval == 42.0


def test_random_pool_drops_non_strings_and_clamps_interval(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        '{"schema_version": 10, "random_pool": ["mode:a", 5, null], "random_interval": "x"}',
        encoding="utf-8",
    )
    loaded = load_settings(path)
    assert loaded.random_pool == ["mode:a"]  # junk entries dropped
    assert loaded.random_interval == RANDOM_INTERVAL_DEFAULT  # invalid -> default


def test_interval_below_range_clamps(tmp_path) -> None:
    path = tmp_path / "settings.json"
    save_settings(Settings(random_interval=0.5), path)
    assert load_settings(path).random_interval == RANDOM_INTERVAL_MIN


def test_v9_file_migrates_to_v10(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"schema_version": 9, "mode": "spectrum"}', encoding="utf-8")
    migrated = load_settings(path)
    assert migrated.random_pool == []
    assert migrated.random_interval == RANDOM_INTERVAL_DEFAULT
    assert migrated.schema_version >= 10


# -- transition state ---------------------------------------------------------
def test_transition_alpha_progresses() -> None:
    trans = ModeTransition(outgoing=None, incoming=None, target_index=1, duration=1.0)  # type: ignore[arg-type]
    assert trans.alpha() == 0
    assert trans.advance(0.5) is False
    assert trans.alpha() == pytest.approx(127, abs=2)
    assert trans.advance(0.6) is True  # past duration
    assert trans.alpha() == 255


# -- app wiring ---------------------------------------------------------------
@pytest.fixture
def app() -> App:
    instance = App(load_settings=False)
    instance._auto = False
    instance._auto_pool = set()
    return instance


def test_toggle_auto_fills_empty_pool(app: App) -> None:
    assert app._auto_pool == set()
    app._toggle_auto()
    assert app._auto is True
    assert app._auto_pool == set(app._mode_keys)


def test_toggle_pool_mode_and_valid_indices(app: App) -> None:
    keys = app._mode_keys
    app._toggle_pool_mode(keys[0])
    app._toggle_pool_mode(keys[1])
    assert set(app._valid_pool_indices()) == {0, 1}
    app._toggle_pool_mode(keys[0])  # toggling again removes it
    assert app._valid_pool_indices() == [1]


def test_set_all_selects_and_clears(app: App) -> None:
    app._set_pool_all(True)
    assert app._auto_pool == set(app._mode_keys)
    app._set_pool_all(False)
    assert app._auto_pool == set()


def test_interval_clamps_to_range(app: App) -> None:
    app._auto_interval = RANDOM_INTERVAL_MIN
    app._adjust_interval(-100.0)
    assert app._auto_interval == RANDOM_INTERVAL_MIN
    app._adjust_interval(10_000.0)
    assert app._auto_interval == RANDOM_INTERVAL_MAX


def test_auto_advance_cut_switches_without_repeat(app: App) -> None:
    app._reduce_motion = True  # reduce-motion uses a hard cut (no transition)
    keys = app._mode_keys
    app._set_pool_all(False)
    app._toggle_pool_mode(keys[0])
    app._toggle_pool_mode(keys[1])
    app._set_mode_index(0)
    app._auto_advance()
    assert app._mode_index == 1  # only other pooled mode
    assert app._transition is None  # cut, not a fade


def test_transition_lifecycle_commits_one_mode(app: App) -> None:
    keys = app._mode_keys
    app._reduce_motion = False
    app._set_pool_all(False)
    app._toggle_pool_mode(keys[0])
    app._toggle_pool_mode(keys[1])
    app._set_mode_index(0)
    app._auto = True
    app._auto_elapsed = app._auto_interval  # due now
    app._update_auto(0.0)
    assert app._transition is not None  # a fade started
    app._update_auto(TRANSITION_DURATION + 0.05)  # run it past the end
    assert app._transition is None
    assert app._mode_index == 1  # incoming committed; exactly one active visual


def test_manual_switch_cancels_active_transition(app: App) -> None:
    keys = app._mode_keys
    app._reduce_motion = False
    app._set_pool_all(False)
    app._toggle_pool_mode(keys[1])
    app._set_mode_index(0)
    app._auto = True
    app._auto_elapsed = app._auto_interval
    app._update_auto(0.0)
    assert app._transition is not None
    app._set_mode_index(len(keys) - 1)  # user picks a mode mid-fade
    assert app._transition is None
    assert app._mode_index == len(keys) - 1


def test_draw_transition_renders_without_error(app: App) -> None:
    keys = app._mode_keys
    app._reduce_motion = False
    app._set_pool_all(False)
    app._toggle_pool_mode(keys[1])
    app._set_mode_index(0)
    app._auto = True
    app._auto_elapsed = app._auto_interval
    app._update_auto(0.0)
    surface = pygame.Surface(app._layout.canvas.size)
    app._draw_transition(surface, 0.016)  # must not raise


def test_pool_persists_as_tagged_modes(app: App) -> None:
    keys = app._mode_keys
    app._set_pool_all(False)
    app._toggle_pool_mode(keys[0])
    app._auto_interval = 35.0
    settings = app._current_settings()
    assert settings.random_pool == [f"mode:{keys[0]}"]
    assert settings.random_interval == 35.0


# -- panel --------------------------------------------------------------------
def test_shuffle_panel_routes_clicks() -> None:
    events: dict[str, object] = {"toggled": [], "auto": 0, "up": 0, "all": []}
    actions = ShuffleActions(
        toggle_auto=lambda: events.__setitem__("auto", int(events["auto"]) + 1),  # type: ignore[arg-type]
        interval_down=lambda: None,
        interval_up=lambda: events.__setitem__("up", int(events["up"]) + 1),  # type: ignore[arg-type]
        toggle_mode=lambda key: events["toggled"].append(key),  # type: ignore[union-attr]
        set_all=lambda on: events["all"].append(on),  # type: ignore[union-attr]
    )
    panel = ShufflePanel(actions)
    panel.set_state([("spectrum", "Spectrum", False)], "Every 20s", False)
    panel.toggle()
    canvas = pygame.Rect(0, 0, 800, 600)
    lay = panel._layout(canvas)
    panel._handle_click(lay.rows[0].rect.center, lay)
    panel._handle_click(lay.auto.center, lay)
    panel._handle_click(lay.interval_up.center, lay)
    panel._handle_click(lay.all_btn.center, lay)
    panel._handle_click(lay.none_btn.center, lay)
    assert events["toggled"] == ["spectrum"]
    assert events["auto"] == 1
    assert events["up"] == 1
    assert events["all"] == [True, False]
