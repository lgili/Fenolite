# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The scene cache of the viewer (capability viewer-performance, change c0182).

A scene is cached under a key made of the SHA-256 of its input (the file, or every file of a library folder),
the theme it was drawn in, and a digest of Fenolite's own code (every module and the page, so that a scene is
never served by another build of Fenolite, a development build included). An entry is one gzipped JSON file,
written atomically; an entry that cannot be read is deleted and rebuilt. The cache holds scenes only, never a
file's bytes, and is safe to delete.

Where: ``user`` (the default) is the user's cache folder (``FENOLITE_CACHE_DIR``, else ``$XDG_CACHE_HOME``,
``%LOCALAPPDATA%`` or ``~/.cache``, then ``fenolite/view``); ``project`` is ``.fenolite/view-cache`` of the
project folder; ``off`` caches nothing.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any, Literal, cast

import fenolite

Where = Literal["user", "project", "off"]
WHERE: tuple[Where, ...] = ("user", "project", "off")
PROJECT_FOLDER = Path(".fenolite") / "view-cache"


@cache
def code_digest() -> str:
    """The SHA-256 of Fenolite's modules and page, in path order (computed once per process)."""
    root = Path(fenolite.__file__).parent
    digest = hashlib.sha256(fenolite.__version__.encode())
    for path in sorted(root.rglob("*")):
        if path.suffix in (".py", ".html") and path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def input_digest(path: Path) -> str:
    """The SHA-256 of a file, or of every file of a folder with its relative path."""
    digest = hashlib.sha256()
    if path.is_dir():
        for item in sorted(p for p in path.rglob("*") if p.is_file()):
            digest.update(item.relative_to(path).as_posix().encode() + b"\0")
            digest.update(hashlib.sha256(item.read_bytes()).digest())
    else:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def user_folder() -> Path:
    given = os.environ.get("FENOLITE_CACHE_DIR")
    if given:
        return Path(given) / "view"
    base = os.environ.get("XDG_CACHE_HOME") or os.environ.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home() / ".cache") / "fenolite" / "view"


class SceneCache:
    """Scenes by input, theme and code; ``folder`` ``None`` caches nothing. ``hits`` and ``misses`` count the
    lookups of this object."""

    def __init__(self, folder: Path | None) -> None:
        self.folder = folder
        self.hits = 0
        self.misses = 0

    @classmethod
    def at(cls, where: Where, project: Path) -> SceneCache:
        if where == "off":
            return cls(None)
        return cls(user_folder() if where == "user" else project / PROJECT_FOLDER)

    def key(self, path: Path, theme: str) -> str:
        parts = (code_digest(), theme, input_digest(path))
        return hashlib.sha256("\n".join(parts).encode()).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        if self.folder is None:
            return None
        entry = self.folder / f"{key}.json.gz"
        try:
            value: Any = json.loads(gzip.decompress(entry.read_bytes()))
        except FileNotFoundError:
            self.misses += 1
            return None
        except (OSError, ValueError, EOFError):
            entry.unlink(missing_ok=True)
            self.misses += 1
            return None
        if not isinstance(value, dict):
            entry.unlink(missing_ok=True)
            self.misses += 1
            return None
        self.hits += 1
        return cast("dict[str, Any]", value)

    def put(self, key: str, scene: dict[str, Any]) -> None:
        if self.folder is None:
            return
        data = gzip.compress(json.dumps(scene, separators=(",", ":")).encode("utf-8"), mtime=0)
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            handle, temp = tempfile.mkstemp(dir=self.folder, suffix=".tmp")
            with os.fdopen(handle, "wb") as out:
                out.write(data)
            os.replace(temp, self.folder / f"{key}.json.gz")
        except OSError:
            return  # a cache that cannot be written only costs time

    def scene(self, path: Path, theme: str, build: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        """The cached scene of ``path`` in ``theme``, else ``build()``, stored."""
        if self.folder is None:
            return build()
        key = self.key(path, theme)
        found = self.get(key)
        if found is not None:
            return found
        built = build()
        self.put(key, built)
        return built


__all__ = ["WHERE", "SceneCache", "Where", "code_digest", "input_digest", "user_folder"]
