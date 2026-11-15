"""Asset loading and caching.

All paths are resolved relative to a project ``assets`` root. Loaders are
memoised so the same texture/font/sound is only decoded once. In ``dev_mode``,
:meth:`hot_reload` re-decodes any texture whose file changed on disk, so you can
tweak art without restarting the game.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pygame

__all__ = ["AssetManager"]


class AssetManager:
    def __init__(self, root: str | Path, *, dev_mode: bool = False) -> None:
        self.root = Path(root)
        self.dev_mode = dev_mode
        self._textures: dict[str, pygame.Surface] = {}
        self._fonts: dict[tuple[str, int], pygame.font.Font] = {}
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._mtimes: dict[str, float] = {}

    def resolve(self, name: str) -> Path:
        path = Path(name)
        return path if path.is_absolute() else self.root / path

    # -- textures -------------------------------------------------------------
    def texture(self, name: str) -> pygame.Surface:
        cached = self._textures.get(name)
        if cached is not None:
            return cached
        surface = self._load_surface(self.resolve(name))
        self._textures[name] = surface
        return surface

    def _load_surface(self, path: Path) -> pygame.Surface:
        surface = pygame.image.load(str(path))
        # convert_alpha needs a display; fall back gracefully when headless.
        if pygame.display.get_surface() is not None:
            surface = surface.convert_alpha()
        self._mtimes[str(path)] = path.stat().st_mtime
        return surface

    def register_surface(self, name: str, surface: pygame.Surface) -> pygame.Surface:
        """Cache a surface created at runtime (e.g. procedurally) under ``name``."""
        self._textures[name] = surface
        return surface

    # -- fonts ----------------------------------------------------------------
    def font(self, name: str | None, size: int) -> pygame.font.Font:
        key = (name or "", size)
        cached = self._fonts.get(key)
        if cached is not None:
            return cached
        if name is None:
            font = pygame.font.Font(None, size)
        else:
            font = pygame.font.Font(str(self.resolve(name)), size)
        self._fonts[key] = font
        return font

    # -- audio ----------------------------------------------------------------
    def sound(self, name: str) -> pygame.mixer.Sound:
        cached = self._sounds.get(name)
        if cached is not None:
            return cached
        sound = pygame.mixer.Sound(str(self.resolve(name)))
        self._sounds[name] = sound
        return sound

    def register_sound(self, name: str, sound: pygame.mixer.Sound) -> pygame.mixer.Sound:
        self._sounds[name] = sound
        return sound

    # -- data -----------------------------------------------------------------
    def load_json(self, name: str) -> Any:
        with self.resolve(name).open(encoding="utf-8") as handle:
            return json.load(handle)

    # -- dev-mode hot reload --------------------------------------------------
    def hot_reload(self) -> list[str]:
        """Re-decode textures whose files changed. Returns reloaded names."""
        if not self.dev_mode:
            return []
        reloaded: list[str] = []
        for name in list(self._textures):
            path = self.resolve(name)
            if not path.exists():
                continue
            mtime = path.stat().st_mtime
            if self._mtimes.get(str(path), mtime) != mtime:
                self._textures[name] = self._load_surface(path)
                reloaded.append(name)
        return reloaded

    def clear(self) -> None:
        self._textures.clear()
        self._fonts.clear()
        self._sounds.clear()
        self._mtimes.clear()
