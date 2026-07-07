"""Native macOS system-audio capture via ScreenCaptureKit (no extra drivers).

macOS 13+ exposes system audio ("what you hear") through ``SCStream`` with
``capturesAudio = True``. This backend taps it via pyobjc, downmixes to mono
float32 ``-1..1``, and feeds the shared :class:`MonoRingBuffer` — the same shape
the analyzer already consumes.

**Requirements & caveats**

* macOS 13.0+ and the pyobjc ScreenCaptureKit frameworks (mac requirements only).
* **Screen Recording permission** (System Settings → Privacy & Security → Screen
  Recording): macOS gates system-audio capture behind it. The first run prompts.
* Everything is **fail-soft**: any missing framework, denied permission, or API
  error sets ``status = ERROR`` and never raises, so the app falls back to the
  BlackHole/mic path (see ``audio.source_factory``).

Compared to BlackHole (PR3), this needs no virtual driver install — but requires
the permission. BlackHole stays the recommended, dependency-free-of-permission
route; this is the "just works, no install" option.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import numpy as np
from numpy.typing import NDArray

from audio_visualizer.audio.ring_buffer import MonoRingBuffer
from audio_visualizer.audio.source import SourceStatus
from audio_visualizer.config import RING_BUFFER_SECONDS

logger = logging.getLogger(__name__)

# macOS AudioFormatFlag: samples stored as separate per-channel buffers.
_FLAG_NON_INTERLEAVED = 1 << 5
# CMSampleBuffer flag: keep the returned AudioBufferList 16-byte aligned.
_ASSURE_16_BYTE_ALIGNMENT = 1
# Content-fetch / stream-start handshake timeout (seconds).
_HANDSHAKE_TIMEOUT = 6.0
# Requested capture format; ScreenCaptureKit delivers float32.
_REQUEST_SAMPLE_RATE = 48000
_REQUEST_CHANNELS = 2


def downmix_pcm_float32(data: bytes, channels: int, interleaved: bool) -> NDArray[np.float32]:
    """Reinterpret raw float32 PCM ``data`` and average channels down to mono.

    ``interleaved`` selects the memory layout: ``LRLR…`` (interleaved) vs
    ``LLL…RRR…`` (non-interleaved / planar). Ragged tails are trimmed so the
    reshape is always valid.
    """
    samples = np.frombuffer(data, dtype=np.float32)
    ch = max(1, int(channels))
    if ch == 1 or samples.size < ch:
        return samples.astype(np.float32, copy=True)

    frames = samples.size // ch
    usable = frames * ch
    block = samples[:usable]
    if interleaved:
        return block.reshape(frames, ch).mean(axis=1).astype(np.float32)
    return block.reshape(ch, frames).mean(axis=0).astype(np.float32)


def native_capture_available() -> bool:
    """True when ScreenCaptureKit + CoreMedia can be imported (macOS 13+ pyobjc)."""
    try:
        import CoreMedia  # noqa: F401
        import ScreenCaptureKit  # noqa: F401

        return True
    except Exception:
        logger.debug("ScreenCaptureKit unavailable", exc_info=True)
        return False


class MacSystemAudioSource:
    """System-audio capture via ScreenCaptureKit (``SCStream`` audio output)."""

    def __init__(self, ring_seconds: float = RING_BUFFER_SECONDS) -> None:
        self.sample_rate = _REQUEST_SAMPLE_RATE
        self.channels = 1
        self.device_name = "System Audio (native tap)"
        self.status = SourceStatus.STOPPED

        self._ring_seconds = ring_seconds
        self._ring = MonoRingBuffer(int(self.sample_rate * ring_seconds))
        self._stream: Any = None
        self._output: Any = None

    # -- lifecycle ------------------------------------------------------------
    def start(self) -> None:
        try:
            self._start_stream()
            self.status = SourceStatus.RUNNING
            logger.info("Native system-audio capture started (ScreenCaptureKit)")
        except Exception:
            logger.exception("Failed to start ScreenCaptureKit capture")
            self.status = SourceStatus.ERROR
            self._teardown()

    def _start_stream(self) -> None:
        import ScreenCaptureKit as sck

        content = self._fetch_shareable_content(sck)
        displays = list(content.displays())
        if not displays:
            raise RuntimeError("No displays available for ScreenCaptureKit capture")

        cfg = sck.SCStreamConfiguration.alloc().init()
        cfg.setCapturesAudio_(True)
        cfg.setSampleRate_(_REQUEST_SAMPLE_RATE)
        cfg.setChannelCount_(_REQUEST_CHANNELS)
        # Avoid capturing our own output (prevents a feedback loop when the app
        # itself makes sound). Older systems may lack the setter — ignore then.
        try:
            cfg.setExcludesCurrentProcessAudio_(True)
        except Exception:  # pragma: no cover - version dependent
            logger.debug("excludesCurrentProcessAudio unavailable", exc_info=True)

        filt = sck.SCContentFilter.alloc().initWithDisplay_excludingWindows_(displays[0], [])

        self._ring = MonoRingBuffer(int(_REQUEST_SAMPLE_RATE * self._ring_seconds))
        self._output = _AudioStreamOutput.alloc().initWithSink_(self._ring)
        self._stream = sck.SCStream.alloc().initWithFilter_configuration_delegate_(filt, cfg, None)

        ok, err = self._stream.addStreamOutput_type_sampleHandlerQueue_error_(
            self._output, sck.SCStreamOutputTypeAudio, None, None
        )
        if not ok:
            raise RuntimeError(f"addStreamOutput failed: {err}")

        self._await_start()

    def _fetch_shareable_content(self, sck: Any) -> Any:
        """Synchronously fetch shareable content (async API + an event gate)."""
        result: dict[str, Any] = {}
        done = threading.Event()

        def handler(content: Any, error: Any) -> None:
            result["content"] = content
            result["error"] = error
            done.set()

        sck.SCShareableContent.getShareableContentWithCompletionHandler_(handler)
        if not done.wait(_HANDSHAKE_TIMEOUT):
            raise TimeoutError("Timed out fetching ScreenCaptureKit content")
        if result.get("error") is not None or result.get("content") is None:
            raise RuntimeError(f"Shareable content error: {result.get('error')}")
        return result["content"]

    def _await_start(self) -> None:
        """Start the stream and block until the completion handler fires."""
        done = threading.Event()
        result: dict[str, Any] = {}

        def handler(error: Any) -> None:
            result["error"] = error
            done.set()

        self._stream.startCaptureWithCompletionHandler_(handler)
        if not done.wait(_HANDSHAKE_TIMEOUT):
            raise TimeoutError("Timed out starting ScreenCaptureKit capture")
        if result.get("error") is not None:
            raise RuntimeError(f"startCapture error: {result['error']}")

    def stop(self) -> None:
        self._teardown()
        self.status = SourceStatus.STOPPED

    def _teardown(self) -> None:
        stream = self._stream
        self._stream = None
        self._output = None
        if stream is None:
            return
        try:
            stream.stopCaptureWithCompletionHandler_(lambda error: None)
        except Exception:  # pragma: no cover - defensive
            logger.debug("Error stopping ScreenCaptureKit stream", exc_info=True)

    # -- consumer -------------------------------------------------------------
    def read_latest(self, num_samples: int) -> NDArray[np.float32] | None:
        return self._ring.read_latest(num_samples)


def _make_output_class() -> Any:
    """Build the ``SCStreamOutput`` delegate class lazily (needs pyobjc at import).

    Defining it inside a function keeps this module importable on any OS and on
    macOS without the pyobjc frameworks — the class is only created when native
    capture is actually used.
    """
    import CoreMedia
    import objc
    from Foundation import NSObject

    class _AudioStreamOutput(NSObject):
        """Receives audio ``CMSampleBuffer``s and writes mono into the ring."""

        def initWithSink_(self, sink: MonoRingBuffer) -> Any:  # noqa: N802
            self = objc.super(_AudioStreamOutput, self).init()
            if self is None:
                return None
            self._sink = sink
            return self

        def stream_didOutputSampleBuffer_ofType_(  # noqa: N802
            self, stream: Any, sample_buffer: Any, output_type: int
        ) -> None:
            try:
                mono = _extract_mono(CoreMedia, sample_buffer)
                if mono is not None and mono.size:
                    self._sink.write(mono)
            except Exception:  # pragma: no cover - never raise into ObjC
                logger.debug("audio sample extraction failed", exc_info=True)

        def stream_didStopWithError_(self, stream: Any, error: Any) -> None:  # noqa: N802
            logger.warning("ScreenCaptureKit stream stopped: %s", error)

    return _AudioStreamOutput


def _extract_mono(cm: Any, sample_buffer: Any) -> NDArray[np.float32] | None:
    """Pull mono float32 samples out of an audio ``CMSampleBuffer``."""
    channels, interleaved = _read_format(cm, sample_buffer)

    status, size_needed, _ = cm.CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer(
        sample_buffer, None, None, 0, None, None, _ASSURE_16_BYTE_ALIGNMENT, None
    )
    if status != 0 or size_needed <= 0:
        return None

    import CoreAudio

    n_buffers = channels if interleaved is False else 1
    abl = CoreAudio.AudioBufferList(max(1, n_buffers))
    status, _, block_buffer = cm.CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer(
        sample_buffer, None, abl, size_needed, None, None, _ASSURE_16_BYTE_ALIGNMENT, None
    )
    if status != 0 or block_buffer is None:
        return None

    length = int(cm.CMBlockBufferGetDataLength(block_buffer))
    if length <= 0:
        return None
    copy_status, data = cm.CMBlockBufferCopyDataBytes(block_buffer, 0, length, None)
    if copy_status != 0 or not data:
        return None
    return downmix_pcm_float32(bytes(data), channels, interleaved)


def _read_format(cm: Any, sample_buffer: Any) -> tuple[int, bool]:
    """Return ``(channels, interleaved)`` from the buffer's audio format.

    Defaults to stereo non-interleaved (ScreenCaptureKit's native shape) if the
    format description can't be read.
    """
    try:
        fmt = cm.CMSampleBufferGetFormatDescription(sample_buffer)
        asbd = cm.CMAudioFormatDescriptionGetStreamBasicDescription(fmt)
        channels = max(1, int(asbd.mChannelsPerFrame))
        interleaved = not bool(int(asbd.mFormatFlags) & _FLAG_NON_INTERLEAVED)
        return channels, interleaved
    except Exception:  # pragma: no cover - defensive
        logger.debug("Could not read audio format; assuming stereo planar", exc_info=True)
        return _REQUEST_CHANNELS, False


# Bind the delegate class name for ``alloc()`` in :meth:`MacSystemAudioSource.start`.
# Resolved lazily so import never requires pyobjc.
class _LazyOutput:
    _cls: Any = None

    def __getattr__(self, name: str) -> Any:
        if _LazyOutput._cls is None:
            _LazyOutput._cls = _make_output_class()
        return getattr(_LazyOutput._cls, name)


_AudioStreamOutput = _LazyOutput()
