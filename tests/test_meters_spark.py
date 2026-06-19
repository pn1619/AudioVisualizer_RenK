"""VU Meters needle sparks must fly along the needle (build 15, v00.0B.11).

The tip is positioned in normalized space (x/w, y/h); the velocity must be
aspect-compensated so the spark traces the needle's on-screen angle even on a
very non-square (widescreen) surface.
"""

from __future__ import annotations

import math

import pygame
import pytest

from audio_visualizer.visuals.meters import Meters


@pytest.fixture(scope="module", autouse=True)
def _pygame_ready():
    pygame.init()
    pygame.display.set_mode((10, 10))
    yield
    pygame.quit()


@pytest.mark.parametrize("angle_deg", [40.0, 90.0, 140.0])
def test_needle_spark_follows_needle_angle_on_wide_window(angle_deg: float) -> None:
    w, h = 960, 200  # extreme widescreen exaggerates any aspect skew
    meters = Meters()
    meters._spark_mult = 1.0
    meters._sparks.cap = 5000
    cell = pygame.Rect(400, 0, 90, 180)
    angle = math.radians(angle_deg)

    meters._emit_needle_tip(cell, level=0.7, count=2000, hue=0.5, angle=angle, w=w, h=h)
    sparks = meters._sparks._sparks
    assert sparks, "expected needle sparks to be emitted"

    # Mean velocity -> pixel space (the symmetric spread averages out).
    mean_vx = sum(s.vx for s in sparks) / len(sparks) * w
    mean_vy = sum(s.vy for s in sparks) / len(sparks) * h
    emit_angle = math.atan2(-mean_vy, mean_vx)  # screen y is down
    assert abs(emit_angle - angle) < 0.08  # ~4.5 deg of the actual needle angle
