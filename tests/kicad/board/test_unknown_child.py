# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An unknown child survives a write (capability kicad-oracle "Written boards keep read content" and
kicad-slots "Opaque child unchanged on a same-target write"; change c0017).

``dimension.kicad_pcb`` (authored, header ``20241229``) holds one ``dimension`` between two segments,
which the reader keeps opaque. One segment is moved in the model and the board is written for 9 and
for 10: the ``dimension`` comes back tree-equal, at its source index for target 9 and between the same
neighbours for target 10 (whose root has no net table), and each text loads on its major.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _boards import mm
from _probes import DIMENSION, major, run

from fenolite.backends.kicad.pcb import opaque_count, read_board, write_board
from fenolite.backends.kicad.sexpr import Node, load, parse
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_kicad


def moved() -> Design:
    design = read_board(DIMENSION)
    assert design.board is not None
    return design.replace_entity(dataclasses.replace(design.board.tracks[0], start=mm(6, 10)))


def neighbours(root: Node) -> tuple[Node | None, Node, Node | None]:
    nodes = [c for c in root.children if isinstance(c, Node)]
    i = next(k for k, c in enumerate(nodes) if c.name == "dimension")
    return nodes[i - 1], nodes[i], nodes[i + 1] if i + 1 < len(nodes) else None


@pytest.mark.parametrize("target", [9, 10])
def test_unknown_child_survives_a_write(target: int) -> None:
    if target > major():
        pytest.skip(f"KiCad {major()} does not load target {target}")
    source = load(DIMENSION)
    design = moved()
    text = write_board(design, target=target).text
    written = parse(text)
    before, dimension, after = neighbours(source)
    assert neighbours(written)[1] == dimension
    if target == 9:
        index = source.children.index(dimension)
        assert written.children[index] == dimension
        assert opaque_count(read_board(text)) == opaque_count(read_board(DIMENSION))
    else:
        found_before, _, found_after = neighbours(written)
        assert (
            found_before is not None and before is not None and found_after is not None and after is not None
        )
        assert found_before.find("uuid") == before.find("uuid") and found_after.find("uuid") == after.find(
            "uuid"
        )
        removed = 1  # the root (net 0 "") slot
        assert opaque_count(read_board(text)) == opaque_count(read_board(DIMENSION)) - removed
    assert run(f"pcb-write-dimension-{target}") == "load"


def test_fixture_is_authored() -> None:
    assert Path(DIMENSION).is_file()
