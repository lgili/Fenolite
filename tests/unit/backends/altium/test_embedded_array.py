# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Embedded Board Array record (capability altium-pcb-writer, "Array record read back", "Gate off";
change c0173, task 7.2; ``H-A-PANEL-RECORD``, ``INFERRED`` from Part Q phase A, S-1422)."""

from __future__ import annotations

import struct
from functools import cache
from pathlib import Path

import pytest
from _panels import PANELS, build_board, run

from fenolite.backends.altium import pcbdoc
from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.pcbprops import PropertyRecord, parse_blocks, parse_mil
from fenolite.dsl import Panel, mm, to_model
from fenolite.panel.altium import array_record, embedded_files
from fenolite.panel.build import read_source
from fenolite.panel.layout import layout

MM = 1_000_000
DOCUMENT = "../board/board.PcbDoc"


def units(text: str | None) -> int:
    value = parse_mil(text)
    assert value is not None, text
    assert value.denominator == 1, text
    return int(value)


def records(data: bytes) -> tuple[int, tuple[PropertyRecord, ...]]:
    compound = open_compound(data)
    (count,) = struct.unpack("<I", compound.read("EmbeddedBoards6/Header"))
    found, trailing, issues = parse_blocks(compound.read("EmbeddedBoards6/Data"), where="EmbeddedBoards6")
    assert not trailing and not issues
    return count, found


def kit_panel() -> Panel:
    """2 × 2 copies of the 40 × 30 mm fixture board with 2 mm gaps: spacing 42 and 32 mm."""
    panel = Panel("panel", board="board.PcbDoc")
    panel.grid(2, 2, gap=mm(2))
    return panel


@cache
def board_file(folder: str) -> Path:
    return build_board(Path(folder) / "board", "altium")


@pytest.fixture(scope="module")
def board(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return board_file(str(tmp_path_factory.mktemp("array")))


def test_record_alone_reads_back() -> None:
    at = (rec.to_units(10 * MM), rec.to_units(20 * MM))
    size = (rec.to_units(40 * MM), rec.to_units(30 * MM))
    data = rec.embedded_board_array(
        DOCUMENT,
        at,
        size,
        rows=2,
        cols=2,
        row_spacing=rec.to_units(32 * MM),
        col_spacing=rec.to_units(42 * MM),
    )
    (found,), trailing, issues = parse_blocks(data, where="array")
    assert not trailing and not issues
    assert found.get("DOCUMENTPATH") == DOCUMENT
    assert (found.get("ROWCOUNT"), found.get("COLCOUNT")) == ("2", "2")
    assert units(found.get("ROWSPACING")) == rec.to_units(32 * MM)
    assert units(found.get("COLSPACING")) == rec.to_units(42 * MM)
    assert (units(found.get("X")), units(found.get("Y"))) == at
    assert units(found.get("X2")) - units(found.get("X1")) == rec.to_units(42 * MM) + size[0]
    assert units(found.get("Y2")) - units(found.get("Y1")) == rec.to_units(32 * MM) + size[1]
    assert float(found.text("ROTATION")) == 0
    assert found.get("MIRROR") == "FALSE" and found.get("ORIGINMODE") == "1"


def test_record_refuses_absolute_paths() -> None:
    for path in ("C:\\boards\\board.PcbDoc", "/boards/board.PcbDoc", "..\\board\\board.PcbDoc"):
        with pytest.raises(ValueError, match="relative path"):
            rec.embedded_board_array(path, (0, 0), (1, 1), rows=1, cols=1, row_spacing=1, col_spacing=1)


def test_turned_record() -> None:
    data = rec.embedded_board_array(
        DOCUMENT, (0, 0), (100, 100), rows=1, cols=2, row_spacing=100, col_spacing=120, rotation=90_000_000
    )
    (found,), _, _ = parse_blocks(data, where="array")
    assert float(found.text("ROTATION")) == 90


def test_array_record_read_back(board: Path) -> None:
    """Scenario "Array record read back": the panel document holds one array whose counts, spacing,
    location and rotation are the written ones."""
    model = to_model(kit_panel())
    design, _ = read_source(board)
    laid = layout(model, design)
    files, issues = embedded_files(model, laid, design, DOCUMENT)
    assert not [i for i in issues if i.severity == "error"], issues
    assert set(files) == {"panel.PcbDoc", "panel.PrjPcb"}
    count, (found,) = records(files["panel.PcbDoc"])
    assert count == 1
    assert found.raw == array_record(laid, DOCUMENT)
    assert found.get("DOCUMENTPATH") == DOCUMENT
    assert (found.get("ROWCOUNT"), found.get("COLCOUNT")) == ("2", "2")
    # the board read from its document lies on the 2.54 nm unit: each spacing within one unit of 32 and 42 mm
    assert abs(units(found.get("ROWSPACING")) - rec.to_units(32 * MM)) <= 1
    assert abs(units(found.get("COLSPACING")) - rec.to_units(42 * MM)) <= 1
    left = min(copy.rect.x0 for copy in laid.copies)
    low = max(copy.rect.y1 for copy in laid.copies)
    offset = pcbdoc.BOARD_OFFSET_MIL * 25_400
    assert units(found.get("X")) == rec.to_units(left + offset)
    assert units(found.get("Y")) == rec.to_units(laid.size.h - low + offset)
    assert float(found.text("ROTATION")) == 0


def test_array_refuses_mirror_and_turns(board: Path) -> None:
    design, _ = read_source(board)
    mirrored = Panel("panel", board="board.PcbDoc")
    mirrored.grid(2, 2, mirror=True)
    with pytest.raises(ValueError, match="mirrored"):
        model = to_model(mirrored)
        embedded_files(model, layout(model, design), design, DOCUMENT)
    turned = Panel("panel", board="board.PcbDoc")
    turned.grid(2, 2, rot=90)
    model = to_model(turned)
    with pytest.raises(ValueError, match="unturned"):
        array_record(layout(model, design), DOCUMENT)


def test_gate_off(tmp_path: Path) -> None:
    """Scenario "Gate off": with ``EMBEDDED_ARRAYS`` false, ``--altium-panel auto`` writes the flattened
    panel, whose ``EmbeddedBoards6`` has ``Header`` 0 and an empty ``Data``."""
    assert pcbdoc.EMBEDDED_ARRAYS is False
    out = tmp_path / "out"
    code, envelope, err = run(
        "panel", str(PANELS / "tabs.py"), "--out", str(out), "--target", "altium", "--altium-panel", "auto",
        "--confirm", "--no-backup",
    )  # fmt: skip
    assert code == 0, (envelope.get("issues"), err)
    compound = open_compound((out / "tabs.PcbDoc").read_bytes())
    assert compound.read("EmbeddedBoards6/Header") == struct.pack("<I", 0)
    assert compound.read("EmbeddedBoards6/Data") == b""
    assert "altium.panel-flattened" in str(envelope)
