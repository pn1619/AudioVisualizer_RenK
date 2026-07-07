"""macOS audio capture via PortAudio (``sounddevice``).

macOS has no WASAPI-style loopback, so this opens a PortAudio **input** stream —
a microphone by default, or a virtual loopback device (e.g. BlackHole) when the
user routes system audio into it (see ``plan/macos-port.md``). Mirrors
:class:`audio.capture.LoopbackSource`: negotiates the device's native format,
downmixes to mono float32 ``-1..1`` in a tiny callback, and writes into a bounded
ring buffer. All failures set ``status = ERROR`` instead of raising.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import numpy as np
from numpy.typing import NDArray

from audio_visualizer.audio.source import SourceStatus
from audio_visualizer.config import RING_BUFFER_SECONDS, SAMPLE_RATE_FALLBACK

logger = logging.getLogger(__name__)

# PortAudio callback block size (frames); small enough for low latency, large
# enough to keep callback overhead negligible.
_BLOCK_SIZE = 1024


class MacInputSource:
    """Captures audio from a macOS input device via ``sounddevice``.

    With ``device_id == ""`` it follows the **system default input**. A non-empty
    ``device_id`` (a device *name*) pins a specific input; if that device is gone
    at :meth:`start` it falls back to the default input rather than failing.
    """

    def __init__(self, device_id: str = "", ring_seconds: float = RING_BUFFER_SECONDS) -> None:
        self.sample_rate = SAMPLE_RATE_FALLBACK
        self.channels = 1
        self.device_name = ""
        self.status = SourceStatus.STOPPED
        self._device_id = device_id

        self._ring_seconds = ring_seconds
        self._stream: Any = None

        self._lock = threading.Lock()
        self._ring: NDArray[np.float32] | None = None
        self._write = 0
        self._filled = 0

    # -- lifecycle ------------------------------------------------------------
    def start(self) -> None:
        try:
            import sounddevice as sd

            index, info = self._resolve_device(sd)
            self.sample_rate = int(info["default_samplerate"])
            self.channels = max(1, int(info["max_input_channels"]))
            self.device_name = str(info["name"])

            ring_len = max(1, int(self.sample_rate * self._ring_seconds))
            with self._lock:
                self._ring = np.zeros(ring_len, dtype=np.float32)
                self._write = 0
                self._filled = 0

            self._stream = sd.InputStream(
                device=index,
                channels=self.channels,
                samplerate=self.sample_rate,
                dtype="float32",
                blocksize=_BLOCK_SIZE,
                callback=self._callback,
            )
            self._stream.start()
            self.status = SourceStatus.RUNNING
            logger.info(
                "Mac input started: %s @ %d Hz, %d ch",
                self.device_name,
                self.sample_rate,
                self.channels,
            )
        except Exception:
            logger.exception("Failed to start macOS input capture")
            self.status = SourceStatus.ERROR
            self._cleanup()

    def _resolve_device(self, sd: Any) -> tuple[int | None, dict]:
        """Return ``(device_index, info)`` to open: the pinned ``device_id`` if
        present and still available, else the system default input."""
        if self._device_id:
            try:
                for idx, dev in enumerate(sd.query_devices()):
                    if int(dev["max_input_channels"]) < 1:
                        continue
                    if str(dev["name"]) == self._device_id:
                        return idx, dev
            except Exception:  # pragma: no cover - defensive
                logger.debug("Device enumeration failed while resolving", exc_info=True)
            logger.warning(
                "Selected source %r not found; falling back to default input",
                self._device_id,
            )
        default = sd.query_devices(kind="input")
        # query_devices(kind=...) omits an index; None tells PortAudio "default".
        return None, default

    def stop(self) -> None:
        self._cleanup()
        self.status = SourceStatus.STOPPED

    def _cleanup(self) -> None:
        try:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
        except Exception:  # pragma: no cover - defensive
            logger.debug("Error closing stream", exc_info=True)
        finally:
            self._stream = None

    # -- audio callback (runs on a background thread; keep it tiny) -----------
    def _callback(self, indata, frames, time_info, status_flags):
        try:
            block = np.asarray(indata, dtype=np.float32)
            mono = block.mean(axis=1) if block.ndim > 1 else block
            self._write_ring(mono)
        except Exception:  # pragma: no cover - never propagate from callback
            logger.debug("callback error", exc_info=True)

    def _write_ring(self, mono: NDArray[np.float32]) -> None:
        with self._lock:
            ring = self._ring
            if ring is None:
                return
            n = mono.size
            cap = ring.size
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

    # -- consumer -------------------------------------------------------------
    def read_latest(self, num_samples: int) -> NDArray[np.float32] | None:
        n = int(num_samples)
        with self._lock:
            ring = self._ring
            if ring is None or self._filled < n or n <= 0:
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
