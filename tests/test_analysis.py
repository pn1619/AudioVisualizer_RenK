"""DSP unit tests on synthetic signals."""

from __future__ import annotations

import numpy as np

from audio_visualizer.audio.analysis import Analyzer
from audio_visualizer.config import BAND_COUNT, FFT_SIZE


def _sine(freq: float, sample_rate: int, n: int, amp: float = 0.5) -> np.ndarray:
    t = np.arange(n) / sample_rate
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_silence_gives_zero_bands_no_nan() -> None:
    analyzer = Analyzer()
    frame = analyzer.analyze(np.zeros(FFT_SIZE, dtype=np.float32), 48000)
    assert frame.rms == 0.0
    assert not np.any(np.isnan(frame.band_energies))
    assert float(frame.band_energies.max()) < 1e-3


def test_sine_energy_lands_in_expected_band() -> None:
    sr = 48000
    freq = 1000.0
    analyzer = Analyzer()
    # Run a few times so attack smoothing settles.
    frame = None
    for _ in range(20):
        frame = analyzer.analyze(_sine(freq, sr, FFT_SIZE), sr)
    assert frame is not None
    peak_band = int(np.argmax(frame.band_energies))

    # Recreate the band edges to find which band 1 kHz should fall into.
    edges = np.logspace(np.log10(30.0), np.log10(min(16000.0, sr / 2 - 1)), BAND_COUNT + 1)
    expected = int(np.searchsorted(edges, freq) - 1)
    assert abs(peak_band - expected) <= 1


def test_rms_and_peak_match_known_input() -> None:
    analyzer = Analyzer()
    sr = 48000
    frame = analyzer.analyze(_sine(1000.0, sr, FFT_SIZE, amp=0.5), sr)
    assert abs(frame.rms - 0.5 / np.sqrt(2)) < 0.02
    assert abs(frame.peak - 0.5) < 0.02


def test_band_mapping_respects_sample_rate() -> None:
    analyzer = Analyzer()
    f1 = analyzer.analyze(_sine(1000.0, 44100, FFT_SIZE), 44100)
    f2 = analyzer.analyze(_sine(1000.0, 48000, FFT_SIZE), 48000)
    assert f1.sample_rate == 44100
    assert f2.sample_rate == 48000
    # The band map is rebuilt per rate; both should produce valid 0..1 bands.
    for f in (f1, f2):
        assert f.band_energies.min() >= 0.0
        assert f.band_energies.max() <= 1.0


def test_block_length_is_normalized() -> None:
    analyzer = Analyzer()
    short = analyzer.analyze(np.ones(100, dtype=np.float32), 48000)
    long = analyzer.analyze(np.ones(FFT_SIZE * 2, dtype=np.float32), 48000)
    assert short.waveform_mono.size == FFT_SIZE
    assert long.waveform_mono.size == FFT_SIZE
