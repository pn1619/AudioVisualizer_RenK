"""Entry point: parse args, configure logging, install excepthook, run the App."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from audio_visualizer.config import APP_NAME, APP_VERSION, SELFTEST_FRAMES

logger = logging.getLogger(__name__)


def _configure_logging(debug: bool) -> None:
    """Send logs to the console and a rotating ``logs/app.log`` file."""
    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger()
    root.setLevel(level)

    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    try:
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError:  # pragma: no cover - logging must never crash the app
        logger.warning("Could not open log file; logging to console only.")


def _install_excepthook() -> None:
    """Log any uncaught exception (with traceback) before the process dies."""

    def _hook(exc_type, exc_value, exc_tb):
        logging.getLogger().critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="audio_visualizer", description=APP_NAME)
    parser.add_argument("--debug", action="store_true", help="verbose DEBUG logging")
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="render a few headless frames with a synthetic tone, then exit 0",
    )
    parser.add_argument("--mode", default=None, help="start in this visual mode (key)")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Program entry point. Returns a process exit code."""
    args = _parse_args(argv)
    _configure_logging(args.debug)
    _install_excepthook()

    # For the headless self-test, force SDL dummy drivers BEFORE pygame is imported.
    if args.selftest:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    from audio_visualizer.platform_win import enable_dpi_awareness

    enable_dpi_awareness()

    # Import App lazily so the SDL env vars above take effect first.
    from audio_visualizer.app import App

    logger.info("%s %s starting (selftest=%s)", APP_NAME, APP_VERSION, args.selftest)
    app = App(start_mode=args.mode)
    if args.selftest:
        return app.run_selftest(SELFTEST_FRAMES)
    return app.run()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
