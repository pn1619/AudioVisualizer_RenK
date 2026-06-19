"""A minimal single-line text input (for naming/renaming user looks).

Reads printable characters from pygame ``TEXTINPUT`` events and handles
backspace/enter via ``KEYDOWN``. The owner positions it (``set_rect``), feeds it
events, and reads ``text``; pressing Enter returns a submit signal from
:meth:`handle_event`. Kept tiny and dependency-free like the other widgets.
"""

from __future__ import annotations

import pygame

from audio_visualizer.config import COLOR_TEXT, COLOR_TEXT_DIM
from audio_visualizer.ui.style import TEXT_PAD, draw_panel, fit_text


class TextInput:
    """An editable one-line field with a caret, placeholder, and length cap."""

    def __init__(self, max_len: int = 60, placeholder: str = "") -> None:
        self.text = ""
        self.placeholder = placeholder
        self._max_len = max_len
        self.focused = True  # owned by a modal, so it starts focused
        self.rect = pygame.Rect(0, 0, 0, 0)
        self._caret_phase = 0.0

    def set_rect(self, rect: pygame.Rect) -> None:
        self.rect = rect

    def set_text(self, text: str) -> None:
        self.text = (text or "")[: self._max_len]

    def update(self, dt: float) -> None:
        """Advance the caret blink timer."""
        self._caret_phase = (self._caret_phase + dt) % 1.0

    def handle_event(self, event: pygame.event.Event) -> str:
        """Process an event. Returns ``"submit"`` on Enter, else ``""``.

        Backspace deletes; printable characters append up to ``max_len``.
        """
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.focused = self.rect.collidepoint(event.pos)
            return ""
        if not self.focused:
            return ""
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return "submit"
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
        elif event.type == pygame.TEXTINPUT:
            if len(self.text) < self._max_len:
                self.text += event.text
                self.text = self.text[: self._max_len]
        return ""

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        draw_panel(surface, self.rect, accent_border=self.focused)
        show_placeholder = not self.text
        content = self.placeholder if show_placeholder else self.text
        color = COLOR_TEXT_DIM if show_placeholder else COLOR_TEXT
        fitted = fit_text(font, content, self.rect.width - TEXT_PAD * 2)
        text = font.render(fitted, True, color)
        surface.blit(text, text.get_rect(midleft=(self.rect.x + TEXT_PAD, self.rect.centery)))
        # Blinking caret after the text while focused.
        if self.focused and self._caret_phase < 0.5:
            cx = self.rect.x + TEXT_PAD + (text.get_width() if not show_placeholder else 0) + 1
            cx = min(cx, self.rect.right - TEXT_PAD)
            pygame.draw.line(
                surface, COLOR_TEXT, (cx, self.rect.y + 6), (cx, self.rect.bottom - 6), 1
            )
