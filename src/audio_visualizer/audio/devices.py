"""Enumerate selectable audio sources (WASAPI loopback + real inputs).

This is a *capture* concern: it pokes ``pyaudiowpatch`` directly and is never
imported by ``app.py`` or the analyzer. ``LoopbackSource`` uses
:func:`find_device_info` to open a chosen device; the UI uses
:func:`list_sources` to offer the choices.

Everything is defensive — any failure yields an empty list (or ``None``)
rather than raising, so the app can fall back to the default device.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceInfo:
    """A user-selectable capture source.

    ``id`` is the stable identifier we persist (the device *name*, since device
    indices are not stable across sessions/replugs). ``kind`` distinguishes a
    render endpoint's loopback ("what you hear") from a real input ("the mic").
    """

    id: str
    name: str
    kind: str  # "loopback" | "input"
    is_default: bool


def _iter_raw(pa: Any, wasapi_type: int) -> list[tuple[dict, str]]:
    """Return ``(raw_device_info, kind)`` for every distinct selectable device.

    Loopback endpoints come first (system audio of each speaker/headphone/HDMI
    output), then real WASAPI inputs (microphone / line-in). Duplicate names are
    collapsed so the same endpoint isn't listed twice.
    """
    out: list[tuple[dict, str]] = []
    seen: set[str] = set()

    try:
        loopbacks = pa.get_loopback_device_info_generator()
    except Exception:  # pragma: no cover - defensive
        loopbacks = []
    for info in loopbacks:
        name = str(info.get("name", ""))
        if not name or name in seen:
            continue
        seen.add(name)
        out.append((info, "loopback"))

    wasapi_index: int | None = None
    try:
        wasapi_index = int(pa.get_host_api_info_by_type(wasapi_type)["index"])
    except Exception:  # pragma: no cover - defensive
        wasapi_index = None

    try:
        count = int(pa.get_device_count())
    except Exception:  # pragma: no cover - defensive
        count = 0
    for i in range(count):
        try:
            info = pa.get_device_info_by_index(i)
        except Exception:  # pragma: no cover - defensive
            continue
        if info.get("isLoopbackDevice"):
            continue
        if int(info.get("maxInputChannels", 0)) <= 0:
            continue
        if wasapi_index is not None and info.get("hostApi") != wasapi_index:
            continue
        name = str(info.get("name", ""))
        if not name or name in seen:
            continue
        seen.add(name)
        out.append((info, "input"))
    return out


def list_sources() -> list[SourceInfo]:
    """List selectable sources, or ``[]`` if enumeration is unavailable."""
    try:
        import pyaudiowpatch as pyaudio
    except Exception:  # pragma: no cover - import guarded for headless/CI
        logger.debug("pyaudiowpatch unavailable; no selectable sources", exc_info=True)
        return []

    pa = pyaudio.PyAudio()
    try:
        default_name = ""
        try:
            default_name = str(pa.get_default_wasapi_loopback().get("name", ""))
        except Exception:  # pragma: no cover - defensive
            logger.debug("No default loopback while enumerating", exc_info=True)
        sources: list[SourceInfo] = []
        for info, kind in _iter_raw(pa, pyaudio.paWASAPI):
            name = str(info.get("name", ""))
            sources.append(SourceInfo(name, name, kind, name == default_name))
        return sources
    except Exception:
        logger.exception("Failed to enumerate audio sources")
        return []
    finally:
        try:
            pa.terminate()
        except Exception:  # pragma: no cover - defensive
            pass


def find_device_info(pa: Any, name: str, wasapi_type: int) -> dict | None:
    """Return the raw pyaudio device dict whose name matches ``name``, or ``None``.

    Used by :class:`LoopbackSource` to open a previously selected device; the
    caller already owns the ``PyAudio`` handle.
    """
    if not name:
        return None
    for info, _kind in _iter_raw(pa, wasapi_type):
        if str(info.get("name", "")) == name:
            return info
    return None
