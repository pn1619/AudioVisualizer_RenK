"""Phase 0B-c (build 11): music-driven Beat Buttons (Rnd / Next auto-press)."""

from __future__ import annotations

import pygame
import pytest

from audio_visualizer.beat_trigger import BeatTrigger
from audio_visualizer.config import BEAT_SENSITIVITY_LABELS
from audio_visualizer.ui.beat_panel import BeatPanel


@pytest.fixture(scope="module", autouse=True)
def _pygame_ready():
    pygame.init()
    pygame.display.set_mode((10, 10))
    yield
    pygame.quit()


def _drive(trigger: BeatTrigger, *, beats: int, gap_s: float, onset: float = 0.8) -> int:
    """Feed steady frames at 60fps with a strong onset spike every ``gap_s`` seconds."""
    dt = 1.0 / 60.0
    fired = 0
    t_since_beat = 0.0
    for _ in range(int(beats * gap_s / dt) + 1):
        t_since_beat += dt
        spike = onset if t_since_beat >= gap_s else 0.02
        if t_since_beat >= gap_s:
            t_since_beat = 0.0
        fired += len(trigger.update(spike, is_silent=False, dt=dt))
    return fired


def test_default_is_off_and_emits_nothing() -> None:
    trigger = BeatTrigger()
    assert trigger.any_enabled() is False
    assert _drive(trigger, beats=20, gap_s=0.3) == 0


def test_silence_never_triggers() -> None:
    trigger = BeatTrigger({"randomize": 4})  # Max
    fired = 0
    for _ in range(600):  # 10s of loud-but-silent (is_silent gate on)
        fired += len(trigger.update(1.0, is_silent=True, dt=1 / 60))
    assert fired == 0


def test_cooldown_caps_rate_even_with_constant_onset() -> None:
    """A sustained high onset must not machine-gun: Max cooldown is ~0.45s."""
    trigger = BeatTrigger({"randomize": 4})
    fired = 0
    seconds = 5.0
    for _ in range(int(seconds * 60)):
        fired += len(trigger.update(1.0, is_silent=False, dt=1 / 60))
    # 5s / 0.45s cooldown -> at most ~11 fires; comfortably under a per-second flood.
    assert 1 <= fired <= 12


def test_low_sensitivity_fires_less_than_max() -> None:
    low = BeatTrigger({"randomize": 1})
    high = BeatTrigger({"randomize": 4})
    low_fires = _drive(low, beats=30, gap_s=0.6)
    high_fires = _drive(high, beats=30, gap_s=0.6)
    assert high_fires > low_fires
    assert low_fires >= 1  # strong beats still get through at the lowest level


def test_cycle_wraps_through_levels() -> None:
    trigger = BeatTrigger()
    assert trigger.level("next") == 0
    for expected in range(1, len(BEAT_SENSITIVITY_LABELS)):
        trigger.cycle("next")
        assert trigger.level("next") == expected
    trigger.cycle("next")  # wraps back to Off
    assert trigger.level("next") == 0


def test_unknown_action_is_ignored() -> None:
    trigger = BeatTrigger({"bogus": 3, "randomize": 2})
    assert trigger.level("randomize") == 2
    assert trigger.level("bogus") == 0
    trigger.set_level("bogus", 4)  # no-op, never raises
    assert "bogus" not in trigger.levels_dict()


def test_panel_click_cycles_via_callback() -> None:
    calls: list[str] = []
    panel = BeatPanel(cycle_action=calls.append)
    panel.set_state({"randomize": 0, "next": 0})
    panel.open = True
    canvas = pygame.Rect(0, 0, 1000, 700)
    row = panel._rows(panel._panel_rect(canvas))[0]
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=row.rect.center)
    assert panel.handle_event(event, canvas) is True
    assert calls == [row.action_key]


def test_settings_round_trip_beat_levels(tmp_path) -> None:
    from audio_visualizer import settings as settings_mod

    path = tmp_path / "settings.json"
    s = settings_mod.Settings(beat_levels={"randomize": 3, "next": 1})
    assert settings_mod.save(s, path) is True
    loaded = settings_mod.load(path)
    assert loaded.beat_levels == {"randomize": 3, "next": 1}


def test_settings_beat_levels_rejects_junk(tmp_path) -> None:
    from audio_visualizer import settings as settings_mod

    raw = settings_mod._beat_levels({"randomize": 99, "next": "x", "bogus": 2}, default={})
    assert raw == {"randomize": len(BEAT_SENSITIVITY_LABELS) - 1}  # clamped, junk dropped
