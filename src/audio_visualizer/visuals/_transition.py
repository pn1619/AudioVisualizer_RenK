"""Cross-fade state for auto-cycle switches (Phase 0B-c).

A :class:`ModeTransition` is a **frozen-snapshot dissolve**: when a switch starts
the App grabs the current canvas into ``snapshot`` and applies the new mode/look
to the live global immediately. Each frame the live (new) scene is drawn first
and the frozen old scene is blitted on top at a falling alpha, so it dissolves
away. This works identically whether the next item is a built-in mode or a saved
look (which also changes background/logo/theme) and renders the *live* scene only
once. The leading underscore keeps the registry's ``discover()`` from importing
this as a visual mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame


@dataclass
class ModeTransition:
    """A timed dissolve of a frozen ``snapshot`` (the outgoing scene) over the live one."""

    snapshot: pygame.Surface
    duration: float
    elapsed: float = field(default=0.0)

    def advance(self, dt: float) -> bool:
        """Advance the fade clock. Returns True once the transition is complete."""
        self.elapsed += max(0.0, dt)
        return self.elapsed >= self.duration

    def overlay_alpha(self) -> int:
        """Alpha (0..255) for the frozen snapshot: full at start, 0 at the end."""
        if self.duration <= 0.0:
            return 0
        return int(round(255 * (1.0 - min(1.0, self.elapsed / self.duration))))
