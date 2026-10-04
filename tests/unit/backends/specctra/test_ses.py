# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Specctra session reader (capability specctra-dsn, "Session files are read into copper"). Every
session text here is authored for Fenolite; none was written by a router."""

from __future__ import annotations

import dataclasses
from fractions import Fraction
from pathlib import Path

import pytest
from _placed import Part, design_of, mm, pt
from _specctra import bench, two_pads

from fenolite.backends.specctra.dsn import Names
from fenolite.backends.specctra.ses import Place, Session, SessionVia, Wire, read_session, to_copper
from fenolite.core.errors import FormatError
from fenolite.core.ids import derived_id, is_id
from fenolite.model.board import Track, Via

DATA = Path(__file__).resolve().parents[3] / "data" / "specctra"
F = Fraction


def _authored() -> str:
    return (DATA / "two_pads.ses").read_text(encoding="utf-8")


def _names() -> Names:
    return two_pads().write().names


def _session(routes: str, *, placement: str = "", was_is: str = "", extra: str = "") -> str:
    return (
        f"(session s (base_design b.dsn) {placement} {was_is} {extra} "
        f"(routes (resolution um 10) (network_out {routes})))"
    )


def _codes(issues: tuple[object, ...]) -> list[str]:
    return [issue.code for issue in issues]  # type: ignore[attr-defined]


# --- reading ----------------------------------------------------------------------------------------


def test_reads_the_authored_session() -> None:
    session = read_session(_authored(), file="two_pads.ses")
    assert session == Session(
        name="two_pads.ses",
        unit="um",
        resolution=10,
        wires=(
            Wire(
                "A",
                "F.Cu",
                F(2500),
                ((F(108000), F(-100000)), (F(150000), F(-120000)), (F(192000), F(-100000))),
            ),
        ),
        vias=(SessionVia("A", "Via_600_300", (F(150000), F(-120000))),),
        places=(
            Place("R1", (F(100000), F(-100000)), "front", F(0)),
            Place("R2", (F(200000), F(-100000)), "front", F(0)),
        ),
        place_unit="um",
        place_resolution=10,
        swaps=(),
        unknown=(),
    )


def test_authored_session_to_copper() -> None:
    """Scenario "Authored session"."""
    b = two_pads()
    names = b.write().names
    tracks, vias, issues = to_copper(read_session(_authored()), names, selected=("A",))
    assert issues == ()
    net = b.design.nets_by_name["A"].id
    assert [(t.start, t.end, t.width, t.layer, t.net_id) for t in tracks] == [
        (pt(10.8, 10), pt(15, 12), mm(0.25), "F.Cu", net),
        (pt(15, 12), pt(19.2, 10), mm(0.25), "F.Cu", net),
    ]
    (via,) = vias
    assert (via.position, via.diameter, via.drill) == (pt(15, 12), mm(0.6), mm(0.3))
    assert via.layers == ("F.Cu", "B.Cu") and via.net_id == net and via.via_type == "through"
    assert all(isinstance(t, Track) and is_id(t.id, "trk") for t in tracks)
    assert isinstance(via, Via) and is_id(via.id, "via")
    # the route ends on the pad centres
    ends = {pad.position for pad in b.pads if pad.net == "A"}
    assert {tracks[0].start, tracks[-1].end} == ends


def test_ids_derive_from_the_net_and_the_geometry() -> None:
    names = _names()
    first = to_copper(read_session(_authored()), names, selected=("A",))
    second = to_copper(read_session(_authored()), names, selected=("A",))
    assert first == second
    tracks, vias, _ = first
    assert tracks[0].id == derived_id("trk", "specctra", "A:F.Cu:250000:10800000,10000000:15000000,12000000")
    assert vias[0].id == derived_id("via", "specctra", "A:Via_600_300:15000000,12000000")
    assert len({item.id for item in (*tracks, *vias)}) == 3


def test_a_reversed_or_repeated_segment_gives_one_track() -> None:
    text = _session(
        "(net A (wire (path F.Cu 2500 0 0 1000 0)) (wire (path F.Cu 2500 1000 0 0 0)) "
        "(via Via_600_300 5 5 5 5))"
    )
    tracks, vias, _ = to_copper(read_session(text), _names(), selected=("A",))
    assert len(tracks) == 1 and len(vias) == 1


def test_zero_length_segments_are_dropped() -> None:
    text = _session("(net A (wire (path F.Cu 2500 0 0 0 0 1000 0 1000 0)))")
    tracks, _, _ = to_copper(read_session(text), _names(), selected=("A",))
    assert [(t.start, t.end) for t in tracks] == [(pt(0, 0), pt(0.1, 0))]


def test_unselected_net_ignored() -> None:
    """Scenario "Unselected net ignored"."""
    design = design_of(
        Part("R1", "Mini_R_0603", 10, 10, nets={"1": "A", "2": "B"}),
        Part("R2", "Mini_R_0603", 20, 10, nets={"1": "A", "2": "B"}),
    )
    names = bench(design, selected=("A", "B")).write().names
    text = _session(
        "(net A (wire (path F.Cu 2500 0 0 1000 0))) "
        "(net B (wire (path F.Cu 2500 0 500 1000 500)) (via Nowhere 1 1)) "
        "(net Stranger (wire (path F.Cu 2500 0 900 1000 900)))"
    )
    tracks, vias, issues = to_copper(read_session(text), names, selected=("A",))
    assert [t.net_id for t in tracks] == [design.nets_by_name["A"].id]
    assert vias == () and issues == ()
    assert to_copper(read_session(text), names, selected=()) == ((), (), ())


def test_session_in_another_resolution() -> None:
    """The same route written in mil at 100 units per mil, and in mm with decimals."""
    names = _names()
    mil = (
        "(session s (routes (resolution mil 100) (network_out (net A "
        "(wire (path F.Cu 1000 10000 -20000 30000 -20000)) (via Via_600_300 30000 -20000)))))"
    )
    tracks, vias, _ = to_copper(read_session(mil), names, selected=("A",))
    assert (tracks[0].start, tracks[0].end, tracks[0].width) == (pt(2.54, 5.08), pt(7.62, 5.08), mm(0.254))
    assert vias[0].position == pt(7.62, 5.08)
    metric = (
        "(session s (routes (resolution mm 1000) (network_out (net A "
        "(wire (path F.Cu 250 2540.5 -5080 7620 -5080))))))"
    )
    tracks, _, _ = to_copper(read_session(metric), names, selected=("A",))
    assert tracks[0].start.x == 2_540_500 and tracks[0].width == mm(0.25)


def test_a_value_that_is_no_whole_nanometre_is_rounded_half_to_even() -> None:
    text = "(session s (routes (resolution um 2000) (network_out (net A (wire (path F.Cu 500 1 0 3 0))))))"
    tracks, _, _ = to_copper(read_session(text), _names(), selected=("A",))
    assert (tracks[0].start.x, tracks[0].end.x) == (0, 2)  # 0.5 nm and 1.5 nm


# --- refusals of to_copper ----------------------------------------------------------------------


def test_unknown_padstack() -> None:
    text = _session("(net A (wire (path F.Cu 2500 0 0 1000 0)) (via Via_999_1 5 5))")
    tracks, vias, issues = to_copper(read_session(text), _names(), selected=("A",))
    assert (tracks, vias) == ((), ())
    (issue,) = issues
    assert (
        issue.code == "specctra.unknown-padstack"
        and issue.severity == "error"
        and "Via_999_1" in issue.message
    )


def test_session_that_moves_a_component() -> None:
    """Scenario "Session that moves a component"."""
    text = _session(
        "(net A (wire (path F.Cu 2500 0 0 1000 0)))",
        placement="(placement (resolution um 10) (component R1 (place R1 100000 -110000 front 0)))",
    )
    tracks, vias, issues = to_copper(read_session(text), _names(), selected=("A",))
    assert (tracks, vias) == ((), ())
    (issue,) = issues
    assert (
        issue.code == "specctra.session-moved" and issue.severity == "error" and "moves R1" in issue.message
    )


@pytest.mark.parametrize(
    ("placement", "was_is", "why"),
    [
        ("(placement (component R1 (place R1 100000 -100000 back 0)))", "", "turns R1"),
        ("(placement (component R1 (place R1 100000 -100000 front 90)))", "", "turns R1"),
        ("(placement (component R9 (place R9 100000 -100000 front 0)))", "", "places R9"),
        ("", "(was_is (pins R1-1 R1-2) (pins R1-2 R1-1))", "swaps 2 pin(s)"),
    ],
)
def test_other_sessions_that_change_the_placement(placement: str, was_is: str, why: str) -> None:
    text = _session("(net A (wire (path F.Cu 2500 0 0 1000 0)))", placement=placement, was_is=was_is)
    tracks, vias, issues = to_copper(read_session(text), _names(), selected=("A",))
    assert (tracks, vias) == ((), ())
    assert _codes(issues) == ["specctra.session-moved"] and why in issues[0].message


@pytest.mark.parametrize(
    "placement",
    [
        "(placement (resolution um 10) (component R1 (place R1 100000 -100000 front 0)))",
        "(placement (component R1 (place R1 100000 -100000 FRONT 0.00)))",
        "(placement (unit um) (component R1 (place R1 10000 -10000 front 0)))",
        "(placement (component R1 (place R1 10000.0 -10000.0 front 0)))",
        "(placement (unit mm) (component R1 (place R1 10 -10 front 0 (lock_type position))))",
    ],
)
def test_session_that_repeats_the_placement(placement: str) -> None:
    """Scenario "Session that repeats the placement": in database units or in the unit itself."""
    text = _session("(net A (wire (path F.Cu 2500 0 0 1000 0)))", placement=placement, was_is="(was_is)")
    tracks, _, issues = to_copper(read_session(text), _names(), selected=("A",))
    assert len(tracks) == 1 and issues == ()


def test_protected_input_wiring_is_ignored() -> None:
    b = two_pads()
    assert b.design.board is not None
    net = b.design.nets_by_name["A"].id
    track = Track(
        id="trk_00000000-0000-4000-8000-000000000001",
        start=pt(10.8, 10),
        end=pt(15, 10),
        width=mm(0.25),
        layer="F.Cu",
        net_id=net,
    )
    via = Via(
        id="via_00000000-0000-4000-8000-000000000001",
        position=pt(15, 10),
        diameter=mm(0.6),
        drill=mm(0.3),
        layers=("F.Cu", "B.Cu"),
        net_id=net,
    )
    board = dataclasses.replace(b.design.board, tracks=(track,), vias=(via,))
    names = dataclasses.replace(b, design=dataclasses.replace(b.design, board=board)).write().names
    text = _session(
        "(net A (wire (path F.Cu 2500 150000 -100000 108000 -100000)) (via Via_600_300 150000 -100000) "
        "(wire (path B.Cu 2500 150000 -100000 192000 -100000)) (via Via_600_300 192000 -100000))"
    )
    tracks, vias, issues = to_copper(read_session(text), names, selected=("A",))
    assert [(t.layer, t.start, t.end) for t in tracks] == [("B.Cu", pt(15, 10), pt(19.2, 10))]
    assert [v.position for v in vias] == [pt(19.2, 10)]
    assert issues == ()


def test_unknown_lists_are_reported_once_per_head() -> None:
    """An unknown list at every level, and a wire that is no path."""
    text = _session(
        "(net A (wire (path F.Cu 2500 0 0 1000 0) (type route) (colour red)) "
        "(wire (polygon F.Cu 0 0 0 10 0 10 10) (colour blue)) (via Via_600_300 5 5 (type route) (glow 1)) "
        "(fromto a b)) (group G)",
        extra="(floor_plan (room x)) (history (self (comment x)))",
        placement="(placement (place_control (flip_style rotate_first)))",
        was_is="(was_is (gates a b))",
    )
    session = read_session(text)
    assert session.unknown == (
        "colour",
        "floor_plan",
        "fromto",
        "gates",
        "glow",
        "group",
        "place_control",
        "polygon",
    )
    tracks, vias, issues = to_copper(session, _names(), selected=("A",))
    assert len(tracks) == 1 and len(vias) == 1
    assert _codes(issues) == ["specctra.unknown-list"] * 8
    assert {issue.severity for issue in issues} == {"info"}
    assert [issue.where for issue in issues] == list(session.unknown)


def test_session_without_routes_gives_no_copper() -> None:
    session = read_session("(session s (base_design b.dsn))")
    assert session.unit is None and session.wires == ()
    assert to_copper(session, _names(), selected=("A",)) == ((), (), ())


def test_wire_on_a_layer_the_design_lacks() -> None:
    text = _session("(net A (wire (path In1.Cu 2500 0 0 1000 0)))")
    with pytest.raises(FormatError, match=r"In1\.Cu"):
        to_copper(read_session(text), _names(), selected=("A",))


def test_via_between_inner_layers_keeps_its_type() -> None:
    b = bench(design_of(Part("R1", "Mini_R_0603", 10, 10, nets={"1": "A"}), copper=4))
    assert b.design.board is not None
    copper = [la.name for la in b.design.board.layers if la.kind == "copper"]
    spans = {"blind": (copper[0], copper[1]), "buried": (copper[1], copper[2])}
    stubs = tuple(
        Via(
            id=f"via_00000000-0000-4000-8000-00000000000{n}",
            position=pt(5, 5 + n),
            diameter=mm(0.6),
            drill=mm(0.3),
            layers=layers,
        )
        for n, layers in enumerate(spans.values(), start=1)
    )
    board = dataclasses.replace(b.design.board, vias=stubs)
    names = dataclasses.replace(b, design=dataclasses.replace(b.design, board=board)).write().names
    text = _session(
        "(net A (via Via_600_300_L1_L2 10 10) (via Via_600_300_L2_L3 20 20) (via Via_600_300 30 30))"
    )
    _, vias, _ = to_copper(read_session(text), names, selected=("A",))
    assert [v.via_type for v in vias] == ["blind", "buried", "through"]
    assert [v.layers for v in vias] == [spans["blind"], spans["buried"], (copper[0], copper[-1])]


# --- malformed sessions -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("(pcb x)", "starts with"),
        ("(session s (routes (network_out)))", "declares no resolution"),
        ("(session s (routes (resolution parsec 10)))", "needs one of"),
        ("(session s (routes (resolution um ten)))", "positive integer"),
        ("(session s (routes (resolution um 0)))", "positive integer"),
        ("(session s (placement (unit furlong)))", "needs one of"),
        ("(session s (placement (component R1 (place R1 1 2))))", "place needs"),
        ("(session s (placement (component R1 (place R1 x 2 front 0))))", "not a number"),
        ("(session s (was_is (pins a)))", "two pin references"),
        (_session("(net (wire (path F.Cu 1 0 0 1 1)))"), "needs a name"),
        (_session("(net A (wire (path F.Cu 2500 0 0)))"), "at least two points"),
        (_session("(net A (wire (path F.Cu 2500 0 0 1 1 2)))"), "odd number"),
        (_session("(net A (wire (path F.Cu wide 0 0 1 1)))"), "not a number"),
        (_session("(net A (via Via_600_300 1))"), "needs a padstack"),
        (_session("(net A (via Via_600_300 1 2 3))"), "odd number"),
        ("(session s", "not closed"),
    ],
)
def test_malformed_sessions(text: str, message: str) -> None:
    with pytest.raises(FormatError) as caught:
        read_session(text, file="x.ses")
    assert message in str(caught.value)
    assert caught.value.file == "x.ses" and caught.value.offset is not None


def test_a_placement_with_its_own_resolution_holds_database_units() -> None:
    """What Freerouting 2.4.1 writes (probe ``dsn-accept``): under ``(resolution um 10)`` the written
    position is 100000, and 10000 is another place."""
    text = _session(
        "(net A (wire (path F.Cu 2500 0 0 1000 0)))",
        placement="(placement (resolution um 10) (component R1 (place R1 10000 -10000 front 0)))",
    )
    tracks, _, issues = to_copper(read_session(text), _names(), selected=("A",))
    assert tracks == () and _codes(issues) == ["specctra.session-moved"]
