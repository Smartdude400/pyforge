"""Demo-specific components and the platformer player controller."""

from __future__ import annotations

from dataclasses import dataclass

import pyforge as pf

# Tuning constants.
MOVE_SPEED = 220.0
JUMP_SPEED = 560.0
GRAVITY = 1500.0

# Collision layers.
LAYER_WORLD = 0x1
LAYER_PLAYER = 0x2
LAYER_PICKUP = 0x4


@dataclass(slots=True)
class PlayerTag(pf.Component):
    facing: float = 1.0
    was_grounded: bool = False


@dataclass(slots=True)
class Coin(pf.Component):
    spin: float = 0.0


class PlayerControllerSystem(pf.System):
    """Reads input each fixed step and drives the player body and animation."""

    priority = -10  # before physics (priority 100)

    def __init__(
        self,
        inp: pf.InputManager,
        tilemap: pf.TileMap,
        audio: pf.AudioManager,
    ) -> None:
        self.input = inp
        self.tilemap = tilemap
        self.audio = audio

    def update(self, world: pf.World, time: pf.GameTime) -> None:
        for entity, tag, transform, body, sprite, animator in self._players(world):
            axis = self.input.axis("move_x")
            body.velocity = pf.Vec2(axis * MOVE_SPEED, body.velocity.y)
            if abs(axis) > 0.05:
                tag.facing = 1.0 if axis > 0 else -1.0
            sprite.flip_x = tag.facing < 0

            grounded = self._grounded(world, entity, transform)
            if grounded and self.input.just_pressed("jump"):
                body.velocity = pf.Vec2(body.velocity.x, -JUMP_SPEED)
                self.audio.play_sound("jump", volume=0.5)
                self._dust(world, entity, transform)
            if grounded and not tag.was_grounded:
                self._dust(world, entity, transform)
            tag.was_grounded = grounded

            self._animate(animator, grounded, axis)

    def _players(
        self, world: pf.World
    ) -> list[tuple[pf.Entity, PlayerTag, pf.Transform, pf.RigidBody, pf.Sprite, pf.Animator]]:
        result = []
        for entity, tag in world.query(PlayerTag):
            transform = world.get_component(entity, pf.Transform)
            body = world.get_component(entity, pf.RigidBody)
            sprite = world.get_component(entity, pf.Sprite)
            animator = world.get_component(entity, pf.Animator)
            if transform and body and sprite and animator:
                result.append((entity, tag, transform, body, sprite, animator))
        return result

    def _grounded(self, world: pf.World, entity: pf.Entity, transform: pf.Transform) -> bool:
        collider = world.require(entity, pf.Collider)
        half_w = collider.width / 2.0 - 2.0
        foot_y = transform.position.y + collider.height / 2.0 + 2.0
        for dx in (-half_w, half_w):
            tx, ty = self.tilemap.world_to_tile(pf.Vec2(transform.position.x + dx, foot_y))
            if self.tilemap.is_solid(tx, ty):
                return True
        return False

    def _dust(self, world: pf.World, entity: pf.Entity, transform: pf.Transform) -> None:
        emitter = world.get_component(entity, pf.ParticleEmitter)
        if emitter is not None:
            collider = world.require(entity, pf.Collider)
            feet = pf.Vec2(transform.position.x, transform.position.y + collider.height / 2.0)
            emitter.burst(10, feet)

    def _animate(self, animator: pf.Animator, grounded: bool, axis: float) -> None:
        if not grounded:
            animator.play("jump")
        elif abs(axis) > 0.1:
            animator.play("run")
        else:
            animator.play("idle")
