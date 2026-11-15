"""Sprite-sheet slicing and frame animation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from .components import Sprite
from .ecs import Component, System, World

if TYPE_CHECKING:
    from .clock import GameTime

__all__ = ["Animation", "AnimationSystem", "Animator", "SpriteSheet"]


class SpriteSheet:
    """Slices a single texture into a grid of equally sized frames."""

    def __init__(self, texture: pygame.Surface, frame_width: int, frame_height: int) -> None:
        self.texture = texture
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.columns = texture.get_width() // frame_width
        self.rows = texture.get_height() // frame_height

    def frame(self, column: int, row: int) -> pygame.Surface:
        rect = pygame.Rect(
            column * self.frame_width,
            row * self.frame_height,
            self.frame_width,
            self.frame_height,
        )
        return self.texture.subsurface(rect).copy()

    def row_frames(
        self, row: int, start: int = 0, count: int | None = None
    ) -> list[pygame.Surface]:
        end = self.columns if count is None else min(start + count, self.columns)
        return [self.frame(c, row) for c in range(start, end)]

    def all_frames(self) -> list[pygame.Surface]:
        return [self.frame(c, r) for r in range(self.rows) for c in range(self.columns)]


@dataclass(slots=True)
class Animation:
    """An ordered list of frames played at ``fps``."""

    frames: list[pygame.Surface]
    fps: float = 12.0
    loop: bool = True

    @property
    def duration(self) -> float:
        return len(self.frames) / self.fps if self.fps > 0 else 0.0

    def frame_at(self, elapsed: float) -> tuple[pygame.Surface, bool]:
        """Return ``(frame, finished)`` for the time ``elapsed`` into the clip."""
        if not self.frames:
            raise ValueError("animation has no frames")
        if self.fps <= 0:
            return self.frames[0], True
        index = int(elapsed * self.fps)
        finished = index >= len(self.frames)
        if self.loop:
            index %= len(self.frames)
        else:
            index = min(index, len(self.frames) - 1)
        return self.frames[index], finished and not self.loop


@dataclass(slots=True)
class Animator(Component):
    """Plays named animations and writes the current frame into a :class:`Sprite`."""

    animations: dict[str, Animation] = field(default_factory=dict)
    current: str | None = None
    elapsed: float = 0.0
    speed: float = 1.0
    playing: bool = True
    finished: bool = False

    def add(self, name: str, animation: Animation) -> None:
        self.animations[name] = animation
        if self.current is None:
            self.current = name

    def play(self, name: str, *, restart: bool = False) -> None:
        if name == self.current and not restart:
            return
        if name not in self.animations:
            raise KeyError(f"no animation named {name!r}")
        self.current = name
        self.elapsed = 0.0
        self.playing = True
        self.finished = False


class AnimationSystem(System):
    """Advances every :class:`Animator` and updates its :class:`Sprite` frame."""

    priority = -50  # run before rendering

    def update(self, world: World, time: GameTime) -> None:
        for _entity, animator, sprite in world.query(Animator, Sprite):
            if not animator.playing or animator.current is None:
                continue
            clip = animator.animations.get(animator.current)
            if clip is None:
                continue
            animator.elapsed += time.dt * animator.speed
            frame, finished = clip.frame_at(animator.elapsed)
            sprite.surface = frame
            if finished:
                animator.finished = True
                animator.playing = clip.loop
