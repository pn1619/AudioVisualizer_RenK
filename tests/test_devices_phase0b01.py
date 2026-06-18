"""Phase 0B-a: selectable sound source (device enumeration, resolution, panel)."""

from __future__ import annotations

import pygame

from audio_visualizer.audio.capture import LoopbackSource
from audio_visualizer.audio.devices import _iter_raw, find_device_info
from audio_visualizer.settings import Settings
from audio_visualizer.settings import load as load_settings
from audio_visualizer.settings import save as save_settings
from audio_visualizer.ui.source_panel import SourceActions, SourcePanel

_WASAPI = 0  # fake host-API index used throughout


class _FakePA:
    """Minimal stand-in for ``pyaudiowpatch.PyAudio`` for enumeration tests."""

    def __init__(self, loopbacks: list[dict], devices: list[dict], default_name: str = "") -> None:
        self._loopbacks = loopbacks
        self._devices = devices
        self._default_name = default_name

    def get_loopback_device_info_generator(self):
        return iter(self._loopbacks)

    def get_host_api_info_by_type(self, _type: int) -> dict:
        return {"index": _WASAPI}

    def get_device_count(self) -> int:
        return len(self._devices)

    def get_device_info_by_index(self, i: int) -> dict:
        return self._devices[i]

    def get_default_wasapi_loopback(self) -> dict:
        return {
            "name": self._default_name,
            "index": 0,
            "maxInputChannels": 2,
            "defaultSampleRate": 48000,
        }


class _FakePyaudioModule:
    paWASAPI = _WASAPI


def _sample_pa() -> _FakePA:
    loopbacks = [{"name": "Speakers [Loopback]", "index": 5, "maxInputChannels": 2}]
    devices = [
        {
            "name": "Speakers [Loopback]",
            "isLoopbackDevice": True,
            "maxInputChannels": 2,
            "hostApi": _WASAPI,
        },
        {"name": "Microphone", "maxInputChannels": 1, "hostApi": _WASAPI},
        {"name": "Mic (MME)", "maxInputChannels": 1, "hostApi": 9},  # non-WASAPI -> skipped
        {"name": "Speakers", "maxInputChannels": 0, "hostApi": _WASAPI},  # output-only -> skipped
    ]
    return _FakePA(loopbacks, devices, default_name="Speakers [Loopback]")


def test_iter_raw_lists_loopback_then_inputs_and_filters() -> None:
    rows = _iter_raw(_sample_pa(), _WASAPI)
    names = [(str(info["name"]), kind) for info, kind in rows]
    assert names == [("Speakers [Loopback]", "loopback"), ("Microphone", "input")]


def test_find_device_info_matches_or_none() -> None:
    pa = _sample_pa()
    assert find_device_info(pa, "Microphone", _WASAPI)["maxInputChannels"] == 1
    assert find_device_info(pa, "does-not-exist", _WASAPI) is None
    assert find_device_info(pa, "", _WASAPI) is None  # empty id -> default, no lookup


def test_resolve_device_default_match_and_fallback() -> None:
    pa = _sample_pa()
    module = _FakePyaudioModule()

    default_src = LoopbackSource(device_id="")
    default_src._pa = pa
    assert default_src._resolve_device(module)["name"] == "Speakers [Loopback]"

    pinned = LoopbackSource(device_id="Microphone")
    pinned._pa = pa
    assert pinned._resolve_device(module)["name"] == "Microphone"

    gone = LoopbackSource(device_id="Unplugged")
    gone._pa = pa
    # Missing device -> default loopback fallback (never raises).
    assert gone._resolve_device(module)["name"] == "Speakers [Loopback]"


def test_settings_source_id_roundtrip_and_migration(tmp_path) -> None:
    path = tmp_path / "settings.json"
    assert save_settings(Settings(source_id="Microphone"), path)
    assert load_settings(path).source_id == "Microphone"

    # An older (v7, no source_id) file migrates to a default empty source_id.
    path.write_text('{"schema_version": 7, "mode": "spectrum"}', encoding="utf-8")
    migrated = load_settings(path)
    assert migrated.source_id == ""
    assert migrated.schema_version >= 8


def test_source_panel_click_selects_and_closes() -> None:
    selected: list[str] = []
    panel = SourcePanel(SourceActions(select=selected.append))
    panel.set_state([("", "Default (system audio)"), ("Microphone", "Input: Microphone")], "")
    panel.open = True
    canvas = pygame.Rect(0, 0, 800, 600)

    rows = panel._row_rects(canvas)
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rows[1][1].center)
    assert panel.handle_event(event, canvas) is True
    assert selected == ["Microphone"]
    assert panel.open is False


def test_source_panel_click_outside_closes() -> None:
    panel = SourcePanel(SourceActions(select=lambda _id: None))
    panel.set_state([("", "Default (system audio)")], "")
    panel.open = True
    canvas = pygame.Rect(0, 0, 800, 600)
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(2, 2))
    panel.handle_event(event, canvas)
    assert panel.open is False
