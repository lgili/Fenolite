# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Atomic file writes with backups, and SHA-256 helpers.

No file is ever modified in place: data goes to a temporary file in the target directory, which
is then renamed over the target. When the target existed and ``backup`` is true, its previous
content is kept next to it as ``<name>.bak``.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

_CHUNK = 1 << 20


@dataclass(frozen=True, slots=True)
class WriteReceipt:
    """What :func:`atomic_write` wrote."""

    path: Path
    sha256: str
    backup_path: Path | None


def sha256_bytes(data: bytes) -> str:
    """Hex SHA-256 of ``data``."""
    return hashlib.sha256(data).hexdigest()


def sha256_of(path: str | os.PathLike[str]) -> str:
    """Hex SHA-256 of the file at ``path``, read in chunks."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _default_mode() -> int:
    umask = os.umask(0)
    os.umask(umask)
    return 0o666 & ~umask


def atomic_write(path: str | os.PathLike[str], data: bytes, *, backup: bool = True) -> WriteReceipt:
    """Write ``data`` to ``path`` atomically and return a receipt.

    Parent directories are created. If ``path`` exists and ``backup`` is true, its previous content
    is copied to ``<path>.bak`` before the rename. On any failure the target is left untouched and
    the temporary file is removed.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    tmp = Path(tmp_name)
    backup_path: Path | None = None
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if target.exists():
            shutil.copymode(target, tmp)
            if backup:
                backup_path = target.with_name(target.name + ".bak")
                shutil.copy2(target, backup_path)
        else:
            os.chmod(tmp, _default_mode())
        os.replace(tmp, target)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        raise
    return WriteReceipt(path=target, sha256=sha256_bytes(data), backup_path=backup_path)


__all__ = ["WriteReceipt", "atomic_write", "sha256_bytes", "sha256_of"]
