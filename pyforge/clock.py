"""Frame timing: fixed/variable delta tracking, timescale and FPS stats.

The :class:`GameTime` object is created by the :class:`~pyforge.app.App` and
passed into every update so systems never reach for a global clock.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

__all__ = ["FrameStats", "GameTime"]


@dataclass(slots=True)
class FrameStats:
    """Rolling render-loop statistics for the debug overlay."""

    fps: float = 0.0
    frame_ms: float = 0.0
    update_calls: int = 0
    _samples: deque[float] = field(default_factory=lambda: deque(maxlen=120))

    def record(self, frame_seconds: float, update_calls: int) -> None:
        self.frame_ms = frame_seconds * 1000.0
        self.update_calls = update_calls
        self._samples.append(frame_seconds)
        total = sum(self._samples)
        if total > 0.0:
            self.fps = len(self._samples) / total


@dataclass(slots=True)
class GameTime:
    """Time passed to systems each step.

    ``fixed_dt`` is the constant simulation step (seconds). ``dt`` is whichever
    delta applies to the current call — equal to ``fixed_dt * scale`` during a
    fixed update, or the real frame delta during a variable/render update.
    ``alpha`` is the [0, 1] interpolation factor between the last two fixed
    states, for smooth rendering between simulation ticks.
    """

    fixed_dt: float
    dt: float = 0.0
    scale: float = 1.0
    alpha: float = 0.0
    elapsed: float = 0.0
    frame: int = 0
    paused: bool = False

    @property
    def scaled_fixed_dt(self) -> float:
        """Fixed timestep adjusted by the current timescale (0 while paused)."""
        return 0.0 if self.paused else self.fixed_dt * self.scale
