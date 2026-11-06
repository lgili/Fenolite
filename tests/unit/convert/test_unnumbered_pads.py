# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pads without a number stay in their footprint through KiCad to Altium (change c0433)."""

import dataclasses
from pathlib import Path

from _convert import source_of, two_layer

from fenolite.api.conversion import verify_conversion
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.convert import convert_project
from fenolite.core.coords import Point, Size
from fenolite.model.design import Design
from fenolite.model.library import Library

NM = 3
"""The rounding of the written unit (2.54 nm), as the conversion profile allows."""


def _with_unnumbered_pads() -> tuple[Design, str]:
    """The two-layer board whose first footprint gains an exposed copper pad on the net of its pad 1 and a
    mechanical non-plated hole pad, both without a number, at distinct places."""
    design = two_layer()
    assert design.board is not None
    footprint = design.board.footprints[0]
    first = footprint.pads[0]
    exposed = dataclasses.replace(
        first, id="pad-exposed", number="", position=Point(0, 2_000_000), size=Size(1_200_000, 1_200_000)
    )
    hole = dataclasses.replace(
        first, id="pad-hole", number="", net_id=None, kind="np_thru_hole", shape="circle", drill=1_000_000,
        size=Size(1_000_000, 1_000_000), position=Point(0, -2_000_000),
        layers=("F.Cu", "B.Cu", "F.Mask", "B.Mask"),
    )  # fmt: skip
    footprint = dataclasses.replace(footprint, pads=(*footprint.pads, exposed, hole))
    board = dataclasses.replace(design.board, footprints=(footprint, *design.board.footprints[1:]))
    ref = next(c.ref for c in design.circuit.components if c.id == footprint.component_id)
    return dataclasses.replace(design, board=board), ref


def _near(a: Point, b: Point) -> bool:
    return abs(a.x - b.x) <= NM and abs(a.y - b.y) <= NM


def test_two_unnumbered_pads_are_written_in_their_footprint(tmp_path: Path) -> None:
    design, ref = _with_unnumbered_pads()
    assert design.board is not None
    source = design.board.footprints[0]
    conversion = convert_project(source_of(design), to="altium", allow_lossy=True)
    row = next(row for row in conversion.report.rows if row.kind == "pad")
    assert (row.source, row.written, row.changed, row.lost) == (6, 6, 0, 0)
    for name, data in conversion.files.items():
        (tmp_path / name).write_bytes(data)
    backend = AltiumBackend()
    target = backend.read(tmp_path / conversion.read_back).design
    assert target.board is not None
    assert sum(len(fp.pads) for fp in target.board.footprints) == 6
    component = next(c for c in target.circuit.components if c.ref == ref)
    read = next(fp for fp in target.board.footprints if fp.component_id == component.id)
    assert sorted(p.number for p in read.pads) == ["", "", "1", "2"]
    unnumbered = sorted((p for p in read.pads if not p.number), key=lambda p: p.position.y)
    hole, exposed = unnumbered
    assert _near(hole.position, Point(0, -2_000_000)) and hole.kind == "np_thru_hole" and hole.net_id is None
    assert _near(exposed.position, Point(0, 2_000_000)) and exposed.kind == "smd"
    nets = {n.id: n.name for n in target.circuit.nets}
    source_nets = {n.id: n.name for n in design.circuit.nets}
    assert nets[exposed.net_id or ""] == source_nets[source.pads[0].net_id or ""]
    assert not target.board.holes
    library = backend.read(tmp_path / "two_layer.PcbLib").content
    assert isinstance(library, Library)
    pattern = read.lib_ref.rpartition(":")[2]
    library_footprint = next(fp for fp in library.footprints if fp.name == pattern)
    assert sorted(p.number for p in library_footprint.pads) == ["", "", "1", "2"]


def test_unnumbered_pads_leave_no_equivalence_difference() -> None:
    """The comparison of the conversion finds no pad missing from the footprint and no anonymous
    footprint: the pads were neither dropped nor moved out of their component."""
    design, _ = _with_unnumbered_pads()
    result = verify_conversion(convert_project(source_of(design), to="altium", allow_lossy=True))
    kinds = {e.difference.kind for e in result.explained} | {d.kind for d in result.unexplained}
    assert not kinds & {"pad-missing", "ref-ambiguous"}
    assert result.unexplained == ()
