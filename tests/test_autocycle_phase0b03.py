"""Phase 0B-c: auto-cycle ("shuffle") — tagged pool (modes + looks), Next, cross-fade."""

from __future__ import annotations

import pygame
import pytest

from audio_visualizer.app import App
from audio_visualizer.config import (
    RANDOM_FADE_MAX,
    RANDOM_FADE_MIN,
    RANDOM_FADE_STEP,
    RANDOM_INTERVAL_DEFAULT,
    RANDOM_INTERVAL_MAX,
    RANDOM_INTERVAL_MIN,
    TRANSITION_DURATION,
)
from audio_visualizer.looks import LooksStore
from audio_visualizer.settings import Settings
from audio_visualizer.settings import load as load_settings
from audio_visualizer.settings import save as save_settings
from audio_visualizer.ui.shuffle_panel import ShuffleActions, ShufflePanel
from audio_visualizer.visuals import registry
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


def test_random_options_roundtrip(tmp_path) -> None:
    path = tmp_path / "settings.json"
    save_settings(Settings(random_options=True), path)
    assert load_settings(path).random_options is True
    assert load_settings(path).schema_version >= 11


def test_random_fade_roundtrip_and_clamp(tmp_path) -> None:
    path = tmp_path / "settings.json"
    save_settings(Settings(random_fade=1.5), path)
    loaded = load_settings(path)
    assert loaded.random_fade == 1.5
    assert loaded.schema_version >= 12
    path.write_text('{"schema_version": 12, "random_fade": 99}', encoding="utf-8")
    assert load_settings(path).random_fade == RANDOM_FADE_MAX  # clamped to range


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
def test_transition_overlay_alpha_falls_to_zero() -> None:
    trans = ModeTransition(snapshot=pygame.Surface((4, 4)), duration=1.0)
    assert trans.overlay_alpha() == 255  # frozen scene fully opaque at the start
    assert trans.advance(0.5) is False
    assert trans.overlay_alpha() == pytest.approx(128, abs=2)
    assert trans.advance(0.6) is True  # past duration
    assert trans.overlay_alpha() == 0  # fully dissolved


# -- app wiring ---------------------------------------------------------------
@pytest.fixture
def app() -> App:
    instance = App(load_settings=False)
    instance._looks_store = LooksStore()  # isolate from any real looks.json
    instance._auto = False
    instance._auto_pool = set()
    instance._auto_current = ""
    return instance


def test_toggle_auto_fills_empty_pool_with_all_items(app: App) -> None:
    assert app._auto_pool == set()
    app._toggle_auto()
    assert app._auto is True
    assert app._auto_pool == app._all_pool_tags()


def test_toggle_item_and_valid_pool(app: App) -> None:
    keys = app._mode_keys
    app._toggle_pool_item(f"mode:{keys[0]}")
    app._toggle_pool_item(f"mode:{keys[1]}")
    assert set(app._valid_pool()) == {f"mode:{keys[0]}", f"mode:{keys[1]}"}
    app._toggle_pool_item(f"mode:{keys[0]}")  # toggling again removes it
    assert app._valid_pool() == [f"mode:{keys[1]}"]


def test_set_all_selects_and_clears(app: App) -> None:
    app._set_pool_all(True)
    assert app._auto_pool == app._all_pool_tags()
    app._set_pool_all(False)
    assert app._auto_pool == set()


def test_interval_clamps_to_range(app: App) -> None:
    app._auto_interval = RANDOM_INTERVAL_MIN
    app._adjust_interval(-100.0)
    assert app._auto_interval == RANDOM_INTERVAL_MIN
    app._adjust_interval(10_000.0)
    assert app._auto_interval == RANDOM_INTERVAL_MAX


def test_pick_next_never_repeats_current(app: App) -> None:
    keys = app._mode_keys
    app._set_pool_all(False)
    app._toggle_pool_item(f"mode:{keys[0]}")
    app._toggle_pool_item(f"mode:{keys[1]}")
    app._auto_current = f"mode:{keys[0]}"
    assert app._pick_next() == f"mode:{keys[1]}"
    app._auto_current = f"mode:{keys[1]}"
    assert app._pick_next() == f"mode:{keys[0]}"


def test_pick_next_single_item_equal_to_current_is_none(app: App) -> None:
    key = app._mode_keys[0]
    app._set_pool_all(False)
    app._toggle_pool_item(f"mode:{key}")
    app._auto_current = f"mode:{key}"
    assert app._pick_next() is None  # nothing new to switch to


def test_auto_advance_cut_switches_without_repeat(app: App) -> None:
    app._reduce_motion = True  # reduce-motion uses a hard cut (no fade overlay)
    keys = app._mode_keys
    app._set_pool_all(False)
    app._toggle_pool_item(f"mode:{keys[1]}")
    app._set_mode_index(0)
    app._auto_advance()
    assert app._mode_index == 1
    assert app._transition is None
    assert app._auto_current == f"mode:{keys[1]}"


def test_look_in_pool_applies_on_advance(app: App) -> None:
    keys = app._mode_keys
    look = app._capture_look("Pinned")
    look.base_mode_key = keys[1]
    look.sensitivity = 3.0
    created = app._looks_store.add(look)
    assert created is not None
    tag = f"look:{created.id}"
    app._set_pool_all(False)
    app._toggle_pool_item(tag)
    assert app._valid_pool() == [tag]
    app._reduce_motion = True
    app._set_mode_index(0)
    app._auto_advance()
    assert app._mode_keys[app._mode_index] == keys[1]
    assert app._sensitivity == pytest.approx(3.0)
    assert app._auto_current == tag


def test_randomize_globals_stays_in_range(app: App) -> None:
    from audio_visualizer.config import (
        SENSITIVITY_MAX,
        SENSITIVITY_MIN,
        SIZE_SCALE_MAX,
        SIZE_SCALE_MIN,
        SPEED_SCALE_MAX,
        SPEED_SCALE_MIN,
    )

    for _ in range(50):
        app._randomize_globals()
        assert SENSITIVITY_MIN <= app._sensitivity <= SENSITIVITY_MAX
        assert 0.0 <= app._smoothing <= 0.9
        assert SIZE_SCALE_MIN <= app._theme.size_scale <= SIZE_SCALE_MAX
        assert SPEED_SCALE_MIN <= app._theme.speed_scale <= SPEED_SCALE_MAX


def test_randomize_globals_actually_varies(app: App) -> None:
    seen = set()
    for _ in range(40):
        app._randomize_globals()
        seen.add((app._sensitivity, app._theme.size_scale, app._theme.speed_scale))
    assert len(seen) > 10  # continuous ranges -> values rarely repeat


def test_randomize_current_mode_keeps_same_mode(app: App) -> None:
    before = app._mode_index
    app._randomize_current_mode()
    assert app._mode_index == before  # the manual Rnd button never switches modes


def test_randomize_mode_options_keeps_indices_valid(app: App) -> None:
    # Pick the mode exposing the most options so randomization has something to do.
    keys = app._mode_keys
    target = max(keys, key=lambda k: len(type(registry.create(k)).OPTIONS))
    app._set_mode_index(keys.index(target))
    app._randomize_mode_options()
    for opt in type(app._visual).OPTIONS:
        idx = app._visual.option_index(opt.key)
        assert 0 <= idx < len(opt.choices)
        if opt.key == "preset":
            assert idx == 0  # preset forced to Custom so siblings stay free


def test_random_options_off_keeps_mode_defaults(app: App) -> None:
    keys = app._mode_keys
    app._auto_random_options = False
    app._reduce_motion = True
    app._set_pool_all(False)
    app._toggle_pool_item(f"mode:{keys[1]}")
    app._set_mode_index(0)
    app._auto_advance()
    defaults = {opt.key: opt.default_index for opt in type(app._visual).OPTIONS}
    actual = {opt.key: app._visual.option_index(opt.key) for opt in type(app._visual).OPTIONS}
    assert actual == defaults  # no randomization when the toggle is off


def test_transition_lifecycle_applies_then_clears(app: App) -> None:
    keys = app._mode_keys
    app._reduce_motion = False
    app._set_pool_all(False)
    app._toggle_pool_item(f"mode:{keys[1]}")
    app._set_mode_index(0)
    app._auto = True
    app._auto_elapsed = app._auto_interval  # due now
    app._update_auto(0.0)
    assert app._transition is not None  # a fade overlay is in flight
    assert app._mode_index == 1  # the new item is applied live immediately
    app._update_auto(TRANSITION_DURATION + 0.05)  # run it past the end
    assert app._transition is None
    assert app._mode_index == 1  # exactly one active visual


def test_mode_to_mode_uses_live_crossfade(app: App) -> None:
    keys = app._mode_keys
    app._reduce_motion = False
    app._set_pool_all(False)
    app._toggle_pool_item(f"mode:{keys[1]}")
    app._set_mode_index(0)
    old_visual = app._visual
    app._auto_current = f"mode:{keys[0]}"
    app._auto_advance()
    assert app._transition is not None
    assert app._transition.is_live  # both visuals animate during the fade
    assert app._transition.prev_visual is old_visual
    assert app._transition.snapshot is None


def test_switch_onto_look_uses_frozen_dissolve(app: App) -> None:
    keys = app._mode_keys
    look = app._capture_look("Pinned")
    look.base_mode_key = keys[1]
    created = app._looks_store.add(look)
    assert created is not None
    tag = f"look:{created.id}"
    app._reduce_motion = False
    app._set_pool_all(False)
    app._toggle_pool_item(tag)
    app._set_mode_index(0)
    app._auto_current = f"mode:{keys[0]}"
    app._auto_advance()
    assert app._transition is not None
    assert not app._transition.is_live  # looks change globals -> frozen snapshot
    assert app._transition.snapshot is not None


def test_adjust_fade_clamps_and_snaps(app: App) -> None:
    app._auto_fade = 0.6
    app._adjust_fade(RANDOM_FADE_STEP)
    assert app._auto_fade == pytest.approx(0.7)
    app._adjust_fade(-100.0)
    assert app._auto_fade == RANDOM_FADE_MIN
    app._adjust_fade(100.0)
    assert app._auto_fade == RANDOM_FADE_MAX


def test_zero_fade_hard_cuts(app: App) -> None:
    keys = app._mode_keys
    app._reduce_motion = False
    app._auto_fade = 0.0
    app._set_pool_all(False)
    app._toggle_pool_item(f"mode:{keys[1]}")
    app._set_mode_index(0)
    app._auto_advance()
    assert app._transition is None  # 0s fade is an instant cut


def test_status_chip_label_mode_vs_look(app: App) -> None:
    keys = app._mode_keys
    app._auto_current = f"mode:{keys[0]}"
    assert app._current_item_label().startswith("Mode: ")
    look = app._capture_look("Neon")
    created = app._looks_store.add(look)
    assert created is not None
    app._auto_current = f"look:{created.id}"
    assert app._current_item_label() == "Look: Neon"


def test_manual_switch_cancels_active_fade(app: App) -> None:
    keys = app._mode_keys
    app._reduce_motion = False
    app._set_pool_all(False)
    app._toggle_pool_item(f"mode:{keys[1]}")
    app._set_mode_index(0)
    app._auto = True
    app._auto_elapsed = app._auto_interval
    app._update_auto(0.0)
    assert app._transition is not None
    app._set_mode_index(len(keys) - 1)  # user picks a mode mid-fade
    assert app._transition is None
    assert app._mode_index == len(keys) - 1


def test_shuffle_next_advances_when_auto_off(app: App) -> None:
    keys = app._mode_keys
    app._reduce_motion = True
    app._auto = False
    app._set_pool_all(False)
    app._toggle_pool_item(f"mode:{keys[1]}")
    app._set_mode_index(0)
    app._shuffle_next()
    assert app._mode_index == 1


def test_shuffle_next_fills_empty_pool(app: App) -> None:
    assert app._auto_pool == set()
    app._reduce_motion = True
    app._shuffle_next()
    assert app._auto_pool == app._all_pool_tags()


def test_draw_transition_renders_without_error(app: App) -> None:
    keys = app._mode_keys
    app._reduce_motion = False
    app._set_pool_all(False)
    app._toggle_pool_item(f"mode:{keys[1]}")
    app._set_mode_index(0)
    app._auto = True
    app._auto_elapsed = app._auto_interval
    app._update_auto(0.0)
    surface = pygame.Surface(app._layout.canvas.size)
    bg_copy = surface.copy()
    app._draw_transition(surface, 0.016, bg_copy)  # must not raise


def test_auto_status_overlay_runs(app: App) -> None:
    app._set_pool_all(True)
    app._auto = True
    app._draw_auto_status(app._screen, app._layout.canvas)  # countdown shown, no error
    app._auto = False
    app._draw_auto_status(app._screen, app._layout.canvas)  # no-op when off, no error


def test_stale_look_tag_excluded_and_not_persisted(app: App) -> None:
    key = app._mode_keys[0]
    app._auto_pool = {"look:ghost", f"mode:{key}"}
    assert app._valid_pool() == [f"mode:{key}"]  # ghost look dropped
    assert app._current_settings().random_pool == [f"mode:{key}"]


# -- panel --------------------------------------------------------------------
def test_shuffle_panel_routes_clicks() -> None:
    events: dict[str, object] = {
        "toggled": [],
        "auto": 0,
        "next": 0,
        "up": 0,
        "all": [],
        "rand": 0,
        "fade": 0,
    }
    actions = ShuffleActions(
        toggle_auto=lambda: events.__setitem__("auto", int(events["auto"]) + 1),  # type: ignore[arg-type]
        shuffle_next=lambda: events.__setitem__("next", int(events["next"]) + 1),  # type: ignore[arg-type]
        interval_down=lambda: None,
        interval_up=lambda: events.__setitem__("up", int(events["up"]) + 1),  # type: ignore[arg-type]
        fade_down=lambda: None,
        fade_up=lambda: events.__setitem__("fade", int(events["fade"]) + 1),  # type: ignore[arg-type]
        toggle_item=lambda key: events["toggled"].append(key),  # type: ignore[union-attr]
        set_all=lambda on: events["all"].append(on),  # type: ignore[union-attr]
        toggle_random_options=lambda: events.__setitem__("rand", int(events["rand"]) + 1),  # type: ignore[arg-type]
    )
    panel = ShufflePanel(actions)
    panel.set_state(
        [("mode:spectrum", "Spectrum", False), ("look:abc", "\u2605 Neon", True)],
        "Every 20s",
        False,
        False,
        "Fade: 0.6s",
    )
    panel.toggle()
    canvas = pygame.Rect(0, 0, 800, 600)
    lay = panel._layout(canvas)
    panel._handle_click(lay.rows[0].rect.center, lay)
    panel._handle_click(lay.next_btn.center, lay)
    panel._handle_click(lay.auto.center, lay)
    panel._handle_click(lay.interval_up.center, lay)
    panel._handle_click(lay.fade_up.center, lay)
    panel._handle_click(lay.random_opts.center, lay)
    panel._handle_click(lay.all_btn.center, lay)
    panel._handle_click(lay.none_btn.center, lay)
    assert events["toggled"] == ["mode:spectrum"]
    assert events["next"] == 1
    assert events["auto"] == 1
    assert events["up"] == 1
    assert events["fade"] == 1
    assert events["rand"] == 1
    assert events["all"] == [True, False]
