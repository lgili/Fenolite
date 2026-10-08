# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The connected pieces of a net's copper (capability design-equivalence, "Routed connectivity of a net";
change c0089; ``H-G-EQ-L5-SPLIT``)."""

from __future__ import annotations

import dataclasses
import time
from math import gcd

import pytest
from _cases import design, netted, pad
from _routes import (
    ALL,
    MM,
    arc,
    board,
    mm,
    parts,
    resegmented,
    routed,
    track,
    via,
    with_board,
    with_track,
    without,
    zone,
)
from hypothesis import given, settings
from hypothesis import strategies as st

from fenolite.analysis import views
from fenolite.checks.equivalence import Tolerances, compare_designs
from fenolite.checks.equivalence.routing import (
    Piece,
    arc_length,
    pieces,
    span_names,
    track_length,
)
from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.model.board import Arc, Track
from fenolite.model.design import Design


def of(found: Design, net: str) -> tuple[Piece, ...]:
    """The pieces of the net called ``net``."""
    ids = {n.name: n.id for n in found.circuit.nets}
    return pieces(found).get(ids[net], ())


# --- the scenarios ---------------------------------------------------------------------------------


def two_pads() -> Design:
    """A top pad, a track to a via, and a bottom track to a second pad on the bottom layer."""
    bare = design(
        [("R1", "1k"), ("R2", "1k")],
        {"R1": (pad("1"),), "R2": (pad("1", layers=("Bottom",)),)},
        {"R1": mm(0, 0), "R2": mm(10, 0)},
        name="two-pads",
    )
    found = netted(bare, {"N": (("R1", "1"), ("R2", "1"))})
    tracks = (
        track(found, "top", "N", mm(0, 0), mm(4, 0)),
        track(found, "bottom", "N", mm(4, 0), mm(10, 0), "Bottom"),
    )
    return with_board(found, tracks=tracks, vias=(via(found, "v", "N", mm(4, 0)),))


def test_two_pads_joined_through_a_via() -> None:
    assert of(two_pads(), "N") == (
        Piece(("R1-1", "R2-1"), (("top-bottom", 1),), (("top", 4 * MM), ("bottom", 6 * MM)), True),
    )


def test_an_open_connection() -> None:
    assert of(without(two_pads(), "bottom"), "N") == (
        Piece(("R1-1",), (("top-bottom", 1),), (("top", 4 * MM),), True),
        Piece(("R2-1",)),
    )


def test_the_routed_board() -> None:
    found = routed()
    assert of(found, "A") == (
        Piece(("J1-1", "J2-1"), (("top-bottom", 1),), (("top", 10 * MM), ("bottom", 10 * MM)), True),
    )
    assert of(found, "B") == (
        Piece(("J1-2", "J2-2"), (("top-bottom", 2),), (("top", 20 * MM), ("bottom", 10 * MM)), True),
    )
    assert of(found, "C") == (Piece(("R1-1", "R2-1"), (), (("top", 5 * MM),), True),)
    assert of(found, "D") == (Piece(("R1-2", "R2-2"), (), (("top", 4 * MM + 1_570_796),), True),)
    held = pieces(found)
    assert (held.zones_unfilled, held.no_net, held.unshaped) == (0, 0, 0) and len(held) == 4


def test_no_board_and_no_copper() -> None:
    assert dict(pieces(dataclasses.replace(routed(), board=None))) == {}
    bare = pieces(parts())
    assert all(len(held) == 2 and not any(p.copper for p in held) for held in bare.values())


# --- order and segmentation ------------------------------------------------------------------------


def test_the_order_of_the_items_does_not_matter() -> None:
    found = routed()
    held = board(found)
    turned = with_board(
        found,
        tracks=tuple(reversed(held.tracks)),
        vias=tuple(reversed(held.vias)),
        footprints=tuple(reversed(held.footprints)),
    )
    swapped = with_board(
        found, tracks=tuple(dataclasses.replace(t, start=t.end, end=t.start) for t in held.tracks)
    )
    assert pieces(turned) == pieces(found) == pieces(swapped)


def _cuts(item: Track, picks: list[int]) -> list[Point]:
    """Points of the track, in order from its start, at the chosen steps of its smallest integer step."""
    dx, dy = item.end.x - item.start.x, item.end.y - item.start.y
    steps = gcd(abs(dx), abs(dy))
    if steps < 2:
        return []
    chosen = sorted({1 + pick % (steps - 1) for pick in picks})
    return [Point(item.start.x + dx // steps * k, item.start.y + dy // steps * k) for k in chosen]


@st.composite
def boards(draw: st.DrawFn) -> Design:
    """The routed board with some more tracks on net ``C`` between points of a 1 µm grid, at any angle."""
    found = routed()
    grid = st.integers(-20_000, 20_000).map(lambda v: v * 1_000)
    extra: list[Track] = []
    at = mm(9, 12)
    for k in range(draw(st.integers(0, 4))):
        end = Point(at.x + draw(grid), at.y + draw(grid))
        if end != at:
            extra.append(track(found, f"extra-{k}", "C", at, end))
            at = end
    return with_board(found, tracks=(*board(found).tracks, *extra))


@settings(max_examples=40, deadline=None)
@given(found=boards(), picks=st.lists(st.lists(st.integers(0, 10**9), max_size=4), min_size=16, max_size=16))
def test_split_invariance(found: Design, picks: list[list[int]]) -> None:
    """``H-G-EQ-L5-SPLIT``, first half: a track cut at points of itself, or joined again, is the same
    copper. The pieces are equal, to the nanometre."""
    order = {t.id: k for k, t in enumerate(board(found).tracks)}
    cut = resegmented(found, lambda item: _cuts(item, picks[order[item.id]]))
    assert pieces(cut) == pieces(found)
    assert len(board(cut).tracks) >= len(board(found).tracks)


@settings(max_examples=40, deadline=None)
@given(
    found=boards(),
    picks=st.lists(st.lists(st.integers(0, 10**9), max_size=3), min_size=16, max_size=16),
    shifts=st.lists(st.integers(-2, 2), min_size=4, max_size=4),
    data=st.data(),
)
def test_split_invariance_with_rounding(
    found: Design, picks: list[list[int]], shifts: list[int], data: st.DataObject
) -> None:
    """``H-G-EQ-L5-SPLIT``, second half: with every coordinate of every segment end moved by up to 2 nm
    as well, level 5 reports nothing within a tolerance of 2 nm per segment end (a segment of two ends
    moved by 2 nm on both axes changes its length by less than 6 nm, and a run that no longer merges is
    rounded once more)."""
    order = {t.id: k for k, t in enumerate(board(found).tracks)}
    cut = resegmented(found, lambda item: _cuts(item, picks[order[item.id]]))
    moved = tuple(
        dataclasses.replace(
            t,
            start=Point(
                t.start.x + data.draw(st.sampled_from(shifts)), t.start.y + data.draw(st.sampled_from(shifts))
            ),
            end=Point(
                t.end.x + data.draw(st.sampled_from(shifts)), t.end.y + data.draw(st.sampled_from(shifts))
            ),
        )
        for t in board(cut).tracks
    )
    other = with_board(cut, tracks=moved)
    tolerance = Tolerances(length_nm=7 * len(moved))
    result = compare_designs(found, other, level=5, tolerances=tolerance).levels[-1]
    assert result.differences == () and result.notices == (), (result.differences, result.notices)


def test_split_invariance_worst_case() -> None:
    """``H-G-EQ-L5-SPLIT`` as first written (2 nm per segment end) is refuted by one segment: a diagonal
    whose two ends move apart by 2 nm on both axes grows by 4·√2 nm, more than 4 nm. ``H-G-EQ-L5-SPLIT-2``
    states the bound that holds, 7 nm per segment."""
    found = routed()
    diagonal = track(found, "diagonal", "C", mm(9, 12), mm(12, 15))
    one = with_board(found, tracks=(*board(found).tracks, diagonal))
    grown = dataclasses.replace(
        diagonal,
        start=Point(diagonal.start.x - 2, diagonal.start.y - 2),
        end=Point(diagonal.end.x + 2, diagonal.end.y + 2),
    )
    other = with_board(found, tracks=(*board(found).tracks, grown))
    at_4 = compare_designs(one, other, level=5, tolerances=Tolerances(length_nm=4)).levels[-1]
    assert [(d.kind, d.a, d.b) for d in at_4.differences] == [("route-length", "top=9242641", "top=9242646")]
    assert (
        compare_designs(one, other, level=5, tolerances=Tolerances(length_nm=7)).levels[-1].differences == ()
    )


def test_track_length() -> None:
    a, b, c, d = Point(0, 0), Point(3, 4), Point(6, 8), Point(9, 12)
    assert track_length([(a, d)]) == 15
    assert track_length([(a, b), (b, c), (c, d)]) == 15  # three parts of 5 on one line
    assert track_length([(a, c), (b, d)]) == 20  # copper drawn twice counts twice
    assert track_length([(a, b), (d, c), (b, b)]) == 10  # direction and empty segments do not matter
    assert track_length([(Point(0, 0), Point(1, 1)), (Point(1, 1), Point(2, 2))]) == 3  # √8, not 1 + 1
    assert track_length([(Point(0, 0), Point(10, 0)), (Point(0, 1), Point(10, 1))]) == 20  # two lines
    assert track_length([(Point(0, 0), Point(1, 1)), (Point(0, 1), Point(1, 2))]) == 2  # 1.41 each, apart
    assert track_length([]) == 0


# --- lengths of arcs -------------------------------------------------------------------------------


def test_arc_length() -> None:
    half = arc_length(mm(11, 12), mm(11.5, 12.5), mm(11, 13))
    assert half == 1_570_796  # π × 0.5 mm
    assert arc_length(mm(0, 0), mm(5, 0), mm(10, 0)) == 10 * MM  # collinear points: the straight parts
    assert arc_length(mm(0, 0), mm(0, 0), mm(3, 4)) == 5 * MM  # no arc: the distance of the ends
    three_quarters = arc_length(mm(1, 0), mm(-1, 0), mm(0, -1))
    assert abs(three_quarters - 4_712_389) <= 1  # 1.5 π mm, through the far side


@pytest.mark.parametrize(
    "points",
    [
        (mm(11, 12), mm(11.5, 12.5), mm(11, 13)),
        (mm(0, 0), mm(1.3, 0.7), mm(2, 3)),
        (mm(5, 5), mm(-3, 9), mm(4, 4.5)),
        (Point(0, 0), Point(1, 1), Point(3, 0)),
        (mm(1, 0), mm(-1, 0), mm(0, -1)),
    ],
)
def test_arc_length_is_the_length_of_the_net_view(points: tuple[Point, Point, Point]) -> None:
    """``checks`` may not import ``analysis``, so the arc length is computed in both; they agree."""
    ident = derived_id("arc", "test", "length")
    model = Arc(id=ident, start=points[0], mid=points[1], end=points[2], width=1, layer="Top")
    assert arc_length(*points) == views.arc_length(model)


# --- layers, pads and zones ------------------------------------------------------------------------


def test_span_names() -> None:
    found = routed()
    assert span_names(board(found)) == {"Top": "top", "Mid": "inner1", "Bottom": "bottom"}
    layers = tuple(la for la in board(found).layers if la.name != "Bottom")
    assert span_names(dataclasses.replace(board(found), layers=layers)) == {"Top": "top", "Mid": "bottom"}


def test_blind_via_and_inner_track() -> None:
    found = routed()
    moved = with_track(found, "b-bottom", layer="Mid")
    blind = with_board(
        moved,
        vias=tuple(
            dataclasses.replace(v, layers=("Top", "Mid"), via_type="blind")
            if v.net_id == of_net(found, "B")
            else v
            for v in board(moved).vias
        ),
    )
    assert of(blind, "B") == (
        Piece(("J1-2", "J2-2"), (("top-inner1", 2),), (("top", 20 * MM), ("inner1", 10 * MM)), True),
    )


def of_net(found: Design, name: str) -> str:
    return next(n.id for n in found.circuit.nets if n.name == name)


def test_a_track_joins_a_pad_only_on_the_pads_layers() -> None:
    """``C`` is routed on the top layer between two top pads: on the bottom layer it reaches neither."""
    found = with_track(routed(), "c-top", layer="Bottom")
    assert of(found, "C") == (Piece((), (), (("bottom", 5 * MM),), True), Piece(("R1-1",)), Piece(("R2-1",)))


def test_pad_shapes_reach_as_far_as_the_pad() -> None:
    """A rectangular pad of 1 mm by 0.5 mm, turned with its footprint: a track that ends 0.6 mm from the
    centre along the pad's long axis touches it, and one that ends 0.45 mm away across it does not."""
    bare = design([("R1", "1k")], {"R1": (pad("1"),)}, {"R1": mm(0, 0)}, name="shape")
    found = netted(bare, {"N": (("R1", "1"),)})
    thin = 100_000

    def joined(a: Point, b: Point, rotation: int = 0) -> bool:
        footprints = tuple(dataclasses.replace(f, rotation=rotation) for f in board(found).footprints)
        one = with_board(found, footprints=footprints, tracks=(track(found, "t", "N", a, b, width=thin),))
        return len(of(one, "N")) == 1

    assert joined(mm(0.54, 0), mm(3, 0)) and not joined(mm(0.56, 0), mm(3, 0))
    assert joined(mm(0, 0.29), mm(0, 3)) and not joined(mm(0, 0.31), mm(0, 3))
    # a quarter turn of the footprint swaps the axes (a positive angle is counter-clockwise, Y down)
    assert joined(mm(0, -0.54), mm(0, -3), 90_000_000) and not joined(mm(0.31, 0), mm(3, 0), 90_000_000)
    oval = dataclasses.replace(board(found).footprints[0].pads[0], shape="oval")
    rounded = with_board(found, footprints=(dataclasses.replace(board(found).footprints[0], pads=(oval,)),))
    corner = track(rounded, "t", "N", mm(0.53, 0.28), mm(3, 3), width=thin)
    assert len(of(with_board(rounded, tracks=(corner,)), "N")) == 2  # the corner of the rectangle is cut
    assert len(of(with_board(found, tracks=(corner,)), "N")) == 1


def test_pads_without_copper_or_number() -> None:
    hole = pad("", 0, 0, kind="np_thru_hole", layers=ALL, drill=MM)
    bare = design(
        [("H1", "HOLE"), ("R1", "1k")],
        {"H1": (hole,), "R1": (pad("1"), pad("", MM, 0), pad("9", 0, 0, size=Size(0, 0)))},
        {"H1": mm(5, 0), "R1": mm(0, 0)},
        name="odd",
    )
    found = netted(bare, {"N": (("R1", "1"), ("R1", ""), ("R1", "9"), ("H1", ""))})
    found = with_board(found, tracks=(track(found, "t", "N", mm(1, 0), mm(5, 0)),))
    held = pieces(found)
    # the pad without a number joins the track and the numbered pad beside it, and names nothing;
    # the hole without plating has no copper; the pad without a size cannot be shaped
    assert held[of_net(found, "N")] == (Piece(("R1-1",), (), (("top", 4 * MM),), True),)
    assert held.unshaped == 1


def test_copper_without_a_net_is_counted() -> None:
    found = routed()
    loose = dataclasses.replace(track(found, "loose", "A", mm(30, 30), mm(31, 30)), net_id=None)
    held = pieces(with_board(found, tracks=(*board(found).tracks, loose)))
    assert held.no_net == 1 and dict(held) == dict(pieces(found))


def test_zone_fill_joins_and_an_unfilled_zone_does_not() -> None:
    found = without(routed(), "c-top")
    ring = (mm(8, 9), mm(10, 9), mm(10, 16), mm(8, 16))
    filled = with_board(found, zones=(zone(found, "z", "C", "Top", ring, filled=True),))
    assert of(filled, "C") == (Piece(("R1-1", "R2-1"), (), (), True),)
    assert pieces(filled).zones_unfilled == 0
    empty = with_board(found, zones=(zone(found, "z", "C", "Top", ring, filled=False),))
    assert of(empty, "C") == (Piece(("R1-1",)), Piece(("R2-1",)))
    held = pieces(empty)
    assert held.zones_unfilled == 1 and held.unfilled_nets == {of_net(found, "C")}
    below = with_board(found, zones=(zone(found, "z", "C", "Bottom", ring, filled=True),))
    assert of(below, "C") == (Piece((), (), (), True), Piece(("R1-1",)), Piece(("R2-1",)))


def test_arc_joins_its_ends() -> None:
    found = routed()
    assert len(of(without(found, "d"), "D")) == 2
    moved = with_board(found, arcs=(arc(found, "d", "D", mm(11, 12), mm(11.5, 12.5), mm(11, 13), "Bottom"),))
    assert len(of(moved, "D")) == 3


# --- size ------------------------------------------------------------------------------------------


def test_a_board_of_three_thousand_items_takes_seconds() -> None:
    """600 nets of two pads, two tracks and a via each: 3000 copper items, read well inside the bound."""
    count = 600
    refs = [(f"R{k}", "1k") for k in range(count)]
    pads = {ref: (pad("1", -MM, 0), pad("2", MM, 0, layers=("Bottom",))) for ref, _ in refs}
    at = {f"R{k}": Point(k % 30 * 4 * MM, k // 30 * 3 * MM) for k in range(count)}
    bare = design(refs, pads, at, name="large")
    found = netted(bare, {f"N{k}": ((f"R{k}", "1"), (f"R{k}", "2")) for k in range(count)})
    tracks, vias = [], []
    for k in range(count):
        centre = at[f"R{k}"]
        left, right = Point(centre.x - MM, centre.y), Point(centre.x + MM, centre.y)
        tracks.append(track(found, f"l{k}", f"N{k}", left, centre))
        tracks.append(track(found, f"r{k}", f"N{k}", centre, right, "Bottom"))
        vias.append(via(found, f"v{k}", f"N{k}", centre))
    large = with_board(found, tracks=tuple(tracks), vias=tuple(vias))
    started = time.perf_counter()
    held = pieces(large)
    elapsed = time.perf_counter() - started
    assert len(held) == count and all(len(found) == 1 and len(found[0].pads) == 2 for found in held.values())
    assert elapsed < 20, f"{elapsed:.1f} s for 3000 items"
