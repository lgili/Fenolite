# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A straight Altium arc is kept (change c0485; capability design-conversion, "A straight Altium arc is
kept").

The source is authored for these tests: the board of ``tests/_altium_pour.py`` with one GND track, one GND
via and one GND arc record of radius 10 mm and a sweep of 0.001 degree, whose three points round onto one
line (a span of 175 nm), written by Fenolite's own writer with that record (``PcbDocSpec.arc_records``)."""

from __future__ import annotations

import dataclasses
import importlib.util
import re
from pathlib import Path

import pytest
from _altium_pour import FILENAME, Board, mm, track, via

from fenolite.api.board import read_board
from fenolite.api.conversion import ConversionResult, convert
from fenolite.backends.altium import pcbdoc
from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.adapter import units
from fenolite.backends.altium.lower import ARC_STRAIGHT, KeptStraightArc
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import ArcRecord
from fenolite.backends.kicad import boardcarrier
from fenolite.convert import straightarcs
from fenolite.model.board import Arc

pytestmark = pytest.mark.skipif(importlib.util.find_spec("pyclipper") is None, reason="needs the geo extra")

GEOMETRY = rec.ArcGeometry(4_000_000, 4_000_000, 3_937_008, 0.0, 0.001)


def _source(folder: Path) -> Path:
    first, last = (units.angle(a)[0] for a in (GEOMETRY.start, GEOMETRY.end))
    start, mid, end = units.arc_points(GEOMETRY.cx, GEOMETRY.cy, GEOMETRY.radius, first, last)
    arc = Arc(id="a1", start=start, mid=mid, end=end, width=mm(0.25), layer="F.Cu", net_id="GND")
    board = Board(zones=(), tracks=(track("t1", "GND", (5, 5), (10, 5)),), vias=(via("v1", "GND", 20, 15),))
    spec = dataclasses.replace(board.spec(), arcs=(arc,), arc_records={"a1": GEOMETRY})
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / FILENAME
    path.write_bytes(pcbdoc.write_pcbdoc_result(spec, filename=FILENAME, pour="outline").data)
    return path


def _write(result: ConversionResult, folder: Path) -> Path:
    for key, data in result.conversion.files.items():
        path = folder / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (found,) = [*folder.glob("*.kicad_pcb"), *folder.glob("*.PcbDoc")]
    return found


def _arcs(path: Path) -> list[tuple[int, int, int, float, float]]:
    arcs = [a for a in read_pcbdoc(path.read_bytes()).arcs if isinstance(a, ArcRecord)]
    return [(a.cx, a.cy, a.radius, a.start_angle, a.end_angle) for a in arcs]


def _counts(path: Path) -> tuple[int, int]:
    board = read_board(path).design.board
    assert board is not None
    return len(board.tracks), len(board.arcs)


def _changed(result: ConversionResult) -> set[str]:
    return {reason.reason for row in result.conversion.report.rows for reason in row.reasons if row.changed}


def test_source_arc_is_straight(tmp_path: Path) -> None:
    source = _source(tmp_path / "a")
    assert _counts(source) == (1, 1)
    (kept,) = straightarcs.found(read_board(source).design)
    assert kept.layer == "F.Cu" and kept.width == mm(0.25) and kept.net == "GND"


def test_carrier_round_trip() -> None:
    arcs = [KeptStraightArc("1,2,3,0x0.0p+0,0x1.0p+0", "F.Cu", 250_000, "GND"),
            KeptStraightArc("4,5,6,0x0.0p+0,0x1.0p+0", "B.Cu", 1, None)]  # fmt: skip
    text = straightarcs.carrier_text(arcs)
    assert sorted(straightarcs.read_carrier(text.encode("utf-8")), key=str) == sorted(arcs, key=str)
    assert straightarcs.read_carrier(b'{"schema":"other","arcs":[]}') == []
    assert straightarcs.read_carrier(b"not json") == []


def test_conversion_through_kicad_keeps_the_arc(tmp_path: Path) -> None:
    """Scenario "A straight arc comes back": the way back writes the source's arc record and reports no arc
    changed."""
    source = _source(tmp_path / "a")
    board = _write(convert(source, to="kicad", allow_lossy=True, verify=False), tmp_path / "k")
    carried = boardcarrier.carried(board.read_text(encoding="utf-8"))
    assert len(straightarcs.read_carrier(carried.get(straightarcs.PROPERTY))) == 1
    back = convert(board, to="altium", allow_lossy=True, verify=False)
    assert ARC_STRAIGHT not in _changed(back)
    document = _write(back, tmp_path / "b")
    assert _counts(document) == (1, 1)
    assert _arcs(document) == _arcs(source) and len(_arcs(source)) == 1


def test_a_track_with_new_uuid_comes_back_as_the_arc(tmp_path: Path) -> None:
    """Scenario "A script's track comes back as the arc": ``import --to python`` holds the arc as a track,
    and its build gives it another uuid; the record is found by the track's ends, layer, width and net."""
    source = _source(tmp_path / "a")
    board = _write(convert(source, to="kicad", allow_lossy=True, verify=False), tmp_path / "k")
    text = board.read_text(encoding="utf-8")
    arc = re.search(
        r"\t\(arc\n\t\t\(start ([^)]*)\)\n\t\t\(mid [^)]*\)\n\t\t\(end ([^)]*)\)\n(.*?)\n\t\)\n", text, re.S
    )
    assert arc is not None
    rest = re.sub(r'\(uuid "[^"]*"\)', '(uuid "00000000-0000-4000-8000-0000000000aa")', arc.group(3))
    segment = f"\t(segment\n\t\t(start {arc.group(1)})\n\t\t(end {arc.group(2)})\n{rest}\n\t)\n"
    board.write_text(text.replace(arc.group(0), segment), encoding="utf-8")
    assert _counts(board) == (2, 0)
    document = _write(convert(board, to="altium", allow_lossy=True, verify=False), tmp_path / "b")
    assert _counts(document) == (1, 1)
    assert _arcs(document) == _arcs(source)


def test_a_moved_track_stays_a_track(tmp_path: Path) -> None:
    """Scenario "An edited track stays a track": the KiCad arc's end moved by 1 um."""
    source = _source(tmp_path / "a")
    board = _write(convert(source, to="kicad", allow_lossy=True, verify=False), tmp_path / "k")
    text = board.read_text(encoding="utf-8")
    end = re.search(r"\(arc\n\t\t\(start [^)]*\)\n\t\t\(mid [^)]*\)\n\t\t\(end ([^ ]*) ([^)]*)\)", text)
    assert end is not None
    moved = f"{float(end.group(2)) - 0.001:.6f}"
    board.write_text(text.replace(end.group(0), end.group(0).replace(end.group(2), moved)), encoding="utf-8")
    back = convert(board, to="altium", allow_lossy=True, verify=False)
    assert _counts(_write(back, tmp_path / "b")) == (2, 0)
