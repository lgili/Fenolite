# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Truncated input never crashes the reader (capability altium-schematic-reader, "Truncated input never
crashes")."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from fenolite.backends.altium.read import sch
from fenolite.backends.altium.read.schlib import read_schlib
from fenolite.core.errors import FormatError

ROOT = Path(__file__).resolve().parents[5]
BLINK = ROOT / "tests" / "data" / "altium" / "blink"
CUTS = 257


def _lengths(size: int) -> list[int]:
    return sorted({size * index // (CUTS - 1) for index in range(CUTS)})


READERS: list[tuple[str, Callable[[bytes], object]]] = [
    ("blink.SchDoc", sch.read_schematic),
    ("blink.SchLib", read_schlib),
]


@pytest.mark.parametrize(("name", "reader"), READERS, ids=[name for name, _ in READERS])
def test_truncated_input_never_crashes(name: str, reader: Callable[[bytes], object]) -> None:
    data = (BLINK / name).read_bytes()
    lengths = _lengths(len(data))
    assert len(lengths) == CUTS
    outcomes = {"result": 0, "error": 0}
    for length in lengths:
        try:
            reader(data[:length])
            outcomes["result"] += 1
        except FormatError:
            outcomes["error"] += 1
    assert outcomes["result"] >= 1 and outcomes["error"] >= 1


@pytest.mark.parametrize(("name", "reader"), READERS, ids=[name for name, _ in READERS])
def test_flipped_bytes_never_crash(name: str, reader: Callable[[bytes], object]) -> None:
    data = bytearray((BLINK / name).read_bytes())
    for position in range(0, len(data), max(1, len(data) // 300)):
        changed = bytearray(data)
        changed[position] ^= 0xFF
        try:
            reader(bytes(changed))
        except FormatError:
            pass
