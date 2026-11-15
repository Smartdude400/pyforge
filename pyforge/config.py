"""Settings persistence and a simple save-slot API.

Settings are stored as JSON (human-editable, dependency-free). Existing TOML
config files can also be *read* via the stdlib ``tomllib``. Saves are JSON blobs
written to individual slot files under a saves directory.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

__all__ = ["SaveManager", "Settings"]


class Settings:
    """A flat-or-nested dict of JSON-serialisable settings with dotted access."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = data or {}

    def get(self, key: str, default: Any = None) -> Any:
        node: Any = self._data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, key: str, value: Any) -> None:
        parts = key.split(".")
        node = self._data
        for part in parts[:-1]:
            child = node.get(part)
            if not isinstance(child, dict):
                child = {}
                node[part] = child
            node = child
        node[parts[-1]] = value

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    # -- persistence ----------------------------------------------------------
    @classmethod
    def load(cls, path: str | Path) -> Settings:
        p = Path(path)
        if not p.exists():
            return cls()
        if p.suffix == ".toml":
            with p.open("rb") as handle:
                return cls(dict(tomllib.load(handle)))
        with p.open(encoding="utf-8") as handle:
            return cls(json.load(handle))

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as handle:
            json.dump(self._data, handle, indent=2, sort_keys=True)


class SaveManager:
    """Reads/writes named save slots as JSON files in a directory."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def _slot_path(self, slot: str) -> Path:
        safe = "".join(c for c in slot if c.isalnum() or c in ("-", "_"))
        return self.directory / f"{safe or 'save'}.json"

    def save(self, slot: str, data: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        with self._slot_path(slot).open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)

    def load(self, slot: str) -> dict[str, Any] | None:
        path = self._slot_path(slot)
        if not path.exists():
            return None
        with path.open(encoding="utf-8") as handle:
            result: dict[str, Any] = json.load(handle)
            return result

    def exists(self, slot: str) -> bool:
        return self._slot_path(slot).exists()

    def delete(self, slot: str) -> None:
        self._slot_path(slot).unlink(missing_ok=True)

    def list_slots(self) -> list[str]:
        if not self.directory.exists():
            return []
        return sorted(p.stem for p in self.directory.glob("*.json"))
