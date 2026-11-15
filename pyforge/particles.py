"""A pooled particle system: emitters, simulation and rendering.

Each :class:`ParticleEmitter` owns a fixed-capacity pool of particle structs so
steady-state emission performs **zero allocations** — dead particles are reused
in place. Particles interpolate colour, alpha and size across their lifetime.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from .components import Transform
from .ecs import Component, System, World
from .math import Vec2, lerp
from .render import Layer, Renderer

if TYPE_CHECKING:
    from .clock import GameTime

__all__ = ["Particle", "ParticleEmitter", "ParticleSystem"]

RGBA = tuple[int, int, int, int]


@dataclass(slots=True)
class Particle:
    alive: bool = False
    position: Vec2 = field(default_factory=Vec2.zero)
    velocity: Vec2 = field(default_factory=Vec2.zero)
    age: float = 0.0
    lifetime: float = 1.0


@dataclass(slots=True)
class ParticleEmitter(Component):
    """Configuration plus the particle pool for one emitter."""

    capacity: int = 256
    rate: float = 60.0  # particles per second while emitting
    emitting: bool = True
    # Emission shape: a cone around ``direction`` with +/- ``spread`` radians.
    direction: float = -math.pi / 2.0
    spread: float = math.pi
    speed_min: float = 40.0
    speed_max: float = 120.0
    lifetime_min: float = 0.4
    lifetime_max: float = 1.0
    size_start: float = 6.0
    size_end: float = 0.0
    color_start: RGBA = (255, 220, 120, 255)
    color_end: RGBA = (255, 80, 40, 0)
    gravity: Vec2 = field(default_factory=Vec2.zero)
    local_offset: Vec2 = field(default_factory=Vec2.zero)
    layer: int = Layer.PARTICLES

    _pool: list[Particle] = field(default_factory=list)
    _accumulator: float = 0.0

    def _ensure_pool(self) -> None:
        if len(self._pool) != self.capacity:
            self._pool = [Particle() for _ in range(self.capacity)]

    def burst(self, count: int, origin: Vec2) -> None:
        """Emit ``count`` particles immediately from ``origin`` (world space)."""
        self._ensure_pool()
        spawned = 0
        for particle in self._pool:
            if spawned >= count:
                break
            if not particle.alive:
                self._spawn(particle, origin)
                spawned += 1

    def _spawn(self, particle: Particle, origin: Vec2) -> None:
        angle = self.direction + random.uniform(-self.spread, self.spread)
        speed = random.uniform(self.speed_min, self.speed_max)
        particle.alive = True
        particle.position = origin + self.local_offset
        particle.velocity = Vec2.from_angle(angle, speed)
        particle.age = 0.0
        particle.lifetime = random.uniform(self.lifetime_min, self.lifetime_max)

    @property
    def active_count(self) -> int:
        return sum(1 for p in self._pool if p.alive)


def _lerp_color(a: RGBA, b: RGBA, t: float) -> RGBA:
    return (
        int(lerp(a[0], b[0], t)),
        int(lerp(a[1], b[1], t)),
        int(lerp(a[2], b[2], t)),
        int(lerp(a[3], b[3], t)),
    )


class ParticleSystem(System):
    """Simulates emitters in the fixed step; draw with :meth:`render`."""

    priority = 50

    def update(self, world: World, time: GameTime) -> None:
        dt = time.dt
        if dt <= 0.0:
            return
        for entity, emitter in world.query(ParticleEmitter):
            emitter._ensure_pool()
            transform = world.get_component(entity, Transform)
            origin = transform.position if transform is not None else Vec2.zero()
            self._emit(emitter, origin, dt)
            self._step(emitter, dt)

    def _emit(self, emitter: ParticleEmitter, origin: Vec2, dt: float) -> None:
        if not emitter.emitting or emitter.rate <= 0.0:
            return
        emitter._accumulator += emitter.rate * dt
        to_spawn = int(emitter._accumulator)
        emitter._accumulator -= to_spawn
        if to_spawn > 0:
            emitter.burst(to_spawn, origin)

    def _step(self, emitter: ParticleEmitter, dt: float) -> None:
        gravity = emitter.gravity
        for particle in emitter._pool:
            if not particle.alive:
                continue
            particle.age += dt
            if particle.age >= particle.lifetime:
                particle.alive = False
                continue
            particle.velocity = particle.velocity + gravity * dt
            particle.position = particle.position + particle.velocity * dt

    def render(self, world: World, renderer: Renderer) -> None:
        for _entity, emitter in world.query(ParticleEmitter):
            self._render_emitter(emitter, renderer)

    def _render_emitter(self, emitter: ParticleEmitter, renderer: Renderer) -> None:
        for particle in emitter._pool:
            if not particle.alive:
                continue
            t = particle.age / particle.lifetime if particle.lifetime > 0 else 1.0
            size = max(1.0, lerp(emitter.size_start, emitter.size_end, t))
            color = _lerp_color(emitter.color_start, emitter.color_end, t)
            renderer.draw_sprite(
                _circle_texture(int(size), color),
                particle.position,
                layer=emitter.layer,
                z=particle.position.y,
            )


# -- a tiny cache of soft circle textures keyed by (diameter, color) ----------
_circle_cache: dict[tuple[int, RGBA], pygame.Surface] = {}


def _circle_texture(diameter: int, color: RGBA) -> pygame.Surface:
    diameter = max(1, diameter)
    key = (diameter, color)
    cached = _circle_cache.get(key)
    if cached is not None:
        return cached
    surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    radius = diameter / 2.0
    pygame.draw.circle(surface, color, (int(radius), int(radius)), max(1, int(radius)))
    if len(_circle_cache) < 4096:
        _circle_cache[key] = surface
    return surface
