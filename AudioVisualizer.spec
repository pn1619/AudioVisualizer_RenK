# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: single-file Windows build of AudioVisualizer.

Critically bundles the PortAudio DLL that ships with pyaudiowpatch (the #1
packaging gotcha). Build via tools\\build-exe.ps1.
"""

import os
import sys

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

# Make the src/ package importable while this spec is evaluated.
sys.path.insert(0, os.path.abspath("src"))

from audio_visualizer.config import APP_NAME, APP_VERSION  # noqa: E402

# Pull in pyaudiowpatch's bundled PortAudio DLL.
binaries = collect_dynamic_libs("pyaudiowpatch")

# Bundle packaged assets (the RenK logo PNG) into audio_visualizer/assets so the
# resource loader finds them under sys._MEIPASS in the frozen build.
_assets_src = os.path.abspath(os.path.join("src", "audio_visualizer", "assets"))
datas = [(_assets_src, os.path.join("audio_visualizer", "assets"))] if os.path.isdir(
    _assets_src
) else []

# The visual modes are imported dynamically (registry.discover), so PyInstaller's
# static analysis can't see them. Collect them explicitly so discovery finds them
# inside the frozen bundle.
hiddenimports = ["pyaudiowpatch", *collect_submodules("audio_visualizer.visuals")]

# Windows version resource derived from the single APP_VERSION (PP.FF.BB). Parts
# are parsed base-16 because FF uses hex from phase 10 on ("0A" == 10).
_parts = [int(p, 16) for p in APP_VERSION.split(".")]
_vtuple = tuple((_parts + [0, 0, 0, 0])[:4])
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=_vtuple, prodvers=_vtuple, mask=0x3F, flags=0x0, OS=0x40004,
                      fileType=0x1, subtype=0x0),
    kids=[
        StringFileInfo([
            StringTable("040904B0", [
                StringStruct("CompanyName", APP_NAME),
                StringStruct("FileDescription", "Windows system-audio visualizer"),
                StringStruct("FileVersion", APP_VERSION),
                StringStruct("InternalName", APP_NAME),
                StringStruct("OriginalFilename", f"{APP_NAME}.exe"),
                StringStruct("ProductName", APP_NAME),
                StringStruct("ProductVersion", APP_VERSION),
            ]),
        ]),
        VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
    ],
)

# Optional icon: drop assets/icon.ico into the repo and it's picked up automatically.
_icon = os.path.abspath(os.path.join("assets", "icon.ico"))
icon_arg = _icon if os.path.exists(_icon) else None

a = Analysis(
    ["src/audio_visualizer/__main__.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
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
    version=version_info,
    icon=icon_arg,
)
