"""Beat Buttons: let the music "press" app actions (e.g. Rnd / Next).

Pure logic (no pygame/I/O), so it's easy to unit-test. Each action carries a
**sensitivity** level (``Off``..``Max``) and the **frequency band** it listens to
(``All``/``Bass``/``Mid``/``High``). On every frame the engine measures each band
group's energy, tracks a slow **baseline** per group, and fires an action when its
band's energy spikes above ``baseline * ratio`` (so it adapts to the track), clears
an absolute floor, and a per-level **cooldown** has elapsed.

The cooldown keeps triggering reasonable: ``Max`` fires on most beats but never more
than ~3x/second, while ``Min`` only reacts to strong hits seconds apart. Silence
emits nothing — baselines decay toward zero and the floor blocks spurious fires.

It also exposes a small read-only "meter" (:attr:`intensity`, :attr:`active_band`,
:attr:`flash`) the on-screen indicator uses to show how close a fire is.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from audio_visualizer.config import (
    BEAT_ACTIONS,
    BEAT_BAND_DEFAULT,
    BEAT_BANDS,
    BEAT_BASELINE_TAU,
    BEAT_FLASH_TAU,
    BEAT_SENSITIVITY_LABELS,
    BEAT_SENSITIVITY_PARAMS,
)

_ACTION_KEYS: tuple[str, ...] = tuple(key for key, _label in BEAT_ACTIONS)
_BAND_KEYS: tuple[str, ...] = tuple(key for key, _label in BEAT_BANDS)
_MAX_LEVEL = len(BEAT_SENSITIVITY_LABELS) - 1


def _band_signal(bands: NDArray[np.float32], band: str) -> float:
    """Mean energy of the chosen third of the spectrum (whole for ``all``)."""
    n = bands.size
    if n == 0:
        return 0.0
    third = max(1, n // 3)
    if band == "bass":
        lo, hi = 0, third
    elif band == "mid":
        lo, hi = third, 2 * third
    elif band == "high":
        lo, hi = 2 * third, n
    else:  # all
        lo, hi = 0, n
    return float(np.mean(bands[lo:hi]))


class BeatTrigger:
    """Decides which actions the music should auto-fire this frame."""

    def __init__(
        self,
        levels: dict[str, int] | None = None,
        bands: dict[str, str] | None = None,
        enabled: bool = True,
    ) -> None:
        self._enabled = bool(enabled)
        self._levels: dict[str, int] = {key: 0 for key in _ACTION_KEYS}
        self._bands: dict[str, str] = {key: BEAT_BAND_DEFAULT for key in _ACTION_KEYS}
        if levels:
            for key, value in levels.items():
                if key in self._levels:
                    self._levels[key] = self._clamp(value)
        if bands:
            for key, value in bands.items():
                if key in self._bands and value in _BAND_KEYS:
                    self._bands[key] = value
        self._baseline: dict[str, float] = {key: 0.0 for key in _BAND_KEYS}
        self._since: dict[str, float] = {key: 1e9 for key in _ACTION_KEYS}
        # Read-only meter for the indicator (max across enabled actions).
        self.intensity = 0.0
        self.active_band = BEAT_BAND_DEFAULT
        self.flash = 0.0

    @staticmethod
    def _clamp(value: int) -> int:
        return max(0, min(_MAX_LEVEL, int(value)))

    def level(self, action: str) -> int:
        return self._levels.get(action, 0)

    def band(self, action: str) -> str:
        return self._bands.get(action, BEAT_BAND_DEFAULT)

    def set_level(self, action: str, index: int) -> None:
        if action in self._levels:
            self._levels[action] = self._clamp(index)

    def cycle(self, action: str) -> None:
        """Advance ``action`` to the next sensitivity level, wrapping past Max."""
        if action in self._levels:
            self._levels[action] = (self._levels[action] + 1) % (_MAX_LEVEL + 1)

    def cycle_band(self, action: str) -> None:
        """Advance ``action`` to the next listened band, wrapping."""
        if action in self._bands:
            idx = _BAND_KEYS.index(self._bands[action])
            self._bands[action] = _BAND_KEYS[(idx + 1) % len(_BAND_KEYS)]

    def set_band(self, action: str, band: str) -> None:
        if action in self._bands and band in _BAND_KEYS:
            self._bands[action] = band

    def set_enabled(self, value: bool) -> None:
        """Master switch: when off the engine fires nothing (settings are kept)."""
        self._enabled = bool(value)

    def is_enabled(self) -> bool:
        return self._enabled

    def any_enabled(self) -> bool:
        return any(level > 0 for level in self._levels.values())

    def active(self) -> bool:
        """True when the feature is on AND at least one action has a level set."""
        return self._enabled and self.any_enabled()

    def levels_dict(self) -> dict[str, int]:
        return dict(self._levels)

    def bands_dict(self) -> dict[str, str]:
        return dict(self._bands)

    def reset(self) -> None:
        """Clear baselines + cooldowns + meter (e.g. when capture stops)."""
        self._baseline = {key: 0.0 for key in _BAND_KEYS}
        self._since = {key: 1e9 for key in _ACTION_KEYS}
        self.intensity = 0.0
        self.flash = 0.0

    def update(self, band_energies: NDArray[np.float32], is_silent: bool, dt: float) -> list[str]:
        """Advance state by ``dt`` and return the action keys that should fire now."""
        for key in self._since:
            self._since[key] += dt
        self.flash = max(0.0, self.flash - (dt / BEAT_FLASH_TAU if BEAT_FLASH_TAU else 1.0))
        alpha = 1.0 if dt >= BEAT_BASELINE_TAU else dt / BEAT_BASELINE_TAU
        signals = {band: _band_signal(band_energies, band) for band in _BAND_KEYS}
        for band, sig in signals.items():
            self._baseline[band] += (sig - self._baseline[band]) * alpha

        if is_silent or not self._enabled:
            self.intensity = 0.0
            return []
        fired: list[str] = []
        best_intensity = 0.0
        best_band = self.active_band
        for key in _ACTION_KEYS:
            params = BEAT_SENSITIVITY_PARAMS[self._levels[key]]
            if params is None:
                continue
            ratio, floor, cooldown = params
            band = self._bands[key]
            sig = signals[band]
            threshold = max(self._baseline[band] * ratio, floor)
            intensity = sig / threshold if threshold > 0 else 0.0
            if intensity > best_intensity:
                best_intensity = intensity
                best_band = band
            ready = self._since[key] >= cooldown
            if ready and sig >= floor and sig >= self._baseline[band] * ratio:
                fired.append(key)
                self._since[key] = 0.0
        self.intensity = min(1.0, best_intensity)
        self.active_band = best_band
        if fired:
            self.flash = 1.0
        return fired
