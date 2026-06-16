"""Locate bundled asset files in both dev and frozen (PyInstaller) runs.

Assets live in ``audio_visualizer/assets/``. When frozen, PyInstaller unpacks
them under ``sys._MEIPASS``; in dev they sit next to this module. Lookups never
raise — a missing asset returns ``None`` so callers degrade gracefully.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_ASSETS_SUBDIR = "assets"


def _candidate_dirs() -> list[Path]:
    """Directories that may hold ``assets/`` (frozen bundle first, then dev tree)."""
    dirs: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        dirs.append(Path(meipass) / "audio_visualizer" / _ASSETS_SUBDIR)
        dirs.append(Path(meipass) / _ASSETS_SUBDIR)
    dirs.append(Path(__file__).resolve().parent / _ASSETS_SUBDIR)
    return dirs


def asset_path(name: str) -> Path | None:
    """Return the path to bundled asset ``name``, or ``None`` if not found."""
    for base in _candidate_dirs():
        candidate = base / name
        if candidate.is_file():
            return candidate
    logger.warning("Asset %r not found in %s", name, [str(d) for d in _candidate_dirs()])
    return None
