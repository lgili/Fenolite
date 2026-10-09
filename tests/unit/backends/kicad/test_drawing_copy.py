# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Plot copies of a board and KiCad's drill report (capability manufacturing-exports, "Drawing plot
copies" and "Fabrication drawing kind"; change c0117). Hermetic: no ``kicad-cli`` runs."""

from __future__ import annotations

import hashlib

from _boards import FIXTURE
from _drawdesign import SHOWN_REF, bench_design, bench_text
from _fakecli import drill_report

from fenolite.backends.base import PlotDimension, PlotTable, PlotText
from fenolite.backends.kicad.drawing import (
    default_sheet_obstacles,
    dimension_value,
    item_nodes,
    layer_extent,
    plot_copy,
    read_drill_report,
    shows_reference,
)
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse, tree_equal
from fenolite.core.coords import Point

MM = 1_000_000
SIZE = 1_500_000
TABLE = PlotTable(
    "fab:drill",
    "Dwgs.User",
    Point(200 * MM, 20 * MM),
    (20 * MM, 30 * MM, 10 * MM),
    (6 * MM, 6 * MM),
    (("Drill", "Count", "Holes"), ("0.300", "3", 'a "via"\nline')),
    1_500_000,
)


def _copy(major: int) -> str:
    text = FIXTURE.read_text(encoding="utf-8")
    return plot_copy(text, [TABLE], paper="A3", major=major, layers=("Dwgs.User",))


def _undone(copy: str) -> Node:
    """The copy without its three changes: the paper, the added layer row and the table."""
    root = parse(copy)
    children: list[object] = []
    for child in root.children:
        if isinstance(child, Node) and child.name == "table":
            continue
        if isinstance(child, Node) and child.name == "paper":
            child = parse('(paper "A4")')
        if isinstance(child, Node) and child.name == "layers":
            child = child.with_children([row for row in child.children if "Dwgs.User" not in dumps(row)])
        children.append(child)
    return root.with_children(children)  # type: ignore[arg-type]


def test_copy_holds_only_the_changes_of_the_page() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    before = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert '"Dwgs.User"' not in text and '(paper "A4")' in text
    copy = _copy(9)
    root = parse(copy)
    assert dumps(root.find("paper"), style="compact") == '(paper "A3")'  # type: ignore[arg-type]
    assert '(17 "Dwgs.User" user "User.Drawings")' in copy
    tables = root.nodes("table")
    assert len(tables) == 1 and tables[0].find("uuid") is None and root.children[-1] is tables[0]
    assert tree_equal(_undone(copy), parse(text))
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == before


def test_target_10_table() -> None:
    table = parse(_copy(10)).nodes("table")[0]
    assert [child.name for child in table.nodes()] == [
        "column_count",
        "uuid",
        "layer",
        "border",
        "separators",
        "column_widths",
        "row_heights",
        "cells",
    ]
    assert dumps(table.find("column_widths"), style="compact") == "(column_widths 20 30 10)"  # type: ignore[arg-type]
    cells = table.find("cells")
    assert cells is not None and len(cells.nodes("table_cell")) == 6
    for cell in cells.nodes("table_cell"):
        assert [child.name for child in cell.nodes()] == [
            "start",
            "end",
            "margins",
            "span",
            "layer",
            "uuid",
            "effects",
        ]
    last = cells.nodes("table_cell")[-1]
    assert last.atoms()[0].value == 'a "via"\nline'
    compact = dumps(last, style="compact")
    assert "(start 250 26) (end 260 32) (margins 1 1 1 1) (span 1 1)" in compact
    assert "(size 1.5 1.5)" in dumps(last, style="compact") and "(thickness 0.225)" in dumps(
        last, style="compact"
    )
    uuids = [dumps(node) for node in (table, *cells.nodes("table_cell")) for node in node.nodes("uuid")]
    assert len(set(uuids)) == 7


def test_same_input_same_copy() -> None:
    assert _copy(10) == _copy(10) and _copy(9) != _copy(10)
    renamed = plot_copy(
        FIXTURE.read_text(encoding="utf-8"),
        [PlotText("assembly-top:designator:x", "R1", "F.Fab", Point(MM, MM), MM)],
        paper="A4",
        major=10,
        layers=("F.Fab",),
    )
    assert renamed.count('"F.Fab" user') == 1  # the layer row is added once, or was there already


def test_text_and_dimension_nodes() -> None:
    front = PlotText("p:a", "R1", "F.Fab", Point(10 * MM, 20 * MM), MM)
    back = PlotText("p:b", "R2", "B.Fab", Point(10 * MM, 20 * MM), MM)
    corner, layer = Point(100 * MM, 100 * MM), "Dwgs.User"
    width = PlotDimension(
        "fab:width", layer, corner, Point(176 * MM, 100 * MM), -8 * MM, "horizontal", 2, SIZE
    )
    height = PlotDimension(
        "fab:height", layer, corner, Point(100 * MM, 192_505_000), -8 * MM, "vertical", 2, SIZE
    )
    a, b, c, d = (dumps(node, style="compact") for node in item_nodes([front, back, width, height], major=10))
    assert a.startswith('(gr_text "R1" (at 10 20 0) (layer "F.Fab") (uuid') and "justify" not in a
    assert "(justify mirror)" in b and '(layer "B.Fab")' in b
    assert c.startswith('(dimension (type orthogonal) (layer "Dwgs.User") (uuid')
    assert "(pts (xy 100 100) (xy 176 100)) (height -8) (orientation 0)" in c
    assert '(format (prefix "") (suffix "") (units 2) (units_format 1) (precision 2))' in c
    assert '(gr_text "76.00 mm" (at 138 100 0)' in c and "(orientation 1)" in d
    assert dimension_value(height) == "92.51 mm"  # half away from zero
    assert item_nodes([front], major=9) == item_nodes([front], major=10)


def test_layer_extent() -> None:
    text = bench_text(10)
    assert layer_extent(text, "Dwgs.User") is None and layer_extent(text, "F.Fab") is None
    assert layer_extent(text, "Edge.Cuts") == (100 * MM, 100 * MM, 176 * MM, 192 * MM)
    copy = plot_copy(text, [TABLE], paper="A3", major=10, layers=("Dwgs.User",))
    assert layer_extent(copy, "Dwgs.User") == (200 * MM, 20 * MM, 260 * MM, 32 * MM)


def test_a_footprint_that_shows_its_reference() -> None:
    design = read_board(bench_text(10))
    assert design.board is not None
    refs = {component.id: component.ref for component in design.circuit.components}
    shown = {refs[fp.component_id]: shows_reference(fp, "F.Fab") for fp in design.board.footprints}
    assert shown == {"R1": False, "R3": False, "J1": False, "H1": False, SHOWN_REF: True, "R2": False}
    bottom = next(fp for fp in design.board.footprints if fp.side == "bottom")
    assert not shows_reference(bottom, "B.Fab")
    built = bench_design().board
    assert built is not None and not any(shows_reference(fp, "F.Fab") for fp in built.footprints)
    hidden = bench_text(10).replace(
        '(layer "F.Fab")\n\t\t\t(uuid "d0a0', '(layer "F.Fab") (hide yes) (uuid "d0a0'
    )
    hidden = hidden.replace(
        '(at 0 0 0) (layer "F.Fab") (uuid "d0a00000', '(at 0 0 0) (layer "F.Fab") (hide yes) (uuid "d0a00000'
    )
    again = read_board(hidden)
    assert again.board is not None and not any(shows_reference(fp, "F.Fab") for fp in again.board.footprints)


def test_obstacles_of_the_default_sheet() -> None:
    margin, boxes = default_sheet_obstacles(420 * MM, 297 * MM)
    assert margin == (10 * MM, 10 * MM, 410 * MM, 287 * MM)
    assert boxes[-1] == (300 * MM, 253 * MM, 408 * MM, 285 * MM)


def test_both_forms_of_a_tool_line() -> None:
    text = (
        "Drill report for b.kicad_pcb\nCreated on 2026-10-07T00:00:00\n\n"
        "Drill file 'b-PTH.drl' contains\n"
        '    T1  0.300mm  0.0118"  (83 holes))\n'
        '    T2  0.600mm  0.0236"  (6 holes)\n'
    )
    report = read_drill_report(text)
    assert [(f.name, f.plated, f.span, f.tools) for f in report.files] == [
        ("b-PTH.drl", True, None, ((300_000, 83), (600_000, 6)))
    ]


def test_report_of_kicad_form() -> None:
    text = drill_report(
        "b", {"0.300": 3, "1.000": 3}, {"3.200": 1}, {("F.Cu", "In1.Cu"): {"0.100": 1, "0.200": 1}}
    )
    files = read_drill_report(text).files
    assert [(f.name, f.plated, f.span) for f in files] == [
        ("b-PTH.drl", True, None),
        ("b-front-in1.drl", True, ("F.Cu", "In1.Cu")),
        ("b-NPTH.drl", False, None),
    ]
    assert files[1].tools == ((100_000, 1), (200_000, 1)) and files[2].tools == ((3_200_000, 1),)
    slotted = text.replace("(3 holes))", "(3 holes)  (with 1 slot)")
    assert read_drill_report(slotted).files[0].tools == ((300_000, 3), (1_000_000, 3))
    assert read_drill_report("Drill report\nCreated on today\n").files == ()
