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
