"""SyntheticSource behavior + the int16/stereo downmix math used by capture."""

from __future__ import annotations

import numpy as np

from audio_visualizer.audio.source import SourceStatus, SyntheticSource


def test_synthetic_requires_start() -> None:
    src = SyntheticSource()
    assert src.read_latest(128) is None
    src.start()
    assert src.status is SourceStatus.RUNNING
    out = src.read_latest(128)
    assert out is not None and out.size == 128
    assert out.dtype == np.float32


def test_synthetic_is_bounded_and_continuous() -> None:
    src = SyntheticSource(frequency=440.0, sample_rate=48000, amplitude=0.5)
    src.start()
    a = src.read_latest(256)
    b = src.read_latest(256)
    assert a is not None and b is not None
    assert np.max(np.abs(a)) <= 0.5 + 1e-6
    # Phase advances, so consecutive blocks are not identical.
    assert not np.array_equal(a, b)


def test_synthetic_silence_mode() -> None:
    src = SyntheticSource(mode="silence")
    src.start()
    out = src.read_latest(512)
    assert out is not None
    assert np.allclose(out, 0.0)


def test_int16_stereo_downmix_to_mono_float() -> None:
    # Mirrors capture.py: int16 stereo -> mean -> /32768 -> float32 in -1..1.
    stereo = np.array([[32767, -32768], [0, 0], [16384, 16384]], dtype=np.int16)
    mono = stereo.reshape(-1, 2).mean(axis=1).astype(np.float32) / 32768.0
    assert mono.shape == (3,)
    assert mono.dtype == np.float32
    assert -1.0 <= float(mono.min()) and float(mono.max()) <= 1.0
    assert abs(mono[2] - 0.5) < 1e-3
