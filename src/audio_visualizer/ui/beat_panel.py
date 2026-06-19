"""Modal "Beat Buttons" table: let the music auto-press actions (Phase 0B-c).

Opened from the ``Menu``. Each row is an action (Rnd, Next); clicking the row
cycles its sensitivity ``Off -> Low -> Med -> High -> Max -> Off``. A higher
sensitivity reacts to more beats and spaces fires more tightly; ``Off`` disables
it. Mirrors the other modals (dim backdrop, centered panel, click-outside/Esc to
close). The App owns the live :class:`BeatTrigger`; this panel only displays the
current levels and routes a "cycle this action" click.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from audio_visualizer.config import (
    BEAT_ACTIONS,
    BEAT_SENSITIVITY_LABELS,
    COLOR_BG,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
)
from audio_visualizer.ui.style import STYLE, TEXT_PAD, draw_panel, fit_text

_PANEL_W = 460
_ROW_H = 40
_PAD = 14
_GAP = 8
_LABEL_H = 22
_LEVEL_W = 150  # width of the sensitivity badge on the right of each row


@dataclass(frozen=True)
class _ActionRow:
    action_key: str
    rect: pygame.Rect


class BeatPanel:
    """Centered modal listing beat-triggerable actions + their sensitivity."""

    def __init__(self, cycle_action: Callable[[str], None]) -> None:
        self._cycle = cycle_action
        self.open = False
        # action_key -> sensitivity index (mirrors the App's BeatTrigger each frame).
        self._levels: dict[str, int] = {key: 0 for key, _label in BEAT_ACTIONS}
        self._hover_close = False

    def set_state(self, levels: dict[str, int]) -> None:
        self._levels = dict(levels)

    def toggle(self) -> None:
        self.open = not self.open

    # -- geometry -------------------------------------------------------------
    def _panel_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        body = (
            _PAD
            + _LABEL_H  # intro line
            + _GAP
            + len(BEAT_ACTIONS) * (_ROW_H + _GAP)
            + _LABEL_H  # hint line
            + _GAP
            + _ROW_H  # close
            + _PAD
        )
        height = min(body, canvas.height - 2 * _PAD)
        rect = pygame.Rect(0, 0, min(_PANEL_W, canvas.width - 2 * _PAD), height)
        rect.center = canvas.center
        return rect

    def _rows(self, panel: pygame.Rect) -> list[_ActionRow]:
        x = panel.x + _PAD
        w = panel.width - _PAD * 2
        y = panel.y + _PAD + _LABEL_H + _GAP
        rows: list[_ActionRow] = []
        for key, _label in BEAT_ACTIONS:
            rows.append(_ActionRow(key, pygame.Rect(x, y, w, _ROW_H)))
            y += _ROW_H + _GAP
        return rows

    def _close_rect(self, panel: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(
            panel.x + _PAD, panel.bottom - _PAD - _ROW_H, panel.width - _PAD * 2, _ROW_H
        )

    # -- input ----------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event, canvas: pygame.Rect) -> bool:
        if not self.open:
            return False
        panel = self._panel_rect(canvas)
        if event.type == pygame.MOUSEMOTION:
            self._hover_close = self._close_rect(panel).collidepoint(event.pos)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._handle_click(event.pos, panel)
        return False

    def _handle_click(self, pos: tuple[int, int], panel: pygame.Rect) -> bool:
        if self._close_rect(panel).collidepoint(pos):
            self.open = False
            return True
        for row in self._rows(panel):
            if row.rect.collidepoint(pos):
                self._cycle(row.action_key)
                return True
        if not panel.collidepoint(pos):
            self.open = False
        return True

    # -- draw -----------------------------------------------------------------
    def draw(
        self,
        surface: pygame.Surface,
        canvas: pygame.Rect,
        font: pygame.font.Font,
        font_small: pygame.font.Font,
    ) -> None:
        if not self.open:
            return
        dim = pygame.Surface(canvas.size, pygame.SRCALPHA)
        dim.fill((*COLOR_BG, 200))
        surface.blit(dim, canvas.topleft)

        panel = self._panel_rect(canvas)
        draw_panel(surface, panel, accent_border=True)
        title = font.render("Beat Buttons", True, STYLE.accent)
        surface.blit(title, (panel.x + _PAD, panel.y - title.get_height() - 4))

        intro = font_small.render("Let the music press a button for you:", True, COLOR_TEXT_DIM)
        surface.blit(intro, (panel.x + _PAD, panel.y + _PAD))

        labels = {key: label for key, label in BEAT_ACTIONS}
        for row in self._rows(panel):
            self._draw_row(surface, row, labels[row.action_key], font, font_small)

        hint = font_small.render(
            "Higher = reacts to more beats. Off = disabled.", True, COLOR_TEXT_DIM
        )
        surface.blit(hint, (panel.x + _PAD, self._close_rect(panel).top - _LABEL_H))

        self._draw_close(surface, panel, font)

    def _draw_row(
        self,
        surface: pygame.Surface,
        row: _ActionRow,
        label: str,
        font: pygame.font.Font,
        font_small: pygame.font.Font,
    ) -> None:
        level = self._levels.get(row.action_key, 0)
        on = level > 0
        draw_panel(surface, row.rect, accent_border=on)
        text_w = row.rect.width - _LEVEL_W - TEXT_PAD * 3
        name = fit_text(font, label, text_w)
        color = COLOR_TEXT if on else COLOR_TEXT_DIM
        text = font.render(name, True, color)
        surface.blit(text, text.get_rect(midleft=(row.rect.x + TEXT_PAD, row.rect.centery)))
        badge = pygame.Rect(
            row.rect.right - _LEVEL_W - TEXT_PAD, row.rect.centery - 13, _LEVEL_W, 26
        )
        draw_panel(surface, badge, accent_fill=on)
        level_text = font_small.render(BEAT_SENSITIVITY_LABELS[level], True, COLOR_TEXT)
        surface.blit(level_text, level_text.get_rect(center=badge.center))

    def _draw_close(
        self, surface: pygame.Surface, panel: pygame.Rect, font: pygame.font.Font
    ) -> None:
        rect = self._close_rect(panel)
        draw_panel(surface, rect, hovered=self._hover_close, accent_border=True)
        text = font.render("Close", True, COLOR_TEXT)
        surface.blit(text, text.get_rect(center=rect.center))
