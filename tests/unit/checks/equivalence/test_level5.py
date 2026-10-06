# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Level 5 compares routing per net (capability design-equivalence, "Level 5 compares routing per net";
change c0089; ``H-G-EQ-L5``)."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

import pytest
from _cases import renamed_nets, reversed_order, two_layer
from _routes import MM, board, mm, parts, routed, track, via, with_board, with_track, without, zone

from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.checks.equivalence import (
    Difference,
    LevelResult,
    Rule,
    Tolerances,
    compare_designs,
    difference_issues,
    max_level,
)
from fenolite.checks.equivalence.model import EXACT
from fenolite.checks.equivalence.routing import (
    DEFAULT_RULE,
    NOTICES,
    NetPairing,
    Step,
    level_routing,
    pair_nets,
)
from fenolite.core.coords import Point
from fenolite.model.board import Layer
from fenolite.model.design import Design

REFS = ("J1", "J2", "R1", "R2")


def level5(a: Design, b: Design, tolerances: Tolerances = EXACT) -> LevelResult:
    return compare_designs(a, b, level=5, tolerances=tolerances).levels[-1]


def kinds(result: LevelResult) -> list[tuple[str, str]]:
    return [(d.kind, d.where) for d in result.differences]


# --- copies ----------------------------------------------------------------------------------------


def test_a_faithful_copy() -> None:
    """The routed two-layer board, and a copy written and read again by the KiCad backend."""
    source = two_layer()
    copy = read_board(write_board(source, target=10).text, file="copy.kicad_pcb")
    report = compare_designs(source, copy, level=5)
    result = report.levels[-1]
    assert report.equivalent and [level.level for level in report.levels] == [1, 2, 3, 4, 5]
    assert (result.name, result.differences, result.notices, result.compared) == ("routing", (), (), 3)
    assert result.summary["nets"] == 3 and result.summary["vias"] == {"a": 1, "b": 1}
    assert result.summary["length"]["a"] == result.summary["length"]["b"] > 0


def test_the_same_board_under_other_names() -> None:
    """Net names, net ids, layer names and the order of the items take no part."""
    found = routed()
    other = reversed_order(renamed_nets(found))
    ids = {
        old.id: new.id for old, new in zip(found.circuit.nets, renamed_nets(found).circuit.nets, strict=True)
    }
    names = {"Top": "F", "Mid": "In", "Bottom": "B", "Mask": "Mask"}
    held = board(other)
    other = with_board(
        other,
        layers=tuple(dataclasses.replace(la, name=names[la.name]) for la in held.layers),
        tracks=tuple(
            dataclasses.replace(t, net_id=ids[t.net_id or ""], layer=names[t.layer]) for t in held.tracks
        ),
        arcs=tuple(
            dataclasses.replace(a, net_id=ids[a.net_id or ""], layer=names[a.layer]) for a in held.arcs
        ),
        vias=tuple(
            dataclasses.replace(v, net_id=ids[v.net_id or ""], layers=tuple(names[n] for n in v.layers))
            for v in reversed(held.vias)
        ),
        footprints=tuple(
            dataclasses.replace(
                f,
                pads=tuple(dataclasses.replace(p, layers=tuple(names[n] for n in p.layers)) for p in f.pads),
            )
            for f in held.footprints
        ),
    )
    result = level5(found, other)
    assert (result.differences, result.notices, result.compared) == ((), (), 4)
    assert result.summary == {
        "nets": 4,
        "pieces": {"a": 4, "b": 4},
        "vias": {"a": 3, "b": 3},
        "length": {"a": 60_570_796, "b": 60_570_796},
        "unjudged": 0,
        "nets_unpaired": {"a": 0, "b": 0},
        "zones_unfilled": {"a": 0, "b": 0},
        "copper_no_net": {"a": 0, "b": 0},
        "unshaped": {"a": 0, "b": 0},
    }


def test_a_board_moved_as_a_whole() -> None:
    """Routing has no frame: a board moved by one vector has the same pieces."""
    found = routed()
    dx, dy = 7 * MM, -3 * MM
    held = board(found)

    def moved(point: Point) -> Point:
        return Point(point.x + dx, point.y + dy)

    other = with_board(
        found,
        footprints=tuple(dataclasses.replace(f, position=moved(f.position)) for f in held.footprints),
        tracks=tuple(dataclasses.replace(t, start=moved(t.start), end=moved(t.end)) for t in held.tracks),
        arcs=tuple(
            dataclasses.replace(a, start=moved(a.start), mid=moved(a.mid), end=moved(a.end))
            for a in held.arcs
        ),
        vias=tuple(dataclasses.replace(v, position=moved(v.position)) for v in held.vias),
    )
    assert level5(found, other).differences == ()


# --- the five planted edits ------------------------------------------------------------------------

PLANTED: tuple[tuple[str, Callable[[Design], Design], str, str, str, str], ...] = (
    (
        "a track removed",
        lambda d: without(d, "a-top"),
        "route-connectivity", "A:J1-1", "J1-1,J2-1", "J1-1 | J2-1",
    ),
    (
        "a via removed",
        lambda d: without(d, "b-2"),
        "route-vias", "B:J1-2,J2-2", "top-bottom=2", "top-bottom=1",
    ),
    (
        "a track moved to another layer",
        lambda d: with_track(d, "b-bottom", layer="Mid"),
        "route-length", "B:J1-2,J2-2", "top=20000000,inner1=0,bottom=10000000",
        "top=20000000,inner1=10000000,bottom=0",
    ),
    (
        "a connection opened",
        lambda d: with_track(d, "c-top", end=mm(9, 12)),
        "route-connectivity", "C:R1-1", "R1-1,R2-1", "R1-1 | R2-1",
    ),
    (
        "a net's copper deleted",
        lambda d: without(d, "d-1", "d-2", "d"),
        "route-missing", "D", "routed", "",
    ),
)  # fmt: skip


@pytest.mark.parametrize("case", PLANTED, ids=[case[0] for case in PLANTED])
def test_planted(case: tuple[str, Callable[[Design], Design], str, str, str, str]) -> None:
    """``H-G-EQ-L5``: each edit gives one difference, of its kind, that names the net."""
    _, edit, kind, where, value_a, value_b = case
    found = routed()
    report = compare_designs(found, edit(found), level=5)
    assert [len(level.differences) for level in report.levels] == [0, 0, 0, 0, 1]
    result = report.levels[-1]
    assert result.differences == (Difference(5, kind, where, result.differences[0].field, value_a, value_b),)
    assert result.notices == () and not report.equivalent
    issues = difference_issues(report)
    assert [(i.code, i.severity, i.where) for i in issues] == [(f"equiv.{kind}", "error", where)]
    back = compare_designs(edit(found), found, level=5).levels[-1]
    assert [(d.kind, d.a, d.b) for d in back.differences] == [(kind, value_b, value_a)]


def test_planted_in_order() -> None:
    found = routed()
    codes = [f"equiv.{level5(found, case[1](found)).differences[0].kind}" for case in PLANTED]
    assert codes == [
        "equiv.route-connectivity",
        "equiv.route-vias",
        "equiv.route-length",
        "equiv.route-connectivity",
        "equiv.route-missing",
    ]


def test_each_fault_once_and_sorted() -> None:
    """A net that fails on connectivity gives no via or length difference; the output is sorted."""
    found = routed()
    other = without(without(with_track(found, "c-top", end=mm(9, 12)), "a-top", "a"), "b-2")
    result = level5(found, other)
    assert kinds(result) == [
        ("route-connectivity", "A:J1-1"),
        ("route-vias", "B:J1-2,J2-2"),
        ("route-connectivity", "C:R1-1"),
    ]
    assert level5(found, reversed_order(other)) == result


# --- tolerances ------------------------------------------------------------------------------------


def test_length_tolerances() -> None:
    found = routed()
    longer = with_track(found, "c-top", start=mm(9, 10 - 0.0001))  # 100 nm more on 5 mm: 20 ppm
    assert kinds(level5(found, longer)) == [("route-length", "C:R1-1,R2-1")]
    assert kinds(level5(found, longer, Tolerances(length_nm=99))) == [("route-length", "C:R1-1,R2-1")]
    assert kinds(level5(found, longer, Tolerances(length_nm=100))) == []
    assert kinds(level5(found, longer, Tolerances(length_ppm=19))) == [("route-length", "C:R1-1,R2-1")]
    assert kinds(level5(found, longer, Tolerances(length_ppm=20))) == []
    assert kinds(level5(found, longer, Tolerances(length_nm=5, length_ppm=20))) == []
    with pytest.raises(ValueError, match="length_ppm"):
        Tolerances(length_ppm=-1)


def test_the_tolerance_is_per_span() -> None:
    """A length moved from one layer to another is not hidden by an equal total."""
    found = routed()
    other = with_track(found, "b-bottom", layer="Mid")
    assert kinds(level5(found, other, Tolerances(length_nm=9 * MM))) == [("route-length", "B:J1-2,J2-2")]
    assert kinds(level5(found, other, Tolerances(length_nm=10 * MM))) == []


# --- notices ---------------------------------------------------------------------------------------


def test_stub_is_a_warning_that_fails_nothing() -> None:
    found = routed()
    stub = track(found, "stub", "A", mm(30, 30), mm(32, 30))
    lone = via(found, "lone", "A", mm(40, 40))
    other = with_board(found, tracks=(*board(found).tracks, stub), vias=(*board(found).vias, lone))
    report = compare_designs(found, other, level=5)
    result = report.levels[-1]
    assert report.equivalent and result.differences == ()
    assert result.notices == (
        Difference(5, "route-stub", "A", "stubs", "pieces=0,length=0", "pieces=2,length=2000000"),
    )
    assert [(i.code, i.severity, i.where) for i in difference_issues(report)] == [
        ("equiv.route-stub", "warning", "A")
    ]
    assert level5(other, other).notices == ()
    shorter = with_board(other, tracks=(*board(found).tracks, dataclasses.replace(stub, end=mm(31, 30))))
    assert [n.kind for n in level5(other, shorter).notices] == ["route-stub"]
    assert level5(other, shorter, Tolerances(length_nm=MM)).notices == ()


def test_unfilled_zone_leaves_a_net_unjudged() -> None:
    """``C`` is joined by a zone fill on one side and holds the same zone without a fill on the other:
    nothing is said about it but that it was not judged."""
    found = without(routed(), "c-top")
    ring = (mm(8, 9), mm(10, 9), mm(10, 16), mm(8, 16))
    stitch = via(found, "stitch", "C", mm(9, 12))
    filled = with_board(
        found, zones=(zone(found, "z", "C", "Top", ring, filled=True),), vias=(*board(found).vias, stitch)
    )
    empty = with_board(
        found, zones=(zone(found, "z", "C", "Top", ring, filled=False),), vias=(*board(found).vias, stitch)
    )
    report = compare_designs(filled, empty, level=5)
    result = report.levels[-1]
    assert report.equivalent and result.differences == ()
    assert result.notices == (Difference(5, "route-unjudged", "C", "zones", "", "pieces=3"),)
    assert result.summary["unjudged"] == 1 and result.summary["zones_unfilled"] == {"a": 0, "b": 1}
    assert [(i.code, i.severity) for i in difference_issues(report)] == [("equiv.route-unjudged", "info")]
    # with the fill on both sides the net is judged, and the stitching via is part of its piece
    assert level5(filled, filled).notices == () and level5(filled, filled).summary["unjudged"] == 0
    # a zone without a fill on a net that its tracks join anyway changes nothing
    routed_too = with_board(routed(), zones=(zone(found, "z", "C", "Top", ring, filled=False),))
    assert level5(routed(), routed_too).notices == ()
    assert kinds(level5(routed_too, without(routed_too, "c-top"))) == []
    assert [n.kind for n in level5(routed_too, without(routed_too, "c-top")).notices] == ["route-unjudged"]


def test_a_rule_excludes_a_difference_and_a_notice() -> None:
    found = routed()
    stub = track(found, "stub", "A", mm(30, 30), mm(32, 30))
    other = with_board(without(found, "b-2"), tracks=(*board(found).tracks, stub))
    rules = (
        Rule("vias", 5, "route-vias", "B:*", "undecided", "a via less", "H-G-EQ-L5"),
        Rule("stub", 5, "route-stub", "A", "undecided", "a stub more", "H-G-EQ-L5"),
    )
    report = compare_designs(found, other, level=5, rules=rules)
    result = report.levels[-1]
    assert report.equivalent and result.differences == () and result.notices == ()
    assert [(e.rule_id, e.difference.kind) for e in result.excluded] == [
        ("vias", "route-vias"),
        ("stub", "route-stub"),
    ]
    assert [i.code for i in difference_issues(report)] == ["equiv.excluded", "equiv.excluded"]


# --- pairing and scope -----------------------------------------------------------------------------


def test_pairing_follows_level_2() -> None:
    found = routed()
    pairing = pair_nets(found, renamed_nets(found), REFS)
    assert len(pairing.pairs) == 4 and len(pairing.elements) == 8
    names_a = {n.id: n.name for n in found.circuit.nets}
    names_b = {n.id: n.name for n in renamed_nets(found).circuit.nets}
    assert sorted((names_a[a], names_b[b]) for a, b in pairing.pairs) == [
        ("A", "N0"), ("B", "N1"), ("C", "N2"), ("D", "N3"),
    ]  # fmt: skip
    assert pair_nets(found, found, ("J1", "J2")).elements == {"J1-1", "J1-2", "J2-1", "J2-2"}
    assert len(pair_nets(found, found, ("J1", "J2")).pairs) == 2
    assert pair_nets(found, found, ()) == NetPairing()


def test_a_net_that_level_2_reports_is_not_compared_again() -> None:
    """``R2-1`` moved from ``C`` to ``D``: level 2 says so, and level 5 leaves both nets alone."""
    found = routed()
    ids = {n.name: n.id for n in found.circuit.nets}
    held = board(found)
    footprints = tuple(
        dataclasses.replace(
            f,
            pads=tuple(
                dataclasses.replace(p, net_id=ids["D"])
                if p.net_id == ids["C"] and f.position == mm(10, 15)
                else p
                for p in f.pads
            ),
        )
        for f in held.footprints
    )
    other = with_board(found, footprints=footprints)
    report = compare_designs(found, other, level=5)
    assert [d.kind for d in report.levels[1].differences] == ["net"]
    result = report.levels[-1]
    assert result.differences == () and result.compared == 2
    assert result.summary["nets_unpaired"] == {"a": 2, "b": 2}


def test_components_out_of_scope_give_no_pad() -> None:
    """With ``R2`` ignored, ``C`` joins ``R1-1`` to copper only; cutting the track short of ``R2`` is then
    a change of length, not of connectivity."""
    found = routed()
    other = with_track(found, "c-top", end=mm(9, 12))
    scoped = compare_designs(found, other, level=5, ignore_refs=("R2",)).levels[-1]
    assert kinds(scoped) == [("route-length", "C:R1-1")]


def test_unrouted_nets_are_not_compared() -> None:
    found = routed()
    result = level5(without(found, "c-top"), without(found, "c-top"))
    assert result.compared == 3 and result.differences == ()


# --- levels ----------------------------------------------------------------------------------------


def test_max_level() -> None:
    found, bare = routed(), parts()
    assert (max_level(found, found), max_level(found, bare), max_level(bare, bare)) == (5, 4, 4)
    only_via = with_board(bare, vias=(via(bare, "v", "A", mm(3, 3)),))
    assert max_level(only_via, found) == 5
    assert max_level(found, dataclasses.replace(found, board=None)) == 2
    with pytest.raises(
        ValueError, match=r"level 5 needs a track, an arc or a via on both sides, and side b holds"
    ):
        compare_designs(found, bare, level=5)
    with pytest.raises(ValueError, match=r"side a and b holds none; the highest level available is 4"):
        compare_designs(bare, bare, level=5)
    with pytest.raises(ValueError, match="level is one of 1, 2, 3, 4, 5"):
        compare_designs(found, found, level=6)
    assert len(compare_designs(found, bare, level=4).levels) == 4


def test_single_copper_layer_board() -> None:
    found = routed()
    layers = tuple(la for la in board(found).layers if la.name in ("Top", "Mask"))
    assert all(isinstance(la, Layer) for la in layers)
    one = with_board(without(found, "a-bottom", "b-bottom"), layers=layers)
    assert level5(one, one).differences == ()


# --- the rule is one table -------------------------------------------------------------------------


def test_the_rule_is_one_table() -> None:
    """The kinds, their order and which of them end the judgement of a net are ``DEFAULT_RULE``; another
    rule is another table, given to ``level_routing``."""
    assert [(step.kind, step.final) for step in DEFAULT_RULE] == [
        ("route-unjudged", True),
        ("route-missing", True),
        ("route-connectivity", True),
        ("route-vias", False),
        ("route-length", False),
        ("route-stub", False),
    ]
    assert NOTICES == {"route-stub", "route-unjudged"}
    found = routed()
    other = without(found, "b-2")
    pairing = pair_nets(found, other, REFS)
    assert kinds(level_routing(found, other, pairing)) == [("route-vias", "B:J1-2,J2-2")]
    loose = tuple(step for step in DEFAULT_RULE if step.kind != "route-vias")
    assert kinds(level_routing(found, other, pairing, rule=loose)) == []
    always: Step = Step("route-missing", lambda a, b, tolerances: [((), a.name, "")], final=True)
    assert [d.a for d in level_routing(found, found, pairing, rule=(always,)).differences] == [
        "A",
        "B",
        "C",
        "D",
    ]
