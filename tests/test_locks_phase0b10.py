"""Phase 00.0B.10: randomize locks, Hotkeys modal, live looks-panel refresh."""

from __future__ import annotations

import pygame
import pytest

from audio_visualizer.app import App
from audio_visualizer.looks import LooksStore
from audio_visualizer.ui.controls import ControlActions, ControlBar, OptionSpec
from audio_visualizer.ui.hotkeys import HotkeysDialog
from audio_visualizer.ui.looks_panel import LooksActions, LooksPanel


@pytest.fixture(scope="module", autouse=True)
def _pygame_ready():
    pygame.init()
    yield
    pygame.quit()


@pytest.fixture
def app() -> App:
    instance = App(load_settings=False)
    instance._looks_store = LooksStore()
    return instance


# -- app: global locks --------------------------------------------------------
def test_locked_global_is_not_randomized(app: App) -> None:
    app._sensitivity = 1.23
    app._toggle_global_lock("sensitivity")
    assert "sensitivity" in app._locked_globals
    for _ in range(40):
        app._randomize_globals()
    assert app._sensitivity == 1.23  # held by the lock


def test_unlocked_global_changes_eventually(app: App) -> None:
    seen = set()
    for _ in range(60):
        app._randomize_globals()
        seen.add(app._theme.size_scale)
    assert len(seen) > 1  # an unlocked global varies across rolls


# -- app: per-mode option locks ----------------------------------------------
def _first_lockable_key(app: App) -> str:
    for opt in type(app._visual).OPTIONS:
        if opt.key != "preset" and len(opt.choices) > 1:
            return opt.key
    raise AssertionError("expected at least one lockable option on the default mode")


def test_locked_option_is_not_randomized(app: App) -> None:
    key = _first_lockable_key(app)
    app._visual.set_option_index(key, 0)
    app._toggle_option_lock(key)
    for _ in range(40):
        app._randomize_mode_options()
    assert app._visual.option_index(key) == 0


def test_mode_switch_clears_option_locks(app: App) -> None:
    key = _first_lockable_key(app)
    app._toggle_option_lock(key)
    assert app._locked_options
    other = (app._mode_index + 1) % len(app._mode_keys)
    app._set_mode_index(other)
    assert app._locked_options == set()


def test_mode_switch_keeps_global_locks(app: App) -> None:
    app._toggle_global_lock("speed")
    other = (app._mode_index + 1) % len(app._mode_keys)
    app._set_mode_index(other)
    assert "speed" in app._locked_globals  # globals persist across mode switches


# -- control bar: lock toggles ------------------------------------------------
def _actions() -> tuple[ControlActions, dict]:
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
        select_color=lambda key: None,
        option_change=lambda key, idx: None,
        toggle_reduce_motion=lambda: None,
        open_logo_panel=lambda: None,
        open_about=lambda: None,
        toggle_fullscreen=lambda: None,
        quit=lambda: None,
        toggle_global_lock=lambda key: calls.setdefault("global", key),
        toggle_option_lock=lambda key: calls.setdefault("option", key),
    )
    return actions, calls


def _click(rect: pygame.Rect) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center)


def test_global_lock_click_invokes_action() -> None:
    actions, calls = _actions()
    bar = ControlBar(actions, [("waveform", "Waveform")])
    bar.relayout(pygame.Rect(0, 0, 1600, 120))
    assert bar.handle_event(_click(bar._size_lock.rect)) is True
    assert calls["global"] == "size"


def test_global_lock_reflects_state() -> None:
    actions, _ = _actions()
    bar = ControlBar(actions, [("waveform", "Waveform")])
    bar.relayout(pygame.Rect(0, 0, 1600, 120))
    bar.set_state(
        capturing=True,
        mode_key="waveform",
        reduce_motion=False,
        color_scheme="rainbow_plus",
        sensitivity=1.0,
        smoothing=0.5,
        size_scale=1.0,
        speed_scale=1.0,
        locked_globals={"smoothing"},
    )
    assert bar._smooth_lock.locked is True
    assert bar._sens_lock.locked is False


def test_option_lock_click_invokes_action() -> None:
    actions, calls = _actions()
    bar = ControlBar(actions, [("waveform", "Waveform")])
    bar.relayout(pygame.Rect(0, 0, 1600, 120))
    bar.set_mode_options(
        [OptionSpec("thickness", "Line", ("Thin", "Normal", "Thick"), 1, lockable=True)]
    )
    assert len(bar._option_locks) == 1
    _dd, lock = bar._option_locks[0]
    assert bar.handle_event(_click(lock.rect)) is True
    assert calls["option"] == "thickness"


def test_preset_or_single_choice_options_have_no_lock() -> None:
    actions, _ = _actions()
    bar = ControlBar(actions, [("waveform", "Waveform")])
    bar.relayout(pygame.Rect(0, 0, 1600, 120))
    bar.set_mode_options(
        [
            OptionSpec("preset", "Preset", ("Custom", "A"), 0, lockable=False),
            OptionSpec("solo", "Solo", ("Only",), 0, lockable=False),
        ]
    )
    assert bar._option_locks == []


# -- hotkeys modal ------------------------------------------------------------
def test_hotkeys_dialog_toggles() -> None:
    dlg = HotkeysDialog()
    assert dlg.open is False
    dlg.toggle()
    assert dlg.open is True


# -- looks panel: live refresh after delete/dup -------------------------------
def test_looks_panel_refreshes_on_delete() -> None:
    store = {"rows": [("a", "One"), ("b", "Two")]}

    def _delete(look_id: str) -> None:
        store["rows"] = [r for r in store["rows"] if r[0] != look_id]

    actions = LooksActions(
        save_new=lambda name: None,
        update_active=lambda: None,
        load=lambda look_id: None,
        delete=_delete,
        duplicate=lambda look_id: None,
        refresh_state=lambda: (store["rows"], "", ""),
    )
    panel = LooksPanel(actions)
    panel.set_state([("a", "One"), ("b", "Two")], "", "")
    panel.open = True
    canvas = pygame.Rect(0, 0, 1000, 800)
    lay = panel._layout(canvas)
    # First click arms "Sure?", second confirms the delete.
    panel._handle_click(lay.rows[0].delete.center, lay)
    panel._handle_click(lay.rows[0].delete.center, lay)
    assert [r[0] for r in panel._rows] == ["b"]
