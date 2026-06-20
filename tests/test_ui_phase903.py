"""Phase 9.03 GUI polish: font fitting, flow/wrap layout, dropdown bounds,
the Appearance panel, dynamic bar height, and settings v3 round-trip/migration."""

from __future__ import annotations

import json

import pygame
import pytest

from audio_visualizer import settings as settings_mod
from audio_visualizer.config import MIN_WINDOW_SIZE
from audio_visualizer.settings import Settings
from audio_visualizer.ui.appearance_panel import AppearanceActions, AppearancePanel
from audio_visualizer.ui.controls import ControlActions, ControlBar
from audio_visualizer.ui.dropdown import Dropdown
from audio_visualizer.ui.layout import Layout
from audio_visualizer.ui.style import fit_text


@pytest.fixture(scope="module", autouse=True)
def _pygame_ready():
    pygame.init()
    pygame.display.set_mode((10, 10))
    yield
    pygame.quit()


def _font() -> pygame.font.Font:
    return pygame.font.Font(None, 22)


def _noop_actions() -> ControlActions:
    noop = lambda *_: None  # noqa: E731 - tiny test stub
    return ControlActions(
        toggle_capture=noop,
        prev_mode=noop,
        next_mode=noop,
        select_mode=noop,
        sensitivity_down=noop,
        sensitivity_up=noop,
        smoothing_down=noop,
        smoothing_up=noop,
        size_down=noop,
        size_up=noop,
        speed_down=noop,
        speed_up=noop,
        cycle_color_scheme=noop,
        select_color=noop,
        option_change=noop,
        toggle_reduce_motion=noop,
        open_logo_panel=noop,
        open_about=noop,
        toggle_fullscreen=noop,
        quit=noop,
    )


def test_fit_text_truncates_with_ellipsis() -> None:
    font = _font()
    long = "Rainbow+ an absurdly long option label that will not fit"
    fitted = fit_text(font, long, 60)
    assert font.size(fitted)[0] <= 60
    assert fitted.endswith("\u2026")
    # Short text is returned untouched.
    assert fit_text(font, "hi", 1000) == "hi"


def test_control_bar_wraps_and_grows_on_narrow_window() -> None:
    bar = ControlBar(_noop_actions(), [("waveform", "Waveform")])
    wide = bar.content_height(1280)
    narrow = bar.content_height(MIN_WINDOW_SIZE[0])
    assert narrow > wide, "bar should grow taller as widgets wrap on a narrow window"

    bar.relayout(pygame.Rect(0, 0, MIN_WINDOW_SIZE[0], narrow))
    widgets = [w for w, _ in bar._row1] + [bar._color, *bar._option_dropdowns]
    for w in widgets:
        assert w.rect.right <= MIN_WINDOW_SIZE[0], "no widget may spill past the window edge"


def test_dropdown_open_list_stays_within_right_bound() -> None:
    dd = Dropdown(lambda _k: None, title="Color")
    dd.set_options([("a", "Aaaa"), ("b", "Bbbb")])
    dd.set_rect(pygame.Rect(600, 0, 150, 30))
    dd.set_bound_right(640)
    dd.open = True
    for rect in dd._option_rects():
        assert rect.right <= 640


def test_appearance_panel_rows_cycle() -> None:
    calls: list[str] = []
    panel = AppearancePanel(
        AppearanceActions(
            cycle_style=lambda: calls.append("style"),
            cycle_accent=lambda: calls.append("accent"),
            cycle_font=lambda: calls.append("font"),
            cycle_cursor=lambda: calls.append("cursor"),
            set_hue=lambda h: calls.append("hue"),
            set_color_scheme=lambda s: calls.append("scheme"),
        )
    )
    panel.open = True
    canvas = pygame.Rect(0, 0, 1280, 720)
    rows = panel._row_rects(canvas)
    keys = [key for key, _rect in rows]
    for _key, rect in rows:
        ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center)
        assert panel.handle_event(ev, canvas) is True
    assert calls == keys  # each row routed to its own action, in order


def test_layout_accepts_dynamic_control_bar_height() -> None:
    layout = Layout.compute((1280, 720), control_bar_height=120)
    assert layout.control_bar.height == 120
    assert layout.canvas.top == 120
    # A hidden bar ignores any height override.
    hidden = Layout.compute((1280, 720), show_control_bar=False, control_bar_height=120)
    assert hidden.control_bar.height == 0


def test_settings_ui_roundtrip(tmp_path) -> None:
    path = tmp_path / "settings.json"
    assert settings_mod.save(Settings(ui_style="glass", ui_font="sans"), path)
    loaded = settings_mod.load(path)
    assert loaded.schema_version == settings_mod.SETTINGS_SCHEMA_VERSION
    assert loaded.ui_style == "glass"
    assert loaded.ui_font == "sans"


def test_settings_migrates_old_file_to_ui_defaults(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"schema_version": 1, "mode": "waveform"}), encoding="utf-8")
    loaded = settings_mod.load(path)
    assert loaded.schema_version == settings_mod.SETTINGS_SCHEMA_VERSION
    assert loaded.ui_style == "flat"  # default applied for the missing key
    assert loaded.ui_font == "mono"
