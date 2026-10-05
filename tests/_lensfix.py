# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The edits of the lens acceptance fixture (change c0069; ``tests/data/lens/acceptance/design.py``), shared
by the hermetic test and the KiCad oracle.

``edit_board`` stands for the work done in KiCad: five footprints moved by distinct offsets, three tracks
from pad to pad with version-4 uuids, one ``Reference`` property moved, and a group of two footprints.
``edit_script`` adds the part ``R9`` to ``io`` and renames the module ``power`` to ``supply`` with
``moved()``. The offsets are round numbers chosen for the test.
"""

from __future__ import annotations

from _layout_edit import (
    MM,
    add_group,
    add_items,
    mm,
    move_footprint,
    move_property,
    net_ref,
    pad_position,
)

FOLDER = "tests/data/lens/acceptance"
NAME = "lensfix"
MOVES: dict[str, tuple[int, int]] = {
    "R1": (1 * MM, 0),
    "R2": (2 * MM, 0),
    "D1": (0, 1_500_000),
    "D2": (500_000, 0),
    "R5": (-1 * MM, 1 * MM),
}
"""Reference → the offset its footprint is moved by; ``R1``, ``R2`` and ``D1`` are in ``power``."""
PATHS: dict[str, str] = {
    "U1": "U1",
    "R1": "power/R1",
    "R2": "power/R2",
    "R3": "power/R3",
    "D1": "power/D1",
    "R4": "io/R4",
    "D2": "io/D2",
    "R5": "io/R5",
}
"""Reference → component path before the rename."""
TRACKS: tuple[tuple[str, str, tuple[str, str], tuple[str, str]], ...] = (
    ("00000000-0000-4000-8000-0000000c6901", "power/FB", ("R1", "2"), ("R2", "1")),
    ("00000000-0000-4000-8000-0000000c6902", "io/LED_A", ("R4", "2"), ("D2", "1")),
    ("00000000-0000-4000-8000-0000000c6903", "VIN", ("R1", "1"), ("R3", "1")),
)
"""``(uuid, net, (ref, pad), (ref, pad))`` of the three tracks: a module net of ``power``, one of ``io`` and
a top-level net."""
GROUP = "00000000-0000-4000-8000-0000000c69f1"
GROUPED = ("R1", "R2")
FIELD_REF = "R3"
"""The ``power`` footprint whose ``Reference`` property is moved 1 mm."""
ADD_R9 = 'r9 = Part("R9", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="1k")\nio.add(r9)\n'
ALIAS = 'design.moved("power", "supply")\n'


def renamed(path: str) -> str:
    """The component path or net name after ``power`` is renamed ``supply``."""
    return "supply" + path[len("power") :] if path.startswith("power/") else path


def edit_board(text: str) -> str:
    """The built board with the edits that stand for work in KiCad."""
    for ref, (dx, dy) in MOVES.items():
        text = move_footprint(text, ref, dx, dy)
    items: list[str] = []
    for uuid, net, (ref_a, pad_a), (ref_b, pad_b) in TRACKS:
        start, end = pad_position(text, ref_a, pad_a), pad_position(text, ref_b, pad_b)
        items.append(
            f"(segment (start {mm(start.x)} {mm(start.y)}) (end {mm(end.x)} {mm(end.y)}) (width 0.25) "
            f'(layer "F.Cu") {net_ref(text, net)} (uuid "{uuid}"))'
        )
    text = add_items(text, *items)
    text = move_property(text, FIELD_REF, "Reference", 0, MM)
    return add_group(text, GROUP, *GROUPED, name="pair")


def edit_script(text: str) -> str:
    """The script with ``R9`` added to ``io`` and ``power`` renamed ``supply`` through ``moved()``."""
    for old, new in (
        ('power = Module("power")\n', 'power = Module("supply")\n' + ALIAS),
        ("io.add(r4, d2, r5)\n", "io.add(r4, d2, r5)\n" + ADD_R9),
    ):
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    return text


def drop_alias(text: str) -> str:
    assert text.count(ALIAS) == 1
    return text.replace(ALIAS, "")


__all__ = [
    "FIELD_REF",
    "FOLDER",
    "GROUP",
    "GROUPED",
    "MOVES",
    "NAME",
    "PATHS",
    "TRACKS",
    "drop_alias",
    "edit_board",
    "edit_script",
    "renamed",
]
