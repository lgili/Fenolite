# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Change c0465: the governing allowance and the stub of a dangling item (``checks.allowances``), on
authored benches; the DRC stage's use of them (verification-loop, "Allowances in the DRC stage")."""

from __future__ import annotations

from _coppercheck import Copper, disc_entry, mm

from fenolite.checks.allowances import Stub, governing, stub, stub_subject, stub_suffix
from fenolite.checks.padpath import CopperGraph
from fenolite.core.coords import Point
from fenolite.model.rules import Rule, RuleSubject, Selector


def _p(x: float, y: float) -> Point:
    return Point(mm(x), mm(y))


def _padded(net: str = "SIG") -> Copper:
    """A bench with one pad of ``net`` at the origin."""
    bench = Copper()
    bench.pad("U1", "1", net, disc_entry(0, 0, mm(1)))
    return bench


def test_stub_from_a_pad_to_an_open_end() -> None:
    bench = _padded()
    track = bench.track("SIG", _p(0, 0), _p(2, 0))
    found = stub(bench.build(), track.id, pads=bench.pads)
    assert isinstance(found, Stub)
    assert (found.length, found.pieces, found.open_ends, found.end_id) == (mm(2), (track.id,), 1, track.id)
    assert found.layer == "F.Cu"


def test_stub_follows_a_run_of_two_pieces() -> None:
    bench = _padded()
    first = bench.track("SIG", _p(0, 0), _p(1, 0))
    second = bench.track("SIG", _p(1, 0), _p(3, 0))
    design = bench.build()
    for item in (first, second):
        found = stub(design, item.id, pads=bench.pads)
        assert isinstance(found, Stub) and found.length == mm(3), item.id
        assert found.pieces == tuple(sorted((first.id, second.id))) and found.end_id == second.id


def test_stub_stops_at_a_junction() -> None:
    bench = _padded()
    trunk = bench.track("SIG", _p(0, 0), _p(2, 0))
    up = bench.track("SIG", _p(2, 0), _p(2, 1))
    down = bench.track("SIG", _p(2, 0), _p(2, -1.5))
    design = bench.build()
    assert stub(design, trunk.id, pads=bench.pads) == "not-dangling"
    found_up, found_down = (stub(design, t.id, pads=bench.pads) for t in (up, down))
    assert isinstance(found_up, Stub) and isinstance(found_down, Stub)
    assert (found_up.length, found_down.length) == (mm(1), mm(1.5))


def test_a_track_open_at_both_ends_is_one_stub() -> None:
    bench = Copper()
    track = bench.track("SIG", _p(0, 0), _p(5, 0))
    found = stub(bench.build(), track.id)
    assert isinstance(found, Stub) and (found.length, found.open_ends) == (mm(5), 2)


def test_a_via_that_joins_nothing_is_an_open_end() -> None:
    bench = _padded()
    track = bench.track("SIG", _p(0, 0), _p(3, 0))
    via = bench.via("SIG", _p(3, 0))
    design = bench.build()
    for item in (track.id, via.id):
        found = stub(design, item, pads=bench.pads)
        assert isinstance(found, Stub) and (found.length, found.open_ends) == (mm(3), 1), item
    lone = Copper()
    alone = lone.via("SIG", _p(1, 1))
    found = stub(lone.build(), alone.id)
    assert isinstance(found, Stub) and (found.length, found.end_id, found.open_ends) == (0, "", 1)


def test_a_via_that_joins_other_copper_is_not_an_end() -> None:
    bench = _padded()
    bench.pad("U2", "1", "SIG", disc_entry(mm(6), 0, mm(1), "B.Cu"))
    top = bench.track("SIG", _p(0, 0), _p(3, 0))
    via = bench.via("SIG", _p(3, 0))
    bench.track("SIG", _p(3, 0), _p(6, 0), layer="B.Cu")
    design = bench.build()
    assert stub(design, top.id, pads=bench.pads) == "not-dangling"
    assert stub(design, via.id, pads=bench.pads) == "not-dangling"


def test_a_stub_ends_in_a_zone_of_its_net() -> None:
    bench = _padded()
    track = bench.track("SIG", _p(0, 0), _p(3, 0))
    ring = (_p(2.5, -1), _p(5, -1), _p(5, 1), _p(2.5, 1))
    bench.zone("SIG", ring, fills=(ring,))
    assert stub(bench.build(), track.id, pads=bench.pads) == "not-dangling"
    other = _padded()
    open_track = other.track("SIG", _p(0, 0), _p(3, 0))
    other.zone("GND", ring, fills=(ring,))  # a zone of another net is not the stub's copper
    found = stub(other.build(), open_track.id, pads=other.pads)
    assert isinstance(found, Stub) and found.length == mm(3)


def test_an_arc_piece_counts_its_exact_length() -> None:
    bench = _padded()
    track = bench.track("SIG", _p(0, 0), _p(1, 0))
    arc = bench.arc("SIG", _p(1, 0), _p(2, 1), _p(3, 0))
    design = bench.build()
    graph = CopperGraph(design, pads=bench.pads)
    arc_length = (
        sum(
            step.length_nm for neighbours in graph.adj.values() for _, step in neighbours if step.id == arc.id
        )
        // 2
    )  # each edge is listed at both of its vertices
    found = stub(design, arc.id, pads=bench.pads, graph=graph)
    assert isinstance(found, Stub)
    assert found.length == mm(1) + arc_length and found.end_id == arc.id and arc_length > mm(2)
    assert found.pieces == tuple(sorted((track.id, arc.id)))


def test_an_unknown_item_has_no_stub() -> None:
    bench = _padded()
    bench.track("SIG", _p(0, 0), _p(1, 0))
    assert stub(bench.build(), "trk_00000000-0000-4000-8000-00000000dead", pads=bench.pads) == "no-item"


def test_stub_subject_and_suffix() -> None:
    bench = _padded()
    track = bench.track("SIG", _p(0, 0), _p(1.25, 0))
    design = bench.build()
    found = stub(design, track.id, pads=bench.pads)
    assert isinstance(found, Stub)
    subject = stub_subject(design, found)
    assert (subject.item_kind, subject.net, subject.layer) == ("track", "SIG", "F.Cu")
    rule = Rule(id="rul_00000000-0000-4000-8000-0000000c0465", name="SIG_STUB", kind="antenna",
                selector_a=Selector("net", "SIG"), max=mm(1.5))  # fmt: skip
    assert stub_suffix(found.length, rule) == " (stub 1.25mm within 1.5mm of rule SIG_STUB)"


def _rule(name: str, kind: str, a: Selector, b: Selector | None = None, **fields: object) -> Rule:
    return Rule(id=f"rul_00000000-0000-4000-8000-{len(name):012d}", name=name, kind=kind, selector_a=a,  # type: ignore[arg-type]
                selector_b=b, **fields)  # type: ignore[arg-type]  # fmt: skip


def _subject(net: str, layer: str = "F.Cu") -> RuleSubject:
    return RuleSubject(item_kind="track", net=net, netclass="Default", layer=layer)


def test_the_later_short_rule_governs_in_either_order() -> None:
    allow = _rule("join", "short", Selector("all"), Selector("all"), severity="ignore")
    forbid = _rule("keep_apart", "short", Selector("net", "AGND"), Selector("net", "DGND"), priority=1)
    rules = (forbid, allow)
    assert governing(rules, "short", _subject("AGND"), _subject("VIN")) is allow
    assert governing(rules, "short", _subject("DGND"), _subject("AGND")) is forbid
    assert governing((allow,), "short", _subject("agnd"), _subject("dgnd")) is allow  # letter case folded
    assert governing((), "short", _subject("AGND"), _subject("DGND")) is None
    on_bottom = _rule(
        "bottom", "short", Selector("all"), Selector("all"), severity="ignore", layers=("B.Cu",)
    )
    assert governing((on_bottom,), "short", _subject("A"), _subject("B")) is None
    assert governing((on_bottom,), "short", _subject("A", "B.Cu"), _subject("B", "B.Cu")) is on_bottom


def test_the_governing_antenna_rule() -> None:
    wide = _rule("any", "antenna", Selector("all"), max=0)
    narrow = _rule("sig_stub", "antenna", Selector("net", "SIG"), max=mm(1), priority=1)
    assert governing((narrow, wide), "antenna", _subject("SIG")) is narrow
    assert governing((narrow, wide), "antenna", _subject("VIN")) is wide
