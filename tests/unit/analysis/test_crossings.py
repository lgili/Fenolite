# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``analysis.crossings`` (change c0199; capability board-analyses, "Barrier crossings"), on the authored
benches of ``tests/_crossbench.py``, with ways counted by hand."""

from __future__ import annotations

import dataclasses

import pytest
from _crossbench import CLEARANCE, GAP_WAY, PITCH, ROW, WIDTH, row

from fenolite.analysis.boundary import board_boundary
from fenolite.analysis.crossings import CrossingReport, Cut, analyze_crossings, fits
from fenolite.backends.kicad.frame import board_pads
from fenolite.core.coords import Point
from fenolite.core.evidence import Level
from fenolite.model.board import Track
from fenolite.model.design import Design

MM = 1_000_000


def run(design: Design, *cuts: Cut, **options: int) -> CrossingReport:
    board = design.board
    assert board is not None
    return analyze_crossings(
        design, pads=board_pads(design), cuts=cuts or (ROW,), boundary=board_boundary(board), **options
    )


def test_fits_counted_by_hand() -> None:
    assert fits(GAP_WAY, WIDTH, CLEARANCE) == 2
    assert fits(WIDTH, WIDTH, CLEARANCE) == 1 and fits(WIDTH - 1, WIDTH, CLEARANCE) == 0
    assert fits(2 * WIDTH + CLEARANCE, WIDTH, CLEARANCE) == 2


def test_row_ways_counted_by_hand() -> None:
    """Scenario "Ways counted by hand": seven gaps of two tracks on each layer."""
    report = run(row(), width=WIDTH)
    (found,) = report.rows
    assert found.length == 7 * PITCH and found.clearance == CLEARANCE and found.width == WIDTH
    assert [entry.layer for entry in found.layers] == ["F.Cu", "B.Cu"]
    for entry in found.layers:
        assert len(entry.ways) == 7 and [way.tracks for way in entry.ways] == [2] * 7
        assert all(GAP_WAY - 4 <= way.length <= GAP_WAY for way in entry.ways)
        first = entry.ways[0]
        assert abs(first.start - (MM // 2 + CLEARANCE)) <= 2 and first.a.y == ROW.a.y
        assert {o.kind for o in entry.obstacles} == {"pad"}
    assert found.supply == 28 and report.issues == () and report.evidence.level is Level.INFERRED


def test_more_nets_than_ways() -> None:
    """Scenario "More nets than ways": 20 open connections, 14 tracks on the top layer alone."""
    report = run(row(links=20, top_only=True), width=WIDTH)
    (found,) = report.rows
    bottom = next(entry for entry in found.layers if entry.layer == "B.Cu")
    assert bottom.ways == () and {o.kind for o in bottom.obstacles} >= {"area"}
    assert found.supply == 14 and found.open == 20 and len(found.demand) == 20
    assert [found_issue.code for found_issue in report.issues] == ["analysis.crossings-short"]
    message = report.issues[0].message
    assert "20" in message and "14" in message


def test_routed_copper_is_demand_and_obstacle() -> None:
    design = row(links=1)
    board = design.board
    assert board is not None
    net_id = next(net.id for net in design.circuit.nets if net.name == "L01")
    x = 10 * MM + PITCH // 2  # the middle of the first gap
    track = Track(
        id="trk_x", start=Point(x, 10 * MM), end=Point(x, 30 * MM), width=WIDTH, layer="F.Cu", net_id=net_id
    )
    design = dataclasses.replace(design, board=dataclasses.replace(board, tracks=(track,)))
    (found,) = run(design, width=WIDTH).rows
    assert [(d.net, d.open, d.routed) for d in found.demand] == [("L01", 0, 1)]
    top = found.layers[0]
    # the track and its clearance split the first gap into two ways too short for a track
    assert any(o.kind == "track" for o in top.obstacles) and top.tracks == 12 and len(top.ways) == 8


def test_edge_and_classes() -> None:
    """A cut that leaves the board is blocked outside it; without --width the classes give none."""
    design = row()
    long_cut = Cut("long", Point(-5 * MM, 5 * MM), Point(65 * MM, 5 * MM))
    (found,) = run(design, long_cut, width=WIDTH).rows
    (way,) = found.layers[0].ways  # the cut runs from x -5 mm: the board spans 5 mm to 65 mm along it
    assert abs(way.start - (5 * MM + CLEARANCE)) <= 2 and abs(way.end - (65 * MM - CLEARANCE)) <= 2
    assert found.layers[1].ways == found.layers[0].ways
    report = run(design)
    assert report.rows[0].layers == () and [i.code for i in report.issues] == ["analysis.input-missing"]


@pytest.mark.parametrize("clearance", [CLEARANCE, 3 * CLEARANCE])
def test_clearance_option(clearance: int) -> None:
    (found,) = run(row(), width=WIDTH, clearance=clearance).rows
    assert found.clearance == clearance
    expected = fits(PITCH - MM - 2 * clearance, WIDTH, clearance)
    assert [way.tracks for way in found.layers[0].ways] == [expected] * 7


def test_without_pads_unverified() -> None:
    design = row()
    assert analyze_crossings(design, pads=None, cuts=(ROW,), width=WIDTH).evidence.level is Level.UNVERIFIED
