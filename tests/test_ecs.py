from __future__ import annotations

from dataclasses import dataclass

from pyforge.clock import GameTime
from pyforge.ecs import Component, System, World


@dataclass(slots=True)
class Position(Component):
    x: float = 0.0
    y: float = 0.0


@dataclass(slots=True)
class Velocity(Component):
    dx: float = 0.0
    dy: float = 0.0


def make_time() -> GameTime:
    return GameTime(fixed_dt=1.0 / 60.0, dt=1.0 / 60.0)


def test_create_and_query() -> None:
    world = World()
    e1 = world.create_entity(Position(1.0, 2.0), Velocity(1.0, 0.0))
    world.create_entity(Position(0.0, 0.0))
    assert world.entity_count == 2
    rows = world.query(Position, Velocity)
    assert len(rows) == 1
    entity, pos, vel = rows[0]
    assert entity == e1 and pos.x == 1.0 and vel.dx == 1.0


def test_get_require_has() -> None:
    world = World()
    e = world.create_entity(Position(5.0, 5.0))
    assert world.has_component(e, Position)
    assert world.require(e, Position).x == 5.0
    assert world.get_component(e, Velocity) is None


def test_deferred_remove_and_destroy() -> None:
    world = World()
    e = world.create_entity(Position(), Velocity())
    world.remove_component(e, Velocity)
    # Still present until flush.
    assert world.has_component(e, Velocity)
    world.flush()
    assert not world.has_component(e, Velocity)

    world.destroy_entity(e)
    assert world.is_alive(e)
    world.flush()
    assert not world.is_alive(e)
    assert world.entity_count == 0


def test_query_snapshot_is_safe_during_mutation() -> None:
    world = World()
    for i in range(5):
        world.create_entity(Position(float(i), 0.0))
    seen = 0
    for entity, _pos in world.query(Position):
        seen += 1
        world.destroy_entity(entity)  # mutate while iterating snapshot
    assert seen == 5
    world.flush()
    assert world.entity_count == 0


def test_systems_run_in_priority_order() -> None:
    order: list[str] = []

    class A(System):
        priority = 10

        def update(self, world: World, time: GameTime) -> None:
            order.append("A")

    class B(System):
        priority = -5

        def update(self, world: World, time: GameTime) -> None:
            order.append("B")

    world = World()
    world.add_system(A())
    world.add_system(B())
    world.update(make_time())
    assert order == ["B", "A"]


def test_movement_system_integration() -> None:
    class Movement(System):
        def update(self, world: World, time: GameTime) -> None:
            for _e, pos, vel in world.query(Position, Velocity):
                pos.x += vel.dx * time.dt
                pos.y += vel.dy * time.dt

    world = World()
    e = world.create_entity(Position(0.0, 0.0), Velocity(60.0, 0.0))
    world.add_system(Movement())
    world.update(make_time())
    assert abs(world.require(e, Position).x - 1.0) < 1e-9
