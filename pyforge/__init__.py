"""PyForge — a modular, fixed-timestep 2D game engine built on pygame-ce.

Quickstart
----------
::

    import pyforge as pf

    class MyScene(pf.Scene):
        def on_enter(self) -> None:
            self.world.create_entity(
                pf.Transform(position=pf.Vec2(100, 100)),
                pf.Sprite(surface=my_surface),
            )

    app = pf.App(pf.AppConfig(title="My Game"))
    app.run(MyScene())
"""

from __future__ import annotations

from .animation import Animation, AnimationSystem, Animator, SpriteSheet
from .app import App, AppConfig
from .assets import AssetManager
from .audio import AudioManager
from .camera import Camera2D
from .clock import FrameStats, GameTime
from .components import Name, Sprite, SpriteRenderSystem, Transform
from .config import SaveManager, Settings
from .debug import Console, DebugOverlay, configure_logging, get_logger
from .ecs import Component, Entity, System, World
from .events import EventBus, Subscription
from .input import (
    Binding,
    InputManager,
    KeyBind,
    MouseBind,
    PadAxisBind,
    PadButtonBind,
)
from .math import Rect, Vec2, approx, clamp, lerp, sign
from .particles import Particle, ParticleEmitter, ParticleSystem
from .physics import (
    BodyType,
    Collider,
    CollisionEnter,
    CollisionExit,
    PhysicsSystem,
    RigidBody,
    ShapeType,
)
from .render import Color, Layer, Renderer
from .scene import Scene, SceneManager
from .tilemap import TileMap
from .ui import Button, Label, Panel, UIRoot, Widget, anchor

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # math
    "Vec2", "Rect", "clamp", "lerp", "sign", "approx",
    # core
    "App", "AppConfig", "Scene", "SceneManager",
    "World", "Entity", "Component", "System",
    "GameTime", "FrameStats", "EventBus", "Subscription",
    # rendering
    "Renderer", "Color", "Layer", "Camera2D",
    "Transform", "Sprite", "Name", "SpriteRenderSystem",
    "SpriteSheet", "Animation", "Animator", "AnimationSystem",
    "TileMap",
    # input
    "InputManager", "Binding", "KeyBind", "MouseBind", "PadButtonBind", "PadAxisBind",
    # assets / audio
    "AssetManager", "AudioManager",
    # physics
    "PhysicsSystem", "RigidBody", "Collider", "BodyType", "ShapeType",
    "CollisionEnter", "CollisionExit",
    # particles
    "ParticleSystem", "ParticleEmitter", "Particle",
    # ui
    "UIRoot", "Widget", "Label", "Button", "Panel", "anchor",
    # config / debug
    "Settings", "SaveManager",
    "DebugOverlay", "Console", "configure_logging", "get_logger",
]
