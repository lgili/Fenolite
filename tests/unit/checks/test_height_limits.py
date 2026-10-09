# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``checks.placement.judge_heights`` and ``heights_of`` on authored layouts (capability placement, "Height
limits judged"; change c0140). Every layout is built by hand here, with round values invented for these
tests: square extents of 2 mm around each part, rule areas drawn as squares."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

from fenolite.backends.base import PlacedExtent
from fenolite.checks.placement import RuleReport, heights_of, judge_heights, rules_of
from fenolite.core.coords import Point, Size
from fenolite.model.board import (
    Board,
    ComponentBody,
    FootprintAttribute,
    FootprintInstance,
    Keepout,
    Outline,
    Pad,
    Side,
)
from fenolite.model.circuit import Circuit, Component
from fenolite.model.design import Design
from fenolite.model.rules import HeightLimit, RuleSet

MM = 1_000_000


def at(x: float, y: float) -> Point:
    return Point(round(x * MM), round(y * MM))


def square(x: float, y: float, half: float) -> tuple[Point, ...]:
    return (at(x - half, y - half), at(x + half, y - half), at(x + half, y + half), at(x - half, y + half))


def body(ref: str, height_mm: float) -> ComponentBody:
    return ComponentBody(id=f"bdy_{ref}", kind="extruded", height=round(height_mm * MM))


class Board_:
    """A 50 mm × 30 mm board, its parts and rule areas."""

    def __init__(self) -> None:
        self.components: list[Component] = []
        self.footprints: list[FootprintInstance] = []
        self.keepouts: list[Keepout] = []
        self.extents: list[PlacedExtent] = []

    def part(
        self,
        ref: str,
        x: float,
        y: float,
        *,
        height: float | None = None,
        side: Side = "top",
        attributes: tuple[FootprintAttribute, ...] = (),
        source: str = "courtyard",
        pads: Sequence[Pad] = (),
    ) -> None:
        self.components.append(Component(id=f"cmp_{ref}", ref=ref, properties={"fenolite.path": ref}))
        bodies = () if height is None else (body(ref, height),)
        self.footprints.append(
            FootprintInstance(
                id=f"fpi_{ref}",
                component_id=f"cmp_{ref}",
                lib_ref="",
                position=at(x, y),
                side=side,
                attributes=attributes,
                bodies=bodies,
                pads=tuple(pads),
            )
        )
        ring = (square(x, y, 1),)
        front, back = (ring, ()) if side == "top" else ((), ring)
        self.extents.append(PlacedExtent(f"fpi_{ref}", side, front, back, source))  # type: ignore[arg-type]

    def area(self, name: str, outline: tuple[Point, ...], layers: tuple[str, ...] = ("F.Cu",)) -> None:
        self.keepouts.append(
            Keepout(id=f"kpo_{name}_{len(self.keepouts)}", outline=outline, layers=layers, name=name)
        )

    def design(self, limits: Sequence[HeightLimit] = ()) -> Design:
        base = Design.new("heights", seed=0)
        assert base.rules is not None
        board = Board(
            id="brd_1",
            outline=Outline(id="out_1", points=(at(0, 0), at(50, 0), at(50, 30), at(0, 30))),
            footprints=tuple(self.footprints),
            keepouts=tuple(self.keepouts),
        )
        return dataclasses.replace(
            base,
            circuit=Circuit(components=tuple(self.components)),
            board=board,
            rules=dataclasses.replace(base.rules, heights=tuple(limits)),
        )


def lid_board(j1: float = 9) -> Board_:
    """The area ``LID`` on ``F.Cu`` over the top-side parts U2, J1 and R1, the bottom-side B1 and the
    ``dnp`` part R2; P1 lies outside it."""
    layout = Board_()
    layout.area("LID", square(10, 10, 8))
    layout.part("U2", 6, 6, height=3)
    layout.part("J1", 10, 10, height=j1)
    layout.part("R1", 14, 14)
    layout.part("B1", 6, 14, height=9, side="bottom")
    layout.part("R2", 14, 6, height=12, attributes=("dnp",))
    layout.part("P1", 40, 20, height=20)
    return layout


def run(layout: Board_, limits: Sequence[HeightLimit]) -> RuleReport:
    design = layout.design(limits)
    return judge_heights(design, rules_of(design).heights, heights_of(design, None), extents=layout.extents)


def test_height_limit_on_one_side() -> None:
    report = run(lid_board(), (HeightLimit("LID", 5 * MM),))
    found = [(i.code, i.severity, i.where) for i in report.issues]
    assert found == [
        ("placement.height-unknown", "warning", "R1"),
        ("placement.too-tall", "error", "J1"),
    ]
    tall = report.issues[1]
    assert "LID" in tall.message and "5 mm" in tall.message and "9 mm" in tall.message
    unknown = report.issues[0]
    assert "LID" in unknown.message and "5 mm" in unknown.message
    assert report.counts == {"height": {"judged": 3, "failed": 1, "unknown": 1}}
    assert report.judged == 3


def test_the_limit_sets_the_severity() -> None:
    report = run(lid_board(), (HeightLimit("LID", 5 * MM, "warning"),))
    assert [(i.code, i.severity) for i in report.issues if i.code == "placement.too-tall"] == [
        ("placement.too-tall", "warning")
    ]


def test_equal_to_the_limit_and_an_inner_area() -> None:
    layout = lid_board(j1=5)
    layout.area("MID", square(10, 10, 2), layers=("In1.Cu",))
    report = run(layout, (HeightLimit("LID", 5 * MM), HeightLimit("MID", MM)))
    assert all(i.where != "J1" for i in report.issues)
    assert report.counts == {"height": {"judged": 3, "failed": 0, "unknown": 1}}


def test_a_bottom_area_judges_bottom_parts() -> None:
    layout = lid_board()
    layout.area("UNDER", square(6, 14, 2), layers=("B.Cu",))
    report = run(layout, (HeightLimit("UNDER", 5 * MM),))
    assert [(i.code, i.where) for i in report.issues] == [("placement.too-tall", "B1")]


def test_rings_that_only_touch_do_not_meet() -> None:
    layout = Board_()
    layout.part("J1", 10, 10, height=9)
    layout.area("LID", (at(11, 9), at(13, 9), at(13, 11), at(11, 11)))  # shares the edge x = 11 mm
    assert run(layout, (HeightLimit("LID", 5 * MM),)).issues == ()


def test_a_limit_without_its_area() -> None:
    report = run(lid_board(), (HeightLimit("FAN", 12 * MM),))
    (found,) = report.issues
    assert (found.code, found.severity, found.where) == ("placement.rule-unresolved", "error", "FAN")
    assert "FAN" in found.message
    assert report.counts == {"height": {"judged": 0, "failed": 0, "unknown": 0}}


def test_two_areas_of_one_name_give_one_finding() -> None:
    layout = lid_board()
    layout.area("LID", square(10, 10, 3))
    report = run(layout, (HeightLimit("LID", 5 * MM),))
    assert [i.where for i in report.issues if i.code == "placement.too-tall"] == ["J1"]


def test_a_part_without_a_courtyard() -> None:
    layout = Board_()
    layout.area("LID", square(10, 10, 8))
    layout.part("J1", 10, 10, height=9, source="pads")
    (found,) = run(layout, (HeightLimit("LID", 5 * MM),)).issues
    assert found.code == "placement.too-tall"
    assert found.message.endswith("(approximate extent)")


def test_board_only_and_mounting_holes_are_judged_only_with_a_height() -> None:
    hole = Pad(
        id="pad_h", number="", kind="np_thru_hole", shape="circle", position=at(0, 0), size=Size(MM, MM)
    )
    layout = Board_()
    layout.area("LID", square(10, 10, 8))
    layout.part("LOGO", 8, 8, attributes=("board_only",))
    layout.part("H1", 12, 12, pads=(hole,))
    layout.part("H2", 12, 8, height=9, pads=(hole,))
    report = run(layout, (HeightLimit("LID", 5 * MM),))
    assert [(i.code, i.where) for i in report.issues] == [("placement.too-tall", "H2")]
    assert report.counts == {"height": {"judged": 1, "failed": 1, "unknown": 0}}


def test_a_part_off_the_board_is_not_judged() -> None:
    layout = Board_()
    layout.area("LID", square(55, 10, 8))
    layout.part("J1", 55, 10, height=9)
    assert run(layout, (HeightLimit("LID", 5 * MM),)).issues == ()


def test_no_limit_judges_nothing() -> None:
    report = run(lid_board(), ())
    assert report.issues == () and report.counts == {}


def test_issues_are_sorted_and_the_function_is_pure() -> None:
    limits = (HeightLimit("LID", 5 * MM), HeightLimit("FAN", MM))
    first, second = run(lid_board(), limits), run(lid_board(), limits)
    assert first == second
    keys = [(i.code, i.where, i.message) for i in first.issues]
    assert keys == sorted(keys)


def test_heights_of_the_board_first_of_the_stored_model_second() -> None:
    stored = Board_()
    stored.part("J1", 10, 10, height=9)
    stored.part("R1", 14, 14)
    model = stored.design()
    kicad = Board_()
    kicad.part("J1", 20, 20)
    kicad.part("R1", 14, 14)
    kicad_design = kicad.design()
    altium = Board_()
    altium.part("J1", 20, 20, height=7)
    altium.part("R1", 14, 14)
    altium_design = altium.design()
    assert heights_of(kicad_design, model) == {"fpi_J1": 9 * MM, "fpi_R1": None}
    assert heights_of(altium_design, model) == {"fpi_J1": 7 * MM, "fpi_R1": None}
    assert heights_of(kicad_design, None) == {"fpi_J1": None, "fpi_R1": None}


def test_rules_of_gives_the_limits() -> None:
    limits = (HeightLimit("FAN", MM), HeightLimit("LID", 5 * MM))
    design = lid_board().design(limits)
    rules = rules_of(design)
    assert rules.heights == limits and bool(rules)
    assert not rules_of(dataclasses.replace(design, rules=RuleSet(id="rst_1")))
