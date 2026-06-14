"""Pure DSP: samples in -> AnalysisFrame out. No pygame, no I/O.

Hann window + rfft -> log-spaced bands, plus RMS/peak, with attack/release
smoothing. Guards against silence so all-zero input never yields NaN.
"""

from __future__ import annotations

import time

import numpy as np
from numpy.typing import NDArray

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import (
    BAND_COUNT,
    FFT_SIZE,
    MAX_HZ,
    MIN_HZ,
    ONSET_FLUX_GAIN,
    SMOOTH_ATTACK,
    SMOOTH_RELEASE,
)

# Magnitudes are mapped from this dB floor..0 dB into 0..1 for display.
_DB_FLOOR = -80.0
_EPS = 1e-9


class Analyzer:
    """Turns a block of mono samples into a normalized, smoothed AnalysisFrame."""

    def __init__(
        self,
        fft_size: int = FFT_SIZE,
        band_count: int = BAND_COUNT,
        min_hz: float = MIN_HZ,
        max_hz: float = MAX_HZ,
        attack: float = SMOOTH_ATTACK,
        release: float = SMOOTH_RELEASE,
    ) -> None:
        self.fft_size = int(fft_size)
        self.band_count = int(band_count)
        self.min_hz = float(min_hz)
        self.max_hz = float(max_hz)
        self.attack = float(attack)
        self.release = float(release)

        self._window = np.hanning(self.fft_size).astype(np.float32)
        self._smoothed = np.zeros(self.band_count, dtype=np.float32)
        self._prev_targets = np.zeros(self.band_count, dtype=np.float32)
        self._cached_rate: int | None = None
        self._band_bins: list[tuple[int, int]] = []

    def set_smoothing(self, attack: float, release: float) -> None:
        """Update attack/release coefficients at runtime (from UI controls)."""
        self.attack = float(np.clip(attack, 0.01, 1.0))
        self.release = float(np.clip(release, 0.01, 1.0))

    def _ensure_band_map(self, sample_rate: int) -> None:
        """(Re)build the FFT-bin ranges for each log-spaced band for this rate."""
        if sample_rate == self._cached_rate and self._band_bins:
            return
        nyquist = sample_rate / 2.0
        hi = min(self.max_hz, nyquist - 1.0)
        lo = max(1.0, self.min_hz)
        edges = np.logspace(np.log10(lo), np.log10(hi), self.band_count + 1)
        freqs = np.fft.rfftfreq(self.fft_size, d=1.0 / sample_rate)

        bins: list[tuple[int, int]] = []
        for i in range(self.band_count):
            start = int(np.searchsorted(freqs, edges[i], side="left"))
            end = int(np.searchsorted(freqs, edges[i + 1], side="left"))
            end = max(end, start + 1)  # every band owns at least one bin
            bins.append((start, min(end, freqs.size)))
        self._band_bins = bins
        self._cached_rate = sample_rate

    def reset(self) -> None:
        """Clear smoothing/onset state (e.g. after stopping capture)."""
        self._smoothed[:] = 0.0
        self._prev_targets[:] = 0.0

    def analyze(self, samples: NDArray[np.float32], sample_rate: int) -> AnalysisFrame:
        """Analyze ``samples`` (mono float32). Length is normalized to fft_size."""
        block = self._fit_block(samples)
        rms = float(np.sqrt(np.mean(block * block))) if block.size else 0.0
        peak = float(np.max(np.abs(block))) if block.size else 0.0

        self._ensure_band_map(sample_rate)
        windowed = block * self._window
        spectrum = np.abs(np.fft.rfft(windowed)) / (self.fft_size / 2)

        targets = np.empty(self.band_count, dtype=np.float32)
        for i, (start, end) in enumerate(self._band_bins):
            mag = float(np.mean(spectrum[start:end])) if end > start else 0.0
            db = 20.0 * np.log10(mag + _EPS)
            targets[i] = float(np.clip((db - _DB_FLOOR) / (-_DB_FLOOR), 0.0, 1.0))

        onset = self._compute_onset(targets)
        self._apply_smoothing(targets)

        return AnalysisFrame(
            waveform_mono=block.copy(),
            band_energies=self._smoothed.copy(),
            rms=rms,
            peak=peak,
            sample_rate=int(sample_rate),
            timestamp=time.monotonic(),
            onset=onset,
        )

    def _compute_onset(self, targets: NDArray[np.float32]) -> float:
        """Spectral flux: positive band increases since the last frame, 0..1."""
        flux = float(np.sum(np.maximum(targets - self._prev_targets, 0.0)))
        self._prev_targets = targets.copy()
        return float(np.clip(flux / self.band_count * ONSET_FLUX_GAIN, 0.0, 1.0))

    def _fit_block(self, samples: NDArray[np.float32]) -> NDArray[np.float32]:
        s = np.asarray(samples, dtype=np.float32).ravel()
        if s.size == self.fft_size:
            return s
        if s.size > self.fft_size:
            return s[-self.fft_size :]
        out = np.zeros(self.fft_size, dtype=np.float32)
        if s.size:
            out[-s.size :] = s
        return out

    def _apply_smoothing(self, targets: NDArray[np.float32]) -> None:
        rising = targets > self._smoothed
        coeff = np.where(rising, self.attack, self.release).astype(np.float32)
        self._smoothed += coeff * (targets - self._smoothed)
