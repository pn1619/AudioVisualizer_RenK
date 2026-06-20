"""Beat Buttons: music auto-presses Rnd / Next (band-aware engine + indicator).

Originally added in build 11 (v00.0B.13); extended in build 12 (v00.0B.14) for the
per-action frequency band, expanded sensitivity ladder, and on-screen indicator.
"""

from __future__ import annotations

import numpy as np
import pygame
import pytest

from audio_visualizer.beat_trigger import BeatTrigger
from audio_visualizer.config import BEAT_SENSITIVITY_LABELS
from audio_visualizer.ui.beat_indicator import draw_beat_indicator
from audio_visualizer.ui.beat_panel import BeatPanel

_BANDS = 48
_MAX = len(BEAT_SENSITIVITY_LABELS) - 1


@pytest.fixture(scope="module", autouse=True)
def _pygame_ready():
    pygame.init()
    pygame.display.set_mode((10, 10))
    yield
    pygame.quit()


def _bands(level: float, band: str = "all") -> np.ndarray:
    """A band-energy vector with energy concentrated in one third (or all)."""
    arr = np.zeros(_BANDS, dtype=np.float32)
    third = _BANDS // 3
    if band == "bass":
        arr[:third] = level
    elif band == "mid":
        arr[third : 2 * third] = level
    elif band == "high":
        arr[2 * third :] = level
    else:
        arr[:] = level
    return arr


def _drive(trigger: BeatTrigger, *, beats: int, gap_s: float, band: str = "all") -> int:
    """Feed 60fps frames with an energy spike in ``band`` every ``gap_s`` seconds."""
    dt = 1.0 / 60.0
    fired = 0
    t = 0.0
    quiet = _bands(0.02, band)
    spike = _bands(0.85, band)
    for _ in range(int(beats * gap_s / dt) + 1):
        t += dt
        frame = spike if t >= gap_s else quiet
        if t >= gap_s:
            t = 0.0
        fired += len(trigger.update(frame, is_silent=False, dt=dt))
    return fired


def test_default_is_off_and_emits_nothing() -> None:
    trigger = BeatTrigger()
    assert trigger.any_enabled() is False
    assert _drive(trigger, beats=20, gap_s=0.3) == 0


def test_silence_never_triggers() -> None:
    trigger = BeatTrigger({"randomize": _MAX})
    fired = sum(len(trigger.update(_bands(1.0), is_silent=True, dt=1 / 60)) for _ in range(600))
    assert fired == 0


def test_cooldown_caps_rate_even_with_constant_energy() -> None:
    """A sustained tone must not machine-gun: even the top level has a ~0.18s cooldown."""
    trigger = BeatTrigger({"randomize": _MAX})
    fired = sum(
        len(trigger.update(_bands(1.0), is_silent=False, dt=1 / 60)) for _ in range(int(5.0 * 60))
    )
    assert 1 <= fired <= 32  # 5s / 0.18s -> ~27 max; still not a per-frame flood


def test_low_sensitivity_fires_less_than_max() -> None:
    low = BeatTrigger({"randomize": 1})
    high = BeatTrigger({"randomize": _MAX})
    low_fires = _drive(low, beats=40, gap_s=0.6)
    high_fires = _drive(high, beats=40, gap_s=0.6)
    assert high_fires > low_fires
    assert low_fires >= 1


def test_band_selectivity() -> None:
    """A bass-listening action ignores treble-only spikes."""
    trigger = BeatTrigger({"randomize": _MAX}, {"randomize": "bass"})
    bass_hits = _drive(trigger, beats=30, gap_s=0.5, band="bass")
    trigger.reset()
    treble_hits = _drive(trigger, beats=30, gap_s=0.5, band="high")
    assert bass_hits >= 1
    assert treble_hits == 0


def test_cycle_wraps_through_levels() -> None:
    trigger = BeatTrigger()
    for expected in range(1, len(BEAT_SENSITIVITY_LABELS)):
        trigger.cycle("next")
        assert trigger.level("next") == expected
    trigger.cycle("next")
    assert trigger.level("next") == 0


def test_cycle_band_wraps() -> None:
    trigger = BeatTrigger()
    assert trigger.band("next") == "all"
    seen = {trigger.band("next")}
    for _ in range(4):
        trigger.cycle_band("next")
        seen.add(trigger.band("next"))
    assert seen == {"all", "bass", "mid", "high"}
    assert trigger.band("next") == "all"  # wrapped back


def test_intensity_and_flash_track_beats() -> None:
    # A mid level (floor above the 0.02 "quiet" energy) so only the 0.9 spike fires;
    # the top levels intentionally fire on any sustained energy above their tiny floor.
    trigger = BeatTrigger({"randomize": 4})
    # Quiet frames -> low intensity.
    for _ in range(30):
        trigger.update(_bands(0.02), is_silent=False, dt=1 / 60)
    quiet_intensity = trigger.intensity
    fired = trigger.update(_bands(0.9), is_silent=False, dt=1 / 60)
    assert fired == ["randomize"]
    assert trigger.flash == pytest.approx(1.0)
    assert trigger.intensity > quiet_intensity


def test_unknown_action_is_ignored() -> None:
    trigger = BeatTrigger({"bogus": 3, "randomize": 2}, {"bogus": "bass"})
    assert trigger.level("randomize") == 2
    assert "bogus" not in trigger.levels_dict()
    assert "bogus" not in trigger.bands_dict()


def test_panel_dropdowns_route_callbacks() -> None:
    from audio_visualizer.config import BEAT_INDICATOR_POSITIONS

    calls: dict[str, object] = {}
    panel = BeatPanel(
        set_level=lambda a, i: calls.__setitem__("level", (a, i)),
        set_band=lambda a, b: calls.__setitem__("band", (a, b)),
        toggle_indicator=lambda: calls.__setitem__("indicator", True),
        set_position=lambda p: calls.__setitem__("position", p),
        set_shape=lambda s: calls.__setitem__("shape", s),
        set_fade=lambda f: calls.__setitem__("fade", f),
    )
    panel.set_state(
        {"randomize": 0, "next": 0}, {"randomize": "all", "next": "all"}, False, "top-right"
    )
    panel.open = True
    canvas = pygame.Rect(0, 0, 1100, 760)

    def _click(pos: tuple[int, int]) -> None:
        panel.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos), canvas)

    lay = panel._layout(canvas)
    action = lay.rows[0].action_key

    # Open the band dropdown, then pick "bass" (index 1 in BEAT_BANDS).
    _click(lay.rows[0].band_rect.center)
    _click(panel._band_dd[action]._option_rects()[1].center)
    # Open the sensitivity dropdown, then pick level index 5.
    _click(lay.rows[0].level_rect.center)
    _click(panel._level_dd[action]._option_rects()[5].center)
    # Indicator is a plain toggle.
    _click(lay.indicator.center)
    # Open the position dropdown, then pick index 1.
    _click(lay.position.center)
    _click(panel._position_dd._option_rects()[1].center)

    assert calls["band"] == (action, "bass")
    assert calls["level"] == (action, 5)
    assert calls["indicator"] is True
    assert calls["position"] == BEAT_INDICATOR_POSITIONS[1][0]


def test_indicator_draws_without_error() -> None:
    surface = pygame.Surface((640, 480))
    canvas = pygame.Rect(0, 0, 640, 480)
    for band in ("all", "bass", "mid", "high"):
        for pos in ("top-right", "center", "bottom-left"):
            draw_beat_indicator(surface, canvas, pos, intensity=0.7, band=band, flash=0.5)


def test_settings_round_trip_beat(tmp_path) -> None:
    from audio_visualizer import settings as settings_mod

    path = tmp_path / "settings.json"
    s = settings_mod.Settings(
        beat_levels={"randomize": 3, "next": 1},
        beat_bands={"randomize": "bass", "next": "high"},
        beat_indicator=True,
        beat_indicator_pos="center",
    )
    assert settings_mod.save(s, path) is True
    loaded = settings_mod.load(path)
    assert loaded.beat_levels == {"randomize": 3, "next": 1}
    assert loaded.beat_bands == {"randomize": "bass", "next": "high"}
    assert loaded.beat_indicator is True
    assert loaded.beat_indicator_pos == "center"


def test_settings_beat_rejects_junk() -> None:
    from audio_visualizer import settings as settings_mod

    levels = settings_mod._beat_levels({"randomize": 99, "next": "x", "bogus": 2}, default={})
    assert levels == {"randomize": _MAX}
    bands = settings_mod._beat_bands({"randomize": "ultrasound", "next": "mid"}, default={})
    assert bands == {"next": "mid"}
