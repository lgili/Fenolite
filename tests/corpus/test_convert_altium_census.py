# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The eight public PCB documents of the corpus written as KiCad boards (change c0161,
``H-K-CONV-A2K-LOAD``; capability design-conversion, scenario "Public documents converted").

The measurement of the design (task 1.1): each document is read with the Altium backend. Its import holds
no KiCad layer row, so ``write_board`` cannot write it. Given the rows of the layers whose names the
two-copper table of KiCad holds (with the inner rows of a four-layer table), the import still holds items
on names that no row declares: the test counts them per name, footprint fields and pads included. Two
documents hold slots turned against the X and Y axes of their footprint, all in oval pads. Since task
2.2 the board writer refuses that probe's board.

The conversion (task 3.2): each document converted to KiCad 10 and 9 with ``fenolite.api.convert(...,
to="kicad", allow_lossy=True)`` is written, read back equal at level 5, gives no ``convert.unexplained``,
and its report holds the counts per kind and reason of ``CONVERTED`` (``docs/evidence/conversion.md``,
"Altium to KiCad").
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from functools import cache

import pytest
from _corpus import manifest_items, require

from fenolite.api.conversion import ConversionResult, convert
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import LAYER_UNDECLARED, undeclared_layers, write_board
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.convert import from_altium, kicad_project, to_kicad
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


@pytest.mark.parametrize("number", DOCUMENTS)
def test_probe_board_refused(number: str) -> None:
    """Since task 2.2 the board writer refuses the probe's board: one ``kicad.board.layer-undeclared`` per
    layer name, with the count of items, never droppable."""
    design = imported(number)
    assert design.board is not None
    probe = dataclasses.replace(design, board=probe_rows(design.board))
    with pytest.raises(LossyWriteError) as refused:
        write_board(probe, target=10, allow_lossy=True)
    assert refused.value.droppable is False
    found = {i.where: i.message for i in refused.value.issues if i.code == LAYER_UNDECLARED}
    assert sorted(found) == sorted(UNDECLARED[number])
    for name, count in UNDECLARED[number].items():
        assert found[name].startswith(f"{count} item")


R_EDITED = kicad_project.REASON_EDITED
R_SCHEMATIC = kicad_project.REASON_SCHEMATIC
R_SCHEMATIC_REFUSED = kicad_project.REASON_SCHEMATIC_REFUSED
R_RULE_OPT = to_kicad.REASON_RULE_OPT
CONVERTED: dict[str, dict[tuple[str, str, str], int]] = {
    "01": {
        ("footprint", "changed", R_EDITED): 1,
        ("keep-out", "changed", from_altium.REASON_KEEPOUT_ARC): 1,
        ("rule", "changed", R_RULE_OPT): 1,
        ("graphic", "changed", from_altium.REASON_KEEPOUT_AREA): 20,
        ("schematic", "changed", R_SCHEMATIC): 1,
    },
    "02": {
        ("rule", "changed", R_RULE_OPT): 1,
        ("text", "lost", from_altium.REASON_DRILL): 1,
        ("schematic", "changed", R_SCHEMATIC): 1,
    },
    "03": {
        ("rule", "changed", R_RULE_OPT): 2,
        ("graphic", "changed", from_altium.REASON_KEEPOUT_AREA): 1,
        ("schematic", "changed", R_SCHEMATIC): 1,
    },
    "04": {
        ("footprint-graphic", "changed", from_altium.REASON_KEEPOUT_FOOTPRINT): 1,
        ("rule", "changed", R_RULE_OPT): 1,
        ("schematic", "changed", R_SCHEMATIC): 1,
    },
    "05": {
        ("rule", "changed", R_RULE_OPT): 1,
        ("schematic", "changed", R_SCHEMATIC): 1,
    },
    "06": {
        ("footprint-graphic", "changed", from_altium.REASON_KEEPOUT_FOOTPRINT): 2,
        ("rule", "changed", R_RULE_OPT): 1,
        ("graphic", "changed", from_altium.REASON_KEEPOUT_AREA): 4,
        ("graphic", "lost", from_altium.REASON_OUTSIDE): 3,
        ("schematic", "changed", R_SCHEMATIC): 1,
    },
    "07": {
        ("footprint", "changed", R_EDITED): 2,
        ("schematic", "changed", R_SCHEMATIC): 1,
    },
    "08": {
        ("footprint", "changed", R_EDITED): 260,
        ("footprint", "changed", from_altium.REASON_NAME): 1,
        ("pad", "changed", from_altium.REASON_PADSTACK): 5,
        ("text", "lost", from_altium.REASON_DRILL): 298,
        ("graphic", "lost", from_altium.REASON_DRILL): 1000,
        ("graphic", "changed", from_altium.REASON_KEEPOUT_AREA): 1,
        ("schematic", "lost", R_SCHEMATIC_REFUSED): 1,
    },
}
"""Per document converted to KiCad 10, the items changed and lost per kind and reason (measured on
2026-10-09; the table of ``docs/evidence/conversion.md``, "Altium to KiCad"). Target 9 gives the same."""


@cache
def converted(number: str, target: int) -> ConversionResult:
    return convert(require(_row(number)), to="kicad", kicad_version=target, allow_lossy=True)  # type: ignore[arg-type]


@pytest.mark.parametrize("target", [10, 9])
@pytest.mark.parametrize("number", DOCUMENTS)
def test_public_documents_converted(number: str, target: int) -> None:
    """Scenario "Public documents converted": each document is written, read back equal at level 5
    (every difference explained), and its report holds the counts of ``CONVERTED``."""
    result = converted(number, target)
    assert result.unexplained == ()
    assert not [i for i in result.issues if i.code == "convert.unexplained"]
    report = result.equivalence.report if result.equivalence is not None else None
    assert report is not None and report.levels[-1].level == 5
    assert {found.difference.kind for found in result.explained} <= {"ref-ambiguous"}
    rows = {
        (row.kind, reason.outcome, reason.reason): reason.count
        for row in result.conversion.report.rows
        for reason in row.reasons
    }
    print(f"{PREFIX}{number} t{target}: {rows}")
    assert rows == CONVERTED[number]
    board = result.conversion.design.board
    assert board is not None and undeclared_layers(board) == {}
    name = result.conversion.source.name
    assert {f"{name}.kicad_pcb", f"{name}.kicad_pro", f"{name}.kicad_dru", "fp-lib-table"} <= set(
        result.conversion.files
    )
