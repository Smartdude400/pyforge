from __future__ import annotations

import math

from pyforge.math import Rect, Vec2, approx, clamp, lerp, sign


def test_vec_arithmetic() -> None:
    a = Vec2(1.0, 2.0)
    b = Vec2(3.0, -1.0)
    assert a + b == Vec2(4.0, 1.0)
    assert b - a == Vec2(2.0, -3.0)
    assert a * 2.0 == Vec2(2.0, 4.0)
    assert 2.0 * a == Vec2(2.0, 4.0)
    assert -a == Vec2(-1.0, -2.0)


def test_vec_geometry() -> None:
    assert approx(Vec2(3.0, 4.0).length(), 5.0)
    assert Vec2(3.0, 4.0).length_squared() == 25.0
    assert approx(Vec2(2.0, 0.0).normalized().length(), 1.0)
    assert Vec2(0.0, 0.0).normalized() == Vec2(0.0, 0.0)
    assert approx(Vec2(1.0, 0.0).dot(Vec2(0.0, 1.0)), 0.0)
    assert approx(Vec2(1.0, 0.0).cross(Vec2(0.0, 1.0)), 1.0)


def test_vec_rotation_and_angle() -> None:
    rotated = Vec2(1.0, 0.0).rotated(math.pi / 2)
    assert approx(rotated.x, 0.0) and approx(rotated.y, 1.0)
    assert approx(Vec2.from_angle(0.0).x, 1.0)
    assert approx(Vec2(0.0, 1.0).angle(), math.pi / 2)


def test_vec_clamp_length() -> None:
    assert approx(Vec2(10.0, 0.0).clamp_length(3.0).length(), 3.0)
    assert Vec2(1.0, 0.0).clamp_length(5.0) == Vec2(1.0, 0.0)


def test_scalars() -> None:
    assert clamp(5.0, 0.0, 3.0) == 3.0
    assert clamp(-1.0, 0.0, 3.0) == 0.0
    assert lerp(0.0, 10.0, 0.5) == 5.0
    assert sign(-2.0) == -1.0 and sign(0.0) == 0.0 and sign(4.0) == 1.0


def test_rect_intersection() -> None:
    a = Rect(0.0, 0.0, 10.0, 10.0)
    b = Rect(5.0, 5.0, 10.0, 10.0)
    assert a.intersects(b)
    overlap = a.intersection(b)
    assert overlap == Rect(5.0, 5.0, 5.0, 5.0)
    assert a.intersection(Rect(100.0, 100.0, 1.0, 1.0)) is None


def test_rect_center_and_contains() -> None:
    r = Rect.from_center(Vec2(0.0, 0.0), 4.0, 2.0)
    assert r == Rect(-2.0, -1.0, 4.0, 2.0)
    assert r.center == Vec2(0.0, 0.0)
    assert r.contains_point(Vec2(0.0, 0.0))
    assert not r.contains_point(Vec2(3.0, 0.0))
