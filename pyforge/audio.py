"""Audio playback with master/sfx/music volume buses.

Effects are played through cached :class:`pygame.mixer.Sound` objects; music is
streamed via :mod:`pygame.mixer.music`. All effective volumes are the product
of the bus volume and the master volume, so a single master slider works.
"""

from __future__ import annotations

import pygame

from .assets import AssetManager
from .math import clamp

__all__ = ["AudioManager"]


class AudioManager:
    def __init__(self, assets: AssetManager) -> None:
        self._assets = assets
        self._master = 1.0
        self._sfx = 1.0
        self._music = 1.0
        self._current_music: str | None = None

    @property
    def available(self) -> bool:
        """False when the mixer failed to initialise (e.g. no audio device)."""
        return pygame.mixer.get_init() is not None

    # -- volume buses ---------------------------------------------------------
    @property
    def master_volume(self) -> float:
        return self._master

    @master_volume.setter
    def master_volume(self, value: float) -> None:
        self._master = clamp(value, 0.0, 1.0)
        self._apply_music_volume()

    @property
    def sfx_volume(self) -> float:
        return self._sfx

    @sfx_volume.setter
    def sfx_volume(self, value: float) -> None:
        self._sfx = clamp(value, 0.0, 1.0)

    @property
    def music_volume(self) -> float:
        return self._music

    @music_volume.setter
    def music_volume(self, value: float) -> None:
        self._music = clamp(value, 0.0, 1.0)
        self._apply_music_volume()

    # -- sound effects --------------------------------------------------------
    def play_sound(
        self, name: str, *, volume: float = 1.0, loops: int = 0
    ) -> pygame.mixer.Channel | None:
        """Play a cached sound effect through the sfx bus."""
        if not self.available:
            return None
        sound = self._assets.sound(name)
        sound.set_volume(clamp(volume, 0.0, 1.0) * self._sfx * self._master)
        return sound.play(loops=loops)

    # -- music ----------------------------------------------------------------
    def play_music(self, name: str, *, loops: int = -1, fade_ms: int = 0) -> None:
        if not self.available:
            return
        pygame.mixer.music.load(str(self._assets.resolve(name)))
        self._current_music = name
        self._apply_music_volume()
        pygame.mixer.music.play(loops=loops, fade_ms=fade_ms)

    def stop_music(self, *, fade_ms: int = 0) -> None:
        if not self.available:
            return
        if fade_ms > 0:
            pygame.mixer.music.fadeout(fade_ms)
        else:
            pygame.mixer.music.stop()
        self._current_music = None

    def pause_music(self) -> None:
        if self.available:
            pygame.mixer.music.pause()

    def resume_music(self) -> None:
        if self.available:
            pygame.mixer.music.unpause()

    @property
    def current_music(self) -> str | None:
        return self._current_music

    def _apply_music_volume(self) -> None:
        if self.available:
            pygame.mixer.music.set_volume(self._music * self._master)
