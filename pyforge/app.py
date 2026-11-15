"""The application host: window, services and the fixed-timestep game loop.

The loop uses the classic *accumulator* pattern so simulation runs at a fixed
rate (default 60 Hz) regardless of render framerate. Rendering happens as fast
as allowed and receives an interpolation ``alpha`` to smooth between the last
two simulation states. Gameplay therefore never depends on frame rate.

``App`` is the single explicit context object the spec calls for: it owns the
assets, input, audio, event bus, camera, renderer and scene stack, and is
injected into every :class:`~pyforge.scene.Scene`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from .assets import AssetManager
from .audio import AudioManager
from .camera import Camera2D
from .clock import FrameStats, GameTime
from .events import EventBus
from .input import InputManager
from .render import Color, Renderer
from .scene import Scene, SceneManager

__all__ = ["App", "AppConfig"]


@dataclass(slots=True)
class AppConfig:
    """Window and loop configuration."""

    title: str = "PyForge"
    width: int = 1280
    height: int = 720
    fixed_fps: int = 60
    #: Render FPS cap; 0 leaves it uncapped (still bounded by vsync if on).
    target_fps: int = 0
    vsync: bool = True
    resizable: bool = True
    clear_color: Color = (16, 16, 24)
    assets_dir: str = "assets"
    dev_mode: bool = False
    #: Largest real frame delta (seconds) fed to the loop, to avoid a death
    #: spiral after a stall (breakpoint, window drag, ...).
    max_frame_time: float = 0.25
    audio_frequency: int = 44100
    audio_channels: int = 2
    audio_buffer: int = 512


@dataclass(slots=True)
class App:
    config: AppConfig = field(default_factory=AppConfig)

    # Services (populated in __post_init__).
    surface: pygame.Surface = field(init=False)
    camera: Camera2D = field(init=False)
    renderer: Renderer = field(init=False)
    input: InputManager = field(init=False)
    assets: AssetManager = field(init=False)
    audio: AudioManager = field(init=False)
    events: EventBus = field(init=False)
    scenes: SceneManager = field(init=False)
    time: GameTime = field(init=False)
    stats: FrameStats = field(init=False)

    _running: bool = field(init=False, default=False)
    _clock: pygame.time.Clock = field(init=False)
    _accumulator: float = field(init=False, default=0.0)
    _overlay_hook: object = field(init=False, default=None)

    def __post_init__(self) -> None:
        pygame.init()
        try:
            pygame.mixer.pre_init(
                self.config.audio_frequency,
                -16,
                self.config.audio_channels,
                self.config.audio_buffer,
            )
            pygame.mixer.init()
        except pygame.error:
            # No audio device (CI, headless). AudioManager degrades gracefully.
            pass
        pygame.joystick.init()

        flags = pygame.RESIZABLE if self.config.resizable else 0
        try:
            self.surface = pygame.display.set_mode(
                (self.config.width, self.config.height),
                flags,
                vsync=1 if self.config.vsync else 0,
            )
        except pygame.error:
            self.surface = pygame.display.set_mode((self.config.width, self.config.height), flags)
        pygame.display.set_caption(self.config.title)

        self.camera = Camera2D(self.config.width, self.config.height)
        self.renderer = Renderer(self.surface, self.camera, clear_color=self.config.clear_color)
        self.input = InputManager()
        self.assets = AssetManager(self.config.assets_dir, dev_mode=self.config.dev_mode)
        self.audio = AudioManager(self.assets)
        self.events = EventBus()
        self.scenes = SceneManager(self)
        self.time = GameTime(fixed_dt=1.0 / float(self.config.fixed_fps))
        self.stats = FrameStats()
        self._clock = pygame.time.Clock()

        for index in range(pygame.joystick.get_count()):
            self.input.attach_joystick(pygame.joystick.Joystick(index))

    # -- public control -------------------------------------------------------
    @property
    def running(self) -> bool:
        return self._running

    def quit(self) -> None:
        """Request a clean shutdown after the current frame."""
        self._running = False

    @property
    def paused(self) -> bool:
        return self.time.paused

    @paused.setter
    def paused(self, value: bool) -> None:
        self.time.paused = value

    @property
    def timescale(self) -> float:
        return self.time.scale

    @timescale.setter
    def timescale(self, value: float) -> None:
        self.time.scale = max(0.0, value)

    def set_overlay(self, overlay: object) -> None:
        """Attach a debug overlay (anything with ``draw(renderer, app)``)."""
        self._overlay_hook = overlay

    # -- main loop ------------------------------------------------------------
    def run(self, initial_scene: Scene) -> None:
        """Push ``initial_scene`` and run until :meth:`quit` or window close."""
        self.scenes.push(initial_scene)
        self._running = True
        try:
            while self._running:
                self._frame()
        finally:
            self.shutdown()

    def _frame(self) -> None:
        frame_ms = self._clock.tick(self.config.target_fps)
        frame_dt = min(frame_ms / 1000.0, self.config.max_frame_time)

        self._pump_events()

        # Fixed-timestep simulation.
        self._accumulator += frame_dt
        fixed_dt = self.time.fixed_dt
        steps = 0
        max_steps = 8
        while self._accumulator >= fixed_dt and steps < max_steps:
            self._accumulator -= fixed_dt
            steps += 1
            if not self.time.paused:
                self.time.dt = fixed_dt * self.time.scale
                self.time.elapsed += self.time.dt
                self.time.frame += 1
                self.scenes.fixed_update(self.time)
        self.time.alpha = self._accumulator / fixed_dt if fixed_dt > 0 else 0.0

        # Variable (render-rate) update.
        self.time.dt = frame_dt
        self.camera.update(self.time)
        self.scenes.variable_update(self.time)
        if self.config.dev_mode:
            self.assets.hot_reload()

        # Render.
        self.renderer.begin_frame()
        self.scenes.draw(self.renderer)
        overlay = self._overlay_hook
        if overlay is not None:
            overlay.draw(self.renderer, self)  # type: ignore[attr-defined]
        self.renderer.flush()
        pygame.display.flip()

        self.stats.record(frame_dt, steps)
        if self.scenes.is_empty:
            self.quit()

    def _pump_events(self) -> None:
        self.input.new_frame()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit()
            elif event.type == pygame.VIDEORESIZE:
                self._on_resize(event.w, event.h)
            self.input.process_event(event)
            self.scenes.handle_event(event)
        self.input.update()

    def _on_resize(self, width: int, height: int) -> None:
        flags = pygame.RESIZABLE if self.config.resizable else 0
        self.surface = pygame.display.set_mode((width, height), flags)
        self.renderer.surface = self.surface
        self.camera.set_viewport(width, height)

    def shutdown(self) -> None:
        self.scenes.clear()
        pygame.quit()
