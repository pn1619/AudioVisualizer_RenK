"""Bake the RenK app icon from a source artwork PNG (one-off asset tool).

Center-crops the source to a square, rounds the corners (transparent outside the
badge), and writes:

* ``src/audio_visualizer/assets/renk_icon.png`` - 256px window/taskbar icon.
* ``assets/icon.ico`` - multi-size icon PyInstaller bakes into the .exe.

Usage::

    .venv/Scripts/python tools/prep_icon.py [SOURCE.png]

Requires Pillow (dev-only; not a runtime dependency). Re-run only when the source
artwork changes.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

_REPO = Path(__file__).resolve().parent.parent
_PNG_OUT = _REPO / "src" / "audio_visualizer" / "assets" / "renk_icon.png"
_ICO_OUT = _REPO / "assets" / "icon.ico"
_ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
_CORNER_RADIUS_FRAC = 0.22  # rounded-square corner radius as a fraction of the side


def _square_crop(img: Image.Image) -> Image.Image:
    side = min(img.size)
    left = (img.width - side) // 2
    top = (img.height - side) // 2
    return img.crop((left, top, left + side, top + side))


def _round_corners(img: Image.Image) -> Image.Image:
    """Return ``img`` (RGBA) with a rounded-square alpha mask applied."""
    size = img.size[0]
    radius = int(size * _CORNER_RADIUS_FRAC)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: prep_icon.py SOURCE.png", file=sys.stderr)
        return 2
    src = Image.open(sys.argv[1]).convert("RGBA")
    square = _round_corners(_square_crop(src).resize((256, 256), Image.LANCZOS))

    _PNG_OUT.parent.mkdir(parents=True, exist_ok=True)
    _ICO_OUT.parent.mkdir(parents=True, exist_ok=True)
    square.save(_PNG_OUT)
    square.save(_ICO_OUT, sizes=[(s, s) for s in _ICO_SIZES])
    print(f"wrote {_PNG_OUT}")
    print(f"wrote {_ICO_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
