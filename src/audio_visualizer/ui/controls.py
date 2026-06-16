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
)
from audio_visualizer.ui.button import Button
from audio_visualizer.ui.chip import Chip
from audio_visualizer.ui.dropdown import Dropdown

_OPTION_W = 150  # width of the color + per-mode option dropdowns


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


@dataclass(frozen=True)
class OptionSpec:
    """A per-mode option to render as a dropdown (label + choices + selection)."""

    key: str
    label: str
    choice_labels: tuple[str, ...]
    current_index: int


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

        # Compact steppers: [-] <Name value> [+]; the chip carries the name+value so
        # the tiny buttons stay unambiguous without long labels (which the wider
        # monospace UI font would otherwise truncate).
        minus, plus = "\u2212", "+"
        self._sens_down = Button(minus, actions.sensitivity_down)
        self._sens_chip = Chip()
        self._sens_up = Button(plus, actions.sensitivity_up)
        self._smooth_down = Button(minus, actions.smoothing_down)
        self._smooth_chip = Chip()
        self._smooth_up = Button(plus, actions.smoothing_up)
        self._size_down = Button(minus, actions.size_down)
        self._size_chip = Chip()
        self._size_up = Button(plus, actions.size_up)
        self._speed_down = Button(minus, actions.speed_down)
        self._speed_chip = Chip()
        self._speed_up = Button(plus, actions.speed_up)

        self._reduce = Button("Motion+", actions.toggle_reduce_motion)
        self._logo = Button("RenK", actions.open_logo_panel)
        self._about = Button("About", actions.open_about)

        self._color = Dropdown(actions.select_color, title="Color")
        self._color.set_options([(s, COLOR_SCHEME_LABELS.get(s, s)) for s in COLOR_SCHEMES])

        # (widget, width) in display order for each row.
        step = 28  # width of a -/+ stepper button
        self._row1: list[tuple[Button | Dropdown | Chip, int]] = [
            (self._menu, 84),
            (self._prev, step),
            (self._dropdown, 156),
            (self._next, step),
            (self._sens_down, step),
            (self._sens_chip, 96),
            (self._sens_up, step),
            (self._smooth_down, step),
            (self._smooth_chip, 116),
            (self._smooth_up, step),
            (self._size_down, step),
            (self._size_chip, 96),
            (self._size_up, step),
            (self._speed_down, step),
            (self._speed_chip, 104),
            (self._speed_up, step),
            (self._reduce, 90),
            (self._logo, 60),
            (self._about, 68),
        ]
        self._option_dropdowns: list[Dropdown] = []
        self._bar: pygame.Rect | None = None
        self._buttons = [w for w, _ in self._row1 if isinstance(w, Button)]
        self._chips = [w for w, _ in self._row1 if isinstance(w, Chip)]

    def _on_menu_select(self, key: str) -> None:
        """Route a Menu item to its action (Start/Stop, Fullscreen, Appearance, Quit)."""
        if key == "capture":
            self._actions.toggle_capture()
        elif key == "fullscreen":
            self._actions.toggle_fullscreen()
        elif key == "appearance":
            self._actions.open_appearance()
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
    ) -> None:
        self._menu.set_options(
            [
                ("capture", "Stop" if capturing else "Start"),
                ("fullscreen", "Fullscreen"),
                ("appearance", "Appearance\u2026"),
                ("quit", "Quit"),
            ]
        )
        self._dropdown.set_selected(mode_key)
        self._reduce.label = "Motion-" if reduce_motion else "Motion+"
        self._color.set_selected(color_scheme)
        self._sens_chip.text = f"Sens {sensitivity:.2f}"
        self._smooth_chip.text = f"Smooth {smoothing:.2f}"
        self._size_chip.text = f"Size {size_scale:.2f}"
        self._speed_chip.text = f"Speed {speed_scale:.2f}"

    def set_mode_options(self, specs: list[OptionSpec]) -> None:
        """Rebuild the per-mode option dropdowns for the active visual mode."""
        self._option_dropdowns = []
        for spec in specs:
            dd = Dropdown(self._make_option_callback(spec.key), title=spec.label)
            dd.set_options([(str(i), label) for i, label in enumerate(spec.choice_labels)])
            dd.set_selected(str(spec.current_index))
            self._option_dropdowns.append(dd)
        if self._bar is not None:
            self.relayout(self._bar)

    def _make_option_callback(self, key: str) -> Callable[[str], None]:
        return lambda index_str: self._actions.option_change(key, int(index_str))

    def toggle_mode_dropdown(self) -> None:
        self._dropdown.toggle()

    # -- layout ---------------------------------------------------------------
    def _row2_items(self) -> list[tuple[Button | Dropdown | Chip, int]]:
        """Bottom group: color scheme + one dropdown per active-mode option."""
        return [(self._color, _OPTION_W), *[(dd, _OPTION_W) for dd in self._option_dropdowns]]

    def _flow(
        self,
        items: list[tuple[Button | Dropdown | Chip, int]],
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
        for widget, w in items:
            if x > left and x + w > right:
                x = left
                y += CONTROL_ROW_HEIGHT + CONTROL_GAP
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
        return [self._menu, self._dropdown, self._color, *self._option_dropdowns]

    def handle_event(self, event: pygame.event.Event) -> bool:
        for dd in self._all_dropdowns():
            if dd.handle_event(event):
                if dd.open:  # keep only the just-opened dropdown expanded
                    for other in self._all_dropdowns():
                        if other is not dd:
                            other.open = False
                return True
        clicked = False
        for btn in self._buttons:
            if btn.handle_event(event):
                clicked = True
        return clicked

    # -- draw -----------------------------------------------------------------
    def draw(self, surface: pygame.Surface, bar: pygame.Rect, font: pygame.font.Font) -> None:
        pygame.draw.rect(surface, COLOR_BAR, bar)
        pygame.draw.line(surface, COLOR_BORDER, bar.bottomleft, bar.bottomright)
        for btn in self._buttons:
            btn.draw(surface, font)
        for chip in self._chips:
            chip.draw(surface, font)
        # Draw closed dropdowns first, then the open one last so its list is on top.
        dropdowns = self._all_dropdowns()
        open_dd = next((dd for dd in dropdowns if dd.open), None)
        for dd in dropdowns:
            if dd is not open_dd:
                dd.draw(surface, font)
        if open_dd is not None:
            open_dd.draw(surface, font)
