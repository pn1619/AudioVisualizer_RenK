"""Fractal Tree: the concept art itself, brought to life by the music.

Per request, this mode reproduces ``assets/concept-art/concept-07-fractaltree.png``
*exactly* -- because it **renders that artwork directly** as the (static) tree -- and then
animates it with the audio:

* **Flowers (shape-matched glow).** Each painted bloom lights up *in its own petal shape*:
  a masked copy of the bloom's own pixels is added back over itself, brightening with the
  music, so the glow overlays the flower perfectly (no circular blob). Onsets pop the blooms
  bigger and emit drifting pink particles.
* **Tree body (frequency glow).** The teal trunk/roots brighten with the **bass** and the
  pink foliage shimmers with the **treble** -- the bioluminescent palette reacting to the
  spectrum, painted only onto the parts of the image that are already those colours.
* **Energy flow.** Bright bands of light **run up the tree from the roots to the blooms**,
  tracing the real trunk/branches. A geodesic "distance-from-roots" field is computed once
  (multi-source BFS over the tree's bright pixels seeded at the base), then moving bands along
  that field are added back -- brightness and speed react to the music.

The artwork (with its title/legend corner cleaned off) is bundled as
``assets/fractal_tree.png``, loaded once, fit to the canvas and cached. The tree itself never
changes geometry; only light is added on top. Its near-black background is **luminance-keyed to
transparent** so the mode composites over the app's background layer instead of overwriting it --
the tree floats on whatever background effect is running, with the dark gaps showing it through.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass

import numpy as np
import pygame
import pygame.surfarray

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import ONSET_THRESHOLD
from audio_visualizer.resources import asset_path
from audio_visualizer.visuals._helpers import Color, clamp, scale_color
from audio_visualizer.visuals.base import BaseVisualizer, ModeOption, OptionChoice, Theme
from audio_visualizer.visuals.registry import register

logger = logging.getLogger(__name__)

_IMAGE_NAME = "fractal_tree.png"
_PARTICLE_CAP = 520
_WAVES = 1.8  # how many energy bands ride the tree at once


@dataclass
class _Flower:
    nx: float  # normalised centre in the fitted image
    ny: float
    tint: Color
    patch: pygame.Surface  # masked copy of the bloom's own pixels (non-petal = black)
    px: int  # top-left of the patch in canvas pixels
    py: int


@dataclass
class _Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    color: Color
    size: float


_PRESET = ModeOption(
    "preset",
    "Preset",
    (
        OptionChoice("Custom", 0),
        OptionChoice("Bloom", 1),
        OptionChoice("Sparkle", 2),
        OptionChoice("Calm", 3),
    ),
    default_index=1,
)
_GLOW = ModeOption(
    "t3glow",
    "Flower Glow",
    (OptionChoice("Soft", 0.6), OptionChoice("Normal", 1.0), OptionChoice("Bright", 1.5)),
    default_index=1,
)
_BODY = ModeOption(
    "t3body",
    "Tree Glow",
    (OptionChoice("Off", 0.0), OptionChoice("Subtle", 0.55), OptionChoice("Pulse", 1.0)),
    default_index=1,
)
_FLOW = ModeOption(
    "t3flow",
    "Energy Flow",
    (OptionChoice("Off", 0.0), OptionChoice("Stream", 1.0), OptionChoice("Surge", 1.7)),
    default_index=1,
)
_PARTICLES = ModeOption(
    "t3particles",
    "Particles",
    (OptionChoice("Off", 0.0), OptionChoice("Soft", 1.0), OptionChoice("Lush", 2.0)),
    default_index=2,
)
_REACT = ModeOption(
    "t3react",
    "Reactivity",
    (OptionChoice("Calm", 0.4), OptionChoice("Normal", 1.0), OptionChoice("Punch", 1.8)),
    default_index=1,
)
_DRIFT = ModeOption(
    "t3drift",
    "Drift",
    (OptionChoice("Float", 0), OptionChoice("Burst", 1), OptionChoice("Swirl", 2)),
    default_index=0,
)


@register(key="fractal_tree", display_name="Fractal Tree", order=95)
class FractalTree(BaseVisualizer):
    """The concept-art fractal tree rendered as-is, lit by shape-matched, audio-reactive glow."""

    OPTIONS = (_PRESET, _GLOW, _BODY, _FLOW, _PARTICLES, _REACT, _DRIFT)
    PRESETS = {
        1: {"t3glow": 1, "t3body": 1, "t3flow": 1, "t3particles": 2, "t3react": 1, "t3drift": 0},
        2: {"t3glow": 2, "t3body": 2, "t3flow": 2, "t3particles": 2, "t3react": 2, "t3drift": 1},
        3: {"t3glow": 0, "t3body": 1, "t3flow": 1, "t3particles": 1, "t3react": 0, "t3drift": 0},
    }

    def __init__(self, reduce_motion: bool = False, theme: Theme | None = None) -> None:
        super().__init__(reduce_motion, theme)
        self._t = 0.0
        self._src: pygame.Surface | None = None
        self._scaled: pygame.Surface | None = None
        self._cool_arr: np.ndarray | None = None  # teal pixels only (bass glow), float
        self._warm_arr: np.ndarray | None = None  # pink pixels only (treble glow), float
        self._glow_small: pygame.Surface | None = None  # reused low-res body-glow buffer
        self._phase: np.ndarray | None = None  # geodesic dist-from-roots (0..1, -1 off-tree)
        self._flow_base: np.ndarray | None = None  # brightened tree colour for the running light
        self._phase_w: np.ndarray | None = None  # phase * _WAVES * tau (precomputed band arg)
        self._comb: np.ndarray | None = None  # reused body-light accumulator
        self._size: tuple[int, int] = (0, 0)
        self._fit = (0, 0, 1, 1)
        self._flowers_norm: list[tuple[float, float, Color]] = []  # detected once, size-free
        self._flowers: list[_Flower] = []  # rebuilt per size (carry the pixel patches)
        self._bloom: np.ndarray = np.zeros(0, dtype=np.float32)
        self._particles: list[_Particle] = []
        self._rng = random.Random(7)
        self._load_failed = False
        self._baseline = 0.0

    def on_enter(self) -> None:
        self._t = 0.0
        self._particles.clear()
        self._rng.seed(7)

    # -- asset + detection ----------------------------------------------------
    def _ensure_source(self) -> None:
        if self._src is not None or self._load_failed:
            return
        path = asset_path(_IMAGE_NAME)
        if path is None:
            self._load_failed = True
            logger.warning("Fractal-tree artwork %r missing; drawing empty background", _IMAGE_NAME)
            return
        try:
            self._src = pygame.image.load(str(path))
        except pygame.error:
            self._load_failed = True
            logger.exception("Failed to load fractal-tree artwork")
            return
        self._flowers_norm = _detect_flowers(self._src)

    def _ensure_scaled(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        if self._src is None or self._size == (w, h):
            return
        iw, ih = self._src.get_size()
        scale = min(w / iw, h / ih)
        fw, fh = max(1, int(iw * scale)), max(1, int(ih * scale))
        # Match the target surface's pixel format so per-frame blits skip conversion.
        base = pygame.transform.smoothscale(self._src, (fw, fh)).convert(surface)
        # Key the near-black background to transparent so the tree composites over the app's
        # background layer instead of painting an opaque black rectangle over it.
        self._scaled = _luma_keyed(base)
        ox, oy = (w - fw) // 2, (h - fh) // 2
        self._fit = (ox, oy, fw, fh)
        self._size = (w, h)
        self._particles.clear()
        # The body glow is soft, so build the colour layers at low res (cheap to modulate
        # per frame) and upscale once when compositing -- a free blur, and far faster.
        gf = min(1.0, 480.0 / max(fw, fh))
        gs = (max(1, int(fw * gf)), max(1, int(fh * gf)))
        small = pygame.transform.smoothscale(base, gs)
        # Keep the colour layers as float arrays so per-frame modulation is a cheap numpy
        # combine; only a single upscale + additive blit touches full-resolution pixels.
        self._cool_arr = _color_array(small, warm=False)
        self._warm_arr = _color_array(small, warm=True)
        self._phase, self._flow_base = _flow_field(small)
        self._phase_w = self._phase * (_WAVES * math.tau)
        self._comb = np.zeros_like(self._cool_arr)
        self._glow_small = pygame.Surface(gs).convert(surface)
        self._build_flower_patches(surface, ox, oy, fw, fh)

    def _build_flower_patches(
        self, surface: pygame.Surface, ox: int, oy: int, fw: int, fh: int
    ) -> None:
        self._flowers = []
        span = max(fw, fh)
        for nx, ny, tint in self._flowers_norm:
            pr = max(6, int(span * 0.05))
            cx, cy = int(nx * fw), int(ny * fh)
            rect = pygame.Rect(cx - pr, cy - pr, pr * 2, pr * 2).clip(self._scaled.get_rect())
            if rect.width < 4 or rect.height < 4:
                continue
            patch = _petal_patch(self._scaled.subsurface(rect)).convert(surface)
            self._flowers.append(_Flower(nx, ny, tint, patch, ox + rect.x, oy + rect.y))
        self._bloom = np.zeros(len(self._flowers), dtype=np.float32)

    # -- frame ----------------------------------------------------------------
    def draw(self, surface: pygame.Surface, frame: AnalysisFrame | None, dt: float) -> None:
        w, h = surface.get_size()
        if w < 8 or h < 8:
            return
        self._t += dt
        self._ensure_source()
        self._ensure_scaled(surface)

        # No opaque fill: the app has already drawn the background layer onto ``surface`` and the
        # keyed artwork (transparent where the art is black) is alpha-blended over it.
        if self._scaled is not None:
            surface.blit(self._scaled, (self._fit[0], self._fit[1]))
        if not self._flowers:
            return

        bands = None if frame is None else frame.band_energies
        n = 0 if bands is None else bands.size
        low = 0.0 if not n else float(np.mean(bands[: max(1, n // 4)]))
        high = 0.0 if not n else float(np.mean(bands[n // 2 :]))
        rms = 0.0 if frame is None else min(1.0, frame.rms)
        onset = 0.0 if frame is None else frame.onset

        self._body_effects(surface, low, high, rms)
        self._update_blooms(dt, onset, high, rms)
        self._update_particles(dt)
        self._flower_glow(surface)

    # -- tree-body light: frequency glow + energy flow ------------------------
    def _body_effects(self, surface: pygame.Surface, low: float, high: float, rms: float) -> None:
        """Composite the body's added light (glow + running energy) in one low-res pass."""
        if self._cool_arr is None or self._glow_small is None:
            return
        body = float(self.option("t3body"))
        flow = float(self.option("t3flow"))
        flow_on = flow > 0.0 and not self.reduce_motion and self._phase is not None
        if body <= 0.0 and not flow_on:
            return
        ox, oy, fw, fh = self._fit
        comb = self._comb
        comb.fill(0.0)
        if body > 0.0:
            sb = clamp(body * (0.9 * low + 0.1))  # bass -> teal trunk/roots
            sw = clamp(body * (0.9 * high + 0.1))  # treble -> pink foliage
            comb += self._cool_arr * sb
            comb += self._warm_arr * sw
        if flow_on:
            comb += self._flow_layer(flow, rms)
        np.clip(comb, 0, 255, out=comb)
        pygame.surfarray.blit_array(self._glow_small, comb.astype(np.uint8))
        big = pygame.transform.scale(self._glow_small, (fw, fh))  # diffuse, so fast scale is fine
        surface.blit(big, (ox, oy), special_flags=pygame.BLEND_ADD)

    def _flow_layer(self, flow: float, rms: float) -> np.ndarray:
        """Narrow bright bands travelling up the dist-from-roots field, lighting the branches."""
        amp = flow * (0.22 + 0.95 * rms)  # louder music -> brighter energy
        speed = 0.30 + 0.85 * rms  # ... and faster running
        # Bands repeat along the tree (``_WAVES`` periods) and sweep root -> tips with time.
        band = 0.5 + 0.5 * np.cos(self._phase_w - (self._t * speed * math.tau))
        band *= band  # ^2
        band *= band  # ^4
        band *= band  # ^8 -- narrow crests, dark gaps, via cheap multiplies
        band *= amp
        return band[:, :, None] * self._flow_base

    # -- bloom envelopes + emission -------------------------------------------
    def _update_blooms(self, dt: float, onset: float, high: float, rms: float) -> None:
        n = len(self._flowers)
        if self._bloom.shape[0] != n:
            self._bloom = np.zeros(n, dtype=np.float32)
        self._bloom *= math.exp(-dt * 2.2)
        self._baseline = 0.18 + 0.45 * high + 0.18 * rms
        if onset >= ONSET_THRESHOLD and not self.reduce_motion:
            react = float(self.option("t3react"))
            for _ in range(max(2, int(n * (0.3 + 0.4 * react)))):
                self._bloom[self._rng.randrange(n)] = 1.0
            self._emit(onset)

    def _emit(self, onset: float) -> None:
        amount = float(self.option("t3particles"))
        if amount <= 0.0 or self.reduce_motion:
            return
        _ox, _oy, fw, _fh = self._fit
        drift = int(self.option("t3drift"))
        per = int((3 + 5 * amount) * clamp(0.4 + onset))
        for i, fl in enumerate(self._flowers):
            if float(self._bloom[i]) < 0.5:
                continue
            fx = fl.px + fl.patch.get_width() * 0.5
            fy = fl.py + fl.patch.get_height() * 0.5
            for _ in range(per):
                if len(self._particles) >= _PARTICLE_CAP:
                    break
                self._particles.append(self._spawn(fx, fy, fl.tint, drift, fw))

    def _spawn(self, fx: float, fy: float, tint: Color, drift: int, fw: int) -> _Particle:
        rng = self._rng
        speed = fw * rng.uniform(0.02, 0.07)
        ang = rng.uniform(0, math.tau)
        if drift == 0:
            vx, vy = math.cos(ang) * speed * 0.4, -abs(rng.gauss(0.6, 0.3)) * speed
        elif drift == 1:
            vx, vy = math.cos(ang) * speed, math.sin(ang) * speed
        else:
            vx, vy = -math.sin(ang) * speed, math.cos(ang) * speed - speed * 0.4
        life = rng.uniform(0.8, 1.8)
        col = tint if rng.random() < 0.8 else (120, 230, 235)
        return _Particle(fx, fy, vx, vy, life, life, col, rng.uniform(0.7, 1.6))

    def _update_particles(self, dt: float) -> None:
        grav = -8.0 if int(self.option("t3drift")) == 0 else 18.0
        alive: list[_Particle] = []
        for p in self._particles:
            p.life -= dt
            if p.life <= 0.0:
                continue
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy += grav * dt
            p.vx *= 0.985
            alive.append(p)
        self._particles = alive

    # -- flower glow (shape-matched) + particles ------------------------------
    def _flower_glow(self, surface: pygame.Surface) -> None:
        gain = float(self.option("t3glow"))
        base = self._baseline
        for i, fl in enumerate(self._flowers):
            env = clamp(base + float(self._bloom[i]))
            v = int(255 * clamp(gain * env))
            if v <= 4:
                continue
            tmp = fl.patch.copy()
            tmp.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
            pop = 1.0 + 0.18 * float(self._bloom[i])  # blooms swell on the beat
            x, y = fl.px, fl.py
            if pop > 1.02:
                nw, nh = int(tmp.get_width() * pop), int(tmp.get_height() * pop)
                x -= (nw - tmp.get_width()) // 2
                y -= (nh - tmp.get_height()) // 2
                tmp = pygame.transform.scale(tmp, (nw, nh))
            surface.blit(tmp, (x, y), special_flags=pygame.BLEND_ADD)
        self._draw_particles(surface)

    def _draw_particles(self, surface: pygame.Surface) -> None:
        # Drawn directly (bright dots) -- cheaper than a full-screen additive layer.
        for p in self._particles:
            t = clamp(p.life / p.max_life)
            rad = max(1, int(p.size * (1.0 + 2.0 * t)))
            pygame.draw.circle(
                surface, scale_color(p.color, 0.45 + 0.55 * t), (int(p.x), int(p.y)), rad
            )


def _color_array(scaled: pygame.Surface, warm: bool) -> np.ndarray:
    """A float (w, h, 3) array of the image keeping only warm (pink) or cool (teal) pixels."""
    arr = pygame.surfarray.array3d(scaled)
    r = arr[:, :, 0].astype(np.int32)
    g = arr[:, :, 1].astype(np.int32)
    b = arr[:, :, 2].astype(np.int32)
    if warm:
        keep = (r >= g - 5) & ((r + b) > 170) & (r > 95)
    else:
        keep = (g > r + 12) & (b > 60) & (g > 80)
    return np.where(keep[:, :, None], arr, 0).astype(np.float32)


def _luma_keyed(surf: pygame.Surface) -> pygame.Surface:
    """Copy ``surf`` with a luminance-derived alpha: black background -> transparent.

    A gentle ramp keeps the tree's soft glow semi-transparent (so it blends into the background
    behind it) while fully clearing the near-black canvas.
    """
    arr = pygame.surfarray.array3d(surf).astype(np.float32)
    luma = arr[:, :, 0] * 0.299 + arr[:, :, 1] * 0.587 + arr[:, :, 2] * 0.114
    alpha = np.clip((luma - 6.0) / 54.0, 0.0, 1.0) ** 0.75
    keyed = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    pygame.surfarray.blit_array(keyed, arr.astype(np.uint8))
    ap = pygame.surfarray.pixels_alpha(keyed)
    ap[:] = (alpha * 255.0).astype(np.uint8)
    del ap  # unlock the surface before it's used
    return keyed


def _shift(b: np.ndarray, dx: int, dy: int) -> np.ndarray:
    """Boolean array shifted by (dx, dy) with zero fill (for neighbour tests)."""
    out = np.zeros_like(b)
    w, h = b.shape
    out[max(0, dx) : w + min(0, dx), max(0, dy) : h + min(0, dy)] = b[
        max(0, -dx) : w + min(0, -dx), max(0, -dy) : h + min(0, -dy)
    ]
    return out


def _neighbors8(b: np.ndarray) -> np.ndarray:
    """Cells 8-connected to any True cell of ``b``."""
    out = np.zeros_like(b)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                out |= _shift(b, dx, dy)
    return out


def _flow_field(small: pygame.Surface) -> tuple[np.ndarray, np.ndarray]:
    """Geodesic distance-from-roots over the tree, plus the colour to light along it.

    Returns ``(phase, flow_base)`` both shaped ``(w, h, ...)`` to match ``small``: ``phase`` is the
    normalised distance (0 at the roots .. 1 at the farthest reachable tip, -1 off the tree), and
    ``flow_base`` is the brightened tree colour the running light is tinted by.
    """
    arr = pygame.surfarray.array3d(small).astype(np.float32)  # (w, h, 3)
    w, h = arr.shape[0], arr.shape[1]
    luma = arr[:, :, 0] * 0.299 + arr[:, :, 1] * 0.587 + arr[:, :, 2] * 0.114
    mask = luma > 26.0  # tree pixels stand out from the near-black background
    # BFS on a coarser grid (cheaper, and small gaps get bridged by a 1px dilation).
    cf = 2
    cmask = mask[::cf, ::cf].copy()
    cmask |= _neighbors8(cmask)
    cw, ch = cmask.shape
    inf = np.float32(1e9)
    dist = np.full((cw, ch), inf, dtype=np.float32)
    seed = np.zeros((cw, ch), dtype=bool)
    seed[:, int(ch * 0.90) :] = cmask[:, int(ch * 0.90) :]  # roots: bottom of the tree
    if not seed.any():
        rows = np.where(cmask.any(axis=0))[0]
        if rows.size:
            seed[:, rows.max()] = cmask[:, rows.max()]
    dist[seed] = 0.0
    frontier = seed
    step = 0
    while frontier.any() and step < 1500:
        step += 1
        newf = _neighbors8(frontier) & cmask & (dist >= inf)
        dist[newf] = step
        frontier = newf
    reach = dist < inf
    maxd = float(dist[reach].max()) if reach.any() else 1.0
    phase_c = np.where(reach, dist / maxd, -1.0).astype(np.float32)
    up = np.repeat(np.repeat(phase_c, cf, axis=0), cf, axis=1)
    phase = np.full((w, h), -1.0, dtype=np.float32)
    phase[: up.shape[0], : up.shape[1]] = up[:w, :h]
    flow_base = np.minimum(255.0, arr * 1.7 + 35.0) * mask[:, :, None]
    flow_base[phase < 0.0] = 0.0
    return phase, flow_base.astype(np.float32)


def _petal_patch(region: pygame.Surface) -> pygame.Surface:
    """Mask a bloom patch so only its bright petal pixels remain (rest black)."""
    arr = pygame.surfarray.array3d(region)
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    keep = (r >= g - 8) & ((r.astype(np.int32) + b) > 180) & (r > 105)
    out = np.where(keep[:, :, None], arr, 0).astype(np.uint8)
    return pygame.surfarray.make_surface(out)


def _detect_flowers(src: pygame.Surface) -> list[tuple[float, float, Color]]:
    """Find the big bright-magenta blooms in the artwork (normalised centres + tint)."""
    iw, ih = src.get_size()
    sw = 192
    sh = max(1, int(ih * sw / iw))
    small = pygame.transform.smoothscale(src, (sw, sh))
    arr = pygame.surfarray.array3d(small).astype(np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    mask = ((r > 165) & (b > 110) & (g < 0.72 * r) & ((r + b) > 300)).astype(np.float32)
    cell = 4
    gw, gh = sw // cell, sh // cell
    pool = mask[: gw * cell, : gh * cell].reshape(gw, cell, gh, cell).sum(axis=(1, 3))
    cells = [
        (pool[i, j], i, j) for i in range(gw) for j in range(gh) if pool[i, j] > cell * cell * 0.35
    ]
    cells.sort(reverse=True)
    chosen: list[tuple[int, int]] = []
    flowers: list[tuple[float, float, Color]] = []
    for _score, i, j in cells:
        if any((i - ci) ** 2 + (j - cj) ** 2 <= 9.0 for ci, cj in chosen):
            continue
        chosen.append((i, j))
        nx = (i + 0.5) * cell / sw
        ny = (j + 0.5) * cell / sh
        tint = src.get_at((min(iw - 1, int(nx * iw)), min(ih - 1, int(ny * ih))))
        flowers.append((nx, ny, (tint[0], tint[1], tint[2])))
    return flowers
