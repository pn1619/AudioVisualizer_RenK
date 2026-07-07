"""macOS native (ScreenCaptureKit) system-audio backend — hardware-free tests.

Covers the pure/plumbing parts that don't need Screen Recording permission or a
real display: PCM downmix, the shared ring buffer, factory dispatch, the picker
entry, fail-soft ``start()``, and the CMSampleBuffer extraction orchestration
(with a fake CoreMedia/CoreAudio).
"""

from __future__ import annotations

import sys
import types

import numpy as np
import pytest

from audio_visualizer.audio.ring_buffer import MonoRingBuffer
from audio_visualizer.audio.source import SourceStatus
from audio_visualizer.config import MAC_SYSTEM_AUDIO_SOURCE_ID


# -- downmix ------------------------------------------------------------------
def test_downmix_interleaved_stereo() -> None:
    from audio_visualizer.audio.capture_mac_native import downmix_pcm_float32

    data = np.array([1, 3, 2, 4, 3, 5], dtype=np.float32).tobytes()  # LR LR LR
    np.testing.assert_array_equal(
        downmix_pcm_float32(data, 2, interleaved=True),
        np.array([2, 3, 4], dtype=np.float32),
    )


def test_downmix_planar_stereo() -> None:
    from audio_visualizer.audio.capture_mac_native import downmix_pcm_float32

    data = np.array([1, 2, 3, 3, 4, 5], dtype=np.float32).tobytes()  # LLL RRR
    np.testing.assert_array_equal(
        downmix_pcm_float32(data, 2, interleaved=False),
        np.array([2, 3, 4], dtype=np.float32),
    )


def test_downmix_mono_passthrough() -> None:
    from audio_visualizer.audio.capture_mac_native import downmix_pcm_float32

    data = np.array([0.1, 0.2, 0.3], dtype=np.float32).tobytes()
    np.testing.assert_allclose(
        downmix_pcm_float32(data, 1, interleaved=True),
        np.array([0.1, 0.2, 0.3], dtype=np.float32),
    )


def test_downmix_ragged_tail_trimmed() -> None:
    from audio_visualizer.audio.capture_mac_native import downmix_pcm_float32

    # 5 samples, 2 channels -> last stray sample dropped, 2 mono frames.
    data = np.array([1, 1, 2, 2, 9], dtype=np.float32).tobytes()
    out = downmix_pcm_float32(data, 2, interleaved=True)
    np.testing.assert_array_equal(out, np.array([1, 2], dtype=np.float32))


def test_downmix_empty() -> None:
    from audio_visualizer.audio.capture_mac_native import downmix_pcm_float32

    assert downmix_pcm_float32(b"", 2, interleaved=True).size == 0


# -- ring buffer --------------------------------------------------------------
def test_ring_buffer_roundtrip_and_wrap() -> None:
    ring = MonoRingBuffer(10)
    ring.write(np.arange(4, dtype=np.float32))
    np.testing.assert_array_equal(ring.read_latest(4), np.arange(4, dtype=np.float32))
    ring.write(np.arange(4, 16, dtype=np.float32))  # wraps
    np.testing.assert_array_equal(ring.read_latest(10), np.arange(6, 16, dtype=np.float32))


def test_ring_buffer_insufficient_returns_none() -> None:
    ring = MonoRingBuffer(100)
    ring.write(np.ones(3, dtype=np.float32))
    assert ring.read_latest(10) is None


def test_ring_buffer_write_larger_than_capacity() -> None:
    ring = MonoRingBuffer(4)
    ring.write(np.arange(10, dtype=np.float32))
    np.testing.assert_array_equal(ring.read_latest(4), np.array([6, 7, 8, 9], dtype=np.float32))


# -- availability / factory / picker -----------------------------------------
def test_native_capture_available_returns_bool() -> None:
    from audio_visualizer.audio.capture_mac_native import native_capture_available

    assert isinstance(native_capture_available(), bool)


def test_factory_dispatches_native_on_sentinel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    from audio_visualizer.audio.capture_mac_native import MacSystemAudioSource
    from audio_visualizer.audio.source_factory import create_source

    src = create_source(MAC_SYSTEM_AUDIO_SOURCE_ID)
    assert isinstance(src, MacSystemAudioSource)


def test_picker_lists_native_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    from audio_visualizer.audio import devices_mac

    monkeypatch.setattr(devices_mac, "native_capture_available", lambda: True)
    # No sounddevice -> only the native entry remains.
    monkeypatch.setitem(sys.modules, "sounddevice", None)
    sources = devices_mac.list_sources()
    assert sources and sources[0].id == MAC_SYSTEM_AUDIO_SOURCE_ID
    assert sources[0].kind == "loopback"


def test_picker_omits_native_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    from audio_visualizer.audio import devices_mac

    monkeypatch.setattr(devices_mac, "native_capture_available", lambda: False)
    monkeypatch.setitem(sys.modules, "sounddevice", None)
    assert devices_mac.list_sources() == []


# -- fail-soft start ----------------------------------------------------------
def test_native_start_fails_soft_without_frameworks(monkeypatch: pytest.MonkeyPatch) -> None:
    from audio_visualizer.audio.capture_mac_native import MacSystemAudioSource

    monkeypatch.setitem(sys.modules, "ScreenCaptureKit", None)  # import -> ImportError
    src = MacSystemAudioSource()
    src.start()
    assert src.status is SourceStatus.ERROR
    assert src.read_latest(1024) is None
    src.stop()
    assert src.status is SourceStatus.STOPPED


# -- CMSampleBuffer extraction orchestration (fake CoreMedia/CoreAudio) -------
def _fake_coremedia(channels: int, planar_flag: bool, pcm: bytes) -> types.ModuleType:
    cm = types.ModuleType("CoreMedia")

    asbd = types.SimpleNamespace(
        mChannelsPerFrame=channels,
        mFormatFlags=(1 << 5) if planar_flag else 0,
    )
    cm.CMSampleBufferGetFormatDescription = lambda sbuf: "fmt"  # type: ignore[attr-defined]
    cm.CMAudioFormatDescriptionGetStreamBasicDescription = lambda fmt: asbd  # type: ignore[attr-defined]

    def get_abl(sbuf, a1, abl, size, a4, a5, flag, a7):  # type: ignore[no-untyped-def]
        if abl is None:  # size-query pass
            return (0, 64, None)
        return (0, 0, "blockbuffer")

    cm.CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer = get_abl  # type: ignore[attr-defined]
    cm.CMBlockBufferGetDataLength = lambda bb: len(pcm)  # type: ignore[attr-defined]
    cm.CMBlockBufferCopyDataBytes = lambda bb, off, length, dest: (0, pcm)  # type: ignore[attr-defined]
    return cm


def test_extract_mono_from_fake_sample_buffer(monkeypatch: pytest.MonkeyPatch) -> None:
    from audio_visualizer.audio import capture_mac_native as native

    pcm = np.array([1, 3, 2, 4], dtype=np.float32).tobytes()  # interleaved LR LR
    cm = _fake_coremedia(channels=2, planar_flag=False, pcm=pcm)

    fake_coreaudio = types.ModuleType("CoreAudio")
    fake_coreaudio.AudioBufferList = lambda n: object()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "CoreAudio", fake_coreaudio)

    out = native._extract_mono(cm, sample_buffer="sbuf")
    np.testing.assert_array_equal(out, np.array([2, 3], dtype=np.float32))


def test_extract_mono_returns_none_on_bad_status(monkeypatch: pytest.MonkeyPatch) -> None:
    from audio_visualizer.audio import capture_mac_native as native

    cm = _fake_coremedia(channels=2, planar_flag=False, pcm=b"")
    cm.CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer = (  # type: ignore[attr-defined]
        lambda *a: (-1, 0, None)
    )
    assert native._extract_mono(cm, sample_buffer="sbuf") is None
