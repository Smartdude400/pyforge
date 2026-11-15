"""Demo entry point. Run with ``python -m examples.demo`` from the repo root."""

from __future__ import annotations

import logging
from pathlib import Path

import pygame

import pyforge as pf

from .assets_gen import write_music
from .scenes import MenuScene

GENERATED_DIR = Path(__file__).parent / "_generated"


def configure_input(inp: pf.InputManager) -> None:
    """Bind logical actions to keyboard and gamepad inputs."""
    inp.bind_axis(
        "move_x",
        pf.KeyBind(pygame.K_d, 1.0),
        pf.KeyBind(pygame.K_RIGHT, 1.0),
        pf.KeyBind(pygame.K_a, -1.0),
        pf.KeyBind(pygame.K_LEFT, -1.0),
        pf.PadAxisBind(axis=0, direction=1.0),
    )
    inp.bind_action(
        "jump",
        pf.KeyBind(pygame.K_SPACE),
        pf.KeyBind(pygame.K_w),
        pf.KeyBind(pygame.K_UP),
        pf.PadButtonBind(button=0),
    )


def build_app() -> pf.App:
    config = pf.AppConfig(
        title="PyForge Demo — Platformer",
        width=1280,
        height=720,
        assets_dir=str(GENERATED_DIR),
        clear_color=(28, 32, 48),
        dev_mode=False,
    )
    app = pf.App(config)
    if app.audio.available:
        write_music(GENERATED_DIR / "music.wav")
    configure_input(app.input)
    return app


def main() -> None:
    pf.configure_logging(logging.INFO)
    app = build_app()
    app.run(MenuScene())


if __name__ == "__main__":
    main()
