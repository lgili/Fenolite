# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Slots and cut-outs in a conversion (capability design-conversion, "Slots and cut-outs in a conversion";
change c0170).

The fixture is the shared one of change c0167 (``tests/data/slots/design.py``) as the build writes it for
KiCad 10 (``tests/data/slots/slots_t10.kicad_pcb``): a 60 × 40 mm board, the lone slot ``S1``, the L of
``S2`` and ``S3`` merged into one ring, the rounded cut-out and the round hole ``H1``. Read back, its
edges are four rings of ``Edge.Cuts`` graphics: the board and three inner rings, each with arcs.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path

import pytest
from _convert import read_as

from fenolite.backends.altium import lower, pcbdoc
from fenolite.backends.altium.cutouts import GATED
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RegionRecord
from fenolite.backends.kicad.pcb import read_board
from fenolite.convert import convert_project
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model.board import Graphic
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]
SLOTS_T10 = ROOT / "tests" / "data" / "slots" / "slots_t10.kicad_pcb"
MM = 1_000_000


def _fixture() -> Design:
    return read_board(SLOTS_T10.read_text(encoding="utf-8"), file=SLOTS_T10.name)


def _cutout_regions(data: bytes) -> list[RegionRecord]:
    found: list[RegionRecord] = []
    for region in read_pcbdoc(data).regions:
        assert isinstance(region, RegionRecord)
        if dict(region.properties.fields).get("ISBOARDCUTOUT") == "TRUE":
            found.append(region)
    return found


def _lines(name: str, ring: Sequence[tuple[float, float]]) -> list[Graphic]:
    points = [Point(round(x * MM), round(y * MM)) for x, y in ring]
    return [
        Graphic(id=derived_id("gfx", "test", f"{name}:{k}"), kind="line", layer="Edge.Cuts", points=(a, b))
        for k, (a, b) in enumerate(zip(points, [*points[1:], points[0]], strict=True))
    ]


def _with_edges(design: Design, *graphics: Graphic) -> Design:
    """``design`` whose edge graphics are ``graphics``."""
    board = design.board
    assert board is not None
    kept = tuple(g for g in board.graphics if g.layer != "Edge.Cuts")
    return dataclasses.replace(design, board=dataclasses.replace(board, graphics=(*kept, *graphics)))


BOX = [(0, 0), (60, 0), (60, 40), (0, 40)]


def test_altium_fixture_with_the_gate_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Fixture to Altium", the gate off: three rings lost with the gate's reason, none under
    ``outline``, and no region in the document."""
    read_as(monkeypatch, _fixture())
    conversion = convert_project("slots.kicad_pcb", to="altium")
    report = conversion.report
    assert report.row("outline") is None
    row = report.row("cutout")
    assert row is not None and (row.source, row.written, row.changed, row.lost) == (3, 0, 0, 3)
    assert row.loss == "report" and row.group == "board"
    assert [(r.reason, r.outcome, r.ids) for r in row.reasons] == [
        (GATED, "lost", ("cutout/1", "cutout/2", "cutout/3"))
    ]
    assert not _cutout_regions(conversion.files[conversion.read_back])


def test_altium_fixture_with_the_gate_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Fixture to Altium", the gate on: the three rings are written as cut-out regions, each
    changed because its arcs are polygonised."""
    monkeypatch.setattr(pcbdoc, "CUTOUT_REGIONS", True)
    read_as(monkeypatch, _fixture())
    conversion = convert_project("slots.kicad_pcb", to="altium")
    report = conversion.report
    assert report.row("outline") is None
    row = report.row("cutout")
    assert row is not None and (row.source, row.written, row.changed, row.lost) == (3, 0, 3, 0)
    assert [(r.reason, r.outcome) for r in row.reasons] == [(lower.CUTOUT_POLYGONISED, "changed")]
    assert len(_cutout_regions(conversion.files[conversion.read_back])) == 3
    assert not report.lossy


def test_altium_ring_without_arcs_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cut-out of straight edges is written as it is: counted written, not changed."""
    monkeypatch.setattr(pcbdoc, "CUTOUT_REGIONS", True)
    design = _with_edges(_fixture(), *_lines("box", BOX), *_lines("cut", [(5, 5), (9, 5), (9, 8), (5, 8)]))
    read_as(monkeypatch, design)
    conversion = convert_project("slots.kicad_pcb", to="altium")
    row = conversion.report.row("cutout")
    assert row is not None and (row.source, row.written, row.changed, row.lost) == (1, 1, 0, 0)
    (region,) = _cutout_regions(conversion.files[conversion.read_back])
    assert len(region.outline) == 4


def test_altium_overlapping_rings_count_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two overlapping inner rings of the edges are one region, counted once and changed "merged"."""
    pytest.importorskip("pyclipper")
    monkeypatch.setattr(pcbdoc, "CUTOUT_REGIONS", True)
    design = _with_edges(
        _fixture(),
        *_lines("box", BOX),
        *_lines("a", [(5, 5), (15, 5), (15, 10), (5, 10)]),
        *_lines("b", [(10, 8), (20, 8), (20, 12), (10, 12)]),
    )
    read_as(monkeypatch, design)
    conversion = convert_project("slots.kicad_pcb", to="altium")
    row = conversion.report.row("cutout")
    assert row is not None and (row.source, row.written, row.changed, row.lost) == (1, 0, 1, 0)
    assert [(r.reason, r.ids) for r in row.reasons] == [(lower.CUTOUT_MERGED, ("cutout/1+cutout/2",))]
    (region,) = _cutout_regions(conversion.files[conversion.read_back])
    assert len(region.outline) == 8


def test_altium_overlap_without_a_union_is_lost(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the ``geo`` extra the overlapping rings stay one item, lost with the reason that names it."""
    from fenolite.backends.altium import cutouts
    from fenolite.geometry.errors import backend_unavailable

    def unavailable(*_args: object, **_kwargs: object) -> object:
        raise backend_unavailable("no backend")

    monkeypatch.setattr(cutouts, "merge_groups", unavailable)
    monkeypatch.setattr(pcbdoc, "CUTOUT_REGIONS", True)
    design = _with_edges(
        _fixture(),
        *_lines("box", BOX),
        *_lines("a", [(5, 5), (15, 5), (15, 10), (5, 10)]),
        *_lines("b", [(10, 8), (20, 8), (20, 12), (10, 12)]),
    )
    read_as(monkeypatch, design)
    row = convert_project("slots.kicad_pcb", to="altium").report.row("cutout")
    assert row is not None and (row.source, row.lost) == (1, 1)
    assert [(r.reason, r.ids) for r in row.reasons] == [(cutouts.NO_UNION, ("cutout/1+cutout/2",))]


def test_altium_board_ring_arcs_as_today(monkeypatch: pytest.MonkeyPatch) -> None:
    """The board ring of the edges is written as before: an arc as two straight edges, counted under
    ``outline`` by the id of its graphic; no edge is "outside the first ring" any more."""
    arc = Graphic(
        id=derived_id("gfx", "test", "arc"),
        kind="arc",
        layer="Edge.Cuts",
        points=(Point(60 * MM, 40 * MM), Point(30 * MM, 50 * MM), Point(0, 40 * MM)),
    )
    lines = _lines("box", BOX)[:2] + _lines("left", [(0, 40), (0, 0)])[:1]
    design = _with_edges(_fixture(), *lines, arc, *_lines("cut", [(5, 5), (9, 5), (9, 8), (5, 8)]))
    read_as(monkeypatch, design)
    conversion = convert_project("slots.kicad_pcb", to="altium")
    row = conversion.report.row("outline")
    assert row is not None and [(r.reason, r.ids) for r in row.reasons] == [(lower.OUTLINE_ARC, (arc.id,))]
    cutout = conversion.report.row("cutout")
    assert cutout is not None and (cutout.source, cutout.lost) == (1, 1)
    outline = read_pcbdoc(conversion.files[conversion.read_back]).board.outline
    assert len({(round(v.x), round(v.y)) for v in outline}) == 5  # four corners and the arc's mid


# --- Altium to KiCad -----------------------------------------------------------------------------------

BOARD_RING = (Point(0, 0), Point(60 * MM, 0), Point(60 * MM, 40 * MM), Point(0, 40 * MM))
CUT_A = (Point(10 * MM, 10 * MM), Point(20 * MM, 10 * MM), Point(20 * MM, 15 * MM), Point(10 * MM, 15 * MM))
CUT_B = (Point(15 * MM, 12 * MM), Point(25 * MM, 12 * MM), Point(25 * MM, 20 * MM), Point(15 * MM, 20 * MM))
SLOTS_ALTIUM = ROOT / "tests" / "data" / "slots" / "slots_altium.PcbDoc"


def _overlapping(folder: Path) -> Path:
    """An Altium document authored here: a 60 × 40 mm board with two overlapping board cut-out regions and
    a free slot pad of 1 × 3 mm turned 30° (a ``Hole`` written by ``hole_record``)."""
    from fenolite.backends.altium.pcbdoc import PcbDocSpec, write_pcbdoc
    from fenolite.model.board import Hole

    hole = Hole(
        id="hol_c0170", position=Point(40 * MM, 30 * MM), drill=MM, length=3 * MM, rotation=30_000_000
    )
    spec = PcbDocSpec(outline=BOARD_RING, cutouts=(CUT_A, CUT_B), holes=(hole,))
    path = folder / "overlap.PcbDoc"
    path.write_bytes(write_pcbdoc(spec, filename=path.name))
    return path


def _board(conversion: object) -> Design:
    files = getattr(conversion, "files")  # noqa: B009
    name = getattr(conversion, "read_back")  # noqa: B009
    return read_board(files[name].decode("utf-8"), file=name)


def test_kicad_overlapping_cutouts_are_merged(tmp_path: Path) -> None:
    """Scenario "Overlapping Altium cut-outs to KiCad": one merged ring, ``cutout`` counts one ring changed
    with "merged", and the slot is the footprint ``Fenolite_Holes:NPTH_Slot_1x3mm``."""
    pytest.importorskip("pyclipper")
    from fenolite.backends.kicad.outline import edge_outline

    conversion = convert_project(_overlapping(tmp_path), to="kicad")
    row = conversion.report.row("cutout")
    assert row is not None and (row.source, row.written, row.changed, row.lost) == (1, 0, 1, 0)
    assert [(r.reason, r.ids) for r in row.reasons] == [("merged", ("cutout/1+cutout/2",))]
    board = _board(conversion)
    edges = edge_outline(board)
    assert edges is not None and len(edges.cutouts) == 1 and len(edges.cutouts[0]) == 8
    assert board.board is not None
    (hole,) = [fp for fp in board.board.footprints if fp.lib_ref.startswith("Fenolite_Holes:")]
    assert hole.lib_ref == "Fenolite_Holes:NPTH_Slot_1x3mm" and hole.rotation == 30_000_000
    assert "lib/Fenolite_Holes.pretty/NPTH_Slot_1x3mm.kicad_mod" in conversion.files
    assert b'(name "Fenolite_Holes")' in conversion.files["fp-lib-table"]
    holes = conversion.report.row("hole")
    assert holes is not None and (holes.source, holes.written, holes.changed, holes.lost) == (1, 1, 0, 0)


def test_kicad_overlap_without_a_union_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the ``geo`` extra the overlap cannot be merged: a ``refuse`` loss of ``cutout`` (exit 7
    without consent); with consent the two rings are not written."""
    from fenolite.backends.kicad.outline import edge_outline
    from fenolite.convert import LossyConversionError, to_kicad
    from fenolite.convert.report import OVERLAP_NO_UNION
    from fenolite.geometry.errors import backend_unavailable

    def unavailable(*_args: object, **_kwargs: object) -> object:
        raise backend_unavailable("no backend")

    monkeypatch.setattr(to_kicad, "merge_groups", unavailable)
    source = _overlapping(tmp_path)
    with pytest.raises(LossyConversionError) as caught:
        convert_project(source, to="kicad")
    assert [found.where for found in caught.value.issues] == ["cutout"]
    conversion = convert_project(source, to="kicad", allow_lossy=True)
    row = conversion.report.row("cutout")
    assert row is not None and row.loss == "refuse" and (row.source, row.lost) == (1, 1)
    assert [(r.reason, r.ids) for r in row.reasons] == [(OVERLAP_NO_UNION, ("cutout/1+cutout/2",))]
    assert conversion.report.refused == ("cutout",)
    edges = edge_outline(_board(conversion))
    assert edges is not None and not edges.cutouts


def test_kicad_cutouts_without_overlap_are_written_as_read() -> None:
    """The c0168 fixture document: three cut-out regions that do not overlap, each kept; its four holes
    are the footprints the script ``tests/data/slots/altium.py`` declares (``metric`` names them so)."""
    conversion = convert_project(SLOTS_ALTIUM, to="kicad")
    row = conversion.report.row("cutout")
    assert row is not None and (row.source, row.written, row.changed, row.lost) == (3, 3, 0, 0)
    board = _board(conversion).board
    assert board is not None and board.outline is None
    names = sorted(fp.lib_ref for fp in board.footprints)
    assert names == [
        "Fenolite_Holes:NPTH_3.2mm",
        "Fenolite_Holes:NPTH_Slot_2x10mm",
        "Fenolite_Holes:NPTH_Slot_2x10mm",
        "Fenolite_Holes:NPTH_Slot_2x12mm",
    ]
    assert all(
        fp.attributes == ("board_only", "exclude_from_pos_files", "exclude_from_bom")
        for fp in board.footprints
    )


def test_holes_same_footprint_from_a_script_and_a_conversion(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Same footprint from a script and a conversion": ``design.hole`` built for KiCad 10 and a
    model ``Hole`` of the same drill and length at the same place, converted, give the footprint
    ``Fenolite_Holes:NPTH_Slot_1x3mm`` with equal pads, and the same library file."""
    from _outlinehelp import build_script

    from fenolite.backends.altium.adapter import import_board
    from fenolite.backends.altium.read.pcb import read_pcbdoc as read_document
    from fenolite.convert import to_kicad
    from fenolite.convert.direction import Options
    from fenolite.convert.sources import SourceProject
    from fenolite.dsl import Design as Script
    from fenolite.dsl import mm

    script = Script("holes")
    script.board(mm(30), mm(20))
    script.hole("H1", mm(10), mm(10), drill=mm(1), length=mm(3))
    built = build_script(script, 10)
    built_board = read_board(built.files["holes.kicad_pcb"].decode("utf-8"), file="holes.kicad_pcb").board
    assert built_board is not None
    (placed,) = built_board.footprints

    imported = import_board(read_document(SLOTS_ALTIUM.read_bytes()), file=SLOTS_ALTIUM.name, sha256="0" * 64)
    assert imported.board is not None
    hole = dataclasses.replace(
        imported.board.holes[0], position=placed.position, drill=MM, length=3 * MM, rotation=0
    )
    design = dataclasses.replace(imported, board=dataclasses.replace(imported.board, holes=(hole,)))
    source = SourceProject(
        given=SLOTS_ALTIUM,
        path=SLOTS_ALTIUM,
        root=SLOTS_ALTIUM.parent,
        backend="altium",
        kind="pcbdoc",
        design=design,
    )
    written = to_kicad.write_altium(source, Options(kicad_version=10, name="holes"))
    board = read_board(written.files["holes.kicad_pcb"].decode("utf-8"), file="holes.kicad_pcb").board
    assert board is not None
    (converted,) = [fp for fp in board.footprints if fp.lib_ref.startswith("Fenolite_Holes:")]
    assert converted.lib_ref == placed.lib_ref == "Fenolite_Holes:NPTH_Slot_1x3mm"
    assert (converted.position, converted.rotation) == (placed.position, placed.rotation)

    def shape(pad: object) -> tuple[object, ...]:
        stack = getattr(pad, "padstack")  # noqa: B009
        fields = ("number", "kind", "shape", "size", "position", "rotation", "drill", "layers")
        return (*(getattr(pad, f) for f in fields), stack.hole_shape, stack.hole_length, stack.hole_rotation)

    assert [shape(p) for p in converted.pads] == [shape(p) for p in placed.pads]
    key = "lib/Fenolite_Holes.pretty/NPTH_Slot_1x3mm.kicad_mod"
    assert written.files[key] == built.files[key]


def test_holes_a_plated_hole_is_changed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A plated hole is the numbered pad of a footprint ``PTH_…_Pad_…`` whose copper is the hole: changed,
    "a pad without a net"."""
    from fenolite.backends.altium.adapter import import_board
    from fenolite.backends.altium.read.pcb import read_pcbdoc as read_document
    from fenolite.convert import to_kicad
    from fenolite.convert.direction import Options
    from fenolite.convert.sources import SourceProject

    imported = import_board(read_document(SLOTS_ALTIUM.read_bytes()), file=SLOTS_ALTIUM.name, sha256="0" * 64)
    assert imported.board is not None
    first = dataclasses.replace(imported.board.holes[0], plated=True)
    design = dataclasses.replace(imported, board=dataclasses.replace(imported.board, holes=(first,)))
    source = SourceProject(
        given=SLOTS_ALTIUM,
        path=SLOTS_ALTIUM,
        root=SLOTS_ALTIUM.parent,
        backend="altium",
        kind="pcbdoc",
        design=design,
    )
    written = to_kicad.write_altium(source, Options(kicad_version=10))
    row = written.report.row("hole")
    assert row is not None and (row.source, row.changed) == (1, 1)
    assert [(r.reason, r.ids) for r in row.reasons] == [(to_kicad.PLATED_REASON, (first.id,))]
    board = read_board(written.files[written.read_back].decode("utf-8"), file="x.kicad_pcb").board
    assert board is not None
    (fp,) = [fp for fp in board.footprints if fp.lib_ref.startswith("Fenolite_Holes:PTH_")]
    (pad,) = fp.pads
    assert (pad.number, pad.kind, pad.net_id) == ("1", "thru_hole", None)


def test_holes_metric_takes_a_length_to_the_micrometre_the_document_holds() -> None:
    from fenolite.backends.altium.pcbrecords import to_units
    from fenolite.convert.to_kicad import metric

    assert metric(1_000_001) == 1_000_000 and metric(3_200_001) == 3_200_000
    assert metric(1_000_003) == 1_000_003  # 1.27 nm per half unit: 3 nm is another unit
    assert to_units(metric(2_000_001)) == to_units(2_000_001)
