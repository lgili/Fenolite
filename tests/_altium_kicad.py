# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Shared parts of the two ``kicad-cli`` oracles of the Altium PCB reader (change c0041): KiCad's length
conversion and the matching of compared items within the tolerance."""

from __future__ import annotations

import math
from collections.abc import Sequence
from fractions import Fraction
from typing import Any

TOLERANCE = 2
SLOT = 2
"""Hole shape 2 of a pad's sixth subrecord: a slot, whose size is not compared."""
PASTE_LAYERS = (35, 36)
"""Top Paste and Bottom Paste: KiCad imports no pad of these layers."""

Item = tuple[Any, ...]
"""A compared item: integer coordinates first (``coords`` of them), then exact fields."""


def match(mine: Sequence[Item], theirs: Sequence[Item], coords: int) -> tuple[list[Item], list[Item], int]:
    """Pair items whose first ``coords`` values differ by at most :data:`TOLERANCE` each and whose other
    values are equal: the unmatched items of each side and the largest difference of a pair."""
    buckets: dict[tuple[int, int], list[int]] = {}
    for index, item in enumerate(theirs):
        buckets.setdefault((item[0] // 1000, item[1] // 1000), []).append(index)
    used: set[int] = set()
    lonely: list[Item] = []
    worst = 0
    for item in mine:
        bx, by = item[0] // 1000, item[1] // 1000
        found = None
        for key in ((bx + i, by + j) for i in (-1, 0, 1) for j in (-1, 0, 1)):
            for index in buckets.get(key, ()):
                other = theirs[index]
                if index in used or other[coords:] != item[coords:]:
                    continue
                gap = max(abs(a - b) for a, b in zip(item[:coords], other[:coords], strict=True))
                if gap <= TOLERANCE:
                    found = index
                    worst = max(worst, gap)
                    break
            if found is not None:
                break
        if found is None:
            lonely.append(item)
        else:
            used.add(found)
    return lonely, [t for i, t in enumerate(theirs) if i not in used], worst


def _away(value: Fraction) -> int:
    whole = math.floor(abs(value) + Fraction(1, 2))
    return whole if value >= 0 else -whole


def kicad_nm(units: int) -> int:
    """A length as KiCad's importer converts it (``pcb-read.md``, "What KiCad does not import"; S-0163):
    ``units · 2.54`` rounded to the nanometre, then to the nearest 10 nm, ties away from zero."""
    return _away(Fraction(_away(Fraction(units * 127, 50)), 10)) * 10
