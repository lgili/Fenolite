# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``analysis.ties`` (change c0198; capability board-analyses, "Ground ties" and "Sense nets and isolation
islands"), on the authored benches of ``tests/_groundties.py``."""

from __future__ import annotations

import dataclasses

from _groundties import T1, T2, V1, ground, isolated, pads, sense, split_nets

from fenolite.analysis.ties import IslandReport, Tie, TieReport, analyze_ties, isolation_islands
from fenolite.core.coords import Point
from fenolite.core.evidence import Level

MM = 1_000_000

DOMAINS = {"PWR": ("Q*",), "CTL": ("U*",)}


def codes(report: TieReport | IslandReport) -> list[str]:
    return [found.code for found in report.issues]


def test_single_tie_splits_the_net() -> None:
    """Scenario "A single tie splits the net"."""
    design = ground()
    report = analyze_ties(design, pads=pads(design), ties=[Tie.of_items([T1])], domains=DOMAINS)
    (row,) = report.rows
    assert row.split and row.groups == (("Q1-1", "Q2-1"), ("U1-1",))
    assert [item.id for item in row.removed] == [T1] and row.zones == "filled" and row.nets == ("GND",)
    assert report.issues == () and report.evidence.level is Level.INFERRED
    assert report.summary == {"ties": 1, "split": 1, "sense": 0, "shared": 0}


def test_parallel_tie_through_a_via() -> None:
    """Scenario "A parallel tie through a via": the path names the via."""
    design = ground(via=True)
    report = analyze_ties(design, pads=pads(design), ties=[Tie.of_items([T1])])
    (row,) = report.rows
    assert not row.split and row.groups == (("Q1-1", "Q2-1", "U1-1"),)
    assert codes(report) == ["analysis.tie-parallel"] and report.issues[0].severity == "error"
    kinds = [item.kind for item in row.path]
    assert kinds == ["fill", "via", "track", "via", "fill"] and row.path[1].id == V1
    assert V1 in report.issues[0].message


def test_tie_of_several_items() -> None:
    """Naming the parallel joint too splits the net again."""
    design = ground(via=True)
    report = analyze_ties(design, pads=pads(design), ties=[Tie.of_items([T1, V1])])
    assert report.rows[0].split and report.issues == ()


def test_removal_by_area_is_not_used() -> None:
    """Scenario "Removal by area is not used": ``t2`` crosses the box of ``t1`` and stays."""
    design = ground()
    board = design.board
    assert board is not None
    t1, t2 = (track for track in board.tracks if track.id in (T1, T2))
    assert min(t1.start.x, t1.end.x) <= t2.end.x <= max(t1.start.x, t1.end.x)
    assert min(t1.start.y, t1.end.y) <= t2.end.y <= max(t1.start.y, t1.end.y)
    (row,) = analyze_ties(design, pads=pads(design), ties=[Tie.of_items([T1])]).rows
    assert T2 not in {item.id for item in row.removed}
    assert "Q2-1" in row.groups[0] and "Q1-1" in row.groups[0]


def test_extra_joint_between_domains() -> None:
    """A control pad in the power area is ``analysis.tie-extra``, naming the pad."""
    design = ground(intruder=True)
    report = analyze_ties(design, pads=pads(design), ties=[Tie.of_items([T1])], domains=DOMAINS)
    (row,) = report.rows
    assert row.split and row.extra == ("U2-1",)
    assert codes(report) == ["analysis.tie-extra"] and report.issues[0].where == "U2-1"


def test_tie_by_part() -> None:
    """``--tie REF``: the net-tie part's pads are removed, and its sides are its nets."""
    design = split_nets()
    report = analyze_ties(design, pads=pads(design), ties=[Tie.of_part("NT1")])
    (row,) = report.rows
    assert row.split and row.groups == (("Q1-1",), ("U1-1",)) and row.nets == ("GND_C", "GND_P")
    assert sorted(item.where for item in row.removed) == ["NT1-1", "NT1-2"] and report.issues == ()


def test_unmatched_and_dangling() -> None:
    """A name that matches nothing is ``analysis.tie-unmatched``; a stub inside one pour joins nothing."""
    design = ground()
    board = design.board
    assert board is not None
    stub = dataclasses.replace(
        board.tracks[0], id="trk_stub", start=Point(5 * MM, 5 * MM), end=Point(6 * MM, 5 * MM)
    )
    design = dataclasses.replace(design, board=dataclasses.replace(board, tracks=(*board.tracks, stub)))
    report = analyze_ties(
        design,
        pads=pads(design),
        ties=[Tie.of_items(["nothing"]), Tie.of_part("X9"), Tie.of_items(["trk_stub"])],
    )
    assert codes(report) == ["analysis.tie-unmatched", "analysis.tie-unmatched", "analysis.tie-dangling"]


def test_unfilled_zones_are_named() -> None:
    design = ground(fill=False)
    report = analyze_ties(design, pads=pads(design), ties=[Tie.of_items([T1])])
    assert report.rows[0].zones == "unfilled"
    assert "analysis.input-missing" in codes(report)


def test_without_pads_unverified() -> None:
    report = analyze_ties(ground(), pads=None, ties=[Tie.of_items([T1])])
    assert report.evidence.level is Level.UNVERIFIED


def test_sense_track_that_leaves_from_a_pour() -> None:
    """Scenario "A sense track that leaves from a pour"."""
    design = sense()
    report = analyze_ties(design, pads=pads(design), sense=["ISENSE_P", "ISENSE_N"])
    assert codes(report) == ["analysis.sense-shared"]
    message = report.issues[0].message
    assert "ISENSE_P" in message and "DC_BUS" in message and "track" in message and "fill" in message
    rows = {row.net: row for row in report.sense}
    assert [item.kind for item in rows["ISENSE_P"].shared] == ["fill"] and rows["ISENSE_N"].shared == ()


def test_sense_through_a_net_tie_is_clean() -> None:
    """The sense pad of a net-tie group may touch its load pad."""
    design = sense(from_pour=False)
    report = analyze_ties(design, pads=pads(design), sense=["ISENSE_P", "ISENSE_N", "NOPE"])
    assert codes(report) == ["analysis.tie-unmatched"]


def test_islands_across_an_isolator() -> None:
    """Scenario "Islands across an isolator"."""
    report = isolation_islands(isolated(), barriers=["U5"])
    assert [(island.nets, island.barriers) for island in report.islands] == [
        (("A1", "A2"), ("U5",)),
        (("B1", "B2"), ("U5",)),
    ]
    joined = isolation_islands(isolated(), barriers=["Z1"])
    assert [island.nets for island in joined.islands] == [("A1", "A2", "B1", "B2")]
    assert codes(joined) == ["analysis.tie-unmatched"]
