"""The one interface every visual mode implements."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import (
    COLOR_HUE2_DEFAULT,
    COLOR_HUE_DEFAULT,
    COLOR_SCHEME_DEFAULT,
    SIZE_SCALE_DEFAULT,
    SPEED_SCALE_DEFAULT,
)


@dataclass
class Theme:
    """Shared, user-tunable visual settings passed (live) to every mode.

    The App owns one instance and mutates it as the user adjusts controls; all
    active visuals hold the same reference, so changes take effect immediately.
    """

    size_scale: float = SIZE_SCALE_DEFAULT  # multiplier on particle/flake sizes
    speed_scale: float = SPEED_SCALE_DEFAULT  # multiplier on animation speed
    color_scheme: str = COLOR_SCHEME_DEFAULT  # see config.COLOR_SCHEMES
    color_phase: float = 0.0  # 0..1 time offset advanced by the App for rainbow_plus
    custom_hue: float = COLOR_HUE_DEFAULT  # 0..1 hue for the Solid/Mono schemes
    custom_hue2: float = COLOR_HUE2_DEFAULT  # 0..1 second hue for the Stereo scheme


@dataclass(frozen=True)
class OptionChoice:
    """One selectable value in a :class:`ModeOption` (label + numeric value)."""

    label: str
    value: float


@dataclass(frozen=True)
class ModeOption:
    """A per-mode tunable shown as its own dropdown (e.g. snowfall fall speed).

    Choices are discrete so they map cleanly onto a dropdown; ``value`` is what
    the mode reads via :meth:`BaseVisualizer.option`.
    """

    key: str
    label: str
    choices: tuple[OptionChoice, ...]
    default_index: int = 0


class BaseVisualizer:
    """Base class for all visual modes.

    Subclasses implement :meth:`draw`. The ``KEY``/``DISPLAY_NAME``/``ORDER``
    class attributes are set by the ``@register`` decorator. Lifecycle hooks
    have safe no-op defaults; override only what you need.
    """

    KEY: str = ""
    DISPLAY_NAME: str = ""
    ORDER: int = 100
    # Modes that flash/strobe set this True so the app shows the one-time
    # photosensitivity notice before they first appear.
    STROBES: bool = False
    # Per-mode tunables exposed as their own dropdowns; override in subclasses.
    OPTIONS: tuple[ModeOption, ...] = ()
    # Optional curated presets: ``{preset_index: {option_key: choice_index}}``.
    # A mode with presets declares a "preset" option (first choice = a no-op
    # "Custom"); selecting another choice snaps the listed sibling options.
    PRESETS: dict[int, dict[str, int]] = {}

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        self.reduce_motion = reduce_motion
        # The App replaces this with its shared Theme; a default keeps modes
        # usable standalone (e.g. in tests) without any wiring.
        self.theme = theme if theme is not None else Theme()
        self._option_index: dict[str, int] = {opt.key: opt.default_index for opt in self.OPTIONS}

    # -- per-mode options -----------------------------------------------------
    def _option_def(self, key: str) -> ModeOption:
        for opt in self.OPTIONS:
            if opt.key == key:
                return opt
        raise KeyError(key)

    def option(self, key: str) -> float:
        """Current value of option ``key``."""
        return self._option_def(key).choices[self._option_index[key]].value

    def option_index(self, key: str) -> int:
        """Index of the currently selected choice for option ``key``."""
        return self._option_index[key]

    def set_option_index(self, key: str, index: int) -> None:
        """Select choice ``index`` for option ``key`` (clamped); notify the mode."""
        opt = self._option_def(key)
        self._option_index[key] = max(0, min(index, len(opt.choices) - 1))
        self.on_option_change(key)

    def on_option_change(self, key: str) -> None:
        """React to an option change. Default: apply a chosen preset (if any).

        Subclasses that override this should call ``super().on_option_change(key)``
        to keep preset handling working.
        """
        if key == "preset" and self.PRESETS:
            self._apply_preset()

    def _apply_preset(self) -> None:
        """Snap sibling options to the selected preset's choice indices."""
        mapping = self.PRESETS.get(self.option_index("preset"), {})
        for opt_key, choice in mapping.items():
            if opt_key in self._option_index:
                count = len(self._option_def(opt_key).choices)
                self._option_index[opt_key] = max(0, min(choice, count - 1))

    def on_enter(self) -> None:
        """Called when this mode becomes active."""

    def on_exit(self) -> None:
        """Called when switching away from this mode."""

    def on_resize(self, size: tuple[int, int]) -> None:
        """Called when the drawing surface changes size."""

    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        """Render one frame.

        Args:
            surface: Target surface; read its current size for all geometry.
            frame: Latest analysis, or ``None`` when idle/no data yet.
            dt: Seconds since the previous frame.
        """
        raise NotImplementedError
