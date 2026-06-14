"""Status line, idle/error banners, and the F3 debug overlay."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from audio_visualizer.config import (
    COLOR_ACCENT,
    COLOR_BG,
    COLOR_ERROR,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
    COLOR_WARN,
)


@dataclass
class HudState:
    """Everything the HUD needs to render one frame."""

    device_name: str
    mode_label: str
    fps: float
    rms: float
    peak: float
    capturing: bool
    idle: bool
    error: bool


class Hud:
    """Draws the bottom status line, banners, and the optional debug overlay."""

    def __init__(self) -> None:
        self.show_debug = False

    def toggle_debug(self) -> None:
        self.show_debug = not self.show_debug

    def draw(
        self,
        surface: pygame.Surface,
        canvas: pygame.Rect,
        state: HudState,
        font: pygame.font.Font,
    ) -> None:
        self._draw_status_line(surface, canvas, state, font)
        if state.error:
            self._banner(surface, canvas, "No audio device / capture error", COLOR_ERROR, font)
        elif state.capturing and state.idle:
            self._banner(surface, canvas, "No audio detected - play something", COLOR_WARN, font)
        elif not state.capturing:
            self._banner(surface, canvas, "Press Start (Space) to capture", COLOR_TEXT_DIM, font)
        if self.show_debug:
            self._draw_debug(surface, canvas, state, font)

    def draw_notice(
        self,
        surface: pygame.Surface,
        canvas: pygame.Rect,
        font: pygame.font.Font,
        font_small: pygame.font.Font,
    ) -> None:
        """One-time photosensitivity warning shown before a strobing mode."""
        overlay = pygame.Surface(canvas.size, pygame.SRCALPHA)
        overlay.fill((*COLOR_BG, 220))
        surface.blit(overlay, canvas.topleft)

        lines = [
            ("Photosensitivity warning", COLOR_WARN, font),
            ("This mode can flash and strobe.", COLOR_TEXT, font_small),
            ("Enable reduce-motion (M) if sensitive.", COLOR_TEXT, font_small),
            ("Press any key to continue.", COLOR_TEXT_DIM, font_small),
        ]
        total_h = sum(f.get_height() + 8 for _, _, f in lines)
        y = canvas.centery - total_h // 2
        for text, color, f in lines:
            label = f.render(text, True, color)
            rect = label.get_rect(center=(canvas.centerx, y + label.get_height() // 2))
            surface.blit(label, rect)
            y += label.get_height() + 8

    def _draw_status_line(
        self,
        surface: pygame.Surface,
        canvas: pygame.Rect,
        state: HudState,
        font: pygame.font.Font,
    ) -> None:
        device = state.device_name or "(not capturing)"
        text = f"{state.mode_label}   |   {device}   |   {state.fps:4.0f} FPS"
        label = font.render(text, True, COLOR_TEXT_DIM)
        surface.blit(label, (canvas.x + 8, canvas.bottom - label.get_height() - 6))

    def _banner(
        self,
        surface: pygame.Surface,
        canvas: pygame.Rect,
        message: str,
        color: tuple[int, int, int],
        font: pygame.font.Font,
    ) -> None:
        label = font.render(message, True, color)
        rect = label.get_rect(center=(canvas.centerx, canvas.y + 24))
        surface.blit(label, rect)

    def _draw_debug(
        self,
        surface: pygame.Surface,
        canvas: pygame.Rect,
        state: HudState,
        font: pygame.font.Font,
    ) -> None:
        lines = [
            f"FPS:  {state.fps:6.1f}",
            f"RMS:  {state.rms:6.3f}",
            f"Peak: {state.peak:6.3f}",
            f"Mode: {state.mode_label}",
            f"Cap:  {state.capturing}  idle={state.idle}  err={state.error}",
        ]
        x = canvas.x + 8
        y = canvas.y + 8
        for i, line in enumerate(lines):
            color = COLOR_ACCENT if i == 0 else COLOR_TEXT
            label = font.render(line, True, color)
            surface.blit(label, (x, y + i * (label.get_height() + 2)))
