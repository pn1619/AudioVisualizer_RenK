"""Cross-fade state for auto-cycle switches (Phase 0B-c).

A :class:`ModeTransition` fades an outgoing scene out over the live (incoming)
one over ``duration`` seconds. It comes in two flavors:

* **Live cross-fade** (``prev_visual`` set) — used for **mode -> mode** switches.
  The outgoing visual instance is kept alive and re-rendered **every frame**
  during the fade, so both visuals keep animating. Costs a second render per
  frame, but only while a fade is in flight.
* **Frozen dissolve** (``snapshot`` set) — used for switches onto a **saved
  look** (which also changes background/logo/theme). The outgoing scene is
  captured once into ``snapshot`` and blitted on top at a falling alpha.

The App applies the new mode/look to the live global immediately, draws the live
scene, then this overlays the outgoing scene at :meth:`overlay_alpha`. The
leading underscore keeps the registry's ``discover()`` from importing this as a
visual mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from audio_visualizer.visuals.base import BaseVisualizer


@dataclass
class ModeTransition:
    """A timed fade of an outgoing scene over the live one.

    Exactly one of ``prev_visual`` (live cross-fade) or ``snapshot`` (frozen
    dissolve) is set; the App picks based on whether the switch is mode->mode.
    """

    duration: float
    elapsed: float = field(default=0.0)
    snapshot: pygame.Surface | None = None
    prev_visual: BaseVisualizer | None = None

    @property
    def is_live(self) -> bool:
        """True when the outgoing visual is re-rendered live (mode->mode)."""
        return self.prev_visual is not None

    def advance(self, dt: float) -> bool:
        """Advance the fade clock. Returns True once the transition is complete."""
        self.elapsed += max(0.0, dt)
        return self.elapsed >= self.duration

    def overlay_alpha(self) -> int:
        """Alpha (0..255) for the outgoing scene: full at start, 0 at the end."""
        if self.duration <= 0.0:
            return 0
        return int(round(255 * (1.0 - min(1.0, self.elapsed / self.duration))))
