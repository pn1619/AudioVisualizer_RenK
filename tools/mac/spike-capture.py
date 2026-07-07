#!/usr/bin/env python3
"""Phase 0.5 macOS capture spike: prove PortAudio delivers input samples.

Lists input devices, opens one (default or ``--device``), prints RMS/peak for
~5 seconds. Run with audio playing (mic, BlackHole, or routed system audio).

    ./tools/mac/spike-capture.py
    ./tools/mac/spike-capture.py --list
    ./tools/mac/spike-capture.py --device "BlackHole" --seconds 8

Throwaway diagnostic; the real implementation will live in
``src/audio_visualizer/audio/capture_mac.py`` (PR2+). Requires ``sounddevice``
(``requirements-mac.txt``).
"""

from __future__ import annotations

import argparse
import sys
import time

import numpy as np

_DEFAULT_SECONDS = 5.0
_PRINT_HZ = 10.0


def _list_devices() -> int:
    import sounddevice as sd

    print("Input devices (PortAudio):")
    hostapis = {i: api["name"] for i, api in enumerate(sd.query_hostapis())}
    for idx, dev in enumerate(sd.query_devices()):
        if int(dev["max_input_channels"]) < 1:
            continue
        api = hostapis.get(int(dev["hostapi"]), "?")
        default_in = ""
        try:
            default = sd.query_devices(kind="input")
            if int(default["index"]) == idx:
                default_in = " [default input]"
        except Exception:
            pass
        print(
            f"  [{idx}] {dev['name']} — {int(dev['max_input_channels'])} ch, "
            f"{int(dev['default_samplerate'])} Hz ({api}){default_in}"
        )
    return 0


def _resolve_device_index(name_or_index: str | None) -> tuple[int, dict]:
    import sounddevice as sd

    if name_or_index is None:
        dev = sd.query_devices(kind="input")
        return int(dev["index"]), dev
    if name_or_index.isdigit():
        idx = int(name_or_index)
        return idx, sd.query_devices(idx)
    needle = name_or_index.casefold()
    for idx, dev in enumerate(sd.query_devices()):
        if int(dev["max_input_channels"]) < 1:
            continue
        if needle in str(dev["name"]).casefold():
            return idx, dev
    raise SystemExit(f"ERROR: no input device matching {name_or_index!r}")


def _run(device: str | None, seconds: float) -> int:
    import sounddevice as sd

    idx, info = _resolve_device_index(device)
    rate = int(info["default_samplerate"])
    channels = max(1, int(info["max_input_channels"]))
    name = str(info["name"])

    print(f"Device : [{idx}] {name}")
    print(f"Format : {rate} Hz, {channels} ch, float32 (input)")
    print(f"Reading {seconds:.0f}s ... play audio to see RMS rise, silence -> ~0\n")

    latest = {"rms": 0.0, "peak": 0.0}

    def callback(indata, frames, time_info, status) -> None:  # type: ignore[no-untyped-def]
        if status:
            print(f"  [status] {status}", file=sys.stderr)
        mono = indata.mean(axis=1) if indata.ndim > 1 else indata
        mono = mono.astype(np.float32, copy=False)
        latest["rms"] = float(np.sqrt(np.mean(mono * mono))) if mono.size else 0.0
        latest["peak"] = float(np.max(np.abs(mono))) if mono.size else 0.0

    interval = 1.0 / _PRINT_HZ
    with sd.InputStream(
        device=idx,
        channels=channels,
        samplerate=rate,
        dtype="float32",
        callback=callback,
    ):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            print(f"  RMS {latest['rms']:.4f}  peak {latest['peak']:.4f}")
            time.sleep(interval)

    print("\nOK — samples received.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="macOS capture spike (PortAudio / sounddevice)")
    parser.add_argument("--list", action="store_true", help="List input devices and exit")
    parser.add_argument(
        "--device",
        metavar="NAME|INDEX",
        help="Input device (substring match or index); default = system default input",
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=_DEFAULT_SECONDS,
        help=f"How long to print RMS (default {_DEFAULT_SECONDS:g})",
    )
    args = parser.parse_args(argv)
    if args.list:
        return _list_devices()
    try:
        return _run(args.device, max(0.5, args.seconds))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
