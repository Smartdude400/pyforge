"""Stack-based scene management.

The :class:`SceneManager` keeps a stack of scenes. The top scene is *active*
(receives input and fixed updates); scenes below it are *paused* but still
drawn when ``transparent`` is set (useful for a pause menu over the game).

Each :class:`Scene` owns its own ECS :class:`~pyforge.ecs.World`, so swapping
scenes never leaks entities between them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .ecs import World

if TYPE_CHECKING:
    import pygame

    from .app import App
    from .clock import GameTime
    from .render import Renderer

__all__ = ["Scene", "SceneManager"]


class Scene:
    """Base class for a game screen (menu, level, pause overlay, ...).

    Override the lifecycle hooks you need. ``app`` is injected by the
    :class:`SceneManager` before :meth:`on_enter` is called, giving the scene
    access to shared services (assets, input, audio, events).
    """

    #: If True, the scene directly below this one is still drawn (overlay).
    transparent: bool = False
    #: If True, the scene directly below still receives fixed updates.
    update_below: bool = False

    def __init__(self) -> None:
        self.world: World = World()
        self._app: App | None = None

    @property
    def app(self) -> App:
        if self._app is None:
            raise RuntimeError("scene is not attached to an App yet")
        return self._app

    def _attach(self, app: App) -> None:
        self._app = app

    # -- lifecycle hooks ------------------------------------------------------
    def on_enter(self) -> None:
        """Called once when the scene is pushed onto the stack."""

    def on_exit(self) -> None:
        """Called once when the scene is popped from the stack."""

    def on_pause(self) -> None:
        """Called when another scene is pushed on top of this one."""

    def on_resume(self) -> None:
        """Called when the scene above this one is popped, re-activating it."""

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle a raw pygame event (only the active scene receives these)."""

    def fixed_update(self, time: GameTime) -> None:
        """Fixed-timestep simulation step. Default: step the scene's world."""
        self.world.update(time)

    def variable_update(self, time: GameTime) -> None:
        """Per-render-frame update (animations, camera smoothing)."""

    def draw(self, renderer: Renderer) -> None:
        """Render the scene."""


class SceneManager:
    """Owns the scene stack and dispatches the loop to the active scene(s)."""

    def __init__(self, app: App) -> None:
        self._app = app
        self._stack: list[Scene] = []

    @property
    def current(self) -> Scene | None:
        return self._stack[-1] if self._stack else None

    @property
    def stack_size(self) -> int:
        return len(self._stack)

    @property
    def is_empty(self) -> bool:
        return not self._stack

    # -- stack operations -----------------------------------------------------
    def push(self, scene: Scene) -> None:
        """Push a new active scene; the previous active scene is paused."""
        if self._stack:
            self._stack[-1].on_pause()
        scene._attach(self._app)
        self._stack.append(scene)
        scene.on_enter()

    def pop(self) -> Scene | None:
        """Pop the active scene, resuming the one beneath it."""
        if not self._stack:
            return None
        scene = self._stack.pop()
        scene.on_exit()
        if self._stack:
            self._stack[-1].on_resume()
        return scene

    def replace(self, scene: Scene) -> None:
        """Replace the active scene without touching scenes below it."""
        if self._stack:
            old = self._stack.pop()
            old.on_exit()
        scene._attach(self._app)
        self._stack.append(scene)
        scene.on_enter()

    def set_root(self, scene: Scene) -> None:
        """Clear the whole stack and start fresh with ``scene``."""
        self.clear()
        self.push(scene)

    def clear(self) -> None:
        while self._stack:
            self._stack.pop().on_exit()

    # -- loop dispatch --------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if self._stack:
            self._stack[-1].handle_event(event)

    def fixed_update(self, time: GameTime) -> None:
        # Walk from the top down, stopping at the first scene that does not
        # allow the one below it to update.
        for scene in self._active_slice(self._update_depth()):
            scene.fixed_update(time)

    def variable_update(self, time: GameTime) -> None:
        for scene in self._active_slice(self._update_depth()):
            scene.variable_update(time)

    def draw(self, renderer: Renderer) -> None:
        # Draw bottom-up so overlays render on top.
        for scene in self._active_slice(self._draw_depth()):
            scene.draw(renderer)

    # -- helpers --------------------------------------------------------------
    def _update_depth(self) -> int:
        # A scene is active if every scene above it set ``update_below``.
        depth = 1
        i = len(self._stack) - 1
        while i > 0 and self._stack[i].update_below:
            depth += 1
            i -= 1
        return depth

    def _draw_depth(self) -> int:
        # A scene is drawn if every scene above it is ``transparent``.
        depth = 1
        i = len(self._stack) - 1
        while i > 0 and self._stack[i].transparent:
            depth += 1
            i -= 1
        return depth

    def _active_slice(self, depth: int) -> list[Scene]:
        if depth <= 0 or not self._stack:
            return []
        return self._stack[-depth:]
