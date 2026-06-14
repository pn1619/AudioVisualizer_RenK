"""Windows-specific shims, each guarded so the module imports cleanly anywhere.

No pygame and no app logic here — just OS integration (DPI awareness, %APPDATA%).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from audio_visualizer.config import APP_NAME

logger = logging.getLogger(__name__)


def enable_dpi_awareness() -> None:
    """Make the process per-monitor DPI aware so pygame is crisp on scaled displays.

    No-op (and never raises) on non-Windows or if the call is unavailable.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        # 2 == PROCESS_PER_MONITOR_DPI_AWARE
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # pragma: no cover - best effort, platform dependent
        logger.debug("Could not set DPI awareness", exc_info=True)


def get_appdata_dir() -> Path:
    """Return the per-user app data directory, creating it if needed.

    Uses ``%APPDATA%\\AudioVisualizer`` on Windows, else a hidden dir under HOME.
    """
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".config"
    path = root / APP_NAME
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:  # pragma: no cover - extremely unlikely
        logger.warning("Could not create app data dir at %s", path)
    return path
