"""Real WASAPI loopback capture via pyaudiowpatch.

Negotiates the default render device's native format, downmixes to mono
float32 in ``-1..1``, and writes into a bounded ring buffer from a tiny
callback. All failures set ``status = ERROR`` instead of raising, so the app
can show a banner and keep running.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import numpy as np
from numpy.typing import NDArray

from audio_visualizer.audio.devices import find_device_info
from audio_visualizer.audio.source import SourceStatus
from audio_visualizer.config import RING_BUFFER_SECONDS, SAMPLE_RATE_FALLBACK

logger = logging.getLogger(__name__)


class LoopbackSource:
    """Captures audio from a WASAPI device.

    With ``device_id == ""`` it follows the **default render device's** loopback
    (today's behavior — "what you hear"). A non-empty ``device_id`` (a device
    *name* from :mod:`audio.devices`) pins a specific output loopback or real
    input (microphone); if that device is gone at ``start()`` time it falls back
    to the default loopback rather than failing.
    """

    def __init__(self, device_id: str = "", ring_seconds: float = RING_BUFFER_SECONDS) -> None:
        self.sample_rate = SAMPLE_RATE_FALLBACK
        self.channels = 2
        self.device_name = ""
        self.status = SourceStatus.STOPPED
        self._device_id = device_id

        self._ring_seconds = ring_seconds
        self._pa: Any = None
        self._stream: Any = None
        self._continue_flag = 0  # pyaudio.paContinue, resolved on start()

        self._lock = threading.Lock()
        self._ring: NDArray[np.float32] | None = None
        self._write = 0
        self._filled = 0

    # -- lifecycle ------------------------------------------------------------
    def start(self) -> None:
        try:
            import pyaudiowpatch as pyaudio

            self._continue_flag = pyaudio.paContinue
            self._pa = pyaudio.PyAudio()
            info = self._resolve_device(pyaudio)

            self.sample_rate = int(info["defaultSampleRate"])
            self.channels = max(1, int(info["maxInputChannels"]))
            self.device_name = str(info["name"])

            ring_len = max(1, int(self.sample_rate * self._ring_seconds))
            with self._lock:
                self._ring = np.zeros(ring_len, dtype=np.float32)
                self._write = 0
                self._filled = 0

            self._stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=int(info["index"]),
                frames_per_buffer=1024,
                stream_callback=self._callback,
            )
            self.status = SourceStatus.RUNNING
            logger.info(
                "Loopback started: %s @ %d Hz, %d ch",
                self.device_name,
                self.sample_rate,
                self.channels,
            )
        except Exception:
            logger.exception("Failed to start loopback capture")
            self.status = SourceStatus.ERROR
            self._cleanup()

    def _resolve_device(self, pyaudio: Any) -> dict:
        """Pick the device dict to open: the pinned ``device_id`` if present and
        still available, else the default render device's loopback."""
        if self._device_id:
            match = find_device_info(self._pa, self._device_id, pyaudio.paWASAPI)
            if match is not None:
                return match
            logger.warning(
                "Selected source %r not found; falling back to default loopback",
                self._device_id,
            )
        return self._pa.get_default_wasapi_loopback()

    def stop(self) -> None:
        self._cleanup()
        self.status = SourceStatus.STOPPED

    def _cleanup(self) -> None:
        try:
            if self._stream is not None:
                self._stream.stop_stream()
                self._stream.close()
        except Exception:  # pragma: no cover - defensive
            logger.debug("Error closing stream", exc_info=True)
        finally:
            self._stream = None
        try:
            if self._pa is not None:
                self._pa.terminate()
        except Exception:  # pragma: no cover - defensive
            logger.debug("Error terminating PyAudio", exc_info=True)
        finally:
            self._pa = None

    # -- audio callback (runs on a background thread; keep it tiny) -----------
    def _callback(self, in_data, frame_count, time_info, status_flags):
        try:
            raw = np.frombuffer(in_data, dtype=np.int16)
            if self.channels > 1:
                raw = raw.reshape(-1, self.channels).mean(axis=1)
            mono = raw.astype(np.float32) / 32768.0
            self._write_ring(mono)
        except Exception:  # pragma: no cover - never propagate from callback
            logger.debug("callback error", exc_info=True)
        return (None, self._continue_flag)

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
