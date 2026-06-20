"""Modal "Beat Buttons" table: let the music auto-press actions (Phase 0B-c).

Opened from the ``Beat\u2026`` control-bar button (next to Shuffle). A master
**On/Off** toggle at the top turns the whole feature off without losing any
per-action settings. Each row is an
action (Rnd, Next) with two **dropdowns**: the **band** it listens to
(All/Bass/Mid/High) and its **sensitivity** (Off..Insane). Below the table, an
On/Off **toggle** for a small on-screen **indicator** plus a **dropdown** for its
position. Multi-choice controls use dropdowns (clearer than click-to-cycle); the
binary indicator stays a toggle. Mirrors the other modals (dim backdrop, centered
panel, click-outside/Esc to close). The App owns the live :class:`BeatTrigger`;
this panel only displays state and routes selections.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from audio_visualizer.config import (
    BEAT_ACTIONS,
    BEAT_BANDS,
    BEAT_FADE_CHOICES,
    BEAT_INDICATOR_OPACITY_CHOICES,
    BEAT_INDICATOR_POSITIONS,
    BEAT_INDICATOR_SHAPES,
    BEAT_SENSITIVITY_LABELS,
    COLOR_BG,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
)
from audio_visualizer.ui.dropdown import Dropdown
from audio_visualizer.ui.style import STYLE, TEXT_PAD, draw_panel, fit_text

_PANEL_W = 480
_ROW_H = 30
_PAD = 14
_GAP = 8
_LABEL_H = 22
_BAND_W = 92  # width of the band dropdown
_LEVEL_W = 108  # width of the sensitivity dropdown


@dataclass(frozen=True)
class _ActionRow:
    action_key: str
    label_rect: pygame.Rect
    band_rect: pygame.Rect
    level_rect: pygame.Rect


@dataclass(frozen=True)
class _PanelLayout:
    panel: pygame.Rect
    master: pygame.Rect
    rows: list[_ActionRow]
    indicator: pygame.Rect
    position: pygame.Rect
    shape: pygame.Rect
    opacity: pygame.Rect
    fade: pygame.Rect
    close: pygame.Rect


class BeatPanel:
    """Centered modal: per-action band + sensitivity dropdowns, plus indicator."""

    def __init__(
        self,
        set_level: Callable[[str, int], None],
        set_band: Callable[[str, str], None],
        toggle_indicator: Callable[[], None],
        set_position: Callable[[str], None],
        set_shape: Callable[[str], None],
        set_opacity: Callable[[str], None],
        set_fade: Callable[[str], None],
        toggle_enabled: Callable[[], None],
    ) -> None:
        self._set_level = set_level
        self._set_band = set_band
        self._toggle_indicator = toggle_indicator
        self._set_position = set_position
        self._toggle_enabled = toggle_enabled
        self.open = False
        self._enabled = True
        self._indicator_on = False
        self._hover_close = False

        # One band + one sensitivity dropdown per action.
        self._band_dd: dict[str, Dropdown] = {}
        self._level_dd: dict[str, Dropdown] = {}
        level_options = [(str(i), label) for i, label in enumerate(BEAT_SENSITIVITY_LABELS)]
        for key, _label in BEAT_ACTIONS:
            band = Dropdown(self._make_band_cb(key))
            band.set_options(list(BEAT_BANDS))
            self._band_dd[key] = band
            level = Dropdown(self._make_level_cb(key))
            level.set_options(level_options)
            self._level_dd[key] = level
        self._position_dd = Dropdown(set_position)
        self._position_dd.set_options(list(BEAT_INDICATOR_POSITIONS))
        self._shape_dd = Dropdown(set_shape, title="Shape")
        self._shape_dd.set_options(list(BEAT_INDICATOR_SHAPES))
        self._opacity_dd = Dropdown(set_opacity, title="Opacity")
        self._opacity_dd.set_options(
            [(key, label) for key, label, _v in BEAT_INDICATOR_OPACITY_CHOICES]
        )
        self._fade_dd = Dropdown(set_fade, title="Transition")
        self._fade_dd.set_options([(key, label) for key, label, _s in BEAT_FADE_CHOICES])

    def _make_band_cb(self, action: str) -> Callable[[str], None]:
        return lambda band: self._set_band(action, band)

    def _make_level_cb(self, action: str) -> Callable[[str], None]:
        return lambda index_str: self._set_level(action, int(index_str))

    def _dropdowns(self) -> list[Dropdown]:
        return [
            *self._band_dd.values(),
            *self._level_dd.values(),
            self._position_dd,
            self._shape_dd,
            self._opacity_dd,
            self._fade_dd,
        ]

    def set_state(
        self,
        levels: dict[str, int],
        bands: dict[str, str],
        indicator_on: bool,
        position_key: str,
        shape_key: str = "dot",
        opacity_key: str = "100",
        fade_key: str = "medium",
        enabled: bool = True,
    ) -> None:
        self._enabled = enabled
        for key, level in levels.items():
            if key in self._level_dd:
                self._level_dd[key].set_selected(str(level))
        for key, band in bands.items():
            if key in self._band_dd:
                self._band_dd[key].set_selected(band)
        self._indicator_on = indicator_on
        self._position_dd.set_selected(position_key)
        self._shape_dd.set_selected(shape_key)
        self._opacity_dd.set_selected(opacity_key)
        self._fade_dd.set_selected(fade_key)

    def toggle(self) -> None:
        self.open = not self.open
        if not self.open:
            self._close_dropdowns()

    def _close_dropdowns(self) -> None:
        for dd in self._dropdowns():
            dd.open = False

    # -- geometry -------------------------------------------------------------
    def _panel_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        body = (
            _PAD
            + _ROW_H  # master On/Off toggle
            + _GAP
            + _LABEL_H  # intro line
            + _GAP
            + len(BEAT_ACTIONS) * (_ROW_H + _GAP)
            + _GAP
            + _ROW_H  # indicator toggle + position
            + _GAP
            + _ROW_H  # shape + opacity
            + _GAP
            + _ROW_H  # transition fade
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
        master = pygame.Rect(x, panel.y + _PAD, w, _ROW_H)
        y = master.bottom + _GAP + _LABEL_H + _GAP
        rows: list[_ActionRow] = []
        for key, _label in BEAT_ACTIONS:
            level_rect = pygame.Rect(x + w - _LEVEL_W, y, _LEVEL_W, _ROW_H)
            band_rect = pygame.Rect(level_rect.x - _GAP - _BAND_W, y, _BAND_W, _ROW_H)
            label_rect = pygame.Rect(x, y, band_rect.x - _GAP - x, _ROW_H)
            rows.append(_ActionRow(key, label_rect, band_rect, level_rect))
            y += _ROW_H + _GAP
        y += _GAP
        half = (w - _GAP) // 2
        indicator = pygame.Rect(x, y, half, _ROW_H)
        position = pygame.Rect(indicator.right + _GAP, y, x + w - (indicator.right + _GAP), _ROW_H)
        y += _ROW_H + _GAP
        shape = pygame.Rect(x, y, half, _ROW_H)
        opacity = pygame.Rect(shape.right + _GAP, y, x + w - (shape.right + _GAP), _ROW_H)
        y += _ROW_H + _GAP
        fade = pygame.Rect(x, y, w, _ROW_H)
        close = pygame.Rect(x, panel.bottom - _PAD - _ROW_H, w, _ROW_H)
        return _PanelLayout(panel, master, rows, indicator, position, shape, opacity, fade, close)

    def _sync_widgets(self, lay: _PanelLayout) -> None:
        """Push current rects into the dropdowns and bound their open lists."""
        for row in lay.rows:
            self._band_dd[row.action_key].set_rect(row.band_rect)
            self._level_dd[row.action_key].set_rect(row.level_rect)
        self._position_dd.set_rect(lay.position)
        self._shape_dd.set_rect(lay.shape)
        self._opacity_dd.set_rect(lay.opacity)
        self._fade_dd.set_rect(lay.fade)
        right = lay.panel.right - _PAD
        for dd in self._dropdowns():
            dd.set_bound_right(right)

    # -- input ----------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event, canvas: pygame.Rect) -> bool:
        if not self.open:
            return False
        lay = self._layout(canvas)
        self._sync_widgets(lay)
        for dd in self._dropdowns():
            if dd.handle_event(event):
                if dd.open:  # keep only the just-opened dropdown expanded
                    for other in self._dropdowns():
                        if other is not dd:
                            other.open = False
                return True
        if event.type == pygame.MOUSEMOTION:
            self._hover_close = lay.close.collidepoint(event.pos)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._handle_click(event.pos, lay)
        return False

    def _handle_click(self, pos: tuple[int, int], lay: _PanelLayout) -> bool:
        if lay.close.collidepoint(pos):
            self.open = False
            self._close_dropdowns()
            return True
        if lay.master.collidepoint(pos):
            self._toggle_enabled()
            return True
        if lay.indicator.collidepoint(pos):
            self._toggle_indicator()
            return True
        if not lay.panel.collidepoint(pos):
            self.open = False
            self._close_dropdowns()
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
        self._sync_widgets(lay)
        panel = lay.panel
        draw_panel(surface, panel, accent_border=True)
        title = font.render("Beat Buttons", True, STYLE.accent)
        surface.blit(title, (panel.x + _PAD, panel.y - title.get_height() - 4))

        self._draw_button(
            surface,
            lay.master,
            f"Beat Buttons: {'On' if self._enabled else 'Off'}",
            font,
            active=self._enabled,
        )

        intro = font_small.render(
            "Let the music press a button for you (band \u2192 sensitivity):",
            True,
            COLOR_TEXT_DIM,
        )
        surface.blit(intro, (panel.x + _PAD, lay.master.bottom + _GAP))

        labels = {key: label for key, label in BEAT_ACTIONS}
        for row in lay.rows:
            self._draw_action_label(surface, row, labels[row.action_key], font)

        self._draw_button(
            surface,
            lay.indicator,
            f"Indicator: {'On' if self._indicator_on else 'Off'}",
            font,
            active=self._indicator_on,
        )

        hint = font_small.render(
            "Higher sensitivity = reacts to more beats. Off = disabled.",
            True,
            COLOR_TEXT_DIM,
        )
        surface.blit(hint, (panel.x + _PAD, lay.close.top - _LABEL_H))
        self._draw_button(surface, lay.close, "Close", font, hovered=self._hover_close)

        # Dropdowns last (closed first, open one on top) so their lists overlay all.
        dds = self._dropdowns()
        open_dd = next((dd for dd in dds if dd.open), None)
        for dd in dds:
            if dd is not open_dd:
                dd.draw(surface, font_small)
        if open_dd is not None:
            open_dd.draw(surface, font_small)

    def _draw_action_label(
        self,
        surface: pygame.Surface,
        row: _ActionRow,
        label: str,
        font: pygame.font.Font,
    ) -> None:
        on = self._enabled and (
            self._level_dd[row.action_key].current_label != BEAT_SENSITIVITY_LABELS[0]
        )
        color = COLOR_TEXT if on else COLOR_TEXT_DIM
        name = fit_text(font, label, row.label_rect.width - TEXT_PAD)
        text = font.render(name, True, color)
        surface.blit(
            text, text.get_rect(midleft=(row.label_rect.x + TEXT_PAD, row.label_rect.centery))
        )

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
