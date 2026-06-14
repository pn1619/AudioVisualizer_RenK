"""Visual registry: discovery, uniqueness, ordering, and drop-in registration."""

from __future__ import annotations

from audio_visualizer.visuals import registry
from audio_visualizer.visuals.base import BaseVisualizer


def test_discover_finds_builtin_modes() -> None:
    registry.discover()
    keys = registry.keys()
    for expected in ("waveform", "spectrum", "lightshow"):
        assert expected in keys


def test_keys_are_unique() -> None:
    registry.discover()
    keys = registry.keys()
    assert len(keys) == len(set(keys))


def test_available_is_ordered_by_order() -> None:
    registry.discover()
    modes = registry.available()
    orders = [m.ORDER for m in modes]
    assert orders == sorted(orders)


def test_drop_in_class_auto_registers() -> None:
    """Proves 'add a mode = one file': defining + decorating is all it takes."""
    registry.discover()
    before = len(registry.keys())

    @registry.register(key="unittest_dummy", display_name="Dummy", order=999)
    class _Dummy(BaseVisualizer):
        def draw(self, surface, frame, dt):  # type: ignore[no-untyped-def]
            return None

    assert "unittest_dummy" in registry.keys()
    assert len(registry.keys()) == before + 1
    instance = registry.create("unittest_dummy")
    assert isinstance(instance, BaseVisualizer)
    assert instance.DISPLAY_NAME == "Dummy"
