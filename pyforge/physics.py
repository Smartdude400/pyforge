"""Lightweight 2D physics: integration, broad/narrow phase and resolution.

Scope (deliberately small, designed to be swappable for a real solver):

* Body types: ``dynamic`` (integrated, collides), ``kinematic`` (moved by
  velocity, pushes dynamics, unaffected itself) and ``static`` (immovable).
* Shapes: axis-aligned boxes and circles, in any combination.
* Broad phase: a uniform spatial hash, so cost scales with occupancy not N².
* Resolution: positional correction + a restitution impulse along the contact
  normal, weighted by inverse mass.
* Events: ``CollisionEnter`` / ``CollisionExit`` published on the event bus,
  with triggers reporting overlaps without any physical response.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from .components import Transform
from .ecs import Component, Entity, System, World
from .events import EventBus
from .math import Rect, Vec2

if TYPE_CHECKING:
    from .clock import GameTime

__all__ = [
    "BodyType",
    "Collider",
    "CollisionEnter",
    "CollisionExit",
    "PhysicsSystem",
    "RigidBody",
    "ShapeType",
]


class BodyType(Enum):
    STATIC = "static"
    KINEMATIC = "kinematic"
    DYNAMIC = "dynamic"


class ShapeType(Enum):
    BOX = "box"
    CIRCLE = "circle"


@dataclass(slots=True)
class RigidBody(Component):
    velocity: Vec2 = field(default_factory=Vec2.zero)
    body_type: BodyType = BodyType.DYNAMIC
    mass: float = 1.0
    restitution: float = 0.0
    gravity_scale: float = 1.0
    #: Per-second velocity damping (0 = none). Applied as v *= (1 - drag*dt).
    drag: float = 0.0

    @property
    def inverse_mass(self) -> float:
        if self.body_type is not BodyType.DYNAMIC or self.mass <= 0.0:
            return 0.0
        return 1.0 / self.mass


@dataclass(slots=True)
class Collider(Component):
    shape: ShapeType = ShapeType.BOX
    width: float = 1.0
    height: float = 1.0
    radius: float = 0.5
    offset: Vec2 = field(default_factory=Vec2.zero)
    is_trigger: bool = False
    #: Bitmask layer this collider belongs to.
    layer: int = 0x1
    #: Bitmask of layers this collider tests against.
    mask: int = 0xFFFFFFFF

    def world_center(self, transform: Transform) -> Vec2:
        return transform.position + self.offset

    def aabb(self, transform: Transform) -> Rect:
        center = self.world_center(transform)
        if self.shape is ShapeType.CIRCLE:
            return Rect.from_center(center, self.radius * 2.0, self.radius * 2.0)
        return Rect.from_center(center, self.width, self.height)


@dataclass(frozen=True, slots=True)
class CollisionEnter:
    a: Entity
    b: Entity
    normal: Vec2
    penetration: float
    trigger: bool


@dataclass(frozen=True, slots=True)
class CollisionExit:
    a: Entity
    b: Entity


@dataclass(frozen=True, slots=True)
class _Contact:
    normal: Vec2  # unit vector pointing from A toward B
    penetration: float


def _box_vs_box(a: Rect, b: Rect) -> _Contact | None:
    overlap_x = min(a.right, b.right) - max(a.left, b.left)
    overlap_y = min(a.bottom, b.bottom) - max(a.top, b.top)
    if overlap_x <= 0.0 or overlap_y <= 0.0:
        return None
    if overlap_x < overlap_y:
        normal = Vec2(1.0 if a.center.x < b.center.x else -1.0, 0.0)
        return _Contact(normal, overlap_x)
    normal = Vec2(0.0, 1.0 if a.center.y < b.center.y else -1.0)
    return _Contact(normal, overlap_y)


def _circle_vs_circle(ca: Vec2, ra: float, cb: Vec2, rb: float) -> _Contact | None:
    delta = cb - ca
    distance = delta.length()
    radius_sum = ra + rb
    if distance >= radius_sum:
        return None
    if distance <= 1e-9:
        return _Contact(Vec2(1.0, 0.0), radius_sum)
    return _Contact(delta / distance, radius_sum - distance)


def _circle_vs_box(center: Vec2, radius: float, box: Rect) -> _Contact | None:
    closest_x = max(box.left, min(center.x, box.right))
    closest_y = max(box.top, min(center.y, box.bottom))
    delta = Vec2(center.x - closest_x, center.y - closest_y)
    distance = delta.length()
    if distance >= radius:
        return None
    if distance <= 1e-9:
        # Centre is inside the box: push out along the shallowest axis.
        contact = _box_vs_box(Rect.from_center(center, radius * 2, radius * 2), box)
        return contact
    # Normal points from circle (A) toward box (B).
    return _Contact((delta / distance) * -1.0, radius - distance)


class _SpatialHash:
    """Uniform grid mapping cell coordinates to the entities overlapping them."""

    def __init__(self, cell_size: float) -> None:
        self.cell_size = cell_size
        self._cells: dict[tuple[int, int], list[Entity]] = defaultdict(list)

    def clear(self) -> None:
        self._cells.clear()

    def _cells_for(self, rect: Rect) -> list[tuple[int, int]]:
        size = self.cell_size
        x0, y0 = int(rect.left // size), int(rect.top // size)
        x1, y1 = int(rect.right // size), int(rect.bottom // size)
        return [(cx, cy) for cx in range(x0, x1 + 1) for cy in range(y0, y1 + 1)]

    def insert(self, entity: Entity, rect: Rect) -> None:
        for cell in self._cells_for(rect):
            self._cells[cell].append(entity)

    def candidate_pairs(self) -> set[tuple[Entity, Entity]]:
        pairs: set[tuple[Entity, Entity]] = set()
        for bucket in self._cells.values():
            count = len(bucket)
            for i in range(count):
                for j in range(i + 1, count):
                    a, b = bucket[i], bucket[j]
                    pairs.add((a, b) if a < b else (b, a))
        return pairs


class PhysicsSystem(System):
    """Integrates bodies and resolves collisions once per fixed step."""

    priority = 100

    def __init__(
        self,
        *,
        gravity: Vec2 | None = None,
        cell_size: float = 64.0,
        events: EventBus | None = None,
    ) -> None:
        self.gravity = gravity if gravity is not None else Vec2.zero()
        self.events = events
        self._hash = _SpatialHash(cell_size)
        self._contacts: set[tuple[Entity, Entity]] = set()

    def update(self, world: World, time: GameTime) -> None:
        dt = time.dt
        if dt <= 0.0:
            return
        self._integrate(world, dt)
        self._resolve(world)

    # -- integration ----------------------------------------------------------
    def _integrate(self, world: World, dt: float) -> None:
        for _entity, transform, body in world.query(Transform, RigidBody):
            transform.sync_previous()
            if body.body_type is BodyType.STATIC:
                continue
            velocity = body.velocity
            if body.body_type is BodyType.DYNAMIC:
                velocity = velocity + self.gravity * (body.gravity_scale * dt)
                if body.drag > 0.0:
                    velocity = velocity * max(0.0, 1.0 - body.drag * dt)
            body.velocity = velocity
            transform.position = transform.position + velocity * dt

    # -- collision ------------------------------------------------------------
    def _resolve(self, world: World) -> None:
        self._hash.clear()
        colliders = world.query(Transform, Collider)
        transforms: dict[Entity, Transform] = {}
        col_map: dict[Entity, Collider] = {}
        for entity, transform, collider in colliders:
            transforms[entity] = transform
            col_map[entity] = collider
            self._hash.insert(entity, collider.aabb(transform))

        current: set[tuple[Entity, Entity]] = set()
        for a, b in self._hash.candidate_pairs():
            ca, cb = col_map[a], col_map[b]
            if (ca.mask & cb.layer) == 0 and (cb.mask & ca.layer) == 0:
                continue
            contact = self._narrow_phase(transforms[a], ca, transforms[b], cb)
            if contact is None:
                continue
            current.add((a, b))
            trigger = ca.is_trigger or cb.is_trigger
            if (a, b) not in self._contacts and self.events is not None:
                self.events.publish(
                    CollisionEnter(a, b, contact.normal, contact.penetration, trigger)
                )
            if not trigger:
                self._apply_response(world, a, b, contact)

        for pair in self._contacts - current:
            if self.events is not None:
                self.events.publish(CollisionExit(pair[0], pair[1]))
        self._contacts = current

    def _narrow_phase(
        self, ta: Transform, ca: Collider, tb: Transform, cb: Collider
    ) -> _Contact | None:
        if ca.shape is ShapeType.BOX and cb.shape is ShapeType.BOX:
            return _box_vs_box(ca.aabb(ta), cb.aabb(tb))
        if ca.shape is ShapeType.CIRCLE and cb.shape is ShapeType.CIRCLE:
            return _circle_vs_circle(
                ca.world_center(ta), ca.radius, cb.world_center(tb), cb.radius
            )
        if ca.shape is ShapeType.CIRCLE:
            return _circle_vs_box(ca.world_center(ta), ca.radius, cb.aabb(tb))
        contact = _circle_vs_box(cb.world_center(tb), cb.radius, ca.aabb(ta))
        # Flip the normal so it still points from A toward B.
        return None if contact is None else _Contact(-contact.normal, contact.penetration)

    def _apply_response(self, world: World, a: Entity, b: Entity, contact: _Contact) -> None:
        body_a = world.get_component(a, RigidBody)
        body_b = world.get_component(b, RigidBody)
        inv_a = body_a.inverse_mass if body_a else 0.0
        inv_b = body_b.inverse_mass if body_b else 0.0
        inv_sum = inv_a + inv_b
        if inv_sum <= 0.0:
            return

        ta = world.require(a, Transform)
        tb = world.require(b, Transform)
        normal = contact.normal

        # Positional correction (push the pair apart along the normal).
        correction = normal * (contact.penetration / inv_sum)
        ta.position = ta.position - correction * inv_a
        tb.position = tb.position + correction * inv_b

        # Restitution impulse.
        vel_a = body_a.velocity if body_a else Vec2.zero()
        vel_b = body_b.velocity if body_b else Vec2.zero()
        relative_normal = (vel_b - vel_a).dot(normal)
        if relative_normal > 0.0:
            return  # already separating
        restitution = min(
            body_a.restitution if body_a else 0.0,
            body_b.restitution if body_b else 0.0,
        )
        impulse = -(1.0 + restitution) * relative_normal / inv_sum
        impulse_vec = normal * impulse
        if body_a is not None:
            body_a.velocity = vel_a - impulse_vec * inv_a
        if body_b is not None:
            body_b.velocity = vel_b + impulse_vec * inv_b
