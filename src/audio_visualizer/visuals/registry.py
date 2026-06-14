"""Auto-registration + discovery for visual modes (no central list to maintain)."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from collections.abc import Callable

from audio_visualizer.visuals.base import BaseVisualizer

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, type[BaseVisualizer]] = {}
_SKIP = {"base", "registry"}


def register(
    key: str, display_name: str | None = None, order: int = 100
) -> Callable[[type[BaseVisualizer]], type[BaseVisualizer]]:
    """Class decorator that records a visual mode under ``key``."""

    def decorator(cls: type[BaseVisualizer]) -> type[BaseVisualizer]:
        cls.KEY = key
        cls.DISPLAY_NAME = display_name or key.replace("_", " ").title()
        cls.ORDER = order
        if key in _REGISTRY and _REGISTRY[key] is not cls:
            logger.warning("Visual mode key %r already registered; overwriting", key)
        _REGISTRY[key] = cls
        return cls

    return decorator


def discover() -> None:
    """Import every non-underscore module in this package to trigger @register."""
    package = importlib.import_module(__package__)
    for module in pkgutil.iter_modules(package.__path__):
        if module.name.startswith("_") or module.name in _SKIP:
            continue
        importlib.import_module(f"{__package__}.{module.name}")


def available() -> list[type[BaseVisualizer]]:
    """Registered modes ordered by ``ORDER`` then ``KEY``."""
    return sorted(_REGISTRY.values(), key=lambda c: (c.ORDER, c.KEY))


def keys() -> list[str]:
    """Mode keys in display order."""
    return [cls.KEY for cls in available()]


def create(key: str, **kwargs) -> BaseVisualizer:
    """Instantiate the mode registered under ``key``."""
    return _REGISTRY[key](**kwargs)


def clear() -> None:
    """Remove all registrations (used by tests)."""
    _REGISTRY.clear()
