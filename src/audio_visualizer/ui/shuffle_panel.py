"""Modal panel for auto-cycle ("shuffle") settings (Phase 0B-c).

Opened from the ``Shuffle…`` button in the control bar. Holds the on/off toggle,
a Next (skip-ahead) button, the switch interval stepper, and a checklist of which
items are in the rotation — built-in **modes** and saved **looks** (★) (an empty
rotation means nothing auto-switches). Mirrors the other modals (dim backdrop,
centered panel, click-outside/Esc to close).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from audio_visualizer.config import COLOR_BG, COLOR_TEXT, COLOR_TEXT_DIM
from audio_visualizer.ui.style import STYLE, TEXT_PAD, draw_panel, fit_text

_PANEL_W = 460
_ROW_H = 34
_PAD = 12
_GAP = 8
_LABEL_H = 22
_MAX_VISIBLE_ROWS = 8  # mode rows shown at once (wheel-scroll for more)


@dataclass
class ShuffleActions:
    """Callbacks the App wires to the auto-cycle state."""

    toggle_auto: Callable[[], None]
    shuffle_next: Callable[[], None]
    interval_down: Callable[[], None]
    interval_up: Callable[[], None]
    fade_down: Callable[[], None]
    fade_up: Callable[[], None]
    toggle_item: Callable[[str], None]
    set_all: Callable[[bool], None]
    toggle_random_options: Callable[[], None]


@dataclass(frozen=True)
class _ItemRow:
    """Interactive rect for one rotation-item checkbox row (mode or look)."""

    item_key: str
    rect: pygame.Rect


@dataclass(frozen=True)
class _PanelLayout:
    """Every interactive rect in the panel, computed once per frame."""

    panel: pygame.Rect
    auto: pygame.Rect
    next_btn: pygame.Rect
    interval_down: pygame.Rect
    interval_chip: pygame.Rect
    interval_up: pygame.Rect
    fade_down: pygame.Rect
    fade_chip: pygame.Rect
    fade_up: pygame.Rect
    random_opts: pygame.Rect
    label_y: int
    all_btn: pygame.Rect
    none_btn: pygame.Rect
    rows: list[_ItemRow]
    close: pygame.Rect


class ShufflePanel:
    """Centered modal: Auto toggle + interval stepper + mode rotation checklist."""

    def __init__(self, actions: ShuffleActions) -> None:
        self._actions = actions
        self.open = False
        self._rows: list[tuple[str, str, bool]] = []  # (item_key, label, in_pool)
        self._interval_label = ""
        self._auto_on = False
        self._random_options_on = False
        self._fade_label = ""
        self._scroll = 0

    # -- state ----------------------------------------------------------------
    def set_state(
        self,
        rows: list[tuple[str, str, bool]],
        interval_label: str,
        auto_on: bool,
        random_options_on: bool = False,
        fade_label: str = "",
    ) -> None:
        """Refresh the item checklist, interval/fade text, and toggles (each frame)."""
        self._rows = rows
        self._interval_label = interval_label
        self._auto_on = auto_on
        self._random_options_on = random_options_on
        self._fade_label = fade_label

    def toggle(self) -> None:
        self.open = not self.open
        if self.open:
            self._scroll = 0

    # -- geometry -------------------------------------------------------------
    def _visible_rows(self) -> int:
        return min(_MAX_VISIBLE_ROWS, max(0, len(self._rows)))

    def _panel_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        body = (
            _PAD
            + _ROW_H  # auto toggle
            + _GAP
            + _ROW_H  # interval stepper
            + _GAP
            + _ROW_H  # fade stepper
            + _GAP
            + _ROW_H  # randomize-options toggle
            + _GAP
            + _LABEL_H  # "Modes in rotation" label + All/None
            + self._visible_rows() * _ROW_H
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
        y = panel.y + _PAD
        next_w = 110
        auto = pygame.Rect(x, y, w - next_w - _GAP, _ROW_H)
        next_btn = pygame.Rect(auto.right + _GAP, y, next_w, _ROW_H)
        y += _ROW_H + _GAP
        step = 40
        interval_down = pygame.Rect(x, y, step, _ROW_H)
        interval_up = pygame.Rect(panel.right - _PAD - step, y, step, _ROW_H)
        interval_chip = pygame.Rect(
            interval_down.right + _GAP,
            y,
            interval_up.x - interval_down.right - _GAP * 2,
            _ROW_H,
        )
        y += _ROW_H + _GAP
        fade_down = pygame.Rect(x, y, step, _ROW_H)
        fade_up = pygame.Rect(panel.right - _PAD - step, y, step, _ROW_H)
        fade_chip = pygame.Rect(
            fade_down.right + _GAP, y, fade_up.x - fade_down.right - _GAP * 2, _ROW_H
        )
        y += _ROW_H + _GAP
        random_opts = pygame.Rect(x, y, w, _ROW_H)
        y += _ROW_H + _GAP
        label_y = y
        all_w = 60
        all_btn = pygame.Rect(panel.right - _PAD - all_w * 2 - _GAP, y - 4, all_w, _LABEL_H)
        none_btn = pygame.Rect(panel.right - _PAD - all_w, y - 4, all_w, _LABEL_H)
        y += _LABEL_H
        rows: list[_ItemRow] = []
        visible = self._rows[self._scroll : self._scroll + self._visible_rows()]
        for item_key, _label, _on in visible:
            rows.append(_ItemRow(item_key, pygame.Rect(x, y, w, _ROW_H)))
            y += _ROW_H
        close = pygame.Rect(x, panel.bottom - _PAD - _ROW_H, w, _ROW_H)
        return _PanelLayout(
            panel=panel,
            auto=auto,
            next_btn=next_btn,
            interval_down=interval_down,
            interval_chip=interval_chip,
            interval_up=interval_up,
            fade_down=fade_down,
            fade_chip=fade_chip,
            fade_up=fade_up,
            random_opts=random_opts,
            label_y=label_y,
            all_btn=all_btn,
            none_btn=none_btn,
            rows=rows,
            close=close,
        )

    # -- input ----------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event, canvas: pygame.Rect) -> bool:
        if not self.open:
            return False
        lay = self._layout(canvas)
        if event.type == pygame.MOUSEWHEEL:
            self._scroll = max(
                0, min(self._scroll - event.y, max(0, len(self._rows) - self._visible_rows()))
            )
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._handle_click(event.pos, lay)
        return False

    def _handle_click(self, pos: tuple[int, int], lay: _PanelLayout) -> bool:
        if lay.auto.collidepoint(pos):
            self._actions.toggle_auto()
            return True
        if lay.next_btn.collidepoint(pos):
            self._actions.shuffle_next()
            return True
        if lay.interval_down.collidepoint(pos):
            self._actions.interval_down()
            return True
        if lay.interval_up.collidepoint(pos):
            self._actions.interval_up()
            return True
        if lay.fade_down.collidepoint(pos):
            self._actions.fade_down()
            return True
        if lay.fade_up.collidepoint(pos):
            self._actions.fade_up()
            return True
        if lay.random_opts.collidepoint(pos):
            self._actions.toggle_random_options()
            return True
        if lay.all_btn.collidepoint(pos):
            self._actions.set_all(True)
            return True
        if lay.none_btn.collidepoint(pos):
            self._actions.set_all(False)
            return True
        for row in lay.rows:
            if row.rect.collidepoint(pos):
                self._actions.toggle_item(row.item_key)
                return True
        if lay.close.collidepoint(pos):
            self.open = False
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
        title = font.render("Shuffle", True, STYLE.accent)
        surface.blit(title, (panel.x + _PAD, panel.y - title.get_height() - 4))

        self._draw_button(
            surface,
            lay.auto,
            f"Auto-cycle: {'On' if self._auto_on else 'Off'}",
            font,
            active=self._auto_on,
        )
        self._draw_button(surface, lay.next_btn, "Next \u23ed", font)
        self._draw_button(surface, lay.interval_down, "\u2212", font)
        self._draw_button(surface, lay.interval_chip, self._interval_label, font)
        self._draw_button(surface, lay.interval_up, "+", font)
        self._draw_button(surface, lay.fade_down, "\u2212", font)
        self._draw_button(surface, lay.fade_chip, self._fade_label, font)
        self._draw_button(surface, lay.fade_up, "+", font)
        self._draw_button(
            surface,
            lay.random_opts,
            f"Randomize mode options: {'On' if self._random_options_on else 'Off'}",
            font,
            active=self._random_options_on,
        )

        label = font_small.render("In rotation (\u2605 = saved look)", True, COLOR_TEXT_DIM)
        surface.blit(label, (panel.x + _PAD, lay.label_y))
        self._draw_button(surface, lay.all_btn, "All", font_small)
        self._draw_button(surface, lay.none_btn, "None", font_small)

        for row in lay.rows:
            self._draw_item_row(surface, row, font)

        self._draw_button(surface, lay.close, "Close", font)

    def _draw_item_row(
        self, surface: pygame.Surface, row: _ItemRow, font: pygame.font.Font
    ) -> None:
        name, on = next(
            ((n, o) for k, n, o in self._rows if k == row.item_key), (row.item_key, False)
        )
        draw_panel(surface, row.rect, accent_border=on)
        box = pygame.Rect(row.rect.x + TEXT_PAD, row.rect.centery - 8, 16, 16)
        draw_panel(surface, box, accent_fill=on)
        if on:
            check = font.render("\u2713", True, COLOR_TEXT)
            surface.blit(check, check.get_rect(center=box.center))
        text_x = box.right + TEXT_PAD
        label = fit_text(font, name, row.rect.right - text_x - TEXT_PAD)
        color = COLOR_TEXT if on else COLOR_TEXT_DIM
        text = font.render(label, True, color)
        surface.blit(text, text.get_rect(midleft=(text_x, row.rect.centery)))

    def _draw_button(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        font: pygame.font.Font,
        *,
        active: bool = False,
    ) -> None:
        draw_panel(surface, rect, accent_fill=active)
        text = font.render(fit_text(font, label, rect.width - TEXT_PAD * 2), True, COLOR_TEXT)
        surface.blit(text, text.get_rect(center=rect.center))
