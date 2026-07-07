"""Platform-aware audio source + device enumeration selection.

``app.py`` depends only on this factory and the :class:`AudioSource` interface —
never on a concrete capture backend. On Windows it wires WASAPI loopback
(:class:`audio.capture.LoopbackSource`); on macOS it wires PortAudio input
(:class:`audio.capture_mac.MacInputSource`). See ``plan/macos-port.md``.
"""

from __future__ import annotations

import sys

from audio_visualizer.audio.devices import SourceInfo
from audio_visualizer.audio.source import AudioSource


def create_source(device_id: str = "") -> AudioSource:
    """Return the capture source for the current platform.

    ``device_id`` is a persisted device *name* (empty = system default). Backends
    are imported lazily so neither platform pulls in the other's capture library.
    """
    if sys.platform == "darwin":
        from audio_visualizer.audio.capture_mac import MacInputSource

        return MacInputSource(device_id=device_id)

    from audio_visualizer.audio.capture import LoopbackSource

    return LoopbackSource(device_id=device_id)


def list_sources() -> list[SourceInfo]:
    """List selectable capture sources for the current platform (``[]`` if none)."""
    if sys.platform == "darwin":
        from audio_visualizer.audio import devices_mac

        return devices_mac.list_sources()

    from audio_visualizer.audio import devices

    return devices.list_sources()
