"""Demo scenes: menu, the platformer level, pause and game-over overlays."""

from __future__ import annotations

import math

import pygame

import pyforge as pf

from . import assets_gen as art
from .game import (
    GRAVITY,
    LAYER_PICKUP,
    LAYER_PLAYER,
    LAYER_WORLD,
    Coin,
    PlayerControllerSystem,
    PlayerTag,
)

# A compact level. '#': dirt, '=': grass, '.': empty, 'P': player, 'C': coin, 'F': flag.
LEVEL = [
    "........................................",
    "........................................",
    "...........C....C...............C.......",
    ".........=====........=====.......F.....",
    "..............................=====.....",
    "....C.................C.................",
    "..=====...C.......=====.................",
    "..........====.........................",
    "P.....C................C......C.........",
    "=====....========...========...........",
    "#####....########...########....========",
    "#####....########...########....########",
]
TILE = art.TILE


class MenuScene(pf.Scene):
    def on_enter(self) -> None:
        viewport = self.app.camera.viewport
        title_font = self.app.assets.font(None, 72)
        font = self.app.assets.font(None, 32)
        self.ui = pf.UIRoot()
        self.ui.add(
            pf.Label(
                "PyForge Demo",
                title_font,
                pf.Vec2(viewport.x / 2, viewport.y * 0.28),
                align="center",
                color=(120, 200, 255),
            )
        )
        self.ui.add(
            pf.Label(
                "WASD / arrows move  -  Space jumps  -  gamepad supported",
                font,
                pf.Vec2(viewport.x / 2, viewport.y * 0.4),
                align="center",
                color=(180, 188, 210),
            )
        )
        self.ui.add(
            pf.Button(
                "Play",
                font,
                pf.anchor(viewport, 220, 56, align="center", offset=pf.Vec2(0, 20)),
                self._play,
            )
        )
        self.ui.add(
            pf.Button(
                "Quit",
                font,
                pf.anchor(viewport, 220, 56, align="center", offset=pf.Vec2(0, 90)),
                self.app.quit,
            )
        )

    def _play(self) -> None:
        self.app.scenes.replace(GameScene())

    def variable_update(self, time: pf.GameTime) -> None:
        self.ui.update(self.app.input)

    def draw(self, renderer: pf.Renderer) -> None:
        self.ui.draw(renderer)


class GameScene(pf.Scene):
    def on_enter(self) -> None:
        app = self.app
        self.font = app.assets.font(None, 28)
        self.small_font = app.assets.font(None, 20)

        self.tileset = art.make_tileset()
        self.player_anim = art.make_player_animations()
        self.coin_frames = art.make_coin_animation()
        self.flag_image = art.make_flag()
        self._register_audio()

        self.tilemap = self._build_tilemap()
        self.tilemap.build_static_bodies(self.world, layer_mask=LAYER_WORLD)

        self.score = 0
        self.coins_left = 0
        self.spawn = pf.Vec2(0, 0)
        self.flag_pos = pf.Vec2(0, 0)
        self._spawn_entities()

        # Systems.
        self.world.add_system(
            PlayerControllerSystem(app.input, self.tilemap, app.audio)
        )
        self.world.add_system(pf.AnimationSystem())
        self.world.add_system(pf.PhysicsSystem(gravity=pf.Vec2(0, GRAVITY), events=app.events))
        self.world.add_system(pf.ParticleSystem())
        self.sprite_renderer = pf.SpriteRenderSystem(app.renderer)
        self.particle_renderer = pf.ParticleSystem()

        # Camera follows the player within the level bounds.
        app.camera.set_bounds(self.tilemap.bounds)

        # Coin pickups via the physics event bus.
        self._subs = [app.events.subscribe(pf.CollisionEnter, self._on_collision)]

        self.overlay = pf.DebugOverlay(self.small_font)
        app.set_overlay(self.overlay)
        self.console = self._make_console()
        self.finished = False

        if app.audio.available:
            app.audio.music_volume = 0.6
            app.audio.play_music("music.wav", fade_ms=800)

    # -- setup helpers --------------------------------------------------------
    def _register_audio(self) -> None:
        audio = self.app.audio
        if not audio.available:
            return
        self.app.assets.register_sound("jump", art.make_tone([330, 440], 120))
        self.app.assets.register_sound("coin", art.make_tone([880, 1320], 130, volume=0.4))
        self.app.assets.register_sound("win", art.make_tone([523, 659, 784], 400, volume=0.4))

    def _build_tilemap(self) -> pf.TileMap:
        rows = []
        for line in LEVEL:
            row = []
            for ch in line:
                if ch == "=":
                    row.append(0)  # grass
                elif ch == "#":
                    row.append(1)  # dirt
                else:
                    row.append(-1)
            rows.append(row)
        return pf.TileMap.from_rows(rows, TILE, self.tileset, solid_tiles={0, 1})

    def _spawn_entities(self) -> None:
        for ty, line in enumerate(LEVEL):
            for tx, ch in enumerate(line):
                center = self.tilemap.tile_center(tx, ty)
                if ch == "P":
                    # Spawn a little above the tile so the player drops in.
                    spawn = center - pf.Vec2(0, 64)
                    self.spawn = spawn
                    self._create_player(spawn)
                elif ch == "C":
                    self._create_coin(center)
                    self.coins_left += 1
                elif ch == "F":
                    self.flag_pos = center
                    self.world.create_entity(
                        pf.Transform(position=center),
                        pf.Sprite(surface=self.flag_image, layer=pf.Layer.FOREGROUND),
                    )

    def _create_player(self, position: pf.Vec2) -> None:
        animator = pf.Animator()
        animator.add("idle", pf.Animation(self.player_anim["idle"], fps=3))
        animator.add("run", pf.Animation(self.player_anim["run"], fps=12))
        animator.add("jump", pf.Animation(self.player_anim["jump"], fps=1))
        self.player = self.world.create_entity(
            PlayerTag(),
            pf.Transform(position=position, previous_position=position),
            pf.Sprite(surface=self.player_anim["idle"][0], layer=pf.Layer.ENTITIES, z=10),
            animator,
            pf.RigidBody(body_type=pf.BodyType.DYNAMIC, mass=1.0),
            pf.Collider(
                shape=pf.ShapeType.BOX,
                width=24,
                height=36,
                layer=LAYER_PLAYER,
                mask=LAYER_WORLD | LAYER_PICKUP,
            ),
            pf.ParticleEmitter(
                capacity=64,
                emitting=False,
                rate=0.0,
                direction=-math.pi / 2,
                spread=math.pi / 3,
                speed_min=20,
                speed_max=70,
                lifetime_min=0.2,
                lifetime_max=0.5,
                size_start=5,
                size_end=0,
                color_start=(200, 200, 190, 200),
                color_end=(120, 110, 100, 0),
                gravity=pf.Vec2(0, 120),
            ),
        )

    def _create_coin(self, position: pf.Vec2) -> None:
        animator = pf.Animator()
        animator.add("spin", pf.Animation(self.coin_frames, fps=10))
        self.world.create_entity(
            Coin(),
            pf.Transform(position=position),
            pf.Sprite(surface=self.coin_frames[0], layer=pf.Layer.ENTITIES),
            animator,
            pf.Collider(
                shape=pf.ShapeType.CIRCLE,
                radius=9,
                is_trigger=True,
                layer=LAYER_PICKUP,
                mask=LAYER_PLAYER,
            ),
        )

    def _make_console(self) -> pf.Console:
        console = pf.Console(self.small_font)
        console.register("give", lambda args: self._cmd_give(args))
        console.register("tp", lambda args: self._cmd_tp(args))
        console.log("console ready - try 'give 100' or 'tp 200 100'")
        return console

    def _cmd_give(self, args: list[str]) -> str:
        amount = int(args[0]) if args else 10
        self.score += amount
        return f"score += {amount}"

    def _cmd_tp(self, args: list[str]) -> str | None:
        if len(args) < 2:
            return "usage: tp <x> <y>"
        transform = self.world.require(self.player, pf.Transform)
        transform.position = pf.Vec2(float(args[0]), float(args[1]))
        return None

    # -- events ---------------------------------------------------------------
    def _on_collision(self, event: pf.CollisionEnter) -> None:
        for coin_entity, other in ((event.a, event.b), (event.b, event.a)):
            if self.world.get_component(coin_entity, Coin) is not None and other == self.player:
                self._collect(coin_entity)
                return

    def _collect(self, coin_entity: pf.Entity) -> None:
        if not self.world.is_alive(coin_entity):
            return
        position = self.world.require(coin_entity, pf.Transform).position
        self.world.destroy_entity(coin_entity)
        self.score += 10
        self.coins_left -= 1
        self.app.audio.play_sound("coin", volume=0.4)
        self._coin_sparkle(position)

    def _coin_sparkle(self, position: pf.Vec2) -> None:
        emitter = pf.ParticleEmitter(
            capacity=24,
            emitting=False,
            rate=0.0,
            spread=math.pi,
            speed_min=60,
            speed_max=140,
            lifetime_min=0.3,
            lifetime_max=0.6,
            size_start=5,
            size_end=0,
            color_start=(255, 230, 120, 255),
            color_end=(255, 120, 40, 0),
            gravity=pf.Vec2(0, 200),
        )
        emitter.burst(16, position)
        self.world.create_entity(pf.Transform(position=position), emitter)

    # -- loop -----------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if self.console.handle_event(event):
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.app.scenes.push(PauseScene())
            elif event.key == pygame.K_F1:
                self.overlay.toggle()
            elif event.key == pygame.K_BACKQUOTE:
                self.console.toggle()

    def variable_update(self, time: pf.GameTime) -> None:
        transform = self.world.require(self.player, pf.Transform)
        self.app.camera.follow(transform.interpolated(time.alpha), smoothing=0.15)
        if not self.finished:
            self._check_end(transform.position)

    def _check_end(self, player_pos: pf.Vec2) -> None:
        if player_pos.y > self.tilemap.world_size.y + 200:
            self.finished = True
            self.app.scenes.push(GameOverScene(won=False, score=self.score))
        elif self.coins_left <= 0 and player_pos.distance_to(self.flag_pos) < 40:
            self.finished = True
            self.app.audio.play_sound("win")
            self.app.scenes.push(GameOverScene(won=True, score=self.score))

    def draw(self, renderer: pf.Renderer) -> None:
        self.tilemap.draw(renderer)
        self.sprite_renderer.render(self.world, self.app.time)
        self.particle_renderer.render(self.world, renderer)
        self._draw_hud(renderer)
        self.console.draw(renderer)

    def _draw_hud(self, renderer: pf.Renderer) -> None:
        renderer.draw_text(
            self.font, f"Score {self.score}", pf.Vec2(16, 12), (255, 235, 150),
            layer=pf.Layer.UI, screen_space=True,
        )
        renderer.draw_text(
            self.font, f"Coins left {self.coins_left}", pf.Vec2(16, 44), (180, 220, 255),
            layer=pf.Layer.UI, screen_space=True,
        )
        renderer.draw_text(
            self.small_font, "Esc pause   F1 debug   ` console",
            pf.Vec2(renderer.size[0] - 16, 12), (160, 168, 190),
            anchor="topright", layer=pf.Layer.UI, screen_space=True,
        )

    def on_exit(self) -> None:
        for sub in self._subs:
            sub.unsubscribe()
        self.app.set_overlay(None)
        if self.app.audio.available:
            self.app.audio.stop_music(fade_ms=400)


class PauseScene(pf.Scene):
    transparent = True
    update_below = False  # freeze the game while paused

    def on_enter(self) -> None:
        viewport = self.app.camera.viewport
        font = self.app.assets.font(None, 32)
        self.ui = pf.UIRoot()
        panel = pf.Panel(pf.anchor(viewport, 320, 260, align="center"))
        self.ui.add(panel)
        panel.add(
            pf.Label(
                "Paused", font, pf.Vec2(panel.rect.center.x, panel.rect.top + 36),
                align="center",
            )
        )
        cx = panel.rect.center.x
        top = panel.rect.top + 80
        panel.add(pf.Button("Resume", font, pf.Rect(cx - 110, top, 220, 48), self._resume))
        panel.add(pf.Button("Menu", font, pf.Rect(cx - 110, top + 60, 220, 48), self._menu))
        panel.add(pf.Button("Quit", font, pf.Rect(cx - 110, top + 120, 220, 48), self.app.quit))

    def _resume(self) -> None:
        self.app.scenes.pop()

    def _menu(self) -> None:
        self.app.scenes.set_root(MenuScene())

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._resume()

    def variable_update(self, time: pf.GameTime) -> None:
        self.ui.update(self.app.input)

    def draw(self, renderer: pf.Renderer) -> None:
        size = renderer.size
        renderer.draw_rect(
            pf.Rect(0, 0, size[0], size[1]), (10, 12, 20, 150),
            layer=pf.Layer.UI, z=-10, screen_space=True,
        )
        self.ui.draw(renderer)


class GameOverScene(pf.Scene):
    transparent = True

    def __init__(self, *, won: bool, score: int) -> None:
        super().__init__()
        self.won = won
        self.score = score

    def on_enter(self) -> None:
        viewport = self.app.camera.viewport
        title_font = self.app.assets.font(None, 64)
        font = self.app.assets.font(None, 32)
        self.ui = pf.UIRoot()
        message = "You Win!" if self.won else "Game Over"
        color = (140, 230, 150) if self.won else (235, 120, 120)
        self.ui.add(
            pf.Label(message, title_font, pf.Vec2(viewport.x / 2, viewport.y * 0.32),
                     align="center", color=color)
        )
        self.ui.add(
            pf.Label(f"Score {self.score}", font, pf.Vec2(viewport.x / 2, viewport.y * 0.44),
                     align="center")
        )
        self.ui.add(
            pf.Button("Play again", font,
                      pf.anchor(viewport, 240, 56, align="center", offset=pf.Vec2(0, 20)),
                      self._again)
        )
        self.ui.add(
            pf.Button("Menu", font,
                      pf.anchor(viewport, 240, 56, align="center", offset=pf.Vec2(0, 90)),
                      self._menu)
        )

    def _again(self) -> None:
        self.app.scenes.set_root(GameScene())

    def _menu(self) -> None:
        self.app.scenes.set_root(MenuScene())

    def variable_update(self, time: pf.GameTime) -> None:
        self.ui.update(self.app.input)

    def draw(self, renderer: pf.Renderer) -> None:
        size = renderer.size
        renderer.draw_rect(
            pf.Rect(0, 0, size[0], size[1]), (8, 10, 16, 180),
            layer=pf.Layer.UI, z=-10, screen_space=True,
        )
        self.ui.draw(renderer)
