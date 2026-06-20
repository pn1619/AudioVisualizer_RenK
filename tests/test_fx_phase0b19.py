"""Phase 0B-c (build 19): beat master switch, new laser shapes, new backdrops.

Covers the master On/Off for the Beat feature (settings preserved), the replaced
laser figures (Star / Butterfly), and the Background dropdown key round-trip.
"""

from __future__ import annotations

import math

import numpy as np

from audio_visualizer import settings as settings_mod
from audio_visualizer.app import _bg_num_key, _nearest
from audio_visualizer.beat_trigger import BeatTrigger
from audio_visualizer.config import BG_OPACITY_CHOICES, BG_SENSITIVITY_CHOICES
from audio_visualizer.settings import Settings


# -- beat master switch -------------------------------------------------------
def test_beat_master_switch_blocks_and_preserves() -> None:
    loud = np.full(48, 1.0, dtype=np.float32)
    bt = BeatTrigger(levels={"randomize": 9}, enabled=True)  # max sensitivity

    fired = [a for _ in range(20) for a in bt.update(loud, is_silent=False, dt=0.05)]
    assert "randomize" in fired  # enabled + loud -> fires
    assert bt.active() is True

    bt.set_enabled(False)
    assert bt.is_enabled() is False
    assert bt.active() is False  # off, regardless of the level still being set
    after = [a for _ in range(20) for a in bt.update(loud, is_silent=False, dt=0.05)]
    assert after == []
    assert bt.intensity == 0.0

    bt.set_enabled(True)  # the per-action level was preserved, so it's active again
    assert bt.level("randomize") == 9
    assert bt.active() is True


def test_settings_round_trip_beat_enabled(tmp_path) -> None:
    path = tmp_path / "settings.json"
    assert settings_mod.save(Settings(beat_enabled=False), path)
    assert settings_mod.load(path).beat_enabled is False
    # A file missing the key defaults to On.
    path.write_text('{"schema_version": 18}', encoding="utf-8")
    assert settings_mod.load(path).beat_enabled is True


# -- laser shapes -------------------------------------------------------------
def test_laser_star_and_butterfly_produce_finite_points() -> None:
    from audio_visualizer.visuals.laser import Laser

    laser = Laser()
    star = laser._star(100.0, 100.0, 50.0, 50.0, low=0.5, high=0.5)
    butterfly = laser._butterfly(100.0, 100.0, 50.0, 50.0, low=0.5, high=0.5)
    assert len(star) >= 10  # at least a 5-spike star (2 pts/spike + close)
    assert len(butterfly) > 100  # a dense traced curve
    assert all(math.isfinite(x) and math.isfinite(y) for x, y in star + butterfly)


def test_laser_star_spike_count_rides_highs() -> None:
    from audio_visualizer.visuals.laser import Laser

    laser = Laser()
    few = laser._star(0.0, 0.0, 50.0, 50.0, low=0.0, high=0.0)
    many = laser._star(0.0, 0.0, 50.0, 50.0, low=0.0, high=1.0)
    assert len(many) > len(few)  # more highs -> more spikes


# -- background dropdown key round-trip --------------------------------------
def test_bg_num_keys_decode_to_their_choice() -> None:
    for value in BG_SENSITIVITY_CHOICES:
        assert _nearest(float(_bg_num_key(value)), BG_SENSITIVITY_CHOICES, -1.0) == value
    for value in BG_OPACITY_CHOICES:
        assert _nearest(float(_bg_num_key(value)), BG_OPACITY_CHOICES, -1.0) == value
