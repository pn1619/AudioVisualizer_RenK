"""Modal "Beat Buttons" table: let the music auto-press actions (Phase 0B-c).

Opened from the ``Beat\u2026`` control-bar button (next to Shuffle). Each row is an
action (Rnd, Next) with two clickable badges: the **band** it listens to
(All/Bass/Mid/High) and its **sensitivity** (Off..Max). Below the table, toggles for
a small on-screen **indicator** (and its position). Mirrors the other modals (dim
backdrop, centered panel, click-outside/Esc to close). The App owns the live
:class:`BeatTrigger`; this panel only displays state and routes the click actions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from audio_visualizer.config import (
    BEAT_ACTIONS,
    BEAT_BANDS,
    BEAT_SENSITIVITY_LABELS,
    COLOR_BG,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
)
from audio_visualizer.ui.style import STYLE, TEXT_PAD, draw_panel, fit_text

_PANEL_W = 480
_ROW_H = 40
_PAD = 14
_GAP = 8
_LABEL_H = 22
_BAND_W = 84  # width of the band badge
_LEVEL_W = 96  # width of the sensitivity badge

_BAND_LABELS = {key: label for key, label in BEAT_BANDS}


@dataclass(frozen=True)
class _ActionRow:
    action_key: str
    rect: pygame.Rect
    band_rect: pygame.Rect
    level_rect: pygame.Rect


@dataclass(frozen=True)
class _PanelLayout:
    panel: pygame.Rect
    rows: list[_ActionRow]
    indicator: pygame.Rect
    position: pygame.Rect
    close: pygame.Rect


class BeatPanel:
    """Centered modal: per-action band + sensitivity, plus indicator toggles."""

    def __init__(
        self,
        cycle_level: Callable[[str], None],
        cycle_band: Callable[[str], None],
        toggle_indicator: Callable[[], None],
        cycle_position: Callable[[], None],
    ) -> None:
        self._cycle_level = cycle_level
        self._cycle_band = cycle_band
        self._toggle_indicator = toggle_indicator
        self._cycle_position = cycle_position
        self.open = False
        self._levels: dict[str, int] = {key: 0 for key, _label in BEAT_ACTIONS}
        self._bands: dict[str, str] = {key: "all" for key, _label in BEAT_ACTIONS}
        self._indicator_on = False
        self._position_label = ""
        self._hover_close = False

    def set_state(
        self,
        levels: dict[str, int],
        bands: dict[str, str],
        indicator_on: bool,
        position_label: str,
    ) -> None:
        self._levels = dict(levels)
        self._bands = dict(bands)
        self._indicator_on = indicator_on
        self._position_label = position_label

    def toggle(self) -> None:
        self.open = not self.open

    # -- geometry -------------------------------------------------------------
    def _panel_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        body = (
            _PAD
            + _LABEL_H  # intro line
            + _GAP
            + len(BEAT_ACTIONS) * (_ROW_H + _GAP)
            + _GAP
            + _ROW_H  # indicator toggle
            + _GAP
            + _ROW_H  # position
            + _GAP
            + _LABEL_H  # hint
            + _GAP
            + _ROW_H  # close
            + _PAD
        )
        height = min(body, canvas.height - 2 * _PAD)
        rect = pygame.Rect(0, 0, min(_PANEL_W, canvas.width - 2 * _PAD), height)
        rect.center = canvas.center
        return rect

    def _layout(self, canvas: pygame.Rect) -> _PanelLayout:
        panel = self._panel_rect(canvas)
        x = panel.x + _PAD
        w = panel.width - _PAD * 2
        y = panel.y + _PAD + _LABEL_H + _GAP
        rows: list[_ActionRow] = []
        for key, _label in BEAT_ACTIONS:
            row = pygame.Rect(x, y, w, _ROW_H)
            level_rect = pygame.Rect(row.right - _LEVEL_W, y, _LEVEL_W, _ROW_H)
            band_rect = pygame.Rect(level_rect.x - _GAP - _BAND_W, y, _BAND_W, _ROW_H)
            rows.append(_ActionRow(key, row, band_rect, level_rect))
            y += _ROW_H + _GAP
        y += _GAP
        indicator = pygame.Rect(x, y, w, _ROW_H)
        y += _ROW_H + _GAP
        position = pygame.Rect(x, y, w, _ROW_H)
        close = pygame.Rect(x, panel.bottom - _PAD - _ROW_H, w, _ROW_H)
        return _PanelLayout(panel, rows, indicator, position, close)

    # -- input ----------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event, canvas: pygame.Rect) -> bool:
        if not self.open:
            return False
        lay = self._layout(canvas)
        if event.type == pygame.MOUSEMOTION:
            self._hover_close = lay.close.collidepoint(event.pos)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._handle_click(event.pos, lay)
        return False

    def _handle_click(self, pos: tuple[int, int], lay: _PanelLayout) -> bool:
        if lay.close.collidepoint(pos):
            self.open = False
            return True
        for row in lay.rows:
            if row.band_rect.collidepoint(pos):
                self._cycle_band(row.action_key)
                return True
            if row.level_rect.collidepoint(pos):
                self._cycle_level(row.action_key)
                return True
        if lay.indicator.collidepoint(pos):
            self._toggle_indicator()
            return True
        if lay.position.collidepoint(pos):
            self._cycle_position()
            return True
        if not lay.panel.collidepoint(pos):
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

        lay = self._layout(canvas)
        panel = lay.panel
        draw_panel(surface, panel, accent_border=True)
        title = font.render("Beat Buttons", True, STYLE.accent)
        surface.blit(title, (panel.x + _PAD, panel.y - title.get_height() - 4))

        intro = font_small.render(
            "Let the music press a button for you (band \u2192 sensitivity):",
            True,
            COLOR_TEXT_DIM,
        )
        surface.blit(intro, (panel.x + _PAD, panel.y + _PAD))

        labels = {key: label for key, label in BEAT_ACTIONS}
        for row in lay.rows:
            self._draw_action_row(surface, row, labels[row.action_key], font, font_small)

        self._draw_button(
            surface,
            lay.indicator,
            f"On-screen indicator: {'On' if self._indicator_on else 'Off'}",
            font,
            active=self._indicator_on,
        )
        self._draw_button(
            surface,
            lay.position,
            f"Indicator position: {self._position_label}",
            font,
            active=False,
        )

        hint = font_small.render(
            "Higher sensitivity = reacts to more beats. Off = disabled.",
            True,
            COLOR_TEXT_DIM,
        )
        surface.blit(hint, (panel.x + _PAD, lay.close.top - _LABEL_H))
        self._draw_button(surface, lay.close, "Close", font, hovered=self._hover_close)

    def _draw_action_row(
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
        name_w = row.band_rect.x - row.rect.x - TEXT_PAD * 2
        name = fit_text(font, label, name_w)
        color = COLOR_TEXT if on else COLOR_TEXT_DIM
        text = font.render(name, True, color)
        surface.blit(text, text.get_rect(midleft=(row.rect.x + TEXT_PAD, row.rect.centery)))
        self._draw_badge(
            surface,
            row.band_rect,
            _BAND_LABELS.get(self._bands.get(row.action_key, "all"), "All"),
            font_small,
            active=on,
        )
        self._draw_badge(
            surface, row.level_rect, BEAT_SENSITIVITY_LABELS[level], font_small, active=on
        )

    @staticmethod
    def _draw_badge(
        surface: pygame.Surface,
        rect: pygame.Rect,
        text: str,
        font: pygame.font.Font,
        *,
        active: bool,
    ) -> None:
        badge = pygame.Rect(rect.x, rect.centery - 13, rect.width, 26)
        draw_panel(surface, badge, accent_fill=active)
        label = font.render(text, True, COLOR_TEXT)
        surface.blit(label, label.get_rect(center=badge.center))

    @staticmethod
    def _draw_button(
        surface: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        font: pygame.font.Font,
        *,
        active: bool = False,
        hovered: bool = False,
    ) -> None:
        draw_panel(surface, rect, accent_fill=active, hovered=hovered)
        text = font.render(fit_text(font, label, rect.width - TEXT_PAD * 2), True, COLOR_TEXT)
        surface.blit(text, text.get_rect(center=rect.center))
