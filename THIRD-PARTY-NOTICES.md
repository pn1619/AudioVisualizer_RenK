# Third-Party Notices

AudioVisualizer is distributed as a single `.exe` that bundles the third-party
components below. Each remains under its own license; copies/links are provided
here to satisfy their notice requirements. AudioVisualizer itself is proprietary
software — all rights reserved (see `LICENSE`).

---

## pygame — LGPL 2.1

- Project: https://www.pygame.org/ — Source: https://github.com/pygame/pygame
- License: GNU Lesser General Public License v2.1 (https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html)
- Used **unmodified** and loaded as a dynamic dependency. Per the LGPL, you may
  obtain pygame's source at the link above and replace the bundled library with a
  compatible version. SDL2 (zlib license) ships with pygame.

## NumPy — BSD 3-Clause

- Project: https://numpy.org/ — Source: https://github.com/numpy/numpy
- License: BSD 3-Clause (https://github.com/numpy/numpy/blob/main/LICENSE.txt)
- Copyright (c) 2005–present, NumPy Developers.

## PyAudioWPatch — MIT

- Project/Source: https://github.com/s0d3s/PyAudioWPatch
- License: MIT (https://github.com/s0d3s/PyAudioWPatch/blob/master/LICENSE.txt)
- A PyAudio fork adding WASAPI loopback support. PyAudio itself is MIT-licensed.

## PortAudio — MIT-style

- Project/Source: http://www.portaudio.com/ — https://github.com/PortAudio/portaudio
- License: MIT-style (http://www.portaudio.com/license.html)
- The PortAudio DLL is bundled (via `pyaudiowpatch`) so loopback capture works in
  the packaged executable.

---

To regenerate exact installed versions of Python dependencies:

```powershell
.\.venv\Scripts\python -m pip freeze > requirements.lock.txt
```
