"""Audio source interface + a synthetic source for tests/CI/--selftest.

The rest of the app depends only on :class:`AudioSource`; the real capture
implementation lives in ``capture.py`` and is never imported by ``app.py`` or
the analyzer directly.
"""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray


class SourceStatus(StrEnum):
    """Lifecycle/health of an audio source (distinct from 'silent', which is a
    property of the *signal* and decided by analysis)."""

    STOPPED = "stopped"
    RUNNING = "running"
    ERROR = "error"


@runtime_checkable
class AudioSource(Protocol):
    """Pull-based mono audio source.

    Implementations expose recent samples via :meth:`read_latest`; consumers
    (the analyzer) never block on them.
    """

    sample_rate: int
    channels: int
    device_name: str
    status: SourceStatus

    def start(self) -> None:
        """Begin producing samples. Must not raise; set ERROR status instead."""
        ...

    def stop(self) -> None:
        """Stop producing samples and release resources."""
        ...

    def read_latest(self, num_samples: int) -> NDArray[np.float32] | None:
        """Return the most recent ``num_samples`` mono samples, or ``None`` if
        not enough data is available yet."""
        ...


class SyntheticSource:
    """Deterministic generator used for tests, CI, and ``--selftest``.

    Produces a continuous sine (or sweep, or silence) so the full pipeline can
    run with no hardware. Each :meth:`read_latest` advances an internal phase,
    yielding a seamless waveform regardless of call cadence.
    """

    def __init__(
        self,
        frequency: float = 440.0,
        sample_rate: int = 48000,
        amplitude: float = 0.5,
        mode: str = "sine",
    ) -> None:
        self.frequency = float(frequency)
        self.sample_rate = int(sample_rate)
        self.channels = 1
        self.amplitude = float(amplitude)
        self.mode = mode
        self.device_name = f"Synthetic ({mode})"
        self.status = SourceStatus.STOPPED
        self._phase = 0  # samples generated so far

    def start(self) -> None:
        self.status = SourceStatus.RUNNING

    def stop(self) -> None:
        self.status = SourceStatus.STOPPED

    def read_latest(self, num_samples: int) -> NDArray[np.float32] | None:
        if self.status is not SourceStatus.RUNNING or num_samples <= 0:
            return None
        n = int(num_samples)
        idx = np.arange(self._phase, self._phase + n, dtype=np.float64)
        self._phase += n

        if self.mode == "silence":
            return np.zeros(n, dtype=np.float32)

        if self.mode == "sweep":
            # Slow log sweep across the audible range for a livelier test signal.
            t = idx / self.sample_rate
            freq = 80.0 * (2.0 ** (t % 6.0))  # 80 Hz .. ~5 kHz, repeating
            phase = 2.0 * math.pi * np.cumsum(freq) / self.sample_rate
            return (self.amplitude * np.sin(phase)).astype(np.float32)

        # default: steady sine
        samples = self.amplitude * np.sin(2.0 * math.pi * self.frequency * idx / self.sample_rate)
        return samples.astype(np.float32)
