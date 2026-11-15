"""Debug helpers: logging setup, an on-screen overlay and a tiny console."""

from __future__ import annotations

import logging
from collections.abc import Callable

import pygame

from .components import Transform
from .math import Rect, Vec2
from .physics import Collider, ShapeType
from .render import Layer, Renderer

__all__ = ["Console", "DebugOverlay", "configure_logging", "get_logger"]


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"pyforge.{name}")


class DebugOverlay:
    """Press a bound key to toggle; renders stats and (optionally) colliders.

    Attach with ``app.set_overlay(overlay)`` and toggle with :meth:`toggle`.
    """

    def __init__(self, font: pygame.font.Font) -> None:
        self.font = font
        self.visible = False
        self.show_colliders = True

    def toggle(self) -> None:
        self.visible = not self.visible

    def draw(self, renderer: Renderer, app: object) -> None:
        if not self.visible:
            return
        # ``app`` is the pyforge.App; typed loosely to avoid an import cycle.
        stats = app.stats  # type: ignore[attr-defined]
        scene = app.scenes.current  # type: ignore[attr-defined]
        camera = app.camera  # type: ignore[attr-defined]
        world = scene.world if scene is not None else None
        lines = [
            f"FPS {stats.fps:5.1f}   frame {stats.frame_ms:4.1f} ms   steps {stats.update_calls}",
            f"entities {world.entity_count if world else 0}",
            f"camera {camera.position.x:7.1f}, {camera.position.y:7.1f}  zoom {camera.zoom:.2f}",
        ]
        for i, line in enumerate(lines):
            renderer.draw_text(
                self.font,
                line,
                Vec2(8.0, 8.0 + i * 18.0),
                (180, 255, 180),
                layer=Layer.DEBUG,
                screen_space=True,
            )
        if self.show_colliders and world is not None:
            self._draw_colliders(renderer, world)

    def _draw_colliders(self, renderer: Renderer, world: object) -> None:
        color = (90, 230, 90)
        for _entity, transform, collider in world.query(Transform, Collider):  # type: ignore[attr-defined]
            center = collider.world_center(transform)
            if collider.shape is ShapeType.CIRCLE:
                renderer.draw_circle(
                    center, collider.radius, color, width=1, layer=Layer.DEBUG
                )
            else:
                rect = Rect.from_center(center, collider.width, collider.height)
                renderer.draw_rect(rect, color, width=1, layer=Layer.DEBUG)


class Console:
    """A minimal drop-down console. Register commands, toggle, type, run.

    Feed it pygame events from a scene's ``handle_event`` while open.
    """

    def __init__(self, font: pygame.font.Font, *, max_lines: int = 8) -> None:
        self.font = font
        self.visible = False
        self.max_lines = max_lines
        self._input = ""
        self._history: list[str] = []
        self._commands: dict[str, Callable[[list[str]], str | None]] = {}

    def register(self, name: str, handler: Callable[[list[str]], str | None]) -> None:
        self._commands[name] = handler

    def log(self, text: str) -> None:
        self._history.append(text)
        del self._history[: max(0, len(self._history) - 100)]

    def toggle(self) -> None:
        self.visible = not self.visible

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True if the event was consumed by the console."""
        if not self.visible or event.type != pygame.KEYDOWN:
            return False
        if event.key == pygame.K_RETURN:
            self._run(self._input)
            self._input = ""
        elif event.key == pygame.K_BACKSPACE:
            self._input = self._input[:-1]
        elif event.unicode and event.unicode.isprintable():
            self._input += event.unicode
        return True

    def _run(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        self.log(f"> {line}")
        parts = line.split()
        handler = self._commands.get(parts[0])
        if handler is None:
            self.log(f"unknown command: {parts[0]}")
            return
        result = handler(parts[1:])
        if result:
            self.log(result)

    def draw(self, renderer: Renderer) -> None:
        if not self.visible:
            return
        width = renderer.size[0]
        height = (self.max_lines + 1) * 20 + 8
        renderer.draw_rect(
            Rect(0, 0, width, height), (12, 12, 18, 230), layer=Layer.DEBUG, screen_space=True
        )
        visible_lines = self._history[-self.max_lines :]
        for i, line in enumerate(visible_lines):
            renderer.draw_text(
                self.font, line, Vec2(8.0, 6.0 + i * 20.0), (200, 220, 200),
                layer=Layer.DEBUG, z=1, screen_space=True,
            )
        renderer.draw_text(
            self.font, f"> {self._input}", Vec2(8.0, 6.0 + self.max_lines * 20.0),
            (255, 255, 160), layer=Layer.DEBUG, z=1, screen_space=True,
        )
