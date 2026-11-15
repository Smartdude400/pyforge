from __future__ import annotations

from dataclasses import dataclass

from pyforge.events import EventBus


@dataclass
class Ping:
    value: int


@dataclass
class Pong:
    text: str


def test_publish_to_typed_subscribers() -> None:
    bus = EventBus()
    received: list[int] = []
    bus.subscribe(Ping, lambda e: received.append(e.value))
    bus.publish(Ping(1))
    bus.publish(Pong("ignored"))
    bus.publish(Ping(2))
    assert received == [1, 2]


def test_unsubscribe() -> None:
    bus = EventBus()
    received: list[int] = []
    sub = bus.subscribe(Ping, lambda e: received.append(e.value))
    bus.publish(Ping(1))
    sub.unsubscribe()
    bus.publish(Ping(2))
    assert received == [1]


def test_listener_may_unsubscribe_during_dispatch() -> None:
    bus = EventBus()
    calls: list[str] = []

    def once(_event: object) -> None:
        calls.append("once")
        sub.unsubscribe()

    sub = bus.subscribe(Ping, once)
    bus.subscribe(Ping, lambda _e: calls.append("always"))
    bus.publish(Ping(0))
    bus.publish(Ping(0))
    assert calls == ["once", "always", "always"]


def test_clear() -> None:
    bus = EventBus()
    received: list[int] = []
    bus.subscribe(Ping, lambda e: received.append(e.value))
    bus.clear()
    bus.publish(Ping(1))
    assert received == []
