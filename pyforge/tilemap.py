"""A simple tile grid: storage, culled rendering and collider generation."""

from __future__ import annotations

from collections.abc import Sequence

import pygame

from .components import Transform
from .ecs import Entity, World
from .math import Rect, Vec2
from .physics import BodyType, Collider, RigidBody, ShapeType
from .render import Layer, Renderer

__all__ = ["TileMap"]

EMPTY = -1


class TileMap:
    """A dense grid of integer tile ids drawn from a ``tileset`` of surfaces."""

    def __init__(
        self,
        columns: int,
        rows: int,
        tile_size: int,
        tileset: Sequence[pygame.Surface],
        *,
        solid_tiles: set[int] | None = None,
    ) -> None:
        self.columns = columns
        self.rows = rows
        self.tile_size = tile_size
        self.tileset = list(tileset)
        self.solid_tiles = solid_tiles or set()
        self._tiles: list[int] = [EMPTY] * (columns * rows)

    # -- construction ---------------------------------------------------------
    @classmethod
    def from_rows(
        cls,
        rows_data: Sequence[Sequence[int]],
        tile_size: int,
        tileset: Sequence[pygame.Surface],
        *,
        solid_tiles: set[int] | None = None,
    ) -> TileMap:
        rows = len(rows_data)
        columns = len(rows_data[0]) if rows else 0
        tilemap = cls(columns, rows, tile_size, tileset, solid_tiles=solid_tiles)
        for y, row in enumerate(rows_data):
            for x, value in enumerate(row):
                tilemap.set(x, y, value)
        return tilemap

    # -- access ---------------------------------------------------------------
    def in_bounds(self, tx: int, ty: int) -> bool:
        return 0 <= tx < self.columns and 0 <= ty < self.rows

    def get(self, tx: int, ty: int) -> int:
        if not self.in_bounds(tx, ty):
            return EMPTY
        return self._tiles[ty * self.columns + tx]

    def set(self, tx: int, ty: int, value: int) -> None:
        if self.in_bounds(tx, ty):
            self._tiles[ty * self.columns + tx] = value

    def is_solid(self, tx: int, ty: int) -> bool:
        return self.get(tx, ty) in self.solid_tiles

    # -- coordinate helpers ---------------------------------------------------
    @property
    def world_size(self) -> Vec2:
        return Vec2(self.columns * self.tile_size, self.rows * self.tile_size)

    @property
    def bounds(self) -> Rect:
        return Rect(0.0, 0.0, self.columns * self.tile_size, self.rows * self.tile_size)

    def tile_center(self, tx: int, ty: int) -> Vec2:
        return Vec2((tx + 0.5) * self.tile_size, (ty + 0.5) * self.tile_size)

    def world_to_tile(self, world: Vec2) -> tuple[int, int]:
        return int(world.x // self.tile_size), int(world.y // self.tile_size)

    # -- rendering ------------------------------------------------------------
    def draw(self, renderer: Renderer, *, layer: int = Layer.TILEMAP) -> None:
        view = renderer.camera.visible_world_rect()
        size = self.tile_size
        x0 = max(0, int(view.left // size))
        y0 = max(0, int(view.top // size))
        x1 = min(self.columns - 1, int(view.right // size))
        y1 = min(self.rows - 1, int(view.bottom // size))
        tileset = self.tileset
        for ty in range(y0, y1 + 1):
            base = ty * self.columns
            for tx in range(x0, x1 + 1):
                tile = self._tiles[base + tx]
                if 0 <= tile < len(tileset):
                    renderer.draw_sprite(
                        tileset[tile], self.tile_center(tx, ty), layer=layer
                    )

    # -- physics --------------------------------------------------------------
    def build_static_bodies(self, world: World, *, layer_mask: int = 0x1) -> list[Entity]:
        """Create one static box collider per solid tile (greedy-merged by row).

        Returns the created entities so callers can destroy them on unload.
        """
        created: list[Entity] = []
        size = self.tile_size
        for ty in range(self.rows):
            tx = 0
            while tx < self.columns:
                if not self.is_solid(tx, ty):
                    tx += 1
                    continue
                run_start = tx
                while tx < self.columns and self.is_solid(tx, ty):
                    tx += 1
                run_len = tx - run_start
                width = run_len * size
                center = Vec2((run_start + run_len / 2.0) * size, (ty + 0.5) * size)
                entity = world.create_entity(
                    Transform(position=center),
                    Collider(
                        shape=ShapeType.BOX,
                        width=width,
                        height=float(size),
                        layer=layer_mask,
                    ),
                    RigidBody(body_type=BodyType.STATIC),
                )
                created.append(entity)
        return created
