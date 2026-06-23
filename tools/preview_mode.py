"""Headless preview renderer for visual modes (dev cross-check tool).

Renders a registered visual mode for a few seconds of *synthetic* audio and saves
the final frame (or a grid of frames) to a PNG, so we can eyeball a new mode against
its concept art without launching the full app. Headless via the SDL dummy driver.

Usage (from repo root, with the project venv active)::

    python tools/preview_mode.py <mode_key> <out.png> [--size WxH] [--frames N]
        [--seconds S] [--opt key=index ...] [--grid]

Not shipped in the exe; a developer aid only.
"""

from __future__ import annotations

import argparse
import math
import os

import numpy as np

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402  (must follow the SDL env setup)

from audio_visualizer.audio.frame import AnalysisFrame  # noqa: E402
from audio_visualizer.visuals import registry  # noqa: E402
from audio_visualizer.visuals.base import Theme  # noqa: E402

_BANDS = 64


def _synthetic_frame(t: float, sample_rate: int = 48000) -> AnalysisFrame:
    """A lively, deterministic fake frame at time ``t`` (seconds).

    Bass thumps on a 2 Hz beat, mids/treble wander, and onset spikes on the beat —
    enough motion to exercise band-, level-, and onset-driven modes.
    """
    beat_phase = (t * 2.0) % 1.0
    beat = math.exp(-((beat_phase / 0.18) ** 2))  # sharp thump each beat
    idx = np.arange(_BANDS, dtype=np.float32) / _BANDS
    bass = (0.85 * beat) * np.exp(-((idx - 0.04) ** 2) / 0.01)
    mids = 0.5 * (0.5 + 0.5 * np.sin(t * 1.7 + idx * 18.0)) * np.exp(-((idx - 0.4) ** 2) / 0.05)
    treble = 0.35 * (0.5 + 0.5 * np.sin(t * 5.3 + idx * 40.0)) * np.exp(-((idx - 0.8) ** 2) / 0.08)
    bands = np.clip(bass + mids + treble + 0.08, 0.0, 1.0).astype(np.float32)

    n = 512
    tt = np.linspace(0.0, 1.0, n, dtype=np.float32)
    wave = (
        0.5 * np.sin(2 * np.pi * (4 * tt + t))
        + 0.3 * np.sin(2 * np.pi * (11 * tt - t * 0.7))
        + 0.2 * beat * np.sin(2 * np.pi * 2 * tt)
    ).astype(np.float32)

    rms = float(0.18 + 0.45 * beat + 0.1 * math.sin(t * 0.9))
    peak = float(min(1.0, abs(wave).max()))
    onset = float(beat if beat > 0.4 else 0.0)
    return AnalysisFrame(
        wave, bands, rms=rms, peak=peak, sample_rate=sample_rate, timestamp=t, onset=onset
    )


def _render(args: argparse.Namespace) -> None:
    pygame.init()
    registry.discover()
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    w, h = (int(v) for v in args.size.lower().split("x"))
    visual = registry.create(args.mode, reduce_motion=False)
    visual.theme = Theme()
    for spec in args.opt or []:
        key, _, idx = spec.partition("=")
        visual.set_option_index(key, int(idx))
    visual.on_enter()

    surface = pygame.Surface((w, h))
    dt = args.seconds / max(1, args.frames)
    saved: list[pygame.Surface] = []
    grab_at = {int(args.frames * f) for f in (0.5, 0.75, 1.0)} if args.grid else {args.frames}
    for i in range(1, args.frames + 1):
        surface.fill((0, 0, 0))
        visual.draw(surface, _synthetic_frame(i * dt), dt)
        if i in grab_at:
            saved.append(surface.copy())

    if args.grid and len(saved) > 1:
        cols = len(saved)
        out = pygame.Surface((w * cols, h))
        for i, s in enumerate(saved):
            out.blit(s, (w * i, 0))
        pygame.image.save(out, args.out)
    else:
        pygame.image.save(saved[-1], args.out)
    print(f"saved {args.out} ({args.mode}, {w}x{h}, {args.frames} frames)")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", help="registered mode key, e.g. test_dna")
    p.add_argument("out", help="output PNG path")
    p.add_argument("--size", default="960x540")
    p.add_argument("--frames", type=int, default=180)
    p.add_argument("--seconds", type=float, default=3.0)
    p.add_argument("--opt", action="append", help="option override key=index (repeatable)")
    p.add_argument("--grid", action="store_true", help="save a 3-up grid of mid/late frames")
    _render(p.parse_args())


if __name__ == "__main__":
    main()
