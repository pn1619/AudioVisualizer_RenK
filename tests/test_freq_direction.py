"""Frequency Direction option (build 14, v00.0B.10).

Covers the pure ``freq_order`` mapping (linear + folded, degenerate sizes) and that
the bar-style frequency modes (Spectrum / VU Meters / Dot Matrix) actually reorder
their output when the direction changes.
"""

from __future__ import annotations

import numpy as np
import pygame
import pytest

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.visuals._helpers import freq_order
from audio_visualizer.visuals.matrix import Matrix
from audio_visualizer.visuals.meters import Meters
from audio_visualizer.visuals.spectrum import Spectrum

_LH, _HL, _CO, _OC = 0, 1, 2, 3


def _gradient_frame(n: int = 32) -> AnalysisFrame:
    """Band energies that ramp 0->1 so any reorder visibly changes the image."""
    return AnalysisFrame(
        waveform_mono=np.zeros(256, dtype=np.float32),
        band_energies=np.linspace(0.05, 1.0, n, dtype=np.float32),
        rms=0.5,
        peak=1.0,
        sample_rate=48000,
        timestamp=0.0,
        onset=0.2,
    )


@pytest.mark.parametrize("n", [0, 1, 2, 7, 8, 32])
def test_freq_order_linear_is_a_permutation(n: int) -> None:
    lh = freq_order(n, _LH)
    hl = freq_order(n, _HL)
    assert lh.tolist() == list(range(n))
    assert hl.tolist() == list(range(n))[::-1]
    # Both are exact permutations of 0..n-1.
    assert sorted(lh.tolist()) == list(range(n))
    assert sorted(hl.tolist()) == list(range(n))


@pytest.mark.parametrize("n", [2, 7, 8, 33])
def test_freq_order_folded_is_symmetric(n: int) -> None:
    co = freq_order(n, _CO)
    oc = freq_order(n, _OC)
    for arr in (co, oc):
        assert arr.tolist() == arr[::-1].tolist()  # mirrored about center
        assert arr.min() >= 0 and arr.max() <= n - 1


@pytest.mark.parametrize("n", [7, 8, 33])
def test_freq_order_folded_orientation(n: int) -> None:
    """With a real center, Center->Out reads higher bands at the edges; Out->Center inverts."""
    co = freq_order(n, _CO)
    oc = freq_order(n, _OC)
    assert co[0] > co[n // 2]
    assert oc[0] < oc[n // 2]


def _array(mode, frame, direction: int) -> np.ndarray:
    mode.set_option_index("freqdir", direction)
    mode.on_enter()
    surface = pygame.Surface((220, 160))
    mode.draw(surface, frame, dt=1 / 60)
    return pygame.surfarray.array3d(surface).copy()


@pytest.mark.parametrize("factory", [Spectrum, Meters, Matrix])
def test_direction_changes_output(factory) -> None:
    """Low->High and High->Low must render differently for a ramped spectrum."""
    frame = _gradient_frame()
    low_high = _array(factory(), frame, _LH)
    high_low = _array(factory(), frame, _HL)
    assert not np.array_equal(low_high, high_low)


@pytest.mark.parametrize("factory", [Spectrum, Meters, Matrix])
@pytest.mark.parametrize("direction", [_LH, _HL, _CO, _OC])
def test_all_directions_draw_without_error(factory, direction: int) -> None:
    _array(factory(), _gradient_frame(), direction)  # must not raise
