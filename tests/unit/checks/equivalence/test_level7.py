# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Level 7 compares exact geometry (capability design-equivalence, "Level 7 compares exact geometry" and
"Level 7 normalisation"; change c0278)."""

from __future__ import annotations

import dataclasses

from _cases import footprint, two_layer, with_footprint

from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.checks.equivalence import LevelResult, Tolerances, compare_designs
from fenolite.checks.equivalence.model import EXACT
from fenolite.core.coords import Point
from fenolite.model.board import Board, FootprintInstance, Outline, OutlineArc, ZoneFill
from fenolite.model.design import Design


def level7(a: Design, b: Design, tolerances: Tolerances = EXACT) -> LevelResult:
    report = compare_designs(a, b, level=7, tolerances=tolerances, strict=True)
    assert [level.level for level in report.levels] == [1, 2, 3, 4, 5, 6, 7]
    return report.levels[-1]


def board(design: Design) -> Board:
    assert design.board is not None
    return design.board


def with_board(design: Design, **changes: object) -> Design:
    return dataclasses.replace(design, board=dataclasses.replace(board(design), **changes))


OUTLINE = Outline(
    id="out-1",
    points=(Point(0, 0), Point(50_000_000, 0), Point(50_000_000, 30_000_000), Point(0, 30_000_000)),
    arcs=(OutlineArc(0, 1, Point(52_000_000, 15_000_000)),),
)


def test_a_design_against_itself_and_a_copy() -> None:
    source = two_layer()
    assert level7(source, source).differences == ()
    copy = read_board(write_board(source, target=10).text, file="copy.kicad_pcb")
    report = compare_designs(source, copy, level=7, strict=True)
    assert report.equivalent, report.differences
    assert report.levels[-1].name == "geometry"


def test_levels_6_and_7_on_request() -> None:
    from fenolite.checks.equivalence import max_level

    source = two_layer()
    report = compare_designs(source, source, level=7, strict=True)
    assert len(report.levels) == 7 and report.equivalent and max_level(source, source) == 5


def test_zone_refilled_is_equal() -> None:
    source = two_layer()
    zone = board(source).zones[0]
    refilled = dataclasses.replace(
        zone, fills=(ZoneFill(zone.layers[0], (Point(1, 1), Point(9, 1), Point(9, 9))),), filled=False
    )
    copy = with_board(source, zones=(refilled, *board(source).zones[1:]))
    assert level7(source, copy).differences == ()


def test_zone_fields() -> None:
    source = two_layer()
    zone = board(source).zones[0]
    changed = dataclasses.replace(
        zone, priority=zone.priority + 1, settings=dataclasses.replace(zone.settings, clearance=1)
    )
    found = [(d.kind, d.field) for d in level7(source, with_board(source, zones=(changed,))).differences]
    assert found == [("zone-field", "priority"), ("zone-field", "settings.clearance")]


def test_silkscreen_field_moved() -> None:
    source = two_layer()

    def moved(found: FootprintInstance) -> FootprintInstance:
        fields = tuple(
            dataclasses.replace(f, position=Point(f.position.x + 100_000, f.position.y))
            if f.name == "Reference"
            else f
            for f in found.fields
        )
        return dataclasses.replace(found, fields=fields)

    copy = with_footprint(source, "R1", moved)
    assert footprint(copy, "R1") != footprint(source, "R1")
    found = [(d.kind, d.where, d.field) for d in level7(source, copy).differences]
    assert found == [("field-pose", "R1:Reference", "position")]
    assert level7(source, copy, Tolerances(length_nm=100_000)).differences == ()


def test_outline_arc_changed() -> None:
    source = with_board(two_layer(), outline=OUTLINE)
    other = dataclasses.replace(OUTLINE, arcs=(OutlineArc(0, 1, Point(53_000_000, 15_000_000)),))
    found = level7(source, with_board(source, outline=other)).differences
    assert [(d.kind, bool(d.a), bool(d.b)) for d in found] == [
        ("outline-missing", True, False),
        ("outline-missing", False, True),
    ]


def test_ring_drawn_the_other_way() -> None:
    source = with_board(two_layer(), outline=OUTLINE)
    p = OUTLINE.points
    # clockwise from another start: (50,30) (50,0) (0,0) (0,30); the arc edge (50,0)-(50,30) is edge 0 now
    other = Outline(
        id="out-2", points=(p[2], p[1], p[0], p[3]), arcs=(OutlineArc(0, 0, Point(52_000_000, 15_000_000)),)
    )
    assert level7(source, with_board(source, outline=other)).differences == ()


def test_board_text_and_graphic() -> None:
    source = two_layer()
    text = board(source).texts[0]
    copy = with_board(source, texts=(dataclasses.replace(text, rotation=90_000_000),))
    assert [(d.kind, d.where, d.field) for d in level7(source, copy).differences] == [
        ("text-field", "board:F.SilkS:FENOLITE", "rotation")
    ]
    gone = with_board(source, texts=(), graphics=board(source).graphics[:-1])
    kinds = sorted(d.kind for d in level7(source, gone).differences)
    assert kinds == ["graphic-missing", "text-missing"]
