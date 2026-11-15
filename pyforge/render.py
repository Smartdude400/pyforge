"""Rendering: a camera-aware, layer/z-ordered draw command buffer.

Subsystems submit draw calls in any order; the :class:`Renderer` buffers them
and, on :meth:`flush`, executes them sorted by ``(layer, z, submission order)``.
This decouples *when* something is drawn from *what order* it appears in, which
is exactly what you want for sprites, tilemaps and UI sharing one frame.

Coordinates are world-space by default and transformed through the camera.
Pass ``screen_space=True`` for HUD/UI that should ignore the camera.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import pygame

from .camera import Camera2D
from .math import Rect, Vec2

__all__ = ["Color", "Layer", "Renderer"]

Color = pygame.Color | tuple[int, int, int] | tuple[int, int, int, int]


class Layer:
    """Conventional layer indices (any int works; these are just defaults)."""

    BACKGROUND = 0
    TILEMAP = 100
    ENTITIES = 200
    PARTICLES = 300
    FOREGROUND = 400
    UI = 1000
    DEBUG = 2000


@dataclass(slots=True)
class _Command:
    layer: int
    z: float
    order: int
    func: Callable[[pygame.Surface], None]


@dataclass(slots=True)
class Renderer:
    """Owns the display surface and a camera; buffers and flushes draw calls."""

    surface: pygame.Surface
    camera: Camera2D
    clear_color: Color = (16, 16, 24)
    _commands: list[_Command] = field(default_factory=list)
    _order: int = 0

    # -- frame lifecycle ------------------------------------------------------
    def begin_frame(self) -> None:
        self._commands.clear()
        self._order = 0
        self.surface.fill(self.clear_color)

    def flush(self) -> None:
        """Sort buffered commands and blit them to the surface."""
        self._commands.sort(key=lambda c: (c.layer, c.z, c.order))
        surface = self.surface
        for command in self._commands:
            command.func(surface)
        self._commands.clear()

    def _submit(self, layer: int, z: float, func: Callable[[pygame.Surface], None]) -> None:
        self._commands.append(_Command(layer, z, self._order, func))
        self._order += 1

    # -- helpers --------------------------------------------------------------
    def _to_screen(self, position: Vec2, screen_space: bool) -> Vec2:
        return position if screen_space else self.camera.world_to_screen(position)

    @property
    def size(self) -> tuple[int, int]:
        return self.surface.get_size()

    # -- sprites --------------------------------------------------------------
    def draw_sprite(
        self,
        image: pygame.Surface,
        position: Vec2,
        *,
        origin: Vec2 | None = None,
        scale: float = 1.0,
        rotation: float = 0.0,
        flip_x: bool = False,
        flip_y: bool = False,
        tint: Color | None = None,
        layer: int = Layer.ENTITIES,
        z: float = 0.0,
        screen_space: bool = False,
    ) -> None:
        """Queue a sprite blit. ``origin`` is the pivot in source pixels."""
        zoom = 1.0 if screen_space else self.camera.zoom
        effective_scale = scale * zoom
        screen_pos = self._to_screen(position, screen_space)

        def render(surface: pygame.Surface) -> None:
            img = image
            if flip_x or flip_y:
                img = pygame.transform.flip(img, flip_x, flip_y)
            if rotation != 0.0 or effective_scale != 1.0:
                img = pygame.transform.rotozoom(img, -math.degrees(rotation), effective_scale)
            if tint is not None:
                img = img.copy()
                img.fill(tint, special_flags=pygame.BLEND_RGBA_MULT)
            rect = img.get_rect()
            if origin is None:
                rect.center = (int(screen_pos.x), int(screen_pos.y))
            else:
                pivot = origin * effective_scale
                rect.topleft = (int(screen_pos.x - pivot.x), int(screen_pos.y - pivot.y))
            surface.blit(img, rect)

        self._submit(layer, z, render)

    # -- primitives -----------------------------------------------------------
    def draw_rect(
        self,
        rect: Rect,
        color: Color,
        *,
        width: int = 0,
        layer: int = Layer.ENTITIES,
        z: float = 0.0,
        screen_space: bool = False,
    ) -> None:
        zoom = 1.0 if screen_space else self.camera.zoom
        top_left = self._to_screen(Vec2(rect.x, rect.y), screen_space)
        size = (max(1, int(rect.width * zoom)), max(1, int(rect.height * zoom)))
        line_width = width if width == 0 else max(1, int(width))

        def render(surface: pygame.Surface) -> None:
            pygame.draw.rect(
                surface,
                color,
                pygame.Rect(int(top_left.x), int(top_left.y), size[0], size[1]),
                line_width,
            )

        self._submit(layer, z, render)

    def draw_circle(
        self,
        center: Vec2,
        radius: float,
        color: Color,
        *,
        width: int = 0,
        layer: int = Layer.ENTITIES,
        z: float = 0.0,
        screen_space: bool = False,
    ) -> None:
        zoom = 1.0 if screen_space else self.camera.zoom
        screen_pos = self._to_screen(center, screen_space)
        screen_radius = max(1, int(radius * zoom))

        def render(surface: pygame.Surface) -> None:
            pygame.draw.circle(
                surface,
                color,
                (int(screen_pos.x), int(screen_pos.y)),
                screen_radius,
                width,
            )

        self._submit(layer, z, render)

    def draw_line(
        self,
        start: Vec2,
        end: Vec2,
        color: Color,
        *,
        width: int = 1,
        layer: int = Layer.ENTITIES,
        z: float = 0.0,
        screen_space: bool = False,
    ) -> None:
        a = self._to_screen(start, screen_space)
        b = self._to_screen(end, screen_space)

        def render(surface: pygame.Surface) -> None:
            pygame.draw.line(surface, color, a.as_int_tuple(), b.as_int_tuple(), width)

        self._submit(layer, z, render)

    def draw_polygon(
        self,
        points: Sequence[Vec2],
        color: Color,
        *,
        width: int = 0,
        layer: int = Layer.ENTITIES,
        z: float = 0.0,
        screen_space: bool = False,
    ) -> None:
        screen_points = [self._to_screen(p, screen_space).as_int_tuple() for p in points]

        def render(surface: pygame.Surface) -> None:
            if len(screen_points) >= 3:
                pygame.draw.polygon(surface, color, screen_points, width)

        self._submit(layer, z, render)

    # -- text -----------------------------------------------------------------
    def draw_text(
        self,
        font: pygame.font.Font,
        text: str,
        position: Vec2,
        color: Color = (255, 255, 255),
        *,
        anchor: str = "topleft",
        layer: int = Layer.UI,
        z: float = 0.0,
        screen_space: bool = True,
    ) -> None:
        """Render ``text``. ``anchor`` matches pygame.Rect attribute names."""
        screen_pos = self._to_screen(position, screen_space)

        def render(surface: pygame.Surface) -> None:
            image = font.render(text, True, color)
            rect = image.get_rect()
            setattr(rect, anchor, (int(screen_pos.x), int(screen_pos.y)))
            surface.blit(image, rect)

        self._submit(layer, z, render)

    # -- raw surface (e.g. a pre-composited layer) ----------------------------
    def draw_surface(
        self,
        image: pygame.Surface,
        position: Vec2,
        *,
        layer: int = Layer.BACKGROUND,
        z: float = 0.0,
        screen_space: bool = True,
    ) -> None:
        screen_pos = self._to_screen(position, screen_space)

        def render(surface: pygame.Surface) -> None:
            surface.blit(image, screen_pos.as_int_tuple())

        self._submit(layer, z, render)
