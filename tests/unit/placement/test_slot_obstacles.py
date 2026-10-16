# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Slots are placement obstacles (capability constrained-board-placement, "Slots are placement obstacles";
change c0170): the constrained placer's hard checks, its preview and the body-volume analysis take the
rings of ``model.outline.outline_items``, so a slot is judged as the same ring drawn as a cut-out."""

from __future__ import annotations

import dataclasses
import runpy
from pathlib import Path

from fenolite.analysis.body_volumes import VolumeConstraints, check_body_volumes
from fenolite.backends.base import BoardFrame, PlacedExtent
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import Design as Script
from fenolite.dsl import to_model
from fenolite.model.board import ComponentBody, FootprintInstance, OutlineArc
from fenolite.model.design import Design
from fenolite.model.outline import slot_ring
from fenolite.placement.constrained_legality import check_constraints
from fenolite.placement.constraints import PlacementConstraints
from fenolite.placement.legality import outline_rings
from fenolite.placement.preview import placement_preview

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "data" / "slots" / "design.py"
MM = 1_000_000


def _fixture() -> Design:
    script = runpy.run_path(str(FIXTURE))["design"]
    assert isinstance(script, Script)
    return to_model(script)


def _s1() -> Point:
    """The centre of the lone slot ``S1`` of the fixture (12 × 2 mm, turned 30°)."""
    board = _fixture().board
    assert board is not None and board.outline is not None
    return next(s.center for s in board.outline.slots if s.name == "S1")


def _clear() -> Point:
    """A point of the board 15 mm right and 20 mm below ``S1``, clear of every ring."""
    return Point(_s1().x + 15 * MM, _s1().y + 20 * MM)


def _as_cutout(design: Design) -> Design:
    """``design`` with ``S1`` drawn as a cut-out of the same ring (its stadium) instead of a slot."""
    board = design.board
    assert board is not None and board.outline is not None
    outline = board.outline
    (slot,) = [s for s in outline.slots if s.name == "S1"]
    item = slot_ring(slot)
    ring = len(outline.cutouts) + 1
    arcs = (*outline.arcs, *(OutlineArc(ring, k, mid) for k, mid in enumerate(item.mids) if mid is not None))
    changed = dataclasses.replace(
        outline,
        cutouts=(*outline.cutouts, item.points),
        arcs=tuple(sorted(arcs, key=lambda arc: (arc.ring, arc.edge))),
        slots=tuple(s for s in outline.slots if s.name != "S1"),
    )
    return dataclasses.replace(design, board=dataclasses.replace(board, outline=changed))


def _square(centre: Point, half: int) -> tuple[Point, ...]:
    x, y = centre.x, centre.y
    return (
        Point(x - half, y - half),
        Point(x + half, y - half),
        Point(x + half, y + half),
        Point(x - half, y + half),
    )


class _Frame:
    """An authored frame: one courtyard of 1 mm about ``centre`` and no pads."""

    def __init__(self, centre: Point) -> None:
        self.centre = centre

    def board_pads(self, design: Design, *, issues: object = None) -> tuple[()]:
        return ()

    def placed_extents(self, design: Design, *, issues: object = None) -> tuple[PlacedExtent, ...]:
        return (PlacedExtent("F1", "top", front=(_square(self.centre, MM // 2),), source="courtyard"),)

    def board_edges(self, design: Design, *, issues: object = None) -> None:
        return None


def _hard(design: Design, centre: Point) -> tuple[str, ...]:
    frame = _Frame(centre)
    assert isinstance(frame, BoardFrame)
    return check_constraints(design, frame, PlacementConstraints()).hard


def test_a_footprint_over_a_slot() -> None:
    """Scenario "A footprint over a slot": the courtyard over ``S1`` is reported as overlapping a cut-out,
    with the same hard findings as for the same ring drawn as a cut-out."""
    slot = _hard(_fixture(), _s1())
    drawn = _hard(_as_cutout(_fixture()), _s1())
    assert "cutout:F1" in slot and slot == drawn


def test_a_footprint_clear_of_the_slots() -> None:
    assert "cutout:F1" not in _hard(_fixture(), _clear())


def test_the_rings_hold_each_slot_polygonised() -> None:
    design = _fixture()
    assert design.board is not None and design.board.outline is not None
    rings = outline_rings(design.board.outline)
    assert len(rings) == 1 + 1 + 3  # the board, the cut-out, S1, S2 and S3
    assert rings[0] == design.board.outline.points and rings[1] == design.board.outline.cutouts[0]
    assert all(len(ring) > 4 for ring in rings[2:])


def test_the_preview_draws_the_slots() -> None:
    design = _fixture()
    svg = placement_preview(design, _Frame(_s1()), face="top")  # type: ignore[arg-type]
    path = next(line for line in svg.splitlines() if line.startswith("<path"))
    assert path.count("M ") == 5


def _body_over(design: Design, centre: Point, half: int) -> Design:
    ring = _square(Point(0, 0), half)
    body = ComponentBody(
        id=derived_id("bdy", "test", "pin"),
        kind="extruded",
        height=MM,
        z_min=-MM // 2,
        z_max=MM,
        outline=ring,
    )
    fp = FootprintInstance(
        id=derived_id("fp", "test", "pin"), component_id="", lib_ref="", position=centre, bodies=(body,)
    )
    assert design.board is not None
    return dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=(fp,)))


def test_a_body_through_a_slot_meets_no_board() -> None:
    """A body that reaches below the surface entirely inside ``S1`` meets no board material, as one inside
    a cut-out; outside the slot it penetrates the board."""
    constraints = VolumeConstraints(board_thickness=1_600_000)
    inside = check_body_volumes(_body_over(_fixture(), _s1(), MM // 4), constraints)
    assert not [f for f in inside.findings if f.code == "body.board-penetration"]
    drawn = check_body_volumes(_body_over(_as_cutout(_fixture()), _s1(), MM // 4), constraints)
    assert not [f for f in drawn.findings if f.code == "body.board-penetration"]
    outside = check_body_volumes(_body_over(_fixture(), _clear(), MM // 4), constraints)
    assert [f for f in outside.findings if f.code == "body.board-penetration"]
