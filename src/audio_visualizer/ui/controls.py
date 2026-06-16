"""Top control bar: two rows of controls + dropdowns, laid out and click-routed.

Row 1 holds global controls (capture, mode picker, sensitivity/smoothing/size/
speed with inline value chips). Row 2 holds the color-scheme dropdown plus one
dropdown per option exposed by the active visual mode.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from audio_visualizer.config import COLOR_PANEL, COLOR_SCHEME_LABELS, COLOR_SCHEMES
from audio_visualizer.ui.button import Button
from audio_visualizer.ui.chip import Chip
from audio_visualizer.ui.dropdown import Dropdown


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

        self._sens_down = Button("Sens -", actions.sensitivity_down)
        self._sens_chip = Chip()
        self._sens_up = Button("Sens +", actions.sensitivity_up)
        self._smooth_down = Button("Smooth -", actions.smoothing_down)
        self._smooth_chip = Chip()
        self._smooth_up = Button("Smooth +", actions.smoothing_up)
        self._size_down = Button("Size -", actions.size_down)
        self._size_chip = Chip()
        self._size_up = Button("Size +", actions.size_up)
        self._speed_down = Button("Speed -", actions.speed_down)
        self._speed_chip = Chip()
        self._speed_up = Button("Speed +", actions.speed_up)

        self._reduce = Button("Motion+", actions.toggle_reduce_motion)
        self._logo = Button("RenK", actions.open_logo_panel)
        self._about = Button("About", actions.open_about)

        self._color = Dropdown(actions.select_color, title="Color")
        self._color.set_options([(s, COLOR_SCHEME_LABELS.get(s, s)) for s in COLOR_SCHEMES])

        # (widget, width) in display order for each row.
        self._row1: list[tuple[Button | Dropdown | Chip, int]] = [
            (self._menu, 72),
            (self._prev, 28),
            (self._dropdown, 130),
            (self._next, 28),
            (self._sens_down, 52),
            (self._sens_chip, 46),
            (self._sens_up, 52),
            (self._smooth_down, 64),
            (self._smooth_chip, 46),
            (self._smooth_up, 64),
            (self._size_down, 52),
            (self._size_chip, 46),
            (self._size_up, 52),
            (self._speed_down, 56),
            (self._speed_chip, 46),
            (self._speed_up, 56),
            (self._reduce, 64),
            (self._logo, 52),
            (self._about, 56),
        ]
        self._option_dropdowns: list[Dropdown] = []
        self._bar: pygame.Rect | None = None
        self._buttons = [w for w, _ in self._row1 if isinstance(w, Button)]
        self._chips = [w for w, _ in self._row1 if isinstance(w, Chip)]

    def _on_menu_select(self, key: str) -> None:
        """Route a Menu item to its action (Start/Stop, Fullscreen, Quit)."""
        if key == "capture":
            self._actions.toggle_capture()
        elif key == "fullscreen":
            self._actions.toggle_fullscreen()
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
                ("quit", "Quit"),
            ]
        )
        self._dropdown.set_selected(mode_key)
        self._reduce.label = "Motion-" if reduce_motion else "Motion+"
        self._color.set_selected(color_scheme)
        self._sens_chip.text = f"{sensitivity:.2f}"
        self._smooth_chip.text = f"{smoothing:.2f}"
        self._size_chip.text = f"{size_scale:.2f}"
        self._speed_chip.text = f"{speed_scale:.2f}"

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
    def relayout(self, bar: pygame.Rect) -> None:
        self._bar = bar
        pad = 6
        row_h = max(1, (bar.height - pad * 3) // 2)
        row1_y = bar.y + pad
        row2_y = row1_y + row_h + pad

        x = bar.x + pad
        for widget, w in self._row1:
            widget.set_rect(pygame.Rect(x, row1_y, w, row_h))
            x += w + pad

        x = bar.x + pad
        self._color.set_rect(pygame.Rect(x, row2_y, 150, row_h))
        x += 150 + pad
        for dd in self._option_dropdowns:
            dd.set_rect(pygame.Rect(x, row2_y, 150, row_h))
            x += 150 + pad

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
        pygame.draw.rect(surface, COLOR_PANEL, bar)
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
