"""macOS capture backend: device enumeration, factory dispatch, ring buffer.

Hardware-free: a fake ``sounddevice`` module is injected so these run on any OS
(including the Windows CI runner and the mac runner without a real device).
"""

from __future__ import annotations

import sys
import types

import numpy as np
import pytest

from audio_visualizer.audio.devices import SourceInfo
from audio_visualizer.audio.source import SourceStatus


def _fake_sounddevice(devices: list[dict], default_input: int = 0) -> types.ModuleType:
    """Build a stand-in ``sounddevice`` module exposing query_devices/default."""
    mod = types.ModuleType("sounddevice")

    def query_devices(index=None, kind=None):  # type: ignore[no-untyped-def]
        if kind == "input":
            dev = dict(devices[default_input])
            dev["index"] = default_input
            return dev
        if index is None:
            return list(devices)
        return devices[index]

    default = types.SimpleNamespace(device=(default_input, -1))
    mod.query_devices = query_devices  # type: ignore[attr-defined]
    mod.default = default  # type: ignore[attr-defined]
    return mod


_DEVICES = [
    {"name": "MacBook Air Microphone", "max_input_channels": 1, "default_samplerate": 48000},
    {"name": "BlackHole 2ch", "max_input_channels": 2, "default_samplerate": 48000},
    {"name": "Speakers (output only)", "max_input_channels": 0, "default_samplerate": 48000},
]


@pytest.fixture
def fake_sd(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    mod = _fake_sounddevice(_DEVICES, default_input=0)
    monkeypatch.setitem(sys.modules, "sounddevice", mod)
    return mod


def test_list_sources_orders_loopback_first(fake_sd: types.ModuleType) -> None:
    from audio_visualizer.audio import devices_mac

    sources = devices_mac.list_sources()
    names = [s.name for s in sources]
    # BlackHole (loopback-like) first, output-only device excluded.
    assert names == ["BlackHole 2ch", "MacBook Air Microphone"]
    assert sources[0].kind == "loopback"
    assert sources[1].kind == "input"


def test_default_input_flagged(fake_sd: types.ModuleType) -> None:
    from audio_visualizer.audio import devices_mac

    sources = {s.name: s for s in devices_mac.list_sources()}
    assert sources["MacBook Air Microphone"].is_default is True
    assert sources["BlackHole 2ch"].is_default is False


def test_has_loopback_device(fake_sd: types.ModuleType) -> None:
    from audio_visualizer.audio import devices_mac

    assert devices_mac.has_loopback_device() is True


def test_list_sources_empty_without_sounddevice(monkeypatch: pytest.MonkeyPatch) -> None:
    from audio_visualizer.audio import devices_mac

    monkeypatch.setitem(sys.modules, "sounddevice", None)  # import -> ImportError
    assert devices_mac.list_sources() == []


def test_loopback_hint_matching() -> None:
    from audio_visualizer.audio.devices_mac import _is_loopback_like

    assert _is_loopback_like("BlackHole 2ch")
    assert _is_loopback_like("Aggregate Device")
    assert not _is_loopback_like("MacBook Air Microphone")


def test_factory_dispatches_mac(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    from audio_visualizer.audio.capture_mac import MacInputSource
    from audio_visualizer.audio.source_factory import create_source

    src = create_source(device_id="BlackHole 2ch")
    assert isinstance(src, MacInputSource)


def test_factory_dispatches_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    from audio_visualizer.audio.capture import LoopbackSource
    from audio_visualizer.audio.source_factory import create_source

    src = create_source()
    assert isinstance(src, LoopbackSource)


def test_factory_list_sources_mac(
    monkeypatch: pytest.MonkeyPatch, fake_sd: types.ModuleType
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    from audio_visualizer.audio import source_factory

    sources = source_factory.list_sources()
    assert all(isinstance(s, SourceInfo) for s in sources)
    assert any(s.kind == "loopback" for s in sources)


def test_mac_source_ring_buffer_roundtrip() -> None:
    """Ring buffer write/read is correct without opening a real stream."""
    from audio_visualizer.audio.capture_mac import MacInputSource

    src = MacInputSource()
    src.sample_rate = 48000
    src._ring = np.zeros(10, dtype=np.float32)  # small ring for the test

    src._write_ring(np.arange(4, dtype=np.float32))
    assert src.read_latest(4) is not None
    np.testing.assert_array_equal(src.read_latest(4), np.array([0, 1, 2, 3], dtype=np.float32))

    # Wrap-around: write past capacity, keep only the most recent.
    src._write_ring(np.arange(4, 16, dtype=np.float32))  # 12 more -> wraps
    latest = src.read_latest(10)
    assert latest is not None
    np.testing.assert_array_equal(latest, np.arange(6, 16, dtype=np.float32))


def test_mac_source_read_latest_insufficient_data() -> None:
    from audio_visualizer.audio.capture_mac import MacInputSource

    src = MacInputSource()
    src._ring = np.zeros(100, dtype=np.float32)
    src._write_ring(np.ones(3, dtype=np.float32))
    assert src.read_latest(10) is None  # only 3 filled


def test_mac_source_start_fails_soft(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing/broken sounddevice sets ERROR, never raises."""
    from audio_visualizer.audio.capture_mac import MacInputSource

    monkeypatch.setitem(sys.modules, "sounddevice", None)  # import -> ImportError
    src = MacInputSource()
    src.start()
    assert src.status is SourceStatus.ERROR
