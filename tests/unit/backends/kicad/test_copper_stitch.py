# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Stitching vias (capability manual-copper, "Stitching vias"; change c0028): candidates along a polyline
and on a region grid, and the exact clearance test checked against brute force. Hermetic."""

from __future__ import annotations

import dataclasses
import math
import random
from fractions import Fraction

import pytest
from _copper import stitch
from _placed import Part, design_of, mm, pt

from fenolite.backends.kicad.copper import copper_uuid, edge_clearance_in_force, resolve_copper
from fenolite.backends.kicad.frame import find_pads, part_frame
from fenolite.backends.kicad.outline import board_outline
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.dsl import Anchor, PadEnd
from fenolite.geometry import dist2_point_segment
from fenolite.model.board import Arc, Keepout, Outline, Track, Via
from fenolite.model.circuit import NetClass
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet, Selector

SQUARE = (pt(0, 0), pt(10, 0), pt(10, 10), pt(0, 10))
GRID = [pt(2.5 * i, 2.5 * j) for j in (1, 2, 3) for i in (1, 2, 3)]


def _empty(*nets: str) -> Design:
    return design_of(extra_nets=nets or ("GND", "VIN"))


def _resolve(design: Design, *intents: object) -> tuple[list[Via], list[Issue]]:
    found: list[Issue] = []
    result = resolve_copper(design, intents, issues=found)  # type: ignore[arg-type]
    assert result.board is not None and design.board is not None
    created = [v for v in result.board.vias if v not in design.board.vias]
    return created, found


def _net(design: Design, name: str) -> str:
    return next(net.id for net in design.circuit.nets if net.name == name)


def _with(design: Design, **items: tuple[object, ...]) -> Design:
    assert design.board is not None
    return dataclasses.replace(design, board=dataclasses.replace(design.board, **items))  # type: ignore[arg-type]


def _user_via(design: Design, point: Point, net: str | None, diameter: int = 600_000, n: int = 1) -> Via:
    native = f"00000000-0000-4000-8000-{n:012d}"
    return Via(
        id=derived_id("via", "kicad", native),
        native_ids={"kicad": native},
        position=point,
        diameter=diameter,
        drill=diameter // 2,
        layers=("F.Cu", "B.Cu"),
        net_id=None if net is None else _net(design, net),
    )


def _user_track(
    design: Design, a: Point, b: Point, net: str | None, width: int = 200_000, n: int = 1
) -> Track:
    native = f"00000000-0000-4000-9000-{n:012d}"
    return Track(
        id=derived_id("trk", "kicad", native),
        native_ids={"kicad": native},
        start=a,
        end=b,
        width=width,
        layer="F.Cu",
        net_id=None if net is None else _net(design, net),
    )


# -- candidates


def test_along_a_line() -> None:
    vias, found = _resolve(_empty(), stitch("s", along=(pt(0, 0), pt(10, 0))))
    assert found == [] and [v.position for v in vias] == [pt(x, 0) for x in (0, 2.5, 5, 7.5, 10)]
    assert [v.native_ids["kicad"] for v in vias] == [copper_uuid("s", f"via[{k}]") for k in range(5)]
    assert {(v.diameter, v.drill, v.layers) for v in vias} == {(mm(0.6), mm(0.3), ("F.Cu", "B.Cu"))}


def test_along_division_rule() -> None:
    """Each segment is cut into the fewest equal parts no longer than the pitch; a vertex appears once."""
    exact, _ = _resolve(_empty(), stitch("s", pitch=mm(2.5), along=(pt(0, 0), pt(10, 0))))
    assert len(exact) == 5  # a length that is a whole number of pitches needs no extra part
    bent, _ = _resolve(_empty(), stitch("s", pitch=mm(4), along=(pt(0, 0), pt(6, 0), pt(6, 3))))
    assert [v.position for v in bent] == [pt(0, 0), pt(3, 0), pt(6, 0), pt(6, 3)]
    diagonal, _ = _resolve(_empty(), stitch("s", pitch=mm(5), along=(pt(0, 0), pt(3, 4), pt(3, 9))))
    assert [v.position for v in diagonal] == [pt(0, 0), pt(3, 4), pt(3, 9)]  # 5 mm long: one part each
    thirds, _ = _resolve(_empty(), stitch("s", pitch=mm(4), along=(Point(0, 0), Point(mm(10), 1))))
    # three parts of a line that is not axis-aligned: the division points round half to even
    assert [v.position for v in thirds] == [
        Point(0, 0),
        Point(3333333, 0),
        Point(6666667, 1),
        Point(mm(10), 1),
    ]


def test_region_grid_with_margin() -> None:
    vias, found = _resolve(
        _empty(), stitch("s", pitch=mm(2.5), region=SQUARE, origin=pt(0, 0), margin=mm(0.2))
    )
    assert found == [] and [v.position for v in vias] == GRID
    names = [copper_uuid("s", f"via[{i},{j}]") for j in (1, 2, 3) for i in (1, 2, 3)]
    assert [v.native_ids["kicad"] for v in vias] == names


def test_region_grid_is_global() -> None:
    """A growing region keeps the vias, and the ids, it already had."""
    small, _ = _resolve(_empty(), stitch("s", pitch=mm(2.5), region=SQUARE, origin=pt(0, 0)))
    wide = (pt(-5, 0), pt(15, 0), pt(15, 10), pt(-5, 10))
    large, _ = _resolve(_empty(), stitch("s", pitch=mm(2.5), region=wide, origin=pt(0, 0)))
    ids = {v.native_ids["kicad"]: v.position for v in large}
    assert all(ids[v.native_ids["kicad"]] == v.position for v in small) and len(large) > len(small)
    shifted, _ = _resolve(_empty(), stitch("s", pitch=mm(2.5), region=SQUARE, origin=pt(1, 1)))
    assert [v.position for v in shifted][0] == pt(1, 1) and len(shifted) == 16


def test_region_edges_are_exact() -> None:
    """A via exactly ``diameter / 2 + margin`` from an edge is kept; one nanometre closer is not."""
    ring = (pt(0, 0), pt(10, 0), pt(10, 10), pt(0, 10))
    kept, _ = _resolve(_empty(), stitch("s", pitch=mm(20), region=ring, origin=pt(0.5, 5), margin=mm(0.2)))
    assert [v.position for v in kept] == [pt(0.5, 5)]
    near, found = _resolve(
        _empty(), stitch("s", pitch=mm(20), region=ring, origin=Point(mm(0.5) - 1, mm(5)), margin=mm(0.2))
    )
    assert near == [] and [i.code for i in found] == ["kicad.copper.stitch-empty"]


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"along": (pt(0, 0), pt(1, 0)), "region": SQUARE},
        {"along": (pt(0, 0),)},
        {"region": (pt(0, 0), pt(1, 0))},
        {"region": (pt(0, 0), pt(4, 4), pt(4, 0), pt(0, 4))},
        {"along": (pt(0, 0), pt(1, 0)), "pitch": 0},
        {"along": (pt(0, 0), pt(1, 0)), "margin": -1},
    ],
)
def test_bad_stitch_intents(fields: dict[str, object]) -> None:
    pitch = fields.pop("pitch", mm(3))
    vias, found = _resolve(_empty(), stitch("s", pitch=pitch, **fields))  # type: ignore[arg-type]
    assert vias == [] and [(i.code, i.severity) for i in found] == [("kicad.copper.bad-intent", "error")]


def test_stitch_sizes_and_nets() -> None:
    line = (pt(0, 0), pt(10, 0))
    cls = NetClass(id="ncl_00000000-0000-4000-8000-000000000001", name="PWR", clearance=mm(0.2),
                   via_diameter=mm(0.8), via_drill=mm(0.4))  # fmt: skip
    classed = design_of(extra_nets=("GND",), classes=(cls,), class_of={"GND": "PWR"})
    vias, found = _resolve(classed, stitch("s", along=line, diameter=None, drill=None, clearance=None))
    assert found == [] and {(v.diameter, v.drill) for v in vias} == {(mm(0.8), mm(0.4))}
    for intent, code in (
        (stitch("s", along=line, clearance=None), "kicad.copper.size-missing"),
        (stitch("s", along=line, diameter=None), "kicad.copper.size-missing"),
        (stitch("s", along=line, clearance=-1), "kicad.copper.bad-size"),
        (stitch("s", along=line, net=None), "kicad.copper.no-net"),
        (stitch("s", along=line, net="NOPE"), "kicad.copper.unknown-net"),
    ):
        assert [i.code for i in _resolve(_empty(), intent)[1]] == [code]


# -- clearance


def test_region_with_margin_and_a_pad_to_avoid() -> None:
    design = design_of(
        Part("R1", "Mini_R_0603", 5, 5, nets={"1": "LED_DRV", "2": "LED_DRV"}), extra_nets=("GND",)
    )
    vias, found = _resolve(design, stitch("s", pitch=mm(2.5), region=SQUARE, origin=pt(0, 0), margin=mm(0.2)))
    assert [v.position for v in vias] == [p for p in GRID if p != pt(5, 5)]
    (issue,) = found
    assert (issue.code, issue.severity) == (
        "kicad.copper.stitch-skipped",
        "info",
    ) and "1 stitch" in issue.message


def test_own_net_via_touched() -> None:
    design = _empty()
    existing = _user_via(design, pt(5, 5), "GND")
    vias, found = _resolve(
        _with(design, vias=(existing,)), stitch("s", pitch=mm(2.5), region=SQUARE, origin=pt(0, 0))
    )
    assert [v.position for v in vias] == [p for p in GRID if p != pt(5, 5)]
    assert [i.code for i in found] == ["kicad.copper.stitch-skipped"]


def test_own_net_tracks_are_no_obstacle_and_other_nets_are() -> None:
    design = _empty()
    line = (pt(0, 0), pt(10, 0))
    own = _with(design, tracks=(_user_track(design, pt(0, 0), pt(10, 0), "GND"),))
    assert len(_resolve(own, stitch("s", along=line))[0]) == 5
    other = _with(design, tracks=(_user_track(design, pt(5, -3), pt(5, 3), "VIN"),))
    vias, found = _resolve(other, stitch("s", along=line))
    assert [v.position for v in vias] == [pt(x, 0) for x in (0, 2.5, 7.5, 10)] and len(found) == 1
    unnetted = _with(design, tracks=(_user_track(design, pt(5, -3), pt(5, 3), None),))
    assert len(_resolve(unnetted, stitch("s", along=line))[0]) == 4


def test_clearance_boundary_is_exact() -> None:
    """A via whose edge is exactly the clearance from other copper stays; one nanometre closer goes."""
    design = _empty()
    # via radius 0.3 mm, track half-width 0.1 mm, clearance 0.2 mm: the limit is 0.6 mm between axes
    at_limit = _with(design, tracks=(_user_track(design, pt(-5, 0.6), pt(5, 0.6), "VIN"),))
    assert len(_resolve(at_limit, stitch("s", pitch=mm(20), along=(pt(0, 0), pt(0, -10))))[0]) == 2
    closer = Track(**{**dataclasses.asdict(at_limit.board.tracks[0]), "start": Point(mm(-5), mm(0.6) - 1),  # type: ignore[union-attr]
                      "end": Point(mm(5), mm(0.6) - 1)})  # fmt: skip
    vias, _ = _resolve(
        _with(design, tracks=(closer,)), stitch("s", pitch=mm(20), along=(pt(0, 0), pt(0, -10)))
    )
    assert [v.position for v in vias] == [pt(0, -10)]


def test_arcs_holes_and_earlier_intents_count() -> None:
    design = _empty()
    arc = Arc(id="arc_00000000-0000-4000-8000-000000000001", start=pt(4, 1), mid=pt(5, 0), end=pt(6, 1),
              width=mm(0.2), layer="F.Cu", net_id=_net(design, "VIN"))  # fmt: skip
    vias, _ = _resolve(_with(design, arcs=(arc,)), stitch("s", along=(pt(0, 0), pt(10, 0))))
    assert pt(5, 0) not in [v.position for v in vias] and len(vias) == 4
    holes = design_of(Part("J1", "Mini_Edge_Cases", 5, 0), extra_nets=("GND",))
    near_hole, _ = _resolve(holes, stitch("s", pitch=mm(20), along=(pt(5, 2), pt(5, 30))))
    assert [v.position for v in near_hole] == [pt(5, 22), pt(5, 30)][-1:] or pt(5, 2) not in [
        v.position for v in near_hole
    ]
    first = stitch("a", net="VIN", along=(pt(0, 0), pt(10, 0)))
    second = stitch("b", net="GND", along=(pt(5, -5), pt(5, 5)), pitch=mm(5))
    both, found = _resolve(design, first, second)
    crossing = [v for v in both if v.native_ids["kicad"] == copper_uuid("b", "via[1]")]
    assert crossing == [] and [i.code for i in found] == ["kicad.copper.stitch-skipped"]


def test_candidates_of_one_stitch_do_not_stack() -> None:
    loop = (pt(0, 0), pt(3, 0), pt(0, 0))
    vias, found = _resolve(_empty(), stitch("s", along=loop))
    assert [v.position for v in vias] == [pt(0, 0), pt(3, 0)] and [i.code for i in found] == [
        "kicad.copper.stitch-skipped"
    ]


def test_stitch_empty() -> None:
    design = _empty()
    wall = _with(design, tracks=(_user_track(design, pt(-1, 0), pt(11, 0), "VIN", width=mm(2)),))
    vias, found = _resolve(wall, stitch("s", along=(pt(0, 0), pt(10, 0))))
    assert vias == [] and [(i.code, i.severity) for i in found] == [
        ("kicad.copper.stitch-skipped", "info"),
        ("kicad.copper.stitch-empty", "warning"),
    ]


def test_clearance_agrees_with_brute_force() -> None:
    """Over generated layouts, the vias kept are exactly the candidates that keep the clearance from every
    obstacle, decided here with rationals and no spatial index."""
    rng = random.Random(2028)
    clearance, diameter = mm(0.2), mm(0.6)
    for round_ in range(25):
        design = _empty()
        tracks = tuple(
            _user_track(
                design,
                Point(rng.randint(0, mm(20)), rng.randint(0, mm(20))),
                Point(rng.randint(0, mm(20)), rng.randint(0, mm(20))),
                rng.choice(["VIN", None]),
                width=rng.choice([mm(0.15), mm(0.4), 250_001]),
                n=n,
            )
            for n in range(1, 7)
        )
        vias = tuple(
            _user_via(
                design,
                Point(rng.randint(0, mm(20)), rng.randint(0, mm(20))),
                rng.choice(["VIN", "GND"]),
                diameter=rng.choice([mm(0.5), mm(0.8)]),
                n=n,
            )  # fmt: skip
            for n in range(1, 5)
        )
        layout = _with(design, tracks=tracks, vias=vias)
        region = (pt(0, 0), pt(20, 0), pt(20, 20), pt(0, 20))
        kept, _ = _resolve(layout, stitch("s", pitch=mm(1.7), region=region, origin=pt(0.3, 0.3)))

        def allowed(
            point: Point,
            tracks: tuple[Track, ...] = tracks,
            vias: tuple[Via, ...] = vias,
            design: Design = design,
        ) -> bool:
            for track in tracks:
                limit = Fraction(2 * clearance + diameter + track.width, 2) ** 2
                if dist2_point_segment(point, track.start, track.end) < limit:
                    return False
            for via in vias:
                distance = (point.x - via.position.x) ** 2 + (point.y - via.position.y) ** 2
                own = via.net_id == _net(design, "GND")
                reach = Fraction((0 if own else 2 * clearance) + diameter + via.diameter, 2) ** 2
                if distance <= reach if own else distance < reach:
                    return False
            return True

        grid = [
            Point(mm(0.3) + i * mm(1.7), mm(0.3) + j * mm(1.7))
            for j in range(12)
            for i in range(12)
            if mm(0.3) <= mm(0.3) + i * mm(1.7) <= mm(19.7) and mm(0.3) <= mm(0.3) + j * mm(1.7) <= mm(19.7)
        ]
        expected = [p for p in grid if allowed(p)]
        assert [v.position for v in kept] == expected, round_


# -- keep-outs and the board edge (c0074; H-K-STITCH-AVOID)

LINE = (pt(0, 0), pt(10, 0))
BOARD = (pt(0, -20), pt(40, -20), pt(40, 20), pt(0, 20))


def _keepout(*, no_vias: bool = True, layers: tuple[str, ...] = ("F.Cu", "B.Cu"), n: int = 1) -> Keepout:
    """A rule area over x from 4 mm to 6 mm."""
    ring = (pt(4, -2), pt(6, -2), pt(6, 2), pt(4, 2))
    return Keepout(id=derived_id("kpo", "test", str(n)), outline=ring, layers=layers, no_vias=no_vias)


def _outlined(design: Design, ring: tuple[Point, ...] = BOARD) -> Design:
    return _with(design, outline=Outline(id=derived_id("out", "test", "o"), points=ring))  # type: ignore[arg-type]


def _edge_rule(design: Design, minimum: int, *, name: str = "edge", priority: int = 0) -> Design:
    rule = Rule(
        id=derived_id("rul", "test", name),
        name=name,
        kind="edge_clearance",
        selector_a=Selector("all"),
        min=minimum,
        priority=priority,
    )
    old = design.rules.rules if design.rules is not None else ()
    return dataclasses.replace(design, rules=RuleSet(id=derived_id("rst", "test", "r"), rules=(*old, rule)))


def test_fence_across_a_keep_out() -> None:
    design = _with(_empty(), keepouts=(_keepout(),))
    vias, found = _resolve(design, stitch("s", along=LINE))
    assert [v.position for v in vias] == [pt(x, 0) for x in (0, 2.5, 7.5, 10)]
    (skipped,) = found
    assert skipped.code == "kicad.copper.stitch-skipped" and "1 stitch candidate" in skipped.message
    assert [v.native_ids["kicad"] for v in vias] == [copper_uuid("s", f"via[{k}]") for k in (0, 1, 3, 4)]


def test_keep_out_that_allows_vias_or_lies_on_no_copper_layer() -> None:
    for area in (_keepout(no_vias=False), _keepout(layers=("F.SilkS",))):
        vias, found = _resolve(_with(_empty(), keepouts=(area,)), stitch("s", along=LINE))
        assert len(vias) == 5 and found == []
    one_layer, _ = _resolve(_with(_empty(), keepouts=(_keepout(layers=("B.Cu",)),)), stitch("s", along=LINE))
    assert len(one_layer) == 4  # a through via crosses every copper layer
    wildcard, _ = _resolve(_with(_empty(), keepouts=(_keepout(layers=("*.Cu",)),)), stitch("s", along=LINE))
    assert len(wildcard) == 4


def test_via_disc_touching_a_keep_out_is_dropped() -> None:
    """The disc of 0.6 mm at x = 3.7 mm touches the area that starts at x = 4 mm; at 3.699 mm it clears."""
    design = _with(_empty(), keepouts=(_keepout(),))
    touching, _ = _resolve(design, stitch("s", along=(pt(3.7, 0), pt(3.7, 1)), pitch=mm(5)))
    clear, _ = _resolve(design, stitch("s", along=(pt(3.699, 0), pt(3.699, 1)), pitch=mm(5)))
    assert touching == [] and len(clear) == 2


def test_keep_outs_given_beside_the_design() -> None:
    found: list[Issue] = []
    result = resolve_copper(_empty(), (stitch("s", along=LINE),), issues=found, keepouts=(_keepout(),))  # type: ignore[arg-type]
    assert result.board is not None and len(result.board.vias) == 4


def test_fence_along_the_edge() -> None:
    design = _edge_rule(_outlined(_empty()), mm(0.5))
    vias, found = _resolve(design, stitch("s", along=(pt(0.4, -5), pt(0.4, 5))))
    assert vias == [] and [i.code for i in found] == [
        "kicad.copper.stitch-skipped",
        "kicad.copper.stitch-empty",
    ]
    assert found[1].severity == "warning"


def test_edge_clearance_is_measured_from_the_via_copper() -> None:
    """With 0.5 mm of clearance a via of 0.6 mm is legal from x = 0.8 mm: 0.3 mm of copper, then the gap."""
    design = _edge_rule(_outlined(_empty()), mm(0.5))
    at_limit, _ = _resolve(design, stitch("s", along=(pt(0.8, -5), pt(0.8, 5))))
    inside, _ = _resolve(design, stitch("s", along=(pt(0.799, -5), pt(0.799, 5))))
    assert len(at_limit) == 5 and inside == []


def test_no_closed_outline_no_edge_check() -> None:
    design = _edge_rule(_empty(), mm(0.5))
    assert board_outline(design).rings == ()
    vias, found = _resolve(design, stitch("s", along=(pt(0.4, -5), pt(0.4, 5))))
    assert len(vias) == 5 and found == []


def test_edge_clearance_in_force() -> None:
    plain = _outlined(_empty())
    assert edge_clearance_in_force(plain) == 0 and edge_clearance_in_force(plain, mm(0.3)) == mm(0.3)
    ruled = _edge_rule(plain, mm(0.5))
    assert edge_clearance_in_force(ruled, mm(0.3)) == mm(0.5)
    # the later rule governs: priority 1 is written last
    both = _edge_rule(ruled, mm(0.2), name="tight", priority=1)
    assert edge_clearance_in_force(both, mm(0.3)) == mm(0.2)
    vias, _ = _resolve(both, stitch("s", along=(pt(0.5, -5), pt(0.5, 5))))
    assert len(vias) == 5
    floor: list[Issue] = []
    result = resolve_copper(
        plain, (stitch("s", along=(pt(0.4, -5), pt(0.4, 5))),), issues=floor, edge_floor=mm(0.5)
    )  # type: ignore[arg-type]
    assert result.board is not None and result.board.vias == ()


def test_region_grid_keeps_off_a_cut_out() -> None:
    hole = (pt(4, 4), pt(6, 4), pt(6, 6), pt(4, 6))
    ring = (pt(-5, -5), pt(15, -5), pt(15, 15), pt(-5, 15))
    outline = Outline(id=derived_id("out", "test", "o"), points=ring, cutouts=(hole,))
    design = _edge_rule(_with(_empty(), outline=outline), mm(0.2))  # type: ignore[arg-type]
    vias, _ = _resolve(design, stitch("s", region=SQUARE, pitch=mm(2.5), origin=pt(0, 0), margin=mm(0.2)))
    assert pt(5, 5) not in [v.position for v in vias] and len(vias) == 8


# -- pad regions and grids in a part's frame (change c0111)

THERMAL: dict[str, object] = {"pitch": mm(1), "margin": mm(0.1)}
"""The thermal array of the scenarios: 1 mm pitch, 0.6 mm vias, 0.1 mm margin, 0.2 mm clearance."""
NINE = [(i, j) for j in (-1, 0, 1) for i in (-1, 0, 1)]


def _anchor_part(rot: float = 0, side: str = "top", **nets: str) -> Part:
    pads = {"1": "VIN", "4": "GND", **nets}
    return Part("U1", "Frame_Anchor", 20, 20, rot, side, nets=pads, library="Frame")  # type: ignore[arg-type]


def _locators(key: str, vias: list[Via]) -> dict[str, Point]:
    wanted = {copper_uuid(key, f"via[{i},{j}]"): f"via[{i},{j}]" for i in range(-3, 4) for j in range(-3, 4)}
    return {wanted[v.native_ids["kicad"]]: v.position for v in vias}


def test_pad_region_makes_a_thermal_array() -> None:
    """Scenario "Thermal array in a pad": the pad is no obstacle to its own array."""
    design = design_of(_anchor_part())
    vias, found = _resolve(design, stitch("ep", region=PadEnd("U1", "4", None), **THERMAL))
    assert found == []
    assert _locators("ep", vias) == {f"via[{i},{j}]": pt(21 + i, 20 + j) for i, j in NINE}
    assert [v.position for v in vias] == [pt(21 + i, 20 + j) for i, j in NINE], "in order of j then i"
    assert all(v.layers == ("F.Cu", "B.Cu") and v.net_id == _net(design, "GND") for v in vias)
    # the same region as a ring of board points keeps nothing: every candidate is in a pad
    ring = (pt(19.5, 18.5), pt(22.5, 18.5), pt(22.5, 21.5), pt(19.5, 21.5))
    none, blocked = _resolve(design, stitch("ring", region=ring, origin=pt(21, 20), **THERMAL))
    assert none == [] and [i.code for i in blocked] == [
        "kicad.copper.stitch-skipped",
        "kicad.copper.stitch-empty",
    ]


def test_pad_region_grid_turns_with_the_part() -> None:
    """Scenario "The grid turns with the part": 30° on the bottom, the same locators as at 0°."""
    design = design_of(_anchor_part(30, "bottom"))
    vias, found = _resolve(design, stitch("ep", region=PadEnd("U1", "4", None), **THERMAL))
    frame = part_frame(design, "U1", number="4")
    assert found == []
    assert _locators("ep", vias) == {f"via[{i},{j}]": frame.point(Point(mm(i), mm(j))) for i, j in NINE}
    flat, _ = _resolve(design_of(_anchor_part()), stitch("ep", region=PadEnd("U1", "4"), **THERMAL))
    assert {v.native_ids["kicad"] for v in vias} == {v.native_ids["kicad"] for v in flat}
    assert vias[4].position == find_pads(design, "U1", 4)[0].position, "via[0,0] is the pad's centre"
    assert {v.position for v in vias} != {v.position for v in flat}


def test_pad_region_of_another_net() -> None:
    """Scenario "A pad region of another net"."""
    design = design_of(_anchor_part(), Part("J1", "Mini_Edge_Cases", 40, 20))
    vias, found = _resolve(
        design,
        stitch("ep", net="VIN", region=PadEnd("U1", "4", None), **THERMAL),
        stitch("j1", region=PadEnd("J1", "1", None), **THERMAL),
    )
    assert vias == []
    assert [(i.where, i.code) for i in found] == [
        ("ep", "kicad.copper.net-conflict"),
        ("j1", "kicad.copper.bad-intent"),
    ]
    assert all(word in found[0].message for word in ("ep", "U1", "'4'"))
    assert all(word in found[1].message for word in ("j1", "J1", "'1'"))


def test_keepout_across_a_pad_region() -> None:
    """Scenario "A keep-out across a pad region": the pad's own copper is no obstacle, the keep-out is."""
    ring = (pt(21.6, 18.5), pt(22.4, 18.5), pt(22.4, 21.5), pt(21.6, 21.5))
    area = Keepout(id=derived_id("kpo", "test", "pad"), outline=ring, layers=("F.Cu", "B.Cu"), no_vias=True)
    design = _with(design_of(_anchor_part()), keepouts=(area,))
    vias, found = _resolve(design, stitch("ep", region=PadEnd("U1", "4", None), **THERMAL))
    assert sorted(v.position for v in vias) == sorted(pt(x, 20 + j) for x in (20, 21) for j in (-1, 0, 1))
    assert [i.code for i in found] == ["kicad.copper.stitch-skipped"]
    assert " 3 stitch candidate(s)" in found[0].message


def test_pad_region_with_an_anchored_origin() -> None:
    """An anchored origin lays the grid of a pad region from that anchor, in its part's frame."""
    design = design_of(_anchor_part(90))
    origin = Anchor("U1", "4", None, Point(mm(0.5), mm(0.5)))
    vias, found = _resolve(design, stitch("ep", region=PadEnd("U1", "4"), origin=origin, **THERMAL))
    frame = part_frame(design, "U1", number=4)
    assert found == []
    assert _locators("ep", vias) == {
        f"via[{i},{j}]": frame.point(Point(mm(0.5 + i), mm(0.5 + j))) for j in (-1, 0) for i in (-1, 0)
    }


def test_ring_region_with_an_anchored_origin() -> None:
    """A ring region whose origin is an anchor: the grid is laid in the anchor's part's frame, and the
    anchors among the ring's points are resolved first."""
    design = design_of(_anchor_part(30, "bottom"), extra_nets=("AUX",))
    corners = [Point(mm(4), mm(-2)), Point(mm(8), mm(-2)), Point(mm(8), mm(2)), Point(mm(4), mm(2))]
    ring = tuple(Anchor("U1", None, None, corner) for corner in corners)
    origin = Anchor("U1", None, None, Point(mm(6), 0))
    vias, found = _resolve(design, stitch("s", net="AUX", region=ring, origin=origin, **THERMAL))
    frame = part_frame(design, "U1")
    assert found == []
    assert _locators("s", vias) == {f"via[{i},{j}]": frame.point(Point(mm(6 + i), mm(j))) for i, j in NINE}
    # a board-point origin keeps the board-frame grid for the same ring
    start = frame.point(Point(mm(6), 0))
    board_grid, _ = _resolve(design, stitch("s", net="AUX", region=ring, origin=start, **THERMAL))
    assert all(
        (v.position.x - start.x) % mm(1) == 0 and (v.position.y - start.y) % mm(1) == 0 for v in board_grid
    )
    assert board_grid and {v.position for v in board_grid} != {v.position for v in vias}


def test_along_takes_anchors() -> None:
    design = design_of(_anchor_part(90), extra_nets=("AUX",))
    line = (Anchor("U1", None, None, Point(mm(6), mm(-4))), Anchor("U1", None, None, Point(mm(6), mm(4))))
    vias, found = _resolve(design, stitch("s", net="AUX", along=line, pitch=mm(2)))
    # at 90° on the top the offset (6, y) of the part is the board point (20 + y, 20 − 6)
    assert [v.position for v in vias] == [pt(16 + 2 * k, 14) for k in range(5)] and found == []


def test_other_pads_and_the_holes_of_the_region_still_block() -> None:
    """The exemption covers only the copper entries of the region's own pads."""
    # a through-hole pad: a disc of 1.7 mm with a 1 mm hole, so the centre candidate meets the hole
    design = design_of(Part("J1", "Mini_Edge_Cases", 40, 20, nets={"4": "GND"}))
    small = {"diameter": mm(0.2), "drill": mm(0.1), "clearance": mm(0.05), "pitch": mm(0.7)}
    vias, found = _resolve(design, stitch("tht", region=PadEnd("J1", "4"), **small))
    assert sorted(v.position for v in vias) == sorted(
        [pt(36 - 0.7, 20), pt(36 + 0.7, 20), pt(36, 20 - 0.7), pt(36, 20 + 0.7)]
    )
    assert [i.code for i in found] == ["kicad.copper.stitch-skipped"] and " 1 stitch" in found[0].message
    # a pad of the same net that the region does not name is an obstacle: pads 3 and 4 are both on GND
    near = design_of(_anchor_part(**{"3": "GND"}))
    wide = {"clearance": mm(3), "pitch": mm(1), "margin": mm(0.1)}
    vias, found = _resolve(near, stitch("ep", region=PadEnd("U1", "4"), **wide))
    # pad 3 ends at x = 16.75 mm: with 3 mm of clearance a via needs its centre at x ≥ 20.05 mm
    assert sorted({v.position.x for v in vias}) == [mm(21), mm(22)]
    assert " 3 stitch candidate(s)" in found[0].message


def test_pad_region_on_the_bottom_uses_the_bottom_copper() -> None:
    design = design_of(_anchor_part(0, "bottom"))
    assert [e.layer for e in find_pads(design, "U1", 4)[0].copper] == ["B.Cu"]
    vias, found = _resolve(design, stitch("ep", region=PadEnd("U1", "4"), **THERMAL))
    assert len(vias) == 9 and found == []


def _inside_shape(shape: str, w: float, h: float, x: float, y: float, grow: float) -> bool:
    """Whether the pad-frame point lies in the pad of ``shape`` and size ``w`` x ``h`` grown by ``grow``
    (floats, nanometres): the pad as its definition draws it, not as the copper entries hold it."""
    ax, ay = abs(x), abs(y)
    if shape == "circle":
        return math.hypot(ax, ay) <= w / 2 + grow
    if shape == "rect":
        return ax <= w / 2 + grow and ay <= h / 2 + grow
    radius = min(w, h) / 2 if shape == "oval" else 0.25 * min(w, h)
    cx, cy = max(ax - (w / 2 - radius), 0.0), max(ay - (h / 2 - radius), 0.0)
    return math.hypot(cx, cy) <= radius + grow


@pytest.mark.parametrize("angle", [0, 30])
@pytest.mark.parametrize(
    ("number", "shape", "w", "h"),
    [
        ("1", "circle", 0.8, 0.8),
        ("2", "rect", 0.8, 0.6),
        ("3", "oval", 1.0, 0.6),
        ("4", "roundrect", 1.0, 0.8),
    ],
)
def test_exact_inside_test_against_sampling(number: str, shape: str, w: float, h: float, angle: int) -> None:
    """The exact test of a pad region against a 10 µm sampling of the pad: no sampled candidate is kept
    whose disc leaves the pad, and every candidate whose disc stays 2 µm inside it is kept."""
    from fenolite.backends.kicad.copper import _disc_in_entry  # pyright: ignore[reportPrivateUsage]

    design = design_of(Part("U1", "Frame_Shapes", 10, 10, angle, library="Frame"))
    (pad,) = find_pads(design, "U1", number)
    (entry,) = pad.copper
    reach = mm(0.3)  # a via of 0.2 mm with a margin of 0.05 mm: a disc of radius 0.15 mm
    radius = reach / 2
    turn = math.radians(pad.rotation / 1_000_000)
    cos, sin = math.cos(turn), math.sin(turn)
    rim = [
        (radius * math.cos(2 * math.pi * k / 32), radius * math.sin(2 * math.pi * k / 32)) for k in range(32)
    ]

    def within(dx: float, dy: float, grow: float) -> bool:
        return _inside_shape(shape, mm(w), mm(h), dx * cos - dy * sin, dx * sin + dy * cos, grow)

    step, half = 10_000, mm(max(w, h)) // 2 + 20_000
    kept = wrong = missed = 0
    for sx in range(-half, half + 1, step):
        for sy in range(-half, half + 1, step):
            exact = _disc_in_entry(Point(pad.position.x + sx, pad.position.y + sy), entry, reach)
            kept += exact
            if exact:
                wrong += not all(within(sx + rx, sy + ry, 2.0) for rx, ry in rim)
            elif within(sx, sy, -radius - 2_000):
                missed += 1
    assert kept > 100, "the sampling must reach inside the pad"
    assert wrong == 0, f"{wrong} kept candidate(s) whose disc leaves the {shape} pad at {angle}°"
    assert missed == 0, f"{missed} candidate(s) refused although the disc stays 2 µm inside the pad"
