"""A 2D camera mapping between world space and screen space."""

from __future__ import annotations

from .clock import GameTime
from .math import Rect, Vec2, clamp

__all__ = ["Camera2D"]


class Camera2D:
    """Pan/zoom camera. ``position`` is the world point at the viewport centre."""

    def __init__(self, viewport_width: int, viewport_height: int) -> None:
        self.position: Vec2 = Vec2(0.0, 0.0)
        self.zoom: float = 1.0
        self.min_zoom: float = 0.1
        self.max_zoom: float = 10.0
        self._viewport = Vec2(float(viewport_width), float(viewport_height))
        self._follow_target: Vec2 | None = None
        self._follow_smoothing: float = 0.0
        self._bounds: Rect | None = None

    # -- configuration --------------------------------------------------------
    def set_viewport(self, width: int, height: int) -> None:
        self._viewport = Vec2(float(width), float(height))

    @property
    def viewport(self) -> Vec2:
        return self._viewport

    def set_zoom(self, zoom: float) -> None:
        self.zoom = clamp(zoom, self.min_zoom, self.max_zoom)

    def set_bounds(self, bounds: Rect | None) -> None:
        """Constrain the camera centre so the view stays inside ``bounds``."""
        self._bounds = bounds

    def follow(self, target: Vec2, smoothing: float = 0.0) -> None:
        """Track ``target``. ``smoothing`` in [0,1): 0 snaps, higher = laggier."""
        self._follow_target = target
        self._follow_smoothing = clamp(smoothing, 0.0, 0.9999)

    def stop_following(self) -> None:
        self._follow_target = None

    # -- per-frame update -----------------------------------------------------
    def update(self, time: GameTime) -> None:
        if self._follow_target is not None:
            if self._follow_smoothing <= 0.0:
                self.position = self._follow_target
            else:
                # Frame-rate independent exponential smoothing.
                t = 1.0 - self._follow_smoothing ** (time.dt * 60.0 if time.dt > 0 else 1.0)
                self.position = self.position.lerp(self._follow_target, clamp(t, 0.0, 1.0))
        self._apply_bounds()

    def _apply_bounds(self) -> None:
        bounds = self._bounds
        if bounds is None:
            return
        half_w = self._viewport.x / (2.0 * self.zoom)
        half_h = self._viewport.y / (2.0 * self.zoom)
        x = self.position.x
        y = self.position.y
        if bounds.width >= 2 * half_w:
            x = clamp(x, bounds.left + half_w, bounds.right - half_w)
        else:
            x = bounds.center.x
        if bounds.height >= 2 * half_h:
            y = clamp(y, bounds.top + half_h, bounds.bottom - half_h)
        else:
            y = bounds.center.y
        self.position = Vec2(x, y)

    # -- transforms -----------------------------------------------------------
    def world_to_screen(self, world: Vec2) -> Vec2:
        offset = (world - self.position) * self.zoom
        return Vec2(offset.x + self._viewport.x / 2.0, offset.y + self._viewport.y / 2.0)

    def screen_to_world(self, screen: Vec2) -> Vec2:
        centered = Vec2(screen.x - self._viewport.x / 2.0, screen.y - self._viewport.y / 2.0)
        return centered / self.zoom + self.position

    def visible_world_rect(self) -> Rect:
        """World-space rectangle currently visible (useful for culling)."""
        half_w = self._viewport.x / (2.0 * self.zoom)
        half_h = self._viewport.y / (2.0 * self.zoom)
        return Rect(
            self.position.x - half_w,
            self.position.y - half_h,
            half_w * 2.0,
            half_h * 2.0,
        )
