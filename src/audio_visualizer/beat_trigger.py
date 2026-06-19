"""Beat Buttons: let the music "press" app actions (e.g. Rnd / Next).

Pure logic (no pygame/I/O), so it's easy to unit-test. Each action carries a
sensitivity level (``Off``/``Low``/``Med``/``High``/``Max``). On every frame the
engine tracks a slow **baseline** of the onset strength and fires an action when
the live onset spikes above ``baseline * ratio`` (adapting to the track's energy)
*and* an absolute floor is cleared *and* a per-level **cooldown** has elapsed.

The cooldown is what keeps triggering reasonable: ``Max`` fires on most beats but
never more than ~2x/second, while ``Low`` only reacts to strong hits spaced
several seconds apart. Silence emits nothing — the baseline decays toward zero and
the onset floor blocks spurious fires.
"""

from __future__ import annotations

from audio_visualizer.config import (
    BEAT_ACTIONS,
    BEAT_BASELINE_TAU,
    BEAT_SENSITIVITY_LABELS,
    BEAT_SENSITIVITY_PARAMS,
)

_ACTION_KEYS: tuple[str, ...] = tuple(key for key, _label in BEAT_ACTIONS)
_MAX_LEVEL = len(BEAT_SENSITIVITY_LABELS) - 1


class BeatTrigger:
    """Decides which actions the music should auto-fire this frame."""

    def __init__(self, levels: dict[str, int] | None = None) -> None:
        self._levels: dict[str, int] = {key: 0 for key in _ACTION_KEYS}
        if levels:
            for key, value in levels.items():
                if key in self._levels:
                    self._levels[key] = self._clamp(value)
        self._baseline = 0.0
        self._since: dict[str, float] = {key: 1e9 for key in _ACTION_KEYS}

    @staticmethod
    def _clamp(value: int) -> int:
        return max(0, min(_MAX_LEVEL, int(value)))

    def level(self, action: str) -> int:
        """Current sensitivity index for ``action`` (0 = Off)."""
        return self._levels.get(action, 0)

    def set_level(self, action: str, index: int) -> None:
        if action in self._levels:
            self._levels[action] = self._clamp(index)

    def cycle(self, action: str) -> None:
        """Advance ``action`` to the next sensitivity level, wrapping past Max."""
        if action in self._levels:
            self._levels[action] = (self._levels[action] + 1) % (_MAX_LEVEL + 1)

    def any_enabled(self) -> bool:
        return any(level > 0 for level in self._levels.values())

    def levels_dict(self) -> dict[str, int]:
        """A copy of the per-action levels (for persistence)."""
        return dict(self._levels)

    def reset(self) -> None:
        """Clear baseline + cooldowns (e.g. when capture stops)."""
        self._baseline = 0.0
        self._since = {key: 1e9 for key in _ACTION_KEYS}

    def update(self, onset: float, is_silent: bool, dt: float) -> list[str]:
        """Advance state by ``dt`` and return the action keys that should fire now."""
        for key in self._since:
            self._since[key] += dt
        # Track the baseline regardless of silence so it decays toward zero.
        alpha = 1.0 if dt >= BEAT_BASELINE_TAU else dt / BEAT_BASELINE_TAU
        self._baseline += (onset - self._baseline) * alpha
        if is_silent:
            return []
        fired: list[str] = []
        for key in _ACTION_KEYS:
            params = BEAT_SENSITIVITY_PARAMS[self._levels[key]]
            if params is None:
                continue
            ratio, floor, cooldown = params
            if self._since[key] < cooldown or onset < floor:
                continue
            if onset >= self._baseline * ratio:
                fired.append(key)
                self._since[key] = 0.0
        return fired
