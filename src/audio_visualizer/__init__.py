"""Windows system-audio visualizer (WASAPI loopback + pygame).

Importing this package sets ``PYGAME_HIDE_SUPPORT_PROMPT`` before pygame is ever
imported, so the library's stdout banner never pollutes our output or logs.
"""

from __future__ import annotations

import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from audio_visualizer.config import APP_VERSION  # noqa: E402

__all__ = ["APP_VERSION"]
