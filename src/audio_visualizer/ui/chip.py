"""A small labeled value box that can optionally be clicked to type a new value.

By default a :class:`Chip` is a read-only display (e.g. ``"Sens 1.50"``). Give it an
``on_submit`` callback and it becomes editable: clicking focuses it, the user types a
number, and Enter (or clicking away) submits the typed text. Parsing/validation lives
in the callback, so an invalid entry can simply be ignored — the chip never crashes.
"""

from __future__ import annotations

from collections.abc import Callable

import pygame

from audio_visualizer.config import COLOR_TEXT
from audio_visualizer.ui.style import TEXT_PAD, draw_panel, fit_text

_ALLOWED = "0123456789.-"
_MAX_LEN = 8


class Chip:
    """A value box; read-only unless given ``on_submit`` (then click-to-edit)."""

    def __init__(self, text: str = "", on_submit: Callable[[str], None] | None = None) -> None:
        self.text = text
        self.prefix = ""  # shown before the typed buffer while editing (e.g. "Sens ")
        self.rect = pygame.Rect(0, 0, 0, 0)
        self._on_submit = on_submit
        self.editing = False
        self._buffer = ""

    @property
    def editable(self) -> bool:
        return self._on_submit is not None

    def set_rect(self, rect: pygame.Rect) -> None:
        self.rect = rect

    def begin_edit(self) -> None:
        if self.editable:
            self.editing = True
            self._buffer = ""

    def cancel_edit(self) -> None:
        self.editing = False
        self._buffer = ""

    def _commit(self) -> None:
        buf = self._buffer.strip()
        self.editing = False
        self._buffer = ""
        if self._on_submit is not None and buf:
            self._on_submit(buf)  # callback parses/validates; bad input is ignored

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Route one event. Returns True when consumed (so callers stop here)."""
        if not self.editable:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.begin_edit()
                return True
            if self.editing:  # clicking elsewhere commits what was typed
                self._commit()
            return False
        if not self.editing:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._commit()
            elif event.key == pygame.K_ESCAPE:
                self.cancel_edit()
            elif event.key == pygame.K_BACKSPACE:
                self._buffer = self._buffer[:-1]
            return True  # swallow all keys while editing so shortcuts don't fire
        if event.type == pygame.TEXTINPUT:
            for ch in event.text:
                if ch in _ALLOWED and len(self._buffer) < _MAX_LEN:
                    self._buffer += ch
            return True
        return False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        draw_panel(surface, self.rect, accent_border=True)
        shown = f"{self.prefix}{self._buffer}_" if self.editing else self.text
        label = fit_text(font, shown, self.rect.width - TEXT_PAD * 2)
        text = font.render(label, True, COLOR_TEXT)
        surface.blit(text, text.get_rect(center=self.rect.center))
