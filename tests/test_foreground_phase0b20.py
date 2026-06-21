"""Phase 0B.20: global Foreground overlay (lightning + flames), panel, persistence."""

from __future__ import annotations

import numpy as np
import pygame

from audio_visualizer import looks as looks_mod
from audio_visualizer import settings as settings_mod
from audio_visualizer.config import FG_FLAME_MAX, FG_MODES
from audio_visualizer.looks import Look
from audio_visualizer.settings import Settings
from audio_visualizer.ui.foreground_panel import ForegroundActions, ForegroundPanel
from audio_visualizer.visuals.base import Theme
from audio_visualizer.visuals.foreground import Foreground


# -- effects render ------------------------------------------------------------
def _beat_frame(make_frame, onset: float = 0.95):
    return make_frame(level=0.8, onset=onset)


def test_off_foreground_is_a_noop(make_frame) -> None:
    surface = pygame.Surface((120, 80))
    surface.fill((9, 9, 15))
    before = pygame.surfarray.array3d(surface).copy()
    Foreground(theme=Theme()).draw(surface, _beat_frame(make_frame), 1 / 60)
    assert np.array_equal(before, pygame.surfarray.array3d(surface))


def test_all_fg_modes_render_without_error(make_frame) -> None:
    surface = pygame.Surface((200, 140))
    fg = Foreground(theme=Theme())
    for mode in FG_MODES:
        fg.mode = mode
        for direction in ("random", "top", "left", "all"):
            fg.direction = direction
            for _ in range(8):  # several beats so bursts spawn + fade
                surface.fill((8, 8, 14))
                fg.draw(surface, _beat_frame(make_frame), 0.05)  # must not raise


def test_lightning_paints_then_fades_when_silent(make_frame) -> None:
    surface = pygame.Surface((160, 120))
    fg = Foreground(theme=Theme())
    fg.mode = "lightning"
    fg.draw(surface, _beat_frame(make_frame), 0.05)  # a beat spawns bolt(s) + flash
    assert fg._bolts
    silent = make_frame(level=0.0, onset=0.0)
    for _ in range(40):
        fg.draw(surface, silent, 0.05)
    assert fg._bolts == [] and fg._flash <= 0.5


def test_flames_emit_and_stay_bounded(make_frame) -> None:
    surface = pygame.Surface((200, 160))
    fg = Foreground(theme=Theme())
    fg.mode = "flames"
    fg.intensity = 2.0
    for _ in range(200):
        fg.draw(surface, _beat_frame(make_frame), 1 / 120)
    assert 0 < len(fg._flames) <= FG_FLAME_MAX


def test_reduce_motion_dampens_lightning(make_frame) -> None:
    fg = Foreground(theme=Theme(), reduce_motion=True)
    fg.mode = "lightning"
    surface = pygame.Surface((160, 120))
    fg.draw(surface, _beat_frame(make_frame, onset=1.0), 0.05)
    assert len(fg._bolts) == 1  # reduce-motion caps bolts to one


# -- panel routing -------------------------------------------------------------
def _make_panel(calls: dict[str, str]) -> ForegroundPanel:
    return ForegroundPanel(
        ForegroundActions(
            set_mode=lambda v: calls.__setitem__("mode", v),
            set_intensity=lambda v: calls.__setitem__("intensity", v),
            set_direction=lambda v: calls.__setitem__("direction", v),
            set_color=lambda v: calls.__setitem__("color", v),
            set_opacity=lambda v: calls.__setitem__("opacity", v),
            set_flash=lambda v: calls.__setitem__("flash", v),
            set_reactivity=lambda v: calls.__setitem__("reactivity", v),
            set_wind=lambda v: calls.__setitem__("wind", v),
        ),
        mode_options=[("off", "Off"), ("lightning", "Lightning")],
        intensity_options=[("1", "x1.00"), ("2", "x2.00")],
        direction_options=[("random", "Random"), ("left", "From left")],
        color_options=[("auto", "Auto (natural)"), ("blue", "Blue")],
        opacity_options=[("0.5", "50%"), ("1", "100%")],
        flash_options=[("0", "Off"), ("1", "Full")],
        reactivity_options=[("1", "Normal"), ("2", "Frantic")],
        wind_options=[("0", "None"), ("350", "Right")],
    )


def test_foreground_panel_dropdowns_route_callbacks() -> None:
    calls: dict[str, str] = {}
    panel = _make_panel(calls)
    panel.open = True
    canvas = pygame.Rect(0, 0, 1280, 720)

    def _click(pos: tuple[int, int]) -> None:
        panel.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos), canvas)

    rows = {key: dd for key, _label, dd in panel._row_rects(canvas)}
    panel._sync_widgets(canvas)
    _click(rows["mode"].center)
    _click(panel._dd["mode"]._option_rects()[1].center)
    _click(rows["direction"].center)
    _click(panel._dd["direction"]._option_rects()[1].center)

    assert calls["mode"] == "lightning"
    assert calls["direction"] == "left"


# -- persistence ---------------------------------------------------------------
def test_settings_round_trip_foreground(tmp_path) -> None:
    path = tmp_path / "settings.json"
    saved = Settings(fg_mode="flames", fg_intensity=2.0, fg_direction="left", fg_opacity=0.5)
    assert settings_mod.save(saved, path)
    loaded = settings_mod.load(path)
    assert loaded.schema_version == settings_mod.SETTINGS_SCHEMA_VERSION
    assert (loaded.fg_mode, loaded.fg_direction) == ("flames", "left")
    assert (loaded.fg_intensity, loaded.fg_opacity) == (2.0, 0.5)


def test_settings_bad_fg_values_fall_back(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"fg_mode": "nope", "fg_direction": "sideways"}', encoding="utf-8")
    loaded = settings_mod.load(path)
    assert loaded.fg_mode in FG_MODES
    assert loaded.fg_direction in ("random", "top", "bottom", "left", "right", "all")


def test_look_foreground_domain_round_trips() -> None:
    look = Look(
        id="x",
        name="L",
        base_mode_key="bars",
        foreground={
            "link": "local",
            "value": {"fg_mode": "lightning", "fg_intensity": 1.5, "fg_direction": "top"},
        },
    )
    restored = looks_mod._from_json(looks_mod.to_json(look))
    assert restored is not None
    assert restored.foreground.get("link") == "local"
    value = restored.foreground.get("value")
    assert isinstance(value, dict) and value["fg_mode"] == "lightning"
