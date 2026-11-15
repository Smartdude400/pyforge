"""End-to-end smoke test: boot the demo headlessly and run the subsystems.

Uses SDL's dummy video/audio drivers so it works in CI with no window or sound
card. It drives the real frame loop a few times, then steps the simulation
deterministically and forces a coin pickup to cover the collision→event→
particle→audio path.
"""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pyforge as pf
from examples.demo.game import Coin
from examples.demo.main import build_app
from examples.demo.scenes import GameScene, MenuScene


def fixed_time() -> pf.GameTime:
    return pf.GameTime(fixed_dt=1.0 / 60.0, dt=1.0 / 60.0)


def test_demo_boots_steps_and_collects_coin() -> None:
    app = build_app()
    try:
        # Menu runs through the real loop without error.
        app.scenes.push(MenuScene())
        for _ in range(3):
            app._frame()

        # Enter the level.
        app.scenes.replace(GameScene())
        scene = app.scenes.current
        assert isinstance(scene, GameScene)

        start_y = scene.world.require(scene.player, pf.Transform).position.y

        # Step the simulation deterministically: the player should fall and land.
        time = fixed_time()
        for _ in range(120):
            scene.fixed_update(time)
            scene.variable_update(time)
        landed_y = scene.world.require(scene.player, pf.Transform).position.y
        assert landed_y > start_y  # gravity pulled the player down onto the ground

        # Render path must run cleanly (tilemap, sprites, particles, HUD).
        app.renderer.begin_frame()
        app.scenes.draw(app.renderer)
        app.renderer.flush()

        # Force a coin pickup to exercise the trigger/event/score path.
        coins = scene.world.query(Coin, pf.Transform)
        assert coins, "level should contain coins"
        starting_score = scene.score
        starting_left = scene.coins_left
        _coin_entity, _coin, coin_transform = coins[0]
        player_transform = scene.world.require(scene.player, pf.Transform)
        player_transform.position = coin_transform.position
        body = scene.world.require(scene.player, pf.RigidBody)
        body.velocity = pf.Vec2(0.0, 0.0)

        for _ in range(3):
            scene.fixed_update(time)

        assert scene.score >= starting_score + 10
        assert scene.coins_left == starting_left - 1
    finally:
        app.shutdown()
