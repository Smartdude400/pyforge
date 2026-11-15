"""A small typed publish/subscribe event bus for decoupled subsystem comms.

Events are plain classes (often dataclasses). Subscribers register a callback
against an event *type* and receive every instance published of that type::

    @dataclass
    class PlayerDied:
        score: int

    bus = EventBus()
    bus.subscribe(PlayerDied, lambda e: print(e.score))
    bus.publish(PlayerDied(score=42))
"""

from __future__ import annotations

import contextlib
from collections import defaultdict
from collections.abc import Callable
from typing import TypeVar

__all__ = ["EventBus", "Subscription"]

E = TypeVar("E")
Listener = Callable[[object], None]


class Subscription:
    """Handle returned by :meth:`EventBus.subscribe`; call to unsubscribe."""

    __slots__ = ("_active", "_bus", "_event_type", "_listener")

    def __init__(self, bus: EventBus, event_type: type, listener: Listener) -> None:
        self._bus = bus
        self._event_type = event_type
        self._listener = listener
        self._active = True

    def unsubscribe(self) -> None:
        if self._active:
            self._bus._remove(self._event_type, self._listener)
            self._active = False

    def __call__(self) -> None:
        self.unsubscribe()


class EventBus:
    """Synchronous, type-keyed event dispatcher.

    Publishing iterates over a snapshot of listeners, so handlers may safely
    subscribe or unsubscribe (including unsubscribing themselves) during
    dispatch without corrupting iteration.
    """

    def __init__(self) -> None:
        self._listeners: dict[type, list[Listener]] = defaultdict(list)

    def subscribe(self, event_type: type[E], listener: Callable[[E], None]) -> Subscription:
        """Register ``listener`` for ``event_type``; returns an unsubscribe handle."""
        # Stored as the erased Listener type; safe because we only ever call it
        # with instances of event_type.
        erased: Listener = listener  # type: ignore[assignment]
        self._listeners[event_type].append(erased)
        return Subscription(self, event_type, erased)

    def publish(self, event: object) -> None:
        """Dispatch ``event`` to every listener registered for its exact type."""
        listeners = self._listeners.get(type(event))
        if not listeners:
            return
        for listener in tuple(listeners):
            listener(event)

    def clear(self) -> None:
        """Remove all subscriptions (e.g. when tearing down a scene)."""
        self._listeners.clear()

    def _remove(self, event_type: type, listener: Listener) -> None:
        bucket = self._listeners.get(event_type)
        if bucket is None:
            return
        with contextlib.suppress(ValueError):
            bucket.remove(listener)
        if not bucket:
            del self._listeners[event_type]
