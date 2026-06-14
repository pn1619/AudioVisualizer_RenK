"""Settings persistence: round-trip + corrupt/unknown/bad-type -> defaults."""

from __future__ import annotations

import json

from audio_visualizer import settings as s
from audio_visualizer.config import DEFAULT_WINDOW_SIZE, SETTINGS_SCHEMA_VERSION
from audio_visualizer.settings import Settings


def test_round_trip(tmp_path) -> None:
    path = tmp_path / "settings.json"
    original = Settings(
        mode="spectrum",
        sensitivity=2.0,
        smoothing=0.3,
        reduce_motion=True,
        fullscreen=True,
        window_size=(800, 600),
        notice_acknowledged=True,
        size_scale=1.5,
        speed_scale=0.5,
        color_scheme="rainbow",
    )
    assert s.save(original, path) is True
    loaded = s.load(path)
    assert loaded.mode == "spectrum"
    assert loaded.sensitivity == 2.0
    assert loaded.smoothing == 0.3
    assert loaded.reduce_motion is True
    assert loaded.fullscreen is True
    assert loaded.window_size == (800, 600)
    assert loaded.notice_acknowledged is True
    assert loaded.size_scale == 1.5
    assert loaded.speed_scale == 0.5
    assert loaded.color_scheme == "rainbow"


def test_invalid_color_scheme_falls_back(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"color_scheme": "neon"}), encoding="utf-8")
    assert s.load(path).color_scheme == "classic"


def test_missing_file_returns_defaults(tmp_path) -> None:
    assert s.load(tmp_path / "does-not-exist.json") == Settings()


def test_corrupt_json_returns_defaults(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{ this is not valid json", encoding="utf-8")
    assert s.load(path) == Settings()


def test_non_object_json_returns_defaults(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert s.load(path) == Settings()


def test_unknown_schema_keeps_known_keys(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"schema_version": 999, "mode": "laser", "sensitivity": 3.0}),
        encoding="utf-8",
    )
    loaded = s.load(path)
    assert loaded.schema_version == SETTINGS_SCHEMA_VERSION
    assert loaded.mode == "laser"
    assert loaded.sensitivity == 3.0


def test_wrong_types_fall_back_per_field(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"sensitivity": "loud", "window_size": "big", "reduce_motion": "yes"}),
        encoding="utf-8",
    )
    loaded = s.load(path)
    assert loaded.sensitivity == 1.0
    assert loaded.window_size == DEFAULT_WINDOW_SIZE
    assert loaded.reduce_motion is False
