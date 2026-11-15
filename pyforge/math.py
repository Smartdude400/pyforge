"""2D math primitives: :class:`Vec2`, :class:`Rect`, and scalar helpers.

This module is intentionally dependency-free (no pygame import) so it can be
unit-tested headlessly and reused by every other subsystem.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Final

__all__ = ["Rect", "Vec2", "approx", "clamp", "lerp", "sign"]

_EPSILON: Final = 1e-9


def clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into the inclusive range ``[low, high]``."""
    if value < low:
        return low
    if value > high:
        return high
    return value


def lerp(a: float, b: float, t: float) -> float:
    """Linearly interpolate from ``a`` to ``b`` by ``t`` (unclamped)."""
    return a + (b - a) * t


def sign(value: float) -> float:
    """Return -1.0, 0.0 or 1.0 matching the sign of ``value``."""
    if value > 0.0:
        return 1.0
    if value < 0.0:
        return -1.0
    return 0.0


def approx(a: float, b: float, epsilon: float = _EPSILON) -> bool:
    """Return True if ``a`` and ``b`` are within ``epsilon`` of each other."""
    return abs(a - b) <= epsilon


@dataclass(frozen=True, slots=True)
class Vec2:
    """An immutable 2D vector with float components.

    Operations return new vectors, which keeps gameplay code easy to reason
    about. For allocation-sensitive inner loops, prefer working with the raw
    ``x``/``y`` floats directly.
    """

    x: float = 0.0
    y: float = 0.0

    # -- construction helpers -------------------------------------------------
    @staticmethod
    def zero() -> Vec2:
        return Vec2(0.0, 0.0)

    @staticmethod
    def one() -> Vec2:
        return Vec2(1.0, 1.0)

    @staticmethod
    def from_angle(radians: float, length: float = 1.0) -> Vec2:
        """Unit (or ``length``) vector pointing at ``radians`` (0 = +x, CCW)."""
        return Vec2(math.cos(radians) * length, math.sin(radians) * length)

    # -- operators ------------------------------------------------------------
    def __add__(self, other: Vec2) -> Vec2:
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vec2) -> Vec2:
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> Vec2:
        return Vec2(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__

    def __truediv__(self, scalar: float) -> Vec2:
        return Vec2(self.x / scalar, self.y / scalar)

    def __neg__(self) -> Vec2:
        return Vec2(-self.x, -self.y)

    def __iter__(self) -> Iterator[float]:
        yield self.x
        yield self.y

    # -- geometry -------------------------------------------------------------
    def dot(self, other: Vec2) -> float:
        return self.x * other.x + self.y * other.y

    def cross(self, other: Vec2) -> float:
        """2D scalar cross product (z-component of the 3D cross)."""
        return self.x * other.y - self.y * other.x

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def length_squared(self) -> float:
        return self.x * self.x + self.y * self.y

    def distance_to(self, other: Vec2) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def normalized(self) -> Vec2:
        """Unit vector in the same direction; zero vector stays zero."""
        length = self.length()
        if length <= _EPSILON:
            return Vec2(0.0, 0.0)
        return Vec2(self.x / length, self.y / length)

    def with_length(self, length: float) -> Vec2:
        return self.normalized() * length

    def clamp_length(self, max_length: float) -> Vec2:
        if self.length_squared() > max_length * max_length:
            return self.with_length(max_length)
        return self

    def rotated(self, radians: float) -> Vec2:
        cos_r = math.cos(radians)
        sin_r = math.sin(radians)
        return Vec2(self.x * cos_r - self.y * sin_r, self.x * sin_r + self.y * cos_r)

    def angle(self) -> float:
        """Angle in radians of this vector relative to +x."""
        return math.atan2(self.y, self.x)

    def perpendicular(self) -> Vec2:
        """Return the vector rotated 90 degrees counter-clockwise."""
        return Vec2(-self.y, self.x)

    def lerp(self, other: Vec2, t: float) -> Vec2:
        return Vec2(lerp(self.x, other.x, t), lerp(self.y, other.y, t))

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)

    def as_int_tuple(self) -> tuple[int, int]:
        return (int(self.x), int(self.y))


@dataclass(frozen=True, slots=True)
class Rect:
    """An axis-aligned float rectangle defined by top-left corner and size.

    Distinct from :class:`pygame.Rect` (which is integer-only) so physics and
    cameras can work in continuous world space.
    """

    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0

    @staticmethod
    def from_center(center: Vec2, width: float, height: float) -> Rect:
        return Rect(center.x - width / 2.0, center.y - height / 2.0, width, height)

    @staticmethod
    def from_min_max(min_x: float, min_y: float, max_x: float, max_y: float) -> Rect:
        return Rect(min_x, min_y, max_x - min_x, max_y - min_y)

    # -- edges / corners ------------------------------------------------------
    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def center(self) -> Vec2:
        return Vec2(self.x + self.width / 2.0, self.y + self.height / 2.0)

    @property
    def size(self) -> Vec2:
        return Vec2(self.width, self.height)

    @property
    def top_left(self) -> Vec2:
        return Vec2(self.x, self.y)

    # -- queries --------------------------------------------------------------
    def contains_point(self, point: Vec2) -> bool:
        return self.left <= point.x <= self.right and self.top <= point.y <= self.bottom

    def intersects(self, other: Rect) -> bool:
        return (
            self.left < other.right
            and self.right > other.left
            and self.top < other.bottom
            and self.bottom > other.top
        )

    def intersection(self, other: Rect) -> Rect | None:
        """Overlap rectangle, or None if the rects do not intersect."""
        min_x = max(self.left, other.left)
        min_y = max(self.top, other.top)
        max_x = min(self.right, other.right)
        max_y = min(self.bottom, other.bottom)
        if min_x >= max_x or min_y >= max_y:
            return None
        return Rect.from_min_max(min_x, min_y, max_x, max_y)

    def union(self, other: Rect) -> Rect:
        min_x = min(self.left, other.left)
        min_y = min(self.top, other.top)
        max_x = max(self.right, other.right)
        max_y = max(self.bottom, other.bottom)
        return Rect.from_min_max(min_x, min_y, max_x, max_y)

    def inflated(self, dx: float, dy: float) -> Rect:
        """Grow (or shrink) the rect by ``dx``/``dy`` on every side."""
        return Rect(self.x - dx, self.y - dy, self.width + 2 * dx, self.height + 2 * dy)

    def moved(self, delta: Vec2) -> Rect:
        return Rect(self.x + delta.x, self.y + delta.y, self.width, self.height)

    def with_center(self, center: Vec2) -> Rect:
        return Rect.from_center(center, self.width, self.height)
