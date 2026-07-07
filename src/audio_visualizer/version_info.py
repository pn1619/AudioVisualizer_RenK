"""Platform-aware app version selection (Windows vs macOS lines)."""

from __future__ import annotations

import sys

from audio_visualizer.config import APP_VERSION, APP_VERSION_MAC


def app_version() -> str:
    """Return the version string for the running platform.

    Windows builds use ``APP_VERSION`` (``00``–``09`` ``PP`` line). macOS builds use
    ``APP_VERSION_MAC`` (``A0``–``F0`` line). See ``plan/git-and-versioning.md`` §3.1.
    """
    if sys.platform == "darwin":
        return APP_VERSION_MAC
    return APP_VERSION
