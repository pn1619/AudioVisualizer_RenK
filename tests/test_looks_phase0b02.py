"""Phase 0B-b: user custom looks ("My Looks") store, persistence, and app wiring."""

from __future__ import annotations

import json

import pytest

from audio_visualizer.app import App
from audio_visualizer.config import LOOK_NAME_MAX, LOOKS_MAX, SENSITIVITY_STEP
from audio_visualizer.looks import (
    LINK_LOCAL,
    Look,
    LooksStore,
    export_look,
    import_look,
    load,
    sanitize_name,
    save,
)
from audio_visualizer.settings import Settings
from audio_visualizer.settings import load as load_settings
from audio_visualizer.settings import save as save_settings
from audio_visualizer.ui.looks_panel import LooksActions, LooksPanel


def _look(name: str = "Look", mode: str = "spectrum") -> Look:
    return Look(
        id="",
        name=name,
        base_mode_key=mode,
        options={"bars": 1},
        theme={"size_scale": 1.0, "speed_scale": 1.0, "color_scheme": "classic"},
        sensitivity=1.0,
        smoothing=0.5,
        background={"link": LINK_LOCAL, "value": {"bg_mode": "off"}},
        logo={"link": LINK_LOCAL, "value": {"logo_enabled": False}},
    )


# -- store CRUD ---------------------------------------------------------------
def test_add_assigns_fresh_id_on_collision_and_caps() -> None:
    store = LooksStore()
    a = store.add(_look("A"))
    b = store.add(Look(id=a.id, name="B", base_mode_key="spectrum"))  # same id
    assert a is not None and b is not None
    assert a.id != b.id  # collision -> fresh id
    assert [look.name for look in store.looks] == ["A", "B"]


def test_duplicate_inserts_after_with_copy_name_and_new_id() -> None:
    store = LooksStore()
    a = store.add(_look("Neon"))
    clone = store.duplicate(a.id)
    assert clone is not None
    assert clone.name == "Neon copy"
    assert clone.id != a.id
    assert store.index_of(clone.id) == store.index_of(a.id) + 1


def test_move_reorders_and_clamps() -> None:
    store = LooksStore()
    a = store.add(_look("A"))
    b = store.add(_look("B"))
    assert store.move(b.id, -1) is True
    assert [look.name for look in store.looks] == ["B", "A"]
    assert store.move(b.id, -1) is False  # already at top -> no-op
    assert a is not None


def test_rename_and_name_exists() -> None:
    store = LooksStore()
    a = store.add(_look("A"))
    assert store.rename(a.id, "Renamed") is True
    assert store.name_exists("Renamed") is True
    assert store.name_exists("Renamed", ignore_id=a.id) is False


def test_delete_and_cap() -> None:
    store = LooksStore()
    ids = [store.add(_look(f"L{i}")).id for i in range(3)]
    assert store.delete(ids[1]) is True
    assert [look.name for look in store.looks] == ["L0", "L2"]
    full = LooksStore([_look(f"x{i}") for i in range(LOOKS_MAX)])
    assert full.add(_look("overflow")) is None  # cap enforced


def test_sanitize_name_trims_and_limits() -> None:
    assert sanitize_name("   ") == "Untitled"
    assert sanitize_name("  a   b  ") == "a b"
    assert len(sanitize_name("x" * 200)) == LOOK_NAME_MAX


# -- serialization / compatibility -------------------------------------------
def test_roundtrip_and_unknown_keys_preserved(tmp_path) -> None:
    path = tmp_path / "looks.json"
    raw = {
        "schema_version": 999,  # unknown future version -> lenient
        "looks": [
            {"id": "k1", "name": "Future", "base_mode_key": "spectrum", "tomorrow": [1, 2]},
        ],
    }
    path.write_text(json.dumps(raw), encoding="utf-8")
    store = load(path)
    assert len(store.looks) == 1
    assert store.looks[0].extra["tomorrow"] == [1, 2]

    assert save(store, path)
    reread = json.loads(path.read_text(encoding="utf-8"))
    assert reread["looks"][0]["tomorrow"] == [1, 2]  # forward-compat round-trip


def test_malformed_records_skipped_not_fatal(tmp_path) -> None:
    path = tmp_path / "looks.json"
    raw = {
        "looks": [
            {"name": "no mode"},  # missing base_mode_key -> skip
            5,  # not a dict -> skip
            {"id": "ok", "name": "Good", "base_mode_key": "spectrum"},
        ]
    }
    path.write_text(json.dumps(raw), encoding="utf-8")
    store = load(path)
    assert [look.name for look in store.looks] == ["Good"]


def test_corrupt_or_missing_file_is_empty(tmp_path) -> None:
    missing = tmp_path / "nope.json"
    assert load(missing).looks == []
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    assert load(bad).looks == []


def test_save_keeps_backup(tmp_path) -> None:
    path = tmp_path / "looks.json"
    store = LooksStore([_look("A")])
    assert save(store, path)
    assert save(store, path)  # second save rotates a .bak of the first
    assert path.with_suffix(".json.bak").exists()


def test_export_import_assigns_fresh_id(tmp_path) -> None:
    src = _look("Shared")
    src.id = "original-id"
    out = tmp_path / "shared.look.json"
    assert export_look(src, out)
    imported = import_look(out)
    assert imported is not None
    assert imported.name == "Shared"
    assert imported.id != "original-id"  # never reuse an imported id


# -- settings migration -------------------------------------------------------
def test_settings_active_look_roundtrip_and_migration(tmp_path) -> None:
    path = tmp_path / "settings.json"
    assert save_settings(Settings(active_look="abc123"), path)
    assert load_settings(path).active_look == "abc123"

    path.write_text('{"schema_version": 8, "mode": "spectrum"}', encoding="utf-8")
    migrated = load_settings(path)
    assert migrated.active_look == ""  # older file migrates to default
    assert migrated.schema_version >= 9


# -- app wiring ---------------------------------------------------------------
@pytest.fixture
def app() -> App:
    instance = App(load_settings=False)
    instance._looks_store = LooksStore()  # isolate from any real looks.json
    instance._active_look_id = ""
    instance._look_baseline = None
    return instance


def test_capture_apply_roundtrip(app: App) -> None:
    captured = app._capture_look("snap")
    app._adjust_sensitivity(SENSITIVITY_STEP)  # change the live state
    app._set_color_scheme("rainbow")
    app._apply_look(captured)
    assert app._capture_look("again").matches_payload(captured)


def test_save_new_stays_on_live(app: App) -> None:
    # Saving bookmarks the current look but leaves the user on None/Live, so the
    # saved look is a distinct dropdown entry (not silently auto-activated).
    app._save_new_look("Mine")
    assert app._active_look_id == ""
    assert len(app._looks_store.looks) == 1


def test_active_look_dirty_tracking(app: App) -> None:
    app._save_new_look("Mine")
    app._select_look(app._looks_store.looks[0].id)  # selecting it makes it active
    assert app._active_look_id != ""
    assert app._is_active_dirty() is False
    app._adjust_sensitivity(SENSITIVITY_STEP)
    assert app._is_active_dirty() is True


def test_select_none_restores_live_not_save(app: App) -> None:
    base = app._sensitivity
    app._save_new_look("Mine")
    look_id = app._looks_store.looks[0].id
    app._adjust_sensitivity(SENSITIVITY_STEP)  # live edit after saving
    live = app._sensitivity
    assert live != base
    app._select_look(look_id)  # applying the look reverts to its captured value
    assert app._sensitivity == pytest.approx(base)
    app._select_look("")  # None / Live restores the live state, not the saved look
    assert app._sensitivity == pytest.approx(live)


def test_apply_missing_mode_is_nonfatal(app: App) -> None:
    before = app._visual.KEY
    ghost = app._capture_look("ghost")
    ghost.base_mode_key = "does_not_exist_xyz"
    app._apply_look(ghost)  # must not raise
    assert app._visual.KEY == before


# -- panel --------------------------------------------------------------------
def test_panel_save_new_invokes_action() -> None:
    saved: list[str] = []
    actions = LooksActions(
        save_new=saved.append,
        update_active=lambda: None,
        load=lambda _id: None,
        delete=lambda _id: None,
        duplicate=lambda _id: None,
    )
    panel = LooksPanel(actions)
    panel.set_state([], "", "")
    panel.toggle()
    panel._name.set_text("Fresh")
    panel._submit_save(force_new=True)
    assert saved == ["Fresh"]
    assert panel.open is False
