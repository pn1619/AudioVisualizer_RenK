"""Enumerate selectable macOS input sources via PortAudio (``sounddevice``).

Parallel to :mod:`audio.devices` (Windows/WASAPI). macOS has no loopback
endpoints, so every entry is a real **input**; a virtual device such as
BlackHole (or an aggregate device) is tagged ``kind="loopback"`` because the
user routes system audio through it (see ``plan/macos-port.md``).

Defensive throughout: any failure yields an empty list rather than raising, so
the app falls back to the default input.
"""

from __future__ import annotations

import logging

from audio_visualizer.audio.capture_mac_native import native_capture_available
from audio_visualizer.audio.devices import SourceInfo
from audio_visualizer.config import MAC_SYSTEM_AUDIO_SOURCE_ID

logger = logging.getLogger(__name__)

# Substrings that indicate a virtual/loopback-capable device (system audio).
_LOOPBACK_HINTS = ("blackhole", "loopback", "soundflower", "aggregate", "multi-output")


def _is_loopback_like(name: str) -> bool:
    """True when the device name looks like a system-audio routing device."""
    low = name.casefold()
    return any(hint in low for hint in _LOOPBACK_HINTS)


def list_sources() -> list[SourceInfo]:
    """List selectable inputs, or ``[]`` if enumeration is unavailable.

    Loopback-like devices (BlackHole, aggregates) are listed first so "what you
    hear" routing is easy to find, then real inputs (microphones).
    """
    native = _native_source_entry()

    try:
        import sounddevice as sd
    except Exception:  # pragma: no cover - import guarded for headless/CI
        logger.debug("sounddevice unavailable; no selectable sources", exc_info=True)
        return native

    try:
        default_index = -1
        try:
            default_index = int(sd.default.device[0])
        except Exception:  # pragma: no cover - defensive
            logger.debug("No default input while enumerating", exc_info=True)

        loopbacks: list[SourceInfo] = []
        inputs: list[SourceInfo] = []
        seen: set[str] = set()
        for idx, dev in enumerate(sd.query_devices()):
            if int(dev["max_input_channels"]) < 1:
                continue
            name = str(dev["name"])
            if not name or name in seen:
                continue
            seen.add(name)
            is_default = idx == default_index
            if _is_loopback_like(name):
                loopbacks.append(SourceInfo(name, name, "loopback", is_default))
            else:
                inputs.append(SourceInfo(name, name, "input", is_default))
        return native + loopbacks + inputs
    except Exception:
        logger.exception("Failed to enumerate macOS audio sources")
        return native


def _native_source_entry() -> list[SourceInfo]:
    """Return the ScreenCaptureKit tap as a selectable source when available.

    Listed first so the zero-install "what you hear" option is easy to find.
    Requires macOS 13+ and Screen Recording permission (granted on first use).
    """
    if not native_capture_available():
        return []
    return [
        SourceInfo(
            MAC_SYSTEM_AUDIO_SOURCE_ID,
            "System Audio (native tap)",
            "loopback",
            False,
        )
    ]


def has_loopback_device() -> bool:
    """True when a system-audio routing device (e.g. BlackHole) is available."""
    return any(s.kind == "loopback" for s in list_sources())
