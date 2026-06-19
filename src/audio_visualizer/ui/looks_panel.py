"""Modal panel to save and manage user looks ("My Looks").

This is the **Save/manage** affordance (opened from the ``Save…`` button); the
separate ``My Looks`` dropdown in the control bar is the load affordance. Here
the user names + saves the current look (create-new or update the active one),
and manages saved looks (load / duplicate / delete with a click-twice confirm).

Mirrors the other modals (dim backdrop, centered panel, click-outside/Esc to
close). Per-domain Background/Logo Local|Global, reorder, and export/import
arrive in a later 0B-b build.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from audio_visualizer.config import COLOR_BG, COLOR_TEXT, COLOR_TEXT_DIM, LOOK_NAME_MAX
from audio_visualizer.ui.style import STYLE, TEXT_PAD, draw_panel, fit_text
from audio_visualizer.ui.text_input import TextInput

_PANEL_W = 540
_ROW_H = 34
_PAD = 12
_GAP = 8
_LABEL_H = 22
_MAX_VISIBLE_ROWS = 7  # saved-look rows shown at once (wheel-scroll for more)


@dataclass
class LooksActions:
    """Callbacks the App wires to the looks store."""

    save_new: Callable[[str], None]
    update_active: Callable[[], None]
    load: Callable[[str], None]
    delete: Callable[[str], None]
    duplicate: Callable[[str], None]
    # Export the whole library to the companion file (returns a status message);
    # import merges a companion file in. ``library_path`` reports where that file
    # lives so the panel can show the current location. Defaulted so older
    # callers/tests that omit them keep working.
    export_library: Callable[[], str] = lambda: ""
    import_library: Callable[[], str] = lambda: ""
    library_path: Callable[[], str] = lambda: ""


@dataclass(frozen=True)
class _RowRects:
    """Interactive rects for one saved-look row."""

    look_id: str
    name: pygame.Rect
    dup: pygame.Rect
    delete: pygame.Rect


@dataclass(frozen=True)
class _PanelLayout:
    """Every interactive rect in the panel, computed once per frame."""

    panel: pygame.Rect
    name: pygame.Rect
    save_new: pygame.Rect
    update: pygame.Rect
    export: pygame.Rect
    import_: pygame.Rect
    io_info_y: int
    label_y: int
    rows: list[_RowRects]
    close: pygame.Rect


class LooksPanel:
    """Centered modal: name field + Save/Update, and a managed list of looks."""

    def __init__(self, actions: LooksActions) -> None:
        self._actions = actions
        self.open = False
        self._rows: list[tuple[str, str]] = []  # (look_id, name)
        self._active_id = ""
        self._active_name = ""
        self._name = TextInput(max_len=LOOK_NAME_MAX, placeholder="Name this look\u2026")
        self._scroll = 0
        self._confirm_delete_id = ""
        self._hover_key = ""  # which control the mouse is over (for highlight)
        self._status = ""  # last export/import result message (shown under the IO row)

    # -- state ----------------------------------------------------------------
    def set_state(self, rows: list[tuple[str, str]], active_id: str, active_name: str) -> None:
        """Refresh the saved-look list and the active look (called on open)."""
        self._rows = rows
        self._active_id = active_id
        self._active_name = active_name

    def toggle(self) -> None:
        self.open = not self.open
        if self.open:
            self._name.set_text(self._active_name)
            self._name.focused = True
            self._scroll = 0
            self._confirm_delete_id = ""
            self._status = ""

    def update(self, dt: float) -> None:
        if self.open:
            self._name.update(dt)

    # -- geometry -------------------------------------------------------------
    def _visible_rows(self) -> int:
        return min(_MAX_VISIBLE_ROWS, max(0, len(self._rows)))

    def _panel_rect(self, canvas: pygame.Rect) -> pygame.Rect:
        body = (
            _PAD
            + _ROW_H  # name field
            + _GAP
            + _ROW_H  # save / update row
            + _GAP
            + _ROW_H  # export / import row
            + _GAP
            + _LABEL_H * 2  # file location + last status lines
            + _GAP
            + _LABEL_H  # "Saved looks" label
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
        """Compute every interactive rect once (shared by input + draw)."""
        panel = self._panel_rect(canvas)
        x = panel.x + _PAD
        w = panel.width - _PAD * 2
        y = panel.y + _PAD
        name = pygame.Rect(x, y, w, _ROW_H)
        y += _ROW_H + _GAP
        half = (w - _GAP) // 2
        save_new = pygame.Rect(x, y, half, _ROW_H)
        update = pygame.Rect(x + half + _GAP, y, w - half - _GAP, _ROW_H)
        y += _ROW_H + _GAP
        export = pygame.Rect(x, y, half, _ROW_H)
        import_ = pygame.Rect(x + half + _GAP, y, w - half - _GAP, _ROW_H)
        y += _ROW_H + _GAP
        io_info_y = y
        y += _LABEL_H * 2 + _GAP
        label_y = y
        y += _LABEL_H
        list_rows: list[_RowRects] = []
        visible = self._rows[self._scroll : self._scroll + self._visible_rows()]
        for look_id, _name in visible:
            del_w, dup_w = 64, 64
            name_w = w - del_w - dup_w - _GAP * 2
            list_rows.append(
                _RowRects(
                    look_id,
                    pygame.Rect(x, y, name_w, _ROW_H),
                    pygame.Rect(x + name_w + _GAP, y, dup_w, _ROW_H),
                    pygame.Rect(x + name_w + dup_w + _GAP * 2, y, del_w, _ROW_H),
                )
            )
            y += _ROW_H
        close = pygame.Rect(x, panel.bottom - _PAD - _ROW_H, w, _ROW_H)
        return _PanelLayout(
            panel, name, save_new, update, export, import_, io_info_y, label_y, list_rows, close
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

        # The name field consumes typing; Enter saves (update if active, else new).
        submit = self._name.handle_event(event)
        if submit == "submit":
            self._submit_save()
            return True
        if event.type == pygame.TEXTINPUT or (
            event.type == pygame.KEYDOWN and event.key == pygame.K_BACKSPACE
        ):
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._handle_click(event.pos, lay)
        return False

    def _handle_click(self, pos: tuple[int, int], lay: _PanelLayout) -> bool:
        if lay.save_new.collidepoint(pos):
            self._submit_save(force_new=True)
            return True
        if self._active_id and lay.update.collidepoint(pos):
            self._actions.update_active()
            self.open = False
            return True
        if lay.export.collidepoint(pos):
            self._status = self._actions.export_library()
            return True
        if lay.import_.collidepoint(pos):
            self._status = self._actions.import_library()
            return True
        for row in lay.rows:
            if row.name.collidepoint(pos):
                self._actions.load(row.look_id)
                self.open = False
                return True
            if row.dup.collidepoint(pos):
                self._actions.duplicate(row.look_id)
                self._confirm_delete_id = ""
                return True
            if row.delete.collidepoint(pos):
                if self._confirm_delete_id == row.look_id:
                    self._actions.delete(row.look_id)
                    self._confirm_delete_id = ""
                else:
                    self._confirm_delete_id = row.look_id  # arm "Sure?" on first click
                return True
        if lay.close.collidepoint(pos):
            self.open = False
            return True
        if not lay.panel.collidepoint(pos):
            self.open = False
        return True

    def _submit_save(self, force_new: bool = False) -> None:
        name = self._name.text.strip()
        if not force_new and self._active_id:
            self._actions.update_active()
        else:
            self._actions.save_new(name)
        self.open = False

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
        title = font.render("My Looks", True, STYLE.accent)
        surface.blit(title, (panel.x + _PAD, panel.y - title.get_height() - 4))

        self._name.set_rect(lay.name)
        self._name.draw(surface, font)
        self._draw_button(surface, lay.save_new, "Save as new", font)
        update_label = (
            f"Update '{fit_text(font_small, self._active_name, 160)}'"
            if self._active_id
            else "Update (no look)"
        )
        self._draw_button(
            surface, lay.update, update_label, font_small, enabled=bool(self._active_id)
        )

        self._draw_button(surface, lay.export, "Export to file", font_small)
        self._draw_button(surface, lay.import_, "Import from file", font_small)

        location = self._actions.library_path()
        if location:
            loc = font_small.render(
                f"File: {fit_text(font_small, location, panel.width - _PAD * 2 - 44)}",
                True,
                COLOR_TEXT_DIM,
            )
            surface.blit(loc, (panel.x + _PAD, lay.io_info_y))
        if self._status:
            status = font_small.render(
                fit_text(font_small, self._status, panel.width - _PAD * 2), True, STYLE.accent
            )
            surface.blit(status, (panel.x + _PAD, lay.io_info_y + _LABEL_H))

        label = font_small.render("Saved looks", True, COLOR_TEXT_DIM)
        surface.blit(label, (panel.x + _PAD, lay.label_y))

        if not self._rows:
            empty = font_small.render("No saved looks yet.", True, COLOR_TEXT_DIM)
            surface.blit(empty, (panel.x + _PAD, lay.label_y + _LABEL_H + 4))
        for row in lay.rows:
            self._draw_row(surface, row, font_small)

        self._draw_button(surface, lay.close, "Close", font)

    def _draw_row(self, surface: pygame.Surface, row: _RowRects, font: pygame.font.Font) -> None:
        name = next((n for i, n in self._rows if i == row.look_id), row.look_id)
        active = row.look_id == self._active_id
        draw_panel(surface, row.name, accent_border=active)
        text = font.render(fit_text(font, name, row.name.width - TEXT_PAD * 2), True, COLOR_TEXT)
        surface.blit(text, text.get_rect(midleft=(row.name.x + TEXT_PAD, row.name.centery)))
        self._draw_button(surface, row.dup, "Dup", font)
        confirming = self._confirm_delete_id == row.look_id
        self._draw_button(surface, row.delete, "Sure?" if confirming else "Del", font)

    def _draw_button(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        font: pygame.font.Font,
        *,
        enabled: bool = True,
    ) -> None:
        draw_panel(surface, rect)
        color = COLOR_TEXT if enabled else COLOR_TEXT_DIM
        text = font.render(fit_text(font, label, rect.width - TEXT_PAD * 2), True, color)
        surface.blit(text, text.get_rect(center=rect.center))
