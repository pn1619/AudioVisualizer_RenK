r"""Phase 0.5 capture spike: prove WASAPI loopback delivers samples.

Opens the default output device's loopback stream and prints RMS for ~5 seconds,
plus the device's native format. Run with audio playing, then with silence.

    .\.venv\Scripts\python tools\spike-loopback.py [seconds]

Throwaway diagnostic; the real implementation lives in
src/audio_visualizer/audio/capture.py.
"""

from __future__ import annotations

import sys
import time

import numpy as np
import pyaudiowpatch as pyaudio


def main(seconds: float = 5.0) -> int:
    pa = pyaudio.PyAudio()
    try:
        info = pa.get_default_wasapi_loopback()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: no loopback device: {exc}")
        pa.terminate()
        return 1

    rate = int(info["defaultSampleRate"])
    channels = max(1, int(info["maxInputChannels"]))
    print(f"Device : {info['name']}")
    print(f"Format : {rate} Hz, {channels} ch, int16 (loopback)")
    print(f"Reading {seconds:.0f}s ... play audio to see RMS rise, silence -> ~0\n")

    latest = {"rms": 0.0, "peak": 0.0}

    def callback(in_data, frame_count, time_info, status):  # type: ignore[no-untyped-def]
        raw = np.frombuffer(in_data, dtype=np.int16)
        if channels > 1:
            raw = raw.reshape(-1, channels).mean(axis=1)
        mono = raw.astype(np.float32) / 32768.0
        latest["rms"] = float(np.sqrt(np.mean(mono * mono))) if mono.size else 0.0
        latest["peak"] = float(np.max(np.abs(mono))) if mono.size else 0.0
        return (None, pyaudio.paContinue)

    stream = pa.open(
        format=pyaudio.paInt16,
        channels=channels,
        rate=rate,
        input=True,
        input_device_index=int(info["index"]),
        frames_per_buffer=1024,
        stream_callback=callback,
    )

    end = time.monotonic() + seconds
    try:
        while time.monotonic() < end:
            bar = "#" * int(min(1.0, latest["rms"] * 4) * 40)
            print(f"  RMS {latest['rms']:.4f}  peak {latest['peak']:.4f}  |{bar:<40}|", end="\r")
            time.sleep(0.1)
    finally:
        print()
        stream.stop_stream()
        stream.close()
        pa.terminate()
    print("\nDone.")
    return 0


if __name__ == "__main__":
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
    raise SystemExit(main(secs))
