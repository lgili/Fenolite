# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Keys of imported items and the lock of an import (change c0275, design decisions 5 to 7).

Keys come from names, paths and sorted coordinates only. A net name becomes one key segment by an
injective escape into the key alphabet ``[A-Za-z0-9_.+-]``: ``_`` and every other character outside it are
written as ``_`` and four hex digits (``_U`` and six beyond the basic plane).
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from fenolite.dsl.lock import lock_text, make_lock

_KEEP = re.compile(r"[A-Za-z0-9.+-]")


def segment(name: str) -> str:
    """``name`` as one key segment; distinct names give distinct segments, and ``""`` gives ``_``."""
    if not name:
        return "_"
    out: list[str] = []
    for char in name:
        if _KEEP.fullmatch(char):
            out.append(char)
        elif ord(char) <= 0xFFFF:
            out.append(f"_{ord(char):04x}")
        else:
            out.append(f"_U{ord(char):06x}")
    return "".join(out)


def lock_of(design: str, refs: Mapping[str, str]) -> str:
    """The text of ``design.lock`` recording every part key (component path) and its ref (c0249)."""
    return lock_text(make_lock(design, {"refs": dict(sorted(refs.items()))}))


__all__ = ["lock_of", "segment"]
