# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The blocks of a drawing (capability manufacturing-exports, "Drawing tables and notes"; change c0117).

The stack-up scenario states the fields of change c0101 (``dielectric_kind`` and ``Stackup.thickness()``)
where the model has them; before c0101 a dielectric reads ``dielectric`` and the total is the sum of the
entries, which is what this file then asserts.
"""

from __future__ import annotations

import dataclasses

from _drawdesign import DRILL_ROWS, bench_design

from fenolite.backends.base import PlotTable
from fenolite.core.coords import Point
from fenolite.exports.drawing_spec import DEFAULT, FabSpec
from fenolite.exports.drawing_tables import (
    GLYPH_BOUND,
    GLYPH_SET,
    LINE_PITCH,
    MARGIN,
    board_block,
    break_lines,
    drill_block,
    drill_rows,
    fab_blocks,
    impedance_block,
    line_pitch,
    mm_text,
    notes_block,
    stackup_block,
    text_width,
)
from fenolite.model.board import StackLayer, Stackup, Via
from fenolite.model.design import Design

SIZE = 1_500_000
MM = 1_000_000
NOTE = " ".join(["Fabricate", "to", "the", "class", "that", "the", "order", "states;"] * 6)[:227]
HAS_KIND = "dielectric_kind" in {field.name for field in dataclasses.fields(StackLayer)}


def _with(design: Design, **changes: object) -> Design:
    assert design.board is not None
    return dataclasses.replace(design, board=dataclasses.replace(design.board, **changes))  # type: ignore[arg-type]


def _two_layer_stackup() -> Stackup:
    def layer(name: str, kind: str, thickness: int = 0, **more: object) -> StackLayer:
        return StackLayer(id=f"sly_{name}", name=name, kind=kind, thickness=thickness, **more)  # type: ignore[arg-type]

    core = {"dielectric_kind": "core"} if HAS_KIND else {}
    return Stackup(
        id="stk_two",
        layers=(
            layer("F.SilkS", "silkscreen"),
            layer("F.Paste", "solderpaste"),
            layer("F.Mask", "soldermask", 10_000),
            layer("F.Cu", "copper", 35_000),
            layer("dielectric 1", "dielectric", 1_510_000, material="FR4", epsilon_r="4.5", **core),
            layer("B.Cu", "copper", 35_000),
            layer("B.Mask", "soldermask", 10_000),
            layer("B.Paste", "solderpaste"),
            layer("B.SilkS", "silkscreen"),
        ),
    )


# -- text


def test_text_bounds() -> None:
    assert GLYPH_BOUND * SIZE == 2_175_000 and line_pitch(SIZE) == 2_415_000 == LINE_PITCH * SIZE
    assert text_width("", SIZE) == 0
    extra = 375_000  # what KiCad adds to the advances of a line: a quarter of the size
    assert text_width("m" * 10, SIZE) == 21_750_000 + extra and text_width("m", SIZE) == 2_175_000 + extra
    assert text_width("±µ°×Ω–—…", SIZE) == 8 * 2_175_000 + extra
    # a character that was not measured counts twice the size
    assert text_width("\u4e2d", SIZE) == 2 * SIZE + extra
    assert {"A", "z", "0", "~", " ", "Ä", "ß", "ñ"} <= GLYPH_SET and "\n" not in GLYPH_SET


def test_text_lengths_in_millimetres() -> None:
    assert [mm_text(v) for v in (300_000, 1_600_000, 210_400, 0, 76 * MM)] == [
        "0.300",
        "1.600",
        "0.2104",
        "0.000",
        "76.000",
    ]


def test_notes_are_broken_by_the_bound() -> None:
    assert len(NOTE) == 227
    width = 78 * MM
    broken = break_lines(NOTE, width, SIZE)
    lines = broken.split("\n")
    assert len(lines) > 1 and all(text_width(line, SIZE) <= width for line in lines)
    assert " ".join(lines) == NOTE
    block = notes_block((NOTE,), 80 * MM, SIZE)
    assert block is not None and block.rows == (("1.", broken),)
    assert block.row_heights == (len(lines) * 2_415_000 + 2 * MM,)
    assert block.column_widths[1] == 80 * MM and not block.border


def test_notes_cut_a_long_word_and_keep_line_feeds() -> None:
    width = 10 * 2_175_000 + 375_000
    word = "x" * 25
    assert break_lines(f"a {word} b", width, SIZE).split("\n") == ["a", "x" * 10, "x" * 10, "xxxxx b"]
    assert break_lines("one\n\ntwo", width, SIZE) == "one\n\ntwo"
    assert break_lines("", width, SIZE) == ""
    assert break_lines("a b", width, SIZE) == "a b"


def test_notes_are_numbered_and_absent_without_a_note() -> None:
    assert notes_block((), 120 * MM, SIZE) is None
    block = notes_block(("First ${TITLE}.", "Second."), 120 * MM, SIZE)
    assert block is not None and [row[0] for row in block.rows] == ["1.", "2."]
    assert block.rows[0][1] == "First ${TITLE}."  # a variable is left to KiCad
    assert block.width == text_width("2.", SIZE) + 2 * MARGIN + 120 * MM
    plot = block.plot(Point(MM, 2 * MM), "Dwgs.User")
    assert isinstance(plot, PlotTable) and plot.at == Point(MM, 2 * MM) and not plot.border


# -- tables


def test_stackup_rows_of_a_two_layer_board() -> None:
    design = _with(bench_design(), stackup=_two_layer_stackup())
    block = stackup_block(design, SIZE)
    assert block is not None
    head, *rows, total = block.rows
    assert head == ("Layer", "Type", "Material", "Thickness", "Dk")  # no Color and no Df column
    assert [row[0] for row in rows] == [
        "F.SilkS",
        "F.Mask",
        "F.Cu",
        "dielectric 1",
        "B.Cu",
        "B.Mask",
        "B.SilkS",
    ]
    assert rows[3] == ("dielectric 1", "core" if HAS_KIND else "dielectric", "FR4", "1.510", "4.5")
    assert rows[0] == ("F.SilkS", "silkscreen", "", "", "")  # a thickness of 0 is an empty cell
    assert total == ("Total", "", "", "1.600", "")
    assert all(
        width == max(text_width(row[c], SIZE) for row in block.rows) + 2 * MARGIN
        for c, width in enumerate(block.column_widths)
    )
    assert set(block.row_heights) == {2_415_000 + 2 * MARGIN}


def test_drill_rows_of_vias_and_pads() -> None:
    design = bench_design()
    assert design.board is not None
    blind = dataclasses.replace(design.board.vias[3], drill=100_000)
    design = _with(design, vias=(*design.board.vias[:3], blind))
    rows = drill_rows(design)
    assert [(r.plated, r.first, r.last, r.drill, r.slot, r.count, r.kinds) for r in rows] == [
        (True, "F.Cu", "B.Cu", 300_000, None, 3, ("via",)),
        (True, "F.Cu", "B.Cu", 1_000_000, None, 2, ("pad",)),
        (True, "F.Cu", "B.Cu", 1_000_000, 2_000_000, 1, ("pad",)),
        (False, "F.Cu", "B.Cu", 3_200_000, None, 1, ("pad",)),
        (True, "F.Cu", "In1.Cu", 100_000, None, 1, ("via",)),
    ]
    block = drill_block(rows, SIZE)
    assert block is not None
    assert block.rows[0] == ("Drill", "Slot", "Plated", "Layers", "Count", "Holes")
    assert block.rows[3] == ("1.000", "2.000", "yes", "F.Cu - B.Cu", "1", "pad")
    assert block.rows[4] == ("3.200", "", "no", "F.Cu - B.Cu", "1", "pad")
    assert block.rows[-1] == ("Total", "", "", "", "8", "")


def test_drill_rows_of_the_bench_and_a_via_on_a_pad_drill() -> None:
    design = bench_design()
    assert tuple(
        (r.plated, r.first, r.last, r.drill, r.slot, r.count, r.kinds) for r in drill_rows(design)
    ) == (DRILL_ROWS)
    assert design.board is not None
    same = dataclasses.replace(design.board.vias[0], id="via_extra", drill=1_000_000, layers=("B.Cu", "F.Cu"))
    rows = drill_rows(_with(design, vias=(*design.board.vias, same)))
    assert (rows[1].count, rows[1].kinds) == (3, ("via", "pad"))
    assert drill_rows(design) == drill_rows(design)  # pure


def test_drill_block_without_a_slot_or_a_hole() -> None:
    design = _with(bench_design(), footprints=())
    block = drill_block(drill_rows(design), SIZE)
    assert block is not None and block.rows[0] == ("Drill", "Plated", "Layers", "Count", "Holes")
    assert drill_block(drill_rows(_with(design, vias=())), SIZE) is None


def test_board_block() -> None:
    block = board_block(bench_design(), SIZE)
    assert block is not None
    assert block.rows == (
        ("Board", "Value"),
        ("Copper layers", "4"),
        ("Outline", "76.000 x 92.000"),
        ("Thickness", "1.580"),
        ("Finish", "ENIG"),
        ("Impedance controlled", "no"),
        ("Smallest drill", "0.100"),
    )
    assert not any("via" in row[0].lower() and "protect" in row[0].lower() for row in block.rows)


def test_no_stackup() -> None:
    design = _with(bench_design(), stackup=None)
    blocks, issues = fab_blocks(design, DEFAULT)
    assert [block.name for block in blocks] == ["board", "drill"]
    assert [row[0] for row in blocks[0].rows] == ["Board", "Copper layers", "Outline", "Smallest drill"]
    assert [(i.code, i.severity) for i in issues] == [("drawing.stackup-missing", "info")]
    spec = dataclasses.replace(DEFAULT, fab=FabSpec(tables=("board", "drill")))
    assert fab_blocks(design, spec)[1] == ()  # a table that was not asked for is not missed


def test_impedance_gives_no_block_and_no_issue() -> None:
    assert impedance_block(bench_design(), SIZE) is None
    spec = dataclasses.replace(DEFAULT, fab=FabSpec(tables=("impedance",), notes=("N.",)))
    assert fab_blocks(bench_design(), spec) == ((), ())


def test_blocks_of_the_fabrication_page_in_order() -> None:
    spec = dataclasses.replace(DEFAULT, fab=FabSpec(notes=("One.",)))
    blocks, issues = fab_blocks(bench_design(), spec)
    assert [block.name for block in blocks] == ["board", "stackup", "drill", "notes"] and issues == ()
    assert all(isinstance(via, Via) for via in bench_design().board.vias)  # type: ignore[union-attr]
