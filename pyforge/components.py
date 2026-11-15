"""Common, reusable components and the sprite-render system.

Subsystem-specific components live with their subsystem (``RigidBody`` and
``Collider`` in :mod:`pyforge.physics`, ``Animator`` in
:mod:`pyforge.animation`, ``ParticleEmitter`` in :mod:`pyforge.particles`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from .ecs import Component, System, World
from .math import Vec2
from .render import Color, Layer, Renderer

if TYPE_CHECKING:
    from .clock import GameTime

__all__ = ["Name", "Sprite", "SpriteRenderSystem", "Transform"]


@dataclass(slots=True)
class Transform(Component):
    """Position/rotation/scale, plus the previous position for interpolation."""

    position: Vec2 = field(default_factory=Vec2.zero)
    rotation: float = 0.0
    scale: float = 1.0
    #: Set by the physics step each fixed update; used to smooth rendering.
    previous_position: Vec2 = field(default_factory=Vec2.zero)

    def interpolated(self, alpha: float) -> Vec2:
        """Render position blended between the last two simulation states."""
        return self.previous_position.lerp(self.position, alpha)

    def sync_previous(self) -> None:
        self.previous_position = self.position


@dataclass(slots=True)
class Sprite(Component):
    """A drawable image attached to an entity's :class:`Transform`."""

    surface: pygame.Surface
    layer: int = Layer.ENTITIES
    z: float = 0.0
    origin: Vec2 | None = None
    tint: Color | None = None
    flip_x: bool = False
    flip_y: bool = False
    scale: float = 1.0
    visible: bool = True


@dataclass(slots=True)
class Name(Component):
    """An optional human-readable label, handy for debugging/queries."""

    value: str = ""


class SpriteRenderSystem(System):
    """Draws every entity that has both a :class:`Transform` and :class:`Sprite`.

    Runs as a *variable* (render-rate) step rather than a fixed step so it can
    interpolate using ``time.alpha`` for smooth motion between simulation ticks.
    Call :meth:`render` from a scene's ``draw`` rather than via ``World.update``.
    """

    def __init__(self, renderer: Renderer) -> None:
        self.renderer = renderer

    def render(self, world: World, time: GameTime) -> None:
        for _entity, transform, sprite in world.query(Transform, Sprite):
            if not sprite.visible:
                continue
            position = transform.interpolated(time.alpha)
            self.renderer.draw_sprite(
                sprite.surface,
                position,
                origin=sprite.origin,
                scale=sprite.scale * transform.scale,
                rotation=transform.rotation,
                flip_x=sprite.flip_x,
                flip_y=sprite.flip_y,
                tint=sprite.tint,
                layer=sprite.layer,
                z=sprite.z,
            )
