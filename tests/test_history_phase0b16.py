"""Build 16: session look history (Prev/Next back-forward queue).

Covers the in-memory history queue feeding the control-bar ``Prev``/``Next``
buttons: produce-on-Next-at-end, replay-forward, Prev step-back, and the
Rnd-truncates-forward rule. Headless (no real audio); uses ``SyntheticSource``.
"""

from __future__ import annotations

import pytest

from audio_visualizer.app import App
from audio_visualizer.looks import LooksStore


@pytest.fixture
def app() -> App:
    instance = App(load_settings=False)
    instance._looks_store = LooksStore()  # isolate from any real looks.json
    instance._auto = False
    instance._auto_pool = set()
    instance._auto_current = ""
    instance._reduce_motion = True  # hard-cut switches keep assertions simple
    return instance


def test_history_seeded_with_launch_look(app: App) -> None:
    assert len(app._history) == 1
    assert app._history_pos == 0


def test_prev_noop_at_oldest(app: App) -> None:
    app._history_back()
    assert app._history_pos == 0


def test_manual_switch_commits_and_prev_restores(app: App) -> None:
    keys = app._mode_keys
    app._set_mode_key(keys[1])
    app._set_mode_key(keys[3])
    assert app._mode_index == 3
    assert app._history_pos == 2

    app._history_back()
    assert app._mode_index == 1
    app._history_back()
    assert app._history_pos == 0


def test_rnd_commits_and_prev_restores_feel(app: App) -> None:
    app._set_mode_index(2)
    app._sensitivity = 2.0
    app._commit_history()
    pos = app._history_pos

    app._randomize_current_mode()  # rolls a new (random) feel, commits
    assert app._history_pos == pos + 1

    app._history_back()
    assert app._sensitivity == pytest.approx(2.0)
    assert app._mode_index == 2  # Rnd never switches modes


def test_next_replays_forward_without_producing(app: App) -> None:
    keys = app._mode_keys
    app._set_mode_key(keys[1])
    app._set_mode_key(keys[2])
    app._history_back()
    app._history_back()
    assert app._history_pos == 0

    n = len(app._history)
    app._history_next()  # replays forward, no new entry
    assert app._history_pos == 1
    assert len(app._history) == n
    assert app._mode_index == 1


def test_next_at_end_produces_new(app: App) -> None:
    keys = app._mode_keys
    app._set_pool_all(False)
    app._toggle_pool_item(f"mode:{keys[1]}")
    app._set_mode_index(0)
    app._auto_current = f"mode:{keys[0]}"

    n = len(app._history)
    app._history_next()  # at the newest entry -> produce a fresh item
    assert app._mode_index == 1
    assert len(app._history) == n + 1


def test_rnd_truncates_forward_branch(app: App) -> None:
    keys = app._mode_keys
    app._set_mode_key(keys[1])  # pos 1
    app._set_mode_key(keys[2])  # pos 2
    app._history_back()  # back to pos 1 (mode keys[1])
    assert app._history_pos == 1

    app._randomize_current_mode()  # drops the keys[2] entry, appends a fresh one
    assert app._history_pos == 2
    assert len(app._history) == 3

    app._history_back()  # earlier history is still intact
    assert app._mode_index == 1


def test_history_cap_rolls_oldest(app: App, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("audio_visualizer.app.HISTORY_MAX", 3)
    for _ in range(10):
        app._randomize_current_mode()
    assert len(app._history) == 3
    assert app._history_pos == 2


def test_history_goto_jumps_to_position(app: App) -> None:
    keys = app._mode_keys
    app._set_mode_key(keys[1])  # pos 1
    app._set_mode_key(keys[2])  # pos 2
    app._set_mode_key(keys[3])  # pos 3
    assert app._history_pos == 3

    app._history_goto("2")  # 1-based -> index 1 (the keys[1] entry)
    assert app._history_pos == 1
    assert app._mode_index == 1


def test_history_goto_clamps_too_big_to_latest(app: App) -> None:
    keys = app._mode_keys
    app._set_mode_key(keys[1])
    app._history_back()  # step back to oldest
    assert app._history_pos == 0

    app._history_goto("999")  # beyond the end -> clamp to the latest entry
    assert app._history_pos == len(app._history) - 1


def test_history_goto_ignores_non_numeric(app: App) -> None:
    app._set_mode_key(app._mode_keys[1])
    pos = app._history_pos
    app._history_goto("abc")
    assert app._history_pos == pos


def test_history_goto_below_one_clamps_to_first(app: App) -> None:
    keys = app._mode_keys
    app._set_mode_key(keys[1])
    app._set_mode_key(keys[2])
    app._history_goto("0")  # 1-based; anything < 1 clamps to the first entry
    assert app._history_pos == 0
