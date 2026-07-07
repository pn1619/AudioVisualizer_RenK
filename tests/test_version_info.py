"""Platform-specific app version strings."""

from __future__ import annotations

import sys

import pytest

from audio_visualizer.config import APP_VERSION, APP_VERSION_MAC
from audio_visualizer.version_info import app_version


def test_app_version_windows_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-macOS platforms report the Windows canonical version."""
    monkeypatch.setattr(sys, "platform", "win32")
    assert app_version() == APP_VERSION


def test_app_version_mac_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """macOS reports the separate mac port version line."""
    monkeypatch.setattr(sys, "platform", "darwin")
    assert app_version() == APP_VERSION_MAC


def test_mac_version_uses_a_line_prefix() -> None:
    """macOS PP field starts with A–F (hex platform family)."""
    prefix = APP_VERSION_MAC.split(".", 1)[0][0].upper()
    assert prefix in "ABCDEF"


def test_windows_version_uses_zero_line_prefix() -> None:
    """Windows PP field starts with 0–9."""
    prefix = APP_VERSION.split(".", 1)[0][0]
    assert prefix in "0123456789"
