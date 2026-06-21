"""Top control bar: two rows of controls + dropdowns, laid out and click-routed.

Row 1 holds global controls (capture, mode picker, sensitivity/smoothing/size/
speed with inline value chips). Row 2 holds the color-scheme dropdown plus one
dropdown per option exposed by the active visual mode.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from audio_visualizer.config import (
    COLOR_BAR,
    COLOR_BORDER,
    COLOR_SCHEME_LABELS,
    COLOR_SCHEMES,
    CONTROL_GAP,
    CONTROL_ROW_HEIGHT,
    SENS_BANDS,
)
from audio_visualizer.ui.button import Button
from audio_visualizer.ui.chip import Chip
from audio_visualizer.ui.dropdown import Dropdown
from audio_visualizer.ui.lock_toggle import LockToggle

_OPTION_W = 150  # width of the color + per-mode option dropdowns
_LOCK_W = 26  # width of a lock toggle
_LOCK_GAP = 2  # tight gap between a control and its trailing lock pin


@dataclass
class ControlActions:
    """Callbacks the control bar invokes (wired to the App)."""

    toggle_capture: Callable[[], None]
    prev_mode: Callable[[], None]
    next_mode: Callable[[], None]
    select_mode: Callable[[str], None]
    sensitivity_down: Callable[[], None]
    sensitivity_up: Callable[[], None]
    smoothing_down: Callable[[], None]
    smoothing_up: Callable[[], None]
    size_down: Callable[[], None]
    size_up: Callable[[], None]
    speed_down: Callable[[], None]
    speed_up: Callable[[], None]
    cycle_color_scheme: Callable[[], None]
    select_color: Callable[[str], None]
    option_change: Callable[[str, int], None]
    toggle_reduce_motion: Callable[[], None]
    open_logo_panel: Callable[[], None]
    open_about: Callable[[], None]
    toggle_fullscreen: Callable[[], None]
    quit: Callable[[], None]
    # Opens the Appearance panel (UI style + font). Defaulted so older callers/tests
    # that build ControlActions without it keep working.
    open_appearance: Callable[[], None] = lambda: None
    # Opens the Background panel (backdrop + reactivity + opacity). Defaulted likewise.
    open_background: Callable[[], None] = lambda: None
    # Opens the Foreground panel (overlay effects + intensity + direction). Defaulted likewise.
    open_foreground: Callable[[], None] = lambda: None
    # Opens the Source panel (selectable capture device). Defaulted likewise.
    open_source: Callable[[], None] = lambda: None
    # Selects a user look by id ("" -> None/Live). Defaulted likewise.
    select_look: Callable[[str], None] = lambda _id: None
    # Opens the Save/Manage Looks modal. Defaulted likewise.
    open_looks: Callable[[], None] = lambda: None
    # Toggles auto-cycle (shuffle) on/off. Defaulted likewise.
    toggle_auto: Callable[[], None] = lambda: None
    # Advances to the next rotation item now. Defaulted likewise.
    shuffle_next: Callable[[], None] = lambda: None
    # Steps back to the previously shown look (history navigation). Defaulted likewise.
    previous: Callable[[], None] = lambda: None
    # Jumps to a 1-based position in the look history (typed into the Prev/Next chip).
    history_goto: Callable[[str], None] = lambda _v: None
    # Opens the Shuffle settings modal (interval + mode/look pool). Defaulted likewise.
    open_shuffle: Callable[[], None] = lambda: None
    # Randomizes the current mode's options + global feel (no mode switch). Defaulted likewise.
    randomize_current: Callable[[], None] = lambda: None
    # Direct value entry from the editable chips (text -> parsed/clamped by the App;
    # invalid input is ignored, never raised). Defaulted likewise.
    set_sensitivity_value: Callable[[str], None] = lambda _s: None
    set_smoothing_value: Callable[[str], None] = lambda _s: None
    set_size_value: Callable[[str], None] = lambda _s: None
    set_speed_value: Callable[[str], None] = lambda _s: None
    # Toggle a randomize-lock: held items aren't re-rolled by Rnd/Next/auto. The
    # global variant takes a feel key (sensitivity/smoothing/size/speed); the option
    # variant takes a per-mode option key. Defaulted likewise.
    toggle_global_lock: Callable[[str], None] = lambda _k: None
    toggle_option_lock: Callable[[str], None] = lambda _k: None
    # Opens the Hotkeys reference modal. Defaulted likewise.
    open_hotkeys: Callable[[], None] = lambda: None
    # Opens the Beat Buttons modal (music auto-presses actions). Defaulted likewise.
    open_beat: Callable[[], None] = lambda: None
    # Selects which frequency band the Sensitivity gain targets (all/bass/mid/high).
    select_sens_band: Callable[[str], None] = lambda _b: None


@dataclass(frozen=True)
class OptionSpec:
    """A per-mode option to render as a dropdown (label + choices + selection)."""

    key: str
    label: str
    choice_labels: tuple[str, ...]
    current_index: int
    # Whether this option gets a lock toggle (only options Rnd actually re-rolls), and
    # whether it is currently locked. Defaulted so existing callers/tests still work.
    lockable: bool = False
    locked: bool = False


class ControlBar:
    """Lays out and renders the two-row control bar and routes input."""

    def __init__(self, actions: ControlActions, mode_options: list[tuple[str, str]]) -> None:
        self._actions = actions
        # Start/Stop, Fullscreen and Quit are grouped into one "Menu" action dropdown.
        self._menu = Dropdown(self._on_menu_select, static_label="Menu")
        self._prev = Button("<", actions.prev_mode)
        self._dropdown = Dropdown(actions.select_mode)
        self._dropdown.set_options(mode_options)
        self._next = Button(">", actions.next_mode)
        # Dice button: re-roll the current mode's options + global feel (no mode change).
        self._random = Button("Rnd", actions.randomize_current)

        # User looks ("My Looks"): a load dropdown + a Save/Manage button. Kept in
        # row 1 (global controls), distinct from the per-mode "Preset" dropdown in
        # row 2, so the two never read alike.
        self._looks = Dropdown(actions.select_look, title="My Looks")
        self._looks.set_options([("", "None / Live")])
        self._save_look = Button("Save\u2026", actions.open_looks)

        # Auto-cycle ("shuffle"): an on/off toggle, a Next (skip-ahead) button, and a
        # settings button (interval + which modes/looks are in the rotation). The
        # toggle paints accent-filled when on.
        self._auto = Button("Auto", actions.toggle_auto)
        # Prev/Next walk the session look history (browser-style back/forward); the
        # chip between them shows "pos/total" and is click-to-edit to jump.
        self._prev_item = Button("Prev", actions.previous)
        self._hist_chip = Chip(on_submit=actions.history_goto)
        self._next_item = Button("Next", actions.shuffle_next)
        self._shuffle = Button("Shuffle\u2026", actions.open_shuffle)
        # Beat Buttons: music auto-presses actions (opens the Beat modal).
        self._beat_btn = Button("Beat\u2026", actions.open_beat)

        # Compact steppers: [-] <Name value> [+]; the chip carries the name+value so
        # the tiny buttons stay unambiguous without long labels (which the wider
        # monospace UI font would otherwise truncate).
        minus, plus = "\u2212", "+"
        self._sens_down = Button(minus, actions.sensitivity_down)
        self._sens_chip = Chip(on_submit=actions.set_sensitivity_value)
        self._sens_up = Button(plus, actions.sensitivity_up)
        self._smooth_down = Button(minus, actions.smoothing_down)
        self._smooth_chip = Chip(on_submit=actions.set_smoothing_value)
        self._smooth_up = Button(plus, actions.smoothing_up)
        self._size_down = Button(minus, actions.size_down)
        self._size_chip = Chip(on_submit=actions.set_size_value)
        self._size_up = Button(plus, actions.size_up)
        self._speed_down = Button(minus, actions.speed_down)
        self._speed_chip = Chip(on_submit=actions.set_speed_value)
        self._speed_up = Button(plus, actions.speed_up)
        # Picks which band the Sensitivity gain targets; sits right after the Sens lock.
        self._sens_band = Dropdown(actions.select_sens_band, title="Band")
        self._sens_band.set_options(list(SENS_BANDS))
        self._sens_chip.prefix = "Sens "
        self._smooth_chip.prefix = "Smooth "
        self._size_chip.prefix = "Size "
        self._speed_chip.prefix = "Speed "
        # A lock toggle per global-feel chip; locked feel stays put through Rnd/Next/auto.
        self._sens_lock = LockToggle(lambda: actions.toggle_global_lock("sensitivity"))
        self._smooth_lock = LockToggle(lambda: actions.toggle_global_lock("smoothing"))
        self._size_lock = LockToggle(lambda: actions.toggle_global_lock("size"))
        self._speed_lock = LockToggle(lambda: actions.toggle_global_lock("speed"))
        self._global_locks: dict[str, LockToggle] = {
            "sensitivity": self._sens_lock,
            "smoothing": self._smooth_lock,
            "size": self._size_lock,
            "speed": self._speed_lock,
        }

        self._reduce = Button("Motion+", actions.toggle_reduce_motion)
        self._src = Button("Src", actions.open_source)
        self._bg = Button("BG", actions.open_background)
        self._fg = Button("FG", actions.open_foreground)
        self._logo = Button("RenK", actions.open_logo_panel)
        self._about = Button("About", actions.open_about)

        self._color = Dropdown(actions.select_color, title="Color")
        self._color.set_options([(s, COLOR_SCHEME_LABELS.get(s, s)) for s in COLOR_SCHEMES])

        # (widget, width) in display order for each row.
        step = 28  # width of a -/+ stepper button
        self._row1: list[tuple[Button | Dropdown | Chip | LockToggle, int]] = [
            (self._menu, 84),
            (self._prev, step),
            (self._dropdown, 156),
            (self._next, step),
            (self._random, 48),
            (self._looks, 168),
            (self._save_look, 64),
            (self._auto, 60),
            (self._prev_item, 54),
            (self._hist_chip, 56),
            (self._next_item, 54),
            (self._shuffle, 84),
            (self._beat_btn, 60),
            (self._sens_down, step),
            (self._sens_chip, 96),
            (self._sens_up, step),
            (self._sens_lock, _LOCK_W),
            (self._sens_band, 108),
            (self._smooth_down, step),
            (self._smooth_chip, 116),
            (self._smooth_up, step),
            (self._smooth_lock, _LOCK_W),
            (self._size_down, step),
            (self._size_chip, 96),
            (self._size_up, step),
            (self._size_lock, _LOCK_W),
            (self._speed_down, step),
            (self._speed_chip, 104),
            (self._speed_up, step),
            (self._speed_lock, _LOCK_W),
            (self._reduce, 90),
            (self._src, 50),
            (self._bg, 48),
            (self._fg, 48),
            (self._logo, 60),
            (self._about, 68),
        ]
        self._option_dropdowns: list[Dropdown] = []
        self._option_locks: list[tuple[Dropdown, LockToggle]] = []
        self._bar: pygame.Rect | None = None
        self._buttons = [w for w, _ in self._row1 if isinstance(w, Button)]
        self._chips: list[Chip] = [w for w, _ in self._row1 if isinstance(w, Chip)]

    def _on_menu_select(self, key: str) -> None:
        """Route a Menu item to its action (Start/Stop, Fullscreen, Appearance, etc.)."""
        if key == "capture":
            self._actions.toggle_capture()
        elif key == "fullscreen":
            self._actions.toggle_fullscreen()
        elif key == "appearance":
            self._actions.open_appearance()
        elif key == "hotkeys":
            self._actions.open_hotkeys()
        elif key == "quit":
            self._actions.quit()

    # -- state / contents -----------------------------------------------------
    def set_state(
        self,
        capturing: bool,
        mode_key: str,
        reduce_motion: bool,
        color_scheme: str,
        sensitivity: float,
        smoothing: float,
        size_scale: float,
        speed_scale: float,
        auto_on: bool = False,
        locked_globals: set[str] | None = None,
        sens_band: str = "all",
        beat_active: bool = False,
    ) -> None:
        self._menu.set_options(
            [
                ("capture", "Stop" if capturing else "Start"),
                ("fullscreen", "Fullscreen"),
                ("appearance", "Appearance\u2026"),
                ("hotkeys", "Hotkeys\u2026"),
                ("quit", "Quit"),
            ]
        )
        self._dropdown.set_selected(mode_key)
        self._auto.active = auto_on
        self._beat_btn.active = beat_active
        self._reduce.label = "Motion-" if reduce_motion else "Motion+"
        # Highlight Motion only in the "+" (full-motion) state, never when reduced.
        self._reduce.active = not reduce_motion
        self._color.set_selected(color_scheme)
        self._sens_chip.text = f"Sens {sensitivity:.2f}"
        self._sens_band.set_selected(sens_band)
        self._smooth_chip.text = f"Smooth {smoothing:.2f}"
        self._size_chip.text = f"Size {size_scale:.2f}"
        self._speed_chip.text = f"Speed {speed_scale:.2f}"
        locked = locked_globals or set()
        for lock_key, lock in self._global_locks.items():
            lock.locked = lock_key in locked

    def set_history(self, position: int, total: int) -> None:
        """Refresh the ``pos/total`` look-history chip between Prev and Next."""
        self._hist_chip.text = f"{position}/{total}"

    def set_looks(self, rows: list[tuple[str, str]], selected_id: str) -> None:
        """Refresh the ``My Looks`` dropdown contents + current selection."""
        self._looks.set_options(rows)
        self._looks.set_selected(selected_id)

    def set_mode_options(self, specs: list[OptionSpec]) -> None:
        """Rebuild the per-mode option dropdowns (+ lock toggles) for the active mode."""
        self._option_dropdowns = []
        self._option_locks = []  # (dropdown, lock) pairs, parallel to lockable options
        for spec in specs:
            dd = Dropdown(self._make_option_callback(spec.key), title=spec.label)
            dd.set_options([(str(i), label) for i, label in enumerate(spec.choice_labels)])
            dd.set_selected(str(spec.current_index))
            self._option_dropdowns.append(dd)
            if spec.lockable:
                lock = LockToggle(self._make_lock_callback(spec.key))
                lock.locked = spec.locked
                self._option_locks.append((dd, lock))
        if self._bar is not None:
            self.relayout(self._bar)

    def _make_option_callback(self, key: str) -> Callable[[str], None]:
        return lambda index_str: self._actions.option_change(key, int(index_str))

    def _make_lock_callback(self, key: str) -> Callable[[], None]:
        return lambda: self._actions.toggle_option_lock(key)

    def toggle_mode_dropdown(self) -> None:
        self._dropdown.toggle()

    # -- layout ---------------------------------------------------------------
    def _row2_items(self) -> list[tuple[Button | Dropdown | Chip | LockToggle, int]]:
        """Bottom group: color scheme + each option dropdown (with its lock toggle)."""
        locks = {id(dd): lock for dd, lock in self._option_locks}
        items: list[tuple[Button | Dropdown | Chip | LockToggle, int]] = [(self._color, _OPTION_W)]
        for dd in self._option_dropdowns:
            items.append((dd, _OPTION_W))
            lock = locks.get(id(dd))
            if lock is not None:
                items.append((lock, _LOCK_W))
        return items

    def _flow(
        self,
        items: list[tuple[Button | Dropdown | Chip | LockToggle, int]],
        left: int,
        right: int,
        top: int,
        place: bool,
    ) -> int:
        """Flow ``items`` left-to-right, wrapping when they'd pass ``right``.

        Returns the ``y`` of the last row used. When ``place`` is False the widgets
        aren't moved (used to measure the needed height before the bar exists).
        """
        x = left
        y = top
        for idx, (widget, w) in enumerate(items):
            # A lock pin hugs the control it governs: keep them together on wrap and
            # use a tight gap before the pin so it reads as "belongs to the left control".
            is_lock = isinstance(widget, LockToggle)
            next_is_lock = idx + 1 < len(items) and isinstance(items[idx + 1][0], LockToggle)
            group_w = w + (_LOCK_W + _LOCK_GAP if next_is_lock else 0)
            if not is_lock and x > left and x + group_w > right:
                x = left
                y += CONTROL_ROW_HEIGHT + CONTROL_GAP
            if is_lock:
                x -= CONTROL_GAP - _LOCK_GAP  # pull the pin closer to its control
            if place:
                widget.set_rect(pygame.Rect(x, y, w, CONTROL_ROW_HEIGHT))
            x += w + CONTROL_GAP
        return y

    def content_height(self, width: int) -> int:
        """Total bar height needed to flow all widgets at the given window width."""
        left, right, top = CONTROL_GAP, width - CONTROL_GAP, CONTROL_GAP
        y = self._flow(self._row1, left, right, top, place=False)
        y = self._flow(self._row2_items(), left, right, y + CONTROL_ROW_HEIGHT + CONTROL_GAP, False)
        return y + CONTROL_ROW_HEIGHT + CONTROL_GAP

    def relayout(self, bar: pygame.Rect) -> None:
        self._bar = bar
        left, right = bar.x + CONTROL_GAP, bar.right - CONTROL_GAP
        top = bar.y + CONTROL_GAP
        y = self._flow(self._row1, left, right, top, place=True)
        self._flow(self._row2_items(), left, right, y + CONTROL_ROW_HEIGHT + CONTROL_GAP, True)
        # Keep every open option list inside the window's right edge.
        for dd in self._all_dropdowns():
            dd.set_bound_right(bar.right - CONTROL_GAP)

    # -- input ----------------------------------------------------------------
    def _all_dropdowns(self) -> list[Dropdown]:
        return [
            self._menu,
            self._dropdown,
            self._looks,
            self._sens_band,
            self._color,
            *self._option_dropdowns,
        ]

    def is_editing(self) -> bool:
        """True while any value chip is capturing typed input (suppresses shortcuts)."""
        return any(chip.editing for chip in self._chips)

    def handle_event(self, event: pygame.event.Event) -> bool:
        for dd in self._all_dropdowns():
            if dd.handle_event(event):
                if dd.open:  # keep only the just-opened dropdown expanded
                    for other in self._all_dropdowns():
                        if other is not dd:
                            other.open = False
                return True
        for chip in self._chips:
            if chip.handle_event(event):
                if chip.editing:  # only one chip edits at a time
                    for other_chip in self._chips:
                        if other_chip is not chip:
                            other_chip.cancel_edit()
                return True
        for lock in self._all_locks():
            if lock.handle_event(event):
                return True
        clicked = False
        for btn in self._buttons:
            if btn.handle_event(event):
                clicked = True
        return clicked

    def _all_locks(self) -> list[LockToggle]:
        return [*self._global_locks.values(), *(lock for _dd, lock in self._option_locks)]

    # -- draw -----------------------------------------------------------------
    def draw(self, surface: pygame.Surface, bar: pygame.Rect, font: pygame.font.Font) -> None:
        pygame.draw.rect(surface, COLOR_BAR, bar)
        pygame.draw.line(surface, COLOR_BORDER, bar.bottomleft, bar.bottomright)
        for btn in self._buttons:
            btn.draw(surface, font)
        for chip in self._chips:
            chip.draw(surface, font)
        for lock in self._all_locks():
            lock.draw(surface, font)
        # Draw closed dropdowns first, then the open one last so its list is on top.
        dropdowns = self._all_dropdowns()
        open_dd = next((dd for dd in dropdowns if dd.open), None)
        for dd in dropdowns:
            if dd is not open_dd:
                dd.draw(surface, font)
        if open_dd is not None:
            open_dd.draw(surface, font)
