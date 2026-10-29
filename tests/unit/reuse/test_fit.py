# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.reuse.fit_block`` and ``fit_rigid`` (change c0210; capability layout-reuse, "Block copy by
pad fit"), on the authored boards of ``tests/_reusebench.py``. Hermetic."""

from __future__ import annotations

import dataclasses
from math import isqrt

import pytest
from _reusebench import CHIP, DEFINITIONS, IC6, LIBRARY, NETS, WIDE, layout, reference, target, y_up
from _ties import MM, TieBoard

from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.mod import prepare_authored_definition
from fenolite.backends.kicad.replace import move_footprint
from fenolite.core.coords import Point
from fenolite.dsl import Footprint, nm
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef
from fenolite.reuse import BlockFit, Placement, fit_block, fit_rigid, moved_placement

BLOCK = ("U1", "R1", "R2", "R3", "R4")
UM = 1_000


def _applied(design: Design, fit: BlockFit) -> Design:
    """``design`` with every placed part of ``fit`` moved, as the command moves them."""
    for part in fit.placed:
        placement = part.placement
        assert placement is not None
        if placement != part.before:
            design = move_footprint(
                design,
                part.footprint_id,
                at=placement.at,
                rotation=placement.rotation,
                side=placement.side,
                definitions=DEFINITIONS,
            )
    return design


def _far(a: Point, b: Point) -> int:
    return isqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def _landing(design: Design, fit: BlockFit) -> int:
    """The largest distance of a pad of a placed part from its goal, on ``design`` after the moves."""
    records = {(record.footprint_id, record.number): record for record in board_pads(design)}
    return max(
        _far(records[(part.footprint_id, match.number)].position, match.goal)
        for part in fit.placed
        for match in part.pads
    )


def test_the_plain_block() -> None:
    """Each part is placed by its pads: ``R2`` turned by a further 90° with the block, ``R4`` on the
    bottom as its reference part is, and every pad on its goal."""
    design = target()
    fit = fit_block(layout(reference()), layout(design), BLOCK)
    assert fit.issues == () and fit.flipped is False
    assert fit.transform is not None and fit.transform.mirror is False
    placed = {part.ref: part.placement for part in fit.parts}
    assert placed["U1"] == Placement(Point(42 * MM, 18 * MM), 90_000_000, "top")
    assert placed["R2"] == Placement(Point(42 * MM, 12 * MM), 180_000_000, "top")
    assert placed["R4"] == Placement(Point(42 * MM, 24 * MM), 180_000_000, "bottom")
    assert all(part.residual == 0 and part.within(fit.tolerance) == part.matched for part in fit.parts)
    assert [part.matched for part in fit.parts] == [6, 2, 2, 2, 2]
    assert _landing(_applied(design, fit), fit) == 0


def test_a_mirrored_reference_is_found() -> None:
    """Scenario "A mirrored reference is found": the reference drawn with the Y axis up gives a block
    transform with a mirror, and every part lands exactly where the Y-down reference puts it."""
    design = target()
    drawn = layout(reference())
    mirrored = fit_block(y_up(drawn), layout(design), BLOCK)
    plain = fit_block(drawn, layout(design), BLOCK)
    assert mirrored.issues == () and mirrored.transform is not None and mirrored.transform.mirror is True
    assert [part.placement for part in mirrored.parts] == [part.placement for part in plain.parts]
    assert all(part.residual is not None and part.residual <= UM for part in mirrored.parts)
    assert _landing(_applied(design, mirrored), mirrored) <= UM
    # a copy by the raw coordinates of the Y-up reference would put R1 below U1 instead of beside it
    r1 = next(part for part in mirrored.parts if part.ref == "R1")
    assert r1.placement is not None and r1.placement.at == Point(37 * MM, 18 * MM)
    assert not any(part.mirror_suspected or part.side_changed for part in mirrored.parts)


def test_a_part_without_a_fit() -> None:
    """Scenario "A part without a fit": ``R3`` of another pitch stays, with one ``reuse.no-fit``."""
    fit = fit_block(layout(reference()), layout(target(r3=WIDE)), BLOCK)
    assert [(found.code, found.severity, found.where) for found in fit.issues] == [
        ("reuse.no-fit", "error", "R3")
    ]
    r3 = next(part for part in fit.parts if part.ref == "R3")
    assert r3.placement is None and r3.matched == 2 and r3.within(fit.tolerance) == 0
    assert r3.residual == MM // 2
    assert [part.ref for part in fit.placed] == ["U1", "R1", "R2", "R4"]
    # a tolerance that covers the difference places it, each pad 0.5 mm from its goal
    loose = fit_block(layout(reference()), layout(target(r3=WIDE)), BLOCK, tolerance=MM // 2)
    assert loose.issues == () and len(loose.placed) == 5


def test_the_anchor_on_the_other_side() -> None:
    """With the anchor on the bottom, the block is flipped: every part takes the other side than its
    reference part, and no part is suspected."""
    design = target(anchor_side="bottom")
    fit = fit_block(layout(reference()), layout(design), BLOCK)
    assert fit.issues == () and fit.flipped is True
    assert fit.transform is not None and fit.transform.mirror is True
    sides = {part.ref: part.placement.side for part in fit.parts if part.placement is not None}
    assert sides == {"U1": "bottom", "R1": "bottom", "R2": "bottom", "R3": "bottom", "R4": "top"}
    assert all(part.side_changed for part in fit.parts)
    assert _landing(_applied(design, fit), fit) == 0


def test_another_anchor_gives_the_same_block() -> None:
    fit = fit_block(layout(reference()), layout(target()), BLOCK, anchor="U1")
    other = fit_block(layout(reference()), layout(_placed_r1()), BLOCK, anchor="R1")
    assert other.issues == ()
    assert [part.placement for part in other.parts] == [part.placement for part in fit.parts]


def _placed_r1() -> Design:
    """The target with ``R1`` already where the block wants it and ``U1`` in the row."""
    design = target()
    fit = fit_block(layout(reference()), layout(design), BLOCK)
    r1 = next(part for part in fit.parts if part.ref == "R1")
    assert r1.placement is not None
    u1 = next(part for part in fit.parts if part.ref == "U1")
    design = move_footprint(
        design, r1.footprint_id, at=r1.placement.at, rotation=r1.placement.rotation, definitions=DEFINITIONS
    )
    return move_footprint(
        design, u1.footprint_id, at=Point(30 * MM, 35 * MM), rotation=0, definitions=DEFINITIONS
    )


def test_a_two_pad_anchor_is_ambiguous_only_in_its_mirror() -> None:
    """``R1`` alone cannot tell a mirror: the anchor's own side decides, so the block is not mirrored."""
    fit = fit_block(layout(reference()), layout(_placed_r1()), ("R1", "R2"))
    assert fit.transform is not None and fit.transform.mirror is False and fit.issues == ()


def test_mapped_parts_of_a_second_channel() -> None:
    """``--map``: the parts of a second channel, ``U11`` and ``R11``, take the block of ``U1`` and
    ``R1``."""
    board = TieBoard()
    board.place("U11", IC6, Point(30 * MM, 20 * MM), nets=NETS["U1"])
    board.place("R11", CHIP, Point(10 * MM, 35 * MM), nets=NETS["R1"])
    fit = fit_block(
        layout(reference()), layout(board.build()), ("U11", "R11"), mapping={"U11": "U1", "R11": "R1"}
    )
    assert fit.issues == ()
    (_, r11) = fit.parts
    assert (r11.ref, r11.reference) == ("R11", "R1")
    assert r11.placement == Placement(Point(30 * MM, 15 * MM), 0, "top")


def test_unknown_parts() -> None:
    fit = fit_block(layout(reference()), layout(target()), ("U1", "R9"), mapping={"R9": "R1"})
    assert [(found.code, found.where) for found in fit.issues] == [("reuse.unknown-part", "R9")]
    fit = fit_block(layout(reference()), layout(target()), ("U1", "R1"), mapping={"R1": "R7"})
    assert [(found.code, found.where) for found in fit.issues] == [("reuse.unknown-part", "R7")]
    assert [part.ref for part in fit.parts] == ["U1"]
    fit = fit_block(layout(reference()), layout(target()), ("U9", "R1"))
    assert fit.transform is None and fit.parts == ()
    with pytest.raises(ValueError, match="anchor"):
        fit_block(layout(reference()), layout(target()), ("U1",), anchor="R1")
    with pytest.raises(ValueError, match="once"):
        fit_block(layout(reference()), layout(target()), ("U1", "U1"))


def test_an_anchor_without_a_fit() -> None:
    """An anchor of another footprint gives no block transform and places nothing."""
    fit = fit_block(layout(reference()), layout(target(r3=WIDE)), ("R3", "R1"))
    assert fit.transform is None and fit.parts == ()
    assert [(found.code, found.where) for found in fit.issues] == [("reuse.no-fit", "R3")]
    assert "nothing is placed" in fit.issues[0].message


def _mirrored_ic6() -> Footprint:
    """``IC6`` numbered clockwise: its mirror image."""
    footprint = Footprint(LIBRARY, "IC6M", kind="smd")
    for pad in IC6.pads:
        footprint.pad(
            pad.number, at=(nm(pad.position.x), nm(-pad.position.y)), size=(nm(pad.size.w), nm(pad.size.h))
        )
    return footprint


def test_a_mirrored_footprint_is_suspected() -> None:
    """A part whose footprint is the mirror of its reference part's fits only on the other side: it is
    placed there with ``reuse.mirror-suspected``."""
    mirrored = _mirrored_ic6().definition
    board = TieBoard()
    board.place("U1", IC6, Point(42 * MM, 18 * MM), nets=NETS["U1"])
    board.place("U2", mirrored, Point(10 * MM, 35 * MM), nets=NETS["U1"])
    source = TieBoard()
    source.place("U1", IC6, Point(20 * MM, 20 * MM), nets=NETS["U1"])
    source.place("U2", IC6, Point(30 * MM, 20 * MM), nets=NETS["U1"])
    design = board.build()
    fit = fit_block(layout(source.build()), layout(design), ("U1", "U2"))
    assert [(found.code, found.severity, found.where) for found in fit.issues] == [
        ("reuse.mirror-suspected", "warning", "U2")
    ]
    u2 = fit.parts[1]
    assert u2.placement is not None and u2.placement.side == "bottom" and u2.mirror_suspected
    definitions = {**DEFINITIONS, mirrored.lib_id: prepare_authored_definition(mirrored)}
    placed = move_footprint(
        design,
        u2.footprint_id,
        at=u2.placement.at,
        rotation=u2.placement.rotation,
        side=u2.placement.side,
        definitions=definitions,
    )
    assert _landing(placed, dataclasses.replace(fit, parts=(u2,))) == 0


def test_fit_rigid() -> None:
    """The least-squares translation, the preferred mirror among exact fits, and the refusal of no pair."""
    pairs = [(Point(0, 0), Point(10, 3)), (Point(4, 0), Point(10, 7))]
    found = fit_rigid(pairs, tolerance=0)
    assert found.transform.rot_udeg == 270_000_000 and found.transform.mirror is False
    assert found.residual == 0 and found.within(0) == 2
    assert fit_rigid(pairs, tolerance=0, mirror=True).transform.mirror is True
    noisy = fit_rigid([(Point(0, 0), Point(1, 0)), (Point(10, 0), Point(10, 0))], tolerance=10)
    assert noisy.transform.rot_udeg == 0 and noisy.distances == (1, 1)  # half a nanometre each, rounded up
    with pytest.raises(ValueError, match="pair"):
        fit_rigid([], tolerance=0)


def test_moved_placement() -> None:
    """A fit composed with a placement: a quarter turn about the origin moves a bottom part and turns it."""
    turn = fit_rigid([(Point(1, 0), Point(0, -1)), (Point(0, 1), Point(1, 0))], tolerance=0).transform
    assert turn.rot_udeg == 90_000_000
    placed = moved_placement(turn, Placement(Point(5 * MM, 0), 30_000_000, "bottom"))
    assert placed == Placement(Point(0, -5 * MM), 120_000_000, "bottom")


def _regulator(name: str, pads: tuple[tuple[str, float, float], ...]) -> FootprintDef:
    """An authored footprint whose pads may share a number (the DSL refuses a repeated number, so the
    pads are numbered apart, then renamed)."""
    footprint = Footprint(LIBRARY, name, kind="smd")
    for index, (_, x, y) in enumerate(pads):
        at = (nm(round(x * MM)), nm(round(y * MM)))
        footprint.pad(f"#{index}", at=at, size=(nm(MM // 2), nm(MM // 2)))
    definition = footprint.definition
    renamed = tuple(
        dataclasses.replace(pad, number=number)
        for pad, (number, _, _) in zip(definition.pads, pads, strict=True)
    )
    return prepare_authored_definition(dataclasses.replace(definition, pads=renamed))


REG = _regulator(
    "REG",
    (("1", -2, -1), ("2", -2, 1), ("3", 2, -1), ("GND", 0, -1), ("GND", 0, 0), ("GND", 0.5, 1)),
)
"""Three numbered pins and three pads numbered ``GND``, placed so that no turn maps them on each other."""
REG_NETS = {"1": "VIN", "2": "EN", "3": "GND", "GND": "GND"}
GNDS = _regulator("GNDS", (("GND", -1, 0), ("GND", 1, 0)))
"""Two pads numbered ``GND`` and nothing else: the partition cannot tell them apart."""


def _turn(design: Design, lib_id: str, definitions: dict[str, FootprintDef]) -> Design:
    """``design`` with the footprint of ``lib_id`` turned by 90°."""
    assert design.board is not None
    fp = next(fp for fp in design.board.footprints if fp.lib_ref == lib_id)
    return move_footprint(design, fp.id, rotation=90_000_000, definitions=definitions)


def _regulators(*, turned: bool) -> tuple[Design, Design]:
    """A reference block of ``U1`` (``REG``), ``R1`` and ``J1`` (``GNDS``), and a target board with the
    same parts elsewhere, ``U1`` turned by 90° when ``turned``."""
    source = TieBoard()
    source.place("U1", REG, Point(20 * MM, 20 * MM), nets=REG_NETS)
    source.place("R1", CHIP, Point(20 * MM, 16 * MM), nets={"1": "VIN", "2": "GND"})
    source.place("J1", GNDS, Point(26 * MM, 20 * MM), nets={"GND": "GND"})
    board = TieBoard()
    board.place("U1", REG, Point(40 * MM, 20 * MM), nets=REG_NETS)
    board.place("R1", CHIP, Point(10 * MM, 35 * MM), nets={"1": "VIN", "2": "GND"})
    board.place("J1", GNDS, Point(20 * MM, 35 * MM), nets={"GND": "GND"})
    design = board.build()
    if turned:
        design = _turn(design, REG.lib_id, {REG.lib_id: REG})
    return source.build(), design


@pytest.mark.parametrize("turned", [False, True])
def test_ground_pads_paired_by_their_nets_partition(turned: bool) -> None:
    """Scenario "Ground pads paired by their nets": the three ``GND`` pads of the anchor pair by net and
    lie on their goals; ``J1``, of two ``GND`` pads only, stays unpaired."""
    source, design = _regulators(turned=turned)
    fit = fit_block(layout(source), layout(design), ("U1", "R1", "J1"))
    u1, r1, j1 = fit.parts
    assert (u1.matched, u1.by_net) == (6, 3)
    assert sorted(match.number for match in u1.pads if match.by == "net") == ["GND", "GND", "GND"]
    assert len({match.pad_id for match in u1.pads}) == 6
    assert len({match.reference_pad_id for match in u1.pads}) == 6
    assert u1.residual is not None and u1.residual <= UM
    records = {record.pad_id: record for record in board_pads(design)}
    assert all(_far(records[match.pad_id].position, match.goal) <= UM for match in u1.pads)
    assert r1.placement is not None and r1.by_net == 0
    assert j1.placement is None and j1.matched == 0
    assert [(found.code, found.where) for found in fit.issues] == [("reuse.no-fit", "J1")]


def test_a_part_of_ground_pads_partition() -> None:
    """A part whose ``GND`` pads lie beside numbered pins is fitted on all its pads, turned with the
    block; its ``GND`` pads land on their goals."""
    source = TieBoard()
    source.place("U1", IC6, Point(20 * MM, 20 * MM), nets=NETS["U1"])
    source.place("U2", REG, Point(30 * MM, 20 * MM), nets=REG_NETS)
    board = TieBoard()
    board.place("U1", IC6, Point(42 * MM, 18 * MM), nets=NETS["U1"])
    board.place("U2", REG, Point(10 * MM, 35 * MM), nets=REG_NETS)
    design = _turn(board.build(), IC6.lib_id, DEFINITIONS)
    fit = fit_block(layout(source.build()), layout(design), ("U1", "U2"))
    assert fit.issues == ()
    u2 = fit.parts[1]
    assert (u2.matched, u2.by_net) == (6, 3) and u2.residual == 0
    assert u2.placement == Placement(Point(42 * MM, 8 * MM), 90_000_000, "top")
    placed = move_footprint(
        design,
        u2.footprint_id,
        at=u2.placement.at,
        rotation=u2.placement.rotation,
        definitions={**DEFINITIONS, REG.lib_id: REG},
    )
    pads = [record for record in board_pads(placed) if record.footprint_id == u2.footprint_id]
    for match in u2.pads:
        assert min(_far(record.position, match.goal) for record in pads if record.number == match.number) == 0
