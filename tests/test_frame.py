"""AnalysisFrame contract: immutability and shapes."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from audio_visualizer.audio.frame import AnalysisFrame


def _make_frame(rms: float = 0.5) -> AnalysisFrame:
    return AnalysisFrame(
        waveform_mono=np.zeros(8, dtype=np.float32),
        band_energies=np.zeros(4, dtype=np.float32),
        rms=rms,
        peak=rms,
        sample_rate=48000,
        timestamp=0.0,
    )


def test_frame_is_frozen() -> None:
    frame = _make_frame()
    with pytest.raises(dataclasses.FrozenInstanceError):
        frame.rms = 1.0  # type: ignore[misc]


def test_is_silent_threshold() -> None:
    assert _make_frame(rms=0.0).is_silent
    assert not _make_frame(rms=0.5).is_silent


def test_shapes_and_dtypes() -> None:
    frame = _make_frame()
    assert frame.waveform_mono.dtype == np.float32
    assert frame.band_energies.size == 4
    assert frame.sample_rate == 48000
