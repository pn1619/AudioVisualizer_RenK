"""The one interface every visual mode implements."""

from __future__ import annotations

import pygame

from audio_visualizer.audio.frame import AnalysisFrame


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

    def __init__(self, reduce_motion: bool = False) -> None:
        self.reduce_motion = reduce_motion

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
