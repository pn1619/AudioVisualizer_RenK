"""Bounded mono ring buffer shared by macOS capture backends.

A single-writer / single-reader circular buffer of ``float32`` samples. Writes
happen on an audio callback thread; :meth:`read_latest` is called from the main
loop. A lock guards the small critical sections (index math + copies) so the two
threads never see a torn state.
"""

from __future__ import annotations

import threading

import numpy as np
from numpy.typing import NDArray


class MonoRingBuffer:
    """Fixed-capacity circular buffer holding the most recent mono samples."""

    def __init__(self, capacity: int) -> None:
        cap = max(1, int(capacity))
        self._ring: NDArray[np.float32] = np.zeros(cap, dtype=np.float32)
        self._write = 0
        self._filled = 0
        self._lock = threading.Lock()

    def write(self, mono: NDArray[np.float32]) -> None:
        """Append ``mono`` samples, overwriting the oldest when full."""
        with self._lock:
            ring = self._ring
            cap = ring.size
            n = mono.size
            if n == 0:
                return
            if n >= cap:
                ring[:] = mono[-cap:]
                self._write = 0
                self._filled = cap
                return
            end = self._write + n
            if end <= cap:
                ring[self._write : end] = mono
            else:
                first = cap - self._write
                ring[self._write :] = mono[:first]
                ring[: end - cap] = mono[first:]
            self._write = end % cap
            self._filled = min(cap, self._filled + n)

    def read_latest(self, num_samples: int) -> NDArray[np.float32] | None:
        """Return the most recent ``num_samples``, or ``None`` if not enough yet."""
        n = int(num_samples)
        with self._lock:
            ring = self._ring
            if n <= 0 or self._filled < n:
                return None
            cap = ring.size
            start = (self._write - n) % cap
            if start + n <= cap:
                return ring[start : start + n].copy()
            first = cap - start
            out = np.empty(n, dtype=np.float32)
            out[:first] = ring[start:]
            out[first:] = ring[: n - first]
            return out
