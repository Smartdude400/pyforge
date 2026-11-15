"""Input handling with a rebindable action-mapping layer.

Bind logical *actions* ("jump", "move_x") to physical inputs (keys, mouse
buttons, gamepad buttons/axes). Gameplay code asks about actions, never raw
keys, so rebinding and gamepad support come for free::

    inp.bind_action("jump", KeyBind(pygame.K_SPACE), PadButtonBind(0))
    inp.bind_axis("move_x", PadAxisBind(0), KeyBind(pygame.K_d), KeyBind(pygame.K_a, -1))
    ...
    if inp.just_pressed("jump"): ...
    velocity_x = inp.axis("move_x") * speed
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass

import pygame

from .math import Vec2

__all__ = [
    "Binding",
    "InputManager",
    "KeyBind",
    "MouseBind",
    "PadAxisBind",
    "PadButtonBind",
]


@dataclass(frozen=True)
class Binding:
    """Base class for a physical input bound to an action.

    Decorated as a (field-less) frozen dataclass so subclass bindings can be
    serialised generically via :func:`dataclasses.asdict`.
    """

    def is_active(self, mgr: InputManager) -> bool:
        return self.value(mgr) >= 0.5

    def value(self, mgr: InputManager) -> float:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class KeyBind(Binding):
    """A keyboard key. ``scale`` lets one key drive a negative axis side."""

    key: int
    scale: float = 1.0

    def value(self, mgr: InputManager) -> float:
        return self.scale if mgr.key_held(self.key) else 0.0


@dataclass(frozen=True, slots=True)
class MouseBind(Binding):
    """A mouse button (0 = left, 1 = middle, 2 = right)."""

    button: int
    scale: float = 1.0

    def value(self, mgr: InputManager) -> float:
        return self.scale if mgr.mouse_held(self.button) else 0.0


@dataclass(frozen=True, slots=True)
class PadButtonBind(Binding):
    button: int
    scale: float = 1.0
    pad: int = 0

    def value(self, mgr: InputManager) -> float:
        return self.scale if mgr.pad_button_held(self.pad, self.button) else 0.0


@dataclass(frozen=True, slots=True)
class PadAxisBind(Binding):
    """A gamepad analog axis. ``direction`` selects which half maps positive."""

    axis: int
    direction: float = 1.0
    deadzone: float = 0.2
    pad: int = 0

    def value(self, mgr: InputManager) -> float:
        raw = mgr.pad_axis(self.pad, self.axis) * self.direction
        if raw < self.deadzone:
            return 0.0
        return (raw - self.deadzone) / (1.0 - self.deadzone)


_BINDING_TYPES: dict[str, type[Binding]] = {
    cls.__name__: cls for cls in (KeyBind, MouseBind, PadButtonBind, PadAxisBind)
}


class InputManager:
    """Polls devices each frame and resolves bound actions and axes."""

    def __init__(self) -> None:
        self._action_bindings: dict[str, list[Binding]] = {}
        self._active: set[str] = set()
        self._just_pressed: set[str] = set()
        self._just_released: set[str] = set()

        self._keys: Sequence[bool] = []
        self._mouse_buttons: tuple[bool, ...] = (False, False, False, False, False)
        self._mouse_buttons_prev: tuple[bool, ...] = (False, False, False, False, False)
        self._mouse_pos = Vec2(0.0, 0.0)
        self._mouse_prev = Vec2(0.0, 0.0)
        self._scroll = 0.0
        self._scroll_accum = 0.0

        self._joysticks: dict[int, pygame.joystick.JoystickType] = {}

    # -- binding configuration ------------------------------------------------
    def bind_action(self, action: str, *bindings: Binding) -> None:
        """Bind one or more physical inputs to a digital ``action``."""
        self._action_bindings.setdefault(action, []).extend(bindings)

    def bind_axis(self, action: str, *bindings: Binding) -> None:
        """Alias of :meth:`bind_action`; reads back via :meth:`axis`/:meth:`value`."""
        self.bind_action(action, *bindings)

    def clear_bindings(self, action: str | None = None) -> None:
        if action is None:
            self._action_bindings.clear()
        else:
            self._action_bindings.pop(action, None)

    def export_bindings(self) -> dict[str, list[dict[str, object]]]:
        """Serialise bindings to plain data (for settings persistence)."""
        out: dict[str, list[dict[str, object]]] = {}
        for action, binds in self._action_bindings.items():
            out[action] = [{"type": type(b).__name__, **asdict(b)} for b in binds]
        return out

    def import_bindings(self, data: dict[str, list[dict[str, object]]]) -> None:
        """Rebuild bindings from :meth:`export_bindings` data, replacing current."""
        self._action_bindings.clear()
        for action, binds in data.items():
            for raw in binds:
                fields = dict(raw)
                kind = fields.pop("type", None)
                binding_cls = _BINDING_TYPES.get(str(kind))
                if binding_cls is not None:
                    self.bind_action(action, binding_cls(**fields))

    # -- device callbacks -----------------------------------------------------
    def attach_joystick(self, joystick: pygame.joystick.JoystickType) -> None:
        joystick.init()
        self._joysticks[joystick.get_instance_id()] = joystick

    def process_event(self, event: pygame.event.Event) -> None:
        """Feed a pygame event; handles wheel scroll and gamepad hotplug."""
        if event.type == pygame.MOUSEWHEEL:
            self._scroll_accum += event.y
        elif event.type == pygame.JOYDEVICEADDED:
            self.attach_joystick(pygame.joystick.Joystick(event.device_index))
        elif event.type == pygame.JOYDEVICEREMOVED:
            self._joysticks.pop(event.instance_id, None)

    # -- per-frame -----------------------------------------------------------
    def new_frame(self) -> None:
        """Reset per-frame accumulators; call before pumping events."""
        self._mouse_prev = self._mouse_pos
        self._scroll = self._scroll_accum
        self._scroll_accum = 0.0

    def update(self) -> None:
        """Snapshot devices and recompute action edge states. Call after events."""
        self._keys = pygame.key.get_pressed()
        self._mouse_buttons_prev = self._mouse_buttons
        self._mouse_buttons = pygame.mouse.get_pressed(num_buttons=5)
        mx, my = pygame.mouse.get_pos()
        self._mouse_pos = Vec2(float(mx), float(my))

        current = {a for a in self._action_bindings if self._resolve(a) >= 0.5}
        self._set_active(current)

    def _set_active(self, current: set[str]) -> None:
        """Diff ``current`` against last frame to derive edge states."""
        previous = self._active
        self._just_pressed = current - previous
        self._just_released = previous - current
        self._active = current

    def _resolve(self, action: str) -> float:
        best = 0.0
        for binding in self._action_bindings.get(action, ()):
            best = max(best, binding.value(self))
        return best

    # -- action queries -------------------------------------------------------
    def held(self, action: str) -> bool:
        return action in self._active

    def just_pressed(self, action: str) -> bool:
        return action in self._just_pressed

    def just_released(self, action: str) -> bool:
        return action in self._just_released

    def value(self, action: str) -> float:
        """Analog magnitude of an action in ``[0, 1]`` (1.0 for digital held)."""
        return self._resolve(action)

    def axis(self, action: str) -> float:
        """Signed axis value combining all bindings (their ``scale``/direction)."""
        total = 0.0
        for binding in self._action_bindings.get(action, ()):
            total += binding.value(self)
        return max(-1.0, min(1.0, total))

    def vector(self, x_action: str, y_action: str) -> Vec2:
        """A 2D movement vector from two axis actions, clamped to unit length."""
        return Vec2(self.axis(x_action), self.axis(y_action)).clamp_length(1.0)

    # -- raw device state -----------------------------------------------------
    def key_held(self, key: int) -> bool:
        # pygame's ScancodeWrapper maps high keycodes (arrows, F-keys) internally
        # and never raises; a plain list (used in tests) may, so guard with except.
        try:
            return bool(self._keys[key])
        except (IndexError, KeyError):
            return False

    def mouse_held(self, button: int) -> bool:
        if not 0 <= button < len(self._mouse_buttons):
            return False
        return bool(self._mouse_buttons[button])

    def mouse_pressed(self, button: int) -> bool:
        """True only on the frame ``button`` transitions to down."""
        if not 0 <= button < len(self._mouse_buttons):
            return False
        return bool(self._mouse_buttons[button]) and not bool(self._mouse_buttons_prev[button])

    def mouse_released(self, button: int) -> bool:
        """True only on the frame ``button`` transitions to up."""
        if not 0 <= button < len(self._mouse_buttons):
            return False
        return not bool(self._mouse_buttons[button]) and bool(self._mouse_buttons_prev[button])

    @property
    def mouse_position(self) -> Vec2:
        return self._mouse_pos

    @property
    def mouse_delta(self) -> Vec2:
        return self._mouse_pos - self._mouse_prev

    @property
    def scroll(self) -> float:
        return self._scroll

    def pad_button_held(self, pad: int, button: int) -> bool:
        joystick = self._pad(pad)
        if joystick is None or button >= joystick.get_numbuttons():
            return False
        return bool(joystick.get_button(button))

    def pad_axis(self, pad: int, axis: int) -> float:
        joystick = self._pad(pad)
        if joystick is None or axis >= joystick.get_numaxes():
            return 0.0
        return float(joystick.get_axis(axis))

    def _pad(self, index: int) -> pygame.joystick.JoystickType | None:
        pads = list(self._joysticks.values())
        return pads[index] if 0 <= index < len(pads) else None
