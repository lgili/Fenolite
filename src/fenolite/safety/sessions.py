# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Lock files that a CAD tool leaves beside a file it holds open (capability file-safety, "Open sessions and
placeholders").

Only tools whose lock-file pattern a public source records are detected (``PROVENANCE.md``): KiCad writes
``~<file name>.lck`` in the folder of the file it opens, and removes it on close (S-0828, S-0829). A lock
file left by a crash looks the same; the warning says so. Other tools are not detected.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

LOCK_PREFIX = "~"
LOCK_SUFFIX = ".lck"
TOOL = "KiCad"


@dataclass(frozen=True, slots=True)
class OpenSession:
    """A file and the lock file beside it."""

    path: Path
    lock: Path
    tool: str = TOOL


def lock_path(path: Path) -> Path:
    """Where KiCad's lock file of ``path`` lies."""
    return path.with_name(f"{LOCK_PREFIX}{path.name}{LOCK_SUFFIX}")


def open_sessions(paths: Iterable[Path]) -> tuple[OpenSession, ...]:
    """The files of ``paths`` that have a lock file beside them, in the order given, without repeats."""
    found: dict[Path, OpenSession] = {}
    for path in paths:
        lock = lock_path(path)
        if path not in found and lock.is_file():
            found[path] = OpenSession(path, lock)
    return tuple(found.values())


def lock_files(root: Path) -> tuple[OpenSession, ...]:
    """Every lock file under ``root`` with the file it names (which may be gone: a stale lock)."""
    found: list[OpenSession] = []
    for lock in sorted(root.rglob(f"{LOCK_PREFIX}*{LOCK_SUFFIX}")):
        if lock.is_file():
            name = lock.name[len(LOCK_PREFIX) : -len(LOCK_SUFFIX)]
            if name:
                found.append(OpenSession(lock.with_name(name), lock))
    return tuple(found)


__all__ = ["LOCK_PREFIX", "LOCK_SUFFIX", "OpenSession", "lock_files", "lock_path", "open_sessions"]
