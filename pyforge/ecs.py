"""A lightweight, archetype-free Entity-Component-System.

Design choices and trade-offs
-----------------------------
* **Entities are ints.** Cheap to create, copy and store in spatial structures.
* **Components are dataclasses** subclassing :class:`Component`. Storage is a
  ``dict[type, dict[Entity, Component]]`` ("sparse set" style). This favours
  simple, dynamic add/remove over the raw cache locality of an archetype ECS —
  the right trade for a Python engine where attribute access dominates anyway.
* **Queries pick the smallest matching pool** and probe the rest, then return a
  *materialised snapshot*. That makes adding/removing components or destroying
  entities safe while iterating query results.
* **Structural removals are deferred** and flushed between systems, so a system
  never observes an entity half-destroyed.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, NewType, TypeVar, overload

if TYPE_CHECKING:
    from .clock import GameTime

__all__ = ["Component", "Entity", "System", "World"]

Entity = NewType("Entity", int)

C = TypeVar("C", bound="Component")
C1 = TypeVar("C1", bound="Component")
C2 = TypeVar("C2", bound="Component")
C3 = TypeVar("C3", bound="Component")
C4 = TypeVar("C4", bound="Component")


class Component:
    """Marker base class for components. Subclass with ``@dataclass``."""

    __slots__ = ()


class System:
    """Base class for systems. Lower ``priority`` runs earlier each step.

    Override :meth:`update` for per-step logic. :meth:`on_added` /
    :meth:`on_removed` fire when the system is attached to / detached from a
    world, which is handy for wiring event-bus subscriptions.
    """

    priority: int = 0

    def on_added(self, world: World) -> None:
        """Called when the system is registered with a world."""

    def on_removed(self, world: World) -> None:
        """Called when the system is removed from a world."""

    def update(self, world: World, time: GameTime) -> None:
        """Per-fixed-step update. Override in subclasses."""


class World:
    """Container of entities, components and systems."""

    def __init__(self) -> None:
        self._next_id: int = 1
        self._entities: set[Entity] = set()
        self._components: dict[type, dict[Entity, Component]] = {}
        self._systems: list[System] = []
        self._destroy_queue: list[Entity] = []
        self._remove_queue: list[tuple[Entity, type]] = []

    # -- entities -------------------------------------------------------------
    def create_entity(self, *components: Component) -> Entity:
        """Create an entity, optionally attaching ``components`` immediately."""
        entity = Entity(self._next_id)
        self._next_id += 1
        self._entities.add(entity)
        for component in components:
            self.add_component(entity, component)
        return entity

    def is_alive(self, entity: Entity) -> bool:
        return entity in self._entities

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    def destroy_entity(self, entity: Entity) -> None:
        """Queue ``entity`` for destruction; applied on the next :meth:`flush`."""
        if entity in self._entities:
            self._destroy_queue.append(entity)

    # -- components -----------------------------------------------------------
    def add_component(self, entity: Entity, component: Component) -> None:
        if entity not in self._entities:
            raise KeyError(f"entity {entity} is not alive")
        pool = self._components.setdefault(type(component), {})
        pool[entity] = component

    def remove_component(self, entity: Entity, component_type: type[C]) -> None:
        """Queue removal of a component; applied on the next :meth:`flush`."""
        self._remove_queue.append((entity, component_type))

    def get_component(self, entity: Entity, component_type: type[C]) -> C | None:
        pool = self._components.get(component_type)
        if pool is None:
            return None
        component = pool.get(entity)
        return component  # type: ignore[return-value]

    def require(self, entity: Entity, component_type: type[C]) -> C:
        """Like :meth:`get_component` but raises if the component is missing."""
        component = self.get_component(entity, component_type)
        if component is None:
            raise KeyError(f"entity {entity} has no {component_type.__name__}")
        return component

    def has_component(self, entity: Entity, component_type: type) -> bool:
        pool = self._components.get(component_type)
        return pool is not None and entity in pool

    # -- queries --------------------------------------------------------------
    def entities_with(self, component_type: type[C]) -> list[Entity]:
        pool = self._components.get(component_type)
        return list(pool.keys()) if pool else []

    @overload
    def query(self, c1: type[C1], /) -> list[tuple[Entity, C1]]: ...
    @overload
    def query(self, c1: type[C1], c2: type[C2], /) -> list[tuple[Entity, C1, C2]]: ...
    @overload
    def query(
        self, c1: type[C1], c2: type[C2], c3: type[C3], /
    ) -> list[tuple[Entity, C1, C2, C3]]: ...
    @overload
    def query(
        self, c1: type[C1], c2: type[C2], c3: type[C3], c4: type[C4], /
    ) -> list[tuple[Entity, C1, C2, C3, C4]]: ...

    def query(self, *component_types: type) -> list[Any]:
        """Return a snapshot of ``(entity, *components)`` matching every type.

        Iterating the result is safe against component add/remove and entity
        destruction performed inside the loop. The public overloads above give
        precise tuple types; this implementation returns ``list[Any]`` because
        ``list`` is invariant and cannot unify the overload return types.
        """
        if not component_types:
            return []
        pools = [self._components.get(t) for t in component_types]
        if any(pool is None for pool in pools):
            return []
        # Drive iteration from the smallest pool to minimise probes.
        smallest_index = min(range(len(pools)), key=lambda i: len(pools[i]))  # type: ignore[arg-type]
        driver = pools[smallest_index]
        assert driver is not None
        results: list[tuple[object, ...]] = []
        for entity, driver_component in driver.items():
            row: list[object] = [entity]
            ok = True
            for i, pool in enumerate(pools):
                if i == smallest_index:
                    row.append(driver_component)
                    continue
                assert pool is not None
                component = pool.get(entity)
                if component is None:
                    ok = False
                    break
                row.append(component)
            if ok:
                results.append(tuple(row))
        return results

    # -- systems --------------------------------------------------------------
    def add_system(self, system: System) -> System:
        """Register a system; systems are kept sorted by ``priority``."""
        self._systems.append(system)
        self._systems.sort(key=lambda s: s.priority)
        system.on_added(self)
        return system

    def remove_system(self, system: System) -> None:
        if system in self._systems:
            self._systems.remove(system)
            system.on_removed(self)

    def get_system(self, system_type: type[C]) -> C | None:
        for system in self._systems:
            if isinstance(system, system_type):
                return system
        return None

    @property
    def systems(self) -> Iterator[System]:
        return iter(self._systems)

    # -- step -----------------------------------------------------------------
    def update(self, time: GameTime) -> None:
        """Run every system in priority order, flushing between each."""
        for system in tuple(self._systems):
            system.update(self, time)
            self.flush()

    def flush(self) -> None:
        """Apply all queued component removals and entity destructions."""
        if self._remove_queue:
            for entity, component_type in self._remove_queue:
                pool = self._components.get(component_type)
                if pool is not None:
                    pool.pop(entity, None)
            self._remove_queue.clear()
        if self._destroy_queue:
            for entity in self._destroy_queue:
                if entity not in self._entities:
                    continue
                for pool in self._components.values():
                    pool.pop(entity, None)
                self._entities.discard(entity)
            self._destroy_queue.clear()

    def clear(self) -> None:
        """Remove all entities and components (systems are kept)."""
        self._entities.clear()
        self._components.clear()
        self._destroy_queue.clear()
        self._remove_queue.clear()
