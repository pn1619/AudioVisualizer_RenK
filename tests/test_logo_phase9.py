"""Phase 9: the global RenK logo overlay, its settings, and the About/panel modals."""

from __future__ import annotations

import numpy as np
import pygame
import pytest

from audio_visualizer.audio.frame import AnalysisFrame
from audio_visualizer.config import (
    LOGO_COLOR_MODES,
    LOGO_OPACITIES,
    LOGO_POSITIONS,
    LOGO_SIZES,
)
from audio_visualizer.settings import Settings, _from_dict
from audio_visualizer.ui.about import AboutDialog
from audio_visualizer.ui.logo_panel import LogoPanel, LogoPanelActions
from audio_visualizer.visuals.base import Theme
from audio_visualizer.visuals.logo import RenkLogo, _to_luminance


@pytest.fixture(scope="module", autouse=True)
def _pygame_ready():
    pygame.init()
    # A display is needed for convert_alpha (image load); dummy driver keeps it headless.
    pygame.display.set_mode((320, 240))
    yield
    pygame.quit()


def _logo_surface(size: int = 32) -> pygame.Surface:
    """A small per-pixel-alpha stand-in for the bundled logo art."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(surf, (40, 200, 255, 255), (size // 2, size // 2), size // 2, width=3)
    return surf


def _onset_frame(rms: float = 0.5, onset: float = 1.0) -> AnalysisFrame:
    return AnalysisFrame(
        waveform_mono=np.zeros(8, dtype=np.float32),
        band_energies=np.full(48, 0.6, dtype=np.float32),
        rms=rms,
        peak=0.8,
        sample_rate=48000,
        timestamp=0.0,
        onset=onset,
    )


# -- RenkLogo -----------------------------------------------------------------
def test_logo_unavailable_is_noop_when_asset_missing() -> None:
    logo = RenkLogo(surface=None)
    # A circle with no real asset path may or may not load; if not, draw must no-op.
    if not logo.available:
        surface = pygame.Surface((320, 240))
        logo.draw(surface, _onset_frame(), 0.016)  # must not raise


def test_logo_draws_without_error_all_positions_and_sizes() -> None:
    logo = RenkLogo(surface=_logo_surface())
    assert logo.available
    surface = pygame.Surface((400, 300))
    for pos in LOGO_POSITIONS:
        for size in LOGO_SIZES:
            logo.position = pos
            logo.size_key = size
            logo.draw(surface, _onset_frame(), 0.016)  # no exception = pass


def test_logo_disabled_skips_drawing() -> None:
    logo = RenkLogo(surface=_logo_surface())
    logo.enabled = False
    before = logo._angle
    logo.draw(pygame.Surface((320, 240)), _onset_frame(), 0.5)
    assert logo._angle == before  # disabled logo does not advance/spin


def test_logo_spins_over_time() -> None:
    logo = RenkLogo(surface=_logo_surface(), theme=Theme())
    surface = pygame.Surface((320, 240))
    logo.draw(surface, _onset_frame(rms=0.0), 0.5)
    assert logo._angle > 0.0


def test_logo_rainbow_mode_renders() -> None:
    logo = RenkLogo(surface=_logo_surface())
    logo.color_mode = "rainbow_plus"
    logo.theme.color_phase = 0.3
    logo.draw(pygame.Surface((320, 240)), _onset_frame(), 0.016)  # tint path must run


def test_logo_emits_sparks_on_onset_when_enabled() -> None:
    logo = RenkLogo(surface=_logo_surface())
    logo.emit = True
    logo.draw(pygame.Surface((320, 240)), _onset_frame(onset=1.0), 0.016)
    assert logo._sparks.count > 0


def test_logo_reduce_motion_disables_emission() -> None:
    logo = RenkLogo(surface=_logo_surface(), reduce_motion=True)
    logo.emit = True
    for _ in range(5):
        logo.draw(pygame.Surface((320, 240)), _onset_frame(onset=1.0), 0.016)
    assert logo._sparks.count == 0


def test_logo_opacity_path_runs() -> None:
    logo = RenkLogo(surface=_logo_surface())
    for opacity in LOGO_OPACITIES:
        logo.opacity = opacity
        logo.draw(pygame.Surface((320, 240)), _onset_frame(), 0.016)


def test_to_luminance_preserves_size_and_alpha() -> None:
    src = _logo_surface(24)
    lum = _to_luminance(src)
    assert lum.get_size() == src.get_size()
    assert lum.get_flags() & pygame.SRCALPHA


def test_logo_preserves_source_aspect_ratio() -> None:
    # A 3:2 source must not be squished into a square when scaled.
    src = pygame.Surface((30, 20), pygame.SRCALPHA)
    pygame.draw.ellipse(src, (40, 200, 255, 255), src.get_rect(), width=2)
    logo = RenkLogo(surface=src)
    logo.size_key = "medium"
    logo.draw(pygame.Surface((400, 300)), _onset_frame(), 0.016)
    w, h = logo._scaled_size
    assert abs(w / h - 30 / 20) < 0.05  # aspect preserved


def test_logo_more_size_presets_all_render() -> None:
    logo = RenkLogo(surface=_logo_surface())
    surface = pygame.Surface((500, 400))
    heights = []
    for size in LOGO_SIZES:
        logo.size_key = size
        logo.draw(surface, _onset_frame(), 0.016)
        heights.append(logo._scaled_size[1])
    assert len(LOGO_SIZES) >= 6
    assert heights == sorted(heights)  # presets increase in size


def test_logo_rainbow_uses_varied_hue_map() -> None:
    logo = RenkLogo(surface=_logo_surface(40))
    logo.color_mode = "rainbow_plus"
    logo.draw(pygame.Surface((320, 240)), _onset_frame(), 0.016)
    assert logo._hue_map is not None
    # A swirling rainbow spans many hues, not one flat value.
    assert float(logo._hue_map.max() - logo._hue_map.min()) > 0.3


# -- Settings round-trip / migration ------------------------------------------
def test_logo_settings_round_trip() -> None:
    s = Settings(
        logo_enabled=False,
        logo_size="large",
        logo_position="top_right",
        logo_opacity=0.5,
        logo_color="rainbow_plus",
        logo_emit=True,
    )
    restored = _from_dict(s.to_json())
    assert restored.logo_enabled is False
    assert restored.logo_size == "large"
    assert restored.logo_position == "top_right"
    assert restored.logo_opacity == 0.5
    assert restored.logo_color == "rainbow_plus"
    assert restored.logo_emit is True


def test_logo_settings_default_when_missing() -> None:
    restored = _from_dict({"schema_version": 1})  # an old (v1) file lacks logo_* keys
    defaults = Settings()
    assert restored.logo_enabled == defaults.logo_enabled
    assert restored.logo_size in LOGO_SIZES
    assert restored.logo_color in LOGO_COLOR_MODES


def test_logo_opacity_snaps_to_nearest_preset() -> None:
    restored = _from_dict({"logo_opacity": 0.6})
    assert restored.logo_opacity in LOGO_OPACITIES


def test_logo_invalid_choice_falls_back() -> None:
    restored = _from_dict({"logo_size": "huge", "logo_position": "nope"})
    assert restored.logo_size in LOGO_SIZES
    assert restored.logo_position in LOGO_POSITIONS


# -- Modals -------------------------------------------------------------------
def _panel() -> tuple[LogoPanel, dict[str, int]]:
    calls = {
        "enabled": 0,
        "color": 0,
        "opacity": 0,
        "size": 0,
        "position": 0,
        "spin": 0,
        "emit": 0,
    }
    actions = LogoPanelActions(
        toggle_enabled=lambda: calls.__setitem__("enabled", calls["enabled"] + 1),
        cycle_color=lambda: calls.__setitem__("color", calls["color"] + 1),
        cycle_opacity=lambda: calls.__setitem__("opacity", calls["opacity"] + 1),
        cycle_size=lambda: calls.__setitem__("size", calls["size"] + 1),
        cycle_position=lambda: calls.__setitem__("position", calls["position"] + 1),
        cycle_spin=lambda: calls.__setitem__("spin", calls["spin"] + 1),
        toggle_emit=lambda: calls.__setitem__("emit", calls["emit"] + 1),
    )
    return LogoPanel(actions), calls


def test_logo_panel_row_click_invokes_action() -> None:
    panel, calls = _panel()
    panel.open = True
    canvas = pygame.Rect(0, 0, 800, 600)
    _, first_row = panel._row_rects(canvas)[0]  # the "enabled" row
    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1, pos=(first_row.centerx, first_row.centery)
    )
    assert panel.handle_event(event, canvas) is True
    assert calls["enabled"] == 1


def test_logo_panel_close_button_dismisses() -> None:
    panel, _ = _panel()
    panel.open = True
    canvas = pygame.Rect(0, 0, 800, 600)
    close = panel._close_rect(canvas)
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=close.center)
    panel.handle_event(event, canvas)
    assert panel.open is False


def test_logo_panel_ignores_events_when_closed() -> None:
    panel, calls = _panel()
    canvas = pygame.Rect(0, 0, 800, 600)
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(10, 10))
    assert panel.handle_event(event, canvas) is False
    assert sum(calls.values()) == 0


def test_logo_panel_draws_without_error() -> None:
    panel, _ = _panel()
    panel.open = True
    panel.set_state({"enabled": "On", "color": "Default", "opacity": "75%"})
    surface = pygame.Surface((800, 600))
    font = pygame.font.Font(None, 22)
    panel.draw(surface, pygame.Rect(0, 0, 800, 600), font, font)


def test_menu_dropdown_routes_actions() -> None:
    from audio_visualizer.ui.controls import ControlActions, ControlBar

    calls: dict[str, int] = {"capture": 0, "fullscreen": 0, "quit": 0}
    actions = ControlActions(
        toggle_capture=lambda: calls.__setitem__("capture", calls["capture"] + 1),
        prev_mode=lambda: None,
        next_mode=lambda: None,
        select_mode=lambda key: None,
        sensitivity_down=lambda: None,
        sensitivity_up=lambda: None,
        smoothing_down=lambda: None,
        smoothing_up=lambda: None,
        size_down=lambda: None,
        size_up=lambda: None,
        speed_down=lambda: None,
        speed_up=lambda: None,
        cycle_color_scheme=lambda: None,
        select_color=lambda key: None,
        option_change=lambda key, idx: None,
        toggle_reduce_motion=lambda: None,
        open_logo_panel=lambda: None,
        open_about=lambda: None,
        toggle_fullscreen=lambda: calls.__setitem__("fullscreen", calls["fullscreen"] + 1),
        quit=lambda: calls.__setitem__("quit", calls["quit"] + 1),
    )
    bar = ControlBar(actions, [("waveform", "Waveform")])
    bar.set_state(True, "waveform", False, "classic", 1.0, 0.5, 1.0, 1.0)
    # Menu header stays "Menu" regardless of last action chosen.
    assert bar._menu.current_label == "Menu"
    bar._on_menu_select("capture")
    bar._on_menu_select("fullscreen")
    bar._on_menu_select("quit")
    assert calls == {"capture": 1, "fullscreen": 1, "quit": 1}


def test_about_dialog_toggle_and_draw() -> None:
    about = AboutDialog()
    assert about.open is False
    about.toggle()
    assert about.open is True
    surface = pygame.Surface((800, 600))
    font = pygame.font.Font(None, 22)
    about.draw(surface, pygame.Rect(0, 0, 800, 600), font, font)
    canvas = pygame.Rect(0, 0, 800, 600)
    close = about._close_rect(canvas)
    about.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=close.center), canvas
    )
    assert about.open is False
