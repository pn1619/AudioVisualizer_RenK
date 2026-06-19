"""Cross-fade state for auto-cycle mode switches (Phase 0B-c).

A :class:`ModeTransition` holds the outgoing + incoming visuals for the brief
window while one mode dissolves into the next. The App owns the offscreen
compositing (it needs the shared background/logo); this module only tracks the
fade clock and exposes the blend ``alpha``. The leading underscore keeps the
registry's ``discover()`` from importing this as a visual mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from audio_visualizer.visuals.base import BaseVisualizer


@dataclass
class ModeTransition:
    """A timed cross-fade from ``outgoing`` to ``incoming`` (target mode index)."""

    outgoing: BaseVisualizer
    incoming: BaseVisualizer
    target_index: int
    duration: float
    elapsed: float = field(default=0.0)

    def advance(self, dt: float) -> bool:
        """Advance the fade clock. Returns True once the transition is complete."""
        self.elapsed += max(0.0, dt)
        return self.elapsed >= self.duration

    def alpha(self) -> int:
        """Incoming-mode blend alpha in 0..255 (0 = fully outgoing, 255 = incoming)."""
        if self.duration <= 0.0:
            return 255
        return int(round(255 * min(1.0, self.elapsed / self.duration)))
