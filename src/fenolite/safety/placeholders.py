# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Files that a sync client keeps only online (capability file-safety, "Open sessions and placeholders").

Such a file is recognised by the attributes its operating system documents, never by reading it, because a
read makes the client fetch it (and may block):

- on Windows, ``st_file_attributes`` holds ``FILE_ATTRIBUTE_OFFLINE`` (0x1000),
  ``FILE_ATTRIBUTE_RECALL_ON_OPEN`` (0x40000) or ``FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS`` (0x400000)
  (S-0830, S-0831);
- on macOS, ``st_flags`` holds ``SF_DATALESS`` (0x40000000; ``stat.SF_DATALESS`` from Python 3.13) (S-0831).

Elsewhere no attribute is documented, and no file is online-only.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

FILE_ATTRIBUTE_OFFLINE = 0x1000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x40000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000
WINDOWS_ONLINE_ONLY = (
    FILE_ATTRIBUTE_OFFLINE | FILE_ATTRIBUTE_RECALL_ON_OPEN | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
)
SF_DATALESS: int = getattr(stat, "SF_DATALESS", 0x40000000)


class _Stat(Protocol):
    @property
    def st_mode(self) -> int: ...


def is_online_only(info: _Stat) -> bool:
    """Whether a ``stat`` result describes a file kept only online."""
    attributes = getattr(info, "st_file_attributes", 0) or 0
    flags = getattr(info, "st_flags", 0) or 0
    return bool(attributes & WINDOWS_ONLINE_ONLY) or bool(flags & SF_DATALESS)


def online_only(paths: Iterable[Path]) -> tuple[Path, ...]:
    """The files of ``paths`` kept only online, in the order given; a path that cannot be read is skipped."""
    found: list[Path] = []
    for path in paths:
        try:
            info = os.stat(path, follow_symlinks=True)
        except OSError:
            continue
        if is_online_only(info):
            found.append(path)
    return tuple(found)


__all__ = [
    "FILE_ATTRIBUTE_OFFLINE",
    "FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS",
    "FILE_ATTRIBUTE_RECALL_ON_OPEN",
    "SF_DATALESS",
    "WINDOWS_ONLINE_ONLY",
    "is_online_only",
    "online_only",
]
