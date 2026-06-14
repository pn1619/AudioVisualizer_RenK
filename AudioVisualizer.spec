# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: single-file Windows build of AudioVisualizer.

Critically bundles the PortAudio DLL that ships with pyaudiowpatch (the #1
packaging gotcha). Build via tools\\build-exe.ps1.
"""

import os
import sys

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

# Make the src/ package importable while this spec is evaluated.
sys.path.insert(0, os.path.abspath("src"))

# Pull in pyaudiowpatch's bundled PortAudio DLL.
binaries = collect_dynamic_libs("pyaudiowpatch")

# The visual modes are imported dynamically (registry.discover), so PyInstaller's
# static analysis can't see them. Collect them explicitly so discovery finds them
# inside the frozen bundle.
hiddenimports = ["pyaudiowpatch", *collect_submodules("audio_visualizer.visuals")]

a = Analysis(
    ["src/audio_visualizer/__main__.py"],
    pathex=["src"],
    binaries=binaries,
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AudioVisualizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
)
