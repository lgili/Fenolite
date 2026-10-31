# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The offline cache of library releases (change c0279, ``docs/library-repo.md``, "Offline cache").

``<library dir>`` is ``FENOLITE_LIBRARY_DIR`` (absolute), else ``$XDG_CACHE_HOME/fenolite/library``, the
macOS or Windows cache folder, or ``~/.cache/fenolite/library`` (the rules of ``fenolite.core.tools``). It
holds ``<version>/index.json``, ``<version>/assets/<asset>`` and a stamp ``<version>/.fenolite-library.toml``
listing the verified digests. Only ``fenolite get --confirm`` writes it; this module names paths and reads
files, checking each digest before a byte is used.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from fenolite.library.items import VERSION, version_key

LIBRARY_ENV = "FENOLITE_LIBRARY_DIR"
INDEX = "index.json"
ASSETS = "assets"
STAMP = ".fenolite-library.toml"


def library_dir() -> Path:
    """The cache folder; a relative ``FENOLITE_LIBRARY_DIR`` raises ``ValueError``."""
    explicit = os.environ.get(LIBRARY_ENV, "")
    if explicit:
        folder = Path(explicit).expanduser()
        if not folder.is_absolute():
            raise ValueError(f"{LIBRARY_ENV} must be an absolute path, not {explicit!r}")
        return folder
    cache = os.environ.get("XDG_CACHE_HOME", "")
    if cache:
        return Path(cache) / "fenolite" / "library"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "fenolite" / "library"
    local = os.environ.get("LOCALAPPDATA", "")
    if sys.platform == "win32" and local:
        return Path(local) / "fenolite" / "library"
    return Path.home() / ".cache" / "fenolite" / "library"


def index_path(version: str) -> Path:
    return library_dir() / version / INDEX


def asset_path(version: str, asset: str) -> Path:
    return library_dir() / version / ASSETS / asset


def stamp_path(version: str) -> Path:
    return library_dir() / version / STAMP


def read_verified(path: Path, sha256: str | None, size: int | None = None) -> bytes | None:
    """The bytes at ``path`` when they have ``sha256`` (and ``size``), else ``None``; a missing file is
    ``None``. With ``sha256`` ``None`` the bytes are returned as they are."""
    try:
        if size is not None and path.stat().st_size != size:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if sha256 is not None and hashlib.sha256(data).hexdigest() != sha256:
        return None
    return data


def cached_versions() -> list[str]:
    """The versions with a cached index, oldest first."""
    try:
        folder = library_dir()
        names = [p.name for p in folder.iterdir() if (p / INDEX).is_file() and VERSION.fullmatch(p.name)]
    except (OSError, ValueError):
        return []
    return sorted(names, key=version_key)


def read_stamp(version: str) -> dict[str, str]:
    """The verified digests the stamp of ``version`` lists (asset → SHA-256)."""
    try:
        data = tomllib.loads(stamp_path(version).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    table = data.get("verified", {})
    if not isinstance(table, dict):
        return {}
    return {str(k): str(v) for k, v in cast(dict[str, object], table).items()}


def stamp_text(version: str, digests: Mapping[str, str]) -> bytes:
    lines = [
        "# Written by fenolite get: the assets of this release that were checked against their digests.",
        'schema = "fenolite.library-cache.v0"',
        f'version = "{version}"',
        "",
        "[verified]",
        *(f'"{name}" = "{digest}"' for name, digest in sorted(digests.items())),
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


__all__ = [
    "ASSETS",
    "INDEX",
    "LIBRARY_ENV",
    "STAMP",
    "asset_path",
    "cached_versions",
    "index_path",
    "library_dir",
    "read_stamp",
    "read_verified",
    "stamp_path",
    "stamp_text",
]
