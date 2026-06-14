"""Onset (spectral-flux) detection: transients trigger, steady tones do not."""

from __future__ import annotations

import numpy as np

from audio_visualizer.audio.analysis import Analyzer
from audio_visualizer.config import FFT_SIZE, ONSET_THRESHOLD


def _sine(freq: float, sample_rate: int, n: int, amp: float = 0.5) -> np.ndarray:
    t = np.arange(n) / sample_rate
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_broadband_transient_triggers_onset() -> None:
    analyzer = Analyzer()
    sr = 48000
    analyzer.analyze(np.zeros(FFT_SIZE, dtype=np.float32), sr)  # settle on silence
    rng = np.random.default_rng(0)
    burst = (0.8 * rng.standard_normal(FFT_SIZE)).astype(np.float32)
    frame = analyzer.analyze(burst, sr)
    assert frame.onset >= ONSET_THRESHOLD


def test_steady_tone_has_no_onset() -> None:
    analyzer = Analyzer()
    sr = 48000
    frame = None
    for _ in range(12):
        frame = analyzer.analyze(_sine(1000.0, sr, FFT_SIZE), sr)
    assert frame is not None
    assert frame.onset < ONSET_THRESHOLD


def test_silence_onset_is_zero() -> None:
    analyzer = Analyzer()
    frame = None
    for _ in range(3):
        frame = analyzer.analyze(np.zeros(FFT_SIZE, dtype=np.float32), 48000)
    assert frame is not None
    assert frame.onset == 0.0
