"""Procedural assets for the demo so the repo ships with no binary files.

Everything the demo draws or plays is synthesised here at runtime: character
sprite-sheets, the tileset, the coin animation, sound effects and a short
looping music track (written to a WAV the AudioManager streams).
"""

from __future__ import annotations

import array
import math
import wave
from pathlib import Path

import pygame

TILE = 32


# -- helpers ------------------------------------------------------------------
def _surface(width: int, height: int) -> pygame.Surface:
    return pygame.Surface((width, height), pygame.SRCALPHA)


def _round_body(surface: pygame.Surface, color: tuple[int, int, int], bob: int) -> None:
    w, h = surface.get_size()
    body = pygame.Rect(4, 8 + bob, w - 8, h - 12 - bob)
    pygame.draw.rect(surface, color, body, border_radius=8)
    pygame.draw.rect(surface, (20, 24, 36), body, width=2, border_radius=8)
    # eyes
    eye_y = 16 + bob
    pygame.draw.circle(surface, (245, 245, 255), (w // 2 - 5, eye_y), 4)
    pygame.draw.circle(surface, (245, 245, 255), (w // 2 + 5, eye_y), 4)
    pygame.draw.circle(surface, (20, 20, 30), (w // 2 - 4, eye_y), 2)
    pygame.draw.circle(surface, (20, 20, 30), (w // 2 + 6, eye_y), 2)


# -- characters ---------------------------------------------------------------
def make_player_animations() -> dict[str, list[pygame.Surface]]:
    color = (90, 170, 240)
    idle: list[pygame.Surface] = []
    for bob in (0, 1):
        surf = _surface(32, 40)
        _round_body(surf, color, bob)
        idle.append(surf)

    run: list[pygame.Surface] = []
    for i in range(4):
        surf = _surface(32, 40)
        _round_body(surf, color, i % 2)
        # legs swinging
        phase = math.sin(i / 4 * math.tau)
        pygame.draw.line(surf, (30, 40, 60), (12, 34), (12 - int(phase * 4), 40), 4)
        pygame.draw.line(surf, (30, 40, 60), (20, 34), (20 + int(phase * 4), 40), 4)
        run.append(surf)

    jump = _surface(32, 40)
    _round_body(jump, (120, 200, 255), 0)
    return {"idle": idle, "run": run, "jump": [jump]}


def make_coin_animation() -> list[pygame.Surface]:
    frames: list[pygame.Surface] = []
    for i in range(8):
        surf = _surface(20, 20)
        width = max(2, int(abs(math.cos(i / 8 * math.tau)) * 16) + 2)
        rect = pygame.Rect(10 - width // 2, 2, width, 16)
        pygame.draw.ellipse(surf, (255, 205, 70), rect)
        pygame.draw.ellipse(surf, (180, 130, 20), rect, width=2)
        frames.append(surf)
    return frames


# -- tiles --------------------------------------------------------------------
def make_tileset() -> list[pygame.Surface]:
    grass = _surface(TILE, TILE)
    grass.fill((70, 50, 36))
    pygame.draw.rect(grass, (84, 160, 78), (0, 0, TILE, 8))
    pygame.draw.rect(grass, (54, 120, 58), (0, 6, TILE, 3))
    pygame.draw.rect(grass, (40, 30, 22), (0, 0, TILE, TILE), width=1)

    dirt = _surface(TILE, TILE)
    dirt.fill((70, 50, 36))
    for dx, dy in ((6, 8), (20, 14), (12, 24)):
        pygame.draw.circle(dirt, (58, 40, 28), (dx, dy), 3)
    pygame.draw.rect(dirt, (40, 30, 22), (0, 0, TILE, TILE), width=1)
    return [grass, dirt]


def make_flag() -> pygame.Surface:
    surf = _surface(TILE, TILE * 2)
    pygame.draw.rect(surf, (200, 200, 210), (4, 0, 3, TILE * 2))
    pygame.draw.polygon(surf, (235, 90, 90), [(7, 2), (26, 10), (7, 18)])
    return surf


# -- audio --------------------------------------------------------------------
def make_tone(
    frequencies: list[float], ms: int, *, volume: float = 0.35, sample_rate: int = 44100
) -> pygame.mixer.Sound:
    """Synthesise a short stereo tone (a chord of ``frequencies``) as a Sound."""
    n = int(sample_rate * ms / 1000)
    buf = array.array("h")
    amp = volume * 32767 / max(1, len(frequencies))
    for i in range(n):
        t = i / sample_rate
        env = min(1.0, i / (0.01 * n + 1)) * min(1.0, (n - i) / (0.25 * n + 1))
        sample = int(sum(math.sin(math.tau * f * t) for f in frequencies) * amp * env)
        buf.append(sample)
        buf.append(sample)
    return pygame.mixer.Sound(buffer=buf.tobytes())


def write_music(path: Path, *, sample_rate: int = 44100) -> None:
    """Write a short looping arpeggio to ``path`` as a 16-bit stereo WAV."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    notes = [220.0, 277.18, 329.63, 277.18, 246.94, 329.63, 392.0, 329.63]
    note_ms = 260
    buf = array.array("h")
    for note in notes:
        count = int(sample_rate * note_ms / 1000)
        for i in range(count):
            t = i / sample_rate
            env = min(1.0, (count - i) / (0.4 * count + 1))
            value = math.sin(math.tau * note * t) + 0.4 * math.sin(math.tau * note * 2 * t)
            sample = int(value * 0.18 * 32767 * env)
            buf.append(sample)
            buf.append(sample)
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(buf.tobytes())
