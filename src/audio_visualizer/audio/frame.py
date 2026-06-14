"""The immutable snapshot passed from analysis to the visualizers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class AnalysisFrame:
    """One analyzed slice of audio. Immutable so it can cross threads safely.

    Attributes:
        waveform_mono: Mono samples in ``-1..1`` used for the oscilloscope.
        band_energies: Per-band magnitudes in ``0..1`` (log-spaced, low->high Hz).
        rms: Root-mean-square level of this slice (``>= 0``).
        peak: Peak absolute sample of this slice (``0..1``).
        sample_rate: Sample rate the slice was captured at.
        timestamp: ``time.monotonic()`` when the frame was produced.
        onset: Beat/onset strength in ``0..1`` from spectral flux (0 = no transient).
    """

    waveform_mono: NDArray[np.float32]
    band_energies: NDArray[np.float32]
    rms: float
    peak: float
    sample_rate: int
    timestamp: float
    onset: float = 0.0

    @property
    def is_silent(self) -> bool:
        """True when the slice carries effectively no signal."""
        from audio_visualizer.config import IDLE_RMS_THRESHOLD

        return self.rms < IDLE_RMS_THRESHOLD
