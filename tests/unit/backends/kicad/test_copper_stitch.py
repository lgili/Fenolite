# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Stitching vias (capability manual-copper, "Stitching vias"; change c0028): candidates along a polyline
and on a region grid, and the exact clearance test checked against brute force. Hermetic."""

from __future__ import annotations

import dataclasses
import random
from fractions import Fraction

import pytest
from _copper import stitch
from _placed import Part, design_of, mm, pt

from fenolite.backends.kicad.copper import copper_uuid, resolve_copper
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.geometry import dist2_point_segment
from fenolite.model.board import Arc, Track, Via
from fenolite.model.circuit import NetClass
from fenolite.model.design import Design

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
