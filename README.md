# PyForge

A modular, **fixed-timestep 2D game engine** for Python, built on
[pygame-ce](https://pyga.me/). PyForge gives you an Entity-Component-System
core, a scene stack, a layered renderer with a 2D camera, rebindable input
(keyboard / mouse / gamepad), a small physics solver, particles, audio,
UI widgets, save/settings persistence, and debug tooling — all behind a clean,
fully type-hinted API.

```python
import pygame
import pyforge as pf

class HelloScene(pf.Scene):
    def on_enter(self) -> None:
        surface = pygame.Surface((40, 40))  # or load via self.app.assets
        surface.fill((120, 200, 255))
        self.world.create_entity(
            pf.Transform(position=pf.Vec2(640, 360)),
            pf.Sprite(surface=surface),
        )
        self.renderer = pf.SpriteRenderSystem(self.app.renderer)

    def draw(self, renderer: pf.Renderer) -> None:
        self.renderer.render(self.world, self.app.time)

pf.App(pf.AppConfig(title="Hello PyForge")).run(HelloScene())
```

---

## Install

Requires **Python 3.11+**.

```bash
# from the project root
pip install -e .            # installs pyforge + pygame-ce
pip install -e ".[dev]"     # also installs pytest, mypy, ruff
```

## Run the demo

A complete little platformer that exercises **every** subsystem — menu → game →
pause → game-over, sprite animation, tilemap, camera follow, AABB + trigger
physics, particles, procedural SFX/music, a HUD, a debug overlay and an in-game
console. All art and audio are generated procedurally, so there are no binary
assets in the repo.

```bash
python -m examples.demo
```

Controls: **A/D** or **←/→** to move, **Space / W / ↑** to jump (gamepad
supported), **Esc** to pause, **F1** for the debug overlay, **`** for the
console (try `give 100` or `tp 200 100`).

---

## Architecture

PyForge is layered: a framework-agnostic core (math, ECS, events, scenes,
timing) with pygame-backed subsystems composed on top. The `App` is the single
explicit context object — it owns every service and injects itself into scenes,
so there are no hidden global singletons.

```
        ┌────────────────────────────── App (fixed-timestep loop) ──────────────────────────────┐
        │  assets · audio · input · events · camera · renderer · scenes · time · stats           │
        └───────────────────────────────────────────────────────────────────────────────────────┘
                 │
   SceneManager (stack: push/pop/replace)
                 │
        Scene ── owns ──▶ World (ECS)
                              │  entities + components (dataclasses)
                              ▼
        Systems run in priority order each fixed step:
          PlayerController(-10) ▸ Animation(-50) ▸ Particles(50) ▸ Physics(100)
```

### The game loop (determinism)

The loop uses an **accumulator**: simulation advances in fixed 60 Hz steps
independent of render framerate, and rendering receives an interpolation
`alpha` to smooth motion between ticks. Gameplay never depends on FPS. A
`max_frame_time` clamp prevents the "spiral of death" after a stall.

### Subsystem map

| Subsystem | Module | Highlights |
|---|---|---|
| Core loop & time | `app.py`, `clock.py` | accumulator, interpolation, pause/timescale, FPS stats |
| ECS | `ecs.py` | typed `query()` overloads, smallest-pool iteration, deferred structural edits |
| Scenes | `scene.py` | stack manager, per-scene worlds, transparent overlays, `update_below` |
| Rendering | `render.py`, `camera.py` | layer/z-ordered command buffer, world↔screen camera, zoom/follow/bounds |
| Sprites & animation | `components.py`, `animation.py` | sprite sheets, frame clips, interpolated rendering |
| Tilemaps | `tilemap.py` | culled drawing, greedy-merged static colliders |
| Input | `input.py` | action mapping, analog axes, pressed/held/released, binding persistence |
| Assets | `assets.py` | cached textures/fonts/sounds, dev-mode hot-reload |
| Physics | `physics.py` | AABB + circle, spatial-hash broad phase, impulse resolution, collision events |
| Particles | `particles.py` | pooled emitters, color/size-over-life |
| Audio | `audio.py` | master/sfx/music buses, music fades |
| UI | `ui.py` | panels, labels, buttons, anchored layout |
| Events | `events.py` | typed pub/sub, safe mutation during dispatch |
| Save / config | `config.py` | JSON settings (dotted keys), TOML read, save slots |
| Debug | `debug.py` | overlay (FPS/entities/colliders), logging, console |

### Key design trade-offs

- **Sparse-set ECS, not archetypes.** Storage is `dict[type, dict[Entity, Component]]`.
  In Python, attribute access dominates the cost anyway, so we trade archetype
  cache locality for trivially cheap add/remove and simpler code. Queries drive
  iteration from the smallest matching pool.
- **Snapshot queries + deferred removals.** `query()` returns a materialised
  list and entity destruction / component removal are queued and flushed between
  systems, so a system never sees an entity half-destroyed.
- **Command-buffer renderer.** Draw calls are submitted in any order and flushed
  sorted by `(layer, z, submission order)`, decoupling submission from draw
  order for sprites, tilemaps, particles and UI sharing a frame.
- **Small, swappable physics.** Enough for platformers/top-down games; designed
  so a heavier solver could replace `PhysicsSystem` without touching gameplay.

---

## Quality gates

```bash
python -m pytest        # 32 tests: math, ecs, events, scenes, input, physics, demo smoke
python -m mypy pyforge  # passes under --strict
python -m ruff check .  # lint clean
```

Tests run fully headless (SDL dummy drivers, configured in `tests/conftest.py`),
so they need no window or sound card.

## Project layout

```
pyforge/            the engine package (one module per subsystem)
examples/demo/      the playable demo (procedural assets, four scenes)
tests/              headless unit + integration tests
pyproject.toml      packaging, pytest/ruff/mypy config
```

## License

MIT.
