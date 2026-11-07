# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reading the Embedded Board Array records (``read.arrays``; change c0374, task 2.2; ``H-A-PANEL-RECORD``,
``INFERRED`` from the panels Altium Designer 24.5.2.23 saved in Part Q phase A, S-1422)."""

from __future__ import annotations

import os
from fractions import Fraction
from pathlib import Path

import pytest

from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.cfb import Storage, write_compound
from fenolite.backends.altium.read.arrays import ArrayError, BoardArray, board_arrays

MM = 1_000_000
SAVED = os.environ.get("FENOLITE_ALTIUM_Q_SAVED")
"""The folder ``saved/board`` of Part Q phase A: the ten panels Altium saved (kept outside the repository)."""


def mm(units: Fraction) -> float:
    """Units of 1/10 000 mil (2.54 nm) in millimetres, to the micrometre."""
    return round(float(units * Fraction(254, 100) / MM), 3)


def document(*records: bytes, count: int | None = None) -> bytes:
    header = (len(records) if count is None else count).to_bytes(4, "little")
    storage = Storage("EmbeddedBoards6", (("Header", header), ("Data", b"".join(records))))
    return write_compound([("FileHeader", b"\0" * 8), storage])


def record(**options: object) -> bytes:
    values: dict[str, object] = {
        "rows": 2,
        "cols": 3,
        "row_spacing": rec.to_units(32 * MM),
        "col_spacing": rec.to_units(42 * MM),
    }
    values.update(options)
    at = (rec.to_units(5 * MM), rec.to_units(7 * MM))
    size = (rec.to_units(40 * MM), rec.to_units(30 * MM))
    return rec.embedded_board_array("board.PcbDoc", at, size, **values)  # type: ignore[arg-type]


def without(block: bytes, field: bytes) -> bytes:
    """``block`` without ``field``, its length word written again."""
    payload = block[4:].replace(field, b"")
    return len(payload).to_bytes(4, "little") + payload


def test_an_authored_array_reads_back() -> None:
    (array,) = board_arrays(document(record()))
    assert array.document == "board.PcbDoc"
    assert (mm(array.x), mm(array.y)) == (5.0, 7.0)
    assert (array.cols, array.rows) == (3, 2)
    assert (mm(array.col_pitch), mm(array.row_pitch)) == (42.0, 32.0)
    assert (array.rotation, array.mirrored, array.linked) == (0.0, False, False)


def test_turn_mirror_and_link_read_back() -> None:
    (array,) = board_arrays(document(record(rotation=90_000_000, mirrored=True, linked=True)))
    assert (array.rotation, array.mirrored, array.linked) == (90.0, True, True)


def test_arrays_keep_their_record_order() -> None:
    found = board_arrays(document(record(rows=1, cols=1), record()))
    assert [(a.cols, a.rows) for a in found] == [(1, 1), (3, 2)]


def test_documents_without_arrays_hold_none() -> None:
    assert board_arrays(document()) == ()
    assert board_arrays(b"not a compound file") == ()


def test_records_that_do_not_read_are_refused() -> None:
    with pytest.raises(ArrayError, match="Header counts 2"):
        board_arrays(document(record(), count=2))
    with pytest.raises(ArrayError, match="ROWCOUNT"):
        board_arrays(document(without(record(), b"|ROWCOUNT=2")))
    with pytest.raises(ArrayError, match="bytes after"):
        board_arrays(document(record()[:-3]))


SAVED_PANELS: dict[str, tuple[tuple[str, float, float, float, bool, int, int, float, float, bool], ...]] = {
    # name: (document, x, y mm, rotation, mirrored, columns, rows, column and row pitch mm, linked) per array
    "panel-a": (("board.PcbDoc", 5, 5, 0, False, 2, 2, 42, 32, False),),
    "panel-cols4": (("board.PcbDoc", 5, 5, 0, False, 4, 2, 42, 32, False),),
    "panel-rows3": (("board.PcbDoc", 5, 5, 0, False, 2, 3, 42, 32, False),),
    "panel-spacing": (("board.PcbDoc", 5, 5, 0, False, 2, 2, 45, 35, False),),
    "panel-margin": (("board.PcbDoc", 5, 5, 0, False, 2, 2, 43, 33, False),),
    "panel-rot90": (("board.PcbDoc", 5, 5, 90, False, 2, 2, 42, 32, False),),
    "panel-mirror": (("board.PcbDoc", 5, 5, 0, True, 2, 2, 42, 32, False),),
    "panel-link": (("board.PcbDoc", 5, 5, 0, False, 2, 2, 42, 32, True),),
    "panel-move": (("board.PcbDoc", 12, 7, 0, False, 2, 2, 42, 32, False),),
    "panel-two": (
        ("board.PcbDoc", 100, 5, 0, False, 1, 1, 38.1, 63.5, False),
        ("board.PcbDoc", 5, 5, 0, False, 2, 2, 42, 32, False),
    ),
}
"""What ``pcb-document.md``, "Embedded board arrays", records for each saved panel (S-1422)."""


def _row(array: BoardArray) -> tuple[str, float, float, float, bool, int, int, float, float, bool]:
    return (
        array.document,
        mm(array.x),
        mm(array.y),
        array.rotation,
        array.mirrored,
        array.cols,
        array.rows,
        mm(array.col_pitch),
        mm(array.row_pitch),
        array.linked,
    )


@pytest.mark.skipif(not SAVED, reason="FENOLITE_ALTIUM_Q_SAVED names saved/board of Part Q phase A")
@pytest.mark.parametrize("name", sorted(SAVED_PANELS))
def test_the_saved_panels_read_as_recorded(name: str) -> None:
    assert SAVED
    data = (Path(SAVED).expanduser() / f"{name}.PcbDoc").read_bytes()
    assert tuple(_row(array) for array in board_arrays(data)) == SAVED_PANELS[name]


Q12 = os.environ.get("FENOLITE_ALTIUM_Q12")


@pytest.mark.skipif(not Q12, reason="FENOLITE_ALTIUM_Q12 names panel-saved.PcbDoc of case Q12")
def test_the_array_altium_saved_again_reads_back() -> None:
    """Case Q12 (Part Q phase B): Altium saved Fenolite's array again; the record holds the location
    with the document's 1000 mil offset (the user interface shows 0, 5 mm) and the pitch to the micrometre."""
    assert Q12
    (array,) = board_arrays(Path(Q12).expanduser().read_bytes())
    assert _row(array) == ("../board/board.PcbDoc", 25.4, 30.4, 0, False, 2, 2, 42, 32, False)
