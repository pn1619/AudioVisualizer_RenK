"""Loads the UI fonts the user picks (modern monospace or sans).

We use pygame's ``SysFont`` with a comma-separated preference list so the first
installed family wins (e.g. Cascadia/Consolas for the terminal-style mono look).
If no system font resolves, we fall back to pygame's built-in font so the UI
always renders.
"""

from __future__ import annotations

import logging

import pygame

from audio_visualizer.config import (
    UI_FONT_DEFAULT,
    UI_FONT_FAMILIES,
    UI_FONT_SIZE,
    UI_FONT_SIZE_SMALL,
)

logger = logging.getLogger(__name__)


def get_ui_fonts(choice: str) -> tuple[pygame.font.Font, pygame.font.Font]:
    """Return ``(font, font_small)`` for the requested font ``choice``.

    ``choice`` is one of :data:`config.UI_FONTS` ("mono" or "sans"); an unknown
    value falls back to the default. Never raises.
    """
    families = UI_FONT_FAMILIES.get(choice) or UI_FONT_FAMILIES[UI_FONT_DEFAULT]
    try:
        main = pygame.font.SysFont(families, UI_FONT_SIZE)
        small = pygame.font.SysFont(families, UI_FONT_SIZE_SMALL)
    except Exception:  # extremely defensive: a font backend hiccup must not crash
        logger.warning("SysFont %r failed; using the built-in font", families, exc_info=True)
        main = pygame.font.Font(None, UI_FONT_SIZE + 5)
        small = pygame.font.Font(None, UI_FONT_SIZE_SMALL + 5)
    return main, small
