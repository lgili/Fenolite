# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board cut-outs, notches and polygon cut-outs (change c0497, D3 and D4), on the authored ``drawn`` board
(``board_ops``). The gates are opened by the test: ``edit.GATES`` stays off."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import Path

from fenolite.backends.altium import edit
from fenolite.backends.altium.edit import drawing
from fenolite.backends.altium.edit import records as rec
from fenolite.backends.altium.edit.state import State
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RegionRecord
from tests.unit.backends.altium.edit.board_ops import MECHANICAL_1
from tests.unit.backends.altium.edit.conftest import OPEN, mm

INNER = [(mm(14), mm(10)), (mm(18), mm(10)), (mm(18), mm(12)), (mm(14), mm(12))]
ACROSS = [(mm(38), mm(10)), (mm(42), mm(10)), (mm(42), mm(14)), (mm(38), mm(14))]


def _commit(path: Path, build: Callable[[edit.Session], object]) -> tuple[edit.Receipt, bytes]:
    session = edit.open(path, gates=OPEN)
    assert isinstance(session, edit.Session)
    build(session)
    out = path.with_name("out.PcbDoc")
    receipt = session.commit(out, backup=False)
    return receipt, out.read_bytes() if receipt.written else b""


def _added(before: bytes, after: bytes, storage: str) -> list[bytes]:
    return list((Counter(State.of(after).get(storage)) - Counter(State.of(before).get(storage))).elements())


def test_inner_cutout(ops_board: Callable[[str], Path]) -> None:
    path = ops_board("drawn")
    before = path.read_bytes()
    receipt, after = _commit(path, lambda s: s.add_board_cutout(INNER, drawing="Mechanical 1"))
    assert receipt.written, receipt.issues
    for storage in ("Regions6", "ShapeBasedRegions6"):
        [new] = _added(before, after, storage)
        keys = rec.region_keys(new)
        assert keys["ISBOARDCUTOUT"] == "TRUE" and keys.get("KIND", "0") == "0" and new[1 + 4] == 56
    assert State.of(after).get("Board6") == State.of(before).get("Board6")
    # the redraw draws the split outline edge as one track: 9 tracks become 12, four along the new ring
    tracks = [e for _, _, e in drawing.drawn_edges(State.of(after), MECHANICAL_1) if e.centre is None]
    assert len(tracks) == 12 and sum(e.what == "drawn track" for e in tracks) == 12
    assert drawing.check_pcbdoc(after) == []


def test_crossing_and_notch(ops_board: Callable[[str], Path]) -> None:
    path = ops_board("drawn")
    before = path.read_bytes()
    receipt, _ = _commit(path, lambda s: s.add_board_cutout(ACROSS))
    assert [i.code for i in receipt.issues] == [
        "altium.edit.assertion"
    ] and "board outline" in receipt.issues[0].message
    receipt, after = _commit(path, lambda s: s.add_board_cutout(ACROSS, notch=True))
    assert receipt.written, receipt.issues
    outline = read_pcbdoc(after).board.outline
    assert len(outline) == 5 + 4 + 1 and sum(v.kind != 0 for v in outline) == 1
    assert _added(before, after, "Regions6") == [] and _added(before, after, "ShapeBasedRegions6") == []
    assert len(drawing.compare(State.of(after), MECHANICAL_1)) > 0  # the drawing is stale until redrawn


def test_notch_into_board_regions(board_ops: dict[str, bytes]) -> None:
    """A document that holds ``BoardRegions`` (Fenolite's writer writes none) takes the notched outline there
    with its arc as chords."""
    from fenolite.backends.altium.edit import ops
    from fenolite.backends.altium.pcbrecords import region_record

    state = State.of(board_ops["drawn"])
    ring = drawing.polygonised(drawing.outline_vertices(state))[0]
    state.streams["BoardRegions/Data"] = b""
    state.records["BoardRegions"] = ([region_record(56, ring)], b"")
    ops.add_board_cutout(state, ACROSS, notch=True)
    [held] = state.typed("BoardRegions")
    assert isinstance(held, RegionRecord)
    outline = drawing.polygonised(drawing.outline_vertices(state))[0]
    assert [(round(v.x), round(v.y)) for v in held.outline] == outline and len(outline) > 9


def test_polygon_cutout(ops_board: Callable[[str], Path]) -> None:
    path = ops_board("drawn")
    before = path.read_bytes()
    ring = [(mm(20), mm(13)), (mm(22), mm(13)), (mm(22), mm(15)), (mm(20), mm(15))]
    session = edit.open(path, gates=OPEN)
    assert isinstance(session, edit.Session)
    receipt = session.add_polygon_cutout(ring, layer="Bottom Layer").commit(
        path.with_name("out.PcbDoc"), backup=False
    )
    assert receipt.written, receipt.issues
    assert session.stale_pours == ["GND"]
    after = path.with_name("out.PcbDoc").read_bytes()
    [new] = _added(before, after, "Regions6")
    assert rec.region_keys(new)["KIND"] == "1" and rec.prefix_of(new)[0] == 32
    poured = [
        r for r in read_pcbdoc(after).regions if isinstance(r, RegionRecord) and r.prefix.polygon is not None
    ]
    assert [r.prefix.polygon for r in poured] == [1]  # VIN keeps its piece, GND loses its own


def test_cutout_gate(ops_board: Callable[[str], Path]) -> None:
    path = ops_board("drawn")
    session = edit.open(path)
    assert isinstance(session, edit.Session)
    out = path.with_name("out.PcbDoc")
    receipt = session.add_board_cutout(INNER).commit(out)
    assert [i.code for i in receipt.issues] == ["altium.edit.gate"]
    assert "cutout" in receipt.issues[0].message and "H-A-EDIT-CUTOUT" in receipt.issues[0].message
    assert not out.exists() and not edit.GATES["cutout"]
