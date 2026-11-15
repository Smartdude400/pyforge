from __future__ import annotations

from pyforge.clock import GameTime
from pyforge.components import Transform
from pyforge.ecs import World
from pyforge.events import EventBus
from pyforge.math import Rect, Vec2
from pyforge.physics import (
    BodyType,
    Collider,
    CollisionEnter,
    PhysicsSystem,
    RigidBody,
    ShapeType,
    _box_vs_box,
    _circle_vs_circle,
)


def step(world: World, system: PhysicsSystem, dt: float = 1.0 / 60.0, steps: int = 1) -> None:
    time = GameTime(fixed_dt=dt, dt=dt)
    for _ in range(steps):
        system.update(world, time)


def test_box_overlap_normal_and_depth() -> None:
    a = Rect(0.0, 0.0, 10.0, 10.0)
    b = Rect(8.0, 2.0, 10.0, 10.0)  # overlaps 2px on x, normal should be +x
    contact = _box_vs_box(a, b)
    assert contact is not None
    assert contact.normal == Vec2(1.0, 0.0)
    assert abs(contact.penetration - 2.0) < 1e-9


def test_boxes_not_touching() -> None:
    assert _box_vs_box(Rect(0, 0, 5, 5), Rect(100, 100, 5, 5)) is None


def test_circle_overlap() -> None:
    contact = _circle_vs_circle(Vec2(0, 0), 5.0, Vec2(6, 0), 5.0)
    assert contact is not None
    assert abs(contact.penetration - 4.0) < 1e-9
    assert contact.normal == Vec2(1.0, 0.0)


def test_gravity_integration() -> None:
    world = World()
    system = PhysicsSystem(gravity=Vec2(0.0, 100.0))
    e = world.create_entity(
        Transform(position=Vec2(0.0, 0.0)),
        Collider(shape=ShapeType.BOX, width=10, height=10),
        RigidBody(body_type=BodyType.DYNAMIC),
    )
    step(world, system, steps=10)
    # Fell downward under gravity.
    assert world.require(e, Transform).position.y > 0.0


def test_dynamic_rests_on_static_floor() -> None:
    world = World()
    system = PhysicsSystem(gravity=Vec2(0.0, 500.0))
    world.create_entity(
        Transform(position=Vec2(0.0, 100.0)),
        Collider(shape=ShapeType.BOX, width=400, height=20),
        RigidBody(body_type=BodyType.STATIC),
    )
    box = world.create_entity(
        Transform(position=Vec2(0.0, 0.0)),
        Collider(shape=ShapeType.BOX, width=20, height=20),
        RigidBody(body_type=BodyType.DYNAMIC),
    )
    step(world, system, steps=120)
    pos = world.require(box, Transform).position
    # Box should settle on top of the floor: floor top = 90, box half = 10.
    assert abs(pos.y - 80.0) < 2.0


def test_trigger_emits_event_without_response() -> None:
    bus = EventBus()
    events: list[CollisionEnter] = []
    bus.subscribe(CollisionEnter, events.append)
    world = World()
    system = PhysicsSystem(events=bus)
    world.create_entity(
        Transform(position=Vec2(0.0, 0.0)),
        Collider(shape=ShapeType.BOX, width=20, height=20, is_trigger=True),
        RigidBody(body_type=BodyType.STATIC),
    )
    world.create_entity(
        Transform(position=Vec2(5.0, 0.0)),
        Collider(shape=ShapeType.BOX, width=20, height=20),
        RigidBody(body_type=BodyType.DYNAMIC, gravity_scale=0.0),
    )
    step(world, system)
    assert len(events) == 1
    assert events[0].trigger is True
