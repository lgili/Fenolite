# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Anchored points in script copper (capability manual-copper, "Anchored points in script copper"; change
c0111): ``resolve_copper`` replaces each anchor by its board point on the placed design. Hermetic."""

from __future__ import annotations

from types import SimpleNamespace

from _buildhelp import resolver
from _copper import at, built_blink, end, track, via
from _placed import Part, design_of, mm, pt

from fenolite.backends.kicad import copper
from fenolite.backends.kicad.copper import AnchorLike, copper_uuid, resolve_copper
from fenolite.backends.kicad.frame import find_pads, part_frame
from fenolite.backends.kicad.replace import move_footprint
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.dsl import Anchor, ArcStep, ViaStep
from fenolite.model.board import Arc, Track, Via
from fenolite.model.design import Design

FAN9 = via("fan9", Anchor("U1", "9", None, Point(0, mm(1))), net="VIN")  # type: ignore[arg-type]


def _resolve(design: Design, *intents: object, unplaced: tuple[str, ...] = ()) -> tuple[Design, list[Issue]]:
    found: list[Issue] = []
    result = resolve_copper(design, intents, unplaced=unplaced, issues=found)  # type: ignore[arg-type]
    return result, found


def _vias(design: Design) -> tuple[Via, ...]:
    assert design.board is not None
    return design.board.vias


def _tracks(design: Design) -> tuple[Track, ...]:
    assert design.board is not None
    return design.board.tracks


def _arcs(design: Design) -> tuple[Arc, ...]:
    assert design.board is not None
    return design.board.arcs


def _net(design: Design, name: str) -> str:
    return next(net.id for net in design.circuit.nets if net.name == name)


def _pad(design: Design, component: str, number: str | int) -> Point:
    return find_pads(design, component, number)[0].position


def _turned(design: Design, ref: str, degrees: int) -> Design:
    """``design`` with the footprint of ``ref`` placed again at the same point at ``degrees``."""
    assert design.board is not None
    component = next(c for c in design.circuit.components if c.ref == ref)
    footprint = next(fp for fp in design.board.footprints if fp.component_id == component.id)
    known = {footprint.lib_ref: resolver(10).footprint(footprint.lib_ref)}
    return move_footprint(design, footprint.id, rotation=degrees * 1_000_000, definitions=known, force=True)


def test_a_via_anchored_beside_a_pad() -> None:
    """Scenario "A via anchored beside a pad"."""
    blink = built_blink()
    resolved, found = _resolve(blink, FAN9)
    (made,) = _vias(resolved)
    pad = _pad(blink, "U1", 9)
    assert made.position == Point(pad.x, pad.y + mm(1))
    assert made.net_id == _net(blink, "VIN") and (made.diameter, made.drill) == (mm(0.6), mm(0.3))
    assert made.native_ids["kicad"] == copper_uuid("fan9", "via")
    assert found == []


def test_anchored_copper_follows_a_turned_part() -> None:
    """Scenario "Anchored copper follows a turned part": the same uuid, at the pad's new place."""
    resolved, _ = _resolve(built_blink(), FAN9)
    turned = _turned(resolved, "U1", 90)
    again, found = _resolve(turned, FAN9)
    (made,) = _vias(again)
    pad = _pad(turned, "U1", 9)
    assert pad != _pad(resolved, "U1", 9), "the control: the pad moved"
    assert made.position == Point(pad.x + mm(1), pad.y)
    assert made.position == part_frame(turned, "U1", number="9").point(Point(0, mm(1)))
    assert made.native_ids["kicad"] == copper_uuid("fan9", "via") == _vias(resolved)[0].native_ids["kicad"]
    assert [(i.code, i.where) for i in found] == [("kicad.copper.regenerated", copper_uuid("fan9", "via"))]


def test_an_anchor_is_not_a_pad_end() -> None:
    """Scenario "An anchor is not a pad end": it joins no pad and gives the track no net."""
    blink = built_blink()
    beside = Anchor("R1", "2", None, Point(mm(1), 0))
    stub = track("stub", end("R1", 2), beside)
    loose = track("loose", Anchor("R1", "2", None, Point(0, 0)), beside)
    resolved, found = _resolve(blink, stub, loose)
    (made,) = _tracks(resolved)
    pad = _pad(blink, "R1", 2)
    assert (made.start, made.end) == (pad, Point(pad.x + mm(1), pad.y))
    assert made.net_id == _net(blink, "LED_A"), "the net of its pad end"
    assert made.native_ids["kicad"] == copper_uuid("stub", "seg[0]")
    assert [(i.code, i.where) for i in found] == [("kicad.copper.no-net", "loose")]
    # with a named net the two anchors make a track on it, although both lie in a pad of another net
    named, quiet = _resolve(blink, track("loose", Anchor("R1", "2", None, Point(0, 0)), beside, net="GND"))
    assert _tracks(named)[0].net_id == _net(blink, "GND") and quiet == []


def test_anchors_that_cannot_be_resolved() -> None:
    """Scenario "Anchors that cannot be resolved": each intent creates nothing, the next are resolved."""
    blink = built_blink()
    resolved, found = _resolve(
        blink,
        via("nopart", Anchor("R9", None, None, Point(0, 0))),  # type: ignore[arg-type]
        via("nopad", Anchor("R1", "7", None, Point(0, 0))),  # type: ignore[arg-type]
        via("staged", Anchor("D1", "1", None, Point(0, 0))),  # type: ignore[arg-type]
        via("beyond", Anchor("R1", "2", 3, Point(0, 0))),  # type: ignore[arg-type]
        via("good", Anchor("R1", None, None, Point(0, mm(3)))),  # type: ignore[arg-type]
        unplaced=("D1",),
    )
    assert [v.native_ids["kicad"] for v in _vias(resolved)] == [copper_uuid("good", "via")]
    assert [(i.where, i.code, i.severity) for i in found] == [
        ("nopart", "kicad.copper.pad-not-found", "error"),
        ("nopad", "kicad.copper.pad-not-found", "error"),
        ("staged", "kicad.copper.end-unplaced", "warning"),
        ("beyond", "kicad.copper.pad-not-found", "error"),
    ]
    messages = {i.where: i.message for i in found}
    assert "nopart" in messages["nopart"] and "R9" in messages["nopart"]
    assert "nopad" in messages["nopad"] and "R1" in messages["nopad"] and "'7'" in messages["nopad"]
    assert "staged" in messages["staged"] and "D1" in messages["staged"]
    assert "R1" in messages["beyond"] and "'2'" in messages["beyond"] and "index 3" in messages["beyond"]


def test_an_anchor_on_a_shared_number_needs_an_index() -> None:
    """Scenario "An anchor on a shared number needs an index"."""
    design = design_of(Part("J1", "Mini_Edge_Cases", 0, 0), extra_nets=("GND",))
    resolved, found = _resolve(
        design,
        via("a", Anchor("J1", "1", None, Point(0, 0))),  # type: ignore[arg-type]
        via("b", Anchor("J1", "1", 1, Point(0, 0))),  # type: ignore[arg-type]
    )
    (made,) = _vias(resolved)
    assert made.position == pt(2, 0) and made.native_ids["kicad"] == copper_uuid("b", "via")
    (issue,) = found
    assert (issue.code, issue.where) == ("kicad.copper.bad-intent", "a")
    assert "a:" in issue.message and "J1" in issue.message and "'1'" in issue.message


def test_anchors_in_via_steps_and_arc_steps() -> None:
    """Every place a track holds a point: a waypoint, the ``at`` of a via step, ``mid`` and ``end`` of an
    arc step. The locators are those of the elements, as for board points."""
    design = design_of(Part("U1", "Frame_Anchor", 20, 20, 90, "bottom", library="Frame"), extra_nets=("GND",))
    frame = part_frame(design, "U1")
    offsets = [Point(mm(5), mm(-6)), Point(mm(5), mm(-4)), Point(mm(6), mm(-3)), Point(mm(7), mm(-3))]
    start, corner, middle, last = (Anchor("U1", None, None, offset) for offset in offsets)
    hop = Anchor("U1", "4", None, Point(mm(8), mm(-3)))  # pad 4 is at (1, 0): the point (9, −3) of the part
    path = (start, corner, ArcStep(middle, last), ViaStep(hop, "B.Cu", mm(0.6), mm(0.3)), at(10, 10))
    resolved, found = _resolve(design, track("bend", *path, net="GND"))
    assert found == []
    a, b, c, d = (frame.point(offset) for offset in offsets)
    e = frame.point(Point(mm(9), mm(-3)))
    assert e == part_frame(design, "U1", number=4).point(Point(mm(8), mm(-3)))
    (arc,) = _arcs(resolved)
    assert (arc.start, arc.mid, arc.end) == (b, c, d) and arc.native_ids["kicad"] == copper_uuid(
        "bend", "arc[2]"
    )
    (step,) = _vias(resolved)
    assert step.position == e and step.native_ids["kicad"] == copper_uuid("bend", "via[3]")
    segments = {t.native_ids["kicad"]: (t.start, t.end, t.layer) for t in _tracks(resolved)}
    assert segments == {
        copper_uuid("bend", "seg[0]"): (a, b, "F.Cu"),
        copper_uuid("bend", "seg[2]"): (d, e, "F.Cu"),
        copper_uuid("bend", "seg[3]"): (e, at(10, 10), "B.Cu"),
    }
    # on the bottom at 90° the offset (5, −6) of the part is mirrored, then turned
    assert a == pt(20 + 6, 20 - 5)


def test_an_anchor_is_read_by_attribute() -> None:
    """``AnchorLike`` is a protocol: any object with the four attributes is an anchor, and an element that
    has ``offset`` is never read as a pad end."""
    design = design_of(Part("U1", "Frame_Anchor", 20, 20, library="Frame", nets={"4": "GND"}))
    duck = SimpleNamespace(component="U1", number="4", index=None, offset=Point(mm(1), 0))
    assert isinstance(duck, AnchorLike) and "AnchorLike" in copper.__all__
    resolved, found = _resolve(design, track("t", duck, at(1, 1), net="GND", layer="B.Cu"))
    (made,) = _tracks(resolved)
    assert made.start == pt(22, 20) and made.layer == "B.Cu", "a pad end of pad 4 would need copper on B.Cu"
    assert found == []


def test_intents_without_anchors_resolve_as_before() -> None:
    blink = built_blink()
    plain = [track("a", end("R1", 2), at(36, 9)), via("b", at(20, 20))]
    first, found = _resolve(blink, *plain)
    assert found == [] and len(_tracks(first)) == 1 and _vias(first)[0].position == at(20, 20)
    again, quiet = _resolve(first, *plain)
    assert again == first and quiet == []
