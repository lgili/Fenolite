# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The eight public PCB documents of the corpus written as KiCad boards (change c0161,
``H-K-CONV-A2K-LOAD``; capability design-conversion, scenario "Public documents converted").

The measurement of the design (task 1.1): each document is read with the Altium backend. Its import holds
no KiCad layer row, so ``write_board`` cannot write it. Given the rows of the layers whose names the
two-copper table of KiCad holds (with the inner rows of a four-layer table), the import still holds items
on names that no row declares: the test counts them per name, footprint fields and pads included. Two
documents hold slots turned against the X and Y axes of their footprint, all in oval pads.
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from functools import cache

import pytest
from _corpus import manifest_items, require

from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import write_board
from fenolite.model.board import Board
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_corpus
PREFIX = "altium-third-party-pcbdoc-"
DOCUMENTS = tuple(f"{n:02d}" for n in range(1, 9))
UNDECLARED: dict[str, dict[str, int]] = {
    "01": {"Altium.KeepOut": 20},
    "02": {"Altium.DrillDrawing": 1, "Mech.1": 16},
    "03": {"Altium.KeepOut": 1},
    "04": {"Mech.1": 12, "Mech.2": 15},
    "05": {"Mech.1": 4},
    "06": {"Altium.74": 3, "Altium.KeepOut": 4, "Mech.1": 16, "Mech.2": 1},
    "07": {"Mech.1": 12},
    "08": {"Altium.DrillDrawing": 1298, "Altium.KeepOut": 1, "Mech.1": 62, "Mech.15": 6},
}
"""Per document, the items on each layer name that no row of the probe's table declares (measured on
2026-10-09; the design's table, footprint fields and pads included)."""
TURNED_SLOTS: dict[str, dict[tuple[str, int], int]] = {
    "07": {("oval", 45_000_000): 4, ("oval", 135_000_000): 4},
    "08": {("oval", 45_000_000): 2, ("oval", 135_000_000): 2},
}
"""Per document, the slots whose axis (``hole_rotation``, the import's frame of the footprint) is neither
along X nor along Y, by pad shape and axis modulo 180°."""


def _row(number: str) -> object:
    rows = {item.id: item for item in manifest_items("altium-pcbdoc")}
    rows.update({item.id: item for item in manifest_items("altium")})
    return rows[PREFIX + number]


@cache
def imported(number: str) -> Design:
    read = AltiumBackend().read(require(_row(number)))  # type: ignore[arg-type]
    assert isinstance(read.content, Design)
    return read.content


def probe_rows(board: Board) -> Board:
    """``board`` with KiCad's rows on the layers whose names a created table holds, every other layer
    left out of the table (the probe of the design, measurement 2)."""
    copper = sum(1 for layer in board.layers if layer.kind == "copper")
    rows = {layer.name: layer for layer in created_layers(copper if copper in (2, 4, 6, 8) else 2)}
    layers = tuple(
        dataclasses.replace(layer, ext={**layer.ext, "kicad": rows[layer.name].ext["kicad"]})
        for layer in board.layers
        if layer.name in rows
    )
    return dataclasses.replace(board, layers=layers)


def undeclared(board: Board) -> dict[str, int]:
    """The items of ``board`` per layer name that no layer of ``board`` declares."""
    declared = {layer.name for layer in board.layers}
    found: Counter[str] = Counter()
    names: list[str] = []
    for fp in board.footprints:
        names += [f.layer for f in fp.fields]
        names += [name for pad in fp.pads for name in pad.layers]
    names += [x.layer for x in (*board.tracks, *board.arcs, *board.graphics, *board.texts, *board.dimensions)]
    names += [name for x in (*board.vias, *board.zones, *board.keepouts) for name in x.layers]
    found.update(name for name in names if name not in declared)
    return dict(sorted(found.items()))


def turned_slots(board: Board) -> dict[tuple[str, int], int]:
    found: Counter[tuple[str, int]] = Counter()
    for fp in board.footprints:
        for pad in fp.pads:
            stack = pad.padstack
            if stack is None or stack.hole_shape != "slot":
                continue
            turn = stack.hole_rotation % 180_000_000
            if turn not in (0, 90_000_000):
                found[(pad.shape, turn)] += 1
    return dict(sorted(found.items()))


@pytest.mark.parametrize("number", DOCUMENTS)
def test_import_has_no_kicad_rows(number: str) -> None:
    """Measurement 1: the import's layers carry no KiCad row, so the board writer cannot write them."""
    design = imported(number)
    assert design.board is not None
    assert all("kicad" not in layer.ext for layer in design.board.layers)
    with pytest.raises(KeyError, match="number"):
        write_board(design, target=10)


@pytest.mark.parametrize("number", DOCUMENTS)
def test_undeclared_layer_names(number: str) -> None:
    """Measurement 2: the items on names that the probe's table does not declare."""
    design = imported(number)
    assert design.board is not None
    board = probe_rows(design.board)
    found = undeclared(board)
    print(f"{PREFIX}{number}: {found}")
    assert found == UNDECLARED[number]


@pytest.mark.parametrize("number", DOCUMENTS)
def test_turned_slots(number: str) -> None:
    design = imported(number)
    assert design.board is not None
    assert turned_slots(design.board) == TURNED_SLOTS.get(number, {})
